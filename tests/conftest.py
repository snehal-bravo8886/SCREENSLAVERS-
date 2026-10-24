from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.main import create_app, DEFAULT_SEED, DEFAULT_ARCHIVE

@pytest.fixture(scope='session')
def client(tmp_path_factory):
    upload_dir = tmp_path_factory.mktemp('uploads')
    app=create_app(seed_path=DEFAULT_SEED,archive_path=DEFAULT_ARCHIVE,upload_dir=upload_dir)
    with TestClient(app) as c:
        yield c

@pytest.fixture
def working_client(tmp_path):
    app=create_app(seed_path=DEFAULT_SEED,archive_path=DEFAULT_ARCHIVE,upload_dir=tmp_path/'uploads')
    with TestClient(app) as c:
        yield c
