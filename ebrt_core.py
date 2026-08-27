#!/usr/bin/env python3
"""EBRT v0.8: model-interface-agnostic backward revision.

The core owns a differentiable public trajectory, backward credit assignment,
bounded control projection, and joint-lane composition.  Model-specific code
is confined to adapters.  The bundled MLX adapter is the first executable
open-weight backend; hosted API adapters implement the same protocol but are
not required by the core or its network-zero self-test.

This module does not expose, infer, or claim to edit private chain-of-thought.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import socket
import time
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Literal, Mapping, Protocol, Sequence
from unittest import mock

import torch


CORE_PROTOCOL_VERSION = "ebrt-model-interface-core-v0.7.1"
JOINT_PROTOCOL_VERSION = "ebrt-joint-trajectory-v0.8.0"
RESULT_SCHEMA_VERSION = "ebrt-model-interface-result-v0.8.0"
SELF_TEST_SCHEMA_VERSION = "ebrt-model-interface-self-test-v0.8.0"
POST_RUN_CONTRACT_VERSION = "ebrt-post-run-contract-v0.8.0"
AXES = ("revision", "invalidation", "stability")
EVIDENCE_ROLES = frozenset(
    {"context", "required_support", "invalidated_prior", "correction", "stable"}
)
DTYPE = torch.float64
FD_EPSILON = 1.0e-6
FD_TOLERANCE = 2.0e-7
FLOAT_TOLERANCE = 1.0e-12

CLAIM_BOUNDARY = (
    "EBRT differentiates only through a detached, core-owned copy of an explicit adapter-supplied trajectory.",
    "A ModelAdapter may wrap a hosted API or an open-weight runtime; the core does not differentiate through generation.",
    "A passing conformance run establishes protocol execution, not semantic superiority or general reasoning improvement.",
    "The bundled public trajectory is an inspectable surrogate, not a transcript of private model reasoning.",
    "Heterogeneous multi-model effects remain unassessed until distinct model backends are run under a locked comparison.",
)

JsonObject = dict[str, Any]


class EBRTError(RuntimeError):
    """A strict model-interface or trajectory invariant failed."""


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
    return json.loads(_canonical_bytes(value))


def _seal(value: Mapping[str, Any]) -> JsonObject:
    output = _clone(value)
    output["fingerprint_sha256"] = _fingerprint(output)
    return output


def _without_fingerprint(value: Mapping[str, Any]) -> JsonObject:
    output = _clone(value)
    output.pop("fingerprint_sha256", None)
    return output


def _sealed_snapshot(value: Any, label: str) -> JsonObject:
    _require(isinstance(value, Mapping), f"{label}_TYPE_INVALID")
    try:
        snapshot = _clone(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise EBRTError(f"{label}_NOT_CANONICAL_JSON") from exc
    _require(
        snapshot.get("fingerprint_sha256")
        == _fingerprint(_without_fingerprint(snapshot)),
        f"{label}_FINGERPRINT_INVALID",
    )
    return snapshot


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise EBRTError(reason)


def _finite(value: Any, label: str) -> float:
    _require(not isinstance(value, bool), f"{label}_NONNUMERIC")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise EBRTError(f"{label}_NONNUMERIC") from exc
    _require(math.isfinite(number), f"{label}_NONFINITE")
    return 0.0 if number == 0.0 else number


def _safe_id(value: str, label: str) -> str:
    _require(
        isinstance(value, str)
        and bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9_.:-]{0,63}", value)),
        f"{label}_INVALID",
    )
    return value


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    ordinal: int
    text: str
    role: Literal[
        "context",
        "required_support",
        "invalidated_prior",
        "correction",
        "stable",
    ]
    neutral_effect: tuple[float, float, float]
    control_basis: tuple[float, float, float]

    def to_dict(self) -> JsonObject:
        return {
            "evidence_id": self.evidence_id,
            "ordinal": self.ordinal,
            "text": self.text,
            "role": self.role,
            "neutral_effect": list(self.neutral_effect),
            "control_basis": list(self.control_basis),
        }


@dataclass(frozen=True)
class RevisionEvent:
    event_id: str
    correction_evidence_id: str
    invalidated_evidence_ids: tuple[str, ...]
    stable_evidence_ids: tuple[str, ...]

    def to_dict(self) -> JsonObject:
        return {
            "event_id": self.event_id,
            "correction_evidence_id": self.correction_evidence_id,
            "invalidated_evidence_ids": list(self.invalidated_evidence_ids),
            "stable_evidence_ids": list(self.stable_evidence_ids),
        }


@dataclass(frozen=True)
class PriorPublicState:
    answer: str
    active_support_ids: tuple[str, ...]
    stable_values: tuple[tuple[str, str], ...]

    def to_dict(self) -> JsonObject:
        return {
            "answer": self.answer,
            "active_support_ids": list(self.active_support_ids),
            "stable_values": [
                {"key": key, "value": value} for key, value in self.stable_values
            ],
        }


@dataclass(frozen=True)
class RevisionTask:
    task_id: str
    question: str
    answer_choices: tuple[str, ...]
    evidence: tuple[Evidence, ...]
    before_horizon_evidence_ids: tuple[str, ...]
    prior_state: PriorPublicState
    event: RevisionEvent
    terminal_target: tuple[float, float, float]
    decay: float = 0.85
    control_budget: float = 0.75
    learning_rate: float = 0.8
    reinspection_count: int = 3

    def to_public_dict(self) -> JsonObject:
        """Return model-visible task material; semantic gold is never included."""

        return {
            "schema_version": "ebrt-revision-task-v0.7.1",
            "task_id": self.task_id,
            "question": self.question,
            "answer_choices": list(self.answer_choices),
            "evidence": [row.to_dict() for row in self.evidence],
            "before_horizon_evidence_ids": list(self.before_horizon_evidence_ids),
            "prior_state": self.prior_state.to_dict(),
            "event": self.event.to_dict(),
            "trajectory_contract": {
                "axes": list(AXES),
                "terminal_target": list(self.terminal_target),
                "decay": self.decay,
                "control_budget": self.control_budget,
                "learning_rate": self.learning_rate,
                "reinspection_count": self.reinspection_count,
            },
        }


@dataclass(frozen=True)
class PostRunContract:
    """A post-generation check that is never passed to ModelAdapter.generate."""

    expected_answer: str
    required_support_ids: tuple[str, ...]
    forbidden_support_ids: tuple[str, ...]
    required_compiled_preserve_ids: tuple[str, ...]

    def to_dict(self) -> JsonObject:
        """Return the exact post-generation contract as a sealed receipt."""

        return _seal(
            {
                "schema_version": POST_RUN_CONTRACT_VERSION,
                "expected_answer": self.expected_answer,
                "required_support_ids": list(self.required_support_ids),
                "forbidden_support_ids": list(self.forbidden_support_ids),
                "required_compiled_preserve_ids": list(
                    self.required_compiled_preserve_ids
                ),
            }
        )


def validate_task(task: RevisionTask) -> None:
    _safe_id(task.task_id, "TASK_ID")
    _require(bool(task.question.strip()), "QUESTION_EMPTY")
    _require(len(task.answer_choices) >= 2, "ANSWER_CHOICES_TOO_SMALL")
    _require(
        len(set(task.answer_choices)) == len(task.answer_choices)
        and all(
            isinstance(row, str)
            and bool(row)
            and row == row.strip()
            and row.isprintable()
            for row in task.answer_choices
        ),
        "ANSWER_CHOICES_INVALID",
    )
    _require(task.prior_state.answer in task.answer_choices, "PRIOR_ANSWER_INVALID")
    _require(len(task.evidence) >= 2, "EVIDENCE_TOO_SMALL")
    ids = [row.evidence_id for row in task.evidence]
    _require(len(ids) == len(set(ids)), "EVIDENCE_ID_DUPLICATE")
    _require(
        [row.ordinal for row in task.evidence]
        == list(range(1, len(task.evidence) + 1)),
        "EVIDENCE_ORDINAL_INVALID",
    )
    for row in task.evidence:
        _safe_id(row.evidence_id, "EVIDENCE_ID")
        _require(row.evidence_id.upper() != "NONE", "EVIDENCE_ID_RESERVED")
        _require(bool(row.text.strip()), "EVIDENCE_TEXT_EMPTY")
        _require(
            isinstance(row.role, str) and row.role in EVIDENCE_ROLES,
            "EVIDENCE_ROLE_INVALID",
        )
        for label, vector in (
            ("NEUTRAL_EFFECT", row.neutral_effect),
            ("CONTROL_BASIS", row.control_basis),
        ):
            _require(len(vector) == len(AXES), f"{label}_DIMENSION_INVALID")
            for value in vector:
                _finite(value, label)
        _require(
            row.control_basis[AXES.index("stability")] == 0.0,
            "STABILITY_AXIS_MUST_BE_EXACT_ZERO",
        )
    id_set = set(ids)
    _safe_id(task.event.event_id, "EVENT_ID")
    for label, values in (
        ("INVALIDATED_EVIDENCE", task.event.invalidated_evidence_ids),
        ("STABLE_EVIDENCE", task.event.stable_evidence_ids),
        ("BEFORE_HORIZON", task.before_horizon_evidence_ids),
        ("PRIOR_SUPPORT", task.prior_state.active_support_ids),
    ):
        _require(len(values) == len(set(values)), f"{label}_DUPLICATE")
    _require(
        all(
            isinstance(key, str)
            and isinstance(value, str)
            and bool(key.strip())
            and bool(value.strip())
            for key, value in task.prior_state.stable_values
        ),
        "STABLE_VALUE_INVALID",
    )
    stable_keys = [key for key, _value in task.prior_state.stable_values]
    _require(len(stable_keys) == len(set(stable_keys)), "STABLE_VALUE_KEY_DUPLICATE")
    _require(
        task.event.correction_evidence_id in id_set,
        "CORRECTION_EVIDENCE_UNKNOWN",
    )
    _require(
        set(task.event.invalidated_evidence_ids).issubset(id_set),
        "INVALIDATED_EVIDENCE_UNKNOWN",
    )
    _require(
        set(task.event.stable_evidence_ids).issubset(id_set),
        "STABLE_EVIDENCE_UNKNOWN",
    )
    _require(
        not set(task.event.invalidated_evidence_ids)
        & set(task.event.stable_evidence_ids),
        "EVENT_ROLE_OVERLAP",
    )
    _require(
        task.event.correction_evidence_id
        not in set(task.event.invalidated_evidence_ids)
        | set(task.event.stable_evidence_ids),
        "CORRECTION_ROLE_OVERLAP",
    )
    role_ids = {
        role: {row.evidence_id for row in task.evidence if row.role == role}
        for role in EVIDENCE_ROLES
    }
    _require(
        role_ids["correction"] == {task.event.correction_evidence_id},
        "CORRECTION_ROLE_MISMATCH",
    )
    _require(
        role_ids["invalidated_prior"] == set(task.event.invalidated_evidence_ids),
        "INVALIDATED_ROLE_MISMATCH",
    )
    _require(
        role_ids["stable"] == set(task.event.stable_evidence_ids),
        "STABLE_ROLE_MISMATCH",
    )
    correction_index = ids.index(task.event.correction_evidence_id)
    _require(correction_index > 0, "CORRECTION_MUST_FOLLOW_PRIOR_EVIDENCE")
    _require(
        task.before_horizon_evidence_ids == tuple(ids[:correction_index]),
        "BEFORE_HORIZON_NOT_CHRONOLOGICAL_PREFIX",
    )
    _require(
        set(task.prior_state.active_support_ids).issubset(
            set(task.before_horizon_evidence_ids)
        ),
        "PRIOR_SUPPORT_OUTSIDE_HORIZON",
    )
    _require(len(task.terminal_target) == len(AXES), "TARGET_DIMENSION_INVALID")
    for value in task.terminal_target:
        _finite(value, "TARGET")
    decay = _finite(task.decay, "DECAY")
    control_budget = _finite(task.control_budget, "CONTROL_BUDGET")
    learning_rate = _finite(task.learning_rate, "LEARNING_RATE")
    _require(0.0 < decay <= 1.0, "DECAY_INVALID")
    _require(control_budget > 0.0, "CONTROL_BUDGET_INVALID")
    _require(learning_rate > 0.0, "LEARNING_RATE_INVALID")
    _require(
        1 <= task.reinspection_count <= len(task.evidence),
        "REINSPECTION_COUNT_INVALID",
    )


def validate_contract(task: RevisionTask, contract: PostRunContract) -> None:
    _require(type(contract) is PostRunContract, "CONTRACT_TYPE_INVALID")
    ids = {row.evidence_id for row in task.evidence}
    _require(contract.expected_answer in task.answer_choices, "CONTRACT_ANSWER_INVALID")
    for label, values in (
        ("REQUIRED_SUPPORT", contract.required_support_ids),
        ("FORBIDDEN_SUPPORT", contract.forbidden_support_ids),
        ("REQUIRED_COMPILED_PRESERVE", contract.required_compiled_preserve_ids),
    ):
        _require(len(values) == len(set(values)), f"{label}_DUPLICATE")
        _require(set(values).issubset(ids), f"{label}_UNKNOWN")
    _require(
        not set(contract.required_support_ids) & set(contract.forbidden_support_ids),
        "CONTRACT_SUPPORT_OVERLAP",
    )
    _require(
        set(contract.required_compiled_preserve_ids).issubset(
            set(task.event.stable_evidence_ids)
        ),
        "CONTRACT_PRESERVE_NOT_STABLE",
    )


@dataclass(frozen=True)
class TrajectoryEnvelope:
    lane_id: str
    state_adapter_id: str
    state_adapter_config: tuple[tuple[str, float], ...]
    axis_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    roles: tuple[str, ...]
    neutral_effects: torch.Tensor
    control_basis: torch.Tensor
    target: torch.Tensor
    eligible_mask: torch.Tensor
    event_index: int
    decay: float
    control_budget: float
    learning_rate: float


class StateAdapter(Protocol):
    adapter_id: str

    def build(self, task: RevisionTask, *, lane_id: str) -> TrajectoryEnvelope: ...


def _clone_envelope(envelope: TrajectoryEnvelope) -> TrajectoryEnvelope:
    """Clone all mutable tensors while retaining immutable public metadata."""

    return replace(
        envelope,
        neutral_effects=envelope.neutral_effects.detach().clone(),
        control_basis=envelope.control_basis.detach().clone(),
        target=envelope.target.detach().clone(),
        eligible_mask=envelope.eligible_mask.detach().clone(),
    )


def _prepare_state_envelope(
    task: RevisionTask,
    state_adapter: StateAdapter,
    envelope: TrajectoryEnvelope,
    *,
    lane_id: str,
    label: str,
) -> TrajectoryEnvelope:
    _require(
        isinstance(envelope, TrajectoryEnvelope),
        f"{label}_ENVELOPE_TYPE_INVALID",
    )
    _require(envelope.lane_id == lane_id, f"{label}_LANE_MISMATCH")
    adapter_id = getattr(state_adapter, "adapter_id", None)
    _safe_id(adapter_id, f"{label}_ID")
    _require(
        envelope.state_adapter_id == adapter_id,
        f"{label}_ID_MISMATCH",
    )
    _require(
        isinstance(envelope.state_adapter_config, tuple),
        f"{label}_CONFIG_INVALID",
    )
    config_keys: list[str] = []
    for row in envelope.state_adapter_config:
        _require(
            isinstance(row, tuple) and len(row) == 2,
            f"{label}_CONFIG_ROW_INVALID",
        )
        key, value = row
        _safe_id(key, f"{label}_CONFIG_KEY")
        _finite(value, f"{label}_CONFIG_VALUE")
        config_keys.append(key)
    _require(
        config_keys == sorted(config_keys)
        and len(config_keys) == len(set(config_keys)),
        f"{label}_CONFIG_KEYS_INVALID",
    )
    _require(envelope.axis_ids == AXES, f"{label}_AXIS_MISMATCH")
    _require(
        envelope.evidence_ids == tuple(row.evidence_id for row in task.evidence),
        f"{label}_EVIDENCE_MISMATCH",
    )
    _require(
        envelope.roles == tuple(row.role for row in task.evidence),
        f"{label}_ROLE_MISMATCH",
    )
    expected_event_index = next(
        index
        for index, row in enumerate(task.evidence)
        if row.evidence_id == task.event.correction_evidence_id
    )
    _require(
        envelope.event_index == expected_event_index,
        f"{label}_EVENT_INDEX_MISMATCH",
    )
    for field_name, observed, expected in (
        ("DECAY", envelope.decay, task.decay),
        ("CONTROL_BUDGET", envelope.control_budget, task.control_budget),
        ("LEARNING_RATE", envelope.learning_rate, task.learning_rate),
    ):
        _require(
            _finite(observed, f"{label}_{field_name}")
            == _finite(expected, f"TASK_{field_name}"),
            f"{label}_{field_name}_MISMATCH",
        )
    count = len(task.evidence)
    tensors = {
        "NEUTRAL_EFFECTS": envelope.neutral_effects,
        "CONTROL_BASIS": envelope.control_basis,
        "TARGET": envelope.target,
        "ELIGIBLE_MASK": envelope.eligible_mask,
    }
    for field_name, tensor in tensors.items():
        _require(isinstance(tensor, torch.Tensor), f"{label}_{field_name}_TYPE_INVALID")
        _require(tensor.device.type == "cpu", f"{label}_{field_name}_DEVICE_INVALID")
    _require(
        envelope.neutral_effects.shape == (count, len(AXES))
        and envelope.neutral_effects.dtype == DTYPE,
        f"{label}_NEUTRAL_EFFECTS_CONTRACT_INVALID",
    )
    _require(
        envelope.control_basis.shape == (count, len(AXES))
        and envelope.control_basis.dtype == DTYPE,
        f"{label}_CONTROL_BASIS_CONTRACT_INVALID",
    )
    _require(
        envelope.target.shape == (len(AXES),) and envelope.target.dtype == DTYPE,
        f"{label}_TARGET_CONTRACT_INVALID",
    )
    _require(
        envelope.eligible_mask.shape == (count,)
        and envelope.eligible_mask.dtype == torch.bool,
        f"{label}_ELIGIBLE_MASK_CONTRACT_INVALID",
    )
    detached = _clone_envelope(envelope)
    _require(
        all(
            not tensor.requires_grad and tensor.grad_fn is None
            for tensor in (
                detached.neutral_effects,
                detached.control_basis,
                detached.target,
                detached.eligible_mask,
            )
        ),
        f"{label}_STOP_GRADIENT_FAILED",
    )
    _require(
        bool(torch.all(torch.isfinite(detached.neutral_effects)))
        and bool(torch.all(torch.isfinite(detached.control_basis)))
        and bool(torch.all(torch.isfinite(detached.target))),
        f"{label}_TENSOR_NONFINITE",
    )
    _require(
        torch.equal(
            detached.target,
            torch.tensor(task.terminal_target, dtype=DTYPE),
        ),
        f"{label}_TARGET_MISMATCH",
    )
    expected_eligible = torch.linalg.vector_norm(detached.control_basis, dim=1) > 0.0
    _require(
        torch.equal(detached.eligible_mask, expected_eligible),
        f"{label}_ELIGIBLE_MASK_MISMATCH",
    )
    _require(
        bool(detached.eligible_mask[detached.event_index]),
        f"{label}_CORRECTION_INELIGIBLE",
    )
    stability_index = AXES.index("stability")
    _require(
        bool(torch.all(detached.control_basis[:, stability_index] == 0.0)),
        f"{label}_STABILITY_BASIS_NONZERO",
    )
    return detached


@dataclass(frozen=True)
class TypedPublicStateAdapter:
    """Maps typed public effects into a differentiable trajectory envelope."""

    adapter_id: str = "typed-public-state-v0.7.1"
    support_scale: float = 1.0
    invalidation_scale: float = 1.0
    correction_scale: float = 1.0

    def build(self, task: RevisionTask, *, lane_id: str) -> TrajectoryEnvelope:
        validate_task(task)
        _safe_id(lane_id, "LANE_ID")
        _safe_id(self.adapter_id, "STATE_ADAPTER_ID")
        scales = {
            "support": _finite(self.support_scale, "SUPPORT_SCALE"),
            "invalidation": _finite(self.invalidation_scale, "INVALIDATION_SCALE"),
            "correction": _finite(self.correction_scale, "CORRECTION_SCALE"),
        }
        _require(all(value > 0.0 for value in scales.values()), "STATE_SCALE_INVALID")
        scale_by_role = {
            "context": 1.0,
            "required_support": scales["support"],
            "invalidated_prior": scales["invalidation"],
            "correction": scales["correction"],
            "stable": 1.0,
        }
        neutral = torch.tensor(
            [row.neutral_effect for row in task.evidence], dtype=DTYPE
        )
        basis = torch.tensor(
            [
                [value * scale_by_role[row.role] for value in row.control_basis]
                for row in task.evidence
            ],
            dtype=DTYPE,
        )
        eligible = torch.linalg.vector_norm(basis, dim=1) > 0.0
        correction_index = next(
            index
            for index, row in enumerate(task.evidence)
            if row.evidence_id == task.event.correction_evidence_id
        )
        _require(bool(torch.any(eligible)), "NO_ELIGIBLE_CONTROL_SITE")
        _require(
            bool(torch.any(eligible[:correction_index])),
            "NO_PRE_EVENT_CONTROL_SITE",
        )
        _require(
            bool(eligible[correction_index]),
            "CORRECTION_CONTROL_INELIGIBLE",
        )
        return TrajectoryEnvelope(
            lane_id=lane_id,
            state_adapter_id=self.adapter_id,
            state_adapter_config=(
                ("correction_scale", scales["correction"]),
                ("invalidation_scale", scales["invalidation"]),
                ("support_scale", scales["support"]),
            ),
            axis_ids=AXES,
            evidence_ids=tuple(row.evidence_id for row in task.evidence),
            roles=tuple(row.role for row in task.evidence),
            neutral_effects=neutral,
            control_basis=basis,
            target=torch.tensor(task.terminal_target, dtype=DTYPE),
            eligible_mask=eligible,
            event_index=correction_index,
            decay=task.decay,
            control_budget=task.control_budget,
            learning_rate=task.learning_rate,
        )


def _forward(envelope: TrajectoryEnvelope, controls: torch.Tensor) -> torch.Tensor:
    count = len(envelope.evidence_ids)
    _require(controls.shape == (count,), "CONTROL_SHAPE_INVALID")
    _require(controls.dtype == DTYPE, "CONTROL_DTYPE_INVALID")
    state = torch.zeros(len(envelope.axis_ids), dtype=DTYPE)
    points: list[torch.Tensor] = []
    for index in range(count):
        admission = torch.tanh(controls[index])
        state = (
            envelope.decay * state
            + envelope.neutral_effects[index]
            + envelope.control_basis[index] * admission
        )
        points.append(state)
    return torch.stack(points)


def _loss(
    envelope: TrajectoryEnvelope,
    controls: torch.Tensor,
    trajectory: torch.Tensor | None = None,
) -> tuple[torch.Tensor, JsonObject]:
    points = _forward(envelope, controls) if trajectory is None else trajectory
    terminal = 0.5 * torch.sum((points[-1] - envelope.target).square())
    post_event = points[envelope.event_index :]
    path = 0.5 * torch.mean((post_event - envelope.target).square())
    control = 0.5 * torch.sum(controls.square())
    eligible = controls[envelope.eligible_mask]
    if eligible.numel() > 1:
        smoothness = torch.sum((eligible[1:] - eligible[:-1]).square())
    else:
        smoothness = torch.zeros((), dtype=DTYPE)
    total = terminal + 0.15 * path + 0.02 * control + 0.01 * smoothness
    return total, {
        "terminal": _finite(float(terminal.detach()), "TERMINAL_LOSS"),
        "path": _finite(float(path.detach()), "PATH_LOSS"),
        "control": _finite(float(control.detach()), "CONTROL_LOSS"),
        "smoothness": _finite(float(smoothness.detach()), "SMOOTHNESS_LOSS"),
        "total": _finite(float(total.detach()), "TOTAL_LOSS"),
    }


def _project_controls(
    proposal: torch.Tensor,
    eligible_mask: torch.Tensor,
    budget: float,
) -> torch.Tensor:
    admitted = torch.where(eligible_mask, proposal, torch.zeros_like(proposal))
    norm = torch.linalg.vector_norm(admitted)
    if float(norm) > budget:
        admitted = admitted * (budget / norm)
    return admitted


def _central_difference(
    envelope: TrajectoryEnvelope,
    controls: torch.Tensor,
    index: int,
) -> float:
    plus = controls.detach().clone()
    minus = controls.detach().clone()
    plus[index] += FD_EPSILON
    minus[index] -= FD_EPSILON
    plus_loss, _ = _loss(envelope, plus)
    minus_loss, _ = _loss(envelope, minus)
    return float((plus_loss - minus_loss) / (2.0 * FD_EPSILON))


def _trajectory_rows(
    envelope: TrajectoryEnvelope, trajectory: torch.Tensor
) -> list[JsonObject]:
    public_trajectory = trajectory.detach()
    return [
        {
            "step": index + 1,
            "evidence_id": evidence_id,
            "role": envelope.roles[index],
            "state": {
                axis_id: _finite(float(public_trajectory[index, axis]), "STATE")
                for axis, axis_id in enumerate(envelope.axis_ids)
            },
        }
        for index, evidence_id in enumerate(envelope.evidence_ids)
    ]


class BackwardRevisionCore:
    """Provider-free v0.7.1 single-trajectory optimizer."""

    def optimize(self, envelope: TrajectoryEnvelope) -> JsonObject:
        count = len(envelope.evidence_ids)
        zero = torch.zeros(count, dtype=DTYPE, requires_grad=True)
        neutral = _forward(envelope, zero)
        neutral_loss, neutral_parts = _loss(envelope, zero, neutral)
        neutral_loss.backward()
        gradient = zero.grad
        _require(gradient is not None, "BACKWARD_DID_NOT_POPULATE_GRADIENT")
        _require(bool(torch.all(torch.isfinite(gradient))), "GRADIENT_NONFINITE")

        fd_errors = []
        for index in range(count):
            if bool(envelope.eligible_mask[index]):
                fd = _central_difference(envelope, zero.detach(), index)
                fd_errors.append(abs(fd - float(gradient[index])))
            else:
                fd_errors.append(abs(float(gradient[index])))
        max_fd_error = max(fd_errors, default=0.0)

        proposal = -envelope.learning_rate * gradient.detach()
        controls = _project_controls(
            proposal, envelope.eligible_mask, envelope.control_budget
        )
        accepted = False
        accepted_loss = neutral_loss.detach()
        accepted_parts = neutral_parts
        accepted_trajectory = neutral.detach()
        backtracking_steps = 0
        for backtracking_steps in range(21):
            candidate_trajectory = _forward(envelope, controls)
            candidate_loss, candidate_parts = _loss(
                envelope, controls, candidate_trajectory
            )
            if float(candidate_loss.detach()) < float(neutral_loss.detach()) - 1.0e-12:
                accepted = True
                accepted_loss = candidate_loss.detach()
                accepted_parts = candidate_parts
                accepted_trajectory = candidate_trajectory.detach()
                break
            controls = 0.5 * controls
        _require(accepted, "NO_DESCENDING_BOUNDED_CONTROL")

        credit_rows = [
            {
                "step": index + 1,
                "evidence_id": evidence_id,
                "role": envelope.roles[index],
                "eligible": bool(envelope.eligible_mask[index]),
                "gradient": _finite(float(gradient[index]), "CREDIT_GRADIENT"),
                "control": _finite(float(controls[index]), "CREDIT_CONTROL"),
                "absolute_control": _finite(
                    abs(float(controls[index])), "CREDIT_MAGNITUDE"
                ),
            }
            for index, evidence_id in enumerate(envelope.evidence_ids)
        ]
        stability_index = envelope.axis_ids.index("stability")
        checks = {
            "real_backward_executed_once": True,
            "central_finite_difference_agreement": max_fd_error <= FD_TOLERANCE,
            "zero_control_exact_noop": torch.equal(
                neutral.detach(),
                _forward(envelope, torch.zeros(count, dtype=DTYPE)).detach(),
            ),
            "objective_decreased": float(accepted_loss.detach())
            < float(neutral_loss.detach()),
            "control_is_non_neutral": bool(torch.any(torch.abs(controls) > 0.0)),
            "control_budget_respected": float(torch.linalg.vector_norm(controls))
            <= envelope.control_budget + FLOAT_TOLERANCE,
            "ineligible_sites_are_zero": bool(
                torch.all(controls[~envelope.eligible_mask] == 0.0)
            ),
            "pre_event_backward_credit_nonzero": bool(
                torch.any(torch.abs(gradient[: envelope.event_index]) > 0.0)
            ),
            "stable_axis_exact_identity": torch.equal(
                neutral.detach()[:, stability_index],
                accepted_trajectory[:, stability_index],
            ),
        }
        _require(all(checks.values()), "SINGLE_TRAJECTORY_CHECK_FAILED")
        return _seal(
            {
                "schema_version": CORE_PROTOCOL_VERSION,
                "lane_id": envelope.lane_id,
                "state_adapter_id": envelope.state_adapter_id,
                "state_adapter_config": dict(envelope.state_adapter_config),
                "axis_ids": list(envelope.axis_ids),
                "event_index": envelope.event_index,
                "neutral": {
                    "loss": neutral_parts,
                    "trajectory": _trajectory_rows(envelope, neutral.detach()),
                },
                "revised": {
                    "loss": accepted_parts,
                    "trajectory": _trajectory_rows(envelope, accepted_trajectory),
                },
                "credit_map": credit_rows,
                "control_l2": _finite(
                    float(torch.linalg.vector_norm(controls)), "CONTROL_L2"
                ),
                "control_budget": envelope.control_budget,
                "backtracking_steps": backtracking_steps,
                "finite_difference_max_abs_error": _finite(
                    max_fd_error, "FD_MAX_ERROR"
                ),
                "checks": checks,
                "gradient_boundary": "detached_public_trajectory_after_state_adapter",
            }
        )


def _core_lane_material(
    envelope: TrajectoryEnvelope,
    receipt: Mapping[str, Any],
    *,
    label: str,
) -> tuple[JsonObject, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """Validate one sealed core lane against the admitted public envelope."""

    snapshot = _sealed_snapshot(receipt, label)
    _require(
        snapshot.get("schema_version") == CORE_PROTOCOL_VERSION,
        f"{label}_SCHEMA_MISMATCH",
    )
    _require(snapshot.get("lane_id") == envelope.lane_id, f"{label}_LANE_MISMATCH")
    _require(
        snapshot.get("state_adapter_id") == envelope.state_adapter_id,
        f"{label}_STATE_ADAPTER_MISMATCH",
    )
    _require(
        snapshot.get("state_adapter_config") == dict(envelope.state_adapter_config),
        f"{label}_STATE_ADAPTER_CONFIG_MISMATCH",
    )
    _require(
        snapshot.get("axis_ids") == list(envelope.axis_ids),
        f"{label}_AXIS_MISMATCH",
    )
    _require(
        snapshot.get("event_index") == envelope.event_index,
        f"{label}_EVENT_INDEX_MISMATCH",
    )
    _require(
        _finite(snapshot.get("control_budget"), f"{label}_CONTROL_BUDGET")
        == envelope.control_budget,
        f"{label}_CONTROL_BUDGET_MISMATCH",
    )
    _require(
        snapshot.get("gradient_boundary")
        == "detached_public_trajectory_after_state_adapter",
        f"{label}_GRADIENT_BOUNDARY_MISMATCH",
    )

    credit = snapshot.get("credit_map")
    _require(
        isinstance(credit, list) and len(credit) == len(envelope.evidence_ids),
        f"{label}_CREDIT_MAP_INVALID",
    )
    gradients: list[float] = []
    controls: list[float] = []
    for index, row in enumerate(credit):
        _require(isinstance(row, Mapping), f"{label}_CREDIT_ROW_INVALID")
        _require(row.get("step") == index + 1, f"{label}_CREDIT_STEP_MISMATCH")
        _require(
            row.get("evidence_id") == envelope.evidence_ids[index],
            f"{label}_CREDIT_EVIDENCE_MISMATCH",
        )
        _require(
            row.get("role") == envelope.roles[index],
            f"{label}_CREDIT_ROLE_MISMATCH",
        )
        _require(
            isinstance(row.get("eligible"), bool)
            and row["eligible"] == bool(envelope.eligible_mask[index]),
            f"{label}_CREDIT_ELIGIBILITY_MISMATCH",
        )
        gradient = _finite(row.get("gradient"), f"{label}_CREDIT_GRADIENT")
        control = _finite(row.get("control"), f"{label}_CREDIT_CONTROL")
        magnitude = _finite(row.get("absolute_control"), f"{label}_CREDIT_MAGNITUDE")
        _require(
            magnitude >= 0.0
            and math.isclose(
                magnitude,
                abs(control),
                rel_tol=1.0e-12,
                abs_tol=FLOAT_TOLERANCE,
            ),
            f"{label}_CREDIT_MAGNITUDE_MISMATCH",
        )
        if not bool(envelope.eligible_mask[index]):
            _require(
                gradient == 0.0 and control == 0.0,
                f"{label}_INELIGIBLE_CREDIT_NONZERO",
            )
        gradients.append(gradient)
        controls.append(control)

    gradient_tensor = torch.tensor(gradients, dtype=DTYPE)
    control_tensor = torch.tensor(controls, dtype=DTYPE)
    control_l2 = _finite(snapshot.get("control_l2"), f"{label}_CONTROL_L2")
    expected_l2 = _finite(
        float(torch.linalg.vector_norm(control_tensor)),
        f"{label}_EXPECTED_CONTROL_L2",
    )
    _require(
        math.isclose(
            control_l2,
            expected_l2,
            rel_tol=1.0e-12,
            abs_tol=FLOAT_TOLERANCE,
        ),
        f"{label}_CONTROL_L2_MISMATCH",
    )
    _require(
        control_l2 <= envelope.control_budget + FLOAT_TOLERANCE,
        f"{label}_CONTROL_BUDGET_EXCEEDED",
    )

    zero = torch.zeros(len(envelope.evidence_ids), dtype=DTYPE)
    neutral_trajectory = _forward(envelope, zero)
    revised_trajectory = _forward(envelope, control_tensor)
    _, neutral_loss = _loss(envelope, zero, neutral_trajectory)
    _, revised_loss = _loss(envelope, control_tensor, revised_trajectory)
    _require(
        snapshot.get("neutral")
        == {
            "loss": neutral_loss,
            "trajectory": _trajectory_rows(envelope, neutral_trajectory),
        },
        f"{label}_NEUTRAL_REPLAY_MISMATCH",
    )
    _require(
        snapshot.get("revised")
        == {
            "loss": revised_loss,
            "trajectory": _trajectory_rows(envelope, revised_trajectory),
        },
        f"{label}_REVISED_REPLAY_MISMATCH",
    )
    return (
        snapshot,
        gradient_tensor,
        control_tensor,
        neutral_trajectory,
        revised_trajectory,
    )


def _validate_single_core_receipt(
    envelope: TrajectoryEnvelope,
    receipt: Mapping[str, Any],
) -> JsonObject:
    snapshot, gradients, controls, neutral, revised = _core_lane_material(
        envelope,
        receipt,
        label="CORE_RECEIPT",
    )
    zero = torch.zeros(len(envelope.evidence_ids), dtype=DTYPE)
    fd_errors = [
        abs(_central_difference(envelope, zero, index) - float(gradients[index]))
        if bool(envelope.eligible_mask[index])
        else abs(float(gradients[index]))
        for index in range(len(envelope.evidence_ids))
    ]
    max_fd_error = max(fd_errors, default=0.0)
    observed_fd_error = _finite(
        snapshot.get("finite_difference_max_abs_error"),
        "CORE_RECEIPT_FD_MAX_ERROR",
    )
    _require(
        math.isclose(
            observed_fd_error,
            max_fd_error,
            rel_tol=1.0e-9,
            abs_tol=1.0e-15,
        ),
        "CORE_RECEIPT_FD_ERROR_MISMATCH",
    )
    backtracking_steps = snapshot.get("backtracking_steps")
    _require(
        isinstance(backtracking_steps, int)
        and not isinstance(backtracking_steps, bool)
        and 0 <= backtracking_steps <= 20,
        "CORE_RECEIPT_BACKTRACKING_STEPS_INVALID",
    )
    expected_controls = _project_controls(
        -envelope.learning_rate * gradients,
        envelope.eligible_mask,
        envelope.control_budget,
    )
    neutral_loss, _ = _loss(envelope, zero, neutral)
    accepted = False
    expected_backtracking_steps = 0
    for expected_backtracking_steps in range(21):
        candidate_trajectory = _forward(envelope, expected_controls)
        candidate_loss, _ = _loss(
            envelope,
            expected_controls,
            candidate_trajectory,
        )
        if float(candidate_loss) < float(neutral_loss) - 1.0e-12:
            accepted = True
            break
        expected_controls = 0.5 * expected_controls
    _require(accepted, "CORE_RECEIPT_UPDATE_HAS_NO_DESCENT")
    _require(
        torch.equal(controls, expected_controls),
        "CORE_RECEIPT_CONTROL_UPDATE_MISMATCH",
    )
    _require(
        backtracking_steps == expected_backtracking_steps,
        "CORE_RECEIPT_BACKTRACKING_STEPS_MISMATCH",
    )
    stability_index = envelope.axis_ids.index("stability")
    expected_checks = {
        "real_backward_executed_once": True,
        "central_finite_difference_agreement": max_fd_error <= FD_TOLERANCE,
        "zero_control_exact_noop": torch.equal(
            neutral,
            _forward(envelope, zero),
        ),
        "objective_decreased": float(snapshot["revised"]["loss"]["total"])
        < float(snapshot["neutral"]["loss"]["total"]),
        "control_is_non_neutral": bool(torch.any(torch.abs(controls) > 0.0)),
        "control_budget_respected": float(torch.linalg.vector_norm(controls))
        <= envelope.control_budget + FLOAT_TOLERANCE,
        "ineligible_sites_are_zero": bool(
            torch.all(controls[~envelope.eligible_mask] == 0.0)
        ),
        "pre_event_backward_credit_nonzero": bool(
            torch.any(torch.abs(gradients[: envelope.event_index]) > 0.0)
        ),
        "stable_axis_exact_identity": torch.equal(
            neutral[:, stability_index],
            revised[:, stability_index],
        ),
    }
    _require(
        snapshot.get("checks") == expected_checks and all(expected_checks.values()),
        "CORE_RECEIPT_CHECKS_INVALID",
    )
    return snapshot


@dataclass(frozen=True)
class ActuatorProgram:
    lane_id: str
    reinspect: tuple[tuple[str, int, float], ...]
    suppress: tuple[str, ...]
    preserve: tuple[str, ...]
    steps: tuple[str, ...]
    source_credit_fingerprint_sha256: str

    def to_dict(self) -> JsonObject:
        return _seal(
            {
                "schema_version": "ebrt-actuator-program-v0.7.1",
                "lane_id": self.lane_id,
                "reinspect": [
                    {
                        "evidence_id": evidence_id,
                        "allocation_units": units,
                        "signed_control": control,
                    }
                    for evidence_id, units, control in self.reinspect
                ],
                "suppress_evidence_ids": list(self.suppress),
                "preserve_evidence_ids": list(self.preserve),
                "steps": list(self.steps),
                "source_credit_fingerprint_sha256": self.source_credit_fingerprint_sha256,
            }
        )


class ActuatorAdapter(Protocol):
    adapter_id: str

    def compile(
        self,
        task: RevisionTask,
        optimized: Mapping[str, Any],
        *,
        lane_id: str,
    ) -> ActuatorProgram: ...


def _largest_remainder_units(weights: Sequence[float], total: int = 100) -> list[int]:
    _require(total > 0 and len(weights) > 0, "ALLOCATION_INPUT_INVALID")
    clipped = [max(0.0, float(row)) for row in weights]
    weight_sum = sum(clipped)
    if weight_sum <= 0.0:
        clipped = [1.0] * len(clipped)
        weight_sum = float(len(clipped))
    raw = [total * value / weight_sum for value in clipped]
    floors = [math.floor(value) for value in raw]
    remainder = total - sum(floors)
    order = sorted(
        range(len(raw)), key=lambda index: (-(raw[index] - floors[index]), index)
    )
    for index in order[:remainder]:
        floors[index] += 1
    return floors


@dataclass(frozen=True)
class PublicRevisionActuator:
    adapter_id: str = "public-revision-actuator-v0.7.1"

    def compile(
        self,
        task: RevisionTask,
        optimized: Mapping[str, Any],
        *,
        lane_id: str,
    ) -> ActuatorProgram:
        _require(optimized.get("lane_id") == lane_id, "ACTUATOR_LANE_MISMATCH")
        _require(
            optimized.get("fingerprint_sha256")
            == _fingerprint(_without_fingerprint(optimized)),
            "CONTROL_RECEIPT_FINGERPRINT_INVALID",
        )
        credit = optimized.get("credit_map")
        _require(isinstance(credit, list), "CREDIT_MAP_INVALID")
        known_rows = {row.evidence_id: row for row in task.evidence}
        rows: dict[str, Mapping[str, Any]] = {}
        for row in credit:
            _require(isinstance(row, Mapping), "CREDIT_MAP_ROW_INVALID")
            evidence_id = row.get("evidence_id")
            _require(
                isinstance(evidence_id, str) and evidence_id in known_rows,
                "CREDIT_MAP_EVIDENCE_UNKNOWN",
            )
            _require(evidence_id not in rows, "CREDIT_MAP_EVIDENCE_DUPLICATE")
            source = known_rows[evidence_id]
            _require(row.get("step") == source.ordinal, "CREDIT_MAP_STEP_MISMATCH")
            _require(row.get("role") == source.role, "CREDIT_MAP_ROLE_MISMATCH")
            _require(
                isinstance(row.get("eligible"), bool), "CREDIT_MAP_ELIGIBLE_INVALID"
            )
            admitted_eligible = row["eligible"]
            gradient = _finite(row.get("gradient"), "CREDIT_MAP_GRADIENT")
            control = _finite(row.get("control"), "CREDIT_MAP_CONTROL")
            magnitude = _finite(row.get("absolute_control"), "CREDIT_MAP_MAGNITUDE")
            _require(magnitude >= 0.0, "CREDIT_MAP_MAGNITUDE_NEGATIVE")
            _require(
                math.isclose(
                    magnitude,
                    abs(control),
                    rel_tol=1.0e-12,
                    abs_tol=FLOAT_TOLERANCE,
                ),
                "CREDIT_MAP_MAGNITUDE_MISMATCH",
            )
            if not admitted_eligible:
                _require(
                    control == 0.0 and gradient == 0.0, "INELIGIBLE_CREDIT_NONZERO"
                )
            rows[evidence_id] = row
        _require(set(rows) == set(known_rows), "CREDIT_MAP_COVERAGE_MISMATCH")
        invalidated = set(task.event.invalidated_evidence_ids)
        stable = set(task.event.stable_evidence_ids)
        correction = task.event.correction_evidence_id
        eligible = [
            row.evidence_id
            for row in task.evidence
            if row.evidence_id not in invalidated | stable
            and bool(rows[row.evidence_id]["eligible"])
        ]
        ranked = sorted(
            eligible,
            key=lambda evidence_id: (
                -float(rows[evidence_id]["absolute_control"]),
                next(
                    row.ordinal
                    for row in task.evidence
                    if row.evidence_id == evidence_id
                ),
            ),
        )
        chosen = [correction] + [row for row in ranked if row != correction]
        chosen = chosen[: task.reinspection_count]
        _require(correction in chosen, "CORRECTION_NOT_REINSPECTED")
        weights = [float(rows[row]["absolute_control"]) for row in chosen]
        _require(
            any(weight > 0.0 for weight in weights),
            "NO_REALIZED_REINSPECTION_CONTROL",
        )
        units = _largest_remainder_units(weights)
        reinspect = tuple(
            (evidence_id, allocation, float(rows[evidence_id]["control"]))
            for evidence_id, allocation in zip(chosen, units, strict=True)
        )
        _require(sum(row[1] for row in reinspect) == 100, "ALLOCATION_NOT_CLOSED")
        _require(
            not set(chosen) & (invalidated | stable),
            "ACTUATOR_ROLE_OVERLAP",
        )
        steps = (
            "LOAD_FULL_CONTEXT",
            "SUPPRESS_INVALIDATED_SUPPORT",
            "REINSPECT_BY_BACKWARD_CREDIT",
            "PRESERVE_STABLE_CONSTRAINTS",
            "REGENERATE_ONCE",
        )
        return ActuatorProgram(
            lane_id=lane_id,
            reinspect=reinspect,
            suppress=tuple(task.event.invalidated_evidence_ids),
            preserve=tuple(task.event.stable_evidence_ids),
            steps=steps,
            source_credit_fingerprint_sha256=str(optimized["fingerprint_sha256"]),
        )


def _validate_compiled_program(
    task: RevisionTask,
    optimized: Mapping[str, Any],
    program: ActuatorProgram,
    *,
    lane_id: str,
) -> None:
    _require(isinstance(program, ActuatorProgram), "ACTUATOR_PROGRAM_TYPE_INVALID")
    expected = PublicRevisionActuator().compile(
        task,
        optimized,
        lane_id=lane_id,
    )
    _require(program == expected, "ACTUATOR_PROGRAM_BINDING_MISMATCH")


@dataclass(frozen=True)
class AdapterDescriptor:
    adapter_id: str
    model_id: str
    interface_kind: Literal[
        "deterministic_conformance", "local_open_weight", "hosted_api"
    ]
    state_visibility: Literal["public_only", "native_latent"]
    differentiable_through_model: bool = False
    generation_config: tuple[tuple[str, str | int | float | bool], ...] = ()

    def to_dict(self) -> JsonObject:
        configuration = dict(self.generation_config)
        return {
            "adapter_id": self.adapter_id,
            "model_id": self.model_id,
            "interface_kind": self.interface_kind,
            "state_visibility": self.state_visibility,
            "differentiable_through_model": self.differentiable_through_model,
            "generation_config": configuration,
            "generation_config_fingerprint_sha256": _fingerprint(configuration),
        }


def _validate_adapter_descriptor(descriptor: AdapterDescriptor, label: str) -> None:
    _safe_id(descriptor.adapter_id, f"{label}_ADAPTER_ID")
    _require(
        isinstance(descriptor.model_id, str)
        and bool(descriptor.model_id.strip())
        and len(descriptor.model_id) <= 512
        and all(character.isprintable() for character in descriptor.model_id),
        f"{label}_MODEL_ID_INVALID",
    )
    _require(
        descriptor.interface_kind
        in {"deterministic_conformance", "local_open_weight", "hosted_api"},
        f"{label}_INTERFACE_KIND_INVALID",
    )
    _require(
        descriptor.state_visibility in {"public_only", "native_latent"},
        f"{label}_STATE_VISIBILITY_INVALID",
    )
    _require(
        descriptor.differentiable_through_model is False,
        f"{label}_GRADIENT_BOUNDARY_INVALID",
    )
    _require(
        isinstance(descriptor.generation_config, tuple),
        f"{label}_GENERATION_CONFIG_INVALID",
    )
    configuration_keys: list[str] = []
    for row in descriptor.generation_config:
        _require(
            isinstance(row, tuple) and len(row) == 2,
            f"{label}_GENERATION_CONFIG_ROW_INVALID",
        )
        key, value = row
        _safe_id(key, f"{label}_GENERATION_CONFIG_KEY")
        _require(
            isinstance(value, (str, int, float, bool)),
            f"{label}_GENERATION_CONFIG_VALUE_INVALID",
        )
        if isinstance(value, str):
            _require(
                bool(value)
                and len(value) <= 512
                and all(character.isprintable() for character in value),
                f"{label}_GENERATION_CONFIG_VALUE_INVALID",
            )
        elif isinstance(value, float):
            _finite(value, f"{label}_GENERATION_CONFIG_VALUE")
        configuration_keys.append(key)
    _require(
        configuration_keys == sorted(configuration_keys)
        and len(configuration_keys) == len(set(configuration_keys)),
        f"{label}_GENERATION_CONFIG_KEYS_INVALID",
    )


@dataclass(frozen=True)
class ModelResult:
    answer: str
    support_ids: tuple[str, ...]
    raw_text: str
    descriptor: AdapterDescriptor
    request_fingerprint_sha256: str
    latency_ms: float
    logical_calls: int = 1

    def to_dict(self) -> JsonObject:
        return _seal(
            {
                "schema_version": "ebrt-model-result-v0.7.1",
                "answer": self.answer,
                "support_ids": list(self.support_ids),
                "raw_text": self.raw_text,
                "adapter": self.descriptor.to_dict(),
                "request_fingerprint_sha256": self.request_fingerprint_sha256,
                "latency_ms": _finite(self.latency_ms, "LATENCY_MS"),
                "logical_calls": self.logical_calls,
            }
        )


class ModelAdapter(Protocol):
    descriptor: AdapterDescriptor

    def generate(
        self,
        task: RevisionTask,
        program: ActuatorProgram,
        *,
        prompt_policy: Literal["chronological", "credit_first"],
    ) -> ModelResult: ...


def _evidence_order(
    task: RevisionTask,
    program: ActuatorProgram,
    prompt_policy: Literal["chronological", "credit_first"],
) -> list[Evidence]:
    chronological = list(task.evidence)
    if prompt_policy == "chronological":
        return chronological
    _require(prompt_policy == "credit_first", "PROMPT_POLICY_INVALID")
    by_id = {row.evidence_id: row for row in task.evidence}
    first = [by_id[row[0]] for row in program.reinspect]
    seen = {row.evidence_id for row in first}
    remainder = [
        row
        for row in chronological
        if row.evidence_id not in seen and row.evidence_id not in set(program.suppress)
    ]
    suppressed = [by_id[row] for row in program.suppress]
    return first + remainder + suppressed


def build_model_invocation(
    task: RevisionTask,
    program: ActuatorProgram,
    *,
    prompt_policy: Literal["chronological", "credit_first"],
) -> JsonObject:
    ordered = _evidence_order(task, program, prompt_policy)
    public_program = program.to_dict()
    reinspect = json.dumps(
        public_program["reinspect"],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    suppress = ",".join(program.suppress) or "NONE"
    preserve = ",".join(program.preserve) or "NONE"
    prompt = "\n".join(
        [
            "You are a generator behind the EBRT model-interface adapter.",
            "Apply the public revision program to the full evidence context.",
            "Return exactly two lines and nothing else:",
            f"ANSWER=<{' or '.join(task.answer_choices)}>",
            "SUPPORT=<comma-separated active evidence IDs>",
            "SUPPORT must include the late correction that authorizes the revision.",
            "Do not include PRESERVE-only evidence unless it directly supports the answer.",
            "",
            f"Question: {task.question}",
            "Evidence:",
            *[f"{row.evidence_id}: {row.text}" for row in ordered],
            "Revision program:",
            f"REINSPECT_JSON {reinspect}",
            f"SUPPRESS {suppress}",
            f"PRESERVE {preserve}",
            "Do not cite suppressed evidence as active support.",
        ]
    )
    return _seal(
        {
            "schema_version": "ebrt-model-invocation-v0.7.1",
            "task_id": task.task_id,
            "lane_id": program.lane_id,
            "prompt_policy": prompt_policy,
            "answer_choices": list(task.answer_choices),
            "evidence_ids": [row.evidence_id for row in ordered],
            "actuator_program": public_program,
            "program_fingerprint_sha256": public_program["fingerprint_sha256"],
            "prompt": prompt,
        }
    )


def _parse_model_text(
    raw_text: str,
    *,
    task: RevisionTask,
) -> tuple[str, tuple[str, ...]]:
    _require(isinstance(raw_text, str) and bool(raw_text), "MODEL_TEXT_INVALID")
    normalized = raw_text.replace("\r\n", "\n")
    if normalized.endswith("\n"):
        normalized = normalized[:-1]
    lines = normalized.split("\n")
    _require(len(lines) == 2, "MODEL_RESPONSE_LINE_COUNT_INVALID")
    answer_match = re.fullmatch(
        r"[ \t]*ANSWER[ \t]*=[ \t]*(.*?)[ \t]*",
        lines[0],
        flags=re.IGNORECASE,
    )
    support_match = re.fullmatch(
        r"[ \t]*SUPPORT[ \t]*=[ \t]*(.*?)[ \t]*",
        lines[1],
        flags=re.IGNORECASE,
    )
    _require(answer_match is not None, "MODEL_ANSWER_LINE_INVALID")
    _require(support_match is not None, "MODEL_SUPPORT_LINE_INVALID")
    answer_value = answer_match.group(1).strip()
    _require(bool(answer_value), "MODEL_ANSWER_EMPTY")
    if answer_value in task.answer_choices:
        answer = answer_value
    elif (
        answer_value.startswith("<")
        and answer_value.endswith(">")
        and answer_value[1:-1] in task.answer_choices
    ):
        answer = answer_value[1:-1]
    else:
        raise EBRTError("MODEL_ANSWER_OUTSIDE_CHOICES")
    support_value = support_match.group(1).strip()
    if support_value.startswith("<") and support_value.endswith(">"):
        support_value = support_value[1:-1]
    support_tokens = tuple(
        row.strip() for row in support_value.split(",") if row.strip()
    )
    if any(row.upper() == "NONE" for row in support_tokens):
        _require(support_tokens == ("NONE",), "MODEL_SUPPORT_NONE_MIXED")
        support: tuple[str, ...] = ()
    else:
        support = support_tokens
    known = {row.evidence_id for row in task.evidence}
    _require(len(support) == len(set(support)), "MODEL_SUPPORT_DUPLICATE")
    _require(set(support).issubset(known), "MODEL_SUPPORT_UNKNOWN")
    return answer, support


@dataclass
class CallableModelAdapter:
    """Provider-neutral shim: hosted SDKs can bind at this exact callable edge."""

    descriptor: AdapterDescriptor
    callback: Callable[[Mapping[str, Any]], str]

    def generate(
        self,
        task: RevisionTask,
        program: ActuatorProgram,
        *,
        prompt_policy: Literal["chronological", "credit_first"],
    ) -> ModelResult:
        invocation = build_model_invocation(task, program, prompt_policy=prompt_policy)
        started = time.perf_counter()
        raw = self.callback(_clone(invocation))
        latency_ms = (time.perf_counter() - started) * 1000.0
        _require(isinstance(raw, str), "MODEL_CALLBACK_MUST_RETURN_TEXT")
        answer, support = _parse_model_text(raw, task=task)
        return ModelResult(
            answer=answer,
            support_ids=support,
            raw_text=raw,
            descriptor=self.descriptor,
            request_fingerprint_sha256=str(invocation["fingerprint_sha256"]),
            latency_ms=latency_ms,
        )


def _local_model_id(path: Path, *, explicit: str | None = None) -> str:
    if explicit is not None:
        _require(
            isinstance(explicit, str)
            and bool(explicit.strip())
            and len(explicit) <= 512
            and all(character.isprintable() for character in explicit),
            "LOCAL_MODEL_ID_INVALID",
        )
        identity, separator, revision = explicit.rpartition("@")
        _require(
            separator == "@" and bool(identity) and bool(revision),
            "LOCAL_MODEL_ID_REVISION_REQUIRED",
        )
        return explicit
    for candidate in (path, *path.parents):
        if candidate.name.startswith("models--"):
            repository = candidate.name.removeprefix("models--").replace("--", "/")
            if repository:
                relative_parts = path.relative_to(candidate).parts
                if len(relative_parts) >= 2 and relative_parts[0] == "snapshots":
                    return f"{repository}@{relative_parts[1]}"
                raise EBRTError("LOCAL_MODEL_ID_REVISION_REQUIRED")
    raise EBRTError("LOCAL_MODEL_ID_REVISION_REQUIRED")


class SharedMLXRuntime:
    """Lazy one-process MLX runtime shared by one or more v0.8 lanes."""

    def __init__(
        self,
        model_path: str,
        *,
        model_id: str | None = None,
        max_tokens: int = 48,
        seed: int = 0,
    ):
        path = Path(model_path).expanduser().resolve()
        _require(path.is_dir(), "LOCAL_MODEL_PATH_NOT_FOUND")
        _require(
            any(path.glob("*.safetensors"))
            or any(path.glob("*.safetensors.index.json")),
            "LOCAL_MODEL_WEIGHTS_NOT_FOUND",
        )
        self.model_path = path
        self._model_id = _local_model_id(path, explicit=model_id)
        _require(
            isinstance(self._model_id, str)
            and bool(self._model_id.strip())
            and len(self._model_id) <= 512
            and all(character.isprintable() for character in self._model_id),
            "LOCAL_MODEL_ID_INVALID",
        )
        _require(
            isinstance(max_tokens, int)
            and not isinstance(max_tokens, bool)
            and 1 <= max_tokens <= 4096,
            "MLX_MAX_TOKENS_INVALID",
        )
        _require(
            isinstance(seed, int)
            and not isinstance(seed, bool)
            and 0 <= seed <= 2**63 - 1,
            "MLX_SEED_INVALID",
        )
        self.max_tokens = max_tokens
        self.seed = seed
        self._model: Any = None
        self._tokenizer: Any = None

    @property
    def model_id(self) -> str:
        return self._model_id

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            from mlx_lm import load
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise EBRTError("MLX_LM_NOT_INSTALLED") from exc
        try:
            self._model, self._tokenizer = load(str(self.model_path))
        except Exception as exc:  # pragma: no cover - model/runtime dependent
            raise EBRTError("MLX_MODEL_LOAD_FAILED") from exc

    def generate(self, prompt: str) -> str:
        self._load()
        try:
            import mlx.core as mx
            from mlx_lm import generate
            from mlx_lm.sample_utils import make_sampler
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise EBRTError("MLX_LM_NOT_INSTALLED") from exc
        try:
            mx.random.seed(self.seed)
            rendered = self._tokenizer.apply_chat_template(
                [{"role": "user", "content": prompt}],
                tokenize=False,
                add_generation_prompt=True,
            )
            return generate(
                self._model,
                self._tokenizer,
                prompt=rendered,
                max_tokens=self.max_tokens,
                sampler=make_sampler(temp=0.0),
                verbose=False,
            )
        except Exception as exc:  # pragma: no cover - model/runtime dependent
            raise EBRTError("MLX_GENERATION_FAILED") from exc


@dataclass
class MLXLocalAdapter:
    runtime: SharedMLXRuntime
    adapter_id: str

    @property
    def descriptor(self) -> AdapterDescriptor:
        return AdapterDescriptor(
            adapter_id=self.adapter_id,
            model_id=self.runtime.model_id,
            interface_kind="local_open_weight",
            state_visibility="public_only",
            differentiable_through_model=False,
            generation_config=(
                ("add_generation_prompt", True),
                ("max_tokens", self.runtime.max_tokens),
                ("sampler_temperature", 0.0),
                ("seed", self.runtime.seed),
            ),
        )

    def generate(
        self,
        task: RevisionTask,
        program: ActuatorProgram,
        *,
        prompt_policy: Literal["chronological", "credit_first"],
    ) -> ModelResult:
        invocation = build_model_invocation(task, program, prompt_policy=prompt_policy)
        started = time.perf_counter()
        raw = self.runtime.generate(str(invocation["prompt"]))
        latency_ms = (time.perf_counter() - started) * 1000.0
        answer, support = _parse_model_text(raw, task=task)
        return ModelResult(
            answer=answer,
            support_ids=support,
            raw_text=raw,
            descriptor=self.descriptor,
            request_fingerprint_sha256=str(invocation["fingerprint_sha256"]),
            latency_ms=latency_ms,
        )


def _structural_model_checks(
    task: RevisionTask,
    program: ActuatorProgram,
    result: ModelResult,
    *,
    expected_descriptor: AdapterDescriptor,
    expected_request_fingerprint_sha256: str,
) -> JsonObject:
    known = {row.evidence_id for row in task.evidence}
    try:
        parsed_raw = _parse_model_text(result.raw_text, task=task)
    except EBRTError:
        parsed_raw = None
    return {
        "raw_text_conforms_to_schema": parsed_raw is not None,
        "raw_text_matches_returned_fields": parsed_raw
        == (result.answer, result.support_ids),
        "answer_is_allowed": result.answer in task.answer_choices,
        "support_ids_are_known": set(result.support_ids).issubset(known),
        "invalidated_support_absent": not set(result.support_ids)
        & set(task.event.invalidated_evidence_ids),
        "correction_is_active_support": task.event.correction_evidence_id
        in set(result.support_ids),
        "typed_suppression_compiled": set(program.suppress)
        == set(task.event.invalidated_evidence_ids),
        "typed_preservation_compiled": set(program.preserve)
        == set(task.event.stable_evidence_ids),
        "one_model_invocation": result.logical_calls == 1,
        "request_fingerprint_matches_invocation": result.request_fingerprint_sha256
        == expected_request_fingerprint_sha256,
        "adapter_descriptor_matches_binding": result.descriptor == expected_descriptor,
        "latency_is_finite_and_nonnegative": math.isfinite(result.latency_ms)
        and result.latency_ms >= 0.0,
        "gradient_did_not_cross_model_boundary": (
            not expected_descriptor.differentiable_through_model
            and not result.descriptor.differentiable_through_model
        ),
    }


def _grade_contract(
    result: ModelResult | Mapping[str, Any],
    program: ActuatorProgram | Mapping[str, Any],
    contract: PostRunContract,
) -> JsonObject:
    if isinstance(result, ModelResult):
        answer = result.answer
        support_ids = set(result.support_ids)
    else:
        answer = str(result["answer"])
        support_ids = set(result["support_ids"])
    if isinstance(program, ActuatorProgram):
        preserve = set(program.preserve)
    else:
        preserve = set(program["preserve_evidence_ids"])
    checks = {
        "expected_answer": answer == contract.expected_answer,
        "required_support_present": set(contract.required_support_ids).issubset(
            support_ids
        ),
        "forbidden_support_absent": not set(contract.forbidden_support_ids)
        & support_ids,
        "required_compiled_preserve_present": set(
            contract.required_compiled_preserve_ids
        ).issubset(preserve),
    }
    contract_receipt = _seal(
        {
            "schema_version": POST_RUN_CONTRACT_VERSION,
            "expected_answer": contract.expected_answer,
            "required_support_ids": list(contract.required_support_ids),
            "forbidden_support_ids": list(contract.forbidden_support_ids),
            "required_compiled_preserve_ids": list(
                contract.required_compiled_preserve_ids
            ),
        }
    )
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "contract": contract_receipt,
        "checks": checks,
    }


def _is_trusted_builtin_core(core: Any, expected_type: type[Any]) -> bool:
    """Only the exact built-in implementation can attest this run's backward."""

    optimize = getattr(core, "optimize", None)
    return (
        type(core) is expected_type
        and getattr(optimize, "__func__", None) is expected_type.optimize
    )


