# Architecture and data flow

```text
IBM AMLSim synthetic archive
   | Member 1: validate → canonical transfers → directed graph → 4 detectors
   v
Evidence-linked alert handoff (data/member_a_IBM_20K_handoff.json)
   | Member 2: group alerts → F/V/N/B review-priority score → evidence sensitivity
   v
CaseEngine (member_b/engine.py)
   | Member 4: FastAPI JSON endpoints (backend/main.py, backend/service.py)
   v
Member 3: browser frontend (frontend/index.html, frontend/js/*.js)
```

## Source of truth

The backend loads the verified JSON handoff on startup. The same genuine IBM archive is included for upload/re-analysis. `member1/` contains the full standalone detector implementation; the backend uses the final native importer under root `src/` and Member 2's engine under root `member_b/`. **Do not mix the old teammate-generated CSV into this project.**

## Responsibilities

- **Member 1:** archive provenance, data validation, graph construction, detection and evidence IDs. Run `cd member1 && python -m pytest tests -q`.
- **Member 2:** case construction, transparent F/V/N/B scoring, and fixed-membership Stress Test. Source: `member_b/engine.py`; tests: `tests/test_member_b_native.py`.
- **Member 3:** UI state, case queue, network graph, timeline, selected transaction, score factors and Stress Test. Source: `frontend/`.
- **Member 4:** API contracts, upload validation, orchestration, error handling, tests and frontend integration. Source: `backend/` and `tests/`.

## Technical caveats

- **Native simulation steps:** no invented wall-clock times or minutes.
- **Synthetic monetary units:** not real USD/EUR amounts.
- **Heuristic review priority:** not probability or a validated fraud classification.
- **Stress Test:** removes one evidence transfer from factor calculations for an existing case; original case and grouping remain unchanged.
- **Local demo:** no authentication or persistence across restart. Avoid public internet exposure.

## UI technology

The delivered Member 3 implementation is static ES-module JavaScript, HTML and CSS. It has no React or Cytoscape.js dependency; do not describe it as a React implementation.
