#!/usr/bin/env python3
"""Stage a release beside an existing Compose installation; activate explicitly."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
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
                'networks':{'archviz-update':None},
                'healthcheck':{'test':['CMD','python','-c',
                    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=2).read()"],
                    'interval':'5s','timeout':'3s','start_period':'15s','retries':6},
            },
            'frontend': {
                'image':'archviz-update-frontend:'+tag,
                'build':{'context':str(candidate/'frontend'),'dockerfile':'Dockerfile'},
                'entrypoint':['/docker-entrypoint.sh'],
                'command':['nginx','-g','daemon off;'],
                'networks':{'archviz-update':None},
            },
            'nginx': {
                'volumes':[mount(candidate/'nginx.conf','/etc/nginx/nginx.conf',True)],
                'networks':{'archviz-update':None},
                'depends_on':{'backend':{'condition':'service_healthy'},'frontend':{'condition':'service_started'}},
            },
        },
        'networks':{'archviz-update':{'driver':'bridge'}},
    }


def release_model(original, patch):
    """Modify Compose's normalized model, avoiding cross-file type merges in 2.24."""
    result=json.loads(json.dumps(original))
    for name, updates in patch['services'].items():
        service=result.setdefault('services',{}).setdefault(name,{})
        for key,value in updates.items():
            if key=='volumes':
                mounts={item['target']:item for item in service.get('volumes',[])}
                mounts.update({item['target']:item for item in value})
                service[key]=list(mounts.values())
            elif key in ('build','environment','networks','depends_on'):
                existing=service.get(key) or {}
                if not isinstance(existing,dict):
                    raise ValueError('Compose no normalizó el campo '+name+'.'+key)
                service[key]={**existing,**value}
            else:
                service[key]=value
        if 'build' in service:
            # New Dockerfiles must build their final stage, not a legacy builder target.
            service['build'].pop('target',None)
            service['build'].pop('dockerfile_inline',None)
        if name=='frontend':
            # Serve the compiled image, never a stale host dist directory from the old builder.
            for legacy in ('volumes','ports','profiles'):
                service.pop(legacy,None)
    result['networks']={**result.get('networks',{}),**patch['networks']}
    return result


def private_json(path, data):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    os.fchmod(fd,0o600)
    with os.fdopen(fd,'w') as stream:
        json.dump(data,stream,indent=2)
        stream.write('\n')


def commands(state):
    old = state['compose']+['-p',state['project'],'-f',str(Path(state['base'])/'docker-compose.yml')]
    if state.get('release_config'):
        return old, state['compose']+['-p',state['project'],'-f',state['release_config']]
    return old, old+['-f',str(CANDIDATE/'deployment.override.json')]


def save(state):
    private_json(STATE,state)


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
    old, _ = commands(state)
    original=json.loads(subprocess.check_output(old+['config','--format','json'],text=True))
    if not {'backend','nginx'}.issubset(original.get('services',{})):
        raise ValueError('La instalación no tiene los servicios backend y nginx esperados.')
    # Compose's rendered JSON already escapes interpolation for a safe round trip.
    # This resolved configuration can contain credentials: keep it private, never print it.
    rendered=CANDIDATE/'deployment.compose.json'
    private_json(rendered,release_model(original,build_override(base,CANDIDATE,tag)))
    state['release_config']=str(rendered)
    state['release_config_sha256']=digest(rendered)
    _, release = commands(state)
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
        'from app.services.architectural_pdf import ArchitecturalPDFEngine; '
        'from app.services.cad_geometry import import_dxf; '
        'from app.main import app; assert callable(ArchitecturalPDFEngine().process_pdf); '
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
    if state.get('release_config') and digest(state['release_config'])!=state['release_config_sha256']:
        raise ValueError('La configuración preparada cambió. Repite la preparación antes de activar.')
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
