"""Select and verify the retained records displayed in Appendix B.2.

Usage: python temporal_source/build_appendix_b_examples.py --data-root DATASET_DEPOSIT
The full data deposit supplies native tables and its versioned file manifest.
"""
from pathlib import Path
import argparse
import hashlib
import json

import pandas as pd
import pyarrow.parquet as pq


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-root', type=Path, required=True)
    parser.add_argument('--paper-root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    native = args.data_root / 'data/native'
    target = args.paper_root / 'supplementary/temporal'
    manifest = pd.read_csv(args.data_root / 'metadata/file_manifest.csv').set_index('path')
    checks = []

    def check(name, condition):
        checks.append({'check': name, 'passed': bool(condition)})
        if not condition:
            raise ValueError(name)

    def row(table, ordinal):
        # Read only the batch needed for this bounded example.
        batch = next(pq.ParquetFile(native / (table + '.parquet')).iter_batches(batch_size=ordinal + 1))
        return batch.slice(ordinal, 1).to_pylist()[0]

    def utc(integer, unit):
        return pd.to_datetime(int(integer), unit=unit, utc=True)

    def iso(value, precision='seconds'):
        return pd.Timestamp(value).isoformat(timespec=precision).replace('+00:00', 'Z')

    def source(table, ordinal, record):
        path = 'data/native/' + table + '.parquet'
        keys = {k: record[k] for k in (
            'source_tx', 'source_block', 'log_index', 'oo_request_id', 'reporter',
            'query_id', 'block_number', 'source_tx_index', 'epoch_id', 'publisher'
        ) if k in record}
        return {'table': table, 'row_ordinal': ordinal, 'native_keys': keys,
                'declared_source_sha256': manifest.loc[path, 'sha256']}

    uma = row('polygon_uma_request_rounds', 0)
    tellor = row('tellor_micro_reports', 0)
    pyth = row('pyth_ois_publisher_epoch_factors', 0)
    recovered = row('chainlink_staking_v02_events', 2129)
    missing = row('chainlink_staking_v02_events', 0)
    u = utc(uma['block_time'], 's')
    t = utc(tellor['timestamp_ms'], 'ms')
    a, b = utc(pyth['epoch_start_time_unix'], 's'), utc(pyth['epoch_end_time_unix'], 's')
    check('UMA integer-second conversion agrees with retained UTC', u == uma['event_time_utc'])
    check('Tellor integer-millisecond conversion agrees with retained UTC', t == tellor['event_time_utc'])
    check('Tellor millisecond remainder is preserved', t.microsecond == (int(tellor['timestamp_ms']) % 1000) * 1000)
    check('Pyth start and end agree with retained UTC', a == pyth['epoch_start_utc'] and b == pyth['epoch_end_utc'])
    check('Pyth interval has positive duration', a < b)
    check('Pyth interval has no invented event time', pyth['event_time_utc'] is None and pyth['event_time_status'] == 'epoch_record_not_an_instant_event')
    matches = pq.read_table(
        native / 'chronicle_ethereum_events.parquet',
        columns=['transaction_hash', 'block_number', 'log_index', 'block_timestamp', 'event_time_utc'],
        filters=[('block_number', '=', recovered['source_block'])]
    ).to_pylist()
    seconds = {int(m['block_timestamp']) for m in matches if m['block_timestamp'] is not None}
    check('Ethereum block lookup has one consistent retained timestamp', len(seconds) == 1)
    block_seconds = next(iter(seconds))
    r = utc(block_seconds, 's')
    check('Chainlink recovered time agrees with matching block evidence', r == recovered['event_time_utc'])
    check('Chainlink recovery retains its evidence status', recovered['event_time_status'] == 'retained_same_chain_block_join')
    check('Unmatched example retains missing event time and status', missing['event_time_utc'] is None and missing['event_time_status'] == 'missing_retained_block_time')
    recovery_examples = pd.read_csv(target / 'block_recovery_examples.csv', dtype=str).fillna('')
    for ordinal, record in [(2129, recovered), (0, missing)]:
        selected = recovery_examples[(recovery_examples.table == 'chainlink_staking_v02_events') & (recovery_examples.source_row_ordinal == str(ordinal))]
        check(f'Chainlink row {ordinal} agrees with the earlier recovery register', len(selected) == 1 and selected.iloc[0].source_tx == record['source_tx'] and selected.iloc[0].original_event_time == 'absent')

    examples = [
        {'example_id': 'E1', 'observation': 'UMA request', **source('polygon_uma_request_rounds', 0, uma),
         'raw_fields': ['block_time'], 'raw_values': [str(uma['block_time'])], 'unit': 's',
         'target_fields': ['event_time_utc'], 'utc_values': [iso(u)], 'meaning': 'Recorded request-event block time; distinct from request-reference time.'},
        {'example_id': 'E2', 'observation': 'Tellor report', **source('tellor_micro_reports', 0, tellor),
         'raw_fields': ['timestamp_ms'], 'raw_values': [str(tellor['timestamp_ms'])], 'unit': 'ms',
         'target_fields': ['event_time_utc'], 'utc_values': [iso(t, 'milliseconds')], 'meaning': 'Native report timestamp with millisecond precision.'},
        {'example_id': 'E3', 'observation': 'Pyth epoch', **source('pyth_ois_publisher_epoch_factors', 0, pyth),
         'raw_fields': ['epoch_start_time_unix', 'epoch_end_time_unix'],
         'raw_values': [str(pyth['epoch_start_time_unix']), str(pyth['epoch_end_time_unix'])], 'unit': 's',
         'target_fields': ['epoch_start_utc', 'epoch_end_utc'], 'utc_values': [iso(a), iso(b)],
         'meaning': 'Half-open support interval [start, end); neither payment nor instantaneous event time.'},
        {'example_id': 'E4', 'observation': 'Chainlink staking event', **source('chainlink_staking_v02_events', 2129, recovered),
         'raw_fields': [], 'raw_values': [None], 'unit': None,
         'target_fields': ['event_time_utc'], 'utc_values': [iso(r)],
         'meaning': 'Missing execution time recovered from a consistent retained Ethereum block reference.',
         'matched_chain': 'Ethereum', 'matched_source_table': 'chronicle_ethereum_events',
         'matched_source_sha256': manifest.loc['data/native/chronicle_ethereum_events.parquet', 'sha256'],
         'matched_records': matches, 'matched_block_seconds': str(block_seconds)},
        {'example_id': 'E5', 'observation': 'Chainlink staking event', **source('chainlink_staking_v02_events', 0, missing),
         'raw_fields': [], 'raw_values': [None], 'unit': None,
         'target_fields': ['event_time_utc'], 'utc_values': [None],
         'meaning': 'No match in the retained recovery register; missing status preserved. This is not a claim that the timestamp is unknowable from other sources.'}
    ]
    target.mkdir(parents=True, exist_ok=True)
    (target / 'appendix_b_selected_examples.json').write_text(json.dumps(examples, indent=2, default=str) + '\n')
    flat = [{k: json.dumps(v, default=str) if isinstance(v, (dict, list)) else v for k, v in e.items()} for e in examples]
    pd.DataFrame(flat).to_csv(target / 'appendix_b_selected_examples.csv', index=False)

    def stamp(value, millis=False):
        s = iso(value, 'milliseconds' if millis else 'seconds').removesuffix('Z')
        return s.replace('T', r'\newline ')

    rows = [
        r'\textbf{E1} UMA request & ' + str(uma['block_time']) + r' s & ' + stamp(u) + r' & Exact second conversion; request-event block time. \\',
        r'\textbf{E2} Tellor report & ' + str(tellor['timestamp_ms']) + r' ms & ' + stamp(t, True) + r' & Exact millisecond conversion; fractional seconds retained. \\',
        r'\textbf{E3} Pyth epoch & $[' + str(pyth['epoch_start_time_unix']) + r',$\newline $' + str(pyth['epoch_end_time_unix']) + r')$ s & Start: ' + a.strftime('%Y-%m-%d') + r'\newline End: ' + b.strftime('%Y-%m-%d') + r'\newline Both at 00:00:00 & Epoch support interval; no event or payment time inferred. \\',
        r'\textbf{E4} Chainlink staking & Missing; Ethereum block ' + f"{recovered['source_block']:,}" + r' & ' + stamp(r) + r' & Recovered from a retained Chronicle record for the same Ethereum block. \\',
        r'\textbf{E5} Chainlink staking & Missing; Ethereum block ' + f"{missing['source_block']:,}" + r' & Missing & No retained block-time match; value remains missing. \\'
    ]
    tex = r'''\begin{table}[!htbp]
\centering\tabstyle
\caption{Native-to-UTC examples from retained observations. Epochs use $[a,b)$ intervals; missing values remain explicit. Record identifiers and source matches accompany the examples.}
\label{tab:temporal_examples}
\begin{tabularx}{\linewidth}{@{}L{.16\linewidth}L{.23\linewidth}L{.25\linewidth}Y@{}}
\toprule\tablehead
Observation & Native value & UTC representation & Interpretation \\
\midrule
''' + '\n'.join(rows) + r'''
\bottomrule
\end{tabularx}
\end{table}
'''
    (args.paper_root / 'tables/temporal_worked_examples.tex').write_text(tex)
    result = {'passed': all(c['passed'] for c in checks), 'examples': 5, 'checks': checks,
              'scope': 'Bounded checks against retained native records and prior UTC annotations; no fresh acquisition or complete-coverage claim.',
              'source_hashes': 'Copied from the existing versioned file manifest; full source-file checksums were not recomputed for this bounded selection.',
              'table_sha256': hashlib.sha256(tex.encode()).hexdigest()}
    (target / 'appendix_b_examples_validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'examples': 5, 'passed': result['passed'], 'checks': len(checks)}))


if __name__ == '__main__':
    main()
