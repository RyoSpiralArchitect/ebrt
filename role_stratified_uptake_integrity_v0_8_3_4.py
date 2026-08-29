#!/usr/bin/env python3
"""Exact-runtime integrity replication wrapper for EBRT v0.8.3.

This r05 successor binds the Python and local-model distribution versions that
execute the already known loader-bound canary.  It is an integrity repetition,
not fresh scientific evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Mapping, Sequence

import role_stratified_uptake_integrity_v0_8_3_3 as loader_bound
from ebrt_core import EBRTError, _canonical_bytes, _seal, _sealed_snapshot


LOCK_SCHEMA_VERSION = "ebrt-role-uptake-runtime-lock-v0.8.3.4"
RUN_SCHEMA_VERSION = "ebrt-role-uptake-runtime-run-v0.8.3.4"
SELF_TEST_SCHEMA_VERSION = "ebrt-role-uptake-runtime-self-test-v0.8.3.4"
EXPECTED_RUNTIME = {
    "python_implementation": "CPython",
    "python_version": "3.13.13",
    "system": "Darwin",
    "machine": "arm64",
    "macos_version": "26.2",
    "distributions": {
        "huggingface-hub": "0.36.2",
        "mlx": "0.31.1",
        "mlx-lm": "0.31.2",
        "numpy": "2.4.4",
        "safetensors": "0.7.0",
        "tokenizers": "0.22.2",
        "torch": "2.11.0",
        "transformers": "4.57.6",
    },
}
CLAIM_BOUNDARY = (
    "This r05 execution repeats already observed cases only to bind exact declared runtime versions.",
    "The repeated outputs are contaminated by known r01-r04 results and are not fresh scientific replication evidence.",
    "Python, OS product version, architecture, and all declared local-model distribution versions are checked before and after calls.",
    "The runtime receipt binds installed distribution versions; it does not claim a signed binary or hardware attestation.",
    "All original v0.8.3 effect-attribution, one-model, public-role, and stop-gradient boundaries remain unchanged.",
)

JsonObject = dict[str, Any]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
    except OSError as error:
        raise EBRTError("ROLE_RUNTIME_SOURCE_READ_FAILED") from error
    return digest.hexdigest()


def _load_json(path: Path) -> JsonObject:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EBRTError("ROLE_RUNTIME_ARTIFACT_READ_FAILED") from error
    if not isinstance(value, dict):
        raise EBRTError("ROLE_RUNTIME_ARTIFACT_TYPE_INVALID")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _runtime_receipt() -> JsonObject:
    distributions: dict[str, str] = {}
    for package_name in sorted(EXPECTED_RUNTIME["distributions"]):
        try:
            distributions[package_name] = version(package_name)
        except PackageNotFoundError as error:
            raise EBRTError("ROLE_RUNTIME_DISTRIBUTION_MISSING") from error
    return _seal(
        {
            "schema_version": "ebrt-local-runtime-receipt-v0.8.3.4",
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
            "system": platform.system(),
            "machine": platform.machine(),
            "macos_version": platform.mac_ver()[0],
            "distributions": distributions,
        }
    )


def _expected_runtime_receipt() -> JsonObject:
    return _seal(
        {
            "schema_version": "ebrt-local-runtime-receipt-v0.8.3.4",
            **EXPECTED_RUNTIME,
        }
    )


def _validate_runtime() -> JsonObject:
    observed = _runtime_receipt()
    expected = _expected_runtime_receipt()
    if _canonical_bytes(observed) != _canonical_bytes(expected):
        raise EBRTError("ROLE_RUNTIME_VERSION_MISMATCH")
    return observed


def lock_spec(
    base_lock: Mapping[str, Any],
    source_lock: Mapping[str, Any],
    snapshot_lock: Mapping[str, Any],
    loader_lock: Mapping[str, Any],
) -> JsonObject:
    locked_loader = loader_bound.validate_lock(
        loader_lock,
        base_lock,
        source_lock,
        snapshot_lock,
    )
    runtime = _expected_runtime_receipt()
    return _seal(
        {
            "schema_version": LOCK_SCHEMA_VERSION,
            "status": "LOCKED_BEFORE_PROVIDER_CALLS",
            "wrapper_sha256": _sha256(Path(__file__)),
            "loader_lock_fingerprint_sha256": locked_loader["fingerprint_sha256"],
            "runtime": runtime,
            "runtime_fingerprint_sha256": runtime["fingerprint_sha256"],
            "replication_status": "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R04_CASES",
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
) -> JsonObject:
    observed = _sealed_snapshot(value, "ROLE_RUNTIME_LOCK")
    expected = lock_spec(base_lock, source_lock, snapshot_lock, loader_lock)
    if _canonical_bytes(observed) != _canonical_bytes(expected):
        raise EBRTError("ROLE_RUNTIME_LOCK_MISMATCH")
    return observed


def run_integrity_replication(
    model_path: str,
    lock: Mapping[str, Any],
    base_lock: Mapping[str, Any],
    source_lock: Mapping[str, Any],
    snapshot_lock: Mapping[str, Any],
    loader_lock: Mapping[str, Any],
) -> JsonObject:
    locked = validate_lock(
        lock,
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
    )
    before = _validate_runtime()
    prior_run = loader_bound.run_integrity_replication(
        model_path,
        loader_lock,
        base_lock,
        source_lock,
        snapshot_lock,
    )
    after = _validate_runtime()
    if _canonical_bytes(before) != _canonical_bytes(after):
        raise EBRTError("ROLE_RUNTIME_CHANGED_DURING_RUN")
    return _seal(
        {
            "schema_version": RUN_SCHEMA_VERSION,
            "status": "COMPLETE",
            "policy_lock_fingerprint_sha256": locked["fingerprint_sha256"],
            "runtime_before": before,
            "runtime_after": after,
            "runtime_unchanged": True,
            "prior_run": prior_run,
            "summary": prior_run["summary"],
            "replication_status": "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R04_CASES",
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
) -> JsonObject:
    locked = validate_lock(
        lock,
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
    )
    snapshot = _sealed_snapshot(value, "ROLE_RUNTIME_RUN")
    expected_keys = {
        "schema_version",
        "status",
        "policy_lock_fingerprint_sha256",
        "runtime_before",
        "runtime_after",
        "runtime_unchanged",
        "prior_run",
        "summary",
        "replication_status",
        "effect_attribution_status",
        "claim_boundary",
        "fingerprint_sha256",
    }
    expected_runtime = _sealed_snapshot(locked.get("runtime"), "ROLE_RUNTIME_LOCKED")
    observed_before = _sealed_snapshot(
        snapshot.get("runtime_before"), "ROLE_RUNTIME_BEFORE"
    )
    observed_after = _sealed_snapshot(
        snapshot.get("runtime_after"), "ROLE_RUNTIME_AFTER"
    )
    if (
        set(snapshot) != expected_keys
        or snapshot.get("schema_version") != RUN_SCHEMA_VERSION
        or snapshot.get("status") != "COMPLETE"
        or snapshot.get("policy_lock_fingerprint_sha256")
        != locked["fingerprint_sha256"]
        or _canonical_bytes(observed_before) != _canonical_bytes(expected_runtime)
        or _canonical_bytes(observed_after) != _canonical_bytes(expected_runtime)
        or snapshot.get("runtime_unchanged") is not True
        or snapshot.get("replication_status")
        != "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R04_CASES"
        or snapshot.get("effect_attribution_status") != "NOT_ASSESSED"
        or snapshot.get("claim_boundary") != list(CLAIM_BOUNDARY)
    ):
        raise EBRTError("ROLE_RUNTIME_RUN_HEADER_INVALID")
    prior_verification = loader_bound.verify_run(
        snapshot.get("prior_run"),
        loader_lock,
        base_lock,
        source_lock,
        snapshot_lock,
    )
    if _canonical_bytes(snapshot.get("summary")) != _canonical_bytes(
        snapshot["prior_run"]["summary"]
    ):
        raise EBRTError("ROLE_RUNTIME_SUMMARY_MISMATCH")
    return _seal(
        {
            "schema_version": "ebrt-role-uptake-runtime-verification-v0.8.3.4",
            "status": "PASS",
            "run_fingerprint_sha256": snapshot["fingerprint_sha256"],
            "prior_verification_fingerprint_sha256": prior_verification[
                "fingerprint_sha256"
            ],
            "checks": {
                "pre_call_lock_exact": True,
                "python_and_platform_exact": True,
                "local_runtime_distribution_versions_exact": True,
                "runtime_unchanged_across_calls": True,
                "loader_bound_run_portably_verified": True,
                "known_case_replication_boundary_exact": True,
            },
        }
    )


def self_test(
    base_lock: Mapping[str, Any],
    source_lock: Mapping[str, Any],
    snapshot_lock: Mapping[str, Any],
    loader_lock: Mapping[str, Any],
) -> JsonObject:
    spec = lock_spec(base_lock, source_lock, snapshot_lock, loader_lock)
    runtime = _validate_runtime()
    checks = {
        "runtime_matches_declared_lock": _canonical_bytes(runtime)
        == _canonical_bytes(spec["runtime"]),
        "mlx_version_exact": runtime["distributions"]["mlx"] == "0.31.1",
        "mlx_lm_version_exact": runtime["distributions"]["mlx-lm"] == "0.31.2",
        "torch_version_exact": runtime["distributions"]["torch"] == "2.11.0",
        "known_case_replication_label_exact": spec["replication_status"]
        == "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R04_CASES",
    }
    if not all(checks.values()):
        raise EBRTError("ROLE_RUNTIME_SELF_TEST_FAILED")
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
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("self-test")
    commands.add_parser("lock-spec")
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
        if args.command == "self-test":
            value = self_test(base_lock, source_lock, snapshot_lock, loader_lock)
        elif args.command == "lock-spec":
            value = lock_spec(base_lock, source_lock, snapshot_lock, loader_lock)
        elif args.command == "run":
            value = run_integrity_replication(
                args.model,
                _load_json(args.lock),
                base_lock,
                source_lock,
                snapshot_lock,
                loader_lock,
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
            )
        else:  # pragma: no cover
            raise EBRTError("ROLE_RUNTIME_COMMAND_UNKNOWN")
        print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except EBRTError as error:
        print(json.dumps({"status": "ERROR", "error_code": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
