# PUCT versus stochastic multistart with the same repair trajectories

Status: **PROTOCOL FROZEN BEFORE HARD-CASE SEARCHES; RESULTS PENDING**

The [bounded-trajectory study](RND_PUCT_TRAJECTORY_STUDY.md) found feasible
repairs in 6/9 uniform-prior PUCT runs and 7/9 gradient-prior PUCT runs, with
6/9 exact minima in each. That comparison established an improvement over the
single-move tree controls, but did not establish that retaining a tree was
needed. This block compares that PUCT policy with a fixed stochastic restart
policy using one shared local-repair implementation.

## Common mechanism and policy difference

`ebrt_multistart_repair.py` factors the unchanged continuation into
`extend_trajectory`: after one selected recoloring, take at most seven
strictly improving gradient moves. Every step recomputes the all-edge loss
gradient, with edits measured against the original coloring. All intermediate
states are evaluated and can update the best feasible incumbent. Ancestor
cycles include every intermediate state; the first move may worsen the loss.
The first move plus continuation spends at most eight state evaluations.
Both allocation strategies call this exact helper.

PUCT retains its tree, Q/N statistics, score, priors, and endpoint backup.
The new PUCT path must reproduce every original result field of the frozen
trajectory kernel. That is tested on small cases before this block, then
checked against all eighteen matching saved hard-case controls after collection.
No previous runtime or closed result is edited.

Multistart is defined before observing outcomes:

1. Evaluate the original coloring at depth zero. Each episode starts there.
2. Compute the same uniform or gradient action prior as PUCT. Remove actions
   whose successor is an ancestor in this episode. Sample one remaining action
   proportional to its prior mass, renormalized on admissible actions.
3. Apply the shared at-most-eight-move trajectory and continue from its endpoint.
   A local minimum ends only that continuation. It does not cause an immediate
   restart: the next sampled first move can escape by worsening the objective.
4. Restart only at depth 2*n primitive recolorings or when no acyclic first
   action remains. Reevaluate the original coloring and charge that evaluation.
   If no legal action exists at all, stop instead of repeating identical roots.
5. Keep the best feasible incumbent across episodes, but never use it, an oracle
   solution, or fixture witnesses to choose a new start. Do not stop at a known
   optimum. Stop at the common state-evaluation or traversal cap.

Thus starts are stochastic perturbations of the original assignment. They
are not free jumps to independently drawn complete colorings. The baseline
has no retained tree, visit counts, Q values, or incumbent-guided restart.
It may revisit the same state in different episodes, with every evaluation
charged again. Episode receipts record evaluation boundaries, primitive depth,
segment count, first action, and restart reason. A restart that consumes the
last evaluation is retained as a zero-move final episode.

Decision randomness uses `Random(seed)`; the common local operator uses
`Random(seed ^ 0x5A17)`. Streams continue across restarts without reseeding.
PUCT shuffles tied tree actions while multistart samples prior-weighted actions;
identical seed labels do not imply identical generated paths. Fixed vertices,
action space, loss, 0.1 uniform prior mixture, 0.5 temperature, maximum local
trajectory length, and incumbent acceptance checks are common to both policies.

## Fixed comparison

| Arm | Allocation strategy | Prior for first action | Local continuation |
| --- | --- | --- | --- |
| puct_uniform | PUCT with retained tree | Uniform | Up to seven improving gradient steps |
| puct_gradient | PUCT with retained tree | Directional gradient | Same operator |
| multistart_uniform | Sampled trajectories with restarts | Uniform | Same operator |
| multistart_gradient | Sampled trajectories with restarts | Directional gradient | Same operator |

All arms use gradients for local repair. Compare allocation strategies within
each prior setting; compare priors within each strategy. This tests one defined
multistart policy against the PUCT package. It does not isolate the effect of
Q alone, N alone, caching alone, or prove a claim about all restart algorithms.

Run the unchanged 24/36/48-vertex development cases with seeds 7,19,43: nine
runs per arm, 36 total. Case order is 24,36,48; arm order follows the table
for seeds 7 and 43 and reverses for seed 19. Each run permits 2048 state
evaluations including all roots, restarts, and intermediates; 2*n primitive
recolorings per path/episode; and 8192 traversal/decision attempts. Maximum
block work is 73728 search-state evaluations and zero provider calls. No seed
selection, restart-policy tuning, case replacement, or adaptive budget changes
follow outcomes within this block.

Count actual gradients, local moves, starts/restarts, prior draws, state
evaluations, and elapsed search time separately. An equal state-evaluation
cap is not equal FLOPs or wall-clock work. Root revisits inside a retained
PUCT tree do not invoke another state evaluation; multistart reevaluates and
charges each restart. This accounting is explicit rather than hiding its
restart overhead. Post-run exact oracles and replay are diagnostic work and
cannot propose branches, choose starts, or terminate search.

Primary endpoints: feasible and exactly minimal accepted assignments out of
all nine planned runs per arm, with every case/seed retained. Report excess
edits on feasible answers, residual conflicts for failed diagnostics, actual
work, and paired outcomes. Search inputs contain only the public problem and
original coloring. Minimum edits 12/18/21 and witnesses stay outside search;
independent exact search checks minimality afterward. These reused development
cases and three tie-breaking seeds are not a held-out general reasoning test.
No LLM-as-a-judge or model generation is involved.

## Execution and validation

```bash
python run_puct_multistart_study.py plan --output /tmp/puct-multistart-plan.json
python run_puct_multistart_study.py run --plan /tmp/puct-multistart-plan.json --output /tmp/puct-multistart-report.json
python run_puct_multistart_study.py verify --plan /tmp/puct-multistart-plan.json --report /tmp/puct-multistart-report.json --output /tmp/puct-multistart-verification.json
```

Freeze source and plan before hard-case searches. Plans bind the previous
trajectory plan fingerprint, source and fixture hashes, schedule, both policy
definitions, settings, and Python/Torch versions. Outputs use private 0600
files outside the checkout and refuse overwrite. Replay reconstructs all
search outputs, episode ledgers, grades, and summaries. Timing is checked for
validity but is not reproduced or independently authenticated.

Tests cover unchanged PUCT results after sharing the operator, matched
continuations for a fixed first move, actual evaluator calls for roots and
intermediates, mid-segment stops, primitive depths, episode cycle guards,
absence of tree-statistic calls, streams continuing across restarts, feasible
incumbents surviving invalid restarts, gradient accounting, bounded schedules,
and replay/tamper rejection. New allocation-policy tests search only small
fixtures during preflight. All 265 relevant network-zero tests passed,
including ten new multistart tests. The baseline plan fingerprint matched
the saved trajectory plan exactly before hard-case searches in this block.
