#!/usr/bin/env python3
"""Capacity-matched dual-route policy for the frozen EBRT mechanism.

This module adds a runtime policy without editing the v0.1 mechanism or the
v0.2 observer.  It separates three roles that v0.1 intentionally represented
with one ``RevisionEvent.target_steps`` field:

* objective anchors: states that define what premise is being corrected;
* control steps: states whose bounded control vectors may be optimized; and
* replay floor: the common suffix boundary used by every matched arm.

The online leverage feature is a prefix-only centered finite difference.  It
never reads an observation or state after the event source.  In ``matched``
mode every arm pays the same probe cost; in ``native`` mode only L2, D2, and G2
run the probe because only those policies consume its ranking.

This remains a structured toy-state policy experiment, not a claim about
natural-language reasoning or pretrained-model hidden states.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import torch

import instrumentation_ebrt_v0_2 as observer


SCHEMA_VERSION = "ebrt-dual-route-policy-v0.3"
ARMS = ("S2", "L2", "D2", "SR2", "G2")
ARM_IDS = {
    "S2": "S2_semantic",
    "L2": "L2_source_projection",
    "D2": "D2_dual",
    "SR2": "SR2_semantic_random",
    "G2": "G2_gold_diagnostic",
}
ARM_ALIASES = {
    **{arm: arm for arm in ARMS},
    **{value: key for key, value in ARM_IDS.items()},
}
PROBE_MODES = ("matched", "native")
NATIVE_PROBE_ARMS = frozenset({"L2", "D2", "G2"})
EXPECTED_MONOLITH_SHA256 = (
    "b1702f2868839d989cc3a9321d227436a23c3dad6cc86483edee9d5dbab3a529"
)
EXPECTED_INSTRUMENTATION_SHA256 = (
    "663b0e446e07d8c24be228f3e5e56a6a53665bd3a637979bf285597f7d0bbb7d"
)
DEFAULT_ROUTE_CAPACITY = 2
DEFAULT_LEVERAGE_EPSILON = 1e-3
DEFAULT_EVENT_DELTA_NORM_CAP = 1.75
DEFAULT_ABSOLUTE_CONTROL_NORM_CAP = 1.75
DEFAULT_GEOMETRY_EPSILON = 1e-8

MODULE_PATH = Path(__file__).resolve()
MONOLITH_PATH = MODULE_PATH.with_name("ebrt_monolith_v0_1.py")
INSTRUMENTATION_PATH = MODULE_PATH.with_name("instrumentation_ebrt_v0_2.py")
frozen = observer.frozen


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_frozen_sources() -> dict[str, str]:
    """Fail closed if either inherited implementation changed."""

    actual_monolith = _sha256(MONOLITH_PATH)
    actual_instrumentation = _sha256(INSTRUMENTATION_PATH)
    if actual_monolith != EXPECTED_MONOLITH_SHA256:
        raise RuntimeError(
            "frozen v0.1 monolith SHA256 mismatch: "
            f"expected={EXPECTED_MONOLITH_SHA256} actual={actual_monolith}"
        )
    if actual_instrumentation != EXPECTED_INSTRUMENTATION_SHA256:
        raise RuntimeError(
            "frozen v0.2 instrumentation SHA256 mismatch: "
            f"expected={EXPECTED_INSTRUMENTATION_SHA256} "
            f"actual={actual_instrumentation}"
        )
    return {
        "monolith_sha256": actual_monolith,
        "instrumentation_sha256": actual_instrumentation,
    }


assert_frozen_sources()


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _tensor_payload(value: torch.Tensor) -> list[Any]:
    return value.detach().cpu().tolist()


def _tensor_fingerprint(value: torch.Tensor) -> str:
    return _fingerprint(_tensor_payload(value))


def _ordered_unique(values: Sequence[int]) -> list[int]:
    output: list[int] = []
    for value in values:
        integer = int(value)
        if integer not in output:
            output.append(integer)
    return output


@dataclass(frozen=True)
class RoutePlan:
    """One event's separated semantic, control, and replay decisions."""

    arm: str
    source_step: int
    objective_anchor_steps: tuple[int, ...]
    control_steps: tuple[int, ...]
    replay_floor: int
    candidate_steps: tuple[int, ...]
    semantic_rank: tuple[int, ...]
    leverage_rank: tuple[int, ...]
    gold_steps: tuple[int, ...]
    probe_mode: str
    probe_performed: bool
    probe_used_for_routing: bool
    online_probe_generator_step_calls: int
    decision_state_fingerprint: str
    decision_control_fingerprint: str
    capacity_requested: int
    capacity_used: int
    arm_id: str
    case_id: str
    model_seed: int
    event_ordinal: int
    replay_policy: str

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


