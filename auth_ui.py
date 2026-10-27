"""Streamlit sign-in gate. UI state is never accepted as an authorization role."""
import json
import streamlit as st
from security import AuthStore,ROLES


def auth_token():return st.session_state.get('_auth_token')

def current_user():
 user=AuthStore().identity(auth_token())
 if not user or user['must_change']:raise PermissionError('Please sign in again.')
 return user

def can_edit():
 try:
  user=current_user()
  AuthStore().authorize(auth_token(),st.session_state.get('active_project'),write=True)
  return user['role'] in ('Administrator','Analyst')
 except PermissionError:return False


def require_edit():
 AuthStore().authorize(auth_token(),st.session_state.get('active_project'),write=True)


def clear_session():
 for key in list(st.session_state):del st.session_state[key]


def require_login():
 store=AuthStore()
 if not store.has_users():
  store.ensure_setup_key()
  st.title('Set up OpsIntel')
  st.info('Create the first administrator. Your existing projects will be available to this administrator.')
  st.caption('Open the setup-key.txt file in the app’s data folder and enter its contents below. This one-time key is created on this computer; there is no default password.')
  with st.form('first_admin',clear_on_submit=True):
   key=st.text_input('One-time setup key',type='password')
   username=st.text_input('Administrator username')
   display=st.text_input('Your name')
   password=st.text_input('Administrator password',type='password',help='At least 15 characters.')
   confirm=st.text_input('Confirm administrator password',type='password')
   submitted=st.form_submit_button('Create administrator')
  if submitted:
   try:
    if password!=confirm:raise ValueError('Passwords do not match.')
    store.bootstrap(username,display,password,key)
    clear_session();st.session_state._auth_notice='Administrator created. Sign in to continue.';st.rerun()
   except (ValueError,PermissionError) as exc:st.error(str(exc))
  st.stop()
 token=auth_token();user=store.identity(token,touch=True)
 if not user:
  # Expired/revoked sessions never retain a previous user’s project or drafts.
  notice=st.session_state.pop('_auth_notice',None)
  if token or st.session_state.get('active_project'):clear_session()
  st.title('Sign in to OpsIntel')
  if notice:st.success(notice)
  st.caption('Use your local account. Accounts and project permissions are managed by an administrator.')
  with st.form('sign_in',clear_on_submit=True):
   username=st.text_input('Username')
   password=st.text_input('Password',type='password')
   submitted=st.form_submit_button('Sign in')
  if submitted:
   result=store.login(username,password)
   if result:
    clear_session();st.session_state._auth_token=result;st.rerun()
   else:st.error('Sign-in failed. Check your credentials or try again in five minutes if repeated attempts were made.')
  st.stop()
 if user['must_change']:
  st.title('Set your own password')
  st.caption('Your administrator supplied a temporary password. Choose a new password before opening projects.')
  password_form(store,forced=True)
  if st.button('Sign out'):
   store.logout(token);clear_session();st.rerun()
  st.stop()
 return user


def password_form(store,forced=False):
 with st.form('change_password',clear_on_submit=True):
  current=st.text_input('Current password',type='password')
  new=st.text_input('New password',type='password',help='At least 15 characters.')
  confirm=st.text_input('Confirm new password',type='password')
  submitted=st.form_submit_button('Change password')
 if submitted:
  try:
   if new!=confirm:raise ValueError('Passwords do not match.')
   store.change_password(auth_token(),current,new)
   clear_session();st.session_state._auth_notice='Password changed. Sign in with your new password.';st.rerun()
  except (ValueError,PermissionError) as exc:st.error(str(exc))


def account_sidebar(user):
 st.sidebar.caption(f'Signed in: {user["display_name"]} · {user["role"]}')
 def logout():
  AuthStore().logout(auth_token());clear_session()
 st.sidebar.button('Sign out',on_click=logout)
 def toggle():st.session_state._auth_account_open=not st.session_state.get('_auth_account_open',False)
 st.sidebar.button('Back to workbench' if st.session_state.get('_auth_account_open') else 'Account & access',on_click=toggle)


