"""Local identity, sessions and authorization. No project data is public by default."""
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROLES=['Administrator','Analyst','Viewer']
ITERATIONS=600_000
IDLE_SECONDS=30*60
SESSION_SECONDS=8*60*60


def password_record(password):
 if not 15<=len(password)<=1024:
  raise ValueError('Use a password of 15 to 1,024 characters.')
 salt=secrets.token_bytes(32)
 digest=hashlib.pbkdf2_hmac('sha256',password.encode('utf-8'),salt,ITERATIONS)
 return json.dumps(dict(algorithm='pbkdf2-sha256',iterations=ITERATIONS,salt=salt.hex(),digest=digest.hex()))


def check_password(password,record):
 try:
  data=json.loads(record)
  if data['algorithm']!='pbkdf2-sha256' or not 100_000<=int(data['iterations'])<=2_000_000:return False
  if len(password)>1024:return False
  digest=hashlib.pbkdf2_hmac('sha256',password.encode('utf-8'),bytes.fromhex(data['salt']),data['iterations'])
  return hmac.compare_digest(digest.hex(),data['digest'])
 except (ValueError,TypeError,KeyError):return False


def normalize_username(username):
 value=username.strip().casefold()
 if not re.fullmatch(r'[a-z0-9][a-z0-9_.@-]{2,79}',value):
  raise ValueError('Username must be 3-80 characters: letters, numbers, dot, underscore, @ or hyphen.')
 return value


def stamp():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def token_hash(token):return hashlib.sha256(token.encode()).hexdigest()


class ClosingConnection(sqlite3.Connection):
 def __exit__(self,exc_type,exc_value,traceback):
  try:return super().__exit__(exc_type,exc_value,traceback)
  finally:self.close()


