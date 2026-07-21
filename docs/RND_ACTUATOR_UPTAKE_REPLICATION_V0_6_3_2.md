# EBRT v0.6.3.2 — Mirrored Fresh Actuator Replication

Status: **NETWORK-ZERO PREFLIGHT; NO LIVE CALL AUTHORIZED**

## Why this namespace exists

The frozen v0.6.3.1 live result observed a directional public closure pattern
in one serial `C -> X -> D -> Z` block. X and D selected the preregistered
aligned closure while Z and C did not. That result established a useful
sensitivity candidate, but one case and one fixed serial order cannot separate
the evidence-order contrast from temporal or provider drift.

v0.6.3.2 asks one narrower follow-up question:

> Does the same EBRT-derived public evidence-order contrast appear in both
> halves of one fresh sealed case when the paired arms exchange early and late
> serial positions?

This is a replication gate, not a quality benchmark. It neither rewrites nor
regrades v0.6.3.1.

## Network-zero surface

The namespace consists of one producer monolith, two frozen semantic inputs,
one pure-stdlib verifier, one policy lock, and one canonical preflight artifact:

```text
actuator_uptake_replication_v0_6_3_2.py
fixtures/actuator_uptake_replication_v0_6_3_2.json
fixtures/actuator_uptake_replication_gold_v0_6_3_2.json
verify_actuator_uptake_replication_v0_6_3_2_portable.py
policy_lock_actuator_uptake_replication_v0_6_3_2.json
artifacts/actuator_uptake_replication_v0_6_3_2_preflight/
```

The producer contains no live command. Reproduce only the network-zero
contracts with:

```bash
python3 actuator_uptake_replication_v0_6_3_2.py self-test
python3 actuator_uptake_replication_v0_6_3_2.py build-artifact
python3 actuator_uptake_replication_v0_6_3_2.py validate-artifact
python3 -I -S verify_actuator_uptake_replication_v0_6_3_2_portable.py verify
python3 -I -S verify_actuator_uptake_replication_v0_6_3_2_portable.py self-test
```

`emit-lock` constructs the reviewed zero-call lock. It is not provider
authorization. Any live run needs a separate reviewed runner, merged execution
lock, and exact annotated authorization tag.

## Fresh relative to the frozen predecessor

The synthetic shipment-manifest case is fresh relative to the frozen v0.6.3.1
predecessor, not an independently sampled population case. It is structurally
isomorphic to the earlier archive case while rotating every semantic
coordinate that could silently preserve the earlier response:

- case, checkpoint, question, evidence text, and evidence IDs are new;
- evidence IDs use `N1` through `N7`, disjoint from the earlier `E...` set;
- all evidence-row byte hashes are disjoint from v0.6.3.1;
- the candidate-ID salt and all four opaque candidate IDs are new;
- the correct answer moves from choice ordinal 0 to ordinal 1;
- the aligned closure moves from catalog ordinal 3 to ordinal 1; and
- the candidate catalog is byte-identical in every one of the four arm
  payloads and therefore in all eight scheduled attempts.

The producer and portable verifier reject drift in these freshness properties.
There was no provider probing, pilot call, or case selection by hosted output.

## One actuator, four payload bytes, eight attempts

The local mechanism is unchanged in kind from v0.6.3.1:

```text
public recurrent surrogate
  -> one real local float64 backward pass
  -> deterministic path-block placement
  -> stop-gradient / JSON boundary
  -> full raw evidence payload
  -> hosted selected_closure_id
```

Z is the frozen neutral order. X is the preregistered correction-first positive
control. D places the locally preferred path block before the opposed block. C
is the geometry-matched anti-placement. C and D keep the event, invalidated
evidence, and stable evidence at identical positions and are matched in
Spearman footrule, Kendall distance, and fixed-point count relative to Z.

Exactly four distinct canonical provider payload byte strings are sealed—one
per arm. The execution plan references each byte string twice. Block and arm
metadata, attempt IDs, gradients, gold, role labels, and expected answers are
never inside the provider payload.

The exact schedule is:

```text
Block A: C -> Z -> D -> X
Block B: D -> X -> C -> Z
```

Thus C and D each occupy positions `{1, 3}`, with their order reversed between
blocks. Z and X each occupy positions `{2, 4}`, also with their order reversed.
Every scheduled attempt has a unique local blinded attempt ID, but a repeated
arm resolves to the same sealed request ID, payload fingerprint, and payload
bytes in both blocks.

