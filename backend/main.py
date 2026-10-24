"""FastAPI application — production-shaped local hackathon MVP, not a deployed bank system."""
from __future__ import annotations
from contextlib import asynccontextmanager
from pathlib import Path
from hashlib import sha256
import os
import uuid

from fastapi import FastAPI, UploadFile, File, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.concurrency import run_in_threadpool

from backend.contracts import AnalysisRequest, ReviewStatusRequest, StressTestRequest
from backend.service import Registry, ApiFault, MAX_UPLOAD_BYTES, safe_archive_check
from src.ibm_scenario import ingest_archive

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SEED = ROOT / 'data' / 'member_a_IBM_20K_handoff.json'
DEFAULT_ARCHIVE = ROOT / 'data' / '20K_fanin200cycle200.tgz'


def create_app(*, seed_path: Path = DEFAULT_SEED, archive_path: Path = DEFAULT_ARCHIVE,
               upload_dir: Path | None = None) -> FastAPI:
    store = Registry(seed_path, archive_path, upload_dir or ROOT / 'runtime' / 'uploads')

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await run_in_threadpool(app.state.registry.startup)
        yield

    app = FastAPI(title='Screenslavers Investigator API', version='1.0.0', lifespan=lifespan,
      description='Explainable investigation candidate workflows on IBM AMLSim native simulation steps; NOT fraud probability.')
    app.state.registry = store
    raw_origins = os.getenv('SCREENSLAVERS_CORS_ORIGINS',
        'http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000')
    origins = [v.strip() for v in raw_origins.split(',') if v.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=['GET','POST','PATCH'],
                       allow_headers=['Content-Type'], allow_credentials=False)

    @app.exception_handler(ApiFault)
    async def api_fault_handler(request: Request, exc: ApiFault):
        del request
        return JSONResponse(status_code=exc.code, content={'error':exc.message})

    @app.get('/health', tags=['Health'])
    def health():
        _, summary = store.current()
        return {'status':'ok','ready':True,'run_id':summary['run_id'],
                'data':'IBM AMLSim synthetic','time_unit':'simulation_step'}

    @app.get('/api/meta', tags=['Metadata'])
    def meta():
        return {'product':'Screenslavers', 'api_version':'1.0.0',
                'time_unit':'simulation_step', 'clock_time_available':False,
                'currency':'XXX', 'currency_label':'unspecified synthetic monetary unit',
                'score_name':'Investigation priority index (0-100)',
                'score_is_probability':False,
                'score_version':'context_evidence_v2_heuristic',
                'priority_weights':{'pattern_strength':0.45,'activity_anomaly':0.35,'evidence_support':0.20},
                'score_formula':'P = 100 * (0.45*M + 0.35*A + 0.20*C)',
                'score_accuracy':'Not measured; account-level evaluation labels are withheld from scoring.',
                'stress_test_mode':'fixed_membership_evidence_sensitivity',
                'input_schema_version':'member-a-simulation-step-v1',
                'endpoints': ['/api/summary','/api/cases','/api/cases/{case_id}',
                              '/api/cases/{case_id}/graph','/api/cases/{case_id}/timeline',
                              '/api/cases/{case_id}/stress-test',
                              '/api/cases/{case_id}/review']}

    @app.get('/api/summary', tags=['Metadata'])
    def summary():
        return store.current()[1]

    @app.get('/api/datasets/current', tags=['Dataset'])
    def dataset_status():
        return store.dataset_status()

    @app.post('/api/datasets/load', tags=['Dataset'], status_code=202)
    async def dataset_load(file: UploadFile = File(...)):
        filename = file.filename or ''
        if not (filename.lower().endswith('.tgz') or filename.lower().endswith('.tar.gz')):
            raise ApiFault(415, 'Only IBM AMLSim .tgz or .tar.gz archives are supported')
        store.upload_dir.mkdir(parents=True, exist_ok=True)
        dest = store.upload_dir / f'uploaded-{uuid.uuid4().hex}.tgz'
        digest = sha256()
        length = 0
        try:
            with dest.open('wb') as fp:
                while chunk := await file.read(1024*1024):
                    length += len(chunk)
                    if length > MAX_UPLOAD_BYTES:
                        raise ApiFault(413,'Archive exceeds maximum compressed size of 10 MiB')
                    digest.update(chunk)
                    fp.write(chunk)
            await run_in_threadpool(safe_archive_check, dest)
            # Reuse the final Module A importer to reject malformed source content.
            # Account-level labels returned here are discarded, never served over HTTP.
            try:
                await run_in_threadpool(ingest_archive, dest)
            except (ValueError, OSError) as exc:
                raise ApiFault(400, f"IBM archive data failed validation: {exc}") from exc
            return store.stage_upload(dest,digest.hexdigest())
        except Exception:
            dest.unlink(missing_ok=True)
            raise
        finally:
            await file.close()

    @app.post('/api/analyze', tags=['Dataset'])
    async def analyze(body: AnalysisRequest | None = None):
        return await run_in_threadpool(store.analyze, include_cycles=(body.include_cycles if body else True))

    @app.get('/api/cases', tags=['Cases'])
    def list_cases(limit: int = Query(default=20,ge=1,le=100),
                   offset: int = Query(default=0,ge=0),
                   min_priority: float = Query(default=0,ge=0,le=100),
                   detector: str | None = Query(default=None),
                   search: str | None = Query(default=None,max_length=128),
                   review_status: str = Query(default='all')):
        engine, sm = store.current()
        if detector is not None and detector not in ('fan_in','fan_out','rapid_pass_through','temporal_cycle'):
            raise ApiFault(422, 'Unknown detector filter')
        if review_status not in ('all', 'to_do', 'in_progress', 'done'):
            raise ApiFault(422, 'Unknown review status filter')
        statuses = store.review_statuses(sm['run_id'])
        all_items = engine.get_case_summaries(top_k=None)
        if min_priority:
            all_items = [c for c in all_items if c['priority_score'] >= min_priority]
        if detector:
            all_items = [c for c in all_items if detector in c['detector_types']]
        if search:
            needle = search.strip().lower()
            # Limit search to case ID; full graph-wide search is not silently performed.
            all_items = [c for c in all_items if needle in c['case_id'].lower()]
        if review_status != 'all':
            all_items = [c for c in all_items if statuses.get(c['case_id'], 'to_do') == review_status]
        total = len(all_items)
        page = all_items[offset:offset+limit]
        for item in page:
            item['review_status'] = statuses.get(item['case_id'], 'to_do')
        counts = {'to_do': 0, 'in_progress': 0, 'done': 0}
        counts['to_do'] = sm['cases'] - sum(status in ('in_progress', 'done') for status in statuses.values())
        counts['in_progress'] = sum(status == 'in_progress' for status in statuses.values())
        counts['done'] = sum(status == 'done' for status in statuses.values())
        return {'run_id':sm['run_id'],'items':page,
                'total':total,'limit':limit,'offset':offset,
                'review_counts':counts,
                'time_unit':'simulation_step','score_is_probability':False}

    def require_case(case_id:str):
        engine,_=store.current()
        try:
            return engine, engine._case(case_id)
        except KeyError:
            raise ApiFault(404,'Unknown investigation case') from None

    @app.get('/api/cases/{case_id}', tags=['Cases'])
    def case_details(case_id: str):
        engine, summary = store.current()
        try:
            detail = engine.case_details(case_id)
        except KeyError:
            raise ApiFault(404,'Unknown investigation case') from None
        detail['review_status'] = store.review_statuses(summary['run_id']).get(case_id, 'to_do')
        return detail

    @app.patch('/api/cases/{case_id}/review', tags=['Cases'])
    def update_case_review(case_id: str, body: ReviewStatusRequest):
        require_case(case_id)
        _, summary = store.current()
        updated_at = store.set_review_status(summary['run_id'], case_id, body.status)
        return {'run_id': summary['run_id'], 'case_id': case_id,
                'status': body.status, 'updated_at': updated_at}

    @app.get('/api/cases/{case_id}/graph', tags=['Cases'])
    def case_graph(case_id: str):
        engine,_=require_case(case_id)
        return engine.graph(case_id)

    @app.get('/api/cases/{case_id}/timeline', tags=['Cases'])
    def case_timeline(case_id: str):
        engine,_=require_case(case_id)
        case=engine._case(case_id)
        return {'case_id':case_id,'time_unit':'simulation_step',
                'items':[engine.tx_by_id[i] for i in case['transaction_ids']]}

    @app.post('/api/cases/{case_id}/stress-test', tags=['Cases'])
    def case_stress(case_id: str, body: StressTestRequest):
        engine,case = require_case(case_id)
        if (body.excluded_transaction_id is None) == (body.excluded_transaction_ids is None):
            raise ApiFault(422,'Provide either one excluded transaction or a list of excluded transactions')
        transaction_ids = ([body.excluded_transaction_id] if body.excluded_transaction_id is not None
                           else body.excluded_transaction_ids)
        if len(transaction_ids) != len(set(transaction_ids)):
            raise ApiFault(422,'Excluded transaction IDs must be unique')
        if not set(transaction_ids).issubset(case['transaction_ids']):
            raise ApiFault(422,'Every excluded transaction must be evidence in this case')
        return engine.stress_test(case_id, transaction_ids)

    @app.get('/api/transactions/{transaction_id}', tags=['Evidence'])
    def transaction(transaction_id: str):
        engine,_=store.current()
        if transaction_id not in engine.tx_by_id:
            raise ApiFault(404,'Unknown transaction ID')
        return engine.tx_by_id[transaction_id]

    @app.get('/api/alerts/{alert_id}', tags=['Evidence'])
    def alert(alert_id: str):
        engine,_=store.current()
        if alert_id not in engine.alert_by_id:
            raise ApiFault(404,'Unknown alert ID')
        alert = engine.alert_by_id[alert_id]
        return {'alert':alert,
                'transactions':[engine.tx_by_id[x] for x in alert['transaction_ids']]}

    return app

app = create_app()
