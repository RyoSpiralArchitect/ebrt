import copy
import socket
import unittest
from unittest.mock import patch

import ebrt_multistart_repair as engine
import ebrt_puct_repair as base
import ebrt_puct_trajectory as frozen
import run_puct_multistart_study as study
from ebrt_core import EBRTError
from test_ebrt_puct_repair import problem
from test_ebrt_puct_trajectory import star, reseal


class MultistartTests(unittest.TestCase):
    def setUp(self):
        guard = patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden'))
        guard.start()
        self.addCleanup(guard.stop)

    def test_shared_operator_preserves_all_frozen_puct_fields(self):
        for graph in (problem(), star(5), problem(edges=(), initial=(0, 0))):
            for arm in ('uniform_puct', 'gradient_puct'):
                for seed in (7, 19):
                    for steps, cap, depth in ((1, 32, 6), (8, 100, 6), (8, 1, 1), (8, 5, 1)):
                        config = base.SearchConfig(seed=seed, max_evaluations=cap, max_depth=depth)
                        old = frozen.search(graph, arm, config, max_steps=steps)
                        new = engine.search(graph, 'puct', arm, config, max_steps=steps)
                        self.assertEqual({k: new[k] for k in old}, old)
                        self.assertEqual(new['starts'], 1)
                        self.assertEqual(new['restart_evaluations'], 0)

    def test_both_strategies_call_identical_continuation_for_same_first_move(self):
        config = base.SearchConfig(max_evaluations=5)
        results = []
        for strategy in ('puct', 'multistart'):
            with patch.object(base, 'action_priors', return_value={(1, 1): 1.0}), \
                 patch.object(engine, 'extend_trajectory', wraps=engine.extend_trajectory) as extend:
                results.append(engine.search(star(), strategy, 'uniform_puct', config))
            self.assertEqual(extend.call_count, 1)
        for key in ('best_seen', 'improvements', 'local_steps', 'local_gradient_calls', 'trajectory_lengths'):
            self.assertEqual(results[0][key], results[1][key])
        self.assertEqual(results[1]['trajectory_lengths'], [4])

    def test_actual_evaluator_counts_roots_restarts_and_mid_segment_stops(self):
        original = base.RepairProblem.assess
        with patch.object(base.RepairProblem, 'assess', autospec=True, side_effect=original) as evaluate:
            result = engine.search(star(), 'multistart', 'uniform_puct',
                                   base.SearchConfig(max_evaluations=7, max_depth=1))
        self.assertEqual(evaluate.call_count, 7)
        self.assertEqual(result['starts'], 4)
        self.assertEqual(result['restart_evaluations'], 3)
        self.assertEqual(result['trajectory_lengths'], [1, 1, 1])
        self.assertEqual(result['episodes'][-1]['depth'], 0)
        self.assertEqual([e['stop_reason'] for e in result['episodes'][:-1]], ['DEPTH_LIMIT'] * 3)
        for cap in (1, 2, 5, 9):
            with patch.object(base.RepairProblem, 'assess', autospec=True, side_effect=original) as evaluate:
                result = engine.search(star(), 'multistart', 'uniform_puct', base.SearchConfig(max_evaluations=cap))
            self.assertEqual(evaluate.call_count, cap)
            self.assertEqual(result['starts'] + sum(result['trajectory_lengths']), cap)
            self.assertTrue(all(n <= 8 for n in result['trajectory_lengths']))

    def test_no_tree_statistics_and_prior_sampling_continues_across_restarts(self):
        config = base.SearchConfig(max_evaluations=51, max_depth=1, seed=7)
        with patch.object(base, 'puct_score', side_effect=AssertionError('no tree statistics')), \
             patch.object(engine, 'TrajectoryEdge', side_effect=AssertionError('no retained tree')):
            result = engine.search(star(4), 'multistart', 'uniform_puct', config)
        actions = {tuple(e['first_action']) for e in result['episodes'] if e['first_action'] is not None}
        self.assertGreater(len(actions), 1)  # Streams are not reset on every start.
        self.assertEqual(result['prior_draws'], len(result['trajectory_lengths']))
        self.assertEqual(result['root_visits'], 0)
        self.assertEqual(result['root_children_evaluated'], 0)
        self.assertEqual(result, engine.search(star(4), 'multistart', 'uniform_puct', config))

    def test_episodes_exclude_all_ancestors_and_every_local_move_improves(self):
        graph = problem()
        original = base.RepairProblem.assess
        with patch.object(base.RepairProblem, 'assess', autospec=True, side_effect=original) as evaluate:
            result = engine.search(graph, 'multistart', 'gradient_puct',
                                   base.SearchConfig(max_evaluations=100, max_depth=6))
        states = [call.args[1] for call in evaluate.call_args_list]
        next_eval, segment_cursor = 1, 0
        for episode in result['episodes']:
            self.assertEqual(episode['start_evaluation'], next_eval)
            path = states[episode['start_evaluation'] - 1:episode['end_evaluation']]
            self.assertEqual(path[0], graph.initial)
            self.assertEqual(len(path), episode['depth'] + 1)
            self.assertEqual(len(path), len(set(path)))
            self.assertLessEqual(episode['depth'], 6)
            lengths = result['trajectory_lengths'][segment_cursor:segment_cursor + episode['segments']]
            cursor = 1
            for length in lengths:
                for step in range(length):
                    self.assertEqual(sum(a != b for a, b in zip(path[cursor - 1], path[cursor])), 1)
                    self.assertEqual(path[cursor][0], 0)
                    if step:
                        self.assertLess(graph.assess(path[cursor])[2], graph.assess(path[cursor - 1])[2])
                    cursor += 1
            self.assertEqual(cursor, len(path))
            segment_cursor += episode['segments']
            next_eval = episode['end_evaluation'] + 1
        self.assertEqual(next_eval, result['evaluations'] + 1)
        self.assertEqual(segment_cursor, len(result['trajectory_lengths']))
        self.assertGreater(result['local_cycle_actions_rejected'], 0)

    def test_no_acyclic_action_restarts_but_no_legal_action_stops(self):
        result = engine.search(problem(edges=(), initial=(0, 0)), 'multistart', 'uniform_puct',
                               base.SearchConfig(max_evaluations=20, max_depth=10))
        self.assertTrue(any(e['stop_reason'] == 'NO_ACYCLIC_ACTIONS' for e in result['episodes']))
        self.assertEqual(result['evaluations'], 20)
        impossible = problem(edges=((0, 1),), initial=(0, 0), fixed=((0, 0), (1, 0)))
        result = engine.search(impossible, 'multistart', 'gradient_puct')
        self.assertEqual(result['stop_reason'], 'NO_LEGAL_ACTIONS')
        self.assertIsNone(result['candidate'])
        self.assertEqual(result['evaluations'], 1)

    def test_valid_incumbent_survives_restart_to_invalid_original(self):
        graph = problem()
        config = base.SearchConfig(max_evaluations=4, max_depth=2)
        result = engine.search(graph, 'multistart', 'uniform_puct', config)
        self.assertEqual(result['starts'], 2)
        self.assertEqual(result['episodes'][-1]['depth'], 0)
        self.assertEqual(result['candidate_edits'], 2)
        self.assertEqual(len(set(result['candidate'].values())), 3)
        self.assertEqual(graph.initial, (0, 0, 0))
        self.assertEqual(result['best_seen']['conflicts'], 0)

    def test_gradient_accounting_and_invalid_strategy(self):
        for prior in ('uniform_puct', 'gradient_puct'):
            result = engine.search(star(), 'multistart', prior, base.SearchConfig(max_evaluations=30))
            self.assertGreater(result['local_gradient_calls'], 0)
            self.assertEqual(result['gradient_calls'], result['prior_gradient_calls'] + result['local_gradient_calls'])
            self.assertEqual(result['local_steps'], sum(n - 1 for n in result['trajectory_lengths']))
            if prior == 'uniform_puct':
                self.assertEqual(result['prior_gradient_calls'], 0)
            else:
                self.assertGreater(result['prior_gradient_calls'], 0)
        with self.assertRaises(ValueError):
            engine.search(problem(), 'unknown', 'uniform_puct')
        with self.assertRaises(ValueError):
            engine.search(problem(), 'multistart', 'uniform_puct', max_steps=9)

    def test_fixed_schedule_and_plan_tampering_before_dispatch(self):
        plan = study.build_plan()
        self.assertEqual(len(plan['schedule']), 36)
        self.assertEqual(plan['maximum_search_state_evaluations'], 73728)
        self.assertEqual(plan['max_provider_attempts'], 0)
        self.assertEqual(plan['baseline_plan_fingerprint_sha256'], study.baseline.build_plan()['fingerprint_sha256'])
        for arm, (strategy, prior) in study.ARMS.items():
            selected = [r for r in plan['schedule'] if r['arm'] == arm]
            self.assertEqual(len(selected), 9)
            self.assertTrue(all(r['strategy'] == strategy and r['prior_arm'] == prior and r['max_steps'] == 8 for r in selected))
        for offset in range(0, 36, 4):
            group = plan['schedule'][offset:offset + 4]
            self.assertTrue(all(row['config'] == group[0]['config'] for row in group))
        bad = copy.deepcopy(plan)
        bad['restart_policy'] = 'FREE_ORACLE_STARTS'
        with patch.object(study, 'search') as dispatch, self.assertRaises(EBRTError):
            study.run_plan(reseal(bad))
        dispatch.assert_not_called()

    def test_tiny_fixture_collection_replay_and_tampering(self):
        fixture = {'id': 'tiny', 'nodes': list('ABC'), 'prior': dict.fromkeys('ABC', 0),
                   'edges': [['A', 'B'], ['A', 'C'], ['B', 'C']],
                   'added': [['A', 'B'], ['A', 'C'], ['B', 'C']], 'minimum_changes': 2}
        def config(**kwargs):
            return base.SearchConfig(**dict(kwargs, max_evaluations=32))
        with patch.object(study, 'load_fixtures', return_value=[fixture]), patch.object(study, 'SearchConfig', side_effect=config):
            plan = study.build_plan()
            report = study.run_plan(plan)
            self.assertEqual(report['actual_provider_calls'], 0)
            self.assertEqual(len(report['records']), 12)
            self.assertTrue(all(s['planned'] == s['completed'] == 3 for s in report['summary'].values()))
            self.assertEqual(study.verify_report(report, plan)['checked_runs'], 12)
            for corruption in ('truncated', 'starts', 'grade', 'summary'):
                bad = copy.deepcopy(report)
                if corruption == 'truncated':
                    bad['records'].pop()
                elif corruption == 'starts':
                    bad['records'][2]['result']['starts'] += 1
                elif corruption == 'grade':
                    bad['records'][0]['grade']['minimal'] = not bad['records'][0]['grade']['minimal']
                else:
                    bad['summary']['multistart_uniform']['evaluations'] += 1
                with self.assertRaises(EBRTError):
                    study.verify_report(reseal(bad), plan)


if __name__ == '__main__':
    unittest.main()
