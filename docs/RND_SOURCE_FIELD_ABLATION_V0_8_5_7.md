# v0.8.5.7 — Supplementary source-field ablation

Status: **PREPARED; 58 SYNTHETIC CHECKS PASS; ZERO NEW MODEL GENERATIONS**

The [v0.8.5.6 result](RND_PUBLIC_CALCULATION_BRIDGE_V0_8_5_6.md#r01--2026-09-10)
contains a correct public calculation and a correct product-bridge answer,
but both bridge outputs drop required R2. Strict final grades remain 0/3.
R4 is valid factor-bearing evidence; the open question is whether the
**partial supplementary source record** contributes to support collapse.
That is a hypothesis, not a diagnosis already established by the old block.

This successor changes one field on one known case. It adds one auxiliary
[runner](../source_field_ablation_v0_8_5_7.py), not another controller. The core,
existing prompts, parsers, strict graders, and executed artifacts are untouched.

## Fixed recorded source, not a fresh calculator result

The source is the single actual v0.8.5.6 r01 `calculation` terminal:

```text
CALC_JSON={"base_count":5,"multiplier":3,"product":15,"answer":"15_CREDITS","rule_evidence_id":"R4"}
```

Its exact raw bytes are copied from the old artifact, not reconstructed from
this display or semantic gold. Before preparing or verifying a new lock, the
runner checks pinned file hashes for the prior lock, results, journal, and
verification receipt, and runs the unchanged prior portable verifier. The
source receipt retains the old call's input/output cost separately; that call
is not counted as a newly executed calculation.

The compiler drops `answer`, never recomputes or corrects `product`, and
does not add R2 or expected support. A parsed wrong product or known-but-wrong
source ID remains wrong. The experiment is a **contaminated recorded-source
replay**, not evidence that a fresh calculator reliably emits these values.

## Two conditions, in AB then BA order

| Condition | Supplementary record | Final input tokens |
| --- | --- | ---: |
| A: `with_source` | base 5, multiplier 3, product 15, source R4 | 757 |
| B: `without_source` | base 5, multiplier 3, product 15 | 747 |

Only `rule_evidence_id` is removed from the `PUBLIC_CALCULATION_JSON` line.
The complete A prompt is byte-identical to the previous actual product-bridge
dispatch. Complete chronological raw evidence, checking instructions, final
question, choices, and STATE_JSON schema remain byte-identical between A and
B. Raw R4 stays present in both: this is not evidence deletion. The record
remains explicitly unverified supplementary data in both conditions.

Same cached `mlx-community/Mistral-7B-Instruct-v0.3-4bit` snapshot
`a4b8f870474b0eb527f466a03fbc187830d271f5`, seed 0, temperature 0,
fresh per-call KV state, 96 output-token ceiling, no retries or downloads.

| Order | Call | Purpose | Input tokens |
| ---: | --- | --- | ---: |
| 1 | `state_format` | Unchanged literal STATE_JSON readiness | 72 |
| 2 | `state_task` | Unchanged task-shaped strict readiness | 657 |
| 3 | `pair1_with_source` | Pair 1, A | 757 |
| 4 | `pair1_without_source` | Pair 1, B | 747 |
| 5 | `pair2_without_source` | Pair 2, B | 747 |
| 6 | `pair2_with_source` | Pair 2, A | 757 |

Both readiness checks must pass. Otherwise the block stops after two calls
with no final-state denominator. Once admitted, all four planned final calls
remain in the artifact, including generation and format failures. There are
**at most six calls, four final-state cells, and zero fresh calculation calls**.

Reversing the pair order permits a small repeat-consistency check. These are
two descriptive repeats on the same contaminated case, not fresh cases,
independent random samples, or a causal superiority test. Removing the field
also removes ten input tokens; shared output ceilings do not equalize total
compute or isolate the field's semantic meaning from prompt-length effects.

## Readouts: strict repair is still primary

- Preserve each complete raw final output, parsed public state, execution
  status, strict grade, input/output tokens, latency, and finish reason.
- Record answer value and R2 membership separately. An unparsed output has
  unknown R2 membership, not an observed R2 omission.
- Retain the existing miss / over-edit / wrong-value secondary diagnostics.
  R2 was present in the before state: dropping it is an over-edit as well as
  missing required support under the unchanged strict final contract.
- Normalize both pair comparisons from **with source to without source**,
  while retaining the actual execution order. A generation error cannot
  count as a strict repair or regression.
- Compare exact raw outputs and normalized public states within each arm.
  Two identical greedy outputs are a local consistency observation, not an
  estimate of general reliability.

A correct answer with missing R2 is still FAIL. Removal that restores R2 but
breaks the answer is not a successful repair either. Consistent strict repair
would motivate a successor test of this interface, not an immediate compiler
promotion. A null would leave the single-field hypothesis unsupported here;
it would not rule out interactions with the record, instruction, or context.

There is no gradient intervention, private reasoning observation, hidden-state
editing, general reasoning gain, or matched-compute claim. Stable reference
membership is observable; stable fact values absent from the legacy output
schema remain unobservable.

## Lock, execution boundary, and preparation evidence

The [lock](../policy_lock_source_field_ablation_v0_8_5_7.json) binds all ten
source files, the pinned prior-record receipt, all six complete actual prompts,
the schedule, bounds, model identity, and post-call grading contract. Unlike
the previous dynamic bridge, **no synthetic prompt previews are needed**:
the recorded source already exists, so every future dispatch is fixed now.

The [preflight](../artifacts/source_field_ablation_v0_8_5_7/preflight.json)
renders those six inputs with the real cached tokenizer and records seven
snapshot files plus Python/package versions. It does not generate text or
establish model readiness. The runtime must recheck the published non-main
preparation commit and all source/record/preflight bytes before any call.
Each full dispatch is flushed and fsynced before generation. An exclusive
execution claim survives interruptions and prevents a new run with another
output directory. An interruption leaves its partial journal, not a fabricated
complete result.

The [58-check self-test](../artifacts/source_field_ablation_v0_8_5_7/self_test.json)
passes. It covers the actual prior-dispatch byte match, one-field-only change,
uncorrected wrong calculations, parser rejections, AB/BA normalization,
readiness stops, generation errors, journal replay, forged grades, mocked
durable dispatch, interruption retention, and no-retry enforcement.
All new generator outputs in these tests are synthetic.

- Self-test fingerprint:
  `17cb46c49892d3fe3c9ac229cdddb3f88012bdc2171f2d6b83600b6367369d35`.
- Lock fingerprint:
  `4e5084f51512bdc28d5a4599662851a94c1818d5ea84e7b36a98b9a929e6d331`.
- Preflight fingerprint:
  `f6b85b3946b4ed3b515ba15d2b1243bd6c910a8b7fcf610ba7ea0ffee0e41952`.
- Recorded-source receipt fingerprint:
  `0a2ac505635f230184a0d22e430a540e47a34c7867d19416d9ec833d7ee9da25`.

```sh
python3 source_field_ablation_v0_8_5_7.py self-test
```

At preparation, no v0.8.5.7 live result or execution claim exists. After
separate authorization, push the preparation commit, then invoke `run` with
that exact commit, the cached snapshot, lock, preflight, a fresh output
directory, and `--execute-local-once`. Do not rerun to obtain a preferred
answer. After the authorized block, the portable verifier command is:

```sh
python3 source_field_ablation_v0_8_5_7.py verify \
  artifacts/source_field_ablation_v0_8_5_7/r01/results.json \
  --lock policy_lock_source_field_ablation_v0_8_5_7.json
```

Verification recomputes source binding, projections, prompts, readiness,
grades, pair diagnostics, and journal correspondence without generation.
It checks recorded tokenization for internal consistency, not by retokenizing.
Hashes establish integrity, not signatures or independent proof of execution.
