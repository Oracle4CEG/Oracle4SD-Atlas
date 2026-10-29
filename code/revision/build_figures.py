"""Compact manuscript figures with editable SVG text and embedded Times New Roman."""
from pathlib import Path
import argparse,base64,io,json
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as md
from matplotlib.font_manager import FontProperties,fontManager
from matplotlib.patches import FancyArrowPatch
from matplotlib.text import Text
from fontTools import subset
from fontTools.ttLib import TTFont

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--fonts',required=True);a=p.parse_args();r=Path(a.root);out=r/'figures';out.mkdir(exist_ok=True);data=r/'data';font=Path(a.fonts)/'Times.TTF';fontManager.addfont(str(font));fp=FontProperties(fname=font)
    plt.rcParams.update({'font.family':'Times New Roman','font.size':8.5,'axes.titlesize':9.2,'axes.labelsize':8.5,'xtick.labelsize':8,'ytick.labelsize':8,'pdf.fonttype':42,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.6,'xtick.major.width':.6,'ytick.major.width':.6,'svg.hashsalt':'atlas-revision-final'})
    for f in Path(a.fonts).glob('*.TTF'):fontManager.addfont(str(f))
    plt.rcParams.update({'mathtext.fontset':'custom','mathtext.rm':'Times New Roman','mathtext.it':'Times New Roman:italic','mathtext.bf':'Times New Roman:bold','mathtext.fallback':None})
    purple='#6756C8';blue='#3184C8';orange='#C77936';grey='#9195A1';ink='#242440'
    def save(fig,name):
        for x in fig.findobj(Text):x.set_fontproperties(FontProperties(fname=font,size=x.get_fontsize()))
        for ext in ['pdf','svg','png']:fig.savefig(out/(name+'.'+ext),dpi=220)
        s=(out/(name+'.svg')).read_text();ft=TTFont(font);ss=subset.Subsetter();ss.populate(text=''.join(t.get_text() for t in fig.findobj(Text))+'×−0123456789½₀');ss.subset(ft);buf=io.BytesIO();ft.save(buf)
        css='@font-face{font-family:"Times New Roman";src:url(data:font/ttf;base64,'+base64.b64encode(buf.getvalue()).decode()+') format("truetype");}'
        s=s.replace('<defs>','<defs><style type="text/css">'+css+'</style>',1);(out/(name+'.svg')).write_text(s);plt.close(fig)
    def clean(ax):ax.grid(axis='y',color='#E8E8ED',lw=.45,zorder=0);ax.tick_params(length=3,pad=3)
    def dates(ax):ax.xaxis.set_major_locator(md.AutoDateLocator(minticks=3,maxticks=4,interval_multiples=False));ax.xaxis.set_major_formatter(md.DateFormatter('%b %Y'))
    # A small descriptive gallery: one unit and denominator per panel.
    d=pd.read_parquet(data/'daily/daily_measurements.parquet');policy=pd.read_parquet(data/'daily/flare_historical_signing_policy.parquet');delay=pd.read_parquet(data/'daily/uma_daily_completion_delay.parquet')
    fig,axs=plt.subplots(2,2,figsize=(166/25.4,101/25.4));fig.subplots_adjust(left=.10,right=.98,bottom=.10,top=.92,hspace=.63,wspace=.32)
    sub=d[d.branch.eq('Tellor')&d.metric.eq('report_submissions')];axs[0,0].scatter(sub.date_utc,sub.active_accounts,s=3,color=purple);axs[0,0].set_title('(a) Tellor reporter participation',loc='left');axs[0,0].set_ylabel('Active addresses / day')
    sub=d[d.branch.eq('Flare FTSOv2')&d.metric.eq('reward_paid')];axs[0,1].scatter(sub.date_utc,sub.value/1e6,s=3,color=blue);axs[0,1].set_title('(b) Flare realized claims',loc='left');axs[0,1].set_ylabel('FLR paid / day (millions)')
    sub=delay[delay.asset.eq('0x2791bca1f2de4661ed88a30c99a7a9449aa84174')];axs[1,0].scatter(sub.date_utc,sub.p90_hours,s=3,color='#B9B1E7',label='90th percentile');axs[1,0].scatter(sub.date_utc,sub.median_hours,s=3,color=purple,label='Median');axs[1,0].set_yscale('log');axs[1,0].set_title('(c) UMA completed-request delay',loc='left');axs[1,0].set_ylabel('Request to settlement (h)');axs[1,0].legend(frameon=False,fontsize=7.5,loc='upper left',markerscale=2)
    axs[1,1].plot(policy.epoch_start_utc,policy.effective_signers,color=blue,lw=.9);axs[1,1].set_title('(d) Flare signing-weight concentration',loc='left');axs[1,1].set_ylabel('Effective signing addresses')
    for ax in axs.flat:clean(ax);dates(ax)
    save(fig,'daily_gallery')
    d.to_csv(out/'daily_gallery_source.csv.gz',index=False);delay.to_csv(out/'delay_gallery_source.csv',index=False);policy.to_csv(out/'signing_policy_gallery_source.csv',index=False)
    # Six separate rule populations; no pooled error count.
    sem=pd.read_csv(data/'evidence/semantic_summary.csv');fig,ax=plt.subplots(figsize=(166/25.4,56/25.4));fig.subplots_adjust(left=.31,right=.96,bottom=.23,top=.91)
    labels=['UMA challenge status','UMA settlement status','UMA winner component','Tellor outcome meaning','Tellor applied loss','DVM accrual classification'];pct=100*sem.before_violations/sem.population;y=np.arange(6)
    ax.barh(y,pct,color=purple,height=.52);ax.scatter(np.zeros(6),y,s=20,color=orange,zorder=3,clip_on=False,label='After correction');ax.set_yticks(y,labels);ax.invert_yaxis();ax.set_xlim(0,109);ax.set_xticks([0,25,50,75,100]);ax.set_xlabel('Rule violations within each tested population (%)');ax.legend(frameon=False,loc='lower right',fontsize=8)
    for yy,x in zip(y,pct):ax.text(x+1.5,yy,f'{x:.1f}',va='center',fontsize=8)
    ax.grid(axis='x',lw=.4,color='#E8E8ED');ax.set_axisbelow(True);save(fig,'semantic_gallery');sem.to_csv(out/'semantic_gallery_source.csv',index=False)
    # Actual elapsed-time axis, with endpoints labelled off-axis to avoid overcrowding.
    ev=pd.read_parquet(data/'evidence/cross_chain/five_transactions.parquet');fig=plt.figure(figsize=(166/25.4,76/25.4));gs=fig.add_gridspec(2,2,height_ratios=[1.1,1],hspace=.65,wspace=.35,left=.10,right=.97,bottom=.14,top=.92);ax=fig.add_subplot(gs[0,:]);ax.set_title('(a) Request lifecycle',loc='left')
    ax.plot([0,100.279],[0,0],color=grey,lw=1)
    offsets=[(-1,15),(0,32),(12,-25),(-12,32),(0,15)]
    for (_,x),(dx,dy) in zip(ev.iterrows(),offsets):
        col=blue if x.chain=='Ethereum' else purple;ax.scatter(x.hours_since_request,0,s=23,c=col,zorder=3);ax.annotate(x.stage,(x.hours_since_request,0),xytext=(dx,dy),textcoords='offset points',ha='center',fontsize=8,arrowprops=dict(arrowstyle='-',lw=.55,color=col))
    ax.set_xlim(-3,105);ax.set_ylim(-.9,1.0);ax.set_yticks([]);ax.set_xticks([0,25,50,75,100]);ax.set_xlabel('Elapsed UTC hours');ax.spines['left'].set_visible(False)
    ax2=fig.add_subplot(gs[1,0]);ax2.set_title('(b) Settlement payout',loc='left');ax2.barh([0],[750],color=purple,height=.5,label='Principal returned');ax2.barh([0],[250],left=[750],color=blue,height=.5,label='Winner gain');ax2.set_yticks([]);ax2.set_xlim(0,1080);ax2.set_xlabel('USDC.e');ax2.text(375,0,'Principal returned\n750',ha='center',va='center',color='white',fontsize=8);ax2.text(875,0,'Gain\n250',ha='center',va='center',color='white',fontsize=8)
    ax3=fig.add_subplot(gs[1,1]);ax3.set_title('(c) Net recorded flows',loc='left');ax3.barh([2,1,0],[-750,250,500],color=[purple,blue,grey],height=.55);ax3.axvline(0,lw=.6,color=ink);ax3.set_yticks([2,1,0],['Proposer','Disputer','Fee recipient']);ax3.set_xlim(-850,620);ax3.set_xlabel('USDC.e')
    save(fig,'cross_chain_gallery');ev.to_csv(out/'cross_chain_gallery_source.csv',index=False)
    # Explicit information/outcome boundary, with empirical target distribution.
    pred=pd.read_parquet(data/'prediction/uma_prediction_tasks.parquet');fig,axs=plt.subplots(1,2,figsize=(166/25.4,48/25.4),gridspec_kw={'width_ratios':[1.9,1]});fig.subplots_adjust(left=.04,right=.98,bottom=.24,top=.83,wspace=.27)
    ax=axs[0];ax.set_title('(a) Information and outcome',loc='left');ax.set_xlim(-.1,3.1);ax.set_ylim(-.6,1.1);ax.axis('off');ax.annotate('',(3,0),(0,0),arrowprops=dict(arrowstyle='->',lw=.9,color=grey))
    for x,label in [(0,'Request'),(1,'Proposal'),(2,'Challenge'),(3,'Resolution')]:ax.scatter(x,0,c=purple if x<=1 else blue,s=22);ax.text(x,-.22,label,ha='center',fontsize=8)
    ax.axvline(1,ymin=.12,ymax=.95,color=orange,lw=.8,ls='--');ax.text(1,.67,r'$T_0$',ha='center',fontsize=9);ax.text(.23,.30,'Past settlements',ha='center',fontsize=8);ax.text(2.45,.42,'Retrospective selection',ha='center',fontsize=8)
    ax=axs[1];counts=pred.proposal_rejected_by_protocol.value_counts();ax.bar([0,1],[counts[0],counts[1]],color=[purple,blue],width=.6);ax.set_xticks([0,1],['Unchanged','Changed']);ax.set_ylabel('Requests');ax.set_title('(b) Resolution vs proposal',loc='left');clean(ax);save(fig,'prediction_task')
    # All sixteen feature distributions, appendix only. Displayed on their documented units.
    defs=pd.read_csv(data/'prediction/feature_dictionary.csv');fig,axs=plt.subplots(4,4,figsize=(166/25.4,145/25.4));fig.subplots_adjust(left=.08,right=.985,bottom=.07,top=.96,wspace=.45,hspace=.88)
    names=['log(1 + bond)','log(1 + final fee)','log(1 + reward)','Reward / bond','Liveness (h)','Proposal delay (h)','Ancillary bytes','Proposer: prior count','Proposer: prior\ndispute rate','Proposer: prior\nrejection rate','Requester: prior count','Requester: prior\ndispute rate','Requester: prior\nrejection rate','Registered adapter','Proposed price class','Adapter version']
    summary=[]
    for i,(ax,f,label) in enumerate(zip(axs.flat,defs.feature,names)):
        s=pred[f].dropna();ax.set_title(f'({chr(97+i)}) {label}',loc='left',fontsize=7.8)
        if f in ['proposed_price_class','adapter_version','requester_is_polymarket_adapter']:
            vc=s.astype(str).value_counts();short={'binary_zero':'0','binary_one':'1','indeterminate_half':'½','early_expiration':'Early','True':'Yes','False':'No','v2_0':'V2','v3_current':'V3'};labs=[short.get(x,short.get(x.replace('polymarket_','').replace('adapter_',''),x.replace('polymarket_','').replace('adapter_',''))) for x in vc.index];ax.bar(range(len(vc)),vc.values,color=purple,width=.65);ax.set_xticks(range(len(vc)),labs,rotation=25 if len(labs)>3 else 0)
        else:ax.hist(pd.to_numeric(s),bins=min(15,max(1,s.nunique())),color=purple,linewidth=.3,edgecolor='white');ax.ticklabel_format(axis='x',style='sci',scilimits=(-2,4),useMathText=True)
        if i%4==0:ax.set_ylabel('Requests',fontsize=7.5)
        ax.tick_params(labelsize=7);summary.append({'feature':f,'nonmissing':len(s),'missing':len(pred)-len(s)})
    save(fig,'prediction_features');pd.DataFrame(summary).to_csv(out/'prediction_feature_missingness.csv',index=False)
    # Feasibility uses a small set of primary measurement families; full twenty-column matrix is data.
    feas=pd.read_csv(r/'metadata/variable_feasibility.csv');cols=['role_participation','realized_rewards','applied_losses','capital_hours','completion_delay','control_weight_hhi','historical_threshold','independent_deviation'];branches=feas.branch.drop_duplicates().tolist();codes={'derivable':0,'additional_acquisition':1,'inapplicable_to_sampled_delivery_unit':2,'unknown':3};z=np.array([[codes[feas[(feas.branch==b)&(feas.variable==m)].iloc[0].feasibility] for m in cols]for b in branches]);fig,ax=plt.subplots(figsize=(166/25.4,67/25.4));fig.subplots_adjust(left=.22,right=.98,bottom=.24,top=.94)
    from matplotlib.colors import ListedColormap
    ax.pcolormesh(np.arange(9)-.5,np.arange(9)-.5,z,cmap=ListedColormap([purple,'#DAD7ED','#F1F1F3',orange]),vmin=0,vmax=3,shading='flat',rasterized=False);ax.set_ylim(7.5,-.5);ax.set_yticks(range(8),branches);ax.set_xticks(range(8),['Actors','Payments','Losses','Capital\ntime','Delay','Weights','Threshold','External\nreference']);ax.tick_params(length=0);ax.set_xticks(np.arange(-.5,8,1),minor=True);ax.set_yticks(np.arange(-.5,8,1),minor=True);ax.grid(which='minor',color='white',linewidth=2);ax.tick_params(which='minor',length=0)
    for i in range(8):
        for j in range(8):ax.text(j,i,['D','A','–','?'][z[i,j]],ha='center',va='center',fontsize=9,color='white' if z[i,j] in [0,3] else ink)
    save(fig,'feasibility_gallery')
    manifest=[]
    for f in out.glob('*.pdf'):
        import fitz
        doc=fitz.open(f);manifest.append(dict(figure=f.stem,width_mm=round(doc[0].rect.width*25.4/72,2),height_mm=round(doc[0].rect.height*25.4/72,2),raster_images=len(doc[0].get_images()),fonts=[x[3] for x in doc[0].get_fonts()]))
    (out/'figure_validation.json').write_text(json.dumps(manifest,indent=2));print('Generated six compact figure galleries, including all sixteen feature distributions.')
if __name__=='__main__':main()
