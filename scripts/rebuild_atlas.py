"""Verify the 71 frozen inputs, repair full data, and rebuild application views.

Every output is written below a new directory. Original inputs are never edited.
This is an offline reconstruction from archived native/curated evidence, not
a claim to recollect all chain histories from currently available RPCs.
"""
import argparse
import csv
import hashlib
import json
import os
import platform
import resource
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code/reconstruction"))
from scripts.revision_semantics import SCHEMA_VERSION, TRUTH_DEFINITIONS, UNIT_DEFINITIONS, MAPPING_RULES, common_projection

RELEASE = "atlas-repaired-20261012"
REBUILT_TABLES = {"accountability_events","sample_b_observable_accountability",
                  "sample_c_strict_honesty_events","economic_semantics_events",
                  "realized_reward_slash_events","accountability_episodes","financial_episodes"}


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def sqlpath(path):
    return "'" + str(path).replace("'", "''") + "'"


def table(root, name):
    return f"read_parquet({sqlpath(Path(root) / 'data/curated/parquet' / (name + '.parquet'))})"


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")


def copy_file(source, target):
    """A private output name; callers must replace, never truncate linked bytes."""
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except OSError:
        shutil.copyfile(source, target)


def rewrite(con, query, target):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".new.parquet")
    if tmp.exists():
        raise FileExistsError(tmp)
    con.execute(f"COPY ({query}) TO {sqlpath(tmp)} (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)")
    tmp.replace(target)


def audit(con, root):
    ep = f"read_parquet({sqlpath(Path(root) / 'data/applications/oata/accountability_episodes.parquet')})"
    q = {
        "uma": f"""SELECT count(*) AS rows,
          count(*) FILTER(WHERE e.challenged AND (r.dispute_tx IS NULL OR r.disputer='0x0000000000000000000000000000000000000000')) AS false_challenged,
          count(*) FILTER(WHERE e.transfer_confirmed AND r.settlement_tx IS NULL) AS transfer_without_settlement,
          count(*) FILTER(WHERE r.economic_status LIKE 'settled_disputed_%' AND
            try_cast(e.reward_paid_raw AS HUGEINT) IS DISTINCT FROM
            try_cast(r.explicit_report_reward_raw AS HUGEINT)+try_cast(r.dispute_winner_reward_raw AS HUGEINT)) AS incomplete_disputed_reward
          FROM {ep} e JOIN {table(root,'polygon_uma_request_rounds')} r ON e.unit_id=r.oo_request_id
          WHERE e.episode_type='uma_oov2_request'""",
        "tellor": f"""SELECT count(*) AS rows,
          count(*) FILTER(WHERE d.vote_result NOT IN ('SUPPORT','NO_QUORUM_MAJORITY_SUPPORT')
            AND try_cast(e.principal_slashed_raw AS HUGEINT)>0) AS rejected_challenge_as_slash
          FROM {ep} e JOIN {table(root,'tellor_disputes')} d ON e.unit_id=d.dispute_id WHERE e.episode_type='tellor_dispute'""",
        "dvm": f"""SELECT count(*) AS rows,
          count(*) FILTER(WHERE list_contains(state_sequence,'PRINCIPAL_SLASHED') AND NOT state_change_confirmed) AS unapplied_principal_slash
          FROM {ep} WHERE episode_type='uma_dvm_voter'""",
        "sample_c": f"""SELECT count(*) AS rows,
          count(*) FILTER(WHERE (outcome_status LIKE '%SUPPORT' AND strict_event_class<>'tellor_report_rejected')
            OR (outcome_status LIKE '%AGAINST' AND strict_event_class<>'tellor_report_supported')) AS inverted_tellor_labels
          FROM {table(root,'sample_c_strict_honesty_events')} WHERE native_table='tellor_disputes'""",
        "financial": f"""SELECT asset,asset_decimals,protocol,terminal_event,count(*) AS rows,
          sum(try_cast(reward_paid AS HUGEINT))::VARCHAR AS reward_paid_raw,
          sum(try_cast(principal_slashed AS HUGEINT))::VARCHAR AS principal_slashed_raw
          FROM read_parquet({sqlpath(Path(root)/'data/applications/financial_benchmark/financial_episodes.parquet')}) GROUP BY ALL ORDER BY ALL""",
    }
    result = {}
    for name, query in q.items():
        cur = con.execute(query)
        fields = [x[0] for x in cur.description]
        result[name] = [dict(zip(fields, row)) for row in cur.fetchall()]
    return result


