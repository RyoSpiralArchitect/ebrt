# PUCT versus stochastic multistart with the same repair trajectories

Status: **COLLECTED; MULTISTART 9/9 MINIMAL FOR BOTH PRIORS, PUCT 6/9 FOR BOTH**

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

## Executed results

Source `217d85bb9abadc310191233358ce75155a425f89` was committed before the
plan and hard-case searches. Collection and verification completed on
2026-10-28 (Asia/Tokyo). All 36 runs spent exactly 2048 state evaluations,
for 73728 total, with zero provider calls. No policy tuning or added seeds
followed these outcomes.

| Allocation / prior | Completed / planned | Feasible | Exactly minimal |
| --- | ---: | ---: | ---: |
| PUCT / uniform | 9 / 9 | 6 / 9 | 6 / 9 |
| PUCT / gradient | 9 / 9 | 7 / 9 | 6 / 9 |
| Multistart / uniform | 9 / 9 | 9 / 9 | 9 / 9 |
| Multistart / gradient | 9 / 9 | 9 / 9 | 9 / 9 |

The fixed multistart policy reached the exact optimum on every case/seed
under both priors. Each PUCT arm retained its earlier six minimal outputs.
The retained tree was therefore not necessary for reaching the optima on
this development set at this budget. The result supports this multistart
comparator over the frozen PUCT policies at the stated endpoint; it is not
a general superiority result or an isolated causal estimate for Q/N backup.

| Case | Seed | PUCT / uniform | PUCT / gradient | Multistart / uniform | Multistart / gradient |
| --- | ---: | --- | --- | --- | --- |
| hard-24 | 7 | Optimal: 12 edits | Optimal: 12 edits | Optimal: 12 edits | Optimal: 12 edits |
| hard-24 | 19 | Optimal: 12 edits | Optimal: 12 edits | Optimal: 12 edits | Optimal: 12 edits |
| hard-24 | 43 | Optimal: 12 edits | Optimal: 12 edits | Optimal: 12 edits | Optimal: 12 edits |
| hard-36 | 7 | Optimal: 18 edits | Feasible: 19 edits (+1) | Optimal: 18 edits | Optimal: 18 edits |
| hard-36 | 19 | Optimal: 18 edits | Optimal: 18 edits | Optimal: 18 edits | Optimal: 18 edits |
| hard-36 | 43 | Invalid: 1 conflict | Optimal: 18 edits | Optimal: 18 edits | Optimal: 18 edits |
| hard-48 | 7 | Optimal: 21 edits | Invalid: 1 conflict | Optimal: 21 edits | Optimal: 21 edits |
| hard-48 | 19 | Invalid: 1 conflict | Optimal: 21 edits | Optimal: 21 edits | Optimal: 21 edits |
| hard-48 | 43 | Invalid: 1 conflict | Invalid: 2 conflicts | Optimal: 21 edits | Optimal: 21 edits |

All 31 accepted assignments passed independent node-coverage, palette,
fixed-color, edge, and original-edit checks; 30 were oracle-minimal. Invalid
PUCT states remain diagnostics with no excess-edit grade. No failed trial
was dropped or replaced. The PUCT controls match all original fields in the
saved trajectory block, including their invalid-state edit counts and work
counters. They are deterministic controls, not eighteen new independent
observations.

## Work, restart behavior, and arrival times

All four rows below spend 18432 state evaluations. The identity is
`start-state evaluations + selected first moves + improving local moves`.
The count includes all intermediates and all repeated restart roots.

| Allocation / prior | Start-state evaluations | Selected first moves | Improving local moves | Gradient calls (prior + local) | Search seconds, summed |
| --- | ---: | ---: | ---: | --- | ---: |
| PUCT / uniform | 9 | 4663 | 13760 | 0 + 17749 | 11.619 |
| PUCT / gradient | 9 | 7746 | 10677 | 2036 + 18016 | 16.826 |
| Multistart / uniform | 279 | 5513 | 12640 | 0 + 17522 | 12.668 |
| Multistart / gradient | 279 | 7657 | 10496 | 7657 + 17629 | 17.251 |

Each multistart arm spent 270 evaluations reevaluating restart roots in
addition to its nine original roots. Both used 42 starts per 24-node run,
29 per 36-node run, and 22 per 48-node run. Every completed episode reached
its 2*n depth limit; the final episode ended at the shared evaluation limit.
No hard-case restart was triggered by lack of an acyclic action. The streams
were not reseeded at restarts. All 558 multistart episode ledgers account for
their evaluation intervals, sampled first actions, and primitive depths.

This policy spends longer consecutive paths than the retained-tree policy
within the same overall evaluation cap. The comparison changes allocation
and restart behavior together; it does not establish that restarting alone,
removing Q alone, or deeper paths alone caused the difference. State counts
are matched, but gradient computations and elapsed time differ. In this one
environment the multistart arms took slightly longer than their corresponding
PUCT arms; no speed or equal-FLOP advantage is claimed.

The first evaluation at which an optimum was recorded is a descriptive
trace diagnostic, assessed with the oracle after search. Every run continued
to 2048; this metric was not a stopping condition or a selected budget:

| Case | Seed | Multistart / uniform | Multistart / gradient |
| --- | ---: | ---: | ---: |
| hard-24 | 7 | 72 | 43 |
| hard-24 | 19 | 272 | 188 |
| hard-24 | 43 | 124 | 286 |
| hard-36 | 7 | 402 | 198 |
| hard-36 | 19 | 59 | 937 |
| hard-36 | 43 | 129 | 218 |
| hard-48 | 7 | 1014 | 136 |
| hard-48 | 19 | 357 | 97 |
| hard-48 | 43 | 1247 | 561 |

Equal 9/9 final success does not imply identical trajectories or a stable
gradient-prior efficiency benefit. Likewise, multistart does not dominate
PUCT at every evaluation prefix: uniform PUCT reached the hard-48/seed-7
optimum at evaluation 81, while uniform multistart first reached it at 1014.
These are trace observations within the fixed run, not new smaller-budget
experiments. A held-out suite and predeclared budget curves would be needed
before selecting a generally preferred allocation policy.

The successful baseline still uses the same public-state gradient local
repair; the uniform prior does not remove that operator. On this coloring
loss, its gradients equal direct one-step energy differences. No unique
autograd mechanism, hosted-model improvement, or production promotion is
established. The concrete finding is that retained PUCT statistics are not
required for the observed repair success under this tested configuration.

## Verification receipts

All 36 searches replayed exactly, including results, incumbent traces,
episode ledgers, and work counters. Replay spent another 73728 state
evaluations as diagnostic work, not extra trials. A separate audit checked
all 36 raw assignments and budget identities, all 558 multistart episodes,
all 540 charged restarts, and every original field of the eighteen PUCT
controls. Timing is not independently reproduced by replay.

```text
plan:   61ce1bb451d9e04e3b54d4f04007ee756f8cb44442565626fbd5ab96439bac07
report: 7cf5ab7d474c2a36c365180e1f5261e09b47ecb6a87fa26178b95863a0bb72e9
verify: 7c7e12fa129d071b1d05fff7c203dbef4bfd39a4cc3446c2a200ebe5407891e1
audit:  1b3c7ec065e96708b9c88763156922cf9334d615386785bfc7a4327251365b83
```

The plan, raw report, replay receipt, and audit receipt remain in private
0600 files outside the checkout. Earlier runtime sources and closed reports
remain unchanged.
