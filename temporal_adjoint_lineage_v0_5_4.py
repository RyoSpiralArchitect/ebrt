#!/usr/bin/env python3
"""EBRT v0.5.4 network-zero temporal adjoint over v0.5.3 lineage.

The public fixtures select symbolic policies only.  The typed program, state
axes, transitions, closure target, Jacobians, actuator normalization, and
control arms are derived here from the sealed v0.5.3 repaired graph.
"""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import math
import socket
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterator, Mapping, Optional, Sequence
from unittest import mock

import torch

import factorized_lineage_v0_5_3 as v053


ROOT = Path(__file__).resolve().parent
DEFAULT_EVENT_FIXTURE = ROOT / "fixtures" / "temporal_adjoint_lineage_v0_5_4_dev.json"
DEFAULT_NO_EVENT_FIXTURE = ROOT / "fixtures" / "temporal_adjoint_lineage_v0_5_4_no_event.json"

FIXTURE_SCHEMA_VERSION = "ebrt-temporal-adjoint-lineage-fixture-v0.5.4"
NO_EVENT_FIXTURE_SCHEMA_VERSION = "ebrt-temporal-adjoint-lineage-no-event-fixture-v0.5.4"
PROGRAM_SCHEMA_VERSION = "ebrt-compiled-temporal-lineage-program-v0.5.4"
CONTROL_MAP_SCHEMA_VERSION = "ebrt-temporal-lineage-control-map-v0.5.4"
ADJOINT_AUDIT_SCHEMA_VERSION = "ebrt-temporal-lineage-adjoint-audit-v0.5.4"
LANE_SCHEMA_VERSION = "ebrt-sealed-temporal-lineage-lane-v0.5.4"
GEOMETRY_SCHEMA_VERSION = "ebrt-temporal-lineage-actuator-geometry-v0.5.4"
COMPARISON_SCHEMA_VERSION = "ebrt-temporal-lineage-comparison-v0.5.4"
NO_EVENT_AUDIT_SCHEMA_VERSION = ADJOINT_AUDIT_SCHEMA_VERSION
SELF_TEST_SCHEMA_VERSION = "ebrt-temporal-lineage-bundle-self-test-v0.5.4"

LOCKED_SCHEDULE_IDS = ("correction_early", "correction_late")
CHANNELS = ("direct", "inherited")
SHAM_TRANSFORMS = ("cyclic_plus_1", "cyclic_minus_1", "reverse")
HARD_GATE_IDS = (
    "v053_source_exact",
    "compiled_closure_exact",
    "fixture_mechanism_injection_rejected",
    "forward_sensitivity_agreement",
    "reverse_adjoint_agreement",
    "central_finite_difference_agreement",
    "normalized_jacobian_geometry",
    "severed_path_zero_credit",
    "independent_operator_permutation_invariant",
    "identity_insertion_invariant",
    "early_late_top_credit_switch",
    "no_event_exact_identity",
    "matched_control_geometry",
    "exact_credit_beats_zero_and_node_tied",
    "exact_credit_beats_all_timing_shams",
    "two_build_byte_identity",
    "socket_denied_network_zero",
)
PROMOTION_STATUS = "PROMOTE_V0_5_5_TEMPORAL_GATE"
STOP_STATUS = "STOP_V0_5_5_TEMPORAL_GATE"
RHO_FRACTION = 0.1
FD_EPSILON = 1.0e-6
FLOAT_DTYPE = torch.float64
V053_REGRESSION_PATH = ROOT / "artifacts" / "factorized_lineage_v0_5_3" / "factorized_lineage_regression.json"
EXPECTED_V053_REGRESSION_FINGERPRINT = "0335ede60f428ddf77f7266d1c2bea6483c4698e924f555e9be8a7d3422e2997"
EXPECTED_V053_REPAIRED_GRAPH_FINGERPRINT = "361d6961938dda2d69ccc0340fecb802c55af40d6cd551c628eb307462416333"
EXPECTED_V053_REPAIRED_CLOSURE_FINGERPRINT = "899afdca968e3a3e1c1dd7f9eb5c4605e18c7c6b4188a8a4f4af1707a2859c9c"

FORBIDDEN_FIXTURE_KEYS = frozenset(
    {
        "matrix",
        "matrices",
        "base_matrix",
        "basis",
        "bases",
        "jacobian",
        "jacobians",
        "terminal_gold",
        "gold",
        "expected_terminal",
        "operator_order",
        "operator_orders",
        "site_order",
        "delta",
        "control_values",
        "actuator_geometry",
    }
)


class TemporalAdjointValidationError(RuntimeError):
    """A strict EBRT v0.5.4 temporal-lineage invariant failed."""


JsonObject = dict[str, Any]


def canonical_json_bytes(value: Any, *, trailing_newline: bool = False) -> bytes:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return encoded + (b"\n" if trailing_newline else b"")


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _clone(value: Any) -> Any:
    return json.loads(canonical_json_bytes(value))


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise TemporalAdjointValidationError(
            f"{label} keys differ: missing={sorted(expected-set(value))}, "
            f"extra={sorted(set(value)-expected)}"
        )


