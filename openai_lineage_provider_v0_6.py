#!/usr/bin/env python3
"""Pinned OpenAI Responses boundary for EBRT v0.6 lineage outputs.

This module is deliberately narrow: it sends one already-validated public
provider payload through the instrumented v0.4.3 Responses boundary and
returns only a strict public-lineage mapping plus its sanitized receipt.  It
does not build treatments, load semantic gold, grade an answer, persist raw
provider bodies, or expose private reasoning.
"""

from __future__ import annotations

import argparse
import json
import socket
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any, Iterator, Mapping, Sequence
from unittest import mock

from openai import OpenAI

from hosted_bundle_lineage_v0_6 import ProviderLineageOutput
from language_replay_bridge_v0_4 import ProviderReceipt, canonical_json, fingerprint
from openai_response_boundary_v0_4_3 import InstrumentedResponsesClientBase


MODEL = "gpt-5.6-sol"
REASONING_EFFORT = "low"
MAX_OUTPUT_TOKENS = 4608
TIMEOUT_SECONDS = 60.0

LINEAGE_INSTRUCTIONS = (
    "Produce only the strict public lineage output. Use the ordered raw evidence "
    "as semantic authority. A public revision program, when present, is external "
    "execution metadata rather than new evidence, a gold answer, or hidden model "
    "state. Signed actuator displacement is bounded operation-level guidance: it "
    "is not truth, probability, evidence importance, or permission to override "
    "raw evidence. When a revision program is present, instantiate its visible "
    "typed_dependency_graph exactly in support-node evidence links, target "
    "direct-support links, Fact dependencies, and invalidation edges; those graph "
    "edges remain supplied structure rather than evidence truth. Derive the answer "
    "and every target value only from raw evidence. When no revision program is "
    "present, infer a minimal public support graph directly from raw evidence; do "
    "not fabricate a revision event. Explicit invalidation dominates active support. "
    "Cite only supplied evidence IDs, never use invalidated evidence as active support, "
    "return every supplied slot ID exactly once, and use only values allowed for "
    "that slot. Return support nodes and typed target dependencies; direct, "
    "inherited, and total closure are computed locally. Return the strict public "
    "decision-state schema without private chain-of-thought or a prose derivation."
)
INSTRUCTIONS_FINGERPRINT_SHA256 = fingerprint(LINEAGE_INSTRUCTIONS)


class OpenAILineageProviderV0_6(InstrumentedResponsesClientBase):
    """One-attempt, no-retry provider for a strict public lineage output."""

    def __init__(self, *, client: OpenAI | None = None) -> None:
        super().__init__(
            model=MODEL,
            reasoning_effort=REASONING_EFFORT,
            timeout_seconds=TIMEOUT_SECONDS,
            client=client,
        )

    @property
    def provenance(self) -> dict[str, Any]:
        return {
            "provider": "openai_responses",
            "api": "responses.with_raw_response.parse+raw.parse",
            "model": MODEL,
            "reasoning_effort": REASONING_EFFORT,
            "service_tier": "default",
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "timeout_seconds": int(TIMEOUT_SECONDS),
            "sdk_retries": 0,
            "store": False,
            "previous_response_id": False,
            "truncation": "disabled",
            "instructions_fingerprint_sha256": INSTRUCTIONS_FINGERPRINT_SHA256,
            "response_schema_fingerprint_sha256": fingerprint(
                ProviderLineageOutput.model_json_schema()
            ),
        }

    def generate(
        self, input_payload: Mapping[str, Any]
    ) -> tuple[dict[str, Any], ProviderReceipt]:
        """Run one logical call and return public JSON plus its sanitized receipt."""

        if not isinstance(input_payload, Mapping):
            raise TypeError("input_payload must be a mapping")
        # Canonical round-tripping rejects non-JSON values, NaN, and aliasing
        # before the irreversible provider boundary without retaining caller state.
        public_input = json.loads(canonical_json(dict(input_payload)))
        parsed, receipt = self._parse(
            input_payload=public_input,
            instructions=LINEAGE_INSTRUCTIONS,
            text_format=ProviderLineageOutput,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )
        if not isinstance(parsed, ProviderLineageOutput):
            raise AssertionError("instrumented boundary returned the wrong output type")
        public_output = parsed.model_dump(mode="json")
        reparsed = ProviderLineageOutput.model_validate(public_output)
        if canonical_json(reparsed.model_dump(mode="json")) != canonical_json(
            public_output
        ):
            raise AssertionError("public lineage output did not round-trip exactly")
        return public_output, receipt


