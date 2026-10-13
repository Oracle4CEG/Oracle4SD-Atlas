"""Reconstruct the historical 49-epoch panel without a live Solana RPC."""
import argparse
import base64
import gzip
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code/reconstruction/src"))
from oracle_ledger.pyth_ois import EPOCH_SECONDS, FRAC64_MULTIPLIER, decode_pool_config, decode_pool_data

SNAPSHOT_SHA256 = "fcd29f8b5b520c848693790459ab8304047338b8910d2478d1b76fb8502f35f4"
CUTOFF = 1782863999


def decode_snapshot(path):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != SNAPSHOT_SHA256:
        raise ValueError("Historical Pyth snapshot hash mismatch")
    snap = json.loads(gzip.decompress(raw))
    pool = decode_pool_data(base64.b64decode(snap["pool_data_base64"]))
    config = decode_pool_config(base64.b64decode(snap["pool_config_base64"]))
    if config["pool_data"] != snap["pool_pubkey"]:
        raise ValueError("Pyth pool/config identity mismatch")
    epochs, factors = [], []
    for event in sorted(pool["events"], key=lambda row: row["epoch"]):
        epoch = int(event["epoch"])
        if not epoch or (epoch + 1) * EPOCH_SECONDS > CUTOFF:
            continue
        y = int(event["y"])
        start, end = epoch * EPOCH_SECONDS, (epoch + 1) * EPOCH_SECONDS
        active = 0
        for index, (self_ratio, other_ratio, fee) in enumerate(event["publisher_factors"]):
            self_rate = y * int(self_ratio) // FRAC64_MULTIPLIER
            other_rate = y * int(other_ratio) // FRAC64_MULTIPLIER
            delegator_rate = other_rate * (FRAC64_MULTIPLIER - int(fee)) // FRAC64_MULTIPLIER
            active += bool(self_ratio or other_ratio)
            factors.append(dict(
                epoch_id=epoch, epoch_start_time_unix=start, epoch_end_time_unix=end,
                publisher_index=index, publisher=pool["publishers"][index],
                publisher_stake_account=pool["publisher_stake_accounts"][index],
                reward_rate_y_raw=str(y), self_reward_ratio_raw=str(self_ratio),
                delegated_reward_ratio_raw=str(other_ratio), delegation_fee_raw=str(fee),
                publisher_self_reward_rate_raw=str(self_rate), delegator_net_reward_rate_raw=str(delegator_rate),
                publisher_delegation_fee_reward_rate_raw=str(other_rate-delegator_rate),
                rate_decimals=6, reward_active_regime=y > 0,
                has_positive_reward_factor=self_ratio > 0 or other_ratio > 0,
                source_account=snap["pool_pubkey"], source_storage_index=event["storage_index"],
            ))
        epochs.append(dict(
            epoch_id=epoch, epoch_start_time_unix=start, epoch_end_time_unix=end,
            epoch_start_time=datetime.fromtimestamp(start, timezone.utc).isoformat().replace("+00:00", "Z"),
            epoch_end_time=datetime.fromtimestamp(end, timezone.utc).isoformat().replace("+00:00", "Z"),
            reward_rate_y_raw=str(y), rate_decimals=6, reward_active_regime=y > 0,
            registered_publishers_in_current_stable_index=len(pool["publishers"]),
            publishers_with_positive_reward_factor=active, source_account=snap["pool_pubkey"],
            source_storage_index=event["storage_index"],
        ))
    counters = [dict(publisher_index=i, publisher=p,
                     slash_events_created_lifetime=int(pool["slash_counters"][i]),
                     source_account=snap["pool_pubkey"], snapshot_slot=snap["snapshot_slot"],
                     snapshot_time_unix=snap["snapshot_time_unix"])
                for i, p in enumerate(pool["publishers"])]
    return {"pyth_ois_reward_epochs": epochs, "pyth_ois_publisher_epoch_factors": factors,
            "pyth_ois_slash_counters": counters}


def replay(output, reference=None):
    import pyarrow as pa
    import pyarrow.parquet as pq
    import duckdb
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    data = decode_snapshot(ROOT / "data/data_source/pyth_historical/rolling_program_state.json.gz")
    checks = []
    con = duckdb.connect(config={"threads": 2, "memory_limit": "1GB"})
    for name, rows in data.items():
        target = output / (name + ".parquet")
        if target.exists():
            raise FileExistsError(target)
        source = Path(reference) / target.name if reference else None
        schema = pq.read_schema(source) if source else None
        # The historical Parquet writer represented UTC instants as timezone-naive
        # timestamps; parse instants first rather than casting ISO text blindly.
        typed_rows = [{**row, **{key: datetime.fromisoformat(row[key].replace("Z", "+00:00"))
                                for key in ("epoch_start_time", "epoch_end_time") if key in row}}
                      for row in rows]
        data_table = pa.Table.from_pylist(typed_rows)
        if schema:
            data_table = data_table.select(schema.names).cast(schema)
        pq.write_table(data_table, target, compression="zstd")
        check = {"table": name, "rows": len(rows), "passed": True}
        if source:
            con.read_parquet(str(target)).create_view("actual", replace=True)
            con.read_parquet(str(source)).create_view("reference", replace=True)
            different = con.execute("SELECT count(*) FROM ((SELECT * FROM actual EXCEPT ALL SELECT * FROM reference) UNION ALL (SELECT * FROM reference EXCEPT ALL SELECT * FROM actual))").fetchone()[0]
            check.update(differing_rows=different, passed=different == 0)
        checks.append(check)
    report = {"snapshot_sha256": SNAPSHOT_SHA256, "source_commit": "68a9a36ec3d41364490e71b056b422c99f13e0cf",
              "scope": "archived account state; not a fresh RPC collection", "checks": checks,
              "passed": all(c["passed"] for c in checks)}
    (output / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    if not report["passed"]:
        raise ValueError("Pyth replay differs from the registered historical tables")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True)
    p.add_argument("--reference", help="Directory containing the three historical Parquet tables")
    a = p.parse_args()
    print(json.dumps(replay(a.output, a.reference), indent=2))
