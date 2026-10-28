"""Portable, print-ready report generation with charts embedded as PNGs."""
import io
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape
import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure
from matplotlib.dates import AutoDateLocator, ConciseDateFormatter
import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,LongTable,Image,PageBreak,KeepTogether
from targets import evaluate_rules
from data_quality import scan_quality,source_spec,present_mask

NAVY=colors.HexColor('#0B1220');BLUE=colors.HexColor('#2563EB');INK=colors.HexColor('#17263B')
MUTED=colors.HexColor('#52647B');LINE=colors.HexColor('#D8E2EF');LIGHT=colors.HexColor('#F1F5F9')
WIDTH=A4[0]-88
LABELS={'volume':'Volume','completed':'Completed work','cycle_time_min':'Cycle time (minutes)',
        'sla_breach':'SLA breach rate (%)','cost_inr':'Cost (INR)'}


def register_fonts():
 fontdir=Path(matplotlib.get_data_path())/'fonts'/'ttf'
 if 'OpsRegular' not in pdfmetrics.getRegisteredFontNames():
  pdfmetrics.registerFont(TTFont('OpsRegular',str(fontdir/'DejaVuSans.ttf')))
  pdfmetrics.registerFont(TTFont('OpsBold',str(fontdir/'DejaVuSans-Bold.ttf')))
  pdfmetrics.registerFontFamily('OpsRegular',normal='OpsRegular',bold='OpsBold',italic='OpsRegular',boldItalic='OpsBold')


def number(value,suffix=''):
 return 'N/A' if value is None or pd.isna(value) or not np.isfinite(value) else f'{value:,.1f}{suffix}'


def alert_number(value):
 return 'N/A' if value is None or pd.isna(value) or not np.isfinite(value) else f'{float(value):,.6g}'


def executive_kpis(frame):
 def metric(key,method):
  if key not in frame or not pd.api.types.is_numeric_dtype(frame[key]):return None
  values=frame[key].dropna()
  if values.empty or not np.isfinite(values).all():return None
  if key=='sla_breach' and not values.isin([0,1]).all():return None
  result=float(getattr(values,method)())
  return result*100 if key=='sla_breach' else result
 return [('Records',f'{len(frame):,}'),('Total volume',number(metric('volume','sum'))),
         ('Avg cycle time',number(metric('cycle_time_min','mean'),' min')),
         ('SLA breach rate',number(metric('sla_breach','mean'),'%'))]


