# Bounded repair trajectories inside PUCT: a 2x2 comparison

Status: **COLLECTED; TRAJECTORIES REACH 6/9 AND 7/9 FEASIBLE, BOTH 6/9 MINIMAL**

The [single-recolor pilot](RND_PUCT_REPAIR_PILOT.md) produced no feasible
answers. Its gradient PUCT trees reached only depths 9/6/8 on the 24/36/48-node
cases, below the necessary minimum edits 12/18/21. The depth caps themselves
were not reached. This separate study implements the previously specified
local-repair trajectory intervention without changing the closed pilot.

## What changes

An expanded edge starts with the single recoloring selected by PUCT. Then
up to seven further strictly improving gradient steps are taken. Gradients
are recomputed after every local move using all current edges and edit cost
against the original input coloring. The shared operator selects the largest
positive directional gain that does not return to an ancestor state. It stops
at a local minimum, an ancestor-cycle barrier, eight total moves, the remaining
state budget, or the remaining primitive-move depth budget.

Every intermediate state is mechanically assessed, charged, and considered
for the best feasible incumbent. The endpoint becomes the tree child. Its
actual heuristic value is backed up once along the selected tree path;
intermediate evaluations do not inflate visit counts. The same state reached
through a different acyclic path is charged again, with no transposition cache.
Cycle checks include every intermediate state in the full ancestor path.

Tree depth and recoloring depth are reported separately. The depth cap remains
2*n **primitive recolorings**, not 2*n eight-move edges. If a trajectory runs
out of the shared evaluation budget midway, its last evaluated state is the
endpoint; no remainder is generated for free. Feasible incumbents do not stop
search or expose the exact optimum as a stopping target.

The loss, all legal first actions, 0.1 uniform prior mixture, 0.5 softmax
temperature, c_PUCT=1.25, first-play urgency, endpoint value, and single-agent
mean-value backup remain as in the pilot. There is no progressive widening,
learned value function, random rollout, model proposal, or oracle-completed
leaf. First moves may worsen the objective; subsequent local moves must
improve it. Directional derivatives equal exact one-step energy differences
for this public bilinear coloring loss. They do not differentiate through a
language model or the discrete tree path.

Tree tie-breaking retains `Random(seed)`; local tie-breaking uses a separate
`Random(seed ^ 0x5A17)` stream so local shuffles do not consume the tree's random
stream. Different search paths can still consume their streams differently.
Matching seeds does not make trajectories identical across conditions.

## Frozen factorial schedule and work accounting

| Arm | Tree prior | Maximum moves per expanded edge | Local operator |
| --- | --- | ---: | --- |
| uniform_single | Uniform | 1 | None |
| gradient_single | Directional gradient | 1 | None |
| uniform_trajectory | Uniform | 8 | Improving gradient repair |
| gradient_trajectory | Directional gradient | 8 | Improving gradient repair |

Both trajectory arms use the identical local-repair operator. In particular,
`uniform_trajectory` uses gradients during local repair and is not gradient-free.
Compare priors within each trajectory setting and the trajectory intervention
within each prior setting. No greedy-only arm is added to this block.

The three unchanged development cases run with seeds 7,19,43, giving nine runs
per condition and 36 total. Case order is 24,36,48. Arm order follows the table
for seeds 7 and 43 and reverses for seed 19. Each run permits at most 2048 state
evaluations including the root, 2*n primitive recolorings along a path, and
8192 tree traversal attempts. Maximum block work is 73728 search-state
evaluations and zero provider calls. Local evaluations consume the same cap;
gradient calculations, traversal counts, and wall time are reported separately.
Matched evaluation ceilings are not matched actual compute or an LLM token
budget. Post-run exact oracle checks and deterministic replay are diagnostic
work outside the search budget, and cannot guide any candidate or branch.

The new search kernel supports max_steps=1 as the no-trajectory control. Tests
require equality of every original search result field with the frozen pilot
kernel, including gradients, visits, incumbents, stop causes, and cycle counts.
After collection, compare the 18 hard-case controls with the closed pilot's
matching records. Those deterministic repetitions are controls and replay
checks, not independent new problem samples.

Primary endpoints remain feasible and exactly minimal accepted assignments
out of all nine planned runs per arm. Report every case/seed result, excess
edits for feasible candidates, residual conflicts for failed searches, primitive
and tree depth, and actual work. Keep failures in denominators. Do not select
the best seed, increase budgets, change fixtures, tune constants, or modify
the local operator after seeing this block's outcomes. These reused development
fixtures and three tie-breaking seeds do not establish general superiority.