class RevisionEngine:
    """v0.7.1 single-lane composition of the five public interfaces."""

    def __init__(
        self,
        *,
        core: BackwardRevisionCore | None = None,
        state_adapter: StateAdapter | None = None,
        actuator_adapter: ActuatorAdapter | None = None,
    ) -> None:
        self.core = core or BackwardRevisionCore()
        self.state_adapter = state_adapter or TypedPublicStateAdapter()
        self.actuator_adapter = actuator_adapter or PublicRevisionActuator()

    def run(
        self,
        task: RevisionTask,
        model_adapter: ModelAdapter,
        *,
        lane_id: str = "primary",
        prompt_policy: Literal["chronological", "credit_first"] = "credit_first",
        post_run_contract: PostRunContract | None = None,
    ) -> JsonObject:
        validate_task(task)
        if post_run_contract is not None:
            validate_contract(task, post_run_contract)
        envelope = _prepare_state_envelope(
            task,
            self.state_adapter,
            self.state_adapter.build(task, lane_id=lane_id),
            lane_id=lane_id,
            label="STATE_ADAPTER",
        )
        optimized = _validate_single_core_receipt(
            envelope,
            self.core.optimize(_clone_envelope(envelope)),
        )
        _require(
            _is_trusted_builtin_core(self.core, BackwardRevisionCore),
            "CORE_EXECUTION_UNVERIFIED",
        )
        program = self.actuator_adapter.compile(
            task,
            _clone(optimized),
            lane_id=lane_id,
        )
        _validate_compiled_program(
            task,
            optimized,
            program,
            lane_id=lane_id,
        )
        expected_descriptor = model_adapter.descriptor
        _require(
            isinstance(expected_descriptor, AdapterDescriptor),
            "MODEL_ADAPTER_DESCRIPTOR_INVALID",
        )
        _validate_adapter_descriptor(expected_descriptor, "MODEL_ADAPTER")
        expected_invocation = build_model_invocation(
            task, program, prompt_policy=prompt_policy
        )
        result = model_adapter.generate(task, program, prompt_policy=prompt_policy)
        _require(isinstance(result, ModelResult), "MODEL_RESULT_TYPE_INVALID")
        structural = _structural_model_checks(
            task,
            program,
            result,
            expected_descriptor=expected_descriptor,
            expected_request_fingerprint_sha256=str(
                expected_invocation["fingerprint_sha256"]
            ),
        )
        _require(all(structural.values()), "MODEL_RESULT_STRUCTURAL_FAILURE")
        contract_grade = (
            _grade_contract(result, program, post_run_contract)
            if post_run_contract is not None
            else {"status": "NOT_ASSESSED", "contract": None, "checks": {}}
        )
        return _seal(
            {
                "schema_version": RESULT_SCHEMA_VERSION,
                "mode": "single_lane_v0.7.1",
                "status": "PASS",
                "core_protocol": CORE_PROTOCOL_VERSION,
                "task_fingerprint_sha256": _fingerprint(task.to_public_dict()),
                "trajectory": optimized,
                "actuator": program.to_dict(),
                "model_result": result.to_dict(),
                "structural_verification": {
                    "status": "PASS",
                    "checks": structural,
                },
                "post_run_contract": contract_grade,
                "semantic_correctness_status": (
                    contract_grade["status"]
                    if post_run_contract is not None
                    else "NOT_ASSESSED"
                ),
                "effect_attribution_status": "NOT_ASSESSED",
                "claim_boundary": list(CLAIM_BOUNDARY),
            }
        )


