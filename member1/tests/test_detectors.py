"""
Unit Tests for Rule-Based Explainable Detectors
Adheres to Section 3.3, 10 & 14.
"""

import pytest
import os
from src.pipeline import FinancialCrimeDetectionPipeline

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "controlled_test_fixture.csv")


@pytest.fixture
def pipeline_result():
    pipeline = FinancialCrimeDetectionPipeline(enable_cycle_detector=True)
    return pipeline.run_from_csv(FIXTURE_PATH)


def test_rapid_pass_through_detection(pipeline_result):
    pass_alerts = [a for a in pipeline_result.alerts if a.detector == "rapid_pass_through"]
    assert len(pass_alerts) >= 1

    # Verify target mule account A-212 was flagged
    mule_alert = next((a for a in pass_alerts if "A-212" in a.account_ids), None)
    assert mule_alert is not None
    assert mule_alert.features["intermediary_account"] == "A-212"
    assert "T-1001" in mule_alert.transaction_ids
    assert "T-1002" in mule_alert.transaction_ids
    assert mule_alert.features["elapsed_minutes"] == 5.0
    assert 0.90 <= mule_alert.features["transfer_ratio"] <= 1.0


def test_fan_in_detection(pipeline_result):
    fanin_alerts = [a for a in pipeline_result.alerts if a.detector == "fan_in"]
    assert len(fanin_alerts) >= 1

    # Verify AGG-99 aggregator flagged
    agg_alert = next((a for a in fanin_alerts if "AGG-99" in a.account_ids), None)
    assert agg_alert is not None
    assert agg_alert.features["target_account"] == "AGG-99"
    assert agg_alert.features["distinct_counterparties"] >= 3
    assert set(["T-2001", "T-2002", "T-2003"]).issubset(set(agg_alert.transaction_ids))


def test_time_respecting_cycle_detection(pipeline_result):
    cycle_alerts = [a for a in pipeline_result.alerts if a.detector == "temporal_cycle"]
    assert len(cycle_alerts) >= 1

    cyc_alert = cycle_alerts[0]
    assert set(cyc_alert.account_ids) == {"CYC-A", "CYC-B", "CYC-C"}
    assert set(cyc_alert.transaction_ids) == {"T-3001", "T-3002", "T-3003"}


def test_all_evidence_ids_exist_in_dataset(pipeline_result):
    """
    CRITICAL ACCEPTANCE CHECK (Section 10):
    Every single transaction ID in every emitted alert MUST exist in the loaded dataset.
    No hallucinated or invented IDs!
    """
    valid_tx_ids = set(t.transaction_id for t in pipeline_result.transactions)
    for alert in pipeline_result.alerts:
        for tx_id in alert.transaction_ids:
            assert tx_id in valid_tx_ids, f"Alert {alert.alert_id} referenced non-existent tx {tx_id}!"


def test_pipeline_determinism():
    """Running the pipeline twice on the same input must give identical output."""
    pipeline = FinancialCrimeDetectionPipeline()
    res1 = pipeline.run_from_csv(FIXTURE_PATH)
    res2 = pipeline.run_from_csv(FIXTURE_PATH)

    assert len(res1.alerts) == len(res2.alerts)
    for a1, a2 in zip(res1.alerts, res2.alerts):
        assert a1.alert_id == a2.alert_id
        assert a1.detector == a2.detector
        assert a1.transaction_ids == a2.transaction_ids
        assert a1.features == a2.features
