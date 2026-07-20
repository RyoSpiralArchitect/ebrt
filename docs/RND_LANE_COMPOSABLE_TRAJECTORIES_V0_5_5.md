# EBRT v0.5.5 — Lane-Composable Public Trajectories

Status: **COMPLETE CONTAMINATED NETWORK-ZERO MECHANISM — 10/10 TOP-LEVEL GATES AND 10/10 REQUIRED SUBCHECKS PASS**

Decision: **`PROMOTE_V0_6_LANE_COMPOSITION_GATE`**

This note records the completed multiplicity milestone that follows the v0.5.4
temporal adjoint result. It does not report a hosted-model run, an agent system,
a generated answer, or a final-output improvement.

The exact promoted statement is:

> On one contaminated frozen public bundle, EBRT composed three byte-sealed
> trajectories through one typed merge junction while preserving
> shared-evidence byte identity, lane-local provenance and isolation, and exact
> block-gradient agreement.

No broader wording is licensed by this artifact.

## Why this milestone exists

v0.5.3 made public support lineage factorized and testable. v0.5.4 compiled that
program into a differentiable recurrence and routed exact terminal credit over
operator-time sites. Both milestones still evaluated one trajectory at a time.

v0.5.5 asks one narrower question:

> Can three byte-sealed public trajectories share one evidence ledger and one
> typed merge junction while preserving shared-evidence identity, lane-local
> provenance and isolation, and exact block-gradient agreement?

The milestone adds composition only. It does not add autonomous orchestration.

## Frozen predecessor

The v0.5.4 checkpoint is immutable input:

```text
commit
  0820da1b79b3f912f7cde84aa13014c28951eb05

tree
  7e21fe0f5dbcf93c85660bb466041b6f0c1b6d13

manifest
  60423518deee7e6b4bd69678a51d84269378e4725711803c46d079940227913b

correction_early lane
  799b2d6b10129e63e751054e995d2e5017a2f73af44916d68068ee3c82b72d17

correction_late lane
  54c806a29fdf80f9677b5a008e140734e28a201e719a98ce8d312bf34298afc8

stable_constraint lane
  379e63f9bfce0af69df2240fe85835b7032efb0de3209773f71f818ba43f40cb
```

The v0.5.5 policy lock pins every predecessor source, fixture, artifact, and
lane receipt. The canonical bundle byte-copies the three lane JSON files into
`sealed_lanes/`; it does not recreate or normalize them.

## Minimal composition substrate

```text
correction_early  --\
correction_late   ----> typed Fact equality junction --> terminal evaluation

stable_constraint -----------------------------> isolated Constraint audit
```

Every lane keeps its own namespace, source receipt, temporal schedule, and
public controls. Shared evidence is admitted only through a canonical ledger
keyed by Evidence ID and content SHA-256. Reusing an Evidence ID with different
bytes is invalid.

That digest binds canonical public node-payload bytes across these sealed lanes.
It does not establish evidence truth, semantic equivalence, or provenance
beyond the pinned source artifact.

The only merge admitted in this version is one frozen, acyclic, typed junction.
It may relate declared compatible terminal Fact axes. It cannot introduce an
undeclared cross-lane edge, merge a Constraint into a Fact, or rewrite a lane's
sealed public program.

## Block credit

Let lane \(i\) expose a terminal public vector \(q_i(u_i)\), with lane-local
control \(u_i\). Stack those outputs as \(q\), let \(A\) be the mechanically
compiled typed incidence matrix, and let \(m\) be a separately bounded merge
slack. The raw disagreement and residual are

\[
d=Aq,
\qquad
r=Aq-m.
\]

The bundle objective is a deterministic local public loss

\[
J(u_1,u_2,u_3,m)=
\sum_i J_i(u_i)
+\tfrac12\lVert Aq-m\rVert_2^2
+\tfrac12\lVert m\rVert_2^2,
\]

where every \(J_i\), admitted control site, and bound comes from a sealed lane
or the frozen merge contract. The merge regularizer prevents disagreement from
being hidden without cost in \(m\). The terminal seed for lane \(i\) and the
merge-control gradient are

\[
\psi_i=\nabla_{q_i}J_i+A_i^{\top}(Aq-m),
\qquad
g_m=-(Aq-m)+m.
\]

The complete block gradient is

\[
\nabla_{(u,m)} J =
\begin{bmatrix}
\nabla_{u_1}J \\
\nabla_{u_2}J \\
\nabla_{u_3}J \\
g_m
\end{bmatrix}.
\]

The implementation must agree across its declared exact/manual construction,
full autograd, and central finite differences. The stable Constraint lane is
disconnected from the Fact junction, so its cross-lane block and control must
remain exactly zero under the locked tolerance.

The public audit records \(Aq\), \(m\), and \(Aq-m\) separately; it does not
collapse raw disagreement, admitted merge control, and residual into one value.

This backward pass exists only inside the public PyTorch substrate. It does not
cross JSON, a provider API, token sampling, or a model's hidden state.

## Deterministic contracts

The canonical artifact separates seven public payloads:

- `shared_evidence_ledger.json` records Evidence IDs and exact content hashes;
- `sealed_bundle.json` records the three immutable lane receipts and namespace;
- `merge_contract.json` records the one typed junction and its admitted axes;
- `bundle_control_map.json` records bounded lane and merge controls separately;
- `block_adjoint_audit.json` records manual, autograd, and finite-difference
  block checks;
- `hard_gate_audit.json` records promotion gates and every adversarial
  subcheck; and
- `self_test.json` mirrors the exact promotion conjunction.

The manifest covers all seven payloads, the human-readable mechanism report,
and all three nested lane copies. Unknown, missing, extra, non-regular, and
symlink entries are rejected. Publication uses a staging directory and restores
the previous complete bundle if replacement fails.

## Locked hard gates

Promotion is the conjunction of these ten top-level gates and every boolean
subcheck recorded below them:

1. exact v0.5.4 source gate;
2. exact one-lane degeneration;
3. shared-ledger consistency;
4. namespace isolation;
5. block-gradient agreement;
6. disconnected-lane zero response;
7. invariance under all six lane permutations;
8. tamper-ready source and artifact receipts;
9. complete lane and merge bounds; and
10. deterministic zero-provider, zero-network execution.

The adversarial surface includes duplicate lane aliases, conflicting evidence
hashes, conflicting terminal-axis targets, forbidden schema fields, source
mutation, semantic artifact mutation, coherent re-signing, two independent
builds, socket denial, and publication rollback.

The success status is exactly:

```text
PROMOTE_V0_6_LANE_COMPOSITION_GATE
```

Any failed gate or boolean subcheck yields exactly:

```text
STOP_V0_6_LANE_COMPOSITION_GATE
```

## Canonical result

The sealed bundle passed all ten top-level gates and all ten required named
subchecks. The source result and builder self-test both report
`PROMOTE_V0_6_LANE_COMPOSITION_GATE`, with provider and network calls exactly
zero.

```text
source bundle fingerprint
  5bfbe5c07ae05208a403092b1011b1ccbe876d7f8dbe8a692aeac14bd92f8429

core self-test fingerprint
  d49992fe602bdc75d5d65675f39076f2b021e51fc7f385df70b3e8ba2db83d8f

canonical manifest file
  b26db72c0f3316565e7967b27f96ea5a2e6aa0b91d68ef539dd16fe7166f00f1

shared-ledger artifact
  b3d93b93cf8deb472ccb1cb93213f81c9db64af278faa5ca3bf507688967b172

block-adjoint artifact
  4a63577a6b924acf35fe455194219aeda7d28875d67c5376843f68c32151f703

control-map artifact
  d45c77ddfe3fc871ac35696e062bd21320d970fd962dc1c81569db93877f24e0
```

The merge contract contains one typed junction, 24 exact same-axis incidence
clauses, and a 24-dimensional separately bounded merge-control vector. The
stable Constraint lane participates in the bundle but in none of those
clauses.

| Audit | Observed | Locked tolerance | Result |
| --- | ---: | ---: | --- |
| block vs full autograd max absolute error | `2.220446049250313e-16` | `2e-12` | PASS |
| matrix-free reverse vs autograd max absolute error | `0.0` | `2e-12` | PASS |
| central finite difference vs autograd max absolute error | `1.238149138771405e-09` | `5e-8` | PASS |
| lane-order permutations | `6/6` exact | `6/6` | PASS |

The one-lane bundle reduced exactly to the sealed v0.5.4
`correction_early` lane: its incidence matrix had zero rows, its merge-control
vector was empty, its objective equaled the source-lane objective, and its
generated/source equivalence fingerprints were both
`c0b1c3c1b7f5c5502be311002f011cf246c31b5e4d8fea32b6fba039cb21b4ff`.

The three-lane neutral objective was `1.34063720703125`; one bounded public
control step produced `1.3387428526673435`. This decrease is a local
mechanism sanity check under the contaminated frozen objective. It is not a
claim about answer quality or superiority over another reasoning method.

The builder then passed a second independent byte-identical build, strict JSON
duplicate and non-finite rejection, source and semantic-artifact mutation,
coherent re-signing and JSON-reformat attacks, extra/missing/symlink rejection,
socket denial, and atomic-publication rollback. Standalone validation rebuilt
the expected payload from the pinned inputs and returned
`VALID_CANONICAL_NETWORK_ZERO_ARTIFACT` without using the validator host as a
promotion gate.

## Claim boundary

The sealed bundle passed, so this version may say:

> On one contaminated frozen public bundle, EBRT composed three byte-sealed
> trajectories through one typed merge junction while preserving
> shared-evidence byte identity, lane-local provenance and isolation, and exact
> block-gradient agreement.

It may not say that:

- multiple agents or models were executed or coordinated;
- a learned router or arbiter selected a lane;
- the merge represents private chain-of-thought or hosted-model hidden states;
- a provider, tool, memory system, or final-output generator participated;
- composition improved an answer, reasoning quality, or general capability; or
- a contaminated synthetic mechanism result estimates a population effect.

## What follows

v0.6 may define how external executions populate sealed lanes and how one
controlled full-context regeneration consumes a merged public program. That
protocol must be separately locked. It cannot revise v0.5.5 after observing a
provider output, and it cannot use the v0.5.5 mechanism gate as evidence of
multi-agent superiority.