def chart_image(frame,metric,dimension):
 if metric not in frame or not pd.api.types.is_numeric_dtype(frame[metric]):return None,'No numeric metric available.'
 tmp=frame.copy()
 values=tmp[metric]
 invalid=values.notna() & ~np.isfinite(values)
 if invalid.any():return None,'Chart omitted because the selected metric contains non-finite values.'
 if metric=='sla_breach' and not values.dropna().isin([0,1]).all():
  return None,'SLA chart omitted because breach flags are not 0/1.'
 if dimension not in tmp:return None,f'No {dimension} column available.'
 note=''
 if dimension=='date':
  tmp['date']=pd.to_datetime(tmp['date'],format='mixed',errors='coerce',utc=True).dt.tz_convert(None).dt.normalize()
  excluded=int(tmp['date'].isna().sum())
  if excluded:note=f'{excluded:,} rows with missing/invalid dates excluded. '
  tmp=tmp[tmp.date.notna()]
 else:
  tmp=tmp[tmp[dimension].notna()]
 if tmp.empty or not tmp[metric].notna().any():return None,'No usable data for this chart.'
 group=tmp.groupby(dimension,dropna=False)[metric]
 totals=metric in ('volume','completed','cost_inr')
 result=group.sum(min_count=1) if totals else group.mean()
 result=result.dropna()
 if metric=='sla_breach':result*=100
 if result.empty:return None,'No usable values for this chart.'
 fig=Figure(figsize=(8.0,2.55),dpi=160,facecolor='white')
 ax=fig.subplots();ax.set_facecolor('white')
 if dimension=='date':
  result=result.sort_index()
  ax.plot(result.index,result.values,color='#2563EB',linewidth=2,marker='o' if len(result)<15 else None,markersize=3)
  if len(result)>1:ax.set_xlim(result.index.min(),result.index.max())
  locator=AutoDateLocator(minticks=3,maxticks=6)
  ax.xaxis.set_major_locator(locator);ax.xaxis.set_major_formatter(ConciseDateFormatter(locator))
 else:
  result=result.sort_values(ascending=False)
  if len(result)>12:result=result.head(12);note+='Top 12 segments by value shown. '
  result=result.iloc[::-1]
  originals=[str(v) for v in result.index]
  labels=['\n'.join(textwrap.wrap(v if len(v)<=80 else v[:77]+'...',28)) for v in originals]
  if any(len(v)>80 for v in originals):note+='Long category labels shortened; exports retain full values. '
  # More vertical room keeps multiple category labels legible.
  fig.set_size_inches(8.0,max(2.55,sum(len(v.splitlines()) for v in labels)*.16+.7))
  ax.barh(range(len(result)),result.values,color='#2563EB',height=.6)
  ax.set_yticks(range(len(result)),labels=labels)
 ax.tick_params(axis='both',labelsize=8,colors='#52647B')
 for spine in ['top','right']:ax.spines[spine].set_visible(False)
 for spine in ['left','bottom']:ax.spines[spine].set_color('#D8E2EF')
 ax.grid(axis='y' if dimension=='date' else 'x',color='#E5ECF5',linewidth=.6)
 ax.set_axisbelow(True)
 label=LABELS.get(metric,metric.replace('_',' ').title())
 if dimension=='date':ax.set_ylabel(label,fontsize=8,color='#17263B')
 else:ax.set_xlabel(label,fontsize=8,color='#17263B')
 fig.tight_layout(pad=1.0)
 buffer=io.BytesIO();fig.savefig(buffer,format='png',dpi=160,bbox_inches='tight');buffer.seek(0)
 image=Image(buffer)
 ratio=WIDTH/image.imageWidth
 image.drawWidth=WIDTH;image.drawHeight=image.imageHeight*ratio
 return image,note+('Totals by segment/date.' if totals else 'Row averages by segment/date; missing metric values excluded.')


