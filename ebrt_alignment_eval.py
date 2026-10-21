#!/usr/bin/env python3
"""Predeclared numeric-control alignment and evidence-placement diagnostic.

Two engineered cases cross the production control-to-site assignment with a
fixed tuple permutation, and chronological with credit-first evidence order.
The permutation is auxiliary research material, never an admitted program in
the standard engine. Eight hosted attempts at most, with no retries.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

from ebrt_core import (
    ActuatorProgram, AdapterDescriptor, EBRTError, ModelResult, _canonical_bytes,
    _fingerprint, _grade_contract, _parse_model_text, _seal, _sealed_snapshot,
    _structural_model_checks, build_model_invocation,
)
from ebrt_alignment_cases import build_cases
from ebrt_demo import _prompt_records
from ebrt_engine import CoverageFirstActuator, validate_program
from ebrt_hosted import HostedConfig, HostedResponsesRuntime, PRIVACY, _open_output
from ebrt_support_eval import _check_provider
from local_output_diff_corpus_v0_8_2 import (
    _common_output_grade, _program_from_receipt, compile_revision,
)
from role_stratified_uptake_canary_v0_8_3 import (
    _output_diff, compiler_coverage, provider_uptake,
)


PLAN_SCHEMA = "ebrt-alignment-plan-v1"
REPORT_SCHEMA = "ebrt-alignment-diagnostic-v1"
ARMS = (
    "aligned_chronological", "permuted_chronological",
    "aligned_credit_first", "permuted_credit_first",
)
CALL_LIMIT = 8
SOURCE_FILES = (
    "ebrt_core.py", "ebrt_engine.py", "ebrt_demo.py", "ebrt_hosted.py",
    "local_output_diff_corpus_v0_8_2.py", "role_stratified_uptake_canary_v0_8_3.py",
    "ebrt_support_cases.py", "ebrt_support_eval.py",
    "ebrt_alignment_cases.py", "ebrt_alignment_eval.py",
)
FACTORS = {
    ARMS[0]: ("aligned", "chronological"),
    ARMS[1]: ("permuted", "chronological"),
    ARMS[2]: ("aligned", "credit_first"),
    ARMS[3]: ("permuted", "credit_first"),
}


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise EBRTError(reason)


def _config(material: Mapping[str, Any]) -> HostedConfig:
    try:
        config = HostedConfig(material["model"], material["reasoning_effort"],
                              material["max_output_tokens"], material["timeout_seconds"])
        _require(_canonical_bytes(config.to_dict()) == _canonical_bytes(material),
                 "ALIGNMENT_PLAN_MISMATCH")
        return config
    except (KeyError, TypeError, ValueError):
        raise EBRTError("ALIGNMENT_PLAN_MISMATCH") from None


def _sources() -> dict[str, str]:
    root = Path(__file__).resolve().parent
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in SOURCE_FILES}


def _permute_program(program: ActuatorProgram) -> ActuatorProgram:
    """Rotate numeric tuples only; IDs and their ordering remain fixed."""
    rows = program.reinspect
    _require(len(rows) == 3 and len({(row[1], row[2]) for row in rows}) == 3,
             "ALIGNMENT_ASYMMETRIC_CONTROL_REQUIRED")
    return replace(program, reinspect=tuple(
        (row[0], rows[(index + 1) % len(rows)][1], rows[(index + 1) % len(rows)][2])
        for index, row in enumerate(rows)
    ))


def _without_lines(prompt: str, prefixes: tuple[str, ...]) -> list[str]:
    return [line for line in prompt.splitlines() if not line.startswith(prefixes)]


def _matched_inputs(task, programs: Mapping[str, ActuatorProgram],
                    invocations: Mapping[str, Mapping[str, Any]]) -> dict[str, bool]:
    baseline = programs[ARMS[0]]
    baseline_dict = baseline.to_dict()
    fixed_fields = {key: value for key, value in baseline_dict.items()
                    if key not in {"reinspect", "fingerprint_sha256"}}
    expected_evidence = sorted(
        [{"evidence_id": row.evidence_id, "text": row.text} for row in task.evidence],
        key=lambda row: row["evidence_id"],
    )
    expected_data = _prompt_records(invocations[ARMS[0]])
    checks = {
        "same_task_and_full_evidence": expected_data[1] == expected_evidence and all(
            _prompt_records(invocation) == expected_data for invocation in invocations.values()),
        "same_selected_ids_and_reinspect_order": all(
            tuple(row[0] for row in program.reinspect) == tuple(row[0] for row in baseline.reinspect)
            for program in programs.values()),
        "same_non_numeric_program_fields": all(
            {key: value for key, value in program.to_dict().items()
             if key not in {"reinspect", "fingerprint_sha256"}} == fixed_fields
            for program in programs.values()),
        "same_numeric_tuple_multiset_and_selected_l2": all(
            sorted((row[1], row[2]) for row in program.reinspect)
            == sorted((row[1], row[2]) for row in baseline.reinspect)
            for program in programs.values()),
        "same_positive_three_slot_hundred_unit_budget": task.reinspection_count == 3 and all(
            len(program.reinspect) == 3 and sum(row[1] for row in program.reinspect) == 100
            and all(type(row[1]) is int and row[1] > 0 for row in program.reinspect)
            for program in programs.values()),
        "complete_declared_support_coverage": all(
            compiler_coverage(task, program)["status"] == "PASS" for program in programs.values()),
        "same_instruction_text": all(
            _without_lines(invocation["prompt"], ("EVIDENCE_JSON ", "REINSPECT_JSON "))
            == _without_lines(invocations[ARMS[0]]["prompt"], ("EVIDENCE_JSON ", "REINSPECT_JSON "))
            for invocation in invocations.values()),
        "alignment_pairs_change_only_numeric_assignment": all(
            _without_lines(invocations[left]["prompt"], ("REINSPECT_JSON ",))
            == _without_lines(invocations[right]["prompt"], ("REINSPECT_JSON ",))
            for left, right in ((ARMS[0], ARMS[1]), (ARMS[2], ARMS[3]))),
        "placement_pairs_change_only_evidence_order": all(
            _without_lines(invocations[left]["prompt"], ("EVIDENCE_JSON ",))
            == _without_lines(invocations[right]["prompt"], ("EVIDENCE_JSON ",))
            for left, right in ((ARMS[0], ARMS[2]), (ARMS[1], ARMS[3]))),
        "permutation_changes_every_selected_numeric_tuple": all(
            left[1:] != right[1:]
            for left, right in zip(baseline.reinspect, programs[ARMS[1]].reinspect, strict=True)),
        "placement_changes_evidence_order": invocations[ARMS[0]]["evidence_ids"]
            != invocations[ARMS[2]]["evidence_ids"],
    }
    return checks


def build_plan(config: HostedConfig) -> dict[str, Any]:
    """Fix all inputs, perturbations, contracts and eight-cell order offline."""
    cases = build_cases()
    _require(len(cases) == 2 and len({case.task.task_id for case in cases}) == 2,
             "ALIGNMENT_CASE_SET_INVALID")
    planned = []
    for case in cases:
        task = case.task
        _, core_receipt = compile_revision(task)
        aligned = CoverageFirstActuator().compile(task, core_receipt["trajectory"], lane_id="primary")
        validate_program(task, core_receipt["trajectory"], aligned, lane_id="primary")
        permuted = _permute_program(aligned)
        programs = {arm: aligned if FACTORS[arm][0] == "aligned" else permuted for arm in ARMS}
        invocations = {
            arm: build_model_invocation(task, programs[arm], prompt_policy=FACTORS[arm][1])
            for arm in ARMS
        }
        matched = _matched_inputs(task, programs, invocations)
        _require(all(matched.values()), "ALIGNMENT_MATCHED_INPUT_PREFLIGHT_FAILED")
        planned.append({
            "case_id": task.task_id, "family": case.family,
            "task": task.to_public_dict(), "contract": case.contract.to_dict(),
            "trajectory": core_receipt["trajectory"],
            "programs": {arm: program.to_dict() for arm, program in programs.items()},
            "invocations": invocations,
            "compiler_coverage": {arm: compiler_coverage(task, program) for arm, program in programs.items()},
            "matched_inputs": matched,
        })
    schedule = [{"case_id": case["case_id"], "arm_id": ARMS[(index + offset) % len(ARMS)]}
                for index, case in enumerate(planned) for offset in range(len(ARMS))]
    return _seal({
        "schema_version": PLAN_SCHEMA, "generation_config": config.to_dict(),
        "call_limit": CALL_LIMIT, "source_sha256": _sources(),
        "cases": planned, "schedule": schedule,
        "arm_factors": {arm: {"numeric_assignment": FACTORS[arm][0], "evidence_placement": FACTORS[arm][1]}
                        for arm in ARMS},
        "perturbation": "ROTATE_SELECTED_ALLOCATION_AND_SIGNED_CONTROL_TUPLES_LEFT_ONCE",
        "evidence_label": "FRESH_ENGINEERED_ALIGNMENT_PLACEMENT_DIAGNOSTIC",
        "actuator_admission": "AUXILIARY_PERTURBATION_STANDARD_ENGINE_UNCHANGED",
        "role_source": "CALLER_SUPPLIED_PUBLIC_ROLES",
    })


def _validated_plan(plan: Mapping[str, Any]) -> tuple[dict[str, Any], HostedConfig]:
    snapshot = _sealed_snapshot(plan, "ALIGNMENT_PLAN")
    try:
        config = _config(snapshot["generation_config"])
        expected = build_plan(config)
    except (KeyError, TypeError, ValueError, AttributeError):
        raise EBRTError("ALIGNMENT_PLAN_MISMATCH") from None
    _require(_canonical_bytes(snapshot) == _canonical_bytes(expected), "ALIGNMENT_PLAN_MISMATCH")
    return snapshot, config


def _descriptor(config: HostedConfig) -> AdapterDescriptor:
    return AdapterDescriptor(
        adapter_id="openai-alignment-diagnostic-v1", model_id="openai/" + config.model,
        interface_kind="hosted_api", state_visibility="public_only",
        differentiable_through_model=False,
        generation_config=tuple(sorted(config.to_dict().items())),
    )


def _score_cell(planned: Mapping[str, Any], case: Any, arm: str, raw_text: Any,
                receipt: Mapping[str, Any], index: int, config: HostedConfig) -> dict[str, Any]:
    invocation = planned["invocations"][arm]
    _check_provider(receipt, index, invocation, config)
    result = None
    error = receipt["error_code"]
    status = "PROVIDER_ERROR"
    if receipt["status"] == "COMPLETED":
        _require(isinstance(raw_text, str), "ALIGNMENT_RAW_TEXT_MISSING")
        try:
            answer, support = _parse_model_text(raw_text, task=case.task)
            result = {"answer": answer, "support_ids": list(support), "raw_text": raw_text}
            status = "PARSED"
        except EBRTError as failure:
            status, error = "FORMAT_ERROR", str(failure)
    else:
        _require(raw_text is None, "ALIGNMENT_ERROR_RAW_TEXT_INVALID")
    parsed = {"status": status, **(result or {})}
    program = _program_from_receipt(planned["programs"][arm])
    structural = {"status": "NOT_ASSESSED", "checks": {}}
    post_contract = {"status": "NOT_ASSESSED"}
    if result is not None:
        descriptor = _descriptor(config)
        model_result = ModelResult(
            answer=result["answer"], support_ids=tuple(result["support_ids"]),
            raw_text=raw_text, descriptor=descriptor,
            request_fingerprint_sha256=invocation["fingerprint_sha256"],
            latency_ms=receipt["latency_ms"],
        )
        checks = _structural_model_checks(
            case.task, program, model_result, expected_descriptor=descriptor,
            expected_request_fingerprint_sha256=invocation["fingerprint_sha256"],
        )
        structural = {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks}
        post_contract = _grade_contract(model_result, program, case.contract)
    return {
        "case_id": case.task.task_id, "arm_id": arm, "provider_receipt_index": index,
        "invocation_fingerprint_sha256": invocation["fingerprint_sha256"],
        "numeric_assignment": FACTORS[arm][0], "evidence_placement": FACTORS[arm][1],
        "status": status, "error_code": error, "raw_text": raw_text, "result": result,
        "grade": _common_output_grade(parsed, case.contract),
        "compiler_coverage": compiler_coverage(case.task, program),
        "provider_uptake": provider_uptake(case.task, program, parsed),
        "structural": structural, "post_run_contract": post_contract,
        "actuator_admission": "AUXILIARY_DIAGNOSTIC_ONLY",
    }


def _summary(cells: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    summary = {}
    for arm in ARMS:
        rows = [cell for cell in cells if cell["arm_id"] == arm]
        summary[arm] = {
            "case_count": len(rows),
            "answer_correct_count": sum(row["grade"]["checks"]["expected_answer"] for row in rows),
            "strict_pass_count": sum(row["grade"]["status"] == "PASS" for row in rows),
            "required_support_count": sum(row["grade"]["checks"]["required_support_present"] for row in rows),
            "compiler_coverage_count": sum(row["compiler_coverage"]["status"] == "PASS" for row in rows),
            "uptake_count": sum(row["provider_uptake"]["status"] == "PASS" for row in rows),
            "structural_pass_count": sum(row["structural"]["status"] == "PASS" for row in rows),
        }
    return summary


def _comparison(case_id: str, factor: str, held_constant: str,
                left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    parsed = left["status"] == right["status"] == "PARSED"
    difference = None
    if parsed:
        difference = _output_diff(left["arm_id"], left["result"], right["arm_id"], right["result"])
    return _seal({
        "case_id": case_id, "factor": factor, "held_constant": held_constant,
        "left_arm": left["arm_id"], "right_arm": right["arm_id"],
        "status": "ASSESSED" if parsed else "NOT_ASSESSED", "output_diff": difference,
        "strict_pass_transition": [left["grade"]["status"], right["grade"]["status"]] if parsed else None,
    })


def _derive_report(plan: Mapping[str, Any], config: HostedConfig,
                   receipts: Sequence[Mapping[str, Any]], raw_texts: Sequence[Any]) -> dict[str, Any]:
    _require(len(receipts) == len(raw_texts) == CALL_LIMIT, "ALIGNMENT_CELL_COUNT_MISMATCH")
    planned = {case["case_id"]: case for case in plan["cases"]}
    cases = {case.task.task_id: case for case in build_cases()}
    cells = [_score_cell(planned[entry["case_id"]], cases[entry["case_id"]], entry["arm_id"],
                         raw_texts[index], receipts[index], index, config)
             for index, entry in enumerate(plan["schedule"])]
    by_cell = {(row["case_id"], row["arm_id"]): row for row in cells}
    comparisons = [
        _comparison(case_id, factor, held, by_cell[(case_id, left)], by_cell[(case_id, right)])
        for case_id in planned
        for factor, held, left, right in (
            ("numeric_assignment", "chronological", ARMS[0], ARMS[1]),
            ("numeric_assignment", "credit_first", ARMS[2], ARMS[3]),
            ("evidence_placement", "aligned", ARMS[0], ARMS[2]),
            ("evidence_placement", "permuted", ARMS[1], ARMS[3]),
        )
    ]
    models = {receipt.get("returned_model") for receipt in receipts}
    matched = {
        "exactly_eight_attempts": len(receipts) == CALL_LIMIT,
        "same_generation_configuration": all(row["generation_config_fingerprint_sha256"]
            == _fingerprint(config.to_dict()) for row in receipts),
        "same_returned_model": len(models) == 1 and None not in models,
        "all_outputs_parsed": all(row["status"] == "PARSED" for row in cells),
        "all_predeclared_input_controls_hold": all(
            all(case["matched_inputs"].values()) for case in plan["cases"]),
    }
    return _seal({
        "schema_version": REPORT_SCHEMA, "plan_fingerprint_sha256": plan["fingerprint_sha256"],
        "status": "COMPLETE", "execution_status": "PASS" if all(matched.values()) else "FAIL",
        "privacy": PRIVACY, "evidence_label": "FRESH_ENGINEERED_ALIGNMENT_PLACEMENT_DIAGNOSTIC",
        "actual_provider_calls": len(receipts), "generation_config": config.to_dict(),
        "cells": cells, "provider_receipts": list(receipts), "summary": _summary(cells),
        "comparisons": comparisons, "matched_inputs": matched,
        "effect_attribution_status": "CONDITIONAL_ALIGNMENT_AND_PLACEMENT_DIAGNOSTIC",
        "gradient_specific_effect_status": "NOT_ASSESSED", "role_extraction_status": "NOT_ASSESSED",
        "claim_boundary": [
            "Two deliberately engineered cases and one serial call per cell, not a general quality estimate.",
            "All arms retain identical selected IDs, required-support coverage, full evidence, and instruction text.",
            "The numeric perturbation rotates existing allocation/control tuples and preserves their multiset and selected L2 norm.",
            "Selection and REINSPECT row ordering remain gradient-derived and shared; this is not a gradient-free control.",
            "The permutation is an auxiliary counterfactual and is not admitted by the standard production engine.",
            "Paired output differences are assessed only when both outputs parse; failed calls are never treated as equal outputs.",
            "The comparisons concern numeric alignment and evidence placement conditional on fixed coverage and text.",
            "Caller-supplied roles, role extraction, gradient superiority, and general reasoning improvements are not evaluated.",
            "COMPLETE records eight spent attempts; execution, integrity, and semantic grades are separate.",
            "Provider identifiers, usage and visible outputs are local receipts requiring review before export.",
        ],
    })


def run_plan(plan: Mapping[str, Any], *, client: Any = None) -> dict[str, Any]:
    snapshot, config = _validated_plan(plan)
    runtime = HostedResponsesRuntime(config, client, max_attempts=CALL_LIMIT)
    cases = {case["case_id"]: case for case in snapshot["cases"]}
    raw_texts = []
    for entry in snapshot["schedule"]:
        raw = None
        try:
            raw = runtime.generate(cases[entry["case_id"]]["invocations"][entry["arm_id"]])
        except EBRTError:
            # A sanitized provider error remains in this cell and spends its attempt.
            pass
        raw_texts.append(raw)
    report = _derive_report(snapshot, config, runtime.receipts, raw_texts)
    verify_report(report, snapshot)
    return report


def verify_report(report: Mapping[str, Any], plan: Mapping[str, Any]) -> dict[str, Any]:
    """Rebuild the fixed plan and every score from visible outputs and receipts."""
    snapshot, config = _validated_plan(plan)
    checked = _sealed_snapshot(report, "ALIGNMENT_REPORT")
    try:
        cells = checked["cells"]
        _require(isinstance(cells, list) and len(cells) == CALL_LIMIT, "ALIGNMENT_CELL_COUNT_MISMATCH")
        expected = _derive_report(snapshot, config, checked["provider_receipts"],
                                  [cell["raw_text"] for cell in cells])
    except (KeyError, TypeError, ValueError, AttributeError):
        raise EBRTError("ALIGNMENT_REPORT_MISMATCH") from None
    _require(_canonical_bytes(checked) == _canonical_bytes(expected), "ALIGNMENT_REPORT_MISMATCH")
    return _seal({
        "status": "PASS", "plan_fingerprint_sha256": snapshot["fingerprint_sha256"],
        "report_fingerprint_sha256": checked["fingerprint_sha256"],
        "execution_status": checked["execution_status"], "checked_cells": CALL_LIMIT,
        "meaning": "Internal receipt consistency, not provider authenticity or reasoning quality.",
    })


def render_text(report: Mapping[str, Any]) -> str:
    lines = [f"Alignment/placement diagnostic: {report['status']}; execution={report['execution_status']}",
             f"Provider attempts: {report['actual_provider_calls']}/{CALL_LIMIT}",
             "Arm                       Answer  Required support  Strict  Compiler  Uptake"]
    for arm, row in report["summary"].items():
        def count(key):
            return f"{row[key]}/{row['case_count']}"
        lines.append(f"{arm:<26} {count('answer_correct_count'):<7} {count('required_support_count'):<17} "
                     f"{count('strict_pass_count'):<7} {count('compiler_coverage_count'):<9} {count('uptake_count')}")
    assessed = [row for row in report["comparisons"] if row["status"] == "ASSESSED"]
    changed = sum(row["output_diff"]["raw_text_changed"] for row in assessed)
    lines.extend([f"Paired comparisons assessed: {len(assessed)}/{len(report['comparisons'])}; visible output changed: {changed}.",
                  "Auxiliary permutation; the standard engine's admission policy is unchanged.",
                  "Conditional numeric-alignment/placement diagnostic; gradient superiority is NOT_ASSESSED."])
    return "\n".join(lines) + "\n"


def _load(path: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        _require(isinstance(value, dict), "ALIGNMENT_JSON_INVALID")
        return value
    except (OSError, ValueError):
        raise EBRTError("ALIGNMENT_JSON_UNREADABLE") from None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan_cmd = commands.add_parser("plan", help="compile and seal eight inputs without API calls")
    plan_cmd.add_argument("--model", required=True)
    plan_cmd.add_argument("--reasoning-effort", default="low")
    plan_cmd.add_argument("--max-output-tokens", type=int, default=1024)
    plan_cmd.add_argument("--timeout", type=float, default=60.0)
    plan_cmd.add_argument("--output", required=True)
    run_cmd = commands.add_parser("run", help="one attempt per declared cell, eight at most")
    run_cmd.add_argument("--plan", required=True)
    run_cmd.add_argument("--output", required=True)
    verify_cmd = commands.add_parser("verify", help="recompute scores without API calls")
    verify_cmd.add_argument("--plan", required=True)
    verify_cmd.add_argument("--report", required=True)
    args = parser.parse_args(argv)
    output = None
    try:
        if args.command == "verify":
            result = verify_report(_load(args.report), _load(args.plan))
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.command == "plan":
            config = HostedConfig(args.model, args.reasoning_effort, args.max_output_tokens, args.timeout)
            result = build_plan(config)
            output = _open_output(args.output)
        else:
            plan = _load(args.plan)
            _validated_plan(plan)
            output = _open_output(args.output)
            result = run_plan(plan)
        json.dump(result, output, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        output.write("\n")
        print(f"Alignment plan saved: {CALL_LIMIT} declared attempts, no API calls."
              if args.command == "plan" else render_text(result), end="\n" if args.command == "plan" else "")
        return 0 if args.command == "plan" or result["execution_status"] == "PASS" else 1
    except EBRTError as error:
        if output:
            json.dump({"status": "ERROR", "privacy": PRIVACY, "error_code": str(error)}, output)
            output.write("\n")
        print(f"Alignment diagnostic failed: {error}", file=sys.stderr)
        return 1
    except OSError:
        print("Alignment diagnostic failed: ALIGNMENT_FILE_IO_FAILED", file=sys.stderr)
        return 1
    finally:
        if output:
            output.close()


if __name__ == "__main__":
    raise SystemExit(main())
