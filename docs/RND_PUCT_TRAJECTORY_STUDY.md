# Bounded repair trajectories inside PUCT: a 2x2 comparison

Status: **PROTOCOL FROZEN BEFORE HARD-CASE SEARCHES; RESULTS PENDING**

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
