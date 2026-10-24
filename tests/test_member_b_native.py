import copy
import json
from pathlib import Path
import pytest

from member_b import CaseConfig, CaseEngine, load_handoff

ROOT=Path(__file__).resolve().parents[1]
SMALL=ROOT/'examples'/'member_a_small_handoff.json'

def tx(i,u,v,step,amount=100):
    return {"transaction_id":f'T{i}',"source_account":u,"destination_account":v,"amount":amount,
            "currency":"XXX","timestamp":None,"simulation_step":step,"time_unit":"simulation_step","id_is_derived":True}

def alert(i,kind,ids,transactions,focus=None):
    by={t['transaction_id']:t for t in transactions}
    ts=[by[j] for j in ids]
    ac=sorted({a for t in ts for a in (t['source_account'],t['destination_account'])})
    feat={}
    if focus is not None:feat['focus_account']=focus
    if kind=='rapid_pass_through':feat['intermediary_account']=ts[0]['destination_account']
    return {"alert_id":f'DET-TEST-{i:06d}',"detector":kind,"account_ids":ac,"transaction_ids":ids,
            "start_step":min(t['simulation_step'] for t in ts),"end_step":max(t['simulation_step'] for t in ts),
            "start_time":None,"end_time":None,"time_unit":"simulation_step","features":feat,"reason":"Synthetic test case only"}

def payload(t,a):return {"schema_version":"member-a-simulation-step-v1","dataset_summary":{},"transactions":t,"alerts":a}

def basic():
    t=[tx(1,'A','B',20,100),tx(2,'C','B',20,100),tx(3,'D','B',21,100),
       tx(4,'E','B',21,100),tx(5,'F','B',22,100),tx(6,'B','G',23,85)]
    a=[alert(1,'fan_in',['T1','T2','T3','T4','T5'],t,'B'),
       alert(2,'rapid_pass_through',['T5','T6'],t)]
    return payload(t,a)

def test_small_real_source_handoff_valid():
    d=load_handoff(SMALL)
    assert d['dataset_summary']['alerts']==4
    e=CaseEngine(d)
    assert e.statistics()['alerts_assigned_once']
    assert len(e.cases)==2

def test_evidence_overlap_creates_case():
    e=CaseEngine(basic());cs=e.build_cases()
    assert len(cs)==1 and cs[0]['alert_count']==2
    assert len(cs[0]['transaction_ids'])==6
    assert set(cs[0]['detector_types'])=={'fan_in','rapid_pass_through'}

def test_no_alerts_means_no_cases():
    e=CaseEngine(payload([tx(1,'A','B',0)],[]))
    assert e.build_cases()==[] and e.statistics()['cases']==0

def test_disjoint_suspicious_patterns_do_not_merge():
    t=[tx(1,'A','B',0),tx(2,'B','C',1),tx(3,'D','E',0),tx(4,'E','F',1)]
    a=[alert(1,'rapid_pass_through',['T1','T2'],t),alert(2,'rapid_pass_through',['T3','T4'],t)]
    assert len(CaseEngine(payload(t,a)).build_cases())==2

def test_shared_single_account_not_sufficient():
    t=[tx(1,'A','B',20),tx(2,'B','C',21),tx(3,'B','D',20),tx(4,'D','E',21)]
    a=[alert(1,'rapid_pass_through',['T1','T2'],t),alert(2,'rapid_pass_through',['T3','T4'],t)]
    assert len(CaseEngine(payload(t,a)).build_cases())==2

def test_time_cap_prevents_distant_merge():
    t=[tx(1,'A','B',0),tx(2,'B','C',1),tx(3,'A','B',60),tx(4,'B','D',61)]
    a=[alert(1,'rapid_pass_through',['T1','T2'],t),alert(2,'rapid_pass_through',['T3','T4'],t)]
    # Even though both share accounts, no merge across widely separated steps
    assert len(CaseEngine(payload(t,a)).build_cases())==2

def test_case_id_invariant_to_input_order():
    d=basic();e1=CaseEngine(d);c1=e1.build_cases()
    d2=copy.deepcopy(d);d2['transactions'].reverse();d2['alerts'].reverse()
    e2=CaseEngine(d2);c2=e2.build_cases()
    assert c1==c2

