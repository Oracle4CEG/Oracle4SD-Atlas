# Atlas and research delivery boundary

Hugging Face revision `ee197fc6fd6b8d980e7c7dda4feae966efe5d28c` preserves the
existing public demonstration files and adds two separate artifact prefixes:

| Prefix | Contents | Validation scope |
| --- | --- | --- |
| `atlas/selected-inputs/2026-10-10/` | Four curated UMA source tables | SHA-256, byte lengths and row counts agree with the existing full inventory |
| `research/agentic-audit/2026-10-10/` | Research cohort, splits, evidence, recorded model runs, recovery history and reference outputs | Research-specific reconstruction, policy/guard analysis and saved-response replay; owned by Oracle-Agentic-Audit |

The [snapshot manifest](../metadata/research_snapshot.json) gives archive and
per-file identities. Verify the anonymous public download without changing local
data:

```bash
python scripts/verify_research_snapshot.py --output runs/research-source-check.json
```

The selected source tables are 514,794 OOV2 event rows, 42,676 request-round rows,
42,676 request-flow QC rows and 835 grade-A link rows. They are related tables, not
disjoint episode populations. Research selects and rechecks its 810-case cohort;
these counts do not imply 835 final experimental cases or that every request is
disputed. See the research repository's actual exclusion and feature-lineage checks.

## Code responsibilities

This repository retains acquisition profiles, protocol parsing, lifecycle
reconstruction, cleaning, data dictionaries and global QC/audit code. The
[historical production code](../code/production/README.md) covers the broader
candidate; [full-data instructions](FULL_DATA.md) explain dependencies, execution
order and unavailable historical sources. The bundled real case provides an
executable, limited validation example.

The [research repository](https://github.com/Oracle4CEG/Oracle-Agentic-Audit) owns
sample selection, model experiments, decision policies, safeguards, statistical
analysis, tables, plots and its public reproduction notebook. It consumes this
fixed selected snapshot. Atlas does not claim the research notebook as its own
full-resource construction pipeline.

## Remaining full-resource gates

Four of the inventoried files are now available in a public archive. The complete
71-file inventory (67 curated plus four application files) is still not a fully
published or semantically cleared release. Existing application-label, financial
classification and schema failures remain recorded in the
[issue log](../metadata/issue_log.csv). Historical Pyth state, source registries,
full archive/DOI, independent review and descriptor arXiv posting remain separate
work. No DOI, arXiv identifier or hosted-Colab PASS is invented here.
