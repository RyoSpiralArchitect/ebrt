#!/usr/bin/env python3
"""Build the sealed, network-zero EBRT v0.5.5 lane-composition bundle.

The builder byte-copies three committed v0.5.4 sealed lanes, verifies their
complete predecessor receipt chain, and publishes only public composition,
merge, control, and block-adjoint artifacts.  No provider, model, agent,
router, tool, memory, UI, or natural-language generation participates.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import json
import os
import re
import shutil
import socket
import stat
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterator, Mapping, Optional, Sequence
from unittest import mock

import benchmark_lane_composition_v0_5_5 as benchmark
import lane_composable_trajectory_v0_5_5 as core


ROOT = Path(__file__).resolve().parent
LOCK_PATH = ROOT / "policy_lock_lane_composition_v0_5_5.json"

LOCK_SCHEMA_VERSION = "ebrt-lane-composition-policy-lock-v0.5.5"
LOCK_STATUS = "LOCKED_CONTAMINATED_NETWORK_ZERO_LANE_COMPOSITION"
MANIFEST_SCHEMA_VERSION = "ebrt-lane-composition-manifest-v0.5.5"
BUNDLE_STATUS = "COMPLETE_CONTAMINATED_NETWORK_ZERO_LANE_COMPOSITION"
PROMOTION_STATUS = "PROMOTE_V0_6_LANE_COMPOSITION_GATE"
STOP_STATUS = "STOP_V0_6_LANE_COMPOSITION_GATE"
PROMOTION_CLAIM = (
    "On one contaminated frozen public bundle, EBRT composed three byte-sealed "
    "trajectories through one typed merge junction while preserving shared-evidence "
    "byte identity, lane-local provenance and isolation, and exact block-gradient "
    "agreement."
)

ARTIFACT_DIRECTORY = "artifacts/lane_composition_v0_5_5"
ROOT_ARTIFACT_FILES = (
    "shared_evidence_ledger.json",
    "sealed_bundle.json",
    "merge_contract.json",
    "bundle_control_map.json",
    "block_adjoint_audit.json",
    "hard_gate_audit.json",
    "self_test.json",
    "mechanism_report.md",
)
SEALED_LANE_FILES = (
    "sealed_lanes/correction_early.json",
    "sealed_lanes/correction_late.json",
    "sealed_lanes/stable_constraint.json",
)
MANIFEST_FILENAME = "manifest.json"
ARTIFACT_FILES = (*ROOT_ARTIFACT_FILES, *SEALED_LANE_FILES)
ALL_ARTIFACT_FILES = (*ARTIFACT_FILES, MANIFEST_FILENAME)

CORE_PAYLOAD_KEYS = (
    "shared_evidence_ledger",
    "sealed_bundle",
    "merge_contract",
    "bundle_control_map",
    "block_adjoint_audit",
    "hard_gate_audit",
    "self_test",
)
PAYLOAD_TO_FILENAME = {
    "shared_evidence_ledger": "shared_evidence_ledger.json",
    "sealed_bundle": "sealed_bundle.json",
    "merge_contract": "merge_contract.json",
    "bundle_control_map": "bundle_control_map.json",
    "block_adjoint_audit": "block_adjoint_audit.json",
    "hard_gate_audit": "hard_gate_audit.json",
    "self_test": "self_test.json",
}

CORE_SOURCE_PATH = "lane_composable_trajectory_v0_5_5.py"
BENCHMARK_SOURCE_PATH = "benchmark_lane_composition_v0_5_5.py"
BUILDER_SOURCE_PATH = "build_lane_composition_artifact_v0_5_5.py"
COMPOSITION_FIXTURE_PATH = "fixtures/lane_composition_v0_5_5.json"
ONE_LANE_FIXTURE_PATH = "fixtures/lane_composition_v0_5_5_one_lane.json"

PREDECESSOR_COMMIT_SHA = "33e3beee2c175217c6a493b7eec86e01b54780e8"
PREDECESSOR_TREE_SHA = "9920bac359f7d13e63676f2fc13120383293b337"
PREDECESSOR_MANIFEST_SHA256 = (
    "3a7e1c1903e447cba9c0da471558074d4558386c79e112addc090768978d5472"
)
PREDECESSOR_SOURCE_RECEIPTS = {
    "benchmark": {
        "path": "benchmark_temporal_adjoint_lineage_v0_5_4.py",
        "bytes": 9745,
        "sha256": "6459e97ae44967f301bd7ec7cb360126432d213965240d754e27619590cc87b8",
    },
    "builder": {
        "path": "build_temporal_adjoint_lineage_artifact_v0_5_4.py",
        "bytes": 51260,
        "sha256": "bd70d4313989589959b7cd8c6542ce066034a36e460c470b753a6910b5596ffe",
    },
    "composition_source": {
        "path": "temporal_adjoint_lineage_v0_5_4.py",
        "bytes": 96418,
        "sha256": "c92acd3a51b16caada00c58bcf40ef11b1031a7161e1afd6e282266924c8461b",
    },
    "event_fixture": {
        "path": "fixtures/temporal_adjoint_lineage_v0_5_4_dev.json",
        "bytes": 1050,
        "sha256": "a1d4b2d55d403c13e89548dbe54ba4ebc80401a1e70b1972541039afeb1b7749",
    },
    "no_event_fixture": {
        "path": "fixtures/temporal_adjoint_lineage_v0_5_4_no_event.json",
        "bytes": 915,
        "sha256": "e3ff041d8983f43cb0cfa7d60dd1baca041c7c714bd4af381f2690e08c4580a7",
    },
    "policy_lock": {
        "path": "policy_lock_temporal_adjoint_lineage_v0_5_4.json",
        "bytes": 10155,
        "sha256": "44a30c082b7239464e25ef0a2d82e7442155306dca05317f2c9dcc3c466e6dc5",
    },
}
PREDECESSOR_ARTIFACT_RECEIPTS = {
    "actuator_geometry.json": {
        "path": "artifacts/temporal_adjoint_lineage_v0_5_4/actuator_geometry.json",
        "bytes": 178587,
        "sha256": "f257403ddbf204d46af5c3807c37b3102fe8e7c39da35b62840b400e7a96b43f",
    },
    "arm_comparison.json": {
        "path": "artifacts/temporal_adjoint_lineage_v0_5_4/arm_comparison.json",
        "bytes": 13235,
        "sha256": "944039a8c58b61847d8ee0ed78c1b9adcc7903a49d13c787afab0bc22e6f2f23",
    },
    "compiled_programs.json": {
        "path": "artifacts/temporal_adjoint_lineage_v0_5_4/compiled_programs.json",
        "bytes": 10636,
        "sha256": "357bab8950da93a08c0d3f459bcf347e533feac28629db7bd77fa87e60c805ab",
    },
    "correction_early_sealed_lane.json": {
        "path": "artifacts/temporal_adjoint_lineage_v0_5_4/correction_early_sealed_lane.json",
        "bytes": 69960,
        "sha256": "799b2d6b10129e63e751054e995d2e5017a2f73af44916d68068ee3c82b72d17",
    },
    "correction_late_sealed_lane.json": {
        "path": "artifacts/temporal_adjoint_lineage_v0_5_4/correction_late_sealed_lane.json",
        "bytes": 69447,
        "sha256": "54c806a29fdf80f9677b5a008e140734e28a201e719a98ce8d312bf34298afc8",
    },
    "manifest.json": {
        "path": "artifacts/temporal_adjoint_lineage_v0_5_4/manifest.json",
        "bytes": 4920,
        "sha256": PREDECESSOR_MANIFEST_SHA256,
    },
    "mechanism_report.md": {
        "path": "artifacts/temporal_adjoint_lineage_v0_5_4/mechanism_report.md",
        "bytes": 4029,
        "sha256": "342fdc8fbec51112b2a981c2f30d4395aba8bb5b52bdac3d58caa2cfb5c84899",
    },
    "no_event_audit.json": {
        "path": "artifacts/temporal_adjoint_lineage_v0_5_4/no_event_audit.json",
        "bytes": 1207,
        "sha256": "ec5da4ddf51123ade7d2495eb13685c310131bdab3fe4aec88310740da370909",
    },
    "self_test.json": {
        "path": "artifacts/temporal_adjoint_lineage_v0_5_4/self_test.json",
        "bytes": 6077,
        "sha256": "488b5041ef99b1b8663a03d098a426c7c59a88de4e2a257f03a1f72b24f8c5d4",
    },
    "source_receipt.json": {
        "path": "artifacts/temporal_adjoint_lineage_v0_5_4/source_receipt.json",
        "bytes": 4811,
        "sha256": "84847669eca84c83cf8334658e6f5106c37d3e8a32aa4bbe7793dedb5bf5969f",
    },
    "stable_constraint_sealed_lane.json": {
        "path": "artifacts/temporal_adjoint_lineage_v0_5_4/stable_constraint_sealed_lane.json",
        "bytes": 2972,
        "sha256": "4ea3d27501907821510c2ad6f7cea4c5c14057b505b6ff8463a53b66bf7e98b8",
    },
}
PREDECESSOR_LANES = {
    "correction_early": {
        "source_path": "artifacts/temporal_adjoint_lineage_v0_5_4/correction_early_sealed_lane.json",
        "artifact_path": "sealed_lanes/correction_early.json",
        "bytes": 69960,
        "sha256": "799b2d6b10129e63e751054e995d2e5017a2f73af44916d68068ee3c82b72d17",
    },
    "correction_late": {
        "source_path": "artifacts/temporal_adjoint_lineage_v0_5_4/correction_late_sealed_lane.json",
        "artifact_path": "sealed_lanes/correction_late.json",
        "bytes": 69447,
        "sha256": "54c806a29fdf80f9677b5a008e140734e28a201e719a98ce8d312bf34298afc8",
    },
    "stable_constraint": {
        "source_path": "artifacts/temporal_adjoint_lineage_v0_5_4/stable_constraint_sealed_lane.json",
        "artifact_path": "sealed_lanes/stable_constraint.json",
        "bytes": 2972,
        "sha256": "4ea3d27501907821510c2ad6f7cea4c5c14057b505b6ff8463a53b66bf7e98b8",
    },
}

TOP_LEVEL_GATE_IDS = (
    "v0_5_4_source_gate_exact",
    "one_lane_exact",
    "ledger_consistent",
    "namespace_isolated",
    "block_gradient_agreement",
    "disconnected_zero",
    "permutation_invariant",
    "tamper_ready_source_receipts",
    "bounds_complete",
    "deterministic_network_zero",
)
REQUIRED_SUBCHECK_IDS = (
    "all_six_lane_permutations_invariant",
    "artifact_tamper_rejected",
    "conflicting_axis_target_rejected",
    "conflicting_evidence_hash_rejected",
    "duplicate_lane_alias_rejected",
    "forbidden_schema_surface_rejected",
    "provider_calls_zero",
    "socket_denied",
    "source_tamper_rejected",
    "two_build_byte_identical",
)

EXPECTED_SCHEMAS = {
    "block_adjoint_audit": "ebrt-block-adjoint-audit-artifact-v0.5.5",
    "bundle_control_map": "ebrt-lane-control-bundle-artifact-v0.5.5",
    "fixture": "ebrt-lane-composition-fixture-v0.5.5",
    "hard_gate_audit": "ebrt-lane-composition-hard-gate-audit-v0.5.5",
    "manifest": MANIFEST_SCHEMA_VERSION,
    "merge_contract": "ebrt-lane-merge-contract-artifact-v0.5.5",
    "sealed_bundle": "ebrt-sealed-lane-composition-bundle-v0.5.5",
    "sealed_lane": "ebrt-sealed-temporal-lineage-lane-v0.5.4",
    "self_test": "ebrt-lane-composition-self-test-v0.5.5",
    "shared_evidence_ledger": "ebrt-shared-evidence-ledger-artifact-v0.5.5",
}
EXPECTED_CANONICALIZATION = {
    "allow_nan": False,
    "encoding": "utf-8",
    "ensure_ascii": False,
    "separators": [",", ":"],
    "sort_keys": True,
    "trailing_newline": True,
}
EXPECTED_EXPERIMENT_CONTRACT = {
    "contaminated": True,
    "junction_count": 1,
    "lane_ids": ["correction_early", "correction_late", "stable_constraint"],
    "network_calls": 0,
    "promotion_claim": PROMOTION_CLAIM,
    "promotion_status": PROMOTION_STATUS,
    "provider_calls": 0,
    "required_subcheck_ids": list(REQUIRED_SUBCHECK_IDS),
    "stop_status": STOP_STATUS,
    "top_level_gate_ids": list(TOP_LEVEL_GATE_IDS),
}
MAX_FILE_BYTES = 5_000_000
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ArtifactValidationError(RuntimeError):
    """A v0.5.5 lock, source, payload, artifact, or publication is invalid."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json_bytes(value: Any, *, trailing_newline: bool = False) -> bytes:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return encoded + (b"\n" if trailing_newline else b"")