@dataclass(frozen=True)
class JointLaneSpec:
    lane_id: str
    state_adapter: StateAdapter
    model_adapter: ModelAdapter
    prompt_policy: Literal["chronological", "credit_first"]
    weight: float = 1.0


def _joint_loss(
    envelopes: Sequence[TrajectoryEnvelope],
    weights: Sequence[float],
    slices: Sequence[slice],
    controls: torch.Tensor,
) -> tuple[torch.Tensor, JsonObject, list[torch.Tensor]]:
    lane_losses: list[torch.Tensor] = []
    lane_parts: JsonObject = {}
    trajectories: list[torch.Tensor] = []
    for envelope, weight, lane_slice in zip(envelopes, weights, slices, strict=True):
        lane_controls = controls[lane_slice]
        trajectory = _forward(envelope, lane_controls)
        lane_loss, parts = _loss(envelope, lane_controls, trajectory)
        trajectories.append(trajectory)
        lane_losses.append(weight * lane_loss)
        lane_parts[envelope.lane_id] = parts
    consensus = torch.zeros((), dtype=DTYPE)
    for left in range(len(trajectories)):
        for right in range(left + 1, len(trajectories)):
            consensus = consensus + 0.5 * torch.mean(
                (trajectories[left][-1, :2] - trajectories[right][-1, :2]).square()
            )
    total = torch.stack(lane_losses).sum() + 0.10 * consensus
    return (
        total,
        {
            "lanes": lane_parts,
            "consensus": _finite(float(consensus.detach()), "CONSENSUS_LOSS"),
            "total": _finite(float(total.detach()), "JOINT_LOSS"),
        },
        trajectories,
    )


