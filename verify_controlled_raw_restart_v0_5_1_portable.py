#!/usr/bin/env python3
"""Portable, stdlib-only verifier for the two frozen EBRT v0.5.1 bundles.

This verifies canonical bytes, digest lineage, recorded runtime/receipt
consistency, execution accounting, and the public calls ledger.  It never
imports the experiment runner or third-party packages, never contacts a
provider, and never gates on the verifier host runtime.  Numerical surrogate
reproduction and provider-body authentication are intentionally out of scope.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import platform
import shutil
import stat
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parent
POLICY_PATH = ROOT / "policy_lock_controlled_raw_restart_v0_5_1.json"
POLICY_SHA256 = "5173ce5aaa1f28d6e27cbdfffec5c38e0785e27d67cb4667abc5f07d200e8f2c"
POLICY_RELATIVE_PATH = "policy_lock_controlled_raw_restart_v0_5_1.json"
FILE_SET = frozenset({"results.json", "calls.jsonl", "report.md", "manifest.json"})
ARMS = (
    "raw_restart_zero_control",
    "raw_restart_textual_envelope",
    "raw_restart_matched_permutation",
    "controlled_raw_restart",
)
ARM_ORDER = (
    "raw_restart_zero_control",
    "raw_restart_textual_envelope",
    "controlled_raw_restart",
    "raw_restart_matched_permutation",
)

SOURCE_ANCHORS = {
    "aperture_v0_4_1": (
        "benchmark_aperture_controls_v0_4_1.py",
        "d5dd4a8a81172ad3603869d1f15f9649340ba7eab0c1627f5ab6ce2f9f752e66",
    ),
    "benchmark": (
        "benchmark_controlled_raw_restart_v0_5_1.py",
        "18ba54ebfd0cab2b3d35dab828a0fa2a8baf7edc0d965ce48b5ded3f09558a5c",
    ),
    "bridge": (
        "controlled_raw_restart_v0_5_1.py",
        "94d9f527334ef7b496db7afb3f6faf847b488e8b0ec043f486991e92092dde08",
    ),
    "provider_boundary_v0_4_3": (
        "openai_response_boundary_v0_4_3.py",
        "7f78fce94cb141a4355d3c040010e11e049ff67a3a8c603099d0548a47b7cf03",
    ),
    "public_card_schema_v0_4": (
        "language_replay_bridge_v0_4.py",
        "5fd765ec5ca55562e7b712ec48adc6f54588080c276cbfa58aabcb72492666c2",
    ),
    "public_card_validator_v0_4_2": (
        "benchmark_aperture_controls_v0_4_2.py",
        "b6b2dc592a03726b1f680835aefe18c399b1cb6e97c87d44e3d18f2e24bfdbd0",
    ),
    "strict_grader_v0_4": (
        "benchmark_language_replay_v0_4.py",
        "813ab885cecdacec034536a7dfeaa01c101554cc58663d1a79ad133595c6df91",
    ),
    "temporal_controller": (
        "temporal_adjoint_state_controller_v0_5_t.py",
        "43df27a8595274f694e7c0741c4fe642a66ae37a0719e5d3256d4a0f37f6b7b5",
    ),
}
FIXTURE_ANCHORS = {
    "bridge": (
        "fixtures/controlled_raw_restart_v0_5_1_canary.json",
        "0a250924ba0a8dd6c34aa2ce0dd72fde4de826715d1d4a7995bea41bcc7821d8",
    ),
    "gold": (
        "fixtures/language_replay_v0_4_dev_gold.json",
        "ca0d89c0eb92a7c9addb61014f64730762a17cf6ac1d76f0b5ca8a205b13f32a",
    ),
    "source_cases": (
        "fixtures/language_replay_v0_4_dev.json",
        "6b9ec912ae85c08ecdb76f71efecb24e4a05742b58330dda639cb4ed5d6fc5f6",
    ),
}

CANONICAL = {
    "benchmark_controlled_raw_restart_v0_5_1_live_canary": {
        "status": "INCOMPLETE_CANARY",
        "success_manifest": False,
        "result_fingerprint": "0009deddb69b28b67cf1ee7aa846374dcd38994204b16ddb5347a1b3823c232b",
        "files": {
            "calls.jsonl": (
                "d2c4c61a629d5e31e10a3fd4556257b95cd72782f86a4cd76ae49c7f26e48a46",
                7986,
            ),
            "manifest.json": (
                "28148bad238c15165986af2cd4f093d308c40e269242dc151937d69ddfb7608e",
                2893,
            ),
            "report.md": (
                "1e15adc4740a36402735049b23936339ecdc1bbeea556acfa7e311b249e2b691",
                1158,
            ),
            "results.json": (
                "ba5f9cd8faf22c2dbe0905c00bb29f746913c186acd59eb5cebffbdfec198e03",
                43768,
            ),
        },
    },
    "benchmark_controlled_raw_restart_v0_5_1_quota_recovery_r01": {
        "status": "COMPLETE_CANARY",
        "success_manifest": True,
        "result_fingerprint": "69a9518c709c5d8e26583c5b440fb9f855fab611f803041c597109f06b44787c",
        "files": {
            "calls.jsonl": (
                "6c68152d6440816a28a3c5495643257870d862ab346eb80f84741a75855e73ec",
                7562,
            ),
            "manifest.json": (
                "304315d9725492372921a8c1af40f36f64d4877b03ea05b68575bb2e2b8a5558",
                2890,
            ),
            "report.md": (
                "41a79dff01e12ce2389d9c77fb91d85d0d650b5430bd3774234ba0db1deb8a28",
                1562,
            ),
            "results.json": (
                "e4b8009e392d5e4b6045307e5932668827060e8fe7f9cc8e382f6f6b746df035",
                50575,
            ),
        },
    },
}

RESULT_CLAIM_BOUNDARY = [
    "This is one development-contaminated case and one unbalanced four-call block.",
    "Provider randomness and run position are not separated from arm behavior.",
    "The public temporal program and case binding are explicit oracle inputs.",
    "GPT, provider parsing, and final generation remain outside the gradient graph.",
    "A changed output or controlled-only pass is a canary observation, not an advantage estimate.",
    "Frozen predecessor imports may hash the gold file for source integrity, but semantic gold JSON is parsed and attached only after all four provider attempts.",
]

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
METADATA_KEYS = frozenset(
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


class PortableVerificationError(RuntimeError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return _sha(_canonical(value))


def _strict_json(data: bytes, label: str) -> dict[str, Any]:
    def pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in pairs:
            if key in out:
                raise PortableVerificationError(f"{label}: duplicate JSON key {key!r}")
            out[key] = value
        return out

    def bad_constant(value: str) -> None:
        raise PortableVerificationError(f"{label}: non-finite JSON constant {value}")

    try:
        value = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=pairs_hook,
            parse_constant=bad_constant,
        )
    except PortableVerificationError:
        raise
    except Exception as error:
        raise PortableVerificationError(
            f"{label}: invalid strict UTF-8 JSON"
        ) from error
    if not isinstance(value, dict):
        raise PortableVerificationError(f"{label}: root must be an object")
    return value


def _exact(
    value: Any, keys: set[str] | frozenset[str], label: str
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != set(keys):
        raise PortableVerificationError(f"{label}: schema mismatch")
    return value


def _is_sha(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(c in "0123456789abcdef" for c in value)
    )


def _nonnegative_int(value: Any) -> bool:
    return type(value) is int and value >= 0


def _read_regular(path: Path, label: str) -> bytes:
    try:
        mode = os.lstat(path).st_mode
    except OSError as error:
        raise PortableVerificationError(f"{label}: missing file") from error
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise PortableVerificationError(f"{label}: must be a regular non-symlink file")
    return path.read_bytes()


def _locked_path(relative: str, label: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise PortableVerificationError(f"{label}: invalid relative path")
    parts = Path(relative).parts
    if ".." in parts:
        raise PortableVerificationError(f"{label}: path escapes repository")
    return ROOT.joinpath(*parts)


def _validate_policy() -> tuple[dict[str, Any], dict[str, str]]:
    raw = _read_regular(POLICY_PATH, "policy lock")
    if _sha(raw) != POLICY_SHA256:
        raise PortableVerificationError("policy lock: external SHA-256 anchor mismatch")
    policy = _strict_json(raw, "policy lock")
    _exact(
        policy,
        {
            "schema_version",
            "status",
            "promotion_eligible",
            "arms",
            "execution",
            "runtime",
            "instructions_fingerprint_sha256",
            "sources",
            "fixtures",
            "canary_decision_rules",
            "claim_boundary",
        },
        "policy lock",
    )
    if (
        policy["schema_version"] != "ebrt-controlled-raw-restart-policy-lock-v0.5.1"
        or policy["status"] != "PREREGISTERED_DEV_CANARY"
        or policy["promotion_eligible"] is not False
        or tuple(policy["arms"]) != ARMS
        or tuple(policy["execution"].get("arm_order", ())) != ARM_ORDER
        or policy["execution"].get("expected_api_attempts") != 4
        or policy["execution"].get("retry_policy") != "one_attempt_no_retry"
        or not _is_sha(policy["instructions_fingerprint_sha256"])
    ):
        raise PortableVerificationError("policy lock: frozen protocol drifted")
    if set(policy["sources"]) != set(SOURCE_ANCHORS):
        raise PortableVerificationError("policy lock: source labels drifted")
    snapshot: dict[str, str] = {}
    for label, (relative, expected_sha) in SOURCE_ANCHORS.items():
        spec = _exact(policy["sources"][label], {"path", "sha256"}, f"source {label}")
        if spec != {"path": relative, "sha256": expected_sha}:
            raise PortableVerificationError(f"source {label}: lock identity drifted")
        if (
            _sha(
                _read_regular(
                    _locked_path(relative, f"source {label}"), f"source {label}"
                )
            )
            != expected_sha
        ):
            raise PortableVerificationError(f"source {label}: byte hash mismatch")
        snapshot[label] = expected_sha
    if set(policy["fixtures"]) != set(FIXTURE_ANCHORS):
        raise PortableVerificationError("policy lock: fixture labels drifted")
    for label, (relative, expected_sha) in FIXTURE_ANCHORS.items():
        spec = _exact(policy["fixtures"][label], {"path", "sha256"}, f"fixture {label}")
        if spec != {"path": relative, "sha256": expected_sha}:
            raise PortableVerificationError(f"fixture {label}: lock identity drifted")
        data = _read_regular(
            _locked_path(relative, f"fixture {label}"), f"fixture {label}"
        )
        if _sha(data) != expected_sha:
            raise PortableVerificationError(f"fixture {label}: byte hash mismatch")
        _strict_json(data, f"fixture {label}")
    return policy, snapshot


def _host_descriptor() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "operating_system": platform.system(),
        "operating_system_release": platform.release(),
        "machine": platform.machine(),
    }


def _select_anchor(
    directory: Path, buffers: Mapping[str, bytes]
) -> tuple[str, Mapping[str, Any]]:
    name = directory.name
    if name not in CANONICAL:
        manifest_sha = _sha(buffers["manifest.json"])
        matches = [
            key
            for key, value in CANONICAL.items()
            if value["files"]["manifest.json"][0] == manifest_sha
        ]
        if len(matches) != 1:
            raise PortableVerificationError(
                "artifact: not one of the two externally anchored bundles"
            )
        name = matches[0]
    anchor = CANONICAL[name]
    for filename, (expected_sha, expected_bytes) in anchor["files"].items():
        data = buffers[filename]
        if len(data) != expected_bytes or _sha(data) != expected_sha:
            raise PortableVerificationError(
                f"{filename}: external canonical anchor mismatch"
            )
    return name, anchor


def _validate_receipt(
    receipt: Any,
    *,
    payload: Mapping[str, Any],
    status: str,
    runtime: Mapping[str, Any],
    instructions_fingerprint: str,
    label: str,
) -> None:
    receipt = _exact(receipt, RECEIPT_KEYS, label)
    usage = _exact(receipt["usage"], USAGE_KEYS, f"{label}.usage")
    metadata = _exact(receipt["metadata"], METADATA_KEYS, f"{label}.metadata")
    if (
        receipt["provider"] != runtime["provider"]
        or receipt["requested_model"] != runtime["model"]
        or receipt["logical_calls"] != 1
        or receipt["api_calls"] != 1
        or receipt["request_fingerprint"] != _fingerprint(payload)
        or receipt["prompt_fingerprint"] != instructions_fingerprint
        or isinstance(receipt["latency_ms"], bool)
        or not isinstance(receipt["latency_ms"], (int, float))
        or not math.isfinite(float(receipt["latency_ms"]))
        or float(receipt["latency_ms"]) < 0.0
        or float(receipt["latency_ms"])
        > float(runtime["timeout_seconds"]) * 1000.0 + 5000.0
    ):
        raise PortableVerificationError(f"{label}: request/runtime binding drifted")
    token_keys = USAGE_KEYS - {"exact_provider_tokens"}
    exact_tokens = usage["exact_provider_tokens"]
    if (
        type(exact_tokens) is not bool
        or (
            exact_tokens and any(not _nonnegative_int(usage[key]) for key in token_keys)
        )
        or (not exact_tokens and any(usage[key] is not None for key in token_keys))
    ):
        raise PortableVerificationError(f"{label}: usage schema drifted")
    if (
        exact_tokens
        and usage["total_tokens"] != usage["input_tokens"] + usage["output_tokens"]
    ):
        raise PortableVerificationError(f"{label}: provider token accounting drifted")
    if (
        metadata["receipt_schema_version"] != "ebrt-provider-boundary-receipt-v0.4.3"
        or metadata["reasoning_effort"] != runtime["reasoning_effort"]
        or metadata["max_output_tokens"] != runtime["max_output_tokens"]
        or metadata["store"] is not runtime["store"]
        or metadata["previous_response_id"] is not runtime["previous_response_id"]
        or metadata["truncation"] != runtime["truncation"]
        or metadata["sdk_version"] != runtime["openai"]
        or metadata["pydantic_version"] != runtime["pydantic"]
        or metadata["python_version"] != runtime["python"]
        or metadata["attempt"] != 1
        or metadata["retry_count"] != 0
        or metadata["api_call_count_semantics"] != "attempted_client_call"
        or not _is_sha(metadata["client_request_id_sha256"])
        or not _is_sha(metadata["response_schema_fingerprint"])
        or not _is_sha(metadata["semantic_protocol_fingerprint"])
    ):
        raise PortableVerificationError(f"{label}: recorded runtime metadata drifted")
    outcome = metadata["attempt_outcome"]
    if status == "completed":
        if (
            outcome != "completed"
            or metadata["status"] != "completed"
            or metadata["http_observed"] is not True
            or metadata["http_status_code"] != 200
            or metadata["parse_boundary"] != "succeeded"
            or any(
                metadata[key] is not None
                for key in ("failure_phase", "failure_reason_code", "failure_type")
            )
            or receipt["returned_model"] != runtime["model"]
            or usage["exact_provider_tokens"] is not True
        ):
            raise PortableVerificationError(f"{label}: completed receipt drifted")
    elif status == "failed":
        if (
            outcome != "http_status_error"
            or metadata["status"] != "http_status_error"
            or metadata["http_observed"] is not True
            or not isinstance(metadata["http_status_code"], int)
            or metadata["http_status_code"] < 400
            or metadata["failure_phase"] != "http_status"
            or metadata["failure_reason_code"] != "insufficient_quota"
            or metadata["failure_type"] != "insufficient_quota"
            or metadata["parse_boundary"] != "not_entered"
        ):
            raise PortableVerificationError(f"{label}: failed receipt lineage drifted")
    else:
        raise PortableVerificationError(f"{label}: unsupported arm status")


def verify_artifact(
    artifact_dir: Path,
    *,
    host_descriptor: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if artifact_dir.is_symlink() or not artifact_dir.is_dir():
        raise PortableVerificationError("artifact directory must be a real directory")
    entries = {item.name for item in artifact_dir.iterdir()}
    if entries != FILE_SET:
        raise PortableVerificationError("artifact file set mismatch")
    buffers = {name: _read_regular(artifact_dir / name, name) for name in FILE_SET}
    canonical_id, anchor = _select_anchor(artifact_dir, buffers)
    policy, source_snapshot = _validate_policy()
    manifest = _strict_json(buffers["manifest.json"], "manifest.json")
    result = _strict_json(buffers["results.json"], "results.json")
    _exact(
        manifest,
        {
            "schema_version",
            "status",
            "success_manifest",
            "result_fingerprint_sha256",
            "policy_lock",
            "source_snapshot_sha256",
            "runtime",
            "artifacts",
            "claim_boundary",
        },
        "manifest",
    )
    if set(manifest["artifacts"]) != {"results.json", "calls.jsonl", "report.md"}:
        raise PortableVerificationError("manifest: artifact labels drifted")
    for name in ("results.json", "calls.jsonl", "report.md"):
        record = _exact(
            manifest["artifacts"][name], {"sha256", "bytes"}, f"manifest.{name}"
        )
        if record != {"sha256": _sha(buffers[name]), "bytes": len(buffers[name])}:
            raise PortableVerificationError(f"manifest: {name} digest drifted")
    if manifest["policy_lock"] != {
        "path": POLICY_RELATIVE_PATH,
        "sha256": POLICY_SHA256,
    }:
        raise PortableVerificationError("manifest: policy lock seal drifted")
    recorded = _exact(
        manifest["runtime"],
        {
            "python",
            "openai",
            "pydantic",
            "operating_system",
            "operating_system_release",
            "machine",
        },
        "manifest.runtime",
    )
    for key in ("python", "openai", "pydantic", "machine"):
        if recorded[key] != policy["runtime"][key]:
            raise PortableVerificationError(
                f"manifest: recorded runtime mismatch: {key}"
            )
    if manifest["source_snapshot_sha256"] != source_snapshot:
        raise PortableVerificationError("manifest: source snapshot drifted")
    if manifest["claim_boundary"] != policy["claim_boundary"]:
        raise PortableVerificationError("manifest: claim boundary drifted")
    material = copy.deepcopy(result)
    observed_fp = material.pop("fingerprint_sha256", None)
    if (
        observed_fp != _fingerprint(material)
        or observed_fp != anchor["result_fingerprint"]
    ):
        raise PortableVerificationError("results.json: result fingerprint drifted")
    _exact(
        result,
        {
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
        },
        "results.json",
    )
    if (
        result["schema_version"] != "ebrt-controlled-raw-restart-benchmark-v0.5.1"
        or result["mode"] != "openai_live_dev_canary"
        or result["status"] != anchor["status"]
        or manifest["status"] != anchor["status"]
        or manifest["success_manifest"] is not anchor["success_manifest"]
        or manifest["result_fingerprint_sha256"] != observed_fp
        or result["source_snapshot_sha256"] != source_snapshot
        or result["claim_boundary"] != RESULT_CLAIM_BOUNDARY
    ):
        raise PortableVerificationError("result/manifest frozen identity drifted")
    execution = _exact(
        result["execution"],
        {
            "arm_order",
            "expected_attempts",
            "observed_receipts",
            "observed_api_calls",
            "retry_policy",
            "semantic_gold_parsed_after_all_attempts",
        },
        "execution",
    )
    if (
        tuple(execution["arm_order"]) != ARM_ORDER
        or execution["expected_attempts"] != 4
        or execution["retry_policy"] != "one_attempt_no_retry"
        or execution["semantic_gold_parsed_after_all_attempts"] is not True
        or set(result["arms"]) != set(ARMS)
    ):
        raise PortableVerificationError("execution geometry drifted")
    expected_status = "completed" if anchor["status"] == "COMPLETE_CANARY" else "failed"
    expected_rows = []
    receipt_count = 0
    api_calls = 0
    for arm_id in ARM_ORDER:
        arm = result["arms"][arm_id]
        if not isinstance(arm, Mapping):
            raise PortableVerificationError(f"arm {arm_id}: not an object")
        if (
            arm.get("arm_id") != arm_id
            or arm.get("run_position") != ARM_ORDER.index(arm_id)
            or arm.get("status") != expected_status
            or arm.get("provider_input_fingerprint_sha256")
            != _fingerprint(arm.get("provider_input"))
        ):
            raise PortableVerificationError(f"arm {arm_id}: execution identity drifted")
        _validate_receipt(
            arm.get("receipt"),
            payload=arm["provider_input"],
            status=expected_status,
            runtime=policy["runtime"],
            instructions_fingerprint=policy["instructions_fingerprint_sha256"],
            label=f"arm {arm_id}.receipt",
        )
        receipt_count += 1
        api_calls += int(arm["receipt"]["api_calls"])
        if expected_status == "completed":
            if arm.get("failure") is not None or not isinstance(
                arm.get("final_card"), Mapping
            ):
                raise PortableVerificationError(
                    f"arm {arm_id}: completed shape drifted"
                )
        else:
            if (
                arm.get("final_card") is not None
                or arm.get("rejected_candidate_card") is not None
                or arm.get("observed_receipt_count") != 1
                or arm.get("failure")
                != {
                    "exception_class": "OpenAIProviderBoundaryError",
                    "category": "provider_boundary_error",
                    "reason_code": "insufficient_quota",
                }
            ):
                raise PortableVerificationError(f"arm {arm_id}: failed shape drifted")
        expected_rows.append(
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
    if (
        execution["observed_receipts"] != receipt_count
        or execution["observed_api_calls"] != api_calls
    ):
        raise PortableVerificationError("execution receipt/API accounting drifted")
    raw_lines = buffers["calls.jsonl"]
    expected_ledger = b"".join(_canonical(row) + b"\n" for row in expected_rows)
    if raw_lines != expected_ledger:
        raise PortableVerificationError("calls.jsonl: exact public ledger drifted")
    for index, line in enumerate(raw_lines.splitlines()):
        _strict_json(line, f"calls.jsonl line {index + 1}")
    decision = result["decision"]
    complete = expected_status == "completed"
    if (
        not isinstance(decision, Mapping)
        or decision.get("bridge_complete") is not complete
        or decision.get("promotion_eligible") is not False
        or (not complete and decision.get("strict_pass_arms") != [])
    ):
        raise PortableVerificationError("decision/accounting drifted")
    return {
        "status": "VALID_CANONICAL_ARTIFACT",
        "canonical_id": canonical_id,
        "artifact_status": result["status"],
        "success_manifest": manifest["success_manifest"],
        "result_fingerprint_sha256": observed_fp,
        "recorded_runtime": dict(recorded),
        "validator_host": dict(host_descriptor or _host_descriptor()),
        "validator_host_gated": False,
        "validation_boundary": (
            "canonical bytes, policy/source/fixture digests, recorded runtime/receipt "
            "lineage, result fingerprint, execution accounting, and calls ledger; "
            "no provider authentication or numerical surrogate reproduction"
        ),
    }


def _copy_bundle(source: Path, root: Path) -> Path:
    target = root / source.name
    shutil.copytree(source, target)
    return target


def _expect_rejected(label: str, callback: Any) -> str:
    try:
        callback()
    except PortableVerificationError as error:
        return f"{label}: {error}"
    raise AssertionError(f"tamper accepted: {label}")


def run_self_test() -> dict[str, Any]:
    canonical_paths = [ROOT / "artifacts" / name for name in CANONICAL]
    results = [verify_artifact(path) for path in canonical_paths]
    foreign = {
        "python": "0.0-foreign",
        "operating_system": "ForeignOS",
        "operating_system_release": "999",
        "machine": "s390x",
    }
    foreign_result = verify_artifact(canonical_paths[0], host_descriptor=foreign)
    if (
        foreign_result["validator_host"] != foreign
        or foreign_result["validator_host_gated"] is not False
    ):
        raise AssertionError("foreign-host diagnostic affected verification")
    checks: list[str] = [
        "both canonical bundles pass",
        "foreign host is diagnostic only",
    ]
    _expect_rejected("duplicate-key", lambda: _strict_json(b'{"a":1,"a":2}', "probe"))
    _expect_rejected("NaN", lambda: _strict_json(b'{"a":NaN}', "probe"))
    checks.extend(["duplicate JSON keys fail", "NaN fails"])
    with tempfile.TemporaryDirectory(prefix="ebrt-v051-portable-self-test-") as raw:
        temp = Path(raw)
        missing = _copy_bundle(canonical_paths[0], temp / "missing-root")
        (missing / "report.md").unlink()
        checks.append(
            _expect_rejected("missing-file", lambda: verify_artifact(missing))
        )
        extra = _copy_bundle(canonical_paths[0], temp / "extra-root")
        (extra / "extra.txt").write_text("tamper", encoding="utf-8")
        checks.append(_expect_rejected("extra-file", lambda: verify_artifact(extra)))
        symlink = _copy_bundle(canonical_paths[0], temp / "symlink-root")
        (symlink / "report.md").unlink()
        (symlink / "report.md").symlink_to(canonical_paths[0] / "report.md")
        checks.append(_expect_rejected("symlink", lambda: verify_artifact(symlink)))
        coherent = _copy_bundle(canonical_paths[1], temp / "coherent-root")
        result = _strict_json(
            (coherent / "results.json").read_bytes(), "coherent result"
        )
        result["decision"]["promotion_eligible"] = True
        material = copy.deepcopy(result)
        material.pop("fingerprint_sha256")
        result["fingerprint_sha256"] = _fingerprint(material)
        result_bytes = (
            json.dumps(
                result, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False
            )
            + "\n"
        ).encode()
        (coherent / "results.json").write_bytes(result_bytes)
        manifest = _strict_json(
            (coherent / "manifest.json").read_bytes(), "coherent manifest"
        )
        manifest["result_fingerprint_sha256"] = result["fingerprint_sha256"]
        manifest["artifacts"]["results.json"] = {
            "sha256": _sha(result_bytes),
            "bytes": len(result_bytes),
        }
        (coherent / "manifest.json").write_bytes(
            (
                json.dumps(
                    manifest,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                    allow_nan=False,
                )
                + "\n"
            ).encode()
        )
        checks.append(
            _expect_rejected("coherent-resign", lambda: verify_artifact(coherent))
        )
        ledger = _copy_bundle(canonical_paths[1], temp / "ledger-root")
        data = bytearray((ledger / "calls.jsonl").read_bytes())
        data[0] = ord("[")
        (ledger / "calls.jsonl").write_bytes(bytes(data))
        checks.append(_expect_rejected("ledger", lambda: verify_artifact(ledger)))
        runtime = _copy_bundle(canonical_paths[1], temp / "runtime-root")
        manifest = _strict_json(
            (runtime / "manifest.json").read_bytes(), "runtime manifest"
        )
        manifest["runtime"]["machine"] = "foreign"
        (runtime / "manifest.json").write_bytes(
            (
                json.dumps(
                    manifest,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                    allow_nan=False,
                )
                + "\n"
            ).encode()
        )
        checks.append(
            _expect_rejected("recorded-runtime", lambda: verify_artifact(runtime))
        )
    for path in canonical_paths:
        verify_artifact(path)
    return {
        "status": "PASS",
        "canonical_artifacts": [item["canonical_id"] for item in results],
        "checks": checks,
        "provider_calls": 0,
        "host_runtime_gated": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--artifact-dir", type=Path, required=True)
    sub.add_parser("self-test")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        output = (
            run_self_test()
            if args.command == "self-test"
            else verify_artifact(args.artifact_dir)
        )
    except PortableVerificationError as error:
        print(
            json.dumps(
                {"status": "INVALID", "error": str(error)}, indent=2, sort_keys=True
            )
        )
        return 1
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
