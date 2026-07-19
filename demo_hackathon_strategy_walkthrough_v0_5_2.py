#!/usr/bin/env python3
"""Two-call English product walkthrough for EBRT v0.5.2.

This is deliberately not a matched causal benchmark.  It shows one public
decision before a late correction and one controlled full-context regeneration
after that correction.  Semantic gold is parsed only after both provider
attempts have finished.
"""

from __future__ import annotations

import argparse
import copy
import dataclasses
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import socket
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence
from unittest import mock

from benchmark_controlled_raw_restart_v0_5_1 import (
    CONTROLLED_RESTART_INSTRUCTIONS,
    FORBIDDEN_PROVIDER_KEYS,
    _validate_receipt as _validate_v051_receipt,
)
from benchmark_language_replay_v0_4 import grade_card
from controlled_raw_restart_v0_5_1 import (
    ARM_GRADIENT,
    build_arm_bundle,
    build_case_temporal_suite,
    build_restart_payload,
    load_bridge_fixture,
    public_card_diff,
    validate_public_card,
)
from language_replay_bridge_v0_4 import (
    CARD_SCHEMA_VERSION,
    CardResult,
    DecisionFact,
    ProviderReceipt,
    ProviderUsage,
    ReasoningCard,
    canonical_json,
    fingerprint,
)
from temporal_adjoint_state_controller_v0_5_t import (
    TemporalAdjointStateController,
)


ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = "ebrt-hackathon-strategy-walkthrough-v0.5.2"
ARTIFACT_SCHEMA_VERSION = "ebrt-hackathon-strategy-artifact-v0.5.2"
PHASE_BEFORE = "before_event"
PHASE_AFTER = "controlled_after_event"
PHASE_ORDER = (PHASE_BEFORE, PHASE_AFTER)
LOCK_PATH = ROOT / "policy_lock_hackathon_strategy_walkthrough_v0_5_2.json"
FIXTURE_PATH = ROOT / "fixtures" / "hackathon_strategy_walkthrough_v0_5_2.json"
GOLD_PATH = ROOT / "fixtures" / "hackathon_strategy_walkthrough_v0_5_2_gold.json"
DEFAULT_LIVE_OUTPUT = (
    ROOT / "demo_results" / "hackathon_strategy_walkthrough_v0_5_2_live_r01"
)
ARTIFACT_FILES = ("demo.json", "calls.jsonl", "report.md", "manifest.json")

RESULT_CLAIM_BOUNDARY = (
    "This is one synthetic English product walkthrough, not a matched causal benchmark or fresh quality evaluation.",
    "The before and after calls have different visible evidence horizons; the after call also has a revision envelope and later run position.",
    "The public temporal program, semantic roles, evidence values, event scope, operator order, and terminal surrogate target are explicit oracle inputs.",
    "The provider receives a stop-gradient JSON projection; GPT, provider parsing, and final generation remain outside the gradient graph.",
    "Surrogate objective movement and actual public-output movement are reported separately; neither implies the other.",
    "A POLISH to PROVE change demonstrates this sealed walkthrough contract only, not a general reasoning, quality, efficiency, or causal advantage.",
)

EXPECTED_EXECUTION_LOCK = {
    "phase_order": list(PHASE_ORDER),
    "evidence_horizons": {
        PHASE_BEFORE: "ordered R1-R5 exactly once; no R6; no revision envelope",
        PHASE_AFTER: (
            "ordered R1-R6 exactly once; fixed gradient temporal-control envelope"
        ),
    },
    "expected_api_attempts": 2,
    "calls_per_phase": 1,
    "retry_policy": "one_attempt_no_retry",
    "provider_seed": "unset_not_claimed",
    "order_balance": "fixed_story_order_not_a_comparison_block",
    "semantic_gold_boundary": (
        "gold JSON is parsed and grading is attached only after both provider "
        "attempts; pre-call integrity checks may hash locked bytes"
    ),
    "private_chain_of_thought": "not_requested_not_persisted",
    "hidden_model_state": "not_accessed",
}
EXPECTED_RUNTIME_FIXED = {
    "provider": "openai_responses",
    "api": "responses.with_raw_response.parse+raw.parse",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "low",
    "service_tier": "default",
    "max_output_tokens": 4608,
    "timeout_seconds": 60,
    "sdk_retries": 0,
    "store": False,
    "previous_response_id": False,
    "truncation": "disabled",
}
LOCKED_SOURCE_PATHS = {
    "walkthrough_runner": "demo_hackathon_strategy_walkthrough_v0_5_2.py",
    "controlled_restart_bridge": "controlled_raw_restart_v0_5_1.py",
    "sealed_receipt_harness": "benchmark_controlled_raw_restart_v0_5_1.py",
    "temporal_controller": "temporal_adjoint_state_controller_v0_5_t.py",
    "provider_boundary": "openai_response_boundary_v0_4_3.py",
    "strict_grader": "benchmark_language_replay_v0_4.py",
    "public_card_schema": "language_replay_bridge_v0_4.py",
}
LOCKED_FIXTURE_PATHS = {
    "fixture": "fixtures/hackathon_strategy_walkthrough_v0_5_2.json",
    "gold": "fixtures/hackathon_strategy_walkthrough_v0_5_2_gold.json",
}
EXPECTED_WALKTHROUGH_DECISION_RULES = {
    "call_block_complete": (
        "both fixed provider attempts produce one sealed receipt and locally valid "
        "public card"
    ),
    "before_phase_pass": (
        "POLISH plus pre-event required support and stable video fact under the "
        "R1-R5 horizon"
    ),
    "before_stale_regrade": (
        "the unchanged before card fails the separate post-event final contract"
    ),
    "after_phase_pass": (
        "PROVE plus required corrected support, R3 invalidation, and stable video "
        "fact under R1-R6"
    ),
    "walkthrough_contract_passed": (
        "all call, phase, stale-regrade, output-diff, invalidation, and stability "
        "checks pass"
    ),
    "causal_interpretation": (
        "forbidden because evidence horizon, event envelope, and run position "
        "change together"
    ),
    "quality_promotion": (
        "forbidden; the frozen v0.5.1 A/B/C/D block remains the control-placement test"
    ),
}
COMMON_PHASE_KEYS = frozenset(
    {
        "phase_id",
        "run_position",
        "evidence_horizon",
        "status",
        "provider_input",
        "provider_input_fingerprint_sha256",
        "projection",
        "public_card",
        "receipt",
        "failure",
        "grade",
        "post_event_regrade",
    }
)
COMPLETED_PHASE_KEYS = COMMON_PHASE_KEYS
FAILED_PHASE_KEYS = COMMON_PHASE_KEYS | {
    "rejected_candidate_card",
    "observed_receipt_count",
}
FAILURE_RECORD_KEYS = frozenset({"exception_class", "category", "reason_code"})


class WalkthroughValidationError(RuntimeError):
    """A sealed v0.5.2 walkthrough invariant failed."""


def _canonical_json_bytes(value: Any, *, trailing_newline: bool = False) -> bytes:
    output = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return output + (b"\n" if trailing_newline else b"")