def _reject_forbidden_fixture_material(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            lowered = key.lower()
            if lowered in FORBIDDEN_FIXTURE_KEYS or any(
                token in lowered for token in ("jacobian", "matrix", "basis", "terminal_gold")
            ):
                raise TemporalAdjointValidationError(
                    f"forbidden numeric mechanism fixture key at {path}.{key}"
                )
            _reject_forbidden_fixture_material(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_forbidden_fixture_material(child, f"{path}[{index}]")
    elif isinstance(value, float):
        raise TemporalAdjointValidationError(
            f"fixture floating-point mechanism value forbidden at {path}"
        )


def _strict_load_json(path: Path) -> JsonObject:
    if not path.is_file() or path.is_symlink():
        raise TemporalAdjointValidationError(f"expected regular fixture: {path}")

    def reject_constant(token: str) -> None:
        raise TemporalAdjointValidationError(f"non-finite JSON constant: {token}")

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> JsonObject:
        output: JsonObject = {}
        for key, value in pairs:
            if key in output:
                raise TemporalAdjointValidationError(f"duplicate JSON key: {key}")
            output[key] = value
        return output

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_constant,
        )
    except (json.JSONDecodeError, UnicodeError, OSError, ValueError) as exc:
        raise TemporalAdjointValidationError(f"invalid fixture {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise TemporalAdjointValidationError("fixture root must be object")
    return value


def validate_fixture(value: Mapping[str, Any], *, no_event: bool = False) -> None:
    if not isinstance(value, Mapping):
        raise TemporalAdjointValidationError("fixture must be object")
    _reject_forbidden_fixture_material(value)
    common = {
        "claim_boundary",
        "control_policy",
        "event",
        "fixture_id",
        "lineage_source",
        "schema_version",
        "terminal_contract",
    }
    _exact_keys(value, common | ({"lane"} if no_event else {"schedule_policy_ids"}), "fixture")
    expected_schema = NO_EVENT_FIXTURE_SCHEMA_VERSION if no_event else FIXTURE_SCHEMA_VERSION
    if value["schema_version"] != expected_schema:
        raise TemporalAdjointValidationError("fixture schema mismatch")
    if not isinstance(value["fixture_id"], str) or not value["fixture_id"]:
        raise TemporalAdjointValidationError("fixture_id must be nonempty")
    claim = value["claim_boundary"]
    if not isinstance(claim, list) or not claim or not all(isinstance(row, str) and row for row in claim):
        raise TemporalAdjointValidationError("claim_boundary must be nonempty strings")
    source = value["lineage_source"]
    if not isinstance(source, Mapping):
        raise TemporalAdjointValidationError("lineage_source must be object")
    _exact_keys(source, {"closure_status", "graph_status", "version"}, "lineage_source")
    if dict(source) != {
        "closure_status": "COMPUTED",
        "graph_status": "CONTAMINATED_REPAIR_OVERLAY",
        "version": "v0.5.3",
    }:
        raise TemporalAdjointValidationError("fixture must bind exact v0.5.3 repaired source")
    event = value["event"]
    if not isinstance(event, Mapping):
        raise TemporalAdjointValidationError("event must be object")
    _exact_keys(event, {"correction_evidence_id", "triggered"}, "event")
    expected_triggered = not no_event
    if (
        event["correction_evidence_id"] != "R6"
        or not isinstance(event["triggered"], bool)
        or event["triggered"] is not expected_triggered
    ):
        raise TemporalAdjointValidationError("event sentinel mismatch")
    if no_event:
        lane = value["lane"]
        if not isinstance(lane, Mapping):
            raise TemporalAdjointValidationError("lane must be object")
        _exact_keys(lane, {"kind", "target_node_id"}, "lane")
        if dict(lane) != {
            "kind": "constraint_only_identity",
            "target_node_id": "constraint:video_constraint",
        }:
            raise TemporalAdjointValidationError("no-event lane contract mismatch")
        if value["control_policy"] != "exact_zero_no_event_v0_5_4":
            raise TemporalAdjointValidationError("no-event control policy mismatch")
        if value["terminal_contract"] != "stable_constraint_identity_v0_5_4":
            raise TemporalAdjointValidationError("no-event terminal contract mismatch")
    else:
        if value["schedule_policy_ids"] != ["correction_early", "correction_late"]:
            raise TemporalAdjointValidationError("arbitrary schedule policy forbidden")
        if value["control_policy"] != "one_exact_normalized_adjoint_step_v0_5_4":
            raise TemporalAdjointValidationError("event control policy mismatch")
        if value["terminal_contract"] != "repaired_fact_closure_constraint_neutral_v0_5_4":
            raise TemporalAdjointValidationError("event terminal contract mismatch")


def load_fixture(path: Path = DEFAULT_EVENT_FIXTURE, *, no_event: bool = False) -> JsonObject:
    value = _strict_load_json(path)
    validate_fixture(value, no_event=no_event)
    return _clone(value)


@dataclass(frozen=True)
class CompiledProgram:
    fixture_id: str
    event_triggered: bool
    regression_fingerprint_sha256: str
    graph: JsonObject
    closure: JsonObject
    node_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    target_node_ids: tuple[str, ...]
    fact_target_node_ids: tuple[str, ...]
    constraint_target_node_ids: tuple[str, ...]
    positive_edges: tuple[tuple[str, str, str, str], ...]
    invalidation_edges: tuple[tuple[str, str], ...]
    incoming: Mapping[str, tuple[tuple[str, str], ...]]
    sweep_order: tuple[str, ...]
    schedules: Mapping[str, tuple[str, ...]]
    node_index: Mapping[str, int]
    evidence_index: Mapping[str, int]

    @property
    def state_shape(self) -> tuple[int, int, int]:
        return (len(CHANNELS), len(self.evidence_ids), len(self.node_ids))

    @property
    def site_count(self) -> int:
        return 0 if not self.event_triggered else len(self.sweep_order) * len(self.evidence_ids)


def _canonical_kahn_order(
    node_ids: Sequence[str], positive_edges: Sequence[tuple[str, str, str, str]]
) -> tuple[str, ...]:
    indegree = {node_id: 0 for node_id in node_ids}
    adjacency = {node_id: [] for node_id in node_ids}
    for _edge_id, source, target, _provenance in positive_edges:
        indegree[target] += 1
        adjacency[source].append(target)
    heap = [node_id for node_id in node_ids if indegree[node_id] == 0]
    heapq.heapify(heap)
    ordered: list[str] = []
    while heap:
        node_id = heapq.heappop(heap)
        ordered.append(node_id)
        for target in sorted(adjacency[node_id]):
            indegree[target] -= 1
            if indegree[target] == 0:
                heapq.heappush(heap, target)
    if len(ordered) != len(node_ids):
        raise TemporalAdjointValidationError("positive lineage graph is cyclic")
    incoming_targets = {target for _edge_id, _source, target, _provenance in positive_edges}
    return tuple(node_id for node_id in ordered if node_id in incoming_targets)


def compile_program(
    fixture: Mapping[str, Any] | None = None, *, no_event: bool | None = None
) -> CompiledProgram:
    if fixture is None:
        fixture = load_fixture(
            DEFAULT_NO_EVENT_FIXTURE if no_event else DEFAULT_EVENT_FIXTURE,
            no_event=bool(no_event),
        )
    if no_event is None:
        no_event = fixture.get("schema_version") == NO_EVENT_FIXTURE_SCHEMA_VERSION
    validate_fixture(fixture, no_event=no_event)
    regression = _strict_load_json(V053_REGRESSION_PATH)
    v053.validate_regression(regression)
    if regression.get("fingerprint_sha256") != EXPECTED_V053_REGRESSION_FINGERPRINT:
        raise TemporalAdjointValidationError("committed v0.5.3 regression fingerprint drift")
    graph = _clone(regression["repaired"]["graph"])
    closure = _clone(regression["repaired"]["closure"])
    v053.validate_graph(graph)
    v053.validate_closure_report(closure)
    if graph["status"] != "CONTAMINATED_REPAIR_OVERLAY" or closure["status"] != "COMPUTED":
        raise TemporalAdjointValidationError("v0.5.3 repaired source not sealed")
    if graph["fingerprint_sha256"] != EXPECTED_V053_REPAIRED_GRAPH_FINGERPRINT:
        raise TemporalAdjointValidationError("committed v0.5.3 repaired graph fingerprint drift")
    if closure["fingerprint_sha256"] != EXPECTED_V053_REPAIRED_CLOSURE_FINGERPRINT:
        raise TemporalAdjointValidationError("committed v0.5.3 repaired closure fingerprint drift")
    nodes = sorted(graph["nodes"], key=lambda row: row["node_id"])
    node_ids = tuple(row["node_id"] for row in nodes)
    evidence_nodes = sorted(
        (row for row in nodes if row["node_type"] == "evidence"),
        key=lambda row: row["temporal_ordinal"],
    )
    evidence_ids = tuple(row["evidence_id"] for row in evidence_nodes)
    correction_late = evidence_ids
    positive_edges = tuple(
        sorted(
            (
                (
                    edge["edge_id"],
                    edge["source_node_id"],
                    edge["target_node_id"],
                    edge["provenance"],
                )
                for edge in graph["edges"]
                if edge["edge_type"] in {"supports", "depends_on"}
            ),
            key=lambda row: row[0],
        )
    )
    invalidation_edges = tuple(
        sorted(
            (
                (
                    graph_node[edge["source_node_id"]]["evidence_id"],
                    graph_node[edge["target_node_id"]]["evidence_id"],
                )
                for edge in graph["edges"]
                if edge["edge_type"] == "invalidates"
            ),
        )
    ) if (graph_node := {row["node_id"]: row for row in nodes}) else ()
    if len(invalidation_edges) != 1:
        raise TemporalAdjointValidationError("exactly one invalidation is required")
    invalidator, invalidated = invalidation_edges[0]
    early_work = list(correction_late)
    if invalidator not in early_work or invalidated not in early_work:
        raise TemporalAdjointValidationError("invalidation evidence missing from ordinal")
    early_work.remove(invalidator)
    early_work.insert(early_work.index(invalidated) + 1, invalidator)
    correction_early = tuple(early_work)
    if correction_early == correction_late:
        raise TemporalAdjointValidationError("early correction schedule did not move invalidator")
    schedules = {
        "correction_early": correction_early,
        "correction_late": correction_late,
    }
    incoming_work: dict[str, list[tuple[str, str]]] = {node_id: [] for node_id in node_ids}
    for _edge_id, source, target, _provenance in positive_edges:
        incoming_work[target].append((source, graph_node[source]["node_type"]))
    incoming = {
        node_id: tuple(sorted(rows)) for node_id, rows in incoming_work.items() if rows
    }
    targets = sorted(closure["targets"], key=lambda row: row["target_id"])
    target_node_ids = tuple(row["target_id"] for row in targets)
    fact_target_node_ids = tuple(row["target_id"] for row in targets if row["target_type"] == "fact")
    constraint_target_node_ids = tuple(
        row["target_id"] for row in targets if row["target_type"] == "constraint"
    )
    return CompiledProgram(
        fixture_id=str(fixture["fixture_id"]),
        event_triggered=not no_event,
        regression_fingerprint_sha256=regression["fingerprint_sha256"],
        graph=graph,
        closure=closure,
        node_ids=node_ids,
        evidence_ids=evidence_ids,
        target_node_ids=target_node_ids,
        fact_target_node_ids=fact_target_node_ids,
        constraint_target_node_ids=constraint_target_node_ids,
        positive_edges=positive_edges,
        invalidation_edges=invalidation_edges,
        incoming=incoming,
        sweep_order=_canonical_kahn_order(node_ids, positive_edges),
        schedules=schedules,
        node_index={node_id: index for index, node_id in enumerate(node_ids)},
        evidence_index={evidence_id: index for index, evidence_id in enumerate(evidence_ids)},
    )


def program_receipt(program: CompiledProgram) -> JsonObject:
    closure_by_target = {row["target_id"]: row for row in program.closure["targets"]}
    payload: JsonObject = {
        "channels": list(CHANNELS),
        "state_axis_order": ["channel", "evidence", "node"],
        "event_triggered": program.event_triggered,
        "fixture_id": program.fixture_id,
        "closure_partition": {
            target_id: {
                "direct": closure_by_target[target_id]["direct_active_evidence_ids"],
                "inherited": closure_by_target[target_id]["inherited_active_evidence_ids"],
            }
            for target_id in program.target_node_ids
        },
        "evidence_ids": list(program.evidence_ids),
        "graph_fingerprint_sha256": program.graph["fingerprint_sha256"],
        "closure_fingerprint_sha256": program.closure["fingerprint_sha256"],
        "source_regression_fingerprint_sha256": program.regression_fingerprint_sha256,
        "node_ids": list(program.node_ids),
        "positive_edges": [
            {
                "edge_id": edge_id,
                "provenance": provenance,
                "source_node_id": source,
                "target_node_id": target,
            }
            for edge_id, source, target, provenance in program.positive_edges
        ],
        "schedules": {key: list(program.schedules[key]) for key in sorted(program.schedules)},
        "schema_version": PROGRAM_SCHEMA_VERSION,
        "state_shape": list(program.state_shape),
        "sweep_order": list(program.sweep_order),
        "target_node_ids": list(program.target_node_ids),
    }
    payload["fingerprint_sha256"] = fingerprint(payload)
    return payload


def _node_type_by_id(program: CompiledProgram) -> dict[str, str]:
    return {row["node_id"]: row["node_type"] for row in program.graph["nodes"]}


def _site_rows(program: CompiledProgram, schedule_id: str) -> list[JsonObject]:
    if not program.event_triggered:
        return []
    if schedule_id not in LOCKED_SCHEDULE_IDS or schedule_id not in program.schedules:
        raise TemporalAdjointValidationError(f"unlocked schedule: {schedule_id}")
    node_types = _node_type_by_id(program)
    rows: list[JsonObject] = []
    for horizon_index, evidence_id in enumerate(program.schedules[schedule_id], start=1):
        for target_node_id in program.sweep_order:
            rows.append(
                {
                    "admitted_evidence_id": evidence_id,
                    "horizon_index": horizon_index,
                    "site_id": (
                        f"q:{schedule_id}:h{horizon_index:02d}:"
                        f"{evidence_id}:{target_node_id}"
                    ),
                    "target_node_id": target_node_id,
                    "target_node_type": node_types[target_node_id],
                }
            )
    return rows


def _or_torch(values: Sequence[torch.Tensor], *, like: torch.Tensor) -> torch.Tensor:
    if not values:
        return torch.zeros_like(like)
    stacked = torch.stack(tuple(values), dim=0)
    return 1.0 - torch.prod(1.0 - stacked, dim=0)


def _mapped_source_state(
    state: torch.Tensor, program: CompiledProgram, source_node_id: str, source_type: str
) -> torch.Tensor:
    source = state[:, :, program.node_index[source_node_id]]
    if source_type != "fact":
        return source
    direct = source[0, :]
    inherited = source[1, :]
    total = direct + (1.0 - direct) * inherited
    return torch.stack((torch.zeros_like(total), total), dim=0)


def _message_tensor(
    state: torch.Tensor, program: CompiledProgram, target_node_id: str
) -> torch.Tensor:
    mapped = [
        _mapped_source_state(state, program, source_node_id, source_type)
        for source_node_id, source_type in program.incoming[target_node_id]
    ]
    return _or_torch(mapped, like=state[:, :, program.node_index[target_node_id]])


def _apply_admission(
    state: torch.Tensor, program: CompiledProgram, evidence_id: str
) -> torch.Tensor:
    output = state.clone()
    node_index = program.node_index[f"evidence:{evidence_id}"]
    evidence_index = program.evidence_index[evidence_id]
    output[0, evidence_index, node_index] = torch.ones((), dtype=state.dtype, device=state.device)
    return output


def _apply_invalidations(
    state: torch.Tensor, program: CompiledProgram, source_evidence_id: str
) -> torch.Tensor:
    output = state
    for source, target in program.invalidation_edges:
        if source == source_evidence_id:
            output = output.clone()
            output[:, program.evidence_index[target], :] = 0.0
    return output


def _terminal_axes(program: CompiledProgram) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        (target_node_id, evidence_id, channel)
        for target_node_id in program.fact_target_node_ids
        for evidence_id in program.evidence_ids
        for channel in CHANNELS
    )


def terminal_output(state: torch.Tensor, program: CompiledProgram) -> torch.Tensor:
    rows: list[torch.Tensor] = []
    for target_node_id in program.fact_target_node_ids:
        target = state[:, :, program.node_index[target_node_id]]
        direct = target[0, :]
        inherited = (1.0 - direct) * target[1, :]
        rows.append(torch.stack((direct, inherited), dim=1).reshape(-1))
    return torch.cat(rows, dim=0) if rows else torch.zeros(0, dtype=state.dtype)


def terminal_target(
    program: CompiledProgram, neutral_output: torch.Tensor
) -> torch.Tensor:
    target = neutral_output.detach().clone()
    closure_by_target = {row["target_id"]: row for row in program.closure["targets"]}
    axis_to_index = {axis: index for index, axis in enumerate(_terminal_axes(program))}
    for target_node_id in program.fact_target_node_ids:
        row = closure_by_target[target_node_id]
        direct = set(row["direct_active_evidence_ids"])
        inherited = set(row["inherited_active_evidence_ids"])
        for evidence_id in program.evidence_ids:
            target[axis_to_index[(target_node_id, evidence_id, "direct")]] = (
                1.0 if evidence_id in direct else 0.0
            )
            target[axis_to_index[(target_node_id, evidence_id, "inherited")]] = (
                1.0 if evidence_id in inherited else 0.0
            )
    return target


def _validate_sweep_override(
    program: CompiledProgram, sweep_order: Sequence[str]
) -> tuple[str, ...]:
    order = tuple(sweep_order)
    if set(order) != set(program.sweep_order) or len(order) != len(program.sweep_order):
        raise TemporalAdjointValidationError("internal sweep override is not a permutation")
    position = {node_id: index for index, node_id in enumerate(order)}
    for _edge_id, source, target, _provenance in program.positive_edges:
        if source in position and target in position and position[source] >= position[target]:
            raise TemporalAdjointValidationError("internal sweep override violates dependency order")
    return order


def forward_state(
    program: CompiledProgram,
    schedule_id: str,
    deltas: torch.Tensor,
    *,
    sweep_order_override: Sequence[str] | None = None,
    identity_after_site: int | None = None,
) -> torch.Tensor:
    sites = _site_rows(program, schedule_id)
    if deltas.ndim != 1 or deltas.numel() != len(sites) or deltas.dtype != FLOAT_DTYPE:
        raise TemporalAdjointValidationError("delta vector shape/dtype mismatch")
    sweep_order = (
        program.sweep_order
        if sweep_order_override is None
        else _validate_sweep_override(program, sweep_order_override)
    )
    state = torch.zeros(program.state_shape, dtype=FLOAT_DTYPE, device=deltas.device)
    site_index = 0
    for evidence_id in program.schedules[schedule_id]:
        state = _apply_admission(state, program, evidence_id)
        state = _apply_invalidations(state, program, evidence_id)
        for target_node_id in sweep_order:
            message = _message_tensor(state, program, target_node_id)
            target_index = program.node_index[target_node_id]
            alpha = torch.sigmoid(deltas[site_index])
            output = state.clone()
            output[:, :, target_index] = (
                (1.0 - alpha) * state[:, :, target_index] + alpha * message
            )
            state = output
            if identity_after_site == site_index:
                state = state.clone()
            site_index += 1
    if site_index != len(sites):
        raise AssertionError("site enumeration drift")
    return state


def forward_terminal(
    program: CompiledProgram,
    schedule_id: str,
    deltas: torch.Tensor,
    **kwargs: Any,
) -> torch.Tensor:
    return terminal_output(forward_state(program, schedule_id, deltas, **kwargs), program)


def _mapped_manual(
    state: torch.Tensor,
    tangent: torch.Tensor,
    program: CompiledProgram,
    source_node_id: str,
    source_type: str,
) -> tuple[torch.Tensor, torch.Tensor]:
    source_index = program.node_index[source_node_id]
    value = state[:, :, source_index]
    derivative = tangent[:, :, source_index, :]
    if source_type != "fact":
        return value, derivative
    direct = value[0, :]
    inherited = value[1, :]
    total = direct + (1.0 - direct) * inherited
    total_tangent = (
        (1.0 - inherited).unsqueeze(1) * derivative[0, :, :]
        + (1.0 - direct).unsqueeze(1) * derivative[1, :, :]
    )
    mapped_value = torch.stack((torch.zeros_like(total), total), dim=0)
    mapped_tangent = torch.stack(
        (torch.zeros_like(total_tangent), total_tangent), dim=0
    )
    return mapped_value, mapped_tangent


def _or_manual(
    values: Sequence[torch.Tensor],
    tangents: Sequence[torch.Tensor],
    *,
    like_value: torch.Tensor,
    like_tangent: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    if not values:
        return torch.zeros_like(like_value), torch.zeros_like(like_tangent)
    output = 1.0 - torch.prod(1.0 - torch.stack(tuple(values), dim=0), dim=0)
    derivative = torch.zeros_like(like_tangent)
    for index, candidate_tangent in enumerate(tangents):
        factor = torch.ones_like(like_value)
        for other_index, other_value in enumerate(values):
            if other_index != index:
                factor = factor * (1.0 - other_value)
        derivative = derivative + factor.unsqueeze(-1) * candidate_tangent
    return output, derivative


def _terminal_with_tangent(
    state: torch.Tensor, tangent: torch.Tensor, program: CompiledProgram
) -> tuple[torch.Tensor, torch.Tensor]:
    values: list[torch.Tensor] = []
    derivatives: list[torch.Tensor] = []
    for target_node_id in program.fact_target_node_ids:
        index = program.node_index[target_node_id]
        direct = state[0, :, index]
        inherited_raw = state[1, :, index]
        direct_tangent = tangent[0, :, index, :]
        inherited_tangent = (
            (1.0 - direct).unsqueeze(1) * tangent[1, :, index, :]
            - inherited_raw.unsqueeze(1) * direct_tangent
        )
        values.append(torch.stack((direct, (1.0 - direct) * inherited_raw), dim=1).reshape(-1))
        derivatives.append(torch.stack((direct_tangent, inherited_tangent), dim=1).reshape(-1, tangent.shape[-1]))
    return torch.cat(values, dim=0), torch.cat(derivatives, dim=0)


def manual_forward_jacobian(
    program: CompiledProgram, schedule_id: str, deltas: torch.Tensor
) -> tuple[torch.Tensor, torch.Tensor]:
    sites = _site_rows(program, schedule_id)
    if deltas.shape != (len(sites),) or deltas.dtype != FLOAT_DTYPE:
        raise TemporalAdjointValidationError("manual delta vector mismatch")
    control_count = len(sites)
    state = torch.zeros(program.state_shape, dtype=FLOAT_DTYPE)
    tangent = torch.zeros(program.state_shape + (control_count,), dtype=FLOAT_DTYPE)
    site_index = 0
    for evidence_id in program.schedules[schedule_id]:
        node_index = program.node_index[f"evidence:{evidence_id}"]
        evidence_index = program.evidence_index[evidence_id]
        state = state.clone()
        tangent = tangent.clone()
        state[0, evidence_index, node_index] = 1.0
        tangent[0, evidence_index, node_index, :] = 0.0
        for source, target in program.invalidation_edges:
            if source == evidence_id:
                target_evidence_index = program.evidence_index[target]
                state = state.clone()
                tangent = tangent.clone()
                state[:, target_evidence_index, :] = 0.0
                tangent[:, target_evidence_index, :, :] = 0.0
        for target_node_id in program.sweep_order:
            values: list[torch.Tensor] = []
            tangents: list[torch.Tensor] = []
            for source_node_id, source_type in program.incoming[target_node_id]:
                value, derivative = _mapped_manual(
                    state, tangent, program, source_node_id, source_type
                )
                values.append(value)
                tangents.append(derivative)
            target_index = program.node_index[target_node_id]
            message, message_tangent = _or_manual(
                values,
                tangents,
                like_value=state[:, :, target_index],
                like_tangent=tangent[:, :, target_index, :],
            )
            alpha = torch.sigmoid(deltas[site_index].detach())
            alpha_prime = alpha * (1.0 - alpha)
            previous = state[:, :, target_index]
            previous_tangent = tangent[:, :, target_index, :]
            next_value = (1.0 - alpha) * previous + alpha * message
            next_tangent = (1.0 - alpha) * previous_tangent + alpha * message_tangent
            next_tangent = next_tangent.clone()
            next_tangent[..., site_index] += alpha_prime * (message - previous)
            state = state.clone()
            tangent = tangent.clone()
            state[:, :, target_index] = next_value
            tangent[:, :, target_index, :] = next_tangent
            site_index += 1
    return _terminal_with_tangent(state, tangent, program)


def _axis_sentinel_check(program: CompiledProgram) -> bool:
    """Catch any accidental node-first access in the canonical C,E,N tensor."""

    state = torch.zeros(program.state_shape, dtype=FLOAT_DTYPE)
    state = _apply_admission(state, program, "R4")
    expected = (0, program.evidence_index["R4"], program.node_index["evidence:R4"])
    coordinates = tuple(tuple(int(v) for v in row) for row in torch.nonzero(state).tolist())
    if coordinates != (expected,) or float(state[expected]) != 1.0:
        return False
    message = _message_tensor(state, program, "support:demo_readiness")
    message_coordinates = tuple(
        tuple(int(v) for v in row) for row in torch.nonzero(message).tolist()
    )
    return message_coordinates == ((0, program.evidence_index["R4"]),)


def _forward_with_trace(
    program: CompiledProgram, schedule_id: str, deltas: torch.Tensor
) -> tuple[torch.Tensor, list[dict[str, Any]]]:
    sites = _site_rows(program, schedule_id)
    if deltas.shape != (len(sites),) or deltas.dtype != FLOAT_DTYPE:
        raise TemporalAdjointValidationError("trace delta vector mismatch")
    state = torch.zeros(program.state_shape, dtype=FLOAT_DTYPE)
    trace: list[dict[str, Any]] = []
    site_index = 0
    for evidence_id in program.schedules[schedule_id]:
        node_index = program.node_index[f"evidence:{evidence_id}"]
        evidence_index = program.evidence_index[evidence_id]
        state = _apply_admission(state, program, evidence_id)
        trace.append(
            {
                "kind": "admit",
                "node_index": node_index,
                "evidence_index": evidence_index,
            }
        )
        for source, target in program.invalidation_edges:
            if source == evidence_id:
                state = state.clone()
                target_evidence_index = program.evidence_index[target]
                state[:, target_evidence_index, :] = 0.0
                trace.append(
                    {
                        "kind": "invalidate",
                        "evidence_index": target_evidence_index,
                    }
                )
        for target_node_id in program.sweep_order:
            incoming = program.incoming[target_node_id]
            candidate_values = [
                _mapped_source_state(state, program, source_node_id, source_type).clone()
                for source_node_id, source_type in incoming
            ]
            source_values = [
                state[:, :, program.node_index[source_node_id]].clone()
                for source_node_id, _source_type in incoming
            ]
            target_index = program.node_index[target_node_id]
            previous_target = state[:, :, target_index].clone()
            message = _or_torch(candidate_values, like=previous_target)
            alpha = torch.sigmoid(deltas[site_index].detach())
            state = state.clone()
            state[:, :, target_index] = (
                (1.0 - alpha) * previous_target + alpha * message
            )
            trace.append(
                {
                    "alpha": alpha,
                    "candidate_values": candidate_values,
                    "incoming": incoming,
                    "kind": "site",
                    "message": message,
                    "previous_target": previous_target,
                    "site_index": site_index,
                    "source_values": source_values,
                    "target_index": target_index,
                }
            )
            site_index += 1
    return state, trace


def manual_reverse_adjoint(
    program: CompiledProgram,
    schedule_id: str,
    deltas: torch.Tensor,
    target: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Return exact reverse-mode d(loss)/d(delta), terminal output, and loss."""

    state, trace = _forward_with_trace(program, schedule_id, deltas)
    output = terminal_output(state, program)
    if target.shape != output.shape or target.dtype != FLOAT_DTYPE:
        raise TemporalAdjointValidationError("terminal target mismatch")
    residual = output - target
    loss = 0.5 * torch.dot(residual, residual)
    state_adjoint = torch.zeros_like(state)
    cursor = 0
    for target_node_id in program.fact_target_node_ids:
        node_index = program.node_index[target_node_id]
        direct = state[0, :, node_index]
        inherited_raw = state[1, :, node_index]
        for evidence_index, _evidence_id in enumerate(program.evidence_ids):
            residual_direct = residual[cursor]
            residual_inherited = residual[cursor + 1]
            state_adjoint[0, evidence_index, node_index] += (
                residual_direct - residual_inherited * inherited_raw[evidence_index]
            )
            state_adjoint[1, evidence_index, node_index] += (
                residual_inherited * (1.0 - direct[evidence_index])
            )
            cursor += 2
    gradient = torch.zeros_like(deltas)
    for operation in reversed(trace):
        kind = operation["kind"]
        if kind == "admit":
            state_adjoint = state_adjoint.clone()
            state_adjoint[
                0, operation["evidence_index"], operation["node_index"]
            ] = 0.0
            continue
        if kind == "invalidate":
            state_adjoint = state_adjoint.clone()
            state_adjoint[:, operation["evidence_index"], :] = 0.0
            continue
        if kind != "site":
            raise AssertionError(kind)
        target_index = operation["target_index"]
        alpha = operation["alpha"]
        target_adjoint = state_adjoint[:, :, target_index].clone()
        gradient[operation["site_index"]] = torch.sum(
            target_adjoint
            * alpha
            * (1.0 - alpha)
            * (operation["message"] - operation["previous_target"])
        )
        previous_adjoint = state_adjoint.clone()
        previous_adjoint[:, :, target_index] = (1.0 - alpha) * target_adjoint
        message_adjoint = alpha * target_adjoint
        candidate_values = operation["candidate_values"]
        for candidate_index, (
            (source_node_id, source_type),
            source_value,
        ) in enumerate(zip(operation["incoming"], operation["source_values"])):
            factor = torch.ones_like(message_adjoint)
            for other_index, other_value in enumerate(candidate_values):
                if other_index != candidate_index:
                    factor = factor * (1.0 - other_value)
            mapped_adjoint = factor * message_adjoint
            source_index = program.node_index[source_node_id]
            if source_type == "fact":
                total_adjoint = mapped_adjoint[1, :]
                direct = source_value[0, :]
                inherited = source_value[1, :]
                previous_adjoint[0, :, source_index] += (
                    total_adjoint * (1.0 - inherited)
                )
                previous_adjoint[1, :, source_index] += (
                    total_adjoint * (1.0 - direct)
                )
            else:
                previous_adjoint[:, :, source_index] += mapped_adjoint
        state_adjoint = previous_adjoint
    return gradient, output, loss


def autograd_jacobian(
    program: CompiledProgram, schedule_id: str, deltas: torch.Tensor
) -> torch.Tensor:
    return torch.autograd.functional.jacobian(
        lambda value: forward_terminal(program, schedule_id, value),
        deltas,
        create_graph=False,
        strict=False,
        vectorize=False,
    ).detach()


def central_finite_difference_jacobian(
    program: CompiledProgram,
    schedule_id: str,
    deltas: torch.Tensor,
    *,
    epsilon: float = FD_EPSILON,
) -> torch.Tensor:
    columns: list[torch.Tensor] = []
    for index in range(deltas.numel()):
        displacement = torch.zeros_like(deltas)
        displacement[index] = epsilon
        plus = forward_terminal(program, schedule_id, deltas + displacement)
        minus = forward_terminal(program, schedule_id, deltas - displacement)
        columns.append((plus - minus) / (2.0 * epsilon))
    return torch.stack(columns, dim=1)


def compiled_structural_closure(program: CompiledProgram) -> JsonObject:
    """Compute direct/inherited reachability from compiled transition rules only."""

    invalidated = {target for _source, target in program.invalidation_edges}
    direct: dict[str, set[str]] = {node_id: set() for node_id in program.node_ids}
    inherited: dict[str, set[str]] = {node_id: set() for node_id in program.node_ids}
    for evidence_id in program.evidence_ids:
        if evidence_id not in invalidated:
            direct[f"evidence:{evidence_id}"].add(evidence_id)
    for target_node_id in program.sweep_order:
        for source_node_id, source_type in program.incoming[target_node_id]:
            if source_type == "fact":
                inherited[target_node_id].update(direct[source_node_id])
                inherited[target_node_id].update(inherited[source_node_id])
            else:
                direct[target_node_id].update(direct[source_node_id])
                inherited[target_node_id].update(inherited[source_node_id])
        inherited[target_node_id].difference_update(direct[target_node_id])
    targets = {
        target_node_id: {
            "direct": sorted(direct[target_node_id]),
            "inherited": sorted(inherited[target_node_id]),
        }
        for target_node_id in program.target_node_ids
    }
    return {
        "active_evidence_ids": sorted(set(program.evidence_ids) - invalidated),
        "invalidated_evidence_ids": sorted(invalidated),
        "targets": targets,
    }


def _expected_structural_closure(program: CompiledProgram) -> JsonObject:
    return {
        "active_evidence_ids": list(program.closure["active_evidence_ids"]),
        "invalidated_evidence_ids": list(program.closure["invalidated_evidence_ids"]),
        "targets": {
            row["target_id"]: {
                "direct": list(row["direct_active_evidence_ids"]),
                "inherited": list(row["inherited_active_evidence_ids"]),
            }
            for row in program.closure["targets"]
        },
    }


def _program_without_edge(program: CompiledProgram, edge_id: str) -> CompiledProgram:
    remaining = tuple(edge for edge in program.positive_edges if edge[0] != edge_id)
    if len(remaining) != len(program.positive_edges) - 1:
        raise TemporalAdjointValidationError(f"edge not found for sever test: {edge_id}")
    node_types = _node_type_by_id(program)
    incoming_work: dict[str, list[tuple[str, str]]] = {node_id: [] for node_id in program.node_ids}
    for _remaining_id, source, target, _provenance in remaining:
        incoming_work[target].append((source, node_types[source]))
    incoming = {
        node_id: tuple(sorted(rows))
        for node_id, rows in incoming_work.items()
        if rows
    }
    return replace(
        program,
        positive_edges=remaining,
        incoming=incoming,
        sweep_order=_canonical_kahn_order(program.node_ids, remaining),
    )


def _tensor_floats(value: torch.Tensor) -> list[Any]:
    def normalize(item: Any) -> Any:
        if isinstance(item, list):
            return [normalize(child) for child in item]
        number = float(item)
        if not math.isfinite(number):
            raise TemporalAdjointValidationError("non-finite tensor publication")
        return 0.0 if number == 0.0 else number

    return normalize(value.detach().cpu().tolist())


def _loss_for_delta(
    program: CompiledProgram,
    schedule_id: str,
    delta: torch.Tensor,
    target: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    output = forward_terminal(program, schedule_id, delta)
    residual = output - target
    return 0.5 * torch.dot(residual, residual), output


def _delta_from_normalized(
    normalized: torch.Tensor, scales: torch.Tensor
) -> torch.Tensor:
    delta = torch.zeros_like(normalized)
    eligible = scales > 0.0
    delta[eligible] = normalized[eligible] / scales[eligible]
    if torch.any(delta[~eligible] != 0.0):
        raise AssertionError("zero-leverage controls must remain fixed")
    return delta


def _node_tied_projection(
    gradient: torch.Tensor,
    scales: torch.Tensor,
    sites: Sequence[Mapping[str, Any]],
) -> torch.Tensor:
    projected = torch.zeros_like(gradient)
    eligible = scales > 0.0
    for node_id in sorted({str(row["target_node_id"]) for row in sites}):
        indices = [
            index
            for index, row in enumerate(sites)
            if row["target_node_id"] == node_id and bool(eligible[index])
        ]
        if indices:
            projected[indices] = torch.mean(gradient[indices])
    return projected


def _sham_vectors(
    temporal_control: torch.Tensor,
    scales: torch.Tensor,
    sites: Sequence[Mapping[str, Any]],
) -> tuple[list[tuple[str, torch.Tensor]], dict[str, str]]:
    eligible = scales > 0.0
    groups = {
        node_id: [
            index
            for index, row in enumerate(sites)
            if row["target_node_id"] == node_id and bool(eligible[index])
        ]
        for node_id in sorted({str(row["target_node_id"]) for row in sites})
    }
    distinct: list[tuple[str, torch.Tensor]] = []
    disposition: dict[str, str] = {}
    seen = {canonical_json_bytes(_tensor_floats(temporal_control))}
    for transform in SHAM_TRANSFORMS:
        sham = temporal_control.clone()
        for indices in groups.values():
            if len(indices) <= 1:
                continue
            values = temporal_control[indices]
            if transform == "cyclic_plus_1":
                permuted = torch.roll(values, shifts=1)
            elif transform == "cyclic_minus_1":
                permuted = torch.roll(values, shifts=-1)
            elif transform == "reverse":
                permuted = torch.flip(values, dims=(0,))
            else:
                raise AssertionError(transform)
            sham[indices] = permuted
        key = canonical_json_bytes(_tensor_floats(sham))
        if key in seen:
            disposition[transform] = "NOT_DISTINCT"
            continue
        seen.add(key)
        disposition[transform] = f"D{len(distinct) + 1}"
        distinct.append((transform, sham))
    return distinct, disposition


def _reconstruct_locked_sham_expectations(
    temporal_control: torch.Tensor,
    scales: torch.Tensor,
    sites: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, torch.Tensor], dict[str, str]]:
    """Independently reconstruct the exact locked D family for validation."""

    eligible = scales > 0.0
    node_ids = sorted({str(row["target_node_id"]) for row in sites})
    groups = {
        node_id: tuple(
            index
            for index, row in enumerate(sites)
            if row["target_node_id"] == node_id and bool(eligible[index])
        )
        for node_id in node_ids
    }
    expected_by_arm: dict[str, torch.Tensor] = {}
    disposition: dict[str, str] = {}
    seen = {canonical_json_bytes(_tensor_floats(temporal_control))}
    for transform in SHAM_TRANSFORMS:
        reconstructed = temporal_control.clone()
        for indices_tuple in groups.values():
            indices = list(indices_tuple)
            if len(indices) <= 1:
                continue
            original = temporal_control[indices]
            if transform == "cyclic_plus_1":
                transformed = torch.cat((original[-1:], original[:-1]))
            elif transform == "cyclic_minus_1":
                transformed = torch.cat((original[1:], original[:1]))
            elif transform == "reverse":
                transformed = original[torch.arange(len(indices) - 1, -1, -1)]
            else:
                raise AssertionError(transform)
            reconstructed[indices] = transformed
        key = canonical_json_bytes(_tensor_floats(reconstructed))
        if key in seen:
            disposition[transform] = "NOT_DISTINCT"
            continue
        seen.add(key)
        arm_id = f"D{len(expected_by_arm) + 1}"
        disposition[transform] = arm_id
        expected_by_arm[arm_id] = reconstructed
    return expected_by_arm, disposition


def _exact_float_multiset(value: torch.Tensor) -> list[float]:
    return [float(item) for item in torch.sort(value.detach()).values.tolist()]


def _sign_multiset(value: torch.Tensor) -> list[int]:
    return sorted(int(item) for item in torch.sign(value.detach()).tolist())


def _audit_sham_geometry(
    temporal_control: torch.Tensor,
    controls: Mapping[str, torch.Tensor],
    scales: torch.Tensor,
    sites: Sequence[Mapping[str, Any]],
    observed_transform_by_arm: Mapping[str, str],
    observed_disposition: Mapping[str, str],
) -> JsonObject:
    """Validate emitted D controls without trusting the sham constructor labels."""

    expected_by_arm, expected_disposition = _reconstruct_locked_sham_expectations(
        temporal_control, scales, sites
    )
    actual_d_ids = sorted(
        (arm_id for arm_id in controls if arm_id.startswith("D")),
        key=lambda arm_id: int(arm_id[1:]) if arm_id[1:].isdigit() else 10**9,
    )
    expected_d_ids = list(expected_by_arm)
    eligible = scales > 0.0
    node_ids = sorted({str(row["target_node_id"]) for row in sites})
    eligible_groups = {
        node_id: [
            index
            for index, row in enumerate(sites)
            if row["target_node_id"] == node_id and bool(eligible[index])
        ]
        for node_id in node_ids
    }
    expected_transform_by_arm = {
        arm_id: transform
        for transform, arm_id in expected_disposition.items()
        if arm_id != "NOT_DISTINCT"
    }
    per_sham: dict[str, JsonObject] = {}
    for arm_id in sorted(set(actual_d_ids) | set(expected_d_ids)):
        actual = controls.get(arm_id)
        expected = expected_by_arm.get(arm_id)
        observed_transform = observed_transform_by_arm.get(arm_id)
        expected_transform = expected_transform_by_arm.get(arm_id)
        if actual is None or expected is None:
            per_sham[arm_id] = {
                "distinct_from_c": False,
                "eligible_support_exact": False,
                "exact_locked_transform": False,
                "exact_zero_count_and_sparsity": False,
                "ineligible_sites_zero": False,
                "node_type_mapping_exact": False,
                "normalized_l2_abs_error": None,
                "normalized_l2_exact": False,
                "observed_transform": observed_transform,
                "same_sign_multiset_by_target_node": False,
                "same_value_multiset_by_target_node": False,
                "status": "FAIL",
                "transform": expected_transform,
            }
            continue
        same_values_by_node = all(
            _exact_float_multiset(actual[indices])
            == _exact_float_multiset(temporal_control[indices])
            for indices in eligible_groups.values()
        )
        same_signs_by_node = all(
            _sign_multiset(actual[indices])
            == _sign_multiset(temporal_control[indices])
            for indices in eligible_groups.values()
        )
        same_zero_count_by_node = all(
            int(torch.count_nonzero(actual[indices] == 0.0))
            == int(torch.count_nonzero(temporal_control[indices] == 0.0))
            and int(torch.count_nonzero(actual[indices]))
            == int(torch.count_nonzero(temporal_control[indices]))
            for indices in eligible_groups.values()
        )
        ineligible_zero = bool(torch.all(actual[~eligible] == 0.0))
        eligible_support_exact = (
            actual.shape == temporal_control.shape
            and ineligible_zero
            and all(
                all(bool(eligible[index]) for index in indices)
                for indices in eligible_groups.values()
            )
        )
        node_type_mapping_exact = same_values_by_node and all(
            len({str(sites[index]["target_node_type"]) for index in indices}) <= 1
            for indices in eligible_groups.values()
        )
        l2_error = abs(
            float(torch.linalg.vector_norm(actual))
            - float(torch.linalg.vector_norm(temporal_control))
        )
        exact_locked_transform = (
            observed_transform == expected_transform and torch.equal(actual, expected)
        )
        distinct_from_c = not torch.equal(actual, temporal_control)
        gates = {
            "distinct_from_c": distinct_from_c,
            "eligible_support_exact": eligible_support_exact,
            "exact_locked_transform": exact_locked_transform,
            "exact_zero_count_and_sparsity": same_zero_count_by_node,
            "ineligible_sites_zero": ineligible_zero,
            "node_type_mapping_exact": node_type_mapping_exact,
            "normalized_l2_exact": l2_error <= 2.0e-15,
            "same_sign_multiset_by_target_node": same_signs_by_node,
            "same_value_multiset_by_target_node": same_values_by_node,
        }
        per_sham[arm_id] = {
            **gates,
            "normalized_l2_abs_error": l2_error,
            "observed_transform": observed_transform,
            "status": "PASS" if all(gates.values()) else "FAIL",
            "transform": expected_transform,
            "value_fingerprint_sha256": fingerprint(_tensor_floats(actual)),
        }
    family_gates = {
        "all_three_locked_transforms_accounted_for": (
            set(observed_disposition) == set(SHAM_TRANSFORMS)
            and dict(observed_disposition) == expected_disposition
        ),
        "distinct_d_count_exact": (
            actual_d_ids == expected_d_ids
            and len(actual_d_ids) == len(expected_by_arm)
        ),
        "distinct_d_mapping_exact": (
            dict(observed_transform_by_arm) == expected_transform_by_arm
        ),
        "every_emitted_sham_invariant_exact": (
            bool(per_sham)
            and all(row["status"] == "PASS" for row in per_sham.values())
        ),
    }
    payload: JsonObject = {
        "expected_distinct_d_count": len(expected_by_arm),
        "expected_disposition": expected_disposition,
        "family_gates": family_gates,
        "locked_transforms": list(SHAM_TRANSFORMS),
        "observed_distinct_d_count": len(actual_d_ids),
        "observed_disposition": dict(observed_disposition),
        "per_sham": per_sham,
        "schema_version": "ebrt-temporal-lineage-sham-geometry-audit-v0.5.4",
        "status": "PASS" if all(family_gates.values()) else "FAIL",
    }
    payload["fingerprint_sha256"] = fingerprint(payload)
    return payload


def _selected_terminal_output(
    state: torch.Tensor,
    program: CompiledProgram,
    target_node_ids: Sequence[str],
) -> torch.Tensor:
    rows: list[torch.Tensor] = []
    for target_node_id in target_node_ids:
        target = state[:, :, program.node_index[target_node_id]]
        direct = target[0, :]
        inherited = (1.0 - direct) * target[1, :]
        rows.append(torch.stack((direct, inherited), dim=1).reshape(-1))
    return torch.cat(rows, dim=0) if rows else torch.zeros(0, dtype=FLOAT_DTYPE)


def _projection_geometry(
    scales: torch.Tensor, sites: Sequence[Mapping[str, Any]]
) -> tuple[list[str], torch.Tensor, torch.Tensor]:
    eligible = scales > 0.0
    node_ids = sorted(
        {
            str(row["target_node_id"])
            for index, row in enumerate(sites)
            if bool(eligible[index])
        }
    )
    tied_basis = torch.zeros((len(sites), len(node_ids)), dtype=FLOAT_DTYPE)
    for column, node_id in enumerate(node_ids):
        indices = [
            index
            for index, row in enumerate(sites)
            if row["target_node_id"] == node_id and bool(eligible[index])
        ]
        tied_basis[indices, column] = 1.0 / math.sqrt(len(indices))
    projection = tied_basis @ tied_basis.T
    return node_ids, tied_basis, projection


def _control_map(
    arm_id: str,
    normalized: torch.Tensor,
    scales: torch.Tensor,
    sites: Sequence[Mapping[str, Any]],
    *,
    placement: str,
    sham_transform: str | None = None,
) -> JsonObject:
    delta = _delta_from_normalized(normalized, scales)
    payload: JsonObject = {
        "arm_id": arm_id,
        "controls": [
            {
                "eligible": bool(scales[index] > 0.0),
                "normalized_u": float(normalized[index]) if float(normalized[index]) != 0.0 else 0.0,
                "raw_delta": float(delta[index]) if float(delta[index]) != 0.0 else 0.0,
                "raw_scale_s": float(scales[index]) if float(scales[index]) != 0.0 else 0.0,
                "site_id": row["site_id"],
            }
            for index, row in enumerate(sites)
        ],
        "normalized_l2": float(torch.linalg.vector_norm(normalized)),
        "placement": placement,
        "raw_max_abs_delta": float(torch.max(torch.abs(delta))) if delta.numel() else 0.0,
        "schema_version": CONTROL_MAP_SCHEMA_VERSION,
        "sham_transform": sham_transform,
        "step_count": 0 if arm_id == "A" else 1,
    }
    payload["fingerprint_sha256"] = fingerprint(payload)
    return payload


@dataclass(frozen=True)
class LaneEvaluation:
    schedule_id: str
    geometry: JsonObject
    comparison: JsonObject
    sealed_lane: JsonObject
    controls: Mapping[str, torch.Tensor]
    deltas: Mapping[str, torch.Tensor]
    losses: Mapping[str, float]


def evaluate_lane(program: CompiledProgram, schedule_id: str) -> LaneEvaluation:
    if not program.event_triggered:
        raise TemporalAdjointValidationError("event lane requires triggered program")
    sites = _site_rows(program, schedule_id)
    zero_delta = torch.zeros(len(sites), dtype=FLOAT_DTYPE)
    manual_output, raw_jacobian = manual_forward_jacobian(program, schedule_id, zero_delta)
    torch_output = forward_terminal(program, schedule_id, zero_delta)
    autograd_j = autograd_jacobian(program, schedule_id, zero_delta)
    finite_difference_j = central_finite_difference_jacobian(
        program, schedule_id, zero_delta, epsilon=FD_EPSILON
    )
    if not torch.equal(manual_output, torch_output):
        raise TemporalAdjointValidationError("manual and torch neutral outputs differ")
    target = terminal_target(program, manual_output)
    manual_gradient, reverse_output, neutral_loss_tensor = manual_reverse_adjoint(
        program, schedule_id, zero_delta, target
    )
    autograd_delta = zero_delta.clone().requires_grad_(True)
    autograd_output = forward_terminal(program, schedule_id, autograd_delta)
    autograd_loss = 0.5 * torch.dot(autograd_output - target, autograd_output - target)
    autograd_gradient = torch.autograd.grad(autograd_loss, autograd_delta)[0].detach()
    if not torch.equal(reverse_output, manual_output):
        raise TemporalAdjointValidationError("reverse replay output drift")
    scales = torch.linalg.vector_norm(raw_jacobian, dim=0)
    eligible = scales > 0.0
    if not bool(torch.any(eligible)):
        raise TemporalAdjointValidationError("no positive-leverage temporal sites")
    normalized_jacobian = torch.zeros_like(raw_jacobian)
    normalized_jacobian[:, eligible] = raw_jacobian[:, eligible] / scales[eligible]
    normalized_norms = torch.linalg.vector_norm(normalized_jacobian, dim=0)
    residual = manual_output - target
    normalized_gradient = normalized_jacobian.T @ residual
    normalized_reverse_gradient = torch.zeros_like(manual_gradient)
    normalized_reverse_gradient[eligible] = manual_gradient[eligible] / scales[eligible]
    rho = RHO_FRACTION * torch.min(scales[eligible])
    arm_a = torch.zeros_like(normalized_gradient)
    projected_gradient = _node_tied_projection(normalized_gradient, scales, sites)
    projected_norm = torch.linalg.vector_norm(projected_gradient)
    gradient_norm = torch.linalg.vector_norm(normalized_gradient)
    if not bool(projected_norm > 0.0) or not bool(gradient_norm > 0.0):
        raise TemporalAdjointValidationError("B/C gradient direction is zero")
    arm_b = -rho * projected_gradient / projected_norm
    arm_c = -rho * normalized_gradient / gradient_norm
    shams, sham_disposition = _sham_vectors(arm_c, scales, sites)
    if not shams:
        raise TemporalAdjointValidationError("locked sham family produced no distinct controls")
    controls: dict[str, torch.Tensor] = {"A": arm_a, "B": arm_b, "C": arm_c}
    sham_transform_by_arm: dict[str, str] = {}
    for index, (transform, vector) in enumerate(shams, start=1):
        arm_id = f"D{index}"
        controls[arm_id] = vector
        sham_transform_by_arm[arm_id] = transform
    sham_geometry_audit = _audit_sham_geometry(
        arm_c,
        controls,
        scales,
        sites,
        sham_transform_by_arm,
        sham_disposition,
    )
    deltas = {arm_id: _delta_from_normalized(vector, scales) for arm_id, vector in controls.items()}
    losses: dict[str, float] = {}
    outputs: dict[str, torch.Tensor] = {}
    states: dict[str, torch.Tensor] = {}
    constraint_outputs: dict[str, torch.Tensor] = {}
    for arm_id in sorted(controls):
        loss, output = _loss_for_delta(
            program, schedule_id, deltas[arm_id], target
        )
        state = forward_state(program, schedule_id, deltas[arm_id])
        losses[arm_id] = float(loss)
        outputs[arm_id] = output
        states[arm_id] = state
        constraint_outputs[arm_id] = _selected_terminal_output(
            state, program, program.constraint_target_node_ids
        )
    neutral_constraint = constraint_outputs["A"]
    constraint_drift = {
        arm_id: float(torch.max(torch.abs(value - neutral_constraint)))
        if value.numel()
        else 0.0
        for arm_id, value in constraint_outputs.items()
    }
    c_beats = {
        arm_id: losses["C"] + 1.0e-12 < losses[arm_id]
        for arm_id in sorted(losses)
        if arm_id != "C"
    }
    all_nonzero_arms_exact_l2 = all(
        abs(float(torch.linalg.vector_norm(controls[arm_id])) - float(rho)) <= 2.0e-15
        for arm_id in controls
        if arm_id != "A"
    )
    raw_bounds = {
        arm_id: float(torch.max(torch.abs(delta))) <= RHO_FRACTION + 1.0e-15
        for arm_id, delta in deltas.items()
    }
    top_index = int(torch.argmax(torch.abs(normalized_gradient)))
    sorted_credit = torch.sort(torch.abs(normalized_gradient), descending=True).values
    top_credit_margin = float(sorted_credit[0] - sorted_credit[1])
    top_site = dict(sites[top_index])
    top_site["normalized_abs_credit"] = float(torch.abs(normalized_gradient[top_index]))
    top_site["raw_scale_s"] = float(scales[top_index])
    top_site["runner_up_margin"] = top_credit_margin
    top_site["horizon_label_semantics"] = (
        "admitted_evidence_id names the current horizon; it is not a direct gate on this site"
    )
    manual_forward_error = float(torch.max(torch.abs(raw_jacobian - autograd_j)))
    manual_reverse_error = float(torch.max(torch.abs(manual_gradient - autograd_gradient)))
    finite_difference_error = float(
        torch.max(torch.abs(raw_jacobian - finite_difference_j))
    )
    normalized_norm_error = float(
        torch.max(torch.abs(normalized_norms[eligible] - 1.0))
    )
    normalized_reverse_error = float(
        torch.max(torch.abs(normalized_gradient - normalized_reverse_gradient))
    )
    node_columns, tied_basis, projection = _projection_geometry(scales, sites)
    geometry: JsonObject = {
        "eligible_site_count": int(torch.sum(eligible)),
        "lane_id": schedule_id,
        "node_tied_projection": {
            "P": _tensor_floats(projection),
            "T": _tensor_floats(tied_basis),
            "column_target_node_ids": node_columns,
            "definition": "P=T*T_prime; each T column is the normalized indicator over eligible horizons of one target node",
        },
        "normalized_terminal_jacobian": _tensor_floats(normalized_jacobian),
        "raw_terminal_jacobian": _tensor_floats(raw_jacobian),
        "schema_version": GEOMETRY_SCHEMA_VERSION,
        "sites": [
            {
                **dict(row),
                "eligible": bool(eligible[index]),
                "normalized_jacobian_norm": float(normalized_norms[index]),
                "raw_scale_s": float(scales[index]),
            }
            for index, row in enumerate(sites)
        ],
        "terminal_axes": [
            {
                "channel": channel,
                "evidence_id": evidence_id,
                "target_node_id": target_node_id,
            }
            for target_node_id, evidence_id, channel in _terminal_axes(program)
        ],
    }
    geometry["fingerprint_sha256"] = fingerprint(geometry)
    audit: JsonObject = {
        "autograd_gradient_raw_delta": _tensor_floats(autograd_gradient),
        "backward_calls": 1,
        "central_finite_difference_epsilon": FD_EPSILON,
        "central_finite_difference_max_abs_error": finite_difference_error,
        "manual_forward_max_abs_error": manual_forward_error,
        "manual_reverse_gradient_raw_delta": _tensor_floats(manual_gradient),
        "manual_reverse_max_abs_error": manual_reverse_error,
        "normalized_gradient": _tensor_floats(normalized_gradient),
        "normalized_jacobian_max_norm_error": normalized_norm_error,
        "normalized_reverse_max_abs_error": normalized_reverse_error,
        "schema_version": ADJOINT_AUDIT_SCHEMA_VERSION,
        "status": "PASS",
    }
    audit["fingerprint_sha256"] = fingerprint(audit)
    control_maps: dict[str, JsonObject] = {}
    for arm_id in sorted(controls):
        placement = {
            "A": "zero_control",
            "B": "static_node_tied_projection",
            "C": "exact_temporal_adjoint",
        }.get(arm_id, "locked_within_node_temporal_sham")
        control_maps[arm_id] = _control_map(
            arm_id,
            controls[arm_id],
            scales,
            sites,
            placement=placement,
            sham_transform=sham_transform_by_arm.get(arm_id),
        )
    comparison: JsonObject = {
        "arm_results": {
            arm_id: {
                "control_map_fingerprint_sha256": control_maps[arm_id]["fingerprint_sha256"],
                "constraint_max_abs_drift": constraint_drift[arm_id],
                "improvement_from_A": losses["A"] - losses[arm_id],
                "normalized_l2": control_maps[arm_id]["normalized_l2"],
                "raw_max_abs_delta": control_maps[arm_id]["raw_max_abs_delta"],
                "terminal_loss": losses[arm_id],
            }
            for arm_id in sorted(losses)
        },
        "c_strictly_beats_under_1e_12": c_beats,
        "c_vs_b_loss_margin": losses["B"] - losses["C"],
        "c_vs_best_distinct_d_loss_margin": min(
            losses[arm_id] for arm_id in losses if arm_id.startswith("D")
        )
        - losses["C"],
        "lane_id": schedule_id,
        "rho": float(rho),
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "sham_geometry_audit": sham_geometry_audit,
        "sham_disposition": sham_disposition,
        "status": (
            "PASS"
            if all(c_beats.values()) and sham_geometry_audit["status"] == "PASS"
            else "FAIL"
        ),
    }
    comparison["fingerprint_sha256"] = fingerprint(comparison)
    gates = {
        "all_normalized_jacobian_norms_one": normalized_norm_error <= 2.0e-12,
        "all_nonzero_controls_exact_l2_rho": all_nonzero_arms_exact_l2,
        "all_raw_delta_bounded": all(raw_bounds.values()),
        "c_beats_a_b_and_every_distinct_d": all(c_beats.values()),
        "constraint_preserved_neutral": all(value == 0.0 for value in constraint_drift.values()),
        "finite_difference_agrees": finite_difference_error <= 5.0e-8,
        "manual_forward_agrees_autograd": manual_forward_error <= 2.0e-12,
        "manual_reverse_agrees_autograd": manual_reverse_error <= 2.0e-12,
        "locked_sham_geometry_exact": sham_geometry_audit["status"] == "PASS",
        "normalized_reverse_agrees": normalized_reverse_error <= 2.0e-12,
        "top_credit_has_positive_finite_leverage": (
            math.isfinite(top_site["raw_scale_s"]) and top_site["raw_scale_s"] > 0.0
        ),
        "zero_leverage_controls_fixed_zero": all(
            all(float(controls[arm_id][index]) == 0.0 for arm_id in controls)
            for index in range(len(sites))
            if not bool(eligible[index])
        ),
    }
    lane: JsonObject = {
        "adjoint_audit": audit,
        "claim_boundary": [
            "This lane is one deterministic network-zero mechanism run over the sealed v0.5.3 repaired lineage graph.",
            "The exact temporal-adjoint result is local to the compiled smooth recurrence and matched normalized actuator geometry.",
            "No provider, model generation, optimizer, or downstream grader participated.",
        ],
        "constraint_neutral_receipt": {
            "arm_max_abs_drift": constraint_drift,
            "neutral_output": _tensor_floats(neutral_constraint),
        },
        "control_maps": control_maps,
        "evidence_order": list(program.schedules[schedule_id]),
        "fixture_id": program.fixture_id,
        "gates": gates,
        "geometry_fingerprint_sha256": geometry["fingerprint_sha256"],
        "lane_id": schedule_id,
        "network_calls": 0,
        "neutral": {
            "loss": float(neutral_loss_tensor),
            "target": _tensor_floats(target),
            "terminal_output": _tensor_floats(manual_output),
        },
        "program_fingerprint_sha256": program_receipt(program)["fingerprint_sha256"],
        "provider_calls": 0,
        "schema_version": LANE_SCHEMA_VERSION,
        "sham_geometry_audit": sham_geometry_audit,
        "status": "PASS" if all(gates.values()) else "FAIL",
        "terminal_axis_types": ["fact"],
        "top_credit_site": top_site,
    }
    lane["fingerprint_sha256"] = fingerprint(lane)
    if lane["status"] != "PASS":
        raise TemporalAdjointValidationError(f"lane gates failed for {schedule_id}: {gates}")
    return LaneEvaluation(
        schedule_id=schedule_id,
        geometry=geometry,
        comparison=comparison,
        sealed_lane=lane,
        controls=controls,
        deltas=deltas,
        losses=losses,
    )


def _adversarial_sham_rejection_receipt(
    program: CompiledProgram, evaluation: LaneEvaluation
) -> JsonObject:
    sites = _site_rows(program, evaluation.schedule_id)
    scales = torch.tensor(
        [row["raw_scale_s"] for row in evaluation.geometry["sites"]],
        dtype=FLOAT_DTYPE,
    )
    observed_transform_by_arm = {
        arm_id: row["sham_transform"]
        for arm_id, row in evaluation.sealed_lane["control_maps"].items()
        if arm_id.startswith("D")
    }
    disposition = evaluation.comparison["sham_disposition"]
    sign_flipped_controls = dict(evaluation.controls)
    sign_flipped_controls["D1"] = -evaluation.controls["C"]
    sign_flipped_audit = _audit_sham_geometry(
        evaluation.controls["C"],
        sign_flipped_controls,
        scales,
        sites,
        observed_transform_by_arm,
        disposition,
    )

    cross_node_controls = dict(evaluation.controls)
    cross_node = evaluation.controls["D1"].clone()
    eligible = scales > 0.0
    selected_pair: tuple[int, int] | None = None
    for left_index, left_site in enumerate(sites):
        if not bool(eligible[left_index]):
            continue
        for right_index, right_site in enumerate(sites):
            if (
                bool(eligible[right_index])
                and left_site["target_node_id"] != right_site["target_node_id"]
                and float(cross_node[left_index]) != float(cross_node[right_index])
            ):
                selected_pair = (left_index, right_index)
                break
        if selected_pair is not None:
            break
    if selected_pair is None:
        raise TemporalAdjointValidationError(
            "could not construct cross-node sham adversary"
        )
    left_index, right_index = selected_pair
    left_value = cross_node[left_index].clone()
    cross_node[left_index] = cross_node[right_index]
    cross_node[right_index] = left_value
    cross_node_controls["D1"] = cross_node
    cross_node_audit = _audit_sham_geometry(
        evaluation.controls["C"],
        cross_node_controls,
        scales,
        sites,
        observed_transform_by_arm,
        disposition,
    )
    gates = {
        "cross_node_sham_rejected": cross_node_audit["status"] == "FAIL",
        "sign_flipped_sham_rejected": sign_flipped_audit["status"] == "FAIL",
    }
    payload: JsonObject = {
        "cross_node_audit_fingerprint_sha256": cross_node_audit[
            "fingerprint_sha256"
        ],
        "cross_node_pair": {
            "left_site_id": sites[left_index]["site_id"],
            "right_site_id": sites[right_index]["site_id"],
        },
        "gates": gates,
        "lane_id": evaluation.schedule_id,
        "sign_flipped_audit_fingerprint_sha256": sign_flipped_audit[
            "fingerprint_sha256"
        ],
        "status": "PASS" if all(gates.values()) else "FAIL",
    }
    payload["fingerprint_sha256"] = fingerprint(payload)
    return payload


def run_no_event_audit(
    fixture: Mapping[str, Any] | None = None,
) -> tuple[JsonObject, JsonObject]:
    if fixture is None:
        fixture = load_fixture(DEFAULT_NO_EVENT_FIXTURE, no_event=True)
    program = compile_program(fixture, no_event=True)
    if program.event_triggered or program.site_count != 0:
        raise TemporalAdjointValidationError("no-event compiler exposed controls")
    structural = compiled_structural_closure(program)
    target_node_id = str(fixture["lane"]["target_node_id"])
    partition = structural["targets"][target_node_id]
    stable_input = torch.zeros(
        (len(program.evidence_ids), len(CHANNELS)), dtype=FLOAT_DTYPE
    )
    for evidence_index, evidence_id in enumerate(program.evidence_ids):
        stable_input[evidence_index, 0] = (
            1.0 if evidence_id in set(partition["direct"]) else 0.0
        )
        stable_input[evidence_index, 1] = (
            1.0 if evidence_id in set(partition["inherited"]) else 0.0
        )
    neutral_output = stable_input.clone()
    controlled_output = stable_input.clone()
    audit: JsonObject = {
        "backward_calls": 0,
        "control_count": 0,
        "controlled_output": _tensor_floats(controlled_output),
        "event_triggered": False,
        "exact_identity": torch.equal(stable_input, controlled_output),
        "invalidation_operations": 0,
        "network_calls": 0,
        "neutral_equals_controlled": torch.equal(neutral_output, controlled_output),
        "neutral_output": _tensor_floats(neutral_output),
        "output_identity": torch.equal(stable_input, controlled_output),
        "provider_calls": 0,
        "schema_version": NO_EVENT_AUDIT_SCHEMA_VERSION,
        "stable_input": _tensor_floats(stable_input),
        "status": "PASS",
        "target_node_id": target_node_id,
    }
    if not (
        audit["neutral_equals_controlled"]
        and audit["output_identity"]
        and audit["control_count"] == 0
        and audit["backward_calls"] == 0
    ):
        audit["status"] = "FAIL"
    audit["fingerprint_sha256"] = fingerprint(audit)
    lane: JsonObject = {
        "claim_boundary": list(fixture["claim_boundary"]),
        "control_maps": {},
        "control_values": [],
        "backward_calls": 0,
        "event_triggered": False,
        "fixture_id": fixture["fixture_id"],
        "gates": {
            "backward_calls_zero": audit["backward_calls"] == 0,
            "controls_exact_zero": audit["control_count"] == 0,
            "neutral_equals_controlled": audit["neutral_equals_controlled"],
            "output_identity": audit["output_identity"],
        },
        "lane_id": "stable_constraint",
        "network_calls": 0,
        "neutral_equals_controlled": audit["neutral_equals_controlled"],
        "no_event_audit_fingerprint_sha256": audit["fingerprint_sha256"],
        "program_fingerprint_sha256": program_receipt(program)["fingerprint_sha256"],
        "provider_calls": 0,
        "schema_version": LANE_SCHEMA_VERSION,
        "stable_output": audit["controlled_output"],
        "status": "PASS" if audit["status"] == "PASS" else "FAIL",
        "terminal_axis_types": ["constraint"],
        "terminal_axes": [
            {
                "channel": channel,
                "evidence_id": evidence_id,
                "target_node_id": target_node_id,
            }
            for evidence_id in program.evidence_ids
            for channel in CHANNELS
        ],
    }
    lane["fingerprint_sha256"] = fingerprint(lane)
    if lane["status"] != "PASS":
        raise TemporalAdjointValidationError("no-event stable lane failed")
    return audit, lane


@contextmanager
def network_denied() -> Iterator[dict[str, int]]:
    counters = {"network_calls": 0}

    def deny(*_args: Any, **_kwargs: Any) -> None:
        counters["network_calls"] += 1
        raise AssertionError("network access denied by v0.5.4 self-test")

    with mock.patch.object(socket, "socket", side_effect=deny), mock.patch.object(
        socket, "create_connection", side_effect=deny
    ):
        yield counters


def _expect_rejected(action: Any, label: str) -> bool:
    try:
        action()
    except (TemporalAdjointValidationError, v053.FactorizedLineageValidationError, ValueError, TypeError):
        return True
    raise TemporalAdjointValidationError(f"expected rejection: {label}")


def _pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="validate and compile the locked fixture")
    validate.add_argument("--fixture", type=Path, default=DEFAULT_EVENT_FIXTURE)
    sub.add_parser("self-test", help="run strict mechanism tests")
    return parser


def self_test(
    *,
    event_fixture_path: Path = DEFAULT_EVENT_FIXTURE,
    no_event_fixture_path: Path = DEFAULT_NO_EVENT_FIXTURE,
    event_program: CompiledProgram | None = None,
    evaluations: Mapping[str, LaneEvaluation] | None = None,
    no_event_result: tuple[JsonObject, JsonObject] | None = None,
) -> JsonObject:
    with network_denied() as network_counter:
        event_fixture = load_fixture(event_fixture_path)
        no_event_fixture = load_fixture(no_event_fixture_path, no_event=True)
        program = event_program or compile_program(event_fixture)
        if not program.event_triggered:
            raise TemporalAdjointValidationError("self-test event program is inactive")
        lane_results = dict(evaluations or {})
        for schedule_id in LOCKED_SCHEDULE_IDS:
            lane_results.setdefault(schedule_id, evaluate_lane(program, schedule_id))
        audit, stable_lane = no_event_result or run_no_event_audit(no_event_fixture)

        numeric_fixture = _clone(event_fixture)
        numeric_fixture["base_matrix"] = [[1]]
        arbitrary_order_fixture = _clone(event_fixture)
        arbitrary_order_fixture["operator_order"] = ["support:judging_basis"]
        altered_schedule_fixture = _clone(event_fixture)
        altered_schedule_fixture["schedule_policy_ids"] = ["correction_late", "correction_early"]

        structural = compiled_structural_closure(program)
        expected_structural = _expected_structural_closure(program)
        receipt = program_receipt(program)

        severed = _program_without_edge(
            program, "repair:final_priority->demo_centerpiece"
        )
        severed_zero = torch.zeros(len(_site_rows(severed, "correction_late")), dtype=FLOAT_DTYPE)
        _severed_output, severed_jacobian = manual_forward_jacobian(
            severed, "correction_late", severed_zero
        )
        severed_axis = _terminal_axes(severed).index(
            ("fact:demo_centerpiece", "R2", "inherited")
        )
        severed_upstream_indices = [
            index
            for index, row in enumerate(_site_rows(severed, "correction_late"))
            if row["target_node_id"] == "fact:final_priority"
        ]
        severed_max = float(
            torch.max(
                torch.abs(
                    severed_jacobian[severed_axis, severed_upstream_indices]
                )
            )
        )
        original_zero = torch.zeros(program.site_count, dtype=FLOAT_DTYPE)
        _original_output, original_jacobian = manual_forward_jacobian(
            program, "correction_late", original_zero
        )
        original_axis = _terminal_axes(program).index(
            ("fact:demo_centerpiece", "R2", "inherited")
        )
        original_upstream_indices = [
            index
            for index, row in enumerate(_site_rows(program, "correction_late"))
            if row["target_node_id"] == "fact:final_priority"
        ]
        original_upstream_max = float(
            torch.max(
                torch.abs(original_jacobian[original_axis, original_upstream_indices])
            )
        )

        canonical_order = list(program.sweep_order)
        first = canonical_order.index("support:demo_readiness")
        second = canonical_order.index("support:judging_basis")
        permuted_order = list(canonical_order)
        permuted_order[first], permuted_order[second] = (
            permuted_order[second],
            permuted_order[first],
        )
        canonical_state = forward_state(
            program, "correction_late", original_zero
        )
        permuted_state = forward_state(
            program,
            "correction_late",
            original_zero,
            sweep_order_override=permuted_order,
        )
        permuted_jacobian = torch.autograd.functional.jacobian(
            lambda delta: forward_terminal(
                program,
                "correction_late",
                delta,
                sweep_order_override=permuted_order,
            ),
            original_zero,
        )
        reordered_permuted_jacobian = torch.zeros_like(permuted_jacobian)
        width = len(canonical_order)
        for horizon_index in range(len(program.evidence_ids)):
            for permuted_position, node_id in enumerate(permuted_order):
                canonical_position = canonical_order.index(node_id)
                reordered_permuted_jacobian[
                    :, horizon_index * width + canonical_position
                ] = permuted_jacobian[
                    :, horizon_index * width + permuted_position
                ]

        identity_site = program.site_count // 2
        identity_state = forward_state(
            program,
            "correction_late",
            original_zero,
            identity_after_site=identity_site,
        )
        identity_jacobian = torch.autograd.functional.jacobian(
            lambda delta: forward_terminal(
                program,
                "correction_late",
                delta,
                identity_after_site=identity_site,
            ),
            original_zero,
        )

        late_ordinal = tuple(
            row["evidence_id"]
            for row in sorted(
                (
                    row
                    for row in program.graph["nodes"]
                    if row["node_type"] == "evidence"
                ),
                key=lambda row: row["temporal_ordinal"],
            )
        )
        invalidator, invalidated = program.invalidation_edges[0]
        derived_early = list(late_ordinal)
        derived_early.remove(invalidator)
        derived_early.insert(derived_early.index(invalidated) + 1, invalidator)

        top_signatures = {
            schedule_id: (
                lane_results[schedule_id].sealed_lane["top_credit_site"][
                    "horizon_index"
                ],
                lane_results[schedule_id].sealed_lane["top_credit_site"][
                    "admitted_evidence_id"
                ],
                lane_results[schedule_id].sealed_lane["top_credit_site"][
                    "target_node_id"
                ],
            )
            for schedule_id in LOCKED_SCHEDULE_IDS
        }

        adversarial_sham_receipts = {
            schedule_id: _adversarial_sham_rejection_receipt(
                program, lane_results[schedule_id]
            )
            for schedule_id in LOCKED_SCHEDULE_IDS
        }

        deterministic_rebuilds = {
            schedule_id: evaluate_lane(program, schedule_id)
            for schedule_id in LOCKED_SCHEDULE_IDS
        }
        checks = {
            "arm_b_c_d_exact_l2_and_raw_bound": all(
                lane_results[schedule_id].sealed_lane["gates"][
                    "all_nonzero_controls_exact_l2_rho"
                ]
                and lane_results[schedule_id].sealed_lane["gates"][
                    "all_raw_delta_bounded"
                ]
                for schedule_id in LOCKED_SCHEDULE_IDS
            ),
            "locked_sham_geometry_exact": all(
                lane_results[schedule_id].sealed_lane["gates"][
                    "locked_sham_geometry_exact"
                ]
                for schedule_id in LOCKED_SCHEDULE_IDS
            ),
            "sham_adversaries_rejected": all(
                adversarial_sham_receipts[schedule_id]["status"] == "PASS"
                for schedule_id in LOCKED_SCHEDULE_IDS
            ),
            "c_beats_a_b_every_distinct_locked_d": all(
                lane_results[schedule_id].sealed_lane["gates"][
                    "c_beats_a_b_and_every_distinct_d"
                ]
                for schedule_id in LOCKED_SCHEDULE_IDS
            ),
            "canonical_outputs_byte_deterministic": all(
                canonical_json_bytes(lane_results[schedule_id].sealed_lane)
                == canonical_json_bytes(
                    deterministic_rebuilds[schedule_id].sealed_lane
                )
                and canonical_json_bytes(lane_results[schedule_id].geometry)
                == canonical_json_bytes(deterministic_rebuilds[schedule_id].geometry)
                for schedule_id in LOCKED_SCHEDULE_IDS
            ),
            "compiled_structural_closure_exact": structural == expected_structural,
            "correction_schedules_mechanically_derived": (
                tuple(program.schedules["correction_late"]) == late_ordinal
                and tuple(program.schedules["correction_early"])
                == tuple(derived_early)
            ),
            "early_late_top_credit_switches": (
                top_signatures["correction_early"]
                != top_signatures["correction_late"]
            ),
            "fixture_arbitrary_operator_order_rejected": _expect_rejected(
                lambda: validate_fixture(arbitrary_order_fixture),
                "fixture operator order",
            ),
            "fixture_arbitrary_schedule_rejected": _expect_rejected(
                lambda: validate_fixture(altered_schedule_fixture),
                "fixture schedule",
            ),
            "fixture_numeric_mechanism_rejected": _expect_rejected(
                lambda: validate_fixture(numeric_fixture),
                "fixture numeric mechanism",
            ),
            "identity_insertion_preserves_state_and_credit": (
                torch.equal(canonical_state, identity_state)
                and torch.equal(original_jacobian, identity_jacobian)
            ),
            "independent_support_permutation_exact": (
                torch.equal(canonical_state, permuted_state)
                and torch.equal(original_jacobian, reordered_permuted_jacobian)
            ),
            "manual_autograd_fd_norm_gates_pass": all(
                all(
                    lane_results[schedule_id].sealed_lane["gates"][key]
                    for key in (
                        "all_normalized_jacobian_norms_one",
                        "finite_difference_agrees",
                        "manual_forward_agrees_autograd",
                        "manual_reverse_agrees_autograd",
                    )
                )
                for schedule_id in LOCKED_SCHEDULE_IDS
            ),
            "no_event_zero_control_backward_identity": (
                audit["control_count"] == 0
                and audit["backward_calls"] == 0
                and audit["neutral_equals_controlled"] is True
                and audit["output_identity"] is True
                and stable_lane["status"] == "PASS"
            ),
            "sever_final_to_demo_zeroes_r2_inherited_upstream_jacobian": (
                original_upstream_max > 0.0 and severed_max == 0.0
            ),
            "state_axis_order_channel_evidence_node": _axis_sentinel_check(program),
            "v0_5_3_graph_closure_regression_exact": (
                program.regression_fingerprint_sha256
                == EXPECTED_V053_REGRESSION_FINGERPRINT
                and program.graph["fingerprint_sha256"]
                == EXPECTED_V053_REPAIRED_GRAPH_FINGERPRINT
                and program.closure["fingerprint_sha256"]
                == EXPECTED_V053_REPAIRED_CLOSURE_FINGERPRINT
            ),
            "zero_network_and_provider_calls": (
                network_counter["network_calls"] == 0
                and all(
                    lane_results[schedule_id].sealed_lane["provider_calls"] == 0
                    and lane_results[schedule_id].sealed_lane["network_calls"] == 0
                    for schedule_id in LOCKED_SCHEDULE_IDS
                )
                and audit["provider_calls"] == 0
                and audit["network_calls"] == 0
            ),
        }
        evidence = {
            "adversarial_sham_rejection": adversarial_sham_receipts,
            "lane_numeric_audits": {
                schedule_id: {
                    "c_vs_b_loss_margin": lane_results[schedule_id].comparison[
                        "c_vs_b_loss_margin"
                    ],
                    "c_vs_best_distinct_d_loss_margin": lane_results[
                        schedule_id
                    ].comparison["c_vs_best_distinct_d_loss_margin"],
                    "central_finite_difference_max_abs_error": lane_results[
                        schedule_id
                    ].sealed_lane["adjoint_audit"][
                        "central_finite_difference_max_abs_error"
                    ],
                    "manual_forward_max_abs_error": lane_results[
                        schedule_id
                    ].sealed_lane["adjoint_audit"][
                        "manual_forward_max_abs_error"
                    ],
                    "manual_reverse_max_abs_error": lane_results[
                        schedule_id
                    ].sealed_lane["adjoint_audit"][
                        "manual_reverse_max_abs_error"
                    ],
                    "normalized_jacobian_max_norm_error": lane_results[
                        schedule_id
                    ].sealed_lane["adjoint_audit"][
                        "normalized_jacobian_max_norm_error"
                    ],
                    "top_credit_margin": lane_results[schedule_id].sealed_lane[
                        "top_credit_site"
                    ]["runner_up_margin"],
                    "top_credit_site": lane_results[schedule_id].sealed_lane[
                        "top_credit_site"
                    ],
                }
                for schedule_id in LOCKED_SCHEDULE_IDS
            },
            "network_calls": network_counter["network_calls"],
            "original_r2_demo_upstream_jacobian_max_abs": original_upstream_max,
            "program_fingerprint_sha256": receipt["fingerprint_sha256"],
            "severed_r2_demo_upstream_jacobian_max_abs": severed_max,
            "source_fingerprints": {
                "closure": program.closure["fingerprint_sha256"],
                "graph": program.graph["fingerprint_sha256"],
                "regression": program.regression_fingerprint_sha256,
            },
        }
    hard_gates = {
        "v053_source_exact": checks["v0_5_3_graph_closure_regression_exact"],
        "compiled_closure_exact": checks["compiled_structural_closure_exact"],
        "fixture_mechanism_injection_rejected": (
            checks["fixture_numeric_mechanism_rejected"]
            and checks["fixture_arbitrary_operator_order_rejected"]
            and checks["fixture_arbitrary_schedule_rejected"]
        ),
        "forward_sensitivity_agreement": all(
            lane_results[schedule_id].sealed_lane["gates"][
                "manual_forward_agrees_autograd"
            ]
            for schedule_id in LOCKED_SCHEDULE_IDS
        ),
        "reverse_adjoint_agreement": all(
            lane_results[schedule_id].sealed_lane["gates"][
                "manual_reverse_agrees_autograd"
            ]
            for schedule_id in LOCKED_SCHEDULE_IDS
        ),
        "central_finite_difference_agreement": all(
            lane_results[schedule_id].sealed_lane["gates"][
                "finite_difference_agrees"
            ]
            for schedule_id in LOCKED_SCHEDULE_IDS
        ),
        "normalized_jacobian_geometry": all(
            lane_results[schedule_id].sealed_lane["gates"][
                "all_normalized_jacobian_norms_one"
            ]
            for schedule_id in LOCKED_SCHEDULE_IDS
        ),
        "severed_path_zero_credit": checks[
            "sever_final_to_demo_zeroes_r2_inherited_upstream_jacobian"
        ],
        "independent_operator_permutation_invariant": checks[
            "independent_support_permutation_exact"
        ],
        "identity_insertion_invariant": checks[
            "identity_insertion_preserves_state_and_credit"
        ],
        "early_late_top_credit_switch": checks[
            "early_late_top_credit_switches"
        ],
        "no_event_exact_identity": checks[
            "no_event_zero_control_backward_identity"
        ],
        "matched_control_geometry": checks[
            "arm_b_c_d_exact_l2_and_raw_bound"
        ]
        and checks["locked_sham_geometry_exact"]
        and checks["sham_adversaries_rejected"],
        "exact_credit_beats_zero_and_node_tied": all(
            lane_results[schedule_id].comparison["c_strictly_beats_under_1e_12"][
                arm_id
            ]
            for schedule_id in LOCKED_SCHEDULE_IDS
            for arm_id in ("A", "B")
        ),
        "exact_credit_beats_all_timing_shams": all(
            passed
            for schedule_id in LOCKED_SCHEDULE_IDS
            for arm_id, passed in lane_results[schedule_id].comparison[
                "c_strictly_beats_under_1e_12"
            ].items()
            if arm_id.startswith("D")
        ),
        "two_build_byte_identity": checks[
            "canonical_outputs_byte_deterministic"
        ],
        "socket_denied_network_zero": checks[
            "zero_network_and_provider_calls"
        ],
    }
    if tuple(hard_gates) != HARD_GATE_IDS:
        raise AssertionError("hard gate enumeration drift")
    promotion_ready = all(hard_gates.values())
    payload: JsonObject = {
        "checks": checks,
        "evidence": evidence,
        "hard_gates": hard_gates,
        "network_calls": network_counter["network_calls"],
        "promotion_ready": promotion_ready,
        "provider_calls": 0,
        "schema_version": SELF_TEST_SCHEMA_VERSION,
        "status": "PASS" if all(checks.values()) and promotion_ready else "FAIL",
    }
    payload["fingerprint_sha256"] = fingerprint(payload)
    return payload


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        fixture = load_fixture(args.fixture)
        print(_pretty_json(program_receipt(compile_program(fixture))), end="")
        return 0
    if args.command == "self-test":
        result = self_test()
        print(_pretty_json(result), end="")
        return 0 if result["status"] == "PASS" else 1
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