def account_workspace(user):
 store=AuthStore()
 st.title('Account & access')
 st.caption(f'Account: {user["username"]} · {user["role"]}')
 st.subheader('Change your password')
 password_form(store)
 if user['role']!='Administrator':return
 st.divider();st.subheader('User administration')
 users=store.users(auth_token())
 st.dataframe([{k:v for k,v in u.items() if k!='id'} for u in users],use_container_width=True,hide_index=True)
 with st.expander('Create a user'):
  with st.form('create_user',clear_on_submit=True):
   username=st.text_input('New username')
   display=st.text_input('Display name')
   role=st.selectbox('New user role',ROLES,index=2)
   password=st.text_input('Temporary password',type='password',help='At least 15 characters. The user must change it at first sign-in.')
   create=st.form_submit_button('Create user')
  if create:
   try:
    store.create_user(auth_token(),username,display,password,role)
    st.session_state._auth_notice='User created. Assign project access below.';st.rerun()
   except (ValueError,PermissionError) as exc:st.error(str(exc))
 if st.session_state.get('_auth_notice'):st.success(st.session_state.pop('_auth_notice'))
 lookup={u['id']:u for u in users}
 selected=st.selectbox('Manage user',list(lookup),format_func=lambda k:lookup[k]['username'],key='manage_user')
 target=lookup[selected]
 with st.form('edit_user_'+selected):
  role=st.selectbox('Account role',ROLES,index=ROLES.index(target['role']))
  active=st.checkbox('Account active',value=bool(target['active']))
  update=st.form_submit_button('Save account changes')
 if update:
  try:
   store.update_user(auth_token(),selected,role,active)
   st.session_state._auth_notice='Account updated; that user’s sessions were revoked.';st.rerun()
  except (ValueError,PermissionError) as exc:st.error(str(exc))
 with st.expander('Reset selected user’s password'):
  with st.form('reset_password_'+selected,clear_on_submit=True):
   reset=st.text_input('New temporary password',type='password')
   submit=st.form_submit_button('Reset password')
  if submit:
   try:
    store.reset_password(auth_token(),selected,reset)
    st.session_state._auth_notice='Password reset. The user must sign in again and change it.';st.rerun()
   except (ValueError,PermissionError) as exc:st.error(str(exc))
 st.subheader('Project permissions')
 if target['role']=='Administrator':st.info('Administrators can view and edit every project, including projects imported from older releases.')
 else:
  from storage import ProjectStore
  projects=ProjectStore(actor_token=auth_token()).list()
  grants=store.memberships(auth_token(),selected)
  if projects:
   names={p[0]:p[1]+' · '+p[0][:6] for p in projects}
   project=st.selectbox('Project to assign',list(names),format_func=names.get,key='permission_project_'+selected)
   permissions=['No access','View']+(['Edit'] if target['role']=='Analyst' else [])
   existing={'view':'View','edit':'Edit'}.get(grants.get(project),'No access')
   with st.form('grant_'+selected+'_'+project):
    permission=st.selectbox('Project permission',permissions,index=permissions.index(existing) if existing in permissions else 0)
    submit=st.form_submit_button('Save project permission')
   if submit:
    try:
     store.grant(auth_token(),selected,project,{'No access':None,'View':'view','Edit':'edit'}[permission])
     st.session_state._auth_notice='Project permission saved.';st.rerun()
    except (ValueError,PermissionError) as exc:st.error(str(exc))
   st.dataframe([{'Project':names.get(k,k),'Permission':v} for k,v in grants.items()],use_container_width=True,hide_index=True)
  else:st.info('Create a project in the workbench before assigning access.')
 st.subheader('Security activity')
 events=store.audit(auth_token())
 st.dataframe(events,use_container_width=True,hide_index=True)
 st.caption('Showing the latest 2,000 security events. Passwords, setup keys and session tokens are never written to this log.')
 st.download_button('Export security activity JSON',json.dumps(events,indent=2),'opsintel_security_audit.json','application/json')
