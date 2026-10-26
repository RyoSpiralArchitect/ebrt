"""Fixed 4096-token solver follow-up using the unchanged paired repair evaluator."""
import argparse
import hashlib
import json
from pathlib import Path

import ebrt_repair_scaling_pairs as pairs
from ebrt_core import EBRTError, _canonical_bytes, _seal, _sealed_snapshot
from ebrt_coloring_repair import require
from ebrt_dependency_hosted import _execute_stage
from ebrt_hosted import _open_output

SOLVER_OUTPUT_TOKENS = 4096


def build_plan(model='gpt-5.6-sol'):
    baseline = pairs.build_plan(model)
    study = dict(baseline['study'])
    study.pop('fingerprint_sha256')
    study['schema_version'] = 'ebrt-cascade-budget-study-v1'
    study['solver_config'] = dict(study['solver_config'], max_output_tokens=SOLVER_OUTPUT_TOKENS)
    return _seal({
        'schema_version': 'ebrt-cascade-budget-plan-v1',
        'baseline_plan_fingerprint_sha256': baseline['fingerprint_sha256'],
        'study': _seal(study),
        'policy': baseline['policy'],
        'max_provider_attempts': baseline['max_provider_attempts'],
        'paired_runner_sha256': baseline['runner_sha256'],
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'changed_generation_fields': {'solver.max_output_tokens': [512, SOLVER_OUTPUT_TOKENS]},
    })


def validate_plan(plan):
    plan = _sealed_snapshot(plan, 'BUDGET_PLAN')
    try:
        expected = build_plan(plan['study']['solver_config']['model'])
    except (KeyError, TypeError) as exc:
        raise EBRTError('BUDGET_PLAN_INVALID') from exc
    require(_canonical_bytes(plan) == _canonical_bytes(expected), 'BUDGET_PLAN_MISMATCH')
    return plan


def verify_report(report, plan):
    plan = validate_plan(plan)
    report = _sealed_snapshot(report, 'BUDGET_REPORT')
    try:
        records = [
            {key: stage[key] for key in ('slot', 'provider_receipt', 'raw_text')}
            for stage in report['stages'] if stage['provider_attempt']
        ]
        expected = pairs.derive(plan, records, report['pre_dispatch_failure'])
    except (KeyError, TypeError, IndexError) as exc:
        raise EBRTError('BUDGET_REPORT_INVALID') from exc
    require(_canonical_bytes(expected) == _canonical_bytes(report), 'BUDGET_REPORT_MISMATCH')
    return _seal({
        'status': 'PASS', 'checked_attempts': len(records),
        'plan_fingerprint_sha256': plan['fingerprint_sha256'],
        'report_fingerprint_sha256': report['fingerprint_sha256'],
        'meaning': 'Internal consistency only, not provider authenticity.',
    })


def run_plan(plan, client=None, *, progress=None):
    plan = validate_plan(plan)
    records, pre_dispatch = [], None
    while True:
        derived = pairs.derive(plan, records, partial=True)
        slot = derived['pending_slot']
        if slot is None or derived['fatal_model_mismatch']:
            break
        _, _, invocation, config = pairs.invocation(plan, slot, records)
        record, client, error = _execute_stage(invocation, config.to_dict(), client)
        if error:
            pre_dispatch = {'slot': slot, 'error_code': error}
            break
        records.append({'slot': slot, **record})
        if progress is not None:
            # Public stage status only; no candidate or provider identifiers.
            current = pairs.derive(plan, records, partial=True)
            stage = next(s for s in current['stages'] if s['slot'] == slot)
            progress({'slot': slot, 'case': stage['case'], 'arm': stage['arm'],
                      'kind': stage['kind'], 'status': stage['status']})
    report = pairs.derive(plan, records, pre_dispatch)
    verify_report(report, plan)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('plan', 'run', 'verify'))
    parser.add_argument('--model', default='gpt-5.6-sol')
    parser.add_argument('--plan')
    parser.add_argument('--report')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(Path(path).read_text())
    with _open_output(args.output) as output:
        if args.command == 'plan':
            result = build_plan(args.model)
        elif args.command == 'run':
            result = run_plan(load(args.plan), progress=lambda value: print(json.dumps(value), flush=True))
        else:
            result = verify_report(load(args.report), load(args.plan))
        json.dump(result, output, indent=2, sort_keys=True)
        output.write('\n')
        print(json.dumps({key: result[key] for key in (
            'fingerprint_sha256', 'actual_provider_calls', 'collection_status',
            'execution_status', 'status') if key in result}))
    return 0 if result.get('collection_status', 'COMPLETE') == 'COMPLETE' else 1


if __name__ == '__main__':
    raise SystemExit(main())
