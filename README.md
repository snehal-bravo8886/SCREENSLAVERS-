# Screenslavers — Financial Transaction Investigation Workbench

A four-member, evidence-aware **local prototype** for investigating candidate suspicious patterns in **synthetic IBM AMLSim** transaction data. This is **not** a fraud probability model or a production banking service.


## What it does

1. **Member 1 — Data + detection:** parses the authentic IBM AMLSim 20K scenario, builds a directed graph, and flags rapid pass-through, fan-in, fan-out and temporal-cycle patterns, preserving source transaction IDs.
2. **Member 2 — Case intelligence:** groups related alerts into cases, assigns a transparent **0–100 investigation-priority index**, and performs a fixed-membership evidence sensitivity ("Stress Test"). The index is **not** a probability of crime.
3. **Member 3 — Frontend:** dependency-free HTML/CSS/JavaScript investigator workspace with case queue, interactive graph, timeline, evidence and Stress Test. **It is not React**.
4. **Member 4 — Backend:** FastAPI orchestration and validation, real case and graph APIs, dataset upload/re-analysis, evidence retrieval, and CORS for local development.

The baseline handoff is derived from a synthetic IBM AMLSim archive. Its native time field is a **simulation step**, not a real-world date or minute; amounts are unspecified synthetic units.

## Repository structure

```text
screenslavers/
├── backend/            # Member 4 FastAPI endpoints and registry
├── member_b/           # Member 2 case grouping, scoring and Stress Test
├── src/                # IBM-native importer used by the integrated backend
├── member1/            # Complete standalone Member 1 source, tests, reports
├── frontend/           # Member 3 static frontend, tests and styles
├── data/               # Verified IBM archive and baseline A→B handoff
├── tests/              # Integrated backend, Member 2 and Member 1 API tests
├── scripts/            # Backend smoke tests
├── docs/               # Architecture, API contract and module documentation
├── requirements.txt    # Backend Python dependencies
├── start_backend.sh
└── start_frontend.sh
```

Member 2's **actual implementation** is `member_b/engine.py`. The backend's `src/` contains the final IBM-native importer; the complete standalone Member 1 implementation lives under `member1/src/` (kept separate to prevent Python import collisions).

## Run on macOS (two Terminal windows)

**Terminal 1 — Backend** (from repository root):

```bash
cd screenslavers
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
./start_backend.sh
```

**Terminal 2 — Frontend** (from repository root):

```bash
cd screenslavers
./start_frontend.sh
```

Open **http://127.0.0.1:5173/** for the dashboard, or **http://127.0.0.1:8000/docs** for the API documentation. Both processes must stay running.

The frontend talks to the API on `127.0.0.1:8000`. The backend accepts local dev origins from port `5173`. Override using `SCREENSLAVERS_CORS_ORIGINS` (comma-separated) if needed.

## Test

```bash
# From repository root, with .venv activated
python -m pytest tests -q
python -m scripts.smoke_test

# Standalone Member 1 tests (different src/ package)
cd member1
python -m pytest tests -q
cd ..

# Frontend tests (Node.js required; no npm install)
cd frontend
npm test
cd ..
```

## Baseline demonstration

The included handoff represents **120,558 transactions**, **2,912 candidate alerts**, and **2,573 investigation cases**. With `context_evidence_v2_heuristic`, the current highest-ranked case is `CASE-764AF65F8AE8` at **97.95**. Case `CASE-1086856BCDCD` scores **96.32**; excluding `IBM20K-ROW-0005975` produces **86.31** in the fixed-membership sensitivity test. These are deterministic outputs for the loaded handoff, not independently validated fraud-detection accuracy.

The current `context_evidence_v2_heuristic` priority score is **P = 100 × (0.45M + 0.35A + 0.20C)**. **M** is the maximum severity among active alerts; **A** is the highest focus-account activity anomaly, combining a peer midrank percentile and (when enough prior history exists) historical deviation; **C** measures nonredundant evidence support from detector families after duplicate-family and high-overlap alerts are discounted. The three components are normalized to 0–1, their weighted contributions are rounded individually to two decimals, then summed. Stress Tests keep the case window, membership, and peer reference distribution fixed while recalculating alert status, focus-account activity, and evidence support after exclusions. Formula behavior is tested; predictive accuracy has **not** been measured because account-level evaluation labels are withheld.

## Dataset and limitations

- The bundled `data/20K_fanin200cycle200.tgz` is the IBM AMLSim synthetic 20K scenario; provenance and assumptions are documented in [`member1/DATA_PROVENANCE.md`](member1/DATA_PROVENANCE.md).
- IBM account-level answer labels are excluded from the case API and detection/scoring path.
- The backend is designed for a local, single-worker demo; active uploaded analyses are held in memory and reset on restart.
- A case score of 100 means maximum heuristic review priority, **not 100% fraud likelihood**.
- Evidence Stress Test keeps case membership fixed; it does not rerun every detector and regroup the entire dataset.
- See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and [`docs/FRONTEND_API_CONTRACT.md`](docs/FRONTEND_API_CONTRACT.md).

## Team workflow

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for branch/PR rules and [`docs/GITHUB_SETUP.md`](docs/GITHUB_SETUP.md) for publishing and adding collaborators.

## Licensing

No project license has been selected. The frontend's package manifest currently declares `UNLICENSED`; do not assume permission to redistribute third-party content outside its source license. Verify the source dataset's applicable terms before publishing publicly.
