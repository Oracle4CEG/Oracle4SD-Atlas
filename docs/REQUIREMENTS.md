# Requirements

Case: Python 3.12; CPU; approximately 2 GB RAM suggested; less than 1 MB fixed source evidence plus dependencies and generated outputs. No wallet or secret is required. Exact direct package pins: requirements.txt. Full freeze and measured elapsed times: reports/reproducibility/.

Notebook authoring/execution additionally uses requirements-colab.txt. The tutorial creates an isolated environment and invokes its Python for all scientific stages, so hosted notebook package changes do not overwrite project dependencies.

The supported full replay uses `requirements-release.txt` and the transitive `constraints-release.txt`, managed Python 3.12.12, Linux x86-64 and CPU. The 64 frozen inputs total 1.81 GB; reserve at least 40 GB disk and preferably 8 GB RAM. Recorded native-build/finalization time is about 39 minutes, excluding earlier interrupted attempts and transfers; peak measured RSS is 4.98 GiB. Detailed evidence and caveats are in [FULL_DATA.md](FULL_DATA.md).

Historical collectors may require archive RPC access and protocol-specific indexers. Their costs and quotas depend on the provider and were not measured by the offline replay. Five pinned source-registry archives and the historical Pyth snapshot are available. No paid provider is required to download frozen inputs and reproduce the supported experiments.
