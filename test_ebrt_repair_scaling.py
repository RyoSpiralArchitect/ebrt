import copy
import json
import socket
import unittest
from unittest.mock import patch
import ebrt_repair_scaling as scaling
from ebrt_core import EBRTError, _seal
from ebrt_coloring_repair import backward_feedback, solver_invocation
from test_ebrt_hosted import FakeClient, MODEL, response


def raw_solution(case):
    colors=min(scaling.solutions(case['problem']),key=lambda c:sum(c[n]!=case['prior_colors'][n] for n in c))
    return json.dumps({'colors':colors,'support_ids':['R2','R4','R6']})


def judge(raw,case):
    c=scaling.assess(raw,case)['checks']
    return json.dumps({'checks':c,'verdict':'PASS' if all(c.values()) else 'FAIL','violations':[k for k,v in c.items() if not v]})


def client(plan,override=None):
    outcomes=[]
    for case in plan['cases']:
        raw=raw_solution(case)
        outcomes.extend([raw,raw,judge(raw,case),judge(raw,case)])
    for i,value in (override or {}).items():outcomes[i]=value
    return FakeClient(*(response(x) if isinstance(x,str) else x for x in outcomes))


def reseal(x):
    x=copy.deepcopy(x);x.pop('fingerprint_sha256',None);return _seal(x)


class ScalingTests(unittest.TestCase):
    def setUp(self):
        self.block=patch.object(socket.socket,'connect',side_effect=AssertionError('no network'))
        self.block.start();self.addCleanup(self.block.stop)
        self.plan=scaling.build_plan(MODEL)

    def test_independent_natural_order_exhaustion_and_cascades(self):
        for case in self.plan['cases']:
            p=case['problem'];prior=case['prior_colors'];found=[]
            def visit(c):
                if len(c)==len(p['nodes']):found.append(dict(c));return
                n=p['nodes'][len(c)]
                for color in p['palette']:
                    if any((a==n and b in c and c[b]==color) or (b==n and a in c and c[a]==color) for a,b in p['edges']):continue
                    c[n]=color;visit(c);del c[n]
            visit({'A':'RED'})
            costs=[sum(c[n]!=prior[n] for n in prior) for c in found]
            self.assertEqual(len(found),case['oracle']['solution_count'])
            self.assertEqual(min(costs),case['oracle']['minimum_changes'])
            best=[c for c,k in zip(found,costs) if k==min(costs)]
            self.assertEqual(len(best),case['oracle']['optimal_solution_count'])
            active={n for edge in case['added_edges'] for n in edge}
            self.assertTrue(all(any(c[n]!=prior[n] for n in prior if n not in active) for c in best))

    def test_exact_reuse_and_no_oracle_in_prompts(self):
        for case in self.plan['cases']:
            self.assertEqual(case['feedback'],backward_feedback(case['problem'],case['prior_colors']))
            for arm in scaling.ARMS:
                prompt=solver_invocation(case,arm)['prompt']
                self.assertNotIn('minimum_changes',prompt)
                self.assertNotIn('optimal_solution_count',prompt)
                self.assertNotIn('oracle',prompt)
            self.assertEqual(solver_invocation(case,'full_repair')['prompt'].split('FEEDBACK_JSON')[0],solver_invocation(case,'gradient_feedback')['prompt'].split('FEEDBACK_JSON')[0])

    def test_twelve_call_ledger_and_blind_judge_routing(self):
        c=client(self.plan);r=scaling.run_plan(self.plan,c)
        self.assertEqual(len(c.responses.calls),12)
        self.assertEqual(r['execution_status'],'PASS')
        self.assertTrue(all(g['minimal_repair'] for g in r['assessments'].values()))
        for i,s in enumerate(r['stages']):
            if s['kind']=='judge':
                expected=scaling.judge_invocation(self.plan['cases'][i//4],r['stages'][i-2]['raw_text'])
                self.assertEqual(s['invocation'],expected)
                self.assertNotIn('PRIOR_COLORS_JSON',s['invocation']['prompt'])
                self.assertNotIn('gradient_feedback',s['invocation']['prompt'])
        self.assertEqual(scaling.verify_report(r,self.plan)['checked_stages'],12)

    def test_infeasible_completed_answer_does_not_change_schedule(self):
        case=self.plan['cases'][0];raw=json.dumps({'colors':case['prior_colors']})
        r=scaling.run_plan(self.plan,client(self.plan,{0:raw,2:judge(raw,case)}))
        self.assertEqual(r['actual_provider_calls'],12)
        grade=r['assessments']['cascade-10/full_repair']
        self.assertEqual(grade['feasibility'],'FAIL')
        self.assertIsNone(grade['excess_changes'])
        self.assertFalse(grade['minimal_repair'])

    def test_format_failure_and_disagreement(self):
        raw='not JSON';case=self.plan['cases'][0]
        r=scaling.run_plan(self.plan,client(self.plan,{0:raw,2:judge(raw,case)}))
        self.assertEqual(r['actual_provider_calls'],12)
        self.assertEqual(r['assessments']['cascade-10/full_repair']['format_status'],'FAIL')
        wrong=json.loads(judge(raw_solution(case),case));wrong['checks']['fixed_A']=False
        wrong['verdict']='FAIL';wrong['violations']=['fixed_A']
        r=scaling.run_plan(self.plan,client(self.plan,{2:json.dumps(wrong)}))
        self.assertEqual(r['actual_provider_calls'],12)
        self.assertFalse(r['judgments']['cascade-10/full_repair']['agreement'])

    def test_fail_closed_model_provider_and_judge(self):
        for overrides,count in (({0:RuntimeError('secret')},1),({1:response('{}',model='drift')},2),({2:'{}'},3)):
            r=scaling.run_plan(self.plan,client(self.plan,overrides))
            self.assertEqual(r['actual_provider_calls'],count)
            self.assertEqual(r['execution_status'],'FAIL')
            self.assertNotIn('secret',json.dumps(r))
            self.assertEqual(scaling.verify_report(r,self.plan)['status'],'PASS')

    def test_resealed_tampering_and_truncation(self):
        r=scaling.run_plan(self.plan,client(self.plan))
        bad=copy.deepcopy(r);bad['assessments']['cascade-10/full_repair']['change_count']=0
        with self.assertRaises(EBRTError):scaling.verify_report(reseal(bad),self.plan)
        bad=copy.deepcopy(r);bad['stages']=bad['stages'][:4]
        with self.assertRaises(EBRTError):scaling.verify_report(reseal(bad),self.plan)
        bad=copy.deepcopy(self.plan);bad['cases'][0]['oracle']['minimum_changes']=0
        with self.assertRaises(EBRTError):scaling.run_plan(reseal(bad),client(self.plan))

    def test_hidden_retries_before_any_dispatch(self):
        c=client(self.plan);c.max_retries=1
        r=scaling.run_plan(self.plan,c)
        self.assertEqual(r['actual_provider_calls'],0)
        self.assertEqual(scaling.verify_report(r,self.plan)['status'],'PASS')

if __name__=='__main__':unittest.main()