def step(output, name, args, environment):
    started = time.monotonic()
    log = output / "validation" / (name + ".log")
    print("Running", name, flush=True)
    with log.open("w") as f:
        proc = subprocess.run(args, cwd=ROOT, env=environment, stdout=f, stderr=subprocess.STDOUT)
    if proc.returncode:
        raise RuntimeError(f"{name} failed; full traceback: {log}")
    return {"name": name, "command": args, "elapsed_seconds": round(time.monotonic()-started, 3), "exit_code": 0}


def validate(con, output):
    checks = []
    def zero(name, query, scope):
        value = con.execute(query).fetchone()[0]
        checks.append(dict(name=name, violations=value, passed=value == 0, scope=scope))
    common = table(output, "accountability_events")
    schema=json.loads((ROOT/"schemas/accountability_events_v2.schema.json").read_text())
    expressions=[];schema_keys=[]
    for field,definition in schema['properties'].items():
        definition=schema['$defs'][definition['$ref'].split('/')[-1]] if '$ref' in definition else definition
        invalid=[]
        if 'type' in definition and 'null' not in definition['type']:
            invalid.append(f'"{field}" IS NULL')
        if 'pattern' in definition:
            invalid.append(f'("{field}" IS NOT NULL AND NOT regexp_full_match("{field}",{sqlpath(definition["pattern"])}))')
        if 'enum' in definition:
            invalid.append(f'("{field}" IS NOT NULL AND "{field}" NOT IN ({",".join(sqlpath(v) for v in definition["enum"])}))')
        if 'const' in definition:
            invalid.append(f'"{field}" IS DISTINCT FROM {sqlpath(definition["const"])}')
        if invalid:
            expressions.append('count(*) FILTER(WHERE '+' OR '.join(invalid)+')')
            schema_keys.append(field)
    values=con.execute('SELECT '+','.join(expressions)+' FROM '+common).fetchone()
    checks.extend(dict(name='schema_field_'+name,violations=value,passed=value==0,scope='all common rows') for name,value in zip(schema_keys,values))
    for column, allowed in (("truth_basis", TRUTH_DEFINITIONS), ("accountability_unit_type", UNIT_DEFINITIONS)):
        values = ",".join(sqlpath(x) for x in allowed)
        zero("common_"+column, f"SELECT count(*) FROM {common} WHERE {column} IS NULL OR {column} NOT IN ({values})", "all common rows; reviewed definitions in metadata/semantic_decisions.json")
    zero("common_schema_version", f"SELECT count(*) FROM {common} WHERE schema_version<>'{SCHEMA_VERSION}' OR schema_version IS NULL", "all common rows")
    zero("common_event_id_unique", f"SELECT count(*)-count(DISTINCT accountability_event_id) FROM {common}", "all common rows")
    zero("common_no_accrual_as_principal", f"SELECT count(*) FROM {common} WHERE native_table='uma_dvm_voter_payoffs' AND principal_slashed_raw IS NOT NULL", "all DVM accrual rows")
    zero("common_no_transfer_as_truth", f"SELECT count(*) FROM {common} WHERE native_table IN ('pyth_ois_stake_events','pyth_ois_economic_events') AND truth_basis<>'protocol_state_transition'", "all Pyth economic/stake rows")
    zero("common_cutoff", f"SELECT count(*) FROM {common} WHERE event_time_unix>1782863999", "all non-null common timestamps")
    economic = table(output, "economic_semantics_events")
    realized = table(output, "realized_reward_slash_events")
    zero("realized_requires_evidence", f"SELECT count(*) FROM {realized} WHERE NOT coalesce(cashflow_verified OR state_delta_verified,false)", "all realized-layer rows")
    zero("realized_requires_inclusion", f"SELECT count(*) FROM {realized} WHERE NOT coalesce(include_in_realized_reward OR include_in_realized_slash,false)", "all realized-layer rows")
    zero("accrual_excluded_from_realized", f"SELECT count(*) FROM {economic} WHERE realization_status='accrued_not_applied' AND (include_in_realized_reward OR include_in_realized_slash)", "all economic-layer rows")
    ep = f"read_parquet({sqlpath(output/'data/applications/oata/accountability_episodes.parquet')})"
    zero("episode_id_unique", f"SELECT count(*)-count(DISTINCT episode_id) FROM {ep}", "all rebuilt episodes")
    zero("episode_time_order", f"SELECT count(*) FROM {ep} WHERE end_time<start_time", "all timed episodes")
    zero("rate_is_not_reward_amount", f"SELECT count(*) FROM {ep} WHERE episode_type='pyth_publisher_epoch' AND (reward_accrued_raw IS NOT NULL OR reward_paid_raw IS NOT NULL)", "all Pyth publisher epochs")
    zero("uma_gross_principal_gain_identity", f"SELECT count(*) FROM {ep} WHERE episode_type='uma_oov2_request' AND transfer_confirmed AND try_cast(gross_payout_raw AS HUGEINT) IS DISTINCT FROM try_cast(principal_returned_raw AS HUGEINT)+try_cast(reward_paid_raw AS HUGEINT)", "all flow-confirmed UMA settlements")
    zero("uma_link_evidence", f"SELECT count(*) FROM {ep} e WHERE episode_type='uma_oov2_request' AND cross_chain_flag AND NOT EXISTS (SELECT 1 FROM {table(output,'uma_polygon_ethereum_grade_a_links')} l WHERE l.oo_request_id=e.unit_id AND l.cross_chain_match_grade='A')", "all cross-chain flagged UMA episodes")
    prefix_path=output/'data/applications/oata/prefix_episodes.parquet'
    if prefix_path.exists():
        prefix=f"read_parquet({sqlpath(prefix_path)})"
        raw_fields=[field.name for field in pq.read_schema(prefix_path) if field.name.endswith('_raw')]
        zero('prefix_hides_financial_outcomes',f'SELECT count(*) FROM {prefix} WHERE '+
             ' OR '.join(f'"{name}" IS NOT NULL' for name in raw_fields), 'all retrospective masked episodes; not a T0 certification')
        allowed="'INITIATED','ELIGIBLE','PRINCIPAL_LOCKED','ACTION_PERFORMED','REPORT_SUBMITTED','SERVICE_OBSERVED','CHALLENGED','VOTE_COMMITTED','VOTE_REVEALED'"
        zero('prefix_hides_adjudication_and_terminal_states',f'SELECT count(*) FROM {prefix} WHERE list_count(list_filter(state_sequence,x->x NOT IN ({allowed})))>0', 'all retrospective masked episodes')
    after = audit(con, output)
    for group in ("uma", "tellor", "dvm", "sample_c"):
        for key, value in after[group][0].items():
            if key != "rows":
                checks.append(dict(name=key, violations=value, passed=value == 0, scope="full affected table join"))
    return checks, after


