#!/usr/bin/env python3
"""Build the deterministic, read-only EBRT v0.4.4 Workbench projection.

The builder reads only committed public benchmark artifacts.  It performs no
provider calls and projects an explicit allowlist of evidence, public Reasoning
Cards, machine grades, sanitized accounting, and diagnostic aggregates.  It
does not expose private reasoning text, hidden states, or raw provider bodies.
"""

from __future__ import annotations

import argparse
import copy
import contextlib
import hashlib
import json
import math
import os
import socket
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence


ROOT = Path(__file__).resolve().parent
LOCK_PATH = ROOT / "projection_lock_reasoning_workbench_v0_4_4.json"
BUILDER_PATH = Path(__file__).resolve()
SNAPSHOT_SCHEMA = "ebrt-reasoning-workbench-v0.4.4"
MANIFEST_SCHEMA = "ebrt-reasoning-workbench-manifest-v0.4.4"
LANE_ORDER = ("card_only_forward", "selective_replay", "full_restart")
ACCOUNTING_FIELDS = (
    "api_calls",
    "logical_calls",
    "latency_ms",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cached_input_tokens",
    "cache_write_tokens",
    "reasoning_tokens",
    "exact_provider_tokens",
)
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
LANE_LABELS = {
    "card_only_forward": "Card-only forward",
    "selective_replay": "Selective replay",
    "full_restart": "Full restart",
}
RECEIPT_FIELDS = (
    "provider",
    "requested_model",
    "returned_model",
    "status",
    "service_tier",
    "attempt_outcome",
    "retry_count",
    "refusal_count",
    "usage",
)
EXPECTED_GATES = {
    "recorded_episode_integrity_ready": True,
    "projection_integrity_ready": True,
    "provider_diagnostic_integrity_ready": True,
    "recorded_demo_ready": True,
    "live_execution_ready": False,
    "locked_reasoning_decision_ready": False,
    "reasoning_improvement_claim_ready": False,
    "promotion_eligible": False,
}


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode()).hexdigest()


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
    ).encode()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


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
    output = [_string(item, f"{label} item") for item in _list(value, label)]
    if len(output) != len(set(output)):
        raise ValueError(f"{label} must not contain duplicates")
    return output


def _bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be boolean")
    return value


def _integer(value: Any, label: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")
    return value


def _number(value: Any, label: str, *, minimum: float = 0.0) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    if not math.isfinite(float(value)) or float(value) < minimum:
        raise ValueError(f"{label} must be finite and >= {minimum}")
    return value


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"expected JSON object: {path}:{line_number}")
        output.append(value)
    return output


def _root_path(value: str, label: str) -> Path:
    relative = Path(value)
    if relative.is_absolute():
        raise ValueError(f"{label} must be relative")
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise ValueError(f"{label} escaped repository root")
    return path


def _validate_projection_allowlists(lock: Mapping[str, Any]) -> None:
    allowlist = _mapping(lock.get("projection_allowlist"), "projection allowlist")
    if tuple(allowlist.get("public_card", ())) != CARD_FIELDS:
        raise ValueError("public-card allowlist changed")
    if tuple(allowlist.get("accounting", ())) != ACCOUNTING_FIELDS:
        raise ValueError("accounting allowlist changed")
    if tuple(allowlist.get("receipt", ())) != RECEIPT_FIELDS:
        raise ValueError("sanitized receipt allowlist changed")
    if tuple(allowlist.get("receipt_usage", ())) != ACCOUNTING_FIELDS:
        raise ValueError("sanitized receipt usage allowlist changed")
    if set(allowlist) != {
        "public_card",
        "accounting",
        "receipt",
        "receipt_usage",
    }:
        raise ValueError("projection allowlist gained an unreviewed surface")


def _load_lock() -> dict[str, Any]:
    lock = _load_json(LOCK_PATH)
    if lock.get("schema_version") != (
        "ebrt-reasoning-workbench-projection-lock-v0.4.4"
    ):
        raise ValueError("unexpected projection lock schema")
    if lock.get("status") != "LOCKED_READ_ONLY_PROJECTION":
        raise ValueError("projection lock must be read-only and locked")
    _validate_projection_allowlists(lock)
    if lock.get("gates") != EXPECTED_GATES:
        raise ValueError("projection gates escaped the locked boundary")
    return lock


def _validate_pinned_file(spec: Mapping[str, Any], label: str) -> Path:
    path = _root_path(_string(spec.get("path"), f"{label} path"), label)
    expected = _string(spec.get("sha256"), f"{label} sha256")
    if not path.is_file():
        raise ValueError(f"missing pinned input: {path.relative_to(ROOT)}")
    observed = _sha256(path)
    if observed != expected:
        raise ValueError(
            f"pinned input hash mismatch: {path.relative_to(ROOT)} "
            f"expected={expected} observed={observed}"
        )
    return path


def _validate_artifact_manifest(path: Path) -> None:
    manifest = _load_json(path)
    artifact_hashes = _mapping(
        manifest.get("artifact_sha256"), f"{path} artifact_sha256"
    )
    for filename, expected_value in sorted(artifact_hashes.items()):
        expected = _string(expected_value, f"{path} artifact {filename}")
        artifact_path = (path.parent / filename).resolve()
        if not artifact_path.is_relative_to(path.parent.resolve()):
            raise ValueError(f"artifact path escaped bundle: {filename}")
        if not artifact_path.is_file() or _sha256(artifact_path) != expected:
            raise ValueError(f"artifact manifest mismatch: {artifact_path}")


def _load_inputs(lock: Mapping[str, Any]) -> dict[str, Any]:
    sources = _mapping(lock.get("sources"), "sources")
    loaded: dict[str, Any] = {}
    for source_name, source_value in sorted(sources.items()):
        source = _mapping(source_value, f"source {source_name}")
        loaded[source_name] = {}
        for role, spec_value in sorted(source.items()):
            spec = _mapping(spec_value, f"source {source_name} {role}")
            path = _validate_pinned_file(spec, f"source {source_name} {role}")
            if role in {"calls", "traces"}:
                loaded[source_name][role] = _load_jsonl(path)
            else:
                loaded[source_name][role] = _load_json(path)
            loaded[source_name][f"{role}_path"] = path
            if role == "manifest":
                _validate_artifact_manifest(path)
    for value in _list(lock.get("forbidden_paths"), "forbidden_paths"):
        forbidden = _root_path(_string(value, "forbidden path"), "forbidden path")
        if forbidden.exists():
            raise ValueError(
                f"forbidden v0.4.3 full artifact exists: {forbidden.relative_to(ROOT)}"
            )
    return loaded


def _project_fact(value: Any, evidence_ids: set[str]) -> dict[str, Any]:
    fact = _mapping(value, "decision fact")
    cited = _string_list(fact.get("evidence_ids"), "fact evidence_ids")
    if not set(cited) <= evidence_ids:
        raise ValueError("decision fact cites unknown evidence")
    return {
        "slot": _string(fact.get("slot"), "fact slot"),
        "value": _string(fact.get("value"), "fact value"),
        "evidence_ids": cited,
    }


def _project_card(value: Any, evidence_ids: set[str]) -> dict[str, Any]:
    card = _mapping(value, "public card")
    missing = set(CARD_FIELDS) - set(card)
    if missing:
        raise ValueError(f"public card omitted allowlisted fields: {sorted(missing)}")
    cited = _string_list(card.get("evidence_ids"), "card evidence_ids")
    invalidated = _string_list(
        card.get("invalidated_evidence_ids"), "card invalidated evidence IDs"
    )
    if not set(cited) <= evidence_ids or not set(invalidated) <= evidence_ids:
        raise ValueError("public card cites unknown evidence")
    stance = card.get("stance")
    confidence = card.get("confidence")
    cue = card.get("revision_cue")
    if not isinstance(stance, (int, float)) or isinstance(stance, bool):
        raise ValueError("card stance must be numeric")
    if not -1.0 <= float(stance) <= 1.0:
        raise ValueError("card stance escaped range")
    for label, value_number in (("confidence", confidence), ("revision cue", cue)):
        if (
            isinstance(value_number, bool)
            or not isinstance(value_number, (int, float))
            or not math.isfinite(float(value_number))
            or not 0.0 <= float(value_number) <= 1.0
        ):
            raise ValueError(f"card {label} escaped range")
    facts = [
        _project_fact(item, evidence_ids)
        for item in _list(card.get("decision_facts"), "decision facts")
    ]
    slots = [item["slot"] for item in facts]
    if len(slots) != len(set(slots)):
        raise ValueError("public card contains duplicate decision slots")
    return {
        "schema_version": _string(card.get("schema_version"), "card schema"),
        "checkpoint_id": _string(card.get("checkpoint_id"), "checkpoint ID"),
        "claim": _string(card.get("claim"), "card claim"),
        "topic": _string(card.get("topic"), "card topic"),
        "stance": stance,
        "confidence": confidence,
        "evidence_ids": cited,
        "current_answer": _string(card.get("current_answer"), "current answer"),
        "revision_cue": cue,
        "decision_facts": facts,
        "invalidated_evidence_ids": invalidated,
    }


def _project_accounting(value: Any) -> dict[str, Any]:
    accounting = _mapping(value, "accounting")
    output: dict[str, Any] = {}
    for name in ACCOUNTING_FIELDS:
        item = accounting.get(name)
        if name == "exact_provider_tokens":
            output[name] = _bool(item, f"accounting {name}")
        elif name == "latency_ms":
            output[name] = _number(item, f"accounting {name}")
        else:
            output[name] = _integer(item, f"accounting {name}")
    if output["total_tokens"] != (output["input_tokens"] + output["output_tokens"]):
        raise ValueError("accounting total token mismatch")
    return output


def _validate_sanitized_receipt(value: Any, label: str) -> Mapping[str, Any]:
    receipt = _mapping(value, label)
    if set(receipt) != set(RECEIPT_FIELDS) or len(receipt) != len(RECEIPT_FIELDS):
        raise ValueError(f"{label} escaped its exact allowlist")
    usage = _mapping(receipt.get("usage"), f"{label} usage")
    if set(usage) != set(ACCOUNTING_FIELDS) or len(usage) != len(ACCOUNTING_FIELDS):
        raise ValueError(f"{label} usage escaped its exact allowlist")
    return receipt


