"""Saved project thresholds and on-demand, descriptive alert evaluation."""
import json
import math
import uuid
import numpy as np
import pandas as pd
import streamlit as st
from auth_ui import require_edit

AGGREGATIONS = ['mean', 'sum', 'median', 'count']
DIRECTIONS = ['At most', 'At least']
SCOPES = ['Overall', 'By location', 'By service']
LABELS = {'volume': 'Volume', 'completed': 'Completed', 'cycle_time_min': 'Cycle time (minutes)',
          'sla_breach': 'SLA breach rate (%)', 'cost_inr': 'Cost (INR)'}


def validate_rule(rule):
 if not str(rule.get('name', '')).strip():
  raise ValueError('Enter a target name.')
 if not rule.get('metric'):
  raise ValueError('Choose a numeric metric.')
 if rule.get('aggregation') not in AGGREGATIONS or rule.get('direction') not in DIRECTIONS or rule.get('scope') not in SCOPES:
  raise ValueError('Choose a supported calculation, direction and scope.')
 for field in ['target', 'critical']:
  if not isinstance(rule.get(field), (float, int)) or not math.isfinite(rule[field]):
   raise ValueError('Thresholds must be finite numbers.')
 if rule['metric'] == 'sla_breach':
  if rule['aggregation'] != 'mean':
   raise ValueError('SLA breach rate uses the mean of 0/1 flags, displayed as a percentage.')
  if not all(0 <= rule[k] <= 100 for k in ['target', 'critical']):
   raise ValueError('SLA breach thresholds must be percentages from 0 to 100.')
 if rule['direction'] == 'At most' and rule['critical'] <= rule['target']:
  raise ValueError('For At most, the critical threshold must be greater than the target.')
 if rule['direction'] == 'At least' and rule['critical'] >= rule['target']:
  raise ValueError('For At least, the critical threshold must be less than the target.')


def evaluate_rules(frame, rules):
 rows = []
 for rule in rules:
  base = {'Target': rule.get('name', ''), 'Metric': rule.get('metric', ''),
          'Calculation': rule.get('aggregation', ''),
          'Units': 'values' if rule.get('aggregation')=='count' else {'sla_breach':'%','cycle_time_min':'minutes','cost_inr':'INR'}.get(rule.get('metric'),'native units'),
          'Scope': rule.get('scope', ''),
          'Direction': rule.get('direction', ''), 'Target threshold': rule.get('target'),
          'Critical threshold': rule.get('critical')}
  def unavailable(detail, segment='All records', valid=0, missing=0):
   rows.append(dict(base, Segment=segment, Actual=None, Status='Unavailable',
                    **{'Valid values': valid, 'Missing values': missing, 'Detail': detail}))
  try:
   validate_rule(rule)
  except ValueError as exc:
   unavailable(str(exc)); continue
  metric = rule['metric']
  if metric not in frame:
   unavailable('Metric is missing. Review the target or column mapping.'); continue
  if not pd.api.types.is_numeric_dtype(frame[metric]):
   unavailable('Metric is not numeric. Review the source or column mapping.'); continue
  dimension = {'By location':'location', 'By service':'service'}.get(rule['scope'])
  if dimension and dimension not in frame:
   unavailable(f'{dimension.title()} column is missing.'); continue
  if frame.empty:
   unavailable('No records in the current view.'); continue
  groups = frame.groupby(dimension,dropna=False,sort=False) if dimension else [('All records',frame)]
  for segment, group in groups:
   segment = '(missing)' if pd.isna(segment) else str(segment)
   series = group[metric]
   missing = int(series.isna().sum())
   valid = int(series.notna().sum())
   values = series.dropna()
   if values.empty:
    unavailable('No non-missing metric values.',segment,valid,missing); continue
   if not np.isfinite(values).all():
    unavailable('Metric contains non-finite values.',segment,valid,missing); continue
   if metric == 'sla_breach' and not values.isin([0,1]).all():
    unavailable('SLA breach rate requires 0/1 flags.',segment,valid,missing); continue
   actual = float(getattr(values,rule['aggregation'])())
   if metric == 'sla_breach': actual *= 100
   if not math.isfinite(actual):
    unavailable('Calculation did not produce a finite value.',segment,valid,missing); continue
   if rule['direction'] == 'At most':
    status = 'Critical' if actual >= rule['critical'] else 'Warning' if actual > rule['target'] else 'On target'
   else:
    status = 'Critical' if actual <= rule['critical'] else 'Warning' if actual < rule['target'] else 'On target'
   rows.append(dict(base,Segment=segment,Actual=actual,Status=status,
                    **{'Valid values':valid,'Missing values':missing,'Detail':'Missing values excluded.' if missing else ''}))
 return pd.DataFrame(rows)


