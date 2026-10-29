# Public-source UMA clean-room reproduction

## Scope and inputs

This fixed episode is rebuilt without reading any curated Oracle-Nature ledger. The only
semantic inputs are five public transaction receipts and canonical block headers (four on
Polygon, one on Ethereum), deployed runtime bytecode, checksum-pinned UMA contract source,
and the public case specification. Polygon provider: `polygon.drpc.org`;
Ethereum provider: `ethereum-rpc.publicnode.com`. Source verification: uma_oov2=cached_verified, uma_oov2_interface=cached_verified, uma_voting_v2_deployed_source=cached_verified.

## Reconstructed economic result

The requester configured 5 USDC.e, while proposer and disputer each escrowed 750 USDC.e
(500 bond + 250 final fee). The DVM protocol resolution overturned the proposal. The
disputer received 1,000 USDC.e: 750 returned principal plus 250 realized token gain. The
configured 5 USDC.e was refunded and rolled into the reset request, so it is not counted as
paid reward. The protocol fee is 500 USDC.e. Dispute Gas is retained separately as
`122371903978702660` raw MATIC and is never added to USDC.e.

## Validation and boundary

All 30 canonical receipt/header checks and all 13 lifecycle,
cross-chain and flow checks pass. The Polygon bridge request hash, message hash and Ethereum
DVM request ID are identical, producing `cross_chain_link_grade=A`. Seven source-code
semantic rules pass, including the separation of `VoterSlashed` accrual from
`VoterSlashApplied` stake mutation. This is protocol resolution, not independent factual
truth; the minimal five-transaction case does not reconstruct the complete voter population,
off-chain investigation cost or timestamped USD welfare.

## Reproduction

```bash
python scripts/case_studies/reproduce_uma_public_rpc_case.py
```

For deterministic offline replay after the public evidence has been frozen:

```bash
python scripts/case_studies/reproduce_uma_public_rpc_case.py \
  --snapshot-dir data/case_studies/uma_public_rpc_reproduction/raw \
  --source-cache data/case_studies/uma_public_rpc_reproduction/source \
  --offline-sources
```
