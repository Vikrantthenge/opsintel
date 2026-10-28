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

class ClosingConnection(sqlite3.Connection):
 def __exit__(self,exc_type,exc_value,traceback):
  try:return super().__exit__(exc_type,exc_value,traceback)
  finally:self.close()

class ProjectStore:
 def __init__(self, path=None):
  self.path=Path(path) if path is not None else DB_PATH
  self.path.parent.mkdir(parents=True,exist_ok=True)
  with self.connect() as con:
   con.execute('CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, name TEXT NOT NULL, updated TEXT NOT NULL, payload TEXT NOT NULL)')
 def connect(self):
  return sqlite3.connect(self.path,timeout=15,factory=ClosingConnection)
 def list(self):
  with self.connect() as con:
   return con.execute('SELECT id,name,updated FROM projects ORDER BY updated DESC,id').fetchall()
 def save(self, project_id, state):
  payload=dict(state)
  payload['data']=state['data'].to_json(orient='table',date_format='iso',index=False)
  original=state.get('original_data')
  payload['original_data']=original.to_json(orient='table',date_format='iso',index=False) if original is not None else None
  payload['data_nonfinite']=nonfinite_cells(state['data'])
  payload['original_nonfinite']=nonfinite_cells(original)
  payload['version']=1
  serialized=json.dumps(payload,ensure_ascii=False,allow_nan=False)
  now=datetime.now(timezone.utc).isoformat(timespec='microseconds')
  with self.connect() as con:
   con.execute('INSERT INTO projects VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name, updated=excluded.updated,payload=excluded.payload',
               (project_id,state['name'],now,serialized))
  return now
 def create(self,state):
  project_id=uuid.uuid4().hex
  self.save(project_id,state)
  return project_id
 def load(self,project_id):
  with self.connect() as con:
   row=con.execute('SELECT payload FROM projects WHERE id=?',(project_id,)).fetchone()
  if row is None:raise ValueError('Project no longer exists. Refresh the project list.')
  state=json.loads(row[0])
  if state['version']!=1:raise ValueError('Unsupported project version.')
  state['data']=restore_frame(state['data'],state.get('data_nonfinite',[]))
  original=state.get('original_data')
  state['original_data']=restore_frame(original,state.get('original_nonfinite',[]))
  return state
