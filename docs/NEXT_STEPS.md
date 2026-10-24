# Integration roadmap

## Current state
- Static UI shell and account-centered transaction browsing available locally.
- Dataset profile and selected synthetic source rows included.
- Backend responds only to `/health`.
- Full original dataset archive is needed to run the offline inspection script.

## Next checkpoint
1. Define data contracts for Transaction, Alert, and Case.
2. Parse transactions with stable row IDs and graph relationships.
3. Implement and test one evidence-linked detector against known synthetic examples.
4. Add a case list API and bind the frontend to it.

## Later
- Additional pattern detectors (fan-out, onward flow, cycles, mule-like flow).
- Explainable priority scoring and calibrated thresholds.
- Interactive network, timeline, and Evidence Stress Test.
- Privacy, security, and real-data evaluation before any real financial use.

**No live bank access or validated precision/recall is claimed.**
