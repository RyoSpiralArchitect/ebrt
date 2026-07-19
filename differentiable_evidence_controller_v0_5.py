#!/usr/bin/env python3
"""EBRT v0.5.0: differentiable evidence control over a public graph.

This single-file mechanism core accepts one exact, typed public semantic graph,
freezes it, and optimizes one bounded scalar gate per evidence node with real
PyTorch autograd.  It deliberately stops before language generation:

    public semantic graph (adapter output; stop-gradient)
      -> frozen signed dependency matrix
      -> g = 2 * sigmoid(u)
      -> h = tanh(A.T @ g)
      -> local backward() and bounded control projection
      -> deterministic public JSON control map (non-differentiable boundary)

It does not call a provider, read hidden model state, use evaluation gold, or
claim that a hosted model has improved.  File I/O exists only in the CLI.  The
``optimize`` method itself is a pure local tensor computation over its explicit
graph and configuration arguments.

Examples:

    python3 differentiable_evidence_controller_v0_5.py self-test
    python3 differentiable_evidence_controller_v0_5.py demo
    python3 differentiable_evidence_controller_v0_5.py validate \
        --input-json fixtures/differentiable_evidence_controller_v0_5_dev.json
    python3 differentiable_evidence_controller_v0_5.py optimize \
        --input-json fixtures/differentiable_evidence_controller_v0_5_dev.json \
        --output-json /tmp/ebrt-control-map.json
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import torch
from torch import Tensor


GRAPH_SCHEMA_VERSION = "ebrt-public-semantic-graph-v0.5.0"
CONTROL_MAP_SCHEMA_VERSION = "ebrt-evidence-control-map-v0.5.0"
CONTROLLER_NAME = "EBRT Differentiable Evidence Controller"
CONTROLLER_VERSION = "0.5.0-mechanism"
FLOAT_DTYPE = torch.float64
FINITE_DIFFERENCE_EPSILON = 1e-6
FINITE_DIFFERENCE_ABS_TOLERANCE = 2e-8

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_SOURCE_KINDS = frozenset({"raw_history", "revision_event"})
_ALLOWED_RELATIONS = frozenset({"supports", "contradicts"})
_FORBIDDEN_NON_PUBLIC_KEYS = frozenset(
    {
        "answer",
        "answer_key",
        "correct_answer",
        "evaluation_label",
        "expected_answer",
        "gold",
        "gold_label",
        "machine_success",
        "provider_output",
        "required_support",
        "strict_grade",
        "target_decision",
        "downstream_verdict",
    }
)


class SchemaValidationError(ValueError):
    """Raised when a public graph violates the exact v0.5.0 contract."""


def _canonical_json_bytes(value: Any, *, trailing_newline: bool = False) -> bytes:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return encoded + (b"\n" if trailing_newline else b"")


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _reject_forbidden_keys(value: Any, path: str = "$") -> None:
    """Reject forbidden *mapping keys*, never matching explanatory text."""

    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key)
            if key.casefold() in _FORBIDDEN_NON_PUBLIC_KEYS:
                raise SchemaValidationError(
                    f"{path}.{key}: forbidden non-public/evaluation key"
                )
            _reject_forbidden_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_forbidden_keys(child, f"{path}[{index}]")


def _exact_mapping(value: Any, path: str, expected: set[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SchemaValidationError(f"{path}: expected object")
    if any(not isinstance(key, str) for key in value):
        raise SchemaValidationError(f"{path}: object keys must be strings")
    actual = set(value)
    unknown = sorted(actual - expected)
    missing = sorted(expected - actual)
    if unknown or missing:
        details: list[str] = []
        if unknown:
            details.append(f"unknown keys={unknown}")
        if missing:
            details.append(f"missing keys={missing}")
        raise SchemaValidationError(f"{path}: " + "; ".join(details))
    return value


def _list(value: Any, path: str, *, nonempty: bool = False) -> list[Any]:
    if not isinstance(value, list):
        raise SchemaValidationError(f"{path}: expected array")
    if nonempty and not value:
        raise SchemaValidationError(f"{path}: must not be empty")
    return value


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SchemaValidationError(f"{path}: expected non-empty string")
    if value != value.strip():
        raise SchemaValidationError(f"{path}: leading/trailing whitespace is forbidden")
    return value


def _boolean(value: Any, path: str) -> bool:
    if type(value) is not bool:
        raise SchemaValidationError(f"{path}: expected boolean")
    return value


def _integer(value: Any, path: str) -> int:
    if type(value) is not int:
        raise SchemaValidationError(f"{path}: expected integer")
    return value


def _number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SchemaValidationError(f"{path}: expected finite number")
    result = float(value)
    if not math.isfinite(result):
        raise SchemaValidationError(f"{path}: expected finite number")
    return result


def _unique_strings(
    values: Any, path: str, *, nonempty: bool = False
) -> tuple[str, ...]:
    items = _list(values, path, nonempty=nonempty)
    result = tuple(
        _string(item, f"{path}[{index}]") for index, item in enumerate(items)
    )
    if len(set(result)) != len(result):
        raise SchemaValidationError(f"{path}: duplicate values are forbidden")
    return result


@dataclass(frozen=True)
class EvidenceNode:
    evidence_id: str
    ordinal: int
    public_summary: str
    source_kind: str

    @classmethod
    def from_mapping(cls, value: Any, path: str) -> "EvidenceNode":
        item = _exact_mapping(
            value,
            path,
            {"evidence_id", "ordinal", "public_summary", "source_kind"},
        )
        evidence_id = _string(item["evidence_id"], f"{path}.evidence_id")
        ordinal = _integer(item["ordinal"], f"{path}.ordinal")
        if ordinal < 1:
            raise SchemaValidationError(f"{path}.ordinal: must be >= 1")
        source_kind = _string(item["source_kind"], f"{path}.source_kind")
        if source_kind not in _ALLOWED_SOURCE_KINDS:
            raise SchemaValidationError(
                f"{path}.source_kind: expected one of {sorted(_ALLOWED_SOURCE_KINDS)}"
            )
        return cls(
            evidence_id=evidence_id,
            ordinal=ordinal,
            public_summary=_string(item["public_summary"], f"{path}.public_summary"),
            source_kind=source_kind,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ClaimNode:
    claim_id: str
    public_name: str
    affected_by_event: bool

    @classmethod
    def from_mapping(cls, value: Any, path: str) -> "ClaimNode":
        item = _exact_mapping(
            value, path, {"claim_id", "public_name", "affected_by_event"}
        )
        return cls(
            claim_id=_string(item["claim_id"], f"{path}.claim_id"),
            public_name=_string(item["public_name"], f"{path}.public_name"),
            affected_by_event=_boolean(
                item["affected_by_event"], f"{path}.affected_by_event"
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DependencyEdge:
    edge_id: str
    evidence_id: str
    claim_id: str
    relation: str
    effect: float

    @classmethod
    def from_mapping(cls, value: Any, path: str) -> "DependencyEdge":
        item = _exact_mapping(
            value,
            path,
            {"edge_id", "evidence_id", "claim_id", "relation", "effect"},
        )
        relation = _string(item["relation"], f"{path}.relation")
        if relation not in _ALLOWED_RELATIONS:
            raise SchemaValidationError(
                f"{path}.relation: expected one of {sorted(_ALLOWED_RELATIONS)}"
            )
        effect = _number(item["effect"], f"{path}.effect")
        if not -1.0 <= effect <= 1.0 or effect == 0.0:
            raise SchemaValidationError(f"{path}.effect: must be non-zero in [-1, 1]")
        if relation == "supports" and effect <= 0.0:
            raise SchemaValidationError(
                f"{path}: supports requires a positive signed effect"
            )
        if relation == "contradicts" and effect >= 0.0:
            raise SchemaValidationError(
                f"{path}: contradicts requires a negative signed effect"
            )
        return cls(
            edge_id=_string(item["edge_id"], f"{path}.edge_id"),
            evidence_id=_string(item["evidence_id"], f"{path}.evidence_id"),
            claim_id=_string(item["claim_id"], f"{path}.claim_id"),
            relation=relation,
            effect=effect,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReplacementTarget:
    claim_id: str
    target: float

    @classmethod
    def from_mapping(cls, value: Any, path: str) -> "ReplacementTarget":
        item = _exact_mapping(value, path, {"claim_id", "target"})
        target = _number(item["target"], f"{path}.target")
        if not -1.0 <= target <= 1.0:
            raise SchemaValidationError(f"{path}.target: must be in [-1, 1]")
        return cls(
            claim_id=_string(item["claim_id"], f"{path}.claim_id"),
            target=target,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RevisionEvent:
    event_id: str
    source_evidence_id: str
    triggered: bool
    affected_claim_ids: tuple[str, ...]
    invalidated_evidence_ids: tuple[str, ...]
    replacement_targets: tuple[ReplacementTarget, ...]

    @classmethod
    def from_mapping(cls, value: Any, path: str) -> "RevisionEvent":
        item = _exact_mapping(
            value,
            path,
            {
                "event_id",
                "source_evidence_id",
                "triggered",
                "affected_claim_ids",
                "invalidated_evidence_ids",
                "replacement_targets",
            },
        )
        targets = tuple(
            ReplacementTarget.from_mapping(
                target, f"{path}.replacement_targets[{index}]"
            )
            for index, target in enumerate(
                _list(item["replacement_targets"], f"{path}.replacement_targets")
            )
        )
        target_ids = [target.claim_id for target in targets]
        if len(set(target_ids)) != len(target_ids):
            raise SchemaValidationError(
                f"{path}.replacement_targets: duplicate claim targets are forbidden"
            )
        return cls(
            event_id=_string(item["event_id"], f"{path}.event_id"),
            source_evidence_id=_string(
                item["source_evidence_id"], f"{path}.source_evidence_id"
            ),
            triggered=_boolean(item["triggered"], f"{path}.triggered"),
            affected_claim_ids=_unique_strings(
                item["affected_claim_ids"], f"{path}.affected_claim_ids"
            ),
            invalidated_evidence_ids=_unique_strings(
                item["invalidated_evidence_ids"],
                f"{path}.invalidated_evidence_ids",
            ),
            replacement_targets=targets,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "source_evidence_id": self.source_evidence_id,
            "triggered": self.triggered,
            "affected_claim_ids": list(self.affected_claim_ids),
            "invalidated_evidence_ids": list(self.invalidated_evidence_ids),
            "replacement_targets": [
                target.to_dict() for target in self.replacement_targets
            ],
        }


@dataclass(frozen=True)
class Provenance:
    adapter_name: str
    adapter_version: str
    semantic_source: str
    deterministic: bool
    semantic_payload_sha256: str

    @classmethod
    def from_mapping(cls, value: Any, path: str) -> "Provenance":
        item = _exact_mapping(
            value,
            path,
            {
                "adapter_name",
                "adapter_version",
                "semantic_source",
                "deterministic",
                "semantic_payload_sha256",
            },
        )
        digest = _string(
            item["semantic_payload_sha256"], f"{path}.semantic_payload_sha256"
        )
        if _SHA256_RE.fullmatch(digest) is None:
            raise SchemaValidationError(
                f"{path}.semantic_payload_sha256: expected lowercase SHA-256"
            )
        deterministic = _boolean(item["deterministic"], f"{path}.deterministic")
        if not deterministic:
            raise SchemaValidationError(
                f"{path}.deterministic: frozen controller input must be deterministic"
            )
        return cls(
            adapter_name=_string(item["adapter_name"], f"{path}.adapter_name"),
            adapter_version=_string(item["adapter_version"], f"{path}.adapter_version"),
            semantic_source=_string(item["semantic_source"], f"{path}.semantic_source"),
            deterministic=deterministic,
            semantic_payload_sha256=digest,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PublicSemanticGraph:
    schema_version: str
    graph_id: str
    evidence_nodes: tuple[EvidenceNode, ...]
    claim_nodes: tuple[ClaimNode, ...]
    dependency_edges: tuple[DependencyEdge, ...]
    revision_event: RevisionEvent
    provenance: Provenance
    claim_boundary: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value: Any) -> "PublicSemanticGraph":
        _reject_forbidden_keys(value)
        root = _exact_mapping(
            value,
            "$",
            {
                "schema_version",
                "graph_id",
                "evidence_nodes",
                "claim_nodes",
                "dependency_edges",
                "revision_event",
                "provenance",
                "claim_boundary",
            },
        )
        schema_version = _string(root["schema_version"], "$.schema_version")
        if schema_version != GRAPH_SCHEMA_VERSION:
            raise SchemaValidationError(
                f"$.schema_version: expected {GRAPH_SCHEMA_VERSION!r}"
            )
        evidence_nodes = tuple(
            EvidenceNode.from_mapping(item, f"$.evidence_nodes[{index}]")
            for index, item in enumerate(
                _list(root["evidence_nodes"], "$.evidence_nodes", nonempty=True)
            )
        )
        claim_nodes = tuple(
            ClaimNode.from_mapping(item, f"$.claim_nodes[{index}]")
            for index, item in enumerate(
                _list(root["claim_nodes"], "$.claim_nodes", nonempty=True)
            )
        )
        edges = tuple(
            DependencyEdge.from_mapping(item, f"$.dependency_edges[{index}]")
            for index, item in enumerate(
                _list(root["dependency_edges"], "$.dependency_edges", nonempty=True)
            )
        )
        event = RevisionEvent.from_mapping(root["revision_event"], "$.revision_event")
        provenance = Provenance.from_mapping(root["provenance"], "$.provenance")
        claim_boundary = _unique_strings(
            root["claim_boundary"], "$.claim_boundary", nonempty=True
        )
        graph = cls(
            schema_version=schema_version,
            graph_id=_string(root["graph_id"], "$.graph_id"),
            evidence_nodes=evidence_nodes,
            claim_nodes=claim_nodes,
            dependency_edges=edges,
            revision_event=event,
            provenance=provenance,
            claim_boundary=claim_boundary,
        )
        graph._validate_references_and_hash()
        return graph

    def _validate_references_and_hash(self) -> None:
        evidence_ids = [node.evidence_id for node in self.evidence_nodes]
        claim_ids = [node.claim_id for node in self.claim_nodes]
        edge_ids = [edge.edge_id for edge in self.dependency_edges]
        for name, values in (
            ("evidence_id", evidence_ids),
            ("claim_id", claim_ids),
            ("edge_id", edge_ids),
        ):
            if len(set(values)) != len(values):
                raise SchemaValidationError(f"duplicate {name} values are forbidden")

        ordinals = [node.ordinal for node in self.evidence_nodes]
        if len(set(ordinals)) != len(ordinals):
            raise SchemaValidationError("evidence ordinals must be unique")
        if sorted(ordinals) != list(range(1, len(ordinals) + 1)):
            raise SchemaValidationError(
                "evidence ordinals must form the exact range 1..N"
            )

        evidence_set = set(evidence_ids)
        claim_set = set(claim_ids)
        dependency_pairs: set[tuple[str, str]] = set()
        for edge in self.dependency_edges:
            if edge.evidence_id not in evidence_set:
                raise SchemaValidationError(
                    f"edge {edge.edge_id}: unknown evidence_id {edge.evidence_id!r}"
                )
            if edge.claim_id not in claim_set:
                raise SchemaValidationError(
                    f"edge {edge.edge_id}: unknown claim_id {edge.claim_id!r}"
                )
            dependency_pair = (edge.evidence_id, edge.claim_id)
            if dependency_pair in dependency_pairs:
                raise SchemaValidationError(
                    "duplicate evidence-to-claim dependency pair is forbidden: "
                    f"{dependency_pair!r}"
                )
            dependency_pairs.add(dependency_pair)

        event = self.revision_event
        if event.source_evidence_id not in evidence_set:
            raise SchemaValidationError(
                "revision_event.source_evidence_id must reference an evidence node"
            )
        evidence_by_id = {node.evidence_id: node for node in self.evidence_nodes}
        source_evidence = evidence_by_id[event.source_evidence_id]
        if source_evidence.source_kind != "revision_event":
            raise SchemaValidationError(
                "revision_event.source_evidence_id must reference a "
                "source_kind='revision_event' node"
            )
        if not set(event.invalidated_evidence_ids) <= evidence_set:
            raise SchemaValidationError(
                "revision_event.invalidated_evidence_ids contains an unknown reference"
            )
        if event.source_evidence_id in set(event.invalidated_evidence_ids):
            raise SchemaValidationError(
                "revision source evidence cannot invalidate itself"
            )
        for invalidated_id in event.invalidated_evidence_ids:
            if evidence_by_id[invalidated_id].ordinal >= source_evidence.ordinal:
                raise SchemaValidationError(
                    "invalidated evidence must be strictly earlier than revision source"
                )
        if not set(event.affected_claim_ids) <= claim_set:
            raise SchemaValidationError(
                "revision_event.affected_claim_ids contains an unknown reference"
            )
        target_ids = {target.claim_id for target in event.replacement_targets}
        if not target_ids <= claim_set:
            raise SchemaValidationError(
                "revision_event.replacement_targets contains an unknown claim reference"
            )
        declared_affected = {
            claim.claim_id for claim in self.claim_nodes if claim.affected_by_event
        }
        if declared_affected != set(event.affected_claim_ids):
            raise SchemaValidationError(
                "claim affected_by_event flags must exactly match affected_claim_ids"
            )

        if event.triggered:
            if not event.affected_claim_ids or not event.replacement_targets:
                raise SchemaValidationError(
                    "triggered event requires affected claims and replacement targets"
                )
            if target_ids != set(event.affected_claim_ids):
                raise SchemaValidationError(
                    "replacement target claims must exactly match affected_claim_ids"
                )
            incoming_to_affected = {
                edge.evidence_id
                for edge in self.dependency_edges
                if edge.claim_id in set(event.affected_claim_ids)
            }
            if event.source_evidence_id not in incoming_to_affected:
                raise SchemaValidationError(
                    "triggered event source must have a dependency path to an affected claim"
                )
            if not set(event.invalidated_evidence_ids) <= incoming_to_affected:
                raise SchemaValidationError(
                    "invalidated evidence must have a dependency path to an affected claim"
                )
        elif (
            event.affected_claim_ids
            or event.invalidated_evidence_ids
            or event.replacement_targets
            or declared_affected
        ):
            raise SchemaValidationError(
                "non-triggered event must have empty intervention fields"
            )

        calculated = self.semantic_payload_sha256()
        if calculated != self.provenance.semantic_payload_sha256:
            raise SchemaValidationError(
                "provenance.semantic_payload_sha256 mismatch: "
                f"declared={self.provenance.semantic_payload_sha256} "
                f"calculated={calculated}"
            )

    def semantic_payload(self) -> dict[str, Any]:
        """Exact adapter output covered by provenance.semantic_payload_sha256."""

        return {
            "schema_version": self.schema_version,
            "graph_id": self.graph_id,
            "evidence_nodes": [node.to_dict() for node in self.evidence_nodes],
            "claim_nodes": [node.to_dict() for node in self.claim_nodes],
            "dependency_edges": [edge.to_dict() for edge in self.dependency_edges],
            "revision_event": self.revision_event.to_dict(),
        }

    def semantic_payload_sha256(self) -> str:
        return _sha256_json(self.semantic_payload())

    def to_dict(self) -> dict[str, Any]:
        result = self.semantic_payload()
        result["provenance"] = self.provenance.to_dict()
        result["claim_boundary"] = list(self.claim_boundary)
        return result


@dataclass(frozen=True)
class ControllerConfig:
    revision_steps: int = 120
    learning_rate: float = 0.08
    revision_consistency_weight: float = 4.0
    support_preservation_weight: float = 1.0
    invalidation_suppression_weight: float = 1.5
    stable_claim_drift_weight: float = 2.0
    control_l2_weight: float = 0.05
    max_control_l2_norm: float = 1.25
    role_delta: float = 0.05
    gate_epsilon: float = 1e-12
    acceptance_tolerance: float = 1e-12
    numeric_precision: int = 12

    def validate(self) -> None:
        if type(self.revision_steps) is not int or self.revision_steps < 1:
            raise ValueError("revision_steps must be an integer >= 1")
        if not math.isfinite(self.learning_rate) or self.learning_rate <= 0.0:
            raise ValueError("learning_rate must be finite and > 0")
        for name in (
            "revision_consistency_weight",
            "support_preservation_weight",
            "invalidation_suppression_weight",
            "stable_claim_drift_weight",
            "control_l2_weight",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and >= 0")
        if not math.isfinite(self.max_control_l2_norm) or self.max_control_l2_norm <= 0:
            raise ValueError("max_control_l2_norm must be finite and > 0")
        if not 0.0 <= self.role_delta < 1.0:
            raise ValueError("role_delta must be in [0, 1)")
        if not 0.0 < self.gate_epsilon < 1e-3:
            raise ValueError("gate_epsilon must be in (0, 1e-3)")
        if self.acceptance_tolerance < 0.0:
            raise ValueError("acceptance_tolerance must be >= 0")
        if not 6 <= self.numeric_precision <= 16:
            raise ValueError("numeric_precision must be in [6, 16]")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FrozenPublicSurrogate:
    evidence_ids: tuple[str, ...]
    claim_ids: tuple[str, ...]
    dependency_matrix: Tensor
    baseline_gates: Tensor
    baseline_claim_activations: Tensor
    target_claim_indices: tuple[int, ...]
    target_values: Tensor
    active_support_indices: tuple[int, ...]
    invalidated_indices: tuple[int, ...]
    stable_claim_indices: tuple[int, ...]
    affected_ancestor_indices: tuple[int, ...]


@dataclass(frozen=True)
class TensorLossTerms:
    revision_consistency: Tensor
    support_preservation: Tensor
    invalidation_suppression: Tensor
    stable_claim_drift: Tensor
    control_l2: Tensor
    total: Tensor

    def tensor_dict(self) -> dict[str, Tensor]:
        return {
            "revision_consistency": self.revision_consistency,
            "support_preservation": self.support_preservation,
            "invalidation_suppression": self.invalidation_suppression,
            "stable_claim_drift": self.stable_claim_drift,
            "control_l2": self.control_l2,
            "total": self.total,
        }

    def scalar_dict(self) -> dict[str, float]:
        return {
            name: float(value.detach().item())
            for name, value in self.tensor_dict().items()
        }


@dataclass(frozen=True)
class OptimizationResult:
    graph: PublicSemanticGraph
    config: ControllerConfig
    evidence_ids: tuple[str, ...]
    claim_ids: tuple[str, ...]
    status: str
    baseline_gates: Tensor
    final_gates: Tensor
    baseline_claim_activations: Tensor
    final_claim_activations: Tensor
    loss_before: dict[str, float]
    loss_after: dict[str, float]
    energy_history: tuple[float, ...]
    first_gradient: Tensor
    backward_calls: int
    accepted: bool
    rolled_back: bool
    best_iteration: int
    max_observed_control_l2_norm: float
    min_observed_gate: float
    max_observed_gate: float

    def _rounded(self, value: float) -> float:
        rounded = round(float(value), self.config.numeric_precision)
        return 0.0 if rounded == -0.0 else rounded

    def control_map_without_fingerprint(self) -> dict[str, Any]:
        ordered_nodes = sorted(
            self.graph.evidence_nodes, key=lambda node: (node.ordinal, node.evidence_id)
        )
        graph_index = {
            evidence_id: index for index, evidence_id in enumerate(self.evidence_ids)
        }
        controls: list[dict[str, Any]] = []
        for node in ordered_nodes:
            index = graph_index[node.evidence_id]
            gate = float(self.final_gates[index].item())
            if gate < 1.0 - self.config.role_delta:
                role = "suppress"
            elif gate > 1.0 + self.config.role_delta:
                role = "boost"
            else:
                role = "preserve"
            controls.append(
                {
                    "evidence_id": node.evidence_id,
                    "ordinal": node.ordinal,
                    "role": role,
                    "gate": self._rounded(gate),
                    "delta_from_neutral": self._rounded(gate - 1.0),
                }
            )

        claim_by_id = {claim.claim_id: claim for claim in self.graph.claim_nodes}
        claim_before = {
            claim_id: self._rounded(self.baseline_claim_activations[index].item())
            for index, claim_id in enumerate(self.claim_ids)
        }
        claim_after = {
            claim_id: self._rounded(self.final_claim_activations[index].item())
            for index, claim_id in enumerate(self.claim_ids)
        }
        if set(claim_by_id) != set(self.claim_ids):
            raise RuntimeError("result claim order does not match source graph")
        rounded_before = {
            key: self._rounded(value) for key, value in self.loss_before.items()
        }
        rounded_after = {
            key: self._rounded(value) for key, value in self.loss_after.items()
        }
        return {
            "schema_version": CONTROL_MAP_SCHEMA_VERSION,
            "controller": {
                "name": CONTROLLER_NAME,
                "version": CONTROLLER_VERSION,
                "dtype": "float64",
                "gate_parameterization": "g=2*sigmoid(u)",
                "claim_activation": "h=tanh(A^T*g)",
                "optimizer": "Adam",
                "randomness": "deterministic_no_rng",
                "best_checkpoint_rule": (
                    "minimum finite projected objective; accept only when the "
                    "decrease exceeds acceptance_tolerance"
                ),
                "acceptance_tolerance": self.config.acceptance_tolerance,
                "gradient_boundary": (
                    "local frozen public surrogate only; adapter and JSON projection "
                    "are stop-gradient boundaries"
                ),
            },
            "source": {
                "graph_id": self.graph.graph_id,
                "semantic_payload_sha256": self.graph.semantic_payload_sha256(),
                "event_id": self.graph.revision_event.event_id,
                "event_triggered": self.graph.revision_event.triggered,
            },
            "status": self.status,
            "controls": controls,
            "surrogate": {
                "objective_before": rounded_before,
                "objective_after": rounded_after,
                "claim_activations_before": claim_before,
                "claim_activations_after": claim_after,
            },
            "optimization": {
                "config": self.config.to_dict(),
                "backward_calls": self.backward_calls,
                "accepted": self.accepted,
                "rolled_back": self.rolled_back,
                "best_iteration": self.best_iteration,
                "control_l2_norm": self._rounded(
                    torch.linalg.vector_norm(self.final_gates - 1.0).item()
                ),
                "max_observed_control_l2_norm": self._rounded(
                    self.max_observed_control_l2_norm
                ),
                "min_observed_gate": self._rounded(self.min_observed_gate),
                "max_observed_gate": self._rounded(self.max_observed_gate),
            },
            "claim_boundary": [
                "Mechanism-only optimization over a frozen public semantic graph.",
                "No gradient crosses the semantic adapter, JSON, or provider boundary.",
                "This control map is not evidence of improved hosted-model reasoning.",
            ],
        }

    def to_control_map(self) -> dict[str, Any]:
        payload = self.control_map_without_fingerprint()
        payload["fingerprint_sha256"] = _sha256_json(payload)
        return payload

    def canonical_control_map_bytes(self) -> bytes:
        return _canonical_json_bytes(self.to_control_map(), trailing_newline=True)


class DifferentiableEvidenceController:
    """Local float64 autograd controller over an immutable public graph."""

    def __init__(self, config: ControllerConfig | None = None) -> None:
        self.config = config or ControllerConfig()
        self.config.validate()

    @staticmethod
    def freeze_graph(graph: PublicSemanticGraph) -> FrozenPublicSurrogate:
        evidence_nodes = tuple(
            sorted(
                graph.evidence_nodes, key=lambda node: (node.ordinal, node.evidence_id)
            )
        )
        claim_nodes = tuple(sorted(graph.claim_nodes, key=lambda node: node.claim_id))
        evidence_index = {
            node.evidence_id: index for index, node in enumerate(evidence_nodes)
        }
        claim_index = {node.claim_id: index for index, node in enumerate(claim_nodes)}
        matrix = torch.zeros((len(evidence_nodes), len(claim_nodes)), dtype=FLOAT_DTYPE)
        for edge in graph.dependency_edges:
            matrix[evidence_index[edge.evidence_id], claim_index[edge.claim_id]] += (
                edge.effect
            )
        matrix = matrix.detach()
        matrix.requires_grad_(False)
        baseline_gates = torch.ones(len(evidence_nodes), dtype=FLOAT_DTYPE)
        baseline_claims = torch.tanh(matrix.T @ baseline_gates).detach()

        event = graph.revision_event
        target_claim_indices = tuple(
            claim_index[target.claim_id] for target in event.replacement_targets
        )
        target_values = torch.tensor(
            [target.target for target in event.replacement_targets], dtype=FLOAT_DTYPE
        )
        affected_claims = set(event.affected_claim_ids)
        invalidated = set(event.invalidated_evidence_ids)
        support_indices = sorted(
            {
                evidence_index[edge.evidence_id]
                for edge in graph.dependency_edges
                if edge.claim_id in affected_claims
                and edge.effect > 0.0
                and edge.evidence_id not in invalidated
            }
        )
        invalidated_indices = tuple(
            sorted(evidence_index[item] for item in invalidated)
        )
        stable_claim_indices = tuple(
            index
            for index, claim in enumerate(claim_nodes)
            if not claim.affected_by_event
        )
        affected_ancestors = tuple(
            sorted(
                {
                    evidence_index[edge.evidence_id]
                    for edge in graph.dependency_edges
                    if edge.claim_id in affected_claims
                }
            )
        )
        return FrozenPublicSurrogate(
            evidence_ids=tuple(node.evidence_id for node in evidence_nodes),
            claim_ids=tuple(node.claim_id for node in claim_nodes),
            dependency_matrix=matrix,
            baseline_gates=baseline_gates,
            baseline_claim_activations=baseline_claims,
            target_claim_indices=target_claim_indices,
            target_values=target_values,
            active_support_indices=tuple(support_indices),
            invalidated_indices=invalidated_indices,
            stable_claim_indices=stable_claim_indices,
            affected_ancestor_indices=affected_ancestors,
        )

    @staticmethod
    def gates_from_logits(logits: Tensor) -> Tensor:
        if logits.dtype != FLOAT_DTYPE:
            raise TypeError("controller logits must use torch.float64")
        return 2.0 * torch.sigmoid(logits)

    def loss_terms(
        self, surrogate: FrozenPublicSurrogate, gates: Tensor
    ) -> tuple[Tensor, TensorLossTerms]:
        if gates.dtype != FLOAT_DTYPE or gates.ndim != 1:
            raise TypeError("gates must be a rank-1 torch.float64 tensor")
        if gates.shape != surrogate.baseline_gates.shape:
            raise ValueError("gate count does not match frozen evidence count")
        activations = torch.tanh(surrogate.dependency_matrix.T @ gates)
        zero = gates.sum() * 0.0

        if surrogate.target_claim_indices:
            target_indices = torch.tensor(
                surrogate.target_claim_indices, dtype=torch.long, device=gates.device
            )
            revision = torch.mean(
                (
                    activations[target_indices]
                    - surrogate.target_values.to(device=gates.device)
                ).square()
            )
        else:
            revision = zero

        if surrogate.active_support_indices:
            support_indices = torch.tensor(
                surrogate.active_support_indices, dtype=torch.long, device=gates.device
            )
            support = torch.mean(torch.relu(1.0 - gates[support_indices]).square())
        else:
            support = zero

        if surrogate.invalidated_indices:
            invalidated_indices = torch.tensor(
                surrogate.invalidated_indices, dtype=torch.long, device=gates.device
            )
            invalidation = torch.mean(gates[invalidated_indices].square())
        else:
            invalidation = zero

        if surrogate.stable_claim_indices:
            stable_indices = torch.tensor(
                surrogate.stable_claim_indices, dtype=torch.long, device=gates.device
            )
            stable = torch.mean(
                (
                    activations[stable_indices]
                    - surrogate.baseline_claim_activations.to(device=gates.device)[
                        stable_indices
                    ]
                ).square()
            )
        else:
            stable = zero

        control = torch.mean((gates - 1.0).square())
        total = (
            self.config.revision_consistency_weight * revision
            + self.config.support_preservation_weight * support
            + self.config.invalidation_suppression_weight * invalidation
            + self.config.stable_claim_drift_weight * stable
            + self.config.control_l2_weight * control
        )
        return activations, TensorLossTerms(
            revision_consistency=revision,
            support_preservation=support,
            invalidation_suppression=invalidation,
            stable_claim_drift=stable,
            control_l2=control,
            total=total,
        )

    def _project_logits_(self, logits: Tensor) -> float:
        """Project ||g-1||_2 after every Adam step, then invert the sigmoid."""

        with torch.no_grad():
            gates = self.gates_from_logits(logits)
            delta = gates - 1.0
            norm = float(torch.linalg.vector_norm(delta).item())
            if norm > self.config.max_control_l2_norm:
                delta.mul_(self.config.max_control_l2_norm / norm)
            gates = (1.0 + delta).clamp(
                min=self.config.gate_epsilon,
                max=2.0 - self.config.gate_epsilon,
            )
            logits.copy_(torch.log(gates / (2.0 - gates)))
            return float(torch.linalg.vector_norm(gates - 1.0).item())

    def optimize(self, graph: PublicSemanticGraph) -> OptimizationResult:
        """Optimize only the frozen public surrogate; perform no I/O or network."""

        surrogate = self.freeze_graph(graph)
        baseline_gates = surrogate.baseline_gates.clone()
        with torch.no_grad():
            baseline_activations, baseline_terms_t = self.loss_terms(
                surrogate, baseline_gates
            )
        baseline_terms = baseline_terms_t.scalar_dict()

        if not graph.revision_event.triggered:
            zeros = torch.zeros_like(baseline_gates)
            return OptimizationResult(
                graph=graph,
                config=self.config,
                evidence_ids=surrogate.evidence_ids,
                claim_ids=surrogate.claim_ids,
                status="NO_EVENT_IDENTITY",
                baseline_gates=baseline_gates,
                final_gates=baseline_gates.clone(),
                baseline_claim_activations=baseline_activations.detach().clone(),
                final_claim_activations=baseline_activations.detach().clone(),
                loss_before=baseline_terms,
                loss_after=baseline_terms.copy(),
                energy_history=(float(baseline_terms["total"]),),
                first_gradient=zeros,
                backward_calls=0,
                accepted=False,
                rolled_back=False,
                best_iteration=0,
                max_observed_control_l2_norm=0.0,
                min_observed_gate=1.0,
                max_observed_gate=1.0,
            )

        logits = torch.zeros(
            len(surrogate.evidence_ids), dtype=FLOAT_DTYPE, requires_grad=True
        )
        optimizer = torch.optim.Adam([logits], lr=self.config.learning_rate)
        best_gates = baseline_gates.clone()
        best_energy = float(baseline_terms["total"])
        best_iteration = 0
        energy_history = [best_energy]
        first_gradient = torch.zeros_like(logits)
        backward_calls = 0
        max_norm = 0.0
        min_gate = 1.0
        max_gate = 1.0

        for iteration in range(1, self.config.revision_steps + 1):
            optimizer.zero_grad(set_to_none=True)
            gates = self.gates_from_logits(logits)
            _, terms = self.loss_terms(surrogate, gates)
            if not torch.isfinite(terms.total):
                break
            terms.total.backward()
            backward_calls += 1
            if logits.grad is None or not torch.isfinite(logits.grad).all():
                break
            if iteration == 1:
                first_gradient = logits.grad.detach().clone()
            optimizer.step()
            projected_norm = self._project_logits_(logits)
            with torch.no_grad():
                candidate_gates = self.gates_from_logits(logits)
                _, candidate_terms = self.loss_terms(surrogate, candidate_gates)
                candidate_energy = float(candidate_terms.total.item())
                if not math.isfinite(candidate_energy):
                    break
                energy_history.append(candidate_energy)
                max_norm = max(max_norm, projected_norm)
                min_gate = min(min_gate, float(candidate_gates.min().item()))
                max_gate = max(max_gate, float(candidate_gates.max().item()))
                if candidate_energy < best_energy:
                    best_energy = candidate_energy
                    best_gates = candidate_gates.detach().clone()
                    best_iteration = iteration

        accepted = best_energy < (
            float(baseline_terms["total"]) - self.config.acceptance_tolerance
        )
        final_gates = best_gates if accepted else baseline_gates.clone()
        with torch.no_grad():
            final_activations, final_terms_t = self.loss_terms(surrogate, final_gates)
        final_terms = final_terms_t.scalar_dict()
        last_gates = self.gates_from_logits(logits.detach())
        rolled_back = bool(
            backward_calls > 0
            and (not accepted or not torch.equal(last_gates, final_gates))
        )
        status = "ACCEPTED_LOCAL_CONTROL" if accepted else "ROLLED_BACK_TO_NEUTRAL"
        return OptimizationResult(
            graph=graph,
            config=self.config,
            evidence_ids=surrogate.evidence_ids,
            claim_ids=surrogate.claim_ids,
            status=status,
            baseline_gates=baseline_gates,
            final_gates=final_gates.detach().clone(),
            baseline_claim_activations=baseline_activations.detach().clone(),
            final_claim_activations=final_activations.detach().clone(),
            loss_before=baseline_terms,
            loss_after=final_terms,
            energy_history=tuple(energy_history),
            first_gradient=first_gradient,
            backward_calls=backward_calls,
            accepted=accepted,
            rolled_back=rolled_back,
            best_iteration=best_iteration,
            max_observed_control_l2_norm=max_norm,
            min_observed_gate=min_gate,
            max_observed_gate=max_gate,
        )


def _semantic_payload_from_raw(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(payload[key])
        for key in (
            "schema_version",
            "graph_id",
            "evidence_nodes",
            "claim_nodes",
            "dependency_edges",
            "revision_event",
        )
    }


def _refresh_provenance_hash(payload: dict[str, Any]) -> None:
    payload["provenance"]["semantic_payload_sha256"] = _sha256_json(
        _semantic_payload_from_raw(payload)
    )


def _demo_payload() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": GRAPH_SCHEMA_VERSION,
        "graph_id": "route_code_supersession_public_graph_demo_v0_5",
        "evidence_nodes": [
            {
                "evidence_id": "R1",
                "ordinal": 1,
                "public_summary": "Resolve NERA's bay from its current route code.",
                "source_kind": "raw_history",
            },
            {
                "evidence_id": "R2",
                "ordinal": 2,
                "public_summary": "The public route table maps B2 to BLUE.",
                "source_kind": "raw_history",
            },
            {
                "evidence_id": "R3",
                "ordinal": 3,
                "public_summary": "A superseded registry entry maps NERA to A1.",
                "source_kind": "raw_history",
            },
            {
                "evidence_id": "R4",
                "ordinal": 4,
                "public_summary": "Bay assignment follows the current registry code.",
                "source_kind": "raw_history",
            },
            {
                "evidence_id": "R5",
                "ordinal": 5,
                "public_summary": "NERA's independent cargo seal remains SEALED.",
                "source_kind": "raw_history",
            },
            {
                "evidence_id": "R6",
                "ordinal": 6,
                "public_summary": "A correction replaces R3 and establishes B2.",
                "source_kind": "revision_event",
            },
            {
                "evidence_id": "R7",
                "ordinal": 7,
                "public_summary": "Different shipment NERO is assigned to BLUE.",
                "source_kind": "raw_history",
            },
        ],
        "claim_nodes": [
            {
                "claim_id": "bay_assignment",
                "public_name": "NERA current bay assignment",
                "affected_by_event": True,
            },
            {
                "claim_id": "cargo_seal",
                "public_name": "NERA cargo seal status",
                "affected_by_event": False,
            },
            {
                "claim_id": "other_shipment_bay",
                "public_name": "NERO bay assignment",
                "affected_by_event": False,
            },
        ],
        "dependency_edges": [
            {
                "edge_id": "E_R2_BAY",
                "evidence_id": "R2",
                "claim_id": "bay_assignment",
                "relation": "supports",
                "effect": 0.9,
            },
            {
                "edge_id": "E_R3_BAY",
                "evidence_id": "R3",
                "claim_id": "bay_assignment",
                "relation": "contradicts",
                "effect": -0.9,
            },
            {
                "edge_id": "E_R4_BAY",
                "evidence_id": "R4",
                "claim_id": "bay_assignment",
                "relation": "supports",
                "effect": 0.2,
            },
            {
                "edge_id": "E_R5_SEAL",
                "evidence_id": "R5",
                "claim_id": "cargo_seal",
                "relation": "supports",
                "effect": 1.0,
            },
            {
                "edge_id": "E_R6_BAY",
                "evidence_id": "R6",
                "claim_id": "bay_assignment",
                "relation": "supports",
                "effect": 1.0,
            },
            {
                "edge_id": "E_R7_OTHER",
                "evidence_id": "R7",
                "claim_id": "other_shipment_bay",
                "relation": "supports",
                "effect": 0.9,
            },
        ],
        "revision_event": {
            "event_id": "EV_ROUTE_CODE_SUPERSESSION",
            "source_evidence_id": "R6",
            "triggered": True,
            "affected_claim_ids": ["bay_assignment"],
            "invalidated_evidence_ids": ["R3"],
            "replacement_targets": [{"claim_id": "bay_assignment", "target": 1.0}],
        },
        "provenance": {
            "adapter_name": "synthetic-public-semantic-graph-adapter",
            "adapter_version": "0.5.0-self-test",
            "semantic_source": "built_in_public_contract_demo",
            "deterministic": True,
            "semantic_payload_sha256": "0" * 64,
        },
        "claim_boundary": [
            "Synthetic public mechanism fixture only.",
            (
                "No separately supplied downstream grader verdict, final-answer "
                "artifact, or provider output enters the controller."
            ),
            "This is a synthetic structured oracle graph, not a learned adapter output.",
            "This cannot establish improved hosted-model reasoning.",
        ],
    }
    _refresh_provenance_hash(payload)
    return payload


def _expect_schema_failure(payload: dict[str, Any], label: str) -> None:
    try:
        PublicSemanticGraph.from_mapping(payload)
    except SchemaValidationError:
        return
    raise AssertionError(f"schema tamper was accepted: {label}")


def run_self_tests() -> dict[str, Any]:
    """Run deterministic, network-zero mechanism and contract checks."""

    graph = PublicSemanticGraph.from_mapping(_demo_payload())
    controller = DifferentiableEvidenceController()
    surrogate = controller.freeze_graph(graph)

    if surrogate.dependency_matrix.dtype != FLOAT_DTYPE:
        raise AssertionError("frozen surrogate is not float64")
    if surrogate.dependency_matrix.requires_grad:
        raise AssertionError("public dependency matrix must remain frozen")

    unicode_payload = _demo_payload()
    unicode_payload["graph_id"] = "unicode_public_graph_demo_v0_5"
    unicode_payload["evidence_nodes"][0]["public_summary"] = (
        "公開履歴から現在のルートを解決する。"
    )
    _refresh_provenance_hash(unicode_payload)
    unicode_graph = PublicSemanticGraph.from_mapping(unicode_payload)
    if (
        unicode_graph.semantic_payload_sha256()
        != unicode_payload["provenance"]["semantic_payload_sha256"]
    ):
        raise AssertionError("UTF-8 semantic payload hash did not round-trip")
    escaped_digest = hashlib.sha256(
        json.dumps(
            _semantic_payload_from_raw(unicode_payload),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    if escaped_digest == unicode_graph.semantic_payload_sha256():
        raise AssertionError("UTF-8 hash test did not distinguish escaped JSON")
    unicode_first = DifferentiableEvidenceController(
        ControllerConfig(revision_steps=3)
    ).optimize(unicode_graph)
    unicode_second = DifferentiableEvidenceController(
        ControllerConfig(revision_steps=3)
    ).optimize(unicode_graph)
    if (
        unicode_first.canonical_control_map_bytes()
        != unicode_second.canonical_control_map_bytes()
    ):
        raise AssertionError("UTF-8 graph projection is not byte deterministic")

    # Real terminal credit assignment with all direct penalties disabled.
    revision_only = DifferentiableEvidenceController(
        ControllerConfig(
            revision_steps=4,
            revision_consistency_weight=1.0,
            support_preservation_weight=0.0,
            invalidation_suppression_weight=0.0,
            stable_claim_drift_weight=0.0,
            control_l2_weight=0.0,
        )
    )
    revision_surrogate = revision_only.freeze_graph(graph)
    logits = torch.zeros(
        len(revision_surrogate.evidence_ids), dtype=FLOAT_DTYPE, requires_grad=True
    )
    _, revision_terms = revision_only.loss_terms(
        revision_surrogate, revision_only.gates_from_logits(logits)
    )
    revision_terms.total.backward()
    if logits.grad is None:
        raise AssertionError("revision-only objective produced no gradient")
    credit = {
        evidence_id: float(logits.grad[index].item())
        for index, evidence_id in enumerate(revision_surrogate.evidence_ids)
    }
    for evidence_id in ("R2", "R4", "R6"):
        if not credit[evidence_id] < 0.0:
            raise AssertionError(f"{evidence_id} lacks graph-routed boost credit")
    if not credit["R3"] > 0.0:
        raise AssertionError("R3 lacks graph-routed suppression credit")
    for evidence_id in ("R1", "R5", "R7"):
        if credit[evidence_id] != 0.0:
            raise AssertionError(
                f"{evidence_id} violates revision-only terminal-credit locality "
                "on the locked topology"
            )

    severed_payload = _demo_payload()
    severed_payload["dependency_edges"] = [
        edge
        for edge in severed_payload["dependency_edges"]
        if edge["edge_id"] != "E_R4_BAY"
    ]
    _refresh_provenance_hash(severed_payload)
    severed_graph = PublicSemanticGraph.from_mapping(severed_payload)
    severed_surrogate = revision_only.freeze_graph(severed_graph)
    severed_logits = torch.zeros(
        len(severed_surrogate.evidence_ids), dtype=FLOAT_DTYPE, requires_grad=True
    )
    _, severed_terms = revision_only.loss_terms(
        severed_surrogate, revision_only.gates_from_logits(severed_logits)
    )
    severed_terms.total.backward()
    if severed_logits.grad is None:
        raise AssertionError("severed-edge control produced no gradient tensor")
    severed_r4 = severed_surrogate.evidence_ids.index("R4")
    if float(severed_logits.grad[severed_r4].item()) != 0.0:
        raise AssertionError("R4 retained terminal credit after its edge was severed")

    # Per-term central finite differences versus u -> g -> A -> h -> loss.
    probe_seed = torch.tensor(
        [0.07, -0.11, 0.13, -0.05, 0.09, -0.17, 0.03],
        dtype=FLOAT_DTYPE,
    )
    epsilon = FINITE_DIFFERENCE_EPSILON
    finite_difference_error_by_term: dict[str, float] = {}
    for term_name in (
        "revision_consistency",
        "support_preservation",
        "invalidation_suppression",
        "stable_claim_drift",
        "control_l2",
        "total",
    ):
        probe_logits = probe_seed.detach().clone().requires_grad_(True)
        _, probe_terms = controller.loss_terms(
            surrogate, controller.gates_from_logits(probe_logits)
        )
        probe_terms.tensor_dict()[term_name].backward()
        if probe_logits.grad is None:
            raise AssertionError(
                f"finite-difference probe produced no gradient for {term_name}"
            )
        analytic = probe_logits.grad.detach().clone()
        finite_difference = torch.zeros_like(analytic)
        with torch.no_grad():
            for index in range(len(probe_logits)):
                plus = probe_seed.detach().clone()
                minus = probe_seed.detach().clone()
                plus[index] += epsilon
                minus[index] -= epsilon
                _, plus_terms = controller.loss_terms(
                    surrogate, controller.gates_from_logits(plus)
                )
                _, minus_terms = controller.loss_terms(
                    surrogate, controller.gates_from_logits(minus)
                )
                finite_difference[index] = (
                    plus_terms.tensor_dict()[term_name]
                    - minus_terms.tensor_dict()[term_name]
                ) / (2.0 * epsilon)
        term_error = float(torch.max(torch.abs(analytic - finite_difference)).item())
        finite_difference_error_by_term[term_name] = term_error
        if term_error > FINITE_DIFFERENCE_ABS_TOLERANCE:
            raise AssertionError(
                f"finite-difference/autograd mismatch for {term_name}: {term_error:.3e}"
            )
    max_gradient_error = max(finite_difference_error_by_term.values())

    first = controller.optimize(graph)
    second = controller.optimize(graph)
    if first.canonical_control_map_bytes() != second.canonical_control_map_bytes():
        raise AssertionError("identical optimization runs are not byte deterministic")
    if not first.accepted or not first.loss_after["total"] < first.loss_before["total"]:
        raise AssertionError("normal revision failed to accept a lower-energy control")
    final_norm = float(torch.linalg.vector_norm(first.final_gates - 1.0).item())
    if final_norm > controller.config.max_control_l2_norm + 1e-12:
        raise AssertionError("final control exceeds configured L2 bound")
    if (
        first.max_observed_control_l2_norm
        > controller.config.max_control_l2_norm + 1e-12
    ):
        raise AssertionError("an intermediate control exceeded configured L2 bound")
    if not 0.0 < first.min_observed_gate <= first.max_observed_gate < 2.0:
        raise AssertionError("an observed projected gate escaped the open (0, 2) bound")
    if not bool(torch.all((first.final_gates > 0.0) & (first.final_gates < 2.0))):
        raise AssertionError("bounded sigmoid gate escaped (0, 2)")
    result_index = {
        node.evidence_id: index
        for index, node in enumerate(
            sorted(
                graph.evidence_nodes, key=lambda node: (node.ordinal, node.evidence_id)
            )
        )
    }
    for evidence_id in ("R1", "R5", "R7"):
        if float(first.final_gates[result_index[evidence_id]].item()) != 1.0:
            raise AssertionError(
                f"unrelated gate {evidence_id} moved from exact neutral"
            )
    stable_indices = torch.tensor(surrogate.stable_claim_indices, dtype=torch.long)
    if not torch.equal(
        first.final_claim_activations[stable_indices],
        first.baseline_claim_activations[stable_indices],
    ):
        raise AssertionError("unaffected claim activation drifted")

    # A non-triggered event is an exact identity path and performs no backward.
    no_event_payload = _demo_payload()
    no_event_payload["revision_event"].update(
        {
            "triggered": False,
            "affected_claim_ids": [],
            "invalidated_evidence_ids": [],
            "replacement_targets": [],
        }
    )
    for claim in no_event_payload["claim_nodes"]:
        claim["affected_by_event"] = False
    _refresh_provenance_hash(no_event_payload)
    no_event_graph = PublicSemanticGraph.from_mapping(no_event_payload)
    no_event = controller.optimize(no_event_graph)
    if no_event.backward_calls != 0 or no_event.status != "NO_EVENT_IDENTITY":
        raise AssertionError("zero-event path invoked optimization")
    if not torch.equal(no_event.final_gates, no_event.baseline_gates):
        raise AssertionError("zero-event gates are not exact identity")
    if not torch.equal(
        no_event.final_claim_activations, no_event.baseline_claim_activations
    ):
        raise AssertionError("zero-event claim state changed")

    # Force a one-step overshoot; acceptance must restore the neutral checkpoint.
    rollback_payload = _demo_payload()
    baseline_target = float(
        controller.freeze_graph(graph)
        .baseline_claim_activations[
            controller.freeze_graph(graph).claim_ids.index("bay_assignment")
        ]
        .item()
    )
    rollback_payload["revision_event"]["replacement_targets"][0]["target"] = min(
        1.0, baseline_target + 1e-5
    )
    _refresh_provenance_hash(rollback_payload)
    rollback_graph = PublicSemanticGraph.from_mapping(rollback_payload)
    rollback_controller = DifferentiableEvidenceController(
        ControllerConfig(
            revision_steps=1,
            learning_rate=1000.0,
            revision_consistency_weight=1.0,
            support_preservation_weight=0.0,
            invalidation_suppression_weight=0.0,
            stable_claim_drift_weight=0.0,
            control_l2_weight=0.0,
            max_control_l2_norm=1.25,
        )
    )
    rollback = rollback_controller.optimize(rollback_graph)
    if rollback.accepted or not rollback.rolled_back:
        raise AssertionError("energy-regressing proposal was not rolled back")
    if not torch.equal(rollback.final_gates, rollback.baseline_gates):
        raise AssertionError("rollback did not restore exact neutral gates")
    if rollback.loss_after != rollback.loss_before:
        raise AssertionError("rollback did not restore the baseline energy")

    # Exact schema, forbidden key, recursive unknown-key, and hash tamper guards.
    root_gold = _demo_payload()
    root_gold["gold"] = "BLUE"
    _expect_schema_failure(root_gold, "root gold")
    nested_answer = _demo_payload()
    nested_answer["evidence_nodes"][0]["expected_answer"] = "BLUE"
    _expect_schema_failure(nested_answer, "nested expected_answer")
    provenance_verdict = _demo_payload()
    provenance_verdict["provenance"]["downstream_verdict"] = "PASS"
    _expect_schema_failure(provenance_verdict, "provenance downstream_verdict")
    unknown_nested = _demo_payload()
    unknown_nested["revision_event"]["replacement_targets"][0]["note"] = "extra"
    _expect_schema_failure(unknown_nested, "recursive unknown key")
    hash_tamper = _demo_payload()
    hash_tamper["dependency_edges"][0]["effect"] = 0.8
    _expect_schema_failure(hash_tamper, "semantic payload hash mismatch")
    wrong_source_kind = _demo_payload()
    next(
        node
        for node in wrong_source_kind["evidence_nodes"]
        if node["evidence_id"] == "R6"
    )["source_kind"] = "raw_history"
    _refresh_provenance_hash(wrong_source_kind)
    _expect_schema_failure(wrong_source_kind, "revision source kind")
    late_invalidation = _demo_payload()
    r3 = next(
        node
        for node in late_invalidation["evidence_nodes"]
        if node["evidence_id"] == "R3"
    )
    r7 = next(
        node
        for node in late_invalidation["evidence_nodes"]
        if node["evidence_id"] == "R7"
    )
    r3["ordinal"], r7["ordinal"] = r7["ordinal"], r3["ordinal"]
    _refresh_provenance_hash(late_invalidation)
    _expect_schema_failure(late_invalidation, "late invalidated evidence")
    duplicate_dependency = _demo_payload()
    duplicate_dependency["dependency_edges"].append(
        {
            "edge_id": "E_R2_BAY_DUPLICATE",
            "evidence_id": "R2",
            "claim_id": "bay_assignment",
            "relation": "supports",
            "effect": 0.1,
        }
    )
    _refresh_provenance_hash(duplicate_dependency)
    _expect_schema_failure(duplicate_dependency, "duplicate dependency pair")

    # The pure optimize path must remain functional when socket creation is denied.
    import socket
    from unittest import mock

    with mock.patch.object(
        socket, "socket", side_effect=AssertionError("network used")
    ):
        network_zero = DifferentiableEvidenceController(
            ControllerConfig(revision_steps=2)
        ).optimize(graph)
    if network_zero.backward_calls != 2:
        raise AssertionError("network-zero optimization did not complete locally")

    control_map = first.to_control_map()
    fingerprint = control_map.pop("fingerprint_sha256")
    if fingerprint != _sha256_json(control_map):
        raise AssertionError("control-map fingerprint does not cover exact payload")

    return {
        "status": "PASS",
        "controller": f"{CONTROLLER_NAME} {CONTROLLER_VERSION}",
        "checks": [
            "exact typed public graph and canonical provenance hash",
            "UTF-8 canonical hashing is unescaped and byte deterministic",
            "terminal_graph_credit_assignment",
            "finite-difference agrees with float64 autograd",
            (
                "revision-only terminal credit is local on the locked topology "
                "and severed-edge ablation"
            ),
            "zero-event path is identity with zero backward calls",
            "all gates and projected control L2 remain bounded",
            "accepted control lowers energy and locked unrelated state remains exact",
            "energy-regressing proposal rolls back to neutral",
            "two identical runs emit byte-identical control-map JSON",
            "recursive unknown, gold-field, and semantic-hash tampering is rejected",
            "event-source, temporal invalidation, and duplicate-edge tampering is rejected",
            "pure optimize path completes while socket creation is denied",
        ],
        "mechanism_metrics": {
            "semantic_payload_sha256": graph.semantic_payload_sha256(),
            "max_finite_difference_error": max_gradient_error,
            "finite_difference_error_by_term": finite_difference_error_by_term,
            "finite_difference_epsilon": FINITE_DIFFERENCE_EPSILON,
            "finite_difference_abs_tolerance": FINITE_DIFFERENCE_ABS_TOLERANCE,
            "energy_before": first.loss_before["total"],
            "energy_after": first.loss_after["total"],
            "control_l2_norm": final_norm,
            "max_observed_control_l2_norm": first.max_observed_control_l2_norm,
            "backward_calls": first.backward_calls,
            "control_map_fingerprint": first.to_control_map()["fingerprint_sha256"],
            "terminal_credit_gradient": credit,
        },
        "claim_boundary": (
            "Mechanism/plumbing validation over a synthetic structured oracle "
            "graph only; no separately supplied downstream grader verdict, "
            "final-answer artifact, or provider output enters the controller, "
            "and this is not a hosted-model reasoning benchmark."
        ),
    }


def _load_json_exact(path: Path) -> Any:
    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise SchemaValidationError(f"duplicate JSON key: {key!r}")
            result[key] = value
        return result

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=reject_duplicate_keys)


def _write_json_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "EBRT v0.5.0 mechanism-only differentiable evidence controller over "
            "a frozen public semantic graph"
        )
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser(
        "self-test", help="run deterministic offline mechanism checks"
    )
    demo = subparsers.add_parser("demo", help="optimize the built-in synthetic graph")
    demo.add_argument("--output-json", type=Path)
    validate = subparsers.add_parser("validate", help="validate an exact public graph")
    validate.add_argument("--input-json", type=Path, required=True)
    optimize = subparsers.add_parser(
        "optimize", help="validate and optimize an exact public graph"
    )
    optimize.add_argument("--input-json", type=Path, required=True)
    optimize.add_argument("--output-json", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments == ["--self-test"]:
        arguments = ["self-test"]
    if not arguments:
        arguments = ["demo"]
    args = build_parser().parse_args(arguments)

    try:
        if args.command == "self-test":
            print(_pretty_json(run_self_tests()), end="")
            return 0

        if args.command == "demo":
            graph = PublicSemanticGraph.from_mapping(_demo_payload())
        else:
            graph = PublicSemanticGraph.from_mapping(_load_json_exact(args.input_json))

        if args.command == "validate":
            report = {
                "status": "VALID",
                "schema_version": graph.schema_version,
                "graph_id": graph.graph_id,
                "semantic_payload_sha256": graph.semantic_payload_sha256(),
                "evidence_count": len(graph.evidence_nodes),
                "claim_count": len(graph.claim_nodes),
                "edge_count": len(graph.dependency_edges),
                "event_triggered": graph.revision_event.triggered,
                "claim_boundary": (
                    "Schema and provenance integrity only; no optimization or "
                    "reasoning-quality claim."
                ),
            }
            print(_pretty_json(report), end="")
            return 0

        result = DifferentiableEvidenceController().optimize(graph)
        output = result.canonical_control_map_bytes()
        if args.output_json is not None:
            _write_json_bytes(args.output_json, output)
        print(_pretty_json(result.to_control_map()), end="")
        return 0
    except (OSError, json.JSONDecodeError, SchemaValidationError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
