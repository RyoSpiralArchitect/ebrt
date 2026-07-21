#!/usr/bin/env python3
"""Pure-stdlib verifier for the frozen EBRT v0.6.3.2 live-r01 result.

The verifier imports neither the producer nor any provider, ML, validation, or
Git package.  It validates a copied seven-file artifact plus the frozen live
policy lock, reconstructs the public compiler and two-block classifier from
the recorded public values, and never opens a network or provider boundary.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parent
DEFAULT_ARTIFACT = ROOT / "artifacts" / "actuator_uptake_replication_v0_6_3_2_live_r01"
DEFAULT_LOCK = ROOT / "policy_lock_actuator_uptake_replication_v0_6_3_2_live_r01.json"

EXPECTED_FILES: dict[str, tuple[int, str]] = {
    "attempt_journal.jsonl": (
        35909,
        "d916bfd351df8820bf9a4b4f9c7ff48a0f29667a011436c9111ae81d5b63c231",
    ),
    "calls.jsonl": (
        15725,
        "747a08604f5595ab9069e2f940278207b445b50679736a6bd80c5b10e17cca2a",
    ),
    "manifest.json": (
        4040,
        "ebd53b9ff54d3ac3070983e5835021e78cadf6f0df91225a6bea053c9629b5e6",
    ),
    "projection_bundle.json": (
        20628,
        "b564c66dea7caec3cb67b434774d234b4fd5691aac196ce5f37370a8fc376d7d",
    ),
    "provider_inputs.json": (
        17342,
        "937bcebc9fb03fa6a241c72b80968ec1fe354bbd72c1ff2484a71a42cb9066a1",
    ),
    "report.md": (
        2154,
        "ab7da3341b00e8201477c099423bc7a714478f749ba26814ffb8a8b9c2f4dc3d",
    ),
    "result.json": (
        62935,
        "7e37a37751fe273d895c8d62709cf03ad8c18480f5c5e890191fa030c7b1b353",
    ),
}

EXPECTED_LOCK_BYTES = 11028
EXPECTED_LOCK_SHA256 = (
    "d672987430f3388be03f410481c89e24d6af1c7ec8a43917307a5c9debfc3d24"
)
EXPECTED_LOCK_FINGERPRINT = (
    "7cf24f5f9a57c3c8bf9d9b56d3dd2ae3cc7bafdbf7355bd0aec4d6a57d44af17"
)
EXPECTED_RESULT_FINGERPRINT = (
    "97634c76bfaf2b027368379d8ee7a5520a866c1a999e8686741577febaff7c52"
)
EXPECTED_MANIFEST_FINGERPRINT = (
    "8cfd4018248e482a89b164c585ca816d80b78da3e225a7616905a7cfd56b7790"
)
EXPECTED_PROVIDER_INPUTS_FINGERPRINT = (
    "4fe04eee19ccdea0d477d65164982c9c5a2fa15c3ece0708a6db8fa69061c3db"
)
EXPECTED_PROJECTION_FINGERPRINT = (
    "6b9125b40dbb2d00c84bf7609deca4389c04ab33d262b0fc6000c2c939ffecd4"
)
EXPECTED_AUTHORIZATION_TAG_OBJECT = "e7f4ca03ed04010cf2e399865950973fd066ca41"
EXPECTED_AUTHORIZED_COMMIT = "dc8b344bb7ff05a7d9d0a8e967f1e0c1efc5bf8c"
EXPECTED_PREFLIGHT_TAG_OBJECT = "f7770f4d4ac81fc148bda99f722e50e6ad47b47c"
EXPECTED_PREFLIGHT_COMMIT = "27ad46cc1479b855fbbc450a430afeaeb97a7976"

EXECUTION_ORDER = ("C", "Z", "D", "X", "D", "X", "C", "Z")
BLOCK_SCHEDULES = {"A": ("C", "Z", "D", "X"), "B": ("D", "X", "C", "Z")}
ARMS = ("Z", "C", "D", "X")
BLOCK_IDS = ("A", "B")

SCHEDULE: tuple[tuple[int, str, int, str, str, str, str], ...] = (
    (
        1,
        "A",
        1,
        "C",
        "A_39276f79d4d0b99f",
        "Q_9c19934ca3e89315",
        "cd79b48764fcf316a794dd43d854308cfbfb45895adccd405ba64340e6a35b05",
    ),
    (
        2,
        "A",
        2,
        "Z",
        "A_21009567d2b053a7",
        "Q_164a956eb63d7d9f",
        "ffa986deea3af1c9e63d5633e407c86e81b70b0a29b7eb2401be91f08197995a",
    ),
    (
        3,
        "A",
        3,
        "D",
        "A_2e4f7eee0d24f793",
        "Q_d5e1d40fbdddf363",
        "1c3eb3971d4c6e5f418b6e3ff40c9d02177812d2307a140367d82c581c66279a",
    ),
    (
        4,
        "A",
        4,
        "X",
        "A_a6b410a44c449443",
        "Q_d01c5582258746a7",
        "1e1a3bb4a16ac2592a8fe8e72ee6d943f2257f87e4cfc8dfbac4534315e94fef",
    ),
    (
        5,
        "B",
        1,
        "D",
        "A_4c5f5a302b77395a",
        "Q_d5e1d40fbdddf363",
        "1c3eb3971d4c6e5f418b6e3ff40c9d02177812d2307a140367d82c581c66279a",
    ),
    (
        6,
        "B",
        2,
        "X",
        "A_8c46e16cbc877b13",
        "Q_d01c5582258746a7",
        "1e1a3bb4a16ac2592a8fe8e72ee6d943f2257f87e4cfc8dfbac4534315e94fef",
    ),
    (
        7,
        "B",
        3,
        "C",
        "A_256e156a33fa6895",
        "Q_9c19934ca3e89315",
        "cd79b48764fcf316a794dd43d854308cfbfb45895adccd405ba64340e6a35b05",
    ),
    (
        8,
        "B",
        4,
        "Z",
        "A_fbb3e5ecef6097ca",
        "Q_164a956eb63d7d9f",
        "ffa986deea3af1c9e63d5633e407c86e81b70b0a29b7eb2401be91f08197995a",
    ),
)

SELECTED_CLOSURES = (
    "K_8027291974",
    "K_265e97f857",
    "K_265e97f857",
    "K_265e97f857",
    "K_265e97f857",
    "K_265e97f857",
    "K_8027291974",
    "K_265e97f857",
)
PROVIDER_OUTPUT_FINGERPRINTS = (
    "1a2d7fced411d4b2a569b06b4a562de4c93c8c95936a86f704085391d38e2554",
    "06895e87e2a5de2e5df1ec1988fc17f4868c9716ee6cb0833aa9c3222b546ec8",
    "a478602aa3c8de291be5c97bc4a4b263e86dfa5b77aee41cc765901de1982e7a",
    "c3e02f461a0c0f8ee887115e783bf8f925f66c351ba030afda2ff78e3b2e89ce",
    "a478602aa3c8de291be5c97bc4a4b263e86dfa5b77aee41cc765901de1982e7a",
    "c3e02f461a0c0f8ee887115e783bf8f925f66c351ba030afda2ff78e3b2e89ce",
    "1a2d7fced411d4b2a569b06b4a562de4c93c8c95936a86f704085391d38e2554",
    "06895e87e2a5de2e5df1ec1988fc17f4868c9716ee6cb0833aa9c3222b546ec8",
)
COMPILED_OUTPUT_FINGERPRINTS = (
    "1b9410c7dffe008871df324c507451e488bf68ef4496780aa672beb3585b1256",
    "84df3dde3b6d53fb376e75eb2a86dc61142879ac635b9aada512254d3a642880",
    "dafe466ae6194c4d4019e8a5ccb497f8f9b709e123b217b836d9953dbed8f460",
    "59da7866b9ffabfbca0ef41961f6c8632703d918dec03b37e9c9338e9dd10e5b",
    "dafe466ae6194c4d4019e8a5ccb497f8f9b709e123b217b836d9953dbed8f460",
    "59da7866b9ffabfbca0ef41961f6c8632703d918dec03b37e9c9338e9dd10e5b",
    "1b9410c7dffe008871df324c507451e488bf68ef4496780aa672beb3585b1256",
    "84df3dde3b6d53fb376e75eb2a86dc61142879ac635b9aada512254d3a642880",
)

RESULT_SCHEMA = "ebrt-actuator-uptake-replication-live-result-v0.6.3.2-r01"
CALL_SCHEMA = "ebrt-actuator-uptake-replication-live-call-v0.6.3.2-r01"
JOURNAL_SCHEMA = "ebrt-actuator-uptake-replication-live-journal-v0.6.3.2-r01"
INPUTS_SCHEMA = "ebrt-actuator-uptake-replication-live-inputs-v0.6.3.2-r01"
MANIFEST_SCHEMA = "ebrt-actuator-uptake-replication-live-manifest-v0.6.3.2-r01"
PROJECTION_SCHEMA = "ebrt-actuator-uptake-projection-v0.6.3.2"
PROVIDER_INPUT_SCHEMA = "ebrt-actuator-uptake-provider-input-v0.6.3.1"
PROVIDER_OUTPUT_SCHEMA = "ebrt-actuator-uptake-provider-output-v0.6.3.1"
COMPILED_SCHEMA = "ebrt-actuator-uptake-compiled-output-v0.6.3.2"
CHECKPOINT = "orbital_manifest_revision_f:post_event"

CASE_ID = "orbital_manifest_revision_f"
TARGET_CLOSURE = "K_265e97f857"
QUALITY_VALID = frozenset({"K_265e97f857", "K_8027291974"})
CLOSURE_ROLES = {
    "K_16b90151c4": "STALE_INVALIDATED_SUPPORT",
    "K_265e97f857": "ALIGNED_EVENT_CONSISTENT",
    "K_8027291974": "ALTERNATIVE_EVENT_CONSISTENT",
    "K_fff6ffe598": "MIXED_INSUFFICIENT_SUPPORT",
}
BLOCK_CLAIM_BOUNDARY = [
    "A directional block is necessary but insufficient for aggregate replication.",
    "This per-block classification cannot open v0.6.4 by itself.",
]
AGGREGATE_CLAIM_BOUNDARY = [
    "Only two directional complete blocks open a v0.6.4 network-zero preflight.",
    "No result in this namespace authorizes live v0.6.4 execution.",
    "selected_closure_id is primary; inspection-receipt adherence is secondary and absent from this gate.",
]

FORBIDDEN_PROVIDER_METADATA = frozenset(
    {
        "anti_placement",
        "arm",
        "arm_id",
        "block",
        "block_id",
        "closure_roles",
        "controller",
        "correct_answer",
        "expected_answer",
        "gold",
        "grade",
        "gradient",
        "gradient_target_closure_id",
        "local_controller",
        "path_blocks",
        "positive_control_target_closure_id",
        "preferred_path",
        "quality_valid_closure_ids",
        "replicate",
        "replicate_id",
        "sequence_index",
        "sham",
        "target_closure",
        "target_closure_id",
        "treatment",
        "treatment_id",
        "within_block_index",
    }
)
FORBIDDEN_SECRET_MARKERS = (b"OPENAI_API_KEY", b"sk-proj-", b"sk-live-")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class VerificationError(RuntimeError):
    """The artifact or policy lock violates the frozen public contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def _reject_constant(value: str) -> Any:
    raise VerificationError(f"non-finite JSON constant: {value}")


