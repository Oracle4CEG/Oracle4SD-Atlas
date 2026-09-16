PYTHON ?= python
.PHONY: check test run
check:
	$(PYTHON) scripts/check_repository.py
test:
	$(PYTHON) -m unittest discover -s tests -v
run:
	$(PYTHON) scripts/run_pipeline.py
