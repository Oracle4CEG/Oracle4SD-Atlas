"""Compact vector epoch-support illustration from retained native records."""
from pathlib import Path
import argparse, json, base64, io
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as md
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Rectangle
from fontTools import subset
from fontTools.ttLib import TTFont

p=argparse.ArgumentParser();p.add_argument('--font-dir',type=Path,required=True);a=p.parse_args()
root=Path(__file__).resolve().parents[1]
data=pd.read_csv(root/'supplementary/temporal/epoch_figure_data.csv')
font=next(x for x in a.font_dir.iterdir() if x.name.lower()=='times.ttf')
fp=FontProperties(fname=font)
assert fp.get_name()=='Times New Roman'
plt.rcParams.update({'svg.fonttype':'none','pdf.fonttype':42,'svg.hashsalt':'oracle4sd-time-v1'})
fig,ax=plt.subplots(figsize=(166/25.4,43/25.4))
fig.subplots_adjust(left=.15,right=.97,bottom=.26,top=.79)
start=pd.Timestamp('2026-06-11',tz='UTC');end=pd.Timestamp('2026-07-01T18:00:00Z')
for day in pd.date_range(start,end,freq='D'):ax.axvline(day,color='#E8E9ED',lw=.45,zorder=0)
for _,r in data.iterrows():
    y=1 if r['branch']=='Flare FTSOv2' else 0
    x=md.date2num(pd.Timestamp(r['start_utc']));z=md.date2num(pd.Timestamp(r['end_utc']))
    ax.add_patch(Rectangle((x,y-.22),z-x,.44,facecolor='#6454B3',alpha=.17 if int(r['epoch_id'])%2 else .31,edgecolor='#6454B3',lw=.65))
    ax.text((x+z)/2,y,str(r['epoch_id']),fontproperties=fp,fontsize=8.5,ha='center',va='center',color='#22252D')
    ax.plot(z,y,marker='D',markersize=3,markerfacecolor='#6454B3',markeredgecolor='#6454B3',lw=0)
cut=pd.Timestamp('2026-06-30T23:59:59Z');ax.axvline(cut,color='#BD5B49',linestyle='--',lw=.8)
ax.text(md.date2num(cut),1.48,'Cutoff',fontproperties=fp,fontsize=8.5,ha='center',color='#BD5B49')
ax.text(0,1.17,'Retained epoch support',transform=ax.transAxes,fontproperties=fp,fontsize=9)
ax.set_xlim(start,end);ax.set_ylim(-.5,1.5)
ax.set_yticks([0,1],['Pyth OIS','Flare FTSOv2'])
ax.set_xticks(pd.to_datetime(['2026-06-11','2026-06-15','2026-06-19','2026-06-23','2026-06-27','2026-07-01'],utc=True))
ax.xaxis.set_major_formatter(md.DateFormatter('%d %b',tz='UTC'))
for t in ax.get_xticklabels()+ax.get_yticklabels():t.set_fontproperties(fp);t.set_fontsize(8.5)
ax.tick_params(axis='both',length=0,pad=5)
for s in ax.spines.values():s.set_visible(False)
stem=root/'figures/temporal_epoch_support'
fig.savefig(stem.with_suffix('.pdf'));fig.savefig(stem.with_suffix('.svg'));fig.savefig(stem.with_suffix('.png'),dpi=240)
# Keep SVG text editable while embedding only the required genuine TNR glyphs.
text=stem.with_suffix('.svg').read_text();f=TTFont(font);s=subset.Subsetter();s.populate(text=''.join(t.get_text() for t in ax.texts+ax.get_xticklabels()+ax.get_yticklabels()));s.subset(f);buf=io.BytesIO();f.save(buf)
css='@font-face{font-family:"Times New Roman";src:url(data:font/ttf;base64,'+base64.b64encode(buf.getvalue()).decode()+') format("truetype");}'
text=text.replace('<defs>','<defs><style type="text/css">'+css+'</style>',1);stem.with_suffix('.svg').write_text(text)
print('Created 166 x 43 mm vector figure; Times New Roman 8.5-9 pt.')
