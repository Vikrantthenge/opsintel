"""Explicit diagnostics and preview-first cleanup over a recoverable source copy."""
import hashlib
import json
import numpy as np
import pandas as pd
import streamlit as st
from column_mapping import DATE_ORDERS


def source_spec(raw, mapping=None, saved=None):
 saved = saved or {}
 columns = (mapping or {}).get('columns', {})
 def source(role):
  value = columns.get(role,role if role in raw else None)
  return value if value in raw.columns else None
 numeric = [c for c in raw if pd.api.types.is_numeric_dtype(raw[c])]
 for role in ['volume','completed','cycle_time_min','sla_breach','cost_inr']:
  c = source(role)
  if c is not None and c not in numeric: numeric.append(c)
 spec = dict(date=source('date'),numeric=numeric,breach=source('sla_breach'),
             volume=source('volume'),completed=source('completed'),
             date_order=(mapping or {}).get('date_order',DATE_ORDERS[0]))
 for key in ['date','breach','volume','completed']:
  if key in saved: spec[key]=saved[key] if saved[key] in raw.columns else None
 if 'numeric' in saved:spec['numeric']=[c for c in saved['numeric'] if c in raw]
 if saved.get('date_order') in DATE_ORDERS:spec['date_order']=saved['date_order']
 return spec


def present_mask(series):
 return series.notna() & series.astype(str).str.strip().ne('')


def parse_dates(series, order):
 values=series.where(present_mask(series))
 if pd.api.types.is_datetime64_any_dtype(series):
  return pd.to_datetime(values,errors='coerce',utc=True).dt.tz_convert(None)
 text=values.astype('string').str.strip()
 if order==DATE_ORDERS[0]:
  iso=text.str.match(r'^\d{4}-\d{2}-\d{2}(?:[T ].*)?$',na=False)
  parsed=pd.to_datetime(text.where(iso),format='ISO8601',errors='coerce',utc=True)
 else:
  parsed=pd.to_datetime(text,format='mixed',dayfirst=order==DATE_ORDERS[1],errors='coerce',utc=True)
 return parsed.dt.tz_convert(None)


def scan_quality(raw, spec):
 issues=[]
 def add(mask,column,issue,severity='Review'):
  positions=np.flatnonzero(np.asarray(mask,dtype=bool))
  for pos in positions:
   value='' if column=='(row)' else str(raw.iloc[pos][column])[:200]
   issues.append({'Data row':int(pos)+1,'Column':column,'Issue':issue,'Severity':severity,'Value':value})
 blanks=pd.DataFrame({c:~present_mask(raw[c]) for c in raw},index=raw.index)
 for c in raw:
  add(blanks[c],c,'Missing value')
 add(raw.duplicated(keep='first'),'(row)','Duplicate row')
 add(blanks.all(axis=1),'(row)','Completely empty row')
 date=spec.get('date')
 if date in raw:
  add(present_mask(raw[date]) & parse_dates(raw[date],spec['date_order']).isna(),date,'Invalid date','Invalid')
 numeric=list(dict.fromkeys(spec.get('numeric',[])+[spec.get('breach'),spec.get('volume'),spec.get('completed')]))
 for c in numeric:
  if c not in raw:continue
  parsed=pd.to_numeric(raw[c].where(present_mask(raw[c])),errors='coerce')
  add(present_mask(raw[c]) & (parsed.isna() | ~np.isfinite(parsed)),c,'Invalid number','Invalid')
  add(parsed.notna() & np.isfinite(parsed) & parsed.lt(0),c,'Negative number (review meaning)')
 breach=spec.get('breach')
 if breach in raw:
  parsed=pd.to_numeric(raw[breach].where(present_mask(raw[breach])),errors='coerce')
  add(present_mask(raw[breach]) & ~parsed.isin([0,1]),breach,'Invalid breach flag','Invalid')
 volume,completed=spec.get('volume'),spec.get('completed')
 if volume in raw and completed in raw:
  v=pd.to_numeric(raw[volume],errors='coerce');c=pd.to_numeric(raw[completed],errors='coerce')
  add(c.notna() & v.notna() & np.isfinite(v) & np.isfinite(c) & c.gt(v),completed,'Completed exceeds volume','Invalid')
 return pd.DataFrame(issues,columns=['Data row','Column','Issue','Severity','Value'])