def _pretty_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return _sha256_bytes(_canonical_json_bytes(value))


def _reject_constant(value: str) -> Any:
    raise ArtifactValidationError(f"non-finite JSON constant forbidden: {value}")


def _reject_duplicate_keys(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ArtifactValidationError(f"duplicate JSON key forbidden: {key}")
        result[key] = value
    return result


def _load_json_bytes(value: bytes, label: str) -> Any:
    try:
        text = value.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ArtifactValidationError(f"{label}: not UTF-8") from error
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except ArtifactValidationError:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise ArtifactValidationError(f"{label}: invalid strict JSON") from error


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ArtifactValidationError(message)


def _exact_mapping(value: Any, label: str, expected: set[str]) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), f"{label}: expected object")
    missing = sorted(expected - set(value))
    extra = sorted(set(value) - expected)
    _require(
        not missing and not extra,
        f"{label}: missing={missing or 'none'} extra={extra or 'none'}",
    )
    return value


def _string(value: Any, label: str) -> str:
    _require(
        isinstance(value, str) and value and value == value.strip(),
        f"{label}: expected trimmed non-empty string",
    )
    return value


def _integer(value: Any, label: str, *, minimum: int = 0) -> int:
    _require(type(value) is int and value >= minimum, f"{label}: invalid integer")
    return value