The public search interface is unchanged and contains no witnesses, optimum,
case-selection seed, or exact-search state counts. Exact minimum edits 12/18/21
are checked independently after each run for grading only. Search returns a
candidate only after exact feasibility checks; LLM-as-a-judge is unnecessary
for this offline kernel comparison.

## Running and verifying

```bash
python run_puct_trajectory_study.py plan --output /tmp/puct-trajectory-plan.json
python run_puct_trajectory_study.py run --plan /tmp/puct-trajectory-plan.json --output /tmp/puct-trajectory-report.json
python run_puct_trajectory_study.py verify --plan /tmp/puct-trajectory-plan.json --report /tmp/puct-trajectory-report.json --output /tmp/puct-trajectory-verification.json
```

Source and plan are frozen before the hard-case study. The plan binds the
original pilot plan fingerprint, source and fixture hashes, schedule, settings,
Python version, and Torch version. Files are private 0600 outputs outside the
checkout and refuse overwrite. Verification replays the deterministic search,
compares all result fields, recomputes grades, and reconstructs summaries.
Elapsed times are checked for valid values but are not reproduced or proved
by replay. Verification work is reported separately from experimental trials.

Tests cover unchanged single-step controls, actual evaluator calls for every
intermediate, stopping midway through a trajectory, primitive depth limits,
gradient recomputation, endpoint-only visit backup, full-path cycle protection,
feasible incumbent retention, fixed colors, deterministic replay, schedule
bounds, and resealed report/plan corruption. The production engine and all
earlier experimental runtime sources remain unchanged.
Preflight passed all 255 relevant network-zero tests, including ten new
trajectory tests. The baseline plan fingerprint also matched the saved pilot
plan exactly before any hard-case search in this block.

## Executed results

The block used source `4d360501e1ebe22ef59ee5e793d84e9ed8d99906`, committed
before the plan and searches. All 36 runs and their verification completed on
2026-10-28 (Asia/Tokyo), with zero provider calls. No adaptive changes or extra
seeds followed collection.

| Condition | Completed / planned | Feasible | Exactly minimal |
| --- | ---: | ---: | ---: |
| Uniform prior, one move | 9 / 9 | 0 / 9 | 0 / 9 |
| Gradient prior, one move | 9 / 9 | 0 / 9 | 0 / 9 |
| Uniform prior, up to eight moves | 9 / 9 | 6 / 9 | 6 / 9 |
| Gradient prior, up to eight moves | 9 / 9 | 7 / 9 | 6 / 9 |

All conditions spent exactly 2048 state evaluations per run: 73728 total,
including every intermediate state and all roots. Both trajectory conditions
improved feasibility and minimality over their single-move controls on these
fixed development problems. The gradient prior added one feasible answer,
but did not improve the total number of minimal answers. Three selected
problems and three tie-breaking seeds support a descriptive result, not a
general or statistically established prior advantage.

In the full case/seed table, invalid entries report residual conflicts, not
accepted answers. Diagnostic edit counts on failed trajectories are included
to prevent confusing a low edit count with an improvement on the optimum.

| Case | Seed | Uniform, one move | Gradient, one move | Uniform trajectory | Gradient trajectory |
| --- | ---: | --- | --- | --- | --- |
| hard-24 | 7 | Invalid: 6 conflicts | Invalid: 3 conflicts | Optimal: 12 edits | Optimal: 12 edits |
| hard-24 | 19 | Invalid: 6 conflicts | Invalid: 3 conflicts | Optimal: 12 edits | Optimal: 12 edits |
| hard-24 | 43 | Invalid: 6 conflicts | Invalid: 3 conflicts | Optimal: 12 edits | Optimal: 12 edits |
| hard-36 | 7 | Invalid: 18 conflicts | Invalid: 13 conflicts | Optimal: 18 edits | Feasible: 19 edits (+1) |
| hard-36 | 19 | Invalid: 16 conflicts | Invalid: 13 conflicts | Optimal: 18 edits | Optimal: 18 edits |
| hard-36 | 43 | Invalid: 18 conflicts | Invalid: 13 conflicts | Invalid: 1 conflict, 15 edits | Optimal: 18 edits |
| hard-48 | 7 | Invalid: 22 conflicts | Invalid: 16 conflicts | Optimal: 21 edits | Invalid: 1 conflict, 21 edits |
| hard-48 | 19 | Invalid: 26 conflicts | Invalid: 16 conflicts | Invalid: 1 conflict, 21 edits | Optimal: 21 edits |
| hard-48 | 43 | Invalid: 24 conflicts | Invalid: 16 conflicts | Invalid: 1 conflict, 20 edits | Invalid: 2 conflicts, 19 edits |

