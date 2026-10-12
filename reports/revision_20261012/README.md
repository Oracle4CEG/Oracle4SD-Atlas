# Revision execution evidence

The authoritative result is [full_release.json](full_release.json): **50 checks passed**, **95 Parquet tables**, **17,341,941,711 Parquet bytes**. It records the scientific code commit, source hashes and two-stage reconstruction lineage. The final financial recomputation and validation used managed Python **3.12.12**; the native build used **3.12.7** with the recorded dependency versions. Native-build and finalization timings are separate from earlier interrupted attempts and data-transfer time.

| Evidence | Scope |
|---|---|
| [native_public_download.json](native_public_download.json) | All 64 original inputs downloaded through public immutable URLs; 1,807,346,651 bytes verified |
| [full_publication.json](full_publication.json), [full_public_verification.json](full_public_verification.json) | 143 published files: 95 canonical tables, one additional prediction Parquet and metadata/logs; 47 direct metadata downloads and 96 remote LFS SHA-256 bindings |
| [native_input_identity.json](native_input_identity.json) | Native input hashes, row counts and byte lengths |
| [semantic_before.json](semantic_before.json), [semantic_after.json](semantic_after.json) | Full joins for affected UMA, Tellor and DVM interpretations and monetary summaries |
| [native_build_initial.json](native_build_initial.json) | Preserved failed gate: 850 missing rule IDs, subsequently corrected |
| [first_full_checks.json](first_full_checks.json) | Earlier 21-check run; not the final schema/release gate |
| [input_identity.json](input_identity.json) | Initial 71-file historical snapshot inspection, including replaced derived tables |
| [pyth_replay.json](pyth_replay.json) | 49 epochs, 6,566 factors and 134 counters reconstructed and compared row by row |
| [source_registry_restore.json](source_registry_restore.json) | Five pinned upstream source/registry archives restored with member hashes |
| [unit_tests.txt](unit_tests.txt) | 28 regression tests at notebook execution code d558c46 (27 at the published scientific code commit), including real-row materialization, corrupt input, sampling and future-feature invariance |
| [provenance_acceptance_tests.txt](provenance_acceptance_tests.txt) | 35 current tests, adding seven saved-evidence acceptance and rejection tests |
| [colab_evidence_local_diagnostic.json](colab_evidence_local_diagnostic.json) | Retained local evidence passes diagnostic checks; this report explicitly does not accept hosted Colab execution |
| [historical_hash_recovery.json](historical_hash_recovery.json) | One expected old manifest recovered and verified from an immutable public dataset revision |
| [provenance_public_download.json](provenance_public_download.json) | Eight supplement/registration files re-downloaded and verified at immutable dataset revision 757c8e3 |
| [provenance_card_verification.json](provenance_card_verification.json) | Updated Dataset Card and all 46 root checksum entries verified at dataset revision 356fb1a |
| [decision_benchmark](decision_benchmark/) | Three CPU baselines, chronological 489/161/160 split |
| [repaired_public_replay.json](repaired_public_replay.json) | Eight repaired-release files downloaded; 963 predictions reproduced exactly and 21 completed financial fits read successfully |
| [decision_public_replay.json](decision_public_replay.json) | 963 predictions reproduced exactly from freshly downloaded public inputs |
| [financial_benchmark](financial_benchmark/) | Seven models × three tasks; three additional Kaplan–Meier baselines; fit/status and metric availability |
| [dataset_card_manifest_verification.json](dataset_card_manifest_verification.json) | All 46 updated root manifest entries verified against the published Dataset Card revision |
| [notebook](notebook/) | All 9 cells passed at `d558c46`, with 28 tests and 28 case checks per run; executed notebook and ZIP containing both case runs, full logs and host/scientific environments |
| [review_public_loading.json](review_public_loading.json) | All 15 historical review record sets loaded through public URLs with mlcroissant 1.1.0 |

Financial F1/F2 evaluations use an explicitly labeled random fallback; F3 is chronological. Protocol-balanced sampling and protocol/time covariates can produce high pooled concordance without establishing cross-protocol generalization. Null metrics are not zeros. These reports do not claim hosted Google Colab execution, an independent scientific review, or a dataset DOI.
