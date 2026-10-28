"""PUCT versus stochastic restart search with one shared repair operator."""
from __future__ import annotations

import math
import random

import ebrt_puct_repair as base
from ebrt_puct_trajectory import TrajectoryNode, TrajectoryEdge


def extend_trajectory(problem, first, ancestors, local_rng, config, max_steps, remaining, evaluate):
    """The same improving continuation for both allocation strategies.

    The first move has already been evaluated. Every additional move uses the
    supplied evaluator and consumes one unit of remaining search budget.
    """
    leaf, trail = first, [first.state]
    seen = ancestors | {first.state}
    gradients = steps = cycle_rejections = 0
    while len(trail) < max_steps and steps < remaining and leaf.depth < config.max_depth:
        gains = base.directional_gains(problem, leaf.state)
        gradients += 1
        improving = []
        for move, gain in gains.items():
            if gain > 0:
                target = base.recolor(leaf.state, move)
                if target in seen:
                    cycle_rejections += 1
                else:
                    improving.append(move)
        if not improving:
            break
        local_rng.shuffle(improving)
        move = max(improving, key=gains.get)
        target = base.recolor(leaf.state, move)
        leaf = evaluate(target, leaf.depth + 1)
        steps += 1
        trail.append(target)
        seen.add(target)
    return leaf, tuple(trail), gradients, steps, cycle_rejections


def search(problem, strategy, prior_arm, config=base.SearchConfig(), *, max_steps=8):
    if strategy not in ('puct', 'multistart') or prior_arm not in ('uniform_puct', 'gradient_puct'):
        raise ValueError('Unknown repair strategy or prior')
    if type(max_steps) is not int or not 1 <= max_steps <= 8:
        raise ValueError('Invalid trajectory length')
    decision_rng = random.Random(config.seed)
    local_rng = random.Random(config.seed ^ 0x5A17)
    evaluations = prior_gradients = local_gradients = simulations = cycles = 0
    local_cycle_rejections = depth_reached = tree_depth_reached = local_steps = 0
    best_state, best_key = None, (math.inf, math.inf)
    improvements, lengths, episodes = [], [], []
    starts, prior_draws = 1, 0

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

    def extend(node, action, ancestors):
        nonlocal local_gradients, local_steps, local_cycle_rejections
        first = evaluate(base.recolor(node.state, action), node.depth + 1)
        leaf, trail, gradients, steps, rejections = extend_trajectory(
            problem, first, ancestors, local_rng, config, max_steps,
            config.max_evaluations - evaluations, evaluate,
        )
        local_gradients += gradients
        local_steps += steps
        local_cycle_rejections += rejections
        lengths.append(len(trail))
        return leaf, trail

    root = evaluate(problem.initial, 0)
    stop = 'EVALUATION_LIMIT'
    if strategy == 'puct':
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
                    decision_rng.shuffle(actions)
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
                    leaf, trail = extend(node, action, ancestors)
                    edge.trail, edge.child = trail, leaf
                    leaf.exhausted = leaf.depth >= config.max_depth
                    leaf.visits += 1
                    tree_depth_reached = max(tree_depth_reached, len(path))
                    for parent, taken in path:
                        parent.visits += 1
                        taken.visits += 1
                        taken.value_sum += leaf.value
                    break
                ancestors.update(edge.trail)
                node = edge.child
    else:
        node, ancestors = root, {root.state}
        start_evaluation, segment_count, first_action = 1, 0, None

        def close_episode(reason):
            episodes.append({'start_evaluation': start_evaluation, 'end_evaluation': evaluations,
                             'depth': node.depth, 'segments': segment_count,
                             'first_action': list(first_action) if first_action is not None else None,
                             'stop_reason': reason})

        while evaluations < config.max_evaluations:
            if simulations >= 4 * config.max_evaluations:
                stop = 'SIMULATION_LIMIT'
                break
            simulations += 1
            restart_reason = None
            if node.depth >= config.max_depth:
                restart_reason = 'DEPTH_LIMIT'
            else:
                priors = base.action_priors(problem, node.state, prior_arm, config)
                prior_gradients += int(prior_arm == 'gradient_puct' and bool(priors))
                if not priors:
                    stop = 'NO_LEGAL_ACTIONS'
                    break
                eligible = [a for a in priors if base.recolor(node.state, a) not in ancestors]
                cycles += len(priors) - len(eligible)
                if not eligible:
                    restart_reason = 'NO_ACYCLIC_ACTIONS'
            if restart_reason:
                close_episode(restart_reason)
                node = evaluate(problem.initial, 0)  # Each restart is charged, even though it repeats the prior.
                starts += 1
                ancestors = {node.state}
                start_evaluation, segment_count, first_action = evaluations, 0, None
                continue
            # No Q, N, retained tree, incumbent-guided restart, or oracle target.
            action = decision_rng.choices(eligible, weights=[priors[a] for a in eligible], k=1)[0]
            prior_draws += 1
            if first_action is None:
                first_action = action
            node, trail = extend(node, action, ancestors)
            ancestors.update(trail)
            segment_count += 1
        close_episode(stop)

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
        'strategy': strategy, 'starts': starts, 'restart_evaluations': starts - 1,
        'prior_draws': prior_draws, 'episodes': episodes,
    }
