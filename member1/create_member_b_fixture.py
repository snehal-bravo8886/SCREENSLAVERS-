"""Derive a smaller, LABEL-FREE practice handoff from genuine archive rows.

Choose overlapping alerts to exercise Member B merging, plus bounded preceding
transaction history for featured accounts. Do not use it for benchmark metrics.
"""
import json
from pathlib import Path
from collections import defaultdict

def main():
    full=Path('examples/member_b_IBM_20K_handoff.json')
    data=json.loads(full.read_text(encoding='utf-8'))
    by_id={a['alert_id']:a for a in data['alerts']}
    intended=['DET-FANIN-000001','DET-FANOUT-000043','DET-PASS-000902','DET-FANIN-000002']
    selected=[by_id[i] for i in intended]
    evidence={i for a in selected for i in a['transaction_ids']}
    accounts={i for a in selected for i in a['account_ids']}
    low=min(a['start_step'] for a in selected)-20
    high=max(a['end_step'] for a in selected)
    rows=[t for t in data['transactions']
          if t['transaction_id'] in evidence or
          (low<=t['simulation_step']<=high and (
              t['source_account'] in accounts or t['destination_account'] in accounts))]
    assert evidence.issubset({t['transaction_id'] for t in rows})
    small={'schema_version':data['schema_version'],
           'dataset_summary':{'transactions':len(rows),'accounts':len({x for t in rows for x in (t['source_account'],t['destination_account'])}),
                               'alerts':len(selected),'time_unit':'simulation_step','currency':'XXX','all_transaction_ids_derived':True,
                               'score_is_probability':False},
           'transactions':rows,'alerts':selected}
    target=Path('examples/member_b_small_real_data_fixture.json')
    target.write_text(json.dumps(small,indent=2)+'\n',encoding='utf-8')
    print('Created source-derived (NOT evaluation) subset',len(rows),'transactions',len(selected),'alerts:',target)

if __name__=='__main__':main()