All 13 accepted assignments passed independent raw-color checks: exact node
coverage, allowed palette, fixed A, every edge, and edit counts relative to
the original coloring. Twelve were oracle-minimal; the sole nonminimal answer
was gradient_trajectory on hard-36/seed 7 with 19 edits against an optimum of
18. Failed assignments remain diagnostic only and have no excess-edit grade.

The depth change is visible without increasing the depth or evaluation caps:

| Case | Necessary minimum recolorings | Uniform single depth | Gradient single depth | Uniform trajectory depth | Gradient trajectory depth |
| --- | ---: | ---: | ---: | ---: | ---: |
| hard-24 | 12 | 5–6 | 9 | 17–19 | 16–18 |
| hard-36 | 18 | 4–5 | 6 | 25–27 | 22 |
| hard-48 | 21 | 6–9 | 8 | 28–33 | 23–26 |

These are primitive recoloring depths, not tree-edge counts. Trajectory trees
reached 3–6 tree edges and crossed the necessary primitive-depth bound in
every run. That bound is not sufficient for feasibility: on hard-48 both
trajectory conditions succeeded in only 1/3 seeds, and failures retained one
or two collisions. The prior pilot's universal depth shortfall was removed,
but remaining barriers and finite-budget search failures persist.

Search continued after finding feasibility. For example, uniform_trajectory
on hard-24/seed 43 first found a 14-edit feasible answer at evaluation 343 and
later reached 12 edits at evaluation 1366. Gradient_trajectory on hard-36/seed 7
improved a 20-edit feasible answer to 19 edits but never reached 18. The oracle
was used after search and did not terminate either run.

## Actual work and interpretation

| Condition | State evaluations | Prior gradient calls | Local gradient calls | Local moves after first moves | Search seconds, summed |
| --- | ---: | ---: | ---: | ---: | ---: |
| uniform_single | 18432 | 0 | 0 | 0 | 1.922 |
| gradient_single | 18432 | 7428 | 0 | 0 | 7.756 |
| uniform_trajectory | 18432 | 0 | 17749 | 13760 | 6.855 |
| gradient_trajectory | 18432 | 2036 | 18016 | 10677 | 8.339 |

The trajectory arms expanded 4663 and 7746 tree edges respectively, compared
with 18423 per single-move arm. Intermediate states account for the remainder:
roots + expanded first moves + local moves = state evaluations. Trajectory
lengths never exceeded eight, and no path exceeded 2*n primitive moves.
Gradient calls include attempts that find no admissible improving move; they
are not identical to the number of accepted local steps. Elapsed time covers
search only and is one environment's measurement, not a controlled speed claim.

The observed improvement belongs to the package of bounded gradient local
repair and endpoint-based tree expansion. It is not evidence that gradient
priors alone are effective, that gradients supply information unavailable to
direct local move scoring, or that hosted LLM reasoning has improved. Both
trajectory conditions use the same gradient-based operator, and no model was
called. This block also does not establish that PUCT is necessary: a matched
evaluation-budget restart/local-search baseline has not yet been tested.
That comparison would help isolate the contribution of the tree statistics.
No production-engine promotion or further experiment is included here.

## Replay and audit

All 36 searches replayed exactly, including incumbent traces, trajectory
lengths, depth, visit counts, and gradient/evaluation counters. Replay spent
another 73728 state evaluations as diagnostic work, not extra trials. A
separate raw-color and accounting audit checked all 36 records, including
failed diagnostics and every trajectory-length ledger. All 18 single-move
controls matched every original result field in the saved pilot, not merely
their success/failure labels. Timing was not reproduced by replay.

```text
plan:   e7f6ab4ff21a010e3b6500da56f5aa39c162108bd93582d149eeb38372299f97
report: 6ce385ae3ec3c325a4609230123f9401a39553e5652ee1ddd56e557ffb6134a6
verify: 6663e57668d2f5ff9c3273e4a61b9c97552b61a415efb93f39a3fcd4410bea41
audit:  a38d961bffda417dc06f76b3587767a23c2e92b80fcd071d3ce59294c4514b1c
```

The plan, raw report, replay receipt, and audit receipt remain private 0600
files outside the checkout. Earlier runtime sources, closed reports, and
their results are preserved.