def preview_cleanup(raw,spec,plan):
 if spec.get('date') is not None and spec['date'] in set(spec.get('numeric',[])+[spec.get('breach'),spec.get('volume'),spec.get('completed')]):
  raise ValueError('The date column cannot also be a numeric column. Correct the diagnostic settings.')
 cleaned=raw.copy(deep=True)
 if plan.get('trim'):
  for c in cleaned:
   if cleaned[c].dtype==object or isinstance(cleaned[c].dtype,pd.StringDtype):
    cleaned[c]=cleaned[c].map(lambda v:v.strip() if isinstance(v,str) else v)
 if plan.get('blanks'):
  for c in cleaned:
   cleaned[c]=cleaned[c].mask(cleaned[c].map(lambda v:isinstance(v,str) and not v.strip()))
 invalid_replaced=0
 if plan.get('convert'):
  date=spec.get('date')
  if date in cleaned:
   parsed=parse_dates(cleaned[date],spec['date_order'])
   invalid_replaced+=int((present_mask(cleaned[date]) & parsed.isna()).sum())
   cleaned[date]=parsed
  numeric=list(dict.fromkeys(spec.get('numeric',[])+[spec.get('breach'),spec.get('volume'),spec.get('completed')]))
  for c in numeric:
   if c not in cleaned:continue
   values=pd.to_numeric(cleaned[c].where(present_mask(cleaned[c])),errors='coerce')
   bad=values.isna() | ~np.isfinite(values)
   if c==spec.get('breach'):bad=bad | ~values.isin([0,1])
   invalid_replaced+=int((present_mask(cleaned[c]) & bad).sum())
   cleaned[c]=values.mask(bad)
 if plan.get('drop_empty'):
  empty=pd.DataFrame({c:~present_mask(cleaned[c]) for c in cleaned},index=cleaned.index).all(axis=1)
  cleaned=cleaned[~empty]
 if plan.get('deduplicate'):cleaned=cleaned.drop_duplicates(keep='first')
 return cleaned.reset_index(drop=True),{'Input rows':len(raw),'Output rows':len(cleaned),
                                       'Removed rows':len(raw)-len(cleaned),'Invalid cells replaced':invalid_replaced}


def preview_key(raw,spec,plan):
 data=raw.to_json(orient='table',date_format='iso',index=False)+pd.util.hash_pandas_object(raw,index=True).values.tobytes().hex()
 return hashlib.sha256((data+json.dumps({'spec':spec,'plan':plan},sort_keys=True)).encode()).hexdigest()


