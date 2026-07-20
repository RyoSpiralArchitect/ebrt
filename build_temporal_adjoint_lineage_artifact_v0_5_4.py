#!/usr/bin/env python3
"""Build the sealed, network-zero EBRT v0.5.4 temporal-lineage bundle.

The builder binds a mechanically compiled temporal recurrence to the committed
v0.5.3 factorized-lineage checkpoint.  It verifies every source byte and public
fingerprint before asking the v0.5.4 benchmark module for deterministic public
payloads.  No provider, semantic adapter, generated answer, or hidden model
state participates.

Canonical artifact bytes deliberately exclude timestamps, hostnames, absolute
paths, and observed runtime metadata.  The committed bundle is a contaminated
mechanism result over one frozen public dependency program.
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

import benchmark_temporal_adjoint_lineage_v0_5_4 as benchmark
import temporal_adjoint_lineage_v0_5_4 as core


ROOT = Path(__file__).resolve().parent
BUILDER_PATH = Path(__file__).resolve()
LOCK_PATH = ROOT / "policy_lock_temporal_adjoint_lineage_v0_5_4.json"

LOCK_SCHEMA_VERSION = "ebrt-temporal-adjoint-lineage-policy-lock-v0.5.4"
LOCK_STATUS = "LOCKED_CONTAMINATED_NETWORK_ZERO_TEMPORAL_GATE"
SOURCE_RECEIPT_SCHEMA_VERSION = "ebrt-temporal-lineage-source-receipt-v0.5.4"
COMPILED_PROGRAMS_SCHEMA_VERSION = "ebrt-temporal-lineage-suite-v0.5.4"
ACTUATOR_GEOMETRY_SCHEMA_VERSION = (
    "ebrt-temporal-lineage-actuator-geometry-v0.5.4"
)
SELF_TEST_SCHEMA_VERSION = "ebrt-temporal-lineage-bundle-self-test-v0.5.4"
MANIFEST_SCHEMA_VERSION = "ebrt-temporal-lineage-manifest-v0.5.4"
BUNDLE_STATUS = "COMPLETE_CONTAMINATED_NETWORK_ZERO_TEMPORAL_GATE"
PROMOTION_STATUS = "PROMOTE_V0_5_5_TEMPORAL_GATE"
STOP_STATUS = "STOP_V0_5_5_TEMPORAL_GATE"
PROMOTION_CLAIM = (
    "On one frozen public dependency program, normalized exact temporal credit "
    "selected a finite intervention placement that beat its node-tied projection "
    "and every locked timing permutation."
)

ARTIFACT_DIRECTORY = "artifacts/temporal_adjoint_lineage_v0_5_4"
ARTIFACT_FILES = (
    "source_receipt.json",
    "compiled_programs.json",
    "actuator_geometry.json",
    "arm_comparison.json",
    "correction_early_sealed_lane.json",
    "correction_late_sealed_lane.json",
    "stable_constraint_sealed_lane.json",
    "no_event_audit.json",
    "self_test.json",
    "mechanism_report.md",
)
MANIFEST_FILENAME = "manifest.json"
ALL_ARTIFACT_FILES = (*ARTIFACT_FILES, MANIFEST_FILENAME)

CORE_PAYLOAD_KEYS = (
    "compiled_programs",
    "actuator_geometry",
    "arm_comparison",
    "correction_early_sealed_lane",
    "correction_late_sealed_lane",
    "stable_constraint_sealed_lane",
    "no_event_audit",
    "self_test",
)
PAYLOAD_TO_FILENAME = {
    "compiled_programs": "compiled_programs.json",
    "actuator_geometry": "actuator_geometry.json",
    "arm_comparison": "arm_comparison.json",
    "correction_early_sealed_lane": "correction_early_sealed_lane.json",
    "correction_late_sealed_lane": "correction_late_sealed_lane.json",
    "stable_constraint_sealed_lane": "stable_constraint_sealed_lane.json",
    "no_event_audit": "no_event_audit.json",
    "self_test": "self_test.json",
}

EVENT_FIXTURE_PATH = "fixtures/temporal_adjoint_lineage_v0_5_4_dev.json"
NO_EVENT_FIXTURE_PATH = "fixtures/temporal_adjoint_lineage_v0_5_4_no_event.json"
CORE_SOURCE_PATH = "temporal_adjoint_lineage_v0_5_4.py"
BENCHMARK_SOURCE_PATH = "benchmark_temporal_adjoint_lineage_v0_5_4.py"
BUILDER_SOURCE_PATH = "build_temporal_adjoint_lineage_artifact_v0_5_4.py"

PREDECESSOR_COMMIT_SHA = "c671e149fcbe05217820512a3f90c847cbbcfbf2"
PREDECESSOR_TREE_SHA = "f87266eb14200074ccd95c3feee1bfe170f14df3"
PREDECESSOR_SOURCE_RECEIPTS = {
    "builder": {
        "path": "build_factorized_lineage_artifact_v0_5_3.py",
        "bytes": 55087,
        "sha256": "db9061e20333d6ef1863521cd6d65b99ed521341589bf0230acd48e036a6a9e2",
    },
    "closure_gold": {
        "path": "fixtures/factorized_lineage_v0_5_3_closure_gold.json",
        "bytes": 1981,
        "sha256": "0e30dfe19b926990fd8eac77c781f4ac2087a81da11b74e0f25becf3ffa7447b",
    },
    "core": {
        "path": "factorized_lineage_v0_5_3.py",
        "bytes": 100732,
        "sha256": "d7ad2344a0c37b502feac663e17bb918be1fe50b4d9c94898e18ee757c4cb35b",
    },
    "policy_lock": {
        "path": "policy_lock_factorized_lineage_v0_5_3.json",
        "bytes": 6112,
        "sha256": "145d8f40d7721e49b2bdb7f317c7208d244d3b70f5df057d10ff3bc5b3e1bf39",
    },
    "repair_overlay": {
        "path": "fixtures/factorized_lineage_v0_5_3_repair_overlay.json",
        "bytes": 1306,
        "sha256": "9425bda87e5aa859ec6c8016035c599a0d1f3d8704ec7d012ddf44e6ca05e22e",
    },
}
PREDECESSOR_ARTIFACT_RECEIPTS = {
    "factorized_lineage_regression.json": {
        "path": "artifacts/factorized_lineage_v0_5_3/factorized_lineage_regression.json",
        "bytes": 43579,
        "sha256": "85094e65b9181b893b80bf42c3db859b66a66320a080defefc514ce75fbe910f",
    },
    "lossless_migration.json": {
        "path": "artifacts/factorized_lineage_v0_5_3/lossless_migration.json",
        "bytes": 19072,
        "sha256": "41b19e6210aa387a54b6db24256b1eb1943f685bb4acb226ac8ed0415e50b38a",
    },
    "manifest.json": {
        "path": "artifacts/factorized_lineage_v0_5_3/manifest.json",
        "bytes": 5668,
        "sha256": "50f33ac2029d66210b7b00b7719df09c9cd8c5bbe05b34aadfddb5929adb57e7",
    },
    "mechanism_report.md": {
        "path": "artifacts/factorized_lineage_v0_5_3/mechanism_report.md",
        "bytes": 2488,
        "sha256": "f70d9c06a47451467e62309535c1d163ecabc8e1e71f58bd943fb1f416a3541e",
    },
    "self_test.json": {
        "path": "artifacts/factorized_lineage_v0_5_3/self_test.json",
        "bytes": 4995,
        "sha256": "77948a2b73348bf983999a80498ce2839dcce227418addb9c08b4797dd8efdd9",
    },
}
PREDECESSOR_FINGERPRINTS = {
    "observed_graph_sha256": "8afb3d03084dc33f92ea6d12dbe7c3cfdb53f4642a5d6a937075a53dcb9a74ca",
    "repaired_graph_sha256": "361d6961938dda2d69ccc0340fecb802c55af40d6cd551c628eb307462416333",
    "repaired_closure_sha256": "899afdca968e3a3e1c1dd7f9eb5c4605e18c7c6b4188a8a4f4af1707a2859c9c",
    "repaired_grade_sha256": "2cf9e0d55ec892c187d7763507931c661ef1358578176e3b051cdff8b170d103",
    "regression_sha256": "0335ede60f428ddf77f7266d1c2bea6483c4698e924f555e9be8a7d3422e2997",
}

HARD_GATE_IDS = (
    "v053_source_exact",
    "compiled_closure_exact",
    "fixture_mechanism_injection_rejected",
    "forward_sensitivity_agreement",
    "reverse_adjoint_agreement",
    "central_finite_difference_agreement",
    "normalized_jacobian_geometry",
    "severed_path_zero_credit",
    "independent_operator_permutation_invariant",
    "identity_insertion_invariant",
    "early_late_top_credit_switch",
    "no_event_exact_identity",
    "matched_control_geometry",
    "exact_credit_beats_zero_and_node_tied",
    "exact_credit_beats_all_timing_shams",
    "two_build_byte_identity",
    "socket_denied_network_zero",
)

EXPECTED_CANONICALIZATION = {
    "allow_nan": False,
    "encoding": "utf-8",
    "ensure_ascii": False,
    "separators": [",", ":"],
    "sort_keys": True,
    "trailing_newline": True,
}
EXPECTED_SCHEMAS = {
    "actuator_geometry": ACTUATOR_GEOMETRY_SCHEMA_VERSION,
    "adjoint_audit": "ebrt-temporal-lineage-adjoint-audit-v0.5.4",
    "bundle_self_test": SELF_TEST_SCHEMA_VERSION,
    "compiled_program": "ebrt-compiled-temporal-lineage-program-v0.5.4",
    "compiled_programs": COMPILED_PROGRAMS_SCHEMA_VERSION,
    "comparison": "ebrt-temporal-lineage-comparison-v0.5.4",
    "control_map": "ebrt-temporal-lineage-control-map-v0.5.4",
    "event_fixture": "ebrt-temporal-adjoint-lineage-fixture-v0.5.4",
    "manifest": MANIFEST_SCHEMA_VERSION,
    "no_event_fixture": "ebrt-temporal-adjoint-lineage-no-event-fixture-v0.5.4",
    "sealed_lane": "ebrt-sealed-temporal-lineage-lane-v0.5.4",
    "source_receipt": SOURCE_RECEIPT_SCHEMA_VERSION,
}
EXPECTED_EXPERIMENT_CONTRACT = {
    "contaminated": True,
    "event_schedule_ids": ["correction_early", "correction_late"],
    "hard_gate_ids": list(HARD_GATE_IDS),
    "network_calls": 0,
    "promotion_claim": PROMOTION_CLAIM,
    "promotion_status": PROMOTION_STATUS,
    "provider_calls": 0,
    "stable_lane_id": "stable_constraint",
    "state_axis_order": ["channel", "evidence", "node"],
    "stop_status": STOP_STATUS,
    "terminal_axes": {
        "correction_early": "fact_only",
        "correction_late": "fact_only",
        "stable_constraint": "constraint_only",
    },
}

MAX_FILE_BYTES = 4_000_000
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ArtifactValidationError(RuntimeError):
    """Raised when a lock, source, payload, artifact, or publication is invalid."""


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
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
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
    actual = set(value)
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    _require(
        not missing and not unknown,
        f"{label}: missing={missing or 'none'} unknown={unknown or 'none'}",
    )
    return value


def _string(value: Any, label: str) -> str:
    _require(
        isinstance(value, str) and bool(value) and value == value.strip(),
        f"{label}: expected trimmed non-empty string",
    )
    return value


def _integer(value: Any, label: str, *, minimum: int = 0) -> int:
    _require(
        type(value) is int and value >= minimum,
        f"{label}: expected integer >= {minimum}",
    )
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
    _require(".." not in pure.parts, f"{label}: parent traversal forbidden")
    candidate = repo_root.joinpath(*pure.parts)
    try:
        candidate.resolve().relative_to(repo_root.resolve())
    except ValueError as error:
        raise ArtifactValidationError(f"{label}: path escaped repository root") from error
    return candidate


def _read_regular(path: Path, label: str, *, max_bytes: int = MAX_FILE_BYTES) -> bytes:
    try:
        before = path.lstat()
    except OSError as error:
        raise ArtifactValidationError(f"{label}: cannot stat {path}") from error
    _require(stat.S_ISREG(before.st_mode), f"{label}: expected regular file")
    _require(not path.is_symlink(), f"{label}: symlink forbidden")
    _require(before.st_size <= max_bytes, f"{label}: file exceeds size cap")
    try:
        value = path.read_bytes()
        after = path.lstat()
    except OSError as error:
        raise ArtifactValidationError(f"{label}: cannot read {path}") from error
    _require(
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
        f"{label}: changed while being read",
    )
    _require(len(value) == before.st_size, f"{label}: byte count changed")
    return value


def _read_json_regular(path: Path, label: str) -> tuple[Any, bytes]:
    raw = _read_regular(path, label)
    return _load_json_bytes(raw, label), raw


def _require_exact_json(value: Any, expected: Any, label: str) -> None:
    _require(
        _canonical_json_bytes(value) == _canonical_json_bytes(expected),
        f"{label}: changed from exact locked value",
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
        _require(_sha256_bytes(raw) == digest, f"{label}: SHA-256 mismatch")
    return record


def _validate_predecessor(
    value: Any,
    *,
    repo_root: Path,
    validate_bytes: bool,
) -> dict[str, Any]:
    predecessor = dict(
        _exact_mapping(
            value,
            "lock.predecessor",
            {
                "artifact_receipts",
                "commit_sha",
                "fingerprints",
                "relationship",
                "source_receipts",
                "tree_sha",
            },
        )
    )
    _require(
        predecessor["commit_sha"] == PREDECESSOR_COMMIT_SHA,
        "predecessor commit drift",
    )
    _require(
        predecessor["tree_sha"] == PREDECESSOR_TREE_SHA,
        "predecessor tree drift",
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
        predecessor["fingerprints"],
        PREDECESSOR_FINGERPRINTS,
        "predecessor fingerprints",
    )
    for group_name in ("source_receipts", "artifact_receipts"):
        for name, receipt in predecessor[group_name].items():
            _validate_receipt(
                receipt,
                f"predecessor.{group_name}.{name}",
                repo_root=repo_root,
                validate_bytes=validate_bytes,
            )
    if validate_bytes:
        regression_record = predecessor["artifact_receipts"][
            "factorized_lineage_regression.json"
        ]
        regression_path = _safe_repo_path(
            repo_root, regression_record["path"], "predecessor regression path"
        )
        regression, _raw = _read_json_regular(regression_path, "predecessor regression")
        _require(isinstance(regression, Mapping), "predecessor regression root invalid")
        _require(
            regression.get("fingerprint_sha256")
            == PREDECESSOR_FINGERPRINTS["regression_sha256"],
            "predecessor regression fingerprint mismatch",
        )
        observed = regression.get("observed", {})
        repaired = regression.get("repaired", {})
        _require(
            observed.get("graph", {}).get("fingerprint_sha256")
            == PREDECESSOR_FINGERPRINTS["observed_graph_sha256"],
            "predecessor observed graph fingerprint mismatch",
        )
        _require(
            repaired.get("graph", {}).get("fingerprint_sha256")
            == PREDECESSOR_FINGERPRINTS["repaired_graph_sha256"],
            "predecessor repaired graph fingerprint mismatch",
        )
        _require(
            repaired.get("closure", {}).get("fingerprint_sha256")
            == PREDECESSOR_FINGERPRINTS["repaired_closure_sha256"],
            "predecessor repaired closure fingerprint mismatch",
        )
        _require(
            repaired.get("grade", {}).get("fingerprint_sha256")
            == PREDECESSOR_FINGERPRINTS["repaired_grade_sha256"],
            "predecessor repaired grade fingerprint mismatch",
        )
        _require(regression.get("status") == "PASS", "predecessor regression not PASS")
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
    _require(lock["schema_version"] == LOCK_SCHEMA_VERSION, "lock schema mismatch")
    _require(lock["status"] == LOCK_STATUS, "lock status mismatch")

    sources = _exact_mapping(
        lock["sources"], "lock.sources", {"benchmark", "builder", "core"}
    )
    expected_source_paths = {
        "benchmark": BENCHMARK_SOURCE_PATH,
        "builder": BUILDER_SOURCE_PATH,
        "core": CORE_SOURCE_PATH,
    }
    for name, item in sources.items():
        record = _validate_receipt(
            item,
            f"lock.sources.{name}",
            repo_root=repo_root,
            validate_bytes=validate_sources,
        )
        _require(
            record["path"] == expected_source_paths[name],
            f"source path mismatch: {name}",
        )

    fixtures = _exact_mapping(
        lock["fixtures"], "lock.fixtures", {"event", "no_event"}
    )
    expected_fixture_paths = {
        "event": EVENT_FIXTURE_PATH,
        "no_event": NO_EVENT_FIXTURE_PATH,
    }
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
            f"fixture path mismatch: {name}",
        )
        _exact_mapping(
            item,
            f"lock.fixtures.{name}",
            {"path", "bytes", "sha256", "schema_version", "fixture_id"},
        )
        expected_schema = EXPECTED_SCHEMAS[
            "event_fixture" if name == "event" else "no_event_fixture"
        ]
        _require(item["schema_version"] == expected_schema, f"{name} schema drift")
        _string(item["fixture_id"], f"fixtures.{name}.fixture_id")
        if validate_sources:
            fixture_path = _safe_repo_path(
                repo_root, item["path"], f"fixtures.{name}.path"
            )
            fixture, _raw = _read_json_regular(fixture_path, f"fixture {name}")
            _require(isinstance(fixture, Mapping), f"fixture {name} root invalid")
            _require(
                fixture.get("schema_version") == item["schema_version"]
                and fixture.get("fixture_id") == item["fixture_id"],
                f"fixture identity mismatch: {name}",
            )
            core.validate_fixture(fixture, no_event=name == "no_event")

    _validate_predecessor(
        lock["predecessor"], repo_root=repo_root, validate_bytes=validate_sources
    )
    _require_exact_json(lock["schemas"], EXPECTED_SCHEMAS, "public schemas")
    _require_exact_json(
        lock["experiment_contract"],
        EXPECTED_EXPERIMENT_CONTRACT,
        "experiment contract",
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
        "manifest digest coverage",
    )
    _require(
        _integer(artifact["network_calls"], "artifact.network_calls") == 0,
        "network calls must be zero",
    )
    _require(
        _integer(artifact["provider_calls"], "artifact.provider_calls") == 0,
        "provider calls must be zero",
    )
    _string(artifact["runtime_contract"], "artifact.runtime_contract")

    boundaries = lock["claim_boundary"]
    _require(isinstance(boundaries, list) and bool(boundaries), "claim boundary empty")
    _require(
        all(isinstance(row, str) and row and row == row.strip() for row in boundaries),
        "claim boundary must contain trimmed strings",
    )
    _require(PROMOTION_CLAIM in boundaries, "exact promotion claim not locked")
    return lock


def _load_lock(*, repo_root: Path = ROOT) -> dict[str, Any]:
    path = repo_root / LOCK_PATH.name
    value, _raw = _read_json_regular(path, "policy lock")
    return _validate_lock_mapping(value, repo_root=repo_root)


def _receipt_for(path: Path, *, repo_root: Path, label: str) -> dict[str, Any]:
    raw = _read_regular(path, label)
    return {
        "path": path.relative_to(repo_root).as_posix(),
        "bytes": len(raw),
        "sha256": _sha256_bytes(raw),
    }


def _source_receipt(lock: Mapping[str, Any], *, repo_root: Path) -> dict[str, Any]:
    policy_path = repo_root / LOCK_PATH.name
    return {
        "schema_version": SOURCE_RECEIPT_SCHEMA_VERSION,
        "status": "SEALED",
        "predecessor": copy.deepcopy(lock["predecessor"]),
        "policy_lock": _receipt_for(
            policy_path, repo_root=repo_root, label="policy lock receipt"
        ),
        "sources": copy.deepcopy(lock["sources"]),
        "fixtures": copy.deepcopy(lock["fixtures"]),
        "network_calls": 0,
        "provider_calls": 0,
        "fingerprint_sha256": "",
    }


def _seal_fingerprint(value: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(value))
    _require("fingerprint_sha256" in result, "fingerprint field missing")
    result["fingerprint_sha256"] = ""
    result["fingerprint_sha256"] = _fingerprint(result)
    return result


def _promotion_state(comparison: Mapping[str, Any]) -> tuple[bool, str, Mapping[str, Any]]:
    gates = _exact_mapping(
        comparison.get("hard_gates"), "comparison.hard_gates", set(HARD_GATE_IDS)
    )
    for gate_id, value in gates.items():
        _boolean(value, f"comparison.hard_gates.{gate_id}")
    promotion_ready = _boolean(
        comparison.get("promotion_ready"), "comparison.promotion_ready"
    )
    expected_ready = all(gates[gate_id] for gate_id in HARD_GATE_IDS)
    _require(
        promotion_ready is expected_ready,
        "promotion_ready does not equal conjunction of exact hard gates",
    )
    expected_status = PROMOTION_STATUS if expected_ready else STOP_STATUS
    _require(comparison.get("decision_status") == expected_status, "stop rule drift")
    return expected_ready, expected_status, gates


def _validate_payload_contract(payloads: Any) -> dict[str, Any]:
    values = dict(
        _exact_mapping(payloads, "core payloads", set(CORE_PAYLOAD_KEYS))
    )
    benchmark.validate_artifact_payloads(values)
    for name, value in values.items():
        _require(isinstance(value, Mapping), f"payload {name}: expected object")
        _reject_runtime_metadata(value, f"payload.{name}")
        _require(
            value.get("network_calls") == 0,
            f"payload {name}: network_calls must be zero",
        )
        _require(
            value.get("provider_calls") == 0,
            f"payload {name}: provider_calls must be zero",
        )

    schemas = {
        "compiled_programs": EXPECTED_SCHEMAS["compiled_programs"],
        "actuator_geometry": EXPECTED_SCHEMAS["actuator_geometry"],
        "arm_comparison": EXPECTED_SCHEMAS["comparison"],
        "correction_early_sealed_lane": EXPECTED_SCHEMAS["sealed_lane"],
        "correction_late_sealed_lane": EXPECTED_SCHEMAS["sealed_lane"],
        "stable_constraint_sealed_lane": EXPECTED_SCHEMAS["sealed_lane"],
        "no_event_audit": EXPECTED_SCHEMAS["adjoint_audit"],
        "self_test": EXPECTED_SCHEMAS["bundle_self_test"],
    }
    for name, schema in schemas.items():
        _require(
            values[name].get("schema_version") == schema,
            f"payload {name}: schema mismatch",
        )

    compiled = values["compiled_programs"]
    _require_exact_json(
        compiled.get("state_axis_order"),
        ["channel", "evidence", "node"],
        "compiled state axis order",
    )
    _require(
        compiled.get("source_regression_fingerprint_sha256")
        == PREDECESSOR_FINGERPRINTS["regression_sha256"],
        "compiled program source regression drift",
    )
    _require(
        compiled.get("graph_fingerprint_sha256")
        == PREDECESSOR_FINGERPRINTS["repaired_graph_sha256"],
        "compiled program graph drift",
    )
    _require(
        compiled.get("closure_fingerprint_sha256")
        == PREDECESSOR_FINGERPRINTS["repaired_closure_sha256"],
        "compiled program closure drift",
    )

    early = values["correction_early_sealed_lane"]
    late = values["correction_late_sealed_lane"]
    stable = values["stable_constraint_sealed_lane"]
    _require(early.get("lane_id") == "correction_early", "early lane id drift")
    _require(late.get("lane_id") == "correction_late", "late lane id drift")
    _require(stable.get("lane_id") == "stable_constraint", "stable lane id drift")
    _require_exact_json(early.get("terminal_axis_types"), ["fact"], "early axes")
    _require_exact_json(late.get("terminal_axis_types"), ["fact"], "late axes")
    _require_exact_json(
        stable.get("terminal_axis_types"), ["constraint"], "stable axes"
    )
    _require(stable.get("event_triggered") is False, "stable lane event drift")
    _require(stable.get("backward_calls") == 0, "stable lane backward call drift")
    _require(stable.get("neutral_equals_controlled") is True, "stable lane not identity")
    _require_exact_json(stable.get("control_values"), [], "stable lane controls")

    no_event = values["no_event_audit"]
    _require(no_event.get("event_triggered") is False, "no-event audit drift")
    _require(no_event.get("backward_calls") == 0, "no-event backward call drift")
    _require(no_event.get("exact_identity") is True, "no-event identity failed")
    _require(
        no_event.get("recurrence_zero_delta_exact_zero") is True,
        "no-event recurrence identity failed",
    )

    ready, _status, gates = _promotion_state(values["arm_comparison"])
    self_test = values["self_test"]
    _require(self_test.get("status") == "PASS", "nested self-test not PASS")
    _require_exact_json(
        self_test.get("hard_gates"), dict(gates), "self-test hard gates"
    )
    _require(
        self_test.get("promotion_ready") is ready,
        "self-test promotion state drift",
    )
    return values


def _core_materialize(lock: Mapping[str, Any], *, repo_root: Path) -> dict[str, Any]:
    event_path = _safe_repo_path(
        repo_root, lock["fixtures"]["event"]["path"], "event fixture path"
    )
    no_event_path = _safe_repo_path(
        repo_root,
        lock["fixtures"]["no_event"]["path"],
        "no-event fixture path",
    )
    with _network_guard():
        payloads = benchmark.build_artifact_payloads(event_path, no_event_path)
    return _validate_payload_contract(payloads)


def _mechanism_report(
    lock: Mapping[str, Any], payloads: Mapping[str, Any]
) -> bytes:
    comparison = payloads["arm_comparison"]
    ready, status, gates = _promotion_state(comparison)
    lines = [
        "# EBRT v0.5.4 temporal adjoint lineage mechanism report",
        "",
        f"Status: **{status}**",
        "",
        "## Locked question",
        "",
        "On the frozen v0.5.3 public dependency program, does normalized exact "
        "temporal credit select a finite earlier intervention placement that beats "
        "zero control, the node-tied projection, and every locked timing sham under "
        "matched public actuator geometry?",
        "",
        "## Sealed source",
        "",
        f"- v0.5.3 commit: `{PREDECESSOR_COMMIT_SHA}`",
        f"- repaired graph: `{PREDECESSOR_FINGERPRINTS['repaired_graph_sha256']}`",
        f"- repaired closure: `{PREDECESSOR_FINGERPRINTS['repaired_closure_sha256']}`",
        f"- regression: `{PREDECESSOR_FINGERPRINTS['regression_sha256']}`",
        "- state axis order: `(channel, evidence, node)`",
        "- provider calls: `0`",
        "- network calls: `0`",
        "",
        "## Exact hard gates",
        "",
        "| Gate | Result |",
        "| --- | --- |",
    ]
    for gate_id in HARD_GATE_IDS:
        lines.append(f"| `{gate_id}` | `{'PASS' if gates[gate_id] else 'FAIL'}` |")
    lines.extend(
        [
            "",
            "## Sealed lanes",
            "",
            "- `correction_early`: fact-only terminal axes",
            "- `correction_late`: fact-only terminal axes",
            "- `stable_constraint`: constraint-only no-event identity; zero controls; "
            "`backward_calls=0`; neutral equals controlled",
            "",
            "## Decision",
            "",
        ]
    )
    if ready:
        lines.extend([f"> {PROMOTION_CLAIM}", ""])
    else:
        lines.extend(
            [
                f"> `{STOP_STATUS}`: the exact promotion claim is not established.",
                "",
            ]
        )
    lines.extend(["## Claim boundary", ""])
    lines.extend(f"- {item}" for item in lock["claim_boundary"])
    lines.extend(
        [
            "",
            "This artifact contains no provider execution, generated answer, private "
            "chain-of-thought, GPT hidden-state editing, or fresh benchmark evidence.",
            "",
        ]
    )
    return "\n".join(lines).encode("utf-8")


def _manifest(
    lock: Mapping[str, Any],
    artifacts_without_manifest: Mapping[str, bytes],
    payloads: Mapping[str, Any],
    source_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    ready, decision_status, gates = _promotion_state(payloads["arm_comparison"])
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "status": BUNDLE_STATUS,
        "decision_status": decision_status,
        "promotion_ready": ready,
        "hard_gates": dict(gates),
        "source_receipt_fingerprint_sha256": source_receipt["fingerprint_sha256"],
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
    source_receipt = _seal_fingerprint(_source_receipt(lock, repo_root=repo_root))
    _reject_runtime_metadata(source_receipt, "source_receipt")
    artifacts: dict[str, bytes] = {
        "source_receipt.json": _pretty_json_bytes(source_receipt),
    }
    for payload_name in CORE_PAYLOAD_KEYS:
        filename = PAYLOAD_TO_FILENAME[payload_name]
        artifacts[filename] = _pretty_json_bytes(payloads[payload_name])
    artifacts["mechanism_report.md"] = _mechanism_report(lock, payloads)
    _require(
        set(artifacts) == set(ARTIFACT_FILES),
        "materialized non-manifest file set drift",
    )
    manifest = _manifest(lock, artifacts, payloads, source_receipt)
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
    entries = sorted(directory.iterdir(), key=lambda item: item.name)
    _require(
        [item.name for item in entries] == sorted(ALL_ARTIFACT_FILES),
        "artifact file set mismatch",
    )
    return {
        item.name: _read_regular(item, f"artifact {item.name}") for item in entries
    }


def _bundle_payloads(bundle: Mapping[str, bytes]) -> dict[str, Any]:
    return {
        payload_name: _load_json_bytes(
            bundle[PAYLOAD_TO_FILENAME[payload_name]],
            PAYLOAD_TO_FILENAME[payload_name],
        )
        for payload_name in CORE_PAYLOAD_KEYS
    }


def _validate_bundle_bytes(
    bundle: Mapping[str, bytes],
    lock: Mapping[str, Any],
    *,
    repo_root: Path = ROOT,
) -> None:
    _require(set(bundle) == set(ALL_ARTIFACT_FILES), "bundle key set mismatch")
    source_receipt = _load_json_bytes(bundle["source_receipt.json"], "source receipt")
    _require(isinstance(source_receipt, Mapping), "source receipt root invalid")
    expected_receipt = _seal_fingerprint(_source_receipt(lock, repo_root=repo_root))
    _require_exact_json(source_receipt, expected_receipt, "source receipt derivation")
    _reject_runtime_metadata(source_receipt, "source_receipt")

    payloads = _validate_payload_contract(_bundle_payloads(bundle))
    expected_report = _mechanism_report(lock, payloads)
    _require(
        bundle["mechanism_report.md"] == expected_report,
        "mechanism report is not exact deterministic derivation",
    )
    report = bundle["mechanism_report.md"].decode("utf-8")
    for boundary in lock["claim_boundary"]:
        _require(boundary in report, "report omitted locked claim boundary")

    manifest = _load_json_bytes(bundle[MANIFEST_FILENAME], "manifest")
    _require(isinstance(manifest, Mapping), "manifest root invalid")
    _exact_mapping(
        manifest,
        "manifest",
        {
            "artifact_directory",
            "artifacts",
            "claim_boundary",
            "decision_status",
            "hard_gates",
            "network_calls",
            "promotion_ready",
            "provider_calls",
            "runtime_contract",
            "schema_version",
            "source_receipt_fingerprint_sha256",
            "status",
            "validator_host_used_as_gate",
        },
    )
    _require(manifest["schema_version"] == MANIFEST_SCHEMA_VERSION, "manifest schema drift")
    _require(manifest["status"] == BUNDLE_STATUS, "manifest status drift")
    _require(manifest["artifact_directory"] == ARTIFACT_DIRECTORY, "manifest directory drift")
    _require(manifest["network_calls"] == 0, "manifest network calls drift")
    _require(manifest["provider_calls"] == 0, "manifest provider calls drift")
    _require(manifest["validator_host_used_as_gate"] is False, "host became gate")
    artifact_records = _exact_mapping(
        manifest["artifacts"], "manifest.artifacts", set(ARTIFACT_FILES)
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
            f"digest mismatch: {filename}",
        )
    expected_manifest = _manifest(
        lock,
        {filename: bundle[filename] for filename in ARTIFACT_FILES},
        payloads,
        source_receipt,
    )
    _require_exact_json(manifest, expected_manifest, "manifest derivation")
    _reject_runtime_metadata(manifest, "manifest")


def _write_fsynced(path: Path, value: bytes) -> None:
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
    staging = Path(
        tempfile.mkdtemp(prefix=f".{target.name}.staging-", dir=target.parent)
    )
    backup: Optional[Path] = None
    try:
        for filename in ALL_ARTIFACT_FILES:
            _write_fsynced(staging / filename, artifacts[filename])
        _fsync_directory(staging)
        _validate_bundle_bytes(_read_bundle(staging), lock, repo_root=repo_root)
        if target.exists():
            _require(
                target.is_dir() and not target.is_symlink(),
                "artifact target must be regular directory",
            )
            backup = Path(
                tempfile.mkdtemp(prefix=f".{target.name}.backup-", dir=target.parent)
            )
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
    validate(target)
    return {
        filename: _sha256_bytes(artifacts[filename]) for filename in ALL_ARTIFACT_FILES
    }


def validate(artifact_dir: Optional[Path] = None) -> None:
    lock = _load_lock()
    with _network_guard():
        expected = _materialize(lock)
    _validate_bundle_bytes(expected, lock)
    target = artifact_dir or _artifact_directory(lock)
    observed = _read_bundle(target)
    _validate_bundle_bytes(observed, lock)
    mismatches = [
        filename
        for filename in ALL_ARTIFACT_FILES
        if observed[filename] != expected[filename]
    ]
    _require(not mismatches, f"artifact is not canonical reconstruction: {mismatches}")


def _expect_rejection(label: str, action: Callable[[], Any]) -> None:
    try:
        action()
    except (
        ArtifactValidationError,
        core.TemporalAdjointValidationError,
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
    _require(first == second, "two in-memory builds were not byte-identical")
    _validate_bundle_bytes(first, lock)

    _expect_rejection(
        "duplicate JSON key",
        lambda: _load_json_bytes(b'{"x":1,"x":2}', "duplicate probe"),
    )
    _expect_rejection(
        "non-finite JSON",
        lambda: _load_json_bytes(b'{"x":NaN}', "nonfinite probe"),
    )
    unknown_lock = copy.deepcopy(lock)
    unknown_lock["debug"] = True
    _expect_rejection(
        "unknown lock key",
        lambda: _validate_lock_mapping(unknown_lock, validate_sources=False),
    )
    source_tamper = copy.deepcopy(lock)
    source_tamper["sources"]["core"]["sha256"] = "0" * 64
    _expect_rejection(
        "source hash tamper", lambda: _validate_lock_mapping(source_tamper)
    )
    fixture_tamper = copy.deepcopy(lock)
    fixture_tamper["fixtures"]["event"]["sha256"] = "0" * 64
    _expect_rejection(
        "fixture hash tamper", lambda: _validate_lock_mapping(fixture_tamper)
    )
    predecessor_tamper = copy.deepcopy(lock)
    predecessor_tamper["predecessor"]["fingerprints"][
        "repaired_graph_sha256"
    ] = "0" * 64
    _expect_rejection(
        "predecessor fingerprint tamper",
        lambda: _validate_lock_mapping(predecessor_tamper, validate_sources=False),
    )

    artifact_tamper = dict(first)
    comparison = _load_json_bytes(
        artifact_tamper["arm_comparison.json"], "comparison tamper"
    )
    comparison["promotion_ready"] = not comparison["promotion_ready"]
    artifact_tamper["arm_comparison.json"] = _pretty_json_bytes(comparison)
    _expect_rejection(
        "artifact semantic tamper",
        lambda: _validate_bundle_bytes(artifact_tamper, lock),
    )

    receipt_tamper = dict(first)
    receipt = _load_json_bytes(receipt_tamper["source_receipt.json"], "receipt tamper")
    receipt["predecessor"]["commit_sha"] = "0" * 40
    receipt = _seal_fingerprint(receipt)
    receipt_tamper["source_receipt.json"] = _pretty_json_bytes(receipt)
    receipt_manifest = _load_json_bytes(receipt_tamper["manifest.json"], "manifest")
    receipt_manifest["source_receipt_fingerprint_sha256"] = receipt[
        "fingerprint_sha256"
    ]
    receipt_manifest["artifacts"]["source_receipt.json"] = {
        "bytes": len(receipt_tamper["source_receipt.json"]),
        "sha256": _sha256_bytes(receipt_tamper["source_receipt.json"]),
    }
    receipt_tamper["manifest.json"] = _pretty_json_bytes(receipt_manifest)
    _expect_rejection(
        "coherently resigned source receipt tamper",
        lambda: _validate_bundle_bytes(receipt_tamper, lock),
    )

    report_tamper = dict(first)
    report_tamper["mechanism_report.md"] += b"tampered\n"
    report_manifest = _load_json_bytes(report_tamper["manifest.json"], "manifest")
    report_manifest["artifacts"]["mechanism_report.md"] = {
        "bytes": len(report_tamper["mechanism_report.md"]),
        "sha256": _sha256_bytes(report_tamper["mechanism_report.md"]),
    }
    report_tamper["manifest.json"] = _pretty_json_bytes(report_manifest)
    _expect_rejection(
        "coherently resigned report tamper",
        lambda: _validate_bundle_bytes(report_tamper, lock),
    )

    manifest_tamper = dict(first)
    manifest = _load_json_bytes(manifest_tamper["manifest.json"], "manifest tamper")
    manifest["network_calls"] = 1
    manifest_tamper["manifest.json"] = _pretty_json_bytes(manifest)
    _expect_rejection(
        "manifest network tamper",
        lambda: _validate_bundle_bytes(manifest_tamper, lock),
    )
    extra = dict(first)
    extra["debug.json"] = b"{}\n"
    _expect_rejection("extra artifact", lambda: _validate_bundle_bytes(extra, lock))

    with tempfile.TemporaryDirectory(prefix="ebrt-v054-bundle-audit-") as raw:
        temporary = Path(raw)
        target = temporary / "bundle"
        _publish_bundle(target, first, lock=lock)
        before_fault = _read_bundle(target)
        _expect_rejection(
            "publication fault",
            lambda: _publish_bundle(
                target,
                first,
                lock=lock,
                inject_fault_after_backup=True,
            ),
        )
        _require(_read_bundle(target) == before_fault, "publication rollback failed")
        _require(
            not tuple(temporary.glob(".bundle.staging-*"))
            and not tuple(temporary.glob(".bundle.backup-*")),
            "publication rollback left staging state",
        )
        (target / "unexpected.json").write_text("{}\n", encoding="utf-8")
        _expect_rejection("extra file on disk", lambda: _read_bundle(target))
        (target / "unexpected.json").unlink()
        missing_path = target / "mechanism_report.md"
        missing_bytes = missing_path.read_bytes()
        missing_path.unlink()
        _expect_rejection("missing file on disk", lambda: _read_bundle(target))
        missing_path.write_bytes(missing_bytes)
        manifest_path = target / MANIFEST_FILENAME
        manifest_bytes = manifest_path.read_bytes()
        manifest_path.unlink()
        manifest_path.symlink_to(target / "self_test.json")
        _expect_rejection("symlink artifact", lambda: _read_bundle(target))
        manifest_path.unlink()
        manifest_path.write_bytes(manifest_bytes)

    payloads = _bundle_payloads(first)
    ready, decision_status, gates = _promotion_state(payloads["arm_comparison"])
    return {
        "status": "PASS",
        "self_test": "sealed_portable_network_zero_temporal_lineage_bundle",
        "checks": {
            "artifact_manifest_and_coherent_resign_tampering_rejected": True,
            "extra_missing_and_symlink_artifacts_rejected": True,
            "portable_source_and_predecessor_receipts_verified": True,
            "publication_fault_rollback_verified": True,
            "socket_creation_denied": True,
            "strict_json_duplicate_and_nonfinite_rejected": True,
            "two_build_byte_identity": True,
            "validator_host_not_used_as_gate": True,
        },
        "hard_gates": dict(gates),
        "promotion_ready": ready,
        "decision_status": decision_status,
        "artifact_sha256": {
            filename: _sha256_bytes(first[filename]) for filename in ALL_ARTIFACT_FILES
        },
        "network_calls": 0,
        "provider_calls": 0,
        "claim_boundary": (
            "Contaminated network-zero temporal-lineage mechanism result only."
        ),
    }


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("build", help="build and atomically publish the locked bundle")
    validate_parser = subparsers.add_parser(
        "validate", help="validate and byte-reproduce a published bundle"
    )
    validate_parser.add_argument("--artifact-dir", type=Path, default=None)
    subparsers.add_parser("self-test", help="run network-zero builder tamper tests")
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
    except (ArtifactValidationError, core.TemporalAdjointValidationError) as error:
        raise SystemExit(f"validation failed: {error}") from error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
