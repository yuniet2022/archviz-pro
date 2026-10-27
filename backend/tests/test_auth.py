import hashlib
import time
import sqlite3

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.services.auth_store import AuthStore, password_matches
from app.core.security_context import owner_id
from app.services.project_repository import ProjectRepository
from app.models.schemas import FloorPlanData, Wall, Vector3, PlanReview

ADMIN_PASSWORD='First-owner-passphrase-2026'
MEMBER_PASSWORD='Initial-member-passphrase-2026'


@pytest.fixture
def accounts(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'PROJECT_DB',str(tmp_path/'private.sqlite3'))
    monkeypatch.setattr(settings,'AUTH_COOKIE_SECURE',False)
    monkeypatch.setattr(settings,'AUTH_PUBLIC_ORIGIN','http://testserver')
    store=AuthStore(settings.PROJECT_DB)
    a=store.create_user('a@example.test','Owner A',ADMIN_PASSWORD,'admin',False,bootstrap=True)
    b=store.create_user('b@example.test','Owner B',MEMBER_PASSWORD,'member',False)
    return store,a,b


def signed_in(email,password):
    client=TestClient(app)
    response=client.post('/api/v1/auth/login',json={'email':email,'password':password})
    assert response.status_code==200,response.text
    client.headers['X-CSRF-Token']=response.json()['csrf_token']
    return client,response


def model():
    return FloorPlanData(walls=[Wall(start=Vector3(),end=Vector3(x=4))])


def create_project(account,reviewed=False):
    token=owner_id.set(account['id'])
    try:
        repo=ProjectRepository(settings.PROJECT_DB)
        project=repo.create('same-source','{}','json',model())
        if reviewed:
            project=repo.review(project['project_id'],PlanReview(base_revision=0,floor_plan=model(),approved=True,measurements_confirmed=True,allow_learning=True))
        return repo,project
    finally:owner_id.reset(token)


def test_anonymous_cannot_read_write_download_or_claim_first_administrator(accounts):
    _,a,_=accounts
    _,project=create_project(a)
    pid=project['project_id'];client=TestClient(app)
    for path in [f'/plans/{pid}',f'/plans/{pid}/sources',f'/plans/{pid}/archive',f'/plans/{pid}/export/archviz','/plans','/plans/learning/dataset','/furnish/catalog','/auth/users']:
        assert client.get('/api/v1'+path).status_code==401,path
    assert client.put(f'/api/v1/plans/{pid}/review',json={}).status_code==401
    assert client.post('/api/v1/auth/users',json={}).status_code==401
    assert client.post('/api/v1/auth/register',json={}).status_code==401
    assert client.get('/exports/old-private-file.pdf').status_code==404
    assert set(client.get('/api/v1/plans/learning/status').json())=={'mode','release'}
    assert client.get('/health').status_code==200


def test_login_cookies_csrf_rotation_logout_and_expiry(accounts):
    store,a,_=accounts
    client,response=signed_in(a['email'],ADMIN_PASSWORD)
    cookie=response.headers['set-cookie']
    assert 'HttpOnly' in cookie and 'SameSite=lax' in cookie
    token=client.cookies.get('archviz_session')
    with store.connection() as db:
        digest=db.execute('SELECT digest FROM auth_sessions').fetchone()[0]
        assert digest==hashlib.sha256(token.encode()).hexdigest() and digest!=token
    assert client.get('/api/v1/plans').status_code==200
    csrf=client.headers.pop('X-CSRF-Token')
    assert client.post('/api/v1/auth/logout').status_code==403
    client.headers['X-CSRF-Token']=csrf
    assert client.post('/api/v1/auth/logout',headers={'Origin':'https://evil.test'}).status_code==403
    assert client.post('/api/v1/auth/logout').status_code==200
    assert store.session(token) is None
    client.cookies.set('archviz_session',token)
    assert client.get('/api/v1/plans').status_code==401
    client,_=signed_in(a['email'],ADMIN_PASSWORD)
    with store.connection() as db:db.execute('UPDATE auth_sessions SET expires_at=?',(time.time()-1,))
    assert client.get('/api/v1/plans').status_code==401