def _pretty_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_path(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise WalkthroughValidationError(f"expected JSON object: {path}")
    return value


def _json_clone(value: Any) -> Any:
    return json.loads(_canonical_json_bytes(value))


def _runtime() -> dict[str, str]:
    return {
        "python": sys.version.split()[0],
        "openai": importlib.metadata.version("openai"),
        "pydantic": importlib.metadata.version("pydantic"),
        "operating_system": platform.system(),
        "operating_system_release": platform.release(),
        "machine": platform.machine(),
    }


def _is_sha256(value: Any) -> bool:
    text = str(value)
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def _load_lock(*, verify_gold: bool = True) -> dict[str, Any]:
    lock = _load_json(LOCK_PATH)
    if set(lock) != {
        "schema_version",
        "status",
        "promotion_eligible",
        "execution",
        "runtime",
        "instructions_fingerprint_sha256",
        "sources",
        "fixtures",
        "walkthrough_decision_rules",
        "claim_boundary",
    }:
        raise WalkthroughValidationError("policy lock root schema drifted")
    if (
        lock["schema_version"]
        != "ebrt-hackathon-strategy-walkthrough-policy-lock-v0.5.2"
        or lock["status"] != "PREREGISTERED_PRODUCT_WALKTHROUGH"
        or lock["promotion_eligible"] is not False
    ):
        raise WalkthroughValidationError("policy lock identity drifted")
    execution = lock["execution"]
    if execution != EXPECTED_EXECUTION_LOCK:
        raise WalkthroughValidationError("execution geometry drifted")
    if lock["instructions_fingerprint_sha256"] != fingerprint(
        CONTROLLED_RESTART_INSTRUCTIONS
    ):
        raise WalkthroughValidationError("provider instructions drifted")
    sources = lock["sources"]
    if set(sources) != set(LOCKED_SOURCE_PATHS):
        raise WalkthroughValidationError("source label set drifted")
    for label, expected_path in LOCKED_SOURCE_PATHS.items():
        spec = sources[label]
        if not isinstance(spec, Mapping) or set(spec) != {"path", "sha256"}:
            raise WalkthroughValidationError(f"invalid source lock: {label}")
        if spec["path"] != expected_path or not _is_sha256(spec["sha256"]):
            raise WalkthroughValidationError(f"source identity drifted: {label}")
        path = ROOT / str(spec["path"])
        if not path.is_file() or _sha256_path(path) != spec["sha256"]:
            raise WalkthroughValidationError(f"source hash mismatch: {label}")
    fixtures = lock["fixtures"]
    if set(fixtures) != set(LOCKED_FIXTURE_PATHS):
        raise WalkthroughValidationError("fixture label set drifted")
    for label, expected_path in LOCKED_FIXTURE_PATHS.items():
        spec = fixtures[label]
        if not isinstance(spec, Mapping) or set(spec) != {"path", "sha256"}:
            raise WalkthroughValidationError(f"invalid fixture lock: {label}")
        if spec["path"] != expected_path or not _is_sha256(spec["sha256"]):
            raise WalkthroughValidationError(f"fixture identity drifted: {label}")
        if label == "gold" and not verify_gold:
            continue
        path = ROOT / str(spec["path"])
        if not path.is_file() or _sha256_path(path) != spec["sha256"]:
            raise WalkthroughValidationError(f"fixture hash mismatch: {label}")
    observed_runtime = _runtime()
    expected_runtime = lock["runtime"]
    runtime_version_keys = {"python", "openai", "pydantic", "machine"}
    if set(expected_runtime) != runtime_version_keys | set(
        EXPECTED_RUNTIME_FIXED
    ) or any(
        expected_runtime.get(key) != value
        for key, value in EXPECTED_RUNTIME_FIXED.items()
    ):
        raise WalkthroughValidationError("runtime policy drifted")
    for key in ("python", "openai", "pydantic", "machine"):
        if expected_runtime.get(key) != observed_runtime[key]:
            raise WalkthroughValidationError(f"runtime mismatch: {key}")
    if lock["walkthrough_decision_rules"] != EXPECTED_WALKTHROUGH_DECISION_RULES:
        raise WalkthroughValidationError("walkthrough decision rules drifted")
    if lock["claim_boundary"] != list(RESULT_CLAIM_BOUNDARY):
        raise WalkthroughValidationError("policy/result claim boundary drifted")
    return lock


def _verify_locked_fixture(lock: Mapping[str, Any], label: str) -> None:
    spec = lock["fixtures"][label]
    path = ROOT / str(spec["path"])
    if not path.is_file() or _sha256_path(path) != spec["sha256"]:
        raise WalkthroughValidationError(f"fixture hash mismatch: {label}")


def _source_snapshot(lock: Mapping[str, Any]) -> dict[str, str]:
    output = {
        str(label): _sha256_path(ROOT / str(spec["path"]))
        for label, spec in lock["sources"].items()
    }
    output.update(
        {
            f"fixture:{label}": _sha256_path(ROOT / str(spec["path"]))
            for label, spec in lock["fixtures"].items()
        }
    )
    return output


def _validate_snapshot_against_lock(
    snapshot: Mapping[str, str], lock: Mapping[str, Any]
) -> None:
    expected = {
        **{str(label): str(spec["sha256"]) for label, spec in lock["sources"].items()},
        **{
            f"fixture:{label}": str(spec["sha256"])
            for label, spec in lock["fixtures"].items()
        },
    }
    if dict(snapshot) != expected:
        raise WalkthroughValidationError("locked source/fixture snapshot drifted")


def _all_mapping_keys(value: Any) -> set[str]:
    output: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            output.add(str(key))
            output.update(_all_mapping_keys(child))
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes):
        for child in value:
            output.update(_all_mapping_keys(child))
    return output


def _projection_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        output = dict(value)
    elif hasattr(value, "to_dict"):
        output = dict(value.to_dict())
    elif dataclasses.is_dataclass(value):
        output = dataclasses.asdict(value)
    else:
        raise WalkthroughValidationError("projection is not serializable")
    return _json_clone(output)


