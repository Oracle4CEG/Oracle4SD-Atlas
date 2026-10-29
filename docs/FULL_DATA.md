# Current ten-product release

Use `configs/atlas_utc_release.json` for the dataset repository, fixed revision and version prefix. `scripts/load_atlas_product.py` lists product members and retrieves selected files with checksums. The release contains 100 physical tables; Viewer configurations each expose one representative schema. Shared tables require explicit branch/key filtering.

The reproducibility boundaries are: original chain/API response → retained native table → common/economic representation → prediction/daily product. The bundled raw responses cover selected locators only. Full reconstruction starts from retained native tables; historical operator identities and exhaustive raw collection receipts remain incomplete. The new data preserve supported UTC clocks and clock companions. Older application/model tables are not part of the updated ten-product claim.

The commands below are the retained predecessor reconstruction route. They reproduce the earlier 95-table output, not the current UTC/daily extension. Current builders are in `code/revision`; see the main README and table catalogue.

## Rebuild the current derived products

After downloading the complete version directory, supply its local root as `--deposit`. The preparation step arranges native table paths expected by the builders.

```sh
python code/revision/prepare_native_layout.py --deposit /path/to/atlas-utc-20261029 --output /tmp/oracle-native
python code/revision/build_prediction.py --native /tmp/oracle-native --out /tmp/oracle-task
python code/revision/build_daily.py --native /tmp/oracle-native --raw-root reproduction_inputs --out /tmp/oracle-daily
python code/revision/build_escrow.py --native /tmp/oracle-native --out /tmp/oracle-daily
```

For common/economic tables use `code/revision/load_core_with_utc.py` to join supported clocks by record identity. The old integer-second labels remain provenance. `code/revision/assemble_release.py` is the earlier local assembly recipe; published metadata and release identity supersede its local draft labels.

---

# Full Atlas: download, reconstruct and run experiments

The supported reconstruction starts from **64 frozen native/curated input files (1,807,346,651 bytes)**. It builds the common layer, economic projections, research samples and application views. These are the retained native tables, not every original RPC response. Fresh historical network collection is separate and is not required to reproduce this release.

## Install without relying on the host's venv package

Run from the repository root. The bootstrap needs a host Python with pip and internet. It downloads its own Python 3.12.12 and installs the pinned scientific dependencies; the host Python is not used for scientific processing.

```bash
python3 scripts/bootstrap_environment.py --output runs/environment
```

The validated platform is Linux x86-64 on CPU. Subsequent commands use `runs/environment/scientific/bin/python`. Installation logs, dependency freeze and interpreter identities are saved under `runs/environment/`.

## Download verified inputs and rebuild

```bash
runs/environment/scientific/bin/python scripts/download_atlas.py \
  --component native --output runs/native
runs/environment/scientific/bin/python scripts/rebuild_atlas.py \
  --input-root runs/native --output runs/full-atlas \
  --from-native --with-trajectory-views --with-benchmarks
runs/environment/scientific/bin/python scripts/build_release_metadata.py \
  --release runs/full-atlas
```

The downloader uses immutable revisions, byte lengths and SHA-256 digests in [data_releases.json](../configs/data_releases.json). It verifies existing files and resumes at file boundaries. A changed existing file is an error; use a new directory to retain both versions. The builder refuses to overwrite an existing output directory and verifies all native inputs before constructing data.

The success record is `runs/full-atlas/validation/full_release.json`. Full child-process logs and package versions are retained beside it. `metadata/file_manifest.json` records output identities; `metadata/table_catalog.json`, `field_dictionary.json`, `time_coverage.csv` and `accountability_events.schema.json` document the data. Check scope matters: an economic consistency check does not establish independent factual truth.

To inspect released outputs without rebuilding:

```bash
runs/environment/scientific/bin/python scripts/download_atlas.py \
  --component repaired --output runs/released-atlas
```

For individual files add `--include data/curated/parquet/tellor_disputes.parquet` (repeat for multiple paths). Select `native` for original input identities and `repaired` for reconstructed output identities.

Read a projection without loading the 105-million-row table into RAM:

```bash
runs/environment/scientific/bin/python - <<'PY'
import duckdb
con = duckdb.connect(config={"threads": 2, "memory_limit": "2GB"})
path = "runs/released-atlas/data/curated/parquet/accountability_events.parquet"
rows = con.execute("""
    SELECT oracle_network, event_granularity, reward_amount_raw,
           reward_asset_decimals, truth_basis, rule_id
    FROM read_parquet(?) WHERE oracle_network = 'UMA' LIMIT 5
""", [path]).fetchdf()
print(rows.to_string(index=False))
PY
```

Keep exact raw amounts as strings or sufficiently wide decimal integers. A raw reward-class value does not by itself establish payment; inspect the stage/evidence fields or the realized-event layer. Nulls remain unknown/unobserved/not applicable according to native context.

## Small experiment first

The chronological decision benchmark needs two small files:

```bash
runs/environment/scientific/bin/python scripts/download_atlas.py \
  --component native --output runs/decision-inputs \
  --include data/applications/trustworthy_ai_challenge/decision_samples.parquet \
  --include data/applications/trustworthy_ai_challenge/splits.parquet
runs/environment/scientific/bin/python scripts/run_decision_benchmark.py \
  --release runs/decision-inputs --output runs/decision-experiment
```

This executes a majority baseline, logistic regression and histogram gradient boosting on 810 frozen observations. It validates sample/split identity, chronological ordering and an explicit feature allowlist; fits preprocessing on training data; and saves metrics, predictions and checks. These are small retrospective experiments, not evidence of profitable trading or independently verified historical availability of every off-chain field.

`--with-benchmarks` also runs the financial survival experiment on rebuilt lifecycle tables. Inspect fitting failures and undefined metrics in `data/applications/financial_benchmark/metrics.parquet`; they are not successful scores. A random-split fallback is explicitly labeled where chronological evaluation is infeasible and must not be pooled with chronological results. Unimplemented model families are registered as not executed.

Historical OATA model runners are retained for inspection. Reconstructed retrospective trajectories are descriptive data, not a certified decision-time feature set. The supported decision experiment above uses a separate allowlist. Do not treat historical prefix/trajectory features as proof of leakage-free prediction.

## Historical Pyth state

The original compressed snapshot is included at [pyth_historical](../data/data_source/pyth_historical/), with acquisition metadata and SHA-256. Replay it offline:

```bash
runs/environment/scientific/bin/python scripts/replay_pyth_snapshot.py \
  --output runs/pyth-replay
```

This reconstructs 49 reward epochs, 6,566 publisher/epoch factors and 134 slash-counter records. The full builder also compares every row against the three frozen reference tables. Querying the rolling endpoint today is not a replay of this historical state.

## Evidence, resources and limits

Five upstream source/registry trees (Chronicle Scribe, Chronicle validator registry, RedStone, Pyth governance and Tellor Layer) are archived from immutable public GitHub commits. Restore them without executing upstream code:

```bash
runs/environment/scientific/bin/python scripts/restore_source_registries.py \
  --output runs/source-workspace
```

The script verifies archive and member hashes, restores regular files to collector-compatible `data/raw/source_audit/` paths, and retains upstream licenses. The archives retain upstream symlinks, while the restore script deliberately does not follow or create them. Its validation report records all restored regular files. Remaining public source/deployment references are in the source audit metadata; source identity alone does not establish an on-chain deployed binary match.

The original 15-table review deposit can also be checked through its actual public URLs:

```bash
runs/environment/scientific/bin/python scripts/validate_review_deposit.py \
  --output runs/review-public-loading.json
```

The historical 71-file [inventory](../metadata/full_data_inventory.csv) and [audit](../reports/core_audit_20260915/) preserve original identities and failures. Seven derived tables are replaced by the reconstruction; old hashes are not reassigned to repaired data.

Plan for at least 40 GB of free disk for inputs, overlapping materialized layers, trajectory tables and temporary files. Builders generally limit DuckDB to two threads and 4 GB; survival models use additional workers and memory. The full-run resource report is measured evidence for this machine, not a universal hardware guarantee. Use the small case or decision experiment in free Colab; run the full Atlas on an adequately provisioned workstation or server.

Original collectors and source references are retained in [code/reconstruction](../code/reconstruction/) and [acquisition profiles](../metadata/acquisition_profiles.json). Some historical collectors require archived source trees, archive RPC access or protocol-specific indexers. The 64-table replay does not recreate unavailable RPC histories, recover missing native timestamps, assign a DOI, or supply independent author provenance for every historical operation. The [revision record](REVISION_20261012.md) separates technical repairs from remaining publication work.
