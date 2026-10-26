# Minimal coloring repair after a constraint change

Status: **EXECUTED; BOTH CONDITIONS FOUND THE SAME MINIMAL REPAIR**

The prior assignment A–F = RED, GREEN, RED, BLUE, GREEN, BLUE satisfies the
six-cycle AB, BC, CD, DE, EF, FA with A fixed RED. Adding BE invalidates it.
There are 18 feasible revised assignments. Exactly two change only one vertex:
B to BLUE or E to RED. Enumeration supplies post-run minimality grades only;
neither solution nor the optimal count is placed in a solver prompt.

`ebrt_coloring_repair.py` is a terminal repair experiment using the existing
hosted runtime and coloring predicates. It does not perform source audits.
The previous solution is now explicit state. A float64 one-hot representation
of that state is differentiable: sum the color-vector dot products over
currently violated edges, then call backward. Here the scalar loss is 1,
and only B and E have nonzero gradient, each [0,1,0] in RED/GREEN/BLUE order.
Fixed vertices are excluded from the suggested actuation set. The continuous
surrogate is public, caller-constructed state; hosted generation stays beyond
an autograd boundary. This is not a model-native gradient or a demonstrated
extension of the existing credit trajectory.

Both conditions receive the same current graph, prior colors, added edge,
minimum-change objective, schema, and generation settings. The only prompt
change is a feedback JSON record: null for `full_repair`, the actual surrogate
loss/gradients and suggested vertices for `gradient_feedback`. Suggestions
are not a hard restriction. All current edges are checked after generation.
The feedback treatment also supplies explicit collision localization, so any
observed difference cannot isolate gradients from that additional information.

The frozen schedule is two independent solver requests followed by two blind
feasibility judgments, four attempts maximum, no retries or repairs. Each call
has the same 512-output-token ceiling, low effort, and configured model.
Equal output ceilings do not imply equal input tokens or consumed compute.
Judges see only the corrected problem and candidate, not the condition, prior
state, gradient, edit count, or mechanical result. The existing ten-criterion
rubric judges feasibility; minimality is assessed by exhaustive enumeration.
The judge is the same configured backend in a fresh context.

The report records raw candidates, changed vertices/count, feasibility,
minimality, output format, lineage, and judge agreement separately. A malformed
or infeasible completed candidate is still judged. Well-formed disagreements
do not change the schedule. Provider failures, returned-model drift, and judge
format failures stop subsequent requests. Execution PASS means all four stages
completed their protocols; candidate validity/minimality must be read separately.
Support IDs preserve the previous coloring JSON convention; they do not prove
new source audits took place in this terminal experiment.

Plans pin the prior state, problem, feedback, settings, schedule, source hashes,
and Torch version before requests. Offline verification reconstructs requests,
stop boundaries, grades, and counts from raw records. It checks internal
consistency, not provider authenticity. Prior closed experiments remain intact.

Run from the checkout with private outputs outside it:

```bash
python ebrt_coloring_repair.py plan --output /tmp/repair-plan.json
python ebrt_coloring_repair.py run --plan /tmp/repair-plan.json --output /tmp/repair-report.json
python ebrt_coloring_repair.py verify --plan /tmp/repair-plan.json --report /tmp/repair-report.json --output /tmp/repair-verification.json
```

This single simple case, fixed execution order, and same-backend judgments
cannot establish a general quality or causal advantage. It tests whether the
prior-state repair path operates and whether either condition reaches a known
minimal repair.

## Executed block: 2026-10-26 (Asia/Tokyo)

Source was fixed at `dc1400ecd1239320fce3fa82ef2ed3d9eb3bb4a4` before
planning and execution. All four attempts completed, without retries.
Requested and returned model was `gpt-5.6-sol`; requested output ceilings
totaled 2048 tokens. Both solver responses were byte-identical:

```json
{"colors":{"A":"RED","B":"BLUE","C":"RED","D":"BLUE","E":"GREEN","F":"BLUE"},"support_ids":["R2","R4","R6"]}
```

| Condition | Changed vertices | Change count | Feasible | Minimal | LLM feasibility |
| --- | --- | --- | --- | --- | --- |
| Full repair without feedback | B: GREEN → BLUE | 1 | PASS | PASS | PASS |
| Repair with gradient feedback | B: GREEN → BLUE | 1 | PASS | PASS | PASS |

Both candidates preserved A and every other vertex, passed native format and
lineage metadata checks, and satisfied all seven current edges. Both judges
agreed with all ten mechanical feasibility criteria. Minimality was established
by exhaustive checking, not by the feasibility judge. These are two independent
requests yielding the same assignment, not two distinct repaired solutions.
No repair-quality or edit-count advantage from feedback was observed.

All 199 network-zero tests passed, including 12 new repair checks. They cover
independent enumeration of the two minimal repairs, numerical finite-difference
verification of the actual backward gradients, absence of solution/optimum
leakage, blind judging, nonminimal and malformed candidates, preserved
disagreements, provider/model/judge failures, hidden retries, report tampering,
and rejection of truncated successful reports. Offline replay passed for all
four stages. Raw outputs and report fields were also inspected against the
problem and prior state. Earlier runtime sources were not edited.

The plan, report, and verification remain in private `0600` files outside the
checkout. Their respective fingerprints are:

```text
plan:   26d9a42ea9bb129c82304f71b036eaa61ff048b5b3b8a841761a61bc30e81fc3
report: d80af0d9f2abfd7c2daadf83574007e40997848cba2e1019ad0754a3b5d519cb
verify: 1d3454b77f65f8cb37276fe42f2dfab5afd05339a37a4664bc35cb6933c60119
```
