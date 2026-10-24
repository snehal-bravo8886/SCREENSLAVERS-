"""Data integrity audit for Member 1, not a provenance certification."""
import argparse
import json
from datetime import datetime, timezone
from src.adapter import TransactionIngestionEngine
from run_module_a import load_source


def main():
    p = argparse.ArgumentParser()
    p.add_argument("source")
    p.add_argument("--base-date")
    p.add_argument("--step-minutes", type=float)
    p.add_argument("--allow-derived-ids", action="store_true")
    a = p.parse_args()
    from pathlib import Path
    frame, provenance = load_source(Path(a.source))
    date = datetime.fromisoformat(a.base_date).replace(tzinfo=timezone.utc) if a.base_date else None
    engine = TransactionIngestionEngine(base_datetime=date, step_minutes=a.step_minutes, allow_derived_ids=a.allow_derived_ids)
    transactions, labels = engine.load_from_dataframe(frame)
    report = {"input_provenance": provenance, "audit": engine.audit, "rejected_rows": engine.skipped_records,
              "integrity_passed": len(transactions) == len(frame) and len(transactions) > 0,
              "independent_benchmark_accuracy_verifiable": False,
              "note": "A clean input does not establish original IBM provenance or AML accuracy"}
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["integrity_passed"] else 1)

if __name__ == "__main__":
    main()