def _project_receipt(value: Any) -> dict[str, Any]:
    receipt = _mapping(value, "receipt")
    metadata = _mapping(receipt.get("metadata"), "receipt metadata")
    output = {
        "provider": _string(receipt.get("provider"), "receipt provider"),
        "requested_model": _string(receipt.get("requested_model"), "requested model"),
        "returned_model": _string(receipt.get("returned_model"), "returned model"),
        "status": _string(metadata.get("status"), "receipt status"),
        "service_tier": _string(metadata.get("service_tier"), "service tier"),
        "attempt_outcome": _string(metadata.get("attempt_outcome"), "attempt outcome"),
        "retry_count": _integer(metadata.get("retry_count"), "retry count"),
        "refusal_count": _integer(metadata.get("refusal_count"), "refusal count"),
        "usage": _project_accounting(
            {
                **_mapping(receipt.get("usage"), "receipt usage"),
                "api_calls": receipt.get("api_calls"),
                "logical_calls": receipt.get("logical_calls"),
                "latency_ms": receipt.get("latency_ms"),
            }
        ),
    }
    _validate_sanitized_receipt(output, "projected receipt")
    return output


def _support_ids(card: Mapping[str, Any]) -> list[str]:
    output: list[str] = []
    for evidence_id in card["evidence_ids"]:
        if evidence_id not in output:
            output.append(evidence_id)
    for fact in card["decision_facts"]:
        for evidence_id in fact["evidence_ids"]:
            if evidence_id not in output:
                output.append(evidence_id)
    return output


def _ordered(values: Sequence[str], evidence_order: Sequence[str]) -> list[str]:
    order = {item: index for index, item in enumerate(evidence_order)}
    return sorted(set(values), key=lambda item: (order.get(item, len(order)), item))


def _public_output_diff(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    evidence_order: Sequence[str],
    slot_order: Sequence[str],
) -> dict[str, Any]:
    before_facts = {item["slot"]: item for item in before["decision_facts"]}
    after_facts = {item["slot"]: item for item in after["decision_facts"]}
    fact_changes: list[dict[str, Any]] = []
    for slot in slot_order:
        old = before_facts.get(slot)
        new = after_facts.get(slot)
        old_public = (
            None
            if old is None
            else {"value": old["value"], "evidence_ids": old["evidence_ids"]}
        )
        new_public = (
            None
            if new is None
            else {"value": new["value"], "evidence_ids": new["evidence_ids"]}
        )
        if old_public != new_public:
            fact_changes.append(
                {"slot": slot, "before": old_public, "after": new_public}
            )
    before_support = _support_ids(before)
    after_support = _support_ids(after)
    before_invalidated = before["invalidated_evidence_ids"]
    after_invalidated = after["invalidated_evidence_ids"]
    return {
        "answer_before": before["current_answer"],
        "answer_after": after["current_answer"],
        "answer_changed": before["current_answer"] != after["current_answer"],
        "support_before_ids": _ordered(before_support, evidence_order),
        "support_after_ids": _ordered(after_support, evidence_order),
        "support_added_ids": _ordered(
            set(after_support) - set(before_support), evidence_order
        ),
        "support_dropped_ids": _ordered(
            set(before_support) - set(after_support), evidence_order
        ),
        "invalidated_added_ids": _ordered(
            set(after_invalidated) - set(before_invalidated), evidence_order
        ),
        "invalidated_dropped_ids": _ordered(
            set(before_invalidated) - set(after_invalidated), evidence_order
        ),
        "decision_fact_changes": fact_changes,
        "derived_from": "public_reasoning_cards_only",
    }


def _project_lane_grade(value: Any) -> dict[str, Any]:
    grade = _mapping(value, "lane grade")
    checks_value = _mapping(grade.get("checks"), "lane grade checks")
    checks = {
        name: _bool(checks_value.get(name), f"grade check {name}")
        for name in (
            "answer_exact",
            "expected_invalidated_evidence_marked",
            "forbidden_support_absent",
            "required_evidence_present",
            "required_facts_exact",
            "stable_facts_exact",
        )
    }
    return {
        "machine_success": _bool(grade.get("machine_success"), "machine success"),
        "evidence_consistent": _bool(
            grade.get("evidence_consistent"), "evidence consistent"
        ),
        "checks": checks,
        "citation_precision": _number(
            grade.get("citation_precision"), "citation precision"
        ),
        "citation_recall": _number(grade.get("citation_recall"), "citation recall"),
        "missing_required_evidence_ids": _string_list(
            grade.get("missing_required_evidence_ids"), "missing evidence IDs"
        ),
        "support_evidence_ids": _string_list(
            grade.get("support_evidence_ids"), "support evidence IDs"
        ),
        "unexpected_support_evidence_ids": _string_list(
            grade.get("unexpected_support_evidence_ids"),
            "unexpected support evidence IDs",
        ),
        "stale_historical_cards": _integer(
            grade.get("stale_historical_cards"), "stale historical cards"
        ),
    }


def _sum_receipts(call_values: Sequence[Any]) -> dict[str, Any]:
    projected = [
        _project_receipt(_mapping(item, "branch call")["receipt"])
        for item in call_values
    ]
    output: dict[str, Any] = {
        "api_calls": 0,
        "logical_calls": 0,
        "latency_ms": 0.0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cached_input_tokens": 0,
        "cache_write_tokens": 0,
        "reasoning_tokens": 0,
        "exact_provider_tokens": True,
    }
    for receipt in projected:
        usage = receipt["usage"]
        for name in ACCOUNTING_FIELDS:
            if name == "exact_provider_tokens":
                output[name] = output[name] and usage[name]
            else:
                output[name] += usage[name]
    return output


def _assert_accounting_matches_calls(
    accounting: Mapping[str, Any], call_values: Sequence[Any], label: str
) -> None:
    observed = _sum_receipts(call_values)
    for name in ACCOUNTING_FIELDS:
        if name == "latency_ms":
            if not math.isclose(
                float(accounting[name]),
                float(observed[name]),
                rel_tol=0.0,
                abs_tol=1e-6,
            ):
                raise ValueError(f"{label} latency did not match call receipts")
        elif accounting[name] != observed[name]:
            raise ValueError(f"{label} {name} did not match call receipts")


def _select_episode(
    lock: Mapping[str, Any], inputs: Mapping[str, Any]
) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]:
    source = _mapping(inputs.get("episode_v0_4"), "episode source")
    manifest = _mapping(source.get("manifest"), "episode manifest")
    results = _mapping(source.get("results"), "episode results")
    traces = _list(source.get("traces"), "episode traces")
    case_ids = _string_list(manifest.get("case_ids"), "episode manifest case_ids")
    if not case_ids:
        raise ValueError("episode manifest has no case IDs")
    case_id = case_ids[0]
    expected = _mapping(lock.get("expected"), "expected")
    if case_id != expected.get("selected_case_id"):
        raise ValueError("mechanical first-case selection changed")
    trial_index = _integer(
        _mapping(lock.get("selection"), "selection").get("trial_index"),
        "selection trial index",
    )
    if trial_index != expected.get("trial_index"):
        raise ValueError("trial selection changed")
    selected_results = [
        _mapping(item, "result run")
        for item in _list(results.get("runs"), "results runs")
        if _mapping(item, "result run").get("case_id") == case_id
        and _mapping(item, "result run").get("trial_index") == trial_index
    ]
    if len(selected_results) != 1:
        raise ValueError("mechanical selection was not unique in results")
    result_run = selected_results[0]
    selected_traces = [
        _mapping(item, "trace row")
        for item in traces
        if _mapping(item, "trace row").get("run_id") == result_run.get("run_id")
    ]
    if len(selected_traces) != 1:
        raise ValueError("mechanical selection was not unique in traces")
    trace_row = selected_traces[0]
    trace = _mapping(trace_row.get("trace"), "selected trace")
    if (
        trace_row.get("case_id") != case_id
        or trace.get("case_input_fingerprint") is None
    ):
        raise ValueError("selected trace identity mismatch")
    return result_run, trace_row, trace


def _verify_source_fingerprints(
    result_run: Mapping[str, Any],
    trace_row: Mapping[str, Any],
    trace: Mapping[str, Any],
) -> None:
    trace_material = dict(trace)
    stored_trace_fingerprint = _string(
        trace_material.pop("trace_fingerprint", None), "trace fingerprint"
    )
    if _fingerprint(trace_material) != stored_trace_fingerprint:
        raise ValueError("source trace fingerprint did not recompute")
    if trace_row.get("run_id") != result_run.get("run_id"):
        raise ValueError("source run IDs did not match")
    if result_run.get("trace_fingerprint") != stored_trace_fingerprint:
        raise ValueError("result and trace fingerprints did not match")
    plan = dict(_mapping(trace.get("replay_plan"), "replay plan"))
    stored_plan_fingerprint = _string(
        plan.pop("plan_fingerprint", None), "plan fingerprint"
    )
    if _fingerprint(plan) != stored_plan_fingerprint:
        raise ValueError("source plan fingerprint did not recompute")
    if result_run.get("plan_fingerprint") != stored_plan_fingerprint:
        raise ValueError("result and plan fingerprints did not match")
    lanes = _mapping(trace.get("lanes"), "source lanes")
    if {value.get("plan_fingerprint") for value in lanes.values()} != {
        stored_plan_fingerprint
    }:
        raise ValueError("lane plan fingerprints diverged")
    observation = _mapping(trace.get("revision_observation"), "observation")
    adapted = _mapping(observation.get("adapted_observation"), "adapted observation")
    receipt = _mapping(observation.get("receipt"), "observer receipt")
    if adapted.get("input_sha256") != receipt.get("request_fingerprint"):
        raise ValueError("observer input and request fingerprints diverged")


