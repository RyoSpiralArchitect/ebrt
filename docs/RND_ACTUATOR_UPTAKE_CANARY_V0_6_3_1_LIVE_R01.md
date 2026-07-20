# EBRT v0.6.3.1-live-r01 — Sealed Four-Call Uptake Execution

Status: **PREREGISTERED; ZERO LIVE CALLS; AUTHORIZATION TAG REQUIRED**

This namespace executes only the four provider payloads already sealed by the
v0.6.3.1 network-zero measurement repair. It does not modify or replace that
monolith, its fixture, gold, policy lock, canonical projection, or preflight
artifact.

The predecessor is the annotated tag `v0.6.3.1-preflight`, tag object
`ea987355a1f720aa0859f6ad92f874cf21d0fbe5`, peeled exactly to commit
`c5e1244055e5d7f83493698119549c49df718ed7`. That commit records a zero-call
preflight only. Neither this protocol nor its pull request reports a hosted
result.

## Separate authorization boundary

The live runner and its lock are reviewed and merged separately from both the
preflight and the later result artifact. Merging the runner does not by itself
authorize a provider call. Live execution is permitted only after an annotated
tag named `v0.6.3.1-live-r01-authorized` points exactly at the merge commit that
contains the reviewed runner and lock, and the runner verifies that exact
checked-out source and tag relationship before constructing the live block.

Before that tag exists, the irreversible command must refuse execution. After
the one authorized attempt, the result, journal, receipts, reports, and
portable result verifier are published in a later, separate pull request. They
must not be added retrospectively to this authorization commit.

## Frozen execution geometry

The entire live block is one case, one attempt per arm, in this exact order:

```text
C -> X -> D -> Z
```

- `C` is the frozen geometry-matched anti-placement;
- `X` is the frozen correction-first positive channel control;
- `D` is the frozen local-backward-selected placement; and
- `Z` is the frozen neutral positional reference.

Every call uses the presealed payload for its arm. Retry, reordering, resume,
backfill, replacement calls, adaptive prompt edits, and alternate output paths
are forbidden. A completed or burned attempt is never reused to obtain a more
favorable four-arm block.

The provider receives the unsealed public payload represented by the committed
projection. It does not receive the arm label, treatment role, controller
polarity, closure role, grading gold, target status, or downstream decision.
The sole intentionally treatment-varying semantic payload field remains
evidence order. Per-request IDs, wall-clock position, and provider-side state
may still differ across the fixed serial block.

## Journal and failure contract

Before the first provider call, the runner rederives the controller and all
four payloads, compares them with the exact committed preflight bytes, verifies
the source and authorization receipts, creates the inflight namespace, and
durably records the fixed plan. Before each call it appends and synchronizes an
`ATTEMPT_STARTED` row; after the boundary it appends exactly one terminal row.

There are two deliberately different failure classes.

### Observable arm invalidity

A provider transport failure, malformed or schema-invalid response, or unknown
closure ID makes that arm structurally invalid. The runner records the invalid
terminal row and continues the remaining presealed arms in `C -> X -> D -> Z`
order. It does not retry, reorder, or backfill. After all scheduled arms are
terminal, the whole block is `INCOMPLETE_NOT_ASSESSED`, and semantic gold is
never loaded.

A known stale, mixed, or incomplete closure ID is not a structural failure. It
is a valid semantic endpoint, is compiled into the public graph, and does not
stop the remaining arms.

### Integrity failure

A source, fixture, lock, projection, payload-binding, authorization, journal,
receipt, filesystem, or process-integrity failure means the execution evidence
can no longer support the sealed block. The runner stops before the next call,
leaves the inflight namespace as a burn marker, and forbids resume or reuse.
This condition is not converted into a partially assessed actuator result.

## Delayed semantic gold

The gold artifact remains unavailable to payload construction, provider
execution, partial-failure finalization, and all arm-local decisions. It may be
verified and loaded only after all four arms have reached valid compiled
terminal outputs.

If any arm is structurally invalid, the terminal decision is
`INCOMPLETE_NOT_ASSESSED` without loading gold. If all four compile, the runner
loads the exact locked gold once, applies the frozen classifier, and records
one of the preregistered complete-block decisions. No output may alter the
target closure, arm order, thresholds, or classifier.

Even the strongest allowed decision remains:

```text
PROMOTE_TO_FRESH_REPLICATION
```

It does not directly open v0.6.4.

## Artifact boundary

This authorization pull request contains the runner, its frozen live lock, and
this protocol, but no claimed hosted output. The later result pull request is
the only place for the immutable execution artifact, including the four-arm
attempt journal, public provider inputs, response and compiled-output receipts,
projection copy, report, manifest, and independent result validation.

Provider receipts are operator-auditable records, not provider-signed proof.
The authorization tag fixes the reviewed execution source; it does not
authenticate operator identity or guarantee global exactly-once execution
across independent clones.

## Claim boundary

This is one sealed four-call sensitivity canary. A favorable result may support
only the narrow statement that the evidence-order channel was observable on
this case and that the preregistered D placement differed directionally from
matched C under the frozen closure-choice endpoint.

Because `C -> X -> D -> Z` is one fixed serial block, it cannot by itself
separate evidence-order treatment from temporal or provider drift.

It cannot establish:

- improved answer or lineage quality;
- causal superiority of EBRT over C, X, Z, or another method;
- a population-level or generally reproducible actuator effect;
- general reasoning improvement;
- editing of hosted hidden state, attention, KV cache, or private reasoning;
  or
- equivalence between the selected public closure and private model reasoning.

v0.6.4 remains blocked until a separately designed, fresh, sealed case
replicates a non-null, directionally attributable actuator result under its own
authorization boundary.
