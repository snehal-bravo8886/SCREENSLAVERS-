#!/usr/bin/env python3
"""Read the *actual exported file* and independently verify Member B contract + evidence."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from src.ibm_schemas import IBMStepTransaction, IBMStepAlert

FORBIDDEN = {"isFraud", "is_sar", "fraudStep", "init_balance", "evaluation_labels", "source_alert_id", "source_alert_type"}


def verify(path: Path):
    data=json.loads(path.read_text(encoding='utf-8'))
    assert data['schema_version']=='member-a-simulation-step-v1', 'Schema version mismatch'
    assert not any(k in data for k in FORBIDDEN)
    txs={}
    for record in data['transactions']:
        assert not FORBIDDEN.intersection(record), 'Evaluation label present in transaction handoff'
        tx=IBMStepTransaction.model_validate(record)
        assert tx.transaction_id not in txs, 'Duplicate transaction ID in handoff'
        txs[tx.transaction_id]=tx
    alerts_seen=set()
    counts=Counter()
    for raw in data['alerts']:
        assert not FORBIDDEN.intersection(raw), 'Evaluation label present in alert handoff'
        a=IBMStepAlert.model_validate(raw)
        assert a.alert_id not in alerts_seen, 'Duplicate alert ID'
        alerts_seen.add(a.alert_id)
        assert len(set(a.transaction_ids))==len(a.transaction_ids), 'Duplicated evidence within alert'
        assert all(tid in txs for tid in a.transaction_ids), 'Missing transaction evidence'
        evidence=[txs[tid] for tid in a.transaction_ids]
        assert min(t.simulation_step for t in evidence)==a.start_step
        assert max(t.simulation_step for t in evidence)==a.end_step
        accounts={x for t in evidence for x in (t.source_account,t.destination_account)}
        assert set(a.account_ids)==accounts, 'Alert accounts differ from cited evidence'
        counts[a.detector]+=1
    assert data['dataset_summary']['transactions']==len(txs)
    assert data['dataset_summary']['alerts']==len(alerts_seen)
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    return {'passed':True,'source_file':str(path),'handoff_sha256':digest,
            'transactions_validated':len(txs),'alerts_validated':len(alerts_seen),
            'alert_breakdown':dict(sorted(counts.items())),
            'every_transaction_id_unique':True,'every_alert_id_unique':True,
            'every_evidence_id_exists':True,'every_alert_matches_evidence_accounts_and_step_range':True,
            'no_evaluation_fields_in_public_handoff':True,
            'timestamp_units':'native simulation steps, with timestamp=null'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('--report',type=Path,default=Path('reports/handoff_validation.json'))
    a=p.parse_args();result=verify(a.source);a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
