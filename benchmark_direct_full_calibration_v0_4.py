#!/usr/bin/env python3
"""Completion-ceiling-matched Direct-vs-Full DEV calibration for EBRT v0.4.

The two arms begin after the same fixed, minimal revision envelope:

* ``direct_raw_fixed_revision`` reads all raw evidence in one Responses call;
* ``full_restart`` rebuilds six public Reasoning Cards from an empty state.

This module intentionally does not execute selective replay.  It asks whether
the staged public-card scaffold is worth keeping before optimizing its replay
cost.  Only public structured cards and sanitized provider receipts are stored.
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
SOURCE_FILES = (
    "benchmark_direct_full_calibration_v0_4.py",
    "policy_lock_direct_full_calibration_v0_4.json",
    "language_replay_bridge_v0_4.py",
    "openai_reasoning_provider_v0_4.py",
    "benchmark_language_replay_v0_4.py",
    "policy_lock_v0_4.json",
    "fixtures/language_replay_v0_4_dev.json",
    "fixtures/language_replay_v0_4_dev_gold.json",
    "semantic_adapter_v0_2.py",
    "requirements-live.txt",
)
BOOT_SOURCE_SNAPSHOT = {
    name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    for name in SOURCE_FILES
}


from benchmark_language_replay_v0_4 import grade_card  # noqa: E402
from language_replay_bridge_v0_4 import (  # noqa: E402
    CardRequest,
    CardResult,
    CaseSpec,
    DecisionFact,
    ProviderReceipt,
    ProviderUsage,
    ReasoningCard,
    RevisionContext,
    ScriptedReasoningProvider,
    _aggregate_receipts,
    _public_support_ids,
    _validate_card_result,
    canonical_json,
    fingerprint,
)


SCHEMA_VERSION = "ebrt-direct-full-calibration-v0.4"
ARMS = ("direct_raw_fixed_revision", "full_restart")
DIRECT_CHECKPOINT_ID = "direct:final"
LOCK_PATH = ROOT / "policy_lock_direct_full_calibration_v0_4.json"
FIXTURE_PATH = ROOT / "fixtures" / "language_replay_v0_4_dev.json"
GOLD_PATH = ROOT / "fixtures" / "language_replay_v0_4_dev_gold.json"
DEFAULT_SMOKE_OUTPUT = ROOT / "benchmark_results" / "v0_4_direct_full_live_smoke"
DEFAULT_DEV_OUTPUT = ROOT / "benchmark_results" / "v0_4_direct_full_dev"


DIRECT_INSTRUCTIONS = """\
Produce one compact PUBLIC final decision-state card. Do not provide private
chain-of-thought, hidden reasoning, or a prose derivation. Resolve the question
using only the ordered all_raw_evidence and the fixed public revision envelope.
The current_answer must exactly equal one supplied answer choice. Cite only the
supplied evidence IDs. Evidence named invalidated or superseded in the envelope
must not be used as active support; list it only in invalidated_evidence_ids and
never infer additional invalidations. Use every required decision slot exactly
once, copy each slot_id exactly, and choose only an exact allowed value; use
UNKNOWN when a value is unsupported. Keep the public facts externally
checkable and sufficient to audit the final answer. Return only the strict
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
        raise RuntimeError("calibration source graph changed during execution")


def _load_lock() -> dict[str, Any]:
    lock = _load_json(LOCK_PATH)
    if lock.get("status") != "DEV_DRAFT" or lock.get("promotion_eligible") is not False:
        raise RuntimeError("calibration lock must remain non-promotional DEV_DRAFT")
    if tuple(lock.get("arms", ())) != ARMS:
        raise RuntimeError("calibration arm order does not match implementation")
    live = lock["live_provider"]
    legacy = _load_json(ROOT / "policy_lock_v0_4.json")["live_provider"]
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
        if live[name] != legacy[name]:
            raise RuntimeError(f"calibration/provider drift from v0.4 lock: {name}")
    if lock["budget_match"]["padding"] != "forbidden":
        raise RuntimeError("budget padding must remain forbidden")
    if tuple(lock["revision_envelope"]["provider_fields"]) != (
        "late_evidence_id",
        "relevant",
        "revision_cue",
        "invalidated_evidence_ids",
    ):
        raise RuntimeError("fixed revision envelope fields drifted")
    return lock


def _validate_gold_surface(case: CaseSpec, value: Mapping[str, Any]) -> None:
    if value.get("case_id") != case.case_id:
        raise ValueError("gold case_id mismatch")
    final = value["final"]
    if final["answer"] not in case.answer_choices:
        raise ValueError("gold final answer is outside the public answer choices")
    evidence_ids = set(case.evidence_ids)
    for name in ("evidence_ids", "invalidated_evidence_ids"):
        items = tuple(str(item) for item in final[name])
        if len(items) != len(set(items)) or not set(items) <= evidence_ids:
            raise ValueError(f"invalid gold final {name}")
    slots = {item.slot_id: set(item.allowed_values) for item in case.decision_slots}
    for fact in final["decision_facts"]:
        if fact["slot"] not in slots or fact["value"] not in slots[fact["slot"]]:
            raise ValueError("gold final fact is outside the public decision schema")
        if not set(fact["evidence_ids"]) <= evidence_ids:
            raise ValueError("gold final fact cites unknown evidence")
    grading = value["grading"]
    for name in ("required_evidence_ids", "forbidden_support_evidence_ids"):
        if not set(grading[name]) <= evidence_ids:
            raise ValueError(f"grading {name} cites unknown evidence")


def _load_suite() -> tuple[list[CaseSpec], dict[str, dict[str, Any]]]:
    fixture = _load_json(FIXTURE_PATH)
    gold_file = _load_json(GOLD_PATH)
    if fixture.get("status") != "DEV_DRAFT" or gold_file.get("status") != "DEV_DRAFT":
        raise ValueError("fixture and gold must remain DEV_DRAFT")
    cases = [CaseSpec.from_mapping(item) for item in fixture["cases"]]
    gold = {str(item["case_id"]): item for item in gold_file["cases"]}
    case_ids = [case.case_id for case in cases]
    if len(case_ids) != len(set(case_ids)) or set(case_ids) != set(gold):
        raise ValueError("fixture/gold case IDs do not form one exact unique set")
    for case in cases:
        _validate_gold_surface(case, gold[case.case_id])
    return cases, gold


