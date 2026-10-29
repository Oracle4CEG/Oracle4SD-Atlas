SELECT r.*,p.event_time_utc proposal_utc,p.transaction_index proposal_tx_index,p.log_index proposal_log_index,
    d.event_time_utc dispute_utc,s.event_time_utc settlement_utc,s.transaction_index settlement_tx_index,s.log_index settlement_log_index,
    l.cross_chain_match_grade,l.resolved_price_consistent,l.dvm_request_id,f.settlement_flow_exact
    FROM read_parquet('overleaf_revision_20261026_guide2/temporal_data/data/curated/parquet/polygon_uma_request_rounds.parquet') r
    LEFT JOIN read_parquet('overleaf_revision_20261026_guide2/temporal_data/data/curated/parquet/polygon_oov2_events.parquet') p ON r.oo_request_id=p.oo_request_id AND p.event='ProposePrice'
    LEFT JOIN read_parquet('overleaf_revision_20261026_guide2/temporal_data/data/curated/parquet/polygon_oov2_events.parquet') d ON r.oo_request_id=d.oo_request_id AND d.event='DisputePrice'
    LEFT JOIN read_parquet('overleaf_revision_20261026_guide2/temporal_data/data/curated/parquet/polygon_oov2_events.parquet') s ON r.oo_request_id=s.oo_request_id AND s.event='Settle'
    LEFT JOIN read_parquet('overleaf_revision_20261026_guide2/temporal_data/data/curated/parquet/uma_polygon_ethereum_grade_a_links.parquet') l ON r.oo_request_id=l.oo_request_id
    LEFT JOIN read_parquet('overleaf_revision_20261026_guide2/temporal_data/data/curated/parquet/polygon_uma_request_flow_qc.parquet') f ON r.oo_request_id=f.oo_request_id