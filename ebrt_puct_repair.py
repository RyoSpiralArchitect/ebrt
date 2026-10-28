"""Offline PUCT over public coloring states; no model calls or optimum access."""
from __future__ import annotations

from dataclasses import dataclass
import math
import random

import torch


ARMS = ('gradient_greedy', 'uniform_puct', 'gradient_puct')


@dataclass(frozen=True)
class RepairProblem:
    nodes: tuple[str, ...]
    palette: tuple[str, ...]
    edges: tuple[tuple[int, int], ...]
    initial: tuple[int, ...]
    fixed: tuple[tuple[int, int], ...]

    def __post_init__(self):
        n, k = len(self.nodes), len(self.palette)
        if not (all(type(x) is tuple for x in (self.nodes, self.palette, self.edges, self.initial, self.fixed))
                and all(type(x) is tuple for x in (*self.edges, *self.fixed))
                and 1 <= n <= 128 and 2 <= k <= 16
                and len(set(self.nodes)) == n and len(set(self.palette)) == k
                and all(type(x) is str for x in (*self.nodes, *self.palette))
                and len(self.initial) == n
                and all(type(c) is int and 0 <= c < k for c in self.initial)
                and len(set(self.edges)) == len(self.edges)
                and all(type(a) is int and type(b) is int and 0 <= a < b < n for a, b in self.edges)
                and len(dict(self.fixed)) == len(self.fixed)
                and all(type(i) is int and type(c) is int and 0 <= i < n and 0 <= c < k
                        and self.initial[i] == c for i, c in self.fixed)):
            raise ValueError('Invalid repair problem')

    @classmethod
    def from_public(cls, problem, prior):
        nodes, palette = tuple(problem['nodes']), tuple(problem['palette'])
        if set(prior) != set(nodes):
            raise ValueError('Prior coverage mismatch')
        index = {n: i for i, n in enumerate(nodes)}
        colors = {c: i for i, c in enumerate(palette)}
        return cls(nodes, palette,
                   tuple(sorted(tuple(sorted((index[a], index[b]))) for a, b in problem['edges'])),
                   tuple(colors[prior[n]] for n in nodes),
                   tuple(sorted((index[n], colors[c]) for n, c in problem['fixed_colors'].items())))

    def validate_state(self, state):
        if (type(state) is not tuple or len(state) != len(self.nodes)
                or not all(type(c) is int and 0 <= c < len(self.palette) for c in state)
                or any(state[i] != c for i, c in self.fixed)):
            raise ValueError('Invalid coloring state')

    def assess(self, state):
        self.validate_state(state)
        conflicts = sum(state[a] == state[b] for a, b in self.edges)
        edits = sum(a != b for a, b in zip(state, self.initial))
        energy = conflicts + edits / (len(self.nodes) + 1)
        return conflicts, edits, energy

    def actions(self, state):
        fixed = dict(self.fixed)
        return [(i, c) for i in range(len(self.nodes)) if i not in fixed
                for c in range(len(self.palette)) if c != state[i]]

    def colors(self, state):
        return {n: self.palette[c] for n, c in zip(self.nodes, state)}


def recolor(state, action):
    i, color = action
    return state[:i] + (color,) + state[i + 1:]


def directional_gains(problem, state):
    """Differentiate all current edges plus edits relative to the original prior.

    At a one-hot state, each single-recolor directional derivative equals the
    exact energy change. This is a classical local heuristic, not model credit.
    """
    problem.validate_state(state)
    x = torch.nn.functional.one_hot(torch.tensor(state), len(problem.palette)).to(torch.float64)
    x.requires_grad_(True)
    loss = (len(state) - x[torch.arange(len(state)), torch.tensor(problem.initial)].sum()) / (len(state) + 1)
    if problem.edges:
        endpoints = torch.tensor(problem.edges)
        loss = loss + (x[endpoints[:, 0]] * x[endpoints[:, 1]]).sum()
    loss.backward()
    gradient = x.grad.tolist()
    return {a: gradient[a[0]][state[a[0]]] - gradient[a[0]][a[1]] for a in problem.actions(state)}


@dataclass(frozen=True)
class SearchConfig:
    max_evaluations: int = 2048
    max_depth: int = 96
    c_puct: float = 1.25
    temperature: float = 0.5
    uniform_mix: float = 0.1
    seed: int = 7

    def __post_init__(self):
        if not (type(self.max_evaluations) is int and 1 <= self.max_evaluations <= 100000
                and type(self.max_depth) is int and 1 <= self.max_depth <= 256
                and type(self.seed) is int
                and all(type(v) in (int, float) and math.isfinite(v)
                        for v in (self.c_puct, self.temperature, self.uniform_mix))
                and self.c_puct > 0 and self.temperature > 0 and 0 < self.uniform_mix <= 1):
            raise ValueError('Invalid search configuration')


def action_priors(problem, state, arm, config):
    actions = problem.actions(state)
    if not actions:
        return {}
    if arm == 'uniform_puct':
        return dict.fromkeys(actions, 1 / len(actions))
    if arm != 'gradient_puct':
        raise ValueError('Unknown prior arm')
    gains = directional_gains(problem, state)
    peak = max(gains.values())
    weights = {a: math.exp((gains[a] - peak) / config.temperature) for a in actions}
    total = sum(weights.values())
    return {a: config.uniform_mix / len(actions) + (1 - config.uniform_mix) * weights[a] / total
            for a in actions}


@dataclass
class Edge:
    prior: float
    visits: int = 0
    value_sum: float = 0.0
    child: Node | None = None
    blocked: bool = False


@dataclass
class Node:
    state: tuple[int, ...]
    value: float
    visits: int = 0
    edges: dict[tuple[int, int], Edge] | None = None
    exhausted: bool = False


def puct_score(parent, edge, config):
    # Unvisited edges use the parent's exact current value (first-play urgency).
    q = edge.value_sum / edge.visits if edge.visits else parent.value
    return q + config.c_puct * edge.prior * math.sqrt(1 + parent.visits) / (1 + edge.visits)


def search(problem, arm, config=SearchConfig()):
    if arm not in ARMS:
        raise ValueError('Unknown search arm')
    rng = random.Random(config.seed)
    evaluations = gradients = simulations = cycles = depth_reached = 0
    best_state = None
    best_key = (math.inf, math.inf)
    improvements = []

    def evaluate(state):
        nonlocal evaluations, best_state, best_key
        if evaluations >= config.max_evaluations:
            raise RuntimeError('State evaluation cap exceeded')
        conflicts, edits, energy = problem.assess(state)
        evaluations += 1
        if (conflicts, edits) < best_key:
            best_state, best_key = state, (conflicts, edits)
            improvements.append({'evaluation': evaluations, 'conflicts': conflicts, 'edits': edits})
        return Node(state, 1 - energy / (len(problem.edges) + 1))

    root = evaluate(problem.initial)
    stop = 'EVALUATION_LIMIT'
    if arm == 'gradient_greedy':
        current = root
        while evaluations < config.max_evaluations:
            if depth_reached >= config.max_depth:
                stop = 'DEPTH_LIMIT'
                break
            gains = directional_gains(problem, current.state)
            gradients += 1
            actions = list(gains)
            rng.shuffle(actions)
            if not actions or max(gains.values()) <= 0:
                stop = 'LOCAL_MINIMUM'
                break
            action = max(actions, key=gains.get)
            current = evaluate(recolor(current.state, action))
            depth_reached += 1
    else:
        # Traversals that discover exhausted branches spend a simulation too.
        # This independent cap prevents loops even when no new state is evaluated.
        while evaluations < config.max_evaluations:
            if root.exhausted:
                stop = 'TREE_EXHAUSTED'
                break
            if simulations >= 4 * config.max_evaluations:
                stop = 'SIMULATION_LIMIT'
                break
            simulations += 1
            node, states, path = root, {root.state}, []
            while True:
                if node.edges is None:
                    priors = action_priors(problem, node.state, arm, config)
                    gradients += int(arm == 'gradient_puct' and bool(priors))
                    actions = list(priors)
                    rng.shuffle(actions)
                    node.edges = {a: Edge(priors[a]) for a in actions}
                eligible = [(a, e) for a, e in node.edges.items()
                            if not e.blocked and (e.child is None or not e.child.exhausted)]
                if not eligible:
                    node.exhausted = True
                    break
                action, edge = max(eligible, key=lambda pair: puct_score(node, pair[1], config))
                successor = recolor(node.state, action)
                if successor in states:
                    edge.blocked = True
                    cycles += 1
                    continue
                path.append((node, edge))
                if edge.child is None:
                    leaf = edge.child = evaluate(successor)
                    depth_reached = max(depth_reached, len(path))
                    leaf.exhausted = len(path) >= config.max_depth
                    leaf.visits += 1
                    for parent, taken in path:
                        parent.visits += 1
                        taken.visits += 1
                        taken.value_sum += leaf.value
                    break
                states.add(successor)
                node = edge.child

    feasible = best_key[0] == 0
    return {
        'arm': arm, 'status': 'FEASIBLE_FOUND' if feasible else 'NO_FEASIBLE_FOUND',
        'candidate': problem.colors(best_state) if feasible else None,
        'candidate_edits': best_key[1] if feasible else None,
        'best_seen': {'colors': problem.colors(best_state), 'conflicts': best_key[0], 'edits': best_key[1]},
        'evaluations': evaluations, 'gradient_calls': gradients, 'simulations': simulations,
        'cycle_edges_blocked': cycles, 'max_depth_reached': depth_reached,
        'root_visits': root.visits,
        'root_children_evaluated': sum(e.child is not None for e in (root.edges or {}).values()),
        'stop_reason': stop, 'improvements': improvements,
    }
