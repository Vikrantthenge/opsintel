"""Period comparison calculations over the existing mapped analysis view."""
import calendar
import math
import numpy as np
import pandas as pd

PRESETS=['Latest 7 days vs previous 7','Latest 30 days vs previous 30','Latest calendar week vs previous week','Latest calendar month vs previous month','Custom ranges']
CALCULATIONS=['Default','Sum','Mean','Median']
LABELS={'volume':'Volume','completed':'Completed','cycle_time_min':'Cycle time (minutes)','sla_breach':'SLA breach rate','cost_inr':'Cost (INR)'}
ROW_COUNT=object()
SUM_FIELDS={'volume','completed','cost_inr'}


def normalized_dates(series):
 if pd.api.types.is_datetime64_any_dtype(series):
  return pd.to_datetime(series,errors='coerce',utc=True).dt.tz_convert(None).dt.normalize()
 text=series.astype('string').str.strip()
 valid=text.str.match(r'^\d{4}-\d{2}-\d{2}(?:[T ].*)?$',na=False)
 return pd.to_datetime(text.where(valid),format='ISO8601',errors='coerce',utc=True).dt.tz_convert(None).dt.normalize()


def preset_ranges(anchor,preset):
 end=pd.Timestamp(anchor).normalize()
 if preset==PRESETS[2]:
  start=end-pd.Timedelta(days=end.weekday());end=start+pd.Timedelta(days=6)
  baseline_end=start-pd.Timedelta(days=1);baseline_start=baseline_end-pd.Timedelta(days=6)
 elif preset==PRESETS[3]:
  start=end.replace(day=1);end=start.replace(day=calendar.monthrange(start.year,start.month)[1])
  baseline_end=start-pd.Timedelta(days=1);baseline_start=baseline_end.replace(day=1)
 else:
  days=30 if preset==PRESETS[1] else 7
  start=end-pd.Timedelta(days=days-1)
  baseline_end=start-pd.Timedelta(days=1);baseline_start=baseline_end-pd.Timedelta(days=days-1)
 return dict(baseline_start=baseline_start.date().isoformat(),baseline_end=baseline_end.date().isoformat(),
             current_start=start.date().isoformat(),current_end=end.date().isoformat())


def date_ranges(config):
 out={}
 for period in ['baseline','current']:
  start=pd.Timestamp(config[period+'_start']).normalize()
  end=pd.Timestamp(config[period+'_end']).normalize()
  if pd.isna(start) or pd.isna(end) or start>end:raise ValueError('Each period needs a valid start date on or before its end date.')
  # Bound the timeline before allocating it; this also rejects dates outside Pandas' range.
  days=(end-start).days+1
  if days>3660:raise ValueError('Choose comparison periods of at most 3,660 calendar days each.')
  pd.date_range(start,end)
  out[period]=(start,end,days)
 return out


def default_aggregation(metric):return 'sum' if metric in SUM_FIELDS else 'mean'


def selected_aggregation(config):
 calculation=config.get('calculation','Default')
 if calculation not in CALCULATIONS:raise ValueError('Choose a supported chart calculation.')
 metric=config.get('metric')
 agg=default_aggregation(metric) if calculation=='Default' else calculation.lower()
 if metric=='sla_breach' and agg!='mean':raise ValueError('SLA breach rate must use Default or Mean over 0/1 flags.')
 return agg


def metric_value(frame,metric,aggregation,days=1,normalize=False):
 if metric is ROW_COUNT:return float(len(frame)),len(frame),0,''
 if metric not in frame:return None,0,len(frame),'Column missing.'
 if not pd.api.types.is_numeric_dtype(frame[metric]):return None,0,len(frame),'Column is not numeric; review the mapping.'
 values=frame[metric].dropna();missing=len(frame)-len(values)
 if values.empty:return None,0,missing,'No usable metric values.'
 if not np.isfinite(values).all():return None,len(values),missing,'Non-finite values; review source data.'
 if metric=='sla_breach' and not values.isin([0,1]).all():return None,len(values),missing,'SLA requires numeric 0/1 flags.'
 value=float(getattr(values,aggregation)())
 if not math.isfinite(value):return None,len(values),missing,'Calculation is non-finite.'
 if metric=='sla_breach':value*=100
 if normalize and aggregation=='sum':value/=days
 return value,len(values),missing,'Missing values excluded.' if missing else ''


