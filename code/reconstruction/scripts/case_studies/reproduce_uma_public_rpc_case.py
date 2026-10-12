#!/usr/bin/env python3
"""Reproduce one real UMA episode from public RPC/source records only.

The derivation never reads the project's curated ledgers.  Live mode retrieves
five fixed transaction receipts, their canonical block headers, deployed code,
and pinned contract sources.  ``--snapshot-dir`` replays the same transformation
from redacted raw RPC snapshots for offline tests and release rebuilding.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from datetime import UTC, datetime
from decimal import Decimal, getcontext
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import matplotlib.pyplot as plt
import pandas as pd
import requests
from eth_abi import decode
from eth_utils import keccak
from jsonschema import Draft202012Validator


getcontext().prec = 60
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from oracle_ledger.polygon_uma_ledger import decode_log  # noqa: E402
from oracle_ledger.uma_crosschain import (  # noqa: E402
    oracle_request_hash,
    stamp_legacy_child_ancillary,
    stamp_oov2_ancillary,
)


SPEC_PATH = ROOT / "data/case_studies/uma_public_rpc_case_spec.json"
DEFAULT_OUTPUT = ROOT / "data/case_studies/uma_public_rpc_reproduction"
SCHEMA_PATH = ROOT / "schemas/cross_chain_economic_observation.schema.json"
ABC_DICTIONARY = ROOT / "data/dictionaries/abc_economic_measure_dictionary.json"
TRANSFER_TOPIC = "0x" + keccak(text="Transfer(address,address,uint256)").hex()
REQUEST_RESOLVED_TOPIC = "0x" + keccak(
    text="RequestResolved(uint32,uint256,bytes32,uint256,bytes,int256)"
).hex()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def address_from_topic(topic: str) -> str:
    return "0x" + topic[-40:].lower()


def receipt_cost(receipt: dict[str, Any]) -> int:
    return int(receipt["gasUsed"], 16) * int(receipt["effectiveGasPrice"], 16)


class Rpc:
    def __init__(self, url: str, timeout: int = 30) -> None:
        self.url = url
        self.timeout = timeout
        self.session = requests.Session()
        self.request_id = 0

    @property
    def public_provider(self) -> str:
        parsed = urlparse(self.url)
        return parsed.hostname or "configured-public-rpc"

    def call(self, method: str, params: list[Any]) -> Any:
        last_error: Exception | None = None
        for attempt in range(4):
            self.request_id += 1
            try:
                response = self.session.post(
                    self.url,
                    json={"jsonrpc": "2.0", "id": self.request_id, "method": method, "params": params},
                    timeout=self.timeout,
                )
                response.raise_for_status()
                payload = response.json()
                if payload.get("error"):
                    raise RuntimeError(f"{method}: {payload['error']}")
                return payload.get("result")
            except Exception as exc:  # bounded public-provider retry
                last_error = exc
                time.sleep(0.5 * (attempt + 1))
        raise RuntimeError(f"public RPC call {method} failed via {self.public_provider}: {last_error}")


def select_rpc(explicit: str | None, candidates: list[str], chain_id: int, probe_tx: str) -> Rpc:
    urls = [explicit] if explicit else candidates
    errors: list[str] = []
    for url in urls:
        if not url:
            continue
        client = Rpc(url)
        try:
            observed = int(client.call("eth_chainId", []), 16)
            receipt = client.call("eth_getTransactionReceipt", [probe_tx])
            if observed == chain_id and receipt is not None:
                return client
            errors.append(f"{client.public_provider}: chain={observed}, receipt={receipt is not None}")
        except Exception as exc:
            errors.append(f"{client.public_provider}: {type(exc).__name__}")
    raise RuntimeError("no usable public RPC candidate: " + "; ".join(errors))


def contract_code_evidence(
    client: Rpc, address: str, preferred_block: int, expected_hash: str
) -> dict[str, Any]:
    block_tag = hex(preferred_block)
    historical_error = None
    try:
        code = client.call("eth_getCode", [address, block_tag])
    except Exception as exc:
        historical_error = type(exc).__name__
        code = client.call("eth_getCode", [address, "latest"])
        block_tag = "latest"
    if not code or code == "0x":
        raise RuntimeError(f"no deployed code for {address}")
    observed_hash = "0x" + keccak(bytes.fromhex(code[2:])).hex()
    return {
        "address": address.lower(),
        "queried_block": block_tag,
        "runtime_bytes": (len(code) - 2) // 2,
        "runtime_code_hash": observed_hash,
        "expected_runtime_code_hash": expected_hash,
        "hash_matches": observed_hash == expected_hash,
        "historical_query_fallback": historical_error,
    }


def fetch_live_chain(
    name: str, chain_spec: dict[str, Any], contract_specs: list[dict[str, Any]], explicit_url: str | None
) -> dict[str, Any]:
    transactions = chain_spec["transactions"]
    probe = next(iter(transactions.values()))["hash"]
    client = select_rpc(
        explicit_url,
        chain_spec["default_public_rpc_candidates"],
        int(chain_spec["chain_id"]),
        probe,
    )
    receipts: dict[str, Any] = {}
    blocks: dict[str, Any] = {}
    tx_objects: dict[str, Any] = {}
    for tx_spec in transactions.values():
        tx_hash = tx_spec["hash"].lower()
        receipt = client.call("eth_getTransactionReceipt", [tx_hash])
        tx_object = client.call("eth_getTransactionByHash", [tx_hash])
        if receipt is None or tx_object is None:
            raise RuntimeError(f"{name} returned null transaction evidence for {tx_hash}")
        block_number = int(receipt["blockNumber"], 16)
        block = client.call("eth_getBlockByNumber", [hex(block_number), False])
        if block is None:
            raise RuntimeError(f"{name} returned null block evidence for {tx_hash}")
        for log in receipt.get("logs", []):
            log.setdefault("blockTimestamp", block["timestamp"])
        receipts[tx_hash] = receipt
        tx_objects[tx_hash] = tx_object
        blocks[str(block_number)] = block
    head = int(client.call("eth_blockNumber", []), 16)
    code = []
    earliest = min(item["block_number"] for item in transactions.values())
    for item in contract_specs:
        code.append(contract_code_evidence(client, item["address"], earliest, item["runtime_code_hash"]))
    return {
        "chain": name,
        "chain_id": int(chain_spec["chain_id"]),
        "retrieved_at": datetime.now(UTC).isoformat(),
        "source_mode": "public_rpc",
        "public_provider": client.public_provider,
        "endpoint_credentials_stored": False,
        "head_block_at_retrieval": head,
        "receipts": receipts,
        "transactions": tx_objects,
        "blocks": blocks,
        "contract_code_evidence": code,
    }


def load_fixture_chain(name: str, snapshot_dir: Path) -> dict[str, Any]:
    source = snapshot_dir / f"{name}_rpc_snapshot.json"
    if not source.is_file():
        raise FileNotFoundError(source)
    snapshot = json.loads(source.read_text(encoding="utf-8"))
    snapshot.setdefault("snapshot_origin_mode", snapshot.get("source_mode", "unspecified_frozen_snapshot"))
    snapshot["source_mode"] = "frozen_rpc_snapshot_replay"
    snapshot["endpoint_credentials_stored"] = False
    snapshot.setdefault("public_provider", "redacted-frozen-snapshot")
    snapshot.setdefault("transactions", {})
    snapshot.setdefault("contract_code_evidence", [])
    return snapshot


def validate_chain_snapshot(snapshot: dict[str, Any], chain_spec: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    if int(snapshot["chain_id"]) != int(chain_spec["chain_id"]):
        raise RuntimeError(f"wrong chain id for {snapshot['chain']}")
    for role, expected in chain_spec["transactions"].items():
        tx_hash = expected["hash"].lower()
        receipt = snapshot["receipts"].get(tx_hash)
        if receipt is None:
            raise RuntimeError(f"missing {role} receipt {tx_hash}")
        block = snapshot["blocks"].get(str(expected["block_number"]))
        checks = {
            "successful": int(receipt["status"], 16) == 1,
            "block_number": int(receipt["blockNumber"], 16) == int(expected["block_number"]),
            "receipt_block_hash": receipt["blockHash"].lower() == expected["block_hash"].lower(),
            "header_block_hash": block["hash"].lower() == expected["block_hash"].lower(),
            "block_timestamp": int(block["timestamp"], 16) == int(expected["block_timestamp"]),
            "not_removed": all(not log.get("removed", False) for log in receipt.get("logs", [])),
        }
        for check, passed in checks.items():
            rows.append({"chain": snapshot["chain"], "transaction_role": role, "check": check, "passed": passed})
        if not all(checks.values()):
            raise RuntimeError(f"canonical receipt validation failed for {role}: {checks}")
    return rows


def fetch_source_records(
    spec: dict[str, Any], output: Path, offline: bool, source_cache: Path | None
) -> list[dict[str, Any]]:
    folder = output / "source"
    folder.mkdir(parents=True, exist_ok=True)
    rows = []
    for item in spec["source_records"]:
        destination = folder / item["output_name"]
        if offline:
            expected = item.get("sha256") or item.get("source_code_sha256")
            cached = source_cache / item["output_name"] if source_cache else None
            if not destination.exists() and cached is not None and cached.is_file():
                shutil.copyfile(cached, destination)
                abi = cached.with_name("VotingV2.abi.json")
                if abi.is_file():
                    shutil.copyfile(abi, folder / abi.name)
            observed = sha256_file(destination) if destination.exists() else None
            rows.append({
                "id": item["id"], "url": item["url"], "local_path": str(destination.relative_to(output)),
                "expected_sha256": expected,
                "observed_sha256": observed,
                "status": "cached_verified" if observed == expected else "not_refetched_offline",
            })
            continue
        response = requests.get(item["url"], timeout=45)
        response.raise_for_status()
        if item["id"] == "uma_voting_v2_deployed_source":
            payload = response.json()
            content = payload["source_code"].encode()
            (folder / "VotingV2.abi.json").write_text(
                json.dumps(payload["abi"], indent=2) + "\n", encoding="utf-8"
            )
            metadata = {
                "contract_name": payload.get("name"), "compiler_version": payload.get("compiler_version"),
                "verified_at": payload.get("verified_at"), "is_fully_verified": payload.get("is_fully_verified"),
            }
        else:
            content = response.content
            metadata = {}
        destination.write_bytes(content)
        expected = item.get("sha256") or item.get("source_code_sha256")
        observed = sha256_bytes(content)
        if observed != expected:
            raise RuntimeError(f"source checksum mismatch for {item['id']}: {observed}")
        rows.append({
            "id": item["id"], "url": item["url"], "local_path": str(destination.relative_to(output)),
            "expected_sha256": expected, "observed_sha256": observed, "bytes": len(content),
            "status": "downloaded_verified", **metadata,
        })
    return rows


def verify_contract_semantics(output: Path) -> list[dict[str, Any]]:
    """Verify the exact source statements used to classify economic flows."""
    rules = [
        (
            "UMA_OOV2_CONFIGURED_REWARD_ESCROW_V1", "OptimisticOracleV2.sol",
            "currency.safeTransferFrom(msg.sender, address(this), reward)",
            "A configured request reward is escrowed when RequestPrice executes.",
        ),
        (
            "UMA_OOV2_REWARD_REFUND_ON_DISPUTE_V1", "OptimisticOracleV2.sol",
            "request.reward = 0", "A refunded configured reward is removed before settlement payout.",
        ),
        (
            "UMA_OOV2_PROTOCOL_FEE_PAYMENT_V1", "OptimisticOracleV2.sol",
            "_getStore().payOracleFeesErc20", "Final fee plus burned bond is paid to the protocol Store.",
        ),
        (
            "UMA_OOV2_RESOLVED_PAYOUT_V1", "OptimisticOracleV2.sol",
            "payout = bond.add(unburnedBond).add(request.finalFee).add(request.reward)",
            "The winner's gross settlement payout combines returned capital and economic gain.",
        ),
        (
            "UMA_DVM_REQUEST_RESOLVED_V1", "VotingV2.sol", "emit RequestResolved(",
            "VotingV2 emits the terminal protocol resolution linked to Polygon settlement.",
        ),
        (
            "UMA_DVM_SLASH_ACCRUAL_DISTINCT_FROM_APPLICATION_V1", "VotingV2.sol",
            "emit VoterSlashed(voter, requestIndex, int128(slash))",
            "Request-level slash accrual is a distinct event from later stake application.",
        ),
        (
            "UMA_DVM_SLASH_APPLICATION_DISTINCT_FROM_ACCRUAL_V1", "VotingV2.sol",
            "emit VoterSlashApplied(voter, voterStake.unappliedSlash, voterStake.stake)",
            "Applied stake mutation is not a second economic slash to add to VoterSlashed.",
        ),
    ]
    rows: list[dict[str, Any]] = []
    for rule_id, filename, needle, interpretation in rules:
        path = output / "source" / filename
        if not path.is_file():
            raise RuntimeError(f"required pinned contract source is unavailable: {path}")
        lines = path.read_text(encoding="utf-8").splitlines()
        matches = [index for index, line in enumerate(lines, 1) if needle in line]
        if len(matches) != 1:
            raise RuntimeError(f"source semantic rule {rule_id} expected one match, got {matches}")
        rows.append({
            "rule_id": rule_id, "source_file": filename, "source_sha256": sha256_file(path),
            "line_number": matches[0], "matched_statement": needle,
            "economic_interpretation": interpretation, "validation_status": "passed",
        })
    return rows


def polygon_events(snapshot: dict[str, Any], transaction_specs: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for tx_spec in transaction_specs.values():
        receipt = snapshot["receipts"][tx_spec["hash"].lower()]
        block_time = snapshot["blocks"][str(tx_spec["block_number"])]["timestamp"]
        for raw_log in receipt["logs"]:
            raw_log.setdefault("blockTimestamp", block_time)
            try:
                row = decode_log(raw_log)
            except KeyError:
                row = None
            if row is not None:
                rows.append(row)
    return pd.DataFrame(rows).sort_values(["source_block", "log_index"]).reset_index(drop=True)


def token_flows(snapshot: dict[str, Any], transaction_specs: dict[str, Any], token: str) -> pd.DataFrame:
    rows = []
    for role, tx_spec in transaction_specs.items():
        receipt = snapshot["receipts"][tx_spec["hash"].lower()]
        for log in receipt["logs"]:
            if log["address"].lower() != token or log["topics"][0].lower() != TRANSFER_TOPIC:
                continue
            rows.append({
                "transaction_role": role,
                "token_address": token,
                "sender": address_from_topic(log["topics"][1]),
                "receiver": address_from_topic(log["topics"][2]),
                "amount_raw": str(int(log["data"], 16)),
                "source_transaction": log["transactionHash"].lower(),
                "source_block": int(log["blockNumber"], 16),
                "source_log_index": int(log["logIndex"], 16),
            })
    return pd.DataFrame(rows).sort_values(["source_block", "source_log_index"]).reset_index(drop=True)


def dvm_resolution(snapshot: dict[str, Any], tx_spec: dict[str, Any]) -> dict[str, Any]:
    receipt = snapshot["receipts"][tx_spec["hash"].lower()]
    rows = []
    for log in receipt["logs"]:
        if log["topics"][0].lower() != REQUEST_RESOLVED_TOPIC:
            continue
        timestamp, ancillary, price = decode(
            ["uint256", "bytes", "int256"], bytes.fromhex(log["data"][2:])
        )
        identifier = log["topics"][3].lower()
        rows.append({
            "round_id": int(log["topics"][1], 16),
            "request_index": int(log["topics"][2], 16),
            "identifier": identifier,
            "request_time": int(timestamp),
            "ancillary_data_hex": "0x" + ancillary.hex(),
            "resolved_price_raw": str(price),
            "dvm_request_id": oracle_request_hash(identifier, int(timestamp), ancillary),
            "source_contract": log["address"].lower(),
            "source_transaction": log["transactionHash"].lower(),
            "source_block": int(log["blockNumber"], 16),
            "source_log_index": int(log["logIndex"], 16),
            "block_timestamp": int(snapshot["blocks"][str(tx_spec["block_number"])]["timestamp"], 16),
        })
    if not rows:
        raise RuntimeError("no RequestResolved events in fixed DVM receipt")
    return rows[0] if len(rows) == 1 else next(
        row for row in rows if row["source_log_index"] == 141
    )


def select_one(frame: pd.DataFrame, event: str, case_id: str | None = None) -> pd.Series:
    selected = frame[frame.event.eq(event)]
    if case_id is not None and "oo_request_id" in selected:
        selected = selected[selected.oo_request_id.eq(case_id)]
    if len(selected) != 1:
        raise RuntimeError(f"expected one {event}, found {len(selected)}")
    return selected.iloc[0]


def flow_amount(
    flows: pd.DataFrame, role: str, sender: str, receiver: str
) -> int:
    selected = flows[
        flows.transaction_role.eq(role)
        & flows.sender.eq(sender.lower())
        & flows.receiver.eq(receiver.lower())
    ]
    if len(selected) != 1:
        raise RuntimeError(f"expected one {role} flow {sender}->{receiver}, got {len(selected)}")
    return int(selected.iloc[0].amount_raw)


def build_episode(
    spec: dict[str, Any], polygon: dict[str, Any], ethereum: dict[str, Any],
    events: pd.DataFrame, flows: pd.DataFrame, dvm: dict[str, Any]
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, bool]]:
    case_id = spec["case_id"]
    expected = spec["expected_economic_result"]
    request = select_one(events, "RequestPrice", case_id)
    proposal = select_one(events, "ProposePrice", case_id)
    dispute = select_one(events, "DisputePrice", case_id)
    settlement = select_one(events, "Settle", case_id)
    initialized = select_one(events[events.source_tx.eq(request.source_tx)], "QuestionInitialized")
    bridge = select_one(events[events.source_tx.eq(dispute.source_tx)], "PriceRequestAdded")
    message = select_one(events[events.source_tx.eq(dispute.source_tx)], "MessageSent")

    oov2 = spec["contracts"]["polygon_oov2"]["address"].lower()
    requester, proposer, disputer = request.requester.lower(), proposal.proposer.lower(), dispute.disputer.lower()
    bond = int(initialized.proposal_bond_raw)
    final_fee = int(request.final_fee_raw)
    escrow = bond + final_fee
    proposer_deposit = flow_amount(flows, "proposal", proposer, oov2)
    disputer_deposit = flow_amount(flows, "dispute", disputer, oov2)
    settlement_transfer = flow_amount(flows, "settlement", oov2, disputer)
    reward_refund = flow_amount(flows, "dispute", oov2, requester)
    reward_rolled = flow_amount(flows, "dispute", requester, oov2)
    fee_rows = flows[
        flows.transaction_role.eq("dispute")
        & flows.sender.eq(oov2)
        & ~flows.receiver.isin([requester, proposer, disputer])
    ]
    if len(fee_rows) != 1:
        raise RuntimeError(f"expected one dispute protocol-fee flow, got {len(fee_rows)}")
    protocol_fee = int(fee_rows.iloc[0].amount_raw)
    principal_returned = escrow
    realized_payoff = settlement_transfer - disputer_deposit
    dispute_receipt = polygon["receipts"][dispute.source_tx]
    gas_cost = receipt_cost(dispute_receipt)
    capital_days = Decimal(disputer_deposit) * Decimal(
        int(settlement.block_time) - int(dispute.block_time)
    ) / Decimal(86400)

    oov2_stamped = stamp_oov2_ancillary(request.ancillary_data_hex, requester)
    expected_bridge_ancillary = stamp_legacy_child_ancillary(oov2_stamped)
    computed_bridge_hash = oracle_request_hash(
        request.identifier, int(bridge.dvm_time), expected_bridge_ancillary
    )
    checks = {
        "four_oov2_lifecycle_events": all(
            len(events[(events.event.eq(name)) & (events.oo_request_id.eq(case_id))]) == 1
            for name in ["RequestPrice", "ProposePrice", "DisputePrice", "Settle"]
        ),
        "adapter_parameters_same_request": initialized.ancillary_data_hex == request.ancillary_data_hex,
        "proposal_deposit_equals_bond_plus_final_fee": proposer_deposit == escrow,
        "disputer_deposit_equals_bond_plus_final_fee": disputer_deposit == escrow,
        "configured_reward_refunded_and_rolled": reward_refund == reward_rolled == int(request.reward_raw),
        "settlement_event_equals_transfer": settlement_transfer == int(settlement.gross_payout_raw),
        "legacy_child_ancillary_exact": bridge.stamped_ancillary_data_hex == "0x" + expected_bridge_ancillary.hex(),
        "bridge_request_hash_exact": bridge.request_hash == computed_bridge_hash == spec["dvm_request_id"],
        "bridge_message_hash_exact": message.message_hash == spec["dvm_request_id"],
        "dvm_request_hash_exact": dvm["dvm_request_id"] == spec["dvm_request_id"],
        "dvm_identifier_time_ancillary_exact": (
            dvm["identifier"] == bridge.identifier
            and dvm["request_time"] == int(bridge.dvm_time)
            and dvm["ancillary_data_hex"] == bridge.stamped_ancillary_data_hex
        ),
        "resolved_price_cross_chain_consistent": (
            dvm["resolved_price_raw"] == str(settlement.resolved_price_raw)
        ),
        "public_result_matches_preregistered_qc_values": all([
            str(request.reward_raw) == expected["question_reward_configured_raw"],
            str(bond) == expected["bond_raw"],
            str(final_fee) == expected["final_fee_raw"],
            str(escrow) == expected["escrow_principal_raw"],
            str(settlement_transfer) == expected["settlement_transfer_raw"],
            str(realized_payoff) == expected["realized_payoff_raw"],
            str(protocol_fee) == expected["protocol_fee_raw"],
        ]),
    }
    if not all(checks.values()):
        raise RuntimeError(f"public case economic/link validation failed: {checks}")

    source_by_variable = {
        "bond_raw": [proposal.source_tx, dispute.source_tx],
        "reward_configured_raw": [request.source_tx],
        "reward_paid_raw": [dispute.source_tx, settlement.source_tx],
        "principal_returned_raw": [dispute.source_tx, settlement.source_tx],
        "bond_forfeited_raw": [proposal.source_tx, dispute.source_tx, settlement.source_tx],
        "final_fee_forfeited_raw": [proposal.source_tx, dispute.source_tx],
        "protocol_fee_raw": [dispute.source_tx],
        "gross_payout_raw": [settlement.source_tx],
        "realized_payoff_raw": [dispute.source_tx, settlement.source_tx],
        "gas_cost_native_raw": [dispute.source_tx],
        "capital_days_locked_raw": [dispute.source_tx, settlement.source_tx],
        "cross_chain_link_grade": [dispute.source_tx, dvm["source_transaction"]],
    }
    value_by_variable = {
        "bond_raw": str(bond), "reward_configured_raw": str(request.reward_raw),
        "reward_paid_raw": str(realized_payoff), "principal_returned_raw": str(principal_returned),
        "bond_forfeited_raw": str(bond), "final_fee_forfeited_raw": str(final_fee),
        "protocol_fee_raw": str(protocol_fee), "gross_payout_raw": str(settlement_transfer),
        "realized_payoff_raw": str(realized_payoff), "gas_cost_native_raw": str(gas_cost),
        "capital_days_locked_raw": format(capital_days, "f"), "cross_chain_link_grade": "A",
    }
    provenance_rows = []
    for variable, value in value_by_variable.items():
        payload = {
            "episode_id": case_id, "variable_name": variable, "value": value,
            "source_transactions": source_by_variable[variable],
            "transformation_rule": f"UMA_PUBLIC_RPC_{variable.upper()}_V1",
        }
        provenance_rows.append({
            **payload, "source_transactions": json.dumps(payload["source_transactions"]),
            "source_layer": "public transaction receipts and decoded canonical logs",
            "validation_status": "passed", "provenance_id": canonical_hash(payload),
        })
    provenance = pd.DataFrame(provenance_rows)
    pids = dict(zip(provenance.variable_name, provenance.provenance_id))
    aggregate_pid = canonical_hash(sorted(pids.values()))

    episode = {
        "schema_version": "1.0.0",
        "episode_id": f"uma:polygon-oov2:{case_id}",
        "protocol": "UMA",
        "mechanism": "Polygon OptimisticOracleV2 -> Ethereum VotingV2",
        "native_unit_type": "disputed_request",
        "observation_unit": "cross_chain_episode",
        "security_chain_namespace": "eip155", "security_chain_id": "1",
        "delivery_chain_namespace": "eip155", "delivery_chain_id": "137",
        "actor": disputer, "actor_role": "disputer",
        "counterparty": proposer, "counterparty_role": "proposer",
        "decision_time_unix": int(dispute.block_time),
        "proposal_time_unix": int(proposal.block_time),
        "dispute_time_unix": int(dispute.block_time),
        "settlement_time_unix": int(settlement.block_time),
        "challenge_deadline_unix": int(proposal.expiration_time),
        "terminal_time_unix": int(settlement.block_time),
        "action": "protocol_observed_action",
        "terminal_outcome": "settled_disputed_disputer_wins",
        "right_censored": False,
        "independent_ground_truth": None,
        "ground_truth_status": "protocol_resolution_only",
        "asset_address": request.currency.lower(), "asset_symbol": "USDC.e", "asset_decimals": 6,
        "bond_raw": str(bond), "reward_configured_raw": str(request.reward_raw),
        "reward_paid_raw": str(realized_payoff), "reward_forfeited_raw": None,
        "principal_returned_raw": str(principal_returned), "bond_forfeited_raw": str(bond),
        "final_fee_forfeited_raw": str(final_fee), "principal_slashed_raw": None,
        "protocol_fee_raw": str(protocol_fee), "gross_payout_raw": str(settlement_transfer),
        "realized_payoff_raw": str(realized_payoff), "gas_cost_native_raw": str(gas_cost),
        "investigation_cost_usd": None, "delay_cost_usd": None, "capital_cost_usd": None,
        "usd_value": None, "usd_conversion_source": None, "usd_conversion_time_unix": None,
        "reward_to_bond_ratio": str(Decimal(int(request.reward_raw)) / Decimal(bond)),
        "dispute_decision": True, "proposal_upheld": False,
        "mandatory_wait_seconds": int(proposal.expiration_time) - int(proposal.block_time),
        "resolution_delay_seconds": int(settlement.block_time) - int(dispute.block_time),
        "settlement_delay_seconds": int(settlement.block_time) - int(request.block_time),
        "excess_delay_seconds": int(settlement.block_time) - int(request.block_time)
        - (int(proposal.expiration_time) - int(proposal.block_time)),
        "capital_days_locked_raw": format(capital_days, "f"),
        "verification_cost_usd": None, "economic_regret_usd": None,
        "independent_ground_truth_available": False,
        "dvm_positive_redistribution_raw": None, "dvm_negative_slash_raw": None,
        "decision_evidence_ids": [pids[name] for name in ["bond_raw", "reward_configured_raw"]],
        "evidence_snapshot_time_unix": int(dispute.block_time),
        "future_fields_excluded": [
            "resolved_price_raw", "settlement_time_unix", "reward_paid_raw",
            "principal_returned_raw", "terminal_outcome",
        ],
        "source_chain_namespace": "eip155", "source_chain_id": "137",
        "source_contract": dispute.source_contract.lower(),
        "source_transaction": dispute.source_tx.lower(), "source_log_index": int(dispute.log_index),
        "source_block_number": int(dispute.source_block),
        "source_block_timestamp_unix": int(dispute.block_time), "source_event": "DisputePrice",
        "source_table": "public RPC receipts -> decoded protocol events -> economic episode",
        "source_finality_rule": (
            "Fixed successful Polygon and Ethereum receipts; receipt block hashes equal independently "
            "fetched canonical headers and every log has removed=false."
        ),
        "cross_chain_link_grade": "A", "provenance_id": aggregate_pid,
        "prov_entity_id": f"prov:entity:uma-public:{case_id}",
        "prov_activity_id": "prov:activity:reproduce_uma_public_rpc_case_v1",
        "prov_agent_id": "prov:softwareAgent:oracle-nature",
        "transformation_rule_id": "UMA_PUBLIC_RPC_REAL_EPISODE_V1",
        "contract_semantics_rule_id": "UMA_OOV2_SETTLEMENT_PAYMENT_V1",
        "coverage_status": "partial",
        "missing_reason": (
            "Independent truth, off-chain investigation cost, timestamped USD conversion and DVM voter-level "
            "redistribution are outside this five-transaction public reproduction."
        ),
        "evidence_grade": "A", "validation_status": "passed",
        "validation_rule_ids": [
            "PUBLIC_RPC_CANONICAL_RECEIPT_V1", "UMA_CASE_EVENT_COMPLETENESS_V1",
            "UMA_CASE_SETTLEMENT_FLOW_EXACT_V1", "UMA_CASE_CROSSCHAIN_GRADE_A_V1",
        ],
        "interpretation_note": (
            "Protocol-resolved disputer win, not independently verified truth. Returned principal is excluded "
            "from realized payoff; native Polygon Gas is not added to USDC.e."
        ),
    }
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema).iter_errors(episode))
    if errors:
        raise RuntimeError("episode schema errors: " + "; ".join(error.message for error in errors))

    timeline = pd.DataFrame([
        {"stage": "Request", "timestamp": int(request.block_time), "chain": "Polygon", "transaction_hash": request.source_tx},
        {"stage": "Proposal", "timestamp": int(proposal.block_time), "chain": "Polygon", "transaction_hash": proposal.source_tx},
        {"stage": "Dispute", "timestamp": int(dispute.block_time), "chain": "Polygon", "transaction_hash": dispute.source_tx},
        {"stage": "DVM resolution", "timestamp": dvm["block_timestamp"], "chain": "Ethereum", "transaction_hash": dvm["source_transaction"]},
        {"stage": "Settlement", "timestamp": int(settlement.block_time), "chain": "Polygon", "transaction_hash": settlement.source_tx},
    ])
    timeline["hours_since_request"] = (timeline.timestamp - int(request.block_time)) / 3600
    cashflows = pd.DataFrame([
        {"role": "proposer", "component": "bond + final fee lost", "amount_raw": -escrow},
        {"role": "disputer", "component": "escrow deposited", "amount_raw": -disputer_deposit},
        {"role": "disputer", "component": "settlement received", "amount_raw": settlement_transfer},
        {"role": "oracle fee recipient", "component": "protocol fee", "amount_raw": protocol_fee},
    ])
    cashflows["amount_token"] = cashflows.amount_raw / 10**6
    return episode, provenance, timeline, cashflows, checks


def abc_measures(episode: dict[str, Any], provenance: pd.DataFrame) -> pd.DataFrame:
    definitions = json.loads(ABC_DICTIONARY.read_text(encoding="utf-8"))
    pids = dict(zip(provenance.variable_name, provenance.provenance_id))
    direct = {name: episode.get(name) for name in [
        "bond_raw", "reward_configured_raw", "reward_to_bond_ratio", "mandatory_wait_seconds",
        "protocol_fee_raw", "capital_days_locked_raw", "gas_cost_native_raw", "dispute_decision",
        "proposal_upheld", "settlement_delay_seconds", "excess_delay_seconds", "reward_paid_raw",
        "principal_returned_raw", "bond_forfeited_raw", "gross_payout_raw", "realized_payoff_raw",
        "right_censored", "independent_ground_truth_available", "economic_regret_usd", "verification_cost_usd",
    ]}
    direct["token_only_action_regret_raw"] = "0"
    rows = []
    for item in definitions:
        name = item["variable_name"]
        value = direct.get(name)
        if item["measure_family"] == "A":
            status, reason = "not_applicable_case_level", "A single episode cannot identify a protocol-window concentration measure."
        elif name in {"dvm_signed_payoff_delta_raw", "dvm_applied_stake_delta_raw"}:
            status, reason = "outside_minimal_public_case", "The five fixed lifecycle transactions do not contain the full DVM voter/account application history."
        elif value is None:
            status, reason = "unavailable", item["missing_value_rule"]
        else:
            status, reason = "observed_or_deterministic", None
        rows.append({
            "episode_id": episode["episode_id"], "measure_family": item["measure_family"],
            # A long-form Parquet column needs one stable physical type.  Raw
            # integers stay lossless because they are serialized as decimal
            # strings; the accompanying dictionary carries the unit/type.
            "variable_name": name,
            "value_raw_or_text": (
                None if value is None else str(value).lower() if isinstance(value, bool) else str(value)
            ),
            "measurement_unit": item["measurement_unit"], "observation_unit": item["observation_unit"],
            "case_measure_status": status, "missing_reason": reason,
            "provenance_id": pids.get(name, episode["provenance_id"]),
        })
    return pd.DataFrame(rows)


def render_figure(output: Path, timeline: pd.DataFrame, cashflows: pd.DataFrame) -> None:
    folder = output / "figures"
    folder.mkdir(parents=True, exist_ok=True)
    colors = {"Polygon": "#2563EB", "Ethereum": "#D97706"}
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.7), gridspec_kw={"width_ratios": [1.35, 1]})
    ax = axes[0]
    offsets = {"Request": .18, "Proposal": -.20, "Dispute": .20, "DVM resolution": .20, "Settlement": -.20}
    for row in timeline.itertuples():
        ax.scatter(row.hours_since_request, 0, s=85, color=colors[row.chain], zorder=3)
        ax.annotate(row.stage, (row.hours_since_request, 0), xytext=(row.hours_since_request, offsets[row.stage]),
                    ha="center", fontsize=8, arrowprops={"arrowstyle": "-", "color": "#64748B", "lw": .7})
    ax.plot(timeline.hours_since_request, [0] * len(timeline), color="#94A3B8", lw=1.5)
    ax.set_yticks([]); ax.set_ylim(-.34, .34); ax.set_xlabel("Hours since RequestPrice")
    ax.set_title("(a) Public-RPC lifecycle", loc="left", weight="bold")
    ax.spines[["left", "right", "top"]].set_visible(False)
    for chain, color in colors.items(): ax.scatter([], [], color=color, label=chain)
    ax.legend(frameon=False, loc="lower right", ncol=2, fontsize=8)
    ax = axes[1]
    net = cashflows.groupby("role", as_index=False).amount_token.sum()
    bars = ax.bar(net.role, net.amount_token, color=["#C44536" if x < 0 else "#0F766E" for x in net.amount_token])
    ax.axhline(0, color="#64748B", lw=.8)
    for bar, value in zip(bars, net.amount_token):
        ax.text(bar.get_x() + bar.get_width()/2, value + (18 if value >= 0 else -18), f"{value:+.0f}",
                ha="center", va="bottom" if value >= 0 else "top", fontsize=8)
    ax.set_ylim(-900, 650); ax.set_ylabel("Net USDC.e (principal flows included)")
    ax.set_title("(b) Reconciled allocation", loc="left", weight="bold")
    ax.tick_params(axis="x", rotation=18); ax.spines[["right", "top"]].set_visible(False)
    fig.suptitle("One real UMA episode rebuilt from public source records", weight="bold", fontsize=13)
    fig.tight_layout()
    fig.savefig(folder / "uma_public_rpc_case.pdf", bbox_inches="tight")
    fig.savefig(folder / "uma_public_rpc_case.png", dpi=240, bbox_inches="tight")
    plt.close(fig)


def write_outputs(
    output: Path, spec: dict[str, Any], polygon: dict[str, Any], ethereum: dict[str, Any],
    source_records: list[dict[str, Any]], contract_semantics: list[dict[str, Any]],
    chain_qc: list[dict[str, Any]], events: pd.DataFrame,
    flows: pd.DataFrame, dvm: dict[str, Any], episode: dict[str, Any], provenance: pd.DataFrame,
    timeline: pd.DataFrame, cashflows: pd.DataFrame, economic_checks: dict[str, bool]
) -> None:
    for folder in ["raw", "validated", "processed", "economic", "statistics", "figures"]:
        (output / folder).mkdir(parents=True, exist_ok=True)
    (output / "raw/polygon_rpc_snapshot.json").write_text(json.dumps(polygon, indent=2) + "\n", encoding="utf-8")
    (output / "raw/ethereum_rpc_snapshot.json").write_text(json.dumps(ethereum, indent=2) + "\n", encoding="utf-8")
    (output / "source/case_spec.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    (output / "source/source_manifest.json").write_text(json.dumps(source_records, indent=2) + "\n", encoding="utf-8")
    events.to_parquet(output / "validated/polygon_decoded_events.parquet", index=False)
    flows.to_parquet(output / "validated/token_flows.parquet", index=False)
    pd.DataFrame([dvm]).to_parquet(output / "validated/ethereum_dvm_resolution.parquet", index=False)
    pd.DataFrame(chain_qc).to_parquet(output / "validated/canonical_chain_qc.parquet", index=False)
    (output / "validated/contract_semantics.json").write_text(
        json.dumps(contract_semantics, indent=2) + "\n", encoding="utf-8"
    )
    qc_rows = [{"check": k, "passed": v} for k, v in economic_checks.items()]
    pd.DataFrame(qc_rows).to_parquet(output / "validated/economic_link_qc.parquet", index=False)
    (output / "processed/economic_episode.json").write_text(json.dumps(episode, indent=2) + "\n", encoding="utf-8")
    pd.DataFrame([episode]).to_parquet(output / "processed/economic_episode.parquet", index=False)
    provenance.to_parquet(output / "economic/variable_provenance.parquet", index=False)
    measures = abc_measures(episode, provenance)
    measures.to_parquet(output / "economic/abc_economic_measures.parquet", index=False)
    measures.to_csv(output / "economic/abc_economic_measures.csv", index=False)
    timeline.to_parquet(output / "statistics/lifecycle_timeline.parquet", index=False)
    cashflows.to_parquet(output / "statistics/economic_cashflows.parquet", index=False)
    summary = {
        "episode_id": episode["episode_id"], "source_transactions": 5,
        "decoded_polygon_events": len(events), "usdc_transfer_rows": len(flows),
        "bond_raw": episode["bond_raw"], "principal_returned_raw": episode["principal_returned_raw"],
        "realized_payoff_raw": episode["realized_payoff_raw"],
        "cross_chain_link_grade": episode["cross_chain_link_grade"],
        "all_required_assertions_pass": all(economic_checks.values()) and all(row["passed"] for row in chain_qc),
    }
    (output / "statistics/summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    pd.DataFrame([summary]).to_csv(output / "statistics/summary.csv", index=False)
    render_figure(output, timeline, cashflows)

    source_status = ", ".join(f"{row['id']}={row['status']}" for row in source_records)
    report = f"""# Public-source UMA clean-room reproduction

