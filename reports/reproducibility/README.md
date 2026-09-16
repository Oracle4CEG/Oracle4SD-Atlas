# Fresh environment verification

This directory records tests of `uma-public-rpc-case-v1`. The local fresh-kernel notebook execution report records the exact code commit, runtime, execution counts and whether any cell failed. `environment.freeze.txt` records installed packages. `test-results.txt` and `public-download.json` record separate regression and immutable-download checks.

The notebook clones a pinned code commit into a new workspace, creates its own isolated scientific environment and executes query, inspection, processing, analysis and technical validation. It also runs the pipeline independently a second time and compares scientific values. Generated timestamps and paths are not claimed byte-identical.

Hosted Google Colab UI execution and independent human review are not claimed. They remain handoff checks in docs/HANDOFF.md. Full protocol recollection was not performed by these tests.

The fresh environment exposed a missing Keccak backend that had been supplied by the old workstation environment. The requirements now explicitly include eth-hash with pycryptodome; constraints.txt pins the resolved transitive versions. The final notebook creates a second entirely new scientific environment to verify the fix.

full-local-identity.json records a new read-only verification of all 71 authorized local candidate files: every SHA256 and Parquet row count matched the inventory. Mounted author-data symlinks were explicitly allowed for that run. This verifies file identity, not full-row semantics or public access.

The first full notebook run also exposed inheritance of the host IPython plotting backend in isolated child processes. The tutorial now explicitly uses the noninteractive Agg backend for child commands; the corrected notebook is rerun from an empty workspace. The CI workflow executes the notebook as well as repository checks, negative tests and the case pipeline.

## Recorded results

The corrected notebook completed **9 of9 code cells**, covering all eight sections, in **54.633 seconds** on Python 3.12.7. It cloned code commit `80745c2c9edcdd2c3b4f8bbf244d89751fe4d5f3` and installed its scientific dependencies into a newly created environment. Downloaded wheel caches could be reused. Ten regression/negative tests passed; both independent case reconstructions passed 28 scoped checks and produced the same scientific summary. See notebook_execution.json and tutorial.executed.ipynb.

`environment.freeze.txt` describes the notebook kernel environment; `scientific_environment.freeze.txt` describes the separate environment actually running the pipeline. `fresh_run_environment.json` records the clean detached code checkout and source-code hashes.
