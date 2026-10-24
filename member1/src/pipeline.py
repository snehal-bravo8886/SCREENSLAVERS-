"""Member A's only public analytical entry point.

Use `run_from_csv()` or `run_from_dataframe()` and consume .transactions and .alerts.
Never feed `.evaluation_labels` to detectors, scoring, LLMs or public responses.
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging

from .schemas import CanonicalTransaction, DetectionAlert, EvaluationLabel
from .adapter import TransactionIngestionEngine
from .graph_engine import TemporalGraphEngine
from .detectors import RapidPassThroughDetector, FanInDetector, FanOutDetector, TemporalCycleDetector

logger = logging.getLogger(__name__)


class DetectionPipelineResult:
    def __init__(self, transactions: List[CanonicalTransaction], alerts: List[DetectionAlert],
                 graph_engine: TemporalGraphEngine, evaluation_labels: Dict[str, EvaluationLabel],
                 skipped_records: List[Dict[str, Any]], audit: Dict[str, Any]):
        self.transactions = transactions
        self.alerts = alerts
        self.graph_engine = graph_engine
        self.evaluation_labels = evaluation_labels  # STRICTLY offline evaluation-only
        self.skipped_records = skipped_records
        self.audit = audit

    def public_summary(self) -> Dict[str, Any]:
        """Safe for frontend; intentionally excludes source SAR/scenario labels."""
        breakdown = {}
        for alert in self.alerts:
            breakdown[alert.detector] = breakdown.get(alert.detector, 0) + 1
        return {"total_transactions": len(self.transactions),
                "rejected_rows": len(self.skipped_records),
                "total_alerts": len(self.alerts),
                "alert_breakdown": dict(sorted(breakdown.items())),
                "accounts": self.audit["distinct_accounts"],
                "currency": self.audit["currency"],
                "source_ids_derived": self.audit["source_transaction_ids_derived"]}

    def summary(self) -> Dict[str, Any]:
        """Backwards-compatible safe alias."""
        return self.public_summary()

    def handoff_to_member_b(self) -> Dict[str, Any]:
        """Only source transactions, our alerts and benign dataset configuration."""
        return {"transactions": [t.model_dump(mode="json") for t in self.transactions],
                "alerts": [a.model_dump(mode="json") for a in self.alerts],
                "dataset_summary": self.public_summary()}


class FinancialCrimeDetectionPipeline:
    def __init__(self, *, rapid_pass_window_mins: int = 60,
                 fan_counterparties: int = 3, fan_window_mins: int = 120,
                 enable_cycle_detector: bool = False,
                 base_datetime: Optional[datetime] = None,
                 step_minutes: Optional[float] = None,
                 default_currency: str = "XXX", allow_derived_ids: bool = False):
        self.ingestion = TransactionIngestionEngine(
            base_datetime=base_datetime, step_minutes=step_minutes,
            default_currency=default_currency, allow_derived_ids=allow_derived_ids)
        self.graph_engine = TemporalGraphEngine()
        self.detectors = [
            RapidPassThroughDetector(max_elapsed_minutes=rapid_pass_window_mins,
                                     min_ratio=0.80, max_ratio=1.00),
            FanInDetector(min_counterparties=fan_counterparties, window_minutes=fan_window_mins),
            FanOutDetector(min_counterparties=fan_counterparties, window_minutes=fan_window_mins),
        ]
        if enable_cycle_detector:
            self.detectors.append(TemporalCycleDetector())

    def run_from_dataframe(self, df) -> DetectionPipelineResult:
        txs, eval_labels = self.ingestion.load_from_dataframe(df)
        if not txs:
            raise ValueError("No usable transactions remain after input validation")
        graph = self.graph_engine.build_graph(txs)
        alerts: List[DetectionAlert] = []
        for detector in self.detectors:
            alerts.extend(detector.detect(graph, txs))
        # Detect identifier collisions across algorithms and broken source evidence.
        ids = [a.alert_id for a in alerts]
        if len(set(ids)) != len(ids):
            raise AssertionError("Detector alert_id collision")
        evidence = {t.transaction_id for t in txs}
        for alert in alerts:
            if not alert.transaction_ids or not set(alert.transaction_ids).issubset(evidence):
                raise AssertionError(f"Alert {alert.alert_id} references missing transaction IDs")
        return DetectionPipelineResult(txs, alerts, self.graph_engine,
                                      eval_labels, self.ingestion.skipped_records.copy(),
                                      self.ingestion.audit.copy())

    def run_from_csv(self, csv_filepath: str) -> DetectionPipelineResult:
        import pandas as pd
        return self.run_from_dataframe(pd.read_csv(csv_filepath, dtype=str, keep_default_na=False))
