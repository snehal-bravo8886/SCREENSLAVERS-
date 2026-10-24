"""Native IBM AMLSim scenario graph/detection for archived sourceNodeId/targetNodeId/value/time.

No calendar timestamps or SAR labels are fabricated. Numbers in the IBM file are
simulation steps; no duration in real-world minutes is assumed. The only labels
are account-level `nodes.csv` labels, which NEVER enter this module's detectors.
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from bisect import bisect_right
import hashlib
import io
import json
import math
import tarfile
import time

import networkx as nx
import pandas as pd

TX_HEADERS = ["sourceNodeId", "targetNodeId", "value", "time"]
NODE_HEADERS = ["nodeid", "isFraud", "init_balance", "fraudStep"]


@dataclass(frozen=True, slots=True)
class StepTransaction:
    transaction_id: str
    source_account: str
    destination_account: str
    amount: float
    simulation_step: int
    currency: str = "XXX"

    def to_dict(self):
        return {"transaction_id": self.transaction_id,
                "source_account": self.source_account,
                "destination_account": self.destination_account,
                "amount": self.amount, "currency": self.currency,
                "timestamp": None, "simulation_step": self.simulation_step,
                "time_unit": "simulation_step", "id_is_derived": True}


def _read_archive(path: Path):
    if not path.is_file():
        raise FileNotFoundError(path)
    with tarfile.open(path, "r:gz") as archive:
        members = {Path(m.name).name: m for m in archive if m.isfile()}
        necessary = ("transactions.csv", "nodes.csv", "metadata.txt")
        missing = [n for n in necessary if n not in members]
        if missing:
            raise ValueError(f"Archive lacks required files: {missing}")
        if members["transactions.csv"].size > 150_000_000 or members["nodes.csv"].size > 25_000_000:
            raise ValueError("Archive members exceed dataset limits")
        contents = {n: archive.extractfile(members[n]).read() for n in necessary}
    # CSV parsing uses text strings, retaining source IDs without float coercion.
    raw_tx = pd.read_csv(io.BytesIO(contents["transactions.csv"]),dtype=str,keep_default_na=False)
    raw_nodes = pd.read_csv(io.BytesIO(contents["nodes.csv"]),dtype=str,keep_default_na=False)
    if list(raw_tx.columns) != TX_HEADERS or list(raw_nodes.columns) != NODE_HEADERS:
        raise ValueError(f"Unexpected IBM archive schema: transactions={list(raw_tx.columns)}, nodes={list(raw_nodes.columns)}")
    return raw_tx, raw_nodes, contents


def ingest_archive(path: Path):
    """Return validated data + *private* account labels. Do not pass labels to detectors."""
    raw_tx, raw_nodes, contents = _read_archive(path)
    if raw_tx.empty or raw_nodes.empty:
        raise ValueError("Empty IBM scenario data")
    transactions: List[StepTransaction] = []
    unique_nodes: set[str] = set()
    for num, values in enumerate(raw_tx.itertuples(index=False, name=None), start=2):
        src, dst, raw_amount, raw_step = (str(x).strip() for x in values)
        if not src or not dst or not src.isdecimal() or not dst.isdecimal():
            raise ValueError(f"Invalid account ID at CSV row {num}")
        if not raw_step.isdecimal():
            raise ValueError(f"Invalid simulation step at CSV row {num}")
        try:
            amount = Decimal(raw_amount)
        except InvalidOperation as exc:
            raise ValueError(f"Invalid amount at row {num}") from exc
        if not amount.is_finite() or amount <= 0 or amount > Decimal("1e12"):
            raise ValueError(f"Non-finite, nonpositive or excessive amount at row {num}")
        step = int(raw_step)
        if step < 0:
            raise ValueError(f"Negative simulation step at row {num}")
        transactions.append(StepTransaction(f"IBM20K-ROW-{num-1:07d}", src, dst, float(amount), step))
        unique_nodes.update((src,dst))
    node_ids: set[str] = set()
    private_labels: dict[str, int] = {}
    for rowno, (nid, fraud, _bal, fraudstep) in enumerate(raw_nodes.itertuples(index=False,name=None),start=2):
        if not nid.isdecimal() or nid in node_ids or fraud not in ("0","1"):
            raise ValueError(f"Invalid or duplicate node/label at nodes.csv row {rowno}")
        if not fraudstep.lstrip("-").isdecimal():
            raise ValueError(f"Malformed fraudStep at nodes.csv row {rowno}")
        node_ids.add(nid)
        private_labels[nid] = int(fraud)
    if not unique_nodes.issubset(node_ids):
        raise ValueError(f"Transaction source/target account missing in nodes.csv: {list(unique_nodes-node_ids)[:3]}")
    metadata_text = contents["metadata.txt"].decode("utf-8",errors="replace").strip()
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    audit = {"dataset":path.name,"dataset_type":"IBM AMLSim archived synthetic scenario", "archive_sha256":sha(path.read_bytes()),
             "transactions_csv_sha256":sha(contents["transactions.csv"]),"nodes_csv_sha256":sha(contents["nodes.csv"]),
             "metadata_text":metadata_text,
             "source_columns":TX_HEADERS,"account_columns":NODE_HEADERS,
             "transaction_count":len(transactions),"accounts_in_nodes_file":len(node_ids),
             "accounts_present_in_transfers":len(unique_nodes),
             "simulation_step_min":min(t.simulation_step for t in transactions),
             "simulation_step_max":max(t.simulation_step for t in transactions),
             "amount_unit":"XXX (unspecified synthetic currency)",
             "timestamps":"Native integer simulation steps; no calendar date or elapsed minutes inferred",
             "transactions_with_source_ids":0,"transaction_ids_derived":len(transactions),
             "account_labels_available_offline_only":True,
             "account_labels_flagged":sum(private_labels.values()),
             "declared_fraud_node_count_in_metadata":1803,
             "metadata_account_label_discrepancy":sum(private_labels.values())-1803,
             "source_provenance":"User-supplied 20K_fanin200cycle200.tgz; structurally consistent with published IBM AMLSim archive; SHA listed for verification"}
    return transactions, private_labels, audit


def build_graph(txs: List[StepTransaction]) -> nx.MultiDiGraph:
    G=nx.MultiDiGraph()
    for t in txs:
        G.add_edge(t.source_account,t.destination_account,key=t.transaction_id,
                   transaction_id=t.transaction_id,amount=t.amount,simulation_step=t.simulation_step,currency=t.currency)
    if G.number_of_edges() != len(txs):
        raise AssertionError("Graph lost transaction identity")
    return G


def _new_alert(prefix, count, detector, involved, evidence, start, end, features, reason):
    return {"alert_id":f"DET-{prefix}-{count:06d}","detector":detector,
            "account_ids": sorted(set(involved),key=lambda s:int(s) if s.isdecimal() else s),
            "transaction_ids":list(evidence),
            "start_time":None,"end_time":None,"start_step":int(start),"end_step":int(end),
            "time_unit":"simulation_step", "features":features,"reason":reason}


def detect_fan(txs: List[StepTransaction], direction: str, *, window_steps:int, min_counterparties:int, max_alerts_per_account:int=2):
    if window_steps < 0 or min_counterparties < 2 or max_alerts_per_account < 1:
        raise ValueError("Invalid fan detector config")
    grouped: Dict[str,List[StepTransaction]] = defaultdict(list)
    for t in txs:
        if t.source_account != t.destination_account:
            grouped[t.destination_account if direction=='in' else t.source_account].append(t)
    alerts=[]
    for account in sorted(grouped,key=lambda s:int(s)):
        items=sorted(grouped[account], key=lambda t:(t.simulation_step,t.transaction_id))
        n=len(items); start=0; end=0; counts=defaultdict(int); produced=0
        while start<n and produced<max_alerts_per_account:
            st=items[start].simulation_step
            while end<n and items[end].simulation_step-st<=window_steps:
                party=items[end].source_account if direction=='in' else items[end].destination_account
                counts[party]+=1
                end+=1
            if len(counts)>=min_counterparties:
                batch=items[start:end]
                produced+=1
                direction_name='fan_in' if direction=='in' else 'fan_out'
                alerts.append(_new_alert('FANIN' if direction=='in' else 'FANOUT',len(alerts)+1,direction_name,
                    [account,*counts.keys()], [t.transaction_id for t in batch],
                    batch[0].simulation_step,batch[-1].simulation_step,
                    {"focus_account":account,"distinct_counterparties":len(counts),"transaction_count":len(batch),
                     "total_amount":round(sum(t.amount for t in batch),2),"window_steps":window_steps},
                    f"Candidate {direction_name}: {len(counts)} distinct counterparties in {window_steps} simulation steps; may be routine activity"))
                start=end
                counts.clear()
            else:
                party=items[start].source_account if direction=='in' else items[start].destination_account
                counts[party]-=1
                if counts[party]==0:
                    del counts[party]
                start+=1
            if end<start:
                end=start
    return alerts


def detect_rapid(txs: List[StepTransaction], *,window_steps:int=3, min_ratio:float=.80,max_ratio:float=1.0, max_alerts_per_account:int=5):
    if window_steps<1 or not (0<min_ratio<=max_ratio) or max_alerts_per_account<1:
        raise ValueError("Invalid rapid detector config")
    incoming=defaultdict(list);outgoing=defaultdict(list)
    for t in txs:
        incoming[t.destination_account].append(t)
        outgoing[t.source_account].append(t)
    alerts=[]
    for node in sorted(set(incoming)&set(outgoing),key=lambda s:int(s)):
        ins=sorted(incoming[node], key=lambda t:(t.simulation_step,t.transaction_id))
        outs=sorted(outgoing[node], key=lambda t:(t.simulation_step,t.transaction_id))
        steps=[t.simulation_step for t in ins]
        used=set(); emitted=0
        for out in outs:
            if emitted>=max_alerts_per_account: break
            if out.destination_account==node:continue
            j=bisect_right(steps,out.simulation_step-1)-1
            while j>=0 and out.simulation_step-ins[j].simulation_step<=window_steps:
                inward=ins[j];j-=1
                if inward.transaction_id in used or inward.source_account in (node,out.destination_account):continue
                if inward.currency!=out.currency: continue
                ratio=out.amount/inward.amount
                if min_ratio<=ratio<=max_ratio:
                    used.add(inward.transaction_id)
                    emitted+=1
                    alerts.append(_new_alert('PASS',len(alerts)+1,'rapid_pass_through',
                      [inward.source_account,node,out.destination_account],
                      [inward.transaction_id,out.transaction_id],inward.simulation_step,out.simulation_step,
                      {"intermediary_account":node,"elapsed_steps":out.simulation_step-inward.simulation_step,
                       "transfer_ratio":round(ratio,5),"inflow_amount":inward.amount,"outflow_amount":out.amount,
                       "window_steps":window_steps},
                      f"Candidate onward flow through {node}: two time-ordered transfers with amount ratio {ratio:.3f} within {window_steps} simulation steps"))
                    break
    return alerts


def detect_three_cycles(txs:List[StepTransaction],*,window_steps:int=12,max_alerts:int=1000):
    """Bounded time-respecting 3-edge A→B→C→A; strict time order of STEPS."""
    if window_steps<2 or max_alerts<1:
        raise ValueError("Invalid cycle detector config")
    out=defaultdict(list)
    for t in txs: out[t.source_account].append(t)
    for acct in out: out[acct].sort(key=lambda t:(t.simulation_step,t.transaction_id))
    alerts=[]
    seen=set()
    ordered=sorted(txs,key=lambda t:(t.simulation_step,t.transaction_id))
    for ab in ordered:
        if len(alerts)>=max_alerts:break
        A,B=ab.source_account,ab.destination_account
        if A==B:continue
        for bc in out.get(B,[]):
            if bc.simulation_step<=ab.simulation_step: continue
            if bc.simulation_step-ab.simulation_step>window_steps:break
            C=bc.destination_account
            if C in (A,B):continue
            for ca in out.get(C,[]):
                if ca.simulation_step<=bc.simulation_step:continue
                if ca.simulation_step-ab.simulation_step>window_steps:break
                if ca.destination_account!=A:continue
                key=tuple(sorted((ab.transaction_id,bc.transaction_id,ca.transaction_id)))
                if key in seen:continue
                seen.add(key)
                alerts.append(_new_alert('CYCLE',len(alerts)+1,'temporal_cycle',
                   [A,B,C],[ab.transaction_id,bc.transaction_id,ca.transaction_id],
                   ab.simulation_step,ca.simulation_step,
                   {"cycle_length":3,"elapsed_steps":ca.simulation_step-ab.simulation_step,"window_steps":window_steps},
                   f"Candidate 3-account time-respecting cycle (strictly increasing simulation steps): {A}→{B}→{C}→{A}"))
    return alerts


def evaluate_account_signal_coverage(alerts, private_labels:Dict[str,int], audit):
    """Only an ACCOUNT-LEVEL descriptive comparison. Not transaction or scenario recall."""
    flagged=set(a for al in alerts for a in al['account_ids'])
    positive={a for a,v in private_labels.items() if v==1}
    matched=flagged & positive
    return {"evaluation_type":"account-level exploratory coverage (not money-laundering recall)",
            "labeled_positive_accounts":len(positive),"accounts_mentioned_in_alerts":len(flagged),
            "labeled_positive_accounts_mentioned":len(matched),
            "proportion_positive_accounts_mentioned":round(len(matched)/len(positive),6) if positive else None,
            "source_label_zero_accounts_mentioned":len(flagged-positive),
            "caveat":"Account labels are NOT per-transaction or per-scenario proof; nonfraud labels do not establish false alerts. Detection did not receive these labels."}


def run_archive(path:Path, *,fan_window_steps:int=4,fan_min_counterparties:int=5,
                rapid_window_steps:int=3,include_cycles:bool=False,cycle_window_steps:int=12):
    started=time.perf_counter()
    txs, private_labels, audit=ingest_archive(path)
    graph=build_graph(txs)
    alerts=[]
    alerts.extend(detect_fan(txs,'in',window_steps=fan_window_steps,min_counterparties=fan_min_counterparties))
    alerts.extend(detect_fan(txs,'out',window_steps=fan_window_steps,min_counterparties=fan_min_counterparties))
    alerts.extend(detect_rapid(txs,window_steps=rapid_window_steps))
    if include_cycles:
        alerts.extend(detect_three_cycles(txs,window_steps=cycle_window_steps))
    known={t.transaction_id for t in txs}
    if len(known)!=len(txs):raise AssertionError("Duplicate derived transaction IDs")
    all_ids=set()
    for alert in alerts:
        if alert['alert_id'] in all_ids:raise AssertionError("Duplicate alert ID")
        all_ids.add(alert['alert_id'])
        if not alert['transaction_ids'] or not set(alert['transaction_ids']).issubset(known):
            raise AssertionError("Alert references missing transactions")
    counts=defaultdict(int)
    for a in alerts:counts[a['detector']]+=1
    return {"transactions":txs,"alerts":alerts,"private_labels":private_labels,"audit":audit,
            "graph_node_count":graph.number_of_nodes(),"graph_edge_count":graph.number_of_edges(),
            "alert_breakdown":dict(sorted(counts.items())),
            "account_evaluation":evaluate_account_signal_coverage(alerts,private_labels,audit),
            "runtime_seconds":round(time.perf_counter()-started,3),
            "config":{"time_unit":"simulation_step","fan_window_steps":fan_window_steps,
                      "fan_min_counterparties":fan_min_counterparties,"rapid_window_steps":rapid_window_steps,
                      "cycles_enabled":include_cycles,"cycle_window_steps":cycle_window_steps}}