def build_report(frame,source_data,project,client,source,summary,assumptions,findings,targets,
                 mapping=None,quality_settings=None,original_rows=None,chart_metric=None):
 register_fonts()
 styles={
  'title':ParagraphStyle('title',fontName='OpsBold',fontSize=25,leading=30,textColor=NAVY,spaceAfter=14),
  'h1':ParagraphStyle('h1',fontName='OpsBold',fontSize=17,leading=22,textColor=NAVY,spaceAfter=12),
  'h2':ParagraphStyle('h2',fontName='OpsBold',fontSize=11,leading=15,textColor=INK,spaceBefore=10,spaceAfter=6,keepWithNext=True),
  'body':ParagraphStyle('body',fontName='OpsRegular',fontSize=9,leading=14,textColor=INK,spaceAfter=8,splitLongWords=True),
  'small':ParagraphStyle('small',fontName='OpsRegular',fontSize=7.5,leading=11,textColor=MUTED,spaceAfter=6,splitLongWords=True),
  'cell':ParagraphStyle('cell',fontName='OpsRegular',fontSize=7.2,leading=10,textColor=INK,splitLongWords=True),
  'head':ParagraphStyle('head',fontName='OpsBold',fontSize=7.4,leading=10,textColor=colors.white),
 }
 def p(text,style='body'):
  return Paragraph(escape(str(text)).replace('\n','<br/>'),styles[style])
 story=[]
 def section(title):story.append(p(title,'h2'))
 def table(headers,rows,widths):
  t=LongTable([[p(h,'head') for h in headers]]+[[p(v,'cell') for v in row] for row in rows],
              colWidths=widths,repeatRows=1,hAlign='LEFT',splitInRow=1)
  t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),INK),('VALIGN',(0,0),(-1,-1),'TOP'),
                        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,LIGHT]),
                        ('LINEBELOW',(0,0),(-1,0),.5,LINE),('LINEBELOW',(0,1),(-1,-1),.3,LINE),
                        ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
                        ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
  return t
 generated=datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M UTC')
 story.extend([p('Executive operations review','title'),p(project,'h1'),p(f'Client: {client}'),
               p(f'Source: {source}\nGenerated: {generated}\nScope: full active project dataset; Command Centre filters are not applied.','small')])
 dates=pd.to_datetime(frame['date'],format='mixed',errors='coerce',utc=True) if 'date' in frame else None
 if dates is not None and dates.notna().any():story.append(p(f'Data period: {dates.min():%d %b %Y} to {dates.max():%d %b %Y} (valid dates)','small'))
 cards=[]
 for label,val in executive_kpis(frame):
  cards.append([p(label,'small'),Paragraph(escape(val),ParagraphStyle('kpi',fontName='OpsBold',fontSize=16,leading=20,textColor=NAVY))])
 # Use a vertical label/value stack in each panel.
 cardtable=Table([[Table([[c[0]],[c[1]]],colWidths=[WIDTH/4-18],style=TableStyle([('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)])) for c in cards]],colWidths=[WIDTH/4]*4)
 cardtable.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),LIGHT),('BOX',(0,0),(-1,-1),.5,LINE),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10)]))
 story.extend([Spacer(1,8),cardtable,Spacer(1,8),p('KPIs exclude missing values. Invalid/non-finite measures show N/A. SLA is the mean of 0/1 row flags, not a volume-weighted rate.','small')])
 section('Executive summary');story.append(p(summary))
 spec=source_spec(source_data,mapping,quality_settings)
 issues=scan_quality(source_data,spec)
 missing=sum(int((~present_mask(source_data[c])).sum()) for c in source_data)
 section('Data confidence snapshot')
 story.append(table(['Records','Missing cells','Duplicate rows','Issue entries'],[[f'{len(source_data):,}',f'{missing:,}',f'{source_data.duplicated().sum():,}',f'{len(issues):,}']],[WIDTH/4]*4))
 story.append(p('Issue entries may overlap. Checks cover selected source columns and do not establish completeness or business accuracy.','small'))
 if original_rows is not None:story.append(p(f'Cleanup active: {len(source_data):,} current rows; {original_rows:,} rows in the preserved pre-cleanup original.','small'))
 else:story.append(p('No applied cleanup backup is active.','small'))
 story.append(PageBreak());story.append(p('Operational performance','h1'))
 numeric=list(frame.select_dtypes(include='number').columns)
 metric=chart_metric if chart_metric in numeric else 'volume' if 'volume' in numeric else numeric[0] if numeric else None
 if metric is None:story.append(p('Charts unavailable: the dataset has no numeric metric.'))
 else:
  story.append(p('Selected chart metric: '+LABELS.get(metric,metric),'small'))
  for dimension,title in [('date','Performance over time'),('location','Location comparison'),('service','Service comparison')]:
   image,note=chart_image(frame,metric,dimension)
   if image is None:
    section(title);story.append(p(note,'small'))
   else:
    # Keep each chart with its title and calculation note.
    story.append(KeepTogether([p(title,'h2'),image,p(note,'small')]))
 story.append(PageBreak());story.append(p('Targets & data quality','h1'))
 section('Saved target results')
 alerts=evaluate_rules(frame,targets)
 if alerts.empty:story.append(p('No targets configured for this project.'))
 else:
  counts=alerts.Status.value_counts()
  story.append(p(' | '.join(f'{status}: {int(counts.get(status,0))}' for status in ['Critical','Warning','On target','Unavailable'])))
  rows=[]
  for _,row in alerts.iterrows():
   description=f'{row["Target"]}\n{row["Segment"]}\n{row["Metric"]} / {row["Calculation"]} / {row["Direction"]}\nUnits: {row["Units"]}; valid values: {row["Valid values"]}; missing: {row["Missing values"]}'
   if row['Detail']:description+='\n'+str(row['Detail'])
   rows.append([description,alert_number(row.Actual),alert_number(row['Target threshold']),alert_number(row['Critical threshold']),row.Status])
  t=table(['Target / segment','Actual','Target','Critical','Status'],rows,[WIDTH*.48,WIDTH*.13,WIDTH*.13,WIDTH*.13,WIDTH*.13])
  statuscolors={'Critical':'#FDE4E8','Warning':'#FFF2CC','On target':'#DFF5EC','Unavailable':'#E8EDF3'}
  for index,status in enumerate(alerts.Status,1):t.setStyle(TableStyle([('BACKGROUND',(4,index),(4,index),colors.HexColor(statuscolors[status]))]))
  story.append(t)
  story.append(p('Targets evaluated on the full dataset. Equality meets the target; reaching the critical threshold is critical. Unavailable is not a passing result. Thresholds are not prorated. Statuses use unrounded values; displayed numbers are rounded. In-app checks do not send external notifications.','small'))
 section('Quality checks')
 if source_data.empty:story.append(p('No source records available for quality checks.'))
 elif issues.empty:story.append(p('No issues found by the configured checks.'))
 else:
  counts=issues.groupby(['Issue','Severity'],dropna=False).size().reset_index(name='Entries')
  story.append(table(['Issue','Severity','Entries'],counts.astype(str).values.tolist(),[WIDTH*.63,WIDTH*.22,WIDTH*.15]))
 story.append(p('Download the full row-level issue log from Data Workspace. Diagnostic settings and mapping choices should be reviewed with the data owner.','small'))
 story.append(PageBreak());story.append(p('Approved findings & limitations','h1'))
 approved=[f for f in findings if f.get('approved')]
 story.append(p(f'{len(approved)} analyst-approved finding(s) included. Unapproved findings are excluded. Saved findings are historical records; review them after data or mapping changes.','small'))
 if not approved:story.append(p('No approved findings saved for this project.'))
 for index,finding in enumerate(approved,1):
  section(f'Finding {index}')
  story.append(p(f'Metric: {finding.get("metric","")} | Comparison: {finding.get("dimension","")}','small'))
  for key,label in [('finding','Evidence / hypothesis'),('alternative','Alternative explanations'),('recommendation','Proposed validation step')]:
   section(label);story.append(p(finding.get(key,'')))
 section('Assumptions and limitations');story.append(p(assumptions))
 story.append(p('This report is descriptive. Observed differences do not establish causality. Verify source coverage, metric units, date interpretation and operational context before acting.','small'))
 if mapping:
  section('Applied column mapping')
  rows=[[target,source] for target,source in mapping.get('columns',{}).items() if source is not None]
  if rows:story.append(table(['OpsIntel field','Source column'],rows,[WIDTH*.43,WIDTH*.57]))
  story.append(p('Date format: '+mapping.get('date_order','Not specified'),'small'))
 buffer=io.BytesIO()
 doc=SimpleDocTemplate(buffer,pagesize=A4,rightMargin=44,leftMargin=44,topMargin=72,bottomMargin=48,
                       title='OpsIntel executive operations review',author='OpsIntel')
 def furniture(canvas,document):
  canvas.saveState();canvas.setFillColor(NAVY);canvas.rect(0,A4[1]-40,A4[0],40,fill=1,stroke=0)
  canvas.setFont('OpsBold',10);canvas.setFillColor(colors.white);canvas.drawString(44,A4[1]-25,'OPSINTEL  /  OPERATIONS INTELLIGENCE')
  canvas.setStrokeColor(LINE);canvas.line(44,35,A4[0]-44,35)
  canvas.setFont('OpsRegular',7);canvas.setFillColor(MUTED)
  canvas.drawString(44,23,'OpsIntel 2.6  |  Full project dataset  |  Descriptive analysis')
  canvas.drawRightString(A4[0]-44,23,f'Page {document.page}')
  canvas.restoreState()
 doc.build(story,onFirstPage=furniture,onLaterPages=furniture)
 return buffer.getvalue()
