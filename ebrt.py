#!/usr/bin/env python3
"""EBRT v0.6.2.1 Apply Revision product runtime.

This is the single executable product path for the sealed Apply Revision
acceptance.  It performs two dependent hosted calls around one real local
float64 backward pass:

    Before -> public state -> backward() -> public control -> actuator
           -> full-context regeneration -> strict local verification

The hosted model is never differentiated.  Semantic gold is unavailable to
the provider, controller, actuator compiler, and both hosted calls; it is read
only after two structurally valid public terminals exist.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import heapq
import json
import math
import os
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
from collections import defaultdict
from contextlib import contextmanager
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any, Iterator, Literal, Mapping, Sequence
from unittest import mock

import torch
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, ValidationError

import temporal_adjoint_lineage_v0_5_4 as temporal_v054
from language_replay_bridge_v0_4 import ProviderReceipt, canonical_json
from openai_response_boundary_v0_4_3 import (
    BOUNDARY_PHASES,
    BOUNDARY_REASON_CODES_BY_PHASE,
    InstrumentedResponsesClientBase,
)


ROOT = Path(__file__).resolve().parent
FIXTURE_PATH = ROOT / "fixtures" / "apply_revision_acceptance_v0_6_2_1.json"
GOLD_PATH = ROOT / "fixtures" / "apply_revision_acceptance_gold_v0_6_2_1.json"
LOCK_PATH = ROOT / "policy_lock_apply_revision_acceptance_v0_6_2_1.json"
SOURCE_CASE_PATH = ROOT / "fixtures" / "hackathon_strategy_walkthrough_v0_5_2.json"
TEMPORAL_FIXTURE_PATH = ROOT / "fixtures" / "temporal_adjoint_lineage_v0_5_4_dev.json"
TEMPORAL_LANE_PATH = (
    ROOT
    / "artifacts"
    / "temporal_adjoint_lineage_v0_5_4"
    / "correction_late_sealed_lane.json"
)
V053_REGRESSION_PATH = (
    ROOT
    / "artifacts"
    / "factorized_lineage_v0_5_3"
    / "factorized_lineage_regression.json"
)
DEFAULT_OUTPUT = ROOT / "artifacts" / "apply_revision_acceptance_v0_6_2_1_live_r01"

FIXTURE_SCHEMA = "ebrt-apply-revision-acceptance-fixture-v0.6.2.1"
GOLD_SCHEMA = "ebrt-apply-revision-acceptance-gold-v0.6.2.1"
INPUT_SCHEMA = "ebrt-apply-revision-provider-input-v0.6.2.1"
OUTPUT_SCHEMA = "ebrt-apply-revision-provider-output-v0.6.2.1"
COMPILED_SCHEMA = "ebrt-apply-revision-compiled-closure-v0.6.2.1"
CONTROL_SCHEMA = "ebrt-apply-revision-public-control-map-v0.6.2.1"
ACTUATOR_SCHEMA = "ebrt-apply-revision-compiled-actuator-v0.6.2.1"
RESULT_SCHEMA = "ebrt-apply-revision-result-v0.6.2.1-r01"
CALL_SCHEMA = "ebrt-apply-revision-call-v0.6.2.1-r01"
JOURNAL_SCHEMA = "ebrt-apply-revision-journal-v0.6.2.1-r01"
PROVIDER_INPUTS_SCHEMA = "ebrt-apply-revision-provider-inputs-v0.6.2.1-r01"
TRACE_SCHEMA = "ebrt-apply-revision-trace-v0.6.2.1-r01"
MANIFEST_SCHEMA = "ebrt-apply-revision-manifest-v0.6.2.1-r01"
LOCK_SCHEMA = "ebrt-apply-revision-policy-lock-v0.6.2.1-r01"

PHASES = ("before_event", "after_event")
MODEL = "gpt-5.6-sol"
REASONING_EFFORT = "low"
MAX_OUTPUT_TOKENS = 1024
TIMEOUT_SECONDS = 60.0
AUTHORIZATION_TAG = "v0.6.2.1-apply-revision-live-r01-authorized"

# The local recurrence parameters are part of the policy surface.  The fixture
# mirrors these values; keeping constants here makes drift fail before a call.
STATE_DECAY = 0.82
STEP_SIZE = 0.05
CONTROL_REGULARIZATION = 0.01
FINITE_DIFFERENCE_EPSILON = 1.0e-6
FINITE_DIFFERENCE_TOLERANCE = 1.0e-8
MAX_CONTROL_L2 = 0.25
FLOAT_DTYPE = torch.float64

EXPECTED_V054_LANE_FINGERPRINT = (
    "f7256b7866099f6a682ac7bd733acb26f278eac5000a030ef34932151492077a"
)
EXPECTED_V054_PROGRAM_FINGERPRINT = (
    "686ae870d0694fbecc387836911b13265c04f8cc1b9bc4430369479470b32cfb"
)
EXPECTED_V054_ADJOINT_FINGERPRINT = (
    "0a64495dd1bc0abe8f1c659d1d029dcd61c640f7a8d42b0a2f1bc376e7845406"
)
EXPECTED_V054_EXACT_CONTROL_FINGERPRINT = (
    "3aebb5d68438dcdfb4eb351425c235a170d803017100ae32022988363ab453ad"
)

ARTIFACT_FILES = (
    "result.json",
    "calls.jsonl",
    "attempt_journal.jsonl",
    "provider_inputs.json",
    "apply_revision_trace.json",
    "report.md",
    "manifest.json",
)

LOCKED_SOURCE_PATHS = {
    "product_runtime": Path("ebrt.py"),
    "public_fixture": FIXTURE_PATH.relative_to(ROOT),
    "post_call_semantic_gold": GOLD_PATH.relative_to(ROOT),
    "source_case": SOURCE_CASE_PATH.relative_to(ROOT),
    "temporal_controller": Path("temporal_adjoint_lineage_v0_5_4.py"),
    "temporal_fixture": TEMPORAL_FIXTURE_PATH.relative_to(ROOT),
    "temporal_lane": TEMPORAL_LANE_PATH.relative_to(ROOT),
    "factorized_lineage": Path("factorized_lineage_v0_5_3.py"),
    "factorized_regression": V053_REGRESSION_PATH.relative_to(ROOT),
    "provider_boundary": Path("openai_response_boundary_v0_4_3.py"),
    "provider_types": Path("language_replay_bridge_v0_4.py"),
    "requirements": Path("requirements.txt"),
    "requirements_live": Path("requirements-live.txt"),
}

FORBIDDEN_PROVIDER_KEYS = frozenset(
    {
        "accepted_closure",
        "accepted_closure_id",
        "correct_answer",
        "expected_answer",
        "expected_closure",
        "expected_support",
        "gold",
        "grade",
        "gradient",
        "loss",
        "quality_label",
        "required_support",
        "target_answer",
        "target_closure",
        "target_closure_id",
        "treatment",
        "treatment_id",
    }
)

CLAIM_BOUNDARY = (
    "This is one contaminated synthetic product-acceptance path, not a fresh benchmark, causal comparison, or population estimate.",
    "The controller target is an explicit case-specific oracle and the candidate catalog is supplied public structure, not autonomous semantic discovery.",
    "The actual structurally valid Before output is normalized into the local controller; no free-text claim or private reasoning is reused.",
    "The v0.6.2.1 scalar recurrence is a new actual-Before-conditioned surrogate initialized from a recomputed v0.5.4-derived effect basis; it is not an exact replay of the v0.5.4 temporal mechanism.",
    "A real local backward pass stops at the public control map. GPT-5.6, JSON projection, provider parsing, generation, and grading are not differentiated.",
    "A passing result establishes one executable and verifiable Apply Revision path; effect attribution remains NOT_ASSESSED.",
    "No result supports hidden-state editing, attention or KV-cache control, causal superiority, quality improvement, or general reasoning improvement.",
)

PROVIDER_INSTRUCTIONS = (
    "Return only the strict public Apply Revision response. Raw evidence is the "
    "only semantic authority. Candidate closure IDs are opaque alternatives whose "
    "graphs contain public support structure but no target values, answer, candidate-role label, "
    "quality label, or accepted choice. Select exactly one supplied closure and "
    "derive current_answer plus every target value independently from the visible "
    "raw evidence. When apply_revision is present, treat it only as an external "
    "inspection operation: follow the reinspection order, suppress listed active "
    "evidence, and preserve listed stable evidence, but never treat the operation as new "
    "evidence, truth, an expected answer, or permission to override raw evidence. "
    "Explicit later invalidation dominates active support. Return each target ID "
    "exactly once using only its allowed value. Do not return private chain-of-"
    "thought, prose reasoning, invented evidence, or an unknown closure ID."
)


JsonObject = dict[str, Any]


class ApplyRevisionError(RuntimeError):
    """Fail-closed error with a stable public reason code."""

    def __init__(self, reason_code: str, detail: str = "") -> None:
        self.reason_code = reason_code
        super().__init__(reason_code if not detail else f"{reason_code}: {detail}")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class TargetValueOutput(_StrictModel):
    target_id: str = Field(min_length=1, max_length=96)
    target_type: Literal["fact", "constraint"]
    slot: str = Field(min_length=1, max_length=96)
    value: str = Field(min_length=1, max_length=160)


class ApplyRevisionProviderOutput(_StrictModel):
    schema_version: Literal[OUTPUT_SCHEMA]
    checkpoint_id: str = Field(min_length=1, max_length=160)
    current_answer: Literal["POLISH", "PROVE"]
    selected_closure_id: str = Field(min_length=1, max_length=96)
    target_values: list[TargetValueOutput] = Field(min_length=3, max_length=3)


def _canonical_bytes(value: Any, *, trailing_newline: bool = False) -> bytes:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return raw + (b"\n" if trailing_newline else b"")


def _pretty_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_path(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _clone(value: Any) -> Any:
    return copy.deepcopy(value)


def _without_fingerprint(value: Mapping[str, Any]) -> JsonObject:
    output = dict(value)
    output.pop("fingerprint_sha256", None)
    return output


def _seal(value: Mapping[str, Any]) -> JsonObject:
    output = _without_fingerprint(value)
    output["fingerprint_sha256"] = _fingerprint(output)
    return output


def _require(condition: bool, reason: str, detail: str = "") -> None:
    if not condition:
        raise ApplyRevisionError(reason, detail)


def _reject_constant(value: str) -> Any:
    raise ApplyRevisionError("NONFINITE_JSON", value)


def _reject_duplicates(pairs: Sequence[tuple[str, Any]]) -> JsonObject:
    output: JsonObject = {}
    for key, value in pairs:
        if key in output:
            raise ApplyRevisionError("DUPLICATE_JSON_KEY", key)
        output[key] = value
    return output


def _reject_nonfinite(value: Any, *, label: str) -> None:
    if isinstance(value, float):
        _require(math.isfinite(value), "NONFINITE_JSON", label)
    elif isinstance(value, Mapping):
        for child in value.values():
            _reject_nonfinite(child, label=label)
    elif isinstance(value, list):
        for child in value:
            _reject_nonfinite(child, label=label)


def _strict_json_bytes(raw: bytes, *, label: str) -> Any:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicates,
            parse_constant=_reject_constant,
        )
    except ApplyRevisionError:
        raise
    except Exception as error:
        raise ApplyRevisionError("INVALID_JSON", label) from error
    _reject_nonfinite(value, label=label)
    return value


def _strict_load(path: Path) -> JsonObject:
    value = _strict_json_bytes(path.read_bytes(), label=str(path))
    _require(isinstance(value, dict), "JSON_ROOT_NOT_OBJECT", str(path))
    return value


def _validate_seal(value: Mapping[str, Any], label: str) -> None:
    _require(
        value.get("fingerprint_sha256") == _fingerprint(_without_fingerprint(value)),
        "FINGERPRINT_MISMATCH",
        label,
    )


def _exact_keys(value: Any, expected: set[str], label: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), "OBJECT_REQUIRED", label)
    _require(set(value) == expected, "OBJECT_SCHEMA_DRIFT", label)
    return value


def _unique_strings(value: Any, label: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    _require(isinstance(value, list), "STRING_LIST_REQUIRED", label)
    output = tuple(value)
    _require(allow_empty or bool(output), "STRING_LIST_EMPTY", label)
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


def _file_receipt(path: Path) -> JsonObject:
    raw = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "bytes": len(raw), "sha256": _sha256_bytes(raw)}


def _catalog_order_key(*, salt: str, phase_id: str, closure_id: str) -> str:
    return _fingerprint(
        {"salt": salt, "phase_id": phase_id, "closure_id": closure_id}
    )


def _runtime_contract() -> JsonObject:
    return {
        "python": platform.python_version(),
        "machine": platform.machine(),
        "torch": package_version("torch"),
        "pydantic": package_version("pydantic"),
        "openai": package_version("openai"),
        "provider": "openai_responses",
        "api": "responses.with_raw_response.parse+raw.parse",
        "model": MODEL,
        "reasoning_effort": REASONING_EFFORT,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "timeout_seconds": int(TIMEOUT_SECONDS),
        "sdk_retries": 0,
        "store": False,
        "previous_response_id": False,
        "truncation": "disabled",
    }


def _catalog_map(fixture: Mapping[str, Any], phase_id: str) -> dict[str, Mapping[str, Any]]:
    catalogs = fixture["closure_catalogs"]
    rows = catalogs[phase_id]
    return {str(row["closure_id"]): row for row in rows}


def _validate_graph_candidate(
    candidate: Mapping[str, Any],
    *,
    phase_id: str,
    horizon: Sequence[str],
    slot_specs: Mapping[str, Mapping[str, Any]],
) -> None:
    _exact_keys(candidate, {"closure_id", "graph"}, f"candidate.{phase_id}")
    closure_id = candidate["closure_id"]
    _require(isinstance(closure_id, str) and closure_id.startswith("K_"), "CLOSURE_ID_INVALID")
    graph = _exact_keys(
        candidate["graph"],
        {"support_nodes", "targets", "invalidation_edges"},
        f"candidate.{closure_id}.graph",
    )
    horizon_set = set(horizon)
    supports: dict[str, Mapping[str, Any]] = {}
    for row in graph["support_nodes"]:
        _exact_keys(row, {"support_id", "evidence_ids"}, "support_node")
        support_id = row["support_id"]
        _require(isinstance(support_id, str) and support_id.startswith("support:"), "SUPPORT_ID_INVALID")
        _require(support_id not in supports, "SUPPORT_ID_DUPLICATE")
        evidence_ids = _unique_strings(row["evidence_ids"], f"support.{support_id}")
        _require(set(evidence_ids) <= horizon_set, "SUPPORT_EVIDENCE_OUTSIDE_HORIZON")
        supports[support_id] = row
    _require(bool(supports), "SUPPORT_SET_EMPTY")

    targets: dict[str, Mapping[str, Any]] = {}
    for row in graph["targets"]:
        _exact_keys(
            row,
            {"target_id", "target_type", "slot", "direct_support_ids", "depends_on_target_ids"},
            "target",
        )
        target_id = row["target_id"]
        slot = row["slot"]
        target_type = row["target_type"]
        _require(isinstance(target_id, str) and target_id not in targets, "TARGET_ID_INVALID")
        _require(slot in slot_specs, "TARGET_SLOT_UNKNOWN")
        expected_type = "constraint" if slot == "video_constraint" else "fact"
        _require(target_type == expected_type, "TARGET_TYPE_INVALID")
        _require(target_id == f"{expected_type}:{slot}", "TARGET_ID_SLOT_MISMATCH")
        direct = _unique_strings(row["direct_support_ids"], f"target.{target_id}.direct")
        _require(set(direct) <= set(supports), "TARGET_SUPPORT_UNKNOWN")
        _unique_strings(
            row["depends_on_target_ids"],
            f"target.{target_id}.depends",
            allow_empty=True,
        )
        targets[target_id] = row
    _require(
        set(targets) == {f"{'constraint' if slot == 'video_constraint' else 'fact'}:{slot}" for slot in slot_specs},
        "TARGET_SET_INVALID",
    )
    used = {item for row in targets.values() for item in row["direct_support_ids"]}
    _require(used == set(supports), "ORPHAN_SUPPORT_NODE")
    for row in targets.values():
        for upstream in row["depends_on_target_ids"]:
            _require(upstream in targets, "TARGET_DEPENDENCY_UNKNOWN")
            _require(
                row["target_type"] == targets[upstream]["target_type"] == "fact"
                and upstream != row["target_id"],
                "TARGET_DEPENDENCY_FORBIDDEN",
            )

    indegree = {target_id: 0 for target_id in targets}
    adjacency = {target_id: [] for target_id in targets}
    for target_id, row in targets.items():
        for upstream in row["depends_on_target_ids"]:
            adjacency[upstream].append(target_id)
            indegree[target_id] += 1
    queue = [target_id for target_id, degree in indegree.items() if degree == 0]
    heapq.heapify(queue)
    visited: list[str] = []
    while queue:
        target_id = heapq.heappop(queue)
        visited.append(target_id)
        for downstream in sorted(adjacency[target_id]):
            indegree[downstream] -= 1
            if indegree[downstream] == 0:
                heapq.heappush(queue, downstream)
    _require(len(visited) == len(targets), "TARGET_DEPENDENCY_CYCLE")

    seen_edges: set[tuple[str, str]] = set()
    ordinal = {item: index for index, item in enumerate(horizon)}
    for edge in graph["invalidation_edges"]:
        _exact_keys(edge, {"source_evidence_id", "target_evidence_id"}, "invalidation")
        pair = (edge["source_evidence_id"], edge["target_evidence_id"])
        _require(pair not in seen_edges and set(pair) <= horizon_set, "INVALIDATION_INVALID")
        _require(ordinal[pair[0]] > ordinal[pair[1]], "INVALIDATION_TEMPORAL_ORDER_INVALID")
        seen_edges.add(pair)
    active = {item for row in supports.values() for item in row["evidence_ids"]}
    _require(not (active & {target for _, target in seen_edges}), "INVALIDATED_SUPPORT_ACTIVE")


def validate_fixture(fixture: Mapping[str, Any]) -> JsonObject:
    _exact_keys(
        fixture,
        {
            "schema_version",
            "status",
            "fixture_id",
            "source_case",
            "case",
            "closure_catalogs",
            "public_revision_contract",
            "controller_contract",
            "provider_contract",
            "execution_contract",
            "claim_boundary",
            "fingerprint_sha256",
        },
        "fixture",
    )
    _validate_seal(fixture, "fixture")
    _require(fixture["schema_version"] == FIXTURE_SCHEMA, "FIXTURE_SCHEMA_DRIFT")
    _require(fixture["status"] == "LOCKED_PUBLIC_PRODUCT_ACCEPTANCE_INPUT", "FIXTURE_STATUS_DRIFT")
    source = _exact_keys(
        fixture["source_case"],
        {"path", "file_sha256", "fixture_fingerprint_sha256"},
        "source_case",
    )
    _require(source["path"] == str(SOURCE_CASE_PATH.relative_to(ROOT)), "SOURCE_CASE_PATH_DRIFT")
    _require(source["file_sha256"] == _sha256_path(SOURCE_CASE_PATH), "SOURCE_CASE_BYTES_DRIFT")
    source_case = _strict_load(SOURCE_CASE_PATH)
    _require(
        source["fixture_fingerprint_sha256"] == source_case["fixture_fingerprint_sha256"],
        "SOURCE_CASE_FINGERPRINT_DRIFT",
    )
    case = _exact_keys(
        fixture["case"],
        {"case_id", "question", "answer_choices", "decision_slots", "initial_evidence", "late_evidence"},
        "case",
    )
    source_payload = source_case["case"]
    for key in ("case_id", "question", "answer_choices", "decision_slots", "initial_evidence", "late_evidence"):
        _require(_canonical_bytes(case[key]) == _canonical_bytes(source_payload[key]), "SOURCE_CASE_PAYLOAD_DRIFT", key)
    answers = _unique_strings(case["answer_choices"], "answer_choices")
    _require(tuple(answers) == ("POLISH", "PROVE"), "ANSWER_CHOICES_DRIFT")
    slots: dict[str, Mapping[str, Any]] = {}
    for row in case["decision_slots"]:
        _exact_keys(row, {"slot_id", "description", "allowed_values"}, "decision_slot")
        slot = row["slot_id"]
        _require(isinstance(slot, str) and slot not in slots, "DECISION_SLOT_INVALID")
        _unique_strings(row["allowed_values"], f"slot.{slot}.values")
        slots[slot] = row
    evidence = list(case["initial_evidence"]) + [case["late_evidence"]]
    evidence_ids = []
    for row in evidence:
        _exact_keys(row, {"evidence_id", "text"}, "evidence")
        _require(isinstance(row["text"], str) and row["text"], "EVIDENCE_TEXT_INVALID")
        evidence_ids.append(row["evidence_id"])
    _require(evidence_ids == ["R1", "R2", "R3", "R4", "R5", "R6"], "EVIDENCE_ORDER_DRIFT")

    execution = fixture["execution_contract"]
    ordering = _exact_keys(
        execution["closure_catalog_ordering"],
        {
            "algorithm",
            "salt",
            "canonical_key_fields",
            "canonicalization",
            "role_blind",
            "array_order_must_equal_key_order",
        },
        "closure_catalog_ordering",
    )
    _require(
        ordering["algorithm"] == "ascending_sha256_of_canonical_json"
        and ordering["canonical_key_fields"] == ["salt", "phase_id", "closure_id"]
        and ordering["canonicalization"] == "utf8_sorted_keys_no_whitespace"
        and ordering["role_blind"] is True
        and ordering["array_order_must_equal_key_order"] is True,
        "CATALOG_ORDERING_CONTRACT_DRIFT",
    )
    _require(execution["phase_order"] == list(PHASES), "PHASE_ORDER_DRIFT")
    _require(execution["evidence_horizons"]["before_event"] == evidence_ids[:5], "BEFORE_HORIZON_DRIFT")
    _require(execution["evidence_horizons"]["after_event"] == evidence_ids, "AFTER_HORIZON_DRIFT")
    _require(
        execution["exact_provider_attempts"] == 2
        and execution["one_attempt_per_phase"] is True
        and execution["retry_count"] == 0
        and execution["no_resume"] is True
        and execution["no_backfill"] is True
        and execution["no_third_call"] is True
        and execution["after_payload_materialized_only_after_before_terminal"] is True
        and execution["structurally_valid_before_always_continues"] is True
        and execution["post_call_gold_loaded_only_after_two_structurally_valid_terminals"] is True
        and execution["effect_attribution_status"] == "NOT_ASSESSED",
        "EXECUTION_CONTRACT_DRIFT",
    )
    catalogs = _exact_keys(fixture["closure_catalogs"], set(PHASES), "closure_catalogs")
    all_ids: set[str] = set()
    for phase_id in PHASES:
        rows = catalogs[phase_id]
        _require(isinstance(rows, list) and len(rows) >= 2, "CATALOG_CARDINALITY_INVALID", phase_id)
        observed_ids = [row["closure_id"] for row in rows]
        expected_ids = sorted(
            observed_ids,
            key=lambda closure_id: _catalog_order_key(
                salt=ordering["salt"],
                phase_id=phase_id,
                closure_id=closure_id,
            ),
        )
        _require(observed_ids == expected_ids, "CATALOG_ROLE_BLIND_ORDER_DRIFT", phase_id)
        horizon = execution["evidence_horizons"][phase_id]
        for candidate in rows:
            _validate_graph_candidate(candidate, phase_id=phase_id, horizon=horizon, slot_specs=slots)
            _require(candidate["closure_id"] not in all_ids, "CLOSURE_ID_DUPLICATE")
            all_ids.add(candidate["closure_id"])

    revision = fixture["public_revision_contract"]
    _require(
        revision["correction_evidence_id"] == "R6"
        and revision["invalidated_evidence_ids"] == ["R3"]
        and revision["stable_evidence_id"] == "R5"
        and revision["stable_target_id"] == "constraint:video_constraint",
        "REVISION_CONTRACT_DRIFT",
    )
    _require(
        revision["normalized_prior_state_fields"]
        == [
            "schema_version",
            "checkpoint_id",
            "current_answer",
            "selected_closure_id",
            "target_values",
            "compiled_closure_fingerprint_sha256",
            "fingerprint_sha256",
        ]
        and revision["compiled_actuator_fields"]
        == ["reinspect_evidence_ids", "suppress_evidence_ids", "preserve_evidence_ids"],
        "REVISION_PUBLIC_FIELDS_DRIFT",
    )
    controller = fixture["controller_contract"]
    _require(
        controller["controller_kind"] == "single_temporal_adjoint_public_trajectory"
        and controller["source_version"] == "v0.5.4"
        and controller["schedule_policy_id"] == "correction_late"
        and controller["historical_exact_source_arm"] == "C"
        and controller["actual_before_state_required"] is True
        and float(controller["terminal_decision_target"]) == 0.72,
        "CONTROLLER_CONTRACT_DRIFT",
    )
    for key, expected in {
        "state_decay": STATE_DECAY,
        "step_size": STEP_SIZE,
        "control_regularization": CONTROL_REGULARIZATION,
        "finite_difference_epsilon": FINITE_DIFFERENCE_EPSILON,
        "finite_difference_tolerance": FINITE_DIFFERENCE_TOLERANCE,
        "max_control_l2": MAX_CONTROL_L2,
    }.items():
        _require(float(controller[key]) == expected, "CONTROLLER_PARAMETER_DRIFT", key)
    _require(
        controller["runtime_provenance"]
        == "NEW_V0_6_2_1_ACTUAL_BEFORE_CONDITIONED_SCALAR_RECURRENCE_WITH_V0_5_4_CORRECTION_LATE_EXACT_ARM_C_EFFECT_BASIS"
        and controller["target_provenance"] == "CONTAMINATED_CASE_SPECIFIC_EXPLICIT_ORACLE"
        and controller["actual_before_aggregation"]["component_order"]
        == ["current_answer", "fact:demo_centerpiece", "fact:final_priority"]
        and controller["scalar_recurrence"]["backward_calls"] == 1
        and controller["scalar_recurrence"]["after_provider_output_participates"] is False,
        "CONTROLLER_RUNTIME_PROVENANCE_DRIFT",
    )
    provider = fixture["provider_contract"]
    _require(
        provider["input_schema_version"] == INPUT_SCHEMA
        and provider["output_schema_version"] == OUTPUT_SCHEMA
        and provider["model"] == MODEL
        and provider["reasoning_effort"] == REASONING_EFFORT
        and provider["max_output_tokens"] == MAX_OUTPUT_TOKENS
        and provider["timeout_seconds"] == int(TIMEOUT_SECONDS)
        and provider["sdk_retries"] == 0
        and provider["store"] is False
        and provider["previous_response_id"] is False
        and provider["truncation"] == "disabled",
        "PROVIDER_CONTRACT_DRIFT",
    )
    _unique_strings(fixture["claim_boundary"], "claim_boundary")
    return {
        "status": "PASS",
        "fixture_id": fixture["fixture_id"],
        "fingerprint_sha256": fixture["fingerprint_sha256"],
        "closure_ids": sorted(all_ids),
    }


def load_fixture() -> JsonObject:
    fixture = _strict_load(FIXTURE_PATH)
    validate_fixture(fixture)
    return fixture


def _phase_evidence(fixture: Mapping[str, Any], phase_id: str) -> list[JsonObject]:
    case = fixture["case"]
    all_rows = list(case["initial_evidence"]) + [case["late_evidence"]]
    by_id = {row["evidence_id"]: row for row in all_rows}
    return [
        _clone(by_id[item])
        for item in fixture["execution_contract"]["evidence_horizons"][phase_id]
    ]


def _normalized_prior_state(compiled: Mapping[str, Any]) -> JsonObject:
    state = _seal(
        {
            "schema_version": "ebrt-apply-revision-prior-state-v0.6.2.1",
            "checkpoint_id": compiled["checkpoint_id"],
            "current_answer": compiled["current_answer"],
            "selected_closure_id": compiled["selected_closure_id"],
            "target_values": [
                {
                    "target_id": row["target_id"],
                    "target_type": row["target_type"],
                    "slot": row["slot"],
                    "value": row["value"],
                }
                for row in compiled["targets"]
            ],
            "compiled_closure_fingerprint_sha256": compiled["fingerprint_sha256"],
        }
    )
    _require(
        list(state) == [
            "schema_version",
            "checkpoint_id",
            "current_answer",
            "selected_closure_id",
            "target_values",
            "compiled_closure_fingerprint_sha256",
            "fingerprint_sha256",
        ],
        "PRIOR_STATE_FIELD_ORDER_DRIFT",
    )
    return state


def _compile_candidate_output(
    fixture: Mapping[str, Any],
    phase_id: str,
    output: ApplyRevisionProviderOutput | Mapping[str, Any],
) -> JsonObject:
    try:
        parsed = (
            output
            if isinstance(output, ApplyRevisionProviderOutput)
            else ApplyRevisionProviderOutput.model_validate(output)
        )
    except ValidationError as error:
        raise ApplyRevisionError("OUTPUT_SCHEMA_INVALID") from error
    execution = fixture["execution_contract"]
    _require(parsed.checkpoint_id == execution["checkpoint_ids"][phase_id], "OUTPUT_CHECKPOINT_MISMATCH")
    _require(parsed.current_answer in fixture["case"]["answer_choices"], "OUTPUT_ANSWER_INVALID")
    candidates = _catalog_map(fixture, phase_id)
    _require(parsed.selected_closure_id in candidates, "OUTPUT_CLOSURE_UNKNOWN")
    graph = candidates[parsed.selected_closure_id]["graph"]
    slot_specs = {row["slot_id"]: row for row in fixture["case"]["decision_slots"]}
    values: dict[str, TargetValueOutput] = {}
    for row in parsed.target_values:
        _require(row.target_id not in values, "OUTPUT_TARGET_DUPLICATE")
        _require(row.slot in slot_specs, "OUTPUT_SLOT_UNKNOWN")
        expected_type = "constraint" if row.slot == "video_constraint" else "fact"
        _require(
            row.target_type == expected_type
            and row.target_id == f"{expected_type}:{row.slot}",
            "OUTPUT_TARGET_ID_TYPE_SLOT_MISMATCH",
        )
        _require(row.value in slot_specs[row.slot]["allowed_values"], "OUTPUT_VALUE_OUTSIDE_SCHEMA")
        values[row.target_id] = row
    graph_targets = {row["target_id"]: row for row in graph["targets"]}
    _require(set(values) == set(graph_targets), "OUTPUT_TARGET_SET_MISMATCH")
    supports = {row["support_id"]: row for row in graph["support_nodes"]}
    horizon = tuple(execution["evidence_horizons"][phase_id])
    ordinal = {item: index for index, item in enumerate(horizon)}

    indegree = {target_id: 0 for target_id in graph_targets}
    adjacency = {target_id: [] for target_id in graph_targets}
    for target_id, row in graph_targets.items():
        for upstream in row["depends_on_target_ids"]:
            indegree[target_id] += 1
            adjacency[upstream].append(target_id)
    queue = [target_id for target_id, degree in indegree.items() if degree == 0]
    heapq.heapify(queue)
    topological: list[str] = []
    while queue:
        target_id = heapq.heappop(queue)
        topological.append(target_id)
        for downstream in sorted(adjacency[target_id]):
            indegree[downstream] -= 1
            if indegree[downstream] == 0:
                heapq.heappush(queue, downstream)
    _require(len(topological) == len(graph_targets), "OUTPUT_CLOSURE_CYCLE")

    direct_by_target: dict[str, set[str]] = {}
    inherited_by_target: dict[str, set[str]] = {}
    total_by_target: dict[str, set[str]] = {}
    for target_id in topological:
        row = graph_targets[target_id]
        direct = {
            evidence_id
            for support_id in row["direct_support_ids"]
            for evidence_id in supports[support_id]["evidence_ids"]
        }
        ancestor = {
            evidence_id
            for upstream in row["depends_on_target_ids"]
            for evidence_id in total_by_target[upstream]
        }
        inherited = ancestor - direct
        direct_by_target[target_id] = direct
        inherited_by_target[target_id] = inherited
        total_by_target[target_id] = direct | inherited
    invalidation_edges = sorted(
        (_clone(row) for row in graph["invalidation_edges"]),
        key=lambda row: (row["source_evidence_id"], row["target_evidence_id"]),
    )
    invalidated = {row["target_evidence_id"] for row in invalidation_edges}
    active = {item for values_set in total_by_target.values() for item in values_set}
    _require(not (active & invalidated), "OUTPUT_INVALIDATED_SUPPORT_ACTIVE")
    targets = []
    for target_id in sorted(graph_targets):
        value = values[target_id]
        targets.append(
            {
                "target_id": target_id,
                "target_type": value.target_type,
                "slot": value.slot,
                "value": value.value,
                "direct_active_evidence_ids": sorted(direct_by_target[target_id], key=ordinal.__getitem__),
                "inherited_active_evidence_ids": sorted(inherited_by_target[target_id], key=ordinal.__getitem__),
                "all_active_evidence_ids": sorted(total_by_target[target_id], key=ordinal.__getitem__),
            }
        )
    normalized_output = parsed.model_dump(mode="json")
    normalized_output["target_values"] = sorted(normalized_output["target_values"], key=lambda row: row["target_id"])
    return _seal(
        {
            "schema_version": COMPILED_SCHEMA,
            "phase_id": phase_id,
            "checkpoint_id": parsed.checkpoint_id,
            "current_answer": parsed.current_answer,
            "selected_closure_id": parsed.selected_closure_id,
            "source_horizon_evidence_ids": list(horizon),
            "active_support_evidence_ids": sorted(active, key=ordinal.__getitem__),
            "invalidated_evidence_ids": sorted(invalidated, key=ordinal.__getitem__),
            "invalidation_edges": invalidation_edges,
            "targets": targets,
            "normalized_output": normalized_output,
            "normalized_output_fingerprint_sha256": _fingerprint(normalized_output),
        }
    )


def _state_coordinate(value: str, choices: Sequence[str]) -> float:
    _require(value in choices and len(choices) >= 1, "STATE_COORDINATE_INVALID")
    if len(choices) == 1:
        return 0.0
    return -1.0 + 2.0 * choices.index(value) / (len(choices) - 1)


def _actual_before_scalar(fixture: Mapping[str, Any], compiled: Mapping[str, Any]) -> tuple[float, JsonObject]:
    case = fixture["case"]
    slot_specs = {row["slot_id"]: row for row in case["decision_slots"]}
    components = [
        {
            "axis": "current_answer",
            "value": compiled["current_answer"],
            "coordinate": _state_coordinate(compiled["current_answer"], case["answer_choices"]),
        }
    ]
    for row in compiled["targets"]:
        if row["target_type"] != "fact":
            continue
        components.append(
            {
                "axis": row["target_id"],
                "value": row["value"],
                "coordinate": _state_coordinate(row["value"], slot_specs[row["slot"]]["allowed_values"]),
            }
        )
    _require(len(components) == 3, "BEFORE_STATE_COMPONENT_COUNT_INVALID")
    scalar = math.fsum(float(row["coordinate"]) for row in components) / len(components)
    state = _seal(
        {
            "schema_version": "ebrt-apply-revision-actual-before-state-v0.6.2.1",
            "source_compiled_fingerprint_sha256": compiled["fingerprint_sha256"],
            "source_selected_closure_id": compiled["selected_closure_id"],
            "active_support_evidence_ids": list(compiled["active_support_evidence_ids"]),
            "components": components,
            "initial_scalar": scalar,
        }
    )
    return scalar, state


def _historical_credit_basis() -> tuple[dict[str, float], JsonObject]:
    program = temporal_v054.compile_program()
    lane = temporal_v054.evaluate_lane(program, "correction_late")
    sealed = lane.sealed_lane
    committed = _strict_load(TEMPORAL_LANE_PATH)
    _require(_canonical_bytes(sealed) == _canonical_bytes(committed), "V054_RECOMPUTE_BYTE_DRIFT")
    _require(sealed["fingerprint_sha256"] == EXPECTED_V054_LANE_FINGERPRINT, "V054_LANE_FINGERPRINT_DRIFT")
    _require(sealed["program_fingerprint_sha256"] == EXPECTED_V054_PROGRAM_FINGERPRINT, "V054_PROGRAM_FINGERPRINT_DRIFT")
    _require(sealed["adjoint_audit"]["fingerprint_sha256"] == EXPECTED_V054_ADJOINT_FINGERPRINT, "V054_ADJOINT_FINGERPRINT_DRIFT")
    exact = sealed["control_maps"]["C"]
    _require(exact["fingerprint_sha256"] == EXPECTED_V054_EXACT_CONTROL_FINGERPRINT, "V054_CONTROL_FINGERPRINT_DRIFT")
    absolute: defaultdict[str, float] = defaultdict(float)
    signed: defaultdict[str, float] = defaultdict(float)
    for row in exact["controls"]:
        parts = row["site_id"].split(":")
        _require(len(parts) >= 6 and parts[0] == "q" and parts[1] == "correction_late", "V054_SITE_ID_INVALID")
        evidence_id = parts[3]
        value = float(row["normalized_u"])
        absolute[evidence_id] += abs(value)
        signed[evidence_id] += value
    evidence_ids = [f"R{index}" for index in range(1, 7)]
    _require(set(absolute) == set(evidence_ids), "V054_EVIDENCE_CREDIT_SET_DRIFT")
    maximum = max(absolute.values())
    _require(maximum > 0.0, "V054_CREDIT_BASIS_ZERO")
    effects = {item: absolute[item] / maximum for item in evidence_ids}
    receipt = _seal(
        {
            "schema_version": "ebrt-apply-revision-v054-credit-basis-v0.6.2.1",
            "source_lane_fingerprint_sha256": sealed["fingerprint_sha256"],
            "source_program_fingerprint_sha256": sealed["program_fingerprint_sha256"],
            "source_adjoint_fingerprint_sha256": sealed["adjoint_audit"]["fingerprint_sha256"],
            "source_exact_control_fingerprint_sha256": exact["fingerprint_sha256"],
            "source_backward_calls": sealed["adjoint_audit"]["backward_calls"],
            "absolute_credit_by_evidence_id": dict(sorted(absolute.items())),
            "signed_credit_by_evidence_id": dict(sorted(signed.items())),
            "normalized_effect_by_evidence_id": effects,
        }
    )
    return effects, receipt


def _controller_loss(
    controls: torch.Tensor,
    effects: torch.Tensor,
    *,
    initial_state: float,
    target: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    state = torch.tensor(initial_state, dtype=FLOAT_DTYPE)
    states: list[torch.Tensor] = []
    for control, effect in zip(controls, effects, strict=True):
        state = torch.tanh(STATE_DECAY * state + control * effect)
        states.append(state)
    loss = (state - target).square() + CONTROL_REGULARIZATION * controls.square().sum()
    return loss, torch.stack(states)


def derive_public_control_map(fixture: Mapping[str, Any], compiled_before: Mapping[str, Any]) -> JsonObject:
    initial_scalar, actual_state = _actual_before_scalar(fixture, compiled_before)
    effect_by_id, source_receipt = _historical_credit_basis()
    evidence_ids = tuple(fixture["execution_contract"]["evidence_horizons"]["after_event"])
    effects = torch.tensor([effect_by_id[item] for item in evidence_ids], dtype=FLOAT_DTYPE)
    controls = torch.zeros(len(evidence_ids), dtype=FLOAT_DTYPE, requires_grad=True)
    target = float(fixture["controller_contract"]["terminal_decision_target"])
    loss_before, states_before = _controller_loss(controls, effects, initial_state=initial_scalar, target=target)
    loss_before.backward()
    _require(controls.grad is not None, "BACKWARD_GRADIENT_MISSING")
    gradient = controls.grad.detach().clone()
    displacement = -STEP_SIZE * gradient
    loss_after, states_after = _controller_loss(displacement, effects, initial_state=initial_scalar, target=target)
    epsilon = FINITE_DIFFERENCE_EPSILON
    finite_difference: list[float] = []
    for index in range(len(evidence_ids)):
        positive = torch.zeros(len(evidence_ids), dtype=FLOAT_DTYPE)
        negative = torch.zeros(len(evidence_ids), dtype=FLOAT_DTYPE)
        positive[index] = epsilon
        negative[index] = -epsilon
        plus, _ = _controller_loss(positive, effects, initial_state=initial_scalar, target=target)
        minus, _ = _controller_loss(negative, effects, initial_state=initial_scalar, target=target)
        finite_difference.append(float((plus - minus) / (2.0 * epsilon)))
    errors = [abs(float(gradient[index]) - finite_difference[index]) for index in range(len(evidence_ids))]
    norm = float(torch.linalg.vector_norm(displacement))
    rows = [
        {
            "evidence_id": evidence_id,
            "source_effect": float(effects[index]),
            "gradient": float(gradient[index]),
            "finite_difference_gradient": finite_difference[index],
            "signed_public_credit": float(displacement[index]),
            "active_before": evidence_id in compiled_before["active_support_evidence_ids"],
        }
        for index, evidence_id in enumerate(evidence_ids)
    ]
    checks = {
        "actual_before_state_bound_to_controller": actual_state["source_compiled_fingerprint_sha256"] == compiled_before["fingerprint_sha256"],
        "local_backward_executed": controls.grad is not None,
        "finite_public_credit": all(math.isfinite(row["signed_public_credit"]) for row in rows),
        "surrogate_objective_decreased": float(loss_after.detach()) < float(loss_before.detach()),
        "non_neutral_control_map": any(abs(row["signed_public_credit"]) > 0.0 for row in rows),
        "control_budget_respected": norm <= MAX_CONTROL_L2,
        "finite_difference_agreement": max(errors) <= FINITE_DIFFERENCE_TOLERANCE,
        "gradient_stops_before_provider": True,
    }
    _require(all(checks.values()), "CONTROLLER_HARD_GATE_FAILED")
    return _seal(
        {
            "schema_version": CONTROL_SCHEMA,
            "status": "PASS",
            "actual_before_state": actual_state,
            "source_credit_basis": source_receipt,
            "dtype": "torch.float64",
            "backward_calls": 1,
            "objective_before": float(loss_before.detach()),
            "objective_after": float(loss_after.detach()),
            "terminal_target": target,
            "state_trace_before": [float(value) for value in states_before.detach()],
            "state_trace_after": [float(value) for value in states_after.detach()],
            "control_l2": norm,
            "max_control_l2": MAX_CONTROL_L2,
            "maximum_finite_difference_error": max(errors),
            "finite_difference_tolerance": FINITE_DIFFERENCE_TOLERANCE,
            "credit_rows": rows,
            "checks": checks,
            "gradient_boundary": {
                "starts_at": "actual normalized public Before state plus public temporal credit basis",
                "ends_at": "public control map",
                "crosses_json": False,
                "crosses_provider": False,
                "hosted_model_differentiated": False,
                "actual_provider_output_participated_in_surrogate": True,
                "after_provider_output_participated_in_surrogate": False,
            },
        }
    )


def compile_actuator(
    fixture: Mapping[str, Any],
    compiled_before: Mapping[str, Any],
    control_map: Mapping[str, Any],
) -> JsonObject:
    revision = fixture["public_revision_contract"]
    policy = fixture["controller_contract"]["compilation_policy"]
    invalidated = set(revision["invalidated_evidence_ids"])
    stable_evidence = revision["stable_evidence_id"]
    rows = control_map["credit_rows"]
    eligible = [
        row
        for row in rows
        if row["evidence_id"] not in invalidated
        and row["evidence_id"] != stable_evidence
        and abs(float(row["signed_public_credit"])) > 0.0
    ]
    eligible.sort(key=lambda row: (-abs(float(row["signed_public_credit"])), row["evidence_id"]))
    reinspect = [row["evidence_id"] for row in eligible[: int(policy["reinspection_count"])]]
    active_before = set(compiled_before["active_support_evidence_ids"])
    suppress = sorted(invalidated & active_before)
    preserve = [stable_evidence] if stable_evidence in active_before else []
    _require(len(reinspect) == int(policy["reinspection_count"]), "ACTUATOR_REINSPECTION_COUNT_INVALID")
    actuator = _seal(
        {
            "schema_version": ACTUATOR_SCHEMA,
            "source_before_compiled_fingerprint_sha256": compiled_before["fingerprint_sha256"],
            "source_control_map_fingerprint_sha256": control_map["fingerprint_sha256"],
            "event_id": revision["event_id"],
            "correction_evidence_id": revision["correction_evidence_id"],
            "reinspect_evidence_ids": reinspect,
            "suppress_evidence_ids": suppress,
            "preserve_evidence_ids": preserve,
            "gradient_stops_here": True,
        }
    )
    _require(reinspect == ["R6", "R4", "R2"], "ACTUATOR_REINSPECTION_DRIFT")
    _require(
        suppress == sorted(invalidated & active_before)
        and preserve == ([stable_evidence] if stable_evidence in active_before else []),
        "ACTUATOR_EVENT_OPERATION_DRIFT",
    )
    _require(
        [key for key in fixture["public_revision_contract"]["compiled_actuator_fields"]]
        == ["reinspect_evidence_ids", "suppress_evidence_ids", "preserve_evidence_ids"],
        "ACTUATOR_PUBLIC_FIELD_CONTRACT_DRIFT",
    )
    return actuator


def _candidate_public_rows(fixture: Mapping[str, Any], phase_id: str) -> list[JsonObject]:
    return [
        {"closure_id": row["closure_id"], "graph": _clone(row["graph"])}
        for row in fixture["closure_catalogs"][phase_id]
    ]


def build_provider_payload(
    fixture: Mapping[str, Any],
    phase_id: str,
    *,
    compiled_before: Mapping[str, Any] | None = None,
    actuator: Mapping[str, Any] | None = None,
) -> JsonObject:
    _require(phase_id in PHASES, "PHASE_UNKNOWN")
    before_phase = phase_id == "before_event"
    _require(
        (compiled_before is None and actuator is None) if before_phase else (compiled_before is not None and actuator is not None),
        "DYNAMIC_PAYLOAD_DEPENDENCY_INVALID",
    )
    case = fixture["case"]
    execution = fixture["execution_contract"]
    prior_state = None if before_phase else _normalized_prior_state(compiled_before or {})
    apply_revision = None
    if not before_phase:
        assert actuator is not None
        apply_revision = {
            "schema_version": "ebrt-apply-revision-operation-v0.6.2.1",
            "operation": "APPLY_REVISION",
            "source_prior_state_fingerprint_sha256": prior_state["fingerprint_sha256"],
            "source_control_map_fingerprint_sha256": actuator["source_control_map_fingerprint_sha256"],
            "source_actuator_fingerprint_sha256": actuator["fingerprint_sha256"],
            "event": {
                "event_id": actuator["event_id"],
                "correction_evidence_id": actuator["correction_evidence_id"],
                "invalidated_evidence_ids": list(fixture["public_revision_contract"]["invalidated_evidence_ids"]),
            },
            "reinspect_evidence_ids": list(actuator["reinspect_evidence_ids"]),
            "suppress_evidence_ids": list(actuator["suppress_evidence_ids"]),
            "preserve_evidence_ids": list(actuator["preserve_evidence_ids"]),
            "semantic_authority": "ordered raw evidence only",
            "gradient_boundary": "gradient stopped before this JSON operation and hosted generation",
        }
    payload = {
        "schema_version": INPUT_SCHEMA,
        "case_id": case["case_id"],
        "checkpoint_id": execution["checkpoint_ids"][phase_id],
        "question": case["question"],
        "answer_choices": _clone(case["answer_choices"]),
        "decision_slots": _clone(case["decision_slots"]),
        "all_raw_evidence": _phase_evidence(fixture, phase_id),
        "allowed_evidence_ids": list(execution["evidence_horizons"][phase_id]),
        "candidate_closures": _candidate_public_rows(fixture, phase_id),
        "prior_public_state": prior_state,
        "apply_revision": apply_revision,
    }
    validate_provider_payload(fixture, phase_id, payload)
    return payload


def validate_provider_payload(
    fixture: Mapping[str, Any], phase_id: str, payload: Mapping[str, Any]
) -> JsonObject:
    expected_root = set(fixture["provider_contract"]["input_root_allowlist"])
    _exact_keys(payload, expected_root, f"provider_payload.{phase_id}")
    _require(payload["schema_version"] == INPUT_SCHEMA, "PROVIDER_INPUT_SCHEMA_DRIFT")
    _require(payload["case_id"] == fixture["case"]["case_id"], "PAYLOAD_CASE_DRIFT")
    _require(payload["checkpoint_id"] == fixture["execution_contract"]["checkpoint_ids"][phase_id], "PAYLOAD_CHECKPOINT_DRIFT")
    for key in ("question", "answer_choices", "decision_slots"):
        _require(_canonical_bytes(payload[key]) == _canonical_bytes(fixture["case"][key]), "PAYLOAD_CASE_FIELD_DRIFT", key)
    evidence = payload["all_raw_evidence"]
    ids = [row["evidence_id"] for row in evidence]
    _require(ids == fixture["execution_contract"]["evidence_horizons"][phase_id], "PAYLOAD_EVIDENCE_HORIZON_DRIFT")
    _require(payload["allowed_evidence_ids"] == ids, "PAYLOAD_ALLOWED_EVIDENCE_DRIFT")
    _require(_canonical_bytes(evidence) == _canonical_bytes(_phase_evidence(fixture, phase_id)), "PAYLOAD_EVIDENCE_BYTES_DRIFT")
    _require(
        _canonical_bytes(payload["candidate_closures"]) == _canonical_bytes(_candidate_public_rows(fixture, phase_id)),
        "PAYLOAD_CATALOG_DRIFT",
    )
    if phase_id == "before_event":
        _require(payload["prior_public_state"] is None and payload["apply_revision"] is None, "BEFORE_PAYLOAD_LATE_STATE_LEAK")
    else:
        prior = payload["prior_public_state"]
        operation = payload["apply_revision"]
        _require(isinstance(prior, Mapping) and isinstance(operation, Mapping), "AFTER_DYNAMIC_PAYLOAD_MISSING")
        _exact_keys(
            prior,
            set(fixture["public_revision_contract"]["normalized_prior_state_fields"]),
            "prior_public_state",
        )
        _validate_seal(prior, "prior_public_state")
        _exact_keys(
            operation,
            {
                "schema_version",
                "operation",
                "source_prior_state_fingerprint_sha256",
                "source_control_map_fingerprint_sha256",
                "source_actuator_fingerprint_sha256",
                "event",
                "reinspect_evidence_ids",
                "suppress_evidence_ids",
                "preserve_evidence_ids",
                "semantic_authority",
                "gradient_boundary",
            },
            "apply_revision",
        )
        _exact_keys(
            operation["event"],
            {"event_id", "correction_evidence_id", "invalidated_evidence_ids"},
            "apply_revision.event",
        )
        _require(operation["operation"] == "APPLY_REVISION", "AFTER_OPERATION_INVALID")
        _require(operation["source_prior_state_fingerprint_sha256"] == prior["fingerprint_sha256"], "AFTER_PRIOR_BINDING_INVALID")
        _require(
            operation["event"]
            == {
                "event_id": fixture["public_revision_contract"]["event_id"],
                "correction_evidence_id": fixture["public_revision_contract"]["correction_evidence_id"],
                "invalidated_evidence_ids": fixture["public_revision_contract"]["invalidated_evidence_ids"],
            },
            "AFTER_EVENT_OPERATION_DRIFT",
        )
        for key in fixture["public_revision_contract"]["compiled_actuator_fields"]:
            _unique_strings(operation[key], f"apply_revision.{key}", allow_empty=True)
        _require(
            operation["semantic_authority"] == "ordered raw evidence only"
            and operation["gradient_boundary"]
            == "gradient stopped before this JSON operation and hosted generation",
            "AFTER_OPERATION_BOUNDARY_DRIFT",
        )
    forbidden = _recursive_keys(payload) & FORBIDDEN_PROVIDER_KEYS
    _require(not forbidden, "PROVIDER_PAYLOAD_FORBIDDEN_KEY", ",".join(sorted(forbidden)))
    return {"status": "PASS", "payload_fingerprint_sha256": _fingerprint(payload)}


class OpenAIApplyRevisionProvider(InstrumentedResponsesClientBase):
    def __init__(self, *, client: OpenAI | None = None) -> None:
        super().__init__(
            model=MODEL,
            reasoning_effort=REASONING_EFFORT,
            timeout_seconds=TIMEOUT_SECONDS,
            client=client,
        )

    @property
    def provenance(self) -> JsonObject:
        return {
            **_runtime_contract(),
            "instructions_fingerprint_sha256": _fingerprint(PROVIDER_INSTRUCTIONS),
            "response_schema_fingerprint_sha256": _fingerprint(ApplyRevisionProviderOutput.model_json_schema()),
        }

    def generate(self, payload: Mapping[str, Any]) -> tuple[JsonObject, ProviderReceipt]:
        public_input = json.loads(canonical_json(dict(payload)))
        parsed, receipt = self._parse(
            input_payload=public_input,
            instructions=PROVIDER_INSTRUCTIONS,
            text_format=ApplyRevisionProviderOutput,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )
        _require(isinstance(parsed, ApplyRevisionProviderOutput), "PROVIDER_RUNTIME_OUTPUT_TYPE_INVALID")
        output = parsed.model_dump(mode="json")
        reparsed = ApplyRevisionProviderOutput.model_validate(output).model_dump(mode="json")
        _require(_canonical_bytes(reparsed) == _canonical_bytes(output), "PROVIDER_OUTPUT_ROUNDTRIP_DRIFT")
        return output, receipt


def _failure_record(error: Exception) -> JsonObject:
    return {
        "exception_class": type(error).__name__,
        "reason_code": getattr(error, "reason_code", None),
        "category": getattr(error, "category", None),
        "phase": getattr(error, "phase", None),
    }


def _receipt_dict(value: Any) -> JsonObject:
    if isinstance(value, Mapping):
        return _clone(dict(value))
    if hasattr(value, "to_dict"):
        return _clone(dict(value.to_dict()))
    raise ApplyRevisionError("PROVIDER_RECEIPT_INVALID")


def _validate_receipt(
    receipt: Mapping[str, Any], payload: Mapping[str, Any], *, phase_id: str
) -> None:
    _require(receipt.get("logical_calls") == 1 and receipt.get("api_calls") == 1, "RECEIPT_CALL_COUNT_INVALID", phase_id)
    _require(receipt.get("requested_model") == MODEL, "RECEIPT_MODEL_INVALID", phase_id)
    _require(receipt.get("request_fingerprint") == _fingerprint(payload), "RECEIPT_INPUT_BINDING_INVALID", phase_id)
    _require(receipt.get("prompt_fingerprint") == _fingerprint(PROVIDER_INSTRUCTIONS), "RECEIPT_INSTRUCTIONS_INVALID", phase_id)
    metadata = receipt.get("metadata")
    _require(isinstance(metadata, Mapping), "RECEIPT_METADATA_INVALID")
    _require(
        metadata.get("reasoning_effort") == REASONING_EFFORT
        and metadata.get("max_output_tokens") == MAX_OUTPUT_TOKENS
        and metadata.get("store") is False
        and metadata.get("previous_response_id") is False
        and metadata.get("retry_count") == 0,
        "RECEIPT_RUNTIME_INVALID",
        phase_id,
    )


def _validate_published_receipt(
    receipt: Mapping[str, Any],
    payload: Mapping[str, Any],
    *,
    phase_id: str,
    completed: bool,
    allow_offline_provider: bool,
) -> None:
    _exact_keys(
        receipt,
        {
            "provider",
            "requested_model",
            "returned_model",
            "logical_calls",
            "api_calls",
            "latency_ms",
            "request_fingerprint",
            "prompt_fingerprint",
            "usage",
            "metadata",
        },
        f"receipt.{phase_id}",
    )
    _validate_receipt(receipt, payload, phase_id=phase_id)
    if receipt["provider"] == "offline_scripted":
        _require(allow_offline_provider, "OFFLINE_RECEIPT_NOT_PUBLISHABLE")
        return
    _require(
        receipt["provider"] == "openai_responses",
        "RECEIPT_PROVIDER_INVALID",
        phase_id,
    )
    if completed:
        _require(
            receipt["returned_model"] == MODEL,
            "RECEIPT_RETURNED_MODEL_INVALID",
            phase_id,
        )
    _require(
        isinstance(receipt["latency_ms"], (int, float))
        and not isinstance(receipt["latency_ms"], bool)
        and math.isfinite(float(receipt["latency_ms"]))
        and float(receipt["latency_ms"]) >= 0.0,
        "RECEIPT_LATENCY_INVALID",
    )
    _require(
        receipt["returned_model"] is None
        or (
            isinstance(receipt["returned_model"], str)
            and 0 < len(receipt["returned_model"]) <= 128
        ),
        "RECEIPT_RETURNED_MODEL_SHAPE_INVALID",
    )
    usage = _exact_keys(
        receipt["usage"],
        {
            "exact_provider_tokens",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "cached_input_tokens",
            "cache_write_tokens",
            "reasoning_tokens",
        },
        f"receipt.{phase_id}.usage",
    )
    token_fields = (
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cached_input_tokens",
        "cache_write_tokens",
        "reasoning_tokens",
    )
    _require(
        (usage["exact_provider_tokens"] is True if completed else True)
        and all(
            value is None
            or (isinstance(value, int) and not isinstance(value, bool) and value >= 0)
            for value in (usage[field] for field in token_fields)
        ),
        "RECEIPT_USAGE_INVALID",
        phase_id,
    )
    if completed:
        _require(
            usage["total_tokens"] == usage["input_tokens"] + usage["output_tokens"],
            "RECEIPT_USAGE_TOTAL_INVALID",
            phase_id,
        )
    metadata = _exact_keys(
        receipt["metadata"],
        {
            "receipt_schema_version",
            "status",
            "service_tier",
            "response_id_sha256",
            "server_request_id_sha256",
            "client_request_id_sha256",
            "provider_body_sha256",
            "provider_body_byte_count",
            "http_observed",
            "http_status_code",
            "parse_boundary",
            "failure_phase",
            "failure_reason_code",
            "failure_type",
            "response_schema_fingerprint",
            "semantic_protocol_fingerprint",
            "reasoning_effort",
            "max_output_tokens",
            "store",
            "previous_response_id",
            "truncation",
            "sdk_version",
            "pydantic_version",
            "python_version",
            "attempt",
            "retry_count",
            "api_call_count_semantics",
            "attempt_outcome",
            "refusal_count",
        },
        f"receipt.{phase_id}.metadata",
    )
    expected_protocol = _fingerprint(
        {
            "model": MODEL,
            "instructions_fingerprint": _fingerprint(PROVIDER_INSTRUCTIONS),
            "input_fingerprint": _fingerprint(payload),
            "text_schema_fingerprint": _fingerprint(
                ApplyRevisionProviderOutput.model_json_schema()
            ),
            "reasoning": {"effort": REASONING_EFFORT},
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "store": False,
            "service_tier": "default",
            "truncation": "disabled",
            "timeout_seconds": TIMEOUT_SECONDS,
        }
    )
    _require(
        metadata["receipt_schema_version"]
        == "ebrt-provider-boundary-receipt-v0.4.3"
        and metadata["response_schema_fingerprint"]
        == _fingerprint(ApplyRevisionProviderOutput.model_json_schema())
        and metadata["semantic_protocol_fingerprint"] == expected_protocol
        and metadata["reasoning_effort"] == REASONING_EFFORT
        and metadata["max_output_tokens"] == MAX_OUTPUT_TOKENS
        and metadata["store"] is False
        and metadata["previous_response_id"] is False
        and metadata["truncation"] == "disabled"
        and metadata["sdk_version"] == package_version("openai")
        and metadata["pydantic_version"] == package_version("pydantic")
        and metadata["python_version"] == platform.python_version()
        and metadata["attempt"] == 1
        and metadata["retry_count"] == 0
        and metadata["api_call_count_semantics"] == "attempted_client_call",
        "RECEIPT_METADATA_RUNTIME_INVALID",
        phase_id,
    )
    _require(
        metadata["service_tier"]
        in {None, "auto", "default", "flex", "scale", "priority", "other"},
        "RECEIPT_SERVICE_TIER_INVALID",
        phase_id,
    )
    optional_hash_fields = [
        "server_request_id_sha256",
        "provider_body_sha256",
    ]
    if not completed:
        optional_hash_fields.append("response_id_sha256")
    mandatory_hash_fields = ["client_request_id_sha256"]
    if completed:
        mandatory_hash_fields.append("response_id_sha256")
    _require(
        all(
            metadata[field] is None
            or (
                isinstance(metadata[field], str)
                and len(metadata[field]) == 64
                and all(character in "0123456789abcdef" for character in metadata[field])
            )
            for field in optional_hash_fields
        )
        and all(
            isinstance(metadata[field], str)
            and len(metadata[field]) == 64
            and all(character in "0123456789abcdef" for character in metadata[field])
            for field in mandatory_hash_fields
        )
        and (
            metadata["provider_body_byte_count"] is None
            or (
                isinstance(metadata["provider_body_byte_count"], int)
                and not isinstance(metadata["provider_body_byte_count"], bool)
                and metadata["provider_body_byte_count"] >= 0
            )
        )
        and (
            (metadata["provider_body_sha256"] is None)
            is (metadata["provider_body_byte_count"] is None)
        ),
        "RECEIPT_SANITIZED_DIAGNOSTIC_INVALID",
        phase_id,
    )
    if completed:
        _require(
            metadata["status"] == "completed"
            and metadata["service_tier"] == "default"
            and metadata["http_observed"] is True
            and metadata["http_status_code"] == 200
            and metadata["parse_boundary"] == "succeeded"
            and metadata["failure_phase"] is None
            and metadata["failure_reason_code"] is None
            and metadata["failure_type"] is None
            and metadata["attempt_outcome"] == "completed"
            and metadata["refusal_count"] == 0,
            "COMPLETED_RECEIPT_METADATA_INVALID",
            phase_id,
        )
    else:
        failure_phase = metadata["failure_phase"]
        failure_reason = metadata["failure_reason_code"]
        _require(
            failure_phase in BOUNDARY_PHASES
            and failure_reason in BOUNDARY_REASON_CODES_BY_PHASE[failure_phase]
            and metadata["failure_type"] == failure_reason
            and isinstance(metadata["http_observed"], bool)
            and (
                metadata["http_status_code"] is None
                or (
                    isinstance(metadata["http_status_code"], int)
                    and not isinstance(metadata["http_status_code"], bool)
                    and 100 <= metadata["http_status_code"] <= 599
                )
            )
            and isinstance(metadata["refusal_count"], int)
            and not isinstance(metadata["refusal_count"], bool)
            and metadata["refusal_count"] >= 0,
            "FAILED_RECEIPT_ENUM_INVALID",
            phase_id,
        )
        failure_geometry = {
            "request_call": (
                "transport_error",
                {"no_http_response"},
                "not_entered",
                False,
            ),
            "http_status": (
                "http_status_error",
                {"http_status_error"},
                "not_entered",
                True,
            ),
            "sdk_response_parse": (
                "sdk_parse_error",
                {"http_success_unparsed", "sdk_parse_error"},
                "failed_after_http",
                metadata["status"] == "http_success_unparsed",
            ),
            "provider_contract": (
                "contract_error",
                {
                    "completed",
                    "incomplete",
                    "failed",
                    "cancelled",
                    "queued",
                    "in_progress",
                    "other",
                    "provider_contract_error",
                },
                "succeeded",
                True,
            ),
        }
        expected_outcome, allowed_statuses, expected_parse, expected_http = (
            failure_geometry[failure_phase]
        )
        _require(
            metadata["attempt_outcome"] == expected_outcome
            and metadata["status"] in allowed_statuses
            and metadata["parse_boundary"] == expected_parse
            and metadata["http_observed"] is expected_http,
            "FAILED_RECEIPT_GEOMETRY_INVALID",
            phase_id,
        )
        if failure_phase == "request_call":
            _require(
                metadata["http_status_code"] is None,
                "FAILED_RECEIPT_HTTP_STATUS_INVALID",
                phase_id,
            )
        elif failure_phase == "http_status":
            _require(
                isinstance(metadata["http_status_code"], int)
                and metadata["http_status_code"] >= 400,
                "FAILED_RECEIPT_HTTP_STATUS_INVALID",
                phase_id,
            )
        elif metadata["http_observed"]:
            _require(
                metadata["http_status_code"] == 200,
                "FAILED_RECEIPT_HTTP_STATUS_INVALID",
                phase_id,
            )
        else:
            _require(
                metadata["http_status_code"] is None,
                "FAILED_RECEIPT_HTTP_STATUS_INVALID",
                phase_id,
            )


def _journal_row(kind: str, **fields: Any) -> JsonObject:
    return _seal({"schema_version": JOURNAL_SCHEMA, "kind": kind, **fields})


def _append_journal(path: Path, row: Mapping[str, Any]) -> None:
    with path.open("ab") as handle:
        handle.write(_canonical_bytes(row, trailing_newline=True))
        handle.flush()
        os.fsync(handle.fileno())


def _provider_receipts(provider: Any) -> list[JsonObject]:
    return json.loads(canonical_json(getattr(provider, "audit_receipts", [])))


def execute_gold_free(
    fixture: Mapping[str, Any],
    provider: Any,
    *,
    journal_path: Path,
    dynamic_payload_path: Path,
) -> JsonObject:
    _require(journal_path != dynamic_payload_path, "DURABLE_PATH_ALIAS_INVALID")
    executions: dict[str, JsonObject] = {}
    payloads: dict[str, JsonObject] = {}
    before_payload = build_provider_payload(fixture, "before_event")
    payloads["before_event"] = before_payload
    _append_journal(
        journal_path,
        _journal_row(
            "ATTEMPT_STARTED",
            phase_id="before_event",
            run_position=0,
            provider_input_fingerprint_sha256=_fingerprint(before_payload),
        ),
    )
    before_receipt_count = len(_provider_receipts(provider))
    before_output: JsonObject | None = None
    try:
        raw_output, raw_receipt = provider.generate(before_payload)
        before_output = _clone(raw_output)
        receipt = _receipt_dict(raw_receipt)
        observed = _provider_receipts(provider)[before_receipt_count:]
        _require(len(observed) == 1 and observed[0] == receipt, "PROVIDER_RECEIPT_COUNT_DRIFT")
        _validate_receipt(receipt, before_payload, phase_id="before_event")
        compiled_before = _compile_candidate_output(fixture, "before_event", before_output)
        executions["before_event"] = {
            "phase_id": "before_event",
            "run_position": 0,
            "status": "completed",
            "provider_input_fingerprint_sha256": _fingerprint(before_payload),
            "public_output": before_output,
            "compiled_output": compiled_before,
            "receipt": receipt,
            "failure": None,
        }
    except Exception as error:
        observed = _provider_receipts(provider)[before_receipt_count:]
        _require(len(observed) == 1, "PROVIDER_RECEIPT_COUNT_DRIFT")
        receipt = observed[0]
        executions["before_event"] = {
            "phase_id": "before_event",
            "run_position": 0,
            "status": "failed",
            "provider_input_fingerprint_sha256": _fingerprint(before_payload),
            "public_output": None,
            "rejected_public_output": before_output,
            "compiled_output": None,
            "receipt": receipt,
            "failure": _failure_record(error),
        }
        _append_journal(
            journal_path,
            _journal_row(
                "ATTEMPT_TERMINAL",
                phase_id="before_event",
                run_position=0,
                status="failed",
                provider_input_fingerprint_sha256=_fingerprint(before_payload),
                public_output_fingerprint_sha256=None,
            ),
        )
        return {
            "phase_order": list(PHASES),
            "executions": executions,
            "provider_payloads": payloads,
            "control_map": None,
            "compiled_actuator": None,
            "two_structurally_valid_terminals": False,
            "gold_loaded": False,
        }

    compiled_before = executions["before_event"]["compiled_output"]
    _append_journal(
        journal_path,
        _journal_row(
            "ATTEMPT_TERMINAL",
            phase_id="before_event",
            run_position=0,
            status="completed",
            provider_input_fingerprint_sha256=_fingerprint(before_payload),
            public_output_fingerprint_sha256=_fingerprint(before_output),
            compiled_output_fingerprint_sha256=compiled_before["fingerprint_sha256"],
        ),
    )

    # No semantic branch occurs here.  Every structurally valid Before reaches
    # the same deterministic controller and one dependent After attempt.
    _append_journal(
        journal_path,
        _journal_row(
            "REVISION_STARTED",
            source_before_public_output_fingerprint_sha256=_fingerprint(before_output),
            source_before_compiled_fingerprint_sha256=compiled_before["fingerprint_sha256"],
            gold_loaded=False,
        ),
    )
    control_map = derive_public_control_map(fixture, compiled_before)
    actuator = compile_actuator(fixture, compiled_before, control_map)
    after_payload = build_provider_payload(
        fixture,
        "after_event",
        compiled_before=compiled_before,
        actuator=actuator,
    )
    payloads["after_event"] = after_payload
    _require(not dynamic_payload_path.exists(), "DYNAMIC_PAYLOAD_PATH_ALREADY_EXISTS")
    dynamic_payload_path.parent.mkdir(parents=True, exist_ok=True)
    with dynamic_payload_path.open("xb") as handle:
        handle.write(_canonical_bytes(after_payload))
        handle.flush()
        os.fsync(handle.fileno())
    directory_fd = os.open(dynamic_payload_path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    _require(
        dynamic_payload_path.read_bytes() == _canonical_bytes(after_payload),
        "DYNAMIC_PAYLOAD_DURABILITY_DRIFT",
    )
    _append_journal(
        journal_path,
        _journal_row(
            "REVISION_COMPILED",
            source_before_public_output_fingerprint_sha256=_fingerprint(before_output),
            source_before_compiled_fingerprint_sha256=compiled_before["fingerprint_sha256"],
            controller_input_fingerprint_sha256=control_map["actual_before_state"]["fingerprint_sha256"],
            autograd_audit_fingerprint_sha256=control_map["source_credit_basis"]["source_adjoint_fingerprint_sha256"],
            control_map_fingerprint_sha256=control_map["fingerprint_sha256"],
            compiled_actuator_fingerprint_sha256=actuator["fingerprint_sha256"],
            after_provider_input_fingerprint_sha256=_fingerprint(after_payload),
            gold_loaded=False,
        ),
    )
    _append_journal(
        journal_path,
        _journal_row(
            "ATTEMPT_STARTED",
            phase_id="after_event",
            run_position=1,
            provider_input_fingerprint_sha256=_fingerprint(after_payload),
        ),
    )
    after_receipt_count = len(_provider_receipts(provider))
    after_output: JsonObject | None = None
    try:
        raw_output, raw_receipt = provider.generate(after_payload)
        after_output = _clone(raw_output)
        receipt = _receipt_dict(raw_receipt)
        observed = _provider_receipts(provider)[after_receipt_count:]
        _require(len(observed) == 1 and observed[0] == receipt, "PROVIDER_RECEIPT_COUNT_DRIFT")
        _validate_receipt(receipt, after_payload, phase_id="after_event")
        compiled_after = _compile_candidate_output(fixture, "after_event", after_output)
        executions["after_event"] = {
            "phase_id": "after_event",
            "run_position": 1,
            "status": "completed",
            "provider_input_fingerprint_sha256": _fingerprint(after_payload),
            "public_output": after_output,
            "compiled_output": compiled_after,
            "receipt": receipt,
            "failure": None,
        }
        status = "completed"
    except Exception as error:
        observed = _provider_receipts(provider)[after_receipt_count:]
        _require(len(observed) == 1, "PROVIDER_RECEIPT_COUNT_DRIFT")
        executions["after_event"] = {
            "phase_id": "after_event",
            "run_position": 1,
            "status": "failed",
            "provider_input_fingerprint_sha256": _fingerprint(after_payload),
            "public_output": None,
            "rejected_public_output": after_output,
            "compiled_output": None,
            "receipt": observed[0],
            "failure": _failure_record(error),
        }
        status = "failed"
    _append_journal(
        journal_path,
        _journal_row(
            "ATTEMPT_TERMINAL",
            phase_id="after_event",
            run_position=1,
            status=status,
            provider_input_fingerprint_sha256=_fingerprint(after_payload),
            public_output_fingerprint_sha256=(None if after_output is None else _fingerprint(after_output)),
            compiled_output_fingerprint_sha256=(
                executions["after_event"]["compiled_output"]["fingerprint_sha256"]
                if status == "completed"
                else None
            ),
        ),
    )
    complete = status == "completed"
    return {
        "phase_order": list(PHASES),
        "executions": executions,
        "provider_payloads": payloads,
        "control_map": control_map,
        "compiled_actuator": actuator,
        "two_structurally_valid_terminals": complete,
        "gold_loaded": False,
    }


def validate_gold(gold: Mapping[str, Any], fixture: Mapping[str, Any]) -> None:
    _exact_keys(
        gold,
        {
            "schema_version",
            "status",
            "case_id",
            "source_fixture",
            "closure_roles",
            "before_event",
            "after_event",
            "stale_expectation",
            "expected_public_diff",
            "acceptance_contract",
            "target_provenance",
            "claim_boundary",
            "fingerprint_sha256",
        },
        "gold",
    )
    _validate_seal(gold, "gold")
    _require(gold["schema_version"] == GOLD_SCHEMA, "GOLD_SCHEMA_DRIFT")
    _require(gold["status"] == "LOCKED_POST_TWO_CALL_GRADING_ONLY", "GOLD_STATUS_DRIFT")
    _require(gold["case_id"] == fixture["case"]["case_id"], "GOLD_CASE_DRIFT")
    _require(
        gold["source_fixture"]["fingerprint_sha256"] == fixture["fingerprint_sha256"],
        "GOLD_FIXTURE_BINDING_DRIFT",
    )
    candidate_ids = {
        row["closure_id"]
        for phase_id in PHASES
        for row in fixture["closure_catalogs"][phase_id]
    }
    _require(set(gold["closure_roles"]) == candidate_ids, "GOLD_CLOSURE_ROLE_SET_DRIFT")
    for phase_id in PHASES:
        expected = gold[phase_id]
        _require(expected["selected_closure_id"] in _catalog_map(fixture, phase_id), "GOLD_CLOSURE_UNKNOWN")
        fake = {
            "schema_version": OUTPUT_SCHEMA,
            "checkpoint_id": expected["checkpoint_id"],
            "current_answer": expected["answer"],
            "selected_closure_id": expected["selected_closure_id"],
            "target_values": [
                {
                    "target_id": row["target_id"],
                    "target_type": row["target_type"],
                    "slot": row["slot"],
                    "value": row["value"],
                }
                for row in expected["targets"]
            ],
        }
        compiled = _compile_candidate_output(fixture, phase_id, fake)
        _require(_grade(compiled, expected)["status"] == "PASS", "GOLD_DOES_NOT_SELF_GRADE", phase_id)
    acceptance = gold["acceptance_contract"]
    order_contract = acceptance["catalog_order_contract"]
    _require(
        order_contract["algorithm_source"]
        == "fixture.execution_contract.closure_catalog_ordering"
        and order_contract["must_be_distinct"] is True
        and order_contract["selected_ordinals_zero_based"]
        == {"before_event": 1, "after_event": 2},
        "GOLD_CATALOG_ORDER_CONTRACT_DRIFT",
    )
    selected_ids = []
    for phase_id in PHASES:
        rows = fixture["closure_catalogs"][phase_id]
        ordinal = order_contract["selected_ordinals_zero_based"][phase_id]
        _require(
            rows[ordinal]["closure_id"] == gold[phase_id]["selected_closure_id"],
            "GOLD_SELECTED_CATALOG_ORDINAL_DRIFT",
            phase_id,
        )
        selected_ids.append(rows[ordinal]["closure_id"])
    _require(len(set(selected_ids)) == 2, "GOLD_SELECTED_CLOSURES_NOT_DISTINCT")
    _require(acceptance["effect_attribution_status"] == "NOT_ASSESSED", "GOLD_EFFECT_STATUS_DRIFT")


def _load_gold(fixture: Mapping[str, Any]) -> JsonObject:
    gold = _strict_load(GOLD_PATH)
    validate_gold(gold, fixture)
    return gold


def _grade(compiled: Mapping[str, Any], expected: Mapping[str, Any]) -> JsonObject:
    observed_targets = {row["target_id"]: row for row in compiled["targets"]}
    expected_targets = {row["target_id"]: row for row in expected["targets"]}
    target_results = []
    for target_id in sorted(expected_targets):
        wanted = expected_targets[target_id]
        observed = observed_targets.get(target_id)
        checks = {
            "metadata_exact": bool(
                observed
                and (observed["target_type"], observed["slot"], observed["value"])
                == (wanted["target_type"], wanted["slot"], wanted["value"])
            ),
            "direct_exact": bool(observed and observed["direct_active_evidence_ids"] == wanted["direct_active_evidence_ids"]),
            "inherited_exact": bool(observed and observed["inherited_active_evidence_ids"] == wanted["inherited_active_evidence_ids"]),
            "total_exact": bool(observed and observed["all_active_evidence_ids"] == wanted["all_active_evidence_ids"]),
        }
        target_results.append(
            {
                "target_id": target_id,
                "status": "PASS" if all(checks.values()) else "FAIL",
                "checks": checks,
            }
        )
    answer_pass = compiled["current_answer"] == expected["answer"]
    closure_pass = compiled["selected_closure_id"] == expected["selected_closure_id"]
    invalidation_pass = compiled["invalidation_edges"] == expected["invalidation_edges"]
    fact_pass = all(row["status"] == "PASS" for row in target_results if row["target_id"].startswith("fact:"))
    stable_pass = all(row["status"] == "PASS" for row in target_results if row["target_id"].startswith("constraint:"))
    statuses = {
        "answer_status": "PASS" if answer_pass else "FAIL",
        "closure_selection_status": "PASS" if closure_pass else "FAIL",
        "fact_local_lineage_status": "PASS" if fact_pass else "FAIL",
        "invalidation_status": "PASS" if invalidation_pass else "FAIL",
        "stable_fact_status": "PASS" if stable_pass else "FAIL",
    }
    return _seal(
        {
            "schema_version": "ebrt-apply-revision-grade-v0.6.2.1",
            "status": "PASS" if all(value == "PASS" for value in statuses.values()) else "FAIL",
            **statuses,
            "target_results": target_results,
            "compiled_fingerprint_sha256": compiled["fingerprint_sha256"],
        }
    )


def _stale_grade(compiled_before: Mapping[str, Any], gold: Mapping[str, Any]) -> JsonObject:
    pre_grade = _grade(compiled_before, gold["before_event"])
    post_grade = _grade(compiled_before, gold["after_event"])
    failed_axes = sorted(
        axis
        for axis in ("answer_status", "fact_local_lineage_status", "invalidation_status", "stable_fact_status")
        if post_grade[axis] == "FAIL"
    )
    expected = gold["stale_expectation"]
    checks = {
        "before_own_horizon_pass": pre_grade["status"] == "PASS",
        "same_before_compiled_bytes_used": post_grade["compiled_fingerprint_sha256"] == compiled_before["fingerprint_sha256"],
        "post_event_status_fail": post_grade["status"] == expected["post_event_status"],
        "failed_axes_exact": failed_axes == expected["failed_axes"],
        "stable_axis_pass": post_grade[expected["stable_axis"]] == expected["stable_axis_status"],
    }
    return _seal(
        {
            "schema_version": "ebrt-apply-revision-stale-regrade-v0.6.2.1",
            "status": "PASS" if all(checks.values()) else "FAIL",
            "checks": checks,
            "failed_axes": failed_axes,
            "pre_grade": pre_grade,
            "post_grade": post_grade,
        }
    )


def _public_diff(before: Mapping[str, Any], after: Mapping[str, Any]) -> JsonObject:
    before_targets = {row["target_id"]: row for row in before["targets"]}
    after_targets = {row["target_id"]: row for row in after["targets"]}
    before_support = set(before["active_support_evidence_ids"])
    after_support = set(after["active_support_evidence_ids"])
    before_invalidations = {
        (row["source_evidence_id"], row["target_evidence_id"])
        for row in before["invalidation_edges"]
    }
    after_invalidations = {
        (row["source_evidence_id"], row["target_evidence_id"])
        for row in after["invalidation_edges"]
    }
    return _seal(
        {
            "schema_version": "ebrt-apply-revision-public-diff-v0.6.2.1",
            "answer": {"before": before["current_answer"], "after": after["current_answer"]},
            "selected_closure_id": {"before": before["selected_closure_id"], "after": after["selected_closure_id"]},
            "target_values": [
                {
                    "target_id": target_id,
                    "slot": before_targets[target_id]["slot"],
                    "before": before_targets[target_id]["value"],
                    "after": after_targets[target_id]["value"],
                    "changed": before_targets[target_id]["value"] != after_targets[target_id]["value"],
                }
                for target_id in sorted(before_targets)
            ],
            "support_added_evidence_ids": sorted(after_support - before_support),
            "support_dropped_evidence_ids": sorted(before_support - after_support),
            "invalidation_added_edges": [
                {"source_evidence_id": source, "target_evidence_id": target}
                for source, target in sorted(after_invalidations - before_invalidations)
            ],
            "stable_target_ids": [
                target_id
                for target_id in sorted(before_targets)
                if target_id.startswith("constraint:")
                and before_targets[target_id]["value"] == after_targets[target_id]["value"]
                and before_targets[target_id]["all_active_evidence_ids"] == after_targets[target_id]["all_active_evidence_ids"]
            ],
        }
    )


def _diff_matches_gold(diff: Mapping[str, Any], gold: Mapping[str, Any]) -> bool:
    observed = _without_fingerprint(diff)
    observed.pop("schema_version")
    return _canonical_bytes(observed) == _canonical_bytes(gold["expected_public_diff"])


def _usage_summary(executions: Mapping[str, Mapping[str, Any]]) -> JsonObject:
    receipts = [row["receipt"] for row in executions.values() if row.get("receipt")]
    usage_rows = [row.get("usage", {}) for row in receipts]
    return {
        "logical_calls": sum(int(row.get("logical_calls", 0)) for row in receipts),
        "api_calls": sum(int(row.get("api_calls", 0)) for row in receipts),
        "input_tokens": sum(int(row.get("input_tokens", 0) or 0) for row in usage_rows),
        "output_tokens": sum(int(row.get("output_tokens", 0) or 0) for row in usage_rows),
        "reasoning_tokens": sum(int(row.get("reasoning_tokens", 0) or 0) for row in usage_rows),
        "total_tokens": sum(int(row.get("total_tokens", 0) or 0) for row in usage_rows),
        "latency_ms": math.fsum(float(row.get("latency_ms", 0.0)) for row in receipts),
    }


def finalize_result(
    fixture: Mapping[str, Any], execution: Mapping[str, Any], gold: Mapping[str, Any] | None
) -> JsonObject:
    complete = bool(execution["two_structurally_valid_terminals"])
    _require((gold is not None) == complete, "GOLD_COMPLETENESS_BOUNDARY_INVALID")
    executions = _clone(execution["executions"])
    if not complete:
        return _seal(
            {
                "schema_version": RESULT_SCHEMA,
                "status": "INCOMPLETE_NOT_ASSESSED",
                "case_id": fixture["case"]["case_id"],
                "phase_order": list(PHASES),
                "executions": executions,
                "revision_engine": {
                    "control_map": _clone(execution["control_map"]),
                    "compiled_actuator": _clone(execution["compiled_actuator"]),
                },
                "grades": None,
                "output_diff": None,
                "checks": None,
                "semantic_gold": {
                    "loaded": False,
                    "load_count": 0,
                    "reason": "DENIED_UNTIL_TWO_STRUCTURALLY_VALID_TERMINALS",
                    "fingerprint_sha256": None,
                },
                "decision": {
                    "run_status": "INCOMPLETE_NOT_ASSESSED",
                    "mechanism_status": "NOT_ASSESSED",
                    "before_status": "NOT_ASSESSED",
                    "after_status": "NOT_ASSESSED",
                    "diff_status": "NOT_ASSESSED",
                    "product_acceptance_status": "NOT_ASSESSED",
                    "effect_attribution_status": "NOT_ASSESSED",
                    "terminal_decision": "INCOMPLETE_NOT_ASSESSED",
                },
                "accounting": _usage_summary(executions),
                "claim_boundary": list(CLAIM_BOUNDARY),
            }
        )
    assert gold is not None
    before = executions["before_event"]["compiled_output"]
    after = executions["after_event"]["compiled_output"]
    before_grade = _grade(before, gold["before_event"])
    stale = _stale_grade(before, gold)
    after_grade = _grade(after, gold["after_event"])
    diff = _public_diff(before, after)
    control = execution["control_map"]
    actuator = execution["compiled_actuator"]
    mechanism_checks = {
        **control["checks"],
        "actuator_compiled_deterministically": actuator["source_control_map_fingerprint_sha256"] == control["fingerprint_sha256"],
        "after_payload_sealed_after_before_terminal": execution["provider_payloads"]["after_event"]["apply_revision"]["source_actuator_fingerprint_sha256"] == actuator["fingerprint_sha256"],
    }
    product_checks = {
        "exactly_two_structurally_valid_terminals": complete and len(executions) == 2,
        "before_own_horizon_strict_pass": before_grade["status"] == "PASS",
        "same_before_post_event_stale_signature_exact": stale["status"] == "PASS",
        "after_post_event_strict_pass": after_grade["status"] == "PASS",
        "expected_public_diff_exact": _diff_matches_gold(diff, gold),
        "invalidated_support_absent": not bool(set(after["active_support_evidence_ids"]) & set(after["invalidated_evidence_ids"])),
        "stable_target_preserved": "constraint:video_constraint" in diff["stable_target_ids"],
        "surrogate_control_output_grade_separated": True,
    }
    mechanism_pass = all(mechanism_checks.values())
    product_pass = all(product_checks.values()) and mechanism_pass
    terminal = (
        gold["acceptance_contract"]["pass_terminal_decision"]
        if product_pass
        else gold["acceptance_contract"]["fail_terminal_decision"]
    )
    return _seal(
        {
            "schema_version": RESULT_SCHEMA,
            "status": "COMPLETE_EXACT_TWO_TERMINALS",
            "case_id": fixture["case"]["case_id"],
            "phase_order": list(PHASES),
            "executions": executions,
            "revision_engine": {"control_map": control, "compiled_actuator": actuator},
            "grades": {"before": before_grade, "before_post_event_stale": stale, "after": after_grade},
            "output_diff": diff,
            "checks": {"mechanism": mechanism_checks, "product": product_checks},
            "semantic_gold": {
                "loaded": True,
                "load_count": 1,
                "reason": "TWO_STRUCTURALLY_VALID_TERMINALS_EXIST",
                "fingerprint_sha256": gold["fingerprint_sha256"],
            },
            "decision": {
                "run_status": "COMPLETE_EXACT_TWO_TERMINALS",
                "mechanism_status": "PASS" if mechanism_pass else "FAIL",
                "before_status": "PASS_THEN_STALE" if before_grade["status"] == stale["status"] == "PASS" else "FAIL",
                "after_status": "PASS_STRICT_POST_EVENT" if after_grade["status"] == "PASS" else "FAIL",
                "diff_status": "OBSERVED_EXPECTED_PUBLIC_DIFF" if product_checks["expected_public_diff_exact"] else "DIFF_MISMATCH",
                "product_acceptance_status": "PASS" if product_pass else "FAIL",
                "effect_attribution_status": "NOT_ASSESSED",
                "terminal_decision": terminal,
            },
            "accounting": _usage_summary(executions),
            "claim_boundary": list(CLAIM_BOUNDARY),
        }
    )


@contextmanager
def _network_denied() -> Iterator[dict[str, int]]:
    counts = {"network_calls": 0}

    def denied(*_args: Any, **_kwargs: Any) -> None:
        counts["network_calls"] += 1
        raise AssertionError("network forbidden during Apply Revision offline validation")

    with (
        mock.patch.object(socket, "getaddrinfo", side_effect=denied),
        mock.patch.object(socket, "create_connection", side_effect=denied),
        mock.patch.object(socket.socket, "connect", side_effect=denied),
        mock.patch.object(socket.socket, "connect_ex", side_effect=denied),
    ):
        yield counts


@contextmanager
def _semantic_gold_denied() -> Iterator[dict[str, int]]:
    """Deny semantic parsing while either provider call can still occur.

    The lock and live source guard are allowed to hash the opaque gold bytes.
    Only ``_strict_load(GOLD_PATH)`` crosses the semantic boundary.
    """

    counts = {"attempted_gold_accesses": 0}
    original = _strict_load
    gold_path = GOLD_PATH.resolve()

    def guarded(path: Path) -> JsonObject:
        if path.resolve() == gold_path:
            counts["attempted_gold_accesses"] += 1
            raise ApplyRevisionError("SEMANTIC_GOLD_ACCESSED_BEFORE_TWO_TERMINALS")
        return original(path)

    with mock.patch.object(sys.modules[__name__], "_strict_load", guarded):
        yield counts


def policy_lock_material() -> JsonObject:
    fixture = load_fixture()
    before_payload = build_provider_payload(fixture, "before_event")
    sources = {
        label: _file_receipt(ROOT / relative_path)
        for label, relative_path in LOCKED_SOURCE_PATHS.items()
    }
    return _seal(
        {
            "schema_version": LOCK_SCHEMA,
            "status": "PREREGISTERED_DYNAMIC_EXACT_TWO_CALL_PRODUCT_ACCEPTANCE",
            "sources": sources,
            "runtime": _runtime_contract(),
            "fixture_fingerprint_sha256": fixture["fingerprint_sha256"],
            "semantic_gold_bytes_sha256": sources["post_call_semantic_gold"]["sha256"],
            "provider": {
                "instructions_fingerprint_sha256": _fingerprint(PROVIDER_INSTRUCTIONS),
                "response_schema_fingerprint_sha256": _fingerprint(
                    ApplyRevisionProviderOutput.model_json_schema()
                ),
                "before_payload_fingerprint_sha256": _fingerprint(before_payload),
                "after_payload_fingerprint_sha256": None,
                "after_payload_is_dynamic": True,
            },
            "execution": {
                "authorization_tag": AUTHORIZATION_TAG,
                "phase_order": list(PHASES),
                "exact_provider_attempts": 2,
                "one_attempt_per_phase": True,
                "no_retry": True,
                "no_resume": True,
                "no_backfill": True,
                "no_third_call": True,
                "structurally_valid_before_always_continues": True,
                "after_payload_materialized_only_after_before_terminal": True,
                "semantic_gold_loaded_only_after_two_structurally_valid_terminals": True,
                "effect_attribution_status": "NOT_ASSESSED",
            },
            "artifact": {
                "default_directory": str(DEFAULT_OUTPUT.relative_to(ROOT)),
                "files": list(ARTIFACT_FILES),
            },
            "claim_boundary": list(CLAIM_BOUNDARY),
        }
    )


def _load_lock() -> JsonObject:
    _require(LOCK_PATH.is_file() and not LOCK_PATH.is_symlink(), "POLICY_LOCK_UNAVAILABLE")
    lock = _strict_load(LOCK_PATH)
    _validate_seal(lock, "policy_lock")
    _require(lock == policy_lock_material(), "POLICY_LOCK_OR_SOURCE_BYTES_DRIFT")
    return lock


def _git_text(*args: str, check: bool = True) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=check,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ApplyRevisionError("GIT_BOUNDARY_UNAVAILABLE") from error
    return completed.stdout.strip()


def _tag_exists(tag: str) -> bool:
    try:
        completed = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/tags/{tag}"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ApplyRevisionError("GIT_BOUNDARY_UNAVAILABLE") from error
    _require(completed.returncode in (0, 1), "GIT_TAG_PROBE_FAILED")
    return completed.returncode == 0


def _observe_authorization(*, allow_pending: bool) -> JsonObject:
    _require(Path(_git_text("rev-parse", "--show-toplevel")).resolve() == ROOT, "GIT_ROOT_DRIFT")
    if not _tag_exists(AUTHORIZATION_TAG):
        if allow_pending:
            return {"status": "PENDING_ANNOTATED_TAG", "tag_name": AUTHORIZATION_TAG}
        raise ApplyRevisionError("EXECUTION_AUTHORIZATION_TAG_UNAVAILABLE")
    tag_object = _git_text("rev-parse", "--verify", f"refs/tags/{AUTHORIZATION_TAG}")
    _require(_git_text("cat-file", "-t", tag_object) == "tag", "AUTHORIZATION_TAG_NOT_ANNOTATED")
    commit = _git_text("rev-parse", f"refs/tags/{AUTHORIZATION_TAG}^{{commit}}")
    head = _git_text("rev-parse", "HEAD")
    _require(commit == head, "AUTHORIZED_COMMIT_NOT_HEAD")
    _git_text("merge-base", "--is-ancestor", commit, "refs/remotes/origin/main")
    locked = [str(path) for path in LOCKED_SOURCE_PATHS.values()] + [str(LOCK_PATH.relative_to(ROOT))]
    _git_text("ls-files", "--error-unmatch", "--", *locked)
    _git_text("diff", "--quiet", commit, "--", *locked)
    return {
        "status": "AUTHORIZED_ANNOTATED_TAG",
        "tag_name": AUTHORIZATION_TAG,
        "tag_object": tag_object,
        "authorized_commit": commit,
        "execution_head_commit": head,
        "head_matches_authorized_commit": True,
        "provenance_scope": "OPERATOR_ATTESTED_NOT_CRYPTOGRAPHICALLY_AUTHENTICATED",
    }


def preflight(*, require_api_key: bool = False, require_authorization: bool = False) -> JsonObject:
    with _network_denied() as network:
        fixture = load_fixture()
        before_payload = build_provider_payload(fixture, "before_event")
        _, credit_receipt = _historical_credit_basis()
    _require(network["network_calls"] == 0, "PREFLIGHT_NETWORK_USED")
    calculated_lock = policy_lock_material()
    lock_status = "PENDING_LOCK_FILE"
    if LOCK_PATH.exists():
        lock = _load_lock()
        _require(lock == calculated_lock, "PREFLIGHT_LOCK_DRIFT")
        lock_status = "LOCKED"
    elif require_authorization:
        raise ApplyRevisionError("POLICY_LOCK_UNAVAILABLE")
    authorization = _observe_authorization(allow_pending=not require_authorization)
    if require_api_key:
        _require(bool(os.environ.get("OPENAI_API_KEY")), "OPENAI_API_KEY_UNAVAILABLE")
    checks = {
        "fixture_valid": True,
        "role_blind_catalog_order_valid": True,
        "before_payload_static_and_gold_free": True,
        "v054_credit_basis_recomputed": True,
        "network_calls": network["network_calls"],
        "policy_lock_status": lock_status,
        "authorization_status": authorization["status"],
        "api_key_required": require_api_key,
        "api_key_available": bool(os.environ.get("OPENAI_API_KEY")),
    }
    return _seal(
        {
            "schema_version": "ebrt-apply-revision-preflight-v0.6.2.1-r01",
            "status": (
                "PASS"
                if lock_status == "LOCKED" and authorization["status"] == "AUTHORIZED_ANNOTATED_TAG"
                else "READY_EXCEPT_PENDING_LOCK_OR_AUTHORIZATION"
            ),
            "checks": checks,
            "fixture_fingerprint_sha256": fixture["fingerprint_sha256"],
            "calculated_policy_lock_fingerprint_sha256": calculated_lock["fingerprint_sha256"],
            "before_payload_fingerprint_sha256": _fingerprint(before_payload),
            "credit_basis_fingerprint_sha256": credit_receipt["fingerprint_sha256"],
            "execution_authorization": authorization,
            "effect_attribution_status": "NOT_ASSESSED",
        }
    )


def _calls_bytes(execution: Mapping[str, Any]) -> bytes:
    rows = []
    for phase_id in PHASES:
        if phase_id not in execution["executions"]:
            continue
        row = execution["executions"][phase_id]
        rows.append(
            _seal(
                {
                    "schema_version": CALL_SCHEMA,
                    "phase_id": phase_id,
                    "run_position": row["run_position"],
                    "status": row["status"],
                    "provider_input_fingerprint_sha256": row[
                        "provider_input_fingerprint_sha256"
                    ],
                    "public_output_fingerprint_sha256": (
                        None if row.get("public_output") is None else _fingerprint(row["public_output"])
                    ),
                    "compiled_output_fingerprint_sha256": (
                        None
                        if row.get("compiled_output") is None
                        else row["compiled_output"]["fingerprint_sha256"]
                    ),
                    "failure": _clone(row.get("failure")),
                    "receipt": _clone(row.get("receipt")),
                }
            )
        )
    return b"".join(_canonical_bytes(row, trailing_newline=True) for row in rows)


def _provider_inputs_artifact(execution: Mapping[str, Any]) -> JsonObject:
    return _seal(
        {
            "schema_version": PROVIDER_INPUTS_SCHEMA,
            "phase_order": list(execution["provider_payloads"]),
            "payloads": [
                {
                    "phase_id": phase_id,
                    "payload_fingerprint_sha256": _fingerprint(payload),
                    "payload": _clone(payload),
                }
                for phase_id, payload in execution["provider_payloads"].items()
            ],
            "after_payload_was_dynamic": "after_event" in execution["provider_payloads"],
            "semantic_gold_provider_visible": False,
        }
    )


def _trace_artifact(execution: Mapping[str, Any]) -> JsonObject:
    return _seal(
        {
            "schema_version": TRACE_SCHEMA,
            "actual_before_compiled_fingerprint_sha256": (
                execution["executions"].get("before_event", {}).get("compiled_output") or {}
            ).get("fingerprint_sha256"),
            "control_map": _clone(execution["control_map"]),
            "compiled_actuator": _clone(execution["compiled_actuator"]),
            "effect_attribution_status": "NOT_ASSESSED",
            "gradient_boundary": "local public surrogate to public control map only",
        }
    )


def _report(result: Mapping[str, Any]) -> str:
    decision = result["decision"]
    lines = [
        "# EBRT v0.6.2.1 — Apply Revision Acceptance",
        "",
        f"- Run: `{decision['run_status']}`",
        f"- Mechanism: `{decision['mechanism_status']}`",
        f"- Before: `{decision['before_status']}`",
        f"- After: `{decision['after_status']}`",
        f"- Public diff: `{decision['diff_status']}`",
        f"- Product acceptance: `{decision['product_acceptance_status']}`",
        f"- Effect attribution: `{decision['effect_attribution_status']}`",
        f"- Provider calls: `{result['accounting']['api_calls']}/2`",
        f"- Semantic gold loaded: `{str(result['semantic_gold']['loaded']).lower()}`",
        "",
        "## Apply Revision",
        "",
    ]
    actuator = result["revision_engine"].get("compiled_actuator")
    if actuator:
        lines.extend(
            [
                f"- Reinspect: `{' → '.join(actuator['reinspect_evidence_ids'])}`",
                f"- Suppress: `{', '.join(actuator['suppress_evidence_ids'])}`",
                f"- Preserve: `{', '.join(actuator['preserve_evidence_ids'])}`",
            ]
        )
    lines.extend(["", "## Claim boundary", "", *[f"- {item}" for item in CLAIM_BOUNDARY], ""])
    return "\n".join(lines)


def _manifest_value(
    files: Mapping[str, bytes], result: Mapping[str, Any], lock: Mapping[str, Any]
) -> JsonObject:
    return _seal(
        {
            "schema_version": MANIFEST_SCHEMA,
            "status": "SEALED_APPLY_REVISION_RESULT",
            "result_fingerprint_sha256": result["fingerprint_sha256"],
            "policy_lock_fingerprint_sha256": lock["fingerprint_sha256"],
            "artifacts": {
                name: {"bytes": len(raw), "sha256": _sha256_bytes(raw)}
                for name, raw in files.items()
            },
            "effect_attribution_status": "NOT_ASSESSED",
            "claim_boundary": list(CLAIM_BOUNDARY),
        }
    )


def _materialize_files(
    result: Mapping[str, Any],
    execution: Mapping[str, Any],
    *,
    lock: Mapping[str, Any],
    journal_bytes: bytes,
) -> dict[str, bytes]:
    files = {
        "result.json": _pretty_bytes(result),
        "calls.jsonl": _calls_bytes(execution),
        "attempt_journal.jsonl": journal_bytes,
        "provider_inputs.json": _pretty_bytes(_provider_inputs_artifact(execution)),
        "apply_revision_trace.json": _pretty_bytes(_trace_artifact(execution)),
        "report.md": _report(result).encode("utf-8"),
    }
    files["manifest.json"] = _pretty_bytes(_manifest_value(files, result, lock))
    _require(set(files) == set(ARTIFACT_FILES), "ARTIFACT_FILE_SET_INTERNAL_DRIFT")
    return files


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _publish(output: Path, files: Mapping[str, bytes]) -> None:
    _require(not output.exists() and not output.is_symlink(), "OUTPUT_ALREADY_EXISTS")
    _require(not output.parent.is_symlink(), "OUTPUT_PARENT_SYMLINK")
    _require(set(files) == set(ARTIFACT_FILES), "ARTIFACT_FILE_SET_DRIFT")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.publish.", dir=output.parent))
    try:
        for name in ARTIFACT_FILES:
            path = temporary / name
            path.write_bytes(files[name])
            with path.open("rb") as handle:
                os.fsync(handle.fileno())
        _fsync_directory(temporary)
        os.replace(temporary, output)
        _fsync_directory(output.parent)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _strict_jsonl(raw: bytes, *, label: str) -> list[JsonObject]:
    rows = []
    for index, line in enumerate(raw.splitlines(), start=1):
        value = _strict_json_bytes(line, label=f"{label}:{index}")
        _require(isinstance(value, dict), "JSONL_ROW_NOT_OBJECT", label)
        rows.append(value)
    return rows


def _read_bundle(output: Path) -> dict[str, bytes]:
    _require(output.is_dir() and not output.is_symlink(), "ARTIFACT_DIRECTORY_UNAVAILABLE")
    entries = list(output.iterdir())
    _require(
        len(entries) == len(ARTIFACT_FILES)
        and all(path.is_file() and not path.is_symlink() for path in entries)
        and {path.name for path in entries} == set(ARTIFACT_FILES),
        "ARTIFACT_DIRECTORY_NONCANONICAL",
    )
    return {name: (output / name).read_bytes() for name in ARTIFACT_FILES}


def _expected_journal_rows(execution: Mapping[str, Any]) -> list[JsonObject]:
    executions = execution["executions"]
    payloads = execution["provider_payloads"]
    before = executions["before_event"]
    before_payload = payloads["before_event"]
    rows = [
        _journal_row(
            "ATTEMPT_STARTED",
            phase_id="before_event",
            run_position=0,
            provider_input_fingerprint_sha256=_fingerprint(before_payload),
        )
    ]
    if before["status"] == "completed":
        rows.append(
            _journal_row(
                "ATTEMPT_TERMINAL",
                phase_id="before_event",
                run_position=0,
                status="completed",
                provider_input_fingerprint_sha256=_fingerprint(before_payload),
                public_output_fingerprint_sha256=_fingerprint(before["public_output"]),
                compiled_output_fingerprint_sha256=before["compiled_output"][
                    "fingerprint_sha256"
                ],
            )
        )
    else:
        rows.append(
            _journal_row(
                "ATTEMPT_TERMINAL",
                phase_id="before_event",
                run_position=0,
                status="failed",
                provider_input_fingerprint_sha256=_fingerprint(before_payload),
                public_output_fingerprint_sha256=None,
            )
        )
        return rows

    compiled_before = before["compiled_output"]
    rows.append(
        _journal_row(
            "REVISION_STARTED",
            source_before_public_output_fingerprint_sha256=_fingerprint(
                before["public_output"]
            ),
            source_before_compiled_fingerprint_sha256=compiled_before[
                "fingerprint_sha256"
            ],
            gold_loaded=False,
        )
    )
    control = execution["control_map"]
    actuator = execution["compiled_actuator"]
    after_payload = payloads["after_event"]
    rows.append(
        _journal_row(
            "REVISION_COMPILED",
            source_before_public_output_fingerprint_sha256=_fingerprint(
                before["public_output"]
            ),
            source_before_compiled_fingerprint_sha256=compiled_before[
                "fingerprint_sha256"
            ],
            controller_input_fingerprint_sha256=control["actual_before_state"][
                "fingerprint_sha256"
            ],
            autograd_audit_fingerprint_sha256=control["source_credit_basis"][
                "source_adjoint_fingerprint_sha256"
            ],
            control_map_fingerprint_sha256=control["fingerprint_sha256"],
            compiled_actuator_fingerprint_sha256=actuator["fingerprint_sha256"],
            after_provider_input_fingerprint_sha256=_fingerprint(after_payload),
            gold_loaded=False,
        )
    )
    rows.append(
        _journal_row(
            "ATTEMPT_STARTED",
            phase_id="after_event",
            run_position=1,
            provider_input_fingerprint_sha256=_fingerprint(after_payload),
        )
    )
    after = executions["after_event"]
    rejected = after.get("rejected_public_output")
    rows.append(
        _journal_row(
            "ATTEMPT_TERMINAL",
            phase_id="after_event",
            run_position=1,
            status=after["status"],
            provider_input_fingerprint_sha256=_fingerprint(after_payload),
            public_output_fingerprint_sha256=(
                _fingerprint(after["public_output"])
                if after["status"] == "completed"
                else (None if rejected is None else _fingerprint(rejected))
            ),
            compiled_output_fingerprint_sha256=(
                after["compiled_output"]["fingerprint_sha256"]
                if after["status"] == "completed"
                else None
            ),
        )
    )
    return rows


def _validate_execution_chain(
    fixture: Mapping[str, Any],
    execution: Mapping[str, Any],
    *,
    allow_offline_provider: bool,
) -> None:
    executions = execution["executions"]
    payloads = execution["provider_payloads"]
    phase_ids = [phase_id for phase_id in PHASES if phase_id in executions]
    _require(
        set(executions) == set(phase_ids)
        and phase_ids in (["before_event"], list(PHASES)),
        "EXECUTION_PHASE_ORDER_DRIFT",
    )
    _require(list(payloads) == phase_ids, "EXECUTION_PAYLOAD_PHASE_ORDER_DRIFT")
    for run_position, phase_id in enumerate(phase_ids):
        row = executions[phase_id]
        payload = payloads[phase_id]
        _require(
            row.get("phase_id") == phase_id
            and row.get("run_position") == run_position
            and row.get("status") in {"completed", "failed"},
            "EXECUTION_ROW_IDENTITY_DRIFT",
            phase_id,
        )
        _require(
            row.get("provider_input_fingerprint_sha256") == _fingerprint(payload),
            "EXECUTION_INPUT_BINDING_DRIFT",
            phase_id,
        )
        if row["status"] == "completed":
            _exact_keys(
                row,
                {
                    "phase_id",
                    "run_position",
                    "status",
                    "provider_input_fingerprint_sha256",
                    "public_output",
                    "compiled_output",
                    "receipt",
                    "failure",
                },
                f"execution.{phase_id}",
            )
            _require(row["failure"] is None, "COMPLETED_EXECUTION_HAS_FAILURE")
            _require(isinstance(row["receipt"], Mapping), "COMPLETED_RECEIPT_MISSING")
            _validate_published_receipt(
                row["receipt"],
                payload,
                phase_id=phase_id,
                completed=True,
                allow_offline_provider=allow_offline_provider,
            )
            compiled = _compile_candidate_output(
                fixture, phase_id, row["public_output"]
            )
            _require(
                _canonical_bytes(compiled)
                == _canonical_bytes(row["compiled_output"]),
                "COMPILED_OUTPUT_REDERIVATION_DRIFT",
                phase_id,
            )
        else:
            _exact_keys(
                row,
                {
                    "phase_id",
                    "run_position",
                    "status",
                    "provider_input_fingerprint_sha256",
                    "public_output",
                    "rejected_public_output",
                    "compiled_output",
                    "receipt",
                    "failure",
                },
                f"execution.{phase_id}",
            )
            _require(
                row["public_output"] is None
                and row["compiled_output"] is None
                and isinstance(row["failure"], Mapping),
                "FAILED_EXECUTION_SHAPE_DRIFT",
                phase_id,
            )
            _exact_keys(
                row["failure"],
                {"exception_class", "reason_code", "category", "phase"},
                f"execution.{phase_id}.failure",
            )
            _require(
                isinstance(row["receipt"], Mapping),
                "FAILED_RECEIPT_INVALID",
            )
            receipt_metadata = row["receipt"].get("metadata")
            receipt_completed = bool(
                row["receipt"].get("provider") == "openai_responses"
                and isinstance(receipt_metadata, Mapping)
                and receipt_metadata.get("attempt_outcome") == "completed"
                and receipt_metadata.get("failure_phase") is None
                and receipt_metadata.get("failure_reason_code") is None
            )
            _validate_published_receipt(
                row["receipt"],
                payload,
                phase_id=phase_id,
                completed=receipt_completed,
                allow_offline_provider=allow_offline_provider,
            )
            if row["receipt"]["provider"] == "openai_responses":
                metadata = row["receipt"]["metadata"]
                if receipt_completed:
                    _require(
                        row["rejected_public_output"] is not None
                        and row["failure"]["phase"] is None,
                        "FAILED_LOCAL_REJECTION_CHAIN_DRIFT",
                        phase_id,
                    )
                else:
                    _require(
                        row["rejected_public_output"] is None
                        and row["failure"]["phase"] == metadata["failure_phase"]
                        and row["failure"]["reason_code"]
                        == metadata["failure_reason_code"]
                        and metadata["failure_type"]
                        == metadata["failure_reason_code"],
                        "FAILED_PROVIDER_RECEIPT_CHAIN_DRIFT",
                        phase_id,
                    )

    before = executions["before_event"]
    if before["status"] == "failed":
        _require(
            phase_ids == ["before_event"]
            and execution["control_map"] is None
            and execution["compiled_actuator"] is None,
            "FAILED_BEFORE_CONTINUATION_DRIFT",
        )
        return
    _require(phase_ids == list(PHASES), "VALID_BEFORE_MUST_HAVE_AFTER_ATTEMPT")
    expected_control = derive_public_control_map(fixture, before["compiled_output"])
    expected_actuator = compile_actuator(
        fixture, before["compiled_output"], expected_control
    )
    _require(
        _canonical_bytes(execution["control_map"])
        == _canonical_bytes(expected_control),
        "CONTROL_MAP_REDERIVATION_DRIFT",
    )
    _require(
        _canonical_bytes(execution["compiled_actuator"])
        == _canonical_bytes(expected_actuator),
        "ACTUATOR_REDERIVATION_DRIFT",
    )
    expected_after_payload = build_provider_payload(
        fixture,
        "after_event",
        compiled_before=before["compiled_output"],
        actuator=expected_actuator,
    )
    _require(
        _canonical_bytes(payloads["after_event"])
        == _canonical_bytes(expected_after_payload),
        "AFTER_PAYLOAD_REDERIVATION_DRIFT",
    )


def validate_bundle(
    output: Path,
    *,
    lock: Mapping[str, Any] | None = None,
    in_memory_gold: Mapping[str, Any] | None = None,
    allow_offline_provider: bool = False,
) -> JsonObject:
    files = _read_bundle(output)
    manifest = _strict_json_bytes(files["manifest.json"], label="manifest")
    _require(isinstance(manifest, dict), "MANIFEST_ROOT_INVALID")
    _validate_seal(manifest, "manifest")
    for name, receipt in manifest["artifacts"].items():
        _require(
            name in files
            and name != "manifest.json"
            and receipt == {"bytes": len(files[name]), "sha256": _sha256_bytes(files[name])},
            "MANIFEST_ARTIFACT_RECEIPT_DRIFT",
            name,
        )
    result = _strict_json_bytes(files["result.json"], label="result")
    provider_inputs = _strict_json_bytes(files["provider_inputs.json"], label="provider_inputs")
    trace = _strict_json_bytes(files["apply_revision_trace.json"], label="trace")
    for label, value in (("result", result), ("provider_inputs", provider_inputs), ("trace", trace)):
        _require(isinstance(value, dict), "ARTIFACT_JSON_ROOT_INVALID", label)
        _validate_seal(value, label)
    _require(manifest["result_fingerprint_sha256"] == result["fingerprint_sha256"], "MANIFEST_RESULT_BINDING_DRIFT")
    effective_lock = _load_lock() if lock is None else lock
    _require(manifest["policy_lock_fingerprint_sha256"] == effective_lock["fingerprint_sha256"], "MANIFEST_LOCK_BINDING_DRIFT")
    _exact_keys(
        provider_inputs,
        {
            "schema_version",
            "phase_order",
            "payloads",
            "after_payload_was_dynamic",
            "semantic_gold_provider_visible",
            "fingerprint_sha256",
        },
        "provider_inputs",
    )
    _require(
        provider_inputs["schema_version"] == PROVIDER_INPUTS_SCHEMA
        and provider_inputs["semantic_gold_provider_visible"] is False,
        "PROVIDER_INPUTS_CONTRACT_DRIFT",
    )
    payload_rows = provider_inputs["payloads"]
    _require(isinstance(payload_rows, list) and payload_rows, "PROVIDER_INPUT_ROWS_INVALID")
    phase_order = provider_inputs["phase_order"]
    _require(
        phase_order in (["before_event"], list(PHASES))
        and [row.get("phase_id") for row in payload_rows] == phase_order
        and len(set(phase_order)) == len(phase_order),
        "PROVIDER_INPUT_PHASE_ORDER_DRIFT",
    )
    payloads: dict[str, JsonObject] = {}
    fixture = load_fixture()
    for row in payload_rows:
        _exact_keys(
            row,
            {"phase_id", "payload_fingerprint_sha256", "payload"},
            "provider_input_row",
        )
        phase_id = row["phase_id"]
        payload = row["payload"]
        _require(
            row["payload_fingerprint_sha256"] == _fingerprint(payload),
            "PROVIDER_INPUT_ROW_BINDING_DRIFT",
            phase_id,
        )
        validate_provider_payload(fixture, phase_id, payload)
        payloads[phase_id] = payload
    _require(
        provider_inputs["after_payload_was_dynamic"]
        is ("after_event" in payloads),
        "PROVIDER_INPUT_DYNAMIC_STATUS_DRIFT",
    )
    execution = {
        "phase_order": list(PHASES),
        "executions": _clone(result["executions"]),
        "provider_payloads": payloads,
        "control_map": _clone(trace["control_map"]),
        "compiled_actuator": _clone(trace["compiled_actuator"]),
        "two_structurally_valid_terminals": result["status"] == "COMPLETE_EXACT_TWO_TERMINALS",
        "gold_loaded": False,
    }
    _validate_execution_chain(
        fixture,
        execution,
        allow_offline_provider=allow_offline_provider,
    )
    derived_complete = (
        set(execution["executions"]) == set(PHASES)
        and all(
            execution["executions"][phase_id]["status"] == "completed"
            and execution["executions"][phase_id]["compiled_output"] is not None
            for phase_id in PHASES
        )
    )
    _require(
        execution["two_structurally_valid_terminals"] is derived_complete,
        "TERMINAL_COMPLETENESS_REDERIVATION_DRIFT",
    )
    _require(
        _canonical_bytes(provider_inputs)
        == _canonical_bytes(_provider_inputs_artifact(execution)),
        "PROVIDER_INPUTS_REDERIVATION_DRIFT",
    )
    _require(
        _canonical_bytes(trace) == _canonical_bytes(_trace_artifact(execution)),
        "TRACE_REDERIVATION_DRIFT",
    )
    gold = None
    if execution["two_structurally_valid_terminals"]:
        gold = _load_gold(fixture) if in_memory_gold is None else _clone(in_memory_gold)
        validate_gold(gold, fixture)
    else:
        _require(in_memory_gold is None, "INCOMPLETE_BUNDLE_MUST_NOT_RECEIVE_GOLD")
    expected_result = finalize_result(fixture, execution, gold)
    _require(_canonical_bytes(expected_result) == _canonical_bytes(result), "RESULT_REDERIVATION_DRIFT")
    _require(files["calls.jsonl"] == _calls_bytes(execution), "CALLS_ARTIFACT_DRIFT")
    journal = _strict_jsonl(files["attempt_journal.jsonl"], label="attempt_journal")
    for row in journal:
        _validate_seal(row, "journal_row")
    _require(
        _canonical_bytes(journal) == _canonical_bytes(_expected_journal_rows(execution)),
        "JOURNAL_BINDING_DRIFT",
    )
    _require(files["report.md"] == _report(result).encode("utf-8"), "REPORT_DRIFT")
    expected_manifest = _manifest_value(
        {name: raw for name, raw in files.items() if name != "manifest.json"},
        result,
        effective_lock,
    )
    _require(_canonical_bytes(expected_manifest) == _canonical_bytes(manifest), "MANIFEST_REDERIVATION_DRIFT")
    return {
        "status": "VALID",
        "artifact_directory": str(output),
        "terminal_decision": result["decision"]["terminal_decision"],
        "result_fingerprint_sha256": result["fingerprint_sha256"],
    }


class _ScriptedProvider:
    """Gold-free deterministic provider used only by offline self-test."""

    def __init__(self, *, fail_phase: str | None = None, wrong_before: bool = False) -> None:
        self.audit_receipts: list[JsonObject] = []
        self.fail_phase = fail_phase
        self.wrong_before = wrong_before

    @property
    def provenance(self) -> JsonObject:
        return {"provider": "offline_scripted", **_runtime_contract()}

    @staticmethod
    def _candidate_for(payload: Mapping[str, Any], *, after: bool) -> str:
        matches: list[tuple[int, str]] = []
        for candidate in payload["candidate_closures"]:
            graph = candidate["graph"]
            active = {
                evidence_id
                for support in graph["support_nodes"]
                for evidence_id in support["evidence_ids"]
            }
            invalid = {
                row["target_evidence_id"] for row in graph["invalidation_edges"]
            }
            if (after and invalid == {"R3"} and {"R2", "R4", "R5", "R6"} <= active) or (
                not after and not invalid and "R3" in active
            ):
                structural_specificity = sum(
                    len(row["direct_support_ids"]) + 2 * len(row["depends_on_target_ids"])
                    for row in graph["targets"]
                )
                matches.append((structural_specificity, candidate["closure_id"]))
        if matches:
            return max(matches)[1]
        raise ApplyRevisionError("SCRIPTED_PROVIDER_CANDIDATE_NOT_FOUND")

    def generate(self, payload: Mapping[str, Any]) -> tuple[JsonObject, JsonObject]:
        after = payload["apply_revision"] is not None
        phase_id = "after_event" if after else "before_event"
        receipt = {
            "provider": "offline_scripted",
            "requested_model": MODEL,
            "returned_model": MODEL,
            "logical_calls": 1,
            "api_calls": 1,
            "latency_ms": 0.0,
            "request_fingerprint": _fingerprint(payload),
            "prompt_fingerprint": _fingerprint(PROVIDER_INSTRUCTIONS),
            "usage": {
                "exact_provider_tokens": False,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cached_input_tokens": 0,
                "cache_write_tokens": 0,
                "reasoning_tokens": 0,
            },
            "metadata": {
                "reasoning_effort": REASONING_EFFORT,
                "max_output_tokens": MAX_OUTPUT_TOKENS,
                "store": False,
                "previous_response_id": False,
                "retry_count": 0,
            },
        }
        self.audit_receipts.append(_clone(receipt))
        if self.fail_phase == phase_id:
            return {"schema_version": "invalid"}, receipt
        if not after and self.wrong_before:
            candidate_id = payload["candidate_closures"][0]["closure_id"]
            answer = "PROVE"
            values = ("END_TO_END_PROOF", "LIVE_REASONING_DIFF")
        else:
            candidate_id = self._candidate_for(payload, after=after)
            answer = "PROVE" if after else "POLISH"
            values = (
                ("END_TO_END_PROOF", "LIVE_REASONING_DIFF")
                if after
                else ("ADDITIONAL_UI_POLISH", "POLISHED_SCREENS")
            )
        output = {
            "schema_version": OUTPUT_SCHEMA,
            "checkpoint_id": payload["checkpoint_id"],
            "current_answer": answer,
            "selected_closure_id": candidate_id,
            "target_values": [
                {
                    "target_id": "fact:final_priority",
                    "target_type": "fact",
                    "slot": "final_priority",
                    "value": values[0],
                },
                {
                    "target_id": "fact:demo_centerpiece",
                    "target_type": "fact",
                    "slot": "demo_centerpiece",
                    "value": values[1],
                },
                {
                    "target_id": "constraint:video_constraint",
                    "target_type": "constraint",
                    "slot": "video_constraint",
                    "value": "THREE_MINUTE_NARRATED",
                },
            ],
        }
        return output, receipt


def self_test() -> JsonObject:
    fixture = load_fixture()
    checks: dict[str, bool] = {}
    with _semantic_gold_denied() as precise_barrier:
        opaque_lock = policy_lock_material()
        semantic_parse_rejected = False
        try:
            _load_gold(fixture)
        except ApplyRevisionError as error:
            semantic_parse_rejected = (
                error.reason_code == "SEMANTIC_GOLD_ACCESSED_BEFORE_TWO_TERMINALS"
            )
    checks["opaque_gold_hash_allowed_semantic_parse_denied"] = (
        opaque_lock["semantic_gold_bytes_sha256"] == _sha256_path(GOLD_PATH)
        and semantic_parse_rejected
        and precise_barrier["attempted_gold_accesses"] == 1
    )
    with tempfile.TemporaryDirectory(prefix="ebrt-apply-revision-self-test-") as raw_tmp:
        temporary = Path(raw_tmp)
        journal = temporary / "attempts.jsonl"
        dynamic = temporary / "after.json"
        provider = _ScriptedProvider()
        with _network_denied() as network, _semantic_gold_denied() as denied:
            execution = execute_gold_free(
                fixture,
                provider,
                journal_path=journal,
                dynamic_payload_path=dynamic,
            )
        checks["offline_no_network"] = network["network_calls"] == 0
        checks["gold_denied_during_two_call_execution"] = denied["attempted_gold_accesses"] == 0
        checks["exactly_two_calls"] = len(provider.audit_receipts) == 2
        checks["two_structurally_valid_terminals"] = execution["two_structurally_valid_terminals"]
        gold = _load_gold(fixture)
        result = finalize_result(fixture, execution, gold)
        checks["all_green_product_acceptance"] = (
            result["decision"]["product_acceptance_status"] == "PASS"
        )
        actuator = execution["compiled_actuator"]
        checks["mechanically_honest_actuator"] = (
            actuator["reinspect_evidence_ids"] == ["R6", "R4", "R2"]
            and actuator["suppress_evidence_ids"] == ["R3"]
            and actuator["preserve_evidence_ids"] == ["R5"]
        )
        checks["dynamic_payload_durable_and_bound"] = (
            dynamic.read_bytes() == _canonical_bytes(execution["provider_payloads"]["after_event"])
        )
        journal_rows = _strict_jsonl(journal.read_bytes(), label="self_test_journal")
        checks["exact_six_event_state_machine"] = [row["kind"] for row in journal_rows] == [
            "ATTEMPT_STARTED",
            "ATTEMPT_TERMINAL",
            "REVISION_STARTED",
            "REVISION_COMPILED",
            "ATTEMPT_STARTED",
            "ATTEMPT_TERMINAL",
        ]
        wrong_provider = _ScriptedProvider(wrong_before=True)
        wrong_execution = execute_gold_free(
            fixture,
            wrong_provider,
            journal_path=temporary / "wrong_attempts.jsonl",
            dynamic_payload_path=temporary / "wrong_after.json",
        )
        checks["structurally_valid_before_always_continues"] = (
            len(wrong_provider.audit_receipts) == 2
            and wrong_execution["two_structurally_valid_terminals"]
        )
        failed_provider = _ScriptedProvider(fail_phase="before_event")
        failed_execution = execute_gold_free(
            fixture,
            failed_provider,
            journal_path=temporary / "failed_attempts.jsonl",
            dynamic_payload_path=temporary / "failed_after.json",
        )
        failed_result = finalize_result(fixture, failed_execution, None)
        checks["invalid_before_burns_one_call_no_gold"] = (
            len(failed_provider.audit_receipts) == 1
            and failed_result["semantic_gold"]["loaded"] is False
            and failed_result["decision"]["product_acceptance_status"] == "NOT_ASSESSED"
        )
        synthetic_lock = policy_lock_material()
        files = _materialize_files(
            result,
            execution,
            lock=synthetic_lock,
            journal_bytes=journal.read_bytes(),
        )
        artifact = temporary / "artifact"
        _publish(artifact, files)
        validation = validate_bundle(
            artifact,
            lock=synthetic_lock,
            in_memory_gold=gold,
            allow_offline_provider=True,
        )
        checks["artifact_roundtrip_valid"] = validation["status"] == "VALID"

        def reseal_manifest(bundle: Path) -> None:
            bundle_files = {
                name: (bundle / name).read_bytes()
                for name in ARTIFACT_FILES
                if name != "manifest.json"
            }
            bundle_result = _strict_json_bytes(
                bundle_files["result.json"], label="tamper_result"
            )
            (bundle / "manifest.json").write_bytes(
                _pretty_bytes(
                    _manifest_value(bundle_files, bundle_result, synthetic_lock)
                )
            )

        receipt_tamper = temporary / "receipt_tamper"
        shutil.copytree(artifact, receipt_tamper)
        receipt_result = _strict_json_bytes(
            (receipt_tamper / "result.json").read_bytes(), label="receipt_tamper"
        )
        receipt_result["executions"]["before_event"]["receipt"][
            "requested_model"
        ] = "not-the-locked-model"
        receipt_result = _seal(_without_fingerprint(receipt_result))
        (receipt_tamper / "result.json").write_bytes(_pretty_bytes(receipt_result))
        receipt_calls = _strict_jsonl(
            (receipt_tamper / "calls.jsonl").read_bytes(),
            label="receipt_tamper_calls",
        )
        receipt_calls[0]["receipt"]["requested_model"] = "not-the-locked-model"
        receipt_calls[0] = _seal(_without_fingerprint(receipt_calls[0]))
        (receipt_tamper / "calls.jsonl").write_bytes(
            b"".join(
                _canonical_bytes(row, trailing_newline=True) for row in receipt_calls
            )
        )
        reseal_manifest(receipt_tamper)
        try:
            validate_bundle(
                receipt_tamper,
                lock=synthetic_lock,
                in_memory_gold=gold,
                allow_offline_provider=True,
            )
            receipt_tamper_rejected = False
        except ApplyRevisionError as error:
            receipt_tamper_rejected = error.reason_code == "RECEIPT_MODEL_INVALID"
        checks["coherently_resealed_receipt_tamper_rejected"] = (
            receipt_tamper_rejected
        )

        journal_tamper = temporary / "journal_tamper"
        shutil.copytree(artifact, journal_tamper)
        journal_rows = _strict_jsonl(
            (journal_tamper / "attempt_journal.jsonl").read_bytes(),
            label="journal_tamper_rows",
        )
        journal_rows[0]["provider_input_fingerprint_sha256"] = "0" * 64
        journal_rows[0] = _seal(_without_fingerprint(journal_rows[0]))
        (journal_tamper / "attempt_journal.jsonl").write_bytes(
            b"".join(
                _canonical_bytes(row, trailing_newline=True) for row in journal_rows
            )
        )
        reseal_manifest(journal_tamper)
        try:
            validate_bundle(
                journal_tamper,
                lock=synthetic_lock,
                in_memory_gold=gold,
                allow_offline_provider=True,
            )
            journal_tamper_rejected = False
        except ApplyRevisionError as error:
            journal_tamper_rejected = error.reason_code == "JOURNAL_BINDING_DRIFT"
        checks["coherently_resealed_journal_tamper_rejected"] = (
            journal_tamper_rejected
        )

        hidden_complete = _clone(execution)
        hidden_complete["two_structurally_valid_terminals"] = False
        hidden_result = finalize_result(fixture, hidden_complete, None)
        hidden_files = _materialize_files(
            hidden_result,
            hidden_complete,
            lock=synthetic_lock,
            journal_bytes=journal.read_bytes(),
        )
        hidden_bundle = temporary / "hidden_complete"
        _publish(hidden_bundle, hidden_files)
        try:
            validate_bundle(
                hidden_bundle,
                lock=synthetic_lock,
                allow_offline_provider=True,
            )
            hidden_complete_rejected = False
        except ApplyRevisionError as error:
            hidden_complete_rejected = (
                error.reason_code == "TERMINAL_COMPLETENESS_REDERIVATION_DRIFT"
            )
        checks["completed_terminals_cannot_be_downgraded"] = (
            hidden_complete_rejected
        )
    checks["effect_attribution_not_assessed"] = (
        result["decision"]["effect_attribution_status"] == "NOT_ASSESSED"
    )
    _require(
        all(checks.values()),
        "SELF_TEST_FAILED",
        ",".join(name for name, passed in checks.items() if not passed),
    )
    return _seal(
        {
            "schema_version": "ebrt-apply-revision-self-test-v0.6.2.1-r01",
            "status": "PASS",
            "checks": checks,
            "fixture_fingerprint_sha256": fixture["fingerprint_sha256"],
            "gold_fingerprint_sha256": gold["fingerprint_sha256"],
            "result_fingerprint_sha256": result["fingerprint_sha256"],
        }
    )


def run_live(output: Path = DEFAULT_OUTPUT) -> JsonObject:
    _require(output.is_absolute(), "LIVE_OUTPUT_MUST_BE_ABSOLUTE")
    _require(output == DEFAULT_OUTPUT.resolve(), "LIVE_OUTPUT_NAMESPACE_DRIFT")
    _require(not output.exists(), "LIVE_OUTPUT_ALREADY_EXISTS")
    staging = output.with_name(f".{output.name}.inflight")
    _require(not staging.exists(), "INFLIGHT_EXISTS_NO_RESUME")
    lock = _load_lock()
    preflight_value = preflight(require_api_key=True, require_authorization=True)
    _require(
        _git_text("status", "--porcelain", "--untracked-files=all") == "",
        "LIVE_WORKTREE_NOT_CLEAN",
    )
    fixture = load_fixture()
    authorization = preflight_value["execution_authorization"]
    before_payload = build_provider_payload(fixture, "before_event")
    # Construction performs all SDK/runtime capability checks but no request.
    # Do it before creating the irreversible in-flight namespace.
    provider = OpenAIApplyRevisionProvider()
    source_snapshot = {
        label: _sha256_path(ROOT / relative_path)
        for label, relative_path in LOCKED_SOURCE_PATHS.items()
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    staging.mkdir(mode=0o700)
    _fsync_directory(staging.parent)
    plan = _seal(
        {
            "schema_version": "ebrt-apply-revision-inflight-plan-v0.6.2.1-r01",
            "status": "IRREVERSIBLE_DYNAMIC_TWO_CALL_BLOCK_NOT_YET_STARTED",
            "policy_lock_fingerprint_sha256": lock["fingerprint_sha256"],
            "fixture_fingerprint_sha256": fixture["fingerprint_sha256"],
            "before_payload_fingerprint_sha256": _fingerprint(before_payload),
            "after_payload_fingerprint_sha256": None,
            "after_payload_is_dynamic": True,
            "source_snapshot_sha256": source_snapshot,
            "execution_authorization": authorization,
            "phase_order": list(PHASES),
            "no_retry": True,
            "no_resume": True,
            "no_backfill": True,
        }
    )
    plan_path = staging / "plan.json"
    plan_path.write_bytes(_pretty_bytes(plan))
    with plan_path.open("rb") as handle:
        os.fsync(handle.fileno())
    journal_path = staging / "attempt_journal.jsonl"
    journal_path.touch(mode=0o600)
    _fsync_directory(staging)

    def source_guard() -> None:
        _require(_load_lock()["fingerprint_sha256"] == lock["fingerprint_sha256"], "LIVE_LOCK_CHANGED")
        observed = {
            label: _sha256_path(ROOT / relative_path)
            for label, relative_path in LOCKED_SOURCE_PATHS.items()
        }
        _require(observed == source_snapshot, "LIVE_SOURCE_CHANGED")
        current = _observe_authorization(allow_pending=False)
        _require(
            current["tag_object"] == authorization["tag_object"]
            and current["authorized_commit"] == authorization["authorized_commit"],
            "LIVE_AUTHORIZATION_CHANGED",
        )

    try:
        source_guard()
        with _semantic_gold_denied() as denied:
            execution = execute_gold_free(
                fixture,
                provider,
                journal_path=journal_path,
                dynamic_payload_path=staging / "dynamic_after_payload.json",
            )
            source_guard()
        _require(denied["attempted_gold_accesses"] == 0, "LIVE_GOLD_BOUNDARY_VIOLATED")
    except Exception as error:
        _append_journal(
            journal_path,
            _journal_row(
                "IRRECOVERABLE_GUARD_FAILURE",
                reason_code=getattr(error, "reason_code", type(error).__name__),
                no_resume=True,
            ),
        )
        raise

    gold = _load_gold(fixture) if execution["two_structurally_valid_terminals"] else None
    result = finalize_result(fixture, execution, gold)
    files = _materialize_files(
        result,
        execution,
        lock=lock,
        journal_bytes=journal_path.read_bytes(),
    )
    _publish(output, files)
    validation = validate_bundle(output, lock=lock, in_memory_gold=gold)
    shutil.rmtree(staging)
    _fsync_directory(output.parent)
    return {
        "status": "PUBLISHED",
        "artifact_directory": str(output),
        "terminal_decision": result["decision"]["terminal_decision"],
        "result_fingerprint_sha256": result["fingerprint_sha256"],
        "validation": validation,
    }


def _print_json(value: Mapping[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("self-test", help="run the fully offline mechanism and artifact tests")
    commands.add_parser("emit-lock", help="print the exact policy lock JSON")
    commands.add_parser("preflight", help="run zero-call readiness checks")
    live = commands.add_parser("run-live", help="execute the irreversible exact two-call block")
    live.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    validate = commands.add_parser("validate", help="validate a published artifact bundle")
    validate.add_argument("--artifact-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "self-test":
            value = self_test()
        elif args.command == "emit-lock":
            value = policy_lock_material()
        elif args.command == "preflight":
            value = preflight()
        elif args.command == "run-live":
            value = run_live(args.output.resolve())
        elif args.command == "validate":
            value = validate_bundle(args.artifact_dir.resolve())
        else:  # pragma: no cover
            raise ApplyRevisionError("UNKNOWN_COMMAND")
        _print_json(value)
        return 0
    except ApplyRevisionError as error:
        _print_json(
            {
                "status": "ERROR",
                "reason_code": error.reason_code,
                "detail": str(error),
            }
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
