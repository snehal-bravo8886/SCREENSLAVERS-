import io
import tarfile
import hashlib
from pathlib import Path
from backend.service import safe_archive_check, ApiFault, BASELINE_HANDOFF_SHA256
from backend.main import DEFAULT_ARCHIVE, DEFAULT_SEED


def _tar_bytes(entries):
    out=io.BytesIO()
    with tarfile.open(fileobj=out,mode='w:gz') as t:
        for name,contents in entries:
            raw=contents.encode()
            info=tarfile.TarInfo(name)
            info.size=len(raw)
            t.addfile(info,io.BytesIO(raw))
    return out.getvalue()


def test_baseline_checksum_genuine_and_verified():
    assert hashlib.sha256(DEFAULT_SEED.read_bytes()).hexdigest()==BASELINE_HANDOFF_SHA256
    safe_archive_check(DEFAULT_ARCHIVE)


def test_dataset_status_at_boot(client):
    d=client.get('/api/datasets/current').json()
    assert d['ready'] is True
    assert d['pending_upload'] is None
    assert d['active_source']=='verified_module_a_handoff'


def test_reject_wrong_extension(working_client):
    r=working_client.post('/api/datasets/load',files={'file':('notes.txt',b'hi','text/plain')})
    assert r.status_code==415
    assert working_client.get('/api/summary').json()['cases']==2573


def test_reject_corrupt_archive(working_client):
    r=working_client.post('/api/datasets/load',files={'file':('fake.tgz',b'not an archive','application/gzip')})
    assert r.status_code==400
    assert working_client.get('/api/datasets/current').json()['pending_upload'] is None


def test_reject_archive_missing_required_files(working_client):
    blob=_tar_bytes([('notes.txt','hi')])
    r=working_client.post('/api/datasets/load',files={'file':('wrong.tgz',blob,'application/gzip')})
    assert r.status_code==400
    assert 'transactions.csv' in r.text


def test_reject_archive_wrong_schema(working_client):
    blob=_tar_bytes([('transactions.csv','hi\n1\n'),('nodes.csv','a\n2\n'),('metadata.txt','x')])
    r=working_client.post('/api/datasets/load',files={'file':('wrong.tgz',blob,'application/gzip')})
    assert r.status_code==400 or r.status_code==422
    assert working_client.get('/api/summary').json()['cases']==2573


def test_reject_large_archive_by_stream(working_client):
    payload=b'x'*(10*1024*1024+1)
    r=working_client.post('/api/datasets/load',files={'file':('oversize.tgz',payload,'application/gzip')})
    assert r.status_code==413


def test_real_archive_upload_and_reanalysis(working_client):
    with DEFAULT_ARCHIVE.open('rb') as fp:
        r=working_client.post('/api/datasets/load',files={'file':('20K_fanin200cycle200.tgz',fp,'application/gzip')})
    assert r.status_code==202,r.text
    assert r.json()['requires_analyze'] is True
    # The active result is not changed by a staged upload alone.
    assert working_client.get('/api/summary').json()['source']=='verified_module_a_handoff'
    p=working_client.post('/api/analyze',json={'include_cycles':True})
    assert p.status_code==200,p.text
    s=p.json()
    assert (s['transactions'],s['alerts'],s['cases'])==(120558,2912,2573)
    assert s['source']=='archive_reanalysis'
    assert working_client.get('/api/cases').json()['items'][0]['case_id']=='CASE-1086856BCDCD'


def test_analysis_disabled_cycles_outputs_different_candidate_set(working_client):
    r=working_client.post('/api/analyze',json={'include_cycles':False})
    assert r.status_code==200,r.text
    data=r.json()
    assert data['alerts']==2890
    assert data['alert_breakdown'].get('temporal_cycle',0)==0
    assert data['cases']>0
    assert data['score_is_probability'] is False


def test_analysis_bad_request_rejected_without_changes(working_client):
    before=working_client.get('/api/summary').json()
    r=working_client.post('/api/analyze',json={'include_cycles':'maybe'})
    assert r.status_code==422
    assert working_client.get('/api/summary').json()==before


def test_reject_link_member_in_tar(working_client):
    out=io.BytesIO()
    with tarfile.open(fileobj=out,mode='w:gz') as tar:
        info=tarfile.TarInfo('archive/transactions.csv')
        info.type=tarfile.SYMTYPE
        info.linkname='../something'
        tar.addfile(info)
        for name in ('nodes.csv','metadata.txt'):
            raw=b'x'
            e=tarfile.TarInfo('archive/'+name);e.size=len(raw)
            tar.addfile(e,io.BytesIO(raw))
    r=working_client.post('/api/datasets/load', files={'file':('unsafe.tgz',out.getvalue(),'application/gzip')})
    assert r.status_code==400
    assert 'unsupported links' in r.text


def test_duplicate_archive_member_names_rejected(working_client):
    blob=_tar_bytes([('one/transactions.csv','data'),('two/transactions.csv','data'),
                     ('nodes.csv','nodes'),('metadata.txt','metadata')])
    r=working_client.post('/api/datasets/load',files={'file':('dupe.tgz',blob,'application/gzip')})
    assert r.status_code==400
    assert 'Duplicate' in r.text


def test_failed_reanalysis_does_not_erase_current_cases(working_client,monkeypatch):
    import backend.service as service
    baseline=working_client.get('/api/summary').json()
    def fail_run(*args, **kwargs):
        raise ValueError('test-only failed reanalysis')
    with monkeypatch.context() as m:
        m.setattr(service,'run_archive',fail_run)
        r=working_client.post('/api/analyze',json={'include_cycles':True})
        assert r.status_code==400
        assert 'failed validation' in r.text
    assert working_client.get('/api/summary').json()==baseline
    assert working_client.get('/api/cases?limit=1').json()['items'][0]['case_id']=='CASE-1086856BCDCD'
