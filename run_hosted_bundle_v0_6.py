#!/usr/bin/env python3
"""Preregistered five-call hosted execution for EBRT v0.6.

The irreversible provider boundary is entered only after a network-zero
projection, lineage-schema, predecessor-byte, runtime, and policy-lock
preflight.  Semantic gold is parsed only after all five fixed attempts have
completed.  A provider or local contract failure freezes an incomplete block;
missing cells are never backfilled.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

import hosted_bundle_projection_v0_6 as projection
from hosted_bundle_lineage_v0_6 import (
    ProviderLineageOutput,
    grade_p_pre_event,
    grade_p_stale,
    grade_post_event,
    load_gold,
    preflight_self_test as lineage_preflight_self_test,
    sample_provider_output,
    validate_and_compile_output,
)
from language_replay_bridge_v0_4 import canonical_json, fingerprint
from openai_lineage_provider_v0_6 import (
    INSTRUCTIONS_FINGERPRINT_SHA256,
    MAX_OUTPUT_TOKENS,
    MODEL,
    REASONING_EFFORT,
    TIMEOUT_SECONDS,
    OpenAILineageProviderV0_6,
    offline_transport_self_test,
    provider_self_test,
)
from openai_response_boundary_v0_4_3 import (
    BOUNDARY_REASON_CODES_BY_PHASE,
    RECEIPT_SCHEMA_VERSION,
    OpenAIProviderBoundaryError,
)


ROOT = Path(__file__).resolve().parent
LOCK_PATH = ROOT / "policy_lock_hosted_bundle_v0_6.json"
GOLD_PATH = ROOT / "fixtures" / "hosted_bundle_lineage_gold_v0_6.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "hosted_bundle_execution_v0_6_live_r01"

SCHEMA_VERSION = "ebrt-hosted-bundle-execution-v0.6.1"
LOCK_SCHEMA_VERSION = "ebrt-hosted-bundle-policy-lock-v0.6.1"
MANIFEST_SCHEMA_VERSION = "ebrt-hosted-bundle-manifest-v0.6.1"
CALLS_SCHEMA_VERSION = "ebrt-hosted-bundle-call-receipt-v0.6.1"
PROVIDER_INPUTS_SCHEMA_VERSION = "ebrt-hosted-bundle-provider-inputs-v0.6.1"
CALL_ORDER = ("P", "A", "B", "D", "C")
ARTIFACT_FILES = (
    "result.json",
    "calls.jsonl",
    "attempt_journal.jsonl",
    "provider_inputs.json",
    "projection_bundle.json",
    "report.md",
    "manifest.json",
)

SOURCE_PATHS = {
    "runner": "run_hosted_bundle_v0_6.py",
    "projection": "hosted_bundle_projection_v0_6.py",
    "projection_fixture": "fixtures/hosted_bundle_projection_v0_6.json",
    "lineage": "hosted_bundle_lineage_v0_6.py",
    "lineage_gold": "fixtures/hosted_bundle_lineage_gold_v0_6.json",
    "provider": "openai_lineage_provider_v0_6.py",
    "provider_boundary": "openai_response_boundary_v0_4_3.py",
    "provider_base": "openai_reasoning_provider_v0_4.py",
    "public_receipt_schema": "language_replay_bridge_v0_4.py",
    "live_requirements": "requirements-live.txt",
}

V052_ARTIFACT_PATHS = {
    "calls.jsonl": "artifacts/demo_hackathon_strategy_walkthrough_v0_5_2_live_r01/calls.jsonl",
    "demo.json": "artifacts/demo_hackathon_strategy_walkthrough_v0_5_2_live_r01/demo.json",
    "manifest.json": "artifacts/demo_hackathon_strategy_walkthrough_v0_5_2_live_r01/manifest.json",
    "report.md": "artifacts/demo_hackathon_strategy_walkthrough_v0_5_2_live_r01/report.md",
}

CLAIM_BOUNDARY = (
    "This is one contaminated five-call engineering regression over a known synthetic walkthrough, not a fresh quality benchmark.",
    "P is a pre-event product reference and is excluded from A/B/C/D effect contrasts; the fixed execution order is unbalanced and time-confounded.",
    "A/B/C/D receive byte-identical ordered R1-R6 raw evidence; B/C/D receive the same contaminated typed public DAG and differ only in their frozen public-control treatment.",
    "C and D match in row set, value/sign multiset, sparsity, per-lane norm, merge norm, and schema; only signed-displacement placement differs.",
    "Signed public actuator displacement is not evidence truth, probability, required support, hidden-state editing, or a semantic boost/suppress claim.",
    "The public DAG and surrogate program are supplied case-specific oracle structure rather than autonomously discovered semantics.",
    "No separately loaded grader or gold artifact enters provider input; B/C/D do receive a contaminated answer-adjacent oracle lineage program.",
    "A local backward pass exists only in the public differentiable substrate; no gradient crosses GPT, JSON, provider parsing, or grading boundaries.",
    "Surrogate status, hosted output, strict lineage, effect label, calls, tokens, and latency are reported separately.",
    "Promotion requires a complete bridge plus the preregistered strict P and D paths; it does not require D to outperform A, B, or C.",
    "The frozen v0.5.2 near-pass remains byte-identical and false; this successor does not regrade, relax, or replace it.",
    "Sanitized receipts and local hashes establish internal consistency, not cryptographic provider attestation; an external manifest anchor is required to distinguish a coherent forgery.",
)

DECISION_RULES = {
    "run_complete": "all five fixed attempts return one valid public lineage output and one sanitized receipt",
    "p_pre_event": "P passes the locked R1-R5 POLISH and fact-local lineage contract",
    "p_stale": "the unchanged P output passes its locked post-event stale signature while preserving R5",
    "d_strict": "D passes answer, exact direct/inherited/total lineage, invalidation, and stable-fact endpoints",
    "effect": "observational strict-endpoint contrast only; superiority and causality are not inferred",
    "promotion": "PROMOTE_V0_7_HOSTED_BUNDLE_GATE iff run, P pre-event, P stale, surrogate, and D strict all pass",
    "failure": "any provider or local output-contract failure freezes INCOMPLETE and no missing call is backfilled",
}


class HostedBundleExecutionError(RuntimeError):
    """A policy, execution, artifact, or validation invariant failed."""


def _staging_directory(output: Path) -> Path:
    return output.parent / f".{output.name}.inflight"


def _canonical_bytes(value: Any, *, trailing_newline: bool = False) -> bytes:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return raw + (b"\n" if trailing_newline else b"")


def _pretty_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_path(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _clone(value: Any) -> Any:
    return json.loads(_canonical_bytes(value))


def _seal(value: Mapping[str, Any]) -> dict[str, Any]:
    output = _clone(value)
    output.pop("fingerprint_sha256", None)
    output["fingerprint_sha256"] = fingerprint(output)
    return output


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _strict_load(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise HostedBundleExecutionError(f"expected regular JSON file: {path}")

    def reject_constant(token: str) -> None:
        raise HostedBundleExecutionError(f"non-finite JSON token: {token}")

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, value in pairs:
            if key in output:
                raise HostedBundleExecutionError(f"duplicate JSON key: {key}")
            output[key] = value
        return output

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise HostedBundleExecutionError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise HostedBundleExecutionError(f"JSON root is not an object: {path}")
    return value


def _runtime() -> dict[str, Any]:
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
        "python": sys.version.split()[0],
        "openai": importlib.metadata.version("openai"),
        "pydantic": importlib.metadata.version("pydantic"),
        "torch": importlib.metadata.version("torch"),
        "machine": platform.machine(),
    }


def _file_receipts(paths: Mapping[str, str]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for label, relative in paths.items():
        path = ROOT / relative
        if not path.is_file() or path.is_symlink():
            raise HostedBundleExecutionError(f"locked source missing: {label}")
        raw = path.read_bytes()
        output[label] = {
            "path": relative,
            "bytes": len(raw),
            "sha256": _sha256_bytes(raw),
        }
    return output


def policy_lock_material() -> dict[str, Any]:
    """Return the prospective lock without parsing semantic gold."""

    return _seal(
        {
            "artifact": {
                "default_directory": str(DEFAULT_OUTPUT.relative_to(ROOT)),
                "files": list(ARTIFACT_FILES),
            },
            "call_order": list(CALL_ORDER),
            "claim_boundary": list(CLAIM_BOUNDARY),
            "decision_rules": DECISION_RULES,
            "instructions_fingerprint_sha256": INSTRUCTIONS_FINGERPRINT_SHA256,
            "predecessor_v0_5_2": {
                "expected_walkthrough_contract_passed": False,
                "files": _file_receipts(V052_ARTIFACT_PATHS),
            },
            "response_schema_fingerprint_sha256": fingerprint(
                ProviderLineageOutput.model_json_schema()
            ),
            "runtime": _runtime(),
            "schema_version": LOCK_SCHEMA_VERSION,
            "sources": _file_receipts(SOURCE_PATHS),
            "status": "PREREGISTERED_FIVE_CALL_LIVE_BLOCK",
        }
    )


def _load_lock() -> dict[str, Any]:
    lock = _strict_load(LOCK_PATH)
    if lock != policy_lock_material():
        raise HostedBundleExecutionError("policy lock or locked source bytes drifted")
    if lock.get("fingerprint_sha256") != fingerprint(
        {key: _clone(value) for key, value in lock.items() if key != "fingerprint_sha256"}
    ):
        raise HostedBundleExecutionError("policy lock fingerprint drifted")
    demo = _strict_load(ROOT / V052_ARTIFACT_PATHS["demo.json"])
    if demo.get("decision", {}).get("walkthrough_contract_passed") is not False:
        raise HostedBundleExecutionError("v0.5.2 near-pass endpoint was altered")
    return lock


def _source_snapshot(lock: Mapping[str, Any]) -> dict[str, str]:
    output: dict[str, str] = {}
    for group in ("sources",):
        for label, receipt in lock[group].items():
            output[f"{group}:{label}"] = _sha256_path(ROOT / receipt["path"])
    for label, receipt in lock["predecessor_v0_5_2"]["files"].items():
        output[f"predecessor_v0_5_2:{label}"] = _sha256_path(ROOT / receipt["path"])
    return output


def _payloads_from_bundle(
    bundle: Mapping[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    key = projection.public_treatment_key(bundle)
    rows = key["treatments"]
    if [row["treatment_id"] for row in rows] != list(CALL_ORDER):
        raise HostedBundleExecutionError("projection call order differs from lock")
    payloads: dict[str, dict[str, Any]] = {}
    blind_ids: dict[str, str] = {}
    for row in rows:
        arm = str(row["treatment_id"])
        blind_id = str(row["blinded_request_id"])
        payload = projection.provider_payload_for_blinded_id(bundle, blind_id)
        projection.validate_provider_payload(payload, exact_treatment=arm)
        if fingerprint(payload) != row["provider_payload_sha256"]:
            raise HostedBundleExecutionError("provider payload receipt drifted")
        payloads[arm] = payload
        blind_ids[arm] = blind_id
    if tuple(payloads) != CALL_ORDER:
        raise HostedBundleExecutionError("materialized payload order drifted")
    return payloads, blind_ids


def _expected_provider_provenance() -> dict[str, Any]:
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


def _build_preflight_record(
    *,
    lock: Mapping[str, Any],
    bundle: Mapping[str, Any],
    payloads: Mapping[str, Mapping[str, Any]],
    source_snapshot: Mapping[str, str],
    require_api_key: bool,
) -> dict[str, Any]:
    projection_checks = projection.self_test()
    if (
        projection_checks.get("status") != "PASS"
        or projection_checks.get("projection_fingerprint_sha256")
        != bundle.get("fingerprint_sha256")
    ):
        raise HostedBundleExecutionError("projection self-test did not pass")
    lineage_checks = lineage_preflight_self_test()
    if (
        lineage_checks.get("status") != "PASS"
        or lineage_checks.get("gold_loaded") is not False
    ):
        raise HostedBundleExecutionError("lineage self-test did not pass")
    provider_checks = provider_self_test()
    if provider_checks.get("status") != "PASS":
        raise HostedBundleExecutionError("provider self-test did not pass")
    transport_checks_raw = offline_transport_self_test(
        input_payload=payloads["P"],
        output_payload=sample_provider_output(False),
    )
    transport_checks = {
        "checks": _clone(transport_checks_raw["checks"]),
        "network_calls": transport_checks_raw["network_calls"],
        "provider_calls": transport_checks_raw["provider_calls"],
        "schema_version": transport_checks_raw["schema_version"],
        "simulated_api_calls": transport_checks_raw["simulated_api_calls"],
        "status": transport_checks_raw["status"],
    }
    if (
        transport_checks["status"] != "PASS"
        or transport_checks["network_calls"] != 0
        or transport_checks["provider_calls"] != 0
        or transport_checks["simulated_api_calls"] != 1
        or not all(transport_checks["checks"].values())
    ):
        raise HostedBundleExecutionError("provider fake transport self-test failed")
    expected_provenance = _expected_provider_provenance()
    if require_api_key:
        if not os.environ.get("OPENAI_API_KEY"):
            raise HostedBundleExecutionError("OPENAI_API_KEY is unavailable")
        # All five payloads exist before any provider object is constructed.
        providers = {arm: OpenAILineageProviderV0_6() for arm in CALL_ORDER}
        provenances = [provider.provenance for provider in providers.values()]
        if (
            len({canonical_json(value) for value in provenances}) != 1
            or provenances[0] != expected_provenance
        ):
            raise HostedBundleExecutionError("provider runtime differs across calls")
        if any(provider.audit_receipts for provider in providers.values()):
            raise HostedBundleExecutionError("preflight recorded a provider call")
    if (
        expected_provenance.get("instructions_fingerprint_sha256")
        != lock["instructions_fingerprint_sha256"]
        or expected_provenance.get("response_schema_fingerprint_sha256")
        != lock["response_schema_fingerprint_sha256"]
        or expected_provenance.get("model") != lock["runtime"]["model"]
        or expected_provenance.get("reasoning_effort")
        != lock["runtime"]["reasoning_effort"]
        or expected_provenance.get("max_output_tokens")
        != lock["runtime"]["max_output_tokens"]
        or expected_provenance.get("sdk_retries") != 0
    ):
        raise HostedBundleExecutionError("provider provenance differs from policy lock")
    return {
        "call_order": list(CALL_ORDER),
        "expected_api_attempts": 5,
        "lineage_self_test": lineage_checks,
        "payload_fingerprints": {
            arm: fingerprint(payloads[arm]) for arm in CALL_ORDER
        },
        "projection_self_test": projection_checks,
        "provider": expected_provenance,
        "provider_self_test": provider_checks,
        "provider_transport_self_test": transport_checks,
        "source_snapshot_sha256": dict(source_snapshot),
        "status": "READY",
    }


def _preflight_materialize(output: Path) -> dict[str, Any]:
    if output.exists():
        raise HostedBundleExecutionError(f"output already exists: {output}")
    if _staging_directory(output).exists():
        raise HostedBundleExecutionError(
            f"unresolved prior attempt journal exists: {_staging_directory(output)}"
        )
    lock = _load_lock()
    before = _source_snapshot(lock)
    bundle = projection.build_projection_bundle()
    payloads, blind_ids = _payloads_from_bundle(bundle)
    preflight_record = _build_preflight_record(
        lock=lock,
        bundle=bundle,
        payloads=payloads,
        source_snapshot=before,
        require_api_key=True,
    )
    after = _source_snapshot(lock)
    if after != before:
        raise HostedBundleExecutionError("locked sources changed during preflight")
    return {
        "blind_ids": blind_ids,
        "bundle": bundle,
        "lock": lock,
        "payloads": payloads,
        "preflight": preflight_record,
    }


def preflight(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    material = _preflight_materialize(output)
    return _clone(material["preflight"])


def _failure_record(error: Exception) -> dict[str, Any]:
    if isinstance(error, OpenAIProviderBoundaryError):
        return {
            "category": error.category,
            "exception_class": type(error).__name__,
            "phase": error.phase,
            "reason_code": error.reason_code,
        }
    reason_code = getattr(error, "reason_code", None)
    if isinstance(reason_code, str) and reason_code:
        return {
            "category": "local_lineage_contract_error",
            "exception_class": type(error).__name__,
            "phase": "local_output_contract",
            "reason_code": reason_code,
        }
    return {
        "category": "local_lineage_contract_error",
        "exception_class": type(error).__name__,
        "phase": "local_output_contract",
        "reason_code": "local_output_contract_unclassified",
    }


def _receipt_from_error(error: Exception) -> dict[str, Any] | None:
    receipt = getattr(error, "receipt", None)
    return None if receipt is None else receipt.to_dict()


def _journal_row(
    attempt: Mapping[str, Any],
    *,
    provider_output: Mapping[str, Any] | None,
    compiled_output: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return {
        "attempt": _clone(attempt),
        "compiled_output": _clone(compiled_output),
        "provider_output": _clone(provider_output),
        "schema_version": "ebrt-hosted-bundle-attempt-journal-v0.6.1",
    }


def _append_journal(path: Path, row: Mapping[str, Any]) -> None:
    raw = _canonical_bytes(row, trailing_newline=True)
    with path.open("ab") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def _freeze_receipt_guard_failure(
    path: Path,
    *,
    arm: str,
    blind_id: str,
    payload: Mapping[str, Any],
    receipt: Mapping[str, Any],
    run_position: int,
) -> None:
    """Durably record a receipt-integrity stop without normalizing bad bytes."""

    _append_journal(
        path,
        {
            "blinded_request_id": blind_id,
            "failure": {
                "category": "local_receipt_guard_error",
                "phase": "immediate_post_call_receipt_guard",
                "reason_code": "live_receipt_or_audit_mismatch",
            },
            "provider_input_fingerprint_sha256": fingerprint(payload),
            "receipt": _clone(receipt),
            "run_position": run_position,
            "schema_version": "ebrt-hosted-bundle-receipt-guard-stop-v0.6.1",
            "status": "IRRECOVERABLE_RECEIPT_GUARD_FAILURE",
            "treatment_id": arm,
        },
    )


def _validate_live_receipt(
    provider: OpenAILineageProviderV0_6,
    receipt: Mapping[str, Any],
    payload: Mapping[str, Any],
    *,
    provider_completed: bool,
    failure: Mapping[str, Any] | None,
) -> None:
    if provider.audit_receipts != [_clone(receipt)]:
        raise HostedBundleExecutionError("provider audit receipt differs from return")
    _validate_receipt(
        receipt,
        payload,
        provider_completed=provider_completed,
        failure=failure,
    )


def _journal_bytes(execution: Mapping[str, Any]) -> bytes:
    outputs = execution["provider_outputs"]
    compiled = execution["compiled_outputs"]
    return b"".join(
        _canonical_bytes(
            _journal_row(
                attempt,
                provider_output=outputs.get(attempt["treatment_id"]),
                compiled_output=compiled.get(attempt["treatment_id"]),
            ),
            trailing_newline=True,
        )
        for attempt in execution["attempts"]
    )


def _execute_gold_free(
    payloads: Mapping[str, Mapping[str, Any]],
    blind_ids: Mapping[str, str],
    *,
    journal_path: Path,
) -> dict[str, Any]:
    # This construction happens only after every payload has been materialized.
    providers = {arm: OpenAILineageProviderV0_6() for arm in CALL_ORDER}
    attempts: list[dict[str, Any]] = []
    compiled_by_arm: dict[str, dict[str, Any]] = {}
    output_by_arm: dict[str, dict[str, Any]] = {}
    for run_position, arm in enumerate(CALL_ORDER, start=1):
        payload = payloads[arm]
        provider = providers[arm]
        try:
            public_output, receipt = provider.generate(payload)
        except OpenAIProviderBoundaryError as error:
            receipt_value = _receipt_from_error(error)
            if receipt_value is None:
                raise HostedBundleExecutionError(
                    "provider boundary failure omitted its receipt"
                ) from None
            failure_value = _failure_record(error)
            try:
                _validate_live_receipt(
                    provider,
                    receipt_value,
                    payload,
                    provider_completed=False,
                    failure=failure_value,
                )
            except Exception:
                _freeze_receipt_guard_failure(
                    journal_path,
                    arm=arm,
                    blind_id=blind_ids[arm],
                    payload=payload,
                    receipt=receipt_value,
                    run_position=run_position,
                )
                raise HostedBundleExecutionError(
                    "live receipt guard failed; in-flight journal was frozen"
                ) from None
            attempt = {
                "blinded_request_id": blind_ids[arm],
                "failure": failure_value,
                "provider_input_fingerprint_sha256": fingerprint(payload),
                "receipt": receipt_value,
                "run_position": run_position,
                "status": "PROVIDER_BOUNDARY_ERROR",
                "treatment_id": arm,
            }
            attempts.append(attempt)
            _append_journal(
                journal_path,
                _journal_row(attempt, provider_output=None, compiled_output=None),
            )
            break

        receipt_value = receipt.to_dict()
        try:
            _validate_live_receipt(
                provider,
                receipt_value,
                payload,
                provider_completed=True,
                failure=None,
            )
        except Exception:
            _freeze_receipt_guard_failure(
                journal_path,
                arm=arm,
                blind_id=blind_ids[arm],
                payload=payload,
                receipt=receipt_value,
                run_position=run_position,
            )
            raise HostedBundleExecutionError(
                "live receipt guard failed; in-flight journal was frozen"
            ) from None
        try:
            compiled = validate_and_compile_output(public_output, payload)
        except Exception as error:
            attempt = {
                "blinded_request_id": blind_ids[arm],
                "failure": _failure_record(error),
                "provider_input_fingerprint_sha256": fingerprint(payload),
                "receipt": receipt_value,
                "run_position": run_position,
                "status": "LOCAL_OUTPUT_CONTRACT_ERROR",
                "treatment_id": arm,
            }
            attempts.append(attempt)
            _append_journal(
                journal_path,
                _journal_row(attempt, provider_output=None, compiled_output=None),
            )
            break

        public_output_value = _clone(public_output)
        compiled_value = _clone(compiled)
        attempt = {
            "blinded_request_id": blind_ids[arm],
            "compiled_output_fingerprint_sha256": compiled_value[
                "fingerprint_sha256"
            ],
            "provider_input_fingerprint_sha256": fingerprint(payload),
            "provider_output_fingerprint_sha256": fingerprint(public_output_value),
            "receipt": receipt_value,
            "run_position": run_position,
            "status": "COMPLETED",
            "treatment_id": arm,
        }
        attempts.append(attempt)
        compiled_by_arm[arm] = compiled_value
        output_by_arm[arm] = public_output_value
        _append_journal(
            journal_path,
            _journal_row(
                attempt,
                provider_output=public_output_value,
                compiled_output=compiled_value,
            ),
        )

    complete = (
        len(attempts) == len(CALL_ORDER)
        and [row["treatment_id"] for row in attempts] == list(CALL_ORDER)
        and all(row["status"] == "COMPLETED" for row in attempts)
    )
    return {
        "attempts": attempts,
        "compiled_outputs": compiled_by_arm,
        "provider_outputs": output_by_arm,
        "run_status": "COMPLETE" if complete else "INCOMPLETE",
        "unattempted_treatment_ids": list(CALL_ORDER[len(attempts) :]),
    }


def _grade_pass(value: Mapping[str, Any]) -> bool:
    return value.get("status") == "PASS"


def _output_diff(
    p_output: Mapping[str, Any], d_output: Mapping[str, Any]
) -> dict[str, Any]:
    def target_values(value: Mapping[str, Any]) -> dict[str, str]:
        return {
            str(row["slot"]): str(row["value"])
            for row in value.get("targets", [])
        }

    before = target_values(p_output)
    after = target_values(d_output)
    return {
        "answer": {
            "before": p_output.get("current_answer"),
            "after": d_output.get("current_answer"),
            "changed": p_output.get("current_answer")
            != d_output.get("current_answer"),
        },
        "claim": {
            "before": p_output.get("claim"),
            "after": d_output.get("claim"),
            "changed": p_output.get("claim") != d_output.get("claim"),
            "graded": False,
        },
        "targets": [
            {
                "slot": slot,
                "before": before.get(slot),
                "after": after.get(slot),
                "changed": before.get(slot) != after.get(slot),
            }
            for slot in sorted(set(before) | set(after))
        ],
    }


def _usage_summary(attempts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    fields = (
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cached_input_tokens",
        "cache_write_tokens",
        "reasoning_tokens",
    )
    totals = {field: 0 for field in fields}
    exact = True
    latency_ms = 0.0
    api_calls = 0
    logical_calls = 0
    for attempt in attempts:
        receipt = attempt["receipt"]
        usage = receipt["usage"]
        exact = exact and usage.get("exact_provider_tokens") is True
        for field in fields:
            value = usage.get(field)
            if value is None:
                exact = False
            else:
                totals[field] += int(value)
        latency_ms += float(receipt["latency_ms"])
        api_calls += int(receipt["api_calls"])
        logical_calls += int(receipt["logical_calls"])
    return {
        "api_calls": api_calls,
        "exact_provider_tokens": exact,
        "latency_ms": latency_ms,
        "logical_calls": logical_calls,
        **totals,
    }


def _effect_status(grades: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    d_pass = _grade_pass(grades["D"])
    contrasts: dict[str, str] = {}
    for arm in ("A", "B", "C"):
        comparator_pass = _grade_pass(grades[arm])
        contrasts[f"D_vs_{arm}"] = (
            "POSITIVE"
            if d_pass and not comparator_pass
            else "NEGATIVE"
            if not d_pass and comparator_pass
            else "NULL"
        )
    return {
        "primary": contrasts["D_vs_C"],
        "primary_contrast": "D_vs_C_matched_placement",
        "contrasts": contrasts,
    }


def _finalize(
    execution: Mapping[str, Any],
    *,
    bundle: Mapping[str, Any],
    preflight_value: Mapping[str, Any],
    source_snapshot: Mapping[str, str],
) -> dict[str, Any]:
    complete = execution["run_status"] == "COMPLETE"
    grades: dict[str, Any] = {}
    stale_grade: dict[str, Any] | None = None
    output_diff: dict[str, Any] | None = None
    if complete:
        # This is the first semantic parse of the locked v0.6 gold bytes.
        gold = load_gold(GOLD_PATH)
        compiled = execution["compiled_outputs"]
        grades["P"] = grade_p_pre_event(compiled["P"], gold)
        for arm in ("A", "B", "D", "C"):
            grades[arm] = grade_post_event(compiled[arm], gold)
        stale_grade = grade_p_stale(compiled["P"], gold)
        output_diff = _output_diff(
            execution["provider_outputs"]["P"],
            execution["provider_outputs"]["D"],
        )

    p_status = grades.get("P", {}).get("status", "NOT_ASSESSED")
    stale_status = (
        "NOT_ASSESSED" if stale_grade is None else stale_grade.get("status", "FAIL")
    )
    d_grade = grades.get("D")
    d_strict = "NOT_ASSESSED" if d_grade is None else d_grade.get("status", "FAIL")
    surrogate_status = (
        "PASS"
        if bundle.get("source_gate", {}).get("status") == "PASS"
        and bundle.get("ready_for_live_lock") is True
        else "FAIL"
    )
    effect = (
        {
            "primary": "NOT_ASSESSED",
            "primary_contrast": "D_vs_C_matched_placement",
            "contrasts": {},
        }
        if not complete
        else _effect_status(grades)
    )
    promote = (
        complete
        and p_status == "PASS"
        and stale_status == "PASS"
        and d_strict == "PASS"
        and surrogate_status == "PASS"
    )
    decision_status = (
        "PROMOTE_V0_7_HOSTED_BUNDLE_GATE"
        if promote
        else (
            "HOLD_V0_6_HOSTED_BUNDLE_GATE_INCOMPLETE"
            if not complete
            else "HOLD_V0_6_HOSTED_BUNDLE_GATE"
        )
    )
    result = {
        "call_order": list(CALL_ORDER),
        "claim_boundary": list(CLAIM_BOUNDARY),
        "decision": {
            "d_strict_status": d_strict,
            "decision_status": decision_status,
            "effect_by_comparator": effect["contrasts"],
            "effect_primary_contrast": effect["primary_contrast"],
            "effect_status": effect["primary"],
            "p_pre_event_status": p_status,
            "p_stale_status": stale_status,
            "promotion_ready": promote,
            "run_status": execution["run_status"],
            "surrogate_status": surrogate_status,
        },
        "effect_boundary": (
            "Observational exact-endpoint label over one fixed unbalanced, "
            "time-confounded contaminated block; never a causal estimate."
        ),
        "execution": _clone(execution),
        "grades": grades,
        "lineage_gold_loaded_after_attempts": complete,
        "mode": "openai_live_hosted_bundle_v0_6_1",
        "output_diff_p_to_d": output_diff,
        "preflight": _clone(preflight_value),
        "projection_fingerprint_sha256": bundle["fingerprint_sha256"],
        "public_claim_status": "UNGRADED_PUBLIC_TEXT",
        "schema_version": SCHEMA_VERSION,
        "source_snapshot_sha256": dict(source_snapshot),
        "stale_regrade": stale_grade,
        "usage": _usage_summary(execution["attempts"]),
    }
    return _seal(result)


def _calls_bytes(result: Mapping[str, Any]) -> bytes:
    rows = []
    for attempt in result["execution"]["attempts"]:
        rows.append(
            {
                "blinded_request_id": attempt["blinded_request_id"],
                "failure": _clone(attempt.get("failure")),
                "receipt": attempt["receipt"],
                "run_position": attempt["run_position"],
                "schema_version": CALLS_SCHEMA_VERSION,
                "status": attempt["status"],
                "treatment_id": attempt["treatment_id"],
            }
        )
    return b"".join(_canonical_bytes(row, trailing_newline=True) for row in rows)


def _provider_inputs_artifact(
    payloads: Mapping[str, Mapping[str, Any]], blind_ids: Mapping[str, str]
) -> dict[str, Any]:
    return _seal(
        {
            "call_order": list(CALL_ORDER),
            "payloads": [
                {
                    "blinded_request_id": blind_ids[arm],
                    "payload": _clone(payloads[arm]),
                    "provider_payload_sha256": fingerprint(payloads[arm]),
                    "treatment_id": arm,
                }
                for arm in CALL_ORDER
            ],
            "schema_version": PROVIDER_INPUTS_SCHEMA_VERSION,
        }
    )


def _report(result: Mapping[str, Any]) -> str:
    decision = result["decision"]
    lines = [
        "# EBRT v0.6.1 Hosted Bundle Execution",
        "",
        f"Decision: **{decision['decision_status']}**",
        "",
        "## Independent endpoints",
        "",
        "| Endpoint | Status |",
        "| --- | --- |",
        f"| Run | {decision['run_status']} |",
        f"| P pre-event | {decision['p_pre_event_status']} |",
        f"| P stale regrade | {decision['p_stale_status']} |",
        f"| Public surrogate | {decision['surrogate_status']} |",
        f"| D strict hosted path | {decision['d_strict_status']} |",
        f"| Observational effect | {decision['effect_status']} |",
        "",
        "## Calls",
        "",
        "| Pos | Arm | Status | Answer | Strict grade | API calls | Tokens | Latency ms |",
        "| ---: | --- | --- | --- | --- | ---: | ---: | ---: |",
    ]
    outputs = result["execution"]["provider_outputs"]
    grades = result["grades"]
    for attempt in result["execution"]["attempts"]:
        arm = attempt["treatment_id"]
        usage = attempt["receipt"]["usage"]
        lines.append(
            "| {pos} | {arm} | {status} | {answer} | {grade} | {calls} | {tokens} | {latency:.3f} |".format(
                pos=attempt["run_position"],
                arm=arm,
                status=attempt["status"],
                answer=outputs.get(arm, {}).get("current_answer", "n/a"),
                grade=grades.get(arm, {}).get("status", "NOT_ASSESSED"),
                calls=attempt["receipt"]["api_calls"],
                tokens=usage.get("total_tokens", "n/a"),
                latency=float(attempt["receipt"]["latency_ms"]),
            )
        )
    lines.extend(
        [
            "",
            "## Claim boundary",
            "",
            *[f"- {claim}" for claim in result["claim_boundary"]],
            "",
        ]
    )
    return "\n".join(lines)


def _manifest_value(
    *,
    files: Mapping[str, bytes],
    result: Mapping[str, Any],
    lock: Mapping[str, Any],
) -> dict[str, Any]:
    return _seal(
        {
            "artifacts": {
                name: {"bytes": len(raw), "sha256": _sha256_bytes(raw)}
                for name, raw in files.items()
            },
            "call_order": list(CALL_ORDER),
            "claim_boundary": list(CLAIM_BOUNDARY),
            "decision_status": result["decision"]["decision_status"],
            "policy_lock_fingerprint_sha256": lock["fingerprint_sha256"],
            "result_fingerprint_sha256": result["fingerprint_sha256"],
            "runtime": _runtime(),
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "source_snapshot_sha256": result["source_snapshot_sha256"],
        }
    )


def _materialize(
    result: Mapping[str, Any],
    *,
    payloads: Mapping[str, Mapping[str, Any]],
    blind_ids: Mapping[str, str],
    bundle: Mapping[str, Any],
    lock: Mapping[str, Any],
    journal_bytes: bytes,
) -> dict[str, bytes]:
    provider_inputs = _provider_inputs_artifact(payloads, blind_ids)
    files: dict[str, bytes] = {
        "result.json": _pretty_bytes(result),
        "calls.jsonl": _calls_bytes(result),
        "attempt_journal.jsonl": journal_bytes,
        "provider_inputs.json": _pretty_bytes(provider_inputs),
        "projection_bundle.json": _pretty_bytes(bundle),
        "report.md": _report(result).encode("utf-8"),
    }
    manifest = _manifest_value(
        files=files,
        result=result,
        lock=lock,
    )
    files["manifest.json"] = _pretty_bytes(manifest)
    return files


def _publish(output: Path, files: Mapping[str, bytes]) -> None:
    if output.exists():
        raise HostedBundleExecutionError(f"output already exists: {output}")
    if set(files) != set(ARTIFACT_FILES):
        raise HostedBundleExecutionError("artifact file set drifted before publish")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        for name in ARTIFACT_FILES:
            path = temporary / name
            path.write_bytes(files[name])
            with path.open("rb") as handle:
                os.fsync(handle.fileno())
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def run_live(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    material = _preflight_materialize(output)
    lock = material["lock"]
    source_before = _source_snapshot(lock)
    staging = _staging_directory(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging.mkdir(mode=0o700)
    plan = _seal(
        {
            "call_order": list(CALL_ORDER),
            "payload_fingerprints": material["preflight"]["payload_fingerprints"],
            "policy_lock_fingerprint_sha256": lock["fingerprint_sha256"],
            "projection_fingerprint_sha256": material["bundle"][
                "fingerprint_sha256"
            ],
            "schema_version": "ebrt-hosted-bundle-inflight-plan-v0.6.1",
            "source_snapshot_sha256": source_before,
            "status": "IRREVERSIBLE_CALL_BLOCK_NOT_YET_STARTED",
        }
    )
    plan_path = staging / "plan.json"
    plan_path.write_bytes(_pretty_bytes(plan))
    with plan_path.open("rb") as handle:
        os.fsync(handle.fileno())
    journal_path = staging / "attempt_journal.jsonl"
    journal_path.touch(mode=0o600)
    execution = _execute_gold_free(
        material["payloads"],
        material["blind_ids"],
        journal_path=journal_path,
    )
    journal_bytes = journal_path.read_bytes()
    if journal_bytes != _journal_bytes(execution):
        raise HostedBundleExecutionError("durable attempt journal drifted")
    source_after = _source_snapshot(lock)
    if source_after != source_before:
        raise HostedBundleExecutionError("locked sources changed during live execution")
    result = _finalize(
        execution,
        bundle=material["bundle"],
        preflight_value=material["preflight"],
        source_snapshot=source_before,
    )
    files = _materialize(
        result,
        payloads=material["payloads"],
        blind_ids=material["blind_ids"],
        bundle=material["bundle"],
        lock=lock,
        journal_bytes=journal_bytes,
    )
    _publish(output, files)
    validate_bundle(output)
    shutil.rmtree(staging)
    return {
        "artifact_directory": str(output),
        "decision_status": result["decision"]["decision_status"],
        "effect_status": result["decision"]["effect_status"],
        "result_fingerprint_sha256": result["fingerprint_sha256"],
        "run_status": result["decision"]["run_status"],
        "usage": result["usage"],
    }


def _validate_receipt(
    receipt: Mapping[str, Any],
    payload: Mapping[str, Any],
    *,
    provider_completed: bool,
    failure: Mapping[str, Any] | None,
) -> None:
    required = {
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
    if set(receipt) != required:
        raise HostedBundleExecutionError("provider receipt schema drifted")
    if (
        receipt["provider"] != "openai_responses"
        or receipt["requested_model"] != MODEL
        or receipt["logical_calls"] != 1
        or receipt["api_calls"] != 1
        or receipt["request_fingerprint"] != fingerprint(payload)
        or receipt["prompt_fingerprint"] != INSTRUCTIONS_FINGERPRINT_SHA256
        or not isinstance(receipt["latency_ms"], (int, float))
        or float(receipt["latency_ms"]) < 0.0
    ):
        raise HostedBundleExecutionError("provider receipt binding drifted")
    metadata = receipt["metadata"]
    metadata_keys = {
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
    response_schema_fingerprint = fingerprint(
        ProviderLineageOutput.model_json_schema()
    )
    expected_semantic_protocol = fingerprint(
        {
            "model": MODEL,
            "instructions_fingerprint": INSTRUCTIONS_FINGERPRINT_SHA256,
            "input_fingerprint": fingerprint(payload),
            "text_schema_fingerprint": response_schema_fingerprint,
            "reasoning": {"effort": REASONING_EFFORT},
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "store": False,
            "service_tier": "default",
            "truncation": "disabled",
            "timeout_seconds": TIMEOUT_SECONDS,
        }
    )
    if not isinstance(metadata, Mapping) or set(metadata) != metadata_keys or (
        metadata.get("receipt_schema_version") != RECEIPT_SCHEMA_VERSION
        or metadata.get("attempt") != 1
        or metadata.get("retry_count") != 0
        or metadata.get("reasoning_effort") != REASONING_EFFORT
        or metadata.get("max_output_tokens") != MAX_OUTPUT_TOKENS
        or metadata.get("store") is not False
        or metadata.get("previous_response_id") is not False
        or metadata.get("truncation") != "disabled"
        or metadata.get("sdk_version") != importlib.metadata.version("openai")
        or metadata.get("pydantic_version")
        != importlib.metadata.version("pydantic")
        or metadata.get("python_version") != sys.version.split()[0]
        or metadata.get("api_call_count_semantics") != "attempted_client_call"
        or metadata.get("response_schema_fingerprint")
        != response_schema_fingerprint
        or metadata.get("semantic_protocol_fingerprint")
        != expected_semantic_protocol
        or not _is_sha256(metadata.get("client_request_id_sha256"))
    ):
        raise HostedBundleExecutionError("provider receipt runtime drifted")
    usage = receipt["usage"]
    if not isinstance(usage, Mapping):
        raise HostedBundleExecutionError("provider usage missing")
    if provider_completed:
        if (
            receipt["returned_model"] != MODEL
            or usage.get("exact_provider_tokens") is not True
            or metadata.get("attempt_outcome") != "completed"
            or metadata.get("service_tier") != "default"
            or metadata.get("http_observed") is not True
            or metadata.get("http_status_code") != 200
            or metadata.get("parse_boundary") != "succeeded"
            or not _is_sha256(metadata.get("response_id_sha256"))
            or not _is_sha256(metadata.get("server_request_id_sha256"))
            or not _is_sha256(metadata.get("provider_body_sha256"))
            or not isinstance(metadata.get("provider_body_byte_count"), int)
            or metadata.get("provider_body_byte_count", 0) <= 0
            or metadata.get("failure_phase") is not None
            or metadata.get("failure_reason_code") is not None
            or metadata.get("failure_type") is not None
            or metadata.get("refusal_count") != 0
        ):
            raise HostedBundleExecutionError("completed receipt contract drifted")
    else:
        if not isinstance(failure, Mapping) or set(failure) != {
            "category",
            "exception_class",
            "phase",
            "reason_code",
        }:
            raise HostedBundleExecutionError("provider failure record drifted")
        phase = failure["phase"]
        reason = failure["reason_code"]
        if (
            failure["category"] != "provider_boundary_error"
            or failure["exception_class"] != "OpenAIProviderBoundaryError"
            or phase not in BOUNDARY_REASON_CODES_BY_PHASE
            or reason not in BOUNDARY_REASON_CODES_BY_PHASE[phase]
            or metadata.get("failure_phase") != phase
            or metadata.get("failure_reason_code") != reason
            or metadata.get("failure_type") != reason
            or metadata.get("attempt_outcome") == "completed"
        ):
            raise HostedBundleExecutionError("provider failure/receipt mismatch")
    for key, value in usage.items():
        if key == "exact_provider_tokens":
            continue
        if value is not None and (not isinstance(value, int) or value < 0):
            raise HostedBundleExecutionError("provider usage value drifted")


def _read_artifact_directory(output: Path) -> dict[str, bytes]:
    if not output.is_dir() or output.is_symlink():
        raise HostedBundleExecutionError(f"artifact directory unavailable: {output}")
    observed = []
    for path in output.rglob("*"):
        if path.is_symlink():
            raise HostedBundleExecutionError("artifact contains a symlink")
        if path.is_file():
            observed.append(str(path.relative_to(output)))
    if sorted(observed) != sorted(ARTIFACT_FILES):
        raise HostedBundleExecutionError("artifact recursive file set drifted")
    return {name: (output / name).read_bytes() for name in ARTIFACT_FILES}


def _load_json_bytes(raw: bytes, label: str) -> dict[str, Any]:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="ebrt-v060-validate-", suffix=".json", delete=False
        ) as handle:
            handle.write(raw)
            temporary_path = Path(handle.name)
        return _strict_load(temporary_path)
    except HostedBundleExecutionError as exc:
        raise HostedBundleExecutionError(f"invalid artifact JSON: {label}") from exc
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def validate_bundle(output: Path = DEFAULT_OUTPUT) -> None:
    lock = _load_lock()
    files = _read_artifact_directory(output)
    manifest = _load_json_bytes(files["manifest.json"], "manifest.json")
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise HostedBundleExecutionError("manifest schema drifted")
    if manifest.get("fingerprint_sha256") != fingerprint(
        {key: _clone(value) for key, value in manifest.items() if key != "fingerprint_sha256"}
    ):
        raise HostedBundleExecutionError("manifest fingerprint drifted")
    if manifest.get("policy_lock_fingerprint_sha256") != lock["fingerprint_sha256"]:
        raise HostedBundleExecutionError("manifest policy lock drifted")
    expected_non_manifest = set(ARTIFACT_FILES) - {"manifest.json"}
    if set(manifest.get("artifacts", {})) != expected_non_manifest:
        raise HostedBundleExecutionError("manifest artifact table drifted")
    for name in expected_non_manifest:
        receipt = manifest["artifacts"][name]
        if receipt != {
            "bytes": len(files[name]),
            "sha256": _sha256_bytes(files[name]),
        }:
            raise HostedBundleExecutionError(f"artifact hash drifted: {name}")

    result = _load_json_bytes(files["result.json"], "result.json")
    provider_inputs = _load_json_bytes(
        files["provider_inputs.json"], "provider_inputs.json"
    )
    bundle = _load_json_bytes(files["projection_bundle.json"], "projection_bundle.json")
    projection.validate_projection_bundle(bundle, exact_rederive=False)
    expected_result_keys = {
        "call_order",
        "claim_boundary",
        "decision",
        "effect_boundary",
        "execution",
        "fingerprint_sha256",
        "grades",
        "lineage_gold_loaded_after_attempts",
        "mode",
        "output_diff_p_to_d",
        "preflight",
        "projection_fingerprint_sha256",
        "public_claim_status",
        "schema_version",
        "source_snapshot_sha256",
        "stale_regrade",
        "usage",
    }
    if set(result) != expected_result_keys:
        raise HostedBundleExecutionError("result root schema drifted")
    if result.get("fingerprint_sha256") != fingerprint(
        {key: _clone(value) for key, value in result.items() if key != "fingerprint_sha256"}
    ):
        raise HostedBundleExecutionError("result fingerprint drifted")
    if (
        result.get("schema_version") != SCHEMA_VERSION
        or result.get("claim_boundary") != list(CLAIM_BOUNDARY)
        or result.get("call_order") != list(CALL_ORDER)
        or result.get("projection_fingerprint_sha256")
        != bundle.get("fingerprint_sha256")
        or result.get("public_claim_status") != "UNGRADED_PUBLIC_TEXT"
    ):
        raise HostedBundleExecutionError("result identity drifted")
    if provider_inputs.get("fingerprint_sha256") != fingerprint(
        {
            key: _clone(value)
            for key, value in provider_inputs.items()
            if key != "fingerprint_sha256"
        }
    ):
        raise HostedBundleExecutionError("provider inputs fingerprint drifted")
    if (
        provider_inputs.get("schema_version") != PROVIDER_INPUTS_SCHEMA_VERSION
        or provider_inputs.get("call_order") != list(CALL_ORDER)
    ):
        raise HostedBundleExecutionError("provider inputs identity drifted")

    payloads: dict[str, Mapping[str, Any]] = {}
    blind_ids: dict[str, str] = {}
    rows = provider_inputs.get("payloads")
    if not isinstance(rows, list) or [row.get("treatment_id") for row in rows] != list(
        CALL_ORDER
    ):
        raise HostedBundleExecutionError("provider inputs order drifted")
    for row in rows:
        arm = row["treatment_id"]
        payload = row["payload"]
        if row.get("provider_payload_sha256") != fingerprint(payload):
            raise HostedBundleExecutionError("provider input receipt drifted")
        projection.validate_provider_payload(payload, exact_treatment=arm)
        payloads[arm] = payload
        blind_ids[arm] = row["blinded_request_id"]
    bundle_payloads, bundle_blinds = _payloads_from_bundle(bundle)
    if (
        canonical_json(payloads) != canonical_json(bundle_payloads)
        or blind_ids != bundle_blinds
    ):
        raise HostedBundleExecutionError("provider inputs differ from projection")
    expected_preflight = _build_preflight_record(
        lock=lock,
        bundle=bundle,
        payloads=payloads,
        source_snapshot=_source_snapshot(lock),
        require_api_key=False,
    )
    if canonical_json(result.get("preflight")) != canonical_json(expected_preflight):
        raise HostedBundleExecutionError("preflight record was not independently derived")

    execution = result.get("execution")
    if not isinstance(execution, Mapping) or set(execution) != {
        "attempts",
        "compiled_outputs",
        "provider_outputs",
        "run_status",
        "unattempted_treatment_ids",
    }:
        raise HostedBundleExecutionError("execution record missing")
    attempts = execution.get("attempts")
    if (
        not isinstance(attempts, list)
        or not attempts
        or len(attempts) > len(CALL_ORDER)
    ):
        raise HostedBundleExecutionError("attempt ledger malformed")
    if [row.get("treatment_id") for row in attempts] != list(CALL_ORDER[: len(attempts)]):
        raise HostedBundleExecutionError("attempt order drifted")
    if [row.get("run_position") for row in attempts] != list(
        range(1, len(attempts) + 1)
    ):
        raise HostedBundleExecutionError("attempt position drifted")
    recomputed_compiled: dict[str, Any] = {}
    outputs = execution.get("provider_outputs")
    stored_compiled = execution.get("compiled_outputs")
    if not isinstance(outputs, Mapping) or not isinstance(stored_compiled, Mapping):
        raise HostedBundleExecutionError("execution output maps malformed")
    allowed_statuses = {
        "COMPLETED",
        "LOCAL_OUTPUT_CONTRACT_ERROR",
        "PROVIDER_BOUNDARY_ERROR",
    }
    if any(attempt.get("status") not in allowed_statuses for attempt in attempts):
        raise HostedBundleExecutionError("attempt status unknown")
    if any(attempt.get("status") != "COMPLETED" for attempt in attempts[:-1]):
        raise HostedBundleExecutionError("execution continued after a failed attempt")
    if len(attempts) < len(CALL_ORDER) and attempts[-1].get("status") == "COMPLETED":
        raise HostedBundleExecutionError("incomplete attempt prefix lacks terminal failure")
    completed_keys = {
        "blinded_request_id",
        "compiled_output_fingerprint_sha256",
        "provider_input_fingerprint_sha256",
        "provider_output_fingerprint_sha256",
        "receipt",
        "run_position",
        "status",
        "treatment_id",
    }
    failed_keys = {
        "blinded_request_id",
        "failure",
        "provider_input_fingerprint_sha256",
        "receipt",
        "run_position",
        "status",
        "treatment_id",
    }
    for attempt in attempts:
        arm = attempt["treatment_id"]
        status = attempt["status"]
        completed = status == "COMPLETED"
        if set(attempt) != (completed_keys if completed else failed_keys):
            raise HostedBundleExecutionError("attempt schema drifted")
        failure = attempt.get("failure")
        provider_completed = status in {"COMPLETED", "LOCAL_OUTPUT_CONTRACT_ERROR"}
        _validate_receipt(
            attempt["receipt"],
            payloads[arm],
            provider_completed=provider_completed,
            failure=None if completed else failure,
        )
        if status == "LOCAL_OUTPUT_CONTRACT_ERROR":
            if not isinstance(failure, Mapping) or set(failure) != {
                "category",
                "exception_class",
                "phase",
                "reason_code",
            } or (
                failure["category"] != "local_lineage_contract_error"
                or failure["phase"] != "local_output_contract"
                or not isinstance(failure["reason_code"], str)
                or not failure["reason_code"]
            ):
                raise HostedBundleExecutionError("local contract failure drifted")
        if attempt.get("blinded_request_id") != blind_ids[arm] or attempt.get(
            "provider_input_fingerprint_sha256"
        ) != fingerprint(payloads[arm]):
            raise HostedBundleExecutionError("attempt phase binding drifted")
        if completed:
            if arm not in outputs or arm not in stored_compiled:
                raise HostedBundleExecutionError("completed attempt output missing")
            if attempt.get("provider_output_fingerprint_sha256") != fingerprint(
                outputs[arm]
            ):
                raise HostedBundleExecutionError("provider output fingerprint drifted")
            compiled = validate_and_compile_output(outputs[arm], payloads[arm])
            if canonical_json(compiled) != canonical_json(stored_compiled[arm]):
                raise HostedBundleExecutionError("compiled output drifted")
            if attempt.get("compiled_output_fingerprint_sha256") != compiled[
                "fingerprint_sha256"
            ]:
                raise HostedBundleExecutionError("compiled output receipt drifted")
            recomputed_compiled[arm] = compiled
        elif arm in outputs or arm in stored_compiled:
            raise HostedBundleExecutionError("failed attempt retained accepted output")
    completed_arms = [row["treatment_id"] for row in attempts if row["status"] == "COMPLETED"]
    if set(outputs) != set(completed_arms) or set(stored_compiled) != set(completed_arms):
        raise HostedBundleExecutionError("execution output set drifted")
    if execution.get("unattempted_treatment_ids") != list(CALL_ORDER[len(attempts) :]):
        raise HostedBundleExecutionError("unattempted treatment set drifted")
    complete = len(attempts) == len(CALL_ORDER) and all(
        row["status"] == "COMPLETED" for row in attempts
    )
    if execution.get("run_status") != ("COMPLETE" if complete else "INCOMPLETE"):
        raise HostedBundleExecutionError("run status drifted")

    canonical_execution = _clone(execution)
    canonical_execution["compiled_outputs"] = recomputed_compiled
    expected_result = _finalize(
        canonical_execution,
        bundle=bundle,
        preflight_value=expected_preflight,
        source_snapshot=_source_snapshot(lock),
    )
    if canonical_json(expected_result) != canonical_json(result):
        raise HostedBundleExecutionError("result grades, status, or decision drifted")
    if files["calls.jsonl"] != _calls_bytes(result):
        raise HostedBundleExecutionError("calls ledger drifted")
    if files["attempt_journal.jsonl"] != _journal_bytes(result["execution"]):
        raise HostedBundleExecutionError("attempt journal drifted")
    if files["report.md"] != _report(result).encode("utf-8"):
        raise HostedBundleExecutionError("mechanism report drifted")
    if manifest.get("result_fingerprint_sha256") != result["fingerprint_sha256"]:
        raise HostedBundleExecutionError("manifest result binding drifted")
    if manifest.get("source_snapshot_sha256") != result["source_snapshot_sha256"]:
        raise HostedBundleExecutionError("manifest source snapshot drifted")
    expected_manifest = _manifest_value(
        files={
            name: files[name]
            for name in ARTIFACT_FILES
            if name != "manifest.json"
        },
        result=result,
        lock=lock,
    )
    if canonical_json(manifest) != canonical_json(expected_manifest):
        raise HostedBundleExecutionError("manifest was not independently reconstructed")


def _print_json(value: Mapping[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("emit-lock")
    preflight_parser = subparsers.add_parser("preflight")
    preflight_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    run_parser = subparsers.add_parser("run-live")
    run_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    subparsers.add_parser("component-self-test")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "emit-lock":
        _print_json(policy_lock_material())
    elif args.command == "preflight":
        _print_json(preflight(args.output))
    elif args.command == "run-live":
        _print_json(run_live(args.output))
    elif args.command == "validate":
        validate_bundle(args.output)
        _print_json({"artifact_directory": str(args.output), "status": "VALID"})
    elif args.command == "component-self-test":
        _print_json(
            {
                "lineage": lineage_preflight_self_test(),
                "projection": projection.self_test(),
                "provider": provider_self_test(),
                "status": "PASS",
            }
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
