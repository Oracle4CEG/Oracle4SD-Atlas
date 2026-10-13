# Query Data

query.py accepts --config, --run-dir and --mode bundled|public-download|live. It acquires seven case inputs, checks source SHA256 and writes reports/acquisition.json. Bundled is offline; public-download retrieves two pinned HTTPS snapshots; live queries five transaction hashes. Source errors fail the stage.