class FixedRevisionEnvelope(RevisionContext):
    """Minimal DEV annotation shared by both arms, with no late-text duplication."""

    def to_provider_dict(self, *, include_late_evidence: bool) -> dict[str, Any]:
        del include_late_evidence
        return {
            "late_evidence_id": self.late_evidence.evidence_id,
            "relevant": self.relevant,
            "revision_cue": self.revision_cue,
            "invalidated_evidence_ids": list(self.invalidated_evidence_ids),
        }


def _build_fixed_revision_envelope(case: CaseSpec) -> FixedRevisionEnvelope:
    semantic = dict(case.late_evidence.semantic)
    required = {"revision_cue", "relevant", "invalidated_evidence_ids"}
    if not required <= set(semantic):
        raise ValueError(f"{case.case_id}: incomplete fixed revision annotation")
    if not isinstance(semantic["relevant"], bool):
        raise ValueError(f"{case.case_id}: fixed relevance must be a JSON boolean")
    invalidated = tuple(str(item) for item in semantic["invalidated_evidence_ids"])
    prior_ids = {item.evidence_id for item in case.initial_evidence}
    if len(invalidated) != len(set(invalidated)) or not set(invalidated) <= prior_ids:
        raise ValueError(f"{case.case_id}: invalid fixed invalidation roster")
    revision_cue = float(semantic["revision_cue"])
    if not math.isfinite(revision_cue) or not 0.0 <= revision_cue <= 1.0:
        raise ValueError(f"{case.case_id}: invalid fixed revision cue")
    return FixedRevisionEnvelope(
        late_evidence=case.late_evidence,
        topic="fixed_revision_envelope",
        stance=0.0,
        confidence=1.0,
        revision_cue=revision_cue,
        relevant=bool(semantic["relevant"]),
        invalidated_evidence_ids=invalidated,
        public_summary="not exposed to either provider arm",
    )


def _envelope_dict(context: FixedRevisionEnvelope) -> dict[str, Any]:
    return context.to_provider_dict(include_late_evidence=False)


def _direct_input(
    case: CaseSpec,
    context: FixedRevisionEnvelope,
) -> dict[str, Any]:
    return {
        "question": case.question,
        "answer_choices": list(case.answer_choices),
        "decision_slots": [item.to_dict() for item in case.decision_slots],
        "checkpoint_id": DIRECT_CHECKPOINT_ID,
        "all_raw_evidence": [item.public_dict() for item in case.all_evidence],
        "revision_context": _envelope_dict(context),
        "allowed_evidence_ids": list(case.evidence_ids),
    }


def _card_from_payload(payload: Any) -> ReasoningCard:
    return ReasoningCard(
        checkpoint_id=payload.checkpoint_id,
        claim=payload.claim,
        topic=payload.topic,
        stance=payload.stance,
        confidence=payload.confidence,
        evidence_ids=tuple(payload.evidence_ids),
        current_answer=payload.current_answer,
        revision_cue=payload.revision_cue,
        decision_facts=tuple(
            DecisionFact(
                slot=item.slot,
                value=item.value,
                evidence_ids=tuple(item.evidence_ids),
            )
            for item in payload.decision_facts
        ),
        invalidated_evidence_ids=tuple(payload.invalidated_evidence_ids),
    )


def _validate_direct_result(
    case: CaseSpec,
    context: FixedRevisionEnvelope,
    input_payload: Mapping[str, Any],
    result: CardResult,
) -> None:
    card = result.card
    if result.receipt.request_fingerprint != fingerprint(input_payload):
        raise ValueError("direct receipt/request fingerprint mismatch")
    if card.checkpoint_id != DIRECT_CHECKPOINT_ID:
        raise ValueError("direct provider returned the wrong checkpoint_id")
    if card.current_answer not in case.answer_choices:
        raise ValueError("direct provider returned an answer outside answer_choices")
    slot_values = {
        item.slot_id: set(item.allowed_values) for item in case.decision_slots
    }
    required_slots = {item.slot_id for item in case.decision_slots if item.required}
    observed_slots: set[str] = set()
    for fact in card.decision_facts:
        if fact.slot in observed_slots:
            raise ValueError(f"direct provider returned duplicate slot: {fact.slot}")
        observed_slots.add(fact.slot)
        if fact.slot not in slot_values:
            raise ValueError(f"direct provider returned unknown slot: {fact.slot}")
        if fact.value not in slot_values[fact.slot]:
            raise ValueError(f"direct provider returned disallowed value: {fact.slot}")
    missing = required_slots - observed_slots
    if missing:
        raise ValueError(f"direct provider omitted required slots: {sorted(missing)}")
    allowed = set(case.evidence_ids)
    active_support = set(card.evidence_ids)
    cited = set(card.evidence_ids) | set(card.invalidated_evidence_ids)
    for fact in card.decision_facts:
        active_support.update(fact.evidence_ids)
        cited.update(fact.evidence_ids)
    unknown = cited - allowed
    if unknown:
        raise ValueError(f"direct provider cited unknown evidence: {sorted(unknown)}")
    invalidated = set(context.invalidated_evidence_ids)
    stale = active_support & invalidated
    if stale:
        raise ValueError(
            f"direct provider used invalidated active support: {sorted(stale)}"
        )
    unexpected = set(card.invalidated_evidence_ids) - invalidated
    if unexpected:
        raise ValueError(
            f"direct provider invented invalidations: {sorted(unexpected)}"
        )


