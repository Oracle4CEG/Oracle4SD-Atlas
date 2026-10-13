# Reproduction guide

Use the commands in the root README and the eight-part notebook. `scripts/bootstrap_environment.py` installs managed Python 3.12.12 with `requirements-release.txt` and `constraints-release.txt`. Pin the code commit and retain the full installed-package freeze, input configuration and run reports together. Full data and experiment commands are in [FULL_DATA.md](FULL_DATA.md).

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
| Missing package / incompatible Python | Use the managed bootstrap environment; the host does not need venv/ensurepip; retain its installation log on failure |
| HTTP 429 / timeout / missing historical code | Retain the failed live run; try a suitable archive endpoint or the explicitly separate bundled replay |
| No transaction/receipt | Confirm chain ID and transaction hash; absence is not a zero payment |
| Full inventory missing | Full files are separately distributed; see FULL_DATA.md; the case is not that dataset |
| Notebook kernel interrupted | Restart and run all cells in order; the notebook creates a unique run folder |
| Semantic assertion failure | Read `reports/validation.json` and stage stderr logs; retain original evidence and report the mismatch |

[Current execution reports](../reports/revision_20261012/README.md) state what was actually tested. Hosted Google Colab UI testing is separate from isolated Jupyter execution. The [historical issue log](../metadata/issue_log.csv) is preserved; [current resolutions](../metadata/issue_resolution_20261012.csv) refer to the full reconstruction checks rather than inferring success from the small case.