def changes(baseline,current):
 if baseline is None or current is None:return None,None,'Not comparable'
 difference=current-baseline
 if not math.isfinite(difference):return None,None,'Not comparable'
 relative=difference/abs(baseline)*100 if baseline!=0 else None
 if relative is not None and not math.isfinite(relative):relative=None
 return difference,relative,'Increase' if difference>0 else 'Decrease' if difference<0 else 'No change'


def metric_unit(metric,aggregation,normalize):
 if metric is ROW_COUNT:return 'records'
 unit={'records':'records','volume':'volume','completed':'completed','cycle_time_min':'minutes','sla_breach':'%; change in pp','cost_inr':'INR'}.get(metric,'native units')
 return unit+'/day' if normalize and aggregation=='sum' else unit


def comparison_row(baseline,current,metric,aggregation,days_b,days_c,normalize,label):
 b,b_valid,b_missing,b_note=metric_value(baseline,metric,aggregation,days_b,normalize)
 c,c_valid,c_missing,c_note=metric_value(current,metric,aggregation,days_c,normalize)
 difference,relative,status=changes(b,c)
 return {'Metric':label,'Baseline':b,'Comparison':c,'Change':difference,'Relative change (%)':relative,
         'Unit':metric_unit(metric,aggregation,normalize),'Status':status,'Baseline valid values':b_valid,
         'Comparison valid values':c_valid,'Baseline missing values':b_missing,'Comparison missing values':c_missing,
         'Detail':' '.join(s for s in [('Baseline: '+b_note) if b_note else '',('Comparison: '+c_note) if c_note else ''] if s)}


def dimension_values(series):
 return series.map(lambda x:None if pd.isna(x) else str(x))


def filter_dimensions(frame,config):
 result=frame.copy()
 for dimension in ['location','service']:
  selected=config.get(dimension+'s')
  if dimension not in result:
   if selected is not None:raise ValueError('A saved '+dimension+' filter is unavailable. Review the filters and run the comparison again.')
   continue
  if selected is None:continue
  result=result[dimension_values(result[dimension]).isin(selected)]
 return result


def segments(baseline,current,dimension,metric,aggregation,days_b,days_c,normalize):
 columns=['Segment','Baseline','Comparison','Change','Relative change (%)','Unit','Status','Baseline records','Comparison records','Detail']
 if dimension not in baseline or metric is None:return pd.DataFrame(columns=columns)
 def key(series):return dimension_values(series).map(lambda x:'m:' if x is None else 'v:'+x)
 b_keys=key(baseline[dimension]);c_keys=key(current[dimension])
 keys=sorted(set(b_keys)|set(c_keys),key=lambda x:(x=='m:',x.casefold()))
 rows=[]
 for value in keys:
  b=baseline[b_keys.eq(value)];c=current[c_keys.eq(value)]
  row=comparison_row(b,c,metric,aggregation,days_b,days_c,normalize,'')
  row.pop('Metric');row['Segment']='(Missing value)' if value=='m:' else value[2:]
  row['Baseline records']=len(b);row['Comparison records']=len(c)
  if not len(b):row['Status']='Only in comparison'
  elif not len(c):row['Status']='Only in baseline'
  rows.append(row)
 return pd.DataFrame(rows) if rows else pd.DataFrame(columns=columns)


