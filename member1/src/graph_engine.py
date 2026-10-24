"""
Temporal Multi-Edge Directed Graph Engine
Adheres to Section 3.2: Models bank accounts as nodes and distinct timestamped transfers as edges.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import networkx as nx
from .schemas import CanonicalTransaction


def parse_iso(ts_str: str) -> datetime:
    """Helper to parse ISO-8601 string to timezone-aware datetime."""
    # Handles trailing 'Z' or standard offsets
    clean_str = ts_str.replace("Z", "+00:00")
    return datetime.fromisoformat(clean_str)


class TemporalGraphEngine:
    def __init__(self):
        self.graph = nx.MultiDiGraph()
        self.tx_lookup: Dict[str, CanonicalTransaction] = {}

    def build_graph(self, transactions: List[CanonicalTransaction]) -> nx.MultiDiGraph:
        """
        Builds or updates directed multi-graph from canonical transactions.
        Guarantees deterministic node and edge insertion.
        """
        self.graph.clear()
        self.tx_lookup.clear()

        # Sort transactions deterministically by timestamp, then transaction_id
        sorted_txs = sorted(transactions, key=lambda t: (t.timestamp, t.transaction_id))

        for tx in sorted_txs:
            if tx.transaction_id in self.tx_lookup:
                raise ValueError(f"Duplicate transaction ID in graph input: {tx.transaction_id}")
            self.tx_lookup[tx.transaction_id] = tx
            dt = parse_iso(tx.timestamp)

            # Ensure nodes exist
            if not self.graph.has_node(tx.source_account):
                self.graph.add_node(tx.source_account, account_id=tx.source_account)
            if not self.graph.has_node(tx.destination_account):
                self.graph.add_node(tx.destination_account, account_id=tx.destination_account)

            # Add directed edge with unique key = transaction_id
            self.graph.add_edge(
                tx.source_account,
                tx.destination_account,
                key=tx.transaction_id,
                transaction_id=tx.transaction_id,
                amount=tx.amount,
                currency=tx.currency,
                dt=dt,
                timestamp=tx.timestamp
            )

        return self.graph

    def get_inflows(self, account_id: str) -> List[Dict[str, Any]]:
        """Returns all incoming transfers to an account, sorted chronologically."""
        if not self.graph.has_node(account_id):
            return []
        edges = []
        for u, v, k, data in self.graph.in_edges(account_id, keys=True, data=True):
            edges.append({
                "transaction_id": k,
                "from_account": u,
                "to_account": v,
                "amount": data["amount"],
                "dt": data["dt"],
                "timestamp": data["timestamp"]
            })
        return sorted(edges, key=lambda x: (x["dt"], x["transaction_id"]))

    def get_outflows(self, account_id: str) -> List[Dict[str, Any]]:
        """Returns all outgoing transfers from an account, sorted chronologically."""
        if not self.graph.has_node(account_id):
            return []
        edges = []
        for u, v, k, data in self.graph.out_edges(account_id, keys=True, data=True):
            edges.append({
                "transaction_id": k,
                "from_account": u,
                "to_account": v,
                "amount": data["amount"],
                "dt": data["dt"],
                "timestamp": data["timestamp"]
            })
        return sorted(edges, key=lambda x: (x["dt"], x["transaction_id"]))

    def get_subgraph_nodes_and_edges(self, transaction_ids: List[str]) -> Dict[str, Any]:
        """
        Extracts a clean subgraph representation for Member C (Cytoscape visualization)
        given a list of relevant transaction IDs.
        """
        nodes = set()
        edges = []
        for tx_id in transaction_ids:
            tx = self.tx_lookup.get(tx_id)
            if tx:
                nodes.add(tx.source_account)
                nodes.add(tx.destination_account)
                edges.append({
                    "id": tx.transaction_id,
                    "source": tx.source_account,
                    "target": tx.destination_account,
                    "amount": tx.amount,
                    "currency": tx.currency,
                    "timestamp": tx.timestamp
                })
        return {
            "nodes": [{"id": acc, "label": acc} for acc in sorted(nodes)],
            "edges": edges
        }
