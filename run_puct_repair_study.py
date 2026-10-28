"""Fixed offline PUCT pilot; exact optima are available only to post-run grading."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time

import torch

from ebrt_core import _seal, _sealed_snapshot, _canonical_bytes, EBRTError
from ebrt_hosted import _open_output
from ebrt_hard_oracle import exact_minimum
from ebrt_puct_repair import ARMS, RepairProblem, SearchConfig, search

ROOT = Path(__file__).resolve().parent
FIXTURE = 'fixtures/hard_repair_cases.json'
SEEDS = (7, 19, 43)
PALETTE = ('RED', 'GREEN', 'BLUE')


def public_problem(fixture):
    # This projection is the entire search input: no witnesses, planted target,
    # minimum, restricted optimum, search-state counts, or case-selection seed.
    return RepairProblem.from_public(
        {'nodes': fixture['nodes'], 'palette': PALETTE, 'edges': fixture['edges'],
         'fixed_colors': {'A': 'RED'}},
        {n: PALETTE[c] for n, c in fixture['prior'].items()},
    )


def build_plan():
    fixtures = json.loads((ROOT / FIXTURE).read_text())
    schedule = []
    for fixture in fixtures:
        for index, seed in enumerate(SEEDS):
            for arm in (ARMS if index % 2 == 0 else tuple(reversed(ARMS))):
                config = SearchConfig(seed=seed, max_depth=2 * len(fixture['nodes']))
                schedule.append({'case': fixture['id'], 'arm': arm, 'config': asdict(config)})
    sources = ('ebrt_puct_repair.py', 'run_puct_repair_study.py', 'ebrt_hard_oracle.py',
               'ebrt_core.py', 'ebrt_hosted.py', FIXTURE)
    return _seal({
        'schema_version': 'ebrt-puct-pilot-plan-v1', 'schedule': schedule,
        'torch_version': str(torch.__version__), 'max_provider_attempts': 0,
        'maximum_search_state_evaluations': sum(s['config']['max_evaluations'] for s in schedule),
        'source_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sources},
    })


def validate_plan(plan):
    plan = _sealed_snapshot(plan, 'PUCT_PLAN')
    if _canonical_bytes(plan) != _canonical_bytes(build_plan()):
        raise EBRTError('PUCT_PLAN_MISMATCH')
    return plan


def grade_result(problem, result, optimum):
    seen = tuple(problem.palette.index(result['best_seen']['colors'][n]) for n in problem.nodes)
    conflicts, edits, _ = problem.assess(seen)
    assert (conflicts, edits) == (result['best_seen']['conflicts'], result['best_seen']['edits'])
    feasible = result['candidate'] is not None
    assert feasible == (conflicts == 0)
    if feasible:
        candidate = tuple(problem.palette.index(result['candidate'][n]) for n in problem.nodes)
        assert problem.assess(candidate)[:2] == (0, result['candidate_edits'])
        assert result['candidate_edits'] >= optimum
    return {'feasible': feasible, 'minimal': feasible and result['candidate_edits'] == optimum,
            'minimum_changes': optimum,
            'excess_changes': result['candidate_edits'] - optimum if feasible else None}


def run_plan(plan, progress=None):
    plan = validate_plan(plan)
    fixtures = {f['id']: f for f in json.loads((ROOT / FIXTURE).read_text())}
    records = []
    for slot, item in enumerate(plan['schedule']):
        fixture = fixtures[item['case']]
        problem = public_problem(fixture)
        started = time.perf_counter()
        result = search(problem, item['arm'], SearchConfig(**item['config']))
        elapsed = time.perf_counter() - started
        # Recompute the independent optimum after search; never pass it to search
        # or use it as an early stop, a value target, or a candidate generator.
        optimum, oracle_states = exact_minimum(fixture)
        assert optimum == fixture['minimum_changes']
        grade = grade_result(problem, result, optimum)
        records.append({'slot': slot, **item, 'result': result, 'grade': grade,
                        'search_seconds': elapsed, 'post_run_oracle_states': oracle_states})
        if progress:
            progress({'slot': slot, 'case': item['case'], 'arm': item['arm'],
                      'seed': item['config']['seed'], **grade,
                      'evaluations': result['evaluations'], 'conflicts': result['best_seen']['conflicts']})
    summary = {}
    for arm in ARMS:
        selected = [r for r in records if r['arm'] == arm]
        summary[arm] = {'planned': len(selected),
                        'feasible': sum(r['grade']['feasible'] for r in selected),
                        'minimal': sum(r['grade']['minimal'] for r in selected),
                        'evaluations': sum(r['result']['evaluations'] for r in selected),
                        'gradient_calls': sum(r['result']['gradient_calls'] for r in selected),
                        'search_seconds': sum(r['search_seconds'] for r in selected)}
    return _seal({'schema_version': 'ebrt-puct-pilot-result-v1',
                  'plan_fingerprint_sha256': plan['fingerprint_sha256'],
                  'actual_provider_calls': 0, 'records': records, 'summary': summary})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('plan', 'run'))
    parser.add_argument('--plan')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    with _open_output(args.output) as output:
        if args.command == 'plan':
            result = build_plan()
        else:
            result = run_plan(json.loads(Path(args.plan).read_text()),
                              progress=lambda value: print(json.dumps(value), flush=True))
        json.dump(result, output, indent=2, sort_keys=True)
        output.write('\n')
        print(json.dumps({'fingerprint_sha256': result['fingerprint_sha256']}))


if __name__ == '__main__':
    main()