def _joint_slices(envelopes: Sequence[TrajectoryEnvelope]) -> tuple[slice, ...]:
    slices: list[slice] = []
    start = 0
    for envelope in envelopes:
        end = start + len(envelope.evidence_ids)
        slices.append(slice(start, end))
        start = end
    return tuple(slices)


class JointBackwardRevisionCore:
    """v0.8 block-adjoint over multiple public trajectory lanes."""

    def optimize(
        self,
        envelopes: Sequence[TrajectoryEnvelope],
        *,
        weights: Sequence[float],
    ) -> JsonObject:
        _require(len(envelopes) >= 2, "JOINT_LANE_COUNT_TOO_SMALL")
        _require(len(envelopes) == len(weights), "JOINT_WEIGHT_COUNT_MISMATCH")
        paired = sorted(
            zip(envelopes, weights, strict=True), key=lambda row: row[0].lane_id
        )
        ordered = tuple(row[0] for row in paired)
        ordered_weights = tuple(_finite(row[1], "JOINT_WEIGHT") for row in paired)
        _require(all(row > 0.0 for row in ordered_weights), "JOINT_WEIGHT_INVALID")
        lane_ids = [row.lane_id for row in ordered]
        _require(len(lane_ids) == len(set(lane_ids)), "JOINT_LANE_ID_DUPLICATE")
        first = ordered[0]
        for envelope in ordered[1:]:
            _require(envelope.axis_ids == first.axis_ids, "JOINT_AXIS_MISMATCH")
            _require(
                envelope.evidence_ids == first.evidence_ids,
                "JOINT_EVIDENCE_MISMATCH",
            )
            _require(
                torch.equal(envelope.target, first.target), "JOINT_TARGET_MISMATCH"
            )
            _require(envelope.event_index == first.event_index, "JOINT_EVENT_MISMATCH")

        slices = _joint_slices(ordered)
        total_controls = slices[-1].stop
        zero = torch.zeros(total_controls, dtype=DTYPE, requires_grad=True)
        neutral_loss, neutral_parts, neutral_trajectories = _joint_loss(
            ordered, ordered_weights, slices, zero
        )
        neutral_loss.backward()
        gradient = zero.grad
        _require(gradient is not None, "JOINT_BACKWARD_DID_NOT_POPULATE_GRADIENT")
        _require(bool(torch.all(torch.isfinite(gradient))), "JOINT_GRADIENT_NONFINITE")

        eligible_flat = torch.cat([row.eligible_mask for row in ordered])
        fd_errors: list[float] = []
        for index in range(total_controls):
            if not bool(eligible_flat[index]):
                fd_errors.append(abs(float(gradient[index])))
                continue
            plus = zero.detach().clone()
            minus = zero.detach().clone()
            plus[index] += FD_EPSILON
            minus[index] -= FD_EPSILON
            plus_loss, _, _ = _joint_loss(ordered, ordered_weights, slices, plus)
            minus_loss, _, _ = _joint_loss(ordered, ordered_weights, slices, minus)
            fd = float((plus_loss - minus_loss) / (2.0 * FD_EPSILON))
            fd_errors.append(abs(fd - float(gradient[index])))
        max_fd_error = max(fd_errors, default=0.0)

        lane_controls: list[torch.Tensor] = []
        for envelope, lane_slice in zip(ordered, slices, strict=True):
            proposal = -envelope.learning_rate * gradient.detach()[lane_slice]
            lane_controls.append(
                _project_controls(
                    proposal, envelope.eligible_mask, envelope.control_budget
                )
            )
        controls = torch.cat(lane_controls)
        global_budget = math.sqrt(sum(row.control_budget**2 for row in ordered))
        global_norm = torch.linalg.vector_norm(controls)
        if float(global_norm) > global_budget:
            controls = controls * (global_budget / global_norm)

        accepted = False
        accepted_loss = neutral_loss.detach()
        accepted_parts = neutral_parts
        accepted_trajectories = [row.detach() for row in neutral_trajectories]
        backtracking_steps = 0
        for backtracking_steps in range(21):
            candidate_loss, candidate_parts, candidate_trajectories = _joint_loss(
                ordered, ordered_weights, slices, controls
            )
            if float(candidate_loss.detach()) < float(neutral_loss.detach()) - 1.0e-12:
                accepted = True
                accepted_loss = candidate_loss.detach()
                accepted_parts = candidate_parts
                accepted_trajectories = [row.detach() for row in candidate_trajectories]
                break
            controls = 0.5 * controls
        _require(accepted, "NO_DESCENDING_JOINT_CONTROL")

        lane_receipts: JsonObject = {}
        for envelope, lane_slice, neutral_trajectory, revised_trajectory in zip(
            ordered,
            slices,
            neutral_trajectories,
            accepted_trajectories,
            strict=True,
        ):
            lane_gradient = gradient[lane_slice]
            lane_control = controls[lane_slice]
            stability_index = envelope.axis_ids.index("stability")
            lane_checks = {
                "pre_event_backward_credit_nonzero": bool(
                    torch.any(torch.abs(lane_gradient[: envelope.event_index]) > 0.0)
                ),
                "control_budget_respected": float(
                    torch.linalg.vector_norm(lane_control)
                )
                <= envelope.control_budget + FLOAT_TOLERANCE,
                "ineligible_sites_are_zero": bool(
                    torch.all(lane_control[~envelope.eligible_mask] == 0.0)
                ),
                "stable_axis_exact_identity": torch.equal(
                    neutral_trajectory[:, stability_index],
                    revised_trajectory[:, stability_index],
                ),
            }
            _require(all(lane_checks.values()), "JOINT_LANE_CHECK_FAILED")
            lane_receipts[envelope.lane_id] = _seal(
                {
                    "schema_version": CORE_PROTOCOL_VERSION,
                    "lane_id": envelope.lane_id,
                    "state_adapter_id": envelope.state_adapter_id,
                    "state_adapter_config": dict(envelope.state_adapter_config),
                    "axis_ids": list(envelope.axis_ids),
                    "event_index": envelope.event_index,
                    "neutral": {
                        "loss": neutral_parts["lanes"][envelope.lane_id],
                        "trajectory": _trajectory_rows(envelope, neutral_trajectory),
                    },
                    "revised": {
                        "loss": accepted_parts["lanes"][envelope.lane_id],
                        "trajectory": _trajectory_rows(envelope, revised_trajectory),
                    },
                    "credit_map": [
                        {
                            "step": index + 1,
                            "evidence_id": evidence_id,
                            "role": envelope.roles[index],
                            "eligible": bool(envelope.eligible_mask[index]),
                            "gradient": _finite(
                                float(lane_gradient[index]), "JOINT_CREDIT_GRADIENT"
                            ),
                            "control": _finite(
                                float(lane_control[index]), "JOINT_CREDIT_CONTROL"
                            ),
                            "absolute_control": _finite(
                                abs(float(lane_control[index])),
                                "JOINT_CREDIT_MAGNITUDE",
                            ),
                        }
                        for index, evidence_id in enumerate(envelope.evidence_ids)
                    ],
                    "control_l2": _finite(
                        float(torch.linalg.vector_norm(lane_control)),
                        "JOINT_LANE_CONTROL_L2",
                    ),
                    "control_budget": envelope.control_budget,
                    "checks": lane_checks,
                    "gradient_boundary": "detached_public_trajectory_after_state_adapter",
                }
            )

        checks = {
            "one_joint_backward_executed": True,
            "block_finite_difference_agreement": max_fd_error <= FD_TOLERANCE,
            "joint_objective_decreased": float(accepted_loss.detach())
            < float(neutral_loss.detach()),
            "global_control_is_non_neutral": bool(torch.any(torch.abs(controls) > 0.0)),
            "global_budget_respected": float(torch.linalg.vector_norm(controls))
            <= global_budget + FLOAT_TOLERANCE,
            "lane_namespace_unique": len(lane_ids) == len(set(lane_ids)),
            "shared_axis_contract_exact": all(
                row.axis_ids == first.axis_ids for row in ordered
            ),
        }
        _require(all(checks.values()), "JOINT_TRAJECTORY_CHECK_FAILED")
        return _seal(
            {
                "schema_version": JOINT_PROTOCOL_VERSION,
                "lane_ids": lane_ids,
                "lane_weights": {
                    lane_id: weight
                    for lane_id, weight in zip(lane_ids, ordered_weights, strict=True)
                },
                "neutral_loss": neutral_parts,
                "revised_loss": accepted_parts,
                "lanes": lane_receipts,
                "global_control_l2": _finite(
                    float(torch.linalg.vector_norm(controls)),
                    "JOINT_GLOBAL_CONTROL_L2",
                ),
                "global_control_budget": global_budget,
                "backtracking_steps": backtracking_steps,
                "finite_difference_max_abs_error": _finite(
                    max_fd_error, "JOINT_FD_MAX_ERROR"
                ),
                "checks": checks,
                "gradient_boundary": "joint_adapter_supplied_public_trajectories",
            }
        )


