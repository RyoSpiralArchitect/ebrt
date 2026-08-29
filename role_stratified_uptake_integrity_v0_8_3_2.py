#!/usr/bin/env python3
"""Exact snapshot-manifest replication wrapper for EBRT v0.8.3.

This r03 successor binds every expected snapshot-relative file to its exact
content-addressed Hugging Face blob before repeating the already known canary.
It is an integrity replication, not fresh scientific evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import role_stratified_uptake_canary_v0_8_3 as base
import role_stratified_uptake_integrity_v0_8_3_1 as prior
from ebrt_core import (
    EBRTError,
    _blob_content_matches_address,
    _canonical_bytes,
    _seal,
    _sealed_snapshot,
    _validated_cache_model_id,
)


LOCK_SCHEMA_VERSION = "ebrt-role-uptake-snapshot-lock-v0.8.3.2"
RUN_SCHEMA_VERSION = "ebrt-role-uptake-snapshot-run-v0.8.3.2"
SELF_TEST_SCHEMA_VERSION = "ebrt-role-uptake-snapshot-self-test-v0.8.3.2"
EXPECTED_SNAPSHOT_FILES = (
    {
        "relative_path": "config.json",
        "blob_address": "68b84bf6877ff51d722ec9f076527ab29243d567",
        "address_algorithm": "git_blob_sha1",
        "size_bytes": 721,
    },
    {
        "relative_path": "model.safetensors",
        "blob_address": "d7182d886f93a9efa73d6d556ee33ffe839a4e09e15965eeef46f295ab5b503d",
        "address_algorithm": "sha256",
        "size_bytes": 4077480215,
    },
    {
        "relative_path": "model.safetensors.index.json",
        "blob_address": "807607fbe7e64033bb4dc8114430d8ddbfae4fff",
        "address_algorithm": "git_blob_sha1",
        "size_bytes": 52381,
    },
    {
        "relative_path": "special_tokens_map.json",
        "blob_address": "451134b2ddc2e78555d1e857518c54b4bdc2e87d",
        "address_algorithm": "git_blob_sha1",
        "size_bytes": 414,
    },
    {
        "relative_path": "tokenizer.json",
        "blob_address": "8d7d23136b474a3df1182ed829db19984e295ee7",
        "address_algorithm": "git_blob_sha1",
        "size_bytes": 1961548,
    },
    {
        "relative_path": "tokenizer.model",
        "blob_address": "37f00374dea48658ee8f5d0f21895b9bc55cb0103939607c8185bfd1c6ca1f89",
        "address_algorithm": "sha256",
        "size_bytes": 587404,
    },
    {
        "relative_path": "tokenizer_config.json",
        "blob_address": "dd6391393bf053f6ae562e7ec833bc94d4670680",
        "address_algorithm": "git_blob_sha1",
        "size_bytes": 138039,
    },
)
CLAIM_BOUNDARY = (
    "This r03 execution repeats the already observed r01/r02 cases only to bind the exact expected model snapshot manifest.",
    "The repeated outputs are contaminated by known prior results and are not fresh scientific replication evidence.",
    "Every admitted snapshot file must resolve to the exact pre-locked content-addressed blob and byte size.",
    "The exact snapshot manifest is checked immediately before and after the nine provider calls.",
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
        raise EBRTError("ROLE_SNAPSHOT_SOURCE_READ_FAILED") from error
    return digest.hexdigest()


def _load_json(path: Path) -> JsonObject:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EBRTError("ROLE_SNAPSHOT_ARTIFACT_READ_FAILED") from error
    if not isinstance(value, dict):
        raise EBRTError("ROLE_SNAPSHOT_ARTIFACT_TYPE_INVALID")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _expected_manifest() -> JsonObject:
    files = sorted(EXPECTED_SNAPSHOT_FILES, key=lambda row: row["relative_path"])
    return _seal(
        {
            "schema_version": "ebrt-exact-model-snapshot-manifest-v0.8.3.2",
            "model_id": base.MODEL_ID,
            "files": files,
        }
    )


def _actual_manifest(model_path: str) -> JsonObject:
    root = Path(model_path).expanduser().resolve()
    if _validated_cache_model_id(root) != base.MODEL_ID:
        raise EBRTError("ROLE_SNAPSHOT_MODEL_ID_MISMATCH")
    rows: list[JsonObject] = []
    try:
        entries = sorted(
            root.rglob("*"), key=lambda path: path.relative_to(root).as_posix()
        )
        for entry in entries:
            if entry.is_dir() and not entry.is_symlink():
                continue
            if not entry.is_symlink():
                raise EBRTError("ROLE_SNAPSHOT_ENTRY_NOT_SYMLINK")
            target = entry.resolve(strict=True)
            blob_address = target.name
            if len(blob_address) == 64:
                algorithm = "sha256"
            elif len(blob_address) == 40:
                algorithm = "git_blob_sha1"
            else:
                raise EBRTError("ROLE_SNAPSHOT_BLOB_ADDRESS_INVALID")
            if not _blob_content_matches_address(target):
                raise EBRTError("ROLE_SNAPSHOT_BLOB_CONTENT_INVALID")
            rows.append(
                {
                    "relative_path": entry.relative_to(root).as_posix(),
                    "blob_address": blob_address,
                    "address_algorithm": algorithm,
                    "size_bytes": target.stat().st_size,
                }
            )
    except EBRTError:
        raise
    except (OSError, RuntimeError) as error:
        raise EBRTError("ROLE_SNAPSHOT_MANIFEST_READ_FAILED") from error
    return _seal(
        {
            "schema_version": "ebrt-exact-model-snapshot-manifest-v0.8.3.2",
            "model_id": base.MODEL_ID,
            "files": rows,
        }
    )


def _bind_snapshot(model_path: str) -> JsonObject:
    observed = _actual_manifest(model_path)
    expected = _expected_manifest()
    if _canonical_bytes(observed) != _canonical_bytes(expected):
        raise EBRTError("ROLE_SNAPSHOT_MANIFEST_MISMATCH")
    return observed


def lock_spec(
    base_lock: Mapping[str, Any], prior_lock: Mapping[str, Any]
) -> JsonObject:
    locked_base = base.validate_lock(base_lock)
    locked_prior = prior.validate_lock(prior_lock, base_lock)
    manifest = _expected_manifest()
    return _seal(
        {
            "schema_version": LOCK_SCHEMA_VERSION,
            "status": "LOCKED_BEFORE_PROVIDER_CALLS",
            "wrapper_sha256": _sha256(Path(__file__)),
            "prior_lock_fingerprint_sha256": locked_prior["fingerprint_sha256"],
            "base_lock_fingerprint_sha256": locked_base["fingerprint_sha256"],
            "snapshot_manifest": manifest,
            "snapshot_manifest_fingerprint_sha256": manifest["fingerprint_sha256"],
            "replication_status": "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R02_CASES",
            "effect_attribution_status": "NOT_ASSESSED",
            "claim_boundary": list(CLAIM_BOUNDARY),
        }
    )


def validate_lock(
    value: Any,
    base_lock: Mapping[str, Any],
    prior_lock: Mapping[str, Any],
) -> JsonObject:
    observed = _sealed_snapshot(value, "ROLE_SNAPSHOT_LOCK")
    expected = lock_spec(base_lock, prior_lock)
    if _canonical_bytes(observed) != _canonical_bytes(expected):
        raise EBRTError("ROLE_SNAPSHOT_LOCK_MISMATCH")
    return observed


def run_integrity_replication(
    model_path: str,
    lock: Mapping[str, Any],
    base_lock: Mapping[str, Any],
    prior_lock: Mapping[str, Any],
) -> JsonObject:
    locked = validate_lock(lock, base_lock, prior_lock)
    before = _bind_snapshot(model_path)
    prior_run = prior.run_integrity_replication(model_path, prior_lock, base_lock)
    after = _bind_snapshot(model_path)
    if _canonical_bytes(before) != _canonical_bytes(after):
        raise EBRTError("ROLE_SNAPSHOT_CHANGED_DURING_RUN")
    return _seal(
        {
            "schema_version": RUN_SCHEMA_VERSION,
            "status": "COMPLETE",
            "policy_lock_fingerprint_sha256": locked["fingerprint_sha256"],
            "snapshot_manifest_fingerprint_before": before["fingerprint_sha256"],
            "snapshot_manifest_fingerprint_after": after["fingerprint_sha256"],
            "snapshot_manifest_unchanged": True,
            "prior_run": prior_run,
            "summary": prior_run["summary"],
            "replication_status": "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R02_CASES",
            "effect_attribution_status": "NOT_ASSESSED",
            "claim_boundary": list(CLAIM_BOUNDARY),
        }
    )


def verify_run(
    value: Any,
    lock: Mapping[str, Any],
    base_lock: Mapping[str, Any],
    prior_lock: Mapping[str, Any],
) -> JsonObject:
    locked = validate_lock(lock, base_lock, prior_lock)
    snapshot = _sealed_snapshot(value, "ROLE_SNAPSHOT_RUN")
    expected_keys = {
        "schema_version",
        "status",
        "policy_lock_fingerprint_sha256",
        "snapshot_manifest_fingerprint_before",
        "snapshot_manifest_fingerprint_after",
        "snapshot_manifest_unchanged",
        "prior_run",
        "summary",
        "replication_status",
        "effect_attribution_status",
        "claim_boundary",
        "fingerprint_sha256",
    }
    manifest_fingerprint = locked["snapshot_manifest_fingerprint_sha256"]
    if (
        set(snapshot) != expected_keys
        or snapshot.get("schema_version") != RUN_SCHEMA_VERSION
        or snapshot.get("status") != "COMPLETE"
        or snapshot.get("policy_lock_fingerprint_sha256")
        != locked["fingerprint_sha256"]
        or snapshot.get("snapshot_manifest_fingerprint_before") != manifest_fingerprint
        or snapshot.get("snapshot_manifest_fingerprint_after") != manifest_fingerprint
        or snapshot.get("snapshot_manifest_unchanged") is not True
        or snapshot.get("replication_status")
        != "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R02_CASES"
        or snapshot.get("effect_attribution_status") != "NOT_ASSESSED"
        or snapshot.get("claim_boundary") != list(CLAIM_BOUNDARY)
    ):
        raise EBRTError("ROLE_SNAPSHOT_RUN_HEADER_INVALID")
    prior_verification = prior.verify_run(
        snapshot.get("prior_run"), prior_lock, base_lock
    )
    if _canonical_bytes(snapshot.get("summary")) != _canonical_bytes(
        snapshot["prior_run"]["summary"]
    ):
        raise EBRTError("ROLE_SNAPSHOT_SUMMARY_MISMATCH")
    return _seal(
        {
            "schema_version": "ebrt-role-uptake-snapshot-verification-v0.8.3.2",
            "status": "PASS",
            "run_fingerprint_sha256": snapshot["fingerprint_sha256"],
            "prior_verification_fingerprint_sha256": prior_verification[
                "fingerprint_sha256"
            ],
            "checks": {
                "pre_call_lock_exact": True,
                "exact_expected_blob_manifest_bound": True,
                "manifest_checked_before_and_after_calls": True,
                "prior_source_and_model_binding_verified": True,
                "known_case_replication_boundary_exact": True,
            },
        }
    )


def self_test(
    base_lock: Mapping[str, Any], prior_lock: Mapping[str, Any]
) -> JsonObject:
    spec = lock_spec(base_lock, prior_lock)
    manifest = spec["snapshot_manifest"]
    checks = {
        "seven_expected_snapshot_files": len(manifest["files"]) == 7,
        "snapshot_paths_unique": len(
            {row["relative_path"] for row in manifest["files"]}
        )
        == len(manifest["files"]),
        "all_blob_addresses_are_hashes": all(
            len(row["blob_address"]) in {40, 64} for row in manifest["files"]
        ),
        "all_sizes_positive": all(
            type(row["size_bytes"]) is int and row["size_bytes"] > 0
            for row in manifest["files"]
        ),
        "model_weight_blob_is_sha256_bound": any(
            row["relative_path"] == "model.safetensors"
            and row["address_algorithm"] == "sha256"
            and len(row["blob_address"]) == 64
            for row in manifest["files"]
        ),
        "known_case_replication_label_exact": spec["replication_status"]
        == "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R02_CASES",
    }
    if not all(checks.values()):
        raise EBRTError("ROLE_SNAPSHOT_SELF_TEST_FAILED")
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
    parser.add_argument("--prior-lock", type=Path, required=True)
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
        prior_lock = _load_json(args.prior_lock)
        if args.command == "self-test":
            value = self_test(base_lock, prior_lock)
        elif args.command == "lock-spec":
            value = lock_spec(base_lock, prior_lock)
        elif args.command == "run":
            value = run_integrity_replication(
                args.model,
                _load_json(args.lock),
                base_lock,
                prior_lock,
            )
            _write_json(args.output, value)
        elif args.command == "verify":
            value = verify_run(
                _load_json(args.artifact),
                _load_json(args.lock),
                base_lock,
                prior_lock,
            )
        else:  # pragma: no cover
            raise EBRTError("ROLE_SNAPSHOT_COMMAND_UNKNOWN")
        print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except EBRTError as error:
        print(json.dumps({"status": "ERROR", "error_code": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
