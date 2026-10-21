"""Offline admission and mutation checks for the coverage-first mainline."""

from __future__ import annotations

import contextlib
from dataclasses import replace
import importlib.util
import json
import math
from pathlib import Path
import socket
import sys
import unittest
from unittest import mock

import torch

import ebrt_core as legacy
import ebrt_engine as engine
from ebrt_support_cases import build_cases
from local_output_diff_corpus_v0_8_2 import compile_revision
from role_stratified_uptake_canary_v0_8_3 import compile_role_stratified


def clone(value):
    return json.loads(json.dumps(value))


def descriptor():
    return legacy.AdapterDescriptor(
        adapter_id="mainline-test-actual", model_id="deterministic/actual-generation@v1",
        interface_kind="deterministic_conformance", state_visibility="public_only",
        differentiable_through_model=False,
    )


def adapter_for(task, *, text=None, callback=None):
    requests = []

    def generate(invocation):
        requests.append(invocation)
        if callback is not None:
            callback(invocation)
        return text or f"ANSWER={task.answer_choices[-1]}\nSUPPORT=R6,R4,R2"

    return legacy.CallableModelAdapter(descriptor=descriptor(), callback=generate), requests


class CoverageFirstEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        stack = contextlib.ExitStack()
        cls.addClassCleanup(stack.close)
        for owner, name in (
            (socket, "create_connection"), (socket, "getaddrinfo"),
            (socket.socket, "connect"), (socket.socket, "connect_ex"),
        ):
            stack.enter_context(mock.patch.object(owner, name, side_effect=AssertionError("no network")))
        cls.task = legacy.build_demo_task()
        _, receipt = compile_revision(cls.task)
        cls.trajectory = receipt["trajectory"]

    def assert_blocked(self, task, *, expected=None, **kwargs):
        adapter, requests = adapter_for(task)
        with self.assertRaises(legacy.EBRTError) as caught:
            engine.RevisionEngine(**kwargs).run(task, adapter)
        if expected is not None:
            self.assertIn(expected, str(caught.exception))
        self.assertEqual(requests, [])
        return caught.exception

    def test_default_fresh_cases_cover_all_required_support_without_changing_controls(self) -> None:
        for case in build_cases():
            with self.subTest(case=case.task.task_id):
                top_k, old = compile_revision(case.task)
                candidate = compile_role_stratified(case.task, top_k, old)
                text = f"ANSWER={case.contract.expected_answer}\nSUPPORT=R6,R4,R2"
                adapter, requests = adapter_for(case.task, text=text)
                report = engine.RevisionEngine().run(case.task, adapter, post_run_contract=case.contract)
                self.assertEqual(len(requests), 1)
                self.assertEqual(report["engine_protocol"], "ebrt-coverage-first-engine-v1")
                self.assertEqual(report["actuator_policy"], "coverage_first_v1")
                self.assertEqual(report["trajectory"], old["trajectory"])
                self.assertEqual(report["actuator"], candidate.to_dict())
                self.assertEqual(report["post_run_contract"]["status"], "PASS")
                rows = report["actuator"]["reinspect"]
                self.assertEqual({row["evidence_id"] for row in rows}, {"R2", "R4", "R6"})
                self.assertEqual(len(rows), 3)
                self.assertEqual(sum(row["allocation_units"] for row in rows), 100)
                controls = {row["evidence_id"]: row["control"] for row in report["trajectory"]["credit_map"]}
                self.assertLessEqual(math.sqrt(sum(value * value for value in controls.values())),
                                     case.task.control_budget + 1e-12)
                self.assertTrue(all(row["signed_control"] == controls[row["evidence_id"]] for row in rows))
                old_prompt = legacy.build_model_invocation(case.task, candidate, prompt_policy="credit_first")
                self.assertEqual(requests[0]["prompt"], old_prompt["prompt"])

    def test_existing_demo_keeps_its_model_visible_prompt(self) -> None:
        old_program, _ = compile_revision(self.task)
        adapter, requests = adapter_for(self.task)
        report = engine.RevisionEngine().run(self.task, adapter)
        old_invocation = legacy.build_model_invocation(self.task, old_program, prompt_policy="credit_first")
        self.assertEqual(requests[0]["prompt"], old_invocation["prompt"])
        self.assertEqual(report["trajectory"], self.trajectory)

    def test_one_real_backward_precedes_exactly_one_actual_generation(self) -> None:
        backwards = []
        original_backward = torch.Tensor.backward

        def tracked(tensor, *args, **kwargs):
            backwards.append(tensor)
            return original_backward(tensor, *args, **kwargs)

        adapter, requests = adapter_for(self.task, callback=lambda _: self.assertEqual(len(backwards), 1))
        with mock.patch.object(torch.Tensor, "backward", tracked):
            report = engine.RevisionEngine().run(self.task, adapter)
        self.assertEqual(len(backwards), 1)
        self.assertEqual(len(requests), 1)
        self.assertTrue(report["trajectory"]["checks"]["real_backward_executed_once"])
        self.assertEqual(report["model_result"]["logical_calls"], 1)

    def test_changed_semantic_gold_cannot_change_the_actuator_or_actual_prompt(self) -> None:
        reports, requests = [], []
        contract = legacy.build_demo_contract()
        for gold in (contract, replace(contract, expected_answer="POLISH", required_support_ids=("R6",))):
            adapter, observed = adapter_for(self.task)
            reports.append(engine.RevisionEngine().run(self.task, adapter, post_run_contract=gold))
            requests.append(observed[0])
        self.assertEqual(reports[0]["actuator"], reports[1]["actuator"])
        self.assertEqual(requests[0], requests[1])
        self.assertEqual(reports[0]["post_run_contract"]["status"], "PASS")
        self.assertEqual(reports[1]["post_run_contract"]["status"], "FAIL")

    def test_compile_only_stage_does_not_receive_semantic_gold(self) -> None:
        original = legacy.RevisionEngine.run
        gold_arguments = []

        def capture(instance, *args, **kwargs):
            gold_arguments.append(kwargs.get("post_run_contract"))
            return original(instance, *args, **kwargs)

        adapter, requests = adapter_for(self.task)
        with mock.patch.object(legacy.RevisionEngine, "run", capture):
            engine.RevisionEngine().run(self.task, adapter, post_run_contract=legacy.build_demo_contract())
        self.assertEqual(gold_arguments, [None])
        self.assertEqual(len(requests), 1)

    def test_actual_result_and_latency_replace_the_compile_only_stub_completely(self) -> None:
        results = []

        class ActualAdapter:
            descriptor = descriptor()

            def generate(self, task, program, *, prompt_policy):
                invocation = legacy.build_model_invocation(task, program, prompt_policy=prompt_policy)
                result = legacy.ModelResult(
                    answer="PROVE", support_ids=("R6", "R4", "R2"),
                    raw_text="ANSWER=PROVE\nSUPPORT=R6,R4,R2", descriptor=self.descriptor,
                    request_fingerprint_sha256=invocation["fingerprint_sha256"], latency_ms=123.456,
                )
                results.append(result.to_dict())
                return result

        report = engine.RevisionEngine().run(self.task, ActualAdapter())
        self.assertEqual(report["model_result"], results[0])
        self.assertEqual(report["model_result"]["latency_ms"], 123.456)
        self.assertNotIn("mainline-compile-only", json.dumps(report))
        self.assertNotIn("compile_only_receipt", report)
        self.assertNotIn("legacy_receipt", report)

    def test_observation_only_oscilloscope_receipt_survives_composition(self) -> None:
        policy = legacy.OscilloscopePolicy(event_window_radius=1, native_layer_indices=(0,), sampled_channels=4)
        first, _ = adapter_for(self.task)
        old = legacy.RevisionEngine(oscilloscope_policy=policy).run(self.task, first)
        second, requests = adapter_for(self.task)
        current = engine.RevisionEngine(oscilloscope_policy=policy).run(self.task, second)
        self.assertEqual(current["oscilloscope"], old["oscilloscope"])
        self.assertEqual(len(requests), 1)

    def test_mandatory_support_exceeding_k_fails_before_generation(self) -> None:
        self.assert_blocked(replace(self.task, reinspection_count=2), expected="COVERAGE_CAPACITY_EXCEEDED")

    def test_more_than_one_hundred_slots_is_rejected_without_using_a_receipt(self) -> None:
        extras = tuple(legacy.Evidence(
            f"X{index}", index, "Additional context.", "context", (0.0, 0.0, 0.0), (0.1, 0.0, 0.0)
        ) for index in range(6, 102))
        evidence = (*self.task.evidence[:5], *extras, replace(self.task.evidence[-1], ordinal=102))
        task = replace(self.task, evidence=evidence, reinspection_count=101,
                       before_horizon_evidence_ids=tuple(row.evidence_id for row in evidence[:-1]))
        legacy.validate_task(task)
        with self.assertRaisesRegex(legacy.EBRTError, "COVERAGE_CAPACITY_EXCEEDED"):
            engine.CoverageFirstActuator().compile(task, {}, lane_id="primary")

    def test_ineligible_and_zero_control_required_support_fail_before_generation(self) -> None:
        for basis in ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0)):
            with self.subTest(basis=basis):
                task = replace(self.task, evidence=tuple(
                    replace(row, control_basis=basis) if row.evidence_id == "R2" else row
                    for row in self.task.evidence
                ))
                self.assert_blocked(task, expected="COVERAGE_REQUIRED_CONTROL_UNAVAILABLE")

    def test_integer_allocation_rounded_to_zero_stops_before_generation(self) -> None:
        task = replace(self.task, evidence=tuple(
            replace(row, control_basis=(1e-9, 0.0, 0.0)) if row.evidence_id == "R2" else row
            for row in self.task.evidence
        ))
        self.assert_blocked(task, expected="COVERAGE_ALLOCATION_UNREPRESENTABLE")

    def test_unfillable_exact_selection_count_stops_before_generation(self) -> None:
        self.assert_blocked(replace(self.task, reinspection_count=5), expected="COVERAGE_SELECTION_CAPACITY_UNFILLED")

    def test_program_value_tampering_is_rejected_before_generation(self) -> None:
        def changed_row(program, index, value):
            rows = list(program.reinspect)
            row = list(rows[0])
            row[index] = value(row[index])
            rows[0] = tuple(row)
            return replace(program, reinspect=tuple(rows))

        mutations = {
            "units": lambda program: changed_row(program, 1, lambda units: units + 1),
            "sign": lambda program: changed_row(program, 2, lambda value: -value),
            "source": lambda program: replace(program, source_credit_fingerprint_sha256="0" * 64),
            "suppress": lambda program: replace(program, suppress=()),
            "preserve": lambda program: replace(program, preserve=()),
            "steps": lambda program: replace(program, steps=("REGENERATE_ONCE",)),
            "lane": lambda program: replace(program, lane_id="other"),
        }
        for name, mutation in mutations.items():
            with self.subTest(name=name):
                class TamperedActuator(engine.CoverageFirstActuator):
                    def compile(self, task, optimized, *, lane_id):
                        return mutation(super().compile(task, optimized, lane_id=lane_id))
                self.assert_blocked(self.task, actuator_adapter=TamperedActuator(),
                                    expected="COVERAGE_PROGRAM_BINDING_MISMATCH")

    def test_program_bool_tensor_and_subclass_fields_cannot_pass_canonical_comparison(self) -> None:
        class StringSubclass(str):
            pass

        class TupleSubclass(tuple):
            pass

        class ProgramSubclass(legacy.ActuatorProgram):
            pass

        program = engine.CoverageFirstActuator().compile(self.task, self.trajectory, lane_id="primary")
        first = program.reinspect[0]
        mutations = (
            replace(program, reinspect=((first[0], True, first[2]), *program.reinspect[1:])),
            replace(program, reinspect=((first[0], first[1], True), *program.reinspect[1:])),
            replace(program, reinspect=((first[0], first[1], torch.tensor(first[2])), *program.reinspect[1:])),
            replace(program, reinspect=TupleSubclass(program.reinspect)),
            replace(program, lane_id=StringSubclass(program.lane_id)),
            ProgramSubclass(**program.__dict__),
        )
        for index, changed in enumerate(mutations):
            with self.subTest(index=index):
                class InvalidActuator:
                    def compile(self, task, optimized, *, lane_id):
                        return changed
                self.assert_blocked(self.task, actuator_adapter=InvalidActuator(), expected="COVERAGE_PROGRAM_")

    def test_mutating_a_cloned_compile_receipt_cannot_change_the_trusted_trajectory(self) -> None:
        class MutatingActuator(engine.CoverageFirstActuator):
            def compile(self, task, optimized, *, lane_id):
                program = super().compile(task, optimized, lane_id=lane_id)
                optimized["credit_map"][0]["control"] = 999.0
                optimized["control_budget"] = 999.0
                return program

        adapter, requests = adapter_for(self.task)
        report = engine.RevisionEngine(actuator_adapter=MutatingActuator()).run(self.task, adapter)
        self.assertEqual(report["trajectory"], self.trajectory)
        self.assertEqual(len(requests), 1)

    def test_subclass_or_replayed_cores_cannot_bypass_actual_execution_verification(self) -> None:
        class CustomCore(legacy.BackwardRevisionCore):
            pass

        trajectory = clone(self.trajectory)

        class ReplayCore:
            def optimize(self, envelope):
                return clone(trajectory)

        for core in (CustomCore(), ReplayCore()):
            with self.subTest(core=type(core).__name__):
                self.assert_blocked(self.task, core=core, expected="CORE_EXECUTION_UNVERIFIED")

    def test_instance_optimizer_override_is_rejected_even_if_it_runs_real_backward(self) -> None:
        core = legacy.BackwardRevisionCore()
        original = core.optimize
        core.optimize = lambda envelope: original(envelope)
        self.assert_blocked(self.task, core=core, expected="CORE_EXECUTION_UNVERIFIED")

    def test_class_optimizer_override_is_rejected_even_if_it_runs_real_backward(self) -> None:
        original = legacy.BackwardRevisionCore.optimize
        with mock.patch.object(legacy.BackwardRevisionCore, "optimize", lambda instance, envelope: original(instance, envelope)):
            self.assert_blocked(self.task, expected="CORE_EXECUTION_UNVERIFIED")

    def test_optimizer_patch_before_new_engine_import_still_fails_the_original_pin(self) -> None:
        module_name = "ebrt_engine_adversarial_import_test"
        spec = importlib.util.spec_from_file_location(module_name, Path(engine.__file__))
        module = importlib.util.module_from_spec(spec)
        adapter, requests = adapter_for(self.task)
        with (
            mock.patch.object(legacy.BackwardRevisionCore, "optimize", return_value=clone(self.trajectory)),
            mock.patch.dict(sys.modules, {module_name: module}),
        ):
            spec.loader.exec_module(module)
            with self.assertRaisesRegex(legacy.EBRTError, "CORE_EXECUTION_UNVERIFIED"):
                module.RevisionEngine().run(self.task, adapter)
        self.assertEqual(requests, [])

    def test_descriptor_mutation_during_actual_generation_is_rejected(self) -> None:
        adapter, requests = adapter_for(self.task)

        def mutate(_):
            object.__setattr__(adapter.descriptor, "model_id", "deterministic/mutated")

        original = adapter.callback
        adapter.callback = lambda invocation: (mutate(invocation), original(invocation))[1]
        with self.assertRaisesRegex(legacy.EBRTError, "MODEL_ADAPTER_DESCRIPTOR_MUTATED"):
            engine.RevisionEngine().run(self.task, adapter)
        self.assertEqual(len(requests), 1)

    def test_task_program_and_contract_mutation_during_actual_generation_are_rejected(self) -> None:
        for target in ("task", "program", "contract"):
            with self.subTest(target=target):
                task = legacy.build_demo_task()
                contract = legacy.build_demo_contract()

                class MutatingAdapter:
                    descriptor = descriptor()

                    def generate(self, actual_task, program, *, prompt_policy):
                        invocation = legacy.build_model_invocation(actual_task, program, prompt_policy=prompt_policy)
                        if target == "task":
                            object.__setattr__(actual_task, "question", "Mutated question")
                        elif target == "program":
                            object.__setattr__(program, "suppress", ())
                        else:
                            object.__setattr__(contract, "expected_answer", "POLISH")
                        return legacy.ModelResult(
                            answer="PROVE", support_ids=("R6", "R4", "R2"), raw_text="ANSWER=PROVE\nSUPPORT=R6,R4,R2",
                            descriptor=self.descriptor, request_fingerprint_sha256=invocation["fingerprint_sha256"], latency_ms=1.0,
                        )

                with self.assertRaises(legacy.EBRTError):
                    engine.RevisionEngine().run(task, MutatingAdapter(), post_run_contract=contract)

    def test_changing_the_public_actuator_method_cannot_redefine_admitted_policy(self) -> None:
        original = engine.CoverageFirstActuator.compile

        def tampered(instance, task, optimized, *, lane_id):
            return replace(original(instance, task, optimized, lane_id=lane_id), preserve=())

        with mock.patch.object(engine.CoverageFirstActuator, "compile", tampered):
            self.assert_blocked(self.task, expected="COVERAGE_PROGRAM_BINDING_MISMATCH")

    def test_mainline_demo_remains_deterministic_and_exposes_the_policy(self) -> None:
        import ebrt_demo

        first, second = ebrt_demo.run_demo(), ebrt_demo.run_demo()
        self.assertEqual(first, second)
        self.assertEqual(first["engine_protocol"], "ebrt-coverage-first-engine-v1")
        self.assertEqual(first["actuator_policy"], "coverage_first_v1")
        self.assertNotIn("mainline-compile-only", json.dumps(first))


if __name__ == "__main__":
    unittest.main()