def compare_periods(frame,config):
 if 'date' not in frame:raise ValueError('Map a Date column in Data Workspace to compare periods.')
 ranges=date_ranges(config);agg=selected_aggregation(config);metric=config.get('metric')
 if metric is not None and (metric not in frame or not pd.api.types.is_numeric_dtype(frame[metric])):
  raise ValueError('The saved chart metric is unavailable. Choose another metric and run the comparison again.')
 filtered=filter_dimensions(frame,config)
 dates=normalized_dates(filtered['date']);invalid=int(dates.isna().sum())
 date_key='_opsintel_period_date'
 while date_key in filtered:date_key+='_'
 filtered[date_key]=dates
 periods={};coverage=[];warnings=[]
 for period,label in [('baseline','Baseline'),('current','Comparison')]:
  start,end,days=ranges[period]
  selected=filtered[dates.between(start,end,inclusive='both')].copy()
  observed=selected[date_key].nunique()
  periods[period]=selected
  coverage.append({'Period':label,'Start':str(start.date()),'End':str(end.date()),'Calendar days':days,
                   'Days with records':int(observed),'Days without records':days-int(observed),'Records':len(selected)})
  if selected.empty:warnings.append(label+' period has no records after filters; measures without data are unavailable.')
  elif observed<days:warnings.append(f'{label} period has records on {observed} of {days} requested calendar days. Coverage may be incomplete.')
 if invalid:warnings.append(f'{invalid:,} rows within the selected location/service filters have missing, invalid or ambiguous dates and are excluded. Use date mapping to interpret non-ISO source dates.')
 b,c=periods['baseline'],periods['current'];db,dc=ranges['baseline'][2],ranges['current'][2]
 if db!=dc:warnings.append(f'Periods have different lengths ({db} and {dc} calendar days). '+('Additive measures use per-day normalization.' if config.get('normalize') else 'Consider per-day normalization for additive measures.'))
 overlap=max(0,(min(ranges['baseline'][1],ranges['current'][1])-max(ranges['baseline'][0],ranges['current'][0])).days+1)
 if overlap:warnings.append(f'The periods overlap by {overlap} calendar day(s). The same source rows can appear in both periods.')
 normalize=bool(config.get('normalize',False))
 if normalize:warnings.append('Additive measures are shown per requested calendar day. Missing days are unverified; normalization does not establish complete coverage. Records remain raw row counts.')
 definitions=[(ROW_COUNT,'count','Records'),('volume','sum','Total volume'),('completed','sum','Completed'),
              ('cycle_time_min','mean','Average cycle time'),('sla_breach','mean','SLA breach rate'),('cost_inr','sum','Total cost (INR)')]
 if metric is not None and (metric,agg) not in [(m,a) for m,a,_ in definitions]:
  definitions.append((metric,agg,metric.replace('_',' ').title()+' ('+agg+')'))
 summary=pd.DataFrame([comparison_row(b,c,m,a,db,dc,normalize,label+(' / day' if normalize and a=='sum' else '')) for m,a,label in definitions])
 trend_rows=[]
 if metric is not None:
  for period,label in [('baseline','Baseline'),('current','Comparison')]:
   start,end,days=ranges[period];subset=periods[period]
   grouped={date:group for date,group in subset.groupby(date_key)}
   for offset,date in enumerate(pd.date_range(start,end),1):
    group=grouped.get(date)
    value,valid,missing,note=metric_value(group,metric,agg) if group is not None else (None,0,0,'No records for this day.')
    trend_rows.append({'Period':label,'Date':date,'Day':offset,'Value':value,'Records':len(group) if group is not None else 0,'Detail':note})
 return dict(settings=dict(config),baseline=b,current=c,summary=summary,coverage=pd.DataFrame(coverage),warnings=warnings,
             locations=segments(b,c,'location',metric,agg,db,dc,normalize),services=segments(b,c,'service',metric,agg,db,dc,normalize),
             trend=pd.DataFrame(trend_rows,columns=['Period','Date','Day','Value','Records','Detail']),metric=metric,aggregation=agg,
             date_key=date_key,invalid_dates=invalid,overlap_days=overlap)
