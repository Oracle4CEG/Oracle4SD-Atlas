# Validation status

The small case has 28 top-level checks, covering source identity, an 85-field episode schema, exact prior-summary values, canonical evidence and economic/cross-chain links. The 30 canonical and 13 linkage child checks are retained as separate tables with their denominators. See the case validation JSON and fresh reproduction report.

The larger audit contains both passes and failures. Known failures include false challenged labels from zero addresses, mistaken applied-slash labels, reversed Tellor challenge/report semantics, missing winner reward components, common schema drift, missing timestamps and two historical checksum conflicts. They remain open. [Issue log](../metadata/issue_log.csv), [historical validation](../reports/core_audit_20260915/validation_results.csv).

Passing software tests demonstrates behavior for the tests exercised. It does not validate all protocol histories, establish representativeness, supply independent ground truth or certify financial interpretations.
