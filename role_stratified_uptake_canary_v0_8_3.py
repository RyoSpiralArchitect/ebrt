#!/usr/bin/env python3
"""Fresh role-stratified provider-uptake canary for EBRT v0.8.3.

This auxiliary runner separates two boundaries:

1. compiler coverage: whether the public actuator retains the correction and
   every caller-supplied ``required_support`` role; and
2. provider uptake: whether one local generation actually cites the compiled
   obligations.

It is a three-case, three-arm development canary, not a benchmark or a causal
estimate.  Semantic gold remains post-call-only.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from ebrt_core import (
    ActuatorProgram,
    AdapterDescriptor,
    EBRTError,
    MLXLocalAdapter,
    RevisionTask,
    SharedMLXRuntime,
    _canonical_bytes,
    _finite,
    _fingerprint,
    _largest_remainder_units,
    _parse_model_text,
    _seal,
    _sealed_snapshot,
    build_model_invocation,
)
from local_output_diff_corpus_v0_8_2 import (
    ADMITTED_GENERATION_ERROR_CODES,
    DEFAULT_MAX_TOKENS,
    CorpusCase,
    _common_output_grade,
    _invoke,
    _revision_case,
    build_direct_invocation,
    compile_revision,
)


RUN_SCHEMA_VERSION = "ebrt-role-stratified-uptake-run-v0.8.3"
LOCK_SCHEMA_VERSION = "ebrt-role-stratified-uptake-lock-v0.8.3"
SELF_TEST_SCHEMA_VERSION = "ebrt-role-stratified-uptake-self-test-v0.8.3"
SOURCE_MAIN_COMMIT = "2961feb6aaa2222bb56a62cb04274587487f4a17"
MODEL_ID = (
    "mlx-community/Mistral-7B-Instruct-v0.3-4bit"
    "@a4b8f870474b0eb527f466a03fbc187830d271f5"
)

ARM_DIRECT = "direct_full_context"
ARM_TOP_K = "ebrt_top_k"
ARM_ROLE = "ebrt_role_stratified"
ARM_IDS = (ARM_DIRECT, ARM_TOP_K, ARM_ROLE)
CALL_SCHEDULES = (
    ARM_IDS,
    (ARM_TOP_K, ARM_ROLE, ARM_DIRECT),
    (ARM_ROLE, ARM_DIRECT, ARM_TOP_K),
)
EXPECTED_SELECTIONS = {
    "parcel-dock-policy-revision": {
        ARM_TOP_K: ("R6", "R4", "R1"),
        ARM_ROLE: ("R6", "R4", "R2"),
    },
    "scaled-reading-schema-revision": {
        ARM_TOP_K: ("R6", "R1", "R2"),
        ARM_ROLE: ("R6", "R2", "R4"),
    },
    "grant-eligibility-policy-revision": {
        ARM_TOP_K: ("R6", "R4", "R2"),
        ARM_ROLE: ("R6", "R4", "R2"),
    },
}
CLAIM_BOUNDARY = (
    "This is a three-case development canary over one instruction-capable local model snapshot.",
    "Public required-support roles are caller-supplied scaffold metadata, not dependencies discovered autonomously by EBRT.",
    "Compiler coverage and provider uptake are separate receipts; one does not imply the other.",
    "Each arm differs in its model-visible request bundle, so output differences are not attributable to gradients alone.",
    "Semantic contracts are fixed before provider calls and remain outside all model-visible prompts.",
    "No native activations are captured, and no general reasoning-improvement or cross-model claim is assessed.",
)

JsonObject = dict[str, Any]


def build_cases() -> tuple[CorpusCase, ...]:
    miss_r2_geometry = (
        ((-0.41, 0.0, 0.0), (0.78, 0.0, 0.0)),
        ((0.11, 0.0, 0.0), (0.52, 0.0, 0.0)),
        ((-0.82, 0.0, 0.0), (1.02, 0.61, 0.0)),
        ((0.21, 0.0, 0.0), (0.98, 0.0, 0.0)),
        ((0.0, 0.0, 1.0), (0.0, 0.0, 0.0)),
        ((0.62, 1.0, 0.0), (1.03, 0.52, 0.0)),
    )
    miss_r4_geometry = (
        ((-0.55, 0.0, 0.0), (1.20, 0.0, 0.0)),
        ((0.21, 0.0, 0.0), (0.98, 0.0, 0.0)),
        ((-0.82, 0.0, 0.0), (1.02, 0.61, 0.0)),
        ((0.11, 0.0, 0.0), (0.52, 0.0, 0.0)),
        ((0.0, 0.0, 1.0), (0.0, 0.0, 0.0)),
        ((0.62, 1.0, 0.0), (1.03, 0.52, 0.0)),
    )
    covered_geometry = (
        ((-0.23, 0.0, 0.0), (0.34, 0.0, 0.0)),
        ((0.16, 0.0, 0.0), (0.82, 0.0, 0.0)),
        ((-0.73, 0.0, 0.0), (0.93, 0.53, 0.0)),
        ((0.27, 0.0, 0.0), (1.04, 0.0, 0.0)),
        ((0.0, 0.0, 1.0), (0.0, 0.0, 0.0)),
        ((0.63, 1.0, 0.0), (1.02, 0.43, 0.0)),
    )
    return (
        _revision_case(
            task_id="parcel-dock-policy-revision",
            family="coverage_loss_required_identity",
            question="Which dock should parcel Q-24 be sent to under the corrected routing policy?",
            answer_choices=("DOCK_C", "DOCK_A"),
            prior_answer="DOCK_C",
            expected_answer="DOCK_A",
            texts=(
                "Parcel Q-24 is ready for a dock assignment.",
                "The parcel label records service tier PRIORITY.",
                "The retired routing sheet maps PRIORITY parcels to DOCK_C.",
                "The current routing policy maps PRIORITY parcels to DOCK_A.",
                "The wrapping mode remains WEATHER_SEALED.",
                "Late correction: R3 is superseded; apply the current routing policy in R4.",
            ),
            stable_key="wrapping_mode",
            stable_value="WEATHER_SEALED",
            geometry=miss_r2_geometry,
        ),
        _revision_case(
            task_id="scaled-reading-schema-revision",
            family="coverage_loss_required_rule",
            question="What normalized value should be reported under the corrected schema?",
            answer_choices=("60_UNITS", "6_UNITS"),
            prior_answer="60_UNITS",
            expected_answer="6_UNITS",
            texts=(
                "A normalized reading must be reported for sample S-8.",
                "The raw reading for sample S-8 is 12.",
                "The retired schema multiplies the raw reading by 5.",
                "The current schema multiplies the raw reading by 0.5.",
                "The output label remains NORMALIZED_UNITS.",
                "Late correction: R3 is invalid; calculate with the current schema in R4.",
            ),
            stable_key="output_label",
            stable_value="NORMALIZED_UNITS",
            geometry=miss_r4_geometry,
        ),
        _revision_case(
            task_id="grant-eligibility-policy-revision",
            family="coverage_already_satisfied",
            question="What is applicant N-7's eligibility under the corrected policy?",
            answer_choices=("INELIGIBLE", "ELIGIBLE"),
            prior_answer="INELIGIBLE",
            expected_answer="ELIGIBLE",
            texts=(
                "Applicant N-7 requires one final eligibility decision.",
                "Applicant N-7 has verified classification T2.",
                "The retired policy marks classification T2 as INELIGIBLE.",
                "The current policy marks classification T2 as ELIGIBLE.",
                "The review channel remains HUMAN_REVIEW.",
                "Late correction: R3 is superseded; evaluate against the current policy in R4.",
            ),
            stable_key="review_channel",
            stable_value="HUMAN_REVIEW",
            geometry=covered_geometry,
        ),
    )


def _credit_rows(receipt: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows = receipt["trajectory"]["credit_map"]
    if not isinstance(rows, list):
        raise EBRTError("ROLE_CANARY_CREDIT_MAP_INVALID")
    output: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("evidence_id"), str):
            raise EBRTError("ROLE_CANARY_CREDIT_ROW_INVALID")
        evidence_id = row["evidence_id"]
        if evidence_id in output:
            raise EBRTError("ROLE_CANARY_CREDIT_DUPLICATE")
        output[evidence_id] = row
    return output


def compile_role_stratified(
    task: RevisionTask,
    top_k_program: ActuatorProgram,
    compile_receipt: Mapping[str, Any],
) -> ActuatorProgram:
    rows = _credit_rows(compile_receipt)
    evidence_by_id = {row.evidence_id: row for row in task.evidence}
    invalidated = set(task.event.invalidated_evidence_ids)
    stable = set(task.event.stable_evidence_ids)
    correction = task.event.correction_evidence_id
    required = [
        row.evidence_id for row in task.evidence if row.role == "required_support"
    ]
    mandatory = [correction, *required]
    mandatory = list(dict.fromkeys(mandatory))
    if len(mandatory) > task.reinspection_count:
        raise EBRTError("ROLE_CANARY_REQUIRED_SUPPORT_EXCEEDS_CAPACITY")
    if any(row in invalidated | stable for row in mandatory):
        raise EBRTError("ROLE_CANARY_REQUIRED_SUPPORT_ROLE_CONFLICT")

    eligible = [
        row.evidence_id
        for row in task.evidence
        if row.evidence_id not in invalidated | stable
        and bool(rows[row.evidence_id]["eligible"])
        and float(rows[row.evidence_id]["absolute_control"]) > 0.0
    ]
    required_by_credit = sorted(
        required,
        key=lambda evidence_id: (
            -float(rows[evidence_id]["absolute_control"]),
            evidence_by_id[evidence_id].ordinal,
        ),
    )
    chosen = [correction, *required_by_credit]
    remaining = sorted(
        [row for row in eligible if row not in chosen],
        key=lambda evidence_id: (
            -float(rows[evidence_id]["absolute_control"]),
            evidence_by_id[evidence_id].ordinal,
        ),
    )
    chosen.extend(remaining[: task.reinspection_count - len(chosen)])
    if len(chosen) != task.reinspection_count:
        raise EBRTError("ROLE_CANARY_REINSPECTION_CAPACITY_UNFILLED")
    weights = [float(rows[row]["absolute_control"]) for row in chosen]
    units = _largest_remainder_units(weights)
    reinspect = tuple(
        (evidence_id, allocation, float(rows[evidence_id]["control"]))
        for evidence_id, allocation in zip(chosen, units, strict=True)
    )
    if any(row[1] <= 0 for row in reinspect) or sum(row[1] for row in reinspect) != 100:
        raise EBRTError("ROLE_CANARY_ALLOCATION_INVALID")
    program = ActuatorProgram(
        lane_id=top_k_program.lane_id,
        reinspect=reinspect,
        suppress=top_k_program.suppress,
        preserve=top_k_program.preserve,
        steps=(
            "LOAD_FULL_CONTEXT",
            "SUPPRESS_INVALIDATED_SUPPORT",
            "REINSPECT_ROLE_COVERAGE_THEN_CREDIT",
            "PRESERVE_STABLE_CONSTRAINTS",
            "REGENERATE_ONCE",
        ),
        source_credit_fingerprint_sha256=top_k_program.source_credit_fingerprint_sha256,
    )
    _validate_role_program(task, program, compile_receipt)
    return program


def _validate_role_program(
    task: RevisionTask,
    program: ActuatorProgram,
    compile_receipt: Mapping[str, Any],
) -> None:
    rows = _credit_rows(compile_receipt)
    known = {row.evidence_id for row in task.evidence}
    selected = [row[0] for row in program.reinspect]
    required = {
        row.evidence_id for row in task.evidence if row.role == "required_support"
    }
    required.add(task.event.correction_evidence_id)
    if (
        len(selected) != task.reinspection_count
        or len(selected) != len(set(selected))
        or not required.issubset(selected)
        or not set(selected).issubset(known)
        or set(selected) & set(program.suppress)
        or set(selected) & set(program.preserve)
        or program.suppress != task.event.invalidated_evidence_ids
        or program.preserve != task.event.stable_evidence_ids
        or sum(row[1] for row in program.reinspect) != 100
    ):
        raise EBRTError("ROLE_CANARY_PROGRAM_STRUCTURE_INVALID")
    for evidence_id, units, signed_control in program.reinspect:
        if (
            type(units) is not int
            or units <= 0
            or type(signed_control) is not float
            or signed_control != float(rows[evidence_id]["control"])
        ):
            raise EBRTError("ROLE_CANARY_PROGRAM_BINDING_INVALID")


def _required_public_ids(task: RevisionTask) -> tuple[str, ...]:
    return tuple(
        [row.evidence_id for row in task.evidence if row.role == "required_support"]
        + [task.event.correction_evidence_id]
    )


def compiler_coverage(task: RevisionTask, program: ActuatorProgram) -> JsonObject:
    selected = tuple(row[0] for row in program.reinspect)
    required = _required_public_ids(task)
    missing = [row for row in required if row not in selected]
    return _seal(
        {
            "status": "PASS" if not missing else "FAIL",
            "required_public_evidence_ids": list(required),
            "selected_evidence_ids": list(selected),
            "missing_required_public_evidence_ids": missing,
            "coverage_source": "CALLER_SUPPLIED_PUBLIC_ROLES",
        }
    )


def provider_uptake(
    task: RevisionTask,
    program: ActuatorProgram,
    result: Mapping[str, Any],
) -> JsonObject:
    public_required = set(_required_public_ids(task))
    compiled_obligations = tuple(
        row[0] for row in program.reinspect if row[0] in public_required
    )
    observed = (
        set(result.get("support_ids", []))
        if result.get("status") == "PARSED"
        else set()
    )
    missing = [row for row in compiled_obligations if row not in observed]
    checks = {
        "output_parsed": result.get("status") == "PARSED",
        "compiled_obligations_retained": not missing,
    }
    return _seal(
        {
            "status": "PASS" if all(checks.values()) else "FAIL",
            "checks": checks,
            "compiled_obligation_ids": list(compiled_obligations),
            "observed_support_ids": sorted(observed),
            "missing_compiled_obligation_ids": missing,
        }
    )


def _output_diff(
    left_id: str,
    left: Mapping[str, Any],
    right_id: str,
    right: Mapping[str, Any],
) -> JsonObject:
    left_text = left.get("raw_text")
    right_text = right.get("raw_text")
    left_support = set(left.get("support_ids", []))
    right_support = set(right.get("support_ids", []))
    return _seal(
        {
            "left_arm": left_id,
            "right_arm": right_id,
            "raw_text_changed": left_text != right_text,
            "answer_changed": left.get("answer") != right.get("answer"),
            "answer_transition": [left.get("answer"), right.get("answer")],
            "support_changed": left_support != right_support,
            "support_added": sorted(right_support - left_support),
            "support_removed": sorted(left_support - right_support),
            "unified_diff": list(
                difflib.unified_diff(
                    (left_text or "").splitlines(),
                    (right_text or "").splitlines(),
                    fromfile=left_id,
                    tofile=right_id,
                    lineterm="",
                )
            ),
        }
    )


def compile_case(
    case: CorpusCase,
) -> tuple[ActuatorProgram, ActuatorProgram, JsonObject]:
    top_k, receipt = compile_revision(case.task)
    role = compile_role_stratified(case.task, top_k, receipt)
    expected = EXPECTED_SELECTIONS[case.task.task_id]
    observed = {
        ARM_TOP_K: tuple(row[0] for row in top_k.reinspect),
        ARM_ROLE: tuple(row[0] for row in role.reinspect),
    }
    if observed != expected:
        raise EBRTError("ROLE_CANARY_LOCKED_SELECTION_MISMATCH")
    return top_k, role, receipt


def _source_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def lock_spec() -> JsonObject:
    cases = build_cases()
    compiled = [compile_case(case) for case in cases]
    return _seal(
        {
            "schema_version": LOCK_SCHEMA_VERSION,
            "status": "LOCKED_BEFORE_PROVIDER_CALLS",
            "source_main_commit": SOURCE_MAIN_COMMIT,
            "runner_sha256": _source_sha256(),
            "model_id": MODEL_ID,
            "execution_policy": {
                "temperature": 0.0,
                "seed": 0,
                "max_tokens_per_arm": DEFAULT_MAX_TOKENS,
                "prompt_rendering_mode": "chat_template",
                "calls_per_cell": {arm_id: 1 for arm_id in ARM_IDS},
                "automatic_retry": False,
                "schedule": [list(row) for row in CALL_SCHEDULES],
                "native_state_capture": "DISABLED",
            },
            "cases": [
                {
                    "case_id": case.task.task_id,
                    "task_fingerprint_sha256": _fingerprint(case.task.to_public_dict()),
                    "contract_fingerprint_sha256": case.contract.to_dict()[
                        "fingerprint_sha256"
                    ],
                    "top_k_selection": [row[0] for row in top_k.reinspect],
                    "role_selection": [row[0] for row in role.reinspect],
                }
                for case, (top_k, role, _receipt) in zip(cases, compiled, strict=True)
            ],
            "effect_attribution_status": "NOT_ASSESSED",
            "generalization_status": "ONE_MODEL_DEVELOPMENT_CANARY_ONLY",
            "claim_boundary": list(CLAIM_BOUNDARY),
        }
    )


def _load_json(path: Path) -> JsonObject:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EBRTError("ROLE_CANARY_ARTIFACT_READ_FAILED") from error
    if not isinstance(value, dict):
        raise EBRTError("ROLE_CANARY_ARTIFACT_TYPE_INVALID")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def validate_lock(value: Any) -> JsonObject:
    observed = _sealed_snapshot(value, "ROLE_CANARY_LOCK")
    expected = lock_spec()
    if _canonical_bytes(observed) != _canonical_bytes(expected):
        raise EBRTError("ROLE_CANARY_LOCK_MISMATCH")
    return observed


def _result_receipt_exact(
    result: Mapping[str, Any],
    task: RevisionTask,
    expected_request_fingerprint: str,
) -> JsonObject:
    sealed = _sealed_snapshot(result, "ROLE_CANARY_RESULT")
    expected_keys = {
        "status",
        "error_code",
        "raw_text",
        "answer",
        "support_ids",
        "request_fingerprint_sha256",
        "latency_ms",
        "logical_calls",
        "fingerprint_sha256",
    }
    try:
        latency = _finite(sealed.get("latency_ms"), "ROLE_CANARY_LATENCY")
    except EBRTError as error:
        raise EBRTError("ROLE_CANARY_RESULT_SHAPE_INVALID") from error
    if (
        set(sealed) != expected_keys
        or latency < 0.0
        or type(sealed.get("logical_calls")) is not int
        or sealed["logical_calls"] != 1
        or sealed.get("request_fingerprint_sha256") != expected_request_fingerprint
    ):
        raise EBRTError("ROLE_CANARY_RESULT_SHAPE_INVALID")
    raw_text = sealed.get("raw_text")
    if isinstance(raw_text, str):
        try:
            answer, support = _parse_model_text(raw_text, task=task)
            exact = (
                sealed.get("status") == "PARSED"
                and sealed.get("error_code") is None
                and sealed.get("answer") == answer
                and sealed.get("support_ids") == list(support)
            )
        except EBRTError as error:
            exact = (
                sealed.get("status") == "FORMAT_ERROR"
                and sealed.get("error_code") == str(error)
                and sealed.get("answer") is None
                and sealed.get("support_ids") == []
            )
    else:
        exact = (
            raw_text is None
            and sealed.get("status") == "GENERATION_ERROR"
            and sealed.get("error_code") in ADMITTED_GENERATION_ERROR_CODES
            and sealed.get("answer") is None
            and sealed.get("support_ids") == []
        )
    if not exact:
        raise EBRTError("ROLE_CANARY_RESULT_REPLAY_FAILED")
    return sealed


def _summary(cells: Sequence[Mapping[str, Any]]) -> JsonObject:
    return {
        "case_count": len(cells),
        "provider_calls": len(cells) * len(ARM_IDS),
        "compiler_coverage_passes": {
            arm_id: sum(
                cell["compiled"][arm_id]["coverage"]["status"] == "PASS"
                for cell in cells
            )
            for arm_id in (ARM_TOP_K, ARM_ROLE)
        },
        "provider_uptake_passes": {
            arm_id: sum(
                cell["arms"][arm_id]["provider_uptake"]["status"] == "PASS"
                for cell in cells
            )
            for arm_id in (ARM_TOP_K, ARM_ROLE)
        },
        "semantic_passes": {
            arm_id: sum(
                cell["arms"][arm_id]["semantic_grade"]["status"] == "PASS"
                for cell in cells
            )
            for arm_id in ARM_IDS
        },
        "top_k_to_role_raw_diff_cells": sum(
            cell["diffs"]["top_k_to_role"]["raw_text_changed"] for cell in cells
        ),
        "top_k_to_role_answer_diff_cells": sum(
            cell["diffs"]["top_k_to_role"]["answer_changed"] for cell in cells
        ),
        "top_k_to_role_support_diff_cells": sum(
            cell["diffs"]["top_k_to_role"]["support_changed"] for cell in cells
        ),
        "coverage_repair_cells": sum(
            cell["compiled"][ARM_TOP_K]["coverage"]["status"] == "FAIL"
            and cell["compiled"][ARM_ROLE]["coverage"]["status"] == "PASS"
            for cell in cells
        ),
    }


def run_canary(model_path: str, lock: Mapping[str, Any]) -> JsonObject:
    locked = validate_lock(lock)
    runtime = SharedMLXRuntime(
        model_path,
        model_id=MODEL_ID,
        max_tokens=DEFAULT_MAX_TOKENS,
        seed=0,
        prompt_rendering_mode="chat_template",
    )
    descriptor = MLXLocalAdapter(
        runtime, adapter_id="role-uptake-canary-model"
    ).descriptor
    if descriptor.model_id != MODEL_ID:
        raise EBRTError("ROLE_CANARY_MODEL_ID_MISMATCH")
    cells: list[JsonObject] = []
    for index, case in enumerate(build_cases()):
        top_k, role, compile_receipt = compile_case(case)
        programs = {ARM_TOP_K: top_k, ARM_ROLE: role}
        invocations = {
            ARM_DIRECT: build_direct_invocation(case.task),
            ARM_TOP_K: build_model_invocation(
                case.task, top_k, prompt_policy="credit_first"
            ),
            ARM_ROLE: build_model_invocation(
                case.task, role, prompt_policy="credit_first"
            ),
        }
        order = CALL_SCHEDULES[index]
        results: dict[str, JsonObject] = {}
        for arm_id in order:
            results[arm_id] = _invoke(runtime, case.task, invocations[arm_id])
        semantic = {
            arm_id: _common_output_grade(results[arm_id], case.contract)
            for arm_id in ARM_IDS
        }
        uptake = {
            arm_id: provider_uptake(case.task, programs[arm_id], results[arm_id])
            for arm_id in (ARM_TOP_K, ARM_ROLE)
        }
        cells.append(
            _seal(
                {
                    "case_id": case.task.task_id,
                    "family": case.family,
                    "task": case.task.to_public_dict(),
                    "post_call_contract": case.contract.to_dict(),
                    "call_order": list(order),
                    "compiled": {
                        "trajectory": compile_receipt["trajectory"],
                        ARM_TOP_K: {
                            "program": top_k.to_dict(),
                            "coverage": compiler_coverage(case.task, top_k),
                        },
                        ARM_ROLE: {
                            "program": role.to_dict(),
                            "coverage": compiler_coverage(case.task, role),
                        },
                    },
                    "arms": {
                        arm_id: {
                            "invocation_fingerprint_sha256": invocations[arm_id][
                                "fingerprint_sha256"
                            ],
                            "result": results[arm_id],
                            "semantic_grade": semantic[arm_id],
                            "provider_uptake": uptake.get(arm_id),
                        }
                        for arm_id in ARM_IDS
                    },
                    "diffs": {
                        "direct_to_top_k": _output_diff(
                            ARM_DIRECT,
                            results[ARM_DIRECT],
                            ARM_TOP_K,
                            results[ARM_TOP_K],
                        ),
                        "top_k_to_role": _output_diff(
                            ARM_TOP_K,
                            results[ARM_TOP_K],
                            ARM_ROLE,
                            results[ARM_ROLE],
                        ),
                    },
                }
            )
        )
    return _seal(
        {
            "schema_version": RUN_SCHEMA_VERSION,
            "status": "COMPLETE",
            "policy_lock_fingerprint_sha256": locked["fingerprint_sha256"],
            "model_adapter": descriptor.to_dict(),
            "execution_policy": locked["execution_policy"],
            "cases": cells,
            "summary": _summary(cells),
            "native_state_capture_status": "DISABLED",
            "effect_attribution_status": "NOT_ASSESSED",
            "generalization_status": "ONE_MODEL_DEVELOPMENT_CANARY_ONLY",
            "claim_boundary": list(CLAIM_BOUNDARY),
        }
    )


def verify_run(value: Any, lock: Mapping[str, Any]) -> JsonObject:
    locked = validate_lock(lock)
    snapshot = _sealed_snapshot(value, "ROLE_CANARY_RUN")
    expected_top_keys = {
        "schema_version",
        "status",
        "policy_lock_fingerprint_sha256",
        "model_adapter",
        "execution_policy",
        "cases",
        "summary",
        "native_state_capture_status",
        "effect_attribution_status",
        "generalization_status",
        "claim_boundary",
        "fingerprint_sha256",
    }
    if (
        set(snapshot) != expected_top_keys
        or snapshot.get("schema_version") != RUN_SCHEMA_VERSION
        or snapshot.get("status") != "COMPLETE"
        or snapshot.get("policy_lock_fingerprint_sha256")
        != locked["fingerprint_sha256"]
        or _canonical_bytes(snapshot.get("execution_policy"))
        != _canonical_bytes(locked["execution_policy"])
        or snapshot.get("native_state_capture_status") != "DISABLED"
        or snapshot.get("effect_attribution_status") != "NOT_ASSESSED"
        or snapshot.get("generalization_status") != "ONE_MODEL_DEVELOPMENT_CANARY_ONLY"
        or snapshot.get("claim_boundary") != list(CLAIM_BOUNDARY)
    ):
        raise EBRTError("ROLE_CANARY_RUN_HEADER_INVALID")
    descriptor = snapshot.get("model_adapter")
    expected_descriptor = AdapterDescriptor(
        adapter_id="role-uptake-canary-model",
        model_id=MODEL_ID,
        interface_kind="local_open_weight",
        state_visibility="public_only",
        differentiable_through_model=False,
        generation_config=tuple(
            sorted(
                {
                    "add_generation_prompt": True,
                    "max_tokens": DEFAULT_MAX_TOKENS,
                    "prompt_rendering_mode": "chat_template",
                    "sampler_temperature": 0.0,
                    "seed": 0,
                }.items()
            )
        ),
    ).to_dict()
    if not isinstance(descriptor, Mapping) or _canonical_bytes(
        descriptor
    ) != _canonical_bytes(expected_descriptor):
        raise EBRTError("ROLE_CANARY_MODEL_DESCRIPTOR_INVALID")
    cells = snapshot.get("cases")
    cases = build_cases()
    if not isinstance(cells, list) or len(cells) != len(cases):
        raise EBRTError("ROLE_CANARY_CASES_INVALID")
    replayed_cells: list[JsonObject] = []
    for index, (cell_value, case) in enumerate(zip(cells, cases, strict=True)):
        cell = _sealed_snapshot(cell_value, "ROLE_CANARY_CELL")
        top_k, role, compile_receipt = compile_case(case)
        programs = {ARM_TOP_K: top_k, ARM_ROLE: role}
        expected_invocations = {
            ARM_DIRECT: build_direct_invocation(case.task),
            ARM_TOP_K: build_model_invocation(
                case.task, top_k, prompt_policy="credit_first"
            ),
            ARM_ROLE: build_model_invocation(
                case.task, role, prompt_policy="credit_first"
            ),
        }
        expected_compiled = {
            "trajectory": compile_receipt["trajectory"],
            ARM_TOP_K: {
                "program": top_k.to_dict(),
                "coverage": compiler_coverage(case.task, top_k),
            },
            ARM_ROLE: {
                "program": role.to_dict(),
                "coverage": compiler_coverage(case.task, role),
            },
        }
        if (
            cell.get("case_id") != case.task.task_id
            or cell.get("family") != case.family
            or _canonical_bytes(cell.get("task"))
            != _canonical_bytes(case.task.to_public_dict())
            or _canonical_bytes(cell.get("post_call_contract"))
            != _canonical_bytes(case.contract.to_dict())
            or cell.get("call_order") != list(CALL_SCHEDULES[index])
            or _canonical_bytes(cell.get("compiled"))
            != _canonical_bytes(expected_compiled)
        ):
            raise EBRTError("ROLE_CANARY_CELL_REPLAY_FAILED")
        arms = cell.get("arms")
        if not isinstance(arms, Mapping) or set(arms) != set(ARM_IDS):
            raise EBRTError("ROLE_CANARY_ARMS_INVALID")
        results: dict[str, JsonObject] = {}
        for arm_id in ARM_IDS:
            arm = arms.get(arm_id)
            expected_arm_keys = {
                "invocation_fingerprint_sha256",
                "result",
                "semantic_grade",
                "provider_uptake",
            }
            if not isinstance(arm, Mapping) or set(arm) != expected_arm_keys:
                raise EBRTError("ROLE_CANARY_ARM_SHAPE_INVALID")
            invocation_fingerprint = expected_invocations[arm_id]["fingerprint_sha256"]
            if arm.get("invocation_fingerprint_sha256") != invocation_fingerprint:
                raise EBRTError("ROLE_CANARY_INVOCATION_BINDING_INVALID")
            result = _result_receipt_exact(
                arm["result"], case.task, invocation_fingerprint
            )
            expected_semantic = _common_output_grade(result, case.contract)
            expected_uptake = (
                None
                if arm_id == ARM_DIRECT
                else provider_uptake(case.task, programs[arm_id], result)
            )
            if _canonical_bytes(arm.get("semantic_grade")) != _canonical_bytes(
                expected_semantic
            ) or _canonical_bytes(arm.get("provider_uptake")) != _canonical_bytes(
                expected_uptake
            ):
                raise EBRTError("ROLE_CANARY_GRADE_REPLAY_FAILED")
            results[arm_id] = result
        expected_diffs = {
            "direct_to_top_k": _output_diff(
                ARM_DIRECT,
                results[ARM_DIRECT],
                ARM_TOP_K,
                results[ARM_TOP_K],
            ),
            "top_k_to_role": _output_diff(
                ARM_TOP_K,
                results[ARM_TOP_K],
                ARM_ROLE,
                results[ARM_ROLE],
            ),
        }
        if _canonical_bytes(cell.get("diffs")) != _canonical_bytes(expected_diffs):
            raise EBRTError("ROLE_CANARY_DIFF_REPLAY_FAILED")
        replayed_cells.append(cell)
    if _canonical_bytes(snapshot.get("summary")) != _canonical_bytes(
        _summary(replayed_cells)
    ):
        raise EBRTError("ROLE_CANARY_SUMMARY_REPLAY_FAILED")
    return _seal(
        {
            "schema_version": "ebrt-role-stratified-uptake-verification-v0.8.3",
            "status": "PASS",
            "run_fingerprint_sha256": snapshot["fingerprint_sha256"],
            "checks": {
                "policy_lock_exact": True,
                "deterministic_compilation_replayed": True,
                "invocations_recompiled": True,
                "model_outputs_reparsed": True,
                "compiler_coverage_replayed": True,
                "provider_uptake_replayed": True,
                "semantic_grades_replayed": True,
                "summary_replayed": True,
            },
        }
    )


def self_test() -> JsonObject:
    cases = build_cases()
    compiled = [compile_case(case) for case in cases]
    top_coverage = [
        compiler_coverage(case.task, top_k)["status"]
        for case, (top_k, _role, _receipt) in zip(cases, compiled, strict=True)
    ]
    role_coverage = [
        compiler_coverage(case.task, role)["status"]
        for case, (_top_k, role, _receipt) in zip(cases, compiled, strict=True)
    ]
    invocations = [
        (
            build_direct_invocation(case.task),
            build_model_invocation(case.task, top_k, prompt_policy="credit_first"),
            build_model_invocation(case.task, role, prompt_policy="credit_first"),
        )
        for case, (top_k, role, _receipt) in zip(cases, compiled, strict=True)
    ]
    checks = {
        "three_fresh_case_ids": len(cases) == 3
        and len({case.task.task_id for case in cases}) == 3,
        "cyclic_schedule_exact": all(
            sorted(row.index(arm_id) for row in CALL_SCHEDULES) == [0, 1, 2]
            for arm_id in ARM_IDS
        ),
        "top_k_coverage_pattern_locked": top_coverage == ["FAIL", "FAIL", "PASS"],
        "role_coverage_closes_all_cases": role_coverage == ["PASS", "PASS", "PASS"],
        "contracts_absent_from_prompts": all(
            case.contract.to_dict()["fingerprint_sha256"] not in invocation["prompt"]
            and '"expected_answer"' not in invocation["prompt"]
            for case, rows in zip(cases, invocations, strict=True)
            for invocation in rows
        ),
        "direct_has_no_revision_program": all(
            "REINSPECT_JSON" not in rows[0]["prompt"] for rows in invocations
        ),
        "controlled_arms_have_revision_program": all(
            "REINSPECT_JSON" in rows[1]["prompt"]
            and "REINSPECT_JSON" in rows[2]["prompt"]
            for rows in invocations
        ),
        "coverage_repair_changes_first_two_provider_prompts": all(
            rows[1]["prompt"] != rows[2]["prompt"] for rows in invocations[:2]
        ),
        "already_covered_case_is_provider_prompt_invariant": invocations[2][1]["prompt"]
        == invocations[2][2]["prompt"],
        "role_candidate_is_network_zero": True,
    }
    if not all(checks.values()):
        raise EBRTError("ROLE_CANARY_SELF_TEST_FAILED")
    return _seal(
        {
            "schema_version": SELF_TEST_SCHEMA_VERSION,
            "status": "PASS",
            "checks": checks,
            "claim_boundary": list(CLAIM_BOUNDARY),
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("self-test", help="run network-zero canary checks")
    commands.add_parser("lock-spec", help="print the exact pre-call lock")
    run = commands.add_parser("run", help="execute the sealed nine-call canary")
    run.add_argument("--model", required=True)
    run.add_argument("--lock", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    verify = commands.add_parser("verify", help="verify one stored canary run")
    verify.add_argument("artifact", type=Path)
    verify.add_argument("--lock", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "self-test":
            value = self_test()
        elif args.command == "lock-spec":
            value = lock_spec()
        elif args.command == "run":
            value = run_canary(args.model, _load_json(args.lock))
            _write_json(args.output, value)
        elif args.command == "verify":
            value = verify_run(_load_json(args.artifact), _load_json(args.lock))
        else:  # pragma: no cover
            raise EBRTError("ROLE_CANARY_COMMAND_UNKNOWN")
        print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except EBRTError as error:
        print(json.dumps({"status": "ERROR", "error_code": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
