# v0.8.5.5 — Numeric revision diagnosis

Status: **COMPLETE EIGHT-CALL BLOCK; NO FINAL REPAIR; TWO COMPONENT FORMAT FAILURES**

The v0.8.5.4 credit case cites R2/R4, identifies R6, and preserves the R5
reference, yet all three outputs still say `45_CREDITS` instead of
`15_CREDITS`. Before changing the controller again, isolate observable rule
selection, arithmetic, and answer-label behavior on that one known case.

Implementation stays in one auxiliary
[runner](../numeric_revision_diagnostic_v0_8_5_5.py). The core monolith,
legacy output parser/grader, prior locks, and all earlier run artifacts are
unchanged. This is not another multi-arm algorithm benchmark.

## Paper connection, and the important distinction

[What Else Needs Fixing?](https://arxiv.org/html/2609.03254v1#S2.SS4)
evaluates revision propagation on conversational JSON artifacts. Section 2.4
keeps complete artifact correctness as the primary outcome and separates
omitted required changes, unnecessary changes, and incorrect changed values.
We borrow that diagnostic distinction, not its dataset, patch implementation,
optional-edit rules, sampling methods, or published performance claims.

Our adaptation compares registered public paths against a caller-supplied
before state and a post-call target:

| Required change? | Observed state | Classification |
| --- | --- | --- |
| Yes | Still equal to before | `miss` |
| Yes | Changed, but not to the target | `wrong_value` |
| No | Changed anyway | `over_edit` |
| Either | Equal to target | No error on that path |

Consequently **45 → 45 is a missed revision**, even though the old strict
answer-value check also correctly fails. A hypothetical 45 → 30 would be a
wrong-value edit. The legacy two-choice schema does not admit `30_CREDITS`:
we keep that rejection, rather than expanding the answer space to populate a
new metric. A zero count for `wrong_value` here is not evidence of good
arithmetic. The separate numeric component schema can record other integer
products without changing the final-state contract.

For support, we compare evidence membership, not list position. Dropping R2,
which was present before and must remain present, is an **over-edit** under
this lens; failing to add newly required R4 is a **miss**. The legacy
`decision_support_exact` test still rejects both.

## Prior-output audit: no model calls, no replacement grades

[Secondary audit](../artifacts/numeric_revision_diagnostic_v0_8_5_5/previous_run_edit_audit.json)
first verifies the original v0.8.5.4 artifact and copies its strict grades
unchanged. It then adds path diagnostics in a new namespace.

| Prior arm | Parsed / available | Missed paths | Over-edited paths | Wrong-value edited paths |
| --- | ---: | ---: | ---: | ---: |
| baseline | 4/4 | 1 | 0 | 0 |
| append | 4/4 | 1 | 1 | 0 |
| prepend | 3/4 | 1 | 2 | 0 |

The three misses are the unchanged credit answer. The three over-edits are
R2 omissions in archive/prepend and permit/append + prepend. Freight/prepend
remains an unparsed channel-overlap error, not an edit-error count.

Each parsed output has 13 tracked paths: answer and membership of each of the
six evidence IDs in the support and preserved-reference channels. The prior
support set is partitioned by the caller's stable-evidence annotation. This
is an explicitly recorded projection of the caller's prior public state,
**not a previously emitted typed-state output**. The pre-event revision ID is
unknown and omitted from path comparison; the unchanged strict grader still
checks the actual post-event revision ID. Stable fact values are not emitted
and cannot be audited through their reference IDs.

## Sealed successor design: maximum eight calls

Same cached Mistral snapshot as v0.8.5.4, temperature 0, seed 0, 96-token
ceiling, fresh per-call KV state, no retries, no model download or provider API.
The two readiness calls gate all six diagnostic calls. No output becomes an
input to a later call; all prompts exist before execution.

| Order | Probe | Changed input / purpose | Actual rendered input tokens |
| ---: | --- | --- | ---: |
| 1 | `format` | Existing literal-format readiness | 72 |
| 2 | `readiness` | Existing task-shaped readiness | 657 |
| 3 | `final_reference` | Exact v0.8.5.4 credit baseline prompt | 648 |
| 4 | `final_choice_order` | Reverse only the two answer choices | 648 |
| 5 | `final_explicit_operands` | Query explicitly names R2 × R4; no result given | 692 |
| 6 | `inspect_computation` | Full raw context; public numeric diagnostic object | 473 |
| 7 | `isolated_arithmetic` | Given public operands 5 and 3, no rule selection or labels | 59 |
| 8 | `isolated_label` | Given computed amount 15, select its label | 84 |

The first three final-state probes preserve the complete chronological raw
evidence and the original strict output schema. They are the **only** probes
with a final-state strict grade and repair/regression comparison against the
new reference. A reference is generated anew in this successor; old outputs
are not substituted into a new comparison.

The last three are **assisted component diagnostics**, with separate parsing
and component denominators. In particular, the label probe is deliberately
given the numeric answer computed from public R2/R4 text. Passing that probe
does not count as repairing the full task. No post-call contract or target
answer enters the prompt builder; the numeric scaffolds and their public-text
derivation are nevertheless explicit, not advertised as answer-blind tasks.

There is no EBRT program intervention in this block. This locates a possible
generator-interface failure before choosing a compiler repair; it does not
test gradient utility. Token ceilings are shared, but actual inputs and
computation are not matched across the component probes. The fixed serial
order and one sample per probe do not establish a causal failure mechanism.

## What the public computation probe can tell us

The object contains `base_count`, `multiplier`, `product`, `answer`, and
`rule_evidence_id`. Its checks remain separate:

- R2 base extraction and current multiplier/rule selection;
- product agreement with the **reported** operands;
- product agreement with the **current** public rule;
- answer-label agreement with the reported product and with the current rule.

For example, `(5, 9, 45)` can have internally consistent arithmetic but a
stale selected scale. `(5, 3, 45)` is a public arithmetic inconsistency.
Product 15 with label `45_CREDITS` is a public readout inconsistency. These are
relations among emitted fields, not recovered private model reasoning. The
extra schema may itself change behavior. Component success does not prove
that the same computation happened inside the reference call.

If changing choice order or naming operands repairs the final state, retain
that result as one candidate for a later bounded compiler intervention. Do
not promote it automatically. If all assisted components pass while the
reference fails, retain the end-to-end gap without claiming a unique cause.
Failure artifacts stay sealed; any change requires a successor lock.

## Validation and operation

- 51 synthetic self-checks: PASS, including all three edit classes, exact raw
  and choice-order isolation, unchanged strict failures, component type errors,
  separate denominators, readiness stop, generation errors, and journal replay.
- At preparation, real cached tokenizer preflight rendered 8/8 prompts with
  no weights loaded for generation and **zero new model generations**.
- Lock:
  `b98b42b4b01116cd3135b864b9b46c094f6788ff91610449c1b7983b7ff591d1`.
- Preflight:
  `6daf1f495da9eab070fb2212f2d45e1a3d34a75e16e8932a8bc991489c112dcd`.

```sh
python3 numeric_revision_diagnostic_v0_8_5_5.py self-test
```

The optional `run` command requires the lock, preflight, and exact sources
committed and pushed on a non-main branch, plus `--execute-local-once`.
It rechecks snapshot files, runtime versions, and all rendered tokens before
claiming the one-shot identity. The append-only journal records dispatch
before each generation and flushes each terminal, including errors.

After a separately authorized block:

```sh
python3 numeric_revision_diagnostic_v0_8_5_5.py verify \
  artifacts/numeric_revision_diagnostic_v0_8_5_5/r01/results.json \
  --lock policy_lock_numeric_revision_diagnostic_v0_8_5_5.json
```

Verification replays prompts, parsing, strict grades, path diagnostics,
component checks, and the complete dispatch/terminal journal without another
model call. Hashes are integrity checks, not signatures or proof of model
execution. No `r01` result or execution claim existed at the preparation stage.

## r01 — 2026-09-06

After user authorization, lock commit
`c4f6079b40eba6500ce25b4b75ed2f2557b940b5` was pushed before the one-shot run.
All **8/8 calls completed without retries**. Both legacy readiness checks
passed; every generation ended with `stop`, below the 96-token ceiling.
The unchanged portable verifier passed, including the 18-entry journal.

| Probe | Official outcome | Emitted observation |
| --- | --- | --- |
| `final_reference` | Strict FAIL | `45_CREDITS`; support R2/R4, event R6, preserved reference R5 |
| `final_choice_order` | Strict FAIL | Byte-identical to reference |
| `final_explicit_operands` | Strict FAIL | Byte-identical to reference |
| `inspect_computation` | FORMAT_ERROR | Bare multiline object with 5, 3, 15, `15_CREDITS`, and rule ID R6 |
| `isolated_arithmetic` | FORMAT_ERROR | Bare `{"result":15}` instead of the required prefixed product object |
| `isolated_label` | Component PASS | `LABEL_JSON={"answer":"15_CREDITS"}` with amount 15 supplied in the prompt |

There are **0/3 strict final-state passes** and no final-state repair or diff.
All three state outputs miss only the required `/answer` revision under the
secondary path diagnostic; support, event, and preserved-reference checks pass.
Reversing choice order and explicitly naming R2/R4 do not repair this observed
case. No compiler default changes follow from the block.

Only **1/3 component outputs is parsed**; the other two retain
`V0855_COMPONENT_LINE_INVALID` and null component checks. The raw calculation
text contains useful leads, but we do not strip prefixes, accept extra lines,
rename `result` to `product`, or regrade those outputs. In the computation
text, R6 is the correction event, not the factor-bearing R4 expected by the
registered rule-ID check. A syntax-only repair would therefore not settle
the provenance question either.

The initial readiness checks covered the existing STATE_JSON interface,
**not the two newly failing component formats**. This is a limitation of the
measurement setup: the run completes, but the intended rule/arithmetic/readout
diagnosis remains partial. The label-only PASS is assisted and is not a
full-task repair. The raw appearance of 15 does not prove reliable arithmetic,
nor does a format failure prove an inability to multiply.

The smallest next gate is an explicit, independently admitted component
output contract: clarify its exact shape and separate factor-source evidence
from correction-event evidence, keeping the parser and semantic criteria
strict. Only a successor lock may test that change. After that gate, a public
calculation record feeding final-state generation is a candidate experiment,
not an implemented or established repair. Do not add more controller machinery
or repeat r01 to seek a passing sample.

Total input tokens: 3333. Total output tokens including terminal tokens: 340.
These are observed costs, not matched-compute or speed evidence.

See the immutable generated [report](../artifacts/numeric_revision_diagnostic_v0_8_5_5/r01/report.md),
[results](../artifacts/numeric_revision_diagnostic_v0_8_5_5/r01/results.json),
and the separate [post-run interpretation](../artifacts/numeric_revision_diagnostic_v0_8_5_5/r01/interpretation.md).
