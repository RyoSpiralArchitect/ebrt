#!/usr/bin/env python3
"""Stable stdlib-tree execution wrapper for the EBRT v0.8.3 canary.

Invoke with ``python3 -E -S``. This r12 successor locks the interpreter plus
the complete standard-library Python/native code tree before provider calls.
Imported-module coverage is checked independently before and after generation,
so legitimate lazy imports do not change the locked code universe. The known
cases are repeated for integrity only, not as fresh scientific evidence.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


SOURCE_ONLY_CHILD_ENV = "EBRT_V08311_SOURCE_ONLY_CHILD"
SOURCE_ONLY_PREFIX_ENV = "EBRT_V08311_SOURCE_ONLY_PREFIX"
PRIOR_CHILD_ENVS = (
    "EBRT_V08310_SOURCE_ONLY_CHILD",
    "EBRT_V0839_SOURCE_ONLY_CHILD",
    "EBRT_V0838_SOURCE_ONLY_CHILD",
    "EBRT_V0837_SOURCE_ONLY_CHILD",
)
PRIOR_PREFIX_ENVS = (
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
                    "error_code": "ROLE_STDLIB_TREE_STARTUP_ISOLATION_NOT_ENABLED",
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
                        "error_code": "ROLE_STDLIB_TREE_CHILD_POLICY_INVALID",
                    }
                )
            )
            raise SystemExit(2)
        return
    with tempfile.TemporaryDirectory(prefix="ebrt-v08311-pycache-") as temporary:
        prefix = Path(temporary).resolve()
        if any(prefix.iterdir()):
            print(
                json.dumps(
                    {
                        "status": "ERROR",
                        "error_code": "ROLE_STDLIB_TREE_PREFIX_NOT_EMPTY",
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
                        "error_code": "ROLE_STDLIB_TREE_REEXEC_FAILED",
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
        raise RuntimeError("ROLE_STDLIB_TREE_SITE_PATHS_EMPTY")
    return paths


EXPLICIT_SITE_PATHS = _explicit_site_paths()
for _site_path in EXPLICIT_SITE_PATHS:
    if str(_site_path) not in sys.path:
        sys.path.append(str(_site_path))


import role_stratified_uptake_integrity_v0_8_3_10 as imported_bound  # noqa: E402
from ebrt_core import (  # noqa: E402
    EBRTError,
    _canonical_bytes,
    _fingerprint,
    _seal,
    _sealed_snapshot,
)


stdlib_bound = imported_bound.stdlib_bound
startup_bound = imported_bound.startup_bound
LOCK_SCHEMA_VERSION = "ebrt-role-uptake-stdlib-tree-lock-v0.8.3.11"
RUN_SCHEMA_VERSION = "ebrt-role-uptake-stdlib-tree-run-v0.8.3.11"
SELF_TEST_SCHEMA_VERSION = "ebrt-role-uptake-stdlib-tree-self-test-v0.8.3.11"
CLAIM_BOUNDARY = (
    "This r12 execution repeats already observed cases only to bind the admitted CPython executable and complete standard-library Python/native code tree.",
    "The repeated outputs are contaminated by known r01-r11 results and are not fresh scientific replication evidence.",
    "Imported stdlib coverage is checked against the locked tree before and after calls without requiring an identical lazy-import set.",
    "Both interpreters retain the -E -S startup boundary, verified-source cache bypass, and explicit site-package admission.",
    "Built-in and frozen modules are covered only through the interpreter executable; separately loaded system libraries and non-code stdlib data are not attested.",
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


def _stdlib_root() -> Path:
    return Path(sysconfig.get_paths()["stdlib"]).resolve(strict=True)


def _under_explicit_site(path: Path) -> bool:
    return any(
        startup_bound.complete_bound._relative_to(path, root) is not None
        for root in EXPLICIT_SITE_PATHS
    )


def _stdlib_code_tree_receipt() -> JsonObject:
    root = _stdlib_root()
    extension_suffixes = tuple(importlib.machinery.EXTENSION_SUFFIXES)
    rows: list[JsonObject] = []
    source_count = 0
    native_count = 0
    for candidate in sorted(root.rglob("*"), key=lambda path: path.as_posix()):
        if (
            not candidate.is_file()
            or candidate.is_symlink()
            or _under_explicit_site(candidate)
            or "__pycache__" in candidate.parts
        ):
            continue
        if candidate.suffix == ".py":
            execution_kind = "STDLIB_PYTHON_SOURCE"
            source_count += 1
        elif any(str(candidate).endswith(suffix) for suffix in extension_suffixes):
            execution_kind = "STDLIB_NATIVE_EXTENSION"
            native_count += 1
        else:
            continue
        relative = candidate.relative_to(root).as_posix()
        rows.append(
            {
                "stdlib_relative_path": relative,
                "execution_kind": execution_kind,
                "size_bytes": candidate.stat().st_size,
                "sha256": _sha256(candidate),
            }
        )
    if not rows or source_count <= 0 or native_count <= 0:
        raise EBRTError("ROLE_STDLIB_TREE_EMPTY")
    return _seal(
        {
            "schema_version": "ebrt-standard-library-code-tree-v0.8.3.11",
            "stdlib_root": str(root),
            "file_count": len(rows),
            "python_source_file_count": source_count,
            "native_extension_file_count": native_count,
            "files": rows,
            "file_manifest_fingerprint_sha256": _fingerprint(rows),
        }
    )


def _runtime_identity_receipt() -> JsonObject:
    interpreter = stdlib_bound._interpreter_file_receipt()
    code_tree = _stdlib_code_tree_receipt()
    return _seal(
        {
            "schema_version": "ebrt-runtime-tree-identity-v0.8.3.11",
            "interpreter_files": interpreter,
            "standard_library_code_tree": code_tree,
        }
    )


def _validate_code_tree_shape(value: Any) -> JsonObject:
    receipt = _sealed_snapshot(value, "ROLE_STDLIB_TREE")
    rows = receipt.get("files")
    if (
        set(receipt)
        != {
            "schema_version",
            "stdlib_root",
            "file_count",
            "python_source_file_count",
            "native_extension_file_count",
            "files",
            "file_manifest_fingerprint_sha256",
            "fingerprint_sha256",
        }
        or receipt.get("schema_version") != "ebrt-standard-library-code-tree-v0.8.3.11"
        or not isinstance(receipt.get("stdlib_root"), str)
        or not Path(receipt["stdlib_root"]).is_absolute()
        or not isinstance(rows, list)
        or not rows
        or type(receipt.get("file_count")) is not int
        or type(receipt.get("python_source_file_count")) is not int
        or type(receipt.get("native_extension_file_count")) is not int
        or receipt["file_count"] != len(rows)
        or receipt["file_count"]
        != receipt["python_source_file_count"] + receipt["native_extension_file_count"]
        or receipt["python_source_file_count"] <= 0
        or receipt["native_extension_file_count"] <= 0
        or any(
            not isinstance(row, Mapping)
            or set(row)
            != {
                "stdlib_relative_path",
                "execution_kind",
                "size_bytes",
                "sha256",
            }
            or not isinstance(row.get("stdlib_relative_path"), str)
            or not row["stdlib_relative_path"]
            or Path(row["stdlib_relative_path"]).is_absolute()
            or row.get("execution_kind")
            not in {"STDLIB_PYTHON_SOURCE", "STDLIB_NATIVE_EXTENSION"}
            or type(row.get("size_bytes")) is not int
            or row["size_bytes"] < 0
            or not isinstance(row.get("sha256"), str)
            or len(row["sha256"]) != 64
            for row in rows
        )
        or len({row["stdlib_relative_path"] for row in rows}) != len(rows)
        or rows != sorted(rows, key=lambda row: row["stdlib_relative_path"])
        or receipt.get("file_manifest_fingerprint_sha256") != _fingerprint(rows)
    ):
        raise EBRTError("ROLE_STDLIB_TREE_SHAPE_INVALID")
    return receipt


def _validate_runtime_identity_shape(value: Any) -> JsonObject:
    receipt = _sealed_snapshot(value, "ROLE_STDLIB_TREE_IDENTITY")
    if (
        set(receipt)
        != {
            "schema_version",
            "interpreter_files",
            "standard_library_code_tree",
            "fingerprint_sha256",
        }
        or receipt.get("schema_version") != "ebrt-runtime-tree-identity-v0.8.3.11"
    ):
        raise EBRTError("ROLE_STDLIB_TREE_IDENTITY_SHAPE_INVALID")
    stdlib_bound._validate_interpreter_shape(receipt.get("interpreter_files"))
    _validate_code_tree_shape(receipt.get("standard_library_code_tree"))
    return receipt


def _imported_stdlib_coverage(runtime_identity: Mapping[str, Any]) -> JsonObject:
    identity = _validate_runtime_identity_shape(runtime_identity)
    code_tree = identity["standard_library_code_tree"]
    manifest = {row["stdlib_relative_path"]: row for row in code_tree["files"]}
    root = Path(code_tree["stdlib_root"])
    extension_suffixes = tuple(importlib.machinery.EXTENSION_SUFFIXES)
    rows: list[JsonObject] = []
    source_count = 0
    native_count = 0
    for module_name, module in sorted(sys.modules.items()):
        if module_name in {"__main__", "__mp_main__"}:
            continue
        origin = startup_bound.complete_bound._module_origin(module_name, module)
        if origin is None or _under_explicit_site(origin):
            continue
        relative_path = startup_bound.complete_bound._relative_to(origin, root)
        if relative_path is None:
            continue
        relative = relative_path.as_posix()
        locked = manifest.get(relative)
        if locked is None:
            raise EBRTError("ROLE_STDLIB_IMPORTED_MODULE_OUTSIDE_LOCKED_TREE")
        cached_value = getattr(module, "__cached__", None)
        cached_exists = (
            isinstance(cached_value, (str, os.PathLike)) and Path(cached_value).exists()
        )
        if origin.suffix == ".py":
            if cached_exists or locked["execution_kind"] != "STDLIB_PYTHON_SOURCE":
                raise EBRTError("ROLE_STDLIB_IMPORTED_SOURCE_POLICY_INVALID")
            execution_kind = "VERIFIED_STDLIB_SOURCE_WITH_CACHE_BYPASSED"
            source_count += 1
        elif any(str(origin).endswith(suffix) for suffix in extension_suffixes):
            if locked["execution_kind"] != "STDLIB_NATIVE_EXTENSION":
                raise EBRTError("ROLE_STDLIB_IMPORTED_NATIVE_POLICY_INVALID")
            execution_kind = "BOUND_STDLIB_NATIVE_EXTENSION"
            native_count += 1
        else:
            raise EBRTError("ROLE_STDLIB_IMPORTED_ORIGIN_KIND_UNSUPPORTED")
        observed_sha = _sha256(origin)
        if (
            observed_sha != locked["sha256"]
            or origin.stat().st_size != locked["size_bytes"]
        ):
            raise EBRTError("ROLE_STDLIB_IMPORTED_CONTENT_MISMATCH")
        rows.append(
            {
                "module": module_name,
                "stdlib_relative_path": relative,
                "execution_kind": execution_kind,
                "sha256": observed_sha,
                "cached_bytecode_present": cached_exists,
            }
        )
    if not rows or source_count <= 0 or native_count <= 0:
        raise EBRTError("ROLE_STDLIB_IMPORTED_COVERAGE_EMPTY")
    return _seal(
        {
            "schema_version": "ebrt-imported-stdlib-coverage-v0.8.3.11",
            "status": "PASS",
            "all_file_backed_imports_in_locked_tree": True,
            "module_count": len(rows),
            "python_source_module_count": source_count,
            "native_extension_module_count": native_count,
            "cached_bytecode_file_count": 0,
            "modules": rows,
            "module_manifest_fingerprint_sha256": _fingerprint(rows),
        }
    )


def _validate_coverage_shape(
    value: Any, runtime_identity: Mapping[str, Any]
) -> JsonObject:
    identity = _validate_runtime_identity_shape(runtime_identity)
    tree = {
        row["stdlib_relative_path"]: row
        for row in identity["standard_library_code_tree"]["files"]
    }
    receipt = _sealed_snapshot(value, "ROLE_STDLIB_IMPORTED_COVERAGE")
    rows = receipt.get("modules")
    if (
        set(receipt)
        != {
            "schema_version",
            "status",
            "all_file_backed_imports_in_locked_tree",
            "module_count",
            "python_source_module_count",
            "native_extension_module_count",
            "cached_bytecode_file_count",
            "modules",
            "module_manifest_fingerprint_sha256",
            "fingerprint_sha256",
        }
        or receipt.get("schema_version") != "ebrt-imported-stdlib-coverage-v0.8.3.11"
        or receipt.get("status") != "PASS"
        or receipt.get("all_file_backed_imports_in_locked_tree") is not True
        or not isinstance(rows, list)
        or not rows
        or receipt.get("module_count") != len(rows)
        or receipt.get("module_count")
        != receipt.get("python_source_module_count", -1)
        + receipt.get("native_extension_module_count", -1)
        or receipt.get("python_source_module_count", 0) <= 0
        or receipt.get("native_extension_module_count", 0) <= 0
        or receipt.get("cached_bytecode_file_count") != 0
        or any(
            not isinstance(row, Mapping)
            or set(row)
            != {
                "module",
                "stdlib_relative_path",
                "execution_kind",
                "sha256",
                "cached_bytecode_present",
            }
            or row.get("stdlib_relative_path") not in tree
            or row.get("sha256") != tree[row["stdlib_relative_path"]]["sha256"]
            or row.get("cached_bytecode_present") is not False
            for row in rows
        )
        or receipt.get("module_manifest_fingerprint_sha256") != _fingerprint(rows)
    ):
        raise EBRTError("ROLE_STDLIB_IMPORTED_COVERAGE_SHAPE_INVALID")
    return receipt


def _probe_execution_state(
    model_path: str,
) -> tuple[JsonObject, JsonObject, JsonObject, JsonObject, JsonObject]:
    code, source, startup = startup_bound._probe_execution_state(model_path)
    identity = _runtime_identity_receipt()
    coverage = _imported_stdlib_coverage(identity)
    return code, source, startup, identity, coverage


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
    imported_lock: Mapping[str, Any],
    runtime_code: Mapping[str, Any],
    source_execution: Mapping[str, Any],
    startup_execution: Mapping[str, Any],
    runtime_identity: Mapping[str, Any],
) -> JsonObject:
    locked_imported = imported_bound.validate_lock(
        imported_lock,
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
            "imported_lock_fingerprint_sha256": locked_imported["fingerprint_sha256"],
            "runtime_code": code,
            "runtime_code_fingerprint_sha256": code["fingerprint_sha256"],
            "source_execution": source,
            "source_execution_fingerprint_sha256": source["fingerprint_sha256"],
            "startup_execution": startup,
            "startup_execution_fingerprint_sha256": startup["fingerprint_sha256"],
            "runtime_identity": identity,
            "runtime_identity_fingerprint_sha256": identity["fingerprint_sha256"],
            "replication_status": "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R11_CASES",
            "effect_attribution_status": "NOT_ASSESSED",
            "claim_boundary": list(CLAIM_BOUNDARY),
        }
    )


def validate_lock(value: Any, *locks: Mapping[str, Any]) -> JsonObject:
    if len(locks) != 11:
        raise EBRTError("ROLE_STDLIB_TREE_LOCK_CHAIN_INVALID")
    observed = _sealed_snapshot(value, "ROLE_STDLIB_TREE_LOCK")
    expected = lock_spec(
        *locks,
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
        raise EBRTError("ROLE_STDLIB_TREE_LOCK_MISMATCH")
    return observed


def run_integrity_replication(
    model_path: str, lock: Mapping[str, Any], *locks: Mapping[str, Any]
) -> JsonObject:
    if len(locks) != 11:
        raise EBRTError("ROLE_STDLIB_TREE_LOCK_CHAIN_INVALID")
    (
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
        immutable_lock,
        _complete_lock,
        _verified_source_lock,
        _startup_lock,
        _stdlib_lock,
        _imported_lock,
    ) = locks
    locked = validate_lock(lock, *locks)
    code_before, source_before, startup_before, identity_before, coverage_before = (
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
        raise EBRTError("ROLE_STDLIB_TREE_PRECALL_STATE_MISMATCH")
    _validate_coverage_shape(coverage_before, locked["runtime_identity"])
    base_run = startup_bound.immutable_bound.run_integrity_replication(
        model_path,
        immutable_lock,
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
    )
    startup_bound.complete_bound._verify_mount_receipt(
        base_run.get("mount_receipt"), snapshot_lock
    )
    code_after = startup_bound.complete_bound._complete_runtime_code_receipt()
    source_after = startup_bound.source_bound._source_execution_receipt()
    startup_after = startup_bound._startup_receipt()
    identity_after = _runtime_identity_receipt()
    coverage_after = _imported_stdlib_coverage(identity_after)
    if (
        _canonical_bytes(code_after) != _canonical_bytes(locked["runtime_code"])
        or _canonical_bytes(source_after)
        != _canonical_bytes(locked["source_execution"])
        or _canonical_bytes(startup_after)
        != _canonical_bytes(locked["startup_execution"])
        or _canonical_bytes(identity_after)
        != _canonical_bytes(locked["runtime_identity"])
    ):
        raise EBRTError("ROLE_STDLIB_TREE_POSTCALL_STATE_MISMATCH")
    _validate_coverage_shape(coverage_after, locked["runtime_identity"])
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
            "base_run": base_run,
            "summary": base_run["summary"],
            "replication_status": "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R11_CASES",
            "effect_attribution_status": "NOT_ASSESSED",
            "claim_boundary": list(CLAIM_BOUNDARY),
        }
    )


def verify_run(
    value: Any, lock: Mapping[str, Any], *locks: Mapping[str, Any]
) -> JsonObject:
    if len(locks) != 11:
        raise EBRTError("ROLE_STDLIB_TREE_LOCK_CHAIN_INVALID")
    (
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
        immutable_lock,
        _complete_lock,
        _verified_source_lock,
        _startup_lock,
        _stdlib_lock,
        _imported_lock,
    ) = locks
    locked = validate_lock(lock, *locks)
    snapshot = _sealed_snapshot(value, "ROLE_STDLIB_TREE_RUN")
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
        != "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R11_CASES"
        or snapshot.get("effect_attribution_status") != "NOT_ASSESSED"
        or snapshot.get("claim_boundary") != list(CLAIM_BOUNDARY)
    ):
        raise EBRTError("ROLE_STDLIB_TREE_RUN_HEADER_INVALID")
    before_coverage = _validate_coverage_shape(
        snapshot.get("imported_stdlib_coverage_before"), locked_identity
    )
    after_coverage = _validate_coverage_shape(
        snapshot.get("imported_stdlib_coverage_after"), locked_identity
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
        raise EBRTError("ROLE_STDLIB_TREE_SUMMARY_MISMATCH")
    return _seal(
        {
            "schema_version": "ebrt-role-uptake-stdlib-tree-verification-v0.8.3.11",
            "status": "PASS",
            "run_fingerprint_sha256": snapshot["fingerprint_sha256"],
            "base_verification_fingerprint_sha256": base_verification[
                "fingerprint_sha256"
            ],
            "imported_stdlib_module_count_before": before_coverage["module_count"],
            "imported_stdlib_module_count_after": after_coverage["module_count"],
            "checks": {
                "pre_call_lock_exact": True,
                "interpreter_executable_exact": True,
                "stdlib_code_tree_exact": True,
                "pre_call_imported_stdlib_covered": True,
                "post_call_imported_stdlib_covered": True,
                "stdlib_lazy_import_set_may_expand": True,
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


def self_test(*locks: Mapping[str, Any]) -> JsonObject:
    if len(locks) != 11:
        raise EBRTError("ROLE_STDLIB_TREE_LOCK_CHAIN_INVALID")
    locked_imported = imported_bound.validate_lock(locks[-1], *locks[:-1])
    imported_test = imported_bound.self_test(*locks[:-1])
    identity = _runtime_identity_receipt()
    coverage = _imported_stdlib_coverage(identity)
    tree = identity["standard_library_code_tree"]
    checks = {
        "imported_lock_chain_exact": locked_imported["fingerprint_sha256"]
        == locks[-1]["fingerprint_sha256"],
        "imported_self_test_passed": imported_test["status"] == "PASS",
        "outer_and_child_environment_ignored": sys.flags.ignore_environment == 1,
        "outer_and_child_site_disabled": sys.flags.no_site == 1,
        "source_only_child_active": os.environ.get(SOURCE_ONLY_CHILD_ENV) == "1",
        "interpreter_files_bound": len(identity["interpreter_files"]["files"]) == 2,
        "stdlib_code_tree_nonempty": tree["file_count"] > 0,
        "stdlib_source_tree_nonempty": tree["python_source_file_count"] > 0,
        "stdlib_native_tree_nonempty": tree["native_extension_file_count"] > 0,
        "current_imported_stdlib_covered": coverage["status"] == "PASS",
    }
    if not all(checks.values()):
        raise EBRTError("ROLE_STDLIB_TREE_SELF_TEST_FAILED")
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
            )
        )
        if args.command == "self-test":
            value = self_test(*locks)
        elif args.command == "probe-execution":
            code, source, startup, identity, coverage = _probe_execution_state(
                args.model
            )
            value = _seal(
                {
                    "runtime_code": code,
                    "source_execution": source,
                    "startup_execution": startup,
                    "runtime_identity": identity,
                    "imported_stdlib_coverage": coverage,
                }
            )
        elif args.command == "lock-spec":
            code, source, startup, identity, _coverage = _probe_execution_state(
                args.model
            )
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
            raise EBRTError("ROLE_STDLIB_TREE_COMMAND_UNKNOWN")
        print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (EBRTError, RuntimeError) as error:
        print(json.dumps({"status": "ERROR", "error_code": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
