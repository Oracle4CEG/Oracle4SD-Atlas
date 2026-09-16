# Collection and transformation methods

## Reference and adaptation

Luo, B., Zhang, Z., Wang, Q. and He, B. (2024), [Multi-Chain Graphs of Graphs: A New Approach to Analyzing Blockchain Datasets](https://proceedings.neurips.cc/paper_files/paper/2024/file/3205b048f9cc54b9f7963db0b0f52d53-Paper-Datasets_and_Benchmarks_Track.pdf), NeurIPS Datasets and Benchmarks, §3.2. [Author code](https://github.com/Xtra-Computing/Cryptocurrency-Graphs-of-graphs). The reference was read from the official proceedings; the locally supplied DIVE PDF is a separate manuscript-structure reference.

Section 3.2 collects token transfers through Ethereum, Polygon and BNB Smart Chain explorers, selects active tokens and uses explorer token labels. We adapt its explicit source selection and record-level provenance discipline to oracle mechanisms. We do not adopt its token popularity thresholds, token graph prediction task or fraud labels. No GoG implementation code is copied.

| Collection decision | Oracle4SD adaptation |
|---|---|
| Cohort | Registered oracle contracts/programs, deployment versions and bounded observation periods |
| Observation | Request lifecycle, voter/request payoff, report, payment or provider/epoch according to protocol |
| Acquisition | EVM receipts/logs/headers; Solana signatures and instructions; Tellor ABCI/block results; Flare native reward files |
| Labels | Contract-defined event and adjudication meanings; preserve their object (challenge versus report) and version |
| Evidence | Source transaction/log or native key, code/source hashes, exact cutoff, pagination and failure status |
| Limits | Protocol adjudication is not external truth; an absent response is not a zero event count |

Explorer tags would be descriptive metadata with their source and retrieval date, not truth labels. BNB Smart Chain is part of the reference paper's scope, not the present dataset. We retain token identity and decimals rather than pooling unlike assets.

## Working example

An oracle brings a claim into a smart contract, a program executed by a blockchain. UMA allows a proposal, a challenge backed by collateral, adjudication on Ethereum and settlement on Polygon. A receipt records a transaction's execution and emitted logs; a header supplies its block identity and time. A contract ABI describes how to decode these logs. A transaction hash identifies a transaction, not an independent observation for every derived table.

The [fixed specification](../data/data_source/uma_case/case_spec.json) selects four Polygon transactions at blocks 63,645,613–63,813,887 and one Ethereum resolution at block 21,103,395 (2024-10-29 to 2024-11-03 UTC). All precede the fixed 2026-06-30 cutoff. This is purposive case selection, not a random or representative sample.

1. Acquire seven files and verify SHA256, a digest of the file bytes. Bundled replay uses no network; public-download fetches the two pinned snapshots; live mode recollects selected transactions.
2. Match each receipt to the specified block hash, require successful execution, retain removed-log checks and distinguish historical from latest-code evidence.
3. Decode nine Polygon protocol logs and eight selected USDC.e transfers with pinned source/ABI evidence. Preserve raw integer amounts and source identifiers.
4. Link the Polygon request and dispute to Ethereum adjudication using the request identifier and exact evidence. The project's grade A denotes linkage strength.
5. Apply source-defined settlement rules. The winner receives 1,000 USDC.e: 750 own principal plus 250 gain. The configured 5 USDC.e request reward is not treated as the winner's realized reward. Off-chain investigation cost and external truth remain unavailable.
6. Emit one 85-field episode and child tables; validate against raw-derived assertions, schema and a preserved earlier summary. The earlier summary is a regression reference, not independent ground truth.

## Versions and full history

[Acquisition profiles](../metadata/acquisition_profiles.json) contain per-source endpoints, ranges, pagination, retries and code paths. [Coverage](../reports/core_audit_20260915/protocol_coverage.csv) separates starts, cutoffs and collection times. Post-cutoff retrieval is allowed only when observations are bounded correctly and the snapshot limitation is disclosed. Pyth's later rolling snapshot supports a retained epoch subset, not a reconstruction of all earlier state.

The full pipeline joins native tables into a common evidence layer, then makes economic and realized-transfer projections. The different layers overlap. The common schema has 49 columns; the case schema has 85 fields. [Historical findings](../reports/core_audit_20260915/known_issues.csv) remain failures, including disagreement between some downstream labels and protocol meanings.

## Code attribution

The [mentor template](https://github.com/Oracle4CEG/Oracle4SD-Atlas/tree/2ca64c50c43e189aa9cfc2cacd03520b71119301) supplies folder structure, safe output concepts and the eight-part tutorial organization. Its MIT notice is retained. Native decoder and builder code comes from the local oracle-nature project, with original/imported SHA256 values in [production imports](../metadata/production_code_imports.csv). Public-node defaults replace private endpoint defaults; Flare/Pyth source revisions are fixed. Original execution did not have a root Git identity, so this import cannot prove the historical bytes were co-built from this new commit. UMA source licenses are preserved separately.
