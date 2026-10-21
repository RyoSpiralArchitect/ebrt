"""Mainline single-lane EBRT with required-support coverage before credit.

The historical core remains unchanged. Its admitted compile-only run retains
the original optimizer pin and run-local backward witness. This module owns
the coverage-first actuator and the one actual generation that follows it.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Literal, Mapping

import ebrt_core as legacy
from ebrt_core import (
    ActuatorAdapter, ActuatorProgram, AdapterDescriptor, BackwardRevisionCore,
    CallableModelAdapter, ModelAdapter, ModelResult, OscilloscopePolicy,
    PostRunContract, RevisionTask, StateAdapter, TypedPublicStateAdapter,
    _actuator_program_material, _canonical_bytes, _clone, _fingerprint,
    _grade_contract, _largest_remainder_units, _require, _seal,
    _structural_model_checks, _validate_adapter_descriptor,
    build_model_invocation, validate_contract, validate_task,
)


ENGINE_PROTOCOL = "ebrt-coverage-first-engine-v1"
ACTUATOR_POLICY = "coverage_first_v1"


def _compile_coverage(
    task: RevisionTask, optimized: Mapping[str, Any], *, lane_id: str,
) -> ActuatorProgram:
    validate_task(task)
    _require(task.reinspection_count <= 100, "COVERAGE_CAPACITY_EXCEEDED")
    credit = optimized.get("credit_map")
    _require(isinstance(credit, list) and all(
        isinstance(row, Mapping)
        and type(row.get("evidence_id")) is str and type(row.get("role")) is str
        and type(row.get("step")) is int and type(row.get("eligible")) is bool
        and all(type(row.get(key)) in (int, float)
                for key in ("gradient", "control", "absolute_control"))
        for row in credit
    ), "COVERAGE_CREDIT_FIELD_TYPE_INVALID")
    # This validates the sealed receipt, complete credit rows and their numeric
    # bindings. The engine has already verified the optimizer's execution.
    legacy.PublicRevisionActuator().compile(task, optimized, lane_id=lane_id)
    rows = {row["evidence_id"]: row for row in credit}
    evidence = {row.evidence_id: row for row in task.evidence}
    correction = task.event.correction_evidence_id
    required = [row.evidence_id for row in task.evidence if row.role == "required_support"]
    mandatory = [correction, *required]
    _require(len(mandatory) <= task.reinspection_count, "COVERAGE_CAPACITY_EXCEEDED")
    excluded = set(task.event.invalidated_evidence_ids) | set(task.event.stable_evidence_ids)
    available = {
        key for key, row in rows.items()
        if key not in excluded and row["eligible"] and row["absolute_control"] > 0.0
    }
    _require(set(mandatory).issubset(available), "COVERAGE_REQUIRED_CONTROL_UNAVAILABLE")

    def rank(evidence_id: str) -> tuple[float, int]:
        return -float(rows[evidence_id]["absolute_control"]), evidence[evidence_id].ordinal

    chosen = [correction, *sorted(required, key=rank)]
    remaining = sorted(available - set(chosen), key=rank)
    chosen.extend(remaining[:task.reinspection_count - len(chosen)])
    _require(len(chosen) == task.reinspection_count, "COVERAGE_SELECTION_CAPACITY_UNFILLED")
    units = _largest_remainder_units([float(rows[key]["absolute_control"]) for key in chosen])
    _require(all(value > 0 for value in units) and sum(units) == 100,
             "COVERAGE_ALLOCATION_UNREPRESENTABLE")
    return ActuatorProgram(
        lane_id=lane_id,
        reinspect=tuple((key, value, float(rows[key]["control"]))
                        for key, value in zip(chosen, units, strict=True)),
        suppress=task.event.invalidated_evidence_ids,
        preserve=task.event.stable_evidence_ids,
        steps=("LOAD_FULL_CONTEXT", "SUPPRESS_INVALIDATED_SUPPORT",
               "REINSPECT_ROLE_COVERAGE_THEN_CREDIT", "PRESERVE_STABLE_CONSTRAINTS",
               "REGENERATE_ONCE"),
        source_credit_fingerprint_sha256=optimized["fingerprint_sha256"],
    )


@dataclass(frozen=True)
class CoverageFirstActuator:
    """Cover caller-declared obligations or fail before external generation.

