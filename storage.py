"""Transactional local project storage. No executable serialization is used."""
import json
import sqlite3
import io
import uuid
import numpy as np
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

DB_PATH = Path(__file__).resolve().parent / 'data' / 'opsintel.sqlite3'

def nonfinite_cells(frame):
 cells=[]
 if frame is None:return cells
 for col_index,column in enumerate(frame.columns):
  if pd.api.types.is_numeric_dtype(frame[column]):
   values=frame[column].to_numpy(dtype=float,na_value=np.nan)
   for row_index in np.flatnonzero(np.isinf(values)):
    cells.append([int(row_index),col_index,1 if values[row_index]>0 else -1])
 return cells

def restore_frame(serialized,cells):
 if serialized is None:return None
 frame=pd.read_json(io.StringIO(serialized),orient='table')
 for row,column,sign in cells:
  frame.iat[row,column]=float('inf')*sign
 return frame

class ProjectConflictError(RuntimeError):
 pass


def encode_payload(state):
 payload=dict(state)
 payload.pop('_revision',None)
 payload['data']=state['data'].to_json(orient='table',date_format='iso',index=False)
 original=state.get('original_data')
 payload['original_data']=original.to_json(orient='table',date_format='iso',index=False) if original is not None else None
 payload['data_nonfinite']=nonfinite_cells(state['data'])
 payload['original_nonfinite']=nonfinite_cells(original)
 payload['version']=1
 return json.dumps(payload,ensure_ascii=False,allow_nan=False)


class ProjectStore:
 def __init__(self,path=None,actor_token=None):
  self.path=Path(path) if path is not None else DB_PATH
  self.path.parent.mkdir(parents=True,exist_ok=True)
  self.token=actor_token
  from security import AuthStore
  self.auth=AuthStore(self.path)
 def connect(self):
  from security import ClosingConnection
  con=sqlite3.connect(self.path,timeout=20,factory=ClosingConnection);con.row_factory=sqlite3.Row
  con.execute('PRAGMA foreign_keys=ON')
  return con
 def list(self):
  with self.connect() as con:
   con.execute('BEGIN')
   actor=self.auth.actor(self.token,con)
   if actor['role']=='Administrator':
    rows=con.execute('SELECT id,name,updated FROM projects ORDER BY updated DESC,id').fetchall()
   else:
    rows=con.execute('SELECT p.id,p.name,p.updated FROM projects p JOIN memberships m ON p.id=m.project_id WHERE m.user_id=? ORDER BY p.updated DESC,p.id',(actor['id'],)).fetchall()
   return [tuple(r) for r in rows]
 def save(self,project_id,state,expected_revision=None):
  serialized=encode_payload(state)
  now=datetime.now(timezone.utc).isoformat(timespec='microseconds')
  with self.connect() as con:
   con.execute('BEGIN IMMEDIATE')
   self.auth.authorize(self.token,project_id,True,con)
   row=con.execute('SELECT updated FROM projects WHERE id=?',(project_id,)).fetchone()
   if row is None:raise PermissionError('Project is unavailable.')
   if expected_revision is None or row['updated']!=expected_revision:
    raise ProjectConflictError('This project changed in another session. Export any unsaved work, then use Reload saved project to reopen the latest version.')
   con.execute('UPDATE projects SET name=?,updated=?,payload=? WHERE id=?',(state['name'],now,serialized,project_id))
  return now
 def create(self,state):
  serialized=encode_payload(state)
  now=datetime.now(timezone.utc).isoformat(timespec='microseconds')
  with self.connect() as con:
   con.execute('BEGIN IMMEDIATE');actor=self.auth.actor(self.token,con)
   if actor['role'] not in ('Administrator','Analyst'):raise PermissionError('Your role cannot create projects.')
   project_id=uuid.uuid4().hex
   con.execute('INSERT INTO projects VALUES (?,?,?,?)',(project_id,state['name'],now,serialized))
   con.execute('INSERT INTO memberships VALUES (?,?,?)',(actor['id'],project_id,'edit'))
   con.execute('INSERT INTO last_projects VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET project_id=excluded.project_id',(actor['id'],project_id))
   self.auth.event(con,actor['username'],'Created project',project_id)
  return project_id
 def load(self,project_id):
  with self.connect() as con:
   con.execute('BEGIN')
   self.auth.authorize(self.token,project_id,False,con)
   row=con.execute('SELECT payload,updated FROM projects WHERE id=?',(project_id,)).fetchone()
  if row is None:raise ValueError('Project no longer exists. Refresh the project list.')
  state=json.loads(row['payload'])
  if state['version']!=1:raise ValueError('Unsupported project version.')
  state['data']=restore_frame(state['data'],state.get('data_nonfinite',[]))
  state['original_data']=restore_frame(state.get('original_data'),state.get('original_nonfinite',[]))
  state['_revision']=row['updated']
  return state
