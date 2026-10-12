# Public data releases

Dataset: [OracleEconLab-Oracle-Incentives-v1](https://huggingface.co/datasets/Oracle4CEG/OracleEconLab-Oracle-Incentives-v1).

The repaired full Atlas uses separate immutable components in [data_releases.json](../configs/data_releases.json):

| Component | Revision | Scope |
|---|---|---|
| Native inputs | `c7df3127756d831a61c781d0531c155dc8d9c2fb` | 64 frozen input tables; all publicly downloaded and verified |
| Source registries | `212d469bcae7acdf22a19736e861b4c85596cd73` | Five pinned public upstream archives with member hashes and licenses |
| Repaired outputs | `57ab1e2409652291c75f02c9e066c52011d8b4ad` | 95 canonical tables, one additional prediction Parquet, metadata and execution records; 143 files total |

Use [FULL_DATA.md](FULL_DATA.md) for verified downloads and reconstruction. Current code and schema identities are in [release.json](../metadata/release.json). Public verification distinguishes direct byte downloads from remote LFS SHA-256 bindings; it does not claim a second download of all 17.34 GB of outputs.

The original review subset remains at revision `aabcff2e1492df35f0aaa9abef657133fffe9b81` (historical version 1.5.0-draft). The small-case public-download mode still retrieves its two receipt snapshots and verifies their fixed hashes. Other case inputs are bundled.

The root viewer and root Croissant describe only the original 15 review tables. Repaired metadata was published at `daa45be70a0f2a457b2d77ea70217f97a12cfba3`, with immutable data links; all 15 record sets load with mlcroissant 1.1.0. Full Atlas tables use their separate catalog, dictionary and manifests. No full-Atlas Croissant coverage, hosted Colab pass, complete historical person/agent provenance or DOI is inferred from these checks.
