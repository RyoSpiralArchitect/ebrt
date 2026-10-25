#!/usr/bin/env python3
"""Bounded open-solution coloring demo with blind LLM-as-a-judge checks.

Three source audits precede one free JSON solution. Four stateless judge
requests assess that solution and fixed controls without seeing their origin
or the mechanical checker's grades. All eight attempts are explicit.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping

from ebrt_core import EBRTError, _canonical_bytes, _seal, _sealed_snapshot
from ebrt_hosted import HostedConfig, PRIVACY, _open_output
from ebrt_reinspection import ReinspectionConfig
from ebrt_reinspection_hosted import PRE_DISPATCH_ERRORS, _hosted_config
from ebrt_support_eval import _check_provider
from ebrt_dependency_hosted import _derived_stage, _execute_stage, _stage_spec as _audit_spec
from ebrt_coloring import (
    build_judge_invocation, build_plan, build_solver_invocation, check_candidate,
    parse_judge, validate_plan,
)


REPORT_SCHEMA = "ebrt-open-coloring-judge-result-v1"
MAX_PROVIDER_ATTEMPTS = 8
AUDIT_COUNT = 3


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise EBRTError(reason)


def _control_text(plan, item_id, solver_raw):
    if item_id == "generated":
        _require(type(solver_raw) is str, "COLORING_SOLVER_OUTPUT_MISSING")
        return solver_raw
    return json.dumps(plan["controls"][item_id], ensure_ascii=True,
                      sort_keys=True, separators=(",", ":"), allow_nan=False)


def _specification(plan, task, solver_config, judge_config, program, index, audits, solver_raw):
    if index < AUDIT_COUNT:
        specification = _audit_spec(plan["dependency_plan"], task, program, index, audits)
        kind, evidence_id, invocation, generation_config, _, _ = specification
        return {"kind": kind, "item_id": None, "evidence_id": evidence_id,
                "invocation": invocation, "generation_config": generation_config,
                "audit_specification": specification, "candidate_raw_text": None}
    if index == AUDIT_COUNT:
        return {"kind": "solver", "item_id": None, "evidence_id": None,
                "invocation": build_solver_invocation(task, program, audits, plan["problem"]),
                "generation_config": solver_config.hosted_config(
                    solver_config.final_max_output_tokens).to_dict(),
                "audit_specification": None, "candidate_raw_text": None}
    item_id = plan["judge_schedule"][index - AUDIT_COUNT - 1]
    raw = _control_text(plan, item_id, solver_raw)
    return {"kind": "judge", "item_id": item_id, "evidence_id": None,
            "invocation": build_judge_invocation(plan["problem"], raw),
            "generation_config": judge_config.to_dict(),
            "audit_specification": None, "candidate_raw_text": raw}


def _terminal_stage(plan, specification, record, *, sequence, returned_model):
    receipt, raw = record["provider_receipt"], record["raw_text"]
    config = _hosted_config(specification["generation_config"])
    _check_provider(receipt, 0, specification["invocation"], config)
    status, error, parsed = "PROVIDER_ERROR", receipt["error_code"], None
    if receipt["status"] == "COMPLETED":
        _require(type(raw) is str, "COLORING_RAW_TEXT_MISSING")
        if returned_model is not None and receipt["returned_model"] != returned_model:
            status, error = "MODEL_MISMATCH", "COLORING_RETURNED_MODEL_MISMATCH"
        elif specification["kind"] == "solver":
            parsed = check_candidate(raw, plan["problem"])
            status = "CANDIDATE_RECORDED" if parsed["format_status"] == "PASS" else "CANDIDATE_FORMAT_ERROR"
            error = None if parsed["format_status"] == "PASS" else "COLORING_CANDIDATE_FORMAT_INVALID"
        else:
            try:
                parsed = parse_judge(raw)
                status = "JUDGED"
            except EBRTError as failure:
                status, error = "JUDGE_FORMAT_ERROR", str(failure)
    else:
        _require(raw is None, "COLORING_ERROR_RAW_TEXT_INVALID")
    return {
        "sequence": sequence, "kind": specification["kind"],
        "item_id": specification["item_id"], "evidence_id": None,
        "invocation": specification["invocation"],
        "generation_config": specification["generation_config"],
        "provider_receipt": receipt, "raw_text": raw,
        "parsed": parsed, "status": status, "error_code": error,
    }


def _score_stage(plan, task, program, specification, record, *, index, returned_model):
    if specification["kind"] == "audit":
        stage, _, _ = _derived_stage(
            task, program, index=index, specification=specification["audit_specification"],
            record=record, returned_model=returned_model,
        )
        stage["item_id"] = None
        return stage
    return _terminal_stage(plan, specification, record, sequence=index + 1,
                           returned_model=returned_model)


def _agreement(assessment, judgment):
    if judgment is None:
        return {"status": "NOT_ASSESSED", "verdict_matches_oracle": None,
                "per_criterion": {}, "all_checks_match": None}
    # Native output/lineage formatting is distinct from graph feasibility.
    # A usable colors mapping can be feasible even when wrapper metadata is
    # malformed. Unextractable colors follow the judge rubric's all-false FAIL.
    oracle = assessment["feasibility"]["status"]
    if oracle not in ("PASS", "FAIL"):
        oracle = "FAIL"
    per_criterion = {
        key: judgment["checks"][key] == value
        for key, value in assessment["feasibility"]["checks"].items()
    }
    verdict_matches = judgment["verdict"] == oracle
    checks_match = all(per_criterion.values())
    return {"status": "AGREE" if verdict_matches and checks_match else "DISAGREE",
            "verdict_matches_oracle": verdict_matches,
            "per_criterion": per_criterion, "all_checks_match": checks_match}


def _derive_report(plan, task, solver_config, judge_config, program, records,
                   pre_dispatch_failure=None):
    planned_count = AUDIT_COUNT + 1 + len(plan["judge_schedule"])
    _require(type(records) is list and len(records) <= planned_count == MAX_PROVIDER_ATTEMPTS,
             "COLORING_STAGE_COUNT_MISMATCH")
    stages, audits, judges = [], [], []
    solver_model = judge_model = None
    solver_raw = solver_invocation = candidate = None
    stopped = False
    for index, record in enumerate(records):
        _require(not stopped, "COLORING_CALL_AFTER_STOP")
        spec = _specification(plan, task, solver_config, judge_config, program,
                              index, audits, solver_raw)
        expected_model = judge_model if spec["kind"] == "judge" else solver_model
        stage = _score_stage(plan, task, program, spec, record,
                             index=index, returned_model=expected_model)
        stages.append(stage)
        if stage["provider_receipt"]["status"] == "COMPLETED":
            if spec["kind"] == "judge" and judge_model is None:
                judge_model = stage["provider_receipt"]["returned_model"]
            elif spec["kind"] != "judge" and solver_model is None:
                solver_model = stage["provider_receipt"]["returned_model"]
        if spec["kind"] == "audit":
            if stage["status"] == "VALIDATED":
                audits.append(stage["parsed"])
            else:
                stopped = True
        elif spec["kind"] == "solver":
            solver_invocation = spec["invocation"]
            if stage["status"] in ("CANDIDATE_RECORDED", "CANDIDATE_FORMAT_ERROR"):
                # A malformed or infeasible completed answer remains an item
                # for the fixed judge schedule. Grades never trigger repair.
                solver_raw, candidate = stage["raw_text"], stage["parsed"]
            else:
                stopped = True
        else:
            assessment = check_candidate(spec["candidate_raw_text"], plan["problem"])
            judgment = stage["parsed"] if stage["status"] == "JUDGED" else None
            judges.append({
                "item_id": spec["item_id"], "provider_sequence": index + 1,
                "candidate_raw_text": spec["candidate_raw_text"],
                "candidate_assessment": assessment, "judgment": judgment,
                "status": stage["status"], "error_code": stage["error_code"],
                "agreement": _agreement(assessment, judgment),
            })
            if stage["status"] != "JUDGED":
                stopped = True
        if index == planned_count - 1:
            stopped = True

    if pre_dispatch_failure is not None:
        _require(type(pre_dispatch_failure) is dict and not stopped and len(records) < planned_count,
                 "COLORING_PRE_DISPATCH_FAILURE_INVALID")
        spec = _specification(plan, task, solver_config, judge_config, program,
                              len(records), audits, solver_raw)
        expected = {
            "sequence": len(records) + 1, "kind": spec["kind"],
            "item_id": spec["item_id"], "evidence_id": spec["evidence_id"],
            "error_code": pre_dispatch_failure.get("error_code"),
        }
        _require(_canonical_bytes(pre_dispatch_failure) == _canonical_bytes(expected)
                 and type(expected["error_code"]) is str
                 and expected["error_code"] in PRE_DISPATCH_ERRORS,
                 "COLORING_PRE_DISPATCH_FAILURE_INVALID")
    else:
        _require(stopped, "COLORING_MISSING_PLANNED_STAGE")

    judged = [item for item in judges if item["status"] == "JUDGED"]
    controls = [item for item in judges if item["item_id"] != "generated"]
    complete_controls = len(controls) == len(plan["judge_schedule"]) - 1
    controls_assessed = complete_controls and all(item["status"] == "JUDGED" for item in controls)
    calibration = ("PASS" if all(item["agreement"]["status"] == "AGREE" for item in controls)
                   else "FAIL") if controls_assessed else "INCOMPLETE"
    execution = (len(stages) == planned_count and len(audits) == AUDIT_COUNT
                 and candidate is not None and candidate["format_status"] == "PASS"
                 and len(judged) == len(plan["judge_schedule"])
                 and pre_dispatch_failure is None)
    return _seal({
        "schema_version": REPORT_SCHEMA, "status": "COMPLETE",
        "plan_fingerprint_sha256": plan["fingerprint_sha256"], "privacy": PRIVACY,
        "execution_status": "PASS" if execution else "FAIL",
        "stages": stages, "pre_dispatch_failure": pre_dispatch_failure,
        "validated_audits": audits, "solver_invocation": solver_invocation,
        "candidate_raw_text": solver_raw, "candidate_assessment": candidate,
        "judge_results": judges,
        "actual_provider_calls": len(stages),
        "audit_provider_calls": sum(row["kind"] == "audit" for row in stages),
        "solver_provider_calls": sum(row["kind"] == "solver" for row in stages),
        "judge_provider_calls": sum(row["kind"] == "judge" for row in stages),
        "planned_provider_attempts": planned_count, "max_provider_attempts": MAX_PROVIDER_ATTEMPTS,
        "total_requested_output_token_ceiling": sum(
            row["generation_config"]["max_output_tokens"] for row in stages),
        "total_planned_output_token_ceiling": (solver_config.audit_total_tokens
            + solver_config.final_max_output_tokens
            + len(plan["judge_schedule"]) * judge_config.max_output_tokens),
        "control_calibration": {"status": calibration,
            "judged_count": sum(item["status"] == "JUDGED" for item in controls),
            "planned_count": len(plan["judge_schedule"]) - 1},
        "judgments_agree_count": sum(item["agreement"]["status"] == "AGREE" for item in judges),
        "judgments_disagree_count": sum(item["agreement"]["status"] == "DISAGREE" for item in judges),
        "solver_returned_model": solver_model, "judge_returned_model": judge_model,
        "same_requested_backend": solver_config.model == judge_config.model,
        "same_returned_backend": solver_model is not None and solver_model == judge_model,
        "effect_attribution_status": "NOT_ASSESSED",
        "claim_boundary": [
            "The solver constructs a free JSON coloring, not an enumerated answer choice.",
            "Three verified source audits precede one open terminal and four explicit judge attempts.",
            "Each judge receives only the corrected public problem and one untrusted candidate.",
            "Candidate origin, model identities, controls, and mechanical verdicts are withheld from judge prompts.",
            "Feasibility predicates and source-lineage grading are separate measurements.",
            "Infeasible candidates and well-formed judge disagreements do not change the fixed schedule.",
            "Provider or judge-format failure stops the run without retries or repair.",
            "Same-backend stateless judging is not independent-model evidence or proof of judge reliability.",
            "Token ceilings are not consumed compute, and generation remains outside autograd.",
            "One engineered problem does not establish general reasoning or gradient-specific improvement.",
            "Offline verification checks internal receipt consistency, not provider authenticity.",
        ],
    })


def run_plan(plan: Mapping[str, Any], *, client: Any = None) -> dict[str, Any]:
    snapshot, task, solver_config, judge_config, program = validate_plan(plan)
    _require(len(snapshot["dependency_plan"]["audit_specs"]) == AUDIT_COUNT,
             "COLORING_AUDIT_COUNT_MISMATCH")
    records, audits = [], []
    solver_raw = None
    shared_client, solver_model, judge_model = client, None, None
    pre_dispatch_failure = None
    for index in range(MAX_PROVIDER_ATTEMPTS):
        _require(len(records) < MAX_PROVIDER_ATTEMPTS, "COLORING_CALL_BUDGET_EXHAUSTED")
        spec = _specification(snapshot, task, solver_config, judge_config, program,
                              index, audits, solver_raw)
        record, shared_client, error = _execute_stage(
            spec["invocation"], spec["generation_config"], shared_client)
        if error is not None:
            pre_dispatch_failure = {
                "sequence": index + 1, "kind": spec["kind"], "item_id": spec["item_id"],
                "evidence_id": spec["evidence_id"], "error_code": error,
            }
            break
        records.append(record)
        model = judge_model if spec["kind"] == "judge" else solver_model
        stage = _score_stage(snapshot, task, program, spec, record,
                             index=index, returned_model=model)
        if record["provider_receipt"]["status"] == "COMPLETED":
            if spec["kind"] == "judge" and judge_model is None:
                judge_model = record["provider_receipt"]["returned_model"]
            elif spec["kind"] != "judge" and solver_model is None:
                solver_model = record["provider_receipt"]["returned_model"]
        if spec["kind"] == "audit":
            if stage["status"] != "VALIDATED":
                break
            audits.append(stage["parsed"])
        elif spec["kind"] == "solver":
            if stage["status"] not in ("CANDIDATE_RECORDED", "CANDIDATE_FORMAT_ERROR"):
                break
            solver_raw = stage["raw_text"]
        elif stage["status"] != "JUDGED":
            break
    report = _derive_report(snapshot, task, solver_config, judge_config, program,
                            records, pre_dispatch_failure)
    verify_report(report, snapshot)
    return report


def verify_report(report: Mapping[str, Any], plan: Mapping[str, Any]) -> dict[str, Any]:
    snapshot, task, solver_config, judge_config, program = validate_plan(plan)
    checked = _sealed_snapshot(report, "COLORING_REPORT")
    try:
        _require(type(checked["stages"]) is list, "COLORING_REPORT_MISMATCH")
        records = [{"provider_receipt": row["provider_receipt"], "raw_text": row["raw_text"]}
                   for row in checked["stages"]]
        expected = _derive_report(snapshot, task, solver_config, judge_config, program,
                                  records, checked["pre_dispatch_failure"])
    except (KeyError, TypeError, ValueError, AttributeError, IndexError):
        raise EBRTError("COLORING_REPORT_MISMATCH") from None
    _require(_canonical_bytes(checked) == _canonical_bytes(expected), "COLORING_REPORT_MISMATCH")
    return _seal({
        "status": "PASS", "plan_fingerprint_sha256": snapshot["fingerprint_sha256"],
        "report_fingerprint_sha256": checked["fingerprint_sha256"],
        "execution_status": checked["execution_status"], "checked_stages": len(records),
        "meaning": "Internal receipt consistency, not provider authenticity or judge reliability.",
    })


def render_text(report: Mapping[str, Any]) -> str:
    candidate = report["candidate_assessment"]
    rows = [
        f"Open coloring / LLM-as-a-judge: {report['status']}; execution={report['execution_status']}",
        f"Provider attempts: {report['actual_provider_calls']}/{MAX_PROVIDER_ATTEMPTS} (audits/solver/judges={report['audit_provider_calls']}/{report['solver_provider_calls']}/{report['judge_provider_calls']})",
        f"Generated feasibility: {candidate['feasibility']['status'] if candidate else 'NOT_ASSESSED'}; source lineage: {candidate['lineage']['status'] if candidate else 'NOT_ASSESSED'}",
    ]
    for item in report["judge_results"]:
        verdict = item["judgment"]["verdict"] if item["judgment"] is not None else "NOT_ASSESSED"
        rows.append(f"{item['item_id']}: machine={item['candidate_assessment']['feasibility']['status']}; judge={verdict}; agreement={item['agreement']['status']}")
    rows.extend([
        f"Control calibration: {report['control_calibration']['status']}",
        "Stateless blind judgments; same backend may be used. No general quality or gradient claim.",
    ])
    return "\n".join(rows) + "\n"


def _load(path: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        _require(type(value) is dict, "COLORING_JSON_INVALID")
        return value
    except (OSError, ValueError):
        raise EBRTError("COLORING_JSON_UNREADABLE") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan_cmd = commands.add_parser("plan", help="save the fixed open-solution and blind-judge inputs offline")
    plan_cmd.add_argument("--model", required=True)
    plan_cmd.add_argument("--judge-model")
    plan_cmd.add_argument("--reasoning-effort", default="low")
    plan_cmd.add_argument("--judge-reasoning-effort", default="low")
    plan_cmd.add_argument("--audit-total-tokens", type=int, default=768)
    plan_cmd.add_argument("--audit-min-tokens", type=int, default=128)
    plan_cmd.add_argument("--final-max-output-tokens", type=int, default=512)
    plan_cmd.add_argument("--judge-max-output-tokens", type=int, default=512)
    plan_cmd.add_argument("--timeout", type=float, default=60.0)
    plan_cmd.add_argument("--output", required=True)
    run_cmd = commands.add_parser("run", help="execute at most eight attempts with no repair or retry")
    run_cmd.add_argument("--plan", required=True)
    run_cmd.add_argument("--output", required=True)
    verify_cmd = commands.add_parser("verify", help="rebuild judgments and mechanical comparisons offline")
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
            solver_config = ReinspectionConfig(
                model=args.model, reasoning_effort=args.reasoning_effort,
                audit_total_tokens=args.audit_total_tokens, audit_min_tokens=args.audit_min_tokens,
                final_max_output_tokens=args.final_max_output_tokens, timeout_seconds=args.timeout,
            )
            judge_config = HostedConfig(
                model=args.judge_model or args.model, reasoning_effort=args.judge_reasoning_effort,
                max_output_tokens=args.judge_max_output_tokens, timeout_seconds=args.timeout,
            )
            result = build_plan(solver_config, judge_config)
            output = _open_output(args.output)
        else:
            plan = _load(args.plan)
            validate_plan(plan)
            output = _open_output(args.output)
            result = run_plan(plan)
        json.dump(result, output, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        output.write("\n")
        print("Coloring/judge plan saved: eight declared attempts, no API calls."
              if args.command == "plan" else render_text(result), end="\n" if args.command == "plan" else "")
        return 0 if args.command == "plan" or result["execution_status"] == "PASS" else 1
    except EBRTError as failure:
        if output:
            json.dump({"status": "ERROR", "privacy": PRIVACY, "error_code": str(failure)}, output)
            output.write("\n")
        print(f"Coloring/judge failed: {failure}", file=sys.stderr)
        return 1
    except OSError:
        print("Coloring/judge failed: COLORING_FILE_IO_FAILED", file=sys.stderr)
        return 1
    finally:
        if output:
            output.close()


if __name__ == "__main__":
    raise SystemExit(main())
