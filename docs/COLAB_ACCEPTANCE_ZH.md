> Historical instructions below describe an earlier release. For the current ten-product data, manuscript and tutorial use [the project README](../README.md) and [release configuration](../configs/atlas_utc_release.json). Earlier execution and publication statements do not describe the current release.

# Google Colab 托管验收

这次验收证明：新的 Google 托管 CPU 环境能够从公开仓库启动，复现一个真实 UMA 案例，完成两次确定性回放及固定版本的 28 项回归测试。95 张全量表和全部模型训练使用另一个[全量验收记录](../reports/revision_20261012/full_release.json)，不包含在这个小 notebook 的托管验收范围里。

## 1. 从固定版本打开

[在 Colab 打开本次验收版本](https://colab.research.google.com/github/virusLuke3/Oracle4SD-Atlas/blob/7060311b563beb1fc963d59433ae6b968913662a/notebooks/Oracle4SD_Atlas_Tutorial.ipynb)。组织仓库的默认分支尚未合并此次修改，不要用旧 main 分支验收。

登录 Google 账号，可先“保存副本到云端硬盘”。选择 Python 3、CPU（硬件加速器 None），使用 Google 托管运行时。已有运行时先“断开连接并删除运行时”，再重新连接；不同界面语言的菜单名称可能略有差异。不要选择连接到本地运行时。

无需提供私有数据、API key、钱包、RPC 付费服务或手动安装依赖。安装单元会自行创建 Python 3.12.12 科学计算环境；Colab 主机 Python 版本可以不同。不要修改单元代码或预先手动安装包。

## 2. 一次运行全部

点击“运行时 → 全部运行”（Run all），按 Colab 的提示允许运行该公开 notebook。等待所有 **9 个代码单元**完成。第一次下载依赖需要数分钟；此前本地全新内核运行约 10 分钟，这不是托管 Colab 的耗时保证。

核对这些结果：

| 验收项 | 应当看到 |
|---|---|
| 实际执行代码 | `d558c4669b1020b2664af2bf852658828a1c1da6` |
| 数据版本 | `uma-public-rpc-case-v1` |
| 观测截止 | `2026-06-30T23:59:59Z` |
| 案例规模 | 7 份源文件、5 笔交易、9 条解码协议事件、8 条代币流、1 个经济事件 |
| 支付分解 | 750 USDC.e 返还本金 + 250 USDC.e 代币收益 = 1,000 USDC.e 总转账 |
| 两轮校验 | 每轮 `passed_checks: 28`、`failed_checks: 0` |
| 回归测试 | `Ran 28 tests ... OK` |
| 重复运行 | 两次 reconstruction/statistics/summary.json 完全一致 |
| 最后一行成功提示 | `SUCCESS: two deterministic case replays; see separate full-release validation for the full dataset.` |

打开 notebook 的提交是 `7060311…`，内部执行代码固定为 `d558c46…`，两者不同是有意的：前者交付 notebook，后者是它锁定的执行代码。后续仅文档和验收工具的更新不会改变这次验收的版本。

## 3. 保存两份证据

1. 下载最后一个代码单元导出的 **`oracle-atlas-case-evidence.zip`**。如果浏览器阻止自动下载，使用单元显示的文件路径在 Colab 左侧文件栏下载。必须在删除运行时之前取回。
2. 使用“文件 → 下载 → 下载 .ipynb”保存 **带全部输出的 notebook**。不要开启“保存时忽略代码单元输出”。仅有空白 notebook 或成功截图不足以核对执行过程。

ZIP 应有 `identity.json`、`environment.json`、安装和执行日志、两份包版本清单，以及 `run1/`、`run2/` 的输入和验证结果。实际托管运行应记录 `runtime_kind: hosted_colab`；这个标签来自 notebook 自报，不能单独证明服务器归属。

交回这两份文件，并注明：实际运行人、运行日期和时区、Google 托管 CPU、从全新运行时开始、执行中是否改过代码或做过手动修复。可附保留输出的 Colab 分享链接；不必公开整个 Drive。

## 4. 由接收方核验证据

使用本次修改分支中的工具；它只读取文件，不执行 notebook 或解压其中程序：

```bash
python scripts/validate_colab_evidence.py \
  --notebook /absolute/path/Oracle4SD_Atlas_Tutorial.ipynb \
  --evidence /absolute/path/oracle-atlas-case-evidence.zip \
  --output runs/colab-acceptance/receipt.json
```

正常退出码为 0，报告 `passed: true`。它检查原始代码单元、执行顺序和错误输出、固定代码/数据身份、输入文件 SHA-256、两轮案例校验、支付分解和测试日志。验收工具本身不能提供 Google 签名的运行证明，因此还需保留运行人的上述声明。`--allow-local` 只供调试，不能用它完成托管验收。

如果失败，保留失败单元的完整报错和已有输出，下载 notebook；ZIP 尚未生成时说明失败在哪一单元。修复后应在全新运行时重新全部运行。不要通过跳过单元、删断言、改预期哈希或改 `runtime_kind` 来获得通过。

实际 Google 托管执行仍待提交上述证据。已有的本地新内核和 GitHub Actions 记录不等于托管验收。Google 官方说明了 [notebook 输出、VM 文件和下载的区别](https://research.google.com/colaboratory/faq.html)。
