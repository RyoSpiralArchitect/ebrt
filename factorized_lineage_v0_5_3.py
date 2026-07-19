#!/usr/bin/env python3
"""Network-zero factorized lineage core for EBRT v0.5.3.

The module migrates the frozen v0.5.2 hosted walkthrough into a small public
dependency program.  It deliberately does not call a provider and does not
read semantic gold until both the lossless and repaired graphs have been
sealed and fingerprinted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import socket
import tempfile
from collections import deque
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Union
from unittest import mock


ROOT = Path(__file__).resolve().parent
DEFAULT_SOURCE_ARTIFACT_DIR = (
    ROOT / "artifacts" / "demo_hackathon_strategy_walkthrough_v0_5_2_live_r01"
)
DEFAULT_FIXTURE_PATH = ROOT / "fixtures" / "hackathon_strategy_walkthrough_v0_5_2.json"
DEFAULT_OVERLAY_PATH = (
    ROOT / "fixtures" / "factorized_lineage_v0_5_3_repair_overlay.json"
)
DEFAULT_GOLD_PATH = ROOT / "fixtures" / "factorized_lineage_v0_5_3_closure_gold.json"

GRAPH_SCHEMA_VERSION = "ebrt-factorized-lineage-graph-v0.5.3"
OVERLAY_SCHEMA_VERSION = "ebrt-factorized-lineage-repair-overlay-v0.5.3"
CLOSURE_SCHEMA_VERSION = "ebrt-factorized-lineage-closure-v0.5.3"
GOLD_SCHEMA_VERSION = "ebrt-factorized-lineage-closure-gold-v0.5.3"
GRADE_SCHEMA_VERSION = "ebrt-factorized-lineage-grade-v0.5.3"
REGRESSION_SCHEMA_VERSION = "ebrt-factorized-lineage-regression-v0.5.3"
ABLATION_SCHEMA_VERSION = "ebrt-factorized-lineage-overlay-ablation-v0.5.3"
WITNESS_RANKING_POLICY = (
    "within_class_minimize_repair_overlay_edges_then_path_length_then_"
    "node_path_then_edge_path"
)

NODE_TYPES = ("evidence", "support", "fact", "constraint")
EDGE_TYPES = ("supports", "depends_on", "invalidates")
PROVENANCE_VALUES = ("observed", "migration_inferred", "repair_overlay")
ALLOWED_EDGE_TYPE_PAIRS = {
    "supports": frozenset({("evidence", "support")}),
    "depends_on": frozenset(
        {
            ("support", "fact"),
            ("support", "constraint"),
            ("fact", "fact"),
        }
    ),
    "invalidates": frozenset({("evidence", "evidence")}),
}

EXPECTED_DEMO_FILE_SHA256 = (
    "f6df3c0a371027fd6ed35cfcc75f0b05dc540ebb6d08efeb3764ab62b4616f6b"
)
EXPECTED_DEMO_RESULT_FINGERPRINT = (
    "2e641e0f11f17bb16cbe629048e9cc8cff49706147616d888487f38b243430d4"
)
EXPECTED_FIXTURE_FILE_SHA256 = (
    "ef0b1d44ece10e7412460d9abac4791fe3f3a0172e398bca7a0d8957094f56d2"
)
EXPECTED_FIXTURE_FINGERPRINT = (
    "6fd092005a849b493fa0c812a83e5ba604e84e0870cc72337bb408bdbaccb2ad"
)
EXPECTED_PUBLIC_CARD_FINGERPRINT = (
    "92660291d580731edbf3eced448c0a690f60cfdd0994787e05bfffbfb78e2148"
)

EXPECTED_NODE_IDS = frozenset(
    {
        "evidence:R1",
        "evidence:R2",
        "evidence:R3",
        "evidence:R4",
        "evidence:R5",
        "evidence:R6",
        "support:judging_basis",
        "support:demo_readiness",
        "support:video_constraint",
        "support:superseding_guidance",
        "fact:final_priority",
        "fact:demo_centerpiece",
        "constraint:video_constraint",
    }
)
EXPECTED_REPAIR_EDGES = (
    {
        "edge_id": "repair:demo_readiness->final_priority",
        "edge_type": "depends_on",
        "source_node_id": "support:demo_readiness",
        "target_node_id": "fact:final_priority",
        "provenance": "repair_overlay",
    },
    {
        "edge_id": "repair:final_priority->demo_centerpiece",
        "edge_type": "depends_on",
        "source_node_id": "fact:final_priority",
        "target_node_id": "fact:demo_centerpiece",
        "provenance": "repair_overlay",
    },
)

MIGRATION_ROLE_SPECS = (
    {
        "evidence_ids": ["R4"],
        "support_node_id": "support:demo_readiness",
        "support_role": "demo_readiness",
        "target_node_ids": ["fact:demo_centerpiece"],
    },
    {
        "evidence_ids": ["R2"],
        "support_node_id": "support:judging_basis",
        "support_role": "judging_basis",
        "target_node_ids": ["fact:final_priority"],
    },
    {
        "evidence_ids": ["R6"],
        "support_node_id": "support:superseding_guidance",
        "support_role": "superseding_guidance",
        "target_node_ids": ["fact:demo_centerpiece", "fact:final_priority"],
    },
    {
        "evidence_ids": ["R5"],
        "support_node_id": "support:video_constraint",
        "support_role": "video_constraint",
        "target_node_ids": ["constraint:video_constraint"],
    },
)

GRAPH_CLAIM_BOUNDARY = (
    "This is a network-zero migration of one frozen v0.5.2 synthetic walkthrough, not fresh model evidence.",
    "The public graph contains exactly four node types and three edge types; it is not a general knowledge graph.",
    "Observed provider citations are preserved separately from inferred structural edges and the contaminated repair overlay.",
    "The four migration roles and their evidence/target bindings are case-specific supplied structural annotations derived from the frozen card, not autonomously discovered semantics.",
    "The v0.5.2 strict endpoint remains false; the repaired DAG is a separate engineering regression.",
    "No GPT hidden state is read or edited, and no gradient crosses the adapter, JSON, provider, or grading boundaries.",
)


class FactorizedLineageValidationError(RuntimeError):
    """A v0.5.3 public lineage invariant failed."""


# Stable compatibility name used by the artifact builder.
LineageValidationError = FactorizedLineageValidationError


JsonPath = Union[str, Path]
JsonObject = dict[str, Any]


def _canonical_json_bytes(value: Any, *, trailing_newline: bool = False) -> bytes:
    output = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return output + (b"\n" if trailing_newline else b"")


def _pretty_json(value: Any) -> str:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_path(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _fingerprint(value: Any) -> str:
    return _sha256_bytes(_canonical_json_bytes(value))


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _reject_json_constant(value: str) -> None:
    raise FactorizedLineageValidationError(f"non-finite JSON constant: {value}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> JsonObject:
    output: JsonObject = {}
    for key, value in pairs:
        if key in output:
            raise FactorizedLineageValidationError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def _loads_json_strict(raw: str, *, label: str) -> JsonObject:
    try:
        value = json.loads(
            raw,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise FactorizedLineageValidationError(
            f"invalid JSON for {label}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise FactorizedLineageValidationError(f"expected JSON object for {label}")
    _ensure_finite(value, label=label)
    return value


def _load_json(path: JsonPath) -> JsonObject:
    resolved = Path(path)
    if not resolved.is_file() or resolved.is_symlink():
        raise FactorizedLineageValidationError(
            f"expected regular non-symlink JSON file: {resolved}"
        )
    return _loads_json_strict(resolved.read_text(encoding="utf-8"), label=str(resolved))


def _clone(value: Any) -> Any:
    return json.loads(_canonical_json_bytes(value))


def _ensure_finite(value: Any, *, label: str) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise FactorizedLineageValidationError(f"non-finite number at {label}")
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise FactorizedLineageValidationError(f"non-string key at {label}")
            _ensure_finite(child, label=f"{label}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _ensure_finite(child, label=f"{label}[{index}]")


def _require_exact_keys(
    value: Mapping[str, Any], keys: set[str], *, label: str
) -> None:
    observed = set(value)
    if observed != keys:
        missing = sorted(keys - observed)
        extra = sorted(observed - keys)
        raise FactorizedLineageValidationError(
            f"{label} keys differ: missing={missing}, extra={extra}"
        )


def _require_string(value: Any, *, label: str, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value):
        raise FactorizedLineageValidationError(f"expected string at {label}")
    return value


def _require_string_list(value: Any, *, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise FactorizedLineageValidationError(f"expected string list at {label}")
    if len(value) != len(set(value)):
        raise FactorizedLineageValidationError(f"duplicate value at {label}")
    return list(value)


def _without_fingerprint(value: Mapping[str, Any]) -> JsonObject:
    material = _clone(value)
    material.pop("fingerprint_sha256", None)
    return material


def _normalized_graph_material(graph: Mapping[str, Any]) -> JsonObject:
    material = _without_fingerprint(graph)
    if isinstance(material.get("nodes"), list):
        material["nodes"] = sorted(material["nodes"], key=lambda row: row["node_id"])
    if isinstance(material.get("edges"), list):
        material["edges"] = sorted(material["edges"], key=lambda row: row["edge_id"])
    return material


def graph_fingerprint(graph: Mapping[str, Any]) -> str:
    """Return the order-independent fingerprint of a graph payload."""

    return _fingerprint(_normalized_graph_material(graph))


def _seal_graph(graph: Mapping[str, Any]) -> JsonObject:
    sealed = _clone(graph)
    sealed["nodes"] = sorted(sealed["nodes"], key=lambda row: row["node_id"])
    sealed["edges"] = sorted(sealed["edges"], key=lambda row: row["edge_id"])
    sealed["fingerprint_sha256"] = graph_fingerprint(sealed)
    validate_graph(sealed)
    return sealed


def _validate_public_card(card: Mapping[str, Any]) -> None:
    _require_exact_keys(
        card,
        {
            "checkpoint_id",
            "claim",
            "confidence",
            "current_answer",
            "decision_facts",
            "evidence_ids",
            "invalidated_evidence_ids",
            "revision_cue",
            "schema_version",
            "stance",
            "topic",
        },
        label="source.public_card_snapshot",
    )
    for key in ("checkpoint_id", "claim", "current_answer", "schema_version", "topic"):
        _require_string(card[key], label=f"source.public_card_snapshot.{key}")
    for key in ("confidence", "revision_cue", "stance"):
        value = card[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise FactorizedLineageValidationError(
                f"expected finite number at source.public_card_snapshot.{key}"
            )
        if not math.isfinite(float(value)):
            raise FactorizedLineageValidationError(
                f"non-finite number at source.public_card_snapshot.{key}"
            )
    evidence_ids = _require_string_list(
        card["evidence_ids"], label="source.public_card_snapshot.evidence_ids"
    )
    invalidated_ids = _require_string_list(
        card["invalidated_evidence_ids"],
        label="source.public_card_snapshot.invalidated_evidence_ids",
    )
    if set(evidence_ids) & set(invalidated_ids):
        raise FactorizedLineageValidationError(
            "active and invalidated public-card evidence overlap"
        )
    facts = card["decision_facts"]
    if not isinstance(facts, list) or not facts:
        raise FactorizedLineageValidationError("public card requires decision_facts")
    slots: set[str] = set()
    for index, fact in enumerate(facts):
        if not isinstance(fact, Mapping):
            raise FactorizedLineageValidationError(
                f"decision_facts[{index}] is not object"
            )
        _require_exact_keys(
            fact, {"slot", "value", "evidence_ids"}, label=f"decision_facts[{index}]"
        )
        slot = _require_string(fact["slot"], label=f"decision_facts[{index}].slot")
        _require_string(fact["value"], label=f"decision_facts[{index}].value")
        citations = _require_string_list(
            fact["evidence_ids"], label=f"decision_facts[{index}].evidence_ids"
        )
        if not citations or not set(citations).issubset(evidence_ids):
            raise FactorizedLineageValidationError(
                f"decision_facts[{index}] citations are not active public evidence"
            )
        if slot in slots:
            raise FactorizedLineageValidationError(f"duplicate decision slot: {slot}")
        slots.add(slot)


def _validate_source(source: Mapping[str, Any]) -> None:
    _require_exact_keys(
        source,
        {
            "artifact_result_fingerprint_sha256",
            "correction_evidence_id",
            "demo_file_sha256",
            "fixture_file_sha256",
            "fixture_fingerprint_sha256",
            "fixture_id",
            "legacy_walkthrough_contract_passed",
            "migration_role_map",
            "phase_id",
            "public_card_fingerprint_sha256",
            "public_card_snapshot",
            "raw_evidence_snapshot",
            "stable_evidence_ids",
        },
        label="source",
    )
    for key in (
        "artifact_result_fingerprint_sha256",
        "demo_file_sha256",
        "fixture_file_sha256",
        "fixture_fingerprint_sha256",
        "public_card_fingerprint_sha256",
    ):
        if not _is_sha256(source[key]):
            raise FactorizedLineageValidationError(f"invalid SHA-256 at source.{key}")
    for key in ("correction_evidence_id", "fixture_id", "phase_id"):
        _require_string(source[key], label=f"source.{key}")
    if source["legacy_walkthrough_contract_passed"] is not False:
        raise FactorizedLineageValidationError(
            "frozen legacy endpoint must remain false"
        )
    if source["migration_role_map"] != list(MIGRATION_ROLE_SPECS):
        raise FactorizedLineageValidationError(
            "declared migration structural role map changed"
        )
    stable_ids = _require_string_list(
        source["stable_evidence_ids"], label="source.stable_evidence_ids"
    )
    if stable_ids != ["R5"]:
        raise FactorizedLineageValidationError("canonical stable evidence must be R5")
    snapshot = source["raw_evidence_snapshot"]
    if not isinstance(snapshot, list) or not snapshot:
        raise FactorizedLineageValidationError("raw_evidence_snapshot must be nonempty")
    seen_ids: set[str] = set()
    seen_ordinals: set[int] = set()
    for index, row in enumerate(snapshot):
        if not isinstance(row, Mapping):
            raise FactorizedLineageValidationError(f"raw_evidence_snapshot[{index}]")
        _require_exact_keys(
            row,
            {"evidence_id", "temporal_ordinal", "text"},
            label=f"raw_evidence_snapshot[{index}]",
        )
        evidence_id = _require_string(
            row["evidence_id"], label=f"raw_evidence_snapshot[{index}].evidence_id"
        )
        _require_string(row["text"], label=f"raw_evidence_snapshot[{index}].text")
        ordinal = row["temporal_ordinal"]
        if isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal <= 0:
            raise FactorizedLineageValidationError("invalid temporal ordinal")
        if evidence_id in seen_ids or ordinal in seen_ordinals:
            raise FactorizedLineageValidationError("duplicate raw evidence identity")
        seen_ids.add(evidence_id)
        seen_ordinals.add(ordinal)
    if seen_ids != {"R1", "R2", "R3", "R4", "R5", "R6"}:
        raise FactorizedLineageValidationError(
            "canonical raw evidence must include R1-R6"
        )
    card = source["public_card_snapshot"]
    if not isinstance(card, Mapping):
        raise FactorizedLineageValidationError("public_card_snapshot must be object")
    _validate_public_card(card)
    if _fingerprint(card) != source["public_card_fingerprint_sha256"]:
        raise FactorizedLineageValidationError("public card fingerprint mismatch")
    if set(card["evidence_ids"]) | set(card["invalidated_evidence_ids"]) != seen_ids:
        raise FactorizedLineageValidationError(
            "public card active plus invalidated evidence must cover raw R1-R6"
        )
    if source["correction_evidence_id"] != "R6":
        raise FactorizedLineageValidationError(
            "canonical correction evidence must be R6"
        )


def _validate_node(node: Mapping[str, Any], *, label: str) -> None:
    _ensure_finite(node, label=label)
    node_type = node.get("node_type")
    if node_type not in NODE_TYPES:
        raise FactorizedLineageValidationError(f"invalid node type at {label}")
    common = {"node_id", "node_type", "provenance"}
    if node_type == "evidence":
        keys = common | {"evidence_id", "temporal_ordinal", "text"}
    elif node_type == "support":
        keys = common | {"support_role"}
    else:
        keys = common | {"slot", "value"}
    _require_exact_keys(node, keys, label=label)
    node_id = _require_string(node["node_id"], label=f"{label}.node_id")
    if node["provenance"] not in PROVENANCE_VALUES:
        raise FactorizedLineageValidationError(f"invalid provenance at {label}")
    if node_type == "evidence":
        evidence_id = _require_string(node["evidence_id"], label=f"{label}.evidence_id")
        if node_id != f"evidence:{evidence_id}":
            raise FactorizedLineageValidationError(
                f"evidence node id mismatch at {label}"
            )
        _require_string(node["text"], label=f"{label}.text")
        ordinal = node["temporal_ordinal"]
        if isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal <= 0:
            raise FactorizedLineageValidationError(f"invalid ordinal at {label}")
        if node["provenance"] != "observed":
            raise FactorizedLineageValidationError("Evidence nodes must be observed")
    elif node_type == "support":
        support_role = _require_string(
            node["support_role"], label=f"{label}.support_role"
        )
        if node_id != f"support:{support_role}":
            raise FactorizedLineageValidationError(
                f"support node id mismatch at {label}"
            )
        if node["provenance"] != "migration_inferred":
            raise FactorizedLineageValidationError(
                "support node provenance must be migration_inferred"
            )
    else:
        slot = _require_string(node["slot"], label=f"{label}.slot")
        _require_string(node["value"], label=f"{label}.value")
        prefix = {
            "fact": "fact",
            "constraint": "constraint",
        }[node_type]
        if node_id != f"{prefix}:{slot}":
            raise FactorizedLineageValidationError(f"typed node id mismatch at {label}")
        if node["provenance"] != "observed":
            raise FactorizedLineageValidationError(
                f"{node_type} node provenance must be observed"
            )


def _validate_edge(
    edge: Mapping[str, Any],
    *,
    node_by_id: Mapping[str, Mapping[str, Any]],
    label: str,
) -> None:
    _require_exact_keys(
        edge,
        {"edge_id", "edge_type", "provenance", "source_node_id", "target_node_id"},
        label=label,
    )
    for key in ("edge_id", "edge_type", "source_node_id", "target_node_id"):
        _require_string(edge[key], label=f"{label}.{key}")
    if edge["edge_type"] not in EDGE_TYPES:
        raise FactorizedLineageValidationError(f"invalid edge type at {label}")
    if edge["provenance"] not in PROVENANCE_VALUES:
        raise FactorizedLineageValidationError(f"invalid edge provenance at {label}")
    source = node_by_id.get(edge["source_node_id"])
    target = node_by_id.get(edge["target_node_id"])
    if source is None or target is None:
        raise FactorizedLineageValidationError(f"dangling edge at {label}")
    pair = (source["node_type"], target["node_type"])
    if pair not in ALLOWED_EDGE_TYPE_PAIRS[edge["edge_type"]]:
        raise FactorizedLineageValidationError(
            f"forbidden {edge['edge_type']} direction {pair} at {label}"
        )
    if edge["source_node_id"] == edge["target_node_id"]:
        raise FactorizedLineageValidationError(f"self edge at {label}")
    if edge["edge_type"] == "supports":
        if edge["provenance"] != "migration_inferred":
            raise FactorizedLineageValidationError(
                "supports edges to inferred roles must be migration_inferred"
            )
    elif edge["edge_type"] == "invalidates":
        if edge["provenance"] != "observed":
            raise FactorizedLineageValidationError(
                "invalidates edges must preserve observed provenance"
            )
    elif edge["provenance"] not in {"migration_inferred", "repair_overlay"}:
        raise FactorizedLineageValidationError(
            "depends_on edges must be inferred or repair provenance"
        )
    if edge["edge_type"] == "invalidates":
        if source["temporal_ordinal"] <= target["temporal_ordinal"]:
            raise FactorizedLineageValidationError(
                "invalidation must point from later to earlier evidence"
            )


def _assert_acyclic(
    node_by_id: Mapping[str, Mapping[str, Any]], edges: Sequence[Mapping[str, Any]]
) -> None:
    indegree = {node_id: 0 for node_id in node_by_id}
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in node_by_id}
    for edge in edges:
        source = str(edge["source_node_id"])
        target = str(edge["target_node_id"])
        adjacency[source].append(target)
        indegree[target] += 1
    queue = deque(
        sorted(node_id for node_id, degree in indegree.items() if degree == 0)
    )
    visited = 0
    while queue:
        node_id = queue.popleft()
        visited += 1
        for target in sorted(adjacency[node_id]):
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if visited != len(node_by_id):
        raise FactorizedLineageValidationError("lineage graph contains a cycle")


def _validate_source_consistency(
    graph: Mapping[str, Any],
    node_by_id: Mapping[str, Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
) -> None:
    source = graph["source"]
    card = source["public_card_snapshot"]
    raw_by_id = {row["evidence_id"]: row for row in source["raw_evidence_snapshot"]}
    evidence_nodes = {
        node["evidence_id"]: node
        for node in node_by_id.values()
        if node["node_type"] == "evidence"
    }
    if set(evidence_nodes) != set(raw_by_id):
        raise FactorizedLineageValidationError(
            "Evidence nodes do not preserve raw snapshot"
        )
    for evidence_id, row in raw_by_id.items():
        node = evidence_nodes[evidence_id]
        if (
            node["text"] != row["text"]
            or node["temporal_ordinal"] != row["temporal_ordinal"]
        ):
            raise FactorizedLineageValidationError(
                f"Evidence node changed frozen source: {evidence_id}"
            )
    fact_by_slot = {fact["slot"]: fact for fact in card["decision_facts"]}
    stable_ids = set(source["stable_evidence_ids"])
    observed_support_pairs: set[tuple[str, str]] = set()
    inferred_target_pairs: set[tuple[str, str]] = set()
    observed_invalidations: set[tuple[str, str]] = set()
    for edge in edges:
        if edge["edge_type"] == "supports":
            evidence_id = node_by_id[edge["source_node_id"]]["evidence_id"]
            observed_support_pairs.add((evidence_id, edge["target_node_id"]))
        elif (
            edge["edge_type"] == "depends_on"
            and edge["provenance"] == "migration_inferred"
        ):
            inferred_target_pairs.add((edge["source_node_id"], edge["target_node_id"]))
        elif edge["edge_type"] == "invalidates":
            source_id = node_by_id[edge["source_node_id"]]["evidence_id"]
            target_id = node_by_id[edge["target_node_id"]]["evidence_id"]
            observed_invalidations.add((source_id, target_id))
    expected_support_pairs: set[tuple[str, str]] = set()
    expected_target_pairs: set[tuple[str, str]] = set()
    expected_non_evidence_nodes: set[str] = set()
    evidence_by_target: dict[str, set[str]] = {}
    for slot, fact in fact_by_slot.items():
        is_constraint = bool(set(fact["evidence_ids"])) and set(
            fact["evidence_ids"]
        ).issubset(stable_ids)
        target_id = f"constraint:{slot}" if is_constraint else f"fact:{slot}"
        target = node_by_id.get(target_id)
        if target is None:
            raise FactorizedLineageValidationError(
                f"missing typed target for slot {slot}"
            )
        if target["value"] != fact["value"]:
            raise FactorizedLineageValidationError(f"value changed for slot {slot}")
        expected_non_evidence_nodes.add(target_id)
        evidence_by_target[target_id] = set()
    for role_spec in source["migration_role_map"]:
        support_id = role_spec["support_node_id"]
        support = node_by_id.get(support_id)
        if support is None or support["support_role"] != role_spec["support_role"]:
            raise FactorizedLineageValidationError(
                f"missing declared migration role node: {support_id}"
            )
        expected_non_evidence_nodes.add(support_id)
        expected_support_pairs.update(
            (evidence_id, support_id) for evidence_id in role_spec["evidence_ids"]
        )
        expected_target_pairs.update(
            (support_id, target_id) for target_id in role_spec["target_node_ids"]
        )
        for target_id in role_spec["target_node_ids"]:
            if target_id not in evidence_by_target:
                raise FactorizedLineageValidationError(
                    f"migration role targets unknown fact: {target_id}"
                )
            evidence_by_target[target_id].update(role_spec["evidence_ids"])
    for slot, fact in fact_by_slot.items():
        is_constraint = bool(set(fact["evidence_ids"])) and set(
            fact["evidence_ids"]
        ).issubset(stable_ids)
        target_id = f"constraint:{slot}" if is_constraint else f"fact:{slot}"
        if evidence_by_target[target_id] != set(fact["evidence_ids"]):
            raise FactorizedLineageValidationError(
                f"migration role factorization changed observed citations for {slot}"
            )
    observed_non_evidence_nodes = {
        node_id
        for node_id, node in node_by_id.items()
        if node["node_type"] != "evidence"
    }
    if observed_non_evidence_nodes != expected_non_evidence_nodes:
        raise FactorizedLineageValidationError(
            "typed nodes do not losslessly map card facts"
        )
    if observed_support_pairs != expected_support_pairs:
        raise FactorizedLineageValidationError(
            "migration support edges do not preserve declared evidence roles"
        )
    if inferred_target_pairs != expected_target_pairs:
        raise FactorizedLineageValidationError(
            "inferred structural edges do not preserve fact targets"
        )
    expected_invalidations = {
        (source["correction_evidence_id"], evidence_id)
        for evidence_id in card["invalidated_evidence_ids"]
    }
    if observed_invalidations != expected_invalidations:
        raise FactorizedLineageValidationError(
            "invalidation edges do not preserve the public card"
        )


def validate_graph(graph: Mapping[str, Any]) -> None:
    """Validate the complete strict graph contract."""

    if not isinstance(graph, Mapping):
        raise FactorizedLineageValidationError("graph must be an object")
    _ensure_finite(graph, label="graph")
    _require_exact_keys(
        graph,
        {
            "claim_boundary",
            "derivation",
            "edges",
            "fingerprint_sha256",
            "graph_id",
            "nodes",
            "schema_version",
            "source",
            "status",
            "vocabulary",
        },
        label="graph",
    )
    if graph["schema_version"] != GRAPH_SCHEMA_VERSION:
        raise FactorizedLineageValidationError("graph schema version mismatch")
    _require_string(graph["graph_id"], label="graph.graph_id")
    if graph["status"] not in {
        "LOSSLESS_MIGRATION",
        "CONTAMINATED_REPAIR_OVERLAY",
    }:
        raise FactorizedLineageValidationError("invalid graph status")
    vocabulary = graph["vocabulary"]
    if not isinstance(vocabulary, Mapping):
        raise FactorizedLineageValidationError("vocabulary must be object")
    _require_exact_keys(vocabulary, {"edge_types", "node_types"}, label="vocabulary")
    if vocabulary["node_types"] != list(NODE_TYPES):
        raise FactorizedLineageValidationError("node vocabulary must be exact")
    if vocabulary["edge_types"] != list(EDGE_TYPES):
        raise FactorizedLineageValidationError("edge vocabulary must be exact")
    source = graph["source"]
    if not isinstance(source, Mapping):
        raise FactorizedLineageValidationError("source must be object")
    _validate_source(source)
    derivation = graph["derivation"]
    if not isinstance(derivation, Mapping):
        raise FactorizedLineageValidationError("derivation must be object")
    _require_exact_keys(
        derivation,
        {"kind", "overlay_fingerprint_sha256", "parent_graph_fingerprint_sha256"},
        label="derivation",
    )
    if graph["status"] == "LOSSLESS_MIGRATION":
        if derivation != {
            "kind": "lossless_v0_5_2_migration",
            "overlay_fingerprint_sha256": None,
            "parent_graph_fingerprint_sha256": None,
        }:
            raise FactorizedLineageValidationError("invalid lossless derivation")
    else:
        if derivation["kind"] != "contaminated_repair_overlay":
            raise FactorizedLineageValidationError("invalid repair derivation kind")
        if not _is_sha256(derivation["overlay_fingerprint_sha256"]):
            raise FactorizedLineageValidationError("invalid overlay fingerprint")
        if not _is_sha256(derivation["parent_graph_fingerprint_sha256"]):
            raise FactorizedLineageValidationError("invalid parent graph fingerprint")
    claim_boundary = _require_string_list(
        graph["claim_boundary"], label="graph.claim_boundary"
    )
    if tuple(claim_boundary) != GRAPH_CLAIM_BOUNDARY:
        raise FactorizedLineageValidationError("graph claim boundary changed")
    nodes = graph["nodes"]
    edges = graph["edges"]
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise FactorizedLineageValidationError("nodes and edges must be arrays")
    node_by_id: dict[str, Mapping[str, Any]] = {}
    for index, node in enumerate(nodes):
        if not isinstance(node, Mapping):
            raise FactorizedLineageValidationError(f"nodes[{index}] must be object")
        _validate_node(node, label=f"nodes[{index}]")
        node_id = str(node["node_id"])
        if node_id in node_by_id:
            raise FactorizedLineageValidationError(f"duplicate node id: {node_id}")
        node_by_id[node_id] = node
    if set(node_by_id) != EXPECTED_NODE_IDS:
        raise FactorizedLineageValidationError("canonical node set changed")
    edge_ids: set[str] = set()
    edge_signatures: set[tuple[str, str, str]] = set()
    repair_edges: list[Mapping[str, Any]] = []
    for index, edge in enumerate(edges):
        if not isinstance(edge, Mapping):
            raise FactorizedLineageValidationError(f"edges[{index}] must be object")
        _validate_edge(edge, node_by_id=node_by_id, label=f"edges[{index}]")
        edge_id = str(edge["edge_id"])
        signature = (
            str(edge["edge_type"]),
            str(edge["source_node_id"]),
            str(edge["target_node_id"]),
        )
        if edge_id in edge_ids:
            raise FactorizedLineageValidationError(f"duplicate edge id: {edge_id}")
        if signature in edge_signatures:
            raise FactorizedLineageValidationError(
                f"duplicate edge semantics: {signature}"
            )
        edge_ids.add(edge_id)
        edge_signatures.add(signature)
        if edge["provenance"] == "repair_overlay":
            repair_edges.append(edge)
    if graph["status"] == "LOSSLESS_MIGRATION" and repair_edges:
        raise FactorizedLineageValidationError(
            "lossless graph cannot contain repair edges"
        )
    if graph["status"] == "CONTAMINATED_REPAIR_OVERLAY":
        if sorted(repair_edges, key=lambda row: row["edge_id"]) != sorted(
            EXPECTED_REPAIR_EDGES, key=lambda row: row["edge_id"]
        ):
            raise FactorizedLineageValidationError(
                "repair graph must contain exact overlay"
            )
    _assert_acyclic(node_by_id, edges)
    _validate_source_consistency(graph, node_by_id, edges)
    if not _is_sha256(graph["fingerprint_sha256"]):
        raise FactorizedLineageValidationError("invalid graph fingerprint")
    if graph_fingerprint(graph) != graph["fingerprint_sha256"]:
        raise FactorizedLineageValidationError("graph fingerprint mismatch")


def _validate_frozen_sources(
    source_artifact_dir: JsonPath, fixture_path: JsonPath
) -> tuple[JsonObject, JsonObject, Path, Path]:
    artifact_dir = Path(source_artifact_dir)
    demo_path = artifact_dir / "demo.json"
    resolved_fixture = Path(fixture_path)
    if _sha256_path(demo_path) != EXPECTED_DEMO_FILE_SHA256:
        raise FactorizedLineageValidationError("frozen v0.5.2 demo bytes changed")
    if _sha256_path(resolved_fixture) != EXPECTED_FIXTURE_FILE_SHA256:
        raise FactorizedLineageValidationError("frozen v0.5.2 fixture bytes changed")
    demo = _load_json(demo_path)
    fixture = _load_json(resolved_fixture)
    if demo.get("fingerprint_sha256") != EXPECTED_DEMO_RESULT_FINGERPRINT:
        raise FactorizedLineageValidationError("unexpected v0.5.2 result fingerprint")
    if _fingerprint(_without_fingerprint(demo)) != demo["fingerprint_sha256"]:
        raise FactorizedLineageValidationError("v0.5.2 result fingerprint mismatch")
    if fixture.get("fixture_fingerprint_sha256") != EXPECTED_FIXTURE_FINGERPRINT:
        raise FactorizedLineageValidationError("unexpected v0.5.2 fixture fingerprint")
    fixture_material = _clone(fixture)
    fixture_material.pop("fixture_fingerprint_sha256")
    if _fingerprint(fixture_material) != fixture["fixture_fingerprint_sha256"]:
        raise FactorizedLineageValidationError("v0.5.2 fixture fingerprint mismatch")
    if demo.get("decision", {}).get("walkthrough_contract_passed") is not False:
        raise FactorizedLineageValidationError(
            "legacy strict endpoint is not frozen false"
        )
    phase = demo.get("phases", {}).get("controlled_after_event")
    if not isinstance(phase, Mapping) or phase.get("status") != "completed":
        raise FactorizedLineageValidationError("frozen after phase is unavailable")
    if (
        phase.get("grade", {}).get("checks", {}).get("required_facts_exact")
        is not False
    ):
        raise FactorizedLineageValidationError("frozen fact-local failure disappeared")
    return demo, fixture, demo_path, resolved_fixture


def load_and_migrate(
    source_artifact_dir: JsonPath = DEFAULT_SOURCE_ARTIFACT_DIR,
    fixture_path: JsonPath = DEFAULT_FIXTURE_PATH,
) -> JsonObject:
    """Losslessly migrate the frozen v0.5.2 card without reading closure gold."""

    demo, fixture, demo_path, resolved_fixture = _validate_frozen_sources(
        source_artifact_dir, fixture_path
    )
    phase = demo["phases"]["controlled_after_event"]
    card = _clone(phase["public_card"])
    _validate_public_card(card)
    if _fingerprint(card) != EXPECTED_PUBLIC_CARD_FINGERPRINT:
        raise FactorizedLineageValidationError("frozen after public card changed")
    case = fixture["case"]
    raw_rows: list[JsonObject] = []
    for ordinal, row in enumerate(case["initial_evidence"], start=1):
        raw_rows.append(
            {
                "evidence_id": row["evidence_id"],
                "temporal_ordinal": ordinal,
                "text": row["text"],
            }
        )
    late = case["late_evidence"]
    raw_rows.append(
        {
            "evidence_id": late["evidence_id"],
            "temporal_ordinal": len(raw_rows) + 1,
            "text": late["text"],
        }
    )
    binding = fixture["case_program_binding"]
    stable_ids = sorted(
        row["evidence_id"]
        for row in binding["evidence_bindings"]
        if row["role"] == "stable_context"
    )
    nodes: list[JsonObject] = [
        {
            "evidence_id": row["evidence_id"],
            "node_id": f"evidence:{row['evidence_id']}",
            "node_type": "evidence",
            "provenance": "observed",
            "temporal_ordinal": row["temporal_ordinal"],
            "text": row["text"],
        }
        for row in raw_rows
    ]
    edges: list[JsonObject] = []
    for fact in card["decision_facts"]:
        slot = fact["slot"]
        value = fact["value"]
        is_constraint = bool(fact["evidence_ids"]) and set(
            fact["evidence_ids"]
        ).issubset(stable_ids)
        target_type = "constraint" if is_constraint else "fact"
        target_prefix = "constraint" if is_constraint else "fact"
        target_id = f"{target_prefix}:{slot}"
        nodes.append(
            {
                "node_id": target_id,
                "node_type": target_type,
                "provenance": "observed",
                "slot": slot,
                "value": value,
            }
        )
    for role_spec in MIGRATION_ROLE_SPECS:
        support_id = role_spec["support_node_id"]
        nodes.append(
            {
                "node_id": support_id,
                "node_type": "support",
                "provenance": "migration_inferred",
                "support_role": role_spec["support_role"],
            }
        )
        for evidence_id in role_spec["evidence_ids"]:
            edges.append(
                {
                    "edge_id": f"migration_inferred:{evidence_id}->{support_id}",
                    "edge_type": "supports",
                    "provenance": "migration_inferred",
                    "source_node_id": f"evidence:{evidence_id}",
                    "target_node_id": support_id,
                }
            )
        for target_id in role_spec["target_node_ids"]:
            edges.append(
                {
                    "edge_id": f"migration_inferred:{support_id}->{target_id}",
                    "edge_type": "depends_on",
                    "provenance": "migration_inferred",
                    "source_node_id": support_id,
                    "target_node_id": target_id,
                }
            )
    event = binding["event"]
    correction_id = event["correction_evidence_id"]
    if sorted(card["invalidated_evidence_ids"]) != sorted(
        event["invalidated_evidence_ids"]
    ):
        raise FactorizedLineageValidationError(
            "fixture event and public-card invalidation disagree"
        )
    for invalidated_id in card["invalidated_evidence_ids"]:
        edges.append(
            {
                "edge_id": f"observed:{correction_id}->invalidates:{invalidated_id}",
                "edge_type": "invalidates",
                "provenance": "observed",
                "source_node_id": f"evidence:{correction_id}",
                "target_node_id": f"evidence:{invalidated_id}",
            }
        )
    graph: JsonObject = {
        "claim_boundary": list(GRAPH_CLAIM_BOUNDARY),
        "derivation": {
            "kind": "lossless_v0_5_2_migration",
            "overlay_fingerprint_sha256": None,
            "parent_graph_fingerprint_sha256": None,
        },
        "edges": edges,
        "graph_id": "hackathon_strategy_v0_5_2_lossless_lineage",
        "nodes": nodes,
        "schema_version": GRAPH_SCHEMA_VERSION,
        "source": {
            "artifact_result_fingerprint_sha256": demo["fingerprint_sha256"],
            "correction_evidence_id": correction_id,
            "demo_file_sha256": _sha256_path(demo_path),
            "fixture_file_sha256": _sha256_path(resolved_fixture),
            "fixture_fingerprint_sha256": fixture["fixture_fingerprint_sha256"],
            "fixture_id": fixture["fixture_id"],
            "legacy_walkthrough_contract_passed": False,
            "migration_role_map": _clone(list(MIGRATION_ROLE_SPECS)),
            "phase_id": "controlled_after_event",
            "public_card_fingerprint_sha256": _fingerprint(card),
            "public_card_snapshot": card,
            "raw_evidence_snapshot": raw_rows,
            "stable_evidence_ids": stable_ids,
        },
        "status": "LOSSLESS_MIGRATION",
        "vocabulary": {
            "edge_types": list(EDGE_TYPES),
            "node_types": list(NODE_TYPES),
        },
    }
    return _seal_graph(graph)


def _load_mapping(
    value: Union[JsonPath, Mapping[str, Any]], *, label: str
) -> JsonObject:
    if isinstance(value, (str, Path)):
        return _load_json(value)
    if not isinstance(value, Mapping):
        raise FactorizedLineageValidationError(f"{label} must be object or path")
    _ensure_finite(value, label=label)
    return _clone(value)


def _overlay_fingerprint(overlay: Mapping[str, Any]) -> str:
    material = _without_fingerprint(overlay)
    if isinstance(material.get("edges"), list):
        material["edges"] = sorted(material["edges"], key=lambda row: row["edge_id"])
    return _fingerprint(material)


def validate_repair_overlay(overlay: Mapping[str, Any]) -> None:
    _require_exact_keys(
        overlay,
        {
            "claim_boundary",
            "edges",
            "fingerprint_sha256",
            "overlay_id",
            "schema_version",
            "source_graph_fingerprint_sha256",
            "status",
        },
        label="overlay",
    )
    if overlay["schema_version"] != OVERLAY_SCHEMA_VERSION:
        raise FactorizedLineageValidationError("overlay schema mismatch")
    if overlay["status"] != "LOCKED_CONTAMINATED_ENGINEERING_REPAIR":
        raise FactorizedLineageValidationError("overlay status mismatch")
    _require_string(overlay["overlay_id"], label="overlay.overlay_id")
    if not _is_sha256(overlay["source_graph_fingerprint_sha256"]):
        raise FactorizedLineageValidationError("invalid overlay source fingerprint")
    boundary = _require_string_list(
        overlay["claim_boundary"], label="overlay.claim_boundary"
    )
    if not boundary or not any("contaminated" in line.lower() for line in boundary):
        raise FactorizedLineageValidationError("overlay must declare contamination")
    if not isinstance(overlay["edges"], list) or sorted(
        overlay["edges"], key=lambda row: row.get("edge_id", "")
    ) != sorted(EXPECTED_REPAIR_EDGES, key=lambda row: row["edge_id"]):
        raise FactorizedLineageValidationError(
            "overlay must contain exact two-edge repair"
        )
    if not _is_sha256(overlay["fingerprint_sha256"]):
        raise FactorizedLineageValidationError("invalid overlay fingerprint")
    if _overlay_fingerprint(overlay) != overlay["fingerprint_sha256"]:
        raise FactorizedLineageValidationError("overlay fingerprint mismatch")


def apply_repair_overlay(
    observed_graph: Mapping[str, Any],
    overlay: Union[JsonPath, Mapping[str, Any]],
) -> JsonObject:
    """Apply the separate, explicitly contaminated two-edge repair overlay."""

    validate_graph(observed_graph)
    if observed_graph["status"] != "LOSSLESS_MIGRATION":
        raise FactorizedLineageValidationError("overlay requires lossless parent graph")
    loaded = _load_mapping(overlay, label="overlay")
    validate_repair_overlay(loaded)
    if (
        loaded["source_graph_fingerprint_sha256"]
        != observed_graph["fingerprint_sha256"]
    ):
        raise FactorizedLineageValidationError("overlay parent graph mismatch")
    repaired = _clone(observed_graph)
    repaired.pop("fingerprint_sha256")
    repaired["graph_id"] = "hackathon_strategy_v0_5_3_factorized_lineage_repair"
    repaired["status"] = "CONTAMINATED_REPAIR_OVERLAY"
    repaired["derivation"] = {
        "kind": "contaminated_repair_overlay",
        "overlay_fingerprint_sha256": loaded["fingerprint_sha256"],
        "parent_graph_fingerprint_sha256": observed_graph["fingerprint_sha256"],
    }
    repaired["edges"].extend(_clone(loaded["edges"]))
    return _seal_graph(repaired)


def _propagation_edges(graph: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        edge
        for edge in graph["edges"]
        if edge["edge_type"] in {"supports", "depends_on"}
    ]


def _invalidated_evidence_ids(graph: Mapping[str, Any]) -> list[str]:
    node_by_id = {node["node_id"]: node for node in graph["nodes"]}
    return sorted(
        node_by_id[edge["target_node_id"]]["evidence_id"]
        for edge in graph["edges"]
        if edge["edge_type"] == "invalidates"
    )


def _all_paths(
    start: str,
    target: str,
    adjacency: Mapping[str, Sequence[tuple[str, str]]],
) -> list[tuple[tuple[str, ...], tuple[str, ...]]]:
    paths: list[tuple[tuple[str, ...], tuple[str, ...]]] = []

    def visit(
        node_id: str, node_path: tuple[str, ...], edge_path: tuple[str, ...]
    ) -> None:
        if node_id == target:
            paths.append((node_path, edge_path))
            return
        for next_id, edge_id in adjacency.get(node_id, ()):
            if next_id in node_path:
                raise FactorizedLineageValidationError("cycle reached during closure")
            visit(next_id, node_path + (next_id,), edge_path + (edge_id,))

    visit(start, (start,), ())
    return paths


def _is_direct_path(
    node_path: Sequence[str], node_by_id: Mapping[str, Mapping[str, Any]]
) -> bool:
    return (
        len(node_path) == 3
        and node_by_id[node_path[0]]["node_type"] == "evidence"
        and node_by_id[node_path[1]]["node_type"] == "support"
        and node_by_id[node_path[2]]["node_type"] in {"fact", "constraint"}
    )


def _seal_record(record: Mapping[str, Any]) -> JsonObject:
    sealed = _clone(record)
    sealed["fingerprint_sha256"] = _fingerprint(_without_fingerprint(sealed))
    return sealed


def validate_closure_report(report: Mapping[str, Any]) -> None:
    _require_exact_keys(
        report,
        {
            "active_evidence_ids",
            "fingerprint_sha256",
            "graph_fingerprint_sha256",
            "graph_id",
            "invalidated_evidence_ids",
            "schema_version",
            "status",
            "targets",
            "witness_ranking_policy",
        },
        label="closure",
    )
    if report["schema_version"] != CLOSURE_SCHEMA_VERSION:
        raise FactorizedLineageValidationError("closure schema mismatch")
    if report["status"] != "COMPUTED":
        raise FactorizedLineageValidationError("closure status mismatch")
    if report["witness_ranking_policy"] != WITNESS_RANKING_POLICY:
        raise FactorizedLineageValidationError(
            "closure witness ranking policy mismatch"
        )
    _require_string(report["graph_id"], label="closure.graph_id")
    if not _is_sha256(report["graph_fingerprint_sha256"]):
        raise FactorizedLineageValidationError("invalid closure graph fingerprint")
    active = _require_string_list(
        report["active_evidence_ids"], label="closure.active_evidence_ids"
    )
    invalidated = _require_string_list(
        report["invalidated_evidence_ids"],
        label="closure.invalidated_evidence_ids",
    )
    if active != sorted(active) or invalidated != sorted(invalidated):
        raise FactorizedLineageValidationError("closure evidence sets must be sorted")
    if set(active) & set(invalidated):
        raise FactorizedLineageValidationError("closure active and invalidated overlap")
    targets = report["targets"]
    if not isinstance(targets, list):
        raise FactorizedLineageValidationError("closure targets must be array")
    target_ids: set[str] = set()
    for index, target in enumerate(targets):
        if not isinstance(target, Mapping):
            raise FactorizedLineageValidationError(f"closure.targets[{index}]")
        _require_exact_keys(
            target,
            {
                "all_active_evidence_ids",
                "direct_active_evidence_ids",
                "inherited_active_evidence_ids",
                "slot",
                "target_id",
                "target_type",
                "value",
                "witness_paths",
            },
            label=f"closure.targets[{index}]",
        )
        target_id = _require_string(
            target["target_id"], label=f"closure.targets[{index}].target_id"
        )
        if target_id in target_ids:
            raise FactorizedLineageValidationError("duplicate closure target")
        target_ids.add(target_id)
        if target["target_type"] not in {"fact", "constraint"}:
            raise FactorizedLineageValidationError("invalid closure target type")
        _require_string(target["slot"], label=f"closure.targets[{index}].slot")
        _require_string(target["value"], label=f"closure.targets[{index}].value")
        direct = _require_string_list(
            target["direct_active_evidence_ids"],
            label=f"closure.targets[{index}].direct",
        )
        inherited = _require_string_list(
            target["inherited_active_evidence_ids"],
            label=f"closure.targets[{index}].inherited",
        )
        all_ids = _require_string_list(
            target["all_active_evidence_ids"],
            label=f"closure.targets[{index}].all",
        )
        if direct != sorted(direct) or inherited != sorted(inherited):
            raise FactorizedLineageValidationError("closure partitions must be sorted")
        if all_ids != sorted(all_ids):
            raise FactorizedLineageValidationError(
                "all closure evidence must be sorted"
            )
        if set(direct) & set(inherited) or set(all_ids) != set(direct) | set(inherited):
            raise FactorizedLineageValidationError("invalid direct/inherited partition")
        witnesses = target["witness_paths"]
        if not isinstance(witnesses, list) or len(witnesses) != len(all_ids):
            raise FactorizedLineageValidationError(
                "one witness is required per evidence"
            )
        observed_witness_ids: list[str] = []
        for witness_index, witness in enumerate(witnesses):
            if not isinstance(witness, Mapping):
                raise FactorizedLineageValidationError("witness must be object")
            _require_exact_keys(
                witness,
                {"classification", "edge_path", "evidence_id", "node_path"},
                label=f"witness[{witness_index}]",
            )
            evidence_id = _require_string(
                witness["evidence_id"], label="witness.evidence_id"
            )
            observed_witness_ids.append(evidence_id)
            classification = witness["classification"]
            if classification not in {"direct", "inherited"}:
                raise FactorizedLineageValidationError("invalid witness classification")
            if classification == "direct" and evidence_id not in direct:
                raise FactorizedLineageValidationError(
                    "direct witness partition mismatch"
                )
            if classification == "inherited" and evidence_id not in inherited:
                raise FactorizedLineageValidationError(
                    "inherited witness partition mismatch"
                )
            node_path = _require_string_list(
                witness["node_path"], label="witness.node_path"
            )
            edge_path = _require_string_list(
                witness["edge_path"], label="witness.edge_path"
            )
            if (
                not node_path
                or node_path[0] != f"evidence:{evidence_id}"
                or node_path[-1] != target_id
                or len(edge_path) + 1 != len(node_path)
            ):
                raise FactorizedLineageValidationError("malformed witness path")
        if observed_witness_ids != all_ids:
            raise FactorizedLineageValidationError(
                "witnesses must follow evidence order"
            )
    if [row["target_id"] for row in targets] != sorted(target_ids):
        raise FactorizedLineageValidationError("closure targets must be sorted")
    if not _is_sha256(report["fingerprint_sha256"]):
        raise FactorizedLineageValidationError("invalid closure fingerprint")
    if _fingerprint(_without_fingerprint(report)) != report["fingerprint_sha256"]:
        raise FactorizedLineageValidationError("closure fingerprint mismatch")


def _compute_closure_core(graph: Mapping[str, Any]) -> JsonObject:
    node_by_id = {node["node_id"]: node for node in graph["nodes"]}
    edge_by_id = {edge["edge_id"]: edge for edge in graph["edges"]}
    invalidated = _invalidated_evidence_ids(graph)
    active = sorted(
        node["evidence_id"]
        for node in graph["nodes"]
        if node["node_type"] == "evidence"
        and node["evidence_id"] not in set(invalidated)
    )
    adjacency: dict[str, list[tuple[str, str]]] = {
        node_id: [] for node_id in node_by_id
    }
    for edge in _propagation_edges(graph):
        adjacency[edge["source_node_id"]].append(
            (edge["target_node_id"], edge["edge_id"])
        )
    for node_id in adjacency:
        adjacency[node_id].sort(key=lambda pair: (pair[0], pair[1]))
    targets: list[JsonObject] = []
    for target in sorted(
        (
            node
            for node in graph["nodes"]
            if node["node_type"] in {"fact", "constraint"}
        ),
        key=lambda row: row["node_id"],
    ):
        direct_ids: list[str] = []
        inherited_ids: list[str] = []
        witnesses: list[JsonObject] = []
        for evidence_id in active:
            paths = _all_paths(f"evidence:{evidence_id}", target["node_id"], adjacency)
            if not paths:
                continue
            direct_paths = [
                path for path in paths if _is_direct_path(path[0], node_by_id)
            ]
            classification = "direct" if direct_paths else "inherited"
            candidates = direct_paths if direct_paths else paths
            node_path, edge_path = min(
                candidates,
                key=lambda path: (
                    sum(
                        edge_by_id[edge_id]["provenance"] == "repair_overlay"
                        for edge_id in path[1]
                    ),
                    len(path[1]),
                    path[0],
                    path[1],
                ),
            )
            if classification == "direct":
                direct_ids.append(evidence_id)
            else:
                inherited_ids.append(evidence_id)
            witnesses.append(
                {
                    "classification": classification,
                    "edge_path": list(edge_path),
                    "evidence_id": evidence_id,
                    "node_path": list(node_path),
                }
            )
        all_ids = sorted(direct_ids + inherited_ids)
        witnesses.sort(key=lambda row: row["evidence_id"])
        targets.append(
            {
                "all_active_evidence_ids": all_ids,
                "direct_active_evidence_ids": sorted(direct_ids),
                "inherited_active_evidence_ids": sorted(inherited_ids),
                "slot": target["slot"],
                "target_id": target["node_id"],
                "target_type": target["node_type"],
                "value": target["value"],
                "witness_paths": witnesses,
            }
        )
    report = _seal_record(
        {
            "active_evidence_ids": active,
            "graph_fingerprint_sha256": graph["fingerprint_sha256"],
            "graph_id": graph["graph_id"],
            "invalidated_evidence_ids": invalidated,
            "schema_version": CLOSURE_SCHEMA_VERSION,
            "status": "COMPUTED",
            "targets": targets,
            "witness_ranking_policy": WITNESS_RANKING_POLICY,
        }
    )
    validate_closure_report(report)
    return report


def compute_closure(graph: Mapping[str, Any]) -> JsonObject:
    """Compute exact active direct/inherited closure and deterministic witnesses."""

    validate_graph(graph)
    return _compute_closure_core(graph)


def validate_closure_gold(gold: Mapping[str, Any]) -> None:
    _require_exact_keys(
        gold,
        {
            "claim_boundary",
            "expected_active_evidence_ids",
            "expected_invalidated_evidence_ids",
            "fingerprint_sha256",
            "gold_id",
            "schema_version",
            "source_case_id",
            "status",
            "targets",
        },
        label="gold",
    )
    if gold["schema_version"] != GOLD_SCHEMA_VERSION:
        raise FactorizedLineageValidationError("gold schema mismatch")
    if gold["status"] != "LOCKED_POST_GRAPH_GRADING_ONLY":
        raise FactorizedLineageValidationError("gold status mismatch")
    for key in ("gold_id", "source_case_id"):
        _require_string(gold[key], label=f"gold.{key}")
    active = _require_string_list(
        gold["expected_active_evidence_ids"], label="gold.expected_active"
    )
    invalidated = _require_string_list(
        gold["expected_invalidated_evidence_ids"],
        label="gold.expected_invalidated",
    )
    if active != sorted(active) or invalidated != sorted(invalidated):
        raise FactorizedLineageValidationError("gold evidence sets must be sorted")
    _require_string_list(gold["claim_boundary"], label="gold.claim_boundary")
    targets = gold["targets"]
    if not isinstance(targets, list) or not targets:
        raise FactorizedLineageValidationError("gold targets must be nonempty")
    ids: list[str] = []
    for index, target in enumerate(targets):
        if not isinstance(target, Mapping):
            raise FactorizedLineageValidationError(f"gold.targets[{index}]")
        _require_exact_keys(
            target,
            {
                "all_active_evidence_ids",
                "direct_active_evidence_ids",
                "inherited_active_evidence_ids",
                "slot",
                "target_id",
                "target_type",
                "value",
            },
            label=f"gold.targets[{index}]",
        )
        target_id = _require_string(target["target_id"], label="gold.target_id")
        ids.append(target_id)
        if target["target_type"] not in {"fact", "constraint"}:
            raise FactorizedLineageValidationError("gold target type invalid")
        _require_string(target["slot"], label="gold.slot")
        _require_string(target["value"], label="gold.value")
        direct = _require_string_list(
            target["direct_active_evidence_ids"], label="gold.direct"
        )
        inherited = _require_string_list(
            target["inherited_active_evidence_ids"], label="gold.inherited"
        )
        all_ids = _require_string_list(
            target["all_active_evidence_ids"], label="gold.all"
        )
        if direct != sorted(direct) or inherited != sorted(inherited):
            raise FactorizedLineageValidationError("gold partitions must be sorted")
        if all_ids != sorted(all_ids) or set(all_ids) != set(direct) | set(inherited):
            raise FactorizedLineageValidationError("gold closure partition invalid")
        if set(direct) & set(inherited):
            raise FactorizedLineageValidationError("gold partitions overlap")
    if ids != sorted(ids) or len(ids) != len(set(ids)):
        raise FactorizedLineageValidationError("gold targets must be unique and sorted")
    if not _is_sha256(gold["fingerprint_sha256"]):
        raise FactorizedLineageValidationError("gold fingerprint invalid")
    if _fingerprint(_without_fingerprint(gold)) != gold["fingerprint_sha256"]:
        raise FactorizedLineageValidationError("gold fingerprint mismatch")


def _grade_fingerprint(grade: Mapping[str, Any]) -> str:
    return _fingerprint(_without_fingerprint(grade))


def validate_closure_grade(grade: Mapping[str, Any]) -> None:
    _require_exact_keys(
        grade,
        {
            "checks",
            "fingerprint_sha256",
            "gap_count",
            "gaps",
            "gold_fingerprint_sha256",
            "graph_fingerprint_sha256",
            "schema_version",
            "status",
            "target_results",
        },
        label="grade",
    )
    if grade["schema_version"] != GRADE_SCHEMA_VERSION:
        raise FactorizedLineageValidationError("grade schema mismatch")
    if grade["status"] not in {"PASS", "FAIL"}:
        raise FactorizedLineageValidationError("grade status invalid")
    for key in ("gold_fingerprint_sha256", "graph_fingerprint_sha256"):
        if not _is_sha256(grade[key]):
            raise FactorizedLineageValidationError(f"grade {key} invalid")
    checks = grade["checks"]
    if not isinstance(checks, Mapping):
        raise FactorizedLineageValidationError("grade checks must be object")
    _require_exact_keys(
        checks,
        {"active_exact", "invalidated_exact", "targets_exact"},
        label="grade.checks",
    )
    if not all(isinstance(value, bool) for value in checks.values()):
        raise FactorizedLineageValidationError("grade checks must be booleans")
    if isinstance(grade["gap_count"], bool) or not isinstance(grade["gap_count"], int):
        raise FactorizedLineageValidationError("grade gap_count invalid")
    if not isinstance(grade["gaps"], list) or not isinstance(
        grade["target_results"], list
    ):
        raise FactorizedLineageValidationError("grade arrays invalid")
    if grade["gap_count"] != len(grade["gaps"]):
        raise FactorizedLineageValidationError("grade gap count mismatch")
    passed = all(checks.values()) and all(
        all(result["checks"].values()) for result in grade["target_results"]
    )
    if (grade["status"] == "PASS") != passed:
        raise FactorizedLineageValidationError("grade status/check mismatch")
    if not _is_sha256(grade["fingerprint_sha256"]):
        raise FactorizedLineageValidationError("grade fingerprint invalid")
    if _grade_fingerprint(grade) != grade["fingerprint_sha256"]:
        raise FactorizedLineageValidationError("grade fingerprint mismatch")


def grade_closure(
    report: Mapping[str, Any], gold: Union[JsonPath, Mapping[str, Any]]
) -> JsonObject:
    """Grade closure with exact sets; extra support fails just like missing support."""

    validate_closure_report(report)
    loaded_gold = _load_mapping(gold, label="gold")
    validate_closure_gold(loaded_gold)
    observed_by_id = {row["target_id"]: row for row in report["targets"]}
    expected_by_id = {row["target_id"]: row for row in loaded_gold["targets"]}
    target_results: list[JsonObject] = []
    gaps: list[JsonObject] = []
    for target_id in sorted(set(observed_by_id) | set(expected_by_id)):
        observed = observed_by_id.get(target_id)
        expected = expected_by_id.get(target_id)
        metadata_exact = bool(
            observed is not None
            and expected is not None
            and (
                observed["target_type"],
                observed["slot"],
                observed["value"],
            )
            == (
                expected["target_type"],
                expected["slot"],
                expected["value"],
            )
        )
        observed_direct = set(
            observed["direct_active_evidence_ids"] if observed else []
        )
        observed_inherited = set(
            observed["inherited_active_evidence_ids"] if observed else []
        )
        observed_all = set(observed["all_active_evidence_ids"] if observed else [])
        expected_direct = set(
            expected["direct_active_evidence_ids"] if expected else []
        )
        expected_inherited = set(
            expected["inherited_active_evidence_ids"] if expected else []
        )
        expected_all = set(expected["all_active_evidence_ids"] if expected else [])
        missing_all = sorted(expected_all - observed_all)
        unexpected_all = sorted(observed_all - expected_all)
        for evidence_id in missing_all:
            gaps.append(
                {
                    "evidence_id": evidence_id,
                    "gap_kind": "missing_active_closure",
                    "target_id": target_id,
                }
            )
        for evidence_id in unexpected_all:
            gaps.append(
                {
                    "evidence_id": evidence_id,
                    "gap_kind": "unexpected_active_closure",
                    "target_id": target_id,
                }
            )
        target_results.append(
            {
                "checks": {
                    "all_exact": observed_all == expected_all,
                    "direct_exact": observed_direct == expected_direct,
                    "inherited_exact": observed_inherited == expected_inherited,
                    "metadata_exact": metadata_exact,
                },
                "missing_active_evidence_ids": missing_all,
                "target_id": target_id,
                "unexpected_active_evidence_ids": unexpected_all,
            }
        )
    checks = {
        "active_exact": report["active_evidence_ids"]
        == loaded_gold["expected_active_evidence_ids"],
        "invalidated_exact": report["invalidated_evidence_ids"]
        == loaded_gold["expected_invalidated_evidence_ids"],
        "targets_exact": set(observed_by_id) == set(expected_by_id),
    }
    passed = all(checks.values()) and all(
        all(result["checks"].values()) for result in target_results
    )
    grade = _seal_record(
        {
            "checks": checks,
            "gap_count": len(gaps),
            "gaps": sorted(
                gaps, key=lambda row: (row["target_id"], row["evidence_id"])
            ),
            "gold_fingerprint_sha256": loaded_gold["fingerprint_sha256"],
            "graph_fingerprint_sha256": report["graph_fingerprint_sha256"],
            "schema_version": GRADE_SCHEMA_VERSION,
            "status": "PASS" if passed else "FAIL",
            "target_results": target_results,
        }
    )
    validate_closure_grade(grade)
    return grade


def diagnose_repair_edge_ablation(
    observed_graph: Mapping[str, Any],
    overlay: Union[JsonPath, Mapping[str, Any]],
    gold: Union[JsonPath, Mapping[str, Any]],
) -> JsonObject:
    """Prove each preregistered repair edge closes its corresponding gap."""

    validate_graph(observed_graph)
    loaded_overlay = _load_mapping(overlay, label="overlay")
    repaired = apply_repair_overlay(observed_graph, loaded_overlay)
    loaded_gold = _load_mapping(gold, label="gold")
    validate_closure_gold(loaded_gold)
    expected_gap_by_removed_edge = {
        "repair:demo_readiness->final_priority": (
            "fact:final_priority",
            "R4",
        ),
        "repair:final_priority->demo_centerpiece": (
            "fact:demo_centerpiece",
            "R2",
        ),
    }
    cases: list[JsonObject] = []
    for removed_edge in sorted(loaded_overlay["edges"], key=lambda row: row["edge_id"]):
        ablated = _clone(repaired)
        ablated["edges"] = [
            edge
            for edge in ablated["edges"]
            if edge["edge_id"] != removed_edge["edge_id"]
        ]
        ablated["graph_id"] = (
            f"{repaired['graph_id']}:without:{removed_edge['edge_id']}"
        )
        ablated["fingerprint_sha256"] = graph_fingerprint(ablated)
        node_by_id = {node["node_id"]: node for node in ablated["nodes"]}
        for index, edge in enumerate(ablated["edges"]):
            _validate_edge(
                edge,
                node_by_id=node_by_id,
                label=f"ablation.edges[{index}]",
            )
        _assert_acyclic(node_by_id, ablated["edges"])
        _validate_source_consistency(ablated, node_by_id, ablated["edges"])
        closure = _compute_closure_core(ablated)
        grade = grade_closure(closure, loaded_gold)
        expected_target_id, expected_evidence_id = expected_gap_by_removed_edge[
            removed_edge["edge_id"]
        ]
        observed_gaps = {
            (row["target_id"], row["evidence_id"]) for row in grade["gaps"]
        }
        expected_gaps = {(expected_target_id, expected_evidence_id)}
        if grade["status"] != "FAIL" or observed_gaps != expected_gaps:
            raise FactorizedLineageValidationError(
                f"repair-edge ablation did not reopen exact gap: {removed_edge['edge_id']}"
            )
        cases.append(
            {
                "closure_fingerprint_sha256": closure["fingerprint_sha256"],
                "expected_reopened_evidence_id": expected_evidence_id,
                "expected_reopened_target_id": expected_target_id,
                "grade_fingerprint_sha256": grade["fingerprint_sha256"],
                "grade_status": grade["status"],
                "removed_edge_id": removed_edge["edge_id"],
            }
        )
    report = _seal_record(
        {
            "cases": cases,
            "claim_boundary": [
                "Ablations are local diagnostics over the contaminated repair overlay, not independent evaluation cases."
            ],
            "repaired_graph_fingerprint_sha256": repaired["fingerprint_sha256"],
            "schema_version": ABLATION_SCHEMA_VERSION,
            "status": "PASS",
        }
    )
    validate_repair_edge_ablation(report)
    return report


def validate_repair_edge_ablation(report: Mapping[str, Any]) -> None:
    _require_exact_keys(
        report,
        {
            "cases",
            "claim_boundary",
            "fingerprint_sha256",
            "repaired_graph_fingerprint_sha256",
            "schema_version",
            "status",
        },
        label="ablation",
    )
    if (
        report["schema_version"] != ABLATION_SCHEMA_VERSION
        or report["status"] != "PASS"
    ):
        raise FactorizedLineageValidationError("ablation schema/status mismatch")
    if not _is_sha256(report["repaired_graph_fingerprint_sha256"]):
        raise FactorizedLineageValidationError(
            "ablation repaired graph fingerprint invalid"
        )
    _require_string_list(report["claim_boundary"], label="ablation.claim_boundary")
    cases = report["cases"]
    if not isinstance(cases, list) or len(cases) != 2:
        raise FactorizedLineageValidationError("ablation requires two exact cases")
    expected = {
        "repair:demo_readiness->final_priority": (
            "fact:final_priority",
            "R4",
        ),
        "repair:final_priority->demo_centerpiece": (
            "fact:demo_centerpiece",
            "R2",
        ),
    }
    observed_ids: list[str] = []
    for index, case in enumerate(cases):
        if not isinstance(case, Mapping):
            raise FactorizedLineageValidationError(f"ablation.cases[{index}]")
        _require_exact_keys(
            case,
            {
                "closure_fingerprint_sha256",
                "expected_reopened_evidence_id",
                "expected_reopened_target_id",
                "grade_fingerprint_sha256",
                "grade_status",
                "removed_edge_id",
            },
            label=f"ablation.cases[{index}]",
        )
        edge_id = _require_string(case["removed_edge_id"], label="removed_edge_id")
        observed_ids.append(edge_id)
        if edge_id not in expected:
            raise FactorizedLineageValidationError("unexpected ablated repair edge")
        if (
            case["expected_reopened_target_id"],
            case["expected_reopened_evidence_id"],
        ) != expected[edge_id]:
            raise FactorizedLineageValidationError("ablation reopened-gap mismatch")
        if case["grade_status"] != "FAIL":
            raise FactorizedLineageValidationError("ablation must reopen a failure")
        for key in ("closure_fingerprint_sha256", "grade_fingerprint_sha256"):
            if not _is_sha256(case[key]):
                raise FactorizedLineageValidationError("ablation fingerprint invalid")
    if observed_ids != sorted(expected):
        raise FactorizedLineageValidationError("ablation cases must be canonical")
    if not _is_sha256(report["fingerprint_sha256"]):
        raise FactorizedLineageValidationError("ablation fingerprint invalid")
    if _fingerprint(_without_fingerprint(report)) != report["fingerprint_sha256"]:
        raise FactorizedLineageValidationError("ablation fingerprint mismatch")


def _load_gold_after_graph_seal(
    gold_path: JsonPath,
    observed_graph: Mapping[str, Any],
    repaired_graph: Mapping[str, Any],
) -> JsonObject:
    validate_graph(observed_graph)
    validate_graph(repaired_graph)
    if observed_graph["status"] != "LOSSLESS_MIGRATION":
        raise FactorizedLineageValidationError(
            "closure gold requires a sealed lossless observed graph"
        )
    if repaired_graph["status"] != "CONTAMINATED_REPAIR_OVERLAY":
        raise FactorizedLineageValidationError(
            "closure gold requires a sealed repaired graph"
        )
    if (
        repaired_graph["derivation"]["parent_graph_fingerprint_sha256"]
        != observed_graph["fingerprint_sha256"]
    ):
        raise FactorizedLineageValidationError(
            "closure gold requires repaired-to-observed parent linkage"
        )
    gold = _load_json(gold_path)
    validate_closure_gold(gold)
    return gold


def _regression_fingerprint(bundle: Mapping[str, Any]) -> str:
    return _fingerprint(_without_fingerprint(bundle))


def validate_regression(bundle: Mapping[str, Any]) -> None:
    _require_exact_keys(
        bundle,
        {
            "claim_boundary",
            "fingerprint_sha256",
            "gates",
            "gold_boundary",
            "legacy_endpoint",
            "observed",
            "repair_edge_ablation",
            "repaired",
            "schema_version",
            "status",
        },
        label="regression",
    )
    if bundle["schema_version"] != REGRESSION_SCHEMA_VERSION:
        raise FactorizedLineageValidationError("regression schema mismatch")
    if bundle["status"] != "PASS":
        raise FactorizedLineageValidationError("regression endpoint did not pass")
    for lane in ("observed", "repaired"):
        payload = bundle[lane]
        if not isinstance(payload, Mapping):
            raise FactorizedLineageValidationError(f"regression {lane} invalid")
        _require_exact_keys(payload, {"closure", "grade", "graph"}, label=lane)
        validate_graph(payload["graph"])
        validate_closure_report(payload["closure"])
        validate_closure_grade(payload["grade"])
        if (
            payload["closure"]["graph_fingerprint_sha256"]
            != payload["graph"]["fingerprint_sha256"]
        ):
            raise FactorizedLineageValidationError(f"{lane} closure graph mismatch")
        if (
            payload["grade"]["graph_fingerprint_sha256"]
            != payload["graph"]["fingerprint_sha256"]
        ):
            raise FactorizedLineageValidationError(f"{lane} grade graph mismatch")
        recomputed_closure = compute_closure(payload["graph"])
        if _canonical_json_bytes(recomputed_closure) != _canonical_json_bytes(
            payload["closure"]
        ):
            raise FactorizedLineageValidationError(
                f"{lane} embedded closure is not the canonical graph-bound closure"
            )
    legacy = bundle["legacy_endpoint"]
    if legacy != {
        "preserved_byte_frozen_result": True,
        "walkthrough_contract_passed": False,
    }:
        raise FactorizedLineageValidationError("legacy endpoint was rewritten")
    gold_boundary = bundle["gold_boundary"]
    if gold_boundary != {
        "loaded_after_both_graph_fingerprints": True,
        "participated_in_migration_or_overlay": False,
    }:
        raise FactorizedLineageValidationError("gold boundary mismatch")
    gates = bundle["gates"]
    expected_gates = {
        "active_invalidation_exact": True,
        "each_repair_edge_ablation_reopens_exact_gap": True,
        "existing_lineage_witnesses_prefer_nonrepair": True,
        "legacy_two_gap_reproduced": True,
        "lossless_observed_grade_remains_fail": True,
        "overlay_delta_exact": True,
        "repaired_exact_closure_pass": True,
        "stable_constraint_preserved": True,
        "two_edge_overlay_exact": True,
    }
    if gates != expected_gates:
        raise FactorizedLineageValidationError("regression gates changed")
    validate_repair_edge_ablation(bundle["repair_edge_ablation"])
    if (
        bundle["repair_edge_ablation"]["repaired_graph_fingerprint_sha256"]
        != bundle["repaired"]["graph"]["fingerprint_sha256"]
    ):
        raise FactorizedLineageValidationError("ablation/repaired graph mismatch")
    if bundle["observed"]["grade"]["status"] != "FAIL":
        raise FactorizedLineageValidationError("observed failure must remain visible")
    if bundle["observed"]["grade"]["gap_count"] != 2:
        raise FactorizedLineageValidationError("observed regression must have two gaps")
    if bundle["repaired"]["grade"]["status"] != "PASS":
        raise FactorizedLineageValidationError("repaired closure must pass")
    _require_string_list(bundle["claim_boundary"], label="regression.claim_boundary")
    if not _is_sha256(bundle["fingerprint_sha256"]):
        raise FactorizedLineageValidationError("regression fingerprint invalid")
    if _regression_fingerprint(bundle) != bundle["fingerprint_sha256"]:
        raise FactorizedLineageValidationError("regression fingerprint mismatch")


def build_regression(
    source_artifact_dir: JsonPath = DEFAULT_SOURCE_ARTIFACT_DIR,
    fixture_path: JsonPath = DEFAULT_FIXTURE_PATH,
    overlay_path: JsonPath = DEFAULT_OVERLAY_PATH,
    gold_path: JsonPath = DEFAULT_GOLD_PATH,
) -> JsonObject:
    """Build the sealed local v0.5.3 regression bundle with delayed gold load."""

    observed_graph = load_and_migrate(source_artifact_dir, fixture_path)
    observed_closure = compute_closure(observed_graph)
    repaired_graph = apply_repair_overlay(observed_graph, overlay_path)
    repaired_closure = compute_closure(repaired_graph)
    gold = _load_gold_after_graph_seal(
        gold_path,
        observed_graph,
        repaired_graph,
    )
    observed_grade = grade_closure(observed_closure, gold)
    repaired_grade = grade_closure(repaired_closure, gold)
    observed_gaps = {
        (row["target_id"], row["evidence_id"]) for row in observed_grade["gaps"]
    }
    expected_gaps = {
        ("fact:demo_centerpiece", "R2"),
        ("fact:final_priority", "R4"),
    }
    repaired_by_id = {row["target_id"]: row for row in repaired_closure["targets"]}
    observed_by_id = {row["target_id"]: row for row in observed_closure["targets"]}
    overlay_delta = {
        (target_id, evidence_id)
        for target_id, repaired_target in repaired_by_id.items()
        for evidence_id in (
            set(repaired_target["all_active_evidence_ids"])
            - set(observed_by_id[target_id]["all_active_evidence_ids"])
        )
    }
    overlay_removed = {
        (target_id, evidence_id)
        for target_id, observed_target in observed_by_id.items()
        for evidence_id in (
            set(observed_target["all_active_evidence_ids"])
            - set(repaired_by_id[target_id]["all_active_evidence_ids"])
        )
    }
    repaired_edge_by_id = {edge["edge_id"]: edge for edge in repaired_graph["edges"]}
    existing_witnesses_prefer_nonrepair = True
    for target_id, observed_target in observed_by_id.items():
        repaired_witness_by_evidence = {
            row["evidence_id"]: row
            for row in repaired_by_id[target_id]["witness_paths"]
        }
        for evidence_id in observed_target["all_active_evidence_ids"]:
            witness = repaired_witness_by_evidence[evidence_id]
            if any(
                repaired_edge_by_id[edge_id]["provenance"] == "repair_overlay"
                for edge_id in witness["edge_path"]
            ):
                existing_witnesses_prefer_nonrepair = False
    ablation = diagnose_repair_edge_ablation(
        observed_graph,
        overlay_path,
        gold,
    )
    gates = {
        "active_invalidation_exact": repaired_closure["invalidated_evidence_ids"]
        == ["R3"],
        "each_repair_edge_ablation_reopens_exact_gap": ablation["status"] == "PASS",
        "existing_lineage_witnesses_prefer_nonrepair": (
            existing_witnesses_prefer_nonrepair
        ),
        "legacy_two_gap_reproduced": observed_gaps == expected_gaps,
        "lossless_observed_grade_remains_fail": observed_grade["status"] == "FAIL",
        "overlay_delta_exact": overlay_delta
        == {
            ("fact:demo_centerpiece", "R2"),
            ("fact:final_priority", "R4"),
        }
        and not overlay_removed,
        "repaired_exact_closure_pass": repaired_grade["status"] == "PASS",
        "stable_constraint_preserved": repaired_by_id["constraint:video_constraint"][
            "all_active_evidence_ids"
        ]
        == ["R5"],
        "two_edge_overlay_exact": len(
            [
                edge
                for edge in repaired_graph["edges"]
                if edge["provenance"] == "repair_overlay"
            ]
        )
        == 2,
    }
    if not all(gates.values()):
        raise FactorizedLineageValidationError(f"regression gates failed: {gates}")
    bundle = _seal_record(
        {
            "claim_boundary": [
                "This network-zero regression reuses a known v0.5.2 failure and is contaminated engineering evidence.",
                "The observed graph remains FAIL; the repair is graded as a separate derived artifact.",
                "A local exact closure PASS does not establish hosted-output quality, causal superiority, or general reasoning improvement.",
            ],
            "gates": gates,
            "gold_boundary": {
                "loaded_after_both_graph_fingerprints": True,
                "participated_in_migration_or_overlay": False,
            },
            "legacy_endpoint": {
                "preserved_byte_frozen_result": True,
                "walkthrough_contract_passed": False,
            },
            "observed": {
                "closure": observed_closure,
                "grade": observed_grade,
                "graph": observed_graph,
            },
            "repair_edge_ablation": ablation,
            "repaired": {
                "closure": repaired_closure,
                "grade": repaired_grade,
                "graph": repaired_graph,
            },
            "schema_version": REGRESSION_SCHEMA_VERSION,
            "status": "PASS",
        }
    )
    validate_regression(bundle)
    return bundle


def _expect_rejected(name: str, operation: Any) -> None:
    try:
        operation()
    except (FactorizedLineageValidationError, ValueError, TypeError):
        return
    raise AssertionError(f"mutation was not rejected: {name}")


def _reseal_graph_without_validation(graph: Mapping[str, Any]) -> JsonObject:
    mutated = _clone(graph)
    mutated["fingerprint_sha256"] = graph_fingerprint(mutated)
    return mutated


def _reseal_closure_without_validation(report: Mapping[str, Any]) -> JsonObject:
    mutated = _clone(report)
    mutated["fingerprint_sha256"] = _fingerprint(_without_fingerprint(mutated))
    return mutated


def self_test() -> JsonObject:
    """Run deterministic positive, boundary, and adversarial network-zero tests."""

    observed = load_and_migrate()
    observed_closure = compute_closure(observed)
    overlay = _load_json(DEFAULT_OVERLAY_PATH)
    repaired = apply_repair_overlay(observed, overlay)
    repaired_closure = compute_closure(repaired)
    gold = _load_json(DEFAULT_GOLD_PATH)
    observed_grade = grade_closure(observed_closure, gold)
    repaired_grade = grade_closure(repaired_closure, gold)
    assert observed_grade["status"] == "FAIL"
    assert observed_grade["gap_count"] == 2
    assert {
        (row["target_id"], row["evidence_id"]) for row in observed_grade["gaps"]
    } == {
        ("fact:demo_centerpiece", "R2"),
        ("fact:final_priority", "R4"),
    }
    assert repaired_grade["status"] == "PASS"
    assert repaired_closure["invalidated_evidence_ids"] == ["R3"]
    repaired_targets = {row["target_id"]: row for row in repaired_closure["targets"]}
    assert repaired_targets["constraint:video_constraint"][
        "all_active_evidence_ids"
    ] == ["R5"]
    repaired_edge_by_id = {edge["edge_id"]: edge for edge in repaired["edges"]}

    def repair_edge_count(target_id: str, evidence_id: str) -> int:
        witness = next(
            row
            for row in repaired_targets[target_id]["witness_paths"]
            if row["evidence_id"] == evidence_id
        )
        return sum(
            repaired_edge_by_id[edge_id]["provenance"] == "repair_overlay"
            for edge_id in witness["edge_path"]
        )

    assert repair_edge_count("fact:final_priority", "R6") == 0
    assert repair_edge_count("fact:final_priority", "R4") == 1
    assert repair_edge_count("fact:demo_centerpiece", "R2") == 1
    ablation = diagnose_repair_edge_ablation(observed, overlay, gold)
    assert ablation["status"] == "PASS" and len(ablation["cases"]) == 2

    reordered = _clone(repaired)
    reordered["nodes"].reverse()
    reordered["edges"].reverse()
    validate_graph(reordered)
    assert compute_closure(reordered) == repaired_closure

    cycle = _clone(repaired)
    cycle["edges"].append(
        {
            "edge_id": "tamper:cycle",
            "edge_type": "depends_on",
            "provenance": "repair_overlay",
            "source_node_id": "fact:demo_centerpiece",
            "target_node_id": "fact:final_priority",
        }
    )
    cycle = _reseal_graph_without_validation(cycle)
    _expect_rejected("cycle", lambda: validate_graph(cycle))

    dangling = _clone(observed)
    dangling["edges"][0]["target_node_id"] = "support:missing"
    dangling = _reseal_graph_without_validation(dangling)
    _expect_rejected("dangling", lambda: validate_graph(dangling))

    wrong_type = _clone(observed)
    wrong_type["nodes"][0]["node_type"] = "Entity"
    wrong_type = _reseal_graph_without_validation(wrong_type)
    _expect_rejected("node type", lambda: validate_graph(wrong_type))

    wrong_direction = _clone(observed)
    invalidation = next(
        edge for edge in wrong_direction["edges"] if edge["edge_type"] == "invalidates"
    )
    invalidation["source_node_id"], invalidation["target_node_id"] = (
        invalidation["target_node_id"],
        invalidation["source_node_id"],
    )
    wrong_direction = _reseal_graph_without_validation(wrong_direction)
    _expect_rejected("invalidation direction", lambda: validate_graph(wrong_direction))

    missing_edge = _clone(observed)
    missing_edge["edges"] = [
        edge
        for edge in missing_edge["edges"]
        if edge["edge_id"]
        != "migration_inferred:support:judging_basis->fact:final_priority"
    ]
    missing_edge = _reseal_graph_without_validation(missing_edge)
    _expect_rejected("missing structural edge", lambda: validate_graph(missing_edge))

    shortcut = _clone(observed)
    shortcut["edges"].append(
        {
            "edge_id": "tamper:shortcut",
            "edge_type": "supports",
            "provenance": "observed",
            "source_node_id": "evidence:R2",
            "target_node_id": "fact:demo_centerpiece",
        }
    )
    shortcut = _reseal_graph_without_validation(shortcut)
    _expect_rejected("Evidence to Fact shortcut", lambda: validate_graph(shortcut))

    hidden_r6 = _clone(observed)
    hidden_r6["nodes"] = [
        node for node in hidden_r6["nodes"] if node["node_id"] != "evidence:R6"
    ]
    hidden_r6["edges"] = [
        edge
        for edge in hidden_r6["edges"]
        if "evidence:R6" not in {edge["source_node_id"], edge["target_node_id"]}
    ]
    hidden_r6 = _reseal_graph_without_validation(hidden_r6)
    _expect_rejected("hidden R6", lambda: validate_graph(hidden_r6))

    forbidden_key = _clone(observed)
    forbidden_key["nodes"][0]["expected_evidence_ids"] = ["R2"]
    forbidden_key = _reseal_graph_without_validation(forbidden_key)
    _expect_rejected("forbidden key", lambda: validate_graph(forbidden_key))

    nonfinite = _clone(observed)
    nonfinite["nodes"][0]["temporal_ordinal"] = float("nan")
    _expect_rejected("NaN", lambda: validate_graph(nonfinite))

    duplicate_edge = _clone(observed)
    duplicate_edge["edges"].append(_clone(duplicate_edge["edges"][0]))
    duplicate_edge = _reseal_graph_without_validation(duplicate_edge)
    _expect_rejected("duplicate edge", lambda: validate_graph(duplicate_edge))
    _expect_rejected(
        "duplicate JSON key",
        lambda: _loads_json_strict('{"x":1,"x":2}', label="duplicate-test"),
    )

    overclosed = _clone(repaired_closure)
    target = next(
        row
        for row in overclosed["targets"]
        if row["target_id"] == "fact:final_priority"
    )
    target["direct_active_evidence_ids"].insert(0, "R1")
    target["all_active_evidence_ids"].insert(0, "R1")
    target["witness_paths"].insert(
        0,
        {
            "classification": "direct",
            "edge_path": ["synthetic:a", "synthetic:b"],
            "evidence_id": "R1",
            "node_path": [
                "evidence:R1",
                "support:judging_basis",
                "fact:final_priority",
            ],
        },
    )
    overclosed = _reseal_closure_without_validation(overclosed)
    validate_closure_report(overclosed)
    assert grade_closure(overclosed, gold)["status"] == "FAIL"

    missing_overlay_edge = _clone(overlay)
    missing_overlay_edge["edges"].pop()
    missing_overlay_edge["fingerprint_sha256"] = _overlay_fingerprint(
        missing_overlay_edge
    )
    _expect_rejected(
        "missing overlay edge", lambda: validate_repair_overlay(missing_overlay_edge)
    )

    with tempfile.TemporaryDirectory() as temporary_directory:
        absent_gold = Path(temporary_directory) / "does-not-exist.json"
        assert (
            load_and_migrate(DEFAULT_SOURCE_ARTIFACT_DIR, DEFAULT_FIXTURE_PATH)[
                "status"
            ]
            == "LOSSLESS_MIGRATION"
        )
        assert not absent_gold.exists()

    fake_unsealed = _clone(observed)
    fake_unsealed["fingerprint_sha256"] = "0" * 64
    _expect_rejected(
        "gold before sealed graph",
        lambda: _load_gold_after_graph_seal(
            DEFAULT_GOLD_PATH,
            fake_unsealed,
            repaired,
        ),
    )
    wrong_parent = _clone(repaired)
    wrong_parent["derivation"]["parent_graph_fingerprint_sha256"] = "0" * 64
    wrong_parent = _reseal_graph_without_validation(wrong_parent)
    validate_graph(wrong_parent)
    _expect_rejected(
        "gold with mismatched graph lineage",
        lambda: _load_gold_after_graph_seal(
            DEFAULT_GOLD_PATH,
            observed,
            wrong_parent,
        ),
    )

    def deny_network(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("network access attempted during v0.5.3 self-test")

    with (
        mock.patch.object(socket, "socket", side_effect=deny_network),
        mock.patch.object(socket, "create_connection", side_effect=deny_network),
        mock.patch.object(socket, "getaddrinfo", side_effect=deny_network),
    ):
        bundle = build_regression()
    assert bundle["status"] == "PASS"
    fabricated_witness = _clone(bundle)
    fabricated_target = next(
        row
        for row in fabricated_witness["repaired"]["closure"]["targets"]
        if row["target_id"] == "fact:final_priority"
    )
    fabricated_target["witness_paths"][0]["edge_path"][0] = "fabricated:edge"
    fabricated_witness["repaired"]["closure"] = _reseal_closure_without_validation(
        fabricated_witness["repaired"]["closure"]
    )
    fabricated_witness["fingerprint_sha256"] = _regression_fingerprint(
        fabricated_witness
    )
    _expect_rejected(
        "fabricated graph-unbound witness",
        lambda: validate_regression(fabricated_witness),
    )
    return {
        "checks": {
            "cycle_dangling_type_direction_rejected": True,
            "duplicate_and_nonfinite_rejected": True,
            "each_repair_edge_ablation_reopens_exact_gap": True,
            "exact_set_overclosure_rejected": True,
            "fabricated_witness_rejected": True,
            "forbidden_shortcut_and_hidden_r6_rejected": True,
            "gold_delayed_until_graph_seal": True,
            "legacy_two_gap_reproduced": True,
            "order_deterministic": True,
            "r3_invalidated_r5_preserved": True,
            "repaired_closure_pass": True,
            "socket_denied_execution_passed": True,
            "witness_ranking_prefers_nonrepair": True,
        },
        "observed_graph_fingerprint_sha256": observed["fingerprint_sha256"],
        "repaired_graph_fingerprint_sha256": repaired["fingerprint_sha256"],
        "schema_version": "ebrt-factorized-lineage-self-test-v0.5.3",
        "status": "PASS",
    }


def _write_or_print(payload: Mapping[str, Any], output: Optional[str]) -> None:
    rendered = _pretty_json(payload)
    if output is None:
        print(rendered, end="")
        return
    path = Path(output)
    path.write_text(rendered, encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("self-test", help="run local adversarial self-tests")
    for command in ("demo", "validate"):
        child = subparsers.add_parser(command)
        child.add_argument(
            "--source-artifact-dir", default=str(DEFAULT_SOURCE_ARTIFACT_DIR)
        )
        child.add_argument("--fixture", default=str(DEFAULT_FIXTURE_PATH))
        child.add_argument("--overlay", default=str(DEFAULT_OVERLAY_PATH))
        child.add_argument("--gold", default=str(DEFAULT_GOLD_PATH))
        child.add_argument("--output")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "self-test":
        print(_pretty_json(self_test()), end="")
        return 0
    bundle = build_regression(
        args.source_artifact_dir,
        args.fixture,
        args.overlay,
        args.gold,
    )
    if args.command == "validate":
        validate_regression(bundle)
        payload: Mapping[str, Any] = {
            "fingerprint_sha256": bundle["fingerprint_sha256"],
            "observed_grade": bundle["observed"]["grade"]["status"],
            "repaired_grade": bundle["repaired"]["grade"]["status"],
            "schema_version": REGRESSION_SCHEMA_VERSION,
            "status": "VALID",
        }
    else:
        payload = bundle
    _write_or_print(payload, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
