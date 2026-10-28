"""Validated analysis views over an unchanged source dataset."""
import json
import numpy as np
import pandas as pd
import streamlit as st

FIELDS = {
 'date': 'Date', 'location': 'Location', 'service': 'Service', 'team': 'Team',
 'volume': 'Volume', 'completed': 'Completed', 'cycle_time_min': 'Cycle time (minutes)',
 'sla_breach': 'Breach flag (0 or 1)', 'cost_inr': 'Cost (INR)',
}
NUMERIC = {'volume', 'completed', 'cycle_time_min', 'sla_breach', 'cost_inr'}
DATE_ORDERS = ['Year-month-day (ISO)', 'Day/month/year', 'Month/day/year']


def build_view(raw, config):
 """Return a mapped copy or reject the complete draft; never change raw data."""
 if not config:
  return raw.copy()
 columns = config.get('columns', {})
 errors = []
 if not raw.columns.is_unique:
  raise ValueError('Source column names must be unique.')
 if any(target not in FIELDS for target in columns):
  raise ValueError('Mapping contains an unknown OpsIntel field.')
 selected = {target: source for target, source in columns.items() if source is not None}
 if len(set(selected.values())) != len(selected):
  errors.append('Choose a different source column for each OpsIntel field.')
 for target, source in selected.items():
  if source not in raw.columns:
   errors.append(f'{FIELDS[target]}: source column {source!r} is missing.')
 if errors:
  raise ValueError('\n'.join(errors))
 rename = {source: target for target, source in selected.items()}
 names = [rename.get(c, c) for c in raw.columns]
 if len(set(names)) != len(names):
  raise ValueError('Mapping would create duplicate column names. A destination name already exists in your source. Map that existing column to another field or use it as the source for this field.')
 view = raw.rename(columns=rename).copy()
 date_order = config.get('date_order', DATE_ORDERS[0])
 if date_order not in DATE_ORDERS:
  raise ValueError('Choose a supported date format.')
 for target, source in selected.items():
  values = raw[source]
  present = values.notna() & values.astype(str).str.strip().ne('')
  if target == 'date':
   # ISO is strict; slash-separated dates require an explicit order.
   text = values.where(present)
   if pd.api.types.is_datetime64_any_dtype(values):
    parsed = pd.to_datetime(text, errors='coerce', utc=True)
   elif date_order == DATE_ORDERS[0]:
    iso = values.astype(str).str.match(r'^\d{4}-\d{2}-\d{2}(?:[T ].*)?$')
    parsed = pd.to_datetime(text.where(iso), format='ISO8601', errors='coerce', utc=True)
   else:
    parsed = pd.to_datetime(text, format='mixed', dayfirst=date_order == DATE_ORDERS[1], errors='coerce', utc=True)
   bad = present & parsed.isna()
   if bad.any():
    errors.append(f'{FIELDS[target]}: {int(bad.sum())} invalid dates (example: {values[bad].iloc[0]!r}). Choose the matching date format.')
   view[target] = parsed.dt.tz_convert(None)
  elif target in NUMERIC:
   parsed = pd.to_numeric(values.where(present), errors='coerce')
   bad = present & (parsed.isna() | ~np.isfinite(parsed))
   if bad.any():
    errors.append(f'{FIELDS[target]}: {int(bad.sum())} non-numeric or non-finite values (example: {values[bad].iloc[0]!r}). Use plain numbers without currency symbols or thousands separators.')
   if target == 'sla_breach' and (parsed.notna() & ~parsed.isin([0, 1])).any():
    errors.append('Breach flag must contain only 0, 1 or missing values.')
   view[target] = parsed
 if errors:
  raise ValueError('\n'.join(errors))
 return view


def clear_mapping_widgets():
 for key in list(st.session_state):
  if key.startswith('mapping_input_'):
   del st.session_state[key]


def replace_dataset(data, source):
 st.session_state.data = data
 st.session_state.source = source
 st.session_state.mapping = {}
 st.session_state.original_data = None
 st.session_state.quality_settings = {}
 st.session_state.comparison_settings = {}
 for key in list(st.session_state):
  if key.startswith('cmp_'):del st.session_state[key]
 st.session_state.pop('cleanup_preview',None)
 for key in list(st.session_state):
  if key.startswith('quality_input_'):del st.session_state[key]
 clear_mapping_widgets()


def mapping_workspace(raw, audit):
 st.subheader('Connect your columns')
 st.caption('Choose which source column supplies each OpsIntel field. Preview first, then apply. Your original data stays unchanged. Unmapped columns remain available by their original names; existing standard OpsIntel names still work.')
 applied = st.session_state.mapping
 defaults = applied.get('columns', {})
 with st.form('column_mapping'):
  draft = {}
  cols = st.columns(3)
  for index, (target, label) in enumerate(FIELDS.items()):
   options = [None] + list(raw.columns)
   default = defaults.get(target, target if target in raw else None)
   if default not in options:
    default = None
   with cols[index % 3]:
    draft[target] = st.selectbox(label, options, index=options.index(default),
                               format_func=lambda c: 'Not mapped' if c is None else str(c), key='mapping_input_'+target)
  order = applied.get('date_order', DATE_ORDERS[0])
  date_order = st.selectbox('Source date format', DATE_ORDERS, index=DATE_ORDERS.index(order), key='mapping_input_date_order')
  st.caption('Cycle time must be in minutes and cost in INR. Dates with timezone offsets are converted to UTC. Missing cells remain missing. Breach flags use 0/1. Mapping does not convert units.')
  preview = st.form_submit_button('Preview mapping')
  apply = st.form_submit_button('Apply mapping')
 config = {'columns': draft, 'date_order': date_order}
 if preview or apply:
  try:
   mapped = build_view(raw, config)
   st.markdown('**Mapped data preview**')
   st.dataframe(mapped.head(20), use_container_width=True, hide_index=True)
   st.caption(f'{len(mapped):,} rows retained. Blank mapped dates/numbers remain missing. No rows are dropped.')
   if apply:
    st.session_state.mapping = config
    if audit('Applied column mapping: '+json.dumps(config,ensure_ascii=False)):
     st.success('Mapping applied and saved to this project. All analysis pages now use these fields.')
    else:
     st.warning('Mapping is active in this session, but saving failed. Use Save project now to retry.')
  except (ValueError, TypeError) as exc:
   st.error(str(exc))
   st.info('Mapping was not applied. Fix the selections or source values and try again.')
 def reset():
  st.session_state.mapping = {}
  clear_mapping_widgets()
  audit('Removed column mapping; restored original source fields')
 st.button('Remove applied mapping', on_click=reset, disabled=not st.session_state.mapping)
 current = st.session_state.mapping
 if current:
  st.markdown('**Applied mapping**')
  st.dataframe(pd.DataFrame([{'OpsIntel field':FIELDS[k], 'Source column':v} for k,v in current['columns'].items() if v is not None]),use_container_width=True,hide_index=True)
 else:
  st.caption('No mapping applied. Analysis uses original source fields.')
 st.download_button('Export mapping JSON',json.dumps(current,indent=2),'mapping.json','application/json')
