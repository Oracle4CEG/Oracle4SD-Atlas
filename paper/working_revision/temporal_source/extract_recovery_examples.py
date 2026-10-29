"""Extract actual matched and unmatched records for each missing-clock branch."""
from pathlib import Path
import argparse
import pyarrow.parquet as pq
import pandas as pd

ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--metadata',type=Path,required=True);a=ap.parse_args()
lookup=pd.read_parquet(a.metadata/'retained_block_time_lookup.parquet').set_index(['chain','block']);samples=[]
for n in ['uma_dvm_voter_payoffs','chainlink_staking_v02_events']:
    pf=pq.ParquetFile(a.output/f'data/curated/parquet/{n}.parquet');seen=set();offset=0
    for batch in pf.iter_batches(batch_size=32768,columns=['source_tx','source_block','log_index','event_time_utc','event_time_status']):
        d=batch.to_pandas()
        for state in ['retained_same_chain_block_join','missing_retained_block_time']:
            if state in seen:continue
            q=d[d.event_time_status==state]
            if len(q):
                idx=q.index[0];v=q.iloc[0];key=('Ethereum',v.source_block);e=lookup.loc[key] if key in lookup.index else None
                samples.append(dict(table=n,source_row_ordinal=offset+int(idx),source_tx=v.source_tx,source_block=v.source_block,log_index=v.log_index,original_event_time='absent',event_time_utc='' if pd.isna(v.event_time_utc) else v.event_time_utc.isoformat(),event_time_status=state,matched_source_table='' if e is None else e.source_table,matched_source_seconds='' if e is None else int(e.timestamp_s)))
                seen.add(state)
        offset+=len(d)
        if len(seen)==2:break
pd.DataFrame(samples).to_csv(a.metadata/'block_recovery_examples.csv',index=False)
