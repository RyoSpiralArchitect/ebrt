# EBRT v0.6.2.1 — Apply Revision Acceptance

Status: **LOCKED ZERO-CALL PRODUCT-ACCEPTANCE CONTRACT**

This namespace converts the completed EBRT research substrate into one bounded
developer operation:

```text
actual Before public state
  -> local public backward credit assignment
  -> bounded control map
  -> discrete Apply Revision actuator
  -> one full-context GPT-5.6 regeneration
  -> strict public output and lineage verification
```

It is not a new A/B/C/D benchmark and does not reopen the stopped v0.6.3.2
actuator-replication branch. Its question is narrower:

> Can one sealed `Apply Revision -> Regenerate` operation execute all the way
> from an actual hosted Before state to a verified hosted After state?

A passing result is a product integration acceptance for one known synthetic
case. It is not evidence that the control map caused the output change or that
EBRT improves general reasoning.

## Frozen source and contamination

The English R1-R6 evidence, question, answer choices, and decision slots are
copied byte-for-byte from the known v0.5.2 hackathon-strategy walkthrough. The
fixture pins its source file SHA-256 and embedded fixture fingerprint.

The endpoint is intentionally contaminated:

- v0.5.2 established the Before/After story and exposed a fact-local lineage
  near-pass;
- v0.5.3 supplied the repaired typed dependency closure;
- v0.5.4 supplies a recomputed `correction_late` exact-arm-`C` evidence-effect
  basis, while v0.6.2.1 introduces a new actual-Before-conditioned scalar
  recurrence; and
- the terminal decision target remains an explicit case-specific oracle.

This history is useful for a product acceptance path but disqualifies the run
as fresh reasoning-quality evidence. The effect-attribution endpoint is locked
to `NOT_ASSESSED` regardless of whether product acceptance passes.

## Fixed two-call path

| Position | Phase | Raw horizon | Prior public state | Revision |
| ---: | --- | --- | --- | --- |
| 1 | `before_event` | canonical R1-R5 exactly once | none | none |
| 2 | `after_event` | canonical R1-R6 exactly once | normalized actual Call-1 output | dynamically compiled public actuator |

Call 2 is not precomputed. Its bytes may be materialized only after Call 1 has
produced a structurally valid typed public output. The local controller consumes
that exact normalized output, executes the frozen single temporal-adjoint path,
and emits a bounded control map. A deterministic stop-gradient compiler then
projects the numeric map into three provider-visible operations:

```text
reinspect_evidence_ids
suppress_evidence_ids
preserve_evidence_ids
```

Free-text is not fed back. The normalized prior state contains only:

```text
schema_version
checkpoint_id
current_answer
selected_closure_id
target_values
compiled_closure_fingerprint_sha256
fingerprint_sha256
```

The provider does not receive gradient values, surrogate objectives, semantic
gold, accepted closure IDs, expected answers, or candidate-role names.

## Public closure catalog

The fixture presents a finite public action space. Each candidate contains only
an opaque `closure_id` and a typed graph with support nodes, targets, target
dependencies, and invalidation edges. Answer and target values are absent from
the catalog and must be emitted separately by the provider.

IDs are deterministic but semantically opaque:

```text
K_ + first 10 hex characters of
SHA256(canonical JSON({
  salt: "ebrt-v0.6.2.1-apply-revision-closure",
  phase_id,
  graph
}))
```

Array order is separately frozen by a role-blind keyed permutation. For every
candidate, compute:

```text
SHA256(canonical JSON({
  salt: "ebrt-v0.6.2.1-role-blind-catalog-order",
  phase_id,
  closure_id
}))
```

where canonical JSON is UTF-8, key-sorted, and whitespace-free; then sort by
the full lowercase digest in ascending byte order. The algorithm sees neither
the candidate graph nor any gold role. The runner must preserve this array
order byte-for-byte when constructing provider input. In the sealed catalogs,
the gold-selected Before and After candidates occupy different zero-based
ordinals (`1` and `2`), preventing a shared first-option shortcut.

