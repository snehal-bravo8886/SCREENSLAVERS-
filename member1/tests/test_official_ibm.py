"""Tests based on IBM/AMLSim's public 45-transfer, pre-generated sample.

Source URL: https://raw.githubusercontent.com/IBM/AMLSim/master/sample/outputs/tx.csv
This old graph CSV has no SAR labels; no accuracy metric is claimed.
"""
from datetime import datetime, timezone
from pathlib import Path
from src.pipeline import FinancialCrimeDetectionPipeline

DATA = Path(__file__).resolve().parents[1] / "data/ibm_amlsim_official_sample_tx.csv"


def test_original_ibm_graph_example_is_parsed_as_45_individual_transfers():
    pipeline = FinancialCrimeDetectionPipeline(base_datetime=datetime(2017, 1, 1, tzinfo=timezone.utc),
                                                step_minutes=1440)
    result = pipeline.run_from_csv(str(DATA))
    assert len(result.transactions) == 45
    assert len(result.skipped_records) == 0
    assert result.audit["distinct_accounts"] == 27
    assert result.audit["source_transaction_ids_derived"] == 0
    assert result.transactions[0].transaction_id == "2"
    assert result.transactions[0].source_account == "15"
    assert result.transactions[0].destination_account == "25"
    assert result.transactions[0].currency == "XXX"  # IBM example does not specify a currency
    assert len(result.evaluation_labels) == 0
    assert len(result.graph_engine.tx_lookup) == 45
    assert result.graph_engine.graph.number_of_edges() == 45


def test_original_ibm_graph_example_refuses_unknown_step_length():
    import pytest
    with pytest.raises(ValueError, match="Integer AMLSim timestamps detected"):
        FinancialCrimeDetectionPipeline().run_from_csv(str(DATA))


def test_public_handoff_has_no_source_label_fields():
    import json
    pipeline = FinancialCrimeDetectionPipeline(base_datetime=datetime(2017, 1, 1, tzinfo=timezone.utc),
                                               step_minutes=1440)
    handoff = pipeline.run_from_csv(str(DATA)).handoff_to_member_b()
    blob = json.dumps(handoff)
    for forbidden in ('"is_sar"', '"source_alert_id"', '"model_type"'):
        assert forbidden not in blob
