#!/usr/bin/env python3
"""Portable verifier for the frozen EBRT v0.6.1 five-call artifact.

This verifier was added after the live block.  It intentionally does not
import EBRT, OpenAI, Pydantic, or PyTorch modules; rebuild the v0.5.5
predecessor; execute local autograd; contact a provider; or compare the
producer runtime with the verification host.  It verifies the externally
pinned canonical bytes and the consistency of the recorded public evidence.

The original ``run_hosted_bundle_v0_6.py validate`` command remains an exact
producer-tree/runtime rederivation check.  It is not the portable verification
entrypoint once the repository's v0.5.5 implementation has evolved.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import platform
import shutil
import socket
import stat
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence
from unittest import mock


ROOT = Path(__file__).resolve().parent
POLICY_NAME = "policy_lock_hosted_bundle_v0_6.json"
ARTIFACT_RELATIVE = Path("artifacts/hosted_bundle_execution_v0_6_live_r01")
CALL_ORDER = ("P", "A", "B", "D", "C")

EXPECTED_POLICY = (
    6745,
    "9fb1ae9a9fe86e9ee1cde00de5dd8b286dc23092ebfb06affe3353c3c451e372",
)
EXPECTED_POLICY_FINGERPRINT = (
    "51bd00343dafb4dd9bc0c42dc95c1df1b6f8b7132907e283d84a82b237801072"
)
EXPECTED_RESULT_FINGERPRINT = (
    "a814b54a23faef07e301aa676411789cfb62154c07e5ad373f779ed67621954b"
)
EXPECTED_MANIFEST_FINGERPRINT = (
    "1c8d0c11bdef8a68f05923fbbe783264c252b0ae8004b835d2c6f165ebccb406"
)
EXPECTED_PROJECTION_FINGERPRINT = (
    "ba68204a556cebebe34cafaab10a8402d5b4f36d8018d43b9f51ab8a8f8a2f4a"
)
EXPECTED_PROVIDER_INPUTS_FINGERPRINT = (
    "78c78a3613046518cb4c9107e1f8ceb4334a96b1706eed452972c3e4b604a6fc"
)
EXPECTED_ARTIFACTS: dict[str, tuple[int, str]] = {
    "attempt_journal.jsonl": (
        32413,
        "9b3d82873d10e109d950e0f8a955fa5f7bbccbe1522520b1ae2d016b7b716450",
    ),
    "calls.jsonl": (
        9418,
        "35a099ba14661269cc4ebfd53ea8146961b1ed9993eca54177c46b4605277431",
    ),
    "manifest.json": (
        5033,
        "7554a796c1265734b882d86c990d10473658c72770262561f083177c9674893d",
    ),
    "projection_bundle.json": (
        206352,
        "09bd9130ce633a5099ca573b6a217442b4a9c8160f5ea9035af70e259e2c855a",
    ),
    "provider_inputs.json": (
        199588,
        "59830ccfa5058de41d443f180eafc25a86b9fc28b0d4c3de83274d3983fb029e",
    ),
    "report.md": (
        2481,
        "de8a723a4e0ada6860771fce1145094ff15ec13ef8c1b4307ae2e15ea2d009a2",
    ),
    "result.json": (
        74330,
        "0309dedd4cad1a637eb224333eb3bdc3944b853246874f61ccc5c10dec5c31be",
    ),
}
EXPECTED_V055_COMMIT = "7c94e3eddd70e17aa28213ca603004ad48611f2b"
EXPECTED_V055_TREE = "c89adcd3ecbe3bdead014065d4bb08d729a3ce35"
EXPECTED_V055_SOURCE_RECEIPTS = {
    "block_adjoint_file_sha256": (
        "4a63577a6b924acf35fe455194219aeda7d28875d67c5376843f68c32151f703"
    ),
    "control_bundle_file_sha256": (
        "d45c77ddfe3fc871ac35696e062bd21320d970fd962dc1c81569db93877f24e0"
    ),
    "manifest_file_sha256": (
        "f24409943cddcf857e997e5de16fff221feccf3954fee6c1db07dd984aa671b0"
    ),
}
EXPECTED_V055_LANE_RECEIPTS = {
    "correction_early": (
        "799b2d6b10129e63e751054e995d2e5017a2f73af44916d68068ee3c82b72d17"
    ),
    "correction_late": (
        "54c806a29fdf80f9677b5a008e140734e28a201e719a98ce8d312bf34298afc8"
    ),
    "stable_constraint": (
        "379e63f9bfce0af69df2240fe85835b7032efb0de3209773f71f818ba43f40cb"
    ),
}
MAX_FILE_BYTES = 1_000_000


class VerificationError(RuntimeError):
    """Raised when the frozen canonical snapshot does not validate."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def _reject_constant(value: str) -> Any:
    raise VerificationError(f"non-finite JSON constant is forbidden: {value}")


def _reject_duplicates(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise VerificationError(f"duplicate JSON key is forbidden: {key}")
        output[key] = value
    return output


def _strict_json_bytes(value: bytes, *, label: str) -> Any:
    try:
        text = value.decode("utf-8")
    except UnicodeDecodeError as error:
        raise VerificationError(f"{label} is not UTF-8") from error
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicates,
            parse_constant=_reject_constant,
        )
    except VerificationError:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise VerificationError(f"{label} is not strict JSON") from error


