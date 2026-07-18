#!/usr/bin/env python3
"""OpenAI Responses API providers for the EBRT v0.4 public-state bridge.

Only strict public schemas are persisted.  Raw response objects, opaque
reasoning items, API keys, and Authorization headers are never serialized.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import sys
import time
import uuid
from typing import Annotated, Any, Mapping, Sequence

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field

from language_replay_bridge_v0_4 import (
    AdaptedObservation,
    AdapterProvenance,
    CardRequest,
    CardResult,
    CaseSpec,
    DecisionFact,
    ProviderReceipt,
    ProviderUsage,
    ReasoningCard,
    RevisionObservation,
    canonical_json,
    fingerprint,
)


DEFAULT_MODEL = "gpt-5.6-sol"
DEFAULT_REASONING_EFFORT = "low"
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_CARD_OUTPUT_TOKENS = 768
DEFAULT_MAX_OBSERVER_OUTPUT_TOKENS = 512


CARD_INSTRUCTIONS = """\
Produce one compact PUBLIC decision-state card. Do not provide private chain-of-thought,
hidden reasoning, or a prose derivation. Update the previous public card using only the
current evidence and, when present, the public revision context. The current_answer must
exactly equal one supplied answer choice. Cite only allowed evidence IDs. Invalidated or
superseded evidence must not be used as active support; list it only in
invalidated_evidence_ids. That list must be a subset of the IDs explicitly named in the
public revision context; never infer extra invalidations. For decision_facts, use every required decision slot exactly once,
copy its slot_id exactly, and choose only an exact allowed value; use UNKNOWN until a value
is supported. Keep these public facts externally checkable and sufficient to audit the
answer. Return only the strict structured output.
"""


OBSERVER_INSTRUCTIONS = """\
Produce one compact PUBLIC semantic observation of the late evidence. Do not provide
private chain-of-thought or hidden reasoning. Decide whether the late evidence could
affect the question or current public answer, including a relevant correction that leaves
the final answer unchanged. List only prior evidence IDs that the late evidence explicitly
invalidates, supersedes, revokes, or corrects. If it is relevant but no prior ID can be
identified safely, leave invalidated_evidence_ids empty so the controller can fail closed.
The current public card is the only prior semantic state: do not reconstruct, summarize,
or quote unavailable earlier evidence. The public_summary may summarize the late evidence
and invalidation decision only; it must not calculate a new answer or add prior facts.
Return only the strict structured output.
"""


class DecisionFactPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot: Annotated[str, Field(min_length=1)]
    value: Annotated[str, Field(min_length=1)]
    evidence_ids: list[Annotated[str, Field(min_length=1)]]


class ReasoningCardPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    checkpoint_id: Annotated[str, Field(min_length=1)]
    claim: Annotated[str, Field(min_length=1)]
    topic: Annotated[str, Field(min_length=1)]
    stance: Annotated[float, Field(ge=-1.0, le=1.0)]
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    evidence_ids: Annotated[
        list[Annotated[str, Field(min_length=1)]],
        Field(min_length=1),
    ]
    current_answer: Annotated[str, Field(min_length=1)]
    revision_cue: Annotated[float, Field(ge=0.0, le=1.0)]
    decision_facts: list[DecisionFactPayload]
    invalidated_evidence_ids: list[Annotated[str, Field(min_length=1)]]


class RevisionObservationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: Annotated[str, Field(min_length=1)]
    stance: Annotated[float, Field(ge=-1.0, le=1.0)]
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    revision_cue: Annotated[float, Field(ge=0.0, le=1.0)]
    relevant: bool
    invalidated_evidence_ids: list[Annotated[str, Field(min_length=1)]]
    public_summary: Annotated[str, Field(min_length=1)]


class OpenAIResponseContractError(RuntimeError):
    """The provider returned a refusal, incomplete result, or invalid contract."""


class OpenAIProviderCallError(RuntimeError):
    """A sanitized provider failure paired with its counted call receipt."""

    def __init__(self, category: str, receipt: ProviderReceipt) -> None:
        super().__init__(f"OpenAI provider call failed: {category}")
        self.category = str(category)
        self.receipt = receipt


def _hash_identifier(value: Any) -> str | None:
    if value is None:
        return None
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _extract_refusals(response: Any) -> list[str]:
    refusals: list[str] = []
    for item in getattr(response, "output", ()) or ():
        if getattr(item, "type", None) != "message":
            continue
        for content in getattr(item, "content", ()) or ():
            if getattr(content, "type", None) == "refusal":
                refusals.append(str(getattr(content, "refusal", "provider refusal")))
    return refusals


def _validate_completed_response(response: Any) -> None:
    refusals = _extract_refusals(response)
    if refusals:
        raise OpenAIResponseContractError(
            f"provider refusal ({len(refusals)} public refusal item(s))"
        )
    status = getattr(response, "status", None)
    if status != "completed":
        raise OpenAIResponseContractError(
            f"response status is not completed: {status!r}"
        )
    if getattr(response, "error", None) is not None:
        raise OpenAIResponseContractError("response contains a provider error")
    if getattr(response, "incomplete_details", None) is not None:
        raise OpenAIResponseContractError("response contains incomplete_details")
    if getattr(response, "output_parsed", None) is None:
        raise OpenAIResponseContractError("response has no parsed structured output")


def _usage_from_response(response: Any) -> ProviderUsage:
    usage = getattr(response, "usage", None)
    if usage is None:
        raise OpenAIResponseContractError("completed response did not include usage")
    input_details = getattr(usage, "input_tokens_details", None)
    output_details = getattr(usage, "output_tokens_details", None)
    return ProviderUsage(
        exact_provider_tokens=True,
        input_tokens=int(usage.input_tokens),
        output_tokens=int(usage.output_tokens),
        total_tokens=int(usage.total_tokens),
        cached_input_tokens=int(getattr(input_details, "cached_tokens", 0) or 0),
        cache_write_tokens=int(getattr(input_details, "cache_write_tokens", 0) or 0),
        reasoning_tokens=int(getattr(output_details, "reasoning_tokens", 0) or 0),
    )


def _usage_or_unavailable(response: Any) -> ProviderUsage:
    try:
        return _usage_from_response(response)
    except Exception:
        return ProviderUsage(exact_provider_tokens=False)


class _ResponsesClientBase:
    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        reasoning_effort: str = DEFAULT_REASONING_EFFORT,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        client: OpenAI | None = None,
    ) -> None:
        self.model = str(model)
        self.reasoning_effort = str(reasoning_effort)
        self.timeout_seconds = float(timeout_seconds)
        if self.timeout_seconds <= 0.0:
            raise ValueError("timeout_seconds must be positive")
        self.client = client or OpenAI(
            max_retries=0,
            timeout=self.timeout_seconds,
        )
        self.sdk_version = importlib.metadata.version("openai")
        self._audit_receipts: list[dict[str, Any]] = []

    @property
    def audit_receipts(self) -> list[dict[str, Any]]:
        return json.loads(canonical_json(self._audit_receipts))

    def _receipt(
        self,
        *,
        request_fingerprint: str,
        prompt_fingerprint: str,
        client_request_id: str,
        max_output_tokens: int,
        latency_ms: float,
        response: Any | None,
        usage: ProviderUsage,
        outcome: str,
        failure_type: str | None = None,
    ) -> ProviderReceipt:
        receipt = ProviderReceipt(
            provider="openai_responses",
            requested_model=self.model,
            returned_model=(
                None
                if response is None
                else str(getattr(response, "model", "")) or None
            ),
            logical_calls=1,
            api_calls=1,
            latency_ms=latency_ms,
            request_fingerprint=request_fingerprint,
            prompt_fingerprint=prompt_fingerprint,
            usage=usage,
            metadata={
                "status": (
                    "transport_error"
                    if response is None
                    else str(getattr(response, "status", ""))
                ),
                "service_tier": (
                    None
                    if response is None
                    else getattr(response, "service_tier", None)
                ),
                "response_id_sha256": (
                    None
                    if response is None
                    else _hash_identifier(getattr(response, "id", None))
                ),
                "server_request_id_sha256": (
                    None
                    if response is None
                    else _hash_identifier(getattr(response, "_request_id", None))
                ),
                "client_request_id_sha256": _hash_identifier(client_request_id),
                "reasoning_effort": self.reasoning_effort,
                "max_output_tokens": int(max_output_tokens),
                "store": False,
                "previous_response_id": False,
                "truncation": "disabled",
                "sdk_version": self.sdk_version,
                "python_version": sys.version.split()[0],
                "attempt": 1,
                "retry_count": 0,
                "api_call_count_semantics": "attempted_client_call",
                "attempt_outcome": outcome,
                "failure_type": failure_type,
                "refusal_count": (
                    0 if response is None else len(_extract_refusals(response))
                ),
            },
        )
        self._audit_receipts.append(receipt.to_dict())
        return receipt

    def _parse(
        self,
        *,
        input_payload: Mapping[str, Any],
        instructions: str,
        text_format: type[BaseModel],
        max_output_tokens: int,
    ) -> tuple[Any, ProviderReceipt]:
        request_fingerprint = fingerprint(input_payload)
        prompt_fingerprint = fingerprint(instructions)
        client_request_id = str(uuid.uuid4())
        started = time.perf_counter()
        try:
            response = self.client.responses.parse(
                model=self.model,
                instructions=instructions,
                input=canonical_json(input_payload),
                text_format=text_format,
                reasoning={"effort": self.reasoning_effort},
                max_output_tokens=int(max_output_tokens),
                store=False,
                service_tier="default",
                truncation="disabled",
                extra_headers={"X-Client-Request-Id": client_request_id},
                timeout=self.timeout_seconds,
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - started) * 1000.0
            receipt = self._receipt(
                request_fingerprint=request_fingerprint,
                prompt_fingerprint=prompt_fingerprint,
                client_request_id=client_request_id,
                max_output_tokens=max_output_tokens,
                latency_ms=latency_ms,
                response=None,
                usage=ProviderUsage(exact_provider_tokens=False),
                outcome="transport_error",
                failure_type=type(exc).__name__,
            )
            raise OpenAIProviderCallError("transport_error", receipt) from exc
        latency_ms = (time.perf_counter() - started) * 1000.0
        try:
            _validate_completed_response(response)
            usage = _usage_from_response(response)
        except OpenAIResponseContractError as exc:
            receipt = self._receipt(
                request_fingerprint=request_fingerprint,
                prompt_fingerprint=prompt_fingerprint,
                client_request_id=client_request_id,
                max_output_tokens=max_output_tokens,
                latency_ms=latency_ms,
                response=response,
                usage=_usage_or_unavailable(response),
                outcome="contract_error",
                failure_type=type(exc).__name__,
            )
            raise OpenAIProviderCallError("contract_error", receipt) from exc
        receipt = self._receipt(
            request_fingerprint=request_fingerprint,
            prompt_fingerprint=prompt_fingerprint,
            client_request_id=client_request_id,
            max_output_tokens=max_output_tokens,
            latency_ms=latency_ms,
            response=response,
            usage=usage,
            outcome="completed",
        )
        return response.output_parsed, receipt


class OpenAIResponsesReasoningProvider(_ResponsesClientBase):
    """Generate strict public Reasoning Cards with the Responses API."""

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        reasoning_effort: str = DEFAULT_REASONING_EFFORT,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_output_tokens: int = DEFAULT_MAX_CARD_OUTPUT_TOKENS,
        client: OpenAI | None = None,
    ) -> None:
        super().__init__(
            model=model,
            reasoning_effort=reasoning_effort,
            timeout_seconds=timeout_seconds,
            client=client,
        )
        self.max_output_tokens = int(max_output_tokens)
        if self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")
        self._provenance = {
            "provider": "openai_responses",
            "model": self.model,
            "api": "responses.parse",
            "structured_output": "pydantic_v2",
            "reasoning_effort": self.reasoning_effort,
            "max_output_tokens_per_card": self.max_output_tokens,
            "store": False,
            "previous_response_id": False,
            "service_tier": "default",
            "truncation": "disabled",
            "retries": 0,
            "instructions_fingerprint": fingerprint(CARD_INSTRUCTIONS),
            "sdk_version": self.sdk_version,
        }

    @property
    def provenance(self) -> Mapping[str, Any]:
        return dict(self._provenance)

    def generate(self, request: CardRequest) -> CardResult:
        payload, receipt = self._parse(
            input_payload=request.to_provider_input(),
            instructions=CARD_INSTRUCTIONS,
            text_format=ReasoningCardPayload,
            max_output_tokens=self.max_output_tokens,
        )
        if not isinstance(payload, ReasoningCardPayload):
            raise OpenAIResponseContractError("parsed card has the wrong runtime type")
        card = ReasoningCard(
            checkpoint_id=payload.checkpoint_id,
            claim=payload.claim,
            topic=payload.topic,
            stance=payload.stance,
            confidence=payload.confidence,
            evidence_ids=tuple(payload.evidence_ids),
            current_answer=payload.current_answer,
            revision_cue=payload.revision_cue,
            decision_facts=tuple(
                DecisionFact(
                    slot=item.slot,
                    value=item.value,
                    evidence_ids=tuple(item.evidence_ids),
                )
                for item in payload.decision_facts
            ),
            invalidated_evidence_ids=tuple(payload.invalidated_evidence_ids),
        )
        return CardResult(card=card, receipt=receipt)


def _build_observer_input(
    case: CaseSpec,
    initial_cards: Sequence[ReasoningCard],
) -> dict[str, Any]:
    if not initial_cards:
        raise ValueError("initial_cards must not be empty")
    return {
        "question": case.question,
        "answer_choices": list(case.answer_choices),
        "current_public_card": initial_cards[-1].to_dict(),
        "late_evidence": case.late_evidence.public_dict(),
        "allowed_prior_evidence_ids": [
            item.evidence_id for item in case.initial_evidence
        ],
    }


class OpenAIResponsesSemanticAdapter(_ResponsesClientBase):
    """GPT-backed late-evidence observer compatible with SemanticAdapter v0.2."""

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        reasoning_effort: str = DEFAULT_REASONING_EFFORT,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_output_tokens: int = DEFAULT_MAX_OBSERVER_OUTPUT_TOKENS,
        client: OpenAI | None = None,
    ) -> None:
        super().__init__(
            model=model,
            reasoning_effort=reasoning_effort,
            timeout_seconds=timeout_seconds,
            client=client,
        )
        self.max_output_tokens = int(max_output_tokens)
        if self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")
        self._provenance = AdapterProvenance(
            adapter_name="OpenAIResponsesSemanticAdapter",
            adapter_version="0.4",
            provider="openai_responses",
            model=self.model,
            semantic_source="gpt_public_structured_observer",
            deterministic=False,
            parameters={
                "api": "responses.parse",
                "reasoning_effort": self.reasoning_effort,
                "max_output_tokens": self.max_output_tokens,
                "store": False,
                "previous_response_id": False,
                "service_tier": "default",
                "truncation": "disabled",
                "retries": 0,
                "instructions_fingerprint": fingerprint(OBSERVER_INSTRUCTIONS),
                "sdk_version": self.sdk_version,
            },
        )

    @property
    def provenance(self) -> AdapterProvenance:
        return self._provenance

    def _observe_payload(
        self,
        chunk: Mapping[str, Any],
        *,
        source_id: str,
    ) -> RevisionObservation:
        payload, receipt = self._parse(
            input_payload=chunk,
            instructions=OBSERVER_INSTRUCTIONS,
            text_format=RevisionObservationPayload,
            max_output_tokens=self.max_output_tokens,
        )
        if not isinstance(payload, RevisionObservationPayload):
            raise OpenAIResponseContractError(
                "parsed semantic observation has the wrong runtime type"
            )
        late = chunk["late_evidence"]
        input_digest = fingerprint(chunk)
        adapted = AdaptedObservation(
            topic=payload.topic,
            stance=payload.stance,
            text=str(late["text"]),
            confidence=payload.confidence,
            revision_cue=payload.revision_cue,
            source_id=source_id,
            input_sha256=input_digest,
        )
        return RevisionObservation(
            adapted=adapted,
            relevant=payload.relevant,
            invalidated_evidence_ids=tuple(payload.invalidated_evidence_ids),
            public_summary=payload.public_summary,
            receipt=receipt,
        )

    def observe(
        self,
        chunk: Mapping[str, Any],
        *,
        source_id: str | None = None,
    ) -> AdaptedObservation:
        late = chunk.get("late_evidence")
        if not isinstance(late, Mapping):
            raise ValueError("GPT observer input requires late_evidence mapping")
        resolved_source = source_id or str(late.get("evidence_id", "late-evidence"))
        return self._observe_payload(chunk, source_id=resolved_source).adapted

    def observe_many(
        self,
        chunks: Sequence[Mapping[str, Any]],
    ) -> list[AdaptedObservation]:
        return [self.observe(chunk) for chunk in chunks]

    def observe_revision(
        self,
        case: CaseSpec,
        initial_cards: Sequence[ReasoningCard],
    ) -> RevisionObservation:
        chunk = _build_observer_input(case, initial_cards)
        return self._observe_payload(
            chunk,
            source_id=case.late_evidence.evidence_id,
        )


def schema_self_test() -> dict[str, Any]:
    card_schema = ReasoningCardPayload.model_json_schema()
    observer_schema = RevisionObservationPayload.model_json_schema()
    if card_schema.get("additionalProperties") is not False:
        raise AssertionError("card schema must forbid extra fields")
    if observer_schema.get("additionalProperties") is not False:
        raise AssertionError("observer schema must forbid extra fields")
    if "OPENAI_API_KEY" in canonical_json(
        {"card": card_schema, "observer": observer_schema}
    ):
        raise AssertionError("schema unexpectedly contains a secret field")
    aperture_case = CaseSpec.from_mapping(
        {
            "case_id": "observer_aperture",
            "family": "self_test",
            "question": "Choose A or B.",
            "answer_choices": ["A", "B"],
            "decision_slots": [
                {
                    "slot_id": "choice",
                    "description": "selected choice",
                    "allowed_values": ["A", "B"],
                }
            ],
            "initial_evidence": [
                {"evidence_id": "O1", "text": "RAW_INITIAL_SENTINEL_ONE"},
                {"evidence_id": "O2", "text": "RAW_INITIAL_SENTINEL_TWO"},
            ],
            "late_evidence": {"evidence_id": "O3", "text": "Late correction."},
        }
    )
    aperture_card = ReasoningCard(
        checkpoint_id="card:O2",
        claim="The public card contains only a bounded claim.",
        topic="choice",
        stance=0.0,
        confidence=0.5,
        evidence_ids=("O2",),
        current_answer="A",
        revision_cue=0.0,
        decision_facts=(DecisionFact(slot="choice", value="A", evidence_ids=("O2",)),),
        invalidated_evidence_ids=(),
    )
    observer_input = _build_observer_input(aperture_case, (aperture_card,))
    serialized_observer_input = canonical_json(observer_input)
    if "initial_evidence" in observer_input:
        raise AssertionError("raw initial evidence collection leaked to observer")
    if "RAW_INITIAL_SENTINEL_ONE" in serialized_observer_input:
        raise AssertionError("unpreserved raw initial text leaked to observer")
    if set(observer_input) != {
        "question",
        "answer_choices",
        "current_public_card",
        "late_evidence",
        "allowed_prior_evidence_ids",
    }:
        raise AssertionError("observer aperture drifted from the locked contract")
    return {
        "status": "PASS",
        "model": DEFAULT_MODEL,
        "sdk_version": importlib.metadata.version("openai"),
        "checks": [
            "strict Pydantic public-card schema",
            "strict Pydantic semantic-observer schema",
            "observer excludes raw initial evidence and sees only terminal public state",
            "no private response serialization path",
            "explicit no-retry and stateless Responses configuration",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(schema_self_test(), ensure_ascii=False, indent=2))
