# EBRT v0.8.5.2 r01 — exact public-role isolation

## Sealed execution

- Status: `COMPLETE_WITH_BOUNDED_ADAPTER_ADMISSION`
- Logical calls: `12`
- Automatic retries: `0`
- Models: `2` exact local MLX snapshots
- Policy-lock fingerprint:
  `115b8f6bb1d6fcc69b6ffb50a468fd632e5fbaaf308c4d1c51fe2b10bcce1fb5`
- Result file SHA-256:
  `002bb020f8b4d4758a6e12b0b53b85c65509c2c4920db3ba353d558e33286692`
- Run fingerprint:
  `f6af26d4f2242c8b9ebe8b35718468a4b955ed55cf6476fe7a2e55fd19b09c40`
- Portable verification fingerprint:
  `9c7a6c9827e55fef4442a57357db5d516d97e4ed878cd531b92576ea25f16403`
- Interpretation fingerprint:
  `6764e55b73f6cbf81de3ff839ecc89e406617a88e18230f6d17b47737b4e9cd5`

The lock was committed and pushed as `11ff6f5` before the first model call.
The namespace was run once and was not retried.

## Isolation receipt

Removing only `role` from each v0.8.5.2 model-visible `EVIDENCE_JSON`
record reproduces the complete v0.8.5 prompt bytes.

| Surface | Exact projections |
| --- | ---: |
| Task-channel readiness | 1 / 1 |
| Four direct prompts | 4 / 4 |
| Four role-controlled prompts | 4 / 4 |
| **Total** | **9 / 9** |

The model-visible contrast is therefore labeled
`EXACT_CALLER_SUPPLIED_PUBLIC_ROLE_FIELD`. This isolates an interface-field
delta in the frozen implementation; it does not by itself identify a causal or
general effect.

## Readiness transitions from v0.8.5

| Model | v0.8.5 | v0.8.5.2 | Admission |
| --- | --- | --- | --- |
| Mistral-7B-Instruct-v0.3-4bit | FAIL | PASS | Entered 4 regression cells |
| Qwen2.5-1.5B-Instruct-4bit | FAIL | FAIL | No regression calls |

Mistral changed from:

```json
{"answer":"GATE_RED","decision_support_ids":["R2","R4"],"revision_event_id":"R6","preserved_constraint_ids":["R1","R5"]}
```

to:

```json
{"answer":"GATE_BLUE","decision_support_ids":["R2","R4"],"preserved_constraint_ids":["R5"],"revision_event_id":"R6"}
```

Qwen retained the same bounded failure: the answer, revision event, and stable
constraint were correct, but required support `R2` was absent.

```json
{"answer":"GATE_BLUE","decision_support_ids":["R4"],"preserved_constraint_ids":["R5"],"revision_event_id":"R6"}
```

The receipt therefore records
`OBSERVED_FAIL_TO_PASS_ON_ONE_CONTAMINATED_MODEL`, with role-only causal effect
attribution explicitly `NOT_ASSESSED`.

## Admitted regression cells

Only Mistral passed both readiness gates.

| Metric | Direct | Role-controlled |
| --- | ---: | ---: |
| Strict passes | 3 / 4 | 3 / 4 |
| Strict repairs | — | 0 |
| Strict regressions | — | 0 |

The one failure in both arms was `credit-scale-rule-revision`: both emitted
`45_CREDITS` instead of the expected `15_CREDITS`, while retaining exact
support (`R2`, `R4`), revision (`R6`), and preservation (`R5`) channels.

### Direct versus role-controlled output

- Raw text differences: `3 / 4`
- Parsed list-sequence differences: `3 / 4`
- Normalized public-state differences: `0 / 4`
- Answer differences: `0 / 4`

All three raw differences were only JSON field ordering or
`decision_support_ids` ordering, for example:

```diff
- "decision_support_ids":["R2","R4"]
+ "decision_support_ids":["R4","R2"]
```

The direct/control semantic effect status is therefore
`NULL_ON_ADMITTED_CELLS`.

## What this changes

The exact role field is associated with a complete adapter-admission repair for
the Mistral snapshot, but it is insufficient for the smaller Qwen snapshot and
does not create a semantic direct/control output difference in the admitted
cells. The next algorithm iteration should treat public-role uptake as a
measured adapter capability rather than an assumed invariant.

This result does not show that the role field caused the repair, that public
roles improve reasoning generally, or that the current controller changes
final answer semantics.
