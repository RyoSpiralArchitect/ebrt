"""Network-zero checks of the six-attempt shared-prefix dependency canary."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import socket
import stat
import tempfile
import unittest
from unittest import mock

import ebrt_dependency_canary as canary
from ebrt_dependency_cases import build_case
from ebrt_core import EBRTError, _seal
from ebrt_reinspection import ReinspectionConfig
from test_ebrt_dependency_reinspection import audit_reply, final_reply, quote_for, records
from test_ebrt_hosted import FakeClient, MODEL, SECRET, response


def clone(value):
    return json.loads(json.dumps(value))


def reseal(value):
    material = clone(value)
    material.pop("fingerprint_sha256", None)
    return _seal(material)


def unrelated_quote(case):
    source = next(row.text for row in case.task.evidence if row.evidence_id == "R4")
    return next(line for line in source.splitlines()
                if line.strip() and not any(span in line for span in case.quote_contract["R4"]))


def successful_client(plan, case=None, overrides=None):
    case = build_case() if case is None else case
    context = plan["dependency_plan"]
    outcomes = [audit_reply(case, spec["evidence_id"]) for spec in context["audit_specs"]]
    outcomes.extend((final_reply(case), audit_reply(case, "R4", unrelated_quote(case)), final_reply(case)))
    return FakeClient(*(response(value) if isinstance(value, str) else value
                        for index, outcome in enumerate(outcomes)
                        for value in ((overrides or {}).get(index, outcome),)))


class DependencyCanaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        stack = contextlib.ExitStack()
        cls.addClassCleanup(stack.close)
        for owner, name in ((socket, "create_connection"), (socket, "getaddrinfo"),
                            (socket.socket, "connect"), (socket.socket, "connect_ex")):
            stack.enter_context(mock.patch.object(owner, name,
                side_effect=AssertionError("dependency canary tests cannot use the network")))
        cls.case = build_case()
        cls.config = ReinspectionConfig(model=MODEL)
        cls.plan = canary.build_plan(cls.config)
        cls.report = canary.run_plan(cls.plan, client=successful_client(cls.plan, cls.case))

    def invoke_cli(self, arguments):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = canary.main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_six_requests_share_the_two_parent_audits_without_repeating_them(self):
        client = successful_client(self.plan, self.case)
        report = canary.run_plan(self.plan, client=client)
        self.assertEqual(len(client.responses.calls), 6)
        self.assertEqual(report["actual_provider_calls"], 6)
        self.assertEqual(report["shared_audit_provider_calls"], 2)
        self.assertEqual(report["audit_provider_calls"], 4)
        self.assertEqual(report["final_provider_calls"], 2)
        self.assertEqual(report["execution_status"], "PASS")
        primary_ids = [row["evidence_id"] for call in client.responses.calls
                       for row in records(call["input"], "EVIDENCE_JSON ")
                       if "BEGIN_EBRT_DEPENDENCY_AUDIT" in call["input"]]
        self.assertEqual(primary_ids, ["R6", "R2", "R4", "R4"])

    def test_child_pair_differs_only_in_parent_context_and_final_pair_only_target_quote(self):
        client = successful_client(self.plan, self.case)
        report = canary.run_plan(self.plan, client=client)
        contextual, isolated = (client.responses.calls[index] for index in (2, 4))
        without_parents = lambda prompt: [line for line in prompt.splitlines()
                                         if not line.startswith("PARENT_REINSPECTION_JSON ")]
        self.assertEqual(without_parents(contextual["input"]), without_parents(isolated["input"]))
        self.assertEqual([row["evidence_id"] for row in records(
            contextual["input"], "PARENT_REINSPECTION_JSON ")], ["R2"])
        self.assertEqual(records(isolated["input"], "PARENT_REINSPECTION_JSON "), [])
        settings = lambda call: {key: value for key, value in call.items() if key != "input"}
        self.assertEqual(settings(contextual), settings(isolated))
        left, right = (client.responses.calls[index] for index in (3, 5))
        self.assertEqual(settings(left), settings(right))
        changed = [(one, two) for one, two in zip(
            left["input"].splitlines(), right["input"].splitlines(), strict=True) if one != two]
        self.assertEqual(len(changed), 1)
        for pair in changed:
            for line in pair:
                self.assertTrue(line.startswith("PUBLIC_REINSPECTION_JSON "))
                self.assertEqual(json.loads(line.removeprefix("PUBLIC_REINSPECTION_JSON "))["evidence_id"], "R4")
        self.assertTrue(all(report["matched_inputs"].values()))

    def test_source_provenance_and_quote_sufficiency_are_separate_from_final_quality(self):
        self.assertEqual(self.report["context_report"]["quote_sufficiency"]["status"], "PASS")
        self.assertEqual(self.report["isolated_stages"][0]["status"], "VALIDATED")
        self.assertEqual(self.report["isolated_quote_sufficiency"]["status"], "FAIL")
        self.assertEqual(self.report["isolated_post_run_contract"]["status"], "PASS")
        self.assertEqual(self.report["context_report"]["post_run_contract"]["status"], "PASS")
        comparison = self.report["comparison"]
        self.assertEqual(comparison["status"], "ASSESSED")
        self.assertFalse(comparison["output_diff"]["answer_changed"])
        self.assertFalse(comparison["output_diff"]["support_changed"])

    def test_context_semantic_failure_does_not_gate_the_isolated_branch(self):
        client = successful_client(self.plan, self.case,
                                   {3: final_reply(self.case, self.case.task.prior_state.answer)})
        report = canary.run_plan(self.plan, client=client)
        self.assertEqual(len(client.responses.calls), 6)
        self.assertEqual(report["context_report"]["execution_status"], "PASS")
        self.assertEqual(report["context_report"]["post_run_contract"]["status"], "FAIL")
        self.assertEqual(report["execution_status"], "PASS")
        self.assertEqual(report["comparison"]["status"], "ASSESSED")
        self.assertTrue(report["comparison"]["output_diff"]["answer_changed"])

    def test_context_quote_grade_failure_does_not_gate_the_isolated_branch(self):
        client = successful_client(self.plan, self.case,
                                   {2: audit_reply(self.case, "R4", unrelated_quote(self.case))})
        report = canary.run_plan(self.plan, client=client)
        self.assertEqual(len(client.responses.calls), 6)
        self.assertEqual(report["context_report"]["execution_status"], "PASS")
        self.assertEqual(report["context_report"]["quote_sufficiency"]["status"], "FAIL")
        self.assertEqual(report["execution_status"], "PASS")
        self.assertEqual(report["comparison"]["status"], "ASSESSED")

    def test_context_provider_failure_stops_the_whole_gate_without_extra_attempts(self):
        client = successful_client(self.plan, self.case, {1: RuntimeError(SECRET)})
        report = canary.run_plan(self.plan, client=client)
        self.assertEqual(len(client.responses.calls), 2)
        self.assertEqual(report["actual_provider_calls"], 2)
        self.assertEqual(report["isolated_stages"], [])
        self.assertEqual(report["comparison"]["status"], "NOT_ASSESSED")
        self.assertIsNone(report["comparison"]["output_diff"])
        self.assertNotIn(SECRET, json.dumps(report))
        self.assertEqual(canary.verify_report(report, self.plan)["status"], "PASS")

    def test_isolated_failure_skips_its_final_and_is_never_equal_to_context_output(self):
        client = successful_client(self.plan, self.case, {4: RuntimeError(SECRET)})
        report = canary.run_plan(self.plan, client=client)
        self.assertEqual(len(client.responses.calls), 5)
        self.assertEqual(report["actual_provider_calls"], 5)
        self.assertEqual(report["final_provider_calls"], 1)
        self.assertIsNone(report["isolated_final_model_result"])
        self.assertEqual(report["comparison"]["status"], "NOT_ASSESSED")
        self.assertIsNone(report["comparison"]["output_diff"])
        self.assertEqual(canary.verify_report(report, self.plan)["status"], "PASS")

    def test_malformed_isolated_final_spends_sixth_attempt_without_repair_or_pair_grade(self):
        client = successful_client(self.plan, self.case, {5: "MALFORMED PUBLIC OUTPUT"})
        report = canary.run_plan(self.plan, client=client)
        self.assertEqual(len(client.responses.calls), 6)
        self.assertEqual(report["isolated_stages"][-1]["status"], "FORMAT_ERROR")
        self.assertEqual(report["execution_status"], "FAIL")
        self.assertEqual(report["comparison"]["status"], "NOT_ASSESSED")
        self.assertIsNone(report["comparison"]["output_diff"])

    def test_plan_reproducibility_and_tamper_rejection_precede_dispatch(self):
        self.assertEqual(canary.build_plan(self.config), self.plan)
        self.assertEqual(self.plan["max_provider_attempts"], 6)
        self.assertEqual(self.plan["shared_audit_ids"], ["R6", "R2"])
        for field in ("source", "cap", "target"):
            changed = clone(self.plan)
            if field == "source":
                changed["source_sha256"]["ebrt_dependency_canary.py"] = "0" * 64
            elif field == "cap":
                changed["isolated_audit_spec"]["generation_config"]["max_output_tokens"] += 1
            else:
                changed["target_evidence_id"] = "R2"
            client = successful_client(self.plan, self.case)
            with self.subTest(field=field), self.assertRaises(EBRTError):
                canary.run_plan(reseal(changed), client=client)
            self.assertEqual(client.responses.calls, [])

    def test_report_reconstruction_rejects_forged_context_branch_final_grade_and_counts(self):
        for field in ("context", "isolated_prompt", "quote_grade", "count", "comparison", "binding"):
            changed = clone(self.report)
            if field == "context":
                changed["context_report"]["stages"][2]["invocation"]["prompt"] += "\nFORGED"
            elif field == "isolated_prompt":
                changed["isolated_final_invocation"]["prompt"] += "\nFORGED"
            elif field == "quote_grade":
                changed["isolated_quote_sufficiency"] = reseal({
                    **changed["isolated_quote_sufficiency"], "status": "PASS"})
            elif field == "count":
                changed["actual_provider_calls"] = 4
            elif field == "comparison":
                changed["comparison"]["status"] = "NOT_ASSESSED"
            else:
                changed["isolated_stages"][0]["provider_receipt"]["request_fingerprint_sha256"] = "0" * 64
            with self.subTest(field=field), self.assertRaises(EBRTError):
                canary.verify_report(reseal(changed), self.plan)

    def test_success_prefix_cannot_be_truncated_to_hide_a_missing_isolated_final(self):
        changed = clone(self.report)
        changed["isolated_stages"] = changed["isolated_stages"][:1]
        changed["actual_provider_calls"] = 5
        with self.assertRaises(EBRTError):
            canary.verify_report(reseal(changed), self.plan)

    def test_canary_plan_and_offline_verification_use_private_files_without_sdk(self):
        with tempfile.TemporaryDirectory(prefix="ebrt-dependency-canary-test-") as directory:
            path = Path(directory) / "plan.json"
            with mock.patch.object(canary, "run_plan", side_effect=AssertionError("no execution")):
                code, _, stderr = self.invoke_cli(["plan", "--model", MODEL, "--output", str(path)])
            self.assertEqual(code, 0, stderr)
            self.assertEqual(json.loads(path.read_text()), self.plan)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            report_path = Path(directory) / "report.json"
            report_path.write_text(json.dumps(self.report))
            with mock.patch.object(canary, "run_plan", side_effect=AssertionError("no SDK")):
                code, stdout, stderr = self.invoke_cli([
                    "verify", "--plan", str(path), "--report", str(report_path)])
            self.assertEqual(code, 0, stderr)
            self.assertEqual(json.loads(stdout)["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