def _walk_mappings(value: Any) -> Iterator[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _walk_mappings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_mappings(child)


def _validate_gold_free_payload(
    payload: Mapping[str, Any], fixture: Any, phase_id: str
) -> None:
    expected_keys = {
        "schema_version",
        "case_id",
        "question",
        "answer_choices",
        "decision_slots",
        "checkpoint_id",
        "all_raw_evidence",
        "allowed_evidence_ids",
        "revision_control_envelope",
    }
    if set(payload) != expected_keys:
        raise WalkthroughValidationError(f"provider payload schema drifted: {phase_id}")
    forbidden = _all_mapping_keys(payload) & FORBIDDEN_PROVIDER_KEYS
    if forbidden:
        raise WalkthroughValidationError(
            f"provider payload contains forbidden keys: {sorted(forbidden)}"
        )
    expected_evidence = (
        fixture.case.initial_evidence
        if phase_id == PHASE_BEFORE
        else fixture.case.all_evidence
    )
    expected_raw = [item.public_dict() for item in expected_evidence]
    expected_ids = [item.evidence_id for item in expected_evidence]
    if (
        payload["all_raw_evidence"] != expected_raw
        or payload["allowed_evidence_ids"] != expected_ids
    ):
        raise WalkthroughValidationError(f"evidence horizon drifted: {phase_id}")
    raw_ids = [str(item["evidence_id"]) for item in payload["all_raw_evidence"]]
    if len(raw_ids) != len(set(raw_ids)):
        raise WalkthroughValidationError(f"raw evidence duplicated: {phase_id}")
    if sum("all_raw_evidence" in item for item in _walk_mappings(payload)) != 1:
        raise WalkthroughValidationError("all_raw_evidence must occur exactly once")
    outside = dict(payload)
    outside.pop("all_raw_evidence")
    raw_pairs = {(entry.evidence_id, entry.text) for entry in fixture.case.all_evidence}
    for item in _walk_mappings(outside):
        if (item.get("evidence_id"), item.get("text")) in raw_pairs:
            raise WalkthroughValidationError("raw evidence duplicated outside horizon")
    late_id = fixture.case.late_evidence.evidence_id
    if phase_id == PHASE_BEFORE:
        if (
            payload["checkpoint_id"] != f"{fixture.case.case_id}:pre_event"
            or payload["revision_control_envelope"] is not None
            or late_id in _canonical_json_bytes(payload).decode("utf-8")
        ):
            raise WalkthroughValidationError("pre-event payload leaked late state")
    elif phase_id == PHASE_AFTER:
        if (
            payload["checkpoint_id"] != f"{fixture.case.case_id}:full_context_final"
            or payload["revision_control_envelope"] is None
        ):
            raise WalkthroughValidationError("after-event control payload drifted")
    else:
        raise WalkthroughValidationError(f"unknown phase: {phase_id}")


def _build_phase_payloads(
    fixture: Any,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    bundle = build_arm_bundle(fixture)
    controlled_projection = bundle[ARM_GRADIENT]
    after = _json_clone(build_restart_payload(fixture, controlled_projection))
    before = copy.deepcopy(after)
    before["checkpoint_id"] = f"{fixture.case.case_id}:pre_event"
    before["all_raw_evidence"] = [
        item.public_dict() for item in fixture.case.initial_evidence
    ]
    before["allowed_evidence_ids"] = [
        item.evidence_id for item in fixture.case.initial_evidence
    ]
    before["revision_control_envelope"] = None
    payloads = {PHASE_BEFORE: before, PHASE_AFTER: after}
    projections = {
        PHASE_BEFORE: {
            "phase_id": PHASE_BEFORE,
            "guidance_mode": "pre_event_raw_horizon_no_control",
            "prompt_envelope": None,
            "source_case_fingerprint_sha256": (fixture.source_case_fingerprint_sha256),
        },
        PHASE_AFTER: _projection_dict(controlled_projection),
    }
    for phase_id in PHASE_ORDER:
        _validate_gold_free_payload(payloads[phase_id], fixture, phase_id)
    if after != _json_clone(build_restart_payload(fixture, ARM_GRADIENT)):
        raise WalkthroughValidationError(
            "controlled payload is not exact bridge output"
        )
    return payloads, projections


def _state_as_card(state: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": CARD_SCHEMA_VERSION,
        "checkpoint_id": state["checkpoint_id"],
        "claim": state["claim"],
        "topic": state["topic"],
        "stance": state["stance"],
        "confidence": state["confidence"],
        "evidence_ids": list(state["evidence_ids"]),
        "current_answer": state["answer"],
        "revision_cue": state["revision_cue"],
        "decision_facts": copy.deepcopy(state["decision_facts"]),
        "invalidated_evidence_ids": list(state["invalidated_evidence_ids"]),
    }


def _validate_phase_card(
    fixture: Any,
    phase_id: str,
    card_value: Mapping[str, Any],
    receipt_value: Mapping[str, Any] | None = None,
) -> ReasoningCard:
    card = ReasoningCard.from_mapping(card_value)
    if _json_clone(card.to_dict()) != _json_clone(card_value):
        raise WalkthroughValidationError("public-card schema contains unknown fields")
    if phase_id == PHASE_AFTER:
        validated = validate_public_card(
            fixture, ARM_GRADIENT, card_value, receipt_value
        )
        if (
            validated.revision_cue != fixture.binding.event.revision_cue
            or validated.invalidated_evidence_ids
            != fixture.binding.event.invalidated_evidence_ids
        ):
            raise WalkthroughValidationError("after-event revision state drifted")
        return validated
    if phase_id != PHASE_BEFORE:
        raise WalkthroughValidationError(f"unknown phase: {phase_id}")
    allowed = {item.evidence_id for item in fixture.case.initial_evidence}
    if (
        card.checkpoint_id != f"{fixture.case.case_id}:pre_event"
        or card.current_answer not in fixture.case.answer_choices
        or card.revision_cue != 0.0
        or card.invalidated_evidence_ids
        or not card.evidence_ids
        or not set(card.evidence_ids) <= allowed
    ):
        raise WalkthroughValidationError("pre-event public-card horizon drifted")
    slot_specs = {item.slot_id: item for item in fixture.case.decision_slots}
    facts = {item.slot: item for item in card.decision_facts}
    if len(facts) != len(card.decision_facts) or set(facts) != set(slot_specs):
        raise WalkthroughValidationError("pre-event decision slots drifted")
    for slot, fact in facts.items():
        if (
            fact.value not in slot_specs[slot].allowed_values
            or not fact.evidence_ids
            or not set(fact.evidence_ids) <= allowed
        ):
            raise WalkthroughValidationError("pre-event decision fact drifted")
    return card


def _validate_gold(fixture: Any, gold: Mapping[str, Any]) -> None:
    expected_root = {
        "schema_version",
        "status",
        "case_id",
        "pre_event",
        "final",
        "grading",
        "claim_boundary",
        "fingerprint_sha256",
    }
    if set(gold) != expected_root:
        raise WalkthroughValidationError("gold root schema drifted")
    material = copy.deepcopy(dict(gold))
    observed_fingerprint = str(material.pop("fingerprint_sha256"))
    if observed_fingerprint != fingerprint(material):
        raise WalkthroughValidationError("gold fingerprint mismatch")
    if (
        gold["schema_version"] != "ebrt-hackathon-strategy-walkthrough-gold-v0.5.2"
        or gold["status"] != "LOCKED_DEMO_EXPECTATIONS_NOT_PROVIDER_INPUT"
        or gold["case_id"] != fixture.case.case_id
        or set(gold["grading"]) != {"pre_event", "final"}
    ):
        raise WalkthroughValidationError("gold identity drifted")
    expected_state_keys = {
        "checkpoint_id",
        "answer",
        "claim",
        "topic",
        "stance",
        "confidence",
        "revision_cue",
        "evidence_ids",
        "invalidated_evidence_ids",
        "decision_facts",
    }
    for phase_id, state_key in (
        (PHASE_BEFORE, "pre_event"),
        (PHASE_AFTER, "final"),
    ):
        state = gold[state_key]
        if set(state) != expected_state_keys:
            raise WalkthroughValidationError(f"gold state schema drifted: {state_key}")
        _validate_phase_card(fixture, phase_id, _state_as_card(state))
        grading = gold["grading"][state_key]
        if set(grading) != {
            "required_evidence_ids",
            "forbidden_support_evidence_ids",
            "required_facts",
            "stable_facts",
            "expected_invalidated_evidence_ids",
        }:
            raise WalkthroughValidationError(
                f"gold grading schema drifted: {state_key}"
            )
        probe = {"final": state, "grading": grading}
        if not grade_card(_state_as_card(state), probe)["machine_success"]:
            raise WalkthroughValidationError(f"gold does not self-grade: {state_key}")
    pre = gold["pre_event"]
    final = gold["final"]
    if (
        pre["answer"] != "POLISH"
        or final["answer"] != "PROVE"
        or "R3" not in pre["evidence_ids"]
        or "R4" in pre["evidence_ids"]
        or "R6" in pre["evidence_ids"]
        or "R3" not in final["invalidated_evidence_ids"]
        or "R3" in final["evidence_ids"]
        or "R6" not in final["evidence_ids"]
    ):
        raise WalkthroughValidationError("gold temporal story drifted")
    pre_stable = next(
        item for item in pre["decision_facts"] if item["slot"] == "video_constraint"
    )
    final_stable = next(
        item for item in final["decision_facts"] if item["slot"] == "video_constraint"
    )
    if pre_stable != final_stable:
        raise WalkthroughValidationError("gold stable video fact drifted")


def _load_gold(fixture: Any) -> dict[str, Any]:
    gold = _load_json(GOLD_PATH)
    _validate_gold(fixture, gold)
    return gold


def _grade_phase(
    card_value: Mapping[str, Any], gold: Mapping[str, Any], state_key: str
) -> dict[str, Any]:
    return grade_card(
        card_value,
        {"final": gold[state_key], "grading": gold["grading"][state_key]},
    )


def _provider_receipts(provider: Any) -> list[dict[str, Any]]:
    return json.loads(canonical_json(getattr(provider, "audit_receipts", ())))


def _failure_record(error: Exception) -> dict[str, Any]:
    return {
        "exception_class": type(error).__name__,
        "category": getattr(error, "category", None),
        "reason_code": getattr(error, "reason_code", None),
    }


def _validate_phase_receipt(
    receipt: Mapping[str, Any],
    *,
    phase_id: str,
    phase_status: str,
    mode: str,
    provider_input: Mapping[str, Any],
    lock: Mapping[str, Any],
) -> str:
    base_mode = (
        "scripted_plumbing_only"
        if mode == "scripted_plumbing_only"
        else "openai_live_dev_canary"
    )
    try:
        return _validate_v051_receipt(
            receipt,
            arm_id=phase_id,
            arm_status=phase_status,
            mode=base_mode,
            provider_input=provider_input,
            lock=lock,
        )
    except Exception as error:
        raise WalkthroughValidationError(
            f"receipt validation failed: {phase_id}"
        ) from error


def _execute_gold_free(
    fixture: Any,
    providers: Mapping[str, Any],
    phase_order: Sequence[str],
    *,
    mode: str,
    lock: Mapping[str, Any],
) -> dict[str, Any]:
    if tuple(phase_order) != PHASE_ORDER or set(providers) != set(PHASE_ORDER):
        raise WalkthroughValidationError("provider/phase schedule drifted")
    payloads, projections = _build_phase_payloads(fixture)
    executions: dict[str, Any] = {}
    for run_position, phase_id in enumerate(phase_order):
        provider = providers[phase_id]
        before_receipts = len(_provider_receipts(provider))
        candidate_card: dict[str, Any] | None = None
        try:
            result = provider.generate(payloads[phase_id])
            if not isinstance(result, CardResult):
                raise WalkthroughValidationError("provider returned wrong result type")
            candidate_card = result.card.to_dict()
            receipt = result.receipt.to_dict()
            observed = _provider_receipts(provider)[before_receipts:]
            if len(observed) != 1 or observed[0] != receipt:
                raise WalkthroughValidationError("provider receipt count drifted")
            _validate_phase_receipt(
                receipt,
                phase_id=phase_id,
                phase_status="completed",
                mode=mode,
                provider_input=payloads[phase_id],
                lock=lock,
            )
            _validate_phase_card(fixture, phase_id, candidate_card, receipt)
            executions[phase_id] = {
                "phase_id": phase_id,
                "run_position": run_position,
                "evidence_horizon": ("R1-R5" if phase_id == PHASE_BEFORE else "R1-R6"),
                "status": "completed",
                "provider_input": payloads[phase_id],
                "provider_input_fingerprint_sha256": fingerprint(payloads[phase_id]),
                "projection": projections[phase_id],
                "public_card": candidate_card,
                "receipt": receipt,
                "failure": None,
            }
        except Exception as error:
            observed = _provider_receipts(provider)[before_receipts:]
            executions[phase_id] = {
                "phase_id": phase_id,
                "run_position": run_position,
                "evidence_horizon": ("R1-R5" if phase_id == PHASE_BEFORE else "R1-R6"),
                "status": "failed",
                "provider_input": payloads[phase_id],
                "provider_input_fingerprint_sha256": fingerprint(payloads[phase_id]),
                "projection": projections[phase_id],
                "public_card": None,
                "rejected_candidate_card": candidate_card,
                "receipt": observed[0] if len(observed) == 1 else None,
                "observed_receipt_count": len(observed),
                "failure": _failure_record(error),
            }
    return {"phase_order": list(phase_order), "executions": executions}


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


def _surrogate_diagnostic(fixture: Any) -> dict[str, Any]:
    suite = build_case_temporal_suite(fixture)
    program = suite.materialize(fixture.binding.pair_id, fixture.binding.order_variant)
    result = TemporalAdjointStateController().optimize(program, "transition")
    control_map = result.to_execution_control_map()
    return {
        "status": control_map["status"],
        "source_control_map_fingerprint_sha256": control_map["fingerprint_sha256"],
        "controls": control_map["controls"],
        "objective_before": control_map["surrogate"]["objective_before"],
        "objective_after": control_map["surrogate"]["objective_after"],
        "gradient_boundary": control_map["controller"]["gradient_boundary"],
        "actual_output_participated": False,
    }


def _stable_video_preserved(phases: Mapping[str, Any]) -> bool:
    facts: list[dict[str, Any] | None] = []
    for phase_id in PHASE_ORDER:
        card = phases[phase_id]["public_card"]
        if card is None:
            return False
        facts.append(
            next(
                (
                    item
                    for item in card["decision_facts"]
                    if item["slot"] == "video_constraint"
                ),
                None,
            )
        )
    return facts[0] is not None and facts[0] == facts[1]


def _finalize_after_calls(
    fixture: Any,
    execution: Mapping[str, Any],
    gold: Mapping[str, Any],
    *,
    mode: str,
    source_snapshot: Mapping[str, str],
) -> dict[str, Any]:
    phases = copy.deepcopy(dict(execution["executions"]))
    for phase_id, state_key in (
        (PHASE_BEFORE, "pre_event"),
        (PHASE_AFTER, "final"),
    ):
        phase = phases[phase_id]
        phase["grade"] = (
            {"available": True, **_grade_phase(phase["public_card"], gold, state_key)}
            if phase["status"] == "completed"
            else _unavailable_grade()
        )
        phase["post_event_regrade"] = (
            {"available": True, **_grade_phase(phase["public_card"], gold, "final")}
            if phase_id == PHASE_BEFORE and phase["status"] == "completed"
            else None
        )
    before_card = phases[PHASE_BEFORE]["public_card"]
    after_card = phases[PHASE_AFTER]["public_card"]
    output_diff = (
        public_card_diff(fixture, before_card, after_card)
        if before_card is not None and after_card is not None
        else None
    )
    receipts = [
        phases[phase_id]["receipt"]
        for phase_id in PHASE_ORDER
        if phases[phase_id]["receipt"] is not None
    ]
    all_completed = all(
        phases[phase_id]["status"] == "completed"
        and phases[phase_id]["receipt"] is not None
        for phase_id in PHASE_ORDER
    )
    checks = {
        "both_calls_completed": all_completed,
        "before_matches_pre_event_contract": phases[PHASE_BEFORE]["grade"][
            "machine_success"
        ],
        "before_is_stale_under_post_event_contract": (
            phases[PHASE_BEFORE]["post_event_regrade"] is not None
            and not phases[PHASE_BEFORE]["post_event_regrade"]["machine_success"]
        ),
        "after_matches_post_event_contract": phases[PHASE_AFTER]["grade"][
            "machine_success"
        ],
        "answer_changes_polish_to_prove": (
            output_diff is not None
            and output_diff["answer_before"] == "POLISH"
            and output_diff["answer_after"] == "PROVE"
            and output_diff["answer_changed"] is True
        ),
        "stable_video_constraint_preserved": _stable_video_preserved(phases),
        "R3_invalidated_and_R6_added": (
            output_diff is not None
            and "R3" in output_diff["invalidated_added_ids"]
            and "R3" in output_diff["support_dropped_ids"]
            and "R6" in output_diff["support_added_ids"]
        ),
    }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "COMPLETE_CALL_BLOCK" if all_completed else "INCOMPLETE_CALL_BLOCK",
        "mode": mode,
        "case": {
            "case_id": fixture.case.case_id,
            "family": fixture.case.family,
            "fixture_id": fixture.fixture_id,
            "question": fixture.case.question,
        },
        "execution": {
            "phase_order": list(execution["phase_order"]),
            "expected_attempts": 2,
            "observed_receipts": len(receipts),
            "observed_api_calls": sum(int(item["api_calls"]) for item in receipts),
            "retry_policy": "one_attempt_no_retry",
            "semantic_gold_parsed_after_both_attempts": True,
        },
        "phases": phases,
        "output_diff": output_diff,
        "walkthrough_checks": checks,
        "surrogate_diagnostic": _surrogate_diagnostic(fixture),
        "surrogate_actual_separation": {
            "surrogate_result_source": "local temporal controller projection only",
            "actual_result_source": "post-call strict public-card grader",
            "surrogate_success_implies_actual_success": False,
        },
        "decision": {
            "call_block_complete": all_completed,
            "walkthrough_contract_passed": all(checks.values()),
            "causal_comparison": False,
            "promotion_eligible": False,
        },
        "source_snapshot_sha256": dict(source_snapshot),
        "claim_boundary": list(RESULT_CLAIM_BOUNDARY),
    }
    payload["fingerprint_sha256"] = _sha256_bytes(_canonical_json_bytes(payload))
    return payload


def _call_rows(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "phase_id": phase_id,
            "run_position": result["phases"][phase_id]["run_position"],
            "status": result["phases"][phase_id]["status"],
            "evidence_horizon": result["phases"][phase_id]["evidence_horizon"],
            "provider_input_fingerprint_sha256": result["phases"][phase_id][
                "provider_input_fingerprint_sha256"
            ],
            "receipt": result["phases"][phase_id]["receipt"],
            "failure": result["phases"][phase_id]["failure"],
        }
        for phase_id in result["execution"]["phase_order"]
    ]


