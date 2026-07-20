#!/usr/bin/env python3
"""Strict public-lineage output and grader core for the v0.6 hosted block.

This module is intentionally provider-free.  A hosted provider returns only a
small typed public program.  This module validates that program against the
already-visible request payload, derives direct/inherited/total evidence
closure locally, and grades it only when an explicit post-call gold object is
supplied by the caller.

No model-declared closure is accepted.  No gold file is read at import time or
by ``validate_and_compile_output``.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections import deque
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError


ROOT = Path(__file__).resolve().parent
DEFAULT_GOLD_PATH = ROOT / "fixtures" / "hosted_bundle_lineage_gold_v0_6.json"
OUTPUT_SCHEMA_VERSION = "ebrt-public-lineage-output-v0.6"
COMPILED_SCHEMA_VERSION = "ebrt-public-lineage-closure-v0.6"
GRADE_SCHEMA_VERSION = "ebrt-public-lineage-grade-v0.6"

ALLOWED_SUPPORT_IDS = frozenset(
    {
        "support:judging_basis",
        "support:legacy_guidance",
        "support:demo_readiness",
        "support:superseding_guidance",
        "support:video_constraint",
    }
)


class HostedBundleLineageError(ValueError):
    """A provider-visible public lineage contract was invalid."""

    def __init__(self, reason_code: str, detail: str = "") -> None:
        self.reason_code = reason_code
        super().__init__(reason_code if not detail else f"{reason_code}: {detail}")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


SupportId = Literal[
    "support:judging_basis",
    "support:legacy_guidance",
    "support:demo_readiness",
    "support:superseding_guidance",
    "support:video_constraint",
]
TargetId = Literal[
    "fact:final_priority",
    "fact:demo_centerpiece",
    "constraint:video_constraint",
]
SlotId = Literal["final_priority", "demo_centerpiece", "video_constraint"]
TargetValue = Literal[
    "ADDITIONAL_UI_POLISH",
    "END_TO_END_PROOF",
    "POLISHED_SCREENS",
    "LIVE_REASONING_DIFF",
    "THREE_MINUTE_NARRATED",
]


class SupportNodeOutput(_StrictModel):
    support_id: SupportId
    evidence_ids: list[str] = Field(min_length=1, max_length=6)


class TargetOutput(_StrictModel):
    target_id: TargetId
    target_type: Literal["fact", "constraint"]
    slot: SlotId
    value: TargetValue
    direct_support_ids: list[SupportId] = Field(min_length=1, max_length=5)
    depends_on_target_ids: list[TargetId] = Field(max_length=2)


class InvalidationOutput(_StrictModel):
    source_evidence_id: str = Field(min_length=1, max_length=32)
    target_evidence_id: str = Field(min_length=1, max_length=32)


class ProviderLineageOutput(_StrictModel):
    """The complete provider structured-output surface.

    Direct, inherited, and total closure are deliberately absent.  They are
    computed locally from support nodes and typed target dependencies.
    """

    schema_version: Literal[OUTPUT_SCHEMA_VERSION]
    checkpoint_id: str = Field(min_length=1, max_length=160)
    current_answer: Literal["POLISH", "PROVE"]
    claim: str = Field(min_length=1, max_length=512)
    support_nodes: list[SupportNodeOutput] = Field(min_length=1, max_length=5)
    targets: list[TargetOutput] = Field(min_length=3, max_length=3)
    invalidations: list[InvalidationOutput] = Field(max_length=3)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _unique(values: Sequence[str], *, reason: str, label: str) -> tuple[str, ...]:
    normalized = tuple(str(value) for value in values)
    if len(normalized) != len(set(normalized)):
        raise HostedBundleLineageError(reason, f"duplicate value in {label}")
    return normalized


def _payload_contract(provider_payload: Mapping[str, Any]) -> dict[str, Any]:
    checkpoint_id = provider_payload.get("checkpoint_id")
    if not isinstance(checkpoint_id, str) or not checkpoint_id:
        raise HostedBundleLineageError("PAYLOAD_CHECKPOINT_INVALID")

    answer_choices = provider_payload.get("answer_choices")
    if not isinstance(answer_choices, list) or not answer_choices:
        raise HostedBundleLineageError("PAYLOAD_ANSWER_CHOICES_INVALID")
    answers = _unique(
        answer_choices,
        reason="PAYLOAD_ANSWER_CHOICES_INVALID",
        label="answer_choices",
    )

    raw_evidence = provider_payload.get("all_raw_evidence")
    if not isinstance(raw_evidence, list) or not raw_evidence:
        raise HostedBundleLineageError("PAYLOAD_EVIDENCE_HORIZON_INVALID")
    evidence_ids: list[str] = []
    for row in raw_evidence:
        if not isinstance(row, Mapping) or not isinstance(row.get("evidence_id"), str):
            raise HostedBundleLineageError("PAYLOAD_EVIDENCE_HORIZON_INVALID")
        evidence_ids.append(row["evidence_id"])
    horizon = _unique(
        evidence_ids,
        reason="PAYLOAD_EVIDENCE_HORIZON_INVALID",
        label="all_raw_evidence",
    )
    allowed = provider_payload.get("allowed_evidence_ids", list(horizon))
    if not isinstance(allowed, list) or tuple(allowed) != horizon:
        raise HostedBundleLineageError(
            "PAYLOAD_EVIDENCE_HORIZON_INVALID",
            "allowed_evidence_ids must exactly match ordered raw evidence",
        )

    slots_value = provider_payload.get("decision_slots")
    if not isinstance(slots_value, list) or not slots_value:
        raise HostedBundleLineageError("PAYLOAD_DECISION_SLOTS_INVALID")
    slots: dict[str, tuple[str, ...]] = {}
    for row in slots_value:
        if not isinstance(row, Mapping):
            raise HostedBundleLineageError("PAYLOAD_DECISION_SLOTS_INVALID")
        slot_id = row.get("slot_id")
        values = row.get("allowed_values")
        if (
            not isinstance(slot_id, str)
            or not slot_id
            or slot_id in slots
            or not isinstance(values, list)
            or not values
        ):
            raise HostedBundleLineageError("PAYLOAD_DECISION_SLOTS_INVALID")
        slots[slot_id] = _unique(
            values,
            reason="PAYLOAD_DECISION_SLOTS_INVALID",
            label=f"decision_slots.{slot_id}",
        )
    return {
        "checkpoint_id": checkpoint_id,
        "answers": answers,
        "horizon": horizon,
        "slots": slots,
    }


def _as_output(value: ProviderLineageOutput | Mapping[str, Any]) -> ProviderLineageOutput:
    if isinstance(value, ProviderLineageOutput):
        return value
    try:
        return ProviderLineageOutput.model_validate(value)
    except ValidationError as error:
        raise HostedBundleLineageError("OUTPUT_SCHEMA_INVALID") from error


def _sorted_pairs(values: set[tuple[str, str]]) -> list[list[str]]:
    return [list(pair) for pair in sorted(values)]


def _program_consistency(
    parsed: ProviderLineageOutput,
    provider_payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare emitted public structure with a provider-visible typed graph.

    A mismatch is a semantic lineage failure, not a provider contract failure.
    P/A have no revision program and are explicitly NOT_APPLICABLE.
    """

    program = provider_payload.get("revision_program")
    if program is None:
        return {
            "status": "NOT_APPLICABLE",
            "reason_codes": [],
            "checks": None,
            "missing_edges": [],
            "unexpected_edges": [],
        }
    if not isinstance(program, Mapping):
        raise HostedBundleLineageError("PAYLOAD_TYPED_GRAPH_INVALID")
    graph = program.get("typed_dependency_graph")
    if not isinstance(graph, Mapping):
        raise HostedBundleLineageError("PAYLOAD_TYPED_GRAPH_INVALID")
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise HostedBundleLineageError("PAYLOAD_TYPED_GRAPH_INVALID")
    node_types: dict[str, str] = {}
    for node in nodes:
        if (
            not isinstance(node, Mapping)
            or not isinstance(node.get("node_id"), str)
            or node.get("node_type") not in {"evidence", "support", "fact", "constraint"}
            or node["node_id"] in node_types
        ):
            raise HostedBundleLineageError("PAYLOAD_TYPED_GRAPH_INVALID")
        node_types[node["node_id"]] = node["node_type"]

    expected_support_nodes = {
        node_id for node_id, node_type in node_types.items() if node_type == "support"
    }
    expected_target_nodes = {
        node_id
        for node_id, node_type in node_types.items()
        if node_type in {"fact", "constraint"}
    }
    expected_evidence_support: set[tuple[str, str]] = set()
    expected_support_target: set[tuple[str, str]] = set()
    expected_fact_dependency: set[tuple[str, str]] = set()
    expected_invalidation: set[tuple[str, str]] = set()
    for edge in edges:
        if not isinstance(edge, Mapping):
            raise HostedBundleLineageError("PAYLOAD_TYPED_GRAPH_INVALID")
        source = edge.get("source_node_id")
        target = edge.get("target_node_id")
        edge_type = edge.get("edge_type")
        if (
            not isinstance(source, str)
            or not isinstance(target, str)
            or source not in node_types
            or target not in node_types
        ):
            raise HostedBundleLineageError("PAYLOAD_TYPED_GRAPH_INVALID")
        pair = (source, target)
        types = (node_types[source], node_types[target])
        if edge_type == "supports" and types == ("evidence", "support"):
            expected_evidence_support.add(pair)
        elif edge_type == "depends_on" and types[0] == "support" and types[1] in {
            "fact",
            "constraint",
        }:
            expected_support_target.add(pair)
        elif edge_type == "depends_on" and types == ("fact", "fact"):
            expected_fact_dependency.add(pair)
        elif edge_type == "invalidates" and types == ("evidence", "evidence"):
            expected_invalidation.add(pair)
        else:
            raise HostedBundleLineageError("PAYLOAD_TYPED_GRAPH_INVALID")

    observed_support_nodes = {node.support_id for node in parsed.support_nodes}
    observed_target_nodes = {target.target_id for target in parsed.targets}
    observed_evidence_support = {
        (f"evidence:{evidence_id}", node.support_id)
        for node in parsed.support_nodes
        for evidence_id in node.evidence_ids
    }
    observed_support_target = {
        (support_id, target.target_id)
        for target in parsed.targets
        for support_id in target.direct_support_ids
    }
    observed_fact_dependency = {
        (upstream_id, target.target_id)
        for target in parsed.targets
        for upstream_id in target.depends_on_target_ids
    }
    observed_invalidation = {
        (f"evidence:{edge.source_evidence_id}", f"evidence:{edge.target_evidence_id}")
        for edge in parsed.invalidations
    }
    checks = {
        "support_node_set_exact": observed_support_nodes == expected_support_nodes,
        "target_node_set_exact": observed_target_nodes == expected_target_nodes,
        "evidence_support_edges_exact": (
            observed_evidence_support == expected_evidence_support
        ),
        "support_target_edges_exact": observed_support_target == expected_support_target,
        "fact_dependency_edges_exact": (
            observed_fact_dependency == expected_fact_dependency
        ),
        "invalidation_edges_exact": observed_invalidation == expected_invalidation,
    }
    reason_by_check = {
        "support_node_set_exact": "PROGRAM_SUPPORT_NODE_SET_MISMATCH",
        "target_node_set_exact": "PROGRAM_TARGET_NODE_SET_MISMATCH",
        "evidence_support_edges_exact": "PROGRAM_EVIDENCE_SUPPORT_EDGE_MISMATCH",
        "support_target_edges_exact": "PROGRAM_SUPPORT_TARGET_EDGE_MISMATCH",
        "fact_dependency_edges_exact": "PROGRAM_FACT_DEPENDENCY_EDGE_MISMATCH",
        "invalidation_edges_exact": "PROGRAM_INVALIDATION_EDGE_MISMATCH",
    }
    expected_all = (
        expected_evidence_support
        | expected_support_target
        | expected_fact_dependency
        | expected_invalidation
    )
    observed_all = (
        observed_evidence_support
        | observed_support_target
        | observed_fact_dependency
        | observed_invalidation
    )
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "reason_codes": sorted(
            reason_by_check[name] for name, passed in checks.items() if not passed
        ),
        "checks": checks,
        "missing_edges": _sorted_pairs(expected_all - observed_all),
        "unexpected_edges": _sorted_pairs(observed_all - expected_all),
    }


