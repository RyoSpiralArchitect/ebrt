#!/usr/bin/env python3
"""Network-zero provider-safe projection for the EBRT v0.6 five-call block.

This module projects the byte-pinned v0.5.5 public lane bundle into five
blinded provider payloads.  It does not call a provider, load semantic gold,
grade an output, or claim that the public control values edit hosted-model
hidden state.  Signed values remain public actuator displacements only.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import socket
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence
from unittest import mock

import benchmark_lane_composition_v0_5_5 as v055_benchmark
import lane_composable_trajectory_v0_5_5 as v055


ROOT = Path(__file__).resolve().parent
DEFAULT_FIXTURE = ROOT / "fixtures" / "hosted_bundle_projection_v0_6.json"
PINNED_FIXTURE_FILE_SHA256 = "cf0a5aa51c50d0a3c79b9ce47380181a2e1de6ba32435e25285aa442b88f4c22"
V055_ARTIFACT_DIR = ROOT / "artifacts" / "lane_composition_v0_5_5"
V053_REGRESSION_PATH = (
    ROOT / "artifacts" / "factorized_lineage_v0_5_3" / "factorized_lineage_regression.json"
)
WALKTHROUGH_CASE_PATH = ROOT / "fixtures" / "hackathon_strategy_walkthrough_v0_5_2.json"

FIXTURE_SCHEMA_VERSION = "ebrt-hosted-bundle-projection-fixture-v0.6"
PROVIDER_PAYLOAD_SCHEMA_VERSION = "ebrt-hosted-bundle-provider-payload-v0.6"
REVISION_PROGRAM_SCHEMA_VERSION = "ebrt-hosted-public-revision-program-v0.6"
PUBLIC_GRAPH_SCHEMA_VERSION = "ebrt-provider-safe-dependency-graph-v0.6"
TREATMENT_KEY_SCHEMA_VERSION = "ebrt-public-treatment-key-v0.6"
PROJECTION_SCHEMA_VERSION = "ebrt-hosted-bundle-projection-v0.6"
MATCH_AUDIT_SCHEMA_VERSION = "ebrt-cd-matched-geometry-audit-v0.6"
SELF_TEST_SCHEMA_VERSION = "ebrt-hosted-bundle-projection-self-test-v0.6"

READY_STATUS = "READY_V0_6_1_FIVE_CALL_PREFLIGHT"
STOP_STATUS = "STOP_V0_6_1_FIVE_CALL_PREFLIGHT"
TREATMENTS = ("P", "A", "B", "C", "D")
POST_EVENT_TREATMENTS = frozenset({"A", "B", "C", "D"})
CONTROL_TREATMENTS = frozenset({"B", "C", "D"})
LANE_IDS = ("correction_early", "correction_late", "stable_constraint")

PROVIDER_INSTRUCTIONS_FRAGMENT = (
    "Use ordered raw evidence as semantic authority. The typed dependency graph "
    "and public actuator rows are external execution metadata, not new evidence, "
    "gold, or hidden-model state. A positive or negative signed_displacement is "
    "only a bounded displacement at its named public actuator; it is not truth, "
    "probability, importance, required support, or permission to override raw "
    "evidence. Explicit invalidation dominates active support. Cite only supplied "
    "evidence IDs and return the strict public decision-state schema."
)

_SITE_PATTERN = re.compile(
    r"^q:(?P<lane>[^:]+):h(?P<horizon>[0-9]{2}):(?P<evidence>R[0-9]+):"
    r"(?P<node_type>support|fact|constraint):(?P<node_name>[^:]+)$"
)

FORBIDDEN_PROVIDER_KEYS = frozenset(
    {
        "adjoint",
        "answer_key",
        "arm",
        "arm_id",
        "blinded_request_id",
        "correct_answer",
        "downstream_grade",
        "downstream_result",
        "evaluation_label",
        "expected_answer",
        "expected_evidence",
        "expected_support",
        "gold",
        "gold_label",
        "grade",
        "grading",
        "gradient",
        "machine_success",
        "objective_after",
        "objective_before",
        "provider_output",
        "required_evidence",
        "required_evidence_ids",
        "required_facts",
        "required_support",
        "strict_grade",
        "surrogate",
        "target_value",
        "terminal_decision_target",
        "treatment",
        "treatment_id",
    }
)

PINNED_SOURCE_LOCK: dict[str, Any] = {
    "v0_5_5_commit_sha": "7c94e3eddd70e17aa28213ca603004ad48611f2b",
    "v0_5_5_tree_sha": "c89adcd3ecbe3bdead014065d4bb08d729a3ce35",
    "files": {
        "v0_5_5_core": ("lane_composable_trajectory_v0_5_5.py", 97085, "4e8a648616bf8bc283c2c3d4bad76ca78139c4af2ac755fb18ba6c6ccf6ed83c"),
        "v0_5_5_benchmark": ("benchmark_lane_composition_v0_5_5.py", 9803, "a74435559a0e477a0fea80ea63a1f1a73dc8af0245ead3651aebfa87463a7568"),
        "v0_5_5_builder": ("build_lane_composition_artifact_v0_5_5.py", 51932, "51d24842498cc12f988d39ea3653507586c0ccc27fecf42326459eec04a1ae51"),
        "v0_5_5_policy": ("policy_lock_lane_composition_v0_5_5.json", 12235, "6303b04f3ec3b4f74f4d9d0fb847d5fbcefed459a54479306d9a34bd0d90c1df"),
        "v0_5_5_fixture": ("fixtures/lane_composition_v0_5_5.json", 920, "746e38c1649642103c2b7c01c7582e45c82b18d87a5b3083b99686dbf4e92528"),
        "v0_5_5_manifest": ("artifacts/lane_composition_v0_5_5/manifest.json", 12201, "f24409943cddcf857e997e5de16fff221feccf3954fee6c1db07dd984aa671b0"),
        "v0_5_5_sealed_bundle": ("artifacts/lane_composition_v0_5_5/sealed_bundle.json", 2998, "baa18eac488adb9bceee827f05d0b194a58417404939ef0145cedeeb150856bf"),
        "v0_5_5_shared_ledger": ("artifacts/lane_composition_v0_5_5/shared_evidence_ledger.json", 4311, "b3d93b93cf8deb472ccb1cb93213f81c9db64af278faa5ca3bf507688967b172"),
        "v0_5_5_control_bundle": ("artifacts/lane_composition_v0_5_5/bundle_control_map.json", 29496, "d45c77ddfe3fc871ac35696e062bd21320d970fd962dc1c81569db93877f24e0"),
        "v0_5_5_merge_contract": ("artifacts/lane_composition_v0_5_5/merge_contract.json", 37030, "fb20e89e5668af22f79afdf1769da21abb065fcffa650ffe80986c6b56eb85f6"),
        "v0_5_5_block_adjoint": ("artifacts/lane_composition_v0_5_5/block_adjoint_audit.json", 12538, "4a63577a6b924acf35fe455194219aeda7d28875d67c5376843f68c32151f703"),
        "v0_5_5_hard_gate": ("artifacts/lane_composition_v0_5_5/hard_gate_audit.json", 1219, "c81a0bea2e7ca9ac078d0f15fadb7df1eaeefe7b3b943b9f53338a0bf42f51ef"),
        "v0_5_5_self_test": ("artifacts/lane_composition_v0_5_5/self_test.json", 1204, "ee937803eddf075c03985887dc60079bd3441ea174d897deb79d1ba3847b1ddf"),
        "lane_correction_early": ("artifacts/lane_composition_v0_5_5/sealed_lanes/correction_early.json", 69960, "799b2d6b10129e63e751054e995d2e5017a2f73af44916d68068ee3c82b72d17"),
        "lane_correction_late": ("artifacts/lane_composition_v0_5_5/sealed_lanes/correction_late.json", 69447, "54c806a29fdf80f9677b5a008e140734e28a201e719a98ce8d312bf34298afc8"),
        "lane_stable_constraint": ("artifacts/lane_composition_v0_5_5/sealed_lanes/stable_constraint.json", 2926, "379e63f9bfce0af69df2240fe85835b7032efb0de3209773f71f818ba43f40cb"),
        "v0_5_3_regression": ("artifacts/factorized_lineage_v0_5_3/factorized_lineage_regression.json", 43579, "85094e65b9181b893b80bf42c3db859b66a66320a080defefc514ce75fbe910f"),
        "walkthrough_case": ("fixtures/hackathon_strategy_walkthrough_v0_5_2.json", 6994, "ef0b1d44ece10e7412460d9abac4791fe3f3a0172e398bca7a0d8957094f56d2"),
    },
}


class HostedProjectionValidationError(RuntimeError):
    """A sealed source, projection, blinding, or leakage invariant failed."""


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


def _without_fingerprint(value: Mapping[str, Any]) -> JsonObject:
    output = _clone(value)
    output.pop("fingerprint_sha256", None)
    return output


def _with_fingerprint(value: Mapping[str, Any]) -> JsonObject:
    output = _clone(value)
    output["fingerprint_sha256"] = fingerprint(output)
    return output


def _exact_keys(value: Any, expected: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise HostedProjectionValidationError(f"{label} must be an object")
    actual = set(value)
    if actual != expected:
        raise HostedProjectionValidationError(
            f"{label} keys differ: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )
    return value


def _strict_load_bytes(raw: bytes, *, label: str) -> JsonObject:
    def reject_constant(token: str) -> None:
        raise HostedProjectionValidationError(f"non-finite JSON constant: {token}")

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> JsonObject:
        output: JsonObject = {}
        for key, value in pairs:
            if key in output:
                raise HostedProjectionValidationError(
                    f"duplicate JSON key in {label}: {key}"
                )
            output[key] = value
        return output

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise HostedProjectionValidationError(f"invalid JSON for {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise HostedProjectionValidationError(f"{label} root must be object")
    return value


def _strict_load(path: Path) -> tuple[JsonObject, bytes]:
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise HostedProjectionValidationError(f"expected regular non-symlink file: {path}")
    raw = path.read_bytes()
    return _strict_load_bytes(raw, label=str(path)), raw


def _source_lock_as_fixture() -> JsonObject:
    return {
        "v0_5_5_commit_sha": PINNED_SOURCE_LOCK["v0_5_5_commit_sha"],
        "v0_5_5_tree_sha": PINNED_SOURCE_LOCK["v0_5_5_tree_sha"],
        "files": {
            label: {"path": row[0], "bytes": row[1], "sha256": row[2]}
            for label, row in PINNED_SOURCE_LOCK["files"].items()
        },
    }


def _validate_internal_fingerprint(value: Mapping[str, Any], label: str) -> None:
    if value.get("fingerprint_sha256") != fingerprint(_without_fingerprint(value)):
        raise HostedProjectionValidationError(f"{label} fingerprint mismatch")


def _direction(value: float) -> str:
    if value > 0.0:
        return "positive_displacement"
    if value < 0.0:
        return "negative_displacement"
    return "identity"


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HostedProjectionValidationError(f"{label} must be numeric")
    output = float(value)
    if not math.isfinite(output):
        raise HostedProjectionValidationError(f"{label} must be finite")
    return 0.0 if output == 0.0 else output


def _walk_mappings(value: Any) -> Iterator[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _walk_mappings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_mappings(child)


def _reject_provider_leakage(value: Any) -> None:
    for item in _walk_mappings(value):
        for key in item:
            if str(key).casefold() in FORBIDDEN_PROVIDER_KEYS:
                raise HostedProjectionValidationError(
                    f"provider payload contains forbidden field: {key}"
                )


@contextmanager
def network_denied() -> Iterator[dict[str, int]]:
    counts = {"network_calls": 0}

    def denied(*_args: Any, **_kwargs: Any) -> None:
        counts["network_calls"] += 1
        raise AssertionError("network access is forbidden in EBRT v0.6 projection")

    with mock.patch.object(socket, "create_connection", side_effect=denied), mock.patch.object(
        socket.socket, "connect", side_effect=denied
    ), mock.patch.object(socket.socket, "connect_ex", side_effect=denied):
        yield counts


def validate_fixture(value: Mapping[str, Any]) -> None:
    root = _exact_keys(
        value,
        {
            "block",
            "claim_boundary",
            "fixture_fingerprint_sha256",
            "fixture_id",
            "provider_contract",
            "schema_version",
            "source_lock",
            "status",
        },
        "fixture",
    )
    if root["schema_version"] != FIXTURE_SCHEMA_VERSION:
        raise HostedProjectionValidationError("fixture schema version drifted")
    if (
        root["fixture_id"] != "hackathon_strategy_hosted_bundle_projection_v0_6"
        or root["status"] != "LOCKED_NETWORK_ZERO_PREFLIGHT"
    ):
        raise HostedProjectionValidationError("fixture identity drifted")
    if root["fixture_fingerprint_sha256"] != fingerprint(
        {key: _clone(item) for key, item in root.items() if key != "fixture_fingerprint_sha256"}
    ):
        raise HostedProjectionValidationError("fixture fingerprint mismatch")
    if canonical_json_bytes(root["source_lock"]) != canonical_json_bytes(
        _source_lock_as_fixture()
    ):
        raise HostedProjectionValidationError("fixture source lock differs from code pin")
    block = _exact_keys(
        root["block"],
        {
            "blinded_request_ids",
            "evidence_horizons",
            "revision_modes",
            "sham_transform",
            "treatment_order",
        },
        "fixture.block",
    )
    if block["treatment_order"] != ["P", "A", "B", "D", "C"]:
        raise HostedProjectionValidationError("five-call order drifted")
    blind_ids = block["blinded_request_ids"]
    if not isinstance(blind_ids, Mapping) or set(blind_ids) != set(TREATMENTS):
        raise HostedProjectionValidationError("blinded request ID map drifted")
    blind_values = list(blind_ids.values())
    if (
        len(set(blind_values)) != len(TREATMENTS)
        or not all(
            isinstance(value, str) and re.fullmatch(r"req-[0-9a-f]{24}", value)
            for value in blind_values
        )
    ):
        raise HostedProjectionValidationError("blinded request IDs malformed")
    expected_horizons = {
        "P": ["R1", "R2", "R3", "R4", "R5"],
        **{arm: ["R1", "R2", "R3", "R4", "R5", "R6"] for arm in "ABCD"},
    }
    if block["evidence_horizons"] != expected_horizons:
        raise HostedProjectionValidationError("evidence horizons drifted")
    if block["revision_modes"] != {
        "P": "none",
        "A": "none",
        "B": "typed_dag_zero_control",
        "C": "typed_dag_matched_sham",
        "D": "typed_dag_exact_v0_5_5_control",
    }:
        raise HostedProjectionValidationError("revision mode map drifted")
    if block["sham_transform"] != {
        "lane": "cyclic_left_shift_one_over_each_sorted_eligible_lane_row_set",
        "merge": "cyclic_left_shift_one_over_sorted_merge_row_set",
        "moves": "signed_displacement_only",
        "stable_lane": "empty_exact_identity",
    }:
        raise HostedProjectionValidationError("sham transform drifted")
    if root["provider_contract"] != {
        "raw_context_delivery": "ordered_all_raw_evidence_exactly_once",
        "control_semantics": "signed_public_actuator_displacement_not_evidence_truth",
        "provider_payload_contains_treatment_key": False,
        "provider_payload_contains_blinded_request_id": False,
        "no_private_chain_of_thought": True,
        "one_attempt_no_retry": True,
    }:
        raise HostedProjectionValidationError("provider contract drifted")
    claims = root["claim_boundary"]
    if not isinstance(claims, list) or not claims or not all(
        isinstance(item, str) and item for item in claims
    ):
        raise HostedProjectionValidationError("claim boundary malformed")


def load_fixture(path: Path = DEFAULT_FIXTURE) -> JsonObject:
    value, _raw = _strict_load(Path(path))
    validate_fixture(value)
    canonical, canonical_raw = _strict_load(DEFAULT_FIXTURE)
    if Path(path).resolve() != DEFAULT_FIXTURE.resolve() and canonical_json_bytes(
        value
    ) != canonical_json_bytes(canonical):
        raise HostedProjectionValidationError("fixture differs from canonical lock")
    if sha256_bytes(canonical_raw) != PINNED_FIXTURE_FILE_SHA256:
        raise HostedProjectionValidationError("canonical fixture file hash drifted")
    return _clone(value)


def _verify_receipt_bytes(label: str, raw: bytes, spec: Mapping[str, Any]) -> None:
    if len(raw) != spec["bytes"] or sha256_bytes(raw) != spec["sha256"]:
        raise HostedProjectionValidationError(f"source receipt mismatch: {label}")


def _load_pinned_sources() -> tuple[JsonObject, dict[str, JsonObject]]:
    source_lock = _source_lock_as_fixture()
    loaded: dict[str, JsonObject] = {}
    for label, spec in source_lock["files"].items():
        path = ROOT / spec["path"]
        if not path.is_file() or path.is_symlink():
            raise HostedProjectionValidationError(f"pinned source is not regular: {label}")
        raw = path.read_bytes()
        _verify_receipt_bytes(label, raw, spec)
        if path.suffix == ".json":
            loaded[label] = _strict_load_bytes(raw, label=spec["path"])
    return source_lock, loaded


def _validate_v055_source_gate() -> JsonObject:
    source_lock, loaded = _load_pinned_sources()
    manifest = loaded["v0_5_5_manifest"]
    if (
        manifest.get("decision_status") != v055.PROMOTE_STATUS
        or manifest.get("promotion_ready") is not True
        or manifest.get("network_calls") != 0
        or manifest.get("provider_calls") != 0
    ):
        raise HostedProjectionValidationError("v0.5.5 manifest did not promote")
    artifact_rows = manifest.get("artifacts")
    if not isinstance(artifact_rows, Mapping):
        raise HostedProjectionValidationError("v0.5.5 manifest artifact table missing")
    for relative, receipt in artifact_rows.items():
        path = V055_ARTIFACT_DIR / relative
        if not isinstance(receipt, Mapping) or not path.is_file() or path.is_symlink():
            raise HostedProjectionValidationError(f"manifest artifact missing: {relative}")
        raw = path.read_bytes()
        if len(raw) != receipt.get("bytes") or sha256_bytes(raw) != receipt.get("sha256"):
            raise HostedProjectionValidationError(f"manifest artifact receipt drift: {relative}")

    split = {
        "shared_evidence_ledger": loaded["v0_5_5_shared_ledger"],
        "sealed_bundle": loaded["v0_5_5_sealed_bundle"],
        "merge_contract": loaded["v0_5_5_merge_contract"],
        "bundle_control_map": loaded["v0_5_5_control_bundle"],
        "block_adjoint_audit": loaded["v0_5_5_block_adjoint"],
        "hard_gate_audit": loaded["v0_5_5_hard_gate"],
        "self_test": loaded["v0_5_5_self_test"],
    }
    try:
        v055_benchmark.validate_artifact_payloads(split, exact_rederive=True)
    except Exception as exc:
        raise HostedProjectionValidationError(
            "v0.5.5 split artifacts failed exact independent rederivation"
        ) from exc

    sealed_bundle = split["sealed_bundle"]
    if (
        sealed_bundle.get("decision_status") != v055.PROMOTE_STATUS
        or sealed_bundle.get("promotion_ready") is not True
        or sealed_bundle.get("lane_ids") != list(LANE_IDS)
    ):
        raise HostedProjectionValidationError("sealed bundle identity drifted")
    expected_lane_labels = {
        "correction_early": "lane_correction_early",
        "correction_late": "lane_correction_late",
        "stable_constraint": "lane_stable_constraint",
    }
    for lane_id, source_label in expected_lane_labels.items():
        receipt = sealed_bundle["sealed_lane_receipts"].get(lane_id)
        spec = source_lock["files"][source_label]
        if not isinstance(receipt, Mapping) or (
            receipt.get("bytes"), receipt.get("sha256")
        ) != (spec["bytes"], spec["sha256"]):
            raise HostedProjectionValidationError(f"sealed lane receipt drifted: {lane_id}")

    ledger = split["shared_evidence_ledger"]["ledger"]
    control = split["bundle_control_map"]["control_bundle"]
    v055.validate_evidence_ledger(ledger)
    v055.validate_control_bundle(control)
    regression = loaded["v0_5_3_regression"]
    graph = regression.get("repaired", {}).get("graph")
    if not isinstance(graph, Mapping) or graph.get("fingerprint_sha256") != ledger.get(
        "graph_fingerprint_sha256"
    ):
        raise HostedProjectionValidationError("repaired graph does not bind shared ledger")

    payload = {
        "block_adjoint_file_sha256": source_lock["files"]["v0_5_5_block_adjoint"]["sha256"],
        "control_bundle_file_sha256": source_lock["files"]["v0_5_5_control_bundle"]["sha256"],
        "lane_file_sha256": {
            lane_id: source_lock["files"][label]["sha256"]
            for lane_id, label in expected_lane_labels.items()
        },
        "manifest_file_sha256": source_lock["files"]["v0_5_5_manifest"]["sha256"],
        "network_calls": 0,
        "provider_calls": 0,
        "source_commit_sha": source_lock["v0_5_5_commit_sha"],
        "source_control_bundle_fingerprint_sha256": control["fingerprint_sha256"],
        "source_graph_fingerprint_sha256": ledger["graph_fingerprint_sha256"],
        "source_ledger_fingerprint_sha256": ledger["fingerprint_sha256"],
        "source_manifest_decision_status": manifest["decision_status"],
        "source_tree_sha": source_lock["v0_5_5_tree_sha"],
        "status": "PASS",
    }
    return _with_fingerprint(payload)


def _source_payloads() -> tuple[JsonObject, JsonObject, JsonObject, JsonObject]:
    ledger_artifact, _ = _strict_load(V055_ARTIFACT_DIR / "shared_evidence_ledger.json")
    control_artifact, _ = _strict_load(V055_ARTIFACT_DIR / "bundle_control_map.json")
    merge_artifact, _ = _strict_load(V055_ARTIFACT_DIR / "merge_contract.json")
    regression, _ = _strict_load(V053_REGRESSION_PATH)
    ledger = ledger_artifact["ledger"]
    control = control_artifact["control_bundle"]
    merge = merge_artifact["contract"]
    graph = regression["repaired"]["graph"]
    v055.validate_evidence_ledger(ledger)
    v055.validate_control_bundle(control)
    if graph.get("fingerprint_sha256") != ledger["graph_fingerprint_sha256"]:
        raise HostedProjectionValidationError("public graph/ledger binding drifted")
    return _clone(ledger), _clone(control), _clone(merge), _clone(graph)


def _case_contract(ledger: Mapping[str, Any]) -> JsonObject:
    case_fixture, _ = _strict_load(WALKTHROUGH_CASE_PATH)
    case = _exact_keys(
        case_fixture.get("case"),
        {
            "answer_choices",
            "case_id",
            "decision_slots",
            "family",
            "initial_evidence",
            "late_evidence",
            "question",
        },
        "walkthrough case",
    )
    evidence = list(case["initial_evidence"]) + [case["late_evidence"]]
    ledger_evidence = [
        {
            "evidence_id": row["node_payload"]["evidence_id"],
            "text": row["node_payload"]["text"],
        }
        for row in ledger["entries"]
    ]
    if evidence != ledger_evidence:
        raise HostedProjectionValidationError("walkthrough raw evidence differs from ledger")
    if [row["evidence_id"] for row in evidence] != [
        "R1",
        "R2",
        "R3",
        "R4",
        "R5",
        "R6",
    ]:
        raise HostedProjectionValidationError("walkthrough evidence order drifted")
    return {
        "answer_choices": _clone(case["answer_choices"]),
        "case_id": case["case_id"],
        "decision_slots": _clone(case["decision_slots"]),
        "evidence": _clone(evidence),
        "question": case["question"],
    }


def _provider_safe_graph(graph: Mapping[str, Any]) -> JsonObject:
    nodes: list[JsonObject] = []
    for row in sorted(graph["nodes"], key=lambda item: item["node_id"]):
        node_type = row["node_type"]
        if node_type == "evidence":
            projected = {
                "evidence_id": row["evidence_id"],
                "node_id": row["node_id"],
                "node_type": node_type,
                "temporal_ordinal": row["temporal_ordinal"],
            }
        elif node_type == "support":
            projected = {
                "node_id": row["node_id"],
                "node_type": node_type,
                "support_role": row["support_role"],
            }
        elif node_type in {"fact", "constraint"}:
            projected = {
                "node_id": row["node_id"],
                "node_type": node_type,
                "slot": row["slot"],
            }
        else:
            raise HostedProjectionValidationError("graph node type escaped allowlist")
        nodes.append(projected)
    edges = [
        {
            "edge_id": row["edge_id"],
            "edge_type": row["edge_type"],
            "provenance": row["provenance"],
            "source_node_id": row["source_node_id"],
            "target_node_id": row["target_node_id"],
        }
        for row in sorted(graph["edges"], key=lambda item: item["edge_id"])
    ]
    if {row["node_type"] for row in nodes} != {
        "evidence",
        "support",
        "fact",
        "constraint",
    } or {row["edge_type"] for row in edges} != {
        "supports",
        "depends_on",
        "invalidates",
    }:
        raise HostedProjectionValidationError("provider graph vocabulary drifted")
    projection = {
        "edges": edges,
        "nodes": nodes,
        "schema_version": PUBLIC_GRAPH_SCHEMA_VERSION,
    }
    _reject_provider_leakage(projection)
    if any(
        key in row
        for row in nodes
        for key in ("text", "value", "expected_value", "required_support")
    ):
        raise HostedProjectionValidationError("provider graph leaked semantic endpoint")
    return projection


def _parse_site_id(site_id: str, lane_id: str) -> JsonObject:
    match = _SITE_PATTERN.fullmatch(site_id)
    if match is None or match.group("lane") != lane_id:
        raise HostedProjectionValidationError(f"invalid v0.5.5 site ID: {site_id}")
    node_type = match.group("node_type")
    node_name = match.group("node_name")
    return {
        "eligible": None,
        "evidence_id": match.group("evidence"),
        "horizon_ordinal": int(match.group("horizon")),
        "lane_id": lane_id,
        "node_id": f"{node_type}:{node_name}",
        "node_type": node_type,
        "row_id": site_id,
    }


def _project_exact_lane_controls(control: Mapping[str, Any]) -> list[JsonObject]:
    lanes: list[JsonObject] = []
    for lane in control["lane_control_maps"]:
        lane_id = lane["lane_id"]
        inner = lane["inner_control_map"]
        rows: list[JsonObject] = []
        if inner is not None:
            for source_row in sorted(inner["controls"], key=lambda item: item["site_id"]):
                row = _parse_site_id(source_row["site_id"], lane_id)
                value = _finite_number(
                    source_row["normalized_u"], f"{lane_id}.{source_row['site_id']}"
                )
                row["eligible"] = source_row["eligible"]
                row["signed_displacement"] = value
                row["displacement_direction"] = _direction(value)
                rows.append(row)
        observed_l2 = math.sqrt(math.fsum(row["signed_displacement"] ** 2 for row in rows))
        if abs(observed_l2 - float(lane["normalized_l2_budget"])) > 2.0e-15:
            raise HostedProjectionValidationError(f"source lane norm drifted: {lane_id}")
        lanes.append(
            {
                "lane_id": lane_id,
                "namespace_prefix": lane["namespace_prefix"],
                "normalized_l2": observed_l2,
                "normalized_l2_budget": lane["normalized_l2_budget"],
                "rows": rows,
            }
        )
    if [row["lane_id"] for row in lanes] != sorted(LANE_IDS):
        raise HostedProjectionValidationError("source lane control order drifted")
    return lanes


def _project_exact_merge_controls(
    control: Mapping[str, Any], merge: Mapping[str, Any]
) -> JsonObject:
    clause_by_id = {row["clause_id"]: row for row in merge["clauses"]}
    rows: list[JsonObject] = []
    for source_row in sorted(
        control["merge_control_map"]["controls"], key=lambda item: item["control_id"]
    ):
        clause = clause_by_id.get(source_row["clause_id"])
        if not isinstance(clause, Mapping):
            raise HostedProjectionValidationError("merge control references unknown clause")
        value = _finite_number(source_row["value"], source_row["control_id"])
        rows.append(
            {
                "axis_id": clause["axis_id"],
                "clause_id": source_row["clause_id"],
                "displacement_direction": _direction(value),
                "left_lane_id": clause["left_lane_id"],
                "right_lane_id": clause["right_lane_id"],
                "row_id": source_row["control_id"],
                "signed_displacement": value,
            }
        )
    observed_l2 = math.sqrt(math.fsum(row["signed_displacement"] ** 2 for row in rows))
    source_merge = control["merge_control_map"]
    if abs(observed_l2 - float(source_merge["normalized_l2"])) > 2.0e-15:
        raise HostedProjectionValidationError("source merge norm drifted")
    return {
        "normalized_l2": observed_l2,
        "normalized_l2_budget": source_merge["normalized_l2_budget"],
        "parameterization": source_merge["parameterization"],
        "rows": rows,
    }


def _zero_lanes(source_lanes: Sequence[Mapping[str, Any]]) -> list[JsonObject]:
    lanes = _clone(source_lanes)
    for lane in lanes:
        for row in lane["rows"]:
            row["signed_displacement"] = 0.0
            row["displacement_direction"] = "identity"
        lane["normalized_l2"] = 0.0
    return lanes


def _zero_merge(source_merge: Mapping[str, Any]) -> JsonObject:
    merge = _clone(source_merge)
    for row in merge["rows"]:
        row["signed_displacement"] = 0.0
        row["displacement_direction"] = "identity"
    merge["normalized_l2"] = 0.0
    return merge


def _sham_lanes(source_lanes: Sequence[Mapping[str, Any]]) -> list[JsonObject]:
    lanes = _clone(source_lanes)
    for lane in lanes:
        eligible = [row for row in lane["rows"] if row["eligible"]]
        values = [row["signed_displacement"] for row in eligible]
        if values:
            shifted = values[1:] + values[:1]
            for row, value in zip(eligible, shifted, strict=True):
                row["signed_displacement"] = value
                row["displacement_direction"] = _direction(value)
        lane["normalized_l2"] = math.sqrt(
            math.fsum(row["signed_displacement"] ** 2 for row in lane["rows"])
        )
    return lanes


def _sham_merge(source_merge: Mapping[str, Any]) -> JsonObject:
    merge = _clone(source_merge)
    values = [row["signed_displacement"] for row in merge["rows"]]
    shifted = values[1:] + values[:1]
    for row, value in zip(merge["rows"], shifted, strict=True):
        row["signed_displacement"] = value
        row["displacement_direction"] = _direction(value)
    merge["normalized_l2"] = math.sqrt(math.fsum(value * value for value in shifted))
    return merge


def _revision_program(
    treatment_id: str,
    *,
    ledger: Mapping[str, Any],
    graph: Mapping[str, Any],
    exact_lanes: Sequence[Mapping[str, Any]],
    exact_merge: Mapping[str, Any],
) -> JsonObject | None:
    if treatment_id not in CONTROL_TREATMENTS:
        return None
    if treatment_id == "B":
        lanes = _zero_lanes(exact_lanes)
        merge_controls = _zero_merge(exact_merge)
    elif treatment_id == "C":
        lanes = _sham_lanes(exact_lanes)
        merge_controls = _sham_merge(exact_merge)
    else:
        lanes = _clone(exact_lanes)
        merge_controls = _clone(exact_merge)
    invalidations = ledger["invalidations"]
    if len(invalidations) != 1:
        raise HostedProjectionValidationError("expected one public invalidation")
    invalidation = invalidations[0]
    return {
        "event": {
            "correction_evidence_id": invalidation["source_evidence_id"],
            "invalidated_evidence_ids": [invalidation["target_evidence_id"]],
            "invalidation_edge_id": invalidation["edge_payload"]["edge_id"],
        },
        "instructions_fragment": PROVIDER_INSTRUCTIONS_FRAGMENT,
        "lane_controls": lanes,
        "merge_controls": merge_controls,
        "schema_version": REVISION_PROGRAM_SCHEMA_VERSION,
        "typed_dependency_graph": _provider_safe_graph(graph),
    }


def _build_provider_payload(
    treatment_id: str,
    fixture: Mapping[str, Any],
    case: Mapping[str, Any],
    *,
    ledger: Mapping[str, Any],
    graph: Mapping[str, Any],
    exact_lanes: Sequence[Mapping[str, Any]],
    exact_merge: Mapping[str, Any],
) -> JsonObject:
    if treatment_id not in TREATMENTS:
        raise HostedProjectionValidationError(f"unknown treatment: {treatment_id}")
    horizon = fixture["block"]["evidence_horizons"][treatment_id]
    evidence_by_id = {row["evidence_id"]: row for row in case["evidence"]}
    raw_evidence = [_clone(evidence_by_id[evidence_id]) for evidence_id in horizon]
    payload = {
        "allowed_evidence_ids": list(horizon),
        "all_raw_evidence": raw_evidence,
        "answer_choices": _clone(case["answer_choices"]),
        "case_id": case["case_id"],
        "checkpoint_id": (
            f"{case['case_id']}:pre_event"
            if treatment_id == "P"
            else f"{case['case_id']}:full_context_final"
        ),
        "decision_slots": _clone(case["decision_slots"]),
        "question": case["question"],
        "revision_program": _revision_program(
            treatment_id,
            ledger=ledger,
            graph=graph,
            exact_lanes=exact_lanes,
            exact_merge=exact_merge,
        ),
        "schema_version": PROVIDER_PAYLOAD_SCHEMA_VERSION,
    }
    validate_provider_payload(
        payload,
        fixture=fixture,
        exact_treatment=treatment_id,
        exact_source=False,
    )
    return payload


def _validate_control_row(row: Mapping[str, Any], lane_id: str) -> None:
    _exact_keys(
        row,
        {
            "displacement_direction",
            "eligible",
            "evidence_id",
            "horizon_ordinal",
            "lane_id",
            "node_id",
            "node_type",
            "row_id",
            "signed_displacement",
        },
        "provider lane control row",
    )
    parsed = _parse_site_id(str(row["row_id"]), lane_id)
    for key in ("evidence_id", "horizon_ordinal", "lane_id", "node_id", "node_type", "row_id"):
        if row[key] != parsed[key]:
            raise HostedProjectionValidationError(f"lane control row metadata drifted: {key}")
    if type(row["eligible"]) is not bool:
        raise HostedProjectionValidationError("lane control eligible must be boolean")
    value = _finite_number(row["signed_displacement"], "signed displacement")
    if row["displacement_direction"] != _direction(value):
        raise HostedProjectionValidationError("lane displacement direction drifted")


def _validate_revision_program(program: Mapping[str, Any]) -> None:
    _exact_keys(
        program,
        {
            "event",
            "instructions_fragment",
            "lane_controls",
            "merge_controls",
            "schema_version",
            "typed_dependency_graph",
        },
        "revision program",
    )
    if (
        program["schema_version"] != REVISION_PROGRAM_SCHEMA_VERSION
        or program["instructions_fragment"] != PROVIDER_INSTRUCTIONS_FRAGMENT
    ):
        raise HostedProjectionValidationError("revision program identity drifted")
    event = _exact_keys(
        program["event"],
        {"correction_evidence_id", "invalidated_evidence_ids", "invalidation_edge_id"},
        "revision event",
    )
    if event != {
        "correction_evidence_id": "R6",
        "invalidated_evidence_ids": ["R3"],
        "invalidation_edge_id": "observed:R6->invalidates:R3",
    }:
        raise HostedProjectionValidationError("revision event drifted")
    graph = _exact_keys(
        program["typed_dependency_graph"],
        {"edges", "nodes", "schema_version"},
        "provider graph",
    )
    if graph["schema_version"] != PUBLIC_GRAPH_SCHEMA_VERSION:
        raise HostedProjectionValidationError("provider graph schema drifted")
    if any(
        forbidden in node
        for node in graph["nodes"]
        for forbidden in ("text", "value", "expected_value", "required_support")
    ):
        raise HostedProjectionValidationError("provider graph leaked a semantic endpoint")
    lanes = program["lane_controls"]
    if not isinstance(lanes, list) or [row.get("lane_id") for row in lanes] != sorted(LANE_IDS):
        raise HostedProjectionValidationError("provider lane set/order drifted")
    for lane in lanes:
        _exact_keys(
            lane,
            {
                "lane_id",
                "namespace_prefix",
                "normalized_l2",
                "normalized_l2_budget",
                "rows",
            },
            "provider lane",
        )
        lane_id = lane["lane_id"]
        if lane["namespace_prefix"] != f"lane::{lane_id}::":
            raise HostedProjectionValidationError("provider lane namespace drifted")
        if not isinstance(lane["rows"], list):
            raise HostedProjectionValidationError("provider lane rows must be list")
        for row in lane["rows"]:
            _validate_control_row(row, lane_id)
        row_ids = [row["row_id"] for row in lane["rows"]]
        if row_ids != sorted(row_ids) or len(row_ids) != len(set(row_ids)):
            raise HostedProjectionValidationError("provider lane row IDs drifted")
        observed = math.sqrt(
            math.fsum(float(row["signed_displacement"]) ** 2 for row in lane["rows"])
        )
        if abs(observed - float(lane["normalized_l2"])) > 2.0e-15 or observed > float(
            lane["normalized_l2_budget"]
        ) + 2.0e-15:
            raise HostedProjectionValidationError("provider lane norm drifted")
        if any(not row["eligible"] and row["signed_displacement"] != 0.0 for row in lane["rows"]):
            raise HostedProjectionValidationError("ineligible provider actuator moved")
    merge = _exact_keys(
        program["merge_controls"],
        {
            "normalized_l2",
            "normalized_l2_budget",
            "parameterization",
            "rows",
        },
        "provider merge controls",
    )
    if merge["parameterization"] != "separate_bounded_consistency_slack":
        raise HostedProjectionValidationError("provider merge parameterization drifted")
    merge_ids: list[str] = []
    for row in merge["rows"]:
        _exact_keys(
            row,
            {
                "axis_id",
                "clause_id",
                "displacement_direction",
                "left_lane_id",
                "right_lane_id",
                "row_id",
                "signed_displacement",
            },
            "provider merge row",
        )
        if row["row_id"] != f"merge::{row['clause_id']}":
            raise HostedProjectionValidationError("provider merge row namespace drifted")
        value = _finite_number(row["signed_displacement"], "merge displacement")
        if row["displacement_direction"] != _direction(value):
            raise HostedProjectionValidationError("merge displacement direction drifted")
        merge_ids.append(row["row_id"])
    if merge_ids != sorted(merge_ids) or len(merge_ids) != len(set(merge_ids)):
        raise HostedProjectionValidationError("provider merge row IDs drifted")
    observed_merge = math.sqrt(
        math.fsum(float(row["signed_displacement"]) ** 2 for row in merge["rows"])
    )
    if abs(observed_merge - float(merge["normalized_l2"])) > 2.0e-15 or observed_merge > float(
        merge["normalized_l2_budget"]
    ) + 2.0e-15:
        raise HostedProjectionValidationError("provider merge norm drifted")
    _reject_provider_leakage(program)


def validate_provider_payload(
    payload: Mapping[str, Any],
    *,
    fixture: Mapping[str, Any] | None = None,
    exact_treatment: str | None = None,
    exact_source: bool = True,
) -> None:
    _exact_keys(
        payload,
        {
            "allowed_evidence_ids",
            "all_raw_evidence",
            "answer_choices",
            "case_id",
            "checkpoint_id",
            "decision_slots",
            "question",
            "revision_program",
            "schema_version",
        },
        "provider payload",
    )
    if payload["schema_version"] != PROVIDER_PAYLOAD_SCHEMA_VERSION:
        raise HostedProjectionValidationError("provider payload schema drifted")
    _reject_provider_leakage(payload)
    evidence = payload["all_raw_evidence"]
    if not isinstance(evidence, list) or not evidence:
        raise HostedProjectionValidationError("provider raw evidence malformed")
    ids = [row.get("evidence_id") for row in evidence]
    if ids != payload["allowed_evidence_ids"] or len(ids) != len(set(ids)):
        raise HostedProjectionValidationError("provider evidence IDs/order drifted")
    if any(set(row) != {"evidence_id", "text"} for row in evidence):
        raise HostedProjectionValidationError("provider raw evidence schema drifted")
    if sum("all_raw_evidence" in row for row in _walk_mappings(payload)) != 1:
        raise HostedProjectionValidationError("raw evidence must occur exactly once")
    outside = _clone(payload)
    outside.pop("all_raw_evidence")
    pairs = {(row["evidence_id"], row["text"]) for row in evidence}
    if any((row.get("evidence_id"), row.get("text")) in pairs for row in _walk_mappings(outside)):
        raise HostedProjectionValidationError("raw evidence pair duplicated outside horizon")
    if payload["revision_program"] is not None:
        if not isinstance(payload["revision_program"], Mapping):
            raise HostedProjectionValidationError("revision program must be object or null")
        _validate_revision_program(payload["revision_program"])
    if fixture is not None and exact_treatment is not None:
        validate_fixture(fixture)
        expected_ids = fixture["block"]["evidence_horizons"][exact_treatment]
        expected_has_program = exact_treatment in CONTROL_TREATMENTS
        if ids != expected_ids or (payload["revision_program"] is not None) != expected_has_program:
            raise HostedProjectionValidationError("provider treatment horizon/program drifted")
        blind_values = set(fixture["block"]["blinded_request_ids"].values())
        encoded = canonical_json_bytes(payload).decode("utf-8")
        if any(value in encoded for value in blind_values):
            raise HostedProjectionValidationError("provider payload leaked blinded request ID")
        if exact_source:
            ledger, control, merge, graph = _source_payloads()
            case = _case_contract(ledger)
            expected = _build_provider_payload(
                exact_treatment,
                fixture,
                case,
                ledger=ledger,
                graph=graph,
                exact_lanes=_project_exact_lane_controls(control),
                exact_merge=_project_exact_merge_controls(control, merge),
            )
            if canonical_json_bytes(payload) != canonical_json_bytes(expected):
                raise HostedProjectionValidationError(
                    "provider payload differs from exact sealed projection"
                )


def _value_signature(rows: Sequence[Mapping[str, Any]]) -> JsonObject:
    values = sorted(float(row["signed_displacement"]) for row in rows)
    directions = sorted(str(row["displacement_direction"]) for row in rows)
    return {
        "directions": directions,
        "nonzero_count": sum(value != 0.0 for value in values),
        "signed_displacements": values,
        "sparsity": len(values) - sum(value != 0.0 for value in values),
    }


def _diff_paths(left: Any, right: Any, path: str = "$") -> list[str]:
    if type(left) is not type(right):
        return [path]
    if isinstance(left, Mapping):
        if set(left) != set(right):
            return [path]
        output: list[str] = []
        for key in sorted(left):
            output.extend(_diff_paths(left[key], right[key], f"{path}.{key}"))
        return output
    if isinstance(left, list):
        if len(left) != len(right):
            return [path]
        output = []
        for index, (left_item, right_item) in enumerate(zip(left, right, strict=True)):
            output.extend(_diff_paths(left_item, right_item, f"{path}[{index}]"))
        return output
    return [] if left == right else [path]


def _matched_geometry_audit(c_payload: Mapping[str, Any], d_payload: Mapping[str, Any]) -> JsonObject:
    c_program = c_payload["revision_program"]
    d_program = d_payload["revision_program"]
    if not isinstance(c_program, Mapping) or not isinstance(d_program, Mapping):
        raise HostedProjectionValidationError("C/D revision programs missing")
    lane_rows: list[JsonObject] = []
    all_lane_checks = True
    c_lanes = {row["lane_id"]: row for row in c_program["lane_controls"]}
    d_lanes = {row["lane_id"]: row for row in d_program["lane_controls"]}
    if set(c_lanes) != set(d_lanes) or set(c_lanes) != set(LANE_IDS):
        raise HostedProjectionValidationError("C/D lane sets differ")
    for lane_id in sorted(LANE_IDS):
        c_lane = c_lanes[lane_id]
        d_lane = d_lanes[lane_id]
        c_rows = c_lane["rows"]
        d_rows = d_lane["rows"]
        row_ids_exact = [row["row_id"] for row in c_rows] == [
            row["row_id"] for row in d_rows
        ]
        schema_exact = [sorted(row) for row in c_rows] == [sorted(row) for row in d_rows]
        eligible_mask_exact = [row["eligible"] for row in c_rows] == [
            row["eligible"] for row in d_rows
        ]
        signature_exact = _value_signature(c_rows) == _value_signature(d_rows)
        norm_exact = c_lane["normalized_l2"] == d_lane["normalized_l2"]
        budget_exact = c_lane["normalized_l2_budget"] == d_lane["normalized_l2_budget"]
        placement_differs = (
            lane_id == "stable_constraint"
            or [row["signed_displacement"] for row in c_rows]
            != [row["signed_displacement"] for row in d_rows]
        )
        checks = {
            "budget_exact": budget_exact,
            "eligible_mask_exact": eligible_mask_exact,
            "norm_exact": norm_exact,
            "placement_differs_or_stable_identity": placement_differs,
            "row_ids_exact": row_ids_exact,
            "schema_exact": schema_exact,
            "value_sign_multiset_and_sparsity_exact": signature_exact,
        }
        all_lane_checks = all_lane_checks and all(checks.values())
        lane_rows.append({"checks": checks, "lane_id": lane_id})

    c_merge = c_program["merge_controls"]
    d_merge = d_program["merge_controls"]
    c_merge_rows = c_merge["rows"]
    d_merge_rows = d_merge["rows"]
    merge_checks = {
        "budget_exact": c_merge["normalized_l2_budget"] == d_merge["normalized_l2_budget"],
        "norm_exact": c_merge["normalized_l2"] == d_merge["normalized_l2"],
        "placement_differs": [row["signed_displacement"] for row in c_merge_rows]
        != [row["signed_displacement"] for row in d_merge_rows],
        "row_ids_exact": [row["row_id"] for row in c_merge_rows]
        == [row["row_id"] for row in d_merge_rows],
        "schema_exact": [sorted(row) for row in c_merge_rows]
        == [sorted(row) for row in d_merge_rows],
        "value_sign_multiset_and_sparsity_exact": _value_signature(c_merge_rows)
        == _value_signature(d_merge_rows),
    }
    diff_paths = _diff_paths(c_payload, d_payload)
    allowed_diff_paths = all(
        path.endswith(".signed_displacement")
        or path.endswith(".displacement_direction")
        for path in diff_paths
    )
    payload_schema_exact = set(c_payload) == set(d_payload)
    graph_exact = canonical_json_bytes(c_program["typed_dependency_graph"]) == canonical_json_bytes(
        d_program["typed_dependency_graph"]
    )
    event_exact = c_program["event"] == d_program["event"]
    status = (
        "PASS"
        if all_lane_checks
        and all(merge_checks.values())
        and allowed_diff_paths
        and bool(diff_paths)
        and payload_schema_exact
        and graph_exact
        and event_exact
        else "FAIL"
    )
    return _with_fingerprint(
        {
            "allowed_difference_leaf_fields": [
                "displacement_direction",
                "signed_displacement",
            ],
            "different_leaf_count": len(diff_paths),
            "event_exact": event_exact,
            "graph_exact": graph_exact,
            "lane_audits": lane_rows,
            "merge_checks": merge_checks,
            "only_deterministic_placement_differs": allowed_diff_paths and bool(diff_paths),
            "payload_schema_exact": payload_schema_exact,
            "schema_version": MATCH_AUDIT_SCHEMA_VERSION,
            "status": status,
        }
    )


def _build_treatment_key(
    fixture: Mapping[str, Any], payload_by_treatment: Mapping[str, Mapping[str, Any]]
) -> JsonObject:
    rows = []
    for treatment_id in fixture["block"]["treatment_order"]:
        rows.append(
            {
                "blinded_request_id": fixture["block"]["blinded_request_ids"][treatment_id],
                "evidence_horizon": list(
                    fixture["block"]["evidence_horizons"][treatment_id]
                ),
                "provider_payload_sha256": fingerprint(payload_by_treatment[treatment_id]),
                "revision_mode": fixture["block"]["revision_modes"][treatment_id],
                "treatment_id": treatment_id,
            }
        )
    return _with_fingerprint(
        {
            "call_order_blinded_request_ids": [row["blinded_request_id"] for row in rows],
            "fixture_id": fixture["fixture_id"],
            "schema_version": TREATMENT_KEY_SCHEMA_VERSION,
            "treatments": rows,
        }
    )


def _build_projection_bundle_once(fixture: Mapping[str, Any]) -> JsonObject:
    validate_fixture(fixture)
    source_gate = _validate_v055_source_gate()
    ledger, control, merge, graph = _source_payloads()
    case = _case_contract(ledger)
    exact_lanes = _project_exact_lane_controls(control)
    exact_merge = _project_exact_merge_controls(control, merge)
    payload_by_treatment = {
        treatment_id: _build_provider_payload(
            treatment_id,
            fixture,
            case,
            ledger=ledger,
            graph=graph,
            exact_lanes=exact_lanes,
            exact_merge=exact_merge,
        )
        for treatment_id in TREATMENTS
    }
    treatment_key = _build_treatment_key(fixture, payload_by_treatment)
    payload_rows = [
        {
            "blinded_request_id": blind_id,
            "payload": _clone(payload_by_treatment[treatment_id]),
            "provider_payload_sha256": fingerprint(payload_by_treatment[treatment_id]),
        }
        for treatment_id, blind_id in sorted(
            fixture["block"]["blinded_request_ids"].items(), key=lambda item: item[1]
        )
    ]
    match_audit = _matched_geometry_audit(
        payload_by_treatment["C"], payload_by_treatment["D"]
    )
    post_bytes = {
        treatment_id: canonical_json_bytes(payload_by_treatment[treatment_id]["all_raw_evidence"])
        for treatment_id in POST_EVENT_TREATMENTS
    }
    p_ids = [
        row["evidence_id"] for row in payload_by_treatment["P"]["all_raw_evidence"]
    ]
    post_ids = {
        treatment_id: [
            row["evidence_id"]
            for row in payload_by_treatment[treatment_id]["all_raw_evidence"]
        ]
        for treatment_id in POST_EVENT_TREATMENTS
    }
    forbidden_clear = all(
        not (set(row) & FORBIDDEN_PROVIDER_KEYS)
        for payload in payload_by_treatment.values()
        for row in _walk_mappings(payload)
    )
    blind_values = set(fixture["block"]["blinded_request_ids"].values())
    blind_external = all(
        not any(value in canonical_json_bytes(payload).decode("utf-8") for value in blind_values)
        for payload in payload_by_treatment.values()
    )
    b_program = payload_by_treatment["B"]["revision_program"]
    b_zero = isinstance(b_program, Mapping) and all(
        row["signed_displacement"] == 0.0
        for lane in b_program["lane_controls"]
        for row in lane["rows"]
    ) and all(
        row["signed_displacement"] == 0.0 for row in b_program["merge_controls"]["rows"]
    )
    gates = {
        "b_typed_dag_zero_controls": bool(b_zero),
        "blinding_key_external": blind_external,
        "cd_matched_geometry_exact": match_audit["status"] == "PASS",
        "forbidden_downstream_leakage_absent": forbidden_clear,
        "p_pre_event_horizon_exact": p_ids == ["R1", "R2", "R3", "R4", "R5"],
        "post_event_raw_history_byte_identical": len(set(post_bytes.values())) == 1
        and all(ids == ["R1", "R2", "R3", "R4", "R5", "R6"] for ids in post_ids.values()),
        "source_v0_5_5_exact": source_gate["status"] == "PASS",
        "provider_calls_zero": True,
        "network_calls_zero": True,
    }
    ready = all(gates.values())
    return _with_fingerprint(
        {
            "claim_boundary": list(fixture["claim_boundary"]),
            "decision_status": READY_STATUS if ready else STOP_STATUS,
            "fixture_id": fixture["fixture_id"],
            "gates": gates,
            "matched_geometry_audit": match_audit,
            "network_calls": 0,
            "provider_calls": 0,
            "provider_payloads": payload_rows,
            "public_treatment_key": treatment_key,
            "ready_for_live_lock": ready,
            "schema_version": PROJECTION_SCHEMA_VERSION,
            "source_gate": source_gate,
        }
    )


def build_projection_bundle(fixture_path: Path = DEFAULT_FIXTURE) -> JsonObject:
    fixture = load_fixture(Path(fixture_path))
    with network_denied() as counts:
        result = _build_projection_bundle_once(fixture)
    if counts["network_calls"] != 0:
        raise HostedProjectionValidationError("projection attempted network access")
    validate_projection_bundle(result, fixture=fixture, exact_rederive=False)
    return result


def validate_projection_bundle(
    payload: Mapping[str, Any],
    *,
    fixture: Mapping[str, Any] | None = None,
    exact_rederive: bool = True,
) -> None:
    root = _exact_keys(
        payload,
        {
            "claim_boundary",
            "decision_status",
            "fingerprint_sha256",
            "fixture_id",
            "gates",
            "matched_geometry_audit",
            "network_calls",
            "provider_calls",
            "provider_payloads",
            "public_treatment_key",
            "ready_for_live_lock",
            "schema_version",
            "source_gate",
        },
        "projection bundle",
    )
    if root["schema_version"] != PROJECTION_SCHEMA_VERSION:
        raise HostedProjectionValidationError("projection bundle schema drifted")
    _validate_internal_fingerprint(root, "projection bundle")
    if root["network_calls"] != 0 or root["provider_calls"] != 0:
        raise HostedProjectionValidationError("projection bundle is not network/provider zero")
    if fixture is None:
        fixture = load_fixture()
    else:
        validate_fixture(fixture)
    if root["fixture_id"] != fixture["fixture_id"] or root["claim_boundary"] != fixture[
        "claim_boundary"
    ]:
        raise HostedProjectionValidationError("projection fixture binding drifted")
    _validate_internal_fingerprint(root["source_gate"], "projection source gate")
    if root["source_gate"].get("status") != "PASS":
        raise HostedProjectionValidationError("projection source gate did not pass")

    key = _exact_keys(
        root["public_treatment_key"],
        {
            "call_order_blinded_request_ids",
            "fingerprint_sha256",
            "fixture_id",
            "schema_version",
            "treatments",
        },
        "public treatment key",
    )
    _validate_internal_fingerprint(key, "public treatment key")
    if key["schema_version"] != TREATMENT_KEY_SCHEMA_VERSION or key["fixture_id"] != fixture[
        "fixture_id"
    ]:
        raise HostedProjectionValidationError("public treatment key identity drifted")
    treatment_rows = key["treatments"]
    if not isinstance(treatment_rows, list) or [row.get("treatment_id") for row in treatment_rows] != fixture[
        "block"
    ]["treatment_order"]:
        raise HostedProjectionValidationError("public treatment order drifted")
    for row in treatment_rows:
        _exact_keys(
            row,
            {
                "blinded_request_id",
                "evidence_horizon",
                "provider_payload_sha256",
                "revision_mode",
                "treatment_id",
            },
            "public treatment row",
        )
        treatment_id = row["treatment_id"]
        if (
            row["blinded_request_id"]
            != fixture["block"]["blinded_request_ids"][treatment_id]
            or row["evidence_horizon"]
            != fixture["block"]["evidence_horizons"][treatment_id]
            or row["revision_mode"]
            != fixture["block"]["revision_modes"][treatment_id]
        ):
            raise HostedProjectionValidationError("public treatment row drifted")
    if key["call_order_blinded_request_ids"] != [
        row["blinded_request_id"] for row in treatment_rows
    ]:
        raise HostedProjectionValidationError("blinded call order drifted")

    provider_rows = root["provider_payloads"]
    if not isinstance(provider_rows, list) or len(provider_rows) != len(TREATMENTS):
        raise HostedProjectionValidationError("provider payload row count drifted")
    payload_by_blind: dict[str, Mapping[str, Any]] = {}
    for row in provider_rows:
        _exact_keys(
            row,
            {"blinded_request_id", "payload", "provider_payload_sha256"},
            "provider payload wrapper",
        )
        blind = row["blinded_request_id"]
        if blind in payload_by_blind:
            raise HostedProjectionValidationError("duplicate blinded provider payload")
        if row["provider_payload_sha256"] != fingerprint(row["payload"]):
            raise HostedProjectionValidationError("provider payload wrapper hash drifted")
        payload_by_blind[blind] = row["payload"]
    if set(payload_by_blind) != set(fixture["block"]["blinded_request_ids"].values()):
        raise HostedProjectionValidationError("blinded provider payload set drifted")
    payload_by_treatment: dict[str, Mapping[str, Any]] = {}
    for treatment_row in treatment_rows:
        treatment_id = treatment_row["treatment_id"]
        provider_payload = payload_by_blind[treatment_row["blinded_request_id"]]
        if treatment_row["provider_payload_sha256"] != fingerprint(provider_payload):
            raise HostedProjectionValidationError("treatment/payload receipt drifted")
        validate_provider_payload(
            provider_payload,
            fixture=fixture,
            exact_treatment=treatment_id,
            exact_source=exact_rederive,
        )
        payload_by_treatment[treatment_id] = provider_payload

    observed_match = _matched_geometry_audit(
        payload_by_treatment["C"], payload_by_treatment["D"]
    )
    if canonical_json_bytes(observed_match) != canonical_json_bytes(
        root["matched_geometry_audit"]
    ) or observed_match["status"] != "PASS":
        raise HostedProjectionValidationError("C/D matched geometry audit drifted")
    expected_gate_keys = {
        "b_typed_dag_zero_controls",
        "blinding_key_external",
        "cd_matched_geometry_exact",
        "forbidden_downstream_leakage_absent",
        "network_calls_zero",
        "p_pre_event_horizon_exact",
        "post_event_raw_history_byte_identical",
        "provider_calls_zero",
        "source_v0_5_5_exact",
    }
    if set(root["gates"]) != expected_gate_keys or not all(root["gates"].values()):
        raise HostedProjectionValidationError("projection hard gates did not all pass")
    if (
        root["decision_status"] != READY_STATUS
        or root["ready_for_live_lock"] is not True
    ):
        raise HostedProjectionValidationError("projection did not reach ready status")
    if exact_rederive:
        with network_denied() as counts:
            expected = _build_projection_bundle_once(fixture)
        if counts["network_calls"] != 0:
            raise HostedProjectionValidationError("exact rederivation attempted network")
        if canonical_json_bytes(root) != canonical_json_bytes(expected):
            raise HostedProjectionValidationError(
                "coherently re-signed projection differs from sealed derivation"
            )


def provider_payload_for_blinded_id(
    bundle: Mapping[str, Any], blinded_request_id: str
) -> JsonObject:
    validate_projection_bundle(bundle, exact_rederive=False)
    matches = [
        row["payload"]
        for row in bundle["provider_payloads"]
        if row["blinded_request_id"] == blinded_request_id
    ]
    if len(matches) != 1:
        raise HostedProjectionValidationError("unknown or duplicate blinded request ID")
    payload = _clone(matches[0])
    validate_provider_payload(payload)
    return payload


def public_treatment_key(bundle: Mapping[str, Any]) -> JsonObject:
    validate_projection_bundle(bundle, exact_rederive=False)
    return _clone(bundle["public_treatment_key"])


def _expect_rejected(action: Any, label: str) -> bool:
    try:
        action()
    except HostedProjectionValidationError:
        return True
    raise HostedProjectionValidationError(f"negative mutation was accepted: {label}")


def _coherently_resign_payload_mutation(bundle: Mapping[str, Any]) -> JsonObject:
    mutated = _clone(bundle)
    treatment_rows = mutated["public_treatment_key"]["treatments"]
    d_treatment = next(row for row in treatment_rows if row["treatment_id"] == "D")
    d_wrapper = next(
        row
        for row in mutated["provider_payloads"]
        if row["blinded_request_id"] == d_treatment["blinded_request_id"]
    )
    d_wrapper["payload"]["decision_slots"][0]["description"] += " MUTATED"
    new_hash = fingerprint(d_wrapper["payload"])
    d_wrapper["provider_payload_sha256"] = new_hash
    d_treatment["provider_payload_sha256"] = new_hash
    mutated["public_treatment_key"] = _with_fingerprint(
        _without_fingerprint(mutated["public_treatment_key"])
    )
    return _with_fingerprint(_without_fingerprint(mutated))


def self_test() -> JsonObject:
    fixture = load_fixture()
    with network_denied() as outer_counts:
        first = build_projection_bundle()
        second = build_projection_bundle()
    validate_projection_bundle(first, fixture=fixture, exact_rederive=True)
    exact_twice = canonical_json_bytes(first) == canonical_json_bytes(second)
    key = first["public_treatment_key"]
    by_treatment = {
        row["treatment_id"]: provider_payload_for_blinded_id(
            first, row["blinded_request_id"]
        )
        for row in key["treatments"]
    }

    forbidden = _clone(by_treatment["D"])
    forbidden["gold"] = {"answer": "never-provider-input"}
    arm_leak = _clone(by_treatment["D"])
    arm_leak["arm_id"] = "D"
    blind_leak = _clone(by_treatment["D"])
    blind_leak["blinded_request_id"] = fixture["block"]["blinded_request_ids"]["D"]
    raw_mutation = _clone(by_treatment["D"])
    raw_mutation["all_raw_evidence"][0]["text"] += " MUTATED"

    source_label = "v0_5_5_control_bundle"
    source_spec = _source_lock_as_fixture()["files"][source_label]
    source_raw = (ROOT / source_spec["path"]).read_bytes()
    source_tamper = _expect_rejected(
        lambda: _verify_receipt_bytes(source_label, source_raw + b"x", source_spec),
        "source byte append",
    )
    fixture_mutation = _clone(fixture)
    fixture_mutation["block"]["revision_modes"]["D"] = "coherently_resigned_drift"
    fixture_mutation["fixture_fingerprint_sha256"] = fingerprint(
        {
            key: value
            for key, value in fixture_mutation.items()
            if key != "fixture_fingerprint_sha256"
        }
    )
    coherent_mutation = _coherently_resign_payload_mutation(first)

    subchecks = {
        "arm_label_injection_rejected": _expect_rejected(
            lambda: validate_provider_payload(arm_leak), "arm label injection"
        ),
        "blinded_id_injection_rejected": _expect_rejected(
            lambda: validate_provider_payload(blind_leak), "blind ID injection"
        ),
        "cd_only_deterministic_placement_differs": first["matched_geometry_audit"][
            "status"
        ]
        == "PASS",
        "coherent_payload_resign_rejected": _expect_rejected(
            lambda: validate_projection_bundle(
                coherent_mutation, fixture=fixture, exact_rederive=True
            ),
            "coherent payload resign",
        ),
        "exact_v0_5_5_source_gate_pass": first["source_gate"]["status"] == "PASS",
        "fixture_coherent_resign_rejected": _expect_rejected(
            lambda: validate_fixture(fixture_mutation), "fixture coherent resign"
        ),
        "forbidden_downstream_injection_rejected": _expect_rejected(
            lambda: validate_provider_payload(forbidden), "gold injection"
        ),
        "network_calls_zero": outer_counts["network_calls"] == 0,
        "payload_source_mutation_rejected": _expect_rejected(
            lambda: validate_provider_payload(
                raw_mutation,
                fixture=fixture,
                exact_treatment="D",
                exact_source=True,
            ),
            "raw payload mutation",
        ),
        "provider_calls_zero": first["provider_calls"] == 0,
        "source_byte_tamper_rejected": source_tamper,
        "treatment_key_absent_from_all_payloads": all(
            row["blinded_request_id"]
            not in canonical_json_bytes(by_treatment[row["treatment_id"]]).decode("utf-8")
            for row in key["treatments"]
        ),
        "two_build_byte_identical": exact_twice,
    }
    status = "PASS" if all(subchecks.values()) else "FAIL"
    return _with_fingerprint(
        {
            "decision_status": READY_STATUS if status == "PASS" else STOP_STATUS,
            "network_calls": 0,
            "provider_calls": 0,
            "projection_fingerprint_sha256": first["fingerprint_sha256"],
            "schema_version": SELF_TEST_SCHEMA_VERSION,
            "status": status,
            "subchecks": subchecks,
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        type=Path,
        default=DEFAULT_FIXTURE,
        help="Exact canonical v0.6 projection fixture.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run network-zero projection and adversarial checks.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON instead of canonical compact JSON.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = self_test() if args.self_test else build_projection_bundle(args.fixture)
    if args.pretty:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(canonical_json_bytes(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
