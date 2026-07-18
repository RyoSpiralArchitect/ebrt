#!/usr/bin/env python3
"""Public-state language replay bridge for EBRT v0.4.

This module does not expose, request, or persist private chain-of-thought.  It
operates only on compact public ``ReasoningCard`` checkpoints.  A shared
pre-event trace is forked into three post-event execution lanes:

* card-only forward continuation processes the late evidence once;
* full restart regenerates every public card from an empty checkpoint;
* selective replay preserves a public prefix and regenerates only its suffix.

The replay plan is frozen before any lane executes.  Its inputs are limited to
the public initial trace and a semantic observation of the late evidence; gold
answers and lane outcomes are deliberately absent from this module.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable

from semantic_adapter_v0_2 import (
    AdaptedObservation,
    AdapterProvenance,
    SemanticAdapter,
    StructuredOracleAdapter,
)


SCHEMA_VERSION = "ebrt-language-replay-v0.4"
CARD_SCHEMA_VERSION = "ebrt-public-reasoning-card-v0.4"
DEFAULT_EVENT_THRESHOLD = 0.55
LANES = ("card_only_forward", "full_restart", "selective_replay")


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _nonempty(value: Any, name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{name} must not be empty")
    return text


def _bounded(value: Any, name: str, low: float, high: float) -> float:
    number = float(value)
    if not math.isfinite(number) or not low <= number <= high:
        raise ValueError(f"{name} must be finite and in [{low}, {high}]")
    return number


def _unique_strings(values: Sequence[Any], name: str) -> tuple[str, ...]:
    output = tuple(_nonempty(value, name) for value in values)
    if len(output) != len(set(output)):
        raise ValueError(f"{name} values must be unique")
    return output


@dataclass(frozen=True)
class EvidenceChunk:
    evidence_id: str
    text: str
    semantic: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "evidence_id", _nonempty(self.evidence_id, "evidence_id")
        )
        object.__setattr__(self, "text", _nonempty(self.text, "evidence text"))
        object.__setattr__(self, "semantic", dict(self.semantic))

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "EvidenceChunk":
        return cls(
            evidence_id=value["evidence_id"],
            text=value["text"],
            semantic=value.get("semantic", {}),
        )

    def public_dict(self) -> dict[str, str]:
        return {"evidence_id": self.evidence_id, "text": self.text}

    def trace_dict(self) -> dict[str, Any]:
        return {
            **self.public_dict(),
            "semantic": dict(self.semantic),
        }


@dataclass(frozen=True)
class DecisionSlotSpec:
    slot_id: str
    description: str
    allowed_values: tuple[str, ...]
    required: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "slot_id", _nonempty(self.slot_id, "slot_id"))
        object.__setattr__(
            self,
            "description",
            _nonempty(self.description, "slot description"),
        )
        values = _unique_strings(self.allowed_values, "allowed decision value")
        if "UNKNOWN" not in values:
            values = (*values, "UNKNOWN")
        object.__setattr__(self, "allowed_values", values)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DecisionSlotSpec":
        return cls(
            slot_id=value["slot_id"],
            description=value["description"],
            allowed_values=tuple(value["allowed_values"]),
            required=bool(value.get("required", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    family: str
    question: str
    answer_choices: tuple[str, ...]
    decision_slots: tuple[DecisionSlotSpec, ...]
    initial_evidence: tuple[EvidenceChunk, ...]
    late_evidence: EvidenceChunk

    def __post_init__(self) -> None:
        object.__setattr__(self, "case_id", _nonempty(self.case_id, "case_id"))
        object.__setattr__(self, "family", _nonempty(self.family, "family"))
        object.__setattr__(self, "question", _nonempty(self.question, "question"))
        choices = _unique_strings(self.answer_choices, "answer choice")
        if len(choices) < 2:
            raise ValueError("answer_choices must contain at least two choices")
        object.__setattr__(self, "answer_choices", choices)
        if not self.decision_slots:
            raise ValueError("decision_slots must not be empty")
        slot_ids = [item.slot_id for item in self.decision_slots]
        if len(slot_ids) != len(set(slot_ids)):
            raise ValueError("decision slot IDs must be unique")
        if len(self.initial_evidence) < 2:
            raise ValueError("initial_evidence must contain at least two chunks")
        ids = [item.evidence_id for item in self.initial_evidence]
        ids.append(self.late_evidence.evidence_id)
        if len(ids) != len(set(ids)):
            raise ValueError("evidence IDs must be unique within a case")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "CaseSpec":
        return cls(
            case_id=value["case_id"],
            family=value["family"],
            question=value["question"],
            answer_choices=tuple(value["answer_choices"]),
            decision_slots=tuple(
                DecisionSlotSpec.from_mapping(item) for item in value["decision_slots"]
            ),
            initial_evidence=tuple(
                EvidenceChunk.from_mapping(item) for item in value["initial_evidence"]
            ),
            late_evidence=EvidenceChunk.from_mapping(value["late_evidence"]),
        )

    @property
    def all_evidence(self) -> tuple[EvidenceChunk, ...]:
        return (*self.initial_evidence, self.late_evidence)

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        return tuple(item.evidence_id for item in self.all_evidence)

    def public_context(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer_choices": list(self.answer_choices),
            "decision_slots": [item.to_dict() for item in self.decision_slots],
            "initial_evidence": [item.public_dict() for item in self.initial_evidence],
            "late_evidence": self.late_evidence.public_dict(),
        }

    def trace_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "family": self.family,
            **self.public_context(),
        }


@dataclass(frozen=True)
class DecisionFact:
    slot: str
    value: str
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "slot", _nonempty(self.slot, "fact slot"))
        object.__setattr__(self, "value", _nonempty(self.value, "fact value"))
        object.__setattr__(
            self,
            "evidence_ids",
            _unique_strings(self.evidence_ids, "fact evidence_id"),
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DecisionFact":
        return cls(
            slot=value["slot"],
            value=value["value"],
            evidence_ids=tuple(value["evidence_ids"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class ReasoningCard:
    checkpoint_id: str
    claim: str
    topic: str
    stance: float
    confidence: float
    evidence_ids: tuple[str, ...]
    current_answer: str
    revision_cue: float
    decision_facts: tuple[DecisionFact, ...]
    invalidated_evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("checkpoint_id", "claim", "topic", "current_answer"):
            object.__setattr__(self, name, _nonempty(getattr(self, name), name))
        object.__setattr__(self, "stance", _bounded(self.stance, "stance", -1.0, 1.0))
        object.__setattr__(
            self,
            "confidence",
            _bounded(self.confidence, "confidence", 0.0, 1.0),
        )
        object.__setattr__(
            self,
            "revision_cue",
            _bounded(self.revision_cue, "revision_cue", 0.0, 1.0),
        )
        object.__setattr__(
            self,
            "evidence_ids",
            _unique_strings(self.evidence_ids, "card evidence_id"),
        )
        object.__setattr__(
            self,
            "invalidated_evidence_ids",
            _unique_strings(
                self.invalidated_evidence_ids,
                "invalidated evidence_id",
            ),
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ReasoningCard":
        return cls(
            checkpoint_id=value["checkpoint_id"],
            claim=value["claim"],
            topic=value["topic"],
            stance=value["stance"],
            confidence=value["confidence"],
            evidence_ids=tuple(value["evidence_ids"]),
            current_answer=value["current_answer"],
            revision_cue=value["revision_cue"],
            decision_facts=tuple(
                DecisionFact.from_mapping(item) for item in value["decision_facts"]
            ),
            invalidated_evidence_ids=tuple(value["invalidated_evidence_ids"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": CARD_SCHEMA_VERSION,
            "checkpoint_id": self.checkpoint_id,
            "claim": self.claim,
            "topic": self.topic,
            "stance": self.stance,
            "confidence": self.confidence,
            "evidence_ids": list(self.evidence_ids),
            "current_answer": self.current_answer,
            "revision_cue": self.revision_cue,
            "decision_facts": [item.to_dict() for item in self.decision_facts],
            "invalidated_evidence_ids": list(self.invalidated_evidence_ids),
        }


@dataclass(frozen=True)
class RevisionContext:
    late_evidence: EvidenceChunk
    topic: str
    stance: float
    confidence: float
    revision_cue: float
    relevant: bool
    invalidated_evidence_ids: tuple[str, ...]
    public_summary: str

    def to_provider_dict(self, *, include_late_evidence: bool) -> dict[str, Any]:
        """Expose only routing fields, never the observer's free-form summary."""

        return {
            "late_evidence_id": self.late_evidence.evidence_id,
            "late_evidence": (
                self.late_evidence.public_dict() if include_late_evidence else None
            ),
            "revision_cue": self.revision_cue,
            "relevant": self.relevant,
            "invalidated_evidence_ids": list(self.invalidated_evidence_ids),
        }


