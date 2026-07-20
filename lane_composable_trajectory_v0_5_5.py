#!/usr/bin/env python3
"""EBRT v0.5.5: network-zero composition of sealed public trajectories.

The module consumes the three byte-sealed v0.5.4 lane artifacts.  It does not
create agents, call a provider, route between lanes, or generate language.
The only merge is a typed keyed direct sum plus mechanically generated
same-terminal-axis incidence constraints.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import re
import socket
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterator, Mapping, Optional, Sequence
from unittest import mock

import torch

import temporal_adjoint_lineage_v0_5_4 as v054


ROOT = Path(__file__).resolve().parent
DEFAULT_FIXTURE = ROOT / "fixtures" / "lane_composition_v0_5_5.json"
DEFAULT_ONE_LANE_FIXTURE = (
    ROOT / "fixtures" / "lane_composition_v0_5_5_one_lane.json"
)
V054_ARTIFACT_DIR = ROOT / "artifacts" / "temporal_adjoint_lineage_v0_5_4"
V054_SELF_TEST_PATH = V054_ARTIFACT_DIR / "self_test.json"
V054_MANIFEST_PATH = V054_ARTIFACT_DIR / "manifest.json"
V053_REGRESSION_PATH = (
    ROOT / "artifacts" / "factorized_lineage_v0_5_3" / "factorized_lineage_regression.json"
)

FIXTURE_SCHEMA_VERSION = "ebrt-lane-composition-fixture-v0.5.5"
LEDGER_SCHEMA_VERSION = "ebrt-shared-evidence-ledger-v0.5.5"
RESULT_SCHEMA_VERSION = "ebrt-lane-composition-result-v0.5.5"
MERGE_SCHEMA_VERSION = "ebrt-typed-merge-contract-v0.5.5"
CONTROL_SCHEMA_VERSION = "ebrt-lane-control-bundle-v0.5.5"
BLOCK_AUDIT_SCHEMA_VERSION = "ebrt-block-adjoint-audit-v0.5.5"
SELF_TEST_SCHEMA_VERSION = "ebrt-lane-composition-self-test-v0.5.5"

MERGE_OPERATOR = "typed_keyed_direct_sum_exact_axis_incidence_v0_5_5"
PROMOTE_STATUS = "PROMOTE_V0_6_LANE_COMPOSITION_GATE"
STOP_STATUS = "STOP_V0_6_LANE_COMPOSITION_GATE"
FLOAT_DTYPE = torch.float64
FD_EPSILON = 1.0e-6
BLOCK_ABS_TOLERANCE = 2.0e-12
FD_ABS_TOLERANCE = 5.0e-8
MAX_LANES = 3
NAMESPACE_SEPARATOR = "::"

LANE_PATHS = {
    "correction_early": V054_ARTIFACT_DIR / "correction_early_sealed_lane.json",
    "correction_late": V054_ARTIFACT_DIR / "correction_late_sealed_lane.json",
    "stable_constraint": V054_ARTIFACT_DIR / "stable_constraint_sealed_lane.json",
}
EVENT_LANES = frozenset({"correction_early", "correction_late"})
STABLE_LANE_ID = "stable_constraint"
HARD_GATE_IDS = (
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

FORBIDDEN_SCHEMA_KEYS = frozenset(
    {
        "agent",
        "agents",
        "debate",
        "dynamic_router",
        "generation",
        "final_generation",
        "generated_text",
        "learned_arbiter",
        "live_provider",
        "memory",
        "model",
        "natural_language_generation",
        "prompt",
        "provider",
        "response",
        "retry",
        "routing",
        "router",
        "selection",
        "tool",
        "tools",
        "ui",
        "agent_spawning",
    }
)


class LaneCompositionValidationError(RuntimeError):
    """A strict v0.5.5 public-lane invariant failed."""


JsonObject = dict[str, Any]


def canonical_json_bytes(value: Any, *, trailing_newline: bool = False) -> bytes:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return encoded + (b"\n" if trailing_newline else b"")


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _clone(value: Any) -> Any:
    return json.loads(canonical_json_bytes(value))


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise LaneCompositionValidationError(
            f"{label} keys differ: missing={sorted(expected-set(value))}, "
            f"extra={sorted(set(value)-expected)}"
        )


def _reject_forbidden_schema_keys(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            lowered = key.lower()
            if lowered in FORBIDDEN_SCHEMA_KEYS:
                raise LaneCompositionValidationError(
                    f"forbidden orchestration key at {path}.{key}"
                )
            _reject_forbidden_schema_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_forbidden_schema_keys(child, f"{path}[{index}]")


def _strict_load_bytes(raw: bytes, *, label: str) -> JsonObject:
    def reject_constant(token: str) -> None:
        raise LaneCompositionValidationError(f"non-finite JSON constant: {token}")

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> JsonObject:
        output: JsonObject = {}
        for key, value in pairs:
            if key in output:
                raise LaneCompositionValidationError(
                    f"duplicate JSON key in {label}: {key}"
                )
            output[key] = value
        return output

    try:
        decoded = raw.decode("utf-8")
        value = json.loads(
            decoded,
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise LaneCompositionValidationError(f"invalid JSON for {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise LaneCompositionValidationError(f"{label} root must be object")
    return value


def _strict_load(path: Path) -> tuple[JsonObject, bytes]:
    if not path.is_file() or path.is_symlink():
        raise LaneCompositionValidationError(f"expected regular non-symlink file: {path}")
    raw = path.read_bytes()
    return _strict_load_bytes(raw, label=str(path)), raw


def validate_fixture(value: Mapping[str, Any]) -> None:
    if not isinstance(value, Mapping):
        raise LaneCompositionValidationError("fixture must be object")
    _reject_forbidden_schema_keys(value)
    _exact_keys(
        value,
        {
            "claim_boundary",
            "fixture_id",
            "junction",
            "lane_ids",
            "schema_version",
            "source_contract",
        },
        "fixture",
    )
    if value["schema_version"] != FIXTURE_SCHEMA_VERSION:
        raise LaneCompositionValidationError("fixture schema mismatch")
    if not isinstance(value["fixture_id"], str) or not value["fixture_id"]:
        raise LaneCompositionValidationError("fixture_id must be nonempty")
    claims = value["claim_boundary"]
    if not isinstance(claims, list) or not claims or not all(
        isinstance(row, str) and row for row in claims
    ):
        raise LaneCompositionValidationError("claim_boundary must be nonempty strings")
    lane_ids = value["lane_ids"]
    if not isinstance(lane_ids, list) or not all(isinstance(row, str) for row in lane_ids):
        raise LaneCompositionValidationError("lane_ids must be strings")
    if not 1 <= len(lane_ids) <= MAX_LANES:
        raise LaneCompositionValidationError("lane count must be between one and three")
    if len(set(lane_ids)) != len(lane_ids):
        raise LaneCompositionValidationError("duplicate lane IDs are forbidden")
    if any(row not in LANE_PATHS for row in lane_ids):
        raise LaneCompositionValidationError("fixture requests an undeclared sealed lane")
    expected_lane_ids = {
        "hackathon_strategy_lane_composition_v0_5_5": [
            "correction_early",
            "correction_late",
            "stable_constraint",
        ],
        "hackathon_strategy_lane_composition_one_lane_v0_5_5": [
            "correction_early"
        ],
    }.get(value["fixture_id"])
    if expected_lane_ids is None or lane_ids != expected_lane_ids:
        raise LaneCompositionValidationError(
            "fixture lane IDs/order must match the pinned fixture identity"
        )
    junction = value["junction"]
    if not isinstance(junction, Mapping):
        raise LaneCompositionValidationError("junction must be object")
    _exact_keys(junction, {"count", "operator"}, "fixture.junction")
    if junction["count"] != 1 or junction["operator"] != MERGE_OPERATOR:
        raise LaneCompositionValidationError("exactly one locked merge junction is required")
    source = value["source_contract"]
    if not isinstance(source, Mapping):
        raise LaneCompositionValidationError("source_contract must be object")
    _exact_keys(
        source,
        {
            "required_v0_5_4_decision_status",
            "required_v0_5_4_promotion_ready",
            "version",
        },
        "fixture.source_contract",
    )
    if dict(source) != {
        "required_v0_5_4_decision_status": "PROMOTE_V0_5_5_TEMPORAL_GATE",
        "required_v0_5_4_promotion_ready": True,
        "version": "v0.5.4",
    }:
        raise LaneCompositionValidationError("fixture source gate contract mismatch")


def load_fixture(path: Path = DEFAULT_FIXTURE) -> JsonObject:
    value, _raw = _strict_load(Path(path))
    validate_fixture(value)
    return _clone(value)


def _normalize_float(value: float) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise LaneCompositionValidationError("non-finite numeric publication")
    return 0.0 if number == 0.0 else number


def _tensor_values(value: torch.Tensor) -> list[Any]:
    def normalize(item: Any) -> Any:
        if isinstance(item, list):
            return [normalize(child) for child in item]
        return _normalize_float(float(item))

    return normalize(value.detach().cpu().tolist())


def _with_fingerprint(value: Mapping[str, Any]) -> JsonObject:
    output = _clone(value)
    output["fingerprint_sha256"] = fingerprint(output)
    return output


def _without_fingerprint(value: Mapping[str, Any]) -> JsonObject:
    output = _clone(value)
    output.pop("fingerprint_sha256", None)
    return output


def _validate_internal_fingerprint(value: Mapping[str, Any], label: str) -> None:
    observed = value.get("fingerprint_sha256")
    if not isinstance(observed, str) or observed != fingerprint(_without_fingerprint(value)):
        raise LaneCompositionValidationError(f"{label} internal fingerprint mismatch")


@dataclass(frozen=True)
class TerminalAxis:
    axis_id: str
    channel: str
    evidence_id: str
    target_node_id: str
    target_node_type: str
    target_value: float

    def to_dict(self) -> JsonObject:
        return {
            "axis_id": self.axis_id,
            "channel": self.channel,
            "evidence_id": self.evidence_id,
            "target_node_id": self.target_node_id,
            "target_node_type": self.target_node_type,
            "target_value": _normalize_float(self.target_value),
        }


@dataclass(frozen=True)
class LaneRuntime:
    lane_id: str
    source_path: Path
    source_bytes: bytes
    source_file_sha256: str
    source_manifest_sha256: str
    source_payload: JsonObject
    source_fingerprint_sha256: str
    axes: tuple[TerminalAxis, ...]
    target: torch.Tensor
    neutral_output: torch.Tensor
    program: Optional[v054.CompiledProgram]
    schedule_id: Optional[str]
    sites: tuple[JsonObject, ...]
    raw_jacobian: torch.Tensor
    scales: torch.Tensor
    normalized_jacobian: torch.Tensor
    rho: float
    evidence_bindings: tuple[JsonObject, ...]

    @property
    def control_count(self) -> int:
        return len(self.sites)


def _validate_v054_source_gate() -> JsonObject:
    self_test, self_test_raw = _strict_load(V054_SELF_TEST_PATH)
    manifest, manifest_raw = _strict_load(V054_MANIFEST_PATH)
    _validate_internal_fingerprint(self_test, "v0.5.4 self-test")
    if (
        self_test.get("schema_version") != v054.SELF_TEST_SCHEMA_VERSION
        or self_test.get("status") != "PASS"
        or self_test.get("promotion_ready") is not True
        or set(self_test.get("hard_gates", {})) != set(v054.HARD_GATE_IDS)
        or not all(self_test["hard_gates"].values())
    ):
        raise LaneCompositionValidationError("v0.5.4 self-test gate is not exact PASS")
    if (
        manifest.get("decision_status") != "PROMOTE_V0_5_5_TEMPORAL_GATE"
        or manifest.get("promotion_ready") is not True
        or manifest.get("provider_calls") != 0
        or manifest.get("network_calls") != 0
        or not all(manifest.get("hard_gates", {}).values())
    ):
        raise LaneCompositionValidationError("v0.5.4 manifest did not promote v0.5.5")
    artifact_rows = manifest.get("artifacts")
    if not isinstance(artifact_rows, Mapping):
        raise LaneCompositionValidationError("v0.5.4 manifest artifact table missing")
    for lane_id, path in LANE_PATHS.items():
        row = artifact_rows.get(path.name)
        if not isinstance(row, Mapping):
            raise LaneCompositionValidationError(f"v0.5.4 manifest missing {lane_id}")
        if row.get("sha256") != sha256_bytes(path.read_bytes()):
            raise LaneCompositionValidationError(f"v0.5.4 lane byte receipt drift: {lane_id}")
    payload = {
        "all_hard_gates_true": True,
        "decision_status": manifest["decision_status"],
        "manifest_file_sha256": sha256_bytes(manifest_raw),
        "network_calls": 0,
        "promotion_ready": True,
        "provider_calls": 0,
        "self_test_file_sha256": sha256_bytes(self_test_raw),
        "self_test_fingerprint_sha256": self_test["fingerprint_sha256"],
        "status": "PASS",
    }
    return _with_fingerprint(payload)


def _build_shared_evidence_ledger(program: v054.CompiledProgram) -> JsonObject:
    evidence_nodes = sorted(
        (row for row in program.graph["nodes"] if row["node_type"] == "evidence"),
        key=lambda row: row["temporal_ordinal"],
    )
    entries = [
        {
            "content_sha256": fingerprint(row),
            "evidence_id": row["evidence_id"],
            "node_payload": _clone(row),
        }
        for row in evidence_nodes
    ]
    invalidations = []
    node_by_id = {row["node_id"]: row for row in program.graph["nodes"]}
    for edge in sorted(program.graph["edges"], key=lambda row: row["edge_id"]):
        if edge["edge_type"] != "invalidates":
            continue
        invalidations.append(
            {
                "content_sha256": fingerprint(edge),
                "edge_payload": _clone(edge),
                "source_evidence_id": node_by_id[edge["source_node_id"]]["evidence_id"],
                "target_evidence_id": node_by_id[edge["target_node_id"]]["evidence_id"],
            }
        )
    payload = {
        "entries": entries,
        "graph_fingerprint_sha256": program.graph["fingerprint_sha256"],
        "invalidations": invalidations,
        "schema_version": LEDGER_SCHEMA_VERSION,
    }
    return _with_fingerprint(payload)


def _axis_id(channel: str, evidence_id: str, target_node_id: str) -> str:
    for value in (channel, evidence_id, target_node_id):
        if NAMESPACE_SEPARATOR in value:
            raise LaneCompositionValidationError("terminal axis contains namespace delimiter")
    return f"{channel}|{evidence_id}|{target_node_id}"


def _ledger_hashes(ledger: Mapping[str, Any]) -> dict[str, str]:
    validate_evidence_ledger(ledger)
    return {row["evidence_id"]: row["content_sha256"] for row in ledger["entries"]}


def validate_evidence_ledger(ledger: Mapping[str, Any]) -> None:
    if not isinstance(ledger, Mapping):
        raise LaneCompositionValidationError("evidence ledger must be object")
    _exact_keys(
        ledger,
        {
            "entries",
            "fingerprint_sha256",
            "graph_fingerprint_sha256",
            "invalidations",
            "schema_version",
        },
        "shared_evidence_ledger",
    )
    if ledger["schema_version"] != LEDGER_SCHEMA_VERSION:
        raise LaneCompositionValidationError("evidence ledger schema mismatch")
    if ledger["graph_fingerprint_sha256"] != v054.EXPECTED_V053_REPAIRED_GRAPH_FINGERPRINT:
        raise LaneCompositionValidationError("ledger source graph fingerprint drift")
    entries = ledger["entries"]
    invalidations = ledger["invalidations"]
    if not isinstance(entries, list) or not isinstance(invalidations, list):
        raise LaneCompositionValidationError("ledger entries/invalidations must be lists")
    ids: list[str] = []
    for index, row in enumerate(entries):
        if not isinstance(row, Mapping):
            raise LaneCompositionValidationError("ledger entry must be object")
        _exact_keys(row, {"content_sha256", "evidence_id", "node_payload"}, f"ledger.entries[{index}]")
        evidence_id = row["evidence_id"]
        node = row["node_payload"]
        if not isinstance(evidence_id, str) or not isinstance(node, Mapping):
            raise LaneCompositionValidationError("ledger entry identity malformed")
        if node.get("evidence_id") != evidence_id or node.get("node_type") != "evidence":
            raise LaneCompositionValidationError("ledger node payload identity mismatch")
        if row["content_sha256"] != fingerprint(node):
            raise LaneCompositionValidationError("ledger entry content hash mismatch")
        ids.append(evidence_id)
    if len(ids) != len(set(ids)) or ids != sorted(ids, key=lambda item: int(item[1:])):
        raise LaneCompositionValidationError("ledger Evidence IDs must be unique canonical R-order")
    if ids != ["R1", "R2", "R3", "R4", "R5", "R6"]:
        raise LaneCompositionValidationError("ledger must bind the exact frozen R1-R6 set")
    id_set = set(ids)
    node_to_evidence = {
        row["node_payload"]["node_id"]: row["evidence_id"] for row in entries
    }
    for index, row in enumerate(invalidations):
        if not isinstance(row, Mapping):
            raise LaneCompositionValidationError("ledger invalidation must be object")
        _exact_keys(
            row,
            {"content_sha256", "edge_payload", "source_evidence_id", "target_evidence_id"},
            f"ledger.invalidations[{index}]",
        )
        edge = row["edge_payload"]
        if not isinstance(edge, Mapping) or edge.get("edge_type") != "invalidates":
            raise LaneCompositionValidationError("ledger invalidation edge malformed")
        if row["content_sha256"] != fingerprint(edge):
            raise LaneCompositionValidationError("ledger invalidation hash mismatch")
        if row["source_evidence_id"] not in id_set or row["target_evidence_id"] not in id_set:
            raise LaneCompositionValidationError("ledger invalidation references missing Evidence")
        if (
            node_to_evidence.get(edge.get("source_node_id")) != row["source_evidence_id"]
            or node_to_evidence.get(edge.get("target_node_id")) != row["target_evidence_id"]
        ):
            raise LaneCompositionValidationError("ledger invalidation endpoint identity mismatch")
    if len(invalidations) != 1 or (
        invalidations[0]["source_evidence_id"],
        invalidations[0]["target_evidence_id"],
    ) != ("R6", "R3"):
        raise LaneCompositionValidationError("ledger must preserve exact R6 invalidates R3")
    if ledger["fingerprint_sha256"] != fingerprint(_without_fingerprint(ledger)):
        raise LaneCompositionValidationError("ledger fingerprint mismatch")


def _load_lane(
    lane_id: str,
    *,
    event_program: v054.CompiledProgram,
    stable_program: v054.CompiledProgram,
    ledger: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> LaneRuntime:
    path = LANE_PATHS[lane_id]
    payload, raw = _strict_load(path)
    if payload.get("schema_version") != v054.LANE_SCHEMA_VERSION:
        raise LaneCompositionValidationError(f"sealed lane schema drift: {lane_id}")
    _validate_internal_fingerprint(payload, f"sealed lane {lane_id}")
    if payload.get("lane_id") != lane_id or payload.get("status") != "PASS":
        raise LaneCompositionValidationError(f"sealed lane identity/status drift: {lane_id}")
    if payload.get("network_calls") != 0 or payload.get("provider_calls") != 0:
        raise LaneCompositionValidationError(f"sealed lane is not network-zero: {lane_id}")
    if NAMESPACE_SEPARATOR in lane_id or not re.fullmatch(r"[a-z][a-z0-9_]{0,31}", lane_id):
        raise LaneCompositionValidationError(f"unsafe lane namespace: {lane_id}")
    manifest_row = manifest["artifacts"][path.name]
    file_sha = sha256_bytes(raw)
    if manifest_row.get("sha256") != file_sha:
        raise LaneCompositionValidationError(f"sealed lane manifest mismatch: {lane_id}")
    ledger_by_id = _ledger_hashes(ledger)

    if lane_id in EVENT_LANES:
        program = event_program
        sites = tuple(_clone(row) for row in v054._site_rows(program, lane_id))
        zero = torch.zeros(len(sites), dtype=FLOAT_DTYPE)
        neutral_output, raw_jacobian = v054.manual_forward_jacobian(program, lane_id, zero)
        target = v054.terminal_target(program, neutral_output)
        if payload.get("terminal_axis_types") != ["fact"]:
            raise LaneCompositionValidationError("event lane must expose fact axes only")
        if payload.get("evidence_order") != list(program.schedules[lane_id]):
            raise LaneCompositionValidationError("sealed lane evidence schedule drift")
        if payload.get("neutral") != {
            "loss": float(0.5 * torch.dot(neutral_output - target, neutral_output - target)),
            "target": _tensor_values(target),
            "terminal_output": _tensor_values(neutral_output),
        }:
            raise LaneCompositionValidationError("sealed lane neutral receipt drift")
        axis_tuples = v054._terminal_axes(program)
        axes = tuple(
            TerminalAxis(
                axis_id=_axis_id(channel, evidence_id, target_node_id),
                channel=channel,
                evidence_id=evidence_id,
                target_node_id=target_node_id,
                target_node_type="fact",
                target_value=float(target[index]),
            )
            for index, (target_node_id, evidence_id, channel) in enumerate(axis_tuples)
        )
        scales = torch.linalg.vector_norm(raw_jacobian, dim=0)
        eligible = scales > 0.0
        normalized_jacobian = torch.zeros_like(raw_jacobian)
        normalized_jacobian[:, eligible] = raw_jacobian[:, eligible] / scales[eligible]
        rho = float(v054.RHO_FRACTION * torch.min(scales[eligible]))
        order = list(payload["evidence_order"])
        bindings = tuple(
            {
                "content_sha256": ledger_by_id[evidence_id],
                "evidence_id": evidence_id,
                "schedule_horizon": order.index(evidence_id) + 1,
            }
            for evidence_id in sorted(order)
        )
        schedule_id: Optional[str] = lane_id
    else:
        program = stable_program
        sites = ()
        neutral_output = torch.tensor(payload["stable_output"], dtype=FLOAT_DTYPE).reshape(-1)
        target = neutral_output.clone()
        raw_jacobian = torch.zeros((neutral_output.numel(), 0), dtype=FLOAT_DTYPE)
        scales = torch.zeros(0, dtype=FLOAT_DTYPE)
        normalized_jacobian = raw_jacobian.clone()
        rho = 0.0
        axis_rows = payload.get("terminal_axes")
        if not isinstance(axis_rows, list) or payload.get("terminal_axis_types") != ["constraint"]:
            raise LaneCompositionValidationError("stable lane axis contract drift")
        axes = tuple(
            TerminalAxis(
                axis_id=_axis_id(row["channel"], row["evidence_id"], row["target_node_id"]),
                channel=row["channel"],
                evidence_id=row["evidence_id"],
                target_node_id=row["target_node_id"],
                target_node_type="constraint",
                target_value=float(target[index]),
            )
            for index, row in enumerate(axis_rows)
        )
        bindings = tuple(
            {
                "content_sha256": ledger_by_id[evidence_id],
                "evidence_id": evidence_id,
                "schedule_horizon": None,
            }
            for evidence_id in sorted({row.evidence_id for row in axes})
        )
        schedule_id = None
    if len(axes) != neutral_output.numel() or len({row.axis_id for row in axes}) != len(axes):
        raise LaneCompositionValidationError(f"terminal axis cardinality drift: {lane_id}")
    return LaneRuntime(
        lane_id=lane_id,
        source_path=path,
        source_bytes=raw,
        source_file_sha256=file_sha,
        source_manifest_sha256=str(manifest_row["sha256"]),
        source_payload=_clone(payload),
        source_fingerprint_sha256=str(payload["fingerprint_sha256"]),
        axes=axes,
        target=target,
        neutral_output=neutral_output,
        program=program,
        schedule_id=schedule_id,
        sites=sites,
        raw_jacobian=raw_jacobian,
        scales=scales,
        normalized_jacobian=normalized_jacobian,
        rho=rho,
        evidence_bindings=bindings,
    )


def _validate_runtime_lanes(lanes: Sequence[LaneRuntime]) -> tuple[LaneRuntime, ...]:
    if not 1 <= len(lanes) <= MAX_LANES:
        raise LaneCompositionValidationError("runtime lane count must be one through three")
    ordered = tuple(sorted(lanes, key=lambda row: row.lane_id))
    ids = [row.lane_id for row in ordered]
    if len(set(ids)) != len(ids):
        raise LaneCompositionValidationError("runtime duplicate lane ID")
    if any(
        NAMESPACE_SEPARATOR in row
        or not re.fullmatch(r"[a-z][a-z0-9_]{0,31}", row)
        for row in ids
    ):
        raise LaneCompositionValidationError("runtime namespace collision")
    for lane in ordered:
        _validate_runtime_against_source(lane)
        actual_sha = sha256_bytes(lane.source_bytes)
        if actual_sha != lane.source_file_sha256 or actual_sha != lane.source_manifest_sha256:
            raise LaneCompositionValidationError("runtime sealed bytes do not match receipts")
        _validate_internal_fingerprint(lane.source_payload, "runtime sealed lane")
        if (
            lane.source_payload.get("lane_id") != lane.lane_id
            or lane.source_payload.get("fingerprint_sha256")
            != lane.source_fingerprint_sha256
        ):
            raise LaneCompositionValidationError("runtime sealed payload identity drift")
    byte_hashes = [sha256_bytes(row.source_bytes) for row in ordered]
    fingerprints = [str(row.source_payload["fingerprint_sha256"]) for row in ordered]
    if len(set(byte_hashes)) != len(byte_hashes) or len(set(fingerprints)) != len(fingerprints):
        raise LaneCompositionValidationError("duplicate sealed lane artifact under alias")
    namespaced: set[str] = set()
    for lane in ordered:
        for axis in lane.axes:
            if axis.axis_id != _axis_id(
                axis.channel, axis.evidence_id, axis.target_node_id
            ):
                raise LaneCompositionValidationError("terminal axis ID is not canonical")
            name = f"lane{NAMESPACE_SEPARATOR}{lane.lane_id}{NAMESPACE_SEPARATOR}{axis.axis_id}"
            if name in namespaced:
                raise LaneCompositionValidationError("namespaced terminal collision")
            namespaced.add(name)
        for site in lane.sites:
            local_id = str(site["site_id"])
            if NAMESPACE_SEPARATOR in local_id:
                raise LaneCompositionValidationError("local control ID contains delimiter")
            name = f"lane{NAMESPACE_SEPARATOR}{lane.lane_id}{NAMESPACE_SEPARATOR}{local_id}"
            if name in namespaced:
                raise LaneCompositionValidationError("namespaced control collision")
            namespaced.add(name)
    return ordered


def _program_exact(
    observed: Optional[v054.CompiledProgram], expected: v054.CompiledProgram
) -> bool:
    if observed is None:
        return False
    return (
        v054.program_receipt(observed) == v054.program_receipt(expected)
        and observed.incoming == expected.incoming
        and observed.node_index == expected.node_index
        and observed.evidence_index == expected.evidence_index
        and observed.positive_edges == expected.positive_edges
        and observed.invalidation_edges == expected.invalidation_edges
        and observed.sweep_order == expected.sweep_order
        and observed.schedules == expected.schedules
        and canonical_json_bytes(observed.graph) == canonical_json_bytes(expected.graph)
        and canonical_json_bytes(observed.closure) == canonical_json_bytes(expected.closure)
    )


def _validate_runtime_against_source(lane: LaneRuntime) -> None:
    if lane.lane_id not in LANE_PATHS or lane.source_path.resolve() != LANE_PATHS[
        lane.lane_id
    ].resolve():
        raise LaneCompositionValidationError("runtime lane source path is not pinned")
    if lane.source_bytes != lane.source_path.read_bytes():
        raise LaneCompositionValidationError("runtime lane bytes differ from pinned source")
    parsed = _strict_load_bytes(lane.source_bytes, label=f"runtime {lane.lane_id} bytes")
    if canonical_json_bytes(parsed) != canonical_json_bytes(lane.source_payload):
        raise LaneCompositionValidationError("runtime payload is decoupled from sealed bytes")
    _validate_internal_fingerprint(parsed, f"runtime sealed bytes {lane.lane_id}")
    if (
        parsed.get("lane_id") != lane.lane_id
        or parsed.get("fingerprint_sha256") != lane.source_fingerprint_sha256
        or sha256_bytes(lane.source_bytes) != lane.source_file_sha256
        or lane.source_manifest_sha256 != lane.source_file_sha256
    ):
        raise LaneCompositionValidationError("runtime sealed source identity mismatch")

    if lane.lane_id in EVENT_LANES:
        fixture = v054.load_fixture(v054.DEFAULT_EVENT_FIXTURE)
        program = v054.compile_program(fixture)
        expected_schedule: Optional[str] = lane.lane_id
        expected_sites = tuple(_clone(row) for row in v054._site_rows(program, lane.lane_id))
        zero = torch.zeros(len(expected_sites), dtype=FLOAT_DTYPE)
        neutral, raw_jacobian = v054.manual_forward_jacobian(program, lane.lane_id, zero)
        target = v054.terminal_target(program, neutral)
        scales = torch.linalg.vector_norm(raw_jacobian, dim=0)
        eligible = scales > 0.0
        normalized = torch.zeros_like(raw_jacobian)
        normalized[:, eligible] = raw_jacobian[:, eligible] / scales[eligible]
        rho = float(v054.RHO_FRACTION * torch.min(scales[eligible]))
        axis_tuples = v054._terminal_axes(program)
        axes = tuple(
            TerminalAxis(
                axis_id=_axis_id(channel, evidence_id, target_node_id),
                channel=channel,
                evidence_id=evidence_id,
                target_node_id=target_node_id,
                target_node_type="fact",
                target_value=float(target[index]),
            )
            for index, (target_node_id, evidence_id, channel) in enumerate(axis_tuples)
        )
        ledger = _build_shared_evidence_ledger(program)
        ledger_by_id = _ledger_hashes(ledger)
        order = list(parsed["evidence_order"])
        bindings = tuple(
            {
                "content_sha256": ledger_by_id[evidence_id],
                "evidence_id": evidence_id,
                "schedule_horizon": order.index(evidence_id) + 1,
            }
            for evidence_id in sorted(order)
        )
    else:
        fixture = v054.load_fixture(v054.DEFAULT_NO_EVENT_FIXTURE, no_event=True)
        program = v054.compile_program(fixture, no_event=True)
        expected_schedule = None
        expected_sites = ()
        neutral = torch.tensor(parsed["stable_output"], dtype=FLOAT_DTYPE).reshape(-1)
        target = neutral.clone()
        raw_jacobian = torch.zeros((neutral.numel(), 0), dtype=FLOAT_DTYPE)
        scales = torch.zeros(0, dtype=FLOAT_DTYPE)
        normalized = raw_jacobian.clone()
        rho = 0.0
        axes = tuple(
            TerminalAxis(
                axis_id=_axis_id(row["channel"], row["evidence_id"], row["target_node_id"]),
                channel=row["channel"],
                evidence_id=row["evidence_id"],
                target_node_id=row["target_node_id"],
                target_node_type="constraint",
                target_value=float(target[index]),
            )
            for index, row in enumerate(parsed["terminal_axes"])
        )
        event_program = v054.compile_program(v054.load_fixture(v054.DEFAULT_EVENT_FIXTURE))
        ledger = _build_shared_evidence_ledger(event_program)
        ledger_by_id = _ledger_hashes(ledger)
        bindings = tuple(
            {
                "content_sha256": ledger_by_id[evidence_id],
                "evidence_id": evidence_id,
                "schedule_horizon": None,
            }
            for evidence_id in sorted({axis.evidence_id for axis in axes})
        )
    exact = (
        _program_exact(lane.program, program)
        and lane.schedule_id == expected_schedule
        and canonical_json_bytes(list(lane.sites)) == canonical_json_bytes(list(expected_sites))
        and lane.axes == axes
        and torch.equal(lane.target, target)
        and torch.equal(lane.neutral_output, neutral)
        and torch.equal(lane.raw_jacobian, raw_jacobian)
        and torch.equal(lane.scales, scales)
        and torch.equal(lane.normalized_jacobian, normalized)
        and lane.rho == rho
        and canonical_json_bytes(list(lane.evidence_bindings))
        == canonical_json_bytes(list(bindings))
    )
    if not exact:
        raise LaneCompositionValidationError(
            f"runtime derivation differs from pinned v0.5.4 source: {lane.lane_id}"
        )


def _validate_bindings(lanes: Sequence[LaneRuntime], ledger: Mapping[str, Any]) -> None:
    expected = _ledger_hashes(ledger)
    observed_by_id: dict[str, str] = {}
    for lane in lanes:
        expected_ids = (
            set(lane.source_payload["evidence_order"])
            if lane.lane_id in EVENT_LANES
            else {axis.evidence_id for axis in lane.axes}
        )
        if len(lane.evidence_bindings) != len(expected_ids):
            raise LaneCompositionValidationError("lane evidence binding cardinality mismatch")
        binding_ids: list[str] = []
        for row in lane.evidence_bindings:
            if set(row) != {"content_sha256", "evidence_id", "schedule_horizon"}:
                raise LaneCompositionValidationError("lane evidence binding keys differ")
            evidence_id = str(row["evidence_id"])
            content_hash = str(row["content_sha256"])
            if evidence_id not in expected or expected[evidence_id] != content_hash:
                raise LaneCompositionValidationError("lane evidence binding conflicts with ledger")
            prior = observed_by_id.setdefault(evidence_id, content_hash)
            if prior != content_hash:
                raise LaneCompositionValidationError("same Evidence ID has conflicting hashes")
            if lane.lane_id in EVENT_LANES:
                expected_horizon = lane.source_payload["evidence_order"].index(evidence_id) + 1
                if row["schedule_horizon"] != expected_horizon:
                    raise LaneCompositionValidationError("event binding horizon drift")
            elif row["schedule_horizon"] is not None:
                raise LaneCompositionValidationError("stable binding must not invent a horizon")
            binding_ids.append(evidence_id)
        if set(binding_ids) != expected_ids or len(binding_ids) != len(set(binding_ids)):
            raise LaneCompositionValidationError("lane evidence binding set mismatch")


def _build_clauses(lanes: Sequence[LaneRuntime]) -> tuple[JsonObject, ...]:
    groups: dict[str, list[tuple[str, TerminalAxis]]] = {}
    for lane in lanes:
        for axis in lane.axes:
            groups.setdefault(axis.axis_id, []).append((lane.lane_id, axis))
    clauses: list[JsonObject] = []
    for axis_id in sorted(groups):
        rows = sorted(groups[axis_id], key=lambda row: row[0])
        targets = {canonical_json_bytes(row[1].to_dict()) for row in rows}
        if len(rows) > 1 and len(targets) != 1:
            raise LaneCompositionValidationError("identical terminal axis has conflicting target")
        if len(rows) < 2:
            continue
        if rows[0][1].target_node_type != "fact":
            raise LaneCompositionValidationError("constraint lane must remain disconnected")
        for (left_id, left), (right_id, right) in itertools.combinations(rows, 2):
            if left.target_value != right.target_value:
                raise LaneCompositionValidationError("same-axis target value conflict")
            clause_id = (
                f"eq{NAMESPACE_SEPARATOR}{left_id}{NAMESPACE_SEPARATOR}{right_id}"
                f"{NAMESPACE_SEPARATOR}{fingerprint(axis_id)[:16]}"
            )
            clauses.append(
                {
                    "axis_id": axis_id,
                    "clause_id": clause_id,
                    "incidence": [
                        {"coefficient": 1, "lane_id": left_id},
                        {"coefficient": -1, "lane_id": right_id},
                    ],
                    "left_lane_id": left_id,
                    "right_lane_id": right_id,
                    "target_value": _normalize_float(left.target_value),
                }
            )
    return tuple(clauses)


def compile_bundle(
    fixture: Mapping[str, Any], *, lane_order_override: Sequence[str] | None = None
) -> tuple[JsonObject, JsonObject, tuple[LaneRuntime, ...], tuple[JsonObject, ...]]:
    validate_fixture(fixture)
    source_gate = _validate_v054_source_gate()
    event_fixture = v054.load_fixture(v054.DEFAULT_EVENT_FIXTURE)
    stable_fixture = v054.load_fixture(v054.DEFAULT_NO_EVENT_FIXTURE, no_event=True)
    event_program = v054.compile_program(event_fixture)
    stable_program = v054.compile_program(stable_fixture, no_event=True)
    ledger = _build_shared_evidence_ledger(event_program)
    manifest, _manifest_raw = _strict_load(V054_MANIFEST_PATH)
    lane_ids = list(fixture["lane_ids"] if lane_order_override is None else lane_order_override)
    if sorted(lane_ids) != sorted(fixture["lane_ids"]):
        raise LaneCompositionValidationError("lane order override must be an exact permutation")
    lanes = _validate_runtime_lanes(
        [
            _load_lane(
                lane_id,
                event_program=event_program,
                stable_program=stable_program,
                ledger=ledger,
                manifest=manifest,
            )
            for lane_id in lane_ids
        ]
    )
    _validate_bindings(lanes, ledger)
    clauses = _build_clauses(lanes)
    return source_gate, ledger, lanes, clauses


def _normalized_to_raw(lane: LaneRuntime, normalized: torch.Tensor) -> torch.Tensor:
    if normalized.shape != (lane.control_count,) or normalized.dtype != FLOAT_DTYPE:
        raise LaneCompositionValidationError("normalized lane control shape/dtype mismatch")
    if lane.control_count == 0:
        return normalized.clone()
    eligible = lane.scales > 0.0
    safe = torch.where(eligible, lane.scales, torch.ones_like(lane.scales))
    return torch.where(eligible, normalized / safe, torch.zeros_like(normalized))


def _lane_terminal(lane: LaneRuntime, normalized: torch.Tensor) -> torch.Tensor:
    if lane.program is None or lane.schedule_id is None:
        if normalized.numel() != 0:
            raise LaneCompositionValidationError("stable lane cannot expose controls")
        return lane.neutral_output.clone()
    delta = _normalized_to_raw(lane, normalized)
    return v054.forward_terminal(lane.program, lane.schedule_id, delta)


def _axis_index(lane: LaneRuntime) -> dict[str, int]:
    return {row.axis_id: index for index, row in enumerate(lane.axes)}


def _bundle_objective(
    lanes: Sequence[LaneRuntime],
    clauses: Sequence[Mapping[str, Any]],
    lane_controls: Mapping[str, torch.Tensor],
    merge_control: torch.Tensor,
) -> tuple[torch.Tensor, dict[str, torch.Tensor], dict[str, torch.Tensor], torch.Tensor, torch.Tensor]:
    if merge_control.shape != (len(clauses),) or merge_control.dtype != FLOAT_DTYPE:
        raise LaneCompositionValidationError("merge control shape/dtype mismatch")
    lane_by_id = {lane.lane_id: lane for lane in lanes}
    expected_control_ids = {lane.lane_id for lane in lanes if lane.control_count}
    if set(lane_controls) != expected_control_ids:
        raise LaneCompositionValidationError("lane control map IDs differ from event lanes")
    outputs: dict[str, torch.Tensor] = {}
    losses: dict[str, torch.Tensor] = {}
    for lane in lanes:
        control = lane_controls.get(lane.lane_id)
        if control is None:
            if lane.control_count:
                raise LaneCompositionValidationError("event lane control missing")
            control = torch.zeros(0, dtype=FLOAT_DTYPE)
        output = _lane_terminal(lane, control)
        outputs[lane.lane_id] = output
        residual = output - lane.target
        losses[lane.lane_id] = 0.5 * torch.dot(residual, residual)
    raw_rows: list[torch.Tensor] = []
    index_by_lane = {lane.lane_id: _axis_index(lane) for lane in lanes}
    for clause in clauses:
        left_id = str(clause["left_lane_id"])
        right_id = str(clause["right_lane_id"])
        axis_id = str(clause["axis_id"])
        if left_id not in lane_by_id or right_id not in lane_by_id:
            raise LaneCompositionValidationError("merge clause references undeclared lane")
        raw_rows.append(
            outputs[left_id][index_by_lane[left_id][axis_id]]
            - outputs[right_id][index_by_lane[right_id][axis_id]]
        )
    raw = (
        torch.stack(raw_rows)
        if raw_rows
        else torch.zeros(0, dtype=FLOAT_DTYPE, device=merge_control.device)
    )
    residual = raw - merge_control
    total = sum(losses.values(), torch.zeros((), dtype=FLOAT_DTYPE))
    total = total + 0.5 * torch.dot(residual, residual) + 0.5 * torch.dot(
        merge_control, merge_control
    )
    return total, outputs, losses, raw, residual


def _zero_controls(lanes: Sequence[LaneRuntime], *, requires_grad: bool = False) -> dict[str, torch.Tensor]:
    return {
        lane.lane_id: torch.zeros(
            lane.control_count, dtype=FLOAT_DTYPE, requires_grad=requires_grad
        )
        for lane in lanes
        if lane.control_count
    }


def _full_autograd_gradients(
    lanes: Sequence[LaneRuntime], clauses: Sequence[Mapping[str, Any]]
) -> tuple[dict[str, torch.Tensor], torch.Tensor, JsonObject]:
    controls = _zero_controls(lanes, requires_grad=True)
    merge = torch.zeros(len(clauses), dtype=FLOAT_DTYPE, requires_grad=True)
    total, outputs, losses, raw, residual = _bundle_objective(
        lanes, clauses, controls, merge
    )
    variables = [controls[key] for key in sorted(controls)] + [merge]
    gradients = torch.autograd.grad(total, variables)
    lane_gradients = {
        key: gradients[index].detach().clone()
        for index, key in enumerate(sorted(controls))
    }
    merge_gradient = gradients[-1].detach().clone()
    evaluation = _evaluation_payload(
        lanes, clauses, outputs, losses, raw, residual, merge.detach(), total
    )
    return lane_gradients, merge_gradient, evaluation


def _block_gradients(
    lanes: Sequence[LaneRuntime], clauses: Sequence[Mapping[str, Any]]
) -> tuple[dict[str, torch.Tensor], dict[str, torch.Tensor], torch.Tensor]:
    zero_controls = _zero_controls(lanes)
    merge = torch.zeros(len(clauses), dtype=FLOAT_DTYPE)
    _total, outputs, _losses, raw, _residual = _bundle_objective(
        lanes, clauses, zero_controls, merge
    )
    seeds = {
        lane.lane_id: outputs[lane.lane_id].detach() - lane.target
        for lane in lanes
    }
    index_by_lane = {lane.lane_id: _axis_index(lane) for lane in lanes}
    for index, clause in enumerate(clauses):
        left_id = str(clause["left_lane_id"])
        right_id = str(clause["right_lane_id"])
        axis_id = str(clause["axis_id"])
        seeds[left_id][index_by_lane[left_id][axis_id]] += raw[index]
        seeds[right_id][index_by_lane[right_id][axis_id]] -= raw[index]
    matrix_gradients: dict[str, torch.Tensor] = {}
    reverse_gradients: dict[str, torch.Tensor] = {}
    for lane in lanes:
        if not lane.control_count:
            continue
        matrix_gradients[lane.lane_id] = lane.normalized_jacobian.T @ seeds[lane.lane_id]
        effective_target = outputs[lane.lane_id].detach() - seeds[lane.lane_id]
        raw_gradient, reverse_output, _loss = v054.manual_reverse_adjoint(
            lane.program,
            str(lane.schedule_id),
            torch.zeros(lane.control_count, dtype=FLOAT_DTYPE),
            effective_target,
        )
        if not torch.equal(reverse_output, outputs[lane.lane_id].detach()):
            raise LaneCompositionValidationError("block reverse replay output drift")
        normalized = torch.zeros_like(raw_gradient)
        eligible = lane.scales > 0.0
        normalized[eligible] = raw_gradient[eligible] / lane.scales[eligible]
        reverse_gradients[lane.lane_id] = normalized
    merge_gradient = -raw + merge
    return matrix_gradients, reverse_gradients, merge_gradient


def _finite_difference_gradients(
    lanes: Sequence[LaneRuntime],
    clauses: Sequence[Mapping[str, Any]],
    *,
    epsilon: float = FD_EPSILON,
) -> tuple[dict[str, torch.Tensor], torch.Tensor]:
    if not math.isfinite(epsilon) or epsilon <= 0.0:
        raise LaneCompositionValidationError("finite difference epsilon must be positive")
    controls = _zero_controls(lanes)
    merge = torch.zeros(len(clauses), dtype=FLOAT_DTYPE)

    def loss(rows: Mapping[str, torch.Tensor], merge_value: torch.Tensor) -> float:
        value, _outputs, _losses, _raw, _residual = _bundle_objective(
            lanes, clauses, rows, merge_value
        )
        return float(value)

    lane_gradients: dict[str, torch.Tensor] = {}
    for lane_id in sorted(controls):
        gradient = torch.zeros_like(controls[lane_id])
        for index in range(gradient.numel()):
            plus = {key: value.clone() for key, value in controls.items()}
            minus = {key: value.clone() for key, value in controls.items()}
            plus[lane_id][index] += epsilon
            minus[lane_id][index] -= epsilon
            gradient[index] = (loss(plus, merge) - loss(minus, merge)) / (2.0 * epsilon)
        lane_gradients[lane_id] = gradient
    merge_gradient = torch.zeros_like(merge)
    for index in range(merge.numel()):
        plus = merge.clone()
        minus = merge.clone()
        plus[index] += epsilon
        minus[index] -= epsilon
        merge_gradient[index] = (loss(controls, plus) - loss(controls, minus)) / (
            2.0 * epsilon
        )
    return lane_gradients, merge_gradient


def _max_abs_difference(left: torch.Tensor, right: torch.Tensor) -> float:
    if left.shape != right.shape:
        return math.inf
    return float(torch.max(torch.abs(left - right))) if left.numel() else 0.0


def _project_equal_norm(gradient: torch.Tensor, radius: float) -> torch.Tensor:
    if gradient.numel() == 0 or radius == 0.0:
        return torch.zeros_like(gradient)
    norm = torch.linalg.vector_norm(gradient)
    if not bool(norm > 0.0):
        return torch.zeros_like(gradient)
    return -float(radius) * gradient / norm


def _evaluation_payload(
    lanes: Sequence[LaneRuntime],
    clauses: Sequence[Mapping[str, Any]],
    outputs: Mapping[str, torch.Tensor],
    losses: Mapping[str, torch.Tensor],
    raw: torch.Tensor,
    residual: torch.Tensor,
    merge: torch.Tensor,
    total: torch.Tensor,
) -> JsonObject:
    outputs = {key: value.detach() for key, value in outputs.items()}
    losses = {key: value.detach() for key, value in losses.items()}
    raw = raw.detach()
    residual = residual.detach()
    merge = merge.detach()
    total = total.detach()
    clause_rows = []
    for index, clause in enumerate(clauses):
        clause_rows.append(
            {
                "clause_id": clause["clause_id"],
                "controlled_residual": _normalize_float(float(residual[index])),
                "merge_control": _normalize_float(float(merge[index])),
                "raw_incidence_aq": _normalize_float(float(raw[index])),
            }
        )
    payload = {
        "junction_rows": clause_rows,
        "lane_outputs": [
            {
                "lane_id": lane.lane_id,
                "terminal": [
                    {
                        "axis_id": axis.axis_id,
                        "value": _normalize_float(float(outputs[lane.lane_id][index])),
                    }
                    for index, axis in enumerate(lane.axes)
                ],
                "terminal_loss": _normalize_float(float(losses[lane.lane_id])),
            }
            for lane in sorted(lanes, key=lambda row: row.lane_id)
        ],
        "total_objective": _normalize_float(float(total)),
    }
    return _with_fingerprint(payload)


def _build_control_bundle(
    lanes: Sequence[LaneRuntime],
    clauses: Sequence[Mapping[str, Any]],
    block_gradients: Mapping[str, torch.Tensor],
    merge_gradient: torch.Tensor,
    *,
    one_lane: bool,
) -> tuple[JsonObject, dict[str, torch.Tensor], torch.Tensor]:
    lane_controls: dict[str, torch.Tensor] = {}
    maps: list[JsonObject] = []
    for lane in sorted(lanes, key=lambda row: row.lane_id):
        if not lane.control_count:
            maps.append(
                {
                    "control_count": 0,
                    "inner_control_map": None,
                    "lane_id": lane.lane_id,
                    "namespace_prefix": f"lane{NAMESPACE_SEPARATOR}{lane.lane_id}{NAMESPACE_SEPARATOR}",
                    "normalized_l2_budget": 0.0,
                }
            )
            continue
        control = _project_equal_norm(block_gradients[lane.lane_id], lane.rho)
        lane_controls[lane.lane_id] = control
        placement = "exact_temporal_adjoint" if one_lane else "bundle_block_adjoint"
        inner = v054._control_map(
            "C",
            control,
            lane.scales,
            lane.sites,
            placement=placement,
        )
        maps.append(
            {
                "control_count": lane.control_count,
                "inner_control_map": inner,
                "lane_id": lane.lane_id,
                "namespace_prefix": f"lane{NAMESPACE_SEPARATOR}{lane.lane_id}{NAMESPACE_SEPARATOR}",
                "normalized_l2_budget": _normalize_float(lane.rho),
            }
        )
    event_radii = [lane.rho for lane in lanes if lane.rho > 0.0]
    merge_radius = min(event_radii) if clauses and event_radii else 0.0
    merge_control = _project_equal_norm(merge_gradient, merge_radius)
    merge_map = {
        "controls": [
            {
                "clause_id": clause["clause_id"],
                "control_id": f"merge{NAMESPACE_SEPARATOR}{clause['clause_id']}",
                "value": _normalize_float(float(merge_control[index])),
            }
            for index, clause in enumerate(clauses)
        ],
        "normalized_l2": _normalize_float(float(torch.linalg.vector_norm(merge_control))),
        "normalized_l2_budget": _normalize_float(merge_radius),
        "parameterization": "separate_bounded_consistency_slack",
    }
    payload = {
        "lane_control_maps": maps,
        "merge_control_map": merge_map,
        "schema_version": CONTROL_SCHEMA_VERSION,
    }
    return _with_fingerprint(payload), lane_controls, merge_control


def _lane_receipts(lanes: Sequence[LaneRuntime]) -> list[JsonObject]:
    return [
        {
            "control_count": lane.control_count,
            "evidence_bindings": list(lane.evidence_bindings),
            "immutable_source_bytes_sha256": lane.source_file_sha256,
            "lane_id": lane.lane_id,
            "namespace_prefix": f"lane{NAMESPACE_SEPARATOR}{lane.lane_id}{NAMESPACE_SEPARATOR}",
            "program_fingerprint_sha256": lane.source_payload["program_fingerprint_sha256"],
            "sealed_lane_fingerprint_sha256": lane.source_fingerprint_sha256,
            "source_path": str(lane.source_path.relative_to(ROOT)),
            "terminal_axes": [axis.to_dict() for axis in lane.axes],
        }
        for lane in sorted(lanes, key=lambda row: row.lane_id)
    ]


def _merge_contract(lanes: Sequence[LaneRuntime], clauses: Sequence[Mapping[str, Any]]) -> JsonObject:
    payload = {
        "arity": len(lanes),
        "clauses": list(clauses),
        "junction_count": 1,
        "junction_id": "merge::typed_contract",
        "merge_control_dimension": len(clauses),
        "objective": "sum_lane_objectives_plus_half_norm_Aq_minus_m_squared_plus_half_norm_m_squared",
        "operator": MERGE_OPERATOR,
        "schema_version": MERGE_SCHEMA_VERSION,
        "weights": [],
    }
    return _with_fingerprint(payload)


def _evaluate_compiled(
    lanes: Sequence[LaneRuntime], clauses: Sequence[Mapping[str, Any]], *, with_fd: bool = True
) -> JsonObject:
    lanes = _validate_runtime_lanes(lanes)
    expected_clauses = _build_clauses(lanes)
    if canonical_json_bytes(list(clauses)) != canonical_json_bytes(list(expected_clauses)):
        raise LaneCompositionValidationError("evaluation merge clauses are not mechanically derived")
    clauses = expected_clauses
    full_lane, full_merge, neutral = _full_autograd_gradients(lanes, clauses)
    block_lane, reverse_lane, block_merge = _block_gradients(lanes, clauses)
    if with_fd:
        fd_lane, fd_merge = _finite_difference_gradients(lanes, clauses)
    else:
        fd_lane = {key: value.clone() for key, value in full_lane.items()}
        fd_merge = full_merge.clone()
    lane_rows: list[JsonObject] = []
    maximum_block_error = 0.0
    maximum_reverse_error = 0.0
    maximum_fd_error = 0.0
    for lane_id in sorted(full_lane):
        block_error = _max_abs_difference(block_lane[lane_id], full_lane[lane_id])
        reverse_error = _max_abs_difference(reverse_lane[lane_id], full_lane[lane_id])
        fd_error = _max_abs_difference(fd_lane[lane_id], full_lane[lane_id])
        maximum_block_error = max(maximum_block_error, block_error)
        maximum_reverse_error = max(maximum_reverse_error, reverse_error)
        maximum_fd_error = max(maximum_fd_error, fd_error)
        lane_rows.append(
            {
                "block_gradient": _tensor_values(block_lane[lane_id]),
                "block_max_abs_error": block_error,
                "finite_difference_gradient": _tensor_values(fd_lane[lane_id]),
                "finite_difference_max_abs_error": fd_error,
                "full_autograd_gradient": _tensor_values(full_lane[lane_id]),
                "lane_id": lane_id,
                "matrix_free_reverse_gradient": _tensor_values(reverse_lane[lane_id]),
                "matrix_free_reverse_max_abs_error": reverse_error,
            }
        )
    merge_block_error = _max_abs_difference(block_merge, full_merge)
    merge_fd_error = _max_abs_difference(fd_merge, full_merge)
    maximum_block_error = max(maximum_block_error, merge_block_error)
    maximum_fd_error = max(maximum_fd_error, merge_fd_error)
    one_lane = len(lanes) == 1
    control_bundle, controlled_lane_controls, controlled_merge = _build_control_bundle(
        lanes, clauses, block_lane, block_merge, one_lane=one_lane
    )
    controlled_total, controlled_outputs, controlled_losses, controlled_raw, controlled_residual = (
        _bundle_objective(
            lanes,
            clauses,
            controlled_lane_controls,
            controlled_merge,
        )
    )
    controlled = _evaluation_payload(
        lanes,
        clauses,
        controlled_outputs,
        controlled_losses,
        controlled_raw,
        controlled_residual,
        controlled_merge,
        controlled_total,
    )
    audit = {
        "central_finite_difference_epsilon": FD_EPSILON,
        "lane_gradients": lane_rows,
        "matrix_free_reverse_max_abs_error": maximum_reverse_error,
        "maximum_block_vs_autograd_abs_error": maximum_block_error,
        "maximum_fd_vs_autograd_abs_error": maximum_fd_error,
        "merge_gradient": {
            "block": _tensor_values(block_merge),
            "block_max_abs_error": merge_block_error,
            "finite_difference": _tensor_values(fd_merge),
            "finite_difference_max_abs_error": merge_fd_error,
            "full_autograd": _tensor_values(full_merge),
        },
        "schema_version": BLOCK_AUDIT_SCHEMA_VERSION,
        "status": (
            "PASS"
            if maximum_block_error <= BLOCK_ABS_TOLERANCE
            and maximum_reverse_error <= BLOCK_ABS_TOLERANCE
            and maximum_fd_error <= FD_ABS_TOLERANCE
            else "FAIL"
        ),
    }
    return {
        "block_adjoint_audit": _with_fingerprint(audit),
        "control_bundle": control_bundle,
        "controlled_evaluation": controlled,
        "neutral_evaluation": neutral,
    }


def _expect_rejected(action: Any, label: str) -> bool:
    try:
        action()
    except (LaneCompositionValidationError, v054.TemporalAdjointValidationError):
        return True
    raise LaneCompositionValidationError(f"negative mutation was accepted: {label}")


def _require_exact_derivation(observed: Any, expected: Any) -> None:
    if canonical_json_bytes(observed) != canonical_json_bytes(expected):
        raise LaneCompositionValidationError("coherently re-signed artifact differs from derivation")


@contextmanager
def network_denied() -> Iterator[dict[str, int]]:
    counts = {"network_calls": 0}

    def denied(*_args: Any, **_kwargs: Any) -> None:
        counts["network_calls"] += 1
        raise AssertionError("network access is forbidden in EBRT v0.5.5")

    with mock.patch.object(socket, "create_connection", side_effect=denied), mock.patch.object(
        socket.socket, "connect", side_effect=denied
    ), mock.patch.object(socket.socket, "connect_ex", side_effect=denied):
        yield counts


def validate_control_bundle(payload: Mapping[str, Any]) -> None:
    if not isinstance(payload, Mapping):
        raise LaneCompositionValidationError("control bundle must be object")
    _exact_keys(
        payload,
        {
            "fingerprint_sha256",
            "lane_control_maps",
            "merge_control_map",
            "schema_version",
        },
        "control_bundle",
    )
    if payload["schema_version"] != CONTROL_SCHEMA_VERSION:
        raise LaneCompositionValidationError("control bundle schema mismatch")
    if payload["fingerprint_sha256"] != fingerprint(_without_fingerprint(payload)):
        raise LaneCompositionValidationError("control bundle fingerprint mismatch")
    rows = payload["lane_control_maps"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_LANES:
        raise LaneCompositionValidationError("control bundle lane rows invalid")
    lane_ids: list[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise LaneCompositionValidationError("lane control row must be object")
        _exact_keys(
            row,
            {
                "control_count",
                "inner_control_map",
                "lane_id",
                "namespace_prefix",
                "normalized_l2_budget",
            },
            f"control_bundle.lane_control_maps[{index}]",
        )
        lane_id = row["lane_id"]
        if row["namespace_prefix"] != f"lane::{lane_id}::":
            raise LaneCompositionValidationError("lane control namespace drift")
        lane_ids.append(lane_id)
        inner = row["inner_control_map"]
        budget = float(row["normalized_l2_budget"])
        if inner is None:
            if row["control_count"] != 0 or budget != 0.0:
                raise LaneCompositionValidationError("zero-control lane bound drift")
            continue
        if not isinstance(inner, Mapping):
            raise LaneCompositionValidationError("inner lane control map malformed")
        _validate_internal_fingerprint(inner, "inner lane control map")
        if len(inner.get("controls", [])) != row["control_count"]:
            raise LaneCompositionValidationError("lane control count drift")
        observed = float(inner["normalized_l2"])
        if observed > budget + 2.0e-15 or float(inner["raw_max_abs_delta"]) > 0.1 + 2.0e-15:
            raise LaneCompositionValidationError("lane control exceeded independent bound")
    if lane_ids != sorted(lane_ids) or len(lane_ids) != len(set(lane_ids)):
        raise LaneCompositionValidationError("lane control rows not canonical unique")
    merge = payload["merge_control_map"]
    if not isinstance(merge, Mapping):
        raise LaneCompositionValidationError("merge control map must be object")
    _exact_keys(
        merge,
        {"controls", "normalized_l2", "normalized_l2_budget", "parameterization"},
        "control_bundle.merge_control_map",
    )
    if merge["parameterization"] != "separate_bounded_consistency_slack":
        raise LaneCompositionValidationError("merge control parameterization drift")
    controls = merge["controls"]
    if not isinstance(controls, list):
        raise LaneCompositionValidationError("merge controls must be list")
    values = []
    control_ids = []
    for row in controls:
        if set(row) != {"clause_id", "control_id", "value"}:
            raise LaneCompositionValidationError("merge control row keys differ")
        if row["control_id"] != f"merge::{row['clause_id']}":
            raise LaneCompositionValidationError("merge control namespace drift")
        values.append(float(row["value"]))
        control_ids.append(row["control_id"])
    if len(control_ids) != len(set(control_ids)):
        raise LaneCompositionValidationError("duplicate merge control")
    actual_l2 = math.sqrt(sum(value * value for value in values))
    if abs(actual_l2 - float(merge["normalized_l2"])) > 2.0e-15:
        raise LaneCompositionValidationError("merge control L2 receipt drift")
    if actual_l2 > float(merge["normalized_l2_budget"]) + 2.0e-15:
        raise LaneCompositionValidationError("merge control exceeded separate bound")


def _validate_evaluation(payload: Mapping[str, Any], clause_count: int) -> None:
    if not isinstance(payload, Mapping):
        raise LaneCompositionValidationError("evaluation must be object")
    _exact_keys(
        payload,
        {"fingerprint_sha256", "junction_rows", "lane_outputs", "total_objective"},
        "evaluation",
    )
    if payload["fingerprint_sha256"] != fingerprint(_without_fingerprint(payload)):
        raise LaneCompositionValidationError("evaluation fingerprint mismatch")
    rows = payload["junction_rows"]
    if not isinstance(rows, list) or len(rows) != clause_count:
        raise LaneCompositionValidationError("evaluation junction row count drift")
    raw_penalty = 0.0
    merge_penalty = 0.0
    for row in rows:
        if set(row) != {
            "clause_id",
            "controlled_residual",
            "merge_control",
            "raw_incidence_aq",
        }:
            raise LaneCompositionValidationError("evaluation junction keys differ")
        raw = float(row["raw_incidence_aq"])
        merge = float(row["merge_control"])
        residual = float(row["controlled_residual"])
        if abs((raw - merge) - residual) > 2.0e-15:
            raise LaneCompositionValidationError("Aq-m residual receipt drift")
        raw_penalty += 0.5 * residual * residual
        merge_penalty += 0.5 * merge * merge
    lane_outputs = payload["lane_outputs"]
    if not isinstance(lane_outputs, list) or not lane_outputs:
        raise LaneCompositionValidationError("evaluation lane outputs missing")
    lane_ids = [row["lane_id"] for row in lane_outputs]
    if lane_ids != sorted(lane_ids) or len(lane_ids) != len(set(lane_ids)):
        raise LaneCompositionValidationError("evaluation lane output order drift")
    lane_loss = sum(float(row["terminal_loss"]) for row in lane_outputs)
    expected_total = lane_loss + raw_penalty + merge_penalty
    if abs(expected_total - float(payload["total_objective"])) > 2.0e-12:
        raise LaneCompositionValidationError("bundle objective decomposition drift")


def _one_lane_witness() -> tuple[JsonObject, JsonObject]:
    fixture = load_fixture(DEFAULT_ONE_LANE_FIXTURE)
    source_gate, ledger, lanes, clauses = compile_bundle(fixture)
    evaluated = _evaluate_compiled(lanes, clauses)
    lane = lanes[0]
    generated_map = evaluated["control_bundle"]["lane_control_maps"][0]["inner_control_map"]
    source_map = lane.source_payload["control_maps"]["C"]
    generated_neutral_row = evaluated["neutral_evaluation"]["lane_outputs"][0]
    generated_neutral = {
        "loss": generated_neutral_row["terminal_loss"],
        "target": _tensor_values(lane.target),
        "terminal_output": [row["value"] for row in generated_neutral_row["terminal"]],
    }
    source_equivalence = {
        "control_map_C": source_map,
        "neutral": lane.source_payload["neutral"],
        "sealed_lane_file_sha256": lane.source_file_sha256,
        "sealed_lane_fingerprint_sha256": lane.source_fingerprint_sha256,
    }
    generated_equivalence = {
        "control_map_C": generated_map,
        "neutral": generated_neutral,
        "sealed_lane_file_sha256": lane.source_file_sha256,
        "sealed_lane_fingerprint_sha256": lane.source_fingerprint_sha256,
    }
    merge_controls = evaluated["control_bundle"]["merge_control_map"]["controls"]
    subchecks = {
        "control_map_canonical_bytes_exact": canonical_json_bytes(generated_map)
        == canonical_json_bytes(source_map),
        "equivalence_payload_canonical_bytes_exact": canonical_json_bytes(generated_equivalence)
        == canonical_json_bytes(source_equivalence),
        "incidence_has_zero_rows": len(clauses) == 0,
        "merge_control_vector_empty": merge_controls == [],
        "objective_exact_source_lane": (
            evaluated["neutral_evaluation"]["total_objective"]
            == lane.source_payload["neutral"]["loss"]
        ),
        "sealed_lane_bytes_receipted_unchanged": lane.source_file_sha256
        == lane.source_manifest_sha256,
        "source_gate_pass": source_gate["status"] == "PASS",
        "source_ledger_valid": bool(ledger["entries"]),
    }
    receipt = {
        "generated_equivalence_fingerprint_sha256": fingerprint(generated_equivalence),
        "source_equivalence_fingerprint_sha256": fingerprint(source_equivalence),
        "subchecks": subchecks,
        "status": "PASS" if all(subchecks.values()) else "FAIL",
    }
    return _with_fingerprint(receipt), evaluated


def _disconnected_witness(
    lanes: Sequence[LaneRuntime], clauses: Sequence[Mapping[str, Any]]
) -> JsonObject:
    stable = next((lane for lane in lanes if lane.lane_id == STABLE_LANE_ID), None)
    if stable is None:
        return _with_fingerprint(
            {
                "subchecks": {
                    "stable_lane_present": False,
                    "stable_lane_has_no_incidence": False,
                    "stable_lane_has_zero_controls": False,
                    "stable_perturbation_leaves_event_gradients_exact": False,
                },
                "status": "FAIL",
            }
        )
    baseline, _reverse, _merge = _block_gradients(lanes, clauses)
    perturbation = torch.zeros_like(stable.neutral_output)
    perturbation[0] = 0.125
    perturbed_stable = replace(stable, neutral_output=stable.neutral_output + perturbation)
    perturbed_lanes = tuple(
        perturbed_stable if lane.lane_id == STABLE_LANE_ID else lane for lane in lanes
    )
    perturbed, _perturbed_reverse, _perturbed_merge = _block_gradients(
        perturbed_lanes, clauses
    )
    gradients_exact = set(baseline) == set(perturbed) and all(
        torch.equal(baseline[key], perturbed[key]) for key in baseline
    )
    subchecks = {
        "stable_lane_has_no_incidence": all(
            clause["left_lane_id"] != STABLE_LANE_ID
            and clause["right_lane_id"] != STABLE_LANE_ID
            for clause in clauses
        ),
        "stable_lane_has_zero_controls": stable.control_count == 0,
        "stable_lane_present": True,
        "stable_perturbation_leaves_event_gradients_exact": gradients_exact,
    }
    return _with_fingerprint(
        {"subchecks": subchecks, "status": "PASS" if all(subchecks.values()) else "FAIL"}
    )


def _permutation_witness(
    fixture: Mapping[str, Any], canonical_surface: Mapping[str, Any]
) -> JsonObject:
    lane_ids = tuple(sorted(fixture["lane_ids"]))
    rows = []
    all_exact = True
    expected_bytes = canonical_json_bytes(canonical_surface)
    for permutation in itertools.permutations(lane_ids):
        _source, _ledger, lanes, clauses = compile_bundle(
            fixture, lane_order_override=permutation
        )
        evaluated = _evaluate_compiled(lanes, clauses)
        surface = {
            "block_adjoint_audit": evaluated["block_adjoint_audit"],
            "control_bundle": evaluated["control_bundle"],
            "controlled_evaluation": evaluated["controlled_evaluation"],
            "lane_receipts": _lane_receipts(lanes),
            "merge_contract": _merge_contract(lanes, clauses),
            "neutral_evaluation": evaluated["neutral_evaluation"],
        }
        exact = canonical_json_bytes(surface) == expected_bytes
        all_exact = all_exact and exact
        rows.append(
            {
                "canonical_surface_fingerprint_sha256": fingerprint(surface),
                "exact": exact,
                "input_lane_order": list(permutation),
            }
        )
    payload = {
        "all_permutations_exact": all_exact,
        "expected_permutation_count": math.factorial(len(lane_ids)),
        "observed_permutation_count": len(rows),
        "permutations": rows,
        "status": "PASS" if all_exact and len(rows) == math.factorial(len(lane_ids)) else "FAIL",
    }
    return _with_fingerprint(payload)


def _tamper_subchecks(
    fixture: Mapping[str, Any],
    lanes: Sequence[LaneRuntime],
    ledger: Mapping[str, Any],
    validation_surface: Mapping[str, Any],
) -> JsonObject:
    early = next(lane for lane in lanes if lane.lane_id == "correction_early")
    late = next(lane for lane in lanes if lane.lane_id == "correction_late")
    stable = next(lane for lane in lanes if lane.lane_id == STABLE_LANE_ID)

    forbidden_results = {}
    for key in sorted(FORBIDDEN_SCHEMA_KEYS):
        mutated = _clone(fixture)
        mutated["source_contract"][key] = {"enabled": True}
        forbidden_results[key] = _expect_rejected(
            lambda value=mutated: validate_fixture(value), f"forbidden key {key}"
        )

    duplicate_ledger = _clone(ledger)
    duplicate_ledger["entries"].append(_clone(duplicate_ledger["entries"][0]))
    duplicate_ledger["fingerprint_sha256"] = fingerprint(
        _without_fingerprint(duplicate_ledger)
    )
    conflicting_ledger = _clone(ledger)
    conflicting_ledger["entries"][0]["content_sha256"] = "0" * 64
    conflicting_ledger["fingerprint_sha256"] = fingerprint(
        _without_fingerprint(conflicting_ledger)
    )
    missing_invalidation = _clone(ledger)
    missing_invalidation["invalidations"] = []
    missing_invalidation["fingerprint_sha256"] = fingerprint(
        _without_fingerprint(missing_invalidation)
    )

    conflicting_axis = replace(
        late.axes[0], target_value=late.axes[0].target_value + 0.25
    )
    conflicting_late = replace(late, axes=(conflicting_axis,) + late.axes[1:])
    bad_count = _clone(fixture)
    bad_count["lane_ids"] = ["correction_early"] * 4
    bad_junction = _clone(fixture)
    bad_junction["junction"]["count"] = 2
    cross_edge = _clone(fixture)
    cross_edge["cross_lane_edges"] = [
        {"source": "lane::correction_early::x", "target": "lane::correction_late::y"}
    ]
    mutated_payload = _clone(early.source_payload)
    mutated_payload["status"] = "TAMPERED"
    resigned_payload = _clone(early.source_payload)
    resigned_payload["claim_boundary"].append("forged but coherently re-signed")
    resigned_payload["fingerprint_sha256"] = fingerprint(
        _without_fingerprint(resigned_payload)
    )
    resigned_lane = replace(
        early,
        source_payload=resigned_payload,
        source_fingerprint_sha256=resigned_payload["fingerprint_sha256"],
    )
    coherent_artifact = _clone(validation_surface)
    coherent_artifact["surface"]["block_adjoint_audit"][
        "maximum_block_vs_autograd_abs_error"
    ] = 999.0
    coherent_artifact["surface"]["block_adjoint_audit"]["status"] = "FAIL"
    coherent_artifact["surface"]["block_adjoint_audit"]["fingerprint_sha256"] = fingerprint(
        _without_fingerprint(coherent_artifact["surface"]["block_adjoint_audit"])
    )
    swapped_schedule = replace(early, schedule_id="correction_late")
    changed_jacobian = early.normalized_jacobian.clone()
    changed_jacobian[0, 0] += 0.125
    changed_target_early = replace(early, target=early.target + 0.125)
    changed_target_late = replace(late, target=late.target + 0.125)
    checks = {
        "all_forbidden_nested_schema_keys_rejected": all(forbidden_results.values()),
        "conflicting_axis_target_rejected": _expect_rejected(
            lambda: _build_clauses((early, conflicting_late, stable)),
            "conflicting axis target",
        ),
        "coherent_artifact_resign_rejected": _expect_rejected(
            lambda: _require_exact_derivation(coherent_artifact, validation_surface),
            "coherently re-signed derived artifact",
        ),
        "coherent_payload_resign_rejected": _expect_rejected(
            lambda: _validate_runtime_lanes((resigned_lane,)),
            "coherently re-signed runtime payload",
        ),
        "conflicting_evidence_hash_rejected": _expect_rejected(
            lambda: validate_evidence_ledger(conflicting_ledger),
            "conflicting evidence hash",
        ),
        "duplicate_evidence_id_rejected": _expect_rejected(
            lambda: validate_evidence_ledger(duplicate_ledger),
            "duplicate evidence ID",
        ),
        "duplicate_lane_alias_bytes_rejected": _expect_rejected(
            lambda: _validate_runtime_lanes(
                (early, replace(late, source_bytes=early.source_bytes), stable)
            ),
            "duplicate lane bytes alias",
        ),
        "duplicate_lane_alias_payload_rejected": _expect_rejected(
            lambda: _validate_runtime_lanes(
                (early, replace(late, source_payload=early.source_payload), stable)
            ),
            "duplicate lane payload alias",
        ),
        "empty_order_override_rejected": _expect_rejected(
            lambda: compile_bundle(fixture, lane_order_override=[]),
            "empty lane permutation",
        ),
        "missing_bindings_rejected": _expect_rejected(
            lambda: _validate_bindings((replace(early, evidence_bindings=()),), ledger),
            "missing evidence bindings",
        ),
        "missing_invalidation_rejected": _expect_rejected(
            lambda: validate_evidence_ledger(missing_invalidation),
            "missing invalidation",
        ),
        "namespace_delimiter_axis_rejected": _expect_rejected(
            lambda: _validate_runtime_lanes(
                (
                    replace(
                        early,
                        axes=(replace(early.axes[0], axis_id="x::y"),) + early.axes[1:],
                    ),
                )
            ),
            "axis namespace delimiter",
        ),
        "source_payload_fingerprint_tamper_rejected": _expect_rejected(
            lambda: _validate_internal_fingerprint(mutated_payload, "mutated lane"),
            "source payload tamper",
        ),
        "source_path_swap_rejected": _expect_rejected(
            lambda: _validate_runtime_lanes((replace(early, source_path=late.source_path),)),
            "source path swap",
        ),
        "schedule_swap_rejected": _expect_rejected(
            lambda: _validate_runtime_lanes((swapped_schedule,)),
            "schedule swap",
        ),
        "normalized_jacobian_mutation_rejected": _expect_rejected(
            lambda: _validate_runtime_lanes(
                (replace(early, normalized_jacobian=changed_jacobian),)
            ),
            "normalized Jacobian mutation",
        ),
        "coherent_terminal_target_mutation_rejected": _expect_rejected(
            lambda: _validate_runtime_lanes((changed_target_early, changed_target_late)),
            "coherent terminal target mutation",
        ),
        "undeclared_cross_lane_edge_rejected": _expect_rejected(
            lambda: validate_fixture(cross_edge), "cross-lane edge"
        ),
        "unsafe_lane_id_rejected": _expect_rejected(
            lambda: _validate_runtime_lanes((replace(early, lane_id="bad/id"),)),
            "unsafe lane ID",
        ),
        "four_lanes_rejected": _expect_rejected(
            lambda: validate_fixture(bad_count), "four lanes"
        ),
        "junction_count_not_one_rejected": _expect_rejected(
            lambda: validate_fixture(bad_junction), "two junctions"
        ),
    }
    return _with_fingerprint(
        {
            "forbidden_key_results": forbidden_results,
            "subchecks": checks,
            "status": "PASS" if all(checks.values()) else "FAIL",
        }
    )


def _bounds_subchecks(control_bundle: Mapping[str, Any]) -> JsonObject:
    validate_control_bundle(control_bundle)
    mutated = _clone(control_bundle)
    event_row = next(
        row for row in mutated["lane_control_maps"] if row["inner_control_map"] is not None
    )
    event_row["inner_control_map"]["normalized_l2"] = (
        float(event_row["normalized_l2_budget"]) + 1.0
    )
    event_row["inner_control_map"]["fingerprint_sha256"] = fingerprint(
        _without_fingerprint(event_row["inner_control_map"])
    )
    mutated["fingerprint_sha256"] = fingerprint(_without_fingerprint(mutated))
    checks = {
        "lane_and_merge_budgets_have_separate_receipts": all(
            "normalized_l2_budget" in row
            for row in control_bundle["lane_control_maps"]
        )
        and "normalized_l2_budget" in control_bundle["merge_control_map"],
        "published_control_bundle_valid": True,
        "oversized_lane_control_rejected": _expect_rejected(
            lambda: validate_control_bundle(mutated), "oversized lane control"
        ),
    }
    return _with_fingerprint(
        {"subchecks": checks, "status": "PASS" if all(checks.values()) else "FAIL"}
    )


def _gate_audit(
    *,
    source_gate: Mapping[str, Any],
    one_lane_receipt: Mapping[str, Any],
    ledger: Mapping[str, Any],
    lanes: Sequence[LaneRuntime],
    clauses: Sequence[Mapping[str, Any]],
    evaluated: Mapping[str, Any],
    disconnected: Mapping[str, Any],
    permutation: Mapping[str, Any],
    tamper: Mapping[str, Any],
    bounds: Mapping[str, Any],
    deterministic_checks: Mapping[str, bool],
) -> JsonObject:
    block = evaluated["block_adjoint_audit"]
    subchecks: dict[str, JsonObject] = {
        "v0_5_4_source_gate_exact": {
            "all_v0_5_4_hard_gates_true": source_gate["all_hard_gates_true"],
            "network_calls_zero": source_gate["network_calls"] == 0,
            "promotion_ready": source_gate["promotion_ready"] is True,
            "provider_calls_zero": source_gate["provider_calls"] == 0,
            "status_pass": source_gate["status"] == "PASS",
        },
        "one_lane_exact": dict(one_lane_receipt["subchecks"]),
        "ledger_consistent": {
            "all_lane_bindings_exact": True,
            "exact_r1_r6_entries": [row["evidence_id"] for row in ledger["entries"]]
            == ["R1", "R2", "R3", "R4", "R5", "R6"],
            "exact_r6_invalidates_r3": len(ledger["invalidations"]) == 1
            and ledger["invalidations"][0]["source_evidence_id"] == "R6"
            and ledger["invalidations"][0]["target_evidence_id"] == "R3",
            "ledger_reloaded_and_rehashed": True,
        },
        "namespace_isolated": {
            "exactly_one_junction": True,
            "lane_count_within_one_to_three": 1 <= len(lanes) <= MAX_LANES,
            "namespaces_unique": len({row.lane_id for row in lanes}) == len(lanes),
            "stable_constraint_has_no_clause": all(
                clause["left_lane_id"] != STABLE_LANE_ID
                and clause["right_lane_id"] != STABLE_LANE_ID
                for clause in clauses
            ),
            "typed_incidence_coefficients_exact": all(
                [row["coefficient"] for row in clause["incidence"]] == [1, -1]
                for clause in clauses
            ),
        },
        "block_gradient_agreement": {
            "block_adjoint_status_pass": block["status"] == "PASS",
            "block_vs_autograd_within_tolerance": block[
                "maximum_block_vs_autograd_abs_error"
            ]
            <= BLOCK_ABS_TOLERANCE,
            "finite_difference_within_tolerance": block[
                "maximum_fd_vs_autograd_abs_error"
            ]
            <= FD_ABS_TOLERANCE,
            "matrix_free_reverse_within_tolerance": block[
                "matrix_free_reverse_max_abs_error"
            ]
            <= BLOCK_ABS_TOLERANCE,
        },
        "disconnected_zero": dict(disconnected["subchecks"]),
        "permutation_invariant": {
            "all_input_permutations_exact": permutation["all_permutations_exact"],
            "all_permutations_executed": permutation["observed_permutation_count"]
            == permutation["expected_permutation_count"],
        },
        "tamper_ready_source_receipts": dict(tamper["subchecks"]),
        "bounds_complete": dict(bounds["subchecks"]),
        "deterministic_network_zero": dict(deterministic_checks),
    }
    top_level = {key: all(bool(value) for value in subchecks[key].values()) for key in HARD_GATE_IDS}
    status = "PASS" if all(top_level.values()) else "FAIL"
    return _with_fingerprint(
        {
            "status": status,
            "subchecks": subchecks,
            "top_level_gates": top_level,
        }
    )


def _build_bundle_once(
    fixture: Mapping[str, Any], *, lane_order_override: Sequence[str] | None = None
) -> JsonObject:
    source_gate, ledger, lanes, clauses = compile_bundle(
        fixture, lane_order_override=lane_order_override
    )
    evaluated = _evaluate_compiled(lanes, clauses)
    merge_contract = _merge_contract(lanes, clauses)
    lane_receipts = _lane_receipts(lanes)
    canonical_surface = {
        "block_adjoint_audit": evaluated["block_adjoint_audit"],
        "control_bundle": evaluated["control_bundle"],
        "controlled_evaluation": evaluated["controlled_evaluation"],
        "lane_receipts": lane_receipts,
        "merge_contract": merge_contract,
        "neutral_evaluation": evaluated["neutral_evaluation"],
    }
    one_lane_receipt, _one_lane_evaluated = _one_lane_witness()
    disconnected = _disconnected_witness(lanes, clauses)
    permutation = _permutation_witness(fixture, canonical_surface)
    validation_surface = {
        "one_lane_equivalence": one_lane_receipt,
        "source_gate": source_gate,
        "surface": canonical_surface,
    }
    tamper = _tamper_subchecks(fixture, lanes, ledger, validation_surface)
    bounds = _bounds_subchecks(evaluated["control_bundle"])
    second_evaluation = _evaluate_compiled(lanes, clauses)
    with network_denied() as network_counts:
        denied_evaluation = _evaluate_compiled(lanes, clauses)
    deterministic_checks = {
        "canonical_roundtrip_exact": _strict_load_bytes(
            canonical_json_bytes(canonical_surface), label="canonical surface roundtrip"
        )
        == canonical_surface,
        "network_calls_zero_under_socket_denial": network_counts["network_calls"] == 0,
        "provider_calls_zero": all(
            lane.source_payload.get("provider_calls") == 0 for lane in lanes
        ),
        "two_evaluations_byte_identical": canonical_json_bytes(evaluated)
        == canonical_json_bytes(second_evaluation)
        == canonical_json_bytes(denied_evaluation),
    }
    gates = _gate_audit(
        source_gate=source_gate,
        one_lane_receipt=one_lane_receipt,
        ledger=ledger,
        lanes=lanes,
        clauses=clauses,
        evaluated=evaluated,
        disconnected=disconnected,
        permutation=permutation,
        tamper=tamper,
        bounds=bounds,
        deterministic_checks=deterministic_checks,
    )
    promotion_ready = gates["status"] == "PASS" and all(
        gates["top_level_gates"].values()
    ) and all(
        all(bool(value) for value in rows.values())
        for rows in gates["subchecks"].values()
    )
    result = {
        "block_adjoint_audit": evaluated["block_adjoint_audit"],
        "claim_boundary": list(fixture["claim_boundary"])
        + [
            "The three lanes are deterministic schedule views over one contaminated public program, not independent agents or benchmark replications.",
            "The signed incidence merge has no learned weights, vote, selection, routing, or generated output.",
            "Passing this gate supports only auditable multi-trajectory composition and block credit inside the public surrogate.",
        ],
        "control_bundle": evaluated["control_bundle"],
        "controlled_evaluation": evaluated["controlled_evaluation"],
        "decision_status": PROMOTE_STATUS if promotion_ready else STOP_STATUS,
        "disconnected_audit": disconnected,
        "fixture_id": fixture["fixture_id"],
        "gates": gates,
        "junction": merge_contract,
        "lanes": lane_receipts,
        "network_calls": 0,
        "neutral_evaluation": evaluated["neutral_evaluation"],
        "one_lane_equivalence": one_lane_receipt,
        "permutation_audit": permutation,
        "promotion_ready": promotion_ready,
        "provider_calls": 0,
        "schema_version": RESULT_SCHEMA_VERSION,
        "shared_evidence_ledger": ledger,
        "source_gate": source_gate,
        "tamper_audit": tamper,
    }
    return _with_fingerprint(result)


def build_bundle(
    fixture: Mapping[str, Any] | Path = DEFAULT_FIXTURE,
    *,
    lane_order_override: Sequence[str] | None = None,
) -> JsonObject:
    value = load_fixture(fixture) if isinstance(fixture, Path) else _clone(fixture)
    validate_fixture(value)
    canonical_path = {
        "hackathon_strategy_lane_composition_v0_5_5": DEFAULT_FIXTURE,
        "hackathon_strategy_lane_composition_one_lane_v0_5_5": DEFAULT_ONE_LANE_FIXTURE,
    }.get(value["fixture_id"])
    if canonical_path is None or canonical_json_bytes(value) != canonical_json_bytes(
        load_fixture(canonical_path)
    ):
        raise LaneCompositionValidationError(
            "public build fixture differs from its pinned canonical fixture"
        )
    result = _build_bundle_once(value, lane_order_override=lane_order_override)
    validate_bundle(result, exact_rederive=False)
    return result


def validate_bundle(payload: Mapping[str, Any], *, exact_rederive: bool = True) -> None:
    if not isinstance(payload, Mapping):
        raise LaneCompositionValidationError("bundle result must be object")
    _exact_keys(
        payload,
        {
            "block_adjoint_audit",
            "claim_boundary",
            "control_bundle",
            "controlled_evaluation",
            "decision_status",
            "disconnected_audit",
            "fingerprint_sha256",
            "fixture_id",
            "gates",
            "junction",
            "lanes",
            "network_calls",
            "neutral_evaluation",
            "one_lane_equivalence",
            "permutation_audit",
            "promotion_ready",
            "provider_calls",
            "schema_version",
            "shared_evidence_ledger",
            "source_gate",
            "tamper_audit",
        },
        "bundle result",
    )
    if payload["schema_version"] != RESULT_SCHEMA_VERSION:
        raise LaneCompositionValidationError("bundle result schema mismatch")
    if payload["fingerprint_sha256"] != fingerprint(_without_fingerprint(payload)):
        raise LaneCompositionValidationError("bundle result fingerprint mismatch")
    if payload["network_calls"] != 0 or payload["provider_calls"] != 0:
        raise LaneCompositionValidationError("bundle result is not network/provider zero")
    validate_evidence_ledger(payload["shared_evidence_ledger"])
    validate_control_bundle(payload["control_bundle"])
    junction = payload["junction"]
    _validate_internal_fingerprint(junction, "merge contract")
    if (
        junction.get("schema_version") != MERGE_SCHEMA_VERSION
        or junction.get("junction_count") != 1
        or junction.get("operator") != MERGE_OPERATOR
        or junction.get("weights") != []
    ):
        raise LaneCompositionValidationError("merge contract mechanism drift")
    clause_count = len(junction["clauses"])
    _validate_evaluation(payload["neutral_evaluation"], clause_count)
    _validate_evaluation(payload["controlled_evaluation"], clause_count)
    _validate_internal_fingerprint(payload["block_adjoint_audit"], "block audit")
    _validate_internal_fingerprint(payload["gates"], "gate audit")
    top = payload["gates"].get("top_level_gates")
    subchecks = payload["gates"].get("subchecks")
    if set(top or {}) != set(HARD_GATE_IDS) or set(subchecks or {}) != set(HARD_GATE_IDS):
        raise LaneCompositionValidationError("hard gate IDs drift")
    recomputed_top = {
        key: all(bool(value) for value in subchecks[key].values()) for key in HARD_GATE_IDS
    }
    if dict(top) != recomputed_top:
        raise LaneCompositionValidationError("top-level gates do not conjoin all subchecks")
    promotion = all(recomputed_top.values()) and payload["gates"]["status"] == "PASS"
    expected_status = PROMOTE_STATUS if promotion else STOP_STATUS
    if payload["promotion_ready"] is not promotion or payload["decision_status"] != expected_status:
        raise LaneCompositionValidationError("promotion decision is not exact gate conjunction")
    if exact_rederive:
        fixture_id = payload["fixture_id"]
        fixture_path = {
            "hackathon_strategy_lane_composition_v0_5_5": DEFAULT_FIXTURE,
            "hackathon_strategy_lane_composition_one_lane_v0_5_5": DEFAULT_ONE_LANE_FIXTURE,
        }.get(fixture_id)
        if fixture_path is None:
            raise LaneCompositionValidationError("bundle fixture ID has no pinned rederivation path")
        expected = _build_bundle_once(load_fixture(fixture_path))
        if canonical_json_bytes(payload) != canonical_json_bytes(expected):
            raise LaneCompositionValidationError(
                "bundle differs from independent deterministic source rederivation"
            )


def self_test() -> JsonObject:
    first = build_bundle(DEFAULT_FIXTURE)
    second = build_bundle(DEFAULT_FIXTURE)
    validate_bundle(first)
    validate_bundle(second)
    mutated = _clone(first)
    mutated["controlled_evaluation"]["lane_outputs"][0]["terminal"][0][
        "value"
    ] += 123.0
    mutated["controlled_evaluation"]["fingerprint_sha256"] = fingerprint(
        _without_fingerprint(mutated["controlled_evaluation"])
    )
    mutated["fingerprint_sha256"] = fingerprint(_without_fingerprint(mutated))
    with network_denied() as counts:
        denied = build_bundle(DEFAULT_FIXTURE)
    fixture = load_fixture(DEFAULT_FIXTURE)
    permutation_results = [
        _build_bundle_once(fixture, lane_order_override=permutation)
        for permutation in itertools.permutations(fixture["lane_ids"])
    ]
    all_six_results_exact = len(permutation_results) == 6 and all(
        canonical_json_bytes(row) == canonical_json_bytes(first)
        for row in permutation_results
    )
    aliases = {
        "all_six_lane_permutations_invariant": all_six_results_exact
        and first["permutation_audit"]["all_permutations_exact"]
        and first["permutation_audit"]["observed_permutation_count"] == 6,
        "artifact_tamper_rejected": _expect_rejected(
            lambda: validate_bundle(mutated), "coherently re-signed bundle artifact"
        ),
        "conflicting_axis_target_rejected": first["tamper_audit"]["subchecks"][
            "conflicting_axis_target_rejected"
        ],
        "conflicting_evidence_hash_rejected": first["tamper_audit"]["subchecks"][
            "conflicting_evidence_hash_rejected"
        ],
        "duplicate_lane_alias_rejected": first["tamper_audit"]["subchecks"][
            "duplicate_lane_alias_bytes_rejected"
        ]
        and first["tamper_audit"]["subchecks"][
            "duplicate_lane_alias_payload_rejected"
        ],
        "forbidden_schema_surface_rejected": first["tamper_audit"]["subchecks"][
            "all_forbidden_nested_schema_keys_rejected"
        ],
        "provider_calls_zero": first["provider_calls"] == 0
        and denied["provider_calls"] == 0,
        "socket_denied": counts["network_calls"] == 0,
        "source_tamper_rejected": all(
            first["tamper_audit"]["subchecks"][key]
            for key in (
                "coherent_payload_resign_rejected",
                "normalized_jacobian_mutation_rejected",
                "schedule_swap_rejected",
                "source_path_swap_rejected",
                "source_payload_fingerprint_tamper_rejected",
            )
        ),
        "two_build_byte_identical": canonical_json_bytes(first)
        == canonical_json_bytes(second)
        == canonical_json_bytes(denied),
    }
    top = dict(first["gates"]["top_level_gates"])
    status = "PASS" if all(top.values()) and all(aliases.values()) else "FAIL"
    payload = {
        "bundle_fingerprint_sha256": first["fingerprint_sha256"],
        "decision_status": PROMOTE_STATUS if status == "PASS" else STOP_STATUS,
        "network_calls": 0,
        "promotion_ready": status == "PASS",
        "provider_calls": 0,
        "schema_version": SELF_TEST_SCHEMA_VERSION,
        "status": status,
        "subchecks": aliases,
        "top_level_gates": top,
    }
    return _with_fingerprint(payload)


def _pretty_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
    ) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="build the canonical bundle")
    build.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    subparsers.add_parser("self-test", help="run strict network-zero gates")
    validate = subparsers.add_parser("validate", help="reload and rederive a bundle JSON")
    validate.add_argument("--input-json", type=Path, required=True)
    compile_only = subparsers.add_parser("compile", help="compile ledger/lanes/junction")
    compile_only.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "build":
        print(_pretty_json(build_bundle(args.fixture)), end="")
        return 0
    if args.command == "self-test":
        result = self_test()
        print(_pretty_json(result), end="")
        return 0 if result["status"] == "PASS" else 1
    if args.command == "validate":
        value, _raw = _strict_load(args.input_json)
        validate_bundle(value)
        print(_pretty_json({"status": "PASS", "fingerprint_sha256": value["fingerprint_sha256"]}), end="")
        return 0
    if args.command == "compile":
        fixture = load_fixture(args.fixture)
        source, ledger, lanes, clauses = compile_bundle(fixture)
        print(
            _pretty_json(
                {
                    "clause_count": len(clauses),
                    "lane_ids": [lane.lane_id for lane in lanes],
                    "ledger_fingerprint_sha256": ledger["fingerprint_sha256"],
                    "source_gate_fingerprint_sha256": source["fingerprint_sha256"],
                    "status": "PASS",
                }
            ),
            end="",
        )
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
