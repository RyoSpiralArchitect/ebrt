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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal, Mapping, Protocol, Sequence
from unittest import mock

import torch


CORE_PROTOCOL_VERSION = "ebrt-model-interface-core-v0.7.1"
JOINT_PROTOCOL_VERSION = "ebrt-joint-trajectory-v0.8.0"
RESULT_SCHEMA_VERSION = "ebrt-model-interface-result-v0.8.0"
SELF_TEST_SCHEMA_VERSION = "ebrt-model-interface-self-test-v0.8.0"
AXES = ("revision", "invalidation", "stability")
DTYPE = torch.float64
FD_EPSILON = 1.0e-6
FD_TOLERANCE = 2.0e-7
FLOAT_TOLERANCE = 1.0e-12

CLAIM_BOUNDARY = (
    "EBRT differentiates only through an explicit adapter-supplied trajectory.",
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


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise EBRTError(reason)


def _finite(value: float, label: str) -> float:
    number = float(value)
    _require(math.isfinite(number), f"{label}_NONFINITE")
    return 0.0 if number == 0.0 else number


def _tensor_values(value: torch.Tensor) -> Any:
    def normalize(item: Any) -> Any:
        if isinstance(item, list):
            return [normalize(child) for child in item]
        return _finite(float(item), "TENSOR_VALUE")

    return normalize(value.detach().cpu().tolist())


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


def validate_task(task: RevisionTask) -> None:
    _safe_id(task.task_id, "TASK_ID")
    _require(bool(task.question.strip()), "QUESTION_EMPTY")
    _require(len(task.answer_choices) >= 2, "ANSWER_CHOICES_TOO_SMALL")
    _require(
        len(set(task.answer_choices)) == len(task.answer_choices)
        and all(bool(row.strip()) for row in task.answer_choices),
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
        _require(bool(row.text.strip()), "EVIDENCE_TEXT_EMPTY")
        for label, vector in (
            ("NEUTRAL_EFFECT", row.neutral_effect),
            ("CONTROL_BASIS", row.control_basis),
        ):
            _require(len(vector) == len(AXES), f"{label}_DIMENSION_INVALID")
            for value in vector:
                _finite(value, label)
        _require(
            abs(row.control_basis[AXES.index("stability")]) <= FLOAT_TOLERANCE,
            "STABILITY_AXIS_MUST_BE_UNCONTROLLED",
        )
    id_set = set(ids)
    _safe_id(task.event.event_id, "EVENT_ID")
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
    _require(
        set(task.before_horizon_evidence_ids).issubset(id_set)
        and task.event.correction_evidence_id
        not in set(task.before_horizon_evidence_ids),
        "BEFORE_HORIZON_INVALID",
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
    _require(0.0 < task.decay <= 1.0, "DECAY_INVALID")
    _require(task.control_budget > 0.0, "CONTROL_BUDGET_INVALID")
    _require(task.learning_rate > 0.0, "LEARNING_RATE_INVALID")
    _require(
        1 <= task.reinspection_count <= len(task.evidence),
        "REINSPECTION_COUNT_INVALID",
    )


def validate_contract(task: RevisionTask, contract: PostRunContract) -> None:
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


@dataclass(frozen=True)
class TrajectoryEnvelope:
    lane_id: str
    state_adapter_id: str
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
        scale_by_role = {
            "context": 1.0,
            "required_support": self.support_scale,
            "invalidated_prior": self.invalidation_scale,
            "correction": self.correction_scale,
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
        return TrajectoryEnvelope(
            lane_id=lane_id,
            state_adapter_id=self.adapter_id,
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
                "gradient_boundary": "adapter_supplied_differentiable_trajectory",
            }
        )


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
        rows = {
            str(row["evidence_id"]): row for row in credit if isinstance(row, Mapping)
        }
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


@dataclass(frozen=True)
class AdapterDescriptor:
    adapter_id: str
    model_id: str
    interface_kind: Literal[
        "deterministic_conformance", "local_open_weight", "hosted_api"
    ]
    state_visibility: Literal["public_only", "native_latent"]
    differentiable_through_model: bool = False

    def to_dict(self) -> JsonObject:
        return {
            "adapter_id": self.adapter_id,
            "model_id": self.model_id,
            "interface_kind": self.interface_kind,
            "state_visibility": self.state_visibility,
            "differentiable_through_model": self.differentiable_through_model,
        }


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
    reinspect = ",".join(row[0] for row in program.reinspect)
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
            f"REINSPECT {reinspect}",
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
            "program_fingerprint_sha256": program.to_dict()["fingerprint_sha256"],
            "prompt": prompt,
        }
    )


def _parse_model_text(
    raw_text: str,
    *,
    task: RevisionTask,
) -> tuple[str, tuple[str, ...]]:
    answer_match = re.search(r"(?im)^\s*ANSWER\s*=\s*([^\s]+)\s*$", raw_text)
    support_match = re.search(r"(?im)^\s*SUPPORT\s*=\s*([^\n]*)$", raw_text)
    _require(answer_match is not None, "MODEL_ANSWER_LINE_MISSING")
    _require(support_match is not None, "MODEL_SUPPORT_LINE_MISSING")
    answer = answer_match.group(1).strip().strip("<>")
    _require(answer in task.answer_choices, "MODEL_ANSWER_OUTSIDE_CHOICES")
    support = tuple(
        row.strip()
        for row in support_match.group(1).strip().strip("<>").split(",")
        if row.strip() and row.strip().upper() != "NONE"
    )
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


class SharedMLXRuntime:
    """Lazy one-process MLX runtime shared by one or more v0.8 lanes."""

    def __init__(self, model_path: str, *, max_tokens: int = 48, seed: int = 0):
        path = Path(model_path).expanduser().resolve()
        _require(path.is_dir(), "LOCAL_MODEL_PATH_NOT_FOUND")
        _require(
            any(path.glob("*.safetensors"))
            or any(path.glob("*.safetensors.index.json")),
            "LOCAL_MODEL_WEIGHTS_NOT_FOUND",
        )
        self.model_path = path
        self.max_tokens = max_tokens
        self.seed = seed
        self._model: Any = None
        self._tokenizer: Any = None

    @property
    def model_id(self) -> str:
        return self.model_path.parent.parent.name.replace("models--", "").replace(
            "--", "/"
        )

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            from mlx_lm import load
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise EBRTError("MLX_LM_NOT_INSTALLED") from exc
        self._model, self._tokenizer = load(str(self.model_path))

    def generate(self, prompt: str) -> str:
        self._load()
        try:
            import mlx.core as mx
            from mlx_lm import generate
            from mlx_lm.sample_utils import make_sampler
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise EBRTError("MLX_LM_NOT_INSTALLED") from exc
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
        ).strip()


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
) -> JsonObject:
    known = {row.evidence_id for row in task.evidence}
    return {
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
        "gradient_did_not_cross_model_boundary": not result.descriptor.differentiable_through_model,
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
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
    }


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
        envelope = self.state_adapter.build(task, lane_id=lane_id)
        optimized = self.core.optimize(envelope)
        program = self.actuator_adapter.compile(task, optimized, lane_id=lane_id)
        result = model_adapter.generate(task, program, prompt_policy=prompt_policy)
        structural = _structural_model_checks(task, program, result)
        _require(all(structural.values()), "MODEL_RESULT_STRUCTURAL_FAILURE")
        contract_grade = (
            _grade_contract(result, program, post_run_contract)
            if post_run_contract is not None
            else {"status": "NOT_ASSESSED", "checks": {}}
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
        ordered_weights = tuple(float(row[1]) for row in paired)
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
                    "gradient_boundary": "adapter_supplied_differentiable_trajectory",
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


def _merge_model_results(
    task: RevisionTask,
    lane_results: Mapping[str, ModelResult],
    lane_weights: Mapping[str, float],
) -> JsonObject:
    vote_weight: Counter[str] = Counter()
    for lane_id, result in lane_results.items():
        vote_weight[result.answer] += float(lane_weights[lane_id])
    best_weight = max(vote_weight.values())
    tied = {answer for answer, weight in vote_weight.items() if weight == best_weight}
    if len(tied) == 1:
        answer = next(iter(tied))
        tie_break = "NONE"
    else:
        canonical_lane = sorted(lane_results)[0]
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
            "operator": "weighted_answer_consensus_support_union_minus_invalidated",
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
        envelopes = [
            row.state_adapter.build(task, lane_id=row.lane_id) for row in ordered_lanes
        ]
        joint = self.core.optimize(
            envelopes, weights=[row.weight for row in ordered_lanes]
        )
        programs: dict[str, ActuatorProgram] = {}
        results: dict[str, ModelResult] = {}
        structural: JsonObject = {}
        for lane in ordered_lanes:
            optimized = joint["lanes"][lane.lane_id]
            program = self.actuator_adapter.compile(
                task, optimized, lane_id=lane.lane_id
            )
            result = lane.model_adapter.generate(
                task, program, prompt_policy=lane.prompt_policy
            )
            checks = _structural_model_checks(task, program, result)
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
            else {"status": "NOT_ASSESSED", "checks": {}}
        )
        model_ids = {result.descriptor.model_id for result in results.values()}
        adapter_ids = {result.descriptor.adapter_id for result in results.values()}
        interface_kinds = {
            result.descriptor.interface_kind for result in results.values()
        }
        if len(model_ids) > 1 and interface_kinds == {"local_open_weight"}:
            heterogeneous_status = "OBSERVED"
        elif len(model_ids) > 1:
            heterogeneous_status = "CONFORMANCE_ONLY"
        else:
            heterogeneous_status = "NOT_ASSESSED"
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