def _build_episode(
    lock: Mapping[str, Any], inputs: Mapping[str, Any]
) -> dict[str, Any]:
    result_run, trace_row, trace = _select_episode(lock, inputs)
    _verify_source_fingerprints(result_run, trace_row, trace)
    case = _mapping(trace.get("case"), "case")
    expected = _mapping(lock.get("expected"), "expected")
    initial_evidence_values = _list(case.get("initial_evidence"), "initial evidence")
    if len(initial_evidence_values) != expected.get("initial_evidence_count"):
        raise ValueError("initial evidence count changed")
    evidence: list[dict[str, Any]] = []
    for ordinal, value in enumerate(initial_evidence_values, 1):
        item = _mapping(value, "initial evidence item")
        evidence.append(
            {
                "evidence_id": _string(item.get("evidence_id"), "evidence ID"),
                "ordinal": ordinal,
                "phase": "initial",
                "text": _string(item.get("text"), "evidence text"),
                "invalidated_by_event": False,
            }
        )
    late = _mapping(case.get("late_evidence"), "late evidence")
    evidence.append(
        {
            "evidence_id": _string(late.get("evidence_id"), "late evidence ID"),
            "ordinal": len(evidence) + 1,
            "phase": "event",
            "text": _string(late.get("text"), "late evidence text"),
            "invalidated_by_event": False,
        }
    )
    evidence_order = [item["evidence_id"] for item in evidence]
    if len(evidence_order) != len(set(evidence_order)):
        raise ValueError("evidence IDs must be unique")
    evidence_ids = set(evidence_order)
    observation = _mapping(trace.get("revision_observation"), "observation")
    adapted = _mapping(observation.get("adapted_observation"), "adapted observation")
    invalidated = _string_list(
        observation.get("invalidated_evidence_ids"), "invalidated evidence IDs"
    )
    if invalidated != expected.get("invalidated_evidence_ids"):
        raise ValueError("invalidated evidence roster changed")
    for item in evidence:
        item["invalidated_by_event"] = item["evidence_id"] in invalidated
    if adapted.get("source_id") != expected.get("event_evidence_id"):
        raise ValueError("event evidence ID changed")
    initial_cards_source = _list(trace.get("shared_initial_trace"), "initial trace")
    initial_cards = [_project_card(item, evidence_ids) for item in initial_cards_source]
    initial_calls = _list(trace.get("shared_initial_calls"), "initial calls")
    if len(initial_cards) != len(initial_evidence_values):
        raise ValueError("initial card count did not match initial evidence")
    if len(initial_calls) != len(initial_cards):
        raise ValueError("initial calls did not match initial cards")
    initial_call_cards = [
        _project_card(_mapping(item, "initial call").get("card"), evidence_ids)
        for item in initial_calls
    ]
    if initial_call_cards != initial_cards:
        raise ValueError("initial call cards did not match the public trace")
    if [
        _mapping(item, "initial call").get("sequence_offset") for item in initial_calls
    ] != list(range(len(initial_cards))):
        raise ValueError("initial call sequence offsets changed")
    common_accounting = _project_accounting(trace.get("common_initial_accounting"))
    _assert_accounting_matches_calls(common_accounting, initial_calls, "initial")
    all_physical_calls = list(initial_calls)
    initial_card = initial_cards[-1]
    grade = _mapping(result_run.get("grade"), "run grade")
    initial_grade = _mapping(grade.get("initial"), "initial grade")
    if initial_card["current_answer"] != expected.get("initial_answer"):
        raise ValueError("initial public answer changed")
    if initial_grade.get("observed_answer") != initial_card["current_answer"]:
        raise ValueError("initial grade did not match initial card")
    if initial_grade.get("answer_exact") is not True:
        raise ValueError("pre-event initial answer no longer matches")
    plan_source = _mapping(trace.get("replay_plan"), "replay plan")
    expected_plan = _mapping(expected.get("plan"), "expected plan")
    for name, expected_value in expected_plan.items():
        if plan_source.get(name) != expected_value:
            raise ValueError(f"locked replay plan changed: {name}")
    plan = {
        "event_triggered": _bool(plan_source.get("event_triggered"), "event triggered"),
        "event_threshold": _number(
            plan_source.get("event_threshold"), "event threshold"
        ),
        "selected_anchor_step": _integer(
            plan_source.get("selected_anchor_step"), "selected anchor step"
        ),
        "selected_anchor_evidence_id": _string(
            plan_source.get("selected_anchor_evidence_id"),
            "selected anchor evidence ID",
        ),
        "execution_replay_floor": _integer(
            plan_source.get("execution_replay_floor"), "execution replay floor"
        ),
        "checkpoint_step": _integer(
            plan_source.get("checkpoint_step"), "checkpoint step"
        ),
        "selection_mode": _string(plan_source.get("selection_mode"), "selection mode"),
        "invalidated_evidence_ids": _string_list(
            plan_source.get("invalidated_evidence_ids"),
            "plan invalidated evidence IDs",
        ),
        "decision_input_fingerprint": _string(
            plan_source.get("decision_input_fingerprint"),
            "decision input fingerprint",
        ),
        "pre_outcome": _bool(plan_source.get("pre_outcome"), "pre outcome"),
        "trajectory_horizon_status": _string(
            plan_source.get("trajectory_horizon_status"), "trajectory horizon"
        ),
        "shadow_trajectory_anchor_floor": _integer(
            plan_source.get("shadow_trajectory_anchor_floor"),
            "shadow trajectory anchor floor",
        ),
        "source_plan_fingerprint": _string(
            plan_source.get("plan_fingerprint"), "source plan fingerprint"
        ),
    }
    plan["projection_fingerprint"] = _fingerprint(plan)
    observer_provenance = _mapping(
        trace.get("observer_provenance"), "observer provenance"
    )
    observer_receipt = _project_receipt(observation.get("receipt"))
    all_physical_calls.append({"receipt": observation.get("receipt")})
    observer = {
        "public_summary": _string(observation.get("public_summary"), "public summary"),
        "relevant": _bool(observation.get("relevant"), "observer relevant"),
        "source_id": _string(adapted.get("source_id"), "observer source ID"),
        "topic": _string(adapted.get("topic"), "observer topic"),
        "stance": adapted.get("stance"),
        "confidence": adapted.get("confidence"),
        "revision_cue": adapted.get("revision_cue"),
        "invalidated_evidence_ids": invalidated,
        "source_input_fingerprint": _string(
            adapted.get("input_sha256"), "observer input fingerprint"
        ),
        "provenance": {
            "adapter_name": _string(
                observer_provenance.get("adapter_name"), "adapter name"
            ),
            "adapter_version": _string(
                observer_provenance.get("adapter_version"), "adapter version"
            ),
            "provider": _string(observer_provenance.get("provider"), "provider"),
            "model": _string(observer_provenance.get("model"), "observer model"),
            "semantic_source": _string(
                observer_provenance.get("semantic_source"), "semantic source"
            ),
            "deterministic": _bool(
                observer_provenance.get("deterministic"), "observer deterministic"
            ),
        },
        "receipt": observer_receipt,
    }
    observer["projection_fingerprint"] = _fingerprint(observer)
    event = {
        "event_evidence_id": observer["source_id"],
        "triggered": plan["event_triggered"],
        "relevant": observer["relevant"],
        "revision_cue": observer["revision_cue"],
        "invalidated_evidence_ids": invalidated,
        "selected_anchor_evidence_id": plan["selected_anchor_evidence_id"],
        "public_summary": observer["public_summary"],
    }
    event["projection_fingerprint"] = _fingerprint(event)
    slot_values = _list(case.get("decision_slots"), "decision slots")
    slots = [
        {
            "slot_id": _string(
                _mapping(item, "decision slot").get("slot_id"), "slot ID"
            ),
            "description": _string(
                _mapping(item, "decision slot").get("description"),
                "slot description",
            ),
            "allowed_values": _string_list(
                _mapping(item, "decision slot").get("allowed_values"),
                "allowed values",
            ),
            "required": _bool(
                _mapping(item, "decision slot").get("required"), "slot required"
            ),
        }
        for item in slot_values
    ]
    slot_order = [item["slot_id"] for item in slots]
    source_lanes = _mapping(trace.get("lanes"), "source lanes")
    source_lane_grades = _mapping(grade.get("lanes"), "lane grades")
    expected_lanes = _mapping(expected.get("lane_outcomes"), "expected lanes")
    lanes: list[dict[str, Any]] = []
    for lane_id in LANE_ORDER:
        source_lane = _mapping(source_lanes.get(lane_id), f"lane {lane_id}")
        lane_grade = _project_lane_grade(source_lane_grades.get(lane_id))
        cards = [
            _project_card(item, evidence_ids)
            for item in _list(source_lane.get("cards"), f"{lane_id} cards")
        ]
        branch_calls = _list(source_lane.get("branch_calls"), f"{lane_id} branch calls")
        all_physical_calls.extend(branch_calls)
        regenerated = _integer(
            source_lane.get("regenerated_cards"), f"{lane_id} regenerated cards"
        )
        if len(branch_calls) != regenerated:
            raise ValueError(f"{lane_id} branch calls did not match regenerated cards")
        if len(cards) != len(evidence):
            raise ValueError(f"{lane_id} did not retain six public checkpoints")
        branch_call_cards = [
            _project_card(_mapping(item, "branch call").get("card"), evidence_ids)
            for item in branch_calls
        ]
        if lane_id == "card_only_forward":
            expected_branch_cards = cards[-1:]
        elif lane_id == "selective_replay":
            expected_branch_cards = cards[plan["execution_replay_floor"] :]
        else:
            expected_branch_cards = cards
        if branch_call_cards != expected_branch_cards:
            raise ValueError(f"{lane_id} call cards did not match replayed checkpoints")
        final_card = _project_card(source_lane.get("final_card"), evidence_ids)
        if final_card != cards[-1]:
            raise ValueError(f"{lane_id} final card did not match final checkpoint")
        branch_accounting = _project_accounting(source_lane.get("branch_accounting"))
        _assert_accounting_matches_calls(branch_accounting, branch_calls, lane_id)
        expected_lane = _mapping(expected_lanes.get(lane_id), f"expected {lane_id}")
        observed_lane = {
            "answer": final_card["current_answer"],
            "branch_calls": branch_accounting["api_calls"],
            "machine_success": lane_grade["machine_success"],
            "regenerated_cards": regenerated,
        }
        if observed_lane != expected_lane:
            raise ValueError(f"locked lane outcome changed: {lane_id}")
        if source_lane.get("plan_fingerprint") != plan["source_plan_fingerprint"]:
            raise ValueError(f"{lane_id} plan fingerprint changed")
        lanes.append(
            {
                "lane_id": lane_id,
                "label": LANE_LABELS[lane_id],
                "source_plan_fingerprint": plan["source_plan_fingerprint"],
                "calls": branch_accounting["api_calls"],
                "regenerated_cards": regenerated,
                "replay_accounting": branch_accounting,
                "public_cards": cards,
                "final_card": final_card,
                "grade": lane_grade,
                "public_output_diff": _public_output_diff(
                    initial_card, final_card, evidence_order, slot_order
                ),
            }
        )
    if not plan["pre_outcome"]:
        raise ValueError("replay plan is not pre-outcome")
    if {lane["source_plan_fingerprint"] for lane in lanes} != {
        plan["source_plan_fingerprint"]
    }:
        raise ValueError("projected lanes do not share one plan fingerprint")
    negative_lanes = [
        lane["lane_id"] for lane in lanes if not lane["grade"]["machine_success"]
    ]
    if negative_lanes != ["card_only_forward", "selective_replay"]:
        raise ValueError("recorded negative lanes were not retained")
    full_lane = next(item for item in lanes if item["lane_id"] == "full_restart")
    physical_accounting = _project_accounting(
        trace.get("physical_experiment_accounting")
    )
    _assert_accounting_matches_calls(
        physical_accounting, all_physical_calls, "physical experiment"
    )
    episode = {
        "source": {
            "artifact": "artifacts/benchmark_language_replay_v0_4_live_smoke",
            "mode": _string(result_run.get("mode"), "episode mode"),
            "run_id": _string(result_run.get("run_id"), "run ID"),
            "case_id": _string(result_run.get("case_id"), "case ID"),
            "trial_index": _integer(result_run.get("trial_index"), "trial index"),
            "source_trace_fingerprint": _string(
                trace.get("trace_fingerprint"), "trace fingerprint"
            ),
        },
        "question": _string(case.get("question"), "case question"),
        "answer_choices": _string_list(case.get("answer_choices"), "answer choices"),
        "decision_slots": slots,
        "evidence": evidence,
        "initial": {
            "phase": "pre_event",
            "status": "initial_answer_match",
            "expected_answer": _string(
                initial_grade.get("expected_answer"), "initial expected answer"
            ),
            "observed_answer": _string(
                initial_grade.get("observed_answer"), "initial observed answer"
            ),
            "answer_exact": True,
            "post_event_machine_success": None,
            "public_card": initial_card,
            "public_cards": initial_cards,
            "accounting": common_accounting,
        },
        "observer": observer,
        "event": event,
        "revision_plan": plan,
        "replay_lanes": lanes,
        "public_output_comparison": {
            "before": initial_card,
            "after": full_lane["final_card"],
            "diff": full_lane["public_output_diff"],
            "selected_recorded_lane": "full_restart",
            "selection_rationale": "only_recorded_machine_success_in_selected_episode",
        },
        "recorded_physical_experiment_accounting": physical_accounting,
        "negative_lanes_retained": negative_lanes,
    }
    episode["projection_fingerprint"] = _fingerprint(episode)
    return episode


