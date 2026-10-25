import copy
import itertools
import json
import socket
import unittest
from unittest.mock import patch
import ebrt_coloring_repair as repair
from ebrt_core import EBRTError, _seal
from ebrt_hosted import HostedConfig
from test_ebrt_hosted import FakeClient, MODEL, response
from test_ebrt_coloring import judge_reply


def candidate(vertex='B'):
    colors=repair.prior_colors()
    colors[vertex]='BLUE' if vertex=='B' else 'RED'
    return json.dumps({'colors':colors,'support_ids':['R2','R4','R6']})


def client(first=None,second=None):
    first=first or candidate('B'); second=second or candidate('E')
    return FakeClient(*(response(x) for x in (first,second,judge_reply(first),judge_reply(second))))


def reseal(value):
    value=copy.deepcopy(value); value.pop('fingerprint_sha256',None)
    return _seal(value)


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.net=patch.object(socket.socket,'connect',side_effect=AssertionError('no network'))
        self.net.start(); self.addCleanup(self.net.stop)
        self.plan=repair.build_plan(HostedConfig(MODEL,max_output_tokens=512))

    def test_independent_minimum_has_two_solutions(self):
        p=self.plan; prior=p['prior_colors']; edges=['AB','BC','CD','DE','EF','FA']
        self.assertTrue(all(prior[a]!=prior[b] for a,b in edges))
        self.assertEqual(prior['B'],prior['E'])
        feasible=[]
        for tail in itertools.product(('RED','GREEN','BLUE'),repeat=5):
            colors=dict(zip('ABCDEF',('RED',*tail)))
            if all(colors[a]!=colors[b] for a,b in edges+['BE']):
                feasible.append(colors)
        self.assertEqual(len(feasible),18)
        minima=[c for c in feasible if sum(c[n]!=prior[n] for n in prior)==1]
        self.assertEqual(len(minima),2)
        self.assertEqual({tuple(n for n in prior if c[n]!=prior[n]) for c in minima},{('B',),('E',)})

    def test_actual_backward_localizes_active_edge_and_zero_case(self):
        f=self.plan['feedback']
        self.assertEqual(f['loss'],1)
        self.assertEqual(f['suggested_vertices'],['B','E'])
        self.assertEqual(f['violated_edges'],['BE'])
        self.assertEqual(f['gradient_by_vertex']['B'],[0,1,0])
        self.assertTrue(all(f['repair_priority'][n]==0 for n in 'ACDF'))
        fixed=json.loads(candidate())['colors']
        zero=repair.backward_feedback(self.plan['problem'],fixed)
        self.assertEqual(zero['loss'],0)
        self.assertEqual(zero['suggested_vertices'],[])

    def test_prompt_changes_only_feedback_and_hides_optimum(self):
        prompts=[repair.solver_invocation(self.plan,a)['prompt'] for a in repair.ARMS]
        self.assertEqual(prompts[0].split('FEEDBACK_JSON')[0],prompts[1].split('FEEDBACK_JSON')[0])
        for prompt in prompts:
            self.assertNotIn('minimum_feasible_changes',prompt)
            self.assertNotIn(candidate(),prompt)
        self.assertTrue(prompts[0].endswith('null'))

    def test_four_calls_two_minimal_repairs_blind_judges(self):
        c=client(); r=repair.run_plan(self.plan,c)
        self.assertEqual(len(c.responses.calls),4)
        self.assertEqual(r['execution_status'],'PASS')
        for a in repair.ARMS:
            self.assertTrue(r['assessments'][a]['minimal_repair'])
            self.assertEqual(r['assessments'][a]['change_count'],1)
            self.assertEqual(r['judgments'][a]['agreement']['status'],'AGREE')
        for stage in r['stages'][2:]:
            prompt=stage['invocation']['prompt']
            self.assertNotIn('PRIOR_COLORS_JSON',prompt)
            self.assertNotIn('gradient_feedback',prompt)
        self.assertEqual(repair.verify_report(r,self.plan)['checked_stages'],4)

    def test_nonminimal_feasible_repair_is_not_optimal(self):
        raw=json.dumps({'colors':dict(zip('ABCDEF',('RED','GREEN','RED','GREEN','RED','GREEN'))),'support_ids':['R2','R4','R6']})
        r=repair.run_plan(self.plan,client(first=raw))
        a=r['assessments']['full_repair']
        self.assertEqual(a['candidate']['feasibility']['status'],'PASS')
        self.assertEqual(a['change_count'],3)
        self.assertFalse(a['minimal_repair'])
        self.assertEqual(r['actual_provider_calls'],4)

    def test_invalid_candidate_still_judged_without_repair(self):
        r=repair.run_plan(self.plan,client(first='not json'))
        self.assertEqual(r['actual_provider_calls'],4)
        self.assertIsNone(r['assessments']['full_repair']['change_count'])
        self.assertFalse(r['assessments']['full_repair']['minimal_repair'])
        self.assertEqual(r['judgments']['full_repair']['judgment']['verdict'],'FAIL')

    def test_judge_disagreement_preserved(self):
        wrong=json.loads(judge_reply(candidate())); wrong['checks']['edge_BE']=False
        wrong['verdict']='FAIL'; wrong['violations']=['edge_BE']
        c=FakeClient(response(candidate()),response(candidate('E')),response(json.dumps(wrong)),response(judge_reply(candidate('E'))))
        r=repair.run_plan(self.plan,c)
        self.assertEqual(r['judgments']['full_repair']['agreement']['status'],'DISAGREE')
        self.assertEqual(r['actual_provider_calls'],4)

    def test_provider_and_judge_failures_stop(self):
        for outcomes, count in (([RuntimeError('private secret')],1),([response(candidate()),response(candidate('E')),response('{}')],3)):
            c=FakeClient(*outcomes); r=repair.run_plan(self.plan,c)
            self.assertEqual(r['execution_status'],'FAIL')
            self.assertEqual(r['actual_provider_calls'],count)
            self.assertNotIn('private secret',json.dumps(r))
            self.assertEqual(repair.verify_report(r,self.plan)['status'],'PASS')

    def test_tampering_and_truncated_success_rejected(self):
        r=repair.run_plan(self.plan,client())
        bad=copy.deepcopy(r); bad['assessments']['full_repair']['change_count']=0
        with self.assertRaises(EBRTError): repair.verify_report(reseal(bad),self.plan)
        bad=copy.deepcopy(r); bad['stages']=bad['stages'][:2]
        with self.assertRaises(EBRTError): repair.verify_report(reseal(bad),self.plan)
        bad=copy.deepcopy(self.plan); bad['feedback']['suggested_vertices']=['C']
        with self.assertRaises(EBRTError): repair.run_plan(reseal(bad),client())

    def test_returned_model_change_stops_before_judges(self):
        c=FakeClient(response(candidate()), response(candidate('E'), model='changed-model'))
        r=repair.run_plan(self.plan,c)
        self.assertEqual(r['actual_provider_calls'],2)
        self.assertEqual(r['stages'][-1]['status'],'MODEL_MISMATCH')
        self.assertEqual(repair.verify_report(r,self.plan)['status'],'PASS')

    def test_feedback_gradient_matches_finite_difference(self):
        palette=self.plan['problem']['palette']; prior=self.plan['prior_colors']
        state={n:[float(prior[n]==color) for color in palette] for n in prior}
        def loss(x): return sum(a*b for a,b in zip(x['B'],x['E']))
        eps=1e-6
        for n in prior:
            for k in range(3):
                plus=copy.deepcopy(state); minus=copy.deepcopy(state)
                plus[n][k]+=eps; minus[n][k]-=eps
                numerical=(loss(plus)-loss(minus))/(2*eps)
                self.assertAlmostEqual(numerical,self.plan['feedback']['gradient_by_vertex'][n][k],places=8)

    def test_hidden_retries_rejected_before_dispatch(self):
        c=client(); c.max_retries=1
        r=repair.run_plan(self.plan,c)
        self.assertEqual(r['actual_provider_calls'],0)
        self.assertEqual(len(c.responses.calls),0)
        self.assertEqual(repair.verify_report(r,self.plan)['status'],'PASS')

if __name__=='__main__': unittest.main()
