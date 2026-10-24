# Member 3 → Member 4: Frontend Integration Handoff

## Frozen assumptions and usage

- **Backend base:** `http://127.0.0.1:8000`, bound only to the local Mac.
- **Frontend:** `http://127.0.0.1:5173`, local Python static server (`python3 -m http.server 5173 --bind 127.0.0.1`).
- **Backend allowed CORS origins:** includes `http://127.0.0.1:5173`.
- Frontend is **ES-module JavaScript, HTML and CSS, not React**; requires no package manager for execution.
- React conversion is optional only if required by competition technology rules.
- All case data comes from final ChatGPT-generated Member 1/2 via final Member 4 FastAPI.

## Source of truth endpoints

| Frontend | Backend |
|---|---|
| Page initialization | `GET /health` + `GET /api/summary` + `GET /api/meta` |
| Queue filtering and paging | `GET /api/cases?limit=15&offset=0&min_priority=0&detector=...&search=...` |
| Case details, graph, timeline | `GET /api/cases/{case_id}` |
| Stress Test | `POST /api/cases/{case_id}/stress-test` body `{"excluded_transaction_id":"..."}` |
| Dataset status | `GET /api/datasets/current` (`pending_upload` indicates staged) |
| Stage archive | `POST /api/datasets/load` multipart field `file` |
| Analyze staged archive | `POST /api/analyze` body `{"include_cycles":true}` |

You do **not** need a special frontend backend route or another backend wrapper. `js/api.js` centralizes all requests.

## Critical schema details

- Queue response is `{ items: [...], total, limit, offset, run_id }`, not an array.
- Case details include `account_ids`, `transactions`, `alerts`, `risk_factors`, `graph` and more.
- Graph has `nodes:[{id,label}]` and `edges:[{id,transaction_id,source,target,amount,currency,simulation_step}]`.
- `simulation_step` is an integer; do not render an invented time or date.
- `currency:'XXX'` means unspecified synthetic units.
- `score_is_probability:false`; score is a prioritization index.
- Stress Test returns `baseline_score`, `recomputed_score`, `score_difference`, `changed_factors`, `before_factors`, `after_factors`, `membership_recomputed:false`.
- Switching active archive can change run ID and case IDs. Frontend reloads after successful analysis; it does not keep hardcoded case IDs in production logic.

## Known limitations, with accurate phrasing

- No authentication, persistent database, multiworker server, or bank-grade operational guarantees.
- Backend archive description currently calls any supported uploaded dataset "IBM AMLSim synthetic 20K scenario"; it should be derived from upload metadata if additional scenario types are shown.
- Backend source account fraud labels are never shown in dashboard. This prevents label leakage.
- Pattern detector thresholds and factor weights are heuristic prototype choices, not calibrated risk probability.
- In-memory server analysis resets on backend restart.

## One-machine end-to-end acceptance

1. Start backend, verify `http://127.0.0.1:8000/health` ready true.
2. Start frontend, verify `http://127.0.0.1:5173/` shows online.
3. Top case has 7 alerts, 25 transfers; graph has 25 edges.
4. Clicking one graph edge selects the matching timeline transfer.
5. Four factors render with actual contributions, including missing-history state where appropriate.
6. Run `IBM20K-ROW-0005975` Stress Test on `CASE-1086856BCDCD`; 100.00 to 95.26.
7. Click Reset; stored case remains unchanged.
8. Search and detector filter return server-based results.
9. Optional IBM archive stage and analyze: ensure new run ID and refreshed case state.
