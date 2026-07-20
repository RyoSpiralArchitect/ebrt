# EBRT v0.5.4 — Temporal Adjoint over Factorized Lineage

Status: **COMPLETE CONTAMINATED NETWORK-ZERO MECHANISM RESULT — 17/17 HARD GATES PASS**

Decision: **`PROMOTE_V0_5_5_TEMPORAL_GATE`**

This note records the first completed temporal mechanism compiled directly from
the v0.5.3 factorized public dependency program. It does not report a hosted
model run, a generated answer, or a fresh benchmark result.

The exact promoted statement is:

> On one frozen public dependency program, normalized exact temporal credit selected a finite intervention placement that beat its node-tied projection and every locked timing permutation.

No broader wording is licensed by this artifact.

## Why this milestone exists

v0.5.3 answered a spatial question: can a minimal typed dependency program
distinguish direct and inherited evidence while preserving the known v0.5.2
lineage defect and a separately labeled contaminated repair?

v0.5.4 asks the next, narrower temporal question:

> Once that public dependency program is frozen, can exact backward credit over
> a mechanically compiled recurrence place a bounded intervention over
> operator-time sites under matched normalized actuator geometry?

The distinction matters. A dependency graph says what can affect what. A
temporal recurrence additionally says when an admitted control can affect a
later terminal state. This version tests the latter without introducing an
agent, learned router, model API, or natural-language generation.

## Frozen predecessor

The complete v0.5.3 checkpoint is pinned as immutable input:

```text
commit
  c671e149fcbe05217820512a3f90c847cbbcfbf2

tree
  f87266eb14200074ccd95c3feee1bfe170f14df3

observed graph
  8afb3d03084dc33f92ea6d12dbe7c3cfdb53f4642a5d6a937075a53dcb9a74ca

repaired graph
  361d6961938dda2d69ccc0340fecb802c55af40d6cd551c628eb307462416333

repaired closure
  899afdca968e3a3e1c1dd7f9eb5c4605e18c7c6b4188a8a4f4af1707a2859c9c

repaired grade
  2cf9e0d55ec892c187d7763507931c661ef1358578176e3b051cdff8b170d103

regression
  0335ede60f428ddf77f7266d1c2bea6483c4698e924f555e9be8a7d3422e2997
```

The policy lock also pins the byte count and SHA-256 of every v0.5.3 source,
fixture, policy, and canonical artifact used by the compiler. The builder reads
the committed `factorized_lineage_regression.json` and independently asserts
the internal graph, closure, grade, and regression fingerprints. Merely
reconstructing a similar graph is not sufficient.

## Fixture boundary

The two v0.5.4 fixtures contain symbolic policy selections only.

The event fixture declares:

- the exact v0.5.3 repaired-lineage source class;
- the fixed early and late correction schedule policies;
- the R6 correction event;
- the fact-closure terminal contract; and
- one exact normalized-adjoint control step.

The no-event fixture declares:

- the same sealed source class;
- an untriggered R6 event sentinel;
- the stable video constraint terminal; and
- exact zero control.

Fixture validation recursively rejects numeric mechanism material, including
matrices, bases, Jacobians, deltas, arbitrary operator orders, arbitrary
schedules, and terminal gold. Transition algebra, terminal targets, actuator
geometry, and controls therefore come from the byte-pinned implementation and
the sealed public lineage program rather than post-result fixture tuning.

## Compiled public program

The repaired v0.5.3 graph is compiled into a smooth float64 public recurrence.
The canonical state tensor uses the explicit axis order

```text
(channel, evidence, node)
```

with shape:

```text
(2, 6, 13)
```

The channels are `direct` and `inherited`; the evidence axes are R1-R6; and the
node axes are the sealed Evidence, Support, Fact, and Constraint nodes. The
compiled receipt retains every positive edge's ID, provenance, source, and
target. This prevents a numerically equivalent but provenance-different graph
from silently replacing the v0.5.3 public program.

The event program fingerprint is:

```text
686ae870d0694fbecc387836911b13265c04f8cc1b9bc4430369479470b32cfb
```

The no-event program is separately compiled and has fingerprint:

```text
e7a1df43374765e9a96260f473275e16a91cc2ba6a24e56aa090bfa3efde2d72
```

The early and late schedules are mechanically derived. `correction_late`
follows the sealed evidence ordinals. `correction_early` moves the invalidating
R6 immediately after the invalidated R3; the fixture is not allowed to provide
an arbitrary order.

## Forward and backward mechanism

For a schedule (o), the compiler produces a deterministic recurrence

\[
s_t = F_{o_t}(s_{t-1}, e_t, \delta_t;G),
\]

where (G) is the frozen repaired dependency graph and \(\delta_t\) is a public
bounded intervention at an eligible temporal site.

The terminal objective is evaluated only over Fact axes in the event lanes.
Stable Constraint axes are measured independently and must remain neutral.

The implementation computes terminal sensitivity three ways:

1. a manual forward Jacobian;
2. a manual reverse adjoint checked against autograd; and
3. a central finite-difference Jacobian.

Raw site leverage is

\[
s_i = \left\|\frac{\partial q}{\partial \delta_i}\right\|_2.
\]

Eligible columns are normalized before comparison:

\[
\widehat J_i = J_i / s_i.
\]

Controls are optimized in this normalized coordinate system and projected back
to raw deltas. Zero-leverage sites remain exactly zero. Every nonzero arm uses
the same normalized L2 radius

```text
rho = 0.000390625
```

and the same raw-delta bound.

This normalization is essential: the result concerns temporal placement under
the declared normalized actuator geometry, not a larger raw Jacobian column.

## Matched arms

Each event schedule evaluates the same locked family:

| Arm | Placement |
| --- | --- |
| A | exact zero control |
| B | node-tied projection of terminal credit across the eligible horizons of each node |
| C | exact normalized temporal-adjoint placement |
| D1 | within-node `cyclic_plus_1` timing permutation of C |
| D2 | within-node `cyclic_minus_1` timing permutation of C |
| D3 | within-node `reverse` timing permutation of C |

The D arms preserve the admitted control type, sign inventory, sparsity,
normalized L2 norm, and finite-leverage support while relocating timing. A sham
that collapses to the exact placement is not admitted as distinct evidence.

The final validator does not infer these properties from a constructor label.
For every emitted D arm it independently reconstructs the locked transform and
checks exact within-target-node value and sign multisets, zero count and
sparsity, eligible support, ineligible-site zeroing, node-type mapping,
normalized L2 equality, transform identity, and distinctness from C. It also
mutates one sham by flipping its sign and another by swapping values across
target nodes; both adversarial controls are required to fail the geometry
audit. This closes the earlier validator gap in which norm matching alone could
have admitted a non-matched sham.

## Locked comparison result

### Correction early

| Arm | Terminal loss |
| --- | ---: |
| A | 0.403717041015625 |
| B | 0.4029821069502741 |
| C | **0.40295594656370365** |
| D1 | 0.4029954006869283 |
| D2 | 0.40299547139812064 |
| D3 | 0.4030567659504193 |

The C margin over B is `2.616038657043962e-05`. The C margin over the best
distinct D arm is `3.945412322464703e-05`.

### Correction late

| Arm | Terminal loss |
| --- | ---: |
| A | 0.708404541015625 |
| B | 0.7076684250695172 |
| C | **0.7076294911993222** |
| D1 | 0.7077195378225308 |
| D2 | 0.7077196250595027 |
| D3 | 0.7077492069092428 |

The C margin over B is `3.8933870195045905e-05`. The C margin over the best
distinct D arm is `9.004662320866164e-05`.

C is strictly below A, B, and every distinct locked D arm for both schedules at
the locked `1e-12` strictness boundary. The comparison fingerprint is:

```text
befa18d6c02698dbb7bda6ce3fb8d27ff9fa5b1b1d483eda984f946a843b79e5
```

These are two schedules over one synthetic public program, not independent
replications and not an estimate of general effect size.

This is an implementation-gated development result, not an independently
preregistered or held-out experiment. The comparison family and stop rule were
declared before the canonical bundle was frozen, but the mechanism and its
artifact were developed in the same research cycle.

## Temporal switch

The top normalized-credit site changes with evidence order.

```text
correction_early
  q:correction_early:h06:R5:support:demo_readiness
  |credit| = 0.7133158631277372
  runner-up margin = 0.013797212052760965

correction_late
  q:correction_late:h06:R6:support:superseding_guidance
  |credit| = 1.0281461554883407
  runner-up margin = 0.23053567123948882
```

The horizon evidence ID names the currently admitted horizon; it is not a
claim that the site is a direct evidence gate on that ID. The tested statement
is only that the exact top eligible public intervention site changes between
the mechanically derived schedules.

## Mechanism checks

The largest observed numerical discrepancies were:

```text
manual forward vs autograd Jacobian
  0.0

manual reverse vs autograd gradient
  0.0

central finite difference vs analytic Jacobian
  1.234212732015294e-10

normalized eligible-column norm error
  1.1102230246251565e-16
```

Severing `repair:final_priority->demo_centerpiece` changed the maximum upstream
R2-to-demo inherited Jacobian from `0.03515625` to exact `0.0`. This is the
declared dependency-locality witness.

Inserting an identity operation preserves state and credit exactly. Permuting
the two declared independent Support operations preserves state and the
reordered Jacobian exactly. These tests are local compiler invariants, not a
general commutativity theorem for arbitrary reasoning programs.

## Stable constraint sealed lane

The bundle includes `stable_constraint_sealed_lane.json` under the same sealed
lane schema used by the event schedules. It exposes Constraint terminal axes
only and records:

```text
event_triggered          false
control_values           []
backward_calls           0
neutral_equals_controlled true
```

Its associated no-event audit also records zero network calls, zero provider
calls, zero controls, and exact output identity. This lane is the frozen
disconnected-isolation input intended for the next lane-composition milestone;
it is not evidence of an event detector's calibration.