There is no retry, resume, backfill, tiebreak, adaptive prompt edit, third
block, or ninth call. A separately authorized live namespace must continue
after known semantic failures, while recording malformed, schema-invalid, or
unknown-closure outputs as structurally invalid. One invalid attempt makes the
aggregate result `INCOMPLETE_NOT_ASSESSED`; it cannot be rescued.

## Primary and secondary public fields

The primary action is exactly:

```text
selected_closure_id
```

The provider also returns `reviewed_evidence_ids`. The fixed instruction asks
it to echo the first three presented evidence IDs as an inspection receipt.
That receipt is intentionally secondary and tautological to the ordering
instruction. Its adherence value is excluded from closure grading, the
per-block directional classifier, and the aggregate replication gate.

The provider does not emit a graph. The local compiler expands one known opaque
closure coordinate into a typed public Evidence-to-Decision graph. Known
aligned, alternative, stale, and mixed closures all compile; stale or mixed
coordinates are measured semantic endpoints rather than structural errors.

## Delayed gold boundary

The provider-excluded gold file names the aligned construct target, quality-
valid alternatives, answer, record format, and closure roles. Network-zero
conformance may validate it. A future live runner must deny the gold path from
startup through all provider calls and compile steps.

Gold may be loaded exactly once only after all eight attempts have produced
structurally valid compiled terminals. If even one terminal is missing or
invalid, gold remains unread and the block is incomplete. No arm-specific
semantic classification may occur between calls.

## Per-block classifier

Each complete block independently applies the frozen directional grammar.
For the positive contrast Z to X and placement contrast C to D, with aligned
target `T`:

- directional: reference is not `T`, actuator is `T`;
- ceiling: both are `T`;
- null: both select the same off-target coordinate;
- adverse: reference is `T`, actuator is not `T`; and
- ambiguous: both are off-target and select different coordinates.

A favorable block therefore requires both:

```text
X = aligned and Z != aligned
D = aligned and C != aligned
```

Inspection-receipt adherence, answer equality, output-byte inequality, and
secondary quality fields cannot make a block directional.

## Aggregate strict AND

The aggregate gate never pools closures and never uses a majority vote.
For each contrast:

- two directional blocks become `REPLICATED_DIRECTIONAL`;
- exactly one directional block becomes `MIXED`;
- two matching non-directional statuses retain ceiling, null, adverse, or
  ambiguous meaning; and
- two differing non-directional statuses become heterogeneous/ambiguous.

Only this exact conjunction succeeds:

```text
positive control: REPLICATED_DIRECTIONAL
gradient placement: REPLICATED_DIRECTIONAL
```

Its terminal name is:

```text
REPLICATION_DIRECTIONAL_COUNTERBALANCED
```

The other aggregate terminals are:

```text
INCOMPLETE_NOT_ASSESSED
STOP_REPLICATION_MIXED
STOP_REPLICATION_ADVERSE
STOP_REPLICATION_AMBIGUOUS
STOP_REPLICATION_CEILING_NOT_ASSESSED
STOP_REPLICATION_NULL
```

The network-zero self-test exhausts all 256 per-block closure combinations and
all 49 aggregate-status pairs. Aggregate success opens only the design of a
separately reviewed **v0.6.4 network-zero preflight**. It never authorizes a
v0.6.4 live call.

## Claim boundary

Even a complete directional replication can safely support only this statement:

> A public evidence-order contrast repeated on one fresh sealed case under
> pairwise serial-position counterbalancing.

It does not establish:

- a causal evidence-order effect;
- improved answer, lineage, or reasoning quality;
- population reliability or case-family generalization;
- robustness across models, providers, prompts, or budgets;
- hosted hidden-state, attention, or KV-cache editing;
- equivalence between public closure selection and private reasoning; or
- permission to start a v0.6.4 live evaluation.

The two blocks still occur serially and therefore do not remove all provider
time drift. Counterbalancing narrows one alternative explanation; it does not
turn one fresh case into a population result.

## Stop rule

This is the last actuator-replication experiment before product convergence.
No result may trigger a third block, alternate seed, relaxed gold, prompt
tuning, rescue call, or post-hoc case replacement. After one separately
authorized eight-call block, the namespace is frozen and the project returns
to the Reasoning IDE and submission surface.
