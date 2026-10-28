"""Frozen offline allocation comparison: PUCT versus stochastic multistart."""
import argparse
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import time

from ebrt_core import _seal, _sealed_snapshot, _canonical_bytes
from ebrt_hosted import _open_output
from ebrt_puct_repair import SearchConfig
from ebrt_multistart_repair import search
import run_puct_trajectory_study as baseline

ARMS = {
    'puct_uniform': ('puct', 'uniform_puct'),
    'puct_gradient': ('puct', 'gradient_puct'),
    'multistart_uniform': ('multistart', 'uniform_puct'),
    'multistart_gradient': ('multistart', 'gradient_puct'),
}
require = baseline.require


def load_fixtures():
    return baseline.load_fixtures()


def build_plan():
    old = baseline.build_plan()
    schedule = []
    for fixture in load_fixtures():
        for index, seed in enumerate(baseline.baseline.SEEDS):
            for arm in (tuple(ARMS) if index % 2 == 0 else tuple(reversed(ARMS))):
                strategy, prior = ARMS[arm]
                config = SearchConfig(seed=seed, max_depth=2 * len(fixture['nodes']))
                schedule.append({'case': fixture['id'], 'arm': arm, 'strategy': strategy,
                                 'prior_arm': prior, 'max_steps': 8, 'config': asdict(config)})
    sources = dict(old['source_sha256'])
    for name in ('ebrt_multistart_repair.py', 'run_puct_multistart_study.py'):
        sources[name] = hashlib.sha256((baseline.baseline.ROOT / name).read_bytes()).hexdigest()
    return _seal({
        'schema_version': 'ebrt-puct-multistart-plan-v1',
        'baseline_plan_fingerprint_sha256': old['fingerprint_sha256'],
        'schedule': schedule, 'torch_version': old['torch_version'], 'python_version': old['python_version'],
        'max_provider_attempts': 0,
        'maximum_search_state_evaluations': sum(s['config']['max_evaluations'] for s in schedule),
        'restart_policy': 'ORIGINAL_STATE_CHARGED_AT_DEPTH_LIMIT_OR_NO_ACYCLIC_ACTIONS',
        'action_policy': 'SAMPLE_RENORMALIZED_PRIOR_WITHOUT_VISIT_STATISTICS',
        'source_sha256': sources,
    })


def validate_plan(plan):
    plan = _sealed_snapshot(plan, 'MULTISTART_PLAN')
    require(_canonical_bytes(plan) == _canonical_bytes(build_plan()), 'MULTISTART_PLAN_MISMATCH')
    return plan


def make_report(plan, records):
    summary = {}
    for arm in ARMS:
        selected = [r for r in records if r['arm'] == arm]
        summary[arm] = {'planned': sum(s['arm'] == arm for s in plan['schedule']),
                        'completed': len(selected),
                        'feasible': sum(r['grade']['feasible'] for r in selected),
                        'minimal': sum(r['grade']['minimal'] for r in selected),
                        **{field: sum(r['result'][field] for r in selected) for field in
                           ('evaluations', 'gradient_calls', 'prior_gradient_calls', 'local_gradient_calls',
                            'local_steps', 'starts', 'restart_evaluations', 'prior_draws')},
                        'search_seconds': sum(r['search_seconds'] for r in selected)}
    return _seal({'schema_version': 'ebrt-puct-multistart-result-v1',
                  'plan_fingerprint_sha256': plan['fingerprint_sha256'],
                  'actual_provider_calls': 0, 'records': records, 'summary': summary})


def run_plan(plan, progress=None):
    plan = validate_plan(plan)
    fixtures = {f['id']: f for f in load_fixtures()}
    records = []
    for slot, item in enumerate(plan['schedule']):
        fixture = fixtures[item['case']]
        problem = baseline.baseline.public_problem(fixture)
        started = time.perf_counter()
        result = search(problem, item['strategy'], item['prior_arm'],
                        SearchConfig(**item['config']), max_steps=item['max_steps'])
        elapsed = time.perf_counter() - started
        assessment, oracle_states = baseline.grade(fixture, result)
        records.append({'slot': slot, **item, 'result': result, 'grade': assessment,
                        'search_seconds': elapsed, 'post_run_oracle_states': oracle_states})
        if progress:
            progress({'slot': slot, 'case': item['case'], 'arm': item['arm'],
                      'seed': item['config']['seed'], **assessment,
                      'evaluations': result['evaluations'], 'starts': result['starts'],
                      'conflicts': result['best_seen']['conflicts']})
    return make_report(plan, records)


def verify_report(report, plan):
    plan = validate_plan(plan)
    report = _sealed_snapshot(report, 'MULTISTART_REPORT')
    fixtures = {f['id']: f for f in load_fixtures()}
    require(len(report['records']) == len(plan['schedule']), 'MULTISTART_RECORD_COUNT')
    replayed = 0
    for slot, (record, item) in enumerate(zip(report['records'], plan['schedule'])):
        require(record['slot'] == slot and all(record[k] == v for k, v in item.items()), 'MULTISTART_SLOT_MISMATCH')
        require(set(record) == {'slot', *item, 'result', 'grade', 'search_seconds', 'post_run_oracle_states'},
                'MULTISTART_RECORD_FIELDS')
        elapsed = record['search_seconds']
        require(type(elapsed) in (int, float) and math.isfinite(elapsed) and elapsed >= 0, 'MULTISTART_TIME_INVALID')
        fixture = fixtures[item['case']]
        result = search(baseline.baseline.public_problem(fixture), item['strategy'], item['prior_arm'],
                        SearchConfig(**item['config']), max_steps=item['max_steps'])
        require(_canonical_bytes(record['result']) == _canonical_bytes(result), 'MULTISTART_REPLAY_MISMATCH')
        assessment, states = baseline.grade(fixture, result)
        require(record['grade'] == assessment and record['post_run_oracle_states'] == states, 'MULTISTART_GRADE_MISMATCH')
        replayed += result['evaluations']
    require(_canonical_bytes(report) == _canonical_bytes(make_report(plan, report['records'])), 'MULTISTART_REPORT_MISMATCH')
    return _seal({'status': 'PASS', 'checked_runs': len(report['records']),
                  'replayed_search_state_evaluations': replayed, 'actual_provider_calls': 0,
                  'plan_fingerprint_sha256': plan['fingerprint_sha256'],
                  'report_fingerprint_sha256': report['fingerprint_sha256'],
                  'meaning': 'Deterministic replay and grading; timing is not replayed. Diagnostic work, not extra trials.'})


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
        print(json.dumps({key: result[key] for key in ('fingerprint_sha256', 'status') if key in result}))


if __name__ == '__main__':
    main()
