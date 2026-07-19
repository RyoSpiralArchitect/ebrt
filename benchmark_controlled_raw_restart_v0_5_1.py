#!/usr/bin/env python3
"""Gold-late one-shot generation canary for EBRT v0.5.1.

The four arms share one ordered raw context, one public-card schema, one
instruction string, one output-token ceiling, and one provider attempt.  The
only arm-specific provider input is the locked public execution envelope built
by ``controlled_raw_restart_v0_5_1``. Semantic gold is parsed and attached only
after every provider attempt has finished.
"""

from __future__ import annotations

import argparse
import copy
import dataclasses
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import shutil
import socket
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence
from unittest import mock

from benchmark_language_replay_v0_4 import _validate_gold, grade_card
from controlled_raw_restart_v0_5_1 import (
    build_arm_bundle,
    build_case_temporal_suite,
    build_restart_payload,
    load_bridge_fixture,
    public_card_diff,
    run_self_tests as run_bridge_self_tests,
    validate_public_card,
)
from language_replay_bridge_v0_4 import (
    CardResult,
    CaseSpec,
    DecisionFact,
    ProviderReceipt,
    ProviderUsage,
    ReasoningCard,
    canonical_json,
    fingerprint,
)
from temporal_adjoint_state_controller_v0_5_t import TemporalAdjointStateController


ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = "ebrt-controlled-raw-restart-benchmark-v0.5.1"
ARTIFACT_SCHEMA_VERSION = "ebrt-controlled-raw-restart-artifact-v0.5.1"
ARMS = (
    "raw_restart_zero_control",
    "raw_restart_textual_envelope",
    "raw_restart_matched_permutation",
    "controlled_raw_restart",
)
LOCKED_ARM_ORDER = (ARMS[0], ARMS[1], ARMS[3], ARMS[2])
LOCK_PATH = ROOT / "policy_lock_controlled_raw_restart_v0_5_1.json"
BRIDGE_FIXTURE_PATH = ROOT / "fixtures" / "controlled_raw_restart_v0_5_1_canary.json"
SOURCE_CASES_PATH = ROOT / "fixtures" / "language_replay_v0_4_dev.json"
GOLD_PATH = ROOT / "fixtures" / "language_replay_v0_4_dev_gold.json"
DEFAULT_LIVE_OUTPUT = (
    ROOT / "benchmark_results" / "v0_5_1_controlled_raw_restart_live_canary"
)
ARTIFACT_FILES = ("results.json", "calls.jsonl", "report.md", "manifest.json")

RESULT_CLAIM_BOUNDARY = (
    "This is one development-contaminated case and one unbalanced four-call block.",
    "Provider randomness and run position are not separated from arm behavior.",
    "The public temporal program and case binding are explicit oracle inputs.",
    "GPT, provider parsing, and final generation remain outside the gradient graph.",
    "A changed output or controlled-only pass is a canary observation, not an advantage estimate.",
    "Frozen predecessor imports may hash the gold file for source integrity, but semantic gold JSON is parsed and attached only after all four provider attempts.",
)
SURROGATE_ACTUAL_SEPARATION = {
    "surrogate_result_source": "local temporal controller projection only",
    "actual_result_source": "post-call strict public-card grader",
    "surrogate_success_implies_actual_success": False,
}


CONTROLLED_RESTART_INSTRUCTIONS = """\
Produce one compact PUBLIC final decision-state card. Do not provide private
chain-of-thought, hidden reasoning, or a prose derivation. Use only the ordered
all_raw_evidence, which contains the complete visible context exactly once.
The optional revision_control_envelope is external execution metadata, not new
evidence. Its revision_context identifies explicit invalidation lineage. Its
temporal_controls are bounded hints on named public state-transition operators:
increase strengthens, decrease weakens, and preserve leaves that public
operator unchanged. A numeric delta is not a probability, truth value, model
weight, or permission to override raw evidence. Explicit raw evidence,
invalidation, answer choices, and decision-slot constraints always dominate.
Never invent evidence IDs, invalidations, facts, or control targets.

The current_answer must exactly equal one supplied answer choice. Invalidated
evidence must never be active support. Use every required decision slot exactly
once, copy each slot_id exactly, and choose only an exact allowed value; use
UNKNOWN when unsupported. Keep claim and topic compact, cite public evidence
IDs, and return only the strict structured output.
"""

FORBIDDEN_PROVIDER_KEYS = frozenset(
    {
        "gold",
        "grading",
        "expected_plan",
        "expected_answer",
        "required_facts",
        "stable_facts",
        "required_evidence_ids",
        "forbidden_support_evidence_ids",
        "machine_success",
        "downstream_grade",
        "surrogate",
        "objective_before",
        "objective_after",
        "terminal_state_before",
        "terminal_state_after",
        "adjoint",
        "gradient",
        "terminal_decision_target",
    }
)

RECEIPT_KEYS = frozenset(
    {
        "provider",
        "requested_model",
        "returned_model",
        "logical_calls",
        "api_calls",
        "latency_ms",
        "request_fingerprint",
        "prompt_fingerprint",
        "usage",
        "metadata",
    }
)
USAGE_KEYS = frozenset(
    {
        "exact_provider_tokens",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cached_input_tokens",
        "cache_write_tokens",
        "reasoning_tokens",
    }
)
SCRIPTED_RECEIPT_METADATA_KEYS = frozenset({"attempt", "plumbing_only", "retry_count"})
LIVE_RECEIPT_METADATA_KEYS = frozenset(
    {
        "receipt_schema_version",
        "status",
        "service_tier",
        "response_id_sha256",
        "server_request_id_sha256",
        "client_request_id_sha256",
        "provider_body_sha256",
        "provider_body_byte_count",
        "http_observed",
        "http_status_code",
        "parse_boundary",
        "failure_phase",
        "failure_reason_code",
        "failure_type",
        "response_schema_fingerprint",
        "semantic_protocol_fingerprint",
        "reasoning_effort",
        "max_output_tokens",
        "store",
        "previous_response_id",
        "truncation",
        "sdk_version",
        "pydantic_version",
        "python_version",
        "attempt",
        "retry_count",
        "api_call_count_semantics",
        "attempt_outcome",
        "refusal_count",
    }
)
COMPLETED_ARM_KEYS = frozenset(
    {
        "arm_id",
        "run_position",
        "status",
        "provider_input",
        "provider_input_fingerprint_sha256",
        "projection",
        "final_card",
        "receipt",
        "failure",
        "grade",
    }
)
FAILED_ARM_KEYS = COMPLETED_ARM_KEYS | {
    "rejected_candidate_card",
    "observed_receipt_count",
}
FAILURE_RECORD_KEYS = frozenset({"exception_class", "category", "reason_code"})


class BenchmarkValidationError(RuntimeError):
    """An exact local v0.5.1 artifact or execution invariant failed."""


def _canonical_json_bytes(value: Any, *, trailing_newline: bool = False) -> bytes:
    output = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return output + (b"\n" if trailing_newline else b"")


