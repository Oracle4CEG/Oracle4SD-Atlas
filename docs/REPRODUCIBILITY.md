# Reproduction guide

Use the commands in the root README and the eight-part notebook. Python 3.12 is the tested baseline. Pin the reviewed Git commit and retain `requirements.txt`, the full installed-package freeze, `configs/project.json` and the run reports together.

## What stays fixed

- Seven case source hashes; 85-field schema; previous case-summary reference.
- `uma-public-rpc-case-v1` and cutoff `2026-06-30T23:59:59Z`.
- Exact transaction/block identities in `case_spec.json`.
- Native integer monetary values; no cross-token or implicit USD aggregation.

New run directories receive query/process/analysis/QC outputs. Generated timestamps, absolute run paths, provider metadata and figure rendering need not be byte-identical. Scientific summary values are compared exactly to the frozen previous summary. The pipeline emits code hashes and Git status. Notebook execution records its exact code revision and environment.

## Troubleshooting

| Symptom | Action |
|---|---|
| Existing output directory | Choose another `--output`; do not delete a prior audited result just to pass |
| Input SHA mismatch | Re-check the pinned checkout or download; do not update reference hashes to hide a mismatch |
| Missing package / incompatible Python | Use a clean Python 3.12 virtual environment and the pinned requirements; in Colab use the tutorial's isolated environment |
| HTTP 429 / timeout / missing historical code | Retain the failed live run; try a suitable archive endpoint or the explicitly separate bundled replay |
| No transaction/receipt | Confirm chain ID and transaction hash; absence is not a zero payment |
| Full inventory missing | Full files are separately distributed; see FULL_DATA.md; the case is not that dataset |
| Notebook kernel interrupted | Restart and run all cells in order; the notebook creates a unique run folder |
| Semantic assertion failure | Read `reports/validation.json` and stage stderr logs; retain original evidence and report the mismatch |

[Fresh execution reports](../reports/reproducibility/README.md) state what was actually tested. Hosted Google Colab UI testing is separate from isolated Jupyter execution. [Known full-core defects](../metadata/issue_log.csv) do not disappear when the small case passes.
