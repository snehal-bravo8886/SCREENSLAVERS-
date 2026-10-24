# Screenslavers — Member 4 Complete FastAPI Backend

**Status:** Executed locally against the genuine IBM AMLSim archive's ChatGPT-generated Module A and Module B outputs. No original teammate-created CSV or older Phase 1 backend is used.

## What this service does

This is the HTTP integration layer for the **final ChatGPT-generated packages**, not an independent fake detector:

- **Member A, native IBM AMLSim analysis:** `src/ibm_scenario.py` is copied from the final verified Module A source. A source archive can be re-analyzed on demand, with four transparent detectors. No invented ISO timestamps.
- **Member B, real CaseEngine:** `member_b/engine.py` is copied from the final verified Module B source. Exposes groupings, priority factors, directed graph, evidence, timeline and fixed-membership Stress Test without rewriting business logic.
- **Verified default:** `data/member_a_IBM_20K_handoff.json` is the exact **unchanged, SHA-256 verified** Member A handoff consumed in Member B's tests. The app loads it at startup and computes the cases in memory. Judges can explore immediately, even without uploading anything.
- **Dataset upload/re-analysis:** accepts a valid IBM AMLSim `.tgz` / `.tar.gz` scenario file, validates safely (archive limits, schema checks), stages it, and only updates analysis after `POST /api/analyze`. A failed run does not replace the current valid cases.
- **Priority formula:** `context_evidence_v2_heuristic`: `P = 100 × (0.45M + 0.35A + 0.20C)`. `M` is maximum active-alert severity, `A` is the highest focus-account peer-relative and (when available) historical activity anomaly, and `C = clip((representative_groups − 1)/2, 0, 1)` after duplicate-family and high-Jaccard-overlap evidence discounts. Weighted factor points are rounded individually to two decimals and summed.
- **Accuracy status:** formula behavior is tested, but predictive accuracy is not measured because ground-truth account labels are withheld from the scoring path.

This backend is a **hackathon prototype**, not production bank software. No authentication, audit log database, process supervisor, encryption key management or network rate limiting. Run on `127.0.0.1`; do not expose it directly to the public internet.

## One-time setup — macOS

Unzip `screenslavers.zip` into Downloads.

```bash
cd ~/Downloads/screenslavers
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

**Check the entire backend first:**

```bash
python -m pytest tests -q
python -m scripts.smoke_test
```

**Start the API:**

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open these URLs in your browser:

- Interactive Swagger UI: **http://127.0.0.1:8000/docs**
- Health: **http://127.0.0.1:8000/health**
- Actual summary: **http://127.0.0.1:8000/api/summary**
- Actual case queue: **http://127.0.0.1:8000/api/cases?limit=10**
- Actual case detail: **http://127.0.0.1:8000/api/cases/CASE-1086856BCDCD**

Stop server with `Control+C`.

### Test real HTTP from a second Terminal tab

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/api/summary
curl -s 'http://127.0.0.1:8000/api/cases?limit=3'
curl -s -X POST 'http://127.0.0.1:8000/api/cases/CASE-1086856BCDCD/stress-test' \
  -H 'Content-Type: application/json' \
  -d '{"excluded_transaction_id":"IBM20K-ROW-0005975"}'
```

Stress Tests use fixed case membership and original time bounds, retain the peer reference distribution, recalculate alert assessments and focus-account activity after exclusions, and do not mutate the original saved case. The exact score change depends on the selected case and evidence.

## Verified output on the official IBM-derived input

| Metric | Real output |
|---|---:|
| Synthetic transactions | 120,558 |
| Account-transfer graph edges | 120,558 |
| Candidate detection alerts | 2,912 |
| Investigation cases | 2,573 |
| Multi-alert cases | 196 |
| Scoring version | `context_evidence_v2_heuristic` |
| Score range | 0–100 (review index, not fraud probability) |
| Predictive accuracy | Not measured; ground-truth labels are withheld from scoring |
| Units | Simulation steps; currency `XXX` (unspecified) |

## Endpoints

