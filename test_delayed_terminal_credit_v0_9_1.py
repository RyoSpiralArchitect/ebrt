"""Network-zero tests for delayed terminal credit and sealed API pilot."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import delayed_terminal_credit_v0_9_1 as e


class CanaryTests(unittest.TestCase):
    def test_exact_delayed_nonlocal_gradient(self):
        receipt = e.offline_checks()
        self.assertEqual(receipt['status'], 'PASS')
        self.assertEqual(len(receipt['cases']), 3)
        for row in receipt['cases']:
            self.assertEqual(row['local_gradient'], [0.0,0.0,0.0])
            self.assertNotEqual(row['terminal_gradient'], [0.0,0.0,0.0])
            self.assertNotEqual(row['adjoint_weights'], row['sham_weights'])
            self.assertEqual(sorted(row['adjoint_weights']), sorted(row['sham_weights']))

    def test_matched_public_information_and_oracle_isolation(self):
        for case in e.CASES:
            adjacent = e.prompt(case, 'adjoint')
            scrambled = e.prompt(case, 'scrambled')
            self.assertEqual(adjacent.split('Public review weights')[0],
                             scrambled.split('Public review weights')[0])
            self.assertEqual(e.oracle(case)['support_ids'][-3:],
                             ['E_T1','E_T2','E_EVENT'])
            self.assertEqual(sorted(e.allocation(case,'adjoint')['site_weights']),
                             sorted(e.allocation(case,'scrambled')['site_weights']))

    def test_plan_lock_and_idempotent_destination(self):
        with tempfile.TemporaryDirectory() as d:
            plan=e.make_plan('test-local-model',384)
            e.verify_plan(plan)
            self.assertEqual(len(plan['schedule']),9)
            p=Path(d)/'plan.json'
            e.write_exclusive(p,plan)
            with self.assertRaises(FileExistsError):e.write_exclusive(p,plan)
            tampered=json.loads(json.dumps(plan))
            tampered['schedule'][0]['prompt']+=' anything'
            with self.assertRaisesRegex(RuntimeError,'PLAN_FINGERPRINT_INVALID'):
                e.verify_plan(tampered)
            tampered['fingerprint_sha256']=e.sha({k:v for k,v in tampered.items() if k!='fingerprint_sha256'})
            with self.assertRaisesRegex(RuntimeError,'PLAN_SOURCE_OR_SCHEDULE_MISMATCH'):
                e.verify_plan(tampered)

    def test_fake_api_exact_nine_calls_and_verify(self):
        with tempfile.TemporaryDirectory() as d:
            plan=e.make_plan('fake-model',384)
            p=Path(d)/'results.json'
            calls=[]
            class FakeResponses:
                def create(self,**kwargs):
                    i=len(calls);calls.append(kwargs)
                    row=plan['schedule'][i]
                    case=next(x for x in e.CASES if x['id']==row['case_id'])
                    result=e.oracle(case)
                    return SimpleNamespace(status='completed', model='fake-model',
                        output_text=json.dumps({'answer':result['answer'],'support_ids':result['support_ids']}),
                        usage=SimpleNamespace(input_tokens=200,output_tokens=50))
            class FakeOpenAI:
                def __init__(self,**kwargs):
                    self.responses=FakeResponses()
                    self.config=kwargs
            with mock.patch.dict(os.environ,{'OPENAI_API_KEY':'stub'}), mock.patch.dict(sys.modules,{'openai':SimpleNamespace(OpenAI=FakeOpenAI)}):
                result=e.run(plan,p)
            self.assertEqual(len(calls),9)
            self.assertEqual(result['status'],'COMPLETE_EXACT_NINE_TERMINALS')
            grade=e.verify_report(plan,e.read_json(p))
            self.assertEqual(grade['status'],'DESCRIPTIVE_ONLY')
            self.assertEqual([row['strict'] for row in grade['by_arm'].values()],[3,3,3])
            self.assertTrue(all(x['store'] is False for x in calls))
            self.assertTrue(all(x['model']=='fake-model' for x in calls))
            with self.assertRaisesRegex(RuntimeError,'REPORT_ALREADY_EXISTS'):
                with mock.patch.dict(os.environ,{'OPENAI_API_KEY':'stub'}):e.run(plan,p)

    def test_failure_keeps_journal_no_rescue(self):
        with tempfile.TemporaryDirectory() as d:
            plan=e.make_plan('fake-model',384)
            calls=[]
            class FakeResponses:
                def create(self,**kwargs):calls.append(kwargs);raise RuntimeError('offline-failure')
            class FakeOpenAI:
                def __init__(self,**kwargs):self.responses=FakeResponses()
            p=Path(d)/'result.json'
            with mock.patch.dict(os.environ,{'OPENAI_API_KEY':'stub'}), mock.patch.dict(sys.modules,{'openai':SimpleNamespace(OpenAI=FakeOpenAI)}):
                result=e.run(plan,p)
            self.assertEqual(len(calls),1)
            self.assertEqual(result['status'],'STOP_ON_PROVIDER_ERROR')
            self.assertEqual(e.verify_report(plan,e.read_json(p))['status'],'INCOMPLETE_NOT_ASSESSED')
            self.assertEqual(len(e.read_json(p)['attempts']),1)
            self.assertEqual(e.read_json(p)['attempts'][0]['status'],'ERROR')

    def test_no_credential_refuses_before_ledger(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'report.json'
            with mock.patch.dict(os.environ,{},clear=True):
                with self.assertRaisesRegex(RuntimeError,'OPENAI_API_KEY_UNAVAILABLE'):
                    e.run(e.make_plan('fake-model',384),p)
            self.assertFalse(p.exists())

class ReviewRegressionTests(unittest.TestCase):
    """Attack the recorded boundary, not model answer quality."""

    def _collect(self, response_factory=None):
        plan = e.make_plan("fake-model", 384)
        calls, configurations = [], []
        class FakeResponses:
            def create(self, **kwargs):
                index = len(calls)
                calls.append(kwargs)
                if response_factory is not None:
                    return response_factory(index, plan["schedule"][index])
                row = plan["schedule"][index]
                case = next(c for c in e.CASES if c["id"] == row["case_id"])
                expected = e.oracle(case)
                return SimpleNamespace(
                    id=f"fake-{index}", status="completed", model="fake-model",
                    output_text=json.dumps({"answer": expected["answer"],
                                            "support_ids": expected["support_ids"]}),
                    usage=SimpleNamespace(input_tokens=200, output_tokens=50,
                                          total_tokens=250),
                )
        class FakeOpenAI:
            def __init__(self, **kwargs):
                configurations.append(kwargs)
                self.responses = FakeResponses()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "stub"}), \
                 mock.patch.dict(sys.modules, {"openai": SimpleNamespace(OpenAI=FakeOpenAI)}):
                result = e.run(plan, path)
            self.assertEqual(result, e.read_json(path))
            self.assertEqual(configurations, [{"max_retries": 0, "timeout": 60.0}])
        return plan, result, calls

    def _reseal(self, report):
        return e.sealed({k: v for k, v in report.items() if k != "fingerprint_sha256"})

    def test_incomplete_response_evidence_survives_stop(self):
        def incomplete(_index, _row):
            return SimpleNamespace(id="partial-response", status="incomplete",
                model="fake-model", output_text='{"answer":"14"',
                incomplete_details=SimpleNamespace(reason="max_output_tokens"),
                usage=SimpleNamespace(input_tokens=20, output_tokens=384, total_tokens=404,
                    output_tokens_details=SimpleNamespace(reasoning_tokens=123)))
        plan, report, calls = self._collect(incomplete)
        self.assertEqual(len(calls), 1)
        slot = report["attempts"][0]
        self.assertEqual(slot["reason"], "PROVIDER_INCOMPLETE")
        self.assertEqual(slot["raw"], '{"answer":"14"')
        self.assertEqual(slot["provider_response_id"], "partial-response")
        self.assertEqual(slot["returned_model"], "fake-model")
        self.assertEqual(slot["incomplete_reason"], "max_output_tokens")
        self.assertEqual(slot["usage"]["reasoning_tokens"], 123)
        self.assertNotIn("grade", slot)
        self.assertEqual(e.verify_report(plan, report)["status"], "INCOMPLETE_NOT_ASSESSED")

    def test_model_drift_keeps_receipt_without_grading_or_retry(self):
        def drift(_index, _row):
            return SimpleNamespace(id="drift-response", status="completed",
                model="different-model", output_text="public partial text", usage=None)
        plan, report, calls = self._collect(drift)
        slot = report["attempts"][0]
        self.assertEqual(len(calls), 1)
        self.assertEqual(slot["reason"], "RETURNED_MODEL_DRIFT")
        self.assertEqual(slot["provider_response_id"], "drift-response")
        self.assertEqual(slot["raw"], "public partial text")
        self.assertTrue(all(v is None for v in slot["usage"].values()))
        self.assertEqual(e.verify_report(plan, report)["status"], "INCOMPLETE_NOT_ASSESSED")

    def test_resealed_wrong_or_missing_model_is_rejected(self):
        plan, report, _ = self._collect()
        for value in ("wrong-model", None):
            altered = json.loads(json.dumps(report))
            if value is None:
                del altered["attempts"][0]["returned_model"]
            else:
                altered["attempts"][0]["returned_model"] = value
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                e.verify_report(plan, self._reseal(altered))

    def test_resealed_terminal_state_contradictions_are_rejected(self):
        plan, report, _ = self._collect()
        for status in ("STOP_ON_PROVIDER_ERROR", "UNKNOWN"):
            altered = json.loads(json.dumps(report)); altered["status"] = status
            with self.subTest(status=status), self.assertRaisesRegex(RuntimeError, "REPORT_TERMINAL_STATE_INVALID"):
                e.verify_report(plan, self._reseal(altered))
        altered = json.loads(json.dumps(report)); altered["attempts"].pop()
        with self.assertRaisesRegex(RuntimeError, "REPORT_TERMINAL_STATE_INVALID"):
            e.verify_report(plan, self._reseal(altered))

    def test_nonterminal_failure_and_false_provider_status_rejected(self):
        plan, report, _ = self._collect()
        altered = json.loads(json.dumps(report)); altered["attempts"][0]["status"] = "ERROR"
        with self.assertRaisesRegex(RuntimeError, "ATTEMPT_AFTER_TERMINAL_FAILURE"):
            e.verify_report(plan, self._reseal(altered))
        altered = json.loads(json.dumps(report)); altered["attempts"][0]["provider_status"] = "incomplete"
        with self.assertRaisesRegex(RuntimeError, "RECORDED_PROVIDER_STATUS_INVALID"):
            e.verify_report(plan, self._reseal(altered))

    def test_schema_invalid_outputs_remain_in_denominator(self):
        def invalid(_index, _row):
            return SimpleNamespace(id="invalid-output", status="completed",
                model="fake-model", output_text="not JSON", usage=None)
        plan, report, calls = self._collect(invalid)
        result = e.verify_report(plan, report)
        self.assertEqual(len(calls), 9)
        self.assertEqual(result["status"], "DESCRIPTIVE_ONLY")
        self.assertTrue(all(r["planned"] == r["completed"] == 3 and r["strict"] == 0
                            for r in result["by_arm"].values()))

    def test_duplicate_json_and_nonfinite_are_not_silently_accepted(self):
        for text in ('{"answer":"wrong","answer":"5","support_ids":[]}',
                     '{"answer":"5","support_ids":[],"x":NaN}',
                     '{"x":1e999}'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                e.strict_json(text)
        row = e.make_plan("fake-model", 384)["schedule"][0]
        self.assertFalse(e.grade(row, '{"answer":"wrong","answer":"5","support_ids":[]}')["schema_valid"])

    def test_resealed_bool_usage_and_numeric_grade_are_rejected(self):
        plan, report, _ = self._collect()
        altered = json.loads(json.dumps(report)); altered["attempts"][0]["usage"]["input_tokens"] = True
        with self.assertRaisesRegex(RuntimeError, "USAGE_RECEIPT_INVALID"):
            e.verify_report(plan, self._reseal(altered))
        altered = json.loads(json.dumps(report)); altered["attempts"][0]["grade"]["strict"] = 1
        with self.assertRaisesRegex(RuntimeError, "GRADE_REPLAY_MISMATCH"):
            e.verify_report(plan, self._reseal(altered))

    def test_grades_match_independent_fixture_expectations(self):
        expectations = (("5", [0, -4, 4]), ("14", [38, 19, 19]), ("0", [-40, 0, 40]))
        for case, (answer, gradient) in zip(e.CASES, expectations):
            self.assertEqual(e.oracle(case)["answer"], answer)
            self.assertEqual(e.credit(case)["terminal_gradient"], gradient)

    def test_cli_reports_nonzero_on_stopped_or_incomplete_block(self):
        with mock.patch.object(sys, "argv", ["runner", "run", "--plan", "p", "--output", "r"]), \
             mock.patch.object(e, "read_json", return_value={}), \
             mock.patch.object(e, "run", return_value={"status": "STOP_ON_PROVIDER_ERROR"}), \
             mock.patch("builtins.print"):
            self.assertEqual(e.main(), 1)

if __name__=='__main__':unittest.main()
