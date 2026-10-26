"""Fixed 180-second follow-up to the unchanged hard repair replication."""
import argparse
import hashlib
import json
from pathlib import Path

import ebrt_hard_repair as hard
from ebrt_coloring_repair import require
from ebrt_core import EBRTError, _canonical_bytes, _seal, _sealed_snapshot
from ebrt_dependency_hosted import _execute_stage
from ebrt_hosted import _open_output

TIMEOUT_SECONDS = 180.0


def build_plan(model='gpt-5.6-sol'):
    baseline = hard.build_plan(model)
    plan = dict(baseline)
    plan.pop('fingerprint_sha256')
    plan.update(
        schema_version='ebrt-hard-timeout-plan-v1',
        baseline_plan_fingerprint_sha256=baseline['fingerprint_sha256'],
        config=dict(baseline['config'], timeout_seconds=TIMEOUT_SECONDS),
        runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        changed_generation_fields={
            'solver.timeout_seconds': [60.0, TIMEOUT_SECONDS],
            'judge.timeout_seconds': [60.0, TIMEOUT_SECONDS],
        },
    )
    return _seal(plan)


def validate_plan(plan):
    plan = _sealed_snapshot(plan, 'HARD_TIMEOUT_PLAN')
    try:
        expected = build_plan(plan['config']['model'])
    except (KeyError, TypeError) as exc:
        raise EBRTError('HARD_TIMEOUT_PLAN_INVALID') from exc
    require(_canonical_bytes(plan) == _canonical_bytes(expected), 'HARD_TIMEOUT_PLAN_MISMATCH')
    return plan


def verify_report(report, plan):
    plan = validate_plan(plan)
    report = _sealed_snapshot(report, 'HARD_TIMEOUT_REPORT')
    try:
        records = [
            {key: stage[key] for key in ('slot', 'provider_receipt', 'raw_text')}
            for stage in report['stages'] if stage['provider_attempt']
        ]
        expected = hard.derive(plan, records, report['pre_dispatch_failure'])
    except (KeyError, TypeError, IndexError) as exc:
        raise EBRTError('HARD_TIMEOUT_REPORT_INVALID') from exc
    require(_canonical_bytes(report) == _canonical_bytes(expected), 'HARD_TIMEOUT_REPORT_MISMATCH')
    return _seal({
        'status': 'PASS', 'checked_attempts': len(records),
        'plan_fingerprint_sha256': plan['fingerprint_sha256'],
        'report_fingerprint_sha256': report['fingerprint_sha256'],
        'meaning': 'Internal consistency only, not provider authenticity.',
    })


def run_plan(plan, client=None, *, progress=None):
    plan = validate_plan(plan)
    records, pre = [], None
    while True:
        current = hard.derive(plan, records, partial=True)
        slot = current['pending_slot']
        if slot is None or current['fatal_model_mismatch']:
            break
        _, invocation, config = hard.invocation(plan, slot, records)
        record, client, error = _execute_stage(invocation, config.to_dict(), client)
        if error:
            pre = {'slot': slot, 'error_code': error}
            break
        records.append({'slot': slot, **record})
        if progress is not None:
            stage = next(s for s in hard.derive(plan, records, partial=True)['stages'] if s['slot'] == slot)
            progress({key: stage[key] for key in ('slot', 'trial', 'case', 'arm', 'kind', 'status')})
    report = hard.derive(plan, records, pre)
    verify_report(report, plan)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('plan', 'run', 'verify'))
    parser.add_argument('--plan')
    parser.add_argument('--report')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(Path(path).read_text())
    with _open_output(args.output) as output:
        if args.command == 'plan':
            result = build_plan()
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
