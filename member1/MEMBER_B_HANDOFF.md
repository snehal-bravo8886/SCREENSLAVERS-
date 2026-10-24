# Member B handoff — IBM AMLSim source-native (FINAL CONTRACT proposal)

**Owner:** Member A / Data & Detection. **Consume:** `examples/member_b_small_real_data_fixture.json` first, then `examples/member_b_IBM_20K_handoff.json`.

## The one non-negotiable difference from the earlier blueprint

The supplied IBM archive has ONLY integer simulation steps, not real clock timestamps. To avoid inventing dates, the **source-native** handoff schema has `timestamp: null`, `simulation_step: int`, `time_unit: "simulation_step"`. Alerts have `start_time: null`, `end_time: null`, `start_step: int`, `end_step: int`.

Member B must explicitly update their agreed case/risk schema to handle simulation steps. Do not interpret a step as 10, 30 or 60 minutes; no such duration was verified for this archive. When rendering on the dashboard, use “simulation step 25” instead of a fabricated calendar date.

## Actual JSON formats

```json
{
  "transaction_id": "IBM20K-ROW-0005916",
  "source_account": "9997",
  "destination_account": "5120",
  "amount": 260.85,
  "currency": "XXX",
  "timestamp": null,
  "simulation_step": 25,
  "time_unit": "simulation_step",
  "id_is_derived": true
}
```

**This is a real record from the uploaded IBM archive**, not a fabricated example. `XXX` means no currency was documented by the source.

```json
{
  "alert_id": "DET-FANIN-000001",
  "detector": "fan_in",
  "account_ids": ["5120", "9647", "9920", "9944", "9973", "9997"],
  "transaction_ids": ["IBM20K-ROW-0005916", "IBM20K-ROW-0006083", "IBM20K-ROW-0006356", "IBM20K-ROW-0007631", "IBM20K-ROW-0009178"],
  "start_time": null,
  "end_time": null,
  "start_step": 25,
  "end_step": 29,
  "time_unit": "simulation_step",
  "features": {"focus_account": "5120", "distinct_counterparties": 5, "transaction_count": 5, "total_amount": 1397.64, "window_steps": 4},
  "reason": "Candidate fan_in: 5 distinct counterparties in 4 simulation steps; may be routine activity"
}
```

The *full handoff* object is:

```json
{"schema_version":"member-a-simulation-step-v1", "dataset_summary": {"time_unit":"simulation_step", "currency":"XXX", "all_transaction_ids_derived":true, "transactions":120558, "alerts":2912}, "transactions": [], "alerts": []}
```

`transactions` and `alerts` in the actual file contain **real arrays**. The empty arrays shown immediately above merely abbreviate the schema display.

## Member B algorithm inputs and controls

- `transactions[]` preserves every individual source transfer with a *unique derived row ID*, normalized account IDs, amount and native step.
- `alerts[]` consists of candidate detector signals with exact source supporting IDs, step bounds and rule feature measurements. There are no supplied risk scores.
- To build cases, start from pairs of alerts sharing at least one supporting `transaction_id` within a bounded step interval. The real practice sample contains overlapping alerts for this purpose.
- Case-priority F/V/N/B factors must use **explicitly named simulation-step windows**, normalize to [0,1], and record evidence IDs. Historical B features should only use preceding steps. If no adequate history, mark B unavailable and renormalize available weights rather than inventing behavior.
- Candidate rapid onward flows do NOT prove the same physical funds are forwarded. Treat alert reasons as heuristics, not legal determinations.
- The Evidence Stress Test should recompute affected features after temporarily excluding one evidence transaction; source rows and other case data remain unchanged. Indicate whether case membership was fixed.
- The source has NO original per-transfer IDs or per-transfer SAR label; `DERIVED` identity is *not* proof of provenance beyond the archived CSV row. `nodes.csv` labels never appear in the handoff.

## Exact methods for Member D

```python
from pathlib import Path
from src.ibm_scenario import run_archive

result = run_archive(Path("data/20K_fanin200cycle200.tgz"), include_cycles=True)
transactions = [t.to_dict() for t in result["transactions"]]
alerts = result["alerts"]
# NEVER pass result["private_labels"] into Member B's case engine or frontend.
```

Or simply load `examples/member_b_IBM_20K_handoff.json` after verifying the SHA-256 in `reports/handoff_validation.json`.

## Completion tests

```bash
python -m pytest tests -q
python verify_handoff.py examples/member_b_IBM_20K_handoff.json
python verify_handoff.py examples/member_b_small_real_data_fixture.json --report reports/small_fixture_validation.json
```

**Not supported:** calibrated AML/fraud probability; claims of real-bank validation; precise minutes/hours; transaction-level recall; case-level precision without case-truth mapping; detection of all 200 IBM cycles under the optional 3-node constraint.
