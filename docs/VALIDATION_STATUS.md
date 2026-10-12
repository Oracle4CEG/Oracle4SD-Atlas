# Validation status

The small case has 28 top-level checks, covering source identity, an 85-field episode schema, exact prior-summary values, canonical evidence and economic/cross-chain links. The 30 canonical and 13 linkage child checks are retained as separate tables with their denominators. See the case validation JSON and fresh reproduction report.

The repaired release passes [50 full-release checks](../reports/revision_20261012/full_release.json) over 95 canonical Parquet tables. UMA, Tellor and DVM interpretation errors and common schema failures are corrected. The release also retains one additional Parquet file of decision-benchmark predictions. See the [current issue resolutions](../metadata/issue_resolution_20261012.csv) and [execution evidence](../reports/revision_20261012/README.md): 28 current regression tests, seven financial models across three tasks, three decision baselines and all nine notebook cells.

The [historical issue log](../metadata/issue_log.csv) and [historical validation](../reports/core_audit_20260915/validation_results.csv) retain their failures. The two old checksum conflicts are documented, not retroactively changed into matches. Missing timestamps, independent provenance review, a dataset DOI and actual hosted Google Colab execution remain separately identified limits.

Passing software tests demonstrates behavior for the tests exercised. It does not validate all protocol histories, establish representativeness, supply independent ground truth or certify financial interpretations.
