"""Create the review response, provenance map and remaining-work record."""
from pathlib import Path
import argparse,json,hashlib,shutil,platform,importlib.metadata
import pandas as pd

RESPONSES={
'R01':('本地完成；公共版本待发布','冻结来源提交、数据清单、论文与教程对应关系。','metadata/release_identity.json','公共 GitHub/HF/Overleaf 尚未同步。'),
'R02':('完成','摘要、引言和研究用途围绕测量与数据复用重写。','Oracle4SD_Atlas/main.tex',''),
'R03':('完成','保留五详细面板与三窄扩展；逐分支说明代表性、历史证据及纳排。','Oracle4SD_Atlas/tables/protocol_sources.tex',''),
'R04':('完成；历史绑定有明确限定','实现登记表、时间线与链角色图已纳入。','Oracle4SD_Atlas/supplementary/implementation_register.csv','未把项目上线、版本部署和首事件混写。'),
'R05':('完成当前发布范围','保留原生精度；共同层与经济层使用按唯一键连接的 UTC companion。','dataset_deposit/metadata/core_temporal_validation.json','旧模型应用表属于历史存档。'),
'R06':('部分完成','已用原生事件及已留存区块时间补齐可匹配记录；完成额外 Ethereum header 试采。','data/acquisition/ethereum_header_pilot.json','尚缺大量历史区块头，未插值或用采集时间填补。'),
'R07':('部分完成','区间来源、边界与 partial/unknown 状态明确；缺失日不填零。','Oracle4SD_Atlas/supplementary/temporal/coverage_interval_evidence.csv','完整扫描回执和分页终止审计仍待补充。'),
'R08':('完成当前证据范围','建立八分支与二十候选变量的可行性矩阵。','metadata/variable_feasibility.csv','可推导不代表协议全服务覆盖。'),
'R09':('完成有证据的日频产品','生成八分支分角色、资产和经济阶段的日度观察及原生分母。','data/daily/daily_measurements.parquet','全部保留部分覆盖限定；未虚构缺失变量。'),
'R10':('完成可计算部分','完成日/周守恒、共同日历外边界、epoch 两种假设分配对照。','data/sensitivity/validation.json','严格连续覆盖子集不可认证，相应估计保持空值。'),
'R11':('完成','生成完整请求随访、已完成延迟 ECDF 与右删失状态。','data/sensitivity/uma_request_followup.parquet','完成样本曲线不当作总体生存概率。'),
'R12':('完成自动证据；待人工复核','六规则补总体、历史绑定与执行证据；表9与附录E一致。','data/evidence/validation.json','作者尚未签署历史规则解释。'),
'R13':('完成','输出六个逐对象旧值/新值修正账本。','data/evidence','同对象可能命中多规则，不能相加成独立对象总数。'),
'R14':('完成声明范围的重跑','完整核心重建通过48项检查；三种采集模式的同案例均通过28项检查。','dataset_deposit/metadata/full_reconstruction_validation.json','重建与外部事实真值、人工审核分开。'),
'R15':('完成','810请求；T0为提议事件；目标为原生已决整数与提议整数不等。','data/prediction/uma_prediction_tasks.parquet','回顾性挑战/链接/对账筛选，不能作完整请求错误率。'),
'R16':('完成','十六特征的公式、单位、missing、来源和分布图齐备。','data/prediction/feature_dictionary.csv','历史参数字段仍有绑定限定。'),
'R17':('完成','角色分开的严格过去历史；全810请求直接筛选交叉核验；保留394处特征更正。','data/prediction/feature_corrections.parquet','旧 pooled-history 模型输出仅归档。'),
'R18':('完成','无历史率、零分母比值保持为空；原生金额精度和特殊值保留。','data/prediction/validation.json',''),
'R19':('完成状态审计；部分参数待补证','逐特征可用时间状态；报告早到期排除与二元已决值子集敏感性。','data/prediction/feature_availability.parquet','未将全部候选特征宣称为已证明 T0 可用。'),
'R20':('完成','删除算法和性能叙述、模型图表；旧实验隔离存档。','archive/model_experiments',''),
'R21':('完成','完整五交易登记及receipt/header、标识符、时间检查。','data/evidence/cross_chain/five_transactions.parquet','历史事实真值未单独核验。'),
'R22':('部分完成','实线观察事件、虚线跨链身份/结果链接；明确 relay 路径未知。','figures/cross_chain_evidence_links.svg','完整发送/接收/回传交易和人工浏览器核验待补。'),
'R23':('完成','同资产双边押金、费、返本、收益及配置奖励处理重算。','data/evidence/cross_chain/cashflows.parquet','转账费与机会成本不计入已知净利润。'),
'R24':('完成','十逻辑产品对应100物理Parquet表；共享层非重复独立样本。','dataset_deposit/metadata/logical_products.json',''),
'R25':('完成主变量；一般原生字段仍需深化','新派生字段、时间与案例解释补全；1810字段均列出定义完成度。','dataset_deposit/metadata/field_dictionary.csv','904条保留源码引用层级定义，不声称全部经济语义已人工核验。'),
'R26':('本地完成；线上待发布','十Viewer配置、100RecordSet与物理字典对照；Croissant官方解析通过。','dataset_deposit/croissant.json','两个嵌套表有嵌套字段镜像；未创建公开新版本。'),
'R27':('完成','五类组合图及补充图均有PDF、可编辑SVG、源数据与脚本。','figures',''),
'R28':('完成','补齐附录A–I并清理正文交叉引用。','Oracle4SD_Atlas/main.tex',''),
'R29':('完成','八分支文献、问题、变量、可支持分析与证据缺口逐项对应。','Oracle4SD_Atlas/tables/research_opportunities.tex','理论类比不写作满足定理。'),
'R30':('本地完成','14角色导航、三数据阶段、四代码阶段与八分支来源到结果表。','Oracle4SD_Atlas_Repository/README.md','线上导航未同步。'),
'R31':('完成本地执行','教程加入来源、raw预览、前后值、字典、缺失与图表映射。','tutorial/Oracle4SD_Atlas_Tutorial_executed.ipynb',''),
'R32':('完成限定案例','bundled/public-download/live独立目录；实时链、区块、代码与运行hash核验。','data/acquisition/acquisition_mode_comparison.json','三模式完整链针对同一五交易案例；八分支探针仅为有界原生定位检查。'),
'R33':('完成有界演示','八分支native小样本及八份新取得raw响应归档重放。','tutorial/metadata/raw_replay_validation.json','不等于八分支全量重新采集。'),
'R34':('待外部执行','本地notebook和三模式已执行；提供独立读者与hosted验收步骤。','metadata/independent_reader_acceptance.txt','没有冒充Google托管Colab或独立读者。'),
'R35':('本地完成；线上待发布','组织仓库入口及当前版本导航统一；旧文档标注历史。','Oracle4SD_Atlas_Repository/README.md','尚无当前修订的公开固定commit。'),
'R36':('部分完成','记录本轮实际模型可知信息、提示、采用内容及自动验证。','metadata/ai_assistance_log.json','精确后台版本未暴露；历史提示不补造；人工复核待签署。'),
'R37':('有界试采受接口限制','Base目标合约历史代码、1000块窗口与失败证据已保存。','data/acquisition/redstone_avs_extension/pilot_report.json','历史logs限流/需token；operator/delegator奖励、提现、制裁证据尚未构建。'),
'R38':('完成保留政策重建；绑定待复核','183个Flare历史policy重建权重、角色映射与阈值；另给两个epoch窗口。','data/daily/flare_historical_signing_policy.parquet','运行时历史绑定尚未独立认证；地址不等于实体。'),
'R39':('完成范围限定','独立真值、因果和RL/Agent写作后续研究所需证据。','Oracle4SD_Atlas/sections/06_usage.tex','本轮无因果或强化学习新结论。'),
'R40':('部分完成','按已附指南配色与现有生态图协调；记录所用附件。','metadata/asset_provenance.csv','邮件另提配色PNG和Daily_Panel_and_Figure_References.pdf未见附件。'),
}

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--deposit',required=True);a=p.parse_args();r=Path(a.root).resolve();dep=Path(a.deposit).resolve();m=r/'metadata';m.mkdir(exist_ok=True)
    source=pd.read_csv(r.parent/'manuscript_review_20261026/revision_tasks.csv');rows=[]
    for _,x in source.iterrows():
        status,done,evidence,remaining=RESPONSES[x.id];rows.append({'编号':x.id,'优先级':x.priority,'原修改位置':x.location,'本轮状态':status,'实际处理':done,'证据_相对交付目录':evidence,'尚未完成或解释边界':remaining})
    pd.DataFrame(rows).to_csv(m/'revision_response.csv',index=False,encoding='utf-8-sig')
    pending=[
      ('G01','历史 Ethereum 区块头补采','R06','按缺失高度去重、分批缓存，验证块号/hash、时间单调关系、来源并重建日度产品。','数据维护者，待团队认领','16头试采成功；全量需历史节点额度，先一批试跑后按实际吞吐排期。'),
      ('G02','区间回执与分页审计','R07 R10','逐链/合约/版本登记连续扫描段、失败与重试、终止条件；再定义严格覆盖子集。','数据维护者，待团队认领','每分支先一个有界窗口；工期取决于原始回执是否存在。'),
      ('G03','历史规则和参数人工复核','R04 R12 R19 R25 R36 R38','复核六规则、预测参数T0可用性、部署/升级绑定、主变量经济含义及Flare阈值解释。','作者与协议复核人，待团队认领','建议先复核主文结论与六规则；未承诺完成日期。'),
      ('G04','完整跨链中继证据','R22','在该请求的有限时间范围中收集发送、接收、处理、回传事件；先验证消息键再分解延迟。','数据维护者，待团队认领','先1个案例；额外日志取决于历史接口。'),
      ('G05','RedStone AVS经济试采','R37','保持独立于Push；绑定历史部署/ABI后，限定1个operator或delegator与1个闭合epoch，连接抵押分配、提现、奖励、制裁。','扩展数据负责人，待团队认领','先获得可用Base archive；建议1–2人日做绑定和有界日志原型，再评估全量，不是已经完成的工时。'),
      ('G06','独立读者及Google托管执行','R34','按验收步骤从固定公开入口重跑，保存执行notebook、环境、干预记录与检查结果。','独立读者，待团队认领','必须由实际执行者填写；本地运行不能代替。'),
      ('G07','公开版本协调发布','R01 R26 R30 R35','发布本地已准备的仓库、数据卡、数据、metadata、教程与论文；生成实际commit/version后回填。','发布负责人，待团队认领','内容已准备；本轮未向外部平台写入。'),
      ('G08','补充指定视觉附件','R40','核对邮件指定配色PNG与Daily_Panel_and_Figure_References.pdf；仅据实际附件调整。','作者','本轮附件未包含这两项。'),
    ]
    pd.DataFrame(pending,columns=['缺口','内容','意见项','完成条件','负责人','依赖与估时']).to_csv(m/'remaining_work.csv',index=False,encoding='utf-8-sig')
    (m/'independent_reader_acceptance.txt').write_text('Independent-reader and hosted acceptance\n\nUse the finalized public repository commit and public data version after publication. Record the actual commit, environment, start/end time and any intervention. Run the eight-branch notebook with a fresh Python environment. Separately run the bounded UMA bundled, public-download and live acquisition examples in new directories, followed by processing and validation. Preserve executed notebooks, commands, output checksums and failures. Do not claim full-history acquisition from a bounded success. A Google-hosted Colab run must record its actual hosted CPU/runtime; the supplied local kernel run is not a substitute. The independent reader must enter their own identity and sign-off; no such sign-off is supplied in this delivery.\n')
    human=[{'scope':x,'status':'pending_author_review','reviewer':None,'review_time':None,'decision':None} for x in ['six semantic rules','historical implementation bindings','proposal-time parameter availability','cross-chain case interpretation','final scientific wording']];(m/'human_review_log.json').write_text(json.dumps(human,indent=2))
    ai=json.loads((m/'ai_assistance_log.json').read_text());ai['available_user_instructions_verbatim']=['那就继续做','我的文档里面不能出现这种，明显是AI的表达的语句，尤其是精准的哪一天，具体的reports什么的，以及文件路径这类表达，要求你每次写之前，都要去联网搜索看看，判断一下你自己写的是否过于AI化的表达了','修改完毕后你按照我们的修改意见搞把剩余的内容做完'];ai['adopted_changes']=['recomputed role-separated UMA histories','UTC clock companions','typed daily measurements','closed-request observed escrow exposure','six object-level correction ledgers','cross-chain worked case','compact vector figures','Data Descriptor prose and appendices'];(m/'ai_assistance_log.json').write_text(json.dumps(ai,indent=2,ensure_ascii=False))
    assets=[{'asset':'ecosystem_scope','basis':'attached Guide 1 and Figure Catalogue; retained implementation register','status':'existing revised vector retained'},{'asset':'new figure galleries','basis':'attached Guide 3, original paper and computed native evidence','status':'166 mm wide; Times New Roman; editable SVG and vector PDF'},{'asset':'mentor colour PNG','basis':'mentioned by email','status':'not among supplied attachments'},{'asset':'Daily_Panel_and_Figure_References.pdf','basis':'mentioned by email','status':'not among supplied attachments'}];pd.DataFrame(assets).to_csv(m/'asset_provenance.csv',index=False)
    pol=pd.read_parquet(r/'data/daily/flare_historical_signing_policy.parquet');cols=['reward_epoch_id','epoch_start_utc','epoch_end_utc','registered_signers','weight_total','threshold_raw','registration_mapping_complete'];pol[cols].head(2).to_csv(m/'weights_bounded_pilot.csv',index=False)
    coverage=pd.read_csv(r/'Oracle4SD_Atlas/supplementary/temporal/coverage_interval_evidence.csv');coverage['coverage_status']='partial_or_unverified';coverage['complete_interval_receipts_reaudited']=False;coverage.to_parquet(m/'coverage_intervals.parquet',index=False)
    versions={k:importlib.metadata.version(k) for k in ['pandas','pyarrow','duckdb','matplotlib','nbformat','nbclient']};(m/'runtime_versions.json').write_text(json.dumps({'python':platform.python_version(),'platform':platform.platform(),'packages':versions},indent=2))
    ident={'revision':'local coordinated working-paper revision','date':'2026-10-26','atlas_input_commit':'1dc0dfc3bc919e64f43a110bf29b75ef0e34459c','template_input_commit':'2ca64c50c43e189aa9cfc2cacd03520b71119301','predecessor_data_release':'57ab1e2409652291c75f02c9e066c52011d8b4ad','new_public_commit':None,'new_public_data_version':None,'manuscript':'Oracle4SD_Atlas/main.tex','tutorial':'tutorial/Oracle4SD_Atlas_Tutorial_executed.ipynb','dataset_deposit':str(dep),'core_clock_parent_contract':'metadata/core_key_validation.json','model_experiments':'archive/model_experiments; historical and excluded from current claims'};(m/'release_identity.json').write_text(json.dumps(ident,indent=2))
    profiles=json.loads((r/'tutorial/metadata/profiles.json').read_text());raw=json.loads((r/'tutorial/metadata/raw_profiles.json').read_text());rawmap={x['branch']:x for x in raw};chain=[]
    for x in profiles:
        y=rawmap[x['branch']];chain.append({'branch':x['branch'],'source_register':'metadata/acquisition_profiles.json','raw_input':'tutorial_revision/'+y['raw_input'],'raw_mode':y['raw_mode'],'query_code':'tutorial_revision/query.py','queried_output':'tutorial_revision/queried_data/'+x['branch'].lower().replace(' ','_')+'/archived_raw_response.json','native_table':x['parent_native_table'],'native_input':'tutorial_revision/'+x['input'],'processing_code':'tutorial_revision/processing_code/replay.py','processed_output':'tutorial_revision/'+x['processed_output'],'research_output':'data/daily/daily_measurements.parquet','paper':'Methods; Data overview; Appendices A–D','scope':'bounded raw locator and archived native sample; daily product derives from full retained native tables'})
    pd.DataFrame(chain).to_csv(m/'eight_branch_source_to_output.csv',index=False)
    role=[('data/data_source','Source declarations and retained raw inputs'),('data/queried_data','Acquired evidence before processing'),('data/processed_data','Processed case outputs; current full data in separate deposit'),('code/query_data','Acquisition modes'),('code/process_data','Case processing'),('code/technical_validation','Validation'),('code/analyze_data','Descriptive outputs'),('metadata','Catalogues, dictionaries, provenance and release identity'),('notebooks','Tutorial entry and historical notebook archive'),('templates','Role retained; finished artifacts in tutorial_revision and paper replace blank templates'),('paper','Current LaTeX manuscript and compiled PDF'),('reports','Run evidence, historical reports labelled as predecessors'),('configs','Declared source scopes and versions'),('tests','Reference checks and reconstruction validation')];pd.DataFrame(role,columns=['folder_role','purpose']).to_csv(m/'folder_role_map.csv',index=False)
    # Preserve obsolete completion plans as history, while pointing to the current response.
    old=r/'Oracle4SD_Atlas/supplementary/temporal/remaining_tasks.csv'
    if old.exists():old.rename(old.with_name('remaining_tasks_at_guide2_historical.csv'))
    shutil.copy2(m/'remaining_work.csv',r/'Oracle4SD_Atlas/supplementary/remaining_work.csv')
    shutil.copy2(m/'revision_response.csv',r/'Oracle4SD_Atlas/supplementary/revision_response_complete.csv')
    (r/'README_交付说明.txt').write_text('Oracle4SD Atlas 本地修订交付\n\n论文已按意见补齐日度测量、UMA预测任务、逐对象修正、跨链案例和附录A–I。主文删除模型性能比较；旧实验独立归档。正文与补充材料共35页。新增图片采用166毫米宽矢量PDF和可编辑SVG，使用Times New Roman。\n\n先阅读 Oracle4SD_Atlas_Revised.pdf；Overleaf ZIP中的main.tex为入口。Figures ZIP包含图、源数据和绘图脚本。Research_Companion ZIP包含更新后的本地仓库、八分支教程、代码、字典和验证材料；完整数据另存dataset_deposit（约24 GiB）。\n\nmetadata/revision_response.csv逐条回答40项意见，remaining_work.csv说明仍需的数据与人工步骤。本轮已重建保留数据并执行检查，不表示完成全部历史重采。缺失区块头、连续覆盖回执、完整relay、RedStone AVS经济历史、历史规则人工复核、独立读者/Google托管执行及公共发布仍有缺口。没有生成新GitHub/HF公共版本，也没有替作者签署人工复核。\n\n后续写作继续先核对官方来源和同类论文表达；正文说明方法、数据和适用边界，操作路径和运行日志放配套材料。\n')
    for file in m.iterdir():
        if file.is_file():shutil.copy2(file,dep/'metadata'/file.name)
    print('Forty-item response, remaining work, identity and navigation records created.')
if __name__=='__main__':main()