def _pretty_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_path(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BenchmarkValidationError(f"expected JSON object: {path}")
    return value


def _json_clone(value: Any) -> Any:
    """Normalize tuples and other JSON-compatible containers to stored JSON form."""

    return json.loads(_canonical_json_bytes(value))


def _is_sha256(value: Any) -> bool:
    text = str(value)
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def _is_nonnegative_int(value: Any) -> bool:
    return type(value) is int and value >= 0


def _is_finite_nonnegative_number(value: Any) -> bool:
    return (
        type(value) in {int, float}
        and math.isfinite(float(value))
        and float(value) >= 0.0
    )


def _optional_sha256(value: Any) -> bool:
    return value is None or (isinstance(value, str) and _is_sha256(value))


def _validate_usage(usage: Mapping[str, Any], *, arm_id: str) -> None:
    if set(usage) != USAGE_KEYS:
        raise BenchmarkValidationError(f"receipt usage schema drifted: {arm_id}")
    exact = usage["exact_provider_tokens"]
    token_fields = tuple(USAGE_KEYS - {"exact_provider_tokens"})
    if type(exact) is not bool:
        raise BenchmarkValidationError(f"receipt usage exactness drifted: {arm_id}")
    if not exact:
        if any(usage[name] is not None for name in token_fields):
            raise BenchmarkValidationError(
                f"inexact receipt persisted token counts: {arm_id}"
            )
        return
    if any(not _is_nonnegative_int(usage[name]) for name in token_fields):
        raise BenchmarkValidationError(f"exact receipt token shape drifted: {arm_id}")
    if usage["total_tokens"] != usage["input_tokens"] + usage["output_tokens"]:
        raise BenchmarkValidationError(f"receipt token arithmetic drifted: {arm_id}")
    if usage["cached_input_tokens"] > usage["input_tokens"]:
        raise BenchmarkValidationError(f"receipt cached tokens drifted: {arm_id}")
    if usage["reasoning_tokens"] > usage["output_tokens"]:
        raise BenchmarkValidationError(f"receipt reasoning tokens drifted: {arm_id}")


def _runtime() -> dict[str, str]:
    return {
        "python": sys.version.split()[0],
        "openai": importlib.metadata.version("openai"),
        "pydantic": importlib.metadata.version("pydantic"),
        "operating_system": platform.system(),
        "operating_system_release": platform.release(),
        "machine": platform.machine(),
    }


def _load_lock(*, verify_gold: bool = True) -> dict[str, Any]:
    lock = _load_json(LOCK_PATH)
    if (
        lock.get("schema_version") != "ebrt-controlled-raw-restart-policy-lock-v0.5.1"
        or lock.get("status") != "PREREGISTERED_DEV_CANARY"
        or lock.get("promotion_eligible") is not False
    ):
        raise BenchmarkValidationError("v0.5.1 policy status drifted")
    if tuple(lock.get("arms", ())) != ARMS:
        raise BenchmarkValidationError("v0.5.1 arm order drifted")
    execution = lock.get("execution")
    if not isinstance(execution, Mapping):
        raise BenchmarkValidationError("execution lock is missing")
    if (
        tuple(execution.get("arm_order", ())) != LOCKED_ARM_ORDER
        or set(execution.get("arm_order", ())) != set(ARMS)
        or execution.get("trials") != 1
        or execution.get("case_count") != 1
        or execution.get("expected_api_attempts") != 4
        or execution.get("retry_policy") != "one_attempt_no_retry"
    ):
        raise BenchmarkValidationError("execution geometry drifted")
    if lock.get("instructions_fingerprint_sha256") != fingerprint(
        CONTROLLED_RESTART_INSTRUCTIONS
    ):
        raise BenchmarkValidationError("provider instruction fingerprint drifted")
    sources = lock.get("sources")
    if not isinstance(sources, Mapping) or not sources:
        raise BenchmarkValidationError("source lock is missing")
    for label, spec in sources.items():
        if not isinstance(spec, Mapping) or set(spec) != {"path", "sha256"}:
            raise BenchmarkValidationError(f"invalid source lock: {label}")
        path = ROOT / str(spec["path"])
        if not path.is_file() or _sha256_path(path) != spec["sha256"]:
            raise BenchmarkValidationError(f"source hash mismatch: {label}")
    fixtures = lock.get("fixtures")
    if not isinstance(fixtures, Mapping):
        raise BenchmarkValidationError("fixture lock is missing")
    labels = (
        ("bridge", "source_cases", "gold")
        if verify_gold
        else (
            "bridge",
            "source_cases",
        )
    )
    for label in labels:
        spec = fixtures.get(label)
        if not isinstance(spec, Mapping) or set(spec) != {"path", "sha256"}:
            raise BenchmarkValidationError(f"invalid fixture lock: {label}")
        path = ROOT / str(spec["path"])
        if not path.is_file() or _sha256_path(path) != spec["sha256"]:
            raise BenchmarkValidationError(f"fixture hash mismatch: {label}")
    expected_runtime = lock.get("runtime")
    observed_runtime = _runtime()
    for key in ("python", "openai", "pydantic", "machine"):
        if expected_runtime.get(key) != observed_runtime[key]:
            raise BenchmarkValidationError(f"runtime mismatch: {key}")
    return lock


def _verify_locked_fixture(lock: Mapping[str, Any], label: str) -> None:
    spec = lock["fixtures"][label]
    path = ROOT / str(spec["path"])
    if not path.is_file() or _sha256_path(path) != spec["sha256"]:
        raise BenchmarkValidationError(f"fixture hash mismatch: {label}")


def _source_snapshot(lock: Mapping[str, Any]) -> dict[str, str]:
    return {
        str(label): _sha256_path(ROOT / str(spec["path"]))
        for label, spec in lock["sources"].items()
    }


def _all_mapping_keys(value: Any) -> set[str]:
    output: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            output.add(str(key))
            output.update(_all_mapping_keys(child))
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes):
        for child in value:
            output.update(_all_mapping_keys(child))
    return output


def _validate_gold_free_payload(payload: Mapping[str, Any], arm_id: str) -> None:
    forbidden = _all_mapping_keys(payload) & FORBIDDEN_PROVIDER_KEYS
    if forbidden:
        raise BenchmarkValidationError(
            f"provider payload for {arm_id} contains forbidden keys: {sorted(forbidden)}"
        )
    if tuple(str(item["evidence_id"]) for item in payload["all_raw_evidence"]) != tuple(
        str(item) for item in payload["allowed_evidence_ids"]
    ):
        raise BenchmarkValidationError("raw evidence order/allowlist mismatch")
    raw_ids = [str(item["evidence_id"]) for item in payload["all_raw_evidence"]]
    if len(raw_ids) != len(set(raw_ids)):
        raise BenchmarkValidationError("raw evidence was duplicated")


def _projection_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        output = dict(value)
    elif hasattr(value, "to_dict"):
        output = dict(value.to_dict())
    elif dataclasses.is_dataclass(value):
        output = dataclasses.asdict(value)
    else:
        raise BenchmarkValidationError("arm projection is not serializable")
    return _json_clone(output)


def _arm_payloads(fixture: Any) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    bundles = build_arm_bundle(fixture)
    if tuple(bundles) != ARMS:
        raise BenchmarkValidationError("bridge arm order differs from benchmark lock")
    payloads: dict[str, dict[str, Any]] = {}
    projections: dict[str, dict[str, Any]] = {}
    for arm_id in ARMS:
        payload = build_restart_payload(fixture, arm_id)
        if not isinstance(payload, Mapping):
            raise BenchmarkValidationError("bridge emitted a non-mapping payload")
        payloads[arm_id] = _json_clone(dict(payload))
        projections[arm_id] = _projection_dict(bundles[arm_id])
        _validate_gold_free_payload(payloads[arm_id], arm_id)
        if payloads[arm_id] != _json_clone(build_restart_payload(fixture, arm_id)):
            raise BenchmarkValidationError("bridge payload is not deterministic")
    return payloads, projections


