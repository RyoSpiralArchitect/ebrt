"""Offline conformance and public-contract checks for the comparison demo."""

from __future__ import annotations

import contextlib
import io
import json
import math
from pathlib import Path
import socket
import subprocess
import sys
import unittest
from unittest import mock

import ebrt_demo as demo
from ebrt_core import CallableModelAdapter, EBRTError, build_demo_task
from ebrt_engine import RevisionEngine
from local_output_diff_corpus_v0_8_2 import build_direct_invocation


class ComparisonDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = demo.run_demo()

    def test_report_is_deterministic_without_network(self) -> None:
        denied = AssertionError("the offline demo attempted network access")
        with (
            mock.patch.object(socket, "create_connection", side_effect=denied),
            mock.patch.object(socket, "getaddrinfo", side_effect=denied),
            mock.patch.object(socket.socket, "connect", side_effect=denied),
            mock.patch.object(socket.socket, "connect_ex", side_effect=denied),
        ):
            first = demo.run_demo()
            second = demo.run_demo()
        self.assertEqual(first, second)
        self.assertEqual(json.loads(json.dumps(first, allow_nan=False)), first)
        self.assertEqual(first["schema_version"], "ebrt-comparison-demo-v1")
        self.assertEqual(first["status"], "PASS")
        self.assertEqual(first["evidence_label"], "CONFORMANCE_ONLY")
        self.assertEqual(first["external_model_execution_status"], "NOT_RUN")
        self.assertEqual(first["effect_attribution_status"], "NOT_ASSESSED")

    def test_trajectory_is_the_real_core_receipt_and_replays_with_bounded_controls(self) -> None:
        receipts = []
        original_run = RevisionEngine.run

        def run_and_capture(engine, *args, **kwargs):
            receipt = original_run(engine, *args, **kwargs)
            receipts.append(receipt)
            return receipt

        with mock.patch.object(RevisionEngine, "run", run_and_capture):
            report = demo.run_demo()
        self.assertEqual(len(receipts), 1)
        trajectory = report["trajectory"]
        self.assertEqual(trajectory, receipts[0]["trajectory"])
        self.assertEqual(report["actuator"], receipts[0]["actuator"])
        self.assertTrue(all(trajectory["checks"].values()))

        # Replay the public dynamics independently of the report's checks.
        task = build_demo_task()
        axes = trajectory["axis_ids"]
        controls = trajectory["credit_map"]
        for arm, use_control in (("neutral", False), ("revised", True)):
            state = [0.0] * len(axes)
            for evidence, credit, observed in zip(
                task.evidence, controls, trajectory[arm]["trajectory"], strict=True
            ):
                admission = math.tanh(credit["control"]) if use_control else 0.0
                state = [
                    task.decay * previous + neutral + basis * admission
                    for previous, neutral, basis in zip(
                        state, evidence.neutral_effect, evidence.control_basis, strict=True
                    )
                ]
                self.assertEqual(observed["evidence_id"], evidence.evidence_id)
                for axis, expected in zip(axes, state, strict=True):
                    self.assertAlmostEqual(observed["state"][axis], expected, places=12)
        norm = math.sqrt(sum(row["control"] ** 2 for row in controls))
        self.assertLessEqual(norm, task.control_budget + 1e-12)
        self.assertTrue(any(row["gradient"] != 0 for row in controls[:trajectory["event_index"]]))
        self.assertTrue(all(row["control"] == 0 for row in controls if not row["eligible"]))
        for neutral, revised in zip(
            trajectory["neutral"]["trajectory"], trajectory["revised"]["trajectory"], strict=True
        ):
            self.assertEqual(neutral["state"]["stability"], revised["state"]["stability"])

    def test_both_actual_prompts_include_the_complete_evidence_and_late_correction(self) -> None:
        task = build_demo_task()
        expected = {row.evidence_id: row.text for row in task.evidence}
        headers = []
        for arm in self.report["arms"].values():
            lines = arm["invocation"]["prompt"].splitlines()
            records = [json.loads(line.removeprefix("EVIDENCE_JSON "))
                       for line in lines if line.startswith("EVIDENCE_JSON ")]
            self.assertEqual(len(records), len(expected))
            self.assertEqual({row["evidence_id"]: row["text"] for row in records}, expected)
            self.assertIn(expected[task.event.correction_evidence_id],
                          [row["text"] for row in records])
            headers.append([json.loads(line.removeprefix("TASK_JSON "))
                            for line in lines if line.startswith("TASK_JSON ")])
        self.assertEqual(len(headers[0]), 1)
        self.assertEqual(headers[0], headers[1])
        self.assertEqual(headers[0][0]["question"], task.question)
        self.assertTrue(all(self.report["verification"]["matched_inputs"].values()))

    def test_direct_baseline_has_no_external_revision_program(self) -> None:
        direct = self.report["arms"]["direct_full_context"]["invocation"]
        controlled = self.report["arms"]["ebrt_credit_first"]["invocation"]
        self.assertEqual(direct, build_direct_invocation(build_demo_task()))
        self.assertNotIn("actuator_program", direct)
        for marker in ("REINSPECT_JSON ", "SUPPRESS ", "PRESERVE "):
            self.assertFalse(any(line.startswith(marker) for line in direct["prompt"].splitlines()))
            self.assertTrue(any(line.startswith(marker) for line in controlled["prompt"].splitlines()))
        self.assertEqual(controlled["actuator_program"], self.report["actuator"])

    def test_same_fixed_generator_does_not_manufacture_a_baseline_loss(self) -> None:
        callbacks = []

        def capture_adapter(**kwargs):
            callbacks.append(kwargs["callback"])
            return CallableModelAdapter(**kwargs)

        with mock.patch.object(demo, "CallableModelAdapter", side_effect=capture_adapter):
            report = demo.run_demo()
        self.assertEqual(len(callbacks), 1)
        callback = callbacks[0]
        self.assertEqual(callback({"prompt": "ANSWER=POLISH"}),
                         callback({"prompt": "different evidence and no controls"}))
        direct = report["arms"]["direct_full_context"]
        controlled = report["arms"]["ebrt_credit_first"]
        self.assertEqual(direct["output"], controlled["output"])
        self.assertEqual(direct["output"], {
            "answer": "PROVE", "support_ids": ["R6", "R4", "R2"],
            "raw_text": "ANSWER=PROVE\nSUPPORT=R6,R4,R2",
        })
        for arm in (direct, controlled):
            self.assertEqual(arm["output_grade"]["status"], "PASS")
            self.assertTrue(all(arm["output_grade"]["checks"].values()))
        self.assertEqual(report["output_diff"], {
            "answer_changed": False, "support_changed": False, "raw_text_changed": False,
        })

    def test_walkthrough_exposes_the_revision_and_claim_limits(self) -> None:
        text = demo.render_text(self.report)
        for required in (
            "POLISH", "PROVE", "R6", "Gradient", "Control", "SUPPRESS R3", "PRESERVE R5",
            "direct_full_context", "ebrt_credit_first", "CONFORMANCE_ONLY", "NOT_ASSESSED",
            "fixed scripted", "--json",
        ):
            self.assertIn(required, text)
        self.assertIn("post-run contract=PASS", text)

    def test_cli_text_and_json(self) -> None:
        script = Path(demo.__file__).resolve()
        for args in ([], ["--json"]):
            result = subprocess.run(
                [sys.executable, str(script), *args], cwd=script.parent,
                capture_output=True, text=True, check=False, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, "")
            if args:
                self.assertEqual(json.loads(result.stdout), self.report)
            else:
                self.assertEqual(result.stdout, demo.render_text(self.report))

    def test_cli_failure_returns_nonzero_and_json_remains_parseable(self) -> None:
        for args in ([], ["--json"]):
            stdout, stderr = io.StringIO(), io.StringIO()
            with (
                mock.patch.object(demo, "run_demo", side_effect=EBRTError("TEST_CORE_FAILURE")),
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr),
            ):
                code = demo.main(args)
            self.assertEqual(code, 1)
            if args:
                self.assertEqual(json.loads(stdout.getvalue()), {
                    "status": "ERROR", "reason_code": "TEST_CORE_FAILURE",
                })
                self.assertEqual(stderr.getvalue(), "")
            else:
                self.assertEqual(stdout.getvalue(), "")
                self.assertIn("TEST_CORE_FAILURE", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
