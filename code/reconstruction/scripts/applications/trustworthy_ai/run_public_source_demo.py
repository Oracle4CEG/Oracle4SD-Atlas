#!/usr/bin/env python3
"""Run a small real UMA AI demo from credential-free public RPC evidence.

The committed source registry contains transaction identifiers and a temporal
split, but no outcome labels.  Live mode fetches fixed Polygon/Ethereum
receipts and canonical headers.  Offline mode replays the frozen public-origin
snapshot.  Neither mode reads the project's curated ledgers.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import requests
from eth_abi import decode
from eth_utils import keccak
from sklearn.metrics import brier_score_loss, roc_auc_score


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from oracle_ledger.polygon_uma_ledger import decode_log  # noqa: E402
from oracle_ledger.uma_crosschain import oracle_request_hash  # noqa: E402
from scripts.applications.trustworthy_ai import run_challenge_benchmark as benchmark  # noqa: E402


REGISTRY = ROOT / "data/source_records/uma_public_ai_demo_cases.json"
OUT = ROOT / "data/applications/trustworthy_ai_public_source_demo"
RAW = OUT / "raw/public_rpc_records.jsonl.gz"
REQUEST_RESOLVED_TOPIC = "0x" + keccak(
    text="RequestResolved(uint32,uint256,bytes32,uint256,bytes,int256)"
).hex()
PUBLIC_RPC = {
    "polygon": ["https://polygon.drpc.org", "https://tenderly.rpc.polygon.community"],
    "ethereum": [
        "https://eth-mainnet.g.alchemy.com/public",
        "https://eth-mainnet.public.blastapi.io",
        "https://ethereum-rpc.publicnode.com",
        "https://ethereum.drpc.org",
    ],
}
CHAIN_IDS = {"polygon": 137, "ethereum": 1}
FEATURES = benchmark.MODEL_FEATURES


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def rpc_call(url: str, method: str, params: list[Any], attempts: int = 5) -> Any:
    error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = requests.post(
                url,
                json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                timeout=45,
            )
            response.raise_for_status()
            body = response.json()
            if body.get("error"):
                raise RuntimeError(str(body["error"]))
            return body.get("result")
        except Exception as exc:
            error = exc
            time.sleep(min(5.0, 0.4 * 2**attempt))
    raise RuntimeError(f"{method} failed via {urlparse(url).hostname}: {type(error).__name__}")


def select_provider(chain: str, explicit: str | None, probe_tx: str) -> tuple[str, str]:
    candidates = [explicit] if explicit else PUBLIC_RPC[chain]
    failures: list[str] = []
    for url in candidates:
        if not url:
            continue
        host = urlparse(url).hostname or "public-rpc"
        try:
            chain_id = int(rpc_call(url, "eth_chainId", []), 16)
            receipt = rpc_call(url, "eth_getTransactionReceipt", [probe_tx])
            if chain_id == CHAIN_IDS[chain] and receipt is not None:
                return url, host
            failures.append(f"{host}:chain={chain_id}:receipt={receipt is not None}")
        except Exception as exc:
            failures.append(f"{host}:{type(exc).__name__}")
    raise RuntimeError(f"no usable {chain} public RPC: {'; '.join(failures)}")


def registry_transactions(registry: dict[str, Any], chain: str) -> dict[str, int]:
    rows: dict[str, int] = {}
    for case in registry["cases"]:
        role_map = case[chain]
        for role, item in role_map.items():
            if not isinstance(item, dict) or "transaction_hash" not in item:
                continue
            tx = item["transaction_hash"].lower()
            block = int(item["block_number"])
            if tx in rows and rows[tx] != block:
                raise RuntimeError(f"conflicting block numbers for {tx}")
            rows[tx] = block
    return rows


def fetch_one(urls: list[str], chain: str, tx: str, expected_block: int) -> dict[str, Any]:
    failures: list[str] = []
    for url in urls:
        host = urlparse(url).hostname or "public-rpc"
        try:
            receipt = rpc_call(url, "eth_getTransactionReceipt", [tx])
            if receipt is None:
                failures.append(f"{host}:null_receipt")
                continue
            observed_block = int(receipt["blockNumber"], 16)
            if observed_block != expected_block:
                failures.append(f"{host}:block_mismatch")
                continue
            block = rpc_call(url, "eth_getBlockByNumber", [hex(observed_block), False])
            if block is None:
                failures.append(f"{host}:null_block")
                continue
            checks = {
                "receipt_success": int(receipt["status"], 16) == 1,
                "receipt_header_hash_equal": receipt["blockHash"].lower() == block["hash"].lower(),
                "all_logs_canonical": all(not log.get("removed", False) for log in receipt.get("logs", [])),
            }
            if not all(checks.values()):
                failures.append(f"{host}:canonical_qc")
                continue
            for log in receipt.get("logs", []):
                log.setdefault("blockTimestamp", block["timestamp"])
            return {
                "chain": chain,
                "chain_id": CHAIN_IDS[chain],
                "transaction_hash": tx,
                "expected_block_number": expected_block,
                "public_provider_host": host,
                "receipt": receipt,
                "block": block,
                "canonical_checks": checks,
            }
        except Exception as exc:
            failures.append(f"{host}:{type(exc).__name__}")
    raise RuntimeError(f"public evidence unavailable for {chain}:{tx}: {'; '.join(failures)}")


def fetch_public_records(
    registry: dict[str, Any], polygon_rpc: str | None, ethereum_rpc: str | None, workers: int
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    records: dict[str, dict[str, Any]] = {}
    providers: dict[str, str] = {}
    for chain, explicit in [("polygon", polygon_rpc), ("ethereum", ethereum_rpc)]:
        transactions = registry_transactions(registry, chain)
        url, _ = select_provider(chain, explicit, next(iter(transactions)))
        urls = [url] if explicit else [url] + [candidate for candidate in PUBLIC_RPC[chain] if candidate != url]
        used_hosts: set[str] = set()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(fetch_one, urls, chain, tx, block): tx
                for tx, block in transactions.items()
            }
            for index, future in enumerate(as_completed(futures), 1):
                row = future.result()
                records[f"{chain}:{row['transaction_hash']}"] = row
                used_hosts.add(row["public_provider_host"])
                if index % 50 == 0:
                    print(f"{chain}_public_receipts={index}/{len(transactions)}", flush=True)
        providers[chain] = ",".join(sorted(used_hosts))
    return records, providers


def write_raw(records: dict[str, dict[str, Any]], providers: dict[str, str]) -> None:
    RAW.parent.mkdir(parents=True, exist_ok=True)
    header = {
        "record_type": "metadata",
        "schema_version": "1.0.0",
        "source_mode": "credential_free_public_rpc",
        "public_provider_hosts": providers,
        "endpoint_credentials_stored": False,
        "retrieved_at_utc": datetime.now(UTC).isoformat(),
    }
    with gzip.open(RAW, "wt", encoding="utf-8", compresslevel=9) as handle:
        handle.write(json.dumps(header, separators=(",", ":")) + "\n")
        for key in sorted(records):
            handle.write(json.dumps(records[key], separators=(",", ":")) + "\n")


def load_raw(snapshot: Path = RAW) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    if not snapshot.is_file():
        raise RuntimeError(f"offline public snapshot is missing: {snapshot}")
    records: dict[str, dict[str, Any]] = {}
    providers: dict[str, str] = {}
    with gzip.open(snapshot, "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row.get("record_type") == "metadata":
                providers = row["public_provider_hosts"]
                continue
            records[f"{row['chain']}:{row['transaction_hash'].lower()}"] = row
    return records, providers


def record(records: dict[str, dict[str, Any]], chain: str, tx: str) -> dict[str, Any]:
    return records[f"{chain}:{tx.lower()}"]


def decode_polygon_receipt(item: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for log in item["receipt"].get("logs", []):
        try:
            decoded = decode_log(log)
        except KeyError:
            decoded = None
        if decoded is not None:
            rows.append(decoded)
    return rows


def one(rows: list[dict[str, Any]], event: str, case_id: str) -> dict[str, Any]:
    selected = [row for row in rows if row["event"] == event and row.get("oo_request_id") == case_id]
    if len(selected) != 1:
        raise RuntimeError(f"{case_id}: expected one {event}, found {len(selected)}")
    return selected[0]


def decode_dvm(item: dict[str, Any], expected_id: str) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    for log in item["receipt"].get("logs", []):
        if not log.get("topics") or log["topics"][0].lower() != REQUEST_RESOLVED_TOPIC:
            continue
        timestamp, ancillary, price = decode(
            ["uint256", "bytes", "int256"], bytes.fromhex(log["data"][2:])
        )
        identifier = log["topics"][3].lower()
        dvm_id = oracle_request_hash(identifier, int(timestamp), ancillary)
        if dvm_id == expected_id:
            matches.append({
                "dvm_request_id": dvm_id,
                "identifier": identifier,
                "request_time": int(timestamp),
                "ancillary_data_hex": "0x" + ancillary.hex(),
                "resolved_price_raw": str(price),
                "source_transaction": log["transactionHash"].lower(),
                "source_block": int(log["blockNumber"], 16),
                "source_log_index": int(log["logIndex"], 16),
            })
    if len(matches) != 1:
        raise RuntimeError(f"expected one DVM resolution for {expected_id}, found {len(matches)}")
    return matches[0]


def evidence_row(
    sample_id: str, kind: str, tx: str, block: int | None, timestamp: int, fields: list[str]
) -> dict[str, Any]:
    payload = {
        "sample_id": sample_id,
        "evidence_kind": kind,
        "source_transaction": tx,
        "source_block": block,
        "evidence_time_unix": timestamp,
        "fields": fields,
    }
    return {
        **payload,
        "fields": json.dumps(fields),
        "evidence_id": canonical_hash(payload),
        "availability_rule": "evidence_time_unix <= decision_time_unix",
    }


def decode_cases(
    registry: dict[str, Any], records: dict[str, dict[str, Any]]
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    episodes: list[dict[str, Any]] = []
    decoded_events: list[dict[str, Any]] = []
    chain_qc: list[dict[str, Any]] = []
    for item in records.values():
        for check, passed in item["canonical_checks"].items():
            chain_qc.append({
                "chain": item["chain"], "transaction_hash": item["transaction_hash"],
                "check": check, "passed": bool(passed),
            })
    for case in registry["cases"]:
        case_id = case["sample_id"]
        role_events: dict[str, list[dict[str, Any]]] = {}
        for role, tx_spec in case["polygon"].items():
            role_events[role] = decode_polygon_receipt(
                record(records, "polygon", tx_spec["transaction_hash"])
            )
            for row in role_events[role]:
                decoded_events.append({"sample_id_context": case_id, "transaction_role": role, **row})
        request = one(role_events["request"], "RequestPrice", case_id)
        proposal = one(role_events["proposal"], "ProposePrice", case_id)
        dispute = one(role_events["dispute"], "DisputePrice", case_id)
        settle = one(role_events["settlement"], "Settle", case_id)
        questions = [
            row for row in role_events["adapter_configuration"]
            if row["event"] == "QuestionInitialized"
            and row["source_contract"] == request["requester"]
            and row.get("ancillary_data_hex") == request["ancillary_data_hex"]
        ]
        if len(questions) != 1:
            raise RuntimeError(
                f"{case_id}: expected one exact public QuestionInitialized, found {len(questions)}"
            )
        question = questions[0]
        if question["question_id"] != case["polygon"]["adapter_configuration"]["question_id"]:
            raise RuntimeError(f"{case_id}: adapter question id does not match source registry")
        expected_dvm = case["ethereum"]["dvm_request_id"]
        bridge = [
            row for row in role_events["dispute"]
            if row["event"] == "PriceRequestAdded" and row.get("request_hash") == expected_dvm
        ]
        message = [
            row for row in role_events["dispute"]
            if row["event"] == "MessageSent" and row.get("message_hash") == expected_dvm
        ]
        if len(bridge) != 1 or len(message) != 1:
            raise RuntimeError(f"{case_id}: exact Polygon bridge evidence missing")
        dvm_spec = case["ethereum"]["dvm_resolution"]
        dvm = decode_dvm(
            record(records, "ethereum", dvm_spec["transaction_hash"]), expected_dvm
        )
        proposal_time = int(proposal["block_time"])
        request_time = int(request["block_time"])
        dispute_time = int(dispute["block_time"])
        settlement_time = int(settle["block_time"])
        bond = int(question["proposal_bond_raw"])
        final_fee = int(request["final_fee_raw"])
        escrow = bond + final_fee
        rejected = str(proposal["proposed_price_raw"]) != str(settle["resolved_price_raw"])
        gross = int(settle["gross_payout_raw"])
        payoff = gross - escrow if rejected else -escrow
        dispute_receipt = record(
            records, "polygon", case["polygon"]["dispute"]["transaction_hash"]
        )["receipt"]
        gas = int(dispute_receipt["gasUsed"], 16) * int(dispute_receipt["effectiveGasPrice"], 16)
        checks = {
            "decision_time_matches_registry": proposal_time == int(case["decision_time_unix_expected"]),
            "request_proposal_dispute_order": request_time <= proposal_time <= dispute_time,
            "dispute_before_deadline": dispute_time <= int(proposal["expiration_time"]),
            "settlement_after_dispute": settlement_time > dispute_time,
            "dvm_price_matches_settlement": dvm["resolved_price_raw"] == str(settle["resolved_price_raw"]),
            "bridge_request_id_exact": bridge[0]["request_hash"] == dvm["dvm_request_id"],
            "message_request_id_exact": message[0]["message_hash"] == dvm["dvm_request_id"],
        }
        if not all(checks.values()):
            raise RuntimeError(f"{case_id}: lifecycle/link QC failed: {checks}")
        episodes.append({
            "rank": int(case["rank"]), "split": case["split"], "sample_id": case_id,
            "requester": request["requester"], "proposer": proposal["proposer"],
            "disputer": dispute["disputer"], "request_time": int(request["request_time"]),
            "request_block_time": request_time, "proposal_time": proposal_time,
            "dispute_time": dispute_time, "settlement_time": settlement_time,
            "expiration_time": int(proposal["expiration_time"]),
            "ancillary_data_hex": request["ancillary_data_hex"],
            "reward_configured_raw": str(question["reward_raw"]),
            "bond_raw": str(bond), "final_fee_raw": str(final_fee),
            "escrow_capital_at_risk_raw": str(escrow),
            "proposed_price_raw": str(proposal["proposed_price_raw"]),
            "resolved_price_raw": str(settle["resolved_price_raw"]),
            "gross_payout_raw": str(gross), "realized_challenge_payoff_raw": str(payoff),
            "dispute_gas_native_raw": str(gas),
            "proposal_rejected_by_protocol": int(rejected),
            "ground_truth_status": "protocol_resolution_only",
            "independent_ground_truth_available": False,
            "cross_chain_link_grade": "A",
            "adapter_version": question["contract_role"],
            "request_transaction": request["source_tx"],
            "proposal_transaction": proposal["source_tx"],
            "dispute_transaction": dispute["source_tx"],
            "settlement_transaction": settle["source_tx"],
            "dvm_resolution_transaction": dvm["source_transaction"],
            "dvm_request_id": dvm["dvm_request_id"],
            "case_qc": json.dumps(checks, sort_keys=True),
        })
    return (
        pd.DataFrame(episodes).sort_values("rank").reset_index(drop=True),
        pd.DataFrame(decoded_events), pd.DataFrame(chain_qc),
        pd.DataFrame([{"check": "all_case_lifecycle_and_link_qc", "passed": True}]),
    )


def build_decisions(episodes: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    history_input = episodes.rename(columns={
        "proposal_time": "proposal_time", "settlement_time": "settlement_time",
        "dispute_transaction": "dispute_tx",
    })
    history = benchmark.actor_history(history_input)
    frame = pd.concat([episodes.reset_index(drop=True), history], axis=1)
    decisions: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    split_rows: list[dict[str, Any]] = []
    for row in frame.itertuples(index=False):
        bond = int(row.bond_raw)
        reward = int(row.reward_configured_raw)
        final_fee = int(row.final_fee_raw)
        request_ev = evidence_row(
            row.sample_id, "request", row.request_transaction, None, row.request_block_time,
            ["requester", "ancillary_data_hex", "reward_configured_raw", "final_fee_raw"],
        )
        proposal_ev = evidence_row(
            row.sample_id, "proposal", row.proposal_transaction, None, row.proposal_time,
            ["proposer", "proposed_price_raw", "expiration_time", "bond_raw"],
        )
        history_ev = evidence_row(
            row.sample_id, "lagged_actor_history", "derived:prior-settled-only", None,
            row.proposal_time, [name for name in FEATURES if "prior_" in name],
        )
        evidence.extend([request_ev, proposal_ev, history_ev])
        decisions.append({
            "sample_id": row.sample_id, "protocol": "UMA",
            "mechanism": "Polygon OOV2 -> Ethereum DVM",
            "decision_time_unix": int(row.proposal_time),
            "challenge_deadline_unix": int(row.expiration_time),
            "evidence_snapshot_time_unix": int(row.proposal_time),
            "request_transaction": row.request_transaction,
            "proposal_transaction": row.proposal_transaction,
            "dispute_transaction_outcome_only": row.dispute_transaction,
            "dvm_request_id_outcome_only": row.dvm_request_id,
            "ground_truth_status": "protocol_resolution_only",
            "independent_ground_truth_available": False,
            "observed_action": "Challenge",
            "proposal_rejected_by_protocol": int(row.proposal_rejected_by_protocol),
            "protocol_terminal_outcome": (
                "proposal_rejected" if row.proposal_rejected_by_protocol else "proposal_upheld"
            ),
            "bond_raw_outcome_only": row.bond_raw,
            "final_fee_raw_outcome_only": row.final_fee_raw,
            "realized_challenge_payoff_raw_outcome_only": row.realized_challenge_payoff_raw,
            "future_fields_excluded": json.dumps(benchmark.FORBIDDEN_MODEL_FIELDS),
            "evidence_ids": json.dumps([
                request_ev["evidence_id"], proposal_ev["evidence_id"], history_ev["evidence_id"]
            ]),
            "log_bond_raw": float(np.log1p(bond)),
            "log_final_fee_raw": float(np.log1p(final_fee)),
            "log_reward_plus1_raw": float(np.log1p(reward)),
            "reward_to_bond_ratio": reward / bond if bond else 0.0,
            "liveness_hours": (int(row.expiration_time) - int(row.proposal_time)) / 3600,
            "proposal_latency_hours": (
                int(row.proposal_time) - int(row.request_block_time)
            ) / 3600,
            "ancillary_bytes": len(str(row.ancillary_data_hex).removeprefix("0x")) // 2,
            "requester_is_polymarket_adapter": 1,
            "proposer_prior_completed": int(row.proposer_prior_completed),
            "proposer_prior_dispute_rate": float(row.proposer_prior_dispute_rate),
            "proposer_prior_rejection_rate": float(row.proposer_prior_rejection_rate),
            "requester_prior_completed": int(row.requester_prior_completed),
            "requester_prior_dispute_rate": float(row.requester_prior_dispute_rate),
            "requester_prior_rejection_rate": float(row.requester_prior_rejection_rate),
            "proposed_price_class": benchmark.price_class(row.proposed_price_raw),
            "adapter_version": row.adapter_version,
        })
        split_rows.append({
            "sample_id": row.sample_id, "decision_time_unix": int(row.proposal_time),
            "split": row.split,
        })
    return pd.DataFrame(decisions), pd.DataFrame(evidence), pd.DataFrame(split_rows)


def ece(y: np.ndarray, probability: np.ndarray, bins: int = 5) -> float:
    edges = np.linspace(0, 1, bins + 1)
    result = 0.0
    for low, high in zip(edges[:-1], edges[1:]):
        mask = (probability >= low) & (probability < high if high < 1 else probability <= high)
        if mask.any():
            result += mask.mean() * abs(float(y[mask].mean()) - float(probability[mask].mean()))
    return float(result)


def validate(
    registry: dict[str, Any], records: dict[str, dict[str, Any]], episodes: pd.DataFrame,
    decisions: pd.DataFrame, evidence: pd.DataFrame, splits: pd.DataFrame,
    predictions: pd.DataFrame, metrics: pd.DataFrame, chain_qc: pd.DataFrame,
) -> pd.DataFrame:
    cited = {item for raw in predictions.evidence_ids for item in json.loads(raw)}
    evidence_ids = set(evidence.evidence_id)
    joined = evidence.merge(decisions[["sample_id", "decision_time_unix"]], on="sample_id")
    split_ranges = splits.groupby("split").decision_time_unix.agg(["min", "max"])
    checks = {
        "registry_contains_no_labels": registry["label_in_registry"] is False,
        "all_64_cases_reconstructed": len(episodes) == len(decisions) == 64,
        "all_registered_transactions_frozen": len(records) == sum(
            len(registry_transactions(registry, chain)) for chain in CHAIN_IDS
        ),
        "all_receipt_header_checks_pass": chain_qc.passed.all(),
        "all_cross_chain_links_grade_a": episodes.cross_chain_link_grade.eq("A").all(),
        "both_protocol_outcomes_present": decisions.proposal_rejected_by_protocol.nunique() == 2,
        "each_temporal_split_has_both_classes": all(
            decisions.merge(splits).query("split == @split_name").proposal_rejected_by_protocol.nunique() == 2
            for split_name in ["train", "validation", "test"]
        ),
        "temporal_split_strict": (
            split_ranges.loc["train", "max"] < split_ranges.loc["validation", "min"]
            and split_ranges.loc["validation", "max"] < split_ranges.loc["test", "min"]
        ),
        "all_evidence_available_at_decision": (joined.evidence_time_unix <= joined.decision_time_unix).all(),
        "all_prediction_citations_resolve": cited <= evidence_ids,
        "forbidden_fields_not_model_features": not set(benchmark.FORBIDDEN_MODEL_FIELDS) & set(FEATURES),
        "required_models_evaluated": {
            "always_accept", "always_challenge", "always_abstain", "always_investigate",
            "calibrated_logit_ensemble",
        } <= set(metrics.model),
        "outputs_remain_protocol_only": predictions.ground_truth_status.eq("protocol_resolution_only").all(),
    }
    result = pd.DataFrame([{"check": key, "passed": bool(value)} for key, value in checks.items()])
    if not result.passed.all():
        raise RuntimeError(f"public-source AI demo QC failed: {result[~result.passed].check.tolist()}")
    return result


def write_outputs(
    registry: dict[str, Any], providers: dict[str, str], episodes: pd.DataFrame,
    events: pd.DataFrame, chain_qc: pd.DataFrame, decisions: pd.DataFrame,
    evidence: pd.DataFrame, splits: pd.DataFrame, predictions: pd.DataFrame,
    metrics: pd.DataFrame, risk: pd.DataFrame, coefficients: pd.DataFrame,
    reliability: pd.DataFrame, robustness: pd.DataFrame, qc: pd.DataFrame,
) -> None:
    for folder in ["source", "validated", "processed", "economic", "statistics"]:
        (OUT / folder).mkdir(parents=True, exist_ok=True)
    (OUT / "source/source_registry.json").write_text(
        json.dumps(registry, indent=2) + "\n", encoding="utf-8"
    )
    events.to_parquet(OUT / "validated/decoded_protocol_events.parquet", index=False)
    chain_qc.to_parquet(OUT / "validated/canonical_receipt_qc.parquet", index=False)
    qc.to_parquet(OUT / "validated/pipeline_qc.parquet", index=False)
    episodes.to_parquet(OUT / "processed/economic_episodes.parquet", index=False)
    decisions.to_parquet(OUT / "processed/decision_samples.parquet", index=False)
    evidence.to_parquet(OUT / "processed/evidence_provenance.parquet", index=False)
    splits.to_parquet(OUT / "processed/temporal_splits.parquet", index=False)
    episodes[[
        "sample_id", "bond_raw", "final_fee_raw", "escrow_capital_at_risk_raw",
        "reward_configured_raw", "gross_payout_raw", "realized_challenge_payoff_raw",
        "dispute_gas_native_raw", "ground_truth_status",
    ]].to_parquet(OUT / "economic/challenge_economics.parquet", index=False)
    predictions.to_parquet(OUT / "statistics/predictions.parquet", index=False)
    metrics.to_parquet(OUT / "statistics/metrics.parquet", index=False)
    metrics.to_csv(OUT / "statistics/metrics.csv", index=False)
    risk.to_parquet(OUT / "statistics/risk_coverage.parquet", index=False)
    coefficients.to_csv(OUT / "statistics/model_coefficients.csv", index=False)
    reliability.to_json(OUT / "statistics/reliability.json", orient="records", indent=2)
    robustness.to_parquet(OUT / "statistics/robustness.parquet", index=False)
    model = metrics[metrics.model.eq("calibrated_logit_ensemble")].iloc[0]
    test = decisions.merge(splits).query("split == 'test'")
    probability = predictions[predictions.model.eq("calibrated_logit_ensemble")]
    y = probability.protocol_outcome.to_numpy()
    p = probability.probability_proposal_rejected.to_numpy()
    summary = {
        "registry_id": registry["registry_id"], "cases": len(decisions),
        "split_counts": splits.split.value_counts().to_dict(),
        "test_protocol_rejection_rate": float(test.proposal_rejected_by_protocol.mean()),
        "test_auc": float(roc_auc_score(y, p)),
        "test_brier": float(brier_score_loss(y, p)),
        "test_ece_5": ece(y, p),
        "automated_coverage": float(model.automated_coverage),
        "public_provider_hosts": providers,
        "ground_truth_status": "protocol_resolution_only",
        "all_required_assertions_pass": bool(qc.passed.all()),
    }
    (OUT / "statistics/summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    report = f"""# Public-source UMA AI demonstration

