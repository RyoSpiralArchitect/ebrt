#!/usr/bin/env python3
"""Pure-stdlib verifier for the frozen EBRT v0.6.3 zero-call artifact.

This program does not import the producer, Pydantic, PyTorch, or any provider
SDK.  It verifies the checked-in policy, source receipts, artifact receipts,
internal fingerprints, hard gates, and all sixteen blinded provider payloads.
It never rebuilds the artifact and never opens a network connection.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import stat
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parent
POLICY_RELATIVE = Path("policy_lock_actuator_calibration_v0_6_3.json")
ARTIFACT_RELATIVE = Path("artifacts/actuator_calibration_v0_6_3_preflight")
MAX_FILE_BYTES = 2_000_000
EXPECTED_POLICY_FILE = (
    5306,
    "ea851d9f8298c608e926e62695425b78c7e7ce265f36217d69b3e3e9d9a48dcc",
)
EXPECTED_MANIFEST_FILE = (
    3961,
    "334c5b2840b8565e889c53dd35b866676a1fc58cdb978882a7b05c8a1f48503a",
)
EXPECTED_POLICY_FINGERPRINT = (
    "e72546b5689dabd4fc4684d53e58884707c1e8c53ee26d3044a7e528d40fe639"
)
EXPECTED_MANIFEST_FINGERPRINT = (
    "c924af71cfa24f991b84e9c98b0b19d36b02788b12d89faaec46a7821ae349d2"
)

POLICY_SCHEMA = "ebrt-actuator-calibration-policy-lock-v0.6.3"
MANIFEST_SCHEMA = "ebrt-actuator-calibration-preflight-manifest-v0.6.3"
PROJECTION_SCHEMA = "ebrt-actuator-calibration-projection-v0.6.3"
PROVIDER_INPUT_SCHEMA = "ebrt-actuator-calibration-provider-input-v0.6.3"
SELF_TEST_SCHEMA = "ebrt-actuator-calibration-self-test-v0.6.3"
CONTROLLER_BUNDLE_SCHEMA = "ebrt-actuator-calibration-controller-bundle-v0.6.3"
SCHEDULE_SCHEMA = "ebrt-bounded-reinspection-schedule-v0.6.3"

POLICY_STATUS = "LOCKED_NETWORK_ZERO_PREFLIGHT_NO_LIVE_AUTHORIZATION"
MANIFEST_STATUS = "READY_ZERO_CALL_PREFLIGHT_ONLY"
PROJECTION_STATUS = "READY_NETWORK_ZERO_ACTUATOR_PREFLIGHT"
SELF_TEST_STATUS = "PASS_NETWORK_ZERO"
HANDOFF_STATUS = "AWAIT_EXPLICIT_LIVE_AUTHORIZATION"
OPERATOR = "bounded_reinspection_schedule"
ARMS = ("Z", "C", "D", "X")

ARTIFACT_FILES = frozenset(
    {
        "projection_bundle.json",
        "controller_audit.json",
        "self_test.json",
        "manifest.json",
    }
)
RECEIPTED_ARTIFACT_FILES = ARTIFACT_FILES - {"manifest.json"}
SOURCE_RECEIPT_IDS = frozenset(
    {"core", "fixture", "post_call_gold", "protocol_note", "requirements"}
)
HARD_GATE_IDS = frozenset(
    {
        "strict_fixture_contract",
        "symmetric_candidate_universe",
        "real_float64_backward",
        "central_finite_difference_agreement",
        "unit_l1_polarities",
        "opposite_case_positive_controls",
        "z_true_no_reordering",
        "matched_schedule_geometry",
        "c_eligible_derangement",
        "d_input_alignment_exceeds_c",
        "provider_payloads_leak_free",
        "non_actuator_payload_fields_matched",
        "williams_four_block_balance",
        "sixteen_payloads_presealed",
        "exact_one_closure_enforced",
        "inspection_receipt_excluded_from_alignment",
        "p0_p1_alignment_arithmetic_exact",
        "output_contract_roundtrip",
        "deterministic_double_projection",
        "network_calls_zero",
    }
)
FORBIDDEN_PROVIDER_KEYS = frozenset(
    {
        "accepted_edge_ids",
        "accepted_edges",
        "answer",
        "answer_key",
        "arm",
        "arm_id",
        "correct_answer",
        "treatment_id",
        "blinded_request_id",
        "effect_by_evidence_id",
        "expected_closure",
        "expected_closures",
        "q_d",
        "q_x",
        "polarity",
        "gradient",
        "controller",
        "local_controller",
        "closure_contract",
        "equivalence_classes",
        "valid_necessary_support_closures",
        "expected_answer",
        "preferred_path",
        "terminal_target",
        "valid_closure",
        "valid_closures",
        "gold",
        "grade",
        "sham",
    }
)


class VerificationError(RuntimeError):
    """Raised on any receipt, schema, or semantic contract failure."""


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
        parsed = json.loads(
            text,
            object_pairs_hook=_reject_duplicates,
            parse_constant=_reject_constant,
        )
    except VerificationError:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise VerificationError(f"{label} is not strict JSON") from error
    _reject_nonfinite_numbers(parsed, label=label)
    return parsed


def _reject_nonfinite_numbers(value: Any, *, label: str) -> None:
    if isinstance(value, float):
        _require(math.isfinite(value), f"{label} contains a non-finite number")
    elif isinstance(value, Mapping):
        for child in value.values():
            _reject_nonfinite_numbers(child, label=label)
    elif isinstance(value, list):
        for child in value:
            _reject_nonfinite_numbers(child, label=label)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _pretty_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _fingerprint(value: Any) -> str:
    return _sha256(_canonical_bytes(value))


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _without_fingerprint(value: Mapping[str, Any]) -> dict[str, Any]:
    output = copy.deepcopy(dict(value))
    output.pop("fingerprint_sha256", None)
    return output


def _validate_fingerprint(value: Mapping[str, Any], *, label: str) -> None:
    observed = value.get("fingerprint_sha256")
    _require(
        _is_sha256(observed) and observed == _fingerprint(_without_fingerprint(value)),
        f"{label} fingerprint drifted",
    )


def _validate_canonical_anchor(
    raw: bytes,
    value: Mapping[str, Any],
    *,
    expected_file: tuple[int, str],
    expected_fingerprint: str,
    label: str,
) -> None:
    expected_bytes, expected_sha256 = expected_file
    _require(len(raw) == expected_bytes, f"{label} canonical byte count drifted")
    _require(_sha256(raw) == expected_sha256, f"{label} canonical file SHA-256 drifted")
    _require(
        value.get("fingerprint_sha256") == expected_fingerprint,
        f"{label} canonical internal fingerprint drifted",
    )


def _validate_nested_fingerprints(value: Any, *, label: str) -> int:
    count = 0
    if isinstance(value, Mapping):
        if "fingerprint_sha256" in value:
            _validate_fingerprint(value, label=label)
            count += 1
        for key, child in value.items():
            count += _validate_nested_fingerprints(child, label=f"{label}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            count += _validate_nested_fingerprints(child, label=f"{label}[{index}]")
    return count


def _read_regular(path: Path, *, label: str) -> bytes:
    try:
        before = path.lstat()
    except OSError as error:
        raise VerificationError(f"cannot stat {label}: {path}") from error
    _require(stat.S_ISREG(before.st_mode), f"{label} must be a regular file")
    _require(not path.is_symlink(), f"{label} must not be a symlink")
    _require(before.st_size <= MAX_FILE_BYTES, f"{label} exceeds the size cap")
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


def _strict_object(path: Path, *, label: str) -> tuple[bytes, dict[str, Any]]:
    raw = _read_regular(path, label=label)
    value = _strict_json_bytes(raw, label=label)
    _require(isinstance(value, dict), f"{label} root must be an object")
    _require(raw == _pretty_bytes(value), f"{label} is not canonical pretty JSON")
    return raw, value


def _validate_receipt(
    receipt: Any, *, path: Path, expected_relative: str, label: str
) -> None:
    _require(
        isinstance(receipt, Mapping) and set(receipt) == {"path", "bytes", "sha256"},
        f"{label} receipt schema drifted",
    )
    _require(receipt["path"] == expected_relative, f"{label} receipt path drifted")
    _require(
        type(receipt["bytes"]) is int and receipt["bytes"] >= 0,
        f"{label} bytes invalid",
    )
    _require(_is_sha256(receipt["sha256"]), f"{label} SHA-256 invalid")
    raw = _read_regular(path, label=label)
    _require(len(raw) == receipt["bytes"], f"{label} byte receipt drifted")
    _require(_sha256(raw) == receipt["sha256"], f"{label} SHA-256 receipt drifted")


def _safe_relative(root: Path, relative: Any, *, label: str) -> tuple[str, Path]:
    _require(isinstance(relative, str) and relative, f"{label} path is invalid")
    candidate = Path(relative)
    _require(
        not candidate.is_absolute() and ".." not in candidate.parts,
        f"{label} path escapes root",
    )
    resolved_root = root.resolve()
    resolved = (root / candidate).resolve()
    _require(
        resolved == resolved_root or resolved_root in resolved.parents,
        f"{label} path escapes root",
    )
    return candidate.as_posix(), root / candidate


def _recursive_keys(value: Any) -> set[str]:
    output: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            output.add(str(key))
            output.update(_recursive_keys(child))
    elif isinstance(value, list):
        for child in value:
            output.update(_recursive_keys(child))
    return output


def _validate_policy(root: Path, policy: Mapping[str, Any]) -> None:
    _validate_fingerprint(policy, label="policy")
    _require(
        set(policy)
        == {
            "artifact",
            "canonicalization",
            "claim_boundary",
            "fingerprint_sha256",
            "protocol",
            "runtime_contract",
            "schema_version",
            "sources",
            "status",
        },
        "policy top-level keyset drifted",
    )
    _require(policy.get("schema_version") == POLICY_SCHEMA, "policy schema drifted")
    _require(policy.get("status") == POLICY_STATUS, "policy status drifted")
    canonical = policy.get("canonicalization")
    _require(
        canonical
        == {
            "allow_nan": False,
            "encoding": "utf-8",
            "ensure_ascii": False,
            "separators": [",", ":"],
            "sort_keys": True,
            "trailing_newline": True,
        },
        "policy canonicalization contract drifted",
    )
    artifact = policy.get("artifact")
    _require(isinstance(artifact, Mapping), "policy artifact contract missing")
    _require(
        artifact.get("directory") == ARTIFACT_RELATIVE.as_posix(),
        "artifact directory drifted",
    )
    _require(
        artifact.get("files")
        == [
            "projection_bundle.json",
            "controller_audit.json",
            "self_test.json",
            "manifest.json",
        ],
        "artifact file list drifted",
    )
    _require(
        type(artifact.get("provider_calls")) is int
        and artifact["provider_calls"] == 0
        and type(artifact.get("network_calls")) is int
        and artifact["network_calls"] == 0,
        "policy calls are nonzero",
    )
    runtime = policy.get("runtime_contract")
    _require(
        isinstance(runtime, Mapping)
        and type(runtime.get("provider_calls_authorized")) is int
        and runtime["provider_calls_authorized"] == 0,
        "policy authorizes provider calls",
    )
    protocol = policy.get("protocol")
    _require(isinstance(protocol, Mapping), "policy protocol missing")
    _require(
        set(protocol.get("hard_gate_ids", ())) == HARD_GATE_IDS,
        "policy hard-gate keyset drifted",
    )
    _require(
        protocol.get("provider_payload_count") == 16, "policy payload count drifted"
    )
    sources = policy.get("sources")
    _require(
        isinstance(sources, Mapping) and set(sources) == SOURCE_RECEIPT_IDS,
        "policy source receipt set drifted",
    )
    for source_name, receipt in sources.items():
        _require(isinstance(receipt, Mapping), f"source {source_name} receipt invalid")
        relative, path = _safe_relative(
            root, receipt.get("path"), label=f"source {source_name}"
        )
        _validate_receipt(
            receipt,
            path=path,
            expected_relative=relative,
            label=f"source {source_name}",
        )


def _validate_hard_gates(
    *,
    policy: Mapping[str, Any],
    manifest: Mapping[str, Any],
    self_test: Mapping[str, Any],
) -> None:
    expected_order = policy["protocol"]["hard_gate_ids"]
    _require(
        len(expected_order) == 20 and len(set(expected_order)) == 20,
        "policy must list exactly 20 unique hard gates",
    )
    _require(set(expected_order) == HARD_GATE_IDS, "policy hard-gate keyset drifted")
    _require(
        self_test.get("hard_gate_ids") == expected_order,
        "self-test hard-gate order drifted",
    )
    for label, gates in (
        ("manifest", manifest.get("hard_gates")),
        ("self-test", self_test.get("hard_gates")),
    ):
        _require(isinstance(gates, Mapping), f"{label} hard gates missing")
        _require(
            set(gates) == HARD_GATE_IDS and len(gates) == 20,
            f"{label} hard-gate keyset drifted",
        )
        _require(
            all(value is True for value in gates.values()),
            f"{label} contains a non-passing hard gate",
        )
    _require(
        manifest["hard_gates"] == self_test["hard_gates"],
        "manifest/self-test hard gates differ",
    )


def _validate_provider_payloads(projection: Mapping[str, Any]) -> None:
    payload_rows = projection.get("provider_payloads")
    treatment_rows = projection.get("public_treatment_key")
    _require(
        isinstance(payload_rows, list) and len(payload_rows) == 16,
        "projection must contain 16 provider payloads",
    )
    _require(
        isinstance(treatment_rows, list) and len(treatment_rows) == 16,
        "projection must contain 16 treatment rows",
    )
    payload_by_id: dict[str, str] = {}
    for index, row in enumerate(payload_rows):
        _require(
            isinstance(row, Mapping)
            and set(row)
            == {"blinded_request_id", "payload", "provider_payload_sha256"},
            f"provider payload row {index} schema drifted",
        )
        request_id = row["blinded_request_id"]
        payload = row["payload"]
        payload_sha = row["provider_payload_sha256"]
        _require(
            isinstance(request_id, str)
            and request_id.startswith("req-")
            and len(request_id) == 28
            and request_id not in payload_by_id,
            f"provider payload row {index} blind ID invalid",
        )
        _require(
            isinstance(payload, Mapping),
            f"provider payload row {index} payload invalid",
        )
        _require(
            payload.get("schema_version") == PROVIDER_INPUT_SCHEMA,
            f"provider payload row {index} schema drifted",
        )
        _require(
            _is_sha256(payload_sha) and payload_sha == _fingerprint(payload),
            f"provider payload row {index} hash drifted",
        )
        leaked = _recursive_keys(payload) & FORBIDDEN_PROVIDER_KEYS
        _require(
            not leaked,
            f"provider payload row {index} leaks private keys: {sorted(leaked)}",
        )
        schedule = payload.get("revision_actuator")
        _require(
            isinstance(schedule, Mapping),
            f"provider payload row {index} schedule missing",
        )
        _validate_fingerprint(schedule, label=f"provider payload row {index} schedule")
        _require(
            schedule.get("schema_version") == SCHEDULE_SCHEMA,
            f"provider payload row {index} schedule schema drifted",
        )
        _require(
            schedule.get("operator") == OPERATOR,
            f"provider payload row {index} operator drifted",
        )
        payload_by_id[request_id] = payload_sha

    seen_ids: set[str] = set()
    arm_counts = {arm: 0 for arm in ARMS}
    run_positions: set[int] = set()
    for index, row in enumerate(treatment_rows):
        _require(isinstance(row, Mapping), f"treatment row {index} invalid")
        _require(
            set(row)
            == {
                "blinded_request_id",
                "block_id",
                "block_position",
                "case_id",
                "provider_payload_sha256",
                "run_position",
                "treatment_id",
                "trial_id",
            },
            f"treatment row {index} schema drifted",
        )
        request_id = row["blinded_request_id"]
        _require(
            request_id in payload_by_id and request_id not in seen_ids,
            f"treatment row {index} blind ID mismatch",
        )
        _require(
            row["provider_payload_sha256"] == payload_by_id[request_id],
            f"treatment row {index} payload hash mismatch",
        )
        treatment = row["treatment_id"]
        _require(treatment in arm_counts, f"treatment row {index} arm invalid")
        arm_counts[treatment] += 1
        _require(
            type(row["run_position"]) is int,
            f"treatment row {index} run position invalid",
        )
        run_positions.add(row["run_position"])
        seen_ids.add(request_id)
    _require(
        seen_ids == set(payload_by_id),
        "treatment key does not cover every blinded payload",
    )
    _require(
        arm_counts == {arm: 4 for arm in ARMS}, "treatment arms are not balanced 4x4"
    )
    _require(run_positions == set(range(1, 17)), "run positions are not exactly 1..16")


def _validate_zero_calls(*values: tuple[str, Mapping[str, Any]]) -> None:
    for label, value in values:
        _require(
            type(value.get("provider_calls")) is int and value["provider_calls"] == 0,
            f"{label} provider_calls is nonzero",
        )
        _require(
            type(value.get("network_calls")) is int and value["network_calls"] == 0,
            f"{label} network_calls is nonzero",
        )


def _validate_all_recorded_calls_zero(value: Any, *, label: str) -> int:
    count = 0
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in {"provider_calls", "network_calls"}:
                _require(type(child) is int and child == 0, f"{label}.{key} is nonzero")
                count += 1
            count += _validate_all_recorded_calls_zero(child, label=f"{label}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            count += _validate_all_recorded_calls_zero(child, label=f"{label}[{index}]")
    return count


def verify(root: Path = ROOT, artifact_dir: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    artifact_dir = (artifact_dir or root / ARTIFACT_RELATIVE).resolve()
    _require(
        artifact_dir == (root / ARTIFACT_RELATIVE).resolve(),
        "non-canonical artifact directory",
    )
    try:
        artifact_stat = artifact_dir.lstat()
    except OSError as error:
        raise VerificationError(
            f"cannot stat artifact directory: {artifact_dir}"
        ) from error
    _require(
        stat.S_ISDIR(artifact_stat.st_mode) and not artifact_dir.is_symlink(),
        "artifact root must be a real directory",
    )
    _require(
        {path.name for path in artifact_dir.iterdir()} == ARTIFACT_FILES,
        "artifact directory entry set drifted",
    )

    policy_raw, policy = _strict_object(root / POLICY_RELATIVE, label="policy")
    _validate_canonical_anchor(
        policy_raw,
        policy,
        expected_file=EXPECTED_POLICY_FILE,
        expected_fingerprint=EXPECTED_POLICY_FINGERPRINT,
        label="policy",
    )
    _validate_policy(root, policy)
    manifest_raw, manifest = _strict_object(
        artifact_dir / "manifest.json", label="manifest"
    )
    _validate_canonical_anchor(
        manifest_raw,
        manifest,
        expected_file=EXPECTED_MANIFEST_FILE,
        expected_fingerprint=EXPECTED_MANIFEST_FINGERPRINT,
        label="manifest",
    )
    projection_raw, projection = _strict_object(
        artifact_dir / "projection_bundle.json", label="projection"
    )
    controller_raw, controller = _strict_object(
        artifact_dir / "controller_audit.json", label="controller audit"
    )
    self_test_raw, self_test = _strict_object(
        artifact_dir / "self_test.json", label="self-test"
    )

    values = {
        "manifest": manifest,
        "projection": projection,
        "controller audit": controller,
        "self-test": self_test,
    }
    raw_values = {
        "manifest": manifest_raw,
        "projection_bundle.json": projection_raw,
        "controller_audit.json": controller_raw,
        "self_test.json": self_test_raw,
    }
    nested_fingerprints = sum(
        _validate_nested_fingerprints(value, label=label)
        for label, value in values.items()
    )
    _require(nested_fingerprints >= 12, "too few internal fingerprints were verified")

    _require(
        manifest.get("schema_version") == MANIFEST_SCHEMA, "manifest schema drifted"
    )
    _require(
        set(manifest)
        == {
            "artifact_receipts",
            "claim_boundary",
            "controller_audit_fingerprint_sha256",
            "fingerprint_sha256",
            "handoff_status",
            "hard_gates",
            "live_execution_authorized",
            "network_calls",
            "policy_lock",
            "projection_fingerprint_sha256",
            "provider_calls",
            "schema_version",
            "self_test_fingerprint_sha256",
            "source_receipts",
            "status",
        },
        "manifest top-level keyset drifted",
    )
    _require(manifest.get("status") == MANIFEST_STATUS, "manifest status drifted")
    _require(
        manifest.get("live_execution_authorized") is False,
        "manifest unexpectedly authorizes live execution",
    )
    _require(
        manifest.get("handoff_status") == HANDOFF_STATUS,
        "manifest handoff status drifted",
    )
    _require(
        projection.get("schema_version") == PROJECTION_SCHEMA,
        "projection schema drifted",
    )
    _require(projection.get("status") == PROJECTION_STATUS, "projection status drifted")
    _require(
        self_test.get("schema_version") == SELF_TEST_SCHEMA, "self-test schema drifted"
    )
    _require(self_test.get("status") == SELF_TEST_STATUS, "self-test status drifted")
    _require(
        controller.get("schema_version") == CONTROLLER_BUNDLE_SCHEMA,
        "controller schema drifted",
    )
    _require(controller.get("status") == SELF_TEST_STATUS, "controller status drifted")

    policy_receipt = manifest.get("policy_lock")
    _validate_receipt(
        policy_receipt,
        path=root / POLICY_RELATIVE,
        expected_relative=POLICY_RELATIVE.as_posix(),
        label="policy",
    )
    _require(
        manifest.get("source_receipts") == policy.get("sources"),
        "manifest source receipts differ from policy",
    )
    artifact_receipts = manifest.get("artifact_receipts")
    _require(
        isinstance(artifact_receipts, Mapping), "manifest artifact receipts missing"
    )
    _require(
        set(artifact_receipts) == RECEIPTED_ARTIFACT_FILES,
        "manifest artifact receipt set drifted",
    )
    for filename in sorted(RECEIPTED_ARTIFACT_FILES):
        _validate_receipt(
            artifact_receipts[filename],
            path=artifact_dir / filename,
            expected_relative=(ARTIFACT_RELATIVE / filename).as_posix(),
            label=f"artifact {filename}",
        )

    _require(
        manifest.get("projection_fingerprint_sha256")
        == projection.get("fingerprint_sha256"),
        "projection fingerprint receipt drifted",
    )
    _require(
        manifest.get("self_test_fingerprint_sha256")
        == self_test.get("fingerprint_sha256"),
        "self-test fingerprint receipt drifted",
    )
    _require(
        manifest.get("controller_audit_fingerprint_sha256")
        == controller.get("fingerprint_sha256"),
        "controller fingerprint receipt drifted",
    )
    _validate_hard_gates(policy=policy, manifest=manifest, self_test=self_test)
    _validate_provider_payloads(projection)
    _validate_zero_calls(
        ("policy artifact", policy["artifact"]),
        ("manifest", manifest),
        ("projection", projection),
        ("controller audit", controller),
        ("self-test", self_test),
    )
    recorded_call_fields = sum(
        _validate_all_recorded_calls_zero(value, label=label)
        for label, value in {"policy": policy, **values}.items()
    )
    _require(recorded_call_fields >= 10, "too few call-count fields were verified")
    _require(
        type(policy["runtime_contract"]["provider_calls_authorized"]) is int
        and policy["runtime_contract"]["provider_calls_authorized"] == 0,
        "policy runtime authorizes provider calls",
    )

    return {
        "schema_version": "ebrt-actuator-calibration-portable-verification-v0.6.3",
        "status": "PASS_PORTABLE_NETWORK_ZERO",
        "artifact_directory": ARTIFACT_RELATIVE.as_posix(),
        "policy_sha256": _sha256(policy_raw),
        "manifest_sha256": _sha256(raw_values["manifest"]),
        "manifest_fingerprint_sha256": manifest["fingerprint_sha256"],
        "nested_fingerprints_verified": nested_fingerprints,
        "hard_gates_verified": len(HARD_GATE_IDS),
        "provider_payloads_verified": len(projection["provider_payloads"]),
        "recorded_call_fields_verified": recorded_call_fields,
        "provider_calls": 0,
        "network_calls": 0,
        "claim_boundary": [
            "This verifies the frozen network-zero bytes and public contracts only.",
            "It does not rerun autograd, contact a provider, or establish hosted actuator uptake.",
        ],
    }


def _expect_rejected(callback: Any, label: str) -> None:
    try:
        callback()
    except VerificationError:
        return
    raise VerificationError(f"tamper self-test was not rejected: {label}")


def self_test(root: Path = ROOT) -> dict[str, Any]:
    result = verify(root)
    _expect_rejected(
        lambda: _strict_json_bytes(b'{"x":1,"x":2}', label="duplicate probe"),
        "duplicate JSON key",
    )
    _expect_rejected(
        lambda: _strict_json_bytes(b'{"x":NaN}', label="non-finite probe"),
        "non-finite JSON",
    )
    _, projection = _strict_object(
        root / ARTIFACT_RELATIVE / "projection_bundle.json", label="projection probe"
    )
    leaked = copy.deepcopy(projection)
    leaked["provider_payloads"][0]["payload"]["q_d"] = {"E1": 1.0}
    payload = leaked["provider_payloads"][0]["payload"]
    leaked["provider_payloads"][0]["provider_payload_sha256"] = _fingerprint(payload)
    _expect_rejected(
        lambda: _validate_provider_payloads(leaked), "private provider key"
    )
    _, policy = _strict_object(root / POLICY_RELATIVE, label="policy probe")
    _, manifest = _strict_object(
        root / ARTIFACT_RELATIVE / "manifest.json", label="manifest probe"
    )
    _, tested = _strict_object(
        root / ARTIFACT_RELATIVE / "self_test.json", label="self-test probe"
    )
    missing_gate = copy.deepcopy(tested)
    missing_gate["hard_gates"].pop(next(iter(HARD_GATE_IDS)))
    _expect_rejected(
        lambda: _validate_hard_gates(
            policy=policy, manifest=manifest, self_test=missing_gate
        ),
        "missing hard gate",
    )
    result["tamper_checks"] = {
        "duplicate_json_rejected": True,
        "nonfinite_json_rejected": True,
        "private_provider_key_rejected": True,
        "hard_gate_keyset_tamper_rejected": True,
    }
    result["status"] = "PASS_PORTABLE_WITH_TAMPER_SELF_TEST"
    return result


def _print_json(value: Any) -> None:
    print(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("verify", "self-test"), nargs="?", default="verify"
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        result = verify(args.root) if args.command == "verify" else self_test(args.root)
    except VerificationError as error:
        print(f"FAIL_PORTABLE: {error}", file=sys.stderr)
        return 1
    _print_json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