def _validate_joint_core_receipt(
    envelopes: Sequence[TrajectoryEnvelope],
    weights: Sequence[float],
    receipt: Mapping[str, Any],
) -> JsonObject:
    """Validate a sealed block-adjoint receipt before any actuator can run."""

    _require(len(envelopes) == len(weights), "JOINT_CORE_RECEIPT_WEIGHT_MISMATCH")
    paired = sorted(
        zip(envelopes, weights, strict=True), key=lambda row: row[0].lane_id
    )
    ordered = tuple(row[0] for row in paired)
    ordered_weights = tuple(
        _finite(row[1], "JOINT_CORE_RECEIPT_WEIGHT") for row in paired
    )
    _require(
        len(ordered) >= 2 and all(weight > 0.0 for weight in ordered_weights),
        "JOINT_CORE_RECEIPT_WEIGHT_INVALID",
    )
    snapshot = _sealed_snapshot(receipt, "JOINT_CORE_RECEIPT")
    lane_ids = [envelope.lane_id for envelope in ordered]
    _require(
        snapshot.get("schema_version") == JOINT_PROTOCOL_VERSION,
        "JOINT_CORE_RECEIPT_SCHEMA_MISMATCH",
    )
    _require(
        snapshot.get("lane_ids") == lane_ids,
        "JOINT_CORE_RECEIPT_LANE_IDS_MISMATCH",
    )
    expected_weights = {
        lane_id: weight
        for lane_id, weight in zip(lane_ids, ordered_weights, strict=True)
    }
    _require(
        snapshot.get("lane_weights") == expected_weights,
        "JOINT_CORE_RECEIPT_WEIGHTS_MISMATCH",
    )
    _require(
        snapshot.get("gradient_boundary")
        == "joint_adapter_supplied_public_trajectories",
        "JOINT_CORE_RECEIPT_GRADIENT_BOUNDARY_MISMATCH",
    )
    lanes = snapshot.get("lanes")
    _require(
        isinstance(lanes, Mapping) and set(lanes) == set(lane_ids),
        "JOINT_CORE_RECEIPT_LANES_MISMATCH",
    )

    lane_material: dict[
        str, tuple[JsonObject, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]
    ] = {}
    for envelope in ordered:
        lane_receipt = lanes[envelope.lane_id]
        _require(
            isinstance(lane_receipt, Mapping),
            "JOINT_CORE_RECEIPT_LANE_TYPE_INVALID",
        )
        lane_material[envelope.lane_id] = _core_lane_material(
            envelope,
            lane_receipt,
            label="JOINT_CORE_LANE_RECEIPT",
        )

    slices = _joint_slices(ordered)
    gradients = torch.cat([lane_material[envelope.lane_id][1] for envelope in ordered])
    controls = torch.cat([lane_material[envelope.lane_id][2] for envelope in ordered])
    zero = torch.zeros(len(controls), dtype=DTYPE)
    _, expected_neutral_loss, neutral_trajectories = _joint_loss(
        ordered,
        ordered_weights,
        slices,
        zero,
    )
    backtracking_steps = snapshot.get("backtracking_steps")
    _require(
        isinstance(backtracking_steps, int)
        and not isinstance(backtracking_steps, bool)
        and 0 <= backtracking_steps <= 20,
        "JOINT_CORE_RECEIPT_BACKTRACKING_STEPS_INVALID",
    )
    expected_lane_controls = [
        _project_controls(
            -envelope.learning_rate * gradients[lane_slice],
            envelope.eligible_mask,
            envelope.control_budget,
        )
        for envelope, lane_slice in zip(ordered, slices, strict=True)
    ]
    expected_controls = torch.cat(expected_lane_controls)
    global_budget = math.sqrt(sum(row.control_budget**2 for row in ordered))
    expected_global_norm = torch.linalg.vector_norm(expected_controls)
    if float(expected_global_norm) > global_budget:
        expected_controls = expected_controls * (global_budget / expected_global_norm)
    accepted = False
    expected_backtracking_steps = 0
    for expected_backtracking_steps in range(21):
        candidate_loss, _, _ = _joint_loss(
            ordered,
            ordered_weights,
            slices,
            expected_controls,
        )
        if float(candidate_loss) < float(expected_neutral_loss["total"]) - 1.0e-12:
            accepted = True
            break
        expected_controls = 0.5 * expected_controls
    _require(accepted, "JOINT_CORE_RECEIPT_UPDATE_HAS_NO_DESCENT")
    _require(
        torch.equal(controls, expected_controls),
        "JOINT_CORE_RECEIPT_CONTROL_UPDATE_MISMATCH",
    )
    _require(
        backtracking_steps == expected_backtracking_steps,
        "JOINT_CORE_RECEIPT_BACKTRACKING_STEPS_MISMATCH",
    )
    _, expected_revised_loss, revised_trajectories = _joint_loss(
        ordered,
        ordered_weights,
        slices,
        controls,
    )
    _require(
        snapshot.get("neutral_loss") == expected_neutral_loss,
        "JOINT_CORE_RECEIPT_NEUTRAL_LOSS_MISMATCH",
    )
    _require(
        snapshot.get("revised_loss") == expected_revised_loss,
        "JOINT_CORE_RECEIPT_REVISED_LOSS_MISMATCH",
    )

    fd_errors: list[float] = []
    eligible_flat = torch.cat([envelope.eligible_mask for envelope in ordered])
    for index in range(len(controls)):
        if not bool(eligible_flat[index]):
            fd_errors.append(abs(float(gradients[index])))
            continue
        plus = zero.clone()
        minus = zero.clone()
        plus[index] += FD_EPSILON
        minus[index] -= FD_EPSILON
        plus_loss, _, _ = _joint_loss(
            ordered,
            ordered_weights,
            slices,
            plus,
        )
        minus_loss, _, _ = _joint_loss(
            ordered,
            ordered_weights,
            slices,
            minus,
        )
        finite_difference = float((plus_loss - minus_loss) / (2.0 * FD_EPSILON))
        fd_errors.append(abs(finite_difference - float(gradients[index])))
    max_fd_error = max(fd_errors, default=0.0)
    observed_fd_error = _finite(
        snapshot.get("finite_difference_max_abs_error"),
        "JOINT_CORE_RECEIPT_FD_MAX_ERROR",
    )
    _require(
        math.isclose(
            observed_fd_error,
            max_fd_error,
            rel_tol=1.0e-9,
            abs_tol=1.0e-15,
        ),
        "JOINT_CORE_RECEIPT_FD_ERROR_MISMATCH",
    )

    for envelope, neutral, revised in zip(
        ordered,
        neutral_trajectories,
        revised_trajectories,
        strict=True,
    ):
        _, lane_gradients, lane_controls, stored_neutral, stored_revised = (
            lane_material[envelope.lane_id]
        )
        _require(
            torch.equal(neutral, stored_neutral)
            and torch.equal(revised, stored_revised),
            "JOINT_CORE_RECEIPT_LANE_REPLAY_MISMATCH",
        )
        stability_index = envelope.axis_ids.index("stability")
        expected_lane_checks = {
            "pre_event_backward_credit_nonzero": bool(
                torch.any(torch.abs(lane_gradients[: envelope.event_index]) > 0.0)
            ),
            "control_budget_respected": float(torch.linalg.vector_norm(lane_controls))
            <= envelope.control_budget + FLOAT_TOLERANCE,
            "ineligible_sites_are_zero": bool(
                torch.all(lane_controls[~envelope.eligible_mask] == 0.0)
            ),
            "stable_axis_exact_identity": torch.equal(
                neutral[:, stability_index],
                revised[:, stability_index],
            ),
        }
        _require(
            lane_material[envelope.lane_id][0].get("checks") == expected_lane_checks
            and all(expected_lane_checks.values()),
            "JOINT_CORE_RECEIPT_LANE_CHECKS_INVALID",
        )

    global_l2 = _finite(
        float(torch.linalg.vector_norm(controls)),
        "JOINT_CORE_RECEIPT_EXPECTED_GLOBAL_L2",
    )
    _require(
        math.isclose(
            _finite(
                snapshot.get("global_control_budget"),
                "JOINT_CORE_RECEIPT_GLOBAL_BUDGET",
            ),
            global_budget,
            rel_tol=1.0e-12,
            abs_tol=FLOAT_TOLERANCE,
        ),
        "JOINT_CORE_RECEIPT_GLOBAL_BUDGET_MISMATCH",
    )
    _require(
        math.isclose(
            _finite(
                snapshot.get("global_control_l2"),
                "JOINT_CORE_RECEIPT_GLOBAL_L2",
            ),
            global_l2,
            rel_tol=1.0e-12,
            abs_tol=FLOAT_TOLERANCE,
        ),
        "JOINT_CORE_RECEIPT_GLOBAL_L2_MISMATCH",
    )
    expected_checks = {
        "one_joint_backward_executed": True,
        "block_finite_difference_agreement": max_fd_error <= FD_TOLERANCE,
        "joint_objective_decreased": float(expected_revised_loss["total"])
        < float(expected_neutral_loss["total"]),
        "global_control_is_non_neutral": bool(torch.any(torch.abs(controls) > 0.0)),
        "global_budget_respected": global_l2 <= global_budget + FLOAT_TOLERANCE,
        "lane_namespace_unique": len(lane_ids) == len(set(lane_ids)),
        "shared_axis_contract_exact": all(
            envelope.axis_ids == ordered[0].axis_ids for envelope in ordered
        ),
    }
    _require(
        snapshot.get("checks") == expected_checks and all(expected_checks.values()),
        "JOINT_CORE_RECEIPT_CHECKS_INVALID",
    )
    return snapshot


def _merge_model_results(
    task: RevisionTask,
    lane_results: Mapping[str, ModelResult],
    lane_weights: Mapping[str, float],
) -> JsonObject:
    _require(bool(lane_results), "MERGE_LANE_RESULTS_EMPTY")
    _require(
        set(lane_results) == set(lane_weights),
        "MERGE_LANE_WEIGHT_KEYS_MISMATCH",
    )
    vote_weight: Counter[str] = Counter()
    for lane_id, result in lane_results.items():
        weight = _finite(lane_weights[lane_id], "MERGE_LANE_WEIGHT")
        _require(weight > 0.0, "MERGE_LANE_WEIGHT_INVALID")
        vote_weight[result.answer] += weight
    best_weight = max(vote_weight.values())
    tied = {
        answer
        for answer, weight in vote_weight.items()
        if math.isclose(
            weight,
            best_weight,
            rel_tol=1.0e-12,
            abs_tol=FLOAT_TOLERANCE,
        )
    }
    if len(tied) == 1:
        answer = next(iter(tied))
        tie_break = "NONE"
    else:
        canonical_lane = min(
            lane_id for lane_id, result in lane_results.items() if result.answer in tied
        )
        answer = lane_results[canonical_lane].answer
        tie_break = f"CANONICAL_LANE:{canonical_lane}"
    support_union = {
        evidence_id
        for result in lane_results.values()
        if result.answer == answer
        for evidence_id in result.support_ids
    }
    support_union -= set(task.event.invalidated_evidence_ids)
    ordinal = {row.evidence_id: row.ordinal for row in task.evidence}
    support = sorted(support_union, key=lambda row: ordinal[row])
    return _seal(
        {
            "schema_version": "ebrt-joint-merge-v0.8.0",
            "answer": answer,
            "support_ids": support,
            "vote_weight": dict(sorted(vote_weight.items())),
            "tie_break": tie_break,
            "lane_answers": {
                lane_id: result.answer
                for lane_id, result in sorted(lane_results.items())
            },
            "operator": "weighted_answer_consensus_winner_lane_support_union_minus_invalidated",
        }
    )