def _provider_receipts(provider: Any) -> list[dict[str, Any]]:
    value = getattr(provider, "audit_receipts", ())
    return json.loads(canonical_json(value))


def _failure_record(error: Exception) -> dict[str, Any]:
    return {
        "exception_class": type(error).__name__,
        "category": getattr(error, "category", None),
        "reason_code": getattr(error, "reason_code", None),
    }


def _expected_live_protocol_fingerprints(
    provider_input: Mapping[str, Any], runtime: Mapping[str, Any]
) -> tuple[str, str]:
    from openai_reasoning_provider_v0_4 import ReasoningCardPayload

    schema_fingerprint = fingerprint(ReasoningCardPayload.model_json_schema())
    protocol_fingerprint = fingerprint(
        {
            "model": runtime["model"],
            "instructions_fingerprint": fingerprint(CONTROLLED_RESTART_INSTRUCTIONS),
            "input_fingerprint": fingerprint(provider_input),
            "text_schema_fingerprint": schema_fingerprint,
            "reasoning": {"effort": runtime["reasoning_effort"]},
            "max_output_tokens": int(runtime["max_output_tokens"]),
            "store": False,
            "service_tier": runtime["service_tier"],
            "truncation": runtime["truncation"],
            "timeout_seconds": float(runtime["timeout_seconds"]),
        }
    )
    return schema_fingerprint, protocol_fingerprint


def _validate_receipt(
    receipt: Any,
    *,
    arm_id: str,
    arm_status: str,
    mode: str,
    provider_input: Mapping[str, Any],
    lock: Mapping[str, Any],
) -> str:
    if not isinstance(receipt, Mapping):
        raise BenchmarkValidationError(f"missing receipt: {arm_id}")
    if set(receipt) != RECEIPT_KEYS:
        raise BenchmarkValidationError(f"receipt schema drifted: {arm_id}")
    if receipt.get("request_fingerprint") != fingerprint(provider_input):
        raise BenchmarkValidationError(f"receipt request fingerprint drifted: {arm_id}")
    if receipt.get("prompt_fingerprint") != fingerprint(
        CONTROLLED_RESTART_INSTRUCTIONS
    ):
        raise BenchmarkValidationError(f"receipt prompt fingerprint drifted: {arm_id}")
    if receipt.get("logical_calls") != 1:
        raise BenchmarkValidationError(f"receipt logical call count drifted: {arm_id}")
    if not _is_finite_nonnegative_number(receipt.get("latency_ms")):
        raise BenchmarkValidationError(f"receipt latency drifted: {arm_id}")
    usage = receipt.get("usage")
    metadata = receipt.get("metadata")
    if not isinstance(usage, Mapping) or not isinstance(metadata, Mapping):
        raise BenchmarkValidationError(f"receipt shape drifted: {arm_id}")
    _validate_usage(usage, arm_id=arm_id)
    if mode == "scripted_plumbing_only":
        if (
            receipt.get("provider") != "local_scripted_v0_5_1"
            or receipt.get("requested_model") is not None
            or receipt.get("returned_model") is not None
            or receipt.get("api_calls") != 0
            or float(receipt.get("latency_ms")) != 0.0
            or usage.get("exact_provider_tokens") is not False
            or set(metadata) != SCRIPTED_RECEIPT_METADATA_KEYS
            or metadata != {"attempt": 1, "plumbing_only": True, "retry_count": 0}
        ):
            raise BenchmarkValidationError(f"scripted receipt drifted: {arm_id}")
        return "completed"
    if mode != "openai_live_dev_canary":
        raise BenchmarkValidationError("unknown artifact execution mode")
    if set(metadata) != LIVE_RECEIPT_METADATA_KEYS:
        raise BenchmarkValidationError(
            f"live receipt metadata schema drifted: {arm_id}"
        )
    runtime = lock["runtime"]
    expected_schema_fingerprint, expected_protocol_fingerprint = (
        _expected_live_protocol_fingerprints(provider_input, runtime)
    )
    if (
        receipt.get("provider") != runtime["provider"]
        or receipt.get("requested_model") != runtime["model"]
        or receipt.get("api_calls") != 1
        or float(receipt["latency_ms"])
        > float(runtime["timeout_seconds"]) * 1000.0 + 5000.0
        or metadata.get("receipt_schema_version")
        != "ebrt-provider-boundary-receipt-v0.4.3"
        or metadata.get("attempt") != 1
        or metadata.get("retry_count") != 0
        or metadata.get("reasoning_effort") != runtime["reasoning_effort"]
        or metadata.get("max_output_tokens") != runtime["max_output_tokens"]
        or metadata.get("store") is not False
        or metadata.get("previous_response_id") is not False
        or metadata.get("truncation") != runtime["truncation"]
        or metadata.get("sdk_version") != runtime["openai"]
        or metadata.get("pydantic_version") != runtime["pydantic"]
        or metadata.get("python_version") != runtime["python"]
        or metadata.get("api_call_count_semantics") != "attempted_client_call"
        or metadata.get("response_schema_fingerprint") != expected_schema_fingerprint
        or metadata.get("semantic_protocol_fingerprint")
        != expected_protocol_fingerprint
    ):
        raise BenchmarkValidationError(f"live receipt runtime drifted: {arm_id}")
    if not (
        isinstance(metadata.get("status"), str)
        and metadata["status"]
        and (
            metadata.get("service_tier") is None
            or isinstance(metadata.get("service_tier"), str)
        )
        and _optional_sha256(metadata.get("response_id_sha256"))
        and _optional_sha256(metadata.get("server_request_id_sha256"))
        and _is_sha256(metadata.get("client_request_id_sha256"))
        and _optional_sha256(metadata.get("provider_body_sha256"))
        and _is_sha256(metadata.get("response_schema_fingerprint"))
        and _is_sha256(metadata.get("semantic_protocol_fingerprint"))
        and type(metadata.get("http_observed")) is bool
        and _is_nonnegative_int(metadata.get("refusal_count"))
    ):
        raise BenchmarkValidationError(f"live receipt diagnostics drifted: {arm_id}")
    body_bytes = metadata.get("provider_body_byte_count")
    if body_bytes is not None and not _is_nonnegative_int(body_bytes):
        raise BenchmarkValidationError(f"live receipt body count drifted: {arm_id}")
    if (metadata.get("provider_body_sha256") is None) != (body_bytes is None):
        raise BenchmarkValidationError(f"live receipt body digest drifted: {arm_id}")
    http_status = metadata.get("http_status_code")
    if http_status is not None and not (
        _is_nonnegative_int(http_status) and 100 <= http_status <= 599
    ):
        raise BenchmarkValidationError(f"live receipt HTTP status drifted: {arm_id}")
    if metadata["http_observed"] is False and any(
        value is not None
        for value in (
            http_status,
            metadata.get("server_request_id_sha256"),
            metadata.get("provider_body_sha256"),
        )
    ):
        raise BenchmarkValidationError(
            f"unobserved HTTP receipt carried data: {arm_id}"
        )
    attempt_outcome = metadata.get("attempt_outcome")
    outcome_boundary = {
        "transport_error": ("request_call", "not_entered", False),
        "http_status_error": ("http_status", "not_entered", True),
        "sdk_parse_error": ("sdk_response_parse", "failed_after_http", True),
        "contract_error": ("provider_contract", "succeeded", True),
    }
    if attempt_outcome == "completed":
        if (
            receipt.get("returned_model") != runtime["model"]
            or usage.get("exact_provider_tokens") is not True
            or metadata.get("status") != "completed"
            or metadata.get("service_tier") != runtime["service_tier"]
            or metadata.get("parse_boundary") != "succeeded"
            or metadata.get("failure_phase") is not None
            or metadata.get("failure_reason_code") is not None
            or metadata.get("failure_type") is not None
            or metadata.get("http_observed") is not True
            or metadata.get("http_status_code") != 200
        ):
            raise BenchmarkValidationError(f"completed live receipt drifted: {arm_id}")
    elif attempt_outcome not in outcome_boundary:
        raise BenchmarkValidationError(f"unknown receipt attempt outcome: {arm_id}")
    else:
        from openai_response_boundary_v0_4_3 import (
            BOUNDARY_REASON_CODES_BY_PHASE,
        )

        expected_phase, expected_parse, expected_http = outcome_boundary[
            attempt_outcome
        ]
        phase = metadata.get("failure_phase")
        reason = metadata.get("failure_reason_code")
        if (
            phase != expected_phase
            or metadata.get("parse_boundary") != expected_parse
            or metadata.get("http_observed") is not expected_http
            or reason not in BOUNDARY_REASON_CODES_BY_PHASE[expected_phase]
            or metadata.get("failure_type") != reason
            or arm_status != "failed"
        ):
            raise BenchmarkValidationError(f"failed live receipt drifted: {arm_id}")
        if attempt_outcome == "transport_error" and (
            metadata.get("status") != "no_http_response" or http_status is not None
        ):
            raise BenchmarkValidationError(f"transport receipt drifted: {arm_id}")
        if attempt_outcome == "http_status_error" and (
            metadata.get("status") != "http_status_error"
            or http_status is None
            or http_status < 400
        ):
            raise BenchmarkValidationError(f"HTTP error receipt drifted: {arm_id}")
        if attempt_outcome in {"sdk_parse_error", "contract_error"} and (
            http_status != 200
        ):
            raise BenchmarkValidationError(f"post-HTTP receipt drifted: {arm_id}")
    if arm_status == "completed" and attempt_outcome != "completed":
        raise BenchmarkValidationError(f"completed arm has failed receipt: {arm_id}")
    return str(attempt_outcome)


