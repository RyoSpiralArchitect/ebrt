#!/usr/bin/env python3
"""Portable verifier for the frozen EBRT v0.5.2 canonical walkthrough.

This file was added after the live run.  It does not reproduce local autograd
or authenticate OpenAI.  It verifies the externally pinned canonical bytes,
their frozen repository source graph, recorded producer-runtime consistency,
and the public ledger/grade derivations without importing project packages.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parent
DEFAULT_ARTIFACT_DIR = (
    ROOT / "artifacts" / "demo_hackathon_strategy_walkthrough_v0_5_2_live_r01"
)
POLICY_PATH = "policy_lock_hackathon_strategy_walkthrough_v0_5_2.json"
PHASE_ORDER = ("before_event", "controlled_after_event")
EXPECTED_MANIFEST_SHA256 = (
    "ab86d111d1fc0d2b679a0f6ca001e9d33ae1bfc86468aee404887e3da934299f"
)
EXPECTED_POLICY_SHA256 = (
    "551190c872d3b9bb9db4f2d6fd1aa15f3f9102084e057e90b80d9259ac429c6c"
)
EXPECTED_RESULT_SHA256 = (
    "2e641e0f11f17bb16cbe629048e9cc8cff49706147616d888487f38b243430d4"
)
EXPECTED_ARTIFACTS = {
    "calls.jsonl": (
        3820,
        "0d7794f1b6f3010e3d8171d46f4574ad7801e1e96eef84850dc52519cf0b634e",
    ),
    "demo.json": (
        27548,
        "f6df3c0a371027fd6ed35cfcc75f0b05dc540ebb6d08efeb3764ab62b4616f6b",
    ),
    "manifest.json": (2758, EXPECTED_MANIFEST_SHA256),
    "report.md": (
        2759,
        "81868e378daab3498edbe758ceff9910e7ac0f8c7b444e6913b4ec3e0203fe1d",
    ),
}
EXPECTED_REPOSITORY_FILES = {
    "demo_hackathon_strategy_walkthrough_v0_5_2.py": (
        "f39d565d7a6048d025d6151dc286e93457c73ca641332166ab87219aa70878fe"
    ),
    "controlled_raw_restart_v0_5_1.py": (
        "94d9f527334ef7b496db7afb3f6faf847b488e8b0ec043f486991e92092dde08"
    ),
    "benchmark_controlled_raw_restart_v0_5_1.py": (
        "18ba54ebfd0cab2b3d35dab828a0fa2a8baf7edc0d965ce48b5ded3f09558a5c"
    ),
    "temporal_adjoint_state_controller_v0_5_t.py": (
        "43df27a8595274f694e7c0741c4fe642a66ae37a0719e5d3256d4a0f37f6b7b5"
    ),
    "openai_response_boundary_v0_4_3.py": (
        "7f78fce94cb141a4355d3c040010e11e049ff67a3a8c603099d0548a47b7cf03"
    ),
    "benchmark_language_replay_v0_4.py": (
        "813ab885cecdacec034536a7dfeaa01c101554cc58663d1a79ad133595c6df91"
    ),
    "language_replay_bridge_v0_4.py": (
        "5fd765ec5ca55562e7b712ec48adc6f54588080c276cbfa58aabcb72492666c2"
    ),
    "fixtures/hackathon_strategy_walkthrough_v0_5_2.json": (
        "ef0b1d44ece10e7412460d9abac4791fe3f3a0172e398bca7a0d8957094f56d2"
    ),
    "fixtures/hackathon_strategy_walkthrough_v0_5_2_gold.json": (
        "c9aea1cc992b9bec8b6b00ec4ed941543e3a87f48786dc1729df876cd08d29f3"
    ),
}
SOURCE_LABEL_PATHS = {
    "walkthrough_runner": "demo_hackathon_strategy_walkthrough_v0_5_2.py",
    "controlled_restart_bridge": "controlled_raw_restart_v0_5_1.py",
    "sealed_receipt_harness": "benchmark_controlled_raw_restart_v0_5_1.py",
    "temporal_controller": "temporal_adjoint_state_controller_v0_5_t.py",
    "provider_boundary": "openai_response_boundary_v0_4_3.py",
    "strict_grader": "benchmark_language_replay_v0_4.py",
    "public_card_schema": "language_replay_bridge_v0_4.py",
}
FIXTURE_LABEL_PATHS = {
    "fixture": "fixtures/hackathon_strategy_walkthrough_v0_5_2.json",
    "gold": "fixtures/hackathon_strategy_walkthrough_v0_5_2_gold.json",
}
MAX_FILE_BYTES = 2_000_000
HEX_KEYS = (
    "client_request_id_sha256",
    "provider_body_sha256",
    "response_id_sha256",
    "server_request_id_sha256",
)


class VerificationError(RuntimeError):
    """Raised when the canonical evidence graph does not validate."""


def _reject_constant(value: str) -> Any:
    raise VerificationError(f"non-finite JSON constant is forbidden: {value}")


def _object_no_duplicates(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
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
            object_pairs_hook=_object_no_duplicates,
            parse_constant=_reject_constant,
        )
    except VerificationError:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise VerificationError(f"{label} is not strict JSON") from error


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


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


def _safe_repo_path(repo_root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    _require(
        not pure.is_absolute(), f"absolute repository path is forbidden: {relative}"
    )
    _require(".." not in pure.parts, f"parent traversal is forbidden: {relative}")
    _require(
        relative in EXPECTED_REPOSITORY_FILES, f"unexpected repository path: {relative}"
    )
    return repo_root.joinpath(*pure.parts)


def _read_artifact_files(artifact_dir: Path) -> dict[str, bytes]:
    try:
        root_stat = artifact_dir.lstat()
    except OSError as error:
        raise VerificationError(
            f"cannot stat artifact directory: {artifact_dir}"
        ) from error
    _require(stat.S_ISDIR(root_stat.st_mode), "artifact root must be a directory")
    _require(not artifact_dir.is_symlink(), "artifact root must not be a symlink")
    names = sorted(item.name for item in artifact_dir.iterdir())
    _require(names == sorted(EXPECTED_ARTIFACTS), "artifact file set mismatch")
    output: dict[str, bytes] = {}
    for name, (expected_bytes, expected_hash) in EXPECTED_ARTIFACTS.items():
        value = _read_regular(artifact_dir / name, label=f"artifact {name}")
        _require(len(value) == expected_bytes, f"canonical byte count mismatch: {name}")
        _require(_sha256(value) == expected_hash, f"canonical SHA-256 mismatch: {name}")
        output[name] = value
    return output


def _validate_lock(repo_root: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    policy_bytes = _read_regular(repo_root / POLICY_PATH, label="policy lock")
    _require(_sha256(policy_bytes) == EXPECTED_POLICY_SHA256, "policy SHA-256 mismatch")
    policy = _strict_json_bytes(policy_bytes, label="policy lock")
    _require(isinstance(policy, dict), "policy root must be an object")
    _require(
        policy.get("schema_version")
        == "ebrt-hackathon-strategy-walkthrough-policy-lock-v0.5.2",
        "policy schema drifted",
    )
    _require(
        policy.get("promotion_eligible") is False, "policy promotion boundary drifted"
    )
    _require(
        policy.get("execution", {}).get("phase_order") == list(PHASE_ORDER)
        and policy["execution"].get("expected_api_attempts") == 2
        and policy["execution"].get("calls_per_phase") == 1
        and policy["execution"].get("retry_policy") == "one_attempt_no_retry",
        "policy execution geometry drifted",
    )
    repository_bytes: dict[str, bytes] = {}
    for group_name, expected_paths in (
        ("sources", SOURCE_LABEL_PATHS),
        ("fixtures", FIXTURE_LABEL_PATHS),
    ):
        group = policy.get(group_name)
        _require(isinstance(group, dict), f"policy {group_name} must be an object")
        _require(
            set(group) == set(expected_paths), f"policy {group_name} labels drifted"
        )
        for label, expected_path in expected_paths.items():
            record = group[label]
            _require(
                isinstance(record, dict) and set(record) == {"path", "sha256"},
                f"policy path record drifted: {group_name}.{label}",
            )
            _require(record["path"] == expected_path, f"policy path drifted: {label}")
            expected_hash = EXPECTED_REPOSITORY_FILES[expected_path]
            _require(record["sha256"] == expected_hash, f"policy hash drifted: {label}")
            path = _safe_repo_path(repo_root, expected_path)
            value = _read_regular(path, label=f"repository file {expected_path}")
            _require(
                _sha256(value) == expected_hash,
                f"repository byte drift: {expected_path}",
            )
            repository_bytes[expected_path] = value
    _strict_json_bytes(
        repository_bytes[FIXTURE_LABEL_PATHS["fixture"]], label="walkthrough fixture"
    )
    _strict_json_bytes(
        repository_bytes[FIXTURE_LABEL_PATHS["gold"]], label="walkthrough gold"
    )
    return policy, repository_bytes


def _validate_manifest(manifest: Mapping[str, Any], policy: Mapping[str, Any]) -> None:
    _require(
        set(manifest)
        == {
            "artifacts",
            "claim_boundary",
            "policy_lock",
            "result_fingerprint_sha256",
            "runtime",
            "schema_version",
            "source_snapshot_sha256",
            "status",
            "walkthrough_contract_passed",
        },
        "manifest schema drifted",
    )
    _require(
        manifest["schema_version"] == "ebrt-hackathon-strategy-artifact-v0.5.2",
        "manifest version drifted",
    )
    _require(manifest["status"] == "COMPLETE_CALL_BLOCK", "manifest status drifted")
    _require(
        manifest["walkthrough_contract_passed"] is False, "frozen endpoint drifted"
    )
    _require(
        manifest["result_fingerprint_sha256"] == EXPECTED_RESULT_SHA256,
        "manifest result fingerprint drifted",
    )
    _require(
        manifest["policy_lock"]
        == {"path": POLICY_PATH, "sha256": EXPECTED_POLICY_SHA256},
        "manifest policy anchor drifted",
    )
    _require(
        manifest["claim_boundary"] == policy["claim_boundary"], "claim boundary drifted"
    )
    records = manifest["artifacts"]
    _require(
        set(records) == {"demo.json", "calls.jsonl", "report.md"},
        "manifest artifact set drifted",
    )
    for name in records:
        expected_bytes, expected_hash = EXPECTED_ARTIFACTS[name]
        _require(
            records[name] == {"bytes": expected_bytes, "sha256": expected_hash},
            f"manifest artifact record drifted: {name}",
        )
    runtime = manifest["runtime"]
    _require(
        set(runtime)
        == {
            "machine",
            "openai",
            "operating_system",
            "operating_system_release",
            "pydantic",
            "python",
        },
        "manifest runtime schema drifted",
    )
    for key in ("machine", "openai", "pydantic", "python"):
        _require(
            runtime[key] == policy["runtime"][key], f"recorded runtime drifted: {key}"
        )
    _require(
        isinstance(runtime["operating_system"], str)
        and bool(runtime["operating_system"])
        and isinstance(runtime["operating_system_release"], str)
        and bool(runtime["operating_system_release"]),
        "recorded operating-system observation is missing",
    )
    snapshot = {
        **{label: policy["sources"][label]["sha256"] for label in SOURCE_LABEL_PATHS},
        **{
            f"fixture:{label}": policy["fixtures"][label]["sha256"]
            for label in FIXTURE_LABEL_PATHS
        },
    }
    _require(
        manifest["source_snapshot_sha256"] == snapshot, "manifest source graph drifted"
    )


def _fact_matches(card: Mapping[str, Any], expected: Mapping[str, Any]) -> bool:
    expected_ids = set(expected["evidence_ids"])
    return any(
        fact.get("slot") == expected["slot"]
        and fact.get("value") == expected["value"]
        and expected_ids <= set(fact.get("evidence_ids", []))
        for fact in card["decision_facts"]
    )


def _grade_card(
    card: Mapping[str, Any], final: Mapping[str, Any], grading: Mapping[str, Any]
) -> dict[str, Any]:
    support = set(card["evidence_ids"])
    for fact in card["decision_facts"]:
        support.update(fact["evidence_ids"])
    required = set(grading["required_evidence_ids"])
    forbidden = set(grading["forbidden_support_evidence_ids"])
    gold_support = set(final["evidence_ids"])
    expected_invalidated = set(grading["expected_invalidated_evidence_ids"])
    checks = {
        "answer_exact": card["current_answer"] == final["answer"],
        "required_facts_exact": all(
            _fact_matches(card, item) for item in grading["required_facts"]
        ),
        "stable_facts_exact": all(
            _fact_matches(card, item) for item in grading["stable_facts"]
        ),
        "required_evidence_present": required <= support,
        "forbidden_support_absent": not bool(forbidden & support),
        "expected_invalidated_evidence_marked": (
            expected_invalidated <= set(card["invalidated_evidence_ids"])
        ),
    }
    true_positive = len(support & gold_support)
    return {
        "machine_success": all(checks.values()),
        "evidence_consistent": all(
            value for name, value in checks.items() if name != "answer_exact"
        ),
        "checks": checks,
        "support_evidence_ids": sorted(support),
        "unexpected_support_evidence_ids": sorted(support - gold_support),
        "missing_required_evidence_ids": sorted(required - support),
        "citation_precision": true_positive / len(support) if support else 0.0,
        "citation_recall": true_positive / len(gold_support) if gold_support else 1.0,
    }


def _support_ids(card: Mapping[str, Any]) -> set[str]:
    output = set(card["evidence_ids"])
    for fact in card["decision_facts"]:
        output.update(fact["evidence_ids"])
    return output


def _ordered(values: set[str], evidence_order: Sequence[str]) -> list[str]:
    return [item for item in evidence_order if item in values]


def _public_diff(
    before: Mapping[str, Any], after: Mapping[str, Any], evidence_order: Sequence[str]
) -> dict[str, Any]:
    slot_order = ["final_priority", "demo_centerpiece", "video_constraint"]
    before_facts = {item["slot"]: item for item in before["decision_facts"]}
    after_facts = {item["slot"]: item for item in after["decision_facts"]}
    changes: list[dict[str, Any]] = []
    for slot in slot_order:
        old = before_facts.get(slot)
        new = after_facts.get(slot)
        old_public = (
            None
            if old is None
            else {"value": old["value"], "evidence_ids": old["evidence_ids"]}
        )
        new_public = (
            None
            if new is None
            else {"value": new["value"], "evidence_ids": new["evidence_ids"]}
        )
        if old_public != new_public:
            changes.append({"slot": slot, "before": old_public, "after": new_public})
    before_support = _support_ids(before)
    after_support = _support_ids(after)
    before_invalid = set(before["invalidated_evidence_ids"])
    after_invalid = set(after["invalidated_evidence_ids"])
    return {
        "answer_before": before["current_answer"],
        "answer_after": after["current_answer"],
        "answer_changed": before["current_answer"] != after["current_answer"],
        "support_before_ids": _ordered(before_support, evidence_order),
        "support_after_ids": _ordered(after_support, evidence_order),
        "support_added_ids": _ordered(after_support - before_support, evidence_order),
        "support_dropped_ids": _ordered(before_support - after_support, evidence_order),
        "invalidated_added_ids": _ordered(
            after_invalid - before_invalid, evidence_order
        ),
        "invalidated_dropped_ids": _ordered(
            before_invalid - after_invalid, evidence_order
        ),
        "decision_fact_changes": changes,
        "derived_from": "public_reasoning_cards_only",
    }


def _validate_receipt(phase: Mapping[str, Any], policy: Mapping[str, Any]) -> None:
    receipt = phase["receipt"]
    _require(isinstance(receipt, dict), "completed phase lacks a receipt")
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
        "receipt schema drifted",
    )
    runtime = policy["runtime"]
    metadata = receipt["metadata"]
    _require(
        receipt["api_calls"] == 1 and receipt["logical_calls"] == 1,
        "call accounting drifted",
    )
    _require(
        isinstance(receipt["latency_ms"], (int, float))
        and math.isfinite(receipt["latency_ms"])
        and 0 <= receipt["latency_ms"] <= runtime["timeout_seconds"] * 1000,
        "receipt latency is invalid",
    )
    _require(receipt["provider"] == runtime["provider"], "receipt provider drifted")
    _require(
        receipt["requested_model"] == runtime["model"]
        and receipt["returned_model"] == runtime["model"],
        "receipt model drifted",
    )
    _require(
        receipt["prompt_fingerprint"] == policy["instructions_fingerprint_sha256"],
        "prompt fingerprint drifted",
    )
    expected_request = _sha256(_canonical_json_bytes(phase["provider_input"]))
    _require(
        receipt["request_fingerprint"] == expected_request,
        "request fingerprint drifted",
    )
    _require(
        phase["provider_input_fingerprint_sha256"] == expected_request,
        "phase request fingerprint drifted",
    )
    for key, expected in (
        ("python_version", runtime["python"]),
        ("sdk_version", runtime["openai"]),
        ("pydantic_version", runtime["pydantic"]),
        ("reasoning_effort", runtime["reasoning_effort"]),
        ("service_tier", runtime["service_tier"]),
        ("max_output_tokens", runtime["max_output_tokens"]),
        ("store", runtime["store"]),
        ("previous_response_id", runtime["previous_response_id"]),
        ("truncation", runtime["truncation"]),
        ("retry_count", runtime["sdk_retries"]),
    ):
        _require(metadata.get(key) == expected, f"receipt metadata drifted: {key}")
    _require(
        metadata.get("attempt") == 1
        and metadata.get("attempt_outcome") == "completed"
        and metadata.get("status") == "completed"
        and metadata.get("http_observed") is True
        and metadata.get("http_status_code") == 200
        and metadata.get("parse_boundary") == "succeeded"
        and metadata.get("failure_phase") is None
        and metadata.get("failure_reason_code") is None
        and metadata.get("failure_type") is None,
        "receipt completion boundary drifted",
    )
    for key in HEX_KEYS:
        value = metadata.get(key)
        _require(
            isinstance(value, str)
            and len(value) == 64
            and all(char in "0123456789abcdef" for char in value),
            f"receipt hash drifted: {key}",
        )
    usage = receipt["usage"]
    _require(
        set(usage)
        == {
            "cache_write_tokens",
            "cached_input_tokens",
            "exact_provider_tokens",
            "input_tokens",
            "output_tokens",
            "reasoning_tokens",
            "total_tokens",
        },
        "usage schema drifted",
    )
    _require(usage["exact_provider_tokens"] is True, "provider token exactness drifted")
    for key in (
        "cache_write_tokens",
        "cached_input_tokens",
        "input_tokens",
        "output_tokens",
        "reasoning_tokens",
        "total_tokens",
    ):
        _require(
            type(usage[key]) is int and usage[key] >= 0,
            f"usage value is invalid: {key}",
        )
    _require(
        usage["total_tokens"] == usage["input_tokens"] + usage["output_tokens"],
        "total-token arithmetic drifted",
    )
    _require(
        usage["cached_input_tokens"] <= usage["input_tokens"],
        "cached-input usage drifted",
    )
    _require(
        usage["reasoning_tokens"] <= usage["output_tokens"],
        "reasoning-token usage drifted",
    )


def _validate_result(
    result: dict[str, Any],
    policy: Mapping[str, Any],
    fixture: Mapping[str, Any],
    gold: Mapping[str, Any],
) -> None:
    fingerprint_value = result.get("fingerprint_sha256")
    material = copy.deepcopy(result)
    material.pop("fingerprint_sha256", None)
    _require(
        fingerprint_value == EXPECTED_RESULT_SHA256
        and fingerprint_value == _sha256(_canonical_json_bytes(material)),
        "result fingerprint mismatch",
    )
    _require(
        result.get("schema_version") == "ebrt-hackathon-strategy-walkthrough-v0.5.2"
        and result.get("status") == "COMPLETE_CALL_BLOCK"
        and result.get("mode") == "openai_live_product_walkthrough",
        "result identity drifted",
    )
    execution = result["execution"]
    _require(
        execution
        == {
            "phase_order": list(PHASE_ORDER),
            "expected_attempts": 2,
            "observed_receipts": 2,
            "observed_api_calls": 2,
            "retry_policy": "one_attempt_no_retry",
            "semantic_gold_parsed_after_both_attempts": True,
        },
        "result execution geometry drifted",
    )
    _require(set(result["phases"]) == set(PHASE_ORDER), "result phase set drifted")
    for position, phase_id in enumerate(PHASE_ORDER):
        phase = result["phases"][phase_id]
        _require(
            phase["phase_id"] == phase_id
            and phase["run_position"] == position
            and phase["status"] == "completed"
            and phase["failure"] is None
            and phase["public_card"] is not None,
            f"phase completion drifted: {phase_id}",
        )
        _validate_receipt(phase, policy)
    before = result["phases"][PHASE_ORDER[0]]["public_card"]
    after = result["phases"][PHASE_ORDER[1]]["public_card"]
    before_grade = {
        "available": True,
        **_grade_card(before, gold["pre_event"], gold["grading"]["pre_event"]),
    }
    stale_grade = {
        "available": True,
        **_grade_card(before, gold["final"], gold["grading"]["final"]),
    }
    after_grade = {
        "available": True,
        **_grade_card(after, gold["final"], gold["grading"]["final"]),
    }
    _require(
        result["phases"][PHASE_ORDER[0]]["grade"] == before_grade,
        "Before grade drifted",
    )
    _require(
        result["phases"][PHASE_ORDER[0]]["post_event_regrade"] == stale_grade,
        "stale regrade drifted",
    )
    _require(
        result["phases"][PHASE_ORDER[1]]["grade"] == after_grade, "After grade drifted"
    )
    _require(
        result["phases"][PHASE_ORDER[1]]["post_event_regrade"] is None,
        "After regrade drifted",
    )
    fixture_case = fixture["case"]
    fixture_evidence = [
        item["evidence_id"] for item in fixture_case["initial_evidence"]
    ] + [fixture_case["late_evidence"]["evidence_id"]]
    expected_diff = _public_diff(before, after, fixture_evidence)
    _require(result["output_diff"] == expected_diff, "public output diff drifted")
    stable_before = next(
        item for item in before["decision_facts"] if item["slot"] == "video_constraint"
    )
    stable_after = next(
        item for item in after["decision_facts"] if item["slot"] == "video_constraint"
    )
    checks = {
        "both_calls_completed": True,
        "before_matches_pre_event_contract": before_grade["machine_success"],
        "before_is_stale_under_post_event_contract": not stale_grade["machine_success"],
        "after_matches_post_event_contract": after_grade["machine_success"],
        "answer_changes_polish_to_prove": (
            expected_diff["answer_before"] == "POLISH"
            and expected_diff["answer_after"] == "PROVE"
            and expected_diff["answer_changed"] is True
        ),
        "stable_video_constraint_preserved": stable_before == stable_after,
        "R3_invalidated_and_R6_added": (
            "R3" in expected_diff["invalidated_added_ids"]
            and "R3" in expected_diff["support_dropped_ids"]
            and "R6" in expected_diff["support_added_ids"]
        ),
    }
    _require(result["walkthrough_checks"] == checks, "walkthrough checks drifted")
    _require(
        result["decision"]
        == {
            "call_block_complete": True,
            "walkthrough_contract_passed": all(checks.values()),
            "causal_comparison": False,
            "promotion_eligible": False,
        },
        "walkthrough decision drifted",
    )


def _validate_calls_ledger(value: bytes, result: Mapping[str, Any]) -> None:
    _require(value.endswith(b"\n"), "calls ledger must have a trailing newline")
    raw_lines = value.splitlines()
    _require(
        len(raw_lines) == 2 and all(raw_lines),
        "calls ledger must contain exactly two rows",
    )
    rows = [
        _strict_json_bytes(line, label=f"calls row {index}")
        for index, line in enumerate(raw_lines)
    ]
    expected = [
        {
            "phase_id": phase_id,
            "run_position": result["phases"][phase_id]["run_position"],
            "status": result["phases"][phase_id]["status"],
            "evidence_horizon": result["phases"][phase_id]["evidence_horizon"],
            "provider_input_fingerprint_sha256": result["phases"][phase_id][
                "provider_input_fingerprint_sha256"
            ],
            "receipt": result["phases"][phase_id]["receipt"],
            "failure": result["phases"][phase_id]["failure"],
        }
        for phase_id in PHASE_ORDER
    ]
    _require(rows == expected, "calls ledger rows drifted")
    expected_bytes = b"".join(_canonical_json_bytes(row) + b"\n" for row in expected)
    _require(value == expected_bytes, "calls ledger serialization drifted")


def verify_artifact(
    artifact_dir: Path,
    *,
    repo_root: Path = ROOT,
    validator_host_diagnostic: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    files = _read_artifact_files(artifact_dir)
    policy, repository_bytes = _validate_lock(repo_root)
    manifest = _strict_json_bytes(files["manifest.json"], label="manifest")
    result = _strict_json_bytes(files["demo.json"], label="demo result")
    fixture = _strict_json_bytes(
        repository_bytes[FIXTURE_LABEL_PATHS["fixture"]], label="walkthrough fixture"
    )
    gold = _strict_json_bytes(
        repository_bytes[FIXTURE_LABEL_PATHS["gold"]], label="walkthrough gold"
    )
    _require(
        isinstance(manifest, dict)
        and isinstance(result, dict)
        and isinstance(fixture, dict)
        and isinstance(gold, dict),
        "JSON roots must be objects",
    )
    _validate_manifest(manifest, policy)
    _validate_result(result, policy, fixture, gold)
    _validate_calls_ledger(files["calls.jsonl"], result)
    _require(
        result["source_snapshot_sha256"] == manifest["source_snapshot_sha256"],
        "result source graph drifted",
    )
    _require(
        result["claim_boundary"] == policy["claim_boundary"],
        "result claim boundary drifted",
    )
    return {
        "status": "VALID_CANONICAL_ARTIFACT",
        "artifact_dir": str(artifact_dir),
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "result_fingerprint_sha256": EXPECTED_RESULT_SHA256,
        "recorded_producer_runtime": manifest["runtime"],
        "validator_host_diagnostic": dict(validator_host_diagnostic or {}),
        "validator_host_used_as_gate": False,
        "walkthrough_contract_passed": False,
        "verification_boundary": (
            "canonical byte/source/ledger/public-grade consistency only; no "
            "cross-runtime autograd reproduction or provider attestation"
        ),
    }


def _copy_repository_subset(destination: Path) -> None:
    for relative in (POLICY_PATH, *EXPECTED_REPOSITORY_FILES):
        source = ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def _expect_failure(action: Any, label: str) -> None:
    try:
        action()
    except VerificationError:
        return
    raise AssertionError(f"tamper test unexpectedly passed: {label}")


def self_test() -> dict[str, Any]:
    checks: list[str] = []
    verify_artifact(DEFAULT_ARTIFACT_DIR)
    checks.append("canonical artifact verifies")
    foreign = {"python": "3.10.0", "machine": "x86_64", "system": "Linux"}
    foreign_result = verify_artifact(
        DEFAULT_ARTIFACT_DIR, validator_host_diagnostic=foreign
    )
    _require(
        foreign_result["validator_host_diagnostic"] == foreign
        and foreign_result["validator_host_used_as_gate"] is False,
        "foreign-host diagnostic affected verification",
    )
    checks.append("foreign validator-host diagnostic is non-gating")
    _expect_failure(
        lambda: _strict_json_bytes(b'{"x":1,"x":2}', label="duplicate probe"),
        "duplicate JSON key",
    )
    _expect_failure(
        lambda: _strict_json_bytes(b'{"x":NaN}', label="NaN probe"),
        "non-finite JSON",
    )
    checks.append("duplicate keys and non-finite JSON are rejected")
    with tempfile.TemporaryDirectory(prefix="ebrt-v052-portable-") as raw_temp:
        temp = Path(raw_temp)
        repo = temp / "repo"
        artifact = repo / "artifact"
        _copy_repository_subset(repo)
        shutil.copytree(DEFAULT_ARTIFACT_DIR, artifact)
        verify_artifact(artifact, repo_root=repo)

        changed = bytearray((artifact / "demo.json").read_bytes())
        changed[len(changed) // 2] ^= 1
        (artifact / "demo.json").write_bytes(changed)
        _expect_failure(
            lambda: verify_artifact(artifact, repo_root=repo), "artifact byte flip"
        )
        shutil.copyfile(DEFAULT_ARTIFACT_DIR / "demo.json", artifact / "demo.json")

        (artifact / "extra.json").write_text("{}\n", encoding="utf-8")
        _expect_failure(
            lambda: verify_artifact(artifact, repo_root=repo), "extra artifact"
        )
        (artifact / "extra.json").unlink()

        (artifact / "report.md").unlink()
        _expect_failure(
            lambda: verify_artifact(artifact, repo_root=repo), "missing artifact"
        )
        shutil.copyfile(DEFAULT_ARTIFACT_DIR / "report.md", artifact / "report.md")

        calls = artifact / "calls.jsonl"
        original_calls = calls.read_bytes()
        calls.unlink()
        calls.symlink_to(DEFAULT_ARTIFACT_DIR / "calls.jsonl")
        _expect_failure(
            lambda: verify_artifact(artifact, repo_root=repo), "symlinked artifact"
        )
        calls.unlink()
        calls.write_bytes(original_calls)

        manifest_path = artifact / "manifest.json"
        manifest = _strict_json_bytes(
            manifest_path.read_bytes(), label="manifest tamper source"
        )
        manifest["runtime"]["machine"] = "x86_64"
        manifest_path.write_bytes(
            json.dumps(manifest, indent=2, sort_keys=True).encode() + b"\n"
        )
        _expect_failure(
            lambda: verify_artifact(artifact, repo_root=repo),
            "coherently re-signed manifest",
        )
        shutil.copyfile(DEFAULT_ARTIFACT_DIR / "manifest.json", manifest_path)

        runner_path = repo / SOURCE_LABEL_PATHS["walkthrough_runner"]
        runner_path.write_bytes(runner_path.read_bytes() + b"\n")
        _expect_failure(
            lambda: verify_artifact(artifact, repo_root=repo), "source byte tamper"
        )
    checks.append("byte, file-set, symlink, re-sign, and source tampering are rejected")
    return {
        "status": "PASS",
        "checks": checks,
        "network_calls": 0,
        "verification_boundary": (
            "canonical integrity and public derivations only; no autograd replay or "
            "provider authenticity claim"
        ),
    }


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify_parser = subparsers.add_parser(
        "verify", help="verify the pinned canonical artifact"
    )
    verify_parser.add_argument(
        "--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR
    )
    subparsers.add_parser("self-test", help="run portable verifier tamper tests")
    args = parser.parse_args()
    try:
        if args.command == "verify":
            _print_json(verify_artifact(args.artifact_dir))
        else:
            _print_json(self_test())
    except VerificationError as error:
        parser.exit(1, f"verification failed: {error}\n")


if __name__ == "__main__":
    main()
