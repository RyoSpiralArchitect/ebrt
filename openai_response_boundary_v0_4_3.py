#!/usr/bin/env python3
"""Prospective OpenAI Responses boundary instrumentation for EBRT v0.4.3.

This module deliberately leaves the frozen v0.4 provider untouched.  Under the
exact pinned OpenAI SDK it splits one logical request into two observable local
boundaries:

1. ``responses.with_raw_response.parse(...)`` acquires the HTTP response; and
2. ``raw.parse()`` applies the SDK Response and structured-output parsers.

Only allowlisted diagnostics and hashes enter receipts.  Raw response bodies,
exception messages, response headers, rejected cards, credentials, and private
reasoning are never serialized.  There is no retry or compatibility fallback.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import sys
import time
import uuid
from dataclasses import dataclass
from json import JSONDecodeError
from types import SimpleNamespace
from typing import Any, Mapping

from openai import (
    APIConnectionError,
    APIResponseValidationError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    ConflictError,
    InternalServerError,
    NotFoundError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
    UnprocessableEntityError,
)
from pydantic import BaseModel, ValidationError

from language_replay_bridge_v0_4 import (
    CardResult,
    DecisionFact,
    ProviderReceipt,
    ProviderUsage,
    ReasoningCard,
    canonical_json,
    fingerprint,
)
from openai_reasoning_provider_v0_4 import (
    ReasoningCardPayload,
    _ResponsesClientBase,
    _usage_from_response,
    _usage_or_unavailable,
)


RECEIPT_SCHEMA_VERSION = "ebrt-provider-boundary-receipt-v0.4.3"
EXPECTED_OPENAI_SDK_VERSION = "2.45.0"
EXPECTED_PYDANTIC_VERSION = "2.12.5"

BOUNDARY_PHASES = (
    "request_call",
    "http_status",
    "sdk_response_parse",
    "provider_contract",
)

BOUNDARY_REASON_CODES_BY_PHASE = {
    "request_call": frozenset({"timeout", "connection", "request_unclassified"}),
    "http_status": frozenset(
        {
            "authentication",
            "permission_denied",
            "not_found",
            "bad_request",
            "conflict",
            "unprocessable_entity",
            "insufficient_quota",
            "rate_limit",
            "unknown429",
            "server_error",
            "http_other",
        }
    ),
    "sdk_response_parse": frozenset(
        {
            "sdk_http_envelope_validation",
            "sdk_structured_parse_validation",
            "sdk_response_decode",
            "sdk_parse_unclassified",
        }
    ),
    "provider_contract": frozenset(
        {
            "provider_refusal",
            "provider_status_non_completed",
            "provider_error",
            "provider_incomplete",
            "missing_structured_output",
            "missing_exact_usage",
            "wrong_runtime",
        }
    ),
}
BOUNDARY_REASON_CODES = tuple(
    sorted(
        reason
        for reasons in BOUNDARY_REASON_CODES_BY_PHASE.values()
        for reason in reasons
    )
)

_ALLOWED_API_ERROR_CODES = frozenset(
    {
        "insufficient_quota",
        "rate_limit",
        "rate_limit_exceeded",
    }
)
_ALLOWED_PROVIDER_STATUSES = frozenset(
    {
        "completed",
        "incomplete",
        "failed",
        "cancelled",
        "queued",
        "in_progress",
    }
)
_ALLOWED_SERVICE_TIERS = frozenset(
    {
        "auto",
        "default",
        "flex",
        "scale",
        "priority",
    }
)


class OpenAIBoundaryCapabilityError(RuntimeError):
    """Fail-closed construction error raised before any provider call."""

    category = "provider_boundary_capability_error"
    phase = "capability"

    def __init__(self, reason_code: str) -> None:
        super().__init__(f"OpenAI boundary capability unavailable: {reason_code}")
        self.reason_code = str(reason_code)


class OpenAIProviderBoundaryError(RuntimeError):
    """Sanitized, non-assessable provider-boundary failure with one receipt."""

    category = "provider_boundary_error"

    def __init__(
        self,
        *,
        phase: str,
        reason_code: str,
        receipt: ProviderReceipt,
    ) -> None:
        if phase not in BOUNDARY_PHASES:
            raise AssertionError("unknown v0.4.3 boundary phase")
        if reason_code not in BOUNDARY_REASON_CODES_BY_PHASE[phase]:
            raise AssertionError("phase-incompatible v0.4.3 boundary reason code")
        super().__init__(f"OpenAI provider boundary failed: {reason_code}")
        self.phase = phase
        self.reason_code = reason_code
        self.receipt = receipt


def _hash_identifier(value: Any) -> str | None:
    if value is None:
        return None
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _safe_int(value: Any) -> int | None:
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if result >= 0 else None


@dataclass(frozen=True)
class _SafeHTTPObservation:
    observed: bool
    status_code: int | None = None
    response_body_sha256: str | None = None
    response_body_bytes: int | None = None
    server_request_id_sha256: str | None = None


def _safe_http_observation(value: Any | None) -> _SafeHTTPObservation:
    """Read only status, request-id hash, and body digest from a response.

    ``value`` may be the SDK raw wrapper or an ``httpx.Response`` attached to
    an ``APIStatusError``.  No body text, JSON field, or header is returned.
    """

    if value is None:
        return _SafeHTTPObservation(observed=False)
    response = getattr(value, "http_response", value)
    status_code = _safe_int(getattr(value, "status_code", None))
    if status_code is None:
        status_code = _safe_int(getattr(response, "status_code", None))
    if status_code is not None and not 100 <= status_code <= 599:
        status_code = None

    request_id = getattr(value, "request_id", None)
    if request_id is None:
        try:
            request_id = response.headers.get("x-request-id")
        except Exception:
            request_id = None

    try:
        content = bytes(getattr(value, "content"))
    except Exception:
        try:
            content = bytes(response.content)
        except Exception:
            content = None
    return _SafeHTTPObservation(
        observed=status_code is not None or content is not None or request_id is not None,
        status_code=status_code,
        response_body_sha256=(
            None if content is None else hashlib.sha256(content).hexdigest()
        ),
        response_body_bytes=None if content is None else len(content),
        server_request_id_sha256=_hash_identifier(request_id),
    )


def _safe_provider_status(response: Any | None) -> str | None:
    if response is None:
        return None
    value = str(getattr(response, "status", ""))
    return value if value in _ALLOWED_PROVIDER_STATUSES else "other"


def _safe_service_tier(response: Any | None) -> str | None:
    if response is None:
        return None
    value = getattr(response, "service_tier", None)
    if value is None:
        return None
    text = str(value)
    return text if text in _ALLOWED_SERVICE_TIERS else "other"


def _safe_returned_model(response: Any | None) -> str | None:
    if response is None:
        return None
    value = getattr(response, "model", None)
    if value is None:
        return None
    text = str(value)
    return text if text and len(text) <= 128 else None


def _refusal_count(response: Any | None) -> int:
    count = 0
    for item in getattr(response, "output", ()) or ():
        if getattr(item, "type", None) != "message":
            continue
        for content in getattr(item, "content", ()) or ():
            if getattr(content, "type", None) == "refusal":
                count += 1
    return count


def _classify_http_status(error: APIStatusError) -> str:
    status = _safe_int(getattr(error, "status_code", None))
    if isinstance(error, AuthenticationError) or status == 401:
        return "authentication"
    if isinstance(error, PermissionDeniedError) or status == 403:
        return "permission_denied"
    if isinstance(error, NotFoundError) or status == 404:
        return "not_found"
    if isinstance(error, RateLimitError) or status == 429:
        code = getattr(error, "code", None)
        safe_code = (
            code
            if isinstance(code, str) and code in _ALLOWED_API_ERROR_CODES
            else None
        )
        if safe_code == "insufficient_quota":
            return "insufficient_quota"
        if safe_code in {"rate_limit", "rate_limit_exceeded"}:
            return "rate_limit"
        return "unknown429"
    if isinstance(error, BadRequestError) or status == 400:
        return "bad_request"
    if isinstance(error, ConflictError) or status == 409:
        return "conflict"
    if isinstance(error, UnprocessableEntityError) or status == 422:
        return "unprocessable_entity"
    if isinstance(error, InternalServerError) or (
        status is not None and 500 <= status <= 599
    ):
        return "server_error"
    return "http_other"


def _provider_contract_reason(
    response: Any,
    *,
    text_format: type[BaseModel],
    requested_model: str,
    expected_service_tier: str,
) -> str | None:
    if _refusal_count(response):
        return "provider_refusal"
    if getattr(response, "error", None) is not None:
        return "provider_error"
    if getattr(response, "incomplete_details", None) is not None:
        return "provider_incomplete"
    if getattr(response, "status", None) != "completed":
        return "provider_status_non_completed"
    payload = getattr(response, "output_parsed", None)
    if payload is None:
        return "missing_structured_output"
    if not isinstance(payload, text_format):
        return "wrong_runtime"
    if getattr(response, "model", None) != requested_model:
        return "wrong_runtime"
    observed_service_tier = getattr(response, "service_tier", None)
    if observed_service_tier != expected_service_tier:
        return "wrong_runtime"
    return None


def _reasoning_card_from_payload(payload: ReasoningCardPayload) -> ReasoningCard:
    return ReasoningCard(
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


class InstrumentedResponsesClientBase(_ResponsesClientBase):
    """Pinned two-stage Responses client that emits one sanitized receipt."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._finalized_client_request_ids: set[str] = set()
        self._raw_parse = self._require_boundary_capability()

    def _require_boundary_capability(self) -> Any:
        if self.sdk_version != EXPECTED_OPENAI_SDK_VERSION:
            raise OpenAIBoundaryCapabilityError("openai_sdk_version_mismatch")
        try:
            pydantic_version = importlib.metadata.version("pydantic")
        except Exception:
            raise OpenAIBoundaryCapabilityError(
                "pydantic_version_unavailable"
            ) from None
        if pydantic_version != EXPECTED_PYDANTIC_VERSION:
            raise OpenAIBoundaryCapabilityError("pydantic_version_mismatch")
        if getattr(self.client, "max_retries", None) != 0:
            raise OpenAIBoundaryCapabilityError("client_retry_policy_not_zero")
        try:
            method = self.client.responses.with_raw_response.parse
        except Exception:
            raise OpenAIBoundaryCapabilityError(
                "with_raw_response_parse_unavailable"
            ) from None
        if not callable(method):
            raise OpenAIBoundaryCapabilityError(
                "with_raw_response_parse_unavailable"
            )
        return method

    def _finalize_receipt(
        self,
        *,
        request_fingerprint: str,
        prompt_fingerprint: str,
        text_schema_fingerprint: str,
        request_arguments_fingerprint: str,
        client_request_id: str,
        max_output_tokens: int,
        latency_ms: float,
        http: _SafeHTTPObservation,
        response: Any | None,
        usage: ProviderUsage,
        attempt_outcome: str,
        status_label: str,
        parse_boundary: str,
        failure_phase: str | None,
        failure_reason_code: str | None,
    ) -> ProviderReceipt:
        if client_request_id in self._finalized_client_request_ids:
            raise AssertionError("one provider attempt emitted multiple receipts")
        if (failure_phase is None) != (failure_reason_code is None):
            raise AssertionError("boundary phase and reason must be paired")
        if failure_phase is not None and failure_phase not in BOUNDARY_PHASES:
            raise AssertionError("receipt contains an unknown boundary phase")
        if failure_reason_code is not None and failure_reason_code not in (
            BOUNDARY_REASON_CODES_BY_PHASE[failure_phase]
        ):
            raise AssertionError("receipt contains a phase-incompatible boundary reason")

        receipt = ProviderReceipt(
            provider="openai_responses",
            requested_model=self.model,
            returned_model=_safe_returned_model(response),
            logical_calls=1,
            api_calls=1,
            latency_ms=latency_ms,
            request_fingerprint=request_fingerprint,
            prompt_fingerprint=prompt_fingerprint,
            usage=usage,
            metadata={
                "receipt_schema_version": RECEIPT_SCHEMA_VERSION,
                "status": status_label,
                "service_tier": _safe_service_tier(response),
                "response_id_sha256": _hash_identifier(
                    None if response is None else getattr(response, "id", None)
                ),
                "server_request_id_sha256": http.server_request_id_sha256,
                "client_request_id_sha256": _hash_identifier(client_request_id),
                "provider_body_sha256": http.response_body_sha256,
                "provider_body_byte_count": http.response_body_bytes,
                "http_observed": http.observed,
                "http_status_code": http.status_code,
                "parse_boundary": parse_boundary,
                "failure_phase": failure_phase,
                "failure_reason_code": failure_reason_code,
                "failure_type": failure_reason_code,
                "response_schema_fingerprint": text_schema_fingerprint,
                "semantic_protocol_fingerprint": request_arguments_fingerprint,
                "reasoning_effort": self.reasoning_effort,
                "max_output_tokens": int(max_output_tokens),
                "store": False,
                "previous_response_id": False,
                "truncation": "disabled",
                "sdk_version": self.sdk_version,
                "pydantic_version": importlib.metadata.version("pydantic"),
                "python_version": sys.version.split()[0],
                "attempt": 1,
                "retry_count": 0,
                "api_call_count_semantics": "attempted_client_call",
                "attempt_outcome": attempt_outcome,
                "refusal_count": _refusal_count(response),
            },
        )
        self._finalized_client_request_ids.add(client_request_id)
        self._audit_receipts.append(receipt.to_dict())
        return receipt

    def _raise_failure(
        self,
        *,
        phase: str,
        reason_code: str,
        request_fingerprint: str,
        prompt_fingerprint: str,
        text_schema_fingerprint: str,
        request_arguments_fingerprint: str,
        client_request_id: str,
        max_output_tokens: int,
        latency_ms: float,
        http: _SafeHTTPObservation,
        response: Any | None = None,
        usage: ProviderUsage | None = None,
        parse_boundary: str,
    ) -> None:
        if phase == "request_call":
            outcome = "transport_error"
            status = "no_http_response"
        elif phase == "http_status":
            outcome = "http_status_error"
            status = "http_status_error"
        elif phase == "sdk_response_parse":
            outcome = "sdk_parse_error"
            status = "http_success_unparsed" if http.observed else "sdk_parse_error"
        else:
            outcome = "contract_error"
            status = _safe_provider_status(response) or "provider_contract_error"
        receipt = self._finalize_receipt(
            request_fingerprint=request_fingerprint,
            prompt_fingerprint=prompt_fingerprint,
            text_schema_fingerprint=text_schema_fingerprint,
            request_arguments_fingerprint=request_arguments_fingerprint,
            client_request_id=client_request_id,
            max_output_tokens=max_output_tokens,
            latency_ms=latency_ms,
            http=http,
            response=response,
            usage=usage or ProviderUsage(exact_provider_tokens=False),
            attempt_outcome=outcome,
            status_label=status,
            parse_boundary=parse_boundary,
            failure_phase=phase,
            failure_reason_code=reason_code,
        )
        raise OpenAIProviderBoundaryError(
            phase=phase,
            reason_code=reason_code,
            receipt=receipt,
        ) from None

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
        text_schema_fingerprint = fingerprint(text_format.model_json_schema())
        request_arguments_fingerprint = fingerprint(
            {
                "model": self.model,
                "instructions_fingerprint": prompt_fingerprint,
                "input_fingerprint": request_fingerprint,
                "text_schema_fingerprint": text_schema_fingerprint,
                "reasoning": {"effort": self.reasoning_effort},
                "max_output_tokens": int(max_output_tokens),
                "store": False,
                "service_tier": "default",
                "truncation": "disabled",
                "timeout_seconds": self.timeout_seconds,
            }
        )
        client_request_id = str(uuid.uuid4())
        started = time.perf_counter()

        try:
            raw = self._raw_parse(
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
        except APITimeoutError:
            self._raise_failure(
                phase="request_call",
                reason_code="timeout",
                request_fingerprint=request_fingerprint,
                prompt_fingerprint=prompt_fingerprint,
                text_schema_fingerprint=text_schema_fingerprint,
                request_arguments_fingerprint=request_arguments_fingerprint,
                client_request_id=client_request_id,
                max_output_tokens=max_output_tokens,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                http=_SafeHTTPObservation(observed=False),
                parse_boundary="not_entered",
            )
        except APIConnectionError:
            self._raise_failure(
                phase="request_call",
                reason_code="connection",
                request_fingerprint=request_fingerprint,
                prompt_fingerprint=prompt_fingerprint,
                text_schema_fingerprint=text_schema_fingerprint,
                request_arguments_fingerprint=request_arguments_fingerprint,
                client_request_id=client_request_id,
                max_output_tokens=max_output_tokens,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                http=_SafeHTTPObservation(observed=False),
                parse_boundary="not_entered",
            )
        except APIStatusError as error:
            self._raise_failure(
                phase="http_status",
                reason_code=_classify_http_status(error),
                request_fingerprint=request_fingerprint,
                prompt_fingerprint=prompt_fingerprint,
                text_schema_fingerprint=text_schema_fingerprint,
                request_arguments_fingerprint=request_arguments_fingerprint,
                client_request_id=client_request_id,
                max_output_tokens=max_output_tokens,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                http=_safe_http_observation(getattr(error, "response", None)),
                parse_boundary="not_entered",
            )
        except APIResponseValidationError as error:
            self._raise_failure(
                phase="sdk_response_parse",
                reason_code="sdk_http_envelope_validation",
                request_fingerprint=request_fingerprint,
                prompt_fingerprint=prompt_fingerprint,
                text_schema_fingerprint=text_schema_fingerprint,
                request_arguments_fingerprint=request_arguments_fingerprint,
                client_request_id=client_request_id,
                max_output_tokens=max_output_tokens,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                http=_safe_http_observation(getattr(error, "response", None)),
                parse_boundary="not_entered",
            )
        except Exception:
            self._raise_failure(
                phase="request_call",
                reason_code="request_unclassified",
                request_fingerprint=request_fingerprint,
                prompt_fingerprint=prompt_fingerprint,
                text_schema_fingerprint=text_schema_fingerprint,
                request_arguments_fingerprint=request_arguments_fingerprint,
                client_request_id=client_request_id,
                max_output_tokens=max_output_tokens,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                http=_SafeHTTPObservation(observed=False),
                parse_boundary="not_entered",
            )

        http = _safe_http_observation(raw)
        parse_method = getattr(raw, "parse", None)
        if not callable(parse_method):
            self._raise_failure(
                phase="sdk_response_parse",
                reason_code="sdk_parse_unclassified",
                request_fingerprint=request_fingerprint,
                prompt_fingerprint=prompt_fingerprint,
                text_schema_fingerprint=text_schema_fingerprint,
                request_arguments_fingerprint=request_arguments_fingerprint,
                client_request_id=client_request_id,
                max_output_tokens=max_output_tokens,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                http=http,
                parse_boundary="failed_after_http",
            )
        try:
            response = parse_method()
        except ValidationError as error:
            reason = (
                "sdk_structured_parse_validation"
                if getattr(error, "title", None) == text_format.__name__
                else "sdk_http_envelope_validation"
            )
            self._raise_failure(
                phase="sdk_response_parse",
                reason_code=reason,
                request_fingerprint=request_fingerprint,
                prompt_fingerprint=prompt_fingerprint,
                text_schema_fingerprint=text_schema_fingerprint,
                request_arguments_fingerprint=request_arguments_fingerprint,
                client_request_id=client_request_id,
                max_output_tokens=max_output_tokens,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                http=http,
                parse_boundary="failed_after_http",
            )
        except JSONDecodeError:
            self._raise_failure(
                phase="sdk_response_parse",
                reason_code="sdk_response_decode",
                request_fingerprint=request_fingerprint,
                prompt_fingerprint=prompt_fingerprint,
                text_schema_fingerprint=text_schema_fingerprint,
                request_arguments_fingerprint=request_arguments_fingerprint,
                client_request_id=client_request_id,
                max_output_tokens=max_output_tokens,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                http=http,
                parse_boundary="failed_after_http",
            )
        except APIResponseValidationError:
            self._raise_failure(
                phase="sdk_response_parse",
                reason_code="sdk_http_envelope_validation",
                request_fingerprint=request_fingerprint,
                prompt_fingerprint=prompt_fingerprint,
                text_schema_fingerprint=text_schema_fingerprint,
                request_arguments_fingerprint=request_arguments_fingerprint,
                client_request_id=client_request_id,
                max_output_tokens=max_output_tokens,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                http=http,
                parse_boundary="failed_after_http",
            )
        except Exception:
            self._raise_failure(
                phase="sdk_response_parse",
                reason_code="sdk_parse_unclassified",
                request_fingerprint=request_fingerprint,
                prompt_fingerprint=prompt_fingerprint,
                text_schema_fingerprint=text_schema_fingerprint,
                request_arguments_fingerprint=request_arguments_fingerprint,
                client_request_id=client_request_id,
                max_output_tokens=max_output_tokens,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                http=http,
                parse_boundary="failed_after_http",
            )

        contract_reason = _provider_contract_reason(
            response,
            text_format=text_format,
            requested_model=self.model,
            expected_service_tier="default",
        )
        if contract_reason is not None:
            self._raise_failure(
                phase="provider_contract",
                reason_code=contract_reason,
                request_fingerprint=request_fingerprint,
                prompt_fingerprint=prompt_fingerprint,
                text_schema_fingerprint=text_schema_fingerprint,
                request_arguments_fingerprint=request_arguments_fingerprint,
                client_request_id=client_request_id,
                max_output_tokens=max_output_tokens,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                http=http,
                response=response,
                usage=_usage_or_unavailable(response),
                parse_boundary="succeeded",
            )
        try:
            usage = _usage_from_response(response)
        except Exception:
            self._raise_failure(
                phase="provider_contract",
                reason_code="missing_exact_usage",
                request_fingerprint=request_fingerprint,
                prompt_fingerprint=prompt_fingerprint,
                text_schema_fingerprint=text_schema_fingerprint,
                request_arguments_fingerprint=request_arguments_fingerprint,
                client_request_id=client_request_id,
                max_output_tokens=max_output_tokens,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                http=http,
                response=response,
                parse_boundary="succeeded",
            )

        receipt = self._finalize_receipt(
            request_fingerprint=request_fingerprint,
            prompt_fingerprint=prompt_fingerprint,
            text_schema_fingerprint=text_schema_fingerprint,
            request_arguments_fingerprint=request_arguments_fingerprint,
            client_request_id=client_request_id,
            max_output_tokens=max_output_tokens,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            http=http,
            response=response,
            usage=usage,
            attempt_outcome="completed",
            status_label=_safe_provider_status(response) or "completed",
            parse_boundary="succeeded",
            failure_phase=None,
            failure_reason_code=None,
        )
        return response.output_parsed, receipt


class OpenAIMappingCardProviderV043(InstrumentedResponsesClientBase):
    """v0.4-compatible public mapping-card provider with v0.4.3 receipts."""

    def __init__(
        self,
        *,
        model: str,
        reasoning_effort: str,
        timeout_seconds: float,
        max_output_tokens: int,
        instructions: str,
        client: OpenAI | Any | None = None,
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
        self.instructions = str(instructions)

    @property
    def provenance(self) -> Mapping[str, Any]:
        return {
            "provider": "openai_responses",
            "model": self.model,
            "api": "responses.with_raw_response.parse+raw.parse",
            "request_shape": "responses.parse_v0_4_compatible",
            "structured_output": "pydantic_v2",
            "reasoning_effort": self.reasoning_effort,
            "max_output_tokens": self.max_output_tokens,
            "instructions_fingerprint": fingerprint(self.instructions),
            "store": False,
            "previous_response_id": False,
            "service_tier": "default",
            "truncation": "disabled",
            "retries": 0,
            "sdk_version": self.sdk_version,
            "receipt_schema_version": RECEIPT_SCHEMA_VERSION,
        }

    def generate(self, input_payload: Mapping[str, Any]) -> CardResult:
        payload, receipt = self._parse(
            input_payload=input_payload,
            instructions=self.instructions,
            text_format=ReasoningCardPayload,
            max_output_tokens=self.max_output_tokens,
        )
        # The runtime type is finalized inside _parse before a completed receipt.
        if not isinstance(payload, ReasoningCardPayload):
            raise AssertionError("v0.4.3 runtime-type guard was bypassed")
        return CardResult(card=_reasoning_card_from_payload(payload), receipt=receipt)


def make_openai_mapping_provider_v0_4_3(
    *,
    model: str,
    reasoning_effort: str,
    timeout_seconds: float,
    max_output_tokens: int,
    instructions: str,
    client: OpenAI | Any | None = None,
) -> OpenAIMappingCardProviderV043:
    """Return the v0.4-compatible mapping provider; never silently fallback."""

    return OpenAIMappingCardProviderV043(
        model=model,
        reasoning_effort=reasoning_effort,
        timeout_seconds=timeout_seconds,
        max_output_tokens=max_output_tokens,
        instructions=instructions,
        client=client,
    )


_make_openai_mapping_provider_v0_4_3 = make_openai_mapping_provider_v0_4_3


def _offline_response(card: Mapping[str, Any], **changes: Any) -> dict[str, Any]:
    value = {
        "id": "resp_offline_boundary",
        "created_at": 1,
        "model": "gpt-5.6-sol",
        "object": "response",
        "output": [
            {
                "id": "msg_offline_boundary",
                "content": [
                    {
                        "annotations": [],
                        "text": json.dumps(card, sort_keys=True),
                        "type": "output_text",
                    }
                ],
                "role": "assistant",
                "status": "completed",
                "type": "message",
            }
        ],
        "parallel_tool_calls": True,
        "tool_choice": "auto",
        "tools": [],
        "status": "completed",
        "error": None,
        "incomplete_details": None,
        "service_tier": "default",
        "usage": {
            "input_tokens": 10,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens": 5,
            "output_tokens_details": {"reasoning_tokens": 2},
            "total_tokens": 15,
        },
    }
    value.update(changes)
    return value


def self_test() -> dict[str, Any]:
    """Exercise the real SDK against local MockTransport; never use network."""

    import httpx

    instructions = "Return the offline strict public card."
    input_payload = {
        "question": "Choose A or B.",
        "answer_choices": ["A", "B"],
        "decision_slots": [],
        "checkpoint_id": "card:E1",
        "all_raw_evidence": [{"evidence_id": "E1", "text": "offline"}],
        "revision_context": None,
        "allowed_evidence_ids": ["E1"],
    }
    valid_card = {
        "checkpoint_id": "card:E1",
        "claim": "Bounded offline public card.",
        "topic": "offline",
        "stance": 0.0,
        "confidence": 0.5,
        "evidence_ids": ["E1"],
        "current_answer": "A",
        "revision_cue": 0.0,
        "decision_facts": [],
        "invalidated_evidence_ids": [],
    }

    def client_for(handler: Any) -> tuple[OpenAI, httpx.Client]:
        http_client = httpx.Client(transport=httpx.MockTransport(handler))
        client = OpenAI(
            api_key="sk-offline-self-test-not-a-credential",
            base_url="https://offline.invalid/v1",
            max_retries=0,
            timeout=60.0,
            http_client=http_client,
        )
        return client, http_client

    def provider_for(client: Any) -> OpenAIMappingCardProviderV043:
        return make_openai_mapping_provider_v0_4_3(
            model="gpt-5.6-sol",
            reasoning_effort="low",
            timeout_seconds=60.0,
            max_output_tokens=768,
            instructions=instructions,
            client=client,
        )

    checks: list[str] = []
    raw_requests: list[Any] = []

    def success_handler(request: Any) -> Any:
        raw_requests.append(request)
        return httpx.Response(
            200,
            headers={"x-request-id": "req_offline_success"},
            json=_offline_response(valid_card),
            request=request,
        )

    client, http_client = client_for(success_handler)
    provider = provider_for(client)
    result = provider.generate(input_payload)
    if result.card.current_answer != "A" or len(provider.audit_receipts) != 1:
        raise AssertionError("offline success did not emit exactly one valid receipt")
    success_receipt = provider.audit_receipts[0]
    success_metadata = success_receipt["metadata"]
    required_receipt_metadata = {
        "receipt_schema_version",
        "response_schema_fingerprint",
        "semantic_protocol_fingerprint",
        "attempt",
        "retry_count",
        "attempt_outcome",
        "failure_phase",
        "failure_reason_code",
        "http_observed",
        "http_status_code",
        "parse_boundary",
        "python_version",
        "sdk_version",
        "pydantic_version",
        "store",
        "previous_response_id",
        "truncation",
        "provider_body_sha256",
        "provider_body_byte_count",
    }
    if not required_receipt_metadata <= set(success_metadata):
        raise AssertionError("canonical v0.4.3 receipt metadata is incomplete")
    forbidden_legacy_metadata = {
        "boundary_schema_version",
        "text_schema_fingerprint",
        "request_arguments_fingerprint",
        "http_response_observed",
        "response_body_sha256",
        "response_body_bytes",
    }
    if forbidden_legacy_metadata & set(success_metadata):
        raise AssertionError("non-canonical receipt metadata alias was persisted")
    if (
        success_metadata["attempt_outcome"] != "completed"
        or success_metadata["parse_boundary"] != "succeeded"
        or success_metadata["failure_reason_code"] is not None
        or success_receipt["usage"]["exact_provider_tokens"] is not True
    ):
        raise AssertionError("offline success receipt boundary drifted")
    raw_body = bytes(raw_requests[0].content)
    if raw_requests[0].headers.get("x-stainless-raw-response") != "true":
        raise AssertionError("raw Responses capability header was not present")
    client.close()
    http_client.close()
    checks.append("completed raw acquisition and structured parse emit one receipt")

    standard_requests: list[Any] = []

    def standard_handler(request: Any) -> Any:
        standard_requests.append(request)
        return httpx.Response(
            200,
            headers={"x-request-id": "req_offline_standard"},
            json=_offline_response(valid_card),
            request=request,
        )

    standard_client, standard_http = client_for(standard_handler)
    standard_client.responses.parse(
        model="gpt-5.6-sol",
        instructions=instructions,
        input=canonical_json(input_payload),
        text_format=ReasoningCardPayload,
        reasoning={"effort": "low"},
        max_output_tokens=768,
        store=False,
        service_tier="default",
        truncation="disabled",
        extra_headers={"X-Client-Request-Id": "parity-only"},
        timeout=60.0,
    )
    if raw_body != bytes(standard_requests[0].content):
        raise AssertionError("raw-boundary request body diverged from v0.4 shape")
    raw_headers = dict(raw_requests[0].headers)
    standard_headers = dict(standard_requests[0].headers)
    header_differences = {
        key
        for key in set(raw_headers) | set(standard_headers)
        if raw_headers.get(key) != standard_headers.get(key)
    }
    # Client request IDs intentionally differ; only the raw-mode header may be
    # added by the SDK beyond that explicit per-call identifier.
    if header_differences - {"x-client-request-id", "x-stainless-raw-response"}:
        raise AssertionError("raw-boundary request added an unexpected header delta")
    standard_client.close()
    standard_http.close()
    checks.append("request body matches ordinary responses.parse under SDK 2.45.0")

    def expect_failure(
        handler: Any,
        *,
        phase: str,
        reason_code: str,
        forbidden: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        attempts = 0

        def counted(request: Any) -> Any:
            nonlocal attempts
            attempts += 1
            return handler(request)

        client_value, http_value = client_for(counted)
        provider_value = provider_for(client_value)
        try:
            provider_value.generate(input_payload)
        except OpenAIProviderBoundaryError as error:
            if error.phase != phase or error.reason_code != reason_code:
                raise AssertionError(
                    f"boundary classification drifted: {error.phase}/{error.reason_code}"
                ) from None
            if error.__cause__ is not None:
                raise AssertionError("raw exception was chained into public boundary error")
        else:
            raise AssertionError(f"expected boundary failure: {reason_code}")
        receipts = provider_value.audit_receipts
        if attempts != 1 or len(receipts) != 1:
            raise AssertionError("failure did not preserve one-call/one-receipt policy")
        serialized = canonical_json(receipts)
        if any(value in serialized for value in forbidden):
            raise AssertionError("unsafe raw or exception text reached a receipt")
        if receipts[0]["metadata"]["retry_count"] != 0:
            raise AssertionError("offline failure unexpectedly retried")
        client_value.close()
        http_value.close()
        return receipts[0]

    invalid_card = dict(valid_card)
    invalid_card.update(
        {
            "stance": 2.0,
            "claim": "RAW_RESPONSE_SENTINEL must never be serialized",
        }
    )
    invalid_receipt = expect_failure(
        lambda request: httpx.Response(
            200,
            headers={"x-request-id": "req_invalid_card"},
            json=_offline_response(invalid_card),
            request=request,
        ),
        phase="sdk_response_parse",
        reason_code="sdk_structured_parse_validation",
        forbidden=("RAW_RESPONSE_SENTINEL",),
    )
    if invalid_receipt["metadata"]["http_observed"] is not True:
        raise AssertionError("post-HTTP schema failure lost its HTTP boundary")
    checks.append("structured schema failure is separated from transport")

    expect_failure(
        lambda request: httpx.Response(
            200,
            headers={"content-type": "application/json"},
            content=b"{RAW_BODY_SENTINEL",
            request=request,
        ),
        phase="sdk_response_parse",
        reason_code="sdk_response_decode",
        forbidden=("RAW_BODY_SENTINEL",),
    )
    checks.append("malformed JSON stores only a body digest")

    for api_code, expected_reason in (
        ("insufficient_quota", "insufficient_quota"),
        ("rate_limit", "rate_limit"),
        ("rate_limit_exceeded", "rate_limit"),
        ("future_unknown_code", "unknown429"),
    ):
        receipt = expect_failure(
            lambda request, code=api_code: httpx.Response(
                429,
                headers={"x-request-id": "req_429_offline"},
                json={
                    "error": {
                        "message": "HTTP_ERROR_MESSAGE_SENTINEL",
                        "type": code,
                        "param": None,
                        "code": code,
                    }
                },
                request=request,
            ),
            phase="http_status",
            reason_code=expected_reason,
            forbidden=("HTTP_ERROR_MESSAGE_SENTINEL",),
        )
        if receipt["metadata"]["http_status_code"] != 429:
            raise AssertionError("429 classification lost its status code")
    checks.append("429 quota, rate-limit, and unknown codes stay distinct")

    for status_code, expected_reason in (
        (400, "bad_request"),
        (401, "authentication"),
        (403, "permission_denied"),
        (404, "not_found"),
        (409, "conflict"),
        (418, "http_other"),
        (422, "unprocessable_entity"),
        (500, "server_error"),
    ):
        receipt = expect_failure(
            lambda request, code=status_code: httpx.Response(
                code,
                headers={"x-request-id": f"req_{code}_offline"},
                json={
                    "error": {
                        "message": "HTTP_STATUS_TEXT_SENTINEL",
                        "type": "offline_error",
                        "param": None,
                        "code": "offline_error",
                    }
                },
                request=request,
            ),
            phase="http_status",
            reason_code=expected_reason,
            forbidden=("HTTP_STATUS_TEXT_SENTINEL",),
        )
        if receipt["metadata"]["http_status_code"] != status_code:
            raise AssertionError("HTTP classification lost its status code")
    checks.append("allowlisted HTTP status families are classified without messages")

    def timeout_handler(request: Any) -> Any:
        raise httpx.ReadTimeout("EXCEPTION_TEXT_SENTINEL", request=request)

    timeout_receipt = expect_failure(
        timeout_handler,
        phase="request_call",
        reason_code="timeout",
        forbidden=("EXCEPTION_TEXT_SENTINEL",),
    )
    if timeout_receipt["metadata"]["http_observed"] is not False:
        raise AssertionError("timeout incorrectly claimed an HTTP response")
    checks.append("timeout is pre-HTTP and is never retried")

    def connection_handler(request: Any) -> Any:
        raise httpx.ConnectError("CONNECTION_TEXT_SENTINEL", request=request)

    expect_failure(
        connection_handler,
        phase="request_call",
        reason_code="connection",
        forbidden=("CONNECTION_TEXT_SENTINEL",),
    )
    checks.append("connection failure is separated from HTTP status")

    incomplete = _offline_response(valid_card, status="failed")
    expect_failure(
        lambda request: httpx.Response(200, json=incomplete, request=request),
        phase="provider_contract",
        reason_code="provider_status_non_completed",
    )

    incomplete_detail = _offline_response(
        valid_card,
        status="incomplete",
        incomplete_details={"reason": "max_output_tokens"},
    )
    expect_failure(
        lambda request: httpx.Response(
            200,
            json=incomplete_detail,
            request=request,
        ),
        phase="provider_contract",
        reason_code="provider_incomplete",
    )

    provider_error = _offline_response(
        valid_card,
        status="failed",
        error={
            "code": "server_error",
            "message": "PROVIDER_ERROR_TEXT_SENTINEL",
        },
    )
    expect_failure(
        lambda request: httpx.Response(200, json=provider_error, request=request),
        phase="provider_contract",
        reason_code="provider_error",
        forbidden=("PROVIDER_ERROR_TEXT_SENTINEL",),
    )

    no_output = _offline_response(valid_card, output=[])
    expect_failure(
        lambda request: httpx.Response(200, json=no_output, request=request),
        phase="provider_contract",
        reason_code="missing_structured_output",
    )

    no_usage = _offline_response(valid_card, usage=None)
    expect_failure(
        lambda request: httpx.Response(200, json=no_usage, request=request),
        phase="provider_contract",
        reason_code="missing_exact_usage",
    )

    refusal = _offline_response(valid_card)
    refusal["output"][0]["content"] = [
        {
            "type": "refusal",
            "refusal": "REFUSAL_TEXT_SENTINEL",
        }
    ]
    expect_failure(
        lambda request: httpx.Response(200, json=refusal, request=request),
        phase="provider_contract",
        reason_code="provider_refusal",
        forbidden=("REFUSAL_TEXT_SENTINEL",),
    )
    checks.append("parsed provider-contract failures remain sanitized and non-assessable")

    wrong_model_card = dict(valid_card)
    wrong_model_card["claim"] = "WRONG_MODEL_CARD_SENTINEL"
    wrong_model_receipt = expect_failure(
        lambda request: httpx.Response(
            200,
            json=_offline_response(
                wrong_model_card,
                model="gpt-5.6-terra",
            ),
            request=request,
        ),
        phase="provider_contract",
        reason_code="wrong_runtime",
        forbidden=("WRONG_MODEL_CARD_SENTINEL",),
    )
    if wrong_model_receipt["returned_model"] != "gpt-5.6-terra":
        raise AssertionError("wrong returned model was not safely recorded")

    wrong_tier_card = dict(valid_card)
    wrong_tier_card["claim"] = "WRONG_SERVICE_TIER_CARD_SENTINEL"
    wrong_tier_receipt = expect_failure(
        lambda request: httpx.Response(
            200,
            json=_offline_response(
                wrong_tier_card,
                service_tier="priority",
            ),
            request=request,
        ),
        phase="provider_contract",
        reason_code="wrong_runtime",
        forbidden=("WRONG_SERVICE_TIER_CARD_SENTINEL",),
    )
    if wrong_tier_receipt["metadata"]["service_tier"] != "priority":
        raise AssertionError("wrong service tier was not safely recorded")

    missing_tier_card = dict(valid_card)
    missing_tier_card["claim"] = "MISSING_SERVICE_TIER_CARD_SENTINEL"
    missing_tier_response = _offline_response(missing_tier_card)
    del missing_tier_response["service_tier"]
    missing_tier_receipt = expect_failure(
        lambda request: httpx.Response(
            200,
            json=missing_tier_response,
            request=request,
        ),
        phase="provider_contract",
        reason_code="wrong_runtime",
        forbidden=("MISSING_SERVICE_TIER_CARD_SENTINEL",),
    )
    if missing_tier_receipt["metadata"]["service_tier"] is not None:
        raise AssertionError("missing service tier was not safely recorded")
    checks.append("returned model and exact default service tier are runtime-guarded")

    class FakeRaw:
        status_code = 200
        request_id = "req_wrong_runtime"
        content = b"WRONG_RUNTIME_RAW_SENTINEL"

        def parse(self) -> Any:
            return SimpleNamespace(
                id="resp_wrong_runtime",
                model="gpt-5.6-sol",
                status="completed",
                service_tier="default",
                output=(),
                output_parsed=object(),
                error=None,
                incomplete_details=None,
                usage=SimpleNamespace(
                    input_tokens=1,
                    output_tokens=1,
                    total_tokens=2,
                    input_tokens_details=SimpleNamespace(cached_tokens=0),
                    output_tokens_details=SimpleNamespace(reasoning_tokens=0),
                ),
            )

    class FakeRawEndpoint:
        def __init__(self) -> None:
            self.calls = 0

        def parse(self, **_: Any) -> FakeRaw:
            self.calls += 1
            return FakeRaw()

    class FakeClient:
        max_retries = 0

        def __init__(self) -> None:
            self.endpoint = FakeRawEndpoint()
            self.responses = SimpleNamespace(
                with_raw_response=SimpleNamespace(parse=self.endpoint.parse)
            )

    fake_client = FakeClient()
    fake_provider = provider_for(fake_client)
    try:
        fake_provider.generate(input_payload)
    except OpenAIProviderBoundaryError as error:
        if (
            error.phase != "provider_contract"
            or error.reason_code != "wrong_runtime"
        ):
            raise AssertionError("wrong runtime type escaped its contract guard")
    else:
        raise AssertionError("wrong runtime type was accepted")
    if fake_client.endpoint.calls != 1 or len(fake_provider.audit_receipts) != 1:
        raise AssertionError("wrong runtime type broke exactly-one accounting")
    if "WRONG_RUNTIME_RAW_SENTINEL" in canonical_json(fake_provider.audit_receipts):
        raise AssertionError("wrong-runtime raw body leaked into receipt")
    checks.append("wrong runtime type is guarded before completed receipt")

    class UnclassifiedAcquireEndpoint:
        def __init__(self) -> None:
            self.calls = 0

        def parse(self, **_: Any) -> Any:
            self.calls += 1
            raise RuntimeError("ACQUISITION_EXCEPTION_TEXT_SENTINEL")

    unclassified_endpoint = UnclassifiedAcquireEndpoint()
    unclassified_client = SimpleNamespace(
        max_retries=0,
        responses=SimpleNamespace(
            with_raw_response=SimpleNamespace(parse=unclassified_endpoint.parse)
        ),
    )
    unclassified_provider = provider_for(unclassified_client)
    try:
        unclassified_provider.generate(input_payload)
    except OpenAIProviderBoundaryError as error:
        if error.phase != "request_call" or error.reason_code != "request_unclassified":
            raise AssertionError("acquisition catch-all escaped its phase contract")
    else:
        raise AssertionError("unclassified acquisition failure was accepted")
    if (
        unclassified_endpoint.calls != 1
        or len(unclassified_provider.audit_receipts) != 1
        or "ACQUISITION_EXCEPTION_TEXT_SENTINEL"
        in canonical_json(unclassified_provider.audit_receipts)
    ):
        raise AssertionError("unclassified acquisition receipt policy drifted")
    checks.append("acquisition catch-all is request_unclassified and sanitized")

    class MissingCapabilityClient:
        max_retries = 0
        responses = SimpleNamespace()

    try:
        provider_for(MissingCapabilityClient())
    except OpenAIBoundaryCapabilityError as error:
        if error.reason_code != "with_raw_response_parse_unavailable":
            raise AssertionError("capability failure reason drifted") from None
    else:
        raise AssertionError("missing raw boundary silently fell back")
    checks.append("missing raw capability fails before any call without fallback")

    try:
        OpenAIProviderBoundaryError(
            phase="request_call",
            reason_code="sdk_parse_unclassified",
            receipt=result.receipt,
        )
    except AssertionError:
        pass
    else:
        raise AssertionError("phase-incompatible boundary reason was accepted")
    checks.append("phase and reason-code matrix is enforced")

    serialized_success = canonical_json(success_receipt).casefold()
    for forbidden in (
        "authorization",
        "bearer ",
        "openai_api_key",
        "sk-offline-self-test-not-a-credential",
    ):
        if forbidden in serialized_success:
            raise AssertionError("credential-bearing field reached success receipt")

    return {
        "status": "PASS",
        "receipt_schema_version": RECEIPT_SCHEMA_VERSION,
        "openai_sdk_version": importlib.metadata.version("openai"),
        "pydantic_version": importlib.metadata.version("pydantic"),
        "network_calls": 0,
        "checks": checks,
    }


if __name__ == "__main__":
    print(json.dumps(self_test(), ensure_ascii=False, indent=2))