def execute_gold_free(
    fixture: Any,
    providers: Mapping[str, Any],
    arm_order: Sequence[str],
) -> dict[str, Any]:
    """Execute every arm without parsing or attaching semantic gold."""

    if set(providers) != set(ARMS):
        raise BenchmarkValidationError("providers do not cover the four arms")
    if tuple(sorted(arm_order)) != tuple(sorted(ARMS)):
        raise BenchmarkValidationError("arm execution order is not a permutation")
    payloads, projections = _arm_payloads(fixture)
    executions: dict[str, Any] = {}
    for run_position, arm_id in enumerate(arm_order):
        provider = providers[arm_id]
        before = len(_provider_receipts(provider))
        payload = payloads[arm_id]
        candidate_card: dict[str, Any] | None = None
        try:
            result = provider.generate(payload)
            if not isinstance(result, CardResult):
                raise BenchmarkValidationError(
                    "provider returned the wrong result type"
                )
            candidate_card = result.card.to_dict()
            receipt = result.receipt.to_dict()
            validate_public_card(
                fixture,
                arm_id,
                candidate_card,
                receipt,
            )
            observed = _provider_receipts(provider)[before:]
            if len(observed) != 1 or observed[0] != receipt:
                raise BenchmarkValidationError(
                    "one provider attempt did not produce exactly one matching receipt"
                )
            executions[arm_id] = {
                "arm_id": arm_id,
                "run_position": run_position,
                "status": "completed",
                "provider_input": payload,
                "provider_input_fingerprint_sha256": fingerprint(payload),
                "projection": projections[arm_id],
                "final_card": candidate_card,
                "receipt": receipt,
                "failure": None,
            }
        except Exception as error:
            observed = _provider_receipts(provider)[before:]
            executions[arm_id] = {
                "arm_id": arm_id,
                "run_position": run_position,
                "status": "failed",
                "provider_input": payload,
                "provider_input_fingerprint_sha256": fingerprint(payload),
                "projection": projections[arm_id],
                "final_card": None,
                "rejected_candidate_card": candidate_card,
                "receipt": observed[0] if len(observed) == 1 else None,
                "observed_receipt_count": len(observed),
                "failure": _failure_record(error),
            }
    return {
        "arm_order": list(arm_order),
        "executions": executions,
        "attempted_arms": len(arm_order),
    }


def _load_case_gold(fixture: Any) -> dict[str, Any]:
    gold_file = _load_json(GOLD_PATH)
    matches = [
        item
        for item in gold_file.get("cases", ())
        if str(item.get("case_id")) == fixture.case.case_id
    ]
    if len(matches) != 1:
        raise BenchmarkValidationError("separate gold did not contain one bound case")
    _validate_gold(fixture.case, matches[0])
    return matches[0]


def _validate_source_case_alignment(fixture: Any) -> None:
    source = _load_json(SOURCE_CASES_PATH)
    matches = [
        item
        for item in source.get("cases", ())
        if str(item.get("case_id")) == fixture.case.case_id
    ]
    if len(matches) != 1:
        raise BenchmarkValidationError("source fixture did not contain one bound case")
    source_case = CaseSpec.from_mapping(matches[0])
    if source_case.public_context() != fixture.case.public_context():
        raise BenchmarkValidationError(
            "embedded bridge case drifted from the pinned public source case"
        )


def _unavailable_grade() -> dict[str, Any]:
    return {
        "available": False,
        "machine_success": False,
        "evidence_consistent": False,
        "checks": None,
        "support_evidence_ids": [],
        "unexpected_support_evidence_ids": [],
        "missing_required_evidence_ids": [],
        "citation_precision": None,
        "citation_recall": None,
    }


def _surrogate_diagnostic(fixture: Any) -> dict[str, Any]:
    suite = build_case_temporal_suite(fixture)
    program = suite.materialize(fixture.binding.pair_id, fixture.binding.order_variant)
    result = TemporalAdjointStateController().optimize(program, "transition")
    control_map = result.to_execution_control_map()
    return {
        "status": control_map["status"],
        "schema_version": control_map["schema_version"],
        "source_control_map_fingerprint_sha256": control_map["fingerprint_sha256"],
        "source": control_map["source"],
        "budget": control_map["budget"],
        "controls": control_map["controls"],
        "objective_before": control_map["surrogate"]["objective_before"],
        "objective_after": control_map["surrogate"]["objective_after"],
        "gradient_boundary": control_map["controller"]["gradient_boundary"],
        "actual_output_participated": False,
    }