class JointRevisionEngine:
    """v0.8 trajectory composition followed by adapter-local actuation."""

    def __init__(
        self,
        *,
        core: JointBackwardRevisionCore | None = None,
        actuator_adapter: ActuatorAdapter | None = None,
    ) -> None:
        self.core = core or JointBackwardRevisionCore()
        self.actuator_adapter = actuator_adapter or PublicRevisionActuator()

    def run(
        self,
        task: RevisionTask,
        lanes: Sequence[JointLaneSpec],
        *,
        post_run_contract: PostRunContract | None = None,
    ) -> JsonObject:
        validate_task(task)
        if post_run_contract is not None:
            validate_contract(task, post_run_contract)
        _require(len(lanes) >= 2, "JOINT_ENGINE_LANE_COUNT_TOO_SMALL")
        ordered_lanes = tuple(sorted(lanes, key=lambda row: row.lane_id))
        lane_ids = [row.lane_id for row in ordered_lanes]
        _require(len(lane_ids) == len(set(lane_ids)), "JOINT_ENGINE_LANE_DUPLICATE")
        envelopes: list[TrajectoryEnvelope] = []
        for lane in ordered_lanes:
            envelope = _prepare_state_envelope(
                task,
                lane.state_adapter,
                lane.state_adapter.build(task, lane_id=lane.lane_id),
                lane_id=lane.lane_id,
                label="JOINT_STATE_ADAPTER",
            )
            envelopes.append(envelope)
        core_envelopes = [_clone_envelope(envelope) for envelope in envelopes]
        joint = _validate_joint_core_receipt(
            envelopes,
            [row.weight for row in ordered_lanes],
            self.core.optimize(
                core_envelopes,
                weights=[row.weight for row in ordered_lanes],
            ),
        )
        _require(
            _is_trusted_builtin_core(self.core, JointBackwardRevisionCore),
            "JOINT_CORE_EXECUTION_UNVERIFIED",
        )
        programs: dict[str, ActuatorProgram] = {}
        results: dict[str, ModelResult] = {}
        structural: JsonObject = {}
        for lane in ordered_lanes:
            optimized = joint["lanes"][lane.lane_id]
            program = self.actuator_adapter.compile(
                task,
                _clone(optimized),
                lane_id=lane.lane_id,
            )
            _validate_compiled_program(
                task,
                optimized,
                program,
                lane_id=lane.lane_id,
            )
            expected_descriptor = lane.model_adapter.descriptor
            _require(
                isinstance(expected_descriptor, AdapterDescriptor),
                "JOINT_MODEL_ADAPTER_DESCRIPTOR_INVALID",
            )
            _validate_adapter_descriptor(expected_descriptor, "JOINT_MODEL_ADAPTER")
            expected_invocation = build_model_invocation(
                task, program, prompt_policy=lane.prompt_policy
            )
            result = lane.model_adapter.generate(
                task, program, prompt_policy=lane.prompt_policy
            )
            _require(isinstance(result, ModelResult), "JOINT_MODEL_RESULT_TYPE_INVALID")
            checks = _structural_model_checks(
                task,
                program,
                result,
                expected_descriptor=expected_descriptor,
                expected_request_fingerprint_sha256=str(
                    expected_invocation["fingerprint_sha256"]
                ),
            )
            _require(all(checks.values()), "JOINT_MODEL_RESULT_STRUCTURAL_FAILURE")
            programs[lane.lane_id] = program
            results[lane.lane_id] = result
            structural[lane.lane_id] = {"status": "PASS", "checks": checks}

        merged = _merge_model_results(
            task,
            results,
            {row.lane_id: row.weight for row in ordered_lanes},
        )
        merged_program = {
            "preserve_evidence_ids": sorted(
                {
                    evidence_id
                    for program in programs.values()
                    for evidence_id in program.preserve
                }
            )
        }
        contract_grade = (
            _grade_contract(merged, merged_program, post_run_contract)
            if post_run_contract is not None
            else {"status": "NOT_ASSESSED", "contract": None, "checks": {}}
        )
        model_ids = {result.descriptor.model_id for result in results.values()}
        adapter_ids = {result.descriptor.adapter_id for result in results.values()}
        heterogeneous_status = (
            "CONFORMANCE_ONLY" if len(model_ids) > 1 else "NOT_ASSESSED"
        )
        return _seal(
            {
                "schema_version": RESULT_SCHEMA_VERSION,
                "mode": "joint_trajectory_v0.8",
                "status": "PASS",
                "core_protocol": CORE_PROTOCOL_VERSION,
                "joint_protocol": JOINT_PROTOCOL_VERSION,
                "task_fingerprint_sha256": _fingerprint(task.to_public_dict()),
                "joint_trajectory": joint,
                "actuators": {
                    lane_id: program.to_dict()
                    for lane_id, program in sorted(programs.items())
                },
                "model_results": {
                    lane_id: result.to_dict()
                    for lane_id, result in sorted(results.items())
                },
                "structural_verification": structural,
                "merge": merged,
                "post_run_contract": contract_grade,
                "model_interface_count": len(adapter_ids),
                "distinct_model_id_count": len(model_ids),
                "heterogeneous_model_execution_status": heterogeneous_status,
                "semantic_correctness_status": (
                    contract_grade["status"]
                    if post_run_contract is not None
                    else "NOT_ASSESSED"
                ),
                "effect_attribution_status": "NOT_ASSESSED",
                "claim_boundary": list(CLAIM_BOUNDARY),
            }
        )


def build_demo_task() -> RevisionTask:
    """Known synthetic revision task; intentionally not a fresh benchmark."""

    task = RevisionTask(
        task_id="release-priority-revision",
        question="What is the current final priority: POLISH or PROVE?",
        answer_choices=("POLISH", "PROVE"),
        evidence=(
            Evidence(
                "R1",
                1,
                "The initial recommendation is POLISH.",
                "context",
                (-0.4, 0.0, 0.0),
                (0.2, 0.0, 0.0),
            ),
            Evidence(
                "R2",
                2,
                "Judges evaluate technical implementation, idea, design, and impact.",
                "required_support",
                (0.1, 0.0, 0.0),
                (0.9, 0.0, 0.0),
            ),
            Evidence(
                "R3",
                3,
                "Legacy guidance says design dominates judging, so prioritize POLISH.",
                "invalidated_prior",
                (-0.8, 0.0, 0.0),
                (1.0, 0.6, 0.0),
            ),
            Evidence(
                "R4",
                4,
                "A working end-to-end proof is required.",
                "required_support",
                (0.2, 0.0, 0.0),
                (1.0, 0.0, 0.0),
            ),
            Evidence(
                "R5",
                5,
                "The video remains THREE_MINUTE_NARRATED.",
                "stable",
                (0.0, 0.0, 1.0),
                (0.0, 0.0, 0.0),
            ),
            Evidence(
                "R6",
                6,
                "Late correction: R3 is superseded; technical implementation, idea, design, and impact are equally weighted.",
                "correction",
                (0.6, 1.0, 0.0),
                (1.0, 0.5, 0.0),
            ),
        ),
        before_horizon_evidence_ids=("R1", "R2", "R3", "R4", "R5"),
        prior_state=PriorPublicState(
            answer="POLISH",
            active_support_ids=("R2", "R3", "R5"),
            stable_values=(("video_format", "THREE_MINUTE_NARRATED"),),
        ),
        event=RevisionEvent(
            event_id="late-judging-correction",
            correction_evidence_id="R6",
            invalidated_evidence_ids=("R3",),
            stable_evidence_ids=("R5",),
        ),
        terminal_target=(1.3, 1.0, 0.85),
        decay=0.85,
        control_budget=0.75,
        learning_rate=0.8,
        reinspection_count=3,
    )
    validate_task(task)
    return task


def build_demo_contract() -> PostRunContract:
    return PostRunContract(
        expected_answer="PROVE",
        required_support_ids=("R2", "R4", "R6"),
        forbidden_support_ids=("R3",),
        required_compiled_preserve_ids=("R5",),
    )


def _conformance_adapter(
    *,
    adapter_id: str,
    model_id: str,
    interface_kind: Literal[
        "deterministic_conformance", "local_open_weight", "hosted_api"
    ] = "deterministic_conformance",
) -> CallableModelAdapter:
    return CallableModelAdapter(
        descriptor=AdapterDescriptor(
            adapter_id=adapter_id,
            model_id=model_id,
            interface_kind=interface_kind,
            state_visibility="public_only",
            differentiable_through_model=False,
        ),
        callback=lambda _request: "ANSWER=PROVE\nSUPPORT=R6,R4,R2",
    )


@dataclass(frozen=True)
class _DescriptorOnlyMLXRuntime:
    model_id: str
    max_tokens: int
    seed: int


@dataclass(frozen=True)
class _MisboundStateAdapter:
    returned_lane_id: str
    adapter_id: str = "misbound-state-adapter-test"

    def build(self, task: RevisionTask, *, lane_id: str) -> TrajectoryEnvelope:
        del lane_id
        return TypedPublicStateAdapter().build(
            task,
            lane_id=self.returned_lane_id,
        )


class _GraphBackedStateAdapter:
    adapter_id = "graph-backed-state-adapter-test"

    def __init__(self) -> None:
        self.source = torch.tensor(0.25, dtype=DTYPE, requires_grad=True)

    def build(self, task: RevisionTask, *, lane_id: str) -> TrajectoryEnvelope:
        envelope = TypedPublicStateAdapter(adapter_id=self.adapter_id).build(
            task,
            lane_id=lane_id,
        )
        bridge = self.source - self.source.detach()
        return replace(
            envelope,
            neutral_effects=envelope.neutral_effects + bridge,
            control_basis=envelope.control_basis + bridge,
            target=envelope.target + bridge,
        )


@dataclass(frozen=True)
class _EligibilityTransformingStateAdapter:
    zero_evidence_id: str
    adapter_id: str = "eligibility-transforming-state-adapter-test"

    def build(self, task: RevisionTask, *, lane_id: str) -> TrajectoryEnvelope:
        envelope = TypedPublicStateAdapter(adapter_id=self.adapter_id).build(
            task,
            lane_id=lane_id,
        )
        index = envelope.evidence_ids.index(self.zero_evidence_id)
        basis = envelope.control_basis.clone()
        basis[index] = 0.0
        return replace(
            envelope,
            control_basis=basis,
            eligible_mask=torch.linalg.vector_norm(basis, dim=1) > 0.0,
        )


@dataclass(frozen=True)
class _TaskParameterTamperingStateAdapter:
    field_name: str
    adapter_id: str = "task-parameter-tampering-state-adapter-test"

    def build(self, task: RevisionTask, *, lane_id: str) -> TrajectoryEnvelope:
        envelope = TypedPublicStateAdapter(adapter_id=self.adapter_id).build(
            task,
            lane_id=lane_id,
        )
        if self.field_name == "decay":
            return replace(envelope, decay=envelope.decay + 0.01)
        if self.field_name == "control_budget":
            return replace(envelope, control_budget=envelope.control_budget + 0.01)
        if self.field_name == "learning_rate":
            return replace(envelope, learning_rate=envelope.learning_rate + 0.01)
        if self.field_name == "target":
            target = envelope.target.clone()
            target[0] += 0.01
            return replace(envelope, target=target)
        if self.field_name == "event_index":
            return replace(envelope, event_index=envelope.event_index + 1)
        raise AssertionError("unknown test field")


@dataclass(frozen=True)
class _TamperedActuatorAdapter:
    adapter_id: str = "tampered-actuator-test"

    def compile(
        self,
        task: RevisionTask,
        optimized: Mapping[str, Any],
        *,
        lane_id: str,
    ) -> ActuatorProgram:
        valid = PublicRevisionActuator().compile(
            task,
            optimized,
            lane_id=lane_id,
        )
        return replace(valid, steps=(*valid.steps[:-1], "SKIP_REGENERATION"))


@dataclass(frozen=True)
class _MutatingActuatorAdapter:
    adapter_id: str = "mutating-actuator-test"

    def compile(
        self,
        task: RevisionTask,
        optimized: Mapping[str, Any],
        *,
        lane_id: str,
    ) -> ActuatorProgram:
        _require(isinstance(optimized, dict), "TEST_MUTATION_INPUT_NOT_DICT")
        material = _without_fingerprint(optimized)
        for row in material["credit_map"]:
            if row["eligible"]:
                row["gradient"] = float(row["gradient"]) + 0.25
                break
        tampered = _seal(material)
        optimized.clear()
        optimized.update(tampered)
        return PublicRevisionActuator().compile(
            task,
            optimized,
            lane_id=lane_id,
        )


class _TamperedSingleCore:
    def optimize(self, envelope: TrajectoryEnvelope) -> JsonObject:
        material = _without_fingerprint(BackwardRevisionCore().optimize(envelope))
        material["state_adapter_id"] = "tampered-state-adapter"
        return _seal(material)


class _MutatingSingleCore:
    def optimize(self, envelope: TrajectoryEnvelope) -> JsonObject:
        envelope.neutral_effects[0, 0] += 100.0
        return BackwardRevisionCore().optimize(envelope)


class _AlternateDescendingControlCore:
    def optimize(self, envelope: TrajectoryEnvelope) -> JsonObject:
        material = _without_fingerprint(BackwardRevisionCore().optimize(envelope))
        controls = (
            torch.tensor(
                [row["control"] for row in material["credit_map"]],
                dtype=DTYPE,
            )
            * 0.5
        )
        for index, row in enumerate(material["credit_map"]):
            row["control"] = _finite(
                float(controls[index]),
                "TEST_ALTERNATE_CONTROL",
            )
            row["absolute_control"] = abs(row["control"])
        revised = _forward(envelope, controls)
        _, revised_loss = _loss(envelope, controls, revised)
        material["revised"] = {
            "loss": revised_loss,
            "trajectory": _trajectory_rows(envelope, revised),
        }
        material["control_l2"] = _finite(
            float(torch.linalg.vector_norm(controls)),
            "TEST_ALTERNATE_CONTROL_L2",
        )
        material["backtracking_steps"] = 1
        material["checks"]["objective_decreased"] = (
            revised_loss["total"] < material["neutral"]["loss"]["total"]
        )
        material["checks"]["control_is_non_neutral"] = bool(
            torch.any(torch.abs(controls) > 0.0)
        )
        material["checks"]["control_budget_respected"] = (
            float(torch.linalg.vector_norm(controls))
            <= envelope.control_budget + FLOAT_TOLERANCE
        )
        return _seal(material)


@dataclass(frozen=True)
class _ReplayingSingleCore:
    receipt: Mapping[str, Any]

    def optimize(self, _envelope: TrajectoryEnvelope) -> JsonObject:
        return _clone(self.receipt)


class _TamperedJointCore:
    def optimize(
        self,
        envelopes: Sequence[TrajectoryEnvelope],
        *,
        weights: Sequence[float],
    ) -> JsonObject:
        material = _without_fingerprint(
            JointBackwardRevisionCore().optimize(envelopes, weights=weights)
        )
        material["checks"]["joint_objective_decreased"] = False
        return _seal(material)


class _MutatingJointCore:
    def optimize(
        self,
        envelopes: Sequence[TrajectoryEnvelope],
        *,
        weights: Sequence[float],
    ) -> JsonObject:
        envelopes[0].neutral_effects[0, 0] += 0.01
        return JointBackwardRevisionCore().optimize(envelopes, weights=weights)


@dataclass(frozen=True)
class _ReplayingJointCore:
    receipt: Mapping[str, Any]

    def optimize(
        self,
        _envelopes: Sequence[TrajectoryEnvelope],
        *,
        weights: Sequence[float],
    ) -> JsonObject:
        _require(bool(weights), "TEST_REPLAY_WEIGHTS_MISSING")
        return _clone(self.receipt)


class _MisreportingContract(PostRunContract):
    def to_dict(self) -> JsonObject:
        return _seal(
            {
                "schema_version": POST_RUN_CONTRACT_VERSION,
                "expected_answer": "POLISH",
                "required_support_ids": [],
                "forbidden_support_ids": [],
                "required_compiled_preserve_ids": [],
            }
        )


@contextmanager
def _network_denied() -> Any:
    calls = {"count": 0}

    def denied(*_args: Any, **_kwargs: Any) -> Any:
        calls["count"] += 1
        raise AssertionError("network access forbidden during self-test")

    with (
        mock.patch.object(socket, "create_connection", side_effect=denied),
        mock.patch.object(socket.socket, "connect", side_effect=denied),
    ):
        yield calls


def _raises_ebrt_reason(callback: Callable[[], Any], reason: str) -> bool:
    try:
        callback()
    except EBRTError as error:
        return str(error) == reason
    except Exception:
        return False
    return False


