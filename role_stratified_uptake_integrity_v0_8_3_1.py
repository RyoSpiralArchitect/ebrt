#!/usr/bin/env python3
"""Integrity-bound replication wrapper for the EBRT v0.8.3 canary.

The original r01 result remains immutable.  This successor repeats the known
cases only to bind the exact imported implementation files and require a
content-address-verified Hugging Face cache snapshot before provider calls.
It is not fresh scientific evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import role_stratified_uptake_canary_v0_8_3 as base
from ebrt_core import (
    EBRTError,
    _canonical_bytes,
    _seal,
    _sealed_snapshot,
    _validated_cache_model_id,
)


LOCK_SCHEMA_VERSION = "ebrt-role-uptake-integrity-lock-v0.8.3.1"
RUN_SCHEMA_VERSION = "ebrt-role-uptake-integrity-run-v0.8.3.1"
SELF_TEST_SCHEMA_VERSION = "ebrt-role-uptake-integrity-self-test-v0.8.3.1"
DEPENDENCY_PATHS = (
    "ebrt_core.py",
    "local_output_diff_corpus_v0_8_2.py",
    "role_stratified_uptake_canary_v0_8_3.py",
)
CLAIM_BOUNDARY = (
    "This r02 execution repeats the already observed r01 cases only to repair source and model attribution binding.",
    "The repeated outputs are contaminated by the known r01 result and are not fresh scientific replication evidence.",
    "The model gate admits only the content-address-verified locked Hugging Face cache snapshot.",
    "The lock binds this wrapper and every repository-local implementation file imported by the execution path.",
    "All v0.8.3 effect-attribution, one-model, public-role, and stop-gradient boundaries remain unchanged.",
)

JsonObject = dict[str, Any]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
    except OSError as error:
        raise EBRTError("ROLE_INTEGRITY_SOURCE_READ_FAILED") from error
    return digest.hexdigest()


def _wrapper_sha256() -> str:
    return _sha256(Path(__file__))


def _dependency_hashes() -> JsonObject:
    root = Path(__file__).resolve().parent
    return {name: _sha256(root / name) for name in DEPENDENCY_PATHS}


def _load_json(path: Path) -> JsonObject:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EBRTError("ROLE_INTEGRITY_ARTIFACT_READ_FAILED") from error
    if not isinstance(value, dict):
        raise EBRTError("ROLE_INTEGRITY_ARTIFACT_TYPE_INVALID")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def lock_spec(base_lock: Mapping[str, Any]) -> JsonObject:
    locked_base = base.validate_lock(base_lock)
    return _seal(
        {
            "schema_version": LOCK_SCHEMA_VERSION,
            "status": "LOCKED_BEFORE_PROVIDER_CALLS",
            "wrapper_sha256": _wrapper_sha256(),
            "dependency_sha256": _dependency_hashes(),
            "base_lock_fingerprint_sha256": locked_base["fingerprint_sha256"],
            "model_binding": {
                "model_id": base.MODEL_ID,
                "admission": "EXACT_HF_CACHE_SNAPSHOT_WITH_CONTENT_ADDRESSED_BLOBS",
                "arbitrary_explicit_model_id": "REJECTED",
            },
            "execution_geometry": locked_base["execution_policy"],
            "replication_status": "INTEGRITY_REPLICATION_OVER_KNOWN_R01_CASES",
            "effect_attribution_status": "NOT_ASSESSED",
            "claim_boundary": list(CLAIM_BOUNDARY),
        }
    )


def validate_lock(value: Any, base_lock: Mapping[str, Any]) -> JsonObject:
    observed = _sealed_snapshot(value, "ROLE_INTEGRITY_LOCK")
    expected = lock_spec(base_lock)
    if _canonical_bytes(observed) != _canonical_bytes(expected):
        raise EBRTError("ROLE_INTEGRITY_LOCK_MISMATCH")
    return observed


def _bind_model(model_path: str) -> JsonObject:
    path = Path(model_path).expanduser().resolve()
    derived_model_id = _validated_cache_model_id(path)
    if derived_model_id != base.MODEL_ID:
        raise EBRTError("ROLE_INTEGRITY_MODEL_SNAPSHOT_MISMATCH")
    return _seal(
        {
            "status": "PASS",
            "derived_model_id": derived_model_id,
            "locked_model_id": base.MODEL_ID,
            "validation_method": "HF_CACHE_LAYOUT_PLUS_CONTENT_ADDRESSED_BLOB_VERIFICATION",
            "path_exported": False,
        }
    )


def run_integrity_replication(
    model_path: str,
    lock: Mapping[str, Any],
    base_lock: Mapping[str, Any],
) -> JsonObject:
    locked = validate_lock(lock, base_lock)
    model_binding = _bind_model(model_path)
    base_run = base.run_canary(model_path, base_lock)
    return _seal(
        {
            "schema_version": RUN_SCHEMA_VERSION,
            "status": "COMPLETE",
            "policy_lock_fingerprint_sha256": locked["fingerprint_sha256"],
            "model_binding": model_binding,
            "base_run": base_run,
            "summary": base_run["summary"],
            "replication_status": "INTEGRITY_REPLICATION_OVER_KNOWN_R01_CASES",
            "effect_attribution_status": "NOT_ASSESSED",
            "claim_boundary": list(CLAIM_BOUNDARY),
        }
    )


def verify_run(
    value: Any,
    lock: Mapping[str, Any],
    base_lock: Mapping[str, Any],
) -> JsonObject:
    locked = validate_lock(lock, base_lock)
    snapshot = _sealed_snapshot(value, "ROLE_INTEGRITY_RUN")
    expected_keys = {
        "schema_version",
        "status",
        "policy_lock_fingerprint_sha256",
        "model_binding",
        "base_run",
        "summary",
        "replication_status",
        "effect_attribution_status",
        "claim_boundary",
        "fingerprint_sha256",
    }
    binding = _sealed_snapshot(
        snapshot.get("model_binding"), "ROLE_INTEGRITY_MODEL_BINDING"
    )
    expected_binding = {
        "status": "PASS",
        "derived_model_id": base.MODEL_ID,
        "locked_model_id": base.MODEL_ID,
        "validation_method": "HF_CACHE_LAYOUT_PLUS_CONTENT_ADDRESSED_BLOB_VERIFICATION",
        "path_exported": False,
    }
    if (
        set(snapshot) != expected_keys
        or snapshot.get("schema_version") != RUN_SCHEMA_VERSION
        or snapshot.get("status") != "COMPLETE"
        or snapshot.get("policy_lock_fingerprint_sha256")
        != locked["fingerprint_sha256"]
        or _canonical_bytes(binding) != _canonical_bytes(_seal(expected_binding))
        or snapshot.get("replication_status")
        != "INTEGRITY_REPLICATION_OVER_KNOWN_R01_CASES"
        or snapshot.get("effect_attribution_status") != "NOT_ASSESSED"
        or snapshot.get("claim_boundary") != list(CLAIM_BOUNDARY)
    ):
        raise EBRTError("ROLE_INTEGRITY_RUN_HEADER_INVALID")
    base_verification = base.verify_run(snapshot.get("base_run"), base_lock)
    if _canonical_bytes(snapshot.get("summary")) != _canonical_bytes(
        snapshot["base_run"]["summary"]
    ):
        raise EBRTError("ROLE_INTEGRITY_SUMMARY_MISMATCH")
    return _seal(
        {
            "schema_version": "ebrt-role-uptake-integrity-verification-v0.8.3.1",
            "status": "PASS",
            "run_fingerprint_sha256": snapshot["fingerprint_sha256"],
            "base_run_fingerprint_sha256": snapshot["base_run"]["fingerprint_sha256"],
            "base_verification_fingerprint_sha256": base_verification[
                "fingerprint_sha256"
            ],
            "checks": {
                "pre_call_lock_exact": True,
                "wrapper_hash_exact": True,
                "all_imported_source_hashes_exact": True,
                "locked_model_identity_receipt_exact": True,
                "base_run_portably_verified": True,
                "known_case_replication_boundary_exact": True,
            },
        }
    )


def self_test(base_lock: Mapping[str, Any]) -> JsonObject:
    base_self_test = base.self_test()
    spec = lock_spec(base_lock)
    checks = {
        "base_network_zero_self_test_passes": base_self_test["status"] == "PASS",
        "wrapper_hash_is_sha256": len(spec["wrapper_sha256"]) == 64,
        "all_dependency_hashes_present": set(spec["dependency_sha256"])
        == set(DEPENDENCY_PATHS),
        "all_dependency_hashes_are_sha256": all(
            len(value) == 64 for value in spec["dependency_sha256"].values()
        ),
        "arbitrary_explicit_identity_rejected_by_policy": spec["model_binding"][
            "arbitrary_explicit_model_id"
        ]
        == "REJECTED",
        "known_case_replication_label_exact": spec["replication_status"]
        == "INTEGRITY_REPLICATION_OVER_KNOWN_R01_CASES",
    }
    if not all(checks.values()):
        raise EBRTError("ROLE_INTEGRITY_SELF_TEST_FAILED")
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
    parser.add_argument(
        "--base-lock",
        type=Path,
        required=True,
        help="the immutable v0.8.3 r01 pre-call lock",
    )
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
        if args.command == "self-test":
            value = self_test(base_lock)
        elif args.command == "lock-spec":
            value = lock_spec(base_lock)
        elif args.command == "run":
            value = run_integrity_replication(
                args.model, _load_json(args.lock), base_lock
            )
            _write_json(args.output, value)
        elif args.command == "verify":
            value = verify_run(
                _load_json(args.artifact), _load_json(args.lock), base_lock
            )
        else:  # pragma: no cover
            raise EBRTError("ROLE_INTEGRITY_COMMAND_UNKNOWN")
        print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except EBRTError as error:
        print(json.dumps({"status": "ERROR", "error_code": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
