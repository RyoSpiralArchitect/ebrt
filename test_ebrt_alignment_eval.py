"""Offline checks of matched alignment and evidence-placement perturbations."""

from __future__ import annotations

import contextlib
from dataclasses import replace
import hashlib
import io
import json
import math
from pathlib import Path
import re
import socket
import stat
import tempfile
import unittest
from unittest import mock

import torch

import ebrt_alignment_eval as evaluation
from ebrt_alignment_cases import build_cases
from ebrt_core import AdapterDescriptor, CallableModelAdapter, EBRTError, _seal
from ebrt_engine import CoverageFirstActuator, RevisionEngine
from ebrt_hosted import HostedConfig
from local_output_diff_corpus_v0_8_2 import _program_from_receipt
from test_ebrt_hosted import FakeClient, MODEL, SECRET, response


def clone(value):
    return json.loads(json.dumps(value))


def reseal(value):
    material = clone(value)
    material.pop("fingerprint_sha256", None)
    return _seal(material)


def successful_client(plan, overrides=None):
    cases = {case["case_id"]: case for case in plan["cases"]}
    outcomes = []
    for index, entry in enumerate(plan["schedule"]):
        case = cases[entry["case_id"]]
        text = ("ANSWER=" + case["contract"]["expected_answer"] + "\nSUPPORT="
                + ",".join(case["contract"]["required_support_ids"]))
        outcome = (overrides or {}).get(index, text)
        outcomes.append(response(outcome) if isinstance(outcome, str) else outcome)
    return FakeClient(*outcomes)


def prompt_lines(invocation, prefix):
    return [line for line in invocation["prompt"].splitlines() if line.startswith(prefix)]


def reinspect(invocation):
    return json.loads(prompt_lines(invocation, "REINSPECT_JSON ")[0].removeprefix("REINSPECT_JSON "))


class AlignmentEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        stack = contextlib.ExitStack()
        cls.addClassCleanup(stack.close)
        for owner, name in (
            (socket, "create_connection"), (socket, "getaddrinfo"),
            (socket.socket, "connect"), (socket.socket, "connect_ex"),
        ):
            stack.enter_context(mock.patch.object(
                owner, name, side_effect=AssertionError("alignment tests cannot use the network")
            ))
        cls.config = HostedConfig(model=MODEL)
        cls.plan = evaluation.build_plan(cls.config)
        cls.report = evaluation.run_plan(cls.plan, client=successful_client(cls.plan))

    def invoke_cli(self, args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = evaluation.main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_case_answers_require_the_target_entity_join_and_include_an_unchanged_answer(self) -> None:
        invoice, booking = build_cases()
        for case in (invoice, booking):
            self.assertEqual(case.contract.forbidden_support_ids, ("R1", "R3"))
            self.assertEqual(case.contract.required_support_ids, ("R2", "R4", "R6"))
            self.assertEqual({row.evidence_id for row in case.task.evidence
                              if row.role == "required_support"}, {"R2", "R4"})
            self.assertNotIn(case.contract.expected_answer, case.task.evidence[-1].text)
        invoice_id = re.search(r"invoice (INV-\d+)", invoice.task.question).group(1)
        register = invoice.task.evidence[1].text
        account = re.search(re.escape(invoice_id) + r" belongs to (AC-\d+)", register).group(1)
        region, contract = re.search(re.escape(account) + r" has region (\w+) and contract (\w+)",
                                     register).groups()
        for index, expected in ((2, invoice.task.prior_state.answer),
                                (3, invoice.contract.expected_answer)):
            fee_table = {(one, two): fee for fee, one, two in re.findall(
                r"(\d+_CREDITS) to \((\w+),(\w+)\)", invoice.task.evidence[index].text
            )}
            self.assertEqual(fee_table[(region, contract)], expected)
        self.assertNotEqual(invoice.task.prior_state.answer, invoice.contract.expected_answer)
        booking_id = re.search(r"booking (BK-\d+)", booking.task.question).group(1)
        register = booking.task.evidence[1].text
        session, group = re.search(re.escape(booking_id) + r" selects session (SS-\d+) and group (G-\d+)",
                                   register).groups()
        size = int(re.search(re.escape(group) + r" has size (\d+)", register).group(1))
        for index in (2, 3):
            capacity = int(re.search(re.escape(session) + r" a capacity of (\d+)",
                                     booking.task.evidence[index].text).group(1))
            self.assertEqual("CONFIRM" if size <= capacity else "WAITLIST", booking.contract.expected_answer)
        self.assertEqual(booking.task.prior_state.answer, booking.contract.expected_answer)

    def test_citing_the_still_active_distractor_fails_lineage_despite_correct_answer_and_coverage(self) -> None:
        case = self.plan["cases"][0]
        text = "ANSWER=" + case["contract"]["expected_answer"] + "\nSUPPORT=R6,R4,R2,R1"
        report = evaluation.run_plan(self.plan, client=successful_client(self.plan, {0: text}))
        cell = report["cells"][0]
        self.assertEqual(cell["status"], "PARSED")
        self.assertTrue(cell["grade"]["checks"]["expected_answer"])
        self.assertTrue(cell["grade"]["checks"]["required_support_present"])
        self.assertFalse(cell["grade"]["checks"]["forbidden_support_absent"])
        self.assertEqual(cell["grade"]["status"], "FAIL")
        self.assertEqual(cell["compiler_coverage"]["status"], "PASS")
        self.assertEqual(report["execution_status"], "PASS")

    def test_numeric_pairs_change_only_the_reinspect_numeric_assignment(self) -> None:
        for case in self.plan["cases"]:
            for placement in ("chronological", "credit_first"):
                with self.subTest(case=case["case_id"], placement=placement):
                    left = case["invocations"]["aligned_" + placement]
                    right = case["invocations"]["permuted_" + placement]
                    differing = [(one, two) for one, two in zip(
                        left["prompt"].splitlines(), right["prompt"].splitlines(), strict=True
                    ) if one != two]
                    self.assertEqual(len(differing), 1)
                    self.assertTrue(all(line.startswith("REINSPECT_JSON ")
                                        for pair in differing for line in pair))
                    aligned, permuted = reinspect(left), reinspect(right)
                    self.assertEqual([row["evidence_id"] for row in aligned],
                                     [row["evidence_id"] for row in permuted])
                    tuples = lambda rows: [(row["allocation_units"], row["signed_control"]) for row in rows]
                    self.assertCountEqual(tuples(aligned), tuples(permuted))
                    self.assertTrue(all(one != two for one, two in zip(
                        tuples(aligned), tuples(permuted), strict=True
                    )))
                    self.assertEqual(prompt_lines(left, "EVIDENCE_JSON "),
                                     prompt_lines(right, "EVIDENCE_JSON "))

    def test_placement_pairs_change_only_evidence_record_order(self) -> None:
        for case in self.plan["cases"]:
            for alignment in ("aligned", "permuted"):
                with self.subTest(case=case["case_id"], alignment=alignment):
                    left = case["invocations"][alignment + "_chronological"]
                    right = case["invocations"][alignment + "_credit_first"]
                    other_lines = lambda invocation: [line for line in invocation["prompt"].splitlines()
                                                      if not line.startswith("EVIDENCE_JSON ")]
                    self.assertEqual(other_lines(left), other_lines(right))
                    records_left = prompt_lines(left, "EVIDENCE_JSON ")
                    records_right = prompt_lines(right, "EVIDENCE_JSON ")
                    self.assertCountEqual(records_left, records_right)
                    self.assertNotEqual(records_left, records_right)
                    self.assertEqual(reinspect(left), reinspect(right))

    def test_every_arm_preserves_coverage_slots_numeric_budget_and_instructions(self) -> None:
        for case, planned in zip(build_cases(), self.plan["cases"], strict=True):
            reference = planned["programs"]["aligned_chronological"]
            expected = CoverageFirstActuator().compile(case.task, planned["trajectory"], lane_id="primary")
            self.assertEqual(reference, expected.to_dict())
            controls = {row["evidence_id"]: row["control"] for row in planned["trajectory"]["credit_map"]}
            source_norm = sum(controls[row["evidence_id"]] ** 2 for row in reference["reinspect"])
            for arm, program in planned["programs"].items():
                with self.subTest(case=planned["case_id"], arm=arm):
                    rows = program["reinspect"]
                    self.assertEqual(len(rows), case.task.reinspection_count)
                    self.assertEqual(len({row["evidence_id"] for row in rows}), len(rows))
                    self.assertTrue(set(case.contract.required_support_ids).issubset(
                        {row["evidence_id"] for row in rows}
                    ))
                    self.assertEqual(sum(row["allocation_units"] for row in rows), 100)
                    self.assertTrue(all(type(row["allocation_units"]) is int
                                        and row["allocation_units"] > 0 for row in rows))
                    self.assertAlmostEqual(sum(row["signed_control"] ** 2 for row in rows), source_norm)
                    self.assertLessEqual(math.sqrt(source_norm), case.task.control_budget + 1e-12)
                    for field in ("steps", "suppress_evidence_ids", "preserve_evidence_ids",
                                  "source_credit_fingerprint_sha256"):
                        self.assertEqual(program[field], reference[field])
                    self.assertEqual(planned["compiler_coverage"][arm]["status"], "PASS")

    def test_plan_build_runs_real_backward_without_api_calls(self) -> None:
        original = torch.Tensor.backward
        backwards = []

        def tracked(tensor, *args, **kwargs):
            backwards.append(tensor)
            return original(tensor, *args, **kwargs)

        with (
            mock.patch.object(torch.Tensor, "backward", tracked),
            mock.patch.object(evaluation, "HostedResponsesRuntime", side_effect=AssertionError("no API")),
        ):
            rebuilt = evaluation.build_plan(self.config)
        self.assertEqual(rebuilt, self.plan)
        self.assertEqual(len(backwards), len(build_cases()))
        for case in rebuilt["cases"]:
            self.assertTrue(case["trajectory"]["checks"]["real_backward_executed_once"])

    def test_gold_changes_never_change_programs_or_actual_prompts(self) -> None:
        changed_cases = tuple(replace(case, contract=replace(
            case.contract,
            expected_answer=next(answer for answer in case.task.answer_choices
                                 if answer != case.contract.expected_answer),
            required_support_ids=(case.task.event.correction_evidence_id,),
        )) for case in build_cases())
        with mock.patch.object(evaluation, "build_cases", return_value=changed_cases):
            alternative = evaluation.build_plan(self.config)
        self.assertNotEqual(alternative["fingerprint_sha256"], self.plan["fingerprint_sha256"])
        for old, new in zip(self.plan["cases"], alternative["cases"], strict=True):
            self.assertNotEqual(old["contract"], new["contract"])
            self.assertEqual(old["programs"], new["programs"])
            self.assertEqual(old["invocations"], new["invocations"])

    def test_plan_is_reproducible_pins_transitive_sources_and_declares_eight_unique_cells(self) -> None:
        self.assertEqual(evaluation.build_plan(self.config), self.plan)
        self.assertEqual(self.plan["call_limit"], 8)
        self.assertEqual(len(self.plan["cases"]), 2)
        self.assertEqual(len(self.plan["schedule"]), 8)
        self.assertEqual(len({(row["case_id"], row["arm_id"]) for row in self.plan["schedule"]}), 8)
        root = Path(evaluation.__file__).resolve().parent
        required_sources = {
            "ebrt_alignment_eval.py", "ebrt_alignment_cases.py", "ebrt_support_eval.py",
            "ebrt_support_cases.py", "ebrt_hosted.py", "ebrt_demo.py", "ebrt_engine.py",
            "ebrt_core.py", "local_output_diff_corpus_v0_8_2.py",
            "role_stratified_uptake_canary_v0_8_3.py",
        }
        self.assertTrue(required_sources.issubset(self.plan["source_sha256"]))
        for name, digest in self.plan["source_sha256"].items():
            self.assertEqual(hashlib.sha256((root / name).read_bytes()).hexdigest(), digest)

    def test_provider_calls_follow_frozen_schedule_with_identical_settings_and_full_evidence(self) -> None:
        client = successful_client(self.plan)
        report = evaluation.run_plan(self.plan, client=client)
        self.assertEqual(report["actual_provider_calls"], 8)
        self.assertEqual(len(client.responses.calls), 8)
        planned = {case["case_id"]: case for case in self.plan["cases"]}
        settings = []
        for entry, call, cell in zip(self.plan["schedule"], client.responses.calls, report["cells"], strict=True):
            case = planned[entry["case_id"]]
            invocation = case["invocations"][entry["arm_id"]]
            self.assertEqual(call["input"], invocation["prompt"])
            self.assertEqual((cell["case_id"], cell["arm_id"]), (entry["case_id"], entry["arm_id"]))
            self.assertEqual(cell["invocation_fingerprint_sha256"], invocation["fingerprint_sha256"])
            evidence = [json.loads(line.removeprefix("EVIDENCE_JSON "))
                        for line in call["input"].splitlines() if line.startswith("EVIDENCE_JSON ")]
            self.assertEqual(len(evidence), len(case["task"]["evidence"]))
            self.assertEqual({row["evidence_id"]: row["text"] for row in evidence},
                             {row["evidence_id"]: row["text"] for row in case["task"]["evidence"]})
            for forbidden in ("expected_answer", "required_support_ids", "post_run_contract",
                              "terminal_target", "control_basis", "gradient"):
                self.assertNotIn(forbidden, call["input"])
            settings.append({key: value for key, value in call.items() if key != "input"})
        self.assertTrue(all(setting == settings[0] for setting in settings))
        self.assertFalse(settings[0]["store"])
        self.assertEqual(settings[0]["reasoning"], {"effort": "low"})
        self.assertEqual(settings[0]["text"], {"verbosity": "low"})
        self.assertEqual(report["status"], "COMPLETE")
        self.assertEqual(report["execution_status"], "PASS")

    def test_perturbation_is_not_admitted_by_standard_engine(self) -> None:
        program = _program_from_receipt(self.plan["cases"][0]["programs"]["permuted_credit_first"])

        class PerturbedActuator:
            def compile(self, task, optimized, *, lane_id):
                return program

        callback = mock.Mock(return_value="never generate")
        adapter = CallableModelAdapter(descriptor=AdapterDescriptor(
            adapter_id="alignment-perturbation-test", model_id="deterministic/test",
            interface_kind="deterministic_conformance", state_visibility="public_only",
            differentiable_through_model=False,
        ), callback=callback)
        with self.assertRaisesRegex(EBRTError, "COVERAGE_PROGRAM_BINDING_MISMATCH"):
            RevisionEngine(actuator_adapter=PerturbedActuator()).run(build_cases()[0].task, adapter)
        callback.assert_not_called()

    def test_valid_semantic_failure_does_not_masquerade_as_execution_failure(self) -> None:
        entry = self.plan["schedule"][0]
        case = next(case for case in self.plan["cases"] if case["case_id"] == entry["case_id"])
        text = "ANSWER=" + case["contract"]["expected_answer"] + "\nSUPPORT=R6"
        report = evaluation.run_plan(self.plan, client=successful_client(self.plan, {0: text}))
        self.assertEqual(report["status"], "COMPLETE")
        self.assertEqual(report["execution_status"], "PASS")
        self.assertEqual(report["cells"][0]["grade"]["status"], "FAIL")
        self.assertEqual(report["cells"][0]["structural"]["status"], "PASS")
        self.assertEqual(report["cells"][0]["provider_uptake"]["status"], "FAIL")
        self.assertEqual(report["summary"][entry["arm_id"]]["strict_pass_count"], 1)
        self.assertEqual(evaluation.verify_report(report, self.plan)["status"], "PASS")

    def test_eight_provider_failures_spend_exactly_eight_attempts_without_retry_or_secret_leak(self) -> None:
        client = FakeClient(*(RuntimeError(SECRET) for _ in range(9)))
        report = evaluation.run_plan(self.plan, client=client)
        self.assertEqual(len(client.responses.calls), 8)
        self.assertEqual(report["actual_provider_calls"], 8)
        self.assertEqual(report["execution_status"], "FAIL")
        self.assertTrue(all(cell["status"] == "PROVIDER_ERROR" for cell in report["cells"]))
        self.assertTrue(all(cell["error_code"] == "HOSTED_PROVIDER_ERROR" for cell in report["cells"]))
        self.assertEqual([row["attempt"] for row in report["provider_receipts"]], list(range(1, 9)))
        self.assertNotIn(SECRET, json.dumps(report))

    def test_format_refusal_and_provider_failures_remain_recorded_without_repair(self) -> None:
        malformed = "PUBLIC INVALID ANSWER\nEXTRA VISIBLE OUTPUT"
        refused = response(output=[{"type": "message", "content": [{"type": "refusal", "refusal": SECRET}]}])
        client = successful_client(self.plan, {0: malformed, 1: refused, 2: RuntimeError(SECRET)})
        report = evaluation.run_plan(self.plan, client=client)
        self.assertEqual(len(client.responses.calls), 8)
        self.assertEqual(report["status"], "COMPLETE")
        self.assertEqual(report["execution_status"], "FAIL")
        self.assertEqual(report["cells"][0]["status"], "FORMAT_ERROR")
        self.assertEqual(report["cells"][0]["raw_text"], malformed)
        self.assertEqual(report["cells"][1]["error_code"], "HOSTED_RESPONSE_REFUSAL")
        self.assertIsNone(report["cells"][1]["raw_text"])
        self.assertNotIn(SECRET, json.dumps(report))

    def test_unparsed_pairs_are_not_reported_as_equal_or_as_semantic_transitions(self) -> None:
        client = successful_client(self.plan, {0: RuntimeError(SECRET), 1: RuntimeError(SECRET)})
        report = evaluation.run_plan(self.plan, client=client)
        failed = {(cell["case_id"], cell["arm_id"]) for cell in report["cells"]
                  if cell["status"] != "PARSED"}
        missing = []
        assessed = []
        for pair in report["comparisons"]:
            one = (pair["case_id"], pair["left_arm"])
            two = (pair["case_id"], pair["right_arm"])
            if one in failed or two in failed:
                missing.append(pair)
                self.assertEqual(pair["status"], "NOT_ASSESSED")
                self.assertIsNone(pair["output_diff"])
                self.assertIsNone(pair["strict_pass_transition"])
            else:
                assessed.append(pair)
                self.assertEqual(pair["status"], "ASSESSED")
                self.assertIsNotNone(pair["output_diff"])
        self.assertTrue(missing)
        self.assertTrue(assessed)
        self.assertEqual(evaluation.verify_report(report, self.plan)["status"], "PASS")

    def test_mixed_returned_models_fail_execution_matching_even_when_every_output_passes(self) -> None:
        case = self.plan["cases"][0]
        text = "ANSWER=" + case["contract"]["expected_answer"] + "\nSUPPORT=R6,R4,R2"
        client = successful_client(self.plan, {0: response(text, model="other-returned-model")})
        report = evaluation.run_plan(self.plan, client=client)
        self.assertEqual(report["execution_status"], "FAIL")
        self.assertTrue(all(cell["grade"]["status"] == "PASS" for cell in report["cells"]))
        self.assertEqual(evaluation.verify_report(report, self.plan)["status"], "PASS")

    def test_unsealed_or_resealed_plan_tampering_is_rejected_before_first_call(self) -> None:
        for field in ("unsealed", "source", "schedule", "prompt", "program", "contract"):
            with self.subTest(field=field):
                changed = clone(self.plan)
                if field in ("unsealed", "schedule"):
                    changed["schedule"].reverse()
                elif field == "source":
                    changed["source_sha256"]["ebrt_core.py"] = "0" * 64
                elif field == "prompt":
                    changed["cases"][0]["invocations"][evaluation.ARMS[0]]["prompt"] += "\nINJECTED"
                elif field == "program":
                    changed["cases"][0]["programs"][evaluation.ARMS[0]]["reinspect"][0]["allocation_units"] += 1
                else:
                    changed["cases"][0]["contract"]["expected_answer"] = "FORGED"
                client = successful_client(self.plan)
                with self.assertRaises(EBRTError):
                    evaluation.run_plan(changed if field == "unsealed" else reseal(changed), client=client)
                self.assertEqual(client.responses.calls, [])

    def test_offline_verifier_recomputes_grades_summaries_diffs_and_cell_order(self) -> None:
        for field in ("grade", "summary", "raw_text", "order", "comparison"):
            with self.subTest(field=field):
                changed = clone(self.report)
                if field == "grade":
                    changed["cells"][0]["grade"] = reseal({
                        **changed["cells"][0]["grade"], "status": "FAIL",
                        "checks": {key: False for key in changed["cells"][0]["grade"]["checks"]},
                    })
                elif field == "summary":
                    changed["summary"][evaluation.ARMS[0]]["strict_pass_count"] = 0
                elif field == "raw_text":
                    changed["cells"][0]["raw_text"] = "ANSWER=FORGED\nSUPPORT=R6"
                elif field == "comparison":
                    changed["comparisons"][0]["status"] = "FORGED"
                else:
                    changed["cells"][0], changed["cells"][1] = changed["cells"][1], changed["cells"][0]
                with self.assertRaises(EBRTError):
                    evaluation.verify_report(reseal(changed), self.plan)

    def test_offline_verifier_rejects_resealed_provider_binding_or_hidden_content_tampering(self) -> None:
        for field in ("request", "identifier", "hidden_content", "http_status", "attempt", "usage"):
            with self.subTest(field=field):
                changed = clone(self.report)
                receipt = changed["provider_receipts"][0]
                if field == "request":
                    receipt["request_fingerprint_sha256"] = "0" * 64
                elif field == "identifier":
                    receipt["provider_request_id"] = "invalid\nidentifier"
                elif field == "http_status":
                    receipt["http_status"] = True
                elif field == "attempt":
                    receipt["attempt"] = True
                elif field == "usage":
                    receipt["usage"]["input_tokens"] = True
                else:
                    receipt["hidden_content"] = SECRET
                with self.assertRaises(EBRTError):
                    evaluation.verify_report(reseal(changed), self.plan)

    def test_offline_verification_requires_no_sdk_and_does_not_claim_provider_authenticity(self) -> None:
        with mock.patch.object(evaluation, "HostedResponsesRuntime", side_effect=AssertionError("no API")):
            checked = evaluation.verify_report(self.report, self.plan)
        self.assertEqual(checked["status"], "PASS")
        self.assertEqual(checked["checked_cells"], 8)
        self.assertEqual(checked["report_fingerprint_sha256"], self.report["fingerprint_sha256"])
        self.assertIn("not provider authenticity", checked["meaning"])

    def test_cli_plan_is_offline_and_writes_private_non_overwriting_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ebrt-alignment-test-") as directory:
            path = Path(directory) / "plan.json"
            with mock.patch.object(evaluation, "HostedResponsesRuntime", side_effect=AssertionError("no API")):
                code, stdout, stderr = self.invoke_cli(["plan", "--model", MODEL, "--output", str(path)])
            self.assertEqual(code, 0, stderr)
            self.assertEqual(json.loads(path.read_text()), self.plan)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertIn("no API calls", stdout)

    def test_output_preflight_rejects_existing_and_checkout_paths_before_execution(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ebrt-alignment-test-") as directory:
            plan_path = Path(directory) / "plan.json"
            plan_path.write_text(json.dumps(self.plan))
            existing = Path(directory) / "existing.json"
            existing.write_text("preserve")
            checkout = Path(evaluation.__file__).resolve().parent / ".alignment-test-must-not-exist.json"
            self.assertFalse(checkout.exists())
            for command in ("plan", "run"):
                for path in (existing, checkout):
                    with self.subTest(command=command, path=path):
                        args = (["plan", "--model", MODEL] if command == "plan"
                                else ["run", "--plan", str(plan_path)])
                        with mock.patch.object(evaluation, "run_plan") as run:
                            code, stdout, stderr = self.invoke_cli([*args, "--output", str(path)])
                        self.assertNotEqual(code, 0)
                        run.assert_not_called()
                        self.assertEqual(existing.read_text(), "preserve")
                        self.assertFalse(checkout.exists())

    def test_cli_run_persists_private_reports_and_separates_execution_exit_status(self) -> None:
        failed = evaluation.run_plan(self.plan, client=FakeClient(*(RuntimeError(SECRET) for _ in range(8))))
        with tempfile.TemporaryDirectory(prefix="ebrt-alignment-test-") as directory:
            plan_path = Path(directory) / "plan.json"
            plan_path.write_text(json.dumps(self.plan))
            for expected_code, report in enumerate((self.report, failed)):
                target = Path(directory) / f"report-{expected_code}.json"
                with mock.patch.object(evaluation, "run_plan", return_value=report):
                    code, stdout, stderr = self.invoke_cli([
                        "run", "--plan", str(plan_path), "--output", str(target)
                    ])
                self.assertEqual(code, expected_code, stderr)
                self.assertEqual(json.loads(target.read_text()), report)
                self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
                self.assertNotIn(SECRET, stdout + stderr)

    def test_cli_verify_is_offline_and_rejects_corrupt_report(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ebrt-alignment-test-") as directory:
            plan_path, report_path = Path(directory) / "plan.json", Path(directory) / "report.json"
            plan_path.write_text(json.dumps(self.plan))
            report_path.write_text(json.dumps(self.report))
            args = ["verify", "--plan", str(plan_path), "--report", str(report_path)]
            with mock.patch.object(evaluation, "HostedResponsesRuntime", side_effect=AssertionError("no API")):
                code, stdout, stderr = self.invoke_cli(args)
                self.assertEqual(code, 0, stderr)
                self.assertEqual(json.loads(stdout)["status"], "PASS")
                changed = clone(self.report)
                changed["summary"][evaluation.ARMS[0]]["strict_pass_count"] = 0
                report_path.write_text(json.dumps(reseal(changed)))
                code, stdout, stderr = self.invoke_cli(args)
            self.assertNotEqual(code, 0)
            self.assertIn("REPORT_MISMATCH", stderr)


if __name__ == "__main__":
    unittest.main()
