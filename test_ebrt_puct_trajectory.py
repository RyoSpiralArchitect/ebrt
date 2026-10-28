import copy
import socket
import unittest
from unittest.mock import patch

import ebrt_puct_repair as base
import ebrt_puct_trajectory as trajectory
import run_puct_trajectory_study as study
from ebrt_core import EBRTError, _seal
from test_ebrt_puct_repair import problem


def star(n=12):
    return base.RepairProblem(tuple(['A'] + [f'N{i}' for i in range(1, n)]), ('R', 'G', 'B'),
                              tuple((0, i) for i in range(1, n)), (0,) * n, ((0, 0),))


def reseal(value):
    result = copy.deepcopy(value)
    result.pop('fingerprint_sha256')
    return _seal(result)


class TrajectoryTests(unittest.TestCase):
    def setUp(self):
        guard = patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden'))
        guard.start()
        self.addCleanup(guard.stop)

    def test_one_step_controls_match_every_original_search_field(self):
        for graph in (problem(), problem(edges=(), initial=(0, 0)), star(5)):
            for arm in ('uniform_puct', 'gradient_puct'):
                for seed in (7, 19, 43):
                    for cap, depth in ((1, 6), (17, 1), (64, 6)):
                        config = base.SearchConfig(max_evaluations=cap, max_depth=depth, seed=seed)
                        old = base.search(graph, arm, config)
                        new = trajectory.search(graph, arm, config, max_steps=1)
                        self.assertEqual({k: new[k] for k in old}, old)
                        self.assertEqual(new['local_gradient_calls'], 0)
                        self.assertEqual(new['local_steps'], 0)

    def test_actual_evaluator_calls_stop_mid_trajectory_without_free_states(self):
        graph = star()
        original = base.RepairProblem.assess
        for cap in (1, 2, 3, 5, 9):
            with patch.object(base.RepairProblem, 'assess', autospec=True, side_effect=original) as evaluate:
                result = trajectory.search(graph, 'uniform_puct', base.SearchConfig(max_evaluations=cap))
            self.assertEqual(evaluate.call_count, cap)
            self.assertEqual(result['evaluations'], cap)
            self.assertEqual(sum(result['trajectory_lengths']) + 1, cap)
            self.assertEqual(result['local_steps'], max(0, cap - 2))
            self.assertEqual(result['max_depth_reached'], cap - 1)
            self.assertTrue(all(length <= 8 for length in result['trajectory_lengths']))

    def test_depth_cap_is_primitive_moves_including_intermediates(self):
        for arm in ('uniform_puct', 'gradient_puct'):
            result = trajectory.search(star(), arm, base.SearchConfig(max_evaluations=50, max_depth=3))
            self.assertEqual(result['max_depth_reached'], 3)
            self.assertLessEqual(result['max_tree_depth_reached'], 3)
            self.assertTrue(all(length <= 3 for length in result['trajectory_lengths']))
            self.assertLessEqual(result['evaluations'], 50)

    def test_every_local_step_recomputes_gradient_and_uniform_prior_also_uses_it(self):
        graph = star()
        original = base.directional_gains
        with patch.object(base, 'directional_gains', side_effect=original) as gradient:
            result = trajectory.search(graph, 'uniform_puct', base.SearchConfig(max_evaluations=5))
        states = [call.args[1] for call in gradient.call_args_list]
        self.assertEqual(len(states), 3)
        self.assertEqual(len(set(states)), 3)
        self.assertNotIn(graph.initial, states)
        self.assertEqual(result['prior_gradient_calls'], 0)
        self.assertEqual(result['local_gradient_calls'], 3)
        self.assertEqual(result['gradient_calls'], 3)
        other = trajectory.search(graph, 'gradient_puct', base.SearchConfig(max_evaluations=5))
        self.assertGreater(other['prior_gradient_calls'], 0)
        self.assertGreater(other['local_gradient_calls'], 0)
        self.assertEqual(other['gradient_calls'], other['prior_gradient_calls'] + other['local_gradient_calls'])

    def test_endpoint_backup_happens_once_not_once_per_intermediate(self):
        nodes = []
        cls = trajectory.TrajectoryNode
        def capture(*args, **kwargs):
            node = cls(*args, **kwargs)
            nodes.append(node)
            return node
        with patch.object(trajectory, 'TrajectoryNode', side_effect=capture):
            result = trajectory.search(star(), 'uniform_puct', base.SearchConfig(max_evaluations=5))
        root = nodes[0]
        taken = [edge for edge in root.edges.values() if edge.child is not None]
        self.assertEqual(len(taken), 1)
        self.assertEqual(len(taken[0].trail), 4)
        self.assertEqual(root.visits, 1)
        self.assertEqual(taken[0].visits, 1)
        self.assertEqual(taken[0].value_sum, taken[0].child.value)
        self.assertEqual(result['trajectory_lengths'], [4])

    def test_all_intermediate_ancestors_excluded_and_local_energy_strictly_decreases(self):
        nodes = []
        cls = trajectory.TrajectoryNode
        def capture(*args, **kwargs):
            node = cls(*args, **kwargs)
            nodes.append(node)
            return node
        graph = problem()
        with patch.object(trajectory, 'TrajectoryNode', side_effect=capture):
            result = trajectory.search(graph, 'uniform_puct', base.SearchConfig(max_evaluations=256, max_depth=8))
        charged = 1
        def visit(node, ancestors):
            nonlocal charged
            for edge in (node.edges or {}).values():
                if edge.child is None:
                    continue
                seen = set(ancestors)
                previous = node.state
                for index, state in enumerate(edge.trail):
                    self.assertNotIn(state, seen)
                    self.assertEqual(sum(a != b for a, b in zip(previous, state)), 1)
                    self.assertEqual(state[0], 0)
                    if index:
                        self.assertLess(graph.assess(state)[2], graph.assess(previous)[2])
                    seen.add(state)
                    previous = state
                    charged += 1
                self.assertEqual(edge.trail[-1], edge.child.state)
                self.assertEqual(edge.child.depth, node.depth + len(edge.trail))
                visit(edge.child, seen)
        visit(nodes[0], {nodes[0].state})
        self.assertEqual(charged, result['evaluations'])
        self.assertGreater(result['local_cycle_actions_rejected'], 0)
        self.assertEqual(result['local_steps'], result['evaluations'] - 1 - len(result['trajectory_lengths']))

    def test_incumbents_are_feasible_original_edits_and_keep_searching(self):
        for arm in ('uniform_puct', 'gradient_puct'):
            solved = trajectory.search(problem(), arm, base.SearchConfig(max_evaluations=100))
            self.assertEqual(solved['candidate_edits'], 2)
            self.assertEqual(len(set(solved['candidate'].values())), 3)
            self.assertGreater(solved['evaluations'], 3)
            already = problem(initial=(0, 1, 2))
            kept = trajectory.search(already, arm, base.SearchConfig(max_evaluations=100))
            self.assertEqual(kept['candidate'], already.colors(already.initial))
            self.assertEqual(kept['candidate_edits'], 0)
            impossible = problem(edges=((0, 1),), initial=(0, 0), fixed=((0, 0), (1, 0)))
            failed = trajectory.search(impossible, arm)
            self.assertIsNone(failed['candidate'])
            self.assertEqual(failed['evaluations'], 1)

    def test_replay_and_trajectory_limit_validation(self):
        for steps in (1, 2, 8):
            config = base.SearchConfig(max_evaluations=100, seed=43)
            first = trajectory.search(problem(), 'gradient_puct', config, max_steps=steps)
            self.assertEqual(first, trajectory.search(problem(), 'gradient_puct', config, max_steps=steps))
            self.assertTrue(all(1 <= n <= steps for n in first['trajectory_lengths']))
            self.assertLessEqual(first['simulations'], 400)
        for steps in (0, 9, True, 1.0):
            with self.assertRaises(ValueError):
                trajectory.search(problem(), 'uniform_puct', max_steps=steps)

    def test_fixed_factorial_schedule_caps_and_tamper_before_search(self):
        plan = study.build_plan()
        self.assertEqual(len(plan['schedule']), 36)
        self.assertEqual(plan['maximum_search_state_evaluations'], 36 * 2048)
        self.assertEqual(plan['max_provider_attempts'], 0)
        self.assertEqual(plan['baseline_plan_fingerprint_sha256'], study.baseline.build_plan()['fingerprint_sha256'])
        for arm, (prior, steps) in study.ARMS.items():
            selected = [s for s in plan['schedule'] if s['arm'] == arm]
            self.assertEqual(len(selected), 9)
            self.assertTrue(all(s['prior_arm'] == prior and s['max_steps'] == steps for s in selected))
        bad = copy.deepcopy(plan)
        bad['schedule'][0]['max_steps'] = 8
        with patch.object(study, 'search') as dispatch, self.assertRaises(EBRTError):
            study.run_plan(reseal(bad))
        dispatch.assert_not_called()

    def test_small_fixture_runner_replay_and_resealed_corruption(self):
        fixture = {'id': 'tiny', 'nodes': list('ABC'), 'prior': dict.fromkeys('ABC', 0),
                   'edges': [['A', 'B'], ['A', 'C'], ['B', 'C']],
                   'added': [['A', 'B'], ['A', 'C'], ['B', 'C']], 'minimum_changes': 2}
        def config(**kwargs):
            return base.SearchConfig(**dict(kwargs, max_evaluations=32))
        # Only the small test fixture is searched; the hard pilot stays unrun.
        with patch.object(study, 'load_fixtures', return_value=[fixture]), patch.object(study, 'SearchConfig', side_effect=config):
            plan = study.build_plan()
            report = study.run_plan(plan)
            self.assertEqual(report['actual_provider_calls'], 0)
            self.assertEqual(len(report['records']), 12)
            self.assertTrue(all(s['planned'] == s['completed'] == 3 for s in report['summary'].values()))
            self.assertEqual(study.verify_report(report, plan)['checked_runs'], 12)
            for corruption in ('truncated', 'steps', 'grade', 'summary', 'time'):
                bad = copy.deepcopy(report)
                if corruption == 'truncated':
                    bad['records'].pop()
                elif corruption == 'steps':
                    bad['records'][0]['result']['local_steps'] += 1
                elif corruption == 'grade':
                    bad['records'][0]['grade']['minimal'] = not bad['records'][0]['grade']['minimal']
                elif corruption == 'summary':
                    bad['summary']['uniform_single']['evaluations'] += 1
                else:
                    bad['records'][0]['search_seconds'] = -1
                with self.assertRaises(EBRTError):
                    study.verify_report(reseal(bad), plan)


if __name__ == '__main__':
    unittest.main()
