"""Evidence-first case construction and interpretable priority for IBM native steps.

This module never reads ground-truth labels. All spans are simulation STEPS,
not minutes/hours. Case memberships are fixed during stress tests.
"""
from __future__ import annotations

from bisect import bisect_left
from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any
import json
import math

FORBIDDEN_FIELDS = frozenset({"isFraud", "is_fraud", "is_sar", "alert_type", "model_type", "fraudStep", "fraud_step", "private_labels", "ground_truth", "risk_label"})
DETECTORS = frozenset({"fan_in", "fan_out", "rapid_pass_through", "temporal_cycle"})
BASE_WEIGHTS = {"fund_flow": .35, "velocity": .25, "network_structure": .25, "behavioral_deviation": .15}


@dataclass(frozen=True)
class CaseConfig:
    max_span_steps: int = 12
    max_alerts: int = 7
    max_transactions: int = 28
    max_accounts: int = 35
    max_graph_hops: int = 4
    close_step_gap: int = 2
    historical_lookback_steps: int = 30
    min_historical_steps: int = 12
    min_historical_events: int = 3


def _clean_dataset(payload: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    """Strictly enforce the Member A source-native JSON and no label leakage."""
    if not isinstance(payload, dict) or payload.get("schema_version") != "member-a-simulation-step-v1":
        raise ValueError("Expected schema_version member-a-simulation-step-v1")
    def reject_labels(x: Any) -> None:
        if isinstance(x, dict):
            if FORBIDDEN_FIELDS.intersection(x):
                raise ValueError("Evaluation labels are forbidden anywhere in case engine inputs")
            for v in x.values(): reject_labels(v)
        elif isinstance(x, list):
            for v in x: reject_labels(v)
    reject_labels(payload)
    ts, alerts = payload.get("transactions"), payload.get("alerts")
    if not isinstance(ts, list) or not isinstance(alerts, list):
        raise ValueError("transactions and alerts must be arrays")
    tx_index: dict[str, dict] = {}
    for t in ts:
        if not isinstance(t, dict) or FORBIDDEN_FIELDS.intersection(t):
            raise ValueError("Invalid transaction or forbidden label keys")
        for k in ("transaction_id", "source_account", "destination_account", "amount", "simulation_step", "currency", "time_unit"):
            if k not in t:
                raise ValueError(f"Transaction is missing {k}")
        ident = t["transaction_id"]
        if not isinstance(ident, str) or not ident.strip() or ident in tx_index:
            raise ValueError(f"Empty or duplicate transaction_id: {ident!r}")
        if (not isinstance(t["source_account"], str) or not t["source_account"].strip() or
            not isinstance(t["destination_account"], str) or not t["destination_account"].strip()):
            raise ValueError(f"Invalid account ID for {ident}")
        if not isinstance(t["amount"], (int, float)) or isinstance(t["amount"], bool) or not math.isfinite(t["amount"]) or t["amount"] <= 0:
            raise ValueError(f"Invalid amount for {ident}")
        if not isinstance(t["simulation_step"], int) or isinstance(t["simulation_step"], bool) or t["simulation_step"] < 0:
            raise ValueError(f"Invalid simulation step for {ident}")
        if t["time_unit"] != "simulation_step" or t.get("timestamp", None) is not None or t.get("currency") != "XXX":
            raise ValueError("This engine requires native IBM simulation steps and unspecified XXX currency")
        tx_index[ident] = t
    alert_seen: set[str] = set()
    for a in alerts:
        if not isinstance(a, dict) or FORBIDDEN_FIELDS.intersection(a):
            raise ValueError("Invalid alert or forbidden source evaluation keys")
        aid = a.get("alert_id")
        if not isinstance(aid, str) or not aid or aid in alert_seen:
            raise ValueError(f"Duplicate or empty alert ID {aid!r}")
        alert_seen.add(aid)
        if a.get("detector") not in DETECTORS:
            raise ValueError(f"Unrecognized detector in {aid}")
        ids = a.get("transaction_ids")
        if not isinstance(ids, list) or not ids or any(t not in tx_index for t in ids):
            raise ValueError(f"Missing evidence for alert {aid}")
        if len(set(ids)) != len(ids):
            raise ValueError(f"Repeated evidence inside alert {aid}")
        steps = [tx_index[t]["simulation_step"] for t in ids]
        if a.get("start_step") != min(steps) or a.get("end_step") != max(steps):
            raise ValueError(f"Alert {aid} has incorrect evidence time bounds")
        account_ids = set(a.get("account_ids", []))
        evidence_accounts = {ac for txid in ids for ac in (tx_index[txid]["source_account"],tx_index[txid]["destination_account"])}
        if account_ids != evidence_accounts:
            raise ValueError(f"Alert {aid} has incorrect evidence account IDs")
        if a.get("time_unit") != "simulation_step" or a.get("start_time") is not None or a.get("end_time") is not None:
            raise ValueError(f"Alert {aid} must keep native simulation steps")
    return ts, alerts


def load_handoff(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    _clean_dataset(data)
    return data


class CaseEngine:
    """Immutable input transactions and alerts, cached deterministic cases."""
    def __init__(self, payload: dict, config: CaseConfig | None = None):
        self.config = config or CaseConfig()
        self.transactions, self.alerts = _clean_dataset(payload)
        self.tx_by_id = {t["transaction_id"]: t for t in self.transactions}
        self.alert_by_id = {a["alert_id"]: a for a in self.alerts}
        self.history: dict[str, list[tuple[int,str]]] = defaultdict(list)
        for t in self.transactions:
            self.history[t["source_account"]].append((t["simulation_step"], t["transaction_id"]))
            if t["destination_account"] != t["source_account"]:
                self.history[t["destination_account"]].append((t["simulation_step"], t["transaction_id"]))
        self.history_steps: dict[str, list[int]] = {}
        for acc, evs in self.history.items():
            evs.sort()
            self.history_steps[acc] = [x[0] for x in evs]
        self.cases: list[dict] = []
        self.case_by_id: dict[str, dict] = {}

    def _can_merge(self, x: dict, y: dict) -> bool:
        cfg = self.config
        if len(x["alert_ids"]) + len(y["alert_ids"]) > cfg.max_alerts:
            return False
        if max(x["end"],y["end"]) - min(x["start"],y["start"]) > cfg.max_span_steps:
            return False
        if len(x["tx_ids"] | y["tx_ids"]) > cfg.max_transactions:
            return False
        if len(x["accounts"] | y["accounts"]) > cfg.max_accounts:
            return False
        # Do not create long causal stories from loose network connectivity.
        # Bound the undirected evidence diameter after each union.
        union_ids = x["tx_ids"] | y["tx_ids"]
        adjacency: dict[str, set[str]] = defaultdict(set)
        for tid in union_ids:
            t = self.tx_by_id[tid]
            u,v = t["source_account"], t["destination_account"]
            adjacency[u].add(v);adjacency[v].add(u)
        if not adjacency: return False
        visited: set[str] = set()
        start = next(iter(sorted(adjacency)))
        front = {start}
        for _ in range(cfg.max_graph_hops+1):
            visited |= front
            front = {nxt for u in front for nxt in adjacency[u]}-visited
            if not front: break
        if len(visited) != len(adjacency): return False
        # exact diameter for small bounded components
        for start in adjacency:
            seen = {start}
            frontier = {start}
            for _ in range(cfg.max_graph_hops):
                frontier = {nxt for u in frontier for nxt in adjacency[u]}-seen
                seen |= frontier
                if not frontier: break
            if len(seen) != len(adjacency): return False
        return True

    def _build_clusters(self) -> list[dict]:
        if not self.alerts: return []
        cfg = self.config
        ordered = sorted(self.alerts,key=lambda a:(a["start_step"],a["end_step"],a["alert_id"]))
        parts=[]
        for a in ordered:
            ids=set(a["transaction_ids"])
            parts.append({"alert_ids":{a["alert_id"]},"tx_ids":ids,"accounts":set(a["account_ids"]),
                          "start":a["start_step"],"end":a["end_step"]})
        # Candidate links are limited by actual shared transaction evidence or
        # two accounts + complementary detector types + very close step windows.
        tx_to_alert=defaultdict(list)
        account_to_alert=defaultdict(list)
        for i,a in enumerate(ordered):
            for tid in a["transaction_ids"]:tx_to_alert[tid].append(i)
            for acc in a["account_ids"]:account_to_alert[acc].append(i)
        candidates: dict[tuple[int,int],tuple[int,int]]={}
        for entries in tx_to_alert.values():
            for ix,i in enumerate(entries):
                for j in entries[ix+1:]:
                    key=(i,j)
                    val=candidates.get(key,(0,0))
                    candidates[key]=(val[0]+1,val[1])
        # Only consider accounts found in small enough alert neighborhoods;
        # no quadratic scan over high-degree bank/merchant accounts.
        pair_common: dict[tuple[int,int],int]=defaultdict(int)
        for entries in account_to_alert.values():
            if len(entries)>35:continue
            for ix,i in enumerate(entries):
                for j in entries[ix+1:]:
                    if ordered[i]["detector"]==ordered[j]["detector"]:continue
                    if ordered[j]["start_step"]-ordered[i]["end_step"]>cfg.close_step_gap:continue
                    pair_common[(i,j)]+=1
        for pair,common in pair_common.items():
            if common>=2:
                tx,old_common=candidates.get(pair,(0,0))
                candidates[pair]=(tx,common)
        parent=list(range(len(parts)))
        def find(i):
            while parent[i]!=i:
                parent[i]=parent[parent[i]];i=parent[i]
            return i
        # Strongest evidence links first. Ties resolved by evidence IDs.
        ranked=sorted(candidates, key=lambda ij:(-candidates[ij][0],-candidates[ij][1],ordered[ij[0]]["alert_id"],ordered[ij[1]]["alert_id"]))
        for i,j in ranked:
            a,b=find(i),find(j)
            if a==b:continue
            x,y=parts[a],parts[b]
            if not self._can_merge(x,y):continue
            if (min(x["alert_ids"]),a)>(min(y["alert_ids"]),b): a,b=b,a;x,y=y,x
            parent[b]=a
            x["alert_ids"].update(y["alert_ids"])
            x["tx_ids"].update(y["tx_ids"])
            x["accounts"].update(y["accounts"])
            x["start"]=min(x["start"],y["start"]);x["end"]=max(x["end"],y["end"])
        clusters=[parts[i] for i in range(len(parts)) if find(i)==i]
        return sorted(clusters,key=lambda p:(p["start"],min(p["alert_ids"])))

    def _alert_status(self, alert: dict, included: set[str]) -> dict:
        """Recompute source-defined detector threshold for this alert's OWN evidence.
        No cross-alert reuse; this is an evidence-exclusion sensitivity check,
        NOT a fresh re-detection or claim of a changed case membership.
        """
        live=[self.tx_by_id[i] for i in alert["transaction_ids"] if i in included]
        kind=alert["detector"]
        value=0.0;active=False;raw={}
        focus=alert.get("features",{}).get("focus_account")
        if kind=="fan_in":
            count=len({t["source_account"] for t in live if t["destination_account"]==focus})
            raw={"distinct_senders":count,"threshold":5}
            value=min(1.0,count/5);active=count>=5
        elif kind=="fan_out":
            count=len({t["destination_account"] for t in live if t["source_account"]==focus})
            raw={"distinct_recipients":count,"threshold":5}
            value=min(1.0,count/5);active=count>=5
        elif kind=="rapid_pass_through":
            # Member A emits exactly a 2-transaction onward pair.
            if len(live)==2:
                ordered=sorted(live,key=lambda t:(t["simulation_step"],t["transaction_id"]))
                u,v=ordered
                gap=v["simulation_step"]-u["simulation_step"]
                ratio=v["amount"]/u["amount"]
                active=(0<gap<=3 and .8<=ratio<=1.0 and u["destination_account"]==v["source_account"] and
                        len({u["source_account"],u["destination_account"],v["destination_account"]})==3)
                if active: value=min(1.0,ratio)
                raw={"ratio":round(ratio,6),"step_gap":gap,"matching_pair":active}
            else:raw={"matching_pair":False}
        elif kind=="temporal_cycle":
            if len(live)==3:
                for first in live:
                    for second in live:
                        if first is second or first["destination_account"]!=second["source_account"]:continue
                        for third in live:
                            if third is first or third is second:continue
                            steps=[first["simulation_step"],second["simulation_step"],third["simulation_step"]]
                            if (second["destination_account"]==third["source_account"] and
                                third["destination_account"]==first["source_account"] and
                                len({first["source_account"],second["source_account"],third["source_account"]})==3 and
                                steps[0]<steps[1]<steps[2] and steps[2]-steps[0]<=12):
                                active=True
                                raw={"elapsed_steps":steps[2]-steps[0],"complete_cycle":True}
                                break
                        if active:break
                    if active:break
            if not active:raw={"complete_cycle":False}
            value=1.0 if active else 0.0
        return {"alert_id":alert["alert_id"],"detector":kind,"threshold_met":active,
                "evidence_strength":round(value,6),"measured":raw,"remaining_support_ids":[i for i in alert["transaction_ids"] if i in included]}

    def _baseline(self, anchor_accounts: set[str], current_ids: list[str], start: int, end: int,
                  excluded: str | None) -> tuple[float | None,dict,list[str]]:
        cfg=self.config
        history_window=min(cfg.historical_lookback_steps,start)
        if history_window<cfg.min_historical_steps: return None,{"status":"insufficient_history","reason":"Too few earlier simulation steps"},[]
        current_window=max(1,end-start+1)
        scores=[];details=[]
        current_support=set(current_ids)
        for acc in sorted(anchor_accounts):
            steps=self.history_steps.get(acc,[])
            older=bisect_left(steps,start)
            old_from=bisect_left(steps,start-history_window)
            past_count=older-old_from
            if past_count<cfg.min_historical_events:continue
            current_total=bisect_left(steps,end+1)-older
            if excluded is not None:
                tx=self.tx_by_id[excluded]
                if (tx["source_account"]==acc or tx["destination_account"]==acc) and start<=tx["simulation_step"]<=end:
                    current_total-=1
            expected=past_count*current_window/history_window
            # excess compared to prior per-step volume, unvalidated 3x normalization
            spike=min(1.,max(0.,(current_total/max(expected,1.)-1.)/3.))
            scores.append(spike)
            details.append({"account_id":acc,"prior_transactions":past_count,"prior_window_steps":history_window,
                            "current_transactions":current_total,"current_window_steps":current_window,
                            "expected_current_count":round(expected,4),"normalized_spike":round(spike,6)})
        if not scores:
            return None,{"status":"insufficient_history","reason":"No focus account has >=3 earlier transfers in the lookback"},[]
        best=max(range(len(scores)),key=lambda ix:(scores[ix],-ix))
        best_acc=details[best]["account_id"]
        supports=[tid for tid in current_ids if best_acc in (self.tx_by_id[tid]["source_account"],self.tx_by_id[tid]["destination_account"])]
        return scores[best],{"status":"available","selected_account":best_acc,"measurement":details[best],"compared_accounts":len(scores)},supports

    def _score(self, alert_ids: list[str], tx_ids: list[str], excluded: str | None = None,
               window_bounds: tuple[int,int] | None = None) -> dict:
        included=set(tx_ids)
        if excluded is not None:included.remove(excluded)
        transactions=[self.tx_by_id[i] for i in included]
        transactions.sort(key=lambda t:(t["simulation_step"],t["transaction_id"]))
        evidence_ids=[t["transaction_id"] for t in transactions]
        if not transactions:
            return {"priority_score":0.,"risk_factors":[{"name":n,"available":n!="behavioral_deviation",
                "normalized_value":0. if n!="behavioral_deviation" else None,"contribution":0.,"weight":0.,
                "raw_value":{},"transaction_ids":[],"description":"No evidence remains"} for n in BASE_WEIGHTS],
                "alert_statuses":[],"active_detector_types":[],"evidence_count":0}
        statuses=[self._alert_status(self.alert_by_id[aid],included) for aid in sorted(alert_ids)]
        active_types={a["detector"] for a in statuses if a["threshold_met"]}
        strengths=[a["evidence_strength"] for a in statuses if a["threshold_met"] and a["detector"] in ("rapid_pass_through","temporal_cycle")]
        F=max(strengths,default=0.)
        flow_ids=sorted({i for a in statuses if a["threshold_met"] and a["detector"] in ("rapid_pass_through","temporal_cycle") for i in a["remaining_support_ids"]})
        # Freeze the original observation window during a stress test.
        # Removing the earliest/latest edge must not shrink the denominator.
        start,end=(window_bounds if window_bounds is not None else
                   (transactions[0]["simulation_step"],transactions[-1]["simulation_step"]))
        width=end-start+1
        per_step=len(transactions)/width
        V=min(1.0, per_step/3.) # three evidence transfers per native step saturates
        accounts={x for t in transactions for x in (t["source_account"],t["destination_account"])}
        sources=defaultdict(set);sinks=defaultdict(set)
        for t in transactions:
            sources[t["destination_account"]].add(t["source_account"])
            sinks[t["source_account"]].add(t["destination_account"])
        max_branch=max([0]+[len(v) for v in sources.values()]+[len(v) for v in sinks.values()])
        breadth=min(1.,max(0,len(accounts)-2)/5.)
        branching=min(1.,max_branch/5.)
        corroboration=min(1.,max(0,len(active_types)-1)/2.)
        N=.4*breadth+.4*branching+.2*corroboration
        focal={str(a["features"].get("focus_account") or a["features"].get("intermediary_account"))
               for aid in alert_ids for a in [self.alert_by_id[aid]] if a.get("features",{}).get("focus_account") or a.get("features",{}).get("intermediary_account")}
        if not focal:focal=accounts
        B,behavior_raw,behavior_ids=self._baseline(focal,evidence_ids,start,end,excluded)
        factors=[("fund_flow",F,{"active_rapid_or_cycle_alerts":sum(s["threshold_met"] and s["detector"] in ("rapid_pass_through","temporal_cycle") for s in statuses),"best_strength":round(F,6)},flow_ids,
                  "Strongest still-valid rapid onward-flow or time-ordered cycle signal"),
                 ("velocity",V,{"evidence_transactions":len(transactions),"inclusive_step_span":width,"transfers_per_step":round(per_step,6),"saturation":3.},evidence_ids,
                  "Evidence transaction concentration per native simulation step"),
                 ("network_structure",N,{"accounts":len(accounts),"max_distinct_counterparties":max_branch,"active_detector_types":sorted(active_types),
                                           "account_breadth":round(breadth,6),"branching":round(branching,6),"corroboration":round(corroboration,6)},evidence_ids,
                  "Network breadth, branching, and cross-detector corroboration"),
                 ("behavioral_deviation",B,behavior_raw,behavior_ids,
                  "Current focus-account activity compared with earlier simulation-step history")]
        available=sum(BASE_WEIGHTS[name] for name,value,*_ in factors if value is not None)
        result=[]
        for name,value,raw,ids,description in factors:
            weight=BASE_WEIGHTS[name]/available if value is not None else 0.
            pts=round(100*weight*value,2) if value is not None else 0.
            result.append({"name":name,"available":value is not None,"raw_value":raw,
                           "normalized_value":round(value,6) if value is not None else None,
                           "base_weight":BASE_WEIGHTS[name],"weight":round(weight,6),"contribution":pts,
                           "transaction_ids":ids,"description":description})
        score=round(sum(f["contribution"] for f in result),2)
        return {"priority_score":score,"risk_factors":result,"alert_statuses":statuses,
                "active_detector_types":sorted(active_types),"evidence_count":len(transactions)}

    def build_cases(self) -> list[dict]:
        if self.cases:return self.cases
        all_cases=[]
        for cluster in self._build_clusters():
            alert_ids=sorted(cluster["alert_ids"])
            tx_ids=sorted(cluster["tx_ids"],key=lambda i:(self.tx_by_id[i]["simulation_step"],i))
            fingerprint=sha256("\n".join(alert_ids).encode()).hexdigest()[:12].upper()
            scored=self._score(alert_ids,tx_ids)
            detector_types=sorted({self.alert_by_id[i]["detector"] for i in alert_ids})
            active=scored["active_detector_types"]
            case={"case_id":f"CASE-{fingerprint}","alert_ids":alert_ids,
                  "account_ids":sorted(cluster["accounts"]),"transaction_ids":tx_ids,
                  "start_time":None,"end_time":None,"start_step":cluster["start"],"end_step":cluster["end"],"time_unit":"simulation_step",
                  "priority_score":scored["priority_score"],"score_is_probability":False,
                  "risk_factors":scored["risk_factors"],"detector_types":detector_types,
                  "active_detector_types":active,"alert_count":len(alert_ids),"evidence_count":len(tx_ids),
                  "summary":f"Review candidate with {len(alert_ids)} evidence-linked alert(s): {', '.join(detector_types)}; human assessment required.",
                  "grouping_rule":"overlapping evidence or two shared accounts with close simulation steps; bounded cluster",
                  "case_membership_exclusive":True,
                  "indicator_notes":"Heuristic review priority only; components not calibrated; correlated indicators share some evidence."}
            all_cases.append(case)
        all_cases.sort(key=lambda x:(-x["priority_score"],x["start_step"],x["case_id"]))
        self.cases=all_cases
        self.case_by_id={c["case_id"]:c for c in all_cases}
        return self.cases

    def _case(self, case_id:str)->dict:
        if not self.case_by_id:self.build_cases()
        if case_id not in self.case_by_id:raise KeyError(f"Unknown case_id {case_id}")
        return self.case_by_id[case_id]

    def get_cases(self, top_k:int|None=None)->list[dict]:
        cases=self.build_cases()
        if top_k is not None:
            if type(top_k) is not int or top_k<0:raise ValueError("top_k must be a nonnegative integer")
            return cases[:top_k]
        return cases

    def get_case_summaries(self, top_k:int|None=20)->list[dict]:
        """Lightweight ranked rows intended for GET /api/cases and Member C."""
        return [{"case_id":c["case_id"],"priority_score":c["priority_score"],
                 "score_is_probability":False,"alert_count":c["alert_count"],
                 "evidence_count":c["evidence_count"],"start_step":c["start_step"],
                 "end_step":c["end_step"],"time_unit":"simulation_step",
                 "detector_types":c["detector_types"],"summary":c["summary"]}
                for c in self.get_cases(top_k)]

    def case_details(self, case_id:str)->dict:
        case=self._case(case_id)
        rows=sorted((self.tx_by_id[i] for i in case["transaction_ids"]),key=lambda t:(t["simulation_step"],t["transaction_id"]))
        return {**case,"alerts":[self.alert_by_id[i] for i in case["alert_ids"]],"transactions":rows,
                "graph":self.graph(case_id),"timeline":rows}

    def graph(self, case_id:str)->dict:
        case=self._case(case_id)
        return {"case_id":case_id,"nodes":[{"id":acc,"label":acc} for acc in case["account_ids"]],
                "edges":[{"id":i,"transaction_id":i,"source":self.tx_by_id[i]["source_account"],
                          "target":self.tx_by_id[i]["destination_account"],"amount":self.tx_by_id[i]["amount"],
                          "currency":"XXX","simulation_step":self.tx_by_id[i]["simulation_step"]} for i in case["transaction_ids"]],
                "time_unit":"simulation_step"}

    def stress_test(self,case_id:str,excluded_transaction_id:str)->dict:
        case=self._case(case_id)
        if excluded_transaction_id not in case["transaction_ids"]:
            raise ValueError(f"Transaction {excluded_transaction_id} is not evidence in case {case_id}")
        recomputed=self._score(case["alert_ids"],case["transaction_ids"],excluded=excluded_transaction_id,
                               window_bounds=(case["start_step"],case["end_step"]))
        baseline={x["name"]:x for x in case["risk_factors"]}
        after={x["name"]:x for x in recomputed["risk_factors"]}
        changed=[k for k in BASE_WEIGHTS if baseline[k]["normalized_value"]!=after[k]["normalized_value"] or baseline[k]["available"]!=after[k]["available"]]
        status_before={a["alert_id"]:self._alert_status(a,set(case["transaction_ids"])) for a in (self.alert_by_id[i] for i in case["alert_ids"])}
        affected=[s["alert_id"] for s in recomputed["alert_statuses"] if status_before[s["alert_id"]]!=s]
        return {"case_id":case_id,"excluded_transaction_id":excluded_transaction_id,
                "baseline_score":case["priority_score"],"recomputed_score":recomputed["priority_score"],
                "score_difference":round(recomputed["priority_score"]-case["priority_score"],2),
                "changed_factors":changed,"before_factors":case["risk_factors"],"after_factors":recomputed["risk_factors"],
                "affected_alert_ids":affected,"alert_statuses_after":recomputed["alert_statuses"],
                "membership_recomputed":False,"note":"Fixed-membership sensitivity. Recomputed evidence features for the original alerts; did not re-run all Member A detectors or regroup cases. The source dataset and saved case remain unchanged.",
                "time_unit":"simulation_step"}

    def statistics(self)->dict:
        cases=self.build_cases()
        covered=set(i for c in cases for i in c["alert_ids"])
        grouped=sum(len(c["alert_ids"])>1 for c in cases)
        alert_ids=set(self.alert_by_id)
        return {"input_transactions":len(self.transactions),"input_alerts":len(self.alerts),
                "cases":len(cases),"multi_alert_cases":grouped,"single_alert_cases":len(cases)-grouped,
                "max_alerts_in_case":max((c["alert_count"] for c in cases),default=0),
                "max_evidence_transactions_in_case":max((c["evidence_count"] for c in cases),default=0),
                "max_step_span":max((c["end_step"]-c["start_step"] for c in cases),default=0),
                "alerts_assigned_once":sum(c["alert_count"] for c in cases)==len(alert_ids)==len(covered),
                "behavioral_factor_available_cases":sum(next(f for f in c["risk_factors"] if f["name"]=="behavioral_deviation")["available"] for c in cases),
                "top_10_case_evidence_transactions":len({i for c in cases[:10] for i in c["transaction_ids"]}),
                "top_10_baseline_single_alert_evidence_transactions":self._alert_baseline_coverage(10),
                "top_10_comparison_caveat":"DESCRIPTIVE ONLY: 10 cases and 10 alerts have different evidence-review costs. No AML recall/precision lift is claimed.",
                "time_unit":"simulation_step","score_is_probability":False}

    def _alert_baseline_coverage(self,k:int)->int:
        # Descriptive baseline ranked by single-alert evidence size, not AML case-level accuracy.
        ordered=sorted(self.alerts,key=lambda a:(-len(a["transaction_ids"]),a["start_step"],a["alert_id"]))
        return len({tid for a in ordered[:k] for tid in a["transaction_ids"]})


def run_handoff(path:str|Path,config:CaseConfig|None=None)->CaseEngine:
    engine=CaseEngine(load_handoff(path),config)
    engine.build_cases()
    return engine
