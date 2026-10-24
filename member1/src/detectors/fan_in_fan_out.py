"""Bounded distinct-counterparty concentration detectors.

These are heuristic alert candidates, NOT conclusions of suspicious intent.
Any routine payroll processor can trigger fan-out: evaluation must measure noise.
"""
from __future__ import annotations
from typing import List
import networkx as nx
from .base import BaseDetector
from ..schemas import CanonicalTransaction, DetectionAlert


class _FanDetector(BaseDetector):
    def __init__(self, direction: str, min_counterparties: int = 3,
                 window_minutes: int = 120, max_alerts_per_account: int = 3):
        super().__init__("fan_in" if direction == "in" else "fan_out")
        if min_counterparties < 2 or window_minutes <= 0 or max_alerts_per_account < 1:
            raise ValueError("Invalid fan detector configuration")
        self.direction = direction
        self.min_counterparties = min_counterparties
        self.window_minutes = window_minutes
        self.max_alerts_per_account = max_alerts_per_account

    def detect(self, G: nx.MultiDiGraph, transactions: List[CanonicalTransaction]) -> List[DetectionAlert]:
        alerts = []
        counter = 0
        for account in sorted(G.nodes):
            edges = (list(G.in_edges(account, keys=True, data=True)) if self.direction == "in"
                     else list(G.out_edges(account, keys=True, data=True)))
            # Ignore account-to-itself transfers when looking for distinct counterparties.
            edges = [e for e in edges if e[0] != e[1]]
            if len(edges) < self.min_counterparties:
                continue
            edges.sort(key=lambda e: (e[3]["dt"], e[2]))
            start = 0
            end = 0  # two-pointer rolling window: amortized O(number of account edges)
            counterparty_counts = {}
            emitted = 0
            while start < len(edges) and emitted < self.max_alerts_per_account:
                window_start = edges[start][3]["dt"]
                while end < len(edges) and (edges[end][3]["dt"] - window_start).total_seconds() <= self.window_minutes * 60:
                    party = edges[end][0] if self.direction == "in" else edges[end][1]
                    counterparty_counts[party] = counterparty_counts.get(party, 0) + 1
                    end += 1
                if len(counterparty_counts) >= self.min_counterparties:
                    batch = edges[start:end]
                    counter += 1
                    emitted += 1
                    total = round(sum(e[3]["amount"] for e in batch), 2)
                    alerts.append(DetectionAlert(
                        alert_id=f"DET-{self.name.upper().replace('_', '')}-{counter:05d}",
                        detector=self.name,
                        account_ids=sorted(set(counterparty_counts) | {account}),
                        transaction_ids=[e[2] for e in batch],
                        start_time=batch[0][3]["timestamp"],
                        end_time=batch[-1][3]["timestamp"],
                        features={"target_account" if self.direction == "in" else "source_account": account,
                                  "distinct_counterparties": len(counterparty_counts),
                                  "transaction_count": len(batch),
                                  "total_inflow" if self.direction == "in" else "total_outflow": total,
                                  "window_minutes": self.window_minutes,
                                  "note": "Concentration rule only; normal business payments can trigger this"},
                        reason=f"Concentrated {self.name.replace('_','-')} candidate: {len(counterparty_counts)} distinct counterparties within {self.window_minutes} minutes",
                    ))
                    start = end  # do not duplicate the same burst in many overlapping alerts
                    counterparty_counts.clear()
                else:
                    old = edges[start]
                    party = old[0] if self.direction == "in" else old[1]
                    counterparty_counts[party] -= 1
                    if counterparty_counts[party] == 0:
                        del counterparty_counts[party]
                    start += 1
                if end < start:
                    end = start

        return alerts


class FanInDetector(_FanDetector):
    def __init__(self, min_counterparties: int = 3, window_minutes: int = 120):
        super().__init__("in", min_counterparties, window_minutes)


class FanOutDetector(_FanDetector):
    def __init__(self, min_counterparties: int = 3, window_minutes: int = 120):
        super().__init__("out", min_counterparties, window_minutes)
