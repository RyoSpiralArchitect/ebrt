#!/usr/bin/env python3
"""EBRT v0.6.2.2 live Apply Revision product monolith.

This is the current, generic, one-call product path.  The sealed ``ebrt.py``
v0.6.2.1 acceptance runtime is historical evidence and is intentionally not
imported or modified here.

The live path accepts an already-emitted public Before state and a typed late
event, compiles a bounded public actuator with one local float64 backward pass,
then makes at most one fresh After regeneration call. Reserved gold fields,
graders, provider hidden state, and provider gradients are outside this runtime;
caller semantic content is not certified as gold-free.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
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

REQUEST_SCHEMA = "ebrt-live-apply-revision-request-v0.6.2.2"
PROVIDER_INPUT_SCHEMA = "ebrt-live-provider-input-v0.6.2.2"
PROVIDER_OUTPUT_SCHEMA = "ebrt-live-provider-output-v0.6.2.2"
COMPILED_SCHEMA = "ebrt-live-compiled-closure-v0.6.2.2"
ACTUAL_STATE_SCHEMA = "ebrt-live-actual-before-state-v0.6.2.2"
CONTROL_SCHEMA = "ebrt-live-public-control-map-v0.6.2.2"
ACTUATOR_SCHEMA = "ebrt-live-compiled-actuator-v0.6.2.2"
DIFF_SCHEMA = "ebrt-live-public-diff-v0.6.2.2"
RESPONSE_SCHEMA = "ebrt-live-apply-revision-response-v0.6.2.2"
DEMO_REQUEST_SCHEMA = "ebrt-live-demo-request-v0.6.2.2"
ERROR_SCHEMA = "ebrt-live-error-v0.6.2.2"

MODEL = "gpt-5.6-sol"
REASONING_EFFORT = "low"
MAX_OUTPUT_TOKENS = 1024
TIMEOUT_SECONDS = 60.0

FLOAT_DTYPE = torch.float64
STATE_DECAY = 0.82
STEP_SIZE = 0.05
CONTROL_REGULARIZATION = 0.01
TERMINAL_TARGET = 1.0
FINITE_DIFFERENCE_EPSILON = 1.0e-6
FINITE_DIFFERENCE_TOLERANCE = 1.0e-8
MAX_CONTROL_L2 = 0.25
MAX_BACKTRACKS = 12

MAX_HTTP_BYTES = 256 * 1024
MAX_EVIDENCE = 64
MAX_SLOTS = 32
MAX_CANDIDATES = 16
MAX_SUPPORTS = 128
MAX_IDEMPOTENCY_ENTRIES = 128

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
        "signed_public_credit",
        "reinspection_salience",
        "source_effect",
    }
)

CLAIM_BOUNDARY = (
    "This invalidation-revision path applies one bounded public revision operation to caller-supplied public structure; it is not a semantic correctness oracle.",
    "The local float64 surrogate computes a differentiable reinspection-salience ranking from the compiled public Before support state, role-blind graph incidence, and the typed event.",
    "Suppress and preserve operations are typed-event compiler outputs, not signs inferred from the backward pass.",
    "The gradient stops at the public control map; JSON, provider parsing, generation, and verification are not differentiated.",
    "Operational acceptance means the one-call output is structurally valid and event-consistent; semantic correctness is NOT_ASSESSED.",
    "Effect attribution, causal superiority, quality improvement, hidden-state editing, attention control, and KV-cache control are NOT_ASSESSED.",
)

PROVIDER_INSTRUCTIONS = (
    "Return only the strict public Apply Revision response. Ordered raw evidence is the only semantic authority. "
    "Candidate closure IDs are opaque public alternatives. Select exactly one supplied closure, derive the current answer "
    "and every target value from the visible raw evidence, and honor the supplied Apply Revision operation by reinspecting "
    "the listed evidence, suppressing invalidated active evidence, and preserving listed stable evidence. The operation is "
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
    graph: ClosureGraph, *, evidence_order: Sequence[str]
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
        }
        ancestor = {
            evidence_id
            for upstream in row.depends_on_target_ids
            for evidence_id in total[upstream]
        }
        direct[target_id] = direct_set
        inherited[target_id] = ancestor - direct_set
        total[target_id] = direct_set | ancestor
    invalidated = {row.target_evidence_id for row in graph.invalidation_edges}
    active = {item for values in total.values() for item in values}
    _require(not (active & invalidated), "INVALIDATED_SUPPORT_ACTIVE")
    ordinal = {evidence_id: index for index, evidence_id in enumerate(evidence_order)}
    return {
        "active_support_evidence_ids": sorted(active, key=ordinal.__getitem__),
        "invalidated_evidence_ids": sorted(invalidated, key=ordinal.__getitem__),
        "invalidation_edges": sorted(
            (row.model_dump(mode="json") for row in graph.invalidation_edges),
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
        _fingerprint(row.graph.model_dump(mode="json"))
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
        len(enough_rankable) >= request.reinspection_count,
        "REINSPECTION_COUNT_EXCEEDS_ELIGIBLE_EVIDENCE",
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
) -> JsonObject:
    expected_keys = {
        "schema_version",
        "checkpoint_id",
        "current_answer",
        "selected_closure_id",
        "target_values",
    }
    _require(set(output) == expected_keys, "OUTPUT_SCHEMA_INVALID")
    if require_live_schema:
        _require(output["schema_version"] == PROVIDER_OUTPUT_SCHEMA, "OUTPUT_SCHEMA_VERSION_INVALID")
    _require(output["checkpoint_id"] == expected_checkpoint_id, "OUTPUT_CHECKPOINT_MISMATCH")
    _require(output["current_answer"] in request.answer_choices, "OUTPUT_ANSWER_OUTSIDE_DOMAIN")
    _require(output["selected_closure_id"] in allowed_closure_ids, "OUTPUT_CLOSURE_UNKNOWN")
    rows = output["target_values"]
    _require(isinstance(rows, list) and len(rows) == len(request.decision_slots), "OUTPUT_TARGET_COUNT_INVALID")
    slots = _slot_map(request)
    normalized_rows: list[JsonObject] = []
    seen: set[str] = set()
    for raw in rows:
        _require(isinstance(raw, Mapping), "OUTPUT_TARGET_NOT_OBJECT")
        _require(
            set(raw) == {"target_id", "target_type", "slot", "value"},
            "OUTPUT_TARGET_SCHEMA_INVALID",
        )
        row = TargetValue.model_validate(raw)
        _require(row.target_id not in seen, "OUTPUT_TARGET_DUPLICATE", row.target_id)
        _require(row.slot in slots, "OUTPUT_TARGET_SLOT_UNKNOWN", row.slot)
        spec = slots[row.slot]
        _require(
            row.target_type == spec.target_type
            and row.target_id == f"{spec.target_type}:{row.slot}",
            "OUTPUT_TARGET_TYPE_MISMATCH",
            row.target_id,
        )
        _require(row.value in spec.allowed_values, "OUTPUT_TARGET_VALUE_OUTSIDE_DOMAIN", row.target_id)
        seen.add(row.target_id)
        normalized_rows.append(row.model_dump(mode="json"))
    _require(seen == _expected_target_ids(request), "OUTPUT_TARGET_SET_MISMATCH")
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
    state = _seal(
        {
            "schema_version": ACTUAL_STATE_SCHEMA,
            "source_compiled_fingerprint_sha256": compiled_before["fingerprint_sha256"],
            "source_selected_closure_id": compiled_before["selected_closure_id"],
            "active_support_evidence_ids": list(compiled_before["active_support_evidence_ids"]),
            "components": components,
            "initial_scalar": scalar,
            "coordinate_semantics": "STRUCTURAL_REVISION_READINESS_ENUM_ORDER_INVARIANT",
        }
    )
    return scalar, state


def _public_incidence_effects(request: LiveRevisionRequest) -> tuple[dict[str, float], JsonObject]:
    evidence_ids = [row.evidence_id for row in request.all_raw_evidence]
    scores: defaultdict[str, float] = defaultdict(float)
    direct_hits: defaultdict[str, int] = defaultdict(int)
    inherited_hits: defaultdict[str, int] = defaultdict(int)
    for candidate in request.candidate_closures:
        closure = _structural_closure(candidate.graph, evidence_order=evidence_ids)
        for lineage in closure["targets"].values():
            for evidence_id in lineage["direct_active_evidence_ids"]:
                direct_hits[evidence_id] += 1
                scores[evidence_id] += 2.0
            for evidence_id in lineage["inherited_active_evidence_ids"]:
                inherited_hits[evidence_id] += 1
                scores[evidence_id] += 1.0
    target_count = len(request.decision_slots)
    event = request.event
    scores[event.correction_evidence_id] += 4.0 * (target_count + 1)
    for evidence_id in event.invalidated_evidence_ids:
        scores[evidence_id] += float(target_count + 1)
    for evidence_id in event.stable_evidence_ids:
        scores[evidence_id] += 0.5 * float(target_count + 1)
    maximum = max((scores[evidence_id] for evidence_id in evidence_ids), default=0.0)
    _require(maximum > 0.0 and math.isfinite(maximum), "INCIDENCE_EFFECT_BASIS_ZERO")
    effects = {
        evidence_id: float(scores[evidence_id] / maximum)
        for evidence_id in evidence_ids
    }
    receipt = _seal(
        {
            "schema_version": "ebrt-live-public-incidence-basis-v0.6.2.2",
            "source_kind": "CANDIDATE_GRAPH_INCIDENCE_PLUS_TYPED_EVENT",
            "candidate_graph_fingerprints_sha256": [
                _fingerprint(candidate.graph.model_dump(mode="json"))
                for candidate in request.candidate_closures
            ],
            "event_fingerprint_sha256": _fingerprint(request.event.model_dump(mode="json")),
            "direct_target_incidence_by_evidence_id": {
                evidence_id: direct_hits[evidence_id] for evidence_id in evidence_ids
            },
            "inherited_target_incidence_by_evidence_id": {
                evidence_id: inherited_hits[evidence_id] for evidence_id in evidence_ids
            },
            "raw_score_by_evidence_id": {
                evidence_id: float(scores[evidence_id]) for evidence_id in evidence_ids
            },
            "normalized_effect_by_evidence_id": effects,
            "reserved_gold_fields_participated": False,
            "caller_semantic_content_verified": False,
        }
    )
    return effects, receipt


def _controller_loss(
    controls: torch.Tensor,
    effects: torch.Tensor,
    *,
    initial_state: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    state = torch.tensor(initial_state, dtype=FLOAT_DTYPE)
    states: list[torch.Tensor] = []
    for control, effect in zip(controls, effects, strict=True):
        state = torch.tanh(STATE_DECAY * state + control * effect)
        states.append(state)
    loss = (state - TERMINAL_TARGET).square() + CONTROL_REGULARIZATION * controls.square().sum()
    return loss, torch.stack(states)


def _derive_control_map(
    request: LiveRevisionRequest, compiled_before: Mapping[str, Any]
) -> JsonObject:
    evidence_ids = [row.evidence_id for row in request.all_raw_evidence]
    initial_scalar, actual_state = _actual_before_state(request, compiled_before)
    effect_by_id, source_receipt = _public_incidence_effects(request)
    effects = torch.tensor([effect_by_id[item] for item in evidence_ids], dtype=FLOAT_DTYPE)
    controls = torch.zeros(len(evidence_ids), dtype=FLOAT_DTYPE, requires_grad=True)
    loss_before, states_before = _controller_loss(
        controls, effects, initial_state=initial_scalar
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
    accepted_backtrack = -1
    for backtrack in range(MAX_BACKTRACKS + 1):
        candidate = bounded * (0.5**backtrack)
        candidate_loss, candidate_states = _controller_loss(
            candidate, effects, initial_state=initial_scalar
        )
        if float(candidate_loss.detach()) < float(loss_before.detach()):
            accepted = candidate
            accepted_states = candidate_states
            accepted_loss = candidate_loss
            accepted_backtrack = backtrack
            break
    _require(accepted is not None, "SURROGATE_NO_DESCENT")
    assert accepted_states is not None and accepted_loss is not None

    epsilon = FINITE_DIFFERENCE_EPSILON
    finite_difference: list[float] = []
    for index in range(len(evidence_ids)):
        positive = torch.zeros(len(evidence_ids), dtype=FLOAT_DTYPE)
        negative = torch.zeros(len(evidence_ids), dtype=FLOAT_DTYPE)
        positive[index] = epsilon
        negative[index] = -epsilon
        plus, _ = _controller_loss(positive, effects, initial_state=initial_scalar)
        minus, _ = _controller_loss(negative, effects, initial_state=initial_scalar)
        finite_difference.append(float((plus - minus) / (2.0 * epsilon)))
    errors = [
        abs(float(gradient[index]) - finite_difference[index])
        for index in range(len(evidence_ids))
    ]
    norm = float(torch.linalg.vector_norm(accepted))
    active_before = set(compiled_before["active_support_evidence_ids"])
    rows = [
        {
            "evidence_id": evidence_id,
            "source_effect": float(effects[index]),
            "gradient": float(gradient[index]),
            "finite_difference_gradient": finite_difference[index],
            "reinspection_salience": abs(float(accepted[index])),
            "active_before": evidence_id in active_before,
        }
        for index, evidence_id in enumerate(evidence_ids)
    ]
    checks = {
        "actual_before_state_bound_to_controller": (
            actual_state["source_compiled_fingerprint_sha256"]
            == compiled_before["fingerprint_sha256"]
        ),
        "local_backward_executed": controls.grad is not None,
        "finite_reinspection_salience": all(
            math.isfinite(float(row["reinspection_salience"])) for row in rows
        ),
        "surrogate_objective_decreased": (
            float(accepted_loss.detach()) < float(loss_before.detach())
        ),
        "non_neutral_control_map": any(
            float(row["reinspection_salience"]) > 0.0 for row in rows
        ),
        "control_budget_respected": norm <= MAX_CONTROL_L2 + 1.0e-15,
        "finite_difference_agreement": max(errors) <= FINITE_DIFFERENCE_TOLERANCE,
        "gradient_stops_before_provider": True,
        "reserved_gold_fields_absent": not bool(
            _recursive_keys(request.model_dump(mode="json"))
            & FORBIDDEN_REQUEST_KEYS
        ),
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
            "objective_after": float(accepted_loss.detach()),
            "terminal_target": TERMINAL_TARGET,
            "state_trace_before": [float(value) for value in states_before.detach()],
            "state_trace_after": [float(value) for value in accepted_states.detach()],
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


def _compile_actuator(
    request: LiveRevisionRequest,
    compiled_before: Mapping[str, Any],
    control_map: Mapping[str, Any],
) -> JsonObject:
    invalidated = set(request.event.invalidated_evidence_ids)
    stable = set(request.event.stable_evidence_ids)
    eligible = [
        row
        for row in control_map["credit_rows"]
        if row["evidence_id"] not in invalidated
        and row["evidence_id"] not in stable
        and float(row["reinspection_salience"]) > 0.0
    ]
    eligible.sort(
        key=lambda row: (-float(row["reinspection_salience"]), row["evidence_id"])
    )
    _require(
        len(eligible) >= request.reinspection_count,
        "ACTUATOR_REINSPECTION_COUNT_UNAVAILABLE",
    )
    reinspect = [
        str(row["evidence_id"])
        for row in eligible[: request.reinspection_count]
    ]
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
    return _seal(
        {
            "schema_version": ACTUATOR_SCHEMA,
            "source_before_compiled_fingerprint_sha256": compiled_before["fingerprint_sha256"],
            "source_control_map_fingerprint_sha256": control_map["fingerprint_sha256"],
            "event_id": request.event.event_id,
            "correction_evidence_id": request.event.correction_evidence_id,
            "reinspect_evidence_ids": reinspect,
            "reinspect_source": "DIFFERENTIABLE_REINSPECTION_SALIENCE_RANKING",
            "suppress_evidence_ids": suppress,
            "suppress_source": "TYPED_EVENT_INVALIDATION",
            "preserve_evidence_ids": preserve,
            "preserve_source": "TYPED_EVENT_STABILITY",
            "reinspection_limit": request.reinspection_count,
            "control_l2": control_map["control_l2"],
            "max_control_l2": control_map["max_control_l2"],
            "gradient_stops_here": True,
        }
    )


def _opaque_closure_id(prefix: str, graph: ClosureGraph) -> str:
    return f"{prefix}_{_fingerprint(graph.model_dump(mode='json'))[:16]}"


def _provider_candidate_rows(request: LiveRevisionRequest) -> list[JsonObject]:
    rows = [
        {
            "closure_id": _opaque_closure_id("K", candidate.graph),
            "graph": candidate.graph.model_dump(mode="json"),
        }
        for candidate in request.candidate_closures
    ]
    _require(
        len({row["closure_id"] for row in rows}) == len(rows),
        "OPAQUE_CLOSURE_ID_COLLISION",
    )
    return rows


def _build_provider_payload(
    request: LiveRevisionRequest,
    compiled_before: Mapping[str, Any],
    actuator: Mapping[str, Any],
) -> JsonObject:
    prior = {
        "schema_version": "ebrt-live-prior-state-v0.6.2.2",
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
        "prior_public_state": prior,
        "apply_revision": {
            "schema_version": "ebrt-live-apply-revision-operation-v0.6.2.2",
            "operation": "APPLY_REVISION",
            "event": request.event.model_dump(mode="json"),
            "reinspect_evidence_ids": list(actuator["reinspect_evidence_ids"]),
            "suppress_evidence_ids": list(actuator["suppress_evidence_ids"]),
            "preserve_evidence_ids": list(actuator["preserve_evidence_ids"]),
            "source_prior_state_fingerprint_sha256": _fingerprint(prior),
            "source_actuator_fingerprint_sha256": actuator["fingerprint_sha256"],
            "semantic_authority": "ordered raw evidence only",
            "gradient_boundary": "gradient stopped before this JSON operation and hosted generation",
        },
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
        source = _validated_json_file(
            DEMO_PROVIDER_INPUTS_PATH, label="demo_provider_inputs"
        )
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
        payload = _build_provider_payload(request, compiled_before, actuator)
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
        audit = _audit_after(request, compiled_before, compiled_after)
        mechanism_pass = control_map["status"] == "PASS" and bool(
            actuator["gradient_stops_here"]
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
                },
                "public_control_map": {
                    "fingerprint_sha256": control_map["fingerprint_sha256"],
                    "control_l2": control_map["control_l2"],
                    "max_control_l2": control_map["max_control_l2"],
                    "credit_rows": control_map["credit_rows"],
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
                    "gradient_stops_here": actuator["gradient_stops_here"],
                },
                "boundary": (
                    "Gradient stops at the public control map. GPT-5.6, JSON "
                    "projection, generation, and verification are not backpropagated through."
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
                "semantic_correctness_status": "NOT_ASSESSED",
                "effect_attribution_status": "NOT_ASSESSED",
                "provider_attempts": 1,
            },
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


def build_demo_request(*, request_id: str | None = None) -> JsonObject:
    """Adapt only the public provider inputs from sealed v0.6.2.1."""

    source = _validated_json_file(
        DEMO_PROVIDER_INPUTS_PATH, label="demo_provider_inputs"
    )
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
    source = _validated_json_file(
        DEMO_PROVIDER_INPUTS_PATH, label="demo_provider_inputs"
    )
    return {
        "schema_version": DEMO_REQUEST_SCHEMA,
        "provenance": "CONTAMINATED_REGRESSION_FIXTURE",
        "source_artifact_fingerprint_sha256": source["fingerprint_sha256"],
        "request": request,
    }


def capabilities_value(*, provider_mode: str) -> JsonObject:
    return {
        "schema_version": "ebrt-live-capabilities-v0.6.2.2",
        "status": "READY",
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
            "terminal_idempotency_capacity": MAX_IDEMPOTENCY_ENTRIES,
        },
        "operation_scope": "TYPED_INVALIDATION_REVISION",
        "gradient_boundary": "public control map",
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
    ) -> None:
        self.provider_factory = provider_factory
        self.provider_mode = provider_mode
        self.engine = EBRTRevisionEngine()
        self._gate = threading.BoundedSemaphore(1)
        self._lock = threading.Lock()
        self._terminal: OrderedDict[
            str, tuple[str, Literal["success", "error"], JsonObject, int]
        ] = OrderedDict()
        self._inflight: dict[str, str] = {}
        self.provider_attempts_started = 0

    @property
    def provider_configured(self) -> bool:
        return self.provider_mode == "scripted" or bool(os.environ.get("OPENAI_API_KEY"))

    def health(self) -> JsonObject:
        return {
            "schema_version": "ebrt-live-health-v0.6.2.2",
            "status": "READY" if self.provider_configured else "PROVIDER_UNCONFIGURED",
            "provider_mode": self.provider_mode,
            "provider_configured": self.provider_configured,
            "model": MODEL if self.provider_mode == "openai" else "SCRIPTED_TEST_ONLY",
            "credentials_exposed": False,
        }

    def apply(self, request_value: Mapping[str, Any]) -> tuple[JsonObject, bool]:
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
                if terminal[1] == "success":
                    return _clone(terminal[2]), True
                raise LiveRevisionError(
                    str(terminal[2]["error"]["code"]),
                    http_status=terminal[3],
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
            if not self._gate.acquire(blocking=False):
                raise LiveRevisionError("PROVIDER_BUSY", http_status=429)
            if len(self._terminal) >= MAX_IDEMPOTENCY_ENTRIES:
                self._gate.release()
                raise LiveRevisionError(
                    "IDEMPOTENCY_CAPACITY_EXHAUSTED", http_status=503
                )
            self._inflight[request_id] = fingerprint
            self.provider_attempts_started += 1
        try:
            response = self.engine.execute(request, self.provider_factory())
        except LiveRevisionError as error:
            terminal_error = LiveRevisionError(
                error.reason_code,
                http_status=error.http_status,
            )
            with self._lock:
                self._terminal[request_id] = (
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
                self._terminal[request_id] = (
                    fingerprint,
                    "error",
                    _error_value(terminal_error),
                    terminal_error.http_status,
                )
                self._inflight.pop(request_id, None)
                self._gate.release()
            raise terminal_error from None
        with self._lock:
            self._terminal[request_id] = (
                fingerprint,
                "success",
                _clone(response),
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
        server_version = "EBRTLive/0.6.2.2"
        sys_version = ""

        def log_message(self, _format: str, *_args: Any) -> None:
            return

        @property
        def _origin(self) -> str | None:
            value = self.headers.get("Origin")
            return value if value else None

        def _origin_allowed(self) -> bool:
            return self._origin is None or self._origin in ALLOWED_ORIGINS

        def _send_json(
            self,
            status: int,
            value: Mapping[str, Any],
            *,
            idempotent_replay: bool = False,
        ) -> None:
            raw = _canonical_bytes(value, trailing_newline=True)
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cross-Origin-Resource-Policy", "same-site")
            self.send_header("Content-Security-Policy", "default-src 'none'")
            self.send_header("Connection", "close")
            if self._origin in ALLOWED_ORIGINS:
                self.send_header("Access-Control-Allow-Origin", self._origin)
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
            if not self._guard_origin():
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
                "Accept, Content-Type, Idempotency-Key",
            )
            self.send_header("Access-Control-Max-Age", "600")
            self.send_header("Vary", "Origin")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            if not self._guard_origin():
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
            if not self._guard_origin():
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
                response, replay = service.apply(value)
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
    service = RevisionService(
        _provider_factory(provider_mode), provider_mode=provider_mode
    )
    server = _ThreadingServer((host, port), _handler_type(service))
    return server, service


def serve(
    *,
    host: str,
    port: int,
    provider_mode: Literal["openai", "scripted"],
) -> None:
    server, _service = create_http_server(
        host=host, port=port, provider_mode=provider_mode
    )
    observed_host, observed_port = server.server_address[:2]
    print(
        _pretty(
            {
                "schema_version": "ebrt-live-server-start-v0.6.2.2",
                "status": "READY",
                "url": f"http://{observed_host}:{observed_port}",
                "provider_mode": provider_mode,
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
    engine = EBRTRevisionEngine()
    demo = build_demo_request(request_id="live-demo-self-test-001")
    generic = _synthetic_generic_request()
    with _network_denied() as network:
        demo_result = engine.execute(demo, ScriptedLiveRevisionProvider())
        generic_result = engine.execute(generic, ScriptedLiveRevisionProvider())
    checks["engine_self_test_network_zero"] = network["network_calls"] == 0
    checks["sealed_demo_operational_pass"] = (
        demo_result["verification"]["operational_acceptance_status"] == "PASS"
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
    checks["claim_boundaries_remain_separate"] = all(
        result["verification"]["semantic_correctness_status"] == "NOT_ASSESSED"
        and result["verification"]["effect_attribution_status"] == "NOT_ASSESSED"
        for result in (demo_result, generic_result)
    )

    def rejected_with(value: Mapping[str, Any], reason_code: str) -> bool:
        try:
            validate_request_mapping(value)
        except LiveRevisionError as error:
            return error.reason_code == reason_code
        return False

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
    checks["temporal_prefix_and_duplicate_catalog_rejected"] = (
        rejected_with(
            prefix_violation,
            "BEFORE_HORIZON_MUST_BE_EXACT_PRE_EVENT_PREFIX",
        )
        and rejected_with(duplicate_catalog, "CANDIDATE_GRAPH_DUPLICATE")
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
        and [row["reinspection_salience"] for row in generic_control["credit_rows"]]
        == [row["reinspection_salience"] for row in reversed_control["credit_rows"]]
    )

    provider_payload = _build_provider_payload(
        generic_request,
        generic_before,
        _compile_actuator(generic_request, generic_before, generic_control),
    )
    opaque_ids = [row["closure_id"] for row in provider_payload["candidate_closures"]]
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

    server, service = create_http_server(
        host="127.0.0.1", port=0, provider_mode="scripted"
    )
    port = int(server.server_address[1])
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05})
    thread.daemon = True
    thread.start()
    try:
        health_status, health, _ = _http_json(port, "GET", "/api/health")
        demo_status, envelope, _ = _http_json(port, "GET", "/api/demo-request")
        http_request = envelope["request"]
        post_headers = {"Idempotency-Key": http_request["request_id"]}
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
        conflict = _clone(http_request)
        conflict["question"] = conflict["question"] + " "
        conflict_status, conflict_body, _ = _http_json(
            port,
            "POST",
            "/api/apply-revision",
            value=conflict,
            headers=post_headers,
        )
        origin_status, origin_body, _ = _http_json(
            port,
            "GET",
            "/api/health",
            headers={"Origin": "https://attacker.invalid"},
        )
        duplicate_body = (
            b'{"request_id":"duplicate-0001","request_id":"duplicate-0002"}'
        )
        duplicate_status, duplicate_body_result, _ = _http_json(
            port,
            "POST",
            "/api/apply-revision",
            raw=duplicate_body,
            headers={"Idempotency-Key": "duplicate-0001"},
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    checks["http_health_and_demo_are_zero_call"] = (
        health_status == demo_status == 200
        and health["provider_mode"] == "scripted"
        and envelope["schema_version"] == DEMO_REQUEST_SCHEMA
    )
    checks["http_live_post_completes_once"] = (
        post_status == 200
        and first["verification"]["operational_acceptance_status"] == "PASS"
        and first_headers.get("x-ebrt-idempotent-replay") is None
    )
    checks["http_idempotent_repeat_is_cached"] = (
        repeat_status == 200
        and repeat == first
        and repeat_headers.get("x-ebrt-idempotent-replay") == "true"
        and service.provider_attempts_started == 1
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
            "schema_version": "ebrt-live-self-test-v0.6.2.2",
            "status": "PASS",
            "checks": checks,
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