def _arm_context(value: Any) -> dict[str, Any]:
    arm = _mapping(value, "aperture arm summary")
    return {
        "attempted_runs": _integer(arm.get("attempted_runs"), "attempted runs"),
        "completed_outputs": _integer(
            arm.get("completed_outputs"), "completed outputs"
        ),
        "machine_successes": _integer(
            arm.get("machine_successes"), "machine successes"
        ),
        "api_calls": _integer(arm.get("api_calls"), "API calls"),
        "input_tokens": arm.get("input_tokens"),
        "output_tokens": arm.get("output_tokens"),
        "reasoning_tokens": arm.get("reasoning_tokens"),
    }


def _build_aperture_context(inputs: Mapping[str, Any]) -> dict[str, Any]:
    v041_source = _mapping(inputs.get("aperture_v0_4_1"), "v0.4.1 source")
    v042_source = _mapping(inputs.get("aperture_v0_4_2_r01"), "v0.4.2 source")
    v041_manifest = _mapping(v041_source.get("manifest"), "v0.4.1 manifest")
    v041_results = _mapping(v041_source.get("results"), "v0.4.1 results")
    v042_manifest = _mapping(v042_source.get("manifest"), "v0.4.2 manifest")
    v042_results = _mapping(v042_source.get("results"), "v0.4.2 results")
    v041_summary = _mapping(v041_results.get("summary"), "v0.4.1 summary")
    v042_summary = _mapping(v042_results.get("summary"), "v0.4.2 summary")
    v041_arms = _mapping(v041_summary.get("arm_summary"), "v0.4.1 arms")
    v042_arms = _mapping(v042_summary.get("arm_summary"), "v0.4.2 arms")
    arm_ids = (
        "direct_raw_no_revision",
        "direct_raw_fixed_revision_rerun",
        "staged_card_only_rerun",
        "staged_cumulative_raw",
    )
    return {
        "relationship_to_recorded_episode": "context_only_not_same_causal_episode",
        "v0_4_1": {
            "artifact": "artifacts/benchmark_aperture_controls_v0_4_1_dev",
            "status": _string(v041_manifest.get("status"), "v0.4.1 status"),
            "execution_complete": _bool(
                v041_manifest.get("execution_complete"), "v0.4.1 execution complete"
            ),
            "locked_decision_ready": _bool(
                v041_manifest.get("locked_decision_ready"),
                "v0.4.1 decision ready",
            ),
            "arms": {name: _arm_context(v041_arms[name]) for name in arm_ids},
            "interpretation": (
                "Descriptive incomplete-DEV context only: cumulative raw recorded "
                "30/30 machine successes while card-only recorded 2/28 completed; "
                "the locked cause gate remained closed."
            ),
        },
        "v0_4_2_unchanged_replication_r01": {
            "artifact": (
                "artifacts/benchmark_aperture_controls_"
                "v0_4_2_unchanged_replication_r01_dev"
            ),
            "status": _string(v042_manifest.get("status"), "v0.4.2 status"),
            "execution_complete": _bool(
                v042_manifest.get("execution_complete"), "v0.4.2 execution complete"
            ),
            "locked_decision_ready": _bool(
                v042_manifest.get("locked_decision_ready"),
                "v0.4.2 decision ready",
            ),
            "attempted_api_calls": _integer(
                v042_manifest.get("attempted_api_calls"), "v0.4.2 attempted calls"
            ),
            "nominal_api_calls": _integer(
                v042_manifest.get("nominal_api_calls"), "v0.4.2 nominal calls"
            ),
            "non_assessable_endpoints": _integer(
                v042_manifest.get("non_assessable_failures"),
                "v0.4.2 non-assessable endpoints",
            ),
            "arms": {name: _arm_context(v042_arms[name]) for name in arm_ids},
            "interpretation": (
                "Unchanged replication remained incomplete with 31 non-assessable "
                "endpoints; no locked aperture or reasoning decision was available."
            ),
        },
        "claim_boundary": (
            "These blocks describe separate frozen experiments and do not explain "
            "the selected v0.4 episode causally."
        ),
    }


