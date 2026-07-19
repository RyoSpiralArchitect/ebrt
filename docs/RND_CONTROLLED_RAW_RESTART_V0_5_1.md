# EBRT v0.5.1 — Controlled Raw Restart

Status: **pre-live canary design; non-promotional DEV work**

## Question

Can a case-bound EBRT v0.5-T execution-control map be projected into one
full-context public regeneration without crossing the hosted-model gradient
boundary, hiding the case binding, or conflating surrogate improvement with
final-output quality?

This experiment is a bridge test. It is not yet a benchmark of general
reasoning ability.

## Execution boundary

```text
ordered public raw evidence
        |
        v
case-specific public temporal program       (oracle-specified binding)
        |
        v
v0.5-T exact local adjoint controller        (local PyTorch autograd)
        |
        v
execution-control map                        (canonical JSON)
        |
        v  stop-gradient / deterministic projection
provider-safe public execution envelope
        |
        v
one GPT-5.6 full-context regeneration        (non-differentiable backend)
        |
        v
public Reasoning Card -> strict grade -> output diff
```

The hosted model, provider API, structured-output parser, grader, and final
answer are outside the gradient graph. The control map does not claim to edit
model weights, hidden states, attention, or private chain-of-thought.

## Why the binding is a first-class artifact

The v0.5-T mechanism fixture names synthetic evidence and transition floors.
The v0.4 public language cases use case-local IDs such as `R1` through `R6`.
Injecting the representative P03 map directly into those cases would silently
equate two different semantic programs.

v0.5.1 therefore freezes an explicit case-program binding that records:

- the exact public case fingerprint;
- the evidence ID assigned to every admitted semantic role;
- the ordered public operators and floors;
- the event flag and invalidation lineage;
- the temporal-suite semantic fingerprint;
- the generated execution-control-map fingerprint; and
- the allowlisted projection fingerprint delivered to the provider.

Transition controls remain interventions on named public state operators. They
must not be relabeled as learned evidence importance or model attention.

## Locked canary arms

Every arm receives the same ordered raw evidence exactly once, the same model,
the same instructions, the same structured-output schema, the same output-token
ceiling, and one provider attempt with no retry.

| Arm | Public revision context | Execution-control rows |
| --- | --- | --- |
| `raw_restart_zero_control` | absent | absent |
| `raw_restart_textual_envelope` | present | absent |
| `raw_restart_matched_permutation` | present | the accepted values permuted across the same admitted floors |
| `controlled_raw_restart` | present | the accepted v0.5-T values on their optimized floors |

The matched permutation preserves the control-value multiset and L2 norm. It
breaks floor placement only. The zero/textual contrasts are not norm-matched to
the controlled arm and answer different questions.

The first live canary contains one DEV case and one ordered four-arm block:
four expected API attempts total. One block is intentionally diagnostic and
cannot separate arm quality from provider randomness or execution order.

## Provider-visible envelope

Only the following control fields may cross the provider boundary:

- floor ID and ordinal;
- public operator name;
- transition target ID and kind;
- signed bounded delta and qualitative role;

Arm names, guidance-mode labels, checkpoint condition names, program
fingerprints, and control-map fingerprints remain in the external audit
artifact. They are not provider-visible treatment labels. For the two temporal
arms, provider payloads differ only in the signed delta/role values attached to
the same ordered control rows.

Surrogate terminal states, objective values, adjoint sensitivities, gradients,
gold answers, grading rules, and downstream outcomes are not provider inputs.
The numerical delta is an external execution hint, not probability or evidence.
Raw evidence and explicit invalidation always dominate the hint.

## Evaluation order

1. Validate every pinned non-gold source, fixture, binding, and projection before calls.
2. Materialize all four gold-free payloads.
3. Execute all four one-attempt provider calls in the locked order, applying the
   gold-free local public-card contract immediately after each response.
4. Finalize exactly one sanitized receipt for every attempted call.
5. Only after the last provider attempt, verify and semantically parse the
   separate DEV gold artifact.
6. Compute strict grades.
7. Recompute public output diffs from stored public cards.
8. Publish an atomic artifact bundle, including incomplete runs.

The strict endpoint requires the exact answer, required decision facts,
required support, forbidden-support absence, stable-fact preservation, and the
expected invalidation marker. Provider completion and surrogate improvement are
reported separately from this endpoint.

Frozen predecessor modules may read gold bytes to compute boot-time source
hashes. They do not parse or attach gold semantics to provider execution. The
strong boundary asserted here is therefore semantic parse/grade attachment
after all attempts, not the absence of every pre-call filesystem byte read.

## Decision rules

The canary may establish only that the bridge executed as specified:

- the case-bound temporal controller produced a canonical control map;
- the deterministic projection survived all tamper checks;
- the request boundary sent one arm-specific public payload per provider attempt;
- all attempts have auditable receipts;
- final public cards, strict grades, and output diffs are available; and
- no-event remains an exact zero-control identity offline.

Possible observations are recorded without tuning after the run:

- identical final cards: bridge works, no observed output effect on this case;
- different cards with equal grades: observable behavioral effect only;
- controlled-only strict pass: a single-case canary rescue, not an advantage
  estimate;
- controlled failure: surrogate-to-language projection mismatch is recorded;
- incomplete provider or local-contract path: no arm-quality comparison.

A larger, balanced, fresh hard suite is required before any quality or
generalization claim. The existing v0.4 DEV cases are development-contaminated.

## Claim boundary

Safe after a complete run:

> EBRT generated a bounded external transition-control map with exact local
> adjoints, projected it through an explicit public case binding, and used the
> resulting envelope in one full-context GPT regeneration with an auditable
> final-output diff.

Not supported by this canary:

- GPT itself was differentiated;
- hidden reasoning or attention was inspected or edited;
- the controller discovered the dependency graph;
- numerical controls have calibrated meaning inside the hosted model;
- the controlled arm improves reasoning quality, cost, or reliability; or
- the result generalizes beyond this locked DEV case and runtime.
