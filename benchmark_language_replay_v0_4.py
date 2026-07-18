#!/usr/bin/env python3
"""Matched DEV benchmark for the EBRT v0.4 Language Replay Bridge."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import statistics
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parent
SOURCE_FILES = (
    "language_replay_bridge_v0_4.py",
    "openai_reasoning_provider_v0_4.py",
    "benchmark_language_replay_v0_4.py",
    "policy_lock_v0_4.json",
    "fixtures/language_replay_v0_4_dev.json",
    "fixtures/language_replay_v0_4_dev_gold.json",
    "semantic_adapter_v0_2.py",
    "requirements-live.txt",
)
BOOT_SOURCE_SNAPSHOT = {
    name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    for name in SOURCE_FILES
}

from language_replay_bridge_v0_4 import (  # noqa: E402
    LANES,
    CaseSpec,
    ReasoningCard,
    ScriptedReasoningProvider,
    StructuredRevisionObserver,
    canonical_json,
    execute_language_replay_case,
    fingerprint,
    run_self_tests as run_bridge_self_tests,
)


SCHEMA_VERSION = "ebrt-language-replay-benchmark-v0.4"
LOCK_PATH = ROOT / "policy_lock_v0_4.json"
FIXTURE_PATH = ROOT / "fixtures" / "language_replay_v0_4_dev.json"
GOLD_PATH = ROOT / "fixtures" / "language_replay_v0_4_dev_gold.json"
DEFAULT_FAKE_OUTPUT = ROOT / "benchmark_results" / "v0_4_fake_dev"
DEFAULT_LIVE_OUTPUT = ROOT / "benchmark_results" / "v0_4_live_smoke"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_snapshot() -> dict[str, str]:
    return {name: _sha256(ROOT / name) for name in SOURCE_FILES}


def _assert_source_snapshot(expected: Mapping[str, str]) -> None:
    observed = _source_snapshot()
    if dict(expected) != observed:
        raise RuntimeError("v0.4 source files changed during benchmark execution")


def _load_lock() -> dict[str, Any]:
    lock = _load_json(LOCK_PATH)
    if lock.get("status") != "DEV_DRAFT" or lock.get("promotion_eligible") is not False:
        raise RuntimeError("v0.4 lock must remain non-promotional DEV_DRAFT")
    if tuple(lock.get("lanes", ())) != LANES:
        raise RuntimeError("policy lock lane order does not match implementation")
    return lock


def _load_suite() -> tuple[list[CaseSpec], dict[str, dict[str, Any]], dict[str, Any]]:
    fixture = _load_json(FIXTURE_PATH)
    gold_file = _load_json(GOLD_PATH)
    if fixture.get("status") != "DEV_DRAFT" or gold_file.get("status") != "DEV_DRAFT":
        raise ValueError("fixture and gold must remain DEV_DRAFT")
    cases = [CaseSpec.from_mapping(item) for item in fixture["cases"]]
    gold = {str(item["case_id"]): item for item in gold_file["cases"]}
    case_ids = [case.case_id for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("fixture case IDs must be unique")
    if set(case_ids) != set(gold):
        raise ValueError("fixture/gold case IDs do not match")
    for case in cases:
        _validate_gold(case, gold[case.case_id])
    return cases, gold, gold_file


def _validate_fact(
    value: Mapping[str, Any],
    *,
    evidence_ids: set[str],
    label: str,
) -> None:
    if (
        not str(value.get("slot", "")).strip()
        or not str(value.get("value", "")).strip()
    ):
        raise ValueError(f"{label} fact slot/value must not be empty")
    cited = tuple(str(item) for item in value.get("evidence_ids", ()))
    if not cited or len(cited) != len(set(cited)):
        raise ValueError(f"{label} fact evidence IDs must be nonempty and unique")
    unknown = set(cited) - evidence_ids
    if unknown:
        raise ValueError(f"{label} fact cites unknown evidence: {sorted(unknown)}")


def _validate_state(
    case: CaseSpec,
    state: Mapping[str, Any],
    *,
    label: str,
) -> None:
    if state.get("answer") not in case.answer_choices:
        raise ValueError(f"{label} answer is outside answer choices")
    evidence_ids = set(case.evidence_ids)
    slot_values = {
        item.slot_id: set(item.allowed_values) for item in case.decision_slots
    }
    for name in ("evidence_ids", "invalidated_evidence_ids"):
        values = tuple(str(item) for item in state.get(name, ()))
        if len(values) != len(set(values)) or set(values) - evidence_ids:
            raise ValueError(f"{label} {name} is invalid")
    for fact in state.get("decision_facts", ()):
        _validate_fact(fact, evidence_ids=evidence_ids, label=label)
        if (
            fact["slot"] not in slot_values
            or fact["value"] not in slot_values[fact["slot"]]
        ):
            raise ValueError(f"{label} fact is outside the public decision schema")


def _validate_gold(case: CaseSpec, gold: Mapping[str, Any]) -> None:
    if gold.get("case_id") != case.case_id:
        raise ValueError("gold case_id mismatch")
    _validate_state(case, gold["initial"], label=f"{case.case_id}:initial")
    _validate_state(case, gold["final"], label=f"{case.case_id}:final")
    expected = gold["expected_plan"]
    floor = int(expected["execution_replay_floor"])
    if not 0 <= floor <= len(case.initial_evidence):
        raise ValueError("gold replay floor is out of range")
    grading = gold["grading"]
    evidence_ids = set(case.evidence_ids)
    for name in ("required_evidence_ids", "forbidden_support_evidence_ids"):
        values = set(str(item) for item in grading[name])
        if values - evidence_ids:
            raise ValueError(f"grading {name} contains unknown evidence IDs")
    for name in ("required_facts", "stable_facts"):
        for fact in grading[name]:
            _validate_fact(fact, evidence_ids=evidence_ids, label=name)
            slots = {
                item.slot_id: set(item.allowed_values) for item in case.decision_slots
            }
            if fact["slot"] not in slots or fact["value"] not in slots[fact["slot"]]:
                raise ValueError(
                    f"grading {name} is outside the public decision schema"
                )


def _fact_check(
    card: ReasoningCard,
    expected: Mapping[str, Any],
) -> bool:
    expected_ids = set(str(item) for item in expected["evidence_ids"])
    for fact in card.decision_facts:
        if fact.slot != str(expected["slot"]) or fact.value != str(expected["value"]):
            continue
        if expected_ids <= set(fact.evidence_ids):
            return True
    return False


def grade_card(
    card_value: Mapping[str, Any],
    gold: Mapping[str, Any],
) -> dict[str, Any]:
    card = ReasoningCard.from_mapping(card_value)
    final = gold["final"]
    grading = gold["grading"]
    support = set(card.evidence_ids)
    for fact in card.decision_facts:
        support.update(fact.evidence_ids)
    required_evidence = set(str(item) for item in grading["required_evidence_ids"])
    forbidden = set(str(item) for item in grading["forbidden_support_evidence_ids"])
    gold_support = set(str(item) for item in final["evidence_ids"])
    expected_invalidated = set(str(item) for item in final["invalidated_evidence_ids"])
    checks = {
        "answer_exact": card.current_answer == str(final["answer"]),
        "required_facts_exact": all(
            _fact_check(card, item) for item in grading["required_facts"]
        ),
        "stable_facts_exact": all(
            _fact_check(card, item) for item in grading["stable_facts"]
        ),
        "required_evidence_present": required_evidence <= support,
        "forbidden_support_absent": not bool(forbidden & support),
        "expected_invalidated_evidence_marked": (
            expected_invalidated <= set(card.invalidated_evidence_ids)
        ),
    }
    true_positive = len(support & gold_support)
    precision = true_positive / len(support) if support else 0.0
    recall = true_positive / len(gold_support) if gold_support else 1.0
    return {
        "machine_success": all(checks.values()),
        "evidence_consistent": all(
            value for name, value in checks.items() if name != "answer_exact"
        ),
        "checks": checks,
        "support_evidence_ids": sorted(support),
        "unexpected_support_evidence_ids": sorted(support - gold_support),
        "missing_required_evidence_ids": sorted(required_evidence - support),
        "citation_precision": precision,
        "citation_recall": recall,
    }


def _grade_initial(trace: Mapping[str, Any], gold: Mapping[str, Any]) -> dict[str, Any]:
    card = ReasoningCard.from_mapping(trace["shared_initial_trace"][-1])
    initial = gold["initial"]
    return {
        "answer_exact": card.current_answer == initial["answer"],
        "expected_answer": initial["answer"],
        "observed_answer": card.current_answer,
    }


def _count_stale_cards(
    cards: Sequence[Mapping[str, Any]],
    forbidden_ids: Sequence[str],
) -> int:
    forbidden = set(forbidden_ids)
    count = 0
    for value in cards:
        card = ReasoningCard.from_mapping(value)
        support = set(card.evidence_ids)
        for fact in card.decision_facts:
            support.update(fact.evidence_ids)
        if forbidden & support and not forbidden <= set(card.invalidated_evidence_ids):
            count += 1
    return count


def grade_trace(trace: Mapping[str, Any], gold: Mapping[str, Any]) -> dict[str, Any]:
    expected_plan = gold["expected_plan"]
    plan = trace["replay_plan"]
    plan_checks = {
        "event_triggered": (
            bool(plan["event_triggered"]) == bool(expected_plan["event_triggered"])
        ),
        "execution_replay_floor": (
            int(plan["execution_replay_floor"])
            == int(expected_plan["execution_replay_floor"])
        ),
        "pre_outcome": plan["pre_outcome"] is True,
        "trajectory_horizon_shadow_only": (
            plan["trajectory_horizon_status"] == "shadow_only_not_executed"
        ),
    }
    lane_grades: dict[str, Any] = {}
    forbidden = gold["grading"]["forbidden_support_evidence_ids"]
    for lane in LANES:
        lane_payload = trace["lanes"][lane]
        lane_grades[lane] = {
            **grade_card(lane_payload["final_card"], gold),
            "stale_historical_cards": _count_stale_cards(
                lane_payload["cards"], forbidden
            ),
        }
    full_answer = trace["lanes"]["full_restart"]["final_card"]["current_answer"]
    selective_answer = trace["lanes"]["selective_replay"]["final_card"][
        "current_answer"
    ]
    forward_answer = trace["lanes"]["card_only_forward"]["final_card"]["current_answer"]
    return {
        "initial": _grade_initial(trace, gold),
        "observer_route": {
            "success": all(plan_checks.values()),
            "checks": plan_checks,
        },
        "lanes": lane_grades,
        "paired": {
            "selective_full_answer_match": selective_answer == full_answer,
            "forward_full_answer_match": forward_answer == full_answer,
            "selective_replay_cards_saved_vs_full": (
                trace["lanes"]["full_restart"]["regenerated_cards"]
                - trace["lanes"]["selective_replay"]["regenerated_cards"]
            ),
        },
    }


def _rotated_lane_order(index: int) -> tuple[str, ...]:
    shift = index % len(LANES)
    return (*LANES[shift:], *LANES[:shift])


def run_suite(
    *,
    cases: Sequence[CaseSpec],
    gold: Mapping[str, Mapping[str, Any]],
    provider: Any,
    observer: Any,
    event_threshold: float,
    trials: int,
    mode: str,
) -> dict[str, Any]:
    if trials <= 0:
        raise ValueError("trials must be positive")
    runs: list[dict[str, Any]] = []
    for trial_index in range(trials):
        for case_index, case in enumerate(cases):
            lane_order = _rotated_lane_order(trial_index + case_index)
            trace = execute_language_replay_case(
                case,
                provider=provider,
                observer=observer,
                lane_order=lane_order,
                event_threshold=event_threshold,
            )
            grade = grade_trace(trace, gold[case.case_id])
            runs.append(
                {
                    "run_id": f"{mode}:{trial_index}:{case.case_id}",
                    "mode": mode,
                    "trial_index": trial_index,
                    "case_id": case.case_id,
                    "family": case.family,
                    "lane_order": list(lane_order),
                    "trace": trace,
                    "grade": grade,
                }
            )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "DEV_DRAFT",
        "promotion_eligible": False,
        "mode": mode,
        "trials": trials,
        "case_ids": [case.case_id for case in cases],
        "runs": runs,
        "summary": summarize_runs(runs),
    }


def _mean(values: Sequence[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _median(values: Sequence[float]) -> float | None:
    return statistics.median(values) if values else None


def summarize_runs(runs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    lane_summary: dict[str, Any] = {}
    for lane in LANES:
        grades = [run["grade"]["lanes"][lane] for run in runs]
        payloads = [run["trace"]["lanes"][lane] for run in runs]
        branch = [item["branch_accounting"] for item in payloads]
        counterfactual = [item["counterfactual_total_accounting"] for item in payloads]
        exact_tokens = bool(branch) and all(
            item["exact_provider_tokens"] for item in branch
        )
        exact_counterfactual_tokens = bool(counterfactual) and all(
            item["exact_provider_tokens"] for item in counterfactual
        )
        lane_summary[lane] = {
            "runs": len(runs),
            "machine_successes": sum(item["machine_success"] for item in grades),
            "answer_exact": sum(item["checks"]["answer_exact"] for item in grades),
            "evidence_consistent": sum(item["evidence_consistent"] for item in grades),
            "mean_citation_precision": _mean(
                [float(item["citation_precision"]) for item in grades]
            ),
            "mean_citation_recall": _mean(
                [float(item["citation_recall"]) for item in grades]
            ),
            "regenerated_cards": sum(item["regenerated_cards"] for item in payloads),
            "branch_logical_calls": sum(item["logical_calls"] for item in branch),
            "branch_api_calls": sum(item["api_calls"] for item in branch),
            "median_branch_latency_ms": _median(
                [float(item["latency_ms"]) for item in branch]
            ),
            "exact_provider_tokens": exact_tokens,
            "branch_input_tokens": (
                sum(int(item["input_tokens"]) for item in branch)
                if exact_tokens
                else None
            ),
            "branch_output_tokens": (
                sum(int(item["output_tokens"]) for item in branch)
                if exact_tokens
                else None
            ),
            "branch_reasoning_tokens": (
                sum(int(item["reasoning_tokens"]) for item in branch)
                if exact_tokens
                else None
            ),
            "counterfactual_logical_calls": sum(
                int(item["logical_calls"]) for item in counterfactual
            ),
            "counterfactual_api_calls": sum(
                int(item["api_calls"]) for item in counterfactual
            ),
            "median_counterfactual_latency_ms": _median(
                [float(item["latency_ms"]) for item in counterfactual]
            ),
            "counterfactual_exact_provider_tokens": exact_counterfactual_tokens,
            "counterfactual_input_tokens": (
                sum(int(item["input_tokens"]) for item in counterfactual)
                if exact_counterfactual_tokens
                else None
            ),
            "counterfactual_output_tokens": (
                sum(int(item["output_tokens"]) for item in counterfactual)
                if exact_counterfactual_tokens
                else None
            ),
            "counterfactual_reasoning_tokens": (
                sum(int(item["reasoning_tokens"]) for item in counterfactual)
                if exact_counterfactual_tokens
                else None
            ),
        }
    full = lane_summary["full_restart"]
    selective = lane_summary["selective_replay"]
    full_success_mask = [
        run["grade"]["lanes"]["full_restart"]["machine_success"] for run in runs
    ]
    selective_on_full = [
        run["grade"]["lanes"]["selective_replay"]["machine_success"]
        for run, full_success in zip(runs, full_success_mask, strict=True)
        if full_success
    ]
    route_successes = sum(run["grade"]["observer_route"]["success"] for run in runs)
    cards_saved = sum(
        run["grade"]["paired"]["selective_replay_cards_saved_vs_full"] for run in runs
    )
    full_cards = full["regenerated_cards"]
    receipts = [receipt for run in runs for receipt in _all_receipts(run["trace"])]
    returned_model_values = [receipt.get("returned_model") for receipt in receipts]
    tier_values = [receipt["metadata"].get("service_tier") for receipt in receipts]
    returned_models = set(returned_model_values)
    tiers = set(tier_values)
    token_savings = None
    if full["exact_provider_tokens"] and selective["exact_provider_tokens"]:
        token_savings = {
            "input_tokens": full["branch_input_tokens"]
            - selective["branch_input_tokens"],
            "output_tokens": full["branch_output_tokens"]
            - selective["branch_output_tokens"],
            "reasoning_tokens": (
                full["branch_reasoning_tokens"] - selective["branch_reasoning_tokens"]
            ),
        }
    counterfactual_token_savings = None
    if (
        full["counterfactual_exact_provider_tokens"]
        and selective["counterfactual_exact_provider_tokens"]
    ):
        counterfactual_token_savings = {
            "input_tokens": (
                full["counterfactual_input_tokens"]
                - selective["counterfactual_input_tokens"]
            ),
            "output_tokens": (
                full["counterfactual_output_tokens"]
                - selective["counterfactual_output_tokens"]
            ),
            "reasoning_tokens": (
                full["counterfactual_reasoning_tokens"]
                - selective["counterfactual_reasoning_tokens"]
            ),
        }
    return {
        "runs": len(runs),
        "observer_route_successes": route_successes,
        "lane_summary": lane_summary,
        "paired": {
            "selective_machine_success_on_full_success": (
                sum(selective_on_full) / len(selective_on_full)
                if selective_on_full
                else None
            ),
            "selective_replay_cards_saved_vs_full": cards_saved,
            "selective_replay_card_ratio": (
                selective["regenerated_cards"] / full_cards if full_cards else None
            ),
            "selective_branch_token_savings_vs_full": token_savings,
            "selective_counterfactual_token_savings_vs_full": (
                counterfactual_token_savings
            ),
            "forward_rescued_by_selective": sum(
                (not run["grade"]["lanes"]["card_only_forward"]["machine_success"])
                and run["grade"]["lanes"]["selective_replay"]["machine_success"]
                for run in runs
            ),
            "forward_harmed_by_selective": sum(
                run["grade"]["lanes"]["card_only_forward"]["machine_success"]
                and (not run["grade"]["lanes"]["selective_replay"]["machine_success"])
                for run in runs
            ),
        },
        "live_comparability": {
            "receipt_count": len(receipts),
            "returned_models": sorted(str(item) for item in returned_models),
            "service_tiers": sorted(str(item) for item in tiers),
            "single_returned_model": (
                bool(receipts)
                and None not in returned_models
                and len(returned_models) == 1
            ),
            "single_service_tier": (
                bool(receipts) and None not in tiers and len(tiers) == 1
            ),
            "all_attempts_completed": bool(receipts)
            and all(
                receipt["metadata"].get("attempt_outcome") == "completed"
                for receipt in receipts
            ),
            "no_seed_claim": True,
        },
        "claim_boundary": [
            "Scripted results prove bridge plumbing only, not language reasoning.",
            "Live smoke results are DEV observations, not a promotion benchmark or a general accuracy claim.",
            "Card-only forward is a public-card continuation control, not a universal chat-model baseline.",
            "Token savings are reported only from exact provider usage; no price estimate is inferred.",
        ],
    }


def _all_receipts(trace: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    receipts = [item["receipt"] for item in trace["shared_initial_calls"]]
    receipts.append(trace["revision_observation"]["receipt"])
    for lane in LANES:
        receipts.extend(
            item["receipt"] for item in trace["lanes"][lane]["branch_calls"]
        )
    return receipts


def _validate_live_receipts(
    result: Mapping[str, Any],
    lock: Mapping[str, Any],
    *,
    provider_audit_receipts: Sequence[Mapping[str, Any]],
    observer_audit_receipts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    live = lock["live_provider"]
    expected_model = str(live["model"])
    expected_tier = str(live["service_tier"])
    expected_reasoning_effort = str(live["reasoning_effort"])
    trace_receipts = [
        receipt for run in result["runs"] for receipt in _all_receipts(run["trace"])
    ]
    if not trace_receipts:
        raise RuntimeError("live run produced no provider receipts")
    for index, receipt in enumerate(trace_receipts):
        metadata = receipt["metadata"]
        usage = receipt["usage"]
        checks = {
            "provider": receipt.get("provider") == "openai_responses",
            "requested_model": receipt.get("requested_model") == expected_model,
            "returned_model": receipt.get("returned_model") == expected_model,
            "service_tier": metadata.get("service_tier") == expected_tier,
            "status": metadata.get("status") == "completed",
            "attempt_outcome": metadata.get("attempt_outcome") == "completed",
            "failure_type": metadata.get("failure_type") is None,
            "refusal_count": metadata.get("refusal_count") == 0,
            "attempt": metadata.get("attempt") == 1,
            "retry_count": metadata.get("retry_count") == 0,
            "reasoning_effort": (
                metadata.get("reasoning_effort") == expected_reasoning_effort
            ),
            "store": metadata.get("store") is False,
            "previous_response_id": metadata.get("previous_response_id") is False,
            "truncation": metadata.get("truncation") == "disabled",
            "logical_calls": receipt.get("logical_calls") == 1,
            "api_calls": receipt.get("api_calls") == 1,
            "exact_provider_tokens": usage.get("exact_provider_tokens") is True,
        }
        failed = sorted(name for name, passed in checks.items() if not passed)
        if failed:
            raise RuntimeError(
                f"live receipt {index} failed locked parity fields: {failed}"
            )

    expected_audit_receipts = [
        receipt
        for run in result["runs"]
        for receipt in (
            [item["receipt"] for item in run["trace"]["shared_initial_calls"]]
            + [
                item["receipt"]
                for lane in run["lane_order"]
                for item in run["trace"]["lanes"][lane]["branch_calls"]
            ]
        )
    ]
    expected_observer_receipts = [
        run["trace"]["revision_observation"]["receipt"] for run in result["runs"]
    ]
    if any(
        receipt["metadata"].get("max_output_tokens")
        != int(live["max_card_output_tokens"])
        for receipt in provider_audit_receipts
    ):
        raise RuntimeError("card provider receipt output cap drifted from lock")
    if any(
        receipt["metadata"].get("max_output_tokens")
        != int(live["max_observer_output_tokens"])
        for receipt in observer_audit_receipts
    ):
        raise RuntimeError("observer receipt output cap drifted from lock")
    if canonical_json(list(provider_audit_receipts)) != canonical_json(
        expected_audit_receipts
    ):
        raise RuntimeError("provider audit receipts do not match successful trace")
    if canonical_json(list(observer_audit_receipts)) != canonical_json(
        expected_observer_receipts
    ):
        raise RuntimeError("observer audit receipts do not match successful trace")
    return {
        "status": "PASS",
        "receipt_count": len(trace_receipts),
        "provider_receipt_count": len(provider_audit_receipts),
        "observer_receipt_count": len(observer_audit_receipts),
        "requested_model": expected_model,
        "returned_model": expected_model,
        "service_tier": expected_tier,
    }


def _lane_rows(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in result["runs"]:
        for lane in LANES:
            payload = run["trace"]["lanes"][lane]
            grade = run["grade"]["lanes"][lane]
            branch = payload["branch_accounting"]
            counterfactual = payload["counterfactual_total_accounting"]
            rows.append(
                {
                    "run_id": run["run_id"],
                    "trial_index": run["trial_index"],
                    "case_id": run["case_id"],
                    "family": run["family"],
                    "lane": lane,
                    "lane_order": ">".join(run["lane_order"]),
                    "plan_fingerprint": run["trace"]["replay_plan"]["plan_fingerprint"],
                    "observer_route_success": run["grade"]["observer_route"]["success"],
                    "execution_replay_floor": run["trace"]["replay_plan"][
                        "execution_replay_floor"
                    ],
                    "regenerated_cards": payload["regenerated_cards"],
                    "machine_success": grade["machine_success"],
                    "answer_exact": grade["checks"]["answer_exact"],
                    "evidence_consistent": grade["evidence_consistent"],
                    "citation_precision": grade["citation_precision"],
                    "citation_recall": grade["citation_recall"],
                    "stale_historical_cards": grade["stale_historical_cards"],
                    "branch_logical_calls": branch["logical_calls"],
                    "branch_api_calls": branch["api_calls"],
                    "branch_latency_ms": branch["latency_ms"],
                    "input_tokens": branch["input_tokens"],
                    "output_tokens": branch["output_tokens"],
                    "reasoning_tokens": branch["reasoning_tokens"],
                    "counterfactual_api_calls": counterfactual["api_calls"],
                    "counterfactual_input_tokens": counterfactual["input_tokens"],
                    "counterfactual_output_tokens": counterfactual["output_tokens"],
                    "counterfactual_reasoning_tokens": counterfactual[
                        "reasoning_tokens"
                    ],
                    "final_answer": payload["final_card"]["current_answer"],
                }
            )
    return rows


def _call_rows(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in result["runs"]:
        trace = run["trace"]
        for item in trace["shared_initial_calls"]:
            rows.append(
                {
                    "run_id": run["run_id"],
                    "case_id": run["case_id"],
                    "lane": "shared",
                    **item,
                }
            )
        rows.append(
            {
                "run_id": run["run_id"],
                "case_id": run["case_id"],
                "lane": "observer",
                "phase": "revision_observer",
                "observation": trace["revision_observation"],
            }
        )
        for lane in LANES:
            for item in trace["lanes"][lane]["branch_calls"]:
                rows.append(
                    {
                        "run_id": run["run_id"],
                        "case_id": run["case_id"],
                        "lane": lane,
                        **item,
                    }
                )
    return rows


def _write_json(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(
            value, handle, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False
        )
        handle.write("\n")


def _write_jsonl(path: Path, values: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for value in values:
            handle.write(canonical_json(value))
            handle.write("\n")


def _report_markdown(result: Mapping[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# EBRT v0.4 Language Replay Bridge — DEV report",
        "",
        f"Mode: `{result['mode']}`  ",
        f"Runs: `{summary['runs']}`  ",
        f"Observer route matches DEV gold: `{summary['observer_route_successes']}/{summary['runs']}`",
        "",
        "| Lane | Machine success | Cards regenerated | Branch API calls | Branch input tokens | Branch output tokens |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for lane in LANES:
        item = summary["lane_summary"][lane]
        lines.append(
            "| {lane} | {success}/{runs} | {cards} | {calls} | {input_tokens} | {output_tokens} |".format(
                lane=lane,
                success=item["machine_successes"],
                runs=item["runs"],
                cards=item["regenerated_cards"],
                calls=item["branch_api_calls"],
                input_tokens=item["branch_input_tokens"]
                if item["branch_input_tokens"] is not None
                else "n/a",
                output_tokens=item["branch_output_tokens"]
                if item["branch_output_tokens"] is not None
                else "n/a",
            )
        )
    paired = summary["paired"]
    lines.extend(
        [
            "",
            "Counterfactual totals charge the shared initial trace and the observer to every lane:",
            "",
            "| Lane | Total API calls | Total input tokens | Total output tokens |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for lane in LANES:
        item = summary["lane_summary"][lane]
        lines.append(
            "| {lane} | {calls} | {input_tokens} | {output_tokens} |".format(
                lane=lane,
                calls=item["counterfactual_api_calls"],
                input_tokens=item["counterfactual_input_tokens"]
                if item["counterfactual_input_tokens"] is not None
                else "n/a",
                output_tokens=item["counterfactual_output_tokens"]
                if item["counterfactual_output_tokens"] is not None
                else "n/a",
            )
        )
    lines.extend(
        [
            "",
            f"Selective cards saved versus full restart: `{paired['selective_replay_cards_saved_vs_full']}`.",
            f"Selective/full replay-card ratio: `{paired['selective_replay_card_ratio']:.4f}`.",
            "",
            "This is non-promotional DEV evidence. Scripted mode is plumbing-only; live-smoke mode is not a general LLM accuracy benchmark.",
            "",
        ]
    )
    return "\n".join(lines)


def write_bundle(
    result: Mapping[str, Any],
    output_dir: Path,
    *,
    source_snapshot: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    expected_sources = dict(source_snapshot or _source_snapshot())
    _assert_source_snapshot(expected_sources)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(
            f"refusing to overwrite nonempty output directory: {output_dir}"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    lane_rows = _lane_rows(result)
    call_rows = _call_rows(result)
    public_runs = [
        {key: value for key, value in run.items() if key != "trace"}
        | {
            "trace_fingerprint": run["trace"]["trace_fingerprint"],
            "plan_fingerprint": run["trace"]["replay_plan"]["plan_fingerprint"],
        }
        for run in result["runs"]
    ]
    public_results = {key: value for key, value in result.items() if key != "runs"} | {
        "runs": public_runs
    }
    _write_json(output_dir / "results.json", public_results)
    _write_jsonl(
        output_dir / "traces.jsonl",
        [
            {
                "run_id": run["run_id"],
                "case_id": run["case_id"],
                "trace": run["trace"],
            }
            for run in result["runs"]
        ],
    )
    _write_jsonl(output_dir / "calls.jsonl", call_rows)
    with (output_dir / "lane_rows.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(lane_rows[0]))
        writer.writeheader()
        writer.writerows(lane_rows)
    (output_dir / "benchmark_report.md").write_text(
        _report_markdown(result), encoding="utf-8"
    )
    artifact_paths = [
        output_dir / "results.json",
        output_dir / "traces.jsonl",
        output_dir / "calls.jsonl",
        output_dir / "lane_rows.csv",
        output_dir / "benchmark_report.md",
    ]
    _assert_source_snapshot(expected_sources)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "DEV_DRAFT",
        "promotion_eligible": False,
        "complete": True,
        "mode": result["mode"],
        "case_ids": result["case_ids"],
        "trials": result["trials"],
        "result_fingerprint": fingerprint(public_results),
        "source_sha256": expected_sources,
        "artifact_sha256": {path.name: _sha256(path) for path in artifact_paths},
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "claim_boundary": result["summary"]["claim_boundary"],
    }
    manifest_path = output_dir / "manifest.json"
    _write_json(manifest_path, manifest)
    try:
        _assert_source_snapshot(expected_sources)
    except RuntimeError:
        manifest_path.unlink(missing_ok=True)
        raise
    return manifest


def _write_failure_bundle(
    output_dir: Path,
    *,
    mode: str,
    case_ids: Sequence[str],
    trials: int,
    source_snapshot: Mapping[str, str],
    provider_audit_receipts: Sequence[Mapping[str, Any]],
    observer_audit_receipts: Sequence[Mapping[str, Any]],
    error: BaseException,
) -> dict[str, Any]:
    if (output_dir / "manifest.json").exists():
        raise RuntimeError("refusing to add a failure record to a complete bundle")
    output_dir.mkdir(parents=True, exist_ok=True)
    failure = {
        "schema_version": SCHEMA_VERSION,
        "status": "DEV_DRAFT",
        "promotion_eligible": False,
        "complete": False,
        "mode": mode,
        "case_ids": list(case_ids),
        "trials": int(trials),
        "failure_category": type(error).__name__,
        "provider_audit_receipts": list(provider_audit_receipts),
        "observer_audit_receipts": list(observer_audit_receipts),
        "source_sha256_at_start": dict(source_snapshot),
        "source_snapshot_still_matches": (_source_snapshot() == dict(source_snapshot)),
        "claim_boundary": [
            "This is an incomplete failure record, not canonical benchmark evidence.",
            "No accuracy, model-parity, or token-savings claim may be made from this record.",
            "Only sanitized counted-call receipts are persisted; raw provider errors and responses are excluded.",
        ],
    }
    serialized = canonical_json(failure)
    if "OPENAI_API_KEY" in serialized or "Authorization" in serialized:
        raise AssertionError("secret-bearing field leaked into failure record")
    _write_json(output_dir / "failure.json", failure)
    failure_manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "DEV_DRAFT",
        "promotion_eligible": False,
        "complete": False,
        "failure_category": type(error).__name__,
        "failure_sha256": _sha256(output_dir / "failure.json"),
    }
    _write_json(output_dir / "failure_manifest.json", failure_manifest)
    return failure_manifest


def _scripted_states(gold: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    return {
        case_id: {"initial": value["initial"], "final": value["final"]}
        for case_id, value in gold.items()
    }


def _select_cases(
    cases: Sequence[CaseSpec],
    requested_ids: Sequence[str],
) -> list[CaseSpec]:
    by_id = {case.case_id: case for case in cases}
    unknown = set(requested_ids) - set(by_id)
    if unknown:
        raise ValueError(f"unknown case IDs: {sorted(unknown)}")
    return [by_id[item] for item in requested_ids]


def run_self_tests() -> dict[str, Any]:
    _assert_source_snapshot(BOOT_SOURCE_SNAPSHOT)
    lock = _load_lock()
    cases, gold, gold_file = _load_suite()
    if len(cases) != int(lock["fixtures"]["case_count"]):
        raise AssertionError("policy lock case count mismatch")
    bridge = run_bridge_self_tests()
    from openai_reasoning_provider_v0_4 import schema_self_test

    schemas = schema_self_test()
    result = run_suite(
        cases=cases,
        gold=gold,
        provider=ScriptedReasoningProvider(_scripted_states(gold)),
        observer=StructuredRevisionObserver(),
        event_threshold=float(lock["route"]["event_threshold"]),
        trials=1,
        mode="scripted_plumbing",
    )
    if result["summary"]["observer_route_successes"] != len(cases):
        raise AssertionError("structured observer did not reproduce expected DEV plans")
    for lane in LANES:
        if result["summary"]["lane_summary"][lane]["machine_successes"] != len(cases):
            raise AssertionError(f"scripted plumbing lane failed: {lane}")
        for run in result["runs"]:
            payload = run["trace"]["lanes"][lane]
            if payload["observer_accounting_included"] is not True:
                raise AssertionError(f"observer cost missing from lane total: {lane}")
            expected_calls = (
                payload["common_initial_accounting"]["logical_calls"]
                + run["trace"]["revision_observation"]["receipt"]["logical_calls"]
                + payload["branch_accounting"]["logical_calls"]
            )
            if (
                payload["counterfactual_total_accounting"]["logical_calls"]
                != expected_calls
            ):
                raise AssertionError(f"counterfactual accounting is asymmetric: {lane}")
    no_op = next(run for run in result["runs"] if run["case_id"] == "unrelated_noop")
    if no_op["trace"]["lanes"]["selective_replay"]["regenerated_cards"] != 1:
        raise AssertionError("irrelevant no-op performed backward replay")
    sentinel = str(gold_file["provider_access"])
    if any(sentinel in canonical_json(case.public_context()) for case in cases):
        raise AssertionError("gold-only sentinel leaked into public case context")

    first_run = result["runs"][0]
    negative_card = dict(first_run["trace"]["lanes"]["full_restart"]["final_card"])
    forbidden = gold[first_run["case_id"]]["grading"]["forbidden_support_evidence_ids"][
        0
    ]
    negative_card["evidence_ids"] = [*negative_card["evidence_ids"], forbidden]
    if grade_card(negative_card, gold[first_run["case_id"]])["machine_success"]:
        raise AssertionError("grader accepted retracted evidence as active support")

    repeat = run_suite(
        cases=cases,
        gold=gold,
        provider=ScriptedReasoningProvider(_scripted_states(gold)),
        observer=StructuredRevisionObserver(),
        event_threshold=float(lock["route"]["event_threshold"]),
        trials=1,
        mode="scripted_plumbing",
    )
    if canonical_json(result) != canonical_json(repeat):
        raise AssertionError("scripted benchmark is not byte deterministic")
    source_snapshot = _source_snapshot()
    bad_snapshot = dict(source_snapshot)
    first_source = SOURCE_FILES[0]
    bad_snapshot[first_source] = "0" * 64
    try:
        _assert_source_snapshot(bad_snapshot)
    except RuntimeError:
        pass
    else:
        raise AssertionError("source drift sentinel did not fail closed")
    with tempfile.TemporaryDirectory(prefix="ebrt-v04-failure-self-test-") as temp_dir:
        failure_output = Path(temp_dir) / "failure-bundle"
        _write_failure_bundle(
            failure_output,
            mode="self_test_failure",
            case_ids=[cases[0].case_id],
            trials=1,
            source_snapshot=source_snapshot,
            provider_audit_receipts=[],
            observer_audit_receipts=[],
            error=RuntimeError("PRIVATE_ERROR_MESSAGE_SENTINEL"),
        )
        failure = _load_json(failure_output / "failure.json")
        failure_text = canonical_json(failure)
        if (
            failure["complete"] is not False
            or failure["promotion_eligible"] is not False
        ):
            raise AssertionError(
                "failure bundle was not marked incomplete/non-promotional"
            )
        if (failure_output / "manifest.json").exists():
            raise AssertionError("failure bundle wrote a success manifest")
        if "PRIVATE_ERROR_MESSAGE_SENTINEL" in failure_text:
            raise AssertionError("raw failure message leaked into failure bundle")
    return {
        "status": "PASS",
        "schema_version": SCHEMA_VERSION,
        "case_count": len(cases),
        "bridge": bridge,
        "openai_schemas": schemas,
        "checks": [
            "fixture/gold separation and schema validation",
            "all three scripted plumbing lanes machine-grade successfully",
            "pre-outcome route matches structured DEV annotations",
            "irrelevant late evidence performs no backward replay",
            "retracted-support negative sentinel fails grading",
            "gold-only sentinel absent from public provider context",
            "observer accounting is charged symmetrically to every lane",
            "source drift sentinel fails closed before artifact completion",
            "sanitized incomplete failure bundle excludes raw error text",
            "full scripted bundle is byte deterministic",
        ],
    }


def _run_fake(output: Path, trials: int) -> dict[str, Any]:
    source_snapshot = dict(BOOT_SOURCE_SNAPSHOT)
    _assert_source_snapshot(source_snapshot)
    lock = _load_lock()
    cases, gold, _ = _load_suite()
    _assert_source_snapshot(source_snapshot)
    result = run_suite(
        cases=cases,
        gold=gold,
        provider=ScriptedReasoningProvider(_scripted_states(gold)),
        observer=StructuredRevisionObserver(),
        event_threshold=float(lock["route"]["event_threshold"]),
        trials=trials,
        mode="scripted_plumbing",
    )
    manifest = write_bundle(result, output, source_snapshot=source_snapshot)
    return {"output": str(output), "summary": result["summary"], "manifest": manifest}


def _run_live(
    output: Path,
    case_ids: Sequence[str],
    trials: int,
) -> dict[str, Any]:
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        raise RuntimeError("OPENAI_API_KEY is not available in the process environment")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(
            f"refusing to overwrite nonempty output directory: {output}"
        )
    source_snapshot = dict(BOOT_SOURCE_SNAPSHOT)
    _assert_source_snapshot(source_snapshot)
    lock = _load_lock()
    cases, gold, _ = _load_suite()
    selected = _select_cases(cases, case_ids)
    _assert_source_snapshot(source_snapshot)
    live = lock["live_provider"]
    from openai_reasoning_provider_v0_4 import (
        OpenAIResponsesReasoningProvider,
        OpenAIResponsesSemanticAdapter,
    )

    provider = OpenAIResponsesReasoningProvider(
        model=live["model"],
        reasoning_effort=live["reasoning_effort"],
        timeout_seconds=float(live["timeout_seconds"]),
        max_output_tokens=int(live["max_card_output_tokens"]),
    )
    observer = OpenAIResponsesSemanticAdapter(
        model=live["model"],
        reasoning_effort=live["reasoning_effort"],
        timeout_seconds=float(live["timeout_seconds"]),
        max_output_tokens=int(live["max_observer_output_tokens"]),
    )
    try:
        result = run_suite(
            cases=selected,
            gold=gold,
            provider=provider,
            observer=observer,
            event_threshold=float(lock["route"]["event_threshold"]),
            trials=trials,
            mode="openai_live_smoke",
        )
        result["summary"]["live_receipt_validation"] = _validate_live_receipts(
            result,
            lock,
            provider_audit_receipts=provider.audit_receipts,
            observer_audit_receipts=observer.audit_receipts,
        )
        _assert_source_snapshot(source_snapshot)
        manifest = write_bundle(
            result,
            output,
            source_snapshot=source_snapshot,
        )
    except Exception as exc:
        _write_failure_bundle(
            output,
            mode="openai_live_smoke",
            case_ids=[case.case_id for case in selected],
            trials=trials,
            source_snapshot=source_snapshot,
            provider_audit_receipts=provider.audit_receipts,
            observer_audit_receipts=observer.audit_receipts,
            error=exc,
        )
        raise
    return {"output": str(output), "summary": result["summary"], "manifest": manifest}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("self-test", help="run offline contract and grading tests")
    fake = subparsers.add_parser(
        "fake-dev", help="write deterministic plumbing evidence"
    )
    fake.add_argument("--output", type=Path, default=DEFAULT_FAKE_OUTPUT)
    fake.add_argument("--trials", type=int, default=1)
    live = subparsers.add_parser("live-smoke", help="run the locked GPT-5.6 canary")
    live.add_argument("--output", type=Path, default=DEFAULT_LIVE_OUTPUT)
    live.add_argument("--trials", type=int, default=1)
    live.add_argument(
        "--case-id",
        action="append",
        dest="case_ids",
        help="case ID to run; repeat for multiple cases",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "self-test":
        value = run_self_tests()
    elif args.command == "fake-dev":
        value = _run_fake(args.output, args.trials)
    else:
        lock = _load_lock()
        case_ids = args.case_ids or lock["fixtures"]["live_canary_case_ids"]
        value = _run_live(args.output, case_ids, args.trials)
    print(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