def finalize_after_calls(
    fixture: Any,
    execution: Mapping[str, Any],
    gold: Mapping[str, Any],
    *,
    mode: str,
    source_snapshot: Mapping[str, str],
) -> dict[str, Any]:
    arms = copy.deepcopy(dict(execution["executions"]))
    for arm_id in ARMS:
        arm = arms[arm_id]
        if arm["status"] == "completed":
            arm["grade"] = {
                "available": True,
                **grade_card(arm["final_card"], gold),
            }
        else:
            arm["grade"] = _unavailable_grade()
    comparisons: dict[str, Any] = {}
    baseline = arms[ARMS[0]]["final_card"]
    if baseline is not None:
        for arm_id in ARMS[1:]:
            final_card = arms[arm_id]["final_card"]
            if final_card is not None:
                comparisons[f"{ARMS[0]}__to__{arm_id}"] = public_card_diff(
                    fixture, baseline, final_card
                )
    receipts = [arm["receipt"] for arm in arms.values() if arm["receipt"] is not None]
    api_calls = sum(int(item["api_calls"]) for item in receipts)
    all_completed = all(arms[arm]["status"] == "completed" for arm in ARMS)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "COMPLETE_CANARY" if all_completed else "INCOMPLETE_CANARY",
        "mode": mode,
        "case": {
            "case_id": fixture.case.case_id,
            "family": fixture.case.family,
            "fixture_id": fixture.fixture_id,
            "public_context": _json_clone(fixture.case.public_context()),
        },
        "execution": {
            "arm_order": list(execution["arm_order"]),
            "expected_attempts": 4,
            "observed_receipts": len(receipts),
            "observed_api_calls": api_calls,
            "retry_policy": "one_attempt_no_retry",
            "semantic_gold_parsed_after_all_attempts": True,
        },
        "arms": arms,
        "comparisons": comparisons,
        "surrogate_diagnostic": _surrogate_diagnostic(fixture),
        "surrogate_actual_separation": copy.deepcopy(SURROGATE_ACTUAL_SEPARATION),
        "decision": {
            "bridge_complete": all_completed,
            "strict_pass_arms": [
                arm for arm in ARMS if arms[arm]["grade"]["machine_success"]
            ],
            "controlled_diff_available": (f"{ARMS[0]}__to__{ARMS[-1]}" in comparisons),
            "promotion_eligible": False,
        },
        "source_snapshot_sha256": dict(source_snapshot),
        "claim_boundary": list(RESULT_CLAIM_BOUNDARY),
    }
    payload["fingerprint_sha256"] = _sha256_bytes(_canonical_json_bytes(payload))
    return payload


def _call_rows(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for arm_id in result["execution"]["arm_order"]:
        arm = result["arms"][arm_id]
        rows.append(
            {
                "arm_id": arm_id,
                "run_position": arm["run_position"],
                "status": arm["status"],
                "provider_input_fingerprint_sha256": arm[
                    "provider_input_fingerprint_sha256"
                ],
                "receipt": arm["receipt"],
                "failure": arm["failure"],
            }
        )
    return rows


def _report(result: Mapping[str, Any]) -> str:
    lines = [
        "# EBRT v0.5.1 Controlled Raw Restart — Canary",
        "",
        f"Status: **{result['status']}**",
        "",
        f"Case: `{result['case']['case_id']}`",
        f"Mode: `{result['mode']}`",
        "",
        "| Arm | Status | Strict pass | Answer | API calls |",
        "| --- | --- | ---: | --- | ---: |",
    ]
    for arm_id in ARMS:
        arm = result["arms"][arm_id]
        card = arm["final_card"]
        answer = "—" if card is None else card["current_answer"]
        calls = 0 if arm["receipt"] is None else arm["receipt"]["api_calls"]
        lines.append(
            f"| `{arm_id}` | {arm['status']} | "
            f"{str(arm['grade']['machine_success']).lower()} | {answer} | {calls} |"
        )
    controlled_key = f"{ARMS[0]}__to__{ARMS[-1]}"
    lines.extend(["", "## Baseline to controlled public output diff", ""])
    if controlled_key in result["comparisons"]:
        lines.append("```json")
        lines.append(
            json.dumps(
                result["comparisons"][controlled_key],
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        lines.append("```")
    else:
        lines.append("Unavailable because one or both public cards were rejected.")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            *[f"- {item}" for item in result["claim_boundary"]],
            "",
        ]
    )
    return "\n".join(lines)


def _materialize_bundle(
    result: Mapping[str, Any], lock: Mapping[str, Any]
) -> dict[str, bytes]:
    artifacts: dict[str, bytes] = {
        "results.json": _pretty_json_bytes(result),
        "calls.jsonl": b"".join(
            _canonical_json_bytes(row, trailing_newline=True)
            for row in _call_rows(result)
        ),
        "report.md": _report(result).encode("utf-8"),
    }
    manifest = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "status": result["status"],
        "success_manifest": result["status"] == "COMPLETE_CANARY",
        "result_fingerprint_sha256": result["fingerprint_sha256"],
        "policy_lock": {
            "path": str(LOCK_PATH.relative_to(ROOT)),
            "sha256": _sha256_path(LOCK_PATH),
        },
        "source_snapshot_sha256": dict(result["source_snapshot_sha256"]),
        "runtime": _runtime(),
        "artifacts": {
            name: {"sha256": _sha256_bytes(value), "bytes": len(value)}
            for name, value in artifacts.items()
        },
        "claim_boundary": lock["claim_boundary"],
    }
    artifacts["manifest.json"] = _pretty_json_bytes(manifest)
    return artifacts


def _publish(output: Path, artifacts: Mapping[str, bytes]) -> None:
    if output.exists():
        raise BenchmarkValidationError(f"output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent)
    )
    try:
        for name, value in artifacts.items():
            (staging / name).write_bytes(value)
        validate_bundle(staging)
        os.replace(staging, output)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def write_bundle(
    output: Path, result: Mapping[str, Any], lock: Mapping[str, Any]
) -> dict[str, str]:
    artifacts = _materialize_bundle(result, lock)
    _publish(output, artifacts)
    validate_bundle(output)
    return {name: _sha256_bytes(value) for name, value in artifacts.items()}


