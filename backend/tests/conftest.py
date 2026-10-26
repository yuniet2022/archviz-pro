import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).parents[1]))
_data = tempfile.TemporaryDirectory(prefix='archviz-tests-')
for name, subdir in [('UPLOAD_DIR','uploads'),('EXPORT_DIR','exports'),('VIDEO_OUTPUT_DIR','videos'),('XDG_CACHE_HOME','cache')]:
    os.environ[name] = str(Path(_data.name)/subdir)
os.environ['PROJECT_DB'] = str(Path(_data.name)/'projects.sqlite3')

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'PROJECT_DB', str(tmp_path/'projects.sqlite3'))
    monkeypatch.setattr(settings,'AUTH_COOKIE_SECURE',False)
    monkeypatch.setattr(settings,'AUTH_PUBLIC_ORIGIN','http://testserver')
    from app.services.auth_store import AuthStore
    from app.core.security_context import owner_id
    account=AuthStore(settings.PROJECT_DB).create_user('architect@example.test','Architect','Testing-only-password-2026','admin',False)
    context=owner_id.set(account['id'])
    with TestClient(app) as client:
        response=client.post('/api/v1/auth/login',json={'email':account['email'],'password':'Testing-only-password-2026'})
        assert response.status_code==200,response.text
        client.headers['X-CSRF-Token']=response.json()['csrf_token']
        try:yield client
        finally:owner_id.reset(context)
