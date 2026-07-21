#!/usr/bin/env python3
"""Portable verifier for the immutable EBRT v0.6.2.1 live-r01 artifact.

This module intentionally imports only the Python standard library.  It can be
executed from an unrelated working directory with ``python3 -I -S``.  The
verification has two layers:

1. pin the exact seven-file live-r01 publication, its preregistered source
   lock, and its annotated authorization tag; and
2. independently rebuild the public closure, local scalar credit assignment,
   actuator, dynamic After payload, grades, result, calls, journal, report, and
   manifest.

No provider call or network access is performed.  The verifier does not claim
to reproduce Torch bit-for-bit; it rederives the same float64 recurrence with a
small forward-mode dual-number implementation and checks the published numeric
trace at tight tolerances before requiring every published JSON seal exactly.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import heapq
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parent
DEFAULT_ARTIFACT = ROOT / "artifacts" / "apply_revision_acceptance_v0_6_2_1_live_r01"
LOCK_PATH = ROOT / "policy_lock_apply_revision_acceptance_v0_6_2_1.json"
FIXTURE_PATH = ROOT / "fixtures" / "apply_revision_acceptance_v0_6_2_1.json"
GOLD_PATH = ROOT / "fixtures" / "apply_revision_acceptance_gold_v0_6_2_1.json"
AUTHORIZATION_TAG = "v0.6.2.1-apply-revision-live-r01-authorized"

ARTIFACT_FILES = (
    "result.json",
    "calls.jsonl",
    "attempt_journal.jsonl",
    "provider_inputs.json",
    "apply_revision_trace.json",
    "report.md",
    "manifest.json",
)
PHASES = ("before_event", "after_event")

EXPECTED_LOCK_FINGERPRINT = "31b27497b6ff05369e9f33110f6faa1c3765a2e4caae710a2aa7d7661c4f111e"
EXPECTED_RESULT_FINGERPRINT = "1ba3cfe9565124d92fa8db8222c4d44bc62a81e1da7c6fad07e24e9a8e7ad245"
EXPECTED_MANIFEST_RECEIPT = {
    "bytes": 2401,
    "sha256": "532dd593ef4464d87dd02fd2eeaa712855f47e5de799c669889c0302ee2fe3a4",
}

RESULT_SCHEMA = "ebrt-apply-revision-result-v0.6.2.1-r01"
CALL_SCHEMA = "ebrt-apply-revision-call-v0.6.2.1-r01"
JOURNAL_SCHEMA = "ebrt-apply-revision-journal-v0.6.2.1-r01"
PROVIDER_INPUTS_SCHEMA = "ebrt-apply-revision-provider-inputs-v0.6.2.1-r01"
TRACE_SCHEMA = "ebrt-apply-revision-trace-v0.6.2.1-r01"
MANIFEST_SCHEMA = "ebrt-apply-revision-manifest-v0.6.2.1-r01"
INPUT_SCHEMA = "ebrt-apply-revision-provider-input-v0.6.2.1"
OUTPUT_SCHEMA = "ebrt-apply-revision-provider-output-v0.6.2.1"
COMPILED_SCHEMA = "ebrt-apply-revision-compiled-closure-v0.6.2.1"
CONTROL_SCHEMA = "ebrt-apply-revision-public-control-map-v0.6.2.1"
ACTUATOR_SCHEMA = "ebrt-apply-revision-compiled-actuator-v0.6.2.1"

MODEL = "gpt-5.6-sol"
REASONING_EFFORT = "low"
MAX_OUTPUT_TOKENS = 1024
TIMEOUT_SECONDS = 60.0
STATE_DECAY = 0.82
STEP_SIZE = 0.05
CONTROL_REGULARIZATION = 0.01
FINITE_DIFFERENCE_EPSILON = 1.0e-6
FINITE_DIFFERENCE_TOLERANCE = 1.0e-8
MAX_CONTROL_L2 = 0.25

FORBIDDEN_PROVIDER_KEYS = frozenset(
    {
        "accepted_closure",
        "accepted_closure_id",
        "correct_answer",
        "expected_answer",
        "expected_closure",
        "expected_support",
        "gold",
        "grade",
        "gradient",
        "loss",
        "quality_label",
        "required_support",
        "target_answer",
        "target_closure",
        "target_closure_id",
        "treatment",
        "treatment_id",
    }
)


class VerificationError(RuntimeError):
    """Fail-closed public verifier error."""

    def __init__(self, reason_code: str, detail: str = "") -> None:
        self.reason_code = reason_code
        super().__init__(reason_code if not detail else f"{reason_code}: {detail}")


def require(condition: bool, reason: str, detail: str = "") -> None:
    if not condition:
        raise VerificationError(reason, detail)


def canonical_bytes(value: Any, *, newline: bool = False) -> bytes:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return raw + (b"\n" if newline else b"")


def pretty_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def fingerprint(value: Any) -> str:
    return sha256(canonical_bytes(value))


def without_fingerprint(value: Mapping[str, Any]) -> dict[str, Any]:
    output = dict(value)
    output.pop("fingerprint_sha256", None)
    return output


def seal(value: Mapping[str, Any]) -> dict[str, Any]:
    output = without_fingerprint(value)
    output["fingerprint_sha256"] = fingerprint(output)
    return output


def validate_seal(value: Mapping[str, Any], label: str) -> None:
    require(
        value.get("fingerprint_sha256") == fingerprint(without_fingerprint(value)),
        "FINGERPRINT_MISMATCH",
        label,
    )


def reject_constant(value: str) -> Any:
    raise VerificationError("NONFINITE_JSON", value)


def reject_duplicates(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in output, "DUPLICATE_JSON_KEY", key)
        output[key] = value
    return output


def reject_nonfinite(value: Any, label: str) -> None:
    if isinstance(value, float):
        require(math.isfinite(value), "NONFINITE_JSON", label)
    elif isinstance(value, Mapping):
        for child in value.values():
            reject_nonfinite(child, label)
    elif isinstance(value, list):
        for child in value:
            reject_nonfinite(child, label)


def strict_json(raw: bytes, label: str) -> Any:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_constant,
        )
    except VerificationError:
        raise
    except Exception as error:
        raise VerificationError("INVALID_JSON", label) from error
    reject_nonfinite(value, label)
    return value


def strict_object(raw: bytes, label: str) -> dict[str, Any]:
    value = strict_json(raw, label)
    require(isinstance(value, dict), "JSON_ROOT_NOT_OBJECT", label)
    return value


def strict_jsonl(raw: bytes, label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(raw.splitlines(), start=1):
        value = strict_json(line, f"{label}:{index}")
        require(isinstance(value, dict), "JSONL_ROW_NOT_OBJECT", label)
        rows.append(value)
    return rows


def exact_keys(value: Any, expected: set[str], label: str) -> Mapping[str, Any]:
    require(isinstance(value, Mapping), "OBJECT_REQUIRED", label)
    require(set(value) == expected, "OBJECT_SCHEMA_DRIFT", label)
    return value


def recursive_keys(value: Any) -> set[str]:
    if isinstance(value, Mapping):
        output = {str(key) for key in value}
        for child in value.values():
            output.update(recursive_keys(child))
        return output
    if isinstance(value, list):
        output: set[str] = set()
        for child in value:
            output.update(recursive_keys(child))
        return output
    return set()


def unique_strings(value: Any, label: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    require(isinstance(value, list), "STRING_LIST_REQUIRED", label)
    output = tuple(value)
    require(allow_empty or bool(output), "STRING_LIST_EMPTY", label)
    require(
        all(isinstance(item, str) and item for item in output),
        "STRING_LIST_ITEM_INVALID",
        label,
    )
    require(len(output) == len(set(output)), "STRING_LIST_DUPLICATE", label)
    return output


def run_git(*args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=check,
            capture_output=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise VerificationError("GIT_BOUNDARY_UNAVAILABLE", " ".join(args)) from error


def read_bundle(path: Path) -> dict[str, bytes]:
    require(path.is_dir() and not path.is_symlink(), "ARTIFACT_DIRECTORY_UNAVAILABLE")
    entries = list(path.iterdir())
    require(
        len(entries) == len(ARTIFACT_FILES)
        and {entry.name for entry in entries} == set(ARTIFACT_FILES)
        and all(entry.is_file() and not entry.is_symlink() for entry in entries),
        "ARTIFACT_DIRECTORY_NONCANONICAL",
    )
    return {name: (path / name).read_bytes() for name in ARTIFACT_FILES}


def validate_lock_and_authorization(lock: Mapping[str, Any], *, verify_git: bool) -> dict[str, Any]:
    validate_seal(lock, "policy_lock")
    require(lock["fingerprint_sha256"] == EXPECTED_LOCK_FINGERPRINT, "POLICY_LOCK_ID_DRIFT")
    require(
        lock["schema_version"] == "ebrt-apply-revision-policy-lock-v0.6.2.1-r01"
        and lock["status"] == "PREREGISTERED_DYNAMIC_EXACT_TWO_CALL_PRODUCT_ACCEPTANCE",
        "POLICY_LOCK_CONTRACT_DRIFT",
    )
    require(lock["artifact"]["files"] == list(ARTIFACT_FILES), "POLICY_LOCK_ARTIFACT_SET_DRIFT")
    require(
        lock["artifact"]["default_directory"]
        == "artifacts/apply_revision_acceptance_v0_6_2_1_live_r01",
        "POLICY_LOCK_ARTIFACT_PATH_DRIFT",
    )
    require(
        lock["execution"]
        == {
            "after_payload_materialized_only_after_before_terminal": True,
            "authorization_tag": AUTHORIZATION_TAG,
            "effect_attribution_status": "NOT_ASSESSED",
            "exact_provider_attempts": 2,
            "no_backfill": True,
            "no_resume": True,
            "no_retry": True,
            "no_third_call": True,
            "one_attempt_per_phase": True,
            "phase_order": list(PHASES),
            "semantic_gold_loaded_only_after_two_structurally_valid_terminals": True,
            "structurally_valid_before_always_continues": True,
        },
        "POLICY_LOCK_EXECUTION_DRIFT",
    )
    runtime = lock["runtime"]
    require(
        runtime["provider"] == "openai_responses"
        and runtime["model"] == MODEL
        and runtime["reasoning_effort"] == REASONING_EFFORT
        and runtime["max_output_tokens"] == MAX_OUTPUT_TOKENS
        and runtime["timeout_seconds"] == int(TIMEOUT_SECONDS)
        and runtime["sdk_retries"] == 0
        and runtime["store"] is False
        and runtime["previous_response_id"] is False
        and runtime["truncation"] == "disabled",
        "POLICY_LOCK_RUNTIME_DRIFT",
    )
    sources = lock["sources"]
    require(isinstance(sources, Mapping) and sources, "POLICY_LOCK_SOURCES_INVALID")
    for label, receipt in sources.items():
        exact_keys(receipt, {"path", "bytes", "sha256"}, f"source.{label}")
        relative = Path(receipt["path"])
        require(not relative.is_absolute() and ".." not in relative.parts, "SOURCE_PATH_INVALID", label)
        source = ROOT / relative
        require(source.is_file() and not source.is_symlink(), "LOCKED_SOURCE_UNAVAILABLE", label)
        raw = source.read_bytes()
        require(
            receipt == {"path": receipt["path"], "bytes": len(raw), "sha256": sha256(raw)},
            "LOCKED_SOURCE_RECEIPT_DRIFT",
            label,
        )
    require(
        lock["fixture_fingerprint_sha256"] == "a10f903ee492b0741de3f2e0be8742311ae80bc09eb6b097a3b2c2de6ec1e484"
        and lock["semantic_gold_bytes_sha256"] == sources["post_call_semantic_gold"]["sha256"],
        "POLICY_LOCK_SEMANTIC_BINDING_DRIFT",
    )
    if not verify_git:
        return {"status": "SOURCE_LOCK_VALID_GIT_NOT_ASSESSED"}

    root = Path(run_git("rev-parse", "--show-toplevel").stdout.decode().strip()).resolve()
    require(root == ROOT, "GIT_ROOT_DRIFT")
    tag_ref = f"refs/tags/{AUTHORIZATION_TAG}"
    tag_object = run_git("rev-parse", "--verify", tag_ref).stdout.decode().strip()
    require(run_git("cat-file", "-t", tag_object).stdout.strip() == b"tag", "AUTHORIZATION_TAG_NOT_ANNOTATED")
    tag_commit = run_git("rev-parse", f"{tag_ref}^{{commit}}").stdout.decode().strip()
    message = run_git("for-each-ref", "--format=%(contents)", tag_ref).stdout.decode()
    require(EXPECTED_LOCK_FINGERPRINT in message, "AUTHORIZATION_TAG_LOCK_BINDING_DRIFT")
    for label, receipt in sources.items():
        raw = run_git("show", f"{tag_commit}:{receipt['path']}").stdout
        require(
            len(raw) == receipt["bytes"] and sha256(raw) == receipt["sha256"],
            "AUTHORIZED_SOURCE_RECEIPT_DRIFT",
            label,
        )
    lock_raw = run_git("show", f"{tag_commit}:{LOCK_PATH.relative_to(ROOT)}").stdout
    require(lock_raw == LOCK_PATH.read_bytes(), "AUTHORIZED_POLICY_LOCK_BYTES_DRIFT")
    run_git("merge-base", "--is-ancestor", tag_commit, "HEAD")
    return {
        "status": "AUTHORIZED_ANNOTATED_TAG",
        "tag_name": AUTHORIZATION_TAG,
        "tag_object": tag_object,
        "authorized_commit": tag_commit,
        "provenance_scope": "OPERATOR_ATTESTED_NOT_CRYPTOGRAPHICALLY_AUTHENTICATED",
    }


def load_locked_inputs(lock: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    fixture_raw = FIXTURE_PATH.read_bytes()
    gold_raw = GOLD_PATH.read_bytes()
    require(
        {"path": str(FIXTURE_PATH.relative_to(ROOT)), "bytes": len(fixture_raw), "sha256": sha256(fixture_raw)}
        == lock["sources"]["public_fixture"],
        "FIXTURE_SOURCE_RECEIPT_DRIFT",
    )
    require(
        {"path": str(GOLD_PATH.relative_to(ROOT)), "bytes": len(gold_raw), "sha256": sha256(gold_raw)}
        == lock["sources"]["post_call_semantic_gold"],
        "GOLD_SOURCE_RECEIPT_DRIFT",
    )
    fixture = strict_object(fixture_raw, "fixture")
    gold = strict_object(gold_raw, "gold")
    validate_seal(fixture, "fixture")
    validate_seal(gold, "gold")
    require(fixture["fingerprint_sha256"] == lock["fixture_fingerprint_sha256"], "FIXTURE_LOCK_BINDING_DRIFT")
    require(gold["source_fixture"]["fingerprint_sha256"] == fixture["fingerprint_sha256"], "GOLD_FIXTURE_BINDING_DRIFT")
    require(
        fixture["schema_version"] == "ebrt-apply-revision-acceptance-fixture-v0.6.2.1"
        and fixture["status"] == "LOCKED_PUBLIC_PRODUCT_ACCEPTANCE_INPUT",
        "FIXTURE_CONTRACT_DRIFT",
    )
    require(
        gold["schema_version"] == "ebrt-apply-revision-acceptance-gold-v0.6.2.1"
        and gold["status"] == "LOCKED_POST_TWO_CALL_GRADING_ONLY",
        "GOLD_CONTRACT_DRIFT",
    )
    execution = fixture["execution_contract"]
    require(execution["phase_order"] == list(PHASES), "FIXTURE_PHASE_ORDER_DRIFT")
    require(execution["evidence_horizons"]["before_event"] == ["R1", "R2", "R3", "R4", "R5"], "FIXTURE_BEFORE_HORIZON_DRIFT")
    require(execution["evidence_horizons"]["after_event"] == ["R1", "R2", "R3", "R4", "R5", "R6"], "FIXTURE_AFTER_HORIZON_DRIFT")
    require(
        fixture["case"]["answer_choices"] == ["POLISH", "PROVE"]
        and fixture["public_revision_contract"]["correction_evidence_id"] == "R6"
        and fixture["public_revision_contract"]["invalidated_evidence_ids"] == ["R3"]
        and fixture["public_revision_contract"]["stable_evidence_id"] == "R5",
        "FIXTURE_REVISION_CONTRACT_DRIFT",
    )
    controller = fixture["controller_contract"]
    for key, expected in {
        "state_decay": STATE_DECAY,
        "step_size": STEP_SIZE,
        "control_regularization": CONTROL_REGULARIZATION,
        "finite_difference_epsilon": FINITE_DIFFERENCE_EPSILON,
        "finite_difference_tolerance": FINITE_DIFFERENCE_TOLERANCE,
        "max_control_l2": MAX_CONTROL_L2,
    }.items():
        require(float(controller[key]) == expected, "CONTROLLER_PARAMETER_DRIFT", key)
    require(gold["acceptance_contract"]["effect_attribution_status"] == "NOT_ASSESSED", "GOLD_EFFECT_STATUS_DRIFT")
    return fixture, gold


def phase_evidence(fixture: Mapping[str, Any], phase: str) -> list[dict[str, Any]]:
    rows = list(fixture["case"]["initial_evidence"]) + [fixture["case"]["late_evidence"]]
    by_id = {row["evidence_id"]: row for row in rows}
    return [copy.deepcopy(by_id[item]) for item in fixture["execution_contract"]["evidence_horizons"][phase]]


def candidate_rows(fixture: Mapping[str, Any], phase: str) -> list[dict[str, Any]]:
    return [
        {"closure_id": row["closure_id"], "graph": copy.deepcopy(row["graph"])}
        for row in fixture["closure_catalogs"][phase]
    ]


def validate_provider_output(fixture: Mapping[str, Any], phase: str, output: Mapping[str, Any]) -> None:
    exact_keys(output, {"schema_version", "checkpoint_id", "current_answer", "selected_closure_id", "target_values"}, f"output.{phase}")
    require(output["schema_version"] == OUTPUT_SCHEMA, "OUTPUT_SCHEMA_INVALID", phase)
    require(output["checkpoint_id"] == fixture["execution_contract"]["checkpoint_ids"][phase], "OUTPUT_CHECKPOINT_MISMATCH", phase)
    require(output["current_answer"] in fixture["case"]["answer_choices"], "OUTPUT_ANSWER_INVALID", phase)
    catalogs = {row["closure_id"]: row for row in fixture["closure_catalogs"][phase]}
    require(output["selected_closure_id"] in catalogs, "OUTPUT_CLOSURE_UNKNOWN", phase)
    require(isinstance(output["target_values"], list) and len(output["target_values"]) == 3, "OUTPUT_TARGET_COUNT_INVALID", phase)
    seen: set[str] = set()
    slots = {row["slot_id"]: row for row in fixture["case"]["decision_slots"]}
    for row in output["target_values"]:
        exact_keys(row, {"target_id", "target_type", "slot", "value"}, f"output.{phase}.target")
        require(row["target_id"] not in seen, "OUTPUT_TARGET_DUPLICATE", phase)
        seen.add(row["target_id"])
        expected_type = "constraint" if row["slot"] == "video_constraint" else "fact"
        require(
            row["slot"] in slots
            and row["target_type"] == expected_type
            and row["target_id"] == f"{expected_type}:{row['slot']}"
            and row["value"] in slots[row["slot"]]["allowed_values"],
            "OUTPUT_TARGET_INVALID",
            phase,
        )


def compile_output(fixture: Mapping[str, Any], phase: str, output: Mapping[str, Any]) -> dict[str, Any]:
    validate_provider_output(fixture, phase, output)
    candidates = {row["closure_id"]: row for row in fixture["closure_catalogs"][phase]}
    graph = candidates[output["selected_closure_id"]]["graph"]
    supports = {row["support_id"]: row for row in graph["support_nodes"]}
    targets = {row["target_id"]: row for row in graph["targets"]}
    values = {row["target_id"]: row for row in output["target_values"]}
    require(set(values) == set(targets), "OUTPUT_TARGET_SET_MISMATCH", phase)
    indegree = {target_id: 0 for target_id in targets}
    adjacency = {target_id: [] for target_id in targets}
    for target_id, row in targets.items():
        for upstream in row["depends_on_target_ids"]:
            require(upstream in targets, "OUTPUT_DEPENDENCY_UNKNOWN", phase)
            indegree[target_id] += 1
            adjacency[upstream].append(target_id)
    queue = [target_id for target_id, degree in indegree.items() if degree == 0]
    heapq.heapify(queue)
    order: list[str] = []
    while queue:
        target_id = heapq.heappop(queue)
        order.append(target_id)
        for downstream in sorted(adjacency[target_id]):
            indegree[downstream] -= 1
            if indegree[downstream] == 0:
                heapq.heappush(queue, downstream)
    require(len(order) == len(targets), "OUTPUT_CLOSURE_CYCLE", phase)
    direct: dict[str, set[str]] = {}
    inherited: dict[str, set[str]] = {}
    total: dict[str, set[str]] = {}
    for target_id in order:
        row = targets[target_id]
        direct_set = {
            evidence
            for support_id in row["direct_support_ids"]
            for evidence in supports[support_id]["evidence_ids"]
        }
        ancestor = {
            evidence
            for upstream in row["depends_on_target_ids"]
            for evidence in total[upstream]
        }
        direct[target_id] = direct_set
        inherited[target_id] = ancestor - direct_set
        total[target_id] = direct_set | ancestor
    edges = sorted(
        copy.deepcopy(graph["invalidation_edges"]),
        key=lambda row: (row["source_evidence_id"], row["target_evidence_id"]),
    )
    invalidated = {row["target_evidence_id"] for row in edges}
    active = {item for row in total.values() for item in row}
    require(not active & invalidated, "OUTPUT_INVALIDATED_SUPPORT_ACTIVE", phase)
    horizon = fixture["execution_contract"]["evidence_horizons"][phase]
    ordinal = {item: index for index, item in enumerate(horizon)}
    compiled_targets = []
    for target_id in sorted(targets):
        value = values[target_id]
        compiled_targets.append(
            {
                "target_id": target_id,
                "target_type": value["target_type"],
                "slot": value["slot"],
                "value": value["value"],
                "direct_active_evidence_ids": sorted(direct[target_id], key=ordinal.__getitem__),
                "inherited_active_evidence_ids": sorted(inherited[target_id], key=ordinal.__getitem__),
                "all_active_evidence_ids": sorted(total[target_id], key=ordinal.__getitem__),
            }
        )
    normalized = copy.deepcopy(dict(output))
    normalized["target_values"] = sorted(normalized["target_values"], key=lambda row: row["target_id"])
    return seal(
        {
            "schema_version": COMPILED_SCHEMA,
            "phase_id": phase,
            "checkpoint_id": output["checkpoint_id"],
            "current_answer": output["current_answer"],
            "selected_closure_id": output["selected_closure_id"],
            "source_horizon_evidence_ids": list(horizon),
            "active_support_evidence_ids": sorted(active, key=ordinal.__getitem__),
            "invalidated_evidence_ids": sorted(invalidated, key=ordinal.__getitem__),
            "invalidation_edges": edges,
            "targets": compiled_targets,
            "normalized_output": normalized,
            "normalized_output_fingerprint_sha256": fingerprint(normalized),
        }
    )


class Dual:
    """Minimal float64 forward-mode scalar used to rederive public credit."""

    __slots__ = ("value", "gradient")

    def __init__(self, value: float, gradient: Sequence[float]) -> None:
        self.value = float(value)
        self.gradient = tuple(float(item) for item in gradient)

    def __add__(self, other: Dual | float) -> Dual:
        rhs = other if isinstance(other, Dual) else Dual(float(other), (0.0,) * len(self.gradient))
        return Dual(self.value + rhs.value, [a + b for a, b in zip(self.gradient, rhs.gradient, strict=True)])

    __radd__ = __add__

    def __mul__(self, other: Dual | float) -> Dual:
        rhs = other if isinstance(other, Dual) else Dual(float(other), (0.0,) * len(self.gradient))
        return Dual(
            self.value * rhs.value,
            [a * rhs.value + b * self.value for a, b in zip(self.gradient, rhs.gradient, strict=True)],
        )

    __rmul__ = __mul__

    def __sub__(self, other: Dual | float) -> Dual:
        return self + (-1.0 * other)

    def square(self) -> Dual:
        return self * self


def dual_tanh(value: Dual) -> Dual:
    result = math.tanh(value.value)
    return Dual(result, [(1.0 - result * result) * item for item in value.gradient])


def state_coordinate(value: str, choices: Sequence[str]) -> float:
    require(value in choices and choices, "STATE_COORDINATE_INVALID")
    return 0.0 if len(choices) == 1 else -1.0 + 2.0 * choices.index(value) / (len(choices) - 1)


def actual_before_state(fixture: Mapping[str, Any], compiled: Mapping[str, Any]) -> tuple[float, dict[str, Any]]:
    slots = {row["slot_id"]: row for row in fixture["case"]["decision_slots"]}
    components = [
        {
            "axis": "current_answer",
            "value": compiled["current_answer"],
            "coordinate": state_coordinate(compiled["current_answer"], fixture["case"]["answer_choices"]),
        }
    ]
    for row in compiled["targets"]:
        if row["target_type"] == "fact":
            components.append(
                {
                    "axis": row["target_id"],
                    "value": row["value"],
                    "coordinate": state_coordinate(row["value"], slots[row["slot"]]["allowed_values"]),
                }
            )
    scalar = math.fsum(float(row["coordinate"]) for row in components) / len(components)
    return scalar, seal(
        {
            "schema_version": "ebrt-apply-revision-actual-before-state-v0.6.2.1",
            "source_compiled_fingerprint_sha256": compiled["fingerprint_sha256"],
            "source_selected_closure_id": compiled["selected_closure_id"],
            "active_support_evidence_ids": list(compiled["active_support_evidence_ids"]),
            "components": components,
            "initial_scalar": scalar,
        }
    )


def historical_credit_basis(lock: Mapping[str, Any]) -> tuple[dict[str, float], dict[str, Any]]:
    lane_path = ROOT / lock["sources"]["temporal_lane"]["path"]
    lane = strict_object(lane_path.read_bytes(), "temporal_lane")
    validate_seal(lane, "temporal_lane")
    exact = lane["control_maps"]["C"]
    absolute = {f"R{index}": 0.0 for index in range(1, 7)}
    signed = {f"R{index}": 0.0 for index in range(1, 7)}
    for row in exact["controls"]:
        parts = row["site_id"].split(":")
        require(len(parts) >= 6 and parts[:2] == ["q", "correction_late"], "V054_SITE_ID_INVALID")
        evidence_id = parts[3]
        value = float(row["normalized_u"])
        absolute[evidence_id] += abs(value)
        signed[evidence_id] += value
    maximum = max(absolute.values())
    effects = {key: absolute[key] / maximum for key in absolute}
    receipt = seal(
        {
            "schema_version": "ebrt-apply-revision-v054-credit-basis-v0.6.2.1",
            "source_lane_fingerprint_sha256": lane["fingerprint_sha256"],
            "source_program_fingerprint_sha256": lane["program_fingerprint_sha256"],
            "source_adjoint_fingerprint_sha256": lane["adjoint_audit"]["fingerprint_sha256"],
            "source_exact_control_fingerprint_sha256": exact["fingerprint_sha256"],
            "source_backward_calls": lane["adjoint_audit"]["backward_calls"],
            "absolute_credit_by_evidence_id": dict(sorted(absolute.items())),
            "signed_credit_by_evidence_id": dict(sorted(signed.items())),
            "normalized_effect_by_evidence_id": effects,
        }
    )
    return effects, receipt


def scalar_loss(controls: Sequence[float], effects: Sequence[float], initial: float, target: float) -> tuple[float, list[float]]:
    state = initial
    states = []
    for control, effect in zip(controls, effects, strict=True):
        state = math.tanh(STATE_DECAY * state + control * effect)
        states.append(state)
    loss = (state - target) ** 2 + CONTROL_REGULARIZATION * math.fsum(item * item for item in controls)
    return loss, states


def derive_controller_numeric(
    fixture: Mapping[str, Any],
    compiled_before: Mapping[str, Any],
    lock: Mapping[str, Any],
) -> dict[str, Any]:
    initial, state = actual_before_state(fixture, compiled_before)
    effects_by_id, basis = historical_credit_basis(lock)
    evidence_ids = fixture["execution_contract"]["evidence_horizons"]["after_event"]
    effects = [effects_by_id[item] for item in evidence_ids]
    dimension = len(evidence_ids)
    controls = [Dual(0.0, [1.0 if row == column else 0.0 for column in range(dimension)]) for row in range(dimension)]
    dual_state = Dual(initial, [0.0] * dimension)
    dual_states = []
    for control, effect in zip(controls, effects, strict=True):
        dual_state = dual_tanh(STATE_DECAY * dual_state + control * effect)
        dual_states.append(dual_state.value)
    target = float(fixture["controller_contract"]["terminal_decision_target"])
    loss = (dual_state - target).square()
    for control in controls:
        loss = loss + CONTROL_REGULARIZATION * control.square()
    gradient = list(loss.gradient)
    displacement = [-STEP_SIZE * item for item in gradient]
    loss_after, states_after = scalar_loss(displacement, effects, initial, target)
    epsilon = FINITE_DIFFERENCE_EPSILON
    finite_difference = []
    for index in range(dimension):
        positive = [0.0] * dimension
        negative = [0.0] * dimension
        positive[index] = epsilon
        negative[index] = -epsilon
        plus, _ = scalar_loss(positive, effects, initial, target)
        minus, _ = scalar_loss(negative, effects, initial, target)
        finite_difference.append((plus - minus) / (2.0 * epsilon))
    return {
        "actual_before_state": state,
        "source_credit_basis": basis,
        "evidence_ids": evidence_ids,
        "effects": effects,
        "gradient": gradient,
        "displacement": displacement,
        "objective_before": loss.value,
        "objective_after": loss_after,
        "state_trace_before": dual_states,
        "state_trace_after": states_after,
        "control_l2": math.sqrt(math.fsum(item * item for item in displacement)),
        "finite_difference": finite_difference,
        "maximum_finite_difference_error": max(abs(a - b) for a, b in zip(gradient, finite_difference, strict=True)),
    }


def close_float(observed: Any, expected: float, label: str, tolerance: float = 5.0e-13) -> None:
    require(
        isinstance(observed, (int, float))
        and not isinstance(observed, bool)
        and math.isfinite(float(observed))
        and abs(float(observed) - expected) <= tolerance,
        "CONTROL_NUMERIC_REDERIVATION_DRIFT",
        label,
    )


def validate_control_map(
    fixture: Mapping[str, Any],
    compiled_before: Mapping[str, Any],
    control: Mapping[str, Any],
    lock: Mapping[str, Any],
) -> None:
    validate_seal(control, "control_map")
    require(control["schema_version"] == CONTROL_SCHEMA and control["status"] == "PASS", "CONTROL_SCHEMA_DRIFT")
    derived = derive_controller_numeric(fixture, compiled_before, lock)
    require(canonical_bytes(control["actual_before_state"]) == canonical_bytes(derived["actual_before_state"]), "CONTROL_BEFORE_STATE_DRIFT")
    require(canonical_bytes(control["source_credit_basis"]) == canonical_bytes(derived["source_credit_basis"]), "CONTROL_CREDIT_BASIS_DRIFT")
    require(control["dtype"] == "torch.float64" and control["backward_calls"] == 1, "CONTROL_RUNTIME_DRIFT")
    close_float(control["objective_before"], derived["objective_before"], "objective_before")
    close_float(control["objective_after"], derived["objective_after"], "objective_after")
    close_float(control["control_l2"], derived["control_l2"], "control_l2")
    close_float(control["maximum_finite_difference_error"], derived["maximum_finite_difference_error"], "finite_difference_error", 2.0e-10)
    for index, row in enumerate(control["credit_rows"]):
        require(row["evidence_id"] == derived["evidence_ids"][index], "CONTROL_EVIDENCE_ORDER_DRIFT")
        close_float(row["source_effect"], derived["effects"][index], f"effect.{index}")
        close_float(row["gradient"], derived["gradient"][index], f"gradient.{index}")
        close_float(row["signed_public_credit"], derived["displacement"][index], f"credit.{index}")
        close_float(row["finite_difference_gradient"], derived["finite_difference"][index], f"finite_difference.{index}", 2.0e-10)
        require(row["active_before"] is (row["evidence_id"] in compiled_before["active_support_evidence_ids"]), "CONTROL_ACTIVE_FLAG_DRIFT")
    for label in ("state_trace_before", "state_trace_after"):
        require(len(control[label]) == len(derived[label]), "CONTROL_STATE_TRACE_LENGTH_DRIFT", label)
        for index, expected in enumerate(derived[label]):
            close_float(control[label][index], expected, f"{label}.{index}")
    checks = control["checks"]
    require(all(value is True for value in checks.values()), "CONTROL_CHECK_NOT_PASS")
    require(
        control["gradient_boundary"]
        == {
            "starts_at": "actual normalized public Before state plus public temporal credit basis",
            "ends_at": "public control map",
            "crosses_json": False,
            "crosses_provider": False,
            "hosted_model_differentiated": False,
            "actual_provider_output_participated_in_surrogate": True,
            "after_provider_output_participated_in_surrogate": False,
        },
        "CONTROL_GRADIENT_BOUNDARY_DRIFT",
    )


def compile_actuator(fixture: Mapping[str, Any], compiled: Mapping[str, Any], control: Mapping[str, Any]) -> dict[str, Any]:
    revision = fixture["public_revision_contract"]
    invalidated = set(revision["invalidated_evidence_ids"])
    stable = revision["stable_evidence_id"]
    eligible = [
        row
        for row in control["credit_rows"]
        if row["evidence_id"] not in invalidated
        and row["evidence_id"] != stable
        and abs(float(row["signed_public_credit"])) > 0.0
    ]
    eligible.sort(key=lambda row: (-abs(float(row["signed_public_credit"])), row["evidence_id"]))
    count = int(fixture["controller_contract"]["compilation_policy"]["reinspection_count"])
    active = set(compiled["active_support_evidence_ids"])
    actuator = seal(
        {
            "schema_version": ACTUATOR_SCHEMA,
            "source_before_compiled_fingerprint_sha256": compiled["fingerprint_sha256"],
            "source_control_map_fingerprint_sha256": control["fingerprint_sha256"],
            "event_id": revision["event_id"],
            "correction_evidence_id": revision["correction_evidence_id"],
            "reinspect_evidence_ids": [row["evidence_id"] for row in eligible[:count]],
            "suppress_evidence_ids": sorted(invalidated & active),
            "preserve_evidence_ids": [stable] if stable in active else [],
            "gradient_stops_here": True,
        }
    )
    require(
        actuator["reinspect_evidence_ids"] == ["R6", "R4", "R2"]
        and actuator["suppress_evidence_ids"] == ["R3"]
        and actuator["preserve_evidence_ids"] == ["R5"],
        "ACTUATOR_OPERATION_DRIFT",
    )
    return actuator


def normalized_prior(compiled: Mapping[str, Any]) -> dict[str, Any]:
    return seal(
        {
            "schema_version": "ebrt-apply-revision-prior-state-v0.6.2.1",
            "checkpoint_id": compiled["checkpoint_id"],
            "current_answer": compiled["current_answer"],
            "selected_closure_id": compiled["selected_closure_id"],
            "target_values": [
                {key: row[key] for key in ("target_id", "target_type", "slot", "value")}
                for row in compiled["targets"]
            ],
            "compiled_closure_fingerprint_sha256": compiled["fingerprint_sha256"],
        }
    )


def build_payload(
    fixture: Mapping[str, Any],
    phase: str,
    *,
    compiled_before: Mapping[str, Any] | None = None,
    actuator: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    before = phase == "before_event"
    prior = None if before else normalized_prior(compiled_before or {})
    operation = None
    if not before:
        require(actuator is not None, "ACTUATOR_REQUIRED")
        revision = fixture["public_revision_contract"]
        operation = {
            "schema_version": "ebrt-apply-revision-operation-v0.6.2.1",
            "operation": "APPLY_REVISION",
            "source_prior_state_fingerprint_sha256": prior["fingerprint_sha256"],
            "source_control_map_fingerprint_sha256": actuator["source_control_map_fingerprint_sha256"],
            "source_actuator_fingerprint_sha256": actuator["fingerprint_sha256"],
            "event": {
                "event_id": actuator["event_id"],
                "correction_evidence_id": actuator["correction_evidence_id"],
                "invalidated_evidence_ids": list(revision["invalidated_evidence_ids"]),
            },
            "reinspect_evidence_ids": list(actuator["reinspect_evidence_ids"]),
            "suppress_evidence_ids": list(actuator["suppress_evidence_ids"]),
            "preserve_evidence_ids": list(actuator["preserve_evidence_ids"]),
            "semantic_authority": "ordered raw evidence only",
            "gradient_boundary": "gradient stopped before this JSON operation and hosted generation",
        }
    case = fixture["case"]
    return {
        "schema_version": INPUT_SCHEMA,
        "case_id": case["case_id"],
        "checkpoint_id": fixture["execution_contract"]["checkpoint_ids"][phase],
        "question": case["question"],
        "answer_choices": copy.deepcopy(case["answer_choices"]),
        "decision_slots": copy.deepcopy(case["decision_slots"]),
        "all_raw_evidence": phase_evidence(fixture, phase),
        "allowed_evidence_ids": list(fixture["execution_contract"]["evidence_horizons"][phase]),
        "candidate_closures": candidate_rows(fixture, phase),
        "prior_public_state": prior,
        "apply_revision": operation,
    }


def validate_payload(fixture: Mapping[str, Any], phase: str, payload: Mapping[str, Any]) -> None:
    require(set(payload) == set(fixture["provider_contract"]["input_root_allowlist"]), "PROVIDER_PAYLOAD_SCHEMA_DRIFT", phase)
    require(not (recursive_keys(payload) & FORBIDDEN_PROVIDER_KEYS), "PROVIDER_PAYLOAD_FORBIDDEN_KEY", phase)
    require(payload["allowed_evidence_ids"] == fixture["execution_contract"]["evidence_horizons"][phase], "PROVIDER_PAYLOAD_HORIZON_DRIFT", phase)
    require(canonical_bytes(payload["all_raw_evidence"]) == canonical_bytes(phase_evidence(fixture, phase)), "PROVIDER_PAYLOAD_EVIDENCE_DRIFT", phase)
    require(canonical_bytes(payload["candidate_closures"]) == canonical_bytes(candidate_rows(fixture, phase)), "PROVIDER_PAYLOAD_CATALOG_DRIFT", phase)
    if phase == "before_event":
        require(payload["prior_public_state"] is None and payload["apply_revision"] is None, "BEFORE_PAYLOAD_LEAK")
    else:
        validate_seal(payload["prior_public_state"], "prior_public_state")
        require(payload["apply_revision"]["operation"] == "APPLY_REVISION", "AFTER_OPERATION_INVALID")
        require(payload["apply_revision"]["semantic_authority"] == "ordered raw evidence only", "AFTER_AUTHORITY_DRIFT")


def expected_protocol_fingerprint(lock: Mapping[str, Any], payload: Mapping[str, Any]) -> str:
    return fingerprint(
        {
            "model": MODEL,
            "instructions_fingerprint": lock["provider"]["instructions_fingerprint_sha256"],
            "input_fingerprint": fingerprint(payload),
            "text_schema_fingerprint": lock["provider"]["response_schema_fingerprint_sha256"],
            "reasoning": {"effort": REASONING_EFFORT},
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "store": False,
            "service_tier": "default",
            "truncation": "disabled",
            "timeout_seconds": TIMEOUT_SECONDS,
        }
    )


def is_hash(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(item in "0123456789abcdef" for item in value)


def validate_receipt(receipt: Mapping[str, Any], payload: Mapping[str, Any], phase: str, lock: Mapping[str, Any]) -> None:
    exact_keys(
        receipt,
        {"provider", "requested_model", "returned_model", "logical_calls", "api_calls", "latency_ms", "request_fingerprint", "prompt_fingerprint", "usage", "metadata"},
        f"receipt.{phase}",
    )
    require(
        receipt["provider"] == "openai_responses"
        and receipt["requested_model"] == MODEL
        and receipt["returned_model"] == MODEL
        and receipt["logical_calls"] == 1
        and receipt["api_calls"] == 1
        and receipt["request_fingerprint"] == fingerprint(payload)
        and receipt["prompt_fingerprint"] == lock["provider"]["instructions_fingerprint_sha256"],
        "RECEIPT_IDENTITY_DRIFT",
        phase,
    )
    require(
        isinstance(receipt["latency_ms"], (int, float))
        and not isinstance(receipt["latency_ms"], bool)
        and math.isfinite(float(receipt["latency_ms"]))
        and float(receipt["latency_ms"]) >= 0.0,
        "RECEIPT_LATENCY_INVALID",
        phase,
    )
    usage = exact_keys(
        receipt["usage"],
        {"exact_provider_tokens", "input_tokens", "output_tokens", "total_tokens", "cached_input_tokens", "cache_write_tokens", "reasoning_tokens"},
        f"receipt.{phase}.usage",
    )
    require(usage["exact_provider_tokens"] is True, "RECEIPT_TOKEN_EXACTNESS_DRIFT", phase)
    for key in ("input_tokens", "output_tokens", "total_tokens", "cached_input_tokens", "cache_write_tokens", "reasoning_tokens"):
        require(isinstance(usage[key], int) and not isinstance(usage[key], bool) and usage[key] >= 0, "RECEIPT_TOKEN_INVALID", f"{phase}.{key}")
    require(usage["total_tokens"] == usage["input_tokens"] + usage["output_tokens"], "RECEIPT_USAGE_TOTAL_INVALID", phase)
    metadata = receipt["metadata"]
    expected_metadata_keys = {
        "receipt_schema_version", "status", "service_tier", "response_id_sha256", "server_request_id_sha256", "client_request_id_sha256", "provider_body_sha256", "provider_body_byte_count", "http_observed", "http_status_code", "parse_boundary", "failure_phase", "failure_reason_code", "failure_type", "response_schema_fingerprint", "semantic_protocol_fingerprint", "reasoning_effort", "max_output_tokens", "store", "previous_response_id", "truncation", "sdk_version", "pydantic_version", "python_version", "attempt", "retry_count", "api_call_count_semantics", "attempt_outcome", "refusal_count",
    }
    exact_keys(metadata, expected_metadata_keys, f"receipt.{phase}.metadata")
    require(
        metadata["receipt_schema_version"] == "ebrt-provider-boundary-receipt-v0.4.3"
        and metadata["status"] == "completed"
        and metadata["service_tier"] == "default"
        and metadata["http_observed"] is True
        and metadata["http_status_code"] == 200
        and metadata["parse_boundary"] == "succeeded"
        and metadata["failure_phase"] is None
        and metadata["failure_reason_code"] is None
        and metadata["failure_type"] is None
        and metadata["response_schema_fingerprint"] == lock["provider"]["response_schema_fingerprint_sha256"]
        and metadata["semantic_protocol_fingerprint"] == expected_protocol_fingerprint(lock, payload)
        and metadata["reasoning_effort"] == REASONING_EFFORT
        and metadata["max_output_tokens"] == MAX_OUTPUT_TOKENS
        and metadata["store"] is False
        and metadata["previous_response_id"] is False
        and metadata["truncation"] == "disabled"
        and metadata["sdk_version"] == lock["runtime"]["openai"]
        and metadata["pydantic_version"] == lock["runtime"]["pydantic"]
        and metadata["python_version"] == lock["runtime"]["python"]
        and metadata["attempt"] == 1
        and metadata["retry_count"] == 0
        and metadata["api_call_count_semantics"] == "attempted_client_call"
        and metadata["attempt_outcome"] == "completed"
        and metadata["refusal_count"] == 0,
        "RECEIPT_METADATA_DRIFT",
        phase,
    )
    require(is_hash(metadata["response_id_sha256"]) and is_hash(metadata["client_request_id_sha256"]), "RECEIPT_MANDATORY_HASH_INVALID", phase)
    require(metadata["server_request_id_sha256"] is None or is_hash(metadata["server_request_id_sha256"]), "RECEIPT_SERVER_HASH_INVALID", phase)
    require(metadata["provider_body_sha256"] is None or is_hash(metadata["provider_body_sha256"]), "RECEIPT_BODY_HASH_INVALID", phase)
    require(
        isinstance(metadata["provider_body_byte_count"], int)
        and not isinstance(metadata["provider_body_byte_count"], bool)
        and metadata["provider_body_byte_count"] >= 0,
        "RECEIPT_BODY_BYTES_INVALID",
        phase,
    )


def grade(compiled: Mapping[str, Any], expected: Mapping[str, Any]) -> dict[str, Any]:
    observed_targets = {row["target_id"]: row for row in compiled["targets"]}
    expected_targets = {row["target_id"]: row for row in expected["targets"]}
    target_results = []
    for target_id in sorted(expected_targets):
        wanted = expected_targets[target_id]
        observed = observed_targets.get(target_id)
        checks = {
            "metadata_exact": bool(observed and (observed["target_type"], observed["slot"], observed["value"]) == (wanted["target_type"], wanted["slot"], wanted["value"])),
            "direct_exact": bool(observed and observed["direct_active_evidence_ids"] == wanted["direct_active_evidence_ids"]),
            "inherited_exact": bool(observed and observed["inherited_active_evidence_ids"] == wanted["inherited_active_evidence_ids"]),
            "total_exact": bool(observed and observed["all_active_evidence_ids"] == wanted["all_active_evidence_ids"]),
        }
        target_results.append({"target_id": target_id, "status": "PASS" if all(checks.values()) else "FAIL", "checks": checks})
    statuses = {
        "answer_status": "PASS" if compiled["current_answer"] == expected["answer"] else "FAIL",
        "closure_selection_status": "PASS" if compiled["selected_closure_id"] == expected["selected_closure_id"] else "FAIL",
        "fact_local_lineage_status": "PASS" if all(row["status"] == "PASS" for row in target_results if row["target_id"].startswith("fact:")) else "FAIL",
        "invalidation_status": "PASS" if compiled["invalidation_edges"] == expected["invalidation_edges"] else "FAIL",
        "stable_fact_status": "PASS" if all(row["status"] == "PASS" for row in target_results if row["target_id"].startswith("constraint:")) else "FAIL",
    }
    return seal(
        {
            "schema_version": "ebrt-apply-revision-grade-v0.6.2.1",
            "status": "PASS" if all(value == "PASS" for value in statuses.values()) else "FAIL",
            **statuses,
            "target_results": target_results,
            "compiled_fingerprint_sha256": compiled["fingerprint_sha256"],
        }
    )


def stale_grade(compiled: Mapping[str, Any], gold: Mapping[str, Any]) -> dict[str, Any]:
    pre = grade(compiled, gold["before_event"])
    post = grade(compiled, gold["after_event"])
    axes = sorted(
        axis
        for axis in ("answer_status", "fact_local_lineage_status", "invalidation_status", "stable_fact_status")
        if post[axis] == "FAIL"
    )
    expected = gold["stale_expectation"]
    checks = {
        "before_own_horizon_pass": pre["status"] == "PASS",
        "same_before_compiled_bytes_used": post["compiled_fingerprint_sha256"] == compiled["fingerprint_sha256"],
        "post_event_status_fail": post["status"] == expected["post_event_status"],
        "failed_axes_exact": axes == expected["failed_axes"],
        "stable_axis_pass": post[expected["stable_axis"]] == expected["stable_axis_status"],
    }
    return seal(
        {
            "schema_version": "ebrt-apply-revision-stale-regrade-v0.6.2.1",
            "status": "PASS" if all(checks.values()) else "FAIL",
            "checks": checks,
            "failed_axes": axes,
            "pre_grade": pre,
            "post_grade": post,
        }
    )


def public_diff(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    before_targets = {row["target_id"]: row for row in before["targets"]}
    after_targets = {row["target_id"]: row for row in after["targets"]}
    before_support = set(before["active_support_evidence_ids"])
    after_support = set(after["active_support_evidence_ids"])
    before_edges = {(row["source_evidence_id"], row["target_evidence_id"]) for row in before["invalidation_edges"]}
    after_edges = {(row["source_evidence_id"], row["target_evidence_id"]) for row in after["invalidation_edges"]}
    return seal(
        {
            "schema_version": "ebrt-apply-revision-public-diff-v0.6.2.1",
            "answer": {"before": before["current_answer"], "after": after["current_answer"]},
            "selected_closure_id": {"before": before["selected_closure_id"], "after": after["selected_closure_id"]},
            "target_values": [
                {
                    "target_id": target_id,
                    "slot": before_targets[target_id]["slot"],
                    "before": before_targets[target_id]["value"],
                    "after": after_targets[target_id]["value"],
                    "changed": before_targets[target_id]["value"] != after_targets[target_id]["value"],
                }
                for target_id in sorted(before_targets)
            ],
            "support_added_evidence_ids": sorted(after_support - before_support),
            "support_dropped_evidence_ids": sorted(before_support - after_support),
            "invalidation_added_edges": [
                {"source_evidence_id": source, "target_evidence_id": target}
                for source, target in sorted(after_edges - before_edges)
            ],
            "stable_target_ids": [
                target_id
                for target_id in sorted(before_targets)
                if target_id.startswith("constraint:")
                and before_targets[target_id]["value"] == after_targets[target_id]["value"]
                and before_targets[target_id]["all_active_evidence_ids"] == after_targets[target_id]["all_active_evidence_ids"]
            ],
        }
    )


def usage_summary(executions: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    receipts = [row["receipt"] for row in executions.values()]
    return {
        "logical_calls": sum(row["logical_calls"] for row in receipts),
        "api_calls": sum(row["api_calls"] for row in receipts),
        "input_tokens": sum(row["usage"]["input_tokens"] for row in receipts),
        "output_tokens": sum(row["usage"]["output_tokens"] for row in receipts),
        "reasoning_tokens": sum(row["usage"]["reasoning_tokens"] for row in receipts),
        "total_tokens": sum(row["usage"]["total_tokens"] for row in receipts),
        "latency_ms": math.fsum(float(row["latency_ms"]) for row in receipts),
    }


def expected_result(
    fixture: Mapping[str, Any],
    gold: Mapping[str, Any],
    executions: Mapping[str, Any],
    control: Mapping[str, Any],
    actuator: Mapping[str, Any],
    payloads: Mapping[str, Any],
    claim_boundary: Sequence[str],
) -> dict[str, Any]:
    before = executions["before_event"]["compiled_output"]
    after = executions["after_event"]["compiled_output"]
    before_grade = grade(before, gold["before_event"])
    stale = stale_grade(before, gold)
    after_grade = grade(after, gold["after_event"])
    diff = public_diff(before, after)
    mechanism = {
        **control["checks"],
        "actuator_compiled_deterministically": actuator["source_control_map_fingerprint_sha256"] == control["fingerprint_sha256"],
        "after_payload_sealed_after_before_terminal": payloads["after_event"]["apply_revision"]["source_actuator_fingerprint_sha256"] == actuator["fingerprint_sha256"],
    }
    product = {
        "exactly_two_structurally_valid_terminals": len(executions) == 2,
        "before_own_horizon_strict_pass": before_grade["status"] == "PASS",
        "same_before_post_event_stale_signature_exact": stale["status"] == "PASS",
        "after_post_event_strict_pass": after_grade["status"] == "PASS",
        "expected_public_diff_exact": False,
        "invalidated_support_absent": not bool(set(after["active_support_evidence_ids"]) & set(after["invalidated_evidence_ids"])),
        "stable_target_preserved": "constraint:video_constraint" in diff["stable_target_ids"],
        "surrogate_control_output_grade_separated": True,
    }
    observed_diff = without_fingerprint(diff)
    observed_diff.pop("schema_version")
    product["expected_public_diff_exact"] = canonical_bytes(observed_diff) == canonical_bytes(gold["expected_public_diff"])
    mechanism_pass = all(mechanism.values())
    product_pass = all(product.values()) and mechanism_pass
    return seal(
        {
            "schema_version": RESULT_SCHEMA,
            "status": "COMPLETE_EXACT_TWO_TERMINALS",
            "case_id": fixture["case"]["case_id"],
            "phase_order": list(PHASES),
            "executions": copy.deepcopy(dict(executions)),
            "revision_engine": {"control_map": copy.deepcopy(control), "compiled_actuator": copy.deepcopy(actuator)},
            "grades": {"before": before_grade, "before_post_event_stale": stale, "after": after_grade},
            "output_diff": diff,
            "checks": {"mechanism": mechanism, "product": product},
            "semantic_gold": {
                "loaded": True,
                "load_count": 1,
                "reason": "TWO_STRUCTURALLY_VALID_TERMINALS_EXIST",
                "fingerprint_sha256": gold["fingerprint_sha256"],
            },
            "decision": {
                "run_status": "COMPLETE_EXACT_TWO_TERMINALS",
                "mechanism_status": "PASS" if mechanism_pass else "FAIL",
                "before_status": "PASS_THEN_STALE" if before_grade["status"] == stale["status"] == "PASS" else "FAIL",
                "after_status": "PASS_STRICT_POST_EVENT" if after_grade["status"] == "PASS" else "FAIL",
                "diff_status": "OBSERVED_EXPECTED_PUBLIC_DIFF" if product["expected_public_diff_exact"] else "DIFF_MISMATCH",
                "product_acceptance_status": "PASS" if product_pass else "FAIL",
                "effect_attribution_status": "NOT_ASSESSED",
                "terminal_decision": gold["acceptance_contract"]["pass_terminal_decision"] if product_pass else gold["acceptance_contract"]["fail_terminal_decision"],
            },
            "accounting": usage_summary(executions),
            "claim_boundary": list(claim_boundary),
        }
    )


def calls_bytes(executions: Mapping[str, Any]) -> bytes:
    rows = []
    for phase in PHASES:
        row = executions[phase]
        rows.append(
            seal(
                {
                    "schema_version": CALL_SCHEMA,
                    "phase_id": phase,
                    "run_position": row["run_position"],
                    "status": row["status"],
                    "provider_input_fingerprint_sha256": row["provider_input_fingerprint_sha256"],
                    "public_output_fingerprint_sha256": fingerprint(row["public_output"]),
                    "compiled_output_fingerprint_sha256": row["compiled_output"]["fingerprint_sha256"],
                    "failure": None,
                    "receipt": copy.deepcopy(row["receipt"]),
                }
            )
        )
    return b"".join(canonical_bytes(row, newline=True) for row in rows)


def journal_row(kind: str, **fields: Any) -> dict[str, Any]:
    return seal({"schema_version": JOURNAL_SCHEMA, "kind": kind, **fields})


def expected_journal(
    executions: Mapping[str, Any], payloads: Mapping[str, Any], control: Mapping[str, Any], actuator: Mapping[str, Any]
) -> list[dict[str, Any]]:
    before = executions["before_event"]
    after = executions["after_event"]
    before_input = fingerprint(payloads["before_event"])
    after_input = fingerprint(payloads["after_event"])
    before_public = fingerprint(before["public_output"])
    before_compiled = before["compiled_output"]["fingerprint_sha256"]
    return [
        journal_row("ATTEMPT_STARTED", phase_id="before_event", run_position=0, provider_input_fingerprint_sha256=before_input),
        journal_row("ATTEMPT_TERMINAL", phase_id="before_event", run_position=0, status="completed", provider_input_fingerprint_sha256=before_input, public_output_fingerprint_sha256=before_public, compiled_output_fingerprint_sha256=before_compiled),
        journal_row("REVISION_STARTED", source_before_public_output_fingerprint_sha256=before_public, source_before_compiled_fingerprint_sha256=before_compiled, gold_loaded=False),
        journal_row(
            "REVISION_COMPILED",
            source_before_public_output_fingerprint_sha256=before_public,
            source_before_compiled_fingerprint_sha256=before_compiled,
            controller_input_fingerprint_sha256=control["actual_before_state"]["fingerprint_sha256"],
            autograd_audit_fingerprint_sha256=control["source_credit_basis"]["source_adjoint_fingerprint_sha256"],
            control_map_fingerprint_sha256=control["fingerprint_sha256"],
            compiled_actuator_fingerprint_sha256=actuator["fingerprint_sha256"],
            after_provider_input_fingerprint_sha256=after_input,
            gold_loaded=False,
        ),
        journal_row("ATTEMPT_STARTED", phase_id="after_event", run_position=1, provider_input_fingerprint_sha256=after_input),
        journal_row("ATTEMPT_TERMINAL", phase_id="after_event", run_position=1, status="completed", provider_input_fingerprint_sha256=after_input, public_output_fingerprint_sha256=fingerprint(after["public_output"]), compiled_output_fingerprint_sha256=after["compiled_output"]["fingerprint_sha256"]),
    ]


def expected_provider_inputs(payloads: Mapping[str, Any]) -> dict[str, Any]:
    return seal(
        {
            "schema_version": PROVIDER_INPUTS_SCHEMA,
            "phase_order": list(payloads),
            "payloads": [
                {"phase_id": phase, "payload_fingerprint_sha256": fingerprint(payload), "payload": copy.deepcopy(payload)}
                for phase, payload in payloads.items()
            ],
            "after_payload_was_dynamic": "after_event" in payloads,
            "semantic_gold_provider_visible": False,
        }
    )


def expected_trace(executions: Mapping[str, Any], control: Mapping[str, Any], actuator: Mapping[str, Any]) -> dict[str, Any]:
    return seal(
        {
            "schema_version": TRACE_SCHEMA,
            "actual_before_compiled_fingerprint_sha256": executions["before_event"]["compiled_output"]["fingerprint_sha256"],
            "control_map": copy.deepcopy(control),
            "compiled_actuator": copy.deepcopy(actuator),
            "effect_attribution_status": "NOT_ASSESSED",
            "gradient_boundary": "local public surrogate to public control map only",
        }
    )


def report_text(result: Mapping[str, Any], claim_boundary: Sequence[str]) -> str:
    decision = result["decision"]
    actuator = result["revision_engine"]["compiled_actuator"]
    lines = [
        "# EBRT v0.6.2.1 — Apply Revision Acceptance",
        "",
        f"- Run: `{decision['run_status']}`",
        f"- Mechanism: `{decision['mechanism_status']}`",
        f"- Before: `{decision['before_status']}`",
        f"- After: `{decision['after_status']}`",
        f"- Public diff: `{decision['diff_status']}`",
        f"- Product acceptance: `{decision['product_acceptance_status']}`",
        f"- Effect attribution: `{decision['effect_attribution_status']}`",
        f"- Provider calls: `{result['accounting']['api_calls']}/2`",
        f"- Semantic gold loaded: `{str(result['semantic_gold']['loaded']).lower()}`",
        "",
        "## Apply Revision",
        "",
        f"- Reinspect: `{' → '.join(actuator['reinspect_evidence_ids'])}`",
        f"- Suppress: `{', '.join(actuator['suppress_evidence_ids'])}`",
        f"- Preserve: `{', '.join(actuator['preserve_evidence_ids'])}`",
        "",
        "## Claim boundary",
        "",
        *[f"- {item}" for item in claim_boundary],
        "",
    ]
    return "\n".join(lines)


def expected_manifest(files: Mapping[str, bytes], result: Mapping[str, Any], lock: Mapping[str, Any]) -> dict[str, Any]:
    return seal(
        {
            "schema_version": MANIFEST_SCHEMA,
            "status": "SEALED_APPLY_REVISION_RESULT",
            "result_fingerprint_sha256": result["fingerprint_sha256"],
            "policy_lock_fingerprint_sha256": lock["fingerprint_sha256"],
            "artifacts": {
                name: {"bytes": len(raw), "sha256": sha256(raw)}
                for name, raw in files.items()
            },
            "effect_attribution_status": "NOT_ASSESSED",
            "claim_boundary": list(lock["claim_boundary"]),
        }
    )


def validate_bundle(
    artifact: Path,
    *,
    verify_exact_publication: bool = True,
    verify_git: bool = True,
) -> dict[str, Any]:
    files = read_bundle(artifact)
    if verify_exact_publication:
        require(artifact.name == DEFAULT_ARTIFACT.name, "ARTIFACT_NAMESPACE_DRIFT")
        manifest_receipt = {"bytes": len(files["manifest.json"]), "sha256": sha256(files["manifest.json"])}
        require(manifest_receipt == EXPECTED_MANIFEST_RECEIPT, "EXACT_MANIFEST_RECEIPT_DRIFT")

    lock = strict_object(LOCK_PATH.read_bytes(), "policy_lock")
    authorization = validate_lock_and_authorization(lock, verify_git=verify_git)
    fixture, gold = load_locked_inputs(lock)
    manifest = strict_object(files["manifest.json"], "manifest")
    validate_seal(manifest, "manifest")
    exact_keys(
        manifest,
        {"schema_version", "status", "result_fingerprint_sha256", "policy_lock_fingerprint_sha256", "artifacts", "effect_attribution_status", "claim_boundary", "fingerprint_sha256"},
        "manifest",
    )
    require(manifest["schema_version"] == MANIFEST_SCHEMA and manifest["status"] == "SEALED_APPLY_REVISION_RESULT", "MANIFEST_CONTRACT_DRIFT")
    require(set(manifest["artifacts"]) == set(ARTIFACT_FILES) - {"manifest.json"}, "MANIFEST_ARTIFACT_SET_DRIFT")
    for name, receipt in manifest["artifacts"].items():
        require(receipt == {"bytes": len(files[name]), "sha256": sha256(files[name])}, "MANIFEST_ARTIFACT_RECEIPT_DRIFT", name)
    require(manifest["policy_lock_fingerprint_sha256"] == lock["fingerprint_sha256"], "MANIFEST_LOCK_BINDING_DRIFT")
    require(manifest["claim_boundary"] == lock["claim_boundary"] and manifest["effect_attribution_status"] == "NOT_ASSESSED", "MANIFEST_CLAIM_BOUNDARY_DRIFT")

    result = strict_object(files["result.json"], "result")
    provider_inputs = strict_object(files["provider_inputs.json"], "provider_inputs")
    trace = strict_object(files["apply_revision_trace.json"], "trace")
    for label, value in (("result", result), ("provider_inputs", provider_inputs), ("trace", trace)):
        validate_seal(value, label)
    require(result["schema_version"] == RESULT_SCHEMA and result["status"] == "COMPLETE_EXACT_TWO_TERMINALS", "RESULT_TERMINAL_STATUS_DRIFT")
    require(manifest["result_fingerprint_sha256"] == result["fingerprint_sha256"], "MANIFEST_RESULT_BINDING_DRIFT")
    if verify_exact_publication:
        require(result["fingerprint_sha256"] == EXPECTED_RESULT_FINGERPRINT, "EXACT_RESULT_ID_DRIFT")
    require(provider_inputs["schema_version"] == PROVIDER_INPUTS_SCHEMA, "PROVIDER_INPUTS_SCHEMA_DRIFT")
    require(
        provider_inputs["phase_order"] == list(PHASES)
        and provider_inputs["after_payload_was_dynamic"] is True
        and provider_inputs["semantic_gold_provider_visible"] is False
        and [row["phase_id"] for row in provider_inputs["payloads"]] == list(PHASES),
        "PROVIDER_INPUTS_GEOMETRY_DRIFT",
    )
    payloads: dict[str, Any] = {}
    for row in provider_inputs["payloads"]:
        exact_keys(row, {"phase_id", "payload_fingerprint_sha256", "payload"}, "provider_input_row")
        require(row["payload_fingerprint_sha256"] == fingerprint(row["payload"]), "PROVIDER_INPUT_ROW_BINDING_DRIFT", row["phase_id"])
        validate_payload(fixture, row["phase_id"], row["payload"])
        payloads[row["phase_id"]] = row["payload"]

    executions = result["executions"]
    require(set(executions) == set(PHASES), "EXECUTION_PHASE_SET_DRIFT")
    for position, phase in enumerate(PHASES):
        row = executions[phase]
        exact_keys(row, {"phase_id", "run_position", "status", "provider_input_fingerprint_sha256", "public_output", "compiled_output", "receipt", "failure"}, f"execution.{phase}")
        require(row["phase_id"] == phase and row["run_position"] == position and row["status"] == "completed" and row["failure"] is None, "EXECUTION_TERMINAL_GEOMETRY_DRIFT", phase)
        require(row["provider_input_fingerprint_sha256"] == fingerprint(payloads[phase]), "EXECUTION_INPUT_BINDING_DRIFT", phase)
        compiled = compile_output(fixture, phase, row["public_output"])
        require(canonical_bytes(compiled) == canonical_bytes(row["compiled_output"]), "COMPILED_OUTPUT_REDERIVATION_DRIFT", phase)
        validate_receipt(row["receipt"], payloads[phase], phase, lock)

    before_compiled = executions["before_event"]["compiled_output"]
    control = trace["control_map"]
    actuator = trace["compiled_actuator"]
    validate_control_map(fixture, before_compiled, control, lock)
    derived_actuator = compile_actuator(fixture, before_compiled, control)
    require(canonical_bytes(actuator) == canonical_bytes(derived_actuator), "ACTUATOR_REDERIVATION_DRIFT")
    derived_before_payload = build_payload(fixture, "before_event")
    derived_after_payload = build_payload(fixture, "after_event", compiled_before=before_compiled, actuator=derived_actuator)
    require(canonical_bytes(payloads["before_event"]) == canonical_bytes(derived_before_payload), "BEFORE_PAYLOAD_REDERIVATION_DRIFT")
    require(canonical_bytes(payloads["after_event"]) == canonical_bytes(derived_after_payload), "AFTER_PAYLOAD_REDERIVATION_DRIFT")
    require(canonical_bytes(provider_inputs) == canonical_bytes(expected_provider_inputs(payloads)), "PROVIDER_INPUTS_REDERIVATION_DRIFT")
    require(canonical_bytes(trace) == canonical_bytes(expected_trace(executions, control, actuator)), "TRACE_REDERIVATION_DRIFT")
    require(canonical_bytes(result["revision_engine"]) == canonical_bytes({"control_map": control, "compiled_actuator": actuator}), "RESULT_TRACE_BINDING_DRIFT")

    rebuilt_result = expected_result(fixture, gold, executions, control, actuator, payloads, lock["claim_boundary"])
    require(canonical_bytes(result) == canonical_bytes(rebuilt_result), "RESULT_REDERIVATION_DRIFT")
    require(files["calls.jsonl"] == calls_bytes(executions), "CALLS_ARTIFACT_DRIFT")
    calls = strict_jsonl(files["calls.jsonl"], "calls")
    require(len(calls) == 2 and [row["phase_id"] for row in calls] == list(PHASES), "CALLS_GEOMETRY_DRIFT")
    for row in calls:
        validate_seal(row, "call_row")
    journal = strict_jsonl(files["attempt_journal.jsonl"], "attempt_journal")
    require(len(journal) == 6, "JOURNAL_ROW_COUNT_DRIFT")
    for row in journal:
        validate_seal(row, "journal_row")
    require(canonical_bytes(journal) == canonical_bytes(expected_journal(executions, payloads, control, actuator)), "JOURNAL_BINDING_DRIFT")
    require(files["report.md"] == report_text(result, lock["claim_boundary"]).encode("utf-8"), "REPORT_DRIFT")
    rebuilt_manifest = expected_manifest({name: raw for name, raw in files.items() if name != "manifest.json"}, result, lock)
    require(canonical_bytes(manifest) == canonical_bytes(rebuilt_manifest), "MANIFEST_REDERIVATION_DRIFT")
    require(
        result["decision"]
        == {
            "run_status": "COMPLETE_EXACT_TWO_TERMINALS",
            "mechanism_status": "PASS",
            "before_status": "PASS_THEN_STALE",
            "after_status": "PASS_STRICT_POST_EVENT",
            "diff_status": "OBSERVED_EXPECTED_PUBLIC_DIFF",
            "product_acceptance_status": "PASS",
            "effect_attribution_status": "NOT_ASSESSED",
            "terminal_decision": "ACCEPT_APPLY_REVISION_PATH",
        },
        "DECISION_CONTRACT_DRIFT",
    )
    return {
        "schema_version": "ebrt-apply-revision-portable-verification-v0.6.2.1-r01",
        "status": "VALID",
        "artifact_directory": str(artifact.resolve()),
        "result_fingerprint_sha256": result["fingerprint_sha256"],
        "manifest_file_sha256": sha256(files["manifest.json"]),
        "policy_lock_fingerprint_sha256": lock["fingerprint_sha256"],
        "authorization": authorization,
        "terminal_decision": result["decision"]["terminal_decision"],
        "product_acceptance_status": result["decision"]["product_acceptance_status"],
        "effect_attribution_status": result["decision"]["effect_attribution_status"],
        "provider_calls": result["accounting"]["api_calls"],
        "network_calls": 0,
        "gradient_boundary": "public scalar surrogate to public control map only",
    }


def reseal_manifest(bundle: Path) -> None:
    manifest = strict_object((bundle / "manifest.json").read_bytes(), "tamper_manifest")
    for name in ARTIFACT_FILES:
        if name != "manifest.json":
            raw = (bundle / name).read_bytes()
            manifest["artifacts"][name] = {"bytes": len(raw), "sha256": sha256(raw)}
    result = strict_object((bundle / "result.json").read_bytes(), "tamper_result_for_manifest")
    manifest["result_fingerprint_sha256"] = result.get("fingerprint_sha256")
    (bundle / "manifest.json").write_bytes(pretty_bytes(seal(without_fingerprint(manifest))))


def self_test(artifact: Path, *, verify_git: bool = True) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    pristine = validate_bundle(
        artifact,
        verify_exact_publication=True,
        verify_git=verify_git,
    )
    checks["pristine_exact_publication_valid"] = pristine["status"] == "VALID"
    with tempfile.TemporaryDirectory(prefix="ebrt-v0621-portable-verifier-") as raw_tmp:
        temporary = Path(raw_tmp)

        duplicate = temporary / "duplicate"
        shutil.copytree(artifact, duplicate)
        (duplicate / "result.json").write_bytes(b'{"schema_version":"x","schema_version":"y"}\n')
        manifest = strict_object((duplicate / "manifest.json").read_bytes(), "duplicate_manifest")
        raw = (duplicate / "result.json").read_bytes()
        manifest["artifacts"]["result.json"] = {"bytes": len(raw), "sha256": sha256(raw)}
        (duplicate / "manifest.json").write_bytes(pretty_bytes(seal(without_fingerprint(manifest))))
        try:
            validate_bundle(duplicate, verify_exact_publication=False, verify_git=False)
            checks["duplicate_json_rejected"] = False
        except VerificationError as error:
            checks["duplicate_json_rejected"] = error.reason_code == "DUPLICATE_JSON_KEY"

        nonfinite = temporary / "nonfinite"
        shutil.copytree(artifact, nonfinite)
        raw_result = (nonfinite / "result.json").read_bytes().replace(b'9304.385541006923', b'NaN', 1)
        (nonfinite / "result.json").write_bytes(raw_result)
        manifest = strict_object((nonfinite / "manifest.json").read_bytes(), "nonfinite_manifest")
        manifest["artifacts"]["result.json"] = {"bytes": len(raw_result), "sha256": sha256(raw_result)}
        (nonfinite / "manifest.json").write_bytes(pretty_bytes(seal(without_fingerprint(manifest))))
        try:
            validate_bundle(nonfinite, verify_exact_publication=False, verify_git=False)
            checks["nonfinite_json_rejected"] = False
        except VerificationError as error:
            checks["nonfinite_json_rejected"] = error.reason_code == "NONFINITE_JSON"

        receipt = temporary / "receipt"
        shutil.copytree(artifact, receipt)
        result = strict_object((receipt / "result.json").read_bytes(), "receipt_result")
        result["executions"]["before_event"]["receipt"]["requested_model"] = "not-locked"
        result = seal(without_fingerprint(result))
        (receipt / "result.json").write_bytes(pretty_bytes(result))
        calls = strict_jsonl((receipt / "calls.jsonl").read_bytes(), "receipt_calls")
        calls[0]["receipt"]["requested_model"] = "not-locked"
        calls[0] = seal(without_fingerprint(calls[0]))
        (receipt / "calls.jsonl").write_bytes(b"".join(canonical_bytes(row, newline=True) for row in calls))
        reseal_manifest(receipt)
        try:
            validate_bundle(receipt, verify_exact_publication=False, verify_git=False)
            checks["coherent_receipt_tamper_rejected"] = False
        except VerificationError as error:
            checks["coherent_receipt_tamper_rejected"] = error.reason_code == "RECEIPT_IDENTITY_DRIFT"

        journal_bundle = temporary / "journal"
        shutil.copytree(artifact, journal_bundle)
        rows = strict_jsonl((journal_bundle / "attempt_journal.jsonl").read_bytes(), "journal_rows")
        rows[0]["provider_input_fingerprint_sha256"] = "0" * 64
        rows[0] = seal(without_fingerprint(rows[0]))
        (journal_bundle / "attempt_journal.jsonl").write_bytes(b"".join(canonical_bytes(row, newline=True) for row in rows))
        reseal_manifest(journal_bundle)
        try:
            validate_bundle(journal_bundle, verify_exact_publication=False, verify_git=False)
            checks["coherent_journal_tamper_rejected"] = False
        except VerificationError as error:
            checks["coherent_journal_tamper_rejected"] = error.reason_code == "JOURNAL_BINDING_DRIFT"

        dynamic = temporary / "dynamic"
        shutil.copytree(artifact, dynamic)
        provider = strict_object((dynamic / "provider_inputs.json").read_bytes(), "dynamic_provider")
        provider["payloads"][1]["payload"]["apply_revision"]["reinspect_evidence_ids"] = ["R2", "R4", "R6"]
        provider["payloads"][1]["payload_fingerprint_sha256"] = fingerprint(provider["payloads"][1]["payload"])
        provider = seal(without_fingerprint(provider))
        (dynamic / "provider_inputs.json").write_bytes(pretty_bytes(provider))
        reseal_manifest(dynamic)
        try:
            validate_bundle(dynamic, verify_exact_publication=False, verify_git=False)
            checks["dynamic_payload_tamper_rejected"] = False
        except VerificationError as error:
            checks["dynamic_payload_tamper_rejected"] = error.reason_code in {
                "EXECUTION_INPUT_BINDING_DRIFT",
                "AFTER_PAYLOAD_REDERIVATION_DRIFT",
            }

        control_bundle = temporary / "control"
        shutil.copytree(artifact, control_bundle)
        trace = strict_object(
            (control_bundle / "apply_revision_trace.json").read_bytes(),
            "control_trace",
        )
        trace["control_map"]["credit_rows"][5]["gradient"] += 0.01
        trace["control_map"] = seal(without_fingerprint(trace["control_map"]))
        trace = seal(without_fingerprint(trace))
        (control_bundle / "apply_revision_trace.json").write_bytes(
            pretty_bytes(trace)
        )
        result = strict_object(
            (control_bundle / "result.json").read_bytes(), "control_result"
        )
        result["revision_engine"]["control_map"] = copy.deepcopy(
            trace["control_map"]
        )
        result = seal(without_fingerprint(result))
        (control_bundle / "result.json").write_bytes(pretty_bytes(result))
        reseal_manifest(control_bundle)
        try:
            validate_bundle(
                control_bundle,
                verify_exact_publication=False,
                verify_git=False,
            )
            checks["coherent_control_tamper_rejected"] = False
        except VerificationError as error:
            checks["coherent_control_tamper_rejected"] = (
                error.reason_code == "CONTROL_NUMERIC_REDERIVATION_DRIFT"
            )

        accounting = temporary / "accounting"
        shutil.copytree(artifact, accounting)
        result = strict_object(
            (accounting / "result.json").read_bytes(), "accounting_result"
        )
        result["accounting"]["total_tokens"] += 1
        result = seal(without_fingerprint(result))
        (accounting / "result.json").write_bytes(pretty_bytes(result))
        reseal_manifest(accounting)
        try:
            validate_bundle(
                accounting,
                verify_exact_publication=False,
                verify_git=False,
            )
            checks["coherent_accounting_tamper_rejected"] = False
        except VerificationError as error:
            checks["coherent_accounting_tamper_rejected"] = (
                error.reason_code == "RESULT_REDERIVATION_DRIFT"
            )

        extra = temporary / "extra"
        shutil.copytree(artifact, extra)
        (extra / "unexpected.txt").write_text("x", encoding="utf-8")
        try:
            validate_bundle(extra, verify_exact_publication=False, verify_git=False)
            checks["extra_file_rejected"] = False
        except VerificationError as error:
            checks["extra_file_rejected"] = error.reason_code == "ARTIFACT_DIRECTORY_NONCANONICAL"

    require(all(checks.values()), "SELF_TEST_FAILED", ",".join(key for key, value in checks.items() if not value))
    return seal(
        {
            "schema_version": "ebrt-apply-revision-portable-verifier-self-test-v0.6.2.1-r01",
            "status": "PASS",
            "checks": checks,
            "network_calls": 0,
            "canonical_result_fingerprint_sha256": EXPECTED_RESULT_FINGERPRINT,
        }
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", nargs="?", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--no-git", action="store_true", help="Skip annotated-tag verification; source receipts remain mandatory.")
    args = parser.parse_args(argv)
    try:
        output = (
            self_test(args.artifact, verify_git=not args.no_git)
            if args.self_test
            else validate_bundle(
                args.artifact,
                verify_exact_publication=True,
                verify_git=not args.no_git,
            )
        )
    except VerificationError as error:
        print(
            json.dumps(
                {"status": "INVALID", "reason_code": error.reason_code, "detail": str(error)},
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
