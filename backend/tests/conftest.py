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
    with TestClient(app) as client:
        yield client
