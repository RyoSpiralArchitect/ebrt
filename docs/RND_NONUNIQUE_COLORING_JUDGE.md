# Non-unique coloring with an LLM judge

Status: **OFFLINE VERIFIED; READY FOR FIXED EIGHT-ATTEMPT BLOCK**

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