def test_id_stability_with_additional_unrelated_alert():
    d=basic();c1=CaseEngine(d).build_cases()[0]['case_id']
    d['transactions']+=[tx(10,'Z','Y',50),tx(11,'Y','X',51)]
    d['alerts']+=[alert(10,'rapid_pass_through',['T10','T11'],d['transactions'])]
    assert c1 in [c['case_id'] for c in CaseEngine(d).build_cases()]

def test_score_0_to_100_contributions_reconcile():
    e=CaseEngine(basic());cases=e.build_cases()
    for c in cases:
        assert 0<=c['priority_score']<=100
        assert c['score_is_probability'] is False
        assert round(sum(f['contribution'] for f in c['risk_factors']),2)==c['priority_score']
        assert all(set(f['transaction_ids'])<=set(c['transaction_ids']) for f in c['risk_factors'])

def test_missing_history_remains_unavailable_and_reweighted():
    t=[tx(1,'A','B',1,100),tx(2,'B','C',2,85)]
    e=CaseEngine(payload(t,[alert(1,'rapid_pass_through',['T1','T2'],t)]))
    c=e.build_cases()[0]
    by={f['name']:f for f in c['risk_factors']}
    assert by['behavioral_deviation']['available'] is False
    assert by['behavioral_deviation']['normalized_value'] is None
    assert abs(sum(f['weight'] for f in c['risk_factors'])-1)<1e-5

def test_no_future_data_in_history():
    d=basic();e1=CaseEngine(copy.deepcopy(d));c1=e1.build_cases()[0]
    # Add future activity after the case's last step; it cannot modify the score.
    d['transactions'] += [tx(8,'B','J',90),tx(9,'J','B',91),tx(10,'B','K',92)]
    e2=CaseEngine(d);c2=e2.build_cases()[0]
    assert c1['priority_score']==c2['priority_score']
    assert c1['risk_factors']==c2['risk_factors']

def test_stress_removes_temporarily_and_recomputes_alert_status():
    e=CaseEngine(basic());c=e.build_cases()[0];start=e.case_details(c['case_id'])
    stress=e.stress_test(c['case_id'],'T5')
    assert stress['membership_recomputed'] is False
    assert stress['recomputed_score']!=stress['baseline_score']
    assert stress['changed_factors']
    assert 'DET-TEST-000002' in stress['affected_alert_ids']
    assert start==e.case_details(c['case_id'])
    assert e.stress_test(c['case_id'],'T5')==stress

def test_stress_uses_original_window_for_early_edge():
    e=CaseEngine(basic());c=e.build_cases()[0]
    baseline=next(f for f in c['risk_factors'] if f['name']=='velocity')
    s=e.stress_test(c['case_id'],'T1')
    after=next(f for f in s['after_factors'] if f['name']=='velocity')
    assert after['raw_value']['inclusive_step_span']==baseline['raw_value']['inclusive_step_span']
    assert after['raw_value']['evidence_transactions']==baseline['raw_value']['evidence_transactions']-1

def test_stress_rejects_non_evidence_transaction():
    e=CaseEngine(basic());c=e.build_cases()[0]
    with pytest.raises(ValueError):e.stress_test(c['case_id'],'TOTALLY-UNKNOWN')

def test_graph_links_all_source_evidence():
    e=CaseEngine(basic());c=e.build_cases()[0];g=e.graph(c['case_id'])
    assert {i['transaction_id'] for i in g['edges']}==set(c['transaction_ids'])
    assert {x['id'] for x in g['nodes']}==set(c['account_ids'])
    assert all(i['source'] in set(c['account_ids']) and i['target'] in set(c['account_ids']) for i in g['edges'])

def test_label_leakage_top_level_nested():
    d=basic();d['private_labels']={'A':1}
    with pytest.raises(ValueError,match='labels'):CaseEngine(d)
    d=basic();d['alerts'][0]['features']['fraudStep']=1
    with pytest.raises(ValueError,match='labels'):CaseEngine(d)
    d=basic();d['dataset_summary']['isFraud']={'A':1}
    with pytest.raises(ValueError,match='labels'):CaseEngine(d)