## Exact hard gates

All 17 locked gates passed:

1. `v053_source_exact`
2. `compiled_closure_exact`
3. `fixture_mechanism_injection_rejected`
4. `forward_sensitivity_agreement`
5. `reverse_adjoint_agreement`
6. `central_finite_difference_agreement`
7. `normalized_jacobian_geometry`
8. `severed_path_zero_credit`
9. `independent_operator_permutation_invariant`
10. `identity_insertion_invariant`
11. `early_late_top_credit_switch`
12. `no_event_exact_identity`
13. `matched_control_geometry`
14. `exact_credit_beats_zero_and_node_tied`
15. `exact_credit_beats_all_timing_shams`
16. `two_build_byte_identity`
17. `socket_denied_network_zero`

`promotion_ready` is the conjunction of this exact set. Missing gates, extra
gates, false gates, or a mismatched decision label are rejected. Had any gate
failed, the only valid decision under this namespace would have been
`STOP_V0_5_5_TEMPORAL_GATE`.

## Sealed artifact bundle

The canonical files are:

```text
artifacts/temporal_adjoint_lineage_v0_5_4/
  source_receipt.json
  compiled_programs.json
  actuator_geometry.json
  arm_comparison.json
  correction_early_sealed_lane.json
  correction_late_sealed_lane.json
  stable_constraint_sealed_lane.json
  no_event_audit.json
  self_test.json
  mechanism_report.md
  manifest.json
```

Artifact SHA-256 values:

```text
source_receipt.json
  9968c785d2dd8353df8d39a579af94eca57d13456fb96eac92489e19c4698988
compiled_programs.json
  357bab8950da93a08c0d3f459bcf347e533feac28629db7bd77fa87e60c805ab
actuator_geometry.json
  f257403ddbf204d46af5c3807c37b3102fe8e7c39da35b62840b400e7a96b43f
arm_comparison.json
  944039a8c58b61847d8ee0ed78c1b9adcc7903a49d13c787afab0bc22e6f2f23
correction_early_sealed_lane.json
  799b2d6b10129e63e751054e995d2e5017a2f73af44916d68068ee3c82b72d17
correction_late_sealed_lane.json
  54c806a29fdf80f9677b5a008e140734e28a201e719a98ce8d312bf34298afc8
stable_constraint_sealed_lane.json
  379e63f9bfce0af69df2240fe85835b7032efb0de3209773f71f818ba43f40cb
no_event_audit.json
  e11206e1026920108c27fdeba604138605a3b6f673003c3be86b5c37d5e10a19
self_test.json
  488b5041ef99b1b8663a03d098a426c7c59a88de4e2a257f03a1f72b24f8c5d4
mechanism_report.md
  7af2346ec0d1b20376aa0a9ea679deda1a24a8161046273550c7698fdc1a292c
manifest.json
  60423518deee7e6b4bd69678a51d84269378e4725711803c46d079940227913b
```

The builder validates strict UTF-8 JSON with duplicate-key and non-finite
constant rejection. It verifies portable repository-relative source receipts,
requires two byte-identical builds, denies socket creation during
materialization, detects source/fixture/predecessor/artifact/manifest tampering,
rejects coherently re-signed source receipts and reports, rejects extra,
missing, and symlinked artifact entries, and verifies atomic-publication
rollback.

The canonical manifest excludes timestamps, hostnames, absolute paths, and
observed runtime metadata. The successful build was validated with Python
3.13.13 and PyTorch 2.11.0 on Darwin arm64. System Python 3.9.6 did not contain
PyTorch, so no cross-runtime numerical-byte claim is made.

Reproduction commands:

```bash
python3 -B temporal_adjoint_lineage_v0_5_4.py self-test
python3 -B benchmark_temporal_adjoint_lineage_v0_5_4.py self-test
python3 -B benchmark_temporal_adjoint_lineage_v0_5_4.py validate
python3 -B build_temporal_adjoint_lineage_artifact_v0_5_4.py self-test
python3 -B build_temporal_adjoint_lineage_artifact_v0_5_4.py build
python3 -B build_temporal_adjoint_lineage_artifact_v0_5_4.py validate
```

## Claim boundary

The artifact establishes only the exact quoted local claim at the top of this
note. It does not establish that:

- GPT or another hosted model exposes an editable hidden trajectory;
- gradients pass through a semantic adapter, provider, or generated answer;
- public lineage is isomorphic to private model computation;
- the supplied dependency program was autonomously discovered;
- the early and late schedules are independent replications;
- the result transfers to another graph, task, model, or language domain;
- a better local surrogate predicts a better natural-language output;
- temporal credit is globally optimal or causally superior in an unrestricted
  reasoning system; or
- v0.5.4 is a production inference engine.

The positive gate only permits the next network-zero question: whether several
sealed public trajectories can be composed while preserving lane-local
provenance, isolation, and exact block credit.
