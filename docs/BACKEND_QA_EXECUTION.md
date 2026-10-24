# Member 4 — QA, evaluation and demonstration checklist

## Implemented and executed

- Baseline handoff file is checked against SHA-256 `93f57326a378d71813a6bf233a5cc8d1a8b9a388da7507b5798c53547ca4231d` before startup.
- Member B original source code is used directly; case IDs, grouping, contributions and Stress Test are not reimplemented.
- Genuine Module A source code is called for user-requested reanalysis of compatible IBM archive.
- No colleague's original CSV or deprecated backend code is used.
- Source-native `simulation_step`, null timestamps and unspecified `XXX` currency are preserved.
- All 120,558 transactions and 2,912 alerts are retained with exact source-derived transaction identifiers.
- Live API checks include case pagination/filtering, detailed evidence lookup, graph and timeline, before/after Stress Test and no mutation of original case.
- Invalid case IDs, bad request fields, wrong archive extensions, corrupt archives, missing members, bad source headers and oversize uploads return meaningful errors.
- Initial seed cases and a staged archive reanalysis are tested on real IBM data, not merely mocked fixtures.

## Full automated command

```bash
python -m pytest tests -q
python -m scripts.smoke_test
```

## Manual frontend and integration sign-off (still requires Member 3)

1. Start FastAPI. Open `http://127.0.0.1:8000/docs` and show actual summary.
2. Start React on port 5173. Its network requests should reach this service without CORS errors.
3. Click the top case: case detail should report 7 alerts and 25 original evidence transactions.
4. Click one graph edge: display its transaction_id, endpoints, amount and simulation step.
5. Open timeline: ensure steps are sorted and no false clock time is shown.
6. Exclude `IBM20K-ROW-0005975` in `CASE-1086856BCDCD`: expected 100.00 → 95.26 and reason/factor changes.
7. Click Reset or reopen case: original score must still be 100.00.
8. Upload bundled `.tgz` if showing this feature. Only after `POST /api/analyze` succeeds should the new run ID appear.
9. Try an invalid file. App must keep the previous valid case queue.
10. Rehearse a demo without internet; ensure host/port and allowed origins are correct.

## Evaluation limitations to state explicitly

- The dataset's original fraud labels are at **account level**, not transaction/case level; they are not in the public API.
- Do not claim precision, recall, false-positive rate, guilt predictions or AML probability.
- Member B grouping caps and scoring weights are defined prototype heuristics, not statistically calibrated risk estimates.
- The Evidence Stress Test holds case membership fixed; it does not re-detect or regroup the full graph.
- Original archive metadata fraud-node count disagrees with actual node labels by one; this discrepancy is documented in Module A provenance, but neither count is exposed to the detector.
- Equal-review-cost baseline evaluation and independent case-level ground truth **remain research work**, not completed backend features.

## Runtime/deployment limitations

- Prototype designed for local demo with **one Uvicorn worker**; cases are in memory and reset to default on server restart.
- API has no login, permanent datastore, identity management, authentication, encryption at rest or production monitoring.
- Do not deploy directly to the public internet in this form.
- Upload caps are 10 MiB compressed / 15 MiB expanded; unsupported or ambiguous `.tgz` archive entries are rejected.