def test_reject_duplicate_ids_missing_evidence_and_bad_step():
    d=basic();d['transactions'].append(copy.deepcopy(d['transactions'][0]))
    with pytest.raises(ValueError):CaseEngine(d)
    d=basic();d['alerts'][0]['transaction_ids'].append('MISSING')
    with pytest.raises(ValueError):CaseEngine(d)
    d=basic();d['alerts'][0]['start_step']=999
    with pytest.raises(ValueError):CaseEngine(d)

def test_reject_nan_and_infinity_amounts():
    for value in (float('inf'),float('nan'),0,-1):
        d=basic();d['transactions'][0]['amount']=value
        with pytest.raises(ValueError):CaseEngine(d)

def test_reject_clock_time_assumption():
    d=basic();d['transactions'][0]['timestamp']='2026-10-23T10:00:00Z'
    with pytest.raises(ValueError):CaseEngine(d)

def test_reject_unknown_detector():
    d=basic();d['alerts'][0]['detector']='AI_PROVEN_FRAUD'
    with pytest.raises(ValueError):CaseEngine(d)

def test_unknown_case_and_invalid_limit():
    e=CaseEngine(basic());e.build_cases()
    with pytest.raises(KeyError):e.graph('MISSING')
    with pytest.raises(ValueError):e.get_cases(top_k=-1)

def test_stress_does_not_invent_evidence():
    e=CaseEngine(basic());c=e.build_cases()[0]
    s=e.stress_test(c['case_id'],'T6')
    expected=set(c['transaction_ids'])-{'T6'}
    assert all(set(f['transaction_ids'])<=expected for f in s['after_factors'])

def test_historical_factor_absent_without_enough_earlier_records():
    d=basic();e=CaseEngine(d);c=e.build_cases()[0]
    assert next(f for f in c['risk_factors'] if f['name']=='behavioral_deviation')['available'] is False

def test_full_cases_cover_all_alerts_once_for_small():
    e=CaseEngine(load_handoff(SMALL));c=e.build_cases()
    assert sorted(i for cc in c for i in cc['alert_ids'])==sorted(a['alert_id'] for a in e.alerts)
    assert max(cc['end_step']-cc['start_step'] for cc in c)<=12

def test_details_includes_evidence_and_timeline():
    e=CaseEngine(basic());c=e.build_cases()[0]
    details=e.case_details(c['case_id'])
    assert len(details['transactions'])==len(c['transaction_ids'])
    assert details['timeline']==details['transactions']
    assert {a['alert_id'] for a in details['alerts']}==set(c['alert_ids'])


def test_queue_summaries_lightweight_and_sorted():
    e=CaseEngine(basic());c=e.build_cases()
    summaries=e.get_case_summaries(1)
    assert len(summaries)==1 and summaries[0]['case_id']==c[0]['case_id']
    assert 'risk_factors' not in summaries[0]
    assert summaries[0]['score_is_probability'] is False


def test_complete_real_ibm_handoff_smoke():
    """Actual 120,558-row source and 2,912 alerts; no constructed mock outputs."""
    source=ROOT/'data'/'member_a_IBM_20K_handoff.json'
    if not source.exists():pytest.skip('Full data not installed')
    e=CaseEngine(load_handoff(source));cases=e.build_cases()
    assert len(e.transactions)==120558 and len(e.alerts)==2912
    assert e.statistics()['alerts_assigned_once']
    assert all(c['end_step']-c['start_step']<=12 and c['alert_count']<=7 for c in cases)
    assert all(c['score_is_probability'] is False for c in cases)
    for c in cases[:10]:
        assert set(c['transaction_ids'])<=e.tx_by_id.keys()
        assert round(sum(f['contribution'] for f in c['risk_factors']),2)==c['priority_score']
        s=e.stress_test(c['case_id'],c['transaction_ids'][0])
        assert s['membership_recomputed'] is False
        assert e.case_by_id[c['case_id']]==c
