"""Independent regression checks for actual archived IBM schema + native simulation time."""
import io
import json
import tarfile
from pathlib import Path

import pytest

from src.ibm_scenario import (
    StepTransaction, build_graph, detect_fan, detect_rapid, detect_three_cycles,
    ingest_archive, run_archive, evaluate_account_signal_coverage,
)


def tx(i, a, b, amount, step):
    return StepTransaction(f"E{i}",str(a),str(b),float(amount),step)


def make_archive(path, tx_text, nodes_text, metadata="nodes: 3 (2 fraud nodes)\ntransactions: 2\n"):
    with tarfile.open(path,"w:gz") as tgz:
        for name, text in {"transactions.csv":tx_text,"nodes.csv":nodes_text,"metadata.txt":metadata}.items():
            raw=text.encode()
            info=tarfile.TarInfo(name="sample/"+name)
            info.size=len(raw)
            tgz.addfile(info,io.BytesIO(raw))


def test_archive_real_schema_and_label_partition(tmp_path):
    path=tmp_path/'archive.tgz'
    make_archive(path,"sourceNodeId,targetNodeId,value,time\n1,2,100.4,1\n1,2,100.4,1\n",
                 "nodeid,isFraud,init_balance,fraudStep\n1,1,200.0,1\n2,0,300.0,-1\n3,1,100.0,1\n")
    rows, labels, audit=ingest_archive(path)
    assert len(rows)==2
    assert [r.transaction_id for r in rows]==["IBM20K-ROW-0000001","IBM20K-ROW-0000002"]
    assert rows[0].simulation_step==1
    assert rows[0].to_dict()['timestamp'] is None
    assert 'isFraud' not in json.dumps([r.to_dict() for r in rows])
    assert labels=={'1':1,'2':0,'3':1}
    graph=build_graph(rows)
    assert graph.number_of_edges()==2
    assert graph.number_of_nodes()==2
    assert audit['transactions_with_source_ids']==0


def test_sequential_fan_and_no_same_step_rapid():
    samples=[tx(1,'1','9',100,1),tx(2,'2','9',100,1),tx(3,'3','9',100,2),tx(4,'9','8',90,2)]
    fan=detect_fan(samples,'in',window_steps=1,min_counterparties=3)
    assert len(fan)==1 and set(fan[0]['transaction_ids'])=={'E1','E2','E3'}
    rapid=detect_rapid(samples,window_steps=2)
    assert len(rapid)==1
    assert rapid[0]['transaction_ids']==['E2','E4']  # most recent eligible ID under deterministic tie-break
    assert rapid[0]['features']['elapsed_steps']==1
    assert rapid[0]['start_time'] is None


def test_one_inflow_not_reused():
    samples=[tx(1,'1','2',100,1),tx(2,'2','3',90,2),tx(3,'2','4',85,3)]
    alerts=detect_rapid(samples,window_steps=3)
    assert len(alerts)==1
    assert alerts[0]['transaction_ids']==['E1','E2']


def test_three_cycle_time_order_required():
    sample=[tx(1,'1','2',100,1),tx(2,'2','3',99,2),tx(3,'3','1',98,3)]
    assert len(detect_three_cycles(sample,window_steps=4))==1
    same_step=[tx(1,'1','2',100,1),tx(2,'2','3',99,1),tx(3,'3','1',98,1)]
    assert not detect_three_cycles(same_step,window_steps=4)


def test_window_units_not_minutes():
    assert StepTransaction('E1','1','2',12.0,7).to_dict()['time_unit']=='simulation_step'
    assert 'minutes' not in str(detect_fan([tx(1,1,2,1,1),tx(2,3,2,1,3)],'in',window_steps=4,min_counterparties=2))


def test_wrong_schema_fails(tmp_path):
    path=tmp_path/'bad.tgz'
    make_archive(path,'from,to,amount,timestamp\na,b,1,1\n',
                 'nodeid,isFraud,init_balance,fraudStep\n1,0,5,-1\n')
    with pytest.raises(ValueError,match='Unexpected IBM archive schema'):
        ingest_archive(path)


def test_unknown_node_and_invalid_currency_fails(tmp_path):
    path=tmp_path/'missing-node.tgz'
    make_archive(path,'sourceNodeId,targetNodeId,value,time\n1,8,100,2\n',
                 'nodeid,isFraud,init_balance,fraudStep\n1,0,5,-1\n')
    with pytest.raises(ValueError,match='missing in nodes.csv'):
        ingest_archive(path)


def test_no_label_dependent_detection():
    arr=[tx(1,1,9,100,1),tx(2,2,9,100,1),tx(3,3,9,100,2),tx(4,9,8,90,3)]
    original=detect_fan(arr,'in',window_steps=3,min_counterparties=3)
    for labels in ({'9':1,'8':0},{'9':0,'8':1}):
        _=evaluate_account_signal_coverage(original,labels,{})
        assert detect_fan(arr,'in',window_steps=3,min_counterparties=3)==original


def test_real_ibm_archive_smoke():
    path=Path(__file__).parent.parent/'data'/'20K_fanin200cycle200.tgz'
    if not path.exists():pytest.skip('Archive not present')
    txs,_,audit=ingest_archive(path)
    assert len(txs)==120558
    assert audit['accounts_in_nodes_file']==20000
    assert audit['source_columns']==['sourceNodeId','targetNodeId','value','time']
    assert audit['simulation_step_max']==149
    assert audit['account_labels_flagged']==1804
    graph=build_graph(txs)
    assert graph.number_of_edges()==len(txs)
    assert graph.number_of_nodes()==19980


def test_versioned_contract_validation():
    from src.ibm_schemas import IBMStepTransaction, IBMStepAlert
    t=tx(1,'1','2',100,1).to_dict()
    assert IBMStepTransaction.model_validate(t).simulation_step==1
    from src.ibm_scenario import _new_alert
    alert=_new_alert('PASS',1,'rapid_pass_through',['1','2'],['E1'],1,2,{},'Candidate')
    assert IBMStepAlert.model_validate(alert).time_unit=='simulation_step'
    with pytest.raises(Exception):
        IBMStepTransaction.model_validate({**t,'timestamp':'2026-01-01T00:00:00Z'})