class DualRoutePolicyReasoner(observer.InstrumentedEventDrivenBackwardReasoner):
    """Instrumented EBRT execution with a branch-local matched route policy."""

    def __init__(
        self,
        config: Any | None = None,
        *,
        arm: str,
        case_id: str = "unspecified",
        probe_mode: str = "matched",
        route_seed: int = 0,
        gold_steps_by_source: Mapping[int, Sequence[int]] | None = None,
        route_capacity: int = DEFAULT_ROUTE_CAPACITY,
        leverage_epsilon: float = DEFAULT_LEVERAGE_EPSILON,
        event_delta_norm_cap: float = DEFAULT_EVENT_DELTA_NORM_CAP,
        geometry_epsilon: float = DEFAULT_GEOMETRY_EPSILON,
        capture_deep: bool = False,
    ) -> None:
        if arm not in ARM_ALIASES:
            raise ValueError(
                f"arm must be a short or locked ID from {tuple(ARM_ALIASES)}, "
                f"got {arm!r}"
            )
        if probe_mode not in PROBE_MODES:
            raise ValueError(
                f"probe_mode must be one of {PROBE_MODES}, got {probe_mode!r}"
            )
        if route_capacity != 2:
            raise ValueError("v0.3 matched policy requires route_capacity=2")
        if leverage_epsilon <= 0.0:
            raise ValueError("leverage_epsilon must be positive")
        if event_delta_norm_cap <= 0.0:
            raise ValueError("event_delta_norm_cap must be positive")
        super().__init__(
            config,
            geometry_epsilon=geometry_epsilon,
            capture_deep=capture_deep,
        )
        self.arm = ARM_ALIASES[arm]
        self.arm_id = ARM_IDS[self.arm]
        self.case_id = str(case_id)
        if not self.case_id:
            raise ValueError("case_id must not be empty")
        self.model_seed = int(self.config.seed)
        self.probe_mode = probe_mode
        self.route_seed = int(route_seed)
        self.route_capacity = int(route_capacity)
        self.leverage_epsilon = float(leverage_epsilon)
        self.event_delta_norm_cap = float(event_delta_norm_cap)
        self.absolute_control_norm_cap = min(
            float(self.config.max_control_norm),
            DEFAULT_ABSOLUTE_CONTROL_NORM_CAP,
        )
        self.gold_steps_by_source = {
            int(source): tuple(int(step) for step in steps)
            for source, steps in (gold_steps_by_source or {}).items()
        }
        self._route_plans: list[RoutePlan] = []
        self._route_plan_by_source: dict[int, RoutePlan] = {}
        self._online_probes: list[dict[str, Any]] = []
        self._revision_policy_records: list[dict[str, Any]] = []
        self._committed_controls: torch.Tensor | None = None
        self._revision_attempt_count = 0
        self._active_plan: RoutePlan | None = None
        self._accounting: dict[str, Any] = {}

    @property
    def route_plans(self) -> tuple[RoutePlan, ...]:
        return tuple(self._route_plans)

    @property
    def accounting(self) -> dict[str, Any]:
        return json.loads(json.dumps(self._accounting, allow_nan=False))

    def _reset_policy_state(self) -> None:
        self._route_plans = []
        self._route_plan_by_source = {}
        self._online_probes = []
        self._revision_policy_records = []
        self._committed_controls = None
        self._revision_attempt_count = 0
        self._active_plan = None
        self._accounting = {}

    def _current_prefix_controls(
        self, source_step: int, *, device: torch.device, dtype: torch.dtype
    ) -> torch.Tensor:
        controls = torch.zeros(
            source_step + 1,
            self.config.control_dim,
            device=device,
            dtype=dtype,
        )
        if self._committed_controls is not None:
            copied = min(source_step + 1, int(self._committed_controls.shape[0]))
            controls[:copied] = self._committed_controls[:copied].to(
                device=device, dtype=dtype
            )
        return controls

    def _probe_required(self) -> bool:
        return self.probe_mode == "matched" or self.arm in NATIVE_PROBE_ARMS

    def _semantic_rank(
        self, event: Any, candidate_record: Mapping[str, Any]
    ) -> tuple[int, ...]:
        candidates = [
            (int(item["step"]), float(item.get("attention", 0.0)))
            for item in candidate_record.get("candidates", [])
        ]
        if not candidates:
            candidates = [
                (step, float(event.attention_weights[step]))
                for step in range(len(event.attention_weights))
                if float(event.attention_weights[step]) > 0.0
            ]
        return tuple(
            step
            for step, _ in sorted(
                candidates,
                key=lambda item: (-item[1], item[0]),
            )
        )

    def _prefix_leverage_probe(
        self,
        observations: Sequence[Any],
        source_step: int,
        prefix_states: torch.Tensor,
        event: Any,
        candidate_record: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Measure source projection sensitivity using only the current prefix."""

        candidates = tuple(
            int(step) for step in candidate_record.get("candidate_steps", [])
        )
        prefix_observations = observations[: source_step + 1]
        prefix_codec = frozen.StructuredSemanticCodec(self.config)
        prefix_codec.prepare_topics(prefix_observations)
        encoded = prefix_codec.encode_many(prefix_observations)
        controls = self._current_prefix_controls(
            source_step, device=encoded.device, dtype=encoded.dtype
        )
        topic = prefix_codec.topic_vector(observations[source_step].topic)
        direction = self.generator.control_basis.transpose(0, 1) @ topic
        direction_norm = torch.linalg.vector_norm(direction)
        if float(direction_norm.item()) <= 1e-12:
            raise RuntimeError("topic-aligned control direction has zero norm")
        q = self.config.topic_dim
        base_projection = float((prefix_states[source_step, q : 2 * q] @ topic).item())
        desired_sign = 1.0 if event.revision_target >= base_projection else -1.0
        direction = desired_sign * direction / direction_norm
        expected_calls = 2 * sum(source_step - step + 1 for step in candidates)
        calls_before = int(self.generator.step_call_count)
        semantic_by_step = {
            int(item["step"]): {
                "semantic_score": float(item.get("semantic_score", 0.0)),
                "attention": float(item.get("attention", 0.0)),
            }
            for item in candidate_record.get("candidates", [])
        }
        rows: list[dict[str, Any]] = []
        with torch.no_grad():
            for candidate_step in candidates:
                initial_state = (
                    None
                    if candidate_step == 0
                    else prefix_states[candidate_step - 1].detach()
                )
                plus_controls = controls[candidate_step : source_step + 1].clone()
                minus_controls = plus_controls.clone()
                plus_controls[0] += self.leverage_epsilon * direction
                minus_controls[0] -= self.leverage_epsilon * direction
                encoded_suffix = encoded[candidate_step : source_step + 1]
                plus_states = self.generator.rollout(
                    encoded_suffix,
                    plus_controls,
                    initial_state=initial_state,
                )
                minus_states = self.generator.rollout(
                    encoded_suffix,
                    minus_controls,
                    initial_state=initial_state,
                )
                source_derivative = (plus_states[-1] - minus_states[-1]) / (
                    2.0 * self.leverage_epsilon
                )
                belief_derivative = float(
                    (
                        (plus_states[-1, q : 2 * q] - minus_states[-1, q : 2 * q])
                        @ topic
                    ).item()
                    / (2.0 * self.leverage_epsilon)
                )
                aligned = desired_sign * belief_derivative
                semantic = semantic_by_step.get(candidate_step, {})
                rows.append(
                    {
                        "source_step": int(source_step),
                        "candidate_step": int(candidate_step),
                        "semantic_score": float(semantic.get("semantic_score", 0.0)),
                        "attention": float(semantic.get("attention", 0.0)),
                        "control_direction": _tensor_payload(direction),
                        "source_belief_derivative": belief_derivative,
                        "target_aligned_source_belief_derivative": aligned,
                        "source_state_derivative_norm": float(
                            torch.linalg.vector_norm(source_derivative).item()
                        ),
                        "control_leverage": aligned,
                    }
                )
        actual_calls = int(self.generator.step_call_count) - calls_before
        if actual_calls != expected_calls:
            raise AssertionError(
                "prefix leverage generator accounting mismatch: "
                f"expected={expected_calls} actual={actual_calls}"
            )
        return {
            "source_step": int(source_step),
            "performed": True,
            "method": "prefix_only_centered_finite_difference_topic_aligned_control",
            "metric": "target_aligned_event_source_belief_projection_derivative",
            "epsilon": self.leverage_epsilon,
            "candidate_steps": list(candidates),
            "probe_horizon_step": int(source_step),
            "prefix_observation_count": len(prefix_observations),
            "max_observation_step_read": int(source_step),
            "future_steps_read": 0,
            "generator_step_calls": actual_calls,
            "expected_generator_step_calls": expected_calls,
            "generator_accounting_ok": actual_calls == expected_calls,
            "base_source_projection": base_projection,
            "desired_sign": desired_sign,
            "decision_control_l2": float(torch.linalg.vector_norm(controls).item()),
            "prior_branch_revision_count": self._revision_attempt_count,
            "rows": rows,
        }

    def _leverage_rank(
        self,
        candidates: Sequence[int],
        probe: Mapping[str, Any] | None,
        semantic_rank: Sequence[int],
    ) -> tuple[int, ...]:
        if probe is None:
            return ()
        values = {
            int(row["candidate_step"]): float(row["control_leverage"])
            for row in probe.get("rows", [])
        }
        return tuple(
            sorted(
                (int(step) for step in candidates),
                key=lambda step: (
                    -values.get(step, -math.inf),
                    step,
                ),
            )
        )

    def _counter_based_random_order(
        self,
        candidates: Sequence[int],
        *,
        event_ordinal: int,
        source_step: int,
    ) -> list[int]:
        """SHA256 counter-mode sampling without replacement.

        The locked seed material is, in order: schema version, case ID, model
        seed, event ordinal, and source step.  The draw counter is appended by
        the declared counter-based algorithm, so execution order and process
        RNG state cannot affect the route.
        """

        remaining = sorted(_ordered_unique([int(step) for step in candidates]))
        output: list[int] = []
        counter = 0
        while remaining:
            material = "|".join(
                (
                    SCHEMA_VERSION,
                    self.case_id,
                    str(self.model_seed),
                    str(event_ordinal),
                    str(source_step),
                    str(counter),
                )
            ).encode("utf-8")
            draw = int.from_bytes(hashlib.sha256(material).digest()[:8], "big")
            output.append(remaining.pop(draw % len(remaining)))
            counter += 1
        return output

    def _build_route_plan(
        self,
        *,
        source_step: int,
        candidate_steps: Sequence[int],
        semantic_rank: Sequence[int],
        leverage_rank: Sequence[int],
        probe: Mapping[str, Any] | None,
        prefix_states: torch.Tensor,
        prefix_controls: torch.Tensor,
    ) -> RoutePlan:
        candidates = _ordered_unique([int(step) for step in candidate_steps])
        if not candidates:
            raise AssertionError("detected event has no eligible route candidates")
        semantic = _ordered_unique(
            [step for step in semantic_rank if step in candidates] + candidates
        )
        leverage = _ordered_unique(
            [step for step in leverage_rank if step in candidates]
        )
        gold = _ordered_unique(
            [
                step
                for step in self.gold_steps_by_source.get(source_step, ())
                if step in candidates
            ]
        )
        capacity = min(self.route_capacity, len(candidates))
        event_ordinal = self._revision_attempt_count

        if self.arm == "S2":
            controls = semantic[:capacity]
            objective = [semantic[0]]
        elif self.arm == "L2":
            controls = _ordered_unique(leverage + semantic + candidates)[:capacity]
            objective = [controls[0]]
        elif self.arm == "D2":
            anchor = semantic[0]
            controls = _ordered_unique([anchor] + leverage + semantic + candidates)[
                :capacity
            ]
            objective = [anchor]
        elif self.arm == "SR2":
            anchor = semantic[0]
            remaining = [step for step in candidates if step != anchor]
            shuffled = self._counter_based_random_order(
                remaining,
                event_ordinal=event_ordinal,
                source_step=source_step,
            )
            controls = _ordered_unique([anchor] + shuffled + semantic + candidates)[
                :capacity
            ]
            objective = [anchor]
        elif self.arm == "G2":
            if not gold:
                raise ValueError(
                    f"G2 requires an eligible gold step at source {source_step}"
                )
            anchor = gold[0]
            controls = _ordered_unique([anchor] + leverage + semantic + candidates)[
                :capacity
            ]
            objective = [anchor]
        else:  # pragma: no cover - constructor validation makes this unreachable.
            raise AssertionError(self.arm)

        if len(controls) != capacity or len(set(controls)) != capacity:
            raise AssertionError("route planner failed to fill distinct control slots")
        if not objective or any(step not in controls for step in objective):
            raise AssertionError("objective anchors must be a non-empty control subset")
        probe_calls = int(probe["generator_step_calls"]) if probe else 0
        if self.probe_mode == "matched":
            replay_floor = min(candidates)
            replay_policy = "matched_minimum_eligible_step"
        else:
            replay_floor = min(controls)
            replay_policy = "native_minimum_selected_control_step"
        return RoutePlan(
            arm=self.arm,
            source_step=int(source_step),
            objective_anchor_steps=tuple(sorted(objective)),
            control_steps=tuple(sorted(controls)),
            replay_floor=replay_floor,
            candidate_steps=tuple(candidates),
            semantic_rank=tuple(semantic),
            leverage_rank=tuple(leverage),
            gold_steps=tuple(gold),
            probe_mode=self.probe_mode,
            probe_performed=probe is not None,
            probe_used_for_routing=self.arm in NATIVE_PROBE_ARMS,
            online_probe_generator_step_calls=probe_calls,
            decision_state_fingerprint=_tensor_fingerprint(prefix_states),
            decision_control_fingerprint=_tensor_fingerprint(prefix_controls),
            capacity_requested=self.route_capacity,
            capacity_used=capacity,
            arm_id=self.arm_id,
            case_id=self.case_id,
            model_seed=self.model_seed,
            event_ordinal=event_ordinal,
            replay_policy=replay_policy,
        )

    def _detect_event(
        self,
        observations: Sequence[Any],
        source_step: int,
        prefix_states: torch.Tensor,
        active_prior: Any,
    ) -> Any:
        semantic_event = super()._detect_event(
            observations,
            source_step,
            prefix_states,
            active_prior,
        )
        if semantic_event is None:
            return None
        candidate_record = self._event_candidates[-1]
        candidate_record["semantic_selected_steps"] = list(semantic_event.target_steps)
        if self._revision_attempt_count >= self.config.max_events:
            candidate_record["policy_status"] = "revision_budget_exhausted"
            candidate_record["policy_selected_steps"] = list(
                semantic_event.target_steps
            )
            return semantic_event

        prefix_controls = self._current_prefix_controls(
            source_step,
            device=prefix_states.device,
            dtype=prefix_states.dtype,
        )
        probe = None
        if self._probe_required():
            probe = self._prefix_leverage_probe(
                observations,
                source_step,
                prefix_states,
                semantic_event,
                candidate_record,
            )
            self._online_probes.append(probe)
        else:
            self._online_probes.append(
                {
                    "source_step": int(source_step),
                    "performed": False,
                    "method": None,
                    "metric": (
                        "target_aligned_event_source_belief_projection_derivative"
                    ),
                    "epsilon": self.leverage_epsilon,
                    "candidate_steps": list(candidate_record["candidate_steps"]),
                    "probe_horizon_step": int(source_step),
                    "prefix_observation_count": int(source_step + 1),
                    "max_observation_step_read": int(source_step),
                    "future_steps_read": 0,
                    "generator_step_calls": 0,
                    "expected_generator_step_calls": 0,
                    "generator_accounting_ok": True,
                    "decision_control_l2": float(
                        torch.linalg.vector_norm(prefix_controls).item()
                    ),
                    "prior_branch_revision_count": self._revision_attempt_count,
                    "rows": [],
                    "skip_reason": "native_policy_does_not_consume_leverage",
                }
            )
        semantic_rank = self._semantic_rank(semantic_event, candidate_record)
        leverage_rank = self._leverage_rank(
            candidate_record["candidate_steps"],
            probe,
            semantic_rank,
        )
        plan = self._build_route_plan(
            source_step=source_step,
            candidate_steps=candidate_record["candidate_steps"],
            semantic_rank=semantic_rank,
            leverage_rank=leverage_rank,
            probe=probe,
            prefix_states=prefix_states,
            prefix_controls=prefix_controls,
        )
        self._route_plans.append(plan)
        self._route_plan_by_source[source_step] = plan
        candidate_record["policy_status"] = "planned"
        candidate_record["policy_arm"] = self.arm
        candidate_record["objective_anchor_steps"] = list(plan.objective_anchor_steps)
        candidate_record["policy_selected_steps"] = list(plan.control_steps)
        candidate_record["common_replay_floor"] = plan.replay_floor
        candidate_record["online_probe_performed"] = plan.probe_performed
        candidate_record["online_probe_generator_step_calls"] = (
            plan.online_probe_generator_step_calls
        )
        return dataclasses.replace(
            semantic_event,
            target_steps=plan.control_steps,
        )

    def _revision_energy(
        self,
        states: torch.Tensor,
        controls_delta: torch.Tensor,
        original_states: torch.Tensor,
        event: Any,
        current_topic: torch.Tensor,
    ) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        plan = self._active_plan or self._route_plan_by_source.get(event.source_step)
        if plan is None:
            raise AssertionError(
                "revision energy evaluated without an active route plan"
            )
        q = self.config.topic_dim
        belief_scalar = states[:, q : 2 * q] @ current_topic
        target = torch.as_tensor(
            event.revision_target,
            device=states.device,
            dtype=states.dtype,
        )
        attention = torch.tensor(
            event.attention_weights,
            device=states.device,
            dtype=states.dtype,
        )
        objective_mask = torch.zeros_like(attention)
        objective_mask[list(plan.objective_anchor_steps)] = 1.0
        objective_attention = attention * objective_mask
        objective_attention = objective_attention / objective_attention.sum().clamp_min(
            1e-8
        )
        target_alignment = (
            objective_attention * (belief_scalar[:-1] - target).square()
        ).sum()
        current_consistency = (belief_scalar[event.source_step] - target).square()
        trajectory_anchor = (
            (states[plan.replay_floor :] - original_states[plan.replay_floor :])
            .square()
            .mean()
        )
        control_l2 = controls_delta[list(plan.control_steps)].square().mean()
        total = (
            self.config.target_alignment_weight * target_alignment
            + self.config.current_consistency_weight * current_consistency
            + self.config.trajectory_anchor_weight * trajectory_anchor
            + self.config.control_l2_weight * control_l2
        )
        terms = {
            "target_alignment": target_alignment,
            "current_consistency": current_consistency,
            "trajectory_anchor": trajectory_anchor,
            "control_l2": control_l2,
        }
        if self.capture_deep and self._deep_current is not None:
            self._deep_current.append(
                {
                    "evaluation_index": len(self._deep_current),
                    "energy": float(total.detach().item()),
                    "energy_terms": {
                        name: float(value.detach().item())
                        for name, value in terms.items()
                    },
                    "states": _tensor_payload(states),
                    "controls_delta": _tensor_payload(controls_delta),
                    "objective_anchor_steps": list(plan.objective_anchor_steps),
                    "control_steps": list(plan.control_steps),
                    "replay_floor": plan.replay_floor,
                }
            )
        return total, terms

    def _project_event_delta_(
        self,
        base_controls: torch.Tensor,
        delta: torch.Tensor,
        mask: torch.Tensor,
    ) -> None:
        """Project onto both the absolute per-step and event-delta trust regions."""

        with torch.no_grad():
            candidate = base_controls + mask * delta
            row_norms = torch.linalg.vector_norm(candidate, dim=-1, keepdim=True)
            row_scale = torch.clamp(
                self.absolute_control_norm_cap / row_norms.clamp_min(1e-12),
                max=1.0,
            )
            absolute_projected = candidate * row_scale
            event_delta = (absolute_projected - base_controls) * mask
            event_norm = torch.linalg.vector_norm(event_delta)
            event_scale = min(
                1.0,
                self.event_delta_norm_cap / max(float(event_norm.item()), 1e-12),
            )
            delta.copy_(event_delta * event_scale)

    def _revise_prefix(
        self,
        observations: Sequence[Any],
        encoded: torch.Tensor,
        base_controls: torch.Tensor,
        event: Any,
    ) -> tuple[torch.Tensor, torch.Tensor, Any]:
        """Run the frozen optimizer with separated roles and a common replay floor."""

        plan = self._route_plan_by_source.get(event.source_step)
        if plan is None:
            raise AssertionError("revision invoked before route planning")
        started = time.perf_counter()
        before_controls_cpu = base_controls.detach().cpu().clone()
        original_states = self.generator.rollout(encoded, base_controls).detach()
        mask = torch.zeros_like(base_controls)
        mask[list(plan.control_steps)] = 1.0
        delta = torch.zeros_like(base_controls, requires_grad=True)
        optimizer = torch.optim.Adam([delta], lr=self.config.revision_lr)
        current_topic = self.codec.topic_vector(observations[event.source_step].topic)
        energy_history: list[float] = []
        grad_norms: list[float] = []
        replay_floor = int(plan.replay_floor)
        deep: list[dict[str, Any]] = []
        self._deep_current = deep if self.capture_deep else None
        self._active_plan = plan

        def replay_suffix(candidate_controls: torch.Tensor) -> torch.Tensor:
            if replay_floor == 0:
                return self.generator.rollout(encoded, candidate_controls)
            unchanged_prefix = original_states[:replay_floor]
            replayed_suffix = self.generator.rollout(
                encoded[replay_floor:],
                candidate_controls[replay_floor:],
                initial_state=unchanged_prefix[-1],
            )
            return torch.cat((unchanged_prefix, replayed_suffix), dim=0)

        best_energy = math.inf
        best_delta = torch.zeros_like(delta)
        terms_before: dict[str, float] = {}
        try:
            for iteration in range(self.config.revision_steps):
                optimizer.zero_grad(set_to_none=True)
                candidate_controls = base_controls + mask * delta
                states = replay_suffix(candidate_controls)
                energy, terms = self._revision_energy(
                    states,
                    mask * delta,
                    original_states,
                    event,
                    current_topic,
                )
                energy_value = float(energy.item())
                scalar_terms = {
                    name: float(value.item()) for name, value in terms.items()
                }
                if iteration == 0:
                    terms_before = scalar_terms
                if energy_value < best_energy:
                    best_energy = energy_value
                    best_delta = delta.detach().clone()
                energy_history.append(energy_value)
                energy.backward()
                if delta.grad is None:
                    raise RuntimeError("revision control did not receive a gradient")
                with torch.no_grad():
                    delta.grad.mul_(mask)
                    grad_norms.append(
                        float(torch.linalg.vector_norm(delta.grad).item())
                    )
                optimizer.step()
                self._project_event_delta_(base_controls, delta, mask)

            with torch.no_grad():
                last_controls = base_controls + mask * delta
                last_states = replay_suffix(last_controls)
                last_energy, _ = self._revision_energy(
                    last_states,
                    mask * delta,
                    original_states,
                    event,
                    current_topic,
                )
                last_energy_value = float(last_energy.item())
                energy_history.append(last_energy_value)
                if last_energy_value < best_energy:
                    best_energy = last_energy_value
                    best_delta = delta.detach().clone()

                energy_before = energy_history[0]
                accepted = best_energy < energy_before - 1e-9
                chosen_delta = best_delta if accepted else torch.zeros_like(best_delta)
                rolled_back = not torch.allclose(chosen_delta, delta.detach())
                final_controls = base_controls + mask * chosen_delta
                final_states = replay_suffix(final_controls)
                final_energy, final_terms = self._revision_energy(
                    final_states,
                    mask * chosen_delta,
                    original_states,
                    event,
                    current_topic,
                )
                final_energy_value = float(final_energy.item())
                terms_after = {
                    name: float(value.item()) for name, value in final_terms.items()
                }
                event_delta = mask * chosen_delta
                event_delta_norm = float(torch.linalg.vector_norm(event_delta).item())
                absolute_row_norms = torch.linalg.vector_norm(final_controls, dim=-1)
                absolute_max = float(absolute_row_norms.max().item())
                if event_delta_norm > self.event_delta_norm_cap + 1e-6:
                    raise AssertionError("event delta exceeded its Frobenius norm cap")
                if absolute_max > self.absolute_control_norm_cap + 1e-6:
                    raise AssertionError("absolute per-step control exceeded its cap")
                target_control_norms = {
                    index: float(absolute_row_norms[index].item())
                    for index in plan.control_steps
                }
                state_delta_norms = [
                    float(value)
                    for value in torch.linalg.vector_norm(
                        final_states - original_states, dim=-1
                    ).tolist()
                ]
                target_controls_before = {
                    index: [float(value) for value in base_controls[index].tolist()]
                    for index in plan.control_steps
                }
                target_controls_after = {
                    index: [float(value) for value in final_controls[index].tolist()]
                    for index in plan.control_steps
                }
                affected_states_before = [
                    [float(value) for value in row]
                    for row in original_states[replay_floor:].tolist()
                ]
                affected_states_after = [
                    [float(value) for value in row]
                    for row in final_states[replay_floor:].tolist()
                ]
        finally:
            self._active_plan = None
            self._deep_current = None

        if deep:
            for index, item in enumerate(deep):
                if index < self.config.revision_steps:
                    item["phase"] = "optimizer_evaluation"
                elif index == self.config.revision_steps:
                    item["phase"] = "last_iterate"
                else:
                    item["phase"] = "committed_checkpoint"
        record = frozen.RevisionRecord(
            event=event,
            energy_before=energy_before,
            energy_after=final_energy_value,
            energy_terms_before=terms_before,
            energy_terms_after=terms_after if accepted else terms_before,
            energy_history=energy_history,
            first_grad_norm=grad_norms[0],
            max_grad_norm=max(grad_norms),
            target_control_norms=target_control_norms,
            state_delta_norms=state_delta_norms,
            target_controls_before=target_controls_before,
            target_controls_after=target_controls_after,
            affected_states_before=affected_states_before,
            affected_states_after=affected_states_after,
            earliest_replay_step=replay_floor,
            replayed_state_steps=(self.config.revision_steps + 2)
            * (event.source_step - replay_floor + 1),
            selected_control_count=len(plan.control_steps),
            accepted=accepted,
            rolled_back=rolled_back,
            backward_calls=self.config.revision_steps,
            wall_time_ms=(time.perf_counter() - started) * 1000.0,
        )
        revised_controls = final_controls.detach()
        self._revision_snapshots.append(
            {
                "source_step": int(event.source_step),
                "controls_before": _tensor_payload(before_controls_cpu),
                "controls_after": _tensor_payload(revised_controls),
                "deep_evaluations": deep,
            }
        )
        self._revision_policy_records.append(
            {
                "source_step": int(event.source_step),
                "objective_anchor_steps": list(plan.objective_anchor_steps),
                "control_steps": list(plan.control_steps),
                "replay_floor": replay_floor,
                "replay_span_steps": event.source_step - replay_floor + 1,
                "prefix_recompute_steps": event.source_step + 1,
                "optimizer_replay_steps": record.replayed_state_steps,
                "event_delta_frobenius_norm": event_delta_norm,
                "event_delta_norm_cap": self.event_delta_norm_cap,
                "absolute_control_norm_max": absolute_max,
                "absolute_control_norm_cap": self.absolute_control_norm_cap,
                "event_delta_cap_ok": (
                    event_delta_norm <= self.event_delta_norm_cap + 1e-6
                ),
                "absolute_control_cap_ok": (
                    absolute_max <= self.absolute_control_norm_cap + 1e-6
                ),
                "accepted": bool(accepted),
                "branch_revision_index": self._revision_attempt_count,
                "branch_local_recomputed": True,
            }
        )
        self._committed_controls = revised_controls.detach().clone()
        self._revision_attempt_count += 1
        return revised_controls.detach(), final_states.detach(), record

    def _build_accounting(self, result: Any) -> dict[str, Any]:
        trajectory_length = len(result.observations)
        base_forward_steps = 2 * trajectory_length
        prefix_recompute = sum(
            int(item["prefix_recompute_steps"])
            for item in self._revision_policy_records
        )
        optimizer_replay = sum(
            int(item["optimizer_replay_steps"])
            for item in self._revision_policy_records
        )
        online_probe = sum(
            int(item["generator_step_calls"])
            for item in self._online_probes
            if bool(item.get("performed", False))
        )
        expected_generator = (
            base_forward_steps + prefix_recompute + optimizer_replay + online_probe
        )
        actual_generator = int(result.generator_step_calls)
        expected_backward = self.config.revision_steps * len(result.revisions)
        actual_backward = int(result.backward_calls)
        core_generator = actual_generator - online_probe
        candidate_count = sum(len(item.candidate_steps) for item in self._route_plans)
        accounting = {
            "base_forward_steps": base_forward_steps,
            "prefix_recompute_steps": prefix_recompute,
            "optimizer_replay_steps": optimizer_replay,
            "online_probe_generator_step_calls": online_probe,
            "route_probe_generator_steps": online_probe,
            "expected_generator_step_calls": expected_generator,
            "actual_generator_step_calls": actual_generator,
            "inclusive_generator_steps": actual_generator,
            "core_generator_steps": core_generator,
            "generator_accounting_ok": actual_generator == expected_generator,
            "expected_backward_calls": expected_backward,
            "actual_backward_calls": actual_backward,
            "optimizer_backward_calls": actual_backward,
            "backward_accounting_ok": actual_backward == expected_backward,
            "replayed_state_steps": optimizer_replay,
            "candidate_count": candidate_count,
            "revision_count": len(result.revisions),
            "detected_event_count": len(result.events) + len(result.suppressed_events),
            "probe_event_count": sum(
                int(bool(item.get("performed", False))) for item in self._online_probes
            ),
            "diagnostic_generator_steps_excluded": True,
        }
        if not accounting["generator_accounting_ok"]:
            raise AssertionError(
                "dual-route generator accounting mismatch: "
                f"expected={expected_generator} actual={actual_generator}"
            )
        if not accounting["backward_accounting_ok"]:
            raise AssertionError(
                "dual-route backward accounting mismatch: "
                f"expected={expected_backward} actual={actual_backward}"
            )
        return accounting

    def run(self, observations: Sequence[Any]) -> Any:
        self._reset_policy_state()
        result = super().run(observations)
        self._accounting = self._build_accounting(result)
        if self.last_trace is None:  # pragma: no cover - observer.run establishes it.
            raise AssertionError("observer did not build a trace")
        self.last_trace["dual_route_policy"] = {
            "schema_version": SCHEMA_VERSION,
            "arm": self.arm,
            "arm_id": self.arm_id,
            "case_id": self.case_id,
            "model_seed": self.model_seed,
            "probe_mode": self.probe_mode,
            "route_capacity": self.route_capacity,
            "leverage_epsilon": self.leverage_epsilon,
            "event_delta_norm_cap": self.event_delta_norm_cap,
            "absolute_per_step_control_norm_cap": self.absolute_control_norm_cap,
            "route_seed": self.route_seed,
            "random_route_seed_material": [
                "schema_version",
                "case_id",
                "model_seed",
                "event_ordinal",
                "source_step",
            ],
            "gold_steps_by_source": {
                str(source): list(steps)
                for source, steps in sorted(self.gold_steps_by_source.items())
            },
            "route_plans": [plan.to_dict() for plan in self._route_plans],
            "online_probes": self._online_probes,
            "revisions": self._revision_policy_records,
            "accounting": self._accounting,
            "sequential_contract": (
                "Every event probes the current branch prefix after all earlier "
                "accepted or rolled-back revision decisions; no route cache is reused."
            ),
            "probe_contract": (
                "Centered finite differences stop at the event source and never "
                "read a future observation, state, or terminal outcome."
            ),
            "matched_contract": (
                "All matched-mode arms pay the same prefix probe, two-slot capacity, "
                "common candidate replay floor, optimizer budget, and norm caps."
            ),
            "replay_contract": (
                "Matched mode replays from the minimum eligible candidate for exact "
                "capacity comparison; native mode replays only from the minimum "
                "selected control step for the natural-cost frontier."
            ),
            "source_sha256": assert_frozen_sources(),
            "claim_boundary": [
                "The online leverage feature is one target-aligned source projection direction, not full controllability.",
                "G2 consumes annotated gold anchors and is a privileged diagnostic, not a deployable policy.",
                "Matched capacity controls software confounds on this toy mechanism; it does not establish external reasoning quality.",
            ],
        }
        self.last_trace["trace_fingerprint"] = observer._trace_fingerprint(
            self.last_trace
        )
        return result


DualRouteEventDrivenBackwardReasoner = DualRoutePolicyReasoner


def run_policy(
    observations: Sequence[Any],
    *,
    config: Any | None = None,
    arm: str,
    case_id: str = "unspecified",
    probe_mode: str = "matched",
    route_seed: int = 0,
    gold_steps_by_source: Mapping[int, Sequence[int]] | None = None,
    capture_deep: bool = False,
) -> observer.InstrumentedSession:
    """Convenience entry point returning the existing v0.2 session contract."""

    engine = DualRoutePolicyReasoner(
        config,
        arm=arm,
        case_id=case_id,
        probe_mode=probe_mode,
        route_seed=route_seed,
        gold_steps_by_source=gold_steps_by_source,
        capture_deep=capture_deep,
    )
    return engine.run_instrumented(
        observations,
        candidate_control_leverage=False,
    )


def _multi_candidate_fixture() -> list[Any]:
    return [
        frozen.Observation("claim", 1.00, "active anchor"),
        frozen.Observation("claim", 0.82, "near confirmation"),
        frozen.Observation("context", 0.10, "intervening context"),
        frozen.Observation("claim", 0.24, "weak same-topic candidate"),
        frozen.Observation("claim", -0.45, "premise shift"),
        frozen.Observation("tail", 0.20, "post-event tail"),
    ]


def _sequential_fixture() -> list[Any]:
    return [
        frozen.Observation("claim", 1.00, "initial anchor"),
        frozen.Observation("claim", 0.82, "first confirmation"),
        frozen.Observation("claim", -0.40, "first shift"),
        frozen.Observation("claim", -0.28, "second confirmation"),
        frozen.Observation("claim", 0.90, "second shift"),
    ]


def _session_fingerprint(result: Any) -> str:
    return result.to_dict(include_states=False)["metrics"][
        "reproducibility_fingerprint"
    ]


def run_self_tests() -> dict[str, Any]:
    """Exercise policy semantics, accounting, matching, and determinism."""

    source_hashes = assert_frozen_sources()
    config = frozen.EBRTConfig(
        seed=17,
        top_k=2,
        revision_steps=4,
        max_events=4,
    )
    observations = _multi_candidate_fixture()
    gold = {4: (0,)}
    matched: dict[str, tuple[DualRoutePolicyReasoner, Any]] = {}
    for arm in ARMS:
        engine = DualRoutePolicyReasoner(
            config,
            arm=arm,
            case_id="multi-candidate-fixture",
            probe_mode="matched",
            route_seed=919,
            gold_steps_by_source=gold,
        )
        result = engine.run(observations)
        if len(engine.route_plans) != 1 or len(result.revisions) != 1:
            raise AssertionError(f"{arm} did not execute exactly one routed revision")
        plan = engine.route_plans[0]
        if plan.capacity_used != 2 or len(plan.control_steps) != 2:
            raise AssertionError(f"{arm} did not use two distinct control slots")
        if plan.replay_floor != 0:
            raise AssertionError(f"{arm} did not use the common candidate floor")
        if plan.replay_policy != "matched_minimum_eligible_step":
            raise AssertionError(f"{arm} recorded the wrong matched replay policy")
        if not plan.probe_performed:
            raise AssertionError(f"matched arm {arm} skipped its charged probe")
        if not engine.accounting["generator_accounting_ok"]:
            raise AssertionError(f"{arm} generator accounting failed")
        policy_revision = engine.last_trace["dual_route_policy"]["revisions"][0]
        if not policy_revision["event_delta_cap_ok"]:
            raise AssertionError(f"{arm} event delta cap failed")
        if not policy_revision["absolute_control_cap_ok"]:
            raise AssertionError(f"{arm} absolute control cap failed")
        probe = engine.last_trace["dual_route_policy"]["online_probes"][0]
        if probe["future_steps_read"] != 0 or probe["probe_horizon_step"] != 4:
            raise AssertionError(f"{arm} prefix probe read beyond its event")
        matched[arm] = (engine, result)

    matched_probe_calls = {
        engine.accounting["online_probe_generator_step_calls"]
        for engine, _ in matched.values()
    }
    matched_total_calls = {
        engine.accounting["actual_generator_step_calls"]
        for engine, _ in matched.values()
    }
    matched_replay_steps = {
        engine.accounting["optimizer_replay_steps"] for engine, _ in matched.values()
    }
    if len(matched_probe_calls) != 1:
        raise AssertionError("matched arms paid different online probe costs")
    if len(matched_total_calls) != 1:
        raise AssertionError("matched arms used different total generator calls")
    if len(matched_replay_steps) != 1:
        raise AssertionError("matched arms used different optimizer replay work")
    objective_expectations = {
        "S2": (matched["S2"][0].route_plans[0].semantic_rank[0],),
        "L2": (matched["L2"][0].route_plans[0].leverage_rank[0],),
        "D2": (matched["D2"][0].route_plans[0].semantic_rank[0],),
        "SR2": (matched["SR2"][0].route_plans[0].semantic_rank[0],),
        "G2": (0,),
    }
    for arm, expected_objective in objective_expectations.items():
        actual_objective = matched[arm][0].route_plans[0].objective_anchor_steps
        if actual_objective != expected_objective:
            raise AssertionError(
                f"{arm} objective definition mismatch: "
                f"expected={expected_objective} actual={actual_objective}"
            )

    native_probe_expectation = {
        "S2": False,
        "L2": True,
        "D2": True,
        "SR2": False,
        "G2": True,
    }
    native: dict[str, DualRoutePolicyReasoner] = {}
    for arm, expected_probe in native_probe_expectation.items():
        engine = DualRoutePolicyReasoner(
            config,
            arm=arm,
            case_id="multi-candidate-fixture",
            probe_mode="native",
            route_seed=919,
            gold_steps_by_source=gold,
        )
        engine.run(observations)
        performed = engine.route_plans[0].probe_performed
        if performed is not expected_probe:
            raise AssertionError(f"native probe policy mismatch arm={arm}: {performed}")
        native_plan = engine.route_plans[0]
        matched_plan = matched[arm][0].route_plans[0]
        if native_plan.objective_anchor_steps != matched_plan.objective_anchor_steps:
            raise AssertionError(f"native mode changed {arm} objective selection")
        if native_plan.control_steps != matched_plan.control_steps:
            raise AssertionError(f"native mode changed {arm} control selection")
        if native_plan.replay_floor != min(native_plan.control_steps):
            raise AssertionError(f"native mode did not use {arm}'s selected floor")
        if native_plan.replay_policy != "native_minimum_selected_control_step":
            raise AssertionError(f"{arm} recorded the wrong native replay policy")
        if not engine.accounting["generator_accounting_ok"]:
            raise AssertionError(f"native {arm} generator accounting failed")
        native[arm] = engine
    if (
        native["L2"].route_plans[0].replay_floor
        == matched["L2"][0].route_plans[0].replay_floor
    ):
        raise AssertionError("native L2 fixture did not exercise natural replay cost")

    first_engine, first_result = matched["D2"]
    repeat_engine = DualRoutePolicyReasoner(
        config,
        arm="D2",
        case_id="multi-candidate-fixture",
        probe_mode="matched",
        route_seed=919,
        gold_steps_by_source=gold,
    )
    repeat_result = repeat_engine.run(observations)
    if _session_fingerprint(first_result) != _session_fingerprint(repeat_result):
        raise AssertionError("D2 session fingerprint is not deterministic")
    if [item.to_dict() for item in first_engine.route_plans] != [
        item.to_dict() for item in repeat_engine.route_plans
    ]:
        raise AssertionError("D2 route plans are not deterministic")
    first_trace_fingerprint = first_engine.last_trace["trace_fingerprint"]
    repeat_trace_fingerprint = repeat_engine.last_trace["trace_fingerprint"]
    if first_trace_fingerprint != repeat_trace_fingerprint:
        raise AssertionError("D2 full policy trace fingerprint is not deterministic")

    random_by_case: dict[str, tuple[int, ...]] = {}
    for case_id in ("random-case-a", "random-case-b"):
        engine = DualRoutePolicyReasoner(
            config,
            arm="SR2",
            case_id=case_id,
            probe_mode="matched",
            route_seed=1,
            gold_steps_by_source=gold,
        )
        engine.run(observations)
        plan = engine.route_plans[0]
        if plan.case_id != case_id or plan.model_seed != config.seed:
            raise AssertionError("SR2 plan lost locked case/model seed material")
        random_by_case[case_id] = plan.control_steps
    for case_id in reversed(tuple(random_by_case)):
        engine = DualRoutePolicyReasoner(
            config,
            arm="SR2",
            case_id=case_id,
            probe_mode="matched",
            route_seed=999,
            gold_steps_by_source=gold,
        )
        engine.run(observations)
        if engine.route_plans[0].control_steps != random_by_case[case_id]:
            raise AssertionError(
                "SR2 route changed with execution order or legacy route_seed"
            )

    sequential = _sequential_fixture()
    sequential_engine = DualRoutePolicyReasoner(
        config,
        arm="D2",
        case_id="sequential-fixture",
        probe_mode="matched",
        route_seed=313,
        gold_steps_by_source={2: (0,), 4: (2,)},
    )
    sequential_result = sequential_engine.run(sequential)
    if len(sequential_engine.route_plans) != 2:
        raise AssertionError("sequential fixture did not plan both events")
    if len(sequential_result.revisions) != 2:
        raise AssertionError("sequential fixture did not revise both events")
    second_plan = sequential_engine.route_plans[1]
    zero_controls = torch.zeros(
        second_plan.source_step + 1,
        config.control_dim,
    )
    if second_plan.decision_control_fingerprint == _tensor_fingerprint(zero_controls):
        raise AssertionError("second event did not inherit its branch-local controls")
    second_revision = sequential_engine.last_trace["dual_route_policy"]["revisions"][1]
    if second_revision["branch_revision_index"] != 1:
        raise AssertionError("second event was not recomputed after the first branch")
    if not sequential_engine.accounting["generator_accounting_ok"]:
        raise AssertionError("sequential generator accounting failed")

    stable_engine = DualRoutePolicyReasoner(
        config,
        arm="S2",
        case_id="stable-fixture",
        probe_mode="matched",
    )
    stable_result = stable_engine.run(frozen.stable_scenario())
    if stable_result.events or stable_engine.route_plans:
        raise AssertionError("stable fixture unexpectedly routed an event")
    if stable_engine.accounting["online_probe_generator_step_calls"] != 0:
        raise AssertionError("stable fixture paid an unnecessary probe")
    if not torch.equal(
        stable_result.controls, torch.zeros_like(stable_result.controls)
    ):
        raise AssertionError("stable fixture changed a control")

    return {
        "status": "PASS",
        "schema_version": SCHEMA_VERSION,
        "source_sha256": source_hashes,
        "checks": [
            "all five matched K=2 arms execute one charged prefix-only probe",
            "objective anchors, control steps, and common replay floor are separated",
            "matched arms share exact probe, replay, and total generator work",
            "native mode probes only L2, D2, and G2",
            "native mode preserves route semantics and replays from selected controls",
            "event-delta Frobenius and absolute per-step control caps hold",
            "route plans and committed sessions are deterministic",
            "full policy trace fingerprints exclude timing and repeat exactly",
            "SR2 uses locked case/model/event SHA counter sampling independent of execution order",
            "sequential events recompute from branch-local committed controls",
            "strict generator and backward accounting closes",
            "stable no-event execution remains zero-control and probe-free",
        ],
        "matched_generator_step_calls": next(iter(matched_total_calls)),
        "matched_online_probe_step_calls": next(iter(matched_probe_calls)),
        "sequential_generator_step_calls": sequential_engine.accounting[
            "actual_generator_step_calls"
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="EBRT v0.3 capacity-matched dual-route policy"
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run deterministic policy and accounting checks",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.self_test:
        build_parser().print_help()
        return 0
    print(json.dumps(run_self_tests(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
