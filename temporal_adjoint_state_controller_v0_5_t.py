#!/usr/bin/env python3
"""EBRT v0.5-T: temporal adjoint control over a public state program.

The controller in this file is an experimental, mechanism-only successor to
the frozen v0.5.0 one-hop evidence controller.  It executes a supplied smooth
public recurrence,

    h_t = phi_t((M_t + c_t D_t) h_{t-1} + b_t x_t (1 + e_t)),

and allocates one bounded control vector either to public evidence leaves or
to public state-transition bases.  Exact local adjoints, PyTorch autograd, and
fixed finite interventions are reported separately.  No gradient crosses a
semantic adapter, JSON boundary, provider API, or language model.

The module deliberately does not generate language or call a network.  The
synthetic matrices, event, ordering, and terminal target are oracle inputs.

Examples:

    python3 temporal_adjoint_state_controller_v0_5_t.py self-test
    python3 temporal_adjoint_state_controller_v0_5_t.py validate \
      --input-json fixtures/temporal_adjoint_state_controller_v0_5_t_dev.json
    python3 temporal_adjoint_state_controller_v0_5_t.py inspect \
      --input-json fixtures/temporal_adjoint_state_controller_v0_5_t_dev.json \
      --pair-id P03 --order-variant early_correction
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import socket
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Iterator, Literal, Mapping, Sequence
from unittest import mock

import torch
from torch import Tensor


SUITE_SCHEMA_VERSION = "ebrt-temporal-paired-suite-v0.5-t.0"
EXECUTION_CONTROL_MAP_SCHEMA_VERSION = "ebrt-execution-control-map-v1.0.0"
TEMPORAL_AUDIT_SCHEMA_VERSION = "ebrt-temporal-adjoint-audit-v0.5-t.0"
CONTROLLER_NAME = "EBRT Temporal Adjoint State Controller"
CONTROLLER_VERSION = "0.5-t.0-experiment"
FLOAT_DTYPE = torch.float64
FINITE_DIFFERENCE_EPSILON = 1e-6
FINITE_DIFFERENCE_ABS_TOLERANCE = 3e-8
MANUAL_ADJOINT_ABS_TOLERANCE = 2e-12

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_ACTIVATIONS = frozenset({"identity", "tanh"})
_ALLOWED_SOURCE_KINDS = frozenset({"raw_history", "revision_event", "stable_context"})
_ALLOWED_LANES = frozenset({"leaf", "transition"})
_FORBIDDEN_NON_PUBLIC_KEYS = frozenset(
    {
        "answer",
        "answer_key",
        "correct_answer",
        "downstream_verdict",
        "evaluation_label",
        "expected_answer",
        "final_answer",
        "gold",
        "gold_label",
        "machine_success",
        "provider_output",
        "reasoning_tokens",
        "strict_grade",
    }
)


class SchemaValidationError(ValueError):
    """Raised when the temporal public suite violates its exact contract."""


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
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key)
            if key.casefold() in _FORBIDDEN_NON_PUBLIC_KEYS:
                raise SchemaValidationError(f"{path}.{key}: forbidden non-public key")
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
        parts: list[str] = []
        if unknown:
            parts.append(f"unknown keys={unknown}")
        if missing:
            parts.append(f"missing keys={missing}")
        raise SchemaValidationError(f"{path}: " + "; ".join(parts))
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
        raise SchemaValidationError(f"{path}: surrounding whitespace is forbidden")
    return value


def _optional_string(value: Any, path: str) -> str | None:
    if value is None:
        return None
    return _string(value, path)


def _boolean(value: Any, path: str) -> bool:
    if type(value) is not bool:
        raise SchemaValidationError(f"{path}: expected boolean")
    return value


def _number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SchemaValidationError(f"{path}: expected finite number")
    result = float(value)
    if not math.isfinite(result):
        raise SchemaValidationError(f"{path}: expected finite number")
    return result


def _unique_strings(
    value: Any, path: str, *, nonempty: bool = False
) -> tuple[str, ...]:
    items = _list(value, path, nonempty=nonempty)
    result = tuple(
        _string(item, f"{path}[{index}]") for index, item in enumerate(items)
    )
    if len(set(result)) != len(result):
        raise SchemaValidationError(f"{path}: duplicate values are forbidden")
    return result


def _vector(value: Any, path: str, dimension: int) -> tuple[float, ...]:
    items = _list(value, path)
    if len(items) != dimension:
        raise SchemaValidationError(f"{path}: expected length {dimension}")
    return tuple(_number(item, f"{path}[{index}]") for index, item in enumerate(items))


def _matrix(value: Any, path: str, dimension: int) -> tuple[tuple[float, ...], ...]:
    rows = _list(value, path)
    if len(rows) != dimension:
        raise SchemaValidationError(f"{path}: expected {dimension} rows")
    return tuple(
        _vector(row, f"{path}[{index}]", dimension) for index, row in enumerate(rows)
    )


def _tensor_vector(value: tuple[float, ...]) -> Tensor:
    return torch.tensor(value, dtype=FLOAT_DTYPE).detach()


def _tensor_matrix(value: tuple[tuple[float, ...], ...]) -> Tensor:
    return torch.tensor(value, dtype=FLOAT_DTYPE).detach()


@dataclass(frozen=True)
class EvidenceSpec:
    evidence_id: str
    public_summary: str
    source_kind: str

    @classmethod
    def from_mapping(cls, value: Any, path: str) -> "EvidenceSpec":
        item = _exact_mapping(
            value, path, {"evidence_id", "public_summary", "source_kind"}
        )
        source_kind = _string(item["source_kind"], f"{path}.source_kind")
        if source_kind not in _ALLOWED_SOURCE_KINDS:
            raise SchemaValidationError(
                f"{path}.source_kind: expected one of {sorted(_ALLOWED_SOURCE_KINDS)}"
            )
        return cls(
            evidence_id=_string(item["evidence_id"], f"{path}.evidence_id"),
            public_summary=_string(item["public_summary"], f"{path}.public_summary"),
            source_kind=source_kind,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OperatorSpec:
    operator_id: str
    public_name: str
    activation: str
    evidence_id: str | None
    transition_control_id: str | None
    base_matrix: tuple[tuple[float, ...], ...]
    evidence_direction: tuple[float, ...]
    transition_basis: tuple[tuple[float, ...], ...]

    @classmethod
    def from_mapping(cls, value: Any, path: str, dimension: int) -> "OperatorSpec":
        item = _exact_mapping(
            value,
            path,
            {
                "operator_id",
                "public_name",
                "activation",
                "evidence_id",
                "transition_control_id",
                "base_matrix",
                "evidence_direction",
                "transition_basis",
            },
        )
        activation = _string(item["activation"], f"{path}.activation")
        if activation not in _ALLOWED_ACTIVATIONS:
            raise SchemaValidationError(
                f"{path}.activation: expected one of {sorted(_ALLOWED_ACTIVATIONS)}"
            )
        result = cls(
            operator_id=_string(item["operator_id"], f"{path}.operator_id"),
            public_name=_string(item["public_name"], f"{path}.public_name"),
            activation=activation,
            evidence_id=_optional_string(item["evidence_id"], f"{path}.evidence_id"),
            transition_control_id=_optional_string(
                item["transition_control_id"], f"{path}.transition_control_id"
            ),
            base_matrix=_matrix(item["base_matrix"], f"{path}.base_matrix", dimension),
            evidence_direction=_vector(
                item["evidence_direction"], f"{path}.evidence_direction", dimension
            ),
            transition_basis=_matrix(
                item["transition_basis"], f"{path}.transition_basis", dimension
            ),
        )
        evidence_norm = math.sqrt(
            sum(item * item for item in result.evidence_direction)
        )
        basis_norm = math.sqrt(
            sum(item * item for row in result.transition_basis for item in row)
        )
        if result.evidence_id is None and evidence_norm != 0.0:
            raise SchemaValidationError(
                f"{path}.evidence_direction: must be exact zero without evidence_id"
            )
        if result.evidence_id is not None and not math.isclose(
            evidence_norm, 1.0, rel_tol=0.0, abs_tol=1e-12
        ):
            raise SchemaValidationError(
                f"{path}.evidence_direction: controlled evidence basis must have L2 norm 1"
            )
        if result.transition_control_id is None and basis_norm != 0.0:
            raise SchemaValidationError(
                f"{path}.transition_basis: must be exact zero without control id"
            )
        if result.transition_control_id is not None and not math.isclose(
            basis_norm, 1.0, rel_tol=0.0, abs_tol=1e-12
        ):
            raise SchemaValidationError(
                f"{path}.transition_basis: controlled transition basis must have Frobenius norm 1"
            )
        return result

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PairParameters:
    pair_id: str
    evidence_values: tuple[tuple[str, float], ...]
    terminal_decision_target: float

    @classmethod
    def from_mapping(
        cls, value: Any, path: str, evidence_ids: tuple[str, ...]
    ) -> "PairParameters":
        item = _exact_mapping(
            value,
            path,
            {"pair_id", "evidence_values", "terminal_decision_target"},
        )
        raw_values = _exact_mapping(
            item["evidence_values"], f"{path}.evidence_values", set(evidence_ids)
        )
        values = tuple(
            (
                evidence_id,
                _number(
                    raw_values[evidence_id], f"{path}.evidence_values.{evidence_id}"
                ),
            )
            for evidence_id in evidence_ids
        )
        target = _number(
            item["terminal_decision_target"], f"{path}.terminal_decision_target"
        )
        if not -1.0 <= target <= 1.0:
            raise SchemaValidationError(
                f"{path}.terminal_decision_target: must be in [-1, 1]"
            )
        return cls(
            pair_id=_string(item["pair_id"], f"{path}.pair_id"),
            evidence_values=values,
            terminal_decision_target=target,
        )

    def evidence_value_map(self) -> dict[str, float]:
        return dict(self.evidence_values)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pair_id": self.pair_id,
            "evidence_values": dict(self.evidence_values),
            "terminal_decision_target": self.terminal_decision_target,
        }


@dataclass(frozen=True)
class TraceOrder:
    order_variant: str
    operator_ids: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value: Any, path: str) -> "TraceOrder":
        item = _exact_mapping(value, path, {"order_variant", "operator_ids"})
        return cls(
            order_variant=_string(item["order_variant"], f"{path}.order_variant"),
            operator_ids=_unique_strings(
                item["operator_ids"], f"{path}.operator_ids", nonempty=True
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_variant": self.order_variant,
            "operator_ids": list(self.operator_ids),
        }


@dataclass(frozen=True)
class RevisionSpec:
    event_id: str
    triggered: bool
    correction_evidence_id: str
    decision_state_axis: str
    stable_state_axis: str

    @classmethod
    def from_mapping(cls, value: Any, path: str) -> "RevisionSpec":
        item = _exact_mapping(
            value,
            path,
            {
                "event_id",
                "triggered",
                "correction_evidence_id",
                "decision_state_axis",
                "stable_state_axis",
            },
        )
        return cls(
            event_id=_string(item["event_id"], f"{path}.event_id"),
            triggered=_boolean(item["triggered"], f"{path}.triggered"),
            correction_evidence_id=_string(
                item["correction_evidence_id"], f"{path}.correction_evidence_id"
            ),
            decision_state_axis=_string(
                item["decision_state_axis"], f"{path}.decision_state_axis"
            ),
            stable_state_axis=_string(
                item["stable_state_axis"], f"{path}.stable_state_axis"
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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
            raise SchemaValidationError(f"{path}.deterministic: must be true")
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
class TemporalPairedSuite:
    schema_version: str
    suite_id: str
    state_axes: tuple[str, ...]
    initial_state: tuple[float, ...]
    evidence_specs: tuple[EvidenceSpec, ...]
    operators: tuple[OperatorSpec, ...]
    leaf_control_ids: tuple[str, ...]
    transition_control_ids: tuple[str, ...]
    trace_orders: tuple[TraceOrder, ...]
    pair_parameters: tuple[PairParameters, ...]
    sham_source_index_by_target: tuple[int, ...]
    revision_event: RevisionSpec
    provenance: Provenance
    claim_boundary: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value: Any) -> "TemporalPairedSuite":
        _reject_forbidden_keys(value)
        root = _exact_mapping(
            value,
            "$",
            {
                "schema_version",
                "suite_id",
                "state_axes",
                "initial_state",
                "evidence_specs",
                "operators",
                "leaf_control_ids",
                "transition_control_ids",
                "trace_orders",
                "pair_parameters",
                "sham_source_index_by_target",
                "revision_event",
                "provenance",
                "claim_boundary",
            },
        )
        schema_version = _string(root["schema_version"], "$.schema_version")
        if schema_version != SUITE_SCHEMA_VERSION:
            raise SchemaValidationError(
                f"$.schema_version: expected {SUITE_SCHEMA_VERSION!r}"
            )
        state_axes = _unique_strings(root["state_axes"], "$.state_axes", nonempty=True)
        dimension = len(state_axes)
        evidence_specs = tuple(
            EvidenceSpec.from_mapping(item, f"$.evidence_specs[{index}]")
            for index, item in enumerate(
                _list(root["evidence_specs"], "$.evidence_specs", nonempty=True)
            )
        )
        evidence_ids = tuple(item.evidence_id for item in evidence_specs)
        if len(set(evidence_ids)) != len(evidence_ids):
            raise SchemaValidationError("duplicate evidence_id values are forbidden")
        operators = tuple(
            OperatorSpec.from_mapping(item, f"$.operators[{index}]", dimension)
            for index, item in enumerate(
                _list(root["operators"], "$.operators", nonempty=True)
            )
        )
        operator_ids = tuple(item.operator_id for item in operators)
        if len(set(operator_ids)) != len(operator_ids):
            raise SchemaValidationError("duplicate operator_id values are forbidden")
        leaf_control_ids = _unique_strings(
            root["leaf_control_ids"], "$.leaf_control_ids", nonempty=True
        )
        transition_control_ids = _unique_strings(
            root["transition_control_ids"],
            "$.transition_control_ids",
            nonempty=True,
        )
        if len(leaf_control_ids) != len(transition_control_ids):
            raise SchemaValidationError(
                "leaf and transition lanes must expose the same control count"
            )
        if set(leaf_control_ids) != set(evidence_ids):
            raise SchemaValidationError(
                "leaf_control_ids must be an exact permutation of evidence ids"
            )
        operator_evidence = tuple(
            item.evidence_id for item in operators if item.evidence_id is not None
        )
        operator_controls = tuple(
            item.transition_control_id
            for item in operators
            if item.transition_control_id is not None
        )
        if len(operator_evidence) != len(set(operator_evidence)) or set(
            operator_evidence
        ) != set(evidence_ids):
            raise SchemaValidationError(
                "each evidence id must occur on exactly one operator"
            )
        if len(operator_controls) != len(set(operator_controls)) or set(
            operator_controls
        ) != set(transition_control_ids):
            raise SchemaValidationError(
                "each transition control id must occur on exactly one operator"
            )
        trace_orders = tuple(
            TraceOrder.from_mapping(item, f"$.trace_orders[{index}]")
            for index, item in enumerate(
                _list(root["trace_orders"], "$.trace_orders", nonempty=True)
            )
        )
        variants = tuple(item.order_variant for item in trace_orders)
        if len(set(variants)) != len(variants) or len(variants) < 2:
            raise SchemaValidationError(
                "trace orders require at least two unique order variants"
            )
        for order in trace_orders:
            if set(order.operator_ids) != set(operator_ids) or len(
                order.operator_ids
            ) != len(operator_ids):
                raise SchemaValidationError(
                    f"trace {order.order_variant!r} must be an exact operator permutation"
                )
        pair_parameters = tuple(
            PairParameters.from_mapping(
                item, f"$.pair_parameters[{index}]", evidence_ids
            )
            for index, item in enumerate(
                _list(root["pair_parameters"], "$.pair_parameters", nonempty=True)
            )
        )
        pair_ids = tuple(item.pair_id for item in pair_parameters)
        if len(set(pair_ids)) != len(pair_ids):
            raise SchemaValidationError("duplicate pair_id values are forbidden")
        sham_values = _list(
            root["sham_source_index_by_target"], "$.sham_source_index_by_target"
        )
        if len(sham_values) != len(transition_control_ids):
            raise SchemaValidationError(
                "sham permutation length must equal the transition control count"
            )
        sham = tuple(
            int(item)
            if type(item) is int
            else (_ for _ in ()).throw(
                SchemaValidationError(
                    f"$.sham_source_index_by_target[{index}]: expected integer"
                )
            )
            for index, item in enumerate(sham_values)
        )
        if sorted(sham) != list(range(len(transition_control_ids))):
            raise SchemaValidationError("sham indices must form an exact permutation")
        if sham == tuple(range(len(sham))):
            raise SchemaValidationError("sham permutation must not be identity")
        revision_event = RevisionSpec.from_mapping(
            root["revision_event"], "$.revision_event"
        )
        if revision_event.correction_evidence_id not in set(evidence_ids):
            raise SchemaValidationError(
                "revision_event.correction_evidence_id is unknown"
            )
        if revision_event.decision_state_axis not in set(state_axes):
            raise SchemaValidationError("revision decision state axis is unknown")
        if revision_event.stable_state_axis not in set(state_axes):
            raise SchemaValidationError("revision stable state axis is unknown")
        suite = cls(
            schema_version=schema_version,
            suite_id=_string(root["suite_id"], "$.suite_id"),
            state_axes=state_axes,
            initial_state=_vector(root["initial_state"], "$.initial_state", dimension),
            evidence_specs=evidence_specs,
            operators=operators,
            leaf_control_ids=leaf_control_ids,
            transition_control_ids=transition_control_ids,
            trace_orders=trace_orders,
            pair_parameters=pair_parameters,
            sham_source_index_by_target=sham,
            revision_event=revision_event,
            provenance=Provenance.from_mapping(root["provenance"], "$.provenance"),
            claim_boundary=_unique_strings(
                root["claim_boundary"], "$.claim_boundary", nonempty=True
            ),
        )
        if suite.semantic_payload_sha256() != suite.provenance.semantic_payload_sha256:
            raise SchemaValidationError(
                "$.provenance.semantic_payload_sha256: semantic payload hash mismatch; "
                f"expected {suite.semantic_payload_sha256()}"
            )
        return suite

    def semantic_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "suite_id": self.suite_id,
            "state_axes": list(self.state_axes),
            "initial_state": list(self.initial_state),
            "evidence_specs": [item.to_dict() for item in self.evidence_specs],
            "operators": [item.to_dict() for item in self.operators],
            "leaf_control_ids": list(self.leaf_control_ids),
            "transition_control_ids": list(self.transition_control_ids),
            "trace_orders": [item.to_dict() for item in self.trace_orders],
            "pair_parameters": [item.to_dict() for item in self.pair_parameters],
            "sham_source_index_by_target": list(self.sham_source_index_by_target),
            "revision_event": self.revision_event.to_dict(),
        }

    def semantic_payload_sha256(self) -> str:
        return _sha256_json(self.semantic_payload())

    def to_dict(self) -> dict[str, Any]:
        payload = self.semantic_payload()
        payload["provenance"] = self.provenance.to_dict()
        payload["claim_boundary"] = list(self.claim_boundary)
        return payload

    def materialize(self, pair_id: str, order_variant: str) -> "FrozenTemporalProgram":
        pairs = {item.pair_id: item for item in self.pair_parameters}
        orders = {item.order_variant: item for item in self.trace_orders}
        if pair_id not in pairs:
            raise KeyError(f"unknown pair_id {pair_id!r}")
        if order_variant not in orders:
            raise KeyError(f"unknown order_variant {order_variant!r}")
        pair = pairs[pair_id]
        order = orders[order_variant]
        operator_by_id = {item.operator_id: item for item in self.operators}
        evidence_values = pair.evidence_value_map()
        floors: list[FrozenFloor] = []
        for ordinal, operator_id in enumerate(order.operator_ids, start=1):
            operator = operator_by_id[operator_id]
            floors.append(
                FrozenFloor(
                    floor_id=f"F{ordinal:02d}:{operator.operator_id}",
                    floor_ordinal=ordinal,
                    operator_id=operator.operator_id,
                    public_name=operator.public_name,
                    activation=operator.activation,
                    evidence_id=operator.evidence_id,
                    evidence_value=(
                        evidence_values[operator.evidence_id]
                        if operator.evidence_id is not None
                        else 0.0
                    ),
                    transition_control_id=operator.transition_control_id,
                    base_matrix=_tensor_matrix(operator.base_matrix),
                    evidence_direction=_tensor_vector(operator.evidence_direction),
                    transition_basis=_tensor_matrix(operator.transition_basis),
                )
            )
        evidence_floor = {
            floor.evidence_id: floor
            for floor in floors
            if floor.evidence_id is not None
        }
        transition_floor = {
            floor.transition_control_id: floor
            for floor in floors
            if floor.transition_control_id is not None
        }
        return FrozenTemporalProgram(
            suite_id=self.suite_id,
            semantic_payload_sha256=self.semantic_payload_sha256(),
            pair_id=pair_id,
            order_variant=order_variant,
            state_axes=self.state_axes,
            initial_state=_tensor_vector(self.initial_state),
            floors=tuple(floors),
            leaf_control_ids=self.leaf_control_ids,
            transition_control_ids=self.transition_control_ids,
            leaf_control_floor_ids=tuple(
                evidence_floor[item].floor_id for item in self.leaf_control_ids
            ),
            leaf_control_floor_ordinals=tuple(
                evidence_floor[item].floor_ordinal for item in self.leaf_control_ids
            ),
            transition_control_floor_ids=tuple(
                transition_floor[item].floor_id for item in self.transition_control_ids
            ),
            transition_control_floor_ordinals=tuple(
                transition_floor[item].floor_ordinal
                for item in self.transition_control_ids
            ),
            terminal_decision_target=pair.terminal_decision_target,
            decision_state_index=self.state_axes.index(
                self.revision_event.decision_state_axis
            ),
            stable_state_index=self.state_axes.index(
                self.revision_event.stable_state_axis
            ),
            event_id=self.revision_event.event_id,
            event_triggered=self.revision_event.triggered,
            claim_boundary=self.claim_boundary,
        )


@dataclass(frozen=True)
class FrozenFloor:
    floor_id: str
    floor_ordinal: int
    operator_id: str
    public_name: str
    activation: str
    evidence_id: str | None
    evidence_value: float
    transition_control_id: str | None
    base_matrix: Tensor
    evidence_direction: Tensor
    transition_basis: Tensor


@dataclass(frozen=True)
class FrozenTemporalProgram:
    suite_id: str
    semantic_payload_sha256: str
    pair_id: str
    order_variant: str
    state_axes: tuple[str, ...]
    initial_state: Tensor
    floors: tuple[FrozenFloor, ...]
    leaf_control_ids: tuple[str, ...]
    transition_control_ids: tuple[str, ...]
    leaf_control_floor_ids: tuple[str, ...]
    leaf_control_floor_ordinals: tuple[int, ...]
    transition_control_floor_ids: tuple[str, ...]
    transition_control_floor_ordinals: tuple[int, ...]
    terminal_decision_target: float
    decision_state_index: int
    stable_state_index: int
    event_id: str
    event_triggered: bool
    claim_boundary: tuple[str, ...]

    def control_ids(self, lane: str) -> tuple[str, ...]:
        if lane == "leaf":
            return self.leaf_control_ids
        if lane == "transition":
            return self.transition_control_ids
        raise ValueError(f"unknown control lane {lane!r}")

    def control_floor_ids(self, lane: str) -> tuple[str, ...]:
        if lane == "leaf":
            return self.leaf_control_floor_ids
        if lane == "transition":
            return self.transition_control_floor_ids
        raise ValueError(f"unknown control lane {lane!r}")

    def control_floor_ordinals(self, lane: str) -> tuple[int, ...]:
        if lane == "leaf":
            return self.leaf_control_floor_ordinals
        if lane == "transition":
            return self.transition_control_floor_ordinals
        raise ValueError(f"unknown control lane {lane!r}")


@dataclass(frozen=True)
class ControllerConfig:
    revision_steps: int = 300
    learning_rate: float = 0.06
    max_control_abs: float = 0.75
    max_control_l2_norm: float = 0.55
    revision_consistency_weight: float = 1.0
    stable_state_drift_weight: float = 1.0
    control_l2_weight: float = 0.01
    finite_control_step: float = 0.10
    active_leverage_relative_threshold: float = 0.25
    role_delta: float = 0.02
    acceptance_tolerance: float = 1e-12
    numeric_precision: int = 12

    def validate(self) -> None:
        if type(self.revision_steps) is not int or self.revision_steps < 1:
            raise ValueError("revision_steps must be an integer >= 1")
        for name in (
            "learning_rate",
            "max_control_abs",
            "max_control_l2_norm",
            "revision_consistency_weight",
            "stable_state_drift_weight",
            "control_l2_weight",
            "finite_control_step",
            "active_leverage_relative_threshold",
            "role_delta",
            "acceptance_tolerance",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and >= 0")
        if self.learning_rate == 0.0:
            raise ValueError("learning_rate must be > 0")
        if not 0.0 < self.max_control_l2_norm <= self.max_control_abs:
            raise ValueError("max_control_l2_norm must be in (0, max_control_abs]")
        if not 0.0 < self.finite_control_step <= self.max_control_l2_norm:
            raise ValueError("finite_control_step must be in (0, max_control_l2_norm]")
        if not 0.0 < self.active_leverage_relative_threshold <= 1.0:
            raise ValueError("active_leverage_relative_threshold must be in (0, 1]")
        if not 6 <= self.numeric_precision <= 16:
            raise ValueError("numeric_precision must be in [6, 16]")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LossTerms:
    revision_consistency: Tensor
    stable_state_drift: Tensor
    control_l2: Tensor
    total: Tensor

    def tensor_dict(self) -> dict[str, Tensor]:
        return {
            "revision_consistency": self.revision_consistency,
            "stable_state_drift": self.stable_state_drift,
            "control_l2": self.control_l2,
            "total": self.total,
        }

    def scalar_dict(self) -> dict[str, float]:
        return {
            key: float(value.detach().item())
            for key, value in self.tensor_dict().items()
        }


@dataclass(frozen=True)
class OptimizationResult:
    program: FrozenTemporalProgram
    config: ControllerConfig
    lane: Literal["leaf", "transition"]
    status: str
    baseline_terminal_state: Tensor
    final_terminal_state: Tensor
    baseline_trajectory: tuple[Tensor, ...]
    final_trajectory: tuple[Tensor, ...]
    final_deltas: Tensor
    first_gradient: Tensor
    loss_before: dict[str, float]
    loss_after: dict[str, float]
    energy_history: tuple[float, ...]
    backward_calls: int
    accepted: bool
    rolled_back: bool
    best_iteration: int
    max_observed_control_l2_norm: float

    def _rounded(self, value: float) -> float:
        rounded = round(float(value), self.config.numeric_precision)
        return 0.0 if rounded == -0.0 else rounded

    def execution_control_map_without_fingerprint(self) -> dict[str, Any]:
        controls: list[dict[str, Any]] = []
        ids = self.program.control_ids(self.lane)
        floor_ids = self.program.control_floor_ids(self.lane)
        ordinals = self.program.control_floor_ordinals(self.lane)
        target_kind = "evidence" if self.lane == "leaf" else "transition"
        for target_id, floor_id, ordinal, delta_tensor in zip(
            ids, floor_ids, ordinals, self.final_deltas, strict=True
        ):
            delta = float(delta_tensor.item())
            if delta > self.config.role_delta:
                role = "increase"
            elif delta < -self.config.role_delta:
                role = "decrease"
            else:
                role = "preserve"
            controls.append(
                {
                    "target_kind": target_kind,
                    "target_id": target_id,
                    "floor_id": floor_id,
                    "floor_ordinal": ordinal,
                    "role": role,
                    "delta": self._rounded(delta),
                    "applied_value": self._rounded(
                        1.0 + delta if self.lane == "leaf" else delta
                    ),
                }
            )
        controls.sort(
            key=lambda item: (
                item["floor_ordinal"],
                item["target_kind"],
                item["target_id"],
            )
        )
        return {
            "schema_version": EXECUTION_CONTROL_MAP_SCHEMA_VERSION,
            "controller": {
                "name": CONTROLLER_NAME,
                "version": CONTROLLER_VERSION,
                "lane": self.lane,
                "dtype": "float64",
                "control_parameterization": (
                    "delta=max_control_abs*tanh(u), projected to shared L2 budget"
                ),
                "gradient_boundary": (
                    "frozen public recurrence only; adapter, JSON, provider, and "
                    "generation are stop-gradient boundaries"
                ),
            },
            "source": {
                "suite_id": self.program.suite_id,
                "semantic_payload_sha256": self.program.semantic_payload_sha256,
                "pair_id": self.program.pair_id,
                "order_variant": self.program.order_variant,
                "event_id": self.program.event_id,
                "event_triggered": self.program.event_triggered,
            },
            "status": self.status,
            "controls": controls,
            "budget": {
                "control_count": len(controls),
                "max_control_abs": self.config.max_control_abs,
                "max_control_l2_norm": self.config.max_control_l2_norm,
                "observed_control_l2_norm": self._rounded(
                    torch.linalg.vector_norm(self.final_deltas).item()
                ),
            },
            "surrogate": {
                "objective_before": {
                    key: self._rounded(value) for key, value in self.loss_before.items()
                },
                "objective_after": {
                    key: self._rounded(value) for key, value in self.loss_after.items()
                },
                "terminal_state_before": {
                    axis: self._rounded(self.baseline_terminal_state[index].item())
                    for index, axis in enumerate(self.program.state_axes)
                },
                "terminal_state_after": {
                    axis: self._rounded(self.final_terminal_state[index].item())
                    for index, axis in enumerate(self.program.state_axes)
                },
            },
            "optimization": {
                "backward_calls": self.backward_calls,
                "accepted": self.accepted,
                "rolled_back": self.rolled_back,
                "best_iteration": self.best_iteration,
                "max_observed_control_l2_norm": self._rounded(
                    self.max_observed_control_l2_norm
                ),
            },
            "claim_boundary": [
                "Actionable controls are projections of a synthetic public surrogate.",
                "No provider or final generation is executed by this map.",
                "A lower surrogate objective is not evidence of better hosted-model reasoning.",
            ],
        }

    def to_execution_control_map(self) -> dict[str, Any]:
        payload = self.execution_control_map_without_fingerprint()
        payload["fingerprint_sha256"] = _sha256_json(payload)
        return payload

    def canonical_execution_control_map_bytes(self) -> bytes:
        return _canonical_json_bytes(
            self.to_execution_control_map(), trailing_newline=True
        )


class TemporalAdjointStateController:
    """Float64 controller for one immutable public temporal program."""

    def __init__(self, config: ControllerConfig | None = None) -> None:
        self.config = config or ControllerConfig()
        self.config.validate()

    @staticmethod
    def controls_from_logits(logits: Tensor, max_abs: float) -> Tensor:
        if logits.dtype != FLOAT_DTYPE or logits.ndim != 1:
            raise TypeError("logits must be a rank-1 torch.float64 tensor")
        return max_abs * torch.tanh(logits)

    @staticmethod
    def _activate(value: Tensor, activation: str) -> Tensor:
        if activation == "tanh":
            return torch.tanh(value)
        if activation == "identity":
            return value
        raise ValueError(f"unknown activation {activation!r}")

    @staticmethod
    def _activation_derivative(state: Tensor, activation: str) -> Tensor:
        if activation == "tanh":
            return 1.0 - state.square()
        if activation == "identity":
            return torch.ones_like(state)
        raise ValueError(f"unknown activation {activation!r}")

    def rollout(
        self,
        program: FrozenTemporalProgram,
        *,
        leaf_deltas: Tensor | None = None,
        transition_deltas: Tensor | None = None,
    ) -> tuple[Tensor, tuple[Tensor, ...]]:
        leaf = (
            torch.zeros(len(program.leaf_control_ids), dtype=FLOAT_DTYPE)
            if leaf_deltas is None
            else leaf_deltas
        )
        transition = (
            torch.zeros(len(program.transition_control_ids), dtype=FLOAT_DTYPE)
            if transition_deltas is None
            else transition_deltas
        )
        if leaf.dtype != FLOAT_DTYPE or leaf.shape != (len(program.leaf_control_ids),):
            raise TypeError("leaf_deltas has the wrong dtype or shape")
        if transition.dtype != FLOAT_DTYPE or transition.shape != (
            len(program.transition_control_ids),
        ):
            raise TypeError("transition_deltas has the wrong dtype or shape")
        leaf_index = {
            item: index for index, item in enumerate(program.leaf_control_ids)
        }
        transition_index = {
            item: index for index, item in enumerate(program.transition_control_ids)
        }
        state = program.initial_state.clone()
        trajectory = [state]
        for floor in program.floors:
            matrix = floor.base_matrix
            if floor.transition_control_id is not None:
                matrix = matrix + (
                    transition[transition_index[floor.transition_control_id]]
                    * floor.transition_basis
                )
            evidence_term = floor.evidence_direction * floor.evidence_value
            if floor.evidence_id is not None:
                evidence_term = evidence_term * (
                    1.0 + leaf[leaf_index[floor.evidence_id]]
                )
            preactivation = matrix @ state + evidence_term
            state = self._activate(preactivation, floor.activation)
            trajectory.append(state)
        return state, tuple(trajectory)

    def loss_terms(
        self,
        program: FrozenTemporalProgram,
        terminal_state: Tensor,
        controls: Tensor,
        baseline_stable_value: Tensor,
    ) -> LossTerms:
        revision = (
            terminal_state[program.decision_state_index]
            - program.terminal_decision_target
        ).square()
        stable = (
            terminal_state[program.stable_state_index] - baseline_stable_value
        ).square()
        control = torch.sum(controls.square())
        total = (
            self.config.revision_consistency_weight * revision
            + self.config.stable_state_drift_weight * stable
            + self.config.control_l2_weight * control
        )
        return LossTerms(
            revision_consistency=revision,
            stable_state_drift=stable,
            control_l2=control,
            total=total,
        )

    def _project_logits_(self, logits: Tensor) -> float:
        with torch.no_grad():
            controls = self.controls_from_logits(logits, self.config.max_control_abs)
            norm = float(torch.linalg.vector_norm(controls).item())
            if norm > self.config.max_control_l2_norm:
                controls.mul_(self.config.max_control_l2_norm / norm)
            ratio = (controls / self.config.max_control_abs).clamp(
                min=-1.0 + 1e-12, max=1.0 - 1e-12
            )
            logits.copy_(torch.atanh(ratio))
            return float(torch.linalg.vector_norm(controls).item())

    def optimize(
        self, program: FrozenTemporalProgram, lane: Literal["leaf", "transition"]
    ) -> OptimizationResult:
        if lane not in _ALLOWED_LANES:
            raise ValueError(f"lane must be one of {sorted(_ALLOWED_LANES)}")
        control_ids = program.control_ids(lane)
        baseline_controls = torch.zeros(len(control_ids), dtype=FLOAT_DTYPE)
        with torch.no_grad():
            baseline_terminal, baseline_trajectory = self.rollout(program)
            baseline_stable = baseline_terminal[program.stable_state_index].clone()
            baseline_terms_t = self.loss_terms(
                program,
                baseline_terminal,
                baseline_controls,
                baseline_stable,
            )
        baseline_terms = baseline_terms_t.scalar_dict()
        if not program.event_triggered:
            return OptimizationResult(
                program=program,
                config=self.config,
                lane=lane,
                status="NO_EVENT_IDENTITY",
                baseline_terminal_state=baseline_terminal,
                final_terminal_state=baseline_terminal.clone(),
                baseline_trajectory=baseline_trajectory,
                final_trajectory=tuple(item.clone() for item in baseline_trajectory),
                final_deltas=baseline_controls,
                first_gradient=baseline_controls.clone(),
                loss_before=baseline_terms,
                loss_after=baseline_terms.copy(),
                energy_history=(baseline_terms["total"],),
                backward_calls=0,
                accepted=False,
                rolled_back=False,
                best_iteration=0,
                max_observed_control_l2_norm=0.0,
            )
        logits = torch.zeros(len(control_ids), dtype=FLOAT_DTYPE, requires_grad=True)
        optimizer = torch.optim.Adam([logits], lr=self.config.learning_rate)
        best_controls = baseline_controls.clone()
        best_energy = baseline_terms["total"]
        best_iteration = 0
        first_gradient = baseline_controls.clone()
        energy_history = [best_energy]
        backward_calls = 0
        max_norm = 0.0
        for iteration in range(1, self.config.revision_steps + 1):
            optimizer.zero_grad(set_to_none=True)
            controls = self.controls_from_logits(logits, self.config.max_control_abs)
            kwargs = (
                {"leaf_deltas": controls}
                if lane == "leaf"
                else {"transition_deltas": controls}
            )
            terminal, _ = self.rollout(program, **kwargs)
            terms = self.loss_terms(program, terminal, controls, baseline_stable)
            if not torch.isfinite(terms.total):
                break
            terms.total.backward()
            backward_calls += 1
            if logits.grad is None or not torch.isfinite(logits.grad).all():
                break
            if iteration == 1:
                # Report sensitivity in standardized delta coordinates, not the
                # scale-dependent unconstrained logit coordinates.
                first_gradient = (
                    logits.grad.detach().clone() / self.config.max_control_abs
                )
            optimizer.step()
            max_norm = max(max_norm, self._project_logits_(logits))
            with torch.no_grad():
                candidate = self.controls_from_logits(
                    logits, self.config.max_control_abs
                )
                kwargs = (
                    {"leaf_deltas": candidate}
                    if lane == "leaf"
                    else {"transition_deltas": candidate}
                )
                terminal, _ = self.rollout(program, **kwargs)
                candidate_terms = self.loss_terms(
                    program, terminal, candidate, baseline_stable
                )
                energy = float(candidate_terms.total.item())
                if not math.isfinite(energy):
                    break
                energy_history.append(energy)
                if energy < best_energy:
                    best_energy = energy
                    best_controls = candidate.detach().clone()
                    best_iteration = iteration
        accepted = best_energy < (
            baseline_terms["total"] - self.config.acceptance_tolerance
        )
        final_controls = best_controls if accepted else baseline_controls
        kwargs = (
            {"leaf_deltas": final_controls}
            if lane == "leaf"
            else {"transition_deltas": final_controls}
        )
        with torch.no_grad():
            final_terminal, final_trajectory = self.rollout(program, **kwargs)
            final_terms_t = self.loss_terms(
                program, final_terminal, final_controls, baseline_stable
            )
        return OptimizationResult(
            program=program,
            config=self.config,
            lane=lane,
            status="CONTROL_ACCEPTED" if accepted else "ROLLED_BACK_TO_IDENTITY",
            baseline_terminal_state=baseline_terminal,
            final_terminal_state=final_terminal,
            baseline_trajectory=baseline_trajectory,
            final_trajectory=final_trajectory,
            final_deltas=final_controls,
            first_gradient=first_gradient,
            loss_before=baseline_terms,
            loss_after=final_terms_t.scalar_dict(),
            energy_history=tuple(energy_history),
            backward_calls=backward_calls,
            accepted=accepted,
            rolled_back=not accepted,
            best_iteration=best_iteration,
            max_observed_control_l2_norm=max_norm,
        )

    def direct_control_gradient(
        self, program: FrozenTemporalProgram, lane: Literal["leaf", "transition"]
    ) -> Tensor:
        if not program.event_triggered:
            return torch.zeros(len(program.control_ids(lane)), dtype=FLOAT_DTYPE)
        controls = torch.zeros(
            len(program.control_ids(lane)), dtype=FLOAT_DTYPE, requires_grad=True
        )
        baseline_terminal, _ = self.rollout(program)
        baseline_stable = baseline_terminal[program.stable_state_index].detach()
        kwargs = (
            {"leaf_deltas": controls}
            if lane == "leaf"
            else {"transition_deltas": controls}
        )
        terminal, _ = self.rollout(program, **kwargs)
        terms = self.loss_terms(program, terminal, controls, baseline_stable)
        terms.total.backward()
        if controls.grad is None:
            raise RuntimeError("direct control gradient was not populated")
        return controls.grad.detach().clone()

    def manual_adjoint_gradient(
        self, program: FrozenTemporalProgram, lane: Literal["leaf", "transition"]
    ) -> Tensor:
        if not program.event_triggered:
            return torch.zeros(len(program.control_ids(lane)), dtype=FLOAT_DTYPE)
        terminal, trajectory = self.rollout(program)
        terminal_adjoint = torch.zeros_like(terminal)
        terminal_adjoint[program.decision_state_index] = (
            2.0
            * self.config.revision_consistency_weight
            * (
                terminal[program.decision_state_index]
                - program.terminal_decision_target
            )
        )
        # Stable drift is defined relative to this exact neutral terminal, so
        # its neutral adjoint contribution is exactly zero.
        adjoint = terminal_adjoint
        gradients = torch.zeros(len(program.control_ids(lane)), dtype=FLOAT_DTYPE)
        control_index = {
            item: index for index, item in enumerate(program.control_ids(lane))
        }
        for floor_index in range(len(program.floors) - 1, -1, -1):
            floor = program.floors[floor_index]
            state_before = trajectory[floor_index]
            state_after = trajectory[floor_index + 1]
            local = adjoint * self._activation_derivative(state_after, floor.activation)
            if lane == "leaf" and floor.evidence_id is not None:
                gradients[control_index[floor.evidence_id]] = torch.dot(
                    local, floor.evidence_direction * floor.evidence_value
                )
            if lane == "transition" and floor.transition_control_id is not None:
                gradients[control_index[floor.transition_control_id]] = torch.dot(
                    local, floor.transition_basis @ state_before
                )
            adjoint = floor.base_matrix.T @ local
        return gradients

    def finite_control_leverage(
        self, program: FrozenTemporalProgram, lane: Literal["leaf", "transition"]
    ) -> tuple[dict[str, float], dict[str, float]]:
        gradient = self.direct_control_gradient(program, lane)
        baseline_terminal, _ = self.rollout(program)
        baseline_stable = baseline_terminal[program.stable_state_index].detach()
        zeros = torch.zeros(len(program.control_ids(lane)), dtype=FLOAT_DTYPE)
        baseline_task = self.loss_terms(
            program, baseline_terminal, zeros, baseline_stable
        )
        leverage: dict[str, float] = {}
        applied_step: dict[str, float] = {}
        for index, control_id in enumerate(program.control_ids(lane)):
            step = 0.0
            if float(gradient[index].item()) > 0.0:
                step = -self.config.finite_control_step
            elif float(gradient[index].item()) < 0.0:
                step = self.config.finite_control_step
            candidate = zeros.clone()
            candidate[index] = step
            kwargs = (
                {"leaf_deltas": candidate}
                if lane == "leaf"
                else {"transition_deltas": candidate}
            )
            terminal, _ = self.rollout(program, **kwargs)
            terms = self.loss_terms(program, terminal, candidate, baseline_stable)
            # Exclude regularization from leverage: it measures realized task
            # effect under the same externally fixed finite intervention.
            base_task_value = (
                self.config.revision_consistency_weight
                * baseline_task.revision_consistency
                + self.config.stable_state_drift_weight
                * baseline_task.stable_state_drift
            )
            candidate_task_value = (
                self.config.revision_consistency_weight * terms.revision_consistency
                + self.config.stable_state_drift_weight * terms.stable_state_drift
            )
            leverage[control_id] = float(
                (base_task_value - candidate_task_value).item()
            )
            applied_step[control_id] = step
        return leverage, applied_step

    def structural_control_reachability(
        self, program: FrozenTemporalProgram, lane: Literal["leaf", "transition"]
    ) -> dict[str, bool]:
        control_to_floor: dict[str, int] = {}
        immediate_axes: dict[str, Tensor] = {}
        for index, floor in enumerate(program.floors):
            if lane == "leaf" and floor.evidence_id is not None:
                control_to_floor[floor.evidence_id] = index
                immediate_axes[floor.evidence_id] = floor.evidence_direction != 0.0
            if lane == "transition" and floor.transition_control_id is not None:
                control_to_floor[floor.transition_control_id] = index
                immediate_axes[floor.transition_control_id] = torch.any(
                    floor.transition_basis != 0.0, dim=1
                )
        objective_axes = torch.zeros(len(program.state_axes), dtype=torch.bool)
        objective_axes[program.decision_state_index] = True
        objective_axes[program.stable_state_index] = True
        result: dict[str, bool] = {}
        for control_id in program.control_ids(lane):
            affected = immediate_axes[control_id].clone()
            for floor in program.floors[control_to_floor[control_id] + 1 :]:
                nonzero = floor.base_matrix != 0.0
                affected = torch.any(nonzero & affected.unsqueeze(0), dim=1)
            result[control_id] = bool(torch.any(affected & objective_axes).item())
        return result

    def temporal_adjoint_audit(
        self, program: FrozenTemporalProgram, result: OptimizationResult
    ) -> dict[str, Any]:
        lane = result.lane
        analytic = self.direct_control_gradient(program, lane)
        manual = self.manual_adjoint_gradient(program, lane)
        leverage, finite_steps = self.finite_control_leverage(program, lane)
        reachability = self.structural_control_reachability(program, lane)
        ids = program.control_ids(lane)
        floor_ids = program.control_floor_ids(lane)
        ordinals = program.control_floor_ordinals(lane)
        total_mass = float(torch.sum(torch.abs(analytic)).item())
        rows: list[dict[str, Any]] = []
        for index, (control_id, floor_id, ordinal) in enumerate(
            zip(ids, floor_ids, ordinals, strict=True)
        ):
            rows.append(
                {
                    "target_kind": "evidence" if lane == "leaf" else "transition",
                    "target_id": control_id,
                    "floor_id": floor_id,
                    "floor_ordinal": ordinal,
                    "signed_adjoint_sensitivity": round(
                        float(analytic[index].item()), self.config.numeric_precision
                    ),
                    "normalized_absolute_sensitivity": round(
                        (
                            abs(float(analytic[index].item())) / total_mass
                            if total_mass > 0.0
                            else 0.0
                        ),
                        self.config.numeric_precision,
                    ),
                    "finite_control_step": finite_steps[control_id],
                    "finite_control_leverage": round(
                        leverage[control_id], self.config.numeric_precision
                    ),
                    "structurally_reaches_terminal_objective": reachability[control_id],
                }
            )
        structural_ordinals = [
            ordinal
            for control_id, ordinal in zip(ids, ordinals, strict=True)
            if reachability[control_id]
        ]
        max_leverage = max(leverage.values(), default=0.0)
        active_threshold = max_leverage * self.config.active_leverage_relative_threshold
        active_ordinals = [
            ordinal
            for control_id, ordinal in zip(ids, ordinals, strict=True)
            if max_leverage > 0.0 and leverage[control_id] >= active_threshold
        ]
        top_index = max(
            range(len(ids)), key=lambda index: (leverage[ids[index]], -ordinals[index])
        )
        has_active_leverage = max_leverage > 0.0
        sorted_leverage = sorted(leverage.values(), reverse=True)
        leverage_margin = sorted_leverage[0] - sorted_leverage[1]
        payload = {
            "schema_version": TEMPORAL_AUDIT_SCHEMA_VERSION,
            "source": {
                "suite_id": program.suite_id,
                "semantic_payload_sha256": program.semantic_payload_sha256,
                "pair_id": program.pair_id,
                "order_variant": program.order_variant,
                "event_id": program.event_id,
                "event_triggered": program.event_triggered,
            },
            "lane": lane,
            "adjoint_rows": rows,
            "floor_summary": {
                "structural_earliest_control_floor_ordinal": (
                    min(structural_ordinals) if structural_ordinals else None
                ),
                "active_earliest_control_floor_ordinal": (
                    min(active_ordinals) if active_ordinals else None
                ),
                "active_leverage_relative_threshold": self.config.active_leverage_relative_threshold,
                "top_finite_leverage_target_id": (
                    ids[top_index] if has_active_leverage else None
                ),
                "top_finite_leverage_floor_id": (
                    floor_ids[top_index] if has_active_leverage else None
                ),
                "top_finite_leverage_floor_ordinal": (
                    ordinals[top_index] if has_active_leverage else None
                ),
                "top_finite_leverage_margin_over_second": round(
                    leverage_margin, self.config.numeric_precision
                ),
            },
            "gradient_checks": {
                "manual_adjoint_max_abs_error": float(
                    torch.max(torch.abs(analytic - manual)).item()
                ),
                "manual_adjoint_abs_tolerance": MANUAL_ADJOINT_ABS_TOLERANCE,
            },
            "trajectory": [
                {
                    "floor_id": "F00:initial"
                    if index == 0
                    else program.floors[index - 1].floor_id,
                    "state": {
                        axis: round(
                            float(state[axis_index].item()),
                            self.config.numeric_precision,
                        )
                        for axis_index, axis in enumerate(program.state_axes)
                    },
                }
                for index, state in enumerate(result.baseline_trajectory)
            ],
            "diagnostic_boundary": [
                "Adjoint sensitivity is local and parameterization-dependent; it is not attention or causal importance.",
                "Finite control leverage is measured only inside the supplied synthetic recurrence.",
                "The audit is a sidecar and does not alter execution-control-map bytes.",
            ],
        }
        payload["fingerprint_sha256"] = _sha256_json(payload)
        return payload


def _semantic_payload_from_raw(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(value)
        for key, value in payload.items()
        if key not in {"provenance", "claim_boundary"}
    }


def semantic_payload_sha256_from_raw(payload: Mapping[str, Any]) -> str:
    return _sha256_json(_semantic_payload_from_raw(payload))


def _load_json_exact(path: Path) -> Any:
    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise SchemaValidationError(f"duplicate JSON key {key!r}")
            result[key] = value
        return result

    return json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_keys
    )


@contextmanager
def _network_guard() -> Iterator[None]:
    with mock.patch.object(
        socket, "socket", side_effect=AssertionError("network used")
    ):
        yield


def _validate_gradient_finite_difference(
    controller: TemporalAdjointStateController,
    program: FrozenTemporalProgram,
    lane: Literal["leaf", "transition"],
) -> float:
    analytic = controller.direct_control_gradient(program, lane)
    baseline_terminal, _ = controller.rollout(program)
    baseline_stable = baseline_terminal[program.stable_state_index].detach()
    finite = torch.zeros_like(analytic)
    for index in range(len(analytic)):
        plus = torch.zeros_like(analytic)
        minus = torch.zeros_like(analytic)
        plus[index] += FINITE_DIFFERENCE_EPSILON
        minus[index] -= FINITE_DIFFERENCE_EPSILON
        plus_kwargs = (
            {"leaf_deltas": plus} if lane == "leaf" else {"transition_deltas": plus}
        )
        minus_kwargs = (
            {"leaf_deltas": minus} if lane == "leaf" else {"transition_deltas": minus}
        )
        plus_terminal, _ = controller.rollout(program, **plus_kwargs)
        minus_terminal, _ = controller.rollout(program, **minus_kwargs)
        plus_loss = controller.loss_terms(
            program, plus_terminal, plus, baseline_stable
        ).total
        minus_loss = controller.loss_terms(
            program, minus_terminal, minus, baseline_stable
        ).total
        finite[index] = (plus_loss - minus_loss) / (2.0 * FINITE_DIFFERENCE_EPSILON)
    return float(torch.max(torch.abs(analytic - finite)).item())


def run_self_tests() -> dict[str, Any]:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / ("temporal_adjoint_state_controller_v0_5_t_dev.json")
    )
    if not fixture_path.is_file():
        raise AssertionError(f"required fixture is missing: {fixture_path}")
    suite = TemporalPairedSuite.from_mapping(_load_json_exact(fixture_path))
    controller = TemporalAdjointStateController()
    early = suite.materialize("P03", "early_correction")
    late = suite.materialize("P03", "late_correction")
    max_fd_error = 0.0
    max_manual_error = 0.0
    for program in (early, late):
        for lane in ("leaf", "transition"):
            fd_error = _validate_gradient_finite_difference(controller, program, lane)
            max_fd_error = max(max_fd_error, fd_error)
            if fd_error > FINITE_DIFFERENCE_ABS_TOLERANCE:
                raise AssertionError(
                    f"finite-difference mismatch for {program.order_variant}/{lane}: {fd_error:.3e}"
                )
            manual = controller.manual_adjoint_gradient(program, lane)
            analytic = controller.direct_control_gradient(program, lane)
            error = float(torch.max(torch.abs(manual - analytic)).item())
            max_manual_error = max(max_manual_error, error)
            if error > MANUAL_ADJOINT_ABS_TOLERANCE:
                raise AssertionError(
                    f"manual adjoint mismatch for {program.order_variant}/{lane}: {error:.3e}"
                )

    early_transition = controller.optimize(early, "transition")
    late_transition = controller.optimize(late, "transition")
    for result in (early_transition, late_transition):
        if not result.accepted or not (
            result.loss_after["total"] < result.loss_before["total"]
        ):
            raise AssertionError("temporal transition control was not accepted")
        if (
            torch.linalg.vector_norm(result.final_deltas).item()
            > controller.config.max_control_l2_norm + 1e-12
        ):
            raise AssertionError("final control exceeded the shared L2 budget")
        if (
            result.max_observed_control_l2_norm
            > controller.config.max_control_l2_norm + 1e-12
        ):
            raise AssertionError("intermediate control exceeded the shared L2 budget")
    early_audit = controller.temporal_adjoint_audit(early, early_transition)
    late_audit = controller.temporal_adjoint_audit(late, late_transition)
    if (
        early_audit["floor_summary"]["top_finite_leverage_target_id"]
        != "decision_write"
    ):
        raise AssertionError("early correction did not nominate decision_write")
    if late_audit["floor_summary"]["top_finite_leverage_target_id"] != "revision_mix":
        raise AssertionError("late correction did not nominate revision_mix")

    # Cut every premise-to-decision base edge.  Upstream evidence leaf credit
    # must become exact zero, while the unrelated stable branch remains local.
    severed_floors: list[FrozenFloor] = []
    for floor in late.floors:
        matrix = floor.base_matrix.clone()
        if floor.operator_id in {"decision", "revision"}:
            matrix[late.decision_state_index, late.state_axes.index("premise")] = 0.0
        severed_floors.append(replace(floor, base_matrix=matrix.detach()))
    severed = replace(late, floors=tuple(severed_floors))
    severed_gradient = controller.direct_control_gradient(severed, "leaf")
    leaf_index = {item: index for index, item in enumerate(severed.leaf_control_ids)}
    for evidence_id in ("legacy_record", "registry_correction"):
        if float(severed_gradient[leaf_index[evidence_id]].item()) != 0.0:
            raise AssertionError("severed upstream leaf retained terminal credit")

    # Insert an exact identity floor.  The terminal state and all standardized
    # gradients must remain byte-for-byte equal.
    identity_dimension = len(late.state_axes)
    identity = FrozenFloor(
        floor_id="F03A:identity_split",
        floor_ordinal=3,
        operator_id="identity_split",
        public_name="Exact public identity split",
        activation="identity",
        evidence_id=None,
        evidence_value=0.0,
        transition_control_id=None,
        base_matrix=torch.eye(identity_dimension, dtype=FLOAT_DTYPE),
        evidence_direction=torch.zeros(identity_dimension, dtype=FLOAT_DTYPE),
        transition_basis=torch.zeros(
            (identity_dimension, identity_dimension), dtype=FLOAT_DTYPE
        ),
    )
    split_floors = list(late.floors)
    split_floors.insert(3, identity)
    split = replace(late, floors=tuple(split_floors))
    late_terminal, _ = controller.rollout(late)
    split_terminal, _ = controller.rollout(split)
    if not torch.equal(late_terminal, split_terminal):
        raise AssertionError("identity-node split changed the terminal state")
    for lane in ("leaf", "transition"):
        if not torch.equal(
            controller.direct_control_gradient(late, lane),
            controller.direct_control_gradient(split, lane),
        ):
            raise AssertionError("identity-node split changed control gradients")

    # Audit is a detachable observer: constructing it must not alter execution
    # map bytes before or after observation.
    bytes_before = late_transition.canonical_execution_control_map_bytes()
    _ = controller.temporal_adjoint_audit(late, late_transition)
    bytes_after = late_transition.canonical_execution_control_map_bytes()
    if bytes_before != bytes_after:
        raise AssertionError("audit observer changed execution-map bytes")
    second = controller.optimize(late, "transition")
    if bytes_before != second.canonical_execution_control_map_bytes():
        raise AssertionError("identical runs did not emit byte-stable controls")

    no_event_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / ("temporal_adjoint_state_controller_v0_5_t_no_event.json")
    )
    no_event_suite = TemporalPairedSuite.from_mapping(_load_json_exact(no_event_path))
    no_event = no_event_suite.materialize("P00", "early_correction")
    for lane in ("leaf", "transition"):
        result = controller.optimize(no_event, lane)
        if result.status != "NO_EVENT_IDENTITY" or result.backward_calls != 0:
            raise AssertionError("no-event path invoked backward optimization")
        if not torch.equal(
            result.baseline_terminal_state, result.final_terminal_state
        ) or not torch.equal(
            result.final_deltas, torch.zeros_like(result.final_deltas)
        ):
            raise AssertionError("no-event path was not exact identity")

    with _network_guard():
        guarded = TemporalAdjointStateController(
            ControllerConfig(revision_steps=2)
        ).optimize(early, "transition")
    if guarded.backward_calls != 2:
        raise AssertionError("network-denied local optimization did not complete")

    # Recursive forbidden-key and semantic-hash tamper guards.
    raw = _load_json_exact(fixture_path)
    bad = copy.deepcopy(raw)
    bad["pair_parameters"][0]["gold"] = "BLUE"
    try:
        TemporalPairedSuite.from_mapping(bad)
    except SchemaValidationError:
        pass
    else:
        raise AssertionError("forbidden gold field was accepted")
    bad = copy.deepcopy(raw)
    bad["operators"][0]["base_matrix"][0][0] += 0.01
    try:
        TemporalPairedSuite.from_mapping(bad)
    except SchemaValidationError:
        pass
    else:
        raise AssertionError("semantic hash tamper was accepted")

    return {
        "status": "PASS",
        "controller": f"{CONTROLLER_NAME} {CONTROLLER_VERSION}",
        "checks": [
            "exact typed temporal suite and canonical semantic hash",
            "float64 autograd matches central finite differences",
            "manual temporal adjoint recurrence matches autograd",
            "edge severing removes upstream terminal credit",
            "identity-node split preserves terminal state and gradients",
            "paired order changes the top finite-leverage transition floor",
            "bounded optimization lowers the terminal-only objective",
            "audit sidecar leaves execution-control-map bytes unchanged",
            "no-event path is exact identity with zero backward calls",
            "recursive forbidden-key and semantic-hash tampering are rejected",
            "pure local optimization completes while sockets are denied",
        ],
        "mechanism_metrics": {
            "semantic_payload_sha256": suite.semantic_payload_sha256(),
            "max_finite_difference_error": max_fd_error,
            "finite_difference_abs_tolerance": FINITE_DIFFERENCE_ABS_TOLERANCE,
            "max_manual_adjoint_error": max_manual_error,
            "manual_adjoint_abs_tolerance": MANUAL_ADJOINT_ABS_TOLERANCE,
            "early_top_control": early_audit["floor_summary"][
                "top_finite_leverage_target_id"
            ],
            "late_top_control": late_audit["floor_summary"][
                "top_finite_leverage_target_id"
            ],
            "early_objective_before": early_transition.loss_before["total"],
            "early_objective_after": early_transition.loss_after["total"],
            "late_objective_before": late_transition.loss_before["total"],
            "late_objective_after": late_transition.loss_after["total"],
        },
        "claim_boundary": (
            "Synthetic supplied public recurrence only; exact local adjoints do not "
            "discover dependencies, establish causality, or evidence a hosted-model "
            "reasoning improvement."
        ),
    }


def _pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("self-test", help="run deterministic mechanism checks")
    fingerprint = subparsers.add_parser(
        "fingerprint", help="print the semantic-payload SHA-256 for an unlocked JSON"
    )
    fingerprint.add_argument("--input-json", type=Path, required=True)
    validate = subparsers.add_parser("validate", help="validate one temporal suite")
    validate.add_argument("--input-json", type=Path, required=True)
    inspect = subparsers.add_parser(
        "inspect", help="optimize one pair/order and print map plus audit"
    )
    inspect.add_argument("--input-json", type=Path, required=True)
    inspect.add_argument("--pair-id", required=True)
    inspect.add_argument("--order-variant", required=True)
    inspect.add_argument("--lane", choices=sorted(_ALLOWED_LANES), default="transition")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "self-test":
        print(_pretty_json(run_self_tests()), end="")
        return 0
    raw = _load_json_exact(args.input_json)
    if args.command == "fingerprint":
        print(semantic_payload_sha256_from_raw(raw))
        return 0
    suite = TemporalPairedSuite.from_mapping(raw)
    if args.command == "validate":
        print(
            _pretty_json(
                {
                    "status": "VALID",
                    "schema_version": suite.schema_version,
                    "suite_id": suite.suite_id,
                    "pair_count": len(suite.pair_parameters),
                    "order_variants": [
                        item.order_variant for item in suite.trace_orders
                    ],
                    "semantic_payload_sha256": suite.semantic_payload_sha256(),
                }
            ),
            end="",
        )
        return 0
    program = suite.materialize(args.pair_id, args.order_variant)
    controller = TemporalAdjointStateController()
    result = controller.optimize(program, args.lane)
    print(
        _pretty_json(
            {
                "execution_control_map": result.to_execution_control_map(),
                "temporal_adjoint_audit": controller.temporal_adjoint_audit(
                    program, result
                ),
            }
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
