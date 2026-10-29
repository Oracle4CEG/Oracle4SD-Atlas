"""Create DuckDB views joining unchanged core records to validated UTC clocks."""
from pathlib import Path
import argparse,json
import duckdb

TABLE_KEYS = {
    'accountability_events':'accountability_event_id',
    'sample_b_observable_accountability':'accountability_event_id',
    'sample_c_strict_honesty_events':'accountability_event_id',
    'economic_semantics_events':'evidence_id',
    'realized_reward_slash_events':'evidence_id',
}

def register_views(connection, deposit):
    root=Path(deposit).resolve()
    connection.execute("SET TimeZone='UTC'")
    for name,key in TABLE_KEYS.items():
        parent=str(root/'data/core'/(name+'.parquet')).replace("'","''")
        clocks=str(root/'data/core_clocks'/(name+'_clocks.parquet')).replace("'","''")
        connection.execute(f'CREATE OR REPLACE VIEW "{name}_utc" AS SELECT p.*, c.* EXCLUDE ({key}) FROM read_parquet(\'{parent}\') p LEFT JOIN read_parquet(\'{clocks}\') c ON p.{key}=c.{key}')
    return [name+'_utc' for name in TABLE_KEYS]

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--deposit',required=True);p.add_argument('--database',default=':memory:');a=p.parse_args()
    c=duckdb.connect(a.database,config={'threads':2,'memory_limit':'4GB'})
    print(json.dumps({'views':register_views(c,a.deposit),'timezone':'UTC'}))
