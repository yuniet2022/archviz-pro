import hmac
import ipaddress
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.security_context import owner_id
from app.services.auth_store import AuthStore

COOKIE='archviz_session'
PUBLIC_PATHS={settings.API_V1_PREFIX+path for path in ('/auth/session','/auth/login','/plans/learning/status')}


def store():return AuthStore(settings.PROJECT_DB)


def trusted_proxy(request):
    address=request.client.host if request.client else ''
    try:return ipaddress.ip_address(address).is_private
    except ValueError:return False


def client_address(request):
    if trusted_proxy(request):
        try:return str(ipaddress.ip_address(request.headers.get('x-real-ip','')))
        except ValueError:pass
    return request.client.host if request.client else 'unknown'


def effective_scheme(request):
    # Only accept proxy scheme from a local/private reverse proxy. The production
    # backend port is bound to loopback; nginx overwrites this header.
    forwarded=request.headers.get('x-forwarded-proto','')
    return forwarded if trusted_proxy(request) and forwarded in ('http','https') else request.url.scheme


def login_available(request):
    origin=settings.AUTH_PUBLIC_ORIGIN.rstrip('/')
    if settings.AUTH_COOKIE_SECURE:
        return bool(origin.startswith('https://') and effective_scheme(request)=='https')
    # Insecure cookies are only a local development option, never a public IP.
    host=request.url.hostname
    return host in ('127.0.0.1','localhost','testserver','::1')


def check_origin(request):
    origin=request.headers.get('origin')
    referer=request.headers.get('referer')
    expected=settings.AUTH_PUBLIC_ORIGIN.rstrip('/') or f'{effective_scheme(request)}://{request.headers.get("host","")}'
    if origin is not None and origin!=expected:
        raise HTTPException(403,'Origen de la solicitud no permitido.')
    if origin is None and referer:
        parsed=urlsplit(referer)
        if f'{parsed.scheme}://{parsed.netloc}'!=expected:raise HTTPException(403,'Origen de la solicitud no permitido.')
    if request.headers.get('sec-fetch-site')=='cross-site':
        raise HTTPException(403,'Origen de la solicitud no permitido.')


def user(request:Request):
    identity=getattr(request.state,'user',None)
    if not identity:raise HTTPException(401,'Inicia sesión para continuar.')
    return identity


def admin(request:Request):
    identity=user(request)
    if identity['role']!='admin':raise HTTPException(403,'Esta acción requiere una cuenta administradora.')
    return identity


async def authenticate(request,call_next):
    path=request.url.path
    # The API server has no public project/static routes. Keep new endpoints
    # private by default, even if a deployment changes the API prefix.
    protected=path not in ('/','/health')
    if path.startswith('/exports'):
        return JSONResponse({'detail':'Archivo no disponible. Usa las descargas del proyecto.'},status_code=404)
    request.state.user=None
    context=None
    if protected:
        identity=store().session(request.cookies.get(COOKIE))
        request.state.user=identity
        if path not in PUBLIC_PATHS and not identity:
            return JSONResponse({'detail':'Inicia sesión para continuar.'},status_code=401,headers={'Cache-Control':'no-store'})
        if identity:
            context=owner_id.set(identity['id'])
            if identity['must_change'] and path not in {settings.API_V1_PREFIX+suffix for suffix in ('/auth/session','/auth/password','/auth/logout')}:
                owner_id.reset(context)
                return JSONResponse({'detail':'Cambia tu contraseña temporal para continuar.'},status_code=403)
        try:
            if request.method not in ('GET','HEAD','OPTIONS'):
                check_origin(request)
                if path!=settings.API_V1_PREFIX+'/auth/login' and identity:
                    if not hmac.compare_digest(request.headers.get('x-csrf-token',''),identity['csrf']):
                        raise HTTPException(403,'La sesión de seguridad cambió. Recarga la página e inténtalo de nuevo.')
        except HTTPException as error:
            if context is not None:owner_id.reset(context)
            return JSONResponse({'detail':error.detail},status_code=error.status_code)
    try:
        response=await call_next(request)
    finally:
        if context is not None:owner_id.reset(context)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='same-origin'
    if protected:response.headers['Cache-Control']='no-store'
    if settings.AUTH_COOKIE_SECURE and effective_scheme(request)=='https':
        response.headers['Strict-Transport-Security']='max-age=31536000'
    return response
