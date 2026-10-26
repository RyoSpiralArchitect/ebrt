# Fixed repair implementation on harder cascade cases

Status: **FIRST BLOCK STOPPED; PAIRED FOLLOW-UP PREFLIGHT**

This extends the terminal repair experiment in the same PR. The existing
`ebrt_coloring_repair.py` is byte-unchanged. The evaluation adapter directly
calls its `backward_feedback` and `solver_invocation`: identical collision
loss, actual backward, priority values, suggested-vertex policy, prompt text,
and repair objective. The solver remains gpt-5.6-sol, low effort, 512 output
tokens, no retries. The prompt's original singular “added edge” wording is
retained even though the JSON now carries multiple added edges.

Only evaluation plumbing generalizes beyond the former hard-coded six-node
problem: frozen graph fixtures, exhaustive proper-coloring search, per-graph
constraint checks, and per-graph judge criterion names. No solution or optimum
is sent to either solver. The judge evaluates feasibility, not minimality.
Judge output ceilings are 2048 instead of 512 to accommodate up to 38 criterion
booleans; both conditions receive identical judge settings. A changed judge
protocol means these judge results should not be treated as identical-format
replications of the earlier six-node block.

## Predeclared cases and selection

| Case | Vertices | Current edges | Added conflicting edges | Feasible solutions | Minimum changes | Optimal solutions |
| --- | --- | --- | --- | --- | --- | --- |
| cascade-10 | 10 | 17 | 5 | 16 | 5 | 3 |
| cascade-14 | 14 | 32 | 10 | 12 | 8 | 2 |
| cascade-18 | 18 | 35 | 16 | 184 | 9 | 4 |

All use RED/GREEN/BLUE with A fixed RED. Previous colors satisfy every old
edge. Added edges are exactly the current edges whose endpoints had equal
previous colors. Every optimal repair changes at least one vertex outside
those initially conflicting edges. Thus repairing only the suggested vertices
cannot attain the optimum. The unchanged prompt allows changing other vertices.

Fixtures were selected entirely offline before provider calls. For sizes
10/14/18, use Python Random(size*10000 + index), indices starting at 1, with
edge sampling densities .43/.38/.33. Draw prior colors and a planted feasible
coloring (A fixed RED in each), then sample edges only across unequal planted
colors. Retain the first case with at least three conflicting edges, some
inactive vertices, minimum edits at least floor(size/3), at least two optima,
and an inactive-vertex change in every optimum. Selected seeds are
100001, 140006, 180001. The planted coloring is not included in fixtures or
prompts. Exact committed fixtures are authoritative. This is structural
selection of engineered cascade cases, not an untouched random benchmark or
selection based on LLM performance.

Exhaustive enumeration uses edge pruning and a saturation/degree variable
order. A separate test exhausts in natural vertex order and independently
confirms solution counts, minimum costs, number of optima, and the cascade
condition. The count/optimum metadata stays on the grading side.

## Frozen execution and interpretation

Case order is 10,14,18. Within each case: full repair, gradient-feedback repair,
blind judge of the first raw output, blind judge of the second raw output.
Twelve actual attempts maximum; 3072 solver plus 12288 judge requested output
tokens maximum (15360 total). These are ceilings, not consumed compute.
No retries, prompt tuning, replacement cases, or winner-selected reruns occur.
A provider/model/judge-format failure stops the remaining block. Completed
malformed/infeasible answers and well-formed judge disagreements are retained
and do not change the schedule. Each invocation uses a fresh context.

Primary measurements are feasibility and attaining the exact minimum change
count, then excess changes among feasible answers. Infeasible answers are not
rewarded for editing fewer vertices. Judge/checker agreement and native output
format are separate measurements. Execution PASS indicates protocol completion,
not a correct repair. The support_ids field retains the prior terminal schema;
there are no new source-audit requests in this experiment.

Only the FEEDBACK_JSON record differs between solver conditions. It contains
explicit conflict localization as well as gradients, so a difference cannot
isolate gradient information from the other supplied facts. Inputs have unequal
lengths despite matched solver settings. Three fixed-order pairs, without
replications, support descriptive differences only. The same-backend judges
are not independent-model evidence. Surrogate-state backpropagation does not
cross into the hosted model.

Plans pin fixtures, runtime sources, feedback, settings, Torch version, and
case order. Offline replay reconstructs requests, grade fields, judgments,
call counts, and stop boundaries. Receipts are private, outside the checkout;
verification checks internal consistency, not provider authenticity. Earlier
closed plans and reports remain unchanged and verifiable.

```bash
python ebrt_repair_scaling.py plan --output /tmp/cascades-plan.json
python ebrt_repair_scaling.py run --plan /tmp/cascades-plan.json --output /tmp/cascades-report.json
python ebrt_repair_scaling.py verify --plan /tmp/cascades-plan.json --report /tmp/cascades-report.json --output /tmp/cascades-verification.json
```

## First block stopped before a comparison

The first block was fixed at source
`4045557256cb8bf64ce824b4462d5738ba8198c0`. Its first request, cascade-10 /
full_repair, returned `HOSTED_RESPONSE_INCOMPLETE`: 512 output tokens, all
512 reported as reasoning tokens, with no completed visible candidate.
The original global fail-fast rule stopped after one actual request. No
feedback-arm output or judge was observed. Offline integrity verification
passed for that failed block. It was not resumed or relabeled as a wrong
mathematical answer.

```text
plan:   bfaff0bbb7098d59ec427eccfb23bfe893474e002aae3c5ca06e7784627db3d7
report: 2e777a9e50c4f0116d9b05cc2815b92c391d3a350417f468353f12afa5cff554
verify: eadcd6bd75e728145d74dbcd03e31b23e5cadee6b7d8190b90f1b70bb8d5fc1b
```

## Separately fixed paired follow-up

`ebrt_repair_scaling_pairs.py` adds an evaluation-only failure-isolation policy.
The original evaluation source and failed block remain unchanged. The new plan
pins the original study plan and new runner hash. All three cases, both solver
prompts, the actual backward implementation, solver settings (including the
512 ceiling), and judge rubric/settings remain exactly the same. The evaluator
now records provider failure as one condition's outcome and proceeds to the
other independent condition. A judge is skipped, spending no attempt, if its
solver returned no completed raw candidate. A completed but malformed answer
still receives a judge. Judge format/provider failure is also retained without
preventing the next independent pair. Returned-model drift or a pre-dispatch
configuration failure still stops the whole follow-up.

The full three-case schedule is fixed before these new calls, with at most
12 new attempts and no replacement or repeat within this block. This repeats
the first baseline condition as part of a newly declared paired collection;
it is not an untouched first run. The first failure remains part of the record.
Across both blocks the maximum is 13 actual requests. This adaptation follows
an execution-budget failure before any completed candidate or judge outcome;
there is no selection on an observed quality advantage. No further automatic
budget, prompt, or case tuning is planned.

Collection completion, provider completion, mathematical feasibility, edit
optimality, and judge agreement are separate statuses. Missing outputs count
as failure to produce a usable repair under the budget, not as a specific
coloring-constraint violation. Summaries retain all three planned pairs,
including missing outputs; they do not compare only surviving candidates.

```bash
python ebrt_repair_scaling_pairs.py plan --output /tmp/cascade-pairs-plan.json
python ebrt_repair_scaling_pairs.py run --plan /tmp/cascade-pairs-plan.json --output /tmp/cascade-pairs-report.json
python ebrt_repair_scaling_pairs.py verify --plan /tmp/cascade-pairs-plan.json --report /tmp/cascade-pairs-report.json --output /tmp/cascade-pairs-verification.json
```
