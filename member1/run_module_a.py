#!/usr/bin/env python3
"""Run Member A on a CSV or an IBM AMLSim .tgz file; export actual evidence.

Examples:
  python run_module_a.py data/controlled_test_fixture.csv
  python run_module_a.py data/ibm_amlsim_official_sample_tx.csv \
       --base-date 2017-01-01 --step-minutes 1440
  python run_module_a.py data/20K_fanin200cycle200.tgz \
       --base-date 2017-01-01 --step-minutes 1440 --allow-derived-ids

NOTE: 1440 is an explicitly selected DAY-STEP analysis assumption, not a
verified timestamp duration for all AMLSim exports.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from src.pipeline import FinancialCrimeDetectionPipeline


def load_source(path: Path):
    """Load one raw CSV without extracting a potentially unsafe archive to disk."""
    if not path.is_file():
        raise FileNotFoundError(path)
    name = path.name.lower()
    if name.endswith((".tgz", ".tar.gz")):
        with tarfile.open(path, "r:gz") as tf:
            files = [m for m in tf.getmembers() if m.isfile() and m.name.lower().endswith(".csv")]
            def rank(m):
                n = Path(m.name).name.lower()
                # Never pick alerts.csv / account tables as transaction input.
                priority = 0 if n == "transactions.csv" else 1 if n == "tx.csv" else 2
                return (priority, n)
            ordered = sorted(files, key=rank)
            recognized = []
            for m in ordered:
                if any(w in m.name.lower() for w in ("alert", "member", "account", "node", "balance")):
                    continue
                if m.size > 120_000_000:
                    raise ValueError(f"Refusing oversized CSV member: {m.name}")
                f = tf.extractfile(m)
                if f is None:
                    continue
                raw = f.read()
                header = pd.read_csv(io.BytesIO(raw), nrows=0).columns
                lowered = {c.lower() for c in header}
                if (lowered & {"source", "src", "sender", "orig_acct", "account_id", "source_account", "from", "source_id"}) and (
                    lowered & {"target", "dst", "receiver", "bene_acct", "counter_party_account_num", "destination_account", "to", "target_id"}
                ) and (lowered & {"amount", "base_amt", "txn_amount_orig", "weight"}):
                    recognized.append((m.name, raw))
            if not recognized:
                candidates = [m.name for m in files]
                raise ValueError("No supported transactions CSV found in archive. Contents: " + str(candidates))
            selected_name, content = recognized[0]
            return pd.read_csv(io.BytesIO(content), dtype=str, keep_default_na=False), {
                "archive_member": selected_name,
                "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "transaction_csv_sha256": hashlib.sha256(content).hexdigest(),
                "input_type": "IBM AMLSim archive contents",
            }
    if name.endswith(".csv"):
        raw = path.read_bytes()
        return pd.read_csv(io.BytesIO(raw), dtype=str, keep_default_na=False), {
            "input_type": "CSV",
            "archive_member": None,
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "transaction_csv_sha256": hashlib.sha256(raw).hexdigest(),
        }
    raise ValueError("Expected .csv, .tgz or .tar.gz")


def arguments():
    p = argparse.ArgumentParser(description="Verified-input Member A transaction detector")
    p.add_argument("source", type=Path, help="IBM AMLSim transaction CSV or a pre-generated archive")
    p.add_argument("--base-date", help="Explicit simulation origin, e.g. 2017-01-01 (UTC)")
    p.add_argument("--step-minutes", type=float, help="Explicit duration for ONE simulation step")
    p.add_argument("--allow-derived-ids", action="store_true", help="If source lacks transaction IDs, label stable synthetic row IDs")
    p.add_argument("--rapid-window-minutes", type=int, default=60)
    p.add_argument("--fan-window-minutes", type=int, default=120)
    p.add_argument("--fan-counterparties", type=int, default=3)
    p.add_argument("--cycles", action="store_true", help="Enable optional bounded cycle detector")
    p.add_argument("--strict", action="store_true", help="Fail if any transaction row was rejected")
    p.add_argument("--report", type=Path, default=Path("reports/member_a_run.json"))
    p.add_argument("--handoff", type=Path, default=Path("examples/member_b_handoff.json"))
    return p.parse_args()


def main():
    args = arguments()
    if (args.base_date is None) != (args.step_minutes is None):
        raise SystemExit("Supply both --base-date and --step-minutes, or neither")
    origin = None
    if args.base_date:
        origin = datetime.fromisoformat(args.base_date.replace("Z", "+00:00"))
        if origin.tzinfo is None:
            origin = origin.replace(tzinfo=timezone.utc)
    df, provenance = load_source(args.source)
    p = FinancialCrimeDetectionPipeline(
        base_datetime=origin, step_minutes=args.step_minutes,
        allow_derived_ids=args.allow_derived_ids,
        rapid_pass_window_mins=args.rapid_window_minutes,
        fan_window_mins=args.fan_window_minutes,
        fan_counterparties=args.fan_counterparties,
        enable_cycle_detector=args.cycles)
    started = time.perf_counter()
    result = p.run_from_dataframe(df)
    elapsed = time.perf_counter() - started
    if args.strict and result.skipped_records:
        raise ValueError(f"Strict mode: {len(result.skipped_records)} input rows rejected")
    report = {"input": str(args.source), "provenance": provenance,
              "input_audit": result.audit,
              "config": {"base_date": origin.isoformat() if origin else None,
                         "step_minutes": args.step_minutes,
                         "time_units_verified_by_source": False if args.step_minutes else None,
                         "rapid_window_minutes": args.rapid_window_minutes,
                         "fan_window_minutes": args.fan_window_minutes,
                         "fan_counterparties": args.fan_counterparties,
                         "cycles_enabled": args.cycles},
              "run_result": result.public_summary(),
              "runtime_seconds": round(elapsed, 4),
              "rejected_rows": result.skipped_records,
              "note": "Rule-based candidates, not proof or a calibrated laundering probability. "
                      "No independent ground-truth score computed from this file."}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.handoff.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.handoff.write_text(json.dumps(result.handoff_to_member_b(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["run_result"], indent=2))
    print("Dataset provenance audit:", args.report)
    print("Member 2 safe transaction/alert handoff:", args.handoff)


if __name__ == "__main__":
    main()
