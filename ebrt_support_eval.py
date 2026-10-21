#!/usr/bin/env python3
"""Predeclared support-retention diagnostics, with nine hosted attempts at most.

The role-coverage actuator is an auxiliary candidate over the same verified
public trajectory. It is not admitted into the frozen core's actuator edge.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence

from ebrt_core import (
    AdapterDescriptor, EBRTError, ModelResult, _canonical_bytes, _fingerprint,
    _grade_contract, _parse_model_text, _seal, _sealed_snapshot,
    _structural_model_checks, build_model_invocation,
)
from ebrt_demo import _prompt_records
from ebrt_hosted import HostedConfig, HostedResponsesRuntime, PRIVACY, _open_output, _safe_identifier
from ebrt_support_cases import build_cases
from local_output_diff_corpus_v0_8_2 import (
    _common_output_grade, _program_from_receipt, build_direct_invocation, compile_revision,
)
from role_stratified_uptake_canary_v0_8_3 import (
    _output_diff, _validate_role_program, compile_role_stratified,
    compiler_coverage, provider_uptake,
)


PLAN_SCHEMA = "ebrt-support-plan-v0.9.0"
REPORT_SCHEMA = "ebrt-support-diagnostic-v0.9.0"
ARMS = ("direct_full_context", "ebrt_top_k", "role_coverage")
CALL_LIMIT = 9
SOURCE_FILES = (
    "ebrt_core.py", "local_output_diff_corpus_v0_8_2.py",
    "role_stratified_uptake_canary_v0_8_3.py", "ebrt_hosted.py",
    "ebrt_demo.py", "ebrt_support_cases.py", "ebrt_support_eval.py",
)


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise EBRTError(reason)


def _config(material: Mapping[str, Any]) -> HostedConfig:
    try:
        config = HostedConfig(material["model"], material["reasoning_effort"],
                              material["max_output_tokens"], material["timeout_seconds"])
        _require(config.to_dict() == material, "SUPPORT_PLAN_MISMATCH")
        return config
    except (KeyError, TypeError, ValueError):
        raise EBRTError("SUPPORT_PLAN_MISMATCH") from None


def _sources() -> dict[str, str]:
    root = Path(__file__).resolve().parent
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in SOURCE_FILES}


def build_plan(config: HostedConfig) -> dict[str, Any]:
    """Compile all cases, programs, prompts, and the rotated schedule offline."""
    cases = build_cases()
    _require(len(cases) == 3 and len({case.task.task_id for case in cases}) == 3,
             "SUPPORT_CASE_SET_INVALID")
    planned = []
    for case in cases:
        task = case.task
        top_k, core_receipt = compile_revision(task)
        candidate = compile_role_stratified(task, top_k, core_receipt)
        _validate_role_program(task, candidate, core_receipt)
        programs = {ARMS[1]: top_k, ARMS[2]: candidate}
        invocations = {ARMS[0]: build_direct_invocation(task)}
        invocations.update({arm: build_model_invocation(task, program, prompt_policy="credit_first")
                            for arm, program in programs.items()})
        expected_data = _prompt_records(invocations[ARMS[0]])
        expected_evidence = sorted(
            [{"evidence_id": row.evidence_id, "text": row.text} for row in task.evidence],
            key=lambda row: row["evidence_id"],
        )
        _require(expected_data[1] == expected_evidence and all(
            _prompt_records(invocation) == expected_data for invocation in invocations.values()
        ), "SUPPORT_PROMPT_EVIDENCE_MISMATCH")
        _require(task.reinspection_count == 3 and all(
            len(program.reinspect) == 3 and sum(row[1] for row in program.reinspect) == 100
            for program in programs.values()
        ), "SUPPORT_CONTROL_BUDGET_MISMATCH")
        planned.append({
            "case_id": task.task_id, "family": case.family,
            "task": task.to_public_dict(), "contract": case.contract.to_dict(),
            "trajectory": core_receipt["trajectory"],
            "programs": {arm: program.to_dict() for arm, program in programs.items()},
            "invocations": invocations,
            "compiler_coverage": {arm: compiler_coverage(task, program) for arm, program in programs.items()},
            "control_prompt_equal": invocations[ARMS[1]]["prompt"] == invocations[ARMS[2]]["prompt"],
        })
    _require([row["compiler_coverage"][ARMS[1]]["status"] for row in planned]
             == ["FAIL", "FAIL", "PASS"], "SUPPORT_DIAGNOSTIC_GEOMETRY_CHANGED")
    _require(all(row["compiler_coverage"][ARMS[2]]["status"] == "PASS" for row in planned)
             and planned[2]["control_prompt_equal"], "SUPPORT_CANDIDATE_PREFLIGHT_FAILED")
    schedule = [{"case_id": case["case_id"], "arm_id": ARMS[(index + offset) % 3]}
                for index, case in enumerate(planned) for offset in range(3)]
    return _seal({
        "schema_version": PLAN_SCHEMA, "generation_config": config.to_dict(),
        "call_limit": CALL_LIMIT, "source_sha256": _sources(),
        "cases": planned, "schedule": schedule,
        "evidence_label": "FRESH_ENGINEERED_SUPPORT_DIAGNOSTIC",
        "candidate_admission": "AUXILIARY_PUBLIC_ROLE_CANDIDATE",
        "role_source": "CALLER_SUPPLIED_PUBLIC_ROLES",
    })


def _validated_plan(plan: Mapping[str, Any]) -> tuple[dict[str, Any], HostedConfig]:
    snapshot = _sealed_snapshot(plan, "SUPPORT_PLAN")
    try:
        config = _config(snapshot["generation_config"])
        expected = build_plan(config)
    except (KeyError, TypeError, ValueError):
        raise EBRTError("SUPPORT_PLAN_MISMATCH") from None
    _require(_canonical_bytes(snapshot) == _canonical_bytes(expected), "SUPPORT_PLAN_MISMATCH")
    return snapshot, config


def _descriptor(config: HostedConfig) -> AdapterDescriptor:
    return AdapterDescriptor(
        adapter_id="openai-support-diagnostic-v0.9.0", model_id="openai/" + config.model,
        interface_kind="hosted_api", state_visibility="public_only",
        differentiable_through_model=False,
        generation_config=tuple(sorted(config.to_dict().items())),
    )


def _check_provider(receipt: Mapping[str, Any], index: int, invocation: Mapping[str, Any],
                    config: HostedConfig) -> None:
    fields = {"attempt", "request_fingerprint_sha256", "generation_config_fingerprint_sha256",
              "requested_model", "returned_model", "response_id", "provider_request_id",
              "usage", "status", "error_code", "latency_ms"}
    _require(isinstance(receipt, Mapping) and fields <= set(receipt)
             and set(receipt) <= fields | {"http_status"}, "SUPPORT_PROVIDER_RECEIPT_INVALID")
    for name in ("returned_model", "response_id", "provider_request_id"):
        _require(receipt[name] is None or _safe_identifier(receipt[name]) == receipt[name],
                 "SUPPORT_PROVIDER_RECEIPT_INVALID")
    http_status = receipt.get("http_status")
    _require(http_status is None or type(http_status) is int and 100 <= http_status <= 599,
             "SUPPORT_PROVIDER_RECEIPT_INVALID")
    _require(receipt.get("attempt") == index + 1
             and type(receipt.get("attempt")) is int
             and receipt.get("request_fingerprint_sha256") == invocation["fingerprint_sha256"]
             and receipt.get("generation_config_fingerprint_sha256") == _fingerprint(config.to_dict())
             and receipt.get("requested_model") == config.model,
             "SUPPORT_PROVIDER_BINDING_MISMATCH")
    latency = receipt.get("latency_ms")
    _require(type(latency) in (int, float) and math.isfinite(latency) and latency >= 0,
             "SUPPORT_PROVIDER_RECEIPT_INVALID")
    usage = receipt.get("usage")
    _require(isinstance(usage, Mapping) and set(usage) == {
        "input_tokens", "output_tokens", "total_tokens", "reasoning_tokens"
    } and all(number is None or type(number) is int and number >= 0 for number in usage.values()),
             "SUPPORT_PROVIDER_RECEIPT_INVALID")
    if receipt.get("status") == "COMPLETED":
        _require(isinstance(receipt.get("returned_model"), str) and bool(receipt["returned_model"])
                 and receipt.get("error_code") is None, "SUPPORT_PROVIDER_RECEIPT_INVALID")
    else:
        _require(receipt.get("status") == "ERROR"
                 and isinstance(receipt.get("error_code"), str)
                 and re.fullmatch(r"HOSTED_[A-Z0-9_]+", receipt["error_code"]) is not None,
                 "SUPPORT_PROVIDER_RECEIPT_INVALID")


def _score_cell(planned: Mapping[str, Any], case: Any, arm: str, raw_text: Any,
                receipt: Mapping[str, Any], index: int, config: HostedConfig) -> dict[str, Any]:
    invocation = planned["invocations"][arm]
    _check_provider(receipt, index, invocation, config)
    result = None
    error = receipt["error_code"]
    status = "PROVIDER_ERROR"
    if receipt["status"] == "COMPLETED":
        _require(isinstance(raw_text, str), "SUPPORT_RAW_TEXT_MISSING")
        try:
            answer, support = _parse_model_text(raw_text, task=case.task)
            result = {"answer": answer, "support_ids": list(support), "raw_text": raw_text}
            status = "PARSED"
        except EBRTError as failure:
            status, error = "FORMAT_ERROR", str(failure)
    else:
        _require(raw_text is None, "SUPPORT_ERROR_RAW_TEXT_INVALID")
    parsed = {"status": status, **(result or {})}
    grade = _common_output_grade(parsed, case.contract)
    coverage = uptake = structural = post_contract = {"status": "NOT_APPLICABLE"}
    admission = "NOT_APPLICABLE"
    if arm != ARMS[0]:
        program = _program_from_receipt(planned["programs"][arm])
        coverage = compiler_coverage(case.task, program)
        uptake = provider_uptake(case.task, program, parsed)
        admission = "AUXILIARY_PUBLIC_ROLE_CANDIDATE" if arm == ARMS[2] else "CORE_ADMITTED_COMPILER"
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
        "status": status, "error_code": error, "raw_text": raw_text, "result": result,
        "grade": grade, "compiler_coverage": coverage, "provider_uptake": uptake,
        "structural": structural, "post_run_contract": post_contract,
        "actuator_admission": admission,
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
            "compiler_coverage_count": None if arm == ARMS[0] else sum(row["compiler_coverage"]["status"] == "PASS" for row in rows),
            "uptake_count": None if arm == ARMS[0] else sum(row["provider_uptake"]["status"] == "PASS" for row in rows),
            "structural_pass_count": None if arm == ARMS[0] else sum(row["structural"]["status"] == "PASS" for row in rows),
        }
    return summary


def _derive_report(plan: Mapping[str, Any], config: HostedConfig,
                   receipts: Sequence[Mapping[str, Any]], raw_texts: Sequence[Any]) -> dict[str, Any]:
    _require(len(receipts) == len(raw_texts) == CALL_LIMIT, "SUPPORT_CELL_COUNT_MISMATCH")
    planned = {case["case_id"]: case for case in plan["cases"]}
    cases = {case.task.task_id: case for case in build_cases()}
    cells = [_score_cell(planned[entry["case_id"]], cases[entry["case_id"]], entry["arm_id"],
                         raw_texts[index], receipts[index], index, config)
             for index, entry in enumerate(plan["schedule"])]
    by_cell = {(row["case_id"], row["arm_id"]): row for row in cells}
    comparisons = []
    for case_id in planned:
        left, right = (by_cell[(case_id, arm)] for arm in ARMS[1:])
        difference = _output_diff(
            ARMS[1], {"raw_text": left["raw_text"], **(left["result"] or {})},
            ARMS[2], {"raw_text": right["raw_text"], **(right["result"] or {})},
        )
        difference.pop("fingerprint_sha256")
        comparisons.append(_seal({"case_id": case_id, **difference}))
    models = {receipt.get("returned_model") for receipt in receipts}
    matched = {
        "exactly_nine_attempts": len(receipts) == CALL_LIMIT,
        "same_generation_configuration": all(row["generation_config_fingerprint_sha256"] == _fingerprint(config.to_dict()) for row in receipts),
        "same_returned_model": len(models) == 1 and None not in models,
        "all_outputs_parsed": all(row["status"] == "PARSED" for row in cells),
        "control_prompts_equal": planned[plan["cases"][2]["case_id"]]["control_prompt_equal"],
    }
    return _seal({
        "schema_version": REPORT_SCHEMA, "plan_fingerprint_sha256": plan["fingerprint_sha256"],
        "status": "COMPLETE", "execution_status": "PASS" if all(matched.values()) else "FAIL",
        "privacy": PRIVACY, "evidence_label": "FRESH_ENGINEERED_SUPPORT_DIAGNOSTIC",
        "actual_provider_calls": len(receipts), "generation_config": config.to_dict(),
        "cells": cells, "provider_receipts": list(receipts), "summary": _summary(cells),
        "comparisons": comparisons, "matched_inputs": matched,
        "effect_attribution_status": "NOT_ASSESSED", "role_extraction_status": "NOT_ASSESSED",
        "claim_boundary": [
            "Three deliberately engineered fresh cases, not a random benchmark or a general quality estimate.",
            "The candidate consumes caller-supplied public roles; role extraction is not evaluated.",
            "Candidate coverage is an auxiliary compiler check, not admission into the frozen core.",
            "All controlled arms share verified core controls, k=3 and 100 allocation units.",
            "One serial call per cell and different prompt packages do not identify a gradient-specific effect.",
            "COMPLETE records nine spent attempts; execution and output-contract grades remain separate.",
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
            # The runtime records a fixed, sanitized error and spends this cell.
            pass
        raw_texts.append(raw)
    report = _derive_report(snapshot, config, runtime.receipts, raw_texts)
    verify_report(report, snapshot)
    return report


def verify_report(report: Mapping[str, Any], plan: Mapping[str, Any]) -> dict[str, Any]:
    """Recompute every score from visible text; a resealed fake grade fails."""
    snapshot, config = _validated_plan(plan)
    checked = _sealed_snapshot(report, "SUPPORT_REPORT")
    try:
        cells = checked["cells"]
        _require(isinstance(cells, list) and len(cells) == CALL_LIMIT, "SUPPORT_CELL_COUNT_MISMATCH")
        expected = _derive_report(snapshot, config, checked["provider_receipts"],
                                  [cell["raw_text"] for cell in cells])
    except (KeyError, TypeError, ValueError, AttributeError):
        raise EBRTError("SUPPORT_REPORT_MISMATCH") from None
    _require(_canonical_bytes(checked) == _canonical_bytes(expected), "SUPPORT_REPORT_MISMATCH")
    return _seal({
        "status": "PASS", "plan_fingerprint_sha256": snapshot["fingerprint_sha256"],
        "report_fingerprint_sha256": checked["fingerprint_sha256"],
        "execution_status": checked["execution_status"], "checked_cells": CALL_LIMIT,
        "meaning": "Internal receipt consistency, not provider authenticity or reasoning quality.",
    })


def render_text(report: Mapping[str, Any]) -> str:
    lines = [f"Support diagnostics: {report['status']}; execution={report['execution_status']}",
             f"Provider attempts: {report['actual_provider_calls']}/{CALL_LIMIT}",
             "Arm                   Answer  Required support  Strict  Compiler  Uptake"]
    for arm, row in report["summary"].items():
        def count(key):
            return "N/A" if row[key] is None else f"{row[key]}/{row['case_count']}"
        lines.append(f"{arm:<22} {count('answer_correct_count'):<7} {count('required_support_count'):<17} "
                     f"{count('strict_pass_count'):<7} {count('compiler_coverage_count'):<9} {count('uptake_count')}")
    lines.extend(["Output-contract failures remain recorded in the per-cell grades.",
                  "Role coverage is an auxiliary candidate using caller-supplied roles.",
                  "Effect attribution: NOT_ASSESSED; no general quality improvement claim."])
    return "\n".join(lines) + "\n"


def _load(path: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        _require(isinstance(value, dict), "SUPPORT_JSON_INVALID")
        return value
    except (OSError, ValueError):
        raise EBRTError("SUPPORT_JSON_UNREADABLE") from None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan_cmd = commands.add_parser("plan", help="compile and seal all inputs without API calls")
    plan_cmd.add_argument("--model", required=True)
    plan_cmd.add_argument("--reasoning-effort", default="low")
    plan_cmd.add_argument("--max-output-tokens", type=int, default=1024)
    plan_cmd.add_argument("--timeout", type=float, default=60.0)
    plan_cmd.add_argument("--output", required=True)
    run_cmd = commands.add_parser("run", help="execute exactly one attempt per declared cell")
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
        print(f"Support plan saved: {CALL_LIMIT} declared attempts, no API calls."
              if args.command == "plan" else render_text(result), end="\n" if args.command == "plan" else "")
        return 0 if args.command == "plan" or result["execution_status"] == "PASS" else 1
    except EBRTError as error:
        if output:
            json.dump({"status": "ERROR", "privacy": PRIVACY, "error_code": str(error)}, output)
            output.write("\n")
        print(f"Support diagnostics failed: {error}", file=sys.stderr)
        return 1
    except OSError:
        print("Support diagnostics failed: SUPPORT_FILE_IO_FAILED", file=sys.stderr)
        return 1
    finally:
        if output:
            output.close()


if __name__ == "__main__":
    raise SystemExit(main())
