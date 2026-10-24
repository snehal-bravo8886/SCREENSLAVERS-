"""Member 4 orchestration over the FINAL ChatGPT-generated Module A/B interfaces.

This module never passes IBM account-level fraud labels into Module B or API responses.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from threading import Lock, RLock
from typing import Any
import json
import tarfile
import uuid

from member_b import CaseEngine, load_handoff
from src.ibm_scenario import ingest_archive, run_archive

BASELINE_HANDOFF_SHA256 = "93f57326a378d71813a6bf233a5cc8d1a8b9a388da7507b5798c53547ca4231d"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED = 15 * 1024 * 1024
REQUIRED_IBM_MEMBERS = {"transactions.csv", "nodes.csv", "metadata.txt"}

class ApiFault(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_archive_check(path: Path) -> None:
    """Reject hazardous tar shapes BEFORE handing contents to Module A.

    Archives are NEVER extracted to the server filesystem. Limit both compressed
    and expanded size; disallow links, duplicate basename ambiguity and extras.
    """
    if not path.is_file() or path.stat().st_size > MAX_UPLOAD_BYTES:
        raise ApiFault(413, "Archive exceeds maximum compressed size of 10 MiB")
    try:
        with tarfile.open(path, "r:gz") as arc:
            entries = {}
            expanded = 0
            for m in arc:
                if m.isdir():
                    continue
                if not m.isfile():
                    raise ApiFault(400, "Archive contains unsupported links or special entries")
                base = Path(m.name).name
                if base in entries:
                    raise ApiFault(400, f"Duplicate archive member name: {base}")
                if ".." in Path(m.name).parts or m.name.startswith("/"):
                    raise ApiFault(400, "Archive has unsafe member paths")
                if m.size < 0:
                    raise ApiFault(400, "Archive contains invalid member size")
                expanded += m.size
                if expanded > MAX_TOTAL_UNCOMPRESSED:
                    raise ApiFault(413, "Archive exceeds expanded size limit of 15 MiB")
                entries[base] = m.size
            if not REQUIRED_IBM_MEMBERS.issubset(entries):
                raise ApiFault(400, "Expected IBM AMLSim transactions.csv, nodes.csv and metadata.txt")
    except (tarfile.TarError, EOFError, OSError) as exc:
        raise ApiFault(400, "Archive is not a valid gzip-compressed tar file") from exc


def _safe_summary(engine: CaseEngine, *, mode: str, digest: str, version: str,
                  archive_name: str | None, graph_accounts: int | None,
                  breakdown: dict[str,int] | None) -> dict[str,Any]:
    stat = engine.statistics()
    return {
        "run_id": version,
        "dataset": "IBM AMLSim synthetic 20K scenario",
        "source": mode,
        "source_archive": archive_name,
        "source_sha256": digest,
        "source_hash_type": "handoff_json" if mode == "verified_module_a_handoff" else "archive_tgz",
        "schema_version": "member-a-simulation-step-v1",
        "time_unit": "simulation_step",
        "currency": "XXX",
        "score_name": "Investigation priority index (0-100)",
        "score_is_probability": False,
        "transactions": stat["input_transactions"],
        "alerts": stat["input_alerts"],
        "cases": stat["cases"],
        "active_accounts": graph_accounts,
        "alert_breakdown": breakdown,
        "case_statistics": stat,
        "limitations": [
            "Time is measured in native simulation steps, not dates, hours or minutes.",
            "Amounts are in unspecified synthetic monetary units (XXX).",
            "Detection rules and review-priority weights are uncalibrated heuristics.",
            "Account-level source labels are withheld from the case engine and public API.",
            "Stress Test recalculates fixed-case evidence sensitivity, not complete re-detection/regrouping.",
        ],
    }


class Registry:
    """Keep a fully prepared immutable run; replace it atomically after analysis."""
    def __init__(self, seed_path: Path, archive_path: Path, upload_dir: Path):
        self.seed_path = Path(seed_path)
        self.archive_path = Path(archive_path)
        self.upload_dir = Path(upload_dir)
        self._state_lock = RLock()
        self._analysis_lock = Lock()
        self.engine: CaseEngine | None = None
        self.summary: dict[str,Any] | None = None
        self.pending_archive: Path | None = None
        self.pending_sha256: str | None = None
        self.active_generation = 0
        self.last_analysis_utc: str | None = None

    def startup(self) -> None:
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        raw = self.seed_path.read_bytes()
        checksum = sha256(raw).hexdigest()
        if checksum != BASELINE_HANDOFF_SHA256:
            raise RuntimeError("Bundled Module A handoff SHA-256 mismatch: refusing unverified seed")
        payload = json.loads(raw)
        engine = CaseEngine(payload)
        engine.build_cases()
        expected_breakdown = dict(Counter(a["detector"] for a in payload["alerts"]))
        accounts = payload.get("dataset_summary", {}).get("accounts")
        summary = _safe_summary(engine, mode="verified_module_a_handoff", digest=checksum,
            version="RUN-BASELINE-IBM20K", archive_name=self.archive_path.name,
            graph_accounts=accounts, breakdown=expected_breakdown)
        with self._state_lock:
            self.engine = engine
            self.summary = summary
            self.active_generation = 1
            self.last_analysis_utc = _now()

    def current(self) -> tuple[CaseEngine,dict]:
        with self._state_lock:
            if self.engine is None or self.summary is None:
                raise ApiFault(503, "Dataset analysis not initialized")
            return self.engine, self.summary

    def dataset_status(self) -> dict:
        _, summary = self.current()
        with self._state_lock:
            return {"ready": True,
                    "active_run_id": summary["run_id"],
                    "active_source": summary["source"],
                    "active_archive": summary["source_archive"],
                    "pending_upload": self.pending_archive.name if self.pending_archive else None,
                    "pending_sha256": self.pending_sha256,
                    "last_analysis_utc": self.last_analysis_utc,
                    "analysis_in_progress": self._analysis_lock.locked(),
                    "time_unit": "simulation_step",
                    "reanalysis_requires_explicit_post": True}

    def stage_upload(self, source: Path, digest: str) -> dict:
        # Hold same lock as analyze while selecting/replacing the archive.
        if not self._analysis_lock.acquire(blocking=False):
            raise ApiFault(409, "Cannot replace pending archive while analysis is running")
        try:
            with self._state_lock:
                old = self.pending_archive
                self.pending_archive = source
                self.pending_sha256 = digest
            if old is not None and old != source:
                old.unlink(missing_ok=True)
            return {"staged": True, "filename": source.name, "sha256": digest,
                    "requires_analyze": True,
                    "note": "Validated IBM source format. Detection and cases are not updated until POST /api/analyze."}
        finally:
            self._analysis_lock.release()

    def analyze(self, *, include_cycles: bool = True) -> dict:
        if not self._analysis_lock.acquire(blocking=False):
            raise ApiFault(409, "A dataset analysis is already in progress")
        try:
            with self._state_lock:
                path = self.pending_archive or self.archive_path
                original_staged = self.pending_archive
            safe_archive_check(path)
            result = run_archive(path, include_cycles=include_cycles)
            payload = {"schema_version": "member-a-simulation-step-v1",
              "dataset_summary": {"transactions": len(result["transactions"]),
                "accounts": result["graph_node_count"], "alerts": len(result["alerts"]),
                "time_unit": "simulation_step", "currency": "XXX",
                "all_transaction_ids_derived": True, "score_is_probability": False},
              "transactions": [t.to_dict() for t in result["transactions"]],
              "alerts": result["alerts"]}
            engine = CaseEngine(payload)
            engine.build_cases()
            digest = sha256(path.read_bytes()).hexdigest()
            with self._state_lock:
                next_number = self.active_generation + 1
            summary = _safe_summary(engine, mode="archive_reanalysis", digest=digest,
                version=f"RUN-{next_number}-{digest[:10].upper()}",
                archive_name=path.name,graph_accounts=result["graph_node_count"],
                breakdown=result["alert_breakdown"])
            with self._state_lock:
                self.engine = engine
                self.summary = summary
                self.active_generation = next_number
                self.last_analysis_utc = _now()
                # An upload remains selected for subsequent re-analysis.
                assert self.pending_archive == original_staged
            return summary
        except ApiFault:
            raise
        except (ValueError, OSError, AssertionError) as exc:
            raise ApiFault(400, f"Dataset analysis failed validation: {exc}") from exc
        finally:
            self._analysis_lock.release()