def financial_benchmark_check(metrics):
    """Keep fresh builds and bounded finalization under the same fit gate."""
    completed=metrics[(metrics['status']=='completed') & metrics['harrell_c_index'].notna()]
    failures=metrics[metrics['status']!='completed']
    return dict(name='financial_models_complete',passed=len(completed)==21 and failures.empty,
                completed_model_track_fits=len(completed),failed_or_unestimable=len(failures),
                scope='Seven fitted models on three tasks; evaluation splits are recorded; undefined time-dependent metrics remain null')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-root", required=True, help="Root of 64 native inputs (--from-native), or the 71-file historical snapshot")
    p.add_argument("--output", required=True, help="New directory; never overwritten")
    p.add_argument("--with-trajectory-views", action="store_true", help="Also materialize all OATA state/transition and model feature tables")
    p.add_argument("--with-benchmarks", action="store_true", help="Run financial prediction experiments after rebuilding data")
    p.add_argument("--from-native", action="store_true", help="Rebuild common, research-sample and economic layers from frozen native tables")
    a = p.parse_args()
    import importlib.util
    required=['seaborn','duckdb','pyarrow']+(['sksurv','xgboost'] if a.with_benchmarks else [])
    missing=[name for name in required if importlib.util.find_spec(name) is None]
    if missing:
        raise RuntimeError(f"Missing {missing}; install requirements-release.txt before starting the full replay")
    source, output = Path(a.input_root).resolve(), Path(a.output).resolve()
    if output.exists():
        raise FileExistsError(f"Use a new output directory: {output}")
    output.mkdir(parents=True)
    (output / "validation").mkdir()
    start = time.monotonic()
    manifest = list(csv.DictReader((ROOT / "metadata/full_data_inventory.csv").open()))
    if a.from_native:
        manifest = [r for r in manifest if r["logical_table"] not in REBUILT_TABLES]
    # Bind executed source before work starts, so an edit during a long replay
    # cannot accidentally be reported as the source of already-computed results.
    executed_sources = sorted((ROOT/"code/reconstruction").rglob("*.py"))+sorted((ROOT/"scripts").glob("*.py"))
    executed_sources += [p for base in ('schemas','code/reconstruction/schemas','data/data_source/full_build_metadata','data/data_source/pyth_historical') for p in (ROOT/base).rglob('*') if p.is_file()]
    executed_sources += list(ROOT.glob('requirements*.txt'))+list(ROOT.glob('constraints*.txt'))
    source_hashes = {str(path.relative_to(ROOT)):sha256(path) for path in executed_sources}
    identity = []
    for index, row in enumerate(manifest):
        path = Path(row["path"])
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Unsafe inventory path")
        src = source / path
        if not src.is_file():
            raise FileNotFoundError(src)
        actual = sha256(src)
        rows = pq.read_metadata(src).num_rows
        passed = actual == row["sha256"] and rows == int(row["rows"]) and src.stat().st_size == int(row["bytes"])
        identity.append(dict(path=str(path), sha256=actual, rows=rows, bytes=src.stat().st_size, passed=passed))
        write_json(output / "validation/input_identity.json", identity)
        if not passed:
            raise ValueError(f"Input identity differs from reviewed snapshot: {path}")
        print(f"Verified input {index+1}/{len(manifest)}: {path.name}", flush=True)
    con = duckdb.connect(config={"threads": 2, "memory_limit": "4GB", "temp_directory": str(output/"scratch")})
    if (source/"data/applications/oata/accountability_episodes.parquet").is_file():
        write_json(output / "validation/semantic_before.json", audit(con, source))
    else:
        write_json(output/"validation/semantic_before.json", {"status":"not rerun; historical application outputs are not native inputs", "reference":"reports/revision_20261012/semantic_before.json"})
    for row in manifest:
        path = Path(row["path"])
        if str(path).startswith(("data/applications/oata/", "data/applications/financial_benchmark/")):
            continue
        copy_file(source / path, output / path)
    env = os.environ.copy()
    env.update(ORACLE_WORKSPACE=str(output), PYTHONPATH=str(ROOT/"code/reconstruction"), MPLBACKEND="Agg",
               OMP_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2", MKL_NUM_THREADS="2")
    steps = []
    if a.from_native:
        (output/"data/manifests").mkdir(parents=True,exist_ok=True)
        for path in (ROOT/"data/data_source/full_build_metadata").glob("*.json"):
            shutil.copy2(path,output/"data/manifests"/path.name)
        shutil.copytree(ROOT/"code/reconstruction/schemas",output/"schemas")
        steps.append(step(output,"native_common",[sys.executable,str(ROOT/"code/reconstruction/scripts/build_accountability_events.py")],env))
        steps.append(step(output,"native_samples",[sys.executable,str(ROOT/"code/reconstruction/scripts/build_research_samples.py"),"--parquet-dir",str(output/"data/curated/parquet"),"--output-dir",str(output/"data/curated/parquet"),"--manifest",str(output/"data/manifests/research_samples.json")],env))
        from scripts import build_realized_economic_events as economics
        economics.PARQUET=output/"data/curated/parquet"
        economics.build_views(con)
        rules=json.loads((output/"data/manifests/contract_semantics_audit.json").read_text())
        registered={r["rule_id"] for r in rules["rules"]}
        used={r[0] for r in con.execute("SELECT DISTINCT source_semantics_rule_id FROM all_economic_semantics").fetchall()}
        if used-registered:
            raise ValueError(f"Unregistered economic rules: {used-registered}")
        rewrite(con,"SELECT * FROM all_economic_semantics",output/"data/curated/parquet/economic_semantics_events.parquet")
        rewrite(con,"SELECT * FROM all_economic_semantics WHERE include_in_realized_reward OR include_in_realized_slash",output/"data/curated/parquet/realized_reward_slash_events.parquet")
    else:
        for name in ("accountability_events", "sample_b_observable_accountability", "sample_c_strict_honesty_events"):
            print("Rebuilding", name, flush=True)
            rewrite(con, common_projection(table(source, name), name.startswith("sample_c")), output/"data/curated/parquet"/(name+".parquet"))
    steps.append(step(output, "pyth_replay", [sys.executable, str(ROOT/"scripts/replay_pyth_snapshot.py"), "--output", str(output/"validation/pyth_replay"), "--reference", str(source/"data/curated/parquet")], env))
    for path in (output/"validation/pyth_replay").glob("*.parquet"):
        # Atomically replace output hardlinks; never overwrite the input inode.
        path.replace(output/"data/curated/parquet"/path.name)
    steps.append(step(output, "oata_episodes", [sys.executable, "-c", "from scripts.applications.oata.common import build_episodes; print(build_episodes())"], env))
    if a.with_trajectory_views:
        steps.append(step(output, "oata_views", [sys.executable, "-c", "from scripts.applications.oata.common import map_states,build_trajectory_views,build_tracks_and_splits; print(map_states()); print(build_trajectory_views()); print(build_tracks_and_splits())"], env))
    steps.append(step(output, "financial_views", [sys.executable, "-c", "from scripts.applications.financial.common import build_episodes,build_splits,build_descriptives; build_episodes(); build_splits(); build_descriptives()"], env))
    if a.with_benchmarks:
        steps.append(step(output, "financial_benchmarks", [sys.executable, "-c", "from scripts.applications.financial.common import run_benchmark; run_benchmark()"], env))
        steps.append(step(output, "decision_benchmark", [sys.executable, str(ROOT/"scripts/run_decision_benchmark.py"), "--release",str(output),"--output",str(output/"experiments/decision_benchmark")],env))
    checks, after = validate(con, output)
    if a.with_benchmarks:
        metrics=con.execute(f"SELECT * FROM read_parquet({sqlpath(output/'data/applications/financial_benchmark/metrics.parquet')})").fetchdf()
        checks.append(financial_benchmark_check(metrics))
    write_json(output/"validation/semantic_after.json", after)
    write_json(output/"metadata/semantic_decisions.json", dict(schema_version=SCHEMA_VERSION, truth_basis=TRUTH_DEFINITIONS, accountability_unit_type=UNIT_DEFINITIONS, mapping_rules=MAPPING_RULES))
    inventory = []
    for path in sorted((output/"data").rglob("*.parquet")):
        meta = pq.read_metadata(path)
        inventory.append(dict(path=str(path.relative_to(output)), rows=meta.num_rows, bytes=path.stat().st_size, sha256=sha256(path)))
    write_json(output/"metadata/file_manifest.json", inventory)
    changed_sources=[name for name,digest in source_hashes.items() if sha256(ROOT/name)!=digest]
    checks.append(dict(name="executed_source_identity_unchanged",passed=not changed_sources,changed_files=changed_sources))
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    report = dict(release=RELEASE, passed=all(x["passed"] for x in checks), checks=checks, steps=steps,
                  input_files=len(identity), output_files=len(inventory),
                  scope="Full registered curated snapshot and reconstructed applications; fresh historical network collection is not claimed",
                  code_commit=git.stdout.strip(), source_sha256=source_hashes, python=platform.python_version(),
                  elapsed_seconds=round(time.monotonic()-start,3),
                  max_rss_kib=max(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss),
                  output_file_bytes=sum(x["bytes"] for x in inventory), finished_utc=datetime.now(timezone.utc).isoformat())
    write_json(output/"validation/full_release.json", report)
    with (output/"validation/environment.freeze.txt").open("w") as f:
        subprocess.run([sys.executable,"-m","pip","freeze"],stdout=f,check=True)
    print(json.dumps({"output":str(output),"passed":report["passed"],"checks":len(checks),"elapsed_seconds":report["elapsed_seconds"]},indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