| Method | Path | Frontend purpose |
|---|---|---|
| `GET` | `/health` | Server and dataset ready |
| `GET` | `/api/meta` | UI-safe labels, units and constraints |
| `GET` | `/api/summary` | Counts, limitations, detector breakdown |
| `GET` | `/api/datasets/current` | Active run + staged upload status |
| `POST` | `/api/datasets/load` | Multipart archive `file` (stage valid IBM `.tgz`) |
| `POST` | `/api/analyze` | Optional JSON `{"include_cycles":true}`; recompute A+B |
| `GET` | `/api/cases` | Paginated priority-sorted case summaries |
| `GET` | `/api/cases/{case_id}` | Full case + actual alerts, transactions, graph, timeline |
| `GET` | `/api/cases/{case_id}/graph` | Cytoscape-compatible graph structure |
| `GET` | `/api/cases/{case_id}/timeline` | Step-ordered evidence transfers |
| `POST` | `/api/cases/{case_id}/stress-test` | Body `{ "excluded_transaction_id": "..." }` |
| `GET` | `/api/transactions/{transaction_id}` | Trace exact source transfer |
| `GET` | `/api/alerts/{alert_id}` | Alert + its evidence transactions |

**Case list filtering:** `limit=1..100` (default 20), `offset>=0`, `min_priority=0..100`, optional `detector=fan_in|fan_out|rapid_pass_through|temporal_cycle`, optional case-ID substring `search=...`. The response is an object `{ "items": [...], "total": ..., "limit": ..., "offset": ... }`, **not** an unwrapped array. This is the agreed frontend contract in `FRONTEND_API_CONTRACT.md`.

## Upload/re-analyze using the exact bundled IBM archive

Swagger: `POST /api/datasets/load` (file picker) then `POST /api/analyze` with `{"include_cycles":true}`.

Or Terminal:

```bash
curl -s -X POST 'http://127.0.0.1:8000/api/datasets/load' \
  -F 'file=@data/20K_fanin200cycle200.tgz'

curl -s -X POST 'http://127.0.0.1:8000/api/analyze' \
  -H 'Content-Type: application/json' \
  -d '{"include_cycles":true}'
```

The sample is **not** a generic arbitrary CSV upload: only the authentic IBM archive layout with `transactions.csv`, `nodes.csv` and `metadata.txt` is accepted. Other schemas require a different adapter and are intentionally rejected instead of guessed.

Upload size limit: **10 MiB compressed / 15 MiB expanded**, enough for this 1.3 MiB scenario. The archive is inspected, not extracted. Results are **in-memory per server process**, are reset to the bundled verified default on restart, and the demo supports one selected uploaded archive at a time. Use one Uvicorn worker, not multiple.

## Architecture

```text
                         FastAPI backend.main
                                  |
                   Member 4 Registry (backend.service)
                                  |
                    (atomic, in-memory snapshot)
                       /                     \\
    startup: verified A JSON                 optional reanalysis
             |                                      |
     Member B CaseEngine                 IBM archive -> Member A run_archive()
             |                                      |
             |                            new A handoff (label-free)
             |                                      |
             +--------------- Member B CaseEngine --+
                                  |
                     GET case queue, details, graph
                     POST Stress Test (no mutation)
                                  |
                            Member C React UI
```

No source account labels are passed into Member B or returned by API endpoints. The raw IBM archive remains bundled for reproducibility, but account-level labels are private to Module A's ingestion/evaluation scope.

## What Member 4 still owns during the event

1. Start the API on a local Mac and confirm `/docs` + case queue work.
2. Connect Member C's React app to `http://127.0.0.1:8000` (may need hostname alignment for CORS).
3. End-to-end click a real case, a graph edge, and run a real Stress Test from the browser.
4. Preserve the exact source-native timing and risk-index caveats in the UI.
5. Test upload on the actual demo laptop and keep the preloaded mode as a fallback.
6. Provide the judges a working local demo; check hackathon AI/prebuilt-code rules.

See `FRONTEND_API_CONTRACT.md`, `QA_EXECUTION.md`, and `docs/openapi.json`.