def _report(result: Mapping[str, Any]) -> str:
    lines = [
        "# EBRT v0.5.2 — Hackathon Strategy Walkthrough",
        "",
        f"Call block: **{result['status']}**",
        f"Walkthrough contract: **{str(result['decision']['walkthrough_contract_passed']).upper()}**",
        "",
        f"> {result['case']['question']}",
        "",
        "| Phase | Visible evidence | Status | Phase pass | Answer | API calls |",
        "| --- | --- | --- | ---: | --- | ---: |",
    ]
    for phase_id in PHASE_ORDER:
        phase = result["phases"][phase_id]
        card = phase["public_card"]
        answer = "—" if card is None else card["current_answer"]
        calls = 0 if phase["receipt"] is None else phase["receipt"]["api_calls"]
        lines.append(
            f"| `{phase_id}` | {phase['evidence_horizon']} | {phase['status']} | "
            f"{str(phase['grade']['machine_success']).lower()} | {answer} | {calls} |"
        )
    stale = result["phases"][PHASE_BEFORE]["post_event_regrade"]
    lines.extend(
        [
            "",
            "## Public output diff",
            "",
            "```json",
            json.dumps(
                result["output_diff"], ensure_ascii=False, indent=2, sort_keys=True
            ),
            "```",
            "",
            "## Surrogate / actual separation",
            "",
            f"- Local surrogate objective: `{result['surrogate_diagnostic']['objective_before']['total']}` → `{result['surrogate_diagnostic']['objective_after']['total']}`",
            f"- Before under its own horizon: `{result['phases'][PHASE_BEFORE]['grade']['machine_success']}`",
            f"- Same Before card under post-event grading: `{None if stale is None else stale['machine_success']}`",
            f"- Controlled after-event output: `{result['phases'][PHASE_AFTER]['grade']['machine_success']}`",
            "- Actual provider output did not participate in local autograd.",
            "",
            "## Boundary",
            "",
            *[f"- {item}" for item in result["claim_boundary"]],
            "",
        ]
    )
    return "\n".join(lines)


