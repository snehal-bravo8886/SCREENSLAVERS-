"""
Short Time-Respecting Cycle Detector
Section 3.3: Flags bounded circular routing (e.g., A -> B -> C -> A) where transactions occur in causal chronological order.
"""

from typing import List, Tuple
from itertools import islice
import logging
from datetime import datetime
import networkx as nx
from .base import BaseDetector
from ..schemas import DetectionAlert, CanonicalTransaction


class TemporalCycleDetector(BaseDetector):
    def __init__(self, max_cycle_length: int = 4, max_window_hours: int = 24, max_candidates: int = 3000):
        super().__init__(name="temporal_cycle")
        self.max_cycle_length = max_cycle_length
        self.max_window_hours = max_window_hours
        self.max_candidates = max_candidates
        self.max_traversals_per_cycle = 100

    def detect(self, G: nx.MultiDiGraph, transactions: List[CanonicalTransaction]) -> List[DetectionAlert]:
        alerts: List[DetectionAlert] = []
        alert_counter = 1
        if G.number_of_nodes() > 3000 or G.number_of_edges() > 15000:
            raise ValueError("Optional cycle analysis refused for oversized graph; use bounded sample or disable cycles")

        # Use a simple directed view to find cycle candidates
        simple_di = nx.DiGraph(G)
        # Bounds limit the search to relevant short cycles. In a very dense graph,
        # stop after max_candidates; this is not an exhaustive search.
        candidate_cycles = nx.simple_cycles(simple_di, length_bound=self.max_cycle_length)
        for cycle_nodes in islice(candidate_cycles, self.max_candidates):
            if len(cycle_nodes) < 2:
                continue
            # Check if there is an edge along each step of cycle with strictly increasing time
            # cycle_nodes: [A, B, C] -> edges (A->B), (B->C), (C->A)
            num_nodes = len(cycle_nodes)
            paths = self._find_temporal_traversals(G, cycle_nodes)

            for path_edges in paths:
                tx_ids = [e["key"] for e in path_edges]
                start_dt = path_edges[0]["data"]["dt"]
                end_dt = path_edges[-1]["data"]["dt"]
                elapsed_hours = (end_dt - start_dt).total_seconds() / 3600.0

                if elapsed_hours <= self.max_window_hours:
                    alert_id = f"DET-CYCLE-{alert_counter:04d}"
                    alert_counter += 1

                    cycle_str = " -> ".join([str(n) for n in cycle_nodes] + [str(cycle_nodes[0])])
                    alert = DetectionAlert(
                        alert_id=alert_id,
                        detector=self.name,
                        account_ids=[str(n) for n in cycle_nodes],
                        transaction_ids=tx_ids,
                        start_time=path_edges[0]["data"]["timestamp"],
                        end_time=path_edges[-1]["data"]["timestamp"],
                        features={
                            "cycle_length": len(cycle_nodes),
                            "elapsed_hours": round(elapsed_hours, 2),
                            "path": cycle_str
                        },
                        reason=f"Time-ordered circular flow: {cycle_str} completed within {elapsed_hours:.2f} hours"
                    )
                    alerts.append(alert)
                    break

        return alerts

    def _find_temporal_traversals(self, G: nx.MultiDiGraph, cycle_nodes: List[str]) -> List[List[dict]]:
        """Finds sequences of edges where each subsequent edge has timestamp > previous edge across any rotation."""
        traversals: List[List[dict]] = []
        n = len(cycle_nodes)

        # A cycle can start at any node in the cycle; test all rotations
        for rot_idx in range(n):
            rotated = cycle_nodes[rot_idx:] + cycle_nodes[:rot_idx]

            def dfs(step: int, current_path: List[dict], last_dt: datetime):
                if len(traversals) >= self.max_traversals_per_cycle:
                    return
                if step == n:
                    traversals.append(list(current_path))
                    return

                u = rotated[step]
                v = rotated[(step + 1) % n]

                if not G.has_edge(u, v):
                    return

                for key, data in G[u][v].items():
                    if len(traversals) >= self.max_traversals_per_cycle:
                        break
                    if data["dt"] > last_dt:
                        current_path.append({"u": u, "v": v, "key": key, "data": data})
                        dfs(step + 1, current_path, data["dt"])
                        current_path.pop()

            u0 = rotated[0]
            v0 = rotated[1]
            if G.has_edge(u0, v0):
                for key, data in G[u0][v0].items():
                    dfs(1, [{"u": u0, "v": v0, "key": key, "data": data}], data["dt"])

            if traversals:
                break

        return traversals
