#!/usr/bin/env python3
"""Pure-stdlib verifier for the EBRT v0.6.3.2 mirrored replication preflight.

This verifier deliberately does not import the producer, PyTorch, Pydantic,
or a provider SDK.  It reads the committed lock and artifact, recomputes the
local recurrent-controller arithmetic with Python floats, derives the four
evidence permutations, and checks every sealed provider payload.  It never
contacts a provider or opens a network connection.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parent
POLICY_RELATIVE = Path("policy_lock_actuator_uptake_replication_v0_6_3_2.json")
FIXTURE_RELATIVE = Path("fixtures/actuator_uptake_replication_v0_6_3_2.json")
GOLD_RELATIVE = Path("fixtures/actuator_uptake_replication_gold_v0_6_3_2.json")
ARTIFACT_RELATIVE = Path("artifacts/actuator_uptake_replication_v0_6_3_2_preflight")
PREDECESSOR_FIXTURE_RELATIVE = Path("fixtures/actuator_uptake_canary_v0_6_3_1.json")
PREDECESSOR_GOLD_RELATIVE = Path("fixtures/actuator_uptake_canary_gold_v0_6_3_1.json")
PREDECESSOR_RESULT_RELATIVE = Path(
    "artifacts/actuator_uptake_canary_v0_6_3_1_live_r01/result.json"
)
PREDECESSOR_MANIFEST_RELATIVE = Path(
    "artifacts/actuator_uptake_canary_v0_6_3_1_live_r01/manifest.json"
)
PREDECESSOR_RESULT_FILE = (
    33159,
    "0ffa875e76f325ee7b3508915a5a52b05b4cbffab07f50efcd9263142da0ec7b",
    "131d64dfe74b99912d5e39b0fdd13d17c69eca0d1361b27a48e75887ec25b8e2",
)
PREDECESSOR_MANIFEST_FILE = (
    3826,
    "23304291a8b8be4f4d93e30e6e461bfd3fe6981976886816170bf90d5006932c",
    "cc90cb304ee150d07dcece9e8c8b37a015783ecd9e9ee61b8c803995c9dfe743",
)
PREDECESSOR_RESULT_TAG_OBJECT = "821c8cd96488e843bc6157ecd0fb4349166131d2"
PREDECESSOR_RESULT_COMMIT = "3f65cce03057e7ccfbd39fc168a7fb9e82e591b2"

MAX_FILE_BYTES = 2_000_000
EXPECTED_POLICY_FILE = (
    10053,
    "b3c14706f11700770e4b7b6ce71acc45dab38f317f249464f18ea74d142652b8",
)
EXPECTED_MANIFEST_FILE = (
    1576,
    "cdf7ae043141a13056f33a0176f8777e8a0e2a24e8ba02f5c8cab5f0a059509b",
)
ARMS = ("Z", "C", "D", "X")
BLOCK_IDS = ("A", "B")
BLOCK_SCHEDULES = {"A": ("C", "Z", "D", "X"), "B": ("D", "X", "C", "Z")}
OPERATOR = "evidence_permutation"
FLOAT_TOLERANCE = 1.0e-12

FIXTURE_SCHEMA = "ebrt-actuator-uptake-replication-fixture-v0.6.3.2"
GOLD_SCHEMA = "ebrt-actuator-uptake-replication-gold-v0.6.3.2"
POLICY_SCHEMA = "ebrt-actuator-uptake-policy-lock-v0.6.3.2"
PROVIDER_INPUT_SCHEMA = "ebrt-actuator-uptake-provider-input-v0.6.3.1"
PROJECTION_SCHEMA = "ebrt-actuator-uptake-projection-v0.6.3.2"
GEOMETRY_SCHEMA = "ebrt-actuator-uptake-permutation-geometry-v0.6.3.2"
CONTROLLER_SCHEMA = "ebrt-actuator-uptake-controller-audit-v0.6.3.2"
SELF_TEST_SCHEMA = "ebrt-actuator-uptake-self-test-v0.6.3.2"
MANIFEST_SCHEMA = "ebrt-actuator-uptake-preflight-manifest-v0.6.3.2"

POLICY_STATUS = "LOCKED_NETWORK_ZERO_PREFLIGHT_NO_LIVE_AUTHORIZATION"
PROJECTION_STATUS = "READY_ZERO_CALL_PREFLIGHT_ONLY"
SELF_TEST_STATUS = "PASS_NETWORK_ZERO"
MANIFEST_STATUS = "READY_ZERO_CALL_PREFLIGHT_ONLY"

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
    {
        "core",
        "fixture",
        "post_call_gold",
        "predecessor_fixture",
        "predecessor_gold",
        "predecessor_result",
        "predecessor_manifest",
        "protocol_note",
        "requirements",
    }
)
HARD_GATE_IDS = (
    "strict_fixture_contract",
    "opaque_candidate_ids",
    "equal_candidate_cardinality",
    "real_float64_backward",
    "finite_difference_agreement",
    "gradient_path_preference_nonzero",
    "exact_z_x_c_d_permutations",
    "matched_d_c_geometry",
    "d_alignment_exceeds_c",
    "immutable_chunk_multiset",
    "only_evidence_order_differs",
    "provider_payloads_leak_free",
    "four_payloads_presealed",
    "fresh_case_rotated_from_predecessor",
    "predecessor_eligibility_anchored",
    "exact_mirrored_eight_call_schedule",
    "payload_bytes_reused_across_blocks",
    "pairwise_serial_positions_counterbalanced",
    "all_known_closures_roundtrip",
    "semantic_failures_are_endpoints",
    "unknown_closure_rejected",
    "per_block_classifier_total",
    "aggregate_strict_and_total",
    "deterministic_double_projection",
    "canonical_artifact_directory_exact",
    "network_calls_zero",
)
FORBIDDEN_PROVIDER_KEYS = frozenset(
    {
        "arm",
        "arm_id",
        "block",
        "block_id",
        "replicate",
        "replicate_id",
        "sequence_index",
        "within_block_index",
        "treatment",
        "treatment_id",
        "gradient",
        "controller",
        "local_controller",
        "path_blocks",
        "preferred_path",
        "target_closure",
        "target_closure_id",
        "positive_control_target_closure_id",
        "gradient_target_closure_id",
        "quality_valid_closure_ids",
        "closure_roles",
        "gold",
        "grade",
        "sham",
        "anti_placement",
        "expected_answer",
        "correct_answer",
    }
)


class VerificationError(RuntimeError):
    """Raised when any byte, schema, receipt, or semantic contract drifts."""


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


def _reject_nonfinite_numbers(value: Any, *, label: str) -> None:
    if isinstance(value, float):
        _require(math.isfinite(value), f"{label} contains a non-finite number")
    elif isinstance(value, Mapping):
        for child in value.values():
            _reject_nonfinite_numbers(child, label=label)
    elif isinstance(value, list):
        for child in value:
            _reject_nonfinite_numbers(child, label=label)


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


def _seal(value: Mapping[str, Any]) -> dict[str, Any]:
    output = _without_fingerprint(value)
    output["fingerprint_sha256"] = _fingerprint(output)
    return output


def _validate_fingerprint(value: Mapping[str, Any], *, label: str) -> None:
    observed = value.get("fingerprint_sha256")
    _require(
        _is_sha256(observed) and observed == _fingerprint(_without_fingerprint(value)),
        f"{label} fingerprint drifted",
    )


def _validate_canonical_anchor(
    raw: bytes, *, expected_file: tuple[int, str], label: str
) -> None:
    expected_bytes, expected_sha256 = expected_file
    _require(len(raw) == expected_bytes, f"{label} canonical byte count drifted")
    _require(_sha256(raw) == expected_sha256, f"{label} canonical file SHA-256 drifted")


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


def _strict_object(
    path: Path, *, label: str, canonical_pretty: bool = False
) -> tuple[bytes, dict[str, Any]]:
    raw = _read_regular(path, label=label)
    value = _strict_json_bytes(raw, label=label)
    _require(isinstance(value, dict), f"{label} root must be an object")
    if canonical_pretty:
        _require(raw == _pretty_bytes(value), f"{label} is not canonical pretty JSON")
    return raw, value


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


def _validate_source_receipt(root: Path, receipt: Any, *, label: str) -> None:
    _require(
        isinstance(receipt, Mapping) and set(receipt) == {"path", "bytes", "sha256"},
        f"{label} receipt schema drifted",
    )
    relative, path = _safe_relative(root, receipt.get("path"), label=label)
    _require(relative == receipt["path"], f"{label} receipt path is not normalized")
    _require(
        type(receipt["bytes"]) is int and receipt["bytes"] >= 0,
        f"{label} bytes invalid",
    )
    _require(_is_sha256(receipt["sha256"]), f"{label} SHA-256 invalid")
    raw = _read_regular(path, label=label)
    _require(len(raw) == receipt["bytes"], f"{label} byte receipt drifted")
    _require(_sha256(raw) == receipt["sha256"], f"{label} SHA-256 receipt drifted")


def _validate_artifact_receipt(receipt: Any, *, raw: bytes, label: str) -> None:
    _require(
        isinstance(receipt, Mapping) and set(receipt) == {"bytes", "sha256"},
        f"{label} receipt schema drifted",
    )
    _require(
        type(receipt["bytes"]) is int and receipt["bytes"] >= 0,
        f"{label} bytes invalid",
    )
    _require(_is_sha256(receipt["sha256"]), f"{label} SHA-256 invalid")
    _require(receipt["bytes"] == len(raw), f"{label} byte receipt drifted")
    _require(receipt["sha256"] == _sha256(raw), f"{label} SHA-256 receipt drifted")


def _finite(value: Any, *, label: str) -> float:
    _require(type(value) in {int, float}, f"{label} must be numeric")
    output = float(value)
    _require(math.isfinite(output), f"{label} must be finite")
    return output


def _close(left: Any, right: Any, *, label: str, tolerance: float = 1.0e-10) -> None:
    observed = _finite(left, label=label)
    expected = _finite(right, label=f"expected {label}")
    _require(
        math.isclose(observed, expected, rel_tol=tolerance, abs_tol=tolerance),
        f"{label} drifted: observed {observed!r}, expected {expected!r}",
    )


def _unique_strings(
    value: Any, *, label: str, allow_empty: bool = False
) -> tuple[str, ...]:
    _require(isinstance(value, list), f"{label} must be a list")
    _require(allow_empty or bool(value), f"{label} must not be empty")
    output = tuple(value)
    _require(
        all(isinstance(item, str) and item for item in output),
        f"{label} contains an invalid item",
    )
    _require(len(output) == len(set(output)), f"{label} contains duplicates")
    return output


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


def _candidate_id(selected: Sequence[str], salt: str) -> str:
    digest = hashlib.sha256(
        salt.encode("utf-8") + b":" + _canonical_bytes(list(selected))
    ).hexdigest()
    return f"K_{digest[:10]}"


def _validate_fixture(fixture: Mapping[str, Any]) -> dict[str, Any]:
    _require(
        set(fixture)
        == {
            "schema_version",
            "status",
            "operator",
            "arms",
            "case",
            "protocol",
            "claim_boundary",
        },
        "fixture top-level keyset drifted",
    )
    _require(fixture.get("schema_version") == FIXTURE_SCHEMA, "fixture schema drifted")
    _require(
        fixture.get("status") == "LOCKED_NETWORK_ZERO_PREFLIGHT_INPUT",
        "fixture status drifted",
    )
    _require(fixture.get("operator") == OPERATOR, "fixture operator drifted")
    _require(tuple(fixture.get("arms", ())) == ARMS, "fixture arm order drifted")
    _unique_strings(fixture.get("claim_boundary"), label="fixture claim boundary")

    case = fixture.get("case")
    _require(isinstance(case, Mapping), "fixture case is invalid")
    _require(
        set(case)
        == {
            "case_id",
            "checkpoint_id",
            "question",
            "answer_choices",
            "record_format_choices",
            "raw_evidence",
            "candidate_closures",
            "public_event_contract",
            "local_controller",
        },
        "fixture case keyset drifted",
    )
    for key in ("case_id", "checkpoint_id", "question"):
        _require(
            isinstance(case.get(key), str) and bool(case[key]),
            f"fixture {key} is invalid",
        )
    _require(
        len(_unique_strings(case.get("answer_choices"), label="answer choices")) == 2,
        "answer choice count drifted",
    )
    _require(
        len(_unique_strings(case.get("record_format_choices"), label="record formats"))
        == 1,
        "record format count drifted",
    )

    raw = case.get("raw_evidence")
    _require(isinstance(raw, list) and len(raw) == 7, "raw evidence count drifted")
    evidence_ids: list[str] = []
    for index, row in enumerate(raw):
        _require(
            isinstance(row, Mapping)
            and set(row) == {"evidence_id", "text"}
            and isinstance(row.get("evidence_id"), str)
            and isinstance(row.get("text"), str)
            and bool(row["text"]),
            f"raw evidence row {index} is invalid",
        )
        evidence_ids.append(str(row["evidence_id"]))
    _require(
        tuple(evidence_ids) == tuple(f"N{index}" for index in range(1, 8)),
        "evidence IDs drifted",
    )
    _require(
        len(evidence_ids) == len(set(evidence_ids)), "evidence IDs contain duplicates"
    )

    protocol = fixture.get("protocol")
    _require(isinstance(protocol, Mapping), "fixture protocol is invalid")
    _require(
        set(protocol)
        == {
            "review_budget",
            "neutral_order",
            "positive_control_order",
            "matched_anti_rule",
            "block_schedules",
            "payload_blinding_seed",
            "attempt_blinding_seed",
            "candidate_id_salt",
            "model",
            "reasoning_effort",
            "max_output_tokens",
            "timeout_seconds",
            "sdk_retries",
            "store",
        },
        "fixture protocol keyset drifted",
    )
    _require(protocol.get("review_budget") == 3, "review budget drifted")
    for key in ("neutral_order", "positive_control_order"):
        order = _unique_strings(protocol.get(key), label=f"protocol {key}")
        _require(
            set(order) == set(evidence_ids), f"protocol {key} is not a permutation"
        )
    _require(
        protocol.get("matched_anti_rule") == "swap_preferred_and_opposed_path_blocks",
        "matched anti rule drifted",
    )
    _require(protocol.get("model") == "gpt-5.6-sol", "model drifted")
    _require(protocol.get("reasoning_effort") == "low", "reasoning effort drifted")
    _require(protocol.get("max_output_tokens") == 1024, "output ceiling drifted")
    _require(protocol.get("timeout_seconds") == 60, "timeout drifted")
    _require(protocol.get("sdk_retries") == 0, "SDK retry policy drifted")
    _require(protocol.get("store") is False, "store policy drifted")
    _require(
        protocol.get("block_schedules")
        == {block: list(BLOCK_SCHEDULES[block]) for block in BLOCK_IDS},
        "block schedules drifted",
    )
    for key in ("payload_blinding_seed", "attempt_blinding_seed", "candidate_id_salt"):
        _require(
            isinstance(protocol.get(key), str) and bool(protocol[key]),
            f"protocol {key} is invalid",
        )

    event = case.get("public_event_contract")
    _require(
        isinstance(event, Mapping)
        and set(event)
        == {"late_event_evidence_id", "invalidated_evidence_id", "stable_evidence_id"},
        "public event contract drifted",
    )
    _require(
        set(event.values()).issubset(evidence_ids),
        "public event references unknown evidence",
    )
    _require(len(set(event.values())) == 3, "public event roles collide")

    candidates = case.get("candidate_closures")
    _require(
        isinstance(candidates, list) and len(candidates) == 4, "candidate count drifted"
    )
    candidate_ids: list[str] = []
    selected_sets: list[tuple[str, ...]] = []
    salt = str(protocol["candidate_id_salt"])
    for index, candidate in enumerate(candidates):
        _require(
            isinstance(candidate, Mapping)
            and set(candidate) == {"closure_id", "selected_evidence_ids"},
            f"candidate {index} schema drifted",
        )
        selected = _unique_strings(
            candidate.get("selected_evidence_ids"), label=f"candidate {index} evidence"
        )
        _require(len(selected) == 4, f"candidate {index} cardinality drifted")
        _require(
            set(selected).issubset(evidence_ids),
            f"candidate {index} references unknown evidence",
        )
        closure_id = candidate.get("closure_id")
        _require(
            isinstance(closure_id, str)
            and closure_id.startswith("K_")
            and len(closure_id) == 12
            and closure_id == _candidate_id(selected, salt),
            f"candidate {index} opaque ID drifted",
        )
        candidate_ids.append(closure_id)
        selected_sets.append(selected)
    _require(
        len(candidate_ids) == len(set(candidate_ids)),
        "candidate IDs contain duplicates",
    )
    _require(
        len(selected_sets) == len(set(selected_sets)),
        "candidate structures contain duplicates",
    )

    controller = case.get("local_controller")
    _require(isinstance(controller, Mapping), "local controller is invalid")
    _require(
        set(controller)
        == {
            "path_blocks",
            "state_decay",
            "terminal_target",
            "step_size",
            "control_regularization",
            "effect_by_evidence_id",
            "finite_difference_epsilon",
            "finite_difference_tolerance",
        },
        "local controller keyset drifted",
    )
    blocks = controller.get("path_blocks")
    _require(
        isinstance(blocks, Mapping) and set(blocks) == {"P0", "P1"},
        "path blocks drifted",
    )
    p0 = _unique_strings(blocks.get("P0"), label="P0")
    p1 = _unique_strings(blocks.get("P1"), label="P1")
    _require(
        len(p0) == len(p1) == 2 and not set(p0).intersection(p1),
        "path block geometry drifted",
    )
    _require(
        set(p0) | set(p1) | set(event.values()) == set(evidence_ids),
        "evidence partition drifted",
    )
    effects = controller.get("effect_by_evidence_id")
    _require(
        isinstance(effects, Mapping) and set(effects) == set(evidence_ids),
        "effect set drifted",
    )
    for evidence_id, value in effects.items():
        _finite(value, label=f"effect {evidence_id}")
    for key in (
        "state_decay",
        "terminal_target",
        "step_size",
        "control_regularization",
        "finite_difference_epsilon",
        "finite_difference_tolerance",
    ):
        _require(
            _finite(controller.get(key), label=key) > 0.0, f"{key} must be positive"
        )
    return {
        "case_id": case["case_id"],
        "evidence_ids": evidence_ids,
        "candidate_ids": candidate_ids,
        "chunk_hashes": [_sha256(_canonical_bytes(row)) for row in raw],
    }


def _validate_gold(gold: Mapping[str, Any], fixture: Mapping[str, Any]) -> None:
    _require(
        set(gold)
        == {
            "schema_version",
            "status",
            "case_id",
            "answer",
            "record_format",
            "positive_control_target_closure_id",
            "gradient_target_closure_id",
            "quality_valid_closure_ids",
            "closure_roles",
            "claim_boundary",
        },
        "gold top-level keyset drifted",
    )
    _require(gold.get("schema_version") == GOLD_SCHEMA, "gold schema drifted")
    _require(
        gold.get("status") == "LOCKED_POST_EIGHT_TERMINALS_GRADING_ONLY",
        "gold status drifted",
    )
    case = fixture["case"]
    candidates = {row["closure_id"]: row for row in case["candidate_closures"]}
    _require(gold.get("case_id") == case["case_id"], "gold case drifted")
    _require(gold.get("answer") in case["answer_choices"], "gold answer invalid")
    _require(
        gold.get("record_format") in case["record_format_choices"],
        "gold format invalid",
    )
    roles = gold.get("closure_roles")
    _require(
        isinstance(roles, Mapping) and set(roles) == set(candidates),
        "gold role set drifted",
    )
    _require(
        set(roles.values())
        == {
            "ALIGNED_EVENT_CONSISTENT",
            "ALTERNATIVE_EVENT_CONSISTENT",
            "STALE_INVALIDATED_SUPPORT",
            "MIXED_INSUFFICIENT_SUPPORT",
        },
        "gold role values drifted",
    )
    valid = _unique_strings(
        gold.get("quality_valid_closure_ids"), label="quality-valid closures"
    )
    _require(
        len(valid) == 2 and set(valid).issubset(candidates),
        "quality-valid closure set drifted",
    )
    target = gold.get("gradient_target_closure_id")
    _require(
        target == gold.get("positive_control_target_closure_id") and target in valid,
        "gold target relation drifted",
    )
    expected_controller = _expected_controller(fixture)
    blocks = case["local_controller"]["path_blocks"]
    event = case["public_event_contract"]
    preferred_selected = tuple(blocks[expected_controller["preferred"]]) + (
        event["late_event_evidence_id"],
        event["stable_evidence_id"],
    )
    opposed_selected = tuple(blocks[expected_controller["opposed"]]) + (
        event["late_event_evidence_id"],
        event["stable_evidence_id"],
    )
    ids_by_selected = {
        tuple(row["selected_evidence_ids"]): row["closure_id"]
        for row in case["candidate_closures"]
    }
    _require(
        preferred_selected in ids_by_selected,
        "preferred event-consistent closure is missing",
    )
    _require(
        opposed_selected in ids_by_selected,
        "opposed event-consistent closure is missing",
    )
    aligned_id = ids_by_selected[preferred_selected]
    alternative_id = ids_by_selected[opposed_selected]
    _require(
        target == aligned_id,
        "gold target is not bound to the preferred controller path",
    )
    _require(
        set(valid) == {aligned_id, alternative_id},
        "quality-valid set is not exactly the two event-consistent closures",
    )
    _require(
        roles[aligned_id] == "ALIGNED_EVENT_CONSISTENT",
        "preferred closure role drifted",
    )
    _require(
        roles[alternative_id] == "ALTERNATIVE_EVENT_CONSISTENT",
        "opposed closure role drifted",
    )
    stale_ids = [
        closure_id
        for closure_id, role in roles.items()
        if role == "STALE_INVALIDATED_SUPPORT"
    ]
    _require(len(stale_ids) == 1, "stale closure role is not unique")
    stale_selected = set(candidates[stale_ids[0]]["selected_evidence_ids"])
    _require(
        event["invalidated_evidence_id"] in stale_selected
        and event["late_event_evidence_id"] not in stale_selected,
        "stale closure structure drifted",
    )
    _unique_strings(gold.get("claim_boundary"), label="gold claim boundary")


def _portable_classify_block(
    z_id: str,
    c_id: str,
    d_id: str,
    x_id: str,
    *,
    target: str,
    candidate_ids: frozenset[str],
) -> tuple[str, str, str]:
    """Independently classify one complete four-arm closure assignment."""

    selected = {"Z": z_id, "C": c_id, "D": d_id, "X": x_id}
    _require(
        all(value in candidate_ids for value in selected.values()),
        "portable classifier received an unknown closure ID",
    )
    _require(target in candidate_ids, "portable classifier target is unknown")

    if z_id == target and x_id == target:
        positive = "POSITIVE_CONTROL_CEILING"
    elif z_id != target and x_id == target:
        positive = "CHANNEL_OPEN_DIRECTIONAL"
    elif z_id == x_id:
        positive = "ACTUATOR_CHANNEL_INERT"
    elif z_id == target and x_id != target:
        positive = "CHANNEL_OPEN_ADVERSE"
    else:
        positive = "CHANNEL_OPEN_DIRECTION_AMBIGUOUS"

    if c_id == target and d_id == target:
        placement = "D_C_TARGET_CEILING"
    elif d_id == target and c_id != target:
        placement = "GRADIENT_PLACEMENT_DIRECTIONAL"
    elif c_id == d_id:
        placement = "GRADIENT_PLACEMENT_NULL"
    elif c_id == target and d_id != target:
        placement = "GRADIENT_PLACEMENT_ADVERSE"
    else:
        placement = "GRADIENT_PLACEMENT_AMBIGUOUS"

    if (
        positive == "CHANNEL_OPEN_DIRECTIONAL"
        and placement == "GRADIENT_PLACEMENT_DIRECTIONAL"
    ):
        terminal = "BLOCK_DIRECTIONAL"
    elif positive == "POSITIVE_CONTROL_CEILING":
        terminal = "STOP_POSITIVE_CONTROL_CEILING_NOT_ASSESSED"
    elif positive == "ACTUATOR_CHANNEL_INERT":
        terminal = "STOP_CHANNEL_INERT"
    elif positive == "CHANNEL_OPEN_DIRECTION_AMBIGUOUS":
        terminal = "STOP_CHANNEL_AMBIGUOUS"
    elif positive == "CHANNEL_OPEN_ADVERSE":
        terminal = "STOP_CHANNEL_ADVERSE"
    elif placement == "D_C_TARGET_CEILING":
        terminal = "STOP_PLACEMENT_CEILING_NOT_ASSESSED"
    elif placement == "GRADIENT_PLACEMENT_NULL":
        terminal = "STOP_PLACEMENT_NULL"
    elif placement == "GRADIENT_PLACEMENT_AMBIGUOUS":
        terminal = "STOP_PLACEMENT_AMBIGUOUS"
    else:
        terminal = "STOP_PLACEMENT_ADVERSE"
    return positive, placement, terminal


def _portable_aggregate_contrast(statuses: Sequence[str]) -> str:
    """Independently reduce two per-block contrast statuses."""

    _require(len(statuses) == 2, "portable aggregate block count drifted")
    directional_count = sum(status.endswith("DIRECTIONAL") for status in statuses)
    if directional_count == 2:
        return "REPLICATED_DIRECTIONAL"
    if directional_count == 1:
        return "MIXED"
    if statuses[0] != statuses[1]:
        return "HETEROGENEOUS_NON_DIRECTIONAL"
    suffix = {
        "POSITIVE_CONTROL_CEILING": "REPLICATED_CEILING",
        "ACTUATOR_CHANNEL_INERT": "REPLICATED_NULL",
        "CHANNEL_OPEN_ADVERSE": "REPLICATED_ADVERSE",
        "CHANNEL_OPEN_DIRECTION_AMBIGUOUS": "REPLICATED_AMBIGUOUS",
        "D_C_TARGET_CEILING": "REPLICATED_CEILING",
        "GRADIENT_PLACEMENT_NULL": "REPLICATED_NULL",
        "GRADIENT_PLACEMENT_ADVERSE": "REPLICATED_ADVERSE",
        "GRADIENT_PLACEMENT_AMBIGUOUS": "REPLICATED_AMBIGUOUS",
    }
    _require(statuses[0] in suffix, "portable aggregate status is unknown")
    return suffix[statuses[0]]


def _portable_aggregate_terminal(positive: str, placement: str) -> str:
    """Independently apply the strict two-block terminal precedence."""

    statuses = {positive, placement}
    if statuses == {"REPLICATED_DIRECTIONAL"}:
        return "REPLICATION_DIRECTIONAL_COUNTERBALANCED"
    if "MIXED" in statuses:
        return "STOP_REPLICATION_MIXED"
    if "REPLICATED_ADVERSE" in statuses:
        return "STOP_REPLICATION_ADVERSE"
    if statuses & {"REPLICATED_AMBIGUOUS", "HETEROGENEOUS_NON_DIRECTIONAL"}:
        return "STOP_REPLICATION_AMBIGUOUS"
    if "REPLICATED_CEILING" in statuses:
        return "STOP_REPLICATION_CEILING_NOT_ASSESSED"
    return "STOP_REPLICATION_NULL"


def _verify_classifier_contract(
    fixture: Mapping[str, Any], gold: Mapping[str, Any]
) -> dict[str, Any]:
    """Exhaustively verify the sealed classifier contract without the producer."""

    candidate_ids = tuple(
        str(row["closure_id"]) for row in fixture["case"]["candidate_closures"]
    )
    candidate_set = frozenset(candidate_ids)
    _require(
        len(candidate_ids) == 4 and len(candidate_set) == 4,
        "portable classifier requires exactly four unique closures",
    )
    target = str(gold["gradient_target_closure_id"])
    _require(target in candidate_set, "portable classifier target drifted")

    block_status_pairs: list[tuple[str, str]] = []
    block_terminals: set[str] = set()
    directional_blocks = 0
    for z_id in candidate_ids:
        for c_id in candidate_ids:
            for d_id in candidate_ids:
                for x_id in candidate_ids:
                    positive, placement, terminal = _portable_classify_block(
                        z_id,
                        c_id,
                        d_id,
                        x_id,
                        target=target,
                        candidate_ids=candidate_set,
                    )
                    block_status_pairs.append((positive, placement))
                    block_terminals.add(terminal)
                    directional_blocks += terminal == "BLOCK_DIRECTIONAL"

    expected_block_terminals = {
        "BLOCK_DIRECTIONAL",
        "STOP_POSITIVE_CONTROL_CEILING_NOT_ASSESSED",
        "STOP_CHANNEL_INERT",
        "STOP_CHANNEL_AMBIGUOUS",
        "STOP_CHANNEL_ADVERSE",
        "STOP_PLACEMENT_CEILING_NOT_ASSESSED",
        "STOP_PLACEMENT_NULL",
        "STOP_PLACEMENT_AMBIGUOUS",
        "STOP_PLACEMENT_ADVERSE",
    }
    _require(
        len(block_status_pairs) == 256,
        "portable per-block classifier space is incomplete",
    )
    _require(
        block_terminals == expected_block_terminals,
        "portable per-block terminal coverage drifted",
    )
    _require(
        directional_blocks == 9,
        "portable per-block directional cardinality drifted",
    )

    aggregate_statuses = (
        "REPLICATED_DIRECTIONAL",
        "MIXED",
        "REPLICATED_CEILING",
        "REPLICATED_NULL",
        "REPLICATED_ADVERSE",
        "REPLICATED_AMBIGUOUS",
        "HETEROGENEOUS_NON_DIRECTIONAL",
    )
    expected_aggregate_terminals = {
        "REPLICATION_DIRECTIONAL_COUNTERBALANCED",
        "STOP_REPLICATION_MIXED",
        "STOP_REPLICATION_ADVERSE",
        "STOP_REPLICATION_AMBIGUOUS",
        "STOP_REPLICATION_CEILING_NOT_ASSESSED",
        "STOP_REPLICATION_NULL",
    }
    aggregate_terminals = {
        _portable_aggregate_terminal(positive, placement)
        for positive in aggregate_statuses
        for placement in aggregate_statuses
    }
    _require(
        len(aggregate_statuses) ** 2 == 49,
        "portable aggregate status-pair space drifted",
    )
    _require(
        aggregate_terminals == expected_aggregate_terminals,
        "portable aggregate terminal precedence drifted",
    )

    aggregate_closure_terminals: set[str] = set()
    aggregate_successes = 0
    for left in block_status_pairs:
        for right in block_status_pairs:
            positive = _portable_aggregate_contrast((left[0], right[0]))
            placement = _portable_aggregate_contrast((left[1], right[1]))
            terminal = _portable_aggregate_terminal(positive, placement)
            aggregate_closure_terminals.add(terminal)
            is_success = terminal == "REPLICATION_DIRECTIONAL_COUNTERBALANCED"
            strict_and = left == (
                "CHANNEL_OPEN_DIRECTIONAL",
                "GRADIENT_PLACEMENT_DIRECTIONAL",
            ) and right == (
                "CHANNEL_OPEN_DIRECTIONAL",
                "GRADIENT_PLACEMENT_DIRECTIONAL",
            )
            _require(
                is_success == strict_and,
                "portable aggregate success escaped the strict two-block AND gate",
            )
            aggregate_successes += is_success

    aggregate_closure_pairs = len(block_status_pairs) ** 2
    _require(
        aggregate_closure_pairs == 65536,
        "portable aggregate closure-pair space is incomplete",
    )
    _require(
        aggregate_closure_terminals == expected_aggregate_terminals,
        "portable aggregate closure-pair terminal coverage drifted",
    )
    _require(
        aggregate_successes == 81,
        "portable aggregate directional cardinality drifted",
    )
    return {
        "per_block_classifier_combinations_verified": len(block_status_pairs),
        "per_block_directional_combinations_verified": directional_blocks,
        "aggregate_status_pairs_verified": len(aggregate_statuses) ** 2,
        "aggregate_closure_block_pairs_verified": aggregate_closure_pairs,
        "aggregate_success_combinations_verified": aggregate_successes,
        "per_block_terminals_verified": sorted(block_terminals),
        "aggregate_terminals_verified": sorted(aggregate_closure_terminals),
    }


def _validate_freshness(
    fixture: Mapping[str, Any],
    gold: Mapping[str, Any],
    predecessor_fixture: Mapping[str, Any],
    predecessor_gold: Mapping[str, Any],
) -> None:
    current_case = fixture["case"]
    previous_case = predecessor_fixture["case"]
    current_ids = [row["closure_id"] for row in current_case["candidate_closures"]]
    previous_ids = [row["closure_id"] for row in previous_case["candidate_closures"]]
    _require(
        current_case["case_id"] != previous_case["case_id"], "fresh case ID reused"
    )
    _require(
        current_case["checkpoint_id"] != previous_case["checkpoint_id"],
        "fresh checkpoint reused",
    )
    _require(
        not (
            {row["evidence_id"] for row in current_case["raw_evidence"]}
            & {row["evidence_id"] for row in previous_case["raw_evidence"]}
        ),
        "fresh evidence IDs overlap predecessor",
    )
    _require(
        not (
            {_sha256(_canonical_bytes(row)) for row in current_case["raw_evidence"]}
            & {_sha256(_canonical_bytes(row)) for row in previous_case["raw_evidence"]}
        ),
        "fresh evidence bytes overlap predecessor",
    )
    _require(
        not (set(current_ids) & set(previous_ids)),
        "fresh candidate IDs overlap predecessor",
    )
    _require(
        current_case["answer_choices"].index(gold["answer"])
        != previous_case["answer_choices"].index(predecessor_gold["answer"]),
        "correct answer ordinal was not rotated",
    )
    _require(
        current_ids.index(gold["gradient_target_closure_id"])
        != previous_ids.index(predecessor_gold["gradient_target_closure_id"]),
        "aligned catalog ordinal was not rotated",
    )


def _validate_predecessor_eligibility(
    result_raw: bytes,
    result: Mapping[str, Any],
    manifest_raw: bytes,
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    for raw, value, expected, label in (
        (result_raw, result, PREDECESSOR_RESULT_FILE, "result"),
        (manifest_raw, manifest, PREDECESSOR_MANIFEST_FILE, "manifest"),
    ):
        _require(len(raw) == expected[0], f"predecessor {label} byte count drifted")
        _require(_sha256(raw) == expected[1], f"predecessor {label} SHA-256 drifted")
        _validate_fingerprint(value, label=f"predecessor {label}")
        _require(
            value.get("fingerprint_sha256") == expected[2],
            f"predecessor {label} fingerprint drifted",
        )
    decision = result.get("decision")
    _require(isinstance(decision, Mapping), "predecessor decision missing")
    _validate_fingerprint(decision, label="predecessor decision")
    _require(
        decision.get("terminal_decision") == "PROMOTE_TO_FRESH_REPLICATION",
        "predecessor terminal drifted",
    )
    _require(
        decision.get("assessment_status") == "ASSESSED",
        "predecessor assessment drifted",
    )
    _require(
        decision.get("direct_v0_6_4_promotion_allowed") is False,
        "predecessor directly promotes v0.6.4",
    )
    _require(
        result.get("direct_v0_6_4_promotion_allowed") is False,
        "predecessor result directly promotes v0.6.4",
    )
    _require(
        manifest.get("result_fingerprint_sha256") == PREDECESSOR_RESULT_FILE[2],
        "predecessor manifest result receipt drifted",
    )
    return {
        "result_tag_object": PREDECESSOR_RESULT_TAG_OBJECT,
        "result_commit": PREDECESSOR_RESULT_COMMIT,
        "result_fingerprint_sha256": PREDECESSOR_RESULT_FILE[2],
        "manifest_fingerprint_sha256": PREDECESSOR_MANIFEST_FILE[2],
    }


def _controller_loss(
    controls: Sequence[float],
    effects: Sequence[float],
    *,
    decay: float,
    target: float,
    regularization: float,
) -> tuple[float, list[float]]:
    state = 0.0
    states: list[float] = []
    for control, effect in zip(controls, effects, strict=True):
        state = math.tanh(decay * state + control * effect)
        states.append(state)
    loss = (state - target) ** 2 + regularization * math.fsum(
        value * value for value in controls
    )
    return loss, states


def _expected_controller(fixture: Mapping[str, Any]) -> dict[str, Any]:
    case = fixture["case"]
    evidence_ids = [row["evidence_id"] for row in case["raw_evidence"]]
    spec = case["local_controller"]
    effects = [float(spec["effect_by_evidence_id"][item]) for item in evidence_ids]
    count = len(evidence_ids)
    decay = float(spec["state_decay"])
    target = float(spec["terminal_target"])
    regularization = float(spec["control_regularization"])
    baseline_loss, states = _controller_loss(
        [0.0] * count,
        effects,
        decay=decay,
        target=target,
        regularization=regularization,
    )
    gradients = [
        -2.0 * target * effects[index] * (decay ** (count - index - 1))
        for index in range(count)
    ]
    displacement = [-float(spec["step_size"]) * value for value in gradients]
    epsilon = float(spec["finite_difference_epsilon"])
    finite_difference: list[float] = []
    for index in range(count):
        positive = [0.0] * count
        negative = [0.0] * count
        positive[index] = epsilon
        negative[index] = -epsilon
        positive_loss, _ = _controller_loss(
            positive, effects, decay=decay, target=target, regularization=regularization
        )
        negative_loss, _ = _controller_loss(
            negative, effects, decay=decay, target=target, regularization=regularization
        )
        finite_difference.append((positive_loss - negative_loss) / (2.0 * epsilon))
    displacement_by_id = dict(zip(evidence_ids, displacement, strict=True))
    path_scores = {
        path_id: math.fsum(
            displacement_by_id[item] for item in spec["path_blocks"][path_id]
        )
        for path_id in ("P0", "P1")
    }
    preferred = max(path_scores, key=path_scores.get)
    opposed = "P1" if preferred == "P0" else "P0"
    return {
        "baseline_loss": baseline_loss,
        "baseline_states": states,
        "gradient": dict(zip(evidence_ids, gradients, strict=True)),
        "displacement": displacement_by_id,
        "finite_difference": dict(zip(evidence_ids, finite_difference, strict=True)),
        "maximum_error": max(
            abs(left - right)
            for left, right in zip(gradients, finite_difference, strict=True)
        ),
        "path_scores": path_scores,
        "preferred": preferred,
        "opposed": opposed,
    }


def _validate_controller(
    controller: Mapping[str, Any], fixture: Mapping[str, Any]
) -> dict[str, Any]:
    _validate_fingerprint(controller, label="controller audit")
    _require(
        set(controller)
        == {
            "schema_version",
            "case_id",
            "dtype",
            "backward_calls",
            "baseline_loss",
            "baseline_states",
            "gradient_by_evidence_id",
            "displacement_by_evidence_id",
            "finite_difference_by_evidence_id",
            "maximum_finite_difference_error",
            "finite_difference_tolerance",
            "path_scores",
            "preferred_path_id",
            "opposed_path_id",
            "gradient_boundary",
            "fingerprint_sha256",
        },
        "controller audit keyset drifted",
    )
    _require(
        controller.get("schema_version") == CONTROLLER_SCHEMA,
        "controller schema drifted",
    )
    _require(
        controller.get("case_id") == fixture["case"]["case_id"],
        "controller case drifted",
    )
    _require(controller.get("dtype") == "torch.float64", "controller dtype drifted")
    _require(controller.get("backward_calls") == 1, "controller backward count drifted")
    _require(
        controller.get("gradient_boundary")
        == {
            "starts_at": "local recurrent public-state surrogate",
            "ends_before": "JSON provider payload",
            "hosted_model_differentiated": False,
        },
        "controller gradient boundary drifted",
    )
    expected = _expected_controller(fixture)
    _close(
        controller.get("baseline_loss"),
        expected["baseline_loss"],
        label="baseline loss",
    )
    states = controller.get("baseline_states")
    _require(
        isinstance(states, list) and len(states) == 7, "baseline state count drifted"
    )
    for index, value in enumerate(states):
        _close(
            value, expected["baseline_states"][index], label=f"baseline state {index}"
        )
    for field, expected_key in (
        ("gradient_by_evidence_id", "gradient"),
        ("displacement_by_evidence_id", "displacement"),
        ("finite_difference_by_evidence_id", "finite_difference"),
    ):
        observed = controller.get(field)
        expected_values = expected[expected_key]
        _require(
            isinstance(observed, Mapping) and set(observed) == set(expected_values),
            f"{field} keyset drifted",
        )
        for evidence_id, value in expected_values.items():
            _close(observed[evidence_id], value, label=f"{field}.{evidence_id}")
    _close(
        controller.get("maximum_finite_difference_error"),
        expected["maximum_error"],
        label="maximum finite-difference error",
    )
    tolerance = float(
        fixture["case"]["local_controller"]["finite_difference_tolerance"]
    )
    _close(
        controller.get("finite_difference_tolerance"),
        tolerance,
        label="finite-difference tolerance",
    )
    _require(
        float(controller["maximum_finite_difference_error"]) <= tolerance,
        "finite-difference agreement failed",
    )
    scores = controller.get("path_scores")
    _require(
        isinstance(scores, Mapping) and set(scores) == {"P0", "P1"},
        "path score keyset drifted",
    )
    for path_id, value in expected["path_scores"].items():
        _close(scores[path_id], value, label=f"path score {path_id}")
    _require(
        controller.get("preferred_path_id") == expected["preferred"],
        "preferred path drifted",
    )
    _require(
        controller.get("opposed_path_id") == expected["opposed"], "opposed path drifted"
    )
    _require(
        abs(float(scores["P0"]) - float(scores["P1"])) > FLOAT_TOLERANCE,
        "controller path preference is tied",
    )
    return expected


def _spearman_footrule(reference: Sequence[str], candidate: Sequence[str]) -> int:
    return sum(abs(reference.index(item) - candidate.index(item)) for item in reference)


def _kendall_distance(reference: Sequence[str], candidate: Sequence[str]) -> int:
    positions = {item: index for index, item in enumerate(candidate)}
    return sum(
        positions[reference[left]] > positions[reference[right]]
        for left in range(len(reference))
        for right in range(left + 1, len(reference))
    )


def _fixed_points(reference: Sequence[str], candidate: Sequence[str]) -> int:
    return sum(left == right for left, right in zip(reference, candidate, strict=True))


def _positional_alignment(
    order: Sequence[str], displacement: Mapping[str, float]
) -> float:
    return math.fsum(
        float(displacement[item]) * float(len(order) - index)
        for index, item in enumerate(order)
    )


def _expected_orders(
    fixture: Mapping[str, Any], controller: Mapping[str, Any]
) -> dict[str, tuple[str, ...]]:
    case = fixture["case"]
    spec = case["local_controller"]
    event = case["public_event_contract"]
    preferred = str(controller["preferred_path_id"])
    opposed = str(controller["opposed_path_id"])
    preferred_block = tuple(spec["path_blocks"][preferred])
    opposed_block = tuple(spec["path_blocks"][opposed])
    anchors = (
        str(event["late_event_evidence_id"]),
        str(event["invalidated_evidence_id"]),
        str(event["stable_evidence_id"]),
    )
    return {
        "Z": tuple(fixture["protocol"]["neutral_order"]),
        "C": opposed_block + (anchors[0],) + preferred_block + anchors[1:],
        "D": preferred_block + (anchors[0],) + opposed_block + anchors[1:],
        "X": tuple(fixture["protocol"]["positive_control_order"]),
    }


def _validate_geometry(
    geometry: Mapping[str, Any],
    fixture: Mapping[str, Any],
    controller: Mapping[str, Any],
) -> dict[str, tuple[str, ...]]:
    _validate_fingerprint(geometry, label="permutation geometry")
    _require(
        set(geometry)
        == {
            "schema_version",
            "case_id",
            "orders",
            "distances_from_z",
            "positional_alignment",
            "d_minus_c_alignment",
            "checks",
            "fingerprint_sha256",
        },
        "permutation geometry keyset drifted",
    )
    _require(
        geometry.get("schema_version") == GEOMETRY_SCHEMA, "geometry schema drifted"
    )
    _require(
        geometry.get("case_id") == fixture["case"]["case_id"], "geometry case drifted"
    )
    expected = _expected_orders(fixture, controller)
    observed_orders = geometry.get("orders")
    _require(
        isinstance(observed_orders, Mapping) and set(observed_orders) == set(ARMS),
        "geometry arm set drifted",
    )
    for arm in ARMS:
        observed = _unique_strings(observed_orders[arm], label=f"geometry order {arm}")
        _require(observed == expected[arm], f"geometry order {arm} drifted")
    _require(len(set(expected.values())) == 4, "four expected orders are not distinct")

    distances = geometry.get("distances_from_z")
    _require(
        isinstance(distances, Mapping) and set(distances) == {"D", "C"},
        "geometry distance arms drifted",
    )
    computed_distances: dict[str, dict[str, int]] = {}
    for arm in ("D", "C"):
        computed = {
            "spearman_footrule": _spearman_footrule(expected["Z"], expected[arm]),
            "kendall": _kendall_distance(expected["Z"], expected[arm]),
            "fixed_points": _fixed_points(expected["Z"], expected[arm]),
        }
        _require(distances[arm] == computed, f"geometry distance {arm} drifted")
        computed_distances[arm] = computed
    _require(
        computed_distances["D"] == computed_distances["C"],
        "D/C permutation geometry is not matched",
    )

    displacement = controller["displacement_by_evidence_id"]
    d_alignment = _positional_alignment(expected["D"], displacement)
    c_alignment = _positional_alignment(expected["C"], displacement)
    alignments = geometry.get("positional_alignment")
    _require(
        isinstance(alignments, Mapping) and set(alignments) == {"D", "C"},
        "alignment keyset drifted",
    )
    _close(alignments["D"], d_alignment, label="D positional alignment")
    _close(alignments["C"], c_alignment, label="C positional alignment")
    _close(
        geometry.get("d_minus_c_alignment"),
        d_alignment - c_alignment,
        label="D minus C alignment",
    )
    event = fixture["case"]["public_event_contract"]
    checks = {
        "all_four_orders_distinct": len(set(expected.values())) == 4,
        "d_c_footrule_matched": computed_distances["D"]["spearman_footrule"]
        == computed_distances["C"]["spearman_footrule"],
        "d_c_kendall_matched": computed_distances["D"]["kendall"]
        == computed_distances["C"]["kendall"],
        "d_c_fixed_points_matched": computed_distances["D"]["fixed_points"]
        == computed_distances["C"]["fixed_points"],
        "d_c_anchor_positions_matched": all(
            expected["D"].index(str(event[key])) == expected["C"].index(str(event[key]))
            for key in (
                "late_event_evidence_id",
                "invalidated_evidence_id",
                "stable_evidence_id",
            )
        ),
        "d_alignment_exceeds_c": d_alignment > c_alignment + FLOAT_TOLERANCE,
    }
    _require(
        geometry.get("checks") == checks and all(checks.values()),
        "geometry checks drifted",
    )
    return expected


def _blind_id(case_id: str, arm: str, seed: str) -> str:
    digest = hashlib.sha256(f"{seed}|{case_id}|{arm}".encode()).hexdigest()
    return f"Q_{digest[:16]}"


def _attempt_id(case_id: str, block_id: str, arm: str, seed: str) -> str:
    digest = hashlib.sha256(f"{seed}|{case_id}|{block_id}|{arm}".encode()).hexdigest()
    return f"A_{digest[:16]}"


def _normalized_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    output = copy.deepcopy(dict(payload))
    output["ordered_raw_evidence"] = sorted(
        output["ordered_raw_evidence"], key=lambda row: row["evidence_id"]
    )
    return output


def _validate_payload(
    payload: Mapping[str, Any],
    *,
    fixture: Mapping[str, Any],
    expected_order: Sequence[str],
    label: str,
) -> tuple[str, tuple[str, ...]]:
    _validate_fingerprint(payload, label=label)
    raw_payload = _without_fingerprint(payload)
    _require(
        set(raw_payload)
        == {
            "schema_version",
            "checkpoint_id",
            "question",
            "answer_choices",
            "record_format_choices",
            "ordered_raw_evidence",
            "candidate_closures",
            "response_contract",
            "task_instructions",
        },
        f"{label} keyset drifted",
    )
    case = fixture["case"]
    _require(
        raw_payload.get("schema_version") == PROVIDER_INPUT_SCHEMA,
        f"{label} schema drifted",
    )
    _require(
        raw_payload.get("checkpoint_id") == case["checkpoint_id"],
        f"{label} checkpoint drifted",
    )
    for key in (
        "question",
        "answer_choices",
        "record_format_choices",
        "candidate_closures",
    ):
        _require(
            _canonical_bytes(raw_payload.get(key)) == _canonical_bytes(case[key]),
            f"{label} {key} drifted",
        )
    _require(
        raw_payload.get("response_contract")
        == {
            "schema_version": "ebrt-actuator-uptake-provider-output-v0.6.3.1",
            "choose_exactly_one_candidate_closure": True,
            "reviewed_evidence_count": 3,
            "return_private_reasoning": False,
        },
        f"{label} response contract drifted",
    )
    _require(
        raw_payload.get("task_instructions")
        == [
            "Use the full evidence set and inspect the immutable chunks in the order presented.",
            "Select exactly one candidate closure and emit only the typed public response.",
            "Do not return private chain-of-thought or invent a closure outside the catalog.",
        ],
        f"{label} task instructions drifted",
    )
    leaked = _recursive_keys(raw_payload) & FORBIDDEN_PROVIDER_KEYS
    _require(not leaked, f"{label} leaks private keys: {sorted(leaked)}")
    rows = raw_payload.get("ordered_raw_evidence")
    _require(
        isinstance(rows, list) and len(rows) == 7, f"{label} evidence count drifted"
    )
    source_rows = {row["evidence_id"]: row for row in case["raw_evidence"]}
    observed_order: list[str] = []
    chunk_hashes: list[str] = []
    for index, row in enumerate(rows):
        _require(
            isinstance(row, Mapping) and set(row) == {"evidence_id", "text"},
            f"{label} evidence row {index} drifted",
        )
        evidence_id = row.get("evidence_id")
        _require(evidence_id in source_rows, f"{label} evidence row {index} is unknown")
        _require(
            _canonical_bytes(row) == _canonical_bytes(source_rows[evidence_id]),
            f"{label} evidence row {index} byte content drifted",
        )
        observed_order.append(str(evidence_id))
        chunk_hashes.append(_sha256(_canonical_bytes(row)))
    _require(
        tuple(observed_order) == tuple(expected_order),
        f"{label} evidence order drifted",
    )
    _require(
        len(observed_order) == len(set(observed_order)), f"{label} repeats evidence"
    )
    return _fingerprint(raw_payload), tuple(sorted(chunk_hashes))


def _validate_projection(
    projection: Mapping[str, Any],
    *,
    fixture: Mapping[str, Any],
    controller: Mapping[str, Any],
) -> dict[str, Any]:
    _validate_fingerprint(projection, label="projection")
    _require(
        set(projection)
        == {
            "schema_version",
            "status",
            "operator",
            "case_id",
            "provider_payload_count",
            "scheduled_call_count",
            "provider_calls_authorized",
            "provider_calls_observed",
            "gold_used_for_projection",
            "gold_release_condition",
            "gold_load_count_after_release",
            "execution_order",
            "block_schedules",
            "execution_schedule",
            "provider_payloads",
            "public_treatment_key",
            "fixture_audit",
            "permutation_geometry",
            "controller_audit_fingerprint_sha256",
            "primary_public_action_field",
            "reviewed_evidence_ids_primary",
            "claim_boundary",
            "fingerprint_sha256",
        },
        "projection keyset drifted",
    )
    _require(
        projection.get("schema_version") == PROJECTION_SCHEMA,
        "projection schema drifted",
    )
    _require(projection.get("status") == PROJECTION_STATUS, "projection status drifted")
    _require(projection.get("operator") == OPERATOR, "projection operator drifted")
    _require(
        projection.get("case_id") == fixture["case"]["case_id"],
        "projection case drifted",
    )
    _require(
        projection.get("provider_payload_count") == 4,
        "projection payload count drifted",
    )
    _require(
        projection.get("scheduled_call_count") == 8,
        "projection scheduled call count drifted",
    )
    _require(
        projection.get("provider_calls_authorized") == 0,
        "projection authorizes provider calls",
    )
    _require(
        projection.get("provider_calls_observed") == 0,
        "projection records provider calls",
    )
    _require(
        projection.get("gold_used_for_projection") is False,
        "projection used post-call gold",
    )
    _require(
        projection.get("gold_release_condition")
        == "AFTER_EIGHT_STRUCTURALLY_VALID_TERMINALS",
        "projection gold release drifted",
    )
    _require(
        projection.get("gold_load_count_after_release") == 1,
        "projection gold load count drifted",
    )
    _require(
        projection.get("primary_public_action_field") == "selected_closure_id",
        "projection primary action drifted",
    )
    _require(
        projection.get("reviewed_evidence_ids_primary") is False,
        "inspection receipt became primary",
    )
    _require(
        projection.get("controller_audit_fingerprint_sha256")
        == controller["fingerprint_sha256"],
        "projection controller receipt drifted",
    )
    expected_orders = _validate_geometry(
        projection.get("permutation_geometry", {}), fixture, controller
    )
    payload_seed = str(fixture["protocol"]["payload_blinding_seed"])
    attempt_seed = str(fixture["protocol"]["attempt_blinding_seed"])
    expected_execution = tuple(
        arm for block in BLOCK_IDS for arm in BLOCK_SCHEDULES[block]
    )
    _require(
        tuple(projection.get("execution_order", ())) == expected_execution,
        "projection execution order drifted",
    )
    _require(
        projection.get("block_schedules")
        == {block: list(BLOCK_SCHEDULES[block]) for block in BLOCK_IDS},
        "projection block schedules drifted",
    )

    payload_rows = projection.get("provider_payloads")
    treatment_rows = projection.get("public_treatment_key")
    _require(
        isinstance(payload_rows, list) and len(payload_rows) == 4,
        "projection must contain four payloads",
    )
    _require(
        isinstance(treatment_rows, list) and len(treatment_rows) == 4,
        "projection must contain four treatment rows",
    )
    payload_by_request: dict[str, Mapping[str, Any]] = {}
    for index, row in enumerate(payload_rows, start=1):
        _require(
            isinstance(row, Mapping) and set(row) == {"blinded_request_id", "payload"},
            f"payload row {index} schema drifted",
        )
        request_id = row.get("blinded_request_id")
        _require(
            isinstance(request_id, str)
            and request_id.startswith("Q_")
            and len(request_id) == 18
            and request_id not in payload_by_request,
            f"payload row {index} blind ID invalid",
        )
        payload = row.get("payload")
        _require(isinstance(payload, Mapping), f"payload row {index} payload invalid")
        payload_by_request[request_id] = payload

    arm_to_payload: dict[str, Mapping[str, Any]] = {}
    for index, row in enumerate(treatment_rows, start=1):
        _require(
            isinstance(row, Mapping)
            and set(row) == {"blinded_request_id", "treatment_id"},
            f"treatment row {index} schema drifted",
        )
        arm = row.get("treatment_id")
        request_id = row.get("blinded_request_id")
        _require(
            arm in ARMS and arm not in arm_to_payload,
            f"treatment row {index} arm invalid",
        )
        _require(
            request_id in payload_by_request, f"treatment row {index} blind ID missing"
        )
        _require(
            request_id
            == _blind_id(str(fixture["case"]["case_id"]), str(arm), payload_seed),
            f"treatment row {index} blind ID drifted",
        )
        arm_to_payload[str(arm)] = payload_by_request[str(request_id)]
    _require(
        set(arm_to_payload) == set(ARMS), "treatment mapping does not cover Z/C/D/X"
    )
    _require(
        len(payload_by_request) == len(arm_to_payload),
        "treatment mapping does not cover every payload",
    )

    schedule = projection.get("execution_schedule")
    _require(
        isinstance(schedule, list) and len(schedule) == 8,
        "execution schedule must contain eight attempts",
    )
    attempt_ids: set[str] = set()
    positions = {arm: [] for arm in ARMS}
    payload_fingerprint_by_arm = {
        arm: arm_to_payload[arm]["fingerprint_sha256"] for arm in ARMS
    }
    for index, row in enumerate(schedule, start=1):
        _require(
            isinstance(row, Mapping)
            and set(row)
            == {
                "sequence_index",
                "block_id",
                "within_block_index",
                "blinded_attempt_id",
                "blinded_request_id",
                "treatment_id",
                "payload_fingerprint_sha256",
            },
            f"execution schedule row {index} schema drifted",
        )
        block_id = BLOCK_IDS[(index - 1) // 4]
        within = ((index - 1) % 4) + 1
        arm = BLOCK_SCHEDULES[block_id][within - 1]
        _require(
            row.get("sequence_index") == index
            and row.get("block_id") == block_id
            and row.get("within_block_index") == within
            and row.get("treatment_id") == arm,
            f"execution schedule row {index} coordinate drifted",
        )
        attempt = _attempt_id(
            str(fixture["case"]["case_id"]), block_id, arm, attempt_seed
        )
        _require(
            row.get("blinded_attempt_id") == attempt and attempt not in attempt_ids,
            f"execution schedule row {index} attempt ID drifted",
        )
        attempt_ids.add(attempt)
        _require(
            row.get("blinded_request_id")
            == _blind_id(str(fixture["case"]["case_id"]), arm, payload_seed),
            f"execution schedule row {index} request reuse drifted",
        )
        _require(
            row.get("payload_fingerprint_sha256") == payload_fingerprint_by_arm[arm],
            f"execution schedule row {index} payload fingerprint drifted",
        )
        positions[arm].append(within)
    _require(
        {arm: sorted(value) for arm, value in positions.items()}
        == {"C": [1, 3], "D": [1, 3], "X": [2, 4], "Z": [2, 4]},
        "pairwise serial positions are not counterbalanced",
    )

    normalized: set[bytes] = set()
    payload_fingerprints: set[str] = set()
    chunk_multisets: set[tuple[str, ...]] = set()
    candidate_catalogs: set[bytes] = set()
    for arm in ARMS:
        payload = arm_to_payload[arm]
        raw_fingerprint, chunks = _validate_payload(
            payload,
            fixture=fixture,
            expected_order=expected_orders[arm],
            label=f"payload {arm}",
        )
        raw_payload = _without_fingerprint(payload)
        normalized.add(_canonical_bytes(_normalized_payload(raw_payload)))
        payload_fingerprints.add(raw_fingerprint)
        chunk_multisets.add(chunks)
        candidate_catalogs.add(_canonical_bytes(raw_payload["candidate_closures"]))
    _require(len(normalized) == 1, "provider payloads differ outside evidence order")
    _require(
        len(payload_fingerprints) == 4,
        "provider payload fingerprints are not four distinct values",
    )
    _require(len(chunk_multisets) == 1, "provider evidence chunk multisets differ")
    _require(len(candidate_catalogs) == 1, "provider candidate catalogs differ")
    _require(
        next(iter(chunk_multisets))
        == tuple(
            sorted(
                _sha256(_canonical_bytes(row))
                for row in fixture["case"]["raw_evidence"]
            )
        ),
        "provider evidence chunks differ from fixture",
    )
    return {
        "orders": expected_orders,
        "payload_fingerprints": payload_fingerprints,
        "scheduled_attempts": len(schedule),
    }


def _validate_self_test(
    self_test: Mapping[str, Any],
    *,
    controller: Mapping[str, Any],
    projection: Mapping[str, Any],
    classifier_audit: Mapping[str, Any],
) -> None:
    _validate_fingerprint(self_test, label="self-test")
    _require(
        set(self_test)
        == {
            "schema_version",
            "status",
            "hard_gates",
            "controller_fingerprint_sha256",
            "projection_fingerprint_sha256",
            "predecessor_anchor_fingerprint_sha256",
            "classifier_combinations_exercised",
            "aggregate_status_pairs_exercised",
            "aggregate_closure_block_pairs_exercised",
            "network_calls",
            "provider_calls",
            "claim_boundary",
            "fingerprint_sha256",
        },
        "self-test keyset drifted",
    )
    _require(
        self_test.get("schema_version") == SELF_TEST_SCHEMA, "self-test schema drifted"
    )
    _require(self_test.get("status") == SELF_TEST_STATUS, "self-test status drifted")
    gates = self_test.get("hard_gates")
    _require(
        isinstance(gates, list) and len(gates) == len(HARD_GATE_IDS),
        "self-test hard-gate count drifted",
    )
    _require(
        gates == [{"gate_id": gate_id, "passed": True} for gate_id in HARD_GATE_IDS],
        "self-test hard gates drifted",
    )
    _require(
        self_test.get("controller_fingerprint_sha256")
        == controller["fingerprint_sha256"],
        "self-test controller receipt drifted",
    )
    _require(
        self_test.get("projection_fingerprint_sha256")
        == projection["fingerprint_sha256"],
        "self-test projection receipt drifted",
    )
    _require(
        self_test.get("classifier_combinations_exercised")
        == classifier_audit["per_block_classifier_combinations_verified"],
        "self-test classifier coverage drifted",
    )
    _require(
        self_test.get("aggregate_status_pairs_exercised")
        == classifier_audit["aggregate_status_pairs_verified"],
        "self-test aggregate status coverage drifted",
    )
    _require(
        self_test.get("aggregate_closure_block_pairs_exercised")
        == classifier_audit["aggregate_closure_block_pairs_verified"],
        "self-test aggregate closure-pair coverage drifted",
    )
    _require(self_test.get("network_calls") == 0, "self-test network calls are nonzero")
    _require(
        self_test.get("provider_calls") == 0, "self-test provider calls are nonzero"
    )


def _validate_policy(
    root: Path,
    policy: Mapping[str, Any],
    *,
    fixture: Mapping[str, Any],
    projection: Mapping[str, Any],
) -> None:
    _validate_fingerprint(policy, label="policy")
    _require(
        set(policy)
        == {
            "schema_version",
            "status",
            "protocol",
            "runtime_contract",
            "predecessor_eligibility_anchor",
            "artifact",
            "canonicalization",
            "sources",
            "claim_boundary",
            "fingerprint_sha256",
        },
        "policy top-level keyset drifted",
    )
    _require(policy.get("schema_version") == POLICY_SCHEMA, "policy schema drifted")
    _require(policy.get("status") == POLICY_STATUS, "policy status drifted")
    _require(
        policy.get("canonicalization")
        == {
            "encoding": "utf-8",
            "ensure_ascii": False,
            "sort_keys": True,
            "separators": [",", ":"],
            "allow_nan": False,
            "trailing_newline": True,
        },
        "policy canonicalization drifted",
    )
    artifact = policy.get("artifact")
    _require(isinstance(artifact, Mapping), "policy artifact contract missing")
    _require(
        artifact
        == {
            "directory": ARTIFACT_RELATIVE.as_posix(),
            "files": sorted(ARTIFACT_FILES),
            "network_calls": 0,
            "provider_calls": 0,
        },
        "policy artifact contract drifted",
    )
    runtime = policy.get("runtime_contract")
    _require(
        isinstance(runtime, Mapping)
        and set(runtime)
        == {
            "python",
            "machine",
            "torch",
            "pydantic",
            "model",
            "reasoning_effort",
            "max_output_tokens",
            "timeout_seconds",
            "sdk_retries",
            "store",
            "previous_response_id",
            "provider_calls_authorized",
        },
        "policy runtime contract drifted",
    )
    for key in ("python", "machine", "torch", "pydantic"):
        _require(
            isinstance(runtime.get(key), str) and bool(runtime[key]),
            f"runtime {key} is invalid",
        )
    protocol_fixture = fixture["protocol"]
    for key in (
        "model",
        "reasoning_effort",
        "max_output_tokens",
        "timeout_seconds",
        "sdk_retries",
        "store",
    ):
        _require(runtime.get(key) == protocol_fixture[key], f"runtime {key} drifted")
    _require(
        runtime.get("previous_response_id") is False,
        "runtime previous_response_id drifted",
    )
    _require(
        runtime.get("provider_calls_authorized") == 0,
        "runtime authorizes provider calls",
    )

    protocol = policy.get("protocol")
    _require(
        isinstance(protocol, Mapping)
        and set(protocol)
        == {
            "operator",
            "arms",
            "case_id",
            "provider_payload_count",
            "scheduled_call_count",
            "block_schedules",
            "execution_schedule",
            "execution_order",
            "orders",
            "hard_gate_ids",
            "primary_action_field",
            "positive_result",
            "v0_6_4_network_zero_preflight_may_open_only_after_aggregate_success",
            "v0_6_4_live_execution_authorized",
            "gold_release_condition",
            "gold_load_count_after_release",
            "retry_resume_backfill_tiebreak_ninth_call_allowed",
            "future_live_provider_instructions_sha256",
            "semantic_failures_are_endpoints",
            "structural_invalid_reasons",
        },
        "policy protocol keyset drifted",
    )
    _require(protocol.get("operator") == OPERATOR, "policy operator drifted")
    _require(protocol.get("arms") == list(ARMS), "policy arms drifted")
    _require(
        protocol.get("case_id") == fixture["case"]["case_id"], "policy case drifted"
    )
    _require(
        protocol.get("provider_payload_count") == 4, "policy payload count drifted"
    )
    _require(
        protocol.get("scheduled_call_count") == 8, "policy scheduled call count drifted"
    )
    _require(
        protocol.get("block_schedules") == projection["block_schedules"],
        "policy block schedules drifted",
    )
    _require(
        protocol.get("execution_schedule") == projection["execution_schedule"],
        "policy execution schedule drifted",
    )
    _require(
        protocol.get("execution_order") == projection["execution_order"],
        "policy execution order drifted",
    )
    _require(
        protocol.get("orders") == projection["permutation_geometry"]["orders"],
        "policy permutation orders drifted",
    )
    _require(
        protocol.get("hard_gate_ids") == list(HARD_GATE_IDS),
        "policy hard-gate order drifted",
    )
    _require(
        protocol.get("primary_action_field") == "selected_closure_id",
        "policy primary action drifted",
    )
    _require(
        protocol.get("positive_result") == "REPLICATION_DIRECTIONAL_COUNTERBALANCED",
        "policy positive result drifted",
    )
    _require(
        protocol.get(
            "v0_6_4_network_zero_preflight_may_open_only_after_aggregate_success"
        )
        is True,
        "policy v0.6.4 network-zero gate drifted",
    )
    _require(
        protocol.get("v0_6_4_live_execution_authorized") is False,
        "policy authorizes live v0.6.4",
    )
    _require(
        protocol.get("gold_release_condition")
        == "AFTER_EIGHT_STRUCTURALLY_VALID_TERMINALS"
        and protocol.get("gold_load_count_after_release") == 1,
        "policy delayed-gold contract drifted",
    )
    _require(
        protocol.get("retry_resume_backfill_tiebreak_ninth_call_allowed") is False,
        "policy permits rescue execution",
    )
    _require(
        protocol.get("future_live_provider_instructions_sha256")
        == "9f3eacea0d23d502ee22bac3317a41707b634d3a83c724845f6fc38f8d4d5ae2",
        "future live instruction fingerprint drifted",
    )
    _require(
        protocol.get("semantic_failures_are_endpoints") is True,
        "policy semantic endpoint rule drifted",
    )
    _require(
        protocol.get("structural_invalid_reasons")
        == [
            "provider_transport_or_timeout",
            "malformed_or_duplicate_key_json",
            "provider_output_schema_invalid",
            "unknown_closure_id",
        ],
        "policy structural-invalid reasons drifted",
    )
    sources = policy.get("sources")
    _require(
        isinstance(sources, Mapping) and set(sources) == SOURCE_RECEIPT_IDS,
        "policy source receipt set drifted",
    )
    expected_source_paths = {
        "core": "actuator_uptake_replication_v0_6_3_2.py",
        "fixture": FIXTURE_RELATIVE.as_posix(),
        "post_call_gold": GOLD_RELATIVE.as_posix(),
        "predecessor_fixture": PREDECESSOR_FIXTURE_RELATIVE.as_posix(),
        "predecessor_gold": PREDECESSOR_GOLD_RELATIVE.as_posix(),
        "predecessor_result": PREDECESSOR_RESULT_RELATIVE.as_posix(),
        "predecessor_manifest": PREDECESSOR_MANIFEST_RELATIVE.as_posix(),
        "protocol_note": "docs/RND_ACTUATOR_UPTAKE_REPLICATION_V0_6_3_2.md",
        "requirements": "requirements.txt",
    }
    for source_id, expected_path in expected_source_paths.items():
        receipt = sources[source_id]
        _require(
            isinstance(receipt, Mapping) and receipt.get("path") == expected_path,
            f"source {source_id} path drifted",
        )
        _validate_source_receipt(root, receipt, label=f"source {source_id}")
    anchor = policy.get("predecessor_eligibility_anchor")
    _require(isinstance(anchor, Mapping), "predecessor eligibility anchor missing")
    _validate_fingerprint(anchor, label="predecessor eligibility anchor")
    _require(
        anchor.get("result_tag_object") == PREDECESSOR_RESULT_TAG_OBJECT,
        "predecessor tag object drifted",
    )
    _require(
        anchor.get("result_commit") == PREDECESSOR_RESULT_COMMIT,
        "predecessor result commit drifted",
    )
    _require(
        anchor.get("terminal_decision") == "PROMOTE_TO_FRESH_REPLICATION",
        "predecessor anchor terminal drifted",
    )
    _require(
        anchor.get("direct_v0_6_4_promotion_allowed") is False,
        "predecessor anchor directly promotes v0.6.4",
    )


def _validate_manifest(
    manifest: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    projection: Mapping[str, Any],
    controller: Mapping[str, Any],
    self_test: Mapping[str, Any],
    artifact_raw: Mapping[str, bytes],
) -> None:
    _validate_fingerprint(manifest, label="manifest")
    _require(
        set(manifest)
        == {
            "schema_version",
            "status",
            "policy_lock_fingerprint_sha256",
            "predecessor_anchor_fingerprint_sha256",
            "projection_fingerprint_sha256",
            "controller_fingerprint_sha256",
            "self_test_fingerprint_sha256",
            "artifact_receipts",
            "network_calls",
            "provider_calls",
            "live_execution_authorized",
            "claim_boundary",
            "fingerprint_sha256",
        },
        "manifest top-level keyset drifted",
    )
    _require(
        manifest.get("schema_version") == MANIFEST_SCHEMA, "manifest schema drifted"
    )
    _require(manifest.get("status") == MANIFEST_STATUS, "manifest status drifted")
    _require(
        manifest.get("live_execution_authorized") is False,
        "manifest authorizes live execution",
    )
    _require(manifest.get("network_calls") == 0, "manifest network calls are nonzero")
    _require(manifest.get("provider_calls") == 0, "manifest provider calls are nonzero")
    _require(
        manifest.get("policy_lock_fingerprint_sha256") == policy["fingerprint_sha256"],
        "manifest policy fingerprint drifted",
    )
    _require(
        manifest.get("predecessor_anchor_fingerprint_sha256")
        == policy["predecessor_eligibility_anchor"]["fingerprint_sha256"],
        "manifest predecessor anchor drifted",
    )
    _require(
        manifest.get("projection_fingerprint_sha256")
        == projection["fingerprint_sha256"],
        "manifest projection fingerprint drifted",
    )
    _require(
        manifest.get("controller_fingerprint_sha256")
        == controller["fingerprint_sha256"],
        "manifest controller fingerprint drifted",
    )
    _require(
        manifest.get("self_test_fingerprint_sha256") == self_test["fingerprint_sha256"],
        "manifest self-test fingerprint drifted",
    )
    receipts = manifest.get("artifact_receipts")
    _require(
        isinstance(receipts, Mapping) and set(receipts) == RECEIPTED_ARTIFACT_FILES,
        "manifest artifact receipt set drifted",
    )
    for filename in sorted(RECEIPTED_ARTIFACT_FILES):
        _validate_artifact_receipt(
            receipts[filename], raw=artifact_raw[filename], label=f"artifact {filename}"
        )


def _validate_all_recorded_calls_zero(value: Any, *, label: str) -> int:
    count = 0
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in {
                "provider_calls",
                "provider_calls_authorized",
                "provider_calls_observed",
                "network_calls",
            }:
                _require(type(child) is int and child == 0, f"{label}.{key} is nonzero")
                count += 1
            count += _validate_all_recorded_calls_zero(child, label=f"{label}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            count += _validate_all_recorded_calls_zero(child, label=f"{label}[{index}]")
    return count


def _artifact_entry_names(root: Path) -> set[str]:
    try:
        directory_stat = root.lstat()
    except OSError as error:
        raise VerificationError(f"cannot stat artifact directory: {root}") from error
    _require(
        stat.S_ISDIR(directory_stat.st_mode) and not root.is_symlink(),
        "artifact root must be a real directory",
    )
    entries = list(root.iterdir())
    _require(
        {path.name for path in entries} == ARTIFACT_FILES,
        "artifact directory entry set drifted",
    )
    for path in entries:
        file_stat = path.lstat()
        _require(
            stat.S_ISREG(file_stat.st_mode) and not path.is_symlink(),
            f"artifact entry must be a regular non-symlink file: {path.name}",
        )
    return {path.name for path in entries}


def verify(root: Path = ROOT, artifact_dir: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    artifact_dir = artifact_dir or root / ARTIFACT_RELATIVE
    _require(
        artifact_dir == root / ARTIFACT_RELATIVE, "non-canonical artifact directory"
    )
    _artifact_entry_names(artifact_dir)

    policy_raw, policy = _strict_object(
        root / POLICY_RELATIVE, label="policy", canonical_pretty=True
    )
    _validate_canonical_anchor(
        policy_raw, expected_file=EXPECTED_POLICY_FILE, label="policy"
    )
    fixture_raw, fixture = _strict_object(root / FIXTURE_RELATIVE, label="fixture")
    gold_raw, gold = _strict_object(root / GOLD_RELATIVE, label="gold")
    _validate_fixture(fixture)
    _validate_gold(gold, fixture)
    classifier_audit = _verify_classifier_contract(fixture, gold)
    _, predecessor_fixture = _strict_object(
        root / PREDECESSOR_FIXTURE_RELATIVE, label="predecessor fixture"
    )
    _, predecessor_gold = _strict_object(
        root / PREDECESSOR_GOLD_RELATIVE, label="predecessor gold"
    )
    predecessor_result_raw, predecessor_result = _strict_object(
        root / PREDECESSOR_RESULT_RELATIVE,
        label="predecessor result",
        canonical_pretty=True,
    )
    predecessor_manifest_raw, predecessor_manifest = _strict_object(
        root / PREDECESSOR_MANIFEST_RELATIVE,
        label="predecessor manifest",
        canonical_pretty=True,
    )
    _validate_freshness(fixture, gold, predecessor_fixture, predecessor_gold)
    predecessor_audit = _validate_predecessor_eligibility(
        predecessor_result_raw,
        predecessor_result,
        predecessor_manifest_raw,
        predecessor_manifest,
    )

    artifact_raw: dict[str, bytes] = {}
    artifacts: dict[str, dict[str, Any]] = {}
    for filename in sorted(ARTIFACT_FILES):
        raw, value = _strict_object(
            artifact_dir / filename, label=f"artifact {filename}", canonical_pretty=True
        )
        artifact_raw[filename] = raw
        artifacts[filename] = value
    projection = artifacts["projection_bundle.json"]
    controller = artifacts["controller_audit.json"]
    self_test_value = artifacts["self_test.json"]
    manifest = artifacts["manifest.json"]
    _validate_canonical_anchor(
        artifact_raw["manifest.json"],
        expected_file=EXPECTED_MANIFEST_FILE,
        label="manifest",
    )

    nested_fingerprints = sum(
        _validate_nested_fingerprints(value, label=filename)
        for filename, value in artifacts.items()
    )
    _require(nested_fingerprints >= 9, "too few nested fingerprints were verified")
    _validate_controller(controller, fixture)
    projection_audit = _validate_projection(
        projection, fixture=fixture, controller=controller
    )
    _validate_self_test(
        self_test_value,
        controller=controller,
        projection=projection,
        classifier_audit=classifier_audit,
    )
    _validate_policy(root, policy, fixture=fixture, projection=projection)
    _require(
        self_test_value.get("predecessor_anchor_fingerprint_sha256")
        == policy["predecessor_eligibility_anchor"]["fingerprint_sha256"],
        "self-test predecessor anchor drifted",
    )
    _validate_manifest(
        manifest,
        policy=policy,
        projection=projection,
        controller=controller,
        self_test=self_test_value,
        artifact_raw=artifact_raw,
    )

    sources = policy["sources"]
    _require(
        sources["fixture"]["bytes"] == len(fixture_raw)
        and sources["fixture"]["sha256"] == _sha256(fixture_raw),
        "fixture source receipt drifted",
    )
    _require(
        sources["post_call_gold"]["bytes"] == len(gold_raw)
        and sources["post_call_gold"]["sha256"] == _sha256(gold_raw),
        "gold source receipt drifted",
    )
    call_fields = sum(
        _validate_all_recorded_calls_zero(value, label=label)
        for label, value in {
            "policy": policy,
            "manifest": manifest,
            "projection": projection,
            "self-test": self_test_value,
        }.items()
    )
    _require(call_fields == 9, "provider/network call-field count drifted")

    return {
        "schema_version": "ebrt-actuator-uptake-portable-verification-v0.6.3.2",
        "status": "PASS_PORTABLE_NETWORK_ZERO",
        "artifact_directory": ARTIFACT_RELATIVE.as_posix(),
        "policy_sha256": _sha256(policy_raw),
        "manifest_sha256": _sha256(artifact_raw["manifest.json"]),
        "policy_fingerprint_sha256": policy["fingerprint_sha256"],
        "manifest_fingerprint_sha256": manifest["fingerprint_sha256"],
        "nested_fingerprints_verified": nested_fingerprints,
        "hard_gates_verified": len(HARD_GATE_IDS),
        "provider_payloads_verified": len(projection["provider_payloads"]),
        "scheduled_attempts_verified": projection_audit["scheduled_attempts"],
        "predecessor_result_fingerprint_sha256": predecessor_audit[
            "result_fingerprint_sha256"
        ],
        "provider_payload_fingerprints_verified": len(
            projection_audit["payload_fingerprints"]
        ),
        **classifier_audit,
        "recorded_call_fields_verified": call_fields,
        "provider_calls": 0,
        "network_calls": 0,
        "claim_boundary": [
            "This independently verifies frozen network-zero bytes and public contracts only.",
            "It does not import the producer, rerun autograd, contact a provider, or establish hosted actuator uptake.",
        ],
    }


def _expect_rejected(callback: Callable[[], Any], label: str) -> None:
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
    _expect_rejected(
        lambda: _strict_json_bytes(b'{"x":1e999}', label="overflow probe"),
        "overflowing JSON number",
    )
    policy_raw = _read_regular(root / POLICY_RELATIVE, label="policy anchor probe")
    _expect_rejected(
        lambda: _validate_canonical_anchor(
            policy_raw + b"\n",
            expected_file=EXPECTED_POLICY_FILE,
            label="policy anchor probe",
        ),
        "policy exact-byte anchor",
    )
    manifest_raw = _read_regular(
        root / ARTIFACT_RELATIVE / "manifest.json", label="manifest anchor probe"
    )
    _expect_rejected(
        lambda: _validate_canonical_anchor(
            manifest_raw[:-1] + b" ",
            expected_file=EXPECTED_MANIFEST_FILE,
            label="manifest anchor probe",
        ),
        "manifest exact-byte anchor",
    )
    _, fixture = _strict_object(root / FIXTURE_RELATIVE, label="fixture probe")
    _, controller = _strict_object(
        root / ARTIFACT_RELATIVE / "controller_audit.json",
        label="controller probe",
        canonical_pretty=True,
    )
    _, projection = _strict_object(
        root / ARTIFACT_RELATIVE / "projection_bundle.json",
        label="projection probe",
        canonical_pretty=True,
    )

    evidence_tamper = copy.deepcopy(projection)
    payload = evidence_tamper["provider_payloads"][0]["payload"]
    payload["ordered_raw_evidence"][0]["text"] += " tamper"
    evidence_tamper["provider_payloads"][0]["payload"] = _seal(payload)
    evidence_tamper = _seal(evidence_tamper)
    _expect_rejected(
        lambda: _validate_projection(
            evidence_tamper, fixture=fixture, controller=controller
        ),
        "immutable evidence chunk",
    )

    candidate_tamper = copy.deepcopy(projection)
    payload = candidate_tamper["provider_payloads"][0]["payload"]
    payload["candidate_closures"][0]["selected_evidence_ids"] = ["N1", "N2", "N6"]
    candidate_tamper["provider_payloads"][0]["payload"] = _seal(payload)
    candidate_tamper = _seal(candidate_tamper)
    _expect_rejected(
        lambda: _validate_projection(
            candidate_tamper, fixture=fixture, controller=controller
        ),
        "candidate cardinality/catalog",
    )

    mapping_tamper = copy.deepcopy(projection)
    mapping_tamper["public_treatment_key"][0]["treatment_id"] = "C"
    mapping_tamper = _seal(mapping_tamper)
    _expect_rejected(
        lambda: _validate_projection(
            mapping_tamper, fixture=fixture, controller=controller
        ),
        "Z/C/D/X treatment mapping",
    )

    schedule_tamper = copy.deepcopy(projection)
    schedule_tamper["execution_schedule"][4]["within_block_index"] = 2
    schedule_tamper = _seal(schedule_tamper)
    _expect_rejected(
        lambda: _validate_projection(
            schedule_tamper, fixture=fixture, controller=controller
        ),
        "mirrored schedule coordinate",
    )

    reuse_tamper = copy.deepcopy(projection)
    reuse_tamper["execution_schedule"][4]["payload_fingerprint_sha256"] = "0" * 64
    reuse_tamper = _seal(reuse_tamper)
    _expect_rejected(
        lambda: _validate_projection(
            reuse_tamper, fixture=fixture, controller=controller
        ),
        "same-arm payload reuse",
    )

    nonzero_tamper = {"provider_calls": 1, "network_calls": 0}
    _expect_rejected(
        lambda: _validate_all_recorded_calls_zero(
            nonzero_tamper, label="nonzero probe"
        ),
        "nonzero provider calls",
    )
    with tempfile.TemporaryDirectory(prefix="ebrt-v0631-portable-extra-") as raw:
        tamper_root = Path(raw)
        for filename in sorted(ARTIFACT_FILES):
            source = root / ARTIFACT_RELATIVE / filename
            (tamper_root / filename).write_bytes(
                _read_regular(source, label=f"extra-file probe {filename}")
            )
        (tamper_root / "extra.json").write_bytes(b"{}\n")
        _expect_rejected(
            lambda: _artifact_entry_names(tamper_root),
            "extra artifact entry",
        )

    result["status"] = "PASS_PORTABLE_WITH_TAMPER_SELF_TEST"
    result["tamper_checks"] = {
        "duplicate_json_rejected": True,
        "nonfinite_json_rejected": True,
        "policy_exact_byte_anchor_tamper_rejected": True,
        "manifest_exact_byte_anchor_tamper_rejected": True,
        "immutable_chunk_tamper_rejected": True,
        "candidate_catalog_tamper_rejected": True,
        "treatment_mapping_tamper_rejected": True,
        "mirrored_schedule_tamper_rejected": True,
        "payload_reuse_tamper_rejected": True,
        "nonzero_calls_rejected": True,
        "extra_artifact_entry_rejected": True,
    }
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
