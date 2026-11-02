# Runtime and execution extensions

These notes preserve the concrete standard single-lane and opt-in execution paths from the former root README. The compiled public program is distinct from its uptake by a generator. See the [overview](../../README.md) and [mechanism](../mechanism/README.md).

## Standard single-lane engine

```python
from ebrt_engine import RevisionEngine
```

`RevisionEngine` defaults to `CoverageFirstActuator`: reserve the late
correction and every caller-declared `required_support` item, rank within
those constraints by the existing credit, and preserve the original signed
controls and L2 budget. A successful program fills the configured number of
slots with positive integer allocations summing to 100. More than 100 slots,
insufficient capacity, ineligible or zero-control required sites, an unfillable
selection count, or an allocation rounded to zero stops before external
generation. The policy guarantees complete declared support selection or a
clear error; it does not guarantee that a generator follows the program.

The engine composes the historical verified core run with an internal
compile-only test double, then validates the complete coverage program and
calls the actual model once. The internal double receives no semantic gold,
makes no provider request, and contributes no answer or latency to the actual
generation receipt. Core optimizer pinning, the run-local backward witness,
structural checks, and post-run grading remain active. Receipts identify
`engine_protocol=ebrt-coverage-first-engine-v1` and
`actuator_policy=coverage_first_v1`.

Historical `ebrt_core.RevisionEngine`, `JointRevisionEngine`, and local-model
CLI commands remain available for their original protocols. They do not
silently adopt the new policy. Source-pinned plans must be replayed against
their recorded code revision; the R&D note gives the snapshot procedure.

```bash
python3 -m unittest -v test_ebrt_engine
```

## Budgeted public reinspection

The opt-in reinspection runtime turns the coverage-first program's allocation
units into actual output-token ceilings for separate evidence-extraction
requests. It validates each returned quotation against the selected source,
then supplies the full context and validated excerpts to one final generation.

```bash
python3 ebrt_reinspection_hosted.py plan --model gpt-5.6-sol \
  --case fresh-normalization-support --output /tmp/ebrt-reinspection-plan.json
python3 ebrt_reinspection_hosted.py run --plan /tmp/ebrt-reinspection-plan.json \
  --output /tmp/ebrt-reinspection-results.json
python3 ebrt_reinspection_hosted.py verify --plan /tmp/ebrt-reinspection-plan.json \
  --report /tmp/ebrt-reinspection-results.json
```

The default three-site run permits at most four provider attempts: three
extractions sharing a 768-token ceiling, followed by one final request capped
at 512 tokens. Per-site floors and exact integer largest remainders determine
the extraction limits. Provider or quotation-validation failure stops the run
before later requests, with no repair or retry. `plan` and `verify` are offline;
output files are new, private files outside the checkout.

This has a separate orchestration protocol and explicit stage ledger. The
standard engine retains its single-generation contract. Quote provenance,
request-budget execution, and final semantic grades are separate checks;
request ceilings do not measure consumed compute or establish improved
reasoning. Signed controls remain provenance. See the
[protocol note](../../docs/RND_BUDGETED_REINSPECTION.md).
The first bounded four-call integration passed all three source checks and
the final output contract. It verifies the execution path on a known case;
it is not a comparative quality result.

```bash
python3 -m unittest -v test_ebrt_reinspection
```

## Dependency-aware public reinspection

`ebrt_dependency_hosted.py` accepts a caller-declared dependency graph between
selected sources. Audits run in dependency order and receive validated quotes
from their direct predecessors. The original per-source token ceilings and
three-audit/one-final limit remain fixed; final artifacts return to original
program order. Required source spans are graded after execution and never
control requests or retries.

The bounded comparison below shares two actual audits, then compares a tariff
lookup with and without the register quotation that supplies its key. It uses
one long-record synthetic case and at most six provider attempts:

```bash
python3 ebrt_dependency_canary.py plan --model gpt-5.6-sol \
  --output /tmp/ebrt-dependency-canary-plan.json
python3 ebrt_dependency_canary.py run --plan /tmp/ebrt-dependency-canary-plan.json \
  --output /tmp/ebrt-dependency-canary-results.json
python3 ebrt_dependency_canary.py verify --plan /tmp/ebrt-dependency-canary-plan.json \
  --report /tmp/ebrt-dependency-canary-results.json
```

`plan` and `verify` are offline. Source provenance, literal required-span
coverage, and final answer/support grades remain separate. This is a small
serial diagnostic using caller-supplied dependencies, not a general quality
estimate. See the [protocol note](../../docs/RND_DEPENDENCY_REINSPECTION.md).
The first fixed block recovered the required table span with parent context;
the isolated extraction only quoted its heading. Both final answers and
support sets were correct, so no final-quality gain was observed.

### Non-unique solutions and an LLM judge

The coloring example constructs a free JSON answer after the same three
dependency-aware audits. Assign colors to A–F from RED/GREEN/BLUE, fix A=RED,
and require different colors across AB, BC, CD, DE, EF, FA, and the newly added
BE edge. Using all three colors is optional; 18 assignments are feasible.
No reference coloring or list of acceptable answers reaches the solver.

```bash
python3 ebrt_coloring_hosted.py plan --model gpt-5.6-sol \
  --judge-model gpt-5.6-sol --output /tmp/ebrt-coloring-plan.json
python3 ebrt_coloring_hosted.py run --plan /tmp/ebrt-coloring-plan.json \
  --output /tmp/ebrt-coloring-results.json
python3 ebrt_coloring_hosted.py verify --plan /tmp/ebrt-coloring-plan.json \
  --report /tmp/ebrt-coloring-results.json
```

