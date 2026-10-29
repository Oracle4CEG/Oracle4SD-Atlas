Oracle4SD Atlas — 第一轮：指南 1 的选择、生态背景与观察范围
日期：2026-10-26

使用
将本 ZIP 作为新工程上传到 Overleaf，主文件选择 main.tex。
保留原工程的 pdfLaTeX 写法与版式。本地已使用 Tectonic 0.15.0 编译并检查 PDF；
本地验证并非在 Overleaf 服务端运行。全文预览另行提供。
无需 shell escape，不需要在 Overleaf 上运行 Python，也不需要重新下载字体。
正文插入的是已嵌入 Times New Roman 的矢量 PDF；SVG 保留可编辑文字。

本轮已完成
1. Introduction：整理已有选择逻辑，避免重复；替换贡献段；引用新的 Figure 1 和 Table 3。
2. Related work §2.1：增加八个分支的机制／观察对象与测量需求；区分协议说明、执行证据和事实验证。
3. §3.1：明确分支定义、选择依据、五个详细面板／三个较窄扩展、链角色及不同历史起点。
4. Table 3：补充测量作用与排除范围；更正 Chronicle、RedStone 的扫描起点与部署日期混淆。
5. Figure 1：插入已讨论的紧凑正文图。按本稿 166 mm 正文宽度重新输出，保持 7.7–10 pt 字号，
   Times New Roman；图内没有长段说明。图注与历史来源在图外。原流程图顺延为 Figure 2，
   原预测图顺延为 Figure 3，引用由 LaTeX 自动更新。
6. §7 / Table 11：逐分支连接研究问题、可用观察和额外证据。预测用途段按粘贴草稿改为未来研究定位。
7. Appendix A：A.1 选择与边界；A.2 历史实现登记；A.3 图形证据。
   Table S1：实现标识、历史来源及证据边界。
   Table S2：图中八张选定表的首末时间。
   Table S3：14 个历史节点及官方来源。
8. 增补历史公告与固定版本元数据的文献，保留原有参考文献条目的顺序。
9. supplementary/：8 分支实现登记 CSV、195 条原始合约登记、采集配置、历史 manifests、图源数据。

本轮没有执行的后续任务
没有重新采集链上数据或重跑科学实验。指南 2、3 的时间字段改造、日度产品、预测变量审计、
算法结果移除、跨链案例扩展及新的验证实验，需要后续按部分处理。
当前摘要、§3.6 和 §6.4 仍保留原有预测实验内容；本次没有将其当作“已完成删除”。

仍需历史证据确认的事项
• 并非每个实现都已建立完整的历史 runtime 生效区间。
• 无法从留存材料核实的部署 UTC 时间保持空值，并记录状态。
• Tellor 公开开放前的网络阶段仍待核实，未将公开开放日当作创世日。
• RedStone 未核实的首个 Push 部署年份没有画成确定节点。
• 生态背景关系是指南中的选例，不是完整多链历史服务清单。
这些限制已经进入正文／附录／CSV，没有以虚构日期或完整覆盖声明代替。

主要文件
main.tex                             主入口与附录引用
sections/01_background.tex          Introduction、Related work
sections/02_methods.tex             §3.1；原流程图仅缩窄 1% 以消除浮动体超高
tables/protocol_sources.tex         Table 3
figures/ecosystem_scope.tex         Figure 1 的正文插图与图注
figures/ecosystem_scope.pdf         已嵌入 Times New Roman 的矢量插图
figures/ecosystem_scope.svg         可编辑插图
sections/06_usage.tex               §7
tables/research_opportunities.tex   Table 11
sections/appendix_a_scope.tex       Appendix A
tables/implementation_register.tex  Table S1
tables/figure_observation_windows.tex Table S2
tables/historical_milestones.tex    Table S3
references.tex                     原文献与新增历史来源
supplementary/                      机器可读登记、图源与留存证据
figure_source/                      绘图脚本与输入；重新绘图时需实际 TNR 字体

验证范围
已完成本地全文编译、交叉引用与引用键检查、浮动体尺寸检查、新图字体与矢量检查，以及修改页目视检查。
人类作者尚未逐条签核历史来源与实现绑定；这里不声称已完成该签核。
