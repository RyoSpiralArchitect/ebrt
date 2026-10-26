"""Paired failure-isolated follow-up; unchanged solver, cases, and token ceilings."""
import argparse
import hashlib
import json
from pathlib import Path
import ebrt_repair_scaling as study
from ebrt_core import EBRTError, _seal, _sealed_snapshot, _canonical_bytes
from ebrt_hosted import _open_output
from ebrt_reinspection_hosted import _hosted_config, PRE_DISPATCH_ERRORS
from ebrt_dependency_hosted import _execute_stage
from ebrt_support_eval import _check_provider
from ebrt_coloring_repair import ARMS, require, solver_invocation


def build_plan(model='gpt-5.6-sol'):
    return _seal({'schema_version':'ebrt-cascade-pairs-plan-v1','study':study.build_plan(model),
        'policy':'CONTINUE_INDEPENDENT_ARMS_ON_PROVIDER_OR_JUDGE_ERROR_SKIP_JUDGE_WITHOUT_RAW',
        'max_provider_attempts':12,
        'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})


def validate_plan(plan):
    plan=_sealed_snapshot(plan,'PAIRS_PLAN')
    expected=build_plan(plan['study']['solver_config']['model'])
    require(_canonical_bytes(plan)==_canonical_bytes(expected),'PAIRS_PLAN_MISMATCH')
    return plan


def invocation(plan,slot,records):
    case=plan['study']['cases'][slot//4];phase=slot%4
    if phase<2: inv=solver_invocation(case,ARMS[phase])
    else:
        record=next(r for r in records if r['slot']==slot-2)
        inv=study.judge_invocation(case,record['raw_text'])
    config=_hosted_config(plan['study']['solver_config' if phase<2 else 'judge_config'])
    return case,phase,inv,config


def derive(plan,records,pre_dispatch=None,partial=False):
    require(type(records) is list and len(records)<=12,'PAIRS_RECORD_COUNT')
    stages=[]; grades={}; judgments={}; solver_status={}; model=None; cursor=0; pending=None; fatal=False
    for slot in range(12):
        case=plan['study']['cases'][slot//4];phase=slot%4;key=case['id']+'/'+ARMS[phase%2]
        if phase>=2 and solver_status[key]!='CANDIDATE_RECORDED':
            stages.append({'slot':slot,'case':case['id'],'arm':ARMS[phase%2],
                           'status':'SKIPPED_NO_CANDIDATE','provider_attempt':False})
            continue
        if cursor==len(records):pending=slot;break
        record=records[cursor]
        require(record['slot']==slot,'PAIRS_SLOT_MISMATCH')
        case,phase,inv,config=invocation(plan,slot,records)
        receipt,raw=record['provider_receipt'],record['raw_text'];_check_provider(receipt,0,inv,config)
        status,error,parsed='PROVIDER_ERROR',receipt['error_code'],None
        if receipt['status']=='COMPLETED':
            require(type(raw) is str,'PAIRS_RAW_MISSING')
            if model is not None and model!=receipt['returned_model']:
                status,error='MODEL_MISMATCH','PAIRS_MODEL_MISMATCH';fatal=True
            else:
                model=receipt['returned_model']
                if phase<2:
                    parsed=study.assess(raw,case);grades[key]=parsed;status='CANDIDATE_RECORDED'
                else:
                    try:
                        parsed=study.parse_judge(raw,case);status='JUDGED'
                        judgments[key]={'judgment':parsed,'agreement':parsed['checks']==grades[key]['checks']}
                    except EBRTError as exc:status,error='JUDGE_FORMAT_ERROR',str(exc)
        else:require(raw is None,'PAIRS_ERROR_RAW_PRESENT')
        if phase<2:solver_status[key]=status
        stages.append({**record,'case':case['id'],'arm':ARMS[phase%2],'kind':'solver' if phase<2 else 'judge',
            'provider_attempt':True,'invocation':inv,'generation_config':config.to_dict(),
            'status':status,'error_code':error,'parsed':parsed})
        cursor+=1
        if fatal:break
    require(cursor==len(records),'PAIRS_EXTRA_RECORDS')
    if pre_dispatch is not None:
        require(not fatal and pending is not None and type(pre_dispatch) is dict
                and set(pre_dispatch)=={'slot','error_code'} and pre_dispatch['slot']==pending
                and pre_dispatch['error_code'] in PRE_DISPATCH_ERRORS,'PAIRS_PRE_DISPATCH_INVALID')
    if not partial:require(pending is None or pre_dispatch is not None,'PAIRS_TRUNCATED_REPORT')
    complete=len(stages)==12 and pre_dispatch is None and not fatal
    return _seal({'schema_version':'ebrt-cascade-pairs-result-v1','plan_fingerprint_sha256':plan['fingerprint_sha256'],
        'stages':stages,'assessments':grades,'judgments':judgments,'solver_status':solver_status,
        'pre_dispatch_failure':pre_dispatch,'actual_provider_calls':len(records),'pending_slot':pending,
        'collection_status':'COMPLETE' if complete else 'INCOMPLETE',
        'execution_status':'PASS' if complete and all(s['status'] in ('CANDIDATE_RECORDED','JUDGED') for s in stages) else 'FAIL',
        'returned_model':model,'fatal_model_mismatch':fatal,
        'interpretation':'Provider failures are outcomes, not mathematical errors; skipped judges spend no attempt. Descriptive paired comparison only.'})


def verify_report(report,plan):
    plan=validate_plan(plan);report=_sealed_snapshot(report,'PAIRS_REPORT')
    records=[{k:s[k] for k in ('slot','provider_receipt','raw_text')} for s in report['stages'] if s['provider_attempt']]
    expected=derive(plan,records,report['pre_dispatch_failure'])
    require(_canonical_bytes(expected)==_canonical_bytes(report),'PAIRS_REPORT_MISMATCH')
    return _seal({'status':'PASS','checked_attempts':len(records),'report_fingerprint_sha256':report['fingerprint_sha256'],
                  'meaning':'Internal consistency only, not provider authenticity.'})


def run_plan(plan,client=None):
    plan=validate_plan(plan);records=[];pre=None
    while True:
        progress=derive(plan,records,partial=True)
        slot=progress['pending_slot']
        if slot is None or progress['fatal_model_mismatch']:break
        _,_,inv,config=invocation(plan,slot,records)
        record,client,error=_execute_stage(inv,config.to_dict(),client)
        if error:pre={'slot':slot,'error_code':error};break
        records.append({'slot':slot,**record})
    report=derive(plan,records,pre);verify_report(report,plan);return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('plan','run','verify'))
    parser.add_argument('--plan');parser.add_argument('--report');parser.add_argument('--output',required=True)
    args=parser.parse_args();load=lambda p:json.loads(Path(p).read_text())
    with _open_output(args.output) as output:
        if args.command=='plan':result=build_plan()
        elif args.command=='run':result=run_plan(load(args.plan))
        else:result=verify_report(load(args.report),load(args.plan))
        json.dump(result,output,indent=2,sort_keys=True);output.write('\n')
        print(json.dumps({k:result[k] for k in ('fingerprint_sha256','actual_provider_calls','collection_status','execution_status','status') if k in result}))
    return 0 if result.get('collection_status','COMPLETE')=='COMPLETE' else 1

if __name__=='__main__':raise SystemExit(main())