def _strict_json_lines(value: bytes, *, label: str) -> list[dict[str, Any]]:
    _require(value.endswith(b"\n"), f"{label} must end with one newline")
    lines = value.splitlines()
    _require(bool(lines), f"{label} is empty")
    output: list[dict[str, Any]] = []
    for index, line in enumerate(lines, start=1):
        parsed = _strict_json_bytes(line, label=f"{label}:{index}")
        _require(isinstance(parsed, dict), f"{label}:{index} must be an object")
        output.append(parsed)
    return output


def _canonical_bytes(value: Any, *, newline: bool = False) -> bytes:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return encoded + (b"\n" if newline else b"")


def _pretty_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _fingerprint(value: Any) -> str:
    return _sha256(_canonical_bytes(value))


def _without_fingerprint(value: Mapping[str, Any]) -> dict[str, Any]:
    output = copy.deepcopy(dict(value))
    output.pop("fingerprint_sha256", None)
    return output


def _seal(value: Mapping[str, Any]) -> dict[str, Any]:
    output = _without_fingerprint(value)
    output["fingerprint_sha256"] = _fingerprint(output)
    return output


def _validate_fingerprint(
    value: Mapping[str, Any], *, label: str, expected: str | None = None
) -> None:
    observed = value.get("fingerprint_sha256")
    _require(
        isinstance(observed, str)
        and observed == _fingerprint(_without_fingerprint(value)),
        f"{label} fingerprint drifted",
    )
    if expected is not None:
        _require(observed == expected, f"{label} canonical fingerprint drifted")


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _read_regular(path: Path, *, label: str, max_bytes: int = MAX_FILE_BYTES) -> bytes:
    try:
        before = path.lstat()
    except OSError as error:
        raise VerificationError(f"cannot stat {label}: {path}") from error
    _require(stat.S_ISREG(before.st_mode), f"{label} must be a regular file")
    _require(not path.is_symlink(), f"{label} must not be a symlink")
    _require(before.st_size <= max_bytes, f"{label} exceeds the size cap")
    try:
        value = path.read_bytes()
        after = path.lstat()
    except OSError as error:
        raise VerificationError(f"cannot read {label}: {path}") from error
    _require(
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
        f"{label} changed while being read",
    )
    _require(len(value) == before.st_size, f"{label} length changed while reading")
    return value


def _read_artifacts(artifact_dir: Path) -> dict[str, bytes]:
    try:
        root_stat = artifact_dir.lstat()
    except OSError as error:
        raise VerificationError(f"cannot stat artifact directory: {artifact_dir}") from error
    _require(stat.S_ISDIR(root_stat.st_mode), "artifact root must be a directory")
    _require(not artifact_dir.is_symlink(), "artifact root must not be a symlink")
    _require(
        sorted(path.name for path in artifact_dir.iterdir())
        == sorted(EXPECTED_ARTIFACTS),
        "artifact root entry set drifted",
    )
    observed: list[str] = []
    for path in artifact_dir.rglob("*"):
        _require(not path.is_symlink(), "artifact tree must not contain symlinks")
        if path.is_file():
            observed.append(str(path.relative_to(artifact_dir)))
    _require(sorted(observed) == sorted(EXPECTED_ARTIFACTS), "artifact file set drifted")
    output: dict[str, bytes] = {}
    for name, (expected_bytes, expected_hash) in EXPECTED_ARTIFACTS.items():
        raw = _read_regular(artifact_dir / name, label=f"artifact {name}")
        _require(len(raw) == expected_bytes, f"canonical byte count drifted: {name}")
        _require(_sha256(raw) == expected_hash, f"canonical SHA-256 drifted: {name}")
        output[name] = raw
    return output


def _recorded_source_snapshot(policy: Mapping[str, Any]) -> dict[str, str]:
    sources = policy.get("sources")
    predecessor = policy.get("predecessor_v0_5_2", {}).get("files")
    _require(isinstance(sources, Mapping), "policy sources are missing")
    _require(isinstance(predecessor, Mapping), "policy predecessor receipts are missing")
    output: dict[str, str] = {}
    for label, receipt in sources.items():
        _require(
            isinstance(receipt, Mapping)
            and set(receipt) == {"bytes", "path", "sha256"}
            and type(receipt["bytes"]) is int
            and receipt["bytes"] > 0
            and isinstance(receipt["path"], str)
            and _is_sha256(receipt["sha256"]),
            f"policy source receipt drifted: {label}",
        )
        output[f"sources:{label}"] = str(receipt["sha256"])
    for label, receipt in predecessor.items():
        _require(
            isinstance(receipt, Mapping)
            and set(receipt) == {"bytes", "path", "sha256"}
            and type(receipt["bytes"]) is int
            and receipt["bytes"] > 0
            and isinstance(receipt["path"], str)
            and _is_sha256(receipt["sha256"]),
            f"policy predecessor receipt drifted: {label}",
        )
        output[f"predecessor_v0_5_2:{label}"] = str(receipt["sha256"])
    return output


