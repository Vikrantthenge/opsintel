"""Print-ready period comparisons using the same calculations as the workspace."""
import io
import textwrap
from datetime import datetime,timezone
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,LongTable,TableStyle,Image,PageBreak,KeepTogether
from xml.sax.saxutils import escape
from reporting import register_fonts,WIDTH,NAVY,INK,MUTED,LINE,LIGHT,alert_number
from periods import compare_periods,LABELS


def image_from_figure(figure):
 buffer=io.BytesIO();figure.savefig(buffer,format='png',dpi=160,bbox_inches='tight');buffer.seek(0)
 image=Image(buffer);scale=WIDTH/image.imageWidth
 image.drawWidth=WIDTH;image.drawHeight=image.imageHeight*scale
 return image


def axes_style(ax):
 ax.set_facecolor('white');ax.tick_params(labelsize=8,colors='#52647B')
 for spine in ['top','right']:ax.spines[spine].set_visible(False)
 for spine in ['bottom','left']:ax.spines[spine].set_color('#D8E2EF')
 ax.set_axisbelow(True)


def comparison_figures(result):
 figures=[];metric=result['metric']
 if metric is None:return [('Performance charts',None,'No numeric chart metric is available.')]
 label=LABELS.get(metric,metric.replace('_',' ').title())+(' (%)' if metric=='sla_breach' else '')
 trend=result['trend']
 if trend.Value.notna().any():
  figure=Figure(figsize=(8,2.7),facecolor='white');ax=figure.subplots();axes_style(ax)
  for period,color in [('Baseline','#64748B'),('Comparison','#2563EB')]:
   data=trend[trend.Period.eq(period)]
   ax.plot(data.Day,data.Value.to_numpy(dtype=float,na_value=np.nan),label=period,color=color,linewidth=1.8,marker='o' if len(data)<15 else None,markersize=3)
  maximum=int(trend.Day.max());ax.set_xlim((1,maximum) if maximum>1 else (.5,1.5))
  ax.xaxis.set_major_locator(MaxNLocator(nbins=8,integer=True))
  ax.set_xlabel('Day of period (aligned from Day 1)',fontsize=8,color='#17263B')
  ax.set_ylabel('\n'.join(textwrap.wrap(label,38)),fontsize=8,color='#17263B')
  ax.grid(axis='y',color='#E5ECF5',linewidth=.6);ax.legend(frameon=False,fontsize=8,loc='lower left',bbox_to_anchor=(0,1.01),ncol=2)
  figure.tight_layout(pad=1)
  figures.append(('Daily performance',image_from_figure(figure),'Daily aggregation: '+result['aggregation']+'. Gaps are unavailable values, not verified zero activity. Per-day summary normalization is not applied again to daily charts.'))
 else:figures.append(('Daily performance',None,'No usable daily metric values in either period.'))
 for key,title in [('locations','Location comparison'),('services','Service comparison')]:
  table=result[key]
  if table.empty or not table[['Baseline','Comparison']].notna().any().any():
   figures.append((title,None,'No usable segment values or the required dimension is missing.'));continue
  selected=table.assign(_rank=table[['Baseline','Comparison']].abs().max(axis=1)).nlargest(12,'_rank').iloc[::-1]
  originals=selected.Segment.astype(str).tolist()
  labels=['\n'.join(textwrap.wrap(v if len(v)<=80 else v[:77]+'...',27)) for v in originals]
  positions=[];height=0
  for value in labels:
   span=max(2,len(value.splitlines())+.4);positions.append(height+span/2);height+=span
  figure=Figure(figsize=(8,max(2.65,height*.13+.9)),facecolor='white');ax=figure.subplots();axes_style(ax)
  ax.barh(np.array(positions)-.22,selected.Baseline.to_numpy(dtype=float,na_value=np.nan),height=.4,label='Baseline',color='#64748B')
  ax.barh(np.array(positions)+.22,selected.Comparison.to_numpy(dtype=float,na_value=np.nan),height=.4,label='Comparison',color='#2563EB')
  ax.set_yticks(positions,labels=labels)
  ax.set_xlabel('\n'.join(textwrap.wrap(label+(' per calendar day' if result['settings'].get('normalize') and result['aggregation']=='sum' else ''),65)),fontsize=8,color='#17263B')
  ax.grid(axis='x',color='#E5ECF5',linewidth=.6);ax.legend(frameon=False,fontsize=8,loc='lower left',bbox_to_anchor=(0,1.01),ncol=2)
  figure.tight_layout(pad=1)
  note='Period '+result['aggregation']+' values. Absent/unusable segments are not treated as zero.'
  if len(table)>12:note+=' Top 12 by either period’s absolute value shown; all segments appear in the tables.'
  if any(len(v)>80 for v in originals):note+=' Long labels shortened; tables and CSVs retain full values.'
  figures.append((title,image_from_figure(figure),note))
 return figures


