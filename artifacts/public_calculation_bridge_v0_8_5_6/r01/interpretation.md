# r01 interpretation — public calculation bridge

Recorded on 2026-09-10 JST. This note interprets the sealed
[results](results.json); it does not modify the generated [report](report.md),
parser, grades, source, or lock. All earlier artifacts remain unchanged.

## What ran

The explicitly authorized one-shot block ran after preparation commit
`f8723aaa8d0c074772803f83b7bf9b55c86bdcbe` was published. All eight calls
completed, without retry, model download, or hosted API calls. The independent
STATE_JSON and CALC_JSON literal/task readiness checks all passed. Portable
verification replayed all 18 journal entries and the actual calculation-to-
bridge transformation successfully.

The target emitted exactly:

```text
CALC_JSON={"base_count":5,"multiplier":3,"product":15,"answer":"15_CREDITS","rule_evidence_id":"R4"}
```

The unchanged parser accepts this record; all seven calculation checks pass.
The old v0.8.5.5 multiline object remains a format failure. No old output was
normalized, repaired, or promoted to a pass.

## Exact final outputs

Raw context only:

```text
STATE_JSON={"answer":"45_CREDITS","decision_support_ids":["R2","R4"],"revision_event_id":"R6","preserved_constraint_ids":["R5"]}
```

With the actual emitted operands and factor-source ID:

```text
STATE_JSON={"answer":"45_CREDITS","decision_support_ids":["R4"],"revision_event_id":"R6","preserved_constraint_ids":["R5"]}
```

With the same record plus the actual emitted product:

```text
STATE_JSON={"answer":"15_CREDITS","decision_support_ids":["R4"],"revision_event_id":"R6","preserved_constraint_ids":["R5"]}
```

The final prompt delta between the two bridges is only `"product":15`.
The source's `answer` is absent from both records. Its 15 was neither supplied
from the grading contract nor recalculated by the bridge compiler. Both
records were labelled unverified, with the complete raw evidence still
present. Raw-only remains byte-identical to the preceding block's reference.

| Condition | Correct answer | Exact support | Strict PASS | Miss | Over-edit | Wrong-value edit |
| --- | --- | --- | --- | ---: | ---: | ---: |
| raw-only | No | Yes | No | 1 | 0 | 0 |
| operands-only | No | No: R2 absent | No | 1 | 1 | 0 |
| product-bridge | Yes | No: R2 absent | No | 0 | 1 | 0 |

The expected support is R2 plus R4. R2 was already present in the caller's
prior state, so dropping it is an over-edit, not a required new edit that
failed to occur. The legacy support diagnostic still correctly labels it a
missing required reference. The strict contract remains primary: **0/3 final
passes and no strict repair**, despite the correct product-bridge answer.

All three outputs retain event R6 and stable reference R5, omit invalidated
R3, and keep the public channels disjoint. Reference preservation does not
demonstrate preservation of stable fact values absent from the output schema.

## What the result narrows

1. The calculation interface is admitted for this block, unlike the prior
   measurement setup. The new prompt elicits one public computation with the
   correct base, factor, product, label, and factor provenance.
2. Operand disclosure alone does not repair the numeric answer here. With
   the emitted product added, the final answer changes to 15. This is an
   observed output-level contrast, not a trace of private arithmetic.
3. Both bridge outputs lose R2. The numerical answer and support preservation
   therefore need independent evaluation: solving one does not solve both.

There is no gradient intervention in this block, no matched-compute quality
evaluation, no replication, and no counterbalanced serial order. We do not
claim that the product is uniquely causal, that hidden arithmetic was
previously correct, or that EBRT reasoning quality has improved. The correct
product could be copied without the final generator recomputing it. The
added common scaffold could affect support independently of the product.

## Smallest candidate follow-up, not executed

The compact record names R4 as the factor source but carries no source ID for
the base count. A testable hypothesis is that the final generator treats that
partial provenance as the whole support set. This would explain the R2
omission in both bridge outputs, but neither an internal mechanism nor a
unique cause has been established.

Before expanding the controller or adding a provenance DAG, a successor can
freeze the same **recorded** numeric fields and compare two otherwise equal
prompts: retain `rule_evidence_id` versus omit only that field. Keep full raw
context and the original strict final-state contract in both. Do not insert
the expected R2/R4 support set or merge the reference output into the result.
Such a comparison is a contaminated compiler replay, not fresh arithmetic,
and needs its own lock, budget, and authorization. R2 recovery would motivate
replication; a null would leave the partial-record hypothesis unresolved.

No follow-up call, compiler promotion, core edit, PR, or merge occurred in
this block. The authorized eight-call budget is exhausted and closed.

## Receipts and observed cost

| Call | Input tokens | Output tokens | Finish |
| --- | ---: | ---: | --- |
| state_format | 72 | 46 | stop |
| state_task | 657 | 52 | stop |
| calc_format | 66 | 41 | stop |
| calc_task | 592 | 41 | stop |
| calculation | 592 | 43 | stop |
| raw_only | 648 | 53 | stop |
| operands_only | 752 | 50 | stop |
| product_bridge | 757 | 50 | stop |

Total: 4136 input tokens, 376 output tokens including terminal tokens.
Summed recorded call latency: 62044.597 ms; this is not complete process
wall-clock time or a speed comparison. No output reached the 96-token ceiling.
Actual bridge lengths differ from the synthetic preflight previews, as the
sealed dynamic protocol anticipated.

- Run fingerprint: `c541b13a4541d0c0a3ff6db380f2d0d7cca93379fd491b3c55e208b8376acc5b`.
- Verification fingerprint: `40fc5cfc408c9232bad7ebe3bbe5e7501d0b70d308d782e34a8eb68a89a5c2a8`.
- Actual calculation raw-text SHA-256: `e9e9d6e3a5aead26c3117aeb9662ca6566cffee9026ceb8d6522503f83f62b23`.
- `results.json` file SHA-256: `11fa4a68de7a736b6a40625a2b33ba89d635827d355b68ff634a69727ed5ae38`.
- `journal.jsonl` file SHA-256: `abba15844416226bc9f1ed3f9675b23b0611cf9291a6ca3e0b3153ef33e29f7f`.
- `verification.json` file SHA-256: `525b5909a0a623b451a3f02f4201d31c7a2b5052abf4a611faf99e335196069b`.
- `report.md` file SHA-256: `7cc353bddfcdeb514f5b84b6eb30426ada03f468471d298ad169dbadf8ac7a59`.

Hashes check consistency, not authenticity or causal attribution. The
portable verifier does not regenerate output or rerun tokenization.