def _validated_provider_receipts(
    results: Mapping[str, Any], calls_rows_value: Any
) -> list[Mapping[str, Any]]:
    calls_rows = _list(calls_rows_value, "v0.4.3 calls rows")
    expected_rows: list[dict[str, Any]] = []
    receipts: list[Mapping[str, Any]] = []
    for run_value in _list(results.get("runs"), "v0.4.3 runs"):
        run = _mapping(run_value, "v0.4.3 run")
        arms = _mapping(run.get("arms"), "v0.4.3 run arms")
        arm_order = _string_list(run.get("arm_order"), "v0.4.3 arm order")
        for arm in arm_order:
            arm_value = _mapping(arms.get(arm), f"v0.4.3 arm {arm}")
            for call_index, receipt_value in enumerate(
                _list(arm_value.get("receipts"), f"v0.4.3 {arm} receipts")
            ):
                receipt = _mapping(receipt_value, "v0.4.3 receipt")
                receipts.append(receipt)
                expected_rows.append(
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
    if calls_rows != expected_rows:
        raise ValueError("v0.4.3 calls rows did not exactly match result receipts")
    return receipts


def _build_provider_atlas(
    lock: Mapping[str, Any], inputs: Mapping[str, Any]
) -> dict[str, Any]:
    source = _mapping(inputs.get("provider_comparison_v0_4_3"), "provider source")
    manifest = _mapping(source.get("manifest"), "v0.4.3 manifest")
    results = _mapping(source.get("results"), "v0.4.3 results")
    provider_receipts = _validated_provider_receipts(results, source.get("calls"))
    comparison = _mapping(source.get("comparison"), "provider comparison")
    metric = _mapping(comparison.get("primary_metric"), "provider primary metric")
    r01 = _mapping(metric.get("r01_frozen_native"), "r01 metric")
    v043 = _mapping(metric.get("v0_4_3_contract_smoke"), "v0.4.3 metric")
    expected = _mapping(lock.get("expected"), "expected")
    expected_provider = _mapping(
        expected.get("provider_diagnostic"), "expected provider diagnostic"
    )
    if len(provider_receipts) != manifest.get("receipt_count") or len(
        provider_receipts
    ) != manifest.get("attempted_api_calls"):
        raise ValueError("v0.4.3 provider receipt cardinality changed")
    http_status_counts: Counter[int] = Counter()
    receipt_phase_counts: Counter[str] = Counter()
    receipt_reason_counts: Counter[str] = Counter()
    for receipt in provider_receipts:
        metadata = _mapping(receipt.get("metadata"), "v0.4.3 receipt metadata")
        if metadata.get("http_observed") is not True:
            raise ValueError("v0.4.3 receipt omitted its HTTP observation")
        status_code = _integer(
            metadata.get("http_status_code"), "v0.4.3 HTTP status code"
        )
        http_status_counts[status_code] += 1
        receipt_phase_counts[
            _string(metadata.get("failure_phase"), "receipt failure phase")
        ] += 1
        receipt_reason_counts[
            _string(metadata.get("failure_reason_code"), "receipt failure reason")
        ] += 1
    expected_http_status_counts = {
        int(code): _integer(count, f"expected HTTP {code} count")
        for code, count in _mapping(
            expected_provider.get("http_status_counts"),
            "expected HTTP status counts",
        ).items()
    }
    if dict(http_status_counts) != expected_http_status_counts:
        raise ValueError("pinned v0.4.3 receipt HTTP status distribution changed")
    if sum(http_status_counts.values()) != manifest.get("http_observed_count") or sum(
        http_status_counts.values()
    ) != manifest.get("http_status_code_available_count"):
        raise ValueError("manifest HTTP count diverged from pinned receipts")
    if r01.get("fraction") != expected_provider.get("r01_fraction"):
        raise ValueError("r01 native diagnostic coverage changed")
    if v043.get("fraction") != expected_provider.get("v0_4_3_fraction"):
        raise ValueError("v0.4.3 diagnostic coverage changed")
    coverage_authority = _string(
        expected_provider.get("coverage_authority"), "coverage authority"
    )
    if (
        manifest.get("contract_smoke_exact_coverage") is not True
        or manifest.get("contract_smoke_coverage_authority") != coverage_authority
        or manifest.get("inherited_v0_4_2_smoke_namespace_projection_validated")
        is not True
    ):
        raise ValueError("authoritative v0.4.3 coverage projection changed")
    live_receipt_validation = _mapping(
        _mapping(results.get("summary"), "v0.4.3 results summary").get(
            "live_receipt_validation"
        ),
        "v0.4.3 live receipt validation",
    )
    if (
        live_receipt_validation.get("contract_smoke_exact_coverage") is not True
        or live_receipt_validation.get("contract_smoke_coverage_authority")
        != coverage_authority
        or live_receipt_validation.get(
            "inherited_v0_4_2_smoke_namespace_projection_validated"
        )
        is not True
    ):
        raise ValueError("results did not retain authoritative coverage lineage")
    if (
        comparison.get("diagnostic_comparison", {}).get("cross_block_effect_estimate")
        is not None
    ):
        raise ValueError("cross-block effect must remain null")
    if manifest.get("diagnostic_integrity_ready") is not True:
        raise ValueError("v0.4.3 diagnostic integrity gate changed")
    if manifest.get("full_launch_ready") is not False:
        raise ValueError("v0.4.3 full launch gate changed")
    if manifest.get("target_output_paths_absent") is not True:
        raise ValueError("v0.4.3 full output absence was not audited")
    manifest_lineage = _mapping(
        manifest.get("derived_artifact_lineage"), "manifest correction lineage"
    )
    results_lineage = _mapping(
        results.get("derived_artifact_lineage"), "results correction lineage"
    )
    verification = _mapping(comparison.get("verification"), "comparison verification")
    verification_checks = _mapping(
        verification.get("checks"), "comparison verification checks"
    )
    if (
        verification_checks.get("v0_4_3_post_freeze_coverage_lineage_valid") is not True
        or verification_checks.get(
            "v0_4_3_provider_receipts_unchanged_by_coverage_correction"
        )
        is not True
    ):
        raise ValueError("comparison did not validate corrected coverage lineage")
    comparison_lineage = _mapping(
        verification.get("v0_4_3_derived_coverage_lineage"),
        "comparison correction lineage",
    )
    lineage_fields = (
        "original_manifest_sha256",
        "provider_receipt_projection_sha256",
        "corrected_results_sha256",
        "authority",
    )
    for name in lineage_fields:
        expected_name = "coverage_authority" if name == "authority" else name
        expected_value = expected_provider.get(expected_name)
        if (
            manifest_lineage.get(name) != expected_value
            or comparison_lineage.get(name) != expected_value
        ):
            raise ValueError(f"provider correction lineage changed: {name}")
    if manifest_lineage.get("original_results_sha256") != expected_provider.get(
        "original_results_sha256"
    ) or results_lineage.get("original_results_sha256") != expected_provider.get(
        "original_results_sha256"
    ):
        raise ValueError("original v0.4.3 results lineage changed")
    if results_lineage.get("original_manifest_sha256") != expected_provider.get(
        "original_manifest_sha256"
    ) or results_lineage.get(
        "provider_receipt_projection_sha256"
    ) != expected_provider.get("provider_receipt_projection_sha256"):
        raise ValueError("results did not retain original observation lineage")
    for lineage_name, lineage_value in (
        ("manifest", manifest_lineage),
        ("results", results_lineage),
    ):
        if (
            lineage_value.get("correction_id") != expected_provider.get("correction_id")
            or lineage_value.get("authority") != coverage_authority
            or lineage_value.get("no_live_call") is not True
            or lineage_value.get("provider_observations_unchanged") is not True
        ):
            raise ValueError(f"{lineage_name} correction lineage changed")
    if comparison_lineage.get("no_live_call") is not True:
        raise ValueError("comparison correction lineage claimed a live call")
    expected_observation_hashes = dict(
        _mapping(
            expected_provider.get("observation_artifacts_unchanged"),
            "expected unchanged observations",
        )
    )
    manifest_observation_hashes = dict(
        _mapping(
            manifest_lineage.get("observation_artifacts_unchanged"),
            "manifest unchanged observations",
        )
    )
    results_observation_hashes = dict(
        _mapping(
            results_lineage.get("observation_artifacts_unchanged"),
            "results unchanged observations",
        )
    )
    artifact_hashes = _mapping(manifest.get("artifact_sha256"), "artifact hashes")
    if (
        manifest_observation_hashes != expected_observation_hashes
        or results_observation_hashes != expected_observation_hashes
        or any(
            artifact_hashes.get(name) != expected_hash
            for name, expected_hash in expected_observation_hashes.items()
        )
    ):
        raise ValueError("provider observation artifact bytes changed")
    source_specs = _mapping(
        _mapping(lock.get("sources"), "sources").get("provider_comparison_v0_4_3"),
        "provider source specs",
    )
    current_manifest_sha = _string(
        _mapping(source_specs.get("manifest"), "provider manifest spec").get("sha256"),
        "provider manifest SHA",
    )
    current_results_sha = _string(
        _mapping(source_specs.get("results"), "provider results spec").get("sha256"),
        "provider results SHA",
    )
    comparison_inputs = _mapping(comparison.get("inputs"), "comparison inputs")
    comparison_smoke = _mapping(
        comparison_inputs.get("v0_4_3_contract_smoke"),
        "comparison v0.4.3 smoke input",
    )
    if (
        comparison_smoke.get("manifest_sha256") != current_manifest_sha
        or manifest_lineage.get("corrected_results_sha256") != current_results_sha
        or current_results_sha != expected_provider.get("corrected_results_sha256")
    ):
        raise ValueError("corrected v0.4.3 source lineage is not authoritative")
    failures = _mapping(
        manifest.get("failure_counts_by_phase_and_allowlisted_code"),
        "failure counts",
    )
    by_reason = _mapping(
        failures.get("provider_boundary_by_reason"), "provider failures by reason"
    )
    by_phase = _mapping(
        failures.get("provider_boundary_by_phase"), "provider failures by phase"
    )
    nonzero_manifest_phases = {
        str(name): int(count) for name, count in by_phase.items() if count
    }
    nonzero_manifest_reasons = {
        str(name): int(count) for name, count in by_reason.items() if count
    }
    if (
        dict(receipt_phase_counts) != nonzero_manifest_phases
        or dict(receipt_reason_counts) != nonzero_manifest_reasons
    ):
        raise ValueError("manifest failure counts diverged from pinned receipts")
    if (
        len(http_status_counts) != 1
        or len(receipt_phase_counts) != 1
        or len(receipt_reason_counts) != 1
    ):
        raise ValueError("v0.4.3 Atlas requires one observed smoke failure family")
    observed_status_code, observed_status_count = next(iter(http_status_counts.items()))
    observed_phase, observed_phase_count = next(iter(receipt_phase_counts.items()))
    observed_reason, observed_reason_count = next(iter(receipt_reason_counts.items()))
    return {
        "artifact": "artifacts/benchmark_aperture_controls_v0_4_3_contract_smoke",
        "status": _string(manifest.get("status"), "v0.4.3 status"),
        "primary_execution_classification": _string(
            manifest.get("primary_execution_classification"),
            "v0.4.3 execution classification",
        ),
        "pipeline": [
            {
                "stage_id": "client_attempt",
                "label": "Client attempts",
                "count": _integer(
                    manifest.get("attempted_api_calls"), "attempted API calls"
                ),
            },
            {
                "stage_id": "http_observation",
                "label": "HTTP observations",
                "count": _integer(
                    manifest.get("http_observed_count"), "HTTP observed count"
                ),
                "status_code": observed_status_code,
                "status_count": observed_status_count,
            },
            {
                "stage_id": "structured_parse",
                "label": "Structured parses",
                "count": _integer(
                    manifest.get("structured_parse_success_count"),
                    "structured parse success count",
                ),
            },
            {
                "stage_id": "provider_contract_acceptance",
                "label": "Accepted outputs",
                "count": _integer(
                    manifest.get("accepted_endpoint_count"),
                    "accepted endpoint count",
                ),
            },
            {
                "stage_id": "reasoning_assessment",
                "label": "Assessed endpoints",
                "count": _integer(
                    manifest.get("assessed_endpoint_count"),
                    "assessed endpoint count",
                ),
            },
        ],
        "classified_failure": {
            "phase": observed_phase,
            "allowlisted_reason_code": observed_reason,
            "count": observed_reason_count,
            "phase_count": observed_phase_count,
            "unclassified_count": _integer(
                manifest.get("unclassified_failed_receipts"),
                "unclassified failed receipts",
            ),
        },
        "receipt_observations": {
            "source": "pinned_calls_jsonl_cross_checked_to_results_json",
            "receipt_count": len(provider_receipts),
            "http_observed_count": sum(http_status_counts.values()),
            "http_status_counts": {
                str(code): count for code, count in sorted(http_status_counts.items())
            },
        },
        "native_diagnostic_coverage": {
            "authority": coverage_authority,
            "r01_frozen_native": {
                "numerator": _integer(r01.get("numerator"), "r01 numerator"),
                "denominator": _integer(r01.get("denominator"), "r01 denominator"),
                "fraction": _string(r01.get("fraction"), "r01 fraction"),
            },
            "v0_4_3_contract_smoke": {
                "numerator": _integer(v043.get("numerator"), "v0.4.3 numerator"),
                "denominator": _integer(v043.get("denominator"), "v0.4.3 denominator"),
                "fraction": _string(v043.get("fraction"), "v0.4.3 fraction"),
            },
            "cross_block_effect_estimate": None,
            "scope": _string(
                _mapping(
                    comparison.get("diagnostic_comparison"),
                    "diagnostic comparison",
                ).get("scope"),
                "diagnostic comparison scope",
            ),
        },
        "coverage_lineage": {
            "schema_version": _string(
                manifest_lineage.get("schema_version"), "correction lineage schema"
            ),
            "correction_id": _string(
                manifest_lineage.get("correction_id"), "correction ID"
            ),
            "authority": coverage_authority,
            "artifact_bytes_postdate_preregistration": _bool(
                manifest_lineage.get("artifact_bytes_postdate_preregistration"),
                "post-preregistration artifact marker",
            ),
            "no_live_call": True,
            "provider_observations_unchanged": True,
            "original_manifest_sha256": _string(
                manifest_lineage.get("original_manifest_sha256"),
                "original manifest SHA",
            ),
            "original_results_sha256": _string(
                manifest_lineage.get("original_results_sha256"),
                "original results SHA",
            ),
            "corrected_manifest_sha256": current_manifest_sha,
            "corrected_results_sha256": current_results_sha,
            "provider_receipt_projection_sha256": _string(
                manifest_lineage.get("provider_receipt_projection_sha256"),
                "provider receipt projection SHA",
            ),
            "observation_artifacts_unchanged": expected_observation_hashes,
        },
        "gates": {
            "diagnostic_integrity_ready": True,
            "full_launch_ready": False,
            "locked_reasoning_ready": False,
            "reasoning_comparison_available": False,
        },
        "claim_boundary": (
            "Coverage is descriptive within each frozen block. The populations "
            "differ, the cross-block effect is null, and no reasoning endpoint was "
            "available in v0.4.3."
        ),
    }


def _assert_privacy(snapshot: Mapping[str, Any], lock: Mapping[str, Any]) -> None:
    forbidden_keys = {
        _string(item, "forbidden output key").lower()
        for item in _list(lock.get("forbidden_output_keys"), "forbidden keys")
    }

    def visit(value: Any) -> Iterator[tuple[str | None, Any]]:
        if isinstance(value, Mapping):
            for key, item in value.items():
                yield str(key), item
                yield from visit(item)
        elif isinstance(value, list):
            for item in value:
                yield None, item
                yield from visit(item)

    for key, value in visit(snapshot):
        if key is not None and key.lower() in forbidden_keys:
            raise ValueError(f"forbidden key leaked into snapshot: {key}")
        if isinstance(value, str):
            lowered = value.lower()
            if "openai_api_key" in lowered or "authorization:" in lowered:
                raise ValueError("secret-bearing marker leaked into snapshot")
            if value.startswith("sk-") or "bearer sk-" in lowered:
                raise ValueError("credential-like value leaked into snapshot")


def _source_ledger(lock: Mapping[str, Any]) -> dict[str, str]:
    output: dict[str, str] = {}
    sources = _mapping(lock.get("sources"), "sources")
    for source_value in sources.values():
        source = _mapping(source_value, "source")
        for spec_value in source.values():
            spec = _mapping(spec_value, "source spec")
            output[_string(spec.get("path"), "source path")] = _string(
                spec.get("sha256"), "source hash"
            )
    output[str(LOCK_PATH.relative_to(ROOT))] = _sha256(LOCK_PATH)
    output[str(BUILDER_PATH.relative_to(ROOT))] = _sha256(BUILDER_PATH)
    return dict(sorted(output.items()))


def _build_snapshot(
    lock: Mapping[str, Any], inputs: Mapping[str, Any]
) -> dict[str, Any]:
    selection = _mapping(lock.get("selection"), "selection")
    episode = _build_episode(lock, inputs)
    snapshot = {
        "schema_version": SNAPSHOT_SCHEMA,
        "status": "RECORDED_READ_ONLY",
        "title": "EBRT Reasoning Workbench",
        "subtitle": "Recorded Revision Workbench + Provider Failure Atlas",
        "generation": {
            "deterministic": True,
            "network_calls": 0,
            "timestamp_recorded": False,
            "projection_mode": "allowlist_only",
            "projection_lock_sha256": _sha256(LOCK_PATH),
            "builder_sha256": _sha256(BUILDER_PATH),
            "source_sha256": _source_ledger(lock),
        },
        "selection": {
            "case_rule": _string(selection.get("case_rule"), "case rule"),
            "case_id": episode["source"]["case_id"],
            "trial_index": episode["source"]["trial_index"],
            "unique_match": True,
        },
        "field_semantics": {
            "evidence": "recorded public raw evidence from the selected fixture",
            "public_reasoning_card": (
                "provider-emitted public structured output; not private reasoning text"
            ),
            "initial": (
                "pre-event answer match only; it has no post-event PASS/FAIL label"
            ),
            "public_output_diff": (
                "deterministic difference between emitted public Reasoning Cards"
            ),
            "reasoning_tokens": (
                "provider-reported usage detail; not reasoning content or quality"
            ),
            "latency_ms": "recorded client latency; not server compute",
            "sanitized_observer_receipt": (
                "exact lock allowlist; raw bodies, headers, IDs, and exceptions omitted"
            ),
            "aperture_context": "separate experiments; not the selected episode",
            "provider_failure_atlas": (
                "status and failure counts derived from pinned receipt rows; not "
                "reasoning-quality evidence"
            ),
        },
        "recorded_episode": episode,
        "aperture_context": _build_aperture_context(inputs),
        "provider_failure_atlas": _build_provider_atlas(lock, inputs),
        "gates": dict(_mapping(lock.get("gates"), "gates")),
        "claim_boundary": _string_list(lock.get("claim_boundary"), "claim boundary"),
    }
    _assert_privacy(snapshot, lock)
    snapshot["projection_fingerprint"] = _fingerprint(snapshot)
    return snapshot


def _verify_projection_fingerprint(value: Mapping[str, Any], label: str) -> None:
    material = dict(value)
    stored = material.pop("projection_fingerprint", None)
    if stored != _fingerprint(material):
        raise ValueError(f"{label} projection fingerprint mismatch")


def _validate_projection(
    snapshot: Mapping[str, Any], lock: Mapping[str, Any] | None = None
) -> None:
    if snapshot.get("schema_version") != SNAPSHOT_SCHEMA:
        raise ValueError("snapshot schema changed")
    if snapshot.get("status") != "RECORDED_READ_ONLY":
        raise ValueError("snapshot status changed")
    generation = _mapping(snapshot.get("generation"), "generation")
    if (
        generation.get("network_calls") != 0
        or generation.get("deterministic") is not True
    ):
        raise ValueError("generation boundary changed")
    gates = _mapping(snapshot.get("gates"), "gates")
    if gates != EXPECTED_GATES:
        raise ValueError("projection gates changed")
    episode = _mapping(snapshot.get("recorded_episode"), "recorded episode")
    _verify_projection_fingerprint(episode, "episode")
    _verify_projection_fingerprint(
        _mapping(episode.get("observer"), "observer"), "observer"
    )
    _verify_projection_fingerprint(_mapping(episode.get("event"), "event"), "event")
    _verify_projection_fingerprint(
        _mapping(episode.get("revision_plan"), "revision plan"), "plan"
    )
    initial = _mapping(episode.get("initial"), "initial")
    observer = _mapping(episode.get("observer"), "observer")
    _validate_sanitized_receipt(observer.get("receipt"), "snapshot observer receipt")
    if (
        initial.get("phase") != "pre_event"
        or initial.get("status") != "initial_answer_match"
        or initial.get("post_event_machine_success") is not None
    ):
        raise ValueError("initial state was relabeled as a post-event outcome")
    evidence = _list(episode.get("evidence"), "evidence")
    evidence_order = [item["evidence_id"] for item in evidence]
    slots = _list(episode.get("decision_slots"), "decision slots")
    slot_order = [item["slot_id"] for item in slots]
    initial_card = _mapping(initial.get("public_card"), "initial card")
    lanes = _list(episode.get("replay_lanes"), "replay lanes")
    if [item["lane_id"] for item in lanes] != list(LANE_ORDER):
        raise ValueError("projected lane order changed")
    for lane in lanes:
        expected_diff = _public_output_diff(
            initial_card,
            _mapping(lane.get("final_card"), "final card"),
            evidence_order,
            slot_order,
        )
        if lane.get("public_output_diff") != expected_diff:
            raise ValueError("public output diff was not derived from public cards")
    full_lane = next(item for item in lanes if item["lane_id"] == "full_restart")
    comparison = _mapping(
        episode.get("public_output_comparison"), "public output comparison"
    )
    if (
        comparison.get("before") != initial_card
        or comparison.get("after") != full_lane["final_card"]
        or comparison.get("diff") != full_lane["public_output_diff"]
        or comparison.get("selected_recorded_lane") != "full_restart"
    ):
        raise ValueError("episode output comparison diverged from recorded lane")
    fingerprints = {lane.get("source_plan_fingerprint") for lane in lanes}
    plan = _mapping(episode.get("revision_plan"), "revision plan")
    if fingerprints != {plan.get("source_plan_fingerprint")}:
        raise ValueError("lane plan fingerprints diverged")
    if plan.get("pre_outcome") is not True:
        raise ValueError("replay plan is not pre-outcome")
    if episode.get("negative_lanes_retained") != [
        "card_only_forward",
        "selective_replay",
    ]:
        raise ValueError("negative replay lanes were lost")
    atlas = _mapping(snapshot.get("provider_failure_atlas"), "failure atlas")
    coverage = _mapping(atlas.get("native_diagnostic_coverage"), "coverage")
    if coverage["r01_frozen_native"]["fraction"] != "0/31":
        raise ValueError("r01 coverage changed")
    if coverage["v0_4_3_contract_smoke"]["fraction"] != "8/8":
        raise ValueError("v0.4.3 coverage changed")
    if coverage.get("cross_block_effect_estimate") is not None:
        raise ValueError("cross-block effect was invented")
    lineage = _mapping(atlas.get("coverage_lineage"), "coverage lineage")
    if (
        lineage.get("authority") != "v0.4.3_policy_exact_schedule_projection"
        or lineage.get("no_live_call") is not True
        or lineage.get("provider_observations_unchanged") is not True
        or coverage.get("authority") != lineage.get("authority")
    ):
        raise ValueError("authoritative coverage lineage changed")
    if lock is not None:
        expected_provider = _mapping(
            _mapping(lock.get("expected"), "expected").get("provider_diagnostic"),
            "expected provider diagnostic",
        )
        for name in (
            "correction_id",
            "authority",
            "original_manifest_sha256",
            "original_results_sha256",
            "corrected_results_sha256",
            "provider_receipt_projection_sha256",
        ):
            snapshot_name = "authority" if name == "authority" else name
            expected_name = "coverage_authority" if name == "authority" else name
            if lineage.get(snapshot_name) != expected_provider.get(expected_name):
                raise ValueError(f"coverage lineage lock mismatch: {name}")
        if lineage.get("observation_artifacts_unchanged") != expected_provider.get(
            "observation_artifacts_unchanged"
        ):
            raise ValueError("unchanged observation hash ledger changed")
    pipeline = _list(atlas.get("pipeline"), "failure atlas pipeline")
    if [item["count"] for item in pipeline] != [8, 8, 0, 0, 0]:
        raise ValueError("provider failure pipeline changed")
    receipt_observations = _mapping(
        atlas.get("receipt_observations"), "Atlas receipt observations"
    )
    if receipt_observations.get("source") != (
        "pinned_calls_jsonl_cross_checked_to_results_json"
    ):
        raise ValueError("Atlas receipt source changed")
    status_counts = _mapping(
        receipt_observations.get("http_status_counts"), "Atlas HTTP status counts"
    )
    http_stage = next(
        item for item in pipeline if item["stage_id"] == "http_observation"
    )
    if (
        receipt_observations.get("receipt_count") != pipeline[0]["count"]
        or receipt_observations.get("http_observed_count") != http_stage["count"]
        or len(status_counts) != 1
        or str(http_stage.get("status_code")) not in status_counts
        or http_stage.get("status_count")
        != status_counts[str(http_stage.get("status_code"))]
        or http_stage.get("status_count") != http_stage.get("count")
    ):
        raise ValueError("Atlas HTTP stage diverged from pinned receipt observations")
    classified_failure = _mapping(
        atlas.get("classified_failure"), "Atlas classified failure"
    )
    if (
        classified_failure.get("count") != http_stage.get("count")
        or classified_failure.get("phase_count") != http_stage.get("count")
        or classified_failure.get("unclassified_count") != 0
    ):
        raise ValueError("Atlas failure classification diverged from receipts")
    if lock is not None:
        expected_status_counts = _mapping(
            _mapping(
                _mapping(lock.get("expected"), "expected").get("provider_diagnostic"),
                "expected provider diagnostic",
            ).get("http_status_counts"),
            "expected HTTP status counts",
        )
        if status_counts != expected_status_counts:
            raise ValueError("Atlas HTTP status counts escaped the projection lock")
    _verify_projection_fingerprint(snapshot, "snapshot")
    if lock is not None:
        _assert_privacy(snapshot, lock)


def _refresh_projection_fingerprints(snapshot: dict[str, Any]) -> None:
    episode = snapshot["recorded_episode"]
    for name in ("observer", "event", "revision_plan"):
        value = episode[name]
        value.pop("projection_fingerprint", None)
        value["projection_fingerprint"] = _fingerprint(value)
    episode.pop("projection_fingerprint", None)
    episode["projection_fingerprint"] = _fingerprint(episode)
    snapshot.pop("projection_fingerprint", None)
    snapshot["projection_fingerprint"] = _fingerprint(snapshot)


def _expect_projection_rejected(
    source: Mapping[str, Any],
    lock: Mapping[str, Any],
    label: str,
    mutate: Any,
) -> None:
    candidate = copy.deepcopy(source)
    mutate(candidate)
    _refresh_projection_fingerprints(candidate)
    try:
        _validate_projection(candidate, lock)
    except ValueError:
        return
    raise AssertionError(f"tampered projection was accepted: {label}")


def _expect_value_error(label: str, action: Any) -> None:
    try:
        action()
    except ValueError:
        return
    raise AssertionError(f"tamper did not fail closed: {label}")


def _tamper_first_provider_http_status(
    inputs: dict[str, Any], status_code: int, *, results_too: bool
) -> None:
    source = inputs["provider_comparison_v0_4_3"]
    source["calls"][0]["receipt"]["metadata"]["http_status_code"] = status_code
    if results_too:
        run = source["results"]["runs"][0]
        first_arm = run["arm_order"][0]
        run["arms"][first_arm]["receipts"][0]["metadata"]["http_status_code"] = (
            status_code
        )


def _report(snapshot: Mapping[str, Any]) -> str:
    episode = snapshot["recorded_episode"]
    lanes = episode["replay_lanes"]
    atlas = snapshot["provider_failure_atlas"]
    aperture = snapshot["aperture_context"]
    lines = [
        "# EBRT v0.4.4 Reasoning Workbench projection",
        "",
        "## Status",
        "",
        "This is a deterministic, read-only projection of recorded public artifacts. "
        "It performs zero network calls and does not apply a live revision.",
        "",
        "## Mechanically selected episode",
        "",
        f"- Rule: `{snapshot['selection']['case_rule']}`",
        f"- Case: `{snapshot['selection']['case_id']}`",
        f"- Trial: `{snapshot['selection']['trial_index']}`",
        f"- Run: `{episode['source']['run_id']}`",
        f"- Source trace: `{episode['source']['source_trace_fingerprint']}`",
        "- Initial state: `pre_event / initial_answer_match` (not post-event PASS/FAIL)",
        "",
        "## Recorded replay lanes",
        "",
        "| Lane | Replay calls | Regenerated cards | Final answer | Machine grade |",
        "| --- | ---: | ---: | --- | --- |",
    ]
    for lane in lanes:
        grade = "PASS" if lane["grade"]["machine_success"] else "FAIL"
        lines.append(
            f"| `{lane['lane_id']}` | {lane['calls']} | "
            f"{lane['regenerated_cards']} | `{lane['final_card']['current_answer']}` "
            f"| {grade} |"
        )
    lines.extend(
        [
            "",
            "All three lanes share the same recorded pre-outcome plan fingerprint: "
            f"`{episode['revision_plan']['source_plan_fingerprint']}`.",
            "",
            "The visible output diff is derived only from public Reasoning Cards. "
            "The retained negative lanes are part of the artifact, not hidden.",
            "",
            "## Separate aperture context",
            "",
            f"- v0.4.1 status: `{aperture['v0_4_1']['status']}`; locked decision "
            f"ready: `{str(aperture['v0_4_1']['locked_decision_ready']).lower()}`.",
            "- v0.4.2 unchanged replication: "
            f"`{aperture['v0_4_2_unchanged_replication_r01']['non_assessable_endpoints']}` "
            "non-assessable endpoints; no locked aperture decision.",
            "",
            "These are separate experiment blocks and are not the same causal episode.",
            "",
            "## Provider Failure Atlas",
            "",
            "| Boundary | Count |",
            "| --- | ---: |",
        ]
    )
    for stage in atlas["pipeline"]:
        lines.append(f"| {stage['label']} | {stage['count']} |")
    coverage = atlas["native_diagnostic_coverage"]
    receipt_observations = atlas["receipt_observations"]
    failure = atlas["classified_failure"]
    status_distribution = ", ".join(
        f"{code}:{count}"
        for code, count in receipt_observations["http_status_counts"].items()
    )
    lines.extend(
        [
            "",
            f"- HTTP status distribution derived from pinned receipts: "
            f"`{status_distribution}`.",
            f"- v0.4.3 typed failure derived from the same receipts: "
            f"`{failure['phase']}/{failure['allowlisted_reason_code']}` "
            f"({failure['count']}/{receipt_observations['receipt_count']}).",
            f"- Native diagnostic coverage: r01 "
            f"`{coverage['r01_frozen_native']['fraction']}` vs v0.4.3 "
            f"`{coverage['v0_4_3_contract_smoke']['fraction']}`.",
            f"- Coverage authority: `{coverage['authority']}`.",
            "- Coverage lineage: post-freeze derived correction, no live call; "
            "provider-observation artifact hashes unchanged.",
            "- Cross-block effect estimate: `null`.",
            "- v0.4.3 full block: not launched; reasoning comparison unavailable.",
            "",
            "## Gates",
            "",
        ]
    )
    for name, value in snapshot["gates"].items():
        lines.append(f"- `{name}`: `{str(value).lower()}`")
    lines.extend(["", "## Claim boundary", ""])
    for item in snapshot["claim_boundary"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Reproducibility",
            "",
            f"- Projection fingerprint: `{snapshot['projection_fingerprint']}`",
            f"- Projection lock: `{snapshot['generation']['projection_lock_sha256']}`",
            f"- Builder: `{snapshot['generation']['builder_sha256']}`",
            "- Canonical and public snapshots are required to be byte-identical.",
            "- Timestamps are intentionally absent.",
            "",
        ]
    )
    return "\n".join(lines)


