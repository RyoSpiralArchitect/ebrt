# Non-unique coloring with an LLM judge

Status: **FIRST BLOCK STOPPED AT QUOTATION VALIDATION; FOLLOW-UP PREFLIGHT**

This example exercises dependency-aware source reinspection with a free JSON
answer. It evaluates feasibility rather than equality to one reference answer.
An LLM judge receives each candidate in a fresh request, and an independent
predicate checker grades the same constraints.

## Problem

Assign RED, GREEN, or BLUE to vertices A through F. Using all three colors is
not required: any subset of the palette is allowed. Vertex A must be RED.
Endpoints of every current edge must have different colors:

```text
AB, BC, CD, DE, EF, FA, BE
```

The six cycle edges existed first; the late correction adds BE. With A fixed,
the current problem has 18 feasible colorings. The count is checked offline
by exhaustive enumeration. Neither the enumeration nor calibration solutions
is supplied to the answer generator.

The model constructs a free object containing `colors` and `support_ids`.
Internal controller placeholders needed by the historical typed task are
withheld from the terminal prompt. The example does not put feasible
colorings into `answer_choices` or invent one expected color assignment.
The mathematical feasibility grade ignores support metadata; source lineage
and native output format are recorded separately. Extractable valid colors
remain mathematically valid even if citation metadata is missing or malformed.

## Execution and judging

The fixed block permits at most eight provider attempts, without retries:

1. Three dependency-ordered source extractions, using the existing per-site
   budget and validated parent-quotation transport.
2. One free JSON solution generation using complete evidence and the verified
   excerpts, through a separately versioned terminal protocol.
3. Four stateless judge requests: the generated candidate, two distinct
   predeclared feasible controls, and a predeclared candidate that violates
   only the newly added BE edge.

Judge prompts contain only the corrected problem, the fixed rubric, and the
candidate as quoted untrusted data. They do not identify the candidate's
source, model, control status, deterministic grade, or a reference solution.
Each request uses a fresh context and the same rubric and generation settings.
An explicitly configured judge model can differ from the solver; using the
same backend does not constitute independent-model validation.

The ten criteria are exact vertex coverage, allowed colors, fixed A, and
the seven edge inequalities. The judge returns criterion booleans, a PASS/FAIL
verdict, and brief concrete violations. Contradictory or malformed judge
outputs are retained as protocol failures, without repair. A well-formed
incorrect judgment remains a recorded disagreement with the predicate
checker. Mathematical failure or disagreement does not select another
candidate or alter the fixed judging schedule.

Provider and pre-dispatch failures stop the block. A completed but malformed
solver response is still available to judge as raw candidate data; it is
not silently rewritten. Every attempted stage is recorded explicitly. Shared
source extractions are not hidden inside a one-call generation receipt.

## Controls and interpretation

Two distinct valid controls test acceptance beyond a single canonical answer.
The negative control satisfies all six old cycle edges and the fixed color,
but gives B and E the same color. It tests whether the added constraint is
actually enforced. Control assignments are fixed before generation and are
never used as solver examples.

This is a small development example, not a comparison demonstrating better
reasoning or a general evaluation of judge reliability. Checker/LLM agreement
on these candidates is reported independently of source provenance, output
format, and citation lineage. No gradient crosses the hosted solver or judge.

Source, problem, controls, rubric, settings, and call budget are fixed before
the first request. Earlier evaluation blocks remain closed. Detailed provider
receipts remain in new private files outside the checkout.

## Offline validation

All 185 network-zero tests passed, including 27 new coloring/judge checks.
These cover the independently enumerated 18 solutions, distinct two-color and
three-color witnesses, the BE-only negative control, absence of reference
assignments and controller placeholders from solver prompts, blind judge
requests, actual eight-stage accounting, preserved disagreements, malformed
responses, source/grade tampering, and private output files.

Independent adversarial review found no required fixes. Mathematical validity
of extractable colors remains assessable when citation metadata or the native
output wrapper is malformed; the raw response and separate format failure are
preserved. Earlier execution sources and closed blocks are unchanged.

## Recorded first-block failure

The first plan was fixed at source
`2564e334b4f8c2e106587a4424bf60ca2ca4fd27` before any request. It stopped
after three source-audit attempts, with no solver or judge calls. The table
audit joined the PROFILE_N edge sentence to a general inequality sentence,
skipping another profile between them in the original paragraph. That string
was not a contiguous source substring, and provenance validation correctly
rejected it with `REINSPECTION_AUDIT_QUOTE_NOT_IN_SOURCE`.

The failed report remains unchanged. Offline consistency verification passed
for its three attempted stages while execution remained FAIL. The closed
block was not resumed or repaired, and no candidate/judge outcome had been
observed.

For a separately declared follow-up block, each profile's edge list and
inequality rule are placed adjacently on one source-record line. The graph,
18-solution set, controls, judge rubric, budget, and strict quotation validator
are unchanged. This input-layout adaptation addresses the observed extraction
failure; it is not evidence of robust extraction or an untouched benchmark.
The follow-up permits at most eight new attempts, with no further automatic
layout tuning or retries. Including the three recorded attempts gives a
maximum of eleven actual requests across these two blocks.

First plan fingerprint:

```text
3914165249492f9e6b89c5763cf471d26bfc5a42f298b23c792ba5bbe630da0d
```

First failed report fingerprint:

```text
fb2d6b12ee0a4e0ac7d0e416e7fb73e0d88fc18461b38fc7bd8e7ed5357dfbfa
```

The original source snapshot and failed plan/report are retained locally.
Replay that report against the recorded source revision; do not rewrite its
hashes or grades to match the follow-up layout.

Follow-up preflight passed all 187 network-zero tests (29 coloring tests).
The two added regressions accept each contiguous profile record and still
reject stitched fragments after three attempts, before solver/judge dispatch.
Independent review found no required implementation fixes.
