import pandas as pd
import plotly.express as px
import streamlit as st
from ui import chart
from targets import show_alerts
LABELS={'volume':'Total volume','completed':'Completed','cycle_time_min':'Cycle time (min)','sla_breach':'SLA breach rate (%)','cost_inr':'Cost (INR)'}
def aggregate(frame,dimension,metric):
 result=frame.groupby(dimension,as_index=False)[metric].agg('sum' if metric in ('volume','completed','cost_inr') else 'mean')
 if metric=='sla_breach': result[metric]*=100
 return result

def command_centre(df):
 filtered=df.copy(); previous=None
 dates=pd.to_datetime(df['date'],errors='coerce') if 'date' in df else None
 cols=st.columns([1.4,1,1])
 with cols[0]:
  if dates is not None and dates.notna().any():
   lo,hi=dates.min().date(),dates.max().date()
   selected=st.date_input('Reporting period',value=(lo,hi),min_value=lo,max_value=hi)
   if not isinstance(selected,(tuple,list)) or len(selected)!=2:
    st.info('Select an end date to complete the period.');return
   start,end=map(pd.Timestamp,selected);span=end-start+pd.Timedelta(days=1)
   filtered=filtered[dates.between(start,end+pd.Timedelta(days=1),inclusive='left')]
   previous=df[dates.between(start-span,start,inclusive='left')].copy()
   if dates.isna().any():st.caption(f'{dates.isna().sum()} rows with invalid dates excluded.')
  else:st.caption('Date filtering requires a valid date column.')
 for col,dimension,label in [(cols[1],'location','Locations'),(cols[2],'service','Services')]:
  with col:
   if dimension in df:
    options=sorted(df[dimension].dropna().unique(),key=str)
    choices=st.multiselect(label,options,default=options)
    filtered=filtered[filtered[dimension].isin(choices)]
    if previous is not None:previous=previous[previous[dimension].isin(choices)]
   else:st.caption(f'Add a {dimension} column to enable this filter.')
 st.caption(f'{len(filtered):,} of {len(df):,} records in view · filters apply to every KPI and chart below')
 if filtered.empty:
  show_alerts(filtered,st.session_state.get('targets',[]),filtered=True)
  st.info('No records match these filters. Adjust the selections to continue.');return
 def value(frame,key):
  if key=='records':return len(frame)
  if key not in frame or not pd.api.types.is_numeric_dtype(frame[key]) or not frame[key].notna().any():return None
  return frame[key].sum() if key=='volume' else frame[key].mean()*(100 if key=='sla_breach' else 1)
 for col,(label,key,unit) in zip(st.columns(4),[('Records','records',''),('Total volume','volume',''),('Avg cycle time','cycle_time_min',' min'),('SLA breach rate','sla_breach','%')]):
  v=value(filtered,key);prior=value(previous,key) if previous is not None and len(previous) else None
  delta=f'{v-prior:+,.1f}{" pp" if key=="sla_breach" else unit}' if v is not None and prior is not None else None
  col.metric(label,f'{v:,.1f}{unit}' if v is not None else 'N/A',delta=delta,delta_color='inverse' if key in ('cycle_time_min','sla_breach') else 'normal')
 st.caption('Changes compare the preceding period of equal length with the same segment filters. SLA assumes a 0/1 breach flag per row.')
 show_alerts(filtered,st.session_state.get('targets',[]),filtered=True)
 numeric=list(filtered.select_dtypes(include='number').columns)
 if not numeric:st.info('Upload numeric columns to see charts.');return
 st.divider();st.subheader('Operational performance')
 metric=st.selectbox('Trend metric',numeric,format_func=lambda x:LABELS.get(x,x.replace('_',' ').title()))
 if dates is not None and dates.notna().any():
  tmp=filtered.copy();tmp['date']=pd.to_datetime(tmp['date'],errors='coerce').dt.normalize()
  chart(px.line(aggregate(tmp,'date',metric),x='date',y=metric,markers=True,labels=LABELS))
 else:st.info('A valid date column is needed for trends.')
 st.subheader('Location & service comparisons')
 metric2=st.selectbox('Comparison metric',numeric,format_func=lambda x:LABELS.get(x,x.replace('_',' ').title()))
 for col,dimension in zip(st.columns(2),['location','service']):
  with col:
   st.markdown('**By '+dimension+'**')
   if dimension in filtered:chart(px.bar(aggregate(filtered,dimension,metric2),x=dimension,y=metric2,color=dimension,labels=LABELS))
   else:st.info(f'Add a {dimension} column to enable this comparison.')
 st.caption('Volume, completed work and cost use totals. Other metrics use row averages; comparisons are descriptive.')
 with st.expander('Inspect filtered records'):
  st.dataframe(filtered,use_container_width=True,hide_index=True)
  st.download_button('Export filtered CSV',filtered.to_csv(index=False),'opsintel_filtered.csv','text/csv')
