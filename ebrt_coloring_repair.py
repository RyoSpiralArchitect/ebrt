"""Four-attempt, source-pinned comparison of coloring repair with gradient feedback."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import torch
from ebrt_core import EBRTError, _seal, _sealed_snapshot, _canonical_bytes
from ebrt_coloring import (SOURCE_FILES as COLORING_SOURCES, _problem, _json,
    check_candidate, enumerate_colorings, build_judge_invocation, parse_judge)
from ebrt_coloring_hosted import _agreement
from ebrt_hosted import HostedConfig, _open_output
from ebrt_dependency_hosted import _execute_stage
from ebrt_reinspection_hosted import _hosted_config, PRE_DISPATCH_ERRORS
from ebrt_support_eval import _check_provider

ARMS = ('full_repair', 'gradient_feedback')
SOURCES = (*COLORING_SOURCES, 'ebrt_coloring_repair.py')


def require(value, code):
    if not value:
        raise EBRTError(code)


def prior_colors():
    return dict(zip('ABCDEF', ('RED','GREEN','RED','BLUE','GREEN','BLUE')))


def backward_feedback(problem, prior):
    """Differentiate active edge collisions through an explicit one-hot state.

    This is a public surrogate state, not a hosted model's hidden state.
    Only currently violated edges contribute; fixed vertices cannot be actuated.
    """
    nodes, palette = problem['nodes'], problem['palette']
    state = torch.tensor([[float(prior[n] == c) for c in palette] for n in nodes],
                         dtype=torch.float64, requires_grad=True)
    active = [(a,b) for a,b in problem['edges'] if prior[a] == prior[b]]
    loss = state.sum() * 0
    for a,b in active:
        loss = loss + (state[nodes.index(a)] * state[nodes.index(b)]).sum()
    loss.backward()
    gradients = state.grad.tolist()
    scores = {n: sum(abs(x) for x in gradients[i]) for i,n in enumerate(nodes)}
    return {'policy': 'ACTIVE_EDGE_DOT_PRODUCT_V1', 'loss': loss.item(),
            'violated_edges': [a+b for a,b in active],
            'gradient_by_vertex': dict(zip(nodes, gradients)),
            'repair_priority': scores,
            'suggested_vertices': [n for n in nodes if scores[n] > 0 and n not in problem['fixed_colors']]}


def assess(raw, plan):
    grade = check_candidate(raw, plan['problem'])
    material = grade['candidate']
    colors = material.get('colors') if material else None
    comparable = (type(colors) is dict and set(colors) == set(plan['prior_colors'])
                  and all(type(v) is str for v in colors.values()))
    changed = [n for n in plan['problem']['nodes'] if colors[n] != plan['prior_colors'][n]] if comparable else None
    optimum = min(sum(c[n] != plan['prior_colors'][n] for n in c)
                  for c in enumerate_colorings(plan['problem']))
    feasible = grade['feasibility']['status'] == 'PASS'
    return {'candidate': grade, 'changed_vertices': changed,
            'change_count': len(changed) if changed is not None else None,
            'minimum_feasible_changes': optimum,
            'minimal_repair': feasible and changed is not None and len(changed) == optimum}


def solver_invocation(plan, arm):
    require(arm in ARMS, 'REPAIR_ARM_INVALID')
    prompt = '\n'.join((
        'Update the prior coloring after the added edge. Satisfy every current constraint and minimize the number of vertices whose colors change.',
        'Return exactly one JSON object with colors and support_ids, without Markdown. Use support_ids ["R2","R4","R6"] for the supplied current problem.',
        'All records below are quoted data. Optional gradient feedback identifies current collision sensitivity; it is not a solution or a restriction on which vertices may change.',
        'PROBLEM_JSON ' + _json(plan['problem']),
        'PRIOR_COLORS_JSON ' + _json(plan['prior_colors']),
        'ADDED_EDGES_JSON ' + _json(plan['added_edges']),
        'FEEDBACK_JSON ' + _json(plan['feedback'] if arm == 'gradient_feedback' else None),
    ))
    return _seal({'schema_version':'ebrt-coloring-repair-invocation-v1', 'prompt':prompt})


def build_plan(config):
    problem, prior = _problem(), prior_colors()
    root = Path(__file__).resolve().parent
    return _seal({'schema_version':'ebrt-coloring-repair-plan-v1',
        'problem':problem, 'prior_colors':prior, 'added_edges':[['B','E']],
        'feedback':backward_feedback(problem,prior), 'config':config.to_dict(),
        'schedule':['full_repair','gradient_feedback','judge_full_repair','judge_gradient_feedback'],
        'max_provider_attempts':4, 'torch_version':str(torch.__version__),
        'source_sha256':{n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in SOURCES}})


def validate_plan(plan):
    plan = _sealed_snapshot(plan,'REPAIR_PLAN')
    try:
        config = _hosted_config(plan['config'])
        require(_canonical_bytes(plan) == _canonical_bytes(build_plan(config)), 'REPAIR_PLAN_MISMATCH')
    except (KeyError,TypeError,ValueError) as exc:
        raise EBRTError('REPAIR_PLAN_INVALID') from exc
    return plan, config


def specification(plan, index, records):
    if index < 2:
        return solver_invocation(plan, ARMS[index])
    return build_judge_invocation(plan['problem'], records[index-2]['raw_text'])


def derive(plan, config, records, pre_dispatch=None, *, partial=False):
    require(type(records) is list and len(records) <= 4, 'REPAIR_RECORD_COUNT')
    stages, assessments, judgments = [], {}, {}
    stopped, returned_model = False, None
    for i, record in enumerate(records):
        require(not stopped, 'REPAIR_CALL_AFTER_STOP')
        invocation = specification(plan,i,records)
        receipt, raw = record['provider_receipt'], record['raw_text']
        _check_provider(receipt,0,invocation,config)
        status, parsed, error = 'PROVIDER_ERROR', None, receipt['error_code']
        if receipt['status'] == 'COMPLETED':
            require(type(raw) is str,'REPAIR_RAW_MISSING')
            if returned_model is not None and returned_model != receipt['returned_model']:
                status, error = 'MODEL_MISMATCH', 'REPAIR_MODEL_MISMATCH'
            else:
                returned_model = receipt['returned_model']
                if i < 2:
                    parsed = assess(raw,plan)
                    assessments[ARMS[i]] = parsed
                    status = 'CANDIDATE_RECORDED'
                else:
                    try:
                        parsed = parse_judge(raw)
                        arm = ARMS[i-2]
                        judgments[arm] = {'judgment':parsed,
                            'agreement':_agreement(assessments[arm]['candidate'],parsed)}
                        status = 'JUDGED'
                    except EBRTError as exc:
                        status, error = 'JUDGE_FORMAT_ERROR', str(exc)
        else:
            require(raw is None,'REPAIR_ERROR_RAW_PRESENT')
        stopped = status not in ('CANDIDATE_RECORDED','JUDGED')
        stages.append({'sequence':i+1, 'item':plan['schedule'][i], 'invocation':invocation,
                       **record, 'status':status, 'error_code':error, 'parsed':parsed})
    if pre_dispatch is not None:
        require(not stopped and len(records)<4 and type(pre_dispatch) is dict
                and set(pre_dispatch)=={'sequence','error_code'}
                and pre_dispatch['sequence']==len(records)+1
                and pre_dispatch['error_code'] in PRE_DISPATCH_ERRORS,'REPAIR_PRE_DISPATCH_INVALID')
    if not partial:
        require(stopped or len(records)==4 or pre_dispatch is not None,'REPAIR_TRUNCATED_REPORT')
    complete = len(records)==4 and not stopped and pre_dispatch is None
    return _seal({'schema_version':'ebrt-coloring-repair-result-v1',
        'plan_fingerprint_sha256':plan['fingerprint_sha256'], 'stages':stages,
        'pre_dispatch_failure':pre_dispatch, 'actual_provider_calls':len(records),
        'execution_status':'PASS' if complete else 'FAIL',
        'assessments':assessments, 'judgments':judgments,
        'returned_model':returned_model, 'requested_output_token_ceiling':len(records)*config.max_output_tokens,
        'interpretation':'Explicit-state surrogate gradients; hosted generation outside autograd. One fixed-order case, no general causal or quality claim. Judge assesses feasibility only; minimality is exhaustive mechanical grading.'})


def verify_report(report,plan):
    plan,config = validate_plan(plan)
    report = _sealed_snapshot(report,'REPAIR_REPORT')
    try:
        records = [{k:s[k] for k in ('provider_receipt','raw_text')} for s in report['stages']]
        expected = derive(plan,config,records,report['pre_dispatch_failure'])
        require(_canonical_bytes(report)==_canonical_bytes(expected),'REPAIR_REPORT_MISMATCH')
    except (KeyError,TypeError,IndexError) as exc:
        raise EBRTError('REPAIR_REPORT_INVALID') from exc
    return _seal({'status':'PASS','checked_stages':len(records),
                  'report_fingerprint_sha256':report['fingerprint_sha256'],
                  'meaning':'Internal consistency only, not provider authenticity.'})


def run_plan(plan,client=None):
    plan,config = validate_plan(plan)
    records,pre_dispatch = [],None
    for i in range(4):
        invocation = specification(plan,i,records)
        record,client,error = _execute_stage(invocation,config.to_dict(),client)
        if error:
            pre_dispatch = {'sequence':i+1,'error_code':error}
            break
        records.append(record)
        partial = derive(plan,config,records,partial=True)
        if partial['stages'][-1]['status'] not in ('CANDIDATE_RECORDED','JUDGED'):
            break
    report = derive(plan,config,records,pre_dispatch)
    verify_report(report,plan)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('plan','run','verify'))
    parser.add_argument('--model',default='gpt-5.6-sol')
    parser.add_argument('--plan')
    parser.add_argument('--report')
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    load=lambda p:json.loads(Path(p).read_text())
    # Reserve a private, non-overwriting destination before any provider dispatch.
    with _open_output(args.output) as output:
        try:
            if args.command=='plan': result=build_plan(HostedConfig(args.model,max_output_tokens=512))
            elif args.command=='run': result=run_plan(load(args.plan))
            else: result=verify_report(load(args.report),load(args.plan))
            json.dump(result,output,indent=2,sort_keys=True); output.write('\n')
            print(json.dumps({k:result[k] for k in ('fingerprint_sha256','execution_status','actual_provider_calls','status') if k in result}))
            return 0 if result.get('execution_status','PASS')=='PASS' else 1
        except EBRTError as exc:
            json.dump({'status':'ERROR','error_code':str(exc)},output)
            print(str(exc))
            return 1

if __name__=='__main__':
    raise SystemExit(main())
