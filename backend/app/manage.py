"""Local account administration. Passwords are entered privately, never CLI arguments."""
import argparse
import getpass
import sys
from app.core.config import settings
from app.services.auth_store import AuthStore
from app.routers.auth import NewUser
from app.services.project_repository import ProjectRepository


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    bootstrap=sub.add_parser('bootstrap-admin');bootstrap.add_argument('--email',required=True)
    bootstrap.add_argument('--name',default='Administrador');bootstrap.add_argument('--claim-legacy',action='store_true')
    reset=sub.add_parser('reset-password');reset.add_argument('--email',required=True)
    claim=sub.add_parser('claim-legacy');claim.add_argument('--email',required=True)
    args=parser.parse_args();auth=AuthStore(settings.PROJECT_DB)
    email=args.email.strip().lower()
    if args.command=='claim-legacy':
        account=auth.user_by_email(email)
        if not account or account['role']!='admin':raise ValueError('Selecciona una cuenta administradora existente.')
        repo=ProjectRepository(settings.PROJECT_DB)
        with repo.connection() as db:
            count=db.execute('INSERT INTO project_owners SELECT id,? FROM projects WHERE id NOT IN (SELECT project_id FROM project_owners)',(account['id'],)).rowcount
        print(f'Proyectos anteriores asignados: {count}')
        return
    if not sys.stdin.isatty():
        raise ValueError('Usa una consola interactiva (docker exec -it). La contraseña no debe pasarse por argumentos ni pegarse en este chat.')
    password=getpass.getpass('Contraseña nueva (mínimo 12 caracteres): ')
    if password!=getpass.getpass('Repite la contraseña: '):raise ValueError('Las contraseñas no coinciden.')
    values=NewUser(email=email,name=getattr(args,'name','Cuenta'),password=password)
    if args.command=='bootstrap-admin':
        account=auth.create_user(values.email,values.name,values.password,'admin',False,bootstrap=True,claim_legacy=args.claim_legacy)
        print('Administrador creado. Proyectos anteriores asignados:',account['claimed_projects'])
    else:
        account=auth.user_by_email(email)
        if not account:raise ValueError('Cuenta no encontrada.')
        auth.reset_password(account['id'],password)
        print('Contraseña actualizada. Las sesiones anteriores han sido revocadas.')


if __name__=='__main__':
    try:main()
    except (ValueError,EOFError) as error:
        print(str(error),file=sys.stderr);raise SystemExit(1)