class _FakeRawResponse:
    def __init__(self, parsed: ProviderLineageOutput) -> None:
        self.status_code = 200
        self.headers = {"x-request-id": "v060-offline-server-request"}
        self.content = b'{"offline":"public-boundary-self-test"}'
        self._parsed = parsed

    def parse(self) -> Any:
        usage = SimpleNamespace(
            input_tokens=37,
            output_tokens=19,
            total_tokens=56,
            input_tokens_details=SimpleNamespace(
                cached_tokens=0,
                cache_write_tokens=0,
            ),
            output_tokens_details=SimpleNamespace(reasoning_tokens=3),
        )
        return SimpleNamespace(
            id="resp-v060-offline",
            model=MODEL,
            service_tier="default",
            status="completed",
            error=None,
            incomplete_details=None,
            output=[],
            output_parsed=self._parsed,
            usage=usage,
        )


class _FakeRawParseEndpoint:
    def __init__(self, parsed: ProviderLineageOutput) -> None:
        self._parsed = parsed
        self.calls: list[dict[str, Any]] = []

    def parse(self, **kwargs: Any) -> _FakeRawResponse:
        self.calls.append(dict(kwargs))
        return _FakeRawResponse(self._parsed)


class _FakeOpenAIClient:
    def __init__(self, parsed: ProviderLineageOutput) -> None:
        self.max_retries = 0
        self.endpoint = _FakeRawParseEndpoint(parsed)
        self.responses = SimpleNamespace(
            with_raw_response=SimpleNamespace(parse=self.endpoint.parse)
        )


@contextmanager
def _network_denied() -> Iterator[dict[str, int]]:
    counts = {"network_calls": 0}

    def denied(*_args: Any, **_kwargs: Any) -> None:
        counts["network_calls"] += 1
        raise AssertionError("network is forbidden in provider boundary self-test")

    with (
        mock.patch.object(socket, "create_connection", side_effect=denied),
        mock.patch.object(socket.socket, "connect", side_effect=denied),
        mock.patch.object(socket.socket, "connect_ex", side_effect=denied),
    ):
        yield counts


