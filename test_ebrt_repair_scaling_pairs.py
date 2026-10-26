import copy
import unittest
import ebrt_repair_scaling_pairs as pairs
from ebrt_core import EBRTError
from test_ebrt_hosted import FakeClient, MODEL, response
from test_ebrt_repair_scaling import client, raw_solution, judge, reseal


class PairedTests(unittest.TestCase):
    def setUp(self):self.plan=pairs.build_plan(MODEL)

    def test_success_reuses_exact_solvers(self):
        c=client(self.plan['study']);r=pairs.run_plan(self.plan,c)
        self.assertEqual(r['actual_provider_calls'],12)
        self.assertEqual(r['execution_status'],'PASS')
        self.assertEqual(pairs.verify_report(r,self.plan)['status'],'PASS')

    def test_all_solver_failures_are_six_attempts_with_skipped_judges(self):
        c=FakeClient(*(RuntimeError('private') for _ in range(6)))
        r=pairs.run_plan(self.plan,c)
        self.assertEqual(r['actual_provider_calls'],6)
        self.assertEqual(r['collection_status'],'COMPLETE')
        self.assertEqual(r['execution_status'],'FAIL')
        self.assertEqual(sum(s['status']=='SKIPPED_NO_CANDIDATE' for s in r['stages']),6)
        self.assertEqual(pairs.verify_report(r,self.plan)['checked_attempts'],6)

    def test_one_arm_failure_does_not_suppress_other_arm(self):
        outcomes=[]
        for case in self.plan['study']['cases']:
            raw=raw_solution(case)
            outcomes.extend([RuntimeError('private'),response(raw),response(judge(raw,case))])
        c=FakeClient(*outcomes);r=pairs.run_plan(self.plan,c)
        self.assertEqual(r['actual_provider_calls'],9)
        self.assertEqual(r['collection_status'],'COMPLETE')
        self.assertEqual(len(r['assessments']),3)
        self.assertTrue(all(k.endswith('/gradient_feedback') for k in r['assessments']))
        self.assertTrue(all(v['agreement'] for v in r['judgments'].values()))

    def test_judge_failure_continues_but_model_drift_stops(self):
        c=client(self.plan['study'],{2:'{}'})
        r=pairs.run_plan(self.plan,c)
        self.assertEqual(r['actual_provider_calls'],12)
        self.assertEqual(r['collection_status'],'COMPLETE')
        c=client(self.plan['study'],{1:response('{}',model='drift')})
        r=pairs.run_plan(self.plan,c)
        self.assertEqual(r['actual_provider_calls'],2)
        self.assertEqual(r['collection_status'],'INCOMPLETE')
        self.assertEqual(pairs.verify_report(r,self.plan)['status'],'PASS')

    def test_tampering_skip_and_truncated_collection_rejected(self):
        r=pairs.run_plan(self.plan,client(self.plan['study']))
        bad=copy.deepcopy(r);bad['stages']=bad['stages'][:4]
        with self.assertRaises(EBRTError):pairs.verify_report(reseal(bad),self.plan)
        bad=copy.deepcopy(r);bad['stages'][2]['slot']=3
        with self.assertRaises(EBRTError):pairs.verify_report(reseal(bad),self.plan)
        bad=copy.deepcopy(self.plan);bad['policy']='retry'
        with self.assertRaises(EBRTError):pairs.run_plan(reseal(bad),client(self.plan['study']))

    def test_pre_dispatch_error_stops_without_provider_attempt(self):
        c=FakeClient(max_retries=1);r=pairs.run_plan(self.plan,c)
        self.assertEqual(r['actual_provider_calls'],0)
        self.assertEqual(r['collection_status'],'INCOMPLETE')
        self.assertEqual(pairs.verify_report(r,self.plan)['status'],'PASS')

if __name__=='__main__':unittest.main()
