import streamlit as st
from datetime import datetime
from storage import ProjectStore

SUMMARY='Operational performance review. All observed associations require human validation.'
LIMITS='Input data and KPI units must be verified by the data owner. No causal claims are made.'

def snapshot():
 s=st.session_state
 return dict(name=s.project_name,client=s.project_client,data=s.data,source=s.source,
             findings=s.findings,audit=s.audit,report=s.report,mapping=s.get("mapping",{}),targets=s.get("targets",[]),original_data=s.get("original_data"),quality_settings=s.get("quality_settings",{}),comparison_settings=s.get("comparison_settings",{}))

def save_project():
 try:
  st.session_state.saved_at=ProjectStore().save(st.session_state.active_project,snapshot())
  return True
 except Exception as exc:
  st.error(f'Project could not be saved. Your session data is still available. {exc}')
  return False

def activate(project_id,state):
 # Clear page widgets on project changes so filters and drafts cannot leak.
 for key in list(st.session_state):
  del st.session_state[key]
 st.session_state.update(active_project=project_id,project_name=state['name'],project_client=state['client'],
                         data=state['data'],source=state['source'],findings=state['findings'],audit=state['audit'],
                         report=state.get('report',dict(summary=SUMMARY,assumptions=LIMITS)),mapping=state.get('mapping',{}),targets=state.get('targets',[]),original_data=state.get('original_data'),quality_settings=state.get('quality_settings',{}),comparison_settings=state.get('comparison_settings',{}))

def project_sidebar(sample):
 try:
  store=ProjectStore()
  if 'active_project' not in st.session_state:
   projects=store.list()
   if projects:
    activate(projects[0][0],store.load(projects[0][0]))
   else:
    state=dict(name='Operational Performance Review',client='Demo Client',data=sample(),source='Fictional demo data',
               findings=[],audit=[],report=dict(summary=SUMMARY,assumptions=LIMITS))
    project_id=store.create(state);activate(project_id,state)
  def open_selected():
   # Read before saving to avoid replacing the current workspace on a load failure.
   try:
    target=st.session_state.project_picker
    loaded=ProjectStore().load(target)
    if save_project():activate(target,loaded)
   except Exception as exc:st.error(f'Could not open project: {exc}')
  def create_new():
   name=st.session_state.new_project_name.strip()
   if not name:
    st.error('Enter a project name.');return
   if not save_project():return
   state=dict(name=name,client='',data=sample(),source='Fictional demo data',findings=[],
              audit=[dict(time=datetime.now().isoformat(timespec='seconds'),action='Created project')],
              report=dict(summary=SUMMARY,assumptions=LIMITS))
   try:
    project_id=ProjectStore().create(state);activate(project_id,state)
   except Exception as exc:st.error(f'Could not create project: {exc}')
  projects=store.list();names={p[0]:p[1]+' · '+p[0][:6] for p in projects};ids=list(names)
  st.sidebar.selectbox('Saved projects',ids,index=ids.index(st.session_state.active_project),format_func=names.get,key='project_picker')
  st.sidebar.button('Open selected project',on_click=open_selected,disabled=st.session_state.get('project_picker')==st.session_state.active_project)
  st.sidebar.text_input('Project name',key='project_name')
  st.sidebar.text_input('Client',key='project_client')
  st.sidebar.button('Save project now',on_click=save_project)
  with st.sidebar.expander('Create a project'):
   st.text_input('New project name',key='new_project_name')
   st.button('Create project',on_click=create_new)
  st.sidebar.caption('Automatically saved locally after changes. New projects start with fictional demo data.')
 except Exception as exc:
  st.error(f'Local project storage is unavailable: {exc}')
  st.stop()

def report_change(field,key):
 st.session_state.report[field]=st.session_state[key]