def offline_transport_self_test(
    *, input_payload: Mapping[str, Any], output_payload: Mapping[str, Any]
) -> dict[str, Any]:
    """Exercise the full receipt boundary with a fake Responses transport."""

    parsed = ProviderLineageOutput.model_validate(dict(output_payload))
    fake = _FakeOpenAIClient(parsed)
    with _network_denied() as counts:
        provider = OpenAILineageProviderV0_6(client=fake)  # type: ignore[arg-type]
        public_output, receipt = provider.generate(input_payload)
    receipt_value = receipt.to_dict()
    expected_output = parsed.model_dump(mode="json")
    call = fake.endpoint.calls[0] if len(fake.endpoint.calls) == 1 else {}
    checks = {
        "exact_public_output_round_trip": (
            canonical_json(public_output) == canonical_json(expected_output)
        ),
        "one_fake_transport_call": len(fake.endpoint.calls) == 1,
        "one_sanitized_audit_receipt": provider.audit_receipts == [receipt_value],
        "request_payload_bound": receipt_value["request_fingerprint"]
        == fingerprint(json.loads(canonical_json(dict(input_payload)))),
        "instructions_bound": receipt_value["prompt_fingerprint"]
        == INSTRUCTIONS_FINGERPRINT_SHA256,
        "runtime_arguments_pinned": (
            call.get("model") == MODEL
            and call.get("instructions") == LINEAGE_INSTRUCTIONS
            and call.get("input")
            == canonical_json(json.loads(canonical_json(dict(input_payload))))
            and call.get("reasoning") == {"effort": REASONING_EFFORT}
            and call.get("max_output_tokens") == MAX_OUTPUT_TOKENS
            and call.get("store") is False
            and call.get("service_tier") == "default"
            and call.get("truncation") == "disabled"
            and call.get("timeout") == TIMEOUT_SECONDS
            and call.get("text_format") is ProviderLineageOutput
            and set(call.get("extra_headers", {})) == {"X-Client-Request-Id"}
        ),
        "completed_receipt_exact_usage": (
            receipt_value["logical_calls"] == 1
            and receipt_value["api_calls"] == 1
            and receipt_value["requested_model"] == MODEL
            and receipt_value["returned_model"] == MODEL
            and receipt_value["usage"]["exact_provider_tokens"] is True
            and receipt_value["usage"]["total_tokens"] == 56
            and receipt_value["usage"]["reasoning_tokens"] == 3
            and receipt_value["metadata"]["attempt_outcome"] == "completed"
            and receipt_value["metadata"]["retry_count"] == 0
            and receipt_value["metadata"]["response_schema_fingerprint"]
            == fingerprint(ProviderLineageOutput.model_json_schema())
        ),
        "network_calls_zero": counts["network_calls"] == 0,
    }
    if not all(checks.values()):
        raise AssertionError("lineage provider offline transport self-test failed")
    return {
        "schema_version": "ebrt-openai-lineage-provider-transport-test-v0.6",
        "status": "PASS",
        "checks": checks,
        "provider_calls": 0,
        "simulated_api_calls": 1,
        "network_calls": 0,
        "receipt": receipt_value,
    }


def provider_self_test() -> dict[str, Any]:
    """Validate static, network-free aspects; transport is tested by the runner."""

    schema = ProviderLineageOutput.model_json_schema()
    provider_fields = {
        "model": MODEL,
        "reasoning_effort": REASONING_EFFORT,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "timeout_seconds": int(TIMEOUT_SECONDS),
        "instructions_fingerprint_sha256": INSTRUCTIONS_FINGERPRINT_SHA256,
        "response_schema_fingerprint_sha256": fingerprint(schema),
    }
    checks = {
        "strict_public_schema_available": isinstance(schema, dict) and bool(schema),
        "instructions_do_not_request_private_reasoning": (
            "without private chain-of-thought" in LINEAGE_INSTRUCTIONS
        ),
        "closure_remains_local": (
            "direct, inherited, and total closure are computed locally"
            in LINEAGE_INSTRUCTIONS
        ),
        "typed_graph_instantiation_is_explicit": (
            "instantiate its visible typed_dependency_graph exactly"
            in LINEAGE_INSTRUCTIONS
            and "supplied structure rather than evidence truth"
            in LINEAGE_INSTRUCTIONS
        ),
        "answer_values_remain_raw_evidence_derived": (
            "Derive the answer and every target value only from raw evidence"
            in LINEAGE_INSTRUCTIONS
        ),
        "null_program_support_inference_is_explicit": (
            "infer a minimal public support graph directly from raw evidence"
            in LINEAGE_INSTRUCTIONS
            and "do not fabricate a revision event" in LINEAGE_INSTRUCTIONS
        ),
        "pinned_model": MODEL == "gpt-5.6-sol",
        "pinned_effort": REASONING_EFFORT == "low",
        "one_attempt_configuration": True,
    }
    if not all(checks.values()):
        raise AssertionError("lineage provider static self-test failed")
    return {
        "schema_version": "ebrt-openai-lineage-provider-self-test-v0.6",
        "status": "PASS",
        "checks": checks,
        "provider_contract": provider_fields,
        "provider_calls": 0,
        "network_calls": 0,
    }


def _print_json(value: Mapping[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("self-test",))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "self-test":
        _print_json(provider_self_test())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
