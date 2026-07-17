#!/usr/bin/env python3
"""Event-driven Backward Reasoning Transformer (EBRT), mechanism v0.1.

This is a single-file, offline PyTorch prototype of one narrow claim:

    a premise-shift event can route a local differentiable objective to selected
    earlier reasoning controls, revise them with real autograd at inference time,
    replay the affected suffix through a frozen generator, and decode only after
    revision has finished.

It is intentionally *not* a language model and does not claim better reasoning.
The structured ``topic`` and ``stance`` fields stand in for a future learned
semantic event probe. Event timing, eligible topic, and revision target are
therefore oracle-scripted in v0.1. Routing uses frozen latent-state Q/K
similarity, not a trained Transformer or learned self-attention policy. Text is
retained only as an auditable observation window.

Examples:

    python ebrt_monolith_v0_1.py --self-test
    python ebrt_monolith_v0_1.py demo --scenario both
    python ebrt_monolith_v0_1.py run --input-json observations.json

Input JSON is either a list or ``{"observations": [...]}`` where each item is:

    {
      "topic": "load_limit",
      "stance": 1.0,
      "text": "Initial premise: the member is within its load limit.",
      "confidence": 1.0,
      "revision_cue": 1.0
    }

``stance`` is a continuous value in [-1, 1]. A later, sufficiently different
stance on the same structured topic can trigger a PREMISE_SHIFT event.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence

import torch
from torch import Tensor, nn
from torch.nn import functional as F


MODEL_NAME = "Event-driven Backward Reasoning Transformer"
MODEL_VERSION = "0.1-mechanism"


@dataclass(frozen=True)
class EBRTConfig:
    """Configuration for the frozen rollout and event-driven latent revision."""

    topic_dim: int = 8
    control_dim: int = 8
    seed: int = 7
    memory_decay: float = 0.72
    observation_gain: float = 0.90
    control_gain: float = 0.85
    context_decay: float = 0.45
    event_threshold: float = 0.55
    attention_temperature: float = 0.20
    attention_contradiction_gain: float = 2.0
    attention_recency_gain: float = 0.05
    top_k: int = 1
    revision_steps: int = 32
    revision_lr: float = 0.08
    target_alignment_weight: float = 1.0
    current_consistency_weight: float = 0.50
    trajectory_anchor_weight: float = 0.02
    control_l2_weight: float = 0.03
    max_control_norm: float = 1.75
    max_events: int = 4
    device: str = "cpu"
    dtype: str = "float32"

    @property
    def latent_dim(self) -> int:
        return self.topic_dim * 3

    def validate(self) -> None:
        if self.topic_dim < 2:
            raise ValueError("topic_dim must be >= 2")
        if self.control_dim < 1 or self.control_dim > self.topic_dim:
            raise ValueError("control_dim must be in [1, topic_dim]")
        if self.top_k < 1:
            raise ValueError("top_k must be >= 1")
        if self.revision_steps < 1:
            raise ValueError("revision_steps must be >= 1")
        if self.revision_lr <= 0.0:
            raise ValueError("revision_lr must be > 0")
        if not 0.0 <= self.event_threshold <= 1.0:
            raise ValueError("event_threshold must be in [0, 1]")
        if self.attention_temperature <= 0.0:
            raise ValueError("attention_temperature must be > 0")
        if self.max_control_norm <= 0.0:
            raise ValueError("max_control_norm must be > 0")
        if self.max_events < 0:
            raise ValueError("max_events must be >= 0")
        if self.dtype not in {"float32", "float64"}:
            raise ValueError("dtype must be float32 or float64")


@dataclass(frozen=True)
class Observation:
    """One visible gloss plus a structured continuous event-probe input."""

    topic: str
    stance: float
    text: str
    confidence: float = 1.0
    revision_cue: float = 1.0

    def validate(self) -> None:
        if not self.topic.strip():
            raise ValueError("observation.topic must not be empty")
        if not self.text.strip():
            raise ValueError("observation.text must not be empty")
        if not -1.0 <= self.stance <= 1.0:
            raise ValueError("observation.stance must be in [-1, 1]")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("observation.confidence must be in [0, 1]")
        if not 0.0 <= self.revision_cue <= 1.0:
            raise ValueError("observation.revision_cue must be in [0, 1]")

    @classmethod
    def from_mapping(cls, item: dict[str, Any]) -> "Observation":
        observation = cls(
            topic=str(item["topic"]),
            stance=float(item["stance"]),
            text=str(item.get("text", item["topic"])),
            confidence=float(item.get("confidence", 1.0)),
            revision_cue=float(item.get("revision_cue", 1.0)),
        )
        observation.validate()
        return observation


@dataclass(frozen=True)
class RevisionEvent:
    """A detected transition plus strictly backward revision routing."""

    source_step: int
    kind: str
    score: float
    prior_stance: float
    current_stance: float
    revision_target: float
    target_steps: tuple[int, ...]
    attention_weights: tuple[float, ...]


@dataclass
class RevisionRecord:
    """Non-destructive audit record for one latent revision."""

    event: RevisionEvent
    energy_before: float
    energy_after: float
    energy_terms_before: dict[str, float]
    energy_terms_after: dict[str, float]
    energy_history: list[float]
    first_grad_norm: float
    max_grad_norm: float
    target_control_norms: dict[int, float]
    state_delta_norms: list[float]
    target_controls_before: dict[int, list[float]]
    target_controls_after: dict[int, list[float]]
    affected_states_before: list[list[float]]
    affected_states_after: list[list[float]]
    earliest_replay_step: int
    replayed_state_steps: int
    selected_control_count: int
    accepted: bool
    rolled_back: bool
    backward_calls: int
    wall_time_ms: float


@dataclass
class SessionResult:
    """Complete output of one EBRT reasoning session."""

    config: EBRTConfig
    observations: list[Observation]
    baseline_states: Tensor
    final_states: Tensor
    controls: Tensor
    events: list[RevisionEvent]
    suppressed_events: list[RevisionEvent]
    revisions: list[RevisionRecord]
    decoded: dict[str, Any]
    decode_call_count: int
    core_hash_before: str
    core_hash_after: str
    backward_calls: int
    generator_step_calls: int
    event_budget_exhausted: bool
    unscanned_steps: int
    elapsed_ms: float
    claim_boundary: list[str] = field(default_factory=list)

    def to_dict(self, include_states: bool = True) -> dict[str, Any]:
        event_dicts = [asdict(event) for event in self.events]
        suppressed_event_dicts = [asdict(event) for event in self.suppressed_events]
        revision_dicts = []
        for revision in self.revisions:
            item = asdict(revision)
            item["event"] = asdict(revision.event)
            revision_dicts.append(item)

        fingerprint_material = {
            "config": asdict(self.config),
            "observations": [asdict(item) for item in self.observations],
            "events": event_dicts,
            "suppressed_events": suppressed_event_dicts,
            "controls": _tensor_to_list(self.controls),
            "final_states": _tensor_to_list(self.final_states),
            "core_hash": self.core_hash_after,
        }
        reproducibility_fingerprint = hashlib.sha256(
            json.dumps(
                fingerprint_material,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()

        payload: dict[str, Any] = {
            "model": MODEL_NAME,
            "version": MODEL_VERSION,
            "config": asdict(self.config),
            "observations": [asdict(observation) for observation in self.observations],
            "events": event_dicts,
            "suppressed_events": suppressed_event_dicts,
            "revisions": revision_dicts,
            "controls": _tensor_to_list(self.controls),
            "decoded": self.decoded,
            "metrics": {
                "steps": len(self.observations),
                "revision_count": len(self.revisions),
                "detected_event_count": len(self.events) + len(self.suppressed_events),
                "suppressed_event_count": len(self.suppressed_events),
                "accepted_revision_count": sum(
                    int(revision.accepted) for revision in self.revisions
                ),
                "trigger_sparsity": (
                    len(self.revisions) / max(1, len(self.observations))
                ),
                "backward_calls": self.backward_calls,
                "generator_step_calls": self.generator_step_calls,
                "replayed_state_steps": sum(
                    revision.replayed_state_steps for revision in self.revisions
                ),
                "selected_control_count": sum(
                    revision.selected_control_count for revision in self.revisions
                ),
                "event_budget_exhausted": self.event_budget_exhausted,
                "unscanned_steps": self.unscanned_steps,
                "reproducibility_fingerprint": reproducibility_fingerprint,
                "decode_call_count": self.decode_call_count,
                "core_unchanged": self.core_hash_before == self.core_hash_after,
                "max_control_norm": float(
                    torch.linalg.vector_norm(self.controls, dim=-1).max().item()
                ),
                "elapsed_ms": self.elapsed_ms,
            },
            "core_hash_before": self.core_hash_before,
            "core_hash_after": self.core_hash_after,
            "implementation_sha256": _implementation_sha256(),
            "claim_boundary": self.claim_boundary,
        }
        if include_states:
            payload["baseline_states"] = _tensor_to_list(self.baseline_states)
            payload["final_states"] = _tensor_to_list(self.final_states)
        return payload


class FrozenReasoningGenerator(nn.Module):
    """A tiny continuous-state generator whose weights never change.

    The latent state has three blocks of ``topic_dim`` values:

    1. topic memory,
    2. signed belief memory,
    3. hashed text context.

    A low-dimensional control enters only the belief block. Controls, not model
    weights, are the inference-time optimization variables.
    """

    def __init__(self, config: EBRTConfig) -> None:
        super().__init__()
        self.config = config
        dtype = _resolve_dtype(config.dtype)
        generator = torch.Generator(device="cpu")
        generator.manual_seed(config.seed)
        raw_basis = torch.randn(
            config.topic_dim,
            config.control_dim,
            generator=generator,
            dtype=dtype,
        )
        basis, _ = torch.linalg.qr(raw_basis, mode="reduced")
        context_mix = torch.randn(
            config.topic_dim,
            config.topic_dim,
            generator=generator,
            dtype=dtype,
        ) / math.sqrt(config.topic_dim)
        self.register_buffer("control_basis", basis)
        self.register_buffer("context_mix", context_mix)
        self.step_call_count = 0
        self.to(config.device)
        for parameter in self.parameters():
            parameter.requires_grad_(False)

    def step(self, previous: Tensor, observation: Tensor, control: Tensor) -> Tensor:
        self.step_call_count += 1
        q = self.config.topic_dim
        prev_topic, prev_belief, prev_context = previous.split(q, dim=-1)
        obs_topic, obs_belief, obs_context = observation.split(q, dim=-1)
        control_effect = self.control_basis @ control

        topic = torch.tanh(
            self.config.memory_decay * prev_topic
            + self.config.observation_gain * obs_topic
        )
        belief = torch.tanh(
            self.config.memory_decay * prev_belief
            + self.config.observation_gain * obs_belief
            + self.config.control_gain * control_effect
        )
        context = torch.tanh(
            self.config.context_decay * prev_context
            + 0.55 * obs_context
            + 0.10 * (self.context_mix @ belief)
        )
        return torch.cat((topic, belief, context), dim=-1)

    def rollout(
        self,
        encoded_observations: Tensor,
        controls: Tensor,
        initial_state: Tensor | None = None,
    ) -> Tensor:
        if encoded_observations.ndim != 2:
            raise ValueError("encoded_observations must have shape [T, latent_dim]")
        if controls.ndim != 2:
            raise ValueError("controls must have shape [T, control_dim]")
        if encoded_observations.shape[0] != controls.shape[0]:
            raise ValueError("observations and controls must have the same length")

        if initial_state is None:
            previous = torch.zeros(
                self.config.latent_dim,
                device=encoded_observations.device,
                dtype=encoded_observations.dtype,
            )
        else:
            if initial_state.shape != (self.config.latent_dim,):
                raise ValueError("initial_state must have shape [latent_dim]")
            previous = initial_state
        states: list[Tensor] = []
        for index in range(encoded_observations.shape[0]):
            previous = self.step(
                previous,
                encoded_observations[index],
                controls[index],
            )
            states.append(previous)
        if not states:
            return torch.empty(
                0,
                self.config.latent_dim,
                device=encoded_observations.device,
                dtype=encoded_observations.dtype,
            )
        return torch.stack(states)

    def frozen_hash(self) -> str:
        digest = hashlib.sha256()
        for name, value in sorted(self.state_dict().items()):
            digest.update(name.encode("utf-8"))
            digest.update(value.detach().cpu().contiguous().numpy().tobytes())
        return digest.hexdigest()


class StructuredSemanticCodec:
    """Deterministically embeds structured topics and visible text glosses."""

    def __init__(self, config: EBRTConfig) -> None:
        self.config = config
        self.device = torch.device(config.device)
        self.dtype = _resolve_dtype(config.dtype)
        self._prepared_topics: dict[str, Tensor] = {}

    def prepare_topics(self, observations: Sequence[Observation]) -> None:
        """Assign orthogonal slots to the bounded structured-topic vocabulary.

        This avoids accidental cross-topic interference in the mechanism demo.
        A learned model would replace these explicit slots with semantic keys.
        """

        unique_topics = list(
            dict.fromkeys(item.topic.strip().lower() for item in observations)
        )
        if len(unique_topics) > self.config.topic_dim:
            raise ValueError(
                f"v0.1 supports at most {self.config.topic_dim} structured topics per run"
            )
        self._prepared_topics = {}
        for index, topic in enumerate(unique_topics):
            vector = torch.zeros(
                self.config.topic_dim, device=self.device, dtype=self.dtype
            )
            vector[index] = 1.0
            self._prepared_topics[topic] = vector

    def _hash_vector(self, namespace: str, text: str) -> Tensor:
        values: list[float] = []
        counter = 0
        while len(values) < self.config.topic_dim:
            material = f"{self.config.seed}|{namespace}|{counter}|{text}".encode()
            block = hashlib.sha256(material).digest()
            for value in block:
                values.append((value / 127.5) - 1.0)
                if len(values) == self.config.topic_dim:
                    break
            counter += 1
        vector = torch.tensor(values, device=self.device, dtype=self.dtype)
        return F.normalize(vector, dim=0, eps=1e-8)

    def topic_vector(self, topic: str) -> Tensor:
        normalized = topic.strip().lower()
        if normalized in self._prepared_topics:
            return self._prepared_topics[normalized]
        return self._hash_vector("topic", normalized)

    def context_vector(self, text: str) -> Tensor:
        return self._hash_vector("context", text.strip().lower())

    def encode(self, observation: Observation) -> Tensor:
        topic = self.topic_vector(observation.topic)
        signed_belief = observation.stance * observation.confidence * topic
        context = 0.35 * self.context_vector(observation.text)
        return torch.cat((topic, signed_belief, context), dim=-1)

    def encode_many(self, observations: Sequence[Observation]) -> Tensor:
        if not observations:
            return torch.empty(
                0,
                self.config.latent_dim,
                device=self.device,
                dtype=self.dtype,
            )
        return torch.stack([self.encode(observation) for observation in observations])


class EventDrivenBackwardReasoner:
    """Runs forward latent reasoning and sparse event-triggered backward revision."""

    def __init__(self, config: EBRTConfig | None = None) -> None:
        self.config = config or EBRTConfig()
        self.config.validate()
        _seed_everything(self.config.seed)
        self.codec = StructuredSemanticCodec(self.config)
        self.generator = FrozenReasoningGenerator(self.config)
        self.decode_call_count = 0

    def _detect_event(
        self,
        observations: Sequence[Observation],
        source_step: int,
        prefix_states: Tensor,
        active_prior: Observation,
    ) -> RevisionEvent | None:
        current = observations[source_step]
        current_topic_key = current.topic.strip().lower()
        eligible = [
            index
            for index in range(source_step)
            if observations[index].topic.strip().lower() == current_topic_key
        ]
        if not eligible:
            return None

        event_score = (
            abs(current.stance - active_prior.stance)
            * 0.5
            * min(current.confidence, active_prior.confidence)
            * current.revision_cue
        )
        if event_score <= 0.0 or event_score < self.config.event_threshold:
            return None

        q = self.config.topic_dim
        current_query = prefix_states[source_step, :q]
        raw_scores: list[Tensor] = []
        for index in eligible:
            prior = observations[index]
            prior_key = prefix_states[index, :q]
            topic_similarity = F.cosine_similarity(
                current_query.unsqueeze(0), prior_key.unsqueeze(0)
            ).squeeze(0)
            contradiction = (
                abs(current.stance - prior.stance)
                * 0.5
                * min(current.confidence, prior.confidence)
                * current.revision_cue
            )
            recency = index / max(1, source_step - 1)
            raw_scores.append(
                topic_similarity / self.config.attention_temperature
                + self.config.attention_contradiction_gain * contradiction
                + self.config.attention_recency_gain * recency
            )

        logits = torch.stack(raw_scores)
        eligible_attention = torch.softmax(logits, dim=0)
        full_attention = torch.zeros(
            source_step,
            device=eligible_attention.device,
            dtype=eligible_attention.dtype,
        )
        full_attention[torch.tensor(eligible, device=eligible_attention.device)] = (
            eligible_attention
        )
        k = min(self.config.top_k, len(eligible))
        selected_local = torch.topk(eligible_attention, k=k).indices.tolist()
        target_steps = tuple(sorted(eligible[index] for index in selected_local))
        return RevisionEvent(
            source_step=source_step,
            kind="PREMISE_SHIFT",
            score=event_score,
            prior_stance=active_prior.stance,
            current_stance=current.stance,
            revision_target=(
                active_prior.stance
                + current.revision_cue
                * current.confidence
                * (current.stance - active_prior.stance)
            ),
            target_steps=target_steps,
            attention_weights=tuple(float(value) for value in full_attention.tolist()),
        )

    def _revision_energy(
        self,
        states: Tensor,
        controls_delta: Tensor,
        original_states: Tensor,
        event: RevisionEvent,
        current_topic: Tensor,
    ) -> tuple[Tensor, dict[str, Tensor]]:
        q = self.config.topic_dim
        belief_states = states[:, q : 2 * q]
        belief_scalar = belief_states @ current_topic
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
        selected_mask = torch.zeros_like(attention)
        selected_mask[list(event.target_steps)] = 1.0
        selected_attention = attention * selected_mask
        selected_attention = selected_attention / selected_attention.sum().clamp_min(
            1e-8
        )
        target_alignment = (
            selected_attention * (belief_scalar[:-1] - target).square()
        ).sum()
        current_consistency = (belief_scalar[event.source_step] - target).square()
        earliest_target = min(event.target_steps)
        trajectory_anchor = (
            (states[earliest_target:] - original_states[earliest_target:])
            .square()
            .mean()
        )
        control_l2 = controls_delta[list(event.target_steps)].square().mean()
        total = (
            self.config.target_alignment_weight * target_alignment
            + self.config.current_consistency_weight * current_consistency
            + self.config.trajectory_anchor_weight * trajectory_anchor
            + self.config.control_l2_weight * control_l2
        )
        return total, {
            "target_alignment": target_alignment,
            "current_consistency": current_consistency,
            "trajectory_anchor": trajectory_anchor,
            "control_l2": control_l2,
        }

    def _project_controls_(
        self, base_controls: Tensor, delta: Tensor, mask: Tensor
    ) -> None:
        with torch.no_grad():
            candidate = base_controls + mask * delta
            norms = torch.linalg.vector_norm(candidate, dim=-1, keepdim=True)
            scale = torch.clamp(
                self.config.max_control_norm / norms.clamp_min(1e-12), max=1.0
            )
            projected = candidate * scale
            delta.copy_((projected - base_controls) * mask)

    def _revise_prefix(
        self,
        observations: Sequence[Observation],
        encoded: Tensor,
        base_controls: Tensor,
        event: RevisionEvent,
    ) -> tuple[Tensor, Tensor, RevisionRecord]:
        started = time.perf_counter()
        original_states = self.generator.rollout(encoded, base_controls).detach()
        mask = torch.zeros_like(base_controls)
        mask[list(event.target_steps)] = 1.0
        delta = torch.zeros_like(base_controls, requires_grad=True)
        optimizer = torch.optim.Adam([delta], lr=self.config.revision_lr)
        current_topic = self.codec.topic_vector(observations[event.source_step].topic)
        energy_history: list[float] = []
        grad_norms: list[float] = []
        earliest_replay_step = min(event.target_steps)

        def replay_suffix(candidate_controls: Tensor) -> Tensor:
            if earliest_replay_step == 0:
                return self.generator.rollout(encoded, candidate_controls)
            unchanged_prefix = original_states[:earliest_replay_step]
            initial_state = unchanged_prefix[-1]
            replayed_suffix = self.generator.rollout(
                encoded[earliest_replay_step:],
                candidate_controls[earliest_replay_step:],
                initial_state=initial_state,
            )
            return torch.cat((unchanged_prefix, replayed_suffix), dim=0)

        best_energy = math.inf
        best_delta = torch.zeros_like(delta)
        terms_before: dict[str, float] = {}

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
            scalar_terms = {name: float(value.item()) for name, value in terms.items()}
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
                grad_norms.append(float(torch.linalg.vector_norm(delta.grad).item()))
            optimizer.step()
            self._project_controls_(base_controls, delta, mask)

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
            target_control_norms = {
                index: float(torch.linalg.vector_norm(final_controls[index]).item())
                for index in event.target_steps
            }
            state_delta_norms = [
                float(value)
                for value in torch.linalg.vector_norm(
                    final_states - original_states, dim=-1
                ).tolist()
            ]
            target_controls_before = {
                index: [float(value) for value in base_controls[index].tolist()]
                for index in event.target_steps
            }
            target_controls_after = {
                index: [float(value) for value in final_controls[index].tolist()]
                for index in event.target_steps
            }
            affected_states_before = [
                [float(value) for value in row]
                for row in original_states[earliest_replay_step:].tolist()
            ]
            affected_states_after = [
                [float(value) for value in row]
                for row in final_states[earliest_replay_step:].tolist()
            ]

        record = RevisionRecord(
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
            earliest_replay_step=earliest_replay_step,
            replayed_state_steps=(self.config.revision_steps + 2)
            * (event.source_step - earliest_replay_step + 1),
            selected_control_count=len(event.target_steps),
            accepted=accepted,
            rolled_back=rolled_back,
            backward_calls=self.config.revision_steps,
            wall_time_ms=(time.perf_counter() - started) * 1000.0,
        )
        return final_controls.detach(), final_states.detach(), record

    def _decode(
        self,
        observations: Sequence[Observation],
        final_states: Tensor,
    ) -> dict[str, Any]:
        self.decode_call_count += 1
        q = self.config.topic_dim
        final_belief = final_states[-1, q : 2 * q]
        topics: dict[str, str] = {}
        for observation in observations:
            canonical = observation.topic.strip().lower()
            topics.setdefault(canonical, observation.topic.strip())
        beliefs: list[dict[str, Any]] = []
        for canonical, display_topic in topics.items():
            score = float((final_belief @ self.codec.topic_vector(canonical)).item())
            if score > 0.15:
                label = "supports"
            elif score < -0.15:
                label = "rejects"
            else:
                label = "uncertain"
            beliefs.append(
                {
                    "topic": canonical,
                    "display_topic": display_topic,
                    "score": score,
                    "label": label,
                }
            )
        summary = "; ".join(
            f"{belief['topic']}={belief['label']} ({belief['score']:+.3f})"
            for belief in beliefs
        )
        return {
            "kind": "toy_belief_summary",
            "summary": summary,
            "beliefs": beliefs,
            "note": "This is a latent-state probe, not free-form language generation.",
        }

    def run(self, observations: Sequence[Observation]) -> SessionResult:
        if not observations:
            raise ValueError("at least one observation is required")
        clean_observations = list(observations)
        for observation in clean_observations:
            observation.validate()

        started = time.perf_counter()
        self.decode_call_count = 0
        self.generator.step_call_count = 0
        core_hash_before = self.generator.frozen_hash()
        self.codec.prepare_topics(clean_observations)
        encoded_all = self.codec.encode_many(clean_observations)
        controls = torch.zeros(
            len(clean_observations),
            self.config.control_dim,
            device=encoded_all.device,
            dtype=encoded_all.dtype,
        )
        baseline_states = self.generator.rollout(encoded_all, controls).detach()
        events: list[RevisionEvent] = []
        suppressed_events: list[RevisionEvent] = []
        revisions: list[RevisionRecord] = []
        backward_calls = 0
        working_states: list[Tensor] = []
        premise_anchors: dict[str, Observation] = {}

        for source_step in range(len(clean_observations)):
            previous = (
                working_states[-1]
                if working_states
                else torch.zeros(
                    self.config.latent_dim,
                    device=encoded_all.device,
                    dtype=encoded_all.dtype,
                )
            )
            next_state = self.generator.step(
                previous,
                encoded_all[source_step],
                controls[source_step],
            ).detach()
            working_states.append(next_state)
            prefix_encoded = encoded_all[: source_step + 1]
            prefix_controls = controls[: source_step + 1]
            prefix_states = torch.stack(working_states)
            current = clean_observations[source_step]
            topic_key = current.topic.strip().lower()
            active_prior = premise_anchors.get(topic_key)
            if active_prior is None:
                premise_anchors[topic_key] = current
                continue
            event = self._detect_event(
                clean_observations,
                source_step,
                prefix_states,
                active_prior,
            )
            if event is None:
                if (
                    active_prior.confidence < self.config.event_threshold
                    and current.confidence > active_prior.confidence
                ):
                    premise_anchors[topic_key] = current
                continue
            premise_anchors[topic_key] = current
            if len(revisions) >= self.config.max_events:
                suppressed_events.append(event)
                continue
            revised_controls, revised_states, record = self._revise_prefix(
                clean_observations[: source_step + 1],
                prefix_encoded,
                prefix_controls,
                event,
            )
            controls[: source_step + 1] = revised_controls
            events.append(event)
            revisions.append(record)
            backward_calls += record.backward_calls
            working_states = [state.detach() for state in revised_states.unbind(0)]

        final_states = torch.stack(working_states).detach()
        decoded = self._decode(clean_observations, final_states)
        core_hash_after = self.generator.frozen_hash()
        if core_hash_before != core_hash_after:
            raise RuntimeError("frozen reasoning generator changed during inference")

        return SessionResult(
            config=self.config,
            observations=clean_observations,
            baseline_states=baseline_states.cpu(),
            final_states=final_states.cpu(),
            controls=controls.detach().cpu(),
            events=events,
            suppressed_events=suppressed_events,
            revisions=revisions,
            decoded=decoded,
            decode_call_count=self.decode_call_count,
            core_hash_before=core_hash_before,
            core_hash_after=core_hash_after,
            backward_calls=backward_calls,
            generator_step_calls=self.generator.step_call_count,
            event_budget_exhausted=bool(suppressed_events),
            unscanned_steps=0,
            elapsed_ms=(time.perf_counter() - started) * 1000.0,
            claim_boundary=[
                "The prototype validates event-to-gradient revision mechanics only.",
                "Event timing, topic eligibility, and the revision target are oracle-scripted from structured topic/stance fields.",
                "Premise anchors are structured hysteresis state, not beliefs discovered by a learned model.",
                "Routing weights use frozen latent-state Q/K similarity, but no Transformer block, learned self-attention, or learned Revision Policy is implemented.",
                "The frozen toy generator is not a pretrained LM hidden manifold.",
                "A synthetic loss decrease is not evidence of reasoning-quality improvement.",
                "The decoder is a belief probe, not natural-language generation.",
            ],
        )


def stable_scenario() -> list[Observation]:
    return [
        Observation(
            topic="route_clearance",
            stance=-0.25,
            text="A separate clearance issue remains mildly unresolved.",
        ),
        Observation(
            topic="load_limit",
            stance=1.0,
            text="Initial premise: the member is within its load limit.",
        ),
        Observation(
            topic="budget",
            stance=0.40,
            text="The current budget remains plausible.",
        ),
        Observation(
            topic="load_limit",
            stance=0.80,
            text="Later evidence still supports the original load premise.",
        ),
    ]


def premise_shift_scenario() -> list[Observation]:
    return [
        Observation(
            topic="route_clearance",
            stance=-0.25,
            text="A separate clearance issue remains mildly unresolved.",
        ),
        Observation(
            topic="load_limit",
            stance=1.0,
            text="Initial premise: the member is within its load limit.",
        ),
        Observation(
            topic="budget",
            stance=0.40,
            text="The current budget remains plausible.",
        ),
        Observation(
            topic="load_limit",
            stance=-0.22,
            text="New measurement contradicts the load premise enough to require revision.",
        ),
    ]


def _assert_close(left: Tensor, right: Tensor, message: str) -> None:
    if not torch.allclose(left, right, atol=1e-6, rtol=1e-6):
        difference = float((left - right).abs().max().item())
        raise AssertionError(f"{message}; max difference={difference}")


def run_self_tests() -> dict[str, Any]:
    """Offline mechanism checks; these are not an algorithmic benchmark."""

    config = EBRTConfig(seed=17, revision_steps=36, revision_lr=0.07)

    stable_engine = EventDrivenBackwardReasoner(config)
    stable = stable_engine.run(stable_scenario())
    if stable.events:
        raise AssertionError("stable scenario unexpectedly triggered a revision")
    _assert_close(
        stable.baseline_states,
        stable.final_states,
        "no-event path must equal forward-only rollout",
    )
    if not torch.count_nonzero(stable.controls).item() == 0:
        raise AssertionError("no-event path must leave every control at zero")
    if stable.decode_call_count != 1:
        raise AssertionError("stable path must decode exactly once")
    if stable.generator_step_calls != 2 * len(stable.observations):
        raise AssertionError(
            "no-event execution must remain linear in trajectory length"
        )

    shift_engine = EventDrivenBackwardReasoner(config)
    shifted = shift_engine.run(premise_shift_scenario())
    if len(shifted.events) != 1 or len(shifted.revisions) != 1:
        raise AssertionError("premise-shift scenario must trigger exactly one revision")
    event = shifted.events[0]
    revision = shifted.revisions[0]
    if event.kind != "PREMISE_SHIFT":
        raise AssertionError("unexpected event kind")
    if not all(target < event.source_step for target in event.target_steps):
        raise AssertionError("revision attention must target only earlier states")
    if len(event.attention_weights) != event.source_step:
        raise AssertionError("attention vector must exclude current and future states")
    if not math.isclose(sum(event.attention_weights), 1.0, abs_tol=1e-6):
        raise AssertionError("backward attention weights must sum to one")
    if revision.energy_after >= revision.energy_before:
        raise AssertionError("local revision energy did not decrease")
    if not revision.accepted:
        raise AssertionError("improving revision must be accepted")
    if revision.first_grad_norm <= 1e-8:
        raise AssertionError("revision control did not receive a nonzero gradient")
    if revision.backward_calls != config.revision_steps:
        raise AssertionError("unexpected number of backward calls")
    if revision.state_delta_norms[event.target_steps[0]] <= 1e-5:
        raise AssertionError("routed earlier state did not change")
    if revision.earliest_replay_step > 0:
        _assert_close(
            shifted.baseline_states[: revision.earliest_replay_step],
            shifted.final_states[: revision.earliest_replay_step],
            "states before the earliest routed target must remain unchanged",
        )
    non_target_controls = shifted.controls.clone()
    non_target_controls[list(event.target_steps)] = 0.0
    if torch.count_nonzero(non_target_controls).item() != 0:
        raise AssertionError("only routed steps may receive nonzero controls")
    if any(
        value > config.max_control_norm + 1e-5
        for value in revision.target_control_norms.values()
    ):
        raise AssertionError("a revised control exceeded its norm bound")
    if shifted.core_hash_before != shifted.core_hash_after:
        raise AssertionError("frozen generator hash changed")
    if shifted.decode_call_count != 1:
        raise AssertionError("shift path must decode exactly once after revision")
    if shifted.backward_calls <= 0:
        raise AssertionError("premise shift must execute real backward calls")

    q = config.topic_dim
    topic_vector = shift_engine.codec.topic_vector("load_limit").cpu()
    baseline_belief = float(
        (shifted.baseline_states[-1, q : 2 * q] @ topic_vector).item()
    )
    revised_belief = float((shifted.final_states[-1, q : 2 * q] @ topic_vector).item())
    if revised_belief >= baseline_belief:
        raise AssertionError(
            "revision did not move final belief toward new negative evidence"
        )
    if abs(revised_belief - event.revision_target) >= abs(
        baseline_belief - event.revision_target
    ):
        raise AssertionError("revision did not reduce distance to its local target")
    readout_flipped = -0.15 < baseline_belief < 0.15 and revised_belief < -0.15

    repeat_engine = EventDrivenBackwardReasoner(config)
    repeated = repeat_engine.run(premise_shift_scenario())
    _assert_close(
        shifted.final_states,
        repeated.final_states,
        "same seed must reproduce final trajectory",
    )
    _assert_close(
        shifted.controls,
        repeated.controls,
        "same seed must reproduce revision controls",
    )
    if shifted.events[0].target_steps != repeated.events[0].target_steps:
        raise AssertionError("same seed must reproduce backward routing")
    shifted_fingerprint = shifted.to_dict()["metrics"]["reproducibility_fingerprint"]
    repeated_fingerprint = repeated.to_dict()["metrics"]["reproducibility_fingerprint"]
    if shifted_fingerprint != repeated_fingerprint:
        raise AssertionError("timing-free reproducibility fingerprints differ")
    if any(
        parameter.requires_grad for parameter in shift_engine.generator.parameters()
    ):
        raise AssertionError("reasoning generator parameters must remain frozen")

    def toy_observation(topic: str, stance: float) -> Observation:
        return Observation(topic=topic, stance=stance, text=f"{topic}:{stance:+.2f}")

    multi_observations = [
        toy_observation("context", 0.10),
        toy_observation("claim", 1.00),
        toy_observation("claim", 0.90),
        toy_observation("claim", -0.30),
        toy_observation("claim", -0.30),
        toy_observation("claim", 0.80),
    ]
    budget_config = EBRTConfig(
        seed=23,
        top_k=2,
        revision_steps=12,
        max_events=1,
    )
    budgeted = EventDrivenBackwardReasoner(budget_config).run(multi_observations)
    if [item.source_step for item in budgeted.events] != [3]:
        raise AssertionError(
            "active premise shift was not detected at the expected step"
        )
    if [item.source_step for item in budgeted.suppressed_events] != [5]:
        raise AssertionError("revision-budget suppression was not recorded")
    if len(budgeted.events[0].target_steps) != 2:
        raise AssertionError("top_k=2 did not route to two prior reasoning states")
    if budgeted.event_budget_exhausted is not True or budgeted.unscanned_steps != 0:
        raise AssertionError("budget exhaustion must remain fully auditable")
    if budgeted.revisions[0].energy_after > budgeted.revisions[0].energy_before:
        raise AssertionError("best-checkpoint acceptance allowed an energy regression")
    if len(budgeted.revisions[0].affected_states_before) != len(
        budgeted.revisions[0].affected_states_after
    ):
        raise AssertionError("per-event pre/post trace is incomplete")

    sequential_config = EBRTConfig(
        seed=23,
        top_k=2,
        revision_steps=12,
        max_events=2,
    )
    sequential = EventDrivenBackwardReasoner(sequential_config).run(multi_observations)
    if [item.source_step for item in sequential.events] != [3, 5]:
        raise AssertionError("two sequential premise shifts were not both committed")
    if not all(item.accepted for item in sequential.revisions):
        raise AssertionError("sequential improving revisions must both be accepted")
    first_revision, second_revision = sequential.revisions
    continuity_offset = (
        second_revision.earliest_replay_step - first_revision.earliest_replay_step
    )
    first_after = torch.tensor(first_revision.affected_states_after[continuity_offset])
    second_before = torch.tensor(second_revision.affected_states_before[0])
    _assert_close(
        first_after,
        second_before,
        "second revision must start from the state committed by the first",
    )
    sequential_repeat = EventDrivenBackwardReasoner(sequential_config).run(
        multi_observations
    )
    if (
        sequential.to_dict()["metrics"]["reproducibility_fingerprint"]
        != sequential_repeat.to_dict()["metrics"]["reproducibility_fingerprint"]
    ):
        raise AssertionError("sequential revision fingerprint is not reproducible")

    appended_observations = premise_shift_scenario() + [
        toy_observation("aaa_future_topic", 0.50)
    ]
    appended = EventDrivenBackwardReasoner(config).run(appended_observations)
    _assert_close(
        shifted.final_states,
        appended.final_states[: len(shifted.observations)],
        "future topic append must not alter an already revised prefix",
    )
    _assert_close(
        shifted.controls,
        appended.controls[: len(shifted.observations)],
        "future topic append must not alter earlier controls",
    )

    zero_signal = EventDrivenBackwardReasoner(
        EBRTConfig(event_threshold=0.0, revision_steps=2)
    ).run([toy_observation("x", 1.0), toy_observation("x", 1.0)])
    if zero_signal.events:
        raise AssertionError("zero contradiction must not trigger at threshold zero")
    low_confidence = EventDrivenBackwardReasoner(
        EBRTConfig(event_threshold=0.01, revision_steps=4)
    ).run(
        [
            toy_observation("x", 1.0),
            Observation(
                topic="x",
                stance=-1.0,
                text="weak counterevidence",
                confidence=0.20,
            ),
        ]
    )
    if not low_confidence.events or not math.isclose(
        low_confidence.events[0].revision_target, 0.60, abs_tol=1e-6
    ):
        raise AssertionError("confidence-aware revision target is incorrect")

    preview_then_confirmation = EventDrivenBackwardReasoner(
        EBRTConfig(event_threshold=0.55, revision_steps=4)
    ).run(
        [
            toy_observation("x", 1.0),
            Observation(
                topic="x",
                stance=-1.0,
                text="weak preview",
                confidence=0.20,
            ),
            toy_observation("x", -1.0),
        ]
    )
    if [item.source_step for item in preview_then_confirmation.events] != [2]:
        raise AssertionError(
            "weak preview must not mask a later high-confidence premise shift"
        )

    weak_initial_anchor = EventDrivenBackwardReasoner(
        EBRTConfig(event_threshold=0.55, revision_steps=4)
    ).run(
        [
            Observation(
                topic="x",
                stance=1.0,
                text="unestablished initial guess",
                confidence=0.0,
            ),
            toy_observation("x", -1.0),
            toy_observation("x", 1.0),
            toy_observation("x", -1.0),
        ]
    )
    if [item.source_step for item in weak_initial_anchor.events] != [2, 3]:
        raise AssertionError(
            "weak initial anchor was not promoted before later premise shifts"
        )

    canonical_topics = EventDrivenBackwardReasoner(EBRTConfig(revision_steps=4)).run(
        [
            toy_observation("Foo", 1.0),
            toy_observation(" foo ", -0.30),
        ]
    )
    if len(canonical_topics.decoded["beliefs"]) != 1:
        raise AssertionError("canonical topic decoding emitted duplicates")

    return {
        "status": "PASS",
        "checks": [
            "no-event path equals forward-only",
            "no-event execution uses linear rather than quadratic forward steps",
            "premise shift triggers one sparse backward event",
            "attention targets only earlier states",
            "pre-target states and non-target controls remain unchanged",
            "local energy decreases through real autograd backward calls",
            "best-checkpoint acceptance prevents energy-regressing commits",
            "control update is bounded",
            "frozen generator hash is unchanged",
            "suffix replay changes the final belief in the expected direction",
            "continuous distance to the oracle revision target decreases",
            "decode is called exactly once after revision",
            "same seed reproduces routing, controls, and trajectory",
            "stale evidence does not retrigger; max-event suppression is recorded",
            "top_k=2 and per-event pre/post audit traces are complete",
            "two accepted revisions preserve inter-event state continuity",
            "future topic append leaves the revised prefix exactly unchanged",
            "zero-signal boundary and confidence-aware target are guarded",
            "weak preview cannot mask later high-confidence confirmation",
            "weak initial anchor is promoted instead of permanently locking detection",
            "canonical topic decoding removes case/whitespace duplicates",
        ],
        "mechanism_metrics": {
            "event_score": event.score,
            "target_steps": list(event.target_steps),
            "energy_before": revision.energy_before,
            "energy_after": revision.energy_after,
            "first_grad_norm": revision.first_grad_norm,
            "baseline_load_belief": baseline_belief,
            "revised_load_belief": revised_belief,
            "toy_readout_flipped": readout_flipped,
            "backward_calls": shifted.backward_calls,
            "reproducibility_fingerprint": shifted_fingerprint,
        },
        "claim_boundary": "Mechanism/plumbing validation only; not a reasoning benchmark.",
    }


def _seed_everything(seed: int) -> None:
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    try:
        torch.use_deterministic_algorithms(True)
    except RuntimeError:
        pass


def _resolve_dtype(name: str) -> torch.dtype:
    if name == "float64":
        return torch.float64
    return torch.float32


def _tensor_to_list(value: Tensor) -> list[Any]:
    return value.detach().cpu().tolist()


def _implementation_sha256() -> str:
    return hashlib.sha256(Path(__file__).resolve().read_bytes()).hexdigest()


def _read_observations(path: Path) -> list[Observation]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        payload = payload.get("observations")
    if not isinstance(payload, list):
        raise ValueError("input JSON must be a list or contain an observations list")
    return [Observation.from_mapping(item) for item in payload]


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def _print_result(name: str, result: SessionResult) -> None:
    print(f"\n[{name}] {MODEL_NAME} {MODEL_VERSION}")
    print(
        f"steps={len(result.observations)} revisions={len(result.revisions)} ", end=""
    )
    print(
        f"backward_calls={result.backward_calls} "
        f"generator_steps={result.generator_step_calls} "
        f"decode_calls={result.decode_call_count}"
    )
    if not result.revisions and not result.suppressed_events:
        print("event: none (trajectory unchanged)")
    for index, revision in enumerate(result.revisions, start=1):
        event = revision.event
        print(
            f"event#{index}: {event.kind} at R{event.source_step} "
            f"score={event.score:.3f} -> targets={list(event.target_steps)}"
        )
        print(
            f"  energy {revision.energy_before:.6f} -> "
            f"{revision.energy_after:.6f}; first_grad={revision.first_grad_norm:.6f}; "
            f"accepted={revision.accepted}; rolled_back_to_best={revision.rolled_back}"
        )
        print(
            "  state_delta_norms="
            + ", ".join(
                f"R{i}:{value:.4f}"
                for i, value in enumerate(revision.state_delta_norms)
            )
        )
    for event in result.suppressed_events:
        print(
            f"suppressed: {event.kind} at R{event.source_step} "
            f"score={event.score:.3f} (revision budget exhausted)"
        )
    print(f"decoded once, after revision: {result.decoded['summary']}")
    print(f"frozen core unchanged: {result.core_hash_before == result.core_hash_after}")


def _config_from_args(args: argparse.Namespace) -> EBRTConfig:
    return EBRTConfig(
        seed=args.seed,
        event_threshold=args.event_threshold,
        top_k=args.top_k,
        revision_steps=args.revision_steps,
        revision_lr=args.revision_lr,
        max_control_norm=args.max_control_norm,
        max_events=args.max_events,
        device=args.device,
        dtype=args.dtype,
    )


def _add_runtime_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--event-threshold", type=float, default=0.55)
    parser.add_argument("--top-k", type=int, default=1)
    parser.add_argument("--revision-steps", type=int, default=32)
    parser.add_argument("--revision-lr", type=float, default=0.08)
    parser.add_argument("--max-control-norm", type=float, default=1.75)
    parser.add_argument("--max-events", type=int, default=4)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--dtype", choices=("float32", "float64"), default="float32")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Single-file EBRT v0.1 mechanism demo: event-triggered, sparse, "
            "inference-time latent revision with a frozen generator."
        )
    )
    subparsers = parser.add_subparsers(dest="command")

    demo = subparsers.add_parser("demo", help="run built-in stable/shift scenarios")
    demo.add_argument(
        "--scenario",
        choices=("stable", "premise-shift", "both"),
        default="both",
    )
    demo.add_argument("--output-json", type=Path)
    _add_runtime_arguments(demo)

    run = subparsers.add_parser("run", help="run structured observations from JSON")
    run.add_argument("--input-json", type=Path, required=True)
    run.add_argument("--output-json", type=Path)
    _add_runtime_arguments(run)

    subparsers.add_parser(
        "self-test", help="run deterministic offline mechanism checks"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments == ["--self-test"]:
        arguments = ["self-test"]
    if not arguments:
        arguments = ["demo", "--scenario", "both"]
    args = build_parser().parse_args(arguments)

    if args.command == "self-test":
        report = run_self_tests()
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
        return 0

    config = _config_from_args(args)
    payload: dict[str, Any]
    if args.command == "run":
        observations = _read_observations(args.input_json)
        result = EventDrivenBackwardReasoner(config).run(observations)
        _print_result("run", result)
        payload = result.to_dict()
    elif args.command == "demo":
        scenarios: list[tuple[str, list[Observation]]] = []
        if args.scenario in {"stable", "both"}:
            scenarios.append(("stable", stable_scenario()))
        if args.scenario in {"premise-shift", "both"}:
            scenarios.append(("premise-shift", premise_shift_scenario()))
        results: dict[str, Any] = {}
        for name, observations in scenarios:
            result = EventDrivenBackwardReasoner(config).run(observations)
            _print_result(name, result)
            results[name] = result.to_dict()
        payload = {
            "model": MODEL_NAME,
            "version": MODEL_VERSION,
            "scenarios": results,
        }
    else:
        raise RuntimeError(f"unsupported command: {args.command}")

    if args.output_json:
        _write_json(args.output_json, payload)
        print(f"trace_json={args.output_json.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