def _materialize_bundle(
    result: Mapping[str, Any], lock: Mapping[str, Any]
) -> dict[str, bytes]:
    artifacts = {
        "demo.json": _pretty_json_bytes(result),
        "calls.jsonl": b"".join(
            _canonical_json_bytes(row, trailing_newline=True)
            for row in _call_rows(result)
        ),
        "report.md": _report(result).encode("utf-8"),
    }
    manifest = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "status": result["status"],
        "walkthrough_contract_passed": result["decision"][
            "walkthrough_contract_passed"
        ],
        "result_fingerprint_sha256": result["fingerprint_sha256"],
        "policy_lock": {
            "path": str(LOCK_PATH.relative_to(ROOT)),
            "sha256": _sha256_path(LOCK_PATH),
        },
        "source_snapshot_sha256": dict(result["source_snapshot_sha256"]),
        "runtime": _runtime(),
        "artifacts": {
            name: {"sha256": _sha256_bytes(value), "bytes": len(value)}
            for name, value in artifacts.items()
        },
        "claim_boundary": lock["claim_boundary"],
    }
    artifacts["manifest.json"] = _pretty_json_bytes(manifest)
    return artifacts


def _publish(output: Path, artifacts: Mapping[str, bytes]) -> None:
    if output.exists():
        raise WalkthroughValidationError(f"output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent)
    )
    try:
        for name, value in artifacts.items():
            (staging / name).write_bytes(value)
        validate_bundle(staging)
        os.replace(staging, output)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def write_bundle(
    output: Path, result: Mapping[str, Any], lock: Mapping[str, Any]
) -> dict[str, str]:
    artifacts = _materialize_bundle(result, lock)
    _publish(output, artifacts)
    validate_bundle(output)
    return {name: _sha256_bytes(value) for name, value in artifacts.items()}


