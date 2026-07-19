#!/usr/bin/env python3
"""Matched synthetic benchmark for EBRT v0.5-T temporal state control.

Four arms share the same paired traces, terminal objective, control count,
standardized coordinate bound, L2 budget, and frozen public program. A, B, and
C share the optimizer policy; D inherits C's exact optimized values and only
changes their floor placement:

    A  static_collapsed_leaf
    B  temporal_leaf_only
    C  temporal_state_transition
    D  matched_floor_shuffle_sham

A is the neutral-point Jacobian collapse of B, not the frozen v0.5.0 binary.
D applies a locked permutation to C's final values, preserving its exact value
multiset and L2 norm while breaking floor placement.  The benchmark is local,
deterministic, synthetic, and network-free.  It does not execute GPT or grade a
natural-language answer.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import socket
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Sequence
from unittest import mock

import torch
from torch import Tensor

from temporal_adjoint_state_controller_v0_5_t import (
    CONTROLLER_VERSION,
    FLOAT_DTYPE,
    ControllerConfig,
    FrozenTemporalProgram,
    OptimizationResult,
    TemporalAdjointStateController,
    TemporalPairedSuite,
    _load_json_exact,
)


COMPARISON_SCHEMA_VERSION = "ebrt-temporal-control-comparison-v0.5-t.0"
BENCHMARK_NAME = "EBRT Temporal State-Control Matched Benchmark"
BENCHMARK_VERSION = "0.5-t.0-experiment"

ARM_A = "A_static_collapsed_leaf"
ARM_B = "B_temporal_leaf_only"
ARM_C = "C_temporal_state_transition"
ARM_D = "D_matched_floor_shuffle_sham"
ARM_ORDER = (ARM_A, ARM_B, ARM_C, ARM_D)

COLLAPSED_GRADIENT_ABS_TOLERANCE = 2e-12
SHAM_NORM_ABS_TOLERANCE = 1e-15
MIN_C_WIN_FRACTION_VS_B = 0.875
MIN_C_WIN_FRACTION_VS_D = 0.875
MIN_AGGREGATE_RELATIVE_REDUCTION_VS_B = 0.25
MIN_ORDER_SWITCH_FRACTION = 1.0
MIN_TOP_LEVERAGE_MARGIN = 0.01
EXPECTED_EARLY_TOP_CONTROL = "decision_write"
EXPECTED_EARLY_TOP_FLOOR_ORDINAL = 4
EXPECTED_LATE_TOP_CONTROL = "revision_mix"
EXPECTED_LATE_TOP_FLOOR_ORDINAL = 5


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


def _rounded(value: float, precision: int) -> float:
    result = round(float(value), precision)
    return 0.0 if result == -0.0 else result


@dataclass(frozen=True)
class ArmOutcome:
    arm_id: str
    control_lane: str
    program: FrozenTemporalProgram
    deltas: Tensor
    baseline_terminal: Tensor
    actual_terminal: Tensor
    actual_task_loss_before: float
    actual_task_loss_after: float
    optimization_objective_after: float
    predicted_terminal: Tensor | None
    predicted_task_loss_after: float | None
    backward_calls: int
    accepted: bool
    top_finite_leverage_target_id: str | None

    def to_row(self, config: ControllerConfig) -> dict[str, Any]:
        return {
            "pair_id": self.program.pair_id,
            "order_variant": self.program.order_variant,
            "arm_id": self.arm_id,
            "control_lane": self.control_lane,
            "control_count": len(self.deltas),
            "control_l2_norm": _rounded(
                torch.linalg.vector_norm(self.deltas).item(), config.numeric_precision
            ),
            "control_values": [
                _rounded(item.item(), config.numeric_precision) for item in self.deltas
            ],
            "actual_task_loss_before": _rounded(
                self.actual_task_loss_before, config.numeric_precision
            ),
            "actual_task_loss_after": _rounded(
                self.actual_task_loss_after, config.numeric_precision
            ),
            "optimization_objective_after": _rounded(
                self.optimization_objective_after, config.numeric_precision
            ),
            "predicted_task_loss_after": (
                _rounded(self.predicted_task_loss_after, config.numeric_precision)
                if self.predicted_task_loss_after is not None
                else None
            ),
            "terminal_decision_before": _rounded(
                self.baseline_terminal[self.program.decision_state_index].item(),
                config.numeric_precision,
            ),
            "terminal_decision_after": _rounded(
                self.actual_terminal[self.program.decision_state_index].item(),
                config.numeric_precision,
            ),
            "terminal_stable_before": _rounded(
                self.baseline_terminal[self.program.stable_state_index].item(),
                config.numeric_precision,
            ),
            "terminal_stable_after": _rounded(
                self.actual_terminal[self.program.stable_state_index].item(),
                config.numeric_precision,
            ),
            "backward_calls": self.backward_calls,
            "accepted": self.accepted,
            "top_finite_leverage_target_id": self.top_finite_leverage_target_id,
        }


class TemporalControlBenchmark:
    def __init__(
        self,
        suite: TemporalPairedSuite,
        config: ControllerConfig | None = None,
    ) -> None:
        self.suite = suite
        self.config = config or ControllerConfig()
        self.config.validate()
        self.controller = TemporalAdjointStateController(self.config)

    def _task_loss(
        self,
        program: FrozenTemporalProgram,
        terminal: Tensor,
        baseline_stable: Tensor,
    ) -> Tensor:
        revision = (
            terminal[program.decision_state_index] - program.terminal_decision_target
        ).square()
        stable = (terminal[program.stable_state_index] - baseline_stable).square()
        return (
            self.config.revision_consistency_weight * revision
            + self.config.stable_state_drift_weight * stable
        )

    def _project_logits_(self, logits: Tensor) -> float:
        with torch.no_grad():
            controls = self.controller.controls_from_logits(
                logits, self.config.max_control_abs
            )
            norm = float(torch.linalg.vector_norm(controls).item())
            if norm > self.config.max_control_l2_norm:
                controls.mul_(self.config.max_control_l2_norm / norm)
            ratio = (controls / self.config.max_control_abs).clamp(
                min=-1.0 + 1e-12, max=1.0 - 1e-12
            )
            logits.copy_(torch.atanh(ratio))
            return float(torch.linalg.vector_norm(controls).item())

    def _collapsed_jacobian(self, program: FrozenTemporalProgram) -> Tensor:
        neutral = torch.zeros(len(program.leaf_control_ids), dtype=FLOAT_DTYPE)
        return torch.autograd.functional.jacobian(
            lambda controls: self.controller.rollout(program, leaf_deltas=controls)[0],
            neutral,
            create_graph=False,
            strict=True,
        ).detach()

    def _terminal_control_jacobian(
        self, program: FrozenTemporalProgram, lane: str
    ) -> Tensor:
        control_ids = program.control_ids(lane)
        neutral = torch.zeros(len(control_ids), dtype=FLOAT_DTYPE)
        kwargs_name = "leaf_deltas" if lane == "leaf" else "transition_deltas"
        full = torch.autograd.functional.jacobian(
            lambda controls: self.controller.rollout(
                program, **{kwargs_name: controls}
            )[0],
            neutral,
            create_graph=False,
            strict=True,
        ).detach()
        objective_indices = torch.tensor(
            [program.decision_state_index, program.stable_state_index],
            dtype=torch.long,
        )
        return full[objective_indices]

    def _static_gradient_equivalence_error(
        self, program: FrozenTemporalProgram
    ) -> float:
        neutral = torch.zeros(
            len(program.leaf_control_ids),
            dtype=FLOAT_DTYPE,
            requires_grad=True,
        )
        baseline, _ = self.controller.rollout(program)
        baseline_stable = baseline[program.stable_state_index].detach()
        jacobian = self._collapsed_jacobian(program)
        predicted = baseline.detach() + jacobian @ neutral
        static_loss = self._task_loss(program, predicted, baseline_stable)
        static_loss = static_loss + self.config.control_l2_weight * torch.sum(
            neutral.square()
        )
        static_loss.backward()
        if neutral.grad is None:
            raise RuntimeError("static neutral gradient was not populated")
        temporal = self.controller.direct_control_gradient(program, "leaf")
        return float(torch.max(torch.abs(neutral.grad - temporal)).item())

    def _optimize_static_collapsed_leaf(
        self, program: FrozenTemporalProgram
    ) -> ArmOutcome:
        baseline, _ = self.controller.rollout(program)
        baseline_stable = baseline[program.stable_state_index].detach()
        baseline_task = float(
            self._task_loss(program, baseline, baseline_stable).item()
        )
        if not program.event_triggered:
            zero_controls = torch.zeros(
                len(program.leaf_control_ids), dtype=FLOAT_DTYPE
            )
            return ArmOutcome(
                arm_id=ARM_A,
                control_lane="leaf_static_collapsed",
                program=program,
                deltas=zero_controls,
                baseline_terminal=baseline,
                actual_terminal=baseline.clone(),
                actual_task_loss_before=baseline_task,
                actual_task_loss_after=baseline_task,
                optimization_objective_after=baseline_task,
                predicted_terminal=baseline.clone(),
                predicted_task_loss_after=baseline_task,
                backward_calls=0,
                accepted=False,
                top_finite_leverage_target_id=None,
            )
        jacobian = self._collapsed_jacobian(program)
        logits = torch.zeros(
            len(program.leaf_control_ids), dtype=FLOAT_DTYPE, requires_grad=True
        )
        optimizer = torch.optim.Adam([logits], lr=self.config.learning_rate)
        best_controls = torch.zeros_like(logits).detach()
        best_objective = baseline_task
        best_predicted = baseline.detach().clone()
        best_predicted_task = baseline_task
        backward_calls = 0
        for _ in range(self.config.revision_steps):
            optimizer.zero_grad(set_to_none=True)
            controls = self.controller.controls_from_logits(
                logits, self.config.max_control_abs
            )
            predicted = baseline.detach() + jacobian @ controls
            task = self._task_loss(program, predicted, baseline_stable)
            objective = task + self.config.control_l2_weight * torch.sum(
                controls.square()
            )
            if not torch.isfinite(objective):
                break
            objective.backward()
            backward_calls += 1
            if logits.grad is None or not torch.isfinite(logits.grad).all():
                break
            optimizer.step()
            self._project_logits_(logits)
            with torch.no_grad():
                candidate = self.controller.controls_from_logits(
                    logits, self.config.max_control_abs
                )
                candidate_predicted = baseline.detach() + jacobian @ candidate
                candidate_task = self._task_loss(
                    program, candidate_predicted, baseline_stable
                )
                candidate_objective = candidate_task + (
                    self.config.control_l2_weight * torch.sum(candidate.square())
                )
                value = float(candidate_objective.item())
                if value < best_objective:
                    best_objective = value
                    best_controls = candidate.detach().clone()
                    best_predicted = candidate_predicted.detach().clone()
                    best_predicted_task = float(candidate_task.item())
        accepted = best_objective < (baseline_task - self.config.acceptance_tolerance)
        final_controls = (
            best_controls
            if accepted
            else torch.zeros(len(program.leaf_control_ids), dtype=FLOAT_DTYPE)
        )
        with torch.no_grad():
            actual, _ = self.controller.rollout(program, leaf_deltas=final_controls)
            actual_task = float(
                self._task_loss(program, actual, baseline_stable).item()
            )
        return ArmOutcome(
            arm_id=ARM_A,
            control_lane="leaf_static_collapsed",
            program=program,
            deltas=final_controls,
            baseline_terminal=baseline,
            actual_terminal=actual,
            actual_task_loss_before=baseline_task,
            actual_task_loss_after=actual_task,
            optimization_objective_after=best_objective,
            predicted_terminal=best_predicted,
            predicted_task_loss_after=best_predicted_task,
            backward_calls=backward_calls,
            accepted=accepted,
            top_finite_leverage_target_id=None,
        )

    def _outcome_from_optimization(
        self,
        arm_id: str,
        result: OptimizationResult,
        top_control: str,
    ) -> ArmOutcome:
        before = (
            self.config.revision_consistency_weight
            * result.loss_before["revision_consistency"]
            + self.config.stable_state_drift_weight
            * result.loss_before["stable_state_drift"]
        )
        after = (
            self.config.revision_consistency_weight
            * result.loss_after["revision_consistency"]
            + self.config.stable_state_drift_weight
            * result.loss_after["stable_state_drift"]
        )
        return ArmOutcome(
            arm_id=arm_id,
            control_lane=result.lane,
            program=result.program,
            deltas=result.final_deltas,
            baseline_terminal=result.baseline_terminal_state,
            actual_terminal=result.final_terminal_state,
            actual_task_loss_before=before,
            actual_task_loss_after=after,
            optimization_objective_after=result.loss_after["total"],
            predicted_terminal=None,
            predicted_task_loss_after=None,
            backward_calls=result.backward_calls,
            accepted=result.accepted,
            top_finite_leverage_target_id=top_control,
        )

    def _matched_sham(
        self, program: FrozenTemporalProgram, source: OptimizationResult
    ) -> ArmOutcome:
        permutation = torch.tensor(
            self.suite.sham_source_index_by_target, dtype=torch.long
        )
        deltas = source.final_deltas[permutation].detach().clone()
        with torch.no_grad():
            baseline, _ = self.controller.rollout(program)
            baseline_stable = baseline[program.stable_state_index].clone()
            terminal, _ = self.controller.rollout(program, transition_deltas=deltas)
            before = float(self._task_loss(program, baseline, baseline_stable).item())
            after = float(self._task_loss(program, terminal, baseline_stable).item())
            objective = after + self.config.control_l2_weight * float(
                torch.sum(deltas.square()).item()
            )
        return ArmOutcome(
            arm_id=ARM_D,
            control_lane="transition_matched_shuffle",
            program=program,
            deltas=deltas,
            baseline_terminal=baseline,
            actual_terminal=terminal,
            actual_task_loss_before=before,
            actual_task_loss_after=after,
            optimization_objective_after=objective,
            predicted_terminal=None,
            predicted_task_loss_after=None,
            backward_calls=0,
            accepted=False,
            top_finite_leverage_target_id=None,
        )

    def run_program(
        self, program: FrozenTemporalProgram
    ) -> tuple[dict[str, ArmOutcome], dict[str, Any]]:
        static = self._optimize_static_collapsed_leaf(program)
        leaf_result = self.controller.optimize(program, "leaf")
        transition_result = self.controller.optimize(program, "transition")
        leaf_audit = self.controller.temporal_adjoint_audit(program, leaf_result)
        transition_audit = self.controller.temporal_adjoint_audit(
            program, transition_result
        )
        leaf = self._outcome_from_optimization(
            ARM_B,
            leaf_result,
            leaf_audit["floor_summary"]["top_finite_leverage_target_id"],
        )
        transition = self._outcome_from_optimization(
            ARM_C,
            transition_result,
            transition_audit["floor_summary"]["top_finite_leverage_target_id"],
        )
        sham = self._matched_sham(program, transition_result)
        return (
            {
                ARM_A: static,
                ARM_B: leaf,
                ARM_C: transition,
                ARM_D: sham,
            },
            {
                "collapsed_gradient_error": self._static_gradient_equivalence_error(
                    program
                ),
                "leaf_terminal_jacobian_frobenius_norm": float(
                    torch.linalg.matrix_norm(
                        self._terminal_control_jacobian(program, "leaf")
                    ).item()
                ),
                "transition_terminal_jacobian_frobenius_norm": float(
                    torch.linalg.matrix_norm(
                        self._terminal_control_jacobian(program, "transition")
                    ).item()
                ),
                "transition_audit": transition_audit,
                "transition_result": transition_result,
            },
        )

    @staticmethod
    def _reachable_subspace_witness() -> dict[str, Any]:
        """Exact witness using the core's same ``(M + cD)h + bxg`` equation."""

        identity = torch.eye(2, dtype=FLOAT_DTYPE)
        evidence_axis = torch.tensor([1.0, 0.0], dtype=FLOAT_DTYPE)
        transition_basis = torch.tensor([[0.0, 0.0], [1.0, 0.0]], dtype=FLOAT_DTYPE)

        def evidence_floor(state: Tensor, leaf_delta: Tensor) -> Tensor:
            return identity @ state + evidence_axis * (1.0 + leaf_delta)

        def transition_floor(state: Tensor, transition_delta: Tensor) -> Tensor:
            return (identity + transition_delta * transition_basis) @ state

        def rollout(
            order: tuple[str, str], leaf_delta: Tensor, transition_delta: Tensor
        ) -> Tensor:
            state = torch.zeros(2, dtype=FLOAT_DTYPE)
            for operator in order:
                if operator == "evidence":
                    state = evidence_floor(state, leaf_delta)
                else:
                    state = transition_floor(state, transition_delta)
            return state

        variants = {
            "evidence_then_transition": ("evidence", "transition"),
            "transition_then_evidence": ("transition", "evidence"),
        }
        rows: dict[str, Any] = {}
        zero = torch.tensor(0.0, dtype=FLOAT_DTYPE)
        for name, order in variants.items():
            leaf_jacobian = torch.autograd.functional.jacobian(
                lambda control: rollout(order, control, zero), zero
            )
            transition_jacobian = torch.autograd.functional.jacobian(
                lambda control: rollout(order, zero, control), zero
            )
            leaf_decision = float(leaf_jacobian[1].item())
            transition_decision = float(transition_jacobian[1].item())
            if leaf_decision != 0.0:
                raise AssertionError("linear witness leaf lane reached decision axis")
            expected_transition = 1.0 if name == "evidence_then_transition" else 0.0
            if transition_decision != expected_transition:
                raise AssertionError("linear witness transition reachability mismatch")
            rows[name] = {
                "leaf_decision_jacobian": leaf_decision,
                "transition_decision_jacobian": transition_decision,
                "leaf_decision_reachable": False,
                "transition_decision_reachable": transition_decision != 0.0,
            }
        return {
            "state_axes": ["public_evidence", "public_decision"],
            "intervention_equation": "h_t=(M_t+c_t*D_t)h_(t-1)+b_t*x_t*(1+e_t)",
            "variants": rows,
            "bounded_claim": (
                "For this supplied linear public program and the controller's exact "
                "transition-basis equation, a post-evidence transition control reaches "
                "a terminal direction outside the admitted leaf-control span. Reversing "
                "the operator order removes that local transition leverage. Adding "
                "state-control pseudo-leaves could algebraically collapse the enlarged "
                "intervention class."
            ),
        }

    def comparison_without_fingerprint(self) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        outcomes_by_case: dict[tuple[str, str], dict[str, ArmOutcome]] = {}
        diagnostics_by_case: dict[tuple[str, str], dict[str, Any]] = {}
        for pair in self.suite.pair_parameters:
            for order in self.suite.trace_orders:
                program = self.suite.materialize(pair.pair_id, order.order_variant)
                outcomes, diagnostics = self.run_program(program)
                outcomes_by_case[(pair.pair_id, order.order_variant)] = outcomes
                diagnostics_by_case[(pair.pair_id, order.order_variant)] = diagnostics
                rows.extend(outcomes[arm].to_row(self.config) for arm in ARM_ORDER)

        case_count = len(outcomes_by_case)
        aggregate: dict[str, Any] = {}
        for arm in ARM_ORDER:
            values = [outcomes[arm] for outcomes in outcomes_by_case.values()]
            before_sum = sum(item.actual_task_loss_before for item in values)
            after_sum = sum(item.actual_task_loss_after for item in values)
            aggregate[arm] = {
                "case_count": case_count,
                "actual_task_loss_before_sum": _rounded(
                    before_sum, self.config.numeric_precision
                ),
                "actual_task_loss_after_sum": _rounded(
                    after_sum, self.config.numeric_precision
                ),
                "actual_task_loss_after_mean": _rounded(
                    after_sum / case_count, self.config.numeric_precision
                ),
            }

        c_wins_b = sum(
            outcomes[ARM_C].actual_task_loss_after
            < outcomes[ARM_B].actual_task_loss_after
            for outcomes in outcomes_by_case.values()
        )
        c_wins_d = sum(
            outcomes[ARM_C].actual_task_loss_after
            < outcomes[ARM_D].actual_task_loss_after
            for outcomes in outcomes_by_case.values()
        )
        c_win_fraction_b = c_wins_b / case_count
        c_win_fraction_d = c_wins_d / case_count
        b_after_sum = sum(
            outcomes[ARM_B].actual_task_loss_after
            for outcomes in outcomes_by_case.values()
        )
        c_after_sum = sum(
            outcomes[ARM_C].actual_task_loss_after
            for outcomes in outcomes_by_case.values()
        )
        relative_reduction = 1.0 - c_after_sum / b_after_sum
        order_switch_pairs = 0
        floor_margin_passes = 0
        pair_floor_rows: list[dict[str, Any]] = []
        for pair in self.suite.pair_parameters:
            tops: dict[str, Any] = {}
            for order in self.suite.trace_orders:
                summary = diagnostics_by_case[(pair.pair_id, order.order_variant)][
                    "transition_audit"
                ]["floor_summary"]
                tops[order.order_variant] = {
                    "target_id": summary["top_finite_leverage_target_id"],
                    "floor_ordinal": summary["top_finite_leverage_floor_ordinal"],
                    "margin_over_second": summary[
                        "top_finite_leverage_margin_over_second"
                    ],
                }
            expected = (
                tops.get("early_correction", {}).get("target_id")
                == EXPECTED_EARLY_TOP_CONTROL
                and tops.get("early_correction", {}).get("floor_ordinal")
                == EXPECTED_EARLY_TOP_FLOOR_ORDINAL
                and tops.get("late_correction", {}).get("target_id")
                == EXPECTED_LATE_TOP_CONTROL
                and tops.get("late_correction", {}).get("floor_ordinal")
                == EXPECTED_LATE_TOP_FLOOR_ORDINAL
            )
            margin_pass = all(
                item["margin_over_second"] >= MIN_TOP_LEVERAGE_MARGIN
                for item in tops.values()
            )
            order_switch_pairs += int(expected)
            floor_margin_passes += int(margin_pass)
            pair_floor_rows.append(
                {
                    "parameter_cell_id": pair.pair_id,
                    "top_controls": tops,
                    "expected_switch": expected,
                    "minimum_margin_pass": margin_pass,
                }
            )
        order_switch_fraction = order_switch_pairs / len(self.suite.pair_parameters)
        floor_margin_fraction = floor_margin_passes / len(self.suite.pair_parameters)

        max_collapsed_error = max(
            diagnostics["collapsed_gradient_error"]
            for diagnostics in diagnostics_by_case.values()
        )
        sham_norm_errors: list[float] = []
        sham_multiset_matches: list[bool] = []
        for outcomes in outcomes_by_case.values():
            c_values = outcomes[ARM_C].deltas
            d_values = outcomes[ARM_D].deltas
            sham_norm_errors.append(
                abs(
                    float(torch.linalg.vector_norm(c_values).item())
                    - float(torch.linalg.vector_norm(d_values).item())
                )
            )
            sham_multiset_matches.append(
                sorted(float(item) for item in c_values)
                == sorted(float(item) for item in d_values)
            )
        max_sham_norm_error = max(sham_norm_errors)

        nonidentity_permutations = [
            permutation
            for permutation in itertools.permutations(
                range(len(self.suite.transition_control_ids))
            )
            if permutation != tuple(range(len(self.suite.transition_control_ids)))
        ]
        exhaustive_sham_rows: list[dict[str, Any]] = []
        for permutation in nonidentity_permutations:
            aggregate_loss = 0.0
            cell_wins = 0
            permutation_tensor = torch.tensor(permutation, dtype=torch.long)
            for outcomes in outcomes_by_case.values():
                source = outcomes[ARM_C]
                candidate = source.deltas[permutation_tensor]
                with torch.no_grad():
                    terminal, _ = self.controller.rollout(
                        source.program, transition_deltas=candidate
                    )
                    stable = source.baseline_terminal[source.program.stable_state_index]
                    candidate_loss = float(
                        self._task_loss(source.program, terminal, stable).item()
                    )
                aggregate_loss += candidate_loss
                cell_wins += int(source.actual_task_loss_after < candidate_loss)
            exhaustive_sham_rows.append(
                {
                    "source_index_by_target": list(permutation),
                    "aggregate_actual_task_loss": _rounded(
                        aggregate_loss, self.config.numeric_precision
                    ),
                    "C_wins_cells": cell_wins,
                    "C_win_fraction": cell_wins / case_count,
                }
            )
        best_nonidentity_sham_loss = min(
            row["aggregate_actual_task_loss"] for row in exhaustive_sham_rows
        )
        minimum_exhaustive_sham_win_fraction = min(
            row["C_win_fraction"] for row in exhaustive_sham_rows
        )
        c_beats_every_sham_aggregate = all(
            c_after_sum < row["aggregate_actual_task_loss"]
            for row in exhaustive_sham_rows
        )

        actuator_scale_rows: list[dict[str, Any]] = []
        for (pair_id, order_variant), diagnostics in diagnostics_by_case.items():
            leaf_norm = diagnostics["leaf_terminal_jacobian_frobenius_norm"]
            transition_norm = diagnostics["transition_terminal_jacobian_frobenius_norm"]
            actuator_scale_rows.append(
                {
                    "parameter_cell_id": pair_id,
                    "order_variant": order_variant,
                    "leaf_terminal_jacobian_frobenius_norm": _rounded(
                        leaf_norm, self.config.numeric_precision
                    ),
                    "transition_terminal_jacobian_frobenius_norm": _rounded(
                        transition_norm, self.config.numeric_precision
                    ),
                    "transition_to_leaf_norm_ratio": _rounded(
                        transition_norm / leaf_norm,
                        self.config.numeric_precision,
                    ),
                }
            )

        gates = {
            "collapsed_A_B_neutral_gradient_equivalence": {
                "threshold": COLLAPSED_GRADIENT_ABS_TOLERANCE,
                "observed_max_abs_error": max_collapsed_error,
                "pass": max_collapsed_error <= COLLAPSED_GRADIENT_ABS_TOLERANCE,
            },
            "C_win_fraction_vs_B_cells": {
                "threshold": MIN_C_WIN_FRACTION_VS_B,
                "observed": c_win_fraction_b,
                "wins": c_wins_b,
                "total": case_count,
                "pass": c_win_fraction_b >= MIN_C_WIN_FRACTION_VS_B,
            },
            "C_win_fraction_vs_locked_D_cells": {
                "threshold": MIN_C_WIN_FRACTION_VS_D,
                "observed": c_win_fraction_d,
                "wins": c_wins_d,
                "total": case_count,
                "pass": c_win_fraction_d >= MIN_C_WIN_FRACTION_VS_D,
            },
            "C_aggregate_relative_reduction_vs_B": {
                "threshold": MIN_AGGREGATE_RELATIVE_REDUCTION_VS_B,
                "observed": relative_reduction,
                "pass": relative_reduction >= MIN_AGGREGATE_RELATIVE_REDUCTION_VS_B,
            },
            "order_sensitive_top_floor_parameter_cells": {
                "threshold": MIN_ORDER_SWITCH_FRACTION,
                "observed": order_switch_fraction,
                "matching_cells": order_switch_pairs,
                "total": len(self.suite.pair_parameters),
                "pass": order_switch_fraction >= MIN_ORDER_SWITCH_FRACTION,
            },
            "top_finite_leverage_margin_parameter_cells": {
                "threshold": MIN_TOP_LEVERAGE_MARGIN,
                "observed_fraction_passing": floor_margin_fraction,
                "matching_cells": floor_margin_passes,
                "total": len(self.suite.pair_parameters),
                "pass": floor_margin_fraction == 1.0,
            },
            "matched_sham_exact_value_multiset": {
                "observed_all": all(sham_multiset_matches),
                "pass": all(sham_multiset_matches),
            },
            "matched_sham_L2_norm": {
                "threshold": SHAM_NORM_ABS_TOLERANCE,
                "observed_max_abs_error": max_sham_norm_error,
                "pass": max_sham_norm_error <= SHAM_NORM_ABS_TOLERANCE,
            },
            "C_beats_every_nonidentity_sham_aggregate": {
                "nonidentity_permutation_count": len(exhaustive_sham_rows),
                "C_aggregate_actual_task_loss": c_after_sum,
                "best_nonidentity_sham_aggregate_actual_task_loss": best_nonidentity_sham_loss,
                "pass": c_beats_every_sham_aggregate,
            },
            "C_win_fraction_against_every_nonidentity_sham": {
                "threshold": 1.0,
                "observed_minimum": minimum_exhaustive_sham_win_fraction,
                "pass": minimum_exhaustive_sham_win_fraction == 1.0,
            },
        }
        all_pass = all(item["pass"] for item in gates.values())
        return {
            "schema_version": COMPARISON_SCHEMA_VERSION,
            "benchmark": {
                "name": BENCHMARK_NAME,
                "version": BENCHMARK_VERSION,
                "controller_version": CONTROLLER_VERSION,
                "randomness": "deterministic_no_rng",
                "network_calls": 0,
            },
            "source": {
                "suite_id": self.suite.suite_id,
                "semantic_payload_sha256": self.suite.semantic_payload_sha256(),
                "parameter_sweep_cell_count": len(self.suite.pair_parameters),
                "order_variant_count": len(self.suite.trace_orders),
                "evaluated_ordered_cell_count": case_count,
                "independent_replication_count": 1,
            },
            "design": {
                "arms": list(ARM_ORDER),
                "shared_terminal_objective": (
                    "decision replacement error + unrelated stable-state drift"
                ),
                "shared_control_count": len(self.suite.leaf_control_ids),
                "shared_standardized_coordinate_max_abs": self.config.max_control_abs,
                "shared_standardized_coordinate_L2_budget": self.config.max_control_l2_norm,
                "effective_actuator_scale_matched": False,
                "effective_actuator_scale_note": (
                    "Frobenius-normalized local bases share a coordinate budget, but "
                    "their terminal Jacobian norms differ with supplied actuator geometry "
                    "and trace order; those norms are reported, not controlled away."
                ),
                "gate_registration": (
                    "locked after pilot implementation; this is not a preregistered study"
                ),
                "sham_source_index_by_target": list(
                    self.suite.sham_source_index_by_target
                ),
                "A_definition": (
                    "neutral-point terminal Jacobian collapse of B; optimized in the "
                    "linearized state and evaluated again in the actual recurrence"
                ),
                "D_definition": (
                    "C final values permuted across locked target floors without "
                    "changing value multiset, sign multiset, sparsity, or L2 norm"
                ),
            },
            "rows": rows,
            "aggregate": aggregate,
            "pair_floor_switches": pair_floor_rows,
            "actuator_scale_audit": actuator_scale_rows,
            "exhaustive_nonidentity_sham_audit": exhaustive_sham_rows,
            "locked_mechanism_gates": gates,
            "decision": {
                "status": (
                    "RECORD_POSITIVE_TEMPORAL_STATE_CONTROL_MECHANISM"
                    if all_pass
                    else "STOP_TEMPORAL_ADDS_EXPLANATION_ONLY"
                ),
                "all_locked_gates_pass": all_pass,
                "bounded_claim": (
                    "On one synthetic oracle-specified topology and its parameter "
                    "sweep, exact local adjoints optimized bounded transition-basis "
                    "controls that outperformed leaf controls and every matched floor "
                    "permutation. The result includes the supplied actuator geometry."
                    if all_pass
                    else "The tested temporal controller did not establish an intervention capability beyond leaf control."
                ),
            },
            "reachable_subspace_witness": self._reachable_subspace_witness(),
            "claim_boundary": [
                "All public transitions, control bases, evidence values, ordering, event flags, and terminal targets are synthetic oracle inputs.",
                "A and B have the same neutral local gradient by construction; finite controls can diverge because A is a linearization.",
                "The eight parameter cells are a local sweep of one topology, not eight independent replications.",
                "Leaf and transition arms share standardized coordinate count and L2 bounds, not matched terminal Jacobian scale; C versus B therefore includes oracle actuator-geometry leverage and does not isolate temporal credit assignment alone.",
                "C winning under that shared coordinate budget supports a supplied-intervention-class result, not dependency discovery or universal non-collapsibility.",
                "Adjoint sensitivity and finite leverage are local surrogate diagnostics, not causal importance or model attention.",
                "No provider, hidden state, final natural-language output, downstream grader, latency, or token count participates.",
                "No hosted-model reasoning-quality, efficiency, production-readiness, or real-world causal claim is supported.",
            ],
        }

    def comparison(self) -> dict[str, Any]:
        payload = self.comparison_without_fingerprint()
        payload["fingerprint_sha256"] = _sha256_json(payload)
        return payload

    def canonical_comparison_bytes(self) -> bytes:
        return _canonical_json_bytes(self.comparison(), trailing_newline=True)


