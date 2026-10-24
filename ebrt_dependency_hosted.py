#!/usr/bin/env python3
"""Execute source-bound reinspection in caller-declared dependency order.

Validated parent quotations become public context for each child extraction.
The original per-site token ceilings and four-attempt outer bound are retained.
Quote sufficiency is a post-run measurement and never controls generation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

from ebrt_core import EBRTError, _canonical_bytes, _clone, _grade_contract, _seal, _sealed_snapshot
from ebrt_hosted import HostedResponsesRuntime, PRIVACY, _open_output
from ebrt_reinspection import ReinspectionConfig
from ebrt_reinspection_hosted import PRE_DISPATCH_ERRORS, _hosted_config, _score_stage
from ebrt_dependency_reinspection import (
    build_audit_invocation, build_final_invocation, build_plan, grade_quotes, validate_plan,
)


PROTOCOL = "ebrt-dependency-reinspection-v1"
REPORT_SCHEMA = "ebrt-dependency-reinspection-result-v1"
MAX_PROVIDER_ATTEMPTS = 4


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise EBRTError(reason)


def _stage_spec(plan, task, program, index: int, audits: Sequence[Mapping[str, Any]]):
    if index < len(plan["audit_specs"]):
        spec = plan["audit_specs"][index]
        by_id = {row["evidence_id"]: row for row in audits}
        _require(len(by_id) == len(audits), "DEPENDENCY_AUDIT_DUPLICATE")
        parents = spec["parent_ids"]
        _require(all(parent in by_id for parent in parents), "DEPENDENCY_PARENT_NOT_EXECUTED")
        parent_audits = [by_id[parent] for parent in parents]
        invocation = build_audit_invocation(task, spec["evidence_id"], parent_audits)
        return "audit", spec["evidence_id"], invocation, spec["generation_config"], parents, parent_audits
    invocation = build_final_invocation(task, program, audits)
    return "final", None, invocation, plan["final_generation_config"], [], []


def _execute_stage(invocation, generation_config, client=None):
    """Make one subordinate attempt, retaining the shared SDK client.

    Returns (record, shared_client, pre_dispatch_error). A record contains only
    provider_receipt and raw_text; runtime-local attempt=1 is not an outer count.
    """
    try:
        runtime = HostedResponsesRuntime(_hosted_config(generation_config), client, max_attempts=1)
    except EBRTError as failure:
        _require(str(failure) in PRE_DISPATCH_ERRORS, "DEPENDENCY_PRE_DISPATCH_FAILURE_INVALID")
        return None, client, str(failure)
    raw_text = None
    try:
        raw_text = runtime.generate(_clone(invocation))
    except EBRTError:
        # The frozen provider runtime records a sanitized error and spends the
        # single attempt. Neither repair nor replacement calls are admitted.
        pass
    _require(runtime.attempts == len(runtime.receipts) == 1,
             "DEPENDENCY_PROVIDER_ATTEMPT_ACCOUNTING_INVALID")
    return {"provider_receipt": _clone(runtime.receipts[0]), "raw_text": raw_text}, runtime.client, None


def _derived_stage(task, program, *, index, specification, record, returned_model):
    kind, evidence_id, invocation, stage_config, parent_ids, parent_audits = specification
    stage, result, structural = _score_stage(
        task, program, sequence=index + 1, kind=kind, evidence_id=evidence_id,
        invocation=invocation, generation_config=stage_config,
        receipt=record["provider_receipt"], raw_text=record["raw_text"],
        returned_model=returned_model,
    )
    stage["parent_ids"] = list(parent_ids)
    stage["parent_audit_fingerprints_sha256"] = [row["fingerprint_sha256"] for row in parent_audits]
    return stage, result, structural


def _derive_report(plan, task, config, contract, program, records, pre_dispatch_failure=None):
    audit_count = len(plan["audit_specs"])
    planned_count = audit_count + 1
    _require(type(records) is list and len(records) <= planned_count <= MAX_PROVIDER_ATTEMPTS,
             "DEPENDENCY_STAGE_COUNT_MISMATCH")
    stages, audits = [], []
    returned_model = None
    final_result = final_invocation = None
    structural = {"status": "NOT_ASSESSED", "checks": {}}
    stopped = False
    for index, record in enumerate(records):
        _require(not stopped, "DEPENDENCY_CALL_AFTER_STOP")
        specification = _stage_spec(plan, task, program, index, audits)
        stage, result, checks = _derived_stage(
            task, program, index=index, specification=specification, record=record,
            returned_model=returned_model,
        )
        stages.append(stage)
        if returned_model is None and stage["provider_receipt"]["status"] == "COMPLETED":
            returned_model = stage["provider_receipt"]["returned_model"]
        if stage["kind"] == "audit":
            if stage["status"] == "VALIDATED":
                audits.append(stage["parsed"])
            else:
                stopped = True
        else:
            final_invocation, final_result, structural = stage["invocation"], result, checks
            stopped = True

    if len(audits) == audit_count:
        final_invocation = build_final_invocation(task, program, audits)
    if pre_dispatch_failure is not None:
        _require(type(pre_dispatch_failure) is dict and not stopped and len(records) < planned_count,
                 "DEPENDENCY_PRE_DISPATCH_FAILURE_INVALID")
        kind, evidence_id, _, _, _, _ = _stage_spec(plan, task, program, len(records), audits)
        expected = {
            "sequence": len(records) + 1, "kind": kind, "evidence_id": evidence_id,
            "error_code": pre_dispatch_failure.get("error_code"),
        }
        _require(_canonical_bytes(pre_dispatch_failure) == _canonical_bytes(expected)
                 and type(expected["error_code"]) is str
                 and expected["error_code"] in PRE_DISPATCH_ERRORS,
                 "DEPENDENCY_PRE_DISPATCH_FAILURE_INVALID")
    else:
        _require(stopped, "DEPENDENCY_MISSING_PLANNED_STAGE")

    grade = _grade_contract(final_result, program, contract) if (
        final_result is not None and contract is not None
    ) else {"status": "NOT_ASSESSED", "contract": None, "checks": {}}
    # This withheld measurement cannot influence audit order, context, calls,
    # final generation, or the early-stop rule above.
    sufficiency = grade_quotes(task, audits, plan["quote_contract"])
    completed_models = {
        row["provider_receipt"]["returned_model"] for row in stages
        if row["provider_receipt"]["status"] == "COMPLETED"
    }
    same_model = len(completed_models) == 1 and None not in completed_models
    execution_passed = (
        len(stages) == planned_count and len(audits) == audit_count
        and stages[-1]["status"] == "PARSED" and structural["status"] == "PASS"
        and same_model and pre_dispatch_failure is None
    )
    audit_stages = [row for row in stages if row["kind"] == "audit"]
    final_stages = [row for row in stages if row["kind"] == "final"]
    passed = execution_passed and grade["status"] != "FAIL" and sufficiency["status"] != "FAIL"
    return _seal({
        "schema_version": REPORT_SCHEMA, "protocol": PROTOCOL,
        "plan_fingerprint_sha256": plan["fingerprint_sha256"],
        "status": "PASS" if passed else "FAIL", "execution_status": "PASS" if execution_passed else "FAIL",
        "privacy": PRIVACY,
        "actual_provider_calls": len(stages), "audit_provider_calls": len(audit_stages),
        "final_provider_calls": len(final_stages), "planned_provider_attempts": planned_count,
        "max_provider_attempts": MAX_PROVIDER_ATTEMPTS,
        "total_requested_output_token_ceiling": sum(row["generation_config"]["max_output_tokens"] for row in stages),
        "total_planned_output_token_ceiling": config.audit_total_tokens + config.final_max_output_tokens,
        "audit_requested_output_token_ceiling": sum(row["generation_config"]["max_output_tokens"] for row in audit_stages),
        "audit_planned_output_token_ceiling": config.audit_total_tokens,
        "dependencies": plan["dependencies"], "audit_order": plan["audit_order"],
        "original_program_order": [row[0] for row in program.reinspect],
        "actuator_execution_status": "PASS" if len(audits) == audit_count else "INCOMPLETE",
        "dependency_context_status": "PASS" if len(audits) == audit_count else "INCOMPLETE",
        "stages": stages, "pre_dispatch_failure": pre_dispatch_failure,
        "validated_audits": audits, "final_invocation": final_invocation,
        "final_model_result": final_result.to_dict() if final_result is not None else None,
        "final_model_result_scope": "FINAL_GENERATION_STAGE_ONLY_NOT_WHOLE_RUN",
        "structural_verification": structural, "post_run_contract": grade,
        "semantic_correctness_status": grade["status"], "quote_sufficiency": sufficiency,
        "same_returned_model": same_model, "signed_control_execution_status": "PROVENANCE_ONLY",
        "effect_attribution_status": "NOT_ASSESSED",
        "claim_boundary": [
            "Caller-declared dependencies order source reinspection and route validated direct-parent quotations.",
            "Source provenance and withheld required-span sufficiency are separate measurements.",
            "Sufficiency grades are computed after execution and never trigger retries or alter requests.",
            "Final quotations are restored to original program order; per-ID caps and selected IDs are unchanged.",
            "The outer ledger counts every provider attempt; final logical_calls=1 concerns only the final stage.",
            "Output-token ceilings do not measure consumed compute; signed controls remain provenance only.",
            "The generator stays outside autograd; no model-native gradient or general quality benefit is established.",
            "Receipt verification checks internal consistency, not provider authenticity or host attestation.",
        ],
    })


def _run_plan_with_client(plan: Mapping[str, Any], *, client: Any = None):
    """Internal composition edge for a predeclared canary sharing its SDK client."""
    snapshot, task, config, contract, program = validate_plan(plan)
    planned_count = len(snapshot["audit_specs"]) + 1
    _require(planned_count <= MAX_PROVIDER_ATTEMPTS, "DEPENDENCY_CALL_LIMIT_EXCEEDED")
    records, audits = [], []
    shared_client, returned_model = client, None
    pre_dispatch_failure = None
    for index in range(planned_count):
        _require(len(records) < planned_count, "DEPENDENCY_CALL_BUDGET_EXHAUSTED")
        specification = _stage_spec(snapshot, task, program, index, audits)
        kind, evidence_id, invocation, stage_config, _, _ = specification
        record, shared_client, error = _execute_stage(invocation, stage_config, shared_client)
        if error is not None:
            pre_dispatch_failure = {"sequence": index + 1, "kind": kind,
                                    "evidence_id": evidence_id, "error_code": error}
            break
        records.append(record)
        stage, _, _ = _derived_stage(
            task, program, index=index, specification=specification, record=record,
            returned_model=returned_model,
        )
        if returned_model is None and record["provider_receipt"]["status"] == "COMPLETED":
            returned_model = record["provider_receipt"]["returned_model"]
        if kind == "audit":
            if stage["status"] != "VALIDATED":
                break
            audits.append(stage["parsed"])
    report = _derive_report(snapshot, task, config, contract, program, records, pre_dispatch_failure)
    verify_report(report, snapshot)
    return report, shared_client


def run_plan(plan: Mapping[str, Any], *, client: Any = None) -> dict[str, Any]:
    return _run_plan_with_client(plan, client=client)[0]


def verify_report(report: Mapping[str, Any], plan: Mapping[str, Any]) -> dict[str, Any]:
    """Rebuild dependency contexts, final input, stop boundaries and all grades."""
    snapshot, task, config, contract, program = validate_plan(plan)
    checked = _sealed_snapshot(report, "DEPENDENCY_REPORT")
    try:
        _require(type(checked["stages"]) is list, "DEPENDENCY_REPORT_MISMATCH")
        records = [{"provider_receipt": row["provider_receipt"], "raw_text": row["raw_text"]}
                   for row in checked["stages"]]
        expected = _derive_report(snapshot, task, config, contract, program, records,
                                  checked["pre_dispatch_failure"])
    except (KeyError, TypeError, ValueError, AttributeError, IndexError):
        raise EBRTError("DEPENDENCY_REPORT_MISMATCH") from None
    _require(_canonical_bytes(checked) == _canonical_bytes(expected), "DEPENDENCY_REPORT_MISMATCH")
    return _seal({
        "status": "PASS", "plan_fingerprint_sha256": snapshot["fingerprint_sha256"],
        "report_fingerprint_sha256": checked["fingerprint_sha256"],
        "execution_status": checked["execution_status"], "checked_stages": len(records),
        "meaning": "Internal receipt consistency, not provider authenticity or reasoning quality.",
    })


def render_text(report: Mapping[str, Any]) -> str:
    return "\n".join([
        f"Dependency-aware reinspection: {report['status']}; execution={report['execution_status']}",
        f"Audit order: {','.join(report['audit_order'])}; original program: {','.join(report['original_program_order'])}",
        f"Provider attempts: {report['actual_provider_calls']}/{report['planned_provider_attempts']} planned; hard limit {report['max_provider_attempts']}",
        f"Audit attempts: {report['audit_provider_calls']}; final attempts: {report['final_provider_calls']}",
        f"Source provenance: {report['actuator_execution_status']}; required source spans: {report['quote_sufficiency']['status']}",
        f"Final structure: {report['structural_verification']['status']}; output contract: {report['semantic_correctness_status']}",
        "Declared-span grades are post-run; source provenance does not establish semantic relevance.",
        "Requested token ceilings are not consumed compute; no general quality or model-native gradient claim.",
    ]) + "\n"


def _load(path: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        _require(type(value) is dict, "DEPENDENCY_JSON_INVALID")
        return value
    except (OSError, ValueError):
        raise EBRTError("DEPENDENCY_JSON_UNREADABLE") from None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan_cmd = commands.add_parser("plan", help="compile a dependency-aware reinspection plan offline")
    plan_cmd.add_argument("--model", required=True)
    plan_cmd.add_argument("--reasoning-effort", default="low")
    plan_cmd.add_argument("--audit-total-tokens", type=int, default=768)
    plan_cmd.add_argument("--audit-min-tokens", type=int, default=128)
    plan_cmd.add_argument("--final-max-output-tokens", type=int, default=512)
    plan_cmd.add_argument("--timeout", type=float, default=60.0)
    plan_cmd.add_argument("--output", required=True)
    run_cmd = commands.add_parser("run", help="execute dependency-ordered audits and one final generation")
    run_cmd.add_argument("--plan", required=True)
    run_cmd.add_argument("--output", required=True)
    verify_cmd = commands.add_parser("verify", help="recompute contexts and grades without provider calls")
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
            from ebrt_dependency_cases import build_case
            case = build_case()
            config = ReinspectionConfig(
                model=args.model, reasoning_effort=args.reasoning_effort,
                audit_total_tokens=args.audit_total_tokens, audit_min_tokens=args.audit_min_tokens,
                final_max_output_tokens=args.final_max_output_tokens, timeout_seconds=args.timeout,
            )
            result = build_plan(case.task, config, dependencies=case.dependencies,
                                quote_contract=case.quote_contract, post_run_contract=case.contract)
            output = _open_output(args.output)
        else:
            plan = _load(args.plan)
            validate_plan(plan)
            output = _open_output(args.output)
            result = run_plan(plan)
        json.dump(result, output, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        output.write("\n")
        print(f"Dependency plan saved: {result['planned_provider_attempts']} planned attempts, no API calls."
              if args.command == "plan" else render_text(result), end="\n" if args.command == "plan" else "")
        return 0 if args.command == "plan" or result["status"] == "PASS" else 1
    except EBRTError as failure:
        if output:
            json.dump({"status": "ERROR", "privacy": PRIVACY, "error_code": str(failure)}, output)
            output.write("\n")
        print(f"Dependency reinspection failed: {failure}", file=sys.stderr)
        return 1
    except OSError:
        print("Dependency reinspection failed: DEPENDENCY_FILE_IO_FAILED", file=sys.stderr)
        return 1
    finally:
        if output:
            output.close()


if __name__ == "__main__":
    raise SystemExit(main())
