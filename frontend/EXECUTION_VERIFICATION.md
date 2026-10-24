# Module 3 — Execution and verification report (2026-10-23)

## Tested with the final Member 4 backend

Backend: `screenslavers` running under Uvicorn on `127.0.0.1:8000`.
Frontend: static files served by Python `http.server` on port 5173.

- HTTP GET `/health` from Python/curl: **200**.
- HTTP GET frontend `/` and `/js/app.js`: **200**, with expected static content types.
- CORS test, `Origin: http://127.0.0.1:5173`: `access-control-allow-origin: http://127.0.0.1:5173` confirmed.
- Node built-in tests: **9 passed, 0 failed, 0 skipped**, while real backend was running.
- API contract tests exercised genuine summary, case queue, filtered cases, complete case details, 25 directed edges, 25 timeline records and Stress Test.
- Rendered browser test via local Python transport bridge: **PASS** desktop/mobile, graph interactions, account filter, selected transaction, factor view, Stress Test, reset, detector filter, search and dataset modal.
- Real selected case: `CASE-1086856BCDCD`, priority 100.00, 7 alerts, 25 original evidence transfers.
- Golden Stress Test: `IBM20K-ROW-0005975` → **100.00 to 95.26**, original state unchanged.
- Files `reports/frontend_desktop.png`, `reports/frontend_stress_test.png`, `reports/frontend_mobile.png` are rendered UI screenshots using **real Member 4 API JSON** (browser network bridged due CI policy).

## Not yet proved

- This environment's enterprise-policy Chromium blocks direct web navigation, including `127.0.0.1`. Therefore the screenshots and interaction tests use the actual bundled JS/CSS/HTML loaded into a browser `about:blank` plus an explicit local Python transport bridge to the real Uvicorn API. **This is not the same as a successful direct-browser fetch or manual cross-origin test on a Mac.** HTTP CORS headers were separately checked with curl.
- Archive upload and subsequent analyze were implemented against the documented Member 4 endpoints, but have **not** been manually executed using the actual browser file picker during this test pass. Test with `QA_CHECKLIST.md` on Mac if that is part of the demo.
- No React/Vite build was performed because this package uses dependency-free web modules. Do not call it a React frontend.
- No measured money-laundering accuracy, false-positive rate or recall is asserted.

## Known scope

- Backend is locally hosted with no user login; do not expose it to the public network.
- SVG case graph is intentionally limited to bounded case subgraphs; no attempt is made to render 120,558 edges simultaneously.
- Data is purely synthetic IBM AMLSim; source step units and unspecified monetary units are preserved.
