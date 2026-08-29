#!/usr/bin/env python3
"""Loader-bound staged-copy replication wrapper for EBRT v0.8.3.

This r04 successor copies the exact locked snapshot into a private APFS
copy-on-write staging directory and passes only that isolated regular-file tree
to MLX.  It closes the cache-symlink TOCTOU boundary exposed by review.  The
known cases are repeated only for integrity, never as fresh scientific data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

import role_stratified_uptake_canary_v0_8_3 as base
import role_stratified_uptake_integrity_v0_8_3_1 as source_bound
import role_stratified_uptake_integrity_v0_8_3_2 as snapshot_bound
from ebrt_core import EBRTError, _canonical_bytes, _seal, _sealed_snapshot


LOCK_SCHEMA_VERSION = "ebrt-role-uptake-loader-lock-v0.8.3.3"
RUN_SCHEMA_VERSION = "ebrt-role-uptake-loader-run-v0.8.3.3"
SELF_TEST_SCHEMA_VERSION = "ebrt-role-uptake-loader-self-test-v0.8.3.3"
STAGING_POLICY = {
    "strategy": "PRIVATE_APFS_COPY_ON_WRITE_CLONE",
    "loader_receives_cache_path": False,
    "staged_entries": "REGULAR_FILES_ONLY",
    "staged_file_mode": "0444",
    "private_directory_mode_during_load": "0500",
    "source_and_staged_inodes": "REQUIRE_DISTINCT",
    "content_check": "EXACT_LOCKED_BLOB_HASH_BEFORE_AND_AFTER_LOAD_AND_CALLS",
    "staged_path_exported": False,
}
CLAIM_BOUNDARY = (
    "This r04 execution repeats already observed cases only to bind the verified bytes to the actual MLX loader path.",
    "The staged run is contaminated by known r01-r03 outputs and is not fresh scientific replication evidence.",
    "MLX receives a private copy-on-write regular-file tree, never the writable Hugging Face cache path.",
    "All staged files are exact locked bytes, distinct inodes, read-only during loading, and rehashed after calls.",
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
        raise EBRTError("ROLE_LOADER_SOURCE_READ_FAILED") from error
    return digest.hexdigest()


def _git_blob_sha1(path: Path) -> str:
    try:
        size = path.stat().st_size
    except OSError as error:
        raise EBRTError("ROLE_LOADER_SOURCE_STAT_FAILED") from error
    digest = hashlib.sha1()
    digest.update(f"blob {size}\0".encode("ascii"))
    try:
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
    except OSError as error:
        raise EBRTError("ROLE_LOADER_SOURCE_READ_FAILED") from error
    return digest.hexdigest()


def _content_address(path: Path, algorithm: str) -> str:
    if algorithm == "sha256":
        return _sha256(path)
    if algorithm == "git_blob_sha1":
        return _git_blob_sha1(path)
    raise EBRTError("ROLE_LOADER_HASH_ALGORITHM_INVALID")


def _load_json(path: Path) -> JsonObject:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EBRTError("ROLE_LOADER_ARTIFACT_READ_FAILED") from error
    if not isinstance(value, dict):
        raise EBRTError("ROLE_LOADER_ARTIFACT_TYPE_INVALID")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _validate_staged_tree(root: Path) -> JsonObject:
    expected = sorted(
        snapshot_bound.EXPECTED_SNAPSHOT_FILES,
        key=lambda row: row["relative_path"],
    )
    try:
        actual_paths = sorted(
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if not path.is_dir()
        )
    except (OSError, RuntimeError) as error:
        raise EBRTError("ROLE_LOADER_STAGED_TREE_READ_FAILED") from error
    expected_paths = [row["relative_path"] for row in expected]
    if actual_paths != expected_paths:
        raise EBRTError("ROLE_LOADER_STAGED_PATH_SET_MISMATCH")
    rows: list[JsonObject] = []
    for expected_row in expected:
        path = root / expected_row["relative_path"]
        try:
            stat = path.lstat()
        except OSError as error:
            raise EBRTError("ROLE_LOADER_STAGED_FILE_STAT_FAILED") from error
        if path.is_symlink() or not path.is_file():
            raise EBRTError("ROLE_LOADER_STAGED_FILE_TYPE_INVALID")
        address = _content_address(path, expected_row["address_algorithm"])
        row = {
            "relative_path": expected_row["relative_path"],
            "blob_address": address,
            "address_algorithm": expected_row["address_algorithm"],
            "size_bytes": stat.st_size,
        }
        if row != expected_row:
            raise EBRTError("ROLE_LOADER_STAGED_CONTENT_MISMATCH")
        rows.append(row)
    return _seal(
        {
            "schema_version": "ebrt-loader-staged-manifest-v0.8.3.3",
            "model_id": base.MODEL_ID,
            "files": rows,
        }
    )


def _clone_exact_snapshot(source_path: str, destination: Path) -> JsonObject:
    source_root = Path(source_path).expanduser().resolve()
    source_manifest = snapshot_bound._bind_snapshot(source_path)
    inode_pairs: list[tuple[int, int]] = []
    for row in sorted(
        snapshot_bound.EXPECTED_SNAPSHOT_FILES,
        key=lambda value: value["relative_path"],
    ):
        source = (source_root / row["relative_path"]).resolve(strict=True)
        target = destination / row["relative_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            completed = subprocess.run(
                ["/bin/cp", "-c", str(source), str(target)],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as error:
            raise EBRTError("ROLE_LOADER_CLONE_EXECUTION_FAILED") from error
        if completed.returncode != 0:
            raise EBRTError("ROLE_LOADER_APFS_CLONE_FAILED")
        try:
            source_stat = source.stat()
            target_stat = target.stat()
            target.chmod(0o444)
        except OSError as error:
            raise EBRTError("ROLE_LOADER_CLONE_STAT_FAILED") from error
        if (
            source_stat.st_dev != target_stat.st_dev
            or source_stat.st_ino == target_stat.st_ino
        ):
            raise EBRTError("ROLE_LOADER_CLONE_INODE_ISOLATION_FAILED")
        inode_pairs.append((source_stat.st_ino, target_stat.st_ino))
    staged_manifest = _validate_staged_tree(destination)
    return _seal(
        {
            "status": "PASS",
            "source_manifest_fingerprint_sha256": source_manifest["fingerprint_sha256"],
            "staged_manifest_fingerprint_sha256": staged_manifest["fingerprint_sha256"],
            "file_count": len(inode_pairs),
            "all_source_and_staged_inodes_distinct": all(
                source != staged for source, staged in inode_pairs
            ),
            "staging_strategy": STAGING_POLICY["strategy"],
            "staged_path_exported": False,
        }
    )


def lock_spec(
    base_lock: Mapping[str, Any],
    source_lock: Mapping[str, Any],
    snapshot_lock: Mapping[str, Any],
) -> JsonObject:
    locked_base = base.validate_lock(base_lock)
    locked_source = source_bound.validate_lock(source_lock, base_lock)
    locked_snapshot = snapshot_bound.validate_lock(
        snapshot_lock, base_lock, source_lock
    )
    return _seal(
        {
            "schema_version": LOCK_SCHEMA_VERSION,
            "status": "LOCKED_BEFORE_PROVIDER_CALLS",
            "wrapper_sha256": _sha256(Path(__file__)),
            "base_lock_fingerprint_sha256": locked_base["fingerprint_sha256"],
            "source_lock_fingerprint_sha256": locked_source["fingerprint_sha256"],
            "snapshot_lock_fingerprint_sha256": locked_snapshot["fingerprint_sha256"],
            "exact_snapshot_manifest_fingerprint_sha256": locked_snapshot[
                "snapshot_manifest_fingerprint_sha256"
            ],
            "staging_policy": STAGING_POLICY,
            "replication_status": "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R03_CASES",
            "effect_attribution_status": "NOT_ASSESSED",
            "claim_boundary": list(CLAIM_BOUNDARY),
        }
    )


def validate_lock(
    value: Any,
    base_lock: Mapping[str, Any],
    source_lock: Mapping[str, Any],
    snapshot_lock: Mapping[str, Any],
) -> JsonObject:
    observed = _sealed_snapshot(value, "ROLE_LOADER_LOCK")
    expected = lock_spec(base_lock, source_lock, snapshot_lock)
    if _canonical_bytes(observed) != _canonical_bytes(expected):
        raise EBRTError("ROLE_LOADER_LOCK_MISMATCH")
    return observed


def run_integrity_replication(
    model_path: str,
    lock: Mapping[str, Any],
    base_lock: Mapping[str, Any],
    source_lock: Mapping[str, Any],
    snapshot_lock: Mapping[str, Any],
) -> JsonObject:
    locked = validate_lock(lock, base_lock, source_lock, snapshot_lock)
    with tempfile.TemporaryDirectory(prefix="ebrt-v0833-") as temporary:
        staged_root = Path(temporary) / "snapshot"
        staged_root.mkdir(mode=0o700)
        clone_receipt = _clone_exact_snapshot(model_path, staged_root)
        before = _validate_staged_tree(staged_root)
        staged_root.chmod(0o500)
        try:
            base_run = base.run_canary(str(staged_root), base_lock)
            after = _validate_staged_tree(staged_root)
        finally:
            staged_root.chmod(0o700)
        if _canonical_bytes(before) != _canonical_bytes(after):
            raise EBRTError("ROLE_LOADER_STAGED_BYTES_CHANGED_DURING_RUN")
    return _seal(
        {
            "schema_version": RUN_SCHEMA_VERSION,
            "status": "COMPLETE",
            "policy_lock_fingerprint_sha256": locked["fingerprint_sha256"],
            "clone_receipt": clone_receipt,
            "staged_manifest_fingerprint_before": before["fingerprint_sha256"],
            "staged_manifest_fingerprint_after": after["fingerprint_sha256"],
            "staged_bytes_unchanged": True,
            "base_run": base_run,
            "summary": base_run["summary"],
            "replication_status": "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R03_CASES",
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
) -> JsonObject:
    locked = validate_lock(lock, base_lock, source_lock, snapshot_lock)
    snapshot = _sealed_snapshot(value, "ROLE_LOADER_RUN")
    expected_keys = {
        "schema_version",
        "status",
        "policy_lock_fingerprint_sha256",
        "clone_receipt",
        "staged_manifest_fingerprint_before",
        "staged_manifest_fingerprint_after",
        "staged_bytes_unchanged",
        "base_run",
        "summary",
        "replication_status",
        "effect_attribution_status",
        "claim_boundary",
        "fingerprint_sha256",
    }
    clone = _sealed_snapshot(snapshot.get("clone_receipt"), "ROLE_LOADER_CLONE")
    expected_manifest_fingerprint = _seal(
        {
            "schema_version": "ebrt-loader-staged-manifest-v0.8.3.3",
            "model_id": base.MODEL_ID,
            "files": sorted(
                snapshot_bound.EXPECTED_SNAPSHOT_FILES,
                key=lambda row: row["relative_path"],
            ),
        }
    )["fingerprint_sha256"]
    expected_clone = {
        "status": "PASS",
        "source_manifest_fingerprint_sha256": locked[
            "exact_snapshot_manifest_fingerprint_sha256"
        ],
        "staged_manifest_fingerprint_sha256": expected_manifest_fingerprint,
        "file_count": 7,
        "all_source_and_staged_inodes_distinct": True,
        "staging_strategy": STAGING_POLICY["strategy"],
        "staged_path_exported": False,
    }
    if (
        set(snapshot) != expected_keys
        or snapshot.get("schema_version") != RUN_SCHEMA_VERSION
        or snapshot.get("status") != "COMPLETE"
        or snapshot.get("policy_lock_fingerprint_sha256")
        != locked["fingerprint_sha256"]
        or _canonical_bytes(clone) != _canonical_bytes(_seal(expected_clone))
        or snapshot.get("staged_manifest_fingerprint_before")
        != expected_manifest_fingerprint
        or snapshot.get("staged_manifest_fingerprint_after")
        != expected_manifest_fingerprint
        or snapshot.get("staged_bytes_unchanged") is not True
        or snapshot.get("replication_status")
        != "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R03_CASES"
        or snapshot.get("effect_attribution_status") != "NOT_ASSESSED"
        or snapshot.get("claim_boundary") != list(CLAIM_BOUNDARY)
    ):
        raise EBRTError("ROLE_LOADER_RUN_HEADER_INVALID")
    base_verification = base.verify_run(snapshot.get("base_run"), base_lock)
    if _canonical_bytes(snapshot.get("summary")) != _canonical_bytes(
        snapshot["base_run"]["summary"]
    ):
        raise EBRTError("ROLE_LOADER_SUMMARY_MISMATCH")
    return _seal(
        {
            "schema_version": "ebrt-role-uptake-loader-verification-v0.8.3.3",
            "status": "PASS",
            "run_fingerprint_sha256": snapshot["fingerprint_sha256"],
            "base_verification_fingerprint_sha256": base_verification[
                "fingerprint_sha256"
            ],
            "checks": {
                "pre_call_lock_exact": True,
                "cache_path_not_passed_to_loader": True,
                "copy_on_write_clone_inodes_distinct": True,
                "exact_staged_bytes_checked_before_and_after": True,
                "base_run_portably_verified": True,
                "known_case_replication_boundary_exact": True,
            },
        }
    )


def self_test(
    base_lock: Mapping[str, Any],
    source_lock: Mapping[str, Any],
    snapshot_lock: Mapping[str, Any],
) -> JsonObject:
    spec = lock_spec(base_lock, source_lock, snapshot_lock)
    checks = {
        "loader_never_receives_cache_path": spec["staging_policy"][
            "loader_receives_cache_path"
        ]
        is False,
        "staged_files_are_regular_only": spec["staging_policy"]["staged_entries"]
        == "REGULAR_FILES_ONLY",
        "staged_files_are_read_only": spec["staging_policy"]["staged_file_mode"]
        == "0444",
        "distinct_inodes_required": spec["staging_policy"]["source_and_staged_inodes"]
        == "REQUIRE_DISTINCT",
        "exact_pre_post_content_check_required": spec["staging_policy"]["content_check"]
        == "EXACT_LOCKED_BLOB_HASH_BEFORE_AND_AFTER_LOAD_AND_CALLS",
        "known_case_replication_label_exact": spec["replication_status"]
        == "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R03_CASES",
    }
    if not all(checks.values()):
        raise EBRTError("ROLE_LOADER_SELF_TEST_FAILED")
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
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("self-test")
    commands.add_parser("lock-spec")
    clone_test = commands.add_parser("clone-test")
    clone_test.add_argument("--model", required=True)
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
        if args.command == "self-test":
            value = self_test(base_lock, source_lock, snapshot_lock)
        elif args.command == "lock-spec":
            value = lock_spec(base_lock, source_lock, snapshot_lock)
        elif args.command == "clone-test":
            with tempfile.TemporaryDirectory(prefix="ebrt-v0833-test-") as temporary:
                root = Path(temporary) / "snapshot"
                root.mkdir(mode=0o700)
                value = _clone_exact_snapshot(args.model, root)
        elif args.command == "run":
            value = run_integrity_replication(
                args.model,
                _load_json(args.lock),
                base_lock,
                source_lock,
                snapshot_lock,
            )
            _write_json(args.output, value)
        elif args.command == "verify":
            value = verify_run(
                _load_json(args.artifact),
                _load_json(args.lock),
                base_lock,
                source_lock,
                snapshot_lock,
            )
        else:  # pragma: no cover
            raise EBRTError("ROLE_LOADER_COMMAND_UNKNOWN")
        print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (EBRTError, subprocess.SubprocessError) as error:
        code = (
            str(error)
            if isinstance(error, EBRTError)
            else "ROLE_LOADER_SUBPROCESS_ERROR"
        )
        print(json.dumps({"status": "ERROR", "error_code": code}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
