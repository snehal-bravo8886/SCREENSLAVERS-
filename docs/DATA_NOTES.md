# Dataset notes

- Source: IBM AMLSim synthetic sample, archive name `20K_fanin200cycle200.tgz`.
- Original archive contains `transactions.csv`, `nodes.csv`, metadata, and diagnostic figures.
- Transaction columns: `sourceNodeId`, `targetNodeId`, `value`, `time`.
- `time` is a discrete simulation step; the UI does not invent real-world timestamps.
- This GitHub checkpoint contains a profile and **selected original synthetic transaction rows**. The complete binary archive is included in the separately supplied midpoint ZIP, not this GitHub upload.
- To use `backend/inspect_dataset.py`, place the original archive in `data/`.
- Frontend records are layout fixtures, **not** detected fraud or labeled cases.
- No validated account risk classification is surfaced.
- Monetary amounts are synthetic units, not INR.
