"""Supplementary follow-up and evidence-link diagrams, using actual retained data."""
from pathlib import Path
import argparse,io,base64
import numpy as np,pandas as pd,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties,fontManager
from matplotlib.text import Text
from fontTools import subset
from fontTools.ttLib import TTFont
def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--fonts',required=True);a=p.parse_args();r=Path(a.root);out=r/'figures';font=Path(a.fonts)/'Times.TTF';fontManager.addfont(str(font));plt.rcParams.update({'font.family':'Times New Roman','font.size':8.5,'axes.titlesize':9,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42,'svg.fonttype':'none'});purple='#6756C8';blue='#3184C8';orange='#C77936'
    def save(fig,name):
        for t in fig.findobj(Text):t.set_fontproperties(FontProperties(fname=font,size=t.get_fontsize()))
        for ext in ['pdf','svg','png']:fig.savefig(out/(name+'.'+ext),dpi=220)
        path=out/(name+'.svg');text=path.read_text();f=TTFont(font);s=subset.Subsetter();s.populate(text=''.join(t.get_text() for t in fig.findobj(Text)));s.subset(f);b=io.BytesIO();f.save(b);css='@font-face{font-family:"Times New Roman";src:url(data:font/ttf;base64,'+base64.b64encode(b.getvalue()).decode()+') format("truetype");}';path.write_text(text.replace('<defs>','<defs><style type="text/css">'+css+'</style>',1));plt.close(fig)
    d=pd.read_parquet(r/'data/sensitivity/uma_request_followup.parquet');fig,axs=plt.subplots(1,2,figsize=(166/25.4,54/25.4));fig.subplots_adjust(left=.10,right=.98,bottom=.28,top=.84,wspace=.38)
    x=np.sort(d.loc[~d.right_censored,'duration_hours'].to_numpy());axs[0].plot(x,np.arange(1,len(x)+1)/len(x),color=purple,lw=1.1);axs[0].set_xscale('log');axs[0].set_ylim(0,1);axs[0].set_xlabel('Request to settlement (hours)');axs[0].set_ylabel('Fraction of completed requests');axs[0].set_title('(a) Completed-request delay',loc='left')
    d['request_year']=d.request_utc.dt.year;g=d.groupby('request_year').right_censored.agg(['sum','count']);frac=100*g['sum']/g['count'];axs[1].bar(g.index,100-frac,color=purple,label='Settled');axs[1].bar(g.index,frac,bottom=100-frac,color=orange,label='Open at cutoff');axs[1].set_ylim(0,100);axs[1].set_ylabel('Retained requests (%)');axs[1].set_xlabel('Request year');axs[1].set_xticks(g.index,g.index.astype(str));axs[1].set_title('(b) Follow-up status',loc='left');axs[1].legend(frameon=False,fontsize=7.5,loc='upper center',bbox_to_anchor=(.5,-.34),ncol=2)
    save(fig,'uma_followup');g.to_csv(out/'uma_followup_source.csv')
    fig,ax=plt.subplots(figsize=(166/25.4,62/25.4));fig.subplots_adjust(left=.04,right=.98,bottom=.07,top=.88);ax.set_xlim(-.2,2.25);ax.set_ylim(7.1,-.7);ax.axis('off')
    for x,label,col in [(0,'Participants',purple),(1,'Polygon OOv2',purple),(2,'Ethereum DVM',blue)]:
        ax.plot([x,x],[-.1,6.8],color='#C7C5D1',lw=.8);ax.text(x,-.35,label,ha='center',fontsize=9,color=col)
    def arrow(x1,x2,y,label,dashed=False,color=purple):
        ax.annotate('',(x2,y),(x1,y),arrowprops={'arrowstyle':'->','lw':1,'color':color,'linestyle':'--' if dashed else '-'});ax.text((x1+x2)/2,y-.16,label,ha='center',fontsize=8,color=color)
    arrow(0,1,.5,'Request');arrow(0,1,1.4,'Proposal');arrow(0,1,2.3,'Challenge');arrow(1,2,3.2,'Linked request',True,orange);ax.scatter(2,4.1,s=22,color=blue);ax.text(1.84,4.1,'Resolution',ha='right',va='center',fontsize=8,color=blue);arrow(2,1,5,'Matched result',True,orange);arrow(0,1,5.9,'Settlement');arrow(1,0,6.8,'Payout')
    save(fig,'cross_chain_evidence_links')
    print('Two supplementary figures generated.')
if __name__=='__main__':main()
