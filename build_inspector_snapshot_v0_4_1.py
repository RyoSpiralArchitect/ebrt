#!/usr/bin/env python3
"""Build a deterministic public Inspector snapshot from EBRT benchmark bundles.

The exporter accepts the frozen two-arm v0.4 Direct-vs-Full bundle and the
four-arm v0.4.1/v0.4.2 causal-control bundles.  It exposes only saved raw
evidence, emitted public Reasoning Cards, machine grades, and sanitized provider
accounting.  Card-to-card diffs describe public outputs, not model internals.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import shutil
import statistics
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parent
DEFAULT_BUNDLE = ROOT / "artifacts" / "benchmark_direct_full_calibration_v0_4_dev"
DEFAULT_PARENT_MANIFEST = DEFAULT_BUNDLE / "manifest.json"
DEFAULT_OUTPUT = (
    ROOT / "inspector" / "public" / "data" / "ebrt-public-inspector-v0.1.json"
)
INSPECTOR_SCHEMA_VERSION = "ebrt-public-inspector-v0.1"

DIRECT_FIXED = "direct_raw_fixed_revision"
DIRECT_NO_REVISION = "direct_raw_no_revision"
FULL_RESTART = "full_restart"
STAGED_CUMULATIVE_RAW = "staged_cumulative_raw"
DIRECT_FIXED_RERUN = "direct_raw_fixed_revision_rerun"
STAGED_CARD_ONLY_RERUN = "staged_card_only_rerun"

TWO_ARM_SET = frozenset((DIRECT_FIXED, FULL_RESTART))
FOUR_ARM_SET = frozenset(
    (DIRECT_FIXED, DIRECT_NO_REVISION, FULL_RESTART, STAGED_CUMULATIVE_RAW)
)
FOUR_ARM_RUNNER_SET = frozenset(
    (
        DIRECT_FIXED_RERUN,
        DIRECT_NO_REVISION,
        STAGED_CARD_ONLY_RERUN,
        STAGED_CUMULATIVE_RAW,
    )
)
ARM_ALIASES = {
    DIRECT_FIXED: DIRECT_FIXED,
    DIRECT_FIXED_RERUN: DIRECT_FIXED,
    DIRECT_NO_REVISION: DIRECT_NO_REVISION,
    FULL_RESTART: FULL_RESTART,
    STAGED_CARD_ONLY_RERUN: FULL_RESTART,
    STAGED_CUMULATIVE_RAW: STAGED_CUMULATIVE_RAW,
}
CANONICAL_ARM_ORDER = (
    DIRECT_FIXED,
    DIRECT_NO_REVISION,
    FULL_RESTART,
    STAGED_CUMULATIVE_RAW,
)
DIRECT_ARMS = frozenset((DIRECT_FIXED, DIRECT_NO_REVISION))
STAGED_ARMS = frozenset((FULL_RESTART, STAGED_CUMULATIVE_RAW))

CONTRAST_DEFINITIONS = (
    {
        "contrast_id": "direct_full_recorded_calibration",
        "reference_arm": DIRECT_FIXED,
        "candidate_arm": FULL_RESTART,
        "public_question": (
            "How does staged card-only execution change final public output quality "
            "relative to one-shot fixed-revision Direct?"
        ),
    },
    {
        "contrast_id": "revision_envelope_ablation",
        "reference_arm": DIRECT_FIXED,
        "candidate_arm": DIRECT_NO_REVISION,
        "public_question": "Does fixed revision metadata change final public output quality?",
    },
    {
        "contrast_id": "raw_aperture_ablation",
        "reference_arm": FULL_RESTART,
        "candidate_arm": STAGED_CUMULATIVE_RAW,
        "public_question": (
            "Does retaining the visible raw prefix change or recover staged public "
            "output quality?"
        ),
    },
    {
        "contrast_id": "staged_residual",
        "reference_arm": DIRECT_FIXED,
        "candidate_arm": STAGED_CUMULATIVE_RAW,
        "public_question": "What quality difference remains after staged raw retention is restored?",
    },
)

FIELD_SEMANTICS = {
    "timeline": "ordered emitted public Reasoning Cards only",
    "public_diff": (
        "set and slot diffs between emitted public cards; not a latent-state trace"
    ),
    "presented_raw_evidence_ids": "public raw-input aperture for that call",
    "allowed_evidence_ids": (
        "stored request-contract evidence roster; not attention or active support"
    ),
    "confidence": (
        "provider-emitted public card field; not a calibrated correctness probability"
    ),
    "reasoning_tokens": (
        "provider-reported usage detail; not private reasoning text or reasoning quality"
    ),
    "latency_ms": "recorded client-call latency; not server compute",
    "cause_decision": (
        "case-level public outcome classification under locked controls"
    ),
}

CARD_FIELDS = (
    "schema_version",
    "checkpoint_id",
    "claim",
    "topic",
    "stance",
    "confidence",
    "evidence_ids",
    "current_answer",
    "revision_cue",
    "decision_facts",
    "invalidated_evidence_ids",
)
USAGE_FIELDS = (
    "exact_provider_tokens",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cached_input_tokens",
    "cache_write_tokens",
    "reasoning_tokens",
)
COST_FIELDS = (
    "logical_calls",
    "api_calls",
    "latency_ms",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cached_input_tokens",
    "cache_write_tokens",
    "reasoning_tokens",
    "exact_provider_tokens",
)
DELTA_FIELDS = (
    "api_calls",
    "latency_ms",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "reasoning_tokens",
)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"expected a JSON object: {path}:{line_number}")
            output.append(value)
    return output


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a nonempty string")
    return value


def _string_list(value: Any, label: str) -> list[str]:
    items = [_string(item, f"{label} item") for item in _list(value, label)]
    if len(items) != len(set(items)):
        raise ValueError(f"{label} must not contain duplicates")
    return items


def _nonnegative_int_or_none(value: Any, label: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer or null")
    return value


def _nonnegative_number_or_none(value: Any, label: str) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a non-negative number or null")
    if not math.isfinite(float(value)) or value < 0:
        raise ValueError(f"{label} must be a finite non-negative number")
    return value


def _safe_relative_path(root: Path, name: str, label: str) -> Path:
    relative = Path(name)
    if relative.is_absolute():
        raise ValueError(f"{label} must be relative: {name}")
    target = (root / relative).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f"{label} escaped its root: {name}")
    return target


def _validate_manifest(bundle: Path) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    manifest_path = bundle / "manifest.json"
    if not manifest_path.exists():
        return None, {
            "manifest_present": False,
            "artifact_files_verified": [],
            "source_files_verified": [],
            "parent_manifest_verified": False,
        }

    manifest = _load_json(manifest_path)
    artifact_hashes = _mapping(
        manifest.get("artifact_sha256"), "manifest artifact_sha256"
    )
    if "results.json" not in artifact_hashes:
        raise ValueError("manifest artifact hashes must include results.json")
    artifact_verified: list[str] = []
    for name in sorted(artifact_hashes):
        expected = _string(artifact_hashes[name], f"manifest artifact hash for {name}")
        target = _safe_relative_path(bundle, str(name), "manifest artifact path")
        if not target.is_file():
            raise ValueError(f"manifest artifact is missing: {name}")
        if _sha256(target) != expected:
            raise ValueError(f"manifest artifact hash mismatch: {name}")
        artifact_verified.append(str(name))

    source_hashes_value = manifest.get("source_sha256", {})
    source_hashes = _mapping(source_hashes_value, "manifest source_sha256")
    source_verified: list[str] = []
    for name in sorted(source_hashes):
        expected = _string(source_hashes[name], f"manifest source hash for {name}")
        target = _safe_relative_path(ROOT, str(name), "manifest source path")
        if not target.is_file():
            raise ValueError(f"manifest source is missing: {name}")
        if _sha256(target) != expected:
            raise ValueError(f"manifest source hash mismatch: {name}")
        source_verified.append(str(name))

    parent_manifest_verified = False
    parent_hash = manifest.get("parent_manifest_sha256")
    if parent_hash is not None:
        expected_parent_hash = _string(parent_hash, "parent_manifest_sha256")
        if not DEFAULT_PARENT_MANIFEST.is_file():
            raise ValueError("parent manifest is missing from the current checkout")
        if _sha256(DEFAULT_PARENT_MANIFEST) != expected_parent_hash:
            raise ValueError("parent manifest hash mismatch")
        parent_manifest_verified = True

    return manifest, {
        "manifest_present": True,
        "manifest_schema_version": manifest.get("schema_version"),
        "manifest_status": manifest.get("status"),
        "success_manifest": manifest.get("success_manifest"),
        "artifact_files_verified": artifact_verified,
        "source_files_verified": source_verified,
        "parent_manifest_verified": parent_manifest_verified,
    }


def _load_bundle(
    bundle: Path,
) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any]]:
    if not bundle.is_dir():
        raise ValueError(f"bundle directory does not exist: {bundle}")
    manifest, validation = _validate_manifest(bundle)
    results_path = bundle / "results.json"
    if not results_path.is_file():
        raise ValueError(f"bundle has no results.json: {bundle}")
    results = _load_json(results_path)
    traces_path = bundle / "traces.jsonl"
    if traces_path.exists() and _load_jsonl(traces_path) != results.get("runs"):
        raise ValueError("traces.jsonl did not exactly match results runs")
    calls_path = bundle / "calls.jsonl"
    if calls_path.exists():
        expected_calls: list[dict[str, Any]] = []
        for run_value in _list(results.get("runs"), "results runs"):
            run = _mapping(run_value, "results run")
            arms = _mapping(run.get("arms"), "results run arms")
            for arm in _string_list(run.get("arm_order"), "results arm_order"):
                arm_value = _mapping(arms.get(arm), f"results arm {arm}")
                for call_index, receipt in enumerate(
                    _list(arm_value.get("receipts", []), f"{arm} receipts")
                ):
                    expected_calls.append(
                        {
                            "run_id": run.get("run_id"),
                            "trial_index": run.get("trial_index"),
                            "case_id": run.get("case_id"),
                            "family": run.get("family"),
                            "arm": arm,
                            "arm_call_index": call_index,
                            "receipt": receipt,
                        }
                    )
        if _load_jsonl(calls_path) != expected_calls:
            raise ValueError("calls.jsonl did not exactly match results receipts")
    return results, manifest, validation


def _case_evidence(run: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    case = _mapping(run.get("case"), "run case")
    envelope_value = run.get(
        "revision_envelope", run.get("fixed_revision_envelope", {})
    )
    envelope = _mapping(envelope_value, "revision envelope")
    invalidated = set(
        _string_list(
            envelope.get("invalidated_evidence_ids", []),
            "revision invalidated_evidence_ids",
        )
    )
    evidence: list[dict[str, Any]] = []
    for value in _list(case.get("initial_evidence"), "case initial_evidence"):
        item = _mapping(value, "initial evidence")
        evidence.append(
            {
                "evidence_id": _string(item.get("evidence_id"), "evidence_id"),
                "ordinal": len(evidence) + 1,
                "kind": "initial",
                "text": _string(item.get("text"), "evidence text"),
            }
        )
    late = _mapping(case.get("late_evidence"), "case late_evidence")
    evidence.append(
        {
            "evidence_id": _string(late.get("evidence_id"), "late evidence_id"),
            "ordinal": len(evidence) + 1,
            "kind": "late",
            "text": _string(late.get("text"), "late evidence text"),
        }
    )
    evidence_ids = [item["evidence_id"] for item in evidence]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("case evidence IDs must be unique")
    if not invalidated <= set(evidence_ids):
        raise ValueError("revision envelope invalidated an unknown evidence ID")
    for item in evidence:
        item["listed_invalidated_by_envelope"] = item["evidence_id"] in invalidated
    return evidence, evidence_ids


def _ordered_ids(values: Sequence[str], evidence_ids: Sequence[str]) -> list[str]:
    order = {item: index for index, item in enumerate(evidence_ids)}
    return sorted(set(values), key=lambda item: (order.get(item, len(order)), item))


def _normalize_fact(
    value: Mapping[str, Any], evidence_ids: Sequence[str]
) -> dict[str, Any]:
    fact_evidence = _string_list(value.get("evidence_ids"), "fact evidence_ids")
    if not set(fact_evidence) <= set(evidence_ids):
        raise ValueError("decision fact cited unknown evidence")
    return {
        "slot": _string(value.get("slot"), "decision fact slot"),
        "value": _string(value.get("value"), "decision fact value"),
        "evidence_ids": fact_evidence,
    }


def _normalize_card(value: Any, evidence_ids: Sequence[str]) -> dict[str, Any]:
    card = _mapping(value, "public card")
    for name in CARD_FIELDS:
        if name not in card:
            raise ValueError(f"public card omitted {name}")
    card_evidence = _string_list(card["evidence_ids"], "card evidence_ids")
    invalidated = _string_list(
        card["invalidated_evidence_ids"], "card invalidated_evidence_ids"
    )
    if not set(card_evidence) <= set(evidence_ids):
        raise ValueError("public card cited unknown evidence")
    if not set(invalidated) <= set(evidence_ids):
        raise ValueError("public card invalidated unknown evidence")
    facts = [
        _normalize_fact(_mapping(item, "decision fact"), evidence_ids)
        for item in _list(card["decision_facts"], "card decision_facts")
    ]
    slots = [item["slot"] for item in facts]
    if len(slots) != len(set(slots)):
        raise ValueError("public card decision slots must be unique")
    stance = card["stance"]
    confidence = card["confidence"]
    revision_cue = card["revision_cue"]
    for name, number, lower, upper in (
        ("stance", stance, -1.0, 1.0),
        ("confidence", confidence, 0.0, 1.0),
        ("revision_cue", revision_cue, 0.0, 1.0),
    ):
        if (
            isinstance(number, bool)
            or not isinstance(number, (int, float))
            or not math.isfinite(float(number))
            or not lower <= number <= upper
        ):
            raise ValueError(f"public card {name} escaped its finite range")
    return {
        "schema_version": _string(card["schema_version"], "card schema_version"),
        "checkpoint_id": _string(card["checkpoint_id"], "checkpoint_id"),
        "claim": _string(card["claim"], "claim"),
        "topic": _string(card["topic"], "topic"),
        "stance": stance,
        "confidence": confidence,
        "evidence_ids": card_evidence,
        "current_answer": _string(card["current_answer"], "current_answer"),
        "revision_cue": revision_cue,
        "decision_facts": facts,
        "invalidated_evidence_ids": invalidated,
    }


def _public_support(card: Mapping[str, Any]) -> list[str]:
    output: list[str] = []
    for evidence_id in card["evidence_ids"]:
        if evidence_id not in output:
            output.append(evidence_id)
    for fact in card["decision_facts"]:
        for evidence_id in fact["evidence_ids"]:
            if evidence_id not in output:
                output.append(evidence_id)
    return output


def _fact_changes(
    before: Mapping[str, Any] | None,
    after: Mapping[str, Any] | None,
    slot_order: Sequence[str],
) -> list[dict[str, Any]]:
    before_facts = (
        {}
        if before is None
        else {item["slot"]: item for item in before["decision_facts"]}
    )
    after_facts = (
        {}
        if after is None
        else {item["slot"]: item for item in after["decision_facts"]}
    )
    ordered_slots = list(slot_order)
    for slot in sorted(set(before_facts) | set(after_facts)):
        if slot not in ordered_slots:
            ordered_slots.append(slot)
    output: list[dict[str, Any]] = []
    for slot in ordered_slots:
        old = before_facts.get(slot)
        new = after_facts.get(slot)
        old_value = (
            None
            if old is None
            else {
                "value": old["value"],
                "evidence_ids": list(old["evidence_ids"]),
            }
        )
        new_value = (
            None
            if new is None
            else {
                "value": new["value"],
                "evidence_ids": list(new["evidence_ids"]),
            }
        )
        if old_value != new_value:
            output.append({"slot": slot, "before": old_value, "after": new_value})
    return output


def _public_diff(
    before: Mapping[str, Any] | None,
    after: Mapping[str, Any],
    evidence_ids: Sequence[str],
    slot_order: Sequence[str],
) -> dict[str, Any]:
    before_support = [] if before is None else _public_support(before)
    after_support = _public_support(after)
    before_invalidated = [] if before is None else before["invalidated_evidence_ids"]
    after_invalidated = after["invalidated_evidence_ids"]
    before_answer = None if before is None else before["current_answer"]
    after_answer = after["current_answer"]
    return {
        "answer_before": before_answer,
        "answer_after": after_answer,
        "answer_changed": before is not None and before_answer != after_answer,
        "support_ids": _ordered_ids(after_support, evidence_ids),
        "support_added_ids": _ordered_ids(
            set(after_support) - set(before_support), evidence_ids
        ),
        "support_dropped_ids": _ordered_ids(
            set(before_support) - set(after_support), evidence_ids
        ),
        "invalidated_added_ids": _ordered_ids(
            set(after_invalidated) - set(before_invalidated), evidence_ids
        ),
        "invalidated_dropped_ids": _ordered_ids(
            set(before_invalidated) - set(after_invalidated), evidence_ids
        ),
        "decision_fact_changes": _fact_changes(before, after, slot_order),
    }


def _normalize_usage(value: Any) -> dict[str, Any]:
    usage = _mapping(value, "receipt usage")
    output: dict[str, Any] = {}
    for name in USAGE_FIELDS:
        if name == "exact_provider_tokens":
            exact = usage.get(name)
            if not isinstance(exact, bool):
                raise ValueError("usage exact_provider_tokens must be boolean")
            output[name] = exact
        else:
            output[name] = _nonnegative_int_or_none(usage.get(name), f"usage {name}")
    total = output["total_tokens"]
    input_tokens = output["input_tokens"]
    output_tokens = output["output_tokens"]
    if (
        total is not None
        and input_tokens is not None
        and output_tokens is not None
        and total != input_tokens + output_tokens
    ):
        raise ValueError("receipt total_tokens did not equal input plus output")
    return output


def _normalize_call(value: Any) -> dict[str, Any]:
    receipt = _mapping(value, "call receipt")
    metadata = _mapping(receipt.get("metadata", {}), "receipt metadata")
    latency = _nonnegative_number_or_none(receipt.get("latency_ms"), "latency_ms")
    if latency is None:
        raise ValueError("receipt latency_ms must be available")
    return {
        "status": metadata.get("status"),
        "attempt_outcome": metadata.get("attempt_outcome"),
        "failure_type": metadata.get("failure_type"),
        "provider": receipt.get("provider"),
        "requested_model": receipt.get("requested_model"),
        "returned_model": receipt.get("returned_model"),
        "service_tier": metadata.get("service_tier"),
        "max_output_tokens": _nonnegative_int_or_none(
            metadata.get("max_output_tokens"), "max_output_tokens"
        ),
        "retry_count": _nonnegative_int_or_none(
            metadata.get("retry_count"), "retry_count"
        ),
        "refusal_count": _nonnegative_int_or_none(
            metadata.get("refusal_count"), "refusal_count"
        ),
        "logical_calls": _nonnegative_int_or_none(
            receipt.get("logical_calls"), "receipt logical_calls"
        ),
        "api_calls": _nonnegative_int_or_none(
            receipt.get("api_calls"), "receipt api_calls"
        ),
        "latency_ms": latency,
        "usage": _normalize_usage(receipt.get("usage")),
        "audit": {
            "request_fingerprint": receipt.get("request_fingerprint"),
            "prompt_fingerprint": receipt.get("prompt_fingerprint"),
            "response_id_sha256": metadata.get("response_id_sha256"),
        },
    }


def _presented_raw_ids(
    arm: str,
    record: Mapping[str, Any],
    sequence_offset: int,
    evidence_ids: Sequence[str],
) -> tuple[list[str], str]:
    if "presented_raw_evidence_ids" in record:
        values = _string_list(
            record["presented_raw_evidence_ids"], "presented_raw_evidence_ids"
        )
        if not set(values) <= set(evidence_ids):
            raise ValueError("presented raw evidence escaped the case")
        return values, "stored_call_record"
    if "retained_raw_evidence_ids" in record:
        retained = _string_list(
            record["retained_raw_evidence_ids"], "retained_raw_evidence_ids"
        )
        current = record.get("current_evidence_id")
        if current is None:
            current = evidence_ids[sequence_offset]
        current = _string(current, "current_evidence_id")
        values = [*retained]
        if current not in values:
            values.append(current)
        if not set(values) <= set(evidence_ids):
            raise ValueError("retained/current raw evidence escaped the case")
        return values, "derived_from_stored_retained_and_current"
    if arm in DIRECT_ARMS:
        return list(evidence_ids), "derived_from_locked_arm_contract"
    if arm == FULL_RESTART:
        current = record.get("current_evidence_id")
        if current is None:
            current = evidence_ids[sequence_offset]
        current = _string(current, "current_evidence_id")
        if current not in evidence_ids:
            raise ValueError("current evidence escaped the case")
        return [current], "derived_from_locked_arm_contract"
    if arm == STAGED_CUMULATIVE_RAW:
        current = record.get("current_evidence_id")
        if current is not None:
            current = _string(current, "current_evidence_id")
            if current not in evidence_ids:
                raise ValueError("current evidence escaped the case")
            end = evidence_ids.index(current) + 1
        else:
            end = sequence_offset + 1
        return list(evidence_ids[:end]), "derived_from_locked_arm_contract"
    raise ValueError(f"unknown arm: {arm}")


def _normalize_timeline(
    arm: str,
    arm_value: Mapping[str, Any],
    evidence_ids: Sequence[str],
    slot_order: Sequence[str],
) -> list[dict[str, Any]]:
    records = [
        _mapping(item, "call record")
        for item in _list(arm_value.get("call_records", []), "call_records")
    ]
    records.sort(key=lambda item: int(item.get("sequence_offset", -1)))
    offsets = [item.get("sequence_offset") for item in records]
    if offsets != list(range(len(records))):
        raise ValueError("call record sequence offsets must be contiguous from zero")
    output: list[dict[str, Any]] = []
    previous: Mapping[str, Any] | None = None
    for record in records:
        offset = int(record["sequence_offset"])
        card = _normalize_card(record.get("card"), evidence_ids)
        presented, presented_source = _presented_raw_ids(
            arm, record, offset, evidence_ids
        )
        current_evidence = record.get("current_evidence_id")
        if current_evidence is not None:
            current_evidence = _string(current_evidence, "current_evidence_id")
        envelope_delivered = record.get(
            "revision_envelope_delivered",
            record.get("revision_context_present", arm != DIRECT_NO_REVISION),
        )
        previous_delivered = record.get(
            "previous_public_card_delivered", arm in STAGED_ARMS and offset > 0
        )
        if not isinstance(envelope_delivered, bool) or not isinstance(
            previous_delivered, bool
        ):
            raise ValueError("call input-delivery flags must be boolean")
        allowed_value = record.get("allowed_evidence_ids")
        allowed_evidence_ids = (
            None
            if allowed_value is None
            else _string_list(allowed_value, "allowed_evidence_ids")
        )
        if allowed_evidence_ids is not None and not set(allowed_evidence_ids) <= set(
            evidence_ids
        ):
            raise ValueError("allowed evidence roster escaped the case")
        output.append(
            {
                "sequence_offset": offset,
                "phase": record.get("phase"),
                "current_evidence_id": current_evidence,
                "presented_raw_evidence_ids": presented,
                "presented_raw_evidence_ids_source": presented_source,
                "allowed_evidence_ids": allowed_evidence_ids,
                "allowed_evidence_ids_source": (
                    None if allowed_evidence_ids is None else "stored_call_record"
                ),
                "revision_envelope_delivered": envelope_delivered,
                "previous_public_card_delivered": previous_delivered,
                "public_card": card,
                "public_diff": _public_diff(previous, card, evidence_ids, slot_order),
                "call": _normalize_call(record.get("receipt")),
            }
        )
        previous = card
    return output


def _normalize_grade(value: Any, evidence_ids: Sequence[str]) -> dict[str, Any]:
    grade = _mapping(value, "arm grade")
    checks_value = grade.get("checks")
    checks = (
        None if checks_value is None else dict(_mapping(checks_value, "grade checks"))
    )
    available = grade.get("available", checks is not None)
    if not isinstance(available, bool):
        raise ValueError("grade available must be boolean")
    machine_success = grade.get("machine_success")
    evidence_consistent = grade.get("evidence_consistent")
    primary_endpoint_assessed = grade.get("primary_endpoint_assessed", available)
    if not isinstance(primary_endpoint_assessed, bool):
        raise ValueError("grade primary_endpoint_assessed must be boolean")
    for name, boolean in (
        ("machine_success", machine_success),
        ("evidence_consistent", evidence_consistent),
    ):
        if boolean is not None and not isinstance(boolean, bool):
            raise ValueError(f"grade {name} must be boolean or null")
    if checks is not None and any(
        not isinstance(item, bool) for item in checks.values()
    ):
        raise ValueError("grade checks must contain only booleans")
    precision = grade.get("citation_precision")
    recall = grade.get("citation_recall")
    for name, number in (
        ("citation_precision", precision),
        ("citation_recall", recall),
    ):
        if number is not None and (
            isinstance(number, bool)
            or not isinstance(number, (int, float))
            or not math.isfinite(float(number))
            or not 0.0 <= number <= 1.0
        ):
            raise ValueError(f"grade {name} must be in [0, 1] or null")
    output = {
        "available": available,
        "primary_endpoint_assessed": primary_endpoint_assessed,
        "machine_success": machine_success,
        "evidence_consistent": evidence_consistent,
        "checks": checks if available else None,
        "citation_precision": precision if available else None,
        "citation_recall": recall if available else None,
    }
    for name in (
        "support_evidence_ids",
        "missing_required_evidence_ids",
        "unexpected_support_evidence_ids",
    ):
        values = _string_list(grade.get(name, []), f"grade {name}")
        if not set(values) <= set(evidence_ids):
            raise ValueError(f"grade {name} escaped the case")
        output[name] = _ordered_ids(values, evidence_ids)
    return output


def _normalize_cost(value: Any) -> dict[str, Any]:
    accounting = _mapping(value, "arm accounting")
    output: dict[str, Any] = {}
    for name in COST_FIELDS:
        if name == "exact_provider_tokens":
            exact = accounting.get(name)
            if not isinstance(exact, bool):
                raise ValueError("accounting exact_provider_tokens must be boolean")
            output[name] = exact
        elif name == "latency_ms":
            output[name] = _nonnegative_number_or_none(
                accounting.get(name), "accounting latency_ms"
            )
        else:
            output[name] = _nonnegative_int_or_none(
                accounting.get(name), f"accounting {name}"
            )
    total = output["total_tokens"]
    input_tokens = output["input_tokens"]
    output_tokens = output["output_tokens"]
    if (
        total is not None
        and input_tokens is not None
        and output_tokens is not None
        and total != input_tokens + output_tokens
    ):
        raise ValueError("accounting total_tokens did not equal input plus output")
    return output


def _normalize_arm(
    arm: str,
    source_arm: str,
    value: Any,
    evidence_ids: Sequence[str],
    slot_order: Sequence[str],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    arm_value = _mapping(value, f"arm {source_arm}")
    if arm_value.get("arm") != source_arm:
        raise ValueError(f"arm payload name mismatch: {source_arm}")
    timeline = _normalize_timeline(arm, arm_value, evidence_ids, slot_order)
    final_value = arm_value.get("final_card")
    final_card = (
        None if final_value is None else _normalize_card(final_value, evidence_ids)
    )
    status = arm_value.get("status")
    if status not in {"completed", "failed"}:
        raise ValueError(f"{arm} status must be completed or failed")
    if status == "completed":
        if final_card is None:
            raise ValueError(f"{arm} completed without a final card")
        if not timeline or final_card != timeline[-1]["public_card"]:
            raise ValueError(f"{arm} final card did not match its final call record")
    elif final_card is not None:
        raise ValueError(f"{arm} failed arm unexpectedly exposed a final card")
    grade = _normalize_grade(arm_value.get("grade", {}), evidence_ids)
    if status == "failed" and grade["available"]:
        raise ValueError(f"{arm} failed arm unexpectedly exposed an available grade")
    primary_endpoint_assessed = arm_value.get(
        "primary_endpoint_assessed", status == "completed"
    )
    if not isinstance(primary_endpoint_assessed, bool):
        raise ValueError(f"{arm} primary_endpoint_assessed must be boolean")
    if grade["primary_endpoint_assessed"] != primary_endpoint_assessed:
        raise ValueError(f"{arm} arm/grade endpoint assessment drifted")
    terminal_outcome = arm_value.get(
        "terminal_outcome",
        "accepted_output" if status == "completed" else "incomplete_error",
    )
    if not isinstance(terminal_outcome, str) or not terminal_outcome:
        raise ValueError(f"{arm} terminal_outcome must be a nonempty string")
    if status == "completed" and terminal_outcome != "accepted_output":
        raise ValueError(f"{arm} completed with a non-output terminal outcome")
    if terminal_outcome == "terminal_local_contract_rejection" and (
        status != "failed" or not primary_endpoint_assessed
    ):
        raise ValueError(f"{arm} terminal strict failure contract drifted")
    if final_card is not None:
        final_support = _ordered_ids(_public_support(final_card), evidence_ids)
        if grade["available"] and grade["support_evidence_ids"] != final_support:
            raise ValueError(f"{arm} grade support did not match its final public card")
    final_answer = None if final_card is None else final_card["current_answer"]
    cost = _normalize_cost(arm_value.get("accounting"))
    expected_api_calls = _nonnegative_int_or_none(
        arm_value.get("expected_api_calls"), "expected_api_calls"
    )
    if status == "completed":
        if expected_api_calls != len(timeline):
            raise ValueError(f"{arm} completed timeline length drifted")
        if cost["logical_calls"] != expected_api_calls:
            raise ValueError(f"{arm} completed logical-call accounting drifted")
        for name in ("logical_calls", "api_calls"):
            call_sum = sum(item["call"][name] for item in timeline)
            if cost[name] != call_sum:
                raise ValueError(f"{arm} {name} did not match timeline receipts")
        latency_sum = sum(item["call"]["latency_ms"] for item in timeline)
        if cost["latency_ms"] is None or not math.isclose(
            float(cost["latency_ms"]), float(latency_sum), rel_tol=0.0, abs_tol=1e-9
        ):
            raise ValueError(f"{arm} latency did not match timeline receipts")
        if cost["exact_provider_tokens"]:
            for name in (
                "input_tokens",
                "output_tokens",
                "total_tokens",
                "cached_input_tokens",
                "cache_write_tokens",
                "reasoning_tokens",
            ):
                call_sum = sum(item["call"]["usage"][name] for item in timeline)
                if cost[name] != call_sum:
                    raise ValueError(f"{arm} {name} did not match timeline receipts")
    return {
        "arm": arm,
        "source_arm": source_arm,
        "status": status,
        "failure_category": arm_value.get("failure_category"),
        "failure_reason_code": arm_value.get("failure_reason_code"),
        "terminal_outcome": terminal_outcome,
        "primary_endpoint_assessed": primary_endpoint_assessed,
        "configured_output_token_ceiling": _nonnegative_int_or_none(
            arm_value.get("configured_output_token_ceiling"),
            "configured_output_token_ceiling",
        ),
        "expected_api_calls": expected_api_calls,
        "timeline": timeline,
        "outcome": {
            "final_checkpoint_id": (
                None if final_card is None else final_card["checkpoint_id"]
            ),
            "final_answer": final_answer,
            **grade,
        },
        "cost": cost,
    }, final_card


def _outcome_relation(reference: Any, candidate: Any) -> str:
    if not isinstance(reference, bool) or not isinstance(candidate, bool):
        return "incomplete"
    if reference and candidate:
        return "both_pass"
    if reference:
        return "reference_only"
    if candidate:
        return "candidate_only"
    return "neither_pass"


def _cost_comparison(
    reference: Mapping[str, Any], candidate: Mapping[str, Any]
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for name in DELTA_FIELDS:
        old = reference.get(name)
        new = candidate.get(name)
        if (
            isinstance(old, (int, float))
            and not isinstance(old, bool)
            and isinstance(new, (int, float))
            and not isinstance(new, bool)
        ):
            output[name] = {
                "reference": old,
                "candidate": new,
                "candidate_minus_reference": new - old,
                "candidate_over_reference": None if old == 0 else new / old,
            }
        else:
            output[name] = {
                "reference": old,
                "candidate": new,
                "candidate_minus_reference": None,
                "candidate_over_reference": None,
            }
    return output


def _run_contrasts(
    arms: Mapping[str, Mapping[str, Any]],
    final_cards: Mapping[str, Mapping[str, Any] | None],
    evidence_ids: Sequence[str],
    slot_order: Sequence[str],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for definition in CONTRAST_DEFINITIONS:
        reference_name = definition["reference_arm"]
        candidate_name = definition["candidate_arm"]
        missing = [
            name for name in (reference_name, candidate_name) if name not in arms
        ]
        if missing:
            output.append(
                {
                    **definition,
                    "available": False,
                    "missing_arms": missing,
                }
            )
            continue
        reference = arms[reference_name]
        candidate = arms[candidate_name]
        reference_outcome = reference["outcome"]
        candidate_outcome = candidate["outcome"]
        reference_support = reference_outcome["support_evidence_ids"]
        candidate_support = candidate_outcome["support_evidence_ids"]
        reference_card = final_cards[reference_name]
        candidate_card = final_cards[candidate_name]
        output.append(
            {
                **definition,
                "available": True,
                "outcome_relation": _outcome_relation(
                    (
                        reference_outcome["machine_success"]
                        if reference_outcome["primary_endpoint_assessed"]
                        else None
                    ),
                    (
                        candidate_outcome["machine_success"]
                        if candidate_outcome["primary_endpoint_assessed"]
                        else None
                    ),
                ),
                "primary_endpoints_assessed": bool(
                    reference_outcome["primary_endpoint_assessed"]
                    and candidate_outcome["primary_endpoint_assessed"]
                ),
                "public_output_diff_available": bool(
                    reference_card is not None and candidate_card is not None
                ),
                "final_answer": {
                    "reference": reference_outcome["final_answer"],
                    "candidate": candidate_outcome["final_answer"],
                    "equal": (
                        reference_outcome["final_answer"]
                        == candidate_outcome["final_answer"]
                    ),
                },
                "public_support_diff": {
                    "reference_only_ids": _ordered_ids(
                        set(reference_support) - set(candidate_support), evidence_ids
                    ),
                    "shared_ids": _ordered_ids(
                        set(reference_support) & set(candidate_support), evidence_ids
                    ),
                    "candidate_only_ids": _ordered_ids(
                        set(candidate_support) - set(reference_support), evidence_ids
                    ),
                },
                "decision_fact_changes": _fact_changes(
                    reference_card, candidate_card, slot_order
                ),
                "configured_output_token_ceiling_equal": (
                    reference["configured_output_token_ceiling"]
                    == candidate["configured_output_token_ceiling"]
                ),
                "cost": _cost_comparison(reference["cost"], candidate["cost"]),
            }
        )
    return output


def _normalize_run(
    value: Any, expected_source_arm_set: frozenset[str]
) -> dict[str, Any]:
    run = _mapping(value, "run")
    run_id = _string(run.get("run_id"), "run_id")
    case = _mapping(run.get("case"), f"{run_id} case")
    case_id = _string(run.get("case_id"), "case_id")
    family = _string(run.get("family"), "family")
    if case.get("case_id") != case_id or case.get("family") != family:
        raise ValueError(f"{run_id}: embedded case identity drifted")
    trial_index = _nonnegative_int_or_none(run.get("trial_index"), "trial_index")
    run_position = _nonnegative_int_or_none(run.get("run_position"), "run_position")
    if trial_index is None or run_position is None:
        raise ValueError(f"{run_id}: trial and run position must be available")
    evidence, evidence_ids = _case_evidence(run)
    decision_slots = [
        dict(_mapping(item, "decision slot"))
        for item in _list(case.get("decision_slots"), "decision_slots")
    ]
    slot_order = [
        _string(item.get("slot_id"), "decision slot_id") for item in decision_slots
    ]
    if len(slot_order) != len(set(slot_order)):
        raise ValueError(f"{run_id}: decision slot IDs must be unique")

    raw_arms = _mapping(run.get("arms"), f"{run_id} arms")
    if frozenset(raw_arms) != expected_source_arm_set:
        raise ValueError(f"{run_id}: arm set drifted within the bundle")
    source_arm_order = _string_list(run.get("arm_order"), f"{run_id} arm_order")
    if set(source_arm_order) != expected_source_arm_set:
        raise ValueError(f"{run_id}: arm_order did not cover every arm exactly once")
    arm_order = [ARM_ALIASES[source_arm] for source_arm in source_arm_order]
    if len(arm_order) != len(set(arm_order)):
        raise ValueError(f"{run_id}: source arm aliases collided")

    arms: dict[str, dict[str, Any]] = {}
    final_cards: dict[str, dict[str, Any] | None] = {}
    for source_arm, arm in zip(source_arm_order, arm_order, strict=True):
        arms[arm], final_cards[arm] = _normalize_arm(
            arm, source_arm, raw_arms[source_arm], evidence_ids, slot_order
        )

    envelope = dict(
        _mapping(
            run.get("revision_envelope", run.get("fixed_revision_envelope", {})),
            "revision envelope",
        )
    )
    all_outputs_completed = run.get(
        "all_outputs_completed",
        all(item["status"] == "completed" for item in arms.values()),
    )
    primary_endpoint_assessed = run.get(
        "primary_endpoint_assessed", bool(run.get("complete"))
    )
    if not isinstance(all_outputs_completed, bool) or not isinstance(
        primary_endpoint_assessed, bool
    ):
        raise ValueError(f"{run_id}: run completion flags must be boolean")
    if all_outputs_completed != all(
        item["status"] == "completed" for item in arms.values()
    ):
        raise ValueError(f"{run_id}: all_outputs_completed drifted from arm status")
    if primary_endpoint_assessed != all(
        item["primary_endpoint_assessed"] for item in arms.values()
    ):
        raise ValueError(f"{run_id}: endpoint assessment drifted from arm status")
    return {
        "run_id": run_id,
        "trial_index": trial_index,
        "run_position": run_position,
        "case_id": case_id,
        "family": family,
        "arm_order": arm_order,
        "source_arm_order": source_arm_order,
        "complete": bool(run.get("complete")),
        "primary_endpoint_assessed": primary_endpoint_assessed,
        "all_outputs_completed": all_outputs_completed,
        "case": {
            "question": _string(case.get("question"), "case question"),
            "answer_choices": _string_list(
                case.get("answer_choices"), "answer_choices"
            ),
            "decision_slots": decision_slots,
            "evidence": evidence,
            "revision_envelope": envelope,
        },
        "arms": [arms[arm] for arm in arm_order],
        "contrasts": _run_contrasts(arms, final_cards, evidence_ids, slot_order),
        "audit": {
            "case_input_fingerprint": run.get("case_input_fingerprint"),
            "revision_envelope_fingerprint": run.get(
                "revision_envelope_fingerprint",
                run.get("fixed_revision_envelope_fingerprint"),
            ),
            "pre_execution_fingerprint": run.get("pre_execution_fingerprint"),
        },
    }


def _arm_map(run: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {item["arm"]: item for item in run["arms"]}


def _sum_exact_cost(values: Sequence[Mapping[str, Any]], name: str) -> int | None:
    if not values or not all(item["exact_provider_tokens"] for item in values):
        return None
    parts = [item.get(name) for item in values]
    if not all(isinstance(item, int) and not isinstance(item, bool) for item in parts):
        return None
    return sum(parts)


def _stable_case_rows(
    runs: Sequence[Mapping[str, Any]],
    arms: Sequence[str],
    declared_trials: int,
) -> list[dict[str, Any]]:
    by_case: defaultdict[str, list[Mapping[str, Any]]] = defaultdict(list)
    case_order: list[str] = []
    for run in runs:
        case_id = run["case_id"]
        if case_id not in by_case:
            case_order.append(case_id)
        by_case[case_id].append(run)
    threshold = declared_trials // 2 + 1
    output: list[dict[str, Any]] = []
    for case_id in case_order:
        case_runs = sorted(by_case[case_id], key=lambda item: item["trial_index"])
        row: dict[str, Any] = {
            "case_id": case_id,
            "family": case_runs[0]["family"],
            "declared_trials": declared_trials,
            "stable_pass_threshold": threshold,
            "arms": {},
        }
        for arm in arms:
            arm_values = [_arm_map(run)[arm] for run in case_runs]
            successes = sum(
                item["outcome"]["machine_success"] is True for item in arm_values
            )
            completed = sum(item["status"] == "completed" for item in arm_values)
            assessed = sum(
                item["outcome"]["primary_endpoint_assessed"] is True
                for item in arm_values
            )
            row["arms"][arm] = {
                "completed_trials": completed,
                "assessed_trials": assessed,
                "successes": successes,
                "stable_pass": (
                    successes >= threshold if assessed == declared_trials else None
                ),
            }
        output.append(row)
    return output


def _classify_cause(stable_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    missing_arms = [
        arm
        for arm in CANONICAL_ARM_ORDER
        if not stable_rows or arm not in stable_rows[0]["arms"]
    ]
    if missing_arms:
        return {
            "status": "not_available_missing_control_arms",
            "decision_unit": "case_stable_pass",
            "rule_version": "direct-full-cause-matrix-v0.1",
            "missing_arms": missing_arms,
        }
    if any(
        value["stable_pass"] is None
        for row in stable_rows
        for value in row["arms"].values()
    ):
        return {
            "status": "incomplete_locked_trials",
            "decision_unit": "case_stable_pass",
            "rule_version": "direct-full-cause-matrix-v0.1",
            "missing_arms": [],
        }

    def cases_where(left: str, right: str) -> list[str]:
        return [
            row["case_id"]
            for row in stable_rows
            if row["arms"][left]["stable_pass"] is True
            and row["arms"][right]["stable_pass"] is False
        ]

    cumulative_rescues = cases_where(STAGED_CUMULATIVE_RAW, FULL_RESTART)
    cumulative_regressions = cases_where(FULL_RESTART, STAGED_CUMULATIVE_RAW)
    direct_only_vs_cumulative = cases_where(DIRECT_FIXED, STAGED_CUMULATIVE_RAW)
    cumulative_only_vs_direct = cases_where(STAGED_CUMULATIVE_RAW, DIRECT_FIXED)
    fixed_only_vs_no_revision = cases_where(DIRECT_FIXED, DIRECT_NO_REVISION)
    no_revision_only_vs_fixed = cases_where(DIRECT_NO_REVISION, DIRECT_FIXED)

    if cumulative_regressions or cumulative_only_vs_direct:
        cumulative_class = "mixed_or_regressed"
    elif not cumulative_rescues:
        cumulative_class = "no_recovery_on_primary_gate"
    elif not direct_only_vs_cumulative:
        cumulative_class = "full_recovery_to_direct_reference"
    else:
        cumulative_class = "partial_recovery_with_staged_residual"

    if fixed_only_vs_no_revision and no_revision_only_vs_fixed:
        envelope_class = "mixed_by_case"
    elif fixed_only_vs_no_revision:
        envelope_class = "fixed_envelope_helpful_on_primary_gate"
    elif no_revision_only_vs_fixed:
        envelope_class = "fixed_envelope_harmful_on_primary_gate"
    else:
        envelope_class = "parity_no_detected_primary_effect"

    return {
        "status": "classified_locked_controls",
        "decision_unit": "case_stable_pass",
        "rule_version": "direct-full-cause-matrix-v0.1",
        "cumulative_raw_class": cumulative_class,
        "revision_envelope_class": envelope_class,
        "matrix_cell": f"{cumulative_class}__{envelope_class}",
        "case_directions": {
            "cumulative_rescues_vs_full": cumulative_rescues,
            "full_regressions_vs_cumulative": cumulative_regressions,
            "direct_only_vs_cumulative": direct_only_vs_cumulative,
            "cumulative_only_vs_direct": cumulative_only_vs_direct,
            "fixed_only_vs_no_revision": fixed_only_vs_no_revision,
            "no_revision_only_vs_fixed": no_revision_only_vs_fixed,
        },
    }


def _summarize(
    runs: Sequence[Mapping[str, Any]], arms: Sequence[str], declared_trials: int
) -> dict[str, Any]:
    stable_rows = _stable_case_rows(runs, arms, declared_trials)
    arm_summary: list[dict[str, Any]] = []
    for arm in arms:
        values = [_arm_map(run)[arm] for run in runs]
        completed = [item for item in values if item["status"] == "completed"]
        grades = [item["outcome"] for item in completed]
        costs = [item["cost"] for item in values]
        precisions = [
            item["citation_precision"]
            for item in grades
            if isinstance(item["citation_precision"], (int, float))
        ]
        recalls = [
            item["citation_recall"]
            for item in grades
            if isinstance(item["citation_recall"], (int, float))
        ]
        latencies = [
            item["latency_ms"]
            for item in costs
            if isinstance(item["latency_ms"], (int, float))
        ]
        arm_summary.append(
            {
                "arm": arm,
                "attempted_runs": len(values),
                "completed_outputs": len(completed),
                "machine_successes": sum(
                    item["machine_success"] is True for item in grades
                ),
                "answer_exact": sum(
                    item["checks"] is not None
                    and item["checks"].get("answer_exact") is True
                    for item in grades
                ),
                "evidence_consistent": sum(
                    item["evidence_consistent"] is True for item in grades
                ),
                "mean_citation_precision": (
                    None if not precisions else statistics.mean(precisions)
                ),
                "mean_citation_recall": (
                    None if not recalls else statistics.mean(recalls)
                ),
                "stable_pass_cases": sum(
                    row["arms"][arm]["stable_pass"] is True for row in stable_rows
                ),
                "cost": {
                    "api_calls": sum(
                        item["api_calls"]
                        for item in costs
                        if item["api_calls"] is not None
                    ),
                    "input_tokens": _sum_exact_cost(costs, "input_tokens"),
                    "output_tokens": _sum_exact_cost(costs, "output_tokens"),
                    "total_tokens": _sum_exact_cost(costs, "total_tokens"),
                    "reasoning_tokens": _sum_exact_cost(costs, "reasoning_tokens"),
                    "sum_latency_ms": None if not latencies else sum(latencies),
                    "median_latency_ms": (
                        None if not latencies else statistics.median(latencies)
                    ),
                },
            }
        )
    return {
        "arms": arm_summary,
        "stable_cases": stable_rows,
        "cause_decision": _classify_cause(stable_rows),
    }


def _normalize_provider_provenance(value: Any) -> dict[str, Any]:
    source = _mapping(value, "provider_provenance")
    output: dict[str, Any] = {}
    for source_arm, provenance_value in source.items():
        if source_arm not in ARM_ALIASES:
            raise ValueError(f"unknown provider-provenance arm: {source_arm}")
        arm = ARM_ALIASES[source_arm]
        if arm in output:
            raise ValueError(f"provider-provenance arm alias collision: {arm}")
        output[arm] = {
            "source_arm": source_arm,
            **dict(_mapping(provenance_value, f"provider provenance {source_arm}")),
        }
    return output


def build_snapshot(
    results: Mapping[str, Any], manifest_validation: Mapping[str, Any]
) -> dict[str, Any]:
    raw_runs = _list(results.get("runs"), "results runs")
    if not raw_runs:
        raise ValueError("results must contain at least one run")
    first_source_arms = frozenset(_mapping(raw_runs[0].get("arms"), "first run arms"))
    if first_source_arms not in (TWO_ARM_SET, FOUR_ARM_SET, FOUR_ARM_RUNNER_SET):
        raise ValueError(
            "bundle must contain the locked two-arm or planned four-arm arm set"
        )
    canonical_arm_set = frozenset(ARM_ALIASES[item] for item in first_source_arms)
    arms = [arm for arm in CANONICAL_ARM_ORDER if arm in canonical_arm_set]
    normalized_runs = [_normalize_run(item, first_source_arms) for item in raw_runs]
    run_ids = [item["run_id"] for item in normalized_runs]
    if len(run_ids) != len(set(run_ids)):
        raise ValueError("run IDs must be unique")
    case_trials = [(item["case_id"], item["trial_index"]) for item in normalized_runs]
    if len(case_trials) != len(set(case_trials)):
        raise ValueError("case/trial pairs must be unique")
    for trial_index in sorted({item["trial_index"] for item in normalized_runs}):
        positions = sorted(
            item["run_position"]
            for item in normalized_runs
            if item["trial_index"] == trial_index
        )
        if positions != list(range(len(positions))):
            raise ValueError("run positions must be contiguous within each trial")
    normalized_runs.sort(
        key=lambda item: (
            item["trial_index"],
            item["run_position"],
            item["case_id"],
            item["run_id"],
        )
    )
    declared_trials = _nonnegative_int_or_none(results.get("trials"), "trials")
    if declared_trials is None or declared_trials < 1:
        raise ValueError("results trials must be at least one")
    observed_case_count = len({item["case_id"] for item in normalized_runs})
    if results.get("case_count") != observed_case_count:
        raise ValueError("results case_count did not match normalized runs")
    return {
        "schema_version": INSPECTOR_SCHEMA_VERSION,
        "artifact": {
            "source_schema_version": results.get("schema_version"),
            "mode": results.get("mode"),
            "status": results.get("status"),
            "promotion_eligible": results.get("promotion_eligible"),
            "execution_complete": results.get("execution_complete"),
            "all_outputs_completed": results.get(
                "all_outputs_completed", results.get("execution_complete")
            ),
            "case_count": results.get("case_count"),
            "trials": declared_trials,
            "run_count": len(normalized_runs),
            "arm_set": arms,
            "source_arm_set": sorted(first_source_arms),
            "claim_boundary": list(results.get("claim_boundary", [])),
            "provider_provenance": _normalize_provider_provenance(
                results.get("provider_provenance", {})
            ),
            "manifest_validation": dict(manifest_validation),
        },
        "field_semantics": dict(FIELD_SEMANTICS),
        "contrast_definitions": [
            {
                **definition,
                "available": {definition["reference_arm"], definition["candidate_arm"]}
                <= canonical_arm_set,
            }
            for definition in CONTRAST_DEFINITIONS
        ],
        "summary": _summarize(normalized_runs, arms, declared_trials),
        "runs": normalized_runs,
    }


def export_bundle(bundle: Path) -> dict[str, Any]:
    results, _manifest, validation = _load_bundle(bundle)
    return build_snapshot(results, validation)


def _write_snapshot(path: Path, snapshot: Mapping[str, Any], *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"refusing to overwrite existing snapshot: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical_json(snapshot) + "\n", encoding="utf-8")


def _expect_value_error(action: Any) -> None:
    try:
        action()
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def _synthetic_four_arm_results(results: Mapping[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(results)
    value["schema_version"] = "ebrt-direct-full-calibration-v0.4.1-test"
    provenance = value.setdefault("provider_provenance", {})
    direct_provenance = provenance.pop(DIRECT_FIXED)
    full_provenance = provenance.pop(FULL_RESTART)
    provenance[DIRECT_FIXED_RERUN] = copy.deepcopy(direct_provenance)
    provenance[DIRECT_NO_REVISION] = copy.deepcopy(direct_provenance)
    provenance[STAGED_CARD_ONLY_RERUN] = copy.deepcopy(full_provenance)
    provenance[STAGED_CUMULATIVE_RAW] = copy.deepcopy(full_provenance)
    for run in value["runs"]:
        run["fixed_revision_envelope"] = run.pop("revision_envelope")
        run["fixed_revision_envelope_fingerprint"] = run.pop(
            "revision_envelope_fingerprint"
        )
        direct_anchor = run["arms"].pop(DIRECT_FIXED)
        full_anchor = run["arms"].pop(FULL_RESTART)
        direct_rerun = copy.deepcopy(direct_anchor)
        direct_rerun["arm"] = DIRECT_FIXED_RERUN
        direct_rerun["call_records"][0]["revision_context_present"] = True
        direct = copy.deepcopy(direct_anchor)
        direct["arm"] = DIRECT_NO_REVISION
        direct["call_records"][0]["revision_context_present"] = False
        card_only = copy.deepcopy(full_anchor)
        card_only["arm"] = STAGED_CARD_ONLY_RERUN
        cumulative = copy.deepcopy(full_anchor)
        cumulative["arm"] = STAGED_CUMULATIVE_RAW
        for index, record in enumerate(card_only["call_records"]):
            record["retained_raw_evidence_ids"] = []
            record["allowed_evidence_ids"] = list(record["card"]["evidence_ids"])
        evidence_ids = [
            *(item["evidence_id"] for item in run["case"]["initial_evidence"]),
            run["case"]["late_evidence"]["evidence_id"],
        ]
        for index, record in enumerate(cumulative["call_records"]):
            record["retained_raw_evidence_ids"] = evidence_ids[:index]
            record["allowed_evidence_ids"] = evidence_ids[: index + 1]
        run["arms"][DIRECT_FIXED_RERUN] = direct_rerun
        run["arms"][DIRECT_NO_REVISION] = direct
        run["arms"][STAGED_CARD_ONLY_RERUN] = card_only
        run["arms"][STAGED_CUMULATIVE_RAW] = cumulative
        run["arm_order"] = [
            DIRECT_FIXED_RERUN,
            DIRECT_NO_REVISION,
            STAGED_CARD_ONLY_RERUN,
            STAGED_CUMULATIVE_RAW,
        ]
    return value


def run_self_tests() -> dict[str, Any]:
    results, _manifest, validation = _load_bundle(DEFAULT_BUNDLE)
    snapshot = build_snapshot(results, validation)
    if snapshot["schema_version"] != INSPECTOR_SCHEMA_VERSION:
        raise AssertionError("inspector schema version drift")
    if len(snapshot["runs"]) != 30:
        raise AssertionError("frozen two-arm run count drift")
    summary = {item["arm"]: item for item in snapshot["summary"]["arms"]}
    if summary[DIRECT_FIXED]["machine_successes"] != 30:
        raise AssertionError("frozen Direct result drift")
    if summary[FULL_RESTART]["machine_successes"] != 4:
        raise AssertionError("frozen Full result drift")
    if snapshot["summary"]["cause_decision"]["status"] != (
        "not_available_missing_control_arms"
    ):
        raise AssertionError("two-arm snapshot overclaimed a causal decision")
    contrast_availability = {
        item["contrast_id"]: item["available"]
        for item in snapshot["contrast_definitions"]
    }
    if contrast_availability["direct_full_recorded_calibration"] is not True:
        raise AssertionError("two-arm recorded contrast was not available")
    if contrast_availability["raw_aperture_ablation"] is not False:
        raise AssertionError("two-arm snapshot invented an aperture control")
    if DEFAULT_OUTPUT != (
        ROOT / "inspector" / "public" / "data" / "ebrt-public-inspector-v0.1.json"
    ):
        raise AssertionError("Inspector default output path drift")
    if any(
        "repair" in definition["public_question"].lower()
        for definition in CONTRAST_DEFINITIONS
    ):
        raise AssertionError("contrast question pre-judged a repair outcome")
    first = snapshot["runs"][0]
    first_arms = _arm_map(first)
    if len(first_arms[DIRECT_FIXED]["timeline"]) != 1:
        raise AssertionError("Direct public timeline drift")
    if len(first_arms[FULL_RESTART]["timeline"]) != 6:
        raise AssertionError("Full public timeline drift")
    if (
        first_arms[FULL_RESTART]["timeline"][0]["presented_raw_evidence_ids_source"]
        != "derived_from_locked_arm_contract"
    ):
        raise AssertionError("input-scope derivation lost its provenance label")
    if _canonical_json(snapshot) != _canonical_json(
        build_snapshot(results, validation)
    ):
        raise AssertionError("snapshot export was not deterministic")

    synthetic = _synthetic_four_arm_results(results)
    synthetic_snapshot = build_snapshot(
        synthetic,
        {
            "manifest_present": False,
            "artifact_files_verified": [],
            "source_files_verified": [],
        },
    )
    if set(synthetic_snapshot["artifact"]["arm_set"]) != FOUR_ARM_SET:
        raise AssertionError("four-arm compatibility drift")
    if set(synthetic_snapshot["artifact"]["source_arm_set"]) != FOUR_ARM_RUNNER_SET:
        raise AssertionError("four-arm runner alias compatibility drift")
    synthetic_first_arms = _arm_map(synthetic_snapshot["runs"][0])
    if synthetic_first_arms[DIRECT_FIXED]["source_arm"] != DIRECT_FIXED_RERUN:
        raise AssertionError("Direct rerun alias was not preserved")
    if synthetic_first_arms[FULL_RESTART]["source_arm"] != STAGED_CARD_ONLY_RERUN:
        raise AssertionError("card-only rerun alias was not preserved")
    if not all(
        item["available"] for item in synthetic_snapshot["contrast_definitions"]
    ):
        raise AssertionError("four-arm snapshot did not expose every contrast")
    cumulative_timeline = synthetic_first_arms[STAGED_CUMULATIVE_RAW]["timeline"]
    if cumulative_timeline[1]["presented_raw_evidence_ids_source"] != (
        "derived_from_stored_retained_and_current"
    ):
        raise AssertionError("stored cumulative-raw aperture was not preserved")
    if synthetic_snapshot["summary"]["cause_decision"]["status"] != (
        "classified_locked_controls"
    ):
        raise AssertionError("complete four-arm controls were not classified")

    incomplete = copy.deepcopy(synthetic)
    incomplete["execution_complete"] = False
    incomplete_run = incomplete["runs"][0]
    incomplete_run["complete"] = False
    failed_arm = incomplete_run["arms"][STAGED_CARD_ONLY_RERUN]
    failed_arm["status"] = "failed"
    failed_arm["failure_category"] = "local_contract_error"
    failed_arm["final_card"] = None
    failed_arm["cards"] = failed_arm["cards"][:2]
    failed_arm["call_records"] = failed_arm["call_records"][:2]
    failed_arm["grade"] = {
        "available": False,
        "machine_success": False,
        "evidence_consistent": False,
        "checks": None,
        "citation_precision": None,
        "citation_recall": None,
        "support_evidence_ids": [],
        "missing_required_evidence_ids": [],
        "unexpected_support_evidence_ids": [],
    }
    incomplete_snapshot = build_snapshot(
        incomplete,
        {
            "manifest_present": False,
            "artifact_files_verified": [],
            "source_files_verified": [],
        },
    )
    failed_normalized = _arm_map(incomplete_snapshot["runs"][0])[FULL_RESTART]
    if failed_normalized["outcome"]["available"] is not False:
        raise AssertionError("failed arm invented an available grade")
    if (
        failed_normalized["outcome"]["machine_success"] is not False
        or failed_normalized["outcome"]["primary_endpoint_assessed"] is not False
    ):
        raise AssertionError("unassessed failure lost its endpoint boundary")
    if incomplete_snapshot["summary"]["cause_decision"]["status"] != (
        "incomplete_locked_trials"
    ):
        raise AssertionError("incomplete controls were causally classified")

    terminal = copy.deepcopy(incomplete)
    terminal["execution_complete"] = True
    terminal["all_outputs_completed"] = False
    terminal_run = terminal["runs"][0]
    terminal_run["complete"] = True
    terminal_run["primary_endpoint_assessed"] = True
    terminal_run["all_outputs_completed"] = False
    terminal_arm = terminal_run["arms"][STAGED_CARD_ONLY_RERUN]
    terminal_arm["primary_endpoint_assessed"] = True
    terminal_arm["terminal_outcome"] = "terminal_local_contract_rejection"
    terminal_arm["failure_reason_code"] = "answer_choice_violation"
    terminal_arm["grade"]["primary_endpoint_assessed"] = True
    terminal_snapshot = build_snapshot(
        terminal,
        {
            "manifest_present": False,
            "artifact_files_verified": [],
            "source_files_verified": [],
        },
    )
    terminal_normalized = _arm_map(terminal_snapshot["runs"][0])[FULL_RESTART]
    if (
        terminal_normalized["outcome"]["available"] is not False
        or terminal_normalized["outcome"]["primary_endpoint_assessed"] is not True
        or terminal_normalized["outcome"]["machine_success"] is not False
        or terminal_normalized["terminal_outcome"]
        != "terminal_local_contract_rejection"
    ):
        raise AssertionError("terminal strict failure was not preserved")

    with tempfile.TemporaryDirectory() as temp_dir:
        corrupt = Path(temp_dir) / "corrupt_bundle"
        shutil.copytree(DEFAULT_BUNDLE, corrupt)
        (corrupt / "results.json").write_text(
            (corrupt / "results.json").read_text(encoding="utf-8") + " ",
            encoding="utf-8",
        )
        _expect_value_error(lambda: _load_bundle(corrupt))
        output = Path(temp_dir) / "snapshot.json"
        _write_snapshot(output, snapshot, force=False)
        round_trip = _load_json(output)
        if round_trip != snapshot:
            raise AssertionError("written snapshot did not round-trip exactly")
        try:
            _write_snapshot(output, snapshot, force=False)
        except FileExistsError:
            pass
        else:
            raise AssertionError("snapshot writer overwrote without --force")

    forbidden_keys = {
        "attention",
        "belief",
        "chain_of_thought",
        "curvature",
        "hidden_state",
        "latent_trajectory",
        "model_memory",
    }

    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            if forbidden_keys & set(value):
                raise AssertionError("snapshot introduced a hidden-state field")
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(snapshot)
    return {
        "status": "ok",
        "tests": 17,
        "two_arm_runs": len(snapshot["runs"]),
        "four_arm_compatibility": True,
        "manifest_artifact_hashes_verified": len(validation["artifact_files_verified"]),
        "manifest_source_hashes_verified": len(validation["source_files_verified"]),
        "schema_version": INSPECTOR_SCHEMA_VERSION,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "self-test",
        help="run manifest, two-arm, four-arm, and deterministic-output checks",
    )
    build = subparsers.add_parser(
        "build", help="build one deterministic public Inspector JSON snapshot"
    )
    build.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    build.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    build.add_argument(
        "--force", action="store_true", help="replace an existing output file"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "self-test":
        print(json.dumps(run_self_tests(), indent=2, sort_keys=True))
        return 0
    if args.command == "build":
        snapshot = export_bundle(args.bundle)
        _write_snapshot(args.output, snapshot, force=args.force)
        print(
            json.dumps(
                {
                    "status": "ok",
                    "schema_version": snapshot["schema_version"],
                    "output": str(args.output),
                    "runs": len(snapshot["runs"]),
                    "arms": snapshot["artifact"]["arm_set"],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
