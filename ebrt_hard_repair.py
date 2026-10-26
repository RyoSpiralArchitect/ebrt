"""Two counterbalanced trials on three fixed hard repair cases; at most 24 calls."""
import argparse
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import torch

import ebrt_repair_scaling as study
from ebrt_coloring_repair import ARMS, backward_feedback, solver_invocation, require
from ebrt_core import EBRTError, _seal, _sealed_snapshot, _canonical_bytes
from ebrt_hard_oracle import exact_minimum
from ebrt_hosted import HostedConfig, _open_output
from ebrt_dependency_hosted import _execute_stage
from ebrt_reinspection_hosted import _hosted_config, PRE_DISPATCH_ERRORS
from ebrt_support_eval import _check_provider

ROOT = Path(__file__).resolve().parent
FIXTURE = 'fixtures/hard_repair_cases.json'


@lru_cache(maxsize=2)
def checked_cases(raw):
    result=[]
    for f in json.loads(raw):
        optimum,visited=exact_minimum(f)
        restricted,_=exact_minimum(f,restricted=True)
        require(optimum==f['minimum_changes'] and visited==f['search_states'], 'HARD_ORACLE_MISMATCH')
        require(restricted==f['restricted_minimum'] and (restricted is None or restricted>optimum), 'HARD_CASCADE_MISMATCH')
        p={'schema_version':'ebrt-hard-coloring-v1','nodes':f['nodes'],'palette':study.PALETTE,
           'fixed_colors':{'A':'RED'},'edges':f['edges'],
           'color_usage':'AT_MOST_THREE_PALETTE_COLORS_NOT_ALL_REQUIRED'}
        prior={n:study.PALETTE[c] for n,c in f['prior'].items()}
        require(f['added']==[e for e in p['edges'] if prior[e[0]]==prior[e[1]]], 'HARD_PRIOR_INVALID')
        require(len(study.checks({},p))==3+len(p['edges']), 'HARD_EDGE_KEY_COLLISION')
        require(len(f['witnesses'])==2 and f['witnesses'][0]!=f['witnesses'][1], 'HARD_NONUNIQUE_INVALID')
        for witness in f['witnesses']:
            colors={n:study.PALETTE[c] for n,c in witness.items()}
            require(all(study.checks(colors,p).values()) and sum(colors[n]!=prior[n] for n in prior)==optimum, 'HARD_WITNESS_INVALID')
        result.append({'id':f['id'],'problem':p,'prior_colors':prior,'added_edges':f['added'],
            'feedback':backward_feedback(p,prior),'oracle':{'minimum_changes':optimum}})
    return result


def build_plan(model='gpt-5.6-sol'):
    cases=json.loads(json.dumps(checked_cases((ROOT/FIXTURE).read_text())))
    schedule=[]
    for trial in range(2):
        for case in (cases if trial==0 else list(reversed(cases))):
            arms=ARMS if trial==0 else tuple(reversed(ARMS))
            for kind in ('solver','judge'):
                for arm in arms:
                    schedule.append({'trial':trial+1,'case':case['id'],'arm':arm,'kind':kind,
                                     'key':f"{case['id']}/trial-{trial+1}/{arm}"})
    return _seal({'schema_version':'ebrt-hard-repair-plan-v1','cases':cases,'schedule':schedule,
        'config':HostedConfig(model,max_output_tokens=4096).to_dict(),'max_provider_attempts':24,
        'torch_version':str(torch.__version__),
        'source_sha256':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in
                        (*study.SOURCES,'ebrt_repair_scaling.py','ebrt_hard_oracle.py','ebrt_hard_repair.py',FIXTURE)}})


def validate_plan(plan):
    plan=_sealed_snapshot(plan,'HARD_PLAN')
    try:expected=build_plan(plan['config']['model'])
    except (KeyError,TypeError) as exc:raise EBRTError('HARD_PLAN_INVALID') from exc
    require(_canonical_bytes(plan)==_canonical_bytes(expected),'HARD_PLAN_MISMATCH')
    return plan


def invocation(plan,slot,records):
    item=plan['schedule'][slot]
    case=next(c for c in plan['cases'] if c['id']==item['case'])
    if item['kind']=='solver':inv=solver_invocation(case,item['arm'])
    else:
        previous=next(r for r in records if plan['schedule'][r['slot']]['key']==item['key']
                      and plan['schedule'][r['slot']]['kind']=='solver')
        inv=study.judge_invocation(case,previous['raw_text'])
    return case,inv,_hosted_config(plan['config'])


