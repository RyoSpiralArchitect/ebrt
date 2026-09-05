# v0.8.5.5 r01 — post-run interpretation

Date: 2026-09-06. Added after the sealed execution. This commentary does not
replace the generated report, change any grading, or authorize another run.

## The final-state failure is unchanged

All three final-state prompts returned the exact same public text:

```text
STATE_JSON={"answer":"45_CREDITS","decision_support_ids":["R2","R4"],"revision_event_id":"R6","preserved_constraint_ids":["R5"]}
```

The final-state strict outcome is **0/3 PASS**. The reference, choice reversal,
and explicit R2-by-R4 query all retain the old answer. Each correctly repairs
the support references and preserves the required reference, but misses the
`/answer` change to `15_CREDITS`. There are no new over-edits and no strict
repairs against the new reference. Identical final text also means no raw or
normalized public output diff between these three probes.

The answer remains 45 even when 15 is first in the choice list. A literal
always-return-the-first-choice account does not describe this pair. This
does not rule out other choice-format effects or establish an internal cause.

## The new component formats did not all survive generation

| Component | Formal result | Literal generated text / observation |
| --- | --- | --- |
| Full-context public computation | FORMAT_ERROR | Multiline JSON without `CALC_JSON=`; numeric fields 5, 3, 15; answer `15_CREDITS`; rule ID R6 |
| Isolated multiplication | FORMAT_ERROR | `{"result":15}` lacks `ARITHMETIC_JSON=` and the required `product` key |
| Given-value label selection | PASS | `LABEL_JSON={"answer":"15_CREDITS"}` |

The full-context computation text was:

```text
{
  "base_count": 5,
  "multiplier": 3,
  "product": 15,
  "answer": "15_CREDITS",
  "rule_evidence_id": "R6"
}
```

Both failed components remain `V0855_COMPONENT_LINE_INVALID`, with
`public_values = null` and `checks = null`. No whitespace/prefix repair or
key remapping is applied. Numeric text is retained as a lead, **not a component
PASS**. R6 names the correction event; the registered factor-source ID is R4.
Accepting bare JSON would not resolve that separate provenance mismatch.

The one passing component already receives amount 15 in its prompt. It shows
the requested label mapping in that assisted invocation, not an end-to-end
repair. None of the component outputs was fed to another call.

## What this does and does not locate

This block does not identify whether the reference fails at rule selection,
arithmetic, or final readout. The new component protocols had no independent
live readiness gate: the two gates admitted the existing STATE_JSON protocol
only. That measurement limitation is now visible and must remain separate
from algorithm quality.

The appearance of the right numeric result in raw text motivates a narrower
follow-up, but neither demonstrates reliable arithmetic nor reveals private
reasoning. Conversely, the rejected format is not evidence that multiplication
is beyond the model. No gradient intervention was evaluated in this block.

The next bounded change should establish the component contract itself with
an explicit shape and independent readiness, including distinct factor-source
and correction-event roles. Keep the same strict criteria and preserve this
failed block. A subsequent public calculation record to final-state bridge
is a hypothesis to test after that gate, not a runtime change made here.

## Execution and preservation

- Lock commit pushed before execution:
  `c4f6079b40eba6500ce25b4b75ed2f2557b940b5`.
- 8 unique logical calls; 8 complete generations; no retries or generation errors.
- Both legacy readiness checks PASS. Every finish reason is `stop`.
- Maximum observed output length: 59 tokens, below the fixed ceiling of 96.
- Total input tokens: 3333; total output tokens including terminal tokens: 340.
- Portable verification PASS, including exact 18-entry dispatch/terminal journal.
- Verification did not execute a model or retokenize the prompts.
- Frozen runner, lock, preflight, core, and historical artifacts are unchanged.

Artifact fingerprint:
`2e2f57885c1d6de0269400338b4c6ed8121da25a261a00cb5226b103dda48a50`.

File SHA-256 values before this commentary was added:

| File | SHA-256 |
| --- | --- |
| results.json | `98b69523aa70c5157ee2be8442c27544cf6666f545704adb8cc8945545e87e0b` |
| journal.jsonl | `a038d672c59a2a9d39945aa7ad5d64de6c7f779fe6b2793ac7c3c0cd01499b44` |
| verification.json | `9f3c9b6280d38d1c4335ec39b388d08dd1477275d3f6a210690ea307d45613b3` |
| report.md | `ad1f013c89a42bbb48624d04d4ba2b92a3f6e445c955b19818475c3ee36c6c06` |

`effect_attribution` remains `NOT_ASSESSED`.
`diagnostic_cause` remains `NOT_IDENTIFIED_SINGLE_INDEPENDENT_PROBES`.
