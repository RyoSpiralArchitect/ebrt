#!/usr/bin/env python3
"""Prospective provider-boundary diagnostics for EBRT v0.4.3.

This runner is deliberately a thin overlay on the frozen v0.4.2 reasoning
experiment.  The four arms, prompts, fixtures, gold, budgets, order, local
validator, primary endpoints, and no-retry policy are inherited unchanged.
The only provider-facing change is delegated to the public v0.4.3 adapter,
which observes ``with_raw_response.parse -> raw.parse`` and emits one sanitized
receipt for each attempted client call.

Provider, SDK, receipt-audit, capability, and internal failures are
non-assessable.  Only the thirteen inherited local public-card validator codes
remain assessed strict failures.  No raw provider response, exception message,
header set, rejected card, credential, or private chain-of-thought is persisted.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import io
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

import benchmark_aperture_controls_v0_4_1 as v041
import benchmark_aperture_controls_v0_4_2 as v042
import openai_response_boundary_v0_4_3 as provider_boundary
from language_replay_bridge_v0_4 import ProviderReceipt, ProviderUsage, canonical_json
from openai_response_boundary_v0_4_3 import (
    BOUNDARY_PHASES,
    BOUNDARY_REASON_CODES,
    BOUNDARY_REASON_CODES_BY_PHASE,
    OpenAIBoundaryCapabilityError,
    OpenAIProviderBoundaryError,
    RECEIPT_SCHEMA_VERSION,
    make_openai_mapping_provider_v0_4_3,
)


ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = "ebrt-aperture-controls-benchmark-v0.4.3"
MANIFEST_SCHEMA_VERSION = "ebrt-aperture-controls-manifest-v0.4.3"
POLICY_SCHEMA_VERSION = "ebrt-provider-boundary-policy-lock-v0.4.3"

LOCK_PATH = ROOT / "policy_lock_aperture_controls_v0_4_3.json"
PREDECESSOR_RUNNER_PATH = ROOT / "benchmark_aperture_controls_v0_4_2.py"
R01_SMOKE_MANIFEST_PATH = ROOT / (
    "artifacts/benchmark_aperture_controls_v0_4_2_unchanged_replication_r01_"
    "contract_smoke/manifest.json"
)
R01_FULL_MANIFEST_PATH = ROOT / (
    "artifacts/benchmark_aperture_controls_v0_4_2_unchanged_replication_r01_dev/"
    "manifest.json"
)

DEFAULT_SMOKE_OUTPUT = (
    ROOT / "benchmark_results" / "v0_4_3_provider_boundary_contract_smoke"
)
DEFAULT_DEV_OUTPUT = ROOT / "benchmark_results" / "v0_4_3_provider_boundary_dev"
CANONICAL_SMOKE_OUTPUT = (
    ROOT / "artifacts" / "benchmark_aperture_controls_v0_4_3_contract_smoke"
)
CANONICAL_DEV_OUTPUT = ROOT / "artifacts" / "benchmark_aperture_controls_v0_4_3_dev"

ARMS = v042.ARMS
ONE_SHOT_ARMS = v042.ONE_SHOT_ARMS
STAGED_ARMS = v042.STAGED_ARMS
LOCKED_TRIALS = v042.LOCKED_TRIALS
LOCKED_CASE_COUNT = v042.LOCKED_CASE_COUNT
LOCKED_CALLS_PER_CASE_TRIAL = v042.LOCKED_CALLS_PER_CASE_TRIAL
ONE_SHOT_INSTRUCTIONS = v042.ONE_SHOT_INSTRUCTIONS
STAGED_INSTRUCTIONS = v042.STAGED_INSTRUCTIONS
LOCAL_CONTRACT_REASON_CODES = v042.LOCAL_CONTRACT_REASON_CODES

PROVIDER_BOUNDARY_PHASES = BOUNDARY_PHASES
PROVIDER_BOUNDARY_REASON_CODES = BOUNDARY_REASON_CODES
MODE_SMOKE = "openai_live_provider_boundary_smoke_v0_4_3"
MODE_DEV = "openai_live_dev_aperture_controls_v0_4_3"

RECEIPT_METADATA_FIELDS = frozenset(
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

OUTCOME_BY_PHASE = {
    "request_call": "transport_error",
    "http_status": "http_status_error",
    "sdk_response_parse": "sdk_parse_error",
    "provider_contract": "contract_error",
}
PARSE_BOUNDARY_BY_PHASE = {
    "request_call": frozenset({"not_entered"}),
    "http_status": frozenset({"not_entered"}),
    "sdk_response_parse": frozenset({"not_entered", "failed_after_http"}),
    "provider_contract": frozenset({"succeeded"}),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash_or_none(path: Path) -> str | None:
    return _sha256(path) if path.is_file() else None


def _policy_boundary_matrix(value: Mapping[str, Any]) -> dict[str, frozenset[str]]:
    raw = value.get("failure_code_allowlist", {}).get("non_assessable_by_phase", {})
    return {
        phase: frozenset(str(item) for item in raw.get(phase, ()))
        for phase in PROVIDER_BOUNDARY_PHASES
    }


def _policy_boot_source_paths(value: Mapping[str, Any]) -> tuple[str, ...]:
    paths = tuple(
        str(item)
        for item in value.get("source_seal", {}).get("boot_source_paths", ())
    )
    if not paths or len(paths) != len(set(paths)):
        raise RuntimeError("v0.4.3 boot-source paths are missing or duplicated")
    required = {
        Path(__file__).name,
        "openai_response_boundary_v0_4_3.py",
        LOCK_PATH.name,
        PREDECESSOR_RUNNER_PATH.name,
        str(R01_SMOKE_MANIFEST_PATH.relative_to(ROOT)),
        str(R01_FULL_MANIFEST_PATH.relative_to(ROOT)),
    }
    if not required <= set(paths):
        raise RuntimeError("v0.4.3 source seal omits an implementation or r01 artifact")
    return paths


def _validate_policy(value: Mapping[str, Any]) -> None:
    if value.get("schema_version") != POLICY_SCHEMA_VERSION:
        raise RuntimeError("v0.4.3 policy schema drifted")
    if (
        value.get("status") != "PREREGISTERED_PROTOCOL"
        or value.get("promotion_eligible") is not False
    ):
        raise RuntimeError(
            "v0.4.3 policy must remain non-promotional PREREGISTERED_PROTOCOL"
        )

    runtime = value.get("runtime", {})
    expected_runtime = {
        "api": "responses.parse_via_with_raw_response",
        "model": "gpt-5.6-sol",
        "reasoning_effort": "low",
        "service_tier": "default",
        "sdk_retries": 0,
        "timeout_seconds": 60,
        "store": False,
        "previous_response_id": False,
        "truncation": "disabled",
    }
    if any(runtime.get(key) != expected for key, expected in expected_runtime.items()):
        raise RuntimeError("v0.4.3 provider runtime contract drifted")

    policy_matrix = _policy_boundary_matrix(value)
    adapter_matrix = {
        phase: frozenset(BOUNDARY_REASON_CODES_BY_PHASE[phase])
        for phase in PROVIDER_BOUNDARY_PHASES
    }
    if policy_matrix != adapter_matrix:
        detail = {
            phase: {
                "policy_only": sorted(policy_matrix[phase] - adapter_matrix[phase]),
                "adapter_only": sorted(adapter_matrix[phase] - policy_matrix[phase]),
            }
            for phase in PROVIDER_BOUNDARY_PHASES
            if policy_matrix[phase] != adapter_matrix[phase]
        }
        raise RuntimeError(
            "provider phase/reason-code drift; canonicalize exactly: "
            + canonical_json(detail)
        )
    local = value.get("failure_code_allowlist", {}).get(
        "assessed_strict_local_public_card_validation", ()
    )
    if tuple(sorted(str(item) for item in local)) != LOCAL_CONTRACT_REASON_CODES:
        raise RuntimeError("the inherited thirteen local validator codes drifted")
    phases = tuple(value.get("observation_boundary", {}).get("phases", ()))
    if phases[:4] != PROVIDER_BOUNDARY_PHASES:
        raise RuntimeError("policy observation-boundary phase order drifted")

    receipt = value.get("receipt_contract", {})
    if (
        receipt.get("cardinality")
        != "exactly_one_terminal_receipt_per_attempted_client_call"
        or receipt.get("attempt_semantics")
        != "attempt_equals_one_and_retry_count_equals_zero"
    ):
        raise RuntimeError("receipt cardinality or retry contract drifted")
    sequence = value.get("execution_sequence", {})
    smoke = sequence.get("contract_smoke", {})
    full = sequence.get("full_block", {})
    if (
        tuple(smoke.get("case_ids", ()))
        != ("unit_reinterpretation", "invalidated_sensor_fallback")
        or smoke.get("trials") != 1
        or smoke.get("nominal_api_calls") != 28
        or full.get("cases") != LOCKED_CASE_COUNT
        or full.get("trials") != LOCKED_TRIALS
        or full.get("nominal_api_calls")
        != LOCKED_CASE_COUNT * LOCKED_TRIALS * LOCKED_CALLS_PER_CASE_TRIAL
    ):
        raise RuntimeError("v0.4.3 exact execution sequence drifted")
    expected_paths = {
        "contract_smoke_working": str(DEFAULT_SMOKE_OUTPUT.relative_to(ROOT)),
        "full_working": str(DEFAULT_DEV_OUTPUT.relative_to(ROOT)),
        "contract_smoke_canonical": str(CANONICAL_SMOKE_OUTPUT.relative_to(ROOT)),
        "full_canonical": str(CANONICAL_DEV_OUTPUT.relative_to(ROOT)),
    }
    if value.get("output_paths") != expected_paths:
        raise RuntimeError("v0.4.3 output-path lock drifted")

    predecessor = value.get("predecessor", {})
    preregistration_policy = ROOT / str(
        predecessor.get("r01_preregistration_policy", "")
    )
    if not preregistration_policy.is_file():
        raise RuntimeError("frozen r01 preregistration policy is missing")
    expected_predecessor = {
        "r01_preregistration_policy_sha256": _sha256(preregistration_policy),
        "r01_contract_smoke_manifest_sha256": _sha256(R01_SMOKE_MANIFEST_PATH),
        "r01_full_manifest_sha256": _sha256(R01_FULL_MANIFEST_PATH),
    }
    if any(
        predecessor.get(key) != expected for key, expected in expected_predecessor.items()
    ):
        raise RuntimeError("v0.4.3 frozen r01 predecessor pin drifted")
    _policy_boot_source_paths(value)


def _read_policy(*, allow_missing: bool = False) -> dict[str, Any] | None:
    if not LOCK_PATH.is_file():
        if allow_missing:
            return None
        raise FileNotFoundError("v0.4.3 live execution requires its policy lock")
    value = v041._load_json(LOCK_PATH)
    _validate_policy(value)
    return value


_BOOT_POLICY = _read_policy(allow_missing=True)
SOURCE_FILES = _policy_boot_source_paths(_BOOT_POLICY) if _BOOT_POLICY is not None else ()


def _source_snapshot(
    paths: Sequence[str] | None = None,
    *,
    allow_missing_policy: bool = False,
) -> dict[str, str | None]:
    selected = tuple(SOURCE_FILES if paths is None else paths)
    snapshot: dict[str, str | None] = {}
    for name in selected:
        path = ROOT / name
        if not path.is_file():
            if allow_missing_policy and path == LOCK_PATH:
                snapshot[name] = None
                continue
            raise RuntimeError(f"v0.4.3 sealed source is missing: {name}")
        snapshot[name] = _sha256(path)
    return snapshot


BOOT_SOURCE_SNAPSHOT = _source_snapshot(allow_missing_policy=True)


def _assert_source_snapshot(
    expected: Mapping[str, str | None],
    *,
    allow_missing_policy: bool = False,
) -> None:
    policy = _read_policy(allow_missing=allow_missing_policy)
    if policy is None:
        if expected:
            raise RuntimeError("source snapshot exists without a policy")
        return
    paths = _policy_boot_source_paths(policy)
    if tuple(expected) != paths:
        raise RuntimeError("source snapshot keys differ from policy boot_source_paths")
    if dict(expected) != _source_snapshot(paths):
        raise RuntimeError("v0.4.3 source graph changed during execution")


def _load_lock(*, allow_missing_policy: bool = False) -> dict[str, Any]:
    policy = _read_policy(allow_missing=allow_missing_policy)
    value = copy.deepcopy(v042._load_lock())
    value["v0_4_3_policy"] = policy
    if policy is not None:
        value["schema_version"] = policy["schema_version"]
        value["protocol_id"] = policy["protocol_id"]
        value["claim_boundary"] = [
            *value["claim_boundary"],
            *policy.get("claim_boundary", ()),
        ]
    return value


ProviderBoundaryError = OpenAIProviderBoundaryError

RECEIPT_AUDIT_REASON_CODES = frozenset(
    {
        "receipt_request_fingerprint_mismatch",
        "receipt_missing",
        "receipt_duplicate",
        "receipt_field_violation",
        "boot_source_snapshot_mismatch",
        "artifact_hash_mismatch",
    }
)


class RunnerAuditError(RuntimeError):
    category = "receipt_audit_error"
    phase = "receipt_audit"

    def __init__(self, reason_code: str) -> None:
        if reason_code not in RECEIPT_AUDIT_REASON_CODES:
            raise AssertionError("unknown v0.4.3 receipt-audit reason code")
        super().__init__(reason_code)
        self.reason_code = reason_code


def _failure_category(error: BaseException) -> str:
    if isinstance(error, OpenAIProviderBoundaryError):
        return error.category
    if isinstance(error, OpenAIBoundaryCapabilityError):
        return error.category
    if isinstance(error, RunnerAuditError):
        return error.category
    return v042._failure_category(error)


def _failure_reason_code(error: BaseException) -> str:
    if isinstance(
        error,
        (OpenAIProviderBoundaryError, OpenAIBoundaryCapabilityError, RunnerAuditError),
    ):
        return error.reason_code
    return v042._failure_reason_code(error)


def _run_one_arm(
    *,
    arm: str,
    case: v041.CaseSpec,
    context: v041.FixedRevisionEnvelope,
    provider: Any,
    configured_ceiling: int,
) -> dict[str, Any]:
    audit_start = len(provider.audit_receipts)
    progress: dict[str, list[Any]] = {"cards": [], "call_records": []}
    try:
        if arm in ONE_SHOT_ARMS:
            final_card = v041._execute_one_shot(
                arm=arm,
                case=case,
                context=context,
                provider=provider,
                progress=progress,
            )
        elif arm in STAGED_ARMS:
            final_card = v041._execute_staged(
                arm=arm,
                case=case,
                context=context,
                provider=provider,
                progress=progress,
            )
        else:
            raise ValueError("unknown aperture-control arm")
    except Exception as error:
        receipts = v041._arm_receipts(provider, audit_start)
        terminal_local = isinstance(error, v042.LocalContractViolation)
        boundary = isinstance(error, OpenAIProviderBoundaryError)
        return {
            "arm": arm,
            "status": "failed",
            "primary_endpoint_assessed": terminal_local,
            "terminal_outcome": (
                "terminal_local_contract_rejection"
                if terminal_local
                else "provider_boundary_failure"
                if boundary
                else "incomplete_error"
            ),
            "failure_category": _failure_category(error),
            "failure_reason_code": _failure_reason_code(error),
            "failure_phase": error.phase if boundary else None,
            "failure_sequence_offset": len(progress["call_records"]),
            "failure_request_fingerprint": (
                error.request_fingerprint
                if terminal_local
                else error.receipt.request_fingerprint
                if boundary
                else None
            ),
            "configured_output_token_ceiling": configured_ceiling,
            "expected_api_calls": v041._expected_calls(arm, case),
            "final_card": None,
            "cards": progress["cards"],
            "call_records": progress["call_records"],
            "receipts": receipts,
            "accounting": v041._accounting(receipts),
        }
    receipts = v041._arm_receipts(provider, audit_start)
    return {
        "arm": arm,
        "status": "completed",
        "primary_endpoint_assessed": True,
        "terminal_outcome": "accepted_output",
        "failure_category": None,
        "failure_reason_code": None,
        "failure_phase": None,
        "failure_sequence_offset": None,
        "failure_request_fingerprint": None,
        "configured_output_token_ceiling": configured_ceiling,
        "expected_api_calls": v041._expected_calls(arm, case),
        "final_card": final_card.to_dict(),
        "cards": progress["cards"],
        "call_records": progress["call_records"],
        "receipts": receipts,
        "accounting": v041._accounting(receipts),
    }


# The frozen executor resolves this symbol from v0.4.1 module globals.
v041._run_one_arm = _run_one_arm


def execute_suite(**kwargs: Any) -> dict[str, Any]:
    result = v042.execute_suite(**kwargs)
    result["schema_version"] = SCHEMA_VERSION
    return result


grade_executions = v042.grade_executions
summarize_runs = v042.summarize_runs


def _is_sha256(value: Any) -> bool:
    text = str(value)
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def _validate_boundary_receipt_fields(receipt: Mapping[str, Any]) -> None:
    required_top = {
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
    if set(receipt) != required_top:
        raise RuntimeError("provider receipt top-level fields drifted")
    if receipt["provider"] != "openai_responses":
        raise RuntimeError("provider receipt identity drifted")
    if receipt["requested_model"] != "gpt-5.6-sol":
        raise RuntimeError("provider receipt requested-model drifted")
    if receipt["logical_calls"] != 1 or receipt["api_calls"] != 1:
        raise RuntimeError("provider receipt call cardinality drifted")
    if not _is_sha256(receipt["request_fingerprint"]) or not _is_sha256(
        receipt["prompt_fingerprint"]
    ):
        raise RuntimeError("provider receipt request or prompt fingerprint drifted")

    metadata = receipt["metadata"]
    if not isinstance(metadata, Mapping) or set(metadata) != RECEIPT_METADATA_FIELDS:
        raise RuntimeError("provider receipt metadata fields drifted")
    if metadata["receipt_schema_version"] != RECEIPT_SCHEMA_VERSION:
        raise RuntimeError("provider receipt schema drifted")
    if (
        metadata["sdk_version"] != provider_boundary.EXPECTED_OPENAI_SDK_VERSION
        or metadata["pydantic_version"]
        != provider_boundary.EXPECTED_PYDANTIC_VERSION
        or metadata["reasoning_effort"] != "low"
    ):
        raise RuntimeError("provider receipt pinned runtime drifted")
    if (
        not isinstance(metadata["max_output_tokens"], int)
        or metadata["max_output_tokens"] <= 0
    ):
        raise RuntimeError("provider receipt output-token cap is invalid")
    if metadata["attempt"] != 1 or metadata["retry_count"] != 0:
        raise RuntimeError("provider retry semantics drifted")
    if metadata["api_call_count_semantics"] != "attempted_client_call":
        raise RuntimeError("provider receipt call semantics drifted")
    if (
        metadata["store"] is not False
        or metadata["previous_response_id"] is not False
        or metadata["truncation"] != "disabled"
    ):
        raise RuntimeError("provider stateless request contract drifted")
    for name in (
        "client_request_id_sha256",
        "response_schema_fingerprint",
        "semantic_protocol_fingerprint",
    ):
        if not _is_sha256(metadata[name]):
            raise RuntimeError(f"provider receipt {name} drifted")
    for name in (
        "response_id_sha256",
        "server_request_id_sha256",
        "provider_body_sha256",
    ):
        if metadata[name] is not None and not _is_sha256(metadata[name]):
            raise RuntimeError(f"provider receipt conditional hash drifted: {name}")
    if (metadata["provider_body_sha256"] is None) != (
        metadata["provider_body_byte_count"] is None
    ):
        raise RuntimeError("provider body digest and byte count were separated")
    if metadata["provider_body_byte_count"] is not None and int(
        metadata["provider_body_byte_count"]
    ) < 0:
        raise RuntimeError("provider body byte count is negative")

    phase = metadata["failure_phase"]
    reason = metadata["failure_reason_code"]
    outcome = metadata["attempt_outcome"]
    parse_boundary = metadata["parse_boundary"]
    if outcome == "completed":
        if phase is not None or reason is not None or metadata["failure_type"] is not None:
            raise RuntimeError("completed receipt carries a failure classification")
        if parse_boundary != "succeeded" or metadata["http_observed"] is not True:
            raise RuntimeError("completed receipt did not cross both SDK boundaries")
        if (
            receipt["returned_model"] != "gpt-5.6-sol"
            or metadata["service_tier"] != "default"
            or not isinstance(metadata["http_status_code"], int)
            or not 200 <= metadata["http_status_code"] <= 299
        ):
            raise RuntimeError("completed receipt response contract drifted")
        if receipt["usage"].get("exact_provider_tokens") is not True:
            raise RuntimeError("completed receipt lacks exact provider usage")
        return

    if phase not in PROVIDER_BOUNDARY_PHASES:
        raise RuntimeError("receipt contains an unknown boundary phase")
    if reason not in BOUNDARY_REASON_CODES_BY_PHASE[phase]:
        raise RuntimeError("receipt contains a phase-incompatible boundary reason")
    if metadata["failure_type"] != reason:
        raise RuntimeError("receipt failure alias differs from its stable reason code")
    if outcome != OUTCOME_BY_PHASE[phase]:
        raise RuntimeError("receipt attempt_outcome is incompatible with its phase")
    if parse_boundary not in PARSE_BOUNDARY_BY_PHASE[phase]:
        raise RuntimeError("receipt parse boundary is incompatible with its phase")
    if phase == "request_call" and (
        metadata["http_observed"] is not False
        or metadata["http_status_code"] is not None
    ):
        raise RuntimeError("pre-HTTP request failure claims an HTTP observation")
    if phase == "http_status" and (
        metadata["http_observed"] is not True
        or not isinstance(metadata["http_status_code"], int)
    ):
        raise RuntimeError("HTTP failure lacks its numeric observed status")
    if phase == "http_status":
        status = metadata["http_status_code"]
        expected_statuses: dict[str, set[int]] = {
            "authentication": {401},
            "permission_denied": {403},
            "not_found": {404},
            "bad_request": {400},
            "conflict": {409},
            "unprocessable_entity": {422},
            "insufficient_quota": {429},
            "rate_limit": {429},
            "unknown429": {429},
        }
        if reason in expected_statuses and status not in expected_statuses[reason]:
            raise RuntimeError("HTTP reason code is incompatible with its status")
        if reason == "server_error" and not 500 <= status <= 599:
            raise RuntimeError("server-error reason lacks a 5xx status")
        known_statuses = set().union(*expected_statuses.values()) | set(range(500, 600))
        if reason == "http_other" and status in known_statuses:
            raise RuntimeError("http_other captured an explicitly classified status")
    if phase == "sdk_response_parse" and parse_boundary == "failed_after_http" and (
        metadata["http_observed"] is not True
    ):
        raise RuntimeError("post-HTTP parse failure lost its HTTP observation")
    if phase in {"sdk_response_parse", "provider_contract"} and metadata[
        "http_observed"
    ] is True:
        status = metadata["http_status_code"]
        if not isinstance(status, int) or not 200 <= status <= 299:
            raise RuntimeError("post-HTTP boundary failure lacks a successful status")
    if phase == "provider_contract":
        if metadata["http_observed"] is not True:
            raise RuntimeError("provider-contract failure lost its HTTP observation")
        if receipt["returned_model"] not in {None, "gpt-5.6-sol"}:
            raise RuntimeError("provider-contract receipt returned-model drifted")
    if phase in {"request_call", "http_status", "sdk_response_parse"} and receipt[
        "usage"
    ].get("exact_provider_tokens") is not False:
        raise RuntimeError("pre-contract failure claims exact provider usage")


def _validate_boundary_receipt(receipt: Mapping[str, Any]) -> None:
    try:
        _validate_boundary_receipt_fields(receipt)
    except RunnerAuditError:
        raise
    except (KeyError, TypeError, ValueError, RuntimeError):
        raise RunnerAuditError("receipt_field_violation") from None


def _validate_provider_boundary_payload(payload: Mapping[str, Any]) -> bool:
    for receipt in payload["receipts"]:
        _validate_boundary_receipt(receipt)
    if payload["terminal_outcome"] != "provider_boundary_failure":
        return False
    if (
        payload.get("primary_endpoint_assessed") is not False
        or payload.get("failure_category") != "provider_boundary_error"
        or payload.get("final_card") is not None
    ):
        raise RuntimeError("provider-boundary endpoint policy drifted")
    phase = payload.get("failure_phase")
    reason = payload.get("failure_reason_code")
    if phase not in PROVIDER_BOUNDARY_PHASES or reason not in (
        BOUNDARY_REASON_CODES_BY_PHASE[phase]
    ):
        raise RuntimeError("provider-boundary payload phase/code drifted")
    receipts = payload["receipts"]
    records = payload["call_records"]
    if not receipts or len(receipts) < len(records) + 1:
        raise RunnerAuditError("receipt_missing")
    if len(receipts) > len(records) + 1:
        raise RunnerAuditError("receipt_duplicate")
    if int(payload.get("failure_sequence_offset", -1)) != len(records):
        raise RuntimeError("provider failure sequence offset drifted")
    final_receipt = receipts[-1]
    metadata = final_receipt["metadata"]
    if (
        metadata["failure_phase"] != phase
        or metadata["failure_reason_code"] != reason
        or payload.get("failure_request_fingerprint")
        != final_receipt["request_fingerprint"]
    ):
        raise RuntimeError("provider failure payload and final receipt disagree")
    return True


def _validate_unique_receipt_ids(receipts: Sequence[Mapping[str, Any]]) -> None:
    observed: set[str] = set()
    for receipt in receipts:
        client_id = str(receipt["metadata"]["client_request_id_sha256"])
        if client_id in observed:
            raise RunnerAuditError("receipt_duplicate")
        observed.add(client_id)


def _v042_receipt_compatibility_projection(
    result: Mapping[str, Any],
    audit_receipts_by_arm: Mapping[str, Sequence[Mapping[str, Any]]],
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    """Project only attempt-outcome labels for frozen v0.4.2 audit reuse.

    Exact v0.4.3 validation runs first.  The returned copies are never persisted;
    they exist solely because the frozen validator predates the two new outcome
    labels while all request, trace, receipt, and accounting geometry is shared.
    """

    projected_result = copy.deepcopy(result)
    projected_audit = copy.deepcopy(dict(audit_receipts_by_arm))

    def project(receipt: dict[str, Any]) -> None:
        outcome = receipt["metadata"]["attempt_outcome"]
        if outcome == "http_status_error":
            receipt["metadata"]["attempt_outcome"] = "transport_error"
        elif outcome == "sdk_parse_error":
            receipt["metadata"]["attempt_outcome"] = "contract_error"

    for run in projected_result["runs"]:
        for arm in ARMS:
            for receipt in run["arms"][arm]["receipts"]:
                project(receipt)
            for record in run["arms"][arm]["call_records"]:
                if isinstance(record.get("receipt"), dict):
                    project(record["receipt"])
    for arm in ARMS:
        for receipt in projected_audit[arm]:
            project(receipt)
    return projected_result, projected_audit


def validate_live_receipts(
    result: Mapping[str, Any],
    lock: Mapping[str, Any],
    *,
    audit_receipts_by_arm: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    if set(audit_receipts_by_arm) != set(ARMS):
        raise RuntimeError("audit receipt map must contain exactly the four frozen arms")
    all_audit_receipts: list[Mapping[str, Any]] = []
    for arm in ARMS:
        stored = [
            receipt
            for run in result["runs"]
            for receipt in run["arms"][arm]["receipts"]
        ]
        if canonical_json(stored) != canonical_json(audit_receipts_by_arm[arm]):
            raise RunnerAuditError("receipt_missing")
        for receipt in audit_receipts_by_arm[arm]:
            _validate_boundary_receipt(receipt)
            all_audit_receipts.append(receipt)
    _validate_unique_receipt_ids(all_audit_receipts)

    boundary_failures = 0
    unclassified_failures = 0
    by_phase = {phase: 0 for phase in PROVIDER_BOUNDARY_PHASES}
    by_reason: dict[str, int] = {
        reason: 0 for reason in PROVIDER_BOUNDARY_REASON_CODES
    }
    for run in result["runs"]:
        for arm in ARMS:
            payload = run["arms"][arm]
            if _validate_provider_boundary_payload(payload):
                boundary_failures += 1
                phase = str(payload["failure_phase"])
                reason = str(payload["failure_reason_code"])
                by_phase[phase] += 1
                by_reason[reason] += 1
            elif payload["terminal_outcome"] not in {
                "accepted_output",
                "terminal_local_contract_rejection",
            }:
                unclassified_failures += 1

    serialized = canonical_json(audit_receipts_by_arm).casefold()
    for forbidden in (
        "authorization",
        "openai_api_key",
        "bearer ",
        "raw_exception_message",
        "raw_response_body",
        "private_leak_sentinel",
    ):
        if forbidden in serialized:
            raise RuntimeError("forbidden provider or credential material entered receipts")

    projected_result, projected_audit = _v042_receipt_compatibility_projection(
        result, audit_receipts_by_arm
    )
    try:
        check = v042.validate_live_receipts(
            projected_result,
            lock,
            audit_receipts_by_arm=projected_audit,
        )
    except RuntimeError:
        raise RunnerAuditError("receipt_field_violation") from None
    check.update(
        {
            "provider_boundary_receipts_validated": True,
            "provider_boundary_failures": boundary_failures,
            "provider_boundary_failures_by_phase": dict(by_phase),
            "provider_boundary_failures_by_reason": dict(sorted(by_reason.items())),
            "unclassified_non_assessable_failures": unclassified_failures,
            "privacy_audit_validated": True,
        }
    )
    return check


def _exact_protocol_coverage(
    result: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
) -> bool:
    try:
        expected, expected_ids, expected_trials = _expected_schedule(result, policy)
        actual, actual_sha256 = _schedule_record(result)
        expected_sha256 = hashlib.sha256(
            canonical_json(expected).encode("utf-8")
        ).hexdigest()
        sequence_name = (
            "contract_smoke" if result["mode"] == MODE_SMOKE else "full_block"
        )
        policy_sha256 = str(
            policy["execution_sequence"][sequence_name][
                "run_and_arm_order_sha256"
            ]
        )
    except (KeyError, TypeError, ValueError, RuntimeError):
        return False
    return bool(
        tuple(result["case_ids"]) == expected_ids
        and int(result["case_count"]) == len(expected_ids)
        and int(result["trials"]) == expected_trials
        and len(result["runs"]) == len(expected)
        and canonical_json(actual) == canonical_json(expected)
        and actual_sha256 == expected_sha256 == policy_sha256
    )


def _derive_gate_flags(
    *,
    exact_coverage: bool,
    receipt_validation: Mapping[str, Any],
    all_primary_endpoints_assessed: bool,
    full_mode: bool,
    integrity_components: Mapping[str, bool],
) -> dict[str, bool]:
    required_components = {
        "preregistration_audit_ready",
        "source_snapshot_audit_ready",
        "receipt_audit_ready",
        "privacy_audit_ready",
        "artifact_audit_ready",
    }
    if set(integrity_components) != required_components:
        raise RuntimeError("diagnostic-integrity component set drifted")
    diagnostic_integrity_ready = bool(
        exact_coverage
        and all(bool(value) for value in integrity_components.values())
        and receipt_validation.get("validated") is True
        and receipt_validation.get("terminal_policy_validated") is True
        and receipt_validation.get("provider_boundary_receipts_validated") is True
        and int(receipt_validation.get("unclassified_non_assessable_failures", 0))
        == 0
    )
    zero_non_assessable = bool(
        int(receipt_validation.get("provider_boundary_failures", 0)) == 0
        and int(receipt_validation.get("non_assessable_failures", 0)) == 0
    )
    locked_decision_ready = bool(
        diagnostic_integrity_ready
        and full_mode
        and all_primary_endpoints_assessed
        and zero_non_assessable
    )
    full_run_launch_ready = bool(
        diagnostic_integrity_ready
        and not full_mode
        and all_primary_endpoints_assessed
        and zero_non_assessable
    )
    return {
        "diagnostic_integrity_ready": diagnostic_integrity_ready,
        "locked_decision_ready": locked_decision_ready,
        "full_run_launch_ready": full_run_launch_ready,
    }


def _arm_rows(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = v042._arm_rows(result)
    payloads = [run["arms"][arm] for run in result["runs"] for arm in ARMS]
    if len(rows) != len(payloads):
        raise AssertionError("v0.4.3 arm-row geometry drifted")
    for row, payload in zip(rows, payloads, strict=True):
        row.update(
            {
                "failure_phase": payload.get("failure_phase"),
                "provider_boundary_failure": (
                    payload["terminal_outcome"] == "provider_boundary_failure"
                ),
            }
        )
    return rows


def _report_markdown(result: Mapping[str, Any]) -> str:
    summary = result["summary"]
    receipt = summary["live_receipt_validation"]
    lines = [
        "# EBRT v0.4.3 provider-boundary diagnostics — DEV report",
        "",
        f"Mode: `{result['mode']}`  ",
        f"Runs: `{summary['runs']}`  ",
        f"Diagnostic integrity ready: `{str(bool(summary['diagnostic_integrity_ready'])).lower()}`  ",
        f"Locked decision ready: `{str(bool(summary['locked_decision_ready'])).lower()}`  ",
        f"Full-run launch ready: `{str(bool(receipt['full_run_launch_ready'])).lower()}`  ",
        f"Provider-boundary failures: `{receipt['provider_boundary_failures']}`  ",
        f"Non-assessable endpoints: `{receipt['non_assessable_failures']}`",
        "",
        "Provider/SDK failures are diagnostically classified but remain",
        "non-assessable. Only inherited local public-card validator rejections",
        "are assessed strict failures.",
        "",
        "| Arm | Strict success / assessed | Accepted | Local rejection | Provider boundary | Non-assessable | API calls |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm in ARMS:
        item = summary["arm_summary"][arm]
        provider_failures = sum(
            run["arms"][arm]["terminal_outcome"] == "provider_boundary_failure"
            for run in result["runs"]
        )
        lines.append(
            "| {arm} | {success}/{assessed} | {accepted} | {local} | {provider} | {missing} | {calls} |".format(
                arm=arm,
                success=item["machine_successes"],
                assessed=item["primary_endpoint_assessed_outputs"],
                accepted=item["completed_outputs"],
                local=item["terminal_local_contract_rejections"],
                provider=provider_failures,
                missing=item["non_assessable_outputs"],
                calls=item["api_calls"],
            )
        )
    lines.extend(["", "## Provider-boundary failures", ""])
    if receipt["provider_boundary_failures_by_reason"]:
        for reason, count in receipt["provider_boundary_failures_by_reason"].items():
            lines.append(f"- `{reason}`: {count}")
    else:
        lines.append("None.")
    lines.extend(
        [
            "",
            "## Claim boundary",
            "",
            "This is contaminated DEV instrumentation, not a holdout, promotion",
            "result, general reasoning-improvement claim, or private-state read.",
            "Diagnostic integrity does not make incomplete endpoints decision-ready.",
            "",
        ]
    )
    return "\n".join(lines)


def _git(*args: str, text: bool = True) -> subprocess.CompletedProcess[Any]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=text,
    )


def _allowed_status_path(line: str, allowed_prefixes: Sequence[str]) -> bool:
    if len(line) < 4:
        return False
    path = line[3:].strip().strip('"')
    if " -> " in path:
        path = path.split(" -> ", 1)[1]
    return any(path == prefix or path.startswith(prefix.rstrip("/") + "/") for prefix in allowed_prefixes)


def _validate_preregistration_state(
    *,
    policy: Mapping[str, Any],
    source_snapshot: Mapping[str, str | None],
    output: Path,
    mode: str,
    contract_smoke_manifest: Path | None,
) -> dict[str, Any]:
    expected_output = DEFAULT_SMOKE_OUTPUT if mode == MODE_SMOKE else DEFAULT_DEV_OUTPUT
    expected_canonical = (
        CANONICAL_SMOKE_OUTPUT if mode == MODE_SMOKE else CANONICAL_DEV_OUTPUT
    )
    if output.resolve() != expected_output.resolve():
        raise RuntimeError("live output must equal the policy-locked working path")
    if output.exists() or expected_canonical.exists():
        raise FileExistsError("policy-locked working or canonical output path already exists")

    allowed_prefixes: list[str] = []
    if mode == MODE_DEV and contract_smoke_manifest is not None:
        try:
            allowed_prefixes.append(
                str(
                    contract_smoke_manifest.resolve().parent.relative_to(
                        ROOT.resolve()
                    )
                )
            )
        except ValueError as error:
            raise RuntimeError("smoke bundle must remain inside the repository") from error
    status_lines = [
        line
        for line in _git("status", "--porcelain", "--untracked-files=all").stdout.splitlines()
        if line and not _allowed_status_path(line, allowed_prefixes)
    ]
    if status_lines:
        raise RuntimeError("v0.4.3 live preflight requires a clean preregistered worktree")

    head = _git("rev-parse", "HEAD").stdout.strip()
    tree = _git("rev-parse", "HEAD^{tree}").stdout.strip()
    try:
        upstream = _git(
            "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"
        ).stdout.strip()
        upstream_head = _git("rev-parse", "@{upstream}").stdout.strip()
    except subprocess.CalledProcessError as error:
        raise RuntimeError("preregistration branch has no pushed upstream") from error
    if head != upstream_head:
        raise RuntimeError("preregistration HEAD is not exactly the pushed upstream HEAD")

    policy_paths = _policy_boot_source_paths(policy)
    if tuple(source_snapshot) != policy_paths:
        raise RuntimeError("runtime source snapshot does not match policy path order")
    for name in policy_paths:
        try:
            committed = _git("show", f"{head}:{name}", text=False).stdout
        except subprocess.CalledProcessError as error:
            raise RuntimeError(f"sealed source is not committed at preregistration HEAD: {name}") from error
        if hashlib.sha256(committed).hexdigest() != source_snapshot[name]:
            raise RuntimeError(f"working source differs from preregistration HEAD: {name}")
    return {
        "preregistration_commit": head,
        "preregistration_tree": tree,
        "upstream": upstream,
        "source_snapshot_matches_preregistration_commit": True,
        "worktree_clean_except_verified_smoke_bundle": True,
        "target_output_paths_absent": True,
    }


def _primary_execution_classification(
    *, mode: str, diagnostic_ready: bool, locked_ready: bool, full_launch_ready: bool
) -> str | None:
    if mode == MODE_SMOKE:
        return None if full_launch_ready else "smoke_gate_failed_full_not_launched"
    if mode != MODE_DEV:
        raise RuntimeError("primary execution classification received an unknown mode")
    if not diagnostic_ready:
        return "full_executed_diagnostic_integrity_failed"
    if locked_ready:
        return "full_executed_decision_ready"
    return "full_executed_diagnostic_integrity_ready_decision_not_ready"


def _schedule_record(result: Mapping[str, Any]) -> tuple[list[dict[str, Any]], str]:
    schedule = [
        {
            "run_id": run["run_id"],
            "trial_index": int(run["trial_index"]),
            "run_position": int(run["run_position"]),
            "original_case_index": int(run["original_case_index"]),
            "case_id": run["case_id"],
            "arm_order": list(run["arm_order"]),
        }
        for run in result["runs"]
    ]
    digest = hashlib.sha256(canonical_json(schedule).encode("utf-8")).hexdigest()
    return schedule, digest


def _expected_schedule(
    result: Mapping[str, Any], policy: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], tuple[str, ...], int]:
    all_cases, _ = v041._load_suite()
    if result["mode"] == MODE_SMOKE:
        preset = policy["execution_sequence"]["contract_smoke"]
        expected_ids = tuple(str(item) for item in preset["case_ids"])
        expected_trials = int(preset["trials"])
        selected = v041._select_cases(all_cases, expected_ids)
    elif result["mode"] == MODE_DEV:
        selected = list(all_cases)
        expected_ids = tuple(case.case_id for case in selected)
        expected_trials = LOCKED_TRIALS
    else:
        raise RuntimeError("unknown v0.4.3 mode for deterministic schedule")
    expected: list[dict[str, Any]] = []
    for trial_index in range(expected_trials):
        for run_position, (original_case_index, case) in enumerate(
            v041._rotated_cases(selected, trial_index)
        ):
            expected.append(
                {
                    "run_id": f"{result['mode']}:{trial_index}:{case.case_id}",
                    "trial_index": trial_index,
                    "run_position": run_position,
                    "original_case_index": original_case_index,
                    "case_id": case.case_id,
                    "arm_order": list(
                        v041._williams_arm_order(
                            trial_index, original_case_index
                        )
                    ),
                }
            )
    return expected, expected_ids, expected_trials


def _execution_diagnostics(
    result: Mapping[str, Any],
    *,
    receipt_validation: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    receipts = [
        receipt
        for run in result["runs"]
        for arm in ARMS
        for receipt in run["arms"][arm]["receipts"]
    ]
    schedule, schedule_sha256 = _schedule_record(result)
    expected_schedule, _, _ = _expected_schedule(result, policy)
    expected_schedule_sha256 = hashlib.sha256(
        canonical_json(expected_schedule).encode("utf-8")
    ).hexdigest()
    local_reasons: dict[str, int] = {
        reason: 0 for reason in LOCAL_CONTRACT_REASON_CODES
    }
    per_arm: dict[str, dict[str, int]] = {}
    for arm in ARMS:
        payloads = [run["arms"][arm] for run in result["runs"]]
        for payload in payloads:
            if payload["terminal_outcome"] == "terminal_local_contract_rejection":
                reason = str(payload["failure_reason_code"])
                local_reasons[reason] += 1
        per_arm[arm] = {
            "denominator": len(payloads),
            "accepted_outputs": sum(
                payload["terminal_outcome"] == "accepted_output"
                for payload in payloads
            ),
            "local_strict_failures": sum(
                payload["terminal_outcome"]
                == "terminal_local_contract_rejection"
                for payload in payloads
            ),
            "assessed_endpoints": sum(
                bool(payload["primary_endpoint_assessed"]) for payload in payloads
            ),
            "non_assessable_endpoints": sum(
                not bool(payload["primary_endpoint_assessed"]) for payload in payloads
            ),
            "strict_machine_successes": sum(
                bool(payload.get("grade", {}).get("machine_success"))
                for payload in payloads
            ),
        }

    failed_receipts = [
        item for item in receipts if item["metadata"]["attempt_outcome"] != "completed"
    ]
    classified_failed_receipts = sum(
        item["metadata"]["failure_phase"] in PROVIDER_BOUNDARY_PHASES
        and item["metadata"]["failure_reason_code"]
        in BOUNDARY_REASON_CODES_BY_PHASE[item["metadata"]["failure_phase"]]
        for item in failed_receipts
    )
    exact_population = bool(
        result["execution_complete"]
        and all(item["usage"]["exact_provider_tokens"] is True for item in receipts)
    )
    token_fields = (
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cached_input_tokens",
        "cache_write_tokens",
        "reasoning_tokens",
    )
    exact_totals: dict[str, int | None] = {}
    for name in token_fields:
        values = [item["usage"].get(name) for item in receipts]
        exact_totals[name] = (
            sum(int(value) for value in values)
            if exact_population and all(value is not None for value in values)
            else None
        )
    exact_total_tokens_available = bool(
        exact_population and exact_totals["total_tokens"] is not None
    )
    summary = result["summary"]
    accepted_endpoint_count = sum(
        run["arms"][arm]["terminal_outcome"] == "accepted_output"
        for run in result["runs"]
        for arm in ARMS
    )
    assessed_endpoint_count = sum(
        bool(run["arms"][arm]["primary_endpoint_assessed"])
        for run in result["runs"]
        for arm in ARMS
    )
    classification = _primary_execution_classification(
        mode=str(result["mode"]),
        diagnostic_ready=bool(summary["diagnostic_integrity_ready"]),
        locked_ready=bool(summary["locked_decision_ready"]),
        full_launch_ready=bool(receipt_validation["full_run_launch_ready"]),
    )
    return {
        "mode": result["mode"],
        "case_ids": list(result["case_ids"]),
        "case_count": int(result["case_count"]),
        "trials": int(result["trials"]),
        "trial_ids": sorted({int(run["trial_index"]) for run in result["runs"]}),
        "run_count": len(result["runs"]),
        "arm_endpoint_count": len(result["runs"]) * len(ARMS),
        "scheduled_arm_endpoints": len(result["runs"]) * len(ARMS),
        "run_and_arm_order": schedule,
        "run_and_arm_order_sha256": schedule_sha256,
        "expected_run_and_arm_order_sha256": expected_schedule_sha256,
        "exact_case_trial_run_arm_coverage": _exact_protocol_coverage(
            result, policy=policy
        ),
        "exact_protocol_coverage": _exact_protocol_coverage(
            result, policy=policy
        ),
        "nominal_calls": int(receipt_validation["nominal_api_calls"]),
        "attempted_calls": int(receipt_validation["attempted_api_calls"]),
        "receipt_count": len(receipts),
        "attempted_calls_equal_receipt_count": int(
            receipt_validation["attempted_api_calls"]
        )
        == len(receipts),
        "classified_failed_receipts": classified_failed_receipts,
        "failed_receipt_count": len(failed_receipts),
        "classified_failed_receipt_count": classified_failed_receipts,
        "unclassified_failed_receipts": len(failed_receipts)
        - classified_failed_receipts,
        "classified_nonassessable_endpoint_count": int(
            receipt_validation["provider_boundary_failures"]
        ),
        "unclassified_nonassessable_failure_count": int(
            receipt_validation["unclassified_non_assessable_failures"]
        ),
        "accepted_endpoint_count": accepted_endpoint_count,
        "assessed_endpoint_count": assessed_endpoint_count,
        "http_observation_recorded_count": len(receipts),
        "http_acquired_count": sum(
            item["metadata"]["http_observed"] is True for item in receipts
        ),
        "http_observed_count": sum(
            item["metadata"]["http_observed"] is True for item in receipts
        ),
        "http_status_code_available_count": sum(
            item["metadata"]["http_status_code"] is not None for item in receipts
        ),
        "http_status_available_count": sum(
            item["metadata"]["http_status_code"] is not None for item in receipts
        ),
        "structured_parse_attempted_count": sum(
            item["metadata"]["parse_boundary"]
            in {"failed_after_http", "succeeded"}
            for item in receipts
        ),
        "structured_parse_succeeded_count": sum(
            item["metadata"]["parse_boundary"] == "succeeded"
            for item in receipts
        ),
        "structured_parse_success_count": sum(
            item["metadata"]["parse_boundary"] == "succeeded"
            for item in receipts
        ),
        "exact_usage_available_count": sum(
            item["usage"]["exact_provider_tokens"] is True for item in receipts
        ),
        "provider_failure_counts_by_phase": dict(
            receipt_validation["provider_boundary_failures_by_phase"]
        ),
        "provider_failure_counts_by_reason": dict(
            receipt_validation["provider_boundary_failures_by_reason"]
        ),
        "failure_counts_by_phase_and_allowlisted_code": {
            "provider_boundary_by_phase": dict(
                receipt_validation["provider_boundary_failures_by_phase"]
            ),
            "provider_boundary_by_reason": dict(
                receipt_validation["provider_boundary_failures_by_reason"]
            ),
            "terminal_local_by_reason": dict(sorted(local_reasons.items())),
            "unclassified_nonassessable": int(
                receipt_validation["unclassified_non_assessable_failures"]
            ),
        },
        "non_assessable_endpoint_count": int(
            receipt_validation["non_assessable_failures"]
        ),
        "terminal_local_rejection_count": int(
            receipt_validation["terminal_local_contract_rejections"]
        ),
        "terminal_local_rejection_reasons": dict(sorted(local_reasons.items())),
        "terminal_local_rejections_by_reason": dict(sorted(local_reasons.items())),
        "terminal_local_rejection_count_and_reason_codes": {
            "count": int(receipt_validation["terminal_local_contract_rejections"]),
            "by_reason": dict(sorted(local_reasons.items())),
        },
        "per_arm_endpoint_counts": per_arm,
        "per_arm_accepted_assessed_strict_counts": copy.deepcopy(per_arm),
        "assessed_four_arm_runs": sum(
            bool(run["primary_endpoint_assessed"]) for run in result["runs"]
        ),
        "all_output_completed_runs": sum(
            bool(run["all_outputs_completed"]) for run in result["runs"]
        ),
        "stable_pass_case_counts": copy.deepcopy(
            summary.get("stable_case_summary", {})
        ),
        "stable_contrast_outcomes": copy.deepcopy(
            summary.get("stable_contrast_outcomes", {})
        ),
        "revision_envelope_contrast": copy.deepcopy(
            summary.get("stable_contrast_outcomes", {}).get(
                "revision_envelope", {}
            )
        ),
        "raw_aperture_contrast": copy.deepcopy(
            summary.get("stable_contrast_outcomes", {}).get("raw_aperture", {})
        ),
        "exact_total_tokens_available": exact_total_tokens_available,
        "exact_total_tokens": exact_totals,
        "exact_total_tokens_only_when_complete": (
            exact_totals if exact_total_tokens_available else None
        ),
        "artifact_hash_map_validated": True,
        "calls_rows_equal_receipts_equal_attempted_calls": True,
        "sibling_staging_directory_fully_audited_before_atomic_publish": True,
        "comparison_available_false_for_terminal_failure_bundle": True,
        "primary_execution_classification": classification,
        "classification_pending_full_execution": bool(
            result["mode"] == MODE_SMOKE and classification is None
        ),
        "cause_conclusion_or_not_assessed": {
            "revision_envelope": summary["cause_decision"][
                "revision_envelope_conclusion"
            ],
            "raw_aperture": summary["cause_decision"][
                "raw_aperture_conclusion"
            ],
        },
    }


def _audit_written_artifacts(
    *,
    result: Mapping[str, Any],
    output: Path,
    artifact_sha256: Mapping[str, str],
    expected_receipt_count: int,
    expected_attempted_calls: int,
    fault_injection: str | None = None,
) -> None:
    for name, expected in artifact_sha256.items():
        path = output / name
        if not path.is_file() or _sha256(path) != expected:
            raise RunnerAuditError("artifact_hash_mismatch")
    reloaded = v041._load_json(output / "results.json")
    if canonical_json(reloaded) != canonical_json(result):
        raise RunnerAuditError("artifact_hash_mismatch")
    if (output / "benchmark_report.md").read_text(encoding="utf-8") != _report_markdown(
        result
    ):
        raise RunnerAuditError("artifact_hash_mismatch")
    trace_lines = [
        line
        for line in (output / "traces.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    if len(trace_lines) != len(result["runs"]):
        raise RunnerAuditError("artifact_hash_mismatch")
    try:
        reloaded_traces = [json.loads(line) for line in trace_lines]
    except (TypeError, ValueError, json.JSONDecodeError):
        raise RunnerAuditError("artifact_hash_mismatch") from None
    if canonical_json(reloaded_traces) != canonical_json(result["runs"]):
        raise RunnerAuditError("artifact_hash_mismatch")
    call_lines = [
        line
        for line in (output / "calls.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    try:
        reloaded_calls = [json.loads(line) for line in call_lines]
    except (TypeError, ValueError, json.JSONDecodeError):
        raise RunnerAuditError("artifact_hash_mismatch") from None
    if canonical_json(reloaded_calls) != canonical_json(v041._call_rows(result)):
        raise RunnerAuditError("artifact_hash_mismatch")
    if not (
        len(reloaded_calls)
        == expected_receipt_count
        == expected_attempted_calls
    ):
        raise RunnerAuditError("artifact_hash_mismatch")
    if sum(int(row["receipt"]["api_calls"]) for row in reloaded_calls) != (
        expected_attempted_calls
    ):
        raise RunnerAuditError("artifact_hash_mismatch")
    if fault_injection == "audit":
        raise RunnerAuditError("artifact_hash_mismatch")


def _write_bundle_directory(
    result: Mapping[str, Any],
    output: Path,
    *,
    source_snapshot: Mapping[str, str | None],
    preregistration: Mapping[str, Any],
    fault_injection: str | None = None,
) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite output path: {output}")
    summary = result["summary"]
    receipt = summary["live_receipt_validation"]
    policy = _read_policy()
    assert policy is not None
    diagnostic_ready = bool(summary["diagnostic_integrity_ready"])
    locked_ready = bool(summary["locked_decision_ready"])
    output.mkdir(parents=True)
    v041._write_json(output / "results.json", result)
    if fault_injection == "write":
        raise RunnerAuditError("artifact_hash_mismatch")
    v041._write_jsonl(output / "traces.jsonl", result["runs"])
    v041._write_jsonl(output / "calls.jsonl", v041._call_rows(result))
    v041._write_csv(output / "arm_rows.csv", _arm_rows(result))
    (output / "benchmark_report.md").write_text(
        _report_markdown(result), encoding="utf-8"
    )
    artifact_names = (
        "results.json",
        "traces.jsonl",
        "calls.jsonl",
        "arm_rows.csv",
        "benchmark_report.md",
    )
    execution = _execution_diagnostics(
        result,
        receipt_validation=receipt,
        policy=policy,
    )
    artifact_sha256 = {name: _sha256(output / name) for name in artifact_names}
    _audit_written_artifacts(
        result=result,
        output=output,
        artifact_sha256=artifact_sha256,
        expected_receipt_count=int(execution["receipt_count"]),
        expected_attempted_calls=int(execution["attempted_calls"]),
        fault_injection=fault_injection,
    )
    integrity_components = {
        "preregistration_audit_ready": bool(
            preregistration.get("source_snapshot_matches_preregistration_commit")
            and preregistration.get("worktree_clean_except_verified_smoke_bundle")
            and preregistration.get("target_output_paths_absent")
        ),
        "source_snapshot_audit_ready": True,
        "receipt_audit_ready": bool(
            receipt["validated"]
            and receipt["terminal_policy_validated"]
            and receipt["provider_boundary_receipts_validated"]
        ),
        "privacy_audit_ready": bool(receipt["privacy_audit_validated"]),
        "artifact_audit_ready": True,
    }
    runtime_versions = {
        "python": platform.python_version(),
        "openai": importlib.metadata.version("openai"),
        "pydantic": importlib.metadata.version("pydantic"),
    }
    predecessor_manifest_sha256s = {
        "r01_contract_smoke": _sha256(R01_SMOKE_MANIFEST_PATH),
        "r01_full": _sha256(R01_FULL_MANIFEST_PATH),
    }
    receipt_and_artifact_audit_results = {
        "receipt_audit_ready": integrity_components["receipt_audit_ready"],
        "source_snapshot_audit_ready": integrity_components[
            "source_snapshot_audit_ready"
        ],
        "preregistration_audit_ready": integrity_components[
            "preregistration_audit_ready"
        ],
        "privacy_audit_ready": integrity_components["privacy_audit_ready"],
        "artifact_hash_map_validated": True,
        "calls_rows_equal_receipts_equal_attempted_calls": True,
        "sibling_staging_directory_fully_audited_before_atomic_publish": True,
    }
    execution.update(
        {
            "preregistration_commit": preregistration.get(
                "preregistration_commit"
            ),
            "preregistration_tree": preregistration.get("preregistration_tree"),
            "policy_sha256": _sha256(LOCK_PATH),
            "boot_source_sha256_map": dict(source_snapshot),
            "predecessor_manifest_sha256s": predecessor_manifest_sha256s,
            "runtime_versions": runtime_versions,
            "receipt_and_artifact_audit_results": (
                receipt_and_artifact_audit_results
            ),
            "diagnostic_integrity_ready": diagnostic_ready,
            "locked_decision_ready": locked_ready,
            "full_launch_ready": bool(receipt["full_run_launch_ready"]),
            "comparison_available": diagnostic_ready,
            "diagnostic_comparison_available": diagnostic_ready,
            "reasoning_comparison_available": locked_ready,
            "comparison_available_false_for_terminal_failure_bundle": True,
        }
    )
    if diagnostic_ready != bool(
        execution["exact_case_trial_run_arm_coverage"]
        and execution["attempted_calls_equal_receipt_count"]
        and all(integrity_components.values())
        and execution["unclassified_failed_receipts"] == 0
        and receipt["unclassified_non_assessable_failures"] == 0
    ):
        raise RunnerAuditError("artifact_hash_mismatch")
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "status": (
            "COMPLETE_LOCKED_DEV"
            if locked_ready
            else "COMPLETE_DIAGNOSTIC_NON_DECISION"
            if diagnostic_ready
            else "INCOMPLETE"
        ),
        "success_manifest": locked_ready,
        "diagnostic_success_manifest": diagnostic_ready,
        "diagnostic_integrity_ready": diagnostic_ready,
        "locked_decision_ready": locked_ready,
        "execution_complete": bool(result["execution_complete"]),
        "all_outputs_completed": bool(result["all_outputs_completed"]),
        "promotion_eligible": False,
        "mode": result["mode"],
        **dict(preregistration),
        **integrity_components,
        "diagnostic_integrity_components": integrity_components,
        "source_sha256": dict(source_snapshot),
        "boot_source_sha256_map": dict(source_snapshot),
        "policy_sha256": _sha256(LOCK_PATH),
        "provider_adapter_sha256": _sha256(
            ROOT / "openai_response_boundary_v0_4_3.py"
        ),
        "r01_contract_smoke_manifest_sha256": _sha256(R01_SMOKE_MANIFEST_PATH),
        "r01_full_manifest_sha256": _sha256(R01_FULL_MANIFEST_PATH),
        "predecessor_manifest_sha256s": predecessor_manifest_sha256s,
        "artifact_sha256": artifact_sha256,
        "artifact_hash_audit_validated": True,
        "artifact_hash_map_validated": execution[
            "artifact_hash_map_validated"
        ],
        "fixture_sha256": _sha256(v041.FIXTURE_PATH),
        "gold_sha256": _sha256(v041.GOLD_PATH),
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "openai": importlib.metadata.version("openai"),
            "pydantic": importlib.metadata.version("pydantic"),
        },
        "runtime_versions": runtime_versions,
        "execution_record": execution,
        "comparison_record": copy.deepcopy(execution),
        "case_ids": execution["case_ids"],
        "case_count": execution["case_count"],
        "trials": execution["trials"],
        "trial_ids": execution["trial_ids"],
        "run_count": execution["run_count"],
        "arm_endpoint_count": execution["arm_endpoint_count"],
        "scheduled_arm_endpoints": execution["scheduled_arm_endpoints"],
        "run_and_arm_order_sha256": execution["run_and_arm_order_sha256"],
        "expected_run_and_arm_order_sha256": execution[
            "expected_run_and_arm_order_sha256"
        ],
        "exact_case_trial_run_arm_coverage": execution[
            "exact_case_trial_run_arm_coverage"
        ],
        "exact_protocol_coverage": execution["exact_protocol_coverage"],
        "nominal_api_calls": receipt["nominal_api_calls"],
        "attempted_api_calls": receipt["attempted_api_calls"],
        "receipt_count": execution["receipt_count"],
        "attempted_calls_equal_receipt_count": execution[
            "attempted_calls_equal_receipt_count"
        ],
        "classified_failed_receipts": execution["classified_failed_receipts"],
        "failed_receipt_count": execution["failed_receipt_count"],
        "classified_failed_receipt_count": execution[
            "classified_failed_receipt_count"
        ],
        "unclassified_failed_receipts": execution[
            "unclassified_failed_receipts"
        ],
        "classified_nonassessable_endpoint_count": execution[
            "classified_nonassessable_endpoint_count"
        ],
        "unclassified_nonassessable_failure_count": execution[
            "unclassified_nonassessable_failure_count"
        ],
        "accepted_endpoint_count": execution["accepted_endpoint_count"],
        "assessed_endpoint_count": execution["assessed_endpoint_count"],
        "http_observation_recorded_count": execution[
            "http_observation_recorded_count"
        ],
        "http_acquired_count": execution["http_acquired_count"],
        "http_observed_count": execution["http_observed_count"],
        "http_status_available_count": execution[
            "http_status_available_count"
        ],
        "http_status_code_available_count": execution[
            "http_status_code_available_count"
        ],
        "structured_parse_attempted_count": execution[
            "structured_parse_attempted_count"
        ],
        "structured_parse_succeeded_count": execution[
            "structured_parse_succeeded_count"
        ],
        "structured_parse_success_count": execution[
            "structured_parse_success_count"
        ],
        "exact_usage_available_count": execution[
            "exact_usage_available_count"
        ],
        "provider_boundary_failures": receipt["provider_boundary_failures"],
        "provider_boundary_failures_by_phase": receipt[
            "provider_boundary_failures_by_phase"
        ],
        "provider_boundary_failures_by_reason": receipt[
            "provider_boundary_failures_by_reason"
        ],
        "failure_counts_by_phase_and_allowlisted_code": execution[
            "failure_counts_by_phase_and_allowlisted_code"
        ],
        "terminal_local_contract_rejections": receipt[
            "terminal_local_contract_rejections"
        ],
        "terminal_local_rejection_reasons": execution[
            "terminal_local_rejection_reasons"
        ],
        "terminal_local_rejections_by_reason": execution[
            "terminal_local_rejections_by_reason"
        ],
        "terminal_local_rejection_count_and_reason_codes": execution[
            "terminal_local_rejection_count_and_reason_codes"
        ],
        "non_assessable_failures": receipt["non_assessable_failures"],
        "per_arm_endpoint_counts": execution["per_arm_endpoint_counts"],
        "per_arm_accepted_assessed_strict_counts": execution[
            "per_arm_accepted_assessed_strict_counts"
        ],
        "assessed_four_arm_runs": execution["assessed_four_arm_runs"],
        "all_output_completed_runs": execution["all_output_completed_runs"],
        "stable_pass_case_counts": execution["stable_pass_case_counts"],
        "stable_contrast_outcomes": execution["stable_contrast_outcomes"],
        "revision_envelope_contrast": execution[
            "revision_envelope_contrast"
        ],
        "raw_aperture_contrast": execution["raw_aperture_contrast"],
        "exact_total_tokens_available": execution[
            "exact_total_tokens_available"
        ],
        "exact_total_tokens": execution["exact_total_tokens"],
        "exact_total_tokens_only_when_complete": execution[
            "exact_total_tokens_only_when_complete"
        ],
        "full_run_launch_ready": receipt["full_run_launch_ready"],
        "full_launch_ready": execution["full_launch_ready"],
        "calls_rows_equal_receipts_equal_attempted_calls": execution[
            "calls_rows_equal_receipts_equal_attempted_calls"
        ],
        "sibling_staging_directory_fully_audited_before_atomic_publish": execution[
            "sibling_staging_directory_fully_audited_before_atomic_publish"
        ],
        "receipt_and_artifact_audit_results": execution[
            "receipt_and_artifact_audit_results"
        ],
        "comparison_available": execution["comparison_available"],
        "diagnostic_comparison_available": execution[
            "diagnostic_comparison_available"
        ],
        "reasoning_comparison_available": execution[
            "reasoning_comparison_available"
        ],
        "comparison_available_false_for_terminal_failure_bundle": execution[
            "comparison_available_false_for_terminal_failure_bundle"
        ],
        "primary_execution_classification": execution[
            "primary_execution_classification"
        ],
        "classification_pending_full_execution": execution[
            "classification_pending_full_execution"
        ],
        "launch_gate": result.get("launch_gate"),
        "cause_decision": dict(summary["cause_decision"]),
        "cause_conclusion_or_not_assessed": execution[
            "cause_conclusion_or_not_assessed"
        ],
        "claim_boundary": {
            "contaminated_dev_only": True,
            "provider_boundary_failures_non_assessable": True,
            "local_contract_rejections_strict_assessed": True,
            "diagnostic_ready_is_not_decision_ready": True,
            "general_reasoning_improvement": False,
        },
    }
    v041._write_json(output / "manifest.json", manifest)
    if canonical_json(v041._load_json(output / "manifest.json")) != canonical_json(
        manifest
    ):
        raise RunnerAuditError("artifact_hash_mismatch")
    return manifest


def write_bundle(
    result: Mapping[str, Any],
    output: Path,
    *,
    source_snapshot: Mapping[str, str | None],
    preregistration: Mapping[str, Any],
    _fault_injection: str | None = None,
) -> dict[str, Any]:
    """Audit a complete sibling stage, then atomically publish it once."""

    if _fault_injection not in {None, "write", "audit", "pre_publish"}:
        raise ValueError("unknown bundle fault injection")
    if output.exists():
        raise FileExistsError(f"refusing to overwrite output path: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage_root = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.stage-", dir=output.parent)
    )
    stage_bundle = stage_root / "bundle"
    try:
        manifest = _write_bundle_directory(
            result,
            stage_bundle,
            source_snapshot=source_snapshot,
            preregistration=preregistration,
            fault_injection=_fault_injection,
        )
        if _fault_injection == "pre_publish":
            raise RunnerAuditError("artifact_hash_mismatch")
        if output.exists():
            raise FileExistsError("final output appeared before atomic publication")
        stage_bundle.rename(output)
        stage_root.rmdir()
        return manifest
    except BaseException:
        if stage_root.exists():
            shutil.rmtree(stage_root)
        raise


def _sanitized_failure_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    metadata = value.get("metadata", {})
    safe_metadata = {
        name: metadata.get(name)
        for name in RECEIPT_METADATA_FIELDS
        if name in metadata
    }
    return {
        "provider": value.get("provider"),
        "requested_model": value.get("requested_model"),
        "returned_model": value.get("returned_model"),
        "logical_calls": value.get("logical_calls"),
        "api_calls": value.get("api_calls"),
        "latency_ms": value.get("latency_ms"),
        "request_fingerprint": value.get("request_fingerprint"),
        "prompt_fingerprint": value.get("prompt_fingerprint"),
        "usage": value.get("usage"),
        "metadata": safe_metadata,
    }


def _write_failure_bundle(
    output: Path,
    *,
    mode: str,
    source_snapshot: Mapping[str, str | None],
    audit_receipts_by_arm: Mapping[str, Sequence[Mapping[str, Any]]],
    error: BaseException,
    preregistration: Mapping[str, Any] | None = None,
) -> None:
    # Never append to, reinterpret, or contaminate any pre-existing bundle.
    # The locked output path is created here only after an attempted live call
    # has produced at least one sanitized receipt (enforced by the caller).
    if output.exists():
        return
    sanitized_audit = {
        arm: [
            _sanitized_failure_receipt(item)
            for item in audit_receipts_by_arm.get(arm, ())
        ]
        for arm in ARMS
    }
    receipts = [item for arm in ARMS for item in sanitized_audit[arm]]
    receipt_count = len(receipts)
    attempted_calls = sum(int(item.get("api_calls") or 0) for item in receipts)
    if mode == MODE_SMOKE:
        primary_classification = "smoke_gate_failed_full_not_launched"
    elif mode == MODE_DEV:
        primary_classification = "full_executed_diagnostic_integrity_failed"
    else:
        primary_classification = "offline_gate_failed_no_live_call"
    prereg = dict(preregistration or {})
    available_seals = {
        "source_sha256": dict(source_snapshot),
        "policy_sha256": _hash_or_none(LOCK_PATH),
        "provider_adapter_sha256": _hash_or_none(
            ROOT / "openai_response_boundary_v0_4_3.py"
        ),
        "preregistration_commit": prereg.get("preregistration_commit"),
        "preregistration_tree": prereg.get("preregistration_tree"),
    }
    value = {
        "schema_version": "ebrt-aperture-controls-failure-v0.4.3",
        "status": "INCOMPLETE",
        "success_manifest": False,
        "diagnostic_integrity_ready": False,
        "locked_decision_ready": False,
        "promotion_eligible": False,
        "mode": mode,
        "primary_execution_classification": primary_classification,
        "comparison_available": False,
        "diagnostic_comparison_available": False,
        "reasoning_comparison_available": False,
        "comparison_available_false_for_terminal_failure_bundle": True,
        "cause_conclusion_or_not_assessed": {
            "revision_envelope": "not_assessed_incomplete_or_subset_run",
            "raw_aperture": "not_assessed_incomplete_or_subset_run",
        },
        "failure_category": _failure_category(error),
        "failure_reason_code": _failure_reason_code(error),
        "failure_phase": (
            error.phase
            if isinstance(error, (OpenAIProviderBoundaryError, RunnerAuditError))
            else None
        ),
        "source_sha256": dict(source_snapshot),
        "policy_sha256": _hash_or_none(LOCK_PATH),
        "available_seals": available_seals,
        "attempted_calls": attempted_calls,
        "receipt_count": receipt_count,
        "attempted_calls_equal_receipt_count": attempted_calls == receipt_count,
        "artifact_hash_map_validated": False,
        "audit_receipts_by_arm": sanitized_audit,
        "sanitization": (
            "exception messages raw responses headers rejected cards and credentials omitted"
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    stage_root = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.failure-stage-", dir=output.parent)
    )
    stage_bundle = stage_root / "bundle"
    try:
        stage_bundle.mkdir()
        v041._write_json(stage_bundle / "failure.json", value)
        if canonical_json(v041._load_json(stage_bundle / "failure.json")) != (
            canonical_json(value)
        ):
            raise RunnerAuditError("artifact_hash_mismatch")
        if output.exists():
            return
        stage_bundle.rename(output)
        stage_root.rmdir()
    finally:
        if stage_root.exists():
            shutil.rmtree(stage_root)


def _validate_smoke_manifest(
    manifest_path: Path,
    *,
    source_snapshot: Mapping[str, str | None],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    if not manifest_path.is_file():
        raise FileNotFoundError("v0.4.3 smoke manifest does not exist")
    allowed_parents = {DEFAULT_SMOKE_OUTPUT.resolve(), CANONICAL_SMOKE_OUTPUT.resolve()}
    if manifest_path.resolve().parent not in allowed_parents:
        raise RuntimeError("smoke manifest is outside a policy-locked bundle path")
    manifest = v041._load_json(manifest_path)
    expected = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "status": "COMPLETE_DIAGNOSTIC_NON_DECISION",
        "success_manifest": False,
        "diagnostic_success_manifest": True,
        "diagnostic_integrity_ready": True,
        "locked_decision_ready": False,
        "promotion_eligible": False,
        "mode": MODE_SMOKE,
        "full_run_launch_ready": True,
        "full_launch_ready": True,
        "non_assessable_failures": 0,
        "nominal_api_calls": 28,
        "receipt_count": 28,
        "attempted_calls_equal_receipt_count": True,
        "exact_protocol_coverage": True,
        "artifact_hash_map_validated": True,
        "calls_rows_equal_receipts_equal_attempted_calls": True,
        "sibling_staging_directory_fully_audited_before_atomic_publish": True,
        "comparison_available": True,
        "diagnostic_comparison_available": True,
        "reasoning_comparison_available": False,
    }
    for key, expected_value in expected.items():
        if manifest.get(key) != expected_value:
            raise RuntimeError(f"v0.4.3 smoke manifest field drifted: {key}")
    if manifest.get("source_sha256") != dict(source_snapshot):
        raise RuntimeError("smoke and full source snapshots differ")
    if manifest.get("policy_sha256") != _sha256(LOCK_PATH):
        raise RuntimeError("smoke policy hash drifted")
    current_head = _git("rev-parse", "HEAD").stdout.strip()
    current_tree = _git("rev-parse", "HEAD^{tree}").stdout.strip()
    if (
        manifest.get("preregistration_commit") != current_head
        or manifest.get("preregistration_tree") != current_tree
    ):
        raise RuntimeError("smoke and full preregistration commits differ")
    artifact_hashes = manifest.get("artifact_sha256", {})
    expected_artifacts = {
        "results.json",
        "traces.jsonl",
        "calls.jsonl",
        "arm_rows.csv",
        "benchmark_report.md",
    }
    if set(artifact_hashes) != expected_artifacts:
        raise RuntimeError("smoke artifact hash map is incomplete")
    for name, expected_hash in artifact_hashes.items():
        path = manifest_path.parent / name
        if (
            Path(name).name != name
            or not path.is_file()
            or _sha256(path) != expected_hash
        ):
            raise RuntimeError(f"smoke artifact hash drifted: {name}")
    if (manifest_path.parent / "failure.json").exists():
        raise RuntimeError("smoke bundle contains failure.json")
    result = v041._load_json(manifest_path.parent / "results.json")
    _audit_written_artifacts(
        result=result,
        output=manifest_path.parent,
        artifact_sha256=artifact_hashes,
        expected_receipt_count=int(manifest["receipt_count"]),
        expected_attempted_calls=int(manifest["attempted_api_calls"]),
    )
    audit = {
        arm: [
            receipt
            for run in result["runs"]
            for receipt in run["arms"][arm]["receipts"]
        ]
        for arm in ARMS
    }
    check = validate_live_receipts(
        result,
        _load_lock(),
        audit_receipts_by_arm=audit,
    )
    flags = _derive_gate_flags(
        exact_coverage=_exact_protocol_coverage(result, policy=policy),
        receipt_validation=check,
        all_primary_endpoints_assessed=all(
            bool(run["primary_endpoint_assessed"]) for run in result["runs"]
        ),
        full_mode=False,
        integrity_components={
            "preregistration_audit_ready": bool(
                manifest.get("preregistration_audit_ready")
            ),
            "source_snapshot_audit_ready": bool(
                manifest.get("source_snapshot_audit_ready")
            ),
            "receipt_audit_ready": bool(manifest.get("receipt_audit_ready")),
            "privacy_audit_ready": bool(manifest.get("privacy_audit_ready")),
            "artifact_audit_ready": bool(manifest.get("artifact_audit_ready")),
        },
    )
    if flags["full_run_launch_ready"] is not True:
        raise RuntimeError("smoke result does not pass the full-launch gate")
    return {
        "schema_version": "ebrt-aperture-controls-launch-gate-v0.4.3",
        "manifest_sha256": _sha256(manifest_path),
        "bundle_name": manifest_path.parent.name,
        "mode": manifest["mode"],
        "diagnostic_integrity_ready": True,
        "full_run_launch_ready": True,
        "nominal_api_calls": check["nominal_api_calls"],
        "attempted_api_calls": check["attempted_api_calls"],
        "provider_boundary_failures": check["provider_boundary_failures"],
        "non_assessable_failures": check["non_assessable_failures"],
    }


def _synthetic_receipt(
    *,
    phase: str | None,
    reason: str | None,
    request_fingerprint: str = "1" * 64,
    prompt_fingerprint: str = "2" * 64,
    max_output_tokens: int = 768,
) -> ProviderReceipt:
    completed = phase is None
    outcome = "completed" if completed else OUTCOME_BY_PHASE[phase]
    parse_boundary = (
        "succeeded"
        if completed or phase == "provider_contract"
        else "failed_after_http"
        if phase == "sdk_response_parse"
        else "not_entered"
    )
    http_observed = phase != "request_call"
    status_by_reason = {
        "authentication": 401,
        "permission_denied": 403,
        "not_found": 404,
        "bad_request": 400,
        "conflict": 409,
        "unprocessable_entity": 422,
        "insufficient_quota": 429,
        "rate_limit": 429,
        "unknown429": 429,
        "server_error": 500,
        "http_other": 418,
    }
    status_code = status_by_reason.get(reason, 200) if http_observed else None
    usage = ProviderUsage(
        exact_provider_tokens=completed,
        input_tokens=10 if completed else None,
        output_tokens=5 if completed else None,
        total_tokens=15 if completed else None,
        cached_input_tokens=0 if completed else None,
        reasoning_tokens=1 if completed else None,
    )
    return ProviderReceipt(
        provider="openai_responses",
        requested_model="gpt-5.6-sol",
        returned_model="gpt-5.6-sol" if completed or http_observed else None,
        logical_calls=1,
        api_calls=1,
        latency_ms=1.0,
        request_fingerprint=request_fingerprint,
        prompt_fingerprint=prompt_fingerprint,
        usage=usage,
        metadata={
            "receipt_schema_version": RECEIPT_SCHEMA_VERSION,
            "status": "completed" if completed else "self_test_failure",
            "service_tier": "default" if completed else None,
            "response_id_sha256": "3" * 64 if http_observed else None,
            "server_request_id_sha256": "4" * 64 if http_observed else None,
            "client_request_id_sha256": "5" * 64,
            "provider_body_sha256": "6" * 64 if http_observed else None,
            "provider_body_byte_count": 64 if http_observed else None,
            "http_observed": http_observed,
            "http_status_code": status_code,
            "parse_boundary": parse_boundary,
            "failure_phase": phase,
            "failure_reason_code": reason,
            "failure_type": reason,
            "response_schema_fingerprint": "7" * 64,
            "semantic_protocol_fingerprint": "8" * 64,
            "reasoning_effort": "low",
            "max_output_tokens": max_output_tokens,
            "store": False,
            "previous_response_id": False,
            "truncation": "disabled",
            "sdk_version": provider_boundary.EXPECTED_OPENAI_SDK_VERSION,
            "pydantic_version": provider_boundary.EXPECTED_PYDANTIC_VERSION,
            "python_version": platform.python_version(),
            "attempt": 1,
            "retry_count": 0,
            "api_call_count_semantics": "attempted_client_call",
            "attempt_outcome": outcome,
            "refusal_count": 1 if reason == "provider_refusal" else 0,
        },
    )


class _OfflineBoundaryFailureProvider:
    def __init__(self, *, max_output_tokens: int, instructions: str) -> None:
        self.max_output_tokens = max_output_tokens
        self.instructions = instructions
        self._audit_receipts: list[dict[str, Any]] = []

    @property
    def provenance(self) -> Mapping[str, Any]:
        return {
            "provider": "openai_responses",
            "model": "gpt-5.6-sol",
            "api": "offline_boundary_self_test",
            "reasoning_effort": "low",
            "max_output_tokens": self.max_output_tokens,
            "instructions_fingerprint": v041.fingerprint(self.instructions),
            "store": False,
            "previous_response_id": False,
            "service_tier": "default",
            "truncation": "disabled",
            "retries": 0,
        }

    @property
    def audit_receipts(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self._audit_receipts)

    def generate(self, input_payload: Mapping[str, Any]) -> Any:
        receipt = _synthetic_receipt(
            phase="request_call",
            reason="timeout",
            request_fingerprint=v041.fingerprint(input_payload),
            prompt_fingerprint=v041.fingerprint(self.instructions),
            max_output_tokens=self.max_output_tokens,
        )
        self._audit_receipts.append(receipt.to_dict())
        raise OpenAIProviderBoundaryError(
            phase="request_call",
            reason_code="timeout",
            receipt=receipt,
        )


def _self_test_phase_code_matrix(policy: Mapping[str, Any]) -> int:
    _validate_policy(policy)
    observed = 0
    for phase in PROVIDER_BOUNDARY_PHASES:
        for reason in sorted(BOUNDARY_REASON_CODES_BY_PHASE[phase]):
            _validate_boundary_receipt(
                _synthetic_receipt(phase=phase, reason=reason).to_dict()
            )
            observed += 1
    if observed != len(PROVIDER_BOUNDARY_REASON_CODES):
        raise AssertionError("self-test did not exercise every boundary reason code")
    wrong = _synthetic_receipt(
        phase="request_call", reason="timeout"
    ).to_dict()
    wrong["metadata"]["failure_reason_code"] = "authentication"
    wrong["metadata"]["failure_type"] = "authentication"
    try:
        _validate_boundary_receipt(wrong)
    except RuntimeError:
        pass
    else:
        raise AssertionError("phase-incompatible reason code passed the receipt audit")
    unknown = _synthetic_receipt(
        phase="request_call", reason="timeout"
    ).to_dict()
    unknown["metadata"]["failure_reason_code"] = "unknown_self_test_code"
    unknown["metadata"]["failure_type"] = "unknown_self_test_code"
    try:
        _validate_boundary_receipt(unknown)
    except RuntimeError:
        pass
    else:
        raise AssertionError("unknown provider reason code passed the receipt audit")

    def expect_tamper_rejected(value: dict[str, Any]) -> None:
        try:
            _validate_boundary_receipt(value)
        except RuntimeError:
            return
        raise AssertionError("representative receipt tamper passed the audit")

    completed = _synthetic_receipt(phase=None, reason=None).to_dict()
    wrong_model = copy.deepcopy(completed)
    wrong_model["requested_model"] = "gpt-self-test-drift"
    expect_tamper_rejected(wrong_model)
    wrong_sdk = copy.deepcopy(completed)
    wrong_sdk["metadata"]["sdk_version"] = "0.0.0"
    expect_tamper_rejected(wrong_sdk)
    wrong_cap = copy.deepcopy(completed)
    wrong_cap["metadata"]["max_output_tokens"] = 0
    expect_tamper_rejected(wrong_cap)
    wrong_returned_model = copy.deepcopy(completed)
    wrong_returned_model["returned_model"] = None
    expect_tamper_rejected(wrong_returned_model)
    wrong_429 = _synthetic_receipt(
        phase="http_status", reason="rate_limit"
    ).to_dict()
    wrong_429["metadata"]["http_status_code"] = 418
    expect_tamper_rejected(wrong_429)
    duplicate = _synthetic_receipt(
        phase="request_call", reason="timeout"
    ).to_dict()
    try:
        _validate_unique_receipt_ids((duplicate, copy.deepcopy(duplicate)))
    except RuntimeError:
        pass
    else:
        raise AssertionError("duplicate receipt identity passed cardinality audit")
    return observed


def _self_test_cli_contract() -> None:
    parser = build_parser()
    smoke = parser.parse_args(["live-contract-smoke"])
    if smoke.command != "live-contract-smoke" or smoke.output != DEFAULT_SMOKE_OUTPUT:
        raise AssertionError("preregistered contract-smoke CLI drifted")
    dev = parser.parse_args(
        [
            "live-dev",
            "--contract-smoke-manifest",
            str(DEFAULT_SMOKE_OUTPUT / "manifest.json"),
        ]
    )
    if (
        dev.command != "live-dev"
        or dev.contract_smoke_manifest
        != DEFAULT_SMOKE_OUTPUT / "manifest.json"
        or dev.output != DEFAULT_DEV_OUTPUT
    ):
        raise AssertionError("preregistered full CLI drifted")


def _self_test_remaining_arms_continue(lock: Mapping[str, Any]) -> dict[str, Any]:
    cases, _ = v041._load_suite()
    case = cases[0]
    card_cap = int(lock["live_provider"]["max_card_output_tokens"])
    direct_cap = len(case.all_evidence) * card_cap
    providers: dict[str, Any] = {
        ARMS[0]: _OfflineBoundaryFailureProvider(
            max_output_tokens=direct_cap,
            instructions=ONE_SHOT_INSTRUCTIONS,
        ),
        ARMS[1]: v041._ScriptedMappingProvider(
            max_output_tokens=direct_cap,
            instructions=ONE_SHOT_INSTRUCTIONS,
        ),
        ARMS[2]: v041._ScriptedMappingProvider(
            max_output_tokens=card_cap,
            instructions=STAGED_INSTRUCTIONS,
        ),
        ARMS[3]: v041._ScriptedMappingProvider(
            max_output_tokens=card_cap,
            instructions=STAGED_INSTRUCTIONS,
        ),
    }
    with contextlib.redirect_stdout(io.StringIO()):
        result = execute_suite(
            cases=[case],
            providers=providers,
            max_card_output_tokens=card_cap,
            trials=1,
            mode="self_test_provider_boundary_continue",
            provider_lock={"provider": "offline_fault_matrix"},
        )
    run = result["runs"][0]
    failed = run["arms"][ARMS[0]]
    if (
        failed["terminal_outcome"] != "provider_boundary_failure"
        or failed["primary_endpoint_assessed"] is not False
        or len(failed["receipts"]) != 1
    ):
        raise AssertionError("faulted arm did not remain one non-assessable attempt")
    for arm in ARMS[1:]:
        if run["arms"][arm]["status"] != "completed":
            raise AssertionError("remaining preassigned arm did not continue")
    receipts = sum(len(run["arms"][arm]["receipts"]) for arm in ARMS)
    if receipts != 14:
        raise AssertionError("continuation test call geometry drifted")
    first_schedule = _schedule_record(result)
    second_schedule = _schedule_record(copy.deepcopy(result))
    if first_schedule != second_schedule:
        raise AssertionError("schedule projection is not deterministic")
    return {
        "failed_arm": ARMS[0],
        "remaining_completed": 3,
        "receipts": receipts,
        "schedule_sha256": first_schedule[1],
    }


def _self_test_manifest_schema(
    policy: Mapping[str, Any], lock: Mapping[str, Any]
) -> dict[str, Any]:
    cases, gold = v041._load_suite()
    case_ids = tuple(policy["execution_sequence"]["contract_smoke"]["case_ids"])
    selected = v041._select_cases(cases, case_ids)
    card_cap = int(lock["live_provider"]["max_card_output_tokens"])
    direct_cap = len(selected[0].all_evidence) * card_cap
    providers = {
        arm: v041._ScriptedMappingProvider(
            max_output_tokens=(direct_cap if arm in ONE_SHOT_ARMS else card_cap),
            instructions=(
                ONE_SHOT_INSTRUCTIONS if arm in ONE_SHOT_ARMS else STAGED_INSTRUCTIONS
            ),
        )
        for arm in ARMS
    }
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        result = execute_suite(
            cases=selected,
            providers=providers,
            max_card_output_tokens=card_cap,
            trials=1,
            mode=MODE_SMOKE,
            provider_lock={"provider": "offline_manifest_self_test"},
        )
    grade_executions(result, gold)
    counter = 0
    for run in result["runs"]:
        for arm in ARMS:
            payload = run["arms"][arm]
            projected: list[dict[str, Any]] = []
            for inherited in payload["receipts"]:
                counter += 1
                receipt = _synthetic_receipt(
                    phase=None,
                    reason=None,
                    request_fingerprint=inherited["request_fingerprint"],
                    prompt_fingerprint=inherited["prompt_fingerprint"],
                    max_output_tokens=int(
                        inherited["metadata"]["max_output_tokens"]
                    ),
                ).to_dict()
                receipt["metadata"]["client_request_id_sha256"] = hashlib.sha256(
                    f"offline-manifest-{counter}".encode("utf-8")
                ).hexdigest()
                projected.append(receipt)
            payload["receipts"] = projected
            for record, receipt in zip(
                payload["call_records"], projected, strict=True
            ):
                record["receipt"] = copy.deepcopy(receipt)
            payload["accounting"] = v041._accounting(projected)
    audit = {
        arm: [
            receipt
            for run in result["runs"]
            for receipt in run["arms"][arm]["receipts"]
        ]
        for arm in ARMS
    }
    receipt_validation = validate_live_receipts(
        result, lock, audit_receipts_by_arm=audit
    )
    expected_schedule, _, _ = _expected_schedule(result, policy)
    expected_schedule_hash = hashlib.sha256(
        canonical_json(expected_schedule).encode("utf-8")
    ).hexdigest()
    smoke_policy_hash = policy["execution_sequence"]["contract_smoke"][
        "run_and_arm_order_sha256"
    ]
    if (
        not _exact_protocol_coverage(result, policy=policy)
        or _schedule_record(result)[1] != expected_schedule_hash
        or expected_schedule_hash != smoke_policy_hash
        or expected_schedule_hash
        != "05b586414582e799dc827e76a7389375f49e0c0f721b234f783f3a9373fd460d"
    ):
        raise AssertionError("offline smoke deterministic schedule drifted")
    full_expected, _, _ = _expected_schedule({"mode": MODE_DEV}, policy)
    full_expected_hash = hashlib.sha256(
        canonical_json(full_expected).encode("utf-8")
    ).hexdigest()
    full_policy_hash = policy["execution_sequence"]["full_block"][
        "run_and_arm_order_sha256"
    ]
    if (
        full_expected_hash != full_policy_hash
        or full_expected_hash
        != "d586e073f31aedf46bafcf391a42330abc508db3610d3bd75adb6d660f66e957"
    ):
        raise AssertionError("offline full deterministic schedule drifted")
    full_case_ids = [item["case_id"] for item in full_expected[:LOCKED_CASE_COUNT]]
    synthetic_full_result = {
        "mode": MODE_DEV,
        "case_ids": full_case_ids,
        "case_count": LOCKED_CASE_COUNT,
        "trials": LOCKED_TRIALS,
        "runs": copy.deepcopy(full_expected),
    }
    if not _exact_protocol_coverage(synthetic_full_result, policy=policy):
        raise AssertionError("offline full exact schedule coverage drifted")
    for sequence_name, protocol_result in (
        ("contract_smoke", result),
        ("full_block", synthetic_full_result),
    ):
        tampered_policy = copy.deepcopy(policy)
        tampered_policy["execution_sequence"][sequence_name][
            "run_and_arm_order_sha256"
        ] = "0" * 64
        if _exact_protocol_coverage(protocol_result, policy=tampered_policy):
            raise AssertionError(
                f"tampered {sequence_name} preregistered schedule hash passed"
            )

    schedule_tampers: list[dict[str, Any]] = []
    for field, value in (
        ("run_id", "self-test-wrong-run-id"),
        ("run_position", 999),
        ("original_case_index", 999),
        ("case_id", "self-test-wrong-case"),
    ):
        tampered = copy.deepcopy(result)
        tampered["runs"][0][field] = value
        schedule_tampers.append(tampered)
    arm_tamper = copy.deepcopy(result)
    arm_tamper["runs"][0]["arm_order"] = list(
        reversed(arm_tamper["runs"][0]["arm_order"])
    )
    schedule_tampers.append(arm_tamper)
    reordered = copy.deepcopy(result)
    reordered["runs"] = list(reversed(reordered["runs"]))
    schedule_tampers.append(reordered)
    duplicated = copy.deepcopy(result)
    duplicated["runs"][1] = copy.deepcopy(duplicated["runs"][0])
    schedule_tampers.append(duplicated)
    dropped = copy.deepcopy(result)
    dropped["runs"].pop()
    schedule_tampers.append(dropped)
    for tampered in schedule_tampers:
        if _exact_protocol_coverage(tampered, policy=policy):
            raise AssertionError("deterministic schedule tamper passed exact coverage")
        if _schedule_record(tampered)[1] == expected_schedule_hash:
            raise AssertionError("deterministic schedule tamper retained expected hash")
    summary = summarize_runs(
        result["runs"],
        locked_case_ids=[case.case_id for case in cases],
        locked_trials=LOCKED_TRIALS,
        historical_reference=lock["historical_reference_only"],
        receipts_validated=True,
    )
    components = {
        "preregistration_audit_ready": True,
        "source_snapshot_audit_ready": True,
        "receipt_audit_ready": True,
        "privacy_audit_ready": True,
        "artifact_audit_ready": True,
    }
    flags = _derive_gate_flags(
        exact_coverage=_exact_protocol_coverage(result, policy=policy),
        receipt_validation=receipt_validation,
        all_primary_endpoints_assessed=True,
        full_mode=False,
        integrity_components=components,
    )
    receipt_validation.update(flags)
    summary["live_receipt_validation"] = receipt_validation
    summary["diagnostic_integrity_ready"] = flags["diagnostic_integrity_ready"]
    summary["locked_decision_ready"] = flags["locked_decision_ready"]
    result["summary"] = summary
    first_record = _execution_diagnostics(
        result, receipt_validation=receipt_validation, policy=policy
    )
    second_record = _execution_diagnostics(
        copy.deepcopy(result),
        receipt_validation=copy.deepcopy(receipt_validation),
        policy=policy,
    )
    if canonical_json(first_record) != canonical_json(second_record):
        raise AssertionError("execution-record regeneration is not deterministic")
    preregistration = {
        "preregistration_commit": "a" * 40,
        "preregistration_tree": "b" * 40,
        "upstream": "offline-self-test",
        "source_snapshot_matches_preregistration_commit": True,
        "worktree_clean_except_verified_smoke_bundle": True,
        "target_output_paths_absent": True,
    }
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        first_manifest = write_bundle(
            result,
            temp_root / "first",
            source_snapshot=BOOT_SOURCE_SNAPSHOT,
            preregistration=preregistration,
        )
        second_manifest = write_bundle(
            copy.deepcopy(result),
            temp_root / "second",
            source_snapshot=BOOT_SOURCE_SNAPSHOT,
            preregistration=preregistration,
        )
        calls_path = temp_root / "first" / "calls.jsonl"
        original_call_lines = [
            line
            for line in calls_path.read_text(encoding="utf-8").splitlines()
            if line
        ]
        call_variants = {
            "drop": original_call_lines[:-1],
            "duplicate": [*original_call_lines, original_call_lines[-1]],
            "reorder": list(reversed(original_call_lines)),
        }
        altered_rows = [json.loads(line) for line in original_call_lines]
        altered_rows[0]["arm_call_index"] = 999
        call_variants["alter"] = [canonical_json(row) for row in altered_rows]
        for name, lines in call_variants.items():
            calls_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            tampered_hashes = dict(first_manifest["artifact_sha256"])
            tampered_hashes["calls.jsonl"] = _sha256(calls_path)
            try:
                _audit_written_artifacts(
                    result=result,
                    output=temp_root / "first",
                    artifact_sha256=tampered_hashes,
                    expected_receipt_count=28,
                    expected_attempted_calls=28,
                )
            except RunnerAuditError:
                pass
            else:
                raise AssertionError(f"calls.jsonl {name} tamper passed artifact audit")
        calls_path.write_text(
            "\n".join(original_call_lines) + "\n", encoding="utf-8"
        )
        if _sha256(calls_path) != first_manifest["artifact_sha256"]["calls.jsonl"]:
            raise AssertionError("calls.jsonl self-test did not restore original bytes")

        for fault in ("write", "audit", "pre_publish"):
            target = temp_root / f"fault-{fault}"
            try:
                write_bundle(
                    copy.deepcopy(result),
                    target,
                    source_snapshot=BOOT_SOURCE_SNAPSHOT,
                    preregistration=preregistration,
                    _fault_injection=fault,
                )
            except RunnerAuditError:
                pass
            else:
                raise AssertionError(f"bundle {fault} fault did not terminate")
            if target.exists() or list(
                temp_root.glob(f".{target.name}.stage-*")
            ):
                raise AssertionError(f"bundle {fault} fault exposed a partial stage")
        preexisting = temp_root / "preexisting-target"
        preexisting.mkdir()
        sentinel = preexisting / "sentinel.txt"
        sentinel.write_text("DO_NOT_MUTATE", encoding="utf-8")
        try:
            write_bundle(
                copy.deepcopy(result),
                preexisting,
                source_snapshot=BOOT_SOURCE_SNAPSHOT,
                preregistration=preregistration,
            )
        except FileExistsError:
            pass
        else:
            raise AssertionError("pre-existing final target was accepted")
        if sentinel.read_text(encoding="utf-8") != "DO_NOT_MUTATE":
            raise AssertionError("pre-existing final target was mutated")
    if canonical_json(first_manifest) != canonical_json(second_manifest):
        raise AssertionError("manifest regeneration is not deterministic")
    required = {
        "case_count",
        "trials",
        "scheduled_arm_endpoints",
        "exact_protocol_coverage",
        "failed_receipt_count",
        "classified_failed_receipt_count",
        "classified_nonassessable_endpoint_count",
        "unclassified_nonassessable_failure_count",
        "accepted_endpoint_count",
        "assessed_endpoint_count",
        "http_observation_recorded_count",
        "http_acquired_count",
        "http_status_code_available_count",
        "structured_parse_success_count",
        "terminal_local_rejections_by_reason",
        "failure_counts_by_phase_and_allowlisted_code",
        "terminal_local_rejection_count_and_reason_codes",
        "receipt_and_artifact_audit_results",
        "per_arm_accepted_assessed_strict_counts",
        "revision_envelope_contrast",
        "raw_aperture_contrast",
        "exact_total_tokens_only_when_complete",
        "full_launch_ready",
        "calls_rows_equal_receipts_equal_attempted_calls",
        "sibling_staging_directory_fully_audited_before_atomic_publish",
        "comparison_available_false_for_terminal_failure_bundle",
        "artifact_hash_map_validated",
        "cause_conclusion_or_not_assessed",
        "receipt_count",
        "run_and_arm_order_sha256",
        "per_arm_endpoint_counts",
        "classified_failed_receipts",
        "unclassified_failed_receipts",
        "http_observed_count",
        "structured_parse_attempted_count",
        "structured_parse_succeeded_count",
        "exact_usage_available_count",
        "terminal_local_rejection_reasons",
        "diagnostic_integrity_components",
        "primary_execution_classification",
        "classification_pending_full_execution",
        "exact_total_tokens_available",
        "exact_total_tokens",
    }
    if not required <= set(first_manifest):
        raise AssertionError("manifest omits a required v0.4.3 execution field")
    execution_required = {
        "preregistration_commit",
        "preregistration_tree",
        "policy_sha256",
        "boot_source_sha256_map",
        "predecessor_manifest_sha256s",
        "runtime_versions",
        "failure_counts_by_phase_and_allowlisted_code",
        "terminal_local_rejection_count_and_reason_codes",
        "receipt_and_artifact_audit_results",
        "per_arm_accepted_assessed_strict_counts",
        "revision_envelope_contrast",
        "raw_aperture_contrast",
        "exact_total_tokens_only_when_complete",
        "diagnostic_integrity_ready",
        "locked_decision_ready",
        "full_launch_ready",
        "calls_rows_equal_receipts_equal_attempted_calls",
        "sibling_staging_directory_fully_audited_before_atomic_publish",
        "comparison_available_false_for_terminal_failure_bundle",
    }
    execution_record = first_manifest["execution_record"]
    if not execution_required <= set(execution_record):
        raise AssertionError("execution_record omits policy-exact field names")
    identity_pairs = (
        ("exact_protocol_coverage", "exact_case_trial_run_arm_coverage"),
        ("classified_failed_receipt_count", "classified_failed_receipts"),
        ("http_acquired_count", "http_observed_count"),
        ("http_status_code_available_count", "http_status_available_count"),
        ("structured_parse_success_count", "structured_parse_succeeded_count"),
        ("full_launch_ready", "full_run_launch_ready"),
    )
    for canonical, alias in identity_pairs:
        if first_manifest[canonical] != first_manifest[alias]:
            raise AssertionError(f"comparison alias differs: {canonical}/{alias}")
    if (
        first_manifest["receipt_count"] != 28
        or first_manifest["scheduled_arm_endpoints"] != 8
        or first_manifest["exact_protocol_coverage"] is not True
        or first_manifest["run_and_arm_order_sha256"]
        != first_manifest["expected_run_and_arm_order_sha256"]
        or set(first_manifest["provider_boundary_failures_by_phase"])
        != set(PROVIDER_BOUNDARY_PHASES)
        or set(first_manifest["provider_boundary_failures_by_reason"])
        != set(PROVIDER_BOUNDARY_REASON_CODES)
        or set(first_manifest["terminal_local_rejections_by_reason"])
        != set(LOCAL_CONTRACT_REASON_CODES)
        or any(first_manifest["provider_boundary_failures_by_phase"].values())
        or any(first_manifest["provider_boundary_failures_by_reason"].values())
        or any(first_manifest["terminal_local_rejections_by_reason"].values())
        or first_manifest["calls_rows_equal_receipts_equal_attempted_calls"]
        is not True
        or first_manifest[
            "sibling_staging_directory_fully_audited_before_atomic_publish"
        ]
        is not True
        or first_manifest["comparison_available"] is not True
        or first_manifest["diagnostic_comparison_available"] is not True
        or first_manifest["reasoning_comparison_available"] is not False
        or first_manifest[
            "comparison_available_false_for_terminal_failure_bundle"
        ]
        is not True
        or first_manifest["primary_execution_classification"] is not None
        or first_manifest["classification_pending_full_execution"] is not True
    ):
        raise AssertionError("offline smoke manifest classification or geometry drifted")
    return {
        "receipt_count": first_manifest["receipt_count"],
        "schedule_sha256": first_manifest["run_and_arm_order_sha256"],
        "deterministic_regeneration": True,
        "atomic_faults_exercised": 3,
        "calls_tampers_exercised": 4,
        "schedule_tampers_exercised": len(schedule_tampers),
    }


def _self_test_gate_separation() -> None:
    base = {
        "validated": True,
        "terminal_policy_validated": True,
        "provider_boundary_receipts_validated": True,
        "unclassified_non_assessable_failures": 0,
        "provider_boundary_failures": 1,
        "non_assessable_failures": 1,
    }
    flags = _derive_gate_flags(
        exact_coverage=True,
        receipt_validation=base,
        all_primary_endpoints_assessed=False,
        full_mode=True,
        integrity_components={
            "preregistration_audit_ready": True,
            "source_snapshot_audit_ready": True,
            "receipt_audit_ready": True,
            "privacy_audit_ready": True,
            "artifact_audit_ready": True,
        },
    )
    if flags != {
        "diagnostic_integrity_ready": True,
        "locked_decision_ready": False,
        "full_run_launch_ready": False,
    }:
        raise AssertionError("diagnostic and decision gates collapsed")
    complete = dict(base)
    complete.update({"provider_boundary_failures": 0, "non_assessable_failures": 0})
    full = _derive_gate_flags(
        exact_coverage=True,
        receipt_validation=complete,
        all_primary_endpoints_assessed=True,
        full_mode=True,
        integrity_components={
            "preregistration_audit_ready": True,
            "source_snapshot_audit_ready": True,
            "receipt_audit_ready": True,
            "privacy_audit_ready": True,
            "artifact_audit_ready": True,
        },
    )
    if not full["diagnostic_integrity_ready"] or not full["locked_decision_ready"]:
        raise AssertionError("complete full gate did not open")
    broken_components = {
        "preregistration_audit_ready": True,
        "source_snapshot_audit_ready": True,
        "receipt_audit_ready": True,
        "privacy_audit_ready": True,
        "artifact_audit_ready": False,
    }
    broken = _derive_gate_flags(
        exact_coverage=True,
        receipt_validation=complete,
        all_primary_endpoints_assessed=True,
        full_mode=True,
        integrity_components=broken_components,
    )
    if broken["diagnostic_integrity_ready"] or broken["locked_decision_ready"]:
        raise AssertionError("failed artifact audit did not close integrity gates")
    if (
        _primary_execution_classification(
            mode=MODE_SMOKE,
            diagnostic_ready=True,
            locked_ready=False,
            full_launch_ready=True,
        )
        is not None
        or _primary_execution_classification(
            mode=MODE_SMOKE,
            diagnostic_ready=False,
            locked_ready=False,
            full_launch_ready=False,
        )
        != "smoke_gate_failed_full_not_launched"
        or _primary_execution_classification(
            mode=MODE_DEV,
            diagnostic_ready=True,
            locked_ready=True,
            full_launch_ready=False,
        )
        != "full_executed_decision_ready"
    ):
        raise AssertionError("primary execution classification drifted")


def run_self_tests() -> dict[str, Any]:
    source_snapshot = dict(BOOT_SOURCE_SNAPSHOT)
    policy = _read_policy(allow_missing=True)
    if policy is not None:
        _assert_source_snapshot(source_snapshot)
    elif source_snapshot:
        raise AssertionError("missing policy produced a nonempty boot snapshot")

    inherited = subprocess.run(
        [sys.executable, str(PREDECESSOR_RUNNER_PATH), "self-test"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if inherited.returncode != 0:
        raise AssertionError("frozen v0.4.2 self-test failed")
    adapter = provider_boundary.self_test()
    if (
        adapter.get("status") != "PASS"
        or adapter.get("network_calls") != 0
        or adapter.get("receipt_schema_version") != RECEIPT_SCHEMA_VERSION
    ):
        raise AssertionError("public provider-boundary adapter self-test failed")

    matrix_count = _self_test_phase_code_matrix(policy) if policy is not None else 0
    lock = _load_lock(allow_missing_policy=True)
    continuation = _self_test_remaining_arms_continue(lock)
    _self_test_gate_separation()
    _self_test_cli_contract()
    manifest_schema = (
        _self_test_manifest_schema(policy, lock) if policy is not None else None
    )

    wrong_snapshot = dict(source_snapshot)
    if wrong_snapshot:
        first = next(iter(wrong_snapshot))
        wrong_snapshot[first] = "0" * 64
        try:
            _assert_source_snapshot(wrong_snapshot)
        except RuntimeError:
            pass
        else:
            raise AssertionError("source-seal tamper passed the boot audit")

    leak = "PRIVATE_LEAK_SENTINEL"
    with tempfile.TemporaryDirectory() as temp_dir:
        receipt = _synthetic_receipt(
            phase="request_call", reason="timeout"
        )
        error = OpenAIProviderBoundaryError(
            phase="request_call", reason_code="timeout", receipt=receipt
        )
        output = Path(temp_dir) / "failure"
        _write_failure_bundle(
            output,
            mode="self_test",
            source_snapshot=source_snapshot,
            audit_receipts_by_arm={
                **{arm: () for arm in ARMS},
                ARMS[0]: (receipt.to_dict(),),
            },
            error=error,
        )
        text = (output / "failure.json").read_text(encoding="utf-8")
        if leak in text or "bearer " in text.casefold():
            raise AssertionError("failure bundle leaked raw error or credential material")
        failure = v041._load_json(output / "failure.json")
        if (
            failure["primary_execution_classification"]
            != "offline_gate_failed_no_live_call"
            or failure["comparison_available"] is not False
            or failure["diagnostic_comparison_available"] is not False
            or failure["reasoning_comparison_available"] is not False
            or failure[
                "comparison_available_false_for_terminal_failure_bundle"
            ]
            is not True
            or failure["attempted_calls"] != 1
            or failure["receipt_count"] != 1
            or failure["attempted_calls_equal_receipt_count"] is not True
            or failure["artifact_hash_map_validated"] is not False
            or set(failure["available_seals"])
            != {
                "source_sha256",
                "policy_sha256",
                "provider_adapter_sha256",
                "preregistration_commit",
                "preregistration_tree",
            }
            or set(failure["cause_conclusion_or_not_assessed"].values())
            != {"not_assessed_incomplete_or_subset_run"}
            or list(Path(temp_dir).glob(".failure.failure-stage-*"))
        ):
            raise AssertionError("sanitized failure-bundle contract drifted")
        contaminated = Path(temp_dir) / "preexisting"
        contaminated.mkdir()
        sentinel = contaminated / "existing.txt"
        sentinel.write_text("DO_NOT_MUTATE", encoding="utf-8")
        _write_failure_bundle(
            contaminated,
            mode="self_test",
            source_snapshot=source_snapshot,
            audit_receipts_by_arm={arm: () for arm in ARMS},
            error=error,
        )
        if (
            sentinel.read_text(encoding="utf-8") != "DO_NOT_MUTATE"
            or (contaminated / "failure.json").exists()
        ):
            raise AssertionError("failure recording mutated a pre-existing bundle")

    if policy is not None:
        _assert_source_snapshot(source_snapshot)
    return {
        "status": "ok",
        "network_calls": 0,
        "predecessor_self_test": "passed",
        "provider_adapter_self_test": "passed",
        "provider_adapter_checks": len(adapter.get("checks", ())),
        "policy": "validated" if policy is not None else "missing_self_test_only",
        "phase_reason_pairs_exercised": matrix_count,
        "catch_all_acquisition": "request_call/request_unclassified",
        "remaining_arms_continue": continuation,
        "manifest_schema": manifest_schema,
        "diagnostic_integrity_separate_from_decision": True,
        "preregistered_cli_contract": True,
        "local_strict_reason_codes": len(LOCAL_CONTRACT_REASON_CODES),
        "provider_boundary_reason_codes": len(PROVIDER_BOUNDARY_REASON_CODES),
        "source_sha256": source_snapshot,
    }


def _run_live(
    *,
    output: Path,
    case_ids: Sequence[str],
    trials: int,
    mode: str,
    contract_smoke_manifest: Path | None = None,
) -> dict[str, Any]:
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        raise RuntimeError("OPENAI_API_KEY is unavailable in the process environment")
    policy = _read_policy()
    assert policy is not None
    source_snapshot = _source_snapshot(_policy_boot_source_paths(policy))
    providers: dict[str, Any] = {}
    preregistration: dict[str, Any] = {}
    try:
        _assert_source_snapshot(source_snapshot)
        preregistration = _validate_preregistration_state(
            policy=policy,
            source_snapshot=source_snapshot,
            output=output,
            mode=mode,
            contract_smoke_manifest=contract_smoke_manifest,
        )
        lock = _load_lock()
        launch_gate = None
        if mode == MODE_DEV:
            if contract_smoke_manifest is None:
                raise RuntimeError("live-dev requires a verified v0.4.3 smoke manifest")
            launch_gate = _validate_smoke_manifest(
                contract_smoke_manifest,
                source_snapshot=source_snapshot,
                policy=policy,
            )
        elif contract_smoke_manifest is not None:
            raise RuntimeError("a smoke manifest is valid only for live-dev")

        v041._validate_parent_manifest()
        cases, gold = v041._load_suite()
        selected = v041._select_cases(cases, case_ids)
        smoke_policy = policy["execution_sequence"]["contract_smoke"]
        if mode == MODE_SMOKE and (
            tuple(case_ids) != tuple(smoke_policy["case_ids"])
            or trials != int(smoke_policy["trials"])
        ):
            raise RuntimeError(
                "v0.4.3 live-contract-smoke must remain exact two-case x one"
            )
        if mode == MODE_DEV and (
            tuple(case_ids) != tuple(case.case_id for case in cases)
            or trials != LOCKED_TRIALS
        ):
            raise RuntimeError("v0.4.3 live-dev must remain exact ten-case x three")
        chunks = {len(case.all_evidence) for case in selected}
        if len(chunks) != 1:
            raise RuntimeError("one-shot output cap requires equal evidence counts")

        live = lock["live_provider"]
        runtime = policy["runtime"]
        for key in (
            "model",
            "reasoning_effort",
            "service_tier",
            "store",
            "previous_response_id",
            "truncation",
        ):
            if runtime[key] != live[key]:
                raise RuntimeError(f"v0.4.3 runtime differs from inherited lock: {key}")
        card_cap = int(live["max_card_output_tokens"])
        direct_cap = next(iter(chunks)) * card_cap
        for arm in ARMS:
            providers[arm] = make_openai_mapping_provider_v0_4_3(
                model=live["model"],
                reasoning_effort=live["reasoning_effort"],
                timeout_seconds=float(runtime["timeout_seconds"]),
                max_output_tokens=(direct_cap if arm in ONE_SHOT_ARMS else card_cap),
                instructions=(
                    ONE_SHOT_INSTRUCTIONS
                    if arm in ONE_SHOT_ARMS
                    else STAGED_INSTRUCTIONS
                ),
            )
        provider_lock = {
            "provider": live["provider"],
            "api": "responses.with_raw_response.parse+raw.parse",
            "model": live["model"],
            "reasoning_effort": live["reasoning_effort"],
            "service_tier": live["service_tier"],
            "store": live["store"],
            "previous_response_id": live["previous_response_id"],
            "truncation": live["truncation"],
            "sdk_retries": 0,
            "resume": False,
            "partial_fill": False,
        }
        result = execute_suite(
            cases=selected,
            providers=providers,
            max_card_output_tokens=card_cap,
            trials=trials,
            mode=mode,
            provider_lock=provider_lock,
        )
        grade_executions(result, gold)
        result["launch_gate"] = launch_gate
        receipt_validation = validate_live_receipts(
            result,
            lock,
            audit_receipts_by_arm={
                arm: providers[arm].audit_receipts for arm in ARMS
            },
        )
        summary = summarize_runs(
            result["runs"],
            locked_case_ids=[case.case_id for case in cases],
            locked_trials=LOCKED_TRIALS,
            historical_reference=lock["historical_reference_only"],
            receipts_validated=bool(receipt_validation["validated"]),
        )
        all_assessed = all(
            bool(run["primary_endpoint_assessed"]) for run in result["runs"]
        )
        flags = _derive_gate_flags(
            exact_coverage=_exact_protocol_coverage(result, policy=policy),
            receipt_validation=receipt_validation,
            all_primary_endpoints_assessed=all_assessed,
            full_mode=(mode == MODE_DEV),
            integrity_components={
                "preregistration_audit_ready": True,
                "source_snapshot_audit_ready": True,
                "receipt_audit_ready": bool(
                    receipt_validation["validated"]
                    and receipt_validation["terminal_policy_validated"]
                    and receipt_validation[
                        "provider_boundary_receipts_validated"
                    ]
                ),
                "privacy_audit_ready": bool(
                    receipt_validation["privacy_audit_validated"]
                ),
                "artifact_audit_ready": True,
            },
        )
        receipt_validation.update(flags)
        summary["live_receipt_validation"] = receipt_validation
        summary["diagnostic_integrity_ready"] = flags[
            "diagnostic_integrity_ready"
        ]
        if mode == MODE_DEV and bool(summary["locked_decision_ready"]) != flags[
            "locked_decision_ready"
        ]:
            raise RuntimeError("v0.4.3 inherited and prospective decision gates disagree")
        summary["locked_decision_ready"] = flags["locked_decision_ready"]
        summary["cause_decision"]["decision_ready"] = flags[
            "locked_decision_ready"
        ]
        result["summary"] = summary
        result["claim_boundary"] = list(lock["claim_boundary"])
        result["preregistration"] = dict(preregistration)
        _assert_source_snapshot(source_snapshot)
        manifest = write_bundle(
            result,
            output,
            source_snapshot=source_snapshot,
            preregistration=preregistration,
        )
    except Exception as error:
        audit = {arm: providers[arm].audit_receipts for arm in providers}
        if any(audit.values()):
            _write_failure_bundle(
                output,
                mode=mode,
                source_snapshot=source_snapshot,
                audit_receipts_by_arm=audit,
                error=error,
                preregistration=preregistration,
            )
        raise
    return {
        "output": str(output),
        "summary": result["summary"],
        "manifest": manifest,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "self-test",
        help="run offline adapter, phase/code, continuation, seal, and gate tests",
    )
    smoke = subparsers.add_parser(
        "live-contract-smoke",
        help="run the fixed two-case one-trial provider-boundary smoke",
    )
    smoke.add_argument("--output", type=Path, default=DEFAULT_SMOKE_OUTPUT)
    dev = subparsers.add_parser(
        "live-dev",
        help="run the exact non-overridable ten-case three-trial DEV block",
    )
    dev.add_argument("--output", type=Path, default=DEFAULT_DEV_OUTPUT)
    dev.add_argument("--contract-smoke-manifest", type=Path, required=True)
    return parser


def _resolve_command(command: str) -> tuple[list[str], int, str]:
    policy = _read_policy()
    assert policy is not None
    cases, _ = v041._load_suite()
    if command == "live-contract-smoke":
        preset = policy["execution_sequence"]["contract_smoke"]
        return list(preset["case_ids"]), int(preset["trials"]), MODE_SMOKE
    if command == "live-dev":
        return [case.case_id for case in cases], LOCKED_TRIALS, MODE_DEV
    raise ValueError("unknown v0.4.3 command")


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "self-test":
        value = run_self_tests()
    else:
        case_ids, trials, mode = _resolve_command(args.command)
        value = _run_live(
            output=args.output,
            case_ids=case_ids,
            trials=trials,
            mode=mode,
            contract_smoke_manifest=getattr(
                args, "contract_smoke_manifest", None
            ),
        )
    print(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