def _boolean(value: Any, label: str) -> bool:
    _require(type(value) is bool, f"{label}: expected boolean")
    return value


def _sha256_string(value: Any, label: str) -> str:
    digest = _string(value, label)
    _require(_SHA256_RE.fullmatch(digest) is not None, f"{label}: invalid SHA-256")
    return digest


def _safe_repo_path(repo_root: Path, value: Any, label: str) -> Path:
    relative = _string(value, label)
    pure = PurePosixPath(relative)
    _require(not pure.is_absolute(), f"{label}: absolute path forbidden")
    _require(".." not in pure.parts, f"{label}: traversal forbidden")
    candidate = repo_root.joinpath(*pure.parts)
    try:
        candidate.resolve().relative_to(repo_root.resolve())
    except ValueError as error:
        raise ArtifactValidationError(f"{label}: escaped repository root") from error
    return candidate


def _read_regular(path: Path, label: str, *, max_bytes: int = MAX_FILE_BYTES) -> bytes:
    try:
        before = path.lstat()
    except OSError as error:
        raise ArtifactValidationError(f"{label}: cannot stat {path}") from error
    _require(stat.S_ISREG(before.st_mode), f"{label}: expected regular file")
    _require(not path.is_symlink(), f"{label}: symlink forbidden")
    _require(before.st_size <= max_bytes, f"{label}: size cap exceeded")
    try:
        value = path.read_bytes()
        after = path.lstat()
    except OSError as error:
        raise ArtifactValidationError(f"{label}: cannot read {path}") from error
    _require(
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
        f"{label}: changed while read",
    )
    _require(len(value) == before.st_size, f"{label}: byte count changed")
    return value


def _read_json_regular(path: Path, label: str) -> tuple[Any, bytes]:
    raw = _read_regular(path, label)
    return _load_json_bytes(raw, label), raw


def _require_exact_json(value: Any, expected: Any, label: str) -> None:
    _require(
        _canonical_json_bytes(value) == _canonical_json_bytes(expected),
        f"{label}: differs from exact locked value",
    )