@dataclass(frozen=True)
class ProviderUsage:
    exact_provider_tokens: bool
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cached_input_tokens: int | None = None
    cache_write_tokens: int | None = None
    reasoning_tokens: int | None = None

    def __post_init__(self) -> None:
        for name in (
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "cached_input_tokens",
            "cache_write_tokens",
            "reasoning_tokens",
        ):
            value = getattr(self, name)
            if value is not None and int(value) < 0:
                raise ValueError(f"{name} must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class ProviderReceipt:
    provider: str
    requested_model: str | None
    returned_model: str | None
    logical_calls: int
    api_calls: int
    latency_ms: float
    request_fingerprint: str
    prompt_fingerprint: str
    usage: ProviderUsage
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.logical_calls < 0 or self.api_calls < 0:
            raise ValueError("call counts must be non-negative")
        if not math.isfinite(self.latency_ms) or self.latency_ms < 0.0:
            raise ValueError("latency_ms must be finite and non-negative")
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "requested_model": self.requested_model,
            "returned_model": self.returned_model,
            "logical_calls": self.logical_calls,
            "api_calls": self.api_calls,
            "latency_ms": self.latency_ms,
            "request_fingerprint": self.request_fingerprint,
            "prompt_fingerprint": self.prompt_fingerprint,
            "usage": self.usage.to_dict(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class CardRequest:
    case_id: str
    question: str
    answer_choices: tuple[str, ...]
    decision_slots: tuple[DecisionSlotSpec, ...]
    checkpoint_id: str
    previous_public_card: ReasoningCard | None
    current_evidence: EvidenceChunk
    revision_context: RevisionContext | None
    allowed_evidence_ids: tuple[str, ...]

    def to_provider_input(self) -> dict[str, Any]:
        """Return the lane-neutral, gold-free payload seen by a provider."""

        return {
            "question": self.question,
            "answer_choices": list(self.answer_choices),
            "decision_slots": [item.to_dict() for item in self.decision_slots],
            "checkpoint_id": self.checkpoint_id,
            "previous_public_card": (
                None
                if self.previous_public_card is None
                else self.previous_public_card.to_dict()
            ),
            "current_evidence": self.current_evidence.public_dict(),
            "revision_context": (
                None
                if self.revision_context is None
                else self.revision_context.to_provider_dict(
                    include_late_evidence=(
                        self.current_evidence.evidence_id
                        != self.revision_context.late_evidence.evidence_id
                    )
                )
            ),
            "allowed_evidence_ids": list(self.allowed_evidence_ids),
        }

    @property
    def request_fingerprint(self) -> str:
        return fingerprint(self.to_provider_input())


@dataclass(frozen=True)
class CardResult:
    card: ReasoningCard
    receipt: ProviderReceipt

    def to_dict(self) -> dict[str, Any]:
        return {"card": self.card.to_dict(), "receipt": self.receipt.to_dict()}


@runtime_checkable
class ReasoningProvider(Protocol):
    @property
    def provenance(self) -> Mapping[str, Any]: ...

    def generate(self, request: CardRequest) -> CardResult: ...


@dataclass(frozen=True)
class RevisionObservation:
    adapted: AdaptedObservation
    relevant: bool
    invalidated_evidence_ids: tuple[str, ...]
    public_summary: str
    receipt: ProviderReceipt

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "invalidated_evidence_ids",
            _unique_strings(
                self.invalidated_evidence_ids,
                "observer invalidated evidence_id",
            ),
        )
        object.__setattr__(
            self,
            "public_summary",
            _nonempty(self.public_summary, "public_summary"),
        )

    def to_dict(self, provenance: AdapterProvenance) -> dict[str, Any]:
        return {
            "adapted_observation": self.adapted.to_trace_dict(provenance),
            "relevant": self.relevant,
            "invalidated_evidence_ids": list(self.invalidated_evidence_ids),
            "public_summary": self.public_summary,
            "receipt": self.receipt.to_dict(),
        }


@runtime_checkable
class RevisionObserver(Protocol):
    @property
    def provenance(self) -> AdapterProvenance: ...

    def observe_revision(
        self,
        case: CaseSpec,
        initial_cards: Sequence[ReasoningCard],
    ) -> RevisionObservation: ...


class StructuredRevisionObserver:
    """DEV-only structured observer layered on the existing v0.2 adapter."""

    def __init__(self) -> None:
        self._adapter = StructuredOracleAdapter()
        self._provenance = AdapterProvenance(
            adapter_name="StructuredRevisionObserver",
            adapter_version="0.4",
            provider="local",
            model=None,
            semantic_source="structured_oracle_dev_only",
            deterministic=True,
            parameters={"base_schema": "ebrt-semantic-observation-v0.2"},
        )

    @property
    def provenance(self) -> AdapterProvenance:
        return self._provenance

    def observe(
        self,
        chunk: Mapping[str, Any],
        *,
        source_id: str | None = None,
    ) -> AdaptedObservation:
        return self._adapter.observe(chunk, source_id=source_id)

    def observe_many(
        self,
        chunks: Sequence[Mapping[str, Any]],
    ) -> list[AdaptedObservation]:
        return [
            self.observe(chunk, source_id=f"structured-revision:{index}")
            for index, chunk in enumerate(chunks)
        ]

    def observe_revision(
        self,
        case: CaseSpec,
        initial_cards: Sequence[ReasoningCard],
    ) -> RevisionObservation:
        del initial_cards
        semantic = dict(case.late_evidence.semantic)
        adapted = self.observe(semantic, source_id=case.late_evidence.evidence_id)
        relevant = bool(semantic.get("relevant", adapted.revision_cue >= 0.5))
        invalidated = tuple(semantic.get("invalidated_evidence_ids", ()))
        summary = str(
            semantic.get(
                "public_summary",
                f"Late evidence concerns {adapted.topic}.",
            )
        )
        request_material = {
            "case": case.public_context(),
            "late_semantic": semantic,
        }
        receipt = ProviderReceipt(
            provider="local_structured_oracle",
            requested_model=None,
            returned_model=None,
            logical_calls=1,
            api_calls=0,
            latency_ms=0.0,
            request_fingerprint=fingerprint(request_material),
            prompt_fingerprint=fingerprint("structured-oracle-v0.4"),
            usage=ProviderUsage(exact_provider_tokens=False),
            metadata={"non_language_oracle": True},
        )
        return RevisionObservation(
            adapted=adapted,
            relevant=relevant,
            invalidated_evidence_ids=invalidated,
            public_summary=summary,
            receipt=receipt,
        )


@dataclass(frozen=True)
class ReplayPlan:
    event_triggered: bool
    event_threshold: float
    selected_anchor_step: int | None
    selected_anchor_evidence_id: str | None
    execution_replay_floor: int
    checkpoint_step: int | None
    selection_mode: str
    invalidated_evidence_ids: tuple[str, ...]
    decision_input_fingerprint: str
    plan_fingerprint: str
    pre_outcome: bool = True
    trajectory_horizon_status: str = "shadow_only_not_executed"
    shadow_trajectory_anchor_floor: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def build_replay_plan(
    case: CaseSpec,
    initial_cards: Sequence[ReasoningCard],
    observation: RevisionObservation,
    *,
    event_threshold: float = DEFAULT_EVENT_THRESHOLD,
) -> ReplayPlan:
    """Freeze a replay decision before any counterfactual lane executes."""

    if len(initial_cards) != len(case.initial_evidence):
        raise ValueError("initial card/evidence lengths do not match")
    threshold = _bounded(event_threshold, "event_threshold", 0.0, 1.0)
    initial_ids = tuple(item.evidence_id for item in case.initial_evidence)
    unknown = set(observation.invalidated_evidence_ids) - set(initial_ids)
    if unknown:
        raise ValueError(
            f"observer returned unknown invalidated evidence IDs: {sorted(unknown)}"
        )

    event_triggered = bool(
        observation.relevant and observation.adapted.revision_cue >= threshold
    )
    selected_step: int | None
    selected_id: str | None
    if not event_triggered:
        floor = len(case.initial_evidence)
        selected_step = None
        selected_id = None
        mode = "no_backward_replay"
    elif observation.invalidated_evidence_ids:
        floor = min(
            initial_ids.index(item) for item in observation.invalidated_evidence_ids
        )
        selected_step = floor
        selected_id = initial_ids[floor]
        mode = "public_invalidated_evidence"
    else:
        floor = 0
        selected_step = 0
        selected_id = initial_ids[0]
        mode = "fail_closed_full_restart"

    checkpoint_step = floor - 1 if floor > 0 else None
    decision_input = {
        "case": case.public_context(),
        "initial_cards": [item.to_dict() for item in initial_cards],
        "observer": {
            "topic": observation.adapted.topic,
            "stance": observation.adapted.stance,
            "confidence": observation.adapted.confidence,
            "revision_cue": observation.adapted.revision_cue,
            "relevant": observation.relevant,
            "invalidated_evidence_ids": list(observation.invalidated_evidence_ids),
            "public_summary": observation.public_summary,
        },
        "event_threshold": threshold,
    }
    decision_fingerprint = fingerprint(decision_input)
    plan_material = {
        "event_triggered": event_triggered,
        "event_threshold": threshold,
        "selected_anchor_step": selected_step,
        "selected_anchor_evidence_id": selected_id,
        "execution_replay_floor": floor,
        "checkpoint_step": checkpoint_step,
        "selection_mode": mode,
        "invalidated_evidence_ids": list(observation.invalidated_evidence_ids),
        "decision_input_fingerprint": decision_fingerprint,
        "pre_outcome": True,
        "trajectory_horizon_status": "shadow_only_not_executed",
        "shadow_trajectory_anchor_floor": floor if event_triggered else None,
    }
    return ReplayPlan(
        **plan_material,
        plan_fingerprint=fingerprint(plan_material),
    )


class ScriptedReasoningProvider:
    """Deterministic gold-backed provider used only for bridge plumbing tests."""

    def __init__(self, scripted_states: Mapping[str, Mapping[str, Any]]) -> None:
        self._states = {
            str(case_id): json.loads(canonical_json(value))
            for case_id, value in scripted_states.items()
        }
        self._provenance = {
            "provider": "local_scripted_gold",
            "model": None,
            "deterministic": True,
            "semantic_source": "machine_gold_plumbing_only",
            "token_counts": "not_estimated",
        }

    @property
    def provenance(self) -> Mapping[str, Any]:
        return dict(self._provenance)

    def generate(self, request: CardRequest) -> CardResult:
        if request.case_id not in self._states:
            raise KeyError(f"missing scripted state for {request.case_id}")
        states = self._states[request.case_id]
        state_name = "final" if request.revision_context is not None else "initial"
        state = states[state_name]
        allowed = set(request.allowed_evidence_ids)
        revision_invalidated = (
            set(request.revision_context.invalidated_evidence_ids)
            if request.revision_context is not None
            else set()
        )
        support_ids = [item for item in state["evidence_ids"] if item in allowed]
        if (
            request.current_evidence.evidence_id not in support_ids
            and request.current_evidence.evidence_id not in revision_invalidated
        ):
            support_ids.append(request.current_evidence.evidence_id)
        invalidated = [
            item
            for item in state.get("invalidated_evidence_ids", [])
            if item in allowed
        ]
        facts: list[DecisionFact] = []
        for raw_fact in state["decision_facts"]:
            cited = tuple(item for item in raw_fact["evidence_ids"] if item in allowed)
            if cited:
                facts.append(
                    DecisionFact(
                        slot=raw_fact["slot"],
                        value=raw_fact["value"],
                        evidence_ids=cited,
                    )
                )
        observed_slots = {item.slot for item in facts}
        for slot in request.decision_slots:
            if slot.required and slot.slot_id not in observed_slots:
                facts.append(
                    DecisionFact(
                        slot=slot.slot_id,
                        value="UNKNOWN",
                        evidence_ids=(),
                    )
                )
        card = ReasoningCard(
            checkpoint_id=request.checkpoint_id,
            claim=state["claim"],
            topic=state["topic"],
            stance=state["stance"],
            confidence=state["confidence"],
            evidence_ids=tuple(support_ids),
            current_answer=state["answer"],
            revision_cue=state["revision_cue"],
            decision_facts=tuple(facts),
            invalidated_evidence_ids=tuple(invalidated),
        )
        receipt = ProviderReceipt(
            provider="local_scripted_gold",
            requested_model=None,
            returned_model=None,
            logical_calls=1,
            api_calls=0,
            latency_ms=0.0,
            request_fingerprint=request.request_fingerprint,
            prompt_fingerprint=fingerprint("scripted-public-card-v0.4"),
            usage=ProviderUsage(exact_provider_tokens=False),
            metadata={"plumbing_only": True},
        )
        return CardResult(card=card, receipt=receipt)


def _validate_card_result(
    request: CardRequest,
    result: CardResult,
) -> None:
    card = result.card
    if result.receipt.request_fingerprint != request.request_fingerprint:
        raise ValueError("provider receipt/request fingerprint mismatch")
    if card.checkpoint_id != request.checkpoint_id:
        raise ValueError("provider returned the wrong checkpoint_id")
    if card.current_answer not in request.answer_choices:
        raise ValueError("provider returned an answer outside answer_choices")
    slot_values = {
        item.slot_id: set(item.allowed_values) for item in request.decision_slots
    }
    observed_slots: set[str] = set()
    for fact in card.decision_facts:
        if fact.slot in observed_slots:
            raise ValueError(f"provider returned duplicate decision slot: {fact.slot}")
        observed_slots.add(fact.slot)
        if fact.slot not in slot_values:
            raise ValueError(f"provider returned unknown decision slot: {fact.slot}")
        if fact.value not in slot_values[fact.slot]:
            raise ValueError(
                f"provider returned disallowed value for decision slot {fact.slot}: {fact.value}"
            )
    missing_required_slots = {
        item.slot_id for item in request.decision_slots if item.required
    } - observed_slots
    if missing_required_slots:
        raise ValueError(
            f"provider omitted required decision slots: {sorted(missing_required_slots)}"
        )
    allowed = set(request.allowed_evidence_ids)
    cited = set(card.evidence_ids) | set(card.invalidated_evidence_ids)
    for fact in card.decision_facts:
        cited.update(fact.evidence_ids)
    unknown = cited - allowed
    if unknown:
        raise ValueError(
            f"provider cited unknown/unavailable evidence IDs: {sorted(unknown)}"
        )
    permitted_invalidated = (
        set(request.revision_context.invalidated_evidence_ids)
        if request.revision_context is not None
        else set()
    )
    active_support = set(card.evidence_ids)
    for fact in card.decision_facts:
        active_support.update(fact.evidence_ids)
    invalidated_support = active_support & permitted_invalidated
    if invalidated_support:
        raise ValueError(
            "provider used invalidated evidence as active support: "
            f"{sorted(invalidated_support)}"
        )
    unexpected_invalidated = set(card.invalidated_evidence_ids) - permitted_invalidated
    if unexpected_invalidated:
        raise ValueError(
            "provider marked evidence invalidated outside the public revision context: "
            f"{sorted(unexpected_invalidated)}"
        )


def _aggregate_receipts(receipts: Sequence[ProviderReceipt]) -> dict[str, Any]:
    exact = bool(receipts) and all(
        item.usage.exact_provider_tokens for item in receipts
    )

    def sum_optional(name: str) -> int | None:
        values = [getattr(item.usage, name) for item in receipts]
        if not exact or any(value is None for value in values):
            return None
        return sum(int(value) for value in values if value is not None)

    return {
        "logical_calls": sum(item.logical_calls for item in receipts),
        "api_calls": sum(item.api_calls for item in receipts),
        "latency_ms": sum(item.latency_ms for item in receipts),
        "exact_provider_tokens": exact,
        "input_tokens": sum_optional("input_tokens"),
        "output_tokens": sum_optional("output_tokens"),
        "total_tokens": sum_optional("total_tokens"),
        "cached_input_tokens": sum_optional("cached_input_tokens"),
        "cache_write_tokens": sum_optional("cache_write_tokens"),
        "reasoning_tokens": sum_optional("reasoning_tokens"),
    }


def _sum_accounting(*values: Mapping[str, Any]) -> dict[str, Any]:
    exact = bool(values) and all(bool(item["exact_provider_tokens"]) for item in values)
    output: dict[str, Any] = {
        "logical_calls": sum(int(item["logical_calls"]) for item in values),
        "api_calls": sum(int(item["api_calls"]) for item in values),
        "latency_ms": sum(float(item["latency_ms"]) for item in values),
        "exact_provider_tokens": exact,
    }
    for name in (
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cached_input_tokens",
        "cache_write_tokens",
        "reasoning_tokens",
    ):
        parts = [item.get(name) for item in values]
        output[name] = (
            sum(int(value) for value in parts if value is not None)
            if exact and all(value is not None for value in parts)
            else None
        )
    return output


def _public_support_ids(card: ReasoningCard | None) -> tuple[str, ...]:
    if card is None:
        return ()
    output: list[str] = []
    for evidence_id in card.evidence_ids:
        if evidence_id not in output:
            output.append(evidence_id)
    for fact in card.decision_facts:
        for evidence_id in fact.evidence_ids:
            if evidence_id not in output:
                output.append(evidence_id)
    return tuple(output)


def _run_sequence(
    *,
    case: CaseSpec,
    provider: ReasoningProvider,
    phase: str,
    evidence: Sequence[EvidenceChunk],
    base_cards: Sequence[ReasoningCard],
    revision_context: RevisionContext | None,
) -> tuple[list[ReasoningCard], list[dict[str, Any]]]:
    cards = list(base_cards)
    records: list[dict[str, Any]] = []
    visible_order = list(_public_support_ids(cards[-1] if cards else None))
    all_case_ids = set(case.evidence_ids)
    for step_offset, chunk in enumerate(evidence):
        allowed_order = list(visible_order)
        if chunk.evidence_id not in allowed_order:
            allowed_order.append(chunk.evidence_id)
        if revision_context is not None:
            for evidence_id in revision_context.invalidated_evidence_ids:
                if evidence_id not in allowed_order:
                    allowed_order.append(evidence_id)
            if revision_context.late_evidence.evidence_id not in allowed_order:
                allowed_order.append(revision_context.late_evidence.evidence_id)
        if not set(allowed_order) <= all_case_ids:
            raise AssertionError("allowed evidence set escaped case boundary")
        request = CardRequest(
            case_id=case.case_id,
            question=case.question,
            answer_choices=case.answer_choices,
            decision_slots=case.decision_slots,
            checkpoint_id=f"card:{chunk.evidence_id}",
            previous_public_card=cards[-1] if cards else None,
            current_evidence=chunk,
            revision_context=revision_context,
            allowed_evidence_ids=tuple(allowed_order),
        )
        result = provider.generate(request)
        _validate_card_result(request, result)
        cards.append(result.card)
        visible_order = list(_public_support_ids(result.card))
        records.append(
            {
                "phase": phase,
                "sequence_offset": step_offset,
                "current_evidence_id": chunk.evidence_id,
                "request_fingerprint": request.request_fingerprint,
                **result.to_dict(),
            }
        )
    return cards, records


def _lane_payload(
    *,
    lane: str,
    cards: Sequence[ReasoningCard],
    records: Sequence[Mapping[str, Any]],
    plan: ReplayPlan,
    common_accounting: Mapping[str, Any],
    observer_accounting: Mapping[str, Any],
) -> dict[str, Any]:
    receipts = [
        ProviderReceipt(
            provider=item["receipt"]["provider"],
            requested_model=item["receipt"]["requested_model"],
            returned_model=item["receipt"]["returned_model"],
            logical_calls=item["receipt"]["logical_calls"],
            api_calls=item["receipt"]["api_calls"],
            latency_ms=item["receipt"]["latency_ms"],
            request_fingerprint=item["receipt"]["request_fingerprint"],
            prompt_fingerprint=item["receipt"]["prompt_fingerprint"],
            usage=ProviderUsage(**item["receipt"]["usage"]),
            metadata=item["receipt"]["metadata"],
        )
        for item in records
    ]
    branch = _aggregate_receipts(receipts)
    counterfactual_parts = [common_accounting, observer_accounting, branch]
    return {
        "lane": lane,
        "plan_fingerprint": plan.plan_fingerprint,
        "cards": [item.to_dict() for item in cards],
        "final_card": cards[-1].to_dict(),
        "branch_calls": list(records),
        "regenerated_cards": len(records),
        "common_initial_accounting": dict(common_accounting),
        "observer_accounting_included": True,
        "branch_accounting": branch,
        "counterfactual_total_accounting": _sum_accounting(*counterfactual_parts),
    }


def execute_language_replay_case(
    case: CaseSpec,
    *,
    provider: ReasoningProvider,
    observer: RevisionObserver,
    lane_order: Sequence[str] = LANES,
    event_threshold: float = DEFAULT_EVENT_THRESHOLD,
) -> dict[str, Any]:
    """Execute one shared trace, freeze a plan, then run all three lanes."""

    lane_order = tuple(lane_order)
    if set(lane_order) != set(LANES) or len(lane_order) != len(LANES):
        raise ValueError(f"lane_order must contain each lane exactly once: {LANES}")
    initial_cards, initial_records = _run_sequence(
        case=case,
        provider=provider,
        phase="shared_initial_forward",
        evidence=case.initial_evidence,
        base_cards=(),
        revision_context=None,
    )
    if len(initial_cards) != len(case.initial_evidence):
        raise AssertionError("shared initial trace length invariant failed")
    observation = observer.observe_revision(case, initial_cards)
    plan = build_replay_plan(
        case,
        initial_cards,
        observation,
        event_threshold=event_threshold,
    )
    if plan.checkpoint_step != (
        plan.execution_replay_floor - 1 if plan.execution_replay_floor > 0 else None
    ):
        raise AssertionError("checkpoint/replay-floor off-by-one invariant failed")
    revision_context = RevisionContext(
        late_evidence=case.late_evidence,
        topic=observation.adapted.topic,
        stance=observation.adapted.stance,
        confidence=observation.adapted.confidence,
        revision_cue=observation.adapted.revision_cue,
        relevant=observation.relevant,
        invalidated_evidence_ids=observation.invalidated_evidence_ids,
        public_summary=observation.public_summary,
    )
    initial_receipts = [
        ProviderReceipt(
            provider=item["receipt"]["provider"],
            requested_model=item["receipt"]["requested_model"],
            returned_model=item["receipt"]["returned_model"],
            logical_calls=item["receipt"]["logical_calls"],
            api_calls=item["receipt"]["api_calls"],
            latency_ms=item["receipt"]["latency_ms"],
            request_fingerprint=item["receipt"]["request_fingerprint"],
            prompt_fingerprint=item["receipt"]["prompt_fingerprint"],
            usage=ProviderUsage(**item["receipt"]["usage"]),
            metadata=item["receipt"]["metadata"],
        )
        for item in initial_records
    ]
    common_accounting = _aggregate_receipts(initial_receipts)
    observer_accounting = _aggregate_receipts([observation.receipt])

    lanes: dict[str, Any] = {}
    all_branch_receipts: list[ProviderReceipt] = []
    for lane in lane_order:
        if lane == "card_only_forward":
            evidence = (case.late_evidence,)
            base_cards = initial_cards
        elif lane == "full_restart":
            evidence = case.all_evidence
            base_cards = ()
        else:
            floor = plan.execution_replay_floor
            evidence = (*case.initial_evidence[floor:], case.late_evidence)
            base_cards = initial_cards[:floor]
        cards, records = _run_sequence(
            case=case,
            provider=provider,
            phase=lane,
            evidence=evidence,
            base_cards=base_cards,
            revision_context=revision_context,
        )
        lane_payload = _lane_payload(
            lane=lane,
            cards=cards,
            records=records,
            plan=plan,
            common_accounting=common_accounting,
            observer_accounting=observer_accounting,
        )
        lanes[lane] = lane_payload
        for item in records:
            receipt = item["receipt"]
            all_branch_receipts.append(
                ProviderReceipt(
                    provider=receipt["provider"],
                    requested_model=receipt["requested_model"],
                    returned_model=receipt["returned_model"],
                    logical_calls=receipt["logical_calls"],
                    api_calls=receipt["api_calls"],
                    latency_ms=receipt["latency_ms"],
                    request_fingerprint=receipt["request_fingerprint"],
                    prompt_fingerprint=receipt["prompt_fingerprint"],
                    usage=ProviderUsage(**receipt["usage"]),
                    metadata=receipt["metadata"],
                )
            )

    expected_work = {
        "card_only_forward": 1,
        "full_restart": len(case.initial_evidence) + 1,
        "selective_replay": (
            len(case.initial_evidence) - plan.execution_replay_floor + 1
        ),
    }
    observed_work = {
        lane: int(payload["regenerated_cards"]) for lane, payload in lanes.items()
    }
    if observed_work != expected_work:
        raise AssertionError(
            f"lane replay work invariant failed: expected={expected_work} observed={observed_work}"
        )
    if {payload["plan_fingerprint"] for payload in lanes.values()} != {
        plan.plan_fingerprint
    }:
        raise AssertionError("lanes did not share one frozen replay plan")

    physical_accounting = _sum_accounting(
        common_accounting,
        observer_accounting,
        _aggregate_receipts(all_branch_receipts),
    )
    trace: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "case": case.trace_dict(),
        "case_input_fingerprint": fingerprint(case.public_context()),
        "provider_provenance": dict(provider.provenance),
        "observer_provenance": observer.provenance.to_dict(),
        "lane_order": list(lane_order),
        "shared_initial_trace": [item.to_dict() for item in initial_cards],
        "shared_initial_calls": initial_records,
        "common_initial_accounting": common_accounting,
        "revision_observation": observation.to_dict(observer.provenance),
        "replay_plan": plan.to_dict(),
        "lanes": lanes,
        "physical_experiment_accounting": physical_accounting,
        "claim_boundary": [
            "Card-only forward is a public-card continuation control, not a universal baseline for chat models.",
            "Selective replay edits public checkpoints only; no hidden states or private chain-of-thought are accessed.",
            "The replay plan is pre-outcome, but this DEV bridge does not establish improved LLM reasoning accuracy.",
            "The adaptive trajectory horizon is shadow-only and does not affect v0.4 routing.",
        ],
    }
    trace["trace_fingerprint"] = fingerprint(trace)
    serialized = canonical_json(trace)
    if "OPENAI_API_KEY" in serialized or "Authorization" in serialized:
        raise AssertionError("secret-bearing field leaked into trace")
    return trace


