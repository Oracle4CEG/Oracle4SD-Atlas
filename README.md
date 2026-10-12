# Oracle4SD Atlas

Oracle4SD Atlas reconstructs how blockchain oracle requests are challenged, adjudicated and paid. Protocol decisions, independent factual truth, principal at risk, accrued entitlements and realized payments remain separate.

**Reconstruction version:** `atlas-repaired-20261012`, common schema **2.0.0**. **Observation cutoff:** 2026-06-30 23:59:59 UTC. The earlier one-request teaching example remains available as `uma-public-rpc-case-v1`.

## Run a small real case

From a fresh checkout, create the scientific environment. The bootstrap downloads pinned Python 3.12.12, so the host does not need a working `venv`/`ensurepip` installation.

```bash
python3 scripts/bootstrap_environment.py --output runs/environment
runs/environment/scientific/bin/python scripts/run_pipeline.py --output runs/my-first-case
runs/environment/scientific/bin/python -m unittest discover -s tests -v
```

The case uses five real transactions across Polygon and Ethereum. Expected result: `validation_passed: true`, with 28 case checks. Its 1,000 USDC.e winning transfer separates into 750 returned principal and 250 token gain; it is not a measurement of total economic profit.

The [notebook](notebooks/Oracle4SD_Atlas_Tutorial.ipynb) retains two runs, complete command logs, interpreter identities and package freezes in a downloadable ZIP. Hosted Google Colab execution is reported separately from execution in a fresh local notebook kernel.

## Download and rebuild the full Atlas

```bash
runs/environment/scientific/bin/python scripts/download_atlas.py \
  --component native --output runs/native
runs/environment/scientific/bin/python scripts/rebuild_atlas.py \
  --input-root runs/native --output runs/full-atlas \
  --from-native --with-trajectory-views --with-benchmarks
runs/environment/scientific/bin/python scripts/build_release_metadata.py \
  --release runs/full-atlas
```

The 64 frozen inputs total 1.81 GB. Downloads use immutable revisions and are checked against SHA-256 and byte lengths. The builder reconstructs the 105,588,120-row common layer, research samples, economic layers and application views. Layers overlap; their row counts must not be added as distinct observations.

See [full reproduction instructions](docs/FULL_DATA.md) for downloading prepared outputs, a small 810-observation experiment, disk requirements, field documentation and the boundary between offline replay and fresh network collection. The [revision record](docs/REVISION_20261012.md) explains the UMA, Tellor, DVM, schema, Pyth and metadata repairs with their verification evidence.

## Contents

| Path | Purpose |
|---|---|
| [code/reconstruction](code/reconstruction/) | Versioned native-layer and application builders used by this revision |
| [code/production](code/production/) | Preserved historical import for comparison |
| [configs/data_releases.json](configs/data_releases.json) | Immutable download URLs, sizes and hashes |
| [data/data_source](data/data_source/) | Bundled case evidence, archived Pyth state and build metadata |
| [schemas](schemas/) | Reviewed common-layer schema and semantic enums |
| [metadata](metadata/) | Source inventories, historical identities and repaired review metadata |
| [reports/revision_20261012](reports/revision_20261012/) | Executed checks, before/after counts and experiment evidence |
| [tests](tests/) | Real-row regression fixtures and failure-path tests |

The dataset covers native records from UMA, Chainlink, Tellor, Flare and Pyth, with limited Chronicle, RedStone and DIA extensions. The 56-category ecosystem census is a separate scope. Missing timestamps remain missing unless source evidence establishes them. Machine checks do not replace independent scientific review or a historical acquisition record.

Code is [MIT](LICENSE); original documentation and derived evidence are [CC BY 4.0](DATA_LICENSE.md). Third-party contract/source licenses are preserved in [notices](THIRD_PARTY_NOTICES.md). Cite the actual code commit and immutable data revision. No dataset DOI is assigned here.
