# Bounded acquisition commands

Each command makes one public request for a registered transaction or height. Timeout is 25 seconds, retries are zero and no pagination is performed. The returned native locator must match. These probes do not collect a full history, bind historical bytecode or establish continuous coverage. Fresh outputs and failures are stored separately from frozen inputs.

Install `requests` in the selected environment, then run from the repository root:

```sh
python tutorial_revision/query.py --root tutorial_revision --branch "UMA" --mode live --output-root /tmp/oracle-live-uma
python tutorial_revision/query.py --root tutorial_revision --branch "Chainlink" --mode live --output-root /tmp/oracle-live-chainlink
python tutorial_revision/query.py --root tutorial_revision --branch "Flare FTSOv2" --mode live --output-root /tmp/oracle-live-flare_ftsov2
python tutorial_revision/query.py --root tutorial_revision --branch "Chronicle" --mode live --output-root /tmp/oracle-live-chronicle
python tutorial_revision/query.py --root tutorial_revision --branch "RedStone Push" --mode live --output-root /tmp/oracle-live-redstone_push
python tutorial_revision/query.py --root tutorial_revision --branch "DIA" --mode live --output-root /tmp/oracle-live-dia
python tutorial_revision/query.py --root tutorial_revision --branch "Pyth" --mode live --output-root /tmp/oracle-live-pyth
python tutorial_revision/query.py --root tutorial_revision --branch "Tellor" --mode live --output-root /tmp/oracle-live-tellor
```

The [executed receipts](../reports/publication_20261029/bounded_acquisition.json) record status, elapsed seconds and response hashes. Configuration, expected block/height/slot and public endpoint are in [raw_profiles.json](../tutorial_revision/metadata/raw_profiles.json). Each receipt records measured wall time; resource requirements are one response held in memory. Historical availability can change. For an unavailable endpoint retain the failed receipt and report the access block.

The [full acquisition profiles](../metadata/acquisition_profiles.json) document historical collector ranges, pagination and limitations. They are not new collection receipts.