def _make_direct_provider(
    *,
    model: str,
    reasoning_effort: str,
    timeout_seconds: float,
    max_output_tokens: int,
) -> Any:
    from openai_reasoning_provider_v0_4 import (
        OpenAIResponseContractError,
        ReasoningCardPayload,
        _ResponsesClientBase,
    )

    class OpenAIDirectRawProvider(_ResponsesClientBase):
        def __init__(self) -> None:
            super().__init__(
                model=model,
                reasoning_effort=reasoning_effort,
                timeout_seconds=timeout_seconds,
            )
            self.max_output_tokens = int(max_output_tokens)

        @property
        def provenance(self) -> Mapping[str, Any]:
            return {
                "provider": "openai_responses",
                "model": self.model,
                "api": "responses.parse",
                "structured_output": "pydantic_v2",
                "reasoning_effort": self.reasoning_effort,
                "max_output_tokens": self.max_output_tokens,
                "instructions_fingerprint": fingerprint(DIRECT_INSTRUCTIONS),
                "store": False,
                "previous_response_id": False,
                "service_tier": "default",
                "truncation": "disabled",
                "retries": 0,
                "sdk_version": self.sdk_version,
            }

        def generate_final(
            self,
            case: CaseSpec,
            context: FixedRevisionEnvelope,
        ) -> tuple[CardResult, dict[str, Any]]:
            input_payload = _direct_input(case, context)
            payload, receipt = self._parse(
                input_payload=input_payload,
                instructions=DIRECT_INSTRUCTIONS,
                text_format=ReasoningCardPayload,
                max_output_tokens=self.max_output_tokens,
            )
            if not isinstance(payload, ReasoningCardPayload):
                raise OpenAIResponseContractError(
                    "parsed direct card has the wrong runtime type"
                )
            result = CardResult(card=_card_from_payload(payload), receipt=receipt)
            _validate_direct_result(case, context, input_payload, result)
            return result, input_payload

    return OpenAIDirectRawProvider()


def _receipt_from_dict(value: Mapping[str, Any]) -> ProviderReceipt:
    return ProviderReceipt(
        provider=value["provider"],
        requested_model=value.get("requested_model"),
        returned_model=value.get("returned_model"),
        logical_calls=int(value["logical_calls"]),
        api_calls=int(value["api_calls"]),
        latency_ms=float(value["latency_ms"]),
        request_fingerprint=value["request_fingerprint"],
        prompt_fingerprint=value["prompt_fingerprint"],
        usage=ProviderUsage(**value["usage"]),
        metadata=value["metadata"],
    )