The configured count is exact. Ineligible or zero-credit mandatory sites,
insufficient slots, and integer allocations rounded to zero are rejected.
The signed control vector and its L2 budget are never changed.
"""

    adapter_id: str = "coverage-first-actuator-v1"

    def compile(self, task: RevisionTask, optimized: Mapping[str, Any], *, lane_id: str) -> ActuatorProgram:
        return _compile_coverage(task, optimized, lane_id=lane_id)


def validate_program(
    task: RevisionTask, optimized: Mapping[str, Any], program: ActuatorProgram, *, lane_id: str,
) -> None:
    """Bind all program fields to the admitted coverage policy, without gold."""
    _require(type(program) is ActuatorProgram, "COVERAGE_PROGRAM_TYPE_INVALID")
    _require(
        type(program.lane_id) is str and type(program.reinspect) is tuple
        and all(type(row) is tuple and len(row) == 3 and type(row[0]) is str
                and type(row[1]) is int and type(row[2]) is float for row in program.reinspect)
        and type(program.suppress) is tuple and all(type(row) is str for row in program.suppress)
        and type(program.preserve) is tuple and all(type(row) is str for row in program.preserve)
        and type(program.steps) is tuple and all(type(row) is str for row in program.steps)
        and type(program.source_credit_fingerprint_sha256) is str,
        "COVERAGE_PROGRAM_FIELD_TYPE_INVALID",
    )
    expected = _compile_coverage(task, optimized, lane_id=lane_id)
    _require(_canonical_bytes(_actuator_program_material(program))
             == _canonical_bytes(_actuator_program_material(expected)),
             "COVERAGE_PROGRAM_BINDING_MISMATCH")


class RevisionEngine:
    """Verified historical optimizer, admitted coverage-first generation."""

    def __init__(
        self, *, core: BackwardRevisionCore | None = None,
        state_adapter: StateAdapter | None = None,
        actuator_adapter: ActuatorAdapter | None = None,
        oscilloscope_policy: OscilloscopePolicy | None = None,
    ) -> None:
        self.core = BackwardRevisionCore() if core is None else core
        self.state_adapter = TypedPublicStateAdapter() if state_adapter is None else state_adapter
        self.actuator_adapter = CoverageFirstActuator() if actuator_adapter is None else actuator_adapter
        if oscilloscope_policy is not None:
            legacy._validate_oscilloscope_policy(oscilloscope_policy)
        self.oscilloscope_policy = oscilloscope_policy

    def run(
        self, task: RevisionTask, model_adapter: ModelAdapter, *, lane_id: str = "primary",
        prompt_policy: Literal["chronological", "credit_first"] = "credit_first",
        post_run_contract: PostRunContract | None = None,
    ) -> dict[str, Any]:
        validate_task(task)
        task_material = _canonical_bytes(task.to_public_dict())
        if post_run_contract is not None:
            validate_contract(task, post_run_contract)
        contract = replace(post_run_contract) if post_run_contract is not None else None
        contract_material = _canonical_bytes(contract.to_dict()) if contract is not None else None
        # This internal test double does not see semantic gold, contact a
        # provider, or contribute an answer/latency to the generation receipt.
        shim = CallableModelAdapter(
            descriptor=AdapterDescriptor(
                adapter_id="mainline-compile-only", model_id="deterministic/compile-only@v1",
                interface_kind="deterministic_conformance", state_visibility="public_only",
                differentiable_through_model=False,
            ),
            callback=lambda _invocation: (
                f"ANSWER={task.answer_choices[0]}\nSUPPORT={task.event.correction_evidence_id}"
            ),
        )
        compiled = legacy.RevisionEngine(
            core=self.core, state_adapter=self.state_adapter,
            oscilloscope_policy=self.oscilloscope_policy,
        ).run(task, shim, lane_id=lane_id, post_run_contract=None)
        _require(_canonical_bytes(task.to_public_dict()) == task_material, "COVERAGE_TASK_MUTATED")
        optimized = _clone(compiled["trajectory"])
        program = self.actuator_adapter.compile(task, _clone(optimized), lane_id=lane_id)
        _require(_canonical_bytes(task.to_public_dict()) == task_material, "COVERAGE_TASK_MUTATED")
        validate_program(task, optimized, program, lane_id=lane_id)

        descriptor = model_adapter.descriptor
        _require(type(descriptor) is AdapterDescriptor, "MODEL_ADAPTER_DESCRIPTOR_INVALID")
        _validate_adapter_descriptor(descriptor, "MODEL_ADAPTER")
        expected_descriptor = replace(descriptor)
        descriptor_material = _canonical_bytes(expected_descriptor.to_dict())
        expected_invocation = build_model_invocation(task, program, prompt_policy=prompt_policy)
        result = model_adapter.generate(task, program, prompt_policy=prompt_policy)
        _require(_canonical_bytes(task.to_public_dict()) == task_material, "COVERAGE_TASK_MUTATED")
        _require(post_run_contract is None or
                 _canonical_bytes(post_run_contract.to_dict()) == contract_material,
                 "POST_RUN_CONTRACT_MUTATED")
        validate_program(task, optimized, program, lane_id=lane_id)
        current_descriptor = model_adapter.descriptor
        _require(type(current_descriptor) is AdapterDescriptor
                 and _canonical_bytes(current_descriptor.to_dict()) == descriptor_material,
                 "MODEL_ADAPTER_DESCRIPTOR_MUTATED")
        _require(type(result) is ModelResult, "MODEL_RESULT_TYPE_INVALID")
        checks = _structural_model_checks(
            task, program, result, expected_descriptor=expected_descriptor,
            expected_request_fingerprint_sha256=expected_invocation["fingerprint_sha256"],
        )
        _require(all(checks.values()), "MODEL_RESULT_STRUCTURAL_FAILURE")
        grade = _grade_contract(result, program, contract) if contract is not None else {
            "status": "NOT_ASSESSED", "contract": None, "checks": {},
        }
        material = {
            "schema_version": "ebrt-coverage-first-result-v1", "mode": "single_lane_coverage_first_v1",
            "status": "PASS", "core_protocol": legacy.CORE_PROTOCOL_VERSION,
            "engine_protocol": ENGINE_PROTOCOL, "actuator_policy": ACTUATOR_POLICY,
            "task_fingerprint_sha256": _fingerprint(task.to_public_dict()),
            "trajectory": optimized, "actuator": program.to_dict(), "model_result": result.to_dict(),
            "structural_verification": {"status": "PASS", "checks": checks},
            "post_run_contract": grade, "semantic_correctness_status": grade["status"],
            "effect_attribution_status": "NOT_ASSESSED",
            "core_execution": "VERIFIED_BY_LEGACY_ENGINE",
            "claim_boundary": [*legacy.CLAIM_BOUNDARY,
                "Coverage-first selection uses caller-supplied evidence roles, not extracted dependencies.",
                "Capacity, realized-control, and allocation failures stop before the actual model call.",
                "The compile-only scripted boundary is not an external model generation.",
            ],
        }
        if "oscilloscope" in compiled:
            material["oscilloscope"] = compiled["oscilloscope"]
        return _seal(material)
