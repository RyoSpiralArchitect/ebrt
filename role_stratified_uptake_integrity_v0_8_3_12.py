#!/usr/bin/env python3
"""CPython-framework-bound wrapper for the EBRT v0.8.3 canary.

Invoke with ``python3 -E -S``. This r13 successor retains the r12 locked stdlib
code tree and additionally binds the macOS Python framework library that holds
the CPython implementation behind the small launcher executable. The repeated
cases are integrity-only and are not fresh scientific evidence.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


SOURCE_ONLY_CHILD_ENV = "EBRT_V08312_SOURCE_ONLY_CHILD"
SOURCE_ONLY_PREFIX_ENV = "EBRT_V08312_SOURCE_ONLY_PREFIX"
PRIOR_CHILD_ENVS = (
    "EBRT_V08311_SOURCE_ONLY_CHILD",
    "EBRT_V08310_SOURCE_ONLY_CHILD",
    "EBRT_V0839_SOURCE_ONLY_CHILD",
    "EBRT_V0838_SOURCE_ONLY_CHILD",
    "EBRT_V0837_SOURCE_ONLY_CHILD",
)
PRIOR_PREFIX_ENVS = (
    "EBRT_V08311_SOURCE_ONLY_PREFIX",
    "EBRT_V08310_SOURCE_ONLY_PREFIX",
    "EBRT_V0839_SOURCE_ONLY_PREFIX",
    "EBRT_V0838_SOURCE_ONLY_PREFIX",
    "EBRT_V0837_SOURCE_ONLY_PREFIX",
)


def _bootstrap_isolated_child() -> None:
    if sys.flags.ignore_environment != 1 or sys.flags.no_site != 1:
        print(
            json.dumps(
                {
                    "status": "ERROR",
                    "error_code": "ROLE_FRAMEWORK_STARTUP_ISOLATION_NOT_ENABLED",
                }
            )
        )
        raise SystemExit(2)
    if os.environ.get(SOURCE_ONLY_CHILD_ENV) == "1":
        expected_prefix = os.environ.get(SOURCE_ONLY_PREFIX_ENV)
        if (
            not sys.dont_write_bytecode
            or sys.pycache_prefix is None
            or expected_prefix is None
            or Path(sys.pycache_prefix).resolve() != Path(expected_prefix).resolve()
        ):
            print(
                json.dumps(
                    {
                        "status": "ERROR",
                        "error_code": "ROLE_FRAMEWORK_CHILD_POLICY_INVALID",
                    }
                )
            )
            raise SystemExit(2)
        return
    with tempfile.TemporaryDirectory(prefix="ebrt-v08312-pycache-") as temporary:
        prefix = Path(temporary).resolve()
        if any(prefix.iterdir()):
            print(
                json.dumps(
                    {
                        "status": "ERROR",
                        "error_code": "ROLE_FRAMEWORK_PREFIX_NOT_EMPTY",
                    }
                )
            )
            raise SystemExit(2)
        environment = os.environ.copy()
        for child_name in (SOURCE_ONLY_CHILD_ENV, *PRIOR_CHILD_ENVS):
            environment[child_name] = "1"
        for prefix_name in (SOURCE_ONLY_PREFIX_ENV, *PRIOR_PREFIX_ENVS):
            environment[prefix_name] = str(prefix)
        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-E",
                    "-S",
                    "-B",
                    "-X",
                    f"pycache_prefix={prefix}",
                    str(Path(__file__).resolve()),
                    *sys.argv[1:],
                ],
                check=False,
                env=environment,
            )
        except OSError:
            print(
                json.dumps(
                    {
                        "status": "ERROR",
                        "error_code": "ROLE_FRAMEWORK_REEXEC_FAILED",
                    }
                )
            )
            raise SystemExit(2) from None
        raise SystemExit(completed.returncode)


if __name__ == "__main__":
    _bootstrap_isolated_child()


import argparse  # noqa: E402
import sysconfig  # noqa: E402
from typing import Any, Mapping, Sequence  # noqa: E402


def _explicit_site_paths() -> tuple[Path, ...]:
    values = {
        sysconfig.get_path("purelib"),
        sysconfig.get_path("platlib"),
    }
    if "osx_framework_user" in sysconfig.get_scheme_names():
        values.add(sysconfig.get_path("purelib", scheme="osx_framework_user"))
        values.add(sysconfig.get_path("platlib", scheme="osx_framework_user"))
    paths = tuple(
        sorted(
            Path(value).resolve()
            for value in values
            if isinstance(value, str) and Path(value).is_dir()
        )
    )
    if not paths:
        raise RuntimeError("ROLE_FRAMEWORK_SITE_PATHS_EMPTY")
    return paths


EXPLICIT_SITE_PATHS = _explicit_site_paths()
for _site_path in EXPLICIT_SITE_PATHS:
    if str(_site_path) not in sys.path:
        sys.path.append(str(_site_path))


import role_stratified_uptake_integrity_v0_8_3_11 as tree_bound  # noqa: E402
from ebrt_core import (  # noqa: E402
    EBRTError,
    _canonical_bytes,
    _seal,
    _sealed_snapshot,
)


startup_bound = tree_bound.startup_bound
LOCK_SCHEMA_VERSION = "ebrt-role-uptake-framework-lock-v0.8.3.12"
RUN_SCHEMA_VERSION = "ebrt-role-uptake-framework-run-v0.8.3.12"
SELF_TEST_SCHEMA_VERSION = "ebrt-role-uptake-framework-self-test-v0.8.3.12"
CLAIM_BOUNDARY = (
    "This r13 execution repeats already observed cases only to bind the macOS Python framework library behind the admitted CPython launcher.",
    "The repeated outputs are contaminated by known r01-r12 results and are not fresh scientific replication evidence.",
    "The r12 interpreter-launcher and complete stdlib code-tree lock remains the code-universe boundary; r13 adds the framework implementation binary.",
    "Both interpreters retain the -E -S startup boundary, verified-source cache bypass, and explicit site-package admission.",
    "Other dyld dependencies, shared system libraries, non-code stdlib data, hardware, kernel, code signing, and malicious-root behavior are not attested.",
    "All original v0.8.3 effect-attribution, one-model, public-role, and stop-gradient boundaries remain unchanged.",
)

JsonObject = dict[str, Any]


def _sha256(path: Path) -> str:
    return startup_bound.complete_bound._sha256(path)


def _load_json(path: Path) -> JsonObject:
    return startup_bound.complete_bound._load_json(path)


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    startup_bound.complete_bound._write_json(path, value)


def _framework_library_receipt() -> JsonObject:
    framework_name = sysconfig.get_config_var("PYTHONFRAMEWORK")
    if not isinstance(framework_name, str) or not framework_name:
        raise EBRTError("ROLE_FRAMEWORK_CONFIGURATION_MISSING")
    configured_path = Path(sys.base_prefix) / framework_name
    try:
        resolved = configured_path.resolve(strict=True)
    except OSError as error:
        raise EBRTError("ROLE_FRAMEWORK_LIBRARY_MISSING") from error
    if not resolved.is_file():
        raise EBRTError("ROLE_FRAMEWORK_LIBRARY_NOT_FILE")
    return _seal(
        {
            "schema_version": "ebrt-python-framework-library-v0.8.3.12",
            "framework_name": framework_name,
            "base_prefix": sys.base_prefix,
            "configured_path": str(configured_path),
            "resolved_path": str(resolved),
            "configured_path_is_symlink": configured_path.is_symlink(),
            "size_bytes": resolved.stat().st_size,
            "sha256": _sha256(resolved),
        }
    )


def _validate_framework_shape(value: Any) -> JsonObject:
    receipt = _sealed_snapshot(value, "ROLE_FRAMEWORK_LIBRARY")
    if (
        set(receipt)
        != {
            "schema_version",
            "framework_name",
            "base_prefix",
            "configured_path",
            "resolved_path",
            "configured_path_is_symlink",
            "size_bytes",
            "sha256",
            "fingerprint_sha256",
        }
        or receipt.get("schema_version") != "ebrt-python-framework-library-v0.8.3.12"
        or not isinstance(receipt.get("framework_name"), str)
        or not receipt["framework_name"]
        or not isinstance(receipt.get("base_prefix"), str)
        or not Path(receipt["base_prefix"]).is_absolute()
        or not isinstance(receipt.get("configured_path"), str)
        or not Path(receipt["configured_path"]).is_absolute()
        or not isinstance(receipt.get("resolved_path"), str)
        or not Path(receipt["resolved_path"]).is_absolute()
        or type(receipt.get("configured_path_is_symlink")) is not bool
        or type(receipt.get("size_bytes")) is not int
        or receipt["size_bytes"] <= 0
        or not isinstance(receipt.get("sha256"), str)
        or len(receipt["sha256"]) != 64
    ):
        raise EBRTError("ROLE_FRAMEWORK_LIBRARY_SHAPE_INVALID")
    return receipt


def _probe_execution_state(
    model_path: str,
) -> tuple[JsonObject, JsonObject, JsonObject, JsonObject, JsonObject, JsonObject]:
    code, source, startup, identity, coverage = tree_bound._probe_execution_state(
        model_path
    )
    return code, source, startup, identity, coverage, _framework_library_receipt()


def lock_spec(
    locks: Sequence[Mapping[str, Any]],
    runtime_code: Mapping[str, Any],
    source_execution: Mapping[str, Any],
    startup_execution: Mapping[str, Any],
    runtime_identity: Mapping[str, Any],
    framework_library: Mapping[str, Any],
) -> JsonObject:
    if len(locks) != 12:
        raise EBRTError("ROLE_FRAMEWORK_LOCK_CHAIN_INVALID")
    locked_tree = tree_bound.validate_lock(locks[-1], *locks[:-1])
    code = startup_bound.complete_bound._validate_runtime_code_shape(runtime_code)
    source = startup_bound.source_bound._validate_source_execution_shape(
        source_execution
    )
    startup = startup_bound._validate_startup_shape(startup_execution)
    identity = tree_bound._validate_runtime_identity_shape(runtime_identity)
    if _canonical_bytes(identity) != _canonical_bytes(locked_tree["runtime_identity"]):
        raise EBRTError("ROLE_FRAMEWORK_STDLIB_TREE_MISMATCH")
    framework = _validate_framework_shape(framework_library)
    return _seal(
        {
            "schema_version": LOCK_SCHEMA_VERSION,
            "status": "LOCKED_BEFORE_PROVIDER_CALLS",
            "wrapper_sha256": _sha256(Path(__file__)),
            "tree_lock_fingerprint_sha256": locked_tree["fingerprint_sha256"],
            "runtime_code": code,
            "runtime_code_fingerprint_sha256": code["fingerprint_sha256"],
            "source_execution": source,
            "source_execution_fingerprint_sha256": source["fingerprint_sha256"],
            "startup_execution": startup,
            "startup_execution_fingerprint_sha256": startup["fingerprint_sha256"],
            "framework_library": framework,
            "framework_library_fingerprint_sha256": framework["fingerprint_sha256"],
            "replication_status": "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R12_CASES",
            "effect_attribution_status": "NOT_ASSESSED",
            "claim_boundary": list(CLAIM_BOUNDARY),
        }
    )


def validate_lock(value: Any, locks: Sequence[Mapping[str, Any]]) -> JsonObject:
    observed = _sealed_snapshot(value, "ROLE_FRAMEWORK_LOCK")
    locked_tree = tree_bound.validate_lock(locks[-1], *locks[:-1])
    expected = lock_spec(
        locks,
        startup_bound.complete_bound._validate_runtime_code_shape(
            observed.get("runtime_code")
        ),
        startup_bound.source_bound._validate_source_execution_shape(
            observed.get("source_execution")
        ),
        startup_bound._validate_startup_shape(observed.get("startup_execution")),
        locked_tree["runtime_identity"],
        _validate_framework_shape(observed.get("framework_library")),
    )
    if _canonical_bytes(observed) != _canonical_bytes(expected):
        raise EBRTError("ROLE_FRAMEWORK_LOCK_MISMATCH")
    return observed


def _base_run(model_path: str, locks: Sequence[Mapping[str, Any]]) -> JsonObject:
    base_lock, source_lock, snapshot_lock, loader_lock, runtime_lock, immutable_lock = (
        locks[:6]
    )
    value = startup_bound.immutable_bound.run_integrity_replication(
        model_path,
        immutable_lock,
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
    )
    startup_bound.complete_bound._verify_mount_receipt(
        value.get("mount_receipt"), snapshot_lock
    )
    return value


def run_integrity_replication(
    model_path: str,
    lock: Mapping[str, Any],
    locks: Sequence[Mapping[str, Any]],
) -> JsonObject:
    if len(locks) != 12:
        raise EBRTError("ROLE_FRAMEWORK_LOCK_CHAIN_INVALID")
    locked = validate_lock(lock, locks)
    locked_tree = tree_bound.validate_lock(locks[-1], *locks[:-1])
    (
        code_before,
        source_before,
        startup_before,
        identity_before,
        coverage_before,
        framework_before,
    ) = _probe_execution_state(model_path)
    if (
        _canonical_bytes(code_before) != _canonical_bytes(locked["runtime_code"])
        or _canonical_bytes(source_before)
        != _canonical_bytes(locked["source_execution"])
        or _canonical_bytes(startup_before)
        != _canonical_bytes(locked["startup_execution"])
        or _canonical_bytes(identity_before)
        != _canonical_bytes(locked_tree["runtime_identity"])
        or _canonical_bytes(framework_before)
        != _canonical_bytes(locked["framework_library"])
    ):
        raise EBRTError("ROLE_FRAMEWORK_PRECALL_STATE_MISMATCH")
    tree_bound._validate_coverage_shape(
        coverage_before, locked_tree["runtime_identity"]
    )
    base_run = _base_run(model_path, locks)
    code_after = startup_bound.complete_bound._complete_runtime_code_receipt()
    source_after = startup_bound.source_bound._source_execution_receipt()
    startup_after = startup_bound._startup_receipt()
    identity_after = tree_bound._runtime_identity_receipt()
    coverage_after = tree_bound._imported_stdlib_coverage(identity_after)
    framework_after = _framework_library_receipt()
    if (
        _canonical_bytes(code_after) != _canonical_bytes(locked["runtime_code"])
        or _canonical_bytes(source_after)
        != _canonical_bytes(locked["source_execution"])
        or _canonical_bytes(startup_after)
        != _canonical_bytes(locked["startup_execution"])
        or _canonical_bytes(identity_after)
        != _canonical_bytes(locked_tree["runtime_identity"])
        or _canonical_bytes(framework_after)
        != _canonical_bytes(locked["framework_library"])
    ):
        raise EBRTError("ROLE_FRAMEWORK_POSTCALL_STATE_MISMATCH")
    tree_bound._validate_coverage_shape(coverage_after, locked_tree["runtime_identity"])
    return _seal(
        {
            "schema_version": RUN_SCHEMA_VERSION,
            "status": "COMPLETE",
            "policy_lock_fingerprint_sha256": locked["fingerprint_sha256"],
            "runtime_code_before": code_before,
            "runtime_code_after": code_after,
            "source_execution_before": source_before,
            "source_execution_after": source_after,
            "startup_execution_before": startup_before,
            "startup_execution_after": startup_after,
            "runtime_identity_before": identity_before,
            "runtime_identity_after": identity_after,
            "imported_stdlib_coverage_before": coverage_before,
            "imported_stdlib_coverage_after": coverage_after,
            "framework_library_before": framework_before,
            "framework_library_after": framework_after,
            "base_run": base_run,
            "summary": base_run["summary"],
            "replication_status": "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R12_CASES",
            "effect_attribution_status": "NOT_ASSESSED",
            "claim_boundary": list(CLAIM_BOUNDARY),
        }
    )


def verify_run(
    value: Any,
    lock: Mapping[str, Any],
    locks: Sequence[Mapping[str, Any]],
) -> JsonObject:
    if len(locks) != 12:
        raise EBRTError("ROLE_FRAMEWORK_LOCK_CHAIN_INVALID")
    locked = validate_lock(lock, locks)
    locked_tree = tree_bound.validate_lock(locks[-1], *locks[:-1])
    snapshot = _sealed_snapshot(value, "ROLE_FRAMEWORK_RUN")
    expected_keys = {
        "schema_version",
        "status",
        "policy_lock_fingerprint_sha256",
        "runtime_code_before",
        "runtime_code_after",
        "source_execution_before",
        "source_execution_after",
        "startup_execution_before",
        "startup_execution_after",
        "runtime_identity_before",
        "runtime_identity_after",
        "imported_stdlib_coverage_before",
        "imported_stdlib_coverage_after",
        "framework_library_before",
        "framework_library_after",
        "base_run",
        "summary",
        "replication_status",
        "effect_attribution_status",
        "claim_boundary",
        "fingerprint_sha256",
    }
    locked_code = startup_bound.complete_bound._validate_runtime_code_shape(
        locked.get("runtime_code")
    )
    locked_source = startup_bound.source_bound._validate_source_execution_shape(
        locked.get("source_execution")
    )
    locked_startup = startup_bound._validate_startup_shape(
        locked.get("startup_execution")
    )
    locked_identity = tree_bound._validate_runtime_identity_shape(
        locked_tree.get("runtime_identity")
    )
    locked_framework = _validate_framework_shape(locked.get("framework_library"))
    if (
        set(snapshot) != expected_keys
        or snapshot.get("schema_version") != RUN_SCHEMA_VERSION
        or snapshot.get("status") != "COMPLETE"
        or snapshot.get("policy_lock_fingerprint_sha256")
        != locked["fingerprint_sha256"]
        or any(
            _canonical_bytes(snapshot.get(key)) != _canonical_bytes(expected)
            for key, expected in (
                ("runtime_code_before", locked_code),
                ("runtime_code_after", locked_code),
                ("source_execution_before", locked_source),
                ("source_execution_after", locked_source),
                ("startup_execution_before", locked_startup),
                ("startup_execution_after", locked_startup),
                ("runtime_identity_before", locked_identity),
                ("runtime_identity_after", locked_identity),
                ("framework_library_before", locked_framework),
                ("framework_library_after", locked_framework),
            )
        )
        or snapshot.get("replication_status")
        != "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R12_CASES"
        or snapshot.get("effect_attribution_status") != "NOT_ASSESSED"
        or snapshot.get("claim_boundary") != list(CLAIM_BOUNDARY)
    ):
        raise EBRTError("ROLE_FRAMEWORK_RUN_HEADER_INVALID")
    before_coverage = tree_bound._validate_coverage_shape(
        snapshot.get("imported_stdlib_coverage_before"), locked_identity
    )
    after_coverage = tree_bound._validate_coverage_shape(
        snapshot.get("imported_stdlib_coverage_after"), locked_identity
    )
    base_lock, source_lock, snapshot_lock, loader_lock, runtime_lock, immutable_lock = (
        locks[:6]
    )
    base_verification = startup_bound.immutable_bound.verify_run(
        snapshot.get("base_run"),
        immutable_lock,
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
    )
    startup_bound.complete_bound._verify_mount_receipt(
        snapshot["base_run"].get("mount_receipt"), snapshot_lock
    )
    if _canonical_bytes(snapshot.get("summary")) != _canonical_bytes(
        snapshot["base_run"]["summary"]
    ):
        raise EBRTError("ROLE_FRAMEWORK_SUMMARY_MISMATCH")
    return _seal(
        {
            "schema_version": "ebrt-role-uptake-framework-verification-v0.8.3.12",
            "status": "PASS",
            "run_fingerprint_sha256": snapshot["fingerprint_sha256"],
            "base_verification_fingerprint_sha256": base_verification[
                "fingerprint_sha256"
            ],
            "imported_stdlib_module_count_before": before_coverage["module_count"],
            "imported_stdlib_module_count_after": after_coverage["module_count"],
            "checks": {
                "pre_call_lock_exact": True,
                "cpython_launcher_exact": True,
                "cpython_framework_library_exact": True,
                "stdlib_code_tree_exact": True,
                "pre_call_imported_stdlib_covered": True,
                "post_call_imported_stdlib_covered": True,
                "stdlib_bytecode_cache_bypassed": True,
                "python_environment_ignored": True,
                "startup_site_disabled": True,
                "pth_processing_disabled": True,
                "sitecustomize_disabled": True,
                "usercustomize_disabled": True,
                "nonstdlib_source_execution_exact": True,
                "complete_runtime_code_receipt_exact": True,
                "mount_receipt_matches_locked_snapshot": True,
                "known_case_replication_boundary_exact": True,
            },
        }
    )


def self_test(locks: Sequence[Mapping[str, Any]]) -> JsonObject:
    if len(locks) != 12:
        raise EBRTError("ROLE_FRAMEWORK_LOCK_CHAIN_INVALID")
    locked_tree = tree_bound.validate_lock(locks[-1], *locks[:-1])
    tree_test = tree_bound.self_test(*locks[:-1])
    framework = _framework_library_receipt()
    checks = {
        "tree_lock_chain_exact": locked_tree["fingerprint_sha256"]
        == locks[-1]["fingerprint_sha256"],
        "tree_self_test_passed": tree_test["status"] == "PASS",
        "outer_and_child_environment_ignored": sys.flags.ignore_environment == 1,
        "outer_and_child_site_disabled": sys.flags.no_site == 1,
        "source_only_child_active": os.environ.get(SOURCE_ONLY_CHILD_ENV) == "1",
        "framework_name_bound": framework["framework_name"] == "Python",
        "framework_library_bound": framework["size_bytes"] > 1_000_000,
        "framework_library_hash_bound": len(framework["sha256"]) == 64,
    }
    if not all(checks.values()):
        raise EBRTError("ROLE_FRAMEWORK_SELF_TEST_FAILED")
    return _seal(
        {
            "schema_version": SELF_TEST_SCHEMA_VERSION,
            "status": "PASS",
            "checks": checks,
            "claim_boundary": list(CLAIM_BOUNDARY),
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-lock", type=Path, required=True)
    parser.add_argument("--source-lock", type=Path, required=True)
    parser.add_argument("--snapshot-lock", type=Path, required=True)
    parser.add_argument("--loader-lock", type=Path, required=True)
    parser.add_argument("--runtime-lock", type=Path, required=True)
    parser.add_argument("--immutable-lock", type=Path, required=True)
    parser.add_argument("--complete-lock", type=Path, required=True)
    parser.add_argument("--verified-source-lock", type=Path, required=True)
    parser.add_argument("--startup-lock", type=Path, required=True)
    parser.add_argument("--stdlib-lock", type=Path, required=True)
    parser.add_argument("--imported-lock", type=Path, required=True)
    parser.add_argument("--tree-lock", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("self-test")
    probe = commands.add_parser("probe-execution")
    probe.add_argument("--model", required=True)
    lock = commands.add_parser("lock-spec")
    lock.add_argument("--model", required=True)
    run = commands.add_parser("run")
    run.add_argument("--model", required=True)
    run.add_argument("--lock", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("artifact", type=Path)
    verify.add_argument("--lock", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        locks = tuple(
            _load_json(path)
            for path in (
                args.base_lock,
                args.source_lock,
                args.snapshot_lock,
                args.loader_lock,
                args.runtime_lock,
                args.immutable_lock,
                args.complete_lock,
                args.verified_source_lock,
                args.startup_lock,
                args.stdlib_lock,
                args.imported_lock,
                args.tree_lock,
            )
        )
        if args.command == "self-test":
            value = self_test(locks)
        elif args.command == "probe-execution":
            code, source, startup, identity, coverage, framework = (
                _probe_execution_state(args.model)
            )
            value = _seal(
                {
                    "runtime_code": code,
                    "source_execution": source,
                    "startup_execution": startup,
                    "runtime_identity": identity,
                    "imported_stdlib_coverage": coverage,
                    "framework_library": framework,
                }
            )
        elif args.command == "lock-spec":
            code, source, startup, identity, _coverage, framework = (
                _probe_execution_state(args.model)
            )
            value = lock_spec(locks, code, source, startup, identity, framework)
        elif args.command == "run":
            value = run_integrity_replication(args.model, _load_json(args.lock), locks)
            _write_json(args.output, value)
        elif args.command == "verify":
            value = verify_run(_load_json(args.artifact), _load_json(args.lock), locks)
        else:  # pragma: no cover
            raise EBRTError("ROLE_FRAMEWORK_COMMAND_UNKNOWN")
        print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (EBRTError, RuntimeError) as error:
        print(json.dumps({"status": "ERROR", "error_code": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
