"""Run full-IBM HTTP API smoke checks without having to open a network port."""
from pathlib import Path
from fastapi.testclient import TestClient
from backend.main import app

with TestClient(app) as client:
    for route in ('/health','/api/meta','/api/summary','/api/cases?limit=3',
                  '/api/cases/CASE-1086856BCDCD',
                  '/api/cases/CASE-1086856BCDCD/graph'):
        response = client.get(route)
        print(f'{response.status_code} GET {route}')
        assert response.status_code==200,response.text
    x=client.post('/api/cases/CASE-1086856BCDCD/stress-test',
                  json={'excluded_transaction_id':'IBM20K-ROW-0005975'})
    assert x.status_code==200,x.text
    data=x.json()
    assert (data['baseline_score'],data['recomputed_score'])==(100.0,95.26)
    print('200 POST stress-test: 100.00 -> 95.26')
    summary=client.get('/api/summary').json()
    assert (summary['transactions'],summary['alerts'],summary['cases'])==(120558,2912,2573)
    print('Verified: 120,558 transactions / 2,912 alerts / 2,573 cases')
    print('ALL BACKEND SMOKE CHECKS PASSED')