def self_test() -> JsonObject:
    task = build_demo_task()
    contract = build_demo_contract()
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
        program = PublicRevisionActuator().compile(
            task,
            BackwardRevisionCore().optimize(
                TypedPublicStateAdapter().build(task, lane_id="contract-check")
            ),
            lane_id="contract-check",
        )
        invocation_before = build_model_invocation(
            task, program, prompt_policy="credit_first"
        )
        validate_contract(task, contract)
        invocation_after = build_model_invocation(
            task, program, prompt_policy="credit_first"
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
        joint = JointRevisionEngine().run(
            task, (lane_b, lane_a), post_run_contract=contract
        )
        joint_reversed = JointRevisionEngine().run(
            task, (lane_a, lane_b), post_run_contract=contract
        )

    checks = {
        "network_zero": network["count"] == 0,
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
            complete = sorted(
                path
                for path in snapshots.iterdir()
                if path.is_dir()
                and (
                    any(path.glob("*.safetensors"))
                    or any(path.glob("*.safetensors.index.json"))
                )
            )
            if complete:
                return str(complete[-1])
    return None


def _resolved_model_path(value: str | None) -> str:
    selected = value or _default_mlx_model_path()
    _require(selected is not None, "LOCAL_MODEL_NOT_CONFIGURED")
    return str(Path(selected).expanduser().resolve())


def run_local_e2e(model_path: str | None) -> JsonObject:
    task = build_demo_task()
    runtime = SharedMLXRuntime(_resolved_model_path(model_path))
    adapter = MLXLocalAdapter(runtime, adapter_id="mlx-local-primary")
    result = RevisionEngine().run(
        task,
        adapter,
        post_run_contract=build_demo_contract(),
    )
    _require(result["post_run_contract"]["status"] == "PASS", "LOCAL_E2E_FAILED")
    return result


def run_joint_local_e2e(model_path: str | None) -> JsonObject:
    task = build_demo_task()
    runtime = SharedMLXRuntime(_resolved_model_path(model_path))
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
    joint = commands.add_parser(
        "joint-local-e2e",
        help="run v0.8 two-lane joint credit through one shared local MLX model",
    )
    joint.add_argument("--model", help="path to a complete local MLX model snapshot")
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
            value = run_local_e2e(args.model)
        elif args.command == "joint-local-e2e":
            value = run_joint_local_e2e(args.model)
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
