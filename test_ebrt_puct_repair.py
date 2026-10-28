from dataclasses import replace
import json
import math
import random
import socket
import unittest
from unittest.mock import patch

import ebrt_puct_repair as p
import run_puct_repair_study as study
from ebrt_core import EBRTError, _seal


def problem(edges=((0, 1), (0, 2), (1, 2)), initial=(0, 0, 0), fixed=((0, 0),)):
    return p.RepairProblem(tuple('ABC'[:len(initial)]), ('RED', 'GREEN', 'BLUE'), edges, initial, fixed)


class PUCTTests(unittest.TestCase):
    def setUp(self):
        guard = patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden'))
        guard.start()
        self.addCleanup(guard.stop)

    def test_directional_derivative_equals_every_exact_one_move_difference(self):
        for seed in range(10):
            rng = random.Random(seed)
            graph = p.RepairProblem(tuple('ABCDE'), ('R', 'G', 'B'),
                                    tuple((a, b) for a in range(5) for b in range(a + 1, 5) if rng.random() < .5),
                                    (0,) + tuple(rng.randrange(3) for _ in range(4)), ((0, 0),))
            state = (0,) + tuple(rng.randrange(3) for _ in range(4))
            before = graph.assess(state)[2]
            for action, gain in p.directional_gains(graph, state).items():
                self.assertAlmostEqual(gain, before - graph.assess(p.recolor(state, action))[2], places=12)

    def test_all_edges_detect_new_conflicts_and_gradient_recomputes(self):
        graph = problem(edges=((0, 1), (1, 2)), initial=(0, 0, 1))
        old = p.directional_gains(graph, graph.initial)
        self.assertAlmostEqual(old[(1, 1)], -.25)  # resolves AB but creates BC, plus one edit
        self.assertAlmostEqual(old[(1, 2)], .75)
        state = p.recolor(graph.initial, (1, 2))
        new = p.directional_gains(graph, state)
        self.assertAlmostEqual(new[(1, 0)], -.75)
        self.assertEqual(graph.assess(state)[:2], (0, 1))

    def test_prior_keeps_inactive_vertices_and_worsening_actions(self):
        graph = problem(edges=((0, 1),), initial=(0, 0, 1))
        config = p.SearchConfig()
        priors = p.action_priors(graph, graph.initial, 'gradient_puct', config)
        self.assertEqual(set(priors), set(graph.actions(graph.initial)))
        self.assertTrue(all(v > 0 for v in priors.values()))
        self.assertTrue(any(i == 2 for i, c in priors))  # C has no initial collision
        self.assertFalse(any(i == 0 for i, c in priors))
        self.assertAlmostEqual(sum(priors.values()), 1)
        uniform = p.action_priors(graph, graph.initial, 'uniform_puct', config)
        self.assertEqual(set(uniform), set(priors))
        self.assertEqual(len(set(uniform.values())), 1)

    def test_edits_always_reference_original_and_feasibility_dominates(self):
        graph = problem()
        state = p.recolor(p.recolor(graph.initial, (1, 1)), (2, 2))
        self.assertEqual(graph.assess(state)[:2], (0, 2))
        self.assertLess(graph.assess(state)[2], 1)
        self.assertEqual(graph.assess(p.recolor(state, (1, 0)))[:2], (1, 1))

    def test_known_triangle_all_arms_find_true_minimum_without_oracle(self):
        graph = problem()
        for arm in p.ARMS:
            result = p.search(graph, arm, p.SearchConfig(max_evaluations=256, max_depth=6))
            self.assertEqual(result['status'], 'FEASIBLE_FOUND')
            self.assertEqual(result['candidate_edits'], 2)
            self.assertEqual(result['candidate']['A'], 'RED')
            self.assertLessEqual(result['evaluations'], 256)
            self.assertLessEqual(result['max_depth_reached'], 6)

    def test_infeasible_fixed_graph_never_emits_accepted_candidate(self):
        graph = problem(edges=((0, 1),), initial=(0, 0), fixed=((0, 0), (1, 0)))
        for arm in p.ARMS:
            result = p.search(graph, arm)
            self.assertIsNone(result['candidate'])
            self.assertIsNone(result['candidate_edits'])
            self.assertEqual(result['best_seen']['conflicts'], 1)
            self.assertEqual(result['evaluations'], 1)

    def test_cycle_guard_exhausts_finite_tree_and_counts_repeated_states(self):
        graph = problem(edges=(), initial=(0, 0))
        for arm in ('uniform_puct', 'gradient_puct'):
            result = p.search(graph, arm, p.SearchConfig(max_evaluations=100))
            self.assertEqual(result['stop_reason'], 'TREE_EXHAUSTED')
            self.assertEqual(result['evaluations'], 5)  # two distinct paths to each noninitial color
            self.assertGreater(result['cycle_edges_blocked'], 0)
            self.assertEqual(result['root_visits'], 4)
            self.assertEqual(result['root_children_evaluated'], 2)
            self.assertEqual(result['candidate_edits'], 0)

    def test_visit_mean_and_prior_both_enter_puct_and_no_sign_flip(self):
        parent = p.Node((0,), .2, visits=9)
        edge = p.Edge(.6, visits=2, value_sum=.8)
        config = p.SearchConfig()
        self.assertAlmostEqual(p.puct_score(parent, edge, config), .4 + 1.25 * .6 * math.sqrt(10) / 3)
        self.assertAlmostEqual(p.puct_score(parent, p.Edge(.6), config), .2 + 1.25 * .6 * math.sqrt(10))

    def test_seed_replay_budget_depth_and_greedy_stop(self):
        graph = problem()
        for arm in p.ARMS:
            config = p.SearchConfig(max_evaluations=1)
            result = p.search(graph, arm, config)
            self.assertEqual(result['evaluations'], 1)
            self.assertEqual(result['gradient_calls'], 0)
            config = p.SearchConfig(max_evaluations=40, max_depth=1, seed=19)
            first = p.search(graph, arm, config)
            self.assertEqual(first, p.search(graph, arm, config))
            self.assertLessEqual(first['max_depth_reached'], 1)
            self.assertLessEqual(first['evaluations'], 40)
            self.assertLessEqual(first['simulations'], 160)
        solved = p.search(graph, 'gradient_greedy')
        self.assertEqual(solved['stop_reason'], 'LOCAL_MINIMUM')

    def test_invalid_configuration_and_state_fail_closed(self):
        for kwargs in ({'max_evaluations': 0}, {'max_depth': True}, {'temperature': 0},
                       {'uniform_mix': 0}, {'c_puct': float('nan')}):
            with self.assertRaises(ValueError):
                p.SearchConfig(**kwargs)
        with self.assertRaises(ValueError):
            replace(problem(), edges=((0, 1), (0, 1)))
        with self.assertRaises(ValueError):
            p.directional_gains(problem(), (1, 0, 0))
        with self.assertRaises(ValueError):
            p.search(problem(), 'unknown')

    def test_study_projection_excludes_oracles_and_schedule_is_bounded(self):
        fixture = json.loads((study.ROOT / study.FIXTURE).read_text())[0]
        expected = study.public_problem(fixture)
        for key in ('minimum_changes', 'restricted_minimum', 'witnesses', 'search_states'):
            fixture[key] = 'not available to search'
        self.assertEqual(study.public_problem(fixture), expected)
        plan = study.build_plan()
        self.assertEqual(len(plan['schedule']), 27)
        self.assertEqual(plan['max_provider_attempts'], 0)
        self.assertEqual(plan['maximum_search_state_evaluations'], 27 * 2048)
        for arm in p.ARMS:
            self.assertEqual(sum(s['arm'] == arm for s in plan['schedule']), 9)
        plan['schedule'][0]['config']['max_evaluations'] = 4096
        plan.pop('fingerprint_sha256')
        with self.assertRaises(EBRTError):
            study.validate_plan(_seal(plan))


if __name__ == '__main__':
    unittest.main()