The two Before candidates each contain exactly three distinct active evidence
IDs. The three After candidates each contain exactly four. The catalog contains
no `role`, `quality`, `accepted`, `expected`, `correct`, `answer`, or target
value field.

Provider-visible candidates are:

```text
before_event
  K_4f9d103c2b
  K_c9dc959be3

after_event
  K_87b5857bbb
  K_4486fd43a1
  K_d59ad14817
```

Their semantic roles exist only in the separate post-two-call gold. The catalog
contains an exact repaired closure, the frozen v0.5.2-style lineage near-pass,
and a stale/mixed closure so that selecting a closure remains a real public
action rather than a one-option echo.

## Provider output

Both calls use the same strict response schema:

```json
{
  "schema_version": "ebrt-apply-revision-provider-output-v0.6.2.1",
  "checkpoint_id": "...",
  "current_answer": "POLISH",
  "selected_closure_id": "K_...",
  "target_values": [
    {
      "target_id": "constraint:video_constraint",
      "target_type": "constraint",
      "slot": "video_constraint",
      "value": "THREE_MINUTE_NARRATED"
    },
    {
      "target_id": "fact:demo_centerpiece",
      "target_type": "fact",
      "slot": "demo_centerpiece",
      "value": "POLISHED_SCREENS"
    },
    {
      "target_id": "fact:final_priority",
      "target_type": "fact",
      "slot": "final_priority",
      "value": "ADDITIONAL_UI_POLISH"
    }
  ]
}
```

The local compiler validates the selected catalog graph against the evidence
horizon, derives direct, inherited, and total active evidence closure, applies
its invalidation edges, and joins the provider's three target values. The
provider selects only an opaque catalog ID; a provider-declared graph is never
accepted, and the locally frozen catalog remains the structural authority.

## Controller and gradient boundary

The runtime controller is a **new v0.6.2.1 actual-Before-conditioned scalar
recurrence**. It is not an exact replay of the v0.5.4 arm-`C` lane and is not
the v0.5.5 multi-lane composition layer. The historical v0.5.4
`correction_late` exact arm `C` is recomputed only to obtain a frozen public
evidence-effect basis.

The actual Before scalar has exactly three components: `current_answer`,
`fact:demo_centerpiece`, and `fact:final_priority`. Constraint targets are
excluded. Each value is mapped by its zero-based ordinal among the fixture's
allowed choices:

```text
coordinate(value, choices) = 0                              if len(choices) = 1
coordinate(value, choices) = -1 + 2*ordinal/(len(choices)-1) otherwise
```

The initial scalar is the arithmetic mean of those exact three coordinates,
computed with `math.fsum / 3`.

For the recomputed v0.5.4 source lane, control sites are grouped by parsed
evidence ID in fixed `R1` through `R6` order:

```text
absolute_credit[e] = sum(abs(normalized_u))
signed_credit[e]   = sum(normalized_u)       # audit only
effect[e]          = absolute_credit[e] / max_j absolute_credit[j]
```

The new scalar trajectory begins at the actual Before scalar. With controls
initialized to exact zero, it executes:

```text
state_i = tanh(0.82 * state_(i-1) + control_i * effect_i)
L = (state_6 - 0.72)^2 + 0.01 * sum(control_i^2)
```

It makes exactly one `backward()` call and projects one update:

```text
control_i = -0.05 * gradient_i
```

The control vector must have L2 norm at most `0.25`. A central finite-
difference audit uses epsilon `0.000001`, and the maximum absolute analytic/
numeric gradient disagreement must be at most `0.00000001`. The actual Before
provider output participates in this recurrence; the After provider output
does not.

The actual Before state is mandatory controller input. Reinspection compilation
selects three nonzero-credit evidence IDs by descending absolute public credit
with evidence-ID tie-breaking. Invalidated evidence, the stable evidence, and
zero-credit evidence are excluded from the reinspection ranking. Event-invalidated
evidence that remains active in Before is instead compiled into suppression;
the stable evidence active in Before is compiled into preservation. For the
sealed strict-Before state, this mechanical policy yields:

```text
reinspect_evidence_ids = ["R6", "R4", "R2"]
suppress_evidence_ids  = ["R3"]
preserve_evidence_ids  = ["R5"]
```

This ordering is derived from the real signed public credits after the frozen
exclusions; it is not rewritten to match an illustrative or gold-authored
sequence.

The boundary is exact:

```text
typed public state
  -> differentiable local public trajectory
  -> backward()
  -> public control map
  -> stop-gradient compiler
  -> JSON payload
  -> GPT-5.6
```

GPT-5.6, provider parsing, JSON projection, generation, and grading are not
differentiated. No hidden state, attention map, or KV cache is read or edited.

## Semantic-gold boundary

`fixtures/apply_revision_acceptance_gold_v0_6_2_1.json` is post-two-call only.
Its bytes may be pinned by the policy lock, but live execution must prevent its
semantic parsing until both provider attempts have structurally valid terminal
outputs and the dynamic Call-2 payload/receipt chain has validated.

At that point it is loaded exactly once. It grades:

1. Before as strict `POLISH` under R1-R5;
2. the exact same compiled Before bytes as stale under R1-R6;
3. After as strict `PROVE` with repaired direct/inherited/total lineage;
4. R6 invalidating R3 and R3 absent from active support;
5. `THREE_MINUTE_NARRATED` preservation; and
6. the exact public answer, target-value, support, invalidation, and stable diff.

An incomplete structural block never loads semantic gold and remains
`INCOMPLETE_NOT_ASSESSED`.

## Structurally valid but semantically unexpected Before

Semantic outcome must not control whether Call 2 occurs. If Call 1 is
structurally valid but emits a wrong answer, a different candidate, or an
unexpected allowed target value, the runner must:

1. record the exact output as a completed Before terminal;
2. normalize that actual output without free text;
3. execute the same locked controller;
4. require the same preregistered finite, non-neutral controller hard gates;
5. compile without a fallback prompt or replacement map;
6. seal the exact dynamic Call-2 payload; and
7. make exactly one After attempt.

All 16 structurally valid finite Before combinations in this bounded catalog
produce a non-neutral map under the locked recurrence. A controller hard-gate
failure is an integrity stop, not an outcome-aware replacement or neutral-map
fallback.

Only post-two-call grading may mark the Before contract failed. This prevents
an outcome-aware early stop, repair, or favorable prompt selection.

A structurally invalid Before cannot seed the controller. In that case Call 2
is not attempted, semantic gold remains unopened, and the result is incomplete.
Receipt or source-integrity failure burns the in-flight namespace rather than
creating a semantic result.

## Status lattice

The result keeps these axes separate. `run_status` is the execution-completion
axis; no separate `attempt_block_status` or `assessment_status` field is
published:

```text
run_status
  COMPLETE_EXACT_TWO_TERMINALS | INCOMPLETE_NOT_ASSESSED

mechanism_status
  PASS | FAIL | NOT_ASSESSED

before_status
  PASS_THEN_STALE | FAIL | NOT_ASSESSED

after_status
  PASS_STRICT_POST_EVENT | FAIL | NOT_ASSESSED

diff_status
  OBSERVED_EXPECTED_PUBLIC_DIFF | DIFF_MISMATCH | NOT_ASSESSED

product_acceptance_status
  PASS | FAIL | NOT_ASSESSED

effect_attribution_status
  NOT_ASSESSED
```

The only terminal decisions are:

```text
ACCEPT_APPLY_REVISION_PATH
HOLD_APPLY_REVISION_PATH
INCOMPLETE_NOT_ASSESSED
```

`effect_attribution_status` has no positive or negative alternative in this
namespace.

## Product acceptance gates

`ACCEPT_APPLY_REVISION_PATH` requires every item below:

1. exactly two structurally valid terminal provider outputs;
2. Before strict own-horizon pass;
3. exact same-compiled-Bytes stale signature under the post-event contract;
4. actual Before state fingerprint bound to controller input;
5. at least one real finite local backward call;
6. a lower finite surrogate objective;
7. a non-neutral bounded public control map;
8. deterministic actuator compilation;
9. Call-2 payload materialized and durably sealed only after Before terminal;
10. strict After answer, direct/inherited/total lineage, invalidation, and stable
    target pass;
