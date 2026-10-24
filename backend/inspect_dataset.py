"""Inspect the original synthetic IBM AMLSim archive offline."""
from __future__ import annotations

import csv
import tarfile
from pathlib import Path

ARCHIVE = Path(__file__).resolve().parents[1] / "data" / "20K_fanin200cycle200.tgz"


def main() -> None:
    if not ARCHIVE.is_file():
        raise SystemExit(f"Missing original archive: {ARCHIVE}\nPlace the dataset here before running this script.")
    with tarfile.open(ARCHIVE, "r:gz") as tar:
        member = next((m for m in tar.getmembers() if m.name.endswith("/transactions.csv")), None)
        if member is None:
            raise RuntimeError("transactions.csv not found in archive")
        stream = tar.extractfile(member)
        if stream is None:
            raise RuntimeError("Unable to read transactions.csv")
        reader = csv.DictReader((line.decode("utf-8") for line in stream))
        expected = {"sourceNodeId", "targetNodeId", "value", "time"}
        if not expected.issubset(reader.fieldnames or ()):
            raise RuntimeError("Unexpected transaction schema")
        count, accounts, steps = 0, set(), set()
        for row in reader:
            count += 1
            accounts.update((row["sourceNodeId"], row["targetNodeId"]))
            steps.add(int(row["time"]))
    print("IBM AMLSim synthetic sample")
    print(f"Transactions: {count:,}")
    print(f"Accounts appearing in transfers: {len(accounts):,}")
    print(f"Simulation steps: {min(steps)} to {max(steps)} ({len(steps)} unique)")
    print("Note: simulation steps are not timestamps")


if __name__ == "__main__":
    main()
