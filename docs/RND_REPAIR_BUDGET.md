# Matched 4096-token follow-up on the fixed cascade cases

Status: **EXECUTED; BOTH CONDITIONS FOUND MINIMAL REPAIRS IN ALL THREE CASES**

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

## Executed results: 2026-10-26 (Asia/Tokyo)

Source was fixed at `2a385efb6b3a62f5fdca93c5399e8b3ddc1b364b` before saving
the plan and dispatching requests. Its bound baseline plan fingerprint is
`c98f49944e7c138a9110afeff2dcefb9b8b4ed6e4b79627e02819ac1251c22ef`, the exact
closed 512-token paired block. All twelve requests completed without retries,
skips, or model drift; requested and returned model was `gpt-5.6-sol`.

| Case | Exact minimum changes | Full repair changes | Gradient feedback changes | Both feasible | Both LLM verdicts |
| --- | --- | --- | --- | --- | --- |
| cascade-10 | 5 | 5 | 5 | PASS | PASS |
| cascade-14 | 8 | 8 | 8 | PASS | PASS |
| cascade-18 | 9 | 9 | 9 | PASS | PASS |

Completed, feasible, and exactly minimal repairs were all 3/3 for each
condition. All six candidates passed native output-format checks. Every judge
criterion agreed with the mechanical checker. A separate direct check of raw
candidate colors confirmed all current edges, A=RED, palette/coverage, and
the reported changed vertices. Exhaustive optima were already independently
verified before generation. The judges did not determine minimality.

There was no observed feasibility or edit-optimality advantage from gradient
feedback. Unlike the 512-token block, this block supports a quality comparison
on completed answers. It does not establish equal quality in general or a
causal effect of budget, because cases are engineered and each arm has one
fixed-order sample per case.

Actual color assignments are listed below in ascending vertex order. The
two conditions found different optima for 10 and 18 vertices; they found the
same optimum for 14 vertices. R=RED, G=GREEN, B=BLUE:

| Case | Condition | Colors in A onward order | Changed vertices |
| --- | --- | --- | --- |
| 10 | Full repair | R R B G B R G R B B | C D E F H |
| 10 | Gradient feedback | R R G B G R B R G B | E F G H I |
| 14 | Full repair | R B R B B G R G G G G R G B | C G H J K L M N |
| 14 | Gradient feedback | R B R B B G R G G G G R G B | C G H J K L M N |
| 18 | Full repair | R G B R B B B G B G G R R R G B G R | B C G H J K O Q R |
| 18 | Gradient feedback | R G B R B R B G B G G R R R B B G R | B C F G H J K Q R |

## Actual provider-reported token usage

These are solver-only observations, not the requested ceilings:

| Case | Condition | Input | Output (includes reasoning) | Reasoning | Total |
| --- | --- | ---: | ---: | ---: | ---: |
| 10 | Full repair | 335 | 2326 | 2263 | 2661 |
| 10 | Gradient feedback | 591 | 2647 | 2584 | 3238 |
| 14 | Full repair | 459 | 2117 | 2038 | 2576 |
| 14 | Gradient feedback | 813 | 1998 | 1919 | 2811 |
| 18 | Full repair | 528 | 2683 | 2588 | 3211 |
| 18 | Gradient feedback | 983 | 2038 | 1943 | 3021 |
| All three | Full repair | 1322 | 7126 | 6889 | 8448 |
| All three | Gradient feedback | 2387 | 6683 | 6446 | 9070 |

Feedback used fewer output/reasoning tokens in two cases and more in one.
Its combined input-plus-output total was higher, owing to the additional
input record. These single samples do not establish an efficiency advantage;
unweighted token totals are not billing cost or consumed compute. The six
judges separately consumed 3616 input and 2024 output tokens. All twelve
requests together consumed 23158 reported total tokens.

Collection COMPLETE, execution PASS, and offline integrity verification PASS
were recorded separately. Verification reconstructed all twelve attempts.
Plans, raw reports, and verification receipts remain in private 0600 files
outside the checkout. The new block adds twelve actual requests; including
the two preceding cascade blocks' seven attempts gives nineteen, with all
failures retained. No further sampling or budget adjustment followed.

```text
plan:   2af69d33951b755b164bce2c4a7dfee956c3f789d40e90433519a3ccf4de68e0
report: f567a781d058fef517eac2599fab1a2b21ba551a561ea6b7f7ac2c1a79bfd20b
verify: 6e7634df74109190e0c9e7bd337ab479cba2808f22ce362e1fb6213b49935713
```
