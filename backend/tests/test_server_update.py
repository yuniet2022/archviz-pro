import argparse
import importlib.util
import json
from pathlib import Path
import pytest


def updater():
    script=Path(__file__).parents[2]/'scripts/server_update.py'
    spec=importlib.util.spec_from_file_location('server_update_guard',script)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_preparation_refuses_to_overwrite_an_active_release(tmp_path, monkeypatch):
    module=updater()
    state=tmp_path/'deployment.state.json'
    state.write_text(json.dumps({'activated':True}))
    monkeypatch.setattr(module,'STATE',state)
    with pytest.raises(ValueError,match='activa'):
        module.prepare(argparse.Namespace(base=str(tmp_path/'old'),backup=str(tmp_path/'backup')))


def test_normalized_release_preserves_credentials_mounts_and_other_services(tmp_path):
    module=updater()
    original={'services':{
        'backend':{'environment':{'DATABASE_URL':'test$$literal'},'networks':{'old':None},
            'volumes':[{'type':'bind','source':'/old/app','target':'/app/app'},
                       {'type':'bind','source':'/old/uploads','target':'/app/uploads'}]},
        'nginx':{'depends_on':{'backend':{'condition':'service_started'}},'networks':{'old':None}},
        'frontend':{'volumes':[{'type':'bind','source':'/stale','target':'/usr/share/nginx/html'}],
                    'ports':[{'target':80,'published':'3000'}],'profiles':['builder'],
                    'build':{'context':'/old/frontend','target':'builder'}},
        'worker':{'image':'original-worker','environment':{'CUSTOM':'keep$$exact'}},
        'db':{'image':'postgres','environment':{'PASSWORD':'test$$value'}}},
        'networks':{'old':{'name':'old-network'}}}
    saved=json.loads(json.dumps(original))
    result=module.release_model(original,module.build_override(tmp_path/'old',tmp_path/'candidate','test'))
    assert original==saved
    assert result['services']['db']==original['services']['db']
    assert result['services']['worker']==original['services']['worker']
    assert result['services']['backend']['environment']['DATABASE_URL']=='test$$literal'
    mounts={item['target']:item['source'] for item in result['services']['backend']['volumes']}
    assert mounts['/app/uploads']=='/old/uploads'
    assert mounts['/app/app']==str(tmp_path/'candidate/backend/app')
    assert result['services']['nginx']['depends_on']['backend']['condition']=='service_healthy'
    assert result['networks']['old']==original['networks']['old']
    for key in ('volumes','ports','profiles'):
        assert key not in result['services']['frontend']
    assert 'target' not in result['services']['frontend']['build']


def test_resolved_configuration_is_private_and_never_printed(tmp_path, capsys):
    module=updater();path=tmp_path/'deployment.compose.json'
    path.write_text('old');path.chmod(0o644)
    data={'environment':{'PRIVATE_VALUE':'test$$value'}}
    module.private_json(path,data)
    assert path.stat().st_mode & 0o777 == 0o600
    assert json.loads(path.read_text())==data
    assert capsys.readouterr().out==''


def test_activation_rejects_changed_resolved_configuration(tmp_path):
    module=updater();path=tmp_path/'deployment.compose.json';path.write_text('{}')
    state={'ready':True,'release_config':str(path),'release_config_sha256':'wrong'}
    with pytest.raises(ValueError,match='configuración preparada'):
        module.activate(state,'http://127.0.0.1')


def test_preparation_checks_disable_tty_for_piped_input(tmp_path, monkeypatch):
    module=updater()
    base=tmp_path/'existing';candidate=tmp_path/'candidate';backup=tmp_path/'backup'
    for root in (base,candidate):
        (root/'backend/app/services').mkdir(parents=True)
    backup.mkdir()
    for name in ('aplicacion.tar.gz','base-de-datos.sql'):
        (backup/name).write_bytes(b'backup')
    (base/'docker-compose.yml').write_text('{}')
    (base/'nginx.conf').write_text('events {}')
    engine=base/'backend/app/services/vector_engine.py'
    engine.write_text('# original engine\n')
    monkeypatch.setattr(module,'CANDIDATE',candidate)
    monkeypatch.setattr(module,'STATE',candidate/'deployment.state.json')
    monkeypatch.setattr(module,'compose_cli',lambda:['docker-compose'])
    checks=[]

    def compose_call(command, **kwargs):
        if 'config' in command and '--format' in command:
            return json.dumps({'services':{'backend':{},'nginx':{}}})
        if 'run' in command:
            options=command[command.index('run')+1:]
            assert '-T' in options, 'Compose would require a TTY with piped stdin'
            assert '--rm' in options and '--no-deps' in options
            assert kwargs.get('stdin')==module.subprocess.DEVNULL, 'Compose must not consume the activation command from a pasted bash script'
            checks.append(options)
            return b'<html>compiled frontend</html>'

    monkeypatch.setattr(module.subprocess,'run',compose_call)
    monkeypatch.setattr(module.subprocess,'check_output',compose_call)
    module.prepare(argparse.Namespace(base=str(base),backup=str(backup),
                                      project='archviz-test',prepare_only=False))
    state=json.loads(module.STATE.read_text())
    assert state['ready'] is True
    assert state['activated'] is False
    assert len(checks)==2
    assert 'backend' in checks[0] and 'frontend' in checks[1]
    assert (candidate/'backend/app/services/vector_engine.py').read_bytes()==engine.read_bytes()
