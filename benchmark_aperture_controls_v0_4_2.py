#!/usr/bin/env python3
"""Versioned diagnostic closure for the EBRT v0.4.1 aperture controls.

v0.4.2 leaves the v0.4.1 runner, lock, and artifacts byte-identical.  It
inherits their provider-facing protocol and changes only local adjudication,
diagnostic instrumentation, direction ordering, and fixed execution presets.
No rejected public card or raw exception message is persisted.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import benchmark_aperture_controls_v0_4_1 as v041
from language_replay_bridge_v0_4 import CardResult, DecisionFact, ReasoningCard


ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = "ebrt-aperture-controls-benchmark-v0.4.2"
LOCK_PATH = ROOT / "policy_lock_aperture_controls_v0_4_2.json"
PREDECESSOR_RUNNER_PATH = ROOT / "benchmark_aperture_controls_v0_4_1.py"
PREDECESSOR_LOCK_PATH = ROOT / "policy_lock_aperture_controls_v0_4_1.json"
PREDECESSOR_MANIFEST_PATH = (
    ROOT / "artifacts" / "benchmark_aperture_controls_v0_4_1_dev" / "manifest.json"
)
DEFAULT_SMOKE_OUTPUT = ROOT / "benchmark_results" / "v0_4_2_aperture_live_smoke"
DEFAULT_CONTRACT_SMOKE_OUTPUT = (
    ROOT / "benchmark_results" / "v0_4_2_aperture_contract_live_smoke"
)
DEFAULT_SUBSET_OUTPUT = ROOT / "benchmark_results" / "v0_4_2_aperture_live_subset"
DEFAULT_DEV_OUTPUT = ROOT / "benchmark_results" / "v0_4_2_aperture_dev"

ARMS = v041.ARMS
ONE_SHOT_ARMS = v041.ONE_SHOT_ARMS
STAGED_ARMS = v041.STAGED_ARMS
LOCKED_TRIALS = v041.LOCKED_TRIALS
LOCKED_CASE_COUNT = v041.LOCKED_CASE_COUNT
LOCKED_CALLS_PER_CASE_TRIAL = v041.LOCKED_CALLS_PER_CASE_TRIAL
ONE_SHOT_INSTRUCTIONS = v041.ONE_SHOT_INSTRUCTIONS
STAGED_INSTRUCTIONS = v041.STAGED_INSTRUCTIONS

LOCAL_CONTRACT_REASON_CODES = (
    "answer_choice_violation",
    "checkpoint_id_mismatch",
    "claim_character_bound_exceeded",
    "disallowed_decision_slot_value",
    "duplicate_decision_slot",
    "invalidated_active_support",
    "invented_invalidation",
    "missing_required_decision_slot",
    "multiple_raw_chunks_copied",
    "topic_character_bound_exceeded",
    "unavailable_evidence_citation",
    "unknown_decision_slot",
    "unseen_active_support",
)

RECEIPT_AUDIT_REASON_CODES = ("receipt_request_fingerprint_mismatch",)

SOURCE_FILES = tuple(
    dict.fromkeys(
        (
            "benchmark_aperture_controls_v0_4_2.py",
            "policy_lock_aperture_controls_v0_4_2.json",
            "benchmark_aperture_controls_v0_4_1.py",
            "policy_lock_aperture_controls_v0_4_1.json",
            "artifacts/benchmark_aperture_controls_v0_4_1_dev/manifest.json",
            "artifacts/benchmark_direct_full_calibration_v0_4_dev/manifest.json",
            *v041.PR6_SOURCE_FILES,
        )
    )
)
BOOT_SOURCE_SNAPSHOT = {
    name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    for name in SOURCE_FILES
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_snapshot() -> dict[str, str]:
    return {name: _sha256(ROOT / name) for name in SOURCE_FILES}


def _assert_source_snapshot(expected: Mapping[str, str]) -> None:
    if dict(expected) != _source_snapshot():
        raise RuntimeError(
            "v0.4.2 diagnostic-closure source graph changed during execution"
        )


def _load_overlay() -> dict[str, Any]:
    value = v041._load_json(LOCK_PATH)
    if value.get("schema_version") != "ebrt-aperture-controls-policy-lock-v0.4.2":
        raise RuntimeError("v0.4.2 policy-lock schema drifted")
    if (
        value.get("status") != "DEV_DRAFT"
        or value.get("promotion_eligible") is not False
    ):
        raise RuntimeError("v0.4.2 policy lock must remain non-promotional DEV_DRAFT")
    predecessor = value.get("predecessor", {})
    expected_predecessor = {
        "runner": PREDECESSOR_RUNNER_PATH.name,
        "runner_sha256": _sha256(PREDECESSOR_RUNNER_PATH),
        "policy_lock": PREDECESSOR_LOCK_PATH.name,
        "policy_lock_sha256": _sha256(PREDECESSOR_LOCK_PATH),
        "artifact_manifest": str(PREDECESSOR_MANIFEST_PATH.relative_to(ROOT)),
        "artifact_manifest_sha256": _sha256(PREDECESSOR_MANIFEST_PATH),
        "result_interpretation": "v0_4_1_remains_byte_identical_and_is_not_re_adjudicated",
    }
    if predecessor != expected_predecessor:
        raise RuntimeError("v0.4.2 predecessor pin drifted")
    if value.get("protocol_inheritance", {}).get("provider_facing_change") is not False:
        raise RuntimeError(
            "v0.4.2 must not introduce a provider-facing protocol change"
        )
    if tuple(sorted(value.get("local_contract_reason_codes", ()))) != (
        LOCAL_CONTRACT_REASON_CODES
    ):
        raise RuntimeError("v0.4.2 local contract reason-code enum drifted")
    if tuple(value.get("non_assessable_receipt_audit_reason_codes", ())) != (
        RECEIPT_AUDIT_REASON_CODES
    ):
        raise RuntimeError("v0.4.2 receipt-audit reason-code enum drifted")
    terminal = value.get("terminal_contract_failure_policy", {})
    local = terminal.get("local_contract_rejection_after_completed_provider_call", {})
    non_assessable = terminal.get(
        "provider_contract_provider_call_receipt_audit_or_internal_failure", {}
    )
    if (
        local.get("arm_action") != "terminal_no_retry_no_repair"
        or local.get("primary_endpoint") != "assessed_strict_failure"
        or local.get("rejected_card") != "not_persisted"
        or non_assessable.get("primary_endpoint") != "not_assessed"
        or terminal.get("no_post_hoc_retry_or_v0_4_1_reclassification") is not True
    ):
        raise RuntimeError("v0.4.2 terminal local-contract policy drifted")
    direction = value.get("direction_rule_revision_envelope", {})
    if tuple(direction.get("ordering", ())) != (
        "mixed",
        "contributes_on_this_dev",
        "harmful_on_this_dev",
        "not_needed_on_this_saturated_dev",
        "no_detected_effect_below_ceiling",
    ):
        raise RuntimeError("v0.4.2 revision-envelope direction ordering drifted")
    presets = value.get("execution_presets", {})
    expected_launch_gate = (
        "exact_two_case_one_trial_coverage",
        "receipt_validation_true",
        "all_attempted_receipts_validated",
        "each_arm_completed_or_allowlisted_terminal_local_contract_rejection",
        "each_terminal_rejection_backed_by_completed_exact_usage_receipt",
        "zero_provider_internal_or_other_non_assessable_failures",
    )
    if (
        tuple(presets.get("live_contract_smoke", {}).get("case_ids", ()))
        != ("unit_reinterpretation", "invalidated_sensor_fallback")
        or presets.get("live_contract_smoke", {}).get("trials") != 1
        or presets.get("live_contract_smoke", {}).get("nominal_api_calls") != 28
        or tuple(
            presets.get("live_contract_smoke", {}).get(
                "full_run_launch_ready_requires", ()
            )
        )
        != expected_launch_gate
        or presets.get("live_dev", {}).get("case_or_trial_override") != "forbidden"
        or presets.get("live_dev", {}).get("contract_smoke_manifest")
        != "required_same_source_and_revalidated_before_provider_calls"
    ):
        raise RuntimeError("v0.4.2 execution preset drifted")
    return value


def _load_lock() -> dict[str, Any]:
    """Return the pinned v0.4.1 lock plus the explicit v0.4.2 overlay."""

    base = copy.deepcopy(v041._load_lock())
    overlay = _load_overlay()
    base["schema_version"] = overlay["schema_version"]
    base["protocol_id"] = overlay["protocol_id"]
    base["v0_4_2_overlay"] = overlay
    base["claim_boundary"] = [
        *base["claim_boundary"],
        *overlay["claim_boundary_append"],
    ]
    base["fixtures"]["contract_smoke_case_ids"] = overlay["execution_presets"][
        "live_contract_smoke"
    ]["case_ids"]
    return base


class LocalContractViolation(ValueError):
    """A rejected public card with one stable, non-sensitive reason code."""

    def __init__(self, reason_code: str, *, request_fingerprint: str) -> None:
        if reason_code not in LOCAL_CONTRACT_REASON_CODES:
            raise AssertionError("unknown local contract reason code")
        super().__init__(f"local public-card contract rejected: {reason_code}")
        self.reason_code = reason_code
        self.request_fingerprint = request_fingerprint


class ReceiptAuditViolation(RuntimeError):
    """A non-assessable mismatch between the request and provider receipt."""

    def __init__(self, reason_code: str) -> None:
        if reason_code not in RECEIPT_AUDIT_REASON_CODES:
            raise AssertionError("unknown receipt audit reason code")
        super().__init__(f"receipt audit invariant rejected: {reason_code}")
        self.reason_code = reason_code


def _reject(reason_code: str, *, request_fingerprint: str) -> None:
    raise LocalContractViolation(
        reason_code,
        request_fingerprint=request_fingerprint,
    )


def _validate_mapping_result(
    case: v041.CaseSpec,
    context: v041.FixedRevisionEnvelope,
    input_payload: Mapping[str, Any],
    result: CardResult,
    *,
    seen_raw_ids: Sequence[str],
) -> None:
    card = result.card
    expected_request_fingerprint = v041.fingerprint(input_payload)
    if result.receipt.request_fingerprint != expected_request_fingerprint:
        raise ReceiptAuditViolation("receipt_request_fingerprint_mismatch")

    def reject(reason_code: str) -> None:
        _reject(
            reason_code,
            request_fingerprint=expected_request_fingerprint,
        )

    if card.checkpoint_id != input_payload["checkpoint_id"]:
        reject("checkpoint_id_mismatch")
    if card.current_answer not in case.answer_choices:
        reject("answer_choice_violation")
    slot_values = {
        item.slot_id: set(item.allowed_values) for item in case.decision_slots
    }
    required_slots = {item.slot_id for item in case.decision_slots if item.required}
    observed_slots: set[str] = set()
    for fact in card.decision_facts:
        if fact.slot in observed_slots:
            reject("duplicate_decision_slot")
        observed_slots.add(fact.slot)
        if fact.slot not in slot_values:
            reject("unknown_decision_slot")
        if fact.value not in slot_values[fact.slot]:
            reject("disallowed_decision_slot_value")
    if required_slots - observed_slots:
        reject("missing_required_decision_slot")
    if len(card.claim) > v041.MAX_PUBLIC_CLAIM_CHARACTERS:
        reject("claim_character_bound_exceeded")
    if len(card.topic) > v041.MAX_PUBLIC_TOPIC_CHARACTERS:
        reject("topic_character_bound_exceeded")
    seen = set(str(item) for item in seen_raw_ids)
    verbatim_matches = v041._verbatim_raw_match_ids(case, card, seen_raw_ids)
    if len(verbatim_matches) > v041.MAX_VERBATIM_RAW_CHUNK_MATCHES:
        reject("multiple_raw_chunks_copied")
    allowed = set(str(item) for item in input_payload["allowed_evidence_ids"])
    if not seen <= set(case.evidence_ids):
        raise AssertionError("validator seen-raw boundary escaped the case")
    active_support = set(card.evidence_ids)
    cited = set(card.evidence_ids) | set(card.invalidated_evidence_ids)
    for fact in card.decision_facts:
        active_support.update(fact.evidence_ids)
        cited.update(fact.evidence_ids)
    if cited - allowed:
        reject("unavailable_evidence_citation")
    if active_support - seen:
        reject("unseen_active_support")
    permitted_invalidated = set(context.invalidated_evidence_ids)
    if active_support & permitted_invalidated:
        reject("invalidated_active_support")
    if set(card.invalidated_evidence_ids) - permitted_invalidated:
        reject("invented_invalidation")


# The frozen executor resolves this validator through its own module globals.
# Rebinding at import time lets v0.4.2 inherit the byte-identical prompt and
# call geometry while keeping the predecessor source file untouched.
v041._validate_mapping_result = _validate_mapping_result


def _failure_category(error: BaseException) -> str:
    if isinstance(error, LocalContractViolation):
        return "local_contract_error"
    if isinstance(error, ReceiptAuditViolation):
        return "receipt_audit_invariant_error"
    provider_category = getattr(error, "category", None)
    if provider_category == "transport_error":
        return "provider_call_exception_unclassified"
    if provider_category == "contract_error":
        return "contract_error"
    if isinstance(error, AssertionError):
        return "internal_invariant_error"
    if isinstance(error, ValueError):
        return "execution_value_error"
    return "unexpected_exception"


def _failure_reason_code(error: BaseException) -> str:
    if isinstance(error, LocalContractViolation):
        return error.reason_code
    if isinstance(error, ReceiptAuditViolation):
        return error.reason_code
    category = getattr(error, "category", None)
    if category == "transport_error":
        return "provider_call_exception_unclassified"
    if category == "contract_error":
        return "provider_response_contract_error"
    if isinstance(error, AssertionError):
        return "internal_invariant_error"
    if isinstance(error, ValueError):
        return "execution_value_error"
    return "unexpected_exception"


def _run_one_arm(
    *,
    arm: str,
    case: v041.CaseSpec,
    context: v041.FixedRevisionEnvelope,
    provider: Any,
    configured_ceiling: int,
) -> dict[str, Any]:
    audit_start = len(provider.audit_receipts)
    progress: dict[str, list[Any]] = {"cards": [], "call_records": []}
    try:
        if arm in ONE_SHOT_ARMS:
            final_card = v041._execute_one_shot(
                arm=arm,
                case=case,
                context=context,
                provider=provider,
                progress=progress,
            )
        elif arm in STAGED_ARMS:
            final_card = v041._execute_staged(
                arm=arm,
                case=case,
                context=context,
                provider=provider,
                progress=progress,
            )
        else:
            raise ValueError("unknown aperture-control arm")
    except Exception as error:
        receipts = v041._arm_receipts(provider, audit_start)
        terminal_local = isinstance(error, LocalContractViolation)
        return {
            "arm": arm,
            "status": "failed",
            "primary_endpoint_assessed": terminal_local,
            "terminal_outcome": (
                "terminal_local_contract_rejection"
                if terminal_local
                else "incomplete_error"
            ),
            "failure_category": _failure_category(error),
            "failure_reason_code": _failure_reason_code(error),
            "failure_sequence_offset": len(progress["call_records"]),
            "failure_request_fingerprint": (
                error.request_fingerprint
                if isinstance(error, LocalContractViolation)
                else None
            ),
            "configured_output_token_ceiling": configured_ceiling,
            "expected_api_calls": v041._expected_calls(arm, case),
            "final_card": None,
            "cards": progress["cards"],
            "call_records": progress["call_records"],
            "receipts": receipts,
            "accounting": v041._accounting(receipts),
        }
    receipts = v041._arm_receipts(provider, audit_start)
    return {
        "arm": arm,
        "status": "completed",
        "primary_endpoint_assessed": True,
        "terminal_outcome": "accepted_output",
        "failure_category": None,
        "failure_reason_code": None,
        "failure_sequence_offset": None,
        "failure_request_fingerprint": None,
        "configured_output_token_ceiling": configured_ceiling,
        "expected_api_calls": v041._expected_calls(arm, case),
        "final_card": final_card.to_dict(),
        "cards": progress["cards"],
        "call_records": progress["call_records"],
        "receipts": receipts,
        "accounting": v041._accounting(receipts),
    }


v041._run_one_arm = _run_one_arm


def execute_suite(**kwargs: Any) -> dict[str, Any]:
    result = v041.execute_suite(**kwargs)
    result["schema_version"] = SCHEMA_VERSION
    for run in result["runs"]:
        run["all_outputs_completed"] = all(
            run["arms"][arm]["status"] == "completed" for arm in ARMS
        )
        run["primary_endpoint_assessed"] = all(
            bool(run["arms"][arm]["primary_endpoint_assessed"]) for arm in ARMS
        )
        # In v0.4.2, complete means every primary endpoint reached a predeclared
        # assessable terminal outcome; all_outputs_completed remains separate.
        run["complete"] = run["primary_endpoint_assessed"]
    result["execution_complete"] = all(
        bool(run["primary_endpoint_assessed"]) for run in result["runs"]
    )
    result["all_outputs_completed"] = all(
        bool(run["all_outputs_completed"]) for run in result["runs"]
    )
    return result


def _unavailable_grade(*, primary_endpoint_assessed: bool) -> dict[str, Any]:
    return {
        "available": False,
        "primary_endpoint_assessed": primary_endpoint_assessed,
        "machine_success": False,
        "evidence_consistent": False,
        "checks": None,
        "support_evidence_ids": [],
        "unexpected_support_evidence_ids": [],
        "missing_required_evidence_ids": [],
        "citation_precision": None,
        "citation_recall": None,
    }


def grade_executions(
    result: dict[str, Any],
    gold: Mapping[str, Mapping[str, Any]],
) -> None:
    """Attach gold after execution and adjudicate locked terminal failures."""

    for run in result["runs"]:
        case_gold = gold[run["case_id"]]
        for arm in ARMS:
            payload = run["arms"][arm]
            if payload["status"] == "completed":
                payload["grade"] = {
                    "available": True,
                    "primary_endpoint_assessed": True,
                    **v041.grade_card(payload["final_card"], case_gold),
                }
            else:
                payload["grade"] = _unavailable_grade(
                    primary_endpoint_assessed=bool(payload["primary_endpoint_assessed"])
                )
        run["primary_endpoint_assessed"] = all(
            bool(run["arms"][arm]["grade"]["primary_endpoint_assessed"]) for arm in ARMS
        )
        run["complete"] = run["primary_endpoint_assessed"]
        if not run["primary_endpoint_assessed"]:
            run["contrast_outcomes"] = {
                "revision_envelope": "incomplete",
                "raw_aperture": "incomplete",
            }
            continue
        success = {
            arm: bool(run["arms"][arm]["grade"]["machine_success"]) for arm in ARMS
        }
        run["contrast_outcomes"] = {
            "revision_envelope": v041._binary_outcome(
                success["direct_raw_no_revision"],
                success["direct_raw_fixed_revision_rerun"],
                first_only="no_revision_only",
                second_only="fixed_revision_only",
            ),
            "raw_aperture": v041._binary_outcome(
                success["staged_card_only_rerun"],
                success["staged_cumulative_raw"],
                first_only="card_only_only",
                second_only="cumulative_raw_only",
            ),
        }


def _decide_causes(
    *,
    stable: Mapping[str, Mapping[str, int]],
    stable_contrast_counts: Mapping[str, Mapping[str, int]],
    locked_case_count: int,
    locked_decision_ready: bool,
    historical_reference: Mapping[str, Any],
) -> dict[str, Any]:
    no_revision = stable["direct_raw_no_revision"]["pass_cases"]
    fixed = stable["direct_raw_fixed_revision_rerun"]["pass_cases"]
    card_only = stable["staged_card_only_rerun"]["pass_cases"]
    cumulative = stable["staged_cumulative_raw"]["pass_cases"]
    revision_counts = stable_contrast_counts["revision_envelope"]
    aperture_counts = stable_contrast_counts["raw_aperture"]

    if not locked_decision_ready:
        revision_conclusion = "not_assessed_incomplete_or_subset_run"
        aperture_conclusion = "not_assessed_incomplete_or_subset_run"
        next_step = "complete_exact_locked_same_block_run"
    else:
        fixed_only = int(revision_counts["fixed_revision_only"])
        no_revision_only = int(revision_counts["no_revision_only"])
        if fixed_only > 0 and no_revision_only > 0:
            revision_conclusion = "revision_envelope_effect_mixed_by_case"
        elif fixed_only > 0:
            revision_conclusion = "revision_envelope_contributes_on_this_dev"
        elif no_revision_only > 0:
            # This directional harm check must precede the saturated no-revision
            # check. v0.4.1 omitted this exercised ordering branch.
            revision_conclusion = "no_revision_outperformed_fixed_on_this_dev"
        elif no_revision == fixed == locked_case_count:
            revision_conclusion = "revision_envelope_not_needed_on_this_saturated_dev"
        elif no_revision == fixed:
            revision_conclusion = "no_revision_envelope_effect_detected_below_ceiling"
        else:
            raise AssertionError("revision contrast counts and stable totals diverged")

        if (
            aperture_counts["card_only_only"] > 0
            and aperture_counts["cumulative_raw_only"] > 0
        ):
            aperture_conclusion = "raw_aperture_effect_mixed_by_case"
        elif (
            cumulative == locked_case_count
            and cumulative > card_only
            and aperture_counts["card_only_only"] == 0
        ):
            aperture_conclusion = "raw_aperture_rescue_candidate_on_this_dev"
        elif cumulative > card_only:
            aperture_conclusion = "partial_raw_aperture_rescue_on_this_dev"
        elif cumulative == card_only == locked_case_count:
            aperture_conclusion = "staged_ceiling_add_fresh_harder_dev"
        else:
            aperture_conclusion = "retained_raw_not_sufficient_under_this_protocol"

        if aperture_conclusion == "raw_aperture_rescue_candidate_on_this_dev":
            next_step = "test_staged_cumulative_raw_on_fresh_harder_holdout"
        elif aperture_conclusion == "partial_raw_aperture_rescue_on_this_dev":
            next_step = "stratify_partial_rescue_then_build_fresh_harder_dev"
        elif (
            revision_conclusion == "revision_envelope_not_needed_on_this_saturated_dev"
        ):
            next_step = "use_one_shot_raw_no_revision_as_primary_scaffold_control"
        elif fixed == locked_case_count:
            next_step = "use_one_shot_fixed_revision_as_primary_scaffold_control"
        else:
            next_step = "add_fresh_harder_dev_before_architecture_choice"

    historical_direct = int(
        historical_reference["direct_raw_fixed_revision_stable_pass_cases"]
    )
    historical_full = int(historical_reference["full_restart_stable_pass_cases"])
    return {
        "decision_ready": locked_decision_ready,
        "revision_envelope_conclusion": revision_conclusion,
        "raw_aperture_conclusion": aperture_conclusion,
        "next_scaffold_step": next_step,
        "selective_replay_status": "paused_no_same_block_rank",
        "stable_pass_counts": {
            "direct_raw_no_revision": no_revision,
            "direct_raw_fixed_revision_rerun": fixed,
            "staged_card_only_rerun": card_only,
            "staged_cumulative_raw": cumulative,
        },
        "historical_replication_context": {
            "direct_fixed_pr6_stable_pass_cases": historical_direct,
            "direct_fixed_same_block_stable_pass_cases": fixed,
            "direct_fixed_ceiling_replication": fixed == historical_direct,
            "pr6_full_stable_pass_cases": historical_full,
            "new_card_only_stable_pass_cases": card_only,
            "card_only_count_matches_historical": card_only == historical_full,
            "card_only_interface_is_not_exact_pr6_full": True,
        },
        "terminal_local_contract_policy": (
            "adjudicated_strict_failure_not_missing_data"
        ),
        "claim": "mechanism_candidate_on_contaminated_dev_not_general_reasoning_improvement",
    }


v041._decide_causes = _decide_causes


def summarize_runs(
    runs: Sequence[Mapping[str, Any]],
    *,
    locked_case_ids: Sequence[str],
    locked_trials: int,
    historical_reference: Mapping[str, Any],
    receipts_validated: bool = False,
) -> dict[str, Any]:
    """Summarize valid cards and adjudicated terminal failures separately."""

    summary = v041.summarize_runs(
        runs,
        locked_case_ids=locked_case_ids,
        locked_trials=locked_trials,
        historical_reference=historical_reference,
        receipts_validated=receipts_validated,
    )
    by_case: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for run in runs:
        by_case[str(run["case_id"])].append(run)

    expected_trial_ids = set(range(locked_trials))
    for row in summary["case_level"]:
        case_runs = by_case[str(row["case_id"])]
        endpoint_assessed = (
            len(case_runs) == locked_trials
            and {int(run["trial_index"]) for run in case_runs} == expected_trial_ids
            and all(
                bool(run["arms"][arm]["primary_endpoint_assessed"])
                for run in case_runs
                for arm in ARMS
            )
        )
        row["primary_endpoint_assessed"] = endpoint_assessed
        row["stable_assessed"] = endpoint_assessed
        if not endpoint_assessed:
            for arm in ARMS:
                row[f"{arm}_stable_pass"] = None
                row[f"{arm}_stable_answer_exact"] = None
            row["revision_envelope_stable_outcome"] = "not_assessed"
            row["raw_aperture_stable_outcome"] = "not_assessed"

    stable = {
        arm: {
            "pass_cases": sum(
                row[f"{arm}_stable_pass"] is True for row in summary["case_level"]
            ),
            "answer_exact_cases": sum(
                row[f"{arm}_stable_answer_exact"] is True
                for row in summary["case_level"]
            ),
        }
        for arm in ARMS
    }
    stable_contrast_counts = {
        "revision_envelope": {
            name: sum(
                row["revision_envelope_stable_outcome"] == name
                for row in summary["case_level"]
            )
            for name in (
                "no_revision_only",
                "fixed_revision_only",
                "both",
                "neither",
                "not_assessed",
            )
        },
        "raw_aperture": {
            name: sum(
                row["raw_aperture_stable_outcome"] == name
                for row in summary["case_level"]
            )
            for name in (
                "card_only_only",
                "cumulative_raw_only",
                "both",
                "neither",
                "not_assessed",
            )
        },
    }
    exact_locked_coverage = set(by_case) == set(locked_case_ids) and all(
        len(by_case[case_id]) == locked_trials
        and {int(run["trial_index"]) for run in by_case[case_id]} == expected_trial_ids
        for case_id in locked_case_ids
    )
    all_locked_primary_endpoints_assessed = exact_locked_coverage and all(
        bool(run["arms"][arm]["primary_endpoint_assessed"])
        for run in runs
        for arm in ARMS
    )
    all_locked_outputs_completed = exact_locked_coverage and all(
        run["arms"][arm]["status"] == "completed" for run in runs for arm in ARMS
    )
    locked_decision_ready = all_locked_primary_endpoints_assessed and receipts_validated

    for arm in ARMS:
        payloads = [run["arms"][arm] for run in runs]
        valid_outputs = [item for item in payloads if item["status"] == "completed"]
        terminal_rejections = [
            item
            for item in payloads
            if item["terminal_outcome"] == "terminal_local_contract_rejection"
        ]
        assessed = [
            item for item in payloads if bool(item["primary_endpoint_assessed"])
        ]
        item = summary["arm_summary"][arm]
        item["completed_outputs"] = len(valid_outputs)
        item["terminal_local_contract_rejections"] = len(terminal_rejections)
        item["primary_endpoint_assessed_outputs"] = len(assessed)
        item["non_assessable_outputs"] = len(payloads) - len(assessed)
        item["strict_failures"] = len(assessed) - int(item["machine_successes"])
        item["failure_reason_code_counts"] = {
            code: sum(
                payload.get("failure_reason_code") == code for payload in payloads
            )
            for code in LOCAL_CONTRACT_REASON_CODES
            if any(payload.get("failure_reason_code") == code for payload in payloads)
        }

    summary.update(
        {
            "completed_four_arm_runs": sum(
                bool(run["all_outputs_completed"]) for run in runs
            ),
            "assessed_four_arm_runs": sum(
                bool(run["primary_endpoint_assessed"]) for run in runs
            ),
            "stable_case_summary": stable,
            "stable_contrast_outcomes": stable_contrast_counts,
            "exact_locked_case_trial_coverage": exact_locked_coverage,
            "all_locked_runs_complete": all_locked_primary_endpoints_assessed,
            "all_locked_primary_endpoints_assessed": (
                all_locked_primary_endpoints_assessed
            ),
            "all_locked_outputs_completed": all_locked_outputs_completed,
            "live_receipts_validated": receipts_validated,
            "locked_decision_ready": locked_decision_ready,
            "cause_decision": _decide_causes(
                stable=stable,
                stable_contrast_counts=stable_contrast_counts,
                locked_case_count=len(locked_case_ids),
                locked_decision_ready=locked_decision_ready,
                historical_reference=historical_reference,
            ),
        }
    )
    return summary


def _validate_terminal_arm_payload(
    payload: Mapping[str, Any],
    *,
    arm: str,
    allowed_reason_codes: set[str],
    expected_evidence_ids: Sequence[str],
) -> None:
    receipts = payload["receipts"]
    records = payload["call_records"]
    if payload["status"] == "completed":
        if payload["terminal_outcome"] != "accepted_output":
            raise RuntimeError("completed arm terminal outcome drifted")
        if payload["primary_endpoint_assessed"] is not True:
            raise RuntimeError("completed arm endpoint became unassessed")
        if payload.get("failure_reason_code") is not None:
            raise RuntimeError("completed arm has a failure reason code")
        if payload.get("failure_request_fingerprint") is not None:
            raise RuntimeError("completed arm has a failure request fingerprint")
        return

    if payload["terminal_outcome"] == "terminal_local_contract_rejection":
        reason_code = payload.get("failure_reason_code")
        if reason_code not in allowed_reason_codes:
            raise RuntimeError(
                "terminal local rejection reason code is not allowlisted"
            )
        if payload.get("failure_category") != "local_contract_error":
            raise RuntimeError("terminal local rejection category drifted")
        if payload.get("primary_endpoint_assessed") is not True:
            raise RuntimeError("terminal local rejection became unassessed")
        if payload.get("final_card") is not None:
            raise RuntimeError("rejected card was persisted")
        if not receipts or len(records) != len(receipts) - 1:
            raise RuntimeError("terminal rejection receipt boundary drifted")
        expected_calls = int(payload["expected_api_calls"])
        contract_expected_calls = (
            1 if arm in ONE_SHOT_ARMS else len(expected_evidence_ids)
        )
        if expected_calls != contract_expected_calls:
            raise RuntimeError("terminal rejection expected-call contract drifted")
        if len(receipts) > expected_calls or len(records) >= expected_calls:
            raise RuntimeError("terminal rejection exceeded its call geometry")
        if int(payload.get("failure_sequence_offset", -1)) != len(records):
            raise RuntimeError("terminal rejection sequence offset drifted")
        if [int(record["sequence_offset"]) for record in records] != list(
            range(len(records))
        ):
            raise RuntimeError("terminal rejection call-record sequence drifted")
        if arm in STAGED_ARMS:
            observed_ids = [record["current_evidence_id"] for record in records]
            if observed_ids != list(expected_evidence_ids[: len(records)]):
                raise RuntimeError("terminal rejection evidence prefix drifted")
            if any(record["phase"] != v041._arm_phase(arm) for record in records):
                raise RuntimeError("terminal rejection staged phase drifted")
        elif records:
            raise RuntimeError("terminal one-shot rejection persisted a call record")
        final_receipt = receipts[-1]
        if final_receipt["metadata"]["attempt_outcome"] != "completed":
            raise RuntimeError("terminal rejection lacks a completed final receipt")
        if final_receipt["usage"]["exact_provider_tokens"] is not True:
            raise RuntimeError("terminal rejection lacks exact final-call usage")
        failure_request_fingerprint = payload.get("failure_request_fingerprint")
        if (
            failure_request_fingerprint is None
            or final_receipt["request_fingerprint"] != failure_request_fingerprint
        ):
            raise RuntimeError("terminal rejection request/receipt fingerprint drifted")
        return

    if payload.get("primary_endpoint_assessed") is not False:
        raise RuntimeError("non-adjudicated failure became endpoint-assessed")


def validate_live_receipts(
    result: Mapping[str, Any],
    lock: Mapping[str, Any],
    *,
    audit_receipts_by_arm: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    check = v041.validate_live_receipts(
        result,
        lock,
        audit_receipts_by_arm=audit_receipts_by_arm,
    )
    allowed = set(lock["v0_4_2_overlay"]["local_contract_reason_codes"])
    for run in result["runs"]:
        expected_evidence_ids = [
            *(item["evidence_id"] for item in run["case"]["initial_evidence"]),
            run["case"]["late_evidence"]["evidence_id"],
        ]
        for arm in ARMS:
            payload = run["arms"][arm]
            _validate_terminal_arm_payload(
                payload,
                arm=arm,
                allowed_reason_codes=allowed,
                expected_evidence_ids=expected_evidence_ids,
            )
            recomputed_accounting = v041._accounting(payload["receipts"])
            if v041.canonical_json(payload["accounting"]) != v041.canonical_json(
                recomputed_accounting
            ):
                raise RuntimeError(f"{arm} accounting does not match stored receipts")
        expected_assessed = all(
            bool(run["arms"][arm]["primary_endpoint_assessed"]) for arm in ARMS
        )
        if bool(run["primary_endpoint_assessed"]) != expected_assessed:
            raise RuntimeError("run endpoint-assessment flag drifted")

    attempted_calls = sum(
        len(run["arms"][arm]["receipts"]) for run in result["runs"] for arm in ARMS
    )
    nominal_calls = len(result["runs"]) * LOCKED_CALLS_PER_CASE_TRIAL
    non_assessable_failures = sum(
        not bool(run["arms"][arm]["primary_endpoint_assessed"])
        for run in result["runs"]
        for arm in ARMS
    )
    terminal_rejections = sum(
        run["arms"][arm]["terminal_outcome"] == "terminal_local_contract_rejection"
        for run in result["runs"]
        for arm in ARMS
    )
    overlay = lock["v0_4_2_overlay"]
    contract_preset = overlay["execution_presets"]["live_contract_smoke"]
    expected_contract_pairs = {
        (str(case_id), trial_index)
        for case_id in contract_preset["case_ids"]
        for trial_index in range(int(contract_preset["trials"]))
    }
    actual_contract_pairs = [
        (str(run["case_id"]), int(run["trial_index"])) for run in result["runs"]
    ]
    expected_run_ids = {
        f"openai_live_contract_smoke:{trial_index}:{case_id}"
        for case_id, trial_index in expected_contract_pairs
    }
    contract_smoke_exact = (
        result["mode"] == "openai_live_contract_smoke"
        and int(result["trials"]) == int(contract_preset["trials"])
        and tuple(result["case_ids"]) == tuple(contract_preset["case_ids"])
        and len(actual_contract_pairs) == len(expected_contract_pairs)
        and set(actual_contract_pairs) == expected_contract_pairs
        and {str(run["run_id"]) for run in result["runs"]} == expected_run_ids
        and all(
            run["mode"] == "openai_live_contract_smoke"
            and run["case"]["case_id"] == run["case_id"]
            for run in result["runs"]
        )
    )
    check.update(
        {
            "nominal_api_calls": nominal_calls,
            "attempted_api_calls": attempted_calls,
            "terminal_local_contract_rejections": terminal_rejections,
            "non_assessable_failures": non_assessable_failures,
            "terminal_policy_validated": True,
            "contract_smoke_exact_coverage": contract_smoke_exact,
            "full_run_launch_ready": bool(
                contract_smoke_exact
                and check["validated"]
                and non_assessable_failures == 0
                and all(
                    bool(run["primary_endpoint_assessed"]) for run in result["runs"]
                )
            ),
        }
    )
    return check


def _arm_rows(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = v041._arm_rows(result)
    payloads = [run["arms"][arm] for run in result["runs"] for arm in ARMS]
    if len(rows) != len(payloads):
        raise AssertionError("arm-row projection geometry drifted")
    for row, payload in zip(rows, payloads, strict=True):
        row.update(
            {
                "primary_endpoint_assessed": payload["primary_endpoint_assessed"],
                "terminal_outcome": payload["terminal_outcome"],
                "failure_reason_code": payload.get("failure_reason_code"),
                "failure_sequence_offset": payload.get("failure_sequence_offset"),
                "failure_request_fingerprint": payload.get(
                    "failure_request_fingerprint"
                ),
            }
        )
    return rows


def _report_markdown(result: Mapping[str, Any]) -> str:
    summary = result["summary"]
    cause = summary["cause_decision"]
    receipt = summary.get("live_receipt_validation", {})
    launch_gate = result.get("launch_gate")
    lines = [
        "# EBRT v0.4.2 diagnostic closure — DEV report",
        "",
        f"Mode: `{result['mode']}`  ",
        f"Four-arm runs: `{summary['runs']}`  ",
        "Primary-endpoint-assessed four-arm runs: "
        f"`{summary['assessed_four_arm_runs']}/{summary['runs']}`  ",
        "All-output-completed four-arm runs: "
        f"`{summary['completed_four_arm_runs']}/{summary['runs']}`  ",
        f"Locked decision ready: `{str(summary['locked_decision_ready']).lower()}`  ",
        f"Revision-envelope conclusion: `{cause['revision_envelope_conclusion']}`  ",
        f"Raw-aperture conclusion: `{cause['raw_aperture_conclusion']}`  ",
        f"Next scaffold step: `{cause['next_scaffold_step']}`  ",
        f"Nominal / attempted API calls: `{receipt.get('nominal_api_calls', 'n/a')}` / `{receipt.get('attempted_api_calls', 'n/a')}`  ",
        f"Full-run launch ready: `{str(bool(receipt.get('full_run_launch_ready'))).lower()}`",
    ]
    if launch_gate is not None:
        lines.extend(
            [
                f"Launch-gate smoke manifest: `{launch_gate['manifest_sha256']}`  ",
                "Launch-gate same-source revalidation: `true`",
            ]
        )
    lines.extend(
        [
            "",
            "A completed provider response rejected by one allowlisted local public-card",
            "rule is a terminal strict failure of the primary endpoint. It is not a",
            "valid final card and is not missing data. Provider, SDK, or internal failures",
            "remain non-assessable and keep the locked cause gate false.",
            "",
            "| Arm | Strict success / assessed | Valid outputs | Terminal local rejection | Non-assessable | API calls |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for arm in ARMS:
        item = summary["arm_summary"][arm]
        lines.append(
            "| {arm} | {success}/{assessed} | {completed} | {terminal} | {incomplete} | {calls} |".format(
                arm=arm,
                success=item["machine_successes"],
                assessed=item["primary_endpoint_assessed_outputs"],
                completed=item["completed_outputs"],
                terminal=item["terminal_local_contract_rejections"],
                incomplete=item["non_assessable_outputs"],
                calls=item["api_calls"],
            )
        )
    reason_rows = [
        (arm, code, count)
        for arm in ARMS
        for code, count in summary["arm_summary"][arm][
            "failure_reason_code_counts"
        ].items()
    ]
    lines.extend(["", "## Terminal local contract rejections", ""])
    if reason_rows:
        lines.extend(
            [
                "| Arm | Stable reason code | Count |",
                "| --- | --- | ---: |",
                *[
                    f"| {arm} | `{code}` | {count} |"
                    for arm, code, count in reason_rows
                ],
            ]
        )
    else:
        lines.append("None.")
    lines.extend(
        [
            "",
            "## Stable case outcomes",
            "",
            "A stable pass means at least two strict successes in the locked three",
            "trials. A terminal local contract rejection contributes one strict failure.",
            "Smoke and subset runs cannot produce a locked cause decision.",
            "",
            "| Case | No revision | Fixed revision | Card only | Cumulative raw | Envelope | Aperture |",
            "| --- | ---: | ---: | ---: | ---: | --- | --- |",
        ]
    )
    for row in summary["case_level"]:
        lines.append(
            "| {case} | {a}/{trials} | {b}/{trials} | {c}/{trials} | {d}/{trials} | {envelope} | {aperture} |".format(
                case=row["case_id"],
                trials=row["trials"],
                a=row["direct_raw_no_revision_successes"],
                b=row["direct_raw_fixed_revision_rerun_successes"],
                c=row["staged_card_only_rerun_successes"],
                d=row["staged_cumulative_raw_successes"],
                envelope=row["revision_envelope_stable_outcome"],
                aperture=row["raw_aperture_stable_outcome"],
            )
        )
    lines.extend(
        [
            "",
            "## Claim boundary",
            "",
            "This is a fresh run under a versioned local endpoint policy, not a",
            "retrospective reclassification of v0.4.1. The prompts, fixtures, model,",
            "arm order, and nominal budget remain inherited from the pinned v0.4.1",
            "protocol. This contaminated DEV calibration is not a holdout, promotion",
            "experiment, or proof of general reasoning improvement.",
            "",
        ]
    )
    return "\n".join(lines)


def write_bundle(
    result: Mapping[str, Any],
    output: Path,
    *,
    source_snapshot: Mapping[str, str],
) -> dict[str, Any]:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(
            f"refusing to overwrite nonempty output directory: {output}"
        )
    receipt_validation = result["summary"].get("live_receipt_validation", {})
    locked_decision_ready = bool(
        result["summary"]["locked_decision_ready"]
        and receipt_validation.get("validated") is True
        and receipt_validation.get("terminal_policy_validated") is True
    )
    output.mkdir(parents=True, exist_ok=True)
    v041._write_json(output / "results.json", result)
    v041._write_jsonl(output / "traces.jsonl", result["runs"])
    v041._write_jsonl(output / "calls.jsonl", v041._call_rows(result))
    v041._write_csv(output / "arm_rows.csv", _arm_rows(result))
    (output / "benchmark_report.md").write_text(
        _report_markdown(result), encoding="utf-8"
    )
    artifact_names = (
        "results.json",
        "traces.jsonl",
        "calls.jsonl",
        "arm_rows.csv",
        "benchmark_report.md",
    )
    execution_complete = bool(result["execution_complete"])
    manifest = {
        "schema_version": "ebrt-aperture-controls-manifest-v0.4.2",
        "status": (
            "COMPLETE_LOCKED_DEV"
            if locked_decision_ready
            else "COMPLETE_NON_DECISION_RUN"
            if execution_complete
            else "INCOMPLETE"
        ),
        "success_manifest": locked_decision_ready,
        "execution_complete": execution_complete,
        "all_outputs_completed": bool(result["all_outputs_completed"]),
        "locked_decision_ready": locked_decision_ready,
        "promotion_eligible": False,
        "mode": result["mode"],
        "source_sha256": dict(source_snapshot),
        "predecessor_runner_sha256": _sha256(PREDECESSOR_RUNNER_PATH),
        "predecessor_lock_sha256": _sha256(PREDECESSOR_LOCK_PATH),
        "predecessor_artifact_manifest_sha256": _sha256(PREDECESSOR_MANIFEST_PATH),
        "parent_manifest_sha256": _sha256(v041.PARENT_MANIFEST_PATH),
        "artifact_sha256": {name: _sha256(output / name) for name in artifact_names},
        "fixture_sha256": _sha256(v041.FIXTURE_PATH),
        "gold_sha256": _sha256(v041.GOLD_PATH),
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "endpoint_policy": (
            "terminal_local_contract_rejection_is_adjudicated_strict_failure"
        ),
        "nominal_api_calls": receipt_validation.get("nominal_api_calls"),
        "attempted_api_calls": receipt_validation.get("attempted_api_calls"),
        "terminal_local_contract_rejections": receipt_validation.get(
            "terminal_local_contract_rejections"
        ),
        "non_assessable_failures": receipt_validation.get("non_assessable_failures"),
        "full_run_launch_ready": bool(receipt_validation.get("full_run_launch_ready")),
        "launch_gate": result.get("launch_gate"),
        "cause_decision": dict(result["summary"]["cause_decision"]),
        "claim_boundary": {
            "contaminated_dev_only": True,
            "v0_4_1_reinterpreted": False,
            "provider_facing_protocol_changed": False,
            "terminal_local_contract_rejection_is_strict_failure": True,
            "observer_evaluated": False,
            "selective_replay_executed": False,
            "general_reasoning_improvement": False,
        },
    }
    v041._write_json(output / "manifest.json", manifest)
    return manifest


def _write_failure_bundle(
    output: Path,
    *,
    mode: str,
    source_snapshot: Mapping[str, str],
    audit_receipts_by_arm: Mapping[str, Sequence[Mapping[str, Any]]],
    error: BaseException,
) -> None:
    failure_path = output / "failure.json"
    if failure_path.exists():
        return
    output.mkdir(parents=True, exist_ok=True)
    value = {
        "schema_version": "ebrt-aperture-controls-failure-v0.4.2",
        "status": "INCOMPLETE",
        "success_manifest": False,
        "promotion_eligible": False,
        "mode": mode,
        "failure_category": _failure_category(error),
        "failure_reason_code": _failure_reason_code(error),
        "source_sha256": dict(source_snapshot),
        "predecessor_runner_sha256": _sha256(PREDECESSOR_RUNNER_PATH),
        "predecessor_lock_sha256": _sha256(PREDECESSOR_LOCK_PATH),
        "predecessor_artifact_manifest_sha256": _sha256(PREDECESSOR_MANIFEST_PATH),
        "parent_manifest_sha256": _sha256(v041.PARENT_MANIFEST_PATH),
        "audit_receipts_by_arm": {
            arm: [
                v041._sanitized_failure_receipt(item)
                for item in audit_receipts_by_arm.get(arm, ())
            ]
            for arm in ARMS
        },
        "sanitization": (
            "exception_message_rejected_card_raw_responses_headers_and_credentials_omitted"
        ),
    }
    v041._write_json(failure_path, value)


def _expect_reason(reason_code: str, action: Any) -> None:
    try:
        action()
    except LocalContractViolation as error:
        if error.reason_code != reason_code:
            raise AssertionError(
                f"expected {reason_code}, received {error.reason_code}"
            ) from error
        return
    raise AssertionError(f"expected local contract reason: {reason_code}")


class _RejectThirdMappingProvider(v041._ScriptedMappingProvider):
    def __init__(self, *, max_output_tokens: int, instructions: str) -> None:
        super().__init__(
            max_output_tokens=max_output_tokens,
            instructions=instructions,
        )
        self._case_call_index = 0

    def generate(self, input_payload: Mapping[str, Any]) -> CardResult:
        if input_payload.get("previous_public_card") is None:
            self._case_call_index = 0
        self._case_call_index += 1
        result = super().generate(input_payload)
        if self._case_call_index == 3:
            return CardResult(
                card=v041._replace_card(
                    result.card,
                    current_answer="SELF_TEST_OUTSIDE_ANSWER_CHOICES",
                ),
                receipt=result.receipt,
            )
        return result


class _InternalFailureMappingProvider(v041._ScriptedMappingProvider):
    def generate(self, input_payload: Mapping[str, Any]) -> CardResult:
        del input_payload
        raise AssertionError("SELF_TEST_INTERNAL_SENTINEL")


def _self_test_reason_codes(
    case: v041.CaseSpec,
    gold: Mapping[str, Any],
) -> None:
    context = v041._build_fixed_revision_envelope(case)
    payload = v041._one_shot_input(case, None)
    gold_card = v041._gold_final_card(case, gold)

    def validate(card: ReasoningCard, request: Mapping[str, Any] = payload) -> None:
        _validate_mapping_result(
            case,
            context,
            request,
            v041._fake_result(
                card,
                request,
                instructions=ONE_SHOT_INSTRUCTIONS,
            ),
            seen_raw_ids=case.evidence_ids,
        )

    observed: set[str] = set()

    def expect(code: str, action: Any) -> None:
        _expect_reason(code, action)
        observed.add(code)

    wrong_receipt = v041._fake_result(
        gold_card,
        {"wrong": "request"},
        instructions=ONE_SHOT_INSTRUCTIONS,
    )
    try:
        _validate_mapping_result(
            case,
            context,
            payload,
            wrong_receipt,
            seen_raw_ids=case.evidence_ids,
        )
    except ReceiptAuditViolation as error:
        if error.reason_code != "receipt_request_fingerprint_mismatch":
            raise AssertionError("receipt-audit reason code drifted") from error
    else:
        raise AssertionError("receipt/request mismatch became a model-card failure")
    expect(
        "checkpoint_id_mismatch",
        lambda: validate(v041._replace_card(gold_card, checkpoint_id="wrong")),
    )
    expect(
        "answer_choice_violation",
        lambda: validate(
            v041._replace_card(
                gold_card,
                current_answer="SELF_TEST_OUTSIDE_ANSWER_CHOICES",
            )
        ),
    )
    facts = [item.to_dict() for item in gold_card.decision_facts]
    expect(
        "duplicate_decision_slot",
        lambda: validate(
            v041._replace_card(gold_card, decision_facts=[*facts, facts[0]])
        ),
    )
    expect(
        "unknown_decision_slot",
        lambda: validate(
            v041._replace_card(
                gold_card,
                decision_facts=[
                    *facts,
                    {
                        "slot": "SELF_TEST_UNKNOWN_SLOT",
                        "value": "UNKNOWN",
                        "evidence_ids": [],
                    },
                ],
            )
        ),
    )
    disallowed = copy.deepcopy(facts)
    disallowed[0]["value"] = "SELF_TEST_DISALLOWED_VALUE"
    expect(
        "disallowed_decision_slot_value",
        lambda: validate(v041._replace_card(gold_card, decision_facts=disallowed)),
    )
    expect(
        "missing_required_decision_slot",
        lambda: validate(v041._replace_card(gold_card, decision_facts=facts[:-1])),
    )
    expect(
        "claim_character_bound_exceeded",
        lambda: validate(
            v041._replace_card(
                gold_card,
                claim="x" * (v041.MAX_PUBLIC_CLAIM_CHARACTERS + 1),
            )
        ),
    )
    expect(
        "topic_character_bound_exceeded",
        lambda: validate(
            v041._replace_card(
                gold_card,
                topic="x" * (v041.MAX_PUBLIC_TOPIC_CHARACTERS + 1),
            )
        ),
    )
    expect(
        "multiple_raw_chunks_copied",
        lambda: validate(
            v041._replace_card(
                gold_card,
                claim=(
                    f"{case.initial_evidence[0].text} {case.initial_evidence[1].text}"
                ),
            )
        ),
    )
    expect(
        "unavailable_evidence_citation",
        lambda: validate(
            v041._replace_card(
                gold_card,
                evidence_ids=[*gold_card.evidence_ids, "SELF_TEST_UNKNOWN_ID"],
            )
        ),
    )
    first_staged = v041._staged_input(
        case,
        context,
        previous_card=None,
        current_index=0,
        cumulative_raw=True,
    )
    future_id = case.initial_evidence[1].evidence_id
    first_staged["allowed_evidence_ids"].append(future_id)
    unseen_card = ReasoningCard(
        checkpoint_id=first_staged["checkpoint_id"],
        claim="Bounded unseen-support self-test.",
        topic="self_test",
        stance=0.0,
        confidence=0.5,
        evidence_ids=(future_id,),
        current_answer=case.answer_choices[0],
        revision_cue=0.0,
        decision_facts=tuple(
            DecisionFact(
                slot=item.slot_id,
                value="UNKNOWN",
                evidence_ids=(future_id,),
            )
            for item in case.decision_slots
            if item.required
        ),
        invalidated_evidence_ids=tuple(context.invalidated_evidence_ids),
    )
    expect(
        "unseen_active_support",
        lambda: _validate_mapping_result(
            case,
            context,
            first_staged,
            v041._fake_result(
                unseen_card,
                first_staged,
                instructions=STAGED_INSTRUCTIONS,
            ),
            seen_raw_ids=(case.initial_evidence[0].evidence_id,),
        ),
    )
    invalidated = context.invalidated_evidence_ids[0]
    expect(
        "invalidated_active_support",
        lambda: validate(
            v041._replace_card(
                gold_card,
                evidence_ids=[*gold_card.evidence_ids, invalidated],
            )
        ),
    )
    unexpected_invalidation = next(
        evidence_id
        for evidence_id in case.evidence_ids
        if evidence_id not in context.invalidated_evidence_ids
    )
    expect(
        "invented_invalidation",
        lambda: validate(
            v041._replace_card(
                gold_card,
                invalidated_evidence_ids=[
                    *gold_card.invalidated_evidence_ids,
                    unexpected_invalidation,
                ],
            )
        ),
    )
    if observed != set(LOCAL_CONTRACT_REASON_CODES):
        raise AssertionError("self-test did not exercise the full reason-code enum")


def _self_test_direction_order(lock: Mapping[str, Any]) -> None:
    stable = {
        arm: {"pass_cases": count, "answer_exact_cases": count}
        for arm, count in zip(ARMS, (10, 8, 1, 10), strict=True)
    }
    counts = {
        "revision_envelope": {
            "no_revision_only": 2,
            "fixed_revision_only": 0,
            "both": 8,
            "neither": 0,
            "not_assessed": 0,
        },
        "raw_aperture": {
            "card_only_only": 0,
            "cumulative_raw_only": 9,
            "both": 1,
            "neither": 0,
            "not_assessed": 0,
        },
    }
    value = _decide_causes(
        stable=stable,
        stable_contrast_counts=counts,
        locked_case_count=10,
        locked_decision_ready=True,
        historical_reference=lock["historical_reference_only"],
    )
    if value["revision_envelope_conclusion"] != (
        "no_revision_outperformed_fixed_on_this_dev"
    ):
        raise AssertionError("harmful revision-envelope direction was misclassified")


def _self_test_terminal_policy(
    case: v041.CaseSpec,
    gold: Mapping[str, Mapping[str, Any]],
    lock: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    card_cap = int(lock["live_provider"]["max_card_output_tokens"])
    direct_cap = len(case.all_evidence) * card_cap
    providers: dict[str, Any] = {
        arm: (
            _RejectThirdMappingProvider(
                max_output_tokens=card_cap,
                instructions=STAGED_INSTRUCTIONS,
            )
            if arm == "staged_card_only_rerun"
            else v041._ScriptedMappingProvider(
                max_output_tokens=(direct_cap if arm in ONE_SHOT_ARMS else card_cap),
                instructions=(
                    ONE_SHOT_INSTRUCTIONS
                    if arm in ONE_SHOT_ARMS
                    else STAGED_INSTRUCTIONS
                ),
            )
        )
        for arm in ARMS
    }
    result = execute_suite(
        cases=[case],
        providers=providers,
        max_card_output_tokens=card_cap,
        trials=1,
        mode="self_test_terminal_policy",
        provider_lock={"provider": "local_scripted_mapping"},
    )
    grade_executions(result, gold)
    rejected = result["runs"][0]["arms"]["staged_card_only_rerun"]
    if (
        rejected["terminal_outcome"] != "terminal_local_contract_rejection"
        or rejected["failure_reason_code"] != "answer_choice_violation"
        or rejected["failure_sequence_offset"] != 2
        or rejected["failure_request_fingerprint"]
        != rejected["receipts"][-1]["request_fingerprint"]
        or len(rejected["receipts"]) != 3
        or len(rejected["call_records"]) != 2
        or rejected["final_card"] is not None
        or rejected["grade"]["primary_endpoint_assessed"] is not True
        or rejected["grade"]["machine_success"] is not False
    ):
        raise AssertionError("terminal local rejection policy drifted")
    summary = summarize_runs(
        result["runs"],
        locked_case_ids=[case.case_id],
        locked_trials=1,
        historical_reference=lock["historical_reference_only"],
        receipts_validated=True,
    )
    if (
        not summary["locked_decision_ready"]
        or summary["all_locked_outputs_completed"]
        or summary["arm_summary"]["staged_card_only_rerun"][
            "terminal_local_contract_rejections"
        ]
        != 1
    ):
        raise AssertionError(
            "terminal rejection did not remain an assessed strict failure"
        )

    incomplete_providers = dict(providers)
    incomplete_providers["staged_card_only_rerun"] = _InternalFailureMappingProvider(
        max_output_tokens=card_cap,
        instructions=STAGED_INSTRUCTIONS,
    )
    incomplete = execute_suite(
        cases=[case],
        providers=incomplete_providers,
        max_card_output_tokens=card_cap,
        trials=1,
        mode="self_test_internal_failure",
        provider_lock={"provider": "local_scripted_mapping"},
    )
    grade_executions(incomplete, gold)
    incomplete_summary = summarize_runs(
        incomplete["runs"],
        locked_case_ids=[case.case_id],
        locked_trials=1,
        historical_reference=lock["historical_reference_only"],
        receipts_validated=True,
    )
    if (
        incomplete_summary["locked_decision_ready"]
        or incomplete["runs"][0]["arms"]["staged_card_only_rerun"][
            "primary_endpoint_assessed"
        ]
        is not False
    ):
        raise AssertionError("internal failure became endpoint-assessed")
    return result, summary


def _self_test_contract_smoke_gate(
    cases: Sequence[v041.CaseSpec],
    lock: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    card_cap = int(lock["live_provider"]["max_card_output_tokens"])
    direct_cap = len(cases[0].all_evidence) * card_cap
    providers: dict[str, Any] = {
        arm: (
            _RejectThirdMappingProvider(
                max_output_tokens=card_cap,
                instructions=STAGED_INSTRUCTIONS,
            )
            if arm == "staged_card_only_rerun"
            else v041._ScriptedMappingProvider(
                max_output_tokens=(direct_cap if arm in ONE_SHOT_ARMS else card_cap),
                instructions=(
                    ONE_SHOT_INSTRUCTIONS
                    if arm in ONE_SHOT_ARMS
                    else STAGED_INSTRUCTIONS
                ),
            )
        )
        for arm in ARMS
    }
    result = execute_suite(
        cases=cases,
        providers=providers,
        max_card_output_tokens=card_cap,
        trials=1,
        mode="openai_live_contract_smoke",
        provider_lock={"provider": "local_scripted_mapping"},
    )
    audit: dict[str, list[dict[str, Any]]] = {arm: [] for arm in ARMS}
    for run in result["runs"]:
        for arm in ARMS:
            payload = run["arms"][arm]
            cap = direct_cap if arm in ONE_SHOT_ARMS else card_cap
            prompt_hash = str(
                result["provider_provenance"][arm]["instructions_fingerprint"]
            )
            live_like = [
                v041._self_test_live_receipt(
                    request_fingerprint=str(receipt["request_fingerprint"]),
                    prompt_fingerprint=prompt_hash,
                    cap=cap,
                    lock=lock,
                )
                for receipt in payload["receipts"]
            ]
            payload["receipts"] = live_like
            for record, receipt in zip(
                payload["call_records"], live_like, strict=False
            ):
                record["receipt"] = receipt
            payload["accounting"] = v041._accounting(live_like)
            audit[arm].extend(live_like)
    check = validate_live_receipts(
        result,
        lock,
        audit_receipts_by_arm=audit,
    )
    if (
        not check["full_run_launch_ready"]
        or check["nominal_api_calls"] != 28
        or check["attempted_api_calls"] != 22
        or check["terminal_local_contract_rejections"] != 2
        or check["non_assessable_failures"] != 0
    ):
        raise AssertionError(f"contract-smoke terminal launch gate drifted: {check}")

    accounting_drift = copy.deepcopy(result)
    accounting_drift["runs"][0]["arms"][ARMS[0]]["accounting"]["api_calls"] = 999
    try:
        validate_live_receipts(
            accounting_drift,
            lock,
            audit_receipts_by_arm=audit,
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("receipt/accounting drift passed the live gate")

    rejection_fingerprint_drift = copy.deepcopy(result)
    rejected_payload = next(
        run["arms"]["staged_card_only_rerun"]
        for run in rejection_fingerprint_drift["runs"]
        if run["arms"]["staged_card_only_rerun"]["status"] == "failed"
    )
    rejected_payload["failure_request_fingerprint"] = "0" * 64
    try:
        validate_live_receipts(
            rejection_fingerprint_drift,
            lock,
            audit_receipts_by_arm=audit,
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("terminal rejection fingerprint drift passed the gate")

    terminal_prefix_drift = copy.deepcopy(result)
    prefix_payload = next(
        run["arms"]["staged_card_only_rerun"]
        for run in terminal_prefix_drift["runs"]
        if run["arms"]["staged_card_only_rerun"]["status"] == "failed"
    )
    prefix_payload["call_records"][1]["current_evidence_id"] = prefix_payload[
        "call_records"
    ][0]["current_evidence_id"]
    try:
        validate_live_receipts(
            terminal_prefix_drift,
            lock,
            audit_receipts_by_arm=audit,
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("terminal staged evidence-prefix drift passed the gate")

    coverage_drift = copy.deepcopy(result)
    coverage_drift["runs"][1]["case_id"] = coverage_drift["runs"][0]["case_id"]
    coverage_check = validate_live_receipts(
        coverage_drift,
        lock,
        audit_receipts_by_arm=audit,
    )
    if coverage_check["full_run_launch_ready"]:
        raise AssertionError("declared contract-smoke metadata hid run coverage drift")

    unknown = copy.deepcopy(result)
    rejected = next(
        run["arms"]["staged_card_only_rerun"]
        for run in unknown["runs"]
        if run["arms"]["staged_card_only_rerun"]["status"] == "failed"
    )
    rejected["failure_reason_code"] = "SELF_TEST_UNALLOWLISTED_REASON"
    unknown_audit = {
        arm: [
            receipt
            for run in unknown["runs"]
            for receipt in run["arms"][arm]["receipts"]
        ]
        for arm in ARMS
    }
    try:
        validate_live_receipts(
            unknown,
            lock,
            audit_receipts_by_arm=unknown_audit,
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("unallowlisted terminal reason passed receipt gate")
    return result, check


def run_self_tests() -> dict[str, Any]:
    source_snapshot = dict(BOOT_SOURCE_SNAPSHOT)
    _assert_source_snapshot(source_snapshot)
    predecessor_process = subprocess.run(
        [sys.executable, str(PREDECESSOR_RUNNER_PATH), "self-test"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    predecessor = json.loads(predecessor_process.stdout)
    if predecessor.get("status") != "ok":
        raise AssertionError("isolated v0.4.1 predecessor self-test did not pass")
    v041._validate_parent_manifest()
    lock = _load_lock()
    cases, gold = v041._load_suite()
    sample = cases[0]
    _self_test_reason_codes(sample, gold[sample.case_id])
    _self_test_direction_order(lock)
    terminal_result, terminal_summary = _self_test_terminal_policy(
        sample,
        gold,
        lock,
    )
    contract_case_ids = lock["fixtures"]["contract_smoke_case_ids"]
    contract_result, contract_check = _self_test_contract_smoke_gate(
        v041._select_cases(cases, contract_case_ids),
        lock,
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        terminal_result["summary"] = terminal_summary
        terminal_result["summary"]["live_receipt_validation"] = {
            "validated": True,
            "terminal_policy_validated": True,
            "nominal_api_calls": 14,
            "attempted_api_calls": 11,
            "terminal_local_contract_rejections": 1,
            "non_assessable_failures": 0,
            "full_run_launch_ready": False,
        }
        terminal_result["claim_boundary"] = list(lock["claim_boundary"])
        manifest = write_bundle(
            terminal_result,
            temp_root / "terminal_bundle",
            source_snapshot=source_snapshot,
        )
        if (
            manifest["schema_version"] != "ebrt-aperture-controls-manifest-v0.4.2"
            or not manifest["success_manifest"]
            or manifest["all_outputs_completed"]
        ):
            raise AssertionError("v0.4.2 terminal bundle manifest drifted")

        failure_dir = temp_root / "failure_bundle"
        _write_failure_bundle(
            failure_dir,
            mode="self_test",
            source_snapshot=source_snapshot,
            audit_receipts_by_arm={arm: () for arm in ARMS},
            error=RuntimeError("DO_NOT_SERIALIZE_THIS_SENTINEL"),
        )
        failure_text = (failure_dir / "failure.json").read_text(encoding="utf-8")
        if "DO_NOT_SERIALIZE_THIS_SENTINEL" in failure_text:
            raise AssertionError("v0.4.2 failure bundle serialized exception text")

        smoke_dir = temp_root / "contract_smoke_bundle"
        smoke_dir.mkdir()
        v041._write_json(smoke_dir / "results.json", contract_result)
        for name in (
            "traces.jsonl",
            "calls.jsonl",
            "arm_rows.csv",
            "benchmark_report.md",
        ):
            (smoke_dir / name).write_text("self-test\n", encoding="utf-8")
        artifact_names = (
            "results.json",
            "traces.jsonl",
            "calls.jsonl",
            "arm_rows.csv",
            "benchmark_report.md",
        )
        smoke_manifest = {
            "schema_version": "ebrt-aperture-controls-manifest-v0.4.2",
            "status": "COMPLETE_NON_DECISION_RUN",
            "success_manifest": False,
            "execution_complete": True,
            "locked_decision_ready": False,
            "promotion_eligible": False,
            "mode": "openai_live_contract_smoke",
            "source_sha256": dict(source_snapshot),
            "predecessor_runner_sha256": _sha256(PREDECESSOR_RUNNER_PATH),
            "predecessor_lock_sha256": _sha256(PREDECESSOR_LOCK_PATH),
            "artifact_sha256": {
                name: _sha256(smoke_dir / name) for name in artifact_names
            },
            "nominal_api_calls": contract_check["nominal_api_calls"],
            "attempted_api_calls": contract_check["attempted_api_calls"],
            "terminal_local_contract_rejections": contract_check[
                "terminal_local_contract_rejections"
            ],
            "non_assessable_failures": 0,
            "full_run_launch_ready": True,
        }
        v041._write_json(smoke_dir / "manifest.json", smoke_manifest)
        launch_gate = _validate_contract_smoke_manifest(
            smoke_dir / "manifest.json",
            source_snapshot=source_snapshot,
        )
        if launch_gate["manifest_sha256"] != _sha256(smoke_dir / "manifest.json"):
            raise AssertionError("contract-smoke launch receipt hash drifted")

    _assert_source_snapshot(source_snapshot)
    return {
        "status": "ok",
        "tests": int(predecessor["tests"]) + 10,
        "predecessor_tests": predecessor["tests"],
        "predecessor_execution": "isolated_subprocess",
        "local_contract_reason_codes": len(LOCAL_CONTRACT_REASON_CODES),
        "terminal_local_contract_rejection": "adjudicated_strict_failure",
        "provider_internal_failures": "not_assessed",
        "source_sha256": source_snapshot,
    }


def _validate_contract_smoke_manifest(
    manifest_path: Path,
    *,
    source_snapshot: Mapping[str, str],
) -> dict[str, Any]:
    """Verify a same-source exact contract smoke before any full-block call."""

    if not manifest_path.is_file():
        raise FileNotFoundError("contract-smoke manifest does not exist")
    manifest = v041._load_json(manifest_path)
    expected_manifest_fields = {
        "schema_version": "ebrt-aperture-controls-manifest-v0.4.2",
        "status": "COMPLETE_NON_DECISION_RUN",
        "success_manifest": False,
        "execution_complete": True,
        "locked_decision_ready": False,
        "promotion_eligible": False,
        "mode": "openai_live_contract_smoke",
        "full_run_launch_ready": True,
        "non_assessable_failures": 0,
        "nominal_api_calls": 28,
    }
    for key, expected in expected_manifest_fields.items():
        if manifest.get(key) != expected:
            raise RuntimeError(f"contract-smoke manifest field drifted: {key}")
    if manifest.get("source_sha256") != dict(source_snapshot):
        raise RuntimeError("contract-smoke source graph differs from live-dev source")
    if manifest.get("predecessor_runner_sha256") != _sha256(
        PREDECESSOR_RUNNER_PATH
    ) or manifest.get("predecessor_lock_sha256") != _sha256(PREDECESSOR_LOCK_PATH):
        raise RuntimeError("contract-smoke predecessor pin drifted")

    artifact_hashes = manifest.get("artifact_sha256")
    expected_artifacts = {
        "results.json",
        "traces.jsonl",
        "calls.jsonl",
        "arm_rows.csv",
        "benchmark_report.md",
    }
    if (
        not isinstance(artifact_hashes, dict)
        or set(artifact_hashes) != expected_artifacts
    ):
        raise RuntimeError("contract-smoke artifact set drifted")
    for name, expected_hash in artifact_hashes.items():
        if Path(name).name != name:
            raise RuntimeError("contract-smoke artifact name escaped its bundle")
        artifact_path = manifest_path.parent / name
        if not artifact_path.is_file() or _sha256(artifact_path) != expected_hash:
            raise RuntimeError(f"contract-smoke artifact hash drifted: {name}")
    if (manifest_path.parent / "failure.json").exists():
        raise RuntimeError("contract-smoke bundle contains a failure artifact")

    result = v041._load_json(manifest_path.parent / "results.json")
    if result.get("schema_version") != SCHEMA_VERSION:
        raise RuntimeError("contract-smoke result schema drifted")
    audit = {
        arm: [
            receipt
            for run in result["runs"]
            for receipt in run["arms"][arm]["receipts"]
        ]
        for arm in ARMS
    }
    receipt_check = validate_live_receipts(
        result,
        _load_lock(),
        audit_receipts_by_arm=audit,
    )
    if receipt_check["full_run_launch_ready"] is not True:
        raise RuntimeError("contract-smoke result does not pass the launch gate")
    for key in (
        "nominal_api_calls",
        "attempted_api_calls",
        "terminal_local_contract_rejections",
        "non_assessable_failures",
        "full_run_launch_ready",
    ):
        if manifest.get(key) != receipt_check.get(key):
            raise RuntimeError(f"contract-smoke manifest/result drifted: {key}")
    return {
        "schema_version": "ebrt-aperture-controls-launch-gate-v0.4.2",
        "manifest_sha256": _sha256(manifest_path),
        "bundle_name": manifest_path.parent.name,
        "mode": manifest["mode"],
        "full_run_launch_ready": True,
        "nominal_api_calls": receipt_check["nominal_api_calls"],
        "attempted_api_calls": receipt_check["attempted_api_calls"],
        "terminal_local_contract_rejections": receipt_check[
            "terminal_local_contract_rejections"
        ],
        "non_assessable_failures": 0,
    }


def _run_live(
    *,
    output: Path,
    case_ids: Sequence[str],
    trials: int,
    mode: str,
    contract_smoke_manifest: Path | None = None,
) -> dict[str, Any]:
    if not 1 <= trials <= 3:
        raise ValueError("live aperture-control trials must be between 1 and 3")
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        raise RuntimeError("OPENAI_API_KEY is not available in the process environment")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(
            f"refusing to overwrite nonempty output directory: {output}"
        )
    source_snapshot = dict(BOOT_SOURCE_SNAPSHOT)
    providers: dict[str, Any] = {}
    try:
        _assert_source_snapshot(source_snapshot)
        launch_gate = None
        if mode == "openai_live_dev_aperture_controls_v0_4_2":
            if contract_smoke_manifest is None:
                raise RuntimeError(
                    "live-dev requires a verified contract-smoke manifest"
                )
            launch_gate = _validate_contract_smoke_manifest(
                contract_smoke_manifest,
                source_snapshot=source_snapshot,
            )
        elif contract_smoke_manifest is not None:
            raise RuntimeError("contract-smoke manifest is only valid for live-dev")
        v041._validate_parent_manifest()
        lock = _load_lock()
        cases, gold = v041._load_suite()
        selected = v041._select_cases(cases, case_ids)
        if not selected:
            raise ValueError("at least one live case is required")
        if mode == "openai_live_dev_aperture_controls_v0_4_2" and (
            tuple(case_ids) != tuple(case.case_id for case in cases)
            or trials != LOCKED_TRIALS
        ):
            raise RuntimeError(
                "live-dev must remain the exact locked ten-case three-trial block"
            )
        chunk_counts = {len(case.all_evidence) for case in selected}
        if len(chunk_counts) != 1:
            raise RuntimeError("one-shot cap requires equal evidence counts")
        live = lock["live_provider"]
        card_cap = int(live["max_card_output_tokens"])
        direct_cap = next(iter(chunk_counts)) * card_cap
        for arm in ARMS:
            providers[arm] = v041._make_openai_mapping_provider(
                model=live["model"],
                reasoning_effort=live["reasoning_effort"],
                timeout_seconds=float(live["timeout_seconds"]),
                max_output_tokens=(direct_cap if arm in ONE_SHOT_ARMS else card_cap),
                instructions=(
                    ONE_SHOT_INSTRUCTIONS
                    if arm in ONE_SHOT_ARMS
                    else STAGED_INSTRUCTIONS
                ),
            )
        provider_lock = {
            "provider": live["provider"],
            "api": live["api"],
            "model": live["model"],
            "reasoning_effort": live["reasoning_effort"],
            "service_tier": live["service_tier"],
            "store": live["store"],
            "previous_response_id": live["previous_response_id"],
            "truncation": live["truncation"],
            "sdk_retries": live["sdk_retries"],
        }
        result = execute_suite(
            cases=selected,
            providers=providers,
            max_card_output_tokens=card_cap,
            trials=trials,
            mode=mode,
            provider_lock=provider_lock,
        )
        grade_executions(result, gold)
        result["launch_gate"] = launch_gate
        receipt_validation = validate_live_receipts(
            result,
            lock,
            audit_receipts_by_arm={arm: providers[arm].audit_receipts for arm in ARMS},
        )
        result["summary"] = summarize_runs(
            result["runs"],
            locked_case_ids=[case.case_id for case in cases],
            locked_trials=LOCKED_TRIALS,
            historical_reference=lock["historical_reference_only"],
            receipts_validated=bool(receipt_validation["validated"]),
        )
        result["summary"]["live_receipt_validation"] = receipt_validation
        result["claim_boundary"] = list(lock["claim_boundary"])
        _assert_source_snapshot(source_snapshot)
        manifest = write_bundle(result, output, source_snapshot=source_snapshot)
    except Exception as error:
        _write_failure_bundle(
            output,
            mode=mode,
            source_snapshot=source_snapshot,
            audit_receipts_by_arm={
                arm: providers[arm].audit_receipts for arm in providers
            },
            error=error,
        )
        raise
    return {
        "output": str(output),
        "summary": result["summary"],
        "manifest": manifest,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "self-test",
        help="run offline predecessor, reason-code, terminal-policy, and gate tests",
    )
    smoke = subparsers.add_parser(
        "live-smoke",
        help="run the fixed route/no-op two-case one-trial smoke",
    )
    smoke.add_argument("--output", type=Path, default=DEFAULT_SMOKE_OUTPUT)
    contract = subparsers.add_parser(
        "live-contract-smoke",
        help="run the fixed prior-failure two-case one-trial diagnostic smoke",
    )
    contract.add_argument("--output", type=Path, default=DEFAULT_CONTRACT_SMOKE_OUTPUT)
    subset = subparsers.add_parser(
        "live-subset",
        help="run an explicit non-decision DEV subset for diagnosis",
    )
    subset.add_argument("--output", type=Path, default=DEFAULT_SUBSET_OUTPUT)
    subset.add_argument("--trials", type=int, default=1)
    subset.add_argument("--case-id", action="append", dest="case_ids", required=True)
    dev = subparsers.add_parser(
        "live-dev",
        help="run the exact locked ten-case three-trial fresh DEV block",
    )
    dev.add_argument("--output", type=Path, default=DEFAULT_DEV_OUTPUT)
    dev.add_argument(
        "--contract-smoke-manifest",
        type=Path,
        required=True,
        help="manifest.json from the exact same-source passing contract smoke",
    )
    return parser


def _resolve_live_command(
    command: str,
    *,
    explicit_case_ids: Sequence[str] | None = None,
    explicit_trials: int | None = None,
) -> tuple[list[str], int, str]:
    lock = _load_lock()
    cases, _ = v041._load_suite()
    overlay = lock["v0_4_2_overlay"]
    if command == "live-smoke":
        preset = overlay["execution_presets"]["live_smoke"]
        return list(preset["case_ids"]), int(preset["trials"]), "openai_live_smoke"
    if command == "live-contract-smoke":
        preset = overlay["execution_presets"]["live_contract_smoke"]
        return (
            list(preset["case_ids"]),
            int(preset["trials"]),
            "openai_live_contract_smoke",
        )
    if command == "live-dev":
        return (
            [case.case_id for case in cases],
            LOCKED_TRIALS,
            "openai_live_dev_aperture_controls_v0_4_2",
        )
    if command == "live-subset":
        if not explicit_case_ids:
            raise ValueError("live-subset requires at least one explicit case ID")
        trials = 1 if explicit_trials is None else int(explicit_trials)
        if not 1 <= trials <= 3:
            raise ValueError("live-subset trials must be between one and three")
        v041._select_cases(cases, explicit_case_ids)
        return list(explicit_case_ids), trials, "openai_live_subset"
    raise ValueError("unknown live command")


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "self-test":
        value = run_self_tests()
    else:
        case_ids, trials, mode = _resolve_live_command(
            args.command,
            explicit_case_ids=getattr(args, "case_ids", None),
            explicit_trials=getattr(args, "trials", None),
        )
        value = _run_live(
            output=args.output,
            case_ids=case_ids,
            trials=trials,
            mode=mode,
            contract_smoke_manifest=getattr(args, "contract_smoke_manifest", None),
        )
    print(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
