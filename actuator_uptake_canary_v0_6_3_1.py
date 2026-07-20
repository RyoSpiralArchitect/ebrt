#!/usr/bin/env python3
"""EBRT v0.6.3.1 observable-actuator uptake canary.

This is a network-zero measurement-repair monolith.  It compiles one real
local float64 backward signal into a deterministic permutation of immutable
evidence chunks, then freezes four provider payloads:

Z  neutral evidence order
X  preregistered correction-first positive control
C  geometry-matched path-block anti-placement
D  path-block placement selected by one local backward pass

The hosted model is not differentiated.  The only primary public action is an
opaque ``selected_closure_id``.  Known but stale or incomplete closures remain
valid observations; only malformed envelopes and unknown IDs are structural
errors.  No live provider call is authorized by this module.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import platform
import socket
import tempfile
from contextlib import contextmanager
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any, Iterator, Literal, Mapping, Sequence
from unittest import mock

import torch
from pydantic import BaseModel, ConfigDict, Field, ValidationError


ROOT = Path(__file__).resolve().parent
FIXTURE_PATH = ROOT / "fixtures" / "actuator_uptake_canary_v0_6_3_1.json"
GOLD_PATH = ROOT / "fixtures" / "actuator_uptake_canary_gold_v0_6_3_1.json"
POLICY_LOCK_PATH = ROOT / "policy_lock_actuator_uptake_canary_v0_6_3_1.json"
NOTE_PATH = ROOT / "docs" / "RND_ACTUATOR_UPTAKE_CANARY_V0_6_3_1.md"
DEFAULT_ARTIFACT_DIR = ROOT / "artifacts" / "actuator_uptake_canary_v0_6_3_1_preflight"

FIXTURE_SCHEMA = "ebrt-actuator-uptake-canary-fixture-v0.6.3.1"
GOLD_SCHEMA = "ebrt-actuator-uptake-canary-gold-v0.6.3.1"
PROVIDER_INPUT_SCHEMA = "ebrt-actuator-uptake-provider-input-v0.6.3.1"
PROVIDER_OUTPUT_SCHEMA = "ebrt-actuator-uptake-provider-output-v0.6.3.1"
COMPILED_OUTPUT_SCHEMA = "ebrt-actuator-uptake-compiled-output-v0.6.3.1"
ENDPOINT_SCHEMA = "ebrt-actuator-uptake-endpoint-v0.6.3.1"
PROJECTION_SCHEMA = "ebrt-actuator-uptake-projection-v0.6.3.1"
CONTROLLER_SCHEMA = "ebrt-actuator-uptake-controller-audit-v0.6.3.1"
SELF_TEST_SCHEMA = "ebrt-actuator-uptake-self-test-v0.6.3.1"
MANIFEST_SCHEMA = "ebrt-actuator-uptake-preflight-manifest-v0.6.3.1"
POLICY_SCHEMA = "ebrt-actuator-uptake-policy-lock-v0.6.3.1"

OPERATOR = "evidence_permutation"
ARMS = ("Z", "C", "D", "X")
FLOAT_TOLERANCE = 1.0e-12

FORBIDDEN_PROVIDER_KEYS = frozenset(
    {
        "arm",
        "arm_id",
        "treatment",
        "treatment_id",
        "gradient",
        "controller",
        "local_controller",
        "path_blocks",
        "preferred_path",
        "target_closure",
        "target_closure_id",
        "positive_control_target_closure_id",
        "gradient_target_closure_id",
        "quality_valid_closure_ids",
        "closure_roles",
        "gold",
        "grade",
        "sham",
        "anti_placement",
        "expected_answer",
        "correct_answer",
    }
)

HARD_GATE_IDS = (
    "strict_fixture_contract",
    "opaque_candidate_ids",
    "equal_candidate_cardinality",
    "real_float64_backward",
    "finite_difference_agreement",
    "gradient_path_preference_nonzero",
    "exact_z_x_c_d_permutations",
    "matched_d_c_geometry",
    "d_alignment_exceeds_c",
    "immutable_chunk_multiset",
    "only_evidence_order_differs",
    "provider_payloads_leak_free",
    "four_payloads_presealed",
    "all_known_closures_roundtrip",
    "semantic_failures_are_endpoints",
    "unknown_closure_rejected",
    "decision_classifier_total",
    "deterministic_double_projection",
    "canonical_artifact_directory_exact",
    "network_calls_zero",
)

CANONICAL_ARTIFACT_FILENAMES = frozenset(
    {
        "projection_bundle.json",
        "controller_audit.json",
        "self_test.json",
        "manifest.json",
    }
)


class UptakeCanaryError(ValueError):
    """Fail-closed structural error with a stable public reason code."""

    def __init__(self, reason_code: str, detail: str = "") -> None:
        self.reason_code = reason_code
        super().__init__(reason_code if not detail else f"{reason_code}: {detail}")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class UptakeProviderOutput(_StrictModel):
    schema_version: Literal[PROVIDER_OUTPUT_SCHEMA]
    checkpoint_id: str = Field(min_length=1, max_length=160)
    current_answer: str = Field(min_length=1, max_length=160)
    record_format: str = Field(min_length=1, max_length=160)
    selected_closure_id: str = Field(min_length=1, max_length=96)
    reviewed_evidence_ids: list[str] = Field(min_length=3, max_length=3)


def _require(condition: bool, reason: str, detail: str = "") -> None:
    if not condition:
        raise UptakeCanaryError(reason, detail)


def _reject_constant(value: str) -> Any:
    raise UptakeCanaryError("NONFINITE_JSON", value)


def _reject_duplicates(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise UptakeCanaryError("DUPLICATE_JSON_KEY", key)
        output[key] = value
    return output


def _reject_nonfinite_numbers(value: Any, *, label: str) -> None:
    if isinstance(value, float):
        _require(math.isfinite(value), "NONFINITE_JSON", label)
    elif isinstance(value, Mapping):
        for child in value.values():
            _reject_nonfinite_numbers(child, label=label)
    elif isinstance(value, list):
        for child in value:
            _reject_nonfinite_numbers(child, label=label)


def _strict_json_bytes(value: bytes, *, label: str) -> Any:
    try:
        text = value.decode("utf-8")
    except UnicodeDecodeError as error:
        raise UptakeCanaryError("NON_UTF8_JSON", label) from error
    try:
        parsed = json.loads(
            text,
            object_pairs_hook=_reject_duplicates,
            parse_constant=_reject_constant,
        )
    except UptakeCanaryError:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise UptakeCanaryError("INVALID_JSON", label) from error
    _reject_nonfinite_numbers(parsed, label=label)
    return parsed


def _strict_load(path: Path) -> dict[str, Any]:
    value = _strict_json_bytes(path.read_bytes(), label=str(path))
    _require(isinstance(value, dict), "JSON_ROOT_NOT_OBJECT", str(path))
    return value


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _canonical_pretty_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _clone(value: Any) -> Any:
    return copy.deepcopy(value)


def _without_fingerprint(value: Mapping[str, Any]) -> dict[str, Any]:
    output = dict(value)
    output.pop("fingerprint_sha256", None)
    return output


def _seal(value: Mapping[str, Any]) -> dict[str, Any]:
    output = _without_fingerprint(value)
    output["fingerprint_sha256"] = _fingerprint(output)
    return output


def _validate_fingerprint(value: Mapping[str, Any], label: str) -> None:
    _require(
        value.get("fingerprint_sha256") == _fingerprint(_without_fingerprint(value)),
        "FINGERPRINT_MISMATCH",
        label,
    )


def _finite(value: Any, label: str) -> float:
    _require(type(value) in {int, float}, "FINITE_NUMBER_REQUIRED", label)
    output = float(value)
    _require(math.isfinite(output), "NONFINITE_NUMBER", label)
    return output


def _unique_strings(value: Any, label: str) -> tuple[str, ...]:
    _require(isinstance(value, list) and value, "STRING_LIST_REQUIRED", label)
    output = tuple(value)
    _require(
        all(isinstance(item, str) and item for item in output),
        "STRING_LIST_ITEM_INVALID",
        label,
    )
    _require(len(output) == len(set(output)), "STRING_LIST_DUPLICATE", label)
    return output


def _recursive_keys(value: Any) -> set[str]:
    if isinstance(value, Mapping):
        output = {str(key) for key in value}
        for child in value.values():
            output.update(_recursive_keys(child))
        return output
    if isinstance(value, list):
        output: set[str] = set()
        for child in value:
            output.update(_recursive_keys(child))
        return output
    return set()


def _candidate_id(selected_evidence_ids: Sequence[str], salt: str) -> str:
    digest = hashlib.sha256(
        salt.encode("utf-8") + b":" + _canonical_bytes(list(selected_evidence_ids))
    ).hexdigest()
    return f"K_{digest[:10]}"


def _candidate_map(case: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows = case["candidate_closures"]
    return {str(row["closure_id"]): dict(row) for row in rows}


def validate_fixture(fixture: Mapping[str, Any]) -> dict[str, Any]:
    _require(
        set(fixture)
        == {
            "schema_version",
            "status",
            "operator",
            "arms",
            "case",
            "protocol",
            "claim_boundary",
        },
        "FIXTURE_ROOT_SCHEMA_DRIFT",
    )
    _require(fixture.get("schema_version") == FIXTURE_SCHEMA, "FIXTURE_SCHEMA_DRIFT")
    _require(
        fixture.get("status") == "LOCKED_NETWORK_ZERO_PREFLIGHT_INPUT",
        "FIXTURE_STATUS_DRIFT",
    )
    _require(fixture.get("operator") == OPERATOR, "OPERATOR_DRIFT")
    _require(tuple(fixture.get("arms", ())) == ARMS, "ARM_SET_DRIFT")
    _unique_strings(fixture.get("claim_boundary"), "fixture.claim_boundary")

    case = fixture.get("case")
    _require(isinstance(case, Mapping), "CASE_INVALID")
    _require(
        set(case)
        == {
            "case_id",
            "checkpoint_id",
            "question",
            "answer_choices",
            "record_format_choices",
            "raw_evidence",
            "candidate_closures",
            "public_event_contract",
            "local_controller",
        },
        "CASE_SCHEMA_DRIFT",
    )
    for key in ("case_id", "checkpoint_id", "question"):
        _require(
            isinstance(case.get(key), str) and bool(case[key]), "CASE_TEXT_INVALID", key
        )
    answer_choices = _unique_strings(case.get("answer_choices"), "answer_choices")
    record_choices = _unique_strings(
        case.get("record_format_choices"), "record_format_choices"
    )
    _require(len(answer_choices) == 2, "ANSWER_CHOICE_COUNT_DRIFT")
    _require(len(record_choices) == 1, "RECORD_FORMAT_COUNT_DRIFT")

    raw = case.get("raw_evidence")
    _require(isinstance(raw, list) and len(raw) == 7, "RAW_EVIDENCE_COUNT_DRIFT")
    _require(
        all(
            isinstance(row, Mapping)
            and set(row) == {"evidence_id", "text"}
            and isinstance(row.get("evidence_id"), str)
            and isinstance(row.get("text"), str)
            and bool(row["text"])
            for row in raw
        ),
        "RAW_EVIDENCE_ROW_INVALID",
    )
    evidence_ids = _unique_strings(
        [row["evidence_id"] for row in raw], "raw_evidence.evidence_ids"
    )
    _require(
        evidence_ids == tuple(f"E{index}" for index in range(1, 8)), "EVIDENCE_ID_DRIFT"
    )
    chunk_hashes = [hashlib.sha256(_canonical_bytes(row)).hexdigest() for row in raw]
    _require(
        len(chunk_hashes) == len(set(chunk_hashes)), "EVIDENCE_CHUNK_HASH_DUPLICATE"
    )

    protocol = fixture.get("protocol")
    _require(isinstance(protocol, Mapping), "PROTOCOL_INVALID")
    _require(
        set(protocol)
        == {
            "review_budget",
            "neutral_order",
            "positive_control_order",
            "matched_anti_rule",
            "execution_order_seed",
            "candidate_id_salt",
            "model",
            "reasoning_effort",
            "max_output_tokens",
            "timeout_seconds",
            "sdk_retries",
            "store",
        },
        "PROTOCOL_SCHEMA_DRIFT",
    )
    _require(protocol.get("review_budget") == 3, "REVIEW_BUDGET_DRIFT")
    for key in ("neutral_order", "positive_control_order"):
        order = _unique_strings(protocol.get(key), f"protocol.{key}")
        _require(set(order) == set(evidence_ids), "PROTOCOL_ORDER_NOT_PERMUTATION", key)
    _require(
        protocol.get("matched_anti_rule") == "swap_preferred_and_opposed_path_blocks",
        "MATCHED_ANTI_RULE_DRIFT",
    )
    _require(protocol.get("model") == "gpt-5.6-sol", "MODEL_DRIFT")
    _require(protocol.get("reasoning_effort") == "low", "REASONING_EFFORT_DRIFT")
    _require(protocol.get("max_output_tokens") == 1024, "OUTPUT_CEILING_DRIFT")
    _require(protocol.get("timeout_seconds") == 60, "TIMEOUT_DRIFT")
    _require(protocol.get("sdk_retries") == 0, "SDK_RETRY_DRIFT")
    _require(protocol.get("store") is False, "STORE_POLICY_DRIFT")
    for key in ("execution_order_seed", "candidate_id_salt"):
        _require(
            isinstance(protocol.get(key), str) and bool(protocol[key]),
            "PROTOCOL_TEXT_INVALID",
            key,
        )

    event = case.get("public_event_contract")
    _require(
        isinstance(event, Mapping)
        and set(event)
        == {"late_event_evidence_id", "invalidated_evidence_id", "stable_evidence_id"},
        "EVENT_CONTRACT_INVALID",
    )
    _require(set(event.values()).issubset(evidence_ids), "EVENT_EVIDENCE_UNKNOWN")
    _require(len(set(event.values())) == 3, "EVENT_EVIDENCE_COLLISION")

    candidates = case.get("candidate_closures")
    _require(
        isinstance(candidates, list) and len(candidates) == 4, "CANDIDATE_COUNT_DRIFT"
    )
    candidate_ids: list[str] = []
    selected_sets: list[tuple[str, ...]] = []
    for row in candidates:
        _require(
            isinstance(row, Mapping)
            and set(row) == {"closure_id", "selected_evidence_ids"},
            "CANDIDATE_ROW_INVALID",
        )
        selected = _unique_strings(
            row.get("selected_evidence_ids"), "candidate.selected"
        )
        _require(len(selected) == 4, "CANDIDATE_CARDINALITY_DRIFT")
        _require(set(selected).issubset(evidence_ids), "CANDIDATE_EVIDENCE_UNKNOWN")
        _require(
            row.get("closure_id")
            == _candidate_id(selected, str(protocol["candidate_id_salt"])),
            "CANDIDATE_ID_HASH_DRIFT",
        )
        candidate_ids.append(str(row["closure_id"]))
        selected_sets.append(selected)
    _require(len(candidate_ids) == len(set(candidate_ids)), "CANDIDATE_ID_DUPLICATE")
    _require(
        len(selected_sets) == len(set(selected_sets)), "CANDIDATE_STRUCTURE_DUPLICATE"
    )

    controller = case.get("local_controller")
    _require(isinstance(controller, Mapping), "CONTROLLER_INVALID")
    _require(
        set(controller)
        == {
            "path_blocks",
            "state_decay",
            "terminal_target",
            "step_size",
            "control_regularization",
            "effect_by_evidence_id",
            "finite_difference_epsilon",
            "finite_difference_tolerance",
        },
        "CONTROLLER_SCHEMA_DRIFT",
    )
    blocks = controller.get("path_blocks")
    _require(
        isinstance(blocks, Mapping) and set(blocks) == {"P0", "P1"},
        "PATH_BLOCKS_INVALID",
    )
    p0 = _unique_strings(blocks.get("P0"), "path_blocks.P0")
    p1 = _unique_strings(blocks.get("P1"), "path_blocks.P1")
    _require(
        len(p0) == len(p1) == 2 and not (set(p0) & set(p1)),
        "PATH_BLOCK_GEOMETRY_INVALID",
    )
    _require(
        set(p0) | set(p1) | set(event.values()) == set(evidence_ids),
        "EVIDENCE_PARTITION_DRIFT",
    )
    effects = controller.get("effect_by_evidence_id")
    _require(
        isinstance(effects, Mapping) and set(effects) == set(evidence_ids),
        "EFFECT_SET_DRIFT",
    )
    for evidence_id, value in effects.items():
        _finite(value, f"effect.{evidence_id}")
    for key in (
        "state_decay",
        "terminal_target",
        "step_size",
        "control_regularization",
        "finite_difference_epsilon",
        "finite_difference_tolerance",
    ):
        _require(
            _finite(controller.get(key), key) > 0.0, "CONTROLLER_VALUE_NONPOSITIVE", key
        )
    return {
        "case_id": case["case_id"],
        "evidence_ids": list(evidence_ids),
        "candidate_ids": candidate_ids,
        "chunk_hashes": chunk_hashes,
    }


def validate_gold(
    gold: Mapping[str, Any], fixture: Mapping[str, Any]
) -> dict[str, Any]:
    _require(
        set(gold)
        == {
            "schema_version",
            "status",
            "case_id",
            "answer",
            "record_format",
            "positive_control_target_closure_id",
            "gradient_target_closure_id",
            "quality_valid_closure_ids",
            "closure_roles",
            "claim_boundary",
        },
        "GOLD_ROOT_SCHEMA_DRIFT",
    )
    _require(gold.get("schema_version") == GOLD_SCHEMA, "GOLD_SCHEMA_DRIFT")
    _require(gold.get("status") == "LOCKED_POST_CALL_GRADING_ONLY", "GOLD_STATUS_DRIFT")
    case = fixture["case"]
    candidates = _candidate_map(case)
    _require(gold.get("case_id") == case["case_id"], "GOLD_CASE_DRIFT")
    _require(gold.get("answer") in case["answer_choices"], "GOLD_ANSWER_INVALID")
    _require(
        gold.get("record_format") in case["record_format_choices"],
        "GOLD_FORMAT_INVALID",
    )
    roles = gold.get("closure_roles")
    _require(
        isinstance(roles, Mapping) and set(roles) == set(candidates),
        "GOLD_ROLE_SET_DRIFT",
    )
    expected_roles = {
        "ALIGNED_EVENT_CONSISTENT",
        "ALTERNATIVE_EVENT_CONSISTENT",
        "STALE_INVALIDATED_SUPPORT",
        "MIXED_INSUFFICIENT_SUPPORT",
    }
    _require(set(roles.values()) == expected_roles, "GOLD_ROLE_VALUE_DRIFT")
    controller = derive_controller(fixture)
    blocks = case["local_controller"]["path_blocks"]
    event = case["public_event_contract"]
    late_event = str(event["late_event_evidence_id"])
    invalidated = str(event["invalidated_evidence_id"])
    stable = str(event["stable_evidence_id"])
    preferred = str(controller["preferred_path_id"])
    opposed = str(controller["opposed_path_id"])
    selected_by_id = {
        closure_id: set(row["selected_evidence_ids"])
        for closure_id, row in candidates.items()
    }
    aligned_set = set(blocks[preferred]) | {late_event, stable}
    alternative_set = set(blocks[opposed]) | {late_event, stable}
    aligned_ids = [
        item for item, selected in selected_by_id.items() if selected == aligned_set
    ]
    alternative_ids = [
        item for item, selected in selected_by_id.items() if selected == alternative_set
    ]
    stale_ids = [
        item
        for item, selected in selected_by_id.items()
        if invalidated in selected and late_event not in selected
    ]
    assigned_ids = set(aligned_ids + alternative_ids + stale_ids)
    mixed_ids = [item for item in candidates if item not in assigned_ids]
    _require(
        all(
            len(items) == 1
            for items in (aligned_ids, alternative_ids, stale_ids, mixed_ids)
        ),
        "GOLD_CONSTRUCT_COORDINATES_AMBIGUOUS",
    )
    expected_roles_by_id = {
        aligned_ids[0]: "ALIGNED_EVENT_CONSISTENT",
        alternative_ids[0]: "ALTERNATIVE_EVENT_CONSISTENT",
        stale_ids[0]: "STALE_INVALIDATED_SUPPORT",
        mixed_ids[0]: "MIXED_INSUFFICIENT_SUPPORT",
    }
    _require(dict(roles) == expected_roles_by_id, "GOLD_ROLE_CONSTRUCT_DRIFT")
    valid_ids = _unique_strings(
        gold.get("quality_valid_closure_ids"), "gold.quality_valid"
    )
    _require(
        set(valid_ids) == {aligned_ids[0], alternative_ids[0]},
        "GOLD_VALID_SET_DRIFT",
    )
    for key in ("positive_control_target_closure_id", "gradient_target_closure_id"):
        _require(gold.get(key) in candidates, "GOLD_TARGET_UNKNOWN", key)
    _require(
        gold["positive_control_target_closure_id"]
        == gold["gradient_target_closure_id"]
        == aligned_ids[0],
        "GOLD_TARGET_RELATION_DRIFT",
    )
    _unique_strings(gold.get("claim_boundary"), "gold.claim_boundary")
    return {
        "case_id": gold["case_id"],
        "target_closure_id": gold["gradient_target_closure_id"],
        "quality_valid_closure_ids": list(valid_ids),
    }


def _controller_loss(
    controls: torch.Tensor,
    effects: torch.Tensor,
    *,
    decay: float,
    target: float,
    regularization: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    state = torch.zeros((), dtype=torch.float64)
    states: list[torch.Tensor] = []
    for control, effect in zip(controls, effects, strict=True):
        state = torch.tanh(decay * state + control * effect)
        states.append(state)
    loss = (state - target).square() + regularization * controls.square().sum()
    return loss, torch.stack(states)


def derive_controller(fixture: Mapping[str, Any]) -> dict[str, Any]:
    case = fixture["case"]
    evidence_ids = tuple(row["evidence_id"] for row in case["raw_evidence"])
    spec = case["local_controller"]
    effects = torch.tensor(
        [float(spec["effect_by_evidence_id"][item]) for item in evidence_ids],
        dtype=torch.float64,
    )
    controls = torch.zeros(len(evidence_ids), dtype=torch.float64, requires_grad=True)
    loss, states = _controller_loss(
        controls,
        effects,
        decay=float(spec["state_decay"]),
        target=float(spec["terminal_target"]),
        regularization=float(spec["control_regularization"]),
    )
    loss.backward()
    _require(controls.grad is not None, "BACKWARD_GRADIENT_MISSING")
    gradient = controls.grad.detach().clone()
    displacement = -float(spec["step_size"]) * gradient

    epsilon = float(spec["finite_difference_epsilon"])
    finite_difference: list[float] = []
    for index in range(len(evidence_ids)):
        positive = torch.zeros(len(evidence_ids), dtype=torch.float64)
        negative = torch.zeros(len(evidence_ids), dtype=torch.float64)
        positive[index] = epsilon
        negative[index] = -epsilon
        positive_loss, _ = _controller_loss(
            positive,
            effects,
            decay=float(spec["state_decay"]),
            target=float(spec["terminal_target"]),
            regularization=float(spec["control_regularization"]),
        )
        negative_loss, _ = _controller_loss(
            negative,
            effects,
            decay=float(spec["state_decay"]),
            target=float(spec["terminal_target"]),
            regularization=float(spec["control_regularization"]),
        )
        finite_difference.append(
            float((positive_loss - negative_loss) / (2.0 * epsilon))
        )
    errors = [
        abs(float(gradient[index]) - finite_difference[index])
        for index in range(len(evidence_ids))
    ]

    blocks = spec["path_blocks"]
    displacement_by_id = {
        item: float(displacement[index]) for index, item in enumerate(evidence_ids)
    }
    path_scores = {
        path_id: math.fsum(displacement_by_id[item] for item in blocks[path_id])
        for path_id in ("P0", "P1")
    }
    _require(
        abs(path_scores["P0"] - path_scores["P1"]) > FLOAT_TOLERANCE,
        "GRADIENT_PATH_TIE",
    )
    preferred = max(path_scores, key=path_scores.get)
    opposed = "P1" if preferred == "P0" else "P0"
    return _seal(
        {
            "schema_version": CONTROLLER_SCHEMA,
            "case_id": case["case_id"],
            "dtype": "torch.float64",
            "backward_calls": 1,
            "baseline_loss": float(loss.detach()),
            "baseline_states": [float(value) for value in states.detach()],
            "gradient_by_evidence_id": {
                item: float(gradient[index]) for index, item in enumerate(evidence_ids)
            },
            "displacement_by_evidence_id": displacement_by_id,
            "finite_difference_by_evidence_id": {
                item: finite_difference[index]
                for index, item in enumerate(evidence_ids)
            },
            "maximum_finite_difference_error": max(errors),
            "finite_difference_tolerance": float(spec["finite_difference_tolerance"]),
            "path_scores": path_scores,
            "preferred_path_id": preferred,
            "opposed_path_id": opposed,
            "gradient_boundary": {
                "starts_at": "local recurrent public-state surrogate",
                "ends_before": "JSON provider payload",
                "hosted_model_differentiated": False,
            },
        }
    )


def _spearman_footrule(reference: Sequence[str], candidate: Sequence[str]) -> int:
    return sum(abs(reference.index(item) - candidate.index(item)) for item in reference)


def _kendall_distance(reference: Sequence[str], candidate: Sequence[str]) -> int:
    candidate_positions = {item: index for index, item in enumerate(candidate)}
    return sum(
        candidate_positions[reference[left]] > candidate_positions[reference[right]]
        for left in range(len(reference))
        for right in range(left + 1, len(reference))
    )


def _fixed_points(reference: Sequence[str], candidate: Sequence[str]) -> int:
    return sum(left == right for left, right in zip(reference, candidate, strict=True))


def _positional_alignment(
    order: Sequence[str], displacement: Mapping[str, float]
) -> float:
    return math.fsum(
        float(displacement[item]) * float(len(order) - index)
        for index, item in enumerate(order)
    )


def compile_permutations(
    fixture: Mapping[str, Any], controller: Mapping[str, Any]
) -> tuple[dict[str, tuple[str, ...]], dict[str, Any]]:
    _validate_fingerprint(controller, "controller")
    case = fixture["case"]
    protocol = fixture["protocol"]
    spec = case["local_controller"]
    event = case["public_event_contract"]
    preferred = str(controller["preferred_path_id"])
    opposed = str(controller["opposed_path_id"])
    preferred_block = tuple(spec["path_blocks"][preferred])
    opposed_block = tuple(spec["path_blocks"][opposed])
    late_event = str(event["late_event_evidence_id"])
    invalidated = str(event["invalidated_evidence_id"])
    stable = str(event["stable_evidence_id"])
    permutations = {
        "Z": tuple(protocol["neutral_order"]),
        "X": tuple(protocol["positive_control_order"]),
        "D": preferred_block + (late_event,) + opposed_block + (invalidated, stable),
        "C": opposed_block + (late_event,) + preferred_block + (invalidated, stable),
    }
    evidence_ids = tuple(row["evidence_id"] for row in case["raw_evidence"])
    _require(
        all(
            len(order) == len(evidence_ids) and set(order) == set(evidence_ids)
            for order in permutations.values()
        ),
        "COMPILED_ORDER_NOT_PERMUTATION",
    )
    _require(len(set(permutations.values())) == 4, "COMPILED_ORDERS_NOT_DISTINCT")
    d_footrule = _spearman_footrule(permutations["Z"], permutations["D"])
    c_footrule = _spearman_footrule(permutations["Z"], permutations["C"])
    d_kendall = _kendall_distance(permutations["Z"], permutations["D"])
    c_kendall = _kendall_distance(permutations["Z"], permutations["C"])
    d_fixed = _fixed_points(permutations["Z"], permutations["D"])
    c_fixed = _fixed_points(permutations["Z"], permutations["C"])
    displacement = controller["displacement_by_evidence_id"]
    d_alignment = _positional_alignment(permutations["D"], displacement)
    c_alignment = _positional_alignment(permutations["C"], displacement)
    checks = {
        "all_four_orders_distinct": len(set(permutations.values())) == 4,
        "d_c_footrule_matched": d_footrule == c_footrule,
        "d_c_kendall_matched": d_kendall == c_kendall,
        "d_c_fixed_points_matched": d_fixed == c_fixed,
        "d_c_anchor_positions_matched": all(
            permutations["D"].index(item) == permutations["C"].index(item)
            for item in (late_event, invalidated, stable)
        ),
        "d_alignment_exceeds_c": d_alignment > c_alignment + FLOAT_TOLERANCE,
    }
    _require(all(checks.values()), "PERMUTATION_GEOMETRY_FAILED")
    geometry = _seal(
        {
            "schema_version": "ebrt-actuator-uptake-permutation-geometry-v0.6.3.1",
            "case_id": case["case_id"],
            "orders": {arm: list(permutations[arm]) for arm in ARMS},
            "distances_from_z": {
                "D": {
                    "spearman_footrule": d_footrule,
                    "kendall": d_kendall,
                    "fixed_points": d_fixed,
                },
                "C": {
                    "spearman_footrule": c_footrule,
                    "kendall": c_kendall,
                    "fixed_points": c_fixed,
                },
            },
            "positional_alignment": {"D": d_alignment, "C": c_alignment},
            "d_minus_c_alignment": d_alignment - c_alignment,
            "checks": checks,
        }
    )
    return permutations, geometry


def _provider_payload(case: Mapping[str, Any], order: Sequence[str]) -> dict[str, Any]:
    rows = {row["evidence_id"]: row for row in case["raw_evidence"]}
    return {
        "schema_version": PROVIDER_INPUT_SCHEMA,
        "checkpoint_id": case["checkpoint_id"],
        "question": case["question"],
        "answer_choices": _clone(case["answer_choices"]),
        "record_format_choices": _clone(case["record_format_choices"]),
        "ordered_raw_evidence": [_clone(rows[item]) for item in order],
        "candidate_closures": _clone(case["candidate_closures"]),
        "response_contract": {
            "schema_version": PROVIDER_OUTPUT_SCHEMA,
            "choose_exactly_one_candidate_closure": True,
            "reviewed_evidence_count": 3,
            "return_private_reasoning": False,
        },
        "task_instructions": [
            "Use the full evidence set and inspect the immutable chunks in the order presented.",
            "Select exactly one candidate closure and emit only the typed public response.",
            "Do not return private chain-of-thought or invent a closure outside the catalog.",
        ],
    }


def validate_provider_payload(
    payload: Mapping[str, Any], *, case: Mapping[str, Any]
) -> dict[str, Any]:
    _require(
        set(payload)
        == {
            "schema_version",
            "checkpoint_id",
            "question",
            "answer_choices",
            "record_format_choices",
            "ordered_raw_evidence",
            "candidate_closures",
            "response_contract",
            "task_instructions",
        },
        "PROVIDER_PAYLOAD_SCHEMA_DRIFT",
    )
    _require(
        payload.get("schema_version") == PROVIDER_INPUT_SCHEMA,
        "PROVIDER_INPUT_SCHEMA_DRIFT",
    )
    _require(
        payload.get("checkpoint_id") == case["checkpoint_id"],
        "PAYLOAD_CHECKPOINT_DRIFT",
    )
    for key in (
        "question",
        "answer_choices",
        "record_format_choices",
        "candidate_closures",
    ):
        _require(
            _canonical_bytes(payload.get(key)) == _canonical_bytes(case[key]),
            "PAYLOAD_FIELD_DRIFT",
            key,
        )
    evidence_rows = payload.get("ordered_raw_evidence")
    _require(
        isinstance(evidence_rows, list)
        and len(evidence_rows) == len(case["raw_evidence"])
        and all(
            isinstance(row, Mapping) and set(row) == {"evidence_id", "text"}
            for row in evidence_rows
        ),
        "PAYLOAD_EVIDENCE_INVALID",
    )
    original = {row["evidence_id"]: row for row in case["raw_evidence"]}
    ids = _unique_strings(
        [row.get("evidence_id") for row in evidence_rows if isinstance(row, Mapping)],
        "payload.evidence",
    )
    _require(set(ids) == set(original), "PAYLOAD_EVIDENCE_SET_DRIFT")
    _require(
        all(
            _canonical_bytes(row) == _canonical_bytes(original[row["evidence_id"]])
            for row in evidence_rows
        ),
        "PAYLOAD_EVIDENCE_BYTE_DRIFT",
    )
    _require(
        not (_recursive_keys(payload) & FORBIDDEN_PROVIDER_KEYS),
        "PROVIDER_PAYLOAD_LEAK",
    )
    _require(
        _canonical_bytes(payload) == _canonical_bytes(_provider_payload(case, ids)),
        "PROVIDER_PAYLOAD_NON_ORDER_FIELD_DRIFT",
    )
    return {
        "ordered_evidence_ids": list(ids),
        "payload_fingerprint_sha256": _fingerprint(payload),
    }


def _normalized_provider_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    output = _clone(dict(payload))
    output["ordered_raw_evidence"] = sorted(
        output["ordered_raw_evidence"], key=lambda row: row["evidence_id"]
    )
    return output


def _execution_order(seed: str) -> tuple[str, ...]:
    return tuple(
        sorted(
            ARMS, key=lambda arm: hashlib.sha256(f"{seed}|{arm}".encode()).hexdigest()
        )
    )


def _blind_id(case_id: str, arm: str, seed: str) -> str:
    digest = hashlib.sha256(f"{seed}|{case_id}|{arm}".encode()).hexdigest()
    return f"Q_{digest[:16]}"


def build_projection(
    fixture: Mapping[str, Any], controller: Mapping[str, Any]
) -> dict[str, Any]:
    fixture_audit = validate_fixture(fixture)
    _validate_fingerprint(controller, "controller")
    case = fixture["case"]
    permutations, geometry = compile_permutations(fixture, controller)
    seed = str(fixture["protocol"]["execution_order_seed"])
    execution_order = _execution_order(seed)
    rows: list[dict[str, Any]] = []
    treatment_key: list[dict[str, Any]] = []
    normalized: list[bytes] = []
    payload_fingerprints: set[str] = set()
    chunk_multisets: set[tuple[str, ...]] = set()
    for sequence_index, arm in enumerate(execution_order, start=1):
        payload = _provider_payload(case, permutations[arm])
        audit = validate_provider_payload(payload, case=case)
        blind_id = _blind_id(str(case["case_id"]), arm, seed)
        rows.append(
            {
                "sequence_index": sequence_index,
                "blinded_request_id": blind_id,
                "payload": _seal(payload),
            }
        )
        treatment_key.append(
            {
                "sequence_index": sequence_index,
                "blinded_request_id": blind_id,
                "treatment_id": arm,
            }
        )
        normalized.append(_canonical_bytes(_normalized_provider_payload(payload)))
        payload_fingerprints.add(str(audit["payload_fingerprint_sha256"]))
        chunk_multisets.add(
            tuple(
                sorted(
                    hashlib.sha256(_canonical_bytes(row)).hexdigest()
                    for row in payload["ordered_raw_evidence"]
                )
            )
        )
    _require(len(payload_fingerprints) == 4, "PROVIDER_PAYLOAD_FINGERPRINT_COLLISION")
    _require(len(set(normalized)) == 1, "NON_ORDER_PROVIDER_FIELD_DRIFT")
    _require(len(chunk_multisets) == 1, "EVIDENCE_CHUNK_MULTISET_DRIFT")
    return _seal(
        {
            "schema_version": PROJECTION_SCHEMA,
            "status": "READY_ZERO_CALL_PREFLIGHT_ONLY",
            "operator": OPERATOR,
            "case_id": case["case_id"],
            "provider_payload_count": 4,
            "provider_calls_authorized": 0,
            "provider_calls_observed": 0,
            "gold_used_for_projection": False,
            "execution_order": list(execution_order),
            "provider_payloads": rows,
            "public_treatment_key": treatment_key,
            "fixture_audit": fixture_audit,
            "permutation_geometry": geometry,
            "controller_audit_fingerprint_sha256": controller["fingerprint_sha256"],
            "claim_boundary": _clone(fixture["claim_boundary"]),
        }
    )


def _unseal(value: Mapping[str, Any], label: str) -> dict[str, Any]:
    _validate_fingerprint(value, label)
    return _without_fingerprint(value)


def _as_output(value: UptakeProviderOutput | Mapping[str, Any]) -> UptakeProviderOutput:
    if isinstance(value, UptakeProviderOutput):
        return value
    try:
        return UptakeProviderOutput.model_validate(value)
    except ValidationError as error:
        raise UptakeCanaryError("OUTPUT_SCHEMA_INVALID") from error


def _expand_known_closure(closure_id: str, case: Mapping[str, Any]) -> dict[str, Any]:
    candidates = _candidate_map(case)
    _require(closure_id in candidates, "OUTPUT_CLOSURE_ID_UNKNOWN")
    selected = tuple(candidates[closure_id]["selected_evidence_ids"])
    event = case["public_event_contract"]
    late_event = str(event["late_event_evidence_id"])
    invalidated = str(event["invalidated_evidence_id"])
    stable = str(event["stable_evidence_id"])
    support_ids = tuple(item for item in selected if item != stable)
    graph_edges = [
        {
            "edge_id": f"SUPPORT_{item}",
            "source_node_id": item,
            "target_node_id": "PUBLIC_DECISION",
            "relation_type": "supports",
        }
        for item in support_ids
    ]
    if stable in selected:
        graph_edges.append(
            {
                "edge_id": f"STABLE_{stable}",
                "source_node_id": stable,
                "target_node_id": "PUBLIC_RECORD_FORMAT",
                "relation_type": "supports",
            }
        )
    if late_event in selected:
        graph_edges.append(
            {
                "edge_id": f"INVALIDATES_{late_event}_{invalidated}",
                "source_node_id": late_event,
                "target_node_id": invalidated,
                "relation_type": "invalidates",
            }
        )
    return {
        "selected_evidence_ids": list(selected),
        "expanded_public_graph": {
            "nodes": list(selected) + ["PUBLIC_DECISION", "PUBLIC_RECORD_FORMAT"],
            "edges": graph_edges,
        },
        "public_contract_checks": {
            "late_event_selected": late_event in selected,
            "invalidated_evidence_absent": invalidated not in selected,
            "stable_evidence_preserved": stable in selected,
        },
    }


def compile_public_output(
    output: UptakeProviderOutput | Mapping[str, Any],
    *,
    payload: Mapping[str, Any],
    case: Mapping[str, Any],
) -> dict[str, Any]:
    """Parse structural output and expand a known closure without semantic rejection."""

    _require("fingerprint_sha256" in payload, "PROVIDER_PAYLOAD_UNSEALED")
    raw_payload = _unseal(payload, "provider payload")
    validate_provider_payload(raw_payload, case=case)
    parsed = _as_output(output)
    _require(
        parsed.checkpoint_id == raw_payload["checkpoint_id"], "OUTPUT_CHECKPOINT_DRIFT"
    )
    _require(
        parsed.current_answer in raw_payload["answer_choices"],
        "OUTPUT_ANSWER_NOT_ALLOWED",
    )
    _require(
        parsed.record_format in raw_payload["record_format_choices"],
        "OUTPUT_FORMAT_NOT_ALLOWED",
    )
    candidates = {row["closure_id"]: row for row in raw_payload["candidate_closures"]}
    _require(parsed.selected_closure_id in candidates, "OUTPUT_CLOSURE_ID_UNKNOWN")
    reviewed = tuple(parsed.reviewed_evidence_ids)
    _require(len(reviewed) == len(set(reviewed)), "OUTPUT_REVIEWED_EVIDENCE_DUPLICATE")
    evidence_ids = tuple(
        row["evidence_id"] for row in raw_payload["ordered_raw_evidence"]
    )
    _require(set(reviewed).issubset(evidence_ids), "OUTPUT_REVIEWED_EVIDENCE_UNKNOWN")

    expansion = _expand_known_closure(parsed.selected_closure_id, case)
    # The case does not carry runtime policy.  The fixed public receipt budget is
    # three, so derive adherence from the first three presented chunks only.
    expected_review = evidence_ids[:3]
    return _seal(
        {
            "schema_version": COMPILED_OUTPUT_SCHEMA,
            "checkpoint_id": parsed.checkpoint_id,
            "current_answer": parsed.current_answer,
            "record_format": parsed.record_format,
            "selected_closure_id": parsed.selected_closure_id,
            "selected_evidence_ids": expansion["selected_evidence_ids"],
            "expanded_public_graph": expansion["expanded_public_graph"],
            "public_contract_checks": expansion["public_contract_checks"],
            "inspection_receipt": {
                "reviewed_evidence_ids": list(reviewed),
                "expected_first_three_evidence_ids": list(expected_review),
                "adherence": reviewed == expected_review,
                "scored_as_primary_uptake": False,
            },
            "provider_output_fingerprint_sha256": _fingerprint(
                parsed.model_dump(mode="json")
            ),
            "provider_payload_fingerprint_sha256": payload["fingerprint_sha256"],
        }
    )


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _presealed_payloads_by_arm(
    fixture: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    controller = derive_controller(fixture)
    projection = build_projection(fixture, controller)
    payload_by_blind = {
        row["blinded_request_id"]: row["payload"]
        for row in projection["provider_payloads"]
    }
    return {
        row["treatment_id"]: payload_by_blind[row["blinded_request_id"]]
        for row in projection["public_treatment_key"]
    }


def validate_compiled_output(
    compiled: Mapping[str, Any],
    *,
    fixture: Mapping[str, Any],
    expected_payload: Mapping[str, Any],
) -> dict[str, Any]:
    _validate_fingerprint(compiled, "compiled output")
    _require(
        set(compiled)
        == {
            "schema_version",
            "checkpoint_id",
            "current_answer",
            "record_format",
            "selected_closure_id",
            "selected_evidence_ids",
            "expanded_public_graph",
            "public_contract_checks",
            "inspection_receipt",
            "provider_output_fingerprint_sha256",
            "provider_payload_fingerprint_sha256",
            "fingerprint_sha256",
        },
        "COMPILED_OUTPUT_SCHEMA_DRIFT",
    )
    case = fixture["case"]
    _require(
        compiled.get("schema_version") == COMPILED_OUTPUT_SCHEMA,
        "COMPILED_OUTPUT_VERSION_DRIFT",
    )
    _require(
        compiled.get("checkpoint_id") == case["checkpoint_id"],
        "COMPILED_OUTPUT_CHECKPOINT_DRIFT",
    )
    _require(
        compiled.get("current_answer") in case["answer_choices"],
        "COMPILED_OUTPUT_ANSWER_DRIFT",
    )
    _require(
        compiled.get("record_format") in case["record_format_choices"],
        "COMPILED_OUTPUT_FORMAT_DRIFT",
    )
    closure_id = compiled.get("selected_closure_id")
    _require(closure_id in _candidate_map(case), "COMPILED_OUTPUT_CLOSURE_UNKNOWN")
    expansion = _expand_known_closure(str(closure_id), case)
    for key in (
        "selected_evidence_ids",
        "expanded_public_graph",
        "public_contract_checks",
    ):
        _require(
            _canonical_bytes(compiled.get(key)) == _canonical_bytes(expansion[key]),
            "COMPILED_OUTPUT_EXPANSION_DRIFT",
            key,
        )
    receipt = compiled.get("inspection_receipt")
    _require(
        isinstance(receipt, Mapping)
        and set(receipt)
        == {
            "reviewed_evidence_ids",
            "expected_first_three_evidence_ids",
            "adherence",
            "scored_as_primary_uptake",
        },
        "COMPILED_OUTPUT_RECEIPT_DRIFT",
    )
    reviewed = _unique_strings(
        receipt.get("reviewed_evidence_ids"), "compiled.reviewed"
    )
    expected = _unique_strings(
        receipt.get("expected_first_three_evidence_ids"), "compiled.expected_review"
    )
    evidence_ids = {row["evidence_id"] for row in case["raw_evidence"]}
    _require(
        len(reviewed) == len(expected) == 3
        and set(reviewed).issubset(evidence_ids)
        and set(expected).issubset(evidence_ids)
        and receipt.get("adherence") is (reviewed == expected)
        and receipt.get("scored_as_primary_uptake") is False,
        "COMPILED_OUTPUT_RECEIPT_INCONSISTENT",
    )
    _validate_fingerprint(expected_payload, "expected arm payload")
    raw_expected_payload = _unseal(expected_payload, "expected arm payload")
    validate_provider_payload(raw_expected_payload, case=case)
    expected_from_payload = tuple(
        row["evidence_id"] for row in raw_expected_payload["ordered_raw_evidence"][:3]
    )
    _require(
        expected == expected_from_payload,
        "COMPILED_OUTPUT_EXPECTED_REVIEW_ARM_DRIFT",
    )
    expected_provider_output = {
        "schema_version": PROVIDER_OUTPUT_SCHEMA,
        "checkpoint_id": compiled["checkpoint_id"],
        "current_answer": compiled["current_answer"],
        "record_format": compiled["record_format"],
        "selected_closure_id": compiled["selected_closure_id"],
        "reviewed_evidence_ids": list(reviewed),
    }
    _require(
        compiled.get("provider_output_fingerprint_sha256")
        == _fingerprint(expected_provider_output),
        "COMPILED_OUTPUT_PROVIDER_FINGERPRINT_INVALID",
    )
    payload_fingerprint = compiled.get("provider_payload_fingerprint_sha256")
    _require(
        _is_sha256(payload_fingerprint), "COMPILED_OUTPUT_PAYLOAD_FINGERPRINT_INVALID"
    )
    _require(
        payload_fingerprint == expected_payload["fingerprint_sha256"],
        "COMPILED_OUTPUT_PAYLOAD_ARM_DRIFT",
    )
    return dict(compiled)


def grade_endpoint(
    compiled: Mapping[str, Any],
    *,
    gold: Mapping[str, Any],
    fixture: Mapping[str, Any],
    expected_payload: Mapping[str, Any],
) -> dict[str, Any]:
    validate_compiled_output(
        compiled,
        fixture=fixture,
        expected_payload=expected_payload,
    )
    validate_gold(gold, fixture)
    closure_id = str(compiled["selected_closure_id"])
    role = str(gold["closure_roles"][closure_id])
    quality_valid = closure_id in set(gold["quality_valid_closure_ids"])
    expected_answer: str | None
    if role in {"ALIGNED_EVENT_CONSISTENT", "ALTERNATIVE_EVENT_CONSISTENT"}:
        expected_answer = str(gold["answer"])
    else:
        expected_answer = None
    answer_trace_status = (
        "NOT_ASSESSED"
        if expected_answer is None
        else "PASS"
        if compiled["current_answer"] == expected_answer
        else "FAIL"
    )
    checks = {
        "answer": compiled["current_answer"] == gold["answer"],
        "record_format": compiled["record_format"] == gold["record_format"],
        "quality_valid_closure": quality_valid,
        "late_event_selected": bool(
            compiled["public_contract_checks"]["late_event_selected"]
        ),
        "invalidated_evidence_absent": bool(
            compiled["public_contract_checks"]["invalidated_evidence_absent"]
        ),
        "stable_evidence_preserved": bool(
            compiled["public_contract_checks"]["stable_evidence_preserved"]
        ),
    }
    d_alignment_score = {
        "ALIGNED_EVENT_CONSISTENT": 1,
        "ALTERNATIVE_EVENT_CONSISTENT": -1,
        "STALE_INVALIDATED_SUPPORT": 0,
        "MIXED_INSUFFICIENT_SUPPORT": 0,
    }[role]
    return _seal(
        {
            "schema_version": ENDPOINT_SCHEMA,
            "case_id": gold["case_id"],
            "selected_closure_id": closure_id,
            "closure_role": role,
            "is_positive_control_target": closure_id
            == gold["positive_control_target_closure_id"],
            "is_gradient_target": closure_id == gold["gradient_target_closure_id"],
            "event_complete_score": 1 if quality_valid else 0,
            "gradient_alignment_score": d_alignment_score,
            "answer_trace_status": answer_trace_status,
            "quality_status": "PASS" if all(checks.values()) else "FAIL",
            "quality_checks": checks,
            "secondary_quality_only": True,
            "compiled_output_fingerprint_sha256": compiled["fingerprint_sha256"],
            "provider_output_fingerprint_sha256": compiled[
                "provider_output_fingerprint_sha256"
            ],
            "provider_payload_fingerprint_sha256": compiled[
                "provider_payload_fingerprint_sha256"
            ],
        }
    )


def _validate_endpoint_for_decision(
    endpoint: Mapping[str, Any], *, gold: Mapping[str, Any]
) -> dict[str, Any]:
    _validate_fingerprint(endpoint, "decision endpoint")
    _require(
        set(endpoint)
        == {
            "schema_version",
            "case_id",
            "selected_closure_id",
            "closure_role",
            "is_positive_control_target",
            "is_gradient_target",
            "event_complete_score",
            "gradient_alignment_score",
            "answer_trace_status",
            "quality_status",
            "quality_checks",
            "secondary_quality_only",
            "compiled_output_fingerprint_sha256",
            "provider_output_fingerprint_sha256",
            "provider_payload_fingerprint_sha256",
            "fingerprint_sha256",
        },
        "DECISION_ENDPOINT_SCHEMA_DRIFT",
    )
    _require(
        endpoint.get("schema_version") == ENDPOINT_SCHEMA,
        "DECISION_ENDPOINT_VERSION_DRIFT",
    )
    _require(endpoint.get("case_id") == gold["case_id"], "DECISION_ENDPOINT_CASE_DRIFT")
    closure_id = endpoint.get("selected_closure_id")
    _require(closure_id in gold["closure_roles"], "DECISION_ENDPOINT_CLOSURE_UNKNOWN")
    role = str(gold["closure_roles"][closure_id])
    score = {
        "ALIGNED_EVENT_CONSISTENT": 1,
        "ALTERNATIVE_EVENT_CONSISTENT": -1,
        "STALE_INVALIDATED_SUPPORT": 0,
        "MIXED_INSUFFICIENT_SUPPORT": 0,
    }[role]
    _require(endpoint.get("closure_role") == role, "DECISION_ENDPOINT_ROLE_DRIFT")
    _require(
        endpoint.get("is_positive_control_target")
        is (closure_id == gold["positive_control_target_closure_id"]),
        "DECISION_ENDPOINT_X_TARGET_DRIFT",
    )
    _require(
        endpoint.get("is_gradient_target")
        is (closure_id == gold["gradient_target_closure_id"]),
        "DECISION_ENDPOINT_D_TARGET_DRIFT",
    )
    _require(
        endpoint.get("event_complete_score")
        == (1 if closure_id in set(gold["quality_valid_closure_ids"]) else 0),
        "DECISION_ENDPOINT_EVENT_SCORE_DRIFT",
    )
    _require(
        endpoint.get("gradient_alignment_score") == score,
        "DECISION_ENDPOINT_ALIGNMENT_SCORE_DRIFT",
    )
    _require(
        endpoint.get("answer_trace_status") in {"PASS", "FAIL", "NOT_ASSESSED"}
        and endpoint.get("quality_status") in {"PASS", "FAIL"}
        and endpoint.get("secondary_quality_only") is True,
        "DECISION_ENDPOINT_STATUS_DRIFT",
    )
    quality_checks = endpoint.get("quality_checks")
    _require(
        isinstance(quality_checks, Mapping)
        and set(quality_checks)
        == {
            "answer",
            "record_format",
            "quality_valid_closure",
            "late_event_selected",
            "invalidated_evidence_absent",
            "stable_evidence_preserved",
        }
        and all(type(value) is bool for value in quality_checks.values()),
        "DECISION_ENDPOINT_QUALITY_CHECK_DRIFT",
    )
    _require(
        endpoint["quality_status"]
        == ("PASS" if all(quality_checks.values()) else "FAIL"),
        "DECISION_ENDPOINT_QUALITY_STATUS_DRIFT",
    )
    _require(
        all(
            _is_sha256(endpoint.get(key))
            for key in (
                "compiled_output_fingerprint_sha256",
                "provider_output_fingerprint_sha256",
                "provider_payload_fingerprint_sha256",
            )
        ),
        "DECISION_ENDPOINT_PROVENANCE_INVALID",
    )
    return dict(endpoint)


def classify_canary(
    compiled_outputs: Mapping[str, Mapping[str, Any] | None],
    *,
    gold: Mapping[str, Any],
    fixture: Mapping[str, Any],
) -> dict[str, Any]:
    _require(set(compiled_outputs) == set(ARMS), "DECISION_ARM_SET_DRIFT")
    validate_gold(gold, fixture)
    payloads_by_arm = _presealed_payloads_by_arm(fixture)
    _require(set(payloads_by_arm) == set(ARMS), "DECISION_PAYLOAD_ARM_SET_DRIFT")
    resolved = {
        arm: _validate_endpoint_for_decision(
            grade_endpoint(
                row,
                gold=gold,
                fixture=fixture,
                expected_payload=payloads_by_arm[arm],
            ),
            gold=gold,
        )
        for arm, row in compiled_outputs.items()
        if row is not None
    }
    invalid_arms = sorted(arm for arm, row in compiled_outputs.items() if row is None)
    if invalid_arms:
        return _seal(
            {
                "schema_version": "ebrt-actuator-uptake-decision-v0.6.3.1",
                "assessment_status": "INCOMPLETE",
                "positive_control_status": "NOT_ASSESSED",
                "gradient_placement_status": "NOT_ASSESSED",
                "terminal_decision": "INCOMPLETE_NOT_ASSESSED",
                "invalid_arms": invalid_arms,
                "direct_v0_6_4_promotion_allowed": False,
            }
        )
    target = str(gold["gradient_target_closure_id"])
    z_id = str(resolved["Z"]["selected_closure_id"])
    x_id = str(resolved["X"]["selected_closure_id"])
    c_id = str(resolved["C"]["selected_closure_id"])
    d_id = str(resolved["D"]["selected_closure_id"])

    if z_id == target and x_id == target:
        positive = "POSITIVE_CONTROL_CEILING"
    elif z_id != target and x_id == target:
        positive = "CHANNEL_OPEN_DIRECTIONAL"
    elif z_id == x_id:
        positive = "ACTUATOR_CHANNEL_INERT"
    elif z_id == target and x_id != target:
        positive = "CHANNEL_OPEN_ADVERSE"
    else:
        positive = "CHANNEL_OPEN_DIRECTION_AMBIGUOUS"

    if c_id == target and d_id == target:
        placement = "D_C_TARGET_CEILING"
    elif d_id == target and c_id != target:
        placement = "GRADIENT_PLACEMENT_DIRECTIONAL"
    elif c_id == d_id:
        placement = "GRADIENT_PLACEMENT_NULL"
    elif c_id == target and d_id != target:
        placement = "GRADIENT_PLACEMENT_ADVERSE"
    else:
        placement = "GRADIENT_PLACEMENT_AMBIGUOUS"

    if (
        positive == "CHANNEL_OPEN_DIRECTIONAL"
        and placement == "GRADIENT_PLACEMENT_DIRECTIONAL"
    ):
        terminal = "PROMOTE_TO_FRESH_REPLICATION"
    elif positive == "POSITIVE_CONTROL_CEILING":
        terminal = "STOP_POSITIVE_CONTROL_CEILING_NOT_ASSESSED"
    elif positive == "ACTUATOR_CHANNEL_INERT":
        terminal = "STOP_CHANNEL_INERT"
    elif positive == "CHANNEL_OPEN_DIRECTION_AMBIGUOUS":
        terminal = "STOP_CHANNEL_AMBIGUOUS"
    elif positive == "CHANNEL_OPEN_ADVERSE":
        terminal = "STOP_CHANNEL_ADVERSE"
    elif placement == "D_C_TARGET_CEILING":
        terminal = "STOP_PLACEMENT_CEILING_NOT_ASSESSED"
    elif placement == "GRADIENT_PLACEMENT_NULL":
        terminal = "STOP_PLACEMENT_NULL"
    elif placement == "GRADIENT_PLACEMENT_AMBIGUOUS":
        terminal = "STOP_PLACEMENT_AMBIGUOUS"
    else:
        terminal = "STOP_PLACEMENT_ADVERSE"
    return _seal(
        {
            "schema_version": "ebrt-actuator-uptake-decision-v0.6.3.1",
            "assessment_status": "ASSESSED",
            "positive_control_status": positive,
            "gradient_placement_status": placement,
            "terminal_decision": terminal,
            "selected_closure_by_arm": {
                arm: resolved[arm]["selected_closure_id"] for arm in ARMS
            },
            "endpoint_fingerprint_by_arm": {
                arm: resolved[arm]["fingerprint_sha256"] for arm in ARMS
            },
            "invalid_arms": [],
            "direct_v0_6_4_promotion_allowed": False,
            "claim_boundary": [
                "PROMOTE_TO_FRESH_REPLICATION opens only a separately sealed replication gate.",
                "This four-call classification is not a quality, causal, or population-level result.",
            ],
        }
    )


def _fake_output(
    closure_id: str,
    *,
    payload: Mapping[str, Any],
    answer: str | None = None,
) -> dict[str, Any]:
    raw_payload = (
        _unseal(payload, "fake payload")
        if "fingerprint_sha256" in payload
        else dict(payload)
    )
    return {
        "schema_version": PROVIDER_OUTPUT_SCHEMA,
        "checkpoint_id": raw_payload["checkpoint_id"],
        "current_answer": answer or raw_payload["answer_choices"][0],
        "record_format": raw_payload["record_format_choices"][0],
        "selected_closure_id": closure_id,
        "reviewed_evidence_ids": [
            row["evidence_id"] for row in raw_payload["ordered_raw_evidence"][:3]
        ],
    }


def _expect_rejected(operation: Any, expected_reason: str) -> bool:
    try:
        operation()
    except UptakeCanaryError as error:
        return error.reason_code == expected_reason
    return False


@contextmanager
def _network_denied() -> Iterator[dict[str, int]]:
    counter = {"attempts": 0}

    def blocked(*_args: Any, **_kwargs: Any) -> Any:
        counter["attempts"] += 1
        raise RuntimeError("NETWORK_DISABLED_BY_V0631_SELF_TEST")

    with (
        mock.patch.object(socket.socket, "connect", new=blocked),
        mock.patch.object(socket.socket, "connect_ex", new=blocked),
        mock.patch.object(socket, "create_connection", new=blocked),
        mock.patch.object(socket, "getaddrinfo", new=blocked),
    ):
        yield counter


def _artifact_directory_contract_audit() -> bool:
    with tempfile.TemporaryDirectory(prefix="ebrt-v0631-artifact-contract-") as raw:
        root = Path(raw)
        for name in CANONICAL_ARTIFACT_FILENAMES:
            (root / name).write_bytes(b"{}\n")
        try:
            _validate_artifact_directory_entries(root)
            exact = True
        except UptakeCanaryError:
            exact = False
        (root / "extra.json").write_bytes(b"{}\n")
        extra_rejected = _expect_rejected(
            lambda: _validate_artifact_directory_entries(root),
            "ARTIFACT_FILE_SET_DRIFT",
        )
        (root / "extra.json").unlink()
        (root / "projection_bundle.json").unlink()
        missing_rejected = _expect_rejected(
            lambda: _validate_artifact_directory_entries(root),
            "ARTIFACT_FILE_SET_DRIFT",
        )
        (root / "projection_bundle.json").symlink_to(root / "controller_audit.json")
        symlink_rejected = _expect_rejected(
            lambda: _validate_artifact_directory_entries(root),
            "ARTIFACT_ENTRY_INVALID",
        )
        return exact and extra_rejected and missing_rejected and symlink_rejected


def run_self_test() -> dict[str, Any]:
    fixture = _strict_load(FIXTURE_PATH)
    gold = _strict_load(GOLD_PATH)
    fixture_audit = validate_fixture(fixture)
    gold_audit = validate_gold(gold, fixture)
    with _network_denied() as network:
        with _network_denied() as dns_probe:
            try:
                socket.getaddrinfo("example.invalid", 443)
            except RuntimeError as error:
                dns_guard_rejected = (
                    str(error) == "NETWORK_DISABLED_BY_V0631_SELF_TEST"
                    and dns_probe["attempts"] == 1
                )
            else:
                dns_guard_rejected = False
        controller = derive_controller(fixture)
        projection = build_projection(fixture, controller)
        second_controller = derive_controller(fixture)
        second_projection = build_projection(fixture, second_controller)
        payload_by_arm = {
            row["treatment_id"]: next(
                item["payload"]
                for item in projection["provider_payloads"]
                if item["blinded_request_id"] == row["blinded_request_id"]
            )
            for row in projection["public_treatment_key"]
        }
        candidate_ids = fixture_audit["candidate_ids"]
        roundtrips: list[bool] = []
        compiled_by_arm_and_id: dict[str, dict[str, dict[str, Any]]] = {
            arm: {} for arm in ARMS
        }
        endpoints_by_arm_and_id: dict[str, dict[str, dict[str, Any]]] = {
            arm: {} for arm in ARMS
        }
        for arm in ARMS:
            for closure_id in candidate_ids:
                output = _fake_output(closure_id, payload=payload_by_arm[arm])
                parsed = UptakeProviderOutput.model_validate(output)
                roundtrips.append(parsed.model_dump(mode="json") == output)
                compiled = compile_public_output(
                    output, payload=payload_by_arm[arm], case=fixture["case"]
                )
                compiled_by_arm_and_id[arm][closure_id] = compiled
                endpoints_by_arm_and_id[arm][closure_id] = grade_endpoint(
                    compiled,
                    gold=gold,
                    fixture=fixture,
                    expected_payload=payload_by_arm[arm],
                )

        stale_id = next(
            closure_id
            for closure_id, role in gold["closure_roles"].items()
            if role == "STALE_INVALIDATED_SUPPORT"
        )
        stale_compiled_without_error = (
            compiled_by_arm_and_id["Z"][stale_id]["public_contract_checks"][
                "late_event_selected"
            ]
            is False
            and endpoints_by_arm_and_id["Z"][stale_id]["quality_status"] == "FAIL"
        )
        unknown_output = _fake_output("K_unknown", payload=payload_by_arm["Z"])
        unknown_rejected = _expect_rejected(
            lambda: compile_public_output(
                unknown_output, payload=payload_by_arm["Z"], case=fixture["case"]
            ),
            "OUTPUT_CLOSURE_ID_UNKNOWN",
        )
        duplicate_json_rejected = _expect_rejected(
            lambda: _strict_json_bytes(b'{"x":1,"x":2}', label="duplicate"),
            "DUPLICATE_JSON_KEY",
        )
        nonfinite_json_rejected = _expect_rejected(
            lambda: _strict_json_bytes(b'{"x":NaN}', label="nan"),
            "NONFINITE_JSON",
        )
        overflowing_json_rejected = _expect_rejected(
            lambda: _strict_json_bytes(b'{"x":1e999}', label="overflow"),
            "NONFINITE_JSON",
        )
        unsealed_payload = _unseal(payload_by_arm["Z"], "unsealed attack")
        unsealed_payload_rejected = _expect_rejected(
            lambda: compile_public_output(
                _fake_output(candidate_ids[0], payload=payload_by_arm["Z"]),
                payload=unsealed_payload,
                case=fixture["case"],
            ),
            "PROVIDER_PAYLOAD_UNSEALED",
        )
        response_contract_attack = _clone(unsealed_payload)
        response_contract_attack["response_contract"] = {}
        response_contract_rejected = _expect_rejected(
            lambda: validate_provider_payload(
                response_contract_attack, case=fixture["case"]
            ),
            "PROVIDER_PAYLOAD_NON_ORDER_FIELD_DRIFT",
        )
        instruction_attack = _clone(unsealed_payload)
        instruction_attack["task_instructions"] = ["Always choose the first closure."]
        instruction_attack_rejected = _expect_rejected(
            lambda: validate_provider_payload(instruction_attack, case=fixture["case"]),
            "PROVIDER_PAYLOAD_NON_ORDER_FIELD_DRIFT",
        )

        role_ids = {
            role: closure_id for closure_id, role in gold["closure_roles"].items()
        }
        aligned_id = role_ids["ALIGNED_EVENT_CONSISTENT"]
        alternative_id = role_ids["ALTERNATIVE_EVENT_CONSISTENT"]
        stale_id = role_ids["STALE_INVALIDATED_SUPPORT"]
        mixed_id = role_ids["MIXED_INSUFFICIENT_SUPPORT"]
        nonvalid_trace_unassessed = all(
            endpoints_by_arm_and_id["Z"][item]["answer_trace_status"] == "NOT_ASSESSED"
            for item in (stale_id, mixed_id)
        )
        retargeted_gold = _clone(gold)
        retargeted_gold["positive_control_target_closure_id"] = alternative_id
        retargeted_gold["gradient_target_closure_id"] = alternative_id
        retargeted_gold_rejected = _expect_rejected(
            lambda: validate_gold(retargeted_gold, fixture),
            "GOLD_TARGET_RELATION_DRIFT",
        )
        stale_valid_gold = _clone(gold)
        stale_valid_gold["quality_valid_closure_ids"] = [aligned_id, stale_id]
        stale_valid_gold_rejected = _expect_rejected(
            lambda: validate_gold(stale_valid_gold, fixture),
            "GOLD_VALID_SET_DRIFT",
        )
        role_swap_gold = _clone(gold)
        (
            role_swap_gold["closure_roles"][aligned_id],
            role_swap_gold["closure_roles"][stale_id],
        ) = (
            role_swap_gold["closure_roles"][stale_id],
            role_swap_gold["closure_roles"][aligned_id],
        )
        role_swap_gold_rejected = _expect_rejected(
            lambda: validate_gold(role_swap_gold, fixture),
            "GOLD_ROLE_CONSTRUCT_DRIFT",
        )
        forged_compiled_rejected = _expect_rejected(
            lambda: classify_canary(
                {arm: {"selected_closure_id": aligned_id} for arm in ARMS},
                gold=gold,
                fixture=fixture,
            ),
            "FINGERPRINT_MISMATCH",
        )
        inconsistent_compiled = _without_fingerprint(
            compiled_by_arm_and_id["D"][aligned_id]
        )
        inconsistent_compiled["selected_closure_id"] = alternative_id
        inconsistent_compiled = _seal(inconsistent_compiled)
        inconsistent_compiled_rejected = _expect_rejected(
            lambda: classify_canary(
                {
                    "Z": compiled_by_arm_and_id["Z"][aligned_id],
                    "C": compiled_by_arm_and_id["C"][aligned_id],
                    "D": inconsistent_compiled,
                    "X": compiled_by_arm_and_id["X"][aligned_id],
                },
                gold=gold,
                fixture=fixture,
            ),
            "COMPILED_OUTPUT_EXPANSION_DRIFT",
        )
        arm_swapped_compiled_rejected = _expect_rejected(
            lambda: classify_canary(
                {
                    "Z": compiled_by_arm_and_id["Z"][alternative_id],
                    "C": compiled_by_arm_and_id["Z"][alternative_id],
                    "D": compiled_by_arm_and_id["Z"][aligned_id],
                    "X": compiled_by_arm_and_id["Z"][aligned_id],
                },
                gold=gold,
                fixture=fixture,
            ),
            "COMPILED_OUTPUT_EXPECTED_REVIEW_ARM_DRIFT",
        )

        decisions: list[str] = []
        for z_id in candidate_ids:
            for c_id in candidate_ids:
                for d_id in candidate_ids:
                    for x_id in candidate_ids:
                        decision = classify_canary(
                            {
                                "Z": compiled_by_arm_and_id["Z"][z_id],
                                "C": compiled_by_arm_and_id["C"][c_id],
                                "D": compiled_by_arm_and_id["D"][d_id],
                                "X": compiled_by_arm_and_id["X"][x_id],
                            },
                            gold=gold,
                            fixture=fixture,
                        )
                        decisions.append(str(decision["terminal_decision"]))
        incomplete = classify_canary(
            {
                "Z": compiled_by_arm_and_id["Z"][candidate_ids[0]],
                "C": None,
                "D": compiled_by_arm_and_id["D"][candidate_ids[1]],
                "X": compiled_by_arm_and_id["X"][candidate_ids[2]],
            },
            gold=gold,
            fixture=fixture,
        )

        def terminal(z_id: str, c_id: str, d_id: str, x_id: str) -> str:
            return str(
                classify_canary(
                    {
                        "Z": compiled_by_arm_and_id["Z"][z_id],
                        "C": compiled_by_arm_and_id["C"][c_id],
                        "D": compiled_by_arm_and_id["D"][d_id],
                        "X": compiled_by_arm_and_id["X"][x_id],
                    },
                    gold=gold,
                    fixture=fixture,
                )["terminal_decision"]
            )

        truth_table = {
            "promote": terminal(alternative_id, alternative_id, aligned_id, aligned_id),
            "positive_ceiling": terminal(
                aligned_id, alternative_id, aligned_id, aligned_id
            ),
            "channel_inert": terminal(
                alternative_id, alternative_id, aligned_id, alternative_id
            ),
            "channel_ambiguous": terminal(
                stale_id, alternative_id, aligned_id, mixed_id
            ),
            "channel_adverse": terminal(
                aligned_id, alternative_id, aligned_id, alternative_id
            ),
            "placement_ceiling": terminal(
                alternative_id, aligned_id, aligned_id, aligned_id
            ),
            "placement_null": terminal(
                alternative_id, alternative_id, alternative_id, aligned_id
            ),
            "placement_ambiguous": terminal(
                alternative_id, stale_id, mixed_id, aligned_id
            ),
            "placement_adverse": terminal(
                alternative_id, aligned_id, alternative_id, aligned_id
            ),
        }
        expected_truth_table = {
            "promote": "PROMOTE_TO_FRESH_REPLICATION",
            "positive_ceiling": "STOP_POSITIVE_CONTROL_CEILING_NOT_ASSESSED",
            "channel_inert": "STOP_CHANNEL_INERT",
            "channel_ambiguous": "STOP_CHANNEL_AMBIGUOUS",
            "channel_adverse": "STOP_CHANNEL_ADVERSE",
            "placement_ceiling": "STOP_PLACEMENT_CEILING_NOT_ASSESSED",
            "placement_null": "STOP_PLACEMENT_NULL",
            "placement_ambiguous": "STOP_PLACEMENT_AMBIGUOUS",
            "placement_adverse": "STOP_PLACEMENT_ADVERSE",
        }

    geometry = projection["permutation_geometry"]
    payloads = [row["payload"] for row in projection["provider_payloads"]]
    normalized_payloads = {
        _canonical_bytes(_normalized_provider_payload(_unseal(payload, "payload")))
        for payload in payloads
    }
    chunk_multisets = {
        tuple(
            sorted(
                hashlib.sha256(_canonical_bytes(row)).hexdigest()
                for row in _unseal(payload, "payload")["ordered_raw_evidence"]
            )
        )
        for payload in payloads
    }
    known_terminal_statuses = {
        "PROMOTE_TO_FRESH_REPLICATION",
        "STOP_POSITIVE_CONTROL_CEILING_NOT_ASSESSED",
        "STOP_CHANNEL_INERT",
        "STOP_CHANNEL_AMBIGUOUS",
        "STOP_CHANNEL_ADVERSE",
        "STOP_PLACEMENT_CEILING_NOT_ASSESSED",
        "STOP_PLACEMENT_NULL",
        "STOP_PLACEMENT_AMBIGUOUS",
        "STOP_PLACEMENT_ADVERSE",
    }
    checks = {
        "strict_fixture_contract": bool(fixture_audit and gold_audit)
        and retargeted_gold_rejected
        and stale_valid_gold_rejected
        and role_swap_gold_rejected,
        "opaque_candidate_ids": all(
            item.startswith("K_") and len(item) == 12 for item in candidate_ids
        ),
        "equal_candidate_cardinality": len(
            {
                len(row["selected_evidence_ids"])
                for row in fixture["case"]["candidate_closures"]
            }
        )
        == 1,
        "real_float64_backward": controller["dtype"] == "torch.float64"
        and controller["backward_calls"] == 1,
        "finite_difference_agreement": controller["maximum_finite_difference_error"]
        <= controller["finite_difference_tolerance"],
        "gradient_path_preference_nonzero": abs(
            controller["path_scores"]["P0"] - controller["path_scores"]["P1"]
        )
        > FLOAT_TOLERANCE,
        "exact_z_x_c_d_permutations": set(geometry["orders"]) == set(ARMS)
        and len({_canonical_bytes(value) for value in geometry["orders"].values()})
        == 4,
        "matched_d_c_geometry": all(
            value for key, value in geometry["checks"].items() if key.startswith("d_c_")
        ),
        "d_alignment_exceeds_c": geometry["checks"]["d_alignment_exceeds_c"],
        "immutable_chunk_multiset": len(chunk_multisets) == 1,
        "only_evidence_order_differs": len(normalized_payloads) == 1,
        "provider_payloads_leak_free": all(
            not (_recursive_keys(_unseal(payload, "payload")) & FORBIDDEN_PROVIDER_KEYS)
            for payload in payloads
        )
        and response_contract_rejected
        and instruction_attack_rejected
        and unsealed_payload_rejected,
        "four_payloads_presealed": len(payloads) == 4
        and len({payload["fingerprint_sha256"] for payload in payloads}) == 4,
        "all_known_closures_roundtrip": all(roundtrips),
        "semantic_failures_are_endpoints": stale_compiled_without_error
        and nonvalid_trace_unassessed,
        "unknown_closure_rejected": unknown_rejected
        and duplicate_json_rejected
        and nonfinite_json_rejected
        and overflowing_json_rejected,
        "decision_classifier_total": len(decisions) == 256
        and set(decisions) == known_terminal_statuses
        and incomplete["terminal_decision"] == "INCOMPLETE_NOT_ASSESSED"
        and truth_table == expected_truth_table
        and forged_compiled_rejected
        and inconsistent_compiled_rejected
        and arm_swapped_compiled_rejected,
        "deterministic_double_projection": _canonical_bytes(controller)
        == _canonical_bytes(second_controller)
        and _canonical_bytes(projection) == _canonical_bytes(second_projection),
        "canonical_artifact_directory_exact": _artifact_directory_contract_audit(),
        "network_calls_zero": network["attempts"] == 0 and dns_guard_rejected,
    }
    _require(set(checks) == set(HARD_GATE_IDS), "HARD_GATE_SET_DRIFT")
    _require(all(checks.values()), "SELF_TEST_HARD_GATE_FAILED")
    return _seal(
        {
            "schema_version": SELF_TEST_SCHEMA,
            "status": "PASS_NETWORK_ZERO",
            "hard_gates": [
                {"gate_id": gate_id, "passed": bool(checks[gate_id])}
                for gate_id in HARD_GATE_IDS
            ],
            "controller_fingerprint_sha256": controller["fingerprint_sha256"],
            "projection_fingerprint_sha256": projection["fingerprint_sha256"],
            "classifier_combinations_exercised": len(decisions),
            "network_calls": network["attempts"],
            "provider_calls": 0,
            "claim_boundary": [
                "Synthetic outputs exercise parser, endpoint, and decision branches only.",
                "They do not instantiate or predict hosted-model uptake.",
            ],
        }
    )


def _file_receipt(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {
        "path": str(path.relative_to(ROOT)),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _runtime_contract(fixture: Mapping[str, Any]) -> dict[str, Any]:
    protocol = fixture["protocol"]
    return {
        "python": platform.python_version(),
        "machine": platform.machine(),
        "torch": package_version("torch"),
        "pydantic": package_version("pydantic"),
        "model": protocol["model"],
        "reasoning_effort": protocol["reasoning_effort"],
        "max_output_tokens": protocol["max_output_tokens"],
        "timeout_seconds": protocol["timeout_seconds"],
        "sdk_retries": protocol["sdk_retries"],
        "store": protocol["store"],
        "previous_response_id": False,
        "provider_calls_authorized": 0,
    }


def policy_lock_material() -> dict[str, Any]:
    fixture = _strict_load(FIXTURE_PATH)
    gold = _strict_load(GOLD_PATH)
    validate_fixture(fixture)
    validate_gold(gold, fixture)
    controller = derive_controller(fixture)
    projection = build_projection(fixture, controller)
    source_paths = {
        "core": Path(__file__).resolve(),
        "fixture": FIXTURE_PATH,
        "post_call_gold": GOLD_PATH,
        "protocol_note": NOTE_PATH,
        "requirements": ROOT / "requirements.txt",
    }
    _require(
        all(path.is_file() for path in source_paths.values()), "POLICY_SOURCE_MISSING"
    )
    return _seal(
        {
            "schema_version": POLICY_SCHEMA,
            "status": "LOCKED_NETWORK_ZERO_PREFLIGHT_NO_LIVE_AUTHORIZATION",
            "protocol": {
                "operator": OPERATOR,
                "arms": list(ARMS),
                "case_id": fixture["case"]["case_id"],
                "provider_payload_count": 4,
                "execution_order": projection["execution_order"],
                "orders": projection["permutation_geometry"]["orders"],
                "hard_gate_ids": list(HARD_GATE_IDS),
                "primary_action_field": "selected_closure_id",
                "positive_result": "PROMOTE_TO_FRESH_REPLICATION",
                "direct_v0_6_4_promotion_allowed": False,
                "semantic_failures_are_endpoints": True,
                "structural_invalid_reasons": [
                    "provider_transport_or_timeout",
                    "malformed_or_duplicate_key_json",
                    "provider_output_schema_invalid",
                    "unknown_closure_id",
                ],
            },
            "runtime_contract": _runtime_contract(fixture),
            "artifact": {
                "directory": str(DEFAULT_ARTIFACT_DIR.relative_to(ROOT)),
                "files": sorted(CANONICAL_ARTIFACT_FILENAMES),
                "network_calls": 0,
                "provider_calls": 0,
            },
            "canonicalization": {
                "encoding": "utf-8",
                "ensure_ascii": False,
                "sort_keys": True,
                "separators": [",", ":"],
                "allow_nan": False,
                "trailing_newline": True,
            },
            "sources": {
                name: _file_receipt(path) for name, path in source_paths.items()
            },
            "claim_boundary": [
                "This lock authorizes deterministic network-zero construction only.",
                "The local float64 backward ends before JSON; no gradient crosses the hosted boundary.",
                "The four synthetic closure coordinates are parser and decision conformance cases, not hosted effects.",
                "A future four-call execution requires a separate merged authorization lock and exact-commit tag.",
                "No result here supports hidden-state editing, attention/KV claims, quality improvement, or general reasoning improvement.",
            ],
        }
    )


def validate_policy_lock() -> dict[str, Any]:
    observed = _strict_load(POLICY_LOCK_PATH)
    expected = policy_lock_material()
    _require(
        _canonical_bytes(observed) == _canonical_bytes(expected), "POLICY_LOCK_DRIFT"
    )
    _validate_fingerprint(observed, "policy lock")
    return observed


def _write_canonical(path: Path, value: Any) -> None:
    path.write_bytes(_canonical_pretty_bytes(value))


def _validate_artifact_directory_entries(root: Path) -> None:
    _require(root.is_dir() and not root.is_symlink(), "ARTIFACT_DIRECTORY_INVALID")
    entries = list(root.iterdir())
    _require(
        {path.name for path in entries} == CANONICAL_ARTIFACT_FILENAMES,
        "ARTIFACT_FILE_SET_DRIFT",
    )
    _require(
        all(path.is_file() and not path.is_symlink() for path in entries),
        "ARTIFACT_ENTRY_INVALID",
    )


def validate_canonical_artifact(
    root: Path = DEFAULT_ARTIFACT_DIR,
) -> dict[str, Any]:
    _validate_artifact_directory_entries(root)
    projection = _strict_load(root / "projection_bundle.json")
    controller = _strict_load(root / "controller_audit.json")
    self_test = _strict_load(root / "self_test.json")
    manifest = _strict_load(root / "manifest.json")
    for label, value in (
        ("projection", projection),
        ("controller", controller),
        ("self test", self_test),
        ("manifest", manifest),
    ):
        _validate_fingerprint(value, label)
    _require(
        projection.get("schema_version") == PROJECTION_SCHEMA,
        "ARTIFACT_PROJECTION_SCHEMA_DRIFT",
    )
    _require(
        controller.get("schema_version") == CONTROLLER_SCHEMA,
        "ARTIFACT_CONTROLLER_SCHEMA_DRIFT",
    )
    _require(
        self_test.get("schema_version") == SELF_TEST_SCHEMA,
        "ARTIFACT_SELF_TEST_SCHEMA_DRIFT",
    )
    _require(
        self_test.get("status") == "PASS_NETWORK_ZERO", "ARTIFACT_SELF_TEST_FAILED"
    )
    _require(
        manifest.get("schema_version") == MANIFEST_SCHEMA,
        "ARTIFACT_MANIFEST_SCHEMA_DRIFT",
    )
    _require(
        manifest.get("status") == "READY_ZERO_CALL_PREFLIGHT_ONLY",
        "ARTIFACT_MANIFEST_STATUS_DRIFT",
    )
    expected_receipts = {
        name: {
            "bytes": len((root / name).read_bytes()),
            "sha256": hashlib.sha256((root / name).read_bytes()).hexdigest(),
        }
        for name in (
            "projection_bundle.json",
            "controller_audit.json",
            "self_test.json",
        )
    }
    _require(
        manifest.get("artifact_receipts") == expected_receipts, "ARTIFACT_RECEIPT_DRIFT"
    )
    policy = validate_policy_lock()
    _require(
        manifest.get("policy_lock_fingerprint_sha256") == policy["fingerprint_sha256"],
        "ARTIFACT_POLICY_FINGERPRINT_DRIFT",
    )
    _require(
        manifest.get("projection_fingerprint_sha256")
        == projection["fingerprint_sha256"]
        and manifest.get("controller_fingerprint_sha256")
        == controller["fingerprint_sha256"]
        and manifest.get("self_test_fingerprint_sha256")
        == self_test["fingerprint_sha256"],
        "ARTIFACT_COMPONENT_FINGERPRINT_DRIFT",
    )
    fixture = _strict_load(FIXTURE_PATH)
    expected_controller = derive_controller(fixture)
    expected_projection = build_projection(fixture, expected_controller)
    expected_self_test = run_self_test()
    _require(
        _canonical_bytes(controller) == _canonical_bytes(expected_controller),
        "ARTIFACT_CONTROLLER_COHERENT_RESIGN",
    )
    _require(
        _canonical_bytes(projection) == _canonical_bytes(expected_projection),
        "ARTIFACT_PROJECTION_COHERENT_RESIGN",
    )
    _require(
        _canonical_bytes(self_test) == _canonical_bytes(expected_self_test),
        "ARTIFACT_SELF_TEST_COHERENT_RESIGN",
    )
    return manifest


def build_canonical_artifact(
    output_dir: Path = DEFAULT_ARTIFACT_DIR,
) -> dict[str, Any]:
    policy = validate_policy_lock()
    fixture = _strict_load(FIXTURE_PATH)
    controller = derive_controller(fixture)
    projection = build_projection(fixture, controller)
    self_test = run_self_test()
    with tempfile.TemporaryDirectory(
        prefix="ebrt-v0631-build-", dir=str(output_dir.parent)
    ) as raw:
        staging = Path(raw)
        _write_canonical(staging / "projection_bundle.json", projection)
        _write_canonical(staging / "controller_audit.json", controller)
        _write_canonical(staging / "self_test.json", self_test)
        artifact_receipts = {
            name: {
                "bytes": len((staging / name).read_bytes()),
                "sha256": hashlib.sha256((staging / name).read_bytes()).hexdigest(),
            }
            for name in (
                "projection_bundle.json",
                "controller_audit.json",
                "self_test.json",
            )
        }
        manifest = _seal(
            {
                "schema_version": MANIFEST_SCHEMA,
                "status": "READY_ZERO_CALL_PREFLIGHT_ONLY",
                "policy_lock_fingerprint_sha256": policy["fingerprint_sha256"],
                "projection_fingerprint_sha256": projection["fingerprint_sha256"],
                "controller_fingerprint_sha256": controller["fingerprint_sha256"],
                "self_test_fingerprint_sha256": self_test["fingerprint_sha256"],
                "artifact_receipts": artifact_receipts,
                "network_calls": 0,
                "provider_calls": 0,
                "live_execution_authorized": False,
                "claim_boundary": [
                    "This artifact freezes four provider payloads but authorizes zero provider calls.",
                    "No synthetic endpoint is evidence of hosted uptake.",
                ],
            }
        )
        _write_canonical(staging / "manifest.json", manifest)
        _validate_artifact_directory_entries(staging)
        if output_dir.exists():
            _validate_artifact_directory_entries(output_dir)
            for name in CANONICAL_ARTIFACT_FILENAMES:
                _require(
                    (output_dir / name).read_bytes() == (staging / name).read_bytes(),
                    "EXISTING_ARTIFACT_BYTE_DRIFT",
                    name,
                )
        else:
            output_dir.parent.mkdir(parents=True, exist_ok=True)
            staging.replace(output_dir)
    return validate_canonical_artifact(output_dir)


def build_preflight() -> dict[str, Any]:
    fixture = _strict_load(FIXTURE_PATH)
    controller = derive_controller(fixture)
    projection = build_projection(fixture, controller)
    self_test = run_self_test()
    policy = validate_policy_lock()
    return _seal(
        {
            "schema_version": "ebrt-actuator-uptake-preflight-v0.6.3.1",
            "status": "READY_ZERO_CALL_PREFLIGHT_ONLY",
            "controller": controller,
            "projection": projection,
            "self_test": self_test,
            "policy_lock_fingerprint_sha256": policy["fingerprint_sha256"],
            "network_calls": 0,
            "provider_calls": 0,
        }
    )


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("self-test", help="run network-zero adversarial checks")
    subparsers.add_parser("preflight", help="print the sealed network-zero preflight")
    subparsers.add_parser("emit-lock", help="write the canonical zero-call policy lock")
    subparsers.add_parser(
        "build-artifact", help="write or validate the canonical preflight artifact"
    )
    subparsers.add_parser(
        "validate-artifact", help="validate the committed canonical artifact"
    )
    args = parser.parse_args(argv)
    if args.command == "self-test":
        _print_json(run_self_test())
    elif args.command == "preflight":
        _print_json(build_preflight())
    elif args.command == "emit-lock":
        _write_canonical(POLICY_LOCK_PATH, policy_lock_material())
        _print_json(_strict_load(POLICY_LOCK_PATH))
    elif args.command == "build-artifact":
        _print_json(build_canonical_artifact())
    elif args.command == "validate-artifact":
        _print_json(validate_canonical_artifact())
    else:  # pragma: no cover - argparse owns the command set.
        raise AssertionError(args.command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
