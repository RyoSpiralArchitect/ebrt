# EBRT v0.6.3.2-live-r01 — Sealed Mirrored Eight-Call Replication

Status: **PREREGISTERED; ZERO LIVE CALLS; AUTHORIZATION TAG REQUIRED**

This namespace executes only the four immutable provider payloads and eight
scheduled attempts already sealed by the v0.6.3.2 network-zero preflight. It
does not modify or replace that monolith, fixture, delayed gold, classifier,
zero-call lock, canonical projection, or preflight artifact.

The predecessor anchor is the annotated tag `v0.6.3.2-preflight`, tag object
`f7770f4d4ac81fc148bda99f722e50e6ad47b47c`, peeled exactly to commit
`27ad46cc1479b855fbbc450a430afeaeb97a7976`. Its committed manifest,
projection, and zero-call lock bytes are rechecked before a live namespace can
be created. This authorization change reports no hosted result.

## Separate authorization boundary

Merging this runner and its lock does not authorize provider use. The
irreversible command is permitted only after an annotated tag named
`v0.6.3.2-live-r01-authorized` points exactly at the reviewed merge commit,
that commit descends from both `origin/main` and the preflight anchor, and the
checked-out HEAD is exactly the authorized commit.

The runner also requires a completely clean worktree, including no untracked
files, before it creates the inflight namespace. The later immutable result,
journal, receipts, report, and result verifier belong in a separate change;
they must not be added retrospectively to this authorization commit.

Before the authorization tag exists, only network-zero inspection is allowed:

```bash
python3 run_actuator_uptake_replication_v0_6_3_2_live_r01.py emit-lock
python3 run_actuator_uptake_replication_v0_6_3_2_live_r01.py component-self-test
python3 run_actuator_uptake_replication_v0_6_3_2_live_r01.py preflight
```

Do **not** run `run-live` before the exact annotated authorization tag exists.

## Frozen execution geometry and identities

The block uses four provider payload identities twice, in this exact mirrored
schedule:

```text
Block A: C -> Z -> D -> X
Block B: D -> X -> C -> Z
```

There are exactly eight unique `blinded_attempt_id` values. They are the sole
keys for execution rows, provider outputs, compiled outputs, and journal
terminals. There are exactly four `blinded_request_id` values; each is reused
once in each block and denotes immutable payload identity only. Reusing a
request ID must never overwrite either attempt's output.

The provider receives only the unsealed public payload referenced by the
committed projection. It never receives block, attempt, arm, gradient,
controller, closure-role, semantic-gold, grade, or expected-result metadata.
The sole intentionally treatment-varying semantic payload field remains
evidence order. Retry, resume, reorder, backfill, replacement, pooling,
tie-break, third block, and ninth call are forbidden.

## Gold barrier and failure contract

Semantic gold is denied while all eight calls and local compilations run. The
runner does not invoke the core gold-reading self-test or lock validators in
live preflight. Only after all eight attempts are terminal and structurally
valid may the exact locked gold be loaded once and the aggregate replication
classifier run once.

A provider boundary failure or public-output structural failure is recorded
for its attempt and the remaining frozen attempts continue. After the eighth
terminal, any such block is classified locally as
`INCOMPLETE_NOT_ASSESSED`; semantic gold and both block classifiers remain
unreachable. A known stale, mixed, or incomplete closure is a valid semantic
endpoint rather than a structural failure.

A source, fixture, lock, projection, payload-binding, authorization, journal,
receipt, filesystem, or process-integrity failure is different: it freezes the
inflight namespace immediately and forbids the next call, resume, or reuse.

## Aggregate decision and stop rule

Each block is classified independently from its four attempt-keyed compiled
outputs. Only if both blocks reproduce the preregistered X-versus-Z and
D-versus-C directional contrasts may the aggregate decision be
`REPLICATION_DIRECTIONAL_COUNTERBALANCED`. One directional block is mixed;
any structurally invalid attempt is unassessed. There is no majority vote or
adaptive follow-up.

Even the strongest result may open only a separately reviewed v0.6.4
**network-zero preflight**. It never authorizes a v0.6.4 live execution.

## Claim boundary

This is one sealed mirrored eight-call replication on a synthetic case fresh
relative to the frozen v0.6.3.1 predecessor, not an independently sampled
population case or quality benchmark. Pairwise serial-position
counterbalancing narrows but does not eliminate temporal or provider drift.
No result here establishes evidence-order causality, causal superiority,
answer or lineage quality improvement, population reliability, hidden-state,
attention, KV-cache, or private-reasoning editing, or general reasoning
improvement. Provider receipts and the local authorization tag are auditable
operator records, not provider-signed proof or global exactly-once semantics
across clones.
