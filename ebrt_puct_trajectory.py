"""Bounded local-repair trajectories as PUCT edges, with every state charged."""
from __future__ import annotations

from dataclasses import dataclass
import math
import random

import ebrt_puct_repair as base


@dataclass
class TrajectoryNode(base.Node):
    # Depth counts primitive recolorings, including intermediate states.
    depth: int = 0


@dataclass
class TrajectoryEdge(base.Edge):
    # Ancestor-cycle checks include intermediate states, not only tree nodes.
    trail: tuple[tuple[int, ...], ...] = ()


def search(problem, prior_arm, config=base.SearchConfig(), *, max_steps=8):
    if prior_arm not in ('uniform_puct', 'gradient_puct'):
        raise ValueError('Unknown PUCT prior')
    if type(max_steps) is not int or not 1 <= max_steps <= 8:
        raise ValueError('Invalid trajectory length')
    tree_rng = random.Random(config.seed)
    local_rng = random.Random(config.seed ^ 0x5A17)
    evaluations = prior_gradients = local_gradients = simulations = cycles = 0
    local_cycle_rejections = depth_reached = tree_depth_reached = local_steps = 0
    best_state, best_key = None, (math.inf, math.inf)
    improvements, lengths = [], []

    def evaluate(state, depth):
        nonlocal evaluations, best_state, best_key, depth_reached
        if evaluations >= config.max_evaluations:
            raise RuntimeError('State evaluation cap exceeded')
        conflicts, edits, energy = problem.assess(state)
        evaluations += 1
        depth_reached = max(depth_reached, depth)
        if (conflicts, edits) < best_key:
            best_state, best_key = state, (conflicts, edits)
            improvements.append({'evaluation': evaluations, 'conflicts': conflicts, 'edits': edits})
        return TrajectoryNode(state, 1 - energy / (len(problem.edges) + 1), depth=depth)

    root = evaluate(problem.initial, 0)
    stop = 'EVALUATION_LIMIT'
    while evaluations < config.max_evaluations:
        if root.exhausted:
            stop = 'TREE_EXHAUSTED'
            break
        if simulations >= 4 * config.max_evaluations:
            stop = 'SIMULATION_LIMIT'
            break
        simulations += 1
        node, ancestors, path = root, {root.state}, []
        while True:
            if node.edges is None:
                priors = base.action_priors(problem, node.state, prior_arm, config)
                prior_gradients += int(prior_arm == 'gradient_puct' and bool(priors))
                actions = list(priors)
                tree_rng.shuffle(actions)
                node.edges = {a: TrajectoryEdge(priors[a]) for a in actions}
            eligible = [(a, e) for a, e in node.edges.items()
                        if not e.blocked and (e.child is None or not e.child.exhausted)]
            if not eligible:
                node.exhausted = True
                break
            action, edge = max(eligible, key=lambda pair: base.puct_score(node, pair[1], config))
            successor = base.recolor(node.state, action)
            if successor in ancestors:
                edge.blocked = True
                cycles += 1
                continue
            path.append((node, edge))
            if edge.child is None:
                leaf = evaluate(successor, node.depth + 1)
                trail = [successor]
                seen = ancestors | {successor}
                while (len(trail) < max_steps and evaluations < config.max_evaluations
                       and leaf.depth < config.max_depth):
                    gains = base.directional_gains(problem, leaf.state)
                    local_gradients += 1
                    improving = []
                    for move, gain in gains.items():
                        if gain > 0:
                            target = base.recolor(leaf.state, move)
                            if target in seen:
                                local_cycle_rejections += 1
                            else:
                                improving.append(move)
                    if not improving:
                        break
                    local_rng.shuffle(improving)
                    move = max(improving, key=gains.get)
                    target = base.recolor(leaf.state, move)
                    leaf = evaluate(target, leaf.depth + 1)
                    local_steps += 1
                    trail.append(target)
                    seen.add(target)
                edge.trail = tuple(trail)
                edge.child = leaf
                leaf.exhausted = leaf.depth >= config.max_depth
                leaf.visits += 1
                lengths.append(len(trail))
                tree_depth_reached = max(tree_depth_reached, len(path))
                # One backup per expanded edge: its endpoint's actual value.
                # Intermediate evaluations update the incumbent, not visit counts.
                for parent, taken in path:
                    parent.visits += 1
                    taken.visits += 1
                    taken.value_sum += leaf.value
                break
            ancestors.update(edge.trail)
            node = edge.child

    feasible = best_key[0] == 0
    return {
        'arm': prior_arm, 'status': 'FEASIBLE_FOUND' if feasible else 'NO_FEASIBLE_FOUND',
        'candidate': problem.colors(best_state) if feasible else None,
        'candidate_edits': best_key[1] if feasible else None,
        'best_seen': {'colors': problem.colors(best_state), 'conflicts': best_key[0], 'edits': best_key[1]},
        'evaluations': evaluations, 'gradient_calls': prior_gradients + local_gradients,
        'simulations': simulations, 'cycle_edges_blocked': cycles, 'max_depth_reached': depth_reached,
        'root_visits': root.visits,
        'root_children_evaluated': sum(e.child is not None for e in (root.edges or {}).values()),
        'stop_reason': stop, 'improvements': improvements,
        'max_steps': max_steps, 'prior_gradient_calls': prior_gradients,
        'local_gradient_calls': local_gradients, 'local_steps': local_steps,
        'local_cycle_actions_rejected': local_cycle_rejections,
        'max_tree_depth_reached': tree_depth_reached, 'trajectory_lengths': lengths,
    }
