# September 17 review handoff

## Common identity for all deliverables

Use `metadata/release.json`: review bundle `atlas-review-20260916`, runnable case `uma-public-rpc-case-v1`, cutoff `2026-06-30T23:59:59Z`, historical core audit `SD-HANDOFF-20260915`. Case results: 5 transactions, 9 protocol events, 8 transfers, 1 lifecycle, 28 scoped checks; 750 principal + 250 gain = 1,000 USDC.e gross transfer.

The larger candidate counts are historical and overlapping: 105,588,120 common / 22,723,389 economic / 19,275,854 realized. They must not be presented as the size of the runnable case or as a fully public validated release.

## Deliverables and status

- GitHub: personal fork prepared for an organization review PR. The PR and exact tested commits are recorded with the handoff response and execution reports. Human review remains pending until an independent reviewer approves.
- Colab: the project notebook can be opened through a commit-pinned GitHub Colab link. Isolated local “Run all” evidence is included; hosted Colab UI execution and any author-owned Drive share are separate pending checks.
- Manuscript: the previous evidence handoff exists locally. The author subsequently supplied the separate descriptor Overleaf project in the October handoff; manuscript editing and a compiled descriptor PDF remain outside this code-delivery update.

## Questions requiring author decisions

1. The designated Hugging Face repository is known. Full raw/curated redistribution approval and DOI deposit remain to be resolved.
2. Should the first Data Descriptor describe the narrower validated scope while the identified application-label and schema issues are repaired?
3. Who will independently review the PR and execute the shared notebook in a fresh hosted Colab runtime?
4. The descriptor Overleaf project is identified. Reconcile its Methods, Data Records and Technical Validation with the actual release before exporting the PDF.

Detailed findings and actions: [issue log](../metadata/issue_log.csv). These items are unresolved work, not statements that the complete three-deliverable handoff is finished.


## Research delivery update, 10 October 2026

The author has designated the existing Hugging Face dataset repository as the
hosting destination and supplied the separate descriptor manuscript project. Those
locations are now known; this does not imply a DOI deposit or arXiv posting.

Four selected UMA source tables are now public at an immutable dataset revision.
[The snapshot manifest](../metadata/research_snapshot.json) binds their archive,
per-file hashes and row counts to the historical full inventory. The research
records occupy a separate dataset prefix and are consumed by Oracle-Agentic-Audit.
[The delivery guide](RESEARCH_DELIVERY.md) states the boundary and verification command.
The remaining full-core deposit, semantic repairs and independent review are still
open. Neither the original one-case tutorial nor the research subset clears them.
