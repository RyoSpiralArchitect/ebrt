# EBRT v0.8.4 typed revision-channel canary

Status: **COMPLETE DEVELOPMENT CANARY; PORTABLE VERIFICATION PASS**

Post-review status: **INTERPRETATION NARROWED; ORIGINAL RUN UNCHANGED**

Review found that the typed prompts alone included support-selection guidance
for a scored stable-evidence criterion. The schema comparison is therefore a
bundled output-interface and support-guidance contrast, not a pure
field-factorization contrast. Review also separated Qwen's task-shaped typed
parse failures from the algorithm-quality denominator. See
[`post_review_interpretation.json`](post_review_interpretation.json). The
frozen legacy aggregate still says `algorithm_diagnostic_models=2`; the
post-review receipt supersedes that interpretation with the corrected count
of `1` without rewriting the source artifact.

This sealed run crossed two public factors over four fresh synthetic cases and
two local instruction-model snapshots:

1. chronological full context versus the role-stratified EBRT control bundle;
2. flat `ANSWER/SUPPORT` output versus typed
   `ANSWER/SUPPORT/REVISION_EVENT` output.

It executed 34 logical local-model calls: one readiness call per model plus
four cases by four arms by two models. There was no automatic retry.

## Aggregate result

| Measurement | Result |
| --- | ---: |
| Adapter-readiness passes | 2/2 |
| Canary calls after readiness | 32/32 |
| Parsed `direct_flat` outputs | 8/8 |
| Parsed `direct_typed` outputs | 4/8 |
| Parsed `role_flat` outputs | 8/8 |
| Parsed `role_typed` outputs | 4/8 |
| Mechanical strict passes: `direct_flat` | 2/8 |
| Mechanical strict passes: `direct_typed` | 0/8 |
| Mechanical strict passes: `role_flat` | 0/8 |
| Mechanical strict passes: `role_typed` | 1/8 |
| Full-factorial algorithm-diagnostic models | 1/2 |
| Admitted strict passes: `direct_flat` | 2/4 |
| Admitted strict passes: `direct_typed` | 0/4 |
| Admitted strict passes: `role_flat` | 0/4 |
| Admitted strict passes: `role_typed` | 1/4 |
| `role_flat` provider-uptake passes | 4/8 |
| `role_typed` provider-uptake passes | 3/8 |
| Flat-to-typed raw differences under control | 8/8 |
| Flat-to-typed strict repairs under control | 1/8 |
| Direct-to-control raw differences under typed schema | 7/8 |

The bundled typed interface produced an observable provider-side difference,
but did not produce a general quality improvement. Field factorization alone
is not identified.

## One positive mechanism case

Mistral, archive-tier case:

```diff
 ANSWER=COLD_TIER
-SUPPORT=R6,R4
+SUPPORT=R4,R2
+REVISION_EVENT=R6
```

`role_flat` omitted required decision evidence `R2`. With the same public EBRT
program, `role_typed` restored `R2`, moved correction provenance `R6` into its
own field, and passed the strict contract. Because typed-only guidance also
changed, this is one bundled-interface development example, not evidence of a
field-factorization or general effect.

## Failure atlas

### Mistral

- All 16 outputs parsed.
- The typed controlled arm separated `R6` from decision support in 3/4 cases.
- `R5` stable evidence still leaked into decision support in three controlled
  typed cases, leaving only the archive case strictly green.
- In the numeric case every arm retained the old answer `45_CREDITS` rather
  than the corrected `15_CREDITS`; an output-channel repair did not repair the
  underlying answer selection.
- The direct typed arm duplicated `R6` in both `SUPPORT` and
  `REVISION_EVENT` in all four cases. A typed schema alone was insufficient;
  the positive separation appeared only with the control bundle.

### Qwen

- The literal three-line readiness probe passed exactly.
- All eight task-shaped typed outputs failed the locked three-line parser.
  Most omitted `SUPPORT`; two controlled outputs repeated or interleaved
  fields. These are adapter/interface failures, not eight EBRT reasoning
  losses.
- All eight flat outputs parsed, but none passed the strict evidence contract.
- The public control bundle changed the visible first-line answer from
  `LANE_NORTH` to `LANE_SOUTH` in the freight case, but from `APPROVE` to
  `HOLD` in the permit case. The actuator channel is visibly non-neutral on
  this snapshot, while the direction of the quality effect is mixed.

The readiness failure is itself diagnostic: literal schema copying did not
test task-shaped field composition. Qwen is retained as a partial
adapter/interface surface and excluded from algorithm-quality denominators.
Future model admission needs separate `FORMAT_READY` and
`TASK_CHANNEL_READY` receipts.

## Next bounded iteration

Do not strengthen the gradient or add more models yet. Keep the core and
single-call geometry fixed, and repair the model-interface boundary:

1. replace the literal-copy readiness probe with a task-shaped, held-out
   channel-composition probe;
2. give stable evidence a non-decision destination rather than exposing
   `PRESERVE` next to active support;
3. test one compact typed state object with explicit slots for answer,
   decision support, revision event, and preserved constraints;
4. keep control selection, provider uptake, parsing, and strict semantic grade
   as separate receipts;
5. treat the observed Qwen answer flips as a non-null but non-monotonic
   actuator result, not as improvement.

## Receipts

- Pre-call lock commit: `68f6390`
- Policy-lock fingerprint:
  `d0bfe3c2a5fa4d86d71e50a154a26a4e046b99eca7f2d1e1c049bd1e51042e15`
- Run fingerprint:
  `2a4dfc288e85c9fd26f73eac37f37e4e8068194067b267709cd2b1ec4ff94d95`
- Results file SHA-256:
  `55a1fb8b11c49cfa69b074916ec2bee18e52bd7e18a2635070f8e510651f4fc6`
- Portable verification fingerprint:
  `39930c83d22ac0e1fef6f5f63549dfdb26c81a36be1107ac6877de2eeefc76fa`
- Post-review interpretation fingerprint:
  `da5dcd2f5a661b7f8ca7d802ee54ff8a0aa8780f378a3ac4aefda46c6590f872`

## Claim boundary

- The control contrast bundles evidence order and explicit revision
  instructions; it is not gradient-only.
- The typed package changes output shape and typed-only support-selection
  guidance, not the backward objective; field factorization alone is not
  identified.
- Only the fully parsed Mistral factorial enters the narrowed
  algorithm-diagnostic surface; Qwen's typed failures remain interface
  diagnostics.
- Caller-supplied roles are scaffolding, not autonomously discovered causal
  structure.
- Public trajectories are surrogates, not private reasoning transcripts.
- One deterministic sample per cell does not establish causal superiority,
  general reasoning improvement, or cross-model regularity.