def validate_and_compile_output(
    output: ProviderLineageOutput | Mapping[str, Any],
    provider_payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate one provider output and derive deterministic lineage closure.

    Classification is direct-wins: evidence with any direct Support->Target
    path is direct even when a longer Fact->Fact path also exists.  Inherited
    contains only ancestor evidence that has no direct path into the target.
    """

    parsed = _as_output(output)
    contract = _payload_contract(provider_payload)
    if parsed.checkpoint_id != contract["checkpoint_id"]:
        raise HostedBundleLineageError("OUTPUT_CHECKPOINT_MISMATCH")
    if parsed.current_answer not in contract["answers"]:
        raise HostedBundleLineageError("OUTPUT_ANSWER_OUTSIDE_CHOICES")

    horizon = tuple(contract["horizon"])
    horizon_set = set(horizon)
    ordinal = {evidence_id: index for index, evidence_id in enumerate(horizon)}

    support_by_id: dict[str, SupportNodeOutput] = {}
    for node in parsed.support_nodes:
        if node.support_id not in ALLOWED_SUPPORT_IDS:
            raise HostedBundleLineageError("OUTPUT_SUPPORT_ID_UNKNOWN", node.support_id)
        if node.support_id in support_by_id:
            raise HostedBundleLineageError("OUTPUT_DUPLICATE_SUPPORT_ID", node.support_id)
        evidence_ids = _unique(
            node.evidence_ids,
            reason="OUTPUT_DUPLICATE_EVIDENCE_REFERENCE",
            label=node.support_id,
        )
        if not set(evidence_ids) <= horizon_set:
            raise HostedBundleLineageError("OUTPUT_EVIDENCE_OUTSIDE_HORIZON")
        support_by_id[node.support_id] = node

    expected_targets = {
        f"fact:{slot}": ("fact", slot) for slot in contract["slots"] if slot != "video_constraint"
    }
    if "video_constraint" in contract["slots"]:
        expected_targets["constraint:video_constraint"] = (
            "constraint",
            "video_constraint",
        )
    target_by_id: dict[str, TargetOutput] = {}
    for target in parsed.targets:
        if target.target_id in target_by_id:
            raise HostedBundleLineageError("OUTPUT_DUPLICATE_TARGET_ID", target.target_id)
        expected = expected_targets.get(target.target_id)
        if expected != (target.target_type, target.slot):
            raise HostedBundleLineageError("OUTPUT_TARGET_ID_TYPE_SLOT_MISMATCH")
        if target.value not in contract["slots"].get(target.slot, ()):
            raise HostedBundleLineageError("OUTPUT_TARGET_VALUE_OUTSIDE_SCHEMA")
        direct_ids = _unique(
            target.direct_support_ids,
            reason="OUTPUT_DUPLICATE_DIRECT_SUPPORT",
            label=target.target_id,
        )
        if not set(direct_ids) <= set(support_by_id):
            raise HostedBundleLineageError("OUTPUT_DANGLING_SUPPORT_REFERENCE")
        _unique(
            target.depends_on_target_ids,
            reason="OUTPUT_DUPLICATE_DEPENDENCY",
            label=target.target_id,
        )
        target_by_id[target.target_id] = target
    if set(target_by_id) != set(expected_targets):
        raise HostedBundleLineageError("OUTPUT_TARGET_SET_MISMATCH")

    used_support_ids = {
        support_id
        for target in parsed.targets
        for support_id in target.direct_support_ids
    }
    if used_support_ids != set(support_by_id):
        raise HostedBundleLineageError("OUTPUT_ORPHAN_SUPPORT_NODE")

    adjacency: dict[str, list[str]] = {target_id: [] for target_id in target_by_id}
    indegree = {target_id: 0 for target_id in target_by_id}
    for target in parsed.targets:
        for upstream_id in target.depends_on_target_ids:
            upstream = target_by_id.get(upstream_id)
            if upstream is None:
                raise HostedBundleLineageError("OUTPUT_DANGLING_TARGET_DEPENDENCY")
            if (
                target.target_type != "fact"
                or upstream.target_type != "fact"
                or upstream_id == target.target_id
            ):
                raise HostedBundleLineageError("OUTPUT_FORBIDDEN_TARGET_DEPENDENCY")
            adjacency[upstream_id].append(target.target_id)
            indegree[target.target_id] += 1
    queue = deque(sorted(target_id for target_id, degree in indegree.items() if degree == 0))
    topological: list[str] = []
    while queue:
        target_id = queue.popleft()
        topological.append(target_id)
        for downstream in sorted(adjacency[target_id]):
            indegree[downstream] -= 1
            if indegree[downstream] == 0:
                queue.append(downstream)
    if len(topological) != len(target_by_id):
        raise HostedBundleLineageError("OUTPUT_LINEAGE_CYCLE")

    invalidation_pairs: list[tuple[str, str]] = []
    for edge in parsed.invalidations:
        pair = (edge.source_evidence_id, edge.target_evidence_id)
        if pair in invalidation_pairs:
            raise HostedBundleLineageError("OUTPUT_DUPLICATE_INVALIDATION")
        if not set(pair) <= horizon_set:
            raise HostedBundleLineageError("OUTPUT_INVALIDATION_OUTSIDE_HORIZON")
        if ordinal[pair[0]] <= ordinal[pair[1]]:
            raise HostedBundleLineageError("OUTPUT_INVALIDATION_NOT_LATER_TO_EARLIER")
        invalidation_pairs.append(pair)
    invalidated_ids = {target for _, target in invalidation_pairs}
    cited_ids = {
        evidence_id
        for node in parsed.support_nodes
        for evidence_id in node.evidence_ids
    }
    if cited_ids & invalidated_ids:
        raise HostedBundleLineageError("OUTPUT_INVALIDATED_EVIDENCE_ACTIVE")

    direct_by_target: dict[str, set[str]] = {}
    total_by_target: dict[str, set[str]] = {}
    inherited_by_target: dict[str, set[str]] = {}
    for target_id in topological:
        target = target_by_id[target_id]
        direct = {
            evidence_id
            for support_id in target.direct_support_ids
            for evidence_id in support_by_id[support_id].evidence_ids
        }
        ancestor_total = {
            evidence_id
            for upstream_id in target.depends_on_target_ids
            for evidence_id in total_by_target[upstream_id]
        }
        inherited = ancestor_total - direct
        direct_by_target[target_id] = direct
        inherited_by_target[target_id] = inherited
        total_by_target[target_id] = direct | inherited

    normalized_output = parsed.model_dump(mode="json")
    normalized_output["support_nodes"] = sorted(
        normalized_output["support_nodes"], key=lambda row: row["support_id"]
    )
    for row in normalized_output["support_nodes"]:
        row["evidence_ids"] = sorted(row["evidence_ids"], key=ordinal.__getitem__)
    normalized_output["targets"] = sorted(
        normalized_output["targets"], key=lambda row: row["target_id"]
    )
    for row in normalized_output["targets"]:
        row["direct_support_ids"] = sorted(row["direct_support_ids"])
        row["depends_on_target_ids"] = sorted(row["depends_on_target_ids"])
    normalized_output["invalidations"] = sorted(
        normalized_output["invalidations"],
        key=lambda row: (row["source_evidence_id"], row["target_evidence_id"]),
    )

    targets = []
    for target_id in sorted(target_by_id):
        target = target_by_id[target_id]
        direct = sorted(direct_by_target[target_id], key=ordinal.__getitem__)
        inherited = sorted(inherited_by_target[target_id], key=ordinal.__getitem__)
        total = sorted(total_by_target[target_id], key=ordinal.__getitem__)
        targets.append(
            {
                "target_id": target_id,
                "target_type": target.target_type,
                "slot": target.slot,
                "value": target.value,
                "direct_active_evidence_ids": direct,
                "inherited_active_evidence_ids": inherited,
                "all_active_evidence_ids": total,
            }
        )

    compiled = {
        "schema_version": COMPILED_SCHEMA_VERSION,
        "checkpoint_id": parsed.checkpoint_id,
        "current_answer": parsed.current_answer,
        "claim": parsed.claim,
        "source_horizon_evidence_ids": list(horizon),
        "active_support_evidence_ids": sorted(cited_ids, key=ordinal.__getitem__),
        "invalidated_evidence_ids": sorted(invalidated_ids, key=ordinal.__getitem__),
        "invalidation_edges": [
            {"source_evidence_id": source, "target_evidence_id": target}
            for source, target in sorted(invalidation_pairs)
        ],
        "targets": targets,
        "program_consistency": _program_consistency(parsed, provider_payload),
        "normalized_output": normalized_output,
    }
    compiled["normalized_output_fingerprint_sha256"] = _fingerprint(normalized_output)
    compiled["fingerprint_sha256"] = _fingerprint(compiled)
    return compiled


def load_gold(path: str | Path = DEFAULT_GOLD_PATH) -> dict[str, Any]:
    """Explicitly load post-call gold; never called by compilation."""

    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise HostedBundleLineageError("GOLD_SCHEMA_INVALID")
    expected = {
        "schema_version",
        "status",
        "case_id",
        "pre_event",
        "post_event",
        "stale_expectation",
        "claim_boundary",
    }
    if set(value) != expected or value["schema_version"] != "ebrt-hosted-bundle-lineage-gold-v0.6":
        raise HostedBundleLineageError("GOLD_SCHEMA_INVALID")
    return value


def _target_map(compiled: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    targets = compiled.get("targets")
    if not isinstance(targets, list):
        raise HostedBundleLineageError("COMPILED_SCHEMA_INVALID")
    return {str(row["target_id"]): row for row in targets}


def _grade_target(
    observed: Mapping[str, Any] | None, expected: Mapping[str, Any]
) -> dict[str, Any]:
    observed_direct = set(() if observed is None else observed["direct_active_evidence_ids"])
    observed_inherited = set(() if observed is None else observed["inherited_active_evidence_ids"])
    observed_total = set(() if observed is None else observed["all_active_evidence_ids"])
    expected_direct = set(expected["direct_active_evidence_ids"])
    expected_inherited = set(expected["inherited_active_evidence_ids"])
    expected_total = set(expected["all_active_evidence_ids"])
    metadata_exact = bool(
        observed is not None
        and (observed["target_type"], observed["slot"], observed["value"])
        == (expected["target_type"], expected["slot"], expected["value"])
    )
    checks = {
        "metadata_exact": metadata_exact,
        "direct_exact": observed_direct == expected_direct,
        "inherited_exact": observed_inherited == expected_inherited,
        "total_exact": observed_total == expected_total,
    }
    reasons: list[str] = []
    if not metadata_exact:
        reasons.append("TARGET_METADATA_MISMATCH")
    if expected_direct - observed_direct:
        reasons.append("DIRECT_SUPPORT_MISSING")
    if observed_direct - expected_direct:
        reasons.append("DIRECT_SUPPORT_UNEXPECTED")
    if expected_inherited - observed_inherited:
        reasons.append("INHERITED_SUPPORT_MISSING")
    if observed_inherited - expected_inherited:
        reasons.append("INHERITED_SUPPORT_UNEXPECTED")
    if expected_total - observed_total:
        reasons.append("TOTAL_SUPPORT_MISSING")
    if observed_total - expected_total:
        reasons.append("TOTAL_SUPPORT_UNEXPECTED")
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "reason_codes": sorted(set(reasons)),
        "checks": checks,
        "missing_evidence_ids": sorted(expected_total - observed_total),
        "unexpected_evidence_ids": sorted(observed_total - expected_total),
        "target_id": expected["target_id"],
    }


def _grade(compiled: Mapping[str, Any], expected: Mapping[str, Any]) -> dict[str, Any]:
    observed_targets = _target_map(compiled)
    expected_targets = {row["target_id"]: row for row in expected["targets"]}
    target_results = [
        _grade_target(observed_targets.get(target_id), expected_targets[target_id])
        for target_id in sorted(expected_targets)
    ]
    answer_pass = compiled.get("current_answer") == expected["answer"]
    fact_results = [
        row for row in target_results if row["target_id"].startswith("fact:")
    ]
    constraint_results = [
        row for row in target_results if row["target_id"].startswith("constraint:")
    ]
    program_consistency = compiled.get("program_consistency")
    if not isinstance(program_consistency, Mapping) or program_consistency.get(
        "status"
    ) not in {"PASS", "FAIL", "NOT_APPLICABLE"}:
        raise HostedBundleLineageError("COMPILED_PROGRAM_CONSISTENCY_INVALID")
    program_consistent = program_consistency["status"] != "FAIL"
    invalidations_exact = (
        compiled.get("invalidation_edges") == expected["invalidation_edges"]
    )
    invalidated_absent = not bool(
        set(compiled.get("active_support_evidence_ids", ()))
        & {row["target_evidence_id"] for row in expected["invalidation_edges"]}
    )
    statuses = {
        "answer_status": "PASS" if answer_pass else "FAIL",
        "fact_local_lineage_status": (
            "PASS"
            if all(row["status"] == "PASS" for row in fact_results)
            and program_consistent
            else "FAIL"
        ),
        "invalidation_status": (
            "PASS" if invalidations_exact and invalidated_absent else "FAIL"
        ),
        "stable_fact_status": (
            "PASS"
            if len(constraint_results) == 1 and constraint_results[0]["status"] == "PASS"
            else "FAIL"
        ),
    }
    reason_codes: list[str] = []
    if not answer_pass:
        reason_codes.append("ANSWER_EXACT_MISMATCH")
    if not invalidations_exact:
        observed = set(
            (row["source_evidence_id"], row["target_evidence_id"])
            for row in compiled.get("invalidation_edges", ())
        )
        wanted = set(
            (row["source_evidence_id"], row["target_evidence_id"])
            for row in expected["invalidation_edges"]
        )
        if wanted - observed:
            reason_codes.append("INVALIDATION_MISSING")
        if observed - wanted:
            reason_codes.append("INVALIDATION_UNEXPECTED")
    if not invalidated_absent:
        reason_codes.append("INVALIDATED_SUPPORT_ACTIVE")
    reason_codes.extend(
        reason
        for row in target_results
        for reason in row["reason_codes"]
    )
    reason_codes.extend(program_consistency.get("reason_codes", ()))
    strict_pass = all(value == "PASS" for value in statuses.values())
    result = {
        "schema_version": GRADE_SCHEMA_VERSION,
        "status": "PASS" if strict_pass else "FAIL",
        **statuses,
        "reason_codes": sorted(set(reason_codes)),
        "target_results": target_results,
        "program_consistency": copy.deepcopy(dict(program_consistency)),
        "compiled_fingerprint_sha256": compiled["fingerprint_sha256"],
    }
    result["fingerprint_sha256"] = _fingerprint(result)
    return result


def grade_p_pre_event(compiled: Mapping[str, Any], gold: Mapping[str, Any]) -> dict[str, Any]:
    return _grade(compiled, gold["pre_event"])


def grade_post_event(compiled: Mapping[str, Any], gold: Mapping[str, Any]) -> dict[str, Any]:
    return _grade(compiled, gold["post_event"])


def grade_p_stale(
    compiled: Mapping[str, Any], gold: Mapping[str, Any]
) -> dict[str, Any]:
    """Regrade the exact same compiled P bytes under the post-event contract."""

    pre_grade = grade_p_pre_event(compiled, gold)
    post_grade = grade_post_event(compiled, gold)
    expected = gold["stale_expectation"]
    observed_failed_axes = sorted(
        key
        for key in (
            "answer_status",
            "fact_local_lineage_status",
            "invalidation_status",
            "stable_fact_status",
        )
        if post_grade[key] == "FAIL"
    )
    checks = {
        "p_pre_event_pass": pre_grade["status"] == "PASS",
        "same_compiled_fingerprint_used": (
            post_grade["compiled_fingerprint_sha256"]
            == compiled["fingerprint_sha256"]
        ),
        "post_event_contract_fails": post_grade["status"] == "FAIL",
        "failed_axes_exact": observed_failed_axes == expected["failed_axes"],
        "stable_fact_remains_pass": post_grade["stable_fact_status"] == "PASS",
    }
    result = {
        "schema_version": "ebrt-p-stale-regrade-v0.6",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "reason_codes": [] if all(checks.values()) else ["P_STALE_SIGNATURE_MISMATCH"],
        "checks": checks,
        "observed_failed_axes": observed_failed_axes,
        "p_compiled_fingerprint_sha256": compiled["fingerprint_sha256"],
        "pre_event_grade_fingerprint_sha256": pre_grade["fingerprint_sha256"],
        "post_event_grade_fingerprint_sha256": post_grade["fingerprint_sha256"],
    }
    result["fingerprint_sha256"] = _fingerprint(result)
    return result


def _sample_revision_program() -> dict[str, Any]:
    nodes = [
        {"node_id": f"evidence:R{index}", "node_type": "evidence"}
        for index in range(1, 7)
    ] + [
        {"node_id": "support:judging_basis", "node_type": "support"},
        {"node_id": "support:demo_readiness", "node_type": "support"},
        {"node_id": "support:superseding_guidance", "node_type": "support"},
        {"node_id": "support:video_constraint", "node_type": "support"},
        {"node_id": "fact:final_priority", "node_type": "fact"},
        {"node_id": "fact:demo_centerpiece", "node_type": "fact"},
        {"node_id": "constraint:video_constraint", "node_type": "constraint"},
    ]
    edge_specs = [
        ("supports", "evidence:R2", "support:judging_basis"),
        ("supports", "evidence:R4", "support:demo_readiness"),
        ("supports", "evidence:R5", "support:video_constraint"),
        ("supports", "evidence:R6", "support:superseding_guidance"),
        ("depends_on", "support:judging_basis", "fact:final_priority"),
        ("depends_on", "support:demo_readiness", "fact:demo_centerpiece"),
        ("depends_on", "support:demo_readiness", "fact:final_priority"),
        ("depends_on", "support:superseding_guidance", "fact:demo_centerpiece"),
        ("depends_on", "support:superseding_guidance", "fact:final_priority"),
        ("depends_on", "support:video_constraint", "constraint:video_constraint"),
        ("depends_on", "fact:final_priority", "fact:demo_centerpiece"),
        ("invalidates", "evidence:R6", "evidence:R3"),
    ]
    return {
        "typed_dependency_graph": {
            "schema_version": "ebrt-provider-safe-typed-lineage-graph-v0.6",
            "nodes": nodes,
            "edges": [
                {
                    "edge_id": f"sample:{index:02d}",
                    "edge_type": edge_type,
                    "source_node_id": source,
                    "target_node_id": target,
                }
                for index, (edge_type, source, target) in enumerate(edge_specs)
            ],
        }
    }


def _payload(post: bool, *, with_program: bool = False) -> dict[str, Any]:
    evidence = [
        {"evidence_id": f"R{index}", "text": f"locked evidence R{index}"}
        for index in range(1, 7 if post else 6)
    ]
    return {
        "checkpoint_id": (
            "hackathon_strategy_walkthrough:full_context_final"
            if post
            else "hackathon_strategy_walkthrough:pre_event"
        ),
        "answer_choices": ["POLISH", "PROVE"],
        "decision_slots": [
            {
                "slot_id": "final_priority",
                "allowed_values": ["ADDITIONAL_UI_POLISH", "END_TO_END_PROOF"],
            },
            {
                "slot_id": "demo_centerpiece",
                "allowed_values": ["POLISHED_SCREENS", "LIVE_REASONING_DIFF"],
            },
            {
                "slot_id": "video_constraint",
                "allowed_values": ["THREE_MINUTE_NARRATED"],
            },
        ],
        "all_raw_evidence": evidence,
        "allowed_evidence_ids": [row["evidence_id"] for row in evidence],
        "revision_program": _sample_revision_program() if with_program else None,
    }


def sample_provider_output(post: bool) -> dict[str, Any]:
    """Return a strict offline fake-provider sample used by boundary tests."""

    if not post:
        return {
            "schema_version": OUTPUT_SCHEMA_VERSION,
            "checkpoint_id": "hackathon_strategy_walkthrough:pre_event",
            "current_answer": "POLISH",
            "claim": "The operative design brief makes polish the current priority.",
            "support_nodes": [
                {"support_id": "support:judging_basis", "evidence_ids": ["R2"]},
                {"support_id": "support:legacy_guidance", "evidence_ids": ["R3"]},
                {"support_id": "support:video_constraint", "evidence_ids": ["R5"]},
            ],
            "targets": [
                {"target_id": "fact:final_priority", "target_type": "fact", "slot": "final_priority", "value": "ADDITIONAL_UI_POLISH", "direct_support_ids": ["support:judging_basis", "support:legacy_guidance"], "depends_on_target_ids": []},
                {"target_id": "fact:demo_centerpiece", "target_type": "fact", "slot": "demo_centerpiece", "value": "POLISHED_SCREENS", "direct_support_ids": ["support:legacy_guidance"], "depends_on_target_ids": []},
                {"target_id": "constraint:video_constraint", "target_type": "constraint", "slot": "video_constraint", "value": "THREE_MINUTE_NARRATED", "direct_support_ids": ["support:video_constraint"], "depends_on_target_ids": []},
            ],
            "invalidations": [],
        }
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "checkpoint_id": "hackathon_strategy_walkthrough:full_context_final",
        "current_answer": "PROVE",
        "claim": "The corrected equal-weight guidance requires an end-to-end proof.",
        "support_nodes": [
            {"support_id": "support:judging_basis", "evidence_ids": ["R2"]},
            {"support_id": "support:demo_readiness", "evidence_ids": ["R4"]},
            {"support_id": "support:superseding_guidance", "evidence_ids": ["R6"]},
            {"support_id": "support:video_constraint", "evidence_ids": ["R5"]},
        ],
        "targets": [
            {"target_id": "fact:final_priority", "target_type": "fact", "slot": "final_priority", "value": "END_TO_END_PROOF", "direct_support_ids": ["support:judging_basis", "support:demo_readiness", "support:superseding_guidance"], "depends_on_target_ids": []},
            {"target_id": "fact:demo_centerpiece", "target_type": "fact", "slot": "demo_centerpiece", "value": "LIVE_REASONING_DIFF", "direct_support_ids": ["support:demo_readiness", "support:superseding_guidance"], "depends_on_target_ids": ["fact:final_priority"]},
            {"target_id": "constraint:video_constraint", "target_type": "constraint", "slot": "video_constraint", "value": "THREE_MINUTE_NARRATED", "direct_support_ids": ["support:video_constraint"], "depends_on_target_ids": []},
        ],
        "invalidations": [
            {"source_evidence_id": "R6", "target_evidence_id": "R3"}
        ],
    }


def _preflight_material() -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    """Exercise schema/closure/program logic without opening semantic gold."""

    p = validate_and_compile_output(sample_provider_output(False), _payload(False))
    d = validate_and_compile_output(
        sample_provider_output(True), _payload(True, with_program=True)
    )
    demo = next(row for row in d["targets"] if row["target_id"] == "fact:demo_centerpiece")
    assert demo["direct_active_evidence_ids"] == ["R4", "R6"]
    assert demo["inherited_active_evidence_ids"] == ["R2"]
    assert demo["all_active_evidence_ids"] == ["R2", "R4", "R6"]
    assert d["program_consistency"]["status"] == "PASS"

    # This output has the exact desired evidence closure but collapses R6 into
    # demo_readiness and drops superseding_guidance.  It remains syntactically
    # valid and compiles; program consistency must expose the factorization bug.
    pooled = sample_provider_output(True)
    pooled["support_nodes"] = [
        {"support_id": "support:judging_basis", "evidence_ids": ["R2"]},
        {"support_id": "support:demo_readiness", "evidence_ids": ["R4", "R6"]},
        {"support_id": "support:video_constraint", "evidence_ids": ["R5"]},
    ]
    pooled["targets"][0]["direct_support_ids"] = [
        "support:judging_basis",
        "support:demo_readiness",
    ]
    pooled["targets"][1]["direct_support_ids"] = ["support:demo_readiness"]
    pooled_compiled = validate_and_compile_output(
        pooled, _payload(True, with_program=True)
    )
    pooled_demo = next(
        row
        for row in pooled_compiled["targets"]
        if row["target_id"] == "fact:demo_centerpiece"
    )
    assert pooled_demo["direct_active_evidence_ids"] == ["R4", "R6"]
    assert pooled_demo["inherited_active_evidence_ids"] == ["R2"]
    assert pooled_compiled["program_consistency"]["status"] == "FAIL"

    rejected: list[str] = []
    attacks: list[tuple[str, dict[str, Any], str]] = []
    cycle = sample_provider_output(True)
    cycle["targets"][0]["depends_on_target_ids"] = ["fact:demo_centerpiece"]
    attacks.append(("cycle", cycle, "OUTPUT_LINEAGE_CYCLE"))
    invalid_active = sample_provider_output(True)
    invalid_active["support_nodes"][0]["evidence_ids"] = ["R3"]
    attacks.append(("invalidated-active", invalid_active, "OUTPUT_INVALIDATED_EVIDENCE_ACTIVE"))
    dangling = sample_provider_output(True)
    dangling["targets"][0]["direct_support_ids"] = ["support:legacy_guidance"]
    attacks.append(("dangling", dangling, "OUTPUT_DANGLING_SUPPORT_REFERENCE"))
    future = sample_provider_output(False)
    future["support_nodes"][0]["evidence_ids"] = ["R6"]
    attacks.append(("future-horizon", future, "OUTPUT_EVIDENCE_OUTSIDE_HORIZON"))
    extra = sample_provider_output(True)
    extra["private_chain_of_thought"] = "forbidden"
    attacks.append(("unknown-field", extra, "OUTPUT_SCHEMA_INVALID"))
    for label, attack, reason in attacks:
        try:
            validate_and_compile_output(
                attack, _payload(False if label == "future-horizon" else True)
            )
        except HostedBundleLineageError as error:
            assert error.reason_code == reason, (label, error.reason_code, reason)
            rejected.append(label)
        else:
            raise AssertionError(f"attack accepted: {label}")
    return p, d, rejected


def preflight_self_test() -> dict[str, Any]:
    """Gold-free live launch preflight.

    This function must remain safe to call before the five provider attempts.
    It neither calls ``load_gold`` nor invokes any grading function.
    """

    p, d, rejected = _preflight_material()
    return {
        "status": "PASS",
        "checks": [
            "strict Pydantic output rejects unknown fields",
            "closure is locally derived with direct-wins inheritance",
            "typed-program edge and role factorization is checked separately from closure",
            "support pooling can preserve closure but is marked program-inconsistent",
            "cycle, dangling support, future evidence, and invalidated active support are rejected",
        ],
        "gold_loaded": False,
        "rejected_attacks": rejected,
        "p_fingerprint_sha256": p["fingerprint_sha256"],
        "d_fingerprint_sha256": d["fingerprint_sha256"],
    }


def self_test() -> dict[str, Any]:
    preflight = preflight_self_test()
    gold = load_gold()
    p = validate_and_compile_output(sample_provider_output(False), _payload(False))
    d = validate_and_compile_output(
        sample_provider_output(True), _payload(True, with_program=True)
    )
    assert grade_p_pre_event(p, gold)["status"] == "PASS"
    assert grade_post_event(d, gold)["status"] == "PASS"
    assert grade_p_stale(p, gold)["status"] == "PASS"

    pooled = sample_provider_output(True)
    pooled["support_nodes"] = [
        {"support_id": "support:judging_basis", "evidence_ids": ["R2"]},
        {"support_id": "support:demo_readiness", "evidence_ids": ["R4", "R6"]},
        {"support_id": "support:video_constraint", "evidence_ids": ["R5"]},
    ]
    pooled["targets"][0]["direct_support_ids"] = [
        "support:judging_basis",
        "support:demo_readiness",
    ]
    pooled["targets"][1]["direct_support_ids"] = ["support:demo_readiness"]
    pooled_compiled = validate_and_compile_output(
        pooled, _payload(True, with_program=True)
    )
    pooled_grade = grade_post_event(pooled_compiled, gold)
    assert pooled_grade["fact_local_lineage_status"] == "FAIL"
    assert pooled_grade["status"] == "FAIL"
    return {
        **preflight,
        "checks": preflight["checks"]
        + [
            "P passes R1-R5 and its unchanged fingerprint is stale under R1-R6",
            "D passes answer, fact-local lineage, invalidation, and stable-fact axes",
            "closure-equivalent support pooling is a semantic lineage FAIL",
        ],
        "gold_loaded": True,
        "pooled_program_reason_codes": pooled_grade["program_consistency"][
            "reason_codes"
        ],
    }


def main() -> None:
    print(json.dumps(self_test(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
