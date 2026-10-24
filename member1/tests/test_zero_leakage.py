"""
Zero-Leakage Audit Test
Verifies that ground truth labels (is_sar, is_laundering, alert_id) never leak into
canonical transactions or detection alerts.
Adheres to Section 4 & Section 12 Risk Register.
"""

import pytest
import os
from src.pipeline import FinancialCrimeDetectionPipeline

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "controlled_test_fixture.csv")
FORBIDDEN_KEYS = {"is_sar", "is_laundering", "islaundering", "label", "target", "source_alert_id"}


def test_zero_leakage_in_transactions():
    pipeline = FinancialCrimeDetectionPipeline()
    result = pipeline.run_from_csv(FIXTURE_PATH)

    for tx in result.transactions:
        tx_dict = tx.model_dump()
        for forbidden in FORBIDDEN_KEYS:
            assert forbidden not in tx_dict, f"Leakage detected in CanonicalTransaction: {forbidden} present!"


def test_zero_leakage_in_detection_alerts():
    pipeline = FinancialCrimeDetectionPipeline()
    result = pipeline.run_from_csv(FIXTURE_PATH)

    for alert in result.alerts:
        alert_dict = alert.model_dump()
        for forbidden in FORBIDDEN_KEYS:
            assert forbidden not in alert_dict, f"Leakage detected in DetectionAlert: {forbidden} present!"
        # Check inside features dict as well
        for forbidden in FORBIDDEN_KEYS:
            assert forbidden not in alert.features, f"Leakage detected in alert features: {forbidden} present!"


def test_evaluation_labels_stored_separately():
    pipeline = FinancialCrimeDetectionPipeline()
    result = pipeline.run_from_csv(FIXTURE_PATH)

    # Evaluation labels must exist separately and map by transaction_id
    assert len(result.evaluation_labels) > 0
    for tx_id, label in result.evaluation_labels.items():
        assert hasattr(label, "is_sar")
        assert label.transaction_id == tx_id