The fixed block permits eight attempts: three audits, one free solution, and
four stateless judge calls covering the generated answer, two distinct valid
controls, and a control violating only BE. The judge sees the problem and one
candidate without its origin, reference answers, or mechanical verdict.
Independent predicates check its ten criterion decisions; disagreement is
recorded without repair. Mathematical feasibility, citation lineage, and
output format are separate. See the [example and protocol](../../docs/RND_NONUNIQUE_COLORING_JUDGE.md).
The executed follow-up generated `RED,GREEN,RED,GREEN,RED,GREEN` for A–F.
All four judge decisions matched the predicate checker, including rejection
of the BE-only violation. The generated coloring coincided with one fixed
control, so this covers three distinct assignments. An earlier quotation
failure remains recorded; the follow-up used an explicitly adapted source
layout. Solver and judge used the same backend in separate contexts.

The [minimal repair experiment](../../docs/RND_COLORING_MINIMAL_REPAIR.md) carries
the previous coloring as explicit state. It compares repair with and without
feedback from a differentiable public collision loss, using two solution
requests and two blind feasibility judgments. Exhaustive checking measures
the number of changed vertices and whether the repair is minimal.
The first four-call block found the same optimal one-vertex repair in both
conditions (B from GREEN to BLUE). Both judges agreed on feasibility; no
quality or edit-count advantage from gradient feedback was observed.
The [cascade evaluation](../../docs/RND_REPAIR_CASCADES.md) keeps that repair
implementation unchanged and tests fixed 10-, 14-, and 18-vertex problems.
Every optimal repair must reach beyond the initially conflicting vertices;
exact feasibility and edit-count grades are compared across both conditions.
In the fixed paired block, both conditions exhausted the unchanged 512-token
solver budget on all three cases without completed answers. Quality and
minimality therefore remain unassessed; all six judges were skipped. The
preceding fail-fast attempt and all six paired outcomes are preserved.
The [matched-budget follow-up](../../docs/RND_REPAIR_BUDGET.md) keeps the same
problems and repair implementation while raising both solver ceilings to
4096 tokens; judge settings and the maximum twelve-attempt schedule remain fixed.
That block completed all twelve attempts. Both conditions produced feasible,
exactly minimal repairs in all three cases (5/8/9 changes), and all six judges
agreed with mechanical feasibility checks. No quality advantage was observed.
The [hard-case replication](../../docs/RND_HARD_REPAIR_REPLICATION.md) adds fixed
24/36/48-vertex problems, independently verified exact optima, and two trials
per condition with reversed execution order. All planned trials remain in
the success-rate denominator, including missing or infeasible answers.
It yielded one minimal answer out of six for full repair and two out of six
with feedback. The other nine solver requests timed out; all three completed
answers were optimal and agreed with their judges. This is a small difference
in completed outputs under the timeout setting, not an established quality gain.
The [matched-timeout follow-up](../../docs/RND_HARD_REPAIR_TIMEOUT.md) keeps the
same cases, prompts, output caps, and counterbalanced schedule while extending
both arms' solver/judge request timeout from 60 to 180 seconds in a separate,
source-pinned block. The earlier observations remain unchanged.
Completion was 3/6 in both arms; feasible outputs were 3/6 versus 2/6, and
minimal outputs 2/6 versus 1/6 (full repair versus feedback). Six other solver
responses reached the 4096-token ceiling without completed answers; none timed
out. All six judges agreed with mechanical checks, including one infeasible
feedback answer. This block shows no feedback advantage.
The [PUCT repair pilot](../../docs/RND_PUCT_REPAIR_PILOT.md) explores a separate
offline hybrid: directional public-state gradients guide tree priors, while
exact constraint values are backed up through PUCT. It compares greedy repair,
uniform PUCT, and gradient-guided PUCT under a shared state-evaluation ceiling.
It makes no model calls and does not change the production engine.
Across three cases and three seeds, each arm found zero feasible repairs.
Gradient PUCT left fewer conflicts than uniform PUCT in every matched row,
but both trees stayed shallower than the minimum required edit counts; greedy
repair was better on the two larger cases. The report proposes bounded local
repair trajectories as tree edges for a separate follow-up.
The [bounded-trajectory study](../../docs/RND_PUCT_TRAJECTORY_STUDY.md) implements
that follow-up as a 2x2 comparison of uniform/gradient priors and one/eight-move
edges. Every intermediate state spends the shared 2048-evaluation budget;
both trajectory conditions use the same gradient-based local repair operator.
The fixed 36-run block found feasible repairs in 6/9 uniform-prior trajectory
runs and 7/9 gradient-prior trajectory runs, with 6/9 exact minima in each.
Both single-move controls remained at 0/9. Every run spent exactly 2048 state
evaluations; all 36 searches replayed exactly, and all 18 single-move controls
matched the closed pilot. This supports the trajectory package on these
development cases, with no established gradient-prior or hosted-model gain.
The [PUCT/multistart comparison](../../docs/RND_PUCT_MULTISTART_STUDY.md) tests
whether retaining the tree helps against a fixed stochastic restart policy.
Both strategies use the same repair continuation and 2048-state evaluation
cap; all restart and intermediate evaluations are charged.
In the frozen 36-run comparison, multistart reached the exact minimum in 9/9
runs with either prior; PUCT retained 6/9 minima with either prior. All runs
spent 2048 state evaluations. Thus the retained tree was unnecessary for
success on this development set at that budget. Work costs and arrival times
still differ, and no general or hosted-model advantage is established.