def _build_material(
    lock: Mapping[str, Any], inputs: Mapping[str, Any]
) -> tuple[dict[str, Any], bytes, bytes]:
    snapshot = _build_snapshot(lock, inputs)
    _validate_projection(snapshot, lock)
    snapshot_bytes = _pretty_json_bytes(snapshot)
    report_bytes = _report(snapshot).encode()
    return snapshot, snapshot_bytes, report_bytes


def _manifest(
    lock: Mapping[str, Any], snapshot_bytes: bytes, report_bytes: bytes
) -> dict[str, Any]:
    return {
        "schema_version": MANIFEST_SCHEMA,
        "status": "COMPLETE_READ_ONLY_PROJECTION",
        "success_manifest": True,
        "deterministic": True,
        "network_calls": 0,
        "timestamp_recorded": False,
        "artifact_sha256": {
            "projection_report.md": _sha256_bytes(report_bytes),
            "snapshot.json": _sha256_bytes(snapshot_bytes),
        },
        "public_snapshot_sha256": _sha256_bytes(snapshot_bytes),
        "source_sha256": _source_ledger(lock),
        "selection": {
            "case_rule": lock["selection"]["case_rule"],
            "case_id": lock["expected"]["selected_case_id"],
            "trial_index": lock["selection"]["trial_index"],
        },
        "gates": dict(lock["gates"]),
        "validation": {
            "source_hashes_and_manifest_artifacts_verified": True,
            "mechanical_selection_unique": True,
            "source_fingerprints_verified": True,
            "pre_outcome_plan_shared_across_lanes": True,
            "call_card_usage_and_grade_contracts_verified": True,
            "sanitized_observer_receipt_exact_allowlist_verified": True,
            "public_output_diff_recomputed": True,
            "negative_lanes_retained": True,
            "provider_coverage_8_of_8_and_0_of_31_verified": True,
            "v0_4_3_corrected_coverage_lineage_verified": True,
            "v0_4_3_provider_observation_bytes_unchanged": True,
            "v0_4_3_http_status_derived_from_pinned_receipts": True,
            "v0_4_3_full_artifact_absent": True,
            "privacy_allowlist_verified": True,
            "canonical_public_byte_identity_required": True,
        },
        "promotion_eligible": False,
    }


