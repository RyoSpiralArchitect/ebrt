import copy
import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ebrt_hard_repair as hard
import ebrt_hard_timeout as followup
from ebrt_core import EBRTError
from test_ebrt_hard_repair import client
from test_ebrt_hosted import FakeClient, MODEL, response
from test_ebrt_repair_scaling import reseal


class HardTimeoutTests(unittest.TestCase):
    def setUp(self):
        guard = patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden'))
        guard.start()
        self.addCleanup(guard.stop)
        self.plan = followup.build_plan(MODEL)

    def test_only_timeout_changes_and_all_prompts_remain_identical(self):
        baseline = hard.build_plan(MODEL)
        self.assertEqual(self.plan['baseline_plan_fingerprint_sha256'], baseline['fingerprint_sha256'])
        actual = copy.deepcopy(self.plan)
        for key in ('baseline_plan_fingerprint_sha256', 'runner_sha256', 'changed_generation_fields'):
            actual.pop(key)
        actual['schema_version'] = baseline['schema_version']
        actual['config']['timeout_seconds'] = baseline['config']['timeout_seconds']
        self.assertEqual(reseal(actual), baseline)
        old = hard.run_plan(baseline, client(baseline))
        new = followup.run_plan(self.plan, client(self.plan))
        self.assertEqual([s['invocation'] for s in new['stages']], [s['invocation'] for s in old['stages']])
        with self.assertRaises(EBRTError):
            hard.validate_plan(self.plan)
        with self.assertRaises(EBRTError):
            followup.validate_plan(baseline)

    def test_sdk_uses_equal_timeout_caps_and_all_denominators(self):
        c = client(self.plan)
        progress = []
        result = followup.run_plan(self.plan, c, progress=progress.append)
        self.assertEqual(result['actual_provider_calls'], 24)
        self.assertEqual(result['execution_status'], 'PASS')
        self.assertEqual(len(c.responses.calls), 24)
        for call in c.responses.calls:
            self.assertEqual(call['timeout'], 180.0)
            self.assertEqual(call['max_output_tokens'], 4096)
            self.assertEqual(call['reasoning'], {'effort': 'low'})
        for arm in hard.ARMS:
            self.assertEqual(result['summary'][arm], {'planned': 6, 'attempted': 6, 'completed': 6, 'feasible': 6, 'minimal': 6})
        self.assertEqual(len(progress), 24)
        self.assertTrue(all(set(p) == {'slot', 'trial', 'case', 'arm', 'kind', 'status'} for p in progress))
        self.assertEqual(followup.verify_report(result, self.plan)['checked_attempts'], 24)

    def test_timeouts_are_not_retried_or_removed_from_denominators(self):
        timeout_error = type('APITimeoutError', (Exception,), {})
        c = FakeClient(*(timeout_error('private message') for _ in range(12)))
        result = followup.run_plan(self.plan, c)
        self.assertEqual(len(c.responses.calls), 12)
        self.assertEqual(result['collection_status'], 'COMPLETE')
        self.assertEqual(result['execution_status'], 'FAIL')
        for arm in hard.ARMS:
            self.assertEqual(result['summary'][arm], {'planned': 6, 'attempted': 6, 'completed': 0, 'feasible': 0, 'minimal': 0})
        self.assertEqual(sum(s['status'] == 'SKIPPED_NO_CANDIDATE' for s in result['stages']), 12)
        self.assertTrue(all(s['error_code'] == 'HOSTED_PROVIDER_TIMEOUT' for s in result['stages'] if s['provider_attempt']))
        self.assertNotIn('private message', json.dumps(result))
        self.assertEqual(followup.verify_report(result, self.plan)['status'], 'PASS')

    def test_drift_and_hidden_retries_stop_and_invalid_candidates_are_judged(self):
        result = followup.run_plan(self.plan, client(self.plan, {1: response('{}', model='drift')}))
        self.assertEqual(result['actual_provider_calls'], 2)
        self.assertEqual(result['collection_status'], 'INCOMPLETE')
        c = FakeClient(max_retries=1)
        result = followup.run_plan(self.plan, c)
        self.assertEqual(result['actual_provider_calls'], 0)
        self.assertEqual(c.responses.calls, [])
        self.assertEqual(followup.verify_report(result, self.plan)['status'], 'PASS')
        result = followup.run_plan(self.plan, client(self.plan, {0: 'not json', 2: '{}'}))
        self.assertEqual(result['actual_provider_calls'], 24)
        self.assertEqual(result['summary']['full_repair']['feasible'], 5)
        self.assertEqual(result['stages'][2]['status'], 'JUDGE_FORMAT_ERROR')

    def test_resealed_settings_receipts_grades_and_truncation_rejected(self):
        for field, value in (('timeout_seconds', 60.0), ('max_output_tokens', 2048), ('max_retries', 1)):
            bad = copy.deepcopy(self.plan)
            bad['config'][field] = value
            c = client(self.plan)
            with self.assertRaises(EBRTError):
                followup.run_plan(reseal(bad), c)
            self.assertEqual(c.responses.calls, [])
        result = followup.run_plan(self.plan, client(self.plan))
        for change in ('grade', 'truncation', 'receipt'):
            bad = copy.deepcopy(result)
            if change == 'grade':
                bad['summary']['full_repair']['minimal'] = 0
            elif change == 'truncation':
                bad['stages'] = bad['stages'][:12]
            else:
                bad['stages'][0]['provider_receipt']['generation_config_fingerprint_sha256'] = '0' * 64
            with self.assertRaises(EBRTError):
                followup.verify_report(reseal(bad), self.plan)

    def test_private_cli_output_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'plan.json'
            with patch('sys.argv', ['followup', 'plan', '--output', str(target)]):
                self.assertEqual(followup.main(), 0)
                self.assertEqual(target.stat().st_mode & 0o777, 0o600)
                with self.assertRaises(EBRTError):
                    followup.main()


if __name__ == '__main__':
    unittest.main()
