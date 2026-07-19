#!/usr/bin/env python3
"""Build the deterministic, network-zero EBRT v0.5.3 lineage bundle.

The builder consumes the byte-pinned canonical v0.5.2 near-pass as immutable
data.  It emits two distinct derivations: a lossless migration that must
reproduce the known fact-local lineage defects, and a separately pinned,
explicitly contaminated repair-overlay regression.  It never reruns or
regrades the hosted v0.5.2 execution.

All v0.5.3 graph computation is standard-library-only and uses strings,
integers, booleans, and deterministic ordering.  No observed host/runtime data
enters canonical artifact bytes.
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

import factorized_lineage_v0_5_3 as core
import verify_hackathon_strategy_walkthrough_v0_5_2_portable as v052_verify


ROOT = Path(__file__).resolve().parent
BUILDER_PATH = Path(__file__).resolve()
LOCK_PATH = ROOT / "policy_lock_factorized_lineage_v0_5_3.json"

LOCK_SCHEMA_VERSION = "ebrt-factorized-lineage-policy-lock-v0.5.3"
LOCK_STATUS = "LOCKED_CONTAMINATED_NETWORK_ZERO_REGRESSION"
MANIFEST_SCHEMA_VERSION = "ebrt-factorized-lineage-manifest-v0.5.3"
SELF_TEST_SCHEMA_VERSION = "ebrt-factorized-lineage-self-test-v0.5.3"
LOSSLESS_ARTIFACT_SCHEMA_VERSION = (
    "ebrt-factorized-lineage-lossless-migration-artifact-v0.5.3"
)
BUNDLE_STATUS = "COMPLETE_NETWORK_ZERO_LINEAGE_REGRESSION"
ARTIFACT_DIRECTORY = "artifacts/factorized_lineage_v0_5_3"
ARTIFACT_FILES = (
    "lossless_migration.json",
    "factorized_lineage_regression.json",
    "self_test.json",
    "mechanism_report.md",
)
MANIFEST_FILENAME = "manifest.json"
ALL_ARTIFACT_FILES = (*ARTIFACT_FILES, MANIFEST_FILENAME)

PREDECESSOR_DIRECTORY = (
    "artifacts/demo_hackathon_strategy_walkthrough_v0_5_2_live_r01"
)
PREDECESSOR_POLICY_PATH = "policy_lock_hackathon_strategy_walkthrough_v0_5_2.json"
PREDECESSOR_VERIFIER_PATH = (
    "verify_hackathon_strategy_walkthrough_v0_5_2_portable.py"
)
SOURCE_FIXTURE_PATH = "fixtures/hackathon_strategy_walkthrough_v0_5_2.json"
SOURCE_FIXTURE_SHA256 = (
    "ef0b1d44ece10e7412460d9abac4791fe3f3a0172e398bca7a0d8957094f56d2"
)
REPAIR_OVERLAY_PATH = "fixtures/factorized_lineage_v0_5_3_repair_overlay.json"
CLOSURE_GOLD_PATH = "fixtures/factorized_lineage_v0_5_3_closure_gold.json"
PREDECESSOR_POLICY_SHA256 = (
    "551190c872d3b9bb9db4f2d6fd1aa15f3f9102084e057e90b80d9259ac429c6c"
)
PREDECESSOR_RESULT_FINGERPRINT = (
    "2e641e0f11f17bb16cbe629048e9cc8cff49706147616d888487f38b243430d4"
)
PREDECESSOR_FILES = {
    "calls.jsonl": {
        "bytes": 3820,
        "sha256": (
            "0d7794f1b6f3010e3d8171d46f4574ad7801e1e96eef84850dc52519cf0b634e"
        ),
    },
    "demo.json": {
        "bytes": 27548,
        "sha256": (
            "f6df3c0a371027fd6ed35cfcc75f0b05dc540ebb6d08efeb3764ab62b4616f6b"
        ),
    },
    "manifest.json": {
        "bytes": 2758,
        "sha256": (
            "ab86d111d1fc0d2b679a0f6ca001e9d33ae1bfc86468aee404887e3da934299f"
        ),
    },
    "report.md": {
        "bytes": 2759,
        "sha256": (
            "81868e378daab3498edbe758ceff9910e7ac0f8c7b444e6913b4ec3e0203fe1d"
        ),
    },
}
EXPECTED_CANONICALIZATION = {
    "encoding": "utf-8",
    "ensure_ascii": False,
    "sort_keys": True,
    "separators": [",", ":"],
    "allow_nan": False,
    "trailing_newline": True,
}
EXPECTED_VOCABULARY = {
    "node_types": ["evidence", "support", "fact", "constraint"],
    "edge_relations": ["supports", "depends_on", "invalidates"],
    "edge_provenance": ["observed", "migration_inferred", "repair_overlay"],
    "positive_closure_relations": ["supports", "depends_on"],
}
EXPECTED_LEGACY_GAPS = {
    "final_priority": ["R4"],
    "demo_centerpiece": ["R2"],
}
EXPECTED_REPAIRED_CLOSURE = {
    "final_priority": ["R2", "R4", "R6"],
    "demo_centerpiece": ["R2", "R4", "R6"],
    "video_constraint": ["R5"],
}
EXPECTED_INVALIDATED = ["R3"]
EXPECTED_OVERLAY_EDGE_IDS = [
    "repair:demo_readiness->final_priority",
    "repair:final_priority->demo_centerpiece",
]
MAX_FILE_BYTES = 2_000_000
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ArtifactValidationError(RuntimeError):
    """Raised when policy, source, artifact, or publication validation fails."""


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


def _reject_constant(value: str) -> Any:
    raise ArtifactValidationError(f"non-finite JSON constant is forbidden: {value}")


def _reject_duplicate_keys(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ArtifactValidationError(f"duplicate JSON key is forbidden: {key}")
        output[key] = value
    return output


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


def _boolean(value: Any, label: str) -> bool:
    _require(type(value) is bool, f"{label}: expected boolean")
    return value


def _integer(value: Any, label: str, *, minimum: int = 0) -> int:
    _require(
        type(value) is int and value >= minimum,
        f"{label}: expected integer >= {minimum}",
    )
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
    resolved_root = repo_root.resolve()
    resolved_candidate = candidate.resolve()
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError as error:
        raise ArtifactValidationError(f"{label}: path escaped repository root") from error
    return candidate


def _read_regular(path: Path, label: str, *, max_bytes: int = MAX_FILE_BYTES) -> bytes:
    try:
        before = path.lstat()
    except OSError as error:
        raise ArtifactValidationError(f"{label}: cannot stat {path}") from error
    _require(stat.S_ISREG(before.st_mode), f"{label}: must be a regular file")
    _require(not path.is_symlink(), f"{label}: symlinks are forbidden")
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
        f"{label}: changed from locked exact value",
    )


def _reject_time_or_host_metadata(value: Any, path: str = "artifact") -> None:
    forbidden = {
        "timestamp",
        "timestamp_utc",
        "generated_at",
        "created_at",
        "updated_at",
        "hostname",
        "host",
        "observed_runtime",
        "runtime_observed",
    }
    if isinstance(value, Mapping):
        for key, child in value.items():
            _require(key not in forbidden, f"{path}: forbidden metadata key {key}")
            _reject_time_or_host_metadata(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_time_or_host_metadata(child, f"{path}[{index}]")


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


def _source_record(value: Any, label: str, repo_root: Path) -> dict[str, Any]:
    record = dict(_exact_mapping(value, label, {"path", "sha256"}))
    path = _safe_repo_path(repo_root, record["path"], f"{label}.path")
    expected = _sha256_string(record["sha256"], f"{label}.sha256")
    observed = _sha256_bytes(_read_regular(path, label))
    _require(observed == expected, f"{label}: source hash mismatch")
    return record


def _validate_lock_mapping(
    value: Any, *, repo_root: Path = ROOT, validate_sources: bool = True
) -> dict[str, Any]:
    lock = dict(
        _exact_mapping(
            value,
            "lock",
            {
                "schema_version",
                "status",
                "sources",
                "predecessor",
                "fixtures",
                "vocabulary",
                "migration_contract",
                "canonicalization",
                "artifact",
                "claim_boundary",
            },
        )
    )
    _require(lock["schema_version"] == LOCK_SCHEMA_VERSION, "lock schema mismatch")
    _require(lock["status"] == LOCK_STATUS, "lock status mismatch")

    sources = _exact_mapping(
        lock["sources"], "lock.sources", {"core", "builder", "v0_5_2_verifier"}
    )
    source_records: dict[str, dict[str, Any]] = {}
    for name, item in sources.items():
        if validate_sources:
            source_records[name] = _source_record(
                item, f"lock.sources.{name}", repo_root
            )
        else:
            source_records[name] = dict(
                _exact_mapping(item, f"lock.sources.{name}", {"path", "sha256"})
            )
            _sha256_string(source_records[name]["sha256"], f"sources.{name}.sha256")
    _require(
        source_records["core"]["path"] == "factorized_lineage_v0_5_3.py",
        "core source path mismatch",
    )
    _require(
        source_records["builder"]["path"]
        == "build_factorized_lineage_artifact_v0_5_3.py",
        "builder source path mismatch",
    )
    _require(
        source_records["v0_5_2_verifier"]["path"] == PREDECESSOR_VERIFIER_PATH,
        "predecessor verifier path mismatch",
    )

    predecessor = _exact_mapping(
        lock["predecessor"],
        "lock.predecessor",
        {
            "artifact_directory",
            "files",
            "policy_lock",
            "result_fingerprint_sha256",
            "walkthrough_contract_passed",
            "relationship",
        },
    )
    _require(
        predecessor["artifact_directory"] == PREDECESSOR_DIRECTORY,
        "predecessor directory mismatch",
    )
    _require_exact_json(predecessor["files"], PREDECESSOR_FILES, "predecessor files")
    policy = _exact_mapping(
        predecessor["policy_lock"], "predecessor.policy_lock", {"path", "sha256"}
    )
    _require(policy["path"] == PREDECESSOR_POLICY_PATH, "predecessor policy path mismatch")
    _require(
        policy["sha256"] == PREDECESSOR_POLICY_SHA256,
        "predecessor policy hash mismatch",
    )
    _require(
        predecessor["result_fingerprint_sha256"] == PREDECESSOR_RESULT_FINGERPRINT,
        "predecessor result fingerprint mismatch",
    )
    _require(
        _boolean(
            predecessor["walkthrough_contract_passed"],
            "predecessor.walkthrough_contract_passed",
        )
        is False,
        "predecessor false verdict must remain exact",
    )
    _string(predecessor["relationship"], "predecessor.relationship")

    fixtures = _exact_mapping(
        lock["fixtures"],
        "lock.fixtures",
        {"source_fixture", "repair_overlay", "closure_gold"},
    )
    source_fixture = dict(
        _exact_mapping(
            fixtures["source_fixture"],
            "lock.fixtures.source_fixture",
            {"path", "sha256", "relationship"},
        )
    )
    _require(
        source_fixture["path"] == SOURCE_FIXTURE_PATH,
        "source fixture path mismatch",
    )
    _require(
        source_fixture["sha256"] == SOURCE_FIXTURE_SHA256,
        "source fixture hash mismatch",
    )
    _string(source_fixture["relationship"], "source_fixture.relationship")
    if validate_sources:
        source_fixture_path = _safe_repo_path(
            repo_root, source_fixture["path"], "source fixture path"
        )
        _require(
            _sha256_bytes(_read_regular(source_fixture_path, "source fixture"))
            == source_fixture["sha256"],
            "source fixture bytes drifted",
        )

    overlay = dict(
        _exact_mapping(
            fixtures["repair_overlay"],
            "lock.fixtures.repair_overlay",
            {"path", "sha256", "schema_version", "overlay_id", "edge_ids"},
        )
    )
    _require(overlay["path"] == REPAIR_OVERLAY_PATH, "repair overlay path mismatch")
    if validate_sources:
        overlay_path = _safe_repo_path(
            repo_root, overlay["path"], "lock.fixtures.repair_overlay.path"
        )
        observed_overlay_hash = _sha256_bytes(
            _read_regular(overlay_path, "repair overlay fixture")
        )
        _require(
            observed_overlay_hash == overlay["sha256"],
            "repair overlay fixture hash mismatch",
        )
    _sha256_string(overlay["sha256"], "overlay_fixture.sha256")
    _require(
        overlay["schema_version"] == core.OVERLAY_SCHEMA_VERSION,
        "repair overlay schema mismatch",
    )
    _string(overlay["overlay_id"], "overlay_fixture.overlay_id")
    _require_exact_json(
        overlay["edge_ids"], EXPECTED_OVERLAY_EDGE_IDS, "repair_overlay.edge_ids"
    )

    gold = dict(
        _exact_mapping(
            fixtures["closure_gold"],
            "lock.fixtures.closure_gold",
            {"path", "sha256", "schema_version", "relationship"},
        )
    )
    _require(gold["path"] == CLOSURE_GOLD_PATH, "closure gold path mismatch")
    _sha256_string(gold["sha256"], "closure_gold.sha256")
    _require(
        gold["schema_version"] == core.GOLD_SCHEMA_VERSION,
        "closure gold schema mismatch",
    )
    _require(
        gold["relationship"]
        == "grading input only; excluded from graph construction and closure",
        "closure gold relationship mismatch",
    )
    if validate_sources:
        gold_path = _safe_repo_path(repo_root, gold["path"], "closure gold path")
        _require(
            _sha256_bytes(_read_regular(gold_path, "closure gold fixture"))
            == gold["sha256"],
            "closure gold fixture hash mismatch",
        )

    _require_exact_json(lock["vocabulary"], EXPECTED_VOCABULARY, "vocabulary")
    _require_exact_json(
        list(core.NODE_TYPES), EXPECTED_VOCABULARY["node_types"], "core node vocabulary"
    )
    _require_exact_json(
        list(core.EDGE_TYPES),
        EXPECTED_VOCABULARY["edge_relations"],
        "core edge vocabulary",
    )
    _require_exact_json(
        list(core.PROVENANCE_VALUES),
        EXPECTED_VOCABULARY["edge_provenance"],
        "core provenance vocabulary",
    )
    migration = _exact_mapping(
        lock["migration_contract"],
        "lock.migration_contract",
        {
            "source_phase",
            "legacy_missing_evidence",
            "repaired_active_closure",
            "invalidated_evidence_ids",
            "legacy_verdict_preserved",
            "overlay_contaminated",
        },
    )
    _require(
        migration["source_phase"] == "controlled_after_event",
        "migration source phase mismatch",
    )
    _require_exact_json(
        migration["legacy_missing_evidence"],
        EXPECTED_LEGACY_GAPS,
        "migration legacy gaps",
    )
    _require_exact_json(
        migration["repaired_active_closure"],
        EXPECTED_REPAIRED_CLOSURE,
        "migration repaired closure",
    )
    _require_exact_json(
        migration["invalidated_evidence_ids"],
        EXPECTED_INVALIDATED,
        "migration invalidated evidence",
    )
    _require(
        migration["legacy_verdict_preserved"] is True,
        "legacy verdict preservation must be true",
    )
    _require(
        migration["overlay_contaminated"] is True,
        "overlay contamination disclosure must be true",
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
            "runtime_contract",
        },
    )
    _require(artifact["directory"] == ARTIFACT_DIRECTORY, "artifact directory mismatch")
    _require_exact_json(artifact["files"], list(ALL_ARTIFACT_FILES), "artifact files")
    _require_exact_json(
        artifact["manifest_digest_coverage"],
        list(ARTIFACT_FILES),
        "manifest digest coverage",
    )
    _require(
        _integer(artifact["network_calls"], "artifact.network_calls") == 0,
        "artifact network calls must remain zero",
    )
    _string(artifact["runtime_contract"], "artifact.runtime_contract")
    boundaries = lock["claim_boundary"]
    _require(isinstance(boundaries, list) and bool(boundaries), "empty claim boundary")
    _require(
        all(isinstance(item, str) and item and item == item.strip() for item in boundaries),
        "claim boundary entries must be trimmed non-empty strings",
    )
    _require(len(boundaries) == len(set(boundaries)), "duplicate claim boundary")
    return copy.deepcopy(lock)


def _load_lock(*, repo_root: Path = ROOT) -> dict[str, Any]:
    value, _ = _read_json_regular(
        _safe_repo_path(
            repo_root,
            "policy_lock_factorized_lineage_v0_5_3.json",
            "policy lock path",
        ),
        "policy lock",
    )
    return _validate_lock_mapping(value, repo_root=repo_root)


def _source_ledger(lock: Mapping[str, Any], *, repo_root: Path) -> dict[str, Any]:
    ledger: dict[str, Any] = {
        "policy_lock": {
            "path": "policy_lock_factorized_lineage_v0_5_3.json",
            "sha256": _sha256_bytes(
                _read_regular(
                    _safe_repo_path(
                        repo_root,
                        "policy_lock_factorized_lineage_v0_5_3.json",
                        "policy lock",
                    ),
                    "policy lock",
                )
            ),
        },
        "predecessor_policy_lock": copy.deepcopy(lock["predecessor"]["policy_lock"]),
    }
    for name, record in sorted(lock["sources"].items()):
        ledger[f"source:{name}"] = copy.deepcopy(record)
    for name, record in sorted(lock["fixtures"].items()):
        ledger[f"fixture:{name}"] = copy.deepcopy(record)
    for filename, record in sorted(lock["predecessor"]["files"].items()):
        ledger[f"predecessor_artifact:{filename}"] = {
            "path": f"{PREDECESSOR_DIRECTORY}/{filename}",
            "bytes": record["bytes"],
            "sha256": record["sha256"],
        }
    return dict(sorted(ledger.items()))


def _load_pinned_inputs(
    lock: Mapping[str, Any], *, repo_root: Path
) -> tuple[dict[str, Path], dict[str, Any]]:
    predecessor_dir = _safe_repo_path(
        repo_root, lock["predecessor"]["artifact_directory"], "predecessor directory"
    )
    verification = v052_verify.verify_artifact(predecessor_dir, repo_root=repo_root)
    _require(
        verification["walkthrough_contract_passed"] is False,
        "portable verifier did not preserve predecessor false",
    )
    observed_names = sorted(item.name for item in predecessor_dir.iterdir())
    _require(
        observed_names == sorted(PREDECESSOR_FILES),
        "predecessor artifact file set mismatch",
    )
    for filename, expected in PREDECESSOR_FILES.items():
        raw = _read_regular(predecessor_dir / filename, f"predecessor {filename}")
        _require(len(raw) == expected["bytes"], f"predecessor byte count drift: {filename}")
        _require(
            _sha256_bytes(raw) == expected["sha256"],
            f"predecessor hash drift: {filename}",
        )
    demo_value = _load_json_bytes(
        _read_regular(predecessor_dir / "demo.json", "predecessor demo"),
        "predecessor demo",
    )
    _require(isinstance(demo_value, dict), "predecessor demo root must be object")
    _require(
        demo_value.get("fingerprint_sha256") == PREDECESSOR_RESULT_FINGERPRINT,
        "predecessor demo fingerprint drift",
    )
    _require(
        demo_value.get("decision", {}).get("walkthrough_contract_passed") is False,
        "predecessor demo false verdict drift",
    )
    paths = {
        "source_artifact_dir": predecessor_dir,
        "source_fixture": _safe_repo_path(
            repo_root,
            lock["fixtures"]["source_fixture"]["path"],
            "source fixture path",
        ),
        "repair_overlay": _safe_repo_path(
            repo_root,
            lock["fixtures"]["repair_overlay"]["path"],
            "repair overlay fixture path",
        ),
        "closure_gold": _safe_repo_path(
            repo_root,
            lock["fixtures"]["closure_gold"]["path"],
            "closure gold fixture path",
        ),
    }
    return paths, dict(verification)


def _seal_lossless_artifact(observed: Mapping[str, Any]) -> dict[str, Any]:
    payload = {
        "closure": copy.deepcopy(observed["closure"]),
        "grade": copy.deepcopy(observed["grade"]),
        "graph": copy.deepcopy(observed["graph"]),
        "legacy_endpoint": {
            "preserved_byte_frozen_result": True,
            "walkthrough_contract_passed": False,
        },
        "schema_version": LOSSLESS_ARTIFACT_SCHEMA_VERSION,
        "status": "EXPECTED_LEGACY_DEFECT_REPRODUCED",
    }
    payload["fingerprint_sha256"] = _sha256_bytes(_canonical_json_bytes(payload))
    return payload


def _validate_lossless_artifact(value: Mapping[str, Any]) -> None:
    _exact_mapping(
        value,
        "lossless artifact",
        {
            "closure",
            "fingerprint_sha256",
            "grade",
            "graph",
            "legacy_endpoint",
            "schema_version",
            "status",
        },
    )
    _require(
        value["schema_version"] == LOSSLESS_ARTIFACT_SCHEMA_VERSION,
        "lossless artifact schema drift",
    )
    _require(
        value["status"] == "EXPECTED_LEGACY_DEFECT_REPRODUCED",
        "lossless artifact status drift",
    )
    _require(
        value["legacy_endpoint"]
        == {
            "preserved_byte_frozen_result": True,
            "walkthrough_contract_passed": False,
        },
        "lossless artifact rewrote predecessor endpoint",
    )
    core.validate_graph(value["graph"])
    core.validate_closure_report(value["closure"])
    core.validate_closure_grade(value["grade"])
    _require(value["graph"]["status"] == "LOSSLESS_MIGRATION", "lossless graph status drift")
    _require(value["grade"]["status"] == "FAIL", "lossless grade must remain FAIL")
    gaps = {
        (row["target_id"], row["evidence_id"]) for row in value["grade"]["gaps"]
    }
    _require(
        gaps
        == {
            ("fact:demo_centerpiece", "R2"),
            ("fact:final_priority", "R4"),
        },
        "lossless artifact did not preserve exact legacy defects",
    )
    material = copy.deepcopy(dict(value))
    fingerprint = material.pop("fingerprint_sha256")
    _require(
        fingerprint == _sha256_bytes(_canonical_json_bytes(material)),
        "lossless artifact fingerprint mismatch",
    )


def _classification_by_evidence(target: Mapping[str, Any]) -> dict[str, str]:
    result = {
        evidence_id: "direct"
        for evidence_id in target["direct_active_evidence_ids"]
    }
    for evidence_id in target["inherited_active_evidence_ids"]:
        _require(evidence_id not in result, "closure classification overlap")
        result[evidence_id] = "inherited"
    _require(
        sorted(result) == target["all_active_evidence_ids"],
        "closure classification partition drift",
    )
    return result


def _validate_exact_repair_delta(regression: Mapping[str, Any]) -> None:
    observed = regression["observed"]["closure"]
    repaired = regression["repaired"]["closure"]
    _require(
        observed["active_evidence_ids"] == repaired["active_evidence_ids"],
        "repair changed global active evidence",
    )
    _require(
        observed["invalidated_evidence_ids"] == repaired["invalidated_evidence_ids"]
        == EXPECTED_INVALIDATED,
        "repair changed invalidation history",
    )
    observed_targets = {row["target_id"]: row for row in observed["targets"]}
    repaired_targets = {row["target_id"]: row for row in repaired["targets"]}
    _require(
        set(observed_targets) == set(repaired_targets),
        "repair changed closure target set",
    )
    expected_additions = {
        "constraint:video_constraint": set(),
        "fact:demo_centerpiece": {"R2"},
        "fact:final_priority": {"R4"},
    }
    _require(
        set(observed_targets) == set(expected_additions),
        "canonical closure target set drift",
    )
    for target_id, expected_added in expected_additions.items():
        before = observed_targets[target_id]
        after = repaired_targets[target_id]
        before_ids = set(before["all_active_evidence_ids"])
        after_ids = set(after["all_active_evidence_ids"])
        _require(
            after_ids - before_ids == expected_added,
            f"unexpected reachability addition at {target_id}",
        )
        _require(
            before_ids - after_ids == set(),
            f"repair removed active evidence at {target_id}",
        )
        before_classes = _classification_by_evidence(before)
        after_classes = _classification_by_evidence(after)
        for evidence_id in sorted(before_ids):
            _require(
                before_classes[evidence_id] == after_classes[evidence_id],
                f"repair reclassified existing evidence at {target_id}:{evidence_id}",
            )
    _require(
        _classification_by_evidence(repaired_targets["fact:final_priority"])["R4"]
        == "direct",
        "R4 must enter final_priority as direct support",
    )
    _require(
        _classification_by_evidence(repaired_targets["fact:demo_centerpiece"])["R2"]
        == "inherited",
        "R2 must enter demo_centerpiece through fact dependency",
    )


# Core integration is deliberately localized here so the artifact builder does
# not duplicate graph semantics.
def _core_materialize(
    paths: Mapping[str, Path],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    regression = core.build_regression(
        source_artifact_dir=paths["source_artifact_dir"],
        fixture_path=paths["source_fixture"],
        overlay_path=paths["repair_overlay"],
        gold_path=paths["closure_gold"],
    )
    core.validate_regression(regression)
    _validate_exact_repair_delta(regression)
    ablation = core.diagnose_repair_edge_ablation(
        regression["observed"]["graph"],
        paths["repair_overlay"],
        paths["closure_gold"],
    )
    _require(ablation.get("status") == "PASS", "repair-edge ablation failed")
    _require_exact_json(
        ablation,
        regression["repair_edge_ablation"],
        "regression repair-edge ablation",
    )
    ablation_cases = {
        row["removed_edge_id"]: (
            row["expected_reopened_target_id"],
            row["expected_reopened_evidence_id"],
            row["grade_status"],
        )
        for row in ablation.get("cases", [])
    }
    _require(
        ablation_cases
        == {
            "repair:demo_readiness->final_priority": (
                "fact:final_priority",
                "R4",
                "FAIL",
            ),
            "repair:final_priority->demo_centerpiece": (
                "fact:demo_centerpiece",
                "R2",
                "FAIL",
            ),
        },
        "repair-edge ablation cases drifted",
    )
    lossless = _seal_lossless_artifact(regression["observed"])
    _validate_lossless_artifact(lossless)
    core_self_test = core.self_test()
    _require(core_self_test.get("status") == "PASS", "core self-test failed")
    return dict(lossless), dict(regression), dict(ablation), dict(core_self_test)


def _build_self_test_artifact(
    lock: Mapping[str, Any],
    lossless: Mapping[str, Any],
    regression: Mapping[str, Any],
    ablation: Mapping[str, Any],
    core_self_test: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": SELF_TEST_SCHEMA_VERSION,
        "status": "PASS",
        "network_calls": 0,
        "checks": {
            "core_self_test_passed": core_self_test.get("status") == "PASS",
            "predecessor_verdict_false_preserved": True,
            "lossless_migration_reproduced_both_legacy_gaps": True,
            "overlay_exactly_two_pinned_edges": True,
            "repaired_direct_and_inherited_closure_exact": True,
            "deterministic_witness_paths_verified": True,
            "invalidated_R3_excluded_from_active_closure": True,
            "stable_R5_constraint_preserved": True,
            "removing_each_overlay_edge_reopens_declared_gap": True,
            "canonical_order_and_fingerprints_verified": True,
            "no_host_or_time_metadata_in_artifacts": True,
        },
        "legacy": {
            "status": lossless.get("status"),
            "missing_evidence": copy.deepcopy(EXPECTED_LEGACY_GAPS),
            "walkthrough_contract_passed": False,
        },
        "regression": {
            "status": regression.get("status"),
            "active_closure": copy.deepcopy(EXPECTED_REPAIRED_CLOSURE),
            "overlay_contaminated": True,
        },
        "repair_edge_ablation": copy.deepcopy(ablation),
        "core_self_test": copy.deepcopy(core_self_test),
        "claim_boundary": list(lock["claim_boundary"]),
    }


def _mechanism_report(
    lock: Mapping[str, Any],
    lossless: Mapping[str, Any],
    regression: Mapping[str, Any],
) -> bytes:
    lines = [
        "# EBRT v0.5.3 factorized-lineage mechanism report",
        "",
        f"Status: **{BUNDLE_STATUS}**",
        "",
        "## Frozen predecessor",
        "",
        "The byte-pinned v0.5.2 hosted walkthrough remains a strict near-pass.",
        "Its original `walkthrough_contract_passed=false` verdict is preserved.",
        "No provider call, hosted replay, or regrade occurs in this bundle.",
        "",
        "## Lossless migration",
        "",
        f"Status: **{lossless.get('status')}**",
        "",
        "The typed migration reproduces the two known fact-local gaps:",
        "",
        "- `final_priority`: missing `R4`",
        "- `demo_centerpiece`: missing `R2`",
        "",
        "## Contaminated repair regression",
        "",
        f"Status: **{regression.get('status')}**",
        "",
        "The separately locked two-edge repair yields:",
        "",
        "- `final_priority`: active closure `R2, R4, R6`",
        "- `demo_centerpiece`: active closure `R2, R4, R6`",
        "- `video_constraint`: active closure `R5`",
        "- invalidated history: `R3`",
        "",
        "This is a contaminated engineering regression over one known failure, not",
        "fresh evidence of reasoning improvement or autonomous graph discovery.",
        "",
        "## Reproduction boundary",
        "",
        "- standard-library-only v0.5.3 graph computation",
        "- deterministic string/integer/boolean canonical artifacts",
        "- validator host and wall-clock time excluded from canonical bytes",
        "- network calls: `0`",
        "",
        "## Claim boundary",
        "",
    ]
    lines.extend(f"- {item}" for item in lock["claim_boundary"])
    lines.append("")
    return "\n".join(lines).encode("utf-8")


def _manifest(
    lock: Mapping[str, Any],
    artifacts_without_manifest: Mapping[str, bytes],
    lossless: Mapping[str, Any],
    regression: Mapping[str, Any],
    *,
    repo_root: Path,
) -> dict[str, Any]:
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "status": BUNDLE_STATUS,
        "source_ledger": _source_ledger(lock, repo_root=repo_root),
        "artifacts": {
            filename: {
                "bytes": len(artifacts_without_manifest[filename]),
                "sha256": _sha256_bytes(artifacts_without_manifest[filename]),
            }
            for filename in ARTIFACT_FILES
        },
        "network_calls": 0,
        "runtime_contract": lock["artifact"]["runtime_contract"],
        "validator_host_used_as_gate": False,
        "legacy": {
            "source_result_fingerprint_sha256": PREDECESSOR_RESULT_FINGERPRINT,
            "walkthrough_contract_passed": False,
            "migration_status": lossless.get("status"),
        },
        "regression": {
            "status": regression.get("status"),
            "overlay_contaminated": True,
        },
        "claim_boundary": list(lock["claim_boundary"]),
    }


def _materialize(
    lock: Mapping[str, Any], *, repo_root: Path = ROOT
) -> dict[str, bytes]:
    paths, _verification = _load_pinned_inputs(lock, repo_root=repo_root)
    with _network_guard():
        lossless, regression, ablation, core_self_test = _core_materialize(paths)
    _reject_time_or_host_metadata(lossless, "lossless_migration")
    _reject_time_or_host_metadata(regression, "factorized_lineage_regression")
    self_test = _build_self_test_artifact(
        lock, lossless, regression, ablation, core_self_test
    )
    _reject_time_or_host_metadata(self_test, "self_test")
    artifacts: dict[str, bytes] = {
        "lossless_migration.json": _pretty_json_bytes(lossless),
        "factorized_lineage_regression.json": _pretty_json_bytes(regression),
        "self_test.json": _pretty_json_bytes(self_test),
        "mechanism_report.md": _mechanism_report(lock, lossless, regression),
    }
    manifest = _manifest(
        lock, artifacts, lossless, regression, repo_root=repo_root
    )
    _reject_time_or_host_metadata(manifest, "manifest")
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


def _validate_bundle_bytes(
    bundle: Mapping[str, bytes], lock: Mapping[str, Any], *, repo_root: Path = ROOT
) -> None:
    _require(set(bundle) == set(ALL_ARTIFACT_FILES), "bundle key set mismatch")
    manifest = _load_json_bytes(bundle[MANIFEST_FILENAME], "manifest")
    _require(isinstance(manifest, Mapping), "manifest root must be object")
    _exact_mapping(
        manifest,
        "manifest",
        {
            "schema_version",
            "status",
            "source_ledger",
            "artifacts",
            "network_calls",
            "runtime_contract",
            "validator_host_used_as_gate",
            "legacy",
            "regression",
            "claim_boundary",
        },
    )
    _require(manifest["schema_version"] == MANIFEST_SCHEMA_VERSION, "manifest schema drift")
    _require(manifest["status"] == BUNDLE_STATUS, "manifest status drift")
    _require(manifest["network_calls"] == 0, "manifest network boundary drift")
    _require(
        manifest["validator_host_used_as_gate"] is False,
        "validator host became a gate",
    )
    _require_exact_json(
        manifest["source_ledger"],
        _source_ledger(lock, repo_root=repo_root),
        "manifest source ledger",
    )
    artifact_records = _exact_mapping(
        manifest["artifacts"], "manifest.artifacts", set(ARTIFACT_FILES)
    )
    _require(MANIFEST_FILENAME not in artifact_records, "manifest hashed itself")
    for filename in ARTIFACT_FILES:
        record = _exact_mapping(
            artifact_records[filename],
            f"manifest.artifacts.{filename}",
            {"bytes", "sha256"},
        )
        _require(record["bytes"] == len(bundle[filename]), f"artifact size mismatch: {filename}")
        _require(
            record["sha256"] == _sha256_bytes(bundle[filename]),
            f"artifact hash mismatch: {filename}",
        )
    _require(
        manifest["legacy"]["walkthrough_contract_passed"] is False,
        "manifest rewrote predecessor verdict",
    )
    _require(manifest["regression"]["overlay_contaminated"] is True, "overlay disclosure drift")
    _require_exact_json(manifest["claim_boundary"], lock["claim_boundary"], "claim boundary")
    _reject_time_or_host_metadata(manifest, "manifest")

    lossless = _load_json_bytes(bundle["lossless_migration.json"], "lossless migration")
    regression = _load_json_bytes(
        bundle["factorized_lineage_regression.json"], "factorized regression"
    )
    _require(isinstance(lossless, Mapping), "lossless migration root must be object")
    _require(isinstance(regression, Mapping), "regression root must be object")
    _validate_lossless_artifact(lossless)
    core.validate_regression(regression)
    _reject_time_or_host_metadata(lossless, "lossless_migration")
    _reject_time_or_host_metadata(regression, "factorized_lineage_regression")

    self_test = _load_json_bytes(bundle["self_test.json"], "self-test")
    _require(isinstance(self_test, Mapping), "self-test root must be object")
    _exact_mapping(
        self_test,
        "self-test",
        {
            "schema_version",
            "status",
            "network_calls",
            "checks",
            "legacy",
            "regression",
            "repair_edge_ablation",
            "core_self_test",
            "claim_boundary",
        },
    )
    _require(self_test.get("schema_version") == SELF_TEST_SCHEMA_VERSION, "self-test schema drift")
    _require(self_test.get("status") == "PASS", "self-test status drift")
    _require(self_test.get("network_calls") == 0, "self-test network boundary drift")
    _require(
        isinstance(self_test.get("checks"), Mapping)
        and all(value is True for value in self_test["checks"].values()),
        "builder self-test checks did not all pass",
    )
    _require(
        self_test.get("legacy", {}).get("walkthrough_contract_passed") is False,
        "self-test rewrote predecessor verdict",
    )
    _require_exact_json(self_test.get("claim_boundary"), lock["claim_boundary"], "self-test claim boundary")
    _require(
        self_test["repair_edge_ablation"].get("status") == "PASS"
        and len(self_test["repair_edge_ablation"].get("cases", [])) == 2,
        "repair-edge ablation evidence drifted",
    )
    _require(
        self_test["core_self_test"].get("status") == "PASS"
        and all(
            value is True
            for value in self_test["core_self_test"].get("checks", {}).values()
        ),
        "nested core self-test did not pass",
    )
    expected_self_test = _build_self_test_artifact(
        lock,
        lossless,
        regression,
        self_test["repair_edge_ablation"],
        self_test["core_self_test"],
    )
    _require_exact_json(self_test, expected_self_test, "self-test exact derivation")
    expected_report_bytes = _mechanism_report(lock, lossless, regression)
    _require(
        bundle["mechanism_report.md"] == expected_report_bytes,
        "mechanism report is not the exact deterministic derivation",
    )
    report = bundle["mechanism_report.md"].decode("utf-8")
    _require(BUNDLE_STATUS in report, "report missing bundle status")
    _require("walkthrough_contract_passed=false" in report, "report hid predecessor false")
    for boundary in lock["claim_boundary"]:
        _require(boundary in report, "report omitted locked claim boundary")
    expected_manifest = _manifest(
        lock,
        {filename: bundle[filename] for filename in ARTIFACT_FILES},
        lossless,
        regression,
        repo_root=repo_root,
    )
    _require_exact_json(manifest, expected_manifest, "manifest exact derivation")


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
        staged = _read_bundle(staging)
        _validate_bundle_bytes(staged, lock, repo_root=repo_root)
        if target.exists():
            _require(target.is_dir() and not target.is_symlink(), "artifact target must be regular directory")
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
        core.FactorizedLineageValidationError,
        ValueError,
        AssertionError,
    ):
        return
    raise AssertionError(f"tamper unexpectedly passed: {label}")


def self_test() -> dict[str, Any]:
    lock = _load_lock()
    predecessor_verifier_self_test = v052_verify.self_test()
    _require(
        predecessor_verifier_self_test.get("status") == "PASS",
        "predecessor portable verifier self-test failed",
    )
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
        lambda: _load_json_bytes(b'{"x":NaN}', "NaN probe"),
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
    overlay_hash_tamper = copy.deepcopy(lock)
    overlay_hash_tamper["fixtures"]["repair_overlay"]["sha256"] = "0" * 64
    _expect_rejection(
        "overlay hash tamper", lambda: _validate_lock_mapping(overlay_hash_tamper)
    )
    gold_hash_tamper = copy.deepcopy(lock)
    gold_hash_tamper["fixtures"]["closure_gold"]["sha256"] = "0" * 64
    _expect_rejection(
        "closure gold hash tamper",
        lambda: _validate_lock_mapping(gold_hash_tamper),
    )
    predecessor_tamper = copy.deepcopy(lock)
    predecessor_tamper["predecessor"]["files"]["demo.json"]["sha256"] = "0" * 64
    _expect_rejection(
        "predecessor seal tamper",
        lambda: _validate_lock_mapping(predecessor_tamper, validate_sources=False),
    )
    overlay_tamper = copy.deepcopy(lock)
    overlay_tamper["fixtures"]["repair_overlay"]["edge_ids"].reverse()
    _expect_rejection(
        "overlay policy tamper",
        lambda: _validate_lock_mapping(overlay_tamper, validate_sources=False),
    )

    artifact_tamper = dict(first)
    regression = _load_json_bytes(
        artifact_tamper["factorized_lineage_regression.json"], "regression tamper"
    )
    regression["overlay_contaminated"] = False
    artifact_tamper["factorized_lineage_regression.json"] = _pretty_json_bytes(regression)
    _expect_rejection(
        "artifact semantic tamper",
        lambda: _validate_bundle_bytes(artifact_tamper, lock),
    )
    manifest_tamper = dict(first)
    manifest = _load_json_bytes(manifest_tamper["manifest.json"], "manifest tamper")
    manifest["network_calls"] = 1
    manifest_tamper["manifest.json"] = _pretty_json_bytes(manifest)
    _expect_rejection(
        "manifest network tamper",
        lambda: _validate_bundle_bytes(manifest_tamper, lock),
    )
    coherent_report_tamper = dict(first)
    coherent_report_tamper["mechanism_report.md"] += b"tampered\n"
    coherent_manifest = _load_json_bytes(
        coherent_report_tamper["manifest.json"], "coherent manifest tamper"
    )
    coherent_manifest["artifacts"]["mechanism_report.md"] = {
        "bytes": len(coherent_report_tamper["mechanism_report.md"]),
        "sha256": _sha256_bytes(coherent_report_tamper["mechanism_report.md"]),
    }
    coherent_report_tamper["manifest.json"] = _pretty_json_bytes(coherent_manifest)
    _expect_rejection(
        "coherently re-signed report tamper",
        lambda: _validate_bundle_bytes(coherent_report_tamper, lock),
    )
    extra = dict(first)
    extra["debug.json"] = b"{}\n"
    _expect_rejection("extra artifact", lambda: _validate_bundle_bytes(extra, lock))

    with tempfile.TemporaryDirectory(prefix="ebrt-v053-artifact-audit-") as raw:
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
        _require(_read_bundle(target) == before_fault, "publication fault changed target")
        _require(
            not tuple(temporary.glob(".bundle.staging-*"))
            and not tuple(temporary.glob(".bundle.backup-*")),
            "publication fault left staging or backup state",
        )
        (target / "unexpected.json").write_text("{}\n", encoding="utf-8")
        _expect_rejection("extra file on disk", lambda: _read_bundle(target))
        (target / "unexpected.json").unlink()
        missing_path = target / "mechanism_report.md"
        missing_bytes = missing_path.read_bytes()
        missing_path.unlink()
        _expect_rejection("missing file on disk", lambda: _read_bundle(target))
        missing_path.write_bytes(missing_bytes)
        manifest_path = target / "manifest.json"
        manifest_bytes = manifest_path.read_bytes()
        manifest_path.unlink()
        manifest_path.symlink_to(target / "self_test.json")
        _expect_rejection("symlink artifact", lambda: _read_bundle(target))
        manifest_path.unlink()
        manifest_path.write_bytes(manifest_bytes)

    return {
        "status": "PASS",
        "self_test": "deterministic_portable_network_zero_lineage_bundle",
        "checks": {
            "two_build_byte_identity": True,
            "socket_creation_denied": True,
            "strict_json_duplicate_and_nonfinite_rejected": True,
            "source_predecessor_and_overlay_seals_verified": True,
            "predecessor_portable_verifier_tamper_suite_passed": True,
            "core_schema_closure_witness_and_mutation_tests_passed": True,
            "artifact_manifest_and_coherent_resign_tampering_rejected": True,
            "extra_missing_and_symlink_artifacts_rejected": True,
            "publication_fault_rollback_verified": True,
            "validator_host_not_used_as_gate": True,
        },
        "artifact_sha256": {
            filename: _sha256_bytes(first[filename]) for filename in ALL_ARTIFACT_FILES
        },
        "network_calls": 0,
        "claim_boundary": (
            "Contaminated, network-zero public-lineage engineering regression only."
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


def main(argv: Sequence[str] | None = None) -> int:
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
    except (ArtifactValidationError, core.FactorizedLineageValidationError) as error:
        raise SystemExit(f"validation failed: {error}") from error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