def derive(plan,records,pre=None,partial=False):
    require(type(records) is list and len(records)<=24,'HARD_CALL_COUNT')
    stages=[];assessments={};judgments={};solver_status={};model=None;cursor=0;pending=None;fatal=False
    for slot,item in enumerate(plan['schedule']):
        key=item['key']
        if item['kind']=='judge' and solver_status[key]!='CANDIDATE_RECORDED':
            stages.append({'slot':slot,**item,'status':'SKIPPED_NO_CANDIDATE','provider_attempt':False});continue
        if cursor==len(records):pending=slot;break
        record=records[cursor];require(record['slot']==slot,'HARD_SLOT_MISMATCH')
        case,inv,config=invocation(plan,slot,records)
        receipt,raw=record['provider_receipt'],record['raw_text'];_check_provider(receipt,0,inv,config)
        status,error,parsed='PROVIDER_ERROR',receipt['error_code'],None
        if receipt['status']=='COMPLETED':
            require(type(raw) is str,'HARD_RAW_MISSING')
            if model is not None and model!=receipt['returned_model']:
                status,error='MODEL_MISMATCH','HARD_MODEL_MISMATCH';fatal=True
            else:
                model=receipt['returned_model']
                if item['kind']=='solver':
                    parsed=study.assess(raw,case);assessments[key]=parsed;status='CANDIDATE_RECORDED'
                else:
                    try:
                        parsed=study.parse_judge(raw,case);status='JUDGED'
                        judgments[key]={'judgment':parsed,'agreement':parsed['checks']==assessments[key]['checks']}
                    except EBRTError as exc:status,error='JUDGE_FORMAT_ERROR',str(exc)
        else:require(raw is None,'HARD_ERROR_RAW_PRESENT')
        if item['kind']=='solver':solver_status[key]=status
        stages.append({**record,**item,'provider_attempt':True,'invocation':inv,'generation_config':config.to_dict(),
                       'status':status,'error_code':error,'parsed':parsed})
        cursor+=1
        if fatal:break
    require(cursor==len(records),'HARD_EXTRA_RECORDS')
    if pre is not None:
        require(not fatal and pending is not None and type(pre) is dict and set(pre)=={'slot','error_code'}
                and pre['slot']==pending and pre['error_code'] in PRE_DISPATCH_ERRORS,'HARD_PRE_DISPATCH_INVALID')
    if not partial:require(pending is None or pre is not None,'HARD_TRUNCATED_REPORT')
    complete=len(stages)==24 and not fatal and pre is None
    summary={}
    for arm in ARMS:
        keys=[s['key'] for s in plan['schedule'] if s['kind']=='solver' and s['arm']==arm]
        summary[arm]={'planned':len(keys),'attempted':sum(k in solver_status for k in keys),
                      'completed':sum(k in assessments for k in keys),
                      'feasible':sum(assessments.get(k,{}).get('feasibility')=='PASS' for k in keys),
                      'minimal':sum(assessments.get(k,{}).get('minimal_repair',False) for k in keys)}
    return _seal({'schema_version':'ebrt-hard-repair-result-v1','plan_fingerprint_sha256':plan['fingerprint_sha256'],
        'stages':stages,'assessments':assessments,'judgments':judgments,'solver_status':solver_status,'summary':summary,
        'pre_dispatch_failure':pre,'pending_slot':pending,'fatal_model_mismatch':fatal,'returned_model':model,
        'actual_provider_calls':len(records),'collection_status':'COMPLETE' if complete else 'INCOMPLETE',
        'execution_status':'PASS' if complete and all(s['status'] in ('CANDIDATE_RECORDED','JUDGED') for s in stages) else 'FAIL'})


def verify_report(report,plan):
    plan=validate_plan(plan);report=_sealed_snapshot(report,'HARD_REPORT')
    records=[{k:s[k] for k in ('slot','provider_receipt','raw_text')} for s in report['stages'] if s['provider_attempt']]
    expected=derive(plan,records,report['pre_dispatch_failure'])
    require(_canonical_bytes(report)==_canonical_bytes(expected),'HARD_REPORT_MISMATCH')
    return _seal({'status':'PASS','checked_attempts':len(records),'report_fingerprint_sha256':report['fingerprint_sha256'],
                  'meaning':'Internal consistency only, not provider authenticity.'})


def run_plan(plan,client=None,progress=None):
    plan=validate_plan(plan);records=[];pre=None
    while True:
        current=derive(plan,records,partial=True);slot=current['pending_slot']
        if slot is None or current['fatal_model_mismatch']:break
        _,inv,config=invocation(plan,slot,records)
        record,client,error=_execute_stage(inv,config.to_dict(),client)
        if error:pre={'slot':slot,'error_code':error};break
        records.append({'slot':slot,**record})
        if progress:
            stage=next(s for s in derive(plan,records,partial=True)['stages'] if s['slot']==slot)
            progress({k:stage[k] for k in ('slot','trial','case','arm','kind','status')})
    report=derive(plan,records,pre);verify_report(report,plan);return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('plan','run','verify'));parser.add_argument('--plan');parser.add_argument('--report')
    parser.add_argument('--output',required=True);args=parser.parse_args();load=lambda p:json.loads(Path(p).read_text())
    with _open_output(args.output) as output:
        if args.command=='plan':result=build_plan()
        elif args.command=='run':result=run_plan(load(args.plan),progress=lambda x:print(json.dumps(x),flush=True))
        else:result=verify_report(load(args.report),load(args.plan))
        json.dump(result,output,indent=2,sort_keys=True);output.write('\n')
        print(json.dumps({k:result[k] for k in ('fingerprint_sha256','actual_provider_calls','collection_status','execution_status','status') if k in result}))
    return 0 if result.get('collection_status','COMPLETE')=='COMPLETE' else 1

if __name__=='__main__':raise SystemExit(main())
