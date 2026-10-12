# 运行数据与实验

以下命令在仓库根目录执行。已验证环境为 Linux x86-64、CPU；不需要钱包、RPC 密钥或 GPU。主文档见 [FULL_DATA.md](FULL_DATA.md)。

本次修复交付在专门分支中。新机器先这样获取代码，避免下载到旧的默认分支：

```bash
git clone --branch fix/usable-atlas-release-20261012 --single-branch \
  https://github.com/virusLuke3/Oracle4SD-Atlas.git
cd Oracle4SD-Atlas
```

## 1. 安装独立环境

```bash
python3 scripts/bootstrap_environment.py --output runs/environment
```

脚本自行安装 Python 3.12.12，不依赖宿主 Python 的 venv/ensurepip。安装日志和依赖版本保存在 `runs/environment/`。每次安装或实验使用新的输出目录。

## 2. 先跑小型实验

```bash
runs/environment/scientific/bin/python scripts/download_atlas.py \
  --component native --output runs/decision-inputs \
  --include data/applications/trustworthy_ai_challenge/decision_samples.parquet \
  --include data/applications/trustworthy_ai_challenge/splits.parquet
runs/environment/scientific/bin/python scripts/run_decision_benchmark.py \
  --release runs/decision-inputs --output runs/decision-experiment
```

这会运行 810 条真实决策样本上的三个基线，输出 `metrics.csv`、`predictions.parquet` 和 `validation.json`。训练/验证/测试按时间分开；标签是后续协议裁决，不是独立事实真值或收益保证。

如果只想重跑七个金融模型，可下载已重建的两个输入表，省去亿级数据重建。此实验仍建议 8 GB 以上内存，使用新的实验目录：

```bash
runs/environment/scientific/bin/python scripts/download_atlas.py \
  --component repaired --output runs/financial-replay \
  --include data/applications/financial_benchmark/landmark_prefixes.parquet \
  --include data/applications/financial_benchmark/splits.parquet
ORACLE_WORKSPACE="$PWD/runs/financial-replay" \
PYTHONPATH="$PWD/code/reconstruction" \
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 \
runs/environment/scientific/bin/python -c \
  'from scripts.applications.financial.common import run_benchmark; run_benchmark()'
```

结果位于 `runs/financial-replay/data/applications/financial_benchmark/`。检查 `metrics.parquet` 的 `status`、`evaluation` 和 `metric_unavailability`：本次发布完成了 21 个模型/任务拟合，F1/F2 使用随机切分回退，F3 使用时间切分。无法估计的指标保持为空。完整重建命令还会自动检查这 21 次拟合是否完成。

## 3. 下载完整结果或重新构建

直接读取修复后的完整数据：

```bash
runs/environment/scientific/bin/python scripts/download_atlas.py \
  --component repaired --output runs/released-atlas
```

从 64 个原生输入文件重新构建：

```bash
runs/environment/scientific/bin/python scripts/download_atlas.py \
  --component native --output runs/native
runs/environment/scientific/bin/python scripts/rebuild_atlas.py \
  --input-root runs/native --output runs/full-atlas \
  --from-native --with-trajectory-views --with-benchmarks
runs/environment/scientific/bin/python scripts/build_release_metadata.py \
  --release runs/full-atlas
```

全量输入约 1.81 GB，重建需至少预留 40 GB 磁盘。建议 8 GB 或以上内存；实际耗时和峰值内存见发布包的 `validation/full_release.json`。全部下载使用固定版本并校验 SHA-256。

成功标志是 `validation/full_release.json` 中 `passed: true`。字段说明、表清单和时间覆盖在 `metadata/`；各阶段完整日志在 `validation/`；金融实验结果在 `data/applications/financial_benchmark/`。金融实验的随机切分回退会明确标记，无法估计的指标保留为空，不能当作 0。

亿级公共表适合用 DuckDB 按列、按条件读取，不要一次性装入 pandas。可以先读取 5 行：

```bash
runs/environment/scientific/bin/python - <<'PY'
import duckdb
con = duckdb.connect(config={"threads": 2, "memory_limit": "2GB"})
path = "runs/released-atlas/data/curated/parquet/accountability_events.parquet"
print(con.execute("SELECT oracle_network, reward_amount_raw, truth_basis, rule_id FROM read_parquet(?) WHERE oracle_network='UMA' LIMIT 5", [path]).fetchdf())
PY
```

原始金额保留为整数字符串，并结合资产和小数位解释；不能把不同代币直接相加，也不能把本金返还算成奖励或总利润。

## 4. 回归测试与历史状态

```bash
runs/environment/scientific/bin/python -m unittest discover -s tests -v
runs/environment/scientific/bin/python scripts/replay_pyth_snapshot.py \
  --output runs/pyth-replay
runs/environment/scientific/bin/python scripts/restore_source_registries.py \
  --output runs/source-workspace
```

Pyth 使用已归档的历史快照，不会用今天的滚动状态替代旧数据。原始审计记录、修改前结果和失败记录均保留；当前修复版具有单独的数据和代码身份。Notebook 的本地执行记录与真实 Google Colab 托管执行记录分开标注。