def run_self_tests() -> dict[str, Any]:
    case = CaseSpec.from_mapping(
        {
            "case_id": "self_test",
            "family": "self_test",
            "question": "Choose OLD or NEW.",
            "answer_choices": ["OLD", "NEW"],
            "decision_slots": [
                {
                    "slot_id": "value",
                    "description": "current value",
                    "allowed_values": ["old", "new"],
                }
            ],
            "initial_evidence": [
                {"evidence_id": "E1", "text": "Stable rule."},
                {"evidence_id": "E2", "text": "The value is old."},
                {"evidence_id": "E3", "text": "Map old to OLD."},
            ],
            "late_evidence": {
                "evidence_id": "E4",
                "text": "Correction: the value is new; E2 is superseded.",
                "semantic": {
                    "topic": "value",
                    "stance": -1.0,
                    "confidence": 1.0,
                    "revision_cue": 1.0,
                    "relevant": True,
                    "invalidated_evidence_ids": ["E2"],
                    "public_summary": "E4 supersedes E2.",
                },
            },
        }
    )
    states = {
        "self_test": {
            "initial": {
                "answer": "OLD",
                "claim": "The old mapping applies.",
                "topic": "value",
                "stance": 1.0,
                "confidence": 0.8,
                "revision_cue": 0.0,
                "evidence_ids": ["E1", "E2", "E3"],
                "invalidated_evidence_ids": [],
                "decision_facts": [
                    {"slot": "value", "value": "old", "evidence_ids": ["E2"]}
                ],
            },
            "final": {
                "answer": "NEW",
                "claim": "The correction changes the value.",
                "topic": "value",
                "stance": -1.0,
                "confidence": 1.0,
                "revision_cue": 1.0,
                "evidence_ids": ["E1", "E3", "E4"],
                "invalidated_evidence_ids": ["E2"],
                "decision_facts": [
                    {"slot": "value", "value": "new", "evidence_ids": ["E4"]}
                ],
            },
        }
    }
    provider = ScriptedReasoningProvider(states)
    observer = StructuredRevisionObserver()
    if not isinstance(observer, SemanticAdapter):
        raise AssertionError("structured revision observer broke SemanticAdapter")
    if not isinstance(provider, ReasoningProvider):
        raise AssertionError("scripted provider broke ReasoningProvider")
    first = execute_language_replay_case(case, provider=provider, observer=observer)
    second = execute_language_replay_case(case, provider=provider, observer=observer)
    if canonical_json(first) != canonical_json(second):
        raise AssertionError("scripted language replay is not byte deterministic")
    plan = first["replay_plan"]
    if plan["execution_replay_floor"] != 1 or plan["checkpoint_step"] != 0:
        raise AssertionError("public checkpoint selection failed")
    expected = {
        "card_only_forward": 1,
        "full_restart": 4,
        "selective_replay": 3,
    }
    observed = {
        lane: payload["regenerated_cards"] for lane, payload in first["lanes"].items()
    }
    if observed != expected:
        raise AssertionError("lane work geometry failed")
    if any(
        payload["plan_fingerprint"] != plan["plan_fingerprint"]
        for payload in first["lanes"].values()
    ):
        raise AssertionError("plan fingerprint diverged across lanes")

    observation = observer.observe_revision(
        case,
        initial_cards=(ReasoningCard.from_mapping(first["shared_initial_trace"][-1]),),
    )
    revision_context = RevisionContext(
        late_evidence=case.late_evidence,
        topic=observation.adapted.topic,
        stance=observation.adapted.stance,
        confidence=observation.adapted.confidence,
        revision_cue=observation.adapted.revision_cue,
        relevant=observation.relevant,
        invalidated_evidence_ids=observation.invalidated_evidence_ids,
        public_summary="TRACE_ONLY_SENTINEL",
    )
    compressed_card = ReasoningCard(
        checkpoint_id="card:E3",
        claim="Only the currently public support remains.",
        topic="value",
        stance=1.0,
        confidence=0.8,
        evidence_ids=("E1", "E2"),
        current_answer="OLD",
        revision_cue=0.0,
        decision_facts=(DecisionFact(slot="value", value="old", evidence_ids=("E2",)),),
        invalidated_evidence_ids=(),
    )
    visible_support = _public_support_ids(compressed_card)
    if visible_support != ("E1", "E2"):
        raise AssertionError("public support aperture retained a ghost evidence ID")
    request = CardRequest(
        case_id=case.case_id,
        question=case.question,
        answer_choices=case.answer_choices,
        decision_slots=case.decision_slots,
        checkpoint_id="card:E4",
        previous_public_card=compressed_card,
        current_evidence=case.late_evidence,
        revision_context=revision_context,
        allowed_evidence_ids=(*visible_support, "E4"),
    )
    provider_input = request.to_provider_input()
    if "public_summary" in canonical_json(provider_input):
        raise AssertionError("observer summary leaked into provider input")
    if canonical_json(provider_input).count(case.late_evidence.text) != 1:
        raise AssertionError("late evidence was duplicated in final provider input")

    receipt = ProviderReceipt(
        provider="self_test",
        requested_model=None,
        returned_model=None,
        logical_calls=1,
        api_calls=0,
        latency_ms=0.0,
        request_fingerprint=request.request_fingerprint,
        prompt_fingerprint=fingerprint("self-test"),
        usage=ProviderUsage(exact_provider_tokens=False),
    )
    base_result = CardResult(
        card=ReasoningCard(
            checkpoint_id=request.checkpoint_id,
            claim="The correction changes the value.",
            topic="value",
            stance=-1.0,
            confidence=1.0,
            evidence_ids=("E4",),
            current_answer="NEW",
            revision_cue=1.0,
            decision_facts=(
                DecisionFact(slot="value", value="new", evidence_ids=("E4",)),
            ),
            invalidated_evidence_ids=("E2",),
        ),
        receipt=receipt,
    )
    _validate_card_result(request, base_result)

    def expect_card_rejection(card: ReasoningCard, label: str) -> None:
        try:
            _validate_card_result(request, CardResult(card=card, receipt=receipt))
        except ValueError:
            return
        raise AssertionError(f"provider boundary accepted {label}")

    expect_card_rejection(
        dataclasses.replace(base_result.card, evidence_ids=("E3", "E4")),
        "a ghost citation omitted from the previous public card",
    )
    expect_card_rejection(
        dataclasses.replace(base_result.card, evidence_ids=("E2", "E4")),
        "invalidated evidence as active support",
    )
    return {
        "status": "PASS",
        "schema_version": SCHEMA_VERSION,
        "checks": [
            "existing SemanticAdapter compatibility",
            "pre-outcome replay-plan fingerprint",
            "anchor/checkpoint off-by-one invariant",
            "three-lane replay work geometry",
            "public-card-only citation aperture",
            "invalidated active-support rejection",
            "observer-summary exclusion and single late-evidence payload",
            "deterministic scripted trace",
            "secret-field trace sentinel",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(run_self_tests(), ensure_ascii=False, indent=2))