def validate_bundle(output: Path) -> None:
    lock = _load_lock()
    entries = tuple(sorted(item.name for item in output.iterdir()))
    if entries != tuple(sorted(ARTIFACT_FILES)):
        raise BenchmarkValidationError("artifact file set mismatch")
    for item in output.iterdir():
        if item.is_symlink() or not item.is_file():
            raise BenchmarkValidationError("artifact entries must be regular files")
    manifest = _load_json(output / "manifest.json")
    if (
        manifest.get("schema_version") != ARTIFACT_SCHEMA_VERSION
        or set(manifest.get("artifacts", {}))
        != {"results.json", "calls.jsonl", "report.md"}
        or manifest.get("runtime") != _runtime()
        or manifest.get("claim_boundary") != lock["claim_boundary"]
        or manifest.get("policy_lock")
        != {
            "path": str(LOCK_PATH.relative_to(ROOT)),
            "sha256": _sha256_path(LOCK_PATH),
        }
    ):
        raise BenchmarkValidationError("artifact manifest contract drifted")
    for name, record in manifest["artifacts"].items():
        value = (output / name).read_bytes()
        if _sha256_bytes(value) != record["sha256"] or len(value) != record["bytes"]:
            raise BenchmarkValidationError(f"artifact digest mismatch: {name}")
    result = _load_json(output / "results.json")
    expected_result_keys = {
        "schema_version",
        "status",
        "mode",
        "case",
        "execution",
        "arms",
        "comparisons",
        "surrogate_diagnostic",
        "surrogate_actual_separation",
        "decision",
        "source_snapshot_sha256",
        "claim_boundary",
        "fingerprint_sha256",
    }
    if set(result) != expected_result_keys:
        raise BenchmarkValidationError("result schema drifted")
    fingerprint_value = result.pop("fingerprint_sha256")
    if fingerprint_value != _sha256_bytes(_canonical_json_bytes(result)):
        raise BenchmarkValidationError("result fingerprint mismatch")
    result["fingerprint_sha256"] = fingerprint_value
    if (
        manifest["result_fingerprint_sha256"] != fingerprint_value
        or manifest["status"] != result["status"]
        or manifest["success_manifest"] is not (result["status"] == "COMPLETE_CANARY")
    ):
        raise BenchmarkValidationError("manifest/result fingerprint mismatch")
    fixture = load_bridge_fixture(BRIDGE_FIXTURE_PATH)
    _validate_source_case_alignment(fixture)
    gold = _load_case_gold(fixture)
    expected_payloads, expected_projections = _arm_payloads(fixture)
    if result["schema_version"] != SCHEMA_VERSION or result["mode"] not in {
        "scripted_plumbing_only",
        "openai_live_dev_canary",
    }:
        raise BenchmarkValidationError("result identity drifted")
    if result["case"] != {
        "case_id": fixture.case.case_id,
        "family": fixture.case.family,
        "fixture_id": fixture.fixture_id,
        "public_context": _json_clone(fixture.case.public_context()),
    }:
        raise BenchmarkValidationError("result case projection drifted")
    if result["source_snapshot_sha256"] != _source_snapshot(lock):
        raise BenchmarkValidationError("result source snapshot drifted")
    if result["claim_boundary"] != list(RESULT_CLAIM_BOUNDARY):
        raise BenchmarkValidationError("result claim boundary drifted")
    if result["surrogate_actual_separation"] != SURROGATE_ACTUAL_SEPARATION:
        raise BenchmarkValidationError("surrogate/actual boundary drifted")
    if result["surrogate_diagnostic"] != _surrogate_diagnostic(fixture):
        raise BenchmarkValidationError("stored surrogate diagnostic drifted")
    if set(result["arms"]) != set(ARMS):
        raise BenchmarkValidationError("stored arms drifted")
    receipt_count = 0
    api_calls = 0
    for arm_id in ARMS:
        arm = result["arms"][arm_id]
        if not isinstance(arm, Mapping) or arm.get("status") not in {
            "completed",
            "failed",
        }:
            raise BenchmarkValidationError(f"stored arm status drifted: {arm_id}")
        expected_arm_keys = (
            COMPLETED_ARM_KEYS if arm["status"] == "completed" else FAILED_ARM_KEYS
        )
        if set(arm) != expected_arm_keys:
            raise BenchmarkValidationError(f"stored arm schema drifted: {arm_id}")
        expected_position = result["execution"]["arm_order"].index(arm_id)
        if (
            arm.get("arm_id") != arm_id
            or arm.get("run_position") != expected_position
            or arm.get("provider_input") != expected_payloads[arm_id]
            or arm.get("provider_input_fingerprint_sha256")
            != fingerprint(expected_payloads[arm_id])
            or arm.get("projection") != expected_projections[arm_id]
        ):
            raise BenchmarkValidationError(f"stored arm projection drifted: {arm_id}")
        receipt_outcome = _validate_receipt(
            arm.get("receipt"),
            arm_id=arm_id,
            arm_status=arm["status"],
            mode=result["mode"],
            provider_input=expected_payloads[arm_id],
            lock=lock,
        )
        receipt_count += 1
        api_calls += int(arm["receipt"]["api_calls"])
        if arm["status"] == "completed":
            if arm.get("final_card") is None or arm.get("failure") is not None:
                raise BenchmarkValidationError(f"completed arm shape drifted: {arm_id}")
            validate_public_card(
                fixture,
                arm_id,
                arm["final_card"],
                arm["receipt"],
            )
            expected_grade = {
                "available": True,
                **grade_card(arm["final_card"], gold),
            }
        else:
            failure = arm.get("failure")
            if (
                arm.get("final_card") is not None
                or arm.get("observed_receipt_count") != 1
                or not isinstance(failure, Mapping)
                or set(failure) != FAILURE_RECORD_KEYS
            ):
                raise BenchmarkValidationError(f"failed arm shape drifted: {arm_id}")
            rejected = arm.get("rejected_candidate_card")
            if receipt_outcome == "completed":
                if not isinstance(rejected, Mapping):
                    raise BenchmarkValidationError(
                        f"local rejection card is missing: {arm_id}"
                    )
                try:
                    validate_public_card(
                        fixture,
                        arm_id,
                        rejected,
                        arm["receipt"],
                    )
                except Exception as error:
                    if failure != _failure_record(error):
                        raise BenchmarkValidationError(
                            f"local rejection reason drifted: {arm_id}"
                        ) from error
                else:
                    raise BenchmarkValidationError(
                        f"stored local rejection now passes: {arm_id}"
                    )
            elif (
                rejected is not None
                or failure.get("exception_class") != "OpenAIProviderBoundaryError"
                or failure.get("category") != "provider_boundary_error"
                or failure.get("reason_code")
                != arm["receipt"]["metadata"]["failure_reason_code"]
            ):
                raise BenchmarkValidationError(
                    f"provider failure record drifted: {arm_id}"
                )
            expected_grade = _unavailable_grade()
        if arm["grade"] != expected_grade:
            raise BenchmarkValidationError(f"stored grade drifted: {arm_id}")
    expected_status = (
        "COMPLETE_CANARY"
        if all(result["arms"][arm]["status"] == "completed" for arm in ARMS)
        else "INCOMPLETE_CANARY"
    )
    expected_execution = {
        "arm_order": list(LOCKED_ARM_ORDER),
        "expected_attempts": 4,
        "observed_receipts": receipt_count,
        "observed_api_calls": api_calls,
        "retry_policy": "one_attempt_no_retry",
        "semantic_gold_parsed_after_all_attempts": True,
    }
    if result["status"] != expected_status or result["execution"] != expected_execution:
        raise BenchmarkValidationError("stored execution accounting drifted")
    expected_comparisons: dict[str, Any] = {}
    baseline = result["arms"][ARMS[0]]["final_card"]
    if baseline is not None:
        for arm_id in ARMS[1:]:
            card = result["arms"][arm_id]["final_card"]
            key = f"{ARMS[0]}__to__{arm_id}"
            if card is not None:
                expected_comparisons[key] = public_card_diff(fixture, baseline, card)
    if result["comparisons"] != expected_comparisons:
        raise BenchmarkValidationError("stored public comparisons drifted")
    expected_decision = {
        "bridge_complete": expected_status == "COMPLETE_CANARY",
        "strict_pass_arms": [
            arm for arm in ARMS if result["arms"][arm]["grade"]["machine_success"]
        ],
        "controlled_diff_available": (
            f"{ARMS[0]}__to__{ARMS[-1]}" in expected_comparisons
        ),
        "promotion_eligible": False,
    }
    if result["decision"] != expected_decision:
        raise BenchmarkValidationError("stored decision drifted")
    if manifest["source_snapshot_sha256"] != _source_snapshot(lock):
        raise BenchmarkValidationError("artifact source snapshot drifted")
    expected_bundle = _materialize_bundle(result, lock)
    for name in ARTIFACT_FILES:
        if (output / name).read_bytes() != expected_bundle[name]:
            raise BenchmarkValidationError(f"artifact bytes drifted: {name}")