def _validate_execution_record(
    fixture: Any,
    phase_id: str,
    phase: Mapping[str, Any],
    expected_payload: Mapping[str, Any],
    expected_projection: Mapping[str, Any],
    *,
    mode: str,
    lock: Mapping[str, Any],
) -> None:
    phase_status = phase.get("status")
    expected_keys = (
        COMPLETED_PHASE_KEYS
        if phase_status == "completed"
        else FAILED_PHASE_KEYS
        if phase_status == "failed"
        else frozenset()
    )
    if not expected_keys or set(phase) != expected_keys:
        raise WalkthroughValidationError(f"phase schema drifted: {phase_id}")
    expected_horizon = "R1-R5" if phase_id == PHASE_BEFORE else "R1-R6"
    if (
        phase["phase_id"] != phase_id
        or phase["run_position"] != PHASE_ORDER.index(phase_id)
        or phase["evidence_horizon"] != expected_horizon
        or phase["provider_input"] != expected_payload
        or phase["provider_input_fingerprint_sha256"] != fingerprint(expected_payload)
        or phase["projection"] != expected_projection
    ):
        raise WalkthroughValidationError(f"stored phase projection drifted: {phase_id}")
    _validate_gold_free_payload(phase["provider_input"], fixture, phase_id)
    receipt = phase["receipt"]
    if not isinstance(receipt, Mapping):
        raise WalkthroughValidationError(f"sealed receipt is missing: {phase_id}")
    outcome = _validate_phase_receipt(
        receipt,
        phase_id=phase_id,
        phase_status=phase_status,
        mode=mode,
        provider_input=expected_payload,
        lock=lock,
    )
    if phase_status == "completed":
        if (
            outcome != "completed"
            or phase["public_card"] is None
            or phase["failure"] is not None
        ):
            raise WalkthroughValidationError(
                f"completed phase shape drifted: {phase_id}"
            )
        _validate_phase_card(fixture, phase_id, phase["public_card"], phase["receipt"])
    else:
        failure = phase["failure"]
        rejected = phase["rejected_candidate_card"]
        if (
            phase["public_card"] is not None
            or not isinstance(failure, Mapping)
            or set(failure) != FAILURE_RECORD_KEYS
            or not isinstance(failure["exception_class"], str)
            or not failure["exception_class"]
            or phase["observed_receipt_count"] != 1
        ):
            raise WalkthroughValidationError(f"failed phase shape drifted: {phase_id}")
        if outcome == "completed":
            if not isinstance(rejected, Mapping):
                raise WalkthroughValidationError(
                    f"local rejection lacks candidate card: {phase_id}"
                )
            try:
                candidate = ReasoningCard.from_mapping(rejected)
            except Exception as error:
                raise WalkthroughValidationError(
                    f"rejected candidate schema is not public: {phase_id}"
                ) from error
            if _json_clone(candidate.to_dict()) != _json_clone(rejected):
                raise WalkthroughValidationError(
                    f"rejected candidate contains unknown fields: {phase_id}"
                )
            try:
                _validate_phase_card(fixture, phase_id, rejected, receipt)
            except Exception as error:
                if failure != _failure_record(error):
                    raise WalkthroughValidationError(
                        f"local rejection reason drifted: {phase_id}"
                    ) from error
            else:
                raise WalkthroughValidationError(
                    f"valid card was forged as a failure: {phase_id}"
                )
        else:
            expected_failure = {
                "exception_class": "OpenAIProviderBoundaryError",
                "category": "provider_boundary_error",
                "reason_code": receipt["metadata"]["failure_reason_code"],
            }
            if rejected is not None or failure != expected_failure:
                raise WalkthroughValidationError(
                    f"provider failure lineage drifted: {phase_id}"
                )