def test_other_user_cannot_access_any_project_route_even_if_admin(accounts):
    store,a,b=accounts
    repo,project=create_project(b,reviewed=True);pid=project['project_id']
    source=repo.add_source(pid,'private.pdf','hash','original',b'secret')[0]
    aclient,_=signed_in(a['email'],ADMIN_PASSWORD)
    for path in [f'/plans/{pid}',f'/plans/{pid}/sources',f'/plans/{pid}/archive',
                 f'/plans/{pid}/export/{"archviz"}',f'/plans/{pid}/export/json',
                 f'/plans/{pid}/export/dxf',f'/plans/{pid}/export/svg',
                 f'/plans/{pid}/sources/{source["id"]}/inspect',f'/plans/{pid}/sources/{source["id"]}/preview']:
        assert aclient.get('/api/v1'+path).status_code==404,path
    assert aclient.put(f'/api/v1/plans/{pid}/review',json={'base_revision':1,'floor_plan':model().model_dump()}).status_code==404
    assert aclient.delete(f'/api/v1/plans/{pid}/learning').status_code==404
    assert aclient.post(f'/api/v1/plans/{pid}/sources',files={'file':('x.pdf',b'hello','application/pdf')}).status_code==404
    assert aclient.patch(f'/api/v1/plans/{pid}/sources/{source["id"]}',json={'page':1}).status_code==404
    assert aclient.post('/api/v1/furnish/fixtures',json={'project_id':pid,'floor_plan':model().model_dump()}).status_code==404
    assert aclient.post('/api/v1/roofs/preview',json={'project_id':pid,'source_id':source['id'],'settings':{},'floor_plan':model().model_dump()}).status_code==404
    assert aclient.get('/api/v1/plans').json()['projects']==[]
    assert aclient.get('/api/v1/plans/learning/dataset').text==''
    assert aclient.get('/api/v1/plans/learning/status').json()['approved_examples']==0
    context=owner_id.set(a['id'])
    try:
        own=ProjectRepository(settings.PROJECT_DB).create('same-source','{}','json',model())
        assert own['learning']['reused'] is False
    finally:owner_id.reset(context)
    bclient,_=signed_in(b['email'],MEMBER_PASSWORD)
    assert bclient.get(f'/api/v1/plans/{pid}').status_code==200
    assert len(bclient.get('/api/v1/plans').json()['projects'])==1
    assert bclient.get('/api/v1/auth/users').status_code==403


def test_legacy_projects_only_assigned_by_explicit_local_bootstrap(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'PROJECT_DB',str(tmp_path/'legacy.sqlite3'))
    repo=ProjectRepository(settings.PROJECT_DB)
    legacy=repo.create('legacy','{}','json',model());pid=legacy['project_id'];before=repo.get(pid)
    store=AuthStore(settings.PROJECT_DB)
    first=store.create_user('owner@example.test','Owner',ADMIN_PASSWORD,'admin',False,bootstrap=True,claim_legacy=True)
    assert first['claimed_projects']==1
    assert repo.get(pid)==before
    context=owner_id.set(first['id'])
    try:assert ProjectRepository(settings.PROJECT_DB).get(pid)==before
    finally:owner_id.reset(context)
    with pytest.raises(ValueError,match='Ya existe'):
        store.create_user('attacker@example.test','Visitor',ADMIN_PASSWORD,'admin',False,bootstrap=True,claim_legacy=True)


def test_admin_created_accounts_change_temporary_password_and_disable_revokes_sessions(accounts):
    store,a,b=accounts
    admin,_=signed_in(a['email'],ADMIN_PASSWORD)
    response=admin.post('/api/v1/auth/users',json={'email':'new@example.test','name':'New account','password':MEMBER_PASSWORD})
    assert response.status_code==201,response.text
    new=response.json()['user'];assert new['must_change']
    member,_=signed_in(new['email'],MEMBER_PASSWORD)
    assert member.get('/api/v1/plans').status_code==403
    assert member.post('/api/v1/auth/password',json={'current_password':'wrong','new_password':'A-new-personal-password-2026'}).status_code==400
    assert member.post('/api/v1/auth/password',json={'current_password':MEMBER_PASSWORD,'new_password':'A-new-personal-password-2026'}).status_code==200
    assert member.get('/api/v1/plans').status_code==401
    assert member.post('/api/v1/auth/login',json={'email':new['email'],'password':MEMBER_PASSWORD}).status_code==401
    member,_=signed_in(new['email'],'A-new-personal-password-2026')
    assert member.get('/api/v1/plans').status_code==200
    assert admin.patch(f'/api/v1/auth/users/{new["id"]}',json={'active':False}).status_code==200
    assert member.get('/api/v1/plans').status_code==401
    assert member.post('/api/v1/auth/login',json={'email':new['email'],'password':'A-new-personal-password-2026'}).status_code==401
    assert admin.patch(f'/api/v1/auth/users/{a["id"]}',json={'active':False}).status_code==400


def test_password_hash_login_throttle_and_generic_invalid_credentials(accounts):
    store,a,b=accounts
    with store.connection() as db:
        encoded=db.execute('SELECT password_hash FROM auth_users WHERE id=?',(a['id'],)).fetchone()[0]
    assert ADMIN_PASSWORD not in encoded and password_matches(ADMIN_PASSWORD,encoded)
    client=TestClient(app)
    wrong=client.post('/api/v1/auth/login',json={'email':a['email'],'password':'wrong'})
    missing=client.post('/api/v1/auth/login',json={'email':'absent@example.test','password':'wrong'})
    assert wrong.json()==missing.json() and wrong.status_code==missing.status_code==401
    for _ in range(7):assert client.post('/api/v1/auth/login',json={'email':a['email'],'password':'wrong'}).status_code==401
    assert client.post('/api/v1/auth/login',json={'email':a['email'],'password':ADMIN_PASSWORD}).status_code==429


