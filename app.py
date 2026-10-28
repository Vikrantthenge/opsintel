import io, json
from datetime import datetime
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title='OpsIntel V2.6 | Operations Intelligence',page_icon='◈',layout='wide')
from ui import apply_theme, chart
from column_mapping import build_view, mapping_workspace, replace_dataset
apply_theme()
@st.cache_data
def sample():
 rng=np.random.default_rng(23); rows=[]
 for d in pd.date_range('2026-08-01',periods=60):
  for site in ['Mumbai','Pune','Bengaluru']:
   for team in ['Team A','Team B']:
    volume=int(rng.integers(30,110)); rate=float(np.clip(rng.normal(.89-(site=='Mumbai')*.09-(team=='Team B')*.04,.06),.5,1))
    rows.append(dict(date=d,location=site,team=team,service=['Fulfilment','Customer support'][team=='Team B'],volume=volume,completed=int(volume*rate),cycle_time_min=round(float(rng.normal(40+(site=='Mumbai')*12,7)),1),sla_breach=int(rng.random()>rate),cost_inr=round(float(rng.uniform(7000,18000)),2)))
 return pd.DataFrame(rows)
from projects import project_sidebar, save_project, report_change

def audit(action):
 st.session_state.audit.append({'time':datetime.now().isoformat(timespec='seconds'),'action':action})
 return save_project()
st.sidebar.title('◈ OpsIntel')
st.sidebar.caption('VERSION 2.6 · OPERATIONS INTELLIGENCE')
page=st.sidebar.radio('Workspace',['Command Centre','Period Comparison','Data Workspace','KPI Explorer','Targets & Alerts','Investigation','Client Report','Audit Trail'])
st.sidebar.divider()
project_sidebar(sample)
project=st.session_state.project_name
client=st.session_state.project_client
raw_df=st.session_state.data.copy()
mapping_valid=True
try:
 df=build_view(raw_df,st.session_state.mapping)
except (ValueError,TypeError) as exc:
 mapping_valid=False
 st.error('Saved mapping cannot be used: '+str(exc))
 st.info('Showing original data. Review or remove the mapping in Data Workspace.')
 df=raw_df.copy()
st.sidebar.markdown('**Active dataset**')
st.sidebar.caption(st.session_state.source)
if st.session_state.mapping:st.sidebar.caption('Column mapping active · saved with project')
if st.session_state.get('original_data') is not None:st.sidebar.caption('Cleanup active · pre-cleanup original retained')
st.sidebar.caption(f'{len(df):,} records · {len(df.columns)} columns')
st.sidebar.caption('Local project · data and findings saved on this computer')
st.caption('OPSINTEL / '+page.upper())
st.title('Executive Command Centre' if page=='Command Centre' else page)
st.caption('Premium Operations Intelligence Workbench · '+project)
if page=='Command Centre':
 from dashboard import command_centre
 command_centre(df)
elif page=='Period Comparison':
 if not mapping_valid:st.info('Fix or remove the saved mapping in Data Workspace before comparing periods.')
 else:
  from comparison_ui import comparison_workspace
  comparison_workspace(df,project,client,st.session_state.source,audit)
elif page=='Data Workspace':
 st.subheader('Upload and validate')
 upload=st.file_uploader('Upload CSV',type='csv')
 if upload:
  try:
   preview=pd.read_csv(upload);st.dataframe(preview.head(20));
   if st.button('Confirm and use this dataset'):
    replace_dataset(preview,upload.name);audit('Uploaded CSV '+upload.name);st.rerun()
  except Exception as e:st.error(str(e))
 pasted=st.text_area('Or paste CSV rows with a header')
 if st.button('Load pasted data') and pasted.strip():
  try:replace_dataset(pd.read_csv(io.StringIO(pasted)),'Manual CSV');audit('Loaded manual data');st.rerun()
  except Exception as e:st.error(str(e))
 if st.button('Restore fictional sample'):replace_dataset(sample(),'Fictional demo data');audit('Restored demo');st.rerun()
 st.subheader('Active source data')
 st.dataframe(raw_df.head(100),use_container_width=True)
 original=st.session_state.get('original_data')
 st.download_button('Export original CSV',(original if original is not None else raw_df).to_csv(index=False),'opsintel_original.csv','text/csv')
 from data_quality import quality_workspace
 quality_workspace(raw_df,audit)
 mapping_workspace(raw_df,audit)
