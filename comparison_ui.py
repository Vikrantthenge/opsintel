"""Comparison workspace and exports, built on the existing no-login application."""
import json
from datetime import date as calendar_date
import pandas as pd
import plotly.express as px
import streamlit as st
from ui import chart
from periods import PRESETS,CALCULATIONS,LABELS,normalized_dates,preset_ranges,date_ranges,selected_aggregation,dimension_values,compare_periods


def display_number(value):
 return 'N/A' if value is None or pd.isna(value) else f'{value:,.6g}'


def styled_table(frame):
 columns=[c for c in ['Baseline','Comparison','Change','Relative change (%)'] if c in frame]
 return frame.style.format({c:'{:,.2f}' for c in columns},na_rep='N/A')


def segment_chart(table,title,key):
 if table.empty:
  st.info('No comparable segments available.');return
 if not table[['Baseline','Comparison']].notna().any().any():
  st.info('No usable metric values for this segment chart.');return
 top=table.assign(_rank=table[['Baseline','Comparison']].abs().max(axis=1)).nlargest(12,'_rank')
 long=top[['Segment','Baseline','Comparison']].melt(id_vars='Segment',var_name='Period',value_name='Value')
 fig=px.bar(long,x='Segment',y='Value',color='Period',barmode='group',title=title,
            color_discrete_map={'Baseline':'#B8C7DA','Comparison':'#60A5FA'})
 chart(fig,key=key)
 if len(table)>12:st.caption('Chart shows the 12 largest segments by either period’s absolute value; table and CSV include every segment.')