def _finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise VerificationError(f"non-finite JSON number: {value}")
    return parsed


def _reject_duplicates(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise VerificationError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def _assert_finite(value: Any, label: str) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise VerificationError(f"non-finite value: {label}")
    if isinstance(value, Mapping):
        for child in value.values():
            _assert_finite(child, label)
    elif isinstance(value, list):
        for child in value:
            _assert_finite(child, label)


def _load_json(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            parse_constant=_reject_constant,
            parse_float=_finite_float,
            object_pairs_hook=_reject_duplicates,
        )
    except VerificationError:
        raise
    except Exception as error:
        raise VerificationError(f"invalid JSON: {label}") from error
    _require(isinstance(value, dict), f"JSON root is not an object: {label}")
    _assert_finite(value, label)
    return value


def _canonical_bytes(value: Any, *, newline: bool = False) -> bytes:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return raw + (b"\n" if newline else b"")


def _pretty_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _fingerprint(value: Any) -> str:
    return _sha256(_canonical_bytes(value))


def _without_fingerprint(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key != "fingerprint_sha256"
    }


def _seal_for_test(value: Mapping[str, Any]) -> dict[str, Any]:
    material = _without_fingerprint(value)
    material["fingerprint_sha256"] = _fingerprint(material)
    return material


def _assert_sealed(value: Mapping[str, Any], label: str) -> None:
    _require(
        value.get("fingerprint_sha256") == _fingerprint(_without_fingerprint(value)),
        f"fingerprint differs: {label}",
    )


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def _recursive_keys(value: Any) -> Iterable[str]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield key
            yield from _recursive_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _recursive_keys(child)


def _load_jsonl(raw: bytes, label: str) -> list[dict[str, Any]]:
    _require(
        bool(raw) and raw.endswith(b"\n"), f"JSONL lacks trailing newline: {label}"
    )
    rows = [
        _load_json(line, f"{label}:{index}")
        for index, line in enumerate(raw.splitlines(), start=1)
    ]
    _require(
        raw == b"".join(_canonical_bytes(row, newline=True) for row in rows),
        f"JSONL is noncanonical: {label}",
    )
    return rows


def _read_artifact_files(directory: Path) -> dict[str, bytes]:
    _require(
        not directory.is_symlink() and directory.is_dir(),
        "artifact directory is unavailable or a symlink",
    )
    paths = list(directory.rglob("*"))
    _require(
        all(
            path.is_file() and not path.is_symlink() and path.parent == directory
            for path in paths
        ),
        "artifact contains a symlink or nested entry",
    )
    _require(
        len(paths) == len(EXPECTED_FILES)
        and {path.name for path in paths} == set(EXPECTED_FILES),
        "artifact file set differs",
    )
    return {name: (directory / name).read_bytes() for name in EXPECTED_FILES}


def _parse_bundle(files: Mapping[str, bytes]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for name in (
        "result.json",
        "manifest.json",
        "provider_inputs.json",
        "projection_bundle.json",
    ):
        value = _load_json(files[name], name)
        _require(files[name] == _pretty_bytes(value), f"JSON is noncanonical: {name}")
        parsed[name] = value
    parsed["calls.jsonl"] = _load_jsonl(files["calls.jsonl"], "calls.jsonl")
    parsed["attempt_journal.jsonl"] = _load_jsonl(
        files["attempt_journal.jsonl"], "attempt_journal.jsonl"
    )
    return parsed


def _public_schedule() -> list[dict[str, Any]]:
    return [
        {
            "sequence_index": sequence,
            "block_id": block,
            "within_block_index": within,
            "blinded_attempt_id": attempt_id,
            "blinded_request_id": request_id,
            "treatment_id": arm,
            "provider_payload_fingerprint_sha256": payload_fp,
        }
        for sequence, block, within, arm, attempt_id, request_id, payload_fp in SCHEDULE
    ]


def _projection_schedule() -> list[dict[str, Any]]:
    return [
        {
            **{
                key: value
                for key, value in row.items()
                if key != "provider_payload_fingerprint_sha256"
            },
            "payload_fingerprint_sha256": row["provider_payload_fingerprint_sha256"],
        }
        for row in _public_schedule()
    ]


def _attempt_identity(row: Sequence[Any]) -> dict[str, Any]:
    sequence, block, within, arm, attempt_id, request_id, _payload_fp = row
    return {
        "sequence_index": sequence,
        "block_id": block,
        "within_block_index": within,
        "blinded_attempt_id": attempt_id,
        "blinded_request_id": request_id,
        "treatment_id": arm,
    }


def _expected_source_snapshot(lock: Mapping[str, Any]) -> dict[str, str]:
    return {
        label: receipt["sha256"]
        for label, receipt in lock["sources"].items()
        if label != "post_call_gold"
    }


def _load_lock(path: Path) -> tuple[dict[str, Any], bytes]:
    _require(not path.is_symlink() and path.is_file(), "policy lock unavailable")
    raw = path.read_bytes()
    lock = _load_json(raw, "policy lock")
    _require(raw == _pretty_bytes(lock), "policy lock JSON is noncanonical")
    _assert_sealed(lock, "policy lock")
    _require(
        len(raw) == EXPECTED_LOCK_BYTES
        and _sha256(raw) == EXPECTED_LOCK_SHA256
        and lock.get("fingerprint_sha256") == EXPECTED_LOCK_FINGERPRINT,
        "policy lock differs from frozen bytes",
    )
    execution = lock.get("execution", {})
    _require(
        lock.get("schema_version")
        == "ebrt-actuator-uptake-replication-live-policy-v0.6.3.2-r01"
        and execution.get("authorization_tag") == "v0.6.3.2-live-r01-authorized"
        and execution.get("execution_order") == list(EXECUTION_ORDER)
        and execution.get("block_schedules")
        == {block: list(BLOCK_SCHEDULES[block]) for block in BLOCK_IDS}
        and execution.get("call_schedule") == _public_schedule()
        and execution.get("exact_attempt_count") == 8
        and execution.get("provider_payload_count") == 4
        and execution.get("provider_calls_authorized") == 8
        and all(
            execution.get(key) is True
            for key in (
                "no_retry",
                "no_resume",
                "no_reorder",
                "no_backfill",
                "no_tiebreak_or_ninth_call",
            )
        )
        and execution.get("v0_6_4_live_execution_authorized") is False,
        "policy lock execution contract differs",
    )
    anchor = lock.get("preflight_anchor", {})
    _require(
        anchor.get("tag_object") == EXPECTED_PREFLIGHT_TAG_OBJECT
        and anchor.get("commit") == EXPECTED_PREFLIGHT_COMMIT
        and anchor.get("projection_fingerprint_sha256")
        == EXPECTED_PROJECTION_FINGERPRINT,
        "policy lock preflight anchor differs",
    )
    sources = lock.get("sources")
    _require(
        isinstance(sources, Mapping) and len(sources) == 14, "lock source set differs"
    )
    for label, receipt in sources.items():
        _require(
            isinstance(receipt, Mapping)
            and set(receipt) == {"path", "bytes", "sha256"}
            and isinstance(receipt["path"], str)
            and type(receipt["bytes"]) is int
            and receipt["bytes"] >= 0
            and _is_sha256(receipt["sha256"]),
            f"lock source receipt differs: {label}",
        )
    return lock, raw


def _validate_manifest_receipts(
    files: Mapping[str, bytes], manifest: Mapping[str, Any]
) -> None:
    _assert_sealed(manifest, "manifest")
    non_manifest = set(EXPECTED_FILES) - {"manifest.json"}
    _require(
        set(manifest)
        == {
            "schema_version",
            "status",
            "attempt_block_status",
            "assessment_status",
            "terminal_decision",
            "policy_lock_fingerprint_sha256",
            "result_fingerprint_sha256",
            "source_snapshot_sha256",
            "artifacts",
            "claim_boundary",
            "fingerprint_sha256",
        }
        and manifest.get("schema_version") == MANIFEST_SCHEMA
        and set(manifest.get("artifacts", {})) == non_manifest,
        "manifest schema differs",
    )
    for name in non_manifest:
        _require(
            manifest["artifacts"][name]
            == {"bytes": len(files[name]), "sha256": _sha256(files[name])},
            f"manifest receipt differs: {name}",
        )


def _validate_projection(projection: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    _assert_sealed(projection, "projection")
    _require(
        projection.get("schema_version") == PROJECTION_SCHEMA
        and projection.get("fingerprint_sha256") == EXPECTED_PROJECTION_FINGERPRINT
        and projection.get("case_id") == CASE_ID
        and projection.get("operator") == "evidence_permutation"
        and projection.get("execution_order") == list(EXECUTION_ORDER)
        and projection.get("block_schedules")
        == {block: list(BLOCK_SCHEDULES[block]) for block in BLOCK_IDS}
        and projection.get("execution_schedule") == _projection_schedule()
        and projection.get("scheduled_call_count") == 8
        and projection.get("provider_payload_count") == 4
        and projection.get("provider_calls_authorized") == 0
        and projection.get("provider_calls_observed") == 0
        and projection.get("gold_used_for_projection") is False
        and projection.get("gold_load_count_after_release") == 1
        and projection.get("gold_release_condition")
        == "AFTER_EIGHT_STRUCTURALLY_VALID_TERMINALS"
        and projection.get("reviewed_evidence_ids_primary") is False
        and projection.get("primary_public_action_field") == "selected_closure_id"
        and projection.get("status") == "READY_ZERO_CALL_PREFLIGHT_ONLY",
        "projection top-level contract differs",
    )
    rows = projection.get("provider_payloads")
    key = projection.get("public_treatment_key")
    _require(
        isinstance(rows, list) and len(rows) == 4, "projection payload catalog differs"
    )
    _require(
        isinstance(key, list) and len(key) == 4, "projection treatment key differs"
    )
    arm_by_request: dict[str, str] = {}
    for item in key:
        _require(
            isinstance(item, Mapping)
            and set(item) == {"blinded_request_id", "treatment_id"}
            and item["treatment_id"] in ARMS,
            "projection treatment row differs",
        )
        arm_by_request[str(item["blinded_request_id"])] = str(item["treatment_id"])
    _require(
        len(arm_by_request) == 4 and set(arm_by_request.values()) == set(ARMS),
        "projection treatment mapping differs",
    )
    expected_arm_by_request = {row[5]: row[3] for row in SCHEDULE}
    _require(
        arm_by_request == expected_arm_by_request,
        "projection treatment/request binding differs",
    )

    expected_request_to_fp = {row[5]: row[6] for row in SCHEDULE}
    catalog: dict[str, dict[str, Any]] = {}
    baseline_without_order: dict[str, Any] | None = None
    baseline_evidence: dict[str, str] | None = None
    for row in rows:
        _require(
            isinstance(row, Mapping) and set(row) == {"blinded_request_id", "payload"},
            "projection payload row schema differs",
        )
        request_id = str(row["blinded_request_id"])
        payload = row["payload"]
        _require(
            request_id in expected_request_to_fp and isinstance(payload, Mapping),
            "projection payload identity differs",
        )
        _assert_sealed(payload, f"projection payload {request_id}")
        _require(
            payload.get("fingerprint_sha256") == expected_request_to_fp[request_id],
            "projection payload fingerprint differs",
        )
        raw = _without_fingerprint(payload)
        _require(
            not (set(_recursive_keys(raw)) & FORBIDDEN_PROVIDER_METADATA),
            "projection exposes treatment metadata",
        )
        _require(
            raw.get("schema_version") == PROVIDER_INPUT_SCHEMA
            and raw.get("checkpoint_id") == CHECKPOINT
            and raw.get("answer_choices") == ["SILVER", "JADE"]
            and raw.get("record_format_choices") == ["ATTESTED_CBOR"],
            "provider payload contract differs",
        )
        evidence = raw.get("ordered_raw_evidence")
        _require(
            isinstance(evidence, list) and len(evidence) == 7,
            "provider evidence list differs",
        )
        evidence_map = {
            item.get("evidence_id"): item.get("text")
            for item in evidence
            if isinstance(item, Mapping) and set(item) == {"evidence_id", "text"}
        }
        _require(len(evidence_map) == 7, "provider evidence is duplicate or malformed")
        without_order = copy.deepcopy(raw)
        without_order.pop("ordered_raw_evidence")
        if baseline_without_order is None:
            baseline_without_order = without_order
            baseline_evidence = evidence_map
        else:
            _require(
                without_order == baseline_without_order
                and evidence_map == baseline_evidence,
                "payloads differ beyond evidence order",
            )
        catalog[request_id] = dict(payload)
    _require(
        set(catalog) == set(expected_request_to_fp),
        "projection payload request set differs",
    )
    return catalog


def _validate_provider_inputs(
    value: Mapping[str, Any], projection_catalog: Mapping[str, Mapping[str, Any]]
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    _assert_sealed(value, "provider inputs")
    _require(
        set(value)
        == {
            "schema_version",
            "projection_fingerprint_sha256",
            "execution_order",
            "provider_payload_count",
            "scheduled_attempt_count",
            "provider_payload_catalog",
            "execution_schedule",
            "provider_received_unsealed_payload_only",
            "fingerprint_sha256",
        }
        and value.get("schema_version") == INPUTS_SCHEMA
        and value.get("fingerprint_sha256") == EXPECTED_PROVIDER_INPUTS_FINGERPRINT
        and value.get("projection_fingerprint_sha256")
        == EXPECTED_PROJECTION_FINGERPRINT
        and value.get("execution_order") == list(EXECUTION_ORDER)
        and value.get("provider_payload_count") == 4
        and value.get("scheduled_attempt_count") == 8
        and value.get("execution_schedule") == _public_schedule()
        and value.get("provider_received_unsealed_payload_only") is True,
        "provider-input artifact contract differs",
    )
    rows = value.get("provider_payload_catalog")
    _require(
        isinstance(rows, list) and len(rows) == 4, "provider-input catalog differs"
    )
    catalog: dict[str, dict[str, Any]] = {}
    for row in rows:
        _require(
            isinstance(row, Mapping)
            and set(row)
            == {
                "blinded_request_id",
                "provider_payload_fingerprint_sha256",
                "sealed_payload",
            },
            "provider-input row schema differs",
        )
        request_id = str(row["blinded_request_id"])
        sealed = row["sealed_payload"]
        _require(
            request_id in projection_catalog
            and sealed == projection_catalog[request_id]
            and row["provider_payload_fingerprint_sha256"]
            == sealed["fingerprint_sha256"],
            "provider-input/projection payload binding differs",
        )
        _assert_sealed(sealed, f"provider input {request_id}")
        _require(
            _fingerprint(_without_fingerprint(sealed)) == sealed["fingerprint_sha256"]
            and not (
                set(_recursive_keys(_without_fingerprint(sealed)))
                & FORBIDDEN_PROVIDER_METADATA
            ),
            "provider-visible payload differs",
        )
        catalog[request_id] = dict(sealed)
    _require(
        set(catalog) == set(projection_catalog), "provider-input request set differs"
    )

    schedule = value["execution_schedule"]
    attempts = [row["blinded_attempt_id"] for row in schedule]
    requests = [row["blinded_request_id"] for row in schedule]
    _require(len(set(attempts)) == 8, "attempt IDs are not unique")
    _require(
        len(set(requests)) == 4
        and all(requests.count(request_id) == 2 for request_id in set(requests)),
        "four payload identities are not each reused twice",
    )
    for request_id in set(requests):
        bound = [row for row in schedule if row["blinded_request_id"] == request_id]
        _require(
            {row["block_id"] for row in bound} == {"A", "B"}
            and len({row["treatment_id"] for row in bound}) == 1
            and len({row["provider_payload_fingerprint_sha256"] for row in bound}) == 1,
            "request identity was rebound across mirrored blocks",
        )
    return catalog, [dict(row) for row in schedule]


def _validate_receipt(
    receipt: Mapping[str, Any], raw_payload: Mapping[str, Any], lock: Mapping[str, Any]
) -> None:
    _require(
        set(receipt)
        == {
            "provider",
            "requested_model",
            "returned_model",
            "logical_calls",
            "api_calls",
            "latency_ms",
            "request_fingerprint",
            "prompt_fingerprint",
            "usage",
            "metadata",
        },
        "provider receipt schema differs",
    )
    runtime = lock["runtime"]
    raw_fp = _fingerprint(raw_payload)
    _require(
        receipt.get("provider") == "openai_responses"
        and receipt.get("requested_model") == runtime["model"]
        and receipt.get("returned_model") == runtime["model"]
        and type(receipt.get("logical_calls")) is int
        and receipt.get("logical_calls") == 1
        and type(receipt.get("api_calls")) is int
        and receipt.get("api_calls") == 1
        and receipt.get("request_fingerprint") == raw_fp
        and receipt.get("prompt_fingerprint") == lock["instructions_fingerprint_sha256"]
        and isinstance(receipt.get("latency_ms"), (int, float))
        and not isinstance(receipt.get("latency_ms"), bool)
        and math.isfinite(float(receipt["latency_ms"]))
        and float(receipt["latency_ms"]) >= 0.0,
        "provider receipt binding differs",
    )
    metadata = receipt["metadata"]
    metadata_keys = {
        "receipt_schema_version",
        "status",
        "service_tier",
        "response_id_sha256",
        "server_request_id_sha256",
        "client_request_id_sha256",
        "provider_body_sha256",
        "provider_body_byte_count",
        "http_observed",
        "http_status_code",
        "parse_boundary",
        "failure_phase",
        "failure_reason_code",
        "failure_type",
        "response_schema_fingerprint",
        "semantic_protocol_fingerprint",
        "reasoning_effort",
        "max_output_tokens",
        "store",
        "previous_response_id",
        "truncation",
        "sdk_version",
        "pydantic_version",
        "python_version",
        "attempt",
        "retry_count",
        "api_call_count_semantics",
        "attempt_outcome",
        "refusal_count",
    }
    semantic_protocol = _fingerprint(
        {
            "model": runtime["model"],
            "instructions_fingerprint": lock["instructions_fingerprint_sha256"],
            "input_fingerprint": raw_fp,
            "text_schema_fingerprint": lock["response_schema_fingerprint_sha256"],
            "reasoning": {"effort": runtime["reasoning_effort"]},
            "max_output_tokens": runtime["max_output_tokens"],
            "store": runtime["store"],
            "service_tier": runtime["service_tier"],
            "truncation": runtime["truncation"],
            "timeout_seconds": float(runtime["timeout_seconds"]),
        }
    )
    _require(
        isinstance(metadata, Mapping)
        and set(metadata) == metadata_keys
        and metadata.get("receipt_schema_version")
        == "ebrt-provider-boundary-receipt-v0.4.3"
        and metadata.get("status") == "completed"
        and metadata.get("service_tier") == runtime["service_tier"]
        and metadata.get("http_observed") is True
        and metadata.get("http_status_code") == 200
        and metadata.get("parse_boundary") == "succeeded"
        and metadata.get("failure_phase") is None
        and metadata.get("failure_reason_code") is None
        and metadata.get("failure_type") is None
        and metadata.get("reasoning_effort") == runtime["reasoning_effort"]
        and metadata.get("max_output_tokens") == runtime["max_output_tokens"]
        and metadata.get("store") is False
        and metadata.get("previous_response_id") is False
        and metadata.get("truncation") == "disabled"
        and metadata.get("sdk_version") == runtime["openai_sdk"]
        and metadata.get("pydantic_version") == runtime["pydantic"]
        and metadata.get("python_version") == runtime["python"]
        and metadata.get("attempt") == 1
        and metadata.get("retry_count") == 0
        and metadata.get("api_call_count_semantics") == "attempted_client_call"
        and metadata.get("attempt_outcome") == "completed"
        and metadata.get("refusal_count") == 0
        and metadata.get("response_schema_fingerprint")
        == lock["response_schema_fingerprint_sha256"]
        and metadata.get("semantic_protocol_fingerprint") == semantic_protocol
        and all(
            _is_sha256(metadata.get(key))
            for key in (
                "client_request_id_sha256",
                "response_id_sha256",
                "server_request_id_sha256",
                "provider_body_sha256",
            )
        )
        and type(metadata.get("provider_body_byte_count")) is int
        and metadata["provider_body_byte_count"] > 0,
        "completed provider receipt differs",
    )
    usage = receipt["usage"]
    token_keys = {
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cached_input_tokens",
        "cache_write_tokens",
        "reasoning_tokens",
    }
    _require(
        isinstance(usage, Mapping)
        and set(usage) == token_keys | {"exact_provider_tokens"}
        and usage.get("exact_provider_tokens") is True
        and all(type(usage.get(key)) is int and usage[key] >= 0 for key in token_keys)
        and usage["total_tokens"] == usage["input_tokens"] + usage["output_tokens"]
        and usage["cached_input_tokens"] <= usage["input_tokens"]
        and usage["reasoning_tokens"] <= usage["output_tokens"],
        "provider usage differs",
    )


def _expected_graph(selected: list[str]) -> dict[str, Any]:
    edges: list[dict[str, str]] = []
    for evidence_id in selected:
        if evidence_id == "N7":
            edges.append(
                {
                    "edge_id": "STABLE_N7",
                    "relation_type": "supports",
                    "source_node_id": "N7",
                    "target_node_id": "PUBLIC_RECORD_FORMAT",
                }
            )
        else:
            edges.append(
                {
                    "edge_id": f"SUPPORT_{evidence_id}",
                    "relation_type": "supports",
                    "source_node_id": evidence_id,
                    "target_node_id": "PUBLIC_DECISION",
                }
            )
    if "N6" in selected:
        edges.append(
            {
                "edge_id": "INVALIDATES_N6_N5",
                "relation_type": "invalidates",
                "source_node_id": "N6",
                "target_node_id": "N5",
            }
        )
    nodes = list(selected)
    if "N6" in selected and "N5" not in nodes:
        nodes.append("N5")
    nodes.extend(["PUBLIC_DECISION", "PUBLIC_RECORD_FORMAT"])
    return {"nodes": nodes, "edges": edges}


def _validate_output_and_compiled(
    output: Mapping[str, Any],
    compiled: Mapping[str, Any],
    sealed_payload: Mapping[str, Any],
    *,
    position: int,
) -> None:
    raw = _without_fingerprint(sealed_payload)
    order = [row["evidence_id"] for row in raw["ordered_raw_evidence"]]
    catalog = {
        row["closure_id"]: row["selected_evidence_ids"]
        for row in raw["candidate_closures"]
    }
    _require(
        set(output)
        == {
            "schema_version",
            "checkpoint_id",
            "selected_closure_id",
            "reviewed_evidence_ids",
            "current_answer",
            "record_format",
        }
        and output.get("schema_version") == PROVIDER_OUTPUT_SCHEMA
        and output.get("checkpoint_id") == CHECKPOINT
        and output.get("selected_closure_id") == SELECTED_CLOSURES[position - 1]
        and output.get("selected_closure_id") in catalog
        and output.get("reviewed_evidence_ids") == order[:3]
        and output.get("current_answer") == "JADE"
        and output.get("record_format") == "ATTESTED_CBOR"
        and _fingerprint(output) == PROVIDER_OUTPUT_FINGERPRINTS[position - 1],
        f"provider public output differs at position {position}",
    )
    selected = list(catalog[output["selected_closure_id"]])
    checks = {
        "late_event_selected": "N6" in selected,
        "invalidated_evidence_absent": "N5" not in selected,
        "stable_evidence_preserved": "N7" in selected,
    }
    expected_without_fp = {
        "schema_version": COMPILED_SCHEMA,
        "checkpoint_id": CHECKPOINT,
        "provider_payload_fingerprint_sha256": sealed_payload["fingerprint_sha256"],
        "provider_output_fingerprint_sha256": _fingerprint(output),
        "selected_closure_id": output["selected_closure_id"],
        "selected_evidence_ids": selected,
        "current_answer": output["current_answer"],
        "record_format": output["record_format"],
        "expanded_public_graph": _expected_graph(selected),
        "inspection_receipt": {
            "reviewed_evidence_ids": output["reviewed_evidence_ids"],
            "expected_first_three_evidence_ids": order[:3],
            "adherence": output["reviewed_evidence_ids"] == order[:3],
            "scored_as_primary_uptake": False,
        },
        "public_contract_checks": checks,
    }
    expected = dict(expected_without_fp)
    expected["fingerprint_sha256"] = _fingerprint(expected_without_fp)
    _require(
        compiled == expected
        and compiled.get("fingerprint_sha256")
        == COMPILED_OUTPUT_FINGERPRINTS[position - 1],
        f"compiled public output differs at position {position}",
    )


def _usage_summary(attempts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    token_keys = (
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cached_input_tokens",
        "cache_write_tokens",
        "reasoning_tokens",
    )
    return {
        "logical_calls": sum(row["receipt"]["logical_calls"] for row in attempts),
        "api_calls": sum(row["receipt"]["api_calls"] for row in attempts),
        "latency_ms": sum(row["receipt"]["latency_ms"] for row in attempts),
        "exact_provider_tokens": True,
        **{
            key: sum(row["receipt"]["usage"][key] for row in attempts)
            for key in token_keys
        },
    }


def _validate_execution(
    result: Mapping[str, Any],
    payloads: Mapping[str, Mapping[str, Any]],
    calls: Sequence[Mapping[str, Any]],
    journal: Sequence[Mapping[str, Any]],
    lock: Mapping[str, Any],
) -> None:
    execution = result.get("execution")
    _require(
        isinstance(execution, Mapping)
        and set(execution)
        == {
            "attempts",
            "provider_outputs",
            "compiled_outputs",
            "attempt_block_status",
            "assessment_status",
            "invalid_blinded_attempt_ids",
            "unattempted_blinded_attempt_ids",
        },
        "execution schema differs",
    )
    attempts = execution["attempts"]
    outputs = execution["provider_outputs"]
    compiled = execution["compiled_outputs"]
    attempt_ids = [row[4] for row in SCHEDULE]
    _require(
        isinstance(attempts, list)
        and len(attempts) == 8
        and isinstance(outputs, Mapping)
        and isinstance(compiled, Mapping)
        and set(outputs) == set(attempt_ids)
        and set(compiled) == set(attempt_ids)
        and execution["attempt_block_status"] == "COMPLETE_EXACT_EIGHT_TERMINALS"
        and execution["assessment_status"] == "READY_FOR_POST_CALL_GOLD"
        and execution["invalid_blinded_attempt_ids"] == []
        and execution["unattempted_blinded_attempt_ids"] == []
        and len(calls) == 8
        and len(journal) == 16,
        "eight-attempt assessed execution differs",
    )
    _require(len(set(attempt_ids)) == 8, "frozen attempt IDs collide")
    request_bindings: dict[str, list[str]] = {}
    for position, (scheduled, attempt) in enumerate(
        zip(SCHEDULE, attempts, strict=True), start=1
    ):
        sequence, block, within, arm, attempt_id, request_id, payload_fp = scheduled
        request_bindings.setdefault(request_id, []).append(attempt_id)
        _require(
            set(attempt)
            == {
                "sequence_index",
                "block_id",
                "within_block_index",
                "blinded_attempt_id",
                "blinded_request_id",
                "treatment_id",
                "provider_input_fingerprint_sha256",
                "provider_output_fingerprint_sha256",
                "compiled_output_fingerprint_sha256",
                "receipt",
                "failure",
                "status",
            }
            and {key: attempt[key] for key in _attempt_identity(scheduled)}
            == _attempt_identity(scheduled)
            and attempt["provider_input_fingerprint_sha256"] == payload_fp
            and attempt["provider_output_fingerprint_sha256"]
            == PROVIDER_OUTPUT_FINGERPRINTS[position - 1]
            and attempt["compiled_output_fingerprint_sha256"]
            == COMPILED_OUTPUT_FINGERPRINTS[position - 1]
            and attempt["failure"] is None
            and attempt["status"] == "COMPLETED",
            f"terminal attempt differs at position {position}",
        )
        sealed = payloads[request_id]
        _validate_receipt(attempt["receipt"], _without_fingerprint(sealed), lock)
        output = outputs[attempt_id]
        compiled_output = compiled[attempt_id]
        _validate_output_and_compiled(
            output, compiled_output, sealed, position=position
        )
        expected_call = {
            "schema_version": CALL_SCHEMA,
            **_attempt_identity(scheduled),
            "status": "COMPLETED",
            "failure": None,
            "receipt": attempt["receipt"],
        }
        _require(
            calls[position - 1] == expected_call, f"call ledger differs at {position}"
        )
        expected_start = {
            "schema_version": JOURNAL_SCHEMA,
            "event": "ATTEMPT_STARTED",
            **_attempt_identity(scheduled),
            "provider_input_fingerprint_sha256": payload_fp,
        }
        expected_terminal = {
            "schema_version": JOURNAL_SCHEMA,
            "event": "ATTEMPT_TERMINAL",
            "attempt": attempt,
            "provider_output": output,
            "compiled_output": compiled_output,
        }
        _require(
            journal[(position - 1) * 2] == expected_start
            and journal[(position - 1) * 2 + 1] == expected_terminal,
            f"attempt journal differs at position {position}",
        )
    _require(
        len(request_bindings) == 4
        and all(
            len(ids) == 2 and len(set(ids)) == 2 for ids in request_bindings.values()
        ),
        "request/attempt reuse geometry differs",
    )
    _require(result.get("usage") == _usage_summary(attempts), "aggregate usage differs")


def _validate_preflight(result: Mapping[str, Any], lock: Mapping[str, Any]) -> None:
    preflight = result.get("preflight")
    _require(isinstance(preflight, Mapping), "preflight record missing")
    _assert_sealed(preflight, "preflight")
    authorization = preflight.get("execution_authorization")
    expected_authorization = {
        "status": "AUTHORIZED_ANNOTATED_TAG",
        "tag_name": "v0.6.3.2-live-r01-authorized",
        "tag_object": EXPECTED_AUTHORIZATION_TAG_OBJECT,
        "authorized_commit": EXPECTED_AUTHORIZED_COMMIT,
        "execution_head_commit": EXPECTED_AUTHORIZED_COMMIT,
        "head_matches_authorized_commit": True,
        "provenance_scope": "OPERATOR_ATTESTED_NOT_CRYPTOGRAPHICALLY_AUTHENTICATED",
    }
    component = preflight.get("component_self_test")
    _require(isinstance(component, Mapping), "component self-test missing")
    _assert_sealed(component, "component self-test")
    expected_provider = {
        **copy.deepcopy(lock["runtime"]),
        "instructions_fingerprint_sha256": lock["instructions_fingerprint_sha256"],
        "response_schema_fingerprint_sha256": lock[
            "response_schema_fingerprint_sha256"
        ],
        "receipt_schema_version": "ebrt-provider-boundary-receipt-v0.4.3",
    }
    payload_map = {row[5]: row[6] for row in SCHEDULE}
    _require(
        preflight.get("schema_version")
        == "ebrt-actuator-uptake-replication-live-preflight-v0.6.3.2-r01"
        and preflight.get("status") == "READY_EXACT_EIGHT_CALL_MIRRORED_LIVE_BLOCK"
        and preflight.get("expected_api_attempts") == 8
        and preflight.get("execution_order") == list(EXECUTION_ORDER)
        and preflight.get("call_order_blinded_attempt_ids")
        == [row[4] for row in SCHEDULE]
        and preflight.get("execution_schedule") == _public_schedule()
        and preflight.get("payload_fingerprints_by_request") == payload_map
        and preflight.get("projection_fingerprint_sha256")
        == EXPECTED_PROJECTION_FINGERPRINT
        and preflight.get("policy_lock_fingerprint_sha256") == EXPECTED_LOCK_FINGERPRINT
        and preflight.get("provider") == expected_provider
        and authorization == expected_authorization
        and preflight.get("source_snapshot_sha256") == _expected_source_snapshot(lock)
        and preflight.get("post_call_gold_expected_receipt")
        == lock["sources"]["post_call_gold"]
        and preflight.get("gold_loaded") is False
        and preflight.get("provider_calls") == 0
        and preflight.get("network_calls") == 0
        and component.get("status") == "PASS_NETWORK_ZERO"
        and component.get("provider_calls") == 0
        and component.get("network_calls") == 0
        and component.get("simulated_api_calls") == 90
        and isinstance(component.get("checks"), Mapping)
        and len(component["checks"]) == 14
        and all(value is True for value in component["checks"].values()),
        "preflight or authorization record differs",
    )


def _classify_block(selected: Mapping[str, str]) -> tuple[str, str, str]:
    _require(set(selected) == set(ARMS), "classifier arm set differs")
    _require(
        all(value in CLOSURE_ROLES for value in selected.values()), "unknown closure"
    )
    z_id, c_id, d_id, x_id = (selected[arm] for arm in ("Z", "C", "D", "X"))
    if z_id == TARGET_CLOSURE and x_id == TARGET_CLOSURE:
        positive = "POSITIVE_CONTROL_CEILING"
    elif z_id != TARGET_CLOSURE and x_id == TARGET_CLOSURE:
        positive = "CHANNEL_OPEN_DIRECTIONAL"
    elif z_id == x_id:
        positive = "ACTUATOR_CHANNEL_INERT"
    elif z_id == TARGET_CLOSURE and x_id != TARGET_CLOSURE:
        positive = "CHANNEL_OPEN_ADVERSE"
    else:
        positive = "CHANNEL_OPEN_DIRECTION_AMBIGUOUS"

    if c_id == TARGET_CLOSURE and d_id == TARGET_CLOSURE:
        placement = "D_C_TARGET_CEILING"
    elif d_id == TARGET_CLOSURE and c_id != TARGET_CLOSURE:
        placement = "GRADIENT_PLACEMENT_DIRECTIONAL"
    elif c_id == d_id:
        placement = "GRADIENT_PLACEMENT_NULL"
    elif c_id == TARGET_CLOSURE and d_id != TARGET_CLOSURE:
        placement = "GRADIENT_PLACEMENT_ADVERSE"
    else:
        placement = "GRADIENT_PLACEMENT_AMBIGUOUS"

    if (
        positive == "CHANNEL_OPEN_DIRECTIONAL"
        and placement == "GRADIENT_PLACEMENT_DIRECTIONAL"
    ):
        terminal = "BLOCK_DIRECTIONAL"
    elif positive == "POSITIVE_CONTROL_CEILING":
        terminal = "STOP_POSITIVE_CONTROL_CEILING_NOT_ASSESSED"
    elif positive == "ACTUATOR_CHANNEL_INERT":
        terminal = "STOP_CHANNEL_INERT"
    elif positive == "CHANNEL_OPEN_DIRECTION_AMBIGUOUS":
        terminal = "STOP_CHANNEL_AMBIGUOUS"
    elif positive == "CHANNEL_OPEN_ADVERSE":
        terminal = "STOP_CHANNEL_ADVERSE"
    elif placement == "D_C_TARGET_CEILING":
        terminal = "STOP_PLACEMENT_CEILING_NOT_ASSESSED"
    elif placement == "GRADIENT_PLACEMENT_NULL":
        terminal = "STOP_PLACEMENT_NULL"
    elif placement == "GRADIENT_PLACEMENT_AMBIGUOUS":
        terminal = "STOP_PLACEMENT_AMBIGUOUS"
    else:
        terminal = "STOP_PLACEMENT_ADVERSE"
    return positive, placement, terminal


def _aggregate_contrast(statuses: Sequence[str]) -> str:
    _require(len(statuses) == 2, "aggregate block count differs")
    directional = sum(status.endswith("DIRECTIONAL") for status in statuses)
    if directional == 2:
        return "REPLICATED_DIRECTIONAL"
    if directional == 1:
        return "MIXED"
    if statuses[0] != statuses[1]:
        return "HETEROGENEOUS_NON_DIRECTIONAL"
    suffix = {
        "POSITIVE_CONTROL_CEILING": "REPLICATED_CEILING",
        "ACTUATOR_CHANNEL_INERT": "REPLICATED_NULL",
        "CHANNEL_OPEN_ADVERSE": "REPLICATED_ADVERSE",
        "CHANNEL_OPEN_DIRECTION_AMBIGUOUS": "REPLICATED_AMBIGUOUS",
        "D_C_TARGET_CEILING": "REPLICATED_CEILING",
        "GRADIENT_PLACEMENT_NULL": "REPLICATED_NULL",
        "GRADIENT_PLACEMENT_ADVERSE": "REPLICATED_ADVERSE",
        "GRADIENT_PLACEMENT_AMBIGUOUS": "REPLICATED_AMBIGUOUS",
    }
    _require(statuses[0] in suffix, "aggregate status unknown")
    return suffix[statuses[0]]


def _aggregate_terminal(positive: str, placement: str) -> str:
    statuses = {positive, placement}
    if statuses == {"REPLICATED_DIRECTIONAL"}:
        return "REPLICATION_DIRECTIONAL_COUNTERBALANCED"
    if "MIXED" in statuses:
        return "STOP_REPLICATION_MIXED"
    if "REPLICATED_ADVERSE" in statuses:
        return "STOP_REPLICATION_ADVERSE"
    if statuses & {"REPLICATED_AMBIGUOUS", "HETEROGENEOUS_NON_DIRECTIONAL"}:
        return "STOP_REPLICATION_AMBIGUOUS"
    if "REPLICATED_CEILING" in statuses:
        return "STOP_REPLICATION_CEILING_NOT_ASSESSED"
    return "STOP_REPLICATION_NULL"


def _endpoint(compiled: Mapping[str, Any]) -> dict[str, Any]:
    closure_id = str(compiled["selected_closure_id"])
    role = CLOSURE_ROLES[closure_id]
    quality_valid = closure_id in QUALITY_VALID
    expected_answer = (
        "JADE"
        if role in {"ALIGNED_EVENT_CONSISTENT", "ALTERNATIVE_EVENT_CONSISTENT"}
        else None
    )
    answer_trace = (
        "NOT_ASSESSED"
        if expected_answer is None
        else "PASS"
        if compiled["current_answer"] == expected_answer
        else "FAIL"
    )
    checks = {
        "answer": compiled["current_answer"] == "JADE",
        "record_format": compiled["record_format"] == "ATTESTED_CBOR",
        "quality_valid_closure": quality_valid,
        "late_event_selected": bool(
            compiled["public_contract_checks"]["late_event_selected"]
        ),
        "invalidated_evidence_absent": bool(
            compiled["public_contract_checks"]["invalidated_evidence_absent"]
        ),
        "stable_evidence_preserved": bool(
            compiled["public_contract_checks"]["stable_evidence_preserved"]
        ),
    }
    material = {
        "schema_version": "ebrt-actuator-uptake-endpoint-v0.6.3.2",
        "case_id": CASE_ID,
        "selected_closure_id": closure_id,
        "closure_role": role,
        "is_positive_control_target": closure_id == TARGET_CLOSURE,
        "is_gradient_target": closure_id == TARGET_CLOSURE,
        "event_complete_score": 1 if quality_valid else 0,
        "gradient_alignment_score": {
            "ALIGNED_EVENT_CONSISTENT": 1,
            "ALTERNATIVE_EVENT_CONSISTENT": -1,
            "STALE_INVALIDATED_SUPPORT": 0,
            "MIXED_INSUFFICIENT_SUPPORT": 0,
        }[role],
        "answer_trace_status": answer_trace,
        "quality_status": "PASS" if all(checks.values()) else "FAIL",
        "quality_checks": checks,
        "secondary_quality_only": True,
        "compiled_output_fingerprint_sha256": compiled["fingerprint_sha256"],
        "provider_output_fingerprint_sha256": compiled[
            "provider_output_fingerprint_sha256"
        ],
        "provider_payload_fingerprint_sha256": compiled[
            "provider_payload_fingerprint_sha256"
        ],
    }
    material["fingerprint_sha256"] = _fingerprint(material)
    return material


def _reconstruct_decision(result: Mapping[str, Any]) -> dict[str, Any]:
    execution = result["execution"]
    compiled = execution["compiled_outputs"]
    block_decisions: dict[str, dict[str, Any]] = {}
    for block_id in BLOCK_IDS:
        rows = [row for row in execution["attempts"] if row["block_id"] == block_id]
        selected = {
            row["treatment_id"]: compiled[row["blinded_attempt_id"]][
                "selected_closure_id"
            ]
            for row in rows
        }
        endpoints = {
            row["treatment_id"]: _endpoint(compiled[row["blinded_attempt_id"]])
            for row in rows
        }
        positive, placement, terminal = _classify_block(selected)
        material = {
            "schema_version": "ebrt-actuator-uptake-decision-v0.6.3.2",
            "block_id": block_id,
            "assessment_status": "ASSESSED",
            "positive_control_status": positive,
            "gradient_placement_status": placement,
            "terminal_decision": terminal,
            "selected_closure_by_arm": {arm: selected[arm] for arm in ARMS},
            "endpoint_fingerprint_by_arm": {
                arm: endpoints[arm]["fingerprint_sha256"] for arm in ARMS
            },
            "invalid_arms": [],
            "direct_v0_6_4_promotion_allowed": False,
            "claim_boundary": BLOCK_CLAIM_BOUNDARY,
        }
        material["fingerprint_sha256"] = _fingerprint(material)
        block_decisions[block_id] = material
    positive = _aggregate_contrast(
        [block_decisions[block]["positive_control_status"] for block in BLOCK_IDS]
    )
    placement = _aggregate_contrast(
        [block_decisions[block]["gradient_placement_status"] for block in BLOCK_IDS]
    )
    terminal = _aggregate_terminal(positive, placement)
    material = {
        "schema_version": "ebrt-actuator-uptake-replication-decision-v0.6.3.2",
        "assessment_status": "ASSESSED",
        "positive_control_replication_status": positive,
        "gradient_placement_replication_status": placement,
        "terminal_decision": terminal,
        "incomplete_blocks": [],
        "block_decisions": block_decisions,
        "v0_6_4_network_zero_preflight_opened": terminal
        == "REPLICATION_DIRECTIONAL_COUNTERBALANCED",
        "v0_6_4_live_execution_authorized": False,
        "claim_boundary": AGGREGATE_CLAIM_BOUNDARY,
    }
    material["fingerprint_sha256"] = _fingerprint(material)
    return material


def _validate_decision(result: Mapping[str, Any]) -> dict[str, Any]:
    decision = result.get("decision")
    _require(isinstance(decision, Mapping), "decision missing")
    _assert_sealed(decision, "decision")
    expected = _reconstruct_decision(result)
    _require(decision == expected, "decision differs from independent reconstruction")
    _require(
        decision["positive_control_replication_status"] == "REPLICATED_CEILING"
        and decision["gradient_placement_replication_status"]
        == "REPLICATED_DIRECTIONAL"
        and decision["terminal_decision"] == "STOP_REPLICATION_CEILING_NOT_ASSESSED"
        and decision["v0_6_4_network_zero_preflight_opened"] is False,
        "frozen assessed ceiling branch differs",
    )
    return expected


def _report(result: Mapping[str, Any]) -> bytes:
    lines = [
        "# EBRT v0.6.3.2 live-r01",
        "",
        f"- Attempt block: `{result['execution']['attempt_block_status']}`",
        f"- Assessment: `{result['decision']['assessment_status']}`",
        f"- Terminal decision: `{result['decision']['terminal_decision']}`",
        f"- Calls: `{result['usage']['api_calls']}/8`",
        f"- Gold loaded: `{str(result['semantic_gold']['loaded']).lower()}`",
        "",
        "## Public outputs",
        "",
        "| Position | Block | Arm | Attempt | Status | Closure |",
        "|---:|---|---|---|---|---|",
    ]
    outputs = result["execution"]["provider_outputs"]
    for attempt in result["execution"]["attempts"]:
        output = outputs.get(attempt["blinded_attempt_id"], {})
        lines.append(
            "| {position} | {block} | {arm} | {attempt_id} | {status} | {closure} |".format(
                position=attempt["sequence_index"],
                block=attempt["block_id"],
                arm=attempt["treatment_id"],
                attempt_id=attempt["blinded_attempt_id"],
                status=attempt["status"],
                closure=output.get("selected_closure_id", "—"),
            )
        )
    lines.extend(
        ["", "## Boundary", "", *[f"- {item}" for item in result["claim_boundary"]], ""]
    )
    return "\n".join(lines).encode("utf-8")


def _validate_result_links(
    files: Mapping[str, bytes],
    result: Mapping[str, Any],
    manifest: Mapping[str, Any],
    projection: Mapping[str, Any],
    lock: Mapping[str, Any],
) -> None:
    _assert_sealed(result, "result")
    _require(
        set(result)
        == {
            "schema_version",
            "mode",
            "claim_boundary",
            "preflight_anchor_tag_object",
            "preflight_anchor_commit",
            "policy_lock_fingerprint_sha256",
            "projection_fingerprint_sha256",
            "preflight",
            "source_snapshot_sha256",
            "execution",
            "semantic_gold",
            "decision",
            "v0_6_4_live_execution_authorized",
            "usage",
            "fingerprint_sha256",
        }
        and result.get("schema_version") == RESULT_SCHEMA
        and result.get("mode") == "openai_live_actuator_uptake_replication_v0_6_3_2_r01"
        and result.get("claim_boundary") == lock.get("claim_boundary")
        and result.get("preflight_anchor_tag_object") == EXPECTED_PREFLIGHT_TAG_OBJECT
        and result.get("preflight_anchor_commit") == EXPECTED_PREFLIGHT_COMMIT
        and result.get("policy_lock_fingerprint_sha256") == EXPECTED_LOCK_FINGERPRINT
        and result.get("projection_fingerprint_sha256")
        == EXPECTED_PROJECTION_FINGERPRINT
        and result.get("source_snapshot_sha256") == _expected_source_snapshot(lock)
        and result.get("v0_6_4_live_execution_authorized") is False
        and result.get("fingerprint_sha256") == EXPECTED_RESULT_FINGERPRINT,
        "result top-level links differ",
    )
    _require(
        result.get("semantic_gold")
        == {
            "loaded": True,
            "classification_load_count": 1,
            "observed_receipt": lock["sources"]["post_call_gold"],
        },
        "post-call gold barrier record differs",
    )
    _require(
        files["report.md"] == _report(result), "report/result relationship differs"
    )
    _require(
        manifest.get("status") == "SEALED_LIVE_RESULT"
        and manifest.get("attempt_block_status")
        == result["execution"]["attempt_block_status"]
        and manifest.get("assessment_status") == result["decision"]["assessment_status"]
        and manifest.get("terminal_decision") == result["decision"]["terminal_decision"]
        and manifest.get("policy_lock_fingerprint_sha256")
        == result["policy_lock_fingerprint_sha256"]
        and manifest.get("result_fingerprint_sha256") == result["fingerprint_sha256"]
        and manifest.get("source_snapshot_sha256") == result["source_snapshot_sha256"]
        and manifest.get("claim_boundary") == result["claim_boundary"]
        and projection.get("fingerprint_sha256")
        == result["projection_fingerprint_sha256"],
        "manifest/report/result links differ",
    )


def _validate_frozen_receipts(files: Mapping[str, bytes]) -> None:
    for name, (expected_bytes, expected_sha) in EXPECTED_FILES.items():
        _require(
            len(files[name]) == expected_bytes and _sha256(files[name]) == expected_sha,
            f"frozen byte receipt differs: {name}",
        )


def _validate_no_secrets(files: Mapping[str, bytes]) -> None:
    for name, raw in files.items():
        _require(
            not any(marker in raw for marker in FORBIDDEN_SECRET_MARKERS),
            f"secret marker retained: {name}",
        )


def verify(directory: Path, lock_path: Path = DEFAULT_LOCK) -> dict[str, Any]:
    """Validate a copied frozen artifact and return a compact public summary."""

    files = _read_artifact_files(directory)
    lock, _ = _load_lock(lock_path)
    parsed = _parse_bundle(files)
    result = parsed["result.json"]
    manifest = parsed["manifest.json"]
    projection = parsed["projection_bundle.json"]
    inputs = parsed["provider_inputs.json"]
    _validate_no_secrets(files)
    _validate_manifest_receipts(files, manifest)
    projection_catalog = _validate_projection(projection)
    payloads, _schedule = _validate_provider_inputs(inputs, projection_catalog)
    _validate_preflight(result, lock)
    _validate_execution(
        result, payloads, parsed["calls.jsonl"], parsed["attempt_journal.jsonl"], lock
    )
    decision = _validate_decision(result)
    _validate_result_links(files, result, manifest, projection, lock)
    _require(
        manifest.get("fingerprint_sha256") == EXPECTED_MANIFEST_FINGERPRINT,
        "manifest fingerprint differs from frozen result",
    )
    _validate_frozen_receipts(files)
    return {
        "status": "VALID_FROZEN_EIGHT_CALL_MIRRORED_RESULT",
        "artifact_directory": str(directory),
        "authorization_tag_object": EXPECTED_AUTHORIZATION_TAG_OBJECT,
        "authorized_commit": EXPECTED_AUTHORIZED_COMMIT,
        "execution_order": list(EXECUTION_ORDER),
        "attempt_count": 8,
        "provider_payload_count": 4,
        "api_calls": result["usage"]["api_calls"],
        "selected_closure_by_block": {
            block: decision["block_decisions"][block]["selected_closure_by_arm"]
            for block in BLOCK_IDS
        },
        "positive_control_replication_status": decision[
            "positive_control_replication_status"
        ],
        "gradient_placement_replication_status": decision[
            "gradient_placement_replication_status"
        ],
        "terminal_decision": decision["terminal_decision"],
        "v0_6_4_network_zero_preflight_opened": decision[
            "v0_6_4_network_zero_preflight_opened"
        ],
        "v0_6_4_live_execution_authorized": False,
        "gold_loaded_after_eight_terminals": result["semantic_gold"]["loaded"],
        "result_fingerprint_sha256": EXPECTED_RESULT_FINGERPRINT,
        "manifest_fingerprint_sha256": EXPECTED_MANIFEST_FINGERPRINT,
        "network_calls": 0,
        "provider_calls_made_by_verifier": 0,
    }


def _write_pretty(path: Path, value: Mapping[str, Any]) -> None:
    path.write_bytes(_pretty_bytes(value))


def _load_path(path: Path) -> dict[str, Any]:
    return _load_json(path.read_bytes(), path.name)


def _refresh_manifest(directory: Path) -> None:
    result = _load_path(directory / "result.json")
    manifest = _load_path(directory / "manifest.json")
    material = _without_fingerprint(manifest)
    material["attempt_block_status"] = result["execution"]["attempt_block_status"]
    material["assessment_status"] = result["decision"]["assessment_status"]
    material["terminal_decision"] = result["decision"]["terminal_decision"]
    material["result_fingerprint_sha256"] = result["fingerprint_sha256"]
    material["source_snapshot_sha256"] = result["source_snapshot_sha256"]
    material["claim_boundary"] = result["claim_boundary"]
    material["artifacts"] = {
        name: {
            "bytes": len((directory / name).read_bytes()),
            "sha256": _sha256((directory / name).read_bytes()),
        }
        for name in EXPECTED_FILES
        if name != "manifest.json"
    }
    _write_pretty(directory / "manifest.json", _seal_for_test(material))


def _rewrite_result(
    directory: Path, result: Mapping[str, Any], *, report: bool = False
) -> None:
    sealed = _seal_for_test(result)
    _write_pretty(directory / "result.json", sealed)
    if report:
        (directory / "report.md").write_bytes(_report(sealed))
    _refresh_manifest(directory)


def _rewrite_json_artifact(
    directory: Path, name: str, value: Mapping[str, Any]
) -> None:
    _write_pretty(directory / name, _seal_for_test(value))
    _refresh_manifest(directory)


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.write_bytes(b"".join(_canonical_bytes(row, newline=True) for row in rows))


def _expect_rejected(operation: Callable[[], Any], label: str) -> None:
    try:
        operation()
    except VerificationError:
        return
    raise VerificationError(f"self-test tamper was accepted: {label}")


def _copy_fixture(root: Path, name: str) -> tuple[Path, Path]:
    case_root = root / name
    artifact = case_root / "artifact"
    artifact.mkdir(parents=True)
    for filename in EXPECTED_FILES:
        shutil.copyfile(DEFAULT_ARTIFACT / filename, artifact / filename)
    lock = case_root / "policy_lock.json"
    shutil.copyfile(DEFAULT_LOCK, lock)
    return artifact, lock


def _classifier_exhaustive_check() -> dict[str, int]:
    closure_ids = tuple(CLOSURE_ROLES)
    block_pairs: list[tuple[str, str]] = []
    directional = 0
    for z_id in closure_ids:
        for c_id in closure_ids:
            for d_id in closure_ids:
                for x_id in closure_ids:
                    positive, placement, terminal = _classify_block(
                        {"Z": z_id, "C": c_id, "D": d_id, "X": x_id}
                    )
                    block_pairs.append((positive, placement))
                    directional += terminal == "BLOCK_DIRECTIONAL"
    _require(
        len(block_pairs) == 256 and directional == 9,
        "per-block classifier space differs",
    )
    aggregate_success = 0
    for left in block_pairs:
        for right in block_pairs:
            positive = _aggregate_contrast((left[0], right[0]))
            placement = _aggregate_contrast((left[1], right[1]))
            success = (
                _aggregate_terminal(positive, placement)
                == "REPLICATION_DIRECTIONAL_COUNTERBALANCED"
            )
            strict = left == (
                "CHANNEL_OPEN_DIRECTIONAL",
                "GRADIENT_PLACEMENT_DIRECTIONAL",
            ) and right == (
                "CHANNEL_OPEN_DIRECTIONAL",
                "GRADIENT_PLACEMENT_DIRECTIONAL",
            )
            _require(success == strict, "aggregate classifier escaped strict AND gate")
            aggregate_success += success
    _require(
        aggregate_success == 81, "aggregate classifier success cardinality differs"
    )
    return {
        "per_block_combinations": 256,
        "per_block_directional": directional,
        "aggregate_block_pairs": 65536,
        "aggregate_directional": aggregate_success,
    }


def self_test() -> dict[str, Any]:
    checks: dict[str, bool] = {}
    classifier = _classifier_exhaustive_check()
    with tempfile.TemporaryDirectory(prefix="ebrt-v0632-result-verifier-") as raw_root:
        root = Path(raw_root)

        artifact, lock = _copy_fixture(root, "foreign-root")
        copied_verifier = root / "foreign-root" / Path(__file__).name
        shutil.copyfile(Path(__file__), copied_verifier)
        completed = subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                str(copied_verifier),
                "verify",
                "--artifact-dir",
                str(artifact),
                "--lock-path",
                str(lock),
            ],
            cwd=root / "foreign-root",
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        _require(
            completed.returncode == 0,
            f"foreign-root isolated verification failed: {completed.stderr}",
        )
        checks["foreign_root_python_I_S_pass"] = True

        artifact, lock = _copy_fixture(root, "extra")
        (artifact / "extra.json").write_bytes(b"{}\n")
        _expect_rejected(lambda: verify(artifact, lock), "extra file")
        checks["extra_file_rejected"] = True

        artifact, lock = _copy_fixture(root, "missing")
        (artifact / "report.md").unlink()
        _expect_rejected(lambda: verify(artifact, lock), "missing file")
        checks["missing_file_rejected"] = True

        artifact, lock = _copy_fixture(root, "symlink")
        (artifact / "report.md").unlink()
        (artifact / "report.md").symlink_to(artifact / "result.json")
        _expect_rejected(lambda: verify(artifact, lock), "symlink")
        checks["symlink_rejected"] = True

        artifact, lock = _copy_fixture(root, "byte-tamper")
        (artifact / "report.md").write_bytes(
            (artifact / "report.md").read_bytes() + b" "
        )
        _expect_rejected(lambda: verify(artifact, lock), "byte tamper")
        checks["byte_tamper_rejected"] = True

        artifact, lock = _copy_fixture(root, "schedule-tamper")
        inputs = _load_path(artifact / "provider_inputs.json")
        inputs["execution_schedule"][0], inputs["execution_schedule"][1] = (
            inputs["execution_schedule"][1],
            inputs["execution_schedule"][0],
        )
        _rewrite_json_artifact(artifact, "provider_inputs.json", inputs)
        _expect_rejected(lambda: verify(artifact, lock), "schedule tamper")
        checks["schedule_tamper_rejected"] = True

        artifact, lock = _copy_fixture(root, "journal-reorder")
        rows = _load_jsonl((artifact / "attempt_journal.jsonl").read_bytes(), "journal")
        rows[0], rows[1] = rows[1], rows[0]
        _write_jsonl(artifact / "attempt_journal.jsonl", rows)
        _refresh_manifest(artifact)
        _expect_rejected(lambda: verify(artifact, lock), "journal reorder")
        checks["journal_reorder_rejected"] = True

        artifact, lock = _copy_fixture(root, "attempt-collision")
        result = _load_path(artifact / "result.json")
        result["execution"]["attempts"][1]["blinded_attempt_id"] = result["execution"][
            "attempts"
        ][0]["blinded_attempt_id"]
        _rewrite_result(artifact, result)
        _expect_rejected(lambda: verify(artifact, lock), "attempt collision")
        checks["attempt_collision_rejected"] = True

        artifact, lock = _copy_fixture(root, "request-rebinding")
        result = _load_path(artifact / "result.json")
        result["execution"]["attempts"][4]["blinded_request_id"] = SCHEDULE[0][5]
        _rewrite_result(artifact, result)
        _expect_rejected(lambda: verify(artifact, lock), "request rebinding")
        checks["request_rebinding_rejected"] = True

        artifact, lock = _copy_fixture(root, "authorization-tamper")
        result = _load_path(artifact / "result.json")
        preflight = copy.deepcopy(result["preflight"])
        preflight["execution_authorization"]["tag_object"] = "0" * 40
        result["preflight"] = _seal_for_test(preflight)
        _rewrite_result(artifact, result)
        _expect_rejected(lambda: verify(artifact, lock), "authorization tamper")
        checks["authorization_tamper_rejected"] = True

        artifact, lock = _copy_fixture(root, "usage-tamper")
        result = _load_path(artifact / "result.json")
        result["usage"]["api_calls"] = 9
        _rewrite_result(artifact, result)
        _expect_rejected(lambda: verify(artifact, lock), "usage tamper")
        checks["usage_tamper_rejected"] = True

        artifact, lock = _copy_fixture(root, "early-gold")
        result = _load_path(artifact / "result.json")
        preflight = copy.deepcopy(result["preflight"])
        preflight["gold_loaded"] = True
        result["preflight"] = _seal_for_test(preflight)
        _rewrite_result(artifact, result)
        _expect_rejected(lambda: verify(artifact, lock), "early gold")
        checks["early_gold_rejected"] = True

        artifact, lock = _copy_fixture(root, "branch-flip")
        result = _load_path(artifact / "result.json")
        decision = copy.deepcopy(result["decision"])
        decision["positive_control_replication_status"] = "REPLICATED_DIRECTIONAL"
        decision["terminal_decision"] = "REPLICATION_DIRECTIONAL_COUNTERBALANCED"
        decision["v0_6_4_network_zero_preflight_opened"] = True
        result["decision"] = _seal_for_test(decision)
        _rewrite_result(artifact, result, report=True)
        _expect_rejected(lambda: verify(artifact, lock), "branch flip")
        checks["assessed_branch_flip_rejected"] = True

        artifact, lock = _copy_fixture(root, "coherent-reseal")
        result = _load_path(artifact / "result.json")
        decision = copy.deepcopy(result["decision"])
        decision["positive_control_replication_status"] = "REPLICATED_NULL"
        decision["gradient_placement_replication_status"] = "REPLICATED_NULL"
        decision["terminal_decision"] = "STOP_REPLICATION_NULL"
        result["decision"] = _seal_for_test(decision)
        _rewrite_result(artifact, result, report=True)
        _expect_rejected(lambda: verify(artifact, lock), "coherent reseal")
        checks["coherent_decision_reseal_rejected"] = True

        artifact, lock = _copy_fixture(root, "secret-injection")
        (artifact / "report.md").write_bytes(
            (artifact / "report.md").read_bytes() + b"OPENAI_API_KEY=sk-live-redacted\n"
        )
        _refresh_manifest(artifact)
        _expect_rejected(lambda: verify(artifact, lock), "secret injection")
        checks["secret_injection_rejected"] = True

    _expect_rejected(lambda: _load_json(b'{"x":1,"x":2}', "duplicate"), "duplicate key")
    checks["duplicate_key_rejected"] = True
    _expect_rejected(lambda: _load_json(b'{"x":1e999}', "nonfinite"), "non-finite")
    checks["nonfinite_number_rejected"] = True
    _require(all(checks.values()), "self-test did not close every gate")
    return {
        "status": "PASS_PORTABLE_FROZEN_RESULT_SELF_TEST",
        "checks": checks,
        "classifier_exhaustive": classifier,
        "check_count": len(checks),
        "network_calls": 0,
        "provider_calls": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify_parser = subparsers.add_parser("verify", help="verify the frozen result")
    verify_parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT)
    verify_parser.add_argument("--lock-path", type=Path, default=DEFAULT_LOCK)
    subparsers.add_parser("self-test", help="run network-zero tamper tests")
    args = parser.parse_args()
    if args.command == "verify":
        output = verify(args.artifact_dir, args.lock_path)
    else:
        output = self_test()
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