def build_comparison_pdf(frame,config,project,client,source):
 register_fonts();result=compare_periods(frame,config)
 styles={
 'title':ParagraphStyle('comparison_title',fontName='OpsBold',fontSize=24,leading=29,textColor=NAVY,spaceAfter=12),
 'h1':ParagraphStyle('comparison_h1',fontName='OpsBold',fontSize=17,leading=22,textColor=NAVY,spaceAfter=12,keepWithNext=True),
 'h2':ParagraphStyle('comparison_h2',fontName='OpsBold',fontSize=11,leading=15,textColor=INK,spaceBefore=10,spaceAfter=6,keepWithNext=True),
 'body':ParagraphStyle('comparison_body',fontName='OpsRegular',fontSize=9,leading=14,textColor=INK,spaceAfter=8,splitLongWords=True),
 'small':ParagraphStyle('comparison_small',fontName='OpsRegular',fontSize=7.5,leading=11,textColor=MUTED,spaceAfter=7,splitLongWords=True),
 'cell':ParagraphStyle('comparison_cell',fontName='OpsRegular',fontSize=7,leading=10,textColor=INK,splitLongWords=True),
 'head':ParagraphStyle('comparison_head',fontName='OpsBold',fontSize=7,leading=10,textColor=colors.white)}
 def p(value,style='body'):return Paragraph(escape(str(value)).replace('\n','<br/>'),styles[style])
 def table(headers,rows,widths):
  t=LongTable([[p(h,'head') for h in headers]]+[[p(v,'cell') for v in row] for row in rows],colWidths=widths,repeatRows=1,splitInRow=1,hAlign='LEFT')
  t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),INK),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,LIGHT]),
   ('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,-1),.3,LINE),('LEFTPADDING',(0,0),(-1,-1),7),
   ('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
  return t
 def signed(value):return 'N/A' if value is None or pd.isna(value) else f'{value:+,.6g}'
 def change_rows(data,segment=False):
  return [[str(row['Segment'] if segment else row['Metric']),alert_number(row.Baseline),alert_number(row.Comparison),
           signed(row.Change),'N/A' if pd.isna(row['Relative change (%)']) else signed(row['Relative change (%)'])+'%',str(row.Unit)] for _,row in data.iterrows()]
 story=[p('Reporting-period comparison','title'),p(project,'h1'),p('Client: '+client),
        p('Source: '+source+'\nGenerated: '+datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M UTC'),'small')]
 story.append(p('Scope: saved comparison dates and location/service selections over the active mapped/cleaned dataset. Command Centre filters are independent.','small'))
 selections=[]
 for key,label in [('locations','Locations'),('services','Services')]:
  values=config.get(key)
  selections.append(label+': '+('All / unavailable dimension' if values is None else ', '.join('(Missing value)' if v is None else str(v) for v in values) if values else 'None selected'))
 story.append(p('\n'.join(selections),'small'))
 coverage=result['coverage']
 story.append(table(['Period','Date range','Calendar days','Days with records','Records'],
   [[r.Period,r.Start+' to '+r.End,str(r['Calendar days']),str(r['Days with records']),str(r.Records)] for _,r in coverage.iterrows()],
   [WIDTH*.17,WIDTH*.35,WIDTH*.16,WIDTH*.17,WIDTH*.15]))
 story.append(p(f'Baseline contains {len(result["baseline"]):,} reported rows; comparison contains {len(result["current"]):,}. The same segment selections apply to both periods.','small'))
 story.append(p('KPI changes','h2'))
 widths=[WIDTH*.30]+[WIDTH*.145]*4+[WIDTH*.12]
 story.append(table(['Metric','Baseline','Comparison','Change','Relative %','Unit'],change_rows(result['summary']),widths))
 story.append(p('Change = comparison minus baseline. Relative change = change / absolute baseline x 100. Relative change is N/A when the baseline is zero or unavailable. SLA absolute changes are percentage points. Numbers shown are rounded; calculations use unrounded values.','small'))
 if config.get('note'):
  story.extend([p('Analyst commentary','h2'),p(config['note'])])
 story.extend([p('Interpretation','h2'),p('Periods are inclusive; timezone-aware dates use UTC. Non-ISO source dates require mapping. Missing values are excluded. Non-finite measures or invalid SLA flags are unavailable. Per-day totals divide by all requested calendar days; this does not verify complete coverage. Unreported activity is not assumed to be zero. Changes are descriptive, not causal, and may reflect different location or service mix.','small')])
 if result['warnings']:
  story.append(p('Coverage and comparability notes','h2'))
  for warning in result['warnings']:
   if not warning.startswith('Additive measures are shown per requested calendar day'):story.append(p(warning,'small'))
 story.extend([PageBreak(),p('Performance comparisons','h1'),p('Chart metric: '+str(LABELS.get(result['metric'],result['metric'] or 'Not available'))+' | Calculation: '+result['aggregation'],'small')])
 for title,image,note in comparison_figures(result):
  content=[p(title,'h2')]
  if image is not None:content.append(image)
  content.append(p(note,'small'));story.append(KeepTogether(content))
 story.extend([PageBreak(),p('Location and service changes','h1')])
 for key,title in [('locations','Location changes'),('services','Service changes')]:
  data=result[key];story.append(p(title,'h2'))
  if data.empty:story.append(p('No segment comparison is available for the selected data.','small'));continue
  story.append(table(['Segment','Baseline','Comparison','Change','Relative %','Unit'],change_rows(data,True),widths))
  # Availability is separate from the numerical values to avoid interpreting absence as zero.
  availability=[[r.Segment,str(r['Baseline records']),str(r['Comparison records']),r.Status] for _,r in data.iterrows() if r.Status in ('Only in baseline','Only in comparison','Not comparable')]
  if availability:
   story.append(p('Availability exceptions','h2'))
   story.append(table(['Segment','Baseline rows','Comparison rows','Availability'],availability,[WIDTH*.4,WIDTH*.16,WIDTH*.18,WIDTH*.26]))
 story.extend([p('Calculation detail and sample sizes','h2')])
 details=[]
 for _,row in result['summary'].iterrows():
  details.append([row.Metric,f'{row["Baseline valid values"]} valid / {row["Baseline missing values"]} missing',
                  f'{row["Comparison valid values"]} valid / {row["Comparison missing values"]} missing',row.Detail or 'No calculation exception.'])
 story.append(table(['Metric','Baseline values','Comparison values','Notes'],details,[WIDTH*.26,WIDTH*.20,WIDTH*.20,WIDTH*.34]))
 output=io.BytesIO();doc=SimpleDocTemplate(output,pagesize=A4,leftMargin=44,rightMargin=44,topMargin=72,bottomMargin=48,title='OpsIntel reporting-period comparison',author='OpsIntel')
 def furniture(canvas,document):
  canvas.saveState();canvas.setFillColor(NAVY);canvas.rect(0,A4[1]-40,A4[0],40,fill=1,stroke=0)
  canvas.setFillColor(colors.white);canvas.setFont('OpsBold',10);canvas.drawString(44,A4[1]-25,'OPSINTEL  /  REPORTING-PERIOD COMPARISON')
  canvas.setStrokeColor(LINE);canvas.line(44,35,A4[0]-44,35);canvas.setFillColor(MUTED);canvas.setFont('OpsRegular',7)
  canvas.drawString(44,23,'OpsIntel 2.6  |  Saved comparison scope  |  Descriptive analysis');canvas.drawRightString(A4[0]-44,23,'Page '+str(document.page));canvas.restoreState()
 doc.build(story,onFirstPage=furniture,onLaterPages=furniture)
 return output.getvalue()
