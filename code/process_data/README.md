# Process Data

process.py reads the acquisition manifest, rechecks input hashes and invokes the imported real UMA case builder. It emits one episode and eight child/QC CSV tables. It never fills absent evidence with zero. Inputs, rule source and counts are written to reports/processing.json.
