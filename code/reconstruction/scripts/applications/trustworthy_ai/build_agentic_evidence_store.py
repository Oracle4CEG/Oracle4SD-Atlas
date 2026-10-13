#!/usr/bin/env python3
"""Freeze the label-free evidence store used by B1 and A1."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from oracle_ledger.oracle_auditor_store import canonical_json, sha256_bytes, sha256_json  # noqa: E402


APP_ROOT = ROOT / "data/applications"
CHALLENGE = APP_ROOT / "trustworthy_ai_challenge"
SEMANTIC = APP_ROOT / "trustworthy_ai_semantic" / "semantic_source.parquet"
MARKET = APP_ROOT / "trustworthy_ai_market_evidence" / "market_feature_snapshot.parquet"
PUBLIC64 = APP_ROOT / "trustworthy_ai_public_source_demo/processed/decision_samples.parquet"
CURATED = Path(os.environ.get(
    "ORACLE_NATURE_CURATED_ROOT", "/mnt/sda/hy/oracle-nature-data/curated"
)) / "parquet"
DEFAULT_OUT = APP_ROOT / "agentic_oracle_auditor"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def native(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def decode_ancillary(value: Any) -> str:
    text = str(value or "")
    if text.startswith("0x"):
        try:
            return bytes.fromhex(text[2:]).decode("utf-8", errors="replace")
        except ValueError:
            return ""
    return text


def evidence_record(
    case_id: str,
    kind: str,
    evidence_time_unix: int,
    source: dict[str, Any],
    content: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    identity = {
        "case_id": case_id,
        "kind": kind,
        "evidence_time_unix": int(evidence_time_unix),
        "source": source,
        "content_sha256": sha256_json(content),
    }
    evidence_id = sha256_json(identity)
    return evidence_id, {
        **identity,
        "content": content,
    }


def choose_robustness_panel(samples: pd.DataFrame, splits: pd.DataFrame) -> list[str]:
    test = samples.merge(splits, on=["sample_id", "decision_time_unix"], validate="one_to_one")
    test = test[test["split"].eq("test")].copy()
    test["panel_order"] = test["sample_id"].map(
        lambda case_id: hashlib.sha256(f"oracle-auditor-robustness-v1:{case_id}".encode()).hexdigest()
    )
    selected = []
    for label in (1, 0):
        group = test[test["proposal_rejected_by_protocol"].eq(label)].sort_values("panel_order")
        if len(group) < 20:
            raise RuntimeError(f"not enough test cases for label {label}")
        selected.extend(group.head(20)["sample_id"].tolist())
    return sorted(selected)


def build_store() -> tuple[dict[str, Any], dict[str, Any]]:
    input_paths = {
        "decision_samples": CHALLENGE / "decision_samples.parquet",
        "evidence_provenance": CHALLENGE / "evidence_provenance.parquet",
        "splits": CHALLENGE / "splits.parquet",
        "semantic_source": SEMANTIC,
        "market_feature_snapshot": MARKET,
        "public_64_decision_samples": PUBLIC64,
        "polygon_uma_request_rounds": CURATED / "polygon_uma_request_rounds.parquet",
    }
    missing = [str(path) for path in input_paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("missing evidence inputs: " + ", ".join(missing))

    samples = pd.read_parquet(input_paths["decision_samples"])
    splits = pd.read_parquet(input_paths["splits"])
    semantic = pd.read_parquet(input_paths["semantic_source"])
    market = pd.read_parquet(input_paths["market_feature_snapshot"])
    public_ids = set(pd.read_parquet(input_paths["public_64_decision_samples"])["sample_id"])
    rounds = pd.read_parquet(input_paths["polygon_uma_request_rounds"])

    if len(samples) != 810:
        raise RuntimeError(f"strict cohort changed: expected 810, got {len(samples)}")
    counts = splits["split"].value_counts().to_dict()
    if counts != {"train": 489, "validation": 161, "test": 160}:
        raise RuntimeError(f"chronological split changed: {counts}")

    allowed_round_columns = [
        "oo_request_id", "source_tx", "source_block", "block_time", "requester",
        "identifier", "request_time", "ancillary_data_hex", "currency",
        "question_reward_raw", "final_fee_raw", "proposer", "proposed_price_raw",
        "expiration_time", "proposal_tx", "proposal_block", "adapter_version",
        "effective_bond_raw", "requester_is_polymarket_adapter", "sample_tier",
    ]
    rounds = rounds.loc[
        rounds["sample_tier"].eq("primary") & rounds["oo_request_id"].isin(samples["sample_id"]),
        allowed_round_columns,
    ].drop_duplicates("oo_request_id", keep="last")
    if len(rounds) != 810:
        raise RuntimeError(f"proposal source rows changed: expected 810, got {len(rounds)}")

    merged = (
        samples.merge(
            rounds,
            left_on="sample_id",
            right_on="oo_request_id",
            validate="one_to_one",
            suffixes=("_sample", ""),
        )
        .merge(semantic[["sample_id", "ancillary_data_hex"]], on="sample_id", how="left", suffixes=("", "_semantic"), validate="one_to_one")
        .merge(
            market.drop(columns=["split"], errors="ignore"),
            on=["sample_id", "decision_time_unix"],
            how="left",
            suffixes=("", "_market"),
            validate="one_to_one",
        )
        .merge(splits, on=["sample_id", "decision_time_unix"], validate="one_to_one")
        .sort_values(["decision_time_unix", "sample_id"])
    )

    cases: dict[str, Any] = {}
    evidence: dict[str, Any] = {}
    actor_history: list[dict[str, Any]] = []
    prior_cases: list[dict[str, Any]] = []

    for row in merged.itertuples(index=False):
        case_id = str(row.sample_id)
        cutoff = int(row.decision_time_unix)
        ancillary_hex = str(row.ancillary_data_hex or "")
        ancillary_text = decode_ancillary(ancillary_hex)
        requester = str(row.requester).lower()
        proposer = str(row.proposer).lower()

        request_content = {
            "request_time_unix": int(row.request_time),
            "requester": requester,
            "identifier": str(row.identifier),
            "ancillary_data_hex": ancillary_hex,
            "ancillary_text": ancillary_text,
            "currency": str(row.currency).lower(),
            "reward_raw": str(row.question_reward_raw),
            "final_fee_raw": str(row.final_fee_raw),
            "adapter_version": str(row.adapter_version),
            "requester_is_polymarket_adapter": bool(row.requester_is_polymarket_adapter),
        }
        request_id, request_record = evidence_record(
            case_id,
            "request",
            int(row.block_time),
            {"type": "polygon_transaction", "transaction": str(row.source_tx), "block": int(row.source_block)},
            request_content,
        )
        evidence[request_id] = request_record

        proposal_content = {
            "proposer": proposer,
            "proposed_price_raw": str(row.proposed_price_raw),
            "expiration_time_unix": int(row.expiration_time),
            "effective_bond_raw": str(row.effective_bond_raw),
            "liveness_hours": native(row.liveness_hours),
            "proposal_latency_hours": native(row.proposal_latency_hours),
            "proposed_price_class": str(row.proposed_price_class),
        }
        proposal_id, proposal_record = evidence_record(
            case_id,
            "proposal",
            cutoff,
            {"type": "polygon_transaction", "transaction": str(row.proposal_tx), "block": int(row.proposal_block)},
            proposal_content,
        )
        evidence[proposal_id] = proposal_record

        actor_ids: list[str] = []
        for role, address in (("proposer", proposer), ("requester", requester)):
            history_content = {
                "address": address,
                "role": role,
                "completed": int(getattr(row, f"{role}_prior_completed")),
                "dispute_rate": float(getattr(row, f"{role}_prior_dispute_rate")),
                "rejection_rate": float(getattr(row, f"{role}_prior_rejection_rate")),
                "construction": "episodes settled no later than the current proposal cutoff; no individual post-proposal record exposed",
            }
            history_id, history_record = evidence_record(
                case_id,
                f"actor_history_{role}",
                cutoff,
                {"type": "derived", "rule": "prior-settled-only-v1"},
                history_content,
            )
            evidence[history_id] = history_record
            actor_ids.append(history_id)
            actor_history.append({
                **history_content,
                "cutoff_unix": cutoff,
                "evidence_id": history_id,
            })

        optional_ids: list[str] = []
        coverage = native(getattr(row, "coverage_status", None))
        if coverage == "complete":
            market_content = {
                key: native(getattr(row, key))
                for key in [
                    "coverage_status", "aligned_probability", "opposing_probability", "price_sum",
                    "market_confidence", "aligned_price_age_seconds", "aligned_momentum_1h",
                    "aligned_momentum_6h", "aligned_momentum_24h", "aligned_volatility_24h",
                    "aligned_range_24h", "total_points_1h", "total_points_6h",
                    "total_points_24h", "total_points_168h",
                ]
            }
            market_id, market_record = evidence_record(
                case_id,
                "proposal_time_market_snapshot",
                cutoff,
                {"type": "checksum_pinned_local_snapshot", "upstream_file": "market_feature_snapshot.parquet"},
                market_content,
            )
            evidence[market_id] = market_record
            optional_ids.append(market_id)

        cases[case_id] = {
            "cutoff_unix": cutoff,
            "split": str(row.split),
            "public_grade_a_64": case_id in public_ids,
            "proposal": {
                "requester": requester,
                "proposer": proposer,
                "request_transaction": str(row.source_tx),
                "proposal_transaction": str(row.proposal_tx),
                "challenge_deadline_unix": int(row.expiration_time),
                "proposed_price_class": str(row.proposed_price_class),
                "adapter_version": str(row.adapter_version),
            },
            "required_evidence_ids": [request_id, proposal_id, *actor_ids],
            "optional_evidence_ids": optional_ids,
        }
        prior_cases.append({
            "case_id": case_id,
            "decision_time_unix": cutoff,
            "search_text": ancillary_text,
            "proposal_summary": {
                "ancillary_text": ancillary_text[:2000],
                "proposed_price_class": str(row.proposed_price_class),
                "adapter_version": str(row.adapter_version),
            },
            "evidence_ids": [request_id, proposal_id],
        })

    panel_ids = choose_robustness_panel(samples, splits)
    store = {
        "schema_version": "oracle-auditor-evidence-v1",
        "label_boundary": "No dispute, vote, resolution, settlement, payout, protocol label, or other target-case post-proposal field is stored.",
        "cohort": {
            "strict_cases": 810,
            "split_counts": {"train": 489, "validation": 161, "test": 160},
            "public_grade_a_cases": len(public_ids),
            "public_grade_a_usage": "end-to-end reproducibility only",
            "robustness_panel_case_ids": panel_ids,
        },
        "cases": cases,
        "evidence": evidence,
        "actor_history": actor_history,
        "prior_cases": prior_cases,
    }
    manifest = {
        "schema_version": "oracle-auditor-evidence-manifest-v1",
        "input_checksums": {
            name: {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": file_sha256(path)}
            for name, path in sorted(input_paths.items())
        },
        "counts": {
            "cases": len(cases),
            "evidence": len(evidence),
            "actor_history": len(actor_history),
            "prior_cases": len(prior_cases),
            "robustness_panel": len(panel_ids),
        },
        "forbidden_fields": [
            "dispute_tx", "dispute_time", "resolved_price_raw", "gross_payout_raw",
            "settlement_tx", "settlement_time", "terminal_outcome", "dvm_request_id",
            "dvm_resolved_price_raw", "proposal_rejected_by_protocol",
        ],
    }
    return store, manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    store, manifest = build_store()
    store_path = out / "evidence_store.json"
    payload = (canonical_json(store) + "\n").encode("utf-8")
    store_path.write_bytes(payload)
    manifest["evidence_store"] = {
        "path": str(store_path),
        "bytes": len(payload),
        "sha256": sha256_bytes(payload),
    }
    manifest_path = out / "evidence_store_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "evidence_store.sha256").write_text(
        f"{manifest['evidence_store']['sha256']}  evidence_store.json\n", encoding="utf-8"
    )
    print(json.dumps({"store": str(store_path), **manifest["evidence_store"], **manifest["counts"]}, sort_keys=True))


if __name__ == "__main__":
    main()
