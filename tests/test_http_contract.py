"""API-level contract tests over actual Module A/B final handoff."""
from collections import Counter
from fastapi.testclient import TestClient
from backend.main import DEFAULT_ARCHIVE, DEFAULT_SEED, create_app


def test_health_is_real(client):
    r=client.get('/health');assert r.status_code==200
    assert r.json()['status']=='ok'
    assert r.json()['time_unit']=='simulation_step'


def test_summary_matches_verified_execution(client):
    p=client.get('/api/summary').json()
    assert (p['transactions'],p['alerts'],p['cases'])==(120558,2912,2573)
    assert p['alert_breakdown']=={'fan_in':680,'fan_out':100,'rapid_pass_through':2110,'temporal_cycle':22}
    assert p['score_is_probability'] is False
    assert p['currency']=='XXX'


def test_case_queue_pagination_is_stable(client):
    a=client.get('/api/cases?limit=5&offset=0').json()
    b=client.get('/api/cases?limit=5&offset=5').json()
    assert a['total']==2573
    assert len(a['items'])==len(b['items'])==5
    assert a['items'][0]['priority_score']>=a['items'][1]['priority_score']
    assert {r['case_id'] for r in a['items']}.isdisjoint({r['case_id'] for r in b['items']})
    assert all(c['score_is_probability'] is False for c in a['items'])


def test_case_details_include_live_evidence(client):
    case_id=client.get('/api/cases').json()['items'][0]['case_id']
    detail=client.get(f'/api/cases/{case_id}').json()
    assert detail['case_id']==case_id
    assert 0<=detail['priority_score']<=100
    assert detail['score_components']['priority_score']==detail['priority_score']
    assert detail['time_unit']=='simulation_step'
    assert detail['start_time'] is None
    assert detail['end_time'] is None
    assert len(detail['alerts'])==7
    assert detail['evidence_count']==len(detail['transactions'])
    assert len(detail['graph']['edges'])==detail['evidence_count']
    assert len(detail['timeline'])==detail['evidence_count']
    assert set(detail['transaction_ids'])=={x['transaction_id'] for x in detail['transactions']}


def test_graph_contains_directed_evidence_edges(client):
    case_id=client.get('/api/cases').json()['items'][0]['case_id']
    graph=client.get(f'/api/cases/{case_id}/graph').json()
    nodes={x['id'] for x in graph['nodes']}
    for e in graph['edges']:
        assert e['source'] in nodes and e['target'] in nodes
        assert e['transaction_id']==e['id']
        assert isinstance(e['simulation_step'],int)
    assert graph['time_unit']=='simulation_step'


def test_timeline_matches_detail(client):
    case_id=client.get('/api/cases').json()['items'][0]['case_id']
    d=client.get(f'/api/cases/{case_id}').json()
    p=client.get(f'/api/cases/{case_id}/timeline').json()
    assert p['items']==d['timeline']


def test_live_stress_test_changes_score_but_not_case(client):
    case_id='CASE-1086856BCDCD'
    before=client.get(f'/api/cases/{case_id}').json()
    tid='IBM20K-ROW-0005975'
    r=client.post(f'/api/cases/{case_id}/stress-test',json={'excluded_transaction_id':tid})
    assert r.status_code==200,r.text
    x=r.json()
    assert x['membership_recomputed'] is False
    assert x['baseline_score']==before['priority_score']
    assert x['recomputed_score']<x['baseline_score']
    assert x['score_difference']==round(x['recomputed_score']-x['baseline_score'],2)
    assert x['baseline_score_components']==before['score_components']
    assert x['recomputed_score_components']['priority_score']==x['recomputed_score']
    assert set(x['recomputed_score_components']) >= {'M','A','C','weighted_total','priority_score'}
    assert len(x['after_factors'])==len(x['before_factors'])
    after=client.get(f'/api/cases/{case_id}').json()
    assert after==before


def test_live_stress_test_accepts_flagged_pattern_transactions(client):
    case_id='CASE-1086856BCDCD'
    before=client.get(f'/api/cases/{case_id}').json()
    transaction_ids=before['alerts'][0]['transaction_ids']
    r=client.post(f'/api/cases/{case_id}/stress-test',json={'excluded_transaction_ids':transaction_ids})
    assert r.status_code==200,r.text
    result=r.json()
    assert result['excluded_transaction_ids']==transaction_ids
    assert result['excluded_transaction_id'] is None
    assert result['membership_recomputed'] is False
    assert result['baseline_score']==before['priority_score']
    assert result['recomputed_score_components']['priority_score']==result['recomputed_score']
    assert set(result['recomputed_score_components']) >= {'M','A','C','weighted_total','priority_score'}
    assert len(result['after_factors'])==len(result['before_factors'])
    assert client.get(f'/api/cases/{case_id}').json()==before