elif page=='KPI Explorer':
 st.subheader('Configurable KPI exploration')
 st.caption('Use Targets & Alerts to save thresholds and evaluate performance gaps. The optional target below remains part of the recorded KPI definition.')
 numeric=list(df.select_dtypes(include='number').columns)
 if numeric:
  metric=st.selectbox('Metric',numeric);aggregation=st.selectbox('Calculation',['mean','sum','median','count']);dimension=st.selectbox('Segment',list(df.columns));target=st.number_input('Optional target',value=0.0)
  value=getattr(df[metric],aggregation)();st.metric(f'{aggregation.title()} {metric}',f'{value:,.2f}')
  result_name='Calculated value'
  while result_name in df.columns:result_name+='_'
  result=df.groupby(dimension,dropna=False)[metric].agg(aggregation).rename(result_name).reset_index();st.dataframe(result,use_container_width=True)
  chart(px.bar(result,x=dimension,y=result_name))
  if st.button('Record KPI definition'):audit(f'KPI {aggregation}({metric}) by {dimension}; target {target}')
 else:st.info('Upload numeric data to explore KPIs.')
elif page=='Targets & Alerts':
 from targets import target_workspace
 target_workspace(df,audit)
elif page=='Investigation':
 st.subheader('Evidence-based investigation')
 numeric=list(df.select_dtypes(include='number').columns)
 if numeric and len(df.columns)>1:
  metric=st.selectbox('Outcome',numeric);dimension=st.selectbox('Comparison dimension',[c for c in df.columns if c!=metric]);min_n=st.slider('Minimum group sample size',2,30,8)
  summary=df.groupby(dimension,dropna=False)[metric].agg(['count','mean','median','std']).reset_index();summary=summary[summary['count']>=min_n];st.dataframe(summary,use_container_width=True)
  if len(summary)>1:
   chart(px.bar(summary,x=dimension,y='mean',error_y='std'))
   st.info('These differences are hypotheses, not causal findings. Check sample size, confounding factors and operational context.')
  else:st.warning('Insufficient groups meeting the selected minimum sample size.')
  finding=st.text_area('Evidence / hypothesis');alternative=st.text_area('Alternative explanations');recommendation=st.text_area('Proposed validation step');approved=st.checkbox('Reviewed and approved by analyst')
  if st.button('Save finding'):
   if finding.strip():st.session_state.findings.append(dict(finding=finding,alternative=alternative,recommendation=recommendation,approved=approved,metric=metric,dimension=dimension));audit('Saved finding');st.success('Finding saved')
   else:st.error('Provide evidence before saving.')
 else:st.warning('Investigation needs a numeric metric and a separate comparison column.')
elif page=='Client Report':
 st.subheader('Client report')
 summary=st.text_area('Executive summary',st.session_state.report['summary'],key='report_summary',on_change=report_change,args=('summary','report_summary'))
 assumptions=st.text_area('Assumptions and limitations',st.session_state.report['assumptions'],key='report_assumptions',on_change=report_change,args=('assumptions','report_assumptions'))
 st.dataframe(pd.DataFrame(st.session_state.findings),use_container_width=True)
 from reporting import build_report
 numeric=list(df.select_dtypes(include='number').columns)
 metric=None
 if numeric:
  preferred=st.session_state.report.get('chart_metric','volume')
  metric=st.selectbox('Report chart metric',numeric,index=numeric.index(preferred) if preferred in numeric else 0,
                      key='report_chart_metric',on_change=report_change,args=('chart_metric','report_chart_metric'))
 st.caption('PDF scope: full active project dataset, including the applied mapping and cleanup. Command Centre filters are not applied. Only approved findings are included.')
 @st.cache_data(show_spinner=False)
 def report_pdf(data,source_data,project,client,source,summary,assumptions,findings,targets,mapping,quality_settings,original_rows,chart_metric):
  return build_report(data,source_data,project,client,source,summary,assumptions,findings,targets,mapping,quality_settings,original_rows,chart_metric)
 try:
  if not mapping_valid:raise ValueError('Fix or remove the saved column mapping in Data Workspace before generating a report.')
  original=st.session_state.get('original_data')
  with st.spinner('Preparing executive report with embedded charts...'):
   document=report_pdf(df,raw_df,project,client,st.session_state.source,summary,assumptions,st.session_state.findings,
                       st.session_state.targets,st.session_state.mapping,st.session_state.get('quality_settings',{}),
                       len(original) if original is not None else None,metric)
  st.download_button('Download PDF report',document,'opsintel_report.pdf','application/pdf')
 except Exception as exc:
  st.error('PDF could not be generated. Your CSV and JSON exports remain available. '+str(exc))
 st.download_button('Download CSV',df.to_csv(index=False),'opsintel_data.csv','text/csv')
 st.download_button('Download findings JSON',json.dumps(st.session_state.findings,indent=2),'findings.json','application/json')
else:
 st.subheader('Project audit trail');st.dataframe(pd.DataFrame(st.session_state.audit),use_container_width=True)
 st.download_button('Export audit trail',json.dumps(st.session_state.audit,indent=2),'audit.json','application/json')
st.divider();st.caption('OpsIntel V2.6 • Projects saved locally. No authentication. Use fictional or de-identified data only. Findings require human validation.')

if save_project():
 st.sidebar.caption("Saved locally · "+st.session_state.saved_at[:19].replace("T"," ")+" UTC")