This demonstration starts from a label-free registry of 64 fixed public transactions,
downloads or replays canonical Polygon and Ethereum receipts, decodes the UMA lifecycle,
derives decision-time features and economic outcomes, and runs the registered logistic
regression plus four simple baselines. It never reads a curated ledger.

- Chronological split: 44 train / 10 validation / 10 test.
- Test AUC: {summary['test_auc']:.3f}; Brier: {summary['test_brier']:.3f}; ECE-5: {summary['test_ece_5']:.3f}.
- Automated Accept/Challenge coverage: {summary['automated_coverage']:.3f}.
- Outcome: later UMA protocol resolution only, not independent factual truth.
- Configured rewards, capital at risk, gross payout and realized challenge payoff remain distinct.

Live public reproduction:

```bash
python scripts/applications/trustworthy_ai/run_public_source_demo.py
```

Deterministic replay after freezing the public receipts:

```bash
python scripts/applications/trustworthy_ai/run_public_source_demo.py --offline
```
"""
    (OUT / "report.md").write_text(report, encoding="utf-8")
    files = sorted(
        path for path in OUT.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    )
    manifest = {
        "dataset": "UMA public-source minimal Trustworthy-AI demonstration",
        "version": "1.0.0", "generated_at_utc": datetime.now(UTC).isoformat(),
        "fixed_cutoff": registry["fixed_cutoff"],
        "derivation_input_policy": "label-free source registry plus credential-free public RPC only",
        "curated_ledger_inputs_used": False,
        "public_provider_hosts": providers,
        "endpoint_credentials_stored": False,
        "all_required_assertions_pass": bool(qc.passed.all()),
        "rows": {
            "episodes": len(episodes), "decisions": len(decisions),
            "evidence": len(evidence), "predictions": len(predictions),
        },
        "files": [{
            "path": str(path.relative_to(OUT)), "bytes": path.stat().st_size,
            "sha256": sha256(path),
        } for path in files],
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    global OUT, RAW
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument(
        "--snapshot", type=Path,
        help="frozen public_rpc_records.jsonl.gz to replay; copied into the output package",
    )
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--polygon-rpc", default=os.environ.get("PUBLIC_POLYGON_RPC_URL"))
    parser.add_argument("--ethereum-rpc", default=os.environ.get("PUBLIC_ETHEREUM_RPC_URL"))
    args = parser.parse_args()
    OUT = args.output.resolve()
    RAW = OUT / "raw/public_rpc_records.jsonl.gz"
    registry = json.loads(args.registry.resolve().read_text(encoding="utf-8"))
    if registry["label_in_registry"] is not False or registry["observation_count"] != 64:
        raise RuntimeError("public source registry scope changed")
    if args.offline:
        source_snapshot = args.snapshot.resolve() if args.snapshot else RAW
        records, providers = load_raw(source_snapshot)
        if source_snapshot != RAW:
            RAW.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_snapshot, RAW)
    else:
        records, providers = fetch_public_records(
            registry, args.polygon_rpc, args.ethereum_rpc, args.workers
        )
        write_raw(records, providers)
    episodes, events, chain_qc, _ = decode_cases(registry, records)
    decisions, evidence, splits = build_decisions(episodes)
    predictions, metrics, risk, coefficients, reliability = benchmark.evaluate_predictions(
        decisions, splits
    )
    robustness = benchmark.robustness_checks(predictions)
    qc = validate(
        registry, records, episodes, decisions, evidence, splits,
        predictions, metrics, chain_qc,
    )
    write_outputs(
        registry, providers, episodes, events, chain_qc, decisions, evidence, splits,
        predictions, metrics, risk, coefficients, reliability, robustness, qc,
    )
    print(json.dumps({
        "output": str(OUT), "cases": len(decisions),
        "public_providers": providers, "test_rows": int(splits.split.eq("test").sum()),
        "all_required_assertions_pass": True,
    }, indent=2))


if __name__ == "__main__":
    main()
