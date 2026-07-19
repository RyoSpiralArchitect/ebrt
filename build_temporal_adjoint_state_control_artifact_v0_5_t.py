#!/usr/bin/env python3
"""Build and validate the locked EBRT v0.5-T mechanism artifact bundle."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import platform
import shutil
import socket
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence
from unittest import mock

import torch

from benchmark_temporal_adjoint_state_control_v0_5_t import (
    BENCHMARK_NAME,
    BENCHMARK_VERSION,
    COLLAPSED_GRADIENT_ABS_TOLERANCE,
    EXPECTED_EARLY_TOP_CONTROL,
    EXPECTED_EARLY_TOP_FLOOR_ORDINAL,
    EXPECTED_LATE_TOP_CONTROL,
    EXPECTED_LATE_TOP_FLOOR_ORDINAL,
    MIN_AGGREGATE_RELATIVE_REDUCTION_VS_B,
    MIN_C_WIN_FRACTION_VS_B,
    MIN_C_WIN_FRACTION_VS_D,
    MIN_ORDER_SWITCH_FRACTION,
    MIN_TOP_LEVERAGE_MARGIN,
    SHAM_NORM_ABS_TOLERANCE,
    TemporalControlBenchmark,
    run_self_tests as run_benchmark_self_tests,
)
from temporal_adjoint_state_controller_v0_5_t import (
    CONTROLLER_NAME,
    CONTROLLER_VERSION,
    ControllerConfig,
    TemporalAdjointStateController,
    TemporalPairedSuite,
    _load_json_exact,
    run_self_tests as run_controller_self_tests,
)


ROOT = Path(__file__).resolve().parent
LOCK_PATH = ROOT / "policy_lock_temporal_adjoint_state_controller_v0_5_t.json"
ARTIFACT_DIRECTORY = "artifacts/temporal_adjoint_state_control_v0_5_t"
ARTIFACT_FILES = (
    "representative_early_execution_control_map.json",
    "representative_early_temporal_adjoint_audit.json",
    "representative_late_execution_control_map.json",
    "representative_late_temporal_adjoint_audit.json",
    "no_event_execution_control_map.json",
    "no_event_temporal_adjoint_audit.json",
    "arm_comparison.json",
    "self_test.json",
    "mechanism_report.md",
    "manifest.json",
)
MANIFEST_SCHEMA_VERSION = "ebrt-temporal-state-control-manifest-v0.5-t.0"
SELF_TEST_SCHEMA_VERSION = "ebrt-temporal-state-control-self-test-v0.5-t.0"


class ArtifactValidationError(ValueError):
    """Raised when a lock or built artifact violates the exact contract."""


def _canonical_json_bytes(value: Any, *, trailing_newline: bool = False) -> bytes:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return encoded + (b"\n" if trailing_newline else b"")


def _pretty_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_bytes(_canonical_json_bytes(value))


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _observed_runtime() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "pytorch": torch.__version__,
        "operating_system": platform.system(),
        "operating_system_release": platform.release(),
        "machine": platform.machine(),
    }


def _exact_mapping(value: Any, label: str, expected: set[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ArtifactValidationError(f"{label}: expected object")
    actual = set(value)
    unknown = sorted(actual - expected)
    missing = sorted(expected - actual)
    if unknown or missing:
        raise ArtifactValidationError(
            f"{label}: unknown={unknown or 'none'} missing={missing or 'none'}"
        )
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ArtifactValidationError(f"{label}: expected trimmed non-empty string")
    return value


def _boolean(value: Any, label: str) -> bool:
    if type(value) is not bool:
        raise ArtifactValidationError(f"{label}: expected boolean")
    return value


def _repo_path(value: Any, label: str) -> Path:
    raw = _string(value, label)
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts:
        raise ArtifactValidationError(
            f"{label}: expected safe repository-relative path"
        )
    resolved = (ROOT / path).resolve()
    if not resolved.is_relative_to(ROOT.resolve()):
        raise ArtifactValidationError(f"{label}: path escapes repository root")
    return resolved


def _validate_lock(value: Any) -> dict[str, Any]:
    lock = dict(
        _exact_mapping(
            value,
            "lock",
            {
                "schema_version",
                "status",
                "sources",
                "fixtures",
                "controller_config",
                "comparison_gates",
                "representative",
                "canonicalization",
                "artifact",
                "claim_boundary",
            },
        )
    )
    if (
        lock["schema_version"]
        != "ebrt-temporal-adjoint-state-control-policy-lock-v0.5-t.0"
    ):
        raise ArtifactValidationError("lock.schema_version mismatch")
    if lock["status"] != "LOCKED_SYNTHETIC_MECHANISM":
        raise ArtifactValidationError("lock.status mismatch")
    sources = _exact_mapping(
        lock["sources"], "lock.sources", {"core", "benchmark", "builder"}
    )
    for name, raw in sources.items():
        item = _exact_mapping(raw, f"lock.sources.{name}", {"path", "sha256"})
        path = _repo_path(item["path"], f"lock.sources.{name}.path")
        expected = _string(item["sha256"], f"lock.sources.{name}.sha256")
        if _sha256(path) != expected:
            raise ArtifactValidationError(f"source hash mismatch: {name}")
    fixtures = _exact_mapping(lock["fixtures"], "lock.fixtures", {"event", "no_event"})
    for name, raw in fixtures.items():
        item = _exact_mapping(
            raw,
            f"lock.fixtures.{name}",
            {"path", "sha256", "semantic_payload_sha256", "suite_id"},
        )
        path = _repo_path(item["path"], f"lock.fixtures.{name}.path")
        if _sha256(path) != item["sha256"]:
            raise ArtifactValidationError(f"fixture full-file hash mismatch: {name}")
        suite = TemporalPairedSuite.from_mapping(_load_json_exact(path))
        if suite.semantic_payload_sha256() != item["semantic_payload_sha256"]:
            raise ArtifactValidationError(f"fixture semantic hash mismatch: {name}")
        if suite.suite_id != item["suite_id"]:
            raise ArtifactValidationError(f"fixture suite id mismatch: {name}")
    expected_config = ControllerConfig().to_dict()
    if lock["controller_config"] != expected_config:
        raise ArtifactValidationError(
            "locked controller config differs from source default"
        )
    expected_gates = {
        "collapsed_gradient_abs_tolerance": COLLAPSED_GRADIENT_ABS_TOLERANCE,
        "sham_norm_abs_tolerance": SHAM_NORM_ABS_TOLERANCE,
        "minimum_C_win_fraction_vs_B": MIN_C_WIN_FRACTION_VS_B,
        "minimum_C_win_fraction_vs_locked_D": MIN_C_WIN_FRACTION_VS_D,
        "minimum_aggregate_relative_reduction_vs_B": MIN_AGGREGATE_RELATIVE_REDUCTION_VS_B,
        "minimum_order_switch_fraction": MIN_ORDER_SWITCH_FRACTION,
        "minimum_top_leverage_margin": MIN_TOP_LEVERAGE_MARGIN,
        "expected_early_top_control": EXPECTED_EARLY_TOP_CONTROL,
        "expected_early_top_floor_ordinal": EXPECTED_EARLY_TOP_FLOOR_ORDINAL,
        "expected_late_top_control": EXPECTED_LATE_TOP_CONTROL,
        "expected_late_top_floor_ordinal": EXPECTED_LATE_TOP_FLOOR_ORDINAL,
        "require_C_beat_every_nonidentity_sham_aggregate": True,
        "minimum_C_win_fraction_against_every_nonidentity_sham": 1.0,
    }
    if lock["comparison_gates"] != expected_gates:
        raise ArtifactValidationError("locked comparison gates differ from source")
    representative = _exact_mapping(
        lock["representative"],
        "lock.representative",
        {"pair_id", "early_order_variant", "late_order_variant", "lane"},
    )
    if representative != {
        "pair_id": "P03",
        "early_order_variant": "early_correction",
        "late_order_variant": "late_correction",
        "lane": "transition",
    }:
        raise ArtifactValidationError("representative selection mismatch")
    canonical = _exact_mapping(
        lock["canonicalization"],
        "lock.canonicalization",
        {
            "encoding",
            "ensure_ascii",
            "sort_keys",
            "separators",
            "allow_nan",
            "trailing_newline",
        },
    )
    if canonical != {
        "encoding": "utf-8",
        "ensure_ascii": False,
        "sort_keys": True,
        "separators": [",", ":"],
        "allow_nan": False,
        "trailing_newline": True,
    }:
        raise ArtifactValidationError("canonicalization policy mismatch")
    artifact = _exact_mapping(
        lock["artifact"], "lock.artifact", {"directory", "files", "network_calls"}
    )
    if artifact["directory"] != ARTIFACT_DIRECTORY:
        raise ArtifactValidationError("artifact directory mismatch")
    if tuple(artifact["files"]) != ARTIFACT_FILES:
        raise ArtifactValidationError("artifact file list mismatch")
    if artifact["network_calls"] != 0:
        raise ArtifactValidationError("network_calls must be exact zero")
    boundaries = lock["claim_boundary"]
    if (
        not isinstance(boundaries, list)
        or not boundaries
        or any(not isinstance(item, str) or not item for item in boundaries)
    ):
        raise ArtifactValidationError("claim_boundary must be a non-empty string list")
    return lock


def _load_lock() -> dict[str, Any]:
    return _validate_lock(_load_json_exact(LOCK_PATH))


@contextmanager
def _network_guard() -> Iterator[None]:
    with mock.patch.object(
        socket, "socket", side_effect=AssertionError("network used")
    ):
        yield


def _source_ledger(lock: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "policy_lock": {
            "path": str(LOCK_PATH.relative_to(ROOT)),
            "sha256": _sha256(LOCK_PATH),
        }
    }
    for group in ("sources", "fixtures"):
        for name, item in lock[group].items():
            result[f"{group[:-1]}:{name}"] = {
                "path": item["path"],
                "sha256": item["sha256"],
            }
    return result


def _mechanism_report(
    comparison: Mapping[str, Any],
    early_map: Mapping[str, Any],
    late_map: Mapping[str, Any],
    early_audit: Mapping[str, Any],
    late_audit: Mapping[str, Any],
) -> bytes:
    aggregate = comparison["aggregate"]
    gates = comparison["locked_mechanism_gates"]
    lines = [
        "# EBRT v0.5-T temporal adjoint state-control mechanism report",
        "",
        f"Status: **{comparison['decision']['status']}**",
        "",
        "## Locked question",
        "",
        "Can controls over supplied public state transitions add a useful intervention "
        "class beyond evidence-leaf gates under the same standardized coordinate count "
        "and L2 cap, while exact local adjoints move the nominated intervention point "
        "when evidence order changes?",
        "",
        "## Four-arm result",
        "",
        "| Arm | Sum of actual terminal task loss (16 cases) |",
        "| --- | ---: |",
    ]
    for arm_id, values in aggregate.items():
        lines.append(f"| `{arm_id}` | {values['actual_task_loss_after_sum']:.12f} |")
    lines.extend(
        [
            "",
            "Across the 16 ordered cells of one local parameter sweep, the temporal "
            "state-transition arm beat the temporal leaf arm in "
            f"**{gates['C_win_fraction_vs_B_cells']['wins']}/16** cells and the locked "
            f"shuffled-floor sham in **{gates['C_win_fraction_vs_locked_D_cells']['wins']}/16**. "
            "Its aggregate loss reduction versus temporal leaf control was "
            f"**{100.0 * gates['C_aggregate_relative_reduction_vs_B']['observed']:.2f}%**.",
            "It also beat all five nonidentity control-floor permutations in all 16 cells; "
            "the best such sham had aggregate loss "
            f"`{gates['C_beats_every_nonidentity_sham_aggregate']['best_nonidentity_sham_aggregate_actual_task_loss']}`.",
            "",
            "## Order-sensitive intervention",
            "",
            "For all eight parameter cells, the largest fixed-step finite "
            "control leverage moved with order:",
            "",
            f"- early correction: `{early_audit['floor_summary']['top_finite_leverage_target_id']}` "
            f"at `{early_audit['floor_summary']['top_finite_leverage_floor_id']}`",
            f"- late correction: `{late_audit['floor_summary']['top_finite_leverage_target_id']}` "
            f"at `{late_audit['floor_summary']['top_finite_leverage_floor_id']}`",
            "",
            "The representative execution maps remained inside the shared L2 budget:",
            "",
            f"- early: `{early_map['budget']['observed_control_l2_norm']}`",
            f"- late: `{late_map['budget']['observed_control_l2_norm']}`",
            "",
            "## Numerical and anti-decoration checks",
            "",
            f"- collapsed A/B neutral-gradient max error: "
            f"`{gates['collapsed_A_B_neutral_gradient_equivalence']['observed_max_abs_error']}`",
            f"- matched-sham L2 max error: "
            f"`{gates['matched_sham_L2_norm']['observed_max_abs_error']}`",
            "- all control bases are normalized locally, but terminal Jacobian norms are not matched; actuator-scale rows are published in `arm_comparison.json`",
            "- manual temporal adjoints and central finite differences are checked by the core self-test",
            "- the audit is a detached sidecar; observing it does not alter execution-map bytes",
            "- no-event is exact identity with zero backward calls",
            "- network calls: `0`",
            "",
            "## Claim boundary",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in comparison["claim_boundary"])
    lines.extend(
        [
            "",
            "The recorded mechanism claim is therefore limited to:",
            "",
            "> On one synthetic oracle-specified topology and its parameter sweep, "
            "exact local adjoints optimized bounded transition-basis controls that "
            "outperformed leaf controls and every matched floor permutation. The "
            "result includes the supplied actuator geometry.",
            "",
        ]
    )
    return "\n".join(lines).encode("utf-8")


def _manifest(
    lock: Mapping[str, Any], artifacts_without_manifest: Mapping[str, bytes]
) -> dict[str, Any]:
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "status": "COMPLETE_LOCKED_SYNTHETIC_MECHANISM",
        "controller": {
            "name": CONTROLLER_NAME,
            "version": CONTROLLER_VERSION,
            "benchmark_name": BENCHMARK_NAME,
            "benchmark_version": BENCHMARK_VERSION,
        },
        "runtime": _observed_runtime(),
        "source_ledger": _source_ledger(lock),
        "artifacts": {
            name: {"sha256": _sha256_bytes(value), "bytes": len(value)}
            for name, value in sorted(artifacts_without_manifest.items())
        },
        "artifact_directory": ARTIFACT_DIRECTORY,
        "network_calls": 0,
        "reproduction_boundary": (
            "Canonical byte identity is asserted for the recorded runtime; arbitrary "
            "cross-runtime floating-point byte identity is not claimed."
        ),
        "claim_boundary": lock["claim_boundary"],
    }


def _materialize(lock: Mapping[str, Any]) -> dict[str, bytes]:
    event_path = _repo_path(lock["fixtures"]["event"]["path"], "event fixture")
    no_event_path = _repo_path(lock["fixtures"]["no_event"]["path"], "no-event fixture")
    event_suite = TemporalPairedSuite.from_mapping(_load_json_exact(event_path))
    no_event_suite = TemporalPairedSuite.from_mapping(_load_json_exact(no_event_path))
    config = ControllerConfig(**lock["controller_config"])
    controller = TemporalAdjointStateController(config)
    benchmark = TemporalControlBenchmark(event_suite, config)
    representative = lock["representative"]
    with _network_guard():
        controller_self_test = run_controller_self_tests()
        benchmark_self_test = run_benchmark_self_tests(event_path)
        comparison = benchmark.comparison()
        early_program = event_suite.materialize(
            representative["pair_id"], representative["early_order_variant"]
        )
        late_program = event_suite.materialize(
            representative["pair_id"], representative["late_order_variant"]
        )
        early_result = controller.optimize(early_program, representative["lane"])
        late_result = controller.optimize(late_program, representative["lane"])
        early_map = early_result.to_execution_control_map()
        late_map = late_result.to_execution_control_map()
        early_audit = controller.temporal_adjoint_audit(early_program, early_result)
        late_audit = controller.temporal_adjoint_audit(late_program, late_result)
        no_event_program = no_event_suite.materialize("P00", "early_correction")
        no_event_result = controller.optimize(no_event_program, "transition")
        no_event_map = no_event_result.to_execution_control_map()
        no_event_audit = controller.temporal_adjoint_audit(
            no_event_program, no_event_result
        )
    if (
        comparison["decision"]["status"]
        != "RECORD_POSITIVE_TEMPORAL_STATE_CONTROL_MECHANISM"
    ):
        raise ArtifactValidationError("comparison did not pass its locked stop rule")
    self_test = {
        "schema_version": SELF_TEST_SCHEMA_VERSION,
        "status": "PASS",
        "controller": controller_self_test,
        "benchmark": benchmark_self_test,
        "network_calls": 0,
        "claim_boundary": (
            "Synthetic mechanism and artifact integrity only; no hosted model executed."
        ),
    }
    artifacts: dict[str, bytes] = {
        "representative_early_execution_control_map.json": _pretty_json_bytes(
            early_map
        ),
        "representative_early_temporal_adjoint_audit.json": _pretty_json_bytes(
            early_audit
        ),
        "representative_late_execution_control_map.json": _pretty_json_bytes(late_map),
        "representative_late_temporal_adjoint_audit.json": _pretty_json_bytes(
            late_audit
        ),
        "no_event_execution_control_map.json": _pretty_json_bytes(no_event_map),
        "no_event_temporal_adjoint_audit.json": _pretty_json_bytes(no_event_audit),
        "arm_comparison.json": _pretty_json_bytes(comparison),
        "self_test.json": _pretty_json_bytes(self_test),
        "mechanism_report.md": _mechanism_report(
            comparison, early_map, late_map, early_audit, late_audit
        ),
    }
    artifacts["manifest.json"] = _pretty_json_bytes(_manifest(lock, artifacts))
    if tuple(artifacts) != ARTIFACT_FILES:
        raise ArtifactValidationError("materialized artifact order/file set mismatch")
    return artifacts


def _artifact_directory(lock: Mapping[str, Any]) -> Path:
    return _repo_path(lock["artifact"]["directory"], "artifact.directory")


def _write_fsynced(path: Path, value: bytes) -> None:
    with path.open("wb") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _publish_bundle(target: Path, artifacts: Mapping[str, bytes]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{target.name}.staging-", dir=target.parent)
    )
    backup = target.parent / f".{target.name}.backup-{os.getpid()}"
    try:
        for name, value in artifacts.items():
            _write_fsynced(staging / name, value)
        _fsync_directory(staging)
        if backup.exists():
            raise ArtifactValidationError(f"unexpected backup path exists: {backup}")
        had_target = target.exists()
        if had_target:
            os.replace(target, backup)
        try:
            os.replace(staging, target)
            _fsync_directory(target.parent)
        except BaseException:
            if had_target and backup.exists() and not target.exists():
                os.replace(backup, target)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def _read_bundle(directory: Path) -> dict[str, bytes]:
    if not directory.is_dir():
        raise ArtifactValidationError(f"artifact directory is missing: {directory}")
    entries = tuple(sorted(directory.iterdir(), key=lambda item: item.name))
    observed = tuple(item.name for item in entries)
    expected = tuple(sorted(ARTIFACT_FILES))
    if observed != expected:
        raise ArtifactValidationError(
            f"artifact file set mismatch: observed={observed}, expected={expected}"
        )
    non_regular = [
        item.name for item in entries if item.is_symlink() or not item.is_file()
    ]
    if non_regular:
        raise ArtifactValidationError(
            f"artifact entries must be regular files: {non_regular}"
        )
    return {name: (directory / name).read_bytes() for name in ARTIFACT_FILES}


def _validate_bundle_bytes(
    observed: Mapping[str, bytes], expected: Mapping[str, bytes]
) -> None:
    if set(observed) != set(expected):
        raise ArtifactValidationError("artifact key set mismatch")
    mismatches = [name for name in ARTIFACT_FILES if observed[name] != expected[name]]
    if mismatches:
        raise ArtifactValidationError(f"artifact byte mismatch: {mismatches}")
    manifest = json.loads(observed["manifest.json"])
    if manifest["runtime"] != _observed_runtime():
        raise ArtifactValidationError("manifest runtime mismatch")
    for name, record in manifest["artifacts"].items():
        if _sha256_bytes(observed[name]) != record["sha256"]:
            raise ArtifactValidationError(f"manifest artifact digest mismatch: {name}")
        if len(observed[name]) != record["bytes"]:
            raise ArtifactValidationError(f"manifest artifact size mismatch: {name}")
    comparison = json.loads(observed["arm_comparison.json"])
    payload = copy.deepcopy(comparison)
    fingerprint = payload.pop("fingerprint_sha256")
    if fingerprint != _sha256_json(payload):
        raise ArtifactValidationError("comparison fingerprint mismatch")
    if not comparison["decision"]["all_locked_gates_pass"]:
        raise ArtifactValidationError("committed comparison failed locked gates")
    no_event = json.loads(observed["no_event_execution_control_map.json"])
    if no_event["status"] != "NO_EVENT_IDENTITY":
        raise ArtifactValidationError("no-event map is not identity")
    if no_event["optimization"]["backward_calls"] != 0:
        raise ArtifactValidationError("no-event map recorded backward calls")


def build() -> dict[str, str]:
    lock = _load_lock()
    artifacts = _materialize(lock)
    target = _artifact_directory(lock)
    _publish_bundle(target, artifacts)
    observed = _read_bundle(target)
    _validate_bundle_bytes(observed, artifacts)
    return {name: _sha256_bytes(value) for name, value in observed.items()}


def validate() -> None:
    lock = _load_lock()
    expected = _materialize(lock)
    observed = _read_bundle(_artifact_directory(lock))
    _validate_bundle_bytes(observed, expected)


def self_test() -> dict[str, Any]:
    lock = _load_lock()
    first = _materialize(lock)
    second = _materialize(lock)
    if first != second:
        raise AssertionError("two in-memory artifact builds were not byte identical")
    _validate_bundle_bytes(first, second)
    tampered = copy.deepcopy(lock)
    tampered["sources"]["core"]["sha256"] = "0" * 64
    try:
        _validate_lock(tampered)
    except ArtifactValidationError:
        pass
    else:
        raise AssertionError("tampered source digest was accepted")
    with tempfile.TemporaryDirectory(prefix="ebrt-v05t-bundle-audit-") as raw:
        bundle = Path(raw) / "bundle"
        bundle.mkdir()
        for name, value in first.items():
            (bundle / name).write_bytes(value)
        _read_bundle(bundle)
        (bundle / "unexpected").mkdir()
        try:
            _read_bundle(bundle)
        except ArtifactValidationError:
            pass
        else:
            raise AssertionError("unexpected artifact subdirectory was accepted")
        (bundle / "unexpected").rmdir()
        manifest = bundle / "manifest.json"
        manifest.unlink()
        manifest.symlink_to(bundle / "arm_comparison.json")
        try:
            _read_bundle(bundle)
        except ArtifactValidationError:
            pass
        else:
            raise AssertionError("symlinked artifact entry was accepted")
    return {
        "status": "PASS",
        "checks": [
            "policy lock pins every source and fixture byte",
            "two same-runtime in-memory builds are byte identical",
            "artifact manifest covers every non-manifest artifact",
            "comparison fingerprint and locked mechanism gates validate",
            "no-event artifact is identity with zero backward calls",
            "tampered source digest is rejected",
            "unexpected directories and symlinked artifact entries are rejected",
            "all materialization completes while socket creation is denied",
        ],
        "artifact_sha256": {
            name: _sha256_bytes(value) for name, value in first.items()
        },
        "runtime": _observed_runtime(),
        "claim_boundary": (
            "Same-runtime synthetic artifact reproducibility only; no provider execution."
        ),
    }


def _pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("build")
    subparsers.add_parser("validate")
    subparsers.add_parser("self-test")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "build":
        print(_pretty_json({"status": "BUILT", "sha256": build()}), end="")
        return 0
    if args.command == "validate":
        validate()
        print(_pretty_json({"status": "VALID"}), end="")
        return 0
    print(_pretty_json(self_test()), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