def self_test() -> JsonObject:
    task = build_demo_task()
    contract = build_demo_contract()
    changed_target_task = replace(
        task,
        terminal_target=(task.terminal_target[0] + 0.01, *task.terminal_target[1:]),
    )
    target_changes_task_fingerprint = _fingerprint(
        task.to_public_dict()
    ) != _fingerprint(changed_target_task.to_public_dict())
    multiword_task = replace(task, answer_choices=("POLISH", "NOT ENOUGH INFORMATION"))
    multiword_answer, multiword_support = _parse_model_text(
        "ANSWER=NOT ENOUGH INFORMATION\nSUPPORT=R6",
        task=multiword_task,
    )
    delimited_task = replace(task, answer_choices=("POLISH", "<UNKNOWN>"))
    delimited_answer, delimited_support = _parse_model_text(
        "ANSWER=<UNKNOWN>\nSUPPORT=<R6>",
        task=delimited_task,
    )
    parser_rejects_extra_lines = _raises_ebrt_reason(
        lambda: _parse_model_text(
            "ANSWER=PROVE\nSUPPORT=R6,R4,R2\nANSWER=POLISH",
            task=task,
        ),
        "MODEL_RESPONSE_LINE_COUNT_INVALID",
    )
    parser_rejects_leading_blank_line = _raises_ebrt_reason(
        lambda: _parse_model_text(
            "\nANSWER=PROVE\nSUPPORT=R6,R4,R2",
            task=task,
        ),
        "MODEL_RESPONSE_LINE_COUNT_INVALID",
    )
    parser_rejects_multiple_terminal_newlines = _raises_ebrt_reason(
        lambda: _parse_model_text(
            "ANSWER=PROVE\nSUPPORT=R6,R4,R2\n\n",
            task=task,
        ),
        "MODEL_RESPONSE_LINE_COUNT_INVALID",
    )
    unpreservable_answer_choice_rejected = _raises_ebrt_reason(
        lambda: validate_task(replace(task, answer_choices=("POLISH", " PROVE "))),
        "ANSWER_CHOICES_INVALID",
    )
    duplicate_event_task = replace(
        task,
        event=replace(
            task.event,
            invalidated_evidence_ids=("R3", "R3"),
        ),
    )
    duplicate_event_rejected = _raises_ebrt_reason(
        lambda: validate_task(duplicate_event_task),
        "INVALIDATED_EVIDENCE_DUPLICATE",
    )
    invalid_role_task = replace(
        task,
        evidence=tuple(
            replace(row, role="not_a_role") if row.evidence_id == "R1" else row
            for row in task.evidence
        ),
    )
    invalid_role_rejected = _raises_ebrt_reason(
        lambda: validate_task(invalid_role_task),
        "EVIDENCE_ROLE_INVALID",
    )
    near_zero_stability_task = replace(
        task,
        evidence=tuple(
            replace(
                row,
                control_basis=(
                    row.control_basis[0],
                    row.control_basis[1],
                    1.0e-13,
                ),
            )
            if row.evidence_id == "R1"
            else row
            for row in task.evidence
        ),
    )
    near_zero_stability_rejected = _raises_ebrt_reason(
        lambda: validate_task(near_zero_stability_task),
        "STABILITY_AXIS_MUST_BE_EXACT_ZERO",
    )
    reserved_evidence_id_task = replace(
        task,
        evidence=(replace(task.evidence[0], evidence_id="NONE"), *task.evidence[1:]),
    )
    reserved_evidence_id_rejected = _raises_ebrt_reason(
        lambda: validate_task(reserved_evidence_id_task),
        "EVIDENCE_ID_RESERVED",
    )
    invalid_scale_rejected = _raises_ebrt_reason(
        lambda: TypedPublicStateAdapter(support_scale=0.0).build(
            task, lane_id="scale-check"
        ),
        "STATE_SCALE_INVALID",
    )
    zero_correction_task = replace(
        task,
        evidence=tuple(
            replace(row, control_basis=(0.0, 0.0, 0.0))
            if row.evidence_id == task.event.correction_evidence_id
            else row
            for row in task.evidence
        ),
    )
    typed_zero_correction_rejected = _raises_ebrt_reason(
        lambda: TypedPublicStateAdapter().build(
            zero_correction_task,
            lane_id="zero-correction-check",
        ),
        "CORRECTION_CONTROL_INELIGIBLE",
    )
    invalid_descriptor_rejected = _raises_ebrt_reason(
        lambda: _validate_adapter_descriptor(
            AdapterDescriptor(
                adapter_id="invalid adapter",
                model_id="model",
                interface_kind="local_open_weight",
                state_visibility="public_only",
            ),
            "MODEL_ADAPTER",
        ),
        "MODEL_ADAPTER_ADAPTER_ID_INVALID",
    )
    cached_snapshot_a = _local_model_id(
        Path("/tmp/hub/models--example--model/snapshots/revision-a")
    )
    cached_snapshot_b = _local_model_id(
        Path("/tmp/hub/models--example--model/snapshots/revision-b")
    )
    cached_path_a = Path("/tmp/hub/models--example--model/snapshots/" + "a" * 40)
    cached_path_b = Path("/tmp/hub/models--example--model/snapshots/" + "b" * 40)
    active_cache_selection = _select_cached_snapshot(
        (cached_path_b, cached_path_a),
        active_revision="a" * 40,
    )
    ambiguous_cache_selection_rejected = _raises_ebrt_reason(
        lambda: _select_cached_snapshot(
            (cached_path_a, cached_path_b),
            active_revision=None,
        ),
        "LOCAL_MODEL_SNAPSHOT_AMBIGUOUS",
    )
    indexed_weight_manifest_complete = _indexed_weight_files_are_complete(
        (
            {
                "weight_map": {
                    "layer.0": "model-00001-of-00002.safetensors",
                    "layer.1": "model-00002-of-00002.safetensors",
                }
            },
        ),
        frozenset(
            {
                "model-00001-of-00002.safetensors",
                "model-00002-of-00002.safetensors",
            }
        ),
    )
    indexed_weight_manifest_rejects_missing_shard = (
        not _indexed_weight_files_are_complete(
            (
                {
                    "weight_map": {
                        "layer.0": "model-00001-of-00002.safetensors",
                        "layer.1": "model-00002-of-00002.safetensors",
                    }
                },
            ),
            frozenset({"model-00001-of-00002.safetensors"}),
        )
    )
    noncache_identity_requires_revision = _raises_ebrt_reason(
        lambda: _local_model_id(Path("/tmp/replaceable-local-model")),
        "LOCAL_MODEL_ID_REVISION_REQUIRED",
    ) and _raises_ebrt_reason(
        lambda: _local_model_id(
            Path("/tmp/replaceable-local-model"),
            explicit="example/model",
        ),
        "LOCAL_MODEL_ID_REVISION_REQUIRED",
    )
    explicit_revision_identity = _local_model_id(
        Path("/tmp/replaceable-local-model"),
        explicit="example/model@weights-sha256-deadbeef",
    )
    mlx_config_a = MLXLocalAdapter(
        runtime=_DescriptorOnlyMLXRuntime(
            model_id="example/model@revision",
            max_tokens=32,
            seed=0,
        ),
        adapter_id="mlx-config-binding-test",
    ).descriptor
    mlx_config_b = MLXLocalAdapter(
        runtime=_DescriptorOnlyMLXRuntime(
            model_id="example/model@revision",
            max_tokens=64,
            seed=1,
        ),
        adapter_id="mlx-config-binding-test",
    ).descriptor
    _validate_adapter_descriptor(mlx_config_a, "MLX_CONFIG_TEST_A")
    _validate_adapter_descriptor(mlx_config_b, "MLX_CONFIG_TEST_B")
    adapter = _conformance_adapter(
        adapter_id="local-conformance-a", model_id="transparent-local-double-a"
    )
    engine = RevisionEngine()
    with _network_denied() as network:
        single = engine.run(
            task,
            adapter,
            post_run_contract=contract,
        )
        replayed_single_core_rejected = _raises_ebrt_reason(
            lambda: RevisionEngine(core=_ReplayingSingleCore(single["trajectory"])).run(
                task,
                adapter,
                post_run_contract=contract,
            ),
            "CORE_EXECUTION_UNVERIFIED",
        )
        tampered_single_core_rejected = _raises_ebrt_reason(
            lambda: RevisionEngine(core=_TamperedSingleCore()).run(
                task,
                adapter,
                post_run_contract=contract,
            ),
            "CORE_RECEIPT_STATE_ADAPTER_MISMATCH",
        )
        mutating_single_core_rejected = _raises_ebrt_reason(
            lambda: RevisionEngine(core=_MutatingSingleCore()).run(
                task,
                adapter,
                post_run_contract=contract,
            ),
            "CORE_RECEIPT_NEUTRAL_REPLAY_MISMATCH",
        )
        alternate_control_law_rejected = _raises_ebrt_reason(
            lambda: RevisionEngine(core=_AlternateDescendingControlCore()).run(
                task,
                adapter,
                post_run_contract=contract,
            ),
            "CORE_RECEIPT_CONTROL_UPDATE_MISMATCH",
        )
        misreporting_contract_rejected = _raises_ebrt_reason(
            lambda: engine.run(
                task,
                adapter,
                post_run_contract=_MisreportingContract(
                    contract.expected_answer,
                    contract.required_support_ids,
                    contract.forbidden_support_ids,
                    contract.required_compiled_preserve_ids,
                ),
            ),
            "CONTRACT_TYPE_INVALID",
        )
        tampered_actuator_rejected = _raises_ebrt_reason(
            lambda: RevisionEngine(actuator_adapter=_TamperedActuatorAdapter()).run(
                task,
                adapter,
                post_run_contract=contract,
            ),
            "ACTUATOR_PROGRAM_BINDING_MISMATCH",
        )
        mutating_actuator_rejected_single = _raises_ebrt_reason(
            lambda: RevisionEngine(actuator_adapter=_MutatingActuatorAdapter()).run(
                task,
                adapter,
                post_run_contract=contract,
            ),
            "ACTUATOR_PROGRAM_BINDING_MISMATCH",
        )
        single_state_identity_rejected = _raises_ebrt_reason(
            lambda: RevisionEngine(
                state_adapter=_MisboundStateAdapter(returned_lane_id="primary")
            ).run(
                task,
                adapter,
                post_run_contract=contract,
            ),
            "STATE_ADAPTER_ID_MISMATCH",
        )
        graph_backed_state_adapter = _GraphBackedStateAdapter()
        graph_backed_state_run = RevisionEngine(
            state_adapter=graph_backed_state_adapter
        ).run(
            task,
            adapter,
            post_run_contract=contract,
        )
        eligibility_transformed_run = RevisionEngine(
            state_adapter=_EligibilityTransformingStateAdapter("R2")
        ).run(
            task,
            adapter,
            post_run_contract=contract,
        )
        transformed_zero_correction_rejected = _raises_ebrt_reason(
            lambda: RevisionEngine(
                state_adapter=_EligibilityTransformingStateAdapter("R6")
            ).run(
                task,
                adapter,
                post_run_contract=contract,
            ),
            "STATE_ADAPTER_CORRECTION_INELIGIBLE",
        )
        task_parameter_tampering_rejected = all(
            _raises_ebrt_reason(
                lambda field_name=field_name: RevisionEngine(
                    state_adapter=_TaskParameterTamperingStateAdapter(field_name)
                ).run(
                    task,
                    adapter,
                    post_run_contract=contract,
                ),
                reason,
            )
            for field_name, reason in (
                ("decay", "STATE_ADAPTER_DECAY_MISMATCH"),
                ("control_budget", "STATE_ADAPTER_CONTROL_BUDGET_MISMATCH"),
                ("learning_rate", "STATE_ADAPTER_LEARNING_RATE_MISMATCH"),
                ("target", "STATE_ADAPTER_TARGET_MISMATCH"),
                ("event_index", "STATE_ADAPTER_EVENT_INDEX_MISMATCH"),
            )
        )
        optimized = BackwardRevisionCore().optimize(
            TypedPublicStateAdapter().build(task, lane_id="contract-check")
        )
        program = PublicRevisionActuator().compile(
            task,
            optimized,
            lane_id="contract-check",
        )
        incomplete_credit = _without_fingerprint(optimized)
        incomplete_credit["credit_map"] = incomplete_credit["credit_map"][:-1]
        incomplete_credit_rejected = _raises_ebrt_reason(
            lambda: PublicRevisionActuator().compile(
                task,
                _seal(incomplete_credit),
                lane_id="contract-check",
            ),
            "CREDIT_MAP_COVERAGE_MISMATCH",
        )
        unrealized_credit = _without_fingerprint(optimized)
        for row in unrealized_credit["credit_map"]:
            if row["evidence_id"] != "R3":
                row["control"] = 0.0
                row["absolute_control"] = 0.0
        unrealized_reinspection_rejected = _raises_ebrt_reason(
            lambda: PublicRevisionActuator().compile(
                task,
                _seal(unrealized_credit),
                lane_id="contract-check",
            ),
            "NO_REALIZED_REINSPECTION_CONTROL",
        )
        invocation_before = build_model_invocation(
            task, program, prompt_policy="credit_first"
        )
        first_reinspect = program.reinspect[0]
        _require(first_reinspect[2] != 0.0, "SELF_TEST_CONTROL_UNEXPECTEDLY_ZERO")
        quantitative_variant = replace(
            program,
            reinspect=(
                (first_reinspect[0], first_reinspect[1], -first_reinspect[2]),
                *program.reinspect[1:],
            ),
        )
        quantitative_invocation = build_model_invocation(
            task,
            quantitative_variant,
            prompt_policy="credit_first",
        )
        validate_contract(task, contract)
        invocation_after = build_model_invocation(
            task, program, prompt_policy="credit_first"
        )
        valid_result = adapter.generate(task, program, prompt_policy="credit_first")
        alternate_contract = replace(contract, required_support_ids=("R6",))
        validate_contract(task, alternate_contract)
        primary_contract_grade = _grade_contract(valid_result, program, contract)
        alternate_contract_grade = _grade_contract(
            valid_result,
            program,
            alternate_contract,
        )
        request_tamper_checks = _structural_model_checks(
            task,
            program,
            replace(valid_result, request_fingerprint_sha256="0" * 64),
            expected_descriptor=adapter.descriptor,
            expected_request_fingerprint_sha256=str(
                invocation_before["fingerprint_sha256"]
            ),
        )
        descriptor_tamper_checks = _structural_model_checks(
            task,
            program,
            replace(
                valid_result,
                descriptor=replace(
                    valid_result.descriptor,
                    adapter_id="tampered-adapter",
                ),
            ),
            expected_descriptor=adapter.descriptor,
            expected_request_fingerprint_sha256=str(
                invocation_before["fingerprint_sha256"]
            ),
        )
        raw_text_tamper_checks = _structural_model_checks(
            task,
            program,
            replace(
                valid_result,
                raw_text="ANSWER=POLISH\nSUPPORT=R6,R4,R2",
            ),
            expected_descriptor=adapter.descriptor,
            expected_request_fingerprint_sha256=str(
                invocation_before["fingerprint_sha256"]
            ),
        )
        tie_merge = _merge_model_results(
            task,
            {
                "lane-a": replace(valid_result, answer="PROVE"),
                "lane-b": replace(valid_result, answer="PROVE"),
                "lane-c": replace(valid_result, answer="POLISH"),
            },
            {"lane-a": 0.1, "lane-b": 0.2, "lane-c": 0.3},
        )

        lane_a = JointLaneSpec(
            lane_id="invalidation",
            state_adapter=TypedPublicStateAdapter(
                adapter_id="typed-public-invalidation-v0.8",
                support_scale=0.75,
                invalidation_scale=1.25,
                correction_scale=1.1,
            ),
            model_adapter=_conformance_adapter(
                adapter_id="local-conformance-a",
                model_id="transparent-local-double-a",
            ),
            prompt_policy="chronological",
            weight=1.0,
        )
        lane_b = JointLaneSpec(
            lane_id="support",
            state_adapter=TypedPublicStateAdapter(
                adapter_id="typed-public-support-v0.8",
                support_scale=1.25,
                invalidation_scale=0.75,
                correction_scale=1.0,
            ),
            model_adapter=_conformance_adapter(
                adapter_id="hosted-api-conformance-b",
                model_id="unexecuted-hosted-shape-b",
                interface_kind="hosted_api",
            ),
            prompt_policy="credit_first",
            weight=1.0,
        )
        misbound_lane_rejected = _raises_ebrt_reason(
            lambda: JointRevisionEngine().run(
                task,
                (
                    replace(
                        lane_a,
                        state_adapter=_MisboundStateAdapter(
                            returned_lane_id=lane_b.lane_id
                        ),
                    ),
                    lane_b,
                ),
                post_run_contract=contract,
            ),
            "JOINT_STATE_ADAPTER_LANE_MISMATCH",
        )
        joint_state_identity_rejected = _raises_ebrt_reason(
            lambda: JointRevisionEngine().run(
                task,
                (
                    replace(
                        lane_a,
                        state_adapter=_MisboundStateAdapter(
                            returned_lane_id=lane_a.lane_id
                        ),
                    ),
                    lane_b,
                ),
                post_run_contract=contract,
            ),
            "JOINT_STATE_ADAPTER_ID_MISMATCH",
        )
        mutating_actuator_rejected_joint = _raises_ebrt_reason(
            lambda: JointRevisionEngine(
                actuator_adapter=_MutatingActuatorAdapter()
            ).run(
                task,
                (lane_a, lane_b),
                post_run_contract=contract,
            ),
            "ACTUATOR_PROGRAM_BINDING_MISMATCH",
        )
        tampered_joint_core_rejected = _raises_ebrt_reason(
            lambda: JointRevisionEngine(core=_TamperedJointCore()).run(
                task,
                (lane_a, lane_b),
                post_run_contract=contract,
            ),
            "JOINT_CORE_RECEIPT_CHECKS_INVALID",
        )
        mutating_joint_core_rejected = _raises_ebrt_reason(
            lambda: JointRevisionEngine(core=_MutatingJointCore()).run(
                task,
                (lane_a, lane_b),
                post_run_contract=contract,
            ),
            "JOINT_CORE_LANE_RECEIPT_NEUTRAL_REPLAY_MISMATCH",
        )
        joint = JointRevisionEngine().run(
            task, (lane_b, lane_a), post_run_contract=contract
        )
        replayed_joint_core_rejected = _raises_ebrt_reason(
            lambda: JointRevisionEngine(
                core=_ReplayingJointCore(joint["joint_trajectory"])
            ).run(
                task,
                (lane_b, lane_a),
                post_run_contract=contract,
            ),
            "JOINT_CORE_EXECUTION_UNVERIFIED",
        )
        joint_reversed = JointRevisionEngine().run(
            task, (lane_a, lane_b), post_run_contract=contract
        )
        declared_local_double_joint = JointRevisionEngine().run(
            task,
            (
                replace(
                    lane_a,
                    model_adapter=_conformance_adapter(
                        adapter_id="declared-local-double-a",
                        model_id="declared/local-a",
                        interface_kind="local_open_weight",
                    ),
                ),
                replace(
                    lane_b,
                    model_adapter=_conformance_adapter(
                        adapter_id="declared-local-double-b",
                        model_id="declared/local-b",
                        interface_kind="local_open_weight",
                    ),
                ),
            ),
            post_run_contract=contract,
        )

    checks = {
        "network_zero": network["count"] == 0,
        "task_fingerprint_binds_terminal_target": target_changes_task_fingerprint,
        "parser_accepts_multiword_answer": multiword_answer == "NOT ENOUGH INFORMATION"
        and multiword_support == ("R6",),
        "parser_preserves_declared_delimiters": delimited_answer == "<UNKNOWN>"
        and delimited_support == ("R6",),
        "parser_enforces_exact_two_lines": parser_rejects_extra_lines,
        "parser_rejects_native_completion_padding": parser_rejects_leading_blank_line
        and parser_rejects_multiple_terminal_newlines,
        "unpreservable_answer_choices_are_rejected": unpreservable_answer_choice_rejected,
        "duplicate_event_ids_are_rejected": duplicate_event_rejected,
        "invalid_runtime_role_is_rejected": invalid_role_rejected,
        "stability_basis_requires_exact_zero": near_zero_stability_rejected,
        "parser_sentinel_cannot_be_evidence_id": reserved_evidence_id_rejected,
        "state_adapter_scales_are_positive": invalid_scale_rejected,
        "correction_must_be_an_admitted_control_site": typed_zero_correction_rejected
        and transformed_zero_correction_rejected,
        "adapter_descriptor_is_runtime_validated": invalid_descriptor_rejected,
        "cached_snapshot_identity_binds_revision": cached_snapshot_a
        == "example/model@revision-a"
        and cached_snapshot_b == "example/model@revision-b"
        and cached_snapshot_a != cached_snapshot_b,
        "cached_model_selection_uses_active_ref_and_rejects_ambiguity": active_cache_selection
        == cached_path_a
        and ambiguous_cache_selection_rejected,
        "cached_snapshot_requires_every_indexed_weight_shard": indexed_weight_manifest_complete
        and indexed_weight_manifest_rejects_missing_shard,
        "noncache_model_identity_requires_explicit_revision": noncache_identity_requires_revision
        and explicit_revision_identity == "example/model@weights-sha256-deadbeef",
        "mlx_decoding_configuration_is_receipt_bound": mlx_config_a != mlx_config_b
        and mlx_config_a.adapter_id == mlx_config_b.adapter_id
        and mlx_config_a.model_id == mlx_config_b.model_id
        and mlx_config_a.to_dict()["generation_config_fingerprint_sha256"]
        != mlx_config_b.to_dict()["generation_config_fingerprint_sha256"]
        and mlx_config_a.to_dict()["generation_config"]
        == {
            "add_generation_prompt": True,
            "max_tokens": 32,
            "sampler_temperature": 0.0,
            "seed": 0,
        },
        "credit_map_requires_exact_coverage": incomplete_credit_rejected,
        "model_visible_allocation_requires_realized_credit": unrealized_reinspection_rejected,
        "compiled_actuator_is_bound_to_backward_receipt": tampered_actuator_rejected,
        "actuator_cannot_mutate_sealed_core_receipt": mutating_actuator_rejected_single
        and mutating_actuator_rejected_joint,
        "core_receipts_are_validated_before_actuation": tampered_single_core_rejected
        and tampered_joint_core_rejected
        and mutating_single_core_rejected
        and mutating_joint_core_rejected,
        "replayed_injected_core_cannot_claim_current_backward_execution": replayed_single_core_rejected
        and replayed_joint_core_rejected,
        "core_receipts_bind_the_declared_update_law": alternate_control_law_rejected,
        "credit_first_order_is_compiled": invocation_before["evidence_ids"][
            : len(program.reinspect)
        ]
        == [row[0] for row in program.reinspect],
        "largest_remainder_allocation_is_deterministic": _largest_remainder_units(
            [1.0, 1.0, 1.0]
        )
        == [34, 33, 33],
        "floating_vote_tie_uses_canonical_tied_lane": tie_merge["answer"] == "PROVE"
        and tie_merge["tie_break"] == "CANONICAL_LANE:lane-a",
        "request_fingerprint_tamper_is_detected": not request_tamper_checks[
            "request_fingerprint_matches_invocation"
        ],
        "adapter_descriptor_tamper_is_detected": not descriptor_tamper_checks[
            "adapter_descriptor_matches_binding"
        ],
        "raw_text_field_tamper_is_detected": raw_text_tamper_checks[
            "raw_text_conforms_to_schema"
        ]
        and not raw_text_tamper_checks["raw_text_matches_returned_fields"],
        "joint_state_lane_binding_is_exact": misbound_lane_rejected,
        "state_adapter_identity_is_bound_single_and_joint": single_state_identity_rejected
        and joint_state_identity_rejected,
        "state_adapter_autograd_history_stops_at_boundary": graph_backed_state_run[
            "status"
        ]
        == "PASS"
        and graph_backed_state_adapter.source.grad is None,
        "state_adapter_eligibility_is_authoritative": next(
            row
            for row in eligibility_transformed_run["trajectory"]["credit_map"]
            if row["evidence_id"] == "R2"
        )["eligible"]
        is False
        and "R2"
        not in {
            row["evidence_id"]
            for row in eligibility_transformed_run["actuator"]["reinspect"]
        },
        "typed_state_adapter_scales_are_receipt_bound": single["trajectory"][
            "state_adapter_config"
        ]
        == {
            "correction_scale": 1.0,
            "invalidation_scale": 1.0,
            "support_scale": 1.0,
        }
        and joint["joint_trajectory"]["lanes"]["support"]["state_adapter_config"]
        == {
            "correction_scale": 1.0,
            "invalidation_scale": 0.75,
            "support_scale": 1.25,
        },
        "task_owned_trajectory_parameters_are_bound": task_parameter_tampering_rejected,
        "single_lane_v0_7_1_pass": single["status"] == "PASS",
        "single_lane_contract_pass": single["post_run_contract"]["status"] == "PASS",
        "single_lane_real_backward": single["trajectory"]["checks"][
            "real_backward_executed_once"
        ],
        "single_lane_pre_event_credit": single["trajectory"]["checks"][
            "pre_event_backward_credit_nonzero"
        ],
        "single_lane_bounded_control": single["trajectory"]["checks"][
            "control_budget_respected"
        ],
        "zero_control_is_noop": single["trajectory"]["checks"][
            "zero_control_exact_noop"
        ],
        "stable_axis_is_identity": single["trajectory"]["checks"][
            "stable_axis_exact_identity"
        ],
        "contract_never_enters_invocation": invocation_before == invocation_after,
        "semantic_receipt_binds_exact_contract": primary_contract_grade["status"]
        == "PASS"
        and alternate_contract_grade["status"] == "PASS"
        and primary_contract_grade["contract"]["fingerprint_sha256"]
        != alternate_contract_grade["contract"]["fingerprint_sha256"]
        and single["post_run_contract"]["contract"] == contract.to_dict(),
        "post_run_contract_rejects_subclass_serialization": misreporting_contract_rejected,
        "quantitative_actuator_is_model_visible": invocation_before["actuator_program"]
        == program.to_dict()
        and quantitative_invocation["actuator_program"]
        == quantitative_variant.to_dict()
        and invocation_before["prompt"] != quantitative_invocation["prompt"]
        and invocation_before["fingerprint_sha256"]
        != quantitative_invocation["fingerprint_sha256"]
        and "allocation_units" in invocation_before["prompt"]
        and "signed_control" in invocation_before["prompt"],
        "model_adapter_protocol_is_provider_neutral": (
            adapter.descriptor.interface_kind == "deterministic_conformance"
            and lane_b.model_adapter.descriptor.interface_kind == "hosted_api"
            and not lane_b.model_adapter.descriptor.differentiable_through_model
        ),
        "joint_v0_8_pass": joint["status"] == "PASS",
        "joint_contract_pass": joint["post_run_contract"]["status"] == "PASS",
        "joint_backward_is_single_block": joint["joint_trajectory"]["checks"][
            "one_joint_backward_executed"
        ],
        "joint_block_fd_agreement": joint["joint_trajectory"]["checks"][
            "block_finite_difference_agreement"
        ],
        "joint_global_budget": joint["joint_trajectory"]["checks"][
            "global_budget_respected"
        ],
        "joint_namespaces_unique": joint["joint_trajectory"]["checks"][
            "lane_namespace_unique"
        ],
        "joint_merge_is_deterministic": joint["merge"]["answer"] == "PROVE"
        and joint["merge"]["support_ids"] == ["R2", "R4", "R6"],
        "lane_order_is_permutation_invariant": joint["joint_trajectory"][
            "fingerprint_sha256"
        ]
        == joint_reversed["joint_trajectory"]["fingerprint_sha256"]
        and joint["merge"]["fingerprint_sha256"]
        == joint_reversed["merge"]["fingerprint_sha256"],
        "heterogeneous_execution_not_overclaimed": joint[
            "heterogeneous_model_execution_status"
        ]
        == "CONFORMANCE_ONLY"
        and declared_local_double_joint["heterogeneous_model_execution_status"]
        == "CONFORMANCE_ONLY"
        and joint["effect_attribution_status"] == "NOT_ASSESSED",
        "legacy_boundary_is_explicit": len(single["claim_boundary"])
        == len(CLAIM_BOUNDARY),
    }
    _require(all(checks.values()), "SELF_TEST_FAILED")
    return _seal(
        {
            "schema_version": SELF_TEST_SCHEMA_VERSION,
            "status": "PASS",
            "checks": checks,
            "single_result_fingerprint_sha256": single["fingerprint_sha256"],
            "joint_result_fingerprint_sha256": joint["fingerprint_sha256"],
            "provider_api_e2e_status": "DEFERRED_NO_CREDENTIALS",
            "local_open_weight_e2e_status": "RUN_LOCAL_E2E_COMMAND",
            "claim_boundary": list(CLAIM_BOUNDARY),
        }
    )


