"""Module A regression tests discovered during integration audit."""
from datetime import datetime, timezone

import pandas as pd
import pytest

from src.adapter import TransactionIngestionEngine
from src.graph_engine import TemporalGraphEngine
from src.pipeline import FinancialCrimeDetectionPipeline
from src.schemas import CanonicalTransaction


BASE = {"source_account": "A", "destination_account": "B", "amount": 100.0,
        "currency": "USD", "timestamp": "2026-10-18T10:00:00Z"}


def rows(*values):
    return pd.DataFrame([dict(BASE, **r) for r in values])


def test_duplicate_ids_do_not_corrupt_graph():
    adapter = TransactionIngestionEngine()
    cleaned, _ = adapter.load_from_dataframe(rows(
        {"transaction_id": "T1"},
        {"transaction_id": "T1", "destination_account": "C"},
        {"transaction_id": "T2"},
    ))
    assert [t.transaction_id for t in cleaned] == ["T1", "T2"]
    assert "Duplicate transaction ID" in adapter.skipped_records[0]["reason"]
    graph = TemporalGraphEngine()
    G = graph.build_graph(cleaned)
    assert G.number_of_edges() == len(cleaned) == len(graph.tx_lookup)


def test_graph_rejects_direct_duplicate_ids():
    tx = CanonicalTransaction(transaction_id="same", source_account="A", destination_account="B",
                              amount=12, currency="USD", timestamp="2026-10-18T10:00:00Z")
    with pytest.raises(ValueError, match="Duplicate transaction ID"):
        TemporalGraphEngine().build_graph([tx, tx])


@pytest.mark.parametrize("bad_field,bad_value", [
    ("source_account", " "),
    ("destination_account", ""),
    ("transaction_id", " "),
    ("amount", float("inf")),
    ("amount", float("-inf")),
    ("amount", 0.001),
    ("timestamp", "NaT"),
    ("timestamp", "not-a-date"),
])
def test_malformed_row_skipped_without_crash(bad_field, bad_value):
    adapter = TransactionIngestionEngine()
    clean, _ = adapter.load_from_dataframe(rows(
        {"transaction_id": "GOOD"},
        {"transaction_id": "BAD", bad_field: bad_value},
    ))
    assert len(clean) == 1
    assert clean[0].transaction_id == "GOOD"
    assert len(adapter.skipped_records) == 1
    assert "raw" not in adapter.skipped_records[0]


def test_numeric_time_steps_need_explicit_scale_and_origin():
    original = rows({"transaction_id": "T1", "timestamp": 5})
    without_cfg = TransactionIngestionEngine()
    with pytest.raises(ValueError, match="specify --base-date"):
        without_cfg.load_from_dataframe(original)
    configured = TransactionIngestionEngine(
        base_datetime=datetime(2026, 10, 1, tzinfo=timezone.utc), step_minutes=60
    )
    clean, _ = configured.load_from_dataframe(original)
    assert len(clean) == 1
    assert clean[0].timestamp == "2026-10-01T05:00:00+00:00"


def test_no_mix_of_currency_without_conversion():
    with pytest.raises(ValueError, match="Mixed currencies"):
        TransactionIngestionEngine().load_from_dataframe(rows(
            {"transaction_id": "T1", "currency": "USD"},
            {"transaction_id": "T2", "currency": "EUR"},
        ))


def test_bad_raw_row_never_exposes_label_metadata():
    df = rows({"transaction_id": "GOOD"}, {"transaction_id": "BAD", "amount": -1})
    df["is_sar"] = [0, 1]
    df["alert_id"] = ["", "SECRET_LABEL"]
    adapter = TransactionIngestionEngine()
    adapter.load_from_dataframe(df)
    assert "SECRET_LABEL" not in str(adapter.skipped_records)
    assert "is_sar" not in str(adapter.skipped_records)


def test_rapid_matching_does_not_use_same_inflow_twice():
    df = rows(
        {"transaction_id": "IN", "source_account": "A", "destination_account": "B", "amount": 100},
        {"transaction_id": "OUT1", "source_account": "B", "destination_account": "C", "amount": 94,
         "timestamp": "2026-10-18T10:05:00Z"},
        {"transaction_id": "OUT2", "source_account": "B", "destination_account": "D", "amount": 95,
         "timestamp": "2026-10-18T10:09:00Z"},
    )
    result = FinancialCrimeDetectionPipeline(enable_cycle_detector=False).run_from_dataframe(df)
    rapid = [a for a in result.alerts if a.detector == "rapid_pass_through"]
    assert len(rapid) == 1
    assert rapid[0].transaction_ids == ["IN", "OUT1"]


def test_deterministic_fanin_does_not_use_ibm_labels():
    df = rows(
        {"transaction_id": "X1", "source_account": "A", "destination_account": "Z"},
        {"transaction_id": "X2", "source_account": "B", "destination_account": "Z",
         "timestamp": "2026-10-18T10:05:00Z"},
        {"transaction_id": "X3", "source_account": "C", "destination_account": "Z",
         "timestamp": "2026-10-18T10:10:00Z"},
    )
    df["is_sar"] = [0,0,0]
    df["alert_id"] = ["","",""]
    a = FinancialCrimeDetectionPipeline(enable_cycle_detector=False).run_from_dataframe(df)
    df["is_sar"] = [1,1,1]
    df["alert_id"] = ["SAR-1","SAR-1","SAR-1"]
    b = FinancialCrimeDetectionPipeline(enable_cycle_detector=False).run_from_dataframe(df)
    assert [al.model_dump() for al in a.alerts] == [al.model_dump() for al in b.alerts]


def test_pipeline_raises_for_empty_valid_input():
    with pytest.raises(ValueError, match="No usable transactions"):
        FinancialCrimeDetectionPipeline().run_from_dataframe(
            rows({"transaction_id": "T1", "amount": -1})
        )