def quality_workspace(raw,audit):
 st.subheader('Data quality & guided cleanup')
 st.caption('Choose the columns to check, then preview any cleanup. Negative numbers are flagged for review; they are never automatically removed. Data row numbers start at 1, excluding the CSV header.')
 defaults=source_spec(raw,st.session_state.mapping,st.session_state.get('quality_settings'))
 options=[None]+list(raw.columns)
 fmt=lambda c:'Not selected' if c is None else str(c)
 with st.form('quality_cleanup'):
  cols=st.columns(3)
  with cols[0]:
   date=st.selectbox('Date column to check',options,index=options.index(defaults['date']),format_func=fmt,key='quality_input_date')
   date_order=st.selectbox('Date format for quality checks',DATE_ORDERS,index=DATE_ORDERS.index(defaults['date_order']),key='quality_input_date_order')
  with cols[1]:
   breach=st.selectbox('Breach flag column to check',options,index=options.index(defaults['breach']),format_func=fmt,key='quality_input_breach')
   numeric=st.multiselect('Numeric columns to check',list(raw.columns),default=defaults['numeric'],key='quality_input_numeric')
  with cols[2]:
   volume=st.selectbox('Volume column to compare',options,index=options.index(defaults['volume']),format_func=fmt,key='quality_input_volume')
   completed=st.selectbox('Completed column to compare',options,index=options.index(defaults['completed']),format_func=fmt,key='quality_input_completed')
  st.markdown('**Optional cleanup steps**')
  trim=st.checkbox('Trim spaces around text',value=False,key='quality_input_trim')
  blanks=st.checkbox('Treat blank text as missing',value=False,key='quality_input_blanks')
  convert=st.checkbox('Convert checked dates/numbers; replace invalid values and breach flags with missing',value=False,key='quality_input_convert')
  st.caption('Conversion uses the selected date format, plain numeric values and 0/1 breach flags. Dates with timezone offsets become UTC. Conversion changes column types. It does not fill gaps, change units, fix negative values or adjust completed work.')
  drop_empty=st.checkbox('Remove completely empty rows',value=False,key='quality_input_drop_empty')
  deduplicate=st.checkbox('Remove exact duplicate rows (keep first)',value=False,key='quality_input_deduplicate')
  preview=st.form_submit_button('Check data & preview cleanup')
  apply=st.form_submit_button('Apply previewed cleanup')
 spec=dict(date=date,date_order=date_order,numeric=numeric,breach=breach,volume=volume,completed=completed)
 plan=dict(trim=trim,blanks=blanks,convert=convert,drop_empty=drop_empty,deduplicate=deduplicate)
 if preview or apply:
  try:
   candidate,stats=preview_cleanup(raw,spec,plan)
   key=preview_key(raw,spec,plan)
   if preview:
    st.session_state.quality_settings=spec
    st.session_state.cleanup_preview=dict(key=key,spec=spec,plan=plan,stats=stats)
   if apply:
    stored=st.session_state.get('cleanup_preview',{})
    if stored.get('key')!=key:
     st.error('Preview these exact settings first. Nothing has been changed.')
    elif not any(plan.values()):st.info('No cleanup steps selected. Your data is unchanged.')
    else:
     if st.session_state.get('original_data') is None:st.session_state.original_data=raw.copy(deep=True)
     st.session_state.data=candidate
     st.session_state.quality_settings=spec
     st.session_state.pop('cleanup_preview',None)
     saved=audit('Applied previewed cleanup: '+json.dumps({'settings':spec,'steps':plan,'results':stats}))
     st.session_state.cleanup_notice={'saved':saved,'message':'Cleanup applied. Original data is available to restore.' if saved else 'Cleanup applied in this session; saving failed. Use Save project now to retry.'}
     st.rerun()
  except (ValueError,TypeError) as exc:st.error(str(exc))
 if st.session_state.get('cleanup_notice'):
  notice=st.session_state.pop('cleanup_notice')
  (st.success if notice['saved'] else st.warning)(notice['message'])
 active_spec=source_spec(raw,st.session_state.mapping,st.session_state.get('quality_settings'))
 issues=scan_quality(raw,active_spec)
 missing=sum(int((~present_mask(raw[c])).sum()) for c in raw)
 for col,(name,value) in zip(st.columns(4),[('Records checked',len(raw)),('Missing cells',missing),('Duplicate rows',int(raw.duplicated().sum())),('Flagged issues',len(issues))]):
  col.metric(name,f'{value:,}')
 if raw.empty:st.info('No records to check. Load data to run quality diagnostics.')
 elif issues.empty:st.success('No issues found by the selected checks. This does not verify business accuracy or source completeness.')
 else:
  st.dataframe(issues.head(1000),use_container_width=True,hide_index=True)
  st.caption(f'Showing up to 1,000 of {len(issues):,} issue entries. A cell or row can have more than one issue. The download contains all entries. Value examples are limited to 200 characters; source data retains the full values.')
 st.download_button('Export quality issues CSV',issues.to_csv(index=False),'opsintel_quality_issues.csv','text/csv')
 profile=pd.DataFrame([dict(column=c,missing=int((~present_mask(raw[c])).sum()),unique=int(raw[c].nunique()),dtype=str(raw[c].dtype)) for c in raw])
 with st.expander('Column quality profile'):st.dataframe(profile,use_container_width=True,hide_index=True)
 stored=st.session_state.get('cleanup_preview')
 if stored:
  if stored['key']==preview_key(raw,stored['spec'],stored['plan']):
   candidate,stats=preview_cleanup(raw,stored['spec'],stored['plan'])
   st.markdown('**Cleanup preview - not yet applied**')
   st.write(stats)
   left,right=st.columns(2)
   with left:st.caption('Before (first 20 rows)');st.dataframe(raw.head(20),use_container_width=True,hide_index=True)
   with right:st.caption('After (first 20 rows)');st.dataframe(candidate.head(20),use_container_width=True,hide_index=True)
   remaining=scan_quality(candidate,stored['spec'])
   st.caption(f'Issue entries before: {len(scan_quality(raw,stored["spec"])):,}; after: {len(remaining):,}. Missing-value issues may increase when invalid values become missing.')
 def restore():
  original=st.session_state.get('original_data')
  if original is not None:
   st.session_state.data=original.copy(deep=True)
   st.session_state.original_data=None
   st.session_state.pop('cleanup_preview',None)
   audit('Restored original data before cleanup')
 st.button('Restore data before cleanup',on_click=restore,disabled=st.session_state.get('original_data') is None)
 st.caption('The original copy is saved with this project on the first cleanup. Further cleanup retains that same original. Importing a replacement dataset starts a new original-copy history. Existing findings and targets are retained; review them after data changes.')
 return issues
