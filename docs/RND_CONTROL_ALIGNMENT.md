# Control alignment and evidence placement diagnostic

Status: **READY FOR PREDECLARED EXECUTION**

Coverage-first selection now prevents omission of caller-declared required
support in the standard single-lane engine. The previous three-case hosted
block found no generation benefit from that selection repair. This next
diagnostic asks whether the mapping of gradient-derived numeric controls to
selected sites changes outputs when coverage and instruction text are held
fixed, and examines evidence ordering as a separate factor.

## Fixed comparison

Two fresh engineered tasks contain a relevant evidence chain and an active
competing chain. Each task uses all its evidence in all four conditions:

| Case | Relevant join | Expected revision | Competing chain |
| --- | --- | --- | --- |
| Invoice handling fee | Invoice → account → region and contract | `11_CREDITS` → `5_CREDITS` | Another invoice still owes `11_CREDITS` |
| Booking capacity | Booking → group and session → size/capacity comparison | `CONFIRM` → `CONFIRM` | Another booking remains `WAITLIST` |

`R2` and `R4` supply the observation and current rule; `R6` authorizes the
revision without restating the target answer. `R1` remains valid for the other
entity, but citing it as support for the queried entity fails the post-run
contract, as does citing retired `R3`. The unchanged-answer booking case
checks that a correction does not automatically require an answer flip.

| Arm | Numeric tuple-to-site mapping | Evidence record order |
| --- | --- | --- |
| `aligned_chronological` | Original coverage-first controls | Chronological |
| `permuted_chronological` | Fixed one-position rotation | Chronological |
| `aligned_credit_first` | Original coverage-first controls | Selected sites first, suppressed sites last |
| `permuted_credit_first` | Fixed one-position rotation | Selected sites first, suppressed sites last |

The aligned program uses the verified backward trajectory and the standard
coverage-first compiler. The perturbed program rotates each pair of
allocation units and signed control among the same three selected IDs. It
preserves the tuple multiset, selected-control L2 norm, three slots, and 100
positive allocation units. This is an auxiliary experimental perturbation;
the standard engine continues to reject it as a control-binding violation.

Within each alignment pair, the selected-ID order in `REINSPECT_JSON` stays
fixed and only the assignment of numeric tuples changes. Within each
placement pair, the program stays fixed and only `EVIDENCE_JSON` record order
changes. Evidence text, task data, suppression, preservation, and all generator
instructions are identical. The plan checks these differences before any
provider call and rejects a no-op permutation.

The plan records the cases, post-run contracts, verified trajectories,
programs, actual prompts, source hashes, generation settings, and rotated
schedule before execution. There is one attempt per cell, at most eight
provider attempts, with no retries. A failed request spends its cell; outcomes
do not trigger an extra block. Two cases cannot fully balance all four serial
positions, so order and provider variation remain limitations.

## Verification and interpretation

The offline verifier rebuilds the plan, reparses visible outputs, and
recomputes output grades, coverage, uptake, paired differences, and summaries.
Failed or malformed outputs remain in the report. A paired comparison with an
unparsed member is not assessed. Execution, receipt integrity, and output
quality have separate statuses. Receipt verification checks internal
consistency and does not authenticate the provider.
The uptake metric checks retention of compiled required-support IDs in the
visible answer, not use of their numeric allocations or signed controls.

This is a conditional diagnostic of numeric alignment and evidence ordering
under a shared textual revision program. Both alignment conditions retain the
same gradient-derived selected-ID ranking. "Aligned" means the original core
mapping, without assuming semantic correctness or optimality. The numeric
intervention moves allocation and signed control together and cannot separate
their individual effects. The public geometry and roles are
hand-built, and the generator remains outside autograd. This design does not
establish that the gradient is semantically calibrated, that a gradient-based
optimizer outperforms alternatives, or that general reasoning improves.

Provider identifiers, usage, timings, and full response receipts stay in new
local files outside the checkout with mode `0600`. The committed note will
record aggregate results, including null outcomes and failures.

Validation passed all 98 network-zero tests across the demo, hosted runtime,
support diagnostic, standard engine, and new alignment diagnostic. The 23 new
tests cover actual prompt difference scopes, semantic entity joins, distractor
lineage, real backward execution, gold noninterference, failed-attempt limits,
unparsed comparisons, source/grade tampering, and private output files.
A separate adversarial review found no required changes after inspecting the
matched prompt boundaries, experimental admission, and report reconstruction.
