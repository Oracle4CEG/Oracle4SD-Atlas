# Contributing to Oracle4SD Atlas

Use a personal fork and a review branch; open a PR into Oracle4CEG/Oracle4SD-Atlas. Keep this MIT notice and third-party licenses. Do not commit credentials, private endpoints, full unreviewed datasets or notebooks containing secrets.

Describe the scientific scope of changes. If monetary or label semantics change, version the schema/rules, preserve prior inputs and references, report affected rows and regenerate only explicitly authorized outputs. Never update a frozen expected result merely to make a test pass.

Run `python scripts/check_repository.py`, `python -m unittest discover -s tests -v` and a fresh `python scripts/run_pipeline.py --output runs/review-unique-name`. Changes to the tutorial also require a new isolated notebook execution record. Record the tested code commit and dirty status. Human review and hosted Colab execution must be reported separately from automated checks.

Full-core failures remain open until their specific evidence and revalidation results are included. Use metadata/issue_log.csv and docs/HANDOFF.md to scope corrections.