@contextmanager
def _network_guard() -> Iterator[None]:
    with mock.patch.object(
        socket, "socket", side_effect=AssertionError("network used")
    ):
        yield


def run_self_tests(fixture_path: Path) -> dict[str, Any]:
    suite = TemporalPairedSuite.from_mapping(_load_json_exact(fixture_path))
    benchmark = TemporalControlBenchmark(suite)
    with _network_guard():
        first = benchmark.comparison()
    second = benchmark.comparison()
    if _canonical_json_bytes(first) != _canonical_json_bytes(second):
        raise AssertionError("identical comparisons were not byte deterministic")
    fingerprint = first.pop("fingerprint_sha256")
    if fingerprint != _sha256_json(first):
        raise AssertionError("comparison fingerprint does not cover exact payload")
    first["fingerprint_sha256"] = fingerprint
    gates = first["locked_mechanism_gates"]
    if not all(item["pass"] for item in gates.values()):
        failed = [name for name, item in gates.items() if not item["pass"]]
        raise AssertionError(f"predeclared temporal gates failed: {failed}")
    if (
        first["decision"]["status"]
        != "RECORD_POSITIVE_TEMPORAL_STATE_CONTROL_MECHANISM"
    ):
        raise AssertionError("passing gates did not record the mechanism result")
    rows = first["rows"]
    expected_rows = (
        len(suite.pair_parameters) * len(suite.trace_orders) * len(ARM_ORDER)
    )
    if len(rows) != expected_rows:
        raise AssertionError("comparison row count is incomplete")
    for pair in first["pair_floor_switches"]:
        if not pair["expected_switch"] or not pair["minimum_margin_pass"]:
            raise AssertionError("one paired trace failed its floor-switch contract")

    no_event_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "temporal_adjoint_state_controller_v0_5_t_no_event.json"
    )
    no_event_suite = TemporalPairedSuite.from_mapping(_load_json_exact(no_event_path))
    no_event_program = no_event_suite.materialize("P00", "early_correction")
    no_event_outcomes, _ = TemporalControlBenchmark(no_event_suite).run_program(
        no_event_program
    )
    for arm_id, outcome in no_event_outcomes.items():
        if outcome.backward_calls != 0 or outcome.accepted:
            raise AssertionError(f"no-event arm {arm_id} invoked optimization")
        if not torch.equal(outcome.deltas, torch.zeros_like(outcome.deltas)):
            raise AssertionError(f"no-event arm {arm_id} emitted nonzero controls")
        if not torch.equal(outcome.baseline_terminal, outcome.actual_terminal):
            raise AssertionError(f"no-event arm {arm_id} changed terminal state")

    # Non-default weights guard the shared task-loss contract. Defaults of 1.0
    # would hide an accidental raw sum in either benchmark rows or leverage.
    weighted_config = ControllerConfig(
        revision_steps=2,
        revision_consistency_weight=2.0,
        stable_state_drift_weight=3.0,
    )
    weighted_benchmark = TemporalControlBenchmark(suite, weighted_config)
    weighted_program = suite.materialize("P03", "late_correction")
    weighted_result = weighted_benchmark.controller.optimize(
        weighted_program, "transition"
    )
    weighted_audit = weighted_benchmark.controller.temporal_adjoint_audit(
        weighted_program, weighted_result
    )
    weighted_outcome = weighted_benchmark._outcome_from_optimization(
        ARM_C,
        weighted_result,
        weighted_audit["floor_summary"]["top_finite_leverage_target_id"],
    )
    expected_weighted_after = float(
        weighted_benchmark._task_loss(
            weighted_program,
            weighted_result.final_terminal_state,
            weighted_result.baseline_terminal_state[
                weighted_program.stable_state_index
            ],
        ).item()
    )
    if abs(weighted_outcome.actual_task_loss_after - expected_weighted_after) > 1e-15:
        raise AssertionError("non-default benchmark task weights were not preserved")
    leverage, steps = weighted_benchmark.controller.finite_control_leverage(
        weighted_program, "transition"
    )
    probe_id = "revision_mix"
    probe_index = weighted_program.transition_control_ids.index(probe_id)
    probe = torch.zeros(len(weighted_program.transition_control_ids), dtype=FLOAT_DTYPE)
    probe[probe_index] = steps[probe_id]
    baseline, _ = weighted_benchmark.controller.rollout(weighted_program)
    candidate, _ = weighted_benchmark.controller.rollout(
        weighted_program, transition_deltas=probe
    )
    expected_leverage = float(
        (
            weighted_benchmark._task_loss(
                weighted_program,
                baseline,
                baseline[weighted_program.stable_state_index],
            )
            - weighted_benchmark._task_loss(
                weighted_program,
                candidate,
                baseline[weighted_program.stable_state_index],
            )
        ).item()
    )
    if abs(leverage[probe_id] - expected_leverage) > 1e-15:
        raise AssertionError("non-default finite-leverage weights were not preserved")
    return {
        "status": "PASS",
        "benchmark": f"{BENCHMARK_NAME} {BENCHMARK_VERSION}",
        "checks": [
            "A/B neutral collapsed-Jacobian gradient equivalence",
            "same standardized control count and L2 coordinate budget across all four arms",
            "C beats B, locked D, and every nonidentity floor permutation under locked gates",
            "top finite-leverage control changes with evidence order",
            "sham preserves exact control-value multiset and L2 norm",
            "exact linear witness separates supplied leaf and state reachable spans",
            "non-default loss weights remain consistent in rows and finite leverage",
            "all four benchmark arms preserve no-event identity without backward optimization",
            "two identical comparisons are byte deterministic",
            "comparison completes while socket creation is denied",
        ],
        "observed": {
            name: {
                key: value
                for key, value in item.items()
                if key
                in {
                    "observed",
                    "observed_max_abs_error",
                    "observed_all",
                    "observed_fraction_passing",
                    "observed_minimum",
                    "wins",
                    "total",
                }
            }
            for name, item in gates.items()
        },
        "comparison_fingerprint_sha256": fingerprint,
        "claim_boundary": first["claim_boundary"],
    }


def _pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _default_fixture() -> Path:
    return (
        Path(__file__).resolve().parent
        / "fixtures"
        / ("temporal_adjoint_state_controller_v0_5_t_dev.json")
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-json", type=Path, default=_default_fixture())
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("self-test")
    subparsers.add_parser("run")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "self-test":
        print(_pretty_json(run_self_tests(args.input_json)), end="")
        return 0
    suite = TemporalPairedSuite.from_mapping(_load_json_exact(args.input_json))
    print(_pretty_json(TemporalControlBenchmark(suite).comparison()), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
