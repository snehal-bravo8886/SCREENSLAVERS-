# MEMBER A — IBM AMLSim authentic-archive delivery

**Status: Full 20K archive processed and verified, 49 tests passing.** This is the Data & Detection module, not case ranking or risk scoring. All output alerts are transparent rule-based *candidates*, never accusations or calibrated criminal probabilities.

## Provenance and what is actually in the archive

- `data/20K_fanin200cycle200.tgz` is the user-uploaded pre-generated IBM/AMLSim `sample/20K_fanin200cycle200.tgz` archive, structurally matching the IBM GitHub release. It is NOT the team-generated `ibm_amlsim_1000.csv`.
- SHA-256 of uploaded archive: `f187bc5784223cdee137ac603164f7183fd58f114090f39e2a12543b6bf48319`
- Contains `transactions.csv` (120,558 rows, `sourceNodeId,targetNodeId,value,time`), `nodes.csv` (20,000 accounts, `nodeid,isFraud,init_balance,fraudStep`), and `metadata.txt` (states 200 fan-in, 200 cycles).
- **Discrepancy:** metadata reports 1,803 fraud nodes, but `nodes.csv` contains **1,804** `isFraud=1` rows. We report the disagreement; source labels remain private offline-only data.
- **No original transaction identifiers, currency, or absolute clock dates are supplied**. Derived identifiers `IBM20K-ROW-0000001` etc. preserve the original row number (not bank-issued IDs); transaction times remain raw integer **simulation steps**. No date, hour, minute, UPI context, real bank or currency is asserted.
- The file is supplied as an upload; published source page: https://github.com/IBM/AMLSim/blob/master/sample/20K_fanin200cycle200.tgz . The reported SHA-256 establishes reproducibility of this copy. It is *not* a cryptographic upstream comparison to IBM's original bytes.

## Run this in Terminal (Mac, Linux)

```bash
cd ~/Downloads/screenslavers/member1
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest tests -q
python run_ibm_20k.py --cycles
python verify_handoff.py examples/member_b_IBM_20K_handoff.json
```

Windows PowerShell: use `.venv\\Scripts\\Activate.ps1` rather than `source .venv/bin/activate`.

**Measured actual execution** (on uploaded source, optional cycles enabled):
- 120,558 accepted transaction records; **19,980** nodes occur in transfers; 20,000 listed in account table; 120,558 distinct graph edges; 0 rejected source rows.
- 2,912 candidate alerts: **680 fan-in, 100 fan-out, 2,110 rapid onward, 22 strictly step-ordered 3-node cycles**. Those 22 alerts are *not* a recall estimate against the 200 declared cycle scenarios.
- 49/49 unit and regression tests passed. Core processing ~1.7–2.0 seconds in the container used for this run, excluding JSON serialization and install time. Times vary by machine.
- All alert and evidence IDs, account membership, step ranges and label-free public exports verified by `verify_handoff.py`.

### Deliverables for Member B

1. `examples/member_b_small_real_data_fixture.json`: 237 authentic rows + 4 overlapping alerts, suitable for building and testing case grouping first (plus limited account history). **Not** a benchmark or a complete background baseline.
2. `examples/member_b_IBM_20K_handoff.json`: **120,558 normalized transfers + 2,912 alerts**, full authoritative JSON interface, no ground truth.
3. `MEMBER_B_HANDOFF.md`: field names, time-unit constraints, important scoring implications.
4. `reports/IBM_20K_verified_run.json`: actual count, data/source SHA, experimental configurations, account-level exploratory statistics, limitations.
5. `reports/handoff_validation.json`: full validation result and output SHA-256.

### Code responsibilities

- `src/ibm_scenario.py`: fail-closed real-archive ingestion; directed NetworkX multigraph; fan-in, fan-out, rapid onward and optional three-edge time-ordered cycle detectors; offline-only account-label audit.
- `src/ibm_schemas.py`: strict Pydantic v2 contract for source-native simulation steps.
- `run_ibm_20k.py`: default official archive runner and JSON exporter.
- `verify_handoff.py`: validates *exported JSON* for ID/evidence integrity, step bounds, schema and forbidden fields.
- `create_member_b_fixture.py`: derives a small practice fixture from real IBM transactions and overlapping alerts.
- `tests/`: 49 runnable tests, including the original dataset adapter tests.
- `src/adapter.py`, `run_module_a.py`: kept for separate legacy/newer CSV formats; **use `run_ibm_20k.py` for this particular 20K archive**. They do not magically support `sourceNodeId/targetNodeId/value/time` or substitute guessed ISO timestamps.

## Detector definitions — hypotheses, not ground-truth logic

- Fan-in and fan-out: at least 5 distinct inbound/outbound counterparties within a **4-simulation-step inclusive window**, max 2 emitted windows per account.
- Rapid onward: A→B followed by B→C in **1–3 strictly increasing simulation steps**, outgoing amount 80–100% of incoming (same unspecified synthetic amount unit), max 5 pair alerts per intermediary; inflow used once per intermediary. This does not trace identifiable currency units.
- Optional cycles: strict A→B→C→A with strictly increasing steps within **12 steps**; maximum 1,000 emitted alerts. This 3-edge rule cannot discover every possible multi-node cycle or every IBM injected scenario.
- Account labels and `fraudStep` are isolated for offline audit and **never** supplied to graph building, detection, Member B handoff or frontend. Normal payroll/payment-provider flows can create many flagged patterns.

## Important constraints for Member 2 / 4

1. **Do not expect an ISO datetime.** Each transaction has `timestamp:null`, `simulation_step:<int>`, `time_unit:"simulation_step"`; each alert uses `start_step`, `end_step`, and has `start_time/end_time:null`.
2. **Do not use minutes/hours or the earlier hardcoded F/V/N/B time windows** without an externally verified mapping to real time. Adapt Member B's velocity/behavior calculations to raw step intervals; document settings and missing historic baselines.
3. Derived source-row IDs remain stable only if original archive row order is preserved; never sort/rewrite transaction rows then regenerate the IDs.
4. For defensible evaluation, `isFraud` is **account-level** and the archive lacks an explicit mapping from 200+200 scenarios to each transfer. Therefore account-label overlap is an exploratory diagnostic, **not** transaction-precision, scenario Recall@K, case Precision@K or claimed detection accuracy.
5. This is a real, tested Member A ingestion/detector **engineering** handoff. Any claim of verified AML accuracy, calibrated score, broad false-positive rate, recall of 200 cycles, or industry deployment would be misleading.

See `DATA_PROVENANCE.md`, `MEMBER_B_HANDOFF.md`, and `EXECUTION_VERIFICATION.md` for details.
