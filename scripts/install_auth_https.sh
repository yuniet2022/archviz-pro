#!/usr/bin/env bash
# Install the authenticated release with a verified temporary HTTPS hostname.
set -euo pipefail
umask 077

public_ip="${1:?Uso: bash scripts/install_auth_https.sh IP_PUBLICA}"
base="${2:-/opt/archviz-pro}"
backup="${3:-/root/archviz-respaldo-20261018-031525}"
candidate="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
project="archviz-pro"
https_container="archviz-pro-https"
https_dir="$base/data/https"
caddy_image="caddy@sha256:eb4d35b7452d1ab6171fbdbe8d9275b2301dad6dad92115d91e19fb9b24d510f"

if [[ ! -t 0 ]]; then
  echo "Ejecuta este instalador en una terminal interactiva o redirígelo con </dev/tty." >&2
  exit 1
fi
if command -v docker-compose >/dev/null; then
  compose=(docker-compose)
else
  docker compose version >/dev/null
  compose=(docker compose)
fi

hostname="$(python3 - "$public_ip" "$https_dir/hostname" <<'PY'
import ipaddress, socket, sys
from pathlib import Path
ip=str(ipaddress.IPv4Address(sys.argv[1]))
if not ipaddress.ip_address(ip).is_global:
    raise SystemExit('Usa la IP pública del servidor.')
saved=Path(sys.argv[2])
choices=[saved.read_text().strip()] if saved.exists() else [ip.replace('.','-')+'.sslip.io',ip+'.nip.io']
for host in choices:
    if not host or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789.-' for c in host):
        raise SystemExit('Nombre HTTPS guardado inválido.')
    try:addresses={a[4][0] for a in socket.getaddrinfo(host,443,socket.AF_INET,socket.SOCK_STREAM)}
    except OSError:continue
    if addresses=={ip}:
        print(host);break
else:
    raise SystemExit('El DNS temporal no resuelve a esta IP. No se ha cambiado la aplicación activa.')
PY
)"

occupants="$(docker ps --filter publish=443 --format '{{.Names}}')"
if [[ -n "$occupants" && "$occupants" != "$https_container" ]]; then
  echo "El puerto 443 está ocupado por: $occupants. Se detuvo la instalación sin sustituir la aplicación." >&2
  exit 1
fi
network="$(docker inspect --format '{{json .NetworkSettings.Networks}}' "$project-backend-1" | python3 -c 'import json,sys; names=[n for n in json.load(sys.stdin) if n.endswith("_archviz-update")]; assert len(names)==1,"No se encontró una única red de la aplicación"; print(names[0])')"

# The backup captures the current project database online, including all source blobs.
docker exec -i "$project-backend-1" python - <<'PY'
import os,sqlite3
from pathlib import Path
from datetime import datetime
os.umask(0o077)
source=Path('/app/data/projects.sqlite3')
if not source.is_file():raise SystemExit('Falta la base de proyectos; no se continúa.')
folder=source.parent/'backups';folder.mkdir(mode=0o700,exist_ok=True)
copy=folder/('antes-de-autenticacion-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.sqlite3')
with sqlite3.connect('file:'+str(source)+'?mode=ro',uri=True) as original:
    with sqlite3.connect(str(copy)) as target:
        original.backup(target)
        if target.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise SystemExit('El respaldo no pasó la comprobación.')
print('RESPALDO VERIFICADO:',copy.name)
PY

python3 "$candidate/scripts/server_update.py" prepare \
  --base "$base" --backup "$backup" --project "$project" \
  --public-origin "https://$hostname"
release=("${compose[@]}" -p "$project" -f "$candidate/deployment.compose.json")