def validate_bundle(output: Path) -> None:
    lock = _load_lock()
    entries = tuple(sorted(item.name for item in output.iterdir()))
    if entries != tuple(sorted(ARTIFACT_FILES)):
        raise WalkthroughValidationError("artifact file set mismatch")
    if any(item.is_symlink() or not item.is_file() for item in output.iterdir()):
        raise WalkthroughValidationError("artifact entries must be regular files")
    manifest = _load_json(output / "manifest.json")
    if (
        manifest.get("schema_version") != ARTIFACT_SCHEMA_VERSION
        or set(manifest.get("artifacts", {}))
        != {"demo.json", "calls.jsonl", "report.md"}
        or manifest.get("runtime") != _runtime()
        or manifest.get("claim_boundary") != lock["claim_boundary"]
        or manifest.get("policy_lock")
        != {
            "path": str(LOCK_PATH.relative_to(ROOT)),
            "sha256": _sha256_path(LOCK_PATH),
        }
    ):
        raise WalkthroughValidationError("artifact manifest drifted")
    for name, record in manifest["artifacts"].items():
        value = (output / name).read_bytes()
        if _sha256_bytes(value) != record["sha256"] or len(value) != record["bytes"]:
            raise WalkthroughValidationError(f"artifact digest mismatch: {name}")
    result = _load_json(output / "demo.json")
    fingerprint_value = result.pop("fingerprint_sha256", None)
    if fingerprint_value != _sha256_bytes(_canonical_json_bytes(result)):
        raise WalkthroughValidationError("result fingerprint mismatch")
    result["fingerprint_sha256"] = fingerprint_value
    fixture = load_bridge_fixture(FIXTURE_PATH)
    gold = _load_gold(fixture)
    payloads, projections = _build_phase_payloads(fixture)
    if result["mode"] not in {
        "scripted_plumbing_only",
        "openai_live_product_walkthrough",
    }:
        raise WalkthroughValidationError("artifact mode drifted")
    for phase_id in PHASE_ORDER:
        _validate_execution_record(
            fixture,
            phase_id,
            result["phases"][phase_id],
            payloads[phase_id],
            projections[phase_id],
            mode=result["mode"],
            lock=lock,
        )
    execution = {
        "phase_order": list(PHASE_ORDER),
        "executions": {},
    }
    for phase_id in PHASE_ORDER:
        phase = copy.deepcopy(result["phases"][phase_id])
        phase.pop("grade")
        phase.pop("post_event_regrade")
        execution["executions"][phase_id] = phase
    expected = _finalize_after_calls(
        fixture,
        execution,
        gold,
        mode=result["mode"],
        source_snapshot=_source_snapshot(lock),
    )
    if result != expected:
        raise WalkthroughValidationError("stored derived result drifted")
    rows = [
        json.loads(line)
        for line in (output / "calls.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    if rows != _call_rows(result):
        raise WalkthroughValidationError("calls ledger drifted")
    expected_bundle = _materialize_bundle(result, lock)
    for name in ARTIFACT_FILES:
        if (output / name).read_bytes() != expected_bundle[name]:
            raise WalkthroughValidationError(f"artifact bytes drifted: {name}")


class _ScriptedProvider:
    """Deterministic plumbing provider; never hosted-model quality evidence."""

    def __init__(self, phase_id: str) -> None:
        self.phase_id = phase_id
        self.audit_receipts: list[dict[str, Any]] = []

    def generate(self, input_payload: Mapping[str, Any]) -> CardResult:
        before = self.phase_id == PHASE_BEFORE
        card = ReasoningCard(
            checkpoint_id=str(input_payload["checkpoint_id"]),
            claim=(
                "Under the current design-dominant brief, Team Spiral should prioritize UI polish."
                if before
                else "Under the corrected equal-weight guidance, Team Spiral should prioritize an end-to-end proof."
            ),
            topic="hackathon_final_build_priority",
            stance=1.0 if before else -1.0,
            confidence=0.9 if before else 1.0,
            evidence_ids=("R2", "R3", "R5") if before else ("R2", "R4", "R5", "R6"),
            current_answer="POLISH" if before else "PROVE",
            revision_cue=0.0 if before else 1.0,
            decision_facts=(
                DecisionFact(
                    slot="final_priority",
                    value="ADDITIONAL_UI_POLISH" if before else "END_TO_END_PROOF",
                    evidence_ids=("R2", "R3") if before else ("R2", "R4", "R6"),
                ),
                DecisionFact(
                    slot="demo_centerpiece",
                    value="POLISHED_SCREENS" if before else "LIVE_REASONING_DIFF",
                    evidence_ids=("R3",) if before else ("R2", "R4", "R6"),
                ),
                DecisionFact(
                    slot="video_constraint",
                    value="THREE_MINUTE_NARRATED",
                    evidence_ids=("R5",),
                ),
            ),
            invalidated_evidence_ids=() if before else ("R3",),
        )
        receipt = ProviderReceipt(
            provider="local_scripted_v0_5_1",
            requested_model=None,
            returned_model=None,
            logical_calls=1,
            api_calls=0,
            latency_ms=0.0,
            request_fingerprint=fingerprint(input_payload),
            prompt_fingerprint=fingerprint(CONTROLLED_RESTART_INSTRUCTIONS),
            usage=ProviderUsage(exact_provider_tokens=False),
            metadata={"attempt": 1, "plumbing_only": True, "retry_count": 0},
        )
        self.audit_receipts.append(receipt.to_dict())
        return CardResult(card=card, receipt=receipt)


@contextmanager
def _network_guard() -> Iterator[None]:
    with mock.patch.object(
        socket, "socket", side_effect=AssertionError("network used in offline test")
    ):
        yield


def run_self_tests() -> dict[str, Any]:
    lock = _load_lock(verify_gold=False)
    fixture = load_bridge_fixture(FIXTURE_PATH)
    payloads, _ = _build_phase_payloads(fixture)
    if [item["evidence_id"] for item in payloads[PHASE_BEFORE]["all_raw_evidence"]] != [
        "R1",
        "R2",
        "R3",
        "R4",
        "R5",
    ]:
        raise AssertionError("pre-event horizon drifted")
    if [item["evidence_id"] for item in payloads[PHASE_AFTER]["all_raw_evidence"]] != [
        "R1",
        "R2",
        "R3",
        "R4",
        "R5",
        "R6",
    ]:
        raise AssertionError("after-event horizon drifted")
    providers = {phase_id: _ScriptedProvider(phase_id) for phase_id in PHASE_ORDER}
    with _network_guard():
        execution = _execute_gold_free(
            fixture,
            providers,
            PHASE_ORDER,
            mode="scripted_plumbing_only",
            lock=lock,
        )
    _verify_locked_fixture(lock, "gold")
    gold = _load_gold(fixture)
    result = _finalize_after_calls(
        fixture,
        execution,
        gold,
        mode="scripted_plumbing_only",
        source_snapshot=_source_snapshot(lock),
    )
    if not result["decision"]["walkthrough_contract_passed"]:
        raise AssertionError("scripted walkthrough did not pass")
    if result["execution"]["observed_api_calls"] != 0:
        raise AssertionError("offline self-test recorded an API call")
    if not (
        result["surrogate_diagnostic"]["objective_after"]["total"]
        < result["surrogate_diagnostic"]["objective_before"]["total"]
        and result["surrogate_diagnostic"]["actual_output_participated"] is False
    ):
        raise AssertionError("surrogate/output separation drifted")

    import httpx
    from openai import OpenAI
    from openai_response_boundary_v0_4_3 import (
        _offline_response,
        make_openai_mapping_provider_v0_4_3,
    )

    after_card = copy.deepcopy(result["phases"][PHASE_AFTER]["public_card"])
    after_card.pop("schema_version", None)

    def offline_handler(request: Any) -> Any:
        return httpx.Response(
            200,
            headers={"x-request-id": "v052-offline-receipt"},
            json=_offline_response(after_card),
            request=request,
        )

    client = OpenAI(
        api_key="offline-v052-self-test",
        base_url="https://offline.invalid/v1",
        http_client=httpx.Client(transport=httpx.MockTransport(offline_handler)),
        max_retries=0,
    )
    try:
        runtime = lock["runtime"]
        provider = make_openai_mapping_provider_v0_4_3(
            model=runtime["model"],
            reasoning_effort=runtime["reasoning_effort"],
            timeout_seconds=float(runtime["timeout_seconds"]),
            max_output_tokens=int(runtime["max_output_tokens"]),
            instructions=CONTROLLED_RESTART_INSTRUCTIONS,
            client=client,
        )
        with _network_guard():
            live_result = provider.generate(payloads[PHASE_AFTER])
        _validate_phase_card(
            fixture,
            PHASE_AFTER,
            live_result.card.to_dict(),
            live_result.receipt.to_dict(),
        )
        _validate_v051_receipt(
            live_result.receipt.to_dict(),
            arm_id=PHASE_AFTER,
            arm_status="completed",
            mode="openai_live_dev_canary",
            provider_input=payloads[PHASE_AFTER],
            lock=lock,
        )
    finally:
        client.close()

    with tempfile.TemporaryDirectory(prefix="ebrt-v052-bundle-test-") as raw:
        root = Path(raw)
        output = root / "bundle"
        write_bundle(output, result, lock)
        validate_bundle(output)

        def expect_resigned_tamper_rejected(
            name: str, tampered_result: dict[str, Any]
        ) -> None:
            tampered_result = copy.deepcopy(tampered_result)
            tampered_result.pop("fingerprint_sha256", None)
            tampered_result["fingerprint_sha256"] = _sha256_bytes(
                _canonical_json_bytes(tampered_result)
            )
            tampered_output = root / name
            tampered_output.mkdir()
            for filename, value in _materialize_bundle(tampered_result, lock).items():
                (tampered_output / filename).write_bytes(value)
            try:
                validate_bundle(tampered_output)
            except WalkthroughValidationError:
                return
            raise AssertionError(f"resigned tamper was accepted: {name}")

        tampered_diff = copy.deepcopy(result)
        tampered_diff["output_diff"]["answer_after"] = "TAMPERED"
        expect_resigned_tamper_rejected("tampered-diff", tampered_diff)

        tampered_receipt = copy.deepcopy(result)
        tampered_receipt["phases"][PHASE_BEFORE]["receipt"]["provider"] = "forged"
        expect_resigned_tamper_rejected("tampered-receipt", tampered_receipt)

        tampered_payload = copy.deepcopy(result)
        tampered_payload["phases"][PHASE_BEFORE]["provider_input"]["gold"] = True
        expect_resigned_tamper_rejected("tampered-payload", tampered_payload)

        tampered_stable = copy.deepcopy(result)
        for fact in tampered_stable["phases"][PHASE_AFTER]["public_card"][
            "decision_facts"
        ]:
            if fact["slot"] == "video_constraint":
                fact["value"] = "UNKNOWN"
        expect_resigned_tamper_rejected("tampered-stable", tampered_stable)

        missing_receipt = copy.deepcopy(result)
        missing_receipt["phases"][PHASE_BEFORE]["receipt"] = None
        expect_resigned_tamper_rejected("missing-completed-receipt", missing_receipt)

        unknown_phase_field = copy.deepcopy(result)
        unknown_phase_field["phases"][PHASE_BEFORE]["private_chain_of_thought"] = (
            "must never persist"
        )
        expect_resigned_tamper_rejected("unknown-phase-field", unknown_phase_field)

        unknown_card_field = copy.deepcopy(result)
        unknown_card_field["phases"][PHASE_BEFORE]["public_card"][
            "private_chain_of_thought"
        ] = "must never persist"
        expect_resigned_tamper_rejected("unknown-card-field", unknown_card_field)

        unknown_fact_field = copy.deepcopy(result)
        unknown_fact_field["phases"][PHASE_BEFORE]["public_card"]["decision_facts"][0][
            "reasoning_text"
        ] = "must never persist"
        expect_resigned_tamper_rejected("unknown-fact-field", unknown_fact_field)

        forged_failure = copy.deepcopy(result)
        forged_phase = forged_failure["phases"][PHASE_BEFORE]
        forged_phase["status"] = "failed"
        forged_phase["rejected_candidate_card"] = copy.deepcopy(
            forged_phase["public_card"]
        )
        forged_phase["public_card"] = None
        forged_phase["observed_receipt_count"] = 2
        forged_phase["failure"] = {
            "exception_class": "ForgedFailure",
            "category": None,
            "reason_code": None,
        }
        expect_resigned_tamper_rejected("forged-failure", forged_failure)

        fault_output = root / "atomic-fault"
        module = sys.modules[__name__]
        with mock.patch.object(
            module,
            "validate_bundle",
            side_effect=WalkthroughValidationError("injected validation fault"),
        ):
            try:
                _publish(fault_output, _materialize_bundle(result, lock))
            except WalkthroughValidationError:
                pass
            else:
                raise AssertionError("atomic validation fault was not raised")
        if fault_output.exists() or tuple(root.glob(".atomic-fault.staging-*")):
            raise AssertionError("atomic validation fault left published state")

    def expect_policy_tamper_rejected(name: str, tampered: dict[str, Any]) -> None:
        original_load_json = _load_json

        def substituted(path: Path) -> dict[str, Any]:
            if path == LOCK_PATH:
                return copy.deepcopy(tampered)
            return original_load_json(path)

        with mock.patch.object(
            sys.modules[__name__], "_load_json", side_effect=substituted
        ):
            try:
                _load_lock(verify_gold=False)
            except WalkthroughValidationError:
                return
        raise AssertionError(f"policy tamper was accepted: {name}")

    runtime_tamper = copy.deepcopy(lock)
    runtime_tamper["runtime"]["model"] = "forged-model"
    runtime_tamper["runtime"]["max_output_tokens"] = 1
    expect_policy_tamper_rejected("runtime", runtime_tamper)

    execution_tamper = copy.deepcopy(lock)
    execution_tamper["execution"]["evidence_horizons"][PHASE_BEFORE] = "forged"
    expect_policy_tamper_rejected("execution", execution_tamper)

    source_tamper = copy.deepcopy(lock)
    source_tamper["sources"].pop("provider_boundary")
    source_tamper["sources"]["unknown"] = {
        "path": "README.md",
        "sha256": _sha256_path(ROOT / "README.md"),
    }
    expect_policy_tamper_rejected("sources", source_tamper)

    return {
        "status": "PASS",
        "checks": [
            "R1-R5 pre-event payload excludes R6 and has no revision envelope",
            "R1-R6 after-event payload exactly equals the controlled v0.5.1 bridge projection",
            "semantic gold is parsed only after both scripted attempts",
            "pre-event strict pass, post-event stale regrade, and controlled final strict pass remain distinct",
            "POLISH-to-PROVE public diff preserves the three-minute narration constraint",
            "local surrogate movement remains separate from actual provider output",
            "mock-transport live receipt seals validate without network access",
            "exact phase/card/fact schemas reject unknown fields and completed phases without receipts",
            "failed-phase lineage is bound to one receipt, rejected candidate, and matching failure code",
            "runtime, execution, source-label, diff, payload, and stable-fact policy tampering is rejected",
            "artifact publication remains atomic under an injected validation fault",
        ],
        "result_fingerprint_sha256": result["fingerprint_sha256"],
        "claim_boundary": "Offline scripted plumbing only; no hosted-model quality evidence.",
    }


def _make_live_providers(lock: Mapping[str, Any]) -> dict[str, Any]:
    from openai_response_boundary_v0_4_3 import (
        make_openai_mapping_provider_v0_4_3,
    )

    runtime = lock["runtime"]
    return {
        phase_id: make_openai_mapping_provider_v0_4_3(
            model=runtime["model"],
            reasoning_effort=runtime["reasoning_effort"],
            timeout_seconds=float(runtime["timeout_seconds"]),
            max_output_tokens=int(runtime["max_output_tokens"]),
            instructions=CONTROLLED_RESTART_INSTRUCTIONS,
        )
        for phase_id in PHASE_ORDER
    }


def preflight() -> dict[str, Any]:
    lock = _load_lock(verify_gold=False)
    fixture = load_bridge_fixture(FIXTURE_PATH)
    payloads, _ = _build_phase_payloads(fixture)
    source_snapshot = _source_snapshot(lock)
    # Integrity-only hash check: semantic gold JSON is still not parsed here.
    _validate_snapshot_against_lock(source_snapshot, lock)
    if not os.environ.get("OPENAI_API_KEY"):
        raise WalkthroughValidationError("OPENAI_API_KEY is unavailable")
    providers = _make_live_providers(lock)
    provenances = [provider.provenance for provider in providers.values()]
    if len({canonical_json(item) for item in provenances}) != 1:
        raise WalkthroughValidationError("provider configuration differs by phase")
    if any(provider.audit_receipts for provider in providers.values()):
        raise WalkthroughValidationError("preflight recorded a provider call")
    return {
        "status": "READY",
        "case_id": fixture.case.case_id,
        "question": fixture.case.question,
        "phase_order": list(PHASE_ORDER),
        "expected_api_attempts": 2,
        "provider": provenances[0],
        "payload_fingerprints": {
            phase_id: fingerprint(payloads[phase_id]) for phase_id in PHASE_ORDER
        },
        "source_snapshot_sha256": source_snapshot,
        "claim_boundary": list(RESULT_CLAIM_BOUNDARY),
    }


def run_live(output: Path) -> dict[str, Any]:
    if output.exists():
        raise WalkthroughValidationError(f"output already exists: {output}")
    lock = _load_lock(verify_gold=False)
    before_sources = _source_snapshot(lock)
    _validate_snapshot_against_lock(before_sources, lock)
    ready = preflight()
    fixture = load_bridge_fixture(FIXTURE_PATH)
    providers = _make_live_providers(lock)
    execution = _execute_gold_free(
        fixture,
        providers,
        PHASE_ORDER,
        mode="openai_live_product_walkthrough",
        lock=lock,
    )
    after_sources = _source_snapshot(lock)
    if after_sources != before_sources:
        raise WalkthroughValidationError(
            "source graph changed during provider execution"
        )
    _validate_snapshot_against_lock(after_sources, lock)
    _verify_locked_fixture(lock, "gold")
    gold = _load_gold(fixture)
    result = _finalize_after_calls(
        fixture,
        execution,
        gold,
        mode="openai_live_product_walkthrough",
        source_snapshot=before_sources,
    )
    sha256 = write_bundle(output, result, lock)
    return {
        "status": result["status"],
        "walkthrough_contract_passed": result["decision"][
            "walkthrough_contract_passed"
        ],
        "output": str(output),
        "answers": {
            phase_id: (
                None
                if result["phases"][phase_id]["public_card"] is None
                else result["phases"][phase_id]["public_card"]["current_answer"]
            )
            for phase_id in PHASE_ORDER
        },
        "expected_api_attempts": ready["expected_api_attempts"],
        "observed_api_calls": result["execution"]["observed_api_calls"],
        "result_fingerprint_sha256": result["fingerprint_sha256"],
        "artifact_sha256": sha256,
    }


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("self-test")
    subparsers.add_parser("preflight")
    live = subparsers.add_parser("live-demo")
    live.add_argument("--output", type=Path, default=DEFAULT_LIVE_OUTPUT)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--artifact-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "self-test":
        _print_json(run_self_tests())
    elif args.command == "preflight":
        _print_json(preflight())
    elif args.command == "live-demo":
        _print_json(run_live(args.output))
    else:
        validate_bundle(args.artifact_dir)
        _print_json({"status": "VALID", "artifact_dir": str(args.artifact_dir)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
