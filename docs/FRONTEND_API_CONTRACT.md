# Frozen Member 4 → Member 3 REST API contract

**Base URL:** `http://127.0.0.1:8000` (or `http://localhost:8000`; pick one and use consistently). React default Vite CORS origins `http://localhost:5173`, `http://127.0.0.1:5173`. Set env `SCREENSLAVERS_CORS_ORIGINS` to comma-separated frontend origins if necessary; do not use `*` for a public deployment.

## 1. Startup state and data units

The backend eagerly loads the unchanged Member A real-IBM handoff and the actual Member B CaseEngine. It is ready when GET `/health` returns HTTP 200 and `ready: true`.

- **Use integer simulation steps**, not date strings. Show `Simulation step 25`.
- `timestamp`, `start_time`, `end_time` are null. Never generate dates from them.
- `currency:"XXX"` means **unspecified synthetic monetary unit**, not dollars or rupees.
- Score is a **0–100 investigator review-priority index**, not the probability of fraud.
- Stress Test is **fixed-membership evidence sensitivity**; source transactions and stored cases are not edited.

## 2. Case queue

**GET** `/api/cases?limit=20&offset=0&min_priority=0`

```json
{
  "run_id": "RUN-BASELINE-IBM20K",
  "items": [
    {
      "case_id": "CASE-1086856BCDCD",
      "priority_score": 100.0,
      "score_is_probability": false,
      "alert_count": 7,
      "evidence_count": 25,
      "start_step": 23,
      "end_step": 29,
      "time_unit": "simulation_step",
      "detector_types": ["fan_in", "fan_out", "rapid_pass_through", "temporal_cycle"],
      "summary": "Review candidate..."
    }
  ],
  "total": 2573,
  "limit": 20,
  "offset": 0,
  "time_unit": "simulation_step",
  "score_is_probability": false
}
```

**Note:** the illustrated case fields other than `case_id`, score and aggregate counts above must be read from the running API; do not hard-code illustrative detector types or time ranges.

### Supported filters

- `limit`: 1..100, `offset`: >=0
- `min_priority`: 0..100
- `detector`: `fan_in`, `fan_out`, `rapid_pass_through`, `temporal_cycle`
- `search`: substring match in case ID (not full graph search)

## 3. Detail, graph and timeline

- **GET** `/api/cases/{case_id}` → complete actual case, F/V/N/B factors, original alerts, evidence transactions, graph, timeline.
- **GET** `/api/cases/{case_id}/graph` → `{ "case_id", "nodes": [{"id", "label"}], "edges": [{"id", "transaction_id", "source", "target", "amount", "currency", "simulation_step"}], "time_unit":"simulation_step" }`.
- **GET** `/api/cases/{case_id}/timeline` → `{ "case_id", "time_unit":"simulation_step", "items": [CanonicalTransaction...] }`.

**Cytoscape conversion:** `elements = [{data:{id:n.id,label:n.label}}, ...graph.edges.map(e=>({data:e}))]`. One edge is one original transfer, not an aggregation.

## 4. Evidence sensitivity

**POST** `/api/cases/{case_id}/stress-test`

```json
{ "excluded_transaction_id": "IBM20K-ROW-0005975" }
```

Response contains `baseline_score`, `recomputed_score`, `score_difference`, `changed_factors`, `before_factors`, `after_factors`, `affected_alert_ids`, `membership_recomputed:false`, a `note`, and `time_unit`.

**Verified golden demo:** case `CASE-1086856BCDCD` excluding `IBM20K-ROW-0005975` changes the index **100.00 → 95.26**. Do not treat this as proof of AML detection accuracy or rerun case grouping.

## 5. Data upload (optional UI enhancement)

`POST /api/datasets/load`: multipart with form file field named `file`; only valid IBM `.tgz` or `.tar.gz` accepted. HTTP 202 means staged and validated, **not yet analyzed**.

`POST /api/analyze`: JSON `{"include_cycles":true}` (or empty body). On success returns same metrics shape as `/api/summary` and atomically switches active cases. If the source is rejected, existing cases remain usable. Never rely on fixed case IDs after a different archive has been analyzed.

## 6. Example JavaScript client

```js
const BASE = 'http://127.0.0.1:8000';

export async function apiGet(path) {
  const res = await fetch(BASE + path);
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
  return res.json();
}

export async function getCases(limit = 20, offset = 0) {
  return apiGet(`/api/cases?limit=${limit}&offset=${offset}`);
}

export async function getCase(caseId) {
  return apiGet(`/api/cases/${encodeURIComponent(caseId)}`);
}

export async function getGraph(caseId) {
  return apiGet(`/api/cases/${encodeURIComponent(caseId)}/graph`);
}

export async function stressTest(caseId, transactionId) {
  const res = await fetch(`${BASE}/api/cases/${encodeURIComponent(caseId)}/stress-test`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ excluded_transaction_id: transactionId }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
  return res.json();
}
```

## 7. Error handling

- 400: invalid archive content / unsupported IBM schema
- 404: unknown case/alert/transaction
- 409: another analysis is running
- 413: oversize upload
- 415: unsupported upload extension
- 422: invalid request parameter or Stress Test transaction outside case
- 503: startup dataset not initialized

Expect JSON errors `{ "error":"..." }` for application validation and standard FastAPI `{ "detail": [...] }` for request schema validation.
