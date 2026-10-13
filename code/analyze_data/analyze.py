"""Describe economic composition without a population or model claim."""

import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ROOT, load_config, read_json, require, write_csv, write_json


def analyze(config, run_dir):
    cfg = load_config(config)
    run = Path(run_dir)
    ep = read_json(run / "processed_data/economic_episode.json")
    principal = int(ep["principal_returned_raw"])
    gross = int(ep["gross_payout_raw"])
    payoff = int(ep["realized_payoff_raw"])
    require(
        gross - principal == payoff,
        "Gross payout must separate returned principal and payoff",
    )
    stats = {
        "data_version": cfg["data_version"],
        "observations": 1,
        "source_transactions": 5,
        "asset": ep["asset_symbol"],
        "asset_decimals": ep["asset_decimals"],
        "principal_returned_raw": str(principal),
        "gross_payout_raw": str(gross),
        "realized_payoff_raw": str(payoff),
        "configured_reward_raw": ep["reward_configured_raw"],
        "external_truth": ep["ground_truth_status"],
        "scope": "one case descriptive reconstruction; not population inference or full economic profit",
    }
    write_json(run / "analysis/summary.json", stats)
    write_csv(
        run / "analysis/cashflow_components.csv",
        [
            {
                "component": "principal_returned",
                "amount_raw": str(principal),
                "asset": ep["asset_symbol"],
            },
            {
                "component": "token_payoff",
                "amount_raw": str(payoff),
                "asset": ep["asset_symbol"],
            },
        ],
    )
    write_csv(
        run / "analysis/field_availability.csv",
        [
            {"field": k, "is_null": v is None, "scope": "one episode"}
            for k, v in ep.items()
        ],
    )
    return stats


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--config", default=str(ROOT / "configs/project.json"))
    p.add_argument("--run-dir", required=True)
    a = p.parse_args()
    print(json.dumps(analyze(a.config, a.run_dir), indent=2))