## Scope and inputs

This fixed episode is rebuilt without reading any curated Oracle-Nature ledger. The only
semantic inputs are five public transaction receipts and canonical block headers (four on
Polygon, one on Ethereum), deployed runtime bytecode, checksum-pinned UMA contract source,
and the public case specification. Polygon provider: `{polygon['public_provider']}`;
Ethereum provider: `{ethereum['public_provider']}`. Source verification: {source_status}.

## Reconstructed economic result

The requester configured 5 USDC.e, while proposer and disputer each escrowed 750 USDC.e
(500 bond + 250 final fee). The DVM protocol resolution overturned the proposal. The
disputer received 1,000 USDC.e: 750 returned principal plus 250 realized token gain. The
configured 5 USDC.e was refunded and rolled into the reset request, so it is not counted as
paid reward. The protocol fee is 500 USDC.e. Dispute Gas is retained separately as
`{episode['gas_cost_native_raw']}` raw MATIC and is never added to USDC.e.

## Validation and boundary

All {len(chain_qc)} canonical receipt/header checks and all {len(economic_checks)} lifecycle,
cross-chain and flow checks pass. The Polygon bridge request hash, message hash and Ethereum
DVM request ID are identical, producing `cross_chain_link_grade=A`. Seven source-code
semantic rules pass, including the separation of `VoterSlashed` accrual from
`VoterSlashApplied` stake mutation. This is protocol resolution, not independent factual
truth; the minimal five-transaction case does not reconstruct the complete voter population,
off-chain investigation cost or timestamped USD welfare.

