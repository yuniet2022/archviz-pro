"""Password hashes and revocable opaque sessions. No shared signing secret."""
from contextlib import contextmanager
import hashlib
import hmac
from pathlib import Path
import secrets
import sqlite3
import time
import uuid


def password_hash(password):
    salt=secrets.token_bytes(16)
    digest=hashlib.scrypt(password.encode(),salt=salt,n=32768,r=8,p=1,maxmem=64*1024*1024)
    return 'scrypt$32768$8$1$'+salt.hex()+'$'+digest.hex()


def password_matches(password,encoded):
    try:
        scheme,n,r,p,salt,digest=encoded.split('$')
        if (scheme,n,r,p)!=('scrypt','32768','8','1'):return False
        candidate=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=32768,r=8,p=1,maxmem=64*1024*1024)
        return hmac.compare_digest(candidate,bytes.fromhex(digest))
    except (ValueError,TypeError):return False


DUMMY_PASSWORD=password_hash('unusable-random-'+secrets.token_urlsafe(24))


def token_hash(token):return hashlib.sha256(token.encode()).hexdigest()


class AuthStore:
    def __init__(self,path):
        self.path=path
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        with self.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS auth_users (
                    id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
                    password_hash TEXT NOT NULL, role TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1, must_change INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    digest TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES auth_users(id),
                    csrf TEXT NOT NULL, expires_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS auth_session_expiry ON auth_sessions(expires_at);
                CREATE TABLE IF NOT EXISTS auth_attempts (
                    bucket TEXT PRIMARY KEY, count INTEGER NOT NULL, expires_at REAL NOT NULL
                );
            ''')

    @contextmanager
    def connection(self):
        db=sqlite3.connect(self.path,timeout=15);db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:yield db
        finally:db.close()

    @staticmethod
    def public(user):
        return {key:user[key] for key in ('id','email','name','role','active','must_change')}

    def create_user(self,email,name,password,role='member',must_change=True,bootstrap=False,claim_legacy=False):
        from app.services.project_repository import ProjectRepository
        if bootstrap:ProjectRepository(self.path)
        encoded=password_hash(password);uid=str(uuid.uuid4())
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if bootstrap and db.execute("SELECT 1 FROM auth_users WHERE role='admin'").fetchone():
                raise ValueError('Ya existe un administrador. Usa la recuperación desde consola si necesitas restablecer su contraseña.')
            try:
                db.execute('INSERT INTO auth_users VALUES (?,?,?,?,?,1,?,?)',
                           (uid,email,name,encoded,role,int(must_change),time.time()))
            except sqlite3.IntegrityError:raise ValueError('Ya existe una cuenta con ese correo.')
            claimed=0
            if claim_legacy:
                claimed=db.execute('''INSERT INTO project_owners(project_id,user_id)
                    SELECT id,? FROM projects WHERE id NOT IN (SELECT project_id FROM project_owners)''',(uid,)).rowcount
        return {'id':uid,'email':email,'name':name,'role':role,'active':1,'must_change':int(must_change),'claimed_projects':claimed}

    def attempt(self,email,address):
        now=time.time()
        buckets=[('email:'+token_hash(email),8),('address:'+token_hash(address),80)]
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM auth_attempts WHERE expires_at<=?',(now,))
            db.execute('DELETE FROM auth_sessions WHERE expires_at<=?',(now,))
            for key,limit in buckets:
                row=db.execute('SELECT count FROM auth_attempts WHERE bucket=?',(key,)).fetchone()
                if row and row['count']>=limit:return False
            for key,_ in buckets:
                db.execute('''INSERT INTO auth_attempts VALUES (?,1,?)
                    ON CONFLICT(bucket) DO UPDATE SET count=count+1''',(key,now+900))
        return True

    def login(self,email,password):
        with self.connection() as db:
            user=db.execute('SELECT * FROM auth_users WHERE email=?',(email,)).fetchone()
        valid=password_matches(password,user['password_hash'] if user else DUMMY_PASSWORD)
        if not valid or not user or not user['active']:return None
        with self.connection() as db:db.execute('DELETE FROM auth_attempts WHERE bucket=?',('email:'+token_hash(email),))
        return self.public(user)

    def new_session(self,user_id,hours):
        token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32);expiry=time.time()+hours*3600
        with self.connection() as db:
            # Cap persistent sessions per account, including repeated legitimate logins.
            db.execute('DELETE FROM auth_sessions WHERE user_id=? AND digest NOT IN '
                       '(SELECT digest FROM auth_sessions WHERE user_id=? ORDER BY expires_at DESC LIMIT 9)',(user_id,user_id))
            db.execute('INSERT INTO auth_sessions VALUES (?,?,?,?)',(token_hash(token),user_id,csrf,expiry))
        return token,csrf

    def sign_in(self,email,password,hours,previous_token=None):
        # Verification and session issuance share a transaction with password
        # resets and deactivation, so an old password cannot create a session
        # after its credentials have already been revoked.
        token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            account=db.execute('SELECT * FROM auth_users WHERE email=?',(email,)).fetchone()
            valid=password_matches(password,account['password_hash'] if account else DUMMY_PASSWORD)
            if not valid or not account or not account['active']:return None
            if previous_token:db.execute('DELETE FROM auth_sessions WHERE digest=?',(token_hash(previous_token),))
            db.execute('DELETE FROM auth_sessions WHERE user_id=? AND digest NOT IN '
                       '(SELECT digest FROM auth_sessions WHERE user_id=? ORDER BY expires_at DESC LIMIT 9)',(account['id'],account['id']))
            db.execute('INSERT INTO auth_sessions VALUES (?,?,?,?)',(token_hash(token),account['id'],csrf,time.time()+hours*3600))
            db.execute('DELETE FROM auth_attempts WHERE bucket=?',('email:'+token_hash(email),))
        return self.public(account),token,csrf

    def session(self,token):
        if not token or len(token)>128:return None
        with self.connection() as db:
            row=db.execute('''SELECT u.*,s.csrf,s.expires_at FROM auth_sessions s
                JOIN auth_users u ON u.id=s.user_id WHERE s.digest=? AND s.expires_at>? AND u.active=1''',
                (token_hash(token),time.time())).fetchone()
        return {**self.public(row),'csrf':row['csrf'],'expires_at':row['expires_at']} if row else None

    def logout(self,token):
        if token:
            with self.connection() as db:db.execute('DELETE FROM auth_sessions WHERE digest=?',(token_hash(token),))

    def change_password(self,uid,old_password,new_password):
        with self.connection() as db:
            user=db.execute('SELECT password_hash FROM auth_users WHERE id=?',(uid,)).fetchone()
        if not user or not password_matches(old_password,user['password_hash']):return False
        encoded=password_hash(new_password)
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            updated=db.execute('UPDATE auth_users SET password_hash=?,must_change=0 WHERE id=? AND password_hash=?',
                               (encoded,uid,user['password_hash'])).rowcount
            if not updated:return False
            db.execute('DELETE FROM auth_sessions WHERE user_id=?',(uid,))
        return True

    def reset_password(self,uid,password,must_change=False):
        encoded=password_hash(password)
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM auth_users WHERE id=?',(uid,)).fetchone():raise ValueError('Cuenta no encontrada.')
            db.execute('UPDATE auth_users SET password_hash=?,must_change=? WHERE id=?',(encoded,int(must_change),uid))
            db.execute('DELETE FROM auth_sessions WHERE user_id=?',(uid,))

    def user_by_email(self,email):
        with self.connection() as db:
            row=db.execute('SELECT * FROM auth_users WHERE email=?',(email,)).fetchone()
        return self.public(row) if row else None

    def users(self):
        with self.connection() as db:return [self.public(row) for row in db.execute('SELECT * FROM auth_users ORDER BY created_at')]

    def set_active(self,uid,active,actor):
        if uid==actor:raise ValueError('No puedes desactivar tu propia cuenta.')
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM auth_users WHERE id=?',(uid,)).fetchone():raise ValueError('Cuenta no encontrada.')
            db.execute('UPDATE auth_users SET active=? WHERE id=?',(int(active),uid))
            db.execute('DELETE FROM auth_sessions WHERE user_id=?',(uid,))
