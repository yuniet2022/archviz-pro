import argparse
import importlib.util
import json
from pathlib import Path
import pytest


def test_preparation_refuses_to_overwrite_an_active_release(tmp_path, monkeypatch):
    script=Path(__file__).parents[2]/'scripts/server_update.py'
    spec=importlib.util.spec_from_file_location('server_update_guard',script)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    state=tmp_path/'deployment.state.json'
    state.write_text(json.dumps({'activated':True}))
    monkeypatch.setattr(module,'STATE',state)
    with pytest.raises(ValueError,match='activa'):
        module.prepare(argparse.Namespace(base=str(tmp_path/'old'),backup=str(tmp_path/'backup')))
