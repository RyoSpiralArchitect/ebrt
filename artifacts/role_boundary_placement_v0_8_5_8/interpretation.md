# v0.8.5.8 r01 — Role placement reaches three generators, with opposite directions

Post-run interpretation, 2026-10-20. This file adds no calls or regrading.
The sealed protocol, source, profiles, results, and journals remain unchanged.

## Execution receipt

Preparation commit: `fb5a89ccb09ec8acf12d3793ba2217642ccde4f5`.
Protocol fingerprint:
`6c701e951dc8088301ece340044f477d118de336269762810bfed8d11dd0947f`.

One shared public-input protocol, three separately sealed backend profiles.
Each block contains two readiness calls, then early/late/late/early finals.
All three completed exactly 6/6 planned generations; both readiness checks
passed in each. There were no retries, fallback generators, additional
calculation calls, or post-observation prompt adjustments. Eighteen is the
execution total, **not** a pooled quality denominator.

| Backend | Parsed finals | Early strict PASS | Late strict PASS | Portable verification |
| --- | ---: | ---: | ---: | --- |
| Mac MLX, Mistral 7B v0.3 4-bit | 0/4 | 0/2 | 0/2 | PASS |
| Furnace, Mistral 7B v0.3 bf16 / TensorRT-LLM | 2/4 | 2/2 | 0/2 | PASS |
| OpenAI API, gpt-5.6-sol / low effort | 4/4 | 0/2 | 2/2 | PASS |

Verification was rerun locally after the remote artifacts were collected.
Each fourteen-entry journal matches its sealed dispatches, terminals, and
final artifact. This is a consistency check, not a cryptographic proof of
provider execution. The 36-check synthetic self-test is independent of these
real-model readiness and final-quality results.

## What changed

Only the location of five pre-existing generic role-boundary instructions:
from their previous early location to immediately after the supplementary
numeric record. Full evidence, instruction text, line multiset, byte length,
numeric record, question, choices, schema, and strict grading stay fixed.
The record is the same actual prior calculation, with its answer label and
source ID dropped. Its product is not recomputed or replaced by a gold value.

Both repetitions of each arm emitted identical raw text within that backend.
The strings below are the actual first-pair terminals, not reconstructed or
repaired states. Second-pair terminals remain in each linked result.

### Mac MLX — raw difference, still no admitted state

Early:

```text
STATE_JSON={"answer":"15_CREDITS","decision_support_ids":["R2","R4","R6"],"revision_event_id":"R6","preserved_constraint_ids":["R5"]}
```

Late:

```text
STATE_JSON={"answer":"15_CREDITS","decision_support_ids":["R4","R6"],"revision_event_id":"R6","preserved_constraint_ids":["R5"]}
```

Both are rejected with `V0852_STATE_CHANNELS_OVERLAP`: R6 occupies both
decision-support and revision-event destinations. Late also lacks R2 in its
raw support list. That is a raw-text observation, not an admitted edit grade.
All four tracked edit diagnostics remain
`NOT_ASSESSED_INVALID_PUBLIC_STATE`. Normalized paired answer/state changes
are null, not false or successful preservation. Strict passes remain 0/4.

### Furnace — early passes; late breaks the role boundary

Early:

```text
STATE_JSON={"answer":"15_CREDITS","decision_support_ids":["R2","R4"],"preserved_constraint_ids":["R5"],"revision_event_id":"R6"}
```

Late:

```text
STATE_JSON={"answer":"15_CREDITS","decision_support_ids":["R1","R2","R4","R6"],"revision_event_id":"R6","preserved_constraint_ids":["R5"]}
```

Early has exact support R2/R4, event R6, and preserved reference R5, and
passes the complete unchanged contract. Late adds R1 and R6 to support;
R6 overlap makes it an invalid public state. Both early-to-late comparisons
are strict regressions, even though their normalized semantic differences
cannot be assessed. No parser repair removes the overlapping reference.

### OpenAI API — late removes an over-edit and passes

Early:

```text
STATE_JSON={"answer":"15_CREDITS","decision_support_ids":["R2","R4"],"preserved_constraint_ids":["R1","R5"],"revision_event_id":"R6"}
```

Late:

```text
STATE_JSON={"answer":"15_CREDITS","decision_support_ids":["R2","R4"],"preserved_constraint_ids":["R5"],"revision_event_id":"R6"}
```

All four states parse. Early has one tracked over-edit at
`/preserved_constraint_ids/R1`; late has zero tracked misses, over-edits, or
wrong values and passes the full contract. Both normalized pairs report a
strict repair and a public-state difference, with no answer change.

The edit baseline is the existing caller-supplied prior state, not a new
Before generation. Its pre-event revision-event ID is unknown. The schema
reports stable references, not stable fact values; neither is inferred from
zero tracked errors. The actual API reports zero reasoning tokens for these
six responses; that count does not expose or measure internal reasoning.

## Usage, completion, and remote boundary

| Backend | Input tokens | Output tokens | Sum of recorded call latency |
| --- | ---: | ---: | ---: |
| MLX | 3,717 | 316 | 85.066 s |
| Furnace | 3,705 | 322 | 21.307 s |
| API | 2,917 | 245 | 14.835 s |

These totals include readiness. They are operational receipts, not a speed,
compute, or cost ranking. Furnace's first call includes load/compilation;
rendering, token accounting, weights/quantization, output ceilings, and
runtime policies differ. Local reasoning-token counts are unavailable, not
observed zero. All local terminals report `stop` below the 96-token ceiling;
all API terminals report `completed` below the 2048-token ceiling.

The API's maximum pre-dispatch reservation was 260345 micro-USD against a
400000 micro-USD block ceiling at the recorded rate card. Actual usage is
shown above, but actual billing is not recorded: `NOT_AN_INVOICE`.
Metadata and input-count requests are separate from the six generations.
No credentials appear in these public artifacts.

Furnace ran in its isolated scratch checkout through the managed
`spiral-local-llm` launcher. No runtime/environment package was changed.
Existing modelopt/transformers, compilation, and context-block warnings were
observed; the run is not described as warning-free. All six calls completed,
and a subsequent GPU process query showed no remaining compute process.
The collected results remain both locally and on Furnace.

## Interpretation and next gate

The shared compiler protocol now has real Mac, Furnace, and hosted API
execution receipts. It reaches actual final generation, with repeated raw
output differences in every block. That is an operational portability result.

It is **not** a universal late-placement repair: API improves under its strict
contract while Furnace regresses, and MLX remains invalid. Do not pool these
cells, compare model quality at matched compute, attribute the reversal to
quantization alone, or infer provider hidden-state/attention behavior.
AB/BA repeats of one known case are not independent fresh-case replication.
Recorded attribution remains `NOT_ESTABLISHED_ONE_KNOWN_CASE`.

No gradient intervention occurs in this comparison. It diagnoses the final
public-state compiler boundary, not the backward controller's quality. Core,
UI, and default compiler remain unchanged. No backend-name routing rule or
automatic winning-arm selector is introduced from this record.

The smallest proposed successor is a fresh, predeclared transfer block with
new numeric revisions and evidence-ID/order variants, keeping this same
generic transformation and role contract. Check direction and strict repair
within each backend, preserving invalid outputs separately. It needs a new
lock and bounded execution authorization; r01 is not repeated or extended.

## Artifact fingerprints

| Run | Sealed artifact fingerprint | Verification fingerprint |
| --- | --- | --- |
| [MLX](mlx_r01/results.json) | `3d3d3bfc71c2608161adc665670efc5ee9bb975bace2556d034ef0633a785839` | `4c88eab7579902cd04c0756e753920e4014fc874a14e757f2c1df6dc9bf50b0f` |
| [Furnace](furnace_r01/results.json) | `e310bfb09ec64aa0404501e6590af1aeb46a97b785aa6b5a58bd588e54d2979c` | `c4a88edf424ecb33319f617c03d4ea15e09102fc05b93072e6a0bbc746b78fd1` |
| [API](openai_r01/results.json) | `8b9c125281148b42b3a23cea98aa3321f7ec94ce7950e9923c6e4d572610c050` | `110a2905385dc487ec2bf35046b80abbd07af0d4e31a14f674376792e978b8a0` |

See the [protocol and operation note](../../docs/RND_ROLE_BOUNDARY_PLACEMENT_V0_8_5_8.md)
for model snapshots, profile fingerprints, preparation, and verifier commands.
