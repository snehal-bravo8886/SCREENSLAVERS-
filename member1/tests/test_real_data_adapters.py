"""Other IBM-style layouts, archive detection, and genuinely independent edge tests."""
from datetime import datetime, timezone
from pathlib import Path
import io
import tarfile
import pandas as pd
import pytest
from run_module_a import load_source
from src.pipeline import FinancialCrimeDetectionPipeline
from src.adapter import TransactionIngestionEngine

DATE = datetime(2017, 1, 1, tzinfo=timezone.utc)


def test_ibm_transaction_export_field_names_and_private_labels():
    df = pd.DataFrame([
        {"tran_id": "0007", "orig_acct": "0001", "bene_acct": "0002", "base_amt": "240.01",
         "tran_timestamp": "4", "is_sar": "1", "alert_id": "SRC-SECRET"},
        {"tran_id": "0008", "orig_acct": "0002", "bene_acct": "0003", "base_amt": "230.00",
         "tran_timestamp": "5", "is_sar": "1", "alert_id": "SRC-SECRET"},
    ])
    p = FinancialCrimeDetectionPipeline(base_datetime=DATE, step_minutes=1440,
                                        rapid_pass_window_mins=1500)
    result = p.run_from_dataframe(df)
    assert result.transactions[0].transaction_id == "0007"
    assert result.transactions[0].source_account == "0001"
    assert result.transactions[0].currency == "XXX"
    assert result.evaluation_labels["0007"].is_sar == 1
    assert result.evaluation_labels["0007"].source_alert_id == "SRC-SECRET"
    assert "SRC-SECRET" not in str(result.handoff_to_member_b())
    assert [a.detector for a in result.alerts] == ["rapid_pass_through"]


def test_archive_reader_selects_transactions_not_accounts_or_alerts(tmp_path):
    path = tmp_path / "amlsim.tgz"
    inputs = {
        "examples/nodes.csv": "account_id,kind\nX,SAR\n",
        "examples/alert_transactions.csv": "orig_acct,bene_acct,base_amt,tran_timestamp\nM,N,100,1\n",
        "examples/transactions.csv": "source,target,amount,step\nA,B,100.00,1\nB,C,90.00,2\n",
        "examples/metadata.txt": "This is an integration test fixture, NOT a real IBM archive.\n",
    }
    with tarfile.open(path, "w:gz") as tf:
        for name, text in inputs.items():
            raw = text.encode()
            ti = tarfile.TarInfo(name)
            ti.size = len(raw)
            tf.addfile(ti, io.BytesIO(raw))
    table, info = load_source(path)
    assert info["archive_member"] == "examples/transactions.csv"
    p = FinancialCrimeDetectionPipeline(base_datetime=DATE, step_minutes=1440,
                                        allow_derived_ids=True, rapid_pass_window_mins=1500)
    result = p.run_from_dataframe(table)
    assert len(result.transactions) == 2
    assert result.audit["source_transaction_ids_derived"] == 2
    assert all(t.transaction_id.startswith("DERIVED-ROW-") for t in result.transactions)
    assert len(result.alerts) == 1


def test_no_automatic_original_ids_for_missing_transaction_ids():
    table = pd.DataFrame({"source": ["A"], "target": ["B"], "amount": [12], "step": [1]})
    with pytest.raises(ValueError, match="transaction_id"):
        TransactionIngestionEngine(base_datetime=DATE, step_minutes=1440).load_from_dataframe(table)


def test_refuse_aggregated_counts_and_time_intervals():
    base = {"TXN_ID": "99", "ACCOUNT_ID": "A", "COUNTER_PARTY_ACCOUNT_NUM": "B",
            "TXN_AMOUNT_ORIG": "15.00", "start": "1", "end": "1", "tx_count": "1"}
    adapter = TransactionIngestionEngine(base_datetime=DATE, step_minutes=1440)
    cleaned, _ = adapter.load_from_dataframe(pd.DataFrame([base, {**base, "TXN_ID": "100", "tx_count": "5"},
                                                            {**base, "TXN_ID": "101", "end": "2"}]))
    assert len(cleaned) == 1
    assert len(adapter.skipped_records) == 2


def test_account_preserves_leading_zeroes_and_money_precision():
    row = {"tran_id": "00009", "orig_acct": "00001", "bene_acct": "00002",
           "base_amt": "10.235", "tran_timestamp": "2026-10-18T12:00:00Z"}
    transactions, _ = TransactionIngestionEngine().load_from_dataframe(pd.DataFrame([row]))
    assert transactions[0].source_account == "00001"
    assert transactions[0].transaction_id == "00009"
    assert transactions[0].amount == 10.24


def test_invalid_label_is_not_claimed_normal():
    row = {"tran_id": "7", "orig_acct": "A", "bene_acct": "B", "base_amt": "10",
           "tran_timestamp": "2026-10-18T12:00:00Z", "is_sar": "UNCONFIRMED"}
    transactions, labels = TransactionIngestionEngine().load_from_dataframe(pd.DataFrame([row]))
    assert len(transactions) == 1
    assert len(labels) == 0


def test_fan_detector_finds_two_nonoverlapping_bursts():
    rows = []
    for j, hour in enumerate((0, 24)):
        for i in range(3):
            rows.append({"transaction_id": f"T-{j}-{i}", "source_account": f"S-{j}-{i}",
                         "destination_account": "C", "amount": 100,
                         "timestamp": f"2026-10-{18+j}T10:{i*10:02d}:00Z"})
    result = FinancialCrimeDetectionPipeline().run_from_dataframe(pd.DataFrame(rows))
    in_alerts = [a for a in result.alerts if a.detector == "fan_in"]
    assert len(in_alerts) == 2
    assert len(set(x for a in in_alerts for x in a.transaction_ids)) == 6


def test_cross_currency_input_rejected_before_scoring():
    df = pd.DataFrame([
        {"transaction_id":"1","source_account":"A","destination_account":"B","amount":100,"currency":"USD","timestamp":"2026-10-18T12:00:00Z"},
        {"transaction_id":"2","source_account":"B","destination_account":"C","amount":90,"currency":"EUR","timestamp":"2026-10-18T12:05:00Z"},
    ])
    with pytest.raises(ValueError, match="Mixed currencies"):
        FinancialCrimeDetectionPipeline().run_from_dataframe(df)