mkdir -p "$https_dir/data" "$https_dir/config"
if docker container inspect "$https_container" >/dev/null 2>&1; then
  configured="$(docker inspect --format '{{json .Config.Env}}' "$https_container" | python3 -c 'import json,sys; print(next((v.split("=",1)[1] for v in json.load(sys.stdin) if v.startswith("ARCHVIZ_HTTPS_HOST=")),""))')"
  if [[ "$configured" != "$hostname" ]]; then
    echo 'El contenedor HTTPS existente usa otra configuración; no se sustituirá automáticamente.' >&2
    exit 1
  fi
  docker start "$https_container" >/dev/null
else
  cp "$candidate/scripts/Caddyfile" "$https_dir/Caddyfile"
  printf '%s\n' "$hostname" > "$https_dir/hostname"
  docker pull "$caddy_image"
  docker run --rm -e "ARCHVIZ_HTTPS_HOST=$hostname" \
    -v "$https_dir/Caddyfile:/etc/caddy/Caddyfile:ro" \
    "$caddy_image" caddy validate --config /etc/caddy/Caddyfile
  if command -v ufw >/dev/null && ufw status | awk '/^Status: active$/{found=1} END{exit !found}'; then
    ufw allow 443/tcp
  fi
  docker run -d --name "$https_container" --restart unless-stopped \
    --network "$network" -p 443:443 \
    -e "ARCHVIZ_HTTPS_HOST=$hostname" \
    -v "$https_dir/Caddyfile:/etc/caddy/Caddyfile:ro" \
    -v "$https_dir/data:/data" -v "$https_dir/config:/config" "$caddy_image"
fi

# The public certificate is verified with the system trust store before asking
# for account credentials or switching releases. No insecure TLS option exists.
if ! python3 - "$hostname" <<'PY'
import sys,time,urllib.request
host=sys.argv[1];deadline=time.monotonic()+180
while time.monotonic()<deadline:
    try:
        with urllib.request.urlopen('https://'+host+'/api/v1/plans/learning/status',timeout=5) as response:
            if response.status==200:print('HTTPS Y CERTIFICADO VERIFICADOS:',host);break
    except (OSError,ValueError):pass
    print('Esperando el certificado HTTPS...',flush=True);time.sleep(3)
else:raise SystemExit('No se pudo verificar HTTPS. Revisa que TCP 443 esté permitido en el firewall de DigitalOcean. La aplicación anterior sigue activa.')
PY
then
  docker logs --tail 15 "$https_container" >&2
  exit 1
fi

email="$(docker exec "$project-backend-1" python -c 'import sqlite3; db=sqlite3.connect("file:/app/data/projects.sqlite3?mode=ro",uri=True); exists=db.execute("SELECT 1 FROM sqlite_master WHERE type=\047table\047 AND name=\047auth_users\047").fetchone(); row=db.execute("SELECT email FROM auth_users WHERE role=\047admin\047 AND active=1 ORDER BY created_at LIMIT 1").fetchone() if exists else None; print(row[0] if row else "")')"
if [[ -z "$email" ]]; then
  read -r -p 'Correo para tu cuenta administradora: ' email
  "${release[@]}" run --rm --no-deps backend python -m app.manage bootstrap-admin \
    --email "$email" --name Administrador --claim-legacy
fi

python3 "$candidate/scripts/server_update.py" activate --url "https://$hostname"
docker exec "$project-backend-1" python -m app.manage claim-legacy --email "$email"
python3 - "$hostname" <<'PY'
import json,sys,urllib.request,urllib.error
url='https://'+sys.argv[1]
with urllib.request.urlopen(url+'/api/v1/auth/session',timeout=10) as response:state=json.load(response)
if not state.get('login_available') or not state.get('accounts_ready'):raise SystemExit('La cuenta o el acceso HTTPS no quedó disponible. Revisa la salida anterior.')
try:urllib.request.urlopen(url+'/api/v1/plans',timeout=10)
except urllib.error.HTTPError as error:
    if error.code!=401:raise
else:raise SystemExit('La comprobación de privacidad falló.')
print('\nACTUALIZACIÓN COMPLETADA. INICIA SESIÓN EN:',url)
PY