def _indexed_weight_files_are_complete(
    index_payloads: Sequence[Any],
    available_files: frozenset[str],
) -> bool:
    if not index_payloads:
        return False
    referenced: set[str] = set()
    for payload in index_payloads:
        if not isinstance(payload, Mapping):
            return False
        weight_map = payload.get("weight_map")
        if not isinstance(weight_map, Mapping) or not weight_map:
            return False
        for parameter_name, filename in weight_map.items():
            if (
                not isinstance(parameter_name, str)
                or not parameter_name
                or not isinstance(filename, str)
                or not filename
            ):
                return False
            shard = Path(filename)
            if shard.name != filename or shard.suffix != ".safetensors":
                return False
            referenced.add(filename)
    return bool(referenced) and referenced.issubset(available_files)


def _snapshot_has_complete_weights(path: Path) -> bool:
    try:
        weight_paths = tuple(path.glob("*.safetensors"))
        index_paths = tuple(sorted(path.glob("*.safetensors.index.json")))
    except OSError:
        return False
    available: set[str] = set()
    for weight_path in weight_paths:
        try:
            if weight_path.is_file() and weight_path.stat().st_size > 0:
                available.add(weight_path.name)
        except OSError:
            return False
    if index_paths:
        payloads: list[Any] = []
        for index_path in index_paths:
            try:
                payloads.append(json.loads(index_path.read_text(encoding="utf-8")))
            except (OSError, UnicodeError, json.JSONDecodeError):
                return False
        return _indexed_weight_files_are_complete(
            payloads,
            frozenset(available),
        )
    if len(available) != 1:
        return False
    only_weight = next(iter(available))
    return re.search(r"-\d{5}-of-\d{5}\.safetensors$", only_weight) is None


def _select_cached_snapshot(
    complete: Sequence[Path],
    *,
    active_revision: str | None,
) -> Path | None:
    candidates = tuple(complete)
    if active_revision is not None:
        _require(
            bool(re.fullmatch(r"[0-9A-Fa-f]{7,64}", active_revision)),
            "LOCAL_MODEL_ACTIVE_REF_INVALID",
        )
        selected = [path for path in candidates if path.name == active_revision]
        _require(
            len(selected) == 1,
            "LOCAL_MODEL_ACTIVE_SNAPSHOT_INCOMPLETE",
        )
        return selected[0]
    if not candidates:
        return None
    _require(len(candidates) == 1, "LOCAL_MODEL_SNAPSHOT_AMBIGUOUS")
    return candidates[0]


def _default_mlx_model_path() -> str | None:
    explicit = os.environ.get("EBRT_LOCAL_MODEL")
    if explicit:
        return explicit
    root = Path.home() / ".cache" / "huggingface" / "hub"
    candidates = (
        root / "models--mlx-community--Mistral-7B-Instruct-v0.3-4bit",
        root / "models--mlx-community--Llama-3.2-3B-bf16",
    )
    for candidate in candidates:
        snapshots = candidate / "snapshots"
        if snapshots.is_dir():
            complete = tuple(
                path
                for path in snapshots.iterdir()
                if path.is_dir() and _snapshot_has_complete_weights(path)
            )
            active_revision: str | None = None
            active_ref = candidate / "refs" / "main"
            if active_ref.exists():
                try:
                    active_revision = active_ref.read_text(encoding="utf-8").strip()
                except OSError as exc:
                    raise EBRTError("LOCAL_MODEL_ACTIVE_REF_UNREADABLE") from exc
            selected = _select_cached_snapshot(
                complete,
                active_revision=active_revision,
            )
            if selected is not None:
                return str(selected)
    return None


def _resolved_model_path(value: str | None) -> str:
    selected = value or _default_mlx_model_path()
    _require(selected is not None, "LOCAL_MODEL_NOT_CONFIGURED")
    return str(Path(selected).expanduser().resolve())


def run_local_e2e(model_path: str | None, model_id: str | None = None) -> JsonObject:
    task = build_demo_task()
    runtime = SharedMLXRuntime(_resolved_model_path(model_path), model_id=model_id)
    adapter = MLXLocalAdapter(runtime, adapter_id="mlx-local-primary")
    result = RevisionEngine().run(
        task,
        adapter,
        post_run_contract=build_demo_contract(),
    )
    _require(result["post_run_contract"]["status"] == "PASS", "LOCAL_E2E_FAILED")
    return result


def run_joint_local_e2e(
    model_path: str | None, model_id: str | None = None
) -> JsonObject:
    task = build_demo_task()
    runtime = SharedMLXRuntime(_resolved_model_path(model_path), model_id=model_id)
    lanes = (
        JointLaneSpec(
            lane_id="invalidation",
            state_adapter=TypedPublicStateAdapter(
                adapter_id="typed-public-invalidation-v0.8",
                support_scale=0.75,
                invalidation_scale=1.25,
                correction_scale=1.1,
            ),
            model_adapter=MLXLocalAdapter(runtime, adapter_id="mlx-local-invalidation"),
            prompt_policy="chronological",
            weight=1.0,
        ),
        JointLaneSpec(
            lane_id="support",
            state_adapter=TypedPublicStateAdapter(
                adapter_id="typed-public-support-v0.8",
                support_scale=1.25,
                invalidation_scale=0.75,
                correction_scale=1.0,
            ),
            model_adapter=MLXLocalAdapter(runtime, adapter_id="mlx-local-support"),
            prompt_policy="credit_first",
            weight=1.0,
        ),
    )
    result = JointRevisionEngine().run(
        task, lanes, post_run_contract=build_demo_contract()
    )
    _require(
        result["post_run_contract"]["status"] == "PASS",
        "JOINT_LOCAL_E2E_FAILED",
    )
    return result


def capabilities() -> JsonObject:
    return _seal(
        {
            "schema_version": "ebrt-capabilities-v0.8.0",
            "status": "READY",
            "core_protocol": CORE_PROTOCOL_VERSION,
            "joint_protocol": JOINT_PROTOCOL_VERSION,
            "interfaces": {
                "state_adapter": "build(task, lane_id) -> TrajectoryEnvelope",
                "actuator_adapter": "compile(task, credit_receipt, lane_id) -> ActuatorProgram",
                "model_adapter": "generate(task, program, prompt_policy) -> ModelResult",
                "observer": "sealed JSON receipts with independent structural and post-run grades",
            },
            "implemented_model_adapters": [
                {
                    "adapter": "MLXLocalAdapter",
                    "status": "EXECUTABLE_LOCAL_OPEN_WEIGHT",
                },
                {
                    "adapter": "CallableModelAdapter",
                    "status": "CONFORMANCE_EDGE_FOR_HOSTED_OR_LOCAL_BACKENDS",
                },
            ],
            "hosted_provider_e2e_status": "DEFERRED_NO_CREDENTIALS",
            "gradient_boundary": "StateAdapter trajectory; never ModelAdapter generation",
            "claim_boundary": list(CLAIM_BOUNDARY),
        }
    )


def _pretty(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("self-test", help="run network-zero v0.7.1/v0.8 conformance")
    commands.add_parser("capabilities", help="print the adapter and claim contract")
    commands.add_parser("demo-task", help="print the known synthetic task")
    local = commands.add_parser(
        "local-e2e", help="run v0.7.1 through a real local MLX model"
    )
    local.add_argument("--model", help="path to a complete local MLX model snapshot")
    local.add_argument(
        "--model-id",
        help="revision-bearing identity (provider/model@revision) required outside a Hugging Face snapshot",
    )
    joint = commands.add_parser(
        "joint-local-e2e",
        help="run v0.8 two-lane joint credit through one shared local MLX model",
    )
    joint.add_argument("--model", help="path to a complete local MLX model snapshot")
    joint.add_argument(
        "--model-id",
        help="revision-bearing identity (provider/model@revision) required outside a Hugging Face snapshot",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "self-test":
            value = self_test()
        elif args.command == "capabilities":
            value = capabilities()
        elif args.command == "demo-task":
            value = build_demo_task().to_public_dict()
        elif args.command == "local-e2e":
            value = run_local_e2e(args.model, args.model_id)
        elif args.command == "joint-local-e2e":
            value = run_joint_local_e2e(args.model, args.model_id)
        else:  # pragma: no cover
            raise EBRTError("UNKNOWN_COMMAND")
        print(_pretty(value), end="")
        return 0
    except EBRTError as error:
        print(
            _pretty(
                {
                    "schema_version": "ebrt-error-v0.8.0",
                    "status": "ERROR",
                    "reason_code": str(error),
                }
            ),
            end="",
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
