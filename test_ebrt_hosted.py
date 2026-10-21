"""Hosted comparison checks using fake SDK responses and no network access."""

from __future__ import annotations

import contextlib
from dataclasses import FrozenInstanceError
import io
import json
from pathlib import Path
import socket
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import ebrt_hosted as hosted
from ebrt_core import EBRTError, build_demo_task
from ebrt_engine import RevisionEngine
from local_output_diff_corpus_v0_8_2 import build_direct_invocation


MODEL = "gpt-test-fixture"
REPLY = "ANSWER=PROVE\nSUPPORT=R6,R4,R2"
WRONG_REPLY = "ANSWER=POLISH\nSUPPORT=R6,R4,R2"
SECRET = "SECRET_TEST_VALUE_MUST_NEVER_APPEAR"


def response(text: str = REPLY, **overrides):
    values = {
        "id": "resp-local-test",
        "model": "gpt-test-fixture-returned",
        "_request_id": "req-local-test",
        "status": "completed",
        "service_tier": "default",
        "error": None,
        "incomplete_details": None,
        "output_text": text,
        "output": [
            SimpleNamespace(type="reasoning", summary=[SECRET], encrypted_content=SECRET),
            SimpleNamespace(
                type="message", role="assistant", status="completed",
                content=[SimpleNamespace(type="output_text", text=text, annotations=[])],
            ),
        ],
        "usage": SimpleNamespace(
            input_tokens=40, output_tokens=12, total_tokens=52,
            input_tokens_details=SimpleNamespace(cached_tokens=5),
            output_tokens_details=SimpleNamespace(reasoning_tokens=3),
        ),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class FakeResponses:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self.outcomes:
            raise AssertionError("unexpected extra provider call")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeClient:
    def __init__(self, *outcomes, max_retries=0):
        self.max_retries = max_retries
        self.responses = FakeResponses(outcomes or (response(), response()))


class HostedComparisonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = hosted.HostedConfig(model=MODEL)
        self.invocation = build_direct_invocation(build_demo_task())
        for owner, name in (
            (socket, "create_connection"), (socket, "getaddrinfo"),
            (socket.socket, "connect"), (socket.socket, "connect_ex"),
        ):
            patcher = mock.patch.object(owner, name, side_effect=AssertionError("network disabled"))
            patcher.start()
            self.addCleanup(patcher.stop)

    def invoke_cli(self, args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = hosted.main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_config_is_frozen_and_rejects_invalid_generation_settings(self) -> None:
        self.assertEqual(self.config.reasoning_effort, "low")
        self.assertEqual(self.config.max_output_tokens, 1024)
        self.assertEqual(self.config.timeout_seconds, 60)
        with self.assertRaises(FrozenInstanceError):
            self.config.model = "other-model"
        for kwargs in (
            {"model": ""}, {"model": MODEL, "max_output_tokens": 0},
            {"model": MODEL, "timeout_seconds": 0},
            {"model": MODEL, "reasoning_effort": "invalid"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises((EBRTError, ValueError)):
                hosted.HostedConfig(**kwargs)

    def test_default_sdk_client_disables_retries_and_sets_timeout(self) -> None:
        factory = mock.Mock(return_value=FakeClient())
        with (
            mock.patch.dict(sys.modules, {"openai": SimpleNamespace(OpenAI=factory)}),
            mock.patch.dict("os.environ", {"OPENAI_API_KEY": SECRET}),
        ):
            hosted.HostedResponsesRuntime(self.config)
        factory.assert_called_once()
        self.assertEqual(factory.call_args.kwargs["max_retries"], 0)
        self.assertEqual(factory.call_args.kwargs["timeout"], self.config.timeout_seconds)

    def test_injected_sdk_client_cannot_enable_hidden_retries(self) -> None:
        client = FakeClient(max_retries=1)
        with self.assertRaisesRegex(EBRTError, "HOSTED_RETRIES_MUST_BE_ZERO"):
            hosted.HostedResponsesRuntime(self.config, client=client)
        self.assertEqual(client.responses.calls, [])

    def test_two_arms_use_identical_generation_settings_and_real_core(self) -> None:
        client = FakeClient()
        receipts = []
        original_run = RevisionEngine.run

        def capture(engine, *args, **kwargs):
            receipt = original_run(engine, *args, **kwargs)
            receipts.append(receipt)
            return receipt

        with mock.patch.object(RevisionEngine, "run", capture):
            report = hosted.run_comparison(self.config, client=client)
        self.assertEqual(len(client.responses.calls), 2)
        self.assertEqual(report["actual_provider_calls"], 2)
        self.assertEqual(len(receipts), 1)
        self.assertEqual(report["trajectory"], receipts[0]["trajectory"])
        self.assertEqual(report["actuator"], receipts[0]["actuator"])
        self.assertTrue(all(report["trajectory"]["checks"].values()))
        settings = []
        for call in client.responses.calls:
            self.assertEqual(call["model"], MODEL)
            self.assertEqual(call["reasoning"], {"effort": "low"})
            self.assertEqual(call["text"], {"verbosity": "low"})
            self.assertEqual(call["max_output_tokens"], 1024)
            self.assertFalse(call["store"])
            self.assertEqual(call["truncation"], "disabled")
            self.assertEqual(call["service_tier"], "default")
            settings.append({key: value for key, value in call.items() if key != "input"})
        self.assertEqual(settings[0], settings[1])
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["evidence_label"], "INTEGRATION_CHECK_KNOWN_FIXTURE")
        self.assertEqual(report["effect_attribution_status"], "NOT_ASSESSED")

    def test_hosted_mainline_covers_required_support_that_legacy_top_k_omits(self) -> None:
        from ebrt_support_cases import build_cases

        for case in build_cases()[:2]:
            with self.subTest(case=case.task.task_id):
                text = f"ANSWER={case.contract.expected_answer}\nSUPPORT=R6,R4,R2"
                client = FakeClient(response(text), response(text))
                with (
                    mock.patch.object(hosted, "build_demo_task", return_value=case.task),
                    mock.patch.object(hosted, "build_demo_contract", return_value=case.contract),
                ):
                    report = hosted.run_comparison(self.config, client=client)
                self.assertEqual(report["status"], "PASS")
                program = report["arms"]["ebrt_credit_first"]["invocation"]["actuator_program"]
                self.assertEqual({row["evidence_id"] for row in program["reinspect"]}, {"R2", "R4", "R6"})
                self.assertNotIn("R1", [row["evidence_id"] for row in program["reinspect"]])
                self.assertIn("REINSPECT_JSON ", client.responses.calls[1]["input"])
                self.assertEqual(report["ebrt_receipt"]["engine_protocol"], "ebrt-coverage-first-engine-v1")
                self.assertEqual(report["ebrt_receipt"]["actuator_policy"], "coverage_first_v1")

    def test_actual_provider_prompts_share_all_evidence_without_gold_labels(self) -> None:
        client = FakeClient()
        report = hosted.run_comparison(self.config, client=client)
        task = build_demo_task()
        expected = {row.evidence_id: row.text for row in task.evidence}
        task_headers = []
        for call in client.responses.calls:
            prompt = call["input"]
            self.assertIsInstance(prompt, str)
            lines = prompt.splitlines()
            evidence = [json.loads(line.removeprefix("EVIDENCE_JSON "))
                        for line in lines if line.startswith("EVIDENCE_JSON ")]
            self.assertEqual(len(evidence), len(task.evidence))
            self.assertEqual({row["evidence_id"]: row["text"] for row in evidence}, expected)
            task_headers.append([json.loads(line.removeprefix("TASK_JSON "))
                                 for line in lines if line.startswith("TASK_JSON ")])
            for gold_key in ("expected_answer", "required_support_ids", "forbidden_support_ids",
                             "post_run_contract", "terminal_target", "control_basis", "gradient"):
                self.assertNotIn(gold_key, prompt)
        self.assertEqual(len(task_headers[0]), 1)
        self.assertEqual(task_headers[0], task_headers[1])
        direct = report["arms"]["direct_full_context"]["invocation"]
        self.assertEqual(direct, self.invocation)
        self.assertNotIn("actuator_program", direct)
        self.assertIn("REINSPECT_JSON ", client.responses.calls[1]["input"])
        self.assertNotIn("REINSPECT_JSON ", client.responses.calls[0]["input"])

    def test_provider_receipts_keep_usage_and_identifiers_but_no_hidden_content(self) -> None:
        client = FakeClient()
        report = hosted.run_comparison(self.config, client=client)
        self.assertEqual(report["privacy"], "LOCAL_ONLY_REVIEW_BEFORE_EXPORT")
        self.assertEqual(len(report["provider_receipts"]), 2)
        allowed_keys = {
            "attempt", "request_fingerprint_sha256", "generation_config_fingerprint_sha256",
            "requested_model", "returned_model",
            "response_id", "provider_request_id", "usage", "latency_ms", "status",
            "error_code", "http_status",
        }
        for index, receipt in enumerate(report["provider_receipts"], start=1):
            self.assertLessEqual(set(receipt), allowed_keys)
            self.assertEqual(receipt["attempt"], index)
            self.assertEqual(receipt["requested_model"], MODEL)
            self.assertEqual(receipt["returned_model"], "gpt-test-fixture-returned")
            self.assertEqual(receipt["response_id"], "resp-local-test")
            self.assertEqual(receipt["provider_request_id"], "req-local-test")
            self.assertEqual(receipt["usage"], {
                "input_tokens": 40, "output_tokens": 12, "total_tokens": 52, "reasoning_tokens": 3,
            })
            self.assertEqual(len(receipt["request_fingerprint_sha256"]), 64)
            self.assertEqual(len(receipt["generation_config_fingerprint_sha256"]), 64)
        encoded = json.dumps(report, allow_nan=False)
        self.assertNotIn(SECRET, encoded)
        self.assertNotIn("encrypted_content", encoded)
        self.assertNotIn("OPENAI_API_KEY", encoded)

    def test_semantic_failure_does_not_turn_into_mechanism_failure(self) -> None:
        for outcomes in ((response(WRONG_REPLY), response()), (response(), response(WRONG_REPLY))):
            with self.subTest(wrong_arm=outcomes[0].output_text == WRONG_REPLY):
                client = FakeClient(*outcomes)
                report = hosted.run_comparison(self.config, client=client)
                self.assertEqual(report["status"], "FAIL")
                self.assertTrue(all(report["trajectory"]["checks"].values()))
                self.assertEqual(report["ebrt_receipt"]["structural_verification"]["status"], "PASS")
                self.assertIn("FAIL", [arm["grade"]["status"] for arm in report["arms"].values()])
                self.assertEqual(report["effect_attribution_status"], "NOT_ASSESSED")

    def test_hard_call_budget_blocks_third_call(self) -> None:
        client = FakeClient(response(), response(), response())
        runtime = hosted.HostedResponsesRuntime(self.config, client=client)
        self.assertEqual(runtime.max_attempts, 2)
        self.assertEqual(runtime.generate(self.invocation), REPLY)
        self.assertEqual(runtime.generate(self.invocation), REPLY)
        with self.assertRaisesRegex(EBRTError, "HOSTED_CALL_BUDGET_EXHAUSTED"):
            runtime.generate(self.invocation)
        self.assertEqual(runtime.attempts, 2)
        self.assertEqual(len(client.responses.calls), 2)

    def test_explicit_nine_attempt_limit_blocks_the_tenth_call(self) -> None:
        client = FakeClient(*(response() for _ in range(10)))
        runtime = hosted.HostedResponsesRuntime(self.config, client=client, max_attempts=9)
        for _ in range(9):
            self.assertEqual(runtime.generate(self.invocation), REPLY)
        with self.assertRaisesRegex(EBRTError, "HOSTED_CALL_BUDGET_EXHAUSTED"):
            runtime.generate(self.invocation)
        self.assertEqual(runtime.attempts, 9)
        self.assertEqual(len(client.responses.calls), 9)

    def test_invalid_explicit_attempt_limits_fail_before_provider_calls(self) -> None:
        for limit in (0, 10, True, False):
            with self.subTest(limit=limit):
                client = FakeClient()
                with self.assertRaisesRegex(EBRTError, "HOSTED_CALL_LIMIT_INVALID"):
                    hosted.HostedResponsesRuntime(self.config, client=client, max_attempts=limit)
                self.assertEqual(client.responses.calls, [])

    def test_failed_calls_spend_budget_and_are_never_automatically_retried(self) -> None:
        client = FakeClient(RuntimeError(SECRET), RuntimeError(SECRET), response())
        runtime = hosted.HostedResponsesRuntime(self.config, client=client)
        for expected_attempts in (1, 2):
            with self.assertRaises(EBRTError) as caught:
                runtime.generate(self.invocation)
            self.assertEqual(str(caught.exception), "HOSTED_PROVIDER_ERROR")
            self.assertNotIn(SECRET, str(caught.exception))
            self.assertEqual(runtime.attempts, expected_attempts)
            self.assertEqual(len(client.responses.calls), expected_attempts)
        with self.assertRaisesRegex(EBRTError, "HOSTED_CALL_BUDGET_EXHAUSTED"):
            runtime.generate(self.invocation)
        self.assertEqual(len(client.responses.calls), 2)
        self.assertNotIn(SECRET, json.dumps(runtime.receipts))

    def test_response_boundary_rejects_incomplete_refusal_error_and_empty_text(self) -> None:
        refused = [SimpleNamespace(type="message", content=[SimpleNamespace(type="refusal", refusal=SECRET)])]
        cases = (
            (response(status="incomplete", incomplete_details=SimpleNamespace(reason=SECRET)), "INCOMPLETE"),
            (response(incomplete_details=SimpleNamespace(reason=SECRET)), "INCOMPLETE"),
            (response(output=refused), "REFUSAL"),
            (response(error=SimpleNamespace(message=SECRET)), "ERROR"),
            (response(""), "TEXT_MISSING"),
            (response("   \n"), "TEXT_MISSING"),
            (response(model=None), "MODEL_MISSING"),
        )
        for provider_response, reason in cases:
            with self.subTest(reason=reason):
                client = FakeClient(provider_response)
                runtime = hosted.HostedResponsesRuntime(self.config, client=client)
                with self.assertRaisesRegex(EBRTError, "HOSTED_RESPONSE_" + reason) as caught:
                    runtime.generate(self.invocation)
                self.assertNotIn(SECRET, str(caught.exception))
                self.assertEqual(runtime.attempts, 1)
                self.assertEqual(len(client.responses.calls), 1)
                self.assertNotIn(SECRET, json.dumps(runtime.receipts))

    def test_provider_exception_messages_do_not_escape_into_report(self) -> None:
        client = FakeClient(RuntimeError(SECRET), RuntimeError(SECRET))
        report = hosted.run_comparison(self.config, client=client)
        self.assertEqual(report["status"], "FAIL")
        self.assertLessEqual(len(client.responses.calls), 2)
        self.assertNotIn(SECRET, json.dumps(report))
        self.assertTrue(all(arm["error_code"] == "HOSTED_PROVIDER_ERROR"
                            for arm in report["arms"].values()))

    def test_malformed_model_text_fails_without_repair_or_extra_calls(self) -> None:
        for bad_arm in (0, 1):
            with self.subTest(bad_arm=bad_arm):
                outcomes = [response(), response()]
                bad_text = REPLY + "\nEXTRA_VISIBLE_PROVIDER_OUTPUT"
                outcomes[bad_arm] = response(bad_text)
                client = FakeClient(*outcomes)
                report = hosted.run_comparison(self.config, client=client)
                self.assertEqual(report["status"], "FAIL")
                self.assertEqual(len(client.responses.calls), 2)
                arm_id = ("direct_full_context", "ebrt_credit_first")[bad_arm]
                self.assertTrue(report["arms"][arm_id]["error_code"])
                self.assertEqual(report["arms"][arm_id]["raw_text"], bad_text)
                self.assertNotIn("EXTRA_VISIBLE_PROVIDER_OUTPUT", report["arms"][arm_id]["error_code"])

    def test_cli_refuses_existing_output_before_calling_provider(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ebrt-hosted-test-") as directory:
            path = Path(directory) / "existing.json"
            path.write_text("preserve this file", encoding="utf-8")
            with mock.patch.object(hosted, "run_comparison") as run:
                code, stdout, stderr = self.invoke_cli(["--model", MODEL, "--output", str(path)])
            self.assertNotEqual(code, 0)
            run.assert_not_called()
            self.assertEqual(path.read_text(encoding="utf-8"), "preserve this file")

    def test_cli_refuses_checkout_output_before_calling_provider(self) -> None:
        path = Path(hosted.__file__).resolve().parent / ".hosted-test-output-must-not-exist.json"
        self.assertFalse(path.exists())
        with mock.patch.object(hosted, "run_comparison") as run:
            code, stdout, stderr = self.invoke_cli(["--model", MODEL, "--output", str(path)])
        self.assertNotEqual(code, 0)
        run.assert_not_called()
        self.assertFalse(path.exists())

    def test_cli_writes_full_local_json_with_private_permissions(self) -> None:
        report = hosted.run_comparison(self.config, client=FakeClient())
        with tempfile.TemporaryDirectory(prefix="ebrt-hosted-test-") as directory:
            path = Path(directory) / "report.json"
            with mock.patch.object(hosted, "run_comparison", return_value=report) as run:
                code, stdout, stderr = self.invoke_cli(["--model", MODEL, "--output", str(path)])
            self.assertEqual(code, 0, stderr)
            run.assert_called_once()
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), report)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertNotIn(SECRET, stdout + stderr)
            self.assertNotIn("EVIDENCE_JSON", stdout)

    def test_cli_semantic_failure_keeps_report_and_exits_nonzero(self) -> None:
        report = hosted.run_comparison(self.config, client=FakeClient(response(), response(WRONG_REPLY)))
        with tempfile.TemporaryDirectory(prefix="ebrt-hosted-test-") as directory:
            path = Path(directory) / "report.json"
            with mock.patch.object(hosted, "run_comparison", return_value=report):
                code, stdout, stderr = self.invoke_cli(["--model", MODEL, "--output", str(path)])
            self.assertNotEqual(code, 0)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["status"], "FAIL")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_cli_provider_errors_print_fixed_codes_without_exception_messages(self) -> None:
        report = hosted.run_comparison(self.config, client=FakeClient(RuntimeError(SECRET), RuntimeError(SECRET)))
        with mock.patch.object(hosted, "run_comparison", return_value=report):
            code, stdout, stderr = self.invoke_cli(["--model", MODEL])
        self.assertNotEqual(code, 0)
        self.assertNotIn(SECRET, stdout + stderr)
        self.assertNotIn("EVIDENCE_JSON", stdout)

    def test_sdk_constructor_errors_are_sanitized_before_cli_output(self) -> None:
        factory = mock.Mock(side_effect=RuntimeError(SECRET))
        with (
            mock.patch.dict(sys.modules, {"openai": SimpleNamespace(OpenAI=factory)}),
            mock.patch.dict("os.environ", {"OPENAI_API_KEY": SECRET}),
        ):
            code, stdout, stderr = self.invoke_cli(["--model", MODEL])
        self.assertNotEqual(code, 0)
        factory.assert_called_once()
        self.assertNotIn(SECRET, stdout + stderr)
        self.assertIn("HOSTED_CLIENT_INITIALIZATION_FAILED", stderr)


if __name__ == "__main__":
    unittest.main()
