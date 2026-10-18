#!/usr/bin/env python3
"""Stage a release beside an existing Compose installation; activate explicitly."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.request


CANDIDATE = Path(__file__).resolve().parents[1]
STATE = CANDIDATE/'deployment.state.json'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compose_cli():
    if shutil.which('docker-compose'):
        return ['docker-compose']
    subprocess.run(['docker','compose','version'], check=True, stdout=subprocess.DEVNULL)
    return ['docker','compose']


def build_override(base, candidate, tag):
    def mount(source, target, readonly=False):
        return {'type':'bind','source':str(source),'target':target,'read_only':readonly}
    volumes = [mount(candidate/'backend/app','/app/app',True),mount(base/'data','/app/data')]
    if (base/'pipeline').is_dir():
        volumes.append(mount(base/'pipeline','/app/pipeline',True))
    return {
        'services': {
            'backend': {
                'image':'archviz-update-backend:'+tag,
                'build':{'context':str(candidate/'backend'),'dockerfile':'Dockerfile'},
                'entrypoint':[],
                'command':['python','-m','uvicorn','app.main:app','--host','0.0.0.0','--port','8000'],
                'volumes':volumes,
                'environment':{'PROJECT_DB':'/app/data/projects.sqlite3','APP_RELEASE_ID':tag},
                'networks':['archviz-update'],
                'healthcheck':{'test':['CMD','python','-c',
                    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=2).read()"],
                    'interval':'5s','timeout':'3s','start_period':'15s','retries':6},
            },
            'frontend': {
                'image':'archviz-update-frontend:'+tag,
                'build':{'context':str(candidate/'frontend'),'dockerfile':'Dockerfile'},
                'entrypoint':['/docker-entrypoint.sh'],
                'command':['nginx','-g','daemon off;'],
                'networks':['archviz-update'],
            },
            'nginx': {
                'volumes':[mount(candidate/'nginx.conf','/etc/nginx/nginx.conf',True)],
                'networks':['archviz-update'],
                'depends_on':{'backend':{'condition':'service_healthy'},'frontend':{'condition':'service_started'}},
            },
        },
        'networks':{'archviz-update':{'driver':'bridge'}},
    }


def commands(state):
    old = state['compose']+['-p',state['project'],'-f',str(Path(state['base'])/'docker-compose.yml')]
    return old, old+['-f',str(CANDIDATE/'deployment.override.json')]


def save(state):
    STATE.write_text(json.dumps(state,indent=2)+'\n')
    STATE.chmod(0o600)


def prepare(args):
    if STATE.is_file() and json.loads(STATE.read_text()).get('activated'):
        raise ValueError('Esta carpeta ya contiene la versión activa. Prepara la siguiente actualización en otra carpeta.')
    base = Path(args.base).resolve()
    backup = Path(args.backup).resolve()
    if CANDIDATE == base or CANDIDATE in base.parents or base in CANDIDATE.parents:
        raise ValueError('La actualización debe estar fuera de la instalación activa.')
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*',args.project):
        raise ValueError('Nombre de proyecto Compose inválido.')
    for name in ('aplicacion.tar.gz','base-de-datos.sql'):
        if not (backup/name).is_file() or (backup/name).stat().st_size == 0:
            raise ValueError('No se encontró el respaldo: '+str(backup/name))
    for path in (base/'docker-compose.yml',base/'nginx.conf',base/'backend/app/services/vector_engine.py'):
        if not path.is_file():
            raise ValueError('Falta un archivo de la instalación actual: '+str(path))
    # Preserve the exact server version, including any changes since it was inspected.
    shutil.copy2(base/'backend/app/services/vector_engine.py',CANDIDATE/'backend/app/services/vector_engine.py')
    (base/'data').mkdir(exist_ok=True)
    tag=datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
    state = {'base':str(base),'backup':str(backup),'project':args.project,'compose':compose_cli(),
             'engine_sha256':digest(base/'backend/app/services/vector_engine.py'),
             'compose_sha256':digest(base/'docker-compose.yml'),'nginx_sha256':digest(base/'nginx.conf'),
             'ready':False,'activated':False,'tag':tag}
    override=CANDIDATE/'deployment.override.json'
    override.write_text(json.dumps(build_override(base,CANDIDATE,tag),indent=2)+'\n')
    override.chmod(0o600)
    old, release = commands(state)
    subprocess.run(old+['config','--quiet'],check=True)
    services=subprocess.check_output(old+['config','--services'],text=True).split()
    if not {'backend','nginx'}.issubset(services):
        raise ValueError('La instalación no tiene los servicios backend y nginx esperados.')
    subprocess.run(release+['config','--quiet'],check=True)
    save(state)
    if args.prepare_only:
        print('Configuración preparada; todavía no se han construido las imágenes ni activado la actualización.')
        return
    # Sequential builds reduce memory pressure on the 2 GB server.
    subprocess.run(release+['build','backend'],check=True)
    subprocess.run(release+['build','frontend'],check=True)
    subprocess.run(release+['run','--rm','--no-deps','backend','python','-c',
        'import fitz; from app.services.vector_engine import VectorEngine; '
        'from app.main import app; assert callable(VectorEngine().process_pdf); '
        'print("Motor vectorial y API compatibles: OK")'],check=True)
    index=subprocess.check_output(release+['run','--rm','--no-deps','frontend','cat','/usr/share/nginx/html/index.html'])
    state['frontend_index_sha256']=hashlib.sha256(index).hexdigest()
    state['ready']=True
    save(state)
    print('PREPARACIÓN COMPLETADA. La aplicación activa no ha sido sustituida.')
    print('Motor conservado, SHA-256: '+state['engine_sha256'])
    print('Para activar: python3 '+str(Path(__file__).resolve())+' activate')
    print('Para volver atrás: python3 '+str(Path(__file__).resolve())+' rollback')


def rollback(state):
    old, _ = commands(state)
    subprocess.run(old+['up','-d','--no-deps','backend','nginx'],check=True)
    state['activated']=False
    save(state)
    print('Configuración original restaurada. Se conservan fuentes y datos de las dos versiones.')


def verify(base_url, release_id, index_sha256, attempts=30):
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(base_url+'/api/v1/plans/learning/status',timeout=3) as response:
                status=json.load(response)
            with urllib.request.urlopen(base_url+'/',timeout=3) as response:
                html=response.read()
            if status.get('mode')=='reviewed_exact_match' and status.get('release')==release_id and hashlib.sha256(html).hexdigest()==index_sha256:
                return
        except (OSError,ValueError):
            pass
        time.sleep(1)
    raise RuntimeError('La web no respondió con la nueva API y el frontend compilado.')


def activate(state, base_url):
    if not state['ready']:
        raise ValueError('Primero completa la preparación y las compilaciones.')
    base=Path(state['base'])
    for path,key in ((base/'docker-compose.yml','compose_sha256'),(base/'nginx.conf','nginx_sha256'),
                     (base/'backend/app/services/vector_engine.py','engine_sha256'),
                     (CANDIDATE/'backend/app/services/vector_engine.py','engine_sha256')):
        if digest(path)!=state[key]:
            raise ValueError('Los archivos cambiaron después de preparar. Repite la preparación antes de activar.')
    _, release=commands(state)
    try:
        subprocess.run(release+['up','-d','--no-deps','backend','frontend','nginx'],check=True)
        verify(base_url,state['tag'],state['frontend_index_sha256'])
    except Exception:
        print('Falló la comprobación de la nueva versión. Restaurando la configuración original.',file=sys.stderr)
        rollback(state)
        raise
    state['activated']=True
    save(state)
    print('ACTUALIZACIÓN ACTIVADA Y COMPROBADA: '+base_url)
    print('Prueba ahora tu PDF A-2, el guardado y la descarga .archviz desde el navegador.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('prepare');p.add_argument('--base',required=True);p.add_argument('--backup',required=True)
    p.add_argument('--project',default='archviz-pro');p.add_argument('--prepare-only',action='store_true')
    p=sub.add_parser('activate');p.add_argument('--url',default='http://127.0.0.1')
    sub.add_parser('rollback')
    args=parser.parse_args()
    if args.action=='prepare':
        prepare(args)
    else:
        state=json.loads(STATE.read_text())
        if args.action=='activate':activate(state,args.url)
        else:rollback(state)


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        print('ERROR: '+str(error),file=sys.stderr)
        sys.exit(1)
