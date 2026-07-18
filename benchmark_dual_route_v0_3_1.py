#!/usr/bin/env python3
"""DEV benchmark for EBRT v0.3.1 replay/loss factorization.

The v0.3 terminal counterexample showed that one ``replay_floor`` variable
changed both physical recomputation and trajectory-loss support. This runner
keeps those factors separate and evaluates two narrow lanes:

* a cost lane that changes execution replay only and requires exact outcomes;
* a trajectory factorial that changes loss support only and allows outcomes to
  differ while holding routing and generator work fixed.

This is a DEV_DRAFT mechanism benchmark. It cannot create promotion evidence or
a holdout ledger until a separate lock contains entirely fresh promotion data.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import hashlib
import json
import platform
import re
import statistics
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

import torch

import dual_route_policy_v0_3_1 as policy


SCHEMA_VERSION = "ebrt-dual-route-benchmark-v0.3.1"
ROOT = Path(__file__).resolve().parent
LOCK_PATH = ROOT / "policy_lock_v0_3_1.json"
DEV_FIXTURE_PATH = ROOT / "fixtures" / "dual_route_v0_3_1_dev.json"
V03_HOLDOUT_FIXTURE_PATH = ROOT / "fixtures" / "dual_route_v0_3_holdout.json"
REGRESSION_FIXTURE_PATH = (
    ROOT / "fixtures" / "dual_route_v0_3_1_regression.json"
)
DEFAULT_FULL_OUTPUT = ROOT / "artifacts" / "benchmark_dual_route_v0_3_1"
DEFAULT_LEDGER = ROOT / "artifacts" / ".dual_route_v0_3_1_holdout_ledger.json"
DEV_COMMANDS = frozenset({"self-test", "quick", "epsilon-audit"})
RUNTIME_COMMANDS = DEV_COMMANDS | {"full"}
REQUIRED_SOURCE_LOCK_FILES = frozenset(
    {
        "ebrt_monolith_v0_1.py",
        "semantic_adapter_v0_2.py",
        "instrumentation_ebrt_v0_2.py",
        "dual_route_policy_v0_3_1.py",
        "benchmark_dual_route_v0_3_1.py",
        "fixtures/dual_route_v0_3_1_dev.json",
        "fixtures/dual_route_v0_3_1_regression.json",
    }
)
REQUIRED_HISTORICAL_EVIDENCE_FILES = frozenset(
    {
        "dual_route_policy_v0_3.py",
        "benchmark_dual_route_v0_3.py",
        "policy_lock_v0_3.json",
        "fixtures/dual_route_v0_3_dev.json",
        "fixtures/dual_route_v0_3_holdout.json",
        "fixtures/dual_route_v0_3_sequential.json",
        "artifacts/.dual_route_v0_3_holdout_ledger.json",
    }
)
RESERVED_PROTOCOL_FIELDS = frozenset({"seed", "revision_steps", "device", "dtype"})
CLAIM_BOUNDARY = (
    "This is a DEV_DRAFT structured-mechanism benchmark, not a promotion experiment.",
    "The historical regression case is contaminated by the v0.3 terminal attempt.",
    "Exact cost-lane equality is a tested software/mechanism invariant, not evidence of reasoning superiority.",
    "Trajectory-factorial differences isolate a toy loss-horizon mechanism and do not establish LLM improvement.",
    "A future full run requires a new LOCKED protocol and entirely fresh primary, stable, and sequential families.",
)
EXPECTED_FLOOR_FACTORIZATION = {
    "floor_policies": [
        "minimum_eligible_step",
        "minimum_selected_control_step",
    ],
    "matched_lane": {
        "probe_mode": "matched",
        "execution_replay_policy": "minimum_eligible_step",
        "trajectory_anchor_policy": "minimum_eligible_step",
    },
    "cost_lane": {
        "probe_mode": "matched",
        "execution_replay_policy": "minimum_selected_control_step",
        "trajectory_anchor_policy": "minimum_eligible_step",
        "fail_closed_invariant": (
            "exact events, controls, final states, decoded output, and outcome fingerprint"
        ),
    },
    "trajectory_factorial_lane": {
        "probe_mode": "matched",
        "execution_replay_policy": "minimum_eligible_step",
        "trajectory_anchor_policy": "minimum_selected_control_step",
        "fixed_factors": [
            "route",
            "objective_anchor",
            "control_steps",
            "execution_replay",
            "probe_work",
            "optimizer_budget",
        ],
        "outcome_difference_allowed": True,
    },
}


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_json_with_sha(path: Path) -> tuple[Any, str]:
    raw = path.read_bytes()
    return json.loads(raw.decode("utf-8")), hashlib.sha256(raw).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, tuple, dict)):
        return _canonical_json(value)
    if isinstance(value, bool):
        return int(value)
    return value


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fields})


def _runtime_environment_snapshot() -> dict[str, str]:
    return {
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "torch_version": torch.__version__,
        "system": platform.system(),
        "machine": platform.machine(),
        "platform": platform.platform(),
        "release": platform.release(),
    }


def _version_pair(value: str) -> tuple[int, int]:
    match = re.match(r"^(\d+)\.(\d+)", value)
    if match is None:
        return (-1, -1)
    return int(match.group(1)), int(match.group(2))


def validate_runtime_lock_schema(lock: Mapping[str, Any]) -> dict[str, Any]:
    if lock.get("status") not in {"DEV_DRAFT", "LOCKED"}:
        raise RuntimeError("policy lock status is missing or invalid")
    for field in ("promotion_eligible", "full_enabled"):
        if type(lock.get(field)) is not bool:
            raise RuntimeError(f"policy lock {field} must be an exact boolean")
    pending = lock.get("pending_promotion_inputs")
    if not isinstance(pending, list) or not all(
        isinstance(value, str) for value in pending
    ):
        raise RuntimeError("pending_promotion_inputs must be an explicit string list")
    runtime = lock.get("runtime")
    if not isinstance(runtime, Mapping):
        raise RuntimeError("runtime lock must be a mapping")
    commands = runtime.get("commands")
    if not isinstance(commands, Mapping) or frozenset(commands) != RUNTIME_COMMANDS:
        raise RuntimeError("runtime command lock key set changed")
    for command in sorted(RUNTIME_COMMANDS):
        command_lock = commands[command]
        if not isinstance(command_lock, Mapping):
            raise RuntimeError(f"runtime command lock must be a mapping: {command}")
        if frozenset(command_lock) != frozenset(
            {"exact_runtime_required", "promotion_eligible"}
        ):
            raise RuntimeError(f"runtime command lock schema changed: {command}")
        for field in ("exact_runtime_required", "promotion_eligible"):
            if type(command_lock.get(field)) is not bool:
                raise RuntimeError(
                    f"runtime command {command} {field} must be an exact boolean"
                )
    payload = {
        "status": lock["status"],
        "promotion_eligible": lock["promotion_eligible"],
        "full_enabled": lock["full_enabled"],
        "pending_promotion_inputs": pending,
        "commands": commands,
    }
    return {"status": "PASS", "schema_fingerprint": _fingerprint(payload)}


def assess_runtime_environment(
    lock: Mapping[str, Any],
    *,
    actual_environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    runtime = lock["runtime"]
    expected = {str(key): str(value) for key, value in runtime["expected_environment"].items()}
    actual_raw = actual_environment or _runtime_environment_snapshot()
    actual = {str(key): str(value) for key, value in actual_raw.items()}
    mismatches = [
        {"field": field, "expected": expected[field], "actual": actual.get(field)}
        for field in sorted(expected)
        if actual.get(field) != expected[field]
    ]
    support = runtime["dev_support"]
    support_violations: list[str] = []
    if _version_pair(actual.get("python_version", "")) < _version_pair(
        str(support["python_minimum"])
    ):
        support_violations.append("python_below_minimum")
    if actual.get("python_implementation") != str(support["python_implementation"]):
        support_violations.append("python_implementation_is_not_cpython")
    if _version_pair(actual.get("torch_version", "")) < _version_pair(
        str(support["torch_minimum"])
    ):
        support_violations.append("torch_below_minimum")
    if _version_pair(actual.get("torch_version", "")) >= _version_pair(
        str(support["torch_maximum_exclusive"])
    ):
        support_violations.append("torch_at_or_above_maximum")
    if str(runtime["device"]) != str(support["device"]) or str(runtime["device"]) != "cpu":
        support_violations.append("execution_device_is_not_supported_cpu")
    if str(runtime["dtype"]) != str(support["dtype"]) or str(runtime["dtype"]) != "float32":
        support_violations.append("execution_dtype_is_not_float32")
    return {
        "expected_environment": expected,
        "actual_environment": actual,
        "matched": not mismatches,
        "mismatches": mismatches,
        "supported_cpu_runtime": not support_violations,
        "support_contract": {
            "python_minimum": str(support["python_minimum"]),
            "python_implementation": str(support["python_implementation"]),
            "torch_minimum": str(support["torch_minimum"]),
            "torch_maximum_exclusive": str(support["torch_maximum_exclusive"]),
            "device": str(support["device"]),
            "dtype": str(support["dtype"]),
        },
        "support_violations": support_violations,
    }


def runtime_contract_for_command(
    lock: Mapping[str, Any],
    command: str,
    *,
    actual_environment: Mapping[str, str] | None = None,
    enforce: bool = True,
) -> dict[str, Any]:
    validate_runtime_lock_schema(lock)
    if command not in RUNTIME_COMMANDS:
        raise ValueError(f"unknown runtime command: {command}")
    command_lock = lock["runtime"]["commands"][command]
    assessment = assess_runtime_environment(
        lock,
        actual_environment=actual_environment,
    )
    exact_required = command_lock["exact_runtime_required"] is True
    if enforce and not assessment["supported_cpu_runtime"]:
        raise RuntimeError(
            "unsupported DEV/runtime contract: "
            + ",".join(assessment["support_violations"])
        )
    if enforce and exact_required and not assessment["matched"]:
        raise RuntimeError(
            "full runtime environment disagrees with policy lock: "
            + _canonical_json(assessment["mismatches"])
        )
    pending_promotion_inputs = lock["pending_promotion_inputs"]
    top_level_ready = (
        str(lock.get("status")) == "LOCKED"
        and lock.get("promotion_eligible") is True
        and lock.get("full_enabled") is True
        and pending_promotion_inputs == []
    )
    command_promotion_capability = command_lock["promotion_eligible"] is True
    effective_promotion_eligible = (
        command == "full" and command_promotion_capability and top_level_ready
    )
    byte_claim = (
        "same_locked_runtime_only"
        if assessment["matched"]
        else "none_cross_runtime"
    )
    return {
        "command": command,
        **assessment,
        "exact_runtime_required": exact_required,
        "command_promotion_capability": command_promotion_capability,
        "top_level_protocol_ready": top_level_ready,
        "promotion_eligible": effective_promotion_eligible,
        "artifact_scope": (
            "promotion_candidate_locked_runtime"
            if effective_promotion_eligible
            else "full_disabled_dev_draft"
            if command == "full"
            else "dev_only_actual_runtime"
        ),
        "byte_reproducibility_claim": byte_claim,
    }


def _configure_runtime(lock: Mapping[str, Any]) -> None:
    torch.set_num_threads(int(lock["runtime"]["torch_threads"]))


def _source_path(name: str) -> Path:
    return ROOT / name


def validate_source_lock(lock: Mapping[str, Any]) -> dict[str, Any]:
    declared = frozenset(str(name) for name in lock["source_sha256"])
    if declared != REQUIRED_SOURCE_LOCK_FILES:
        raise RuntimeError(
            "v0.3.1 source lock key set changed: "
            + _canonical_json(
                {
                    "missing": sorted(REQUIRED_SOURCE_LOCK_FILES - declared),
                    "extra": sorted(declared - REQUIRED_SOURCE_LOCK_FILES),
                }
            )
        )
    mismatches: list[dict[str, str]] = []
    pending: list[str] = []
    actual: dict[str, str] = {}
    for name, expected_value in lock["source_sha256"].items():
        expected = str(expected_value)
        path = _source_path(str(name))
        if not path.is_file():
            mismatches.append({"file": str(name), "expected": expected, "actual": "MISSING"})
            continue
        digest = _sha256(path)
        actual[str(name)] = digest
        if expected == "PENDING":
            pending.append(str(name))
        elif digest != expected:
            mismatches.append({"file": str(name), "expected": expected, "actual": digest})
    if mismatches:
        raise RuntimeError("v0.3.1 source lock mismatch: " + _canonical_json(mismatches))
    if str(lock["status"]) == "LOCKED" and pending:
        raise RuntimeError("LOCKED protocol contains pending source hashes")
    return {"status": "PASS", "actual_sha256": actual, "pending": pending}


def validate_floor_factorization_contract(lock: Mapping[str, Any]) -> dict[str, Any]:
    actual = lock.get("floor_factorization")
    if _canonical_json(actual) != _canonical_json(EXPECTED_FLOOR_FACTORIZATION):
        raise RuntimeError(
            "policy lock floor_factorization disagrees with the implemented lanes"
        )
    return {
        "status": "PASS",
        "contract_fingerprint": _fingerprint(actual),
    }


def validate_historical_evidence(lock: Mapping[str, Any]) -> dict[str, str]:
    declared = frozenset(str(name) for name in lock["historical_evidence_sha256"])
    if declared != REQUIRED_HISTORICAL_EVIDENCE_FILES:
        raise RuntimeError(
            "historical evidence key set changed: "
            + _canonical_json(
                {
                    "missing": sorted(REQUIRED_HISTORICAL_EVIDENCE_FILES - declared),
                    "extra": sorted(declared - REQUIRED_HISTORICAL_EVIDENCE_FILES),
                }
            )
        )
    actual: dict[str, str] = {}
    for name, expected_value in lock["historical_evidence_sha256"].items():
        path = _source_path(str(name))
        digest = _sha256(path)
        if digest != str(expected_value):
            raise RuntimeError(
                f"historical v0.3 evidence changed: {name} "
                f"expected={expected_value} actual={digest}"
            )
        actual[str(name)] = digest
    return actual


def validate_dev_freshness_against_v03_holdout() -> dict[str, Any]:
    old = _read_json(V03_HOLDOUT_FIXTURE_PATH)
    dev = _read_json(DEV_FIXTURE_PATH)
    if dev.get("fresh_relative_to_v0_3_holdout") is not True:
        raise RuntimeError("v0.3.1 DEV fixture lacks its explicit freshness declaration")
    old_cases = list(old["cases"])
    dev_cases = list(dev["cases"])
    overlap: dict[str, list[Any]] = {}
    for field in ("case_id", "family"):
        old_values = {case[field] for case in old_cases}
        shared = sorted({case[field] for case in dev_cases} & old_values)
        if shared:
            overlap[field] = shared
    old_observations = [
        observation
        for case in old_cases
        for observation in case["observations"]
    ]
    dev_observations = [
        observation
        for case in dev_cases
        for observation in case["observations"]
    ]
    for field in ("topic", "text", "stance", "confidence"):
        old_values = {observation[field] for observation in old_observations}
        shared = sorted(
            {observation[field] for observation in dev_observations} & old_values,
            key=str,
        )
        if shared:
            overlap[field] = shared
    if overlap:
        raise RuntimeError(
            "v0.3.1 DEV fixture overlaps the consumed v0.3 holdout: "
            + _canonical_json(overlap)
        )
    return {
        "status": "PASS",
        "case_count": len(dev_cases),
        "observation_count": len(dev_observations),
        "fields_checked": [
            "case_id",
            "family",
            "topic",
            "text",
            "stance",
            "confidence",
        ],
    }


def validate_historical_regression_copy() -> dict[str, Any]:
    regression = _load_fixture(
        REGRESSION_FIXTURE_PATH,
        expected_split="contaminated_historical_regression",
    )
    source_case_id = str(regression.get("source_case_id"))
    source_cases = [
        case
        for case in _read_json(V03_HOLDOUT_FIXTURE_PATH)["cases"]
        if str(case["case_id"]) == source_case_id
    ]
    if len(source_cases) != 1 or len(regression["cases"]) != 1:
        raise RuntimeError("historical regression source case is not unique")
    source_case = source_cases[0]
    copied_case = regression["cases"][0]
    copied_payload = {
        "case_id": copied_case["case_id"],
        "observations": copied_case["observations"],
        "config_overrides": copied_case.get("config_overrides", {}),
    }
    source_payload = {
        "case_id": source_case["case_id"],
        "observations": source_case["observations"],
        "config_overrides": source_case.get("config_overrides", {}),
    }
    if _canonical_json(copied_payload) != _canonical_json(source_payload):
        raise RuntimeError(
            "contaminated regression is not an exact input copy of its v0.3 source"
        )
    return {
        "status": "PASS",
        "source_case_id": source_case_id,
        "copied_input_fingerprint": _fingerprint(copied_payload),
    }


def capture_publication_snapshot(lock: Mapping[str, Any]) -> dict[str, Any]:
    current_lock, policy_lock_sha256 = _read_json_with_sha(LOCK_PATH)
    if _canonical_json(current_lock) != _canonical_json(lock):
        raise RuntimeError("policy lock changed before benchmark snapshot")
    return {
        "policy_lock_sha256": policy_lock_sha256,
        "runtime_lock_schema": validate_runtime_lock_schema(current_lock),
        "source_validation": validate_source_lock(current_lock),
        "historical_evidence_sha256": validate_historical_evidence(current_lock),
        "floor_factorization_contract": validate_floor_factorization_contract(
            current_lock
        ),
        "dev_freshness": validate_dev_freshness_against_v03_holdout(),
        "historical_regression_copy": validate_historical_regression_copy(),
    }


def assert_publication_snapshot_unchanged(
    snapshot: Mapping[str, Any],
) -> None:
    current_lock, policy_lock_sha256 = _read_json_with_sha(LOCK_PATH)
    if policy_lock_sha256 != snapshot["policy_lock_sha256"]:
        raise RuntimeError("policy lock changed during benchmark execution")
    current_runtime_schema = validate_runtime_lock_schema(current_lock)
    if current_runtime_schema != snapshot["runtime_lock_schema"]:
        raise RuntimeError("runtime lock schema changed during benchmark execution")
    current_sources = validate_source_lock(current_lock)
    if current_sources != snapshot["source_validation"]:
        raise RuntimeError("source graph changed during benchmark execution")
    current_historical = validate_historical_evidence(current_lock)
    if current_historical != snapshot["historical_evidence_sha256"]:
        raise RuntimeError("historical evidence changed during benchmark execution")
    current_factorization = validate_floor_factorization_contract(current_lock)
    if current_factorization != snapshot["floor_factorization_contract"]:
        raise RuntimeError("floor factorization contract changed during execution")
    current_freshness = validate_dev_freshness_against_v03_holdout()
    if current_freshness != snapshot["dev_freshness"]:
        raise RuntimeError("DEV freshness status changed during benchmark execution")
    current_regression_copy = validate_historical_regression_copy()
    if current_regression_copy != snapshot["historical_regression_copy"]:
        raise RuntimeError("historical regression copy changed during execution")


def _assert_dev_output_path_allowed(path: Path) -> Path:
    candidate = path.expanduser().resolve()
    candidate_parts = tuple(part.casefold() for part in candidate.parts)
    for reserved in (DEFAULT_FULL_OUTPUT.resolve(), DEFAULT_LEDGER.resolve()):
        reserved_parts = tuple(part.casefold() for part in reserved.parts)
        if candidate_parts[: len(reserved_parts)] == reserved_parts:
            raise RuntimeError(
                "DEV output may not occupy a canonical full path or descendant: "
                f"{candidate}"
            )
    return candidate


def _load_fixture(path: Path, *, expected_split: str) -> dict[str, Any]:
    payload = _read_json(path)
    if payload.get("schema_version") != "ebrt-dual-route-fixtures-v0.3.1":
        raise ValueError(f"unexpected fixture schema: {path}")
    if payload.get("split") != expected_split:
        raise ValueError(f"unexpected fixture split: {path}")
    if payload.get("promotion_eligible") is not False:
        raise ValueError(f"DEV/regression fixture must be non-promotional: {path}")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"fixture must contain cases: {path}")
    return payload


def _observations(case: Mapping[str, Any]) -> list[Any]:
    return [policy.frozen.Observation(**dict(item)) for item in case["observations"]]


def _config(case: Mapping[str, Any], *, model_seed: int, revision_steps: int) -> Any:
    overrides = dict(case.get("config_overrides", {}))
    reserved = sorted(RESERVED_PROTOCOL_FIELDS & overrides.keys())
    if reserved:
        raise ValueError(
            f"fixture overrides reserved protocol fields for {case['case_id']}: "
            + ",".join(reserved)
        )
    values: dict[str, Any] = {
        "seed": int(model_seed),
        "revision_steps": int(revision_steps),
        "device": "cpu",
        "dtype": "float32",
    }
    values.update(overrides)
    config = policy.frozen.EBRTConfig(**values)
    config.validate()
    return config


def _run_lane(
    case: Mapping[str, Any],
    *,
    model_seed: int,
    revision_steps: int,
    arm: str,
    execution_replay_policy: str,
    trajectory_anchor_policy: str,
    leverage_epsilon: float,
) -> tuple[Any, Any]:
    engine = policy.DualRoutePolicyReasoner(
        _config(case, model_seed=model_seed, revision_steps=revision_steps),
        arm=arm,
        case_id=str(case["case_id"]),
        probe_mode="matched",
        execution_replay_policy=execution_replay_policy,
        trajectory_anchor_policy=trajectory_anchor_policy,
        leverage_epsilon=leverage_epsilon,
    )
    result = engine.run(_observations(case))
    if len(engine.route_plans) != 1 or len(result.revisions) != 1:
        raise AssertionError(
            f"factorization fixture must produce one revision: {case['case_id']} {arm}"
        )
    return engine, result


def _event_payload(result: Any) -> list[dict[str, Any]]:
    return [dataclasses.asdict(event) for event in result.events]


def _outcome_payload(result: Any) -> dict[str, Any]:
    return {
        "events": _event_payload(result),
        "controls": result.controls.detach().cpu().tolist(),
        "final_states": result.final_states.detach().cpu().tolist(),
        "decoded": result.decoded,
    }


def _route_signature(plan: Any) -> dict[str, Any]:
    return {
        "source_step": int(plan.source_step),
        "objective_anchor_steps": list(plan.objective_anchor_steps),
        "control_steps": list(plan.control_steps),
        "candidate_steps": list(plan.candidate_steps),
        "semantic_rank": list(plan.semantic_rank),
        "leverage_rank": list(plan.leverage_rank),
    }


def _target_distance_gain(engine: Any, result: Any) -> float:
    event = result.events[0]
    topic = engine.codec.topic_vector(result.observations[event.source_step].topic)
    q = int(result.config.topic_dim)
    target = float(event.revision_target)
    before = float((result.baseline_states[-1, q : 2 * q] @ topic).item())
    after = float((result.final_states[-1, q : 2 * q] @ topic).item())
    return abs(before - target) - abs(after - target)


def _max_tensor_difference(left: torch.Tensor, right: torch.Tensor) -> float:
    return float(torch.max(torch.abs(left - right)).item())


def run_factorized_case(
    case: Mapping[str, Any],
    *,
    split: str,
    model_seed: int,
    revision_steps: int,
    arm: str,
    leverage_epsilon: float,
) -> dict[str, Any]:
    common_engine, common_result = _run_lane(
        case,
        model_seed=model_seed,
        revision_steps=revision_steps,
        arm=arm,
        execution_replay_policy="minimum_eligible_step",
        trajectory_anchor_policy="minimum_eligible_step",
        leverage_epsilon=leverage_epsilon,
    )
    cost_engine, cost_result = _run_lane(
        case,
        model_seed=model_seed,
        revision_steps=revision_steps,
        arm=arm,
        execution_replay_policy="minimum_selected_control_step",
        trajectory_anchor_policy="minimum_eligible_step",
        leverage_epsilon=leverage_epsilon,
    )
    factorial_engine, factorial_result = _run_lane(
        case,
        model_seed=model_seed,
        revision_steps=revision_steps,
        arm=arm,
        execution_replay_policy="minimum_eligible_step",
        trajectory_anchor_policy="minimum_selected_control_step",
        leverage_epsilon=leverage_epsilon,
    )
    common_plan = common_engine.route_plans[0]
    cost_plan = cost_engine.route_plans[0]
    factorial_plan = factorial_engine.route_plans[0]
    minimum_candidate_count = case.get("expected", {}).get(
        "minimum_candidate_count"
    )
    if (
        minimum_candidate_count is not None
        and len(common_plan.candidate_steps) < int(minimum_candidate_count)
    ):
        raise AssertionError(
            "fixture no longer exercises its minimum candidate count: "
            f"{case['case_id']} seed={model_seed} arm={arm}"
        )
    common_route = _route_signature(common_plan)
    if _route_signature(cost_plan) != common_route:
        raise AssertionError("cost lane changed route semantics")
    if _route_signature(factorial_plan) != common_route:
        raise AssertionError("trajectory factorial changed route semantics")
    if cost_plan.trajectory_anchor_floor != common_plan.trajectory_anchor_floor:
        raise AssertionError("cost lane changed trajectory loss support")
    if factorial_plan.execution_replay_floor != common_plan.execution_replay_floor:
        raise AssertionError("trajectory factorial changed physical replay")

    events_equal = _event_payload(common_result) == _event_payload(cost_result)
    controls_equal = torch.equal(common_result.controls, cost_result.controls)
    states_equal = torch.equal(common_result.final_states, cost_result.final_states)
    decoded_equal = common_result.decoded == cost_result.decoded
    energy_history_equal = (
        common_result.revisions[0].energy_history
        == cost_result.revisions[0].energy_history
    )
    outcome_fingerprint_equal = _fingerprint(_outcome_payload(common_result)) == _fingerprint(
        _outcome_payload(cost_result)
    )
    if not all(
        (
            events_equal,
            controls_equal,
            states_equal,
            decoded_equal,
            energy_history_equal,
            outcome_fingerprint_equal,
        )
    ):
        raise AssertionError(
            "execution replay floor changed the exact policy outcome: "
            f"{case['case_id']} seed={model_seed} arm={arm}"
        )
    if cost_plan.execution_replay_floor > 0 and not torch.equal(
        cost_result.final_states[: cost_plan.execution_replay_floor],
        cost_result.baseline_states[: cost_plan.execution_replay_floor],
    ):
        raise AssertionError("cost lane changed a state before physical replay")

    accounting_fields = (
        "actual_generator_step_calls",
        "actual_backward_calls",
        "optimizer_replay_steps",
        "online_probe_generator_step_calls",
    )
    factorial_accounting_equal = all(
        common_engine.accounting[field] == factorial_engine.accounting[field]
        for field in accounting_fields
    )
    if not factorial_accounting_equal:
        raise AssertionError("trajectory factorial changed generator/backward accounting")
    common_replay = int(common_engine.accounting["optimizer_replay_steps"])
    cost_replay = int(cost_engine.accounting["optimizer_replay_steps"])
    if cost_replay > common_replay:
        raise AssertionError("selected execution floor increased replay work")
    fixed_cost_accounting_fields = (
        "base_forward_steps",
        "prefix_recompute_steps",
        "online_probe_generator_step_calls",
        "actual_backward_calls",
        "expected_backward_calls",
    )
    if any(
        common_engine.accounting[field] != cost_engine.accounting[field]
        for field in fixed_cost_accounting_fields
    ):
        raise AssertionError("cost lane changed non-replay accounting")
    common_generator = int(common_engine.accounting["actual_generator_step_calls"])
    cost_generator = int(cost_engine.accounting["actual_generator_step_calls"])
    if common_generator - cost_generator != common_replay - cost_replay:
        raise AssertionError("generator-call saving does not equal replay-step saving")

    factorial_outcome_equal = _fingerprint(_outcome_payload(common_result)) == _fingerprint(
        _outcome_payload(factorial_result)
    )
    trajectory_floor_separated = (
        factorial_plan.trajectory_anchor_floor
        > common_plan.trajectory_anchor_floor
    )
    if not trajectory_floor_separated and not factorial_outcome_equal:
        raise AssertionError("factorial outcome changed without a loss-horizon change")
    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": str(case["case_id"]),
        "family": str(case["family"]),
        "split": split,
        "historically_contaminated": split == "contaminated_historical_regression",
        "model_seed": int(model_seed),
        "revision_steps": int(revision_steps),
        "arm": arm,
        "source_step": int(common_plan.source_step),
        "candidate_steps": list(common_plan.candidate_steps),
        "objective_anchor_steps": list(common_plan.objective_anchor_steps),
        "control_steps": list(common_plan.control_steps),
        "common_execution_replay_floor": int(common_plan.execution_replay_floor),
        "cost_execution_replay_floor": int(cost_plan.execution_replay_floor),
        "common_trajectory_anchor_floor": int(common_plan.trajectory_anchor_floor),
        "factorial_trajectory_anchor_floor": int(
            factorial_plan.trajectory_anchor_floor
        ),
        "execution_floor_separated": (
            cost_plan.execution_replay_floor > common_plan.execution_replay_floor
        ),
        "trajectory_floor_separated": trajectory_floor_separated,
        "cost_lane_events_equal": events_equal,
        "cost_lane_controls_equal": controls_equal,
        "cost_lane_final_states_equal": states_equal,
        "cost_lane_decoded_equal": decoded_equal,
        "cost_lane_energy_history_equal": energy_history_equal,
        "cost_lane_outcome_fingerprint_equal": outcome_fingerprint_equal,
        "common_optimizer_replay_steps": common_replay,
        "cost_optimizer_replay_steps": cost_replay,
        "optimizer_replay_steps_saved": common_replay - cost_replay,
        "common_generator_step_calls": common_generator,
        "cost_generator_step_calls": cost_generator,
        "generator_step_calls_saved": common_generator - cost_generator,
        "cost_lane_non_replay_accounting_equal": True,
        "factorial_accounting_equal": factorial_accounting_equal,
        "factorial_outcome_equal": factorial_outcome_equal,
        "factorial_final_state_delta_max": _max_tensor_difference(
            common_result.final_states, factorial_result.final_states
        ),
        "factorial_control_delta_max": _max_tensor_difference(
            common_result.controls, factorial_result.controls
        ),
        "factorial_decoded_equal": common_result.decoded == factorial_result.decoded,
        "common_target_distance_gain": _target_distance_gain(
            common_engine, common_result
        ),
        "factorial_target_distance_gain": _target_distance_gain(
            factorial_engine, factorial_result
        ),
    }


def _validate_historical_regression(
    row: Mapping[str, Any], case: Mapping[str, Any]
) -> None:
    expected = case["expected"]
    exact_fields = {
        "revision_steps": expected["revision_steps"],
        "source_step": expected["event_source_step"],
        "candidate_steps": expected["candidate_steps"],
        "control_steps": expected["s2_control_steps"],
        "common_execution_replay_floor": expected[
            "common_execution_replay_floor"
        ],
        "cost_execution_replay_floor": expected[
            "selected_execution_replay_floor"
        ],
        "common_trajectory_anchor_floor": expected["trajectory_anchor_floor"],
        "common_optimizer_replay_steps": expected[
            "common_optimizer_replay_steps"
        ],
        "cost_optimizer_replay_steps": expected[
            "selected_optimizer_replay_steps"
        ],
    }
    for field, value in exact_fields.items():
        if row[field] != value:
            raise AssertionError(
                f"historical regression field changed: {field} "
                f"expected={value} actual={row[field]}"
            )
    if row["cost_lane_outcome_fingerprint_equal"] is not True:
        raise AssertionError("v0.3.1 did not repair the historical cost invariant")
    if row["factorial_outcome_equal"] is not False:
        raise AssertionError(
            "trajectory-only factorial did not reproduce the v0.3 outcome divergence"
        )


def _summarize_partition(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise ValueError("summary partition must not be empty")
    savings = [float(row["optimizer_replay_steps_saved"]) for row in rows]
    separated = [row for row in rows if bool(row["execution_floor_separated"])]
    factorial_changed = [row for row in rows if not bool(row["factorial_outcome_equal"])]
    separated_changed = [
        row
        for row in rows
        if bool(row["execution_floor_separated"])
        and not bool(row["factorial_outcome_equal"])
    ]
    return {
        "lane_group_count": len(rows),
        "case_count": len({str(row["case_id"]) for row in rows}),
        "model_seed_count": len({int(row["model_seed"]) for row in rows}),
        "arm_count": len({str(row["arm"]) for row in rows}),
        "cost_lane_exact_outcome_pass_rate": statistics.fmean(
            float(bool(row["cost_lane_outcome_fingerprint_equal"])) for row in rows
        ),
        "execution_floor_separated_count": len(separated),
        "positive_replay_saving_count": sum(value > 0 for value in savings),
        "optimizer_replay_steps_saved_total": int(sum(savings)),
        "optimizer_replay_steps_saved_mean": statistics.fmean(savings),
        "optimizer_replay_steps_saved_mean_among_separated": (
            statistics.fmean(
                float(row["optimizer_replay_steps_saved"]) for row in separated
            )
            if separated
            else 0.0
        ),
        "trajectory_factorial_outcome_changed_count": len(factorial_changed),
        "trajectory_factorial_outcome_changed_fraction": (
            len(factorial_changed) / len(rows)
        ),
        "execution_floor_and_factorial_change_intersection_count": len(
            separated_changed
        ),
        "execution_floor_separated_without_factorial_change_count": (
            len(separated) - len(separated_changed)
        ),
        "factorial_change_without_execution_floor_separation_count": (
            len(factorial_changed) - len(separated_changed)
        ),
    }


def _validate_dev_case_expectations(
    rows: Sequence[Mapping[str, Any]],
    cases: Sequence[Mapping[str, Any]],
) -> None:
    for case in cases:
        case_rows = [row for row in rows if row["case_id"] == case["case_id"]]
        if not case_rows:
            raise AssertionError(f"DEV case produced no lane groups: {case['case_id']}")
        if case.get("expected", {}).get("requires_execution_floor_separation"):
            if not any(bool(row["execution_floor_separated"]) for row in case_rows):
                raise AssertionError(
                    "DEV case no longer exercises execution-floor separation: "
                    f"{case['case_id']}"
                )


def _summarize_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    fresh_dev = [row for row in rows if row["split"] == "dev"]
    contaminated = [
        row
        for row in rows
        if row["split"] == "contaminated_historical_regression"
    ]
    combined = _summarize_partition(rows)
    return {
        **combined,
        "bundle_scope": "combined_dev_and_contaminated_historical_regression",
        "fresh_dev": _summarize_partition(fresh_dev),
        "contaminated_historical_regression": _summarize_partition(contaminated),
        "historical_regression_lane_group_count": len(contaminated),
    }


def run_quick(
    lock: Mapping[str, Any],
    runtime_contract: Mapping[str, Any],
    *,
    policy_lock_sha256: str | None = None,
) -> dict[str, Any]:
    dev = _load_fixture(DEV_FIXTURE_PATH, expected_split="dev")
    regression = _load_fixture(
        REGRESSION_FIXTURE_PATH,
        expected_split="contaminated_historical_regression",
    )
    protocol = lock["dev_protocol"]
    rows: list[dict[str, Any]] = []
    for case in dev["cases"]:
        for seed in protocol["model_seeds"]:
            for arm in protocol["arms"]:
                rows.append(
                    run_factorized_case(
                        case,
                        split="dev",
                        model_seed=int(seed),
                        revision_steps=int(protocol["revision_steps"]),
                        arm=str(arm),
                        leverage_epsilon=float(protocol["leverage_epsilon"]),
                    )
                )
    _validate_dev_case_expectations(rows, dev["cases"])
    for case in regression["cases"]:
        for seed in protocol["model_seeds"]:
            for arm in protocol["historical_regression_arms"]:
                row = run_factorized_case(
                    case,
                    split="contaminated_historical_regression",
                    model_seed=int(seed),
                    revision_steps=int(
                        protocol["historical_regression_revision_steps"]
                    ),
                    arm=str(arm),
                    leverage_epsilon=float(protocol["leverage_epsilon"]),
                )
                if int(seed) == 0 and str(arm) == "S2":
                    _validate_historical_regression(row, case)
                rows.append(row)
    results = {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS",
        "mode": "quick",
        "promotion_status": "not_eligible_dev_draft",
        "policy_lock_sha256": policy_lock_sha256 or _sha256(LOCK_PATH),
        "runtime_contract": dict(runtime_contract),
        "summary": _summarize_rows(rows),
        "rows": rows,
        "epsilon_audit": run_epsilon_audit(
            lock,
            runtime_contract,
            policy_lock_sha256=policy_lock_sha256,
        ),
        "claim_boundary": list(CLAIM_BOUNDARY),
    }
    results["result_fingerprint"] = _fingerprint(results)
    return results


def _write_dev_bundle(
    output: Path,
    results: Mapping[str, Any],
    *,
    lock: Mapping[str, Any],
    publication_snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    output = _assert_dev_output_path_allowed(output)
    assert_publication_snapshot_unchanged(publication_snapshot)
    if output.exists():
        raise FileExistsError(f"DEV output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".ebrt-v031-", dir=output.parent) as tmp:
        stage = Path(tmp) / "bundle"
        stage.mkdir()
        _write_json(stage / "results.json", results)
        _write_csv(stage / "lane_rows.csv", results["rows"])
        artifacts = {
            name: {
                "bytes": (stage / name).stat().st_size,
                "sha256": _sha256(stage / name),
            }
            for name in ("results.json", "lane_rows.csv")
        }
        manifest = {
            "schema_version": "ebrt-dual-route-manifest-v0.3.1",
            "mode": "quick",
            "promotion_status": "not_eligible_dev_draft",
            "policy_lock_status": str(lock["status"]),
            "policy_lock_sha256": publication_snapshot["policy_lock_sha256"],
            "runtime_contract": results["runtime_contract"],
            "runtime_lock_schema": publication_snapshot["runtime_lock_schema"],
            "source_validation": publication_snapshot["source_validation"],
            "historical_evidence_sha256": publication_snapshot[
                "historical_evidence_sha256"
            ],
            "floor_factorization_contract": publication_snapshot[
                "floor_factorization_contract"
            ],
            "dev_freshness": publication_snapshot["dev_freshness"],
            "historical_regression_copy": publication_snapshot[
                "historical_regression_copy"
            ],
            "artifacts": artifacts,
            "bundle_fingerprint": _fingerprint(artifacts),
            "claim_boundary": list(CLAIM_BOUNDARY),
        }
        _write_json(stage / "manifest.json", manifest)
        assert_publication_snapshot_unchanged(publication_snapshot)
        stage.replace(output)
    return manifest


def _write_dev_json(
    output: Path,
    payload: Mapping[str, Any],
    *,
    publication_snapshot: Mapping[str, Any],
) -> None:
    output = _assert_dev_output_path_allowed(output)
    assert_publication_snapshot_unchanged(publication_snapshot)
    if output.exists():
        raise FileExistsError(f"DEV output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".ebrt-v031-", dir=output.parent) as tmp:
        stage = Path(tmp) / output.name
        _write_json(stage, payload)
        assert_publication_snapshot_unchanged(publication_snapshot)
        stage.replace(output)


def run_epsilon_audit(
    lock: Mapping[str, Any],
    runtime_contract: Mapping[str, Any],
    *,
    policy_lock_sha256: str | None = None,
) -> dict[str, Any]:
    case = _load_fixture(DEV_FIXTURE_PATH, expected_split="dev")["cases"][0]
    rows: list[dict[str, Any]] = []
    for epsilon in (1e-4, 1e-3, 1e-2):
        engine, _ = _run_lane(
            case,
            model_seed=0,
            revision_steps=int(lock["dev_protocol"]["revision_steps"]),
            arm="L2",
            execution_replay_policy="minimum_eligible_step",
            trajectory_anchor_policy="minimum_eligible_step",
            leverage_epsilon=epsilon,
        )
        plan = engine.route_plans[0]
        probe = engine.last_trace["dual_route_policy"]["online_probes"][0]
        rows.append(
            {
                "epsilon": epsilon,
                "leverage_rank": list(plan.leverage_rank),
                "control_steps": list(plan.control_steps),
                "finite_difference_scheme_counts": probe[
                    "finite_difference_scheme_counts"
                ],
                "probe_control_norm_max": max(
                    float(row["probe_control_norm_max"]) for row in probe["rows"]
                ),
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS",
        "mode": "epsilon-audit",
        "promotion_status": "not_eligible_dev_draft",
        "policy_lock_sha256": policy_lock_sha256 or _sha256(LOCK_PATH),
        "runtime_contract": dict(runtime_contract),
        "rows": rows,
        "exact_rank_stable": len({_canonical_json(row["leverage_rank"]) for row in rows})
        == 1,
        "claim_boundary": list(CLAIM_BOUNDARY),
    }


def _require_exact_full_runtime(runtime_contract: Mapping[str, Any]) -> None:
    if runtime_contract.get("command") != "full":
        raise RuntimeError("full writer requires a full runtime contract")
    if runtime_contract.get("exact_runtime_required") is not True:
        raise RuntimeError("full runtime contract is not exact")
    if runtime_contract.get("matched") is not True:
        raise RuntimeError("full runtime must match the policy lock exactly")
    if runtime_contract.get("promotion_eligible") is not True:
        raise RuntimeError("full runtime contract is not promotion eligible")


def _assert_full_write_authority(
    lock: Mapping[str, Any],
    supplied_runtime_contract: Mapping[str, Any],
) -> dict[str, Any]:
    current_lock = _read_json(LOCK_PATH)
    if _canonical_json(current_lock) != _canonical_json(lock):
        raise RuntimeError("policy lock changed before full writer authorization")
    validate_source_lock(current_lock)
    validate_historical_evidence(current_lock)
    validate_floor_factorization_contract(current_lock)
    validate_historical_regression_copy()
    current_runtime_contract = runtime_contract_for_command(current_lock, "full")
    if _canonical_json(current_runtime_contract) != _canonical_json(
        supplied_runtime_contract
    ):
        raise RuntimeError("supplied full runtime contract is stale or untrusted")
    _require_exact_full_runtime(current_runtime_contract)
    if (
        str(current_lock.get("status")) != "LOCKED"
        or current_lock.get("promotion_eligible") is not True
        or current_lock.get("full_enabled") is not True
        or current_lock.get("pending_promotion_inputs")
    ):
        raise RuntimeError("full writer lacks a complete LOCKED promotion authority")
    return current_runtime_contract


def _start_holdout_attempt(
    ledger_path: Path,
    lock: Mapping[str, Any],
    runtime_contract: Mapping[str, Any],
) -> None:
    _assert_full_write_authority(lock, runtime_contract)
    if ledger_path.resolve() != DEFAULT_LEDGER.resolve():
        raise RuntimeError("full holdout writer requires the canonical ledger path")
    if not ledger_path.parent.is_dir():
        raise RuntimeError("canonical ledger parent directory does not exist")
    _assert_full_write_authority(lock, runtime_contract)
    with ledger_path.open("x", encoding="utf-8") as handle:
        json.dump(
            {"schema_version": "ebrt-holdout-ledger-v0.3.1", "attempts": []},
            handle,
            sort_keys=True,
            indent=2,
        )
        handle.write("\n")


def _write_full_bundle_guard(
    output: Path,
    lock: Mapping[str, Any],
    runtime_contract: Mapping[str, Any],
) -> None:
    _assert_full_write_authority(lock, runtime_contract)
    if output.resolve() != DEFAULT_FULL_OUTPUT.resolve():
        raise RuntimeError("full bundle writer requires the canonical output path")
    if not output.parent.is_dir():
        raise RuntimeError("canonical full-output parent directory does not exist")
    _assert_full_write_authority(lock, runtime_contract)
    output.mkdir(parents=False, exist_ok=False)


def _assert_full_ready(
    lock: Mapping[str, Any],
    runtime_contract: Mapping[str, Any],
) -> None:
    _assert_full_write_authority(lock, runtime_contract)
    if DEFAULT_LEDGER.exists() or DEFAULT_FULL_OUTPUT.exists():
        raise FileExistsError("canonical v0.3.1 full ledger/output already exists")


def run_self_tests(lock: Mapping[str, Any]) -> dict[str, Any]:
    runtime_lock_schema = validate_runtime_lock_schema(lock)
    source_validation = validate_source_lock(lock)
    historical = validate_historical_evidence(lock)
    floor_factorization = validate_floor_factorization_contract(lock)
    dev_freshness = validate_dev_freshness_against_v03_holdout()
    historical_regression_copy = validate_historical_regression_copy()
    policy_self_test = policy.run_self_tests()
    exact_runtime = runtime_contract_for_command(lock, "self-test")

    sentinel_actual = dict(exact_runtime["actual_environment"])
    sentinel_actual["release"] = sentinel_actual["release"] + "-supported-drift"
    drift_assessment = assess_runtime_environment(
        lock,
        actual_environment=sentinel_actual,
    )
    if drift_assessment["matched"] or not drift_assessment["supported_cpu_runtime"]:
        raise AssertionError("supported runtime drift sentinel was not classified")
    for command in DEV_COMMANDS:
        contract = runtime_contract_for_command(
            lock,
            command,
            actual_environment=sentinel_actual,
        )
        if contract["promotion_eligible"] or contract["byte_reproducibility_claim"] != "none_cross_runtime":
            raise AssertionError(f"DEV drift contract was overclaimed: {command}")
    try:
        runtime_contract_for_command(
            lock,
            "full",
            actual_environment=sentinel_actual,
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("full accepted a supported but non-exact runtime")

    unsupported_actual = dict(exact_runtime["actual_environment"])
    unsupported_actual["python_version"] = "3.10.99"
    try:
        runtime_contract_for_command(
            lock,
            "quick",
            actual_environment=unsupported_actual,
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("DEV accepted an unsupported Python runtime")

    unsupported_torch_actual = dict(exact_runtime["actual_environment"])
    unsupported_torch_actual["torch_version"] = "3.0.0"
    try:
        runtime_contract_for_command(
            lock,
            "quick",
            actual_environment=unsupported_torch_actual,
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("DEV accepted an unsupported PyTorch major version")

    missing_pending_lock = json.loads(_canonical_json(lock))
    missing_pending_lock.pop("pending_promotion_inputs")
    try:
        runtime_contract_for_command(missing_pending_lock, "full", enforce=False)
    except RuntimeError:
        pass
    else:
        raise AssertionError("runtime accepted a missing pending-input field")

    mistyped_promotion_lock = json.loads(_canonical_json(lock))
    mistyped_promotion_lock["runtime"]["commands"]["full"][
        "promotion_eligible"
    ] = "false"
    try:
        runtime_contract_for_command(mistyped_promotion_lock, "full", enforce=False)
    except RuntimeError:
        pass
    else:
        raise AssertionError("runtime accepted a mistyped promotion boolean")

    missing_source_lock = {
        **lock,
        "source_sha256": dict(lock["source_sha256"]),
    }
    missing_source_lock["source_sha256"].pop("benchmark_dual_route_v0_3_1.py")
    try:
        validate_source_lock(missing_source_lock)
    except RuntimeError:
        pass
    else:
        raise AssertionError("source validation accepted a missing required key")

    missing_historical_lock = {
        **lock,
        "historical_evidence_sha256": dict(lock["historical_evidence_sha256"]),
    }
    missing_historical_lock["historical_evidence_sha256"].pop(
        "fixtures/dual_route_v0_3_holdout.json"
    )
    try:
        validate_historical_evidence(missing_historical_lock)
    except RuntimeError:
        pass
    else:
        raise AssertionError("historical validation accepted a missing required key")

    mismatched_factorization_lock = json.loads(_canonical_json(lock))
    mismatched_factorization_lock["floor_factorization"]["cost_lane"][
        "trajectory_anchor_policy"
    ] = "minimum_selected_control_step"
    try:
        validate_floor_factorization_contract(mismatched_factorization_lock)
    except RuntimeError:
        pass
    else:
        raise AssertionError("factorization validation accepted a changed lane")

    drift_full_contract = runtime_contract_for_command(
        lock,
        "full",
        actual_environment=sentinel_actual,
        enforce=False,
    )
    with tempfile.TemporaryDirectory(prefix="ebrt-v031-side-effect-") as tmp:
        ledger = Path(tmp) / "nested" / "ledger.json"
        output = Path(tmp) / "nested-output"
        for callback, target in (
            (_start_holdout_attempt, ledger),
            (_write_full_bundle_guard, output),
        ):
            try:
                callback(target, lock, drift_full_contract)
            except RuntimeError:
                pass
            else:
                raise AssertionError("mismatched full runtime reached a writer")
        if ledger.exists() or output.exists():
            raise AssertionError("mismatched full runtime created ledger/output")

        dev_draft_full_contract = runtime_contract_for_command(lock, "full")
        for callback, target in (
            (_start_holdout_attempt, ledger),
            (_write_full_bundle_guard, output),
        ):
            try:
                callback(target, lock, dev_draft_full_contract)
            except RuntimeError:
                pass
            else:
                raise AssertionError("DEV_DRAFT authority reached a full writer")
        if ledger.exists() or output.exists():
            raise AssertionError("DEV_DRAFT authority created ledger/output")

    for reserved in (
        DEFAULT_FULL_OUTPUT,
        DEFAULT_FULL_OUTPUT / "nested",
        DEFAULT_LEDGER,
        DEFAULT_LEDGER / "nested",
        DEFAULT_FULL_OUTPUT.with_name(DEFAULT_FULL_OUTPUT.name.upper()),
        DEFAULT_LEDGER.with_name(DEFAULT_LEDGER.name.upper()),
    ):
        try:
            _assert_dev_output_path_allowed(reserved)
        except RuntimeError:
            pass
        else:
            raise AssertionError("DEV output accepted a canonical full path")

    override_case = dict(
        _load_fixture(DEV_FIXTURE_PATH, expected_split="dev")["cases"][0]
    )
    override_case["config_overrides"] = {"seed": 999}
    try:
        _config(override_case, model_seed=0, revision_steps=8)
    except ValueError:
        pass
    else:
        raise AssertionError("fixture override replaced a protocol-controlled field")

    regression = _load_fixture(
        REGRESSION_FIXTURE_PATH,
        expected_split="contaminated_historical_regression",
    )["cases"][0]
    regression_row = run_factorized_case(
        regression,
        split="contaminated_historical_regression",
        model_seed=0,
        revision_steps=int(lock["dev_protocol"]["historical_regression_revision_steps"]),
        arm="S2",
        leverage_epsilon=float(lock["dev_protocol"]["leverage_epsilon"]),
    )
    _validate_historical_regression(regression_row, regression)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS",
        "runtime_contract": exact_runtime,
        "runtime_lock_schema": runtime_lock_schema,
        "policy_lock_sha256": _sha256(LOCK_PATH),
        "source_validation": source_validation,
        "historical_evidence_sha256": historical,
        "floor_factorization_contract": floor_factorization,
        "dev_freshness": dev_freshness,
        "historical_regression_copy": historical_regression_copy,
        "policy_self_test_status": policy_self_test["status"],
        "historical_regression": regression_row,
        "checks": [
            "factorized policy self-test",
            "exact runtime accepted for current command",
            "supported runtime drift accepted only for non-promotional DEV",
            "unsupported DEV runtime rejected",
            "unsupported PyTorch major version rejected",
            "runtime readiness fields are present and exactly typed",
            "required source and historical lock key sets are closed",
            "locked floor-factorization schema matches the implemented lanes",
            "non-exact full runtime rejected before ledger/output side effects",
            "exact runtime under DEV_DRAFT rejected before full side effects",
            "DEV outputs rejected at canonical full paths and descendants",
            "fixture overrides cannot replace protocol-controlled fields",
            "DEV identifiers, text, stance, and confidence are fresh versus v0.3 holdout",
            "contaminated regression input exactly copies its v0.3 source case",
            "historical v0.3 evidence remains byte-identical",
            "v0.3 terminal counterexample now passes the exact cost invariant",
            "trajectory-only factorial reproduces the historical divergence",
        ],
        "claim_boundary": list(CLAIM_BOUNDARY),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="EBRT v0.3.1 replay/loss factorization DEV benchmark"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("self-test")
    quick = subparsers.add_parser("quick")
    quick.add_argument("--output", type=Path, required=True)
    epsilon = subparsers.add_parser("epsilon-audit")
    epsilon.add_argument("--output", type=Path, required=True)
    subparsers.add_parser("full")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    lock = _read_json(LOCK_PATH)
    validate_runtime_lock_schema(lock)
    _configure_runtime(lock)
    if args.command == "self-test":
        payload = run_self_tests(lock)
    elif args.command == "quick":
        _assert_dev_output_path_allowed(args.output)
        runtime_contract = runtime_contract_for_command(lock, "quick")
        publication_snapshot = capture_publication_snapshot(lock)
        payload = run_quick(
            lock,
            runtime_contract,
            policy_lock_sha256=publication_snapshot["policy_lock_sha256"],
        )
        assert_publication_snapshot_unchanged(publication_snapshot)
        manifest = _write_dev_bundle(
            args.output,
            payload,
            lock=lock,
            publication_snapshot=publication_snapshot,
        )
        payload = {
            "status": payload["status"],
            "mode": payload["mode"],
            "output": str(args.output.resolve()),
            "summary": payload["summary"],
            "bundle_fingerprint": manifest["bundle_fingerprint"],
            "runtime_matched": runtime_contract["matched"],
            "promotion_status": payload["promotion_status"],
        }
    elif args.command == "epsilon-audit":
        _assert_dev_output_path_allowed(args.output)
        runtime_contract = runtime_contract_for_command(lock, "epsilon-audit")
        publication_snapshot = capture_publication_snapshot(lock)
        payload = run_epsilon_audit(
            lock,
            runtime_contract,
            policy_lock_sha256=publication_snapshot["policy_lock_sha256"],
        )
        assert_publication_snapshot_unchanged(publication_snapshot)
        _write_dev_json(
            args.output,
            payload,
            publication_snapshot=publication_snapshot,
        )
    else:
        runtime_contract = runtime_contract_for_command(lock, "full")
        validate_source_lock(lock)
        validate_historical_evidence(lock)
        _assert_full_ready(lock, runtime_contract)
        raise RuntimeError("LOCKED full matrix is not available in DEV_DRAFT")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