def comparison_workspace(frame,project,client,source,audit):
 st.markdown('''<style>
 .st-key-opsintel_run_comparison button,
 .stFormSubmitButton button,
 button[data-testid$="FormSubmit"],
 [data-testid="stFormSubmitButton"] button,
 button[data-testid="stBaseButton-primaryFormSubmit"],
 button[kind="primaryFormSubmit"] {
  background-color:#E2E8F0!important;color:#0B1220!important;
  -webkit-text-fill-color:#0B1220!important;
  border:2px solid #CBD5E1!important;border-radius:10px!important;
  min-height:48px;font-weight:700!important;
 }
 .st-key-opsintel_run_comparison button *,
 .stFormSubmitButton button *,
 button[data-testid$="FormSubmit"] *,
 [data-testid="stFormSubmitButton"] button *,
 button[data-testid="stBaseButton-primaryFormSubmit"] *,
 button[kind="primaryFormSubmit"] * {
  color:#0B1220!important;-webkit-text-fill-color:#0B1220!important;
  font-weight:700!important;
 }
 [data-testid="stFormSubmitButton"] button:hover {
  background-color:#CBD5E1!important;border-color:#94A3B8!important;
 }
 [data-testid="stFormSubmitButton"] button:focus-visible {
  outline:3px solid #FBBF24!important;outline-offset:3px;
 }
 </style>''',unsafe_allow_html=True)
 if 'date' not in frame:
  st.info('Connect a Date column in Data Workspace before comparing reporting periods.');return
 dates=normalized_dates(frame['date'])
 if not dates.notna().any():
  st.info('No usable dates are available. Use date mapping to interpret non-ISO source dates.');return
 saved=st.session_state.get('comparison_settings',{})
 st.caption('Choose two reporting periods and the same location/service filters. Press Run comparison to save the configuration and update the displayed results.')
 def reset_dates():
  for key in ['cmp_baseline','cmp_current']:
   if key in st.session_state:del st.session_state[key]
 preset=st.selectbox('Period preset',PRESETS,index=PRESETS.index(saved.get('preset',PRESETS[0])) if saved.get('preset',PRESETS[0]) in PRESETS else 0,key='cmp_preset',on_change=reset_dates)
 defaults=preset_ranges(dates.max(),preset)
 if saved and (saved.get('preset')==preset or preset==PRESETS[-1]):
  defaults.update({k:saved[k] for k in defaults if k in saved})
 bounds=[dates.min(),dates.max()]+[pd.Timestamp(defaults[k]) for k in defaults]
 minimum=calendar_date(max(1,min(v.year for v in bounds)-1),1,1)
 maximum=calendar_date(min(9999,max(v.year for v in bounds)+1),12,31)
 numeric=list(frame.select_dtypes(include='number').columns)
 metric_default=saved.get('metric','volume')
 if metric_default not in numeric:metric_default=numeric[0] if numeric else None
 with st.form('period_comparison'):
  left,right=st.columns(2)
  with left:baseline=st.date_input('Baseline period',value=(pd.Timestamp(defaults['baseline_start']).date(),pd.Timestamp(defaults['baseline_end']).date()),min_value=minimum,max_value=maximum,key='cmp_baseline')
  with right:current=st.date_input('Comparison period',value=(pd.Timestamp(defaults['current_start']).date(),pd.Timestamp(defaults['current_end']).date()),min_value=minimum,max_value=maximum,key='cmp_current')
  selections={}
  for col,dimension,label in [(left,'location','Locations to compare'),(right,'service','Services to compare')]:
   with col:
    if dimension in frame:
     values=dimension_values(frame[dimension]);options=sorted(values.dropna().unique(),key=str.casefold)
     if values.isna().any():options.append(None)
     prior=saved.get(dimension+'s')
     default=options if prior is None else [value for value in prior if value in options]
     selections[dimension+'s']=st.multiselect(label,options,default=default,format_func=lambda x:'(Missing value)' if x is None else str(x),key='cmp_'+dimension)
    else:
     selections[dimension+'s']=None
     st.caption('No '+dimension+' column available; that filter and comparison are omitted.')
  c1,c2=st.columns(2)
  with c1:
   metric=st.selectbox('Comparison chart metric',numeric or [None],index=numeric.index(metric_default) if numeric else 0,format_func=lambda x:'No numeric metric' if x is None else LABELS.get(x,x.replace('_',' ').title()),key='cmp_metric')
  with c2:
   calculation=st.selectbox('Chart calculation',CALCULATIONS,index=CALCULATIONS.index(saved.get('calculation','Default')) if saved.get('calculation','Default') in CALCULATIONS else 0,key='cmp_calculation')
  normalize=st.checkbox('Normalize additive measures per calendar day',value=bool(saved.get('normalize',False)),key='cmp_normalize')
  note=st.text_area('Comparison report commentary (optional)',value=saved.get('note',''),key='cmp_note')
  st.caption('Presets anchor to the latest valid date in the full dataset. Calendar presets include a full week/month and can be incomplete. Each period can span up to 3,660 days. Default calculation uses sums for volume/completed/cost and means for other fields. SLA requires 0/1 flags and is shown as a percentage.')
  st.markdown('**Ready? Click Run comparison below to generate or refresh your results.**')
  run=st.form_submit_button('Run comparison',type='primary',use_container_width=True,key='opsintel_run_comparison')
 if run:
  try:
   if len(baseline)!=2 or len(current)!=2:raise ValueError('Complete both date ranges before running a comparison.')
   config=dict(preset=preset,baseline_start=baseline[0].isoformat(),baseline_end=baseline[1].isoformat(),
               current_start=current[0].isoformat(),current_end=current[1].isoformat(),metric=metric,
               calculation=calculation,normalize=normalize,note=note,**selections)
   date_ranges(config);selected_aggregation(config)
   st.session_state.comparison_settings=config
   if audit('Ran reporting-period comparison: '+json.dumps(config,ensure_ascii=False)):
    st.success('Comparison settings saved to this project.')
   else:st.warning('Comparison is available in this session; saving failed. Use Save project now to retry.')
  except (ValueError,TypeError) as exc:st.error(str(exc))
 active=st.session_state.get('comparison_settings',{})
 if not active:
  st.info('Press Run comparison to generate the first result.');return
 try:result=compare_periods(frame,active)
 except (ValueError,TypeError,OverflowError) as exc:
  st.error(str(exc));return
 st.divider();st.subheader('Reporting-period results')
 st.caption(f'Baseline: {active["baseline_start"]} to {active["baseline_end"]} · Comparison: {active["current_start"]} to {active["current_end"]}. Results use the last run configuration and the latest active data.')
 for warning in result['warnings']:st.warning(warning)
 st.dataframe(result['coverage'],use_container_width=True,hide_index=True)
 summary=result['summary']
 for column,index in zip(st.columns(4),[0,1,3,4]):
  row=summary.iloc[index]
  change=row.Change
  suffix=' pp' if index==4 else ''
  delta=None if pd.isna(change) else f'{change:+,.4g}{suffix} vs baseline'
  value=display_number(row.Comparison)+('%' if index==4 and pd.notna(row.Comparison) else '')
  column.metric(row.Metric+' · comparison',value,delta,delta_color='off')
 st.subheader('KPI changes')
 visible=['Metric','Baseline','Comparison','Change','Relative change (%)','Unit','Status']
 st.dataframe(styled_table(summary[visible]),use_container_width=True,hide_index=True)
 st.caption('Change = comparison minus baseline. Relative change = change / absolute baseline × 100; N/A for a zero or unavailable baseline. SLA absolute changes are percentage points. Increases/decreases describe values, not business success. Displayed values are rounded; CSV exports retain calculation precision.')
 with st.expander('Metric sample sizes and calculation details'):
  st.dataframe(summary,use_container_width=True,hide_index=True)
 st.download_button('Export KPI comparison CSV',summary.to_csv(index=False),'opsintel_period_kpis.csv','text/csv')
 if result['metric'] is not None:
  label=LABELS.get(result['metric'],result['metric'])+(' (%)' if result['metric']=='sla_breach' else '')
  st.subheader('Performance aligned by day of period')
  trend=result['trend']
  if trend.Value.notna().any():
   fig=px.line(trend,x='Day',y='Value',color='Period',markers=True,hover_data={'Date':True,'Records':True},labels={'Value':label},
               color_discrete_map={'Baseline':'#B8C7DA','Comparison':'#60A5FA'})
   fig.update_traces(connectgaps=False)
   chart(fig,key='comparison_daily')
  else:st.info('No usable metric values for a daily trend.')
  st.caption('Day 1 aligns the start of each period. Gaps mean no usable reported value, not verified zero activity. Daily charts use daily aggregation; per-day normalization affects period summaries and segment comparisons only.')
  st.download_button('Export daily comparison CSV',trend.to_csv(index=False),'opsintel_period_daily.csv','text/csv')
 for title,key,dimension in [('Location changes','locations','location'),('Service changes','services','service')]:
  st.subheader(title)
  table=result[key]
  if dimension not in frame:st.info('No '+dimension+' column available.');continue
  segment_chart(table,title,'comparison_'+key)
  st.dataframe(styled_table(table),use_container_width=True,hide_index=True)
  st.caption('Segments are the union of both periods. An absent segment is unavailable for numerical change; it is not silently treated as zero.')
  st.download_button('Export '+dimension+' comparison CSV',table.to_csv(index=False),'opsintel_period_'+key+'.csv','text/csv')
 with st.expander('Inspect and export each period’s records'):
  for key,label in [('baseline','baseline'),('current','comparison')]:
   data=result[key].drop(columns=[result['date_key']])
   st.caption(label.title()+f': {len(data):,} records')
   st.dataframe(data.head(100),use_container_width=True,hide_index=True)
   st.download_button('Export '+label+' records CSV',data.to_csv(index=False),'opsintel_'+label+'_records.csv','text/csv')
 from comparison_report import build_comparison_pdf
 @st.cache_data(show_spinner=False)
 def cached_pdf(data,config,project,client,source):return build_comparison_pdf(data,config,project,client,source)
 try:
  with st.spinner('Preparing comparison report...'):document=cached_pdf(frame,active,project,client,source)
  st.download_button('Download comparison PDF',document,'opsintel_period_comparison.pdf','application/pdf')
 except Exception as exc:st.error('Comparison PDF could not be generated. CSV exports remain available. '+str(exc))
 st.download_button('Export comparison settings JSON',json.dumps(active,indent=2),'opsintel_comparison_settings.json','application/json')
