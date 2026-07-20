#!/usr/bin/env python3
"""EBRT v0.6.3 provider-actuator calibration monolith.

This file owns the network-zero v0.6.3 mechanism and public contract.  It asks
one narrow question: can a real local gradient be compiled into one explicit
``bounded_reinspection_schedule`` whose placement is distinguishable from a
matched anti-placement construct control at a hosted-model boundary?

The hosted model is not differentiated.  The public inspection-plan receipt is
never counted as downstream uptake.  The D arm is built and evaluated in the
same frozen q^D coordinate system, so this is construct-aligned calibration,
not independent validation or a reasoning-quality result.

No live provider call is authorized by this module's current CLI.  ``self-test``
and ``preflight`` are network-zero.
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
FIXTURE_PATH = ROOT / "fixtures" / "actuator_calibration_v0_6_3.json"
GOLD_PATH = ROOT / "fixtures" / "actuator_calibration_gold_v0_6_3.json"
POLICY_LOCK_PATH = ROOT / "policy_lock_actuator_calibration_v0_6_3.json"
DEFAULT_ARTIFACT_DIR = ROOT / "artifacts" / "actuator_calibration_v0_6_3_preflight"

FIXTURE_SCHEMA = "ebrt-actuator-calibration-fixture-v0.6.3"
GOLD_SCHEMA = "ebrt-actuator-calibration-gold-v0.6.3"
PROVIDER_INPUT_SCHEMA = "ebrt-actuator-calibration-provider-input-v0.6.3"
PROVIDER_OUTPUT_SCHEMA = "ebrt-actuator-calibration-provider-output-v0.6.3"
COMPILED_SCHEMA = "ebrt-actuator-calibration-compiled-output-v0.6.3"
PROJECTION_SCHEMA = "ebrt-actuator-calibration-projection-v0.6.3"
SELF_TEST_SCHEMA = "ebrt-actuator-calibration-self-test-v0.6.3"
CONTROLLER_AUDIT_SCHEMA = "ebrt-actuator-controller-audit-v0.6.3"

OPERATOR = "bounded_reinspection_schedule"
ARMS = ("Z", "C", "D", "X")
REVIEW_BUDGET = 3
ACTIVE_TIERS = (3, 2, 1)
POSITIVE_CONTROL_SEED = "2b2e58710871767e1f522f75380a7ca3c1d8580e"
POSITIVE_CONTROL_SEED_PROVENANCE = (
    "Immediate v0.6.3 predecessor branch head; fixed before this implementation."
)
FLOAT_TOLERANCE = 1.0e-12
MODEL = "gpt-5.6-sol"
REASONING_EFFORT = "low"
MAX_OUTPUT_TOKENS = 2048
TIMEOUT_SECONDS = 60

WILLIAMS_BLOCKS = (
    ("block_1", "relay_bay_revision_a", 1, ("Z", "C", "X", "D")),
    ("block_2", "coolant_loop_revision_b", 1, ("C", "D", "Z", "X")),
    ("block_3", "relay_bay_revision_a", 2, ("D", "X", "C", "Z")),
    ("block_4", "coolant_loop_revision_b", 2, ("X", "Z", "D", "C")),
)

FORBIDDEN_PROVIDER_KEYS = frozenset(
    {
        "accepted_edge_ids",
        "accepted_edges",
        "answer",
        "answer_key",
        "arm",
        "arm_id",
        "correct_answer",
        "treatment_id",
        "blinded_request_id",
        "effect_by_evidence_id",
        "expected_closure",
        "expected_closures",
        "q_d",
        "q_x",
        "polarity",
        "gradient",
        "controller",
        "local_controller",
        "closure_contract",
        "equivalence_classes",
        "valid_necessary_support_closures",
        "expected_answer",
        "preferred_path",
        "terminal_target",
        "valid_closure",
        "valid_closures",
        "gold",
        "grade",
        "sham",
    }
)

HARD_GATE_IDS = (
    "strict_fixture_contract",
    "symmetric_candidate_universe",
    "real_float64_backward",
    "central_finite_difference_agreement",
    "unit_l1_polarities",
    "opposite_case_positive_controls",
    "z_true_no_reordering",
    "matched_schedule_geometry",
    "c_eligible_derangement",
    "d_input_alignment_exceeds_c",
    "provider_payloads_leak_free",
    "non_actuator_payload_fields_matched",
    "williams_four_block_balance",
    "sixteen_payloads_presealed",
    "exact_one_closure_enforced",
    "inspection_receipt_excluded_from_alignment",
    "p0_p1_alignment_arithmetic_exact",
    "output_contract_roundtrip",
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


class ActuatorCalibrationError(ValueError):
    """Fail-closed v0.6.3 validation error with a stable reason code."""

    def __init__(self, reason_code: str, detail: str = "") -> None:
        self.reason_code = reason_code
        super().__init__(reason_code if not detail else f"{reason_code}: {detail}")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class DecisionSlotOutput(_StrictModel):
    slot_id: str = Field(min_length=1, max_length=96)
    value: str = Field(min_length=1, max_length=160)


class InspectionPlanOutput(_StrictModel):
    operator: Literal[OPERATOR]
    reviewed_evidence_ids: list[str] = Field(
        min_length=REVIEW_BUDGET, max_length=REVIEW_BUDGET
    )


class ActuatorCalibrationOutput(_StrictModel):
    schema_version: Literal[PROVIDER_OUTPUT_SCHEMA]
    checkpoint_id: str = Field(min_length=1, max_length=160)
    current_answer: str = Field(min_length=1, max_length=160)
    decision_slots: list[DecisionSlotOutput] = Field(min_length=1, max_length=8)
    inspection_plan: InspectionPlanOutput
    selected_candidate_edge_ids: list[str] = Field(min_length=1, max_length=64)


def _require(condition: bool, reason: str, detail: str = "") -> None:
    if not condition:
        raise ActuatorCalibrationError(reason, detail)


def _reject_constant(value: str) -> Any:
    raise ActuatorCalibrationError("NONFINITE_JSON", value)


def _reject_duplicates(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ActuatorCalibrationError("DUPLICATE_JSON_KEY", key)
        output[key] = value
    return output


def _strict_json_bytes(value: bytes, *, label: str) -> Any:
    try:
        text = value.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ActuatorCalibrationError("NON_UTF8_JSON", label) from error
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicates,
            parse_constant=_reject_constant,
        )
    except ActuatorCalibrationError:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise ActuatorCalibrationError("INVALID_JSON", label) from error


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


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _clone(value: Any) -> Any:
    return copy.deepcopy(value)


def _without_fingerprint(value: Mapping[str, Any]) -> dict[str, Any]:
    output = _clone(dict(value))
    output.pop("fingerprint_sha256", None)
    return output


def _seal(value: Mapping[str, Any]) -> dict[str, Any]:
    output = _without_fingerprint(value)
    output["fingerprint_sha256"] = _fingerprint(output)
    return output


def _validate_fingerprint(value: Mapping[str, Any], label: str) -> None:
    _require(
        value.get("fingerprint_sha256") == _fingerprint(_without_fingerprint(value)),
        "FINGERPRINT_DRIFT",
        label,
    )


def _finite(value: Any, label: str) -> float:
    _require(
        isinstance(value, (int, float)) and not isinstance(value, bool),
        "NON_NUMERIC_VALUE",
        label,
    )
    output = float(value)
    _require(math.isfinite(output), "NONFINITE_VALUE", label)
    return output


def _unique_strings(values: Any, label: str) -> tuple[str, ...]:
    _require(isinstance(values, list), "EXPECTED_LIST", label)
    output = tuple(value for value in values if isinstance(value, str) and value)
    _require(len(output) == len(values), "INVALID_STRING_LIST", label)
    _require(len(output) == len(set(output)), "DUPLICATE_VALUE", label)
    return output


def _case_map(fixture: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    cases = fixture.get("cases")
    _require(isinstance(cases, list) and len(cases) == 2, "CASE_SET_INVALID")
    output: dict[str, dict[str, Any]] = {}
    for case in cases:
        _require(isinstance(case, dict), "CASE_INVALID")
        case_id = case.get("case_id")
        _require(
            isinstance(case_id, str) and case_id and case_id not in output,
            "CASE_ID_INVALID",
        )
        output[case_id] = case
    return output


def _edge_map(case: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    scaffold = case.get("candidate_scaffold")
    _require(isinstance(scaffold, Mapping), "SCAFFOLD_INVALID")
    edges = scaffold.get("candidate_edges")
    _require(isinstance(edges, list) and edges, "CANDIDATE_EDGES_INVALID")
    output: dict[str, dict[str, Any]] = {}
    for edge in edges:
        _require(isinstance(edge, dict), "CANDIDATE_EDGE_INVALID")
        edge_id = edge.get("edge_id")
        _require(
            isinstance(edge_id, str) and edge_id and edge_id not in output,
            "CANDIDATE_EDGE_ID_INVALID",
        )
        output[edge_id] = edge
    return output


def _closure_parts(case: Mapping[str, Any]) -> dict[str, Any]:
    contract = case.get("closure_contract")
    _require(isinstance(contract, Mapping), "CLOSURE_CONTRACT_INVALID")
    _require(
        set(contract)
        == {
            "equivalence_classes",
            "shared_support",
            "stable_support",
            "invalidation",
            "primary_target_node_id",
            "stable_target_node_id",
        },
        "CLOSURE_CONTRACT_SCHEMA_DRIFT",
    )
    classes = contract.get("equivalence_classes")
    _require(
        isinstance(classes, Mapping) and set(classes) == {"P0", "P1"},
        "EQUIVALENCE_CLASS_INVALID",
    )
    output: dict[str, Any] = {
        "paths": {},
        "primary_target_node_id": contract.get("primary_target_node_id"),
        "stable_target_node_id": contract.get("stable_target_node_id"),
    }
    for path_id in ("P0", "P1"):
        row = classes[path_id]
        _require(
            isinstance(row, Mapping) and set(row) == {"evidence_ids", "edge_ids"},
            "EQUIVALENCE_PATH_INVALID",
            path_id,
        )
        output["paths"][path_id] = {
            "evidence_ids": _unique_strings(
                row.get("evidence_ids"), f"{path_id}.evidence_ids"
            ),
            "edge_ids": _unique_strings(row.get("edge_ids"), f"{path_id}.edge_ids"),
        }
    for key in ("shared_support", "stable_support"):
        row = contract.get(key)
        _require(
            isinstance(row, Mapping) and set(row) == {"evidence_ids", "edge_ids"},
            "CLOSURE_PART_INVALID",
            key,
        )
        output[key] = {
            "evidence_ids": _unique_strings(
                row.get("evidence_ids"), f"{key}.evidence_ids"
            ),
            "edge_ids": _unique_strings(row.get("edge_ids"), f"{key}.edge_ids"),
        }
    invalidation = contract.get("invalidation")
    _require(isinstance(invalidation, Mapping), "INVALIDATION_CONTRACT_INVALID")
    _require(
        set(invalidation) == {"source_evidence_id", "target_evidence_id", "edge_id"},
        "INVALIDATION_CONTRACT_INVALID",
    )
    output["invalidation"] = dict(invalidation)
    return output


def _node_type_map(case: Mapping[str, Any]) -> dict[str, str]:
    scaffold = case.get("candidate_scaffold")
    _require(isinstance(scaffold, Mapping), "SCAFFOLD_INVALID")
    nodes = scaffold.get("nodes")
    _require(isinstance(nodes, list), "SCAFFOLD_NODES_INVALID")
    return {
        str(row["node_id"]): str(row["node_type"])
        for row in nodes
        if isinstance(row, Mapping) and "node_id" in row and "node_type" in row
    }


def _evidence_reaching_target(
    selected_edge_ids: Sequence[str],
    *,
    edges: Mapping[str, Mapping[str, Any]],
    node_types: Mapping[str, str],
    target_node_id: str,
) -> tuple[str, ...]:
    reverse: dict[str, list[str]] = {}
    for edge_id in selected_edge_ids:
        edge = edges[edge_id]
        if edge["relation_type"] not in {"supports", "depends_on"}:
            continue
        reverse.setdefault(str(edge["target_node_id"]), []).append(
            str(edge["source_node_id"])
        )
    reached: set[str] = set()
    frontier = [target_node_id]
    while frontier:
        node_id = frontier.pop()
        if node_id in reached:
            continue
        reached.add(node_id)
        frontier.extend(reverse.get(node_id, ()))
    return tuple(
        sorted(node_id for node_id in reached if node_types.get(node_id) == "evidence")
    )


def _support_edges_reaching_targets(
    selected_edge_ids: Sequence[str],
    *,
    edges: Mapping[str, Mapping[str, Any]],
    target_node_ids: Sequence[str],
) -> set[str]:
    reached_nodes = set(target_node_ids)
    used_edges: set[str] = set()
    changed = True
    while changed:
        changed = False
        for edge_id in selected_edge_ids:
            edge = edges[edge_id]
            if edge["relation_type"] not in {"supports", "depends_on"}:
                continue
            if edge["target_node_id"] in reached_nodes and edge_id not in used_edges:
                used_edges.add(edge_id)
                reached_nodes.add(str(edge["source_node_id"]))
                changed = True
    return used_edges


def validate_fixture(fixture: Mapping[str, Any]) -> dict[str, Any]:
    _require(
        set(fixture)
        == {
            "schema_version",
            "status",
            "operator",
            "review_budget",
            "active_priority_tiers",
            "arms",
            "cases",
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
    _require(fixture.get("review_budget") == REVIEW_BUDGET, "REVIEW_BUDGET_DRIFT")
    _require(
        tuple(fixture.get("active_priority_tiers", ())) == ACTIVE_TIERS, "TIER_DRIFT"
    )
    _require(tuple(fixture.get("arms", ())) == ARMS, "ARM_SET_DRIFT")
    _require(
        bool(_unique_strings(fixture.get("claim_boundary"), "fixture.claim_boundary")),
        "FIXTURE_CLAIM_BOUNDARY_INVALID",
    )
    cases = _case_map(fixture)
    _require(set(cases) == {row[1] for row in WILLIAMS_BLOCKS}, "WILLIAMS_CASE_DRIFT")

    x_choices: dict[str, str] = {}
    path_sizes: set[int] = set()
    symmetric_checks: dict[str, bool] = {}
    for case_id, case in cases.items():
        _require(
            set(case)
            == {
                "case_id",
                "checkpoint_id",
                "question",
                "answer_choices",
                "decision_slots",
                "raw_evidence",
                "candidate_scaffold",
                "local_controller",
                "closure_contract",
            },
            "CASE_SCHEMA_DRIFT",
            case_id,
        )
        _require(
            isinstance(case.get("checkpoint_id"), str)
            and bool(case["checkpoint_id"])
            and isinstance(case.get("question"), str)
            and bool(case["question"]),
            "CASE_TEXT_FIELD_INVALID",
            case_id,
        )
        answer_choices = _unique_strings(
            case.get("answer_choices"), f"{case_id}.answer_choices"
        )
        _require(len(answer_choices) == 2, "ANSWER_CHOICES_INVALID", case_id)
        decision_slots = case.get("decision_slots")
        _require(
            isinstance(decision_slots, list) and len(decision_slots) == 2,
            "DECISION_SLOTS_INVALID",
            case_id,
        )
        slot_ids: list[str] = []
        for slot in decision_slots:
            _require(
                isinstance(slot, Mapping)
                and set(slot) == {"slot_id", "allowed_values"}
                and isinstance(slot.get("slot_id"), str)
                and bool(slot["slot_id"]),
                "DECISION_SLOT_INVALID",
                case_id,
            )
            slot_ids.append(str(slot["slot_id"]))
            _require(
                bool(
                    _unique_strings(
                        slot.get("allowed_values"), f"{case_id}.{slot['slot_id']}"
                    )
                ),
                "DECISION_SLOT_VALUES_INVALID",
                case_id,
            )
        _require(
            len(slot_ids) == len(set(slot_ids)), "DECISION_SLOT_DUPLICATE", case_id
        )
        raw = case.get("raw_evidence")
        _require(
            isinstance(raw, list) and len(raw) >= 7, "RAW_EVIDENCE_INVALID", case_id
        )
        evidence_ids = _unique_strings(
            [row.get("evidence_id") for row in raw if isinstance(row, Mapping)],
            f"{case_id}.raw_evidence",
        )
        _require(len(evidence_ids) == len(raw), "RAW_EVIDENCE_INVALID", case_id)
        _require(
            all(
                isinstance(row, Mapping)
                and set(row) == {"evidence_id", "text"}
                and isinstance(row.get("text"), str)
                and row["text"]
                for row in raw
            ),
            "RAW_EVIDENCE_TEXT_INVALID",
            case_id,
        )

        scaffold = case.get("candidate_scaffold")
        _require(
            isinstance(scaffold, Mapping)
            and set(scaffold)
            == {
                "schema_version",
                "allowed_relation_types",
                "nodes",
                "candidate_edges",
                "target_bindings",
            }
            and scaffold.get("schema_version")
            == "ebrt-neutral-candidate-scaffold-v0.6.3",
            "SCAFFOLD_INVALID",
            case_id,
        )
        nodes = scaffold.get("nodes")
        _require(isinstance(nodes, list) and nodes, "SCAFFOLD_NODES_INVALID", case_id)
        node_ids = _unique_strings(
            [row.get("node_id") for row in nodes if isinstance(row, Mapping)],
            f"{case_id}.nodes",
        )
        _require(len(node_ids) == len(nodes), "SCAFFOLD_NODES_INVALID", case_id)
        _require(
            all(
                isinstance(row, Mapping)
                and set(row) == {"node_id", "node_type"}
                and row.get("node_type")
                in {"evidence", "support", "fact", "constraint"}
                for row in nodes
            ),
            "SCAFFOLD_NODE_SCHEMA_DRIFT",
            case_id,
        )
        node_types = _node_type_map(case)
        _require(
            {node for node, kind in node_types.items() if kind == "evidence"}
            == set(evidence_ids),
            "SCAFFOLD_EVIDENCE_NODE_DRIFT",
            case_id,
        )
        _require(
            tuple(scaffold.get("allowed_relation_types", ()))
            == ("supports", "depends_on", "invalidates"),
            "RELATION_TYPE_SET_DRIFT",
            case_id,
        )
        allowed_relations = set(scaffold.get("allowed_relation_types", ()))
        edges = _edge_map(case)
        for edge_id, edge in edges.items():
            _require(
                set(edge)
                == {"edge_id", "source_node_id", "target_node_id", "relation_type"}
                and edge["source_node_id"] in node_types
                and edge["target_node_id"] in node_types
                and edge["relation_type"] in allowed_relations,
                "CANDIDATE_EDGE_INVALID",
                f"{case_id}:{edge_id}",
            )

        target_bindings = scaffold.get("target_bindings")
        _require(
            isinstance(target_bindings, list) and len(target_bindings) == len(slot_ids),
            "TARGET_BINDINGS_INVALID",
            case_id,
        )
        binding_map: dict[str, str] = {}
        for binding in target_bindings:
            _require(
                isinstance(binding, Mapping)
                and set(binding) == {"node_id", "slot_id"}
                and binding.get("node_id") in node_types
                and node_types[str(binding["node_id"])] in {"fact", "constraint"}
                and binding.get("slot_id") in slot_ids,
                "TARGET_BINDING_INVALID",
                case_id,
            )
            _require(
                binding["node_id"] not in binding_map,
                "TARGET_BINDING_DUPLICATE",
                case_id,
            )
            binding_map[str(binding["node_id"])] = str(binding["slot_id"])
        _require(
            set(binding_map.values()) == set(slot_ids),
            "TARGET_SLOT_BINDING_DRIFT",
            case_id,
        )

        parts = _closure_parts(case)
        p0 = set(parts["paths"]["P0"]["evidence_ids"])
        p1 = set(parts["paths"]["P1"]["evidence_ids"])
        shared = set(parts["shared_support"]["evidence_ids"])
        stable = set(parts["stable_support"]["evidence_ids"])
        invalid_target = parts["invalidation"]["target_evidence_id"]
        _require(len(p0) == len(p1) and len(p0) >= 2, "PATH_CARDINALITY_DRIFT", case_id)
        _require(not (p0 & p1), "PATHS_NOT_DISJOINT", case_id)
        _require(
            not ((p0 | p1) & (shared | stable | {invalid_target})),
            "CLOSURE_PARTITION_OVERLAP",
            case_id,
        )
        _require(
            (p0 | p1 | shared | stable | {invalid_target}).issubset(evidence_ids),
            "CLOSURE_EVIDENCE_UNKNOWN",
            case_id,
        )
        _require(
            p0 | p1 | shared | stable | {invalid_target} == set(evidence_ids),
            "UNMANAGED_EVIDENCE_PRESENT",
            case_id,
        )
        _require(
            isinstance(parts["primary_target_node_id"], str)
            and isinstance(parts["stable_target_node_id"], str)
            and binding_map
            == {
                parts["primary_target_node_id"]: "primary_decision",
                parts["stable_target_node_id"]: "stable_constraint",
            },
            "CLOSURE_TARGET_BINDING_DRIFT",
            case_id,
        )
        path_sizes.add(len(p0))
        all_contract_edges = set(parts["paths"]["P0"]["edge_ids"])
        all_contract_edges |= set(parts["paths"]["P1"]["edge_ids"])
        all_contract_edges |= set(parts["shared_support"]["edge_ids"])
        all_contract_edges |= set(parts["stable_support"]["edge_ids"])
        all_contract_edges.add(parts["invalidation"]["edge_id"])
        _require(all_contract_edges.issubset(edges), "CONTRACT_EDGE_UNKNOWN", case_id)

        for path_id in ("P0", "P1"):
            derived = set(
                _evidence_reaching_target(
                    parts["paths"][path_id]["edge_ids"],
                    edges=edges,
                    node_types=node_types,
                    target_node_id=parts["primary_target_node_id"],
                )
            )
            _require(
                derived == set(parts["paths"][path_id]["evidence_ids"]),
                "PATH_GRAPH_EVIDENCE_DRIFT",
                f"{case_id}:{path_id}",
            )
        _require(
            set(
                _evidence_reaching_target(
                    parts["shared_support"]["edge_ids"],
                    edges=edges,
                    node_types=node_types,
                    target_node_id=parts["primary_target_node_id"],
                )
            )
            == shared,
            "SHARED_GRAPH_EVIDENCE_DRIFT",
            case_id,
        )
        _require(
            set(
                _evidence_reaching_target(
                    parts["stable_support"]["edge_ids"],
                    edges=edges,
                    node_types=node_types,
                    target_node_id=parts["stable_target_node_id"],
                )
            )
            == stable,
            "STABLE_GRAPH_EVIDENCE_DRIFT",
            case_id,
        )
        invalidation_edge = edges[parts["invalidation"]["edge_id"]]
        _require(
            invalidation_edge
            == {
                "edge_id": parts["invalidation"]["edge_id"],
                "source_node_id": parts["invalidation"]["source_evidence_id"],
                "target_node_id": parts["invalidation"]["target_evidence_id"],
                "relation_type": "invalidates",
            },
            "INVALIDATION_EDGE_TOPOLOGY_DRIFT",
            case_id,
        )

        support_targets: list[str] = []
        for path_id in ("P0", "P1"):
            path_edges = [edges[item] for item in parts["paths"][path_id]["edge_ids"]]
            terminal = [
                row
                for row in path_edges
                if node_types[row["source_node_id"]] == "support"
                and node_types[row["target_node_id"]] == "fact"
            ]
            _require(
                len(terminal) == 1, "PATH_TERMINAL_EDGE_INVALID", f"{case_id}:{path_id}"
            )
            support_targets.append(terminal[0]["source_node_id"])
        symmetric = {
            (edge["source_node_id"], edge["target_node_id"])
            for edge in edges.values()
            if edge["relation_type"] == "supports"
        }
        symmetric_checks[case_id] = all(
            (evidence_id, support_id) in symmetric
            for evidence_id in sorted(p0 | p1)
            for support_id in support_targets
        )
        _require(symmetric_checks[case_id], "CANDIDATE_UNIVERSE_NOT_SYMMETRIC", case_id)

        controller = case.get("local_controller")
        _require(
            isinstance(controller, Mapping)
            and set(controller)
            == {
                "eligible_evidence_ids",
                "effect_by_evidence_id",
                "terminal_target",
                "finite_difference_epsilon",
                "finite_difference_tolerance",
            },
            "CONTROLLER_FIXTURE_INVALID",
            case_id,
        )
        effects = controller.get("effect_by_evidence_id")
        _require(isinstance(effects, Mapping), "CONTROLLER_EFFECTS_INVALID", case_id)
        _require(
            set(controller.get("eligible_evidence_ids", ())) == (p0 | p1 | shared),
            "CONTROLLER_ELIGIBILITY_DRIFT",
            case_id,
        )
        _require(
            set(effects) == set(controller["eligible_evidence_ids"]),
            "CONTROLLER_EFFECT_KEYSET_DRIFT",
            case_id,
        )
        for evidence_id in p0 | p1 | shared:
            _finite(effects.get(evidence_id), f"{case_id}.effect.{evidence_id}")
        _finite(controller.get("terminal_target"), f"{case_id}.terminal_target")
        _require(
            _finite(
                controller.get("finite_difference_epsilon"), f"{case_id}.fd_epsilon"
            )
            > 0.0,
            "FINITE_DIFFERENCE_EPSILON_INVALID",
            case_id,
        )
        _require(
            _finite(
                controller.get("finite_difference_tolerance"), f"{case_id}.fd_tolerance"
            )
            > 0.0,
            "FINITE_DIFFERENCE_TOLERANCE_INVALID",
            case_id,
        )

        hashes = {
            path_id: hashlib.sha256(
                f"{POSITIVE_CONTROL_SEED}:{case_id}:{path_id}".encode("utf-8")
            ).hexdigest()
            for path_id in ("P0", "P1")
        }
        x_choices[case_id] = min(hashes, key=hashes.get)  # type: ignore[arg-type]

    _require(path_sizes == {2}, "PATH_SIZE_NOT_FROZEN")
    _require(set(x_choices.values()) == {"P0", "P1"}, "POSITIVE_CONTROL_NOT_BALANCED")
    return {
        "case_ids": sorted(cases),
        "path_size": 2,
        "positive_control_path_by_case": x_choices,
        "symmetric_candidate_universe_by_case": symmetric_checks,
    }


def _center_l1(
    values: Mapping[str, float], eligible: Sequence[str]
) -> dict[str, float]:
    _require(bool(eligible), "POLARITY_ELIGIBLE_SET_EMPTY")
    mean = math.fsum(values[item] for item in eligible) / len(eligible)
    centered = {item: values[item] - mean for item in eligible}
    norm = math.fsum(abs(value) for value in centered.values())
    _require(math.isfinite(norm) and norm > 0.0, "POLARITY_ZERO_NORM")
    return {item: centered[item] / norm for item in eligible}


def _controller_loss(
    u: torch.Tensor, effects: torch.Tensor, target: torch.Tensor
) -> torch.Tensor:
    gates = 2.0 * torch.sigmoid(u)
    state = torch.sum(gates * effects) / torch.sum(gates)
    return torch.square(state - target) + 0.01 * torch.mean(torch.square(gates - 1.0))


def derive_controller(case: Mapping[str, Any]) -> dict[str, Any]:
    case_id = str(case["case_id"])
    parts = _closure_parts(case)
    alternatives = tuple(
        sorted(
            set(parts["paths"]["P0"]["evidence_ids"])
            | set(parts["paths"]["P1"]["evidence_ids"])
        )
    )
    controller = case["local_controller"]
    controller_ids = tuple(controller["eligible_evidence_ids"])
    effects_by_id = {
        item: _finite(controller["effect_by_evidence_id"][item], f"effect:{item}")
        for item in controller_ids
    }
    effects = torch.tensor(
        [effects_by_id[item] for item in controller_ids], dtype=torch.float64
    )
    target = torch.tensor(float(controller["terminal_target"]), dtype=torch.float64)
    u = torch.zeros(len(controller_ids), dtype=torch.float64, requires_grad=True)
    loss = _controller_loss(u, effects, target)
    (gradient,) = torch.autograd.grad(loss, u)
    raw_direction = {
        item: -float(gradient[index].detach().item())
        for index, item in enumerate(controller_ids)
    }
    q_alt = _center_l1(raw_direction, alternatives)
    q_d = {
        item: (q_alt[item] if item in q_alt else 0.0)
        for item in sorted(
            set(controller_ids)
            | set(parts["stable_support"]["evidence_ids"])
            | {parts["invalidation"]["target_evidence_id"]}
        )
    }
    epsilon = float(controller["finite_difference_epsilon"])
    fd_values: list[float] = []
    for index in range(len(controller_ids)):
        plus = torch.zeros(len(controller_ids), dtype=torch.float64)
        minus = torch.zeros(len(controller_ids), dtype=torch.float64)
        plus[index] = epsilon
        minus[index] = -epsilon
        difference = (
            _controller_loss(plus, effects, target)
            - _controller_loss(minus, effects, target)
        ) / (2.0 * epsilon)
        fd_values.append(float(difference.item()))
    max_fd_error = max(
        abs(fd_values[index] - float(gradient[index].item()))
        for index in range(len(controller_ids))
    )
    _require(
        max_fd_error <= float(controller["finite_difference_tolerance"]),
        "FINITE_DIFFERENCE_MISMATCH",
        case_id,
    )
    path_sums = {
        path_id: math.fsum(
            q_d[item] for item in parts["paths"][path_id]["evidence_ids"]
        )
        for path_id in ("P0", "P1")
    }
    _require(
        abs(path_sums["P0"] - path_sums["P1"]) > FLOAT_TOLERANCE,
        "CONTROLLER_PATH_TIE",
        case_id,
    )
    q_d_path = max(path_sums, key=path_sums.get)  # type: ignore[arg-type]

    hashes = {
        path_id: hashlib.sha256(
            f"{POSITIVE_CONTROL_SEED}:{case_id}:{path_id}".encode("utf-8")
        ).hexdigest()
        for path_id in ("P0", "P1")
    }
    q_x_path = min(hashes, key=hashes.get)  # type: ignore[arg-type]
    other_path = "P1" if q_x_path == "P0" else "P0"
    chosen_ids = tuple(parts["paths"][q_x_path]["evidence_ids"])
    other_ids = tuple(parts["paths"][other_path]["evidence_ids"])
    scale = 1.0 / (len(chosen_ids) + len(other_ids))
    q_x = {item: 0.0 for item in q_d}
    for item in chosen_ids:
        q_x[item] = scale
    for item in other_ids:
        q_x[item] = -scale
    _require(
        abs(math.fsum(abs(q_d[item]) for item in alternatives) - 1.0) <= FLOAT_TOLERANCE
        and abs(math.fsum(abs(q_x[item]) for item in alternatives) - 1.0)
        <= FLOAT_TOLERANCE,
        "POLARITY_L1_DRIFT",
        case_id,
    )
    _require(
        all(
            q_d[item] == 0.0 and q_x[item] == 0.0
            for item in set(q_d) - set(alternatives)
        ),
        "PROTECTED_POLARITY_NONZERO",
        case_id,
    )
    return _seal(
        {
            "schema_version": CONTROLLER_AUDIT_SCHEMA,
            "case_id": case_id,
            "backward_calls": 1,
            "dtype": "float64",
            "loss_at_origin": float(loss.detach().item()),
            "gradient_by_evidence_id": {
                item: float(gradient[index].item())
                for index, item in enumerate(controller_ids)
            },
            "finite_difference_gradient_by_evidence_id": {
                item: fd_values[index] for index, item in enumerate(controller_ids)
            },
            "finite_difference_max_abs_error": max_fd_error,
            "finite_difference_tolerance": float(
                controller["finite_difference_tolerance"]
            ),
            "q_d": q_d,
            "q_d_preferred_path": q_d_path,
            "q_d_path_alignment": path_sums,
            "q_x": q_x,
            "q_x_selected_path": q_x_path,
            "q_x_seed": POSITIVE_CONTROL_SEED,
            "q_x_seed_provenance": POSITIVE_CONTROL_SEED_PROVENANCE,
            "claim_boundary": [
                "q^D is derived by one local float64 backward pass and does not cross JSON or a hosted provider.",
                "q^X runtime derivation does not read an answer value, q^D, or a provider output; it intentionally reads the frozen P0/P1 equivalence partition.",
                "The q^X seed is the immediate predecessor branch head, but no broader study-design selection independence is claimed because the cases and controller were designed later.",
                "D is constructed and evaluated in the same q^D coordinate system; this is construct-aligned calibration, not independent validation.",
            ],
        }
    )


def _priority_alignment(priority: Mapping[str, int], q: Mapping[str, float]) -> float:
    return math.fsum(
        float(q.get(item, 0.0)) * int(value) for item, value in priority.items()
    )


def compile_schedules(
    case: Mapping[str, Any], controller_audit: Mapping[str, Any]
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    _validate_fingerprint(controller_audit, "controller audit")
    parts = _closure_parts(case)
    evidence_ids = tuple(row["evidence_id"] for row in case["raw_evidence"])
    alternatives = tuple(
        sorted(
            set(parts["paths"]["P0"]["evidence_ids"])
            | set(parts["paths"]["P1"]["evidence_ids"])
        )
    )
    shared = tuple(parts["shared_support"]["evidence_ids"])
    _require(
        len(alternatives) == 4 and len(shared) == 1, "SCHEDULE_FIXTURE_SHAPE_DRIFT"
    )
    q_d = controller_audit["q_d"]

    z_priority = {item: 0 for item in evidence_ids}
    d_priority = {item: 0 for item in evidence_ids}
    d_ranked = sorted(alternatives, key=lambda item: (-float(q_d[item]), item))
    for tier, evidence_id in zip(ACTIVE_TIERS[:2], d_ranked[:2], strict=True):
        d_priority[evidence_id] = tier
    d_priority[shared[0]] = ACTIVE_TIERS[2]
    expected_d_path = set(
        parts["paths"][controller_audit["q_d_preferred_path"]]["evidence_ids"]
    )
    _require(set(d_ranked[:2]) == expected_d_path, "D_TOP_PATH_NOT_EXACT")

    c_priority = {item: d_priority[item] for item in evidence_ids}
    shift = len(alternatives) // 2
    for index, source_id in enumerate(alternatives):
        target_id = alternatives[(index + shift) % len(alternatives)]
        c_priority[target_id] = d_priority[source_id]

    x_priority = {item: 0 for item in evidence_ids}
    x_path = tuple(
        parts["paths"][controller_audit["q_x_selected_path"]]["evidence_ids"]
    )
    # Reverse-ID tie breaking keeps X distinct from the matched C placement
    # without reading q^D or an answer value.
    for tier, evidence_id in zip(
        ACTIVE_TIERS[:2], sorted(x_path, reverse=True), strict=True
    ):
        x_priority[evidence_id] = tier
    x_priority[shared[0]] = ACTIVE_TIERS[2]

    priorities = {"Z": z_priority, "C": c_priority, "D": d_priority, "X": x_priority}
    schedules: dict[str, dict[str, Any]] = {}
    for arm in ARMS:
        schedule = {
            "schema_version": "ebrt-bounded-reinspection-schedule-v0.6.3",
            "operator": OPERATOR,
            "review_budget": REVIEW_BUDGET,
            "no_reordering": arm == "Z",
            "priority_rows": [
                {"evidence_id": item, "priority_tier": priorities[arm][item]}
                for item in evidence_ids
            ],
        }
        schedules[arm] = _seal(schedule)

    active_multisets = {
        arm: sorted(priorities[arm].values()) for arm in ("C", "D", "X")
    }
    d_alignment = _priority_alignment(d_priority, q_d)
    c_alignment = _priority_alignment(c_priority, q_d)
    geometry = _seal(
        {
            "schema_version": "ebrt-actuator-geometry-audit-v0.6.3",
            "case_id": case["case_id"],
            "evidence_ids": list(evidence_ids),
            "eligible_evidence_ids": list(alternatives),
            "protected_common_evidence_ids": list(shared),
            "active_priority_multisets": active_multisets,
            "c_d_eligible_fixed_points": [
                item for item in alternatives if c_priority[item] == d_priority[item]
            ],
            "d_input_alignment": d_alignment,
            "c_input_alignment": c_alignment,
            "d_minus_c_input_alignment": d_alignment - c_alignment,
            "schedule_fingerprints": {
                arm: schedules[arm]["fingerprint_sha256"] for arm in ARMS
            },
            "checks": {
                "z_all_tied_no_reordering": schedules["Z"]["no_reordering"] is True
                and set(z_priority.values()) == {0},
                "active_tier_multisets_match": len(
                    {_canonical_bytes(value) for value in active_multisets.values()}
                )
                == 1,
                "c_d_eligible_derangement": all(
                    c_priority[item] != d_priority[item] for item in alternatives
                ),
                "c_d_provider_schedules_differ": _canonical_bytes(schedules["C"])
                != _canonical_bytes(schedules["D"]),
                "d_input_alignment_exceeds_c": d_alignment
                > c_alignment + FLOAT_TOLERANCE,
                "x_schedule_is_distinct": all(
                    _canonical_bytes(schedules["X"]) != _canonical_bytes(schedules[arm])
                    for arm in ("Z", "C", "D")
                ),
                "protected_common_tier_fixed": all(
                    priorities[arm][shared[0]] == ACTIVE_TIERS[2]
                    for arm in ("C", "D", "X")
                ),
            },
        }
    )
    _require(
        all(geometry["checks"].values()),
        "SCHEDULE_GEOMETRY_FAILED",
        str(case["case_id"]),
    )
    return schedules, geometry


def _recursive_keys(value: Any) -> set[str]:
    if isinstance(value, Mapping):
        output = set(str(key) for key in value)
        for child in value.values():
            output.update(_recursive_keys(child))
        return output
    if isinstance(value, list):
        output: set[str] = set()
        for child in value:
            output.update(_recursive_keys(child))
        return output
    return set()


def _provider_payload(
    case: Mapping[str, Any], schedule: Mapping[str, Any]
) -> dict[str, Any]:
    payload = {
        "schema_version": PROVIDER_INPUT_SCHEMA,
        "checkpoint_id": case["checkpoint_id"],
        "question": case["question"],
        "answer_choices": _clone(case["answer_choices"]),
        "decision_slots": _clone(case["decision_slots"]),
        "all_raw_evidence": _clone(case["raw_evidence"]),
        "allowed_evidence_ids": [row["evidence_id"] for row in case["raw_evidence"]],
        "candidate_scaffold": _clone(case["candidate_scaffold"]),
        "revision_actuator": _clone(dict(schedule)),
        "response_contract": {
            "schema_version": PROVIDER_OUTPUT_SCHEMA,
            "select_only_candidate_edge_ids": True,
            "return_private_reasoning": False,
            "inspection_plan_is_public_receipt_only": True,
        },
    }
    validate_provider_payload(payload, case=case)
    return payload


def validate_provider_payload(
    payload: Mapping[str, Any], *, case: Mapping[str, Any] | None = None
) -> None:
    _require(
        set(payload)
        == {
            "schema_version",
            "checkpoint_id",
            "question",
            "answer_choices",
            "decision_slots",
            "all_raw_evidence",
            "allowed_evidence_ids",
            "candidate_scaffold",
            "revision_actuator",
            "response_contract",
        },
        "PROVIDER_PAYLOAD_SCHEMA_DRIFT",
    )
    _require(
        payload.get("schema_version") == PROVIDER_INPUT_SCHEMA,
        "PROVIDER_INPUT_VERSION_DRIFT",
    )
    raw = payload.get("all_raw_evidence")
    _require(isinstance(raw, list) and raw, "PROVIDER_RAW_EVIDENCE_INVALID")
    evidence_ids = _unique_strings(
        [row.get("evidence_id") for row in raw if isinstance(row, Mapping)],
        "provider.raw_evidence",
    )
    _require(len(evidence_ids) == len(raw), "PROVIDER_RAW_EVIDENCE_INVALID")
    _require(
        tuple(payload.get("allowed_evidence_ids", ())) == evidence_ids,
        "PROVIDER_ALLOWED_IDS_DRIFT",
    )
    schedule = payload.get("revision_actuator")
    _require(isinstance(schedule, Mapping), "PROVIDER_SCHEDULE_INVALID")
    _validate_fingerprint(schedule, "provider schedule")
    _require(
        set(schedule)
        == {
            "schema_version",
            "operator",
            "review_budget",
            "no_reordering",
            "priority_rows",
            "fingerprint_sha256",
        }
        and schedule.get("schema_version")
        == "ebrt-bounded-reinspection-schedule-v0.6.3"
        and schedule.get("operator") == OPERATOR
        and schedule.get("review_budget") == REVIEW_BUDGET
        and isinstance(schedule.get("no_reordering"), bool),
        "PROVIDER_SCHEDULE_INVALID",
    )
    rows = schedule.get("priority_rows")
    _require(
        isinstance(rows, list) and len(rows) == len(evidence_ids),
        "PRIORITY_ROWS_INVALID",
    )
    _require(
        tuple(row.get("evidence_id") for row in rows if isinstance(row, Mapping))
        == evidence_ids,
        "PRIORITY_ROW_ORDER_DRIFT",
    )
    allowed_tiers = {0, *ACTIVE_TIERS}
    _require(
        all(
            isinstance(row, Mapping)
            and set(row) == {"evidence_id", "priority_tier"}
            and type(row["priority_tier"]) is int
            and row["priority_tier"] in allowed_tiers
            for row in rows
        ),
        "PRIORITY_ROW_INVALID",
    )
    if schedule["no_reordering"]:
        _require(
            all(row["priority_tier"] == 0 for row in rows), "ZERO_SCHEDULE_NOT_TIED"
        )
    else:
        _require(
            sorted(row["priority_tier"] for row in rows if row["priority_tier"] > 0)
            == sorted(ACTIVE_TIERS),
            "ACTIVE_TIER_MULTISET_DRIFT",
        )
    leaked = _recursive_keys(payload) & FORBIDDEN_PROVIDER_KEYS
    _require(not leaked, "PROVIDER_PRIVATE_KEY_LEAK", ",".join(sorted(leaked)))
    response_contract = payload.get("response_contract")
    _require(
        response_contract
        == {
            "schema_version": PROVIDER_OUTPUT_SCHEMA,
            "select_only_candidate_edge_ids": True,
            "return_private_reasoning": False,
            "inspection_plan_is_public_receipt_only": True,
        },
        "RESPONSE_CONTRACT_DRIFT",
    )
    if case is not None:
        _require(payload["checkpoint_id"] == case["checkpoint_id"], "CHECKPOINT_DRIFT")
        _require(payload["question"] == case["question"], "QUESTION_DRIFT")
        _require(
            _canonical_bytes(payload["answer_choices"])
            == _canonical_bytes(case["answer_choices"]),
            "ANSWER_CHOICES_DRIFT",
        )
        _require(
            _canonical_bytes(payload["decision_slots"])
            == _canonical_bytes(case["decision_slots"]),
            "DECISION_SLOTS_DRIFT",
        )
        _require(
            _canonical_bytes(raw) == _canonical_bytes(case["raw_evidence"]),
            "RAW_EVIDENCE_DRIFT",
        )
        _require(
            tuple(payload["allowed_evidence_ids"])
            == tuple(row["evidence_id"] for row in case["raw_evidence"]),
            "ALLOWED_EVIDENCE_IDS_DRIFT",
        )
        _require(
            _canonical_bytes(payload["candidate_scaffold"])
            == _canonical_bytes(case["candidate_scaffold"]),
            "SCAFFOLD_DRIFT",
        )


def _without_actuator(payload: Mapping[str, Any]) -> dict[str, Any]:
    output = _clone(dict(payload))
    output.pop("revision_actuator", None)
    return output


def _blind_id(case_id: str, trial_id: int, arm: str) -> str:
    digest = hashlib.sha256(
        f"ebrt-v063-blind:{case_id}:{trial_id}:{arm}".encode("utf-8")
    ).hexdigest()
    return f"req-{digest[:24]}"


def _validate_williams() -> dict[str, Any]:
    rows = [row[3] for row in WILLIAMS_BLOCKS]
    _require(
        all(set(row) == set(ARMS) and len(row) == len(ARMS) for row in rows),
        "WILLIAMS_ROW_INVALID",
    )
    positions = {arm: [row.index(arm) + 1 for row in rows] for arm in ARMS}
    _require(
        all(sorted(value) == [1, 2, 3, 4] for value in positions.values()),
        "WILLIAMS_POSITION_IMBALANCE",
    )
    carryover = [(row[index], row[index + 1]) for row in rows for index in range(3)]
    expected = {(left, right) for left in ARMS for right in ARMS if left != right}
    _require(
        set(carryover) == expected and len(carryover) == len(expected),
        "WILLIAMS_CARRYOVER_IMBALANCE",
    )
    return {
        "positions": positions,
        "carryover_pairs": [list(item) for item in carryover],
    }


def build_projection(fixture: Mapping[str, Any]) -> dict[str, Any]:
    fixture_audit = validate_fixture(fixture)
    cases = _case_map(fixture)
    controllers = {case_id: derive_controller(case) for case_id, case in cases.items()}
    schedules: dict[str, dict[str, dict[str, Any]]] = {}
    geometry: dict[str, dict[str, Any]] = {}
    payload_by_case_arm: dict[tuple[str, str], dict[str, Any]] = {}
    for case_id, case in cases.items():
        case_schedules, case_geometry = compile_schedules(case, controllers[case_id])
        schedules[case_id] = case_schedules
        geometry[case_id] = case_geometry
        for arm in ARMS:
            payload_by_case_arm[(case_id, arm)] = _provider_payload(
                case, case_schedules[arm]
            )
        non_actuator = {
            _canonical_bytes(_without_actuator(payload_by_case_arm[(case_id, arm)]))
            for arm in ARMS
        }
        _require(len(non_actuator) == 1, "NON_ACTUATOR_FIELDS_UNMATCHED", case_id)

    _validate_williams()
    treatment_rows: list[dict[str, Any]] = []
    payload_rows: list[dict[str, Any]] = []
    run_position = 0
    for block_id, case_id, trial_id, order in WILLIAMS_BLOCKS:
        for block_position, arm in enumerate(order, start=1):
            run_position += 1
            blind_id = _blind_id(case_id, trial_id, arm)
            payload = payload_by_case_arm[(case_id, arm)]
            payload_hash = _fingerprint(payload)
            treatment_rows.append(
                {
                    "run_position": run_position,
                    "block_id": block_id,
                    "block_position": block_position,
                    "case_id": case_id,
                    "trial_id": trial_id,
                    "treatment_id": arm,
                    "blinded_request_id": blind_id,
                    "provider_payload_sha256": payload_hash,
                }
            )
            payload_rows.append(
                {
                    "blinded_request_id": blind_id,
                    "provider_payload_sha256": payload_hash,
                    "payload": _clone(payload),
                }
            )
    _require(
        len(treatment_rows) == 16 and len(payload_rows) == 16, "PAYLOAD_COUNT_DRIFT"
    )
    _require(
        len({row["blinded_request_id"] for row in treatment_rows}) == 16,
        "BLINDED_ID_COLLISION",
    )
    return _seal(
        {
            "schema_version": PROJECTION_SCHEMA,
            "status": "READY_NETWORK_ZERO_ACTUATOR_PREFLIGHT",
            "fixture_fingerprint_sha256": _fingerprint(fixture),
            "fixture_audit": fixture_audit,
            "runtime_contract": {
                "model": MODEL,
                "reasoning_effort": REASONING_EFFORT,
                "max_output_tokens": MAX_OUTPUT_TOKENS,
                "timeout_seconds": TIMEOUT_SECONDS,
                "sdk_retries": 0,
                "store": False,
                "previous_response_id": False,
            },
            "williams_schedule": [
                {
                    "block_id": block_id,
                    "case_id": case_id,
                    "trial_id": trial_id,
                    "order": list(order),
                }
                for block_id, case_id, trial_id, order in WILLIAMS_BLOCKS
            ],
            "controller_audits": [
                controllers[case_id] for case_id in sorted(controllers)
            ],
            "geometry_audits": [geometry[case_id] for case_id in sorted(geometry)],
            "public_treatment_key": treatment_rows,
            "provider_payloads": payload_rows,
            "provider_calls": 0,
            "network_calls": 0,
            "claim_boundary": [
                "This is a network-zero construct-aligned actuator preflight, not a hosted result.",
                "The provider sees one explicit schedule and a symmetric candidate scaffold, never q^D, q^X, treatment labels, accepted paths, expected answers, or grades.",
                "All sixteen payloads are built and fingerprinted before any future provider response.",
            ],
        }
    )


def _as_output(
    value: ActuatorCalibrationOutput | Mapping[str, Any],
) -> ActuatorCalibrationOutput:
    if isinstance(value, ActuatorCalibrationOutput):
        return value
    try:
        return ActuatorCalibrationOutput.model_validate(value)
    except ValidationError as error:
        raise ActuatorCalibrationError("OUTPUT_SCHEMA_INVALID") from error


def _schedule_review_order(schedule: Mapping[str, Any]) -> tuple[str, ...]:
    rows = schedule["priority_rows"]
    indexed = {row["evidence_id"]: index for index, row in enumerate(rows)}
    ordered = sorted(
        rows,
        key=lambda row: (-int(row["priority_tier"]), indexed[row["evidence_id"]]),
    )
    return tuple(row["evidence_id"] for row in ordered[:REVIEW_BUDGET])


def _acyclic_selected_edges(
    selected: Sequence[str], edges: Mapping[str, Mapping[str, Any]]
) -> bool:
    graph: dict[str, list[str]] = {}
    for edge_id in selected:
        edge = edges[edge_id]
        if edge["relation_type"] == "invalidates":
            continue
        graph.setdefault(edge["source_node_id"], []).append(edge["target_node_id"])
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return False
        if node in visited:
            return True
        visiting.add(node)
        for target in graph.get(node, []):
            if not visit(target):
                return False
        visiting.remove(node)
        visited.add(node)
        return True

    return all(visit(node) for node in graph)


def compile_output(
    output: ActuatorCalibrationOutput | Mapping[str, Any],
    *,
    payload: Mapping[str, Any],
    case: Mapping[str, Any],
) -> dict[str, Any]:
    validate_provider_payload(payload, case=case)
    parsed = _as_output(output)
    _require(
        parsed.checkpoint_id == payload["checkpoint_id"], "OUTPUT_CHECKPOINT_DRIFT"
    )
    _require(
        parsed.current_answer in payload["answer_choices"], "OUTPUT_ANSWER_NOT_ALLOWED"
    )
    evidence_ids = tuple(payload["allowed_evidence_ids"])
    reviewed = tuple(parsed.inspection_plan.reviewed_evidence_ids)
    _require(len(reviewed) == len(set(reviewed)), "INSPECTION_PLAN_DUPLICATE")
    _require(set(reviewed).issubset(evidence_ids), "INSPECTION_PLAN_UNKNOWN_EVIDENCE")

    slots = {
        row["slot_id"]: tuple(row["allowed_values"])
        for row in payload["decision_slots"]
    }
    emitted_slots = {row.slot_id: row.value for row in parsed.decision_slots}
    _require(len(emitted_slots) == len(parsed.decision_slots), "OUTPUT_SLOT_DUPLICATE")
    _require(set(emitted_slots) == set(slots), "OUTPUT_SLOT_SET_DRIFT")
    _require(
        all(emitted_slots[slot_id] in allowed for slot_id, allowed in slots.items()),
        "OUTPUT_SLOT_VALUE_NOT_ALLOWED",
    )

    selected = tuple(parsed.selected_candidate_edge_ids)
    _require(len(selected) == len(set(selected)), "SELECTED_EDGE_DUPLICATE")
    edges = _edge_map(case)
    _require(set(selected).issubset(edges), "SELECTED_EDGE_UNKNOWN")
    _require(_acyclic_selected_edges(selected, edges), "SELECTED_GRAPH_CYCLIC")
    parts = _closure_parts(case)
    node_types = _node_type_map(case)
    active_necessary = _evidence_reaching_target(
        selected,
        edges=edges,
        node_types=node_types,
        target_node_id=parts["primary_target_node_id"],
    )
    valid_active_closures = {
        path_id: tuple(
            sorted(
                set(parts["paths"][path_id]["evidence_ids"])
                | set(parts["shared_support"]["evidence_ids"])
            )
        )
        for path_id in ("P0", "P1")
    }
    matches = [
        path_id
        for path_id, expected in valid_active_closures.items()
        if active_necessary == expected
    ]
    _require(len(matches) == 1, "EXACT_ONE_CLOSURE_FAILED")
    path_id = matches[0]
    invalidated = parts["invalidation"]["target_evidence_id"]
    _require(invalidated not in active_necessary, "INVALIDATED_EVIDENCE_ACTIVE")
    stable_ids = _evidence_reaching_target(
        selected,
        edges=edges,
        node_types=node_types,
        target_node_id=parts["stable_target_node_id"],
    )
    _require(
        stable_ids == tuple(sorted(parts["stable_support"]["evidence_ids"])),
        "GRAPH_DERIVED_STABLE_SUPPORT_DRIFT",
    )
    selected_invalidation_edges = [
        edge_id
        for edge_id in selected
        if edges[edge_id]["relation_type"] == "invalidates"
    ]
    _require(
        selected_invalidation_edges == [parts["invalidation"]["edge_id"]],
        "GRAPH_DERIVED_INVALIDATION_DRIFT",
    )
    selected_support_edges = {
        edge_id
        for edge_id in selected
        if edges[edge_id]["relation_type"] in {"supports", "depends_on"}
    }
    expected_support_edge_count = (
        len(parts["paths"][path_id]["edge_ids"])
        + len(parts["shared_support"]["edge_ids"])
        + len(parts["stable_support"]["edge_ids"])
    )
    _require(
        len(selected_support_edges) == expected_support_edge_count,
        "SELECTED_GRAPH_NOT_MINIMAL",
    )
    used_support_edges = _support_edges_reaching_targets(
        selected,
        edges=edges,
        target_node_ids=(
            parts["primary_target_node_id"],
            parts["stable_target_node_id"],
        ),
    )
    _require(
        used_support_edges == selected_support_edges,
        "SELECTED_GRAPH_HAS_IRRELEVANT_EDGE",
    )
    schedule = payload["revision_actuator"]
    expected_review = _schedule_review_order(schedule)
    adherence: bool | None = None
    if schedule["no_reordering"] is False:
        adherence = reviewed == expected_review
    return _seal(
        {
            "schema_version": COMPILED_SCHEMA,
            "checkpoint_id": parsed.checkpoint_id,
            "current_answer": parsed.current_answer,
            "decision_slots": emitted_slots,
            "selected_candidate_edge_ids": list(selected),
            "selected_path_id": path_id,
            "active_necessary_support_closure": list(active_necessary),
            "invalidated_evidence_ids": [invalidated],
            "stable_support_evidence_ids": list(stable_ids),
            "inspection_plan": {
                "reviewed_evidence_ids": list(reviewed),
                "expected_reviewed_evidence_ids": list(expected_review),
                "adherence": adherence,
                "scored_as_downstream": False,
            },
            "provider_output_fingerprint_sha256": _fingerprint(
                parsed.model_dump(mode="json")
            ),
        }
    )


def alignment(compiled: Mapping[str, Any], q: Mapping[str, float]) -> float:
    _validate_fingerprint(compiled, "compiled output")
    # Deliberately reads only the locally compiled active closure.  The public
    # inspection receipt and every free-text field are outside this function.
    return math.fsum(
        float(q.get(item, 0.0)) for item in compiled["active_necessary_support_closure"]
    )


def _gold_map(gold: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    _require(
        set(gold) == {"schema_version", "status", "cases", "claim_boundary"},
        "GOLD_ROOT_SCHEMA_DRIFT",
    )
    _require(gold.get("schema_version") == GOLD_SCHEMA, "GOLD_SCHEMA_DRIFT")
    _require(gold.get("status") == "LOCKED_POST_CALL_GRADING_ONLY", "GOLD_STATUS_DRIFT")
    _require(
        bool(_unique_strings(gold.get("claim_boundary"), "gold.claim_boundary")),
        "GOLD_CLAIM_BOUNDARY_INVALID",
    )
    rows = gold.get("cases")
    _require(isinstance(rows, list) and len(rows) == 2, "GOLD_CASE_SET_INVALID")
    output: dict[str, dict[str, Any]] = {}
    for row in rows:
        _require(
            isinstance(row, dict)
            and set(row)
            == {
                "case_id",
                "answer",
                "slot_values",
                "valid_necessary_support_closures",
                "invalidation_edges",
                "stable_support_evidence_ids",
            },
            "GOLD_CASE_INVALID",
        )
        case_id = row.get("case_id")
        _require(
            isinstance(case_id, str) and case_id not in output, "GOLD_CASE_ID_INVALID"
        )
        _require(
            isinstance(row.get("answer"), str)
            and isinstance(row.get("slot_values"), dict)
            and set(row["slot_values"]) == {"primary_decision", "stable_constraint"}
            and isinstance(row.get("valid_necessary_support_closures"), dict)
            and set(row["valid_necessary_support_closures"]) == {"P0", "P1"}
            and isinstance(row.get("invalidation_edges"), list)
            and len(row["invalidation_edges"]) == 1
            and isinstance(row.get("stable_support_evidence_ids"), list),
            "GOLD_CASE_SHAPE_INVALID",
            str(case_id),
        )
        for path_id, closure in row["valid_necessary_support_closures"].items():
            _require(
                len(_unique_strings(closure, f"gold.{case_id}.{path_id}")) == 3,
                "GOLD_CLOSURE_INVALID",
                str(case_id),
            )
        invalidation = row["invalidation_edges"][0]
        _require(
            isinstance(invalidation, Mapping)
            and set(invalidation) == {"source_evidence_id", "target_evidence_id"}
            and all(
                isinstance(value, str) and value for value in invalidation.values()
            ),
            "GOLD_INVALIDATION_INVALID",
            str(case_id),
        )
        _require(
            bool(
                _unique_strings(
                    row["stable_support_evidence_ids"],
                    f"gold.{case_id}.stable_support_evidence_ids",
                )
            ),
            "GOLD_STABLE_SUPPORT_INVALID",
            str(case_id),
        )
        output[case_id] = row
    _require(
        set(output) == {"relay_bay_revision_a", "coolant_loop_revision_b"},
        "GOLD_CASE_SET_DRIFT",
    )
    return output


def grade_quality(
    output: Mapping[str, Any], compiled: Mapping[str, Any], gold_case: Mapping[str, Any]
) -> dict[str, Any]:
    _validate_fingerprint(compiled, "compiled output")
    slots = {row["slot_id"]: row["value"] for row in output["decision_slots"]}
    valid_closures = {
        tuple(sorted(value))
        for value in gold_case["valid_necessary_support_closures"].values()
    }
    checks = {
        "answer": output["current_answer"] == gold_case["answer"],
        "decision_slots": slots == gold_case["slot_values"],
        "exact_one_valid_closure": tuple(compiled["active_necessary_support_closure"])
        in valid_closures,
        "invalidation": compiled["invalidated_evidence_ids"]
        == [gold_case["invalidation_edges"][0]["target_evidence_id"]],
        "stable_preservation": compiled["stable_support_evidence_ids"]
        == gold_case["stable_support_evidence_ids"],
    }
    return _seal(
        {
            "schema_version": "ebrt-actuator-calibration-quality-grade-v0.6.3",
            "case_id": gold_case["case_id"],
            "status": "PASS" if all(checks.values()) else "FAIL",
            "checks": checks,
            "secondary_quality_only": True,
        }
    )


def _conformance_output(
    *,
    path_id: str,
    case: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    parts = _closure_parts(case)
    _require(path_id in {"P0", "P1"}, "CONFORMANCE_PATH_INVALID")
    selected = list(parts["paths"][path_id]["edge_ids"])
    selected += list(parts["shared_support"]["edge_ids"])
    selected += list(parts["stable_support"]["edge_ids"])
    selected.append(parts["invalidation"]["edge_id"])
    schedule = payload["revision_actuator"]
    reviewed = _schedule_review_order(schedule)
    return {
        "schema_version": PROVIDER_OUTPUT_SCHEMA,
        "checkpoint_id": payload["checkpoint_id"],
        "current_answer": payload["answer_choices"][0],
        "decision_slots": [
            {"slot_id": row["slot_id"], "value": row["allowed_values"][0]}
            for row in payload["decision_slots"]
        ],
        "inspection_plan": {
            "operator": OPERATOR,
            "reviewed_evidence_ids": list(reviewed),
        },
        "selected_candidate_edge_ids": selected,
    }


def _payloads_by_treatment(
    projection: Mapping[str, Any],
) -> dict[tuple[str, int, str], Mapping[str, Any]]:
    payload_by_blind = {
        row["blinded_request_id"]: row["payload"]
        for row in projection["provider_payloads"]
    }
    return {
        (row["case_id"], row["trial_id"], row["treatment_id"]): payload_by_blind[
            row["blinded_request_id"]
        ]
        for row in projection["public_treatment_key"]
    }


def alignment_arithmetic_audit(
    projection: Mapping[str, Any], fixture: Mapping[str, Any]
) -> dict[str, Any]:
    """Verify both valid closures without constructing a hosted-effect result."""

    cases = _case_map(fixture)
    payloads, controllers = _projection_maps(projection)
    rows: list[dict[str, Any]] = []
    roundtrip_checks: list[bool] = []
    arithmetic_checks: list[bool] = []
    for case_id in sorted(cases):
        case = cases[case_id]
        payload = payloads[(case_id, 1, "Z")]
        controller = controllers[case_id]
        for path_id in ("P0", "P1"):
            output = _conformance_output(path_id=path_id, case=case, payload=payload)
            parsed = ActuatorCalibrationOutput.model_validate(output)
            roundtrip = parsed.model_dump(mode="json") == output
            compiled = compile_output(output, payload=payload, case=case)
            observed = {
                "q_d": alignment(compiled, controller["q_d"]),
                "q_x": alignment(compiled, controller["q_x"]),
            }
            active = compiled["active_necessary_support_closure"]
            expected = {
                name: math.fsum(float(q.get(item, 0.0)) for item in active)
                for name, q in (("q_d", controller["q_d"]), ("q_x", controller["q_x"]))
            }
            arithmetic = all(
                abs(observed[name] - expected[name]) <= FLOAT_TOLERANCE
                for name in observed
            )
            roundtrip_checks.append(roundtrip)
            arithmetic_checks.append(arithmetic)
            rows.append(
                {
                    "case_id": case_id,
                    "path_id": path_id,
                    "active_necessary_support_closure": active,
                    "observed_alignment": observed,
                    "expected_alignment": expected,
                    "output_contract_roundtrip": roundtrip,
                    "arithmetic_exact": arithmetic,
                }
            )
    checks = {
        "all_four_path_coordinates_exercised": len(rows) == 4,
        "alignment_arithmetic_exact": all(arithmetic_checks),
        "output_contract_roundtrip": all(roundtrip_checks),
    }
    return _seal(
        {
            "schema_version": "ebrt-actuator-alignment-arithmetic-audit-v0.6.3",
            "status": "PASS" if all(checks.values()) else "FAIL",
            "checks": checks,
            "rows": rows,
            "claim_boundary": [
                "This verifies compiler and alignment arithmetic for both frozen valid closures.",
                "It does not predict or simulate which closure a hosted provider will emit.",
            ],
        }
    )


@contextmanager
def _network_denied() -> Iterator[dict[str, int]]:
    """Deny and count common socket entry points during network-zero tests."""

    counter = {"attempts": 0}

    def blocked(*_args: Any, **_kwargs: Any) -> Any:
        counter["attempts"] += 1
        raise RuntimeError("NETWORK_DISABLED_BY_V063_SELF_TEST")

    with (
        mock.patch.object(socket.socket, "connect", new=blocked),
        mock.patch.object(socket.socket, "connect_ex", new=blocked),
        mock.patch.object(socket, "create_connection", new=blocked),
        mock.patch.object(socket, "getaddrinfo", new=blocked),
    ):
        yield counter


def _expect_rejected(operation: Any, expected_reason: str) -> dict[str, Any]:
    try:
        operation()
    except ActuatorCalibrationError as error:
        _require(
            error.reason_code == expected_reason,
            "UNEXPECTED_REJECTION_REASON",
            f"expected={expected_reason},observed={error.reason_code}",
        )
        return {"rejected": True, "reason_code": error.reason_code}
    raise ActuatorCalibrationError("ADVERSARIAL_INPUT_ACCEPTED", expected_reason)


def _projection_maps(
    projection: Mapping[str, Any],
) -> tuple[
    dict[tuple[str, int, str], Mapping[str, Any]],
    dict[str, Mapping[str, Any]],
]:
    _validate_fingerprint(projection, "projection")
    payloads = _payloads_by_treatment(projection)
    controllers = {row["case_id"]: row for row in projection["controller_audits"]}
    return payloads, controllers


def _adversarial_contract_audit(
    projection: Mapping[str, Any], fixture: Mapping[str, Any]
) -> dict[str, Any]:
    cases = _case_map(fixture)
    payloads, controllers = _projection_maps(projection)
    case_id = "relay_bay_revision_a"
    trial_id = 1
    case = cases[case_id]
    payload = payloads[(case_id, trial_id, "D")]
    base_output = _conformance_output(path_id="P0", case=case, payload=payload)
    parts = _closure_parts(case)
    common = list(parts["shared_support"]["edge_ids"])
    common += list(parts["stable_support"]["edge_ids"])
    common.append(parts["invalidation"]["edge_id"])

    union_output = _clone(base_output)
    union_output["selected_candidate_edge_ids"] = (
        list(parts["paths"]["P0"]["edge_ids"])
        + list(parts["paths"]["P1"]["edge_ids"])
        + common
    )
    union_attack = _expect_rejected(
        lambda: compile_output(union_output, payload=payload, case=case),
        "EXACT_ONE_CLOSURE_FAILED",
    )

    isomorphic_output = _clone(base_output)
    isomorphic_output["selected_candidate_edge_ids"] = [
        "C12",
        "C13",
        "C06",
        *common,
    ]
    isomorphic_compiled = compile_output(isomorphic_output, payload=payload, case=case)
    isomorphic_accepted = isomorphic_compiled[
        "selected_path_id"
    ] == "P0" and isomorphic_compiled["active_necessary_support_closure"] == [
        "E1",
        "E2",
        "E6",
    ]

    mixed_output = _clone(base_output)
    mixed_output["selected_candidate_edge_ids"] = ["C01", "C14", "C03", *common]
    mixed_attack = _expect_rejected(
        lambda: compile_output(mixed_output, payload=payload, case=case),
        "EXACT_ONE_CLOSURE_FAILED",
    )

    compiled_before = compile_output(base_output, payload=payload, case=case)
    receipt_mutation = _clone(base_output)
    original_review = receipt_mutation["inspection_plan"]["reviewed_evidence_ids"]
    replacement_review = [
        evidence_id
        for evidence_id in payload["allowed_evidence_ids"]
        if evidence_id not in original_review
    ][:REVIEW_BUDGET]
    _require(
        len(replacement_review) == REVIEW_BUDGET,
        "RECEIPT_MUTATION_FIXTURE_INVALID",
    )
    receipt_mutation["inspection_plan"]["reviewed_evidence_ids"] = replacement_review
    compiled_after = compile_output(receipt_mutation, payload=payload, case=case)
    receipt_excluded = (
        alignment(compiled_before, controllers[case_id]["q_d"])
        == alignment(compiled_after, controllers[case_id]["q_d"])
        and compiled_after["inspection_plan"]["adherence"] is False
    )

    leaked_payload = _clone(payload)
    leaked_payload["response_contract"]["treatment_id"] = "D"
    leakage_attack = _expect_rejected(
        lambda: validate_provider_payload(leaked_payload, case=case),
        "PROVIDER_PRIVATE_KEY_LEAK",
    )
    duplicate_json_attack = _expect_rejected(
        lambda: _strict_json_bytes(b'{"a":1,"a":2}', label="duplicate-attack"),
        "DUPLICATE_JSON_KEY",
    )
    nonfinite_json_attack = _expect_rejected(
        lambda: _strict_json_bytes(b'{"a":NaN}', label="nonfinite-attack"),
        "NONFINITE_JSON",
    )

    answer_adjacent_scaffold = _clone(fixture)
    answer_adjacent_scaffold["cases"][0]["candidate_scaffold"]["accepted_edge_ids"] = [
        "C01"
    ]
    scaffold_leak_attack = _expect_rejected(
        lambda: validate_fixture(answer_adjacent_scaffold),
        "SCAFFOLD_INVALID",
    )

    question_drift_payload = _clone(payload)
    question_drift_payload["question"] = "Choose any answer."
    question_drift_attack = _expect_rejected(
        lambda: validate_provider_payload(question_drift_payload, case=case),
        "QUESTION_DRIFT",
    )

    empty_bindings_fixture = _clone(fixture)
    empty_bindings_fixture["cases"][0]["candidate_scaffold"]["target_bindings"] = []
    empty_bindings_attack = _expect_rejected(
        lambda: validate_fixture(empty_bindings_fixture),
        "TARGET_BINDINGS_INVALID",
    )

    unmanaged_evidence_fixture = _clone(fixture)
    unmanaged_case = unmanaged_evidence_fixture["cases"][0]
    unmanaged_case["raw_evidence"].append(
        {"evidence_id": "E8", "text": "Unmanaged distractor evidence."}
    )
    unmanaged_case["candidate_scaffold"]["nodes"].append(
        {"node_id": "E8", "node_type": "evidence"}
    )
    unmanaged_evidence_attack = _expect_rejected(
        lambda: validate_fixture(unmanaged_evidence_fixture),
        "UNMANAGED_EVIDENCE_PRESENT",
    )

    topology_drift_fixture = _clone(fixture)
    candidate_edges = topology_drift_fixture["cases"][0]["candidate_scaffold"][
        "candidate_edges"
    ]
    edge_by_id = {row["edge_id"]: row for row in candidate_edges}
    edge_by_id["C01"]["source_node_id"] = "E3"
    edge_by_id["C14"]["source_node_id"] = "E1"
    topology_drift_attack = _expect_rejected(
        lambda: validate_fixture(topology_drift_fixture),
        "PATH_GRAPH_EVIDENCE_DRIFT",
    )
    checks = {
        "union_closure_rejected": union_attack["rejected"],
        "mixed_cross_closure_rejected": mixed_attack["rejected"],
        "graph_isomorphic_closure_accepted": isomorphic_accepted,
        "inspection_receipt_excluded": receipt_excluded,
        "private_provider_key_rejected": leakage_attack["rejected"],
        "duplicate_json_key_rejected": duplicate_json_attack["rejected"],
        "nonfinite_json_rejected": nonfinite_json_attack["rejected"],
        "answer_adjacent_scaffold_key_rejected": scaffold_leak_attack["rejected"],
        "question_drift_rejected": question_drift_attack["rejected"],
        "empty_target_bindings_rejected": empty_bindings_attack["rejected"],
        "unmanaged_evidence_rejected": unmanaged_evidence_attack["rejected"],
        "contract_edge_topology_drift_rejected": topology_drift_attack["rejected"],
    }
    return _seal(
        {
            "schema_version": "ebrt-actuator-calibration-adversarial-audit-v0.6.3",
            "status": "PASS" if all(checks.values()) else "FAIL",
            "checks": checks,
            "rejections": {
                "union": union_attack,
                "mixed_cross": mixed_attack,
                "private_key": leakage_attack,
                "duplicate_json": duplicate_json_attack,
                "nonfinite_json": nonfinite_json_attack,
                "answer_adjacent_scaffold": scaffold_leak_attack,
                "question_drift": question_drift_attack,
                "empty_target_bindings": empty_bindings_attack,
                "unmanaged_evidence": unmanaged_evidence_attack,
                "contract_edge_topology_drift": topology_drift_attack,
            },
            "graph_isomorphic_conformance": {
                "selected_candidate_edge_ids": isomorphic_output[
                    "selected_candidate_edge_ids"
                ],
                "compiled": isomorphic_compiled,
            },
            "receipt_mutation": {
                "before_reviewed_evidence_ids": original_review,
                "after_reviewed_evidence_ids": replacement_review,
                "alignment_before": alignment(
                    compiled_before, controllers[case_id]["q_d"]
                ),
                "alignment_after": alignment(
                    compiled_after, controllers[case_id]["q_d"]
                ),
                "after_adherence": compiled_after["inspection_plan"]["adherence"],
            },
        }
    )


def _hard_gates(
    *,
    projection: Mapping[str, Any],
    second_projection: Mapping[str, Any],
    fixture: Mapping[str, Any],
    arithmetic: Mapping[str, Any],
    adversarial: Mapping[str, Any],
    canonical_artifact_directory_exact: bool,
    network_attempts: int,
) -> dict[str, bool]:
    fixture_audit = projection["fixture_audit"]
    controllers = projection["controller_audits"]
    geometry = projection["geometry_audits"]
    cases = _case_map(fixture)
    alternatives_by_case = {
        case_id: sorted(
            set(_closure_parts(case)["paths"]["P0"]["evidence_ids"])
            | set(_closure_parts(case)["paths"]["P1"]["evidence_ids"])
        )
        for case_id, case in cases.items()
    }
    payloads = projection["provider_payloads"]
    non_actuator_matched = all(
        len(
            {
                _canonical_bytes(
                    _without_actuator(
                        _payloads_by_treatment(projection)[(case_id, trial_id, arm)]
                    )
                )
                for arm in ARMS
            }
        )
        == 1
        for case_id, trial_id in {
            (row["case_id"], row["trial_id"])
            for row in projection["public_treatment_key"]
        }
    )
    provider_payloads_valid = True
    try:
        for row in payloads:
            validate_provider_payload(row["payload"])
    except ActuatorCalibrationError:
        provider_payloads_valid = False
    q_unit = True
    for controller in controllers:
        alternatives = alternatives_by_case[controller["case_id"]]
        q_unit = q_unit and all(
            abs(math.fsum(abs(float(q[item])) for item in alternatives) - 1.0)
            <= FLOAT_TOLERANCE
            for q in (controller["q_d"], controller["q_x"])
        )
    william = _validate_williams()
    gates = {
        "strict_fixture_contract": set(fixture_audit["case_ids"]) == set(cases)
        and all(
            adversarial["checks"][key]
            for key in (
                "duplicate_json_key_rejected",
                "nonfinite_json_rejected",
                "answer_adjacent_scaffold_key_rejected",
                "empty_target_bindings_rejected",
                "unmanaged_evidence_rejected",
                "contract_edge_topology_drift_rejected",
            )
        ),
        "symmetric_candidate_universe": all(
            fixture_audit["symmetric_candidate_universe_by_case"].values()
        ),
        "real_float64_backward": all(
            row["backward_calls"] == 1 and row["dtype"] == "float64"
            for row in controllers
        ),
        "central_finite_difference_agreement": all(
            row["finite_difference_max_abs_error"] <= row["finite_difference_tolerance"]
            for row in controllers
        ),
        "unit_l1_polarities": q_unit,
        "opposite_case_positive_controls": {
            row["q_x_selected_path"] for row in controllers
        }
        == {"P0", "P1"},
        "z_true_no_reordering": all(
            row["checks"]["z_all_tied_no_reordering"] for row in geometry
        ),
        "matched_schedule_geometry": all(
            row["checks"]["active_tier_multisets_match"]
            and row["checks"]["protected_common_tier_fixed"]
            for row in geometry
        ),
        "c_eligible_derangement": all(
            row["checks"]["c_d_eligible_derangement"] for row in geometry
        ),
        "d_input_alignment_exceeds_c": all(
            row["checks"]["d_input_alignment_exceeds_c"] for row in geometry
        ),
        "provider_payloads_leak_free": provider_payloads_valid
        and adversarial["checks"]["private_provider_key_rejected"]
        and adversarial["checks"]["question_drift_rejected"]
        and all(
            not (_recursive_keys(row["payload"]) & FORBIDDEN_PROVIDER_KEYS)
            for row in payloads
        ),
        "non_actuator_payload_fields_matched": non_actuator_matched,
        "williams_four_block_balance": len(william["carryover_pairs"]) == 12,
        "sixteen_payloads_presealed": len(payloads) == 16
        and all(
            row["provider_payload_sha256"] == _fingerprint(row["payload"])
            for row in payloads
        ),
        "exact_one_closure_enforced": adversarial["checks"]["union_closure_rejected"]
        and adversarial["checks"]["mixed_cross_closure_rejected"]
        and adversarial["checks"]["graph_isomorphic_closure_accepted"],
        "inspection_receipt_excluded_from_alignment": adversarial["checks"][
            "inspection_receipt_excluded"
        ],
        "p0_p1_alignment_arithmetic_exact": arithmetic["checks"][
            "all_four_path_coordinates_exercised"
        ]
        and arithmetic["checks"]["alignment_arithmetic_exact"],
        "output_contract_roundtrip": arithmetic["checks"]["output_contract_roundtrip"],
        "deterministic_double_projection": _canonical_bytes(projection)
        == _canonical_bytes(second_projection),
        "canonical_artifact_directory_exact": canonical_artifact_directory_exact,
        "network_calls_zero": network_attempts == 0
        and projection["network_calls"] == 0
        and projection["provider_calls"] == 0,
    }
    _require(set(gates) == set(HARD_GATE_IDS), "HARD_GATE_KEYSET_DRIFT")
    return gates


def run_self_test() -> dict[str, Any]:
    fixture = _strict_load(FIXTURE_PATH)
    with _network_denied() as network_counter:
        projection = build_projection(fixture)
        second_projection = build_projection(_strict_load(FIXTURE_PATH))
        arithmetic = alignment_arithmetic_audit(projection, fixture)
        adversarial = _adversarial_contract_audit(projection, fixture)
    with tempfile.TemporaryDirectory(prefix="ebrt-v063-stale-artifact-") as directory:
        stale_directory = Path(directory)
        (stale_directory / "stale.json").write_text("{}\n", encoding="utf-8")
        stale_entry_attack = _expect_rejected(
            lambda: _validate_artifact_directory_entries(
                stale_directory, require_complete=False
            ),
            "CANONICAL_ARTIFACT_STALE_ENTRY",
        )
    canonical_artifact_directory_exact = stale_entry_attack["rejected"]
    gates = _hard_gates(
        projection=projection,
        second_projection=second_projection,
        fixture=fixture,
        arithmetic=arithmetic,
        adversarial=adversarial,
        canonical_artifact_directory_exact=canonical_artifact_directory_exact,
        network_attempts=network_counter["attempts"],
    )
    _require(all(gates.values()), "HARD_GATE_FAILED")

    # Gold is intentionally loaded only after every fixed local attempt and
    # contract attack above has completed.
    gold = _gold_map(_strict_load(GOLD_PATH))
    cases = _case_map(fixture)
    payloads, _controllers = _projection_maps(projection)
    secondary_grades: list[dict[str, Any]] = []
    for case_id in sorted(cases):
        payload = payloads[(case_id, 1, "D")]
        output = _conformance_output(
            path_id="P0",
            case=cases[case_id],
            payload=payload,
        )
        compiled = compile_output(output, payload=payload, case=cases[case_id])
        secondary_grades.append(grade_quality(output, compiled, gold[case_id]))
    _require(
        all(row["status"] == "PASS" for row in secondary_grades),
        "SECONDARY_SYNTHETIC_GRADE_FAILED",
    )
    return _seal(
        {
            "schema_version": SELF_TEST_SCHEMA,
            "status": "PASS_NETWORK_ZERO",
            "hard_gates": gates,
            "hard_gate_ids": list(HARD_GATE_IDS),
            "provider_calls": 0,
            "network_calls": network_counter["attempts"],
            "projection_fingerprint_sha256": projection["fingerprint_sha256"],
            "fixture_fingerprint_sha256": _fingerprint(fixture),
            "alignment_arithmetic_audit": arithmetic,
            "adversarial_contract_audit": adversarial,
            "artifact_directory_adversarial_audit": {
                "stale_entry_rejected": canonical_artifact_directory_exact,
                "reason_code": stale_entry_attack["reason_code"],
            },
            "secondary_conformance_quality_grades": secondary_grades,
            "claim_boundary": [
                "PASS_NETWORK_ZERO proves local contracts and endpoint plumbing only.",
                "No synthetic arm-effect delta is constructed; conformance outputs only exercise parser and arithmetic contracts.",
                "No result here supports hidden-state editing, causal superiority, or general reasoning improvement.",
            ],
        }
    )


def build_preflight() -> dict[str, Any]:
    lock = validate_policy_lock()
    fixture = _strict_load(FIXTURE_PATH)
    with _network_denied() as network_counter:
        projection = build_projection(fixture)
    _require(network_counter["attempts"] == 0, "PREFLIGHT_NETWORK_ATTEMPTED")
    self_test = run_self_test()
    _require(
        projection["fingerprint_sha256"] == self_test["projection_fingerprint_sha256"],
        "SELF_TEST_PROJECTION_MISMATCH",
    )
    return _seal(
        {
            "schema_version": "ebrt-actuator-calibration-preflight-v0.6.3",
            "status": "READY_ZERO_CALL_PREFLIGHT_ONLY",
            "projection": projection,
            "self_test": self_test,
            "policy_lock_fingerprint_sha256": lock["fingerprint_sha256"],
            "provider_calls": 0,
            "network_calls": 0,
            "live_execution_authorized": False,
            "handoff_status": "AWAIT_EXPLICIT_LIVE_AUTHORIZATION",
            "claim_boundary": [
                "This artifact stops before any hosted call.",
                "A future live block requires a separately frozen policy lock and explicit execution authorization.",
            ],
        }
    )


def _file_receipt(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": str(path.relative_to(ROOT)),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def policy_lock_material() -> dict[str, Any]:
    sources = {
        "core": _file_receipt(ROOT / "actuator_calibration_v0_6_3.py"),
        "fixture": _file_receipt(FIXTURE_PATH),
        "post_call_gold": _file_receipt(GOLD_PATH),
        "requirements": _file_receipt(ROOT / "requirements.txt"),
        "protocol_note": _file_receipt(
            ROOT / "docs" / "RND_ACTUATOR_CALIBRATION_V0_6_3.md"
        ),
    }
    return _seal(
        {
            "schema_version": "ebrt-actuator-calibration-policy-lock-v0.6.3",
            "status": "LOCKED_NETWORK_ZERO_PREFLIGHT_NO_LIVE_AUTHORIZATION",
            "sources": sources,
            "runtime_contract": {
                "model": MODEL,
                "reasoning_effort": REASONING_EFFORT,
                "max_output_tokens": MAX_OUTPUT_TOKENS,
                "timeout_seconds": TIMEOUT_SECONDS,
                "sdk_retries": 0,
                "store": False,
                "previous_response_id": False,
                "provider_calls_authorized": 0,
                "python": platform.python_version(),
                "machine": platform.machine(),
                "torch": torch.__version__,
                "pydantic": package_version("pydantic"),
            },
            "protocol": {
                "operator": OPERATOR,
                "positive_control_seed": POSITIVE_CONTROL_SEED,
                "positive_control_seed_provenance": POSITIVE_CONTROL_SEED_PROVENANCE,
                "arms": list(ARMS),
                "review_budget": REVIEW_BUDGET,
                "active_priority_tiers": list(ACTIVE_TIERS),
                "williams_blocks": [
                    {
                        "block_id": block_id,
                        "case_id": case_id,
                        "trial_id": trial_id,
                        "order": list(order),
                    }
                    for block_id, case_id, trial_id, order in WILLIAMS_BLOCKS
                ],
                "provider_payload_count": 16,
                "hard_gate_ids": list(HARD_GATE_IDS),
                "primary_future_endpoints": {
                    "positive_control": "delta_XZ under q_x; aggregate > 0 and positive in at least 3 of 4 complete blocks",
                    "gradient_placement": "delta_DC under q_d; aggregate > 0 and positive in at least 3 of 4 complete blocks",
                    "schedule_receipt_scored_as_downstream": False,
                    "quality_status": "secondary_only",
                },
                "terminal_statuses": [
                    "ZERO_CALL_PREFLIGHT_STOP",
                    "INCOMPLETE_NOT_ASSESSED",
                    "STOP_OUTPUT_CONTRACT",
                    "STOP_CHANNEL_ADHERENCE_NULL",
                    "STOP_ACTUATOR_ECHO_ONLY",
                    "STOP_GRADIENT_PLACEMENT_NULL",
                    "PROMOTE_V0_6_4_ACTUATOR_GATE",
                ],
            },
            "artifact": {
                "directory": str(DEFAULT_ARTIFACT_DIR.relative_to(ROOT)),
                "files": [
                    "projection_bundle.json",
                    "controller_audit.json",
                    "self_test.json",
                    "manifest.json",
                ],
                "provider_calls": 0,
                "network_calls": 0,
            },
            "canonicalization": {
                "encoding": "utf-8",
                "sort_keys": True,
                "ensure_ascii": False,
                "allow_nan": False,
                "separators": [",", ":"],
                "trailing_newline": True,
            },
            "claim_boundary": [
                "This lock authorizes only deterministic network-zero preflight construction.",
                "The local float64 backward pass ends before JSON and no gradient crosses a hosted provider.",
                "Both exact valid closures are conformance coordinates, not simulated hosted outputs.",
                "No synthetic X-Z or D-C delta is a hard gate or evidence of provider uptake.",
                "A future 16-call block requires explicit authorization after this lock; this file grants none.",
                "No result here supports hidden-state editing, causal superiority, quality improvement, or general reasoning improvement.",
            ],
        }
    )


def validate_policy_lock() -> dict[str, Any]:
    lock = _strict_load(POLICY_LOCK_PATH)
    _validate_fingerprint(lock, "policy lock")
    _require(
        _canonical_bytes(lock) == _canonical_bytes(policy_lock_material()),
        "POLICY_LOCK_DRIFT",
    )
    return lock


def _canonical_pretty_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _write_canonical(path: Path, value: Any) -> None:
    data = _canonical_pretty_bytes(value)
    if path.exists():
        _require(path.read_bytes() == data, "CANONICAL_ARTIFACT_DRIFT", str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _validate_artifact_directory_entries(
    output_dir: Path, *, require_complete: bool
) -> None:
    if not output_dir.exists():
        _require(not require_complete, "CANONICAL_ARTIFACT_DIRECTORY_MISSING")
        return
    _require(
        output_dir.is_dir() and not output_dir.is_symlink(),
        "CANONICAL_ARTIFACT_DIRECTORY_INVALID",
    )
    entries = list(output_dir.iterdir())
    names = {entry.name for entry in entries}
    _require(
        names.issubset(CANONICAL_ARTIFACT_FILENAMES),
        "CANONICAL_ARTIFACT_STALE_ENTRY",
        ",".join(sorted(names - CANONICAL_ARTIFACT_FILENAMES)),
    )
    _require(
        all(entry.is_file() and not entry.is_symlink() for entry in entries),
        "CANONICAL_ARTIFACT_ENTRY_INVALID",
    )
    if require_complete:
        _require(
            names == CANONICAL_ARTIFACT_FILENAMES,
            "CANONICAL_ARTIFACT_FILESET_INCOMPLETE",
        )


def build_canonical_artifact(output_dir: Path = DEFAULT_ARTIFACT_DIR) -> dict[str, Any]:
    lock = validate_policy_lock()
    output_dir = output_dir.resolve()
    _require(
        output_dir == DEFAULT_ARTIFACT_DIR.resolve(),
        "NONCANONICAL_ARTIFACT_DIRECTORY",
    )
    _validate_artifact_directory_entries(output_dir, require_complete=False)
    preflight = build_preflight()
    projection = preflight["projection"]
    self_test = preflight["self_test"]
    controller_audit = _seal(
        {
            "schema_version": "ebrt-actuator-calibration-controller-bundle-v0.6.3",
            "status": "PASS_NETWORK_ZERO",
            "controller_audits": projection["controller_audits"],
            "geometry_audits": projection["geometry_audits"],
            "alignment_arithmetic_audit": self_test["alignment_arithmetic_audit"],
            "provider_calls": 0,
            "network_calls": 0,
            "claim_boundary": [
                "The controller audit proves local gradient and schedule construction only.",
                "It contains no hosted observation or synthetic effect result.",
            ],
        }
    )
    outputs = {
        "projection_bundle.json": projection,
        "controller_audit.json": controller_audit,
        "self_test.json": self_test,
    }
    for filename, value in outputs.items():
        _write_canonical(output_dir / filename, value)
    receipts = {
        filename: _file_receipt(output_dir / filename) for filename in sorted(outputs)
    }
    manifest = _seal(
        {
            "schema_version": "ebrt-actuator-calibration-preflight-manifest-v0.6.3",
            "status": "READY_ZERO_CALL_PREFLIGHT_ONLY",
            "policy_lock": _file_receipt(POLICY_LOCK_PATH),
            "source_receipts": lock["sources"],
            "artifact_receipts": receipts,
            "projection_fingerprint_sha256": projection["fingerprint_sha256"],
            "self_test_fingerprint_sha256": self_test["fingerprint_sha256"],
            "controller_audit_fingerprint_sha256": controller_audit[
                "fingerprint_sha256"
            ],
            "hard_gates": self_test["hard_gates"],
            "provider_calls": 0,
            "network_calls": 0,
            "live_execution_authorized": False,
            "handoff_status": "AWAIT_EXPLICIT_LIVE_AUTHORIZATION",
            "claim_boundary": lock["claim_boundary"],
        }
    )
    _write_canonical(output_dir / "manifest.json", manifest)
    _validate_artifact_directory_entries(output_dir, require_complete=True)
    return manifest


def _print_json(value: Any) -> None:
    print(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("self-test", help="run adversarial network-zero checks")
    subparsers.add_parser("projection", help="print the sealed 16-payload projection")
    subparsers.add_parser("preflight", help="print projection plus self-test")
    subparsers.add_parser("policy-lock", help="print the expected frozen policy lock")
    artifact_parser = subparsers.add_parser(
        "build-artifact", help="write the canonical network-zero artifact"
    )
    artifact_parser.add_argument(
        "--output-dir", type=Path, default=DEFAULT_ARTIFACT_DIR
    )
    args = parser.parse_args(argv)
    if args.command == "self-test":
        _print_json(run_self_test())
    elif args.command == "projection":
        _print_json(build_projection(_strict_load(FIXTURE_PATH)))
    elif args.command == "preflight":
        _print_json(build_preflight())
    elif args.command == "policy-lock":
        _print_json(policy_lock_material())
    else:
        _print_json(build_canonical_artifact(args.output_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
