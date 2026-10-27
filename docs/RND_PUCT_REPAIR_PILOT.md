# Gradient-guided PUCT for public repair states

Status: **OFFLINE PILOT PROTOCOL; RESULTS PENDING**

The [matched-timeout study](RND_HARD_REPAIR_TIMEOUT.md) exposed three failures:
constraint violations, feasible but nonminimal repairs, and no completed answer
within the token cap. A single gradient injection did not establish an advantage.
This pilot tests a different mechanism: recompute directional repair gains at
search nodes and use them as PUCT priors. It makes zero hosted requests and
does not change the production engine or any closed experiment source.

## Two different backward operations

```mermaid
flowchart LR
    S[Public coloring state] --> G[Differentiate collision and edit loss]
    G --> P[Positive prior over every legal recoloring]
    P --> T[PUCT selects a branch]
    T --> E[Evaluate next state with exact constraints]
    E --> B[Back up value to tree visit statistics]
    E --> I[Keep best feasible incumbent]
    B --> T
    E --> S
```

Autograd differentiates an explicit public one-hot state. PUCT backup updates
visit counts and mean values along a sampled tree path; it does not differentiate
that path. Neither operation accesses a language model's hidden reasoning.

For n vertices, the relaxed loss is

`L(X) = sum_(u,v in all edges) dot(X_u, X_v) + sum_v (1 - X_v[original_color_v])/(n+1)`.

At one-hot states this is exactly `conflicts + edits/(n+1)`. One extra conflict
is worse than any possible improvement in edit count. The reference coloring
is always the original input, never the previous search node. All current
edges contribute, including presently satisfied edges that a move might break.
This differs from the earlier active-conflict-only feedback, which remains
unchanged. Fixed vertices cannot be recolored.

For action a changing v from c to d, define
`gain(a) = gradient[v,c] - gradient[v,d]` and
`P(a) = 0.1/|A| + 0.9*softmax(gain(a)/0.5)`.
Every nonfixed vertex and every alternative palette color remain eligible,
including zero-gradient vertices and immediately worsening moves. The positive
floor does not guarantee that a finite budget visits every action. Only
ancestor-state cycles are excluded. Reaching the same state through distinct
acyclic paths is allowed and charged again; there is no transposition cache.

For this bilinear coloring loss, the single-recolor directional derivative
equals the exact one-step energy change. Tests compare every action against
independent energy differences. This is a classical local heuristic expressed
with autograd, not evidence that gradients provide unique information beyond
constraint-based move scoring.

The tree score is

`Q(s,a) + 1.25 * P(s,a) * sqrt(1 + N(s)) / (1 + N(s,a))`.

Unvisited edges use the current state's value as Q. A new leaf has exact
heuristic value `1 - L/(number_of_edges+1)`; its value is backed up as a mean,
without alternating signs because this is single-agent optimization. There
are no random rollouts, learned value model, language-model proposals, or
oracle-completed leaves. Seeded shuffling breaks ties. PUCT priors are computed
once per expanded state, not copied from the root. Search retains the best
evaluated feasible assignment, separately from the best invalid diagnostic
state. An invalid state is never emitted as an accepted candidate. Feasible
incumbents do not stop further edit minimization.

## Fixed pilot comparison

Reuse the existing 24/36/48-vertex cases as development fixtures. Their known
exact optima are available to post-run grading only, not search inputs or stop
conditions. The search interface contains only nodes, palette, edges, original
colors, and fixed colors. Witnesses and other oracle fields are removed before
that interface; independent exact search runs after each trial for grading.

Compare three arms:

| Arm | Action choice | Tree | Gradient computations |
| --- | --- | --- | --- |
| Gradient greedy | Best strictly positive directional gain | None; stop at a local minimum | Recomputed at each step |
| Uniform PUCT | PUCT with uniform priors | Same PUCT and exact heuristic value | None |
| Gradient PUCT | PUCT with directional-gain priors | Same PUCT and exact heuristic value | Once per expanded node |

Each arm runs each case with tie-breaking seeds 7,19,43: 27 runs, nine per arm,
on three distinct problems. The arm order reverses for seed 19. Maximum search
evaluations are 2048 per run, including the root; maximum depth is 2*n and
maximum traversal attempts 4*2048. The entire block admits at most 55296 search
state evaluations and zero provider attempts. Greedy may stop early and spend
less than its cap. This is a matched evaluation ceiling, not matched actual
work, FLOPs, wall-clock time, or LLM token budget. Gradient calls, evaluations,
traversals, and time are reported separately. Post-run oracle and grade checks
are additional diagnostic work and do not guide search.

Primary endpoints: feasible and oracle-minimal outputs out of all nine planned
runs per arm, plus excess edits on feasible outputs. Retain all failures and
all case/seed rows. Record residual conflicts, best-state edit count, depth,
stopping cause, and work counters. No selecting the best seed, changing cases,
adding rollouts, retuning constants, or increasing budgets within this block.
Repeated tie-break seeds are not new independent problems. These previously
used fixtures are not a held-out benchmark and cannot establish broad gains.

```bash
python run_puct_repair_study.py plan --output /tmp/puct-pilot-plan.json
python run_puct_repair_study.py run --plan /tmp/puct-pilot-plan.json --output /tmp/puct-pilot-report.json
```

Freeze code and plan before running the hard cases. Plans bind source hashes,
configuration, schedule, fixture, and Torch version. Output files refuse
overwrite. Individual searches are deterministic for a fixed input/config;
elapsed-time measurements are not deterministic. Fingerprints bind stored
content, not independent proof of execution. Tests cover exact directional
gains, new-collision awareness, the immutable original-edit objective, positive
action coverage, PUCT scoring, cycle handling, bounds, seed replay, invalid
candidate rejection, and oracle-free input projection.
All 245 relevant network-zero tests passed before the hard-case pilot,
including eleven new PUCT tests. No hard-case search outcomes were used to
choose the frozen constants or change the comparison schedule.

## Path to an LLM-assisted hybrid

Keep this pilot distinct from hosted inference. A later adapter could admit
parsed LLM proposals as bounded multi-vertex actions, score their public-state
directions, and validate each resulting assignment before incumbent updates.
Single-vertex gradients are exact here; their prediction for multi-vertex
actions can be wrong because edge cross-terms change too, so those actions
must still be evaluated. The exact graph oracle must never propose branches.

A hosted comparison should give both PUCT variants the same initial state,
proposal mechanism, feasibility checks, and total call/token ceilings; separate
proposal cost from state evaluations. A conflict-only prior and direct local
energy-difference prior would help distinguish useful localization from any
gradient-specific contribution. First use this offline result to determine
whether the tree policy supplies useful exploration under a small fixed budget.
