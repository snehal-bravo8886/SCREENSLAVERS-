# Independent Member 4 execution verification

> Historical execution snapshot from before the current priority-formula update. Its old score outputs and source hashes are not current. See [`BACKEND_IMPLEMENTATION.md`](./BACKEND_IMPLEMENTATION.md) and [`FRONTEND_API_CONTRACT.md`](./FRONTEND_API_CONTRACT.md) for current formula and bundled-data outputs.

**Executed on the ChatGPT container on 23 October 2026.** The recipient must run the commands on their own Mac to confirm local environment compatibility; no claim is made that the ZIP has already run on their computer.

## Source identity verification

The core IBM code and handoff bytes in this package were compared against the actual previous ChatGPT-generated ZIP files:

| Source artifact | SHA-256 | Check |
|---|---|---|
| Module A `src/ibm_scenario.py` | `01fa22c294305b09748ef1169b7ad8ba5f4f1444d2998e3eb7e35018a4fb1ee1` | Exact same file |
| Module B `member_b/engine.py` | `e2c6db8cbfc07dbe0409e6fa1c340bb11432d6f4fb91e2c2f94ff26cf6a9d3b3` | Exact same file |
| Module A label-free handoff JSON | `93f57326a378d71813a6bf233a5cc8d1a8b9a388da7507b5798c53547ca4231d` | Exact same file |

**The original teammate CSV and obsolete Phase 1 backend are not present or used.**

## Actual test execution

```
python -m pytest tests -q
............................................................... [100%]
63 passed
```

The included tests cover original Member B regression tests, native Member A IBM ingestion/detectors, HTTP contracts, real-data case outputs, CORS, evidence traceability, label leakage, invalid input, malicious/invalid upload rejection, real archive re-analysis, disabled-cycle re-analysis, and failure rollback.

## Golden reference

- Input transactions: **120,558**
- Input alerts: **2,912**
- Cases: **2,573**
- Detector breakdown: **680 fan-in, 100 fan-out, 2,110 rapid flow, 22 cycles**
- Historical top case ID: **CASE-1086856BCDCD**
- Historical Stress Test output for **IBM20K-ROW-0005975** → **100.00 -> 95.26**
- Baseline case remains **unchanged** after stress test.

## Actual Uvicorn HTTP integration test

Server started using:

```
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8899
```

A separate HTTP client requested:

```
200 GET /health
200 GET /api/summary
200 GET /api/cases?limit=1
200 GET /api/cases/CASE-1086856BCDCD/graph
200 POST /api/cases/CASE-1086856BCDCD/stress-test
```

The POST returned `baseline_score=100.0`, `recomputed_score=95.26`, `membership_recomputed=false`.

## Scope that was NOT tested

- React frontend rendering on the member's computer (requires Member 3 UI).
- Actual multi-device LAN access or a remote cloud deployment.
- Production security/authentication or simultaneous heavy-user load testing.
- Independent true AML case-level precision/recall; IBM account labels do not provide that.
- Arbitrary uploaded CSVs not conforming to IBM AMLSim's published archived schema.
