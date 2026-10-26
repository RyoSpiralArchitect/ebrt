# Matched 4096-token follow-up on the fixed cascade cases

Status: **PREFLIGHT; ONE FIXED BLOCK PLANNED**

The [512-token study](RND_REPAIR_CASCADES.md) produced no completed candidate
in any of its six paired solver attempts. This separately declared block keeps
all three problems and both repair conditions, increasing the solver output
ceiling from 512 to 4096 in both conditions before any new requests.

`ebrt_repair_budget.py` is a small plan/execution wrapper. It directly reuses
the previous paired evaluator's invocation compiler, state derivation, grading,
stop boundaries, and skipped-judge accounting. The original backward function,
solver prompt, source fixtures, prior colors, added edges, optimum metadata,
case order, model gpt-5.6-sol, low reasoning effort, and 60-second timeout remain
identical. The earlier execution modules are byte-unchanged. A new plan schema
binds the original 512-token plan fingerprint, paired-runner hash, all prior
source hashes, Torch version, and the new wrapper hash. The old validator does
not accept the new plan as an old 512-token block.

Judge settings remain at 2048 output tokens with the same per-graph feasibility
rubric and fresh contexts. They receive neither prior state, arm identity,
gradients, optimum, nor mechanical grade. Same-backend judging does not provide
independent-model validation. Mechanical exhaustive search supplies minimality;
the judge assesses feasibility only.

The schedule is fixed at case sizes 10,14,18, each with full repair, gradient
feedback, then judges of those raw candidates. At most six solver and six judge
attempts are allowed. The maximum requested output ceiling is 36864 tokens
(6*4096 + 6*2048), including reasoning and visible output. Actual consumption
is measured separately. No timeout or retry setting is increased. A completed
but invalid candidate is retained and judged. A solver provider failure is a
recorded outcome; its judge is skipped, and the other independent arm proceeds.
Judge format/provider errors are retained. Model drift or pre-dispatch errors
stop the block. No repeated sampling or automatic budget escalation follows.

Primary outcomes, over all three planned problems per arm, are completed
candidates, feasible repairs, and exact-minimum repairs. Change count/excess
are reported only alongside feasibility. Infeasible candidates cannot win by
making fewer edits. Missing output is not a mathematical constraint violation.
Judge/checker disagreement is separate and retained. Three single fixed-order
pairs support descriptive differences only. A same-budget advantage, if one
appears, cannot distinguish gradients from the explicit conflict localization
also present in feedback. Prompt lengths differ. Comparing against the earlier
512-token block is a disclosed sequential development comparison, not a
randomized budget experiment.

```bash
python ebrt_repair_budget.py plan --output /tmp/repair-budget-plan.json
python ebrt_repair_budget.py run --plan /tmp/repair-budget-plan.json --output /tmp/repair-budget-report.json
python ebrt_repair_budget.py verify --plan /tmp/repair-budget-plan.json --report /tmp/repair-budget-report.json --output /tmp/repair-budget-verification.json
```

Plans/reports use private non-overwriting files outside the checkout. Offline
verification reconstructs requests, counts, raw-response grades, and stop/skip
boundaries, checking internal consistency rather than provider authenticity.
Earlier failures remain closed and unchanged.

Preflight passed all 221 network-zero tests, including eight new checks of
budget-only configuration changes, identical solver invocations, actual SDK
token caps, failure isolation, tampering, old/new validator boundaries, and
private output files. The earlier small repair and 512-token paired reports
still pass offline verification with their original fingerprints.
