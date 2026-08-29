#!/usr/bin/env python3
"""Verified-source execution wrapper for the EBRT v0.8.3 canary.

The r08 successor prevents timestamp-valid adjacent ``.pyc`` files from
silently diverging from the source receipts.  Before importing any repository
or site-package module, the CLI re-executes itself with a fresh empty
``pycache_prefix`` and bytecode writes disabled.  It repeats known cases only
for execution integrity and is not fresh scientific data.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


SOURCE_ONLY_CHILD_ENV = "EBRT_V0837_SOURCE_ONLY_CHILD"
SOURCE_ONLY_PREFIX_ENV = "EBRT_V0837_SOURCE_ONLY_PREFIX"


def _bootstrap_source_only_child() -> None:
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
                        "error_code": "ROLE_SOURCE_ONLY_BOOTSTRAP_INVALID",
                    }
                )
            )
            raise SystemExit(2)
        return
    with tempfile.TemporaryDirectory(prefix="ebrt-v0837-pycache-") as temporary:
        prefix = Path(temporary).resolve()
        if any(prefix.iterdir()):
            print(
                json.dumps(
                    {
                        "status": "ERROR",
                        "error_code": "ROLE_SOURCE_ONLY_PREFIX_NOT_EMPTY",
                    }
                )
            )
            raise SystemExit(2)
        environment = os.environ.copy()
        environment[SOURCE_ONLY_CHILD_ENV] = "1"
        environment[SOURCE_ONLY_PREFIX_ENV] = str(prefix)
        try:
            completed = subprocess.run(
                [
                    sys.executable,
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
                        "error_code": "ROLE_SOURCE_ONLY_REEXEC_FAILED",
                    }
                )
            )
            raise SystemExit(2) from None
        raise SystemExit(completed.returncode)


if __name__ == "__main__":
    _bootstrap_source_only_child()


import argparse  # noqa: E402
import importlib.machinery  # noqa: E402
import importlib.util  # noqa: E402
import marshal  # noqa: E402
import struct  # noqa: E402
import sysconfig  # noqa: E402
from typing import Any, Mapping, Sequence  # noqa: E402

import role_stratified_uptake_integrity_v0_8_3_5 as immutable_bound  # noqa: E402
import role_stratified_uptake_integrity_v0_8_3_6 as complete_bound  # noqa: E402
from ebrt_core import (  # noqa: E402
    EBRTError,
    _canonical_bytes,
    _fingerprint,
    _seal,
    _sealed_snapshot,
)


LOCK_SCHEMA_VERSION = "ebrt-role-uptake-source-lock-v0.8.3.7"
RUN_SCHEMA_VERSION = "ebrt-role-uptake-source-run-v0.8.3.7"
SELF_TEST_SCHEMA_VERSION = "ebrt-role-uptake-source-self-test-v0.8.3.7"
REPOSITORY_ROOT = Path(__file__).resolve().parent
CLAIM_BOUNDARY = (
    "This r08 execution repeats already observed cases only to exclude timestamp-valid divergent Python bytecode from the admitted execution path.",
    "The repeated outputs are contaminated by known r01-r07 results and are not fresh scientific replication evidence.",
    "Repository and site-package Python modules are imported under a fresh empty pycache prefix with bytecode writes disabled, so adjacent caches are ignored.",
    "Python source and native-extension content remain bound by the r07 complete dependency receipt; the r06 read-only model mount is independently verified.",
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


def _source_execution_receipt() -> JsonObject:
    prefix_value = sys.pycache_prefix
    expected_prefix = os.environ.get(SOURCE_ONLY_PREFIX_ENV)
    if (
        os.environ.get(SOURCE_ONLY_CHILD_ENV) != "1"
        or not sys.dont_write_bytecode
        or prefix_value is None
        or expected_prefix is None
    ):
        raise EBRTError("ROLE_SOURCE_ONLY_POLICY_INACTIVE")
    prefix = Path(prefix_value).resolve()
    if prefix != Path(expected_prefix).resolve() or any(prefix.rglob("*")):
        raise EBRTError("ROLE_SOURCE_ONLY_PREFIX_CONTAMINATED")
    stdlib_root = Path(sysconfig.get_paths()["stdlib"]).resolve()
    site_roots = complete_bound._site_roots()
    extension_suffixes = tuple(importlib.machinery.EXTENSION_SUFFIXES)
    rows: list[JsonObject] = []
    source_count = 0
    native_count = 0
    for module_name, module in sorted(sys.modules.items()):
        origin = complete_bound._module_origin(module_name, module)
        if origin is None:
            continue
        repository_relative = complete_bound._relative_to(origin, REPOSITORY_ROOT)
        under_site = any(
            complete_bound._relative_to(origin, root) is not None for root in site_roots
        )
        under_stdlib = complete_bound._relative_to(origin, stdlib_root) is not None
        if repository_relative is None and under_stdlib and not under_site:
            continue
        cached_value = getattr(module, "__cached__", None)
        cached_exists = (
            isinstance(cached_value, (str, os.PathLike)) and Path(cached_value).exists()
        )
        if origin.suffix == ".py":
            if cached_exists:
                raise EBRTError("ROLE_SOURCE_ONLY_CACHED_BYTECODE_PRESENT")
            execution_kind = "VERIFIED_SOURCE_WITH_CACHE_BYPASSED"
            source_count += 1
        elif any(str(origin).endswith(suffix) for suffix in extension_suffixes):
            execution_kind = "BOUND_NATIVE_EXTENSION"
            native_count += 1
        else:
            raise EBRTError("ROLE_SOURCE_ONLY_ORIGIN_KIND_UNSUPPORTED")
        rows.append(
            {
                "module": module_name,
                "execution_kind": execution_kind,
                "origin_sha256": _sha256(origin),
                "cached_bytecode_present": cached_exists,
            }
        )
    if not rows or source_count <= 0:
        raise EBRTError("ROLE_SOURCE_ONLY_MODULE_SET_EMPTY")
    return _seal(
        {
            "schema_version": "ebrt-source-execution-receipt-v0.8.3.7",
            "fresh_empty_pycache_prefix": True,
            "adjacent_pycache_ignored": True,
            "bytecode_writes_disabled": True,
            "cached_bytecode_file_count": 0,
            "module_count": len(rows),
            "python_source_module_count": source_count,
            "native_extension_module_count": native_count,
            "module_execution_fingerprint_sha256": _fingerprint(rows),
        }
    )


def _probe_execution_state(model_path: str) -> tuple[JsonObject, JsonObject]:
    immutable_bound.probe_runtime_code(model_path)
    return (
        complete_bound._complete_runtime_code_receipt(),
        _source_execution_receipt(),
    )


def _validate_source_execution_shape(value: Any) -> JsonObject:
    receipt = _sealed_snapshot(value, "ROLE_SOURCE_ONLY_EXECUTION")
    if (
        set(receipt)
        != {
            "schema_version",
            "fresh_empty_pycache_prefix",
            "adjacent_pycache_ignored",
            "bytecode_writes_disabled",
            "cached_bytecode_file_count",
            "module_count",
            "python_source_module_count",
            "native_extension_module_count",
            "module_execution_fingerprint_sha256",
            "fingerprint_sha256",
        }
        or receipt.get("schema_version") != "ebrt-source-execution-receipt-v0.8.3.7"
        or receipt.get("fresh_empty_pycache_prefix") is not True
        or receipt.get("adjacent_pycache_ignored") is not True
        or receipt.get("bytecode_writes_disabled") is not True
        or receipt.get("cached_bytecode_file_count") != 0
        or type(receipt.get("module_count")) is not int
        or type(receipt.get("python_source_module_count")) is not int
        or type(receipt.get("native_extension_module_count")) is not int
        or receipt["module_count"]
        != receipt["python_source_module_count"]
        + receipt["native_extension_module_count"]
        or receipt["python_source_module_count"] <= 0
        or not isinstance(receipt.get("module_execution_fingerprint_sha256"), str)
        or len(receipt["module_execution_fingerprint_sha256"]) != 64
    ):
        raise EBRTError("ROLE_SOURCE_ONLY_EXECUTION_SHAPE_INVALID")
    return receipt


def lock_spec(
    base_lock: Mapping[str, Any],
    source_lock: Mapping[str, Any],
    snapshot_lock: Mapping[str, Any],
    loader_lock: Mapping[str, Any],
    runtime_lock: Mapping[str, Any],
    immutable_lock: Mapping[str, Any],
    complete_lock: Mapping[str, Any],
    runtime_code: Mapping[str, Any],
    source_execution: Mapping[str, Any],
) -> JsonObject:
    locked_complete = complete_bound.validate_lock(
        complete_lock,
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
        immutable_lock,
    )
    code = complete_bound._validate_runtime_code_shape(runtime_code)
    execution = _validate_source_execution_shape(source_execution)
    return _seal(
        {
            "schema_version": LOCK_SCHEMA_VERSION,
            "status": "LOCKED_BEFORE_PROVIDER_CALLS",
            "wrapper_sha256": _sha256(Path(__file__)),
            "complete_lock_fingerprint_sha256": locked_complete["fingerprint_sha256"],
            "runtime_code": code,
            "runtime_code_fingerprint_sha256": code["fingerprint_sha256"],
            "source_execution": execution,
            "source_execution_fingerprint_sha256": execution["fingerprint_sha256"],
            "replication_status": "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R07_CASES",
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
) -> JsonObject:
    observed = _sealed_snapshot(value, "ROLE_SOURCE_ONLY_LOCK")
    expected = lock_spec(
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
        immutable_lock,
        complete_lock,
        complete_bound._validate_runtime_code_shape(observed.get("runtime_code")),
        _validate_source_execution_shape(observed.get("source_execution")),
    )
    if _canonical_bytes(observed) != _canonical_bytes(expected):
        raise EBRTError("ROLE_SOURCE_ONLY_LOCK_MISMATCH")
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
    )
    code_before, execution_before = _probe_execution_state(model_path)
    if _canonical_bytes(code_before) != _canonical_bytes(
        locked["runtime_code"]
    ) or _canonical_bytes(execution_before) != _canonical_bytes(
        locked["source_execution"]
    ):
        raise EBRTError("ROLE_SOURCE_ONLY_PRECALL_STATE_MISMATCH")
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
    execution_after = _source_execution_receipt()
    if _canonical_bytes(code_after) != _canonical_bytes(
        locked["runtime_code"]
    ) or _canonical_bytes(execution_after) != _canonical_bytes(
        locked["source_execution"]
    ):
        raise EBRTError("ROLE_SOURCE_ONLY_POSTCALL_STATE_MISMATCH")
    return _seal(
        {
            "schema_version": RUN_SCHEMA_VERSION,
            "status": "COMPLETE",
            "policy_lock_fingerprint_sha256": locked["fingerprint_sha256"],
            "runtime_code_before": code_before,
            "runtime_code_after": code_after,
            "source_execution_before": execution_before,
            "source_execution_after": execution_after,
            "prior_run": prior_run,
            "summary": prior_run["summary"],
            "replication_status": "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R07_CASES",
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
    )
    snapshot = _sealed_snapshot(value, "ROLE_SOURCE_ONLY_RUN")
    expected_keys = {
        "schema_version",
        "status",
        "policy_lock_fingerprint_sha256",
        "runtime_code_before",
        "runtime_code_after",
        "source_execution_before",
        "source_execution_after",
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
    locked_execution = _validate_source_execution_shape(locked.get("source_execution"))
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
        != _canonical_bytes(locked_execution)
        or _canonical_bytes(snapshot.get("source_execution_after"))
        != _canonical_bytes(locked_execution)
        or snapshot.get("replication_status")
        != "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R07_CASES"
        or snapshot.get("effect_attribution_status") != "NOT_ASSESSED"
        or snapshot.get("claim_boundary") != list(CLAIM_BOUNDARY)
    ):
        raise EBRTError("ROLE_SOURCE_ONLY_RUN_HEADER_INVALID")
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
        raise EBRTError("ROLE_SOURCE_ONLY_SUMMARY_MISMATCH")
    return _seal(
        {
            "schema_version": "ebrt-role-uptake-source-verification-v0.8.3.7",
            "status": "PASS",
            "run_fingerprint_sha256": snapshot["fingerprint_sha256"],
            "prior_verification_fingerprint_sha256": prior_verification[
                "fingerprint_sha256"
            ],
            "checks": {
                "pre_call_lock_exact": True,
                "fresh_empty_pycache_prefix": True,
                "adjacent_bytecode_cache_bypassed": True,
                "bytecode_writes_disabled": True,
                "all_nonstdlib_python_origins_are_source": True,
                "all_native_extensions_content_bound": True,
                "complete_runtime_code_receipt_exact": True,
                "mount_receipt_matches_locked_snapshot": True,
                "known_case_replication_boundary_exact": True,
            },
        }
    )


def _bytecode_divergence_self_test() -> bool:
    with tempfile.TemporaryDirectory(prefix="ebrt-v0837-fixture-") as temporary:
        root = Path(temporary)
        source = root / "probe_mod.py"
        source.write_text("VALUE='SOURCE'\n", encoding="utf-8")
        stat = source.stat()
        malicious = compile("VALUE='CACHED'\n", str(source), "exec")
        cache = (
            source.parent
            / "__pycache__"
            / f"probe_mod.{sys.implementation.cache_tag}.pyc"
        )
        cache.parent.mkdir(parents=True)
        header = (
            importlib.util.MAGIC_NUMBER
            + struct.pack("<I", 0)
            + struct.pack("<II", int(stat.st_mtime), stat.st_size)
        )
        cache.write_bytes(header + marshal.dumps(malicious))
        regular = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys;sys.path.insert(0,sys.argv[1]);import probe_mod;print(probe_mod.VALUE)",
                str(root),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        with tempfile.TemporaryDirectory(
            prefix="ebrt-v0837-fixture-cache-"
        ) as prefix_value:
            source_only = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-X",
                    f"pycache_prefix={prefix_value}",
                    "-c",
                    "import sys;sys.path.insert(0,sys.argv[1]);import probe_mod;print(probe_mod.VALUE)",
                    str(root),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        return (
            regular.returncode == 0
            and regular.stdout.strip() == "CACHED"
            and source_only.returncode == 0
            and source_only.stdout.strip() == "SOURCE"
        )


def self_test(
    base_lock: Mapping[str, Any],
    source_lock: Mapping[str, Any],
    snapshot_lock: Mapping[str, Any],
    loader_lock: Mapping[str, Any],
    runtime_lock: Mapping[str, Any],
    immutable_lock: Mapping[str, Any],
    complete_lock: Mapping[str, Any],
) -> JsonObject:
    locked_complete = complete_bound.validate_lock(
        complete_lock,
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
        immutable_lock,
    )
    checks = {
        "complete_lock_chain_exact": locked_complete["fingerprint_sha256"]
        == complete_lock["fingerprint_sha256"],
        "source_only_child_active": os.environ.get(SOURCE_ONLY_CHILD_ENV) == "1",
        "bytecode_writes_disabled": sys.dont_write_bytecode,
        "fresh_pycache_prefix_active": sys.pycache_prefix is not None,
        "pycache_prefix_remains_empty": not any(
            Path(sys.pycache_prefix).resolve().rglob("*")
        ),
        "timestamp_valid_divergent_pyc_bypassed": _bytecode_divergence_self_test(),
    }
    if not all(checks.values()):
        raise EBRTError("ROLE_SOURCE_ONLY_SELF_TEST_FAILED")
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
        if args.command == "self-test":
            value = self_test(
                base_lock,
                source_lock,
                snapshot_lock,
                loader_lock,
                runtime_lock,
                immutable_lock,
                complete_lock,
            )
        elif args.command == "probe-execution":
            code, execution = _probe_execution_state(args.model)
            value = _seal(
                {
                    "runtime_code": code,
                    "source_execution": execution,
                }
            )
        elif args.command == "lock-spec":
            code, execution = _probe_execution_state(args.model)
            value = lock_spec(
                base_lock,
                source_lock,
                snapshot_lock,
                loader_lock,
                runtime_lock,
                immutable_lock,
                complete_lock,
                code,
                execution,
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
            )
        else:  # pragma: no cover
            raise EBRTError("ROLE_SOURCE_ONLY_COMMAND_UNKNOWN")
        print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except EBRTError as error:
        print(json.dumps({"status": "ERROR", "error_code": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
