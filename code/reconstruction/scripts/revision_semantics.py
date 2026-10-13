"""Versioned corrections shared by snapshot replay and native builders.

These rules change scientific meaning, not only schema acceptance. Native
VoterSlashed amounts are retained as accruals and never as applied principal.
"""
SCHEMA_VERSION = "2.0.0"

# An observed but unsettled request has a mapping rule, not a settlement rule.
# Leave any other missing rule unset so validation catches an unknown case.
UNSETTLED_RULE_EXPR = """CASE WHEN native_table='polygon_uma_request_rounds'
    AND outcome_status='not_settled' AND rule_id IS NULL
    THEN 'uma_oov2_unsettled_request_observation_v2' ELSE rule_id END AS rule_id"""
MAPPING_RULES = {
    'uma_oov2_unsettled_request_observation_v2':
        'A retained UMA request has economic_status=not_settled. The rule records request observability only; it does not establish settlement, a realized payment or report correctness.'
}

TRUTH_DEFINITIONS = {
    "undisputed_acceptance": "Protocol acceptance without adjudication; does not establish factual truth.",
    "protocol_vote_adjudication": "Protocol voting outcome, not independent factual ground truth.",
    "consensus_median_alignment": "Agreement with the protocol aggregate, not an independent reference.",
    "independent_reference_adjudication": "Adjudication against an explicitly identified independent reference; not inferred from a transfer.",
    "service_availability_condition": "Recorded service or eligibility condition, without a factual truth judgment.",
    "external_ground_truth": "Independent factual label requiring its own source and validation.",
    "protocol_aggregate": "Tellor native report/aggregate inclusion; does not certify the report as true.",
    "signed_payload_verification": "RedStone authenticated payload evidence; signatures authenticate a source, not the price.",
    "cryptographic_validation_and_challenge": "Chronicle validation/challenge mechanism; factual truth is not independently observed.",
    "protocol_recognized_reporting": "Tellor report recognized for a payment; recognition is not external truth.",
    "staking_participation_not_individual_report_truth": "DIA staking withdrawal evidence, with no individual report correctness label.",
    "protocol_state_transition": "Observed Pyth stake/transfer state transition without independent factual adjudication.",
}
UNIT_DEFINITIONS = {
    "request": "One oracle request round, identified by the native request ID.",
    "individual_report": "One native report or authenticated update; not a unique independent real-world fact.",
    "dispute": "A native dispute or a vote/payment event linked to a dispute; consult event_granularity.",
    "voting_request": "Voter-level accrual linked to a DVM request; multiple voters share the request ID.",
    "voting_epoch": "A protocol-defined voting round.",
    "reward_epoch": "A provider, beneficiary or claim observation linked to a protocol reward epoch.",
    "publisher_pool_epoch": "Pyth publisher epoch, stake instruction or reward transfer; native granularity remains essential.",
    "service_availability_window": "Chainlink service interval or staking action; consult native_table and event_granularity.",
    "reporter_jail_lifecycle": "Tellor jail/release event; two rows may belong to one restriction lifecycle.",
    "staking_position": "DIA withdrawal against a native staking position index.",
}


def common_projection(source: str, sample_c: bool = False) -> str:
    """Read v1 common-family rows and return v2 without losing accrued amounts."""
    replacements = [
        f"'{SCHEMA_VERSION}' AS schema_version",
        UNSETTLED_RULE_EXPR,
        "CASE WHEN native_table='uma_dvm_voter_payoffs' THEN NULL ELSE principal_slashed_raw END AS principal_slashed_raw",
        "CASE WHEN native_table='uma_dvm_voter_payoffs' AND penalty_class='principal_slash' THEN 'accrued_stake_penalty' ELSE penalty_class END AS penalty_class",
        "CASE WHEN native_table='uma_dvm_voter_payoffs' AND reward_class='correct_vote_redistribution' THEN 'accrued_stake_redistribution' ELSE reward_class END AS reward_class",
        "CASE WHEN native_table IN ('pyth_ois_stake_events','pyth_ois_economic_events') THEN 'protocol_state_transition' ELSE truth_basis END AS truth_basis",
        "CASE WHEN native_table='uma_dvm_voter_payoffs' THEN 'VoterSlashed is an accrued signed adjustment. Applied net changes belong to VoterSlashApplied; do not sum the two stages.' ELSE interpretation_note END AS interpretation_note",
    ]
    if sample_c:
        replacements.append("""CASE
          WHEN native_table='tellor_disputes' AND outcome_status LIKE '%SUPPORT' THEN 'tellor_report_rejected'
          WHEN native_table='tellor_disputes' AND outcome_status LIKE '%AGAINST' THEN 'tellor_report_supported'
          WHEN native_table='tellor_disputes' THEN 'tellor_report_not_adjudicated'
          WHEN native_table='uma_dvm_voter_payoffs' THEN replace(strict_event_class,'_slash','_penalty_accrual')
          ELSE strict_event_class END AS strict_event_class""")
    # The CTE preserves the original amount before replacing its misleading field.
    return f"""WITH original AS (
      SELECT *, CASE WHEN native_table='uma_dvm_voter_payoffs' THEN principal_slashed_raw END AS penalty_accrued_raw
      FROM {source}
    ) SELECT * REPLACE ({', '.join(replacements)}) FROM original"""
