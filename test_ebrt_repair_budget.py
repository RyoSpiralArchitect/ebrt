import copy
import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ebrt_repair_budget as budget
import ebrt_repair_scaling_pairs as pairs
from ebrt_core import EBRTError
from test_ebrt_hosted import FakeClient, MODEL, response
from test_ebrt_repair_scaling import client, raw_solution, judge, reseal


class BudgetTests(unittest.TestCase):
    def setUp(self):
        block = patch.object(socket.socket, 'connect', side_effect=AssertionError('no network'))
        block.start()
        self.addCleanup(block.stop)
        self.plan = budget.build_plan(MODEL)

    def test_only_solver_generation_ceiling_changes(self):
        base = pairs.build_plan(MODEL)
        self.assertEqual(self.plan['baseline_plan_fingerprint_sha256'], base['fingerprint_sha256'])
        expected = dict(base['study'])
        expected.pop('fingerprint_sha256')
        actual = dict(self.plan['study'])
        actual.pop('fingerprint_sha256')
        actual['schema_version'] = expected['schema_version']
        actual['solver_config'] = dict(actual['solver_config'], max_output_tokens=512)
        self.assertEqual(actual, expected)
        self.assertEqual(self.plan['paired_runner_sha256'], base['runner_sha256'])
        for case in self.plan['study']['cases']:
            for arm in pairs.ARMS:
                old = next(c for c in base['study']['cases'] if c['id'] == case['id'])
                self.assertEqual(pairs.solver_invocation(case, arm), pairs.solver_invocation(old, arm))

    def test_actual_sdk_requests_use_matched_caps_and_replay(self):
        c = client(self.plan['study'])
        progress = []
        result = budget.run_plan(self.plan, c, progress=progress.append)
        self.assertEqual(result['actual_provider_calls'], 12)
        self.assertEqual(result['execution_status'], 'PASS')
        self.assertEqual([call['max_output_tokens'] for call in c.responses.calls], [4096,4096,2048,2048]*3)
        self.assertEqual(len(progress), 12)
        self.assertTrue(all(set(item) == {'slot','case','arm','kind','status'} for item in progress))
        self.assertEqual(budget.verify_report(result, self.plan)['checked_attempts'], 12)

    def test_unusable_answers_do_not_trigger_more_calls(self):
        case = self.plan['study']['cases'][0]
        raw = json.dumps({'colors': case['prior_colors']})
        result = budget.run_plan(self.plan, client(self.plan['study'], {0:raw, 2:judge(raw, case)}))
        self.assertEqual(result['actual_provider_calls'], 12)
        self.assertEqual(result['assessments']['cascade-10/full_repair']['feasibility'], 'FAIL')

    def test_failures_are_isolated_and_model_drift_still_fatal(self):
        result = budget.run_plan(self.plan, FakeClient(*(RuntimeError('secret') for _ in range(6))))
        self.assertEqual(result['actual_provider_calls'], 6)
        self.assertEqual(result['collection_status'], 'COMPLETE')
        self.assertEqual(sum(s['status']=='SKIPPED_NO_CANDIDATE' for s in result['stages']), 6)
        self.assertEqual(budget.verify_report(result, self.plan)['status'], 'PASS')
        result = budget.run_plan(self.plan, client(self.plan['study'], {1:response('{}', model='drift')}))
        self.assertEqual(result['actual_provider_calls'], 2)
        self.assertEqual(result['collection_status'], 'INCOMPLETE')

    def test_resealed_cap_case_policy_and_grade_tampering_rejected(self):
        for field in ('solver_config','judge_config'):
            bad = copy.deepcopy(self.plan)
            bad['study'][field]['max_output_tokens'] = 1024
            bad['study'] = reseal(bad['study'])
            with self.assertRaises(EBRTError):
                budget.run_plan(reseal(bad), client(self.plan['study']))
        result = budget.run_plan(self.plan, client(self.plan['study']))
        bad = copy.deepcopy(result)
        bad['assessments']['cascade-10/full_repair']['minimal_repair'] = False
        with self.assertRaises(EBRTError): budget.verify_report(reseal(bad), self.plan)
        bad = copy.deepcopy(result); bad['stages'] = bad['stages'][:4]
        with self.assertRaises(EBRTError): budget.verify_report(reseal(bad), self.plan)

    def test_old_validator_cannot_accept_new_budget_as_old_plan(self):
        with self.assertRaises(EBRTError): pairs.validate_plan(self.plan)
        old = pairs.build_plan(MODEL)
        with self.assertRaises(EBRTError): budget.validate_plan(old)

    def test_hidden_retries_rejected_before_dispatch(self):
        c = FakeClient(max_retries=1)
        result = budget.run_plan(self.plan, c)
        self.assertEqual(result['actual_provider_calls'], 0)
        self.assertEqual(result['collection_status'], 'INCOMPLETE')
        self.assertEqual(budget.verify_report(result, self.plan)['status'], 'PASS')

    def test_private_cli_plan_and_nonoverwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/'plan.json'
            argv = ['budget','plan','--model',MODEL,'--output',str(target)]
            with patch('sys.argv', argv): self.assertEqual(budget.main(), 0)
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            with patch('sys.argv', argv), self.assertRaises(EBRTError): budget.main()


if __name__ == '__main__':
    unittest.main()
