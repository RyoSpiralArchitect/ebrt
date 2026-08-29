#!/usr/bin/env python3
"""Interpreter- and stdlib-bound wrapper for the EBRT v0.8.3 canary.

Invoke this CLI with ``python3 -E -S``. The admitted child preserves the r09
startup and source-cache isolation, then additionally binds the resolved Python
interpreter executable and every imported file-backed standard-library module.
The known-case repetition is integrity-only and is not fresh scientific data.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


SOURCE_ONLY_CHILD_ENV = "EBRT_V0839_SOURCE_ONLY_CHILD"
SOURCE_ONLY_PREFIX_ENV = "EBRT_V0839_SOURCE_ONLY_PREFIX"
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
                    "error_code": "ROLE_STDLIB_STARTUP_ISOLATION_NOT_ENABLED",
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
                        "error_code": "ROLE_STDLIB_CHILD_POLICY_INVALID",
                    }
                )
            )
            raise SystemExit(2)
        return
    with tempfile.TemporaryDirectory(prefix="ebrt-v0839-pycache-") as temporary:
        prefix = Path(temporary).resolve()
        if any(prefix.iterdir()):
            print(
                json.dumps(
                    {
                        "status": "ERROR",
                        "error_code": "ROLE_STDLIB_PREFIX_NOT_EMPTY",
                    }
                )
            )
            raise SystemExit(2)
        environment = os.environ.copy()
        for child_name in (SOURCE_ONLY_CHILD_ENV, R09_CHILD_ENV, R08_CHILD_ENV):
            environment[child_name] = "1"
        for prefix_name in (SOURCE_ONLY_PREFIX_ENV, R09_PREFIX_ENV, R08_PREFIX_ENV):
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
                        "error_code": "ROLE_STDLIB_REEXEC_FAILED",
                    }
                )
            )
            raise SystemExit(2) from None
        raise SystemExit(completed.returncode)


if __name__ == "__main__":
    _bootstrap_isolated_child()


import argparse  # noqa: E402
import importlib.machinery  # noqa: E402
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
        raise RuntimeError("ROLE_STDLIB_SITE_PATHS_EMPTY")
    return paths


EXPLICIT_SITE_PATHS = _explicit_site_paths()
for _site_path in EXPLICIT_SITE_PATHS:
    if str(_site_path) not in sys.path:
        sys.path.append(str(_site_path))


import role_stratified_uptake_integrity_v0_8_3_8 as startup_bound  # noqa: E402
from ebrt_core import (  # noqa: E402
    EBRTError,
    _canonical_bytes,
    _fingerprint,
    _seal,
    _sealed_snapshot,
)


LOCK_SCHEMA_VERSION = "ebrt-role-uptake-stdlib-lock-v0.8.3.9"
RUN_SCHEMA_VERSION = "ebrt-role-uptake-stdlib-run-v0.8.3.9"
SELF_TEST_SCHEMA_VERSION = "ebrt-role-uptake-stdlib-self-test-v0.8.3.9"
CLAIM_BOUNDARY = (
    "This r10 execution repeats already observed cases only to bind the admitted CPython executable and imported file-backed standard-library code.",
    "The repeated outputs are contaminated by known r01-r09 results and are not fresh scientific replication evidence.",
    "Both interpreters retain the r09 -E -S startup boundary, verified-source cache bypass, and explicit site-package admission.",
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


def _interpreter_file_receipt() -> JsonObject:
    configured = (
        ("sys.executable", sys.executable),
        ("sys._base_executable", getattr(sys, "_base_executable", None)),
    )
    rows: list[JsonObject] = []
    for role, value in configured:
        if not isinstance(value, str) or not value:
            raise EBRTError("ROLE_STDLIB_INTERPRETER_PATH_MISSING")
        invocation_path = Path(value)
        try:
            resolved = invocation_path.resolve(strict=True)
        except OSError as error:
            raise EBRTError("ROLE_STDLIB_INTERPRETER_PATH_MISSING") from error
        if not resolved.is_file():
            raise EBRTError("ROLE_STDLIB_INTERPRETER_NOT_FILE")
        rows.append(
            {
                "role": role,
                "invocation_path": str(invocation_path),
                "resolved_path": str(resolved),
                "invocation_is_symlink": invocation_path.is_symlink(),
                "size_bytes": resolved.stat().st_size,
                "sha256": _sha256(resolved),
            }
        )
    rows.sort(key=lambda row: row["role"])
    return _seal(
        {
            "schema_version": "ebrt-interpreter-file-receipt-v0.8.3.9",
            "files": rows,
            "file_manifest_fingerprint_sha256": _fingerprint(rows),
        }
    )


def _standard_library_receipt() -> JsonObject:
    stdlib_root = Path(sysconfig.get_paths()["stdlib"]).resolve(strict=True)
    extension_suffixes = tuple(importlib.machinery.EXTENSION_SUFFIXES)
    rows: list[JsonObject] = []
    source_count = 0
    native_count = 0
    for module_name, module in sorted(sys.modules.items()):
        if module_name in {"__main__", "__mp_main__"}:
            continue
        origin = startup_bound.complete_bound._module_origin(module_name, module)
        if origin is None:
            continue
        relative = startup_bound.complete_bound._relative_to(origin, stdlib_root)
        under_site = any(
            startup_bound.complete_bound._relative_to(origin, root) is not None
            for root in EXPLICIT_SITE_PATHS
        )
        if relative is None or under_site:
            continue
        cached_value = getattr(module, "__cached__", None)
        cached_exists = (
            isinstance(cached_value, (str, os.PathLike)) and Path(cached_value).exists()
        )
        if origin.suffix == ".py":
            if cached_exists:
                raise EBRTError("ROLE_STDLIB_CACHED_BYTECODE_PRESENT")
            execution_kind = "VERIFIED_STDLIB_SOURCE_WITH_CACHE_BYPASSED"
            source_count += 1
        elif any(str(origin).endswith(suffix) for suffix in extension_suffixes):
            execution_kind = "BOUND_STDLIB_NATIVE_EXTENSION"
            native_count += 1
        else:
            raise EBRTError("ROLE_STDLIB_ORIGIN_KIND_UNSUPPORTED")
        rows.append(
            {
                "module": module_name,
                "stdlib_relative_path": relative.as_posix(),
                "execution_kind": execution_kind,
                "size_bytes": origin.stat().st_size,
                "sha256": _sha256(origin),
                "cached_bytecode_present": cached_exists,
            }
        )
    if not rows or source_count <= 0 or native_count <= 0:
        raise EBRTError("ROLE_STDLIB_MODULE_SET_INCOMPLETE")
    return _seal(
        {
            "schema_version": "ebrt-standard-library-receipt-v0.8.3.9",
            "stdlib_root": str(stdlib_root),
            "module_count": len(rows),
            "python_source_module_count": source_count,
            "native_extension_module_count": native_count,
            "cached_bytecode_file_count": 0,
            "modules": rows,
            "module_manifest_fingerprint_sha256": _fingerprint(rows),
        }
    )


def _runtime_identity_receipt() -> JsonObject:
    interpreter = _interpreter_file_receipt()
    standard_library = _standard_library_receipt()
    return _seal(
        {
            "schema_version": "ebrt-runtime-identity-receipt-v0.8.3.9",
            "interpreter_files": interpreter,
            "standard_library": standard_library,
        }
    )


def _validate_interpreter_shape(value: Any) -> JsonObject:
    receipt = _sealed_snapshot(value, "ROLE_STDLIB_INTERPRETER")
    rows = receipt.get("files")
    if (
        set(receipt)
        != {
            "schema_version",
            "files",
            "file_manifest_fingerprint_sha256",
            "fingerprint_sha256",
        }
        or receipt.get("schema_version") != "ebrt-interpreter-file-receipt-v0.8.3.9"
        or not isinstance(rows, list)
        or len(rows) != 2
        or {row.get("role") for row in rows if isinstance(row, Mapping)}
        != {"sys.executable", "sys._base_executable"}
        or any(
            not isinstance(row, Mapping)
            or set(row)
            != {
                "role",
                "invocation_path",
                "resolved_path",
                "invocation_is_symlink",
                "size_bytes",
                "sha256",
            }
            or not isinstance(row.get("invocation_path"), str)
            or not isinstance(row.get("resolved_path"), str)
            or not Path(row["invocation_path"]).is_absolute()
            or not Path(row["resolved_path"]).is_absolute()
            or type(row.get("invocation_is_symlink")) is not bool
            or type(row.get("size_bytes")) is not int
            or row["size_bytes"] <= 0
            or not isinstance(row.get("sha256"), str)
            or len(row["sha256"]) != 64
            for row in rows
        )
        or receipt.get("file_manifest_fingerprint_sha256") != _fingerprint(rows)
    ):
        raise EBRTError("ROLE_STDLIB_INTERPRETER_SHAPE_INVALID")
    return receipt


def _validate_standard_library_shape(value: Any) -> JsonObject:
    receipt = _sealed_snapshot(value, "ROLE_STDLIB_MODULES")
    rows = receipt.get("modules")
    if (
        set(receipt)
        != {
            "schema_version",
            "stdlib_root",
            "module_count",
            "python_source_module_count",
            "native_extension_module_count",
            "cached_bytecode_file_count",
            "modules",
            "module_manifest_fingerprint_sha256",
            "fingerprint_sha256",
        }
        or receipt.get("schema_version") != "ebrt-standard-library-receipt-v0.8.3.9"
        or not isinstance(receipt.get("stdlib_root"), str)
        or not Path(receipt["stdlib_root"]).is_absolute()
        or not isinstance(rows, list)
        or not rows
        or type(receipt.get("module_count")) is not int
        or type(receipt.get("python_source_module_count")) is not int
        or type(receipt.get("native_extension_module_count")) is not int
        or receipt["module_count"] != len(rows)
        or receipt["module_count"]
        != receipt["python_source_module_count"]
        + receipt["native_extension_module_count"]
        or receipt["python_source_module_count"] <= 0
        or receipt["native_extension_module_count"] <= 0
        or receipt.get("cached_bytecode_file_count") != 0
        or any(
            not isinstance(row, Mapping)
            or set(row)
            != {
                "module",
                "stdlib_relative_path",
                "execution_kind",
                "size_bytes",
                "sha256",
                "cached_bytecode_present",
            }
            or not isinstance(row.get("module"), str)
            or not row["module"]
            or not isinstance(row.get("stdlib_relative_path"), str)
            or Path(row["stdlib_relative_path"]).is_absolute()
            or row.get("execution_kind")
            not in {
                "VERIFIED_STDLIB_SOURCE_WITH_CACHE_BYPASSED",
                "BOUND_STDLIB_NATIVE_EXTENSION",
            }
            or type(row.get("size_bytes")) is not int
            or row["size_bytes"] < 0
            or not isinstance(row.get("sha256"), str)
            or len(row["sha256"]) != 64
            or row.get("cached_bytecode_present") is not False
            for row in rows
        )
        or receipt.get("module_manifest_fingerprint_sha256") != _fingerprint(rows)
    ):
        raise EBRTError("ROLE_STDLIB_MODULE_SHAPE_INVALID")
    return receipt


def _validate_runtime_identity_shape(value: Any) -> JsonObject:
    receipt = _sealed_snapshot(value, "ROLE_STDLIB_RUNTIME_IDENTITY")
    if (
        set(receipt)
        != {
            "schema_version",
            "interpreter_files",
            "standard_library",
            "fingerprint_sha256",
        }
        or receipt.get("schema_version") != "ebrt-runtime-identity-receipt-v0.8.3.9"
    ):
        raise EBRTError("ROLE_STDLIB_RUNTIME_IDENTITY_SHAPE_INVALID")
    _validate_interpreter_shape(receipt.get("interpreter_files"))
    _validate_standard_library_shape(receipt.get("standard_library"))
    return receipt


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
    runtime_code: Mapping[str, Any],
    source_execution: Mapping[str, Any],
    startup_execution: Mapping[str, Any],
    runtime_identity: Mapping[str, Any],
) -> JsonObject:
    locked_startup = startup_bound.validate_lock(
        startup_lock,
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
        immutable_lock,
        complete_lock,
        verified_source_lock,
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
            "startup_lock_fingerprint_sha256": locked_startup["fingerprint_sha256"],
            "runtime_code": code,
            "runtime_code_fingerprint_sha256": code["fingerprint_sha256"],
            "source_execution": source,
            "source_execution_fingerprint_sha256": source["fingerprint_sha256"],
            "startup_execution": startup,
            "startup_execution_fingerprint_sha256": startup["fingerprint_sha256"],
            "runtime_identity": identity,
            "runtime_identity_fingerprint_sha256": identity["fingerprint_sha256"],
            "replication_status": "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R09_CASES",
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
) -> JsonObject:
    observed = _sealed_snapshot(value, "ROLE_STDLIB_LOCK")
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
        raise EBRTError("ROLE_STDLIB_LOCK_MISMATCH")
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
        raise EBRTError("ROLE_STDLIB_PRECALL_STATE_MISMATCH")
    prior_run = startup_bound.run_integrity_replication(
        model_path,
        startup_lock,
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
        immutable_lock,
        complete_lock,
        verified_source_lock,
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
        raise EBRTError("ROLE_STDLIB_POSTCALL_STATE_MISMATCH")
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
            "prior_run": prior_run,
            "summary": prior_run["summary"],
            "replication_status": "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R09_CASES",
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
    )
    snapshot = _sealed_snapshot(value, "ROLE_STDLIB_RUN")
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
        "prior_run",
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
        != "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R09_CASES"
        or snapshot.get("effect_attribution_status") != "NOT_ASSESSED"
        or snapshot.get("claim_boundary") != list(CLAIM_BOUNDARY)
    ):
        raise EBRTError("ROLE_STDLIB_RUN_HEADER_INVALID")
    prior_verification = startup_bound.verify_run(
        snapshot.get("prior_run"),
        startup_lock,
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
        immutable_lock,
        complete_lock,
        verified_source_lock,
    )
    if _canonical_bytes(snapshot.get("summary")) != _canonical_bytes(
        snapshot["prior_run"]["summary"]
    ):
        raise EBRTError("ROLE_STDLIB_SUMMARY_MISMATCH")
    return _seal(
        {
            "schema_version": "ebrt-role-uptake-stdlib-verification-v0.8.3.9",
            "status": "PASS",
            "run_fingerprint_sha256": snapshot["fingerprint_sha256"],
            "prior_verification_fingerprint_sha256": prior_verification[
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
                "known_case_replication_boundary_exact": True,
            },
        }
    )


def _tamper_rejection_self_test(value: Mapping[str, Any]) -> bool:
    tampered = json.loads(json.dumps(value))
    tampered["interpreter_files"]["files"][0]["sha256"] = "0" * 64
    try:
        _validate_runtime_identity_shape(tampered)
    except EBRTError:
        return True
    return False


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
) -> JsonObject:
    locked_startup = startup_bound.validate_lock(
        startup_lock,
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
        immutable_lock,
        complete_lock,
        verified_source_lock,
    )
    startup_test = startup_bound.self_test(
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
        immutable_lock,
        complete_lock,
        verified_source_lock,
    )
    identity = _runtime_identity_receipt()
    stdlib = identity["standard_library"]
    checks = {
        "startup_lock_chain_exact": locked_startup["fingerprint_sha256"]
        == startup_lock["fingerprint_sha256"],
        "startup_self_test_passed": startup_test["status"] == "PASS",
        "outer_and_child_environment_ignored": sys.flags.ignore_environment == 1,
        "outer_and_child_site_disabled": sys.flags.no_site == 1,
        "source_only_child_active": os.environ.get(SOURCE_ONLY_CHILD_ENV) == "1",
        "interpreter_files_bound": len(identity["interpreter_files"]["files"]) == 2,
        "stdlib_source_modules_bound": stdlib["python_source_module_count"] > 0,
        "stdlib_native_modules_bound": stdlib["native_extension_module_count"] > 0,
        "stdlib_bytecode_cache_absent": stdlib["cached_bytecode_file_count"] == 0,
        "runtime_identity_tamper_rejected": _tamper_rejection_self_test(identity),
    }
    if not all(checks.values()):
        raise EBRTError("ROLE_STDLIB_SELF_TEST_FAILED")
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
            raise EBRTError("ROLE_STDLIB_COMMAND_UNKNOWN")
        print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (EBRTError, RuntimeError) as error:
        print(json.dumps({"status": "ERROR", "error_code": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