def _atomic_write(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary_name)
        raise


def _output_paths(lock: Mapping[str, Any]) -> dict[str, Path]:
    outputs = _mapping(lock.get("outputs"), "outputs")
    artifact_dir = _root_path(
        _string(outputs.get("artifact_directory"), "artifact directory"),
        "artifact directory",
    )
    return {
        "snapshot": artifact_dir / "snapshot.json",
        "report": artifact_dir / "projection_report.md",
        "manifest": artifact_dir / "manifest.json",
        "public": _root_path(
            _string(outputs.get("public_snapshot"), "public snapshot"),
            "public snapshot",
        ),
    }


@contextlib.contextmanager
def _network_guard() -> Iterator[None]:
    original_socket = socket.socket
    original_create_connection = socket.create_connection

    def blocked(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("network access attempted by deterministic builder")

    socket.socket = blocked  # type: ignore[assignment]
    socket.create_connection = blocked  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket = original_socket  # type: ignore[assignment]
        socket.create_connection = original_create_connection  # type: ignore[assignment]


def build() -> dict[str, str]:
    lock = _load_lock()
    with _network_guard():
        inputs = _load_inputs(lock)
        _, snapshot_bytes, report_bytes = _build_material(lock, inputs)
        manifest_value = _manifest(lock, snapshot_bytes, report_bytes)
        manifest_bytes = _pretty_json_bytes(manifest_value)
        paths = _output_paths(lock)
        _atomic_write(paths["snapshot"], snapshot_bytes)
        _atomic_write(paths["public"], snapshot_bytes)
        _atomic_write(paths["report"], report_bytes)
        _atomic_write(paths["manifest"], manifest_bytes)
    validate()
    return {
        "snapshot_sha256": _sha256_bytes(snapshot_bytes),
        "report_sha256": _sha256_bytes(report_bytes),
        "manifest_sha256": _sha256_bytes(manifest_bytes),
    }


def validate() -> None:
    lock = _load_lock()
    with _network_guard():
        inputs = _load_inputs(lock)
        _, expected_snapshot, expected_report = _build_material(lock, inputs)
        expected_manifest = _pretty_json_bytes(
            _manifest(lock, expected_snapshot, expected_report)
        )
        paths = _output_paths(lock)
        expected_values = {
            "snapshot": expected_snapshot,
            "public": expected_snapshot,
            "report": expected_report,
            "manifest": expected_manifest,
        }
        for name, expected in expected_values.items():
            path = paths[name]
            if not path.is_file():
                raise ValueError(f"missing generated {name}: {path.relative_to(ROOT)}")
            if path.read_bytes() != expected:
                raise ValueError(f"generated {name} is stale or non-deterministic")
        if paths["snapshot"].read_bytes() != paths["public"].read_bytes():
            raise ValueError("canonical and public snapshots are not byte-identical")


def self_test() -> None:
    lock = _load_lock()
    with _network_guard():
        inputs = _load_inputs(lock)
        first = _build_material(lock, inputs)
        second = _build_material(lock, inputs)
        if first[1:] != second[1:]:
            raise AssertionError("two in-memory builds were not byte-identical")
        _validate_projection(first[0], lock)
        manifest_one = _pretty_json_bytes(_manifest(lock, first[1], first[2]))
        manifest_two = _pretty_json_bytes(_manifest(lock, second[1], second[2]))
        if manifest_one != manifest_two:
            raise AssertionError("two generated manifests were not byte-identical")
        receipt_allowlist_tamper = copy.deepcopy(lock)
        receipt_allowlist_tamper["projection_allowlist"]["receipt"].append(
            "debug_metadata"
        )
        _expect_value_error(
            "sanitized receipt allowlist expansion",
            lambda: _validate_projection_allowlists(receipt_allowlist_tamper),
        )
        receipt_usage_allowlist_tamper = copy.deepcopy(lock)
        receipt_usage_allowlist_tamper["projection_allowlist"]["receipt_usage"].append(
            "estimated_cost"
        )
        _expect_value_error(
            "sanitized receipt usage allowlist expansion",
            lambda: _validate_projection_allowlists(receipt_usage_allowlist_tamper),
        )
        calls_only_status_tamper = copy.deepcopy(inputs)
        _tamper_first_provider_http_status(
            calls_only_status_tamper, 500, results_too=False
        )
        _expect_value_error(
            "calls JSONL receipt diverged from results",
            lambda: _build_provider_atlas(lock, calls_only_status_tamper),
        )
        receipt_count_tamper = copy.deepcopy(inputs)
        receipt_count_tamper["provider_comparison_v0_4_3"]["calls"].pop()
        _expect_value_error(
            "pinned receipt row removed",
            lambda: _build_provider_atlas(lock, receipt_count_tamper),
        )
        matched_status_tamper = copy.deepcopy(inputs)
        _tamper_first_provider_http_status(matched_status_tamper, 500, results_too=True)
        _expect_value_error(
            "pinned receipt HTTP distribution changed",
            lambda: _build_provider_atlas(lock, matched_status_tamper),
        )
        _expect_projection_rejected(
            first[0],
            lock,
            "initial relabeled as post-event",
            lambda value: value["recorded_episode"]["initial"].update(
                {"phase": "post_event"}
            ),
        )
        _expect_projection_rejected(
            first[0],
            lock,
            "public diff detached from cards",
            lambda value: value["recorded_episode"]["replay_lanes"][0][
                "public_output_diff"
            ].update({"answer_after": "BLUE"}),
        )
        _expect_projection_rejected(
            first[0],
            lock,
            "negative lanes removed",
            lambda value: value["recorded_episode"].update(
                {"negative_lanes_retained": []}
            ),
        )
        _expect_projection_rejected(
            first[0],
            lock,
            "cross-block effect invented",
            lambda value: value["provider_failure_atlas"][
                "native_diagnostic_coverage"
            ].update({"cross_block_effect_estimate": 1.0}),
        )
        _expect_projection_rejected(
            first[0],
            lock,
            "coverage authority changed",
            lambda value: value["provider_failure_atlas"]["coverage_lineage"].update(
                {"authority": "unlocked_projection"}
            ),
        )
        _expect_projection_rejected(
            first[0],
            lock,
            "provider observation hash changed",
            lambda value: value["provider_failure_atlas"]["coverage_lineage"][
                "observation_artifacts_unchanged"
            ].update({"calls.jsonl": "0" * 64}),
        )
        _expect_projection_rejected(
            first[0],
            lock,
            "live gate opened",
            lambda value: value["gates"].update({"live_execution_ready": True}),
        )
        _expect_projection_rejected(
            first[0],
            lock,
            "plan no longer pre-outcome",
            lambda value: value["recorded_episode"]["revision_plan"].update(
                {"pre_outcome": False}
            ),
        )
        _expect_projection_rejected(
            first[0],
            lock,
            "lane plan fingerprint diverged",
            lambda value: value["recorded_episode"]["replay_lanes"][0].update(
                {"source_plan_fingerprint": "0" * 64}
            ),
        )
        _expect_projection_rejected(
            first[0],
            lock,
            "forbidden raw response field",
            lambda value: value.update({"raw_response": "redacted"}),
        )
        _expect_projection_rejected(
            first[0],
            lock,
            "observer receipt allowlist expansion",
            lambda value: value["recorded_episode"]["observer"]["receipt"].update(
                {"debug_metadata": "none"}
            ),
        )
        _expect_projection_rejected(
            first[0],
            lock,
            "observer receipt usage allowlist expansion",
            lambda value: value["recorded_episode"]["observer"]["receipt"][
                "usage"
            ].update({"estimated_cost": 0}),
        )
        _expect_projection_rejected(
            first[0],
            lock,
            "Atlas HTTP status detached from receipts",
            lambda value: value["provider_failure_atlas"]["pipeline"][1].update(
                {"status_code": 500}
            ),
        )
        _expect_projection_rejected(
            first[0],
            lock,
            "Atlas HTTP count detached from receipts",
            lambda value: value["provider_failure_atlas"]["pipeline"][1].update(
                {"count": 7, "status_count": 7}
            ),
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("build", "validate", "self-test", "all"),
        nargs="?",
        default="all",
    )
    args = parser.parse_args()
    if args.command == "build":
        hashes = build()
        print(json.dumps({"status": "PASS", **hashes}, sort_keys=True))
    elif args.command == "validate":
        validate()
        print('{"status":"PASS","validation":"canonical_artifacts"}')
    elif args.command == "self-test":
        self_test()
        print('{"status":"PASS","self_test":"deterministic_network_zero"}')
    else:
        hashes = build()
        self_test()
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "validation": "build_validate_self_test",
                    **hashes,
                },
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
