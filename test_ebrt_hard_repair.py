import copy,itertools,json,random,socket,unittest
from pathlib import Path
from unittest.mock import patch
import ebrt_hard_repair as h
from ebrt_hard_oracle import exact_minimum
from ebrt_coloring_repair import solver_invocation
from ebrt_core import EBRTError
from test_ebrt_hosted import FakeClient, response
from test_ebrt_repair_scaling import reseal


def candidate(plan,case_id):
    f=next(f for f in json.loads((h.ROOT/h.FIXTURE).read_text()) if f['id']==case_id)
    return json.dumps({'colors':{n:h.study.PALETTE[c] for n,c in f['witnesses'][0].items()},'support_ids':['R2','R4','R6']})


def client(plan,overrides=None):
    outcomes=[]
    for i,item in enumerate(plan['schedule']):
        case=next(c for c in plan['cases'] if c['id']==item['case']);raw=candidate(plan,case['id'])
        if item['kind']=='judge':
            checks=h.study.assess(raw,case)['checks']
            raw=json.dumps({'verdict':'PASS','checks':checks,'violations':[]})
        value=(overrides or {}).get(i,raw)
        outcomes.append(response(value) if isinstance(value,str) else value)
    return FakeClient(*outcomes)


class HardTests(unittest.TestCase):
    def setUp(self):
        guard=patch.object(socket.socket,'connect',side_effect=AssertionError('network forbidden'))
        guard.start();self.addCleanup(guard.stop);self.plan=h.build_plan('gpt-test-fixture')

    def test_exact_search_against_independent_brute_force(self):
        for seed in range(12):
            rng=random.Random(seed);nodes=list('ABCDEF');prior={n:rng.randrange(3) for n in nodes};prior['A']=0
            target={n:rng.randrange(3) for n in nodes};target['A']=0
            edges=[list(e) for e in itertools.combinations(nodes,2) if target[e[0]]!=target[e[1]] and rng.random()<.7]
            added=[e for e in edges if prior[e[0]]==prior[e[1]]];active={n for e in added for n in e}
            f={'nodes':nodes,'edges':edges,'prior':prior,'added':added}
            for restricted in (False,True):
                costs=[]
                for rest in itertools.product(range(3),repeat=5):
                    c=dict(zip(nodes,(0,*rest)))
                    if all(c[a]!=c[b] for a,b in edges) and (not restricted or all(c[n]==prior[n] for n in nodes if n not in active)):
                        costs.append(sum(c[n]!=prior[n] for n in nodes))
                expected=min(costs) if costs else None
                self.assertEqual(exact_minimum(f,restricted)[0],expected)

    def test_counterbalanced_fixed_schedule_and_exact_prompt_reuse(self):
        self.assertEqual(len(self.plan['schedule']),24)
        self.assertEqual([x['case'] for x in self.plan['schedule'][::4]],['hard-24','hard-36','hard-48','hard-48','hard-36','hard-24'])
        for start in range(0,24,4):
            items=self.plan['schedule'][start:start+4]
            self.assertEqual([x['arm'] for x in items[:2]],list(h.ARMS if start<12 else reversed(h.ARMS)))
        for case in self.plan['cases']:
            for arm in h.ARMS:
                expected=solver_invocation(case,arm)
                for slot,item in enumerate(self.plan['schedule']):
                    if item['case']==case['id'] and item['arm']==arm and item['kind']=='solver':
                        self.assertEqual(h.invocation(self.plan,slot,[])[1],expected)
                self.assertNotIn('witnesses',expected['prompt']);self.assertNotIn('minimum_changes',expected['prompt'])
                self.assertNotIn('trial',expected['prompt'])

    def test_real_ledger_all_twenty_four_and_all_six_denominators(self):
        c=client(self.plan);r=h.run_plan(self.plan,c)
        self.assertEqual(r['actual_provider_calls'],24)
        self.assertEqual(len(c.responses.calls),24)
        self.assertTrue(all(call['max_output_tokens']==4096 for call in c.responses.calls))
        for arm in h.ARMS:self.assertEqual(r['summary'][arm],{'planned':6,'attempted':6,'completed':6,'feasible':6,'minimal':6})
        self.assertEqual(h.verify_report(r,self.plan)['status'],'PASS')
        for s in r['stages']:
            if s['kind']=='judge':
                self.assertNotIn('trial',s['invocation']['prompt'])
                self.assertNotIn('gradient_feedback',s['invocation']['prompt'])

    def test_provider_failures_keep_all_planned_denominators_and_skip_judges(self):
        r=h.run_plan(self.plan,FakeClient(*(RuntimeError('secret') for _ in range(12))))
        self.assertEqual(r['actual_provider_calls'],12)
        self.assertEqual(r['collection_status'],'COMPLETE')
        for arm in h.ARMS:self.assertEqual(r['summary'][arm],{'planned':6,'attempted':6,'completed':0,'feasible':0,'minimal':0})
        self.assertEqual(sum(s['status']=='SKIPPED_NO_CANDIDATE' for s in r['stages']),12)
        self.assertEqual(h.verify_report(r,self.plan)['status'],'PASS')

    def test_invalid_answer_disagreement_and_judge_failure_preserved(self):
        r=h.run_plan(self.plan,client(self.plan,{0:'not json',2:'{}'}))
        self.assertEqual(r['actual_provider_calls'],24)
        self.assertEqual(r['summary']['full_repair']['feasible'],5)
        self.assertEqual(r['collection_status'],'COMPLETE')
        raw=json.loads(client(self.plan).responses.outcomes[2].output_text)
        raw['checks']['fixed_A']=False;raw['verdict']='FAIL';raw['violations']=['fixed_A']
        r=h.run_plan(self.plan,client(self.plan,{2:json.dumps(raw)}))
        self.assertFalse(r['judgments']['hard-24/trial-1/full_repair']['agreement'])
        self.assertEqual(r['summary']['full_repair']['minimal'],6)

    def test_model_drift_and_pre_dispatch_failures_stop(self):
        r=h.run_plan(self.plan,client(self.plan,{1:response('{}',model='other-model')}))
        self.assertEqual(r['actual_provider_calls'],2);self.assertEqual(r['collection_status'],'INCOMPLETE')
        c=FakeClient(max_retries=1);r=h.run_plan(self.plan,c)
        self.assertEqual(r['actual_provider_calls'],0);self.assertEqual(h.verify_report(r,self.plan)['status'],'PASS')

    def test_resealed_schedule_grades_and_truncated_reports_rejected(self):
        bad=copy.deepcopy(self.plan);bad['schedule'][0]['arm']='gradient_feedback'
        with self.assertRaises(EBRTError):h.run_plan(reseal(bad),client(self.plan))
        r=h.run_plan(self.plan,client(self.plan));bad=copy.deepcopy(r);bad['summary']['full_repair']['minimal']=0
        with self.assertRaises(EBRTError):h.verify_report(reseal(bad),self.plan)
        bad=copy.deepcopy(r);bad['stages']=bad['stages'][:12]
        with self.assertRaises(EBRTError):h.verify_report(reseal(bad),self.plan)

if __name__=='__main__':unittest.main()