def show_alerts(frame, rules, filtered=False):
 st.subheader('Performance alerts')
 st.caption('Evaluated against the current Command Centre filters.' if filtered else 'Evaluated against the full active dataset. Command Centre alerts follow its filters.')
 if not rules:
  st.info('No targets configured. Open Targets & Alerts to set your first threshold.')
  return
 result = evaluate_rules(frame,rules)
 counts = result.Status.value_counts()
 critical, warning, unknown = [int(counts.get(s,0)) for s in ['Critical','Warning','Unavailable']]
 if critical: st.error(f'{critical} critical target result(s) need attention.')
 if warning: st.warning(f'{warning} target result(s) are outside the target range.')
 if unknown: st.info(f'{unknown} target result(s) could not be evaluated. Check the details below.')
 if not critical and not warning and not unknown:st.success('All evaluated targets are on track.')
 colors = {'Critical':'#FB7185','Warning':'#FBBF24','On target':'#34D399','Unavailable':'#B8C7DA'}
 styled = result.style.map(lambda status:f'background-color: {colors[status]}; color: #0B1220; font-weight: bold',subset=['Status']).format({'Actual':'{:,.2f}','Target threshold':'{:,.2f}','Critical threshold':'{:,.2f}'},na_rep='—')
 st.dataframe(styled,use_container_width=True,hide_index=True)
 st.caption('Equality meets the target. Reaching the critical threshold is critical. Statuses use unrounded values; displayed numbers are rounded. Missing values are excluded; no usable data is shown as Unavailable, never On target. These are in-app alerts evaluated when you interact with the app.')
 st.download_button('Export alert results CSV',result.to_csv(index=False),'opsintel_alerts.csv','text/csv',key='alerts_csv')


def target_workspace(frame, audit):
 require_edit()
 rules = st.session_state.targets
 st.caption('Save thresholds per project. Use At most for measures such as cycle time or breach rate, and At least for measures such as volume.')
 numeric = list(frame.select_dtypes(include='number').columns)
 choices = [None] + [r['id'] for r in rules]
 names = {r['id']:r['name'] for r in rules}
 selected = st.selectbox('Target to edit',choices,format_func=lambda x:'Create a new target' if x is None else names[x],key='target_editor')
 existing = next((r for r in rules if r['id']==selected),None)
 if existing and existing['metric'] not in numeric:
  numeric.append(existing['metric'])
 if numeric:
  # Separate form identities reset defaults when selecting a different saved target.
  with st.form('target_form_'+str(selected)):
   name = st.text_input('Target name',value=existing['name'] if existing else '',key='target_name_'+str(selected))
   metric = st.selectbox('Target metric',numeric,index=numeric.index(existing['metric']) if existing else 0,format_func=lambda x:LABELS.get(x,x))
   aggregation = st.selectbox('Target calculation',AGGREGATIONS,index=AGGREGATIONS.index(existing['aggregation']) if existing else 0)
   direction = st.selectbox('Target direction',DIRECTIONS,index=DIRECTIONS.index(existing['direction']) if existing else 0)
   scope = st.selectbox('Evaluate target',SCOPES,index=SCOPES.index(existing['scope']) if existing else 0)
   target = st.number_input('Target threshold',value=float(existing['target']) if existing else 0.0)
   critical = st.number_input('Critical threshold',value=float(existing['critical']) if existing else 1.0)
   st.caption('SLA breach rate uses mean and percentage thresholds (for example target 5, critical 10). Other calculations use the metric’s native units; count counts non-missing numeric values. Overall totals reflect the selected reporting period and filters; thresholds are not prorated.')
   save = st.form_submit_button('Save target')
  if save:
   rule = dict(id=selected or uuid.uuid4().hex,name=name.strip(),metric=metric,aggregation=aggregation,
               direction=direction,scope=scope,target=target,critical=critical)
   try:
    validate_rule(rule)
    st.session_state.targets = [r for r in rules if r['id']!=rule['id']] + [rule]
    if audit(('Updated' if selected else 'Created')+' target: '+json.dumps(rule)):
     st.session_state.target_notice='Target saved.'
     st.rerun()
    else: st.warning('Target is active in this session. Use Save project now to retry saving it.')
   except ValueError as exc:st.error(str(exc))
 else:st.info('Load numeric data to configure a target.')
 if st.session_state.pop('target_notice',None):st.success('Target saved.')
 if existing:
  confirm=st.checkbox('Confirm removal of this target',key='target_remove_confirm_'+selected)
  if st.button('Remove selected target',disabled=not confirm):
   st.session_state.targets=[r for r in rules if r['id']!=selected]
   audit('Removed target: '+existing['name'])
   del st.session_state['target_editor']
   st.rerun()
 show_alerts(frame,st.session_state.targets)
 st.download_button('Export target definitions JSON',json.dumps(st.session_state.targets,indent=2),'opsintel_targets.json','application/json')