class AuthStore:
 def __init__(self,path=None):
  if path is None:
   from storage import DB_PATH
   path=DB_PATH
  self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
  with self.connect() as con:
   con.executescript('''
   CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, name TEXT NOT NULL, updated TEXT NOT NULL, payload TEXT NOT NULL);
   CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, display_name TEXT NOT NULL,
    password TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('Administrator','Analyst','Viewer')),
    active INTEGER NOT NULL DEFAULT 1, must_change INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL, last_login TEXT);
   CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created REAL NOT NULL,last_seen REAL NOT NULL,expires REAL NOT NULL);
   CREATE TABLE IF NOT EXISTS memberships (user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    permission TEXT NOT NULL CHECK(permission IN ('view','edit')), PRIMARY KEY(user_id,project_id));
   CREATE TABLE IF NOT EXISTS last_projects (user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE);
   CREATE TABLE IF NOT EXISTS login_attempts (username TEXT PRIMARY KEY,failures INTEGER NOT NULL,window_start REAL NOT NULL,locked_until REAL NOT NULL);
   CREATE TABLE IF NOT EXISTS security_audit (id INTEGER PRIMARY KEY AUTOINCREMENT,time TEXT NOT NULL,actor TEXT NOT NULL,action TEXT NOT NULL,target TEXT NOT NULL);
   ''')
 def connect(self):
  con=sqlite3.connect(self.path,timeout=20,factory=ClosingConnection);con.row_factory=sqlite3.Row
  con.execute('PRAGMA foreign_keys=ON')
  return con
 def event(self,con,actor,action,target=''):
  con.execute('INSERT INTO security_audit(time,actor,action,target) VALUES (?,?,?,?)',(stamp(),actor,action,str(target)))
 def has_users(self):
  with self.connect() as con:return bool(con.execute('SELECT 1 FROM users LIMIT 1').fetchone())
 def setup_file(self):return self.path.parent/'setup-key.txt'
 def ensure_setup_key(self):
  if self.has_users():return
  path=self.setup_file()
  try:
   fd=os.open(str(path),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
  except FileExistsError:return
  with os.fdopen(fd,'w',encoding='utf-8') as handle:handle.write(secrets.token_urlsafe(32))
 def bootstrap(self,username,display_name,password,key):
  username=normalize_username(username);record=password_record(password)
  if not display_name.strip():raise ValueError('Enter a display name.')
  try:expected=self.setup_file().read_text(encoding='utf-8').strip()
  except OSError:raise ValueError('Setup key unavailable. Restart the app and try again.') from None
  if not hmac.compare_digest(key.strip().encode(),expected.encode()):raise ValueError('Setup key is not valid.')
  with self.connect() as con:
   con.execute('BEGIN IMMEDIATE')
   if con.execute('SELECT 1 FROM users LIMIT 1').fetchone():raise ValueError('Setup is already complete. Sign in instead.')
   user_id=uuid.uuid4().hex
   con.execute('INSERT INTO users(id,username,display_name,password,role,created) VALUES (?,?,?,?,?,?)',
               (user_id,username,display_name.strip(),record,'Administrator',stamp()))
   self.event(con,username,'Created first administrator')
  try:self.setup_file().unlink(missing_ok=True)
  except OSError:pass
  return user_id
 def login(self,username,password):
  # Generic errors and equal-cost checks avoid disclosing whether an account exists.
  try:username=normalize_username(username)
  except ValueError:
   username=hashlib.sha256(username.encode()).hexdigest()
  now=time.time()
  with self.connect() as con:
   con.execute('BEGIN IMMEDIATE')
   attempt=con.execute('SELECT * FROM login_attempts WHERE username=?',(username,)).fetchone()
   if attempt and attempt['locked_until']>now:return None
   user=con.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
   dummy=json.dumps(dict(algorithm='pbkdf2-sha256',iterations=ITERATIONS,salt='00'*32,digest='00'*32))
   correct=check_password(password,user['password'] if user else dummy)
   if not user or not user['active'] or not correct:
    failures=attempt['failures']+1 if attempt and now-attempt['window_start']<300 else 1
    start=attempt['window_start'] if attempt and now-attempt['window_start']<300 else now
    locked=now+300 if failures>=5 else 0
    con.execute('INSERT INTO login_attempts VALUES (?,?,?,?) ON CONFLICT(username) DO UPDATE SET failures=excluded.failures,window_start=excluded.window_start,locked_until=excluded.locked_until',(username,failures,start,locked))
    self.event(con,username,'Failed sign-in')
    return None
   con.execute('DELETE FROM login_attempts WHERE username=?',(username,))
   con.execute('DELETE FROM sessions WHERE expires<? OR last_seen<?',(now,now-IDLE_SECONDS))
   token=secrets.token_urlsafe(48)
   con.execute('INSERT INTO sessions VALUES (?,?,?,?,?)',(token_hash(token),user['id'],now,now,now+SESSION_SECONDS))
   con.execute('UPDATE users SET last_login=? WHERE id=?',(stamp(),user['id']))
   self.event(con,username,'Signed in')
   return token
 def identity(self,token,con=None,touch=False):
  if not token:return None
  if con is None:
   with self.connect() as owned:return self.identity(token,owned,touch)
  now=time.time()
  row=con.execute('SELECT u.id,u.username,u.display_name,u.role,u.active,u.must_change,s.last_seen,s.expires FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=?',(token_hash(token),)).fetchone()
  if not row or not row['active'] or row['expires']<=now or row['last_seen']+IDLE_SECONDS<=now:return None
  if touch:con.execute('UPDATE sessions SET last_seen=? WHERE token_hash=?',(now,token_hash(token)))
  return dict(row)
 def actor(self,token,con):
  user=self.identity(token,con)
  if not user or user['must_change']:raise PermissionError('Sign in and complete any required password change.')
  return user
 def authorize(self,token,project_id,write=False,con=None):
  if con is None:
   with self.connect() as owned:return self.authorize(token,project_id,write,owned)
  user=self.actor(token,con)
  if user['role']=='Administrator':return user
  member=con.execute('SELECT permission FROM memberships WHERE user_id=? AND project_id=?',(user['id'],project_id)).fetchone()
  if not member or (write and (user['role']!='Analyst' or member['permission']!='edit')):
   raise PermissionError('You do not have permission for this project or action.')
  return user
 def admin(self,token,con):
  user=self.actor(token,con)
  if user['role']!='Administrator':raise PermissionError('Administrator access is required.')
  return user
 def logout(self,token):
  with self.connect() as con:
   user=self.identity(token,con)
   con.execute('DELETE FROM sessions WHERE token_hash=?',(token_hash(token),))
   if user:self.event(con,user['username'],'Signed out')
 def change_password(self,token,current,new):
  record=password_record(new)
  if current==new:raise ValueError('Choose a different password.')
  with self.connect() as con:
   con.execute('BEGIN IMMEDIATE');user=self.identity(token,con)
   if not user:raise PermissionError('Sign in again before changing your password.')
   old=con.execute('SELECT password FROM users WHERE id=?',(user['id'],)).fetchone()[0]
   if not check_password(current,old):raise ValueError('Current password is not correct.')
   con.execute('UPDATE users SET password=?,must_change=0 WHERE id=?',(record,user['id']))
   con.execute('DELETE FROM sessions WHERE user_id=?',(user['id'],))
   self.event(con,user['username'],'Changed password; revoked all sessions')
 def users(self,token):
  with self.connect() as con:
   self.admin(token,con)
   return [dict(r) for r in con.execute('SELECT id,username,display_name,role,active,must_change,created,last_login FROM users ORDER BY username')]
 def create_user(self,token,username,display_name,password,role):
  username=normalize_username(username);record=password_record(password)
  if role not in ROLES:raise ValueError('Choose a supported role.')
  if not display_name.strip():raise ValueError('Enter a display name.')
  with self.connect() as con:
   con.execute('BEGIN IMMEDIATE');actor=self.admin(token,con);user_id=uuid.uuid4().hex
   try:con.execute('INSERT INTO users(id,username,display_name,password,role,must_change,created) VALUES (?,?,?,?,?,1,?)',(user_id,username,display_name.strip(),record,role,stamp()))
   except sqlite3.IntegrityError:raise ValueError('That username is already in use.') from None
   self.event(con,actor['username'],'Created user',username)
  return user_id
 def update_user(self,token,user_id,role,active):
  if role not in ROLES:raise ValueError('Choose a supported role.')
  with self.connect() as con:
   con.execute('BEGIN IMMEDIATE');actor=self.admin(token,con)
   old=con.execute('SELECT * FROM users WHERE id=?',(user_id,)).fetchone()
   if not old:raise ValueError('User not found.')
   if old['role']=='Administrator' and old['active'] and (role!='Administrator' or not active):
    count=con.execute("SELECT count(*) FROM users WHERE role='Administrator' AND active=1").fetchone()[0]
    if count<=1:raise ValueError('Keep at least one active administrator.')
   con.execute('UPDATE users SET role=?,active=? WHERE id=?',(role,int(active),user_id))
   if role=='Viewer':con.execute("UPDATE memberships SET permission='view' WHERE user_id=?",(user_id,))
   con.execute('DELETE FROM sessions WHERE user_id=?',(user_id,))
   self.event(con,actor['username'],f'Updated user role={role}; active={bool(active)}; revoked sessions',old['username'])
 def reset_password(self,token,user_id,password):
  record=password_record(password)
  with self.connect() as con:
   con.execute('BEGIN IMMEDIATE');actor=self.admin(token,con)
   user=con.execute('SELECT username FROM users WHERE id=?',(user_id,)).fetchone()
   if not user:raise ValueError('User not found.')
   con.execute('UPDATE users SET password=?,must_change=1 WHERE id=?',(record,user_id))
   con.execute('DELETE FROM sessions WHERE user_id=?',(user_id,))
   con.execute('DELETE FROM login_attempts WHERE username=?',(user['username'],))
   self.event(con,actor['username'],'Reset password; revoked sessions',user['username'])
 def memberships(self,token,user_id):
  with self.connect() as con:
   self.admin(token,con)
   return {r['project_id']:r['permission'] for r in con.execute('SELECT project_id,permission FROM memberships WHERE user_id=?',(user_id,))}
 def grant(self,token,user_id,project_id,permission):
  if permission not in ('view','edit',None):raise ValueError('Choose View, Edit or No access.')
  with self.connect() as con:
   con.execute('BEGIN IMMEDIATE');actor=self.admin(token,con)
   user=con.execute('SELECT username,role FROM users WHERE id=?',(user_id,)).fetchone()
   if not user or not con.execute('SELECT 1 FROM projects WHERE id=?',(project_id,)).fetchone():raise ValueError('User or project not found.')
   if user['role']=='Viewer' and permission=='edit':raise ValueError('Viewer accounts can only receive view permission.')
   if user['role']=='Administrator':raise ValueError('Administrators already have access to every project.')
   if permission:
    con.execute('INSERT INTO memberships VALUES (?,?,?) ON CONFLICT(user_id,project_id) DO UPDATE SET permission=excluded.permission',(user_id,project_id,permission))
   else:con.execute('DELETE FROM memberships WHERE user_id=? AND project_id=?',(user_id,project_id))
   self.event(con,actor['username'],f'Project permission: {permission or "none"} for {user["username"]}',project_id)
 def remember_project(self,token,project_id):
  with self.connect() as con:
   con.execute('BEGIN IMMEDIATE');user=self.authorize(token,project_id,False,con)
   con.execute('INSERT INTO last_projects VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET project_id=excluded.project_id',(user['id'],project_id))
 def last_project(self,token):
  with self.connect() as con:
   user=self.actor(token,con)
   row=con.execute('SELECT project_id FROM last_projects WHERE user_id=?',(user['id'],)).fetchone()
   if not row:return None
   try:self.authorize(token,row['project_id'],False,con)
   except PermissionError:return None
   return row['project_id']
 def audit(self,token):
  with self.connect() as con:
   self.admin(token,con)
   return [dict(r) for r in con.execute('SELECT time,actor,action,target FROM security_audit ORDER BY id DESC LIMIT 2000')]
