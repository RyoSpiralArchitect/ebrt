#!/usr/bin/env python3
"""Startup-isolated execution wrapper for the EBRT v0.8.3 canary.

Invoke this CLI with ``python3 -E -S``.  The outer interpreter refuses
execution unless environment-driven Python paths and automatic site
initialization were disabled, then launches the admitted child with
``-E -S -B`` and a fresh empty ``pycache_prefix``.  Only the explicit framework
and user site-package directories are added afterward;
``.pth``, ``sitecustomize``, and ``usercustomize`` hooks are never processed.
The known-case repetition is integrity-only and is not fresh scientific data.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


SOURCE_ONLY_CHILD_ENV = "EBRT_V0838_SOURCE_ONLY_CHILD"
SOURCE_ONLY_PREFIX_ENV = "EBRT_V0838_SOURCE_ONLY_PREFIX"
PRIOR_CHILD_ENV = "EBRT_V0837_SOURCE_ONLY_CHILD"
PRIOR_PREFIX_ENV = "EBRT_V0837_SOURCE_ONLY_PREFIX"


def _bootstrap_isolated_child() -> None:
    if sys.flags.ignore_environment != 1 or sys.flags.no_site != 1:
        print(
            json.dumps(
                {
                    "status": "ERROR",
                    "error_code": "ROLE_STARTUP_ISOLATION_NOT_ENABLED",
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
                        "error_code": "ROLE_STARTUP_CHILD_POLICY_INVALID",
                    }
                )
            )
            raise SystemExit(2)
        return
    with tempfile.TemporaryDirectory(prefix="ebrt-v0838-pycache-") as temporary:
        prefix = Path(temporary).resolve()
        if any(prefix.iterdir()):
            print(
                json.dumps(
                    {
                        "status": "ERROR",
                        "error_code": "ROLE_STARTUP_PREFIX_NOT_EMPTY",
                    }
                )
            )
            raise SystemExit(2)
        environment = os.environ.copy()
        environment[SOURCE_ONLY_CHILD_ENV] = "1"
        environment[SOURCE_ONLY_PREFIX_ENV] = str(prefix)
        environment[PRIOR_CHILD_ENV] = "1"
        environment[PRIOR_PREFIX_ENV] = str(prefix)
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
                        "error_code": "ROLE_STARTUP_REEXEC_FAILED",
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
        raise RuntimeError("ROLE_STARTUP_SITE_PATHS_EMPTY")
    return paths


EXPLICIT_SITE_PATHS = _explicit_site_paths()
for _site_path in EXPLICIT_SITE_PATHS:
    if str(_site_path) not in sys.path:
        sys.path.append(str(_site_path))


import role_stratified_uptake_integrity_v0_8_3_5 as immutable_bound  # noqa: E402
import role_stratified_uptake_integrity_v0_8_3_6 as complete_bound  # noqa: E402
import role_stratified_uptake_integrity_v0_8_3_7 as source_bound  # noqa: E402
from ebrt_core import (  # noqa: E402
    EBRTError,
    _canonical_bytes,
    _fingerprint,
    _seal,
    _sealed_snapshot,
)


LOCK_SCHEMA_VERSION = "ebrt-role-uptake-startup-lock-v0.8.3.8"
RUN_SCHEMA_VERSION = "ebrt-role-uptake-startup-run-v0.8.3.8"
SELF_TEST_SCHEMA_VERSION = "ebrt-role-uptake-startup-self-test-v0.8.3.8"
CLAIM_BOUNDARY = (
    "This r09 execution repeats already observed cases only to exclude automatic Python startup customization from the admitted execution path.",
    "The repeated outputs are contaminated by known r01-r08 results and are not fresh scientific replication evidence.",
    "The outer and child interpreters require -E -S; explicit site-package directories are added only after the source-only cache policy is active.",
    "No .pth, sitecustomize, or usercustomize hook is processed in the admitted run; Python source and native content retain the r08/r07 receipts.",
    "The receipt is not hardware, kernel, code-signing, malicious-root, or scientific-effect attestation.",
    "All original v0.8.3 effect-attribution, one-model, public-role, and stop-gradient boundaries remain unchanged.",
)

JsonObject = dict[str, Any]


def _sha256(path: Path) -> str:
    return complete_bound._sha256(path)


def _load_json(path: Path) -> JsonObject:
    return complete_bound._load_json(path)


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    complete_bound._write_json(path, value)


def _startup_receipt() -> JsonObject:
    prefix_value = sys.pycache_prefix
    expected_prefix = os.environ.get(SOURCE_ONLY_PREFIX_ENV)
    if (
        sys.flags.ignore_environment != 1
        or sys.flags.no_site != 1
        or os.environ.get(SOURCE_ONLY_CHILD_ENV) != "1"
        or not sys.dont_write_bytecode
        or prefix_value is None
        or expected_prefix is None
        or Path(prefix_value).resolve() != Path(expected_prefix).resolve()
        or any(Path(prefix_value).resolve().rglob("*"))
        or "sitecustomize" in sys.modules
        or "usercustomize" in sys.modules
    ):
        raise EBRTError("ROLE_STARTUP_POLICY_INACTIVE")
    path_rows = [
        {
            "path": str(path),
            "exists": path.is_dir(),
        }
        for path in EXPLICIT_SITE_PATHS
    ]
    return _seal(
        {
            "schema_version": "ebrt-startup-execution-receipt-v0.8.3.8",
            "python_environment_ignored": True,
            "startup_site_disabled": True,
            "pth_processing_disabled": True,
            "sitecustomize_disabled": True,
            "usercustomize_disabled": True,
            "fresh_empty_pycache_prefix": True,
            "bytecode_writes_disabled": True,
            "explicit_site_paths": path_rows,
            "explicit_site_path_fingerprint_sha256": _fingerprint(path_rows),
        }
    )


def _probe_execution_state(
    model_path: str,
) -> tuple[JsonObject, JsonObject, JsonObject]:
    immutable_bound.probe_runtime_code(model_path)
    return (
        complete_bound._complete_runtime_code_receipt(),
        source_bound._source_execution_receipt(),
        _startup_receipt(),
    )


def _validate_startup_shape(value: Any) -> JsonObject:
    receipt = _sealed_snapshot(value, "ROLE_STARTUP_EXECUTION")
    paths = receipt.get("explicit_site_paths")
    if (
        set(receipt)
        != {
            "schema_version",
            "python_environment_ignored",
            "startup_site_disabled",
            "pth_processing_disabled",
            "sitecustomize_disabled",
            "usercustomize_disabled",
            "fresh_empty_pycache_prefix",
            "bytecode_writes_disabled",
            "explicit_site_paths",
            "explicit_site_path_fingerprint_sha256",
            "fingerprint_sha256",
        }
        or receipt.get("schema_version") != "ebrt-startup-execution-receipt-v0.8.3.8"
        or any(
            receipt.get(key) is not True
            for key in (
                "startup_site_disabled",
                "python_environment_ignored",
                "pth_processing_disabled",
                "sitecustomize_disabled",
                "usercustomize_disabled",
                "fresh_empty_pycache_prefix",
                "bytecode_writes_disabled",
            )
        )
        or not isinstance(paths, list)
        or not paths
        or any(
            not isinstance(row, Mapping)
            or set(row) != {"path", "exists"}
            or not isinstance(row.get("path"), str)
            or not Path(row["path"]).is_absolute()
            or row.get("exists") is not True
            for row in paths
        )
        or receipt.get("explicit_site_path_fingerprint_sha256") != _fingerprint(paths)
    ):
        raise EBRTError("ROLE_STARTUP_EXECUTION_SHAPE_INVALID")
    return receipt


def lock_spec(
    base_lock: Mapping[str, Any],
    source_lock: Mapping[str, Any],
    snapshot_lock: Mapping[str, Any],
    loader_lock: Mapping[str, Any],
    runtime_lock: Mapping[str, Any],
    immutable_lock: Mapping[str, Any],
    complete_lock: Mapping[str, Any],
    verified_source_lock: Mapping[str, Any],
    runtime_code: Mapping[str, Any],
    source_execution: Mapping[str, Any],
    startup_execution: Mapping[str, Any],
) -> JsonObject:
    locked_source = source_bound.validate_lock(
        verified_source_lock,
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
        immutable_lock,
        complete_lock,
    )
    code = complete_bound._validate_runtime_code_shape(runtime_code)
    source = source_bound._validate_source_execution_shape(source_execution)
    startup = _validate_startup_shape(startup_execution)
    return _seal(
        {
            "schema_version": LOCK_SCHEMA_VERSION,
            "status": "LOCKED_BEFORE_PROVIDER_CALLS",
            "wrapper_sha256": _sha256(Path(__file__)),
            "verified_source_lock_fingerprint_sha256": locked_source[
                "fingerprint_sha256"
            ],
            "runtime_code": code,
            "runtime_code_fingerprint_sha256": code["fingerprint_sha256"],
            "source_execution": source,
            "source_execution_fingerprint_sha256": source["fingerprint_sha256"],
            "startup_execution": startup,
            "startup_execution_fingerprint_sha256": startup["fingerprint_sha256"],
            "replication_status": "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R08_CASES",
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
) -> JsonObject:
    observed = _sealed_snapshot(value, "ROLE_STARTUP_LOCK")
    expected = lock_spec(
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
        immutable_lock,
        complete_lock,
        verified_source_lock,
        complete_bound._validate_runtime_code_shape(observed.get("runtime_code")),
        source_bound._validate_source_execution_shape(observed.get("source_execution")),
        _validate_startup_shape(observed.get("startup_execution")),
    )
    if _canonical_bytes(observed) != _canonical_bytes(expected):
        raise EBRTError("ROLE_STARTUP_LOCK_MISMATCH")
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
    )
    code_before, source_before, startup_before = _probe_execution_state(model_path)
    if (
        _canonical_bytes(code_before) != _canonical_bytes(locked["runtime_code"])
        or _canonical_bytes(source_before)
        != _canonical_bytes(locked["source_execution"])
        or _canonical_bytes(startup_before)
        != _canonical_bytes(locked["startup_execution"])
    ):
        raise EBRTError("ROLE_STARTUP_PRECALL_STATE_MISMATCH")
    prior_run = immutable_bound.run_integrity_replication(
        model_path,
        immutable_lock,
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
    )
    complete_bound._verify_mount_receipt(prior_run.get("mount_receipt"), snapshot_lock)
    code_after = complete_bound._complete_runtime_code_receipt()
    source_after = source_bound._source_execution_receipt()
    startup_after = _startup_receipt()
    if (
        _canonical_bytes(code_after) != _canonical_bytes(locked["runtime_code"])
        or _canonical_bytes(source_after)
        != _canonical_bytes(locked["source_execution"])
        or _canonical_bytes(startup_after)
        != _canonical_bytes(locked["startup_execution"])
    ):
        raise EBRTError("ROLE_STARTUP_POSTCALL_STATE_MISMATCH")
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
            "prior_run": prior_run,
            "summary": prior_run["summary"],
            "replication_status": "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R08_CASES",
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
    )
    snapshot = _sealed_snapshot(value, "ROLE_STARTUP_RUN")
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
        "prior_run",
        "summary",
        "replication_status",
        "effect_attribution_status",
        "claim_boundary",
        "fingerprint_sha256",
    }
    locked_code = complete_bound._validate_runtime_code_shape(
        locked.get("runtime_code")
    )
    locked_source = source_bound._validate_source_execution_shape(
        locked.get("source_execution")
    )
    locked_startup = _validate_startup_shape(locked.get("startup_execution"))
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
        or snapshot.get("replication_status")
        != "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R08_CASES"
        or snapshot.get("effect_attribution_status") != "NOT_ASSESSED"
        or snapshot.get("claim_boundary") != list(CLAIM_BOUNDARY)
    ):
        raise EBRTError("ROLE_STARTUP_RUN_HEADER_INVALID")
    prior_verification = immutable_bound.verify_run(
        snapshot.get("prior_run"),
        immutable_lock,
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
    )
    complete_bound._verify_mount_receipt(
        snapshot["prior_run"].get("mount_receipt"), snapshot_lock
    )
    if _canonical_bytes(snapshot.get("summary")) != _canonical_bytes(
        snapshot["prior_run"]["summary"]
    ):
        raise EBRTError("ROLE_STARTUP_SUMMARY_MISMATCH")
    return _seal(
        {
            "schema_version": "ebrt-role-uptake-startup-verification-v0.8.3.8",
            "status": "PASS",
            "run_fingerprint_sha256": snapshot["fingerprint_sha256"],
            "prior_verification_fingerprint_sha256": prior_verification[
                "fingerprint_sha256"
            ],
            "checks": {
                "pre_call_lock_exact": True,
                "python_environment_ignored": True,
                "startup_site_disabled": True,
                "pth_processing_disabled": True,
                "sitecustomize_disabled": True,
                "usercustomize_disabled": True,
                "fresh_empty_pycache_prefix": True,
                "adjacent_bytecode_cache_bypassed": True,
                "bytecode_writes_disabled": True,
                "complete_runtime_code_receipt_exact": True,
                "mount_receipt_matches_locked_snapshot": True,
                "known_case_replication_boundary_exact": True,
            },
        }
    )


def _customization_hook_self_test() -> bool:
    with tempfile.TemporaryDirectory(prefix="ebrt-v0838-site-hook-") as temporary:
        root = Path(temporary)
        (root / "sitecustomize.py").write_text(
            "print('CUSTOMIZATION_HOOK')\n", encoding="utf-8"
        )
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(root)
        regular = subprocess.run(
            [sys.executable, "-c", "print('BODY')"],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )
        isolated = subprocess.run(
            [sys.executable, "-E", "-S", "-c", "print('BODY')"],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )
        return (
            regular.returncode == 0
            and regular.stdout.splitlines() == ["CUSTOMIZATION_HOOK", "BODY"]
            and isolated.returncode == 0
            and isolated.stdout.splitlines() == ["BODY"]
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
) -> JsonObject:
    locked_source = source_bound.validate_lock(
        verified_source_lock,
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
        immutable_lock,
        complete_lock,
    )
    checks = {
        "verified_source_lock_chain_exact": locked_source["fingerprint_sha256"]
        == verified_source_lock["fingerprint_sha256"],
        "outer_and_child_environment_ignored": sys.flags.ignore_environment == 1,
        "outer_and_child_site_disabled": sys.flags.no_site == 1,
        "source_only_child_active": os.environ.get(SOURCE_ONLY_CHILD_ENV) == "1",
        "bytecode_writes_disabled": sys.dont_write_bytecode,
        "fresh_pycache_prefix_active": sys.pycache_prefix is not None,
        "pycache_prefix_remains_empty": not any(
            Path(sys.pycache_prefix).resolve().rglob("*")
        ),
        "sitecustomize_and_usercustomize_absent": "sitecustomize" not in sys.modules
        and "usercustomize" not in sys.modules,
        "timestamp_valid_divergent_pyc_bypassed": source_bound._bytecode_divergence_self_test(),
        "startup_customization_hook_bypassed": _customization_hook_self_test(),
    }
    if not all(checks.values()):
        raise EBRTError("ROLE_STARTUP_SELF_TEST_FAILED")
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
        if args.command == "self-test":
            value = self_test(
                base_lock,
                source_lock,
                snapshot_lock,
                loader_lock,
                runtime_lock,
                immutable_lock,
                complete_lock,
                verified_source_lock,
            )
        elif args.command == "probe-execution":
            code, source, startup = _probe_execution_state(args.model)
            value = _seal(
                {
                    "runtime_code": code,
                    "source_execution": source,
                    "startup_execution": startup,
                }
            )
        elif args.command == "lock-spec":
            code, source, startup = _probe_execution_state(args.model)
            value = lock_spec(
                base_lock,
                source_lock,
                snapshot_lock,
                loader_lock,
                runtime_lock,
                immutable_lock,
                complete_lock,
                verified_source_lock,
                code,
                source,
                startup,
            )
        elif args.command == "run":
            value = run_integrity_replication(
                args.model,
                _load_json(args.lock),
                base_lock,
                source_lock,
                snapshot_lock,
                loader_lock,
                runtime_lock,
                immutable_lock,
                complete_lock,
                verified_source_lock,
            )
            _write_json(args.output, value)
        elif args.command == "verify":
            value = verify_run(
                _load_json(args.artifact),
                _load_json(args.lock),
                base_lock,
                source_lock,
                snapshot_lock,
                loader_lock,
                runtime_lock,
                immutable_lock,
                complete_lock,
                verified_source_lock,
            )
        else:  # pragma: no cover
            raise EBRTError("ROLE_STARTUP_COMMAND_UNKNOWN")
        print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (EBRTError, RuntimeError) as error:
        print(json.dumps({"status": "ERROR", "error_code": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
