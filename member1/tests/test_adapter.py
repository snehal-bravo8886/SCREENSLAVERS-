"""
Unit Tests for Transaction Ingestion & Validation Adapter
Adheres to Section 3.1 & Section 10 Definition of Done.
"""

import pytest
import os
from src.adapter import TransactionIngestionEngine
from src.schemas import CanonicalTransaction

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "controlled_test_fixture.csv")


def test_ingestion_valid_transactions():
    engine = TransactionIngestionEngine()
    transactions, eval_labels = engine.load_from_csv(FIXTURE_PATH)

    # 17 rows total in CSV: 15 valid, 2 invalid (T-BAD-1 negative amount, T-BAD-2 missing source)
    assert len(transactions) == 15
    assert len(engine.skipped_records) == 2

    # Verify transaction IDs are preserved
    tx_ids = [t.transaction_id for t in transactions]
    assert "T-1001" in tx_ids
    assert "T-1002" in tx_ids
    assert "T-BAD-1" not in tx_ids
    assert "T-BAD-2" not in tx_ids


def test_account_ids_are_strings():
    engine = TransactionIngestionEngine()
    transactions, _ = engine.load_from_csv(FIXTURE_PATH)
    for t in transactions:
        assert isinstance(t.source_account, str)
        assert isinstance(t.destination_account, str)
        assert isinstance(t.amount, float)
        assert t.amount > 0


def test_skipped_records_logged():
    engine = TransactionIngestionEngine()
    engine.load_from_csv(FIXTURE_PATH)
    reasons = [r["reason"] for r in engine.skipped_records]
    assert any("Amount must be finite" in r for r in reasons)
    assert any("Blank or invalid identifier" in r for r in reasons)


def test_private_ground_truth_isolation():
    engine = TransactionIngestionEngine()
    transactions, eval_labels = engine.load_from_csv(FIXTURE_PATH)

    # Label dictionary contains known ground truths
    assert "T-1001" in eval_labels
    assert eval_labels["T-1001"].is_sar == 1
    assert eval_labels["T-1001"].source_alert_id == "SIM_ALT_01"

    # CANONICAL TRANSACTIONS MUST NOT HAVE ANY LABEL ATTRIBUTES
    for t in transactions:
        assert not hasattr(t, "is_sar")
        assert not hasattr(t, "is_laundering")
        assert not hasattr(t, "alert_id")
