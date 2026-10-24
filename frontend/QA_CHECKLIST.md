# Member 3 — Manual QA & Demo Checklist

Use this checklist on the actual Mac/browser. Automated CI cannot replace manual end-to-end acceptance.

- [ ] Member 4 FastAPI running on `127.0.0.1:8000`; `/health` returns `ready:true`.
- [ ] Member 3 static frontend running on `127.0.0.1:5173`; top bar shows **Backend online**.
- [ ] No Safari/Chrome developer console errors and no blocked cross-origin fetch requests.
- [ ] Summary shows 120,558 synthetic transfers, 2,912 alerts, 2,573 cases.
- [ ] First selected case is the current highest-priority case; score remains a 0–100 heuristic.
- [ ] Queue pagination, search by case ID, detector filter, and minimum priority work.
- [ ] Case graph nodes and transaction edges match the selected case's source evidence.
- [ ] Click a graph node: corresponding transfer timeline filters to that account.
- [ ] Click a graph edge or timeline transfer: the correct original transaction ID/amount/step is shown.
- [ ] Graph zoom in/out/reset and pan work, without page scrolling the graph out of view.
- [ ] Risk factor tab shows M/A/C normalized values and weighted points that sum to the case score.
- [ ] Stress Test reports the same baseline as the case header and recalculates alert status, activity, and support without changing case membership or the stored case.
- [ ] Reset returns to original baseline case priority; no original evidence is mutated.
- [ ] Invalid search returns an honest empty state; offline backend shows error and Retry.
- [ ] Dataset dialog shows backend run and pending-upload state.
- [ ] If using dataset upload in demo: load the genuine IBM `.tgz` archive, wait for staging confirmation, click Analyze, and verify new run ID/updated case queue. Do not demo unsupported CSV upload.
- [ ] Safari and Chrome desktop layout display all three panels.
- [ ] Mobile layout is readable with vertically stacked panels.
- [ ] No `₹`, `$`, timestamps, percentage-of-crime or accuracy/recall claims are present.
- [ ] Product naming consistent with submitted team name and organizer rules checked.

## Quick judge walkthrough (about 2 minutes)

Open dashboard → present the true IBM-derived summary → open top case → click graph node → inspect corresponding transfers → Risk factor tab → run an individual or pattern Stress Test → show the changed factor and priority delta → Reset → state limitations truthfully.

## Troubleshooting

- **Backend offline**: ensure Member 4 server is running on port 8000 and not 8001; click Refresh.
- **CORS error**: open UI at `http://127.0.0.1:5173` or `http://localhost:5173` (both permitted by backend), not via local `file://`.
- **Empty queue**: clear filters; case ID search is substring-only.
- **Incorrect scores**: confirm correct active run ID and top case; do not reuse the baseline case ID after a different upload.
- **Upload failure**: only genuine compatible IBM `.tgz`/`.tar.gz` is accepted, max 10 MiB compressed and 15 MiB expanded.
- **Changing backend computer**: `127.0.0.1` always means this computer; coordinate LAN binding and CORS with Member 4.
