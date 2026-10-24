#!/usr/bin/env python3
"""Run the actual IBM sample, without pretending simulation steps are minutes."""
from __future__ import annotations
import argparse
from pathlib import Path
import json
from src.ibm_scenario import run_archive

def main():
    parser=argparse.ArgumentParser(description='Member A: authentic IBM AMLSim 20K example')
    parser.add_argument('--source',type=Path,default=Path('data/20K_fanin200cycle200.tgz'))
    parser.add_argument('--fan-window-steps',type=int,default=4)
    parser.add_argument('--fan-min-counterparties',type=int,default=5)
    parser.add_argument('--rapid-window-steps',type=int,default=3)
    parser.add_argument('--cycles',action='store_true')
    parser.add_argument('--cycle-window-steps',type=int,default=12)
    parser.add_argument('--report',type=Path,default=Path('reports/IBM_20K_verified_run.json'))
    parser.add_argument('--handoff',type=Path,default=Path('examples/member_b_IBM_20K_handoff.json'))
    args=parser.parse_args()
    r=run_archive(args.source,fan_window_steps=args.fan_window_steps,
         fan_min_counterparties=args.fan_min_counterparties,rapid_window_steps=args.rapid_window_steps,
         include_cycles=args.cycles,cycle_window_steps=args.cycle_window_steps)
    report={"source_file":str(args.source),"input_audit":r['audit'],
            "graph":{"nodes":r['graph_node_count'],"edges":r['graph_edge_count']},
            "alert_breakdown":r['alert_breakdown'],"total_alerts":len(r['alerts']),
            "config":r['config'],"runtime_seconds":r['runtime_seconds'],
            "offline_account_level_evaluation":r['account_evaluation'],
            "limitations":["No transaction-level SAR labels or per-scenario mappings are supplied in this archive",
              "Only simulation-step intervals are used: no assumed real-world hours/days",
              "Derived transaction IDs refer to stable source CSV row positions (unchanged archive ordering)",
              "Account-level signal coverage is not case Recall@K or evidence of real-world detection quality",
              "All detectors are heuristic candidates and may flag routine activity"]}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.handoff.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    handoff={"schema_version":"member-a-simulation-step-v1", "dataset_summary":{
       "transactions":len(r['transactions']),"accounts":r['graph_node_count'],"alerts":len(r['alerts']),
       "time_unit":"simulation_step", "currency":"XXX", "all_transaction_ids_derived":True,
       "score_is_probability":False},
       "transactions":[t.to_dict() for t in r['transactions']],"alerts":r['alerts']}
    args.handoff.write_text(json.dumps(handoff,separators=(',',':'))+'\n',encoding='utf-8')
    print(json.dumps({"dataset_transactions":len(r['transactions']),"accounts":r['graph_node_count'],
            "graph_edges":r['graph_edge_count'],"alerts":len(r['alerts']),
            "breakdown":r['alert_breakdown'],"runtime_seconds":r['runtime_seconds'],
            "evaluation":r['account_evaluation']},indent=2))
    print('report:',args.report)
    print('Member 2 label-free handoff:',args.handoff)

if __name__=='__main__':main()