class _ScriptedProvider:
    """Deterministic plumbing provider; never evidence for model quality."""

    def __init__(self, arm_id: str) -> None:
        self.arm_id = arm_id
        self.audit_receipts: list[dict[str, Any]] = []

    def generate(self, input_payload: Mapping[str, Any]) -> CardResult:
        if [item["evidence_id"] for item in input_payload["all_raw_evidence"]] != [
            "R1",
            "R2",
            "R3",
            "R4",
            "R5",
            "R6",
        ]:
            raise AssertionError("scripted provider received the wrong raw order")
        correct = self.arm_id in {
            "raw_restart_textual_envelope",
            "controlled_raw_restart",
        }
        card = ReasoningCard(
            checkpoint_id=str(input_payload["checkpoint_id"]),
            claim=(
                "NERA's corrected B2 route maps to BLUE."
                if correct
                else "NERA's route is reported as AMBER despite the correction."
            ),
            topic="nera_route_code",
            stance=-1.0 if correct else 0.0,
            confidence=1.0,
            evidence_ids=("R2", "R5", "R6"),
            current_answer="BLUE" if correct else "AMBER",
            revision_cue=1.0,
            decision_facts=(
                DecisionFact(slot="current_code", value="B2", evidence_ids=("R6",)),
                DecisionFact(
                    slot="bay",
                    value="BLUE" if correct else "AMBER",
                    evidence_ids=("R2", "R6"),
                ),
                DecisionFact(slot="cargo_seal", value="SEALED", evidence_ids=("R5",)),
            ),
            invalidated_evidence_ids=("R3",),
        )
        receipt = ProviderReceipt(
            provider="local_scripted_v0_5_1",
            requested_model=None,
            returned_model=None,
            logical_calls=1,
            api_calls=0,
            latency_ms=0.0,
            request_fingerprint=fingerprint(input_payload),
            prompt_fingerprint=fingerprint(CONTROLLED_RESTART_INSTRUCTIONS),
            usage=ProviderUsage(exact_provider_tokens=False),
            metadata={"plumbing_only": True, "attempt": 1, "retry_count": 0},
        )
        self.audit_receipts.append(receipt.to_dict())
        return CardResult(card=card, receipt=receipt)


@contextmanager
def _network_guard() -> Iterator[None]:
    with mock.patch.object(
        socket, "socket", side_effect=AssertionError("network used in offline test")
    ):
        yield


def run_self_tests() -> dict[str, Any]:
    lock = _load_lock()
    bridge = run_bridge_self_tests()
    if bridge.get("status") != "PASS":
        raise AssertionError("bridge self-test did not pass")
    fixture = load_bridge_fixture(BRIDGE_FIXTURE_PATH)
    _validate_source_case_alignment(fixture)
    providers = {arm: _ScriptedProvider(arm) for arm in ARMS}
    with _network_guard():
        execution = execute_gold_free(
            fixture, providers, lock["execution"]["arm_order"]
        )
    # This is the first semantic gold parse in the self-test execution path.
    gold = _load_case_gold(fixture)
    result = finalize_after_calls(
        fixture,
        execution,
        gold,
        mode="scripted_plumbing_only",
        source_snapshot=_source_snapshot(lock),
    )
    if result["status"] != "COMPLETE_CANARY":
        raise AssertionError("scripted canary did not complete")
    if result["arms"][ARMS[0]]["grade"]["machine_success"]:
        raise AssertionError("negative scripted baseline unexpectedly passed")
    if not result["arms"][ARMS[-1]]["grade"]["machine_success"]:
        raise AssertionError("positive scripted controlled arm did not pass")
    controlled_key = f"{ARMS[0]}__to__{ARMS[-1]}"
    if not result["comparisons"][controlled_key]["answer_changed"]:
        raise AssertionError("scripted public output diff did not change answer")
    diagnostic = result["surrogate_diagnostic"]
    if not (
        diagnostic["objective_after"]["total"] < diagnostic["objective_before"]["total"]
        and diagnostic["actual_output_participated"] is False
    ):
        raise AssertionError("surrogate/actual result separation drifted")
    if any(
        provider.audit_receipts[0]["api_calls"] != 0 for provider in providers.values()
    ):
        raise AssertionError("offline provider recorded an API call")
    import httpx
    from openai import OpenAI
    from openai_response_boundary_v0_4_3 import (
        _offline_response,
        make_openai_mapping_provider_v0_4_3,
    )

    controlled_payload = execution["executions"][ARMS[-1]]["provider_input"]
    controlled_card = copy.deepcopy(result["arms"][ARMS[-1]]["final_card"])
    controlled_card.pop("schema_version", None)

    def offline_handler(request: Any) -> Any:
        return httpx.Response(
            200,
            headers={"x-request-id": "v051-offline-receipt"},
            json=_offline_response(controlled_card),
            request=request,
        )

    http_client = httpx.Client(transport=httpx.MockTransport(offline_handler))
    client = OpenAI(
        api_key="offline-v051-self-test",
        base_url="https://offline.invalid/v1",
        http_client=http_client,
        max_retries=0,
    )
    try:
        live_provider = make_openai_mapping_provider_v0_4_3(
            model=lock["runtime"]["model"],
            reasoning_effort=lock["runtime"]["reasoning_effort"],
            timeout_seconds=float(lock["runtime"]["timeout_seconds"]),
            max_output_tokens=int(lock["runtime"]["max_output_tokens"]),
            instructions=CONTROLLED_RESTART_INSTRUCTIONS,
            client=client,
        )
        with _network_guard():
            offline_live_result = live_provider.generate(controlled_payload)
        validate_public_card(
            fixture,
            ARMS[-1],
            offline_live_result.card.to_dict(),
            offline_live_result.receipt.to_dict(),
        )
        _validate_receipt(
            offline_live_result.receipt.to_dict(),
            arm_id=ARMS[-1],
            arm_status="completed",
            mode="openai_live_dev_canary",
            provider_input=controlled_payload,
            lock=lock,
        )
        tampered_protocol = offline_live_result.receipt.to_dict()
        tampered_protocol["metadata"]["semantic_protocol_fingerprint"] = "0" * 64
        try:
            _validate_receipt(
                tampered_protocol,
                arm_id=ARMS[-1],
                arm_status="completed",
                mode="openai_live_dev_canary",
                provider_input=controlled_payload,
                lock=lock,
            )
        except BenchmarkValidationError:
            pass
        else:
            raise AssertionError("forged live protocol fingerprint was accepted")
    finally:
        client.close()
    with tempfile.TemporaryDirectory(prefix="ebrt-v051-bundle-test-") as raw:
        root = Path(raw)
        output = root / "bundle"
        write_bundle(output, result, lock)
        validate_bundle(output)

        def expect_resigned_tamper_rejected(
            name: str, tampered_result: dict[str, Any]
        ) -> None:
            tampered_result = copy.deepcopy(tampered_result)
            tampered_result.pop("fingerprint_sha256", None)
            tampered_result["fingerprint_sha256"] = _sha256_bytes(
                _canonical_json_bytes(tampered_result)
            )
            tampered_output = root / name
            tampered_output.mkdir()
            for filename, value in _materialize_bundle(tampered_result, lock).items():
                (tampered_output / filename).write_bytes(value)
            try:
                validate_bundle(tampered_output)
            except BenchmarkValidationError:
                return
            raise AssertionError(f"resigned tamper was accepted: {name}")

        tampered_diff = copy.deepcopy(result)
        tampered_diff["comparisons"][controlled_key]["answer_after"] = "TAMPERED"
        expect_resigned_tamper_rejected("tampered-diff", tampered_diff)

        tampered_receipt = copy.deepcopy(result)
        receipt = tampered_receipt["arms"][ARMS[0]]["receipt"]
        receipt["provider"] = "forged"
        receipt["prompt_fingerprint"] = "0" * 64
        receipt["api_calls"] = 999
        tampered_receipt["execution"]["observed_api_calls"] = 999
        expect_resigned_tamper_rejected("tampered-receipt", tampered_receipt)

        tampered_latency = copy.deepcopy(result)
        tampered_latency["arms"][ARMS[0]]["receipt"]["latency_ms"] = 999_999.0
        expect_resigned_tamper_rejected("tampered-latency", tampered_latency)

        tampered_usage = copy.deepcopy(result)
        usage = tampered_usage["arms"][ARMS[0]]["receipt"]["usage"]
        usage["exact_provider_tokens"] = True
        usage["input_tokens"] = 5
        usage["output_tokens"] = 7
        usage["total_tokens"] = 999
        usage["cached_input_tokens"] = 0
        usage["cache_write_tokens"] = 0
        usage["reasoning_tokens"] = 0
        expect_resigned_tamper_rejected("tampered-usage", tampered_usage)

        tampered_schema = copy.deepcopy(result)
        tampered_schema["arms"][ARMS[0]]["receipt"]["unknown_field"] = True
        tampered_schema["arms"][ARMS[1]]["unknown_field"] = True
        expect_resigned_tamper_rejected("tampered-schema", tampered_schema)

        tampered_derived = copy.deepcopy(result)
        tampered_derived["decision"]["promotion_eligible"] = True
        tampered_derived["execution"]["semantic_gold_parsed_after_all_attempts"] = False
        tampered_derived["claim_boundary"] = ["forged claim"]
        expect_resigned_tamper_rejected("tampered-derived", tampered_derived)
    return {
        "status": "PASS",
        "checks": [
            "case-bound bridge self-tests and no-event identity pass",
            "all four gold-free payloads materialize before execution",
            "one scripted receipt is finalized per arm with zero network calls",
            "mock-transport live receipt and runtime-protocol seals validate offline",
            "strict grading begins only after every arm attempt",
            "surrogate status and actual grade remain separate",
            "public output diff recomputes from stored public cards",
            "resigned diff, receipt schema/runtime/usage, accounting, and derived-claim tampering is rejected",
        ],
        "result_fingerprint_sha256": result["fingerprint_sha256"],
        "claim_boundary": "Offline scripted plumbing only; no hosted-model quality evidence.",
    }


