import hashlib
import streamlit as st
from datetime import datetime
from storage import ProjectStore,encode_payload
from auth_ui import auth_token,current_user,can_edit,require_edit
from security import AuthStore

SUMMARY='Operational performance review. All observed associations require human validation.'
LIMITS='Input data and KPI units must be verified by the data owner. No causal claims are made.'


def store():return ProjectStore(actor_token=auth_token())


def snapshot():
 s=st.session_state
 return dict(name=s.project_name,client=s.project_client,data=s.data,source=s.source,
             findings=s.findings,audit=s.audit,report=s.report,mapping=s.get('mapping',{}),
             targets=s.get('targets',[]),original_data=s.get('original_data'),quality_settings=s.get('quality_settings',{}))


def digest(state):return hashlib.sha256(encode_payload(state).encode()).hexdigest()


def save_project():
 # A viewer's exploratory widget state never writes to shared project storage.
 if not can_edit():return True
 try:
  state=snapshot();checksum=digest(state)
  if checksum==st.session_state.get('project_saved_digest'):return True
  updated=store().save(st.session_state.active_project,state,st.session_state.get('project_revision'))
  st.session_state.saved_at=updated;st.session_state.project_revision=updated
  st.session_state.project_saved_digest=checksum
  return True
 except Exception as exc:
  st.error(f'Project could not be saved. Your session data is still available. {exc}')
  return False


def clear_project():
 retained={k:st.session_state[k] for k in ['_auth_token','_auth_account_open','_auth_notice'] if k in st.session_state}
 for key in list(st.session_state):del st.session_state[key]
 st.session_state.update(retained)


def activate(project_id,state):
 clear_project()
 st.session_state.update(active_project=project_id,project_name=state['name'],project_client=state['client'],
                         data=state['data'],source=state['source'],findings=state['findings'],audit=state['audit'],
                         report=state.get('report',dict(summary=SUMMARY,assumptions=LIMITS)),mapping=state.get('mapping',{}),
                         targets=state.get('targets',[]),original_data=state.get('original_data'),quality_settings=state.get('quality_settings',{}),
                         project_revision=state['_revision'],saved_at=state['_revision'])
 st.session_state.project_saved_digest=digest(snapshot())
 AuthStore().remember_project(auth_token(),project_id)


def new_state(name,sample):
 user=current_user()
 return dict(name=name,client='Demo Client',data=sample(),source='Fictional demo data',findings=[],
             audit=[dict(time=datetime.now().isoformat(timespec='seconds'),actor=user['username'],action='Created project')],
             report=dict(summary=SUMMARY,assumptions=LIMITS))


def project_sidebar(sample):
 try:
  projects=store().list()
  ids=[p[0] for p in projects]
  if st.session_state.get('active_project') not in ids:
   clear_project()
   if projects:
    preferred=AuthStore().last_project(auth_token())
    target=preferred if preferred in ids else projects[0][0]
    activate(target,store().load(target))
   elif current_user()['role'] in ('Administrator','Analyst'):
    project_id=store().create(new_state('Operational Performance Review',sample))
    activate(project_id,store().load(project_id));projects=store().list();ids=[p[0] for p in projects]
   else:
    st.info('No projects are assigned to your account. Ask an administrator to grant project access.')
    st.stop()
  def open_selected():
   try:
    target=st.session_state.project_picker
    loaded=store().load(target)
    if save_project():activate(target,loaded)
   except Exception as exc:st.error(f'Could not open project: {exc}')
  def create_new():
   name=st.session_state.new_project_name.strip()
   if not name:st.error('Enter a project name.');return
   if not save_project():return
   try:
    project_id=store().create(new_state(name,sample));activate(project_id,store().load(project_id))
   except Exception as exc:st.error(f'Could not create project: {exc}')
  def reload_saved():
   try:activate(st.session_state.active_project,store().load(st.session_state.active_project))
   except Exception as exc:st.error(f'Could not reload project: {exc}')
  names={p[0]:p[1]+' · '+p[0][:6] for p in projects}
  st.sidebar.selectbox('Saved projects',ids,index=ids.index(st.session_state.active_project),format_func=names.get,key='project_picker')
  st.sidebar.button('Open selected project',on_click=open_selected,disabled=st.session_state.get('project_picker')==st.session_state.active_project)
  editable=can_edit()
  st.sidebar.text_input('Project name',key='project_name',disabled=not editable)
  st.sidebar.text_input('Client',key='project_client',disabled=not editable)
  st.sidebar.caption('Can edit this project' if editable else 'Read-only project access')
  if editable:st.sidebar.button('Save project now',on_click=save_project)
  if current_user()['role'] in ('Administrator','Analyst'):
   with st.sidebar.expander('Create a project'):
    st.text_input('New project name',key='new_project_name')
    st.button('Create project',on_click=create_new)
  latest=next(p[2] for p in projects if p[0]==st.session_state.active_project)
  if latest!=st.session_state.project_revision:
   st.warning('A newer saved version of this project exists. Export unsaved work before reloading. Your current session has not been overwritten.')
  with st.sidebar.expander('Reload latest saved version'):
   discard=st.checkbox('Discard my unsaved changes',key='discard_project_changes')
   st.button('Reload saved project',on_click=reload_saved,disabled=not discard)
  st.sidebar.caption('Allowed changes save automatically. Reload to see changes from other sessions.')
 except Exception as exc:
  st.error(f'Project workspace is unavailable: {exc}')
  st.stop()


def report_change(field,key):
 require_edit()
 st.session_state.report[field]=st.session_state[key]
