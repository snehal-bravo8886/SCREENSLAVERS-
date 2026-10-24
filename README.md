# Screenslavers 

A work-in-progress investigation interface for **synthetic** financial transaction data.

**Current state:** a static dashboard shell with selectable account-centered sample transfers, a small offline dataset profile, and a FastAPI health-only scaffold. **The frontend and backend are not connected yet.** No fraud detection, risk scoring, investigation-case generation, network analysis, or Evidence Stress Test is operational in this checkpoint.

## What works so far

- Responsive HTML/CSS/JavaScript frontend showing four **UI examples**, not detected suspicious cases.
- Browsing and searching account-centered transaction rows from IBM AMLSim synthetic data.
- Standalone FastAPI `GET /health` endpoint (not connected to frontend).
- Dataset profile and an offline inspection script.

## Run frontend

```bash
cd frontend
python3 -m http.server 5173 --bind 127.0.0.1
```

Open http://127.0.0.1:5173. The page loads only `frontend/data/demo_cases.json`; it makes no backend requests.

## Run backend (optional)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```

Open http://127.0.0.1:8000/health.

## Dataset

The original synthetic archive is `20K_fanin200cycle200.tgz` from the [IBM AMLSim](https://github.com/IBM/AMLSim) ecosystem (120,558 transfers, 20,000 account rows, 149 steps). This GitHub checkpoint includes **a dataset profile and selected authentic sample rows**, not the full binary archive; GitHub's text-file upload integration cannot transmit the archive directly. To run the optional offline inspector, place the original archive at `data/20K_fanin200cycle200.tgz`. The full archive is also included in the separately provided midpoint ZIP.

The archive's `time` column is a discrete simulation index. We do not invent intraday timestamps, and we do not label these UI examples as fraud.

## Not yet implemented

- Pattern detectors: fan-in, fan-out, onward flow, cycles, mule-like flows
- Evidence-backed case grouping and calibrated risk scoring
- Interactive account network and evidence stress testing
- Frontend–backend API integration and persistence
- Validated fraud detection performance or live banking connections

See `docs/PROGRESS_CHECKLIST.md` and `docs/NEXT_STEPS.md` for scope.

## Folder layout

```
frontend/           Static dashboard and selected real synthetic transaction rows
backend/            Health-only FastAPI scaffold; offline archive inspection
data/               Dataset profile (place original archive here for inspection)
docs/               Progress checklist, provenance, and roadmap
```

All monetary values are synthetic units, not assumed INR.
