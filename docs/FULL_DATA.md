# Full-data access and reproduction

## Availability and exact identity

The runnable public release is `uma-public-rpc-case-v1`. Its seven source files and derived case tables are included in this repository. Two raw snapshots can alternatively be obtained at the immutable Hugging Face revision `aabcff2e1492df35f0aaa9abef657133fffe9b81`; exact URLs, byte lengths and SHA256 values are in [source_register.csv](../metadata/source_register.csv).

The [larger public review/demo subset](https://huggingface.co/datasets/Oracle4CEG/OracleEconLab-Oracle-Incentives-v1/tree/aabcff2e1492df35f0aaa9abef657133fffe9b81) has version `1.5.0-draft`. It is not the full core. The 71-record [full inventory](../metadata/full_data_inventory.csv) describes 67 curated Parquet files plus four application files, totaling **15,474,890,321 bytes**. Its hashes identify existing local audited files. Blank download URLs mean **not publicly deposited**, not “download later from the demo URL.” No full archive URL or DOI can honestly be supplied yet.

If the authors provide an authorized copy, preserve inventory-relative paths and verify it with:

```bash
python scripts/verify_full_data.py --root /path/to/authorized-copy --output /tmp/full-verification.json
```

This streams file hashes, reads Parquet row counts and fails for missing, changed or structurally different files. The author layout uses a separately mounted data directory; only for an explicitly authorized mounted layout, add `--allow-external-symlinks`. A normal extracted public archive should be self-contained. It does not repair the known semantic failures. Do not run on the bundled case directory and interpret missing full files as a defect in the case.

## Isolated production workspace

Historical production code is included under [code/production](../code/production/README.md), with per-file original/imported hashes. The default tutorial does not execute expensive full collectors. To inspect or stage a production rerun:

```bash
python scripts/prepare_full_workspace.py --output /path/to/new-production-workspace
python -m pip install -r requirements-production.txt
cd /path/to/new-production-workspace
export PYTHONPATH="$PWD/src"
python -m oracle_ledger --help
python scripts/ingest_polygon_uma.py --help
```

Several legacy collectors write under their own script root; staging prevents accidental changes to a different project. Obtain archive-capable nodes and the exact historical source/state bundles before full collection. A public endpoint URL is not a promise of unrestricted archive access. Read [acquisition profiles](../metadata/acquisition_profiles.json) before selecting a provider.

## Execution order and limitations

Run these commands **inside the staged workspace**. They are documented historical entry points, not a claim that all histories were recollected during this review. Configure your own Ethereum and Polygon archive endpoint URLs in `ETHEREUM_RPC_URL` and `POLYGON_RPC_URL` before running commands that use them.

| Panel | Query and process order |
|---|---|
| UMA | `python scripts/ingest_uma_dvm.py --root . --rpc-url "$ETHEREUM_RPC_URL"`; `python scripts/build_uma_dvm_ledger.py`; `python scripts/ingest_polygon_uma.py --root . --rpc-url "$POLYGON_RPC_URL"`; legacy bridge and flow receipt collectors; `build_polygon_uma_ledger.py`, `build_polygon_uma_flows.py`, `build_uma_crosschain_links.py` |
| Chainlink | `ingest_chainlink_staking_v02.py --root . --rpc-url "$ETHEREUM_RPC_URL"`, `ingest_chainlink_evidence.py --root . --rpc-url "$ETHEREUM_RPC_URL"`; then `build_chainlink_staking_v02_ledger.py`, `build_chainlink_evidence.py` |
| Tellor | `ingest_tellor_reports_block_results.py --cutoff-height 19890860`; disputes, rewards, tips/withdrawals and jail collectors named in `scripts/`; preserve module-version limitations |
| Flare | `ingest_flare_fsp_rewards.py --source-commit 56dccda13597ec78e47c24a38f875fa9ebad897c`; raw claims, claims/chill and attribution builders; exclude straddling epoch 411 |
| Pyth | `ingest_pyth_ois_history.py`; archived rolling-state snapshot required for the old 49-epoch panel. Running `ingest_pyth_ois_rolling_state.py` today creates a new state snapshot, not the old one |
| Chronicle / RedStone | Restore pinned source registries under `data/raw/source_audit/`; run `ingest_chronicle_redstone_events.py` and source settlement audit |
| DIA | `ingest_dia_staking.py`; retain principal/reward reconciliation and deployment range |
| Shared layers | After native prerequisites: `build_accountability_events.py`, `build_phase4_economic_interfaces.py`, `build_realized_economic_events.py`, `export_curated_parquet.py`; then QC scripts. Research-sample builders retain known semantic defects and are not cleared for inference |

Every bare filename in the table is an actual Python file under the staged `scripts/` directory and must be invoked as `python scripts/<filename>`. The [import inventory](../metadata/production_code_imports.csv) and historical [pipeline audit](../reports/core_audit_20260915/pipeline_records_validation_map.csv) provide further dependencies. Staging and `--help` are safe inspection paths, not a one-command full reproduction certification.

### Required external source registries

The RedStone collector reads `data/raw/source_audit/redstone_monorepo_95f8/packages/relayer-remote-config/main/` at commit `95f8cb9fd00b0a9f12c3e4bc45206533c90f09cb` of [redstone-finance/redstone-oracles-monorepo](https://github.com/redstone-finance/redstone-oracles-monorepo). Chronicle source is [chronicleprotocol/scribe](https://github.com/chronicleprotocol/scribe) at `12ff06ca78811e01313afde4b38fe959d6647096`; its validator registry reference is `f06e0a8209fcb47f1535d1b874cb8ff254a9c2c5`, as recorded in the frozen collector. Preserve upstream licenses. Tellor source reference is `943a2709ef0a60eb560447278b2f59923b9de484`; a source reference is not proof of the deployed binary version. Source registry trees and large raw snapshots are not all bundled here. Their complete archival manifest is an explicit full-release blocker.

## Resources and release gate

The existing curated/application files alone occupy about 15.5 GB; raw histories, caches, source trees and temporary outputs require additional disk space. Full collection involves tens of millions of records and archive requests; this review does not provide a measured full-run RAM/time budget. Use a production server, rate-budgeted endpoints and resumable storage. A free Colab session is intended only for the case tutorial.

Before claiming a complete Scientific Data release: deposit immutable full inputs/outputs with permitted licenses and DOI; bind a reviewed code commit to them; archive the historical Pyth state; fix and revalidate semantic/schema issues; provide measured full resource requirements and independent rerun evidence. [Issue log](../metadata/issue_log.csv) records the current gaps.
