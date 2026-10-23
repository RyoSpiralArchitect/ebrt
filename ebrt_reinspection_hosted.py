#!/usr/bin/env python3
"""Execute budgeted public-source reinspection before one final generation.

This is an opt-in orchestration protocol, not the one-call model adapter.
An outer ledger records every audit and final request. Allocations determine
requested output-token ceilings, not consumed compute or private reasoning.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

from ebrt_core import (
    AdapterDescriptor, EBRTError, ModelResult, _canonical_bytes, _clone,
    _grade_contract, _parse_model_text, _seal, _sealed_snapshot,
    _structural_model_checks,
)
from ebrt_hosted import HostedConfig, HostedResponsesRuntime, PRIVACY, _open_output
from ebrt_reinspection import (
    ReinspectionConfig, build_final_invocation, build_plan, parse_audit, validate_plan,
)
from ebrt_support_cases import build_cases
from ebrt_support_eval import _check_provider


PROTOCOL = "ebrt-budgeted-reinspection-v1"
REPORT_SCHEMA = "ebrt-budgeted-reinspection-result-v1"
MAX_PROVIDER_ATTEMPTS = 4
PRE_DISPATCH_ERRORS = frozenset({
    "HOSTED_API_KEY_MISSING", "HOSTED_SDK_MISSING",
    "HOSTED_CLIENT_INITIALIZATION_FAILED", "HOSTED_RETRIES_MUST_BE_ZERO",
})


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise EBRTError(reason)


def _hosted_config(value: Mapping[str, Any]) -> HostedConfig:
    config = HostedConfig(value["model"], value["reasoning_effort"],
                          value["max_output_tokens"], value["timeout_seconds"])
    _require(_canonical_bytes(config.to_dict()) == _canonical_bytes(value),
             "REINSPECTION_STAGE_CONFIG_MISMATCH")
    return config


def _descriptor(config: HostedConfig) -> AdapterDescriptor:
    return AdapterDescriptor(
        adapter_id="openai-public-reinspection-final-v1", model_id="openai/" + config.model,
        interface_kind="hosted_api", state_visibility="public_only",
        differentiable_through_model=False,
        generation_config=tuple(sorted(config.to_dict().items())),
    )


def _stage_spec(plan, task, program, index: int, audits: Sequence[Mapping[str, Any]]):
    if index < len(plan["audit_specs"]):
        spec = plan["audit_specs"][index]
        return "audit", spec["evidence_id"], spec["invocation"], spec["generation_config"]
    return ("final", None, build_final_invocation(task, program, audits),
            plan["final_generation_config"])


def _score_stage(task, program, *, sequence: int, kind: str, evidence_id,
                 invocation, generation_config, receipt, raw_text, returned_model):
    config = _hosted_config(generation_config)
    # Each subordinate runtime is allowed exactly one attempt. Its local
    # attempt=1 is distinct from the outer ledger's global sequence number.
    _check_provider(receipt, 0, invocation, config)
    parsed = result = None
    error = receipt["error_code"]
    status = "PROVIDER_ERROR"
    structural = {"status": "NOT_ASSESSED", "checks": {}}
    if receipt["status"] == "COMPLETED":
        _require(type(raw_text) is str, "REINSPECTION_RAW_TEXT_MISSING")
        if returned_model is not None and receipt["returned_model"] != returned_model:
            status, error = "MODEL_MISMATCH", "REINSPECTION_RETURNED_MODEL_MISMATCH"
        elif kind == "audit":
            try:
                parsed = parse_audit(task, evidence_id, raw_text)
                status = "VALIDATED"
            except EBRTError as failure:
                status, error = "AUDIT_INVALID", str(failure)
        else:
            try:
                answer, support = _parse_model_text(raw_text, task=task)
                descriptor = _descriptor(config)
                result = ModelResult(
                    answer=answer, support_ids=support, raw_text=raw_text,
                    descriptor=descriptor,
                    request_fingerprint_sha256=invocation["fingerprint_sha256"],
                    latency_ms=receipt["latency_ms"], logical_calls=1,
                )
                parsed = result.to_dict()
                checks = _structural_model_checks(
                    task, program, result, expected_descriptor=descriptor,
                    expected_request_fingerprint_sha256=invocation["fingerprint_sha256"],
                )
                structural = {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks}
                status = "PARSED"
            except EBRTError as failure:
                status, error = "FORMAT_ERROR", str(failure)
    else:
        _require(raw_text is None, "REINSPECTION_ERROR_RAW_TEXT_INVALID")
    stage = {
        "sequence": sequence, "kind": kind, "evidence_id": evidence_id,
        "invocation": invocation, "generation_config": generation_config,
        "provider_receipt": receipt, "raw_text": raw_text,
        "parsed": parsed, "status": status, "error_code": error,
    }
    return stage, result, structural


def _derive_report(plan, task, config, contract, program, records, pre_dispatch_failure=None):
    audit_count = len(plan["audit_specs"])
    planned_count = audit_count + 1
    _require(type(records) is list and len(records) <= planned_count <= MAX_PROVIDER_ATTEMPTS,
             "REINSPECTION_STAGE_COUNT_MISMATCH")
    stages, audits = [], []
    returned_model = None
    final_result = final_invocation = None
    structural = {"status": "NOT_ASSESSED", "checks": {}}
    stopped = False
    for index, record in enumerate(records):
        _require(not stopped, "REINSPECTION_CALL_AFTER_STOP")
        kind, evidence_id, invocation, stage_config = _stage_spec(plan, task, program, index, audits)
        stage, result, checks = _score_stage(
            task, program, sequence=index + 1, kind=kind, evidence_id=evidence_id,
            invocation=invocation, generation_config=stage_config,
            receipt=record["provider_receipt"], raw_text=record["raw_text"],
            returned_model=returned_model,
        )
        stages.append(stage)
        if returned_model is None and stage["provider_receipt"]["status"] == "COMPLETED":
            returned_model = stage["provider_receipt"]["returned_model"]
        if kind == "audit":
            if stage["status"] == "VALIDATED":
                audits.append(stage["parsed"])
            else:
                stopped = True
        else:
            final_invocation, final_result, structural = invocation, result, checks
            stopped = True

    if len(audits) == audit_count:
        final_invocation = build_final_invocation(task, program, audits)
    if pre_dispatch_failure is not None:
        _require(not stopped and len(records) < planned_count,
                 "REINSPECTION_PRE_DISPATCH_FAILURE_INVALID")
        kind, evidence_id, _, _ = _stage_spec(plan, task, program, len(records), audits)
        expected = {
            "sequence": len(records) + 1, "kind": kind, "evidence_id": evidence_id,
            "error_code": pre_dispatch_failure.get("error_code"),
        }
        _require(type(pre_dispatch_failure) is dict
                 and _canonical_bytes(pre_dispatch_failure) == _canonical_bytes(expected)
                 and type(expected["error_code"]) is str
                 and expected["error_code"] in PRE_DISPATCH_ERRORS,
                 "REINSPECTION_PRE_DISPATCH_FAILURE_INVALID")
    else:
        _require(stopped, "REINSPECTION_MISSING_PLANNED_STAGE")

    grade = _grade_contract(final_result, program, contract) if (
        final_result is not None and contract is not None
    ) else {"status": "NOT_ASSESSED", "contract": None, "checks": {}}
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
    return _seal({
        "schema_version": REPORT_SCHEMA, "protocol": PROTOCOL,
        "plan_fingerprint_sha256": plan["fingerprint_sha256"],
        "status": "PASS" if execution_passed and grade["status"] != "FAIL" else "FAIL",
        "execution_status": "PASS" if execution_passed else "FAIL",
        "privacy": PRIVACY,
        "actual_provider_calls": len(stages), "audit_provider_calls": len(audit_stages),
        "final_provider_calls": len(final_stages),
        "planned_provider_attempts": planned_count, "max_provider_attempts": MAX_PROVIDER_ATTEMPTS,
        "total_requested_output_token_ceiling": sum(
            row["generation_config"]["max_output_tokens"] for row in stages),
        "total_planned_output_token_ceiling": config.audit_total_tokens + config.final_max_output_tokens,
        "audit_requested_output_token_ceiling": sum(
            row["generation_config"]["max_output_tokens"] for row in audit_stages),
        "audit_planned_output_token_ceiling": config.audit_total_tokens,
        "actuator_execution_status": "PASS" if len(audits) == audit_count else "INCOMPLETE",
        "stages": stages, "pre_dispatch_failure": pre_dispatch_failure,
        "validated_audits": audits, "final_invocation": final_invocation,
        "final_model_result": final_result.to_dict() if final_result is not None else None,
        "final_model_result_scope": "FINAL_GENERATION_STAGE_ONLY_NOT_WHOLE_RUN",
        "structural_verification": structural, "post_run_contract": grade,
        "semantic_correctness_status": grade["status"],
        "same_returned_model": same_model,
        "signed_control_execution_status": "PROVENANCE_ONLY",
        "effect_attribution_status": "NOT_ASSESSED",
        "claim_boundary": [
            "Opt-in public reinspection orchestration; the standard one-call engine is unchanged.",
            "The outer ledger counts every provider attempt; final logical_calls=1 concerns only the final stage.",
            "Allocation units control actual requested output-token ceilings, not consumed compute.",
            "Exact quotations establish source provenance, not semantic relevance or truth.",
            "The final invocation includes full evidence and validated quotations as quoted data.",
            "Signed controls are retained as provenance; this protocol does not execute their sign.",
            "Provider calls remain outside autograd; no private reasoning is requested or retained.",
            "One integration run cannot establish gradient-specific or general reasoning improvement.",
            "Verification establishes internal consistency, not provider authenticity or host attestation.",
        ],
    })


def run_plan(plan: Mapping[str, Any], *, client: Any = None) -> dict[str, Any]:
    """Execute one attempt per audit, stopping before final on any audit failure."""
    snapshot, task, config, contract, program = validate_plan(plan)
    planned_count = len(snapshot["audit_specs"]) + 1
    _require(planned_count <= MAX_PROVIDER_ATTEMPTS, "REINSPECTION_CALL_LIMIT_EXCEEDED")
    records, audits = [], []
    shared_client, returned_model = client, None
    pre_dispatch_failure = None
    for index in range(planned_count):
        _require(len(records) < planned_count, "REINSPECTION_CALL_BUDGET_EXHAUSTED")
        kind, evidence_id, invocation, stage_config = _stage_spec(snapshot, task, program, index, audits)
        try:
            runtime = HostedResponsesRuntime(_hosted_config(stage_config), shared_client, max_attempts=1)
        except EBRTError as failure:
            _require(str(failure) in PRE_DISPATCH_ERRORS, "REINSPECTION_PRE_DISPATCH_FAILURE_INVALID")
            pre_dispatch_failure = {
                "sequence": index + 1, "kind": kind, "evidence_id": evidence_id,
                "error_code": str(failure),
            }
            break
        shared_client = runtime.client
        raw_text = None
        try:
            raw_text = runtime.generate(_clone(invocation))
        except EBRTError:
            # The subordinate runtime records the sanitized failure and spends
            # its single attempt. No retry or replacement output is admitted.
            pass
        _require(runtime.attempts == len(runtime.receipts) == 1,
                 "REINSPECTION_PROVIDER_ATTEMPT_ACCOUNTING_INVALID")
        record = {"provider_receipt": _clone(runtime.receipts[0]), "raw_text": raw_text}
        records.append(record)
        stage, _, _ = _score_stage(
            task, program, sequence=index + 1, kind=kind, evidence_id=evidence_id,
            invocation=invocation, generation_config=stage_config,
            receipt=record["provider_receipt"], raw_text=raw_text, returned_model=returned_model,
        )
        if returned_model is None and record["provider_receipt"]["status"] == "COMPLETED":
            returned_model = record["provider_receipt"]["returned_model"]
        if kind == "audit":
            if stage["status"] != "VALIDATED":
                break
            audits.append(stage["parsed"])
    report = _derive_report(snapshot, task, config, contract, program, records, pre_dispatch_failure)
    verify_report(report, snapshot)
    return report


def verify_report(report: Mapping[str, Any], plan: Mapping[str, Any]) -> dict[str, Any]:
    """Rebuild the dynamic final request and all grades from raw stage records."""
    snapshot, task, config, contract, program = validate_plan(plan)
    checked = _sealed_snapshot(report, "REINSPECTION_REPORT")
    try:
        _require(type(checked["stages"]) is list, "REINSPECTION_REPORT_MISMATCH")
        records = [{"provider_receipt": row["provider_receipt"], "raw_text": row["raw_text"]}
                   for row in checked["stages"]]
        expected = _derive_report(snapshot, task, config, contract, program, records,
                                  checked["pre_dispatch_failure"])
    except (KeyError, TypeError, ValueError, AttributeError, IndexError):
        raise EBRTError("REINSPECTION_REPORT_MISMATCH") from None
    _require(_canonical_bytes(checked) == _canonical_bytes(expected), "REINSPECTION_REPORT_MISMATCH")
    return _seal({
        "status": "PASS", "plan_fingerprint_sha256": snapshot["fingerprint_sha256"],
        "report_fingerprint_sha256": checked["fingerprint_sha256"],
        "execution_status": checked["execution_status"], "checked_stages": len(records),
        "meaning": "Internal receipt consistency, not provider authenticity or reasoning quality.",
    })


def render_text(report: Mapping[str, Any]) -> str:
    return "\n".join([
        f"Budgeted public reinspection: {report['status']}; execution={report['execution_status']}",
        f"Provider attempts: {report['actual_provider_calls']}/{report['planned_provider_attempts']} planned; hard limit {report['max_provider_attempts']}",
        f"Audit attempts: {report['audit_provider_calls']}; final attempts: {report['final_provider_calls']}",
        f"Requested output-token ceilings: {report['total_requested_output_token_ceiling']}/{report['total_planned_output_token_ceiling']} planned",
        f"Public-source audits: {report['actuator_execution_status']}; final structure: {report['structural_verification']['status']}; output contract: {report['semantic_correctness_status']}",
        "Ceilings are request settings, not consumed compute. Signed controls remain provenance only.",
        "No gradient-specific or general quality improvement claim.",
    ]) + "\n"


def _load(path: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        _require(type(value) is dict, "REINSPECTION_JSON_INVALID")
        return value
    except (OSError, ValueError):
        raise EBRTError("REINSPECTION_JSON_UNREADABLE") from None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan_cmd = commands.add_parser("plan", help="compile an offline, bounded reinspection plan")
    plan_cmd.add_argument("--model", required=True)
    case_ids = tuple(case.task.task_id for case in build_cases())
    plan_cmd.add_argument("--case", choices=case_ids, default=case_ids[0])
    plan_cmd.add_argument("--reasoning-effort", default="low")
    plan_cmd.add_argument("--audit-total-tokens", type=int, default=768)
    plan_cmd.add_argument("--audit-min-tokens", type=int, default=128)
    plan_cmd.add_argument("--final-max-output-tokens", type=int, default=512)
    plan_cmd.add_argument("--timeout", type=float, default=60.0)
    plan_cmd.add_argument("--output", required=True)
    run_cmd = commands.add_parser("run", help="execute selected-site audits and one final generation")
    run_cmd.add_argument("--plan", required=True)
    run_cmd.add_argument("--output", required=True)
    verify_cmd = commands.add_parser("verify", help="recompute reports without provider calls")
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
            case = next(case for case in build_cases() if case.task.task_id == args.case)
            config = ReinspectionConfig(
                model=args.model, reasoning_effort=args.reasoning_effort,
                audit_total_tokens=args.audit_total_tokens, audit_min_tokens=args.audit_min_tokens,
                final_max_output_tokens=args.final_max_output_tokens, timeout_seconds=args.timeout,
            )
            result = build_plan(case.task, config, post_run_contract=case.contract)
            output = _open_output(args.output)
        else:
            plan = _load(args.plan)
            validate_plan(plan)
            output = _open_output(args.output)
            result = run_plan(plan)
        json.dump(result, output, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        output.write("\n")
        print(f"Reinspection plan saved: {result['planned_provider_attempts']} planned provider attempts, no API calls."
              if args.command == "plan" else render_text(result), end="\n" if args.command == "plan" else "")
        return 0 if args.command == "plan" or result["status"] == "PASS" else 1
    except EBRTError as failure:
        if output:
            json.dump({"status": "ERROR", "privacy": PRIVACY, "error_code": str(failure)}, output)
            output.write("\n")
        print(f"Reinspection failed: {failure}", file=sys.stderr)
        return 1
    except OSError:
        print("Reinspection failed: REINSPECTION_FILE_IO_FAILED", file=sys.stderr)
        return 1
    finally:
        if output:
            output.close()


if __name__ == "__main__":
    raise SystemExit(main())
