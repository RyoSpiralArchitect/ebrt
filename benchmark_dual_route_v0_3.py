#!/usr/bin/env python3
"""Predeclared, capacity-matched benchmark for EBRT dual-route policy v0.3.

The benchmark has two deliberately separate views:

* decision-point shadow measurements isolate the current action on the common
  first-event prefix and suppress later revisions;
* end-to-end measurements restart every arm from zero controls and let that arm
  redetect and reroute on its own branch.

Only the end-to-end, matched-cost, single-event holdout is promotion eligible.
The structured fixture fields and evaluator targets are synthetic oracle data;
``G2`` is privileged and is never used in a promotion contrast.

Examples::

    python3 benchmark_dual_route_v0_3.py self-test
    python3 benchmark_dual_route_v0_3.py quick --output /tmp/ebrt-v03-quick
    python3 benchmark_dual_route_v0_3.py epsilon-audit --output /tmp/epsilon.json
    python3 benchmark_dual_route_v0_3.py full
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import hashlib
import importlib.util
import json
import math
import platform
import random
import statistics
import sys
import traceback
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Sequence

import torch


SCHEMA_VERSION = "ebrt-dual-route-benchmark-v0.3"
FIXTURE_SCHEMA = "ebrt-dual-route-fixtures-v0.3"
POLICY_LOCK_SCHEMA = "ebrt-dual-route-policy-lock-v0.3"
ROOT = Path(__file__).resolve().parent
DEFAULT_POLICY = ROOT / "dual_route_policy_v0_3.py"
DEFAULT_LOCK = ROOT / "policy_lock_v0_3.json"
DEFAULT_DEV = ROOT / "fixtures" / "dual_route_v0_3_dev.json"
DEFAULT_HOLDOUT = ROOT / "fixtures" / "dual_route_v0_3_holdout.json"
DEFAULT_SEQUENTIAL = ROOT / "fixtures" / "dual_route_v0_3_sequential.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "benchmark_dual_route_v0_3"
DEFAULT_LEDGER = ROOT / "artifacts" / ".dual_route_v0_3_holdout_ledger.json"
RUNNER_IMPORT_SHA256 = hashlib.sha256(Path(__file__).resolve().read_bytes()).hexdigest()

FROZEN_SOURCE_SHA256 = {
    "ebrt_monolith_v0_1.py": (
        "b1702f2868839d989cc3a9321d227436a23c3dad6cc86483edee9d5dbab3a529"
    ),
    "benchmark_ebrt_v0_1.py": (
        "3a12be0344aed424789f4681aee450068f0a7a0b015c8f0167d4b31ea9443619"
    ),
    "semantic_adapter_v0_2.py": (
        "836b7afadabb2e2e5b6ea53afe2795e529ab20193b00d83af9a5624d4f32d2ca"
    ),
    "instrumentation_ebrt_v0_2.py": (
        "663b0e446e07d8c24be228f3e5e56a6a53665bd3a637979bf285597f7d0bbb7d"
    ),
    "benchmark_instrumentation_v0_2.py": (
        "5cb0f390b5b4f9daf3df973725cb3c43c674efa81e505344e3bd05dc0123451c"
    ),
    "render_instrumentation_v0_2.py": (
        "1011835d0829e951e30f421dc14b6c04204bbcce2708e15350270e98be04f7e2"
    ),
}

ARMS = ("S2", "L2", "D2", "SR2", "G2")
ARM_IDS = {
    "S2": "S2_semantic",
    "L2": "L2_source_projection",
    "D2": "D2_dual",
    "SR2": "SR2_semantic_random",
    "G2": "G2_gold_diagnostic",
}
PRIMARY_COMPARISONS = (
    ("D2", "S2", "D2_dual_minus_S2_semantic"),
    ("D2", "SR2", "D2_dual_minus_SR2_semantic_random"),
)
CLAIM_BOUNDARY = (
    "This is a synthetic structured-oracle mechanism benchmark, not an LLM reasoning benchmark.",
    "Promotion is based only on matched-cost end-to-end holdout execution; decision shadows are local diagnostics.",
    "The structured revision target is visible to every arm and is also independently rederived by the evaluator; only annotated gold anchor identity is privileged to G2.",
    "The primary endpoint evaluates terminal distance after one to three post-event tail observations, beyond the prefix horizon optimized by the revision loss.",
    "Family-cluster intervals describe the fixed synthetic family generator and do not establish external validity.",
    "Deterministic generator-step counts are primary compute evidence; raw timing and peak-memory profiling are explicitly outside this deterministic matched bundle.",
)


@dataclasses.dataclass(frozen=True)
class FixtureCase:
    case: Any
    split: str
    evaluation_role: str


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def _stable_int(*parts: Any, modulus: int = 2**31 - 1) -> int:
    material = "|".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big") % modulus


def _runtime_environment_snapshot() -> dict[str, str]:
    return {
        "python_version": platform.python_version(),
        "torch_version": str(torch.__version__),
        "system": platform.system(),
        "machine": platform.machine(),
        "platform": platform.platform(),
        "release": platform.release(),
    }


def _validate_runtime_environment(lock: Mapping[str, Any]) -> dict[str, Any]:
    expected_raw = _config_value(lock, "runtime", "expected_environment")
    if not isinstance(expected_raw, Mapping):
        raise RuntimeError("runtime.expected_environment must be a mapping")
    expected = {str(key): str(value) for key, value in expected_raw.items()}
    actual = _runtime_environment_snapshot()
    if actual != expected:
        raise RuntimeError(
            "runtime environment disagrees with policy lock: "
            + _canonical_json(
                {
                    "expected": expected,
                    "actual": actual,
                    "mismatches": {
                        key: {"expected": expected.get(key), "actual": actual.get(key)}
                        for key in sorted(set(expected) | set(actual))
                        if expected.get(key) != actual.get(key)
                    },
                }
            )
        )
    determinism_scope = str(_config_value(lock, "runtime", "determinism_scope"))
    if determinism_scope != (
        "byte_reproducible_artifacts_require_the_same_locked_runtime_environment"
    ):
        raise RuntimeError("runtime determinism_scope is missing or changed")
    return {
        "environment": actual,
        "determinism_scope": determinism_scope,
        "matched": True,
    }


def _finite(value: Any) -> bool:
    if isinstance(value, torch.Tensor):
        return bool(torch.isfinite(value).all().item())
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, Mapping):
        return all(_finite(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return all(_finite(item) for item in value)
    return True


def _load_module(path: Path, module_name: str) -> Any:
    if not path.is_file():
        raise FileNotFoundError(path)
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load module spec: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        path.write_text("\n", encoding="utf-8")
        return
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(str(key))
                fields.append(str(key))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def _percentile(values: Sequence[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = probability * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _source_paths(policy_path: Path) -> dict[str, Path]:
    paths = {name: ROOT / name for name in FROZEN_SOURCE_SHA256}
    paths["dual_route_policy_v0_3.py"] = policy_path
    paths["benchmark_dual_route_v0_3.py"] = Path(__file__).resolve()
    paths["fixtures/dual_route_v0_3_dev.json"] = DEFAULT_DEV
    paths["fixtures/dual_route_v0_3_holdout.json"] = DEFAULT_HOLDOUT
    paths["fixtures/dual_route_v0_3_sequential.json"] = DEFAULT_SEQUENTIAL
    return paths


def _assert_frozen_sources() -> dict[str, str]:
    actual: dict[str, str] = {}
    for name, expected in FROZEN_SOURCE_SHA256.items():
        path = ROOT / name
        if not path.is_file():
            raise FileNotFoundError(path)
        digest = _sha256(path)
        actual[name] = digest
        if digest != expected:
            raise RuntimeError(
                f"frozen source SHA mismatch: {name} expected={expected} actual={digest}"
            )
    return actual


def _load_policy_lock_with_sha(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    lock = json.loads(raw.decode("utf-8"))
    if lock.get("schema_version") != POLICY_LOCK_SCHEMA:
        raise ValueError(f"unexpected policy lock schema: {lock.get('schema_version')}")
    return lock, hashlib.sha256(raw).hexdigest()


def _load_policy_lock(path: Path) -> dict[str, Any]:
    return _load_policy_lock_with_sha(path)[0]


def _snapshot_source_hashes(paths: Mapping[str, Path]) -> dict[str, str]:
    missing = sorted(name for name, path in paths.items() if not path.is_file())
    if missing:
        raise FileNotFoundError(f"source snapshot paths missing: {missing}")
    return {name: _sha256(path) for name, path in sorted(paths.items())}


def _assert_repository_snapshot_unchanged(
    *,
    policy_lock_path: Path,
    policy_lock_sha256: str,
    source_paths: Mapping[str, Path],
    source_sha256: Mapping[str, str],
    phase: str,
) -> None:
    actual_lock = _sha256(policy_lock_path)
    actual_sources = _snapshot_source_hashes(source_paths)
    if actual_lock != policy_lock_sha256 or actual_sources != dict(source_sha256):
        raise RuntimeError(
            f"repository provenance changed during {phase}: "
            + _canonical_json(
                {
                    "policy_lock": {
                        "expected": policy_lock_sha256,
                        "actual": actual_lock,
                    },
                    "source_mismatches": {
                        name: {
                            "expected": source_sha256.get(name),
                            "actual": actual_sources.get(name),
                        }
                        for name in sorted(set(source_sha256) | set(actual_sources))
                        if source_sha256.get(name) != actual_sources.get(name)
                    },
                }
            )
        )


def _locked_sha_map(lock: Mapping[str, Any]) -> dict[str, str]:
    value = lock.get("frozen_dependencies", {}).get("source_sha256", {})
    if not isinstance(value, Mapping):
        raise ValueError("policy lock frozen_dependencies.source_sha256 must be a map")
    return {str(key): str(digest) for key, digest in value.items()}


def _verify_policy_lock(
    lock: Mapping[str, Any],
    *,
    policy_path: Path,
    require_final: bool,
) -> dict[str, Any]:
    source_paths = _source_paths(policy_path)
    locked = _locked_sha_map(lock)
    required_keys = set(source_paths)
    locked_keys = set(locked)
    unlocked_required = sorted(required_keys - locked_keys)
    unexpected_locked = sorted(locked_keys - required_keys)
    actual = {
        name: _sha256(path)
        for name, path in source_paths.items()
        if name in locked and path.is_file()
    }
    pending = sorted(
        name
        for name, digest in locked.items()
        if not digest or digest.startswith("__PENDING")
    )
    absent = sorted(name for name, path in source_paths.items() if not path.is_file())
    mismatches = {
        name: {"expected": locked[name], "actual": actual.get(name)}
        for name in locked
        if name in actual
        and not locked[name].startswith("__PENDING")
        and locked[name] != actual[name]
    }
    if unlocked_required or unexpected_locked or absent or mismatches:
        raise RuntimeError(
            "policy lock source verification failed: "
            + _canonical_json(
                {
                    "unlocked_required": unlocked_required,
                    "unexpected_locked": unexpected_locked,
                    "absent": absent,
                    "mismatches": mismatches,
                }
            )
        )
    status = str(lock.get("status", ""))
    if require_final and (pending or status != "LOCKED"):
        raise RuntimeError(
            f"full holdout requires status=LOCKED and no pending hashes; status={status} pending={pending}"
        )
    return {
        "status": status,
        "pending": pending,
        "actual_sha256": actual,
        "source_keyset_exact": True,
        "verified": not pending,
    }


def _assert_canonical_full_inputs(
    command: str, *, policy_path: Path, policy_lock_path: Path
) -> None:
    """Prevent a full attempt from consuming the canonical ledger with alternates."""

    if command != "full":
        return
    if policy_path.resolve() != DEFAULT_POLICY.resolve():
        raise RuntimeError("full holdout requires the canonical v0.3 policy path")
    if policy_lock_path.resolve() != DEFAULT_LOCK.resolve():
        raise RuntimeError("full holdout requires the canonical v0.3 policy lock path")


def _config_value(lock: Mapping[str, Any], *path: str) -> Any:
    current: Any = lock
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            raise KeyError(".".join(path))
        current = current[key]
    return current


def validate_locked_protocol(
    lock: Mapping[str, Any], policy: Any, *, command: str, threads: int
) -> dict[str, Any]:
    """Fail before any holdout access when executable semantics drift from lock."""

    if command not in {"quick", "full"}:
        raise ValueError(command)
    runtime_environment = _validate_runtime_environment(lock)
    locked_threads = int(_config_value(lock, "runtime", "torch_threads"))
    if threads != locked_threads:
        raise RuntimeError(
            f"runtime threads disagree with lock: requested={threads} locked={locked_threads}"
        )
    mode = _config_value(lock, "runtime", "execution_modes", command)
    start = int(mode["model_seed_start_inclusive"])
    end = int(mode["model_seed_end_inclusive"])
    if start > end:
        raise RuntimeError("locked seed interval is empty")
    if command == "full":
        if not bool(mode["promotion_eligible"]):
            raise RuntimeError("locked full mode must be promotion eligible")
        if start != int(
            _config_value(lock, "runtime", "model_seeds", "start_inclusive")
        ) or end != int(_config_value(lock, "runtime", "model_seeds", "end_inclusive")):
            raise RuntimeError(
                "full execution-mode seeds disagree with runtime model_seeds"
            )
    elif bool(mode["promotion_eligible"]):
        raise RuntimeError("quick mode must not be promotion eligible")
    locked_arm_ids = {
        str(value["id"])
        for key, value in _config_value(lock, "arms").items()
        if key != "legacy_reference"
    }
    if locked_arm_ids != set(ARM_IDS.values()):
        raise RuntimeError(
            f"locked arm IDs disagree with runner: {sorted(locked_arm_ids)}"
        )
    if (
        tuple(getattr(policy, "ARMS", ())) != ARMS
        or dict(getattr(policy, "ARM_IDS", {})) != ARM_IDS
    ):
        raise RuntimeError("policy arm aliases or IDs disagree with benchmark")
    semantic_checks = {
        "event_threshold": (
            float(_config_value(lock, "event_and_capacity", "event_threshold")),
            0.55,
        ),
        "route_width_k": (
            int(_config_value(lock, "event_and_capacity", "route_width_k")),
            2,
        ),
        "revision_steps": (
            int(
                _config_value(lock, "event_and_capacity", "optimizer", "revision_steps")
            ),
            32,
        ),
        "revision_lr": (
            float(
                _config_value(lock, "event_and_capacity", "optimizer", "learning_rate")
            ),
            0.08,
        ),
        "leverage_epsilon": (
            float(_config_value(lock, "source_projection_leverage", "epsilon")),
            1e-3,
        ),
        "event_delta_norm_cap": (
            float(
                _config_value(
                    lock,
                    "event_and_capacity",
                    "event_delta_frobenius_norm_max",
                )
            ),
            1.75,
        ),
        "per_step_control_norm_cap": (
            float(
                _config_value(
                    lock,
                    "event_and_capacity",
                    "absolute_per_step_control_norm_max",
                )
            ),
            1.75,
        ),
        "primary_margin": (
            float(
                _config_value(
                    lock, "endpoints", "primary", "minimum_superiority_margin"
                )
            ),
            0.02,
        ),
        "bootstrap_resamples": (
            int(_config_value(lock, "statistics", "bootstrap", "resamples")),
            10_000,
        ),
    }
    drift = {
        name: {"locked": actual, "expected": expected}
        for name, (actual, expected) in semantic_checks.items()
        if actual != expected
    }
    if drift:
        raise RuntimeError(f"locked protocol semantic drift: {_canonical_json(drift)}")
    expected_contrasts = [name for _, _, name in PRIMARY_COMPARISONS]
    if (
        list(_config_value(lock, "endpoints", "primary", "co_primary_contrasts"))
        != expected_contrasts
    ):
        raise RuntimeError("locked co-primary contrasts disagree with runner")
    return {
        "command": command,
        "torch_threads": locked_threads,
        "model_seeds": list(range(start, end + 1)),
        "arm_ids": sorted(locked_arm_ids),
        "semantic_fields_verified": sorted(semantic_checks),
        "promotion_eligible": bool(mode["promotion_eligible"]),
        "runtime_environment": runtime_environment,
    }


def _load_fixture_cases(path: Path, v01: Any) -> tuple[str, list[FixtureCase]]:
    root = _read_json(path)
    if root.get("schema_version") != FIXTURE_SCHEMA:
        raise ValueError(f"unexpected fixture schema in {path}")
    split = str(root.get("split", ""))
    raw_cases = root.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError(f"fixture must contain nonempty cases: {path}")
    output: list[FixtureCase] = []
    required = {
        "case_id",
        "family",
        "evaluation_role",
        "observations",
        "config_overrides",
        "note",
    }
    for raw in raw_cases:
        if set(raw) != required:
            raise ValueError(
                f"fixture case fields must be exactly {sorted(required)}: {raw.get('case_id')}"
            )
        case = v01._make_case(
            str(raw["case_id"]),
            str(raw["family"]),
            raw["observations"],
            config_overrides=raw["config_overrides"],
            note=str(raw["note"]),
        )
        output.append(
            FixtureCase(
                case=case,
                split=split,
                evaluation_role=str(raw["evaluation_role"]),
            )
        )
    return split, output


def _eligible_steps(case: Any, event: Any) -> tuple[int, ...]:
    topic = event.topic.strip().lower()
    return tuple(
        index
        for index, observation in enumerate(case.observations[: event.source_step])
        if str(observation["topic"]).strip().lower() == topic
    )


def validate_fixtures(v01: Any, lock: Mapping[str, Any]) -> dict[str, Any]:
    dev_split, dev = _load_fixture_cases(DEFAULT_DEV, v01)
    holdout_split, holdout = _load_fixture_cases(DEFAULT_HOLDOUT, v01)
    sequential_split, sequential = _load_fixture_cases(DEFAULT_SEQUENTIAL, v01)
    if (dev_split, holdout_split, sequential_split) != ("dev", "holdout", "sequential"):
        raise AssertionError("fixture split labels must be dev, holdout, sequential")
    groups = {"dev": dev, "holdout": holdout, "sequential": sequential}
    ids_by_split = {
        split: {item.case.case_id for item in items} for split, items in groups.items()
    }
    families_by_split = {
        split: {item.case.family for item in items} for split, items in groups.items()
    }
    for left, right in (
        ("dev", "holdout"),
        ("dev", "sequential"),
        ("holdout", "sequential"),
    ):
        if ids_by_split[left] & ids_by_split[right]:
            raise AssertionError(f"case IDs overlap: {left}/{right}")
        if families_by_split[left] & families_by_split[right]:
            raise AssertionError(f"families overlap: {left}/{right}")
    all_ids = [item.case.case_id for values in groups.values() for item in values]
    if len(all_ids) != len(set(all_ids)):
        raise AssertionError("fixture case IDs must be globally unique")

    topic_dim = int(
        v01._load_monolith(ROOT / "ebrt_monolith_v0_1.py").EBRTConfig().topic_dim
    )
    expected_overrides_raw = _config_value(
        lock,
        "event_and_capacity",
        "fixture_config_overrides_by_role",
    )
    if not isinstance(expected_overrides_raw, Mapping):
        raise AssertionError(
            "event_and_capacity.fixture_config_overrides_by_role must be a mapping"
        )
    expected_roles = {
        "promotion_primary",
        "stable_guardrail",
        "sequential_stress",
    }
    if set(expected_overrides_raw) != expected_roles:
        raise AssertionError(
            "locked fixture override roles must be exactly "
            f"{sorted(expected_roles)}, got {sorted(expected_overrides_raw)}"
        )
    expected_override_keys = {"event_threshold", "top_k", "max_events"}
    expected_overrides: dict[str, dict[str, Any]] = {}
    for role, values in expected_overrides_raw.items():
        if not isinstance(values, Mapping) or set(values) != expected_override_keys:
            raise AssertionError(
                f"locked fixture overrides for {role} must have exactly "
                f"{sorted(expected_override_keys)}"
            )
        expected_overrides[str(role)] = dict(values)
    role_counts: Counter[str] = Counter()
    family_role_counts: Counter[tuple[str, str, str]] = Counter()
    eligible_counts: list[int] = []
    maximum_unique_topics = 0
    for item in [*dev, *holdout, *sequential]:
        case = item.case
        role = item.evaluation_role
        role_counts[role] += 1
        family_role_counts[(item.split, role, case.family)] += 1
        expected_case_overrides = expected_overrides.get(role)
        if expected_case_overrides is None or _canonical_json(
            case.config_overrides
        ) != _canonical_json(expected_case_overrides):
            raise AssertionError(
                f"fixture config_overrides disagree with locked role contract: "
                f"{case.case_id} role={role} "
                f"expected={_canonical_json(expected_case_overrides)} "
                f"actual={_canonical_json(case.config_overrides)}"
            )
        events = case.expected_events
        unique_topics = {
            str(observation["topic"]).strip().lower()
            for observation in case.observations
        }
        maximum_unique_topics = max(maximum_unique_topics, len(unique_topics))
        if len(unique_topics) > topic_dim:
            raise AssertionError(
                f"fixture exceeds frozen topic_dim={topic_dim}: "
                f"{case.case_id} has {len(unique_topics)} unique topics"
            )
        if role == "promotion_primary":
            if len(events) != 1:
                raise AssertionError(
                    f"primary case must have exactly one event: {case.case_id}"
                )
            eligible = _eligible_steps(case, events[0])
            if not 4 <= len(eligible) <= 6:
                raise AssertionError(
                    f"primary eligible count must be 4..6: {case.case_id} got {len(eligible)}"
                )
            eligible_counts.append(len(eligible))
            tail_count = len(case.observations) - int(events[0].source_step) - 1
            if not 1 <= tail_count <= 3:
                raise AssertionError(
                    f"primary case must have 1..3 post-event tails: {case.case_id}"
                )
        elif role == "stable_guardrail":
            if events:
                raise AssertionError(
                    f"stable case must have zero events: {case.case_id}"
                )
        elif role == "sequential_stress":
            if len(events) < 2:
                raise AssertionError(
                    f"sequential case must have >=2 events: {case.case_id}"
                )
            for event in events:
                eligible = _eligible_steps(case, event)
                if not 4 <= len(eligible) <= 8:
                    raise AssertionError(
                        f"sequential eligible count must be 4..8: "
                        f"{case.case_id}/step{event.source_step} got {len(eligible)}"
                    )
            final_tail_count = len(case.observations) - int(events[-1].source_step) - 1
            if not 1 <= final_tail_count <= 3:
                raise AssertionError(
                    f"sequential case must have 1..3 post-final-event tails: {case.case_id}"
                )
        else:
            raise AssertionError(f"unknown evaluation_role={role}")
    if role_counts != Counter(
        {"promotion_primary": 72, "stable_guardrail": 12, "sequential_stress": 16}
    ):
        raise AssertionError(f"unexpected fixture role counts: {dict(role_counts)}")
    expected_family_shapes = {
        ("dev", "promotion_primary"): (6, 4),
        ("holdout", "promotion_primary"): (12, 4),
        ("holdout", "stable_guardrail"): (3, 4),
        ("sequential", "sequential_stress"): (4, 4),
    }
    for (split, role), (
        expected_families,
        cases_per_family,
    ) in expected_family_shapes.items():
        counts = [
            count
            for (actual_split, actual_role, _), count in family_role_counts.items()
            if actual_split == split and actual_role == role
        ]
        if len(counts) != expected_families or set(counts) != {cases_per_family}:
            raise AssertionError(
                f"fixture family shape mismatch for {split}/{role}: {sorted(counts)}"
            )
    return {
        "groups": groups,
        "summary": {
            "case_counts": {name: len(values) for name, values in groups.items()},
            "family_counts": {name: len(families_by_split[name]) for name in groups},
            "role_counts": dict(sorted(role_counts.items())),
            "primary_eligible_min": min(eligible_counts),
            "primary_eligible_max": max(eligible_counts),
            "frozen_topic_dim": topic_dim,
            "maximum_unique_topics_per_case": maximum_unique_topics,
            "per_family_case_count": 4,
            "fixture_config_overrides_locked": True,
            "disjoint_case_ids": True,
            "disjoint_families": True,
        },
    }


def _configure_runtime(threads: int) -> None:
    if threads < 1:
        raise ValueError("threads must be >= 1")
    torch.set_num_threads(threads)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        if torch.get_num_interop_threads() != 1:
            raise
    torch.use_deterministic_algorithms(True)


def _policy_frozen(policy: Any) -> Any:
    for name in ("frozen", "v01", "core"):
        candidate = getattr(policy, name, None)
        if candidate is not None and hasattr(candidate, "EBRTConfig"):
            return candidate
    return _load_module(ROOT / "ebrt_monolith_v0_1.py", "ebrt_v01_for_dual_route_bench")


def _make_config(
    policy: Any, fixture: FixtureCase, model_seed: int, lock: Mapping[str, Any]
) -> Any:
    frozen = _policy_frozen(policy)
    values: dict[str, Any] = {
        "seed": int(model_seed),
        "revision_steps": int(
            _config_value(lock, "event_and_capacity", "optimizer", "revision_steps")
        ),
        "revision_lr": float(
            _config_value(lock, "event_and_capacity", "optimizer", "learning_rate")
        ),
        "top_k": int(_config_value(lock, "event_and_capacity", "route_width_k")),
        "device": str(_config_value(lock, "runtime", "device")),
        "dtype": str(_config_value(lock, "runtime", "dtype")),
    }
    values.update(fixture.case.config_overrides)
    values["top_k"] = int(_config_value(lock, "event_and_capacity", "route_width_k"))
    config = frozen.EBRTConfig(**values)
    config.validate()
    return config


def _route_seed(case_id: str, model_seed: int) -> int:
    return _stable_int(SCHEMA_VERSION, case_id, model_seed)


def _gold_steps(case: Any) -> dict[int, tuple[int, ...]]:
    return {
        int(event.source_step): tuple(event.target_steps)
        for event in case.expected_events
    }


def _to_observations(policy: Any, case: Any) -> list[Any]:
    frozen = _policy_frozen(policy)
    return [frozen.Observation.from_mapping(dict(item)) for item in case.observations]


def _projection(engine: Any, states: torch.Tensor, topic: str, step: int = -1) -> float:
    q = engine.config.topic_dim
    vector = engine.codec.topic_vector(topic).detach().cpu()
    state = states.detach().cpu()[step, q : 2 * q]
    return float((state @ vector).item())


def _decoded_metrics(case: Any, result: Any) -> dict[str, Any]:
    actual = {
        str(item["topic"]).strip().lower(): str(item["label"])
        for item in result.decoded.get("beliefs", [])
    }
    expected = case.expected_final_labels
    correct = sum(int(actual.get(topic) == label) for topic, label in expected.items())
    target_topics = sorted({event.topic for event in case.expected_events})
    target_correct = sum(
        int(actual.get(topic) == expected.get(topic)) for topic in target_topics
    )
    return {
        "correct_topic_count": correct,
        "expected_topic_count": len(expected),
        "toy_task_success": int(correct == len(expected)),
        "topic_accuracy": correct / len(expected) if expected else None,
        "target_topic_success": (
            int(target_correct == len(target_topics)) if target_topics else None
        ),
        "target_topic_accuracy": (
            target_correct / len(target_topics) if target_topics else None
        ),
    }


def _plan_dict(plan: Any) -> dict[str, Any]:
    if dataclasses.is_dataclass(plan):
        return dataclasses.asdict(plan)
    if hasattr(plan, "to_dict"):
        return dict(plan.to_dict())
    if isinstance(plan, Mapping):
        return dict(plan)
    raise TypeError(f"unsupported route plan: {type(plan).__name__}")


def _rank_steps(value: Any) -> list[int]:
    if value is None:
        return []
    output: list[int] = []
    for item in value:
        if isinstance(item, Mapping):
            step = item.get("step", item.get("candidate_step"))
        elif isinstance(item, (list, tuple)):
            step = item[0]
        else:
            step = item
        output.append(int(step))
    return output


def _event_delta_norms(trace: Mapping[str, Any]) -> list[float]:
    return [
        float(item.get("magnitudes", {}).get("control_delta_l2", 0.0))
        for item in trace.get("revision_mirrors", [])
    ]


def _terminal_metrics(fixture: FixtureCase, engine: Any, result: Any) -> dict[str, Any]:
    case = fixture.case
    expected = sorted(case.expected_events, key=lambda item: item.source_step)
    source_gains: list[float] = []
    annotated_target_control_gains: list[float] = []
    if expected:
        evaluator_event = expected[-1]
        target = float(evaluator_event.revision_target)
        topic = str(evaluator_event.topic)
        baseline_projection = _projection(engine, result.baseline_states, topic)
        final_projection = _projection(engine, result.final_states, topic)
        terminal_gain = abs(baseline_projection - target) - abs(
            final_projection - target
        )
        target_topics = {str(item.topic).strip().lower() for item in expected}
        for event in expected:
            event_topic = str(event.topic).strip().lower()
            event_target = float(event.revision_target)
            source_before = _projection(
                engine, result.baseline_states, event_topic, int(event.source_step)
            )
            source_after = _projection(
                engine, result.final_states, event_topic, int(event.source_step)
            )
            source_gains.append(
                abs(source_before - event_target) - abs(source_after - event_target)
            )
            for target_step in event.target_steps:
                target_before = _projection(
                    engine, result.baseline_states, event_topic, int(target_step)
                )
                target_after = _projection(
                    engine, result.final_states, event_topic, int(target_step)
                )
                annotated_target_control_gains.append(
                    abs(target_before - event_target) - abs(target_after - event_target)
                )
    else:
        target = None
        topic = None
        baseline_projection = None
        final_projection = None
        terminal_gain = 0.0
        target_topics = set()
    unrelated_projection_drift: list[float] = []
    for other_topic in sorted(case.expected_final_labels):
        if other_topic in target_topics:
            continue
        before = _projection(engine, result.baseline_states, other_topic)
        after = _projection(engine, result.final_states, other_topic)
        unrelated_projection_drift.append(abs(after - before))
    state_delta = (
        result.final_states.detach().cpu() - result.baseline_states.detach().cpu()
    )
    state_norms = torch.linalg.vector_norm(state_delta, dim=-1)
    unrelated_state_norms = [
        float(state_norms[index].item())
        for index, observation in enumerate(case.observations)
        if str(observation["topic"]).strip().lower() not in target_topics
    ]
    return {
        "evaluator_topic": topic,
        "evaluator_structured_revision_target": target,
        "endpoint_post_event_tail_count": (
            len(case.observations) - int(expected[-1].source_step) - 1
            if expected
            else None
        ),
        "baseline_terminal_projection": baseline_projection,
        "final_terminal_projection": final_projection,
        "terminal_target_distance_gain": float(terminal_gain),
        "source_target_distance_gain": (
            statistics.fmean(source_gains) if source_gains else None
        ),
        "annotated_target_control_distance_gain": (
            statistics.fmean(annotated_target_control_gains)
            if annotated_target_control_gains
            else None
        ),
        "unrelated_state_leakage": max(unrelated_state_norms, default=0.0),
        "unrelated_terminal_projection_drift_max": max(
            unrelated_projection_drift, default=0.0
        ),
        "state_drift_max": float(state_norms.max().item()) if len(state_norms) else 0.0,
    }


def _structural_metrics(
    fixture: FixtureCase,
    arm: str,
    result: Any,
    engine: Any,
    trace: Mapping[str, Any],
    plans: Sequence[Mapping[str, Any]],
    lock: Mapping[str, Any],
) -> dict[str, Any]:
    controls = result.controls.detach().cpu()
    control_norms = torch.linalg.vector_norm(controls, dim=-1)
    max_control = float(control_norms.max().item()) if len(control_norms) else 0.0
    selected = {int(step) for plan in plans for step in plan.get("control_steps", [])}
    nonselected = [
        float(control_norms[index].item())
        for index in range(len(control_norms))
        if index not in selected
    ]
    replay_floors = [int(plan["replay_floor"]) for plan in plans]
    pre_replay_drift = 0.0
    if replay_floors:
        floor = min(replay_floors)
        delta = (
            result.final_states.detach().cpu() - result.baseline_states.detach().cpu()
        )
        if floor > 0:
            pre_replay_drift = float(
                torch.linalg.vector_norm(delta[:floor], dim=-1).max().item()
            )
    capacity = int(_config_value(lock, "event_and_capacity", "route_width_k"))
    norm_cap = float(
        _config_value(lock, "event_and_capacity", "event_delta_frobenius_norm_max")
    )
    per_step_cap = float(
        _config_value(lock, "event_and_capacity", "absolute_per_step_control_norm_max")
    )
    delta_norms = _event_delta_norms(trace)
    probe_mode = str(getattr(engine, "probe_mode", "matched"))
    expected_probe = probe_mode == "matched" or arm in {"L2", "D2", "G2"}
    route_plans_ok = all(
        len(set(int(step) for step in plan.get("control_steps", []))) == capacity
        and int(plan.get("capacity_used", capacity)) == capacity
        and int(plan["replay_floor"])
        == min(
            int(step)
            for step in (
                plan["candidate_steps"]
                if probe_mode == "matched"
                else plan["control_steps"]
            )
        )
        and bool(plan.get("probe_performed")) == expected_probe
        for plan in plans
    )
    semantic_retained = (
        all(
            bool(_rank_steps(plan.get("semantic_rank")))
            and list(plan.get("objective_anchor_steps", []))
            == [_rank_steps(plan["semantic_rank"])[0]]
            for plan in plans
        )
        if arm == "D2" and plans
        else (True if arm != "D2" else False)
    )
    accounting = dict(getattr(engine, "accounting", {}))
    return {
        "core_unchanged": int(result.core_hash_before == result.core_hash_after),
        "finite_outputs": int(
            _finite(result.baseline_states)
            and _finite(result.final_states)
            and _finite(result.controls)
            and _finite(result.decoded)
        ),
        "max_control_norm_observed": max_control,
        "event_delta_frobenius_norm_max": max(delta_norms, default=0.0),
        "control_bound_ok": int(max_control <= per_step_cap + 1e-6),
        "event_delta_bound_ok": int(max(delta_norms, default=0.0) <= norm_cap + 1e-6),
        "non_control_step_control_norm_max": max(nonselected, default=0.0),
        "pre_replay_state_drift_max": pre_replay_drift,
        "route_plan_ok": int(route_plans_ok if plans else True),
        "matched_plan_ok": int(
            route_plans_ok if plans and probe_mode == "matched" else not plans
        ),
        "dual_semantic_objective_anchor_retained": int(semantic_retained),
        "generator_accounting_ok": int(
            bool(accounting.get("generator_accounting_ok", False))
        ),
        "backward_accounting_ok": int(
            bool(accounting.get("backward_accounting_ok", False))
        ),
    }


def run_arm(
    policy: Any,
    fixture: FixtureCase,
    arm: str,
    model_seed: int,
    lock: Mapping[str, Any],
    *,
    leverage_epsilon: float | None = None,
    probe_mode: str = "matched",
) -> tuple[
    dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]
]:
    if arm not in ARMS:
        raise ValueError(arm)
    case = fixture.case
    config = _make_config(policy, fixture, model_seed, lock)
    epsilon = float(
        leverage_epsilon
        if leverage_epsilon is not None
        else _config_value(lock, "source_projection_leverage", "epsilon")
    )
    route_seed = _route_seed(case.case_id, model_seed)
    engine = policy.DualRoutePolicyReasoner(
        config,
        arm=arm,
        case_id=case.case_id,
        probe_mode=probe_mode,
        route_seed=route_seed,
        # Annotated gold anchor identity is supplied only to the explicitly
        # privileged diagnostic arm. Evaluator gold remains benchmark-side for
        # every deployable or random comparison arm.
        gold_steps_by_source=_gold_steps(case) if arm == "G2" else {},
        route_capacity=int(_config_value(lock, "event_and_capacity", "route_width_k")),
        leverage_epsilon=epsilon,
        event_delta_norm_cap=float(
            _config_value(lock, "event_and_capacity", "event_delta_frobenius_norm_max")
        ),
        capture_deep=False,
    )
    observations = _to_observations(policy, case)
    session = engine.run_instrumented(observations, candidate_control_leverage=False)
    result = session.result
    trace = session.trace
    plans = [_plan_dict(plan) for plan in engine.route_plans]
    if arm != "G2" and any(plan.get("gold_steps") for plan in plans):
        raise AssertionError(
            f"privileged gold anchors leaked into non-G2 route plan: {arm}"
        )
    accounting = dict(engine.accounting)
    terminal = _terminal_metrics(fixture, engine, result)
    decoded = _decoded_metrics(case, result)
    structural = _structural_metrics(fixture, arm, result, engine, trace, plans, lock)
    inclusive = int(
        accounting.get("actual_generator_step_calls", result.generator_step_calls)
    )
    probe_steps = int(accounting.get("online_probe_generator_step_calls", 0))
    optimizer_replay = int(accounting.get("optimizer_replay_steps", 0))
    prefix_recompute = int(accounting.get("prefix_recompute_steps", 0))
    base_forward = int(accounting.get("base_forward_steps", 0))
    core_generator_steps = int(
        accounting.get("core_generator_steps", inclusive - probe_steps)
    )
    candidate_count_total = int(
        accounting.get(
            "candidate_count",
            sum(len(plan.get("candidate_steps", [])) for plan in plans),
        )
    )
    candidate_count_max = max(
        (len(plan.get("candidate_steps", [])) for plan in plans), default=0
    )
    replayed = sum(int(item.replayed_state_steps) for item in result.revisions)
    committed_control_norm = float(
        torch.linalg.vector_norm(result.controls.detach().cpu()).item()
    )
    run_id = f"{fixture.split}:{fixture.evaluation_role}:{case.case_id}:seed{model_seed}:{arm}:{probe_mode}"
    expected_sources = sorted(int(item.source_step) for item in case.expected_events)
    detected_sources = sorted(
        int(item.source_step) for item in [*result.events, *result.suppressed_events]
    )
    committed_sources = sorted(int(item.source_step) for item in result.events)
    event_contract_ok = (
        detected_sources == expected_sources and committed_sources == expected_sources
    )
    session_row: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "mode": "end_to_end",
        "split": fixture.split,
        "evaluation_role": fixture.evaluation_role,
        "case_id": case.case_id,
        "family": case.family,
        "model_seed": model_seed,
        "route_seed": route_seed,
        "arm": arm,
        "arm_id": ARM_IDS[arm],
        "privileged_gold_route": int(arm == "G2"),
        "probe_mode": probe_mode,
        "observation_count": len(case.observations),
        "expected_event_count": len(case.expected_events),
        "expected_event_sources": _canonical_json(expected_sources),
        "detected_event_count": len(result.events) + len(result.suppressed_events),
        "detected_event_sources": _canonical_json(detected_sources),
        "committed_event_count": len(result.events),
        "committed_event_sources": _canonical_json(committed_sources),
        "suppressed_event_count": len(result.suppressed_events),
        "event_contract_ok": int(event_contract_ok),
        "route_plan_count": len(plans),
        "candidate_count": candidate_count_total,
        "candidate_count_total": candidate_count_total,
        "candidate_count_max_per_event": candidate_count_max,
        **terminal,
        "committed_control_frobenius_norm": committed_control_norm,
        "terminal_gain_per_control_norm": (
            float(terminal["terminal_target_distance_gain"]) / committed_control_norm
            if committed_control_norm > 0.0
            else None
        ),
        **decoded,
        **structural,
        "base_forward_steps": base_forward,
        "core_generator_steps": core_generator_steps,
        "prefix_recompute_steps": prefix_recompute,
        "optimizer_replay_steps": optimizer_replay,
        "route_probe_generator_steps": probe_steps,
        "inclusive_generator_steps": inclusive,
        "optimizer_backward_calls": int(
            accounting.get("actual_backward_calls", result.backward_calls)
        ),
        "replayed_state_steps": replayed,
        "terminal_gain_per_1000_inclusive_generator_steps": (
            terminal["terminal_target_distance_gain"] * 1000.0 / inclusive
            if inclusive > 0
            else None
        ),
        "decode_call_count": int(result.decode_call_count),
        "policy_outcome_fingerprint": _fingerprint(
            {
                "events": [dataclasses.asdict(item) for item in result.events],
                "controls": result.controls.tolist(),
                "final_states": result.final_states.tolist(),
                "decoded": result.decoded,
            }
        ),
        "policy_execution_fingerprint": _fingerprint(
            {
                "events": [dataclasses.asdict(item) for item in result.events],
                "controls": result.controls.tolist(),
                "final_states": result.final_states.tolist(),
                "plans": plans,
                "accounting": {
                    key: value
                    for key, value in accounting.items()
                    if key != "algorithm_wall_time_ms"
                },
            }
        ),
    }
    event_rows: list[dict[str, Any]] = []
    for ordinal, event in enumerate(result.events):
        expected = next(
            (
                item
                for item in case.expected_events
                if item.source_step == event.source_step
            ),
            None,
        )
        plan = next(
            (item for item in plans if int(item["source_step"]) == event.source_step),
            None,
        )
        revision = result.revisions[ordinal]
        event_rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "run_id": run_id,
                "case_id": case.case_id,
                "family": case.family,
                "model_seed": model_seed,
                "arm": arm,
                "event_ordinal": ordinal,
                "source_step": int(event.source_step),
                "topic": str(case.observations[event.source_step]["topic"])
                .strip()
                .lower(),
                "event_score": float(event.score),
                "revision_target": float(event.revision_target),
                "gold_target_steps": _canonical_json(
                    list(expected.target_steps) if expected else []
                ),
                "objective_anchor_steps": _canonical_json(
                    plan.get("objective_anchor_steps", []) if plan else []
                ),
                "control_steps": _canonical_json(
                    plan.get("control_steps", []) if plan else []
                ),
                "replay_floor": int(plan["replay_floor"]) if plan else None,
                "candidate_count": len(plan.get("candidate_steps", [])) if plan else 0,
                "accepted": int(revision.accepted),
                "energy_before": float(revision.energy_before),
                "energy_after": float(revision.energy_after),
                "backward_calls": int(revision.backward_calls),
                "replayed_state_steps": int(revision.replayed_state_steps),
            }
        )
    route_rows: list[dict[str, Any]] = []
    for ordinal, plan in enumerate(plans):
        route_rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "run_id": run_id,
                "case_id": case.case_id,
                "family": case.family,
                "model_seed": model_seed,
                "arm": arm,
                "event_ordinal": ordinal,
                "source_step": int(plan["source_step"]),
                "objective_anchor_steps": _canonical_json(
                    plan.get("objective_anchor_steps", [])
                ),
                "control_steps": _canonical_json(plan.get("control_steps", [])),
                "replay_floor": int(plan["replay_floor"]),
                "replay_policy": str(plan.get("replay_policy", "")),
                "candidate_steps": _canonical_json(plan.get("candidate_steps", [])),
                "semantic_rank": _canonical_json(plan.get("semantic_rank", [])),
                "leverage_rank": _canonical_json(plan.get("leverage_rank", [])),
                "gold_steps": _canonical_json(plan.get("gold_steps", [])),
                "probe_performed": int(bool(plan.get("probe_performed"))),
                "probe_used_for_routing": int(bool(plan.get("probe_used_for_routing"))),
                "online_probe_generator_step_calls": int(
                    plan.get("online_probe_generator_step_calls", 0)
                ),
                "capacity_requested": int(plan.get("capacity_requested", 0)),
                "capacity_used": int(plan.get("capacity_used", 0)),
                "decision_state_fingerprint": str(
                    plan.get("decision_state_fingerprint", "")
                ),
                "decision_control_fingerprint": str(
                    plan.get("decision_control_fingerprint", "")
                ),
            }
        )
    shadow_rows: list[dict[str, Any]] = []
    # On single-event cases there are no earlier or later committed revisions, so
    # every arm's event-local v0.2 mirror is exactly the predeclared common-prefix
    # decision shadow. Sequential mirrors remain diagnostics but are not labelled
    # as the canonical-D shadow estimand.
    if len(case.expected_events) == 1:
        mirrors = list(trace.get("revision_mirrors", []))
        if len(mirrors) != 1 or len(plans) != 1:
            raise AssertionError(f"single-event shadow cardinality mismatch: {run_id}")
        for mirror in mirrors:
            mirror_terminal_gain = float(mirror["terminal_target_projection_gain"])
            mirror_control_norm = float(mirror["magnitudes"]["control_delta_l2"])
            if not math.isclose(
                mirror_terminal_gain,
                float(terminal["terminal_target_distance_gain"]),
                rel_tol=1e-6,
                abs_tol=1e-6,
            ):
                raise AssertionError(
                    f"decision shadow terminal gain differs from single-event end-to-end: {run_id}"
                )
            if not math.isclose(
                mirror_control_norm,
                committed_control_norm,
                rel_tol=1e-6,
                abs_tol=1e-6,
            ):
                raise AssertionError(
                    f"decision shadow controls differ from single-event end-to-end: {run_id}"
                )
            if not plans[0].get("decision_state_fingerprint") or not plans[0].get(
                "decision_control_fingerprint"
            ):
                raise AssertionError(
                    f"decision shadow prefix fingerprint missing: {run_id}"
                )
            shadow_rows.append(
                {
                    "schema_version": SCHEMA_VERSION,
                    "estimand": "decision_point_shadow",
                    "run_id": run_id,
                    "case_id": case.case_id,
                    "family": case.family,
                    "model_seed": model_seed,
                    "arm": arm,
                    "source_step": int(mirror["source_step"]),
                    "common_first_event_prefix": 1,
                    "later_revisions_suppressed": 1,
                    "terminal_target_distance_gain": terminal[
                        "terminal_target_distance_gain"
                    ],
                    "terminal_target_projection_gain": mirror_terminal_gain,
                    "source_target_projection_gain": float(
                        mirror["source_target_projection_gain"]
                    ),
                    "unrelated_state_leakage_max": float(
                        mirror["unrelated_state_leakage_max"]
                    ),
                    "event_local_control_delta_l2": mirror_control_norm,
                    "decision_state_fingerprint": str(
                        plans[0]["decision_state_fingerprint"]
                    ),
                    "decision_control_fingerprint": str(
                        plans[0]["decision_control_fingerprint"]
                    ),
                    "equals_single_event_end_to_end": 1,
                }
            )
    return session_row, event_rows, route_rows, shadow_rows


def _assert_run_integrity(row: Mapping[str, Any], *, primary: bool) -> None:
    required_ones = (
        "event_contract_ok",
        "core_unchanged",
        "finite_outputs",
        "control_bound_ok",
        "event_delta_bound_ok",
        "generator_accounting_ok",
        "backward_accounting_ok",
    )
    failures = [key for key in required_ones if int(row[key]) != 1]
    if float(row["non_control_step_control_norm_max"]) > 1e-6:
        failures.append("non_control_step_control_norm_max")
    if float(row["pre_replay_state_drift_max"]) > 1e-6:
        failures.append("pre_replay_state_drift_max")
    if primary and int(row["matched_plan_ok"]) != 1:
        failures.append("matched_plan_ok")
    if failures:
        raise AssertionError(f"run integrity failed {row['run_id']}: {failures}")


def run_matrix(
    policy: Any,
    fixtures: Sequence[FixtureCase],
    seeds: Sequence[int],
    lock: Mapping[str, Any],
    *,
    progress: bool = True,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    sessions: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    routes: list[dict[str, Any]] = []
    shadows: list[dict[str, Any]] = []
    total = len(fixtures) * len(seeds) * len(ARMS)
    completed = 0
    for fixture in sorted(fixtures, key=lambda item: item.case.case_id):
        for seed in seeds:
            arm_order = list(ARMS)
            random.Random(_stable_int("arm-order", fixture.case.case_id, seed)).shuffle(
                arm_order
            )
            paired_rows: dict[str, MutableMapping[str, Any]] = {}
            for arm in arm_order:
                session, arm_events, arm_routes, arm_shadows = run_arm(
                    policy, fixture, arm, seed, lock
                )
                _assert_run_integrity(
                    session, primary=fixture.evaluation_role == "promotion_primary"
                )
                paired_rows[arm] = session
                sessions.append(session)
                events.extend(arm_events)
                routes.extend(arm_routes)
                shadows.extend(arm_shadows)
                completed += 1
                if progress and (completed == total or completed % 100 == 0):
                    print(
                        f"dual-route progress {completed}/{total}",
                        file=sys.stderr,
                        flush=True,
                    )
            if fixture.evaluation_role in {"promotion_primary", "sequential_stress"}:
                cost_signature = {
                    arm: (
                        int(row["inclusive_generator_steps"]),
                        int(row["route_probe_generator_steps"]),
                        int(row["optimizer_backward_calls"]),
                        int(row["replayed_state_steps"]),
                        int(row["candidate_count_total"]),
                    )
                    for arm, row in paired_rows.items()
                }
                matched = len(set(cost_signature.values())) == 1
                if not matched:
                    raise AssertionError(
                        f"capacity-matched cost mismatch {fixture.case.case_id}/seed{seed}: {cost_signature}"
                    )
                for row in paired_rows.values():
                    row["matched_cost_group_ok"] = 1
                if fixture.evaluation_role == "sequential_stress":
                    for row in paired_rows.values():
                        row["common_first_event_prefix_ok"] = None
                    continue
                state_fingerprints = {
                    row["decision_state_fingerprint"]
                    for row in routes
                    if row["case_id"] == fixture.case.case_id
                    and int(row["model_seed"]) == seed
                    and int(row["event_ordinal"]) == 0
                }
                control_fingerprints = {
                    row["decision_control_fingerprint"]
                    for row in routes
                    if row["case_id"] == fixture.case.case_id
                    and int(row["model_seed"]) == seed
                    and int(row["event_ordinal"]) == 0
                }
                if len(state_fingerprints) != 1 or len(control_fingerprints) != 1:
                    raise AssertionError(
                        f"first-event decision prefix differs across arms: {fixture.case.case_id}/seed{seed}"
                    )
                for row in paired_rows.values():
                    row["common_first_event_prefix_ok"] = 1
            else:
                for row in paired_rows.values():
                    row["matched_cost_group_ok"] = None
                    row["common_first_event_prefix_ok"] = None

    def sort_key(row: Mapping[str, Any]) -> tuple[str, int, str, int]:
        return (
            str(row.get("case_id", "")),
            int(row.get("model_seed", 0)),
            str(row.get("arm", "")),
            int(row.get("event_ordinal", 0)),
        )

    return (
        sorted(sessions, key=sort_key),
        sorted(events, key=sort_key),
        sorted(routes, key=sort_key),
        sorted(shadows, key=sort_key),
    )


def run_natural_cost_frontier(
    policy: Any,
    fixtures: Sequence[FixtureCase],
    seeds: Sequence[int],
    lock: Mapping[str, Any],
    matched_sessions: Sequence[Mapping[str, Any]],
    matched_routes: Sequence[Mapping[str, Any]],
    *,
    progress: bool = True,
) -> list[dict[str, Any]]:
    """Run the separate native-cost D2/S2 frontier on primary cases only."""

    primary = [item for item in fixtures if item.evaluation_role == "promotion_primary"]
    matched = {
        (
            str(row["case_id"]),
            int(row["model_seed"]),
            str(row["arm"]),
            int(row["source_step"]),
        ): row
        for row in matched_routes
        if row["arm"] in {"D2", "S2"}
    }
    matched_outcomes = {
        (str(row["case_id"]), int(row["model_seed"]), str(row["arm"])): str(
            row["policy_outcome_fingerprint"]
        )
        for row in matched_sessions
        if row["evaluation_role"] == "promotion_primary" and row["arm"] in {"D2", "S2"}
    }
    output: list[dict[str, Any]] = []
    total = len(primary) * len(seeds) * 2
    completed = 0
    for fixture in sorted(primary, key=lambda item: item.case.case_id):
        for seed in seeds:
            for arm in ("S2", "D2"):
                session, _, routes, _ = run_arm(
                    policy,
                    fixture,
                    arm,
                    seed,
                    lock,
                    probe_mode="native",
                )
                _assert_run_integrity(session, primary=False)
                if int(session["route_plan_ok"]) != 1:
                    raise AssertionError(
                        f"native route plan invalid: {session['run_id']}"
                    )
                outcome_key = (fixture.case.case_id, seed, arm)
                if (
                    matched_outcomes.get(outcome_key)
                    != session["policy_outcome_fingerprint"]
                ):
                    raise AssertionError(
                        f"native selected-min replay changed matched outcome: {outcome_key}"
                    )
                for route in routes:
                    key = (
                        fixture.case.case_id,
                        seed,
                        arm,
                        int(route["source_step"]),
                    )
                    matched_route = matched.get(key)
                    if matched_route is None:
                        raise AssertionError(
                            f"missing matched route for native frontier: {key}"
                        )
                    for field in ("objective_anchor_steps", "control_steps"):
                        if route[field] != matched_route[field]:
                            raise AssertionError(
                                f"native mode changed route selection {key}/{field}"
                            )
                    controls = json.loads(route["control_steps"])
                    if int(route["replay_floor"]) != min(
                        int(step) for step in controls
                    ):
                        raise AssertionError(f"native replay floor mismatch: {key}")
                session["mode"] = "natural_cost_end_to_end"
                session["route_selection_matches_matched"] = 1
                session["outcome_matches_matched"] = 1
                session["native_replay_floor_policy_ok"] = 1
                output.append(session)
                completed += 1
                if progress and (completed == total or completed % 100 == 0):
                    print(
                        f"natural-cost progress {completed}/{total}",
                        file=sys.stderr,
                        flush=True,
                    )
    return sorted(
        output,
        key=lambda row: (str(row["case_id"]), int(row["model_seed"]), str(row["arm"])),
    )


def family_cluster_bootstrap(
    deltas: Mapping[str, Sequence[float]],
    family_by_case: Mapping[str, str],
    *,
    seed: int,
    resamples: int,
) -> dict[str, Any]:
    if resamples < 1:
        raise ValueError("bootstrap resamples must be >= 1")
    per_family: dict[str, list[float]] = defaultdict(list)
    for case_id, values in deltas.items():
        if values:
            per_family[family_by_case[case_id]].append(
                statistics.fmean(float(value) for value in values)
            )
    family_means = {
        family: statistics.fmean(values) for family, values in per_family.items()
    }
    families = sorted(family_means)
    if not families:
        return {
            "family_count": 0,
            "case_count": 0,
            "estimate": None,
            "ci_low": None,
            "ci_high": None,
        }
    estimate = statistics.fmean(family_means.values())
    rng = random.Random(seed)
    draws = [
        statistics.fmean(family_means[rng.choice(families)] for _ in families)
        for _ in range(resamples)
    ]
    return {
        "family_count": len(families),
        "case_count": len(deltas),
        "estimate": estimate,
        "ci_low": _percentile(draws, 0.025),
        "ci_high": _percentile(draws, 0.975),
        "family_weighting": "equal_after_within_family_case_and_seed_mean",
    }


def _paired_stat(
    rows: Sequence[Mapping[str, Any]],
    *,
    left_arm: str,
    right_arm: str,
    metric: str,
    operation: str,
    bootstrap_seed: int,
    bootstrap_resamples: int,
) -> dict[str, Any]:
    indexed = {
        (str(row["case_id"]), int(row["model_seed"]), str(row["arm"])): row
        for row in rows
    }
    family_by_case = {str(row["case_id"]): str(row["family"]) for row in rows}
    pairs = sorted({(str(row["case_id"]), int(row["model_seed"])) for row in rows})
    deltas: dict[str, list[float]] = defaultdict(list)
    for case_id, seed in pairs:
        left = indexed.get((case_id, seed, left_arm))
        right = indexed.get((case_id, seed, right_arm))
        if left is None or right is None:
            raise AssertionError(
                f"missing paired arm: {case_id}/seed{seed}/{left_arm}/{right_arm}"
            )
        lv = left.get(metric)
        rv = right.get(metric)
        if lv is None or rv is None:
            continue
        if operation == "difference":
            value = float(lv) - float(rv)
        elif operation == "ratio":
            if float(rv) <= 0.0:
                raise AssertionError(f"nonpositive ratio denominator: {metric}")
            value = float(lv) / float(rv)
        else:
            raise ValueError(operation)
        if not math.isfinite(value):
            raise AssertionError(f"nonfinite paired statistic: {metric}")
        deltas[case_id].append(value)
    result = family_cluster_bootstrap(
        deltas,
        family_by_case,
        seed=bootstrap_seed
        + _stable_int(left_arm, right_arm, metric, operation, modulus=10_000_000),
        resamples=bootstrap_resamples,
    )
    result.update(
        {
            "left_arm": left_arm,
            "right_arm": right_arm,
            "metric": metric,
            "operation": operation,
            "paired_trial_count": sum(len(values) for values in deltas.values()),
        }
    )
    return result


def build_statistics(
    sessions: Sequence[Mapping[str, Any]],
    natural_sessions: Sequence[Mapping[str, Any]],
    lock: Mapping[str, Any],
    *,
    bootstrap_resamples: int,
) -> dict[str, Any]:
    bootstrap_seed = int(_config_value(lock, "statistics", "bootstrap", "seed"))
    primary = [row for row in sessions if row["evaluation_role"] == "promotion_primary"]
    sequential = [
        row for row in sessions if row["evaluation_role"] == "sequential_stress"
    ]
    primary_contrasts: list[dict[str, Any]] = []
    for left, right, name in PRIMARY_COMPARISONS:
        stat = _paired_stat(
            primary,
            left_arm=left,
            right_arm=right,
            metric="terminal_target_distance_gain",
            operation="difference",
            bootstrap_seed=bootstrap_seed,
            bootstrap_resamples=bootstrap_resamples,
        )
        stat["comparison"] = name
        primary_contrasts.append(stat)

    def guardrail_contrasts(population: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        return {
            "D2_minus_S2_target_topic_success": _paired_stat(
                population,
                left_arm="D2",
                right_arm="S2",
                metric="target_topic_success",
                operation="difference",
                bootstrap_seed=bootstrap_seed,
                bootstrap_resamples=bootstrap_resamples,
            ),
            "D2_minus_S2_all_topic_accuracy": _paired_stat(
                population,
                left_arm="D2",
                right_arm="S2",
                metric="topic_accuracy",
                operation="difference",
                bootstrap_seed=bootstrap_seed,
                bootstrap_resamples=bootstrap_resamples,
            ),
            "D2_minus_S2_unrelated_state_leakage": _paired_stat(
                population,
                left_arm="D2",
                right_arm="S2",
                metric="unrelated_state_leakage",
                operation="difference",
                bootstrap_seed=bootstrap_seed,
                bootstrap_resamples=bootstrap_resamples,
            ),
            "D2_to_SR2_inclusive_steps_ratio": _paired_stat(
                population,
                left_arm="D2",
                right_arm="SR2",
                metric="inclusive_generator_steps",
                operation="ratio",
                bootstrap_seed=bootstrap_seed,
                bootstrap_resamples=bootstrap_resamples,
            ),
        }

    guardrails = guardrail_contrasts(primary)
    sequential_contrasts: list[dict[str, Any]] = []
    if sequential:
        for left, right, name in PRIMARY_COMPARISONS:
            stat = _paired_stat(
                sequential,
                left_arm=left,
                right_arm=right,
                metric="terminal_target_distance_gain",
                operation="difference",
                bootstrap_seed=bootstrap_seed,
                bootstrap_resamples=bootstrap_resamples,
            )
            stat["comparison"] = name
            sequential_contrasts.append(stat)
    sequential_guardrails = guardrail_contrasts(sequential) if sequential else {}
    natural_cost_frontier = _paired_stat(
        natural_sessions,
        left_arm="D2",
        right_arm="S2",
        metric="inclusive_generator_steps",
        operation="ratio",
        bootstrap_seed=bootstrap_seed,
        bootstrap_resamples=bootstrap_resamples,
    )
    arm_summaries: list[dict[str, Any]] = []
    for role in sorted({str(row["evaluation_role"]) for row in sessions}):
        for arm in ARMS:
            arm_rows = [
                row
                for row in sessions
                if row["evaluation_role"] == role and row["arm"] == arm
            ]
            if not arm_rows:
                continue
            arm_summaries.append(
                {
                    "evaluation_role": role,
                    "arm": arm,
                    "trial_count": len(arm_rows),
                    "terminal_target_distance_gain_mean": statistics.fmean(
                        float(row["terminal_target_distance_gain"]) for row in arm_rows
                    ),
                    "target_topic_success_mean": statistics.fmean(
                        float(row["target_topic_success"])
                        for row in arm_rows
                        if row["target_topic_success"] is not None
                    )
                    if any(row["target_topic_success"] is not None for row in arm_rows)
                    else None,
                    "topic_accuracy_mean": statistics.fmean(
                        float(row["topic_accuracy"]) for row in arm_rows
                    ),
                    "unrelated_state_leakage_mean": statistics.fmean(
                        float(row["unrelated_state_leakage"]) for row in arm_rows
                    ),
                    "inclusive_generator_steps_mean": statistics.fmean(
                        float(row["inclusive_generator_steps"]) for row in arm_rows
                    ),
                }
            )
    return {
        "bootstrap": {
            "method": "deterministic_case_family_cluster_percentile",
            "resamples": bootstrap_resamples,
            "seed": bootstrap_seed,
        },
        "arm_summaries": arm_summaries,
        "primary_contrasts": primary_contrasts,
        "guardrail_contrasts": guardrails,
        "sequential_contrasts": sequential_contrasts,
        "sequential_guardrail_contrasts": sequential_guardrails,
        "natural_cost_frontier": {
            **natural_cost_frontier,
            "estimand": "native_replay_minimum_selected_control_step",
            "quality_promotion_contrast": False,
        },
    }


def evaluate_promotion(
    sessions: Sequence[Mapping[str, Any]],
    statistics_payload: Mapping[str, Any],
    lock: Mapping[str, Any],
    *,
    promotion_eligible: bool,
) -> dict[str, Any]:
    primary = [row for row in sessions if row["evaluation_role"] == "promotion_primary"]
    stable = [row for row in sessions if row["evaluation_role"] == "stable_guardrail"]
    sequential = [
        row for row in sessions if row["evaluation_role"] == "sequential_stress"
    ]
    margin = float(
        _config_value(lock, "endpoints", "primary", "minimum_superiority_margin")
    )
    primary_checks = {
        item["comparison"]: bool(
            item["ci_low"] is not None and float(item["ci_low"]) > margin
        )
        for item in statistics_payload["primary_contrasts"]
    }
    guard_stats = statistics_payload["guardrail_contrasts"]
    guard_checks = {
        "target_topic_noninferiority": float(
            guard_stats["D2_minus_S2_target_topic_success"]["ci_low"]
        )
        >= float(
            _config_value(
                lock,
                "endpoints",
                "guardrails",
                "target_topic_success_difference_lower_bound_min",
            )
        ),
        "all_topic_accuracy_noninferiority": float(
            guard_stats["D2_minus_S2_all_topic_accuracy"]["ci_low"]
        )
        >= float(
            _config_value(
                lock,
                "endpoints",
                "guardrails",
                "all_topic_accuracy_difference_lower_bound_min",
            )
        ),
        "unrelated_leakage_bound": float(
            guard_stats["D2_minus_S2_unrelated_state_leakage"]["ci_high"]
        )
        <= float(
            _config_value(
                lock,
                "endpoints",
                "guardrails",
                "unrelated_state_leakage_difference_upper_bound_max",
            )
        ),
        "matched_compute_bound": float(
            guard_stats["D2_to_SR2_inclusive_steps_ratio"]["ci_high"]
        )
        <= float(
            _config_value(
                lock,
                "endpoints",
                "compute",
                "dual_to_semantic_random_inclusive_steps_ratio_upper_bound_max",
            )
        ),
        "natural_compute_bound": float(
            statistics_payload["natural_cost_frontier"]["ci_high"]
        )
        <= float(
            _config_value(
                lock,
                "endpoints",
                "compute",
                "dual_to_semantic_natural_cost_steps_ratio_upper_bound_max",
            )
        ),
        "structural_integrity": all(
            int(row[key]) == 1
            for row in primary
            for key in (
                "event_contract_ok",
                "core_unchanged",
                "finite_outputs",
                "control_bound_ok",
                "event_delta_bound_ok",
                "generator_accounting_ok",
                "backward_accounting_ok",
                "matched_plan_ok",
                "matched_cost_group_ok",
                "common_first_event_prefix_ok",
            )
        ),
        "dual_semantic_objective_retained": all(
            int(row["dual_semantic_objective_anchor_retained"]) == 1
            for row in primary
            if row["arm"] == "D2"
        ),
        "stable_exact_zero": (
            all(
                int(row["detected_event_count"]) == 0
                and float(row["max_control_norm_observed"]) == 0.0
                and float(row["state_drift_max"]) == 0.0
                for row in stable
            )
            if stable
            else None
        ),
    }
    passed = (
        promotion_eligible
        and all(primary_checks.values())
        and all(value is True for value in guard_checks.values())
    )
    if not promotion_eligible:
        status = "not_eligible_quick"
    elif passed:
        status = "promoted_single_event_scope"
    else:
        status = "inconclusive_not_promoted"
    sequential_checks = {
        item["comparison"]: bool(
            item["ci_low"] is not None and float(item["ci_low"]) > margin
        )
        for item in statistics_payload.get("sequential_contrasts", [])
    }
    sequential_guard_stats = statistics_payload.get(
        "sequential_guardrail_contrasts", {}
    )
    sequential_guardrail_checks = (
        {
            "target_topic_noninferiority": bool(sequential_guard_stats)
            and float(
                sequential_guard_stats["D2_minus_S2_target_topic_success"]["ci_low"]
            )
            >= float(
                _config_value(
                    lock,
                    "endpoints",
                    "guardrails",
                    "target_topic_success_difference_lower_bound_min",
                )
            ),
            "all_topic_accuracy_noninferiority": bool(sequential_guard_stats)
            and float(
                sequential_guard_stats["D2_minus_S2_all_topic_accuracy"]["ci_low"]
            )
            >= float(
                _config_value(
                    lock,
                    "endpoints",
                    "guardrails",
                    "all_topic_accuracy_difference_lower_bound_min",
                )
            ),
            "unrelated_leakage_bound": bool(sequential_guard_stats)
            and float(
                sequential_guard_stats["D2_minus_S2_unrelated_state_leakage"]["ci_high"]
            )
            <= float(
                _config_value(
                    lock,
                    "endpoints",
                    "guardrails",
                    "unrelated_state_leakage_difference_upper_bound_max",
                )
            ),
            "matched_compute_bound": bool(sequential_guard_stats)
            and float(
                sequential_guard_stats["D2_to_SR2_inclusive_steps_ratio"]["ci_high"]
            )
            <= float(
                _config_value(
                    lock,
                    "endpoints",
                    "compute",
                    "dual_to_semantic_random_inclusive_steps_ratio_upper_bound_max",
                )
            ),
        }
        if sequential
        else {}
    )
    sequential_structural = bool(sequential) and all(
        int(row[key]) == 1
        for row in sequential
        for key in (
            "event_contract_ok",
            "core_unchanged",
            "finite_outputs",
            "control_bound_ok",
            "event_delta_bound_ok",
            "generator_accounting_ok",
            "backward_accounting_ok",
            "matched_plan_ok",
            "matched_cost_group_ok",
        )
    )
    sequential_supported = (
        passed
        and sequential_structural
        and bool(sequential_checks)
        and all(sequential_checks.values())
        and all(sequential_guardrail_checks.values())
    )
    if not sequential:
        multi_event_claim_status = "not_evaluated_no_sequential_policy_runs"
    elif sequential_supported:
        multi_event_claim_status = "supported"
    else:
        multi_event_claim_status = "not_supported_scope_remains_single_event"
    return {
        "status": status,
        "promotion_eligible": promotion_eligible,
        "co_primary_rule": "intersection_union_both_contrasts_must_pass",
        "minimum_superiority_margin": margin,
        "primary_checks": primary_checks,
        "guardrail_checks": guard_checks,
        "single_event_promotion_passed": passed,
        "sequential_checks": sequential_checks,
        "sequential_guardrail_checks": sequential_guardrail_checks,
        "sequential_structural_integrity": sequential_structural,
        "multi_event_claim_status": multi_event_claim_status,
    }


def run_regression_checks(v01: Any, policy: Any) -> dict[str, Any]:
    cases = v01.build_correctness_cases()
    if len(cases) != 48:
        raise AssertionError("frozen regression suite must contain 48 cases")
    for case in cases:
        independently = v01._derive_expected_events(case.observations)
        if independently != case.expected_events:
            raise AssertionError(f"v0.1 event-label regression failed: {case.case_id}")
    v01_self = v01.run_self_tests(ROOT / "ebrt_monolith_v0_1.py")
    policy_self = policy.run_self_tests() if hasattr(policy, "run_self_tests") else None
    return {
        "frozen_correctness_case_count": len(cases),
        "frozen_family_counts": dict(
            sorted(Counter(case.family for case in cases).items())
        ),
        "event_oracle_labels_rederived": True,
        "v0_1_self_tests": v01_self,
        "dual_route_policy_self_tests": policy_self,
        "promotion_use": "none_regression_and_mechanics_only",
    }


def render_report(results: Mapping[str, Any]) -> str:
    promotion = results["promotion_decision"]
    lines = [
        "# EBRT dual-route v0.3 matched benchmark",
        "",
        f"- Mode: `{results['mode']}`",
        f"- Promotion status: **{promotion['status']}**",
        f"- Sessions: {results['counts']['session_rows']}",
        f"- Decision shadows: {results['counts']['decision_shadow_rows']}",
        f"- Bootstrap resamples: {results['statistics']['bootstrap']['resamples']}",
        "",
        "## Co-primary end-to-end contrasts",
        "",
        "The estimate is left minus right terminal target-distance gain. Promotion requires the family-cluster 95% CI lower bound to exceed +0.02 for both contrasts.",
        "",
        "| Contrast | Estimate | 95% CI | Pass |",
        "|---|---:|---:|:---:|",
    ]
    for item in results["statistics"]["primary_contrasts"]:
        passed = promotion["primary_checks"][item["comparison"]]
        lines.append(
            f"| {item['comparison']} | {item['estimate']:.6f} | [{item['ci_low']:.6f}, {item['ci_high']:.6f}] | {'yes' if passed else 'no'} |"
        )
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
        ]
    )
    for name, passed in promotion["guardrail_checks"].items():
        status = "not evaluated" if passed is None else "pass" if passed else "fail"
        lines.append(f"- `{name}`: {status}")
    natural = results["statistics"]["natural_cost_frontier"]
    lines.append(
        "- Native-cost D2/S2 inclusive-step ratio: "
        f"{natural['estimate']:.6f} "
        f"(95% CI [{natural['ci_low']:.6f}, {natural['ci_high']:.6f}])"
    )
    lines.extend(
        [
            "",
            "## Estimand separation",
            "",
            "`decision_shadow.csv` contains first-event, current-action-only diagnostics. These share a zero-control prefix on the single-event population and suppress later revisions. They are not policy-value estimates.",
            "",
            "`end_to_end_sessions.csv` restarts every arm from zero controls and recomputes each branch. Only this matched-cost holdout estimand can promote D2.",
            "",
            "`natural_cost_sessions.csv` is a separate secondary frontier: D2 probes and each arm replays from its minimum selected control step. Its compute bound is a guardrail, never a quality contrast.",
            "",
            f"Sequential stress: **{promotion['multi_event_claim_status']}**. It is never pooled with the single-event primary population.",
            "",
            "G2 alone receives annotated gold anchor identity and is a privileged diagnostic only. It is excluded from every promotion decision.",
            "",
            "## Claim boundary",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in results["claim_boundary"])
    lines.append("")
    return "\n".join(lines)


def _artifact_record(path: Path) -> dict[str, Any]:
    return {"file": path.name, "bytes": path.stat().st_size, "sha256": _sha256(path)}


def write_bundle(
    output: Path,
    *,
    sessions: Sequence[Mapping[str, Any]],
    natural_sessions: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    routes: Sequence[Mapping[str, Any]],
    shadows: Sequence[Mapping[str, Any]],
    results: Mapping[str, Any],
    sources: Mapping[str, str],
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=False)
    _write_csv(output / "decision_shadow.csv", shadows)
    _write_csv(output / "end_to_end_sessions.csv", sessions)
    _write_csv(output / "natural_cost_sessions.csv", natural_sessions)
    _write_csv(output / "end_to_end_events.csv", events)
    _write_csv(output / "route_plans.csv", routes)
    _write_json(output / "results.json", results)
    (output / "benchmark_report.md").write_text(
        render_report(results), encoding="utf-8"
    )
    artifact_names = (
        "decision_shadow.csv",
        "end_to_end_sessions.csv",
        "natural_cost_sessions.csv",
        "end_to_end_events.csv",
        "route_plans.csv",
        "results.json",
        "benchmark_report.md",
    )
    records = [_artifact_record(output / name) for name in artifact_names]
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "deterministic_bundle": True,
        "deterministic_bundle_scope": results["determinism_scope"],
        "runtime_snapshot": results["runtime_snapshot"],
        "raw_timing_included": False,
        "source_sha256": dict(sorted(sources.items())),
        "artifacts": records,
        "artifact_fingerprint": _fingerprint(records),
        "claim_boundary": list(CLAIM_BOUNDARY),
    }
    _write_json(output / "manifest.json", manifest)
    return manifest


def _protocol_fingerprint(
    lock: Mapping[str, Any], actual_sources: Mapping[str, str]
) -> str:
    return _fingerprint(
        {
            "policy_lock": lock,
            "actual_sources_including_runner": dict(sorted(actual_sources.items())),
        }
    )


def _start_holdout_attempt(
    ledger_path: Path,
    *,
    protocol_fingerprint: str,
    benchmark_sha256: str,
) -> tuple[dict[str, Any], int]:
    ledger = {"schema_version": "ebrt-holdout-ledger-v0.3", "attempts": []}
    attempts = ledger["attempts"]
    attempt = {
        "attempt": len(attempts) + 1,
        "status": "running",
        "protocol_fingerprint": protocol_fingerprint,
        "benchmark_sha256": benchmark_sha256,
        "rerun_permitted": False,
    }
    attempts.append(attempt)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with ledger_path.open("x", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    ledger,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                    allow_nan=False,
                )
                + "\n"
            )
    except FileExistsError as exc:
        raise RuntimeError(
            "the canonical v0.3 holdout ledger already exists; completed, failed, "
            "interrupted, or concurrent attempts are terminal and require a new "
            "policy/holdout version"
        ) from exc
    return ledger, len(attempts) - 1


def _finish_holdout_attempt(
    ledger_path: Path,
    ledger: MutableMapping[str, Any],
    index: int,
    *,
    status: str,
    detail: Mapping[str, Any],
) -> None:
    attempt = ledger["attempts"][index]
    attempt["status"] = status
    attempt.update(detail)
    _write_json(ledger_path, ledger)


def run_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    _assert_canonical_full_inputs(
        args.command,
        policy_path=args.policy,
        policy_lock_path=args.policy_lock,
    )
    _configure_runtime(args.threads)
    lock, lock_sha_snapshot = _load_policy_lock_with_sha(args.policy_lock)
    source_paths = _source_paths(args.policy)
    source_sha_snapshot = _snapshot_source_hashes(source_paths)
    if source_sha_snapshot["benchmark_dual_route_v0_3.py"] != RUNNER_IMPORT_SHA256:
        raise RuntimeError(
            "benchmark source changed after module import and before benchmark start"
        )
    frozen_sources = _assert_frozen_sources()
    v01 = _load_module(ROOT / "benchmark_ebrt_v0_1.py", "ebrt_v01_benchmark_for_v03")
    policy = _load_module(args.policy, "ebrt_dual_route_policy_for_bench")
    _assert_repository_snapshot_unchanged(
        policy_lock_path=args.policy_lock,
        policy_lock_sha256=lock_sha_snapshot,
        source_paths=source_paths,
        source_sha256=source_sha_snapshot,
        phase="module loading",
    )
    lock_verification = _verify_policy_lock(
        lock,
        policy_path=args.policy,
        require_final=args.command == "full",
    )
    locked_protocol = validate_locked_protocol(
        lock, policy, command=args.command, threads=args.threads
    )
    fixture_payload = validate_fixtures(v01, lock)
    regression = run_regression_checks(v01, policy)
    mode = args.command
    seeds = list(locked_protocol["model_seeds"])
    if mode == "quick":
        fixtures = list(fixture_payload["groups"]["dev"])
        if any(item.evaluation_role != "promotion_primary" for item in fixtures):
            raise AssertionError("quick mode must contain DEV primary fixtures only")
    else:
        fixtures = [
            *fixture_payload["groups"]["holdout"],
            *fixture_payload["groups"]["sequential"],
        ]
    actual_sources = dict(source_sha_snapshot)
    actual_sources.update(frozen_sources)
    ledger: dict[str, Any] | None = None
    ledger_index: int | None = None
    protocol_fp: str | None = None
    if mode == "full":
        if args.output.exists():
            raise FileExistsError(f"one-shot output already exists: {args.output}")
        protocol_fp = _protocol_fingerprint(lock, actual_sources)
        ledger, ledger_index = _start_holdout_attempt(
            DEFAULT_LEDGER,
            protocol_fingerprint=protocol_fp,
            benchmark_sha256=_sha256(Path(__file__).resolve()),
        )
    try:
        sessions, events, routes, shadows = run_matrix(
            policy, fixtures, seeds, lock, progress=not args.no_progress
        )
        if mode == "quick" and any(
            row["evaluation_role"] == "sequential_stress" for row in sessions
        ):
            raise AssertionError("quick mode executed a sequential fixture")
        natural_sessions = run_natural_cost_frontier(
            policy,
            fixtures,
            seeds,
            lock,
            sessions,
            routes,
            progress=not args.no_progress,
        )
        resamples = int(
            _config_value(lock, "statistics", "bootstrap", "resamples")
            if mode == "full"
            else args.quick_bootstrap_resamples
        )
        statistics_payload = build_statistics(
            sessions,
            natural_sessions,
            lock,
            bootstrap_resamples=resamples,
        )
        promotion = evaluate_promotion(
            sessions,
            statistics_payload,
            lock,
            promotion_eligible=mode == "full",
        )
        results: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "mode": mode,
            "promotion_eligible": mode == "full",
            "probe_mode": "matched",
            "execution_scope": (
                "dev_primary_only_no_sequential_policy_runs"
                if mode == "quick"
                else "holdout_primary_stable_and_unseen_sequential"
            ),
            "model_seeds": seeds,
            "policy_lock_sha256": lock_sha_snapshot,
            "policy_lock_verification": lock_verification,
            "locked_protocol_validation": locked_protocol,
            "runtime_snapshot": locked_protocol["runtime_environment"]["environment"],
            "determinism_scope": locked_protocol["runtime_environment"][
                "determinism_scope"
            ],
            "holdout_attempt": (
                {
                    "attempt": int(ledger_index) + 1,
                    "canonical_ledger": str(DEFAULT_LEDGER.relative_to(ROOT)),
                    "protocol_fingerprint": protocol_fp,
                    "rerun_permitted": False,
                    "status_at_bundle_creation": "running",
                }
                if mode == "full" and ledger_index is not None
                else None
            ),
            "fixture_validation": fixture_payload["summary"],
            "regression_and_mechanics": regression,
            "counts": {
                "session_rows": len(sessions),
                "natural_cost_session_rows": len(natural_sessions),
                "event_rows": len(events),
                "route_plan_rows": len(routes),
                "decision_shadow_rows": len(shadows),
            },
            "statistics": statistics_payload,
            "promotion_decision": promotion,
            "gold_diagnostic_policy": "privileged_excluded_from_promotion",
            "timing_policy": "raw_wall_time_and_peak_memory_are_not_in_the_deterministic_bundle",
            "claim_boundary": list(CLAIM_BOUNDARY),
        }
        _assert_repository_snapshot_unchanged(
            policy_lock_path=args.policy_lock,
            policy_lock_sha256=lock_sha_snapshot,
            source_paths=source_paths,
            source_sha256=source_sha_snapshot,
            phase="pre-bundle verification",
        )
        manifest = write_bundle(
            args.output,
            sessions=sessions,
            natural_sessions=natural_sessions,
            events=events,
            routes=routes,
            shadows=shadows,
            results=results,
            sources=actual_sources,
        )
        _assert_repository_snapshot_unchanged(
            policy_lock_path=args.policy_lock,
            policy_lock_sha256=lock_sha_snapshot,
            source_paths=source_paths,
            source_sha256=source_sha_snapshot,
            phase="post-bundle verification",
        )
        if mode == "full" and ledger is not None and ledger_index is not None:
            _assert_repository_snapshot_unchanged(
                policy_lock_path=args.policy_lock,
                policy_lock_sha256=lock_sha_snapshot,
                source_paths=source_paths,
                source_sha256=source_sha_snapshot,
                phase="pre-ledger-completion verification",
            )
            _finish_holdout_attempt(
                DEFAULT_LEDGER,
                ledger,
                ledger_index,
                status="completed",
                detail={
                    "artifact_fingerprint": manifest["artifact_fingerprint"],
                    "promotion_status": promotion["status"],
                },
            )
        return {
            "mode": mode,
            "output": str(args.output),
            "promotion_status": promotion["status"],
            "artifact_fingerprint": manifest["artifact_fingerprint"],
            "counts": results["counts"],
        }
    except BaseException as exc:
        if mode == "full" and ledger is not None and ledger_index is not None:
            _finish_holdout_attempt(
                DEFAULT_LEDGER,
                ledger,
                ledger_index,
                status="failed_terminal_new_policy_version_required",
                detail={
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "traceback_fingerprint": _fingerprint(traceback.format_exc()),
                    "rerun_permitted": False,
                    "failure_note": (
                        "The ledger does not store outcome rows, but any started "
                        "attempt is terminal even if failure occurred during bundle writing."
                    ),
                },
            )
        raise


def run_epsilon_audit(args: argparse.Namespace) -> dict[str, Any]:
    _configure_runtime(args.threads)
    _assert_frozen_sources()
    v01 = _load_module(ROOT / "benchmark_ebrt_v0_1.py", "ebrt_v01_epsilon_audit")
    policy = _load_module(args.policy, "ebrt_dual_route_policy_epsilon_audit")
    lock = _load_policy_lock(args.policy_lock)
    fixtures = validate_fixtures(v01, lock)["groups"]["dev"]
    epsilons = (1e-4, 1e-3, 1e-2)
    rows: list[dict[str, Any]] = []
    for fixture in fixtures:
        for epsilon in epsilons:
            _, _, routes, _ = run_arm(
                policy,
                fixture,
                "D2",
                0,
                lock,
                leverage_epsilon=epsilon,
            )
            for route in routes:
                rows.append(
                    {
                        "case_id": fixture.case.case_id,
                        "family": fixture.case.family,
                        "source_step": route["source_step"],
                        "epsilon": epsilon,
                        "leverage_rank": json.loads(route["leverage_rank"]),
                        "control_steps": json.loads(route["control_steps"]),
                    }
                )
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["case_id"], int(row["source_step"]))].append(row)
    exact = 0
    top2 = 0
    for values in grouped.values():
        ranks = [tuple(_rank_steps(item["leverage_rank"])) for item in values]
        exact += int(len(set(ranks)) == 1)
        top2 += int(len({tuple(rank[:2]) for rank in ranks}) == 1)
    result = {
        "schema_version": SCHEMA_VERSION,
        "audit": "source_projection_leverage_epsilon_rank_stability",
        "epsilons": list(epsilons),
        "decision_count": len(grouped),
        "exact_full_rank_rate": exact / len(grouped) if grouped else None,
        "exact_top2_rank_rate": top2 / len(grouped) if grouped else None,
        "rows": rows,
        "promotion_use": "development_diagnostic_only",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise FileExistsError(args.output)
    _write_json(args.output, result)
    return {key: value for key, value in result.items() if key != "rows"}


def run_self_tests(args: argparse.Namespace) -> dict[str, Any]:
    _configure_runtime(args.threads)
    lock, lock_sha_snapshot = _load_policy_lock_with_sha(args.policy_lock)
    runtime_environment = _validate_runtime_environment(lock)
    source_paths = _source_paths(args.policy)
    source_sha_snapshot = _snapshot_source_hashes(source_paths)
    if source_sha_snapshot["benchmark_dual_route_v0_3.py"] != RUNNER_IMPORT_SHA256:
        raise AssertionError("self-test runner changed after import")
    frozen = _assert_frozen_sources()
    v01 = _load_module(ROOT / "benchmark_ebrt_v0_1.py", "ebrt_v01_v03_selftest")
    policy = _load_module(args.policy, "ebrt_dual_route_policy_v03_selftest")
    _assert_repository_snapshot_unchanged(
        policy_lock_path=args.policy_lock,
        policy_lock_sha256=lock_sha_snapshot,
        source_paths=source_paths,
        source_sha256=source_sha_snapshot,
        phase="self-test",
    )
    fixtures = validate_fixtures(v01, lock)
    regression = run_regression_checks(v01, policy)
    bootstrap = family_cluster_bootstrap(
        {"a0": [1.0, 1.0], "a1": [3.0], "b0": [-2.0]},
        {"a0": "a", "a1": "a", "b0": "b"},
        seed=7,
        resamples=100,
    )
    if not math.isclose(float(bootstrap["estimate"]), 0.0):
        raise AssertionError(f"family-equal bootstrap helper failed: {bootstrap}")
    dev_case = fixtures["groups"]["dev"][0]
    rows: list[dict[str, Any]] = []
    fingerprints: dict[str, str] = {}
    for arm in ARMS:
        row, _, _, shadows = run_arm(policy, dev_case, arm, 0, lock)
        _assert_run_integrity(row, primary=True)
        if len(shadows) != 1:
            raise AssertionError("single-event run must yield one decision shadow")
        rows.append(row)
        fingerprints[arm] = str(row["policy_execution_fingerprint"])
    if len({int(row["inclusive_generator_steps"]) for row in rows}) != 1:
        raise AssertionError("matched self-test arms have unequal inclusive cost")
    repeated, _, _, _ = run_arm(policy, dev_case, "D2", 0, lock)
    if repeated["policy_execution_fingerprint"] != fingerprints["D2"]:
        raise AssertionError("D2 execution is not deterministic")
    parser = build_parser()
    subparsers_action = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    full_parser = subparsers_action.choices["full"]
    if any(action.dest == "ledger" for action in full_parser._actions):
        raise AssertionError("full CLI must not expose a holdout-ledger override")
    _assert_canonical_full_inputs(
        "full", policy_path=DEFAULT_POLICY, policy_lock_path=DEFAULT_LOCK
    )
    for alternate_policy, alternate_lock in (
        (ROOT / "alternate_policy.py", DEFAULT_LOCK),
        (DEFAULT_POLICY, ROOT / "alternate_lock.json"),
    ):
        try:
            _assert_canonical_full_inputs(
                "full",
                policy_path=alternate_policy,
                policy_lock_path=alternate_lock,
            )
        except RuntimeError:
            pass
        else:
            raise AssertionError("full CLI accepted a non-canonical policy or lock")
    return {
        "schema_version": SCHEMA_VERSION,
        "frozen_source_count": len(frozen),
        "fixture_validation": fixtures["summary"],
        "regression_case_count": regression["frozen_correctness_case_count"],
        "policy_arms": list(getattr(policy, "ARMS", ())),
        "matched_arm_cost": rows[0]["inclusive_generator_steps"],
        "deterministic_repeat": True,
        "family_bootstrap_helper": "pass",
        "canonical_holdout_ledger_bound": True,
        "canonical_full_policy_and_lock_bound": True,
        "repository_snapshot_guard": "pass",
        "runtime_environment": runtime_environment,
        "status": "pass",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    common.add_argument("--policy-lock", type=Path, default=DEFAULT_LOCK)
    common.add_argument("--threads", type=int, default=1)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("self-test", parents=[common])
    quick = subparsers.add_parser("quick", parents=[common])
    quick.add_argument("--output", type=Path, required=True)
    quick.add_argument("--quick-bootstrap-resamples", type=int, default=500)
    quick.add_argument("--no-progress", action="store_true")
    full = subparsers.add_parser("full", parents=[common])
    full.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    full.add_argument("--no-progress", action="store_true")
    epsilon = subparsers.add_parser("epsilon-audit", parents=[common])
    epsilon.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "self-test":
        payload = run_self_tests(args)
    elif args.command == "epsilon-audit":
        payload = run_epsilon_audit(args)
    else:
        payload = run_benchmark(args)
    print(
        json.dumps(
            payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
