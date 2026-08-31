# EBRT v0.8.5.1 — Public Role Transport Repair

## Question

v0.8.5 separated literal format readiness from task-shaped public-state
composition. Both exact local snapshots passed the literal probe and failed the
task-shaped gate in complementary ways:

- Mistral emitted exact decision evidence but retained the retired answer and
  over-assigned context as a preserved constraint;
- Qwen emitted the corrected answer and exact revision/stable channels but
  omitted one required identity record from decision support.

`RevisionTask` already contains a caller-supplied public role for every
evidence record. The v0.8.5 adapter discarded that field and sent only
`evidence_id` plus `text`. This successor asks one bounded engineering
question:

> Does transporting that already-public role across the model-adapter boundary
> close the known task-channel composition failure?

This is not a fresh benchmark and does not test autonomous role discovery.

## Single intended interface delta

v0.8.5 record:

```json
{"evidence_id":"R2","text":"..."}
```

v0.8.5.1 record:

```json
{"evidence_id":"R2","role":"required_support","text":"..."}
```

The role value is copied exactly from `RevisionTask.evidence[*].role`. Removing
that one field must reproduce the prior text-only record byte-for-byte. The
adapter does not send `expected_answer`, a post-call contract, or semantic-gold
fingerprint.

The output state remains one strict line with pairwise-disjoint destinations:

```text
STATE_JSON={"answer":"...","decision_support_ids":[...],"preserved_constraint_ids":[...],"revision_event_id":"..."}
```

Direct and role-controlled arms receive the same role-record schema and exact
output-contract fingerprint. The controlled arm still additionally changes
evidence order and supplies the compiled public revision program, so any later
direct/control contrast remains bundled rather than gradient-only.

## Frozen execution geometry

- Base main: `fe6b13727cd1ae8ad4c2acd24a8cc601d95dd5be`.
- Exact models: the same Mistral 7B and Qwen 1.5B MLX snapshots as v0.8.5.
- Admission: literal `FORMAT_READY` plus the known v0.8.5
  `TASK_CHANNEL_READY` failure fixture.
- Regression material: the four published v0.8.4 cases, all contaminated.
- Arms: chronological direct public roles and role-controlled public roles.
- Sampling: temperature `0`, seed `0`, 96-token ceiling.
- Schedule: alternating two-arm order over the four cases.
- Retry: none.
- Native-state capture: disabled.

Only a model passing both readiness calls enters regression cells. A stopped
model contributes no algorithm-quality denominator.

## Predeclared interpretation

- Readiness repair is an adapter-interface result only.
- Regression output, if admitted, is contaminated engineering evidence.
- A strict controlled repair does not isolate gradient causality because the
  intervention bundles public role-aware ordering and explicit instructions.
- A null direct/control difference does not negate successful role transport.
- A failure after role transport remains a first-class adapter/capability
  diagnostic; prompts and grades are not relaxed and the same namespace is not
  rerun.
- No private hidden state is observed or edited, and no gradient crosses a
  model adapter.

## Network-zero checks

```bash
python3 -m ruff check public_role_transport_canary_v0_8_5_1.py
python3 public_role_transport_canary_v0_8_5_1.py self-test
python3 public_role_transport_canary_v0_8_5_1.py lock-spec
python3 ebrt_core.py self-test
```

The lock must be committed and pushed before either local model receives a
call. Results are written once under a new artifact namespace and verified by
portable replay.

## Claim boundary

- Caller-supplied public roles are scaffold metadata, not discovered
  dependencies.
- Task material and all four regression cases are contaminated.
- Algorithm quality, provider uptake, and output difference remain separate
  receipts.
- No causal superiority, general reasoning improvement, or cross-model
  regularity is claimed.
