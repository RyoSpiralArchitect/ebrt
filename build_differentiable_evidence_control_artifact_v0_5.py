#!/usr/bin/env python3
"""Build the deterministic, network-zero EBRT v0.5 mechanism evidence bundle.

The builder is intentionally narrower than the controller core.  It verifies one
exact policy lock, two frozen public-graph fixtures, and two lineage-only source
references; runs the core's offline self-tests; optimizes the event and no-event
fixtures; and publishes a same-runtime byte-reproducible evidence bundle.

No provider is called.  The v0.1 implementation and v0.4.1 aperture manifest are
hashed lineage references only and never enter the controller computation.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import json
import math
import os
import platform
import re
import shutil
import socket
import tempfile
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

import differentiable_evidence_controller_v0_5 as core
import torch


ROOT = Path(__file__).resolve().parent
BUILDER_PATH = Path(__file__).resolve()
LOCK_PATH = ROOT / "policy_lock_differentiable_evidence_controller_v0_5.json"

LOCK_SCHEMA_VERSION = "ebrt-differentiable-evidence-control-policy-lock-v0.5.0"
LOCK_STATUS = "LOCKED_MECHANISM_ONLY"
MANIFEST_SCHEMA_VERSION = "ebrt-differentiable-evidence-control-manifest-v0.5.0"
SELF_TEST_SCHEMA_VERSION = "ebrt-differentiable-evidence-control-self-test-v0.5.0"
BUNDLE_STATUS = "COMPLETE_MECHANISM_ONLY_NETWORK_ZERO"
ARTIFACT_DIRECTORY = "artifacts/differentiable_evidence_control_v0_5"
ARTIFACT_FILES = (
    "event_control_map.json",
    "no_event_control_map.json",
    "self_test.json",
    "mechanism_report.md",
)
MANIFEST_FILENAME = "manifest.json"

CONTROLLER_KEYS = {
    "core_path",
    "core_sha256",
    "controller_name",
    "controller_version",
    "graph_schema_version",
    "control_map_schema_version",
    "dtype",
    "gate_parameterization",
    "claim_activation",
    "control_regularizer",
    "optimizer",
    "randomness",
    "config",
    "finite_difference",
    "padding_invariance",
    "canonicalization",
    "projection",
}
CONFIG_KEYS = {
    "revision_steps",
    "learning_rate",
    "revision_consistency_weight",
    "support_preservation_weight",
    "invalidation_suppression_weight",
    "stable_claim_drift_weight",
    "control_l2_weight",
    "max_control_l2_norm",
    "role_delta",
    "gate_epsilon",
    "acceptance_tolerance",
    "numeric_precision",
}
FINITE_DIFFERENCE_TERMS = (
    "revision_consistency",
    "support_preservation",
    "invalidation_suppression",
    "stable_claim_drift",
    "control_l2",
    "total",
)
EXPECTED_CANONICALIZATION = {
    "encoding": "utf-8",
    "ensure_ascii": False,
    "sort_keys": True,
    "separators": [",", ":"],
    "allow_nan": False,
    "trailing_newline": True,
}
EXPECTED_PROJECTION = {
    "role_delta": core.ControllerConfig().role_delta,
    "numeric_precision": core.ControllerConfig().numeric_precision,
    "stable_order": ["ordinal", "evidence_id"],
}
EXPECTED_IDENTITY = {
    "controller_name": core.CONTROLLER_NAME,
    "controller_version": core.CONTROLLER_VERSION,
    "graph_schema_version": core.GRAPH_SCHEMA_VERSION,
    "control_map_schema_version": core.CONTROL_MAP_SCHEMA_VERSION,
    "dtype": "float64",
    "gate_parameterization": "g=2*sigmoid(u)",
    "claim_activation": "h=tanh(A^T*g)",
    "control_regularizer": core.CONTROL_REGULARIZER,
    "optimizer": "Adam",
    "randomness": "deterministic_no_rng",
}
EXPECTED_LINEAGE_RELATIONSHIPS = {
    "v0_1_impl": (
        "historical differentiable mechanism reference only; not an optimization input"
    ),
    "v0_4_1_manifest": (
        "historical aperture observation reference only; not an optimization input"
    ),
}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ArtifactValidationError(ValueError):
    """Raised when the locked bundle contract or generated evidence is invalid."""


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


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _observed_runtime() -> dict[str, str]:
    """Record, but do not generalize beyond, the byte-reproduction runtime."""

    return {
        "python": platform.python_version(),
        "torch": str(torch.__version__),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
    }


def _load_json_exact_bytes(value: bytes, label: str) -> Any:
    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, child in pairs:
            if key in output:
                raise ArtifactValidationError(f"{label}: duplicate JSON key {key!r}")
            output[key] = child
        return output

    try:
        return json.loads(
            value.decode("utf-8"), object_pairs_hook=reject_duplicate_keys
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtifactValidationError(f"{label}: invalid UTF-8 JSON: {exc}") from exc


def _load_json_exact(path: Path) -> Any:
    return _load_json_exact_bytes(path.read_bytes(), str(path))


def _exact_mapping(value: Any, label: str, expected: set[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ArtifactValidationError(f"{label}: expected object")
    if any(not isinstance(key, str) for key in value):
        raise ArtifactValidationError(f"{label}: object keys must be strings")
    actual = set(value)
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if missing or unknown:
        details: list[str] = []
        if missing:
            details.append(f"missing keys={missing}")
        if unknown:
            details.append(f"unknown keys={unknown}")
        raise ArtifactValidationError(f"{label}: " + "; ".join(details))
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ArtifactValidationError(
            f"{label}: expected nonempty string without edge whitespace"
        )
    return value


def _boolean(value: Any, label: str) -> bool:
    if type(value) is not bool:
        raise ArtifactValidationError(f"{label}: expected boolean")
    return value


def _integer(value: Any, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ArtifactValidationError(f"{label}: expected integer >= {minimum}")
    return value


def _sha256_string(value: Any, label: str) -> str:
    digest = _string(value, label)
    if _SHA256_RE.fullmatch(digest) is None:
        raise ArtifactValidationError(f"{label}: expected lowercase SHA-256")
    return digest


def _unique_string_list(value: Any, label: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list):
        raise ArtifactValidationError(f"{label}: expected array")
    output = [_string(item, f"{label}[{index}]") for index, item in enumerate(value)]
    if nonempty and not output:
        raise ArtifactValidationError(f"{label}: must not be empty")
    if len(set(output)) != len(output):
        raise ArtifactValidationError(f"{label}: duplicates are forbidden")
    return output


def _repo_path(value: Any, label: str) -> Path:
    relative_text = _string(value, label)
    relative = Path(relative_text)
    if relative.is_absolute():
        raise ArtifactValidationError(f"{label}: must be repository-relative")
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise ArtifactValidationError(f"{label}: escaped repository root")
    return path


def _require_exact_json(value: Any, expected: Any, label: str) -> None:
    if _canonical_json_bytes(value) != _canonical_json_bytes(expected):
        raise ArtifactValidationError(f"{label}: changed from the locked exact value")


def _reject_time_metadata_keys(value: Any, path: str = "manifest") -> None:
    """Reject actual time metadata without flagging human-readable check labels."""

    forbidden = {
        "timestamp",
        "timestamp_utc",
        "generated_at",
        "created_at",
        "updated_at",
        "build_time",
        "build_timestamp",
    }
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in forbidden:
                raise ArtifactValidationError(f"{path}.{key}: time metadata forbidden")
            _reject_time_metadata_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_time_metadata_keys(child, f"{path}[{index}]")


def _validate_pinned_path(path_value: Any, digest_value: Any, label: str) -> Path:
    path = _repo_path(path_value, f"{label}.path")
    expected = _sha256_string(digest_value, f"{label}.sha256")
    if not path.is_file():
        raise ArtifactValidationError(
            f"{label}: missing pinned file {path.relative_to(ROOT)}"
        )
    observed = _sha256(path)
    if observed != expected:
        raise ArtifactValidationError(
            f"{label}: SHA-256 mismatch expected={expected} observed={observed}"
        )
    return path


def _validate_lock_mapping(value: Any) -> dict[str, Any]:
    lock = _exact_mapping(
        value,
        "policy lock",
        {
            "schema_version",
            "status",
            "controller",
            "fixtures",
            "lineage_reference_only",
            "artifact",
            "claim_boundary",
        },
    )
    if lock["schema_version"] != LOCK_SCHEMA_VERSION:
        raise ArtifactValidationError("policy lock: unexpected schema_version")
    if lock["status"] != LOCK_STATUS:
        raise ArtifactValidationError("policy lock: mechanism-only status changed")

    controller = _exact_mapping(lock["controller"], "controller", CONTROLLER_KEYS)
    if controller["core_path"] != "differentiable_evidence_controller_v0_5.py":
        raise ArtifactValidationError("controller.core_path changed")
    _sha256_string(controller["core_sha256"], "controller.core_sha256")
    for key, expected in EXPECTED_IDENTITY.items():
        if controller[key] != expected:
            raise ArtifactValidationError(f"controller.{key}: unexpected value")

    config = _exact_mapping(controller["config"], "controller.config", CONFIG_KEYS)
    _require_exact_json(config, core.ControllerConfig().to_dict(), "controller.config")
    core.ControllerConfig(**dict(config)).validate()

    finite_difference = _exact_mapping(
        controller["finite_difference"],
        "controller.finite_difference",
        {"epsilon", "absolute_tolerance", "terms"},
    )
    expected_fd = {
        "epsilon": core.FINITE_DIFFERENCE_EPSILON,
        "absolute_tolerance": core.FINITE_DIFFERENCE_ABS_TOLERANCE,
        "terms": list(FINITE_DIFFERENCE_TERMS),
    }
    _require_exact_json(finite_difference, expected_fd, "controller.finite_difference")
    padding_invariance = _exact_mapping(
        controller["padding_invariance"],
        "controller.padding_invariance",
        {"extra_nodes", "absolute_tolerance"},
    )
    _require_exact_json(
        padding_invariance,
        {
            "extra_nodes": core.PADDING_INVARIANCE_EXTRA_NODES,
            "absolute_tolerance": core.PADDING_INVARIANCE_ABS_TOLERANCE,
        },
        "controller.padding_invariance",
    )
    canonicalization = _exact_mapping(
        controller["canonicalization"],
        "controller.canonicalization",
        {
            "encoding",
            "ensure_ascii",
            "sort_keys",
            "separators",
            "allow_nan",
            "trailing_newline",
        },
    )
    _require_exact_json(
        canonicalization,
        EXPECTED_CANONICALIZATION,
        "controller.canonicalization",
    )
    projection = _exact_mapping(
        controller["projection"],
        "controller.projection",
        {"role_delta", "numeric_precision", "stable_order"},
    )
    _require_exact_json(projection, EXPECTED_PROJECTION, "controller.projection")

    fixtures = _exact_mapping(lock["fixtures"], "fixtures", {"event", "no_event"})
    for fixture_name, expected_triggered in (("event", True), ("no_event", False)):
        spec = _exact_mapping(
            fixtures[fixture_name],
            f"fixtures.{fixture_name}",
            {
                "path",
                "sha256",
                "semantic_payload_sha256",
                "graph_id",
                "event_triggered",
            },
        )
        _string(spec["path"], f"fixtures.{fixture_name}.path")
        _sha256_string(spec["sha256"], f"fixtures.{fixture_name}.sha256")
        _sha256_string(
            spec["semantic_payload_sha256"],
            f"fixtures.{fixture_name}.semantic_payload_sha256",
        )
        _string(spec["graph_id"], f"fixtures.{fixture_name}.graph_id")
        if (
            _boolean(
                spec["event_triggered"], f"fixtures.{fixture_name}.event_triggered"
            )
            is not expected_triggered
        ):
            raise ArtifactValidationError(
                f"fixtures.{fixture_name}.event_triggered changed"
            )
    if fixtures["event"]["path"] == fixtures["no_event"]["path"]:
        raise ArtifactValidationError("event and no-event fixtures must be distinct")
    if fixtures["event"]["graph_id"] == fixtures["no_event"]["graph_id"]:
        raise ArtifactValidationError("event and no-event graph IDs must be distinct")

    lineage = _exact_mapping(
        lock["lineage_reference_only"],
        "lineage_reference_only",
        {"v0_1_impl", "v0_4_1_manifest"},
    )
    for source_name, expected_relationship in EXPECTED_LINEAGE_RELATIONSHIPS.items():
        spec = _exact_mapping(
            lineage[source_name],
            f"lineage_reference_only.{source_name}",
            {"path", "sha256", "relationship"},
        )
        _string(spec["path"], f"lineage_reference_only.{source_name}.path")
        _sha256_string(spec["sha256"], f"lineage_reference_only.{source_name}.sha256")
        if spec["relationship"] != expected_relationship:
            raise ArtifactValidationError(
                f"lineage_reference_only.{source_name}.relationship changed"
            )

    artifact = _exact_mapping(
        lock["artifact"], "artifact", {"directory", "files", "network_calls"}
    )
    if artifact["directory"] != ARTIFACT_DIRECTORY:
        raise ArtifactValidationError("artifact.directory changed")
    if _unique_string_list(artifact["files"], "artifact.files") != list(ARTIFACT_FILES):
        raise ArtifactValidationError("artifact.files changed or reordered")
    if _integer(artifact["network_calls"], "artifact.network_calls") != 0:
        raise ArtifactValidationError("artifact.network_calls must remain zero")
    _unique_string_list(lock["claim_boundary"], "claim_boundary", nonempty=True)
    return copy.deepcopy(dict(lock))


def _load_lock() -> dict[str, Any]:
    if not LOCK_PATH.is_file():
        raise ArtifactValidationError(f"missing policy lock: {LOCK_PATH}")
    lock = _validate_lock_mapping(_load_json_exact(LOCK_PATH))
    controller = lock["controller"]
    core_path = _validate_pinned_path(
        controller["core_path"], controller["core_sha256"], "controller core"
    )
    imported_path = Path(core.__file__).resolve()
    if imported_path != core_path:
        raise ArtifactValidationError(
            "imported controller core does not match the locked repository path"
        )
    for source_name, spec in lock["lineage_reference_only"].items():
        _validate_pinned_path(
            spec["path"], spec["sha256"], f"lineage_reference_only.{source_name}"
        )
    return lock


def _validate_fixture_value(
    value: Any,
    raw_bytes: bytes,
    spec: Mapping[str, Any],
    label: str,
) -> core.PublicSemanticGraph:
    if _sha256_bytes(raw_bytes) != spec["sha256"]:
        raise ArtifactValidationError(f"{label}: full fixture SHA-256 mismatch")
    try:
        graph = core.PublicSemanticGraph.from_mapping(value)
    except (core.SchemaValidationError, ValueError) as exc:
        raise ArtifactValidationError(f"{label}: invalid public graph: {exc}") from exc
    if graph.graph_id != spec["graph_id"]:
        raise ArtifactValidationError(f"{label}: graph_id changed")
    if graph.revision_event.triggered is not spec["event_triggered"]:
        raise ArtifactValidationError(f"{label}: event_triggered changed")
    semantic_digest = graph.semantic_payload_sha256()
    if semantic_digest != spec["semantic_payload_sha256"]:
        raise ArtifactValidationError(f"{label}: semantic payload SHA-256 changed")
    if graph.provenance.semantic_payload_sha256 != semantic_digest:
        raise ArtifactValidationError(
            f"{label}: provenance is detached from the semantic payload"
        )
    return graph


def _load_fixture(
    spec: Mapping[str, Any], label: str
) -> tuple[Path, core.PublicSemanticGraph]:
    path = _repo_path(spec["path"], f"{label}.path")
    if not path.is_file():
        raise ArtifactValidationError(f"{label}: missing fixture {path}")
    raw_bytes = path.read_bytes()
    value = _load_json_exact_bytes(raw_bytes, label)
    graph = _validate_fixture_value(value, raw_bytes, spec, label)
    return path, graph


@contextlib.contextmanager
def _network_guard() -> Iterator[None]:
    original_socket = socket.socket
    original_create_connection = socket.create_connection

    def blocked(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("network access attempted by network-zero builder")

    socket.socket = blocked  # type: ignore[assignment]
    socket.create_connection = blocked  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket = original_socket  # type: ignore[assignment]
        socket.create_connection = original_create_connection  # type: ignore[assignment]


def _validate_control_map(
    payload: Any,
    canonical_bytes: bytes,
    graph: core.PublicSemanticGraph,
    lock: Mapping[str, Any],
    *,
    event_expected: bool,
) -> dict[str, Any]:
    value = _exact_mapping(
        payload,
        f"control map {graph.graph_id}",
        {
            "schema_version",
            "controller",
            "source",
            "status",
            "controls",
            "surrogate",
            "optimization",
            "claim_boundary",
            "fingerprint_sha256",
        },
    )
    if value["schema_version"] != core.CONTROL_MAP_SCHEMA_VERSION:
        raise ArtifactValidationError("control-map schema changed")
    if canonical_bytes != _canonical_json_bytes(value, trailing_newline=True):
        raise ArtifactValidationError(
            f"control map {graph.graph_id}: canonical bytes changed"
        )
    map_controller = _exact_mapping(
        value["controller"],
        f"control map {graph.graph_id}.controller",
        {
            "name",
            "version",
            "dtype",
            "gate_parameterization",
            "claim_activation",
            "control_regularizer",
            "optimizer",
            "randomness",
            "best_checkpoint_rule",
            "acceptance_tolerance",
            "gradient_boundary",
        },
    )
    for map_key, lock_key in (
        ("name", "controller_name"),
        ("version", "controller_version"),
        ("dtype", "dtype"),
        ("gate_parameterization", "gate_parameterization"),
        ("claim_activation", "claim_activation"),
        ("control_regularizer", "control_regularizer"),
        ("optimizer", "optimizer"),
        ("randomness", "randomness"),
    ):
        if map_controller[map_key] != lock["controller"][lock_key]:
            raise ArtifactValidationError(
                f"control map {graph.graph_id}.controller.{map_key} changed"
            )
    if (
        map_controller["acceptance_tolerance"]
        != lock["controller"]["config"]["acceptance_tolerance"]
    ):
        raise ArtifactValidationError("control-map acceptance tolerance changed")
    fingerprint = _sha256_string(
        value["fingerprint_sha256"], f"control map {graph.graph_id}.fingerprint"
    )
    without_fingerprint = dict(value)
    without_fingerprint.pop("fingerprint_sha256")
    if fingerprint != _sha256_bytes(_canonical_json_bytes(without_fingerprint)):
        raise ArtifactValidationError(
            f"control map {graph.graph_id}: fingerprint mismatch"
        )

    source = _exact_mapping(
        value["source"],
        f"control map {graph.graph_id}.source",
        {"graph_id", "semantic_payload_sha256", "event_id", "event_triggered"},
    )
    if source != {
        "graph_id": graph.graph_id,
        "semantic_payload_sha256": graph.semantic_payload_sha256(),
        "event_id": graph.revision_event.event_id,
        "event_triggered": event_expected,
    }:
        raise ArtifactValidationError(
            f"control map {graph.graph_id}: source lineage changed"
        )
    optimization = _exact_mapping(
        value["optimization"],
        f"control map {graph.graph_id}.optimization",
        {
            "config",
            "backward_calls",
            "accepted",
            "rolled_back",
            "best_iteration",
            "control_l2_norm",
            "max_observed_control_l2_norm",
            "min_observed_gate",
            "max_observed_gate",
        },
    )
    _require_exact_json(
        optimization["config"], lock["controller"]["config"], "optimization.config"
    )
    controls = value["controls"]
    if not isinstance(controls, list):
        raise ArtifactValidationError("control-map controls must be an array")
    expected_nodes = sorted(
        graph.evidence_nodes, key=lambda node: (node.ordinal, node.evidence_id)
    )
    expected_order = [node.evidence_id for node in expected_nodes]
    if len(controls) != len(expected_nodes):
        raise ArtifactValidationError("control-map evidence cardinality changed")
    observed_order: list[str] = []
    for index, control_value in enumerate(controls):
        control = _exact_mapping(
            control_value,
            f"control[{index}]",
            {"evidence_id", "ordinal", "role", "gate", "delta_from_neutral"},
        )
        evidence_id = _string(control["evidence_id"], f"control[{index}].evidence_id")
        observed_order.append(evidence_id)
        if _integer(control["ordinal"], f"control[{index}].ordinal", minimum=1) != (
            expected_nodes[index].ordinal
        ):
            raise ArtifactValidationError(
                f"control[{index}].ordinal detached from source evidence"
            )
        gate = control["gate"]
        delta = control["delta_from_neutral"]
        if isinstance(gate, bool) or not isinstance(gate, (int, float)):
            raise ArtifactValidationError(f"control[{index}].gate must be numeric")
        if isinstance(delta, bool) or not isinstance(delta, (int, float)):
            raise ArtifactValidationError(
                f"control[{index}].delta_from_neutral must be numeric"
            )
        if not math.isfinite(float(gate)) or not 0.0 < float(gate) < 2.0:
            raise ArtifactValidationError(f"control[{index}].gate escaped (0,2)")
        rounded_delta = round(
            float(gate) - 1.0, lock["controller"]["projection"]["numeric_precision"]
        )
        if rounded_delta == -0.0:
            rounded_delta = 0.0
        if float(delta) != rounded_delta:
            raise ArtifactValidationError(
                f"control[{index}].delta_from_neutral detached from gate"
            )
        role_delta = lock["controller"]["projection"]["role_delta"]
        expected_role = (
            "suppress"
            if float(gate) < 1.0 - role_delta
            else "boost"
            if float(gate) > 1.0 + role_delta
            else "preserve"
        )
        if control["role"] != expected_role:
            raise ArtifactValidationError(f"control[{index}].role detached from gate")
    if observed_order != expected_order:
        raise ArtifactValidationError("control-map evidence order changed")

    max_control_norm = float(lock["controller"]["config"]["max_control_l2_norm"])
    for field in (
        "control_l2_norm",
        "max_observed_control_l2_norm",
        "min_observed_gate",
        "max_observed_gate",
    ):
        observed = optimization[field]
        if isinstance(observed, bool) or not isinstance(observed, (int, float)):
            raise ArtifactValidationError(f"optimization.{field} must be numeric")
        if not math.isfinite(float(observed)):
            raise ArtifactValidationError(f"optimization.{field} must be finite")
    if not 0.0 <= float(optimization["control_l2_norm"]) <= max_control_norm:
        raise ArtifactValidationError("final control L2 escaped the locked bound")
    if not (
        0.0 <= float(optimization["max_observed_control_l2_norm"]) <= max_control_norm
    ):
        raise ArtifactValidationError("observed control L2 escaped the locked bound")
    if not (
        0.0
        < float(optimization["min_observed_gate"])
        <= float(optimization["max_observed_gate"])
        < 2.0
    ):
        raise ArtifactValidationError("observed gate range escaped the open bound")

    if event_expected:
        if value["status"] != "ACCEPTED_LOCAL_CONTROL":
            raise ArtifactValidationError("event control was not accepted")
        if optimization["accepted"] is not True:
            raise ArtifactValidationError("event accepted flag is false")
        if (
            optimization["backward_calls"]
            != lock["controller"]["config"]["revision_steps"]
        ):
            raise ArtifactValidationError("event backward-call count changed")
        before = value["surrogate"]["objective_before"]["total"]
        after = value["surrogate"]["objective_after"]["total"]
        if not float(after) < float(before):
            raise ArtifactValidationError("event objective did not decrease")
    else:
        if value["status"] != "NO_EVENT_IDENTITY":
            raise ArtifactValidationError("no-event control is not identity")
        if optimization["accepted"] is not False:
            raise ArtifactValidationError("no-event control was marked accepted")
        if optimization["backward_calls"] != 0:
            raise ArtifactValidationError("no-event control invoked backward")
        for control in controls:
            if (
                float(control["gate"]) != 1.0
                or float(control["delta_from_neutral"]) != 0.0
                or control["role"] != "preserve"
            ):
                raise ArtifactValidationError("no-event control moved from identity")
        if (
            value["surrogate"]["objective_before"]
            != value["surrogate"]["objective_after"]
        ):
            raise ArtifactValidationError("no-event objective changed")
    return copy.deepcopy(dict(value))


def _source_ledger(
    lock: Mapping[str, Any], fixture_paths: Mapping[str, Path]
) -> dict[str, str]:
    controller = lock["controller"]
    lineage = lock["lineage_reference_only"]
    ledger = {
        str(LOCK_PATH.relative_to(ROOT)): _sha256(LOCK_PATH),
        str(BUILDER_PATH.relative_to(ROOT)): _sha256(BUILDER_PATH),
        controller["core_path"]: controller["core_sha256"],
        lock["fixtures"]["event"]["path"]: _sha256(fixture_paths["event"]),
        lock["fixtures"]["no_event"]["path"]: _sha256(fixture_paths["no_event"]),
        lineage["v0_1_impl"]["path"]: lineage["v0_1_impl"]["sha256"],
        lineage["v0_4_1_manifest"]["path"]: lineage["v0_4_1_manifest"]["sha256"],
    }
    if len(ledger) != 7:
        raise ArtifactValidationError("source ledger contains duplicate paths")
    return dict(sorted(ledger.items()))


def _build_self_test_artifact(
    lock: Mapping[str, Any],
    core_report: Mapping[str, Any],
    event_map: Mapping[str, Any],
    no_event_map: Mapping[str, Any],
) -> dict[str, Any]:
    if core_report.get("status") != "PASS":
        raise ArtifactValidationError("controller core self-test did not pass")
    metrics = _exact_mapping(
        core_report.get("mechanism_metrics"),
        "core self-test mechanism_metrics",
        {
            "semantic_payload_sha256",
            "max_finite_difference_error",
            "finite_difference_error_by_term",
            "finite_difference_epsilon",
            "finite_difference_abs_tolerance",
            "padding_invariance_extra_nodes",
            "padding_invariance_abs_tolerance",
            "max_disconnected_padding_gate_error",
            "energy_before",
            "energy_after",
            "control_l2_norm",
            "max_observed_control_l2_norm",
            "backward_calls",
            "control_map_fingerprint",
            "terminal_credit_gradient",
        },
    )
    if metrics["finite_difference_epsilon"] != core.FINITE_DIFFERENCE_EPSILON:
        raise ArtifactValidationError(
            "core self-test finite-difference epsilon changed"
        )
    if (
        metrics["finite_difference_abs_tolerance"]
        != core.FINITE_DIFFERENCE_ABS_TOLERANCE
    ):
        raise ArtifactValidationError(
            "core self-test finite-difference tolerance changed"
        )
    errors = _exact_mapping(
        metrics["finite_difference_error_by_term"],
        "finite_difference_error_by_term",
        set(FINITE_DIFFERENCE_TERMS),
    )
    if set(errors) != set(lock["controller"]["finite_difference"]["terms"]):
        raise ArtifactValidationError("finite-difference term coverage changed")
    if float(metrics["max_finite_difference_error"]) > float(
        lock["controller"]["finite_difference"]["absolute_tolerance"]
    ):
        raise ArtifactValidationError("finite-difference tolerance was exceeded")
    if (
        metrics["padding_invariance_extra_nodes"]
        != lock["controller"]["padding_invariance"]["extra_nodes"]
    ):
        raise ArtifactValidationError("padding-invariance node count changed")
    if (
        metrics["padding_invariance_abs_tolerance"]
        != lock["controller"]["padding_invariance"]["absolute_tolerance"]
    ):
        raise ArtifactValidationError("padding-invariance tolerance changed")
    if float(metrics["max_disconnected_padding_gate_error"]) > float(
        lock["controller"]["padding_invariance"]["absolute_tolerance"]
    ):
        raise ArtifactValidationError("disconnected-padding invariance failed")
    return {
        "schema_version": SELF_TEST_SCHEMA_VERSION,
        "status": "PASS",
        "network_calls": 0,
        "checks": {
            "core_self_test_passed": True,
            "event_fixture_accepted_local_control": (
                event_map["status"] == "ACCEPTED_LOCAL_CONTROL"
            ),
            "event_objective_decreased": (
                event_map["surrogate"]["objective_after"]["total"]
                < event_map["surrogate"]["objective_before"]["total"]
            ),
            "no_event_exact_identity": (
                no_event_map["status"] == "NO_EVENT_IDENTITY"
                and no_event_map["optimization"]["backward_calls"] == 0
            ),
            "finite_difference_term_coverage_exact": True,
            "disconnected_padding_invariance_verified": True,
            "canonical_control_map_projection_verified": True,
            "lineage_sources_excluded_from_controller_inputs": True,
        },
        "fixture_results": {
            "event": {
                "graph_id": event_map["source"]["graph_id"],
                "semantic_payload_sha256": event_map["source"][
                    "semantic_payload_sha256"
                ],
                "status": event_map["status"],
                "backward_calls": event_map["optimization"]["backward_calls"],
                "objective_before": event_map["surrogate"]["objective_before"]["total"],
                "objective_after": event_map["surrogate"]["objective_after"]["total"],
                "control_map_fingerprint": event_map["fingerprint_sha256"],
            },
            "no_event": {
                "graph_id": no_event_map["source"]["graph_id"],
                "semantic_payload_sha256": no_event_map["source"][
                    "semantic_payload_sha256"
                ],
                "status": no_event_map["status"],
                "backward_calls": no_event_map["optimization"]["backward_calls"],
                "objective_before": no_event_map["surrogate"]["objective_before"][
                    "total"
                ],
                "objective_after": no_event_map["surrogate"]["objective_after"][
                    "total"
                ],
                "control_map_fingerprint": no_event_map["fingerprint_sha256"],
            },
        },
        "core_self_test": copy.deepcopy(dict(core_report)),
        "claim_boundary": list(lock["claim_boundary"]),
    }


def _mechanism_report(
    lock: Mapping[str, Any],
    event_map: Mapping[str, Any],
    no_event_map: Mapping[str, Any],
    self_test: Mapping[str, Any],
) -> bytes:
    runtime = _observed_runtime()
    event_before = event_map["surrogate"]["objective_before"]["total"]
    event_after = event_map["surrogate"]["objective_after"]["total"]
    controls = event_map["controls"]
    role_counts = {
        role: sum(1 for control in controls if control["role"] == role)
        for role in ("boost", "suppress", "preserve")
    }
    lines = [
        "# EBRT v0.5.0 Differentiable Evidence Control — Mechanism Evidence",
        "",
        f"Status: `{BUNDLE_STATUS}`",
        "",
        "This is a deterministic, network-zero mechanism bundle over two frozen",
        "synthetic public semantic graphs. It contains no provider generation or",
        "downstream reasoning-quality evaluation.",
        "",
        "## Locked mechanism result",
        "",
        "| Fixture | Event | Status | Backward calls | Objective before | Objective after |",
        "| --- | ---: | --- | ---: | ---: | ---: |",
        (
            f"| `{event_map['source']['graph_id']}` | yes | `{event_map['status']}` | "
            f"{event_map['optimization']['backward_calls']} | {event_before} | "
            f"{event_after} |"
        ),
        (
            f"| `{no_event_map['source']['graph_id']}` | no | "
            f"`{no_event_map['status']}` | "
            f"{no_event_map['optimization']['backward_calls']} | "
            f"{no_event_map['surrogate']['objective_before']['total']} | "
            f"{no_event_map['surrogate']['objective_after']['total']} |"
        ),
        "",
        "The event fixture produced "
        f"{role_counts['boost']} boost, {role_counts['suppress']} suppress, and "
        f"{role_counts['preserve']} preserve projections. The no-event fixture "
        "remained exact identity with zero backward calls.",
        "",
        "## Numerical checks",
        "",
        (
            "The core self-test covered all five locked loss components plus "
            "the weighted total with central finite differences. Maximum "
            "absolute error: "
            f"`{self_test['core_self_test']['mechanism_metrics']['max_finite_difference_error']}` "
            f"(tolerance `{lock['controller']['finite_difference']['absolute_tolerance']}`)."
        ),
        "",
        "Control gates use `g=2*sigmoid(u)`, are projected in stable "
        "`ordinal,evidence_id` order, and cross a non-differentiable canonical JSON "
        "boundary after local optimization.",
        (
            "Adding "
            f"{lock['controller']['padding_invariance']['extra_nodes']} neutral, "
            "edge-less nodes changed every original gate by at most "
            f"`{self_test['core_self_test']['mechanism_metrics']['max_disconnected_padding_gate_error']}` "
            "(tolerance "
            f"`{lock['controller']['padding_invariance']['absolute_tolerance']}`)."
        ),
        "",
        "## Lineage boundary",
        "",
        (f"- v0.1: {lock['lineage_reference_only']['v0_1_impl']['relationship']}."),
        (
            "- v0.4.1: "
            f"{lock['lineage_reference_only']['v0_4_1_manifest']['relationship']}."
        ),
        "",
        "Neither lineage file is loaded into the graph, loss, gradient, or control "
        "projection.",
        "",
        "## Byte-reproduction runtime",
        "",
        (
            f"Python `{runtime['python']}`, PyTorch `{runtime['torch']}`, "
            f"`{runtime['system']} {runtime['release']} {runtime['machine']}`."
        ),
        "",
        "Byte identity is checked within this recorded runtime; no cross-runtime "
        "numerical identity is claimed.",
        "",
        "## Claim boundary",
        "",
    ]
    lines.extend(f"- {item}" for item in lock["claim_boundary"])
    lines.append("")
    return "\n".join(lines).encode("utf-8")


def _manifest(
    lock: Mapping[str, Any],
    artifact_bytes: Mapping[str, bytes],
    fixture_paths: Mapping[str, Path],
) -> dict[str, Any]:
    artifact_hashes = {
        filename: _sha256_bytes(artifact_bytes[filename]) for filename in ARTIFACT_FILES
    }
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "status": BUNDLE_STATUS,
        "runtime_observed": _observed_runtime(),
        "artifact_sha256": artifact_hashes,
        "source_sha256": _source_ledger(lock, fixture_paths),
        "network_calls": 0,
        "controller": {
            "name": lock["controller"]["controller_name"],
            "version": lock["controller"]["controller_version"],
            "config": copy.deepcopy(lock["controller"]["config"]),
            "finite_difference": copy.deepcopy(lock["controller"]["finite_difference"]),
            "padding_invariance": copy.deepcopy(
                lock["controller"]["padding_invariance"]
            ),
            "canonicalization": copy.deepcopy(lock["controller"]["canonicalization"]),
            "projection": copy.deepcopy(lock["controller"]["projection"]),
        },
        "fixtures": {
            name: {
                "path": lock["fixtures"][name]["path"],
                "sha256": lock["fixtures"][name]["sha256"],
                "semantic_payload_sha256": lock["fixtures"][name][
                    "semantic_payload_sha256"
                ],
                "graph_id": lock["fixtures"][name]["graph_id"],
                "event_triggered": lock["fixtures"][name]["event_triggered"],
            }
            for name in ("event", "no_event")
        },
        "validation": {
            "policy_lock_exact": True,
            "source_hashes_verified": True,
            "public_graph_schema_and_provenance_verified": True,
            "core_self_test_passed": True,
            "finite_difference_constants_and_terms_exact": True,
            "event_control_accepted_and_objective_decreased": True,
            "no_event_identity_and_zero_backward_calls": True,
            "canonical_projection_and_fingerprints_verified": True,
            "lineage_references_excluded_from_controller_inputs": True,
            "manifest_has_no_timestamp": True,
        },
        "claim_boundary": list(lock["claim_boundary"]),
    }


def _validate_manifest(
    value: Any,
    artifact_bytes: Mapping[str, bytes],
    lock: Mapping[str, Any],
    fixture_paths: Mapping[str, Path],
) -> dict[str, Any]:
    manifest = _exact_mapping(
        value,
        "manifest",
        {
            "schema_version",
            "status",
            "runtime_observed",
            "artifact_sha256",
            "source_sha256",
            "network_calls",
            "controller",
            "fixtures",
            "validation",
            "claim_boundary",
        },
    )
    if manifest["schema_version"] != MANIFEST_SCHEMA_VERSION:
        raise ArtifactValidationError("manifest schema changed")
    if manifest["status"] != BUNDLE_STATUS:
        raise ArtifactValidationError("manifest status changed")
    if _integer(manifest["network_calls"], "manifest.network_calls") != 0:
        raise ArtifactValidationError("manifest network_calls must remain zero")
    artifact_hashes = _exact_mapping(
        manifest["artifact_sha256"], "manifest.artifact_sha256", set(ARTIFACT_FILES)
    )
    for filename in ARTIFACT_FILES:
        expected = _sha256_bytes(artifact_bytes[filename])
        if artifact_hashes[filename] != expected:
            raise ArtifactValidationError(
                f"manifest artifact hash mismatch: {filename}"
            )
    if MANIFEST_FILENAME in artifact_hashes:
        raise ArtifactValidationError("manifest must not hash itself")
    _require_exact_json(
        manifest["source_sha256"],
        _source_ledger(lock, fixture_paths),
        "manifest.source_sha256",
    )
    expected_manifest = _manifest(lock, artifact_bytes, fixture_paths)
    _require_exact_json(manifest, expected_manifest, "manifest")
    _reject_time_metadata_keys(manifest)
    return copy.deepcopy(dict(manifest))


def _materialize(lock: Mapping[str, Any]) -> dict[str, bytes]:
    fixture_paths: dict[str, Path] = {}
    graphs: dict[str, core.PublicSemanticGraph] = {}
    for name in ("event", "no_event"):
        fixture_paths[name], graphs[name] = _load_fixture(
            lock["fixtures"][name], f"fixtures.{name}"
        )

    core_report = core.run_self_tests()
    config = core.ControllerConfig(**dict(lock["controller"]["config"]))
    controller = core.DifferentiableEvidenceController(config)
    event_result = controller.optimize(graphs["event"])
    no_event_result = controller.optimize(graphs["no_event"])
    event_bytes = event_result.canonical_control_map_bytes()
    no_event_bytes = no_event_result.canonical_control_map_bytes()
    event_map = _validate_control_map(
        event_result.to_control_map(),
        event_bytes,
        graphs["event"],
        lock,
        event_expected=True,
    )
    no_event_map = _validate_control_map(
        no_event_result.to_control_map(),
        no_event_bytes,
        graphs["no_event"],
        lock,
        event_expected=False,
    )
    self_test_value = _build_self_test_artifact(
        lock, core_report, event_map, no_event_map
    )
    self_test_bytes = _pretty_json_bytes(self_test_value)
    report_bytes = _mechanism_report(lock, event_map, no_event_map, self_test_value)
    artifacts = {
        "event_control_map.json": event_bytes,
        "no_event_control_map.json": no_event_bytes,
        "self_test.json": self_test_bytes,
        "mechanism_report.md": report_bytes,
    }
    manifest_value = _manifest(lock, artifacts, fixture_paths)
    _validate_manifest(manifest_value, artifacts, lock, fixture_paths)
    artifacts[MANIFEST_FILENAME] = _pretty_json_bytes(manifest_value)
    return artifacts


def _artifact_directory(lock: Mapping[str, Any]) -> Path:
    return _repo_path(lock["artifact"]["directory"], "artifact.directory")


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


def _publish_bundle(target: Path, artifacts: Mapping[str, bytes]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(dir=target.parent, prefix=f".{target.name}.staging.")
    )
    backup: Path | None = None
    try:
        for filename in (*ARTIFACT_FILES, MANIFEST_FILENAME):
            _write_fsynced(staging / filename, artifacts[filename])
        _fsync_directory(staging)
        if target.exists():
            if not target.is_dir() or target.is_symlink():
                raise ArtifactValidationError(
                    f"artifact target exists but is not a directory: {target}"
                )
            backup = Path(
                tempfile.mkdtemp(dir=target.parent, prefix=f".{target.name}.backup.")
            )
            backup.rmdir()
            os.replace(target, backup)
        try:
            os.replace(staging, target)
            _fsync_directory(target.parent)
        except BaseException:
            if backup is not None and backup.exists() and not target.exists():
                os.replace(backup, target)
                backup = None
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
            else:
                shutil.rmtree(backup)


def _read_bundle(directory: Path) -> dict[str, bytes]:
    expected_names = {*ARTIFACT_FILES, MANIFEST_FILENAME}
    if not directory.is_dir():
        raise ArtifactValidationError(f"missing artifact directory: {directory}")
    actual_names = {path.name for path in directory.iterdir()}
    if actual_names != expected_names:
        raise ArtifactValidationError(
            "artifact directory file set changed: "
            f"expected={sorted(expected_names)} observed={sorted(actual_names)}"
        )
    return {name: (directory / name).read_bytes() for name in sorted(expected_names)}


def _validate_bundle_bytes(
    bundle: Mapping[str, bytes], lock: Mapping[str, Any]
) -> None:
    expected_names = {*ARTIFACT_FILES, MANIFEST_FILENAME}
    if set(bundle) != expected_names:
        raise ArtifactValidationError("bundle file set changed")
    fixture_paths = {
        name: _repo_path(lock["fixtures"][name]["path"], f"fixtures.{name}.path")
        for name in ("event", "no_event")
    }
    manifest_value = _load_json_exact_bytes(bundle[MANIFEST_FILENAME], "manifest")
    artifact_bytes = {name: bundle[name] for name in ARTIFACT_FILES}
    _validate_manifest(manifest_value, artifact_bytes, lock, fixture_paths)

    for name, event_expected in (("event", True), ("no_event", False)):
        filename = f"{name}_control_map.json"
        payload = _load_json_exact_bytes(bundle[filename], filename)
        _, graph = _load_fixture(lock["fixtures"][name], f"fixtures.{name}")
        _validate_control_map(
            payload,
            bundle[filename],
            graph,
            lock,
            event_expected=event_expected,
        )
    self_test = _exact_mapping(
        _load_json_exact_bytes(bundle["self_test.json"], "self_test.json"),
        "self_test.json",
        {
            "schema_version",
            "status",
            "network_calls",
            "checks",
            "fixture_results",
            "core_self_test",
            "claim_boundary",
        },
    )
    if self_test["schema_version"] != SELF_TEST_SCHEMA_VERSION:
        raise ArtifactValidationError("self-test schema changed")
    if self_test["status"] != "PASS" or self_test["network_calls"] != 0:
        raise ArtifactValidationError("self-test status/network boundary changed")
    if list(self_test["claim_boundary"]) != list(lock["claim_boundary"]):
        raise ArtifactValidationError("self-test claim boundary changed")
    try:
        report = bundle["mechanism_report.md"].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ArtifactValidationError("mechanism report is not UTF-8") from exc
    if BUNDLE_STATUS not in report:
        raise ArtifactValidationError("mechanism report status is missing")
    for boundary in lock["claim_boundary"]:
        if boundary not in report:
            raise ArtifactValidationError(
                "mechanism report omitted a locked claim boundary"
            )


def build() -> dict[str, str]:
    lock = _load_lock()
    with _network_guard():
        artifacts = _materialize(lock)
    _validate_bundle_bytes(artifacts, lock)
    target = _artifact_directory(lock)
    _publish_bundle(target, artifacts)
    validate()
    return {
        filename: _sha256_bytes(artifacts[filename])
        for filename in (*ARTIFACT_FILES, MANIFEST_FILENAME)
    }


def validate() -> None:
    lock = _load_lock()
    with _network_guard():
        expected = _materialize(lock)
    _validate_bundle_bytes(expected, lock)
    target = _artifact_directory(lock)
    observed = _read_bundle(target)
    _validate_bundle_bytes(observed, lock)
    with tempfile.TemporaryDirectory(prefix="ebrt-v0.5-validate-") as temporary:
        reconstruction = Path(temporary)
        for filename in (*ARTIFACT_FILES, MANIFEST_FILENAME):
            _write_fsynced(reconstruction / filename, expected[filename])
        for filename in (*ARTIFACT_FILES, MANIFEST_FILENAME):
            rebuilt = (reconstruction / filename).read_bytes()
            if rebuilt != observed[filename]:
                raise ArtifactValidationError(
                    f"published {filename} is not byte-identical to recomputation"
                )


def _expect_rejection(label: str, callback: Any) -> None:
    try:
        callback()
    except (ArtifactValidationError, core.SchemaValidationError, ValueError):
        return
    raise AssertionError(f"tamper was accepted: {label}")


def self_test() -> dict[str, Any]:
    lock = _load_lock()
    with _network_guard():
        first = _materialize(lock)
        second = _materialize(lock)
    if first != second:
        raise AssertionError("two network-zero builds were not byte-identical")
    _validate_bundle_bytes(first, lock)

    lock_unknown = copy.deepcopy(lock)
    lock_unknown["controller"]["debug"] = True
    _expect_rejection(
        "unknown nested policy key", lambda: _validate_lock_mapping(lock_unknown)
    )
    lock_config = copy.deepcopy(lock)
    lock_config["controller"]["config"]["revision_steps"] += 1
    _expect_rejection(
        "controller config drift", lambda: _validate_lock_mapping(lock_config)
    )
    lock_projection = copy.deepcopy(lock)
    lock_projection["controller"]["projection"]["stable_order"].reverse()
    _expect_rejection(
        "projection order drift", lambda: _validate_lock_mapping(lock_projection)
    )

    event_path = _repo_path(lock["fixtures"]["event"]["path"], "event fixture")
    event_raw = event_path.read_bytes()
    event_value = _load_json_exact_bytes(event_raw, "event fixture")
    event_tamper = copy.deepcopy(event_value)
    event_tamper["evidence_nodes"][0]["public_summary"] += " tampered"
    tampered_bytes = _pretty_json_bytes(event_tamper)
    _expect_rejection(
        "event fixture byte and provenance tamper",
        lambda: _validate_fixture_value(
            event_tamper,
            tampered_bytes,
            lock["fixtures"]["event"],
            "tampered event fixture",
        ),
    )
    no_event_path = _repo_path(lock["fixtures"]["no_event"]["path"], "no-event fixture")
    no_event_raw = no_event_path.read_bytes()
    no_event_value = _load_json_exact_bytes(no_event_raw, "no-event fixture")
    no_event_tamper = copy.deepcopy(no_event_value)
    no_event_tamper["revision_event"]["triggered"] = True
    _expect_rejection(
        "no-event trigger tamper",
        lambda: _validate_fixture_value(
            no_event_tamper,
            _pretty_json_bytes(no_event_tamper),
            lock["fixtures"]["no_event"],
            "tampered no-event fixture",
        ),
    )

    artifact_tamper = dict(first)
    event_map = _load_json_exact_bytes(
        artifact_tamper["event_control_map.json"], "event control map"
    )
    event_map["controls"][0]["gate"] = 1.5
    artifact_tamper["event_control_map.json"] = _canonical_json_bytes(
        event_map, trailing_newline=True
    )
    _expect_rejection(
        "control-map artifact without manifest update",
        lambda: _validate_bundle_bytes(artifact_tamper, lock),
    )
    manifest_tamper = dict(first)
    manifest = _load_json_exact_bytes(manifest_tamper["manifest.json"], "manifest")
    manifest["network_calls"] = 1
    manifest_tamper["manifest.json"] = _pretty_json_bytes(manifest)
    _expect_rejection(
        "manifest network boundary",
        lambda: _validate_bundle_bytes(manifest_tamper, lock),
    )
    extra_artifact = dict(first)
    extra_artifact["debug.json"] = b"{}\n"
    _expect_rejection(
        "extra artifact file", lambda: _validate_bundle_bytes(extra_artifact, lock)
    )

    return {
        "status": "PASS",
        "self_test": "deterministic_network_zero_bundle",
        "checks": {
            "two_build_byte_identity": True,
            "socket_creation_denied": True,
            "unknown_lock_key_rejected": True,
            "controller_config_tamper_rejected": True,
            "projection_tamper_rejected": True,
            "event_fixture_tamper_rejected": True,
            "no_event_fixture_tamper_rejected": True,
            "artifact_tamper_rejected": True,
            "manifest_network_tamper_rejected": True,
            "extra_artifact_rejected": True,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("build", "validate", "self-test", "all"),
        nargs="?",
        default="all",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "build":
            hashes = build()
            print(
                json.dumps(
                    {"status": "PASS", "artifact_sha256": hashes}, sort_keys=True
                )
            )
        elif args.command == "validate":
            validate()
            print('{"status":"PASS","validation":"byte_identical_recompute"}')
        elif args.command == "self-test":
            print(json.dumps(self_test(), sort_keys=True))
        else:
            hashes = build()
            test_report = self_test()
            print(
                json.dumps(
                    {
                        "status": "PASS",
                        "validation": "build_validate_self_test",
                        "artifact_sha256": hashes,
                        "self_test": test_report["self_test"],
                    },
                    sort_keys=True,
                )
            )
        return 0
    except (OSError, json.JSONDecodeError, ArtifactValidationError, ValueError) as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
