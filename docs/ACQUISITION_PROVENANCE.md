# Acquisition provenance supplement, 12 October 2026

The [verification receipt](../metadata/provenance_20261012/verification.json) binds all 64 frozen native inputs to 28 explicitly authored source groups and 39 retained manifests. Every input was rehashed and checked for byte length and Parquet row count against the immutable public release. Seven also match paths and hashes in the older research checksum list; absence from that older list is not a historical hash match.

The complete code and supplement are [publicly archived at dataset revision 757c8e3](https://huggingface.co/datasets/Oracle4CEG/OracleEconLab-Oracle-Incentives-v1/tree/757c8e3e17e6c302423252f493fc0fc4db498fe3/atlas/releases/atlas-repaired-20261012/acquisition-supplement). The [publication manifest](../metadata/provenance_publication.json) records code commit 38e63d2 and immutable hashes. [Fresh public downloads](../reports/revision_20261012/provenance_public_download.json) match all eight uploaded files.

The [per-table record](../metadata/provenance_20261012/native_table_provenance.json) links each input URL/hash to its transformation description, original manifests and available producer sources. The [manifest index](../metadata/provenance_20261012/manifest_index.json) identifies original hashes separately from sanitized archive hashes and extracts recorded acquisition times, cutoffs and upstream commits. Nineteen manifest hashes also match the prior archived originals. Recorded generation time is not necessarily collection start/end time. An upstream protocol source commit is not a collector execution commit.

The [raw-file audit](../metadata/provenance_20261012/raw_hash_audit.json) freshly verifies 688 retained files against their historical manifest hashes: 686 Flare reward files, the Pyth rolling state snapshot and the UMA settlement-receipt fallback. This is 194,091,021 bytes. It does not inventory every original raw RPC segment or claim that these 688 files are all newly published. The Pyth snapshot was already bundled; the other audit entries identify retained historical files.

The [output lineage](../metadata/provenance_20261012/output_lineage.json) covers all 95 canonical Parquet outputs. Unchanged native files have exact byte-copy bindings. Reconstructed outputs refer to a conservative build-level set of inputs and the existing [actual execution activities](../metadata/repaired_atlas_20261012/revision_provenance.json). The conservative dependency set is not a minimal dependency graph or row-level ancestry. The separate benchmark prediction artifact remains in the release download manifest.

The [52 available producer identities](../metadata/provenance_20261012/producer_index.json) link exact historical bytes to existing preserved sources or supplemental source copies. They do not establish which exact source ran historically. Supplemental historical producers are archival evidence; use the supported reconstruction commands for execution. Original collector identity, assistance by an agent and executed collector commits remain unknown where original job receipts are missing. Current DOI authorship is not retroactive evidence of original collection responsibility. The [remaining gaps](../metadata/provenance_20261012/remaining_gaps.json) explicitly keep complete historical acquisition provenance false.

One of the two old checksum conflicts now has a [recovered original manifest](../metadata/recovered_historical/public_ai_manifest.json), independently downloaded from a fixed public dataset revision and matched to the expected SHA-256. The [recovery receipt](../reports/revision_20261012/historical_hash_recovery.json) preserves the distinction between recovered old bytes and the still-different file in the original working directory. The peer-evaluation report's expected bytes remain unrecovered among inspected copies. The original mismatch report is unchanged.

For a custodian with the original acquisition workspace, rebuild the supplement in a new directory:

```bash
runs/environment/scientific/bin/python scripts/build_acquisition_provenance.py \
  --workspace /absolute/path/to/original-workspace \
  --native-root /absolute/path/to/downloaded-native-component \
  --output runs/provenance-audit
```

Ordinary release users can inspect the published supplement without that original workspace. Re-running its stored-file audit is distinct from recollecting historical state from live RPC services. Later mutable snapshots cannot supply missing historical availability evidence.
