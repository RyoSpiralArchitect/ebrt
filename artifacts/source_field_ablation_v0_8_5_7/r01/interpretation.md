# r01 interpretation — supplementary source-field ablation

Recorded on 2026-10-20 JST. This note interprets the sealed
[results](results.json) without modifying the generated [report](report.md),
runner, parser, strict grades, lock, or previous artifacts.

## What ran

After explicit authorization, preparation commit
`5ee39a915804d1e246c45e5d5b4198ea2083a30b` was pushed to the non-main
research branch. The source, recorded calculation, cached snapshot, runtime
versions, and all six rendered inputs matched the sealed preparation.
The 58-check zero-generation self-test passed again before execution.

Both STATE_JSON readiness checks passed. All six planned calls completed:
two readiness calls followed by with/without and without/with source-field
pairs. There were no retries, new calculation calls, downloads, or hosted API
calls. All finish reasons were `stop`; the largest output was 56 tokens,
below the fixed 96-token ceiling. Portable verification replayed all 14
journal entries, projections, prompts, and grades successfully.

The old actual calculation remained a recorded input, not a newly generated
result. The compiler forwarded its numeric fields without the answer label
and without recomputing or correcting its product. Only the supplementary
`rule_evidence_id` field differed between the two final conditions.

## Exact output difference, repeated in reversed order

With source, both calls emitted:

```text
STATE_JSON={"answer":"15_CREDITS","decision_support_ids":["R4"],"revision_event_id":"R6","preserved_constraint_ids":["R5"]}
```

Without source, both calls emitted:

```text
STATE_JSON={"answer":"15_CREDITS","decision_support_ids":["R2","R4","R6"],"revision_event_id":"R6","preserved_constraint_ids":["R5"]}
```

Each arm's two raw outputs are byte-identical. Both with-source outputs also
match the previous v0.8.5.6 product-bridge output byte-for-byte. The literal
answer field says `15_CREDITS` in all four raw outputs, but that observation
does **not** turn invalid public states into graded answer successes.

| Condition | Literal support in raw output | Admitted public states | Strict PASS | Retained failure |
| --- | --- | ---: | ---: | --- |
| With supplementary source | R4 | 2/2 | 0/2 | Required R2 missing |
| Without supplementary source | R2, R4, R6 | 0/2 | 0/2 | R6 overlaps support and revision-event channels |

The unchanged parser rejects both without-source states with
`V0852_STATE_CHANNELS_OVERLAP`. Their R2 text is visibly present, but the
registered `r2_present`, normalized-state comparison, and secondary edit
counts remain unassessed rather than being recovered through a relaxed parser.
The exact raw outputs remain available for descriptive inspection.

For the admitted with-source states, the strict answer check passes while
exact support fails. R2 loss remains one over-edit under the tracked-public-
path diagnostic, with zero missed edits and zero wrong-value edits.

Overall strict final PASS is **0/4**. Both pair comparisons contain complete
generations and changed raw text, but neither has two admitted public states.
There are zero strict repairs, not two successful R2-preservation repairs.
R5 and R6 appear in their expected raw fields throughout; stable fact values
are not emitted and remain unobservable under the legacy contract.

## What this narrows, and what it does not

This bounded intervention produced a repeat-consistent public output
difference under AB/BA ordering. The failure changes from a narrow support
set to a role-overlapping support set. Deleting the supplementary source ID
therefore does not close the strict repair path on this case.

A plausible interface hypothesis is that partial provenance narrows support
too far, while its absence leaves the generator mixing operand evidence with
the correction event. This is not a measurement of private reasoning or proof
that the model internally treats the source ID as the entire support set.
The record's removal changes both field content and ten input tokens. There
is one contaminated case, one model snapshot, greedy decoding, and only two
descriptive repeats per arm. AB/BA does not establish general causal
superiority, equal compute, or performance improvement.

No gradient intervention occurred. The result supplies information about a
generator interface that may later carry EBRT controls; it is not evidence
that EBRT's backward allocation has improved reasoning.

## Smallest candidate follow-up, not executed

The raw task already marks R2/R4 as required support and R6 as the correction,
and the shared prompt already requires pairwise-disjoint output channels.
Adding a correct support list or silently subtracting R6 after generation
would bypass the failure rather than test repair.

A bounded successor could keep the no-source numeric record and all raw
evidence fixed, then move the **existing generic role-separation instructions**
from their early position to immediately after the supplementary record.
Keep the instruction bytes, output schema, and strict grader unchanged; add
no case-specific IDs, expected answer, or gold support. Compare this one
placement change against the frozen current prompt before considering any
core or controller change. This is a proposal, not another authorized run.

No compiler default has been promoted, no old result has been regraded, and
no core, UI, or provider code changed. The six-call budget is exhausted and
closed. The execution claim remains in place.

## Receipts and observed cost

| Call | Input tokens | Output tokens | Finish |
| --- | ---: | ---: | --- |
| state_format | 72 | 46 | stop |
| state_task | 657 | 52 | stop |
| pair1_with_source | 757 | 50 | stop |
| pair1_without_source | 747 | 56 | stop |
| pair2_without_source | 747 | 56 | stop |
| pair2_with_source | 757 | 50 | stop |

Total: 3737 input tokens and 310 output tokens including terminal tokens.
Summed recorded per-call latency: 72862.899 ms, not complete process wall-clock
time or a speed comparison. The old recorded calculation's cost remains
separate from these six new generations.

- Run fingerprint: `000bcf5324141fd47a979c9ee1db77622b6e6c7a8dd24c814bf019f37ddb1a57`.
- Verification fingerprint: `af1151711bc7f1616ca8b73554f779bf9b6496d9aa9225cdb6efc28973437d04`.
- Recorded-source receipt: `0a2ac505635f230184a0d22e430a540e47a34c7867d19416d9ec833d7ee9da25`.
- `results.json` file SHA-256: `2b380abba746b98ea16eda419355c3934ec6ac71a1ccd59c58848238500f2ac8`.
- `journal.jsonl` file SHA-256: `6b3255f089e89b13b21dee9fe96bbb02b2d3d4b825d55094453904cbd068e8ca`.
- `verification.json` file SHA-256: `e2bf2e63eb01418390d587a6638064cd7bde2e76e6b48c45b657d2efa9b11dd6`.
- `report.md` file SHA-256: `40e696782b62153a1bf3a824a9bb69cfb2a85f594964f99ab5a9682066e4416a`.

Hashes check integrity, not authenticity or causal attribution. The portable
verifier does not regenerate text or rerun tokenization.
