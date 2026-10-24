# Screenslavers — Member 3, Complete Investigator Frontend

**Status:** Implemented, API-contract tested, and rendered in desktop/mobile browser harness using genuine responses from the final ChatGPT-generated Member 4 FastAPI service. **Not a mockup.**

This folder is intentionally a **zero-dependency HTML/CSS/ES-module JavaScript application**, not React. During delivery, the execution environment could not download npm dependencies; this implementation can be launched using macOS' Python without npm or Vite, and was tested against the live Member 4 API. This is a framework choice, not a change to the required product or API. If an event rule explicitly requires React, port this interface to React before submission; do not label the current code as React.

It **does not use** the original teammate-generated IBM-labeled CSV or any fake case data. All cases, alerts, graph edges, transaction steps, scores and sensitivity results are returned by the real backend APIs.

## 1. Run on your Mac (two Terminal windows)

**Prerequisite:** The consolidated Screenslavers repository, with backend and frontend in the same root folder.

Terminal window **A — backend**:

```bash
cd ~/Downloads/screenslavers
source .venv/bin/activate
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

If the environment is not initialized, follow the top-level `README.md` and install the root `requirements.txt` first.

Terminal window **B — frontend**:

```bash
cd ~/Downloads/screenslavers/frontend
python3 -m http.server 5173 --bind 127.0.0.1
```

Now open **http://127.0.0.1:5173/** (Safari or Chrome). The backend must show **Backend online** in the top bar. Do not double-click `index.html`: browser ES modules need a local static server.

**Expected:** 120,558 transactions, 2,912 alerts, 2,573 cases, top case `CASE-1086856BCDCD`, review priority 100.00. Cases show **simulation steps**, never invented clock times; transfer amounts are unspecified synthetic units, not dollars or rupees.

No npm install, React runtime, Vite, CDN scripts, or paid API keys are required. An optional Google Fonts stylesheet enhances appearance if the internet works; the UI also functions offline with system fonts.

### Running from a different machine

The documented baseline keeps both services on the **same Mac**, and the frontend calls `http://127.0.0.1:8000`. If moving the frontend to another machine, the backend developer must explicitly configure LAN binding and `SCREENSLAVERS_CORS_ORIGINS` for the frontend's exact origin. Then open the frontend with `?api=http://BACKEND-LAN-IP:8000`. Restrict this to trusted local networks; the backend is **not authenticated** and must not be publicly exposed.

## 2. What the frontend actually does

| UI capability | Real endpoint and behavior |
|---|---|
| Dataset summary and connection | `GET /health`, `/api/summary`, `/api/meta` |
| Case review queue | `GET /api/cases` — server pagination; filter by review status, search by case ID, min priority, detector type |
| Shared case review status | `PATCH /api/cases/{case_id}/review` — persistent To do / In progress / Done state stored by the backend |
| Case view | `GET /api/cases/{case_id}` — all original case alerts, 4 factors, transactions |
| Graph | Real `case.graph` — directed, unique parallel transaction edges; zoom, pan, node/edge selection |
| Timeline | Source-native simulation steps, real amounts and original-derived transaction IDs |
| Evidence explorer | Click a graph edge, timeline item, or alert to inspect source evidence |
| Priority explanations | Four factor contributions F/V/N/B; missing behavioral history is shown as unavailable |
| Evidence Stress Test | `POST /api/cases/{case_id}/stress-test` with one real case transaction ID; compare scores, changed factors, affected alerts; reset |
| Dataset dialog | `GET /api/datasets/current`, stage IBM `.tgz` with `POST /api/datasets/load`, then `POST /api/analyze` |
| Error and loading handling | Offline retry, API errors, empty case-filter results, loading states |
| Responsive view | Desktop, tablet, and stacked mobile layout |

The interface separates the investigation overview, case-review queue, individual case investigations, and methodology into navigable pages. Review status is shared by clients using the same backend and stored in `runtime/review_status.sqlite3`, scoped to the active run. This prototype has no authentication or per-investigator identity; only expose the backend on a trusted network.

**No backend algorithms were recreated or replaced in JavaScript.** This frontend never calculates an independent suspiciousness score; it renders source evidence and server-returned results.

### Evidence Stress Test golden walkthrough

1. Load `CASE-1086856BCDCD` (the first case in the queue).
2. Click the **Stress Test** tab on the right.
3. Select transaction **`IBM20K-ROW-0005975`**.
4. Click **Run Stress Test**.
5. Expected: baseline **100.00**, recomputed **95.26**, change **−4.74**; changed factor: `fund_flow`.
6. Click **Reset**. The original case remains at priority 100.00.

**Scientific scope:** This is **fixed-case evidence sensitivity**. It does not globally rerun pattern detection, recluster all cases, estimate a fraud probability, or establish AML precision/recall. The UI explicitly states that scope.

## 3. Files and handoff

```text
screenslavers/frontend/
├── index.html                 Main investigator UI
├── css/app.css                Responsive dark analytical design
├── js/api.js                  Single authoritative FastAPI client
├── js/graph.js                SVG directed multigraph (pan/zoom/select)
├── js/format.js               HTML safety, native-step formatting
├── js/app.js                  UI state, event handlers, all API flows
├── assets/icon.svg            Favicon
├── package.json               Optional `npm test`; installs nothing
├── tests/unit.test.mjs        JS unit and deterministic graph tests
├── tests/api-contract.test.mjs Live API contract tests
├── tests/visual_browser_test.py Rendered UI with real backend via Python bridge
├── tests/e2e.py               Optional Mac direct-browser test with Playwright
├── reports/                   Execution notes and rendered screenshots
├── FRONTEND_HANDOFF.md         Member 3 → Member 4 interface integration
├── QA_CHECKLIST.md            Judge-demo acceptance checklist
└── EXECUTION_VERIFICATION.md   What has and has not been verified
```

## 4. Tests

With Member 4 backend running:

```bash
cd ~/Downloads/screenslavers/frontend
npm test
```

This uses Node's **built-in test runner**, no installed packages. The automated unit tests work without a backend; live API tests are skipped if the backend isn't accessible. Ensure you see **all 9 tests passed and 0 skipped** before judging. If Node isn't installed, the browser app itself still runs normally.

Optional browser test on your own Mac:

```bash
python3 -m pip install playwright
python3 -m playwright install chromium
python3 tests/e2e.py
```

**Important:** The rendered-browser CI images used a transport bridge because Chromium in the authoring environment blocks direct URLs by administrative policy. Native browser HTTP/CORS and upload-to-analysis interactions require the final **manual local browser acceptance** in `QA_CHECKLIST.md`. The actual FastAPI CORS response to `Origin: http://127.0.0.1:5173` was verified separately.

## 5. Demo and presentation

Show: top counters → select real top case → click nodes/edges → see timeline and actual alerts → explain F/V/N/B factors → Stress Test 100.00 → 95.26 → reset. Keep the explanation factual: candidate patterns, synthetic source, native time steps, uncalibrated review priority.

The `reports/frontend_desktop.png`, `reports/frontend_stress_test.png` and `reports/frontend_mobile.png` show renderings from actual Member 4 API data, with no fake bank/customer data inserted into the UI.

**Screenshot note:** Historical screenshots showing the former project branding were intentionally excluded from this renamed repository. Generate new screenshots from the live Screenslavers dashboard if needed.
