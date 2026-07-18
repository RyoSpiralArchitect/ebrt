#!/usr/bin/env python3
"""Same-block four-arm aperture controls for EBRT v0.4.1.

The benchmark estimates two deliberately narrow effects under pair-shared
prompts:

* one-shot raw context with versus without a fixed revision envelope; and
* staged public-card execution with versus without the prior raw prefix.

It does not request or persist private chain-of-thought.  Provider inputs are
public evidence and public state only.  Gold is attached after every provider
call has completed, and every failed API attempt remains counted by receipt.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import inspect
import json
import math
import os
import platform
import statistics
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parent
PARENT_MANIFEST_PATH = (
    ROOT / "artifacts" / "benchmark_direct_full_calibration_v0_4_dev" / "manifest.json"
)
PR6_SOURCE_FILES = (
    "benchmark_direct_full_calibration_v0_4.py",
    "benchmark_language_replay_v0_4.py",
    "fixtures/language_replay_v0_4_dev.json",
    "fixtures/language_replay_v0_4_dev_gold.json",
    "language_replay_bridge_v0_4.py",
    "openai_reasoning_provider_v0_4.py",
    "policy_lock_direct_full_calibration_v0_4.json",
    "policy_lock_v0_4.json",
    "requirements-live.txt",
    "semantic_adapter_v0_2.py",
)
SOURCE_FILES = (
    "benchmark_aperture_controls_v0_4_1.py",
    "policy_lock_aperture_controls_v0_4_1.json",
    "artifacts/benchmark_direct_full_calibration_v0_4_dev/manifest.json",
    *PR6_SOURCE_FILES,
)
BOOT_SOURCE_SNAPSHOT = {
    name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    for name in SOURCE_FILES
}


from benchmark_direct_full_calibration_v0_4 import (  # noqa: E402
    FixedRevisionEnvelope,
    _build_fixed_revision_envelope,
    _card_from_payload,
    _failure_category,
    _load_suite,
    _receipt_from_dict,
    _rotated_cases,
    _select_cases,
)
from benchmark_language_replay_v0_4 import grade_card  # noqa: E402
from language_replay_bridge_v0_4 import (  # noqa: E402
    CardResult,
    CaseSpec,
    DecisionFact,
    ProviderReceipt,
    ProviderUsage,
    ReasoningCard,
    _aggregate_receipts,
    _public_support_ids,
    canonical_json,
    fingerprint,
)


SCHEMA_VERSION = "ebrt-aperture-controls-benchmark-v0.4.1"
ARMS = (
    "direct_raw_no_revision",
    "direct_raw_fixed_revision_rerun",
    "staged_card_only_rerun",
    "staged_cumulative_raw",
)
ONE_SHOT_ARMS = ARMS[:2]
STAGED_ARMS = ARMS[2:]
CONTRASTS = {
    "revision_envelope": ONE_SHOT_ARMS,
    "raw_aperture": STAGED_ARMS,
}
WILLIAMS_ROWS = (
    (ARMS[0], ARMS[1], ARMS[3], ARMS[2]),
    (ARMS[1], ARMS[2], ARMS[0], ARMS[3]),
    (ARMS[2], ARMS[3], ARMS[1], ARMS[0]),
    (ARMS[3], ARMS[0], ARMS[2], ARMS[1]),
)
LOCKED_TRIALS = 3
LOCKED_SMOKE_TRIALS = 1
LOCKED_CASE_COUNT = 10
LOCKED_EVIDENCE_CHUNKS = 6
LOCKED_CALLS_PER_CASE_TRIAL = 14
LOCKED_FULL_API_CALLS = 420
LOCKED_SMOKE_API_CALLS = 28
LOCKED_CANARY_CASE_IDS = ("route_code_supersession", "unrelated_noop")
MAX_PUBLIC_CLAIM_CHARACTERS = 256
MAX_PUBLIC_TOPIC_CHARACTERS = 64
MIN_GUARDED_RAW_CHARACTERS = 16
MAX_VERBATIM_RAW_CHUNK_MATCHES = 1
DIRECT_CHECKPOINT_ID = "direct:final"
LOCK_PATH = ROOT / "policy_lock_aperture_controls_v0_4_1.json"
FIXTURE_PATH = ROOT / "fixtures" / "language_replay_v0_4_dev.json"
GOLD_PATH = ROOT / "fixtures" / "language_replay_v0_4_dev_gold.json"
DEFAULT_SMOKE_OUTPUT = ROOT / "benchmark_results" / "v0_4_1_aperture_live_smoke"
DEFAULT_DEV_OUTPUT = ROOT / "benchmark_results" / "v0_4_1_aperture_dev"


ONE_SHOT_INSTRUCTIONS = """\
Produce one compact PUBLIC final decision-state card. Do not provide private
chain-of-thought, hidden reasoning, or a prose derivation. Use only the ordered
all_raw_evidence. revision_context is either null or a minimal fixed public
envelope. When it is populated, obey its invalidation roster. When it is null,
infer an invalidation only from an explicit correction, revocation, or
supersession in the raw evidence. Never invent evidence IDs or invalidations.
The current_answer must exactly equal one supplied answer choice. Invalidated
evidence must never be active support. Use every required decision slot exactly
once, copy each slot_id exactly, and choose only an exact allowed value; use
UNKNOWN when unsupported. Do not copy multiple raw evidence chunks into claim
or topic; summarize compactly and cite evidence IDs instead. Keep the public
facts externally checkable. Return only the strict structured output.
"""


STAGED_INSTRUCTIONS = """\
Produce one compact PUBLIC decision-state card. Do not provide private
chain-of-thought, hidden reasoning, or a prose derivation. Update the previous
public card using current_evidence and, when nonempty, retained_raw_evidence.
The retained list contains only prior raw chunks and current_evidence appears
separately exactly once. Use only supplied evidence IDs. Obey the minimal fixed
revision_context: invalidated evidence may be listed as invalidated but must
never be active support, and no additional invalidation may be invented. The
current_answer must exactly equal one supplied answer choice. Use every
required decision slot exactly once, copy each slot_id exactly, and choose only
an exact allowed value; use UNKNOWN when unsupported. Do not copy multiple raw
evidence chunks into claim or topic; summarize compactly and cite evidence IDs
instead. Keep the public facts externally checkable. Return only the strict
structured output.
"""


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_snapshot() -> dict[str, str]:
    return {name: _sha256(ROOT / name) for name in SOURCE_FILES}


def _assert_source_snapshot(expected: Mapping[str, str]) -> None:
    if dict(expected) != _source_snapshot():
        raise RuntimeError(
            "v0.4.1 aperture-control source graph changed during execution"
        )


def _validate_parent_manifest() -> dict[str, Any]:
    manifest = _load_json(PARENT_MANIFEST_PATH)
    if manifest.get("status") != "COMPLETE_LOCKED_DEV":
        raise RuntimeError("PR 6 parent artifact is no longer COMPLETE_LOCKED_DEV")
    if manifest.get("success_manifest") is not True:
        raise RuntimeError("PR 6 parent artifact is not a success manifest")
    source_hashes = manifest.get("source_sha256")
    if not isinstance(source_hashes, Mapping):
        raise RuntimeError("PR 6 parent manifest has no source hash map")
    if set(source_hashes) != set(PR6_SOURCE_FILES):
        raise RuntimeError("PR 6 parent manifest source graph drifted")
    for name in PR6_SOURCE_FILES:
        if str(source_hashes[name]) != _sha256(ROOT / name):
            raise RuntimeError(f"PR 6 pinned source hash mismatch: {name}")
    if manifest.get("fixture_sha256") != _sha256(FIXTURE_PATH):
        raise RuntimeError("PR 6 fixture hash mismatch")
    if manifest.get("gold_sha256") != _sha256(GOLD_PATH):
        raise RuntimeError("PR 6 gold hash mismatch")
    return manifest


def _load_lock() -> dict[str, Any]:
    lock = _load_json(LOCK_PATH)
    if lock.get("status") != "DEV_DRAFT" or lock.get("promotion_eligible") is not False:
        raise RuntimeError(
            "aperture-control lock must remain non-promotional DEV_DRAFT"
        )
    if tuple(lock.get("arms", ())) != ARMS:
        raise RuntimeError("aperture-control arm order drifted")
    observed_contrasts = {
        name: tuple(value) for name, value in lock.get("contrasts", {}).items()
    }
    if observed_contrasts != CONTRASTS:
        raise RuntimeError("aperture-control contrasts drifted")
    locked_rows = tuple(
        tuple(row) for row in lock["execution"].get("williams_rows", ())
    )
    if locked_rows != WILLIAMS_ROWS:
        raise RuntimeError("Williams arm-order rows drifted")
    execution = lock["execution"]
    expected_execution = {
        "trials": LOCKED_TRIALS,
        "smoke_trials": LOCKED_SMOKE_TRIALS,
        "expected_api_calls_per_case_trial": LOCKED_CALLS_PER_CASE_TRIAL,
        "expected_full_locked_api_calls": LOCKED_FULL_API_CALLS,
        "expected_two_case_smoke_api_calls": LOCKED_SMOKE_API_CALLS,
    }
    for name, expected in expected_execution.items():
        if execution.get(name) != expected:
            raise RuntimeError(f"decision-critical execution lock drifted: {name}")
    if execution.get("retry_policy") != ("no_retry_failed_attempts_remain_counted"):
        raise RuntimeError("execution retry policy drifted")
    live = lock["live_provider"]
    parent_live = _load_json(ROOT / "policy_lock_direct_full_calibration_v0_4.json")[
        "live_provider"
    ]
    for name in (
        "model",
        "reasoning_effort",
        "service_tier",
        "store",
        "previous_response_id",
        "truncation",
        "sdk_retries",
        "max_card_output_tokens",
        "timeout_seconds",
    ):
        if live[name] != parent_live[name]:
            raise RuntimeError(f"live-provider drift from PR 6 lock: {name}")
    if lock["budget_match"].get("padding") != "forbidden":
        raise RuntimeError("budget padding must remain forbidden")
    if (
        int(lock["budget_match"]["expected_ceiling_for_current_six_chunk_cases"])
        != 4608
    ):
        raise RuntimeError("locked nominal output ceiling drifted")
    if set(lock["revision_envelope"]["provider_fields"]) != {
        "late_evidence_id",
        "relevant",
        "revision_cue",
        "invalidated_evidence_ids",
    }:
        raise RuntimeError("fixed revision-envelope surface drifted")
    if lock["revision_envelope"].get("direct_raw_no_revision_delivery") is not None:
        raise RuntimeError("no-revision provider delivery must remain null")
    if lock["revision_envelope"].get("staged_temporal_semantics") != (
        "post_event_reconstruction_the_fixed_envelope_is_deliberately_available_"
        "from_the_first_rebuilt_chunk_not_online_event_discovery"
    ):
        raise RuntimeError("staged temporal semantics drifted")
    public_card_lock = lock["public_card_aperture"]
    if (
        int(public_card_lock.get("claim_max_characters", -1))
        != MAX_PUBLIC_CLAIM_CHARACTERS
        or int(public_card_lock.get("topic_max_characters", -1))
        != MAX_PUBLIC_TOPIC_CHARACTERS
        or int(public_card_lock.get("minimum_guarded_raw_characters", -1))
        != MIN_GUARDED_RAW_CHARACTERS
        or int(public_card_lock.get("maximum_verbatim_raw_chunk_matches", -1))
        != MAX_VERBATIM_RAW_CHUNK_MATCHES
        or public_card_lock.get("verbatim_raw_copy")
        != "at_most_one_full_seen_raw_chunk_in_claim_and_topic"
    ):
        raise RuntimeError("public-card aperture lock drifted")
    expected_calls = dict(zip(ARMS, (1, 1, 6, 6), strict=True))
    for arm, calls in expected_calls.items():
        contract = lock["arm_contracts"][arm]
        if int(contract.get("api_calls_per_case", -1)) != calls:
            raise RuntimeError(f"arm call geometry drifted: {arm}")
        expected_pair = "one_shot" if arm in ONE_SHOT_ARMS else "staged"
        if contract.get("shared_prompt_pair") != expected_pair:
            raise RuntimeError(f"arm shared-prompt pair drifted: {arm}")
    fixtures = lock["fixtures"]
    if (
        fixtures.get("input") != str(FIXTURE_PATH.relative_to(ROOT))
        or fixtures.get("gold") != str(GOLD_PATH.relative_to(ROOT))
        or int(fixtures.get("case_count", -1)) != LOCKED_CASE_COUNT
        or int(fixtures.get("evidence_chunks_per_case", -1)) != LOCKED_EVIDENCE_CHUNKS
        or tuple(fixtures.get("live_canary_case_ids", ())) != LOCKED_CANARY_CASE_IDS
    ):
        raise RuntimeError("decision-critical fixture lock drifted")
    grading = lock["grading"]
    if (
        grading.get("primary_endpoint") != "final_card_machine_success"
        or grading.get("primary_decision_unit")
        != "case_level_stable_pass_at_least_two_of_three_trials"
        or grading.get("gold_attachment") != "only_after_all_provider_calls_complete"
        or tuple(grading.get("machine_success_requires", ()))
        != (
            "answer_exact",
            "required_facts_exact",
            "stable_facts_exact",
            "required_evidence_present",
            "forbidden_support_absent",
            "expected_invalidated_evidence_marked",
        )
    ):
        raise RuntimeError("decision-critical grading lock drifted")
    historical = lock["historical_reference_only"]
    if (
        int(historical.get("direct_raw_fixed_revision_stable_pass_cases", -1))
        != LOCKED_CASE_COUNT
        or int(historical.get("full_restart_stable_pass_cases", -1)) != 1
    ):
        raise RuntimeError("PR 6 historical reference drifted")
    expected_cause_outputs = {
        "revision_envelope": {
            "not_assessed_incomplete_or_subset_run",
            "revision_envelope_effect_mixed_by_case",
            "revision_envelope_contributes_on_this_dev",
            "revision_envelope_not_needed_on_this_saturated_dev",
            "no_revision_envelope_effect_detected_below_ceiling",
            "no_revision_outperformed_fixed_on_this_dev",
        },
        "raw_aperture": {
            "not_assessed_incomplete_or_subset_run",
            "raw_aperture_effect_mixed_by_case",
            "raw_aperture_rescue_candidate_on_this_dev",
            "partial_raw_aperture_rescue_on_this_dev",
            "staged_ceiling_add_fresh_harder_dev",
            "retained_raw_not_sufficient_under_this_protocol",
        },
        "next_scaffold_step": {
            "complete_exact_locked_same_block_run",
            "test_staged_cumulative_raw_on_fresh_harder_holdout",
            "stratify_partial_rescue_then_build_fresh_harder_dev",
            "use_one_shot_raw_no_revision_as_primary_scaffold_control",
            "use_one_shot_fixed_revision_as_primary_scaffold_control",
            "add_fresh_harder_dev_before_architecture_choice",
        },
    }
    observed_cause_outputs = {
        name: set(values)
        for name, values in lock.get("cause_decision_outputs", {}).items()
    }
    if observed_cause_outputs != expected_cause_outputs:
        raise RuntimeError("cause-decision output lock drifted")
    expected_direction_rule = {
        "precondition": (
            "exact_locked_case_trial_coverage_all_arms_complete_and_"
            "live_receipts_validated"
        ),
        "revision_envelope": {
            "not_needed_on_this_dev": (
                "no_revision_stable_passes_all_cases_and_no_fixed_only_stable_case"
            ),
            "contributes_on_this_dev": "one_or_more_fixed_only_stable_cases",
            "mixed": "both_fixed_only_and_no_revision_only_stable_cases",
            "no_detected_effect": "equal_stable_case_outcomes_below_ceiling",
        },
        "raw_aperture": {
            "rescue_candidate": (
                "cumulative_raw_stable_passes_all_cases_no_card_only_stable_case_"
                "and_improves_stable_pass_count"
            ),
            "partial_rescue": (
                "cumulative_raw_improves_stable_pass_count_without_full_rescue"
            ),
            "mixed": "both_cumulative_only_and_card_only_stable_cases",
            "not_sufficient": "cumulative_raw_does_not_improve_stable_pass_count",
        },
        "selective_replay": "paused_no_same_block_rank",
        "fresh_harder_suite": "required_before_quality_or_generalization_claim",
    }
    if lock.get("direction_rule") != expected_direction_rule:
        raise RuntimeError("direction-rule lock drifted")
    if lock["source_integrity"]["parent_artifact_manifest"] != str(
        PARENT_MANIFEST_PATH.relative_to(ROOT)
    ):
        raise RuntimeError("parent artifact path drifted")
    return lock


def _envelope_dict(context: FixedRevisionEnvelope) -> dict[str, Any]:
    value = context.to_provider_dict(include_late_evidence=False)
    expected = {
        "late_evidence_id",
        "relevant",
        "revision_cue",
        "invalidated_evidence_ids",
    }
    if set(value) != expected:
        raise ValueError("fixed revision envelope is not minimal")
    return value


def _one_shot_input(
    case: CaseSpec,
    context: FixedRevisionEnvelope | None,
) -> dict[str, Any]:
    return {
        "question": case.question,
        "answer_choices": list(case.answer_choices),
        "decision_slots": [item.to_dict() for item in case.decision_slots],
        "checkpoint_id": DIRECT_CHECKPOINT_ID,
        "all_raw_evidence": [item.public_dict() for item in case.all_evidence],
        "revision_context": None if context is None else _envelope_dict(context),
        "allowed_evidence_ids": list(case.evidence_ids),
    }


def _staged_input(
    case: CaseSpec,
    context: FixedRevisionEnvelope,
    *,
    previous_card: ReasoningCard | None,
    current_index: int,
    cumulative_raw: bool,
) -> dict[str, Any]:
    evidence = case.all_evidence
    if not 0 <= current_index < len(evidence):
        raise IndexError("staged evidence index is out of range")
    current = evidence[current_index]
    prior = evidence[:current_index]
    if cumulative_raw:
        visible_order = [item.evidence_id for item in prior]
    else:
        visible_order = list(_public_support_ids(previous_card))
    if current.evidence_id not in visible_order:
        visible_order.append(current.evidence_id)
    for evidence_id in context.invalidated_evidence_ids:
        if evidence_id not in visible_order:
            visible_order.append(evidence_id)
    if not set(visible_order) <= set(case.evidence_ids):
        raise AssertionError("staged allowed evidence escaped the case boundary")
    if (
        current.evidence_id != case.late_evidence.evidence_id
        and case.late_evidence.evidence_id in visible_order
    ):
        raise AssertionError("late evidence became citable before raw presentation")
    return {
        "question": case.question,
        "answer_choices": list(case.answer_choices),
        "decision_slots": [item.to_dict() for item in case.decision_slots],
        "checkpoint_id": f"card:{current.evidence_id}",
        "previous_public_card": (
            None if previous_card is None else previous_card.to_dict()
        ),
        "retained_raw_evidence": (
            [item.public_dict() for item in prior] if cumulative_raw else []
        ),
        "current_evidence": current.public_dict(),
        "revision_context": _envelope_dict(context),
        "allowed_evidence_ids": visible_order,
    }


def _normalized_copy_text(value: str) -> str:
    return " ".join(str(value).casefold().split())


def _verbatim_raw_match_ids(
    case: CaseSpec,
    card: ReasoningCard,
    seen_raw_ids: Sequence[str],
) -> tuple[str, ...]:
    public_free_text = _normalized_copy_text(f"{card.claim} {card.topic}")
    seen = set(str(item) for item in seen_raw_ids)
    return tuple(
        chunk.evidence_id
        for chunk in case.all_evidence
        if chunk.evidence_id in seen
        and len(_normalized_copy_text(chunk.text)) >= MIN_GUARDED_RAW_CHARACTERS
        and _normalized_copy_text(chunk.text) in public_free_text
    )


def _validate_mapping_result(
    case: CaseSpec,
    context: FixedRevisionEnvelope,
    input_payload: Mapping[str, Any],
    result: CardResult,
    *,
    seen_raw_ids: Sequence[str],
) -> None:
    card = result.card
    if result.receipt.request_fingerprint != fingerprint(input_payload):
        raise ValueError("provider receipt/request fingerprint mismatch")
    if card.checkpoint_id != input_payload["checkpoint_id"]:
        raise ValueError("provider returned the wrong checkpoint_id")
    if card.current_answer not in case.answer_choices:
        raise ValueError("provider returned an answer outside answer_choices")
    slot_values = {
        item.slot_id: set(item.allowed_values) for item in case.decision_slots
    }
    required_slots = {item.slot_id for item in case.decision_slots if item.required}
    observed_slots: set[str] = set()
    for fact in card.decision_facts:
        if fact.slot in observed_slots:
            raise ValueError(f"provider returned duplicate decision slot: {fact.slot}")
        observed_slots.add(fact.slot)
        if fact.slot not in slot_values:
            raise ValueError(f"provider returned unknown decision slot: {fact.slot}")
        if fact.value not in slot_values[fact.slot]:
            raise ValueError(f"provider returned disallowed value: {fact.slot}")
    missing = required_slots - observed_slots
    if missing:
        raise ValueError(f"provider omitted required decision slots: {sorted(missing)}")
    if len(card.claim) > MAX_PUBLIC_CLAIM_CHARACTERS:
        raise ValueError("provider public claim exceeded the locked character bound")
    if len(card.topic) > MAX_PUBLIC_TOPIC_CHARACTERS:
        raise ValueError("provider public topic exceeded the locked character bound")
    seen = set(str(item) for item in seen_raw_ids)
    verbatim_matches = _verbatim_raw_match_ids(case, card, seen_raw_ids)
    if len(verbatim_matches) > MAX_VERBATIM_RAW_CHUNK_MATCHES:
        raise ValueError(
            "provider copied multiple raw chunks into public claim/topic: "
            f"{list(verbatim_matches)}"
        )
    allowed = set(str(item) for item in input_payload["allowed_evidence_ids"])
    if not seen <= set(case.evidence_ids):
        raise AssertionError("validator seen-raw boundary escaped the case")
    active_support = set(card.evidence_ids)
    cited = set(card.evidence_ids) | set(card.invalidated_evidence_ids)
    for fact in card.decision_facts:
        active_support.update(fact.evidence_ids)
        cited.update(fact.evidence_ids)
    unknown = cited - allowed
    if unknown:
        raise ValueError(
            f"provider cited unknown/unavailable evidence: {sorted(unknown)}"
        )
    unseen_active = active_support - seen
    if unseen_active:
        raise ValueError(
            f"provider actively cited unseen raw evidence: {sorted(unseen_active)}"
        )
    permitted_invalidated = set(context.invalidated_evidence_ids)
    stale = active_support & permitted_invalidated
    if stale:
        raise ValueError(f"provider used invalidated active support: {sorted(stale)}")
    unexpected = set(card.invalidated_evidence_ids) - permitted_invalidated
    if unexpected:
        raise ValueError(f"provider invented invalidations: {sorted(unexpected)}")


def _make_openai_mapping_provider(
    *,
    model: str,
    reasoning_effort: str,
    timeout_seconds: float,
    max_output_tokens: int,
    instructions: str,
) -> Any:
    from openai_reasoning_provider_v0_4 import (
        OpenAIResponseContractError,
        ReasoningCardPayload,
        _ResponsesClientBase,
    )

    class OpenAIMappingCardProvider(_ResponsesClientBase):
        def __init__(self) -> None:
            super().__init__(
                model=model,
                reasoning_effort=reasoning_effort,
                timeout_seconds=timeout_seconds,
            )
            self.max_output_tokens = int(max_output_tokens)
            if self.max_output_tokens <= 0:
                raise ValueError("max_output_tokens must be positive")

        @property
        def provenance(self) -> Mapping[str, Any]:
            return {
                "provider": "openai_responses",
                "model": self.model,
                "api": "responses.parse",
                "structured_output": "pydantic_v2",
                "reasoning_effort": self.reasoning_effort,
                "max_output_tokens": self.max_output_tokens,
                "instructions_fingerprint": fingerprint(instructions),
                "store": False,
                "previous_response_id": False,
                "service_tier": "default",
                "truncation": "disabled",
                "retries": 0,
                "sdk_version": self.sdk_version,
            }

        def generate(self, input_payload: Mapping[str, Any]) -> CardResult:
            payload, receipt = self._parse(
                input_payload=input_payload,
                instructions=instructions,
                text_format=ReasoningCardPayload,
                max_output_tokens=self.max_output_tokens,
            )
            if not isinstance(payload, ReasoningCardPayload):
                raise OpenAIResponseContractError(
                    "parsed aperture-control card has the wrong runtime type"
                )
            return CardResult(card=_card_from_payload(payload), receipt=receipt)

    return OpenAIMappingCardProvider()


def _accounting(receipts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return _aggregate_receipts([_receipt_from_dict(item) for item in receipts])


def _arm_receipts(provider: Any, start_index: int) -> list[dict[str, Any]]:
    return provider.audit_receipts[start_index:]


def _expected_calls(arm: str, case: CaseSpec) -> int:
    return 1 if arm in ONE_SHOT_ARMS else len(case.all_evidence)


def _arm_phase(arm: str) -> str:
    return {
        "direct_raw_no_revision": "one_shot_no_revision",
        "direct_raw_fixed_revision_rerun": "one_shot_fixed_revision_rerun",
        "staged_card_only_rerun": "staged_card_only_rerun",
        "staged_cumulative_raw": "staged_cumulative_raw",
    }[arm]


def _execute_one_shot(
    *,
    arm: str,
    case: CaseSpec,
    context: FixedRevisionEnvelope,
    provider: Any,
    progress: dict[str, list[Any]],
) -> ReasoningCard:
    provider_context = None if arm == ARMS[0] else context
    input_payload = _one_shot_input(case, provider_context)
    result = provider.generate(input_payload)
    _validate_mapping_result(
        case,
        context,
        input_payload,
        result,
        seen_raw_ids=case.evidence_ids,
    )
    progress["cards"].append(result.card.to_dict())
    progress["call_records"].append(
        {
            "phase": _arm_phase(arm),
            "sequence_offset": 0,
            "request_fingerprint": result.receipt.request_fingerprint,
            "input_payload_fingerprint": fingerprint(input_payload),
            "revision_context_present": provider_context is not None,
            "public_card_aperture": {
                "claim_characters": len(result.card.claim),
                "topic_characters": len(result.card.topic),
                "verbatim_raw_match_ids": list(
                    _verbatim_raw_match_ids(case, result.card, case.evidence_ids)
                ),
            },
            **result.to_dict(),
        }
    )
    return result.card


def _execute_staged(
    *,
    arm: str,
    case: CaseSpec,
    context: FixedRevisionEnvelope,
    provider: Any,
    progress: dict[str, list[Any]],
) -> ReasoningCard:
    cumulative_raw = arm == "staged_cumulative_raw"
    cards: list[ReasoningCard] = []
    for current_index, current in enumerate(case.all_evidence):
        input_payload = _staged_input(
            case,
            context,
            previous_card=cards[-1] if cards else None,
            current_index=current_index,
            cumulative_raw=cumulative_raw,
        )
        result = provider.generate(input_payload)
        seen_ids = case.evidence_ids[: current_index + 1]
        _validate_mapping_result(
            case,
            context,
            input_payload,
            result,
            seen_raw_ids=seen_ids,
        )
        cards.append(result.card)
        progress["cards"].append(result.card.to_dict())
        progress["call_records"].append(
            {
                "phase": _arm_phase(arm),
                "sequence_offset": current_index,
                "current_evidence_id": current.evidence_id,
                "retained_raw_evidence_ids": [
                    item["evidence_id"]
                    for item in input_payload["retained_raw_evidence"]
                ],
                "allowed_evidence_ids": list(input_payload["allowed_evidence_ids"]),
                "request_fingerprint": result.receipt.request_fingerprint,
                "input_payload_fingerprint": fingerprint(input_payload),
                "public_card_aperture": {
                    "claim_characters": len(result.card.claim),
                    "topic_characters": len(result.card.topic),
                    "verbatim_raw_match_ids": list(
                        _verbatim_raw_match_ids(case, result.card, seen_ids)
                    ),
                },
                **result.to_dict(),
            }
        )
    if len(cards) != len(case.all_evidence):
        raise AssertionError("staged arm did not generate one card per raw chunk")
    return cards[-1]


def _run_one_arm(
    *,
    arm: str,
    case: CaseSpec,
    context: FixedRevisionEnvelope,
    provider: Any,
    configured_ceiling: int,
) -> dict[str, Any]:
    audit_start = len(provider.audit_receipts)
    progress: dict[str, list[Any]] = {"cards": [], "call_records": []}
    try:
        if arm in ONE_SHOT_ARMS:
            final_card = _execute_one_shot(
                arm=arm,
                case=case,
                context=context,
                provider=provider,
                progress=progress,
            )
        elif arm in STAGED_ARMS:
            final_card = _execute_staged(
                arm=arm,
                case=case,
                context=context,
                provider=provider,
                progress=progress,
            )
        else:
            raise ValueError(f"unknown aperture-control arm: {arm}")
    except Exception as error:
        receipts = _arm_receipts(provider, audit_start)
        return {
            "arm": arm,
            "status": "failed",
            "failure_category": _failure_category(error),
            "configured_output_token_ceiling": configured_ceiling,
            "expected_api_calls": _expected_calls(arm, case),
            "final_card": None,
            "cards": progress["cards"],
            "call_records": progress["call_records"],
            "receipts": receipts,
            "accounting": _accounting(receipts),
        }
    receipts = _arm_receipts(provider, audit_start)
    return {
        "arm": arm,
        "status": "completed",
        "configured_output_token_ceiling": configured_ceiling,
        "expected_api_calls": _expected_calls(arm, case),
        "final_card": final_card.to_dict(),
        "cards": progress["cards"],
        "call_records": progress["call_records"],
        "receipts": receipts,
        "accounting": _accounting(receipts),
    }


def _williams_arm_order(
    trial_index: int,
    original_case_index: int,
) -> tuple[str, ...]:
    return WILLIAMS_ROWS[(trial_index + original_case_index) % len(WILLIAMS_ROWS)]


def _public_case_trace(case: CaseSpec) -> dict[str, Any]:
    return {"case_id": case.case_id, "family": case.family, **case.public_context()}


def execute_suite(
    *,
    cases: Sequence[CaseSpec],
    providers: Mapping[str, Any],
    max_card_output_tokens: int,
    trials: int,
    mode: str,
    provider_lock: Mapping[str, Any],
) -> dict[str, Any]:
    """Execute all four gold-free arms; grading is deliberately a later phase."""

    if trials <= 0:
        raise ValueError("trials must be positive")
    if not cases:
        raise ValueError("cases must not be empty")
    if set(providers) != set(ARMS):
        raise ValueError("providers must contain exactly the four locked arms")
    if max_card_output_tokens <= 0:
        raise ValueError("max_card_output_tokens must be positive")
    runs: list[dict[str, Any]] = []
    total_runs = trials * len(cases)
    for trial_index in range(trials):
        for run_position, (original_case_index, case) in enumerate(
            _rotated_cases(cases, trial_index)
        ):
            context = _build_fixed_revision_envelope(case)
            envelope = _envelope_dict(context)
            arm_order = _williams_arm_order(trial_index, original_case_index)
            ceiling = len(case.all_evidence) * int(max_card_output_tokens)
            pre_execution = {
                "case_input_fingerprint": fingerprint(case.public_context()),
                "validator_only_revision_bound": envelope,
                "arm_order": list(arm_order),
                "configured_output_token_ceiling_per_arm": ceiling,
                "provider": dict(provider_lock),
            }
            run: dict[str, Any] = {
                "run_id": f"{mode}:{trial_index}:{case.case_id}",
                "mode": mode,
                "trial_index": trial_index,
                "run_position": run_position,
                "original_case_index": original_case_index,
                "case_id": case.case_id,
                "family": case.family,
                "case": _public_case_trace(case),
                "case_input_fingerprint": pre_execution["case_input_fingerprint"],
                "fixed_revision_envelope": envelope,
                "fixed_revision_envelope_fingerprint": fingerprint(envelope),
                "no_revision_provider_context": None,
                "arm_order": list(arm_order),
                "pre_execution_fingerprint": fingerprint(pre_execution),
                "budget_match": {
                    "scope": "nominal_generated_token_ceiling_per_arm_per_case",
                    **{arm: ceiling for arm in ARMS},
                    "equal": True,
                    "realized_tokens_forced_equal": False,
                },
                "arms": {},
            }
            for arm in arm_order:
                run["arms"][arm] = _run_one_arm(
                    arm=arm,
                    case=case,
                    context=context,
                    provider=providers[arm],
                    configured_ceiling=ceiling,
                )
            run["complete"] = all(
                run["arms"][arm]["status"] == "completed" for arm in ARMS
            )
            runs.append(run)
            print(
                "[aperture-controls] {done}/{total} trial={trial} case={case} complete={complete}".format(
                    done=len(runs),
                    total=total_runs,
                    trial=trial_index,
                    case=case.case_id,
                    complete=str(run["complete"]).lower(),
                ),
                file=sys.stderr,
                flush=True,
            )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "DEV_DRAFT",
        "promotion_eligible": False,
        "mode": mode,
        "trials": trials,
        "case_ids": [case.case_id for case in cases],
        "case_count": len(cases),
        "provider_provenance": {arm: dict(providers[arm].provenance) for arm in ARMS},
        "runs": runs,
        "execution_complete": all(run["complete"] for run in runs),
    }


def _unavailable_grade() -> dict[str, Any]:
    return {
        "available": False,
        "machine_success": False,
        "evidence_consistent": False,
        "checks": None,
        "support_evidence_ids": [],
        "unexpected_support_evidence_ids": [],
        "missing_required_evidence_ids": [],
        "citation_precision": None,
        "citation_recall": None,
    }


def _binary_outcome(
    first: bool,
    second: bool,
    *,
    first_only: str,
    second_only: str,
) -> str:
    if first and second:
        return "both_pass"
    if first:
        return first_only
    if second:
        return second_only
    return "neither_pass"


def grade_executions(
    result: dict[str, Any],
    gold: Mapping[str, Mapping[str, Any]],
) -> None:
    """Attach the hidden grading surface only after all four arms have run."""

    for run in result["runs"]:
        case_gold = gold[run["case_id"]]
        for arm in ARMS:
            payload = run["arms"][arm]
            if payload["status"] == "completed":
                payload["grade"] = {
                    "available": True,
                    **grade_card(payload["final_card"], case_gold),
                }
            else:
                payload["grade"] = _unavailable_grade()
        if not run["complete"]:
            run["contrast_outcomes"] = {
                "revision_envelope": "incomplete",
                "raw_aperture": "incomplete",
            }
            continue
        success = {
            arm: bool(run["arms"][arm]["grade"]["machine_success"]) for arm in ARMS
        }
        run["contrast_outcomes"] = {
            "revision_envelope": _binary_outcome(
                success["direct_raw_no_revision"],
                success["direct_raw_fixed_revision_rerun"],
                first_only="no_revision_only",
                second_only="fixed_revision_only",
            ),
            "raw_aperture": _binary_outcome(
                success["staged_card_only_rerun"],
                success["staged_cumulative_raw"],
                first_only="card_only_only",
                second_only="cumulative_raw_only",
            ),
        }


def _mean(values: Sequence[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _median(values: Sequence[float]) -> float | None:
    return statistics.median(values) if values else None


def _stable_success(values: Sequence[bool]) -> bool:
    return bool(values) and sum(values) >= math.ceil(len(values) / 2)


def _sum_exact_usage(
    accountings: Sequence[Mapping[str, Any]],
    name: str,
) -> int | None:
    if not accountings or not all(
        bool(item["exact_provider_tokens"]) for item in accountings
    ):
        return None
    values = [item.get(name) for item in accountings]
    if any(value is None for value in values):
        return None
    return sum(int(value) for value in values if value is not None)


def _stable_pair_outcome(
    first: bool,
    second: bool,
    *,
    first_only: str,
    second_only: str,
) -> str:
    value = _binary_outcome(
        first,
        second,
        first_only=first_only,
        second_only=second_only,
    )
    return (
        "both"
        if value == "both_pass"
        else "neither"
        if value == "neither_pass"
        else value
    )


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
        if (
            revision_counts["fixed_revision_only"] > 0
            and revision_counts["no_revision_only"] > 0
        ):
            revision_conclusion = "revision_envelope_effect_mixed_by_case"
        elif revision_counts["fixed_revision_only"] > 0:
            revision_conclusion = "revision_envelope_contributes_on_this_dev"
        elif no_revision == locked_case_count:
            revision_conclusion = "revision_envelope_not_needed_on_this_saturated_dev"
        elif no_revision == fixed:
            revision_conclusion = "no_revision_envelope_effect_detected_below_ceiling"
        else:
            revision_conclusion = "no_revision_outperformed_fixed_on_this_dev"

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
        "claim": "mechanism_candidate_on_contaminated_dev_not_general_reasoning_improvement",
    }


def summarize_runs(
    runs: Sequence[Mapping[str, Any]],
    *,
    locked_case_ids: Sequence[str],
    locked_trials: int,
    historical_reference: Mapping[str, Any],
    receipts_validated: bool = False,
) -> dict[str, Any]:
    checks = (
        "answer_exact",
        "required_facts_exact",
        "stable_facts_exact",
        "required_evidence_present",
        "forbidden_support_absent",
        "expected_invalidated_evidence_marked",
    )
    arm_summary: dict[str, Any] = {}
    for arm in ARMS:
        payloads = [run["arms"][arm] for run in runs]
        completed = [item for item in payloads if item["status"] == "completed"]
        grades = [item["grade"] for item in completed]
        accountings = [item["accounting"] for item in payloads]
        arm_summary[arm] = {
            "attempted_runs": len(payloads),
            "completed_outputs": len(completed),
            "failed_or_incomplete_outputs": len(payloads) - len(completed),
            "machine_successes": sum(bool(item["machine_success"]) for item in grades),
            "answer_exact": sum(
                bool(item["checks"]["answer_exact"]) for item in grades
            ),
            "evidence_consistent": sum(
                bool(item["evidence_consistent"]) for item in grades
            ),
            "check_successes": {
                name: sum(bool(item["checks"][name]) for item in grades)
                for name in checks
            },
            "mean_citation_precision": _mean(
                [float(item["citation_precision"]) for item in grades]
            ),
            "mean_citation_recall": _mean(
                [float(item["citation_recall"]) for item in grades]
            ),
            "configured_output_token_ceiling": sum(
                int(item["configured_output_token_ceiling"]) for item in payloads
            ),
            "logical_calls": sum(int(item["logical_calls"]) for item in accountings),
            "api_calls": sum(int(item["api_calls"]) for item in accountings),
            "median_latency_ms_per_arm_run": _median(
                [float(item["latency_ms"]) for item in accountings]
            ),
            "exact_provider_tokens": bool(accountings)
            and all(bool(item["exact_provider_tokens"]) for item in accountings),
            "input_tokens": _sum_exact_usage(accountings, "input_tokens"),
            "output_tokens": _sum_exact_usage(accountings, "output_tokens"),
            "reasoning_tokens": _sum_exact_usage(accountings, "reasoning_tokens"),
            "cached_input_tokens": _sum_exact_usage(accountings, "cached_input_tokens"),
        }

    trial_contrast_counts = {
        contrast: {
            outcome: sum(run["contrast_outcomes"][contrast] == outcome for run in runs)
            for outcome in outcomes
        }
        for contrast, outcomes in {
            "revision_envelope": (
                "no_revision_only",
                "fixed_revision_only",
                "both_pass",
                "neither_pass",
                "incomplete",
            ),
            "raw_aperture": (
                "card_only_only",
                "cumulative_raw_only",
                "both_pass",
                "neither_pass",
                "incomplete",
            ),
        }.items()
    }

    by_case: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for run in runs:
        by_case[str(run["case_id"])].append(run)
    case_rows: list[dict[str, Any]] = []
    for case_id in locked_case_ids:
        case_runs = sorted(
            by_case.get(case_id, ()), key=lambda item: int(item["trial_index"])
        )
        if not case_runs:
            continue
        stable_assessed = len(case_runs) == locked_trials and {
            int(item["trial_index"]) for item in case_runs
        } == set(range(locked_trials))
        row: dict[str, Any] = {
            "case_id": case_id,
            "family": case_runs[0]["family"],
            "trials": len(case_runs),
            "complete_trials": sum(bool(item["complete"]) for item in case_runs),
            "stable_assessed": stable_assessed,
        }
        for arm in ARMS:
            successes = [
                bool(item["arms"][arm]["grade"]["machine_success"])
                for item in case_runs
            ]
            answers = [
                bool(item["arms"][arm]["grade"].get("checks", {}).get("answer_exact"))
                if item["arms"][arm]["grade"]["checks"] is not None
                else False
                for item in case_runs
            ]
            row[f"{arm}_successes"] = sum(successes)
            row[f"{arm}_stable_pass"] = (
                _stable_success(successes) if stable_assessed else None
            )
            row[f"{arm}_answer_exact"] = sum(answers)
            row[f"{arm}_stable_answer_exact"] = (
                _stable_success(answers) if stable_assessed else None
            )
        if stable_assessed:
            row["revision_envelope_stable_outcome"] = _stable_pair_outcome(
                bool(row["direct_raw_no_revision_stable_pass"]),
                bool(row["direct_raw_fixed_revision_rerun_stable_pass"]),
                first_only="no_revision_only",
                second_only="fixed_revision_only",
            )
            row["raw_aperture_stable_outcome"] = _stable_pair_outcome(
                bool(row["staged_card_only_rerun_stable_pass"]),
                bool(row["staged_cumulative_raw_stable_pass"]),
                first_only="card_only_only",
                second_only="cumulative_raw_only",
            )
        else:
            row["revision_envelope_stable_outcome"] = "not_assessed"
            row["raw_aperture_stable_outcome"] = "not_assessed"
        case_rows.append(row)

    stable = {
        arm: {
            "pass_cases": sum(bool(row[f"{arm}_stable_pass"]) for row in case_rows),
            "answer_exact_cases": sum(
                bool(row[f"{arm}_stable_answer_exact"]) for row in case_rows
            ),
        }
        for arm in ARMS
    }
    stable_contrast_counts = {
        "revision_envelope": {
            name: sum(
                row["revision_envelope_stable_outcome"] == name for row in case_rows
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
            name: sum(row["raw_aperture_stable_outcome"] == name for row in case_rows)
            for name in (
                "card_only_only",
                "cumulative_raw_only",
                "both",
                "neither",
                "not_assessed",
            )
        },
    }
    expected_trial_ids = set(range(locked_trials))
    exact_locked_coverage = set(by_case) == set(locked_case_ids) and all(
        len(by_case[case_id]) == locked_trials
        and {int(run["trial_index"]) for run in by_case[case_id]} == expected_trial_ids
        for case_id in locked_case_ids
    )
    all_locked_runs_complete = exact_locked_coverage and all(
        bool(run["complete"]) for run in runs
    )
    locked_decision_ready = all_locked_runs_complete and receipts_validated
    cause_decision = _decide_causes(
        stable=stable,
        stable_contrast_counts=stable_contrast_counts,
        locked_case_count=len(locked_case_ids),
        locked_decision_ready=locked_decision_ready,
        historical_reference=historical_reference,
    )
    return {
        "runs": len(runs),
        "completed_four_arm_runs": sum(bool(run["complete"]) for run in runs),
        "arm_summary": arm_summary,
        "trial_contrast_outcomes": trial_contrast_counts,
        "case_level": case_rows,
        "stable_case_summary": stable,
        "stable_contrast_outcomes": stable_contrast_counts,
        "exact_locked_case_trial_coverage": exact_locked_coverage,
        "all_locked_runs_complete": all_locked_runs_complete,
        "live_receipts_validated": receipts_validated,
        "locked_decision_ready": locked_decision_ready,
        "cause_decision": cause_decision,
    }


def _stored_receipts(
    result: Mapping[str, Any],
    arm: str,
) -> list[dict[str, Any]]:
    return [
        receipt for run in result["runs"] for receipt in run["arms"][arm]["receipts"]
    ]


def _validate_one_live_receipt(
    receipt: Mapping[str, Any],
    *,
    lock: Mapping[str, Any],
    expected_cap: int,
    expected_prompt_fingerprint: str,
) -> None:
    live = lock["live_provider"]
    if receipt["provider"] != "openai_responses":
        raise RuntimeError("unexpected provider in aperture-control receipt")
    if receipt["requested_model"] != live["model"]:
        raise RuntimeError("receipt requested-model drift")
    if receipt["prompt_fingerprint"] != expected_prompt_fingerprint:
        raise RuntimeError("receipt prompt fingerprint drift")
    metadata = receipt["metadata"]
    if metadata["reasoning_effort"] != live["reasoning_effort"]:
        raise RuntimeError("receipt reasoning-effort drift")
    if int(metadata["max_output_tokens"]) != expected_cap:
        raise RuntimeError("receipt output-token cap drift")
    if metadata["store"] is not False or metadata["previous_response_id"] is not False:
        raise RuntimeError("receipt persisted provider state")
    if metadata["truncation"] != "disabled":
        raise RuntimeError("receipt truncation-policy drift")
    if metadata["attempt"] != 1 or metadata["retry_count"] != 0:
        raise RuntimeError("receipt retry-policy drift")
    outcome = metadata["attempt_outcome"]
    if outcome == "completed":
        if receipt["returned_model"] != live["model"]:
            raise RuntimeError("completed receipt returned-model drift")
        if metadata["status"] != "completed":
            raise RuntimeError("completed receipt status drift")
        if metadata["service_tier"] != live["service_tier"]:
            raise RuntimeError("completed receipt service-tier drift")
        if receipt["usage"]["exact_provider_tokens"] is not True:
            raise RuntimeError("completed receipt lacks exact provider usage")
    elif outcome not in {"transport_error", "contract_error"}:
        raise RuntimeError("unknown receipt attempt outcome")
    if receipt["logical_calls"] != 1 or receipt["api_calls"] != 1:
        raise RuntimeError("receipt call accounting drift")
    for name in ("request_fingerprint", "prompt_fingerprint"):
        value = str(receipt[name])
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise RuntimeError(f"invalid receipt {name}")


def validate_live_receipts(
    result: Mapping[str, Any],
    lock: Mapping[str, Any],
    *,
    audit_receipts_by_arm: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    if set(audit_receipts_by_arm) != set(ARMS):
        raise RuntimeError("audit receipt map does not contain exactly four arms")
    stored = {arm: _stored_receipts(result, arm) for arm in ARMS}
    for arm in ARMS:
        if canonical_json(stored[arm]) != canonical_json(audit_receipts_by_arm[arm]):
            raise RuntimeError(f"{arm} audit receipts do not match trace receipts")

    provenance = result["provider_provenance"]
    prompt_fingerprints = {
        arm: str(provenance[arm]["instructions_fingerprint"]) for arm in ARMS
    }
    if prompt_fingerprints[ARMS[0]] != prompt_fingerprints[ARMS[1]]:
        raise RuntimeError("one-shot paired prompts diverged")
    if prompt_fingerprints[ARMS[2]] != prompt_fingerprints[ARMS[3]]:
        raise RuntimeError("staged paired prompts diverged")
    if prompt_fingerprints[ARMS[0]] != fingerprint(ONE_SHOT_INSTRUCTIONS):
        raise RuntimeError("one-shot prompt hash drifted from implementation")
    if prompt_fingerprints[ARMS[2]] != fingerprint(STAGED_INSTRUCTIONS):
        raise RuntimeError("staged prompt hash drifted from implementation")

    card_cap = int(lock["live_provider"]["max_card_output_tokens"])
    envelope_keys = set(lock["revision_envelope"]["provider_fields"])
    for run in result["runs"]:
        if set(run["fixed_revision_envelope"]) != envelope_keys:
            raise RuntimeError("trace revision envelope is not minimal")
        if run["no_revision_provider_context"] is not None:
            raise RuntimeError("no-revision provider context became populated")
        budget = run["budget_match"]
        ceilings = {int(budget[arm]) for arm in ARMS}
        if budget["equal"] is not True or len(ceilings) != 1:
            raise RuntimeError("four-arm configured token ceilings diverged")
        configured_ceiling = ceilings.pop()
        for arm in ARMS:
            payload = run["arms"][arm]
            receipts = payload["receipts"]
            expected_cap = configured_ceiling if arm in ONE_SHOT_ARMS else card_cap
            if int(payload["configured_output_token_ceiling"]) != configured_ceiling:
                raise RuntimeError("arm configured ceiling drifted from run budget")
            for receipt in receipts:
                _validate_one_live_receipt(
                    receipt,
                    lock=lock,
                    expected_cap=expected_cap,
                    expected_prompt_fingerprint=prompt_fingerprints[arm],
                )
            recorded = [item["receipt"] for item in payload["call_records"]]
            if canonical_json(recorded) != canonical_json(receipts[: len(recorded)]):
                raise RuntimeError(f"{arm} call records are not a receipt prefix")
            for record in payload["call_records"]:
                if (
                    record["request_fingerprint"]
                    != record["receipt"]["request_fingerprint"]
                ):
                    raise RuntimeError(f"{arm} record/request fingerprint drift")
                if record["input_payload_fingerprint"] != record["request_fingerprint"]:
                    raise RuntimeError(f"{arm} input/receipt fingerprint drift")
            if payload["status"] == "completed":
                expected_calls = int(payload["expected_api_calls"])
                if len(receipts) != expected_calls or len(recorded) != expected_calls:
                    raise RuntimeError(f"completed {arm} call count drift")
                attempted_cap = sum(
                    int(item["metadata"]["max_output_tokens"]) for item in receipts
                )
                if attempted_cap != configured_ceiling:
                    raise RuntimeError(f"completed {arm} did not attempt its ceiling")
                if arm in STAGED_ARMS:
                    expected_ids = [
                        *(
                            item["evidence_id"]
                            for item in run["case"]["initial_evidence"]
                        ),
                        run["case"]["late_evidence"]["evidence_id"],
                    ]
                    observed_ids = [
                        item["current_evidence_id"] for item in payload["call_records"]
                    ]
                    if observed_ids != expected_ids:
                        raise RuntimeError(f"{arm} staged evidence order drift")
    serialized = canonical_json(stored).lower()
    for forbidden in (
        "authorization",
        "openai_api_key",
        "bearer ",
        "api-key",
    ):
        if forbidden in serialized:
            raise RuntimeError("secret-bearing field appeared in live receipts")
    return {
        "validated": True,
        "receipts_by_arm": {arm: len(stored[arm]) for arm in ARMS},
        "all_runs_complete": bool(result["execution_complete"]),
        "pair_shared_prompts_validated": True,
        "nominal_ceiling_only": True,
        "failed_call_usage_or_transport_classification_claimed": False,
    }


def _call_rows(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in result["runs"]:
        for arm in run["arm_order"]:
            for call_index, receipt in enumerate(run["arms"][arm]["receipts"]):
                rows.append(
                    {
                        "run_id": run["run_id"],
                        "trial_index": run["trial_index"],
                        "case_id": run["case_id"],
                        "family": run["family"],
                        "arm": arm,
                        "arm_call_index": call_index,
                        "receipt": receipt,
                    }
                )
    return rows


def _arm_rows(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in result["runs"]:
        for arm in ARMS:
            payload = run["arms"][arm]
            grade = payload["grade"]
            accounting = payload["accounting"]
            checks = grade["checks"] or {}
            rows.append(
                {
                    "run_id": run["run_id"],
                    "trial_index": run["trial_index"],
                    "case_id": run["case_id"],
                    "family": run["family"],
                    "arm_order": ">".join(run["arm_order"]),
                    "arm": arm,
                    "status": payload["status"],
                    "failure_category": payload.get("failure_category"),
                    "revision_envelope_outcome": run["contrast_outcomes"][
                        "revision_envelope"
                    ],
                    "raw_aperture_outcome": run["contrast_outcomes"]["raw_aperture"],
                    "machine_success": grade["machine_success"],
                    "answer_exact": checks.get("answer_exact"),
                    "evidence_consistent": grade["evidence_consistent"],
                    "citation_precision": grade["citation_precision"],
                    "citation_recall": grade["citation_recall"],
                    "configured_output_token_ceiling": payload[
                        "configured_output_token_ceiling"
                    ],
                    "logical_calls": accounting["logical_calls"],
                    "api_calls": accounting["api_calls"],
                    "latency_ms": accounting["latency_ms"],
                    "input_tokens": accounting["input_tokens"],
                    "output_tokens": accounting["output_tokens"],
                    "reasoning_tokens": accounting["reasoning_tokens"],
                    "final_answer": (
                        None
                        if payload["final_card"] is None
                        else payload["final_card"]["current_answer"]
                    ),
                }
            )
    return rows


def _write_json(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(
            value,
            handle,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        handle.write("\n")


def _write_jsonl(path: Path, values: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for value in values:
            handle.write(canonical_json(value))
            handle.write("\n")


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError("cannot write an empty arm-row table")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _format_optional(value: Any) -> str:
    return "n/a" if value is None else str(value)


def _report_markdown(result: Mapping[str, Any]) -> str:
    summary = result["summary"]
    cause = summary["cause_decision"]
    lines = [
        "# EBRT v0.4.1 aperture controls — DEV report",
        "",
        f"Mode: `{result['mode']}`  ",
        f"Four-arm runs: `{summary['runs']}`  ",
        "Complete four-arm runs: "
        f"`{summary['completed_four_arm_runs']}/{summary['runs']}`  ",
        f"Locked decision ready: `{str(summary['locked_decision_ready']).lower()}`  ",
        f"Revision-envelope conclusion: `{cause['revision_envelope_conclusion']}`  ",
        f"Raw-aperture conclusion: `{cause['raw_aperture_conclusion']}`  ",
        f"Next scaffold step: `{cause['next_scaffold_step']}`",
        "",
        "The one-shot pair shares one prompt; only revision_context differs. The",
        "staged pair shares one prompt; retained raw prefix and its corresponding",
        "allowed evidence aperture differ. Only nominal cumulative max_output_tokens",
        "ceilings are matched. Actual calls, input/output/reasoning tokens, latency,",
        "price, and server compute are measured rather than matched.",
        "",
        "| Arm | Strict success | Completed | API calls | Input tokens | Output tokens | Reasoning tokens |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm in ARMS:
        item = summary["arm_summary"][arm]
        lines.append(
            "| {arm} | {success}/{attempted} | {completed}/{attempted} | {calls} | {input_tokens} | {output_tokens} | {reasoning_tokens} |".format(
                arm=arm,
                success=item["machine_successes"],
                completed=item["completed_outputs"],
                attempted=item["attempted_runs"],
                calls=item["api_calls"],
                input_tokens=_format_optional(item["input_tokens"]),
                output_tokens=_format_optional(item["output_tokens"]),
                reasoning_tokens=_format_optional(item["reasoning_tokens"]),
            )
        )
    lines.extend(
        [
            "",
            "## Stable case outcomes",
            "",
            "A stable pass means at least two successes in the locked three trials.",
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
            "This contaminated DEV calibration is a mechanism diagnostic, not a",
            "holdout, promotion experiment, or proof of general reasoning improvement.",
            "The no-revision arm remains a strict-schema scaffold. Cumulative raw",
            "repeats prior raw input across calls. A failure therefore cannot isolate",
            "retention from sequential commitment, prompt dynamics, or per-call cap",
            "allocation. Selective replay remains paused and unranked.",
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
    )
    output.mkdir(parents=True, exist_ok=True)
    _write_json(output / "results.json", result)
    _write_jsonl(output / "traces.jsonl", result["runs"])
    _write_jsonl(output / "calls.jsonl", _call_rows(result))
    _write_csv(output / "arm_rows.csv", _arm_rows(result))
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
        "schema_version": "ebrt-aperture-controls-manifest-v0.4.1",
        "status": (
            "COMPLETE_LOCKED_DEV"
            if locked_decision_ready
            else "COMPLETE_NON_DECISION_RUN"
            if execution_complete
            else "INCOMPLETE"
        ),
        "success_manifest": locked_decision_ready,
        "execution_complete": execution_complete,
        "locked_decision_ready": locked_decision_ready,
        "promotion_eligible": False,
        "mode": result["mode"],
        "source_sha256": dict(source_snapshot),
        "parent_manifest_sha256": _sha256(PARENT_MANIFEST_PATH),
        "artifact_sha256": {name: _sha256(output / name) for name in artifact_names},
        "fixture_sha256": _sha256(FIXTURE_PATH),
        "gold_sha256": _sha256(GOLD_PATH),
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "cause_decision": dict(result["summary"]["cause_decision"]),
        "claim_boundary": {
            "contaminated_dev_only": True,
            "nominal_output_ceiling_only": True,
            "observer_evaluated": False,
            "selective_replay_executed": False,
            "general_reasoning_improvement": False,
        },
    }
    _write_json(output / "manifest.json", manifest)
    return manifest


def _sanitized_failure_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    """Copy only the receipt fields emitted by the locked v0.4 client."""

    usage_names = (
        "exact_provider_tokens",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cached_input_tokens",
        "cache_write_tokens",
        "reasoning_tokens",
    )
    metadata_names = (
        "status",
        "service_tier",
        "response_id_sha256",
        "server_request_id_sha256",
        "client_request_id_sha256",
        "reasoning_effort",
        "max_output_tokens",
        "store",
        "previous_response_id",
        "truncation",
        "sdk_version",
        "python_version",
        "attempt",
        "retry_count",
        "api_call_count_semantics",
        "attempt_outcome",
        "failure_type",
        "refusal_count",
    )
    usage = value.get("usage", {})
    metadata = value.get("metadata", {})
    if not isinstance(usage, Mapping) or not isinstance(metadata, Mapping):
        return {"status": "malformed_receipt_omitted"}
    return {
        "provider": value.get("provider"),
        "requested_model": value.get("requested_model"),
        "returned_model": value.get("returned_model"),
        "logical_calls": value.get("logical_calls"),
        "api_calls": value.get("api_calls"),
        "latency_ms": value.get("latency_ms"),
        "request_fingerprint": value.get("request_fingerprint"),
        "prompt_fingerprint": value.get("prompt_fingerprint"),
        "usage": {name: usage.get(name) for name in usage_names},
        "metadata": {name: metadata.get(name) for name in metadata_names},
    }


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
        "schema_version": "ebrt-aperture-controls-failure-v0.4.1",
        "status": "INCOMPLETE",
        "success_manifest": False,
        "promotion_eligible": False,
        "mode": mode,
        "failure_category": _failure_category(error),
        "source_sha256": dict(source_snapshot),
        "parent_manifest_sha256": _sha256(PARENT_MANIFEST_PATH),
        "audit_receipts_by_arm": {
            arm: [
                _sanitized_failure_receipt(item)
                for item in audit_receipts_by_arm.get(arm, ())
            ]
            for arm in ARMS
        },
        "sanitization": "exception message raw responses headers and credentials omitted",
    }
    _write_json(failure_path, value)


def _replace_card(card: ReasoningCard, **changes: Any) -> ReasoningCard:
    value = card.to_dict()
    value.update(changes)
    return ReasoningCard.from_mapping(value)


def _gold_final_card(
    case: CaseSpec,
    gold: Mapping[str, Any],
    *,
    checkpoint_id: str = DIRECT_CHECKPOINT_ID,
) -> ReasoningCard:
    state = gold["final"]
    return ReasoningCard(
        checkpoint_id=checkpoint_id,
        claim=state["claim"],
        topic=state["topic"],
        stance=state["stance"],
        confidence=state["confidence"],
        evidence_ids=tuple(state["evidence_ids"]),
        current_answer=state["answer"],
        revision_cue=state["revision_cue"],
        decision_facts=tuple(
            DecisionFact(
                slot=item["slot"],
                value=item["value"],
                evidence_ids=tuple(item["evidence_ids"]),
            )
            for item in state["decision_facts"]
        ),
        invalidated_evidence_ids=tuple(state["invalidated_evidence_ids"]),
    )


def _fake_result(
    card: ReasoningCard,
    input_payload: Mapping[str, Any],
    *,
    instructions: str,
) -> CardResult:
    return CardResult(
        card=card,
        receipt=ProviderReceipt(
            provider="local_contract_test",
            requested_model=None,
            returned_model=None,
            logical_calls=1,
            api_calls=0,
            latency_ms=0.0,
            request_fingerprint=fingerprint(input_payload),
            prompt_fingerprint=fingerprint(instructions),
            usage=ProviderUsage(exact_provider_tokens=False),
            metadata={"plumbing_only": True},
        ),
    )


def _expect_value_error(action: Any) -> None:
    try:
        action()
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def _all_mapping_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            keys.add(str(key))
            keys.update(_all_mapping_keys(child))
    elif isinstance(value, list | tuple):
        for child in value:
            keys.update(_all_mapping_keys(child))
    return keys


def _minimal_prior_card(
    case: CaseSpec,
    context: FixedRevisionEnvelope,
    current_index: int,
) -> ReasoningCard | None:
    if current_index == 0:
        return None
    prior = case.all_evidence[:current_index]
    permitted = [
        item.evidence_id
        for item in prior
        if item.evidence_id not in context.invalidated_evidence_ids
    ]
    support = permitted[-1:]
    return ReasoningCard(
        checkpoint_id=f"card:{prior[-1].evidence_id}",
        claim="Bounded public self-test state.",
        topic="self_test",
        stance=0.0,
        confidence=0.5,
        evidence_ids=tuple(support),
        current_answer=case.answer_choices[0],
        revision_cue=0.0,
        decision_facts=tuple(
            DecisionFact(
                slot=item.slot_id,
                value="UNKNOWN",
                evidence_ids=tuple(support),
            )
            for item in case.decision_slots
            if item.required
        ),
        invalidated_evidence_ids=tuple(context.invalidated_evidence_ids),
    )


class _ScriptedMappingProvider:
    """Gold-free local provider used only to exercise four-arm plumbing."""

    def __init__(self, *, max_output_tokens: int, instructions: str) -> None:
        self.max_output_tokens = int(max_output_tokens)
        self.instructions = instructions
        self._audit_receipts: list[dict[str, Any]] = []
        self.inputs: list[dict[str, Any]] = []

    @property
    def provenance(self) -> Mapping[str, Any]:
        return {
            "provider": "local_scripted_mapping",
            "model": None,
            "deterministic": True,
            "max_output_tokens": self.max_output_tokens,
            "instructions_fingerprint": fingerprint(self.instructions),
            "plumbing_only": True,
        }

    @property
    def audit_receipts(self) -> list[dict[str, Any]]:
        return json.loads(canonical_json(self._audit_receipts))

    def generate(self, input_payload: Mapping[str, Any]) -> CardResult:
        payload = json.loads(canonical_json(input_payload))
        self.inputs.append(payload)
        context = payload.get("revision_context")
        invalidated = (
            []
            if not isinstance(context, Mapping)
            else [str(item) for item in context["invalidated_evidence_ids"]]
        )
        if "all_raw_evidence" in payload:
            available = [
                str(item["evidence_id"]) for item in payload["all_raw_evidence"]
            ]
        else:
            available = [
                str(item["evidence_id"]) for item in payload["retained_raw_evidence"]
            ]
            previous = payload.get("previous_public_card")
            if isinstance(previous, Mapping):
                available.extend(str(item) for item in previous["evidence_ids"])
            available.append(str(payload["current_evidence"]["evidence_id"]))
        support = next(
            (item for item in reversed(available) if item not in invalidated),
            None,
        )
        if support is None:
            raise AssertionError("scripted provider could not choose active support")
        card = ReasoningCard(
            checkpoint_id=str(payload["checkpoint_id"]),
            claim="Bounded public plumbing state.",
            topic="self_test",
            stance=0.0,
            confidence=0.5,
            evidence_ids=(support,),
            current_answer=str(payload["answer_choices"][0]),
            revision_cue=0.0,
            decision_facts=tuple(
                DecisionFact(
                    slot=str(item["slot_id"]),
                    value="UNKNOWN",
                    evidence_ids=(support,),
                )
                for item in payload["decision_slots"]
                if bool(item["required"])
            ),
            invalidated_evidence_ids=tuple(invalidated),
        )
        receipt = ProviderReceipt(
            provider="local_scripted_mapping",
            requested_model=None,
            returned_model=None,
            logical_calls=1,
            api_calls=0,
            latency_ms=0.0,
            request_fingerprint=fingerprint(payload),
            prompt_fingerprint=fingerprint(self.instructions),
            usage=ProviderUsage(exact_provider_tokens=False),
            metadata={
                "plumbing_only": True,
                "max_output_tokens": self.max_output_tokens,
            },
        )
        self._audit_receipts.append(receipt.to_dict())
        return CardResult(card=card, receipt=receipt)


def _assert_williams_balance(trials: int, case_count: int) -> dict[str, Any]:
    if any(set(row) != set(ARMS) or len(row) != len(ARMS) for row in WILLIAMS_ROWS):
        raise AssertionError("Williams row is not a four-arm permutation")
    for position in range(len(ARMS)):
        if {row[position] for row in WILLIAMS_ROWS} != set(ARMS):
            raise AssertionError("Williams base rows are not position-balanced")
    ordered_pairs = [
        pair for row in WILLIAMS_ROWS for pair in zip(row, row[1:], strict=False)
    ]
    expected_pairs = {
        (first, second) for first in ARMS for second in ARMS if first != second
    }
    if set(ordered_pairs) != expected_pairs or len(ordered_pairs) != len(
        expected_pairs
    ):
        raise AssertionError("Williams base rows are not first-order balanced")

    orders = [
        _williams_arm_order(trial, case_index)
        for trial in range(trials)
        for case_index in range(case_count)
    ]
    position_counts = {
        position: {arm: sum(order[position] == arm for order in orders) for arm in ARMS}
        for position in range(len(ARMS))
    }
    if any(
        max(counts.values()) - min(counts.values()) > 1
        for counts in position_counts.values()
    ):
        raise AssertionError("locked assignment is materially position-imbalanced")
    adjacency_counts = {
        pair: sum(
            pair in tuple(zip(order, order[1:], strict=False)) for order in orders
        )
        for pair in expected_pairs
    }
    if max(adjacency_counts.values()) - min(adjacency_counts.values()) > 1:
        raise AssertionError("locked assignment is materially adjacency-imbalanced")
    return {
        "orders": len(orders),
        "position_counts": position_counts,
        "adjacency_min": min(adjacency_counts.values()),
        "adjacency_max": max(adjacency_counts.values()),
    }


def _self_test_cause_decisions(lock: Mapping[str, Any]) -> None:
    historical = lock["historical_reference_only"]

    def stable(a: int, b: int, c: int, d: int) -> dict[str, dict[str, int]]:
        return {
            arm: {"pass_cases": count, "answer_exact_cases": count}
            for arm, count in zip(ARMS, (a, b, c, d), strict=True)
        }

    base_counts = {
        "revision_envelope": {
            "no_revision_only": 0,
            "fixed_revision_only": 0,
            "both": 10,
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
    rescued = _decide_causes(
        stable=stable(10, 10, 1, 10),
        stable_contrast_counts=base_counts,
        locked_case_count=10,
        locked_decision_ready=True,
        historical_reference=historical,
    )
    if rescued["revision_envelope_conclusion"] != (
        "revision_envelope_not_needed_on_this_saturated_dev"
    ):
        raise AssertionError("revision-envelope no-effect rule drifted")
    if rescued["raw_aperture_conclusion"] != (
        "raw_aperture_rescue_candidate_on_this_dev"
    ):
        raise AssertionError("raw-aperture rescue rule drifted")
    fixed_counts = json.loads(canonical_json(base_counts))
    fixed_counts["revision_envelope"].update({"both": 8, "fixed_revision_only": 2})
    fixed = _decide_causes(
        stable=stable(8, 10, 1, 10),
        stable_contrast_counts=fixed_counts,
        locked_case_count=10,
        locked_decision_ready=True,
        historical_reference=historical,
    )
    if fixed["revision_envelope_conclusion"] != (
        "revision_envelope_contributes_on_this_dev"
    ):
        raise AssertionError("revision-envelope contribution rule drifted")
    incomplete = _decide_causes(
        stable=stable(1, 1, 1, 1),
        stable_contrast_counts=base_counts,
        locked_case_count=10,
        locked_decision_ready=False,
        historical_reference=historical,
    )
    if incomplete["decision_ready"] or not incomplete["next_scaffold_step"].startswith(
        "complete_exact_locked"
    ):
        raise AssertionError("incomplete cause-decision gate drifted")


def _self_test_live_receipt(
    *,
    request_fingerprint: str,
    prompt_fingerprint: str,
    cap: int,
    lock: Mapping[str, Any],
) -> dict[str, Any]:
    live = lock["live_provider"]
    return {
        "provider": "openai_responses",
        "requested_model": live["model"],
        "returned_model": live["model"],
        "logical_calls": 1,
        "api_calls": 1,
        "latency_ms": 1.0,
        "request_fingerprint": request_fingerprint,
        "prompt_fingerprint": prompt_fingerprint,
        "usage": {
            "exact_provider_tokens": True,
            "input_tokens": 1,
            "output_tokens": 1,
            "total_tokens": 2,
            "cached_input_tokens": 0,
            "cache_write_tokens": 0,
            "reasoning_tokens": 0,
        },
        "metadata": {
            "status": "completed",
            "service_tier": live["service_tier"],
            "response_id_sha256": "0" * 64,
            "server_request_id_sha256": "1" * 64,
            "client_request_id_sha256": "2" * 64,
            "reasoning_effort": live["reasoning_effort"],
            "max_output_tokens": cap,
            "store": False,
            "previous_response_id": False,
            "truncation": "disabled",
            "sdk_version": "self-test",
            "python_version": platform.python_version(),
            "attempt": 1,
            "retry_count": 0,
            "api_call_count_semantics": "attempted_client_call",
            "attempt_outcome": "completed",
            "failure_type": None,
            "refusal_count": 0,
        },
    }


def run_self_tests() -> dict[str, Any]:
    source_snapshot = dict(BOOT_SOURCE_SNAPSHOT)
    _assert_source_snapshot(source_snapshot)
    parent_manifest = _validate_parent_manifest()
    lock = _load_lock()
    cases, gold = _load_suite()
    if len(cases) != int(lock["fixtures"]["case_count"]):
        raise AssertionError("locked case count drifted")
    if any(
        len(case.all_evidence) != int(lock["fixtures"]["evidence_chunks_per_case"])
        for case in cases
    ):
        raise AssertionError("locked evidence geometry drifted")
    card_cap = int(lock["live_provider"]["max_card_output_tokens"])
    expected_ceiling = int(
        lock["budget_match"]["expected_ceiling_for_current_six_chunk_cases"]
    )

    for case in cases:
        context = _build_fixed_revision_envelope(case)
        envelope = _envelope_dict(context)
        if set(envelope) != set(lock["revision_envelope"]["provider_fields"]):
            raise AssertionError("envelope provider surface drifted")
        if _all_mapping_keys(envelope) & set(
            lock["revision_envelope"]["excluded_fields"]
        ):
            raise AssertionError("forbidden field leaked into fixed envelope")
        no_revision = _one_shot_input(case, None)
        fixed_revision = _one_shot_input(case, context)
        if set(no_revision) != set(fixed_revision):
            raise AssertionError("one-shot pair input keys diverged")
        normalized = json.loads(canonical_json(no_revision))
        normalized["revision_context"] = envelope
        if canonical_json(normalized) != canonical_json(fixed_revision):
            raise AssertionError("one-shot pair differs beyond revision_context")
        if no_revision["revision_context"] is not None:
            raise AssertionError("no-revision arm received a revision envelope")
        if _all_mapping_keys(no_revision) & {"semantic", "gold", "grader_output"}:
            raise AssertionError("hidden annotation leaked to no-revision provider")
        direct_raw = [item["evidence_id"] for item in no_revision["all_raw_evidence"]]
        if direct_raw != list(case.evidence_ids):
            raise AssertionError("one-shot raw evidence order drifted")
        serialized_direct = canonical_json(no_revision)
        for chunk in case.all_evidence:
            if serialized_direct.count(chunk.text) != 1:
                raise AssertionError(
                    "one-shot raw evidence did not appear exactly once"
                )
        if case.late_evidence.text in canonical_json(envelope):
            raise AssertionError("late raw text leaked into revision envelope")

        for current_index, current in enumerate(case.all_evidence):
            previous = _minimal_prior_card(case, context, current_index)
            card_only = _staged_input(
                case,
                context,
                previous_card=previous,
                current_index=current_index,
                cumulative_raw=False,
            )
            cumulative = _staged_input(
                case,
                context,
                previous_card=previous,
                current_index=current_index,
                cumulative_raw=True,
            )
            if set(card_only) != set(cumulative):
                raise AssertionError("staged pair input keys diverged")
            normalized_cumulative = json.loads(canonical_json(cumulative))
            normalized_cumulative["retained_raw_evidence"] = []
            normalized_cumulative["allowed_evidence_ids"] = card_only[
                "allowed_evidence_ids"
            ]
            if canonical_json(normalized_cumulative) != canonical_json(card_only):
                raise AssertionError(
                    "staged pair differs beyond retained raw and allowed aperture"
                )
            if card_only["retained_raw_evidence"]:
                raise AssertionError("card-only rerun retained raw evidence")
            expected_prior = [
                item.public_dict() for item in case.all_evidence[:current_index]
            ]
            if cumulative["retained_raw_evidence"] != expected_prior:
                raise AssertionError("cumulative raw prefix is not exact and ordered")
            if current.public_dict() in cumulative["retained_raw_evidence"]:
                raise AssertionError("current raw chunk was duplicated in retained raw")
            if cumulative["current_evidence"] != current.public_dict():
                raise AssertionError("staged current evidence drifted")
            if (
                card_only["revision_context"] != envelope
                or cumulative["revision_context"] != envelope
            ):
                raise AssertionError(
                    "post-event staged reconstruction lost its fixed envelope"
                )
            if _all_mapping_keys(cumulative) & {"semantic", "gold", "grader_output"}:
                raise AssertionError("hidden annotation leaked to staged provider")
            serialized_cumulative = canonical_json(cumulative)
            for future in case.all_evidence[current_index + 1 :]:
                if future.text in serialized_cumulative:
                    raise AssertionError(
                        "future raw text leaked into cumulative prefix"
                    )
            if current_index < len(case.all_evidence) - 1:
                if case.late_evidence.text in serialized_cumulative:
                    raise AssertionError(
                        "late raw text appeared before final staged call"
                    )
                if case.late_evidence.evidence_id in cumulative["allowed_evidence_ids"]:
                    raise AssertionError(
                        "late evidence became citable before presentation"
                    )
            elif serialized_cumulative.count(case.late_evidence.text) != 1:
                raise AssertionError(
                    "late raw text must appear once in final staged call"
                )

        ceiling = len(case.all_evidence) * card_cap
        if ceiling != expected_ceiling:
            raise AssertionError("current case completion ceiling drifted")
        gold_card = _gold_final_card(case, gold[case.case_id])
        direct_result = _fake_result(
            gold_card,
            no_revision,
            instructions=ONE_SHOT_INSTRUCTIONS,
        )
        _validate_mapping_result(
            case,
            context,
            no_revision,
            direct_result,
            seen_raw_ids=case.evidence_ids,
        )
        if not grade_card(gold_card.to_dict(), gold[case.case_id])["machine_success"]:
            raise AssertionError("gold final card does not pass the shared grader")
        _expect_value_error(
            lambda: _validate_mapping_result(
                case,
                context,
                no_revision,
                _fake_result(
                    _replace_card(
                        gold_card,
                        claim=(
                            f"{case.initial_evidence[0].text} "
                            f"{case.initial_evidence[1].text}"
                        ),
                    ),
                    no_revision,
                    instructions=ONE_SHOT_INSTRUCTIONS,
                ),
                seen_raw_ids=case.evidence_ids,
            )
        )
        invalidated = context.invalidated_evidence_ids[0]
        _expect_value_error(
            lambda: _validate_mapping_result(
                case,
                context,
                no_revision,
                _fake_result(
                    _replace_card(
                        gold_card,
                        evidence_ids=[*gold_card.evidence_ids, invalidated],
                    ),
                    no_revision,
                    instructions=ONE_SHOT_INSTRUCTIONS,
                ),
                seen_raw_ids=case.evidence_ids,
            )
        )
        _expect_value_error(
            lambda: _validate_mapping_result(
                case,
                context,
                no_revision,
                _fake_result(
                    _replace_card(
                        gold_card,
                        decision_facts=[
                            *(item.to_dict() for item in gold_card.decision_facts),
                            gold_card.decision_facts[0].to_dict(),
                        ],
                    ),
                    no_revision,
                    instructions=ONE_SHOT_INSTRUCTIONS,
                ),
                seen_raw_ids=case.evidence_ids,
            )
        )
        _expect_value_error(
            lambda: _validate_mapping_result(
                case,
                context,
                no_revision,
                _fake_result(
                    _replace_card(gold_card, checkpoint_id="wrong:checkpoint"),
                    no_revision,
                    instructions=ONE_SHOT_INSTRUCTIONS,
                ),
                seen_raw_ids=case.evidence_ids,
            )
        )
        _expect_value_error(
            lambda: _validate_mapping_result(
                case,
                context,
                no_revision,
                _fake_result(
                    _replace_card(
                        gold_card,
                        decision_facts=[
                            item.to_dict() for item in gold_card.decision_facts[:-1]
                        ],
                    ),
                    no_revision,
                    instructions=ONE_SHOT_INSTRUCTIONS,
                ),
                seen_raw_ids=case.evidence_ids,
            )
        )
        _expect_value_error(
            lambda: _validate_mapping_result(
                case,
                context,
                no_revision,
                _fake_result(
                    _replace_card(
                        gold_card,
                        evidence_ids=[*gold_card.evidence_ids, "UNKNOWN_ID"],
                    ),
                    no_revision,
                    instructions=ONE_SHOT_INSTRUCTIONS,
                ),
                seen_raw_ids=case.evidence_ids,
            )
        )
        unexpected_invalidation = next(
            item
            for item in case.evidence_ids
            if item not in context.invalidated_evidence_ids
        )
        _expect_value_error(
            lambda: _validate_mapping_result(
                case,
                context,
                no_revision,
                _fake_result(
                    _replace_card(
                        gold_card,
                        invalidated_evidence_ids=[
                            *gold_card.invalidated_evidence_ids,
                            unexpected_invalidation,
                        ],
                    ),
                    no_revision,
                    instructions=ONE_SHOT_INSTRUCTIONS,
                ),
                seen_raw_ids=case.evidence_ids,
            )
        )
        first_staged = _staged_input(
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
            claim="Invalid unseen-support sentinel.",
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
                    evidence_ids=(),
                )
                for item in case.decision_slots
                if item.required
            ),
            invalidated_evidence_ids=tuple(context.invalidated_evidence_ids),
        )
        _expect_value_error(
            lambda: _validate_mapping_result(
                case,
                context,
                first_staged,
                _fake_result(
                    unseen_card,
                    first_staged,
                    instructions=STAGED_INSTRUCTIONS,
                ),
                seen_raw_ids=(case.initial_evidence[0].evidence_id,),
            )
        )
        wrong_receipt_result = _fake_result(
            gold_card,
            {"wrong": "request"},
            instructions=ONE_SHOT_INSTRUCTIONS,
        )
        _expect_value_error(
            lambda: _validate_mapping_result(
                case,
                context,
                no_revision,
                wrong_receipt_result,
                seen_raw_ids=case.evidence_ids,
            )
        )

    balance = _assert_williams_balance(int(lock["execution"]["trials"]), len(cases))
    if "gold" in inspect.signature(execute_suite).parameters:
        raise AssertionError("gold entered the execution function signature")
    _self_test_cause_decisions(lock)

    sample = cases[0]
    fake_providers = {
        arm: _ScriptedMappingProvider(
            max_output_tokens=(expected_ceiling if arm in ONE_SHOT_ARMS else card_cap),
            instructions=(
                ONE_SHOT_INSTRUCTIONS if arm in ONE_SHOT_ARMS else STAGED_INSTRUCTIONS
            ),
        )
        for arm in ARMS
    }
    fake_result = execute_suite(
        cases=[sample],
        providers=fake_providers,
        max_card_output_tokens=card_cap,
        trials=1,
        mode="self_test",
        provider_lock={"provider": "local_scripted_mapping"},
    )
    if not fake_result["execution_complete"]:
        raise AssertionError("scripted four-arm execution did not complete")
    fake_run = fake_result["runs"][0]
    if sum(len(fake_run["arms"][arm]["receipts"]) for arm in ARMS) != 14:
        raise AssertionError("four-arm call geometry drifted from fourteen calls")
    for arm in ARMS:
        payload = fake_run["arms"][arm]
        if len(payload["receipts"]) != _expected_calls(arm, sample):
            raise AssertionError(f"scripted {arm} call count drifted")
        if int(payload["configured_output_token_ceiling"]) != expected_ceiling:
            raise AssertionError(f"scripted {arm} ceiling drifted")
    if (
        fake_providers[ARMS[0]].provenance["instructions_fingerprint"]
        != (fake_providers[ARMS[1]].provenance["instructions_fingerprint"])
    ):
        raise AssertionError("scripted one-shot pair prompt hash diverged")
    if (
        fake_providers[ARMS[2]].provenance["instructions_fingerprint"]
        != (fake_providers[ARMS[3]].provenance["instructions_fingerprint"])
    ):
        raise AssertionError("scripted staged pair prompt hash diverged")
    live_like_audit: dict[str, list[dict[str, Any]]] = {}
    for arm in ARMS:
        payload = fake_run["arms"][arm]
        cap = expected_ceiling if arm in ONE_SHOT_ARMS else card_cap
        prompt_hash = str(
            fake_result["provider_provenance"][arm]["instructions_fingerprint"]
        )
        live_like_receipts = [
            _self_test_live_receipt(
                request_fingerprint=str(record["request_fingerprint"]),
                prompt_fingerprint=prompt_hash,
                cap=cap,
                lock=lock,
            )
            for record in payload["call_records"]
        ]
        payload["receipts"] = live_like_receipts
        for record, receipt in zip(
            payload["call_records"], live_like_receipts, strict=True
        ):
            record["receipt"] = receipt
        live_like_audit[arm] = live_like_receipts
    receipt_check = validate_live_receipts(
        fake_result,
        lock,
        audit_receipts_by_arm=live_like_audit,
    )
    if (
        not receipt_check["validated"]
        or sum(receipt_check["receipts_by_arm"].values()) != 14
    ):
        raise AssertionError("live-like receipt validation geometry drifted")
    grade_executions(fake_result, gold)
    fake_summary = summarize_runs(
        fake_result["runs"],
        locked_case_ids=[case.case_id for case in cases],
        locked_trials=LOCKED_TRIALS,
        historical_reference=lock["historical_reference_only"],
        receipts_validated=bool(receipt_check["validated"]),
    )
    if fake_summary["locked_decision_ready"]:
        raise AssertionError("one-case self-test became locked decision ready")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        failure_dir = temp_root / "failure"
        _write_failure_bundle(
            failure_dir,
            mode="self_test",
            source_snapshot=source_snapshot,
            audit_receipts_by_arm={
                **{arm: () for arm in ARMS},
                ARMS[0]: (
                    {
                        "authorization": "TOP_SECRET_SENTINEL",
                        "usage": {},
                        "metadata": {"authorization": "Bearer TOP_SECRET_SENTINEL"},
                    },
                ),
            },
            error=RuntimeError("DO_NOT_SERIALIZE_THIS_SENTINEL"),
        )
        failure_text = (failure_dir / "failure.json").read_text(encoding="utf-8")
        if "DO_NOT_SERIALIZE_THIS_SENTINEL" in failure_text:
            raise AssertionError("failure bundle serialized a raw exception message")
        if "TOP_SECRET_SENTINEL" in failure_text or "Bearer " in failure_text:
            raise AssertionError("failure bundle serialized a secret-bearing field")
        if (failure_dir / "manifest.json").exists():
            raise AssertionError("failure bundle wrote a success manifest")
        fake_result["summary"] = fake_summary
        fake_result["claim_boundary"] = list(lock["claim_boundary"])
        bundle_dir = temp_root / "bundle"
        manifest = write_bundle(
            fake_result,
            bundle_dir,
            source_snapshot=source_snapshot,
        )
        if manifest["success_manifest"] or manifest["locked_decision_ready"]:
            raise AssertionError("subset self-test wrote a locked success manifest")
    _assert_source_snapshot(source_snapshot)
    return {
        "status": "ok",
        "tests": 24,
        "cases": len(cases),
        "four_arm_calls_per_case_trial": 14,
        "nominal_output_ceiling_per_arm": expected_ceiling,
        "williams_balance": balance,
        "parent_manifest_sha256": _sha256(PARENT_MANIFEST_PATH),
        "parent_source_files_verified": len(parent_manifest["source_sha256"]),
        "source_sha256": source_snapshot,
    }


def _run_live(
    *,
    output: Path,
    case_ids: Sequence[str],
    trials: int,
    mode: str,
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
        _validate_parent_manifest()
        lock = _load_lock()
        cases, gold = _load_suite()
        selected = _select_cases(cases, case_ids)
        if not selected:
            raise ValueError("at least one live case is required")
        chunk_counts = {len(case.all_evidence) for case in selected}
        if len(chunk_counts) != 1:
            raise RuntimeError("one-shot cap requires equal evidence counts")
        live = lock["live_provider"]
        card_cap = int(live["max_card_output_tokens"])
        direct_cap = next(iter(chunk_counts)) * card_cap
        for arm in ARMS:
            providers[arm] = _make_openai_mapping_provider(
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
        help="run offline source-integrity, aperture, order, and grader tests",
    )
    smoke = subparsers.add_parser(
        "live-smoke",
        help="run the locked two-case one-trial four-arm API plumbing check",
    )
    smoke.add_argument("--output", type=Path, default=DEFAULT_SMOKE_OUTPUT)
    smoke.add_argument("--trials", type=int, default=1)
    smoke.add_argument("--case-id", action="append", dest="case_ids")
    dev = subparsers.add_parser(
        "live-dev",
        help="run the full 10-case repeated non-promotional DEV controls",
    )
    dev.add_argument("--output", type=Path, default=DEFAULT_DEV_OUTPUT)
    dev.add_argument("--trials", type=int, default=3)
    dev.add_argument("--case-id", action="append", dest="case_ids")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "self-test":
        value = run_self_tests()
    else:
        lock = _load_lock()
        cases, _ = _load_suite()
        if args.case_ids:
            case_ids = args.case_ids
        elif args.command == "live-smoke":
            case_ids = lock["fixtures"]["live_canary_case_ids"]
        else:
            case_ids = [case.case_id for case in cases]
        value = _run_live(
            output=args.output,
            case_ids=case_ids,
            trials=args.trials,
            mode=(
                "openai_live_smoke"
                if args.command == "live-smoke"
                else "openai_live_dev_aperture_controls"
            ),
        )
    print(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