def _validate_policy(raw: bytes) -> dict[str, Any]:
    expected_bytes, expected_hash = EXPECTED_POLICY
    _require(len(raw) == expected_bytes, "policy canonical byte count drifted")
    _require(_sha256(raw) == expected_hash, "policy canonical SHA-256 drifted")
    policy = _strict_json_bytes(raw, label="policy lock")
    _require(isinstance(policy, dict), "policy root must be an object")
    _validate_fingerprint(
        policy, label="policy lock", expected=EXPECTED_POLICY_FINGERPRINT
    )
    _require(
        policy.get("schema_version") == "ebrt-hosted-bundle-policy-lock-v0.6.1"
        and policy.get("status") == "PREREGISTERED_FIVE_CALL_LIVE_BLOCK"
        and policy.get("call_order") == list(CALL_ORDER),
        "policy identity drifted",
    )
    _require(
        policy.get("artifact")
        == {
            "default_directory": str(ARTIFACT_RELATIVE),
            "files": [
                "result.json",
                "calls.jsonl",
                "attempt_journal.jsonl",
                "provider_inputs.json",
                "projection_bundle.json",
                "report.md",
                "manifest.json",
            ],
        },
        "policy artifact contract drifted",
    )
    runtime = policy.get("runtime")
    _require(
        isinstance(runtime, Mapping)
        and runtime.get("model") == "gpt-5.6-sol"
        and runtime.get("reasoning_effort") == "low"
        and runtime.get("sdk_retries") == 0
        and runtime.get("store") is False
        and runtime.get("previous_response_id") is False,
        "recorded producer runtime drifted",
    )
    _require(
        policy.get("predecessor_v0_5_2", {}).get(
            "expected_walkthrough_contract_passed"
        )
        is False,
        "frozen v0.5.2 endpoint drifted",
    )
    _recorded_source_snapshot(policy)
    return policy


def _validate_projection(bundle: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    _validate_fingerprint(
        bundle,
        label="projection bundle",
        expected=EXPECTED_PROJECTION_FINGERPRINT,
    )
    _require(
        bundle.get("schema_version") == "ebrt-hosted-bundle-projection-v0.6"
        and bundle.get("decision_status") == "READY_V0_6_1_FIVE_CALL_PREFLIGHT"
        and bundle.get("ready_for_live_lock") is True
        and bundle.get("network_calls") == 0
        and bundle.get("provider_calls") == 0,
        "projection identity drifted",
    )
    gates = bundle.get("gates")
    _require(
        isinstance(gates, Mapping)
        and bool(gates)
        and all(value is True for value in gates.values()),
        "projection gate drifted",
    )
    source_gate = bundle.get("source_gate")
    _require(isinstance(source_gate, Mapping), "projection source gate is missing")
    _validate_fingerprint(source_gate, label="recorded v0.5.5 source gate")
    _require(
        source_gate.get("status") == "PASS"
        and source_gate.get("network_calls") == 0
        and source_gate.get("provider_calls") == 0
        and source_gate.get("source_commit_sha") == EXPECTED_V055_COMMIT
        and source_gate.get("source_tree_sha") == EXPECTED_V055_TREE,
        "recorded v0.5.5 source identity drifted",
    )
    for key, expected in EXPECTED_V055_SOURCE_RECEIPTS.items():
        _require(source_gate.get(key) == expected, f"recorded v0.5.5 receipt drifted: {key}")
    _require(
        source_gate.get("lane_file_sha256") == EXPECTED_V055_LANE_RECEIPTS,
        "recorded v0.5.5 lane receipts drifted",
    )
    audit = bundle.get("matched_geometry_audit")
    _require(isinstance(audit, Mapping), "matched geometry audit is missing")
    _validate_fingerprint(audit, label="matched geometry audit")
    _require(
        audit.get("status") == "PASS"
        and audit.get("only_deterministic_placement_differs") is True,
        "matched geometry audit drifted",
    )
    treatment_key = bundle.get("public_treatment_key")
    _require(isinstance(treatment_key, Mapping), "public treatment key is missing")
    _validate_fingerprint(treatment_key, label="public treatment key")
    treatments = treatment_key.get("treatments")
    _require(
        isinstance(treatments, list)
        and [row.get("treatment_id") for row in treatments] == list(CALL_ORDER),
        "public treatment order drifted",
    )
    blind_order = [row.get("blinded_request_id") for row in treatments]
    _require(
        treatment_key.get("call_order_blinded_request_ids") == blind_order
        and len(set(blind_order)) == len(CALL_ORDER),
        "public treatment blinding drifted",
    )
    payload_rows = bundle.get("provider_payloads")
    _require(
        isinstance(payload_rows, list) and len(payload_rows) == len(CALL_ORDER),
        "projection provider payload set drifted",
    )
    by_blind: dict[str, Mapping[str, Any]] = {}
    for row in payload_rows:
        _require(
            isinstance(row, Mapping)
            and set(row) == {
                "blinded_request_id",
                "payload",
                "provider_payload_sha256",
            },
            "projection provider payload row drifted",
        )
        blind_id = row["blinded_request_id"]
        _require(
            isinstance(blind_id, str) and blind_id not in by_blind,
            "duplicate blinded request",
        )
        _require(
            row["provider_payload_sha256"] == _fingerprint(row["payload"]),
            "projection provider payload fingerprint drifted",
        )
        by_blind[blind_id] = row
    _require(set(by_blind) == set(blind_order), "projection blinded payload set drifted")
    for treatment in treatments:
        row = by_blind[treatment["blinded_request_id"]]
        _require(
            row["provider_payload_sha256"] == treatment["provider_payload_sha256"],
            "treatment-to-payload binding drifted",
        )
        evidence_ids = [
            item.get("evidence_id") for item in row["payload"].get("all_raw_evidence", [])
        ]
        _require(evidence_ids == treatment["evidence_horizon"], "evidence horizon drifted")
    return by_blind


def _validate_provider_inputs(
    provider_inputs: Mapping[str, Any],
    bundle: Mapping[str, Any],
    bundle_by_blind: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Mapping[str, Any]], dict[str, str]]:
    _validate_fingerprint(
        provider_inputs,
        label="provider inputs",
        expected=EXPECTED_PROVIDER_INPUTS_FINGERPRINT,
    )
    _require(
        provider_inputs.get("schema_version")
        == "ebrt-hosted-bundle-provider-inputs-v0.6.1"
        and provider_inputs.get("call_order") == list(CALL_ORDER),
        "provider inputs identity drifted",
    )
    rows = provider_inputs.get("payloads")
    _require(
        isinstance(rows, list)
        and [row.get("treatment_id") for row in rows] == list(CALL_ORDER),
        "provider input order drifted",
    )
    treatment_rows = {
        row["treatment_id"]: row
        for row in bundle["public_treatment_key"]["treatments"]
    }
    payloads: dict[str, Mapping[str, Any]] = {}
    blind_ids: dict[str, str] = {}
    for row in rows:
        _require(
            set(row)
            == {"blinded_request_id", "payload", "provider_payload_sha256", "treatment_id"},
            "provider input row schema drifted",
        )
        arm = row["treatment_id"]
        blind_id = row["blinded_request_id"]
        payload = row["payload"]
        _require(
            row["provider_payload_sha256"] == _fingerprint(payload),
            f"provider input fingerprint drifted: {arm}",
        )
        projected = bundle_by_blind.get(blind_id)
        _require(
            isinstance(projected, Mapping)
            and _canonical_bytes(projected["payload"]) == _canonical_bytes(payload)
            and projected["provider_payload_sha256"] == row["provider_payload_sha256"],
            f"provider input differs from frozen projection: {arm}",
        )
        treatment = treatment_rows[arm]
        _require(
            treatment["blinded_request_id"] == blind_id
            and treatment["provider_payload_sha256"] == row["provider_payload_sha256"],
            f"provider input treatment binding drifted: {arm}",
        )
        payloads[arm] = payload
        blind_ids[arm] = blind_id
    post_raw = [_canonical_bytes(payloads[arm]["all_raw_evidence"]) for arm in ("A", "B", "D", "C")]
    _require(len(set(post_raw)) == 1, "post-event raw histories are not byte-identical")
    _require(payloads["P"]["revision_program"] is None, "P revision program drifted")
    _require(payloads["A"]["revision_program"] is None, "A revision program drifted")
    _require(
        all(payloads[arm]["revision_program"] is not None for arm in ("B", "D", "C")),
        "controlled revision program is missing",
    )
    return payloads, blind_ids


