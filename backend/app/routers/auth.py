import re
from uuid import UUID
from typing import Literal
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from app.core.auth import COOKIE, store, user, admin, login_available, client_address
from app.core.config import settings

router=APIRouter(prefix='/auth',tags=['authentication'])


class Credentials(BaseModel):
    email:str=Field(min_length=3,max_length=254)
    password:str=Field(min_length=1,max_length=128)

    @field_validator('email')
    @classmethod
    def email_address(cls,value):
        value=value.strip().lower()
        if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',value):raise ValueError('Escribe un correo válido.')
        return value


class NewUser(Credentials):
    password:str=Field(min_length=12,max_length=128)
    name:str=Field(min_length=1,max_length=100)
    role:Literal['admin','member']='member'

    @field_validator('name')
    @classmethod
    def nonempty_name(cls,value):
        value=value.strip()
        if not value:raise ValueError('Escribe un nombre.')
        return value


class PasswordChange(BaseModel):
    current_password:str=Field(min_length=1,max_length=128)
    new_password:str=Field(min_length=12,max_length=128)


class ActiveUser(BaseModel):
    active:bool


def clear_cookie(response):
    response.delete_cookie(COOKIE,path='/',secure=settings.AUTH_COOKIE_SECURE,httponly=True,samesite='lax')


@router.get('/session')
def session(request:Request):
    identity=getattr(request.state,'user',None)
    users=store().users()
    return {'user':{key:identity[key] for key in ('id','email','name','role','active','must_change')} if identity else None,
            'csrf_token':identity['csrf'] if identity else None,
            'login_available':login_available(request),'accounts_ready':bool(users)}


@router.post('/login')
def login(credentials:Credentials,request:Request,response:Response):
    if not login_available(request):raise HTTPException(503,'El acceso público requiere configurar HTTPS antes de iniciar sesión.')
    auth=store()
    if not auth.attempt(credentials.email,client_address(request)):
        raise HTTPException(429,'Demasiados intentos. Espera 15 minutos antes de volver a intentarlo.',headers={'Retry-After':'900'})
    result=auth.sign_in(credentials.email,credentials.password,settings.AUTH_SESSION_HOURS,request.cookies.get(COOKIE))
    if not result:raise HTTPException(401,'Correo o contraseña incorrectos.')
    identity,token,csrf=result
    response.set_cookie(COOKIE,token,max_age=settings.AUTH_SESSION_HOURS*3600,httponly=True,
                        secure=settings.AUTH_COOKIE_SECURE,samesite='lax',path='/')
    return {'user':identity,'csrf_token':csrf,'login_available':True,'accounts_ready':True}


@router.post('/logout')
def logout(request:Request,response:Response):
    store().logout(request.cookies.get(COOKIE));clear_cookie(response)
    return {'message':'Sesión cerrada.'}


@router.post('/password')
def change_password(values:PasswordChange,request:Request,response:Response):
    identity=user(request);auth=store()
    if not auth.attempt('password:'+identity['id'],client_address(request)):
        raise HTTPException(429,'Demasiados intentos. Espera 15 minutos.')
    if values.current_password==values.new_password:raise HTTPException(422,'Elige una contraseña distinta de la temporal o anterior.')
    if not auth.change_password(identity['id'],values.current_password,values.new_password):
        raise HTTPException(400,'La contraseña actual no coincide.')
    clear_cookie(response)
    return {'message':'Contraseña actualizada. Inicia sesión de nuevo; las sesiones anteriores se han cerrado.'}


@router.get('/users')
def users(request:Request):
    admin(request);return {'users':store().users()}


@router.post('/users',status_code=201)
def create_user(values:NewUser,request:Request):
    admin(request)
    try:return {'user':store().create_user(values.email,values.name,values.password,values.role)}
    except ValueError as error:raise HTTPException(409,str(error))


@router.patch('/users/{uid}')
def active_user(uid:UUID,values:ActiveUser,request:Request):
    identity=admin(request)
    try:store().set_active(str(uid),values.active,identity['id'])
    except ValueError as error:raise HTTPException(400,str(error))
    return {'users':store().users()}
