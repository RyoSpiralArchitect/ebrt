#!/usr/bin/env python3
"""Counterfactual instrumentation for the frozen EBRT v0.1 mechanism.

This module is an observer, not a replacement reasoning implementation.  It
subclasses the SHA-pinned v0.1 engine, records the inputs and outputs of existing
private hooks, and builds exact event-local mirrors from ``RevisionRecord``.
The committed execution path, selected route, controls, states, and counters are
left unchanged. Optional source-projection leverage probes run on a separate cloned
diagnostic engine and are reported outside execution counters.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import torch
import torch.nn.functional as F

from semantic_adapter_v0_2 import AdapterProvenance, StructuredOracleAdapter


SCHEMA_VERSION = "ebrt-instrumentation-v0.2"
EXPECTED_MONOLITH_SHA256 = (
    "b1702f2868839d989cc3a9321d227436a23c3dad6cc86483edee9d5dbab3a529"
)
MONOLITH_PATH = Path(__file__).with_name("ebrt_monolith_v0_1.py")
DEFAULT_GEOMETRY_EPSILON = 1e-8


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_frozen_monolith(path: Path = MONOLITH_PATH) -> str:
    actual = _sha256(path)
    if actual != EXPECTED_MONOLITH_SHA256:
        raise RuntimeError(
            "frozen v0.1 monolith SHA256 mismatch: "
            f"expected={EXPECTED_MONOLITH_SHA256} actual={actual} path={path}"
        )
    return actual


# Verify before importing the implementation whose behavior is being observed.
assert_frozen_monolith()
import ebrt_monolith_v0_1 as frozen  # noqa: E402


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


def _float_list(tensor: torch.Tensor) -> list[Any]:
    return tensor.detach().cpu().tolist()


def _vector_norm(tensor: torch.Tensor) -> float:
    return float(torch.linalg.vector_norm(tensor).item())


def trajectory_geometry(
    states: torch.Tensor | Sequence[Sequence[float]],
    *,
    epsilon: float = DEFAULT_GEOMETRY_EPSILON,
) -> dict[str, Any]:
    """Compute aligned finite-difference geometry for one state block.

    ``velocity[0]`` uses the documented zero initial state.  Acceleration and
    turn angle at step zero are undefined.  A near-zero current velocity also
    makes normalized acceleration and turn angle undefined; JSON uses ``null``.
    """

    if epsilon <= 0.0:
        raise ValueError("geometry epsilon must be positive")
    tensor = torch.as_tensor(states).detach().cpu()
    if tensor.ndim != 2:
        raise ValueError("states must have shape [T, D]")
    if not torch.isfinite(tensor).all():
        raise ValueError("states must be finite")
    length, width = tensor.shape
    if length == 0:
        return {
            "states": [],
            "state_norm": [],
            "velocity": [],
            "speed": [],
            "acceleration": [],
            "acceleration_norm": [],
            "normalized_acceleration": [],
            "turn_angle": [],
            "near_zero_speed": [],
            "epsilon": epsilon,
        }

    zero = torch.zeros(width, dtype=tensor.dtype)
    velocities = torch.empty_like(tensor)
    velocities[0] = tensor[0] - zero
    if length > 1:
        velocities[1:] = tensor[1:] - tensor[:-1]
    speeds = torch.linalg.vector_norm(velocities, dim=-1)
    accelerations: list[list[float] | None] = [None]
    acceleration_norms: list[float | None] = [None]
    normalized: list[float | None] = [None]
    angles: list[float | None] = [None]
    near_zero = [bool(value <= epsilon) for value in speeds.tolist()]

    for index in range(1, length):
        acceleration = velocities[index] - velocities[index - 1]
        acceleration_norm = _vector_norm(acceleration)
        accelerations.append([float(value) for value in acceleration.tolist()])
        acceleration_norms.append(acceleration_norm)
        if near_zero[index]:
            normalized.append(None)
        else:
            normalized.append(acceleration_norm / float(speeds[index].item()))
        if near_zero[index - 1] or near_zero[index]:
            angles.append(None)
        else:
            cosine = float(
                torch.dot(velocities[index - 1], velocities[index])
                / (speeds[index - 1] * speeds[index])
            )
            angles.append(math.acos(max(-1.0, min(1.0, cosine))))

    return {
        "states": _float_list(tensor),
        "state_norm": [
            float(value) for value in torch.linalg.vector_norm(tensor, dim=-1).tolist()
        ],
        "velocity": _float_list(velocities),
        "speed": [float(value) for value in speeds.tolist()],
        "acceleration": accelerations,
        "acceleration_norm": acceleration_norms,
        "normalized_acceleration": normalized,
        "turn_angle": angles,
        "near_zero_speed": near_zero,
        "epsilon": epsilon,
    }


def state_geometry(
    states: torch.Tensor | Sequence[Sequence[float]],
    *,
    topic_dim: int,
    epsilon: float = DEFAULT_GEOMETRY_EPSILON,
) -> dict[str, Any]:
    tensor = torch.as_tensor(states).detach().cpu()
    if tensor.ndim != 2 or tensor.shape[1] != 3 * topic_dim:
        raise ValueError("states must have shape [T, 3 * topic_dim]")
    blocks = {
        "full": tensor,
        "topic": tensor[:, :topic_dim],
        "belief": tensor[:, topic_dim : 2 * topic_dim],
        "context": tensor[:, 2 * topic_dim :],
    }
    return {
        name: trajectory_geometry(values, epsilon=epsilon)
        for name, values in blocks.items()
    }


def _trace_fingerprint(trace: Mapping[str, Any]) -> str:
    material = dict(trace)
    material.pop("trace_fingerprint", None)
    return _fingerprint(material)


@dataclass
class InstrumentedSession:
    """Frozen execution result paired with a deterministic v0.2 trace."""

    result: Any
    trace: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return self.trace


class InstrumentedEventDrivenBackwardReasoner(frozen.EventDrivenBackwardReasoner):
    """Observer-compatible subclass of the frozen v0.1 reasoner."""

    def __init__(
        self,
        config: Any | None = None,
        *,
        geometry_epsilon: float = DEFAULT_GEOMETRY_EPSILON,
        capture_deep: bool = False,
    ) -> None:
        super().__init__(config)
        if geometry_epsilon <= 0.0:
            raise ValueError("geometry_epsilon must be positive")
        self.geometry_epsilon = float(geometry_epsilon)
        self.capture_deep = bool(capture_deep)
        self.last_trace: dict[str, Any] | None = None
        self._event_candidates: list[dict[str, Any]] = []
        self._revision_snapshots: list[dict[str, Any]] = []
        self._deep_current: list[dict[str, Any]] | None = None

    def _detect_event(
        self,
        observations: Sequence[Any],
        source_step: int,
        prefix_states: torch.Tensor,
        active_prior: Any,
    ) -> Any:
        current = observations[source_step]
        topic = current.topic.strip().lower()
        eligible = [
            index
            for index in range(source_step)
            if observations[index].topic.strip().lower() == topic
        ]
        prior_step = next(
            (
                index
                for index in range(source_step)
                if observations[index] is active_prior
            ),
            None,
        )
        event_score = (
            abs(current.stance - active_prior.stance)
            * 0.5
            * min(current.confidence, active_prior.confidence)
            * current.revision_cue
        )
        q = self.config.topic_dim
        decomposed: list[dict[str, Any]] = []
        logits: list[torch.Tensor] = []
        for index in eligible:
            prior = observations[index]
            similarity = F.cosine_similarity(
                prefix_states[source_step, :q].unsqueeze(0),
                prefix_states[index, :q].unsqueeze(0),
            ).squeeze(0)
            contradiction = (
                abs(current.stance - prior.stance)
                * 0.5
                * min(current.confidence, prior.confidence)
                * current.revision_cue
            )
            recency = index / max(1, source_step - 1)
            logit = (
                similarity / self.config.attention_temperature
                + self.config.attention_contradiction_gain * contradiction
                + self.config.attention_recency_gain * recency
            )
            logits.append(logit)
            decomposed.append(
                {
                    "step": index,
                    "topic_similarity": float(similarity.item()),
                    "contradiction": float(contradiction),
                    "recency": float(recency),
                    "logit": float(logit.item()),
                    "semantic_score": float(logit.item()),
                }
            )
        if logits:
            attention = torch.softmax(torch.stack(logits), dim=0).tolist()
            for item, weight in zip(decomposed, attention):
                item["attention"] = float(weight)

        event = super()._detect_event(
            observations, source_step, prefix_states, active_prior
        )
        selected = set(event.target_steps if event is not None else ())
        for item in decomposed:
            item["selected"] = item["step"] in selected
        self._event_candidates.append(
            {
                "source_step": source_step,
                "topic": current.topic,
                "prior_step": prior_step,
                "prior_stance": float(active_prior.stance),
                "prior_confidence": float(active_prior.confidence),
                "current_stance": float(current.stance),
                "current_confidence": float(current.confidence),
                "revision_cue": float(current.revision_cue),
                "event_score": float(event_score),
                "event_threshold": float(self.config.event_threshold),
                "eligible_steps": eligible,
                "candidate_steps": eligible,
                "candidates": decomposed,
                "detected": event is not None,
                "selected_steps": list(event.target_steps) if event else [],
                "attention_weights": list(event.attention_weights) if event else [],
                "routing_evaluated_by_core": event is not None,
                "decomposition_note": (
                    "Exact core route decomposition"
                    if event is not None
                    else "Observer-only counterfactual decomposition; the core returned before routing"
                ),
            }
        )
        return event

    def _revision_energy(
        self,
        states: torch.Tensor,
        controls_delta: torch.Tensor,
        original_states: torch.Tensor,
        event: Any,
        current_topic: torch.Tensor,
    ) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        energy, terms = super()._revision_energy(
            states, controls_delta, original_states, event, current_topic
        )
        if self.capture_deep and self._deep_current is not None:
            self._deep_current.append(
                {
                    "evaluation_index": len(self._deep_current),
                    "energy": float(energy.detach().item()),
                    "energy_terms": {
                        name: float(value.detach().item())
                        for name, value in terms.items()
                    },
                    "states": _float_list(states),
                    "controls_delta": _float_list(controls_delta),
                }
            )
        return energy, terms

    def _revise_prefix(
        self,
        observations: Sequence[Any],
        encoded: torch.Tensor,
        base_controls: torch.Tensor,
        event: Any,
    ) -> tuple[torch.Tensor, torch.Tensor, Any]:
        deep: list[dict[str, Any]] = []
        self._deep_current = deep if self.capture_deep else None
        before = base_controls.detach().cpu().clone()
        revised_controls, revised_states, record = super()._revise_prefix(
            observations, encoded, base_controls, event
        )
        self._deep_current = None
        if deep:
            for index, item in enumerate(deep):
                if index < self.config.revision_steps:
                    item["phase"] = "optimizer_evaluation"
                elif index == self.config.revision_steps:
                    item["phase"] = "last_iterate"
                else:
                    item["phase"] = "committed_checkpoint"
        self._revision_snapshots.append(
            {
                "source_step": int(event.source_step),
                "controls_before": _float_list(before),
                "controls_after": _float_list(revised_controls),
                "deep_evaluations": deep,
            }
        )
        return revised_controls, revised_states, record

    def run(self, observations: Sequence[Any]) -> Any:
        self._event_candidates = []
        self._revision_snapshots = []
        self.last_trace = None
        result = super().run(observations)
        self.last_trace = self._build_trace(result, adapter_provenance=None)
        return result

    def run_instrumented(
        self,
        observations: Sequence[Any],
        *,
        candidate_control_leverage: bool = False,
        leverage_epsilon: float = 1e-3,
        adapter_provenance: AdapterProvenance | Mapping[str, Any] | None = None,
    ) -> InstrumentedSession:
        result = self.run(observations)
        if self.last_trace is None:  # pragma: no cover - run() establishes this.
            raise AssertionError("instrumentation trace was not built")
        # ``run()`` already performed the separate-engine terminal diagnostics.
        # Reuse that pure-data trace so adapter provenance does not double replay
        # work.  A JSON round trip is also a schema-serializability assertion.
        trace = json.loads(json.dumps(self.last_trace, allow_nan=False))
        if adapter_provenance is None:
            trace["adapter_provenance"] = None
        elif isinstance(adapter_provenance, AdapterProvenance):
            trace["adapter_provenance"] = adapter_provenance.to_dict()
        else:
            trace["adapter_provenance"] = dict(adapter_provenance)
        counters_before = (
            result.generator_step_calls,
            result.backward_calls,
            result.decode_call_count,
            result.core_hash_after,
        )
        if candidate_control_leverage:
            leverage = self._control_leverage_probe(
                result, epsilon=float(leverage_epsilon)
            )
            trace["candidate_control_leverage"] = leverage
            lookup = {
                (row["source_step"], row["candidate_step"]): row
                for row in leverage["candidates"]
            }
            for event in trace["event_candidates"]:
                for candidate in event["candidates"]:
                    probe = lookup.get((event["source_step"], candidate["step"]))
                    if probe is not None:
                        candidate["control_leverage"] = probe["control_leverage"]
            counters_after = (
                result.generator_step_calls,
                result.backward_calls,
                result.decode_call_count,
                result.core_hash_after,
            )
            if counters_before != counters_after:
                raise AssertionError("diagnostic probe contaminated execution counters")
        trace["trace_fingerprint"] = _trace_fingerprint(trace)
        self.last_trace = trace
        return InstrumentedSession(result=result, trace=trace)

    def _build_trace(
        self,
        result: Any,
        *,
        adapter_provenance: AdapterProvenance | Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        committed = {event.source_step for event in result.events}
        suppressed = {event.source_step for event in result.suppressed_events}
        event_candidates = json.loads(json.dumps(self._event_candidates))
        for item in event_candidates:
            source = item["source_step"]
            item["status"] = (
                "committed"
                if source in committed
                else "suppressed"
                if source in suppressed
                else "not_detected"
            )

        terminal_diagnostics, diagnostic_meta = self._terminal_diagnostics(result)
        mirrors: list[dict[str, Any]] = []
        for index, (revision, snapshot) in enumerate(
            zip(result.revisions, self._revision_snapshots)
        ):
            event = revision.event
            before_states = torch.tensor(revision.affected_states_before)
            after_states = torch.tensor(revision.affected_states_after)
            delta_states = after_states - before_states
            before_controls = torch.tensor(snapshot["controls_before"])
            after_controls = torch.tensor(snapshot["controls_after"])
            control_delta = after_controls - before_controls
            selected_delta = control_delta[list(event.target_steps)]
            state_norms = torch.linalg.vector_norm(delta_states, dim=-1)
            control_norms = torch.linalg.vector_norm(selected_delta, dim=-1)
            candidate = next(
                (
                    item
                    for item in event_candidates
                    if item["source_step"] == event.source_step
                ),
                None,
            )
            terminal = terminal_diagnostics[index]
            target_local_norms = {
                str(target): float(
                    state_norms[target - revision.earliest_replay_step].item()
                )
                for target in event.target_steps
            }
            mirror = {
                "event_index": index,
                "source_step": int(event.source_step),
                "target_steps": list(event.target_steps),
                "candidate_steps": list(
                    candidate["candidate_steps"] if candidate else []
                ),
                "attention_weights": list(event.attention_weights),
                "earliest_replay_step": int(revision.earliest_replay_step),
                "local_steps": list(
                    range(revision.earliest_replay_step, event.source_step + 1)
                ),
                "replay_span_steps": int(
                    event.source_step - revision.earliest_replay_step + 1
                ),
                "replay_distance": int(
                    event.source_step - revision.earliest_replay_step
                ),
                "route_distances": {
                    str(target): int(event.source_step - target)
                    for target in event.target_steps
                },
                "mirror_states": _float_list(before_states),
                "revised_states": _float_list(after_states),
                "delta_states": _float_list(delta_states),
                "controls_before": snapshot["controls_before"],
                "controls_after": snapshot["controls_after"],
                "target_controls_before": revision.target_controls_before,
                "target_controls_after": revision.target_controls_after,
                "mirror_separation": [float(value) for value in state_norms.tolist()],
                "target_state_delta_l2": target_local_norms,
                "magnitudes": {
                    "control_delta_l2": _vector_norm(selected_delta),
                    "control_delta_per_target": {
                        str(target): float(value)
                        for target, value in zip(
                            event.target_steps, control_norms.tolist()
                        )
                    },
                    "state_delta_l2": _vector_norm(delta_states),
                    "state_delta_max": float(state_norms.max().item()),
                    "state_delta_area": float(state_norms.sum().item()),
                    "source_state_delta_l2": float(state_norms[-1].item()),
                    "terminal_state_delta_l2": terminal["terminal_state_delta_l2"],
                },
                "source_target_projection_gain": terminal[
                    "source_target_projection_gain"
                ],
                "terminal_target_projection_gain": terminal[
                    "terminal_target_projection_gain"
                ],
                "propagation_survival_ratio": terminal["propagation_survival_ratio"],
                "decay_distance": terminal["decay_distance"],
                "propagation_separation": terminal["separation_curve"],
                "unrelated_state_leakage_max": terminal["unrelated_state_leakage_max"],
                "energy_before": float(revision.energy_before),
                "energy_after": float(revision.energy_after),
                "energy_drop": float(revision.energy_before - revision.energy_after),
                "energy_terms_before": dict(revision.energy_terms_before),
                "energy_terms_after": dict(revision.energy_terms_after),
                "energy_history": list(revision.energy_history),
                "first_grad_norm": float(revision.first_grad_norm),
                "max_grad_norm": float(revision.max_grad_norm),
                "accepted_checkpoint": int(
                    min(
                        range(len(revision.energy_history)),
                        key=revision.energy_history.__getitem__,
                    )
                ),
                "accepted": bool(revision.accepted),
                "rolled_back": bool(revision.rolled_back),
                "backward_calls": int(revision.backward_calls),
                "replayed_state_steps": int(revision.replayed_state_steps),
                "deep_evaluations": snapshot["deep_evaluations"],
            }
            mirrors.append(mirror)

        source_payload = result.to_dict(include_states=False)
        source_fingerprint = source_payload["metrics"]["reproducibility_fingerprint"]
        if adapter_provenance is None:
            provenance_payload = None
        elif isinstance(adapter_provenance, AdapterProvenance):
            provenance_payload = adapter_provenance.to_dict()
        else:
            provenance_payload = dict(adapter_provenance)
        baseline = result.baseline_states.detach().cpu()
        final = result.final_states.detach().cpu()
        trace: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "model": frozen.MODEL_NAME,
            "model_version": frozen.MODEL_VERSION,
            "monolith_sha256": EXPECTED_MONOLITH_SHA256,
            "core_hash_before": result.core_hash_before,
            "core_hash_after": result.core_hash_after,
            "config": dataclasses.asdict(result.config),
            "observations": [dataclasses.asdict(item) for item in result.observations],
            "adapter_provenance": provenance_payload,
            "baseline_geometry": state_geometry(
                baseline,
                topic_dim=result.config.topic_dim,
                epsilon=self.geometry_epsilon,
            ),
            "final_geometry": state_geometry(
                final,
                topic_dim=result.config.topic_dim,
                epsilon=self.geometry_epsilon,
            ),
            "delta_geometry": state_geometry(
                final - baseline,
                topic_dim=result.config.topic_dim,
                epsilon=self.geometry_epsilon,
            ),
            "controls": _float_list(result.controls),
            "event_candidates": event_candidates,
            "revision_mirrors": mirrors,
            "candidate_control_leverage": {
                "enabled": False,
                "method": None,
                "metric": "target_aligned_source_belief_projection_derivative",
                "definition": (
                    "Feasible centered or radially projected forward one-sided "
                    "finite difference along one normalized topic-aligned requested "
                    "actuation at the event source."
                ),
                "epsilon": None,
                "candidates": [],
            },
            "execution_metrics": {
                "detected_event_count": len(result.events)
                + len(result.suppressed_events),
                "committed_event_count": len(result.events),
                "suppressed_event_count": len(result.suppressed_events),
                "backward_calls": int(result.backward_calls),
                "generator_step_calls": int(result.generator_step_calls),
                "decode_call_count": int(result.decode_call_count),
                "core_unchanged": result.core_hash_before == result.core_hash_after,
                "diagnostic_generator_step_calls": diagnostic_meta[
                    "generator_step_calls"
                ],
                "timing_note": "Instrumented timing is not a v0.1 performance baseline.",
            },
            "terminal_diagnostic_contract": (
                "Each event comparison retains controls committed before that event, "
                "adds only the current event delta, and suppresses all later revisions."
            ),
            "source_session_fingerprint": source_fingerprint,
            "claim_boundary": [
                "Geometry is computed over the explicit toy state, not a pretrained model hidden manifold.",
                "Confidence and semantic fields are structured inputs, not model-discovered uncertainty.",
                "Normalized acceleration and turn angle are exploratory signals, not reasoning-quality metrics.",
                "Event-local mirrors isolate the current control delta; global baseline deltas do not attribute later events.",
                "Diagnostic source-projection leverage probes do not alter runtime routing or committed execution.",
                "No private chain-of-thought or hosted-model hidden state is observed.",
            ],
        }
        trace["trace_fingerprint"] = _trace_fingerprint(trace)
        return trace

    def _terminal_diagnostics(
        self, result: Any
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        diagnostic = frozen.EventDrivenBackwardReasoner(result.config)
        diagnostic.codec.prepare_topics(result.observations)
        encoded = diagnostic.codec.encode_many(result.observations)
        total_length = len(result.observations)
        outputs: list[dict[str, Any]] = []
        for revision, snapshot in zip(result.revisions, self._revision_snapshots):
            source = revision.event.source_step
            before_prefix = torch.tensor(
                snapshot["controls_before"], device=encoded.device, dtype=encoded.dtype
            )
            after_prefix = torch.tensor(
                snapshot["controls_after"], device=encoded.device, dtype=encoded.dtype
            )
            before_controls = torch.zeros(
                total_length,
                result.config.control_dim,
                device=encoded.device,
                dtype=encoded.dtype,
            )
            after_controls = torch.zeros_like(before_controls)
            before_controls[: source + 1] = before_prefix
            after_controls[: source + 1] = after_prefix
            mirror = diagnostic.generator.rollout(encoded, before_controls).detach()
            revised = diagnostic.generator.rollout(encoded, after_controls).detach()
            separation = torch.linalg.vector_norm(revised - mirror, dim=-1)
            topic = diagnostic.codec.topic_vector(result.observations[source].topic)
            q = result.config.topic_dim
            mirror_projection = mirror[:, q : 2 * q] @ topic
            revised_projection = revised[:, q : 2 * q] @ topic
            target = float(revision.event.revision_target)
            source_gain = float(
                abs(float(mirror_projection[source].item()) - target)
                - abs(float(revised_projection[source].item()) - target)
            )
            terminal_gain = float(
                abs(float(mirror_projection[-1].item()) - target)
                - abs(float(revised_projection[-1].item()) - target)
            )
            source_separation = float(separation[source].item())
            terminal_separation = float(separation[-1].item())
            survival = (
                terminal_separation / source_separation
                if source_separation > self.geometry_epsilon
                else None
            )
            decay_distance = None
            if source_separation > self.geometry_epsilon:
                threshold = source_separation / math.e
                decay_distance = next(
                    (
                        step - source
                        for step in range(source + 1, total_length)
                        if float(separation[step].item()) <= threshold
                    ),
                    None,
                )
            revised_topic = result.observations[source].topic.strip().lower()
            unrelated = [
                step
                for step in range(revision.earliest_replay_step, total_length)
                if result.observations[step].topic.strip().lower() != revised_topic
            ]
            leakage = (
                max(float(separation[step].item()) for step in unrelated)
                if unrelated
                else 0.0
            )
            outputs.append(
                {
                    "terminal_state_delta_l2": terminal_separation,
                    "source_target_projection_gain": source_gain,
                    "terminal_target_projection_gain": terminal_gain,
                    "propagation_survival_ratio": survival,
                    "decay_distance": decay_distance,
                    "unrelated_state_leakage_max": leakage,
                    "separation_curve": [float(value) for value in separation.tolist()],
                }
            )
        return outputs, {
            "generator_step_calls": diagnostic.generator.step_call_count,
            "core_hash": diagnostic.generator.frozen_hash(),
        }

    def _control_leverage_probe(
        self,
        result: Any,
        *,
        epsilon: float,
    ) -> dict[str, Any]:
        if epsilon <= 0.0:
            raise ValueError("leverage epsilon must be positive")
        diagnostic = frozen.EventDrivenBackwardReasoner(result.config)
        diagnostic.codec.prepare_topics(result.observations)
        encoded = diagnostic.codec.encode_many(result.observations)
        total_length = len(result.observations)
        snapshots = {item["source_step"]: item for item in self._revision_snapshots}
        events = {event.source_step: event for event in result.events}
        rows: list[dict[str, Any]] = []
        for candidate_record in self._event_candidates:
            source = candidate_record["source_step"]
            if source not in events or source not in snapshots:
                continue
            event = events[source]
            snapshot = snapshots[source]
            base = torch.zeros(
                total_length,
                result.config.control_dim,
                device=encoded.device,
                dtype=encoded.dtype,
            )
            prefix = torch.tensor(
                snapshot["controls_before"], device=encoded.device, dtype=encoded.dtype
            )
            base[: source + 1] = prefix
            base_states = diagnostic.generator.rollout(encoded, base).detach()
            topic = diagnostic.codec.topic_vector(result.observations[source].topic)
            direction = diagnostic.generator.control_basis.transpose(0, 1) @ topic
            direction_norm = torch.linalg.vector_norm(direction)
            if float(direction_norm.item()) <= 1e-12:
                continue
            q = result.config.topic_dim
            base_source_projection = float(
                (base_states[source, q : 2 * q] @ topic).item()
            )
            desired_sign = (
                1.0 if event.revision_target >= base_source_projection else -1.0
            )
            direction = desired_sign * direction / direction_norm
            for candidate in candidate_record["candidates"]:
                candidate_step = int(candidate["step"])
                mask = torch.zeros_like(base)
                mask[candidate_step] = 1.0
                plus_delta = torch.zeros_like(base)
                minus_delta = torch.zeros_like(base)
                plus_delta[candidate_step] = epsilon * direction
                minus_delta[candidate_step] = -epsilon * direction
                raw_plus = base[candidate_step] + plus_delta[candidate_step]
                raw_minus = base[candidate_step] + minus_delta[candidate_step]
                requested_plus_norm = float(torch.linalg.vector_norm(raw_plus).item())
                requested_minus_norm = float(torch.linalg.vector_norm(raw_minus).item())
                max_control_norm = float(result.config.max_control_norm)
                feasibility_tolerance = 1e-6
                plus_requested_feasible = (
                    requested_plus_norm <= max_control_norm + feasibility_tolerance
                )
                minus_requested_feasible = (
                    requested_minus_norm <= max_control_norm + feasibility_tolerance
                )
                diagnostic._project_controls_(base, plus_delta, mask)
                diagnostic._project_controls_(base, minus_delta, mask)
                plus_controls = base + mask * plus_delta
                minus_controls = base + mask * minus_delta
                actual_plus_delta_norm = float(
                    torch.linalg.vector_norm(plus_delta[candidate_step]).item()
                )
                actual_minus_delta_norm = float(
                    torch.linalg.vector_norm(minus_delta[candidate_step]).item()
                )
                boundary_limited = not (
                    plus_requested_feasible and minus_requested_feasible
                )
                if not boundary_limited:
                    scheme = "centered"
                    plus_states = diagnostic.generator.rollout(
                        encoded, plus_controls
                    ).detach()
                    minus_states = diagnostic.generator.rollout(
                        encoded, minus_controls
                    ).detach()
                    source_derivative = (plus_states[source] - minus_states[source]) / (
                        2.0 * epsilon
                    )
                    terminal_derivative = (plus_states[-1] - minus_states[-1]) / (
                        2.0 * epsilon
                    )
                else:
                    scheme = "projected_forward_one_sided"
                    plus_states = diagnostic.generator.rollout(
                        encoded, plus_controls
                    ).detach()
                    source_derivative = (
                        plus_states[source] - base_states[source]
                    ) / epsilon
                    terminal_derivative = (plus_states[-1] - base_states[-1]) / epsilon
                plus_control_norm = float(
                    torch.linalg.vector_norm(plus_controls[candidate_step]).item()
                )
                minus_control_norm = float(
                    torch.linalg.vector_norm(minus_controls[candidate_step]).item()
                )
                max_probe_control_norm = max(plus_control_norm, minus_control_norm)
                if max_probe_control_norm > max_control_norm + 1e-5:
                    raise AssertionError("diagnostic probe exceeded control bound")
                source_belief_derivative = float(
                    (source_derivative[q : 2 * q] @ topic).item()
                )
                terminal_belief_derivative = float(
                    (terminal_derivative[q : 2 * q] @ topic).item()
                )
                aligned_source = desired_sign * source_belief_derivative
                aligned_terminal = desired_sign * terminal_belief_derivative
                rows.append(
                    {
                        "source_step": source,
                        "candidate_step": candidate_step,
                        "semantic_score": candidate["semantic_score"],
                        "attention": candidate["attention"],
                        "control_direction": _float_list(direction),
                        "finite_difference_scheme": scheme,
                        "requested_epsilon": epsilon,
                        "actual_plus_delta_norm": actual_plus_delta_norm,
                        "actual_minus_delta_norm": actual_minus_delta_norm,
                        "plus_requested_feasible": plus_requested_feasible,
                        "minus_requested_feasible": minus_requested_feasible,
                        "boundary_limited": boundary_limited,
                        "control_norm_before": float(
                            torch.linalg.vector_norm(base[candidate_step]).item()
                        ),
                        "requested_plus_control_norm": requested_plus_norm,
                        "requested_minus_control_norm": requested_minus_norm,
                        "plus_control_norm": plus_control_norm,
                        "minus_control_norm": minus_control_norm,
                        "probe_control_norm_max": max_probe_control_norm,
                        "source_belief_derivative": source_belief_derivative,
                        "terminal_belief_derivative": terminal_belief_derivative,
                        "target_aligned_source_belief_derivative": aligned_source,
                        "target_aligned_terminal_belief_derivative": aligned_terminal,
                        "source_state_derivative_norm": _vector_norm(source_derivative),
                        "terminal_state_derivative_norm": _vector_norm(
                            terminal_derivative
                        ),
                        "control_leverage": aligned_source,
                    }
                )
        scheme_counts: dict[str, int] = {}
        for row in rows:
            scheme = str(row["finite_difference_scheme"])
            scheme_counts[scheme] = scheme_counts.get(scheme, 0) + 1
        return {
            "enabled": True,
            "method": (
                "feasible_centered_or_projected_forward_one_sided_topic_aligned_control"
            ),
            "metric": "target_aligned_source_belief_projection_derivative",
            "definition": (
                "Centered finite difference when both requested topic-aligned "
                "endpoints are feasible; otherwise the forward target-oriented "
                "endpoint is radially projected through the frozen control bound "
                "and compared with the feasible base state."
            ),
            "epsilon": epsilon,
            "max_control_norm": float(result.config.max_control_norm),
            "finite_difference_scheme_counts": scheme_counts,
            "candidates": rows,
            "diagnostic_generator_step_calls": diagnostic.generator.step_call_count,
            "diagnostic_core_hash": diagnostic.generator.frozen_hash(),
            "execution_counter_neutral": True,
            "interpretation": (
                "One-direction event-source projection sensitivity only; it is not an "
                "objective gradient, full-state controllability, runtime route, or "
                "independent quality metric."
            ),
        }


def _coerce_observations(items: Sequence[Any]) -> list[Any]:
    observations: list[Any] = []
    for item in items:
        if isinstance(item, frozen.Observation):
            observations.append(item)
        elif hasattr(item, "to_observation_mapping"):
            observations.append(
                frozen.Observation.from_mapping(item.to_observation_mapping())
            )
        elif isinstance(item, Mapping):
            observations.append(frozen.Observation.from_mapping(dict(item)))
        else:
            raise TypeError(f"unsupported observation type: {type(item).__name__}")
    return observations


def instrument_session(
    observations: Sequence[Any],
    config: Any | None = None,
    *,
    candidate_control_leverage: bool = False,
    leverage_epsilon: float = 1e-3,
    adapter_provenance: AdapterProvenance | Mapping[str, Any] | None = None,
    capture_deep: bool = False,
) -> InstrumentedSession:
    engine = InstrumentedEventDrivenBackwardReasoner(config, capture_deep=capture_deep)
    return engine.run_instrumented(
        _coerce_observations(observations),
        candidate_control_leverage=candidate_control_leverage,
        leverage_epsilon=leverage_epsilon,
        adapter_provenance=adapter_provenance,
    )


def _normalized_revision(revision: Any) -> dict[str, Any]:
    payload = dataclasses.asdict(revision)
    payload.pop("wall_time_ms", None)
    return payload


def _assert_observer_neutral(plain: Any, observed: Any) -> None:
    tensor_pairs = (
        (plain.baseline_states, observed.baseline_states, "baseline states"),
        (plain.final_states, observed.final_states, "final states"),
        (plain.controls, observed.controls, "controls"),
    )
    for left, right, label in tensor_pairs:
        if not torch.equal(left, right):
            raise AssertionError(f"observer changed {label}")
    if [dataclasses.asdict(item) for item in plain.events] != [
        dataclasses.asdict(item) for item in observed.events
    ]:
        raise AssertionError("observer changed events or routes")
    if [dataclasses.asdict(item) for item in plain.suppressed_events] != [
        dataclasses.asdict(item) for item in observed.suppressed_events
    ]:
        raise AssertionError("observer changed suppressed events")
    if [_normalized_revision(item) for item in plain.revisions] != [
        _normalized_revision(item) for item in observed.revisions
    ]:
        raise AssertionError("observer changed revision checkpoints")
    scalar_fields = (
        "decoded",
        "decode_call_count",
        "core_hash_before",
        "core_hash_after",
        "backward_calls",
        "generator_step_calls",
    )
    for field in scalar_fields:
        if getattr(plain, field) != getattr(observed, field):
            raise AssertionError(f"observer changed {field}")
    plain_fp = plain.to_dict(False)["metrics"]["reproducibility_fingerprint"]
    observed_fp = observed.to_dict(False)["metrics"]["reproducibility_fingerprint"]
    if plain_fp != observed_fp:
        raise AssertionError("observer changed the source session fingerprint")


def _sequential_observations() -> list[Any]:
    return [
        frozen.Observation("claim", 1.0, "initial claim"),
        frozen.Observation("context", 0.1, "unrelated context"),
        frozen.Observation("claim", -0.3, "first revision"),
        frozen.Observation("claim", 1.0, "second revision"),
    ]


def run_self_tests() -> dict[str, Any]:
    assert_frozen_monolith()
    config = frozen.EBRTConfig(seed=11, revision_steps=4, max_events=4)
    observations = _sequential_observations()
    plain = frozen.EventDrivenBackwardReasoner(config).run(observations)
    engine = InstrumentedEventDrivenBackwardReasoner(config, capture_deep=True)
    session = engine.run_instrumented(
        observations, candidate_control_leverage=True, leverage_epsilon=1e-3
    )
    _assert_observer_neutral(plain, session.result)
    trace = session.trace
    if trace["schema_version"] != SCHEMA_VERSION:
        raise AssertionError("wrong instrumentation schema")
    if len(trace["revision_mirrors"]) != 2:
        raise AssertionError("sequential fixture did not emit two mirrors")
    second_snapshot = engine._revision_snapshots[1]
    if not any(
        abs(value) > 0.0 for row in second_snapshot["controls_before"] for value in row
    ):
        raise AssertionError("later local mirror lost the earlier committed revision")
    for mirror, revision in zip(trace["revision_mirrors"], session.result.revisions):
        if mirror["mirror_states"] != revision.affected_states_before:
            raise AssertionError("event-local mirror is not exact")
        if mirror["revised_states"] != revision.affected_states_after:
            raise AssertionError("event-local revised branch is not exact")
        if len(mirror["deep_evaluations"]) != config.revision_steps + 2:
            raise AssertionError("deep optimizer capture has the wrong call count")

    committed_by_source = {event.source_step: event for event in session.result.events}
    for candidate in trace["event_candidates"]:
        if candidate["status"] != "committed":
            continue
        event = committed_by_source[candidate["source_step"]]
        if abs(candidate["event_score"] - event.score) > 1e-7:
            raise AssertionError("event score decomposition does not match core")
        for row in candidate["candidates"]:
            if abs(row["attention"] - event.attention_weights[row["step"]]) > 1e-7:
                raise AssertionError("attention decomposition does not match core")

    baseline = session.result.baseline_states
    final = session.result.final_states
    recorded_delta = torch.tensor(trace["delta_geometry"]["full"]["states"])
    if not torch.equal(recorded_delta, final - baseline):
        raise AssertionError("global delta geometry is not exact")

    straight = torch.tensor([[1.0, 0.0], [2.0, 0.0], [3.0, 0.0]])
    reversal = torch.tensor([[1.0, 0.0], [2.0, 0.0], [1.0, 0.0]])
    stopped = torch.tensor([[1.0, 0.0], [1.0, 0.0], [2.0, 0.0]])
    straight_geometry = trajectory_geometry(straight)
    reversal_geometry = trajectory_geometry(reversal)
    stopped_geometry = trajectory_geometry(stopped)
    if abs(straight_geometry["turn_angle"][1]) > 1e-7:
        raise AssertionError("straight-line turn angle is not zero")
    if abs(reversal_geometry["turn_angle"][2] - math.pi) > 1e-7:
        raise AssertionError("reversal turn angle is not pi")
    if stopped_geometry["turn_angle"][1] is not None:
        raise AssertionError("zero-speed turn angle must be null")
    if stopped_geometry["normalized_acceleration"][1] is not None:
        raise AssertionError("zero-speed normalized acceleration must be null")
    rotation = torch.tensor([[0.0, -1.0], [1.0, 0.0]])
    rotated = straight @ rotation
    translated = straight + torch.tensor([5.0, -3.0])
    rotated_geometry = trajectory_geometry(rotated)
    translated_geometry = trajectory_geometry(translated)
    for index in range(1, len(straight)):
        if (
            abs(straight_geometry["speed"][index] - rotated_geometry["speed"][index])
            > 1e-7
        ):
            raise AssertionError("speed is not rotation invariant")
        if (
            abs(straight_geometry["speed"][index] - translated_geometry["speed"][index])
            > 1e-7
        ):
            raise AssertionError("speed is not translation invariant after step zero")

    counters = (
        session.result.generator_step_calls,
        session.result.backward_calls,
        session.result.decode_call_count,
    )
    if not trace["candidate_control_leverage"]["candidates"]:
        raise AssertionError("control-leverage probe returned no candidates")
    if counters != (
        session.result.generator_step_calls,
        session.result.backward_calls,
        session.result.decode_call_count,
    ):
        raise AssertionError("probe changed execution counters")

    committed_candidates = [
        item for item in trace["event_candidates"] if item["status"] == "committed"
    ]
    boundary_candidate = committed_candidates[0]
    boundary_source = int(boundary_candidate["source_step"])
    boundary_step = int(boundary_candidate["candidates"][0]["step"])
    boundary_snapshot = next(
        item
        for item in engine._revision_snapshots
        if int(item["source_step"]) == boundary_source
    )
    boundary_codec = frozen.EventDrivenBackwardReasoner(config)
    boundary_codec.codec.prepare_topics(session.result.observations)
    boundary_topic = boundary_codec.codec.topic_vector(
        session.result.observations[boundary_source].topic
    )
    boundary_direction = (
        boundary_codec.generator.control_basis.transpose(0, 1) @ boundary_topic
    )
    boundary_direction = boundary_direction / torch.linalg.vector_norm(
        boundary_direction
    )
    boundary_snapshot["controls_before"][boundary_step] = _float_list(
        config.max_control_norm * boundary_direction
    )
    boundary_probe = engine._control_leverage_probe(session.result, epsilon=1e-3)
    boundary_rows = [
        item
        for item in boundary_probe["candidates"]
        if int(item["source_step"]) == boundary_source
        and int(item["candidate_step"]) == boundary_step
    ]
    if len(boundary_rows) != 1:
        raise AssertionError("boundary leverage fixture did not produce one row")
    boundary_row = boundary_rows[0]
    if boundary_row["finite_difference_scheme"] != "projected_forward_one_sided":
        raise AssertionError(
            "boundary leverage fixture did not use projected forward probe"
        )
    if boundary_row["boundary_limited"] is not True:
        raise AssertionError("boundary leverage fixture was not marked limited")
    if boundary_row["probe_control_norm_max"] > config.max_control_norm + 1e-5:
        raise AssertionError("boundary leverage fixture exceeded control bound")

    repeated = InstrumentedEventDrivenBackwardReasoner(
        config, capture_deep=True
    ).run_instrumented(observations, candidate_control_leverage=True)
    if repeated.trace["trace_fingerprint"] != trace["trace_fingerprint"]:
        raise AssertionError("trace fingerprint is not deterministic")

    adapter = StructuredOracleAdapter()
    adapted = adapter.observe_many(
        [
            {
                "topic": item.topic,
                "stance": item.stance,
                "text": item.text,
                "confidence": item.confidence,
                "revision_cue": item.revision_cue,
            }
            for item in observations
        ]
    )
    adapted_session = instrument_session(
        adapted, config, adapter_provenance=adapter.provenance
    )
    if (
        adapted_session.trace["adapter_provenance"]["semantic_source"]
        != "structured_oracle"
    ):
        raise AssertionError("adapter provenance is missing")
    return {
        "status": "PASS",
        "schema_version": SCHEMA_VERSION,
        "monolith_sha256": EXPECTED_MONOLITH_SHA256,
        "checks": [
            "frozen v0.1 SHA guard",
            "observer-neutral states, routes, controls, counters, and fingerprint",
            "exact sequential event-local mirrors with prior revisions retained",
            "event score and semantic-attention decomposition parity",
            "global delta reconstruction",
            "geometry straight/turn/reversal/zero-speed/invariance fixtures",
            "deep optimizer call accounting",
            "feasible centered/projected-forward leverage neutrality",
            "boundary leverage probes remain inside the frozen control ball",
            "deterministic trace fingerprint",
            "versioned structured-oracle provenance",
        ],
    }


def _demo_payload(*, deep: bool, leverage: bool) -> dict[str, Any]:
    adapter = StructuredOracleAdapter()
    demo_observations = [
        *_sequential_observations(),
        frozen.Observation(
            "context",
            -0.2,
            "Post-revision continuation used to measure propagation survival.",
        ),
    ]
    adapted = adapter.observe_many(
        [
            {
                "topic": item.topic,
                "stance": item.stance,
                "text": item.text,
                "confidence": item.confidence,
                "revision_cue": item.revision_cue,
            }
            for item in demo_observations
        ]
    )
    session = instrument_session(
        adapted,
        frozen.EBRTConfig(),
        capture_deep=deep,
        candidate_control_leverage=leverage,
        adapter_provenance=adapter.provenance,
    )
    return session.trace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="EBRT v0.2 counterfactual instrumentation observer"
    )
    subparsers = parser.add_subparsers(dest="command")
    demo = subparsers.add_parser("demo", help="emit a deterministic mirror trace")
    demo.add_argument("--deep", action="store_true")
    demo.add_argument("--control-leverage", action="store_true")
    demo.add_argument("--output-json", type=Path)
    subparsers.add_parser("self-test", help="run offline observer-integrity checks")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    import sys

    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments == ["--self-test"]:
        arguments = ["self-test"]
    if not arguments:
        arguments = ["demo"]
    args = build_parser().parse_args(arguments)
    if args.command == "self-test":
        payload = run_self_tests()
    elif args.command == "demo":
        payload = _demo_payload(deep=args.deep, leverage=args.control_leverage)
        if args.output_json:
            args.output_json.parent.mkdir(parents=True, exist_ok=True)
            args.output_json.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)
                + "\n",
                encoding="utf-8",
            )
    else:
        raise RuntimeError(f"unsupported command: {args.command}")
    print(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