def _validate_receipt(
    receipt: Mapping[str, Any],
    payload: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> None:
    _require(
        set(receipt)
        == {
            "api_calls",
            "latency_ms",
            "logical_calls",
            "metadata",
            "prompt_fingerprint",
            "provider",
            "request_fingerprint",
            "requested_model",
            "returned_model",
            "usage",
        },
        "provider receipt schema drifted",
    )
    runtime = policy["runtime"]
    _require(
        receipt["provider"] == runtime["provider"]
        and receipt["requested_model"] == runtime["model"]
        and receipt["returned_model"] == runtime["model"]
        and receipt["logical_calls"] == 1
        and receipt["api_calls"] == 1
        and receipt["request_fingerprint"] == _fingerprint(payload)
        and receipt["prompt_fingerprint"]
        == policy["instructions_fingerprint_sha256"],
        "provider receipt binding drifted",
    )
    latency = receipt["latency_ms"]
    _require(
        isinstance(latency, (int, float))
        and not isinstance(latency, bool)
        and math.isfinite(float(latency))
        and 0.0 <= float(latency) <= float(runtime["timeout_seconds"]) * 1000.0,
        "provider receipt latency drifted",
    )
    metadata = receipt["metadata"]
    _require(isinstance(metadata, Mapping), "provider receipt metadata is missing")
    response_schema = policy["response_schema_fingerprint_sha256"]
    expected_protocol = _fingerprint(
        {
            "model": runtime["model"],
            "instructions_fingerprint": policy["instructions_fingerprint_sha256"],
            "input_fingerprint": _fingerprint(payload),
            "text_schema_fingerprint": response_schema,
            "reasoning": {"effort": runtime["reasoning_effort"]},
            "max_output_tokens": runtime["max_output_tokens"],
            "store": False,
            "service_tier": runtime["service_tier"],
            "truncation": runtime["truncation"],
            # The provider boundary recorded this field from the historical
            # float constant (60.0); the policy presents the same limit as 60.
            "timeout_seconds": float(runtime["timeout_seconds"]),
        }
    )
    for key, expected in (
        ("sdk_version", runtime["openai"]),
        ("pydantic_version", runtime["pydantic"]),
        ("python_version", runtime["python"]),
        ("reasoning_effort", runtime["reasoning_effort"]),
        ("service_tier", runtime["service_tier"]),
        ("max_output_tokens", runtime["max_output_tokens"]),
        ("store", runtime["store"]),
        ("previous_response_id", runtime["previous_response_id"]),
        ("truncation", runtime["truncation"]),
        ("retry_count", runtime["sdk_retries"]),
        ("response_schema_fingerprint", response_schema),
        ("semantic_protocol_fingerprint", expected_protocol),
    ):
        _require(metadata.get(key) == expected, f"recorded receipt metadata drifted: {key}")
    _require(
        metadata.get("attempt") == 1
        and metadata.get("attempt_outcome") == "completed"
        and metadata.get("status") == "completed"
        and metadata.get("http_observed") is True
        and metadata.get("http_status_code") == 200
        and metadata.get("parse_boundary") == "succeeded"
        and metadata.get("failure_phase") is None
        and metadata.get("failure_reason_code") is None
        and metadata.get("failure_type") is None
        and metadata.get("refusal_count") == 0,
        "recorded receipt completion boundary drifted",
    )
    for key in (
        "client_request_id_sha256",
        "provider_body_sha256",
        "response_id_sha256",
        "server_request_id_sha256",
    ):
        _require(_is_sha256(metadata.get(key)), f"recorded receipt hash drifted: {key}")
    usage = receipt["usage"]
    expected_usage_keys = {
        "cache_write_tokens",
        "cached_input_tokens",
        "exact_provider_tokens",
        "input_tokens",
        "output_tokens",
        "reasoning_tokens",
        "total_tokens",
    }
    _require(
        isinstance(usage, Mapping)
        and set(usage) == expected_usage_keys
        and usage["exact_provider_tokens"] is True,
        "recorded provider usage schema drifted",
    )
    for key in expected_usage_keys - {"exact_provider_tokens"}:
        _require(type(usage[key]) is int and usage[key] >= 0, f"usage value drifted: {key}")
    _require(
        usage["total_tokens"] == usage["input_tokens"] + usage["output_tokens"]
        and usage["cached_input_tokens"] <= usage["input_tokens"]
        and usage["reasoning_tokens"] <= usage["output_tokens"],
        "provider usage arithmetic drifted",
    )


def _validate_preflight(
    preflight: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    payloads: Mapping[str, Mapping[str, Any]],
    bundle: Mapping[str, Any],
    source_snapshot: Mapping[str, str],
) -> None:
    _require(
        preflight.get("status") == "READY"
        and preflight.get("call_order") == list(CALL_ORDER)
        and preflight.get("expected_api_attempts") == 5,
        "recorded preflight identity drifted",
    )
    _require(
        preflight.get("source_snapshot_sha256") == source_snapshot,
        "recorded preflight source snapshot drifted",
    )
    _require(
        preflight.get("payload_fingerprints")
        == {arm: _fingerprint(payloads[arm]) for arm in CALL_ORDER},
        "recorded preflight payload fingerprints drifted",
    )
    projection_test = preflight.get("projection_self_test", {})
    _require(
        projection_test.get("status") == "PASS"
        and projection_test.get("network_calls") == 0
        and projection_test.get("provider_calls") == 0
        and projection_test.get("projection_fingerprint_sha256")
        == bundle["fingerprint_sha256"],
        "recorded projection self-test drifted",
    )
    lineage_test = preflight.get("lineage_self_test", {})
    provider_test = preflight.get("provider_self_test", {})
    transport_test = preflight.get("provider_transport_self_test", {})
    _require(
        lineage_test.get("status") == "PASS"
        and lineage_test.get("gold_loaded") is False
        and provider_test.get("status") == "PASS"
        and provider_test.get("network_calls") == 0
        and provider_test.get("provider_calls") == 0
        and transport_test.get("status") == "PASS"
        and transport_test.get("network_calls") == 0
        and transport_test.get("provider_calls") == 0,
        "recorded network-zero preflight checks drifted",
    )
    provider = preflight.get("provider")
    runtime = policy["runtime"]
    _require(
        isinstance(provider, Mapping)
        and provider.get("model") == runtime["model"]
        and provider.get("reasoning_effort") == runtime["reasoning_effort"]
        and provider.get("max_output_tokens") == runtime["max_output_tokens"]
        and provider.get("sdk_retries") == runtime["sdk_retries"]
        and provider.get("instructions_fingerprint_sha256")
        == policy["instructions_fingerprint_sha256"]
        and provider.get("response_schema_fingerprint_sha256")
        == policy["response_schema_fingerprint_sha256"],
        "recorded preflight provider contract drifted",
    )


def _validate_result(
    result: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    bundle: Mapping[str, Any],
    payloads: Mapping[str, Mapping[str, Any]],
    blind_ids: Mapping[str, str],
    calls_raw: bytes,
    journal_raw: bytes,
) -> None:
    _validate_fingerprint(
        result, label="result", expected=EXPECTED_RESULT_FINGERPRINT
    )
    source_snapshot = _recorded_source_snapshot(policy)
    _require(
        result.get("schema_version") == "ebrt-hosted-bundle-execution-v0.6.1"
        and result.get("mode") == "openai_live_hosted_bundle_v0_6_1"
        and result.get("call_order") == list(CALL_ORDER)
        and result.get("claim_boundary") == policy["claim_boundary"]
        and result.get("projection_fingerprint_sha256")
        == bundle["fingerprint_sha256"]
        and result.get("source_snapshot_sha256") == source_snapshot
        and result.get("lineage_gold_loaded_after_attempts") is True,
        "result identity drifted",
    )
    _validate_preflight(
        result["preflight"],
        policy=policy,
        payloads=payloads,
        bundle=bundle,
        source_snapshot=source_snapshot,
    )
    execution = result.get("execution")
    _require(
        isinstance(execution, Mapping)
        and execution.get("run_status") == "COMPLETE"
        and execution.get("unattempted_treatment_ids") == [],
        "execution completion drifted",
    )
    attempts = execution.get("attempts")
    outputs = execution.get("provider_outputs")
    compiled = execution.get("compiled_outputs")
    _require(
        isinstance(attempts, list)
        and [row.get("treatment_id") for row in attempts] == list(CALL_ORDER)
        and [row.get("run_position") for row in attempts] == [1, 2, 3, 4, 5]
        and isinstance(outputs, Mapping)
        and set(outputs) == set(CALL_ORDER)
        and isinstance(compiled, Mapping)
        and set(compiled) == set(CALL_ORDER),
        "execution attempt geometry drifted",
    )
    expected_calls: list[dict[str, Any]] = []
    expected_journal: list[dict[str, Any]] = []
    token_fields = (
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cached_input_tokens",
        "cache_write_tokens",
        "reasoning_tokens",
    )
    usage_totals = {key: 0 for key in token_fields}
    latency_total = 0.0
    for attempt in attempts:
        arm = attempt["treatment_id"]
        _require(
            attempt.get("status") == "COMPLETED"
            and attempt.get("blinded_request_id") == blind_ids[arm]
            and attempt.get("provider_input_fingerprint_sha256")
            == _fingerprint(payloads[arm]),
            f"attempt binding drifted: {arm}",
        )
        _require(
            attempt.get("provider_output_fingerprint_sha256")
            == _fingerprint(outputs[arm]),
            f"provider output fingerprint drifted: {arm}",
        )
        _validate_fingerprint(compiled[arm], label=f"compiled output {arm}")
        _require(
            attempt.get("compiled_output_fingerprint_sha256")
            == compiled[arm]["fingerprint_sha256"],
            f"compiled output binding drifted: {arm}",
        )
        _validate_receipt(attempt["receipt"], payloads[arm], policy)
        expected_calls.append(
            {
                "blinded_request_id": blind_ids[arm],
                "failure": None,
                "receipt": attempt["receipt"],
                "run_position": attempt["run_position"],
                "schema_version": "ebrt-hosted-bundle-call-receipt-v0.6.1",
                "status": "COMPLETED",
                "treatment_id": arm,
            }
        )
        expected_journal.append(
            {
                "attempt": attempt,
                "compiled_output": compiled[arm],
                "provider_output": outputs[arm],
                "schema_version": "ebrt-hosted-bundle-attempt-journal-v0.6.1",
            }
        )
        usage = attempt["receipt"]["usage"]
        for key in token_fields:
            usage_totals[key] += usage[key]
        latency_total += float(attempt["receipt"]["latency_ms"])
    _require(
        _strict_json_lines(calls_raw, label="calls.jsonl") == expected_calls,
        "calls ledger differs from result attempts",
    )
    _require(
        _strict_json_lines(journal_raw, label="attempt_journal.jsonl")
        == expected_journal,
        "attempt journal differs from result execution",
    )
    usage_expected = {
        "api_calls": 5,
        "exact_provider_tokens": True,
        "latency_ms": latency_total,
        "logical_calls": 5,
        **usage_totals,
    }
    _require(result.get("usage") == usage_expected, "aggregate usage drifted")
    grades = result.get("grades")
    _require(isinstance(grades, Mapping) and set(grades) == set(CALL_ORDER), "grade set drifted")
    for arm in CALL_ORDER:
        _validate_fingerprint(grades[arm], label=f"grade {arm}")
        _require(
            grades[arm].get("compiled_fingerprint_sha256")
            == compiled[arm]["fingerprint_sha256"],
            f"grade-to-compiled binding drifted: {arm}",
        )
    _validate_fingerprint(result["stale_regrade"], label="P stale regrade")
    _require(
        {arm: grades[arm]["status"] for arm in CALL_ORDER}
        == {"P": "FAIL", "A": "FAIL", "B": "PASS", "D": "PASS", "C": "PASS"},
        "frozen strict grade outcomes drifted",
    )
    _require(
        outputs["P"]["current_answer"] == "POLISH"
        and all(outputs[arm]["current_answer"] == "PROVE" for arm in ("A", "B", "D", "C")),
        "frozen answer outcomes drifted",
    )
    _require(
        _canonical_bytes(outputs["B"])
        == _canonical_bytes(outputs["D"])
        == _canonical_bytes(outputs["C"])
        and _canonical_bytes(compiled["B"])
        == _canonical_bytes(compiled["D"])
        == _canonical_bytes(compiled["C"]),
        "frozen B/D/C identity observation drifted",
    )
    decision = result.get("decision")
    _require(
        decision
        == {
            "d_strict_status": "PASS",
            "decision_status": "HOLD_V0_6_HOSTED_BUNDLE_GATE",
            "effect_by_comparator": {
                "D_vs_A": "POSITIVE",
                "D_vs_B": "NULL",
                "D_vs_C": "NULL",
            },
            "effect_primary_contrast": "D_vs_C_matched_placement",
            "effect_status": "NULL",
            "p_pre_event_status": "FAIL",
            "p_stale_status": "FAIL",
            "promotion_ready": False,
            "run_status": "COMPLETE",
            "surrogate_status": "PASS",
        },
        "frozen decision outcome drifted",
    )


def _validate_manifest(
    manifest: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    result: Mapping[str, Any],
    files: Mapping[str, bytes],
) -> None:
    _validate_fingerprint(
        manifest, label="manifest", expected=EXPECTED_MANIFEST_FINGERPRINT
    )
    expected_non_manifest = set(EXPECTED_ARTIFACTS) - {"manifest.json"}
    _require(
        manifest.get("schema_version") == "ebrt-hosted-bundle-manifest-v0.6.1"
        and manifest.get("call_order") == list(CALL_ORDER)
        and manifest.get("claim_boundary") == policy["claim_boundary"]
        and manifest.get("decision_status") == "HOLD_V0_6_HOSTED_BUNDLE_GATE"
        and manifest.get("policy_lock_fingerprint_sha256")
        == policy["fingerprint_sha256"]
        and manifest.get("result_fingerprint_sha256")
        == result["fingerprint_sha256"]
        and manifest.get("runtime") == policy["runtime"]
        and manifest.get("source_snapshot_sha256")
        == _recorded_source_snapshot(policy),
        "manifest identity drifted",
    )
    records = manifest.get("artifacts")
    _require(
        isinstance(records, Mapping) and set(records) == expected_non_manifest,
        "manifest artifact table drifted",
    )
    for name in expected_non_manifest:
        _require(
            records[name] == {"bytes": len(files[name]), "sha256": _sha256(files[name])},
            f"manifest artifact receipt drifted: {name}",
        )


def _observed_host_runtime() -> dict[str, str]:
    return {"machine": platform.machine(), "python": sys.version.split()[0]}


def verify_snapshot(
    *,
    repo_root: Path = ROOT,
    artifact_dir: Path | None = None,
    observed_host_runtime: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Verify the recorded canonical snapshot without producer rederivation."""

    # Keep the final path component unresolved so the regular-file and
    # artifact-root symlink checks remain meaningful.
    repo_root = repo_root.absolute()
    artifact_dir = (
        (repo_root / ARTIFACT_RELATIVE)
        if artifact_dir is None
        else artifact_dir.absolute()
    )
    policy_raw = _read_regular(repo_root / POLICY_NAME, label="policy lock")
    policy = _validate_policy(policy_raw)
    files = _read_artifacts(artifact_dir)
    manifest = _strict_json_bytes(files["manifest.json"], label="manifest.json")
    result = _strict_json_bytes(files["result.json"], label="result.json")
    bundle = _strict_json_bytes(
        files["projection_bundle.json"], label="projection_bundle.json"
    )
    provider_inputs = _strict_json_bytes(
        files["provider_inputs.json"], label="provider_inputs.json"
    )
    _require(
        all(isinstance(value, dict) for value in (manifest, result, bundle, provider_inputs)),
        "canonical JSON roots must be objects",
    )
    bundle_by_blind = _validate_projection(bundle)
    payloads, blind_ids = _validate_provider_inputs(
        provider_inputs, bundle, bundle_by_blind
    )
    _validate_result(
        result,
        policy=policy,
        bundle=bundle,
        payloads=payloads,
        blind_ids=blind_ids,
        calls_raw=files["calls.jsonl"],
        journal_raw=files["attempt_journal.jsonl"],
    )
    _validate_manifest(
        manifest, policy=policy, result=result, files=files
    )
    observed = dict(observed_host_runtime or _observed_host_runtime())
    producer = policy["runtime"]
    comparable = {
        key: observed.get(key) == producer.get(key) for key in ("python", "machine")
    }
    return {
        "artifact_directory": str(artifact_dir),
        "canonical_manifest_sha256": EXPECTED_ARTIFACTS["manifest.json"][1],
        "canonical_policy_sha256": EXPECTED_POLICY[1],
        "canonical_result_fingerprint_sha256": EXPECTED_RESULT_FINGERPRINT,
        "current_v0_5_5_sources_read": False,
        "historical_rederivation_performed": False,
        "host_runtime_comparison": comparable,
        "host_runtime_match_is_gate": False,
        "network_calls": 0,
        "producer_runtime": copy.deepcopy(producer),
        "schema_version": "ebrt-hosted-bundle-portable-verification-v0.6.1",
        "status": "VALID_CANONICAL_ARTIFACT",
        "validation_mode": "portable_recorded_snapshot",
        "verification_host": observed,
    }


@contextmanager
def _network_zero_guard() -> Iterator[dict[str, int]]:
    counts = {"socket": 0, "connection": 0}

    def blocked_socket(*args: Any, **kwargs: Any) -> Any:
        counts["socket"] += 1
        raise AssertionError("portable verifier attempted socket creation")

    def blocked_connection(*args: Any, **kwargs: Any) -> Any:
        counts["connection"] += 1
        raise AssertionError("portable verifier attempted a network connection")

    with mock.patch.object(socket, "socket", side_effect=blocked_socket), mock.patch.object(
        socket, "create_connection", side_effect=blocked_connection
    ):
        yield counts


def _expect_rejected(action: Any, label: str) -> None:
    try:
        action()
    except VerificationError:
        return
    raise VerificationError(f"self-test tamper was accepted: {label}")


def _copy_canonical_snapshot(destination: Path) -> tuple[Path, Path]:
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / POLICY_NAME, destination / POLICY_NAME)
    artifact = destination / ARTIFACT_RELATIVE
    artifact.parent.mkdir(parents=True)
    shutil.copytree(ROOT / ARTIFACT_RELATIVE, artifact)
    return destination, artifact


def self_test() -> dict[str, Any]:
    checks: dict[str, bool] = {}
    with _network_zero_guard() as network_counts:
        canonical = verify_snapshot()
        checks["canonical_snapshot_passes"] = (
            canonical["status"] == "VALID_CANONICAL_ARTIFACT"
        )
        with tempfile.TemporaryDirectory(prefix="ebrt-v061-portable-") as temp_name:
            isolated_root, isolated_artifact = _copy_canonical_snapshot(Path(temp_name))
            foreign = verify_snapshot(
                repo_root=isolated_root,
                artifact_dir=isolated_artifact,
                observed_host_runtime={"machine": "foreign-architecture", "python": "0.0.0"},
            )
            checks["foreign_host_is_non_gating"] = (
                foreign["status"] == "VALID_CANONICAL_ARTIFACT"
                and foreign["host_runtime_match_is_gate"] is False
                and not all(foreign["host_runtime_comparison"].values())
            )
            checks["producer_source_tree_is_not_required"] = not any(
                (isolated_root / name).exists()
                for name in (
                    "lane_composable_trajectory_v0_5_5.py",
                    "benchmark_lane_composition_v0_5_5.py",
                    "hosted_bundle_projection_v0_6.py",
                )
            )

        tamper_rejections: list[str] = []
        for name in sorted(EXPECTED_ARTIFACTS):
            with tempfile.TemporaryDirectory(prefix="ebrt-v061-tamper-") as temp_name:
                test_root, test_artifact = _copy_canonical_snapshot(Path(temp_name))
                target = test_artifact / name
                raw = target.read_bytes()
                target.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
                _expect_rejected(
                    lambda: verify_snapshot(repo_root=test_root, artifact_dir=test_artifact),
                    name,
                )
                tamper_rejections.append(name)
        with tempfile.TemporaryDirectory(prefix="ebrt-v061-policy-") as temp_name:
            test_root, test_artifact = _copy_canonical_snapshot(Path(temp_name))
            target = test_root / POLICY_NAME
            raw = target.read_bytes()
            target.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
            _expect_rejected(
                lambda: verify_snapshot(repo_root=test_root, artifact_dir=test_artifact),
                "policy lock",
            )
            tamper_rejections.append("policy lock")
        with tempfile.TemporaryDirectory(prefix="ebrt-v061-coherent-") as temp_name:
            test_root, test_artifact = _copy_canonical_snapshot(Path(temp_name))
            result_path = test_artifact / "result.json"
            result = _strict_json_bytes(result_path.read_bytes(), label="test result")
            result["decision"]["decision_status"] = "FORGED_PROMOTION"
            result = _seal(result)
            result_path.write_bytes(_pretty_bytes(result))
            manifest_path = test_artifact / "manifest.json"
            manifest = _strict_json_bytes(manifest_path.read_bytes(), label="test manifest")
            manifest["decision_status"] = "FORGED_PROMOTION"
            manifest["result_fingerprint_sha256"] = result["fingerprint_sha256"]
            manifest["artifacts"]["result.json"] = {
                "bytes": len(result_path.read_bytes()),
                "sha256": _sha256(result_path.read_bytes()),
            }
            manifest = _seal(manifest)
            manifest_path.write_bytes(_pretty_bytes(manifest))
            _expect_rejected(
                lambda: verify_snapshot(repo_root=test_root, artifact_dir=test_artifact),
                "coherent result/manifest resign",
            )
            tamper_rejections.append("coherent result/manifest resign")
        with tempfile.TemporaryDirectory(prefix="ebrt-v061-extra-") as temp_name:
            test_root, test_artifact = _copy_canonical_snapshot(Path(temp_name))
            (test_artifact / "unexpected.txt").write_bytes(b"unexpected\n")
            _expect_rejected(
                lambda: verify_snapshot(repo_root=test_root, artifact_dir=test_artifact),
                "extra artifact entry",
            )
            tamper_rejections.append("extra artifact entry")
        with tempfile.TemporaryDirectory(prefix="ebrt-v061-symlink-") as temp_name:
            test_root, test_artifact = _copy_canonical_snapshot(Path(temp_name))
            target = test_artifact / "report.md"
            target.unlink()
            target.symlink_to(ROOT / ARTIFACT_RELATIVE / "report.md")
            _expect_rejected(
                lambda: verify_snapshot(repo_root=test_root, artifact_dir=test_artifact),
                "artifact symlink",
            )
            tamper_rejections.append("artifact symlink")
        checks["all_canonical_byte_tampering_rejected"] = set(tamper_rejections) == (
            set(EXPECTED_ARTIFACTS)
            | {
                "policy lock",
                "coherent result/manifest resign",
                "extra artifact entry",
                "artifact symlink",
            }
        )
        _expect_rejected(
            lambda: _strict_json_bytes(b'{"a":1,"a":2}', label="duplicate test"),
            "duplicate JSON key",
        )
        _expect_rejected(
            lambda: _strict_json_bytes(b'{"a":NaN}', label="non-finite test"),
            "non-finite JSON",
        )
        checks["strict_json_attacks_rejected"] = True
    checks["network_calls_zero"] = sum(network_counts.values()) == 0
    _require(all(checks.values()), "portable verifier self-test failed")
    return {
        "checks": checks,
        "current_v0_5_5_sources_read": False,
        "historical_rederivation_performed": False,
        "host_runtime_match_is_gate": False,
        "network_calls": sum(network_counts.values()),
        "schema_version": "ebrt-hosted-bundle-portable-verifier-self-test-v0.6.1",
        "status": "PASS",
        "tamper_rejections": tamper_rejections,
    }


def _print_json(value: Mapping[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--repo-root", type=Path, default=ROOT)
    verify_parser.add_argument("--artifact-dir", type=Path)
    subparsers.add_parser("self-test")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "verify":
        _print_json(
            verify_snapshot(
                repo_root=args.repo_root,
                artifact_dir=args.artifact_dir,
            )
        )
    elif args.command == "self-test":
        _print_json(self_test())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
