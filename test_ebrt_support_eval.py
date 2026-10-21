"""Offline tests of the frozen nine-cell support-retention diagnostic."""

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

import ebrt_support_eval as evaluation
from ebrt_core import (
    AdapterDescriptor, CallableModelAdapter, EBRTError, RevisionEngine, _seal,
)
from ebrt_hosted import HostedConfig
from ebrt_support_cases import build_cases
from local_output_diff_corpus_v0_8_2 import _program_from_receipt, compile_revision
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
        text = "ANSWER=" + case["contract"]["expected_answer"] + "\nSUPPORT=R6,R4,R2"
        outcome = (overrides or {}).get(index, text)
        outcomes.append(response(outcome) if isinstance(outcome, str) else outcome)
    return FakeClient(*outcomes)


class SupportEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        stack = contextlib.ExitStack()
        cls.addClassCleanup(stack.close)
        for owner, name in (
            (socket, "create_connection"), (socket, "getaddrinfo"),
            (socket.socket, "connect"), (socket.socket, "connect_ex"),
        ):
            stack.enter_context(mock.patch.object(
                owner, name, side_effect=AssertionError("support tests cannot use the network")
            ))
        cls.config = HostedConfig(model=MODEL)
        cls.plan = evaluation.build_plan(cls.config)
        cls.report = evaluation.run_plan(cls.plan, client=successful_client(cls.plan))

    def invoke_cli(self, args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = evaluation.main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_cases_require_both_observation_and_rule_and_include_no_change_control(self) -> None:
        cases = build_cases()
        self.assertEqual(len(cases), 3)
        for case in cases:
            self.assertEqual(case.contract.required_support_ids, ("R2", "R4", "R6"))
            self.assertEqual(case.contract.forbidden_support_ids, ("R3",))
            self.assertEqual(case.contract.required_compiled_preserve_ids, ("R5",))
            self.assertEqual({row.evidence_id for row in case.task.evidence
                              if row.role == "required_support"}, {"R2", "R4"})
            self.assertIn("R2", case.task.evidence[-1].text)
            self.assertIn("R4", case.task.evidence[-1].text)
        normalization, routing, duration = cases
        raw = int(re.search(r"is (\d+)", normalization.task.evidence[1].text).group(1))
        factor = int(re.search(r"by (\d+)", normalization.task.evidence[3].text).group(1))
        self.assertEqual(f"{raw * factor}_UNITS", normalization.contract.expected_answer)
        self.assertIn("CLASS_N", routing.task.evidence[1].text)
        self.assertIn("CLASS_N parcels to RIDGE", routing.task.evidence[3].text)
        self.assertEqual(routing.contract.expected_answer, "RIDGE")
        hours = int(re.search(r"is (\d+) hours", duration.task.evidence[1].text).group(1))
        for row in duration.task.evidence[2:4]:
            self.assertLessEqual(hours, int(re.search(r"at most (\d+)", row.text).group(1)))
        self.assertEqual(duration.task.prior_state.answer, duration.contract.expected_answer)
        self.assertTrue(all(case.task.prior_state.answer != case.contract.expected_answer
                            for case in cases[:2]))

    def test_planned_trajectories_and_top_k_come_from_the_real_core(self) -> None:
        for case, planned in zip(build_cases(), self.plan["cases"], strict=True):
            program, receipt = compile_revision(case.task)
            self.assertEqual(planned["trajectory"], receipt["trajectory"])
            self.assertEqual(planned["programs"]["ebrt_top_k"], program.to_dict())
            self.assertTrue(all(planned["trajectory"]["checks"].values()))
            self.assertNotEqual(planned["trajectory"]["neutral"], planned["trajectory"]["revised"])

    def test_engineered_geometries_have_one_of_three_vs_three_of_three_coverage(self) -> None:
        missing = []
        for planned in self.plan["cases"]:
            coverage = planned["compiler_coverage"]
            missing.append(coverage["ebrt_top_k"]["missing_required_public_evidence_ids"])
            self.assertEqual(coverage["role_coverage"]["status"], "PASS")
            controls = {row["evidence_id"]: row["control"]
                        for row in planned["trajectory"]["credit_map"]}
            norm = math.sqrt(sum(value * value for value in controls.values()))
            self.assertLessEqual(norm, planned["task"]["trajectory_contract"]["control_budget"] + 1e-12)
            for program in planned["programs"].values():
                rows = program["reinspect"]
                self.assertEqual(len(rows), 3)
                self.assertEqual(len({row["evidence_id"] for row in rows}), 3)
                self.assertEqual(sum(row["allocation_units"] for row in rows), 100)
                self.assertTrue(all(row["allocation_units"] > 0 for row in rows))
                self.assertEqual(program["suppress_evidence_ids"], ["R3"])
                self.assertEqual(program["preserve_evidence_ids"], ["R5"])
                self.assertTrue(all(row["signed_control"] == controls[row["evidence_id"]]
                                    for row in rows))
                self.assertEqual(program["source_credit_fingerprint_sha256"],
                                 planned["trajectory"]["fingerprint_sha256"])
        self.assertEqual(missing, [["R2"], ["R4"], []])

    def test_no_answer_change_control_has_byte_identical_controlled_prompts(self) -> None:
        case = self.plan["cases"][2]
        self.assertTrue(case["control_prompt_equal"])
        self.assertEqual(case["task"]["prior_state"]["answer"], case["contract"]["expected_answer"])
        self.assertEqual(case["invocations"]["ebrt_top_k"]["prompt"].encode(),
                         case["invocations"]["role_coverage"]["prompt"].encode())
        self.assertFalse(any(row["control_prompt_equal"] for row in self.plan["cases"][:2]))

    def test_gold_contract_changes_cannot_influence_programs_or_provider_prompts(self) -> None:
        altered = tuple(replace(
            case, contract=replace(
                case.contract,
                expected_answer=next(answer for answer in case.task.answer_choices
                                     if answer != case.contract.expected_answer),
                required_support_ids=("R6",),
            )
        ) for case in build_cases())
        with mock.patch.object(evaluation, "build_cases", return_value=altered):
            alternative = evaluation.build_plan(self.config)
        self.assertNotEqual(alternative["fingerprint_sha256"], self.plan["fingerprint_sha256"])
        for original, changed in zip(self.plan["cases"], alternative["cases"], strict=True):
            self.assertNotEqual(original["contract"], changed["contract"])
            self.assertEqual(original["programs"], changed["programs"])
            self.assertEqual(original["invocations"], changed["invocations"])

    def test_plan_build_is_offline_reproducible_and_pins_execution_sources(self) -> None:
        with mock.patch.object(evaluation, "HostedResponsesRuntime", side_effect=AssertionError("no API")):
            self.assertEqual(evaluation.build_plan(self.config), self.plan)
        self.assertEqual(self.plan["call_limit"], 9)
        self.assertEqual(len(self.plan["schedule"]), 9)
        self.assertEqual(len({(row["case_id"], row["arm_id"]) for row in self.plan["schedule"]}), 9)
        root = Path(evaluation.__file__).resolve().parent
        for name, digest in self.plan["source_sha256"].items():
            self.assertEqual(hashlib.sha256((root / name).read_bytes()).hexdigest(), digest)

    def test_all_nine_requests_follow_the_frozen_schedule_and_share_configuration_and_evidence(self) -> None:
        client = successful_client(self.plan)
        report = evaluation.run_plan(self.plan, client=client)
        self.assertEqual(report["actual_provider_calls"], 9)
        self.assertEqual(len(client.responses.calls), 9)
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
            self.assertEqual(len(evidence), 6)
            self.assertEqual({row["evidence_id"]: row["text"] for row in evidence},
                             {row["evidence_id"]: row["text"] for row in case["task"]["evidence"]})
            for gold_field in ("expected_answer", "required_support_ids", "post_run_contract",
                               "terminal_target", "control_basis", "gradient"):
                self.assertNotIn(gold_field, call["input"])
            settings.append({key: value for key, value in call.items() if key != "input"})
        self.assertTrue(all(setting == settings[0] for setting in settings))
        self.assertEqual(settings[0]["model"], MODEL)
        self.assertEqual(settings[0]["reasoning"], {"effort": "low"})
        self.assertEqual(settings[0]["text"], {"verbosity": "low"})
        self.assertFalse(settings[0]["store"])
        self.assertEqual(settings[0]["truncation"], "disabled")
        self.assertEqual(report["status"], "COMPLETE")
        self.assertEqual(report["execution_status"], "PASS")

    def test_mixed_semantic_grades_are_separate_from_complete_successful_execution(self) -> None:
        index = next(index for index, row in enumerate(self.plan["schedule"])
                     if row["arm_id"] == "role_coverage")
        case = next(case for case in self.plan["cases"]
                    if case["case_id"] == self.plan["schedule"][index]["case_id"])
        text = "ANSWER=" + case["contract"]["expected_answer"] + "\nSUPPORT=R6"
        report = evaluation.run_plan(self.plan, client=successful_client(self.plan, {index: text}))
        self.assertEqual(report["status"], "COMPLETE")
        self.assertEqual(report["execution_status"], "PASS")
        self.assertEqual(report["cells"][index]["grade"]["status"], "FAIL")
        self.assertEqual(report["cells"][index]["structural"]["status"], "PASS")
        self.assertEqual(report["cells"][index]["provider_uptake"]["status"], "FAIL")
        self.assertEqual(report["summary"]["role_coverage"]["answer_correct_count"], 3)
        self.assertEqual(report["summary"]["role_coverage"]["strict_pass_count"], 2)
        self.assertEqual(report["summary"]["role_coverage"]["compiler_coverage_count"], 3)
        self.assertEqual(report["summary"]["ebrt_top_k"]["compiler_coverage_count"], 1)
        self.assertEqual(report["summary"]["ebrt_top_k"]["strict_pass_count"], 3)
        self.assertEqual(report["effect_attribution_status"], "NOT_ASSESSED")
        self.assertEqual(report["role_extraction_status"], "NOT_ASSESSED")
        self.assertEqual(evaluation.verify_report(report, self.plan)["status"], "PASS")

    def test_candidate_is_auxiliary_and_cannot_pass_the_frozen_core_actuator_edge(self) -> None:
        for cell in self.report["cells"]:
            expected = {"direct_full_context": "NOT_APPLICABLE", "ebrt_top_k": "CORE_ADMITTED_COMPILER",
                        "role_coverage": "AUXILIARY_PUBLIC_ROLE_CANDIDATE"}[cell["arm_id"]]
            self.assertEqual(cell["actuator_admission"], expected)
        program = _program_from_receipt(self.plan["cases"][0]["programs"]["role_coverage"])

        class CandidateAdapter:
            def compile(self, task, optimized, *, lane_id):
                return program

        callback = mock.Mock(return_value="never generate")
        adapter = CallableModelAdapter(
            descriptor=AdapterDescriptor(
                adapter_id="auxiliary-candidate-test", model_id="deterministic/test",
                interface_kind="deterministic_conformance", state_visibility="public_only",
                differentiable_through_model=False,
            ), callback=callback,
        )
        with self.assertRaisesRegex(EBRTError, "ACTUATOR"):
            RevisionEngine(actuator_adapter=CandidateAdapter()).run(build_cases()[0].task, adapter)
        callback.assert_not_called()

    def test_nine_failed_attempts_are_spent_once_without_retries_or_secret_leaks(self) -> None:
        client = FakeClient(*(RuntimeError(SECRET) for _ in range(10)))
        report = evaluation.run_plan(self.plan, client=client)
        self.assertEqual(len(client.responses.calls), 9)
        self.assertEqual(report["actual_provider_calls"], 9)
        self.assertEqual(report["status"], "COMPLETE")
        self.assertEqual(report["execution_status"], "FAIL")
        self.assertTrue(all(cell["status"] == "PROVIDER_ERROR" for cell in report["cells"]))
        self.assertTrue(all(cell["error_code"] == "HOSTED_PROVIDER_ERROR" for cell in report["cells"]))
        self.assertEqual([row["attempt"] for row in report["provider_receipts"]], list(range(1, 10)))
        self.assertNotIn(SECRET, json.dumps(report))

    def test_malformed_visible_text_is_retained_but_refusal_is_sanitized_without_repairs(self) -> None:
        malformed = "PUBLIC INVALID ANSWER\nEXTRA VISIBLE OUTPUT"
        refused = response(output=[{"type": "message", "content": [{"type": "refusal", "refusal": SECRET}]}])
        client = successful_client(self.plan, {0: malformed, 1: refused, 2: RuntimeError(SECRET)})
        report = evaluation.run_plan(self.plan, client=client)
        self.assertEqual(len(client.responses.calls), 9)
        self.assertEqual(report["status"], "COMPLETE")
        self.assertEqual(report["execution_status"], "FAIL")
        self.assertEqual(report["cells"][0]["status"], "FORMAT_ERROR")
        self.assertEqual(report["cells"][0]["raw_text"], malformed)
        self.assertNotIn("PUBLIC INVALID", report["cells"][0]["error_code"])
        self.assertEqual(report["cells"][1]["error_code"], "HOSTED_RESPONSE_REFUSAL")
        self.assertIsNone(report["cells"][1]["raw_text"])
        self.assertNotIn(SECRET, json.dumps(report))

    def test_unsealed_plan_tamper_is_rejected_before_any_provider_call(self) -> None:
        changed = clone(self.plan)
        changed["schedule"].reverse()
        client = successful_client(self.plan)
        with self.assertRaises(EBRTError):
            evaluation.run_plan(changed, client=client)
        self.assertEqual(client.responses.calls, [])

    def test_resealed_source_hash_tamper_is_rejected_before_any_provider_call(self) -> None:
        changed = clone(self.plan)
        changed["source_sha256"]["ebrt_core.py"] = "0" * 64
        client = successful_client(self.plan)
        with self.assertRaisesRegex(EBRTError, "SUPPORT_PLAN_MISMATCH"):
            evaluation.run_plan(reseal(changed), client=client)
        self.assertEqual(client.responses.calls, [])

    def test_resealed_schedule_or_prompt_tamper_cannot_change_the_predeclared_plan(self) -> None:
        for field in ("schedule", "prompt"):
            with self.subTest(field=field):
                changed = clone(self.plan)
                if field == "schedule":
                    changed["schedule"][0], changed["schedule"][1] = changed["schedule"][1], changed["schedule"][0]
                else:
                    changed["cases"][0]["invocations"]["direct_full_context"]["prompt"] += "\nINJECTED"
                client = successful_client(self.plan)
                with self.assertRaisesRegex(EBRTError, "SUPPORT_PLAN_MISMATCH"):
                    evaluation.run_plan(reseal(changed), client=client)
                self.assertEqual(client.responses.calls, [])

    def test_clean_report_can_be_verified_offline_without_creating_an_sdk_client(self) -> None:
        with mock.patch.object(evaluation, "HostedResponsesRuntime", side_effect=AssertionError("no API")):
            checked = evaluation.verify_report(self.report, self.plan)
        self.assertEqual(checked["status"], "PASS")
        self.assertEqual(checked["checked_cells"], 9)
        self.assertEqual(checked["report_fingerprint_sha256"], self.report["fingerprint_sha256"])
        self.assertIn("not provider authenticity", checked["meaning"])
        self.assertNotIn(SECRET, json.dumps(self.report))

    def test_offline_verification_rejects_resealed_grade_tamper(self) -> None:
        changed = clone(self.report)
        changed["cells"][0]["grade"] = reseal({
            **changed["cells"][0]["grade"], "status": "FAIL",
            "checks": {key: False for key in changed["cells"][0]["grade"]["checks"]},
        })
        with self.assertRaisesRegex(EBRTError, "SUPPORT_REPORT_MISMATCH"):
            evaluation.verify_report(reseal(changed), self.plan)

    def test_offline_verification_rejects_resealed_summary_tamper(self) -> None:
        changed = clone(self.report)
        changed["summary"]["ebrt_top_k"]["strict_pass_count"] = 0
        with self.assertRaisesRegex(EBRTError, "SUPPORT_REPORT_MISMATCH"):
            evaluation.verify_report(reseal(changed), self.plan)

    def test_offline_verification_reparses_visible_response_and_rejects_inconsistent_scores(self) -> None:
        changed = clone(self.report)
        changed["cells"][0]["raw_text"] = "ANSWER=70_UNITS\nSUPPORT=R6"
        with self.assertRaisesRegex(EBRTError, "SUPPORT_REPORT_MISMATCH"):
            evaluation.verify_report(reseal(changed), self.plan)

    def test_offline_verification_rejects_resealed_cell_order_or_receipt_binding_tamper(self) -> None:
        for field in ("order", "receipt", "hidden_content", "identifier", "http_status"):
            with self.subTest(field=field):
                changed = clone(self.report)
                if field == "order":
                    changed["cells"][0], changed["cells"][1] = changed["cells"][1], changed["cells"][0]
                elif field == "receipt":
                    changed["provider_receipts"][0]["request_fingerprint_sha256"] = "0" * 64
                elif field == "hidden_content":
                    changed["provider_receipts"][0]["hidden_content"] = SECRET
                elif field == "identifier":
                    changed["provider_receipts"][0]["provider_request_id"] = "invalid\nidentifier"
                else:
                    changed["provider_receipts"][0]["http_status"] = True
                with self.assertRaises(EBRTError):
                    evaluation.verify_report(reseal(changed), self.plan)

    def test_cli_plan_creates_a_private_json_file_without_any_api_client(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ebrt-support-test-") as directory:
            path = Path(directory) / "plan.json"
            with mock.patch.object(evaluation, "HostedResponsesRuntime", side_effect=AssertionError("no API")):
                code, stdout, stderr = self.invoke_cli(["plan", "--model", MODEL, "--output", str(path)])
            self.assertEqual(code, 0, stderr)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), self.plan)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertIn("no API calls", stdout)

    def test_cli_output_preflight_prevents_overwrite_or_checkout_files_before_execution(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ebrt-support-test-") as directory:
            plan_path = Path(directory) / "plan.json"
            plan_path.write_text(json.dumps(self.plan), encoding="utf-8")
            existing = Path(directory) / "existing.json"
            existing.write_text("preserve", encoding="utf-8")
            checkout_path = Path(evaluation.__file__).resolve().parent / ".support-test-must-not-exist.json"
            self.assertFalse(checkout_path.exists())
            for command in ("plan", "run"):
                for target in (existing, checkout_path):
                    with self.subTest(command=command, target=target):
                        args = (["plan", "--model", MODEL] if command == "plan"
                                else ["run", "--plan", str(plan_path)])
                        with mock.patch.object(evaluation, "run_plan") as run:
                            code, stdout, stderr = self.invoke_cli([*args, "--output", str(target)])
                        self.assertNotEqual(code, 0)
                        run.assert_not_called()
                        self.assertEqual(existing.read_text(encoding="utf-8"), "preserve")
                        self.assertFalse(checkout_path.exists())

    def test_cli_run_writes_private_json_and_reports_execution_failure_independently(self) -> None:
        failed = evaluation.run_plan(self.plan, client=FakeClient(*(RuntimeError(SECRET) for _ in range(9))))
        with tempfile.TemporaryDirectory(prefix="ebrt-support-test-") as directory:
            plan_path = Path(directory) / "plan.json"
            plan_path.write_text(json.dumps(self.plan), encoding="utf-8")
            for index, report in enumerate((self.report, failed)):
                target = Path(directory) / f"report-{index}.json"
                with mock.patch.object(evaluation, "run_plan", return_value=report) as run:
                    code, stdout, stderr = self.invoke_cli(["run", "--plan", str(plan_path), "--output", str(target)])
                run.assert_called_once()
                self.assertEqual(code, index, stderr)
                self.assertEqual(json.loads(target.read_text(encoding="utf-8")), report)
                self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
                self.assertNotIn(SECRET, stdout + stderr)

    def test_cli_verify_uses_no_api_and_rejects_resealed_corrupt_report(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ebrt-support-test-") as directory:
            plan_path, report_path = Path(directory) / "plan.json", Path(directory) / "report.json"
            plan_path.write_text(json.dumps(self.plan), encoding="utf-8")
            report_path.write_text(json.dumps(self.report), encoding="utf-8")
            args = ["verify", "--plan", str(plan_path), "--report", str(report_path)]
            with mock.patch.object(evaluation, "HostedResponsesRuntime", side_effect=AssertionError("no API")):
                code, stdout, stderr = self.invoke_cli(args)
                self.assertEqual(code, 0, stderr)
                self.assertEqual(json.loads(stdout)["status"], "PASS")
                changed = clone(self.report)
                changed["summary"]["role_coverage"]["strict_pass_count"] = 0
                report_path.write_text(json.dumps(reseal(changed)), encoding="utf-8")
                code, stdout, stderr = self.invoke_cli(args)
            self.assertEqual(code, 1)
            self.assertIn("SUPPORT_REPORT_MISMATCH", stderr)


if __name__ == "__main__":
    unittest.main()
