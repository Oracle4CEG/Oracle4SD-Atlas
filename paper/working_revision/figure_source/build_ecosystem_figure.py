"""Compact main-text figure: 180 x 98 mm, true Times New Roman, live-text SVG.

Usage: python build_main_figure.py --font-dir /path/to/Times_New_Roman_fonts
The font directory must contain Times.TTF and Timesbd.TTF (or times.ttf/timesbd.ttf).
Font files are not distributed in this package.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties,findfont
from matplotlib.patches import Rectangle,FancyBboxPatch

ROOT=Path(__file__).resolve().parent
DATA=json.loads((ROOT/'source_data/figure_data.json').read_text())
parser=argparse.ArgumentParser()
parser.add_argument('--font-dir',type=Path)
parser.add_argument('--width-mm',type=float,default=166)
args=parser.parse_args()

def getfont(bold=False):
    if args.font_dir:
        found=[p for p in args.font_dir.iterdir() if p.name.lower()==('timesbd.ttf' if bold else 'times.ttf')]
        if not found: raise FileNotFoundError('Times New Roman font file missing')
        fp=FontProperties(fname=found[0])
    else:
        fp=FontProperties(fname=findfont(FontProperties(family='Times New Roman',weight='bold' if bold else 'normal'),fallback_to_default=False))
    if fp.get_name()!='Times New Roman':raise ValueError('True Times New Roman is required; no substitute is permitted.')
    return fp

REG,BOLD=getfont(),getfont(True)
plt.rcParams.update({'svg.fonttype':'none','pdf.fonttype':42,'ps.fonttype':42,'svg.hashsalt':'Oracle4SD-main-v2','axes.unicode_minus':False})
W,H=180,98
fig=plt.figure(figsize=(args.width_mm/25.4,(args.width_mm*H/W)/25.4),facecolor='white')
ax=fig.add_axes([0,0,1,1]);ax.set_xlim(0,W);ax.set_ylim(H,0);ax.axis('off')
C={'ink':'#22252D','gray':'#737C89','line':'#E5E7EC','purple':'#6454B3','coral':'#BD5B49'}

def txt(x,y,s,size=8,bold=False,ha='left',color=None):
    a=ax.text(x,y,s,ha=ha,va='center',color=color or C['ink'],fontproperties=BOLD if bold else REG,fontsize=size,zorder=7)
    return a

def line(x1,y1,x2,y2,col=None,lw=.45,ls='-',z=2):
    ax.plot([x1,x2],[y1,y2],color=col or C['line'],linewidth=lw,linestyle=ls,zorder=z)

def histmark(x,y,kind,size=3.6):
    mark={'history':'s','service':'o','mechanism':'D'}[kind]
    ax.plot(x,y,marker=mark,markersize=size,markerfacecolor='white' if kind!='mechanism' else C['gray'],markeredgecolor=C['gray'],markeredgewidth=.7,linestyle='none',zorder=6)

def cell(x,y,roles,scope,color):
    fill=color if scope=='sample' else 'white'
    edge=color if scope!='context' else '#A8AFB9'
    p=FancyBboxPatch((x-3,y-2.05),6,4.1,boxstyle='round,pad=0,rounding_size=.65',facecolor=fill,edgecolor=edge,linewidth=.65,zorder=4)
    ax.add_patch(p)
    txt(x,y,roles.replace('/',''),size=7.7,bold=scope=='sample',ha='center',color='white' if scope=='sample' else color if scope=='input' else C['gray'])

def timestamp(s):return datetime.fromisoformat(s.replace('Z','+00:00')).replace(tzinfo=timezone.utc).timestamp()
x0,x1=30,101
t0,t1=timestamp('2017-01-01'),timestamp('2026-07-01')
tx=lambda s:x0+(timestamp(s)-t0)/(t1-t0)*(x1-x0)
rows=[24.5,32,39.5,47,54.5,64,71.5,79]
mx0,step=113,6.8
xs=[mx0+i*step for i in range(10)]

txt(2,6,'a',size=10,bold=True)
txt(7,6,'History and sample windows',size=9,bold=True)
txt(108,6,'b',size=10,bold=True)
txt(113,6,'Chains and sampled roles',size=9,bold=True)

for yr in [2018,2020,2022,2024,2026]:
    x=tx(f'{yr}-01-01')
    txt(x,15,str(yr),size=8,ha='center',color=C['gray'])
    line(x,19,x,83,col='#ECEEF2',lw=.4)
line(tx(DATA['cutoff']),19,tx(DATA['cutoff']),83,col='#A2A7AF',lw=.55,ls=(0,(2,2)))

headers=['ETH','POL','SOL','FLR','TLR','PYT','DIA','ARB','BAS','BNB']
for x,h in zip(xs,headers):txt(x,15,h,size=7.7,ha='center')

for i,(b,y) in enumerate(zip(DATA['branches'],rows)):
    color=C['purple'] if i<5 else C['coral']
    txt(2,y,b['branch'],size=8.5,bold=True,color=color)
    # History and record extents occupy two narrow tracks within each aligned row.
    hy,oy=y-1.6,y+1.4
    line(x0,hy,x1,hy,col='#E8E9ED',lw=.4)
    milestones=[m for m in DATA['milestones'] if m['branch']==b['branch']]
    for m in milestones:
        start=tx(m['date']);x=start
        if m['precision_end']:
            end=tx(m['precision_end']);x=(start+end)/2
            line(start,hy,end,hy,col=C['gray'],lw=.75,z=4)
        histmark(x,hy,m['kind'])
    a,z=tx(b['first_time_utc']),tx(b['last_time_utc'])
    line(a,oy,z,oy,col=color,lw=1.8,z=4)
    line(a,oy-.65,a,oy+.65,col=color,lw=.6,z=4)
    line(z,oy-.65,z,oy+.65,col=color,lw=.6,z=4)
    for r in [r for r in DATA['relations'] if r['branch']==b['branch']]:
        j=DATA['chain_order'].index(r['chain'])
        cell(xs[j],y,r['roles'],r['scope'],color)

line(2,59,177.5,59,col='#C4C8D0',lw=.55)
line(105,11,105,83,col='#D6DAE1',lw=.5)

# Only short, essential legends remain in the artwork. Explanations are in the caption.
for x,kind,label in [(3.5,'history','Origin'),(26,'service','Service'),(50.5,'mechanism','Mechanism')]:
    histmark(x,89,kind,size=3.5);txt(x+2.7,89,label,size=8)
line(81,89,85,89,col=C['purple'],lw=1.8)
txt(87,89,'Records',size=8)

cell(113,89,'','sample',C['purple']);txt(118,89,'Sampled',size=8)
cell(138.5,89,'','context',C['purple']);txt(143.5,89,'Context',size=8)
cell(165,89,'I','input',C['purple']);txt(169.5,89,'Input',size=8)

stem=ROOT.parent/'figures/ecosystem_scope'
fig.savefig(stem.with_suffix('.svg'),metadata={'Title':'Oracle4SD ecosystem and sampled scope','Description':'Main-text figure. 180 by 98 mm. Times New Roman. Explanatory material is supplied in a separate caption.'})
fig.savefig(stem.with_suffix('.pdf'),metadata={'Title':'Oracle4SD ecosystem and sampled scope','Author':'Oracle4SD Atlas','Subject':'180 x 98 mm; Times New Roman; vector artwork with selectable text.'})
fig.savefig(stem.with_suffix('.png'),dpi=240)
plt.close(fig)
print('Created page-width figure in Times New Roman; typography retains its native point sizes.')
