#!/usr/bin/env python3
"""Pure-stdlib verifier for the frozen EBRT v0.6.3.1 live-r01 result.

This verifier intentionally does not import the producer, OpenAI, Pydantic, or
Torch, and it never invokes Git or the network.  It validates both the frozen
byte receipts and the public relationships that make the four-call result
auditable from a copied artifact directory.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_ARTIFACT = ROOT / "artifacts" / "actuator_uptake_canary_v0_6_3_1_live_r01"
DEFAULT_LOCK = ROOT / "policy_lock_actuator_uptake_canary_v0_6_3_1_live_r01.json"

EXPECTED_FILES: dict[str, tuple[int, str]] = {
    "attempt_journal.jsonl": (
        17125,
        "a2906c67f3173d886b1a7da6d8e16fdf9fca9edcee04ce18da0d3f3f2991a521",
    ),
    "calls.jsonl": (
        7493,
        "c0e94cf1c05f3bd60f503fcc77801f20b6edea3b557d3df3f5d59580211a5e1a",
    ),
    "manifest.json": (
        3826,
        "23304291a8b8be4f4d93e30e6e461bfd3fe6981976886816170bf90d5006932c",
    ),
    "projection_bundle.json": (
        17512,
        "a87de8b219d7d5f27eade5122f919483d9653948a037929e21b3417c1964e62a",
    ),
    "provider_inputs.json": (
        14589,
        "dd2ce281ea5ae08b809980a89c459feb93c1105d7e872288fcd2edff4379ade9",
    ),
    "report.md": (
        1671,
        "21eac17967da804013633ca488aca380ad6a480f84618f5350c9b338af9dc470",
    ),
    "result.json": (
        33159,
        "0ffa875e76f325ee7b3508915a5a52b05b4cbffab07f50efcd9263142da0ec7b",
    ),
}
EXPECTED_LOCK_BYTES = 8324
EXPECTED_LOCK_SHA256 = (
    "92868fdf1e07442cab4de5c1f15a6df69691d5904c2dfec9d80896f22523d295"
)
EXPECTED_LOCK_FINGERPRINT = (
    "7f15e08202b3e77a025f82644c04883819d2049d616461a1b07b5cddc637ea66"
)
EXPECTED_RESULT_FINGERPRINT = (
    "131d64dfe74b99912d5e39b0fdd13d17c69eca0d1361b27a48e75887ec25b8e2"
)
EXPECTED_MANIFEST_FINGERPRINT = (
    "cc90cb304ee150d07dcece9e8c8b37a015783ecd9e9ee61b8c803995c9dfe743"
)
EXPECTED_PROVIDER_INPUTS_FINGERPRINT = (
    "7322a50ae0adb45932dd1114f799fc2f78c707ae48849f49aa45abae7e5aa422"
)
EXPECTED_PROJECTION_FINGERPRINT = (
    "65af77712b529bb028aeae22e3eba5d6d943b0299a0b2951758445afcfe83216"
)
EXPECTED_AUTHORIZATION_TAG_OBJECT = "621d6ce5aca04629eefd1f0189635ee84b62e8da"
EXPECTED_AUTHORIZED_COMMIT = "35b84895acb63298a8459dba1e9f3f2a47f4de0f"
EXPECTED_PREFLIGHT_TAG_OBJECT = "ea987355a1f720aa0859f6ad92f874cf21d0fbe5"
EXPECTED_PREFLIGHT_COMMIT = "c5e1244055e5d7f83493698119549c49df718ed7"

EXECUTION_ORDER = ("C", "X", "D", "Z")
BLINDED_IDS = (
    "Q_00b33f7ff9377f35",
    "Q_0289fe8cd42f35a6",
    "Q_f4fc36504480840b",
    "Q_10b2215b1c3170c8",
)
PAYLOAD_FINGERPRINTS = (
    "b15bf97b3d7d6923a698f1c18ce9ba20a95580ac4a21cf9720c21efdcd856b86",
    "56203eff435b9116cea3b7c11dd3ae4ca8b954c14f662d6804cf891f8d73d854",
    "3364d976db8b4c1406c25a1fbe378f447b605e092714ac7975623f946a68fab6",
    "7111067bc34b8ba4b8035edb534d566c71b2f86d981cdf1799de9424ceb09b53",
)
SELECTED_CLOSURES = (
    "K_5c1377f2fc",
    "K_ba42ee466f",
    "K_ba42ee466f",
    "K_f41cb3914f",
)
PROVIDER_OUTPUT_FINGERPRINTS = (
    "b2b4e123551de5ac1eec45f1eb04cf5bcc9e23f19d3279698dd384f74728dacc",
    "e80599888ebdbfca797a140f5e1b1d79abf04389270750789f859577fe890347",
    "77bf6bae708092a90f4784949c1ed6c2dba8503e14fd9c7a1e6504a995cae398",
    "79400328937c24abd23e5f220a3034cc76968dabb7ab8f9f3a429eb7876682cc",
)
COMPILED_OUTPUT_FINGERPRINTS = (
    "467619ce1a53256a7f5b6b16af0b12351478f73083b79c04489d55c421bdc930",
    "35f30664c0ec80d33d7096ac9a9a43cd95293c8f15851c8a0193de28809b0afd",
    "fddf0e15f006235093c75f51f8bb1bc99ca73cd0b9d668b972b0964394f521b7",
    "26521a76d7b8413ebbe9457631b7ecfef7aab7e5ff7dfef89cf83267618d99cf",
)
ENDPOINT_FINGERPRINTS = {
    "C": "958bcc70e40c29909915f56a9600ba7210069dc3d99ade50b1588f9175262ee9",
    "D": "9f91c3279e04de80abb9c53f361f58b985d41fcf695ce3888725bab19d908be5",
    "X": "f7c891f56940b39617932172b8f6c4be4ec374e7aad9a2cf056f7ef72977770b",
    "Z": "70b376359c39e01f5bdd60a2cb099cc37228968454d54c80c352eaa0142f0437",
}

RESULT_SCHEMA = "ebrt-actuator-uptake-live-result-v0.6.3.1-r01"
CALL_SCHEMA = "ebrt-actuator-uptake-live-call-v0.6.3.1-r01"
JOURNAL_SCHEMA = "ebrt-actuator-uptake-live-journal-v0.6.3.1-r01"
INPUTS_SCHEMA = "ebrt-actuator-uptake-live-inputs-v0.6.3.1-r01"
MANIFEST_SCHEMA = "ebrt-actuator-uptake-live-manifest-v0.6.3.1-r01"
PROVIDER_INPUT_SCHEMA = "ebrt-actuator-uptake-provider-input-v0.6.3.1"
PROVIDER_OUTPUT_SCHEMA = "ebrt-actuator-uptake-provider-output-v0.6.3.1"
COMPILED_SCHEMA = "ebrt-actuator-uptake-compiled-output-v0.6.3.1"
CHECKPOINT = "archive_gate_revision_c:post_event"

FORBIDDEN_PROVIDER_METADATA = frozenset(
    {
        "anti_placement",
        "arm",
        "arm_id",
        "closure_roles",
        "controller",
        "correct_answer",
        "expected_answer",
        "gold",
        "grade",
        "gradient",
        "gradient_target_closure_id",
        "local_controller",
        "path_blocks",
        "positive_control_target_closure_id",
        "preferred_path",
        "quality_valid_closure_ids",
        "sham",
        "target_closure",
        "target_closure_id",
        "treatment",
        "treatment_id",
    }
)
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class VerificationError(RuntimeError):
    """The artifact or lock violates the frozen public contract."""


def _reject_constant(value: str) -> Any:
    raise VerificationError(f"non-finite JSON constant: {value}")


def _finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise VerificationError(f"non-finite JSON number: {value}")
    return parsed


def _reject_duplicates(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise VerificationError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def _load_json(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            parse_constant=_reject_constant,
            parse_float=_finite_float,
            object_pairs_hook=_reject_duplicates,
        )
    except VerificationError:
        raise
    except Exception as error:
        raise VerificationError(f"invalid JSON: {label}") from error
    if not isinstance(value, dict):
        raise VerificationError(f"JSON root is not an object: {label}")
    _assert_finite(value, label)
    return value


def _assert_finite(value: Any, label: str) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise VerificationError(f"non-finite value: {label}")
    if isinstance(value, Mapping):
        for child in value.values():
            _assert_finite(child, label)
    elif isinstance(value, list):
        for child in value:
            _assert_finite(child, label)


def _canonical_bytes(value: Any, *, newline: bool = False) -> bytes:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return raw + (b"\n" if newline else b"")


def _pretty_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _fingerprint(value: Any) -> str:
    return _sha256(_canonical_bytes(value))


def _without_fingerprint(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key != "fingerprint_sha256"
    }


def _assert_sealed(value: Mapping[str, Any], label: str) -> None:
    if value.get("fingerprint_sha256") != _fingerprint(_without_fingerprint(value)):
        raise VerificationError(f"fingerprint differs: {label}")


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def _read_artifact_files(directory: Path) -> dict[str, bytes]:
    if directory.is_symlink() or not directory.is_dir():
        raise VerificationError("artifact directory is unavailable or a symlink")
    paths = list(directory.rglob("*"))
    for path in paths:
        if path.is_symlink() or not path.is_file() or path.parent != directory:
            raise VerificationError("artifact contains a symlink or nested entry")
    if len(paths) != len(EXPECTED_FILES) or {path.name for path in paths} != set(
        EXPECTED_FILES
    ):
        raise VerificationError("artifact file set differs")
    return {name: (directory / name).read_bytes() for name in EXPECTED_FILES}


def _load_lock(path: Path) -> tuple[dict[str, Any], bytes]:
    if path.is_symlink() or not path.is_file():
        raise VerificationError("policy lock is unavailable or a symlink")
    raw = path.read_bytes()
    lock = _load_json(raw, "policy lock")
    if raw != _pretty_bytes(lock):
        raise VerificationError("policy lock JSON is noncanonical")
    _assert_sealed(lock, "policy lock")
    if (
        len(raw) != EXPECTED_LOCK_BYTES
        or _sha256(raw) != EXPECTED_LOCK_SHA256
        or lock.get("fingerprint_sha256") != EXPECTED_LOCK_FINGERPRINT
    ):
        raise VerificationError("policy lock differs from frozen bytes")
    authorization = lock.get("execution", {})
    if (
        lock.get("schema_version") != "ebrt-actuator-uptake-live-policy-v0.6.3.1-r01"
        or authorization.get("authorization_tag") != "v0.6.3.1-live-r01-authorized"
        or authorization.get("execution_order") != list(EXECUTION_ORDER)
        or authorization.get("exact_attempt_count") != 4
        or authorization.get("provider_calls_authorized") != 4
        or authorization.get("no_retry") is not True
        or authorization.get("no_resume") is not True
        or authorization.get("no_reorder") is not True
        or authorization.get("no_backfill") is not True
    ):
        raise VerificationError("policy lock execution contract differs")
    preflight_anchor = lock.get("preflight_anchor", {})
    if (
        preflight_anchor.get("tag_object") != EXPECTED_PREFLIGHT_TAG_OBJECT
        or preflight_anchor.get("commit") != EXPECTED_PREFLIGHT_COMMIT
        or preflight_anchor.get("projection_fingerprint_sha256")
        != EXPECTED_PROJECTION_FINGERPRINT
    ):
        raise VerificationError("policy lock preflight anchor differs")
    return lock, raw


def _load_jsonl(raw: bytes, label: str) -> list[dict[str, Any]]:
    if not raw or not raw.endswith(b"\n"):
        raise VerificationError(f"JSONL lacks a trailing newline: {label}")
    rows = [
        _load_json(line, f"{label}:{index}")
        for index, line in enumerate(raw.splitlines(), start=1)
    ]
    canonical = b"".join(_canonical_bytes(row, newline=True) for row in rows)
    if raw != canonical:
        raise VerificationError(f"JSONL is noncanonical: {label}")
    return rows


def _parse_bundle(files: Mapping[str, bytes]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for name in (
        "result.json",
        "manifest.json",
        "provider_inputs.json",
        "projection_bundle.json",
    ):
        value = _load_json(files[name], name)
        if files[name] != _pretty_bytes(value):
            raise VerificationError(f"JSON is noncanonical: {name}")
        parsed[name] = value
    parsed["calls.jsonl"] = _load_jsonl(files["calls.jsonl"], "calls.jsonl")
    parsed["attempt_journal.jsonl"] = _load_jsonl(
        files["attempt_journal.jsonl"], "attempt_journal.jsonl"
    )
    return parsed


def _validate_manifest_receipts(
    files: Mapping[str, bytes], manifest: Mapping[str, Any]
) -> None:
    _assert_sealed(manifest, "manifest")
    non_manifest = set(EXPECTED_FILES) - {"manifest.json"}
    if (
        set(manifest)
        != {
            "schema_version",
            "status",
            "attempt_block_status",
            "assessment_status",
            "terminal_decision",
            "policy_lock_fingerprint_sha256",
            "result_fingerprint_sha256",
            "source_snapshot_sha256",
            "artifacts",
            "claim_boundary",
            "fingerprint_sha256",
        }
        or manifest.get("schema_version") != MANIFEST_SCHEMA
        or set(manifest.get("artifacts", {})) != non_manifest
    ):
        raise VerificationError("manifest schema differs")
    for name in non_manifest:
        if manifest["artifacts"][name] != {
            "bytes": len(files[name]),
            "sha256": _sha256(files[name]),
        }:
            raise VerificationError(f"manifest receipt differs: {name}")


def _recursive_keys(value: Any) -> Iterable[str]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield key
            yield from _recursive_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _recursive_keys(child)


def _validate_projection(projection: Mapping[str, Any]) -> list[dict[str, Any]]:
    _assert_sealed(projection, "projection")
    if (
        projection.get("fingerprint_sha256") != EXPECTED_PROJECTION_FINGERPRINT
        or projection.get("schema_version")
        != "ebrt-actuator-uptake-projection-v0.6.3.1"
        or projection.get("execution_order") != list(EXECUTION_ORDER)
        or projection.get("provider_calls_authorized") != 0
        or projection.get("provider_calls_observed") != 0
        or projection.get("provider_payload_count") != 4
        or projection.get("gold_used_for_projection") is not False
        or projection.get("status") != "READY_ZERO_CALL_PREFLIGHT_ONLY"
    ):
        raise VerificationError("projection top-level contract differs")
    payload_rows = projection.get("provider_payloads")
    treatment_key = projection.get("public_treatment_key")
    if not isinstance(payload_rows, list) or len(payload_rows) != 4:
        raise VerificationError("projection payload schedule differs")
    expected_key: list[dict[str, Any]] = []
    baseline_without_order: dict[str, Any] | None = None
    baseline_evidence: dict[str, str] | None = None
    for position, (arm, blind_id, expected_fp, row) in enumerate(
        zip(
            EXECUTION_ORDER,
            BLINDED_IDS,
            PAYLOAD_FINGERPRINTS,
            payload_rows,
            strict=True,
        ),
        start=1,
    ):
        if set(row) != {"sequence_index", "blinded_request_id", "payload"}:
            raise VerificationError("projection payload row schema differs")
        if row["sequence_index"] != position or row["blinded_request_id"] != blind_id:
            raise VerificationError("projection payload row identity differs")
        payload = row["payload"]
        if not isinstance(payload, Mapping):
            raise VerificationError("projection payload is not an object")
        _assert_sealed(payload, f"payload {arm}")
        if payload.get("fingerprint_sha256") != expected_fp:
            raise VerificationError(f"payload fingerprint differs: {arm}")
        raw = _without_fingerprint(payload)
        if set(_recursive_keys(raw)) & FORBIDDEN_PROVIDER_METADATA:
            raise VerificationError(f"provider-visible forbidden metadata: {arm}")
        if (
            raw.get("schema_version") != PROVIDER_INPUT_SCHEMA
            or raw.get("checkpoint_id") != CHECKPOINT
            or raw.get("answer_choices") != ["VIOLET", "COPPER"]
            or raw.get("record_format_choices") != ["SIGNED_NDJSON"]
        ):
            raise VerificationError(f"provider payload contract differs: {arm}")
        evidence = raw.get("ordered_raw_evidence")
        if not isinstance(evidence, list) or len(evidence) != 7:
            raise VerificationError(f"provider evidence list differs: {arm}")
        evidence_map = {
            item.get("evidence_id"): item.get("text")
            for item in evidence
            if isinstance(item, Mapping) and set(item) == {"evidence_id", "text"}
        }
        if len(evidence_map) != 7:
            raise VerificationError(
                f"provider evidence is duplicate or malformed: {arm}"
            )
        without_order = copy.deepcopy(raw)
        without_order.pop("ordered_raw_evidence")
        if baseline_without_order is None:
            baseline_without_order = without_order
            baseline_evidence = evidence_map
        elif (
            without_order != baseline_without_order or evidence_map != baseline_evidence
        ):
            raise VerificationError("provider arms differ beyond evidence order")
        expected_key.append(
            {
                "sequence_index": position,
                "blinded_request_id": blind_id,
                "treatment_id": arm,
            }
        )
    if treatment_key != expected_key:
        raise VerificationError("projection public treatment key differs")
    return [dict(row) for row in payload_rows]


def _validate_provider_inputs(
    value: Mapping[str, Any], projection_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    _assert_sealed(value, "provider inputs")
    if (
        set(value)
        != {
            "schema_version",
            "projection_fingerprint_sha256",
            "execution_order",
            "payloads",
            "provider_received_unsealed_payload_only",
            "fingerprint_sha256",
        }
        or value.get("schema_version") != INPUTS_SCHEMA
        or value.get("fingerprint_sha256") != EXPECTED_PROVIDER_INPUTS_FINGERPRINT
        or value.get("projection_fingerprint_sha256") != EXPECTED_PROJECTION_FINGERPRINT
        or value.get("execution_order") != list(EXECUTION_ORDER)
        or value.get("provider_received_unsealed_payload_only") is not True
    ):
        raise VerificationError("provider-input artifact contract differs")
    rows = value.get("payloads")
    if not isinstance(rows, list) or len(rows) != 4:
        raise VerificationError("provider-input schedule differs")
    for position, (arm, blind_id, expected_fp, row, projection_row) in enumerate(
        zip(
            EXECUTION_ORDER,
            BLINDED_IDS,
            PAYLOAD_FINGERPRINTS,
            rows,
            projection_rows,
            strict=True,
        ),
        start=1,
    ):
        if (
            set(row)
            != {
                "sequence_index",
                "blinded_request_id",
                "treatment_id",
                "provider_payload_fingerprint_sha256",
                "sealed_payload",
            }
            or row.get("sequence_index") != position
            or row.get("blinded_request_id") != blind_id
            or row.get("treatment_id") != arm
            or row.get("provider_payload_fingerprint_sha256") != expected_fp
            or row.get("sealed_payload") != projection_row["payload"]
        ):
            raise VerificationError(f"provider-input row differs: {arm}")
        sealed = row["sealed_payload"]
        _assert_sealed(sealed, f"provider input sealed payload {arm}")
        if _fingerprint(_without_fingerprint(sealed)) != expected_fp:
            raise VerificationError(f"raw/sealed payload binding differs: {arm}")
        if (
            set(_recursive_keys(_without_fingerprint(sealed)))
            & FORBIDDEN_PROVIDER_METADATA
        ):
            raise VerificationError(f"provider-visible forbidden metadata: {arm}")
    return [dict(row) for row in rows]


def _validate_receipt(
    receipt: Mapping[str, Any], raw_payload: Mapping[str, Any], lock: Mapping[str, Any]
) -> None:
    if set(receipt) != {
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
    }:
        raise VerificationError("provider receipt schema differs")
    runtime = lock["runtime"]
    raw_fp = _fingerprint(raw_payload)
    if (
        receipt.get("provider") != "openai_responses"
        or receipt.get("requested_model") != "gpt-5.6-sol"
        or receipt.get("returned_model") != "gpt-5.6-sol"
        or type(receipt.get("logical_calls")) is not int
        or receipt.get("logical_calls") != 1
        or type(receipt.get("api_calls")) is not int
        or receipt.get("api_calls") != 1
        or receipt.get("request_fingerprint") != raw_fp
        or receipt.get("prompt_fingerprint") != lock["instructions_fingerprint_sha256"]
        or not isinstance(receipt.get("latency_ms"), (int, float))
        or isinstance(receipt.get("latency_ms"), bool)
        or not math.isfinite(float(receipt["latency_ms"]))
        or float(receipt["latency_ms"]) < 0.0
    ):
        raise VerificationError("provider receipt binding differs")
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
    semantic_protocol = _fingerprint(
        {
            "model": runtime["model"],
            "instructions_fingerprint": lock["instructions_fingerprint_sha256"],
            "input_fingerprint": raw_fp,
            "text_schema_fingerprint": lock["response_schema_fingerprint_sha256"],
            "reasoning": {"effort": runtime["reasoning_effort"]},
            "max_output_tokens": runtime["max_output_tokens"],
            "store": runtime["store"],
            "service_tier": runtime["service_tier"],
            "truncation": runtime["truncation"],
            "timeout_seconds": float(runtime["timeout_seconds"]),
        }
    )
    if (
        not isinstance(metadata, Mapping)
        or set(metadata) != metadata_keys
        or metadata.get("receipt_schema_version")
        != "ebrt-provider-boundary-receipt-v0.4.3"
        or metadata.get("status") != "completed"
        or metadata.get("service_tier") != runtime["service_tier"]
        or metadata.get("http_observed") is not True
        or metadata.get("http_status_code") != 200
        or metadata.get("parse_boundary") != "succeeded"
        or metadata.get("failure_phase") is not None
        or metadata.get("failure_reason_code") is not None
        or metadata.get("failure_type") is not None
        or metadata.get("reasoning_effort") != runtime["reasoning_effort"]
        or metadata.get("max_output_tokens") != runtime["max_output_tokens"]
        or metadata.get("store") is not False
        or metadata.get("previous_response_id") is not False
        or metadata.get("truncation") != "disabled"
        or metadata.get("sdk_version") != runtime["openai_sdk"]
        or metadata.get("pydantic_version") != runtime["pydantic"]
        or metadata.get("python_version") != runtime["python"]
        or metadata.get("attempt") != 1
        or metadata.get("retry_count") != 0
        or metadata.get("api_call_count_semantics") != "attempted_client_call"
        or metadata.get("attempt_outcome") != "completed"
        or metadata.get("refusal_count") != 0
        or metadata.get("response_schema_fingerprint")
        != lock["response_schema_fingerprint_sha256"]
        or metadata.get("semantic_protocol_fingerprint") != semantic_protocol
        or not _is_sha256(metadata.get("client_request_id_sha256"))
        or not _is_sha256(metadata.get("response_id_sha256"))
        or not _is_sha256(metadata.get("server_request_id_sha256"))
        or not _is_sha256(metadata.get("provider_body_sha256"))
        or type(metadata.get("provider_body_byte_count")) is not int
        or metadata.get("provider_body_byte_count", 0) <= 0
    ):
        raise VerificationError("completed provider receipt differs")
    usage = receipt["usage"]
    usage_keys = {
        "exact_provider_tokens",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cached_input_tokens",
        "cache_write_tokens",
        "reasoning_tokens",
    }
    if (
        not isinstance(usage, Mapping)
        or set(usage) != usage_keys
        or usage.get("exact_provider_tokens") is not True
    ):
        raise VerificationError("provider usage schema differs")
    for key in usage_keys - {"exact_provider_tokens"}:
        if type(usage.get(key)) is not int or usage[key] < 0:
            raise VerificationError("provider usage value differs")
    if (
        usage["total_tokens"] != usage["input_tokens"] + usage["output_tokens"]
        or usage["cached_input_tokens"] > usage["input_tokens"]
        or usage["reasoning_tokens"] > usage["output_tokens"]
    ):
        raise VerificationError("provider usage relationship differs")


def _expected_graph(selected_evidence: list[str]) -> dict[str, Any]:
    edges: list[dict[str, str]] = []
    for evidence_id in selected_evidence:
        if evidence_id == "E7":
            edges.append(
                {
                    "edge_id": "STABLE_E7",
                    "relation_type": "supports",
                    "source_node_id": "E7",
                    "target_node_id": "PUBLIC_RECORD_FORMAT",
                }
            )
        else:
            edges.append(
                {
                    "edge_id": f"SUPPORT_{evidence_id}",
                    "relation_type": "supports",
                    "source_node_id": evidence_id,
                    "target_node_id": "PUBLIC_DECISION",
                }
            )
    if "E6" in selected_evidence:
        edges.append(
            {
                "edge_id": "INVALIDATES_E6_E5",
                "relation_type": "invalidates",
                "source_node_id": "E6",
                "target_node_id": "E5",
            }
        )
    nodes = [*selected_evidence]
    if "E6" in selected_evidence and "E5" not in nodes:
        nodes.append("E5")
    nodes.extend(["PUBLIC_DECISION", "PUBLIC_RECORD_FORMAT"])
    return {"nodes": nodes, "edges": edges}


def _validate_output_and_compiled(
    output: Mapping[str, Any],
    compiled: Mapping[str, Any],
    sealed_payload: Mapping[str, Any],
    *,
    position: int,
) -> None:
    arm = EXECUTION_ORDER[position - 1]
    raw_payload = _without_fingerprint(sealed_payload)
    evidence_order = [row["evidence_id"] for row in raw_payload["ordered_raw_evidence"]]
    catalog = {
        row["closure_id"]: row["selected_evidence_ids"]
        for row in raw_payload["candidate_closures"]
    }
    if (
        set(output)
        != {
            "schema_version",
            "checkpoint_id",
            "selected_closure_id",
            "reviewed_evidence_ids",
            "current_answer",
            "record_format",
        }
        or output.get("schema_version") != PROVIDER_OUTPUT_SCHEMA
        or output.get("checkpoint_id") != CHECKPOINT
        or output.get("selected_closure_id") != SELECTED_CLOSURES[position - 1]
        or output.get("selected_closure_id") not in catalog
        or output.get("reviewed_evidence_ids") != evidence_order[:3]
        or output.get("current_answer") != "VIOLET"
        or output.get("record_format") != "SIGNED_NDJSON"
        or _fingerprint(output) != PROVIDER_OUTPUT_FINGERPRINTS[position - 1]
    ):
        raise VerificationError(f"provider public output differs: {arm}")
    selected_evidence = catalog[output["selected_closure_id"]]
    expected_without_fp = {
        "schema_version": COMPILED_SCHEMA,
        "checkpoint_id": CHECKPOINT,
        "provider_payload_fingerprint_sha256": sealed_payload["fingerprint_sha256"],
        "provider_output_fingerprint_sha256": _fingerprint(output),
        "selected_closure_id": output["selected_closure_id"],
        "selected_evidence_ids": selected_evidence,
        "current_answer": output["current_answer"],
        "record_format": output["record_format"],
        "expanded_public_graph": _expected_graph(selected_evidence),
        "inspection_receipt": {
            "reviewed_evidence_ids": output["reviewed_evidence_ids"],
            "expected_first_three_evidence_ids": evidence_order[:3],
            "adherence": True,
            "scored_as_primary_uptake": False,
        },
        "public_contract_checks": {
            "late_event_selected": True,
            "invalidated_evidence_absent": True,
            "stable_evidence_preserved": True,
        },
    }
    expected = dict(expected_without_fp)
    expected["fingerprint_sha256"] = _fingerprint(expected_without_fp)
    if (
        compiled != expected
        or compiled.get("fingerprint_sha256")
        != COMPILED_OUTPUT_FINGERPRINTS[position - 1]
    ):
        raise VerificationError(f"compiled public output differs: {arm}")


def _usage_summary(attempts: list[Mapping[str, Any]]) -> dict[str, Any]:
    token_keys = (
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cached_input_tokens",
        "cache_write_tokens",
        "reasoning_tokens",
    )
    return {
        "logical_calls": sum(row["receipt"]["logical_calls"] for row in attempts),
        "api_calls": sum(row["receipt"]["api_calls"] for row in attempts),
        "latency_ms": sum(row["receipt"]["latency_ms"] for row in attempts),
        "exact_provider_tokens": True,
        **{
            key: sum(row["receipt"]["usage"][key] for row in attempts)
            for key in token_keys
        },
    }


def _validate_execution(
    result: Mapping[str, Any],
    provider_rows: list[dict[str, Any]],
    calls: list[dict[str, Any]],
    journal: list[dict[str, Any]],
    lock: Mapping[str, Any],
) -> None:
    execution = result.get("execution")
    if not isinstance(execution, Mapping) or set(execution) != {
        "attempts",
        "provider_outputs",
        "compiled_outputs",
        "attempt_block_status",
        "assessment_status",
        "invalid_blinded_request_ids",
        "unattempted_blinded_request_ids",
    }:
        raise VerificationError("execution schema differs")
    attempts = execution["attempts"]
    outputs = execution["provider_outputs"]
    compiled_outputs = execution["compiled_outputs"]
    if (
        not isinstance(attempts, list)
        or len(attempts) != 4
        or not isinstance(outputs, Mapping)
        or not isinstance(compiled_outputs, Mapping)
        or set(outputs) != set(BLINDED_IDS)
        or set(compiled_outputs) != set(BLINDED_IDS)
        or execution["attempt_block_status"] != "COMPLETE_EXACT_FOUR_TERMINALS"
        or execution["assessment_status"] != "READY_FOR_POST_CALL_GOLD"
        or execution["invalid_blinded_request_ids"] != []
        or execution["unattempted_blinded_request_ids"] != []
        or len(calls) != 4
        or len(journal) != 8
    ):
        raise VerificationError("four-call execution block differs")
    for position, (arm, blind_id, payload_fp, provider_row, attempt) in enumerate(
        zip(
            EXECUTION_ORDER,
            BLINDED_IDS,
            PAYLOAD_FINGERPRINTS,
            provider_rows,
            attempts,
            strict=True,
        ),
        start=1,
    ):
        if (
            set(attempt)
            != {
                "sequence_index",
                "blinded_request_id",
                "treatment_id",
                "provider_input_fingerprint_sha256",
                "provider_output_fingerprint_sha256",
                "compiled_output_fingerprint_sha256",
                "receipt",
                "failure",
                "status",
            }
            or attempt.get("sequence_index") != position
            or attempt.get("blinded_request_id") != blind_id
            or attempt.get("treatment_id") != arm
            or attempt.get("provider_input_fingerprint_sha256") != payload_fp
            or attempt.get("provider_output_fingerprint_sha256")
            != PROVIDER_OUTPUT_FINGERPRINTS[position - 1]
            or attempt.get("compiled_output_fingerprint_sha256")
            != COMPILED_OUTPUT_FINGERPRINTS[position - 1]
            or attempt.get("failure") is not None
            or attempt.get("status") != "COMPLETED"
        ):
            raise VerificationError(f"terminal attempt differs: {arm}")
        sealed = provider_row["sealed_payload"]
        raw = _without_fingerprint(sealed)
        _validate_receipt(attempt["receipt"], raw, lock)
        output = outputs[blind_id]
        compiled = compiled_outputs[blind_id]
        _validate_output_and_compiled(output, compiled, sealed, position=position)
        expected_call = {
            "schema_version": CALL_SCHEMA,
            "sequence_index": position,
            "blinded_request_id": blind_id,
            "treatment_id": arm,
            "status": "COMPLETED",
            "failure": None,
            "receipt": attempt["receipt"],
        }
        if calls[position - 1] != expected_call:
            raise VerificationError(f"call ledger differs: {arm}")
        expected_start = {
            "schema_version": JOURNAL_SCHEMA,
            "event": "ATTEMPT_STARTED",
            "sequence_index": position,
            "blinded_request_id": blind_id,
            "provider_input_fingerprint_sha256": payload_fp,
        }
        expected_terminal = {
            "schema_version": JOURNAL_SCHEMA,
            "event": "ATTEMPT_TERMINAL",
            "attempt": attempt,
            "provider_output": output,
            "compiled_output": compiled,
        }
        if (
            journal[(position - 1) * 2] != expected_start
            or journal[(position - 1) * 2 + 1] != expected_terminal
        ):
            raise VerificationError(f"attempt journal differs: {arm}")
    if result.get("usage") != _usage_summary(attempts):
        raise VerificationError("aggregate usage differs from four receipts")


def _expected_source_snapshot(lock: Mapping[str, Any]) -> dict[str, str]:
    return {
        label: receipt["sha256"]
        for label, receipt in lock["sources"].items()
        if label != "post_call_gold"
    }


def _validate_preflight(result: Mapping[str, Any], lock: Mapping[str, Any]) -> None:
    preflight = result.get("preflight")
    if not isinstance(preflight, Mapping):
        raise VerificationError("preflight record is missing")
    _assert_sealed(preflight, "preflight")
    authorization = preflight.get("execution_authorization")
    expected_authorization = {
        "status": "AUTHORIZED_ANNOTATED_TAG",
        "tag_name": "v0.6.3.1-live-r01-authorized",
        "tag_object": EXPECTED_AUTHORIZATION_TAG_OBJECT,
        "authorized_commit": EXPECTED_AUTHORIZED_COMMIT,
        "execution_head_commit": EXPECTED_AUTHORIZED_COMMIT,
        "head_matches_authorized_commit": True,
        "provenance_scope": "OPERATOR_ATTESTED_NOT_CRYPTOGRAPHICALLY_AUTHENTICATED",
    }
    component = preflight.get("component_self_test")
    if not isinstance(component, Mapping):
        raise VerificationError("component self-test record is missing")
    _assert_sealed(component, "component self-test")
    expected_provider = {
        **copy.deepcopy(lock["runtime"]),
        "instructions_fingerprint_sha256": lock["instructions_fingerprint_sha256"],
        "response_schema_fingerprint_sha256": lock[
            "response_schema_fingerprint_sha256"
        ],
        "receipt_schema_version": "ebrt-provider-boundary-receipt-v0.4.3",
    }
    if (
        preflight.get("schema_version")
        != "ebrt-actuator-uptake-live-preflight-v0.6.3.1-r01"
        or preflight.get("status") != "READY_EXACT_FOUR_CALL_LIVE_BLOCK"
        or preflight.get("expected_api_attempts") != 4
        or preflight.get("execution_order") != list(EXECUTION_ORDER)
        or preflight.get("call_order_blinded_request_ids") != list(BLINDED_IDS)
        or preflight.get("payload_fingerprints")
        != dict(zip(BLINDED_IDS, PAYLOAD_FINGERPRINTS, strict=True))
        or preflight.get("projection_fingerprint_sha256")
        != EXPECTED_PROJECTION_FINGERPRINT
        or preflight.get("policy_lock_fingerprint_sha256") != EXPECTED_LOCK_FINGERPRINT
        or preflight.get("provider") != expected_provider
        or authorization != expected_authorization
        or preflight.get("source_snapshot_sha256") != _expected_source_snapshot(lock)
        or preflight.get("post_call_gold_expected_receipt")
        != lock["sources"]["post_call_gold"]
        or preflight.get("gold_loaded") is not False
        or preflight.get("provider_calls") != 0
        or preflight.get("network_calls") != 0
        or component.get("status") != "PASS_NETWORK_ZERO"
        or component.get("provider_calls") != 0
        or component.get("network_calls") != 0
        or not isinstance(component.get("checks"), Mapping)
        or not component["checks"]
        or not all(value is True for value in component["checks"].values())
    ):
        raise VerificationError("preflight or authorization record differs")


def _validate_decision(result: Mapping[str, Any]) -> None:
    decision = result.get("decision")
    if not isinstance(decision, Mapping):
        raise VerificationError("decision is missing")
    _assert_sealed(decision, "decision")
    expected_selected = dict(zip(EXECUTION_ORDER, SELECTED_CLOSURES, strict=True))
    expected = {
        "schema_version": "ebrt-actuator-uptake-decision-v0.6.3.1",
        "assessment_status": "ASSESSED",
        "positive_control_status": "CHANNEL_OPEN_DIRECTIONAL",
        "gradient_placement_status": "GRADIENT_PLACEMENT_DIRECTIONAL",
        "terminal_decision": "PROMOTE_TO_FRESH_REPLICATION",
        "selected_closure_by_arm": expected_selected,
        "endpoint_fingerprint_by_arm": ENDPOINT_FINGERPRINTS,
        "invalid_arms": [],
        "direct_v0_6_4_promotion_allowed": False,
        "claim_boundary": [
            "PROMOTE_TO_FRESH_REPLICATION opens only a separately sealed replication gate.",
            "This four-call classification is not a quality, causal, or population-level result.",
        ],
    }
    expected["fingerprint_sha256"] = _fingerprint(expected)
    selected_from_execution = {
        attempt["treatment_id"]: result["execution"]["compiled_outputs"][
            attempt["blinded_request_id"]
        ]["selected_closure_id"]
        for attempt in result["execution"]["attempts"]
    }
    if decision != expected or selected_from_execution != expected_selected:
        raise VerificationError("terminal decision or selected closures differ")


def _report(result: Mapping[str, Any]) -> bytes:
    lines = [
        "# EBRT v0.6.3.1 live-r01",
        "",
        f"- Attempt block: `{result['execution']['attempt_block_status']}`",
        f"- Assessment: `{result['decision']['assessment_status']}`",
        f"- Terminal decision: `{result['decision']['terminal_decision']}`",
        f"- Calls: `{result['usage']['api_calls']}/4`",
        f"- Gold loaded: `{str(result['semantic_gold']['loaded']).lower()}`",
        "",
        "## Public outputs",
        "",
        "| Position | Arm | Status | Closure |",
        "|---:|---|---|---|",
    ]
    for attempt in result["execution"]["attempts"]:
        output = result["execution"]["provider_outputs"][attempt["blinded_request_id"]]
        lines.append(
            f"| {attempt['sequence_index']} | {attempt['treatment_id']} | "
            f"{attempt['status']} | {output['selected_closure_id']} |"
        )
    lines.extend(
        ["", "## Boundary", "", *[f"- {item}" for item in result["claim_boundary"]], ""]
    )
    return "\n".join(lines).encode("utf-8")


def _validate_result_links(
    files: Mapping[str, bytes],
    result: Mapping[str, Any],
    manifest: Mapping[str, Any],
    projection: Mapping[str, Any],
    lock: Mapping[str, Any],
) -> None:
    _assert_sealed(result, "result")
    expected_result_keys = {
        "schema_version",
        "mode",
        "claim_boundary",
        "preflight_anchor_tag_object",
        "preflight_anchor_commit",
        "policy_lock_fingerprint_sha256",
        "projection_fingerprint_sha256",
        "preflight",
        "source_snapshot_sha256",
        "execution",
        "semantic_gold",
        "decision",
        "direct_v0_6_4_promotion_allowed",
        "usage",
        "fingerprint_sha256",
    }
    if (
        set(result) != expected_result_keys
        or result.get("schema_version") != RESULT_SCHEMA
        or result.get("mode") != "openai_live_actuator_uptake_canary_v0_6_3_1_r01"
        or result.get("preflight_anchor_tag_object") != EXPECTED_PREFLIGHT_TAG_OBJECT
        or result.get("preflight_anchor_commit") != EXPECTED_PREFLIGHT_COMMIT
        or result.get("policy_lock_fingerprint_sha256") != EXPECTED_LOCK_FINGERPRINT
        or result.get("projection_fingerprint_sha256")
        != EXPECTED_PROJECTION_FINGERPRINT
        or result.get("source_snapshot_sha256") != _expected_source_snapshot(lock)
        or result.get("direct_v0_6_4_promotion_allowed") is not False
        or result.get("fingerprint_sha256") != EXPECTED_RESULT_FINGERPRINT
        or result.get("claim_boundary") != lock.get("claim_boundary")
    ):
        raise VerificationError("result top-level links differ")
    expected_gold = {
        "loaded": True,
        "classification_load_count": 1,
        "observed_receipt": lock["sources"]["post_call_gold"],
    }
    if result.get("semantic_gold") != expected_gold:
        raise VerificationError("post-call gold barrier record differs")
    if files["report.md"] != _report(result):
        raise VerificationError("report/result relationship differs")
    if (
        manifest.get("status") != "SEALED_LIVE_RESULT"
        or manifest.get("attempt_block_status")
        != result["execution"]["attempt_block_status"]
        or manifest.get("assessment_status") != result["decision"]["assessment_status"]
        or manifest.get("terminal_decision") != result["decision"]["terminal_decision"]
        or manifest.get("policy_lock_fingerprint_sha256")
        != result["policy_lock_fingerprint_sha256"]
        or manifest.get("result_fingerprint_sha256") != result["fingerprint_sha256"]
        or manifest.get("source_snapshot_sha256") != result["source_snapshot_sha256"]
        or manifest.get("claim_boundary") != result["claim_boundary"]
        or projection.get("fingerprint_sha256")
        != result["projection_fingerprint_sha256"]
    ):
        raise VerificationError("manifest/report/result links differ")


def _validate_frozen_receipts(files: Mapping[str, bytes]) -> None:
    for name, (expected_bytes, expected_sha) in EXPECTED_FILES.items():
        raw = files[name]
        if len(raw) != expected_bytes or _sha256(raw) != expected_sha:
            raise VerificationError(f"frozen byte receipt differs: {name}")


def verify(directory: Path, lock_path: Path = DEFAULT_LOCK) -> dict[str, Any]:
    """Validate a copied artifact and return a compact public summary."""

    files = _read_artifact_files(directory)
    lock, _ = _load_lock(lock_path)
    parsed = _parse_bundle(files)
    result = parsed["result.json"]
    manifest = parsed["manifest.json"]
    projection = parsed["projection_bundle.json"]
    inputs = parsed["provider_inputs.json"]
    _validate_manifest_receipts(files, manifest)
    projection_rows = _validate_projection(projection)
    provider_rows = _validate_provider_inputs(inputs, projection_rows)
    _validate_preflight(result, lock)
    _validate_execution(
        result,
        provider_rows,
        parsed["calls.jsonl"],
        parsed["attempt_journal.jsonl"],
        lock,
    )
    _validate_decision(result)
    _validate_result_links(files, result, manifest, projection, lock)
    if manifest.get("fingerprint_sha256") != EXPECTED_MANIFEST_FINGERPRINT:
        raise VerificationError("manifest fingerprint differs from frozen result")
    _validate_frozen_receipts(files)
    return {
        "status": "VALID_FROZEN_FOUR_CALL_RESULT",
        "artifact_directory": str(directory),
        "authorization_tag_object": EXPECTED_AUTHORIZATION_TAG_OBJECT,
        "authorized_commit": EXPECTED_AUTHORIZED_COMMIT,
        "execution_order": list(EXECUTION_ORDER),
        "api_calls": result["usage"]["api_calls"],
        "selected_closure_by_arm": result["decision"]["selected_closure_by_arm"],
        "positive_control_status": result["decision"]["positive_control_status"],
        "gradient_placement_status": result["decision"]["gradient_placement_status"],
        "terminal_decision": result["decision"]["terminal_decision"],
        "gold_loaded_after_four_terminals": result["semantic_gold"]["loaded"],
        "result_fingerprint_sha256": EXPECTED_RESULT_FINGERPRINT,
        "manifest_fingerprint_sha256": EXPECTED_MANIFEST_FINGERPRINT,
    }


def _seal_for_test(value: Mapping[str, Any]) -> dict[str, Any]:
    material = _without_fingerprint(value)
    material["fingerprint_sha256"] = _fingerprint(material)
    return material


def _write_pretty(path: Path, value: Mapping[str, Any]) -> None:
    path.write_bytes(_pretty_bytes(value))


def _load_path(path: Path) -> dict[str, Any]:
    return _load_json(path.read_bytes(), path.name)


def _refresh_manifest(directory: Path) -> None:
    result = _load_path(directory / "result.json")
    manifest = _load_path(directory / "manifest.json")
    material = _without_fingerprint(manifest)
    material["attempt_block_status"] = result["execution"]["attempt_block_status"]
    material["assessment_status"] = result["decision"]["assessment_status"]
    material["terminal_decision"] = result["decision"]["terminal_decision"]
    material["result_fingerprint_sha256"] = result["fingerprint_sha256"]
    material["source_snapshot_sha256"] = result["source_snapshot_sha256"]
    material["claim_boundary"] = result["claim_boundary"]
    material["artifacts"] = {
        name: {
            "bytes": len((directory / name).read_bytes()),
            "sha256": _sha256((directory / name).read_bytes()),
        }
        for name in EXPECTED_FILES
        if name != "manifest.json"
    }
    _write_pretty(directory / "manifest.json", _seal_for_test(material))


def _rewrite_result(directory: Path, result: Mapping[str, Any]) -> None:
    _write_pretty(directory / "result.json", _seal_for_test(result))
    _refresh_manifest(directory)


def _expect_rejected(operation: Callable[[], Any], label: str) -> None:
    try:
        operation()
    except VerificationError:
        return
    raise VerificationError(f"self-test tamper was accepted: {label}")


def _copy_fixture(root: Path, name: str) -> tuple[Path, Path]:
    case_root = root / name
    artifact = case_root / "artifact"
    artifact.mkdir(parents=True)
    for filename in EXPECTED_FILES:
        shutil.copyfile(DEFAULT_ARTIFACT / filename, artifact / filename)
    lock = case_root / "policy_lock.json"
    shutil.copyfile(DEFAULT_LOCK, lock)
    return artifact, lock


def self_test() -> dict[str, Any]:
    checks: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="ebrt-v0631-result-verifier-") as raw_root:
        root = Path(raw_root)

        artifact, lock = _copy_fixture(root, "foreign-root")
        verify(artifact, lock)
        checks["canonical_foreign_root_pass"] = True

        artifact, lock = _copy_fixture(root, "extra")
        (artifact / "extra.json").write_bytes(b"{}\n")
        _expect_rejected(lambda: verify(artifact, lock), "extra file")
        checks["extra_file_rejected"] = True

        artifact, lock = _copy_fixture(root, "missing")
        (artifact / "report.md").unlink()
        _expect_rejected(lambda: verify(artifact, lock), "missing file")
        checks["missing_file_rejected"] = True

        artifact, lock = _copy_fixture(root, "symlink")
        (artifact / "report.md").unlink()
        (artifact / "report.md").symlink_to(artifact / "result.json")
        _expect_rejected(lambda: verify(artifact, lock), "symlink")
        checks["symlink_rejected"] = True

        artifact, lock = _copy_fixture(root, "byte-tamper")
        (artifact / "report.md").write_bytes(
            (artifact / "report.md").read_bytes() + b" "
        )
        _expect_rejected(lambda: verify(artifact, lock), "byte tamper")
        checks["byte_tamper_rejected"] = True

        artifact, lock = _copy_fixture(root, "journal-reorder")
        rows = (artifact / "attempt_journal.jsonl").read_bytes().splitlines()
        rows[0], rows[1] = rows[1], rows[0]
        (artifact / "attempt_journal.jsonl").write_bytes(b"\n".join(rows) + b"\n")
        _refresh_manifest(artifact)
        _expect_rejected(lambda: verify(artifact, lock), "journal reorder")
        checks["journal_reorder_rejected"] = True

        artifact, lock = _copy_fixture(root, "authorization-tamper")
        result = _load_path(artifact / "result.json")
        preflight = copy.deepcopy(result["preflight"])
        preflight["execution_authorization"]["tag_object"] = "0" * 40
        result["preflight"] = _seal_for_test(preflight)
        _rewrite_result(artifact, result)
        _expect_rejected(lambda: verify(artifact, lock), "authorization tamper")
        checks["authorization_tamper_rejected"] = True

        artifact, lock = _copy_fixture(root, "usage-tamper")
        result = _load_path(artifact / "result.json")
        result["usage"]["api_calls"] = 5
        _rewrite_result(artifact, result)
        _expect_rejected(lambda: verify(artifact, lock), "usage tamper")
        checks["usage_tamper_rejected"] = True

        artifact, lock = _copy_fixture(root, "request-tamper")
        result = _load_path(artifact / "result.json")
        calls = _load_jsonl((artifact / "calls.jsonl").read_bytes(), "calls")
        journal = _load_jsonl(
            (artifact / "attempt_journal.jsonl").read_bytes(), "journal"
        )
        fake_request = "f" * 64
        result["execution"]["attempts"][0]["receipt"]["request_fingerprint"] = (
            fake_request
        )
        calls[0]["receipt"]["request_fingerprint"] = fake_request
        journal[1]["attempt"]["receipt"]["request_fingerprint"] = fake_request
        (artifact / "calls.jsonl").write_bytes(
            b"".join(_canonical_bytes(row, newline=True) for row in calls)
        )
        (artifact / "attempt_journal.jsonl").write_bytes(
            b"".join(_canonical_bytes(row, newline=True) for row in journal)
        )
        _rewrite_result(artifact, result)
        _expect_rejected(lambda: verify(artifact, lock), "request tamper")
        checks["request_binding_tamper_rejected"] = True

        artifact, lock = _copy_fixture(root, "early-gold")
        result = _load_path(artifact / "result.json")
        preflight = copy.deepcopy(result["preflight"])
        preflight["gold_loaded"] = True
        result["preflight"] = _seal_for_test(preflight)
        _rewrite_result(artifact, result)
        _expect_rejected(lambda: verify(artifact, lock), "early gold")
        checks["early_gold_tamper_rejected"] = True

        artifact, lock = _copy_fixture(root, "terminal-reseal")
        result = _load_path(artifact / "result.json")
        decision = copy.deepcopy(result["decision"])
        decision["positive_control_status"] = "CHANNEL_OPEN_DIRECTION_AMBIGUOUS"
        decision["terminal_decision"] = "STOP_CHANNEL_AMBIGUOUS"
        result["decision"] = _seal_for_test(decision)
        _write_pretty(artifact / "result.json", _seal_for_test(result))
        (artifact / "report.md").write_bytes(
            _report(_load_path(artifact / "result.json"))
        )
        _refresh_manifest(artifact)
        _expect_rejected(lambda: verify(artifact, lock), "coherent terminal reseal")
        checks["coherent_terminal_reseal_rejected"] = True

    _expect_rejected(
        lambda: _load_json(b'{"x":1,"x":2}', "duplicate-key probe"),
        "duplicate JSON key",
    )
    checks["duplicate_key_rejected"] = True
    _expect_rejected(
        lambda: _load_json(b'{"x":1e999}', "non-finite probe"),
        "1e999",
    )
    checks["one_e999_rejected"] = True
    if not all(checks.values()):
        raise VerificationError("self-test did not close every gate")
    return {
        "status": "PASS_PORTABLE_FROZEN_RESULT_SELF_TEST",
        "checks": checks,
        "network_calls": 0,
        "provider_calls": 0,
        "check_count": len(checks),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify_parser = subparsers.add_parser("verify", help="verify the frozen result")
    verify_parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT)
    verify_parser.add_argument("--lock-path", type=Path, default=DEFAULT_LOCK)
    subparsers.add_parser("self-test", help="run network-zero tamper tests")
    args = parser.parse_args()
    if args.command == "verify":
        output = verify(args.artifact_dir, args.lock_path)
    else:
        output = self_test()
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
