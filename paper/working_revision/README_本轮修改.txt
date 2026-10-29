本轮：Appendix B.2 的原生时间—UTC 对照示例

Overleaf 主文件：main.tex；编译器：XeLaTeX。
在上一轮 31 页精简稿上，新增第 24 页 Table S5，全文仍为 31 页。
五组真实留存记录分别说明 UMA 秒级事件时间、Tellor 毫秒时间、Pyth epoch 区间、Chainlink 同链同区块时间补齐和未匹配时间留空。
修改位置：sections/appendix_b_temporal.tex、tables/temporal_worked_examples.tex。
完整记录标识、原始字段、原始值、UTC 值、源表版本和匹配证据见 supplementary/temporal/appendix_b_selected_examples.csv 与 JSON。
原生数据与已存 UTC 字段的有界核对通过；脚本与检查记录随工程提供。本轮没有重建全量数据、补采历史数据或声称完成作者审核。
生成脚本：temporal_source/build_appendix_b_examples.py；--data-root 指向上一轮完整 dataset_deposit。

已检查正文和附录短尾行、全部 31 条图表注释、交叉引用及表格尺寸。原有字体和页边距保持一致。
本地使用 Tectonic 的 XeTeX 引擎编译，不等同于实际托管 Overleaf 执行。
