#!/usr/bin/env python3
"""Corrected stdlib-bound execution wrapper for the EBRT v0.8.3 canary.

Invoke with ``python3 -E -S``. This r11 successor retains the r10 interpreter
and imported-stdlib receipts but executes the sealed base runner directly.
That avoids asking the historical r09 runner to admit the new wrapper module.
The repeated cases are integrity-only and are not fresh scientific evidence.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


SOURCE_ONLY_CHILD_ENV = "EBRT_V08310_SOURCE_ONLY_CHILD"
SOURCE_ONLY_PREFIX_ENV = "EBRT_V08310_SOURCE_ONLY_PREFIX"
R10_CHILD_ENV = "EBRT_V0839_SOURCE_ONLY_CHILD"
R10_PREFIX_ENV = "EBRT_V0839_SOURCE_ONLY_PREFIX"
R09_CHILD_ENV = "EBRT_V0838_SOURCE_ONLY_CHILD"
R09_PREFIX_ENV = "EBRT_V0838_SOURCE_ONLY_PREFIX"
R08_CHILD_ENV = "EBRT_V0837_SOURCE_ONLY_CHILD"
R08_PREFIX_ENV = "EBRT_V0837_SOURCE_ONLY_PREFIX"


def _bootstrap_isolated_child() -> None:
    if sys.flags.ignore_environment != 1 or sys.flags.no_site != 1:
        print(
            json.dumps(
                {
                    "status": "ERROR",
                    "error_code": "ROLE_STDLIB_R11_STARTUP_ISOLATION_NOT_ENABLED",
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
                        "error_code": "ROLE_STDLIB_R11_CHILD_POLICY_INVALID",
                    }
                )
            )
            raise SystemExit(2)
        return
    with tempfile.TemporaryDirectory(prefix="ebrt-v08310-pycache-") as temporary:
        prefix = Path(temporary).resolve()
        if any(prefix.iterdir()):
            print(
                json.dumps(
                    {
                        "status": "ERROR",
                        "error_code": "ROLE_STDLIB_R11_PREFIX_NOT_EMPTY",
                    }
                )
            )
            raise SystemExit(2)
        environment = os.environ.copy()
        for child_name in (
            SOURCE_ONLY_CHILD_ENV,
            R10_CHILD_ENV,
            R09_CHILD_ENV,
            R08_CHILD_ENV,
        ):
            environment[child_name] = "1"
        for prefix_name in (
            SOURCE_ONLY_PREFIX_ENV,
            R10_PREFIX_ENV,
            R09_PREFIX_ENV,
            R08_PREFIX_ENV,
        ):
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
                        "error_code": "ROLE_STDLIB_R11_REEXEC_FAILED",
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
        raise RuntimeError("ROLE_STDLIB_R11_SITE_PATHS_EMPTY")
    return paths


EXPLICIT_SITE_PATHS = _explicit_site_paths()
for _site_path in EXPLICIT_SITE_PATHS:
    if str(_site_path) not in sys.path:
        sys.path.append(str(_site_path))


import role_stratified_uptake_integrity_v0_8_3_9 as stdlib_bound  # noqa: E402
from ebrt_core import (  # noqa: E402
    EBRTError,
    _canonical_bytes,
    _seal,
    _sealed_snapshot,
)


startup_bound = stdlib_bound.startup_bound
LOCK_SCHEMA_VERSION = "ebrt-role-uptake-stdlib-lock-v0.8.3.10"
RUN_SCHEMA_VERSION = "ebrt-role-uptake-stdlib-run-v0.8.3.10"
SELF_TEST_SCHEMA_VERSION = "ebrt-role-uptake-stdlib-self-test-v0.8.3.10"
CLAIM_BOUNDARY = (
    "This r11 execution repeats already observed cases only to bind the admitted CPython executable and imported file-backed standard-library code.",
    "The repeated outputs are contaminated by known r01-r10 results and are not fresh scientific replication evidence.",
    "r11 preserves the zero-call r10 preflight failure and calls the sealed base runner directly instead of re-entering an older exact-module wrapper.",
    "Both interpreters retain the -E -S startup boundary, verified-source cache bypass, and explicit site-package admission.",
    "Built-in and frozen modules are covered only through the interpreter executable; separately loaded system libraries are not attested.",
    "The receipt is not dyld, shared-system-library, hardware, kernel, code-signing, malicious-root, or scientific-effect attestation.",
    "All original v0.8.3 effect-attribution, one-model, public-role, and stop-gradient boundaries remain unchanged.",
)

JsonObject = dict[str, Any]


def _sha256(path: Path) -> str:
    return startup_bound.complete_bound._sha256(path)


def _load_json(path: Path) -> JsonObject:
    return startup_bound.complete_bound._load_json(path)


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    startup_bound.complete_bound._write_json(path, value)


def _runtime_identity_receipt() -> JsonObject:
    return stdlib_bound._runtime_identity_receipt()


def _validate_runtime_identity_shape(value: Any) -> JsonObject:
    return stdlib_bound._validate_runtime_identity_shape(value)


def _probe_execution_state(
    model_path: str,
) -> tuple[JsonObject, JsonObject, JsonObject, JsonObject]:
    code, source, startup = startup_bound._probe_execution_state(model_path)
    return code, source, startup, _runtime_identity_receipt()


def lock_spec(
    base_lock: Mapping[str, Any],
    source_lock: Mapping[str, Any],
    snapshot_lock: Mapping[str, Any],
    loader_lock: Mapping[str, Any],
    runtime_lock: Mapping[str, Any],
    immutable_lock: Mapping[str, Any],
    complete_lock: Mapping[str, Any],
    verified_source_lock: Mapping[str, Any],
    startup_lock: Mapping[str, Any],
    stdlib_lock: Mapping[str, Any],
    runtime_code: Mapping[str, Any],
    source_execution: Mapping[str, Any],
    startup_execution: Mapping[str, Any],
    runtime_identity: Mapping[str, Any],
) -> JsonObject:
    locked_stdlib = stdlib_bound.validate_lock(
        stdlib_lock,
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
        immutable_lock,
        complete_lock,
        verified_source_lock,
        startup_lock,
    )
    code = startup_bound.complete_bound._validate_runtime_code_shape(runtime_code)
    source = startup_bound.source_bound._validate_source_execution_shape(
        source_execution
    )
    startup = startup_bound._validate_startup_shape(startup_execution)
    identity = _validate_runtime_identity_shape(runtime_identity)
    return _seal(
        {
            "schema_version": LOCK_SCHEMA_VERSION,
            "status": "LOCKED_BEFORE_PROVIDER_CALLS",
            "wrapper_sha256": _sha256(Path(__file__)),
            "stdlib_lock_fingerprint_sha256": locked_stdlib["fingerprint_sha256"],
            "runtime_code": code,
            "runtime_code_fingerprint_sha256": code["fingerprint_sha256"],
            "source_execution": source,
            "source_execution_fingerprint_sha256": source["fingerprint_sha256"],
            "startup_execution": startup,
            "startup_execution_fingerprint_sha256": startup["fingerprint_sha256"],
            "runtime_identity": identity,
            "runtime_identity_fingerprint_sha256": identity["fingerprint_sha256"],
            "replication_status": "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R10_CASES",
            "effect_attribution_status": "NOT_ASSESSED",
            "claim_boundary": list(CLAIM_BOUNDARY),
        }
    )


def validate_lock(
    value: Any,
    base_lock: Mapping[str, Any],
    source_lock: Mapping[str, Any],
    snapshot_lock: Mapping[str, Any],
    loader_lock: Mapping[str, Any],
    runtime_lock: Mapping[str, Any],
    immutable_lock: Mapping[str, Any],
    complete_lock: Mapping[str, Any],
    verified_source_lock: Mapping[str, Any],
    startup_lock: Mapping[str, Any],
    stdlib_lock: Mapping[str, Any],
) -> JsonObject:
    observed = _sealed_snapshot(value, "ROLE_STDLIB_R11_LOCK")
    expected = lock_spec(
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
        immutable_lock,
        complete_lock,
        verified_source_lock,
        startup_lock,
        stdlib_lock,
        startup_bound.complete_bound._validate_runtime_code_shape(
            observed.get("runtime_code")
        ),
        startup_bound.source_bound._validate_source_execution_shape(
            observed.get("source_execution")
        ),
        startup_bound._validate_startup_shape(observed.get("startup_execution")),
        _validate_runtime_identity_shape(observed.get("runtime_identity")),
    )
    if _canonical_bytes(observed) != _canonical_bytes(expected):
        raise EBRTError("ROLE_STDLIB_R11_LOCK_MISMATCH")
    return observed


def run_integrity_replication(
    model_path: str,
    lock: Mapping[str, Any],
    base_lock: Mapping[str, Any],
    source_lock: Mapping[str, Any],
    snapshot_lock: Mapping[str, Any],
    loader_lock: Mapping[str, Any],
    runtime_lock: Mapping[str, Any],
    immutable_lock: Mapping[str, Any],
    complete_lock: Mapping[str, Any],
    verified_source_lock: Mapping[str, Any],
    startup_lock: Mapping[str, Any],
    stdlib_lock: Mapping[str, Any],
) -> JsonObject:
    locked = validate_lock(
        lock,
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
        immutable_lock,
        complete_lock,
        verified_source_lock,
        startup_lock,
        stdlib_lock,
    )
    code_before, source_before, startup_before, identity_before = (
        _probe_execution_state(model_path)
    )
    if (
        _canonical_bytes(code_before) != _canonical_bytes(locked["runtime_code"])
        or _canonical_bytes(source_before)
        != _canonical_bytes(locked["source_execution"])
        or _canonical_bytes(startup_before)
        != _canonical_bytes(locked["startup_execution"])
        or _canonical_bytes(identity_before)
        != _canonical_bytes(locked["runtime_identity"])
    ):
        raise EBRTError("ROLE_STDLIB_R11_PRECALL_STATE_MISMATCH")
    prior_run = startup_bound.immutable_bound.run_integrity_replication(
        model_path,
        immutable_lock,
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
    )
    startup_bound.complete_bound._verify_mount_receipt(
        prior_run.get("mount_receipt"), snapshot_lock
    )
    code_after = startup_bound.complete_bound._complete_runtime_code_receipt()
    source_after = startup_bound.source_bound._source_execution_receipt()
    startup_after = startup_bound._startup_receipt()
    identity_after = _runtime_identity_receipt()
    if (
        _canonical_bytes(code_after) != _canonical_bytes(locked["runtime_code"])
        or _canonical_bytes(source_after)
        != _canonical_bytes(locked["source_execution"])
        or _canonical_bytes(startup_after)
        != _canonical_bytes(locked["startup_execution"])
        or _canonical_bytes(identity_after)
        != _canonical_bytes(locked["runtime_identity"])
    ):
        raise EBRTError("ROLE_STDLIB_R11_POSTCALL_STATE_MISMATCH")
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
            "base_run": prior_run,
            "summary": prior_run["summary"],
            "replication_status": "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R10_CASES",
            "effect_attribution_status": "NOT_ASSESSED",
            "claim_boundary": list(CLAIM_BOUNDARY),
        }
    )


def verify_run(
    value: Any,
    lock: Mapping[str, Any],
    base_lock: Mapping[str, Any],
    source_lock: Mapping[str, Any],
    snapshot_lock: Mapping[str, Any],
    loader_lock: Mapping[str, Any],
    runtime_lock: Mapping[str, Any],
    immutable_lock: Mapping[str, Any],
    complete_lock: Mapping[str, Any],
    verified_source_lock: Mapping[str, Any],
    startup_lock: Mapping[str, Any],
    stdlib_lock: Mapping[str, Any],
) -> JsonObject:
    locked = validate_lock(
        lock,
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
        immutable_lock,
        complete_lock,
        verified_source_lock,
        startup_lock,
        stdlib_lock,
    )
    snapshot = _sealed_snapshot(value, "ROLE_STDLIB_R11_RUN")
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
    locked_identity = _validate_runtime_identity_shape(locked.get("runtime_identity"))
    if (
        set(snapshot) != expected_keys
        or snapshot.get("schema_version") != RUN_SCHEMA_VERSION
        or snapshot.get("status") != "COMPLETE"
        or snapshot.get("policy_lock_fingerprint_sha256")
        != locked["fingerprint_sha256"]
        or _canonical_bytes(snapshot.get("runtime_code_before"))
        != _canonical_bytes(locked_code)
        or _canonical_bytes(snapshot.get("runtime_code_after"))
        != _canonical_bytes(locked_code)
        or _canonical_bytes(snapshot.get("source_execution_before"))
        != _canonical_bytes(locked_source)
        or _canonical_bytes(snapshot.get("source_execution_after"))
        != _canonical_bytes(locked_source)
        or _canonical_bytes(snapshot.get("startup_execution_before"))
        != _canonical_bytes(locked_startup)
        or _canonical_bytes(snapshot.get("startup_execution_after"))
        != _canonical_bytes(locked_startup)
        or _canonical_bytes(snapshot.get("runtime_identity_before"))
        != _canonical_bytes(locked_identity)
        or _canonical_bytes(snapshot.get("runtime_identity_after"))
        != _canonical_bytes(locked_identity)
        or snapshot.get("replication_status")
        != "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R10_CASES"
        or snapshot.get("effect_attribution_status") != "NOT_ASSESSED"
        or snapshot.get("claim_boundary") != list(CLAIM_BOUNDARY)
    ):
        raise EBRTError("ROLE_STDLIB_R11_RUN_HEADER_INVALID")
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
        raise EBRTError("ROLE_STDLIB_R11_SUMMARY_MISMATCH")
    return _seal(
        {
            "schema_version": "ebrt-role-uptake-stdlib-verification-v0.8.3.10",
            "status": "PASS",
            "run_fingerprint_sha256": snapshot["fingerprint_sha256"],
            "base_verification_fingerprint_sha256": base_verification[
                "fingerprint_sha256"
            ],
            "checks": {
                "pre_call_lock_exact": True,
                "interpreter_executable_exact": True,
                "imported_stdlib_source_exact": True,
                "imported_stdlib_native_extensions_exact": True,
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


def self_test(
    base_lock: Mapping[str, Any],
    source_lock: Mapping[str, Any],
    snapshot_lock: Mapping[str, Any],
    loader_lock: Mapping[str, Any],
    runtime_lock: Mapping[str, Any],
    immutable_lock: Mapping[str, Any],
    complete_lock: Mapping[str, Any],
    verified_source_lock: Mapping[str, Any],
    startup_lock: Mapping[str, Any],
    stdlib_lock: Mapping[str, Any],
) -> JsonObject:
    locked_stdlib = stdlib_bound.validate_lock(
        stdlib_lock,
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
        immutable_lock,
        complete_lock,
        verified_source_lock,
        startup_lock,
    )
    stdlib_test = stdlib_bound.self_test(
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
        immutable_lock,
        complete_lock,
        verified_source_lock,
        startup_lock,
    )
    identity = _runtime_identity_receipt()
    stdlib = identity["standard_library"]
    checks = {
        "stdlib_lock_chain_exact": locked_stdlib["fingerprint_sha256"]
        == stdlib_lock["fingerprint_sha256"],
        "stdlib_self_test_passed": stdlib_test["status"] == "PASS",
        "outer_and_child_environment_ignored": sys.flags.ignore_environment == 1,
        "outer_and_child_site_disabled": sys.flags.no_site == 1,
        "source_only_child_active": os.environ.get(SOURCE_ONLY_CHILD_ENV) == "1",
        "interpreter_files_bound": len(identity["interpreter_files"]["files"]) == 2,
        "stdlib_source_modules_bound": stdlib["python_source_module_count"] > 0,
        "stdlib_native_modules_bound": stdlib["native_extension_module_count"] > 0,
        "stdlib_bytecode_cache_absent": stdlib["cached_bytecode_file_count"] == 0,
        "direct_base_runner_selected": True,
    }
    if not all(checks.values()):
        raise EBRTError("ROLE_STDLIB_R11_SELF_TEST_FAILED")
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
        base_lock = _load_json(args.base_lock)
        source_lock = _load_json(args.source_lock)
        snapshot_lock = _load_json(args.snapshot_lock)
        loader_lock = _load_json(args.loader_lock)
        runtime_lock = _load_json(args.runtime_lock)
        immutable_lock = _load_json(args.immutable_lock)
        complete_lock = _load_json(args.complete_lock)
        verified_source_lock = _load_json(args.verified_source_lock)
        startup_lock = _load_json(args.startup_lock)
        stdlib_lock = _load_json(args.stdlib_lock)
        locks = (
            base_lock,
            source_lock,
            snapshot_lock,
            loader_lock,
            runtime_lock,
            immutable_lock,
            complete_lock,
            verified_source_lock,
            startup_lock,
            stdlib_lock,
        )
        if args.command == "self-test":
            value = self_test(*locks)
        elif args.command == "probe-execution":
            code, source, startup, identity = _probe_execution_state(args.model)
            value = _seal(
                {
                    "runtime_code": code,
                    "source_execution": source,
                    "startup_execution": startup,
                    "runtime_identity": identity,
                }
            )
        elif args.command == "lock-spec":
            code, source, startup, identity = _probe_execution_state(args.model)
            value = lock_spec(*locks, code, source, startup, identity)
        elif args.command == "run":
            value = run_integrity_replication(
                args.model,
                _load_json(args.lock),
                *locks,
            )
            _write_json(args.output, value)
        elif args.command == "verify":
            value = verify_run(
                _load_json(args.artifact),
                _load_json(args.lock),
                *locks,
            )
        else:  # pragma: no cover
            raise EBRTError("ROLE_STDLIB_R11_COMMAND_UNKNOWN")
        print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (EBRTError, RuntimeError) as error:
        print(json.dumps({"status": "ERROR", "error_code": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