def test_public_http_never_accepts_login_and_secure_cookie_on_https(accounts,monkeypatch):
    _,a,_=accounts
    monkeypatch.setattr(settings,'AUTH_COOKIE_SECURE',True)
    monkeypatch.setattr(settings,'AUTH_PUBLIC_ORIGIN','https://app.example.test')
    client=TestClient(app,base_url='http://app.example.test')
    assert client.get('/api/v1/auth/session').json()['login_available'] is False
    assert client.post('/api/v1/auth/login',json={'email':a['email'],'password':ADMIN_PASSWORD}).status_code==503
    secure=TestClient(app,base_url='https://app.example.test')
    result=secure.post('/api/v1/auth/login',json={'email':a['email'],'password':ADMIN_PASSWORD},headers={'Origin':'https://app.example.test'})
    assert result.status_code==200,result.text
    assert 'Secure' in result.headers['set-cookie'] and result.headers['Strict-Transport-Security']
    monkeypatch.setattr(settings,'AUTH_COOKIE_SECURE',False)
    assert client.get('/api/v1/auth/session').json()['login_available'] is False


def test_console_bootstrap_claims_legacy_and_recovery_does_not_echo_passwords(tmp_path,monkeypatch,capsys):
    from app import manage
    monkeypatch.setattr(settings,'PROJECT_DB',str(tmp_path/'console.sqlite3'))
    legacy=ProjectRepository(settings.PROJECT_DB).create('legacy','{}','json',model())
    monkeypatch.setattr(manage.sys.stdin,'isatty',lambda:True)
    passwords=iter([ADMIN_PASSWORD,ADMIN_PASSWORD])
    monkeypatch.setattr(manage.getpass,'getpass',lambda prompt:next(passwords))
    monkeypatch.setattr(manage.sys,'argv',['manage','bootstrap-admin','--email','operator@example.test','--claim-legacy'])
    manage.main()
    store=AuthStore(settings.PROJECT_DB);operator=store.user_by_email('operator@example.test')
    session,_=store.new_session(operator['id'],12)
    replacement='Recovered-personal-password-2026'
    passwords=iter([replacement,replacement])
    monkeypatch.setattr(manage.getpass,'getpass',lambda prompt:next(passwords))
    monkeypatch.setattr(manage.sys,'argv',['manage','reset-password','--email','operator@example.test'])
    manage.main()
    assert store.session(session) is None
    assert store.login(operator['email'],replacement)
    assert ProjectRepository(settings.PROJECT_DB).get(legacy['project_id'])==legacy
    output=capsys.readouterr().out
    assert ADMIN_PASSWORD not in output and replacement not in output


def test_password_reset_revokes_an_inflight_old_password_login(accounts,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from app.services import auth_store
    store,a,_=accounts
    entered=Event();release=Event();real_matches=auth_store.password_matches
    def verifying(password,encoded):
        entered.set()
        assert release.wait(5)
        return real_matches(password,encoded)
    monkeypatch.setattr(auth_store,'password_matches',verifying)
    with ThreadPoolExecutor(max_workers=2) as pool:
        login=pool.submit(store.sign_in,a['email'],ADMIN_PASSWORD,12)
        assert entered.wait(5)
        reset=pool.submit(store.reset_password,a['id'],'Replacement-passphrase-2026')
        release.set()
        result=login.result(timeout=10)
        reset.result(timeout=10)
    assert result is not None
    assert store.session(result[1]) is None


def test_real_client_rate_limit_address_only_trusted_behind_local_proxy():
    from starlette.requests import Request
    from app.core.auth import client_address,effective_scheme
    def request(address):
        return Request({'type':'http','method':'POST','scheme':'http','path':'/api/v1/auth/login',
                        'headers':[(b'x-real-ip',b'206.189.206.211'),(b'x-forwarded-proto',b'https')],
                        'client':(address,1234),'server':('app.example.test',80),'query_string':b''})
    assert client_address(request('172.18.0.2'))=='206.189.206.211'
    assert effective_scheme(request('172.18.0.2'))=='https'
    assert client_address(request('8.8.8.8'))=='8.8.8.8'
    assert effective_scheme(request('8.8.8.8'))=='http'


def test_console_password_validation_never_displays_entered_password(tmp_path,monkeypatch):
    from app import manage
    monkeypatch.setattr(settings,'PROJECT_DB',str(tmp_path/'validation.sqlite3'))
    monkeypatch.setattr(manage.sys.stdin,'isatty',lambda:True)
    monkeypatch.setattr(manage.getpass,'getpass',lambda prompt:'weak-pw')
    monkeypatch.setattr(manage.sys,'argv',['manage','bootstrap-admin','--email','operator@example.test'])
    with pytest.raises(ValueError) as error:manage.main()
    assert 'weak-pw' not in str(error.value)
    assert 'input_value' not in str(error.value)
