# Dataset audit — actual uploaded IBM example archive

- Source file: `20K_fanin200cycle200.tgz`, user-uploaded, publicly associated with IBM/AMLSim `sample/20K_fanin200cycle200.tgz` (https://github.com/IBM/AMLSim/blob/master/sample/20K_fanin200cycle200.tgz).
- Uploaded-copy SHA-256: `f187bc5784223cdee137ac603164f7183fd58f114090f39e2a12543b6bf48319`.
- Inside-archive transaction CSV SHA-256: `5f650f8b4ce7cc328f1334c65e719496920c422191adbf9fe67f8ae7cfa99fd5`.
- Inside-archive node CSV SHA-256: `c43ac5dccc8bd18f2a67f13d7aaa2291664291410b911c00f8577a071d2a2113`.
- The stated SHA values record and uniquely identify the tested uploaded bytes. **We did not independently download the same official binary and compare digests**; the archive's name, internal organization, and metadata agree with the IBM repository.
- Archive contents: `transactions.csv` 120,558 rows with `sourceNodeId,targetNodeId,value,time`; `nodes.csv` 20,000 rows with `nodeid,isFraud,init_balance,fraudStep`; `metadata.txt` reporting 200 fan-in and 200 cycle patterns; image diagnostics not used as detector inputs.
- Metadata discrepancy: `metadata.txt` states **1,803 fraud nodes**, `nodes.csv` has **1,804** rows with `isFraud==1` (20,000 total: 18,196 labelled 0 and 1,804 labelled 1). The source file is kept unchanged, and this discrepancy is documented without attempting to correct it.
- Transaction rows contain **no ID column, currency column, case labels, alert/scenario IDs, or calendar timestamps**. There are 149 distinct integer time steps (1 through 149), 120,558 source transfer rows, 117,341 distinct source-target pairs and 1,684 completely duplicate 4-column rows. Completely duplicate records are still distinct source transfer *rows*: they are retained with separate derived IDs and separate MultiDiGraph edges.
- Source account table includes 20,000 distinct accounts, but only 19,980 appear in the 120,558 transfers. This is not an error: isolated accounts remain in `nodes.csv` and are excluded from the transaction graph when no edges are present.
- Amounts are positive finite numeric values, min 2.51, max 599.91, **synthetic currency unspecified** (`XXX`).
- Chronology: steps are source-native; no step-to-minutes/days conversion is applied and no real timestamp/date is generated. Strict forward transfer requires increasing steps. Two events on the same step cannot be ordered by this data.
- Source-node labels `isFraud`, `fraudStep`, and initial balances are **not** used by detection or public exports. Offline exploratory account-label coverage is allowed, but **transaction or scenario-level precision/recall cannot be established from these fields alone**.
- Developer-specified detection thresholds and window sizes are hypotheses, not IBM-certified AML rules.

Official project description: https://github.com/IBM/AMLSim .