def _make_live_providers(lock: Mapping[str, Any]) -> dict[str, Any]:
    from openai_response_boundary_v0_4_3 import (
        make_openai_mapping_provider_v0_4_3,
    )

    runtime = lock["runtime"]
    return {
        arm: make_openai_mapping_provider_v0_4_3(
            model=runtime["model"],
            reasoning_effort=runtime["reasoning_effort"],
            timeout_seconds=float(runtime["timeout_seconds"]),
            max_output_tokens=int(runtime["max_output_tokens"]),
            instructions=CONTROLLED_RESTART_INSTRUCTIONS,
        )
        for arm in ARMS
    }


def preflight() -> dict[str, Any]:
    lock = _load_lock(verify_gold=False)
    fixture = load_bridge_fixture(BRIDGE_FIXTURE_PATH)
    _validate_source_case_alignment(fixture)
    payloads, _ = _arm_payloads(fixture)
    if not os.environ.get("OPENAI_API_KEY"):
        raise BenchmarkValidationError("OPENAI_API_KEY is unavailable")
    providers = _make_live_providers(lock)
    provenances = [provider.provenance for provider in providers.values()]
    if len({canonical_json(item) for item in provenances}) != 1:
        raise BenchmarkValidationError("live provider configuration differs by arm")
    if any(provider.audit_receipts for provider in providers.values()):
        raise BenchmarkValidationError(
            "preflight unexpectedly recorded a provider call"
        )
    return {
        "status": "READY",
        "case_id": fixture.case.case_id,
        "arms": list(ARMS),
        "expected_api_attempts": 4,
        "provider": provenances[0],
        "payload_fingerprints": {arm: fingerprint(payloads[arm]) for arm in ARMS},
        "source_snapshot_sha256": _source_snapshot(lock),
    }


def run_live(output: Path) -> dict[str, Any]:
    if output.exists():
        raise BenchmarkValidationError(f"output already exists: {output}")
    lock = _load_lock(verify_gold=False)
    before = _source_snapshot(lock)
    ready = preflight()
    fixture = load_bridge_fixture(BRIDGE_FIXTURE_PATH)
    providers = _make_live_providers(lock)
    execution = execute_gold_free(fixture, providers, lock["execution"]["arm_order"])
    if _source_snapshot(lock) != before:
        raise BenchmarkValidationError("source graph changed during provider execution")
    # Frozen predecessor imports may have hashed gold bytes for source integrity,
    # but the benchmark first validates and parses semantic gold here.
    _verify_locked_fixture(lock, "gold")
    gold = _load_case_gold(fixture)
    result = finalize_after_calls(
        fixture,
        execution,
        gold,
        mode="openai_live_dev_canary",
        source_snapshot=before,
    )
    sha256 = write_bundle(output, result, lock)
    return {
        "status": result["status"],
        "output": str(output),
        "result_fingerprint_sha256": result["fingerprint_sha256"],
        "strict_pass_arms": result["decision"]["strict_pass_arms"],
        "controlled_diff_available": result["decision"]["controlled_diff_available"],
        "expected_api_attempts": ready["expected_api_attempts"],
        "observed_api_calls": result["execution"]["observed_api_calls"],
        "artifact_sha256": sha256,
    }


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("self-test")
    subparsers.add_parser("preflight")
    live = subparsers.add_parser("live-canary")
    live.add_argument("--output", type=Path, default=DEFAULT_LIVE_OUTPUT)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--artifact-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "self-test":
        _print_json(run_self_tests())
    elif args.command == "preflight":
        _print_json(preflight())
    elif args.command == "live-canary":
        _print_json(run_live(args.output))
    else:
        validate_bundle(args.artifact_dir)
        _print_json({"status": "VALID", "artifact_dir": str(args.artifact_dir)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
