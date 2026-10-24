"""Candidate rapid-onward-transfer rule: explainable, time-ordered matching.

This is NOT a funds-provenance model. One incoming transaction matches at most
one outgoing transaction per intermediary to avoid inflated duplicated evidence.
"""
from datetime import datetime
from typing import List
import networkx as nx
from .base import BaseDetector
from ..schemas import DetectionAlert, CanonicalTransaction


class RapidPassThroughDetector(BaseDetector):
    def __init__(self, max_elapsed_minutes: int = 60, min_ratio: float = 0.80, max_ratio: float = 1.05):
        super().__init__(name="rapid_pass_through")
        if max_elapsed_minutes <= 0 or not (0 < min_ratio <= max_ratio):
            raise ValueError("Invalid rapid-pass-through detector thresholds")
        self.max_elapsed_minutes = max_elapsed_minutes
        self.min_ratio = min_ratio
        self.max_ratio = max_ratio

    def detect(self, G: nx.MultiDiGraph, transactions: List[CanonicalTransaction]) -> List[DetectionAlert]:
        alerts: List[DetectionAlert] = []
        for node in sorted(G.nodes()):
            inbound = sorted(G.in_edges(node, keys=True, data=True), key=lambda e: (e[3]["dt"], e[2]))
            outbound = sorted(G.out_edges(node, keys=True, data=True), key=lambda e: (e[3]["dt"], e[2]))
            used_inflows = set()
            for _, destination, out_id, out_data in outbound:
                if node == destination:
                    continue
                # Most recent eligible receipt, and never reuse a receipt across multiple matches.
                for source, _, in_id, in_data in reversed(inbound):
                    if in_id in used_inflows or source == destination or source == node:
                        continue
                    if in_data["currency"] != out_data["currency"]:
                        continue
                    minutes = (out_data["dt"] - in_data["dt"]).total_seconds() / 60
                    if not (0 < minutes <= self.max_elapsed_minutes):
                        continue
                    ratio = out_data["amount"] / in_data["amount"]
                    if not (self.min_ratio <= ratio <= self.max_ratio):
                        continue
                    used_inflows.add(in_id)
                    alerts.append(DetectionAlert(
                        alert_id=f"DET-PASS-{len(alerts)+1:04d}",
                        detector=self.name,
                        account_ids=[str(source), str(node), str(destination)],
                        transaction_ids=[str(in_id), str(out_id)],
                        start_time=in_data["timestamp"],
                        end_time=out_data["timestamp"],
                        features={
                            "elapsed_minutes": round(minutes, 2),
                            "transfer_ratio": round(ratio, 3),
                            "inflow_amount": in_data["amount"],
                            "outflow_amount": out_data["amount"],
                            "intermediary_account": str(node),
                        },
                        reason=(
                            f"Candidate rapid onward flow via {node}: {in_data['amount']:,.2f} "
                            f"{in_data['currency']} received from {source}; "
                            f"{out_data['amount']:,.2f} {out_data['currency']} forwarded to "
                            f"{destination} after {minutes:.1f} minutes."
                        ),
                    ))
                    break
        return alerts
