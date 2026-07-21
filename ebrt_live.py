#!/usr/bin/env python3
"""EBRT Runtime Preview 4 live Apply Revision product monolith.

This is the current, generic, one-call product path.  The sealed ``ebrt.py``
v0.6.2.1 acceptance runtime is historical evidence and is intentionally not
imported or modified here.

The live path accepts an already-emitted public Before state and a typed late
event, rolls one typed public revision trajectory forward, optimizes bounded
time-local controls with one float64 backward pass, rolls the declared public
program forward again, executes a deterministic public actuator program, then
makes at most one fresh After regeneration call. Reserved gold fields, graders,
provider hidden state, and provider gradients are outside this runtime; caller
semantic content is not certified as gold-free.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import hmac
import http.client
import http.server
import json
import math
import os
import socket
import threading
import uuid
from collections import OrderedDict, defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Literal, Mapping, Protocol, Sequence
from unittest import mock

import torch
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from language_replay_bridge_v0_4 import ProviderReceipt, ProviderUsage, canonical_json
from openai_response_boundary_v0_4_3 import (
    InstrumentedResponsesClientBase,
    OpenAIBoundaryCapabilityError,
    OpenAIProviderBoundaryError,
)


ROOT = Path(__file__).resolve().parent
DEMO_PROVIDER_INPUTS_PATH = (
    ROOT
    / "artifacts"
    / "apply_revision_acceptance_v0_6_2_1_live_r01"
    / "provider_inputs.json"
)
DEMO_MANIFEST_PATH = DEMO_PROVIDER_INPUTS_PATH.with_name("manifest.json")
PINNED_DEMO_MANIFEST_SHA256 = "532dd593ef4464d87dd02fd2eeaa712855f47e5de799c669889c0302ee2fe3a4"
PINNED_DEMO_PROVIDER_INPUTS_SHA256 = "d57b33860db84a0378ffd6b6e18ef67ae64d66eb75bd1959c1a1c7424ea90a3f"
PINNED_DEMO_PROVIDER_INPUTS_FINGERPRINT = "a2aa446099b7cf498e307cf2bdb261c6c8aa705db034935bc88bbf040c9936a1"

REQUEST_SCHEMA = "ebrt-live-apply-revision-request-v0.6.2.5"
PROVIDER_INPUT_SCHEMA = "ebrt-live-provider-input-v0.6.2.5"
PROVIDER_OUTPUT_SCHEMA = "ebrt-live-provider-output-v0.6.2.5"
COMPILED_SCHEMA = "ebrt-live-compiled-closure-v0.6.2.5"
ACTUAL_STATE_SCHEMA = "ebrt-live-actual-before-state-v0.6.2.5"
TRAJECTORY_SCHEMA = "ebrt-live-public-revision-trajectory-v0.6.2.5"
CONTROL_SCHEMA = "ebrt-live-public-control-map-v0.6.2.5"
ACTUATOR_SCHEMA = "ebrt-live-compiled-actuator-v0.6.2.5"
ACTUATOR_EXECUTION_SCHEMA = "ebrt-live-actuator-execution-v0.6.2.5"
REVISION_OPERATION_SCHEMA = "ebrt-live-apply-revision-operation-v0.6.2.5"
DEPENDENCY_AUDIT_SCHEMA = "ebrt-live-public-dependency-audit-v0.6.2.5"
DIFF_SCHEMA = "ebrt-live-public-diff-v0.6.2.5"
RESPONSE_SCHEMA = "ebrt-live-apply-revision-response-v0.6.2.5"
DEMO_REQUEST_SCHEMA = "ebrt-live-demo-request-v0.6.2.5"
ERROR_SCHEMA = "ebrt-live-error-v0.6.2.5"

MODEL = "gpt-5.6-sol"
REASONING_EFFORT = "low"
MAX_OUTPUT_TOKENS = 1024
TIMEOUT_SECONDS = 60.0

FLOAT_DTYPE = torch.float64
STATE_DECAY = 0.82
STEP_SIZE = 0.05
CONTROL_REGULARIZATION = 0.01
TEMPORAL_SMOOTHNESS_REGULARIZATION = 0.005
TRAJECTORY_PATH_REGULARIZATION = 0.1
TERMINAL_TARGET = 1.0
INSPECTION_TEMPERATURE = 1.0
INSPECTION_BUDGET_UNITS = 100
ALLOCATION_TOLERANCE = 1.0e-12
SHAM_GEOMETRY_TOLERANCE = 1.0e-15
FINITE_DIFFERENCE_EPSILON = 1.0e-6
FINITE_DIFFERENCE_TOLERANCE = 1.0e-8
MAX_CONTROL_L2 = 0.25
MAX_BACKTRACKS = 12
TRAJECTORY_AXES = (
    "event_consistent_support",
    "invalidated_support_clearance",
    "stable_support_retention",
)
TRAJECTORY_PRODUCT_CHECK_KEYS = (
    "source_actual_before_state_bound",
    "chronological_forward_exact",
    "zero_control_is_exact_unmodified_forward",
    "single_backward_executed",
    "pre_event_temporal_credit_nonzero",
    "correction_site_credit_nonzero",
    "trajectory_objective_decreased",
    "trajectory_path_loss_decreased",
    "revised_forward_replay_exact",
    "stable_axis_exact_identity",
    "bounded_time_local_control",
    "gradient_stops_before_json",
)
CONTROL_PRODUCT_CHECK_KEYS = (
    "actual_before_state_bound_to_controller",
    "local_backward_executed",
    "finite_continuous_allocation",
    "surrogate_objective_decreased",
    "non_neutral_control_map",
    "control_budget_respected",
    "allocation_simplex_respected",
    "ineligible_allocation_zero",
    "surrogate_terminal_state_increased",
    "finite_difference_agreement",
    "public_trajectory_bound",
    "pre_event_temporal_credit_nonzero",
    "trajectory_path_loss_decreased",
    "stable_axis_exact_identity",
    "gradient_stops_before_provider",
    "reserved_gold_fields_absent",
)

MAX_HTTP_BYTES = 256 * 1024
MAX_EVIDENCE = 64
MAX_SLOTS = 32
MAX_CANDIDATES = 16
MAX_SUPPORTS = 128
MAX_IDEMPOTENCY_ENTRIES = 128
MAX_COMPACT_TOMBSTONES = 65_536

RELAY_TOKEN_ENV = "EBRT_RELAY_TOKEN"
RELAY_TOTAL_BUDGET_ENV = "EBRT_RELAY_MAX_PROVIDER_ATTEMPTS_TOTAL"
RELAY_CLIENT_BUDGET_ENV = "EBRT_RELAY_MAX_PROVIDER_ATTEMPTS_PER_CLIENT"
RELAY_TOKEN_HEADER = "X-EBRT-Relay-Token"
RELAY_CLIENT_KEY_HEADER = "X-EBRT-Client-Key"
DEFAULT_RELAY_MAX_PROVIDER_ATTEMPTS_TOTAL = 64
DEFAULT_RELAY_MAX_PROVIDER_ATTEMPTS_PER_CLIENT = 4
MAX_RELAY_PROVIDER_ATTEMPT_BUDGET = 1_000_000
INTERNAL_DIRECT_CLIENT_KEY = "0" * 64

ALLOWED_ORIGINS = frozenset(
    {
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    }
)

FORBIDDEN_REQUEST_KEYS = frozenset(
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
        "gradients",
        "loss",
        "quality_label",
        "required_support",
        "semantic_gold",
        "target_answer",
        "target_closure",
        "target_closure_id",
        "treatment",
        "treatment_id",
    }
)

PROVIDER_FORBIDDEN_KEYS = FORBIDDEN_REQUEST_KEYS | frozenset(
    {
        "control_l2",
        "credit_rows",
        "finite_difference_gradient",
        "objective_after",
        "objective_before",
        "optimized_allocation_fraction",
        "signed_public_credit",
        "reinspection_salience",
        "source_effect",
    }
)

CLAIM_BOUNDARY = (
    "This invalidation-revision path applies one bounded public revision operation to caller-supplied public structure; it is not a semantic correctness oracle.",
    "The local float64 surrogate performs one projected temporal-control step over a three-axis public revision trajectory constructed from the compiled public Before support state, role-blind graph incidence, and the typed event.",
    "The revised public trajectory is re-executed through its declared transition before inspection shares are decoded; it is not a transcript of private model reasoning.",
    "Zero temporal control is an exact no-op over the event-bearing public revision proposals; the uncontrolled trajectory follows only the frozen forward recurrence.",
    "The backward pass assigns where and how much to reinspect. The typed event compiler supplies the allowlisted suppress and preserve semantics.",
    "Inspection allocation fractions and units decoded from absolute temporal-control magnitude are external public review directives; they are not provider attention probabilities, reasoning-token budgets, or measurements of provider uptake.",
    "The local matched-sham comparison is a sealed research diagnostic, not a product execution gate or evidence of provider uptake.",
    "The gradient stops at the public control map; JSON, provider parsing, generation, and verification are not differentiated.",
    "The block/restore dependency probe concerns only the selected caller-supplied public graph; it does not regenerate a counterfactual hosted output or establish hosted-model causality.",
    "Operational acceptance means the one-call output is structurally valid and event-consistent; semantic correctness is NOT_ASSESSED.",
    "Effect attribution, causal superiority, quality improvement, hidden-state editing, attention control, and KV-cache control are NOT_ASSESSED.",
)

PROVIDER_INSTRUCTIONS = (
    "Return only the strict public Apply Revision response. Ordered raw evidence is the only semantic authority. "
    "Candidate closure IDs are opaque public alternatives. Select exactly one supplied closure, derive the current answer "
    "and every target value from the visible raw evidence, and execute the supplied Apply Revision program in its listed "
    "order: load the event, suppress invalidated active evidence, reinspect evidence according to its relative public "
    "inspection allocation decoded from the public revision trajectory, preserve stable evidence, then regenerate from the full context. Inspection shares, abstract "
    "budget units, depth labels, and emphasis weights are review directives, not new evidence, provider token budgets, "
    "attention probabilities, or semantic authority. The operation is "
    "not new evidence, semantic gold, or an expected answer. Do not return private reasoning, prose, invented evidence, "
    "an unknown closure ID, or fields outside the response schema."
)


JsonObject = dict[str, Any]


class LiveRevisionError(RuntimeError):
    """Fail-closed public error with a stable, sanitizable reason code."""

    def __init__(
        self,
        reason_code: str,
        detail: str = "",
        *,
        http_status: int = 422,
        idempotent_replay: bool = False,
    ) -> None:
        self.reason_code = reason_code
        self.detail = detail
        self.http_status = http_status
        self.idempotent_replay = idempotent_replay
        super().__init__(reason_code if not detail else f"{reason_code}: {detail}")


def _require(
    condition: bool,
    reason_code: str,
    detail: str = "",
    *,
    http_status: int = 422,
) -> None:
    if not condition:
        raise LiveRevisionError(reason_code, detail, http_status=http_status)


def _relay_token_from_env() -> str | None:
    value = os.environ.get(RELAY_TOKEN_ENV)
    return value if value else None


def _relay_budget_from_env(name: str, default: int, reason_code: str) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw, 10)
    except (TypeError, ValueError):
        raise LiveRevisionError(reason_code, http_status=500) from None
    _require(
        1 <= value <= MAX_RELAY_PROVIDER_ATTEMPT_BUDGET,
        reason_code,
        http_status=500,
    )
    return value


def _valid_relay_client_key(value: str | None) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _require_relay_client_key(value: str | None) -> str:
    _require(
        _valid_relay_client_key(value),
        "RELAY_CLIENT_KEY_INVALID",
        http_status=400,
    )
    assert value is not None
    return value


def _relay_token_matches(expected: str, observed: str | None) -> bool:
    """Compare fixed-length digests so absent and malformed tokens share one path."""

    expected_digest = hashlib.sha256(expected.encode("utf-8")).digest()
    observed_digest = hashlib.sha256((observed or "").encode("utf-8")).digest()
    return hmac.compare_digest(expected_digest, observed_digest)


def _canonical_bytes(value: Any, *, trailing_newline: bool = False) -> bytes:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return raw + (b"\n" if trailing_newline else b"")


def _pretty(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _clone(value: Any) -> Any:
    return copy.deepcopy(value)


def _without_fingerprint(value: Mapping[str, Any]) -> JsonObject:
    output = dict(value)
    output.pop("fingerprint_sha256", None)
    return output


def _seal(value: Mapping[str, Any]) -> JsonObject:
    output = _clone(_without_fingerprint(value))
    output["fingerprint_sha256"] = _fingerprint(output)
    return output


def _reject_constant(token: str) -> Any:
    raise LiveRevisionError("NONFINITE_JSON", token, http_status=400)


def _reject_duplicates(pairs: Sequence[tuple[str, Any]]) -> JsonObject:
    output: JsonObject = {}
    for key, value in pairs:
        if key in output:
            raise LiveRevisionError("DUPLICATE_JSON_KEY", key, http_status=400)
        output[key] = value
    return output


def _reject_nonfinite(value: Any, *, label: str = "$") -> None:
    if isinstance(value, float):
        _require(math.isfinite(value), "NONFINITE_JSON", label, http_status=400)
    elif isinstance(value, Mapping):
        for key, child in value.items():
            _reject_nonfinite(child, label=f"{label}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_nonfinite(child, label=f"{label}[{index}]")


def strict_json_bytes(raw: bytes, *, label: str = "request") -> Any:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicates,
            parse_constant=_reject_constant,
        )
    except LiveRevisionError:
        raise
    except Exception as error:
        raise LiveRevisionError("INVALID_JSON", label, http_status=400) from error
    _reject_nonfinite(value, label=label)
    return value


def _recursive_keys(value: Any) -> set[str]:
    if isinstance(value, Mapping):
        output = {str(key).lower() for key in value}
        for child in value.values():
            output.update(_recursive_keys(child))
        return output
    if isinstance(value, list):
        output: set[str] = set()
        for child in value:
            output.update(_recursive_keys(child))
        return output
    return set()


def _unique_nonempty(values: Sequence[str], *, label: str) -> tuple[str, ...]:
    output = tuple(values)
    _require(bool(output), "EMPTY_LIST", label)
    _require(all(isinstance(value, str) and value for value in output), "INVALID_STRING_LIST", label)
    _require(len(output) == len(set(output)), "DUPLICATE_LIST_ITEM", label)
    return output


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EvidenceItem(_StrictModel):
    evidence_id: str = Field(min_length=1, max_length=96)
    text: str = Field(min_length=1, max_length=8192)


class DecisionSlot(_StrictModel):
    slot_id: str = Field(min_length=1, max_length=96)
    target_type: Literal["fact", "constraint"]
    description: str = Field(min_length=1, max_length=1024)
    allowed_values: list[str] = Field(min_length=1, max_length=32)


class TargetValue(_StrictModel):
    target_id: str = Field(min_length=1, max_length=192)
    target_type: Literal["fact", "constraint"]
    slot: str = Field(min_length=1, max_length=96)
    value: str = Field(min_length=1, max_length=256)


class PriorPublicState(_StrictModel):
    schema_version: str = Field(min_length=1, max_length=128)
    checkpoint_id: str = Field(min_length=1, max_length=192)
    current_answer: str = Field(min_length=1, max_length=256)
    selected_closure_id: str = Field(min_length=1, max_length=128)
    target_values: list[TargetValue] = Field(min_length=1, max_length=MAX_SLOTS)


class SupportNode(_StrictModel):
    support_id: str = Field(min_length=1, max_length=192)
    evidence_ids: list[str] = Field(min_length=1, max_length=MAX_EVIDENCE)


class ClosureTarget(_StrictModel):
    target_id: str = Field(min_length=1, max_length=192)
    target_type: Literal["fact", "constraint"]
    slot: str = Field(min_length=1, max_length=96)
    direct_support_ids: list[str] = Field(min_length=1, max_length=MAX_SUPPORTS)
    depends_on_target_ids: list[str] = Field(default_factory=list, max_length=MAX_SLOTS)


class InvalidationEdge(_StrictModel):
    source_evidence_id: str = Field(min_length=1, max_length=96)
    target_evidence_id: str = Field(min_length=1, max_length=96)


class ClosureGraph(_StrictModel):
    support_nodes: list[SupportNode] = Field(min_length=1, max_length=MAX_SUPPORTS)
    targets: list[ClosureTarget] = Field(min_length=1, max_length=MAX_SLOTS)
    invalidation_edges: list[InvalidationEdge] = Field(default_factory=list, max_length=MAX_EVIDENCE)


class ClosureCandidate(_StrictModel):
    closure_id: str = Field(min_length=1, max_length=128)
    graph: ClosureGraph


class RevisionEvent(_StrictModel):
    event_id: str = Field(min_length=1, max_length=192)
    correction_evidence_id: str = Field(min_length=1, max_length=96)
    invalidated_evidence_ids: list[str] = Field(min_length=1, max_length=MAX_EVIDENCE)
    stable_evidence_ids: list[str] = Field(min_length=1, max_length=MAX_EVIDENCE)


class LiveRevisionRequest(_StrictModel):
    schema_version: Literal[REQUEST_SCHEMA]
    request_id: str = Field(min_length=8, max_length=128)
    case_id: str = Field(min_length=1, max_length=192)
    checkpoint_id: str = Field(min_length=1, max_length=192)
    question: str = Field(min_length=1, max_length=8192)
    answer_choices: list[str] = Field(min_length=1, max_length=32)
    decision_slots: list[DecisionSlot] = Field(min_length=1, max_length=MAX_SLOTS)
    all_raw_evidence: list[EvidenceItem] = Field(min_length=2, max_length=MAX_EVIDENCE)
    before_horizon_evidence_ids: list[str] = Field(min_length=1, max_length=MAX_EVIDENCE)
    prior_public_state: PriorPublicState
    prior_closure: ClosureGraph
    candidate_closures: list[ClosureCandidate] = Field(min_length=2, max_length=MAX_CANDIDATES)
    event: RevisionEvent
    reinspection_count: int = Field(ge=1, le=8)

    @model_validator(mode="after")
    def validate_cross_fields(self) -> "LiveRevisionRequest":
        _validate_request_cross_fields(self)
        return self


class LiveProviderOutput(_StrictModel):
    schema_version: Literal[PROVIDER_OUTPUT_SCHEMA]
    checkpoint_id: str = Field(min_length=1, max_length=192)
    current_answer: str = Field(min_length=1, max_length=256)
    selected_closure_id: str = Field(min_length=1, max_length=128)
    target_values: list[TargetValue] = Field(min_length=1, max_length=MAX_SLOTS)


def _slot_map(request: LiveRevisionRequest) -> dict[str, DecisionSlot]:
    return {row.slot_id: row for row in request.decision_slots}


def _expected_target_ids(request: LiveRevisionRequest) -> set[str]:
    return {f"{row.target_type}:{row.slot_id}" for row in request.decision_slots}


def _validate_graph(
    graph: ClosureGraph,
    *,
    evidence_order: Sequence[str],
    slots: Mapping[str, DecisionSlot],
    label: str,
) -> None:
    evidence_set = set(evidence_order)
    ordinal = {evidence_id: index for index, evidence_id in enumerate(evidence_order)}
    supports: dict[str, SupportNode] = {}
    for row in graph.support_nodes:
        _require(row.support_id not in supports, "SUPPORT_ID_DUPLICATE", f"{label}.{row.support_id}")
        ids = _unique_nonempty(row.evidence_ids, label=f"{label}.{row.support_id}.evidence_ids")
        _require(set(ids) <= evidence_set, "SUPPORT_EVIDENCE_OUTSIDE_HORIZON", row.support_id)
        supports[row.support_id] = row

    targets: dict[str, ClosureTarget] = {}
    for row in graph.targets:
        _require(row.target_id not in targets, "TARGET_ID_DUPLICATE", f"{label}.{row.target_id}")
        _require(row.slot in slots, "TARGET_SLOT_UNKNOWN", row.slot)
        slot = slots[row.slot]
        _require(
            row.target_type == slot.target_type
            and row.target_id == f"{slot.target_type}:{row.slot}",
            "TARGET_TYPE_SLOT_MISMATCH",
            row.target_id,
        )
        direct = _unique_nonempty(row.direct_support_ids, label=f"{label}.{row.target_id}.direct")
        _require(set(direct) <= set(supports), "TARGET_SUPPORT_UNKNOWN", row.target_id)
        _require(
            len(row.depends_on_target_ids) == len(set(row.depends_on_target_ids)),
            "TARGET_DEPENDENCY_DUPLICATE",
            row.target_id,
        )
        targets[row.target_id] = row
    expected_targets = {f"{row.target_type}:{row.slot_id}" for row in slots.values()}
    _require(set(targets) == expected_targets, "TARGET_SET_MISMATCH", label)
    used_supports = {
        support_id for target in targets.values() for support_id in target.direct_support_ids
    }
    _require(used_supports == set(supports), "ORPHAN_SUPPORT_NODE", label)

    indegree = {target_id: 0 for target_id in targets}
    adjacency = {target_id: [] for target_id in targets}
    for target_id, row in targets.items():
        for upstream in row.depends_on_target_ids:
            _require(upstream in targets and upstream != target_id, "TARGET_DEPENDENCY_UNKNOWN", target_id)
            _require(
                row.target_type == targets[upstream].target_type == "fact",
                "TARGET_DEPENDENCY_TYPE_FORBIDDEN",
                target_id,
            )
            indegree[target_id] += 1
            adjacency[upstream].append(target_id)
    queue = sorted(target_id for target_id, degree in indegree.items() if degree == 0)
    visited: list[str] = []
    while queue:
        target_id = queue.pop(0)
        visited.append(target_id)
        for downstream in sorted(adjacency[target_id]):
            indegree[downstream] -= 1
            if indegree[downstream] == 0:
                queue.append(downstream)
                queue.sort()
    _require(len(visited) == len(targets), "TARGET_DEPENDENCY_CYCLE", label)

    seen_edges: set[tuple[str, str]] = set()
    invalidated: set[str] = set()
    for edge in graph.invalidation_edges:
        pair = (edge.source_evidence_id, edge.target_evidence_id)
        _require(pair not in seen_edges, "INVALIDATION_DUPLICATE", label)
        _require(set(pair) <= evidence_set, "INVALIDATION_EVIDENCE_UNKNOWN", label)
        _require(ordinal[pair[0]] > ordinal[pair[1]], "INVALIDATION_TEMPORAL_ORDER", label)
        seen_edges.add(pair)
        invalidated.add(pair[1])
    active = {
        evidence_id
        for support in supports.values()
        for evidence_id in support.evidence_ids
    }
    _require(not (active & invalidated), "INVALIDATED_SUPPORT_ACTIVE", label)


def _structural_closure(
    graph: ClosureGraph,
    *,
    evidence_order: Sequence[str],
    blocked_evidence_ids: frozenset[str] = frozenset(),
) -> JsonObject:
    supports = {row.support_id: row for row in graph.support_nodes}
    targets = {row.target_id: row for row in graph.targets}
    indegree = {target_id: 0 for target_id in targets}
    adjacency = {target_id: [] for target_id in targets}
    for target_id, row in targets.items():
        for upstream in row.depends_on_target_ids:
            indegree[target_id] += 1
            adjacency[upstream].append(target_id)
    queue = sorted(target_id for target_id, degree in indegree.items() if degree == 0)
    order: list[str] = []
    while queue:
        target_id = queue.pop(0)
        order.append(target_id)
        for downstream in sorted(adjacency[target_id]):
            indegree[downstream] -= 1
            if indegree[downstream] == 0:
                queue.append(downstream)
                queue.sort()
    _require(len(order) == len(targets), "TARGET_DEPENDENCY_CYCLE")
    direct: dict[str, set[str]] = {}
    inherited: dict[str, set[str]] = {}
    total: dict[str, set[str]] = {}
    for target_id in order:
        row = targets[target_id]
        direct_set = {
            evidence_id
            for support_id in row.direct_support_ids
            for evidence_id in supports[support_id].evidence_ids
            if evidence_id not in blocked_evidence_ids
        }
        ancestor = {
            evidence_id
            for upstream in row.depends_on_target_ids
            for evidence_id in total[upstream]
        }
        direct[target_id] = direct_set
        inherited[target_id] = ancestor - direct_set
        total[target_id] = direct_set | ancestor
    retained_invalidation_edges = [
        row
        for row in graph.invalidation_edges
        if row.source_evidence_id not in blocked_evidence_ids
        and row.target_evidence_id not in blocked_evidence_ids
    ]
    invalidated = {row.target_evidence_id for row in retained_invalidation_edges}
    active = {item for values in total.values() for item in values}
    _require(not (active & invalidated), "INVALIDATED_SUPPORT_ACTIVE")
    ordinal = {evidence_id: index for index, evidence_id in enumerate(evidence_order)}
    return {
        "active_support_evidence_ids": sorted(active, key=ordinal.__getitem__),
        "invalidated_evidence_ids": sorted(invalidated, key=ordinal.__getitem__),
        "invalidation_edges": sorted(
            (row.model_dump(mode="json") for row in retained_invalidation_edges),
            key=lambda row: (row["source_evidence_id"], row["target_evidence_id"]),
        ),
        "targets": {
            target_id: {
                "direct_active_evidence_ids": sorted(direct[target_id], key=ordinal.__getitem__),
                "inherited_active_evidence_ids": sorted(inherited[target_id], key=ordinal.__getitem__),
                "all_active_evidence_ids": sorted(total[target_id], key=ordinal.__getitem__),
            }
            for target_id in sorted(targets)
        },
    }


def _canonical_graph_value(graph: ClosureGraph) -> JsonObject:
    """Normalize every graph collection whose order has no contract meaning."""
    support_nodes = [
        {
            "support_id": row.support_id,
            "evidence_ids": sorted(row.evidence_ids),
        }
        for row in graph.support_nodes
    ]
    support_nodes.sort(
        key=lambda row: (row["support_id"], tuple(row["evidence_ids"]))
    )
    targets = [
        {
            "target_id": row.target_id,
            "target_type": row.target_type,
            "slot": row.slot,
            "direct_support_ids": sorted(row.direct_support_ids),
            "depends_on_target_ids": sorted(row.depends_on_target_ids),
        }
        for row in graph.targets
    ]
    targets.sort(key=lambda row: row["target_id"])
    invalidation_edges = sorted(
        (row.model_dump(mode="json") for row in graph.invalidation_edges),
        key=lambda row: (row["source_evidence_id"], row["target_evidence_id"]),
    )
    return {
        "support_nodes": support_nodes,
        "targets": targets,
        "invalidation_edges": invalidation_edges,
    }


def _eligible_reinspection_evidence_ids(
    request: LiveRevisionRequest,
) -> list[str]:
    """Return the frozen public allocation domain in chronological order."""

    invalidated = set(request.event.invalidated_evidence_ids)
    stable = set(request.event.stable_evidence_ids)
    candidate_active: set[str] = set()
    evidence_order = [row.evidence_id for row in request.all_raw_evidence]
    for candidate in request.candidate_closures:
        closure = _structural_closure(candidate.graph, evidence_order=evidence_order)
        candidate_active.update(closure["active_support_evidence_ids"])
    return [
        evidence_id
        for evidence_id in evidence_order
        if evidence_id in candidate_active
        and evidence_id not in invalidated
        and evidence_id not in stable
    ]


def _validate_request_cross_fields(request: LiveRevisionRequest) -> None:
    answers = _unique_nonempty(request.answer_choices, label="answer_choices")
    _require(
        all(len(value) <= 256 for value in answers),
        "ANSWER_CHOICE_TOO_LONG",
    )
    slot_ids = [row.slot_id for row in request.decision_slots]
    _unique_nonempty(slot_ids, label="decision_slots")
    for row in request.decision_slots:
        values = _unique_nonempty(row.allowed_values, label=f"slot.{row.slot_id}.allowed_values")
        _require(all(len(value) <= 256 for value in values), "SLOT_VALUE_TOO_LONG", row.slot_id)
    _require(
        any(row.target_type == "fact" for row in request.decision_slots),
        "FACT_TARGET_REQUIRED",
    )

    evidence_ids = [row.evidence_id for row in request.all_raw_evidence]
    _unique_nonempty(evidence_ids, label="all_raw_evidence")
    before_ids = list(_unique_nonempty(request.before_horizon_evidence_ids, label="before_horizon"))
    _require(set(before_ids) < set(evidence_ids), "BEFORE_HORIZON_MUST_BE_PROPER_SUBSET")
    positions = [evidence_ids.index(item) for item in before_ids if item in set(evidence_ids)]
    _require(len(positions) == len(before_ids), "BEFORE_EVIDENCE_UNKNOWN")
    _require(positions == sorted(positions), "BEFORE_HORIZON_ORDER_DRIFT")

    event = request.event
    _unique_nonempty(event.invalidated_evidence_ids, label="event.invalidated_evidence_ids")
    _unique_nonempty(event.stable_evidence_ids, label="event.stable_evidence_ids")
    _require(event.correction_evidence_id in evidence_ids, "CORRECTION_EVIDENCE_UNKNOWN")
    _require(event.correction_evidence_id not in set(before_ids), "CORRECTION_ALREADY_IN_BEFORE")
    correction_position = evidence_ids.index(event.correction_evidence_id)
    _require(
        before_ids == evidence_ids[:correction_position],
        "BEFORE_HORIZON_MUST_BE_EXACT_PRE_EVENT_PREFIX",
    )
    _require(
        correction_position == len(evidence_ids) - 1,
        "CORRECTION_MUST_TERMINATE_VISIBLE_HORIZON",
    )
    _require(
        set(event.invalidated_evidence_ids) <= set(before_ids),
        "INVALIDATED_EVIDENCE_NOT_IN_BEFORE",
    )
    _require(
        set(event.stable_evidence_ids) <= set(before_ids),
        "STABLE_EVIDENCE_NOT_IN_BEFORE",
    )
    _require(
        not (set(event.invalidated_evidence_ids) & set(event.stable_evidence_ids)),
        "EVENT_INVALIDATED_STABLE_OVERLAP",
    )
    _require(
        all(correction_position > evidence_ids.index(item) for item in event.invalidated_evidence_ids),
        "CORRECTION_NOT_LATER_THAN_INVALIDATED",
    )

    slots = _slot_map(request)
    values = request.prior_public_state.target_values
    _require(len(values) == len(slots), "PRIOR_TARGET_COUNT_MISMATCH")
    value_by_id: dict[str, TargetValue] = {}
    for row in values:
        _require(row.target_id not in value_by_id, "PRIOR_TARGET_DUPLICATE", row.target_id)
        _require(row.slot in slots, "PRIOR_TARGET_SLOT_UNKNOWN", row.slot)
        spec = slots[row.slot]
        _require(
            row.target_type == spec.target_type
            and row.target_id == f"{spec.target_type}:{row.slot}",
            "PRIOR_TARGET_TYPE_MISMATCH",
            row.target_id,
        )
        _require(row.value in spec.allowed_values, "PRIOR_TARGET_VALUE_OUTSIDE_DOMAIN", row.target_id)
        value_by_id[row.target_id] = row
    _require(set(value_by_id) == _expected_target_ids(request), "PRIOR_TARGET_SET_MISMATCH")
    _require(
        request.prior_public_state.current_answer in request.answer_choices,
        "PRIOR_ANSWER_OUTSIDE_DOMAIN",
    )

    _validate_graph(
        request.prior_closure,
        evidence_order=before_ids,
        slots=slots,
        label="prior_closure",
    )
    prior_lineage = _structural_closure(
        request.prior_closure,
        evidence_order=before_ids,
    )
    prior_active = set(prior_lineage["active_support_evidence_ids"])
    prior_edges = {
        (row["source_evidence_id"], row["target_evidence_id"])
        for row in prior_lineage["invalidation_edges"]
    }
    _require(
        set(event.invalidated_evidence_ids) <= prior_active,
        "INVALIDATED_EVIDENCE_NOT_ACTIVE_BEFORE",
    )
    _require(
        set(event.stable_evidence_ids) <= prior_active,
        "STABLE_EVIDENCE_NOT_ACTIVE_BEFORE",
    )
    candidate_ids = [row.closure_id for row in request.candidate_closures]
    _unique_nonempty(candidate_ids, label="candidate_closures")
    candidate_graph_fingerprints = [
        _fingerprint(_canonical_graph_value(row.graph))
        for row in request.candidate_closures
    ]
    _require(
        len(candidate_graph_fingerprints) == len(set(candidate_graph_fingerprints)),
        "CANDIDATE_GRAPH_DUPLICATE",
    )
    full_order = evidence_ids
    event_edges = {
        (event.correction_evidence_id, target)
        for target in event.invalidated_evidence_ids
    }
    exact_after_edges = prior_edges | event_edges
    operational_candidate_exists = False
    enough_rankable: set[str] = set()
    for candidate in request.candidate_closures:
        _validate_graph(
            candidate.graph,
            evidence_order=full_order,
            slots=slots,
            label=f"candidate.{candidate.closure_id}",
        )
        closure = _structural_closure(candidate.graph, evidence_order=full_order)
        observed_edges = {
            (row["source_evidence_id"], row["target_evidence_id"])
            for row in closure["invalidation_edges"]
        }
        active = set(closure["active_support_evidence_ids"])
        correction_fact_bound = any(
            event.correction_evidence_id
            in set(lineage["all_active_evidence_ids"])
            for target_id, lineage in closure["targets"].items()
            if target_id.startswith("fact:")
        )
        if (
            event.correction_evidence_id in active
            and not (active & set(event.invalidated_evidence_ids))
            and observed_edges == exact_after_edges
            and correction_fact_bound
        ):
            operational_candidate_exists = True
        enough_rankable.update(
            active - set(event.invalidated_evidence_ids) - set(event.stable_evidence_ids)
        )
    _require(operational_candidate_exists, "NO_EVENT_CONSISTENT_CANDIDATE")
    _require(
        len(enough_rankable) >= max(request.reinspection_count, 2),
        "CONTINUOUS_ALLOCATION_DOMAIN_TOO_SMALL",
    )


def validate_request_mapping(value: Any) -> LiveRevisionRequest:
    _require(isinstance(value, Mapping), "REQUEST_ROOT_NOT_OBJECT", http_status=400)
    forbidden = _recursive_keys(value) & FORBIDDEN_REQUEST_KEYS
    _require(
        not forbidden,
        "FORBIDDEN_REQUEST_KEY",
        ",".join(sorted(forbidden)),
        http_status=400,
    )
    try:
        return LiveRevisionRequest.model_validate(value)
    except LiveRevisionError:
        raise
    except ValidationError as error:
        raise LiveRevisionError("REQUEST_SCHEMA_INVALID", http_status=422) from error


def _validate_public_output(
    request: LiveRevisionRequest,
    output: Mapping[str, Any],
    *,
    expected_checkpoint_id: str,
    allowed_closure_ids: set[str],
    require_live_schema: bool,
    failure_http_status: int,
) -> JsonObject:
    def output_require(
        condition: bool, reason_code: str, detail: str | None = None
    ) -> None:
        _require(
            condition,
            reason_code,
            detail,
            http_status=failure_http_status,
        )

    expected_keys = {
        "schema_version",
        "checkpoint_id",
        "current_answer",
        "selected_closure_id",
        "target_values",
    }
    output_require(set(output) == expected_keys, "OUTPUT_SCHEMA_INVALID")
    if require_live_schema:
        output_require(
            output["schema_version"] == PROVIDER_OUTPUT_SCHEMA,
            "OUTPUT_SCHEMA_VERSION_INVALID",
        )
    output_require(
        output["checkpoint_id"] == expected_checkpoint_id,
        "OUTPUT_CHECKPOINT_MISMATCH",
    )
    output_require(
        output["current_answer"] in request.answer_choices,
        "OUTPUT_ANSWER_OUTSIDE_DOMAIN",
    )
    output_require(
        output["selected_closure_id"] in allowed_closure_ids,
        "OUTPUT_CLOSURE_UNKNOWN",
    )
    rows = output["target_values"]
    output_require(
        isinstance(rows, list) and len(rows) == len(request.decision_slots),
        "OUTPUT_TARGET_COUNT_INVALID",
    )
    slots = _slot_map(request)
    normalized_rows: list[JsonObject] = []
    seen: set[str] = set()
    for raw in rows:
        output_require(isinstance(raw, Mapping), "OUTPUT_TARGET_NOT_OBJECT")
        output_require(
            set(raw) == {"target_id", "target_type", "slot", "value"},
            "OUTPUT_TARGET_SCHEMA_INVALID",
        )
        row = TargetValue.model_validate(raw)
        output_require(
            row.target_id not in seen, "OUTPUT_TARGET_DUPLICATE", row.target_id
        )
        output_require(row.slot in slots, "OUTPUT_TARGET_SLOT_UNKNOWN", row.slot)
        spec = slots[row.slot]
        output_require(
            row.target_type == spec.target_type
            and row.target_id == f"{spec.target_type}:{row.slot}",
            "OUTPUT_TARGET_TYPE_MISMATCH",
            row.target_id,
        )
        output_require(
            row.value in spec.allowed_values,
            "OUTPUT_TARGET_VALUE_OUTSIDE_DOMAIN",
            row.target_id,
        )
        seen.add(row.target_id)
        normalized_rows.append(row.model_dump(mode="json"))
    output_require(
        seen == _expected_target_ids(request), "OUTPUT_TARGET_SET_MISMATCH"
    )
    normalized = {
        "schema_version": str(output["schema_version"]),
        "checkpoint_id": str(output["checkpoint_id"]),
        "current_answer": str(output["current_answer"]),
        "selected_closure_id": str(output["selected_closure_id"]),
        "target_values": sorted(normalized_rows, key=lambda row: row["target_id"]),
    }
    return normalized


def _compile_output(
    request: LiveRevisionRequest,
    output: Mapping[str, Any],
    graph: ClosureGraph,
    *,
    phase_id: Literal["before_event", "after_event"],
    evidence_order: Sequence[str],
    allowed_closure_ids: set[str],
    require_live_schema: bool,
) -> JsonObject:
    expected_checkpoint = (
        request.prior_public_state.checkpoint_id
        if phase_id == "before_event"
        else request.checkpoint_id
    )
    normalized = _validate_public_output(
        request,
        output,
        expected_checkpoint_id=expected_checkpoint,
        allowed_closure_ids=allowed_closure_ids,
        require_live_schema=require_live_schema,
        failure_http_status=502 if phase_id == "after_event" else 422,
    )
    closure = _structural_closure(graph, evidence_order=evidence_order)
    value_by_id = {row["target_id"]: row for row in normalized["target_values"]}
    target_specs = {row.target_id: row for row in graph.targets}
    targets: list[JsonObject] = []
    for target_id in sorted(target_specs):
        spec = target_specs[target_id]
        value = value_by_id[target_id]
        lineage = closure["targets"][target_id]
        targets.append(
            {
                "target_id": target_id,
                "target_type": spec.target_type,
                "slot": spec.slot,
                "value": value["value"],
                **_clone(lineage),
            }
        )
    return _seal(
        {
            "schema_version": COMPILED_SCHEMA,
            "phase_id": phase_id,
            "checkpoint_id": normalized["checkpoint_id"],
            "current_answer": normalized["current_answer"],
            "selected_closure_id": normalized["selected_closure_id"],
            "source_horizon_evidence_ids": list(evidence_order),
            "active_support_evidence_ids": closure["active_support_evidence_ids"],
            "invalidated_evidence_ids": closure["invalidated_evidence_ids"],
            "invalidation_edges": closure["invalidation_edges"],
            "targets": targets,
            "normalized_output": normalized,
            "normalized_output_fingerprint_sha256": _fingerprint(normalized),
        }
    )


def _actual_before_state(
    request: LiveRevisionRequest, compiled_before: Mapping[str, Any]
) -> tuple[float, JsonObject]:
    active_before = set(compiled_before["active_support_evidence_ids"])
    invalidated = set(request.event.invalidated_evidence_ids)
    stable = set(request.event.stable_evidence_ids)
    correction_present = float(
        request.event.correction_evidence_id in active_before
    )
    invalidated_absent_fraction = 1.0 - (
        len(active_before & invalidated) / len(invalidated)
    )
    stable_present_fraction = len(active_before & stable) / len(stable)
    components: list[JsonObject] = [
        {
            "axis": "correction_evidence_present",
            "coordinate": correction_present,
        },
        {
            "axis": "invalidated_evidence_absent_fraction",
            "coordinate": invalidated_absent_fraction,
        },
        {
            "axis": "stable_evidence_present_fraction",
            "coordinate": stable_present_fraction,
            "diagnostic_only": True,
        },
    ]
    scalar = (correction_present + invalidated_absent_fraction) / 2.0
    initial_vector = [
        correction_present,
        invalidated_absent_fraction,
        stable_present_fraction,
    ]
    state = _seal(
        {
            "schema_version": ACTUAL_STATE_SCHEMA,
            "source_compiled_fingerprint_sha256": compiled_before["fingerprint_sha256"],
            "source_selected_closure_id": compiled_before["selected_closure_id"],
            "active_support_evidence_ids": list(compiled_before["active_support_evidence_ids"]),
            "components": components,
            "initial_scalar": scalar,
            "initial_vector": initial_vector,
            "axis_order": list(TRAJECTORY_AXES),
            "coordinate_semantics": "STRUCTURAL_REVISION_READINESS_ENUM_ORDER_INVARIANT",
        }
    )
    return scalar, state


def _public_incidence_effects(request: LiveRevisionRequest) -> tuple[dict[str, float], JsonObject]:
    evidence_ids = [row.evidence_id for row in request.all_raw_evidence]
    direct_hits: defaultdict[str, int] = defaultdict(int)
    inherited_hits: defaultdict[str, int] = defaultdict(int)
    for candidate in request.candidate_closures:
        closure = _structural_closure(candidate.graph, evidence_order=evidence_ids)
        for lineage in closure["targets"].values():
            for evidence_id in lineage["direct_active_evidence_ids"]:
                direct_hits[evidence_id] += 1
            for evidence_id in lineage["inherited_active_evidence_ids"]:
                inherited_hits[evidence_id] += 1
    scores = {
        evidence_id: float(
            2 * direct_hits[evidence_id] + inherited_hits[evidence_id]
        )
        for evidence_id in evidence_ids
    }
    maximum = max(scores.values(), default=0.0)
    _require(maximum > 0.0 and math.isfinite(maximum), "INCIDENCE_EFFECT_BASIS_ZERO")
    effects = {
        evidence_id: (
            1.0
            if evidence_id == request.event.correction_evidence_id
            else float(scores[evidence_id] / maximum)
        )
        for evidence_id in evidence_ids
    }
    receipt = _seal(
        {
            "schema_version": "ebrt-live-public-incidence-basis-v0.6.2.5",
            "source_kind": "ROLE_BLIND_GRAPH_INCIDENCE_PLUS_EXPLICIT_TYPED_CORRECTION",
            "candidate_graph_fingerprints_sha256": sorted(
                _fingerprint(_canonical_graph_value(candidate.graph))
                for candidate in request.candidate_closures
            ),
            "event_fingerprint_sha256": _fingerprint(request.event.model_dump(mode="json")),
            "direct_target_incidence_by_evidence_id": {
                evidence_id: direct_hits[evidence_id] for evidence_id in evidence_ids
            },
            "inherited_target_incidence_by_evidence_id": {
                evidence_id: inherited_hits[evidence_id] for evidence_id in evidence_ids
            },
            "raw_score_by_evidence_id": scores,
            "normalized_effect_by_evidence_id": effects,
            "correction_override": {
                "evidence_id": request.event.correction_evidence_id,
                "normalized_effect": 1.0,
                "semantic_role": "TYPED_EVENT_BOUNDARY_NOT_GOLD",
            },
            "reserved_gold_fields_participated": False,
            "caller_semantic_content_verified": False,
        }
    )
    return effects, receipt


def _full_admission_support_envelope(
    effects: torch.Tensor,
    eligibility: torch.Tensor,
    *,
    initial_support: torch.Tensor,
) -> torch.Tensor:
    state = initial_support
    rows: list[torch.Tensor] = []
    for index, effect in enumerate(effects):
        decayed = STATE_DECAY * state
        support_effect = torch.where(
            eligibility[index], effect, torch.zeros_like(effect)
        )
        state = 1.0 - (1.0 - decayed) * (1.0 - support_effect)
        rows.append(state)
    return torch.stack(rows)


def _unmodified_forward_trajectory(
    initial_state: torch.Tensor, *, steps: int
) -> torch.Tensor:
    """Run the frozen public recurrence without admitting any event proposal."""

    _require(
        initial_state.shape == (len(TRAJECTORY_AXES),) and steps > 0,
        "UNMODIFIED_FORWARD_SHAPE_INVALID",
    )
    state = initial_state
    rows: list[torch.Tensor] = []
    for _ in range(steps):
        state = torch.stack(
            (
                STATE_DECAY * state[0],
                STATE_DECAY * state[1],
                state[2],
            )
        )
        rows.append(state)
    return torch.stack(rows)


def _controller_loss(
    controls: torch.Tensor,
    effects: torch.Tensor,
    eligibility: torch.Tensor,
    *,
    initial_state: torch.Tensor,
    correction_index: int,
) -> tuple[torch.Tensor, torch.Tensor, dict[str, torch.Tensor]]:
    _require(bool(torch.any(eligibility)), "CONTINUOUS_ALLOCATION_DOMAIN_EMPTY")
    _require(
        controls.ndim == effects.ndim == eligibility.ndim == 1
        and controls.shape == effects.shape == eligibility.shape
        and len(controls) > 1
        and initial_state.shape == (len(TRAJECTORY_AXES),)
        and 0 <= correction_index < len(controls),
        "PUBLIC_TRAJECTORY_SHAPE_INVALID",
    )
    admitted_controls = controls * eligibility.to(dtype=controls.dtype)
    state = initial_state
    states: list[torch.Tensor] = []
    for index, effect in enumerate(effects):
        decayed = torch.stack(
            (
                STATE_DECAY * state[0],
                STATE_DECAY * state[1],
                state[2],
            )
        )
        support_effect = torch.where(
            eligibility[index], effect, torch.zeros_like(effect)
        )
        support_proposal = 1.0 - (1.0 - decayed[0]) * (
            1.0 - support_effect
        )
        invalidation_proposal = torch.where(
            torch.tensor(index == correction_index, dtype=torch.bool),
            torch.ones((), dtype=controls.dtype, device=controls.device),
            decayed[1],
        )
        proposal = torch.stack(
            (support_proposal, invalidation_proposal, initial_state[2])
        )
        # A bounded residual gate keeps the origin literal: u_t == 0 admits
        # none of the event-bearing proposal.  The existing global L2 budget
        # bounds every accepted coordinate to |u_t| <= MAX_CONTROL_L2.
        residual_gate = admitted_controls[index]
        state = decayed + residual_gate * (proposal - decayed)
        states.append(state)
    trajectory = torch.stack(states)
    target = torch.stack(
        (
            torch.ones((), dtype=controls.dtype, device=controls.device),
            torch.ones((), dtype=controls.dtype, device=controls.device),
            initial_state[2],
        )
    )
    terminal_loss = 0.5 * (trajectory[-1] - target).square().sum()
    support_envelope = _full_admission_support_envelope(
        effects,
        eligibility,
        initial_support=initial_state[0],
    )
    path_loss = (
        trajectory[:-1, 0] - support_envelope[:-1]
    ).square().mean()
    control_loss = CONTROL_REGULARIZATION * admitted_controls.square().sum()
    eligible_controls = admitted_controls[eligibility]
    smoothness_loss = TEMPORAL_SMOOTHNESS_REGULARIZATION * (
        eligible_controls[1:] - eligible_controls[:-1]
    ).square().sum()
    loss = (
        terminal_loss
        + TRAJECTORY_PATH_REGULARIZATION * path_loss
        + control_loss
        + smoothness_loss
    )
    return loss, trajectory, {
        "terminal": terminal_loss,
        "path": path_loss,
        "control": control_loss,
        "smoothness": smoothness_loss,
    }


def _masked_allocation(
    controls: torch.Tensor, eligibility: torch.Tensor
) -> torch.Tensor:
    logits = (controls.abs() / INSPECTION_TEMPERATURE).masked_fill(
        ~eligibility, -torch.inf
    )
    return torch.softmax(logits, dim=0)


def _trajectory_points(
    *,
    evidence_ids: Sequence[str],
    states: torch.Tensor,
    controls: torch.Tensor,
    gradients: torch.Tensor,
    eligibility: torch.Tensor,
    correction_index: int,
    support_envelope: torch.Tensor,
) -> list[JsonObject]:
    return [
        _seal(
            {
                "step_index": index,
                "evidence_id": evidence_id,
                "is_correction_event": index == correction_index,
                "eligible_for_temporal_control": bool(eligibility[index]),
                "state": [float(value) for value in states[index].detach()],
                "full_admission_support_reference": float(
                    support_envelope[index].detach()
                ),
                "control_value": float(controls[index]),
                "temporal_gradient": float(gradients[index]),
            }
        )
        for index, evidence_id in enumerate(evidence_ids)
    ]


def _loss_components_value(
    components: Mapping[str, torch.Tensor],
) -> JsonObject:
    return {
        key: float(value.detach()) for key, value in components.items()
    }


def _matched_temporal_sham(
    controls: torch.Tensor, eligibility: torch.Tensor
) -> torch.Tensor:
    """Reverse accepted values over the eligible temporal-control domain."""

    eligible_indices = torch.nonzero(eligibility).flatten()
    sham = controls.clone()
    sham[eligible_indices] = torch.flip(controls[eligible_indices], dims=(0,))
    return sham


def _temporal_sham_diagnostic(
    *,
    accepted: torch.Tensor,
    accepted_loss: torch.Tensor,
    accepted_components: Mapping[str, torch.Tensor],
    sham: torch.Tensor,
    sham_loss: torch.Tensor,
    sham_components: Mapping[str, torch.Tensor],
    eligibility: torch.Tensor,
) -> JsonObject:
    """Seal a local contrast without turning its outcome into a product gate."""

    accepted_values = [float(value) for value in accepted[eligibility]]
    sham_values = [float(value) for value in sham[eligibility]]
    accepted_l2 = float(torch.linalg.vector_norm(accepted))
    sham_l2 = float(torch.linalg.vector_norm(sham))
    checks = {
        "signed_value_multiset_matched": sorted(accepted_values)
        == sorted(sham_values),
        "control_l2_matched": abs(accepted_l2 - sham_l2)
        <= SHAM_GEOMETRY_TOLERANCE,
        "control_regularization_matched": abs(
            float(accepted_components["control"].detach())
            - float(sham_components["control"].detach())
        )
        <= SHAM_GEOMETRY_TOLERANCE,
        "eligible_temporal_smoothness_matched": abs(
            float(accepted_components["smoothness"].detach())
            - float(sham_components["smoothness"].detach())
        )
        <= SHAM_GEOMETRY_TOLERANCE,
        "sham_is_distinct": not torch.equal(accepted, sham),
    }
    geometry_valid = all(
        checks[key]
        for key in (
            "signed_value_multiset_matched",
            "control_l2_matched",
            "control_regularization_matched",
            "eligible_temporal_smoothness_matched",
        )
    )
    exact_objective = float(accepted_loss.detach())
    sham_objective = float(sham_loss.detach())
    exact_beats = exact_objective + 1.0e-12 < sham_objective
    if not geometry_valid:
        status = "INVALID_GEOMETRY"
    elif not checks["sham_is_distinct"]:
        status = "UNAVAILABLE_DEGENERATE"
    else:
        status = "POSITIVE" if exact_beats else "NON_POSITIVE"
    return _seal(
        {
            "schema_version": "ebrt-live-temporal-sham-diagnostic-v0.6.2.5",
            "status": status,
            "construction": "REVERSE_ACCEPTED_CONTROL_VALUES_OVER_ELIGIBLE_TIME_SITES",
            "smoothness_domain": "ADJACENT_ELIGIBLE_TEMPORAL_CONTROL_SITES",
            "exact_objective": exact_objective,
            "sham_objective": sham_objective,
            "objective_margin_sham_minus_exact": sham_objective
            - exact_objective,
            "exact_temporal_placement_beats_matched_sham": exact_beats,
            "exact_control_l2": accepted_l2,
            "sham_control_l2": sham_l2,
            "checks": checks,
            "provider_calls": 0,
            "product_gate_participation": False,
            "claim_scope": "LOCAL_PUBLIC_SURROGATE_ONLY",
        }
    )


def _derive_control_map(
    request: LiveRevisionRequest, compiled_before: Mapping[str, Any]
) -> JsonObject:
    evidence_ids = [row.evidence_id for row in request.all_raw_evidence]
    _, actual_state = _actual_before_state(request, compiled_before)
    effect_by_id, source_receipt = _public_incidence_effects(request)
    effects = torch.tensor([effect_by_id[item] for item in evidence_ids], dtype=FLOAT_DTYPE)
    eligible_ids = set(_eligible_reinspection_evidence_ids(request))
    eligibility = torch.tensor(
        [evidence_id in eligible_ids for evidence_id in evidence_ids],
        dtype=torch.bool,
    )
    _require(
        int(eligibility.sum().item()) >= max(request.reinspection_count, 2),
        "CONTINUOUS_ALLOCATION_DOMAIN_TOO_SMALL",
    )
    correction_index = evidence_ids.index(request.event.correction_evidence_id)
    initial_state = torch.tensor(
        actual_state["initial_vector"], dtype=FLOAT_DTYPE
    )
    controls = torch.zeros(len(evidence_ids), dtype=FLOAT_DTYPE, requires_grad=True)
    loss_before, states_before, components_before = _controller_loss(
        controls,
        effects,
        eligibility,
        initial_state=initial_state,
        correction_index=correction_index,
    )
    loss_before.backward()
    _require(controls.grad is not None, "BACKWARD_GRADIENT_MISSING")
    gradient = controls.grad.detach().clone()
    _require(bool(torch.all(torch.isfinite(gradient))), "NONFINITE_GRADIENT")
    raw_displacement = -STEP_SIZE * gradient
    raw_norm = float(torch.linalg.vector_norm(raw_displacement))
    _require(math.isfinite(raw_norm) and raw_norm > 0.0, "NEUTRAL_CONTROL_MAP")
    budget_scale = min(1.0, MAX_CONTROL_L2 / raw_norm)
    bounded = raw_displacement * budget_scale

    accepted: torch.Tensor | None = None
    accepted_states: torch.Tensor | None = None
    accepted_loss: torch.Tensor | None = None
    accepted_components: dict[str, torch.Tensor] | None = None
    accepted_backtrack = -1
    for backtrack in range(MAX_BACKTRACKS + 1):
        candidate = bounded * (0.5**backtrack)
        candidate_loss, candidate_states, candidate_components = _controller_loss(
            candidate,
            effects,
            eligibility,
            initial_state=initial_state,
            correction_index=correction_index,
        )
        if float(candidate_loss.detach()) < float(loss_before.detach()):
            accepted = candidate
            accepted_states = candidate_states
            accepted_loss = candidate_loss
            accepted_components = candidate_components
            accepted_backtrack = backtrack
            break
    _require(accepted is not None, "SURROGATE_NO_DESCENT")
    assert (
        accepted_states is not None
        and accepted_loss is not None
        and accepted_components is not None
    )

    allocation_before = _masked_allocation(
        torch.zeros_like(controls), eligibility
    )
    accepted_allocation = _masked_allocation(accepted, eligibility)

    epsilon = FINITE_DIFFERENCE_EPSILON
    finite_difference: list[float] = []
    for index in range(len(evidence_ids)):
        positive = torch.zeros(len(evidence_ids), dtype=FLOAT_DTYPE)
        negative = torch.zeros(len(evidence_ids), dtype=FLOAT_DTYPE)
        positive[index] = epsilon
        negative[index] = -epsilon
        plus, _, _ = _controller_loss(
            positive,
            effects,
            eligibility,
            initial_state=initial_state,
            correction_index=correction_index,
        )
        minus, _, _ = _controller_loss(
            negative,
            effects,
            eligibility,
            initial_state=initial_state,
            correction_index=correction_index,
        )
        finite_difference.append(float((plus - minus) / (2.0 * epsilon)))
    errors = [
        abs(float(gradient[index]) - finite_difference[index])
        for index in range(len(evidence_ids))
    ]
    norm = float(torch.linalg.vector_norm(accepted))
    sham = _matched_temporal_sham(accepted, eligibility)
    sham_loss, sham_states, sham_components = _controller_loss(
        sham,
        effects,
        eligibility,
        initial_state=initial_state,
        correction_index=correction_index,
    )
    sham_diagnostic = _temporal_sham_diagnostic(
        accepted=accepted,
        accepted_loss=accepted_loss,
        accepted_components=accepted_components,
        sham=sham,
        sham_loss=sham_loss,
        sham_components=sham_components,
        eligibility=eligibility,
    )
    replay_loss, replay_states, _ = _controller_loss(
        accepted,
        effects,
        eligibility,
        initial_state=initial_state,
        correction_index=correction_index,
    )
    active_before = set(compiled_before["active_support_evidence_ids"])
    support_envelope = _full_admission_support_envelope(
        effects,
        eligibility,
        initial_support=initial_state[0],
    )
    rows = [
        {
            "evidence_id": evidence_id,
            "source_effect": float(effects[index]),
            "gradient": float(gradient[index]),
            "finite_difference_gradient": finite_difference[index],
            "control_value": float(accepted[index]),
            "reinspection_salience": abs(float(accepted[index])),
            "temporal_step_index": index,
            "state_before": [
                float(value) for value in states_before[index].detach()
            ],
            "state_after": [
                float(value) for value in accepted_states[index].detach()
            ],
            "eligible_for_reinspection": evidence_id in eligible_ids,
            "baseline_allocation_fraction": float(
                allocation_before[index].detach()
            ),
            "optimized_allocation_fraction": float(
                accepted_allocation[index].detach()
            ),
            "allocation_delta": float(
                (accepted_allocation[index] - allocation_before[index]).detach()
            ),
            "surrogate_contribution_before": float(
                (allocation_before[index] * effects[index]).detach()
            ),
            "surrogate_contribution_after": float(
                (accepted_allocation[index] * effects[index]).detach()
            ),
            "active_before": evidence_id in active_before,
        }
        for index, evidence_id in enumerate(evidence_ids)
    ]
    neutral_points = _trajectory_points(
        evidence_ids=evidence_ids,
        states=states_before,
        controls=torch.zeros_like(controls),
        gradients=gradient,
        eligibility=eligibility,
        correction_index=correction_index,
        support_envelope=support_envelope,
    )
    revised_points = _trajectory_points(
        evidence_ids=evidence_ids,
        states=accepted_states,
        controls=accepted,
        gradients=gradient,
        eligibility=eligibility,
        correction_index=correction_index,
        support_envelope=support_envelope,
    )
    trajectory_checks = {
        "source_actual_before_state_bound": actual_state[
            "fingerprint_sha256"
        ]
        == _fingerprint(_without_fingerprint(actual_state)),
        "chronological_forward_exact": [
            row["evidence_id"] for row in revised_points
        ]
        == evidence_ids,
        "zero_control_is_exact_unmodified_forward": torch.equal(
            states_before,
            _unmodified_forward_trajectory(
                initial_state, steps=len(evidence_ids)
            ),
        ),
        "single_backward_executed": controls.grad is not None,
        "pre_event_temporal_credit_nonzero": any(
            bool(eligibility[index])
            and index < correction_index
            and abs(float(gradient[index])) > ALLOCATION_TOLERANCE
            for index in range(len(evidence_ids))
        ),
        "correction_site_credit_nonzero": abs(
            float(gradient[correction_index])
        )
        > ALLOCATION_TOLERANCE,
        "trajectory_objective_decreased": float(accepted_loss.detach())
        < float(loss_before.detach()),
        "trajectory_path_loss_decreased": float(
            accepted_components["path"].detach()
        )
        < float(components_before["path"].detach()),
        "revised_forward_replay_exact": torch.equal(
            accepted_states, replay_states
        )
        and float(accepted_loss.detach()) == float(replay_loss.detach()),
        "stable_axis_exact_identity": torch.equal(
            states_before[:, 2], accepted_states[:, 2]
        )
        and bool(
            torch.all(
                accepted_states[:, 2]
                == initial_state[2]
            )
        ),
        "bounded_time_local_control": norm <= MAX_CONTROL_L2 + 1.0e-15,
        "gradient_stops_before_json": True,
    }
    _require(
        tuple(trajectory_checks) == TRAJECTORY_PRODUCT_CHECK_KEYS
        and all(trajectory_checks.values()),
        "PUBLIC_TRAJECTORY_HARD_GATE_FAILED",
        ",".join(
            key for key, passed in trajectory_checks.items() if not passed
        ),
    )
    public_trajectory = _seal(
        {
            "schema_version": TRAJECTORY_SCHEMA,
            "state_kind": "PUBLIC_HAND_BUILT_REVISION_SURROGATE",
            "axis_order": list(TRAJECTORY_AXES),
            "axis_semantics": {
                "event_consistent_support": "higher means more admitted public support has been revisited",
                "invalidated_support_clearance": "higher means the typed invalidation event has been integrated",
                "stable_support_retention": "exactly preserves the compiled public Before coordinate",
            },
            "control_gate": {
                "transform": "BOUNDED_SIGNED_RESIDUAL_GATE",
                "zero_control_semantics": "EXACT_NO_EVENT_PROPOSAL_ADMISSION",
                "maximum_absolute_coordinate": MAX_CONTROL_L2,
            },
            "smoothness_domain": "ADJACENT_ELIGIBLE_TEMPORAL_CONTROL_SITES",
            "terminal_target": [1.0, 1.0, float(initial_state[2])],
            "source_actual_before_state_fingerprint_sha256": actual_state[
                "fingerprint_sha256"
            ],
            "source_credit_basis_fingerprint_sha256": source_receipt[
                "fingerprint_sha256"
            ],
            "correction_step_index": correction_index,
            "neutral": _seal(
                {
                    "objective": float(loss_before.detach()),
                    "loss_components": _loss_components_value(
                        components_before
                    ),
                    "terminal_state": [
                        float(value) for value in states_before[-1].detach()
                    ],
                    "points": neutral_points,
                }
            ),
            "revised": _seal(
                {
                    "objective": float(accepted_loss.detach()),
                    "loss_components": _loss_components_value(
                        accepted_components
                    ),
                    "terminal_state": [
                        float(value) for value in accepted_states[-1].detach()
                    ],
                    "points": revised_points,
                }
            ),
            "matched_temporal_sham": {
                "construction": "REVERSE_ACCEPTED_CONTROL_VALUES_OVER_ELIGIBLE_TIME_SITES",
                "objective": float(sham_loss.detach()),
                "loss_components": _loss_components_value(sham_components),
                "terminal_state": [
                    float(value) for value in sham_states[-1].detach()
                ],
                "control_l2": float(torch.linalg.vector_norm(sham)),
                "provider_calls": 0,
                "claim_scope": "LOCAL_PUBLIC_SURROGATE_ONLY",
            },
            "research_diagnostics": {
                "temporal_sham": sham_diagnostic,
            },
            "checks": trajectory_checks,
            "gradient_boundary": {
                "starts_at": "compiled public Before state plus typed public evidence program",
                "ends_at": "bounded time-local public trajectory controls",
                "hosted_model_differentiated": False,
                "private_reasoning_observed": False,
            },
        }
    )
    checks = {
        "actual_before_state_bound_to_controller": (
            actual_state["source_compiled_fingerprint_sha256"]
            == compiled_before["fingerprint_sha256"]
        ),
        "local_backward_executed": controls.grad is not None,
        "finite_continuous_allocation": all(
            math.isfinite(float(row["control_value"]))
            and math.isfinite(float(row["optimized_allocation_fraction"]))
            for row in rows
        ),
        "surrogate_objective_decreased": (
            float(accepted_loss.detach()) < float(loss_before.detach())
        ),
        "non_neutral_control_map": any(
            abs(float(row["allocation_delta"])) > ALLOCATION_TOLERANCE
            for row in rows
        ),
        "control_budget_respected": norm <= MAX_CONTROL_L2 + 1.0e-15,
        "allocation_simplex_respected": abs(
            sum(float(row["optimized_allocation_fraction"]) for row in rows)
            - 1.0
        )
        <= ALLOCATION_TOLERANCE,
        "ineligible_allocation_zero": all(
            bool(row["eligible_for_reinspection"])
            or abs(float(row["optimized_allocation_fraction"]))
            <= ALLOCATION_TOLERANCE
            for row in rows
        ),
        "surrogate_terminal_state_increased": float(
            accepted_states[-1, :2].mean().detach()
        )
        > float(states_before[-1, :2].mean().detach()),
        "finite_difference_agreement": max(errors) <= FINITE_DIFFERENCE_TOLERANCE,
        "public_trajectory_bound": public_trajectory[
            "source_actual_before_state_fingerprint_sha256"
        ]
        == actual_state["fingerprint_sha256"],
        "pre_event_temporal_credit_nonzero": trajectory_checks[
            "pre_event_temporal_credit_nonzero"
        ],
        "trajectory_path_loss_decreased": trajectory_checks[
            "trajectory_path_loss_decreased"
        ],
        "stable_axis_exact_identity": trajectory_checks[
            "stable_axis_exact_identity"
        ],
        "gradient_stops_before_provider": True,
        "reserved_gold_fields_absent": not bool(
            _recursive_keys(request.model_dump(mode="json"))
            & FORBIDDEN_REQUEST_KEYS
        ),
    }
    _require(
        tuple(checks) == CONTROL_PRODUCT_CHECK_KEYS and all(checks.values()),
        "CONTROLLER_HARD_GATE_FAILED",
    )
    return _seal(
        {
            "schema_version": CONTROL_SCHEMA,
            "status": "PASS",
            "actual_before_state": actual_state,
            "source_credit_basis": source_receipt,
            "dtype": "torch.float64",
            "backward_calls": 1,
            "objective_before": float(loss_before.detach()),
            "objective_after": float(accepted_loss.detach()),
            "terminal_target": TERMINAL_TARGET,
            "inspection_temperature": INSPECTION_TEMPERATURE,
            "provider_visible_allocation_transform": "SOFTMAX_ABSOLUTE_CONTROL_MAGNITUDE",
            "semantic_operation_source": "TYPED_EVENT_COMPILER",
            "allocation_domain_evidence_ids": [
                evidence_id for evidence_id in evidence_ids if evidence_id in eligible_ids
            ],
            "surrogate_terminal_state_before": float(
                states_before[-1, :2].mean().detach()
            ),
            "surrogate_terminal_state_after": float(
                accepted_states[-1, :2].mean().detach()
            ),
            "state_trace_before": [
                [float(value) for value in row] for row in states_before.detach()
            ],
            "state_trace_after": [
                [float(value) for value in row]
                for row in accepted_states.detach()
            ],
            "public_trajectory": public_trajectory,
            "unprojected_control_l2": raw_norm,
            "budget_projection_scale": budget_scale,
            "backtracking_steps": accepted_backtrack,
            "control_l2": norm,
            "max_control_l2": MAX_CONTROL_L2,
            "maximum_finite_difference_error": max(errors),
            "finite_difference_tolerance": FINITE_DIFFERENCE_TOLERANCE,
            "credit_rows": rows,
            "checks": checks,
            "gradient_boundary": {
                "starts_at": "actual normalized public Before state plus public graph incidence and typed event",
                "ends_at": "public control map",
                "crosses_json": False,
                "crosses_provider": False,
                "hosted_model_differentiated": False,
                "reserved_gold_fields_participated": False,
                "caller_semantic_content_verified": False,
            },
        }
    )


def _validate_public_trajectory_derivation(
    request: LiveRevisionRequest,
    compiled_before: Mapping[str, Any],
    control_map: Mapping[str, Any],
) -> None:
    _require(
        control_map.get("schema_version") == CONTROL_SCHEMA
        and control_map.get("fingerprint_sha256")
        == _fingerprint(_without_fingerprint(control_map)),
        "PUBLIC_TRAJECTORY_CONTROL_FINGERPRINT_INVALID",
    )
    _, expected_actual = _actual_before_state(request, compiled_before)
    expected_effects_by_id, expected_receipt = _public_incidence_effects(
        request
    )
    _require(
        control_map.get("actual_before_state") == expected_actual
        and control_map.get("source_credit_basis") == expected_receipt,
        "PUBLIC_TRAJECTORY_SOURCE_DERIVATION_INVALID",
    )
    evidence_ids = [row.evidence_id for row in request.all_raw_evidence]
    rows = control_map.get("credit_rows")
    _require(
        isinstance(rows, list)
        and len(rows) == len(evidence_ids)
        and [row.get("evidence_id") for row in rows] == evidence_ids,
        "PUBLIC_TRAJECTORY_CONTROL_ROWS_INVALID",
    )
    eligible_ids = set(_eligible_reinspection_evidence_ids(request))
    eligibility = torch.tensor(
        [evidence_id in eligible_ids for evidence_id in evidence_ids],
        dtype=torch.bool,
    )
    controls = torch.tensor(
        [float(row["control_value"]) for row in rows], dtype=FLOAT_DTYPE
    )
    gradients = torch.tensor(
        [float(row["gradient"]) for row in rows], dtype=FLOAT_DTYPE
    )
    effects = torch.tensor(
        [expected_effects_by_id[evidence_id] for evidence_id in evidence_ids],
        dtype=FLOAT_DTYPE,
    )
    initial_state = torch.tensor(
        expected_actual["initial_vector"], dtype=FLOAT_DTYPE
    )
    correction_index = evidence_ids.index(
        request.event.correction_evidence_id
    )
    zero = torch.zeros_like(controls)
    neutral_loss, neutral_states, neutral_components = _controller_loss(
        zero,
        effects,
        eligibility,
        initial_state=initial_state,
        correction_index=correction_index,
    )
    finite_difference: list[float] = []
    for index in range(len(evidence_ids)):
        positive = torch.zeros_like(controls)
        negative = torch.zeros_like(controls)
        positive[index] = FINITE_DIFFERENCE_EPSILON
        negative[index] = -FINITE_DIFFERENCE_EPSILON
        plus, _, _ = _controller_loss(
            positive,
            effects,
            eligibility,
            initial_state=initial_state,
            correction_index=correction_index,
        )
        minus, _, _ = _controller_loss(
            negative,
            effects,
            eligibility,
            initial_state=initial_state,
            correction_index=correction_index,
        )
        finite_difference.append(
            float(
                (plus - minus)
                / (2.0 * FINITE_DIFFERENCE_EPSILON)
            )
        )
    errors = [
        abs(float(gradients[index]) - finite_difference[index])
        for index in range(len(evidence_ids))
    ]
    _require(
        all(
            abs(
                float(row["finite_difference_gradient"])
                - finite_difference[index]
            )
            <= 1.0e-15
            and errors[index] <= FINITE_DIFFERENCE_TOLERANCE
            for index, row in enumerate(rows)
        ),
        "PUBLIC_TRAJECTORY_GRADIENT_RECEIPT_INVALID",
    )
    raw_displacement = -STEP_SIZE * gradients
    raw_norm = float(torch.linalg.vector_norm(raw_displacement))
    _require(
        math.isfinite(raw_norm) and raw_norm > 0.0,
        "PUBLIC_TRAJECTORY_CONTROL_UPDATE_INVALID",
    )
    budget_scale = min(1.0, MAX_CONTROL_L2 / raw_norm)
    bounded = raw_displacement * budget_scale
    expected_controls: torch.Tensor | None = None
    expected_backtrack = -1
    for backtrack in range(MAX_BACKTRACKS + 1):
        candidate = bounded * (0.5**backtrack)
        candidate_loss, _, _ = _controller_loss(
            candidate,
            effects,
            eligibility,
            initial_state=initial_state,
            correction_index=correction_index,
        )
        if float(candidate_loss.detach()) < float(neutral_loss.detach()):
            expected_controls = candidate
            expected_backtrack = backtrack
            break
    _require(
        expected_controls is not None
        and torch.equal(controls, expected_controls)
        and control_map.get("unprojected_control_l2") == raw_norm
        and control_map.get("budget_projection_scale") == budget_scale
        and control_map.get("backtracking_steps") == expected_backtrack,
        "PUBLIC_TRAJECTORY_DETERMINISTIC_UPDATE_INVALID",
    )
    revised_loss, revised_states, revised_components = _controller_loss(
        controls,
        effects,
        eligibility,
        initial_state=initial_state,
        correction_index=correction_index,
    )
    neutral_points = _trajectory_points(
        evidence_ids=evidence_ids,
        states=neutral_states,
        controls=zero,
        gradients=gradients,
        eligibility=eligibility,
        correction_index=correction_index,
        support_envelope=_full_admission_support_envelope(
            effects,
            eligibility,
            initial_support=initial_state[0],
        ),
    )
    revised_points = _trajectory_points(
        evidence_ids=evidence_ids,
        states=revised_states,
        controls=controls,
        gradients=gradients,
        eligibility=eligibility,
        correction_index=correction_index,
        support_envelope=_full_admission_support_envelope(
            effects,
            eligibility,
            initial_support=initial_state[0],
        ),
    )
    trajectory = control_map.get("public_trajectory")
    _require(
        isinstance(trajectory, Mapping)
        and trajectory.get("schema_version") == TRAJECTORY_SCHEMA
        and trajectory.get("fingerprint_sha256")
        == _fingerprint(_without_fingerprint(trajectory)),
        "PUBLIC_TRAJECTORY_FINGERPRINT_INVALID",
    )
    neutral = trajectory.get("neutral")
    revised = trajectory.get("revised")
    _require(
        isinstance(neutral, Mapping)
        and isinstance(revised, Mapping)
        and neutral.get("fingerprint_sha256")
        == _fingerprint(_without_fingerprint(neutral))
        and revised.get("fingerprint_sha256")
        == _fingerprint(_without_fingerprint(revised))
        and neutral.get("objective") == float(neutral_loss.detach())
        and revised.get("objective") == float(revised_loss.detach())
        and neutral.get("loss_components")
        == _loss_components_value(neutral_components)
        and revised.get("loss_components")
        == _loss_components_value(revised_components)
        and neutral.get("terminal_state")
        == [float(value) for value in neutral_states[-1].detach()]
        and revised.get("terminal_state")
        == [float(value) for value in revised_states[-1].detach()]
        and neutral.get("points") == neutral_points
        and revised.get("points") == revised_points,
        "PUBLIC_TRAJECTORY_FORWARD_REPLAY_MISMATCH",
    )
    sham = _matched_temporal_sham(controls, eligibility)
    sham_loss, sham_states, sham_components = _controller_loss(
        sham,
        effects,
        eligibility,
        initial_state=initial_state,
        correction_index=correction_index,
    )
    expected_sham_diagnostic = _temporal_sham_diagnostic(
        accepted=controls,
        accepted_loss=revised_loss,
        accepted_components=revised_components,
        sham=sham,
        sham_loss=sham_loss,
        sham_components=sham_components,
        eligibility=eligibility,
    )
    control_norm = float(torch.linalg.vector_norm(controls))
    expected_trajectory_checks = {
        "source_actual_before_state_bound": expected_actual[
            "fingerprint_sha256"
        ]
        == _fingerprint(_without_fingerprint(expected_actual)),
        "chronological_forward_exact": [
            row["evidence_id"] for row in revised_points
        ]
        == evidence_ids,
        "zero_control_is_exact_unmodified_forward": torch.equal(
            neutral_states,
            _unmodified_forward_trajectory(
                initial_state, steps=len(evidence_ids)
            ),
        ),
        "single_backward_executed": control_map.get("backward_calls") == 1,
        "pre_event_temporal_credit_nonzero": any(
            bool(eligibility[index])
            and index < correction_index
            and abs(float(gradients[index])) > ALLOCATION_TOLERANCE
            for index in range(len(evidence_ids))
        ),
        "correction_site_credit_nonzero": abs(
            float(gradients[correction_index])
        )
        > ALLOCATION_TOLERANCE,
        "trajectory_objective_decreased": float(revised_loss.detach())
        < float(neutral_loss.detach()),
        "trajectory_path_loss_decreased": float(
            revised_components["path"].detach()
        )
        < float(neutral_components["path"].detach()),
        "revised_forward_replay_exact": True,
        "stable_axis_exact_identity": torch.equal(
            neutral_states[:, 2], revised_states[:, 2]
        )
        and bool(torch.all(revised_states[:, 2] == initial_state[2])),
        "bounded_time_local_control": control_norm
        <= MAX_CONTROL_L2 + 1.0e-15,
        "gradient_stops_before_json": True,
    }
    expected_matched_sham = {
        "construction": "REVERSE_ACCEPTED_CONTROL_VALUES_OVER_ELIGIBLE_TIME_SITES",
        "objective": float(sham_loss.detach()),
        "loss_components": _loss_components_value(sham_components),
        "terminal_state": [
            float(value) for value in sham_states[-1].detach()
        ],
        "control_l2": float(torch.linalg.vector_norm(sham)),
        "provider_calls": 0,
        "claim_scope": "LOCAL_PUBLIC_SURROGATE_ONLY",
    }
    _require(
        tuple(expected_trajectory_checks) == TRAJECTORY_PRODUCT_CHECK_KEYS
        and all(expected_trajectory_checks.values())
        and trajectory.get("checks") == expected_trajectory_checks
        and trajectory.get("matched_temporal_sham")
        == expected_matched_sham
        and trajectory.get("research_diagnostics")
        == {"temporal_sham": expected_sham_diagnostic}
        and trajectory.get("control_gate")
        == {
            "transform": "BOUNDED_SIGNED_RESIDUAL_GATE",
            "zero_control_semantics": "EXACT_NO_EVENT_PROPOSAL_ADMISSION",
            "maximum_absolute_coordinate": MAX_CONTROL_L2,
        }
        and trajectory.get("smoothness_domain")
        == "ADJACENT_ELIGIBLE_TEMPORAL_CONTROL_SITES"
        and trajectory.get("axis_order") == list(TRAJECTORY_AXES)
        and trajectory.get("terminal_target")
        == [1.0, 1.0, float(initial_state[2])]
        and trajectory.get("source_actual_before_state_fingerprint_sha256")
        == expected_actual["fingerprint_sha256"]
        and trajectory.get("source_credit_basis_fingerprint_sha256")
        == expected_receipt["fingerprint_sha256"]
        and trajectory.get("correction_step_index") == correction_index,
        "PUBLIC_TRAJECTORY_RECEIPT_DERIVATION_INVALID",
    )
    expected_allocation = _masked_allocation(controls, eligibility)
    baseline_allocation = _masked_allocation(zero, eligibility)
    expected_control_checks = {
        "actual_before_state_bound_to_controller": expected_actual[
            "source_compiled_fingerprint_sha256"
        ]
        == compiled_before["fingerprint_sha256"],
        "local_backward_executed": control_map.get("backward_calls") == 1,
        "finite_continuous_allocation": all(
            math.isfinite(float(row["control_value"]))
            and math.isfinite(
                float(row["optimized_allocation_fraction"])
            )
            for row in rows
        ),
        "surrogate_objective_decreased": float(revised_loss.detach())
        < float(neutral_loss.detach()),
        "non_neutral_control_map": any(
            abs(
                float(expected_allocation[index])
                - float(baseline_allocation[index])
            )
            > ALLOCATION_TOLERANCE
            for index in range(len(evidence_ids))
        ),
        "control_budget_respected": control_norm
        <= MAX_CONTROL_L2 + 1.0e-15,
        "allocation_simplex_respected": abs(
            float(expected_allocation.sum()) - 1.0
        )
        <= ALLOCATION_TOLERANCE,
        "ineligible_allocation_zero": all(
            bool(eligibility[index])
            or abs(float(expected_allocation[index]))
            <= ALLOCATION_TOLERANCE
            for index in range(len(evidence_ids))
        ),
        "surrogate_terminal_state_increased": float(
            revised_states[-1, :2].mean().detach()
        )
        > float(neutral_states[-1, :2].mean().detach()),
        "finite_difference_agreement": max(errors)
        <= FINITE_DIFFERENCE_TOLERANCE,
        "public_trajectory_bound": trajectory[
            "source_actual_before_state_fingerprint_sha256"
        ]
        == expected_actual["fingerprint_sha256"],
        "pre_event_temporal_credit_nonzero": expected_trajectory_checks[
            "pre_event_temporal_credit_nonzero"
        ],
        "trajectory_path_loss_decreased": expected_trajectory_checks[
            "trajectory_path_loss_decreased"
        ],
        "stable_axis_exact_identity": expected_trajectory_checks[
            "stable_axis_exact_identity"
        ],
        "gradient_stops_before_provider": True,
        "reserved_gold_fields_absent": not bool(
            _recursive_keys(request.model_dump(mode="json"))
            & FORBIDDEN_REQUEST_KEYS
        ),
    }
    _require(
        control_map.get("objective_before") == float(neutral_loss.detach())
        and control_map.get("objective_after") == float(revised_loss.detach())
        and control_map.get("state_trace_before")
        == [
            [float(value) for value in row]
            for row in neutral_states.detach()
        ]
        and control_map.get("state_trace_after")
        == [
            [float(value) for value in row]
            for row in revised_states.detach()
        ]
        and all(
            float(row["source_effect"])
            == float(effects[index])
            and float(row["gradient"]) == float(gradients[index])
            and float(row["finite_difference_gradient"])
            == finite_difference[index]
            and float(row["control_value"]) == float(controls[index])
            and float(row["reinspection_salience"])
            == abs(float(controls[index]))
            and row["temporal_step_index"] == index
            and bool(row["eligible_for_reinspection"])
            is bool(eligibility[index])
            and float(row["baseline_allocation_fraction"])
            == float(baseline_allocation[index])
            and float(row["optimized_allocation_fraction"])
            == float(expected_allocation[index])
            and float(row["allocation_delta"])
            == float(
                expected_allocation[index] - baseline_allocation[index]
            )
            and float(row["surrogate_contribution_before"])
            == float(
                (baseline_allocation[index] * effects[index]).detach()
            )
            and float(row["surrogate_contribution_after"])
            == float(
                (expected_allocation[index] * effects[index]).detach()
            )
            and row["state_before"]
            == [float(value) for value in neutral_states[index].detach()]
            and row["state_after"]
            == [float(value) for value in revised_states[index].detach()]
            for index, row in enumerate(rows)
        )
        and control_map.get("control_l2") == control_norm
        and control_map.get("max_control_l2") == MAX_CONTROL_L2
        and control_map.get("maximum_finite_difference_error")
        == max(errors)
        and control_map.get("finite_difference_tolerance")
        == FINITE_DIFFERENCE_TOLERANCE
        and control_map.get("provider_visible_allocation_transform")
        == "SOFTMAX_ABSOLUTE_CONTROL_MAGNITUDE"
        and control_map.get("semantic_operation_source")
        == "TYPED_EVENT_COMPILER"
        and control_map.get("checks") == expected_control_checks
        and tuple(expected_control_checks) == CONTROL_PRODUCT_CHECK_KEYS
        and all(expected_control_checks.values()),
        "PUBLIC_TRAJECTORY_CONTROL_DERIVATION_INVALID",
    )


def _derive_no_event_identity_trajectory(
    request: LiveRevisionRequest,
    compiled_before: Mapping[str, Any],
) -> JsonObject:
    """Private zero-call sentinel; the public API still requires a typed event."""

    _, actual_state = _actual_before_state(request, compiled_before)
    initial = [float(value) for value in actual_state["initial_vector"]]
    points = [
        _seal(
            {
                "step_index": index,
                "evidence_id": row.evidence_id,
                "is_correction_event": False,
                "eligible_for_temporal_control": False,
                "state": initial,
                "control_value": 0.0,
                "temporal_gradient": 0.0,
            }
        )
        for index, row in enumerate(request.all_raw_evidence)
    ]
    trace = _seal(
        {
            "objective": 0.0,
            "loss_components": {
                "terminal": 0.0,
                "path": 0.0,
                "control": 0.0,
                "smoothness": 0.0,
            },
            "terminal_state": initial,
            "points": points,
        }
    )
    return _seal(
        {
            "schema_version": TRAJECTORY_SCHEMA,
            "status": "IDENTITY_NO_EVENT",
            "state_kind": "PUBLIC_HAND_BUILT_REVISION_SURROGATE",
            "axis_order": list(TRAJECTORY_AXES),
            "source_actual_before_state_fingerprint_sha256": actual_state[
                "fingerprint_sha256"
            ],
            "neutral": trace,
            "revised": _clone(trace),
            "backward_calls": 0,
            "provider_calls": 0,
            "checks": {
                "exact_identity": True,
                "zero_control": True,
                "zero_backward": True,
                "zero_provider_calls": True,
            },
        }
    )


def _largest_remainder_units(
    rows: Sequence[Mapping[str, Any]], *, total_units: int
) -> dict[str, int]:
    _require(bool(rows) and total_units >= len(rows), "INSPECTION_BUDGET_TOO_SMALL")
    remaining = total_units - len(rows)
    raw = {
        str(row["evidence_id"]): float(row["inspection_share"]) * remaining
        for row in rows
    }
    units = {evidence_id: 1 + math.floor(value) for evidence_id, value in raw.items()}
    remainder = total_units - sum(units.values())
    order = sorted(
        raw,
        key=lambda evidence_id: (
            -(raw[evidence_id] - math.floor(raw[evidence_id])),
            evidence_id,
        ),
    )
    for evidence_id in order[:remainder]:
        units[evidence_id] += 1
    _require(sum(units.values()) == total_units, "INSPECTION_BUDGET_ALLOCATION_INVALID")
    return units


def _review_depth(relative_emphasis: float) -> str:
    if relative_emphasis >= 1.25:
        return "DEEP"
    if relative_emphasis >= 0.75:
        return "STANDARD"
    return "LIGHT"


def _expected_program_steps(
    *,
    correction_evidence_id: str,
    suppress_evidence_ids: Sequence[str],
    inspection_steps: Sequence[Mapping[str, Any]],
    preserve_evidence_ids: Sequence[str],
) -> list[JsonObject]:
    steps: list[JsonObject] = [
        {
            "step_index": 0,
            "operation": "LOAD_EVENT",
            "evidence_id": correction_evidence_id,
        }
    ]
    for evidence_id in suppress_evidence_ids:
        steps.append(
            {
                "step_index": len(steps),
                "operation": "SUPPRESS",
                "evidence_id": evidence_id,
            }
        )
    for row in inspection_steps:
        steps.append(
            {
                "step_index": len(steps),
                "operation": "REINSPECT",
                **dict(row),
            }
        )
    for evidence_id in preserve_evidence_ids:
        steps.append(
            {
                "step_index": len(steps),
                "operation": "PRESERVE",
                "evidence_id": evidence_id,
            }
        )
    steps.append(
        {
            "step_index": len(steps),
            "operation": "PREPARE_FULL_CONTEXT_REGENERATION",
        }
    )
    return steps


def _validate_inspection_plan_and_program(
    *,
    allowed_evidence_ids: set[str],
    correction_evidence_id: str,
    source_public_trajectory_fingerprint_sha256: str,
    suppress_evidence_ids: Sequence[str],
    reinspect_evidence_ids: Sequence[str],
    preserve_evidence_ids: Sequence[str],
    inspection_plan: Mapping[str, Any],
    program: Mapping[str, Any],
) -> None:
    _require(
        inspection_plan.get("schema_version")
        == "ebrt-live-continuous-inspection-plan-v0.6.2.5"
        and inspection_plan.get("fingerprint_sha256")
        == _fingerprint(_without_fingerprint(inspection_plan)),
        "ACTUATOR_INSPECTION_PLAN_FINGERPRINT_INVALID",
    )
    _require(
        inspection_plan.get("allocation_scope")
        == "SELECTED_PUBLIC_REINSPECTION_STEPS"
        and inspection_plan.get("total_budget_units")
        == INSPECTION_BUDGET_UNITS
        and inspection_plan.get("budget_unit_semantics")
        == "ABSTRACT_PUBLIC_REVIEW_ALLOCATION_NOT_PROVIDER_TOKENS",
        "ACTUATOR_INSPECTION_PLAN_CONTRACT_INVALID",
    )
    _require(
        inspection_plan.get("source_public_trajectory_fingerprint_sha256")
        == source_public_trajectory_fingerprint_sha256,
        "ACTUATOR_INSPECTION_PLAN_TRAJECTORY_BINDING_INVALID",
    )
    rows = inspection_plan.get("steps")
    _require(
        isinstance(rows, list)
        and len(rows) == len(reinspect_evidence_ids)
        and 1 <= len(rows) <= 8,
        "ACTUATOR_INSPECTION_STEPS_INVALID",
    )
    expected_row_keys = {
        "evidence_id",
        "priority_rank",
        "controller_allocation_fraction",
        "inspection_share",
        "allocation_delta",
        "relative_emphasis",
        "review_depth",
        "inspection_budget_units",
    }
    seen_ids: set[str] = set()
    for index, row in enumerate(rows, start=1):
        _require(
            isinstance(row, Mapping) and set(row) == expected_row_keys,
            "ACTUATOR_INSPECTION_ROW_SCHEMA_INVALID",
        )
        evidence_id = row["evidence_id"]
        rank = row["priority_rank"]
        controller_fraction = row["controller_allocation_fraction"]
        share = row["inspection_share"]
        delta = row["allocation_delta"]
        relative_emphasis = row["relative_emphasis"]
        budget_units = row["inspection_budget_units"]
        _require(
            isinstance(evidence_id, str)
            and evidence_id in allowed_evidence_ids
            and evidence_id not in seen_ids
            and evidence_id == reinspect_evidence_ids[index - 1],
            "ACTUATOR_INSPECTION_EVIDENCE_INVALID",
        )
        seen_ids.add(evidence_id)
        _require(
            isinstance(rank, int)
            and not isinstance(rank, bool)
            and rank == index,
            "ACTUATOR_INSPECTION_RANK_INVALID",
        )
        for value, label in (
            (controller_fraction, "CONTROLLER_FRACTION"),
            (share, "SHARE"),
            (delta, "DELTA"),
            (relative_emphasis, "EMPHASIS"),
        ):
            _require(
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(float(value)),
                f"ACTUATOR_INSPECTION_{label}_INVALID",
            )
        _require(
            0.0 < float(controller_fraction) <= 1.0
            and 0.0 < float(share) <= 1.0
            and float(relative_emphasis) > 0.0,
            "ACTUATOR_INSPECTION_BOUNDS_INVALID",
        )
        _require(
            abs(float(relative_emphasis) - float(share) * len(rows))
            <= ALLOCATION_TOLERANCE
            and row["review_depth"]
            == _review_depth(float(relative_emphasis)),
            "ACTUATOR_INSPECTION_DERIVATION_INVALID",
        )
        _require(
            isinstance(budget_units, int)
            and not isinstance(budget_units, bool)
            and budget_units >= 1,
            "ACTUATOR_INSPECTION_BUDGET_UNIT_INVALID",
        )
    _require(
        abs(sum(float(row["inspection_share"]) for row in rows) - 1.0)
        <= ALLOCATION_TOLERANCE
        and sum(int(row["inspection_budget_units"]) for row in rows)
        == INSPECTION_BUDGET_UNITS,
        "ACTUATOR_INSPECTION_TOTAL_INVALID",
    )
    expected_order = sorted(
        rows,
        key=lambda row: (
            -float(row["controller_allocation_fraction"]),
            row["evidence_id"],
        ),
    )
    _require(rows == expected_order, "ACTUATOR_INSPECTION_ORDER_INVALID")
    _require(
        program.get("schema_version")
        == "ebrt-live-public-revision-program-v0.6.2.5"
        and program.get("state") == "COMPILED"
        and program.get("source_public_trajectory_fingerprint_sha256")
        == source_public_trajectory_fingerprint_sha256
        and program.get("fingerprint_sha256")
        == _fingerprint(_without_fingerprint(program)),
        "ACTUATOR_PROGRAM_FINGERPRINT_INVALID",
    )
    expected_program = _expected_program_steps(
        correction_evidence_id=correction_evidence_id,
        suppress_evidence_ids=suppress_evidence_ids,
        inspection_steps=rows,
        preserve_evidence_ids=preserve_evidence_ids,
    )
    _require(
        program.get("steps") == expected_program,
        "ACTUATOR_PROGRAM_MATERIALIZATION_INVALID",
    )


def _compile_actuator(
    request: LiveRevisionRequest,
    compiled_before: Mapping[str, Any],
    control_map: Mapping[str, Any],
) -> JsonObject:
    _validate_public_trajectory_derivation(
        request, compiled_before, control_map
    )
    public_trajectory = control_map.get("public_trajectory")
    _require(
        isinstance(public_trajectory, Mapping)
        and public_trajectory.get("schema_version") == TRAJECTORY_SCHEMA
        and public_trajectory.get("fingerprint_sha256")
        == _fingerprint(_without_fingerprint(public_trajectory))
        and isinstance(public_trajectory.get("checks"), Mapping)
        and all(public_trajectory["checks"].values()),
        "ACTUATOR_PUBLIC_TRAJECTORY_INVALID",
    )
    trajectory_fingerprint = str(public_trajectory["fingerprint_sha256"])
    invalidated = set(request.event.invalidated_evidence_ids)
    stable = set(request.event.stable_evidence_ids)
    eligible = [
        row
        for row in control_map["credit_rows"]
        if bool(row["eligible_for_reinspection"])
        and float(row["optimized_allocation_fraction"]) > 0.0
    ]
    eligible.sort(
        key=lambda row: (
            -float(row["optimized_allocation_fraction"]),
            row["evidence_id"],
        )
    )
    _require(
        len(eligible) >= request.reinspection_count,
        "ACTUATOR_REINSPECTION_COUNT_UNAVAILABLE",
    )
    selected = eligible[: request.reinspection_count]
    selected_total = sum(
        float(row["optimized_allocation_fraction"]) for row in selected
    )
    _require(selected_total > 0.0, "ACTUATOR_ALLOCATION_ZERO")
    plan_rows: list[JsonObject] = []
    for rank, row in enumerate(selected, start=1):
        share = float(row["optimized_allocation_fraction"]) / selected_total
        relative_emphasis = share * len(selected)
        review_depth = _review_depth(relative_emphasis)
        plan_rows.append(
            {
                "evidence_id": str(row["evidence_id"]),
                "priority_rank": rank,
                "controller_allocation_fraction": float(
                    row["optimized_allocation_fraction"]
                ),
                "inspection_share": share,
                "allocation_delta": float(row["allocation_delta"]),
                "relative_emphasis": relative_emphasis,
                "review_depth": review_depth,
            }
        )
    units = _largest_remainder_units(
        plan_rows, total_units=INSPECTION_BUDGET_UNITS
    )
    for row in plan_rows:
        row["inspection_budget_units"] = units[str(row["evidence_id"])]
    reinspect = [str(row["evidence_id"]) for row in plan_rows]
    active_before = set(compiled_before["active_support_evidence_ids"])
    evidence_order = [row.evidence_id for row in request.all_raw_evidence]
    suppress = [
        evidence_id
        for evidence_id in evidence_order
        if evidence_id in invalidated & active_before
    ]
    preserve = [
        evidence_id
        for evidence_id in evidence_order
        if evidence_id in stable & active_before
    ]
    _require(
        not (set(reinspect) & (set(suppress) | set(preserve)))
        and not (set(suppress) & set(preserve)),
        "ACTUATOR_OPERATION_OVERLAP",
    )
    inspection_plan = _seal(
        {
            "schema_version": "ebrt-live-continuous-inspection-plan-v0.6.2.5",
            "allocation_scope": "SELECTED_PUBLIC_REINSPECTION_STEPS",
            "source_public_trajectory_fingerprint_sha256": trajectory_fingerprint,
            "total_budget_units": INSPECTION_BUDGET_UNITS,
            "budget_unit_semantics": "ABSTRACT_PUBLIC_REVIEW_ALLOCATION_NOT_PROVIDER_TOKENS",
            "steps": plan_rows,
        }
    )
    program_steps = _expected_program_steps(
        correction_evidence_id=request.event.correction_evidence_id,
        suppress_evidence_ids=suppress,
        inspection_steps=plan_rows,
        preserve_evidence_ids=preserve,
    )
    program = _seal(
        {
            "schema_version": "ebrt-live-public-revision-program-v0.6.2.5",
            "state": "COMPILED",
            "source_control_map_fingerprint_sha256": control_map[
                "fingerprint_sha256"
            ],
            "source_public_trajectory_fingerprint_sha256": trajectory_fingerprint,
            "steps": program_steps,
        }
    )
    _validate_inspection_plan_and_program(
        allowed_evidence_ids={row.evidence_id for row in request.all_raw_evidence},
        correction_evidence_id=request.event.correction_evidence_id,
        source_public_trajectory_fingerprint_sha256=trajectory_fingerprint,
        suppress_evidence_ids=suppress,
        reinspect_evidence_ids=reinspect,
        preserve_evidence_ids=preserve,
        inspection_plan=inspection_plan,
        program=program,
    )
    checks = {
        "source_control_map_bound": control_map["fingerprint_sha256"]
        == program["source_control_map_fingerprint_sha256"],
        "source_public_trajectory_bound": trajectory_fingerprint
        == program["source_public_trajectory_fingerprint_sha256"]
        == inspection_plan["source_public_trajectory_fingerprint_sha256"],
        "selected_count_exact": len(plan_rows) == request.reinspection_count,
        "continuous_allocation_finite": all(
            math.isfinite(float(row["inspection_share"]))
            and math.isfinite(float(row["relative_emphasis"]))
            for row in plan_rows
        ),
        "selected_allocation_simplex_respected": abs(
            sum(float(row["inspection_share"]) for row in plan_rows) - 1.0
        )
        <= ALLOCATION_TOLERANCE,
        "abstract_inspection_budget_exact": sum(
            int(row["inspection_budget_units"]) for row in plan_rows
        )
        == INSPECTION_BUDGET_UNITS,
        "deterministic_priority_order": reinspect
        == [
            str(row["evidence_id"])
            for row in sorted(
                selected,
                key=lambda row: (
                    -float(row["optimized_allocation_fraction"]),
                    row["evidence_id"],
                ),
            )
        ],
        "operation_sets_disjoint": not (
            set(reinspect) & (set(suppress) | set(preserve))
            or set(suppress) & set(preserve)
        ),
        "program_steps_bounded": len(program_steps)
        <= 2 + len(suppress) + len(preserve) + request.reinspection_count,
        "gradient_stops_at_public_program": True,
    }
    _require(all(checks.values()), "ACTUATOR_COMPILER_HARD_GATE_FAILED")
    return _seal(
        {
            "schema_version": ACTUATOR_SCHEMA,
            "source_before_compiled_fingerprint_sha256": compiled_before["fingerprint_sha256"],
            "source_control_map_fingerprint_sha256": control_map["fingerprint_sha256"],
            "source_public_trajectory_fingerprint_sha256": trajectory_fingerprint,
            "event_id": request.event.event_id,
            "correction_evidence_id": request.event.correction_evidence_id,
            "reinspect_evidence_ids": reinspect,
            "reinspect_source": "PUBLIC_TRAJECTORY_ADJOINT_PROJECTION",
            "suppress_evidence_ids": suppress,
            "suppress_source": "TYPED_EVENT_INVALIDATION",
            "preserve_evidence_ids": preserve,
            "preserve_source": "TYPED_EVENT_STABILITY",
            "reinspection_limit": request.reinspection_count,
            "inspection_plan": inspection_plan,
            "program": program,
            "control_l2": control_map["control_l2"],
            "max_control_l2": control_map["max_control_l2"],
            "checks": checks,
            "gradient_stops_here": True,
        }
    )


def _materialize_program_trace(
    steps: Sequence[Mapping[str, Any]],
) -> tuple[list[JsonObject], str]:
    trace: list[JsonObject] = []
    state = "INITIALIZED"
    for expected_index, step in enumerate(steps):
        _require(
            isinstance(step.get("step_index"), int)
            and not isinstance(step.get("step_index"), bool)
            and step["step_index"] == expected_index,
            "ACTUATOR_PROGRAM_INDEX_INVALID",
        )
        operation = str(step["operation"])
        before_state = state
        if operation == "LOAD_EVENT":
            _require(state == "INITIALIZED", "ACTUATOR_TRANSITION_INVALID")
            state = "EVENT_LOADED"
        elif operation == "SUPPRESS":
            _require(
                state in {"EVENT_LOADED", "INVALIDATIONS_APPLIED"},
                "ACTUATOR_TRANSITION_INVALID",
            )
            state = "INVALIDATIONS_APPLIED"
        elif operation == "REINSPECT":
            _require(
                state in {"INVALIDATIONS_APPLIED", "INSPECTION_ALLOCATED"},
                "ACTUATOR_TRANSITION_INVALID",
            )
            state = "INSPECTION_ALLOCATED"
        elif operation == "PRESERVE":
            _require(
                state in {"INSPECTION_ALLOCATED", "STABILITY_LOCKED"},
                "ACTUATOR_TRANSITION_INVALID",
            )
            state = "STABILITY_LOCKED"
        elif operation == "PREPARE_FULL_CONTEXT_REGENERATION":
            _require(
                state in {"INSPECTION_ALLOCATED", "STABILITY_LOCKED"},
                "ACTUATOR_TRANSITION_INVALID",
            )
            state = "READY_FOR_PROVIDER"
        else:
            raise LiveRevisionError("ACTUATOR_OPERATION_UNKNOWN", operation)
        trace.append(
            {
                "step_index": expected_index,
                "operation": operation,
                "state_before": before_state,
                "state_after": state,
                "evidence_id": step.get("evidence_id"),
            }
        )
    _require(state == "READY_FOR_PROVIDER", "ACTUATOR_PROGRAM_INCOMPLETE")
    return trace, state


def _execute_actuator_program(
    request: LiveRevisionRequest,
    actuator: Mapping[str, Any],
    *,
    source_control_map_fingerprint_sha256: str,
    source_prior_state_fingerprint_sha256: str,
) -> JsonObject:
    _require(
        actuator["fingerprint_sha256"]
        == _fingerprint(_without_fingerprint(actuator)),
        "ACTUATOR_FINGERPRINT_INVALID",
    )
    _require(
        actuator["inspection_plan"]["fingerprint_sha256"]
        == _fingerprint(_without_fingerprint(actuator["inspection_plan"])),
        "ACTUATOR_INSPECTION_PLAN_FINGERPRINT_INVALID",
    )
    _require(
        actuator["event_id"] == request.event.event_id
        and actuator["correction_evidence_id"]
        == request.event.correction_evidence_id,
        "ACTUATOR_EVENT_BINDING_INVALID",
    )
    _require(
        actuator["source_control_map_fingerprint_sha256"]
        == source_control_map_fingerprint_sha256,
        "ACTUATOR_CONTROL_MAP_BINDING_INVALID",
    )
    _require(
        isinstance(
            actuator.get("source_public_trajectory_fingerprint_sha256"), str
        )
        and actuator["source_public_trajectory_fingerprint_sha256"]
        == actuator["program"][
            "source_public_trajectory_fingerprint_sha256"
        ]
        == actuator["inspection_plan"][
            "source_public_trajectory_fingerprint_sha256"
        ],
        "ACTUATOR_TRAJECTORY_BINDING_INVALID",
    )
    evidence_ids = {row.evidence_id for row in request.all_raw_evidence}
    _require(
        set(actuator["reinspect_evidence_ids"]) <= evidence_ids
        and set(actuator["suppress_evidence_ids"])
        == set(request.event.invalidated_evidence_ids)
        and set(actuator["preserve_evidence_ids"])
        == set(request.event.stable_evidence_ids),
        "ACTUATOR_EVIDENCE_BINDING_INVALID",
    )
    program = actuator["program"]
    _validate_inspection_plan_and_program(
        allowed_evidence_ids=evidence_ids,
        correction_evidence_id=request.event.correction_evidence_id,
        source_public_trajectory_fingerprint_sha256=actuator[
            "source_public_trajectory_fingerprint_sha256"
        ],
        suppress_evidence_ids=actuator["suppress_evidence_ids"],
        reinspect_evidence_ids=actuator["reinspect_evidence_ids"],
        preserve_evidence_ids=actuator["preserve_evidence_ids"],
        inspection_plan=actuator["inspection_plan"],
        program=program,
    )
    steps = list(program["steps"])
    _require(program["state"] == "COMPILED", "ACTUATOR_PROGRAM_STATE_INVALID")
    _require(
        program["fingerprint_sha256"]
        == _fingerprint(_without_fingerprint(program)),
        "ACTUATOR_PROGRAM_FINGERPRINT_INVALID",
    )
    _require(
        program["source_control_map_fingerprint_sha256"]
        == actuator["source_control_map_fingerprint_sha256"],
        "ACTUATOR_PROGRAM_CONTROL_BINDING_INVALID",
    )
    load_steps = [row for row in steps if row["operation"] == "LOAD_EVENT"]
    suppress_steps = [row for row in steps if row["operation"] == "SUPPRESS"]
    reinspect_steps = [row for row in steps if row["operation"] == "REINSPECT"]
    preserve_steps = [row for row in steps if row["operation"] == "PRESERVE"]
    prepare_steps = [
        row
        for row in steps
        if row["operation"] == "PREPARE_FULL_CONTEXT_REGENERATION"
    ]
    _require(
        len(load_steps) == len(prepare_steps) == 1
        and load_steps[0]["evidence_id"]
        == request.event.correction_evidence_id,
        "ACTUATOR_PROGRAM_BOUNDARY_STEPS_INVALID",
    )
    _require(
        [row["evidence_id"] for row in suppress_steps]
        == list(actuator["suppress_evidence_ids"])
        and [row["evidence_id"] for row in preserve_steps]
        == list(actuator["preserve_evidence_ids"]),
        "ACTUATOR_PROGRAM_TYPED_SUMMARY_MISMATCH",
    )
    program_reinspection_rows = [
        {
            key: value
            for key, value in row.items()
            if key not in {"step_index", "operation"}
        }
        for row in reinspect_steps
    ]
    _require(
        program_reinspection_rows == actuator["inspection_plan"]["steps"],
        "ACTUATOR_PROGRAM_INSPECTION_PLAN_MISMATCH",
    )
    trace, state = _materialize_program_trace(steps)
    provider_operation = _seal(
        {
            "schema_version": REVISION_OPERATION_SCHEMA,
            "operation": "APPLY_REVISION",
            "event": request.event.model_dump(mode="json"),
            "program": program,
            "inspection_plan": actuator["inspection_plan"],
            "reinspect_evidence_ids": list(actuator["reinspect_evidence_ids"]),
            "suppress_evidence_ids": list(actuator["suppress_evidence_ids"]),
            "preserve_evidence_ids": list(actuator["preserve_evidence_ids"]),
            "source_prior_state_fingerprint_sha256": source_prior_state_fingerprint_sha256,
            "source_actuator_fingerprint_sha256": actuator["fingerprint_sha256"],
            "source_public_trajectory_fingerprint_sha256": actuator[
                "source_public_trajectory_fingerprint_sha256"
            ],
            "semantic_authority": "ordered raw evidence only",
            "gradient_boundary": "gradient stopped before this JSON operation and hosted generation",
        }
    )
    checks = {
        "source_actuator_bound": provider_operation[
            "source_actuator_fingerprint_sha256"
        ]
        == actuator["fingerprint_sha256"],
        "source_control_map_bound": actuator[
            "source_control_map_fingerprint_sha256"
        ]
        == source_control_map_fingerprint_sha256,
        "source_public_trajectory_bound": provider_operation[
            "source_public_trajectory_fingerprint_sha256"
        ]
        == actuator["source_public_trajectory_fingerprint_sha256"],
        "program_state_machine_complete": state == "READY_FOR_PROVIDER",
        "execution_trace_exact": len(trace) == len(steps)
        and all(
            row["step_index"] == index for index, row in enumerate(trace)
        ),
        "program_summaries_exact": program_reinspection_rows
        == actuator["inspection_plan"]["steps"],
        "emitted_operation_sealed": provider_operation["fingerprint_sha256"]
        == _fingerprint(_without_fingerprint(provider_operation)),
        "abstract_inspection_budget_exact": sum(
            int(row["inspection_budget_units"])
            for row in provider_operation["inspection_plan"]["steps"]
        )
        == INSPECTION_BUDGET_UNITS,
        "provider_operation_gold_free": not bool(
            _recursive_keys(provider_operation) & PROVIDER_FORBIDDEN_KEYS
        ),
    }
    _require(all(checks.values()), "ACTUATOR_EXECUTION_HARD_GATE_FAILED")
    return _seal(
        {
            "schema_version": ACTUATOR_EXECUTION_SCHEMA,
            "status": "COMPLETED",
            "source_actuator_fingerprint_sha256": actuator["fingerprint_sha256"],
            "source_program_fingerprint_sha256": program["fingerprint_sha256"],
            "source_public_trajectory_fingerprint_sha256": actuator[
                "source_public_trajectory_fingerprint_sha256"
            ],
            "final_state": state,
            "trace": trace,
            "emitted_provider_operation": provider_operation,
            "emitted_provider_operation_fingerprint_sha256": provider_operation[
                "fingerprint_sha256"
            ],
            "checks": checks,
        }
    )


def _opaque_closure_id(prefix: str, graph: ClosureGraph) -> str:
    return f"{prefix}_{_fingerprint(_canonical_graph_value(graph))[:16]}"


def _provider_candidate_rows(request: LiveRevisionRequest) -> list[JsonObject]:
    rows = [
        {
            "closure_id": _opaque_closure_id("K", candidate.graph),
            "graph": _canonical_graph_value(candidate.graph),
        }
        for candidate in request.candidate_closures
    ]
    _require(
        len({row["closure_id"] for row in rows}) == len(rows),
        "OPAQUE_CLOSURE_ID_COLLISION",
    )
    rows.sort(key=lambda row: row["closure_id"])
    return rows


def _build_prior_public_state(
    request: LiveRevisionRequest,
    compiled_before: Mapping[str, Any],
) -> JsonObject:
    return {
        "schema_version": "ebrt-live-prior-state-v0.6.2.5",
        "checkpoint_id": compiled_before["checkpoint_id"],
        "current_answer": compiled_before["current_answer"],
        "selected_closure_id": _opaque_closure_id("P", request.prior_closure),
        "target_values": [
            {
                "target_id": row["target_id"],
                "target_type": row["target_type"],
                "slot": row["slot"],
                "value": row["value"],
            }
            for row in compiled_before["targets"]
        ],
        "compiled_closure_fingerprint_sha256": compiled_before["fingerprint_sha256"],
    }


def _validate_provider_operation(
    operation: Mapping[str, Any], *, allowed_evidence_ids: set[str]
) -> None:
    expected_keys = {
        "schema_version",
        "operation",
        "event",
        "program",
        "inspection_plan",
        "reinspect_evidence_ids",
        "suppress_evidence_ids",
        "preserve_evidence_ids",
        "source_prior_state_fingerprint_sha256",
        "source_actuator_fingerprint_sha256",
        "source_public_trajectory_fingerprint_sha256",
        "semantic_authority",
        "gradient_boundary",
        "fingerprint_sha256",
    }
    _require(
        set(operation) == expected_keys
        and operation.get("schema_version") == REVISION_OPERATION_SCHEMA,
        "PROVIDER_OPERATION_SCHEMA_INVALID",
    )
    _require(operation.get("operation") == "APPLY_REVISION", "PROVIDER_OPERATION_INVALID")
    _require(
        operation.get("fingerprint_sha256")
        == _fingerprint(_without_fingerprint(operation)),
        "PROVIDER_OPERATION_FINGERPRINT_INVALID",
    )
    event_value = operation.get("event")
    try:
        event = RevisionEvent.model_validate(event_value)
    except ValidationError as error:
        raise LiveRevisionError("PROVIDER_OPERATION_EVENT_INVALID") from error
    plan = operation.get("inspection_plan")
    program = operation.get("program")
    _require(
        isinstance(plan, Mapping) and isinstance(program, Mapping),
        "PROVIDER_INSPECTION_PLAN_INVALID",
    )
    reinspect = operation.get("reinspect_evidence_ids")
    suppress = operation.get("suppress_evidence_ids")
    preserve = operation.get("preserve_evidence_ids")
    _require(
        isinstance(reinspect, list)
        and isinstance(suppress, list)
        and isinstance(preserve, list)
        and all(isinstance(value, str) for value in reinspect + suppress + preserve),
        "PROVIDER_OPERATION_SUMMARY_INVALID",
    )
    _validate_inspection_plan_and_program(
        allowed_evidence_ids=allowed_evidence_ids,
        correction_evidence_id=event.correction_evidence_id,
        source_public_trajectory_fingerprint_sha256=str(
            operation.get("source_public_trajectory_fingerprint_sha256")
        ),
        suppress_evidence_ids=suppress,
        reinspect_evidence_ids=reinspect,
        preserve_evidence_ids=preserve,
        inspection_plan=plan,
        program=program,
    )
    _require(
        set(suppress) == set(event.invalidated_evidence_ids)
        and set(preserve) == set(event.stable_evidence_ids)
        and not (set(reinspect) & (set(suppress) | set(preserve))),
        "PROVIDER_OPERATION_EVENT_SUMMARY_MISMATCH",
    )
    _require(
        operation.get("source_public_trajectory_fingerprint_sha256")
        == plan.get("source_public_trajectory_fingerprint_sha256")
        == program.get("source_public_trajectory_fingerprint_sha256"),
        "PROVIDER_OPERATION_TRAJECTORY_BINDING_INVALID",
    )
    _require(
        not (_recursive_keys(operation) & PROVIDER_FORBIDDEN_KEYS),
        "PROVIDER_PAYLOAD_FORBIDDEN_KEY",
    )


def _build_provider_payload(
    request: LiveRevisionRequest,
    compiled_before: Mapping[str, Any],
    prior: Mapping[str, Any],
    control_map: Mapping[str, Any],
    actuator: Mapping[str, Any],
    actuator_execution: Mapping[str, Any],
) -> JsonObject:
    provider_operation = actuator_execution["emitted_provider_operation"]
    _require(
        control_map["fingerprint_sha256"]
        == _fingerprint(_without_fingerprint(control_map)),
        "PROVIDER_CONTROL_MAP_FINGERPRINT_INVALID",
    )
    expected_actuator = _compile_actuator(
        request, compiled_before, control_map
    )
    _require(
        actuator == expected_actuator,
        "PROVIDER_ACTUATOR_BINDING_INVALID",
    )
    expected_execution = _execute_actuator_program(
        request,
        expected_actuator,
        source_control_map_fingerprint_sha256=control_map[
            "fingerprint_sha256"
        ],
        source_prior_state_fingerprint_sha256=_fingerprint(prior),
    )
    _require(
        actuator_execution == expected_execution,
        "PROVIDER_ACTUATOR_EXECUTION_INVALID",
    )
    _require(
        actuator_execution["source_actuator_fingerprint_sha256"]
        == actuator["fingerprint_sha256"]
        and actuator_execution["source_program_fingerprint_sha256"]
        == actuator["program"]["fingerprint_sha256"]
        and actuator_execution[
            "emitted_provider_operation_fingerprint_sha256"
        ]
        == provider_operation["fingerprint_sha256"],
        "PROVIDER_ACTUATOR_EXECUTION_BINDING_INVALID",
    )
    _require(
        actuator["source_public_trajectory_fingerprint_sha256"]
        == control_map["public_trajectory"]["fingerprint_sha256"]
        == actuator_execution[
            "source_public_trajectory_fingerprint_sha256"
        ]
        == provider_operation[
            "source_public_trajectory_fingerprint_sha256"
        ],
        "PROVIDER_TRAJECTORY_PATCH_BINDING_INVALID",
    )
    _require(
        actuator_execution["trace"]
        == _materialize_program_trace(provider_operation["program"]["steps"])[0],
        "PROVIDER_ACTUATOR_EXECUTION_TRACE_INVALID",
    )
    _require(
        provider_operation["source_prior_state_fingerprint_sha256"]
        == _fingerprint(prior)
        and provider_operation["source_actuator_fingerprint_sha256"]
        == actuator["fingerprint_sha256"],
        "PROVIDER_OPERATION_SOURCE_BINDING_INVALID",
    )
    _require(
        provider_operation["event"] == request.event.model_dump(mode="json")
        and provider_operation["program"] == actuator["program"]
        and provider_operation["inspection_plan"]
        == actuator["inspection_plan"]
        and provider_operation["reinspect_evidence_ids"]
        == actuator["reinspect_evidence_ids"]
        and provider_operation["suppress_evidence_ids"]
        == actuator["suppress_evidence_ids"]
        and provider_operation["preserve_evidence_ids"]
        == actuator["preserve_evidence_ids"],
        "PROVIDER_OPERATION_MATERIAL_BINDING_INVALID",
    )
    _validate_provider_operation(
        provider_operation,
        allowed_evidence_ids={row.evidence_id for row in request.all_raw_evidence},
    )
    payload: JsonObject = {
        "schema_version": PROVIDER_INPUT_SCHEMA,
        "case_id": request.case_id,
        "checkpoint_id": request.checkpoint_id,
        "question": request.question,
        "answer_choices": list(request.answer_choices),
        "decision_slots": [row.model_dump(mode="json") for row in request.decision_slots],
        "all_raw_evidence": [row.model_dump(mode="json") for row in request.all_raw_evidence],
        "allowed_evidence_ids": [row.evidence_id for row in request.all_raw_evidence],
        "candidate_closures": _provider_candidate_rows(request),
        "prior_public_state": dict(prior),
        "apply_revision": dict(provider_operation),
    }
    forbidden = _recursive_keys(payload) & PROVIDER_FORBIDDEN_KEYS
    _require(
        not forbidden,
        "PROVIDER_PAYLOAD_FORBIDDEN_KEY",
        ",".join(sorted(forbidden)),
    )
    return payload


def _public_diff(before: Mapping[str, Any], after: Mapping[str, Any]) -> JsonObject:
    before_targets = {row["target_id"]: row for row in before["targets"]}
    after_targets = {row["target_id"]: row for row in after["targets"]}
    _require(set(before_targets) == set(after_targets), "DIFF_TARGET_SET_MISMATCH")
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
            "schema_version": DIFF_SCHEMA,
            "answer": {
                "before": before["current_answer"],
                "after": after["current_answer"],
            },
            "selected_closure_id": {
                "before": before["selected_closure_id"],
                "after": after["selected_closure_id"],
            },
            "target_values": [
                {
                    "target_id": target_id,
                    "slot": before_targets[target_id]["slot"],
                    "before": before_targets[target_id]["value"],
                    "after": after_targets[target_id]["value"],
                    "changed": (
                        before_targets[target_id]["value"]
                        != after_targets[target_id]["value"]
                    ),
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
                if before_targets[target_id]["target_type"] == "constraint"
                and before_targets[target_id]["value"] == after_targets[target_id]["value"]
                and before_targets[target_id]["all_active_evidence_ids"]
                == after_targets[target_id]["all_active_evidence_ids"]
            ],
        }
    )


def _audit_after(
    request: LiveRevisionRequest,
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> dict[str, bool]:
    active_after = set(after["active_support_evidence_ids"])
    after_edges = {
        (row["source_evidence_id"], row["target_evidence_id"])
        for row in after["invalidation_edges"]
    }
    before_edges = {
        (row["source_evidence_id"], row["target_evidence_id"])
        for row in before["invalidation_edges"]
    }
    event_edges = {
        (request.event.correction_evidence_id, evidence_id)
        for evidence_id in request.event.invalidated_evidence_ids
    }
    expected_after_edges = before_edges | event_edges
    stable = set(request.event.stable_evidence_ids)
    before_targets = {row["target_id"]: row for row in before["targets"]}
    after_targets = {row["target_id"]: row for row in after["targets"]}
    stable_bound = [
        target_id
        for target_id, row in before_targets.items()
        if set(row["all_active_evidence_ids"]) & stable
    ]
    before_support = set(before["active_support_evidence_ids"])
    previously_invalidated = set(before["invalidated_evidence_ids"])
    all_expected_invalidated = previously_invalidated | set(
        request.event.invalidated_evidence_ids
    )
    changed_fact_target_ids = [
        target_id
        for target_id, row in before_targets.items()
        if row["target_type"] == "fact"
        and row["value"] != after_targets[target_id]["value"]
    ]
    target_changed = any(
        before_targets[target_id]["value"] != after_targets[target_id]["value"]
        for target_id in before_targets
    )
    public_diff_observable = (
        before["current_answer"] != after["current_answer"]
        or before["selected_closure_id"] != after["selected_closure_id"]
        or before_support != active_after
        or target_changed
    )
    return {
        "provider_output_schema_valid": True,
        "selected_closure_lineage_bound": bool(after["selected_closure_id"]),
        "correction_evidence_active": request.event.correction_evidence_id in active_after,
        "all_invalidated_evidence_absent": not bool(
            active_after & all_expected_invalidated
        ),
        "invalidation_transition_exact": after_edges == expected_after_edges,
        "prior_invalidations_preserved": before_edges <= after_edges,
        "no_previously_invalidated_evidence_resurrected": not bool(
            active_after & previously_invalidated
        ),
        "changed_fact_targets_exist": bool(changed_fact_target_ids),
        "changed_fact_targets_bind_correction": bool(changed_fact_target_ids)
        and all(
            request.event.correction_evidence_id
            in set(after_targets[target_id]["all_active_evidence_ids"])
            for target_id in changed_fact_target_ids
        ),
        "stable_bound_targets_exist": bool(stable_bound),
        "stable_bound_targets_preserved": bool(stable_bound)
        and all(
            before_targets[target_id]["value"] == after_targets[target_id]["value"]
            and (
                set(before_targets[target_id]["all_active_evidence_ids"]) & stable
            )
            <= set(after_targets[target_id]["all_active_evidence_ids"])
            for target_id in stable_bound
        ),
        "public_diff_observable": public_diff_observable,
    }


def _public_dependency_audit(
    request: LiveRevisionRequest,
    selected_graph: ClosureGraph,
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> JsonObject:
    """Zero-call block/restore probe over the selected public graph only."""

    evidence_order = [row.evidence_id for row in request.all_raw_evidence]
    correction = request.event.correction_evidence_id
    baseline = _structural_closure(
        selected_graph, evidence_order=evidence_order
    )
    active_block = {correction}
    blocked = _structural_closure(
        selected_graph,
        evidence_order=evidence_order,
        blocked_evidence_ids=frozenset(active_block),
    )
    active_block.remove(correction)
    unblocked = _structural_closure(
        selected_graph,
        evidence_order=evidence_order,
        blocked_evidence_ids=frozenset(active_block),
    )
    before_targets = {row["target_id"]: row for row in before["targets"]}
    after_targets = {row["target_id"]: row for row in after["targets"]}
    changed_fact_ids = [
        target_id
        for target_id, row in before_targets.items()
        if row["target_type"] == "fact"
        and row["value"] != after_targets[target_id]["value"]
    ]
    target_rows: list[JsonObject] = []
    for target_id in changed_fact_ids:
        baseline_ids = baseline["targets"][target_id][
            "all_active_evidence_ids"
        ]
        blocked_ids = blocked["targets"][target_id][
            "all_active_evidence_ids"
        ]
        unblocked_ids = unblocked["targets"][target_id][
            "all_active_evidence_ids"
        ]
        target_rows.append(
            {
                "target_id": target_id,
                "baseline_contains_correction": correction in baseline_ids,
                "blocked_contains_correction": correction in blocked_ids,
                "blocked_lineage_changed": blocked_ids != baseline_ids,
                "blocked_lineage_evidence_ids": blocked_ids,
                "unblocked_lineage_exact": unblocked_ids == baseline_ids,
            }
        )
    stable = set(request.event.stable_evidence_ids)
    stable_target_ids = [
        target_id
        for target_id, row in after_targets.items()
        if row["target_type"] == "constraint"
        and set(baseline["targets"][target_id]["all_active_evidence_ids"])
        & stable
    ]
    stable_evidence_preserved = bool(stable_target_ids) and all(
        (
            set(baseline["targets"][target_id]["all_active_evidence_ids"])
            & stable
        )
        == (
            set(blocked["targets"][target_id]["all_active_evidence_ids"])
            & stable
        )
        for target_id in stable_target_ids
    )
    expected_event_edges = {
        (correction, evidence_id)
        for evidence_id in request.event.invalidated_evidence_ids
    }
    baseline_edges = {
        (row["source_evidence_id"], row["target_evidence_id"])
        for row in baseline["invalidation_edges"]
    }
    blocked_edges = {
        (row["source_evidence_id"], row["target_evidence_id"])
        for row in blocked["invalidation_edges"]
    }
    checks = {
        "changed_fact_targets_exist": bool(target_rows),
        "correction_bound_before_block": bool(target_rows)
        and all(row["baseline_contains_correction"] for row in target_rows),
        "correction_absent_when_blocked": bool(target_rows)
        and all(not row["blocked_contains_correction"] for row in target_rows),
        "changed_fact_lineage_changes_when_blocked": bool(target_rows)
        and all(row["blocked_lineage_changed"] for row in target_rows),
        "event_consistency_breaks_when_blocked": expected_event_edges
        <= baseline_edges
        and not expected_event_edges <= blocked_edges,
        "stable_evidence_binding_preserved": stable_evidence_preserved,
        "unblocked_recomputation_exact": not active_block
        and canonical_json(unblocked)
        == canonical_json(baseline),
    }
    return _seal(
        {
            "schema_version": DEPENDENCY_AUDIT_SCHEMA,
            "mode": "PUBLIC_GRAPH_BLOCK_RESTORE",
            "scope": "SELECTED_CALLER_SUPPLIED_PUBLIC_GRAPH_ONLY",
            "blocked_evidence_id": correction,
            "provider_calls": 0,
            "hosted_output_regenerated": False,
            "structural_dependency_status": (
                "PASS" if all(checks.values()) else "FAIL"
            ),
            "hosted_causality_status": "NOT_ASSESSED",
            "counterfactual_output_effect_status": "NOT_ASSESSED",
            "baseline_closure_fingerprint_sha256": _fingerprint(baseline),
            "blocked_closure_fingerprint_sha256": _fingerprint(blocked),
            "unblocked_closure_fingerprint_sha256": _fingerprint(unblocked),
            "mask_trace": [
                {
                    "phase": "BLOCK",
                    "blocked_evidence_ids": [correction],
                    "closure_fingerprint_sha256": _fingerprint(blocked),
                },
                {
                    "phase": "UNBLOCK_AND_RECOMPUTE",
                    "blocked_evidence_ids": [],
                    "closure_fingerprint_sha256": _fingerprint(unblocked),
                },
            ],
            "changed_fact_targets": target_rows,
            "stable_target_ids": stable_target_ids,
            "checks": checks,
        }
    )


class RevisionProvider(Protocol):
    """One-attempt provider boundary used by the live engine."""

    model_label: str

    def generate(
        self, payload: Mapping[str, Any]
    ) -> tuple[Mapping[str, Any], ProviderReceipt | Mapping[str, Any]]: ...


class OpenAILiveRevisionProvider(InstrumentedResponsesClientBase):
    """Pinned GPT-5.6 Responses adapter with sanitized one-call receipts."""

    model_label = MODEL

    def __init__(self, *, client: OpenAI | None = None) -> None:
        super().__init__(
            model=MODEL,
            reasoning_effort=REASONING_EFFORT,
            timeout_seconds=TIMEOUT_SECONDS,
            client=client,
        )

    def generate(
        self, payload: Mapping[str, Any]
    ) -> tuple[Mapping[str, Any], ProviderReceipt]:
        parsed, receipt = self._parse(
            input_payload=json.loads(canonical_json(dict(payload))),
            instructions=PROVIDER_INSTRUCTIONS,
            text_format=LiveProviderOutput,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )
        _require(
            isinstance(parsed, LiveProviderOutput),
            "PROVIDER_RUNTIME_OUTPUT_TYPE_INVALID",
            http_status=502,
        )
        return parsed.model_dump(mode="json"), receipt


class ScriptedLiveRevisionProvider:
    """Deterministic network-zero provider for plumbing and browser QA only."""

    model_label = "SCRIPTED_TEST_ONLY"

    def __init__(self) -> None:
        self.attempts = 0

    @staticmethod
    def _choose_candidate(payload: Mapping[str, Any]) -> Mapping[str, Any]:
        operation = payload["apply_revision"]
        event = operation["event"]
        invalidated = set(event["invalidated_evidence_ids"])
        expected_edges = {
            (event["correction_evidence_id"], evidence_id)
            for evidence_id in invalidated
        }
        for candidate in payload["candidate_closures"]:
            graph = candidate["graph"]
            active = {
                evidence_id
                for support in graph["support_nodes"]
                for evidence_id in support["evidence_ids"]
            }
            edges = {
                (row["source_evidence_id"], row["target_evidence_id"])
                for row in graph["invalidation_edges"]
            }
            if (
                event["correction_evidence_id"] in active
                and not (active & invalidated)
                and expected_edges <= edges
            ):
                return candidate
        raise LiveRevisionError("SCRIPTED_EVENT_CONSISTENT_CANDIDATE_MISSING")

    def generate(
        self, payload: Mapping[str, Any]
    ) -> tuple[Mapping[str, Any], ProviderReceipt]:
        self.attempts += 1
        _require(self.attempts == 1, "SCRIPTED_PROVIDER_REUSED", http_status=500)
        _validate_provider_operation(
            payload["apply_revision"],
            allowed_evidence_ids=set(payload["allowed_evidence_ids"]),
        )
        candidate = self._choose_candidate(payload)
        output = {
            "schema_version": PROVIDER_OUTPUT_SCHEMA,
            "checkpoint_id": payload["checkpoint_id"],
            "current_answer": payload["answer_choices"][-1],
            "selected_closure_id": candidate["closure_id"],
            "target_values": [
                {
                    "target_id": f"{slot['target_type']}:{slot['slot_id']}",
                    "target_type": slot["target_type"],
                    "slot": slot["slot_id"],
                    "value": slot["allowed_values"][-1],
                }
                for slot in payload["decision_slots"]
            ],
        }
        receipt = ProviderReceipt(
            provider="scripted_test_provider",
            requested_model=None,
            returned_model=None,
            logical_calls=1,
            api_calls=1,
            latency_ms=0.0,
            request_fingerprint=_fingerprint(payload),
            prompt_fingerprint=_fingerprint(PROVIDER_INSTRUCTIONS),
            usage=ProviderUsage(
                exact_provider_tokens=True,
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                cached_input_tokens=0,
                cache_write_tokens=0,
                reasoning_tokens=0,
            ),
            metadata={
                "status": "completed",
                "mode": "SCRIPTED_TEST_ONLY",
                "retry_count": 0,
                "store": False,
                "previous_response_id": False,
            },
        )
        return output, receipt


def _receipt_mapping(value: ProviderReceipt | Mapping[str, Any]) -> JsonObject:
    if isinstance(value, ProviderReceipt):
        return value.to_dict()
    _require(isinstance(value, Mapping), "PROVIDER_RECEIPT_INVALID", http_status=502)
    return _clone(dict(value))


def _validate_receipt(
    receipt: Mapping[str, Any], payload: Mapping[str, Any]
) -> JsonObject:
    _require(
        receipt.get("logical_calls") == 1 and receipt.get("api_calls") == 1,
        "PROVIDER_RECEIPT_CALL_COUNT_INVALID",
        http_status=502,
    )
    _require(
        receipt.get("request_fingerprint") == _fingerprint(payload),
        "PROVIDER_RECEIPT_INPUT_BINDING_INVALID",
        http_status=502,
    )
    _require(
        receipt.get("prompt_fingerprint") == _fingerprint(PROVIDER_INSTRUCTIONS),
        "PROVIDER_RECEIPT_PROMPT_BINDING_INVALID",
        http_status=502,
    )
    usage = receipt.get("usage")
    _require(isinstance(usage, Mapping), "PROVIDER_RECEIPT_USAGE_INVALID", http_status=502)
    normalized_usage: JsonObject = {}
    for key in ("input_tokens", "output_tokens", "total_tokens", "reasoning_tokens"):
        raw = usage.get(key)
        _require(
            raw is None or (isinstance(raw, int) and not isinstance(raw, bool) and raw >= 0),
            "PROVIDER_RECEIPT_USAGE_INVALID",
            key,
            http_status=502,
        )
        normalized_usage[key] = 0 if raw is None else int(raw)
    latency = receipt.get("latency_ms")
    _require(
        isinstance(latency, (int, float))
        and not isinstance(latency, bool)
        and math.isfinite(float(latency))
        and float(latency) >= 0.0,
        "PROVIDER_RECEIPT_LATENCY_INVALID",
        http_status=502,
    )
    return {
        "logical_calls": 1,
        "api_calls": 1,
        "latency_ms": float(latency),
        **normalized_usage,
    }


def _verification_rows(audit: Mapping[str, bool]) -> list[JsonObject]:
    labels = {
        "provider_output_schema_valid": "Provider output schema",
        "selected_closure_lineage_bound": "Selected closure lineage",
        "correction_evidence_active": "Correction evidence active",
        "all_invalidated_evidence_absent": "All invalidated support removed",
        "invalidation_transition_exact": "Exact invalidation transition",
        "prior_invalidations_preserved": "Prior invalidations preserved",
        "no_previously_invalidated_evidence_resurrected": "No invalidated evidence resurrected",
        "changed_fact_targets_exist": "Changed fact target",
        "changed_fact_targets_bind_correction": "Fact-local correction lineage",
        "stable_bound_targets_exist": "Stable target binding",
        "stable_bound_targets_preserved": "Stable target preserved",
        "public_diff_observable": "Public output diff",
        "public_structural_dependency_block_restore": "Public structural dependency",
    }
    rows = [
        {
            "label": labels[key],
            "detail": key,
            "status": "PASS" if passed else "FAIL",
        }
        for key, passed in audit.items()
    ]
    rows.extend(
        [
            {
                "label": "Semantic correctness",
                "detail": "Reserved gold fields are rejected; caller semantic content is unverified",
                "status": "NOT_ASSESSED",
            },
            {
                "label": "Effect attribution",
                "detail": "One regeneration is not a causal contrast",
                "status": "NOT_ASSESSED",
            },
        ]
    )
    return rows


def _derived_request_provenance(
    request: LiveRevisionRequest,
) -> tuple[Literal["CALLER_SUPPLIED_UNVERIFIED", "CONTAMINATED_REGRESSION_FIXTURE"], str | None]:
    try:
        expected = build_demo_request(request_id=request.request_id)
        source = _validated_demo_source()
    except (LiveRevisionError, KeyError, OSError, TypeError, ValueError):
        return "CALLER_SUPPLIED_UNVERIFIED", None
    if request.model_dump(mode="json") != expected:
        return "CALLER_SUPPLIED_UNVERIFIED", None
    return "CONTAMINATED_REGRESSION_FIXTURE", str(source["fingerprint_sha256"])


class EBRTRevisionEngine:
    """Typed public invalidation-revision engine; one provider attempt per call."""

    def execute(
        self, request_value: Mapping[str, Any] | LiveRevisionRequest, provider: RevisionProvider
    ) -> JsonObject:
        request = (
            request_value
            if isinstance(request_value, LiveRevisionRequest)
            else validate_request_mapping(request_value)
        )
        request_mapping = request.model_dump(mode="json")
        input_fingerprint = _fingerprint(request_mapping)
        input_provenance, source_fingerprint = _derived_request_provenance(request)
        before_output = request.prior_public_state.model_dump(mode="json")
        compiled_before = _compile_output(
            request,
            before_output,
            request.prior_closure,
            phase_id="before_event",
            evidence_order=request.before_horizon_evidence_ids,
            allowed_closure_ids={request.prior_public_state.selected_closure_id},
            require_live_schema=False,
        )
        control_map = _derive_control_map(request, compiled_before)
        actuator = _compile_actuator(request, compiled_before, control_map)
        prior_payload = _build_prior_public_state(request, compiled_before)
        actuator_execution = _execute_actuator_program(
            request,
            actuator,
            source_control_map_fingerprint_sha256=control_map[
                "fingerprint_sha256"
            ],
            source_prior_state_fingerprint_sha256=_fingerprint(prior_payload),
        )
        payload = _build_provider_payload(
            request,
            compiled_before,
            prior_payload,
            control_map,
            actuator,
            actuator_execution,
        )
        try:
            raw_output, raw_receipt = provider.generate(payload)
        except OpenAIProviderBoundaryError as error:
            raise LiveRevisionError(
                f"PROVIDER_{error.phase.upper()}_{error.reason_code.upper()}",
                http_status=502,
            ) from None
        except OpenAIBoundaryCapabilityError as error:
            raise LiveRevisionError(
                f"PROVIDER_CAPABILITY_{error.reason_code.upper()}",
                http_status=503,
            ) from None
        receipt = _receipt_mapping(raw_receipt)
        accounting = _validate_receipt(receipt, payload)
        try:
            provider_output = LiveProviderOutput.model_validate(raw_output).model_dump(
                mode="json"
            )
        except ValidationError as error:
            raise LiveRevisionError(
                "PROVIDER_OUTPUT_SCHEMA_INVALID", http_status=502
            ) from error
        candidate_by_id = {
            _opaque_closure_id("K", candidate.graph): candidate.graph
            for candidate in request.candidate_closures
        }
        selected_id = provider_output["selected_closure_id"]
        _require(
            selected_id in candidate_by_id,
            "PROVIDER_OUTPUT_CLOSURE_UNKNOWN",
            http_status=502,
        )
        compiled_after = _compile_output(
            request,
            provider_output,
            candidate_by_id[selected_id],
            phase_id="after_event",
            evidence_order=[row.evidence_id for row in request.all_raw_evidence],
            allowed_closure_ids=set(candidate_by_id),
            require_live_schema=True,
        )
        diff = _public_diff(compiled_before, compiled_after)
        dependency_audit = _public_dependency_audit(
            request,
            candidate_by_id[selected_id],
            compiled_before,
            compiled_after,
        )
        audit = {
            **_audit_after(request, compiled_before, compiled_after),
            "public_structural_dependency_block_restore": dependency_audit[
                "structural_dependency_status"
            ]
            == "PASS",
        }
        mechanism_pass = (
            control_map["status"] == "PASS"
            and bool(actuator["gradient_stops_here"])
            and all(actuator["checks"].values())
            and actuator_execution["status"] == "COMPLETED"
            and all(actuator_execution["checks"].values())
        )
        operational_pass = mechanism_pass and all(audit.values())

        invalidated = set(request.event.invalidated_evidence_ids)
        stable = set(request.event.stable_evidence_ids)
        evidence_context = []
        for row in request.all_raw_evidence:
            if row.evidence_id == request.event.correction_evidence_id:
                role = "late_event"
            elif row.evidence_id in invalidated:
                role = "invalidated"
            elif row.evidence_id in stable:
                role = "stable_constraint"
            else:
                role = "public_evidence"
            evidence_context.append({**row.model_dump(mode="json"), "role": role})
        correction_text = next(
            row.text
            for row in request.all_raw_evidence
            if row.evidence_id == request.event.correction_evidence_id
        )
        usage = accounting
        response = {
            "schema_version": RESPONSE_SCHEMA,
            "request_id": request.request_id,
            "status": "COMPLETE",
            "mode": "LIVE_AFTER_REGENERATION",
            "case_id": request.case_id,
            "input_fingerprint_sha256": input_fingerprint,
            "context": {
                "question": request.question,
                "model": provider.model_label,
                "input_provenance": input_provenance,
                "source_artifact_fingerprint_sha256": source_fingerprint,
                "evidence": evidence_context,
                "before_horizon_evidence_ids": list(
                    request.before_horizon_evidence_ids
                ),
                "late_event": {
                    "evidence_id": request.event.correction_evidence_id,
                    "event_id": request.event.event_id,
                    "text": correction_text,
                    "invalidated_evidence_ids": list(
                        request.event.invalidated_evidence_ids
                    ),
                    "stable_evidence_ids": list(request.event.stable_evidence_ids),
                },
            },
            "mechanism": {
                "status": "PASS" if mechanism_pass else "FAIL",
                "actual_before_state": {
                    "fingerprint_sha256": control_map["actual_before_state"][
                        "fingerprint_sha256"
                    ],
                    "source_selected_closure_id": control_map[
                        "actual_before_state"
                    ]["source_selected_closure_id"],
                    "initial_scalar": control_map["actual_before_state"][
                        "initial_scalar"
                    ],
                    "initial_vector": control_map["actual_before_state"][
                        "initial_vector"
                    ],
                    "axis_order": control_map["actual_before_state"][
                        "axis_order"
                    ],
                    "active_support_evidence_ids": control_map[
                        "actual_before_state"
                    ]["active_support_evidence_ids"],
                },
                "surrogate": {
                    "objective_before": control_map["objective_before"],
                    "objective_after": control_map["objective_after"],
                    "terminal_target": control_map["terminal_target"],
                    "dtype": control_map["dtype"],
                    "backward_calls": control_map["backward_calls"],
                    "maximum_finite_difference_error": control_map[
                        "maximum_finite_difference_error"
                    ],
                    "inspection_temperature": control_map[
                        "inspection_temperature"
                    ],
                    "surrogate_terminal_state_before": control_map[
                        "surrogate_terminal_state_before"
                    ],
                    "surrogate_terminal_state_after": control_map[
                        "surrogate_terminal_state_after"
                    ],
                },
                "public_trajectory": control_map["public_trajectory"],
                "public_control_map": {
                    "fingerprint_sha256": control_map["fingerprint_sha256"],
                    "control_l2": control_map["control_l2"],
                    "max_control_l2": control_map["max_control_l2"],
                    "provider_visible_allocation_transform": control_map[
                        "provider_visible_allocation_transform"
                    ],
                    "semantic_operation_source": control_map[
                        "semantic_operation_source"
                    ],
                    "credit_rows": control_map["credit_rows"],
                    "allocation_domain_evidence_ids": control_map[
                        "allocation_domain_evidence_ids"
                    ],
                    "checks": control_map["checks"],
                },
                "compiled_actuator": {
                    "fingerprint_sha256": actuator["fingerprint_sha256"],
                    "reinspect_evidence_ids": actuator[
                        "reinspect_evidence_ids"
                    ],
                    "reinspect_source": actuator["reinspect_source"],
                    "suppress_evidence_ids": actuator[
                        "suppress_evidence_ids"
                    ],
                    "suppress_source": actuator["suppress_source"],
                    "preserve_evidence_ids": actuator[
                        "preserve_evidence_ids"
                    ],
                    "preserve_source": actuator["preserve_source"],
                    "correction_evidence_id": actuator[
                        "correction_evidence_id"
                    ],
                    "source_control_map_fingerprint_sha256": actuator[
                        "source_control_map_fingerprint_sha256"
                    ],
                    "source_public_trajectory_fingerprint_sha256": actuator[
                        "source_public_trajectory_fingerprint_sha256"
                    ],
                    "inspection_plan": actuator["inspection_plan"],
                    "program": actuator["program"],
                    "checks": actuator["checks"],
                    "gradient_stops_here": actuator["gradient_stops_here"],
                },
                "actuator_execution": {
                    "fingerprint_sha256": actuator_execution[
                        "fingerprint_sha256"
                    ],
                    "status": actuator_execution["status"],
                    "source_actuator_fingerprint_sha256": actuator_execution[
                        "source_actuator_fingerprint_sha256"
                    ],
                    "source_program_fingerprint_sha256": actuator_execution[
                        "source_program_fingerprint_sha256"
                    ],
                    "source_public_trajectory_fingerprint_sha256": actuator_execution[
                        "source_public_trajectory_fingerprint_sha256"
                    ],
                    "final_state": actuator_execution["final_state"],
                    "trace": actuator_execution["trace"],
                    "emitted_provider_operation_fingerprint_sha256": actuator_execution[
                        "emitted_provider_operation_fingerprint_sha256"
                    ],
                    "provider_payload_fingerprint_sha256": _fingerprint(payload),
                    "provider_payload_receipt_binding_status": "PASS",
                    "checks": actuator_execution["checks"],
                },
                "boundary": (
                    "Gradient stops at bounded time-local controls in the public "
                    "revision trajectory. JSON projection, GPT-5.6 generation, and "
                    "verification are not backpropagated through."
                ),
            },
            "output": {
                "before": {
                    "public_output": compiled_before["normalized_output"],
                    "compiled_output_fingerprint_sha256": compiled_before[
                        "fingerprint_sha256"
                    ],
                    "active_support_evidence_ids": compiled_before[
                        "active_support_evidence_ids"
                    ],
                    "invalidated_evidence_ids": compiled_before[
                        "invalidated_evidence_ids"
                    ],
                    "invalidation_edges": compiled_before["invalidation_edges"],
                },
                "after": {
                    "public_output": compiled_after["normalized_output"],
                    "compiled_output_fingerprint_sha256": compiled_after[
                        "fingerprint_sha256"
                    ],
                    "active_support_evidence_ids": compiled_after[
                        "active_support_evidence_ids"
                    ],
                    "invalidated_evidence_ids": compiled_after[
                        "invalidated_evidence_ids"
                    ],
                    "invalidation_edges": compiled_after["invalidation_edges"],
                },
                "diff": {
                    key: value
                    for key, value in diff.items()
                    if key not in {"schema_version", "fingerprint_sha256", "invalidation_added_edges"}
                },
            },
            "verification": {
                "rows": _verification_rows(audit),
                "operational_acceptance_status": (
                    "PASS" if operational_pass else "FAIL"
                ),
                "provider_output_schema_status": "PASS",
                "lineage_binding_status": (
                    "PASS" if all(audit.values()) else "FAIL"
                ),
                "public_actuator_execution_status": (
                    "PASS" if all(actuator_execution["checks"].values()) else "FAIL"
                ),
                "provider_delivery_status": "PASS",
                "provider_uptake_status": "NOT_ASSESSED",
                "structural_dependency_status": dependency_audit[
                    "structural_dependency_status"
                ],
                "counterfactual_output_effect_status": "NOT_ASSESSED",
                "semantic_correctness_status": "NOT_ASSESSED",
                "effect_attribution_status": "NOT_ASSESSED",
                "provider_attempts": 1,
            },
            "public_dependency_audit": dependency_audit,
            "accounting": {
                "api_calls": usage["api_calls"],
                "logical_calls": usage["logical_calls"],
                "input_tokens": usage["input_tokens"],
                "output_tokens": usage["output_tokens"],
                "reasoning_tokens": usage["reasoning_tokens"],
                "total_tokens": usage["total_tokens"],
                "latency_ms": usage["latency_ms"],
            },
            "claim_boundary": list(CLAIM_BOUNDARY),
        }
        return _seal(response)


def _validated_json_file(path: Path, *, label: str) -> JsonObject:
    _require(path.is_file() and not path.is_symlink(), "DEMO_SOURCE_UNAVAILABLE", label)
    value = strict_json_bytes(path.read_bytes(), label=label)
    _require(isinstance(value, Mapping), "DEMO_SOURCE_INVALID", label)
    value = dict(value)
    fingerprint = value.get("fingerprint_sha256")
    _require(
        isinstance(fingerprint, str)
        and fingerprint == _fingerprint(_without_fingerprint(value)),
        "DEMO_SOURCE_FINGERPRINT_INVALID",
        label,
    )
    return value


def _validated_demo_source(
    *,
    provider_inputs_path: Path = DEMO_PROVIDER_INPUTS_PATH,
    manifest_path: Path = DEMO_MANIFEST_PATH,
) -> JsonObject:
    """Bind the contaminated demo adapter to the published v0.6.2.1 bytes."""

    _require(
        manifest_path.is_file() and not manifest_path.is_symlink(),
        "DEMO_MANIFEST_UNAVAILABLE",
    )
    manifest_bytes = manifest_path.read_bytes()
    _require(
        hashlib.sha256(manifest_bytes).hexdigest() == PINNED_DEMO_MANIFEST_SHA256,
        "DEMO_MANIFEST_PIN_MISMATCH",
    )
    manifest = strict_json_bytes(manifest_bytes, label="demo_manifest")
    _require(isinstance(manifest, Mapping), "DEMO_MANIFEST_INVALID")
    artifacts = manifest.get("artifacts")
    _require(isinstance(artifacts, Mapping), "DEMO_MANIFEST_ARTIFACTS_INVALID")
    provider_entry = artifacts.get("provider_inputs.json")
    _require(isinstance(provider_entry, Mapping), "DEMO_MANIFEST_PROVIDER_INPUTS_MISSING")
    _require(
        provider_entry.get("sha256") == PINNED_DEMO_PROVIDER_INPUTS_SHA256,
        "DEMO_MANIFEST_PROVIDER_INPUTS_PIN_MISMATCH",
    )
    _require(
        provider_inputs_path.is_file() and not provider_inputs_path.is_symlink(),
        "DEMO_SOURCE_UNAVAILABLE",
        "demo_provider_inputs",
    )
    provider_bytes = provider_inputs_path.read_bytes()
    _require(
        hashlib.sha256(provider_bytes).hexdigest()
        == PINNED_DEMO_PROVIDER_INPUTS_SHA256,
        "DEMO_SOURCE_BYTE_PIN_MISMATCH",
    )
    source = _validated_json_file(
        provider_inputs_path, label="demo_provider_inputs"
    )
    _require(
        source.get("fingerprint_sha256")
        == PINNED_DEMO_PROVIDER_INPUTS_FINGERPRINT,
        "DEMO_SOURCE_FINGERPRINT_PIN_MISMATCH",
    )
    return source


def build_demo_request(*, request_id: str | None = None) -> JsonObject:
    """Adapt only the public provider inputs from sealed v0.6.2.1."""

    source = _validated_demo_source()
    rows = source.get("payloads")
    _require(isinstance(rows, list) and len(rows) == 2, "DEMO_PHASES_INVALID")
    phase_by_id = {
        row.get("phase_id"): row.get("payload")
        for row in rows
        if isinstance(row, Mapping)
    }
    before = phase_by_id.get("before_event")
    after = phase_by_id.get("after_event")
    _require(isinstance(before, Mapping) and isinstance(after, Mapping), "DEMO_PHASES_INVALID")
    prior = after.get("prior_public_state")
    operation = after.get("apply_revision")
    _require(isinstance(prior, Mapping) and isinstance(operation, Mapping), "DEMO_DYNAMIC_INPUT_INVALID")
    selected_prior_id = prior.get("selected_closure_id")
    prior_candidates = before.get("candidate_closures")
    _require(isinstance(prior_candidates, list), "DEMO_PRIOR_CATALOG_INVALID")
    prior_candidate = next(
        (
            row
            for row in prior_candidates
            if isinstance(row, Mapping) and row.get("closure_id") == selected_prior_id
        ),
        None,
    )
    _require(isinstance(prior_candidate, Mapping), "DEMO_PRIOR_CLOSURE_MISSING")
    candidates = after.get("candidate_closures")
    _require(isinstance(candidates, list) and candidates, "DEMO_AFTER_CATALOG_INVALID")
    target_type_by_slot: dict[str, str] = {}
    for candidate in candidates:
        for target in candidate["graph"]["targets"]:
            slot = target["slot"]
            observed = target["target_type"]
            previous = target_type_by_slot.setdefault(slot, observed)
            _require(previous == observed, "DEMO_TARGET_TYPE_DRIFT", slot)
    slots = []
    for row in after["decision_slots"]:
        slot_id = row["slot_id"]
        _require(slot_id in target_type_by_slot, "DEMO_SLOT_TARGET_TYPE_MISSING", slot_id)
        slots.append({**dict(row), "target_type": target_type_by_slot[slot_id]})
    event = operation.get("event")
    _require(isinstance(event, Mapping), "DEMO_EVENT_INVALID")
    request = {
        "schema_version": REQUEST_SCHEMA,
        "request_id": request_id or f"live-{uuid.uuid4()}",
        "case_id": after["case_id"],
        "checkpoint_id": after["checkpoint_id"],
        "question": after["question"],
        "answer_choices": after["answer_choices"],
        "decision_slots": slots,
        "all_raw_evidence": after["all_raw_evidence"],
        "before_horizon_evidence_ids": before["allowed_evidence_ids"],
        "prior_public_state": {
            key: prior[key]
            for key in (
                "schema_version",
                "checkpoint_id",
                "current_answer",
                "selected_closure_id",
                "target_values",
            )
        },
        "prior_closure": prior_candidate["graph"],
        "candidate_closures": candidates,
        "event": {
            "event_id": event["event_id"],
            "correction_evidence_id": event["correction_evidence_id"],
            "invalidated_evidence_ids": event["invalidated_evidence_ids"],
            "stable_evidence_ids": operation["preserve_evidence_ids"],
        },
        "reinspection_count": len(operation["reinspect_evidence_ids"]),
    }
    return validate_request_mapping(request).model_dump(mode="json")


def _synthetic_generic_request(*, request_id: str = "synthetic-generic-001") -> JsonObject:
    """Second topology proving that the engine has no R/POLISH fixture IDs."""

    def graph(*, legacy: bool) -> JsonObject:
        if legacy:
            fact_evidence = ["E-old", "E-correct"]
            edges: list[JsonObject] = []
        else:
            fact_evidence = ["E-bridge", "E-correct"]
            edges = [
                {
                    "source_evidence_id": "E-correct",
                    "target_evidence_id": "E-old",
                }
            ]
        return {
            "support_nodes": [
                {"support_id": "support:decision", "evidence_ids": fact_evidence},
                {"support_id": "support:format", "evidence_ids": ["E-stable"]},
            ],
            "targets": [
                {
                    "target_id": "fact:route",
                    "target_type": "fact",
                    "slot": "route",
                    "direct_support_ids": ["support:decision"],
                    "depends_on_target_ids": [],
                },
                {
                    "target_id": "constraint:format",
                    "target_type": "constraint",
                    "slot": "format",
                    "direct_support_ids": ["support:format"],
                    "depends_on_target_ids": [],
                },
            ],
            "invalidation_edges": edges,
        }

    prior_graph = {
        "support_nodes": [
            {"support_id": "support:legacy", "evidence_ids": ["E-old"]},
            {"support_id": "support:format", "evidence_ids": ["E-stable"]},
        ],
        "targets": [
            {
                "target_id": "fact:route",
                "target_type": "fact",
                "slot": "route",
                "direct_support_ids": ["support:legacy"],
                "depends_on_target_ids": [],
            },
            {
                "target_id": "constraint:format",
                "target_type": "constraint",
                "slot": "format",
                "direct_support_ids": ["support:format"],
                "depends_on_target_ids": [],
            },
        ],
        "invalidation_edges": [],
    }
    value: JsonObject = {
        "schema_version": REQUEST_SCHEMA,
        "request_id": request_id,
        "case_id": "generic_route_switch",
        "checkpoint_id": "generic_route_switch:after",
        "question": "Choose OLD or NEW after applying the typed correction.",
        "answer_choices": ["OLD", "NEW"],
        "decision_slots": [
            {
                "slot_id": "route",
                "target_type": "fact",
                "description": "active public route",
                "allowed_values": ["HOLD", "SWITCH"],
            },
            {
                "slot_id": "format",
                "target_type": "constraint",
                "description": "stable output format",
                "allowed_values": ["FIXED"],
            },
        ],
        "all_raw_evidence": [
            {"evidence_id": "E-old", "text": "The initial route is HOLD."},
            {"evidence_id": "E-stable", "text": "The format remains FIXED."},
            {"evidence_id": "E-bridge", "text": "The alternate route is available."},
            {
                "evidence_id": "E-correct",
                "text": "The late correction invalidates E-old and selects the alternate route.",
            },
        ],
        "before_horizon_evidence_ids": ["E-old", "E-stable", "E-bridge"],
        "prior_public_state": {
            "schema_version": "generic-public-state-v1",
            "checkpoint_id": "generic_route_switch:before",
            "current_answer": "OLD",
            "selected_closure_id": "closure:prior",
            "target_values": [
                {
                    "target_id": "fact:route",
                    "target_type": "fact",
                    "slot": "route",
                    "value": "HOLD",
                },
                {
                    "target_id": "constraint:format",
                    "target_type": "constraint",
                    "slot": "format",
                    "value": "FIXED",
                },
            ],
        },
        "prior_closure": prior_graph,
        "candidate_closures": [
            {"closure_id": "closure:event", "graph": graph(legacy=False)},
            {"closure_id": "closure:mixed", "graph": graph(legacy=True)},
        ],
        "event": {
            "event_id": "event:route-correction",
            "correction_evidence_id": "E-correct",
            "invalidated_evidence_ids": ["E-old"],
            "stable_evidence_ids": ["E-stable"],
        },
        "reinspection_count": 2,
    }
    return validate_request_mapping(value).model_dump(mode="json")


def demo_request_envelope() -> JsonObject:
    request = build_demo_request()
    source = _validated_demo_source()
    return _seal({
        "schema_version": DEMO_REQUEST_SCHEMA,
        "provenance": "CONTAMINATED_REGRESSION_FIXTURE",
        "source_artifact_fingerprint_sha256": source["fingerprint_sha256"],
        "request_fingerprint_sha256": _fingerprint(request),
        "request": request,
    })


def capabilities_value(*, provider_mode: str) -> JsonObject:
    return {
        "schema_version": "ebrt-live-capabilities-v0.6.2.5",
        "status": "READY",
        "runtime_label": "EBRT Runtime Preview 4",
        "provider_mode": provider_mode,
        "model": MODEL if provider_mode == "openai" else "SCRIPTED_TEST_ONLY",
        "request_schema_version": REQUEST_SCHEMA,
        "response_schema_version": RESPONSE_SCHEMA,
        "endpoints": [
            "GET /api/health",
            "GET /api/capabilities",
            "GET /api/demo-request",
            "POST /api/apply-revision",
        ],
        "limits": {
            "max_request_bytes": MAX_HTTP_BYTES,
            "max_concurrent_provider_executions": 1,
            "provider_attempts_per_uncached_request": 1,
            "automatic_retries": 0,
            "terminal_result_cache_capacity": MAX_IDEMPOTENCY_ENTRIES,
            "compact_tombstone_capacity": MAX_COMPACT_TOMBSTONES,
            "evicted_identity_reexecution": False,
        },
        "operation_scope": "TYPED_INVALIDATION_REVISION",
        "control_surface": "TEMPORAL_PUBLIC_TRAJECTORY_ADJOINT_CONTROL",
        "actuator_model": "REVISED_PUBLIC_TRAJECTORY_TO_EXECUTABLE_REVISION_PROGRAM",
        "gradient_boundary": "bounded controls in the public revision trajectory",
        "provider_uptake_status": "NOT_ASSESSED",
        "semantic_correctness_status": "NOT_ASSESSED",
        "effect_attribution_status": "NOT_ASSESSED",
    }


ProviderFactory = Callable[[], RevisionProvider]


class RevisionService:
    """Serialized, idempotent façade over the one-attempt revision engine."""

    def __init__(
        self,
        provider_factory: ProviderFactory,
        *,
        provider_mode: Literal["openai", "scripted"],
        terminal_cache_capacity: int = MAX_IDEMPOTENCY_ENTRIES,
        compact_tombstone_capacity: int = MAX_COMPACT_TOMBSTONES,
        relay_token: str | None = None,
        max_provider_attempts_total: int = DEFAULT_RELAY_MAX_PROVIDER_ATTEMPTS_TOTAL,
        max_provider_attempts_per_client: int = DEFAULT_RELAY_MAX_PROVIDER_ATTEMPTS_PER_CLIENT,
    ) -> None:
        _require(
            terminal_cache_capacity > 0,
            "TERMINAL_CACHE_CAPACITY_INVALID",
            http_status=500,
        )
        _require(
            compact_tombstone_capacity >= terminal_cache_capacity,
            "COMPACT_TOMBSTONE_CAPACITY_INVALID",
            http_status=500,
        )
        _require(
            1 <= max_provider_attempts_total <= MAX_RELAY_PROVIDER_ATTEMPT_BUDGET,
            "RELAY_TOTAL_PROVIDER_BUDGET_INVALID",
            http_status=500,
        )
        _require(
            1
            <= max_provider_attempts_per_client
            <= MAX_RELAY_PROVIDER_ATTEMPT_BUDGET,
            "RELAY_CLIENT_PROVIDER_BUDGET_INVALID",
            http_status=500,
        )
        self.provider_factory = provider_factory
        self.provider_mode = provider_mode
        self.engine = EBRTRevisionEngine()
        self.terminal_cache_capacity = terminal_cache_capacity
        self.compact_tombstone_capacity = compact_tombstone_capacity
        self.relay_token = relay_token
        self.max_provider_attempts_total = max_provider_attempts_total
        self.max_provider_attempts_per_client = max_provider_attempts_per_client
        self._gate = threading.BoundedSemaphore(1)
        self._lock = threading.Lock()
        self._terminal: OrderedDict[
            str, tuple[str, Literal["success", "error"], JsonObject, int]
        ] = OrderedDict()
        self._spent: dict[str, str] = {}
        self._inflight: dict[str, str] = {}
        self.provider_attempts_started = 0
        self.provider_attempts_by_client: defaultdict[str, int] = defaultdict(int)

    @property
    def provider_configured(self) -> bool:
        return self.provider_mode == "scripted" or bool(os.environ.get("OPENAI_API_KEY"))

    def health(self) -> JsonObject:
        with self._lock:
            terminal_results_cached = len(self._terminal)
            spent_identities = len(self._spent)
            provider_attempts_started = self.provider_attempts_started
            clients_observed = len(self.provider_attempts_by_client)
        return {
            "schema_version": "ebrt-live-health-v0.6.2.5",
            "status": "READY" if self.provider_configured else "PROVIDER_UNCONFIGURED",
            "provider_mode": self.provider_mode,
            "provider_configured": self.provider_configured,
            "model": MODEL if self.provider_mode == "openai" else "SCRIPTED_TEST_ONLY",
            "credentials_exposed": False,
            "relay": {
                "token_required": self.relay_token is not None,
                "provider_attempt_budgets_enforced": self.relay_token is not None,
                "client_key_format": "HMAC_SHA256_LOWERCASE_HEX_64",
                "provider_attempts_started": provider_attempts_started,
                "provider_attempts_remaining_total": max(
                    0,
                    self.max_provider_attempts_total - provider_attempts_started,
                ),
                "max_provider_attempts_total": self.max_provider_attempts_total,
                "max_provider_attempts_per_client": self.max_provider_attempts_per_client,
                "clients_observed": clients_observed,
            },
            "idempotency": {
                "terminal_results_cached": terminal_results_cached,
                "spent_identities": spent_identities,
                "terminal_result_cache_capacity": self.terminal_cache_capacity,
                "compact_tombstone_capacity": self.compact_tombstone_capacity,
            },
        }

    def _store_terminal_locked(
        self,
        request_id: str,
        fingerprint: str,
        terminal_kind: Literal["success", "error"],
        value: JsonObject,
        http_status: int,
    ) -> None:
        self._spent[request_id] = fingerprint
        self._terminal[request_id] = (
            fingerprint,
            terminal_kind,
            _clone(value),
            http_status,
        )
        self._terminal.move_to_end(request_id)
        while len(self._terminal) > self.terminal_cache_capacity:
            self._terminal.popitem(last=False)

    def apply(
        self,
        request_value: Mapping[str, Any],
        *,
        client_key: str = INTERNAL_DIRECT_CLIENT_KEY,
    ) -> tuple[JsonObject, bool]:
        client_key = _require_relay_client_key(client_key)
        request = validate_request_mapping(request_value)
        canonical = request.model_dump(mode="json")
        fingerprint = _fingerprint(canonical)
        request_id = request.request_id
        with self._lock:
            terminal = self._terminal.get(request_id)
            if terminal is not None:
                _require(
                    terminal[0] == fingerprint,
                    "IDEMPOTENCY_KEY_CONFLICT",
                    http_status=409,
                )
                self._terminal.move_to_end(request_id)
                if terminal[1] == "success":
                    return _clone(terminal[2]), True
                raise LiveRevisionError(
                    str(terminal[2]["error"]["code"]),
                    http_status=terminal[3],
                    idempotent_replay=True,
                )
            spent_fingerprint = self._spent.get(request_id)
            if spent_fingerprint is not None:
                _require(
                    spent_fingerprint == fingerprint,
                    "IDEMPOTENCY_KEY_CONFLICT",
                    http_status=409,
                )
                raise LiveRevisionError(
                    "IDEMPOTENCY_RESULT_EVICTED",
                    http_status=410,
                    idempotent_replay=True,
                )
            inflight = self._inflight.get(request_id)
            if inflight is not None:
                _require(
                    inflight == fingerprint,
                    "IDEMPOTENCY_KEY_CONFLICT",
                    http_status=409,
                )
                raise LiveRevisionError(
                    "REQUEST_ALREADY_IN_FLIGHT", http_status=409
                )
            if len(self._spent) >= self.compact_tombstone_capacity:
                raise LiveRevisionError(
                    "IDEMPOTENCY_CAPACITY_EXHAUSTED", http_status=503
                )
            if self.relay_token is not None:
                if self.provider_attempts_started >= self.max_provider_attempts_total:
                    raise LiveRevisionError(
                        "RELAY_TOTAL_PROVIDER_BUDGET_EXHAUSTED", http_status=429
                    )
                if (
                    self.provider_attempts_by_client.get(client_key, 0)
                    >= self.max_provider_attempts_per_client
                ):
                    raise LiveRevisionError(
                        "RELAY_CLIENT_PROVIDER_BUDGET_EXHAUSTED", http_status=429
                    )
            if not self._gate.acquire(blocking=False):
                raise LiveRevisionError("PROVIDER_BUSY", http_status=429)
            self._inflight[request_id] = fingerprint
            self.provider_attempts_started += 1
            if self.relay_token is not None:
                self.provider_attempts_by_client[client_key] += 1
        try:
            response = self.engine.execute(request, self.provider_factory())
        except LiveRevisionError as error:
            terminal_error = LiveRevisionError(
                error.reason_code,
                http_status=error.http_status,
            )
            with self._lock:
                self._store_terminal_locked(
                    request_id,
                    fingerprint,
                    "error",
                    _error_value(terminal_error),
                    terminal_error.http_status,
                )
                self._inflight.pop(request_id, None)
                self._gate.release()
            raise terminal_error from None
        except Exception:
            terminal_error = LiveRevisionError(
                "INTERNAL_SERVER_ERROR", http_status=500
            )
            with self._lock:
                self._store_terminal_locked(
                    request_id,
                    fingerprint,
                    "error",
                    _error_value(terminal_error),
                    terminal_error.http_status,
                )
                self._inflight.pop(request_id, None)
                self._gate.release()
            raise terminal_error from None
        with self._lock:
            self._store_terminal_locked(
                request_id,
                fingerprint,
                "success",
                response,
                200,
            )
            self._inflight.pop(request_id, None)
            self._gate.release()
        return response, False


def _error_value(error: LiveRevisionError) -> JsonObject:
    return {
        "schema_version": ERROR_SCHEMA,
        "status": "ERROR",
        "error": {"code": error.reason_code},
    }


def _handler_type(service: RevisionService) -> type[http.server.BaseHTTPRequestHandler]:
    class LiveRevisionHandler(http.server.BaseHTTPRequestHandler):
        server_version = "EBRTLive/0.6.2.5-RuntimePreview4"
        sys_version = ""

        def log_message(self, _format: str, *_args: Any) -> None:
            return

        @property
        def _origin(self) -> str | None:
            value = self.headers.get("Origin")
            return value if value else None

        def _origin_allowed(self) -> bool:
            return self._origin is None or self._origin in ALLOWED_ORIGINS

        def _guard_relay_auth(self) -> bool:
            expected = service.relay_token
            if expected is None:
                return True
            if not _relay_token_matches(
                expected,
                self.headers.get(RELAY_TOKEN_HEADER),
            ):
                self._send_json(
                    401,
                    _error_value(
                        LiveRevisionError("RELAY_AUTH_FAILED", http_status=401)
                    ),
                )
                return False
            if not _valid_relay_client_key(
                self.headers.get(RELAY_CLIENT_KEY_HEADER)
            ):
                self._send_json(
                    400,
                    _error_value(
                        LiveRevisionError(
                            "RELAY_CLIENT_KEY_INVALID", http_status=400
                        )
                    ),
                )
                return False
            return True

        def _trusted_client_key(self) -> str:
            if service.relay_token is None:
                return INTERNAL_DIRECT_CLIENT_KEY
            return _require_relay_client_key(
                self.headers.get(RELAY_CLIENT_KEY_HEADER)
            )

        def _send_json(
            self,
            status: int,
            value: Mapping[str, Any],
            *,
            idempotent_replay: bool = False,
        ) -> None:
            raw = _canonical_bytes(value, trailing_newline=True)
            body_sha256 = hashlib.sha256(raw).hexdigest()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("X-EBRT-Body-SHA256", body_sha256)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cross-Origin-Resource-Policy", "same-site")
            self.send_header("Content-Security-Policy", "default-src 'none'")
            self.send_header("Connection", "close")
            if self._origin in ALLOWED_ORIGINS:
                self.send_header("Access-Control-Allow-Origin", self._origin)
                self.send_header(
                    "Access-Control-Expose-Headers",
                    "X-EBRT-Body-SHA256, X-EBRT-Idempotent-Replay",
                )
                self.send_header("Vary", "Origin")
            if idempotent_replay:
                self.send_header("X-EBRT-Idempotent-Replay", "true")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(raw)

        def _guard_origin(self) -> bool:
            if self._origin_allowed():
                return True
            self._send_json(
                403,
                _error_value(
                    LiveRevisionError("ORIGIN_NOT_ALLOWED", http_status=403)
                ),
            )
            return False

        def do_OPTIONS(self) -> None:  # noqa: N802
            if not self._guard_relay_auth() or not self._guard_origin():
                return
            if self.path != "/api/apply-revision":
                self._send_json(
                    404,
                    _error_value(LiveRevisionError("ROUTE_NOT_FOUND", http_status=404)),
                )
                return
            self.send_response(204)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", self._origin or "null")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header(
                "Access-Control-Allow-Headers",
                "Accept, Content-Type, Idempotency-Key, "
                f"{RELAY_TOKEN_HEADER}, {RELAY_CLIENT_KEY_HEADER}",
            )
            self.send_header(
                "Access-Control-Expose-Headers",
                "X-EBRT-Body-SHA256, X-EBRT-Idempotent-Replay",
            )
            self.send_header("Access-Control-Max-Age", "600")
            self.send_header("Vary", "Origin")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            if not self._guard_relay_auth() or not self._guard_origin():
                return
            try:
                if self.path == "/api/health":
                    value = service.health()
                elif self.path == "/api/capabilities":
                    value = capabilities_value(provider_mode=service.provider_mode)
                elif self.path == "/api/demo-request":
                    value = demo_request_envelope()
                else:
                    raise LiveRevisionError("ROUTE_NOT_FOUND", http_status=404)
                self._send_json(200, value)
            except LiveRevisionError as error:
                self._send_json(
                    error.http_status,
                    _error_value(error),
                    idempotent_replay=error.idempotent_replay,
                )
            except Exception:
                self._send_json(
                    500,
                    _error_value(
                        LiveRevisionError("INTERNAL_SERVER_ERROR", http_status=500)
                    ),
                )

        def do_POST(self) -> None:  # noqa: N802
            if not self._guard_relay_auth() or not self._guard_origin():
                return
            try:
                _require(
                    self.path == "/api/apply-revision",
                    "ROUTE_NOT_FOUND",
                    http_status=404,
                )
                content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                _require(
                    content_type == "application/json",
                    "CONTENT_TYPE_MUST_BE_JSON",
                    http_status=415,
                )
                length_value = self.headers.get("Content-Length")
                _require(length_value is not None, "CONTENT_LENGTH_REQUIRED", http_status=411)
                try:
                    length = int(length_value)
                except (TypeError, ValueError):
                    raise LiveRevisionError("CONTENT_LENGTH_INVALID", http_status=400) from None
                _require(0 < length <= MAX_HTTP_BYTES, "REQUEST_BODY_SIZE_INVALID", http_status=413)
                raw = self.rfile.read(length)
                _require(len(raw) == length, "REQUEST_BODY_TRUNCATED", http_status=400)
                value = strict_json_bytes(raw)
                _require(isinstance(value, Mapping), "REQUEST_ROOT_NOT_OBJECT", http_status=400)
                request_id = value.get("request_id")
                idempotency_key = self.headers.get("Idempotency-Key")
                _require(
                    idempotency_key is not None,
                    "IDEMPOTENCY_KEY_REQUIRED",
                    http_status=400,
                )
                _require(
                    isinstance(request_id, str) and idempotency_key == request_id,
                    "IDEMPOTENCY_KEY_MISMATCH",
                    http_status=400,
                )
                response, replay = service.apply(
                    value,
                    client_key=self._trusted_client_key(),
                )
                self._send_json(200, response, idempotent_replay=replay)
            except LiveRevisionError as error:
                self._send_json(
                    error.http_status,
                    _error_value(error),
                    idempotent_replay=error.idempotent_replay,
                )
            except Exception:
                self._send_json(
                    500,
                    _error_value(
                        LiveRevisionError("INTERNAL_SERVER_ERROR", http_status=500)
                    ),
                )

        def do_HEAD(self) -> None:  # noqa: N802
            if not self._guard_relay_auth() or not self._guard_origin():
                return
            self._send_json(
                405,
                _error_value(LiveRevisionError("METHOD_NOT_ALLOWED", http_status=405)),
            )

    return LiveRevisionHandler


class _ThreadingServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _provider_factory(
    mode: Literal["openai", "scripted"],
) -> ProviderFactory:
    if mode == "scripted":
        return ScriptedLiveRevisionProvider
    _require(
        bool(os.environ.get("OPENAI_API_KEY")),
        "OPENAI_API_KEY_UNAVAILABLE",
        http_status=503,
    )
    try:
        OpenAILiveRevisionProvider()
    except OpenAIBoundaryCapabilityError as error:
        raise LiveRevisionError(
            f"PROVIDER_CAPABILITY_{error.reason_code.upper()}", http_status=503
        ) from None
    return OpenAILiveRevisionProvider


def create_http_server(
    *,
    host: str,
    port: int,
    provider_mode: Literal["openai", "scripted"],
) -> tuple[_ThreadingServer, RevisionService]:
    _require(
        host in {"127.0.0.1", "localhost"},
        "NON_LOOPBACK_BIND_FORBIDDEN",
        http_status=400,
    )
    _require(0 <= port <= 65535, "PORT_INVALID", http_status=400)
    relay_token = _relay_token_from_env()
    max_provider_attempts_total = _relay_budget_from_env(
        RELAY_TOTAL_BUDGET_ENV,
        DEFAULT_RELAY_MAX_PROVIDER_ATTEMPTS_TOTAL,
        "RELAY_TOTAL_PROVIDER_BUDGET_INVALID",
    )
    max_provider_attempts_per_client = _relay_budget_from_env(
        RELAY_CLIENT_BUDGET_ENV,
        DEFAULT_RELAY_MAX_PROVIDER_ATTEMPTS_PER_CLIENT,
        "RELAY_CLIENT_PROVIDER_BUDGET_INVALID",
    )
    service = RevisionService(
        _provider_factory(provider_mode),
        provider_mode=provider_mode,
        relay_token=relay_token,
        max_provider_attempts_total=max_provider_attempts_total,
        max_provider_attempts_per_client=max_provider_attempts_per_client,
    )
    server = _ThreadingServer((host, port), _handler_type(service))
    return server, service


def serve(
    *,
    host: str,
    port: int,
    provider_mode: Literal["openai", "scripted"],
) -> None:
    server, service = create_http_server(
        host=host, port=port, provider_mode=provider_mode
    )
    observed_host, observed_port = server.server_address[:2]
    print(
        _pretty(
            {
                "schema_version": "ebrt-live-server-start-v0.6.2.5",
                "status": "READY",
                "url": f"http://{observed_host}:{observed_port}",
                "provider_mode": provider_mode,
                "relay_token_required": service.relay_token is not None,
                "max_provider_attempts_total": service.max_provider_attempts_total,
                "max_provider_attempts_per_client": service.max_provider_attempts_per_client,
                "credentials_exposed": False,
            }
        ),
        end="",
        flush=True,
    )
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


@contextmanager
def _network_denied() -> Iterator[dict[str, int]]:
    counts = {"network_calls": 0}

    def denied(*_args: Any, **_kwargs: Any) -> Any:
        counts["network_calls"] += 1
        raise AssertionError("external network access is forbidden in engine self-test")

    with (
        mock.patch.object(socket, "getaddrinfo", side_effect=denied),
        mock.patch.object(socket, "create_connection", side_effect=denied),
        mock.patch.object(socket.socket, "connect", side_effect=denied),
        mock.patch.object(socket.socket, "connect_ex", side_effect=denied),
    ):
        yield counts


def _http_json(
    port: int,
    method: str,
    path: str,
    *,
    value: Mapping[str, Any] | None = None,
    raw: bytes | None = None,
    headers: Mapping[str, str] | None = None,
) -> tuple[int, JsonObject, Mapping[str, str]]:
    body = raw if raw is not None else (None if value is None else _canonical_bytes(value))
    request_headers = dict(headers or {})
    if body is not None:
        request_headers.setdefault("Content-Type", "application/json")
        request_headers.setdefault("Content-Length", str(len(body)))
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        connection.request(method, path, body=body, headers=request_headers)
        response = connection.getresponse()
        payload = response.read()
        parsed = strict_json_bytes(payload, label="http_self_test_response")
        _require(isinstance(parsed, Mapping), "HTTP_SELF_TEST_RESPONSE_INVALID")
        return response.status, dict(parsed), {key.lower(): value for key, value in response.getheaders()}
    finally:
        connection.close()


def self_test() -> JsonObject:
    checks: dict[str, bool] = {}
    research_observations: JsonObject = {}
    pinned_demo_source = _validated_demo_source()
    pin_rejection_code = None
    with mock.patch(
        f"{__name__}.PINNED_DEMO_PROVIDER_INPUTS_SHA256", "0" * 64
    ):
        try:
            _validated_demo_source()
        except LiveRevisionError as error:
            pin_rejection_code = error.reason_code
    checks["demo_source_is_publication_pinned"] = (
        pinned_demo_source.get("fingerprint_sha256")
        == PINNED_DEMO_PROVIDER_INPUTS_FINGERPRINT
        and pin_rejection_code == "DEMO_MANIFEST_PROVIDER_INPUTS_PIN_MISMATCH"
    )
    engine = EBRTRevisionEngine()
    demo = build_demo_request(request_id="live-demo-self-test-001")
    generic = _synthetic_generic_request()
    with _network_denied() as network:
        demo_result = engine.execute(demo, ScriptedLiveRevisionProvider())
        generic_result = engine.execute(generic, ScriptedLiveRevisionProvider())

        class ContractInvalidProvider(ScriptedLiveRevisionProvider):
            def generate(
                self, payload: Mapping[str, Any]
            ) -> tuple[Mapping[str, Any], ProviderReceipt]:
                output, receipt = super().generate(payload)
                return {**output, "current_answer": "OUTSIDE_REQUEST_DOMAIN"}, receipt

        provider_contract_error: LiveRevisionError | None = None
        try:
            engine.execute(demo, ContractInvalidProvider())
        except LiveRevisionError as error:
            provider_contract_error = error
    checks["engine_self_test_network_zero"] = network["network_calls"] == 0
    checks["provider_contract_failures_are_upstream_502"] = (
        provider_contract_error is not None
        and provider_contract_error.reason_code == "OUTPUT_ANSWER_OUTSIDE_DOMAIN"
        and provider_contract_error.http_status == 502
    )
    checks["sealed_demo_operational_pass"] = (
        demo_result["verification"]["operational_acceptance_status"] == "PASS"
        and demo_result["mechanism"]["public_control_map"][
            "provider_visible_allocation_transform"
        ]
        == "SOFTMAX_ABSOLUTE_CONTROL_MAGNITUDE"
        and demo_result["mechanism"]["public_control_map"][
            "semantic_operation_source"
        ]
        == "TYPED_EVENT_COMPILER"
        and demo_result["output"]["diff"]["answer"]
        == {"before": "POLISH", "after": "PROVE"}
        and demo_result["mechanism"]["compiled_actuator"][
            "reinspect_evidence_ids"
        ]
        == ["R6", "R4", "R2"]
    )
    checks["generic_non_fixture_topology_pass"] = (
        generic_result["verification"]["operational_acceptance_status"] == "PASS"
        and generic_result["mechanism"]["compiled_actuator"][
            "reinspect_evidence_ids"
        ]
        == ["E-correct", "E-bridge"]
        and all(
            not row["evidence_id"].startswith("R")
            for row in generic_result["mechanism"]["public_control_map"][
                "credit_rows"
            ]
        )
    )
    checks["real_backward_fd_bounds_and_descent"] = all(
        result["mechanism"]["surrogate"]["backward_calls"] == 1
        and result["mechanism"]["surrogate"]["objective_after"]
        < result["mechanism"]["surrogate"]["objective_before"]
        and result["mechanism"]["public_control_map"]["control_l2"]
        <= result["mechanism"]["public_control_map"]["max_control_l2"]
        and result["mechanism"]["public_control_map"]["checks"][
            "finite_difference_agreement"
        ]
        for result in (demo_result, generic_result)
    )
    checks["continuous_allocation_reaches_executable_program"] = all(
        abs(
            sum(
                row["optimized_allocation_fraction"]
                for row in result["mechanism"]["public_control_map"][
                    "credit_rows"
                ]
            )
            - 1.0
        )
        <= ALLOCATION_TOLERANCE
        and sum(
            row["inspection_budget_units"]
            for row in result["mechanism"]["compiled_actuator"][
                "inspection_plan"
            ]["steps"]
        )
        == INSPECTION_BUDGET_UNITS
        and result["mechanism"]["actuator_execution"]["status"]
        == "COMPLETED"
        and result["mechanism"]["actuator_execution"]["final_state"]
        == "READY_FOR_PROVIDER"
        and all(
            result["mechanism"]["compiled_actuator"]["checks"].values()
        )
        and all(
            result["mechanism"]["actuator_execution"]["checks"].values()
        )
        for result in (demo_result, generic_result)
    )
    checks["public_block_restore_dependency_is_scoped"] = all(
        result["public_dependency_audit"]["structural_dependency_status"]
        == "PASS"
        and result["public_dependency_audit"]["provider_calls"] == 0
        and not result["public_dependency_audit"]["hosted_output_regenerated"]
        and result["public_dependency_audit"]["hosted_causality_status"]
        == "NOT_ASSESSED"
        and result["verification"]["counterfactual_output_effect_status"]
        == "NOT_ASSESSED"
        for result in (demo_result, generic_result)
    )
    checks["claim_boundaries_remain_separate"] = all(
        result["verification"]["semantic_correctness_status"] == "NOT_ASSESSED"
        and result["verification"]["effect_attribution_status"] == "NOT_ASSESSED"
        and result["verification"]["provider_uptake_status"]
        == "NOT_ASSESSED"
        for result in (demo_result, generic_result)
    )

    def rejected_with(value: Mapping[str, Any], reason_code: str) -> bool:
        try:
            validate_request_mapping(value)
        except LiveRevisionError as error:
            return error.reason_code == reason_code
        return False

    old_protocol = _clone(generic)
    old_protocol["schema_version"] = "ebrt-live-apply-revision-request-v0.6.2.4"
    checks["old_live_protocol_rejected_before_provider"] = rejected_with(
        old_protocol, "REQUEST_SCHEMA_INVALID"
    )

    forged_provenance = _clone(generic)
    forged_provenance["input_provenance"] = "CONTAMINATED_REGRESSION_FIXTURE"
    checks["provenance_is_server_derived"] = (
        demo_result["context"]["input_provenance"]
        == "CONTAMINATED_REGRESSION_FIXTURE"
        and isinstance(
            demo_result["context"]["source_artifact_fingerprint_sha256"], str
        )
        and generic_result["context"]["input_provenance"]
        == "CALLER_SUPPLIED_UNVERIFIED"
        and generic_result["context"]["source_artifact_fingerprint_sha256"]
        is None
        and rejected_with(forged_provenance, "REQUEST_SCHEMA_INVALID")
    )

    prefix_violation = _clone(generic)
    prefix_violation["all_raw_evidence"] = [
        prefix_violation["all_raw_evidence"][0],
        prefix_violation["all_raw_evidence"][1],
        prefix_violation["all_raw_evidence"][3],
        prefix_violation["all_raw_evidence"][2],
    ]
    duplicate_catalog = _clone(generic)
    duplicate_catalog["candidate_closures"][1]["graph"] = _clone(
        duplicate_catalog["candidate_closures"][0]["graph"]
    )
    permuted_duplicate_catalog = _clone(generic)
    permuted_graph = _clone(
        permuted_duplicate_catalog["candidate_closures"][0]["graph"]
    )
    permuted_graph["support_nodes"].reverse()
    permuted_graph["targets"].reverse()
    permuted_graph["invalidation_edges"].reverse()
    for support in permuted_graph["support_nodes"]:
        support["evidence_ids"].reverse()
    for target in permuted_graph["targets"]:
        target["direct_support_ids"].reverse()
        target["depends_on_target_ids"].reverse()
    permuted_duplicate_catalog["candidate_closures"][1]["graph"] = permuted_graph
    future_evidence = _clone(generic)
    future_evidence["all_raw_evidence"].append(
        {
            "evidence_id": "E-future",
            "text": "A second untyped event outside the declared revision horizon.",
        }
    )
    checks["temporal_prefix_and_duplicate_catalog_rejected"] = (
        rejected_with(
            prefix_violation,
            "BEFORE_HORIZON_MUST_BE_EXACT_PRE_EVENT_PREFIX",
        )
        and rejected_with(duplicate_catalog, "CANDIDATE_GRAPH_DUPLICATE")
        and rejected_with(
            permuted_duplicate_catalog,
            "CANDIDATE_GRAPH_DUPLICATE",
        )
        and rejected_with(
            future_evidence,
            "CORRECTION_MUST_TERMINATE_VISIBLE_HORIZON",
        )
    )

    extra_invalidation = _clone(generic)
    extra_invalidation["all_raw_evidence"].insert(
        -1, {"evidence_id": "E-spare", "text": "Unused public background."}
    )
    extra_invalidation["before_horizon_evidence_ids"].append("E-spare")
    extra_invalidation["candidate_closures"][0]["graph"][
        "invalidation_edges"
    ].append(
        {
            "source_evidence_id": "E-correct",
            "target_evidence_id": "E-spare",
        }
    )
    fact_local_misbinding = _clone(generic)
    event_graph = fact_local_misbinding["candidate_closures"][0]["graph"]
    event_graph["support_nodes"][0]["evidence_ids"] = ["E-bridge"]
    event_graph["support_nodes"][1]["evidence_ids"] = [
        "E-stable",
        "E-correct",
    ]
    checks["extra_invalidation_and_fact_local_misbinding_rejected"] = (
        rejected_with(extra_invalidation, "NO_EVENT_CONSISTENT_CANDIDATE")
        and rejected_with(fact_local_misbinding, "NO_EVENT_CONSISTENT_CANDIDATE")
    )

    inherited = _clone(generic)
    inherited["all_raw_evidence"].insert(
        0, {"evidence_id": "E-ancient", "text": "An already invalidated record."}
    )
    inherited["before_horizon_evidence_ids"].insert(0, "E-ancient")
    prior_edge = {
        "source_evidence_id": "E-old",
        "target_evidence_id": "E-ancient",
    }
    inherited["prior_closure"]["invalidation_edges"].append(_clone(prior_edge))
    for candidate in inherited["candidate_closures"]:
        candidate["graph"]["invalidation_edges"].append(_clone(prior_edge))
    inherited_request = validate_request_mapping(inherited)
    with _network_denied() as inherited_network:
        inherited_result = engine.execute(
            inherited_request, ScriptedLiveRevisionProvider()
        )
    resurrection = _clone(inherited)
    resurrection["candidate_closures"][0]["graph"][
        "invalidation_edges"
    ] = [
        row
        for row in resurrection["candidate_closures"][0]["graph"][
            "invalidation_edges"
        ]
        if row != prior_edge
    ]
    checks["prior_invalidation_transition_preserved"] = (
        inherited_network["network_calls"] == 0
        and inherited_result["verification"]["operational_acceptance_status"]
        == "PASS"
        and inherited_result["output"]["before"]["invalidated_evidence_ids"]
        == ["E-ancient"]
        and set(inherited_result["output"]["after"]["invalidated_evidence_ids"])
        == {"E-ancient", "E-old"}
        and rejected_with(resurrection, "NO_EVENT_CONSISTENT_CANDIDATE")
    )

    generic_request = validate_request_mapping(generic)
    generic_before = _compile_output(
        generic_request,
        generic_request.prior_public_state.model_dump(mode="json"),
        generic_request.prior_closure,
        phase_id="before_event",
        evidence_order=generic_request.before_horizon_evidence_ids,
        allowed_closure_ids={generic_request.prior_public_state.selected_closure_id},
        require_live_schema=False,
    )
    generic_control = _derive_control_map(generic_request, generic_before)
    reversed_domains = _clone(generic)
    reversed_domains["answer_choices"].reverse()
    for slot in reversed_domains["decision_slots"]:
        slot["allowed_values"].reverse()
    reversed_request = validate_request_mapping(reversed_domains)
    reversed_before = _compile_output(
        reversed_request,
        reversed_request.prior_public_state.model_dump(mode="json"),
        reversed_request.prior_closure,
        phase_id="before_event",
        evidence_order=reversed_request.before_horizon_evidence_ids,
        allowed_closure_ids={reversed_request.prior_public_state.selected_closure_id},
        require_live_schema=False,
    )
    reversed_control = _derive_control_map(reversed_request, reversed_before)
    checks["controller_is_enum_order_invariant"] = (
        generic_control["actual_before_state"]["initial_scalar"]
        == reversed_control["actual_before_state"]["initial_scalar"]
        and [
            row["optimized_allocation_fraction"]
            for row in generic_control["credit_rows"]
        ]
        == [
            row["optimized_allocation_fraction"]
            for row in reversed_control["credit_rows"]
        ]
    )

    repeat_control = _derive_control_map(generic_request, generic_before)
    trajectory = generic_control["public_trajectory"]
    evidence_order = [
        row.evidence_id for row in generic_request.all_raw_evidence
    ]
    checks["public_trajectory_forward_is_chronological_and_deterministic"] = (
        trajectory == repeat_control["public_trajectory"]
        and [
            row["evidence_id"]
            for row in trajectory["neutral"]["points"]
        ]
        == evidence_order
        and [
            row["step_index"]
            for row in trajectory["revised"]["points"]
        ]
        == list(range(len(evidence_order)))
    )
    correction_index = trajectory["correction_step_index"]
    checks["late_event_assigns_nonzero_pre_event_temporal_credit"] = (
        correction_index == len(evidence_order) - 1
        and any(
            row["eligible_for_reinspection"]
            and row["temporal_step_index"] < correction_index
            and abs(row["gradient"]) > ALLOCATION_TOLERANCE
            and abs(row["control_value"]) > ALLOCATION_TOLERANCE
            for row in generic_control["credit_rows"]
        )
        and trajectory["checks"]["pre_event_temporal_credit_nonzero"]
    )
    with mock.patch(
        f"{__name__}._controller_loss",
        side_effect=AssertionError("no-event identity called trajectory loss"),
    ) as no_event_backward_guard:
        identity_trajectory = _derive_no_event_identity_trajectory(
            generic_request, generic_before
        )
    checks["no_event_is_exact_identity_and_skips_backward"] = (
        no_event_backward_guard.call_count == 0
        and identity_trajectory["status"] == "IDENTITY_NO_EVENT"
        and identity_trajectory["neutral"]
        == identity_trajectory["revised"]
        and identity_trajectory["backward_calls"] == 0
        and identity_trajectory["provider_calls"] == 0
        and all(identity_trajectory["checks"].values())
    )
    checks["trajectory_adjoint_matches_central_finite_difference"] = (
        generic_control["maximum_finite_difference_error"]
        <= FINITE_DIFFERENCE_TOLERANCE
        and all(
            abs(
                row["gradient"] - row["finite_difference_gradient"]
            )
            <= FINITE_DIFFERENCE_TOLERANCE
            for row in generic_control["credit_rows"]
        )
    )
    checks["trajectory_update_is_bounded_and_descends"] = (
        trajectory["revised"]["objective"]
        < trajectory["neutral"]["objective"]
        and generic_control["control_l2"] <= MAX_CONTROL_L2
        and trajectory["revised"]["terminal_state"][0]
        > trajectory["neutral"]["terminal_state"][0]
        and trajectory["revised"]["terminal_state"][1]
        > trajectory["neutral"]["terminal_state"][1]
    )
    checks["typed_event_zero_control_is_true_noop"] = (
        trajectory["checks"]["zero_control_is_exact_unmodified_forward"]
        and trajectory["control_gate"]["zero_control_semantics"]
        == "EXACT_NO_EVENT_PROPOSAL_ADMISSION"
        and trajectory["neutral"]["points"]
        == _trajectory_points(
            evidence_ids=[
                row.evidence_id for row in generic_request.all_raw_evidence
            ],
            states=_unmodified_forward_trajectory(
                torch.tensor(
                    generic_control["actual_before_state"]["initial_vector"],
                    dtype=FLOAT_DTYPE,
                ),
                steps=len(generic_request.all_raw_evidence),
            ),
            controls=torch.zeros(len(generic_request.all_raw_evidence)),
            gradients=torch.tensor(
                [row["gradient"] for row in generic_control["credit_rows"]],
                dtype=FLOAT_DTYPE,
            ),
            eligibility=torch.tensor(
                [
                    bool(row["eligible_for_reinspection"])
                    for row in generic_control["credit_rows"]
                ],
                dtype=torch.bool,
            ),
            correction_index=[
                row.evidence_id for row in generic_request.all_raw_evidence
            ].index(generic_request.event.correction_evidence_id),
            support_envelope=torch.tensor(
                [
                    point["full_admission_support_reference"]
                    for point in trajectory["neutral"]["points"]
                ],
                dtype=FLOAT_DTYPE,
            ),
        )
    )
    neutral_preterminal_points = trajectory["neutral"]["points"][:-1]
    revised_preterminal_points = trajectory["revised"]["points"][:-1]
    neutral_preterminal_path_receipt = sum(
        (
            row["state"][0]
            - row["full_admission_support_reference"]
        )
        ** 2
        for row in neutral_preterminal_points
    ) / len(neutral_preterminal_points)
    revised_preterminal_path_receipt = sum(
        (
            row["state"][0]
            - row["full_admission_support_reference"]
        )
        ** 2
        for row in revised_preterminal_points
    ) / len(revised_preterminal_points)
    checks["trajectory_nonterminal_path_loss_is_active"] = (
        bool(neutral_preterminal_points)
        and len(neutral_preterminal_points)
        == len(revised_preterminal_points)
        and math.isclose(
            trajectory["neutral"]["loss_components"]["path"],
            neutral_preterminal_path_receipt,
            rel_tol=0.0,
            abs_tol=1.0e-15,
        )
        and math.isclose(
            trajectory["revised"]["loss_components"]["path"],
            revised_preterminal_path_receipt,
            rel_tol=0.0,
            abs_tol=1.0e-15,
        )
        and trajectory["neutral"]["loss_components"]["path"] > 0.0
        and trajectory["revised"]["loss_components"]["path"]
        < trajectory["neutral"]["loss_components"]["path"]
        and trajectory["checks"]["trajectory_path_loss_decreased"]
    )
    temporal_diagnostic = trajectory["research_diagnostics"][
        "temporal_sham"
    ]
    checks["matched_time_diagnostic_geometry_is_rederived"] = (
        all(
            temporal_diagnostic["checks"][key]
            for key in (
                "signed_value_multiset_matched",
                "control_l2_matched",
                "control_regularization_matched",
                "eligible_temporal_smoothness_matched",
            )
        )
        and trajectory["matched_temporal_sham"]["control_l2"]
        == generic_control["control_l2"]
        and trajectory["matched_temporal_sham"]["loss_components"][
            "control"
        ]
        == trajectory["revised"]["loss_components"]["control"]
        and trajectory["matched_temporal_sham"]["loss_components"][
            "smoothness"
        ]
        == trajectory["revised"]["loss_components"]["smoothness"]
        and trajectory["matched_temporal_sham"]["provider_calls"] == 0
        and temporal_diagnostic["product_gate_participation"] is False
    )
    research_observations["generic_fixture_temporal_sham"] = {
        "status": temporal_diagnostic["status"],
        "exact_temporal_placement_beats_matched_sham": temporal_diagnostic[
            "exact_temporal_placement_beats_matched_sham"
        ],
        "exact_objective": temporal_diagnostic["exact_objective"],
        "sham_objective": temporal_diagnostic["sham_objective"],
        "product_gate_participation": False,
    }
    synthetic_nonpositive_diagnostic = _temporal_sham_diagnostic(
        accepted=torch.tensor(
            [row["control_value"] for row in generic_control["credit_rows"]],
            dtype=FLOAT_DTYPE,
        ),
        accepted_loss=torch.tensor(1.0, dtype=FLOAT_DTYPE),
        accepted_components={
            key: torch.tensor(value, dtype=FLOAT_DTYPE)
            for key, value in trajectory["revised"]["loss_components"].items()
        },
        sham=_matched_temporal_sham(
            torch.tensor(
                [row["control_value"] for row in generic_control["credit_rows"]],
                dtype=FLOAT_DTYPE,
            ),
            torch.tensor(
                [
                    bool(row["eligible_for_reinspection"])
                    for row in generic_control["credit_rows"]
                ],
                dtype=torch.bool,
            ),
        ),
        sham_loss=torch.tensor(0.9, dtype=FLOAT_DTYPE),
        sham_components={
            key: torch.tensor(value, dtype=FLOAT_DTYPE)
            for key, value in trajectory["matched_temporal_sham"][
                "loss_components"
            ].items()
        },
        eligibility=torch.tensor(
            [
                bool(row["eligible_for_reinspection"])
                for row in generic_control["credit_rows"]
            ],
            dtype=torch.bool,
        ),
    )
    degenerate_controls = torch.tensor([0.0, 0.1], dtype=FLOAT_DTYPE)
    degenerate_eligibility = torch.tensor([False, True], dtype=torch.bool)
    degenerate_components = {
        "terminal": torch.tensor(0.5, dtype=FLOAT_DTYPE),
        "path": torch.tensor(0.25, dtype=FLOAT_DTYPE),
        "control": torch.tensor(0.01, dtype=FLOAT_DTYPE),
        "smoothness": torch.tensor(0.0, dtype=FLOAT_DTYPE),
    }
    degenerate_diagnostic = _temporal_sham_diagnostic(
        accepted=degenerate_controls,
        accepted_loss=torch.tensor(1.0, dtype=FLOAT_DTYPE),
        accepted_components=degenerate_components,
        sham=_matched_temporal_sham(
            degenerate_controls,
            degenerate_eligibility,
        ),
        sham_loss=torch.tensor(1.0, dtype=FLOAT_DTYPE),
        sham_components=degenerate_components,
        eligibility=degenerate_eligibility,
    )
    checks["research_sham_outcome_is_not_a_product_gate"] = (
        synthetic_nonpositive_diagnostic["status"] == "NON_POSITIVE"
        and synthetic_nonpositive_diagnostic["product_gate_participation"]
        is False
        and degenerate_diagnostic["status"] == "UNAVAILABLE_DEGENERATE"
        and degenerate_diagnostic["product_gate_participation"] is False
        and "exact_temporal_placement_beats_matched_sham"
        not in generic_control["checks"]
        and "exact_temporal_placement_beats_matched_sham"
        not in trajectory["checks"]
        and all(generic_control["checks"].values())
        and all(trajectory["checks"].values())
    )
    stable_index = list(TRAJECTORY_AXES).index(
        "stable_support_retention"
    )
    checks["stable_axis_is_exactly_preserved"] = (
        trajectory["checks"]["stable_axis_exact_identity"]
        and all(
            neutral["state"][stable_index]
            == revised["state"][stable_index]
            == generic_control["actual_before_state"]["initial_vector"][
                stable_index
            ]
            for neutral, revised in zip(
                trajectory["neutral"]["points"],
                trajectory["revised"]["points"],
                strict=True,
            )
        )
    )

    generic_actuator = _compile_actuator(
        generic_request, generic_before, generic_control
    )
    checks["trajectory_patch_compiles_exactly_to_continuous_actuator"] = (
        generic_actuator[
            "source_public_trajectory_fingerprint_sha256"
        ]
        == trajectory["fingerprint_sha256"]
        == generic_actuator["inspection_plan"][
            "source_public_trajectory_fingerprint_sha256"
        ]
        == generic_actuator["program"][
            "source_public_trajectory_fingerprint_sha256"
        ]
        and generic_actuator["reinspect_source"]
        == "PUBLIC_TRAJECTORY_ADJOINT_PROJECTION"
        and sum(
            row["inspection_budget_units"]
            for row in generic_actuator["inspection_plan"]["steps"]
        )
        == INSPECTION_BUDGET_UNITS
    )
    tampered_control = _clone(generic_control)
    tampered_trajectory = _without_fingerprint(
        tampered_control["public_trajectory"]
    )
    tampered_revised = _without_fingerprint(
        tampered_trajectory["revised"]
    )
    tampered_point = _without_fingerprint(tampered_revised["points"][0])
    tampered_point["state"][stable_index] += 0.001
    tampered_revised["points"][0] = _seal(tampered_point)
    tampered_trajectory["revised"] = _seal(tampered_revised)
    tampered_control["public_trajectory"] = _seal(tampered_trajectory)
    tampered_control = _seal(_without_fingerprint(tampered_control))
    trajectory_tamper_rejection = ""
    try:
        _compile_actuator(
            generic_request, generic_before, tampered_control
        )
    except LiveRevisionError as error:
        trajectory_tamper_rejection = error.reason_code
    checks["resealed_trajectory_tamper_rejected_before_provider"] = (
        trajectory_tamper_rejection
        == "PUBLIC_TRAJECTORY_FORWARD_REPLAY_MISMATCH"
    )
    sham_tampered_control = _clone(generic_control)
    sham_tampered_trajectory = _without_fingerprint(
        sham_tampered_control["public_trajectory"]
    )
    sham_tampered_trajectory["matched_temporal_sham"][
        "objective"
    ] = -999.0
    sham_tampered_control["public_trajectory"] = _seal(
        sham_tampered_trajectory
    )
    sham_tampered_control = _seal(
        _without_fingerprint(sham_tampered_control)
    )
    sham_tamper_rejection = ""
    try:
        _compile_actuator(
            generic_request, generic_before, sham_tampered_control
        )
    except LiveRevisionError as error:
        sham_tamper_rejection = error.reason_code
    gradient_tampered_control = _clone(generic_control)
    for row in gradient_tampered_control["credit_rows"]:
        row["gradient"] += 123.0
        row["finite_difference_gradient"] += 123.0
    gradient_tampered_trajectory = _without_fingerprint(
        gradient_tampered_control["public_trajectory"]
    )
    for trace_name in ("neutral", "revised"):
        trace_value = _without_fingerprint(
            gradient_tampered_trajectory[trace_name]
        )
        trace_value["points"] = [
            _seal(
                {
                    **_without_fingerprint(point),
                    "temporal_gradient": point["temporal_gradient"]
                    + 123.0,
                }
            )
            for point in trace_value["points"]
        ]
        gradient_tampered_trajectory[trace_name] = _seal(trace_value)
    gradient_tampered_control["public_trajectory"] = _seal(
        gradient_tampered_trajectory
    )
    gradient_tampered_control = _seal(
        _without_fingerprint(gradient_tampered_control)
    )
    gradient_tamper_rejection = ""
    try:
        _compile_actuator(
            generic_request, generic_before, gradient_tampered_control
        )
    except LiveRevisionError as error:
        gradient_tamper_rejection = error.reason_code
    checks["scientific_receipt_reseal_tamper_rejected_before_provider"] = (
        sham_tamper_rejection
        == "PUBLIC_TRAJECTORY_RECEIPT_DERIVATION_INVALID"
        and gradient_tamper_rejection
        == "PUBLIC_TRAJECTORY_GRADIENT_RECEIPT_INVALID"
    )
    contribution_tampered_control = _clone(generic_control)
    contribution_rows = contribution_tampered_control["credit_rows"]
    contribution_delta = 0.125
    for field in (
        "surrogate_contribution_before",
        "surrogate_contribution_after",
    ):
        contribution_rows[0][field] += contribution_delta
        contribution_rows[1][field] -= contribution_delta
    contribution_tampered_control = _seal(
        _without_fingerprint(contribution_tampered_control)
    )
    contribution_tamper_rejection = ""
    try:
        _compile_actuator(
            generic_request,
            generic_before,
            contribution_tampered_control,
        )
    except LiveRevisionError as error:
        contribution_tamper_rejection = error.reason_code
    checks[
        "surrogate_contribution_reseal_tamper_rejected_before_provider"
    ] = (
        contribution_tamper_rejection
        == "PUBLIC_TRAJECTORY_CONTROL_DERIVATION_INVALID"
    )
    generic_prior_payload = _build_prior_public_state(
        generic_request, generic_before
    )
    generic_execution = _execute_actuator_program(
        generic_request,
        generic_actuator,
        source_control_map_fingerprint_sha256=generic_control[
            "fingerprint_sha256"
        ],
        source_prior_state_fingerprint_sha256=_fingerprint(
            generic_prior_payload
        ),
    )
    tampered_actuator = _clone(generic_actuator)
    tampered_program = _without_fingerprint(tampered_actuator["program"])
    tampered_reinspect_step = next(
        row
        for row in tampered_program["steps"]
        if row["operation"] == "REINSPECT"
    )
    tampered_reinspect_step["evidence_id"] = "UNKNOWN-EVIDENCE"
    tampered_actuator["program"] = _seal(tampered_program)
    tampered_actuator = _seal(_without_fingerprint(tampered_actuator))
    tampered_program_rejection = ""
    try:
        _execute_actuator_program(
            generic_request,
            tampered_actuator,
            source_control_map_fingerprint_sha256=generic_control[
                "fingerprint_sha256"
            ],
            source_prior_state_fingerprint_sha256=_fingerprint(
                generic_prior_payload
            ),
        )
    except LiveRevisionError as error:
        tampered_program_rejection = error.reason_code
    checks["tampered_actuator_program_rejected_before_provider"] = (
        tampered_program_rejection
        == "ACTUATOR_PROGRAM_MATERIALIZATION_INVALID"
    )
    provider_payload = _build_provider_payload(
        generic_request,
        generic_before,
        generic_prior_payload,
        generic_control,
        generic_actuator,
        generic_execution,
    )
    resealed_actuator = _clone(generic_actuator)
    resealed_plan_value = _without_fingerprint(
        resealed_actuator["inspection_plan"]
    )
    for row, fraction, units in zip(
        resealed_plan_value["steps"],
        (0.6, 0.4),
        (60, 40),
        strict=True,
    ):
        row["controller_allocation_fraction"] = fraction
        row["inspection_share"] = fraction
        row["allocation_delta"] = fraction - 0.5
        row["relative_emphasis"] = fraction * 2.0
        row["review_depth"] = _review_depth(fraction * 2.0)
        row["inspection_budget_units"] = units
    resealed_plan = _seal(resealed_plan_value)
    resealed_program = _seal(
        {
            "schema_version": "ebrt-live-public-revision-program-v0.6.2.5",
            "state": "COMPILED",
            "source_control_map_fingerprint_sha256": generic_control[
                "fingerprint_sha256"
            ],
            "source_public_trajectory_fingerprint_sha256": generic_control[
                "public_trajectory"
            ]["fingerprint_sha256"],
            "steps": _expected_program_steps(
                correction_evidence_id=generic_request.event.correction_evidence_id,
                suppress_evidence_ids=resealed_actuator[
                    "suppress_evidence_ids"
                ],
                inspection_steps=resealed_plan["steps"],
                preserve_evidence_ids=resealed_actuator[
                    "preserve_evidence_ids"
                ],
            ),
        }
    )
    resealed_actuator["inspection_plan"] = resealed_plan
    resealed_actuator["program"] = resealed_program
    resealed_actuator = _seal(_without_fingerprint(resealed_actuator))
    resealed_execution = _execute_actuator_program(
        generic_request,
        resealed_actuator,
        source_control_map_fingerprint_sha256=generic_control[
            "fingerprint_sha256"
        ],
        source_prior_state_fingerprint_sha256=_fingerprint(
            generic_prior_payload
        ),
    )
    resealed_derivation_rejection = ""
    try:
        _build_provider_payload(
            generic_request,
            generic_before,
            generic_prior_payload,
            generic_control,
            resealed_actuator,
            resealed_execution,
        )
    except LiveRevisionError as error:
        resealed_derivation_rejection = error.reason_code
    checks["resealed_actuator_control_derivation_rejected_before_provider"] = (
        resealed_derivation_rejection == "PROVIDER_ACTUATOR_BINDING_INVALID"
    )
    with mock.patch(f"{__name__}.STEP_SIZE", STEP_SIZE * 0.5):
        magnitude_control = _derive_control_map(
            generic_request, generic_before
        )
        magnitude_actuator = _compile_actuator(
            generic_request, generic_before, magnitude_control
        )
        magnitude_execution = _execute_actuator_program(
            generic_request,
            magnitude_actuator,
            source_control_map_fingerprint_sha256=magnitude_control[
                "fingerprint_sha256"
            ],
            source_prior_state_fingerprint_sha256=_fingerprint(
                generic_prior_payload
            ),
        )
        magnitude_payload = _build_provider_payload(
            generic_request,
            generic_before,
            generic_prior_payload,
            magnitude_control,
            magnitude_actuator,
            magnitude_execution,
        )
    checks["continuous_magnitude_changes_provider_visible_allocation"] = (
        magnitude_actuator["reinspect_evidence_ids"]
        == generic_actuator["reinspect_evidence_ids"]
        and magnitude_actuator["inspection_plan"]["steps"]
        != generic_actuator["inspection_plan"]["steps"]
        and magnitude_actuator["fingerprint_sha256"]
        != generic_actuator["fingerprint_sha256"]
        and _fingerprint(magnitude_payload) != _fingerprint(provider_payload)
    )
    permuted_provider_value = _clone(generic)
    for candidate in permuted_provider_value["candidate_closures"]:
        graph = candidate["graph"]
        graph["support_nodes"].reverse()
        graph["targets"].reverse()
        graph["invalidation_edges"].reverse()
        for support in graph["support_nodes"]:
            support["evidence_ids"].reverse()
        for target in graph["targets"]:
            target["direct_support_ids"].reverse()
            target["depends_on_target_ids"].reverse()
    permuted_provider_value["candidate_closures"].reverse()
    permuted_provider_request = validate_request_mapping(permuted_provider_value)
    permuted_provider_before = _compile_output(
        permuted_provider_request,
        permuted_provider_request.prior_public_state.model_dump(mode="json"),
        permuted_provider_request.prior_closure,
        phase_id="before_event",
        evidence_order=permuted_provider_request.before_horizon_evidence_ids,
        allowed_closure_ids={
            permuted_provider_request.prior_public_state.selected_closure_id
        },
        require_live_schema=False,
    )
    permuted_provider_control = _derive_control_map(
        permuted_provider_request,
        permuted_provider_before,
    )
    canonical_probe = ClosureGraph.model_validate(
        {
            "support_nodes": [
                {"support_id": "S-b", "evidence_ids": ["E-2", "E-1"]},
                {"support_id": "S-a", "evidence_ids": ["E-4", "E-3"]},
            ],
            "targets": [
                {
                    "target_id": "fact:c",
                    "target_type": "fact",
                    "slot": "c",
                    "direct_support_ids": ["S-b", "S-a"],
                    "depends_on_target_ids": ["fact:b", "fact:a"],
                },
                {
                    "target_id": "fact:b",
                    "target_type": "fact",
                    "slot": "b",
                    "direct_support_ids": ["S-b", "S-a"],
                    "depends_on_target_ids": ["fact:a"],
                },
                {
                    "target_id": "fact:a",
                    "target_type": "fact",
                    "slot": "a",
                    "direct_support_ids": ["S-b", "S-a"],
                    "depends_on_target_ids": [],
                },
            ],
            "invalidation_edges": [
                {"source_evidence_id": "E-4", "target_evidence_id": "E-1"},
                {"source_evidence_id": "E-3", "target_evidence_id": "E-2"},
            ],
        }
    )
    canonical_probe_permutation = canonical_probe.model_dump(mode="json")
    canonical_probe_permutation["support_nodes"].reverse()
    canonical_probe_permutation["targets"].reverse()
    canonical_probe_permutation["invalidation_edges"].reverse()
    for support in canonical_probe_permutation["support_nodes"]:
        support["evidence_ids"].reverse()
    for target in canonical_probe_permutation["targets"]:
        target["direct_support_ids"].reverse()
        target["depends_on_target_ids"].reverse()
    permuted_canonical_probe = ClosureGraph.model_validate(
        canonical_probe_permutation
    )
    opaque_ids = [row["closure_id"] for row in provider_payload["candidate_closures"]]
    expected_graph_by_id = {
        _opaque_closure_id("K", candidate.graph): _canonical_graph_value(
            candidate.graph
        )
        for candidate in generic_request.candidate_closures
    }
    observed_graph_by_id = {
        row["closure_id"]: row["graph"]
        for row in provider_payload["candidate_closures"]
    }
    checks["provider_closure_ids_are_server_opaque"] = (
        all(
            value.startswith("K_")
            and len(value) == 18
            and all(char in "0123456789abcdef" for char in value[2:])
            for value in opaque_ids
        )
        and provider_payload["prior_public_state"]["selected_closure_id"].startswith(
            "P_"
        )
        and not (
            set(opaque_ids)
            & {row["closure_id"] for row in generic["candidate_closures"]}
        )
        and provider_payload["candidate_closures"]
        == _provider_candidate_rows(permuted_provider_request)
        and generic_control == permuted_provider_control
        and _canonical_graph_value(canonical_probe)
        == _canonical_graph_value(permuted_canonical_probe)
        and _opaque_closure_id("K", canonical_probe)
        == _opaque_closure_id("K", permuted_canonical_probe)
        and observed_graph_by_id == expected_graph_by_id
    )

    forbidden_rejected = False
    forbidden = _clone(demo)
    forbidden["event"]["expected_answer"] = "PROVE"
    try:
        validate_request_mapping(forbidden)
    except LiveRevisionError as error:
        forbidden_rejected = error.reason_code == "FORBIDDEN_REQUEST_KEY"
    checks["semantic_gold_and_expected_answer_rejected"] = forbidden_rejected

    duplicate_rejected = False
    try:
        strict_json_bytes(b'{"request_id":"first","request_id":"second"}')
    except LiveRevisionError as error:
        duplicate_rejected = error.reason_code == "DUPLICATE_JSON_KEY"
    nonfinite_rejected = False
    try:
        strict_json_bytes(b'{"value":NaN}')
    except LiveRevisionError as error:
        nonfinite_rejected = error.reason_code == "NONFINITE_JSON"
    checks["duplicate_and_nonfinite_json_rejected"] = (
        duplicate_rejected and nonfinite_rejected
    )

    failure_calls = {"count": 0}

    class FailingProvider:
        model_label = "SCRIPTED_FAILURE_TEST_ONLY"

        def generate(
            self, _payload: Mapping[str, Any]
        ) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
            failure_calls["count"] += 1
            raise LiveRevisionError(
                "SCRIPTED_PROVIDER_FAILURE", http_status=502
            )

    failure_service = RevisionService(
        FailingProvider,
        provider_mode="scripted",
    )
    failure_observations: list[tuple[str, bool]] = []
    for _ in range(2):
        try:
            failure_service.apply(demo)
        except LiveRevisionError as error:
            failure_observations.append(
                (error.reason_code, error.idempotent_replay)
            )
    checks["failed_provider_attempt_is_terminally_idempotent"] = (
        failure_calls["count"] == 1
        and failure_service.provider_attempts_started == 1
        and failure_observations
        == [
            ("SCRIPTED_PROVIDER_FAILURE", False),
            ("SCRIPTED_PROVIDER_FAILURE", True),
        ]
    )

    lru_service = RevisionService(
        ScriptedLiveRevisionProvider,
        provider_mode="scripted",
        terminal_cache_capacity=2,
        compact_tombstone_capacity=8,
    )
    lru_requests: list[JsonObject] = []
    with _network_denied() as lru_network:
        for index in range(3):
            request_value = _clone(generic)
            request_value["request_id"] = f"lru-request-{index:02d}"
            lru_requests.append(request_value)
            lru_service.apply(request_value)
        evicted_error: LiveRevisionError | None = None
        try:
            lru_service.apply(lru_requests[0])
        except LiveRevisionError as error:
            evicted_error = error
        fourth_request = _clone(generic)
        fourth_request["request_id"] = "lru-request-03"
        lru_service.apply(fourth_request)
        repeated_fourth, repeated_fourth_is_replay = lru_service.apply(
            fourth_request
        )
    checks["terminal_results_lru_without_identity_reexecution"] = (
        lru_network["network_calls"] == 0
        and evicted_error is not None
        and evicted_error.reason_code == "IDEMPOTENCY_RESULT_EVICTED"
        and evicted_error.http_status == 410
        and evicted_error.idempotent_replay
        and lru_service.provider_attempts_started == 4
        and len(lru_service._terminal) == 2
        and len(lru_service._spent) == 4
        and repeated_fourth_is_replay
        and repeated_fourth["request_id"] == fourth_request["request_id"]
    )

    provider_started = threading.Event()
    provider_release = threading.Event()

    class BlockingProvider:
        model_label = "SCRIPTED_BLOCKING_TEST_ONLY"

        def generate(
            self, payload: Mapping[str, Any]
        ) -> tuple[Mapping[str, Any], ProviderReceipt]:
            provider_started.set()
            _require(
                provider_release.wait(timeout=5),
                "SELF_TEST_BLOCKING_PROVIDER_TIMEOUT",
                http_status=500,
            )
            return ScriptedLiveRevisionProvider().generate(payload)

    blocking_service = RevisionService(
        BlockingProvider,
        provider_mode="scripted",
    )
    threaded_result: dict[str, Any] = {}

    def run_blocking_request() -> None:
        try:
            threaded_result["value"] = blocking_service.apply(demo)
        except Exception as error:  # pragma: no cover - asserted below
            threaded_result["error"] = error

    request_thread = threading.Thread(target=run_blocking_request)
    request_thread.start()
    _require(provider_started.wait(timeout=5), "SELF_TEST_PROVIDER_DID_NOT_START")
    inflight_reason = ""
    try:
        blocking_service.apply(demo)
    except LiveRevisionError as error:
        inflight_reason = error.reason_code
    provider_release.set()
    request_thread.join(timeout=5)
    cached_response, cached_replay = blocking_service.apply(demo)
    checks["inflight_and_terminal_success_prevent_duplicate_calls"] = (
        not request_thread.is_alive()
        and "error" not in threaded_result
        and inflight_reason == "REQUEST_ALREADY_IN_FLIGHT"
        and threaded_result["value"][0] == cached_response
        and cached_replay
        and blocking_service.provider_attempts_started == 1
    )

    lock = strict_json_bytes(
        (ROOT / "policy_lock_apply_revision_acceptance_v0_6_2_1.json").read_bytes(),
        label="historical_policy_lock",
    )
    locked_runtime_sha = lock["sources"]["product_runtime"]["sha256"]
    observed_runtime_sha = hashlib.sha256((ROOT / "ebrt.py").read_bytes()).hexdigest()
    checks["sealed_v0621_runtime_remains_byte_identical"] = (
        locked_runtime_sha == observed_runtime_sha
    )

    relay_token = "self-test-relay-token-7d2d469f"
    relay_headers = {
        RELAY_TOKEN_HEADER: relay_token,
        RELAY_CLIENT_KEY_HEADER: "a" * 64,
    }
    with mock.patch.dict(
        os.environ,
        {
            RELAY_TOKEN_ENV: relay_token,
            RELAY_TOTAL_BUDGET_ENV: "2",
            RELAY_CLIENT_BUDGET_ENV: "1",
        },
        clear=False,
    ):
        server, service = create_http_server(
            host="127.0.0.1", port=0, provider_mode="scripted"
        )
    port = int(server.server_address[1])
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05})
    thread.daemon = True
    thread.start()
    try:
        unauth_status, unauth_body, _ = _http_json(
            port,
            "GET",
            "/api/health",
        )
        invalid_client_status, invalid_client_body, _ = _http_json(
            port,
            "GET",
            "/api/health",
            headers={
                RELAY_TOKEN_HEADER: relay_token,
                RELAY_CLIENT_KEY_HEADER: "NOT-A-TRUSTED-CLIENT-KEY",
            },
        )
        health_status, health, health_headers = _http_json(
            port,
            "GET",
            "/api/health",
            headers=relay_headers,
        )
        demo_status, envelope, demo_headers = _http_json(
            port,
            "GET",
            "/api/demo-request",
            headers=relay_headers,
        )
        http_request = envelope["request"]
        unauth_post_status, unauth_post_body, _ = _http_json(
            port,
            "POST",
            "/api/apply-revision",
            value=http_request,
            headers={"Idempotency-Key": http_request["request_id"]},
        )
        post_headers = {
            **relay_headers,
            "Idempotency-Key": http_request["request_id"],
        }
        post_status, first, first_headers = _http_json(
            port,
            "POST",
            "/api/apply-revision",
            value=http_request,
            headers=post_headers,
        )
        repeat_status, repeat, repeat_headers = _http_json(
            port,
            "POST",
            "/api/apply-revision",
            value=http_request,
            headers=post_headers,
        )
        attempts_after_repeat = service.provider_attempts_started
        conflict = _clone(http_request)
        conflict["question"] = conflict["question"] + " "
        conflict_status, conflict_body, _ = _http_json(
            port,
            "POST",
            "/api/apply-revision",
            value=conflict,
            headers=post_headers,
        )
        same_client_new = _clone(http_request)
        same_client_new["request_id"] = "http-same-client-quota-0001"
        same_client_status, same_client_body, _ = _http_json(
            port,
            "POST",
            "/api/apply-revision",
            value=same_client_new,
            headers={
                **relay_headers,
                "Idempotency-Key": same_client_new["request_id"],
            },
        )
        second_client_request = _clone(http_request)
        second_client_request["request_id"] = "http-second-client-0001"
        second_client_headers = {
            RELAY_TOKEN_HEADER: relay_token,
            RELAY_CLIENT_KEY_HEADER: "b" * 64,
            "Idempotency-Key": second_client_request["request_id"],
        }
        second_client_status, second_client_body, _ = _http_json(
            port,
            "POST",
            "/api/apply-revision",
            value=second_client_request,
            headers=second_client_headers,
        )
        total_quota_request = _clone(http_request)
        total_quota_request["request_id"] = "http-total-quota-0001"
        total_quota_status, total_quota_body, _ = _http_json(
            port,
            "POST",
            "/api/apply-revision",
            value=total_quota_request,
            headers={
                RELAY_TOKEN_HEADER: relay_token,
                RELAY_CLIENT_KEY_HEADER: "c" * 64,
                "Idempotency-Key": total_quota_request["request_id"],
            },
        )
        origin_status, origin_body, _ = _http_json(
            port,
            "GET",
            "/api/health",
            headers={**relay_headers, "Origin": "https://attacker.invalid"},
        )
        duplicate_body = (
            b'{"request_id":"duplicate-0001","request_id":"duplicate-0002"}'
        )
        duplicate_status, duplicate_body_result, _ = _http_json(
            port,
            "POST",
            "/api/apply-revision",
            raw=duplicate_body,
            headers={
                **relay_headers,
                "Idempotency-Key": "duplicate-0001",
            },
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    checks["http_relay_auth_and_client_key_enforced"] = (
        unauth_status == unauth_post_status == 401
        and unauth_body["error"]["code"] == "RELAY_AUTH_FAILED"
        and unauth_post_body["error"]["code"] == "RELAY_AUTH_FAILED"
        and invalid_client_status == 400
        and invalid_client_body["error"]["code"]
        == "RELAY_CLIENT_KEY_INVALID"
    )
    checks["http_health_and_demo_are_authenticated_zero_call"] = (
        health_status == demo_status == 200
        and health_headers.get("server", "").strip()
        == "EBRTLive/0.6.2.5-RuntimePreview4"
        and health["provider_mode"] == "scripted"
        and health["relay"]["token_required"]
        and health["relay"]["provider_attempts_started"] == 0
        and health["relay"]["max_provider_attempts_total"] == 2
        and health["relay"]["max_provider_attempts_per_client"] == 1
        and envelope["schema_version"] == DEMO_REQUEST_SCHEMA
        and envelope["request_fingerprint_sha256"]
        == _fingerprint(envelope["request"])
        and envelope["fingerprint_sha256"]
        == _fingerprint(_without_fingerprint(envelope))
        and demo_headers.get("x-ebrt-body-sha256")
        == hashlib.sha256(_canonical_bytes(envelope, trailing_newline=True)).hexdigest()
    )
    checks["http_live_post_completes_once"] = (
        post_status == 200
        and first["verification"]["operational_acceptance_status"] == "PASS"
        and first_headers.get("x-ebrt-idempotent-replay") is None
        and first_headers.get("x-ebrt-body-sha256")
        == hashlib.sha256(_canonical_bytes(first, trailing_newline=True)).hexdigest()
    )
    checks["http_idempotent_repeat_is_cached"] = (
        repeat_status == 200
        and repeat == first
        and repeat_headers.get("x-ebrt-idempotent-replay") == "true"
        and repeat_headers.get("x-ebrt-body-sha256")
        == first_headers.get("x-ebrt-body-sha256")
        and attempts_after_repeat == 1
    )
    checks["http_client_and_total_provider_budgets_are_hard"] = (
        same_client_status == 429
        and same_client_body["error"]["code"]
        == "RELAY_CLIENT_PROVIDER_BUDGET_EXHAUSTED"
        and second_client_status == 200
        and second_client_body["verification"]["operational_acceptance_status"]
        == "PASS"
        and total_quota_status == 429
        and total_quota_body["error"]["code"]
        == "RELAY_TOTAL_PROVIDER_BUDGET_EXHAUSTED"
        and service.provider_attempts_started == 2
        and service.provider_attempts_by_client.get("a" * 64) == 1
        and service.provider_attempts_by_client.get("b" * 64) == 1
        and service.provider_attempts_by_client.get("c" * 64, 0) == 0
    )
    checks["http_idempotency_conflict_rejected"] = (
        conflict_status == 409
        and conflict_body["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"
    )
    checks["http_origin_and_duplicate_json_rejected"] = (
        origin_status == 403
        and origin_body["error"]["code"] == "ORIGIN_NOT_ALLOWED"
        and duplicate_status == 400
        and duplicate_body_result["error"]["code"] == "DUPLICATE_JSON_KEY"
    )

    _require(
        all(checks.values()),
        "SELF_TEST_FAILED",
        ",".join(name for name, passed in checks.items() if not passed),
        http_status=500,
    )
    return _seal(
        {
            "schema_version": "ebrt-live-self-test-v0.6.2.5",
            "status": "PASS",
            "checks": checks,
            "research_observations": research_observations,
            "demo_result_fingerprint_sha256": demo_result["fingerprint_sha256"],
            "generic_result_fingerprint_sha256": generic_result[
                "fingerprint_sha256"
            ],
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("self-test", help="run network-zero engine and HTTP tests")
    commands.add_parser("demo-request", help="print a fresh contaminated demo request")
    apply_demo = commands.add_parser(
        "apply-demo", help="apply the contaminated demo through one provider attempt"
    )
    apply_demo.add_argument(
        "--provider", choices=("scripted", "openai"), default="scripted"
    )
    server = commands.add_parser("serve", help="serve the loopback live API")
    server.add_argument(
        "--provider", choices=("scripted", "openai"), default="scripted"
    )
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8765)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "self-test":
            value = self_test()
        elif args.command == "demo-request":
            value = demo_request_envelope()
        elif args.command == "apply-demo":
            factory = _provider_factory(args.provider)
            value = EBRTRevisionEngine().execute(build_demo_request(), factory())
        elif args.command == "serve":
            serve(host=args.host, port=args.port, provider_mode=args.provider)
            return 0
        else:  # pragma: no cover
            raise LiveRevisionError("UNKNOWN_COMMAND", http_status=400)
        print(_pretty(value), end="")
        return 0
    except LiveRevisionError as error:
        print(_pretty(_error_value(error)), end="")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