def _reject_runtime_metadata(value: Any, path: str = "artifact") -> None:
    forbidden = {
        "absolute_path",
        "created_at",
        "generated_at",
        "host",
        "hostname",
        "observed_runtime",
        "runtime_observed",
        "timestamp",
        "timestamp_utc",
        "updated_at",
    }
    if isinstance(value, Mapping):
        for key, child in value.items():
            _require(key not in forbidden, f"{path}: forbidden metadata key {key}")
            _reject_runtime_metadata(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_runtime_metadata(child, f"{path}[{index}]")


def _network_guard() -> Iterator[None]:
    def denied(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("network access attempted by network-zero builder")

    with contextlib.ExitStack() as stack:
        stack.enter_context(mock.patch.object(socket, "socket", side_effect=denied))
        stack.enter_context(
            mock.patch.object(socket, "create_connection", side_effect=denied)
        )
        stack.enter_context(mock.patch.object(socket, "getaddrinfo", side_effect=denied))
        yield


_network_guard = contextlib.contextmanager(_network_guard)


def _validate_receipt(
    value: Any,
    label: str,
    *,
    repo_root: Path,
    validate_bytes: bool,
    extra_keys: Sequence[str] = (),
) -> dict[str, Any]:
    record = dict(
        _exact_mapping(
            value,
            label,
            {"path", "bytes", "sha256", *extra_keys},
        )
    )
    path = _safe_repo_path(repo_root, record["path"], f"{label}.path")
    size = _integer(record["bytes"], f"{label}.bytes")
    digest = _sha256_string(record["sha256"], f"{label}.sha256")
    if validate_bytes:
        raw = _read_regular(path, label)
        _require(len(raw) == size, f"{label}: byte count mismatch")
        _require(_sha256_bytes(raw) == digest, f"{label}: digest mismatch")
    return record


def _validate_predecessor(
    value: Any, *, repo_root: Path, validate_bytes: bool
) -> dict[str, Any]:
    predecessor = dict(
        _exact_mapping(
            value,
            "lock.predecessor",
            {
                "artifact_receipts",
                "commit_sha",
                "lane_receipts",
                "manifest_sha256",
                "relationship",
                "source_receipts",
                "tree_sha",
            },
        )
    )
    _require(predecessor["commit_sha"] == PREDECESSOR_COMMIT_SHA, "commit drift")
    _require(predecessor["tree_sha"] == PREDECESSOR_TREE_SHA, "tree drift")
    _require(
        predecessor["manifest_sha256"] == PREDECESSOR_MANIFEST_SHA256,
        "predecessor manifest drift",
    )
    _string(predecessor["relationship"], "predecessor.relationship")
    _require_exact_json(
        predecessor["source_receipts"],
        PREDECESSOR_SOURCE_RECEIPTS,
        "predecessor source receipts",
    )
    _require_exact_json(
        predecessor["artifact_receipts"],
        PREDECESSOR_ARTIFACT_RECEIPTS,
        "predecessor artifact receipts",
    )
    _require_exact_json(
        predecessor["lane_receipts"], PREDECESSOR_LANES, "predecessor lanes"
    )
    for group in ("source_receipts", "artifact_receipts"):
        for name, receipt in predecessor[group].items():
            _validate_receipt(
                receipt,
                f"predecessor.{group}.{name}",
                repo_root=repo_root,
                validate_bytes=validate_bytes,
            )
    for lane_id, receipt in predecessor["lane_receipts"].items():
        exact = _exact_mapping(
            receipt,
            f"predecessor.lane_receipts.{lane_id}",
            {"source_path", "artifact_path", "bytes", "sha256"},
        )
        _require(
            exact["artifact_path"] == f"sealed_lanes/{lane_id}.json",
            f"lane artifact path drift: {lane_id}",
        )
        _validate_receipt(
            {
                "path": exact["source_path"],
                "bytes": exact["bytes"],
                "sha256": exact["sha256"],
            },
            f"predecessor lane {lane_id}",
            repo_root=repo_root,
            validate_bytes=validate_bytes,
        )
    if validate_bytes:
        manifest_path = _safe_repo_path(
            repo_root,
            predecessor["artifact_receipts"]["manifest.json"]["path"],
            "predecessor manifest path",
        )
        manifest, _raw = _read_json_regular(manifest_path, "predecessor manifest")
        _require(isinstance(manifest, Mapping), "predecessor manifest root invalid")
        _require(manifest.get("promotion_ready") is True, "v0.5.4 not promoted")
        _require(
            manifest.get("decision_status") == "PROMOTE_V0_5_5_TEMPORAL_GATE",
            "v0.5.4 decision status drift",
        )
        _require(
            manifest.get("network_calls") == 0
            and manifest.get("provider_calls") == 0,
            "v0.5.4 execution boundary drift",
        )
    return predecessor


def _validate_lock_mapping(
    value: Any,
    *,
    repo_root: Path = ROOT,
    validate_sources: bool = True,
) -> dict[str, Any]:
    lock = dict(
        _exact_mapping(
            value,
            "lock",
            {
                "artifact",
                "canonicalization",
                "claim_boundary",
                "experiment_contract",
                "fixtures",
                "predecessor",
                "schema_version",
                "schemas",
                "sources",
                "status",
            },
        )
    )
    _require(lock["schema_version"] == LOCK_SCHEMA_VERSION, "lock schema drift")
    _require(lock["status"] == LOCK_STATUS, "lock status drift")
    expected_paths = {
        "benchmark": BENCHMARK_SOURCE_PATH,
        "builder": BUILDER_SOURCE_PATH,
        "core": CORE_SOURCE_PATH,
    }
    sources = _exact_mapping(lock["sources"], "lock.sources", set(expected_paths))
    for name, item in sources.items():
        record = _validate_receipt(
            item,
            f"lock.sources.{name}",
            repo_root=repo_root,
            validate_bytes=validate_sources,
        )
        _require(record["path"] == expected_paths[name], f"source path drift: {name}")

    expected_fixture_paths = {
        "composition": COMPOSITION_FIXTURE_PATH,
        "one_lane": ONE_LANE_FIXTURE_PATH,
    }
    fixtures = _exact_mapping(
        lock["fixtures"], "lock.fixtures", set(expected_fixture_paths)
    )
    for name, item in fixtures.items():
        record = _validate_receipt(
            item,
            f"lock.fixtures.{name}",
            repo_root=repo_root,
            validate_bytes=validate_sources,
            extra_keys=("fixture_id", "schema_version"),
        )
        _require(
            record["path"] == expected_fixture_paths[name],
            f"fixture path drift: {name}",
        )
        _require(
            record["schema_version"] == EXPECTED_SCHEMAS["fixture"],
            f"fixture schema drift: {name}",
        )
        if validate_sources:
            fixture, _raw = _read_json_regular(
                _safe_repo_path(repo_root, record["path"], f"fixture {name} path"),
                f"fixture {name}",
            )
            _require(
                fixture.get("schema_version") == record["schema_version"]
                and fixture.get("fixture_id") == record["fixture_id"],
                f"fixture identity drift: {name}",
            )
            core.validate_fixture(fixture)

    _validate_predecessor(
        lock["predecessor"], repo_root=repo_root, validate_bytes=validate_sources
    )
    _require_exact_json(lock["schemas"], EXPECTED_SCHEMAS, "schemas")
    _require_exact_json(
        lock["experiment_contract"], EXPECTED_EXPERIMENT_CONTRACT, "experiment"
    )
    _require_exact_json(
        lock["canonicalization"], EXPECTED_CANONICALIZATION, "canonicalization"
    )
    artifact = _exact_mapping(
        lock["artifact"],
        "lock.artifact",
        {
            "directory",
            "files",
            "manifest_digest_coverage",
            "network_calls",
            "provider_calls",
            "runtime_contract",
        },
    )
    _require(artifact["directory"] == ARTIFACT_DIRECTORY, "artifact directory drift")
    _require_exact_json(artifact["files"], list(ALL_ARTIFACT_FILES), "artifact files")
    _require_exact_json(
        artifact["manifest_digest_coverage"],
        list(ARTIFACT_FILES),
        "manifest coverage",
    )
    _require(artifact["network_calls"] == 0, "artifact network calls drift")
    _require(artifact["provider_calls"] == 0, "artifact provider calls drift")
    _string(artifact["runtime_contract"], "artifact.runtime_contract")
    boundary = lock["claim_boundary"]
    _require(isinstance(boundary, list) and bool(boundary), "claim boundary empty")
    _require(
        all(isinstance(row, str) and row and row == row.strip() for row in boundary),
        "claim boundary invalid",
    )
    _require(PROMOTION_CLAIM in boundary, "promotion claim not locked")
    return lock


def _load_lock(*, repo_root: Path = ROOT) -> dict[str, Any]:
    value, _raw = _read_json_regular(repo_root / LOCK_PATH.name, "policy lock")
    return _validate_lock_mapping(value, repo_root=repo_root)


def _receipt_for(path: Path, *, repo_root: Path, label: str) -> dict[str, Any]:
    raw = _read_regular(path, label)
    return {
        "path": path.relative_to(repo_root).as_posix(),
        "bytes": len(raw),
        "sha256": _sha256_bytes(raw),
    }


def _source_ledger(lock: Mapping[str, Any], *, repo_root: Path) -> dict[str, Any]:
    return {
        "policy_lock": _receipt_for(
            repo_root / LOCK_PATH.name, repo_root=repo_root, label="policy lock"
        ),
        "sources": copy.deepcopy(lock["sources"]),
        "fixtures": copy.deepcopy(lock["fixtures"]),
        "predecessor": copy.deepcopy(lock["predecessor"]),
    }


def _flatten_boolean_leaves(value: Any, path: str = "") -> dict[str, bool]:
    leaves: dict[str, bool] = {}
    if type(value) is bool:
        leaves[path] = value
    elif isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            leaves.update(_flatten_boolean_leaves(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_path = f"{path}[{index}]"
            leaves.update(_flatten_boolean_leaves(child, child_path))
    return leaves


def _promotion_state(
    hard_gate_audit: Mapping[str, Any],
) -> tuple[bool, str, Mapping[str, Any], Mapping[str, Any]]:
    gates = _exact_mapping(
        hard_gate_audit.get("top_level_gates"),
        "hard_gate_audit.top_level_gates",
        set(TOP_LEVEL_GATE_IDS),
    )
    for gate_id, result in gates.items():
        _boolean(result, f"hard_gate_audit.top_level_gates.{gate_id}")
    subchecks = hard_gate_audit.get("subchecks")
    _require(isinstance(subchecks, Mapping), "hard gate subchecks missing")
    leaves = _flatten_boolean_leaves(subchecks)
    _require(bool(leaves), "hard gate subchecks have no boolean leaves")
    for required_id in REQUIRED_SUBCHECK_IDS:
        matches = [path for path in leaves if path.split(".")[-1] == required_id]
        _require(matches, f"required subcheck missing: {required_id}")
        _require(all(leaves[path] for path in matches), f"subcheck failed: {required_id}")
    expected_ready = all(gates.values()) and all(leaves.values())
    ready = _boolean(hard_gate_audit.get("promotion_ready"), "promotion_ready")
    _require(ready is expected_ready, "promotion is not exact conjunction")
    status = PROMOTION_STATUS if ready else STOP_STATUS
    _require(hard_gate_audit.get("decision_status") == status, "decision status drift")
    return ready, status, gates, subchecks


def _validate_payload_contract(
    payloads: Any, *, exact_rederive: bool = False
) -> dict[str, Any]:
    values = dict(_exact_mapping(payloads, "payloads", set(CORE_PAYLOAD_KEYS)))
    benchmark.validate_artifact_payloads(values, exact_rederive=exact_rederive)
    for name, payload in values.items():
        _require(isinstance(payload, Mapping), f"payload {name}: expected object")
        _reject_runtime_metadata(payload, f"payload.{name}")
        _require(payload.get("network_calls") == 0, f"{name}: network calls drift")
        _require(payload.get("provider_calls") == 0, f"{name}: provider calls drift")
    schema_by_payload = {
        "shared_evidence_ledger": EXPECTED_SCHEMAS["shared_evidence_ledger"],
        "sealed_bundle": EXPECTED_SCHEMAS["sealed_bundle"],
        "merge_contract": EXPECTED_SCHEMAS["merge_contract"],
        "bundle_control_map": EXPECTED_SCHEMAS["bundle_control_map"],
        "block_adjoint_audit": EXPECTED_SCHEMAS["block_adjoint_audit"],
        "hard_gate_audit": EXPECTED_SCHEMAS["hard_gate_audit"],
        "self_test": EXPECTED_SCHEMAS["self_test"],
    }
    for name, schema in schema_by_payload.items():
        _require(payloads[name].get("schema_version") == schema, f"{name}: schema drift")
    ready, status, gates, subchecks = _promotion_state(values["hard_gate_audit"])
    self_test = values["self_test"]
    _require(self_test.get("status") == "PASS", "self-test not PASS")
    _require(self_test.get("promotion_ready") is ready, "self-test promotion drift")
    _require(self_test.get("decision_status") == status, "self-test decision drift")
    _require_exact_json(self_test.get("top_level_gates"), dict(gates), "self-test gates")
    _require_exact_json(self_test.get("subchecks"), subchecks, "self-test subchecks")
    bundle = values["sealed_bundle"]
    _require_exact_json(
        bundle.get("lane_ids"),
        ["correction_early", "correction_late", "stable_constraint"],
        "sealed bundle lanes",
    )
    _require(bundle.get("junction_count") == 1, "sealed bundle junction drift")
    lane_receipts = _exact_mapping(
        bundle.get("sealed_lane_receipts"),
        "sealed_bundle.sealed_lane_receipts",
        set(PREDECESSOR_LANES),
    )
    for lane_id, expected in PREDECESSOR_LANES.items():
        receipt = _exact_mapping(
            lane_receipts[lane_id],
            f"sealed_bundle.sealed_lane_receipts.{lane_id}",
            {"bytes", "sealed_lane_fingerprint_sha256", "sha256", "source_path"},
        )
        _require(
            receipt["sha256"] == expected["sha256"]
            and receipt["bytes"] == expected["bytes"]
            and receipt["source_path"] == expected["source_path"],
            f"sealed lane receipt drift: {lane_id}",
        )
        _sha256_string(
            receipt["sealed_lane_fingerprint_sha256"],
            f"sealed lane fingerprint: {lane_id}",
        )
    return values


def _adapter_build_payloads(
    composition_fixture_path: Path, one_lane_fixture_path: Path
) -> dict[str, Any]:
    """The only builder/core glue; keep artifact and receipt logic outside it."""

    return benchmark.build_artifact_payloads(
        composition_fixture_path, one_lane_fixture_path
    )


def _core_materialize(lock: Mapping[str, Any], *, repo_root: Path) -> dict[str, Any]:
    composition = _safe_repo_path(
        repo_root, lock["fixtures"]["composition"]["path"], "composition fixture"
    )
    one_lane = _safe_repo_path(
        repo_root, lock["fixtures"]["one_lane"]["path"], "one-lane fixture"
    )
    with _network_guard():
        payloads = _adapter_build_payloads(composition, one_lane)
    # This is the single trusted semantic rederivation for a materialization.
    # Later in-memory and staging validators compare canonical bytes against
    # this already rederived surface without recursively rebuilding the core.
    return _validate_payload_contract(payloads, exact_rederive=True)


def _lane_source_bytes(lock: Mapping[str, Any], *, repo_root: Path) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for lane_id, receipt in lock["predecessor"]["lane_receipts"].items():
        raw = _read_regular(
            _safe_repo_path(
                repo_root, receipt["source_path"], f"lane source {lane_id}"
            ),
            f"lane source {lane_id}",
        )
        _require(len(raw) == receipt["bytes"], f"lane bytes drift: {lane_id}")
        _require(_sha256_bytes(raw) == receipt["sha256"], f"lane hash drift: {lane_id}")
        parsed = _load_json_bytes(raw, f"lane source {lane_id}")
        _require(
            parsed.get("schema_version") == EXPECTED_SCHEMAS["sealed_lane"],
            f"lane schema drift: {lane_id}",
        )
        _require(parsed.get("lane_id") == lane_id, f"lane identity drift: {lane_id}")
        result[receipt["artifact_path"]] = raw
    _require(set(result) == set(SEALED_LANE_FILES), "sealed lane file set drift")
    return result


def _mechanism_report(lock: Mapping[str, Any], payloads: Mapping[str, Any]) -> bytes:
    ready, status, gates, subchecks = _promotion_state(payloads["hard_gate_audit"])
    lines = [
        "# EBRT v0.5.5 lane-composable public trajectory report",
        "",
        f"Status: **{status}**",
        "",
        "## Locked question",
        "",
        "Can three byte-sealed public trajectories share one evidence ledger and one "
        "typed merge junction while preserving source provenance, disconnected-lane "
        "isolation, exact block credit, and deterministic network-zero execution?",
        "",
        "## Frozen v0.5.4 source",
        "",
        f"- commit: `{PREDECESSOR_COMMIT_SHA}`",
        f"- manifest: `{PREDECESSOR_MANIFEST_SHA256}`",
    ]
    for lane_id in ("correction_early", "correction_late", "stable_constraint"):
        lines.append(f"- {lane_id}: `{PREDECESSOR_LANES[lane_id]['sha256']}`")
    lines.extend(
        [
            "- provider calls: `0`",
            "- network calls: `0`",
            "",
            "## Promotion gates",
            "",
            "| Gate | Result |",
            "| --- | --- |",
        ]
    )
    for gate_id in TOP_LEVEL_GATE_IDS:
        lines.append(f"| `{gate_id}` | `{'PASS' if gates[gate_id] else 'FAIL'}` |")
    leaves = _flatten_boolean_leaves(subchecks)
    lines.extend(["", f"Boolean subchecks: **{sum(leaves.values())}/{len(leaves)} PASS**", ""])
    lines.extend(["## Decision", ""])
    if ready:
        lines.extend([f"> {PROMOTION_CLAIM}", ""])
    else:
        lines.extend([f"> `{STOP_STATUS}`: promotion claim not established.", ""])
    lines.extend(["## Claim boundary", ""])
    lines.extend(f"- {row}" for row in lock["claim_boundary"])
    lines.extend(
        [
            "",
            "This result contains no SOL, agent spawning, model routing, provider "
            "execution, tool use, memory, generated answer, or final-output claim.",
            "",
        ]
    )
    return "\n".join(lines).encode("utf-8")


def _manifest(
    lock: Mapping[str, Any],
    artifacts_without_manifest: Mapping[str, bytes],
    payloads: Mapping[str, Any],
    *,
    repo_root: Path,
) -> dict[str, Any]:
    ready, status, gates, subchecks = _promotion_state(payloads["hard_gate_audit"])
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "status": BUNDLE_STATUS,
        "decision_status": status,
        "promotion_ready": ready,
        "top_level_gates": dict(gates),
        "subchecks": copy.deepcopy(subchecks),
        "source_ledger": _source_ledger(lock, repo_root=repo_root),
        "artifacts": {
            filename: {
                "bytes": len(artifacts_without_manifest[filename]),
                "sha256": _sha256_bytes(artifacts_without_manifest[filename]),
            }
            for filename in ARTIFACT_FILES
        },
        "artifact_directory": ARTIFACT_DIRECTORY,
        "network_calls": 0,
        "provider_calls": 0,
        "runtime_contract": lock["artifact"]["runtime_contract"],
        "validator_host_used_as_gate": False,
        "claim_boundary": list(lock["claim_boundary"]),
    }


def _materialize(
    lock: Mapping[str, Any], *, repo_root: Path = ROOT
) -> dict[str, bytes]:
    payloads = _core_materialize(lock, repo_root=repo_root)
    artifacts: dict[str, bytes] = {
        PAYLOAD_TO_FILENAME[name]: _pretty_json_bytes(payloads[name])
        for name in CORE_PAYLOAD_KEYS
    }
    artifacts.update(_lane_source_bytes(lock, repo_root=repo_root))
    artifacts["mechanism_report.md"] = _mechanism_report(lock, payloads)
    _require(set(artifacts) == set(ARTIFACT_FILES), "non-manifest file set drift")
    manifest = _manifest(lock, artifacts, payloads, repo_root=repo_root)
    _reject_runtime_metadata(manifest, "manifest")
    artifacts[MANIFEST_FILENAME] = _pretty_json_bytes(manifest)
    return artifacts


def _read_bundle(directory: Path) -> dict[str, bytes]:
    try:
        root_stat = directory.lstat()
    except OSError as error:
        raise ArtifactValidationError(f"artifact directory missing: {directory}") from error
    _require(stat.S_ISDIR(root_stat.st_mode), "artifact root must be directory")
    _require(not directory.is_symlink(), "artifact root symlink forbidden")
    entries = sorted(directory.rglob("*"), key=lambda item: item.as_posix())
    relative_files: list[str] = []
    directories: list[str] = []
    for entry in entries:
        relative = entry.relative_to(directory).as_posix()
        _require(not entry.is_symlink(), f"artifact symlink forbidden: {relative}")
        mode = entry.lstat().st_mode
        if stat.S_ISDIR(mode):
            directories.append(relative)
        elif stat.S_ISREG(mode):
            relative_files.append(relative)
        else:
            raise ArtifactValidationError(f"artifact entry type forbidden: {relative}")
    _require(directories == ["sealed_lanes"], "artifact directory set mismatch")
    _require(sorted(relative_files) == sorted(ALL_ARTIFACT_FILES), "artifact file set mismatch")
    return {
        filename: _read_regular(directory / filename, f"artifact {filename}")
        for filename in ALL_ARTIFACT_FILES
    }


def _bundle_payloads(bundle: Mapping[str, bytes]) -> dict[str, Any]:
    return {
        name: _load_json_bytes(bundle[PAYLOAD_TO_FILENAME[name]], PAYLOAD_TO_FILENAME[name])
        for name in CORE_PAYLOAD_KEYS
    }


def _validate_bundle_bytes(
    bundle: Mapping[str, bytes],
    lock: Mapping[str, Any],
    *,
    repo_root: Path = ROOT,
) -> None:
    _require(set(bundle) == set(ALL_ARTIFACT_FILES), "bundle key set mismatch")
    payloads = _validate_payload_contract(
        _bundle_payloads(bundle), exact_rederive=False
    )
    for name, filename in PAYLOAD_TO_FILENAME.items():
        _require(
            bundle[filename] == _pretty_json_bytes(payloads[name]),
            f"non-canonical JSON bytes: {filename}",
        )
    source_lanes = _lane_source_bytes(lock, repo_root=repo_root)
    for filename, expected in source_lanes.items():
        _require(bundle[filename] == expected, f"sealed lane copy differs: {filename}")
    expected_report = _mechanism_report(lock, payloads)
    _require(bundle["mechanism_report.md"] == expected_report, "report derivation drift")
    report = bundle["mechanism_report.md"].decode("utf-8")
    for row in lock["claim_boundary"]:
        _require(row in report, "report omitted locked claim boundary")
    manifest = _load_json_bytes(bundle[MANIFEST_FILENAME], "manifest")
    _require(isinstance(manifest, Mapping), "manifest root invalid")
    _require(
        bundle[MANIFEST_FILENAME] == _pretty_json_bytes(manifest),
        "non-canonical JSON bytes: manifest.json",
    )
    artifact_records = _exact_mapping(
        manifest.get("artifacts"), "manifest.artifacts", set(ARTIFACT_FILES)
    )
    for filename in ARTIFACT_FILES:
        record = _exact_mapping(
            artifact_records[filename],
            f"manifest.artifacts.{filename}",
            {"bytes", "sha256"},
        )
        _require(record["bytes"] == len(bundle[filename]), f"size mismatch: {filename}")
        _require(
            record["sha256"] == _sha256_bytes(bundle[filename]),
            f"hash mismatch: {filename}",
        )
    expected_manifest = _manifest(
        lock,
        {filename: bundle[filename] for filename in ARTIFACT_FILES},
        payloads,
        repo_root=repo_root,
    )
    _require_exact_json(manifest, expected_manifest, "manifest derivation")
    _reject_runtime_metadata(manifest, "manifest")


def _write_fsynced(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _require(not path.parent.is_symlink(), f"artifact parent symlink forbidden: {path.parent}")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            path.unlink()
        raise


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _publish_bundle(
    target: Path,
    artifacts: Mapping[str, bytes],
    *,
    lock: Mapping[str, Any],
    repo_root: Path = ROOT,
    inject_fault_after_backup: bool = False,
) -> None:
    _validate_bundle_bytes(artifacts, lock, repo_root=repo_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    _require(not target.parent.is_symlink(), "artifact parent symlink forbidden")
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.staging-", dir=target.parent))
    backup: Optional[Path] = None
    try:
        for filename in ALL_ARTIFACT_FILES:
            _write_fsynced(staging / filename, artifacts[filename])
        _fsync_directory(staging / "sealed_lanes")
        _fsync_directory(staging)
        _validate_bundle_bytes(_read_bundle(staging), lock, repo_root=repo_root)
        if target.exists():
            _require(target.is_dir() and not target.is_symlink(), "target invalid")
            backup = Path(tempfile.mkdtemp(prefix=f".{target.name}.backup-", dir=target.parent))
            backup.rmdir()
            os.replace(target, backup)
        if inject_fault_after_backup:
            raise ArtifactValidationError("injected publication fault")
        try:
            os.replace(staging, target)
            _fsync_directory(target.parent)
        except BaseException:
            if backup is not None and backup.exists() and not target.exists():
                os.replace(backup, target)
                backup = None
                _fsync_directory(target.parent)
            raise
        if backup is not None:
            shutil.rmtree(backup)
            backup = None
    finally:
        if staging.exists():
            shutil.rmtree(staging)
        if backup is not None and backup.exists():
            if not target.exists():
                os.replace(backup, target)
                _fsync_directory(target.parent)
            else:
                shutil.rmtree(backup)


def _artifact_directory(lock: Mapping[str, Any], *, repo_root: Path = ROOT) -> Path:
    return _safe_repo_path(repo_root, lock["artifact"]["directory"], "artifact directory")


def build() -> dict[str, str]:
    lock = _load_lock()
    with _network_guard():
        artifacts = _materialize(lock)
    _validate_bundle_bytes(artifacts, lock)
    target = _artifact_directory(lock)
    _publish_bundle(target, artifacts, lock=lock)
    observed = _read_bundle(target)
    _validate_bundle_bytes(observed, lock)
    mismatches = [
        name for name in ALL_ARTIFACT_FILES if observed[name] != artifacts[name]
    ]
    _require(not mismatches, f"published artifact differs: {mismatches}")
    return {filename: _sha256_bytes(artifacts[filename]) for filename in ALL_ARTIFACT_FILES}


def validate(artifact_dir: Optional[Path] = None) -> None:
    lock = _load_lock()
    with _network_guard():
        expected = _materialize(lock)
    _validate_bundle_bytes(expected, lock)
    observed = _read_bundle(artifact_dir or _artifact_directory(lock))
    _validate_bundle_bytes(observed, lock)
    mismatches = [name for name in ALL_ARTIFACT_FILES if observed[name] != expected[name]]
    _require(not mismatches, f"artifact not canonical reconstruction: {mismatches}")


def _expect_rejection(label: str, action: Callable[[], Any]) -> None:
    try:
        action()
    except (
        ArtifactValidationError,
        core.LaneCompositionValidationError,
        ValueError,
        AssertionError,
    ):
        return
    raise AssertionError(f"tamper unexpectedly passed: {label}")


def self_test() -> dict[str, Any]:
    lock = _load_lock()
    with _network_guard():
        first = _materialize(lock)
        second = _materialize(lock)
    _require(first == second, "two builds differ")
    _validate_bundle_bytes(first, lock)
    _expect_rejection(
        "duplicate JSON",
        lambda: _load_json_bytes(b'{"x":1,"x":2}', "duplicate probe"),
    )
    _expect_rejection(
        "non-finite JSON",
        lambda: _load_json_bytes(b'{"x":NaN}', "nonfinite probe"),
    )
    unknown = copy.deepcopy(lock)
    unknown["debug"] = True
    _expect_rejection(
        "unknown lock key",
        lambda: _validate_lock_mapping(unknown, validate_sources=False),
    )
    source_tamper = copy.deepcopy(lock)
    source_tamper["sources"]["core"]["sha256"] = "0" * 64
    _expect_rejection("source tamper", lambda: _validate_lock_mapping(source_tamper))
    fixture_tamper = copy.deepcopy(lock)
    fixture_tamper["fixtures"]["composition"]["sha256"] = "0" * 64
    _expect_rejection("fixture tamper", lambda: _validate_lock_mapping(fixture_tamper))
    predecessor_tamper = copy.deepcopy(lock)
    predecessor_tamper["predecessor"]["lane_receipts"]["correction_early"][
        "sha256"
    ] = "0" * 64
    _expect_rejection(
        "predecessor lane tamper",
        lambda: _validate_lock_mapping(predecessor_tamper, validate_sources=False),
    )
    payload_tamper = dict(first)
    gate = _load_json_bytes(payload_tamper["hard_gate_audit.json"], "gate tamper")
    first_gate = TOP_LEVEL_GATE_IDS[0]
    gate["top_level_gates"][first_gate] = False
    payload_tamper["hard_gate_audit.json"] = _pretty_json_bytes(gate)
    _expect_rejection(
        "semantic artifact tamper",
        lambda: _validate_bundle_bytes(payload_tamper, lock),
    )
    reformat_tamper = dict(first)
    reformatted = reformat_tamper["merge_contract.json"].rstrip(b"\n") + b"  \n"
    reformat_tamper["merge_contract.json"] = reformatted
    reformat_manifest = _load_json_bytes(
        reformat_tamper[MANIFEST_FILENAME], "reformat manifest"
    )
    reformat_manifest["artifacts"]["merge_contract.json"] = {
        "bytes": len(reformatted),
        "sha256": _sha256_bytes(reformatted),
    }
    reformat_tamper[MANIFEST_FILENAME] = _pretty_json_bytes(reformat_manifest)
    _expect_rejection(
        "coherently resigned JSON reformat",
        lambda: _validate_bundle_bytes(reformat_tamper, lock),
    )
    lane_tamper = dict(first)
    lane_tamper["sealed_lanes/correction_early.json"] += b" "
    lane_manifest = _load_json_bytes(lane_tamper[MANIFEST_FILENAME], "manifest")
    lane_manifest["artifacts"]["sealed_lanes/correction_early.json"] = {
        "bytes": len(lane_tamper["sealed_lanes/correction_early.json"]),
        "sha256": _sha256_bytes(lane_tamper["sealed_lanes/correction_early.json"]),
    }
    lane_tamper[MANIFEST_FILENAME] = _pretty_json_bytes(lane_manifest)
    _expect_rejection(
        "coherently resigned lane tamper",
        lambda: _validate_bundle_bytes(lane_tamper, lock),
    )
    report_tamper = dict(first)
    report_tamper["mechanism_report.md"] += b"tampered\n"
    report_manifest = _load_json_bytes(report_tamper[MANIFEST_FILENAME], "manifest")
    report_manifest["artifacts"]["mechanism_report.md"] = {
        "bytes": len(report_tamper["mechanism_report.md"]),
        "sha256": _sha256_bytes(report_tamper["mechanism_report.md"]),
    }
    report_tamper[MANIFEST_FILENAME] = _pretty_json_bytes(report_manifest)
    _expect_rejection(
        "coherently resigned report tamper",
        lambda: _validate_bundle_bytes(report_tamper, lock),
    )
    ledger_tamper = dict(first)
    ledger_manifest = _load_json_bytes(ledger_tamper[MANIFEST_FILENAME], "manifest")
    ledger_manifest["source_ledger"]["fixtures"]["composition"]["sha256"] = "0" * 64
    ledger_tamper[MANIFEST_FILENAME] = _pretty_json_bytes(ledger_manifest)
    _expect_rejection(
        "coherently resigned source-ledger tamper",
        lambda: _validate_bundle_bytes(ledger_tamper, lock),
    )
    extra = dict(first)
    extra["debug.json"] = b"{}\n"
    _expect_rejection("extra artifact", lambda: _validate_bundle_bytes(extra, lock))

    with tempfile.TemporaryDirectory(prefix="ebrt-v055-bundle-audit-") as raw:
        temporary = Path(raw)
        target = temporary / "bundle"
        _publish_bundle(target, first, lock=lock)
        before = _read_bundle(target)
        _expect_rejection(
            "publication fault",
            lambda: _publish_bundle(
                target,
                first,
                lock=lock,
                inject_fault_after_backup=True,
            ),
        )
        _require(_read_bundle(target) == before, "publication rollback failed")
        _require(
            not tuple(temporary.glob(".bundle.staging-*"))
            and not tuple(temporary.glob(".bundle.backup-*")),
            "publication rollback left state",
        )
        (target / "unexpected.json").write_text("{}\n", encoding="utf-8")
        _expect_rejection("extra file", lambda: _read_bundle(target))
        (target / "unexpected.json").unlink()
        missing = target / "merge_contract.json"
        missing_bytes = missing.read_bytes()
        missing.unlink()
        _expect_rejection("missing file", lambda: _read_bundle(target))
        missing.write_bytes(missing_bytes)
        lane_path = target / "sealed_lanes" / "correction_early.json"
        lane_bytes = lane_path.read_bytes()
        lane_path.unlink()
        lane_path.symlink_to(target / "sealed_lanes" / "correction_late.json")
        _expect_rejection("symlink lane", lambda: _read_bundle(target))
        lane_path.unlink()
        lane_path.write_bytes(lane_bytes)

    payloads = _bundle_payloads(first)
    ready, status, gates, subchecks = _promotion_state(payloads["hard_gate_audit"])
    return {
        "status": "PASS",
        "self_test": "sealed_network_zero_lane_composition_bundle",
        "checks": {
            "byte_identical_v0_5_4_lane_copies": True,
            "coherent_resign_tampering_rejected": True,
            "extra_missing_and_symlink_rejected": True,
            "portable_source_receipts_verified": True,
            "publication_fault_rollback_verified": True,
            "socket_creation_denied": True,
            "strict_json_duplicate_nonfinite_rejected": True,
            "two_build_byte_identity": True,
        },
        "top_level_gates": dict(gates),
        "subchecks": copy.deepcopy(subchecks),
        "promotion_ready": ready,
        "decision_status": status,
        "artifact_sha256": {
            filename: _sha256_bytes(first[filename]) for filename in ALL_ARTIFACT_FILES
        },
        "network_calls": 0,
        "provider_calls": 0,
        "claim_boundary": "Contaminated public lane-composition mechanism only.",
    }


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build")
    validate_parser = sub.add_parser("validate")
    validate_parser.add_argument("--artifact-dir", type=Path, default=None)
    sub.add_parser("self-test")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "build":
            _print_json({"status": "BUILT", "artifact_sha256": build()})
        elif args.command == "validate":
            validate(args.artifact_dir)
            _print_json(
                {
                    "status": "VALID_CANONICAL_NETWORK_ZERO_ARTIFACT",
                    "validator_host_used_as_gate": False,
                }
            )
        else:
            _print_json(self_test())
    except (ArtifactValidationError, core.LaneCompositionValidationError) as error:
        raise SystemExit(f"validation failed: {error}") from error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
