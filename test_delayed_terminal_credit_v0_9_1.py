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

if __name__=='__main__':unittest.main()
