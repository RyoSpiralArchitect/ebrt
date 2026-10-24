#!/usr/bin/env python3
"""One predeclared dependency-context canary with six attempts at most.

The contextual four-call execution supplies a shared two-audit prefix. Only
the dependent extraction and final generation are repeated without parent
quotations. This is a small conditional diagnostic, not a quality benchmark.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

from ebrt_core import EBRTError, _canonical_bytes, _grade_contract, _seal, _sealed_snapshot
from ebrt_hosted import PRIVACY, _open_output
from ebrt_reinspection import ReinspectionConfig
from ebrt_reinspection_hosted import PRE_DISPATCH_ERRORS, _score_stage
from ebrt_dependency_cases import build_case
from ebrt_dependency_reinspection import (
    PARENT_RECORD_PREFIX, build_audit_invocation, build_final_invocation,
    build_plan as build_dependency_plan, grade_quotes,
    validate_plan as validate_dependency_plan,
)
from ebrt_dependency_hosted import (
    _execute_stage, _run_plan_with_client, verify_report as verify_dependency_report,
)
from role_stratified_uptake_canary_v0_8_3 import _output_diff


PLAN_SCHEMA = "ebrt-dependency-context-canary-plan-v1"
REPORT_SCHEMA = "ebrt-dependency-context-canary-result-v1"
MAX_PROVIDER_ATTEMPTS = 6


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise EBRTError(reason)


def build_plan(config: ReinspectionConfig) -> dict[str, Any]:
    """Fix the case, shared execution, perturbation and complete budget offline."""
    case = build_case()
    dependency = build_dependency_plan(
        case.task, config, dependencies=case.dependencies,
        quote_contract=case.quote_contract, post_run_contract=case.contract,
    )
    target = "R4"
    specs = dependency["audit_specs"]
    _require(len(specs) == 3 and specs[-1]["evidence_id"] == target
             and bool(specs[-1]["parent_ids"]), "DEPENDENCY_CANARY_CASE_INVALID")
    isolated_invocation = build_audit_invocation(case.task, target, [])
    sources = dict(dependency["source_sha256"])
    root = Path(__file__).resolve().parent
    for name in ("ebrt_dependency_canary.py", "ebrt_dependency_cases.py"):
        sources[name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
    return _seal({
        "schema_version": PLAN_SCHEMA, "config": config.to_dict(),
        "dependency_plan": dependency, "target_evidence_id": target,
        "shared_audit_ids": [row["evidence_id"] for row in specs[:-1]],
        "isolated_audit_spec": {
            "evidence_id": target, "invocation": isolated_invocation,
            "generation_config": specs[-1]["generation_config"],
        },
        "schedule": ["CONTEXTUAL_SHARED_PREFIX_AND_DEPENDENT_AUDIT_AND_FINAL",
                     "ISOLATED_DEPENDENT_AUDIT", "ISOLATED_FINAL"],
        "max_provider_attempts": MAX_PROVIDER_ATTEMPTS,
        "planned_provider_attempts": dependency["planned_provider_attempts"] + 2,
        "max_reserved_output_tokens": dependency["max_reserved_output_tokens"]
            + specs[-1]["max_output_tokens"] + config.final_max_output_tokens,
        "source_sha256": sources,
        "evidence_label": "FRESH_ENGINEERED_DEPENDENCY_CONTEXT_CANARY",
        "branch_policy": "ISOLATED_BRANCH_ONLY_AFTER_CONTEXTUAL_EXECUTION_PASS_NOT_GOLD_GRADE",
        "claim_boundary": [
            "Two final conditions share two executed audits, not two independent four-call runs.",
            "Only parent-quotation context changes in the dependent audit prompt.",
            "The isolated condition is an auxiliary perturbation, not admitted dependency execution.",
            "One serial call per condition does not establish causal or general reasoning benefit.",
        ],
    })


def _validated_plan(plan):
    snapshot = _sealed_snapshot(plan, "DEPENDENCY_CANARY_PLAN")
    try:
        config = ReinspectionConfig(**snapshot["config"])
        expected = build_plan(config)
        _require(_canonical_bytes(snapshot) == _canonical_bytes(expected),
                 "DEPENDENCY_CANARY_PLAN_MISMATCH")
        _, task, _, contract, program = validate_dependency_plan(snapshot["dependency_plan"])
        return snapshot, task, config, contract, program
    except (KeyError, TypeError, ValueError, AttributeError, IndexError):
        raise EBRTError("DEPENDENCY_CANARY_PLAN_INVALID") from None


def _without_parent_records(prompt):
    return [line for line in prompt.splitlines() if not line.startswith(PARENT_RECORD_PREFIX)]


def _without_target_quote(prompt, target):
    result = []
    prefix = "PUBLIC_REINSPECTION_JSON "
    for line in prompt.splitlines():
        if line.startswith(prefix) and json.loads(line[len(prefix):])["evidence_id"] == target:
            continue
        result.append(line)
    return result


def _isolated_spec(plan, task, program, audits, index):
    if index == 0:
        spec = plan["isolated_audit_spec"]
        return "audit", spec["evidence_id"], spec["invocation"], spec["generation_config"]
    return ("final", None, build_final_invocation(task, program, audits),
            plan["dependency_plan"]["final_generation_config"])


def _derive_report(plan, task, config, contract, program, context_report, records,
                   pre_dispatch_failure=None):
    verify_dependency_report(context_report, plan["dependency_plan"])
    _require(type(records) is list and len(records) <= 2,
             "DEPENDENCY_CANARY_STAGE_COUNT_MISMATCH")
    context_ok = context_report["execution_status"] == "PASS"
    _require(context_ok or (not records and pre_dispatch_failure is None),
             "DEPENDENCY_CANARY_CALL_AFTER_CONTEXT_FAILURE")
    target = plan["target_evidence_id"]
    context_audits = context_report["validated_audits"]
    audits = [row for row in context_audits if row["evidence_id"] in plan["shared_audit_ids"]]
    returned_model = next((row["provider_receipt"]["returned_model"]
                           for row in context_report["stages"]
                           if row["provider_receipt"]["status"] == "COMPLETED"), None)
    stages, final_result, final_invocation = [], None, None
    structural = {"status": "NOT_ASSESSED", "checks": {}}
    stopped = not context_ok
    isolated_audit_valid = False
    for index, record in enumerate(records):
        _require(not stopped, "DEPENDENCY_CANARY_CALL_AFTER_STOP")
        kind, evidence_id, invocation, stage_config = _isolated_spec(plan, task, program, audits, index)
        stage, result, checks = _score_stage(
            task, program, sequence=5 + index, kind=kind, evidence_id=evidence_id,
            invocation=invocation, generation_config=stage_config,
            receipt=record["provider_receipt"], raw_text=record["raw_text"],
            returned_model=returned_model,
        )
        stages.append(stage)
        if kind == "audit":
            if stage["status"] == "VALIDATED":
                audits.append(stage["parsed"])
                isolated_audit_valid = True
            else:
                stopped = True
        else:
            final_invocation, final_result, structural = invocation, result, checks
            stopped = True
    if isolated_audit_valid:
        final_invocation = build_final_invocation(task, program, audits)
    if pre_dispatch_failure is not None:
        _require(context_ok and not stopped and len(records) < 2
                 and type(pre_dispatch_failure) is dict,
                 "DEPENDENCY_CANARY_PRE_DISPATCH_FAILURE_INVALID")
        kind, evidence_id, _, _ = _isolated_spec(plan, task, program, audits, len(records))
        expected = {"sequence": 5 + len(records), "kind": kind, "evidence_id": evidence_id,
                    "error_code": pre_dispatch_failure.get("error_code")}
        _require(_canonical_bytes(pre_dispatch_failure) == _canonical_bytes(expected)
                 and type(expected["error_code"]) is str and expected["error_code"] in PRE_DISPATCH_ERRORS,
                 "DEPENDENCY_CANARY_PRE_DISPATCH_FAILURE_INVALID")
    else:
        _require(stopped, "DEPENDENCY_CANARY_MISSING_PLANNED_STAGE")

    original_order = [row[0] for row in program.reinspect]
    ordered_audits = sorted(audits, key=lambda row: original_order.index(row["evidence_id"]))
    quote_grade = grade_quotes(task, ordered_audits, plan["dependency_plan"]["quote_contract"]
                               if isolated_audit_valid else None)
    semantic_grade = _grade_contract(final_result, program, contract) if (
        final_result is not None and contract is not None
    ) else {"status": "NOT_ASSESSED", "contract": None, "checks": {}}
    context_target_stage = next((row for row in context_report["stages"]
                                 if row["kind"] == "audit" and row["evidence_id"] == target), None)
    audit_scope = None if not context_ok else (
        _without_parent_records(context_target_stage["invocation"]["prompt"])
        == _without_parent_records(plan["isolated_audit_spec"]["invocation"]["prompt"]))
    final_scope = None if final_invocation is None or context_report["final_invocation"] is None else (
        _without_target_quote(context_report["final_invocation"]["prompt"], target)
        == _without_target_quote(final_invocation["prompt"], target))
    _require(audit_scope is not False and final_scope is not False,
             "DEPENDENCY_CANARY_MATCHED_INPUT_FAILURE")
    both_parsed = context_report["final_model_result"] is not None and final_result is not None
    comparison = _seal({
        "status": "ASSESSED" if both_parsed else "NOT_ASSESSED",
        "output_diff": _output_diff("contextual", context_report["final_model_result"],
                                     "isolated", final_result.to_dict()) if both_parsed else None,
        "strict_pass_transition": [context_report["post_run_contract"]["status"], semantic_grade["status"]]
            if both_parsed else None,
    })
    execution = (context_ok and len(stages) == 2 and stages[-1]["status"] == "PARSED"
                 and structural["status"] == "PASS" and pre_dispatch_failure is None)
    all_stages = context_report["stages"] + stages
    completed_models = {row["provider_receipt"]["returned_model"] for row in all_stages
                        if row["provider_receipt"]["status"] == "COMPLETED"}
    _require(len(all_stages) <= MAX_PROVIDER_ATTEMPTS, "DEPENDENCY_CANARY_CALL_LIMIT_EXCEEDED")
    return _seal({
        "schema_version": REPORT_SCHEMA, "plan_fingerprint_sha256": plan["fingerprint_sha256"],
        "status": "COMPLETE", "execution_status": "PASS" if execution else "FAIL", "privacy": PRIVACY,
        "context_report": context_report, "isolated_stages": stages,
        "isolated_pre_dispatch_failure": pre_dispatch_failure,
        "isolated_validated_audits": ordered_audits if context_ok else [],
        "isolated_final_invocation": final_invocation,
        "isolated_final_model_result": final_result.to_dict() if final_result is not None else None,
        "isolated_quote_sufficiency": quote_grade, "isolated_post_run_contract": semantic_grade,
        "isolated_structural_verification": structural,
        "actual_provider_calls": len(all_stages),
        "contextual_provider_calls": context_report["actual_provider_calls"],
        "isolated_incremental_provider_calls": len(stages),
        "shared_audit_provider_calls": sum(row["kind"] == "audit" and row["evidence_id"]
            in plan["shared_audit_ids"] for row in context_report["stages"]),
        "audit_provider_calls": sum(row["kind"] == "audit" for row in all_stages),
        "final_provider_calls": sum(row["kind"] == "final" for row in all_stages),
        "planned_provider_attempts": MAX_PROVIDER_ATTEMPTS, "max_provider_attempts": MAX_PROVIDER_ATTEMPTS,
        "total_requested_output_token_ceiling": sum(row["generation_config"]["max_output_tokens"]
                                                    for row in all_stages),
        "total_planned_output_token_ceiling": plan["max_reserved_output_tokens"],
        "same_returned_model": len(completed_models) == 1 and None not in completed_models,
        "matched_inputs": {"audit_pair_diff_only_parent_records": audit_scope,
                           "final_pair_diff_only_target_quote": final_scope,
                           "same_final_generation_configuration": True},
        "comparison": comparison,
        "effect_attribution_status": "CONDITIONAL_CONTEXT_PROPAGATION_DIAGNOSTIC",
        "claim_boundary": [
            "One engineered case; contextual and isolated conditions share two actual audit requests.",
            "The six-call ledger counts unique provider attempts, not duplicated branch receipts.",
            "Only validated parent quotations change in the target extraction prompt.",
            "Only the target quotation artifact may change in final full-context prompts.",
            "Quote-sufficiency and semantic grades never gate the isolated branch or trigger retries.",
            "Unparsed final pairs are not assessed; failures are preserved without repair.",
            "Serial single calls cannot separate intervention effects from generation variability.",
            "This is not evidence of gradient-specific, general reasoning, or consumed-compute improvement.",
            "Receipt verification checks internal consistency, not provider authenticity.",
        ],
    })


def run_plan(plan: Mapping[str, Any], *, client: Any = None) -> dict[str, Any]:
    snapshot, task, config, contract, program = _validated_plan(plan)
    context, shared_client = _run_plan_with_client(snapshot["dependency_plan"], client=client)
    records, pre_dispatch_failure = [], None
    if context["execution_status"] == "PASS":
        # No grade or withheld source-span requirement enters this branch condition.
        audits = [row for row in context["validated_audits"]
                  if row["evidence_id"] in snapshot["shared_audit_ids"]]
        returned_model = context["stages"][0]["provider_receipt"]["returned_model"]
        for index in range(2):
            _require(context["actual_provider_calls"] + len(records) < MAX_PROVIDER_ATTEMPTS,
                     "DEPENDENCY_CANARY_CALL_BUDGET_EXHAUSTED")
            kind, evidence_id, invocation, stage_config = _isolated_spec(snapshot, task, program, audits, index)
            record, shared_client, error = _execute_stage(invocation, stage_config, shared_client)
            if error is not None:
                pre_dispatch_failure = {"sequence": 5 + index, "kind": kind,
                                        "evidence_id": evidence_id, "error_code": error}
                break
            records.append(record)
            stage, _, _ = _score_stage(
                task, program, sequence=5 + index, kind=kind, evidence_id=evidence_id,
                invocation=invocation, generation_config=stage_config,
                receipt=record["provider_receipt"], raw_text=record["raw_text"],
                returned_model=returned_model,
            )
            if kind == "audit":
                if stage["status"] != "VALIDATED":
                    break
                audits.append(stage["parsed"])
    report = _derive_report(snapshot, task, config, contract, program, context, records, pre_dispatch_failure)
    verify_report(report, snapshot)
    return report


def verify_report(report: Mapping[str, Any], plan: Mapping[str, Any]) -> dict[str, Any]:
    snapshot, task, config, contract, program = _validated_plan(plan)
    checked = _sealed_snapshot(report, "DEPENDENCY_CANARY_REPORT")
    try:
        records = [{"provider_receipt": row["provider_receipt"], "raw_text": row["raw_text"]}
                   for row in checked["isolated_stages"]]
        expected = _derive_report(snapshot, task, config, contract, program,
                                  checked["context_report"], records, checked["isolated_pre_dispatch_failure"])
    except (KeyError, TypeError, ValueError, AttributeError, IndexError):
        raise EBRTError("DEPENDENCY_CANARY_REPORT_MISMATCH") from None
    _require(_canonical_bytes(checked) == _canonical_bytes(expected), "DEPENDENCY_CANARY_REPORT_MISMATCH")
    return _seal({
        "status": "PASS", "plan_fingerprint_sha256": snapshot["fingerprint_sha256"],
        "report_fingerprint_sha256": checked["fingerprint_sha256"],
        "execution_status": checked["execution_status"], "checked_stages": checked["actual_provider_calls"],
        "meaning": "Internal receipt consistency, not provider authenticity or reasoning quality.",
    })


def render_text(report):
    return "\n".join([
        f"Dependency-context canary: {report['status']}; execution={report['execution_status']}",
        f"Provider attempts: {report['actual_provider_calls']}/{MAX_PROVIDER_ATTEMPTS}; shared audits: {report['shared_audit_provider_calls']}",
        f"Required source spans: contextual={report['context_report']['quote_sufficiency']['status']}; isolated={report['isolated_quote_sufficiency']['status']}",
        f"Final output contract: contextual={report['context_report']['post_run_contract']['status']}; isolated={report['isolated_post_run_contract']['status']}",
        f"Paired output comparison: {report['comparison']['status']}",
        "Single serial calls; no general reasoning, gradient-specific, or causal quality claim.",
    ]) + "\n"


def _load(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        _require(type(value) is dict, "DEPENDENCY_CANARY_JSON_INVALID")
        return value
    except (OSError, ValueError):
        raise EBRTError("DEPENDENCY_CANARY_JSON_UNREADABLE") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan_cmd = commands.add_parser("plan", help="save the six-attempt diagnostic plan offline")
    plan_cmd.add_argument("--model", required=True)
    plan_cmd.add_argument("--reasoning-effort", default="low")
    plan_cmd.add_argument("--audit-total-tokens", type=int, default=768)
    plan_cmd.add_argument("--audit-min-tokens", type=int, default=128)
    plan_cmd.add_argument("--final-max-output-tokens", type=int, default=512)
    plan_cmd.add_argument("--timeout", type=float, default=60.0)
    plan_cmd.add_argument("--output", required=True)
    run_cmd = commands.add_parser("run", help="run the fixed shared-prefix diagnostic once")
    run_cmd.add_argument("--plan", required=True)
    run_cmd.add_argument("--output", required=True)
    verify_cmd = commands.add_parser("verify", help="rebuild grades without provider calls")
    verify_cmd.add_argument("--plan", required=True)
    verify_cmd.add_argument("--report", required=True)
    args = parser.parse_args(argv)
    output = None
    try:
        if args.command == "verify":
            print(json.dumps(verify_report(_load(args.report), _load(args.plan)), indent=2, sort_keys=True))
            return 0
        if args.command == "plan":
            result = build_plan(ReinspectionConfig(
                model=args.model, reasoning_effort=args.reasoning_effort,
                audit_total_tokens=args.audit_total_tokens, audit_min_tokens=args.audit_min_tokens,
                final_max_output_tokens=args.final_max_output_tokens, timeout_seconds=args.timeout,
            ))
            output = _open_output(args.output)
        else:
            plan = _load(args.plan)
            _validated_plan(plan)
            output = _open_output(args.output)
            result = run_plan(plan)
        json.dump(result, output, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        output.write("\n")
        print("Dependency canary plan saved: six declared attempts, no API calls."
              if args.command == "plan" else render_text(result), end="\n" if args.command == "plan" else "")
        return 0 if args.command == "plan" or result["execution_status"] == "PASS" else 1
    except EBRTError as failure:
        if output:
            json.dump({"status": "ERROR", "privacy": PRIVACY, "error_code": str(failure)}, output)
            output.write("\n")
        print(f"Dependency canary failed: {failure}", file=sys.stderr)
        return 1
    except OSError:
        print("Dependency canary failed: DEPENDENCY_CANARY_FILE_IO_FAILED", file=sys.stderr)
        return 1
    finally:
        if output:
            output.close()


if __name__ == "__main__":
    raise SystemExit(main())
