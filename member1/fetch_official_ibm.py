#!/usr/bin/env python3
"""Retrieve ORIGINAL public IBM/AMLSim samples (not user-created AMLSim-lookalikes).
The archive is retrieved from IBM's own official GitHub repository.
"""
import argparse
import hashlib
import json
import tarfile
import urllib.request
from pathlib import Path

URLS = {
    "official-tiny": "https://raw.githubusercontent.com/IBM/AMLSim/master/sample/outputs/tx.csv",
    "official-20k": "https://raw.githubusercontent.com/IBM/AMLSim/master/sample/20K_fanin200cycle200.tgz",
}


def main():
    p = argparse.ArgumentParser(description="Download an authentic IBM AMLSim source file")
    p.add_argument("which", choices=sorted(URLS))
    p.add_argument("--output-dir", type=Path, default=Path("data"))
    p.add_argument("--sha256", help="Optional independently established expected SHA256")
    args = p.parse_args()
    target = args.output_dir / ("ibm_official_sample_tx.csv" if args.which == "official-tiny" else "20K_fanin200cycle200.tgz")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(URLS[args.which], headers={"User-Agent": "Screenslavers-AMLSim-Data-Fetch/1.0"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        content = resp.read(100_000_001)
    if len(content) > 100_000_000:
        raise ValueError("Refusing unexpectedly large dataset")
    digest = hashlib.sha256(content).hexdigest()
    if args.sha256 and digest.lower() != args.sha256.lower():
        raise ValueError("SHA256 DOES NOT MATCH provided expected digest")
    # Basic source-format sanity before storing.
    if target.suffix == ".tgz":
        import io
        with tarfile.open(fileobj=io.BytesIO(content), mode="r:gz") as tf:
            if not any(m.name.lower().endswith(".csv") for m in tf.getmembers()):
                raise ValueError("Archive contains no CSV files")
    else:
        if b"TXN_ID,ACCOUNT_ID,COUNTER_PARTY_ACCOUNT_NUM" not in content[:300]:
            raise ValueError("IBM example CSV header unexpected")
    target.write_bytes(content)
    manifest = {"file": str(target), "url": URLS[args.which], "sha256": digest,
                "byte_size": len(content), "official_origin": "IBM/AMLSim repository",
                "independent_expected_hash_checked": bool(args.sha256)}
    (target.parent / (target.name + ".source.json")).write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