11. exact public `POLISH -> PROVE` and decision-fact diff;
12. separate surrogate, control, provider-output, and grade objects; and
13. `effect_attribution_status=NOT_ASSESSED`.

One failed assessable gate produces `HOLD_APPLY_REVISION_PATH`; it is not
relaxed, regraded, or called an effective pass.

## One-shot durable journal

Before the first call, a new in-flight namespace stores and fsyncs a sealed plan
containing the fixed Call-1 payload, source receipts, authorization receipt,
controller/compiler policy, phase order, and no-retry/no-resume contract. It
does not pretend to know the dynamic Call-2 fingerprint.

The successful journal sequence is exact:

```text
ATTEMPT_STARTED    before_event
ATTEMPT_TERMINAL   before_event
REVISION_STARTED
REVISION_COMPILED
ATTEMPT_STARTED    after_event
ATTEMPT_TERMINAL   after_event
```

The exact Call-2 payload is written and fsynced before `REVISION_COMPILED` is
appended. That row binds the Before provider-output fingerprint, compiled
Before fingerprint, controller-input fingerprint, autograd audit, control-map
fingerprint, compiled-actuator fingerprint, and Call-2 payload fingerprint.

There is no retry, resume, backfill, alternate prompt, fallback map, third call,
or reuse of a consumed namespace. A receipt/source/journal integrity failure
appends `IRRECOVERABLE_GUARD_FAILURE`, leaves the in-flight namespace for
inspection, and publishes no canonical semantic artifact.

## Required zero-call tests

Before a separate live authorization can exist, network-denied tests must cover:

- exact R1-R6 source inheritance and fixture/gold fingerprints;
- opaque salted closure-ID derivation, role-blind keyed catalog ordering,
  different gold-selected ordinals across phases, and equal evidence
  cardinality per phase;
- graph cycles, dangling nodes, duplicate IDs, orphan supports, invalid
  source/target types, and evidence outside the active horizon;
- exact three target values and rejection of unknown/extra output fields;
- total normalization over every structurally valid finite Before output;
- identical Before producing byte-identical controller/Call-2 bytes;
- an alternate valid Before changing the normalized state and dynamic payload;
- real autograd, finite differences, nonfinite gradients, zero-backward,
  neutral-map, over-budget, and objective-increase paths;
- exact stop-gradient actuator compilation and forbidden provider-key leakage;
- structurally valid semantic mismatch continuing to exactly one After call;
- Before/After provider and local-schema failure with semantic gold unopened;
- early/double gold access and outcome-aware call branching rejection;
- journal order, duplicate/missing rows, retry, resume, and third-call rejection;
- provider receipt request/prompt/schema/model/usage/retry tampering;
- source, authorization tag, symlink, file-set, duplicate-JSON-key, nonfinite,
  and coherent-reseal tampering;
- two-build byte identity and socket-denied execution; and
- foreign-root pure-standard-library artifact verification.

The network-zero contract authorizes no provider call. Live execution requires
a separate reviewed lock, merged commit, immutable authorization tag, exact
clean HEAD, and one new output namespace.

## Frozen zero-call receipts

```text
fixture fingerprint     a10f903ee492b0741de3f2e0be8742311ae80bc09eb6b097a3b2c2de6ec1e484
gold fingerprint        1a6fee91d2c676c249436f652bacdd50fdcfd8e7fe8b30e4eefd919723b9b872
policy-lock fingerprint 8cc290a71ba88fa2b2b131d72b8b315492a76324a22527886f2c132c68154f99
before payload          088efd8ad4ab606169878045f780e4c3e93fbfe70efcd18f6e42850132b2b8e3
```

`python3 ebrt.py self-test` passes with zero network calls, exact all-green
scripted integration, coherent receipt/journal tamper rejection, and artifact
round-trip validation. `python3 ebrt.py preflight` reports the policy lock as
`LOCKED` and remains pending only the separately created annotated live
authorization tag.
