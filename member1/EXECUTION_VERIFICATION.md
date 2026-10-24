# Verified run — Member A on uploaded IBM 20K archive

## Run commands

```bash
python -m pytest tests -q
python run_ibm_20k.py --cycles --report reports/IBM_20K_verified_run.json --handoff examples/member_b_IBM_20K_handoff.json
python verify_handoff.py examples/member_b_IBM_20K_handoff.json
python create_member_b_fixture.py
python verify_handoff.py examples/member_b_small_real_data_fixture.json --report reports/small_fixture_validation.json
```

## Results observed in this environment

| Check | Result |
|---|---|
| Pytest suite | **49 passed** |
| IBM archive source transactions | **120,558** |
| Graph nodes occurring in transfers | **19,980** |
| Graph directed multi-edges | **120,558** (no transfer row dropped) |
| Archive account rows | **20,000** |
| Original transaction IDs present | **0** (all 120,558 row IDs derived) |
| Rejected rows | **0** |
| Fan-in candidate alerts | **680** |
| Fan-out candidate alerts | **100** |
| Rapid-onward candidate alerts | **2,110** |
| Strict time-respecting 3-account cycle candidates | **22** |
| Total unique alerts | **2,912** |
| Every referenced evidence ID exists and belongs to same accounts / step window | **Verified by exported-JSON checker** |
| Private `isFraud`/`fraudStep` information in Member B exported JSON | **Absent** |
| Full analysis runtime in environment | **approximately 1.7–2.0 seconds**, excl. writing 28 MB JSON |
| Smaller sample for Member B | **237 actual IBM transfer rows, 4 overlapping alerts** |

## Important evaluation result and limitations

The account-level `nodes.csv` includes 1,804 entries labeled `isFraud=1`. Of these, **904** accounts appear in at least one candidate alert's listed accounts when all four detectors are on. This is merely **exploratory account overlap (~50.1%)**, NOT case recall, actual money-laundering detection sensitivity, or independent accuracy. **6,501** accounts with `isFraud=0` also appear in alerts; these are not necessarily 6,501 false alerts, because account labels and event labels differ. No transaction-level ground-truth flags or precise case associations exist in this particular archive.

We detect 22 qualifying **strictly step-ordered three-edge** cycles, not 200. IBM's metadata describes 200 injected cycle patterns, but the optional detector has a narrow rule and no per-cycle truth mapping; do not equate this count to either correct discoveries or false negatives without further labels.

This dataset contains no verified real time duration or currency; therefore labels such as “within 30 minutes”, “USD”, “80% chance of crime”, “200/200 detected cycles” would be inaccurate.

Member 2 receives transactions and evidence-linked alerts **only**. Member D must create FastAPI responses from safe fields, never serialize the private in-memory account-label dictionary.