def test_transactions_and_alerts_have_full_traceability(client):
    detail=client.get('/api/cases/CASE-1086856BCDCD').json()
    tid=detail['transaction_ids'][0]
    a_id=detail['alert_ids'][0]
    assert client.get(f'/api/transactions/{tid}').json()['transaction_id']==tid
    alert=client.get(f'/api/alerts/{a_id}').json()
    assert alert['alert']['alert_id']==a_id
    assert {t['transaction_id'] for t in alert['transactions']}==set(alert['alert']['transaction_ids'])


def test_search_and_filters(client):
    p=client.get('/api/cases?limit=100&detector=temporal_cycle&min_priority=20').json()
    assert p['total']>0
    assert all('temporal_cycle' in c['detector_types'] and c['priority_score']>=20 for c in p['items'])
    s=client.get('/api/cases?search=CASE-1086856BCDCD').json()
    assert s['total']==1 and s['items'][0]['case_id']=='CASE-1086856BCDCD'
    assert client.get('/api/cases?search=unknownid').json()['total']==0


def test_correct_http_errors(client):
    assert client.get('/api/cases/UNKNOWN').status_code==404
    assert client.get('/api/cases/UNKNOWN/graph').status_code==404
    assert client.get('/api/transactions/UNKNOWN').status_code==404
    assert client.get('/api/alerts/UNKNOWN').status_code==404
    assert client.get('/api/cases?limit=101').status_code==422
    assert client.get('/api/cases?offset=-1').status_code==422
    assert client.get('/api/cases?detector=unknown').status_code==422
    assert client.post('/api/cases/CASE-1086856BCDCD/stress-test',json={'excluded_transaction_id':'NOPE'}).status_code==422
    assert client.post('/api/cases/CASE-1086856BCDCD/stress-test',json={'excluded_transaction_ids':['NOPE']}).status_code==422
    assert client.post('/api/cases/CASE-1086856BCDCD/stress-test',json={'excluded_transaction_ids':['IBM20K-ROW-0005975']*2}).status_code==422
    assert client.post('/api/cases/CASE-1086856BCDCD/stress-test',json={'excluded_transaction_id':'IBM20K-ROW-0005975','excluded_transaction_ids':['IBM20K-ROW-0005975']}).status_code==422
    assert client.post('/api/cases/CASE-1086856BCDCD/stress-test',json={}).status_code==422
    assert client.post('/api/cases/UNKNOWN/stress-test',json={'excluded_transaction_id':'anything'}).status_code==404


def test_cors_preflight_for_local_react(client):
    r=client.options('/api/cases',headers={
       'Origin':'http://localhost:5173', 'Access-Control-Request-Method':'GET'})
    assert r.status_code==200
    assert r.headers['access-control-allow-origin']=='http://localhost:5173'


def test_meta_teaches_frontend_source_units(client):
    m=client.get('/api/meta').json()
    assert m['clock_time_available'] is False
    assert m['score_is_probability'] is False
    assert m['stress_test_mode']=='fixed_membership_evidence_sensitivity'
    assert m['score_formula']=='P = 100 * (0.45*M + 0.35*A + 0.20*C)'
    assert m['score_version']=='context_evidence_v2_heuristic'
    assert m['score_accuracy'].startswith('Not measured')


def test_review_status_is_shared_persisted_and_filterable(working_client):
    case_id='CASE-1086856BCDCD'
    response=working_client.patch(f'/api/cases/{case_id}/review',json={'status':'in_progress'})
    assert response.status_code==200
    assert response.json()['status']=='in_progress'

    upload_dir=working_client.app.state.registry.upload_dir
    shared_app=create_app(seed_path=DEFAULT_SEED,archive_path=DEFAULT_ARCHIVE,upload_dir=upload_dir)
    with TestClient(shared_app) as second_client:
        detail=second_client.get(f'/api/cases/{case_id}').json()
        assert detail['review_status']=='in_progress'
        queue=second_client.get('/api/cases?review_status=in_progress').json()
        assert queue['total']==1
        assert queue['items'][0]['case_id']==case_id
        assert queue['review_counts']['in_progress']==1
        assert queue['review_counts']['to_do']==2572

    assert working_client.patch(f'/api/cases/{case_id}/review',json={'status':'invalid'}).status_code==422
    assert working_client.patch('/api/cases/UNKNOWN/review',json={'status':'done'}).status_code==404
    assert working_client.get('/api/cases?review_status=unknown').status_code==422


def test_no_label_keys_in_api_response(client):
    keys=('"isFraud"','"fraudStep"','"private_labels"','"ground_truth"')
    routes=['/api/summary','/api/cases','/api/cases/CASE-1086856BCDCD','/api/meta']
    for route in routes:
        content=client.get(route).text
        assert all(k not in content for k in keys)