## Reproduction

```bash
python scripts/case_studies/reproduce_uma_public_rpc_case.py
```

For deterministic offline replay after the public evidence has been frozen:

```bash
python scripts/case_studies/reproduce_uma_public_rpc_case.py \\
  --snapshot-dir data/case_studies/uma_public_rpc_reproduction/raw \\
  --source-cache data/case_studies/uma_public_rpc_reproduction/source \\
  --offline-sources
```
"""
    (output / "report.md").write_text(report, encoding="utf-8")

    files = sorted(path for path in output.rglob("*") if path.is_file() and path.name != "manifest.json")
    manifest = {
        "schema_version": "1.0.0", "case_id": spec["case_id"],
        "derivation_inputs": "public RPC receipts, canonical block headers, deployed code and pinned public contract sources",
        "curated_ledger_inputs_used": False,
        "source_modes": {"polygon": polygon["source_mode"], "ethereum": ethereum["source_mode"]},
        "source_origin_modes": {
            "polygon": polygon.get("snapshot_origin_mode", polygon["source_mode"]),
            "ethereum": ethereum.get("snapshot_origin_mode", ethereum["source_mode"]),
        },
        "public_provider_hosts": {
            "polygon": polygon["public_provider"], "ethereum": ethereum["public_provider"],
        },
        "contract_semantic_rules_passed": len(contract_semantics),
        "all_required_assertions_pass": summary["all_required_assertions_pass"],
        "assertions": economic_checks,
        "files": [{
            "path": str(path.relative_to(output)), "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        } for path in files],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, default=SPEC_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--polygon-rpc", default=os.environ.get("PUBLIC_POLYGON_RPC_URL"))
    parser.add_argument("--ethereum-rpc", default=os.environ.get("PUBLIC_ETHEREUM_RPC_URL"))
    parser.add_argument("--snapshot-dir", type=Path, help="Replay redacted raw snapshots without network access")
    parser.add_argument(
        "--source-cache", type=Path,
        help="Directory containing checksum-pinned contract source files for offline replay",
    )
    parser.add_argument("--offline-sources", action="store_true", help="Do not refetch pinned contract sources")
    args = parser.parse_args()
    spec = json.loads(args.spec.resolve().read_text(encoding="utf-8"))
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if args.snapshot_dir:
        polygon = load_fixture_chain("polygon", args.snapshot_dir.resolve())
        ethereum = load_fixture_chain("ethereum", args.snapshot_dir.resolve())
    else:
        polygon_contracts = [item for item in spec["contracts"].values() if item["chain"] == "polygon" and "runtime_code_hash" in item]
        ethereum_contracts = [item for item in spec["contracts"].values() if item["chain"] == "ethereum" and "runtime_code_hash" in item]
        polygon = fetch_live_chain("polygon", spec["chains"]["polygon"], polygon_contracts, args.polygon_rpc)
        ethereum = fetch_live_chain("ethereum", spec["chains"]["ethereum"], ethereum_contracts, args.ethereum_rpc)
        if not all(item["hash_matches"] for item in polygon["contract_code_evidence"] + ethereum["contract_code_evidence"]):
            raise RuntimeError("deployed runtime code hash mismatch")
    chain_qc = validate_chain_snapshot(polygon, spec["chains"]["polygon"])
    chain_qc += validate_chain_snapshot(ethereum, spec["chains"]["ethereum"])
    source_records = fetch_source_records(
        spec, output, args.offline_sources,
        args.source_cache.resolve() if args.source_cache else None,
    )
    contract_semantics = verify_contract_semantics(output)
    events = polygon_events(polygon, spec["chains"]["polygon"]["transactions"])
    flows = token_flows(
        polygon, spec["chains"]["polygon"]["transactions"],
        spec["contracts"]["polygon_usdc_e"]["address"].lower(),
    )
    dvm = dvm_resolution(ethereum, spec["chains"]["ethereum"]["transactions"]["dvm_resolution"])
    episode, provenance, timeline, cashflows, checks = build_episode(
        spec, polygon, ethereum, events, flows, dvm
    )
    write_outputs(
        output, spec, polygon, ethereum, source_records, contract_semantics,
        chain_qc, events, flows, dvm,
        episode, provenance, timeline, cashflows, checks,
    )
    print(json.dumps({
        "output": str(output), "case_id": spec["case_id"],
        "source_modes": {"polygon": polygon["source_mode"], "ethereum": ethereum["source_mode"]},
        "public_providers": {
            "polygon": polygon.get("public_provider"), "ethereum": ethereum.get("public_provider")
        },
        "all_required_assertions_pass": True,
    }, indent=2))


if __name__ == "__main__":
    main()