def _accounting(receipts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return _aggregate_receipts([_receipt_from_dict(item) for item in receipts])


def _failure_category(error: BaseException) -> str:
    provider_category = getattr(error, "category", None)
    if provider_category == "transport_error":
        # The inherited v0.4 client labels every SDK call exception this way,
        # including some API/SDK parse failures. Do not overclaim transport.
        return "provider_call_exception_unclassified"
    if provider_category == "contract_error":
        return str(provider_category)
    if isinstance(error, (ValueError, AssertionError)):
        return "local_contract_error"
    return type(error).__name__


def _execute_direct_arm(
    *,
    case: CaseSpec,
    context: FixedRevisionEnvelope,
    provider: Any,
    configured_ceiling: int,
) -> dict[str, Any]:
    result, input_payload = provider.generate_final(case, context)
    return {
        "arm": "direct_raw_fixed_revision",
        "status": "completed",
        "configured_output_token_ceiling": configured_ceiling,
        "expected_api_calls": 1,
        "input_payload_fingerprint": fingerprint(input_payload),
        "final_card": result.card.to_dict(),
        "cards": [result.card.to_dict()],
        "call_records": [
            {
                "phase": "direct_one_shot",
                "sequence_offset": 0,
                "request_fingerprint": result.receipt.request_fingerprint,
                **result.to_dict(),
            }
        ],
    }


def _execute_full_arm(
    *,
    case: CaseSpec,
    context: FixedRevisionEnvelope,
    provider: Any,
    configured_ceiling: int,
) -> dict[str, Any]:
    cards, records = _run_calibration_full_sequence(
        case=case,
        provider=provider,
        phase="full_restart_calibration",
        evidence=case.all_evidence,
        base_cards=(),
        revision_context=context,
    )
    if len(cards) != len(case.all_evidence):
        raise AssertionError(
            "full restart did not regenerate one card per evidence chunk"
        )
    return {
        "arm": "full_restart",
        "status": "completed",
        "configured_output_token_ceiling": configured_ceiling,
        "expected_api_calls": len(case.all_evidence),
        "final_card": cards[-1].to_dict(),
        "cards": [item.to_dict() for item in cards],
        "call_records": records,
    }


def _run_calibration_full_sequence(
    *,
    case: CaseSpec,
    provider: Any,
    phase: str,
    evidence: Sequence[Any],
    base_cards: Sequence[ReasoningCard],
    revision_context: FixedRevisionEnvelope,
) -> tuple[list[ReasoningCard], list[dict[str, Any]]]:
    """Run the v0.4 public-card aperture without making unseen late raw citable."""

    cards = list(base_cards)
    records: list[dict[str, Any]] = []
    visible_order = list(_public_support_ids(cards[-1] if cards else None))
    all_case_ids = set(case.evidence_ids)
    late_id = revision_context.late_evidence.evidence_id
    for step_offset, chunk in enumerate(evidence):
        allowed_order = list(visible_order)
        if chunk.evidence_id not in allowed_order:
            allowed_order.append(chunk.evidence_id)
        for evidence_id in revision_context.invalidated_evidence_ids:
            if evidence_id not in allowed_order:
                allowed_order.append(evidence_id)
        # The original v0.4 helper adds late_id on every post-event replay step.
        # This calibration intentionally withholds it from active citation until
        # the raw late chunk is actually presented.
        if chunk.evidence_id == late_id and late_id not in allowed_order:
            allowed_order.append(late_id)
        if not set(allowed_order) <= all_case_ids:
            raise AssertionError("allowed evidence set escaped case boundary")
        request = CardRequest(
            case_id=case.case_id,
            question=case.question,
            answer_choices=case.answer_choices,
            decision_slots=case.decision_slots,
            checkpoint_id=f"card:{chunk.evidence_id}",
            previous_public_card=cards[-1] if cards else None,
            current_evidence=chunk,
            revision_context=revision_context,
            allowed_evidence_ids=tuple(allowed_order),
        )
        result = provider.generate(request)
        _validate_card_result(request, result)
        if chunk.evidence_id != late_id:
            active = set(result.card.evidence_ids)
            for fact in result.card.decision_facts:
                active.update(fact.evidence_ids)
            if late_id in active:
                raise ValueError(
                    "full provider cited late evidence before raw presentation"
                )
        cards.append(result.card)
        visible_order = list(_public_support_ids(result.card))
        records.append(
            {
                "phase": phase,
                "sequence_offset": step_offset,
                "current_evidence_id": chunk.evidence_id,
                "request_fingerprint": request.request_fingerprint,
                **result.to_dict(),
            }
        )
    return cards, records


def _arm_receipts(provider: Any, start_index: int) -> list[dict[str, Any]]:
    return provider.audit_receipts[start_index:]


def _run_one_arm(
    *,
    arm: str,
    case: CaseSpec,
    context: FixedRevisionEnvelope,
    provider: Any,
    configured_ceiling: int,
) -> dict[str, Any]:
    audit_start = len(provider.audit_receipts)
    try:
        if arm == "direct_raw_fixed_revision":
            payload = _execute_direct_arm(
                case=case,
                context=context,
                provider=provider,
                configured_ceiling=configured_ceiling,
            )
        elif arm == "full_restart":
            payload = _execute_full_arm(
                case=case,
                context=context,
                provider=provider,
                configured_ceiling=configured_ceiling,
            )
        else:
            raise ValueError(f"unknown calibration arm: {arm}")
    except Exception as error:
        receipts = _arm_receipts(provider, audit_start)
        return {
            "arm": arm,
            "status": "failed",
            "failure_category": _failure_category(error),
            "configured_output_token_ceiling": configured_ceiling,
            "expected_api_calls": 1
            if arm == "direct_raw_fixed_revision"
            else len(case.all_evidence),
            "final_card": None,
            "cards": [],
            "call_records": [],
            "receipts": receipts,
            "accounting": _accounting(receipts),
        }
    receipts = _arm_receipts(provider, audit_start)
    payload["receipts"] = receipts
    payload["accounting"] = _accounting(receipts)
    return payload


def _rotated_arm_order(trial_index: int, original_case_index: int) -> tuple[str, ...]:
    return (
        ARMS if (trial_index + original_case_index) % 2 == 0 else tuple(reversed(ARMS))
    )


def _rotated_cases(
    cases: Sequence[CaseSpec],
    trial_index: int,
) -> list[tuple[int, CaseSpec]]:
    indexed = list(enumerate(cases))
    if not indexed:
        return []
    shift = trial_index % len(indexed)
    return [*indexed[shift:], *indexed[:shift]]


def execute_suite(
    *,
    cases: Sequence[CaseSpec],
    direct_provider: Any,
    full_provider: Any,
    max_card_output_tokens: int,
    trials: int,
    mode: str,
    provider_lock: Mapping[str, Any],
) -> dict[str, Any]:
    """Execute gold-free paired calls; grading is deliberately a later phase."""

    if trials <= 0:
        raise ValueError("trials must be positive")
    if not cases:
        raise ValueError("cases must not be empty")
    runs: list[dict[str, Any]] = []
    total_runs = trials * len(cases)
    for trial_index in range(trials):
        for run_position, (original_case_index, case) in enumerate(
            _rotated_cases(cases, trial_index)
        ):
            context = _build_fixed_revision_envelope(case)
            arm_order = _rotated_arm_order(trial_index, original_case_index)
            ceiling = len(case.all_evidence) * int(max_card_output_tokens)
            pre_execution = {
                "case_input_fingerprint": fingerprint(case.public_context()),
                "revision_envelope": _envelope_dict(context),
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
                "case": case.trace_dict(),
                "case_input_fingerprint": pre_execution["case_input_fingerprint"],
                "revision_envelope": _envelope_dict(context),
                "revision_envelope_fingerprint": fingerprint(_envelope_dict(context)),
                "arm_order": list(arm_order),
                "pre_execution_fingerprint": fingerprint(pre_execution),
                "budget_match": {
                    "scope": "nominal_generated_token_ceiling_per_case",
                    "direct_raw_fixed_revision": ceiling,
                    "full_restart": ceiling,
                    "equal": True,
                    "realized_tokens_forced_equal": False,
                },
                "arms": {},
            }
            providers = {
                "direct_raw_fixed_revision": direct_provider,
                "full_restart": full_provider,
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
                "[calibration] {done}/{total} trial={trial} case={case} complete={complete}".format(
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
        "provider_provenance": {
            "direct_raw_fixed_revision": dict(direct_provider.provenance),
            "full_restart": dict(full_provider.provenance),
        },
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


def grade_executions(
    result: dict[str, Any],
    gold: Mapping[str, Mapping[str, Any]],
) -> None:
    """Attach gold only after every provider call has finished."""

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
            paired_outcome = "incomplete"
        else:
            direct_success = run["arms"]["direct_raw_fixed_revision"]["grade"][
                "machine_success"
            ]
            full_success = run["arms"]["full_restart"]["grade"]["machine_success"]
            if direct_success and full_success:
                paired_outcome = "both_pass"
            elif full_success:
                paired_outcome = "full_only"
            elif direct_success:
                paired_outcome = "direct_only"
            else:
                paired_outcome = "neither_pass"
        run["paired_outcome"] = paired_outcome


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
        item["exact_provider_tokens"] for item in accountings
    ):
        return None
    values = [item.get(name) for item in accountings]
    if any(value is None for value in values):
        return None
    return sum(int(value) for value in values if value is not None)


def summarize_runs(
    runs: Sequence[Mapping[str, Any]],
    *,
    locked_case_ids: Sequence[str],
    locked_trials: int,
) -> dict[str, Any]:
    arm_summary: dict[str, Any] = {}
    checks = (
        "answer_exact",
        "required_facts_exact",
        "stable_facts_exact",
        "required_evidence_present",
        "forbidden_support_absent",
        "expected_invalidated_evidence_marked",
    )
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
            and all(item["exact_provider_tokens"] for item in accountings),
            "input_tokens": _sum_exact_usage(accountings, "input_tokens"),
            "output_tokens": _sum_exact_usage(accountings, "output_tokens"),
            "reasoning_tokens": _sum_exact_usage(accountings, "reasoning_tokens"),
            "cached_input_tokens": _sum_exact_usage(accountings, "cached_input_tokens"),
        }

    paired_counts = {
        name: sum(run["paired_outcome"] == name for run in runs)
        for name in (
            "full_only",
            "direct_only",
            "both_pass",
            "neither_pass",
            "incomplete",
        )
    }
    by_case: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for run in runs:
        by_case[str(run["case_id"])].append(run)
    case_rows: list[dict[str, Any]] = []
    for case_id in locked_case_ids:
        case_runs = sorted(
            by_case.get(case_id, ()), key=lambda item: item["trial_index"]
        )
        if not case_runs:
            continue
        row: dict[str, Any] = {
            "case_id": case_id,
            "family": case_runs[0]["family"],
            "trials": len(case_runs),
            "complete_trials": sum(bool(item["complete"]) for item in case_runs),
            "stable_assessed": (
                len(case_runs) == locked_trials
                and {int(item["trial_index"]) for item in case_runs}
                == set(range(locked_trials))
            ),
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
                _stable_success(successes) if row["stable_assessed"] else None
            )
            row[f"{arm}_answer_exact"] = sum(answers)
            row[f"{arm}_stable_answer_exact"] = (
                _stable_success(answers) if row["stable_assessed"] else None
            )
        direct_stable = row["direct_raw_fixed_revision_stable_pass"]
        full_stable = row["full_restart_stable_pass"]
        row["stable_outcome"] = (
            "not_assessed"
            if not row["stable_assessed"]
            else "both"
            if direct_stable and full_stable
            else "full_only"
            if full_stable
            else "direct_only"
            if direct_stable
            else "neither"
        )
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
    stable_outcome_counts = {
        name: sum(row["stable_outcome"] == name for row in case_rows)
        for name in ("full_only", "direct_only", "both", "neither", "not_assessed")
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
    full_advantage = (
        stable["full_restart"]["pass_cases"]
        - stable["direct_raw_fixed_revision"]["pass_cases"]
    )
    if not all_locked_runs_complete:
        direction = "incomplete_no_direction"
    elif stable["full_restart"]["pass_cases"] == len(locked_case_ids) and stable[
        "direct_raw_fixed_revision"
    ]["pass_cases"] == len(locked_case_ids):
        direction = "ceiling_add_fresh_harder_dev"
    elif (
        full_advantage >= 2
        and stable_outcome_counts["direct_only"] == 0
        and stable["full_restart"]["answer_exact_cases"]
        >= stable["direct_raw_fixed_revision"]["answer_exact_cases"]
    ):
        direction = "full_primary_scaffold_candidate"
    elif (
        stable_outcome_counts["full_only"] > 0
        and stable_outcome_counts["direct_only"] > 0
    ):
        direction = "family_mixed_stratify"
    elif (
        stable["direct_raw_fixed_revision"]["pass_cases"]
        >= stable["full_restart"]["pass_cases"]
    ):
        direction = "repair_public_card_factorization_before_selective"
    else:
        direction = "inconclusive_or_family_mixed"
    return {
        "runs": len(runs),
        "completed_paired_runs": sum(bool(run["complete"]) for run in runs),
        "arm_summary": arm_summary,
        "paired_outcomes": paired_counts,
        "case_level": case_rows,
        "stable_case_summary": stable,
        "stable_outcome_counts": stable_outcome_counts,
        "exact_locked_case_trial_coverage": exact_locked_coverage,
        "locked_decision_ready": all_locked_runs_complete,
        "direction": direction,
        "selective_status": (
            "optional_efficiency_ablation_pending_same_block_quality_guardrail"
            if direction == "full_primary_scaffold_candidate"
            else "not_changed_by_this_two_arm_calibration"
        ),
    }


def _stored_receipts(
    result: Mapping[str, Any],
    arm: str,
) -> list[dict[str, Any]]:
    return [
        receipt for run in result["runs"] for receipt in run["arms"][arm]["receipts"]
    ]


def _validate_one_receipt(
    receipt: Mapping[str, Any],
    *,
    lock: Mapping[str, Any],
    expected_cap: int,
    expected_prompt_fingerprint: str,
) -> None:
    live = lock["live_provider"]
    if receipt["provider"] != "openai_responses":
        raise RuntimeError("unexpected provider in calibration receipt")
    if receipt["requested_model"] != live["model"]:
        raise RuntimeError("receipt requested model drift")
    if receipt["prompt_fingerprint"] != expected_prompt_fingerprint:
        raise RuntimeError("receipt prompt fingerprint drift")
    metadata = receipt["metadata"]
    if metadata["reasoning_effort"] != live["reasoning_effort"]:
        raise RuntimeError("receipt reasoning effort drift")
    if metadata["max_output_tokens"] != expected_cap:
        raise RuntimeError("receipt output-token cap drift")
    if metadata["store"] is not False or metadata["previous_response_id"] is not False:
        raise RuntimeError("receipt persisted provider state")
    if metadata["truncation"] != "disabled":
        raise RuntimeError("receipt truncation policy drift")
    if metadata["attempt"] != 1 or metadata["retry_count"] != 0:
        raise RuntimeError("receipt retry policy drift")
    outcome = metadata["attempt_outcome"]
    if outcome == "completed":
        if receipt["returned_model"] != live["model"]:
            raise RuntimeError("completed receipt returned model drift")
        if metadata["status"] != "completed":
            raise RuntimeError("completed receipt status drift")
        if metadata["service_tier"] != live["service_tier"]:
            raise RuntimeError("completed receipt service tier drift")
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
    direct_audit_receipts: Sequence[Mapping[str, Any]],
    full_audit_receipts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    direct_stored = _stored_receipts(result, "direct_raw_fixed_revision")
    full_stored = _stored_receipts(result, "full_restart")
    if canonical_json(direct_stored) != canonical_json(direct_audit_receipts):
        raise RuntimeError("direct provider audit receipts do not match trace receipts")
    if canonical_json(full_stored) != canonical_json(full_audit_receipts):
        raise RuntimeError("full provider audit receipts do not match trace receipts")
    card_cap = int(lock["live_provider"]["max_card_output_tokens"])
    prompt_fingerprints = {
        arm: str(result["provider_provenance"][arm]["instructions_fingerprint"])
        for arm in ARMS
    }
    for run in result["runs"]:
        envelope = run["revision_envelope"]
        if set(envelope) != {
            "late_evidence_id",
            "relevant",
            "revision_cue",
            "invalidated_evidence_ids",
        }:
            raise RuntimeError("trace revision envelope is not minimal")
        if run["budget_match"]["equal"] is not True:
            raise RuntimeError("paired configured token ceilings diverged")
        direct = run["arms"]["direct_raw_fixed_revision"]
        full = run["arms"]["full_restart"]
        direct_receipts = direct["receipts"]
        full_receipts = full["receipts"]
        direct_cap = int(direct["configured_output_token_ceiling"])
        if direct_cap != int(full["configured_output_token_ceiling"]):
            raise RuntimeError("paired configured token ceilings are unequal")
        for receipt in direct_receipts:
            _validate_one_receipt(
                receipt,
                lock=lock,
                expected_cap=direct_cap,
                expected_prompt_fingerprint=prompt_fingerprints[
                    "direct_raw_fixed_revision"
                ],
            )
        for receipt in full_receipts:
            _validate_one_receipt(
                receipt,
                lock=lock,
                expected_cap=card_cap,
                expected_prompt_fingerprint=prompt_fingerprints["full_restart"],
            )
        if direct["status"] == "completed":
            if len(direct_receipts) != 1 or len(direct["call_records"]) != 1:
                raise RuntimeError("completed direct arm call count drift")
            recorded = [item["receipt"] for item in direct["call_records"]]
            if canonical_json(recorded) != canonical_json(direct_receipts):
                raise RuntimeError("direct call records/receipts diverged")
        if full["status"] == "completed":
            expected = len(run["case"]["initial_evidence"]) + 1
            if len(full_receipts) != expected or len(full["call_records"]) != expected:
                raise RuntimeError("completed full arm call count drift")
            recorded = [item["receipt"] for item in full["call_records"]]
            if canonical_json(recorded) != canonical_json(full_receipts):
                raise RuntimeError("full call records/receipts diverged")
        direct_attempted_cap = sum(
            int(item["metadata"]["max_output_tokens"]) for item in direct_receipts
        )
        full_attempted_cap = sum(
            int(item["metadata"]["max_output_tokens"]) for item in full_receipts
        )
        if direct["status"] == "completed" and direct_attempted_cap != direct_cap:
            raise RuntimeError(
                "completed direct arm did not attempt its locked ceiling"
            )
        if full["status"] == "completed" and full_attempted_cap != direct_cap:
            raise RuntimeError("completed full arm did not attempt its locked ceiling")
    serialized = canonical_json({"direct": direct_stored, "full": full_stored}).lower()
    for forbidden in ("authorization", "openai_api_key", "bearer "):
        if forbidden in serialized:
            raise RuntimeError("secret-bearing field appeared in calibration receipts")
    return {
        "validated": True,
        "direct_receipts": len(direct_stored),
        "full_receipts": len(full_stored),
        "all_runs_complete": bool(result["execution_complete"]),
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
                    "paired_outcome": run["paired_outcome"],
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
    lines = [
        "# EBRT v0.4 Direct vs Full calibration — DEV report",
        "",
        f"Mode: `{result['mode']}`  ",
        f"Paired runs: `{summary['runs']}`  ",
        f"Complete paired runs: `{summary['completed_paired_runs']}/{summary['runs']}`  ",
        f"Locked decision ready: `{str(summary['locked_decision_ready']).lower()}`  ",
        f"Direction: `{summary['direction']}`",
        "",
        "Both arms received the same fixed, summary-free revision envelope. The",
        "comparison matches only the nominal cumulative `max_output_tokens` ceiling;",
        "realized tokens, calls, latency, price, and server compute were not matched.",
        "The interfaces require arm-specific instructions. Direct receives the envelope",
        "once, while Full receives the same metadata on each staged call; late raw text",
        "still appears exactly once per arm and is not citable early in Full.",
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
    paired = summary["paired_outcomes"]
    lines.extend(
        [
            "",
            "## Paired outcomes",
            "",
            f"- Full only: `{paired['full_only']}`",
            f"- Direct only: `{paired['direct_only']}`",
            f"- Both pass: `{paired['both_pass']}`",
            f"- Neither passes: `{paired['neither_pass']}`",
            f"- Incomplete: `{paired['incomplete']}`",
            "",
            "## Stable case outcomes",
            "",
            "A stable pass means at least two successes in the locked three trials.",
            "Smoke runs cannot produce a locked direction.",
            "",
            "| Case | Family | Direct | Full | Outcome |",
            "| --- | --- | ---: | ---: | --- |",
        ]
    )
    for row in summary["case_level"]:
        lines.append(
            "| {case} | {family} | {direct}/{trials} | {full}/{trials} | {outcome} |".format(
                case=row["case_id"],
                family=row["family"],
                direct=row["direct_raw_fixed_revision_successes"],
                full=row["full_restart_successes"],
                trials=row["trials"],
                outcome=row["stable_outcome"],
            )
        )
    lines.extend(
        [
            "",
            "## Claim boundary",
            "",
            "This contaminated DEV calibration does not evaluate the observer, does not",
            "match actual compute, and cannot establish general reasoning improvement.",
            "A Full advantage would support this staged protocol on these cases; it would",
            "not isolate public-card structure from the effect of repeated API calls.",
            "Selective replay was not executed and receives no formal same-block rank.",
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
    locked_decision_ready = bool(result["summary"]["locked_decision_ready"])
    execution_complete = bool(result["execution_complete"])
    manifest = {
        "schema_version": "ebrt-direct-full-calibration-manifest-v0.4",
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
        "artifact_sha256": {name: _sha256(output / name) for name in artifact_names},
        "fixture_sha256": _sha256(FIXTURE_PATH),
        "gold_sha256": _sha256(GOLD_PATH),
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "claim_boundary": {
            "nominal_output_ceiling_only": True,
            "observer_evaluated": False,
            "selective_replay_executed": False,
            "general_reasoning_improvement": False,
        },
    }
    _write_json(output / "manifest.json", manifest)
    return manifest


def _write_failure_bundle(
    output: Path,
    *,
    mode: str,
    source_snapshot: Mapping[str, str],
    direct_audit_receipts: Sequence[Mapping[str, Any]],
    full_audit_receipts: Sequence[Mapping[str, Any]],
    error: BaseException,
) -> None:
    failure_path = output / "failure.json"
    if failure_path.exists():
        return
    output.mkdir(parents=True, exist_ok=True)
    value = {
        "schema_version": "ebrt-direct-full-calibration-failure-v0.4",
        "status": "INCOMPLETE",
        "success_manifest": False,
        "promotion_eligible": False,
        "mode": mode,
        "failure_category": _failure_category(error),
        "source_sha256": dict(source_snapshot),
        "direct_audit_receipts": list(direct_audit_receipts),
        "full_audit_receipts": list(full_audit_receipts),
        "sanitization": "exception message raw responses headers and credentials omitted",
    }
    _write_json(failure_path, value)


def _gold_final_card(case: CaseSpec, gold: Mapping[str, Any]) -> ReasoningCard:
    state = gold["final"]
    return ReasoningCard(
        checkpoint_id=DIRECT_CHECKPOINT_ID,
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


def _fake_direct_result(
    card: ReasoningCard,
    input_payload: Mapping[str, Any],
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
            prompt_fingerprint=fingerprint(DIRECT_INSTRUCTIONS),
            usage=ProviderUsage(exact_provider_tokens=False),
            metadata={"plumbing_only": True},
        ),
    )


def _replace_card(card: ReasoningCard, **changes: Any) -> ReasoningCard:
    value = card.to_dict()
    value.update(changes)
    return ReasoningCard.from_mapping(value)


def _expect_value_error(action: Any) -> None:
    try:
        action()
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def _assert_full_visibility_guard(
    case: CaseSpec,
    gold: Mapping[str, Any],
) -> None:
    requests: list[CardRequest] = []
    scripted = ScriptedReasoningProvider(
        {
            case.case_id: {
                "initial": gold["initial"],
                "final": gold["final"],
            }
        }
    )

    class RecordingProvider:
        @property
        def provenance(self) -> Mapping[str, Any]:
            return scripted.provenance

        def generate(self, request: CardRequest) -> CardResult:
            requests.append(request)
            return scripted.generate(request)

    context = _build_fixed_revision_envelope(case)
    cards, _ = _run_calibration_full_sequence(
        case=case,
        provider=RecordingProvider(),
        phase="visibility_self_test",
        evidence=case.all_evidence,
        base_cards=(),
        revision_context=context,
    )
    seen: set[str] = set()
    late_id = case.late_evidence.evidence_id
    for request, card in zip(requests, cards, strict=True):
        seen.add(request.current_evidence.evidence_id)
        if request.current_evidence.evidence_id != late_id:
            if late_id in request.allowed_evidence_ids:
                raise AssertionError(
                    "late evidence became citable before raw presentation"
                )
        active = set(card.evidence_ids)
        for fact in card.decision_facts:
            active.update(fact.evidence_ids)
        if not active <= seen:
            raise AssertionError("full card actively cited unseen raw evidence")


def run_self_tests() -> dict[str, Any]:
    source_snapshot = dict(BOOT_SOURCE_SNAPSHOT)
    _assert_source_snapshot(source_snapshot)
    lock = _load_lock()
    cases, gold = _load_suite()
    if len(cases) != int(lock["fixtures"]["case_count"]):
        raise AssertionError("locked case count drift")
    card_cap = int(lock["live_provider"]["max_card_output_tokens"])
    expected_ceiling = int(
        lock["budget_match"]["expected_ceiling_for_current_six_chunk_cases"]
    )
    for case in cases:
        context = _build_fixed_revision_envelope(case)
        envelope = _envelope_dict(context)
        if tuple(envelope) != tuple(lock["revision_envelope"]["provider_fields"]):
            raise AssertionError("envelope provider surface drift")
        if any(
            name in envelope
            for name in (
                "topic",
                "stance",
                "confidence",
                "public_summary",
                "answer",
                "gold",
            )
        ):
            raise AssertionError("forbidden field leaked into fixed envelope")
        payload = _direct_input(case, context)
        if canonical_json(payload).count(case.late_evidence.text) != 1:
            raise AssertionError(
                "direct input must contain late raw evidence exactly once"
            )
        if case.late_evidence.text in canonical_json(envelope):
            raise AssertionError("late raw evidence leaked into fixed envelope")
        ceiling = len(case.all_evidence) * card_cap
        if ceiling != expected_ceiling:
            raise AssertionError("current case completion ceiling drift")
        card = _gold_final_card(case, gold[case.case_id])
        result = _fake_direct_result(card, payload)
        _validate_direct_result(case, context, payload, result)
        if not grade_card(card.to_dict(), gold[case.case_id])["machine_success"]:
            raise AssertionError("gold final card does not pass the shared grader")

        invalidated = context.invalidated_evidence_ids[0]
        _expect_value_error(
            lambda: _validate_direct_result(
                case,
                context,
                payload,
                _fake_direct_result(
                    _replace_card(
                        card,
                        evidence_ids=[*card.evidence_ids, invalidated],
                    ),
                    payload,
                ),
            )
        )
        _assert_full_visibility_guard(case, gold[case.case_id])
        _expect_value_error(
            lambda: _validate_direct_result(
                case,
                context,
                payload,
                _fake_direct_result(
                    _replace_card(
                        card, evidence_ids=[*card.evidence_ids, "UNKNOWN_ID"]
                    ),
                    payload,
                ),
            )
        )
        _expect_value_error(
            lambda: _validate_direct_result(
                case,
                context,
                payload,
                _fake_direct_result(
                    _replace_card(
                        card,
                        decision_facts=[
                            item.to_dict() for item in card.decision_facts[:-1]
                        ],
                    ),
                    payload,
                ),
            )
        )
        unexpected_invalidation = next(
            item
            for item in case.evidence_ids
            if item not in context.invalidated_evidence_ids
        )
        _expect_value_error(
            lambda: _validate_direct_result(
                case,
                context,
                payload,
                _fake_direct_result(
                    _replace_card(
                        card,
                        invalidated_evidence_ids=[
                            *card.invalidated_evidence_ids,
                            unexpected_invalidation,
                        ],
                    ),
                    payload,
                ),
            )
        )

    orders = [
        _rotated_arm_order(trial, case_index)
        for trial in range(int(lock["execution"]["trials"]))
        for case_index in range(len(cases))
    ]
    if set(orders) != {ARMS, tuple(reversed(ARMS))}:
        raise AssertionError("arm-order rotation does not cover AB and BA")
    if abs(orders.count(ARMS) - orders.count(tuple(reversed(ARMS)))) > 1:
        raise AssertionError("arm-order rotation is materially imbalanced")
    if tuple(inspect.signature(execute_suite).parameters).count("gold"):
        raise AssertionError("gold entered the execution function signature")
    if tuple(inspect.signature(_run_calibration_full_sequence).parameters) != (
        "case",
        "provider",
        "phase",
        "evidence",
        "base_cards",
        "revision_context",
    ):
        raise AssertionError("calibration full-sequence ABI drift")
    with tempfile.TemporaryDirectory() as temp_dir:
        failure_dir = Path(temp_dir) / "failure"
        _write_failure_bundle(
            failure_dir,
            mode="self_test",
            source_snapshot=source_snapshot,
            direct_audit_receipts=(),
            full_audit_receipts=(),
            error=RuntimeError("DO_NOT_SERIALIZE_THIS_SENTINEL"),
        )
        failure_text = (failure_dir / "failure.json").read_text(encoding="utf-8")
        if "DO_NOT_SERIALIZE_THIS_SENTINEL" in failure_text:
            raise AssertionError("failure bundle serialized a raw exception message")
        if (failure_dir / "manifest.json").exists():
            raise AssertionError("failure bundle wrote a success manifest")
    _assert_source_snapshot(source_snapshot)
    return {
        "status": "ok",
        "tests": 13,
        "cases": len(cases),
        "arm_orders": {
            "direct_first": orders.count(ARMS),
            "full_first": orders.count(tuple(reversed(ARMS))),
        },
        "nominal_output_ceiling_per_arm": expected_ceiling,
        "source_sha256": source_snapshot,
    }


def _select_cases(
    cases: Sequence[CaseSpec],
    requested_ids: Sequence[str],
) -> list[CaseSpec]:
    requested = tuple(str(item) for item in requested_ids)
    if len(requested) != len(set(requested)):
        raise ValueError("case IDs must not be repeated")
    by_id = {case.case_id: case for case in cases}
    unknown = set(requested) - set(by_id)
    if unknown:
        raise ValueError(f"unknown case IDs: {sorted(unknown)}")
    return [by_id[item] for item in requested]


def _run_live(
    *,
    output: Path,
    case_ids: Sequence[str],
    trials: int,
    mode: str,
) -> dict[str, Any]:
    if not 1 <= trials <= 3:
        raise ValueError("live calibration trials must be between 1 and 3")
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        raise RuntimeError("OPENAI_API_KEY is not available in the process environment")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(
            f"refusing to overwrite nonempty output directory: {output}"
        )
    source_snapshot = dict(BOOT_SOURCE_SNAPSHOT)
    direct_provider: Any | None = None
    full_provider: Any | None = None
    try:
        _assert_source_snapshot(source_snapshot)
        lock = _load_lock()
        cases, gold = _load_suite()
        selected = _select_cases(cases, case_ids)
        if not selected:
            raise ValueError("at least one live case is required")
        chunk_counts = {len(case.all_evidence) for case in selected}
        if len(chunk_counts) != 1:
            raise RuntimeError("one direct provider cap requires equal evidence counts")
        live = lock["live_provider"]
        card_cap = int(live["max_card_output_tokens"])
        direct_cap = next(iter(chunk_counts)) * card_cap
        direct_provider = _make_direct_provider(
            model=live["model"],
            reasoning_effort=live["reasoning_effort"],
            timeout_seconds=float(live["timeout_seconds"]),
            max_output_tokens=direct_cap,
        )
        from openai_reasoning_provider_v0_4 import OpenAIResponsesReasoningProvider

        full_provider = OpenAIResponsesReasoningProvider(
            model=live["model"],
            reasoning_effort=live["reasoning_effort"],
            timeout_seconds=float(live["timeout_seconds"]),
            max_output_tokens=card_cap,
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
            direct_provider=direct_provider,
            full_provider=full_provider,
            max_card_output_tokens=card_cap,
            trials=trials,
            mode=mode,
            provider_lock=provider_lock,
        )
        grade_executions(result, gold)
        locked_case_ids = [case.case_id for case in cases]
        result["summary"] = summarize_runs(
            result["runs"],
            locked_case_ids=locked_case_ids,
            locked_trials=int(lock["execution"]["trials"]),
        )
        result["summary"]["live_receipt_validation"] = validate_live_receipts(
            result,
            lock,
            direct_audit_receipts=direct_provider.audit_receipts,
            full_audit_receipts=full_provider.audit_receipts,
        )
        result["claim_boundary"] = list(lock["claim_boundary"])
        _assert_source_snapshot(source_snapshot)
        manifest = write_bundle(result, output, source_snapshot=source_snapshot)
    except Exception as error:
        _write_failure_bundle(
            output,
            mode=mode,
            source_snapshot=source_snapshot,
            direct_audit_receipts=(
                () if direct_provider is None else direct_provider.audit_receipts
            ),
            full_audit_receipts=(
                () if full_provider is None else full_provider.audit_receipts
            ),
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
        "self-test", help="run offline source, aperture, and grader tests"
    )
    smoke = subparsers.add_parser(
        "live-smoke",
        help="run the locked two-case one-trial API plumbing check",
    )
    smoke.add_argument("--output", type=Path, default=DEFAULT_SMOKE_OUTPUT)
    smoke.add_argument("--trials", type=int, default=1)
    smoke.add_argument("--case-id", action="append", dest="case_ids")
    dev = subparsers.add_parser(
        "live-dev",
        help="run the full 10-case repeated non-promotional DEV calibration",
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
                else "openai_live_dev_calibration"
            ),
        )
    print(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
