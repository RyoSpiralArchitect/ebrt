# EBRT v0.5.3 — Factorized Lineage Regression

Status: **COMPLETE NETWORK-ZERO CONTAMINATED ENGINEERING REGRESSION**

This note records the successor to the frozen v0.5.2 strict near-pass. The
source, fixtures, policy lock, and independently reloadable local artifact are
complete. v0.5.3 reports a public-lineage representation result only; it does
not report a new hosted-model result.

## Fixed predecessor evidence

The canonical v0.5.2 walkthrough remains unchanged:

- both provider calls completed;
- the public answer changed `POLISH -> PROVE`;
- R3 left active support and was marked invalid;
- R4 and R6 entered aggregate active support;
- the `THREE_MINUTE_NARRATED` fact remained stable; and
- the strict endpoint remained
  `walkthrough_contract_passed=false`.

The only failed strict check was fact-local support:

```text
final_priority
  observed: R2, R6
  missing:  R4

demo_centerpiece
  observed: R4, R6
  missing:  R2
```

The predecessor artifact is preserved under tag
`v0.5.2-inspector-breakpoint`, which resolves to commit
`6cd42f2528cab6df2c943e1e080d14c7904fb0e5`. v0.5.3 does not relax its gold,
rerun it, or call it an effective pass.

## Research question

Can a minimal typed public dependency program represent why evidence supports a
fact, distinguish direct from inherited evidence, and reproduce the known
v0.5.2 defect before applying a separately declared contaminated repair?

This is a representation and regression question. It is not a test of whether
GPT discovers a graph, whether a generated answer improves, or whether a
differentiable controller caused the v0.5.2 output change.

## Minimal public program

### Node types

The v0.5.3 vocabulary is intentionally small:

| Type | Role |
| --- | --- |
| `evidence` | admitted public observation or update, including R1-R6 |
| `support` | intermediate public reason that can be reused by more than one fact |
| `fact` | decision fact evaluated by the strict endpoint |
| `constraint` | stable public invariant that must be preserved |

The first version does not add entities, a general ontology, modal logic,
probabilistic causal semantics, or free-form relation names.

The exact public schema identifiers include:

```text
ebrt-factorized-lineage-graph-v0.5.3
ebrt-factorized-lineage-closure-v0.5.3
ebrt-factorized-lineage-closure-gold-v0.5.3
ebrt-factorized-lineage-grade-v0.5.3
ebrt-factorized-lineage-regression-v0.5.3
```

### Edge relations

Edges point from a prerequisite toward the state it supports or constrains:

| Relation | Positive closure? | Meaning |
| --- | ---: | --- |
| `supports` | yes | only `Evidence -> Support` |
| `depends_on` | yes | only `Support -> Fact|Constraint` or `Fact -> Fact`; target depends on source |
| `invalidates` | no | only late `Evidence -> Evidence` revocation |

Direct `Evidence -> Fact|Constraint`, `Support -> Support`, every outgoing
`Constraint` edge, and every other source/target pair are invalid. A Fact can
therefore transmit an already formed dependency to another Fact, but raw
evidence cannot bypass the explicit Support layer.

Only the subgraph induced by `supports` and `depends_on` must be acyclic and is
used for positive lineage closure. `invalidates` is evaluated separately. An
invalidated evidence node and any witness path that relies on it are excluded
from active closure even if a positive edge remains in the historical graph.

### Provenance

Every edge uses one locked provenance value:

- `observed` — a relationship explicitly present in the frozen v0.5.2 public
  artifact;
- `migration_inferred` — deterministic structural translation of a flat legacy
  list that adds no effective evidence reachability; or
- `repair_overlay` — the only post-defect, contaminated addition.

The artifact never presents an overlay edge as provider-observed or as part of
the legacy card. The policy lock pins this vocabulary and the separate overlay
fixture bytes.

## Direct and inherited closure

For a positive graph \(G^+=(V,E_{supports}\cup E_{depends\_on})\), define the
active evidence closure of node \(v\) as the non-invalidated evidence ancestors
of \(v\):

\[
C(v)=\{e\in V_{evidence}: e\leadsto v \text{ in }G^+
\land e\notin I\},
\]

where \(I\) is the set revoked by valid `invalidates` edges at the evaluation
horizon.

For each graded Fact or Constraint terminal, the artifact partitions closure
into:

- **direct evidence:** active evidence with a positive path to the terminal
  containing no intermediate Fact; and
- **inherited evidence:** active evidence with a positive path containing at
  least one intermediate Fact, unless that evidence ID also has a direct path.

Support normalization nodes do not make a path inherited. If both path classes
exist, the evidence ID is classified only as direct so the two reported sets are
disjoint.

Every reported item carries a deterministic witness path. Within the applicable
direct or inherited class, canonical ranking first minimizes the number of
`repair_overlay` edges, then path length, then the full node-ID path, and then
the edge-ID path lexicographically. Thus a contaminated repair cannot take
credit for lineage that already had a non-repair path. Closure is a set for
grading, and direct, inherited, and total active evidence must match their
expected sets exactly rather than by subset.

The validator must reject cycles, dangling references, duplicate IDs,
undeclared relations, illegal node-type pairs, self-edges, ambiguous ordinals,
and witness paths inconsistent with the frozen graph.

## Two derivations from one frozen card

### A — Lossless migration

The lossless migration translates only relationships explicitly present in the
v0.5.2 After card:

```text
R2 -[supports]-> support:judging_basis
                       -[depends_on]-> fact:final_priority

R4 -[supports]-> support:demo_readiness
                       -[depends_on]-> fact:demo_centerpiece

R5 -[supports]-> support:video_constraint
                       -[depends_on]-> constraint:video_constraint

R6 -[supports]-> support:superseding_guidance
                       -[depends_on]-> fact:final_priority
                       -[depends_on]-> fact:demo_centerpiece

R6 -[invalidates]-> R3
```

These four role bindings are explicit, case-specific structural annotations
over the frozen public card. v0.5.3 does not claim to discover them from raw
language. Their losslessness is checked by requiring their induced fact-local
citations to equal the frozen card exactly.

Intermediate support nodes may normalize these attachments, but they may not
create a new dependency between decision facts or attach previously missing
evidence to a fact.

Required result: the migrated graph diagnoses the same gaps as the legacy
contract. If the lossless graph passes both facts, the migration has leaked the
known endpoint into representation construction and the v0.5.3 launch gate
fails.

The exact expected lossless partitions are:

```text
final_priority
  direct:    R2, R6
  inherited: empty
  missing:   R4

demo_centerpiece
  direct:    R4, R6
  inherited: empty
  missing:   R2
```

### B — Contaminated two-edge repair overlay

The repair is explicitly informed by the observed defect. In conceptual form,
the migrated program contains a reusable live-proof support node sourced by R4,
alongside the two decision-fact nodes. The overlay adds exactly:

```text
support:demo_readiness -[depends_on]-> fact:final_priority
fact:final_priority    -[depends_on]-> fact:demo_centerpiece
```

The first edge lets R4 reach `final_priority`. The second lets the judging basis
already attached to `final_priority`, including R2, reach
`demo_centerpiece`. R6 remains an explicit direct superseding update rather than
being manufactured by the overlay.

The exact node and edge IDs, source hashes, and canonical order are fixed in the
v0.5.3 lock. Removing either overlay edge reopens its corresponding expected
gap. Adding R2/R4/R6 directly to every fact is not an eligible repair because
it would restate the answer instead of representing dependency.

The intended repaired closure is:

```text
final_priority
  direct:         R2, R4, R6
  inherited:      empty
  active closure: R2, R4, R6

demo_centerpiece
  direct:         R4, R6
  inherited:      R2
  active closure: R2, R4, R6

stable video constraint
  direct:         R5
  inherited:      empty
  active closure: R5

invalidated evidence
  R3
```

This expected partition was observed exactly in the canonical v0.5.3 artifact.
The repair changes reachability only for `(final_priority, R4)` and
`(demo_centerpiece, R2)`; it removes or reclassifies no pre-existing support.

## Required local artifact split

The network-zero build keeps the following surfaces separate. The canonical
files are:

1. `lossless_migration.json` — frozen predecessor reference, lossless graph,
   direct/inherited closure, and reproduced gaps;
2. `fixtures/factorized_lineage_v0_5_3_repair_overlay.json` — the only source
   of contaminated repair edges;
3. `fixtures/factorized_lineage_v0_5_3_closure_gold.json` — the separately
   pinned exact closure contract, never a graph-construction input;
4. `factorized_lineage_regression.json` — merged repaired graph, path receipts,
   immutable legacy result, and new regression grades;
5. `self_test.json` — mutation and mechanism checks;
6. `mechanism_report.md` — human-readable result and claim boundary; and
7. `manifest.json` — source, fixture, policy, runtime contract, hashes, and
   network-call accounting.

The legacy boolean and the new regression boolean are different fields. A
passing new regression must never overwrite or alias
`walkthrough_contract_passed=false`.

## Network-zero acceptance gates

The first reportable v0.5.3 artifact demonstrated all of the following after
reloading emitted bytes:

1. schema and graph invariants pass;
2. the predecessor source/hash references match the frozen checkpoint;
3. the exact legal edge grammar is enforced and every forbidden pair is
   rejected;
4. lossless migration reproduces both missing-evidence diagnoses;
5. the overlay is exactly the separately locked two-edge set;
6. repaired direct, inherited, and total closure exactly match their declared
   sets;
7. every reported evidence item has the repair-minimizing, then
   length-and-lexicographically canonical full-path witness;
8. R3 is absent from active closure and remains visible as invalidated history;
9. R5 remains the sole stable video constraint support;
10. removing either repair edge reopens its declared lineage gap;
11. cycle, dangling-reference, type, provenance, forbidden-key, and tamper
    mutations are rejected;
12. two same-runtime builds are byte identical; and
13. materialization succeeds while socket creation is denied and records zero
    provider/network calls.

Failure of any gate would have left v0.5.3 unaccepted. All gates passed; the
frozen predecessor remains unchanged.

The implementation surface is `factorized_lineage_v0_5_3.py`, with
`self-test`, `demo`, and `validate` commands. The sealed builder exposes
`self-test`, `build`, and `validate`:

```bash
python3 factorized_lineage_v0_5_3.py self-test
python3 factorized_lineage_v0_5_3.py validate
python3 build_factorized_lineage_artifact_v0_5_3.py self-test
python3 build_factorized_lineage_artifact_v0_5_3.py validate
```

The canonical bundle is committed under
`artifacts/factorized_lineage_v0_5_3/`.

## Locked result

The lossless lane remains `FAIL` with exactly the two predecessor gaps. The
separate repaired lane is `PASS` under exact direct, inherited, total,
invalidation, and stable-constraint grading.

```text
observed graph fingerprint
  8afb3d03084dc33f92ea6d12dbe7c3cfdb53f4642a5d6a937075a53dcb9a74ca

repaired graph fingerprint
  361d6961938dda2d69ccc0340fecb802c55af40d6cd551c628eb307462416333

regression bundle fingerprint
  0335ede60f428ddf77f7266d1c2bea6483c4698e924f555e9be8a7d3422e2997

provider/network calls
  0
```

Core self-tests passed under the available Python 3.13 and system Python 3.9
runtimes. The builder reconstructed byte-identical outputs twice, rejected
source/fixture/artifact/coherent-resign/symlink/file-set tampering, verified
publication rollback, and completed with socket creation denied. This is a
deterministic local mechanism record, not cross-platform proof for arbitrary
runtimes.

## Hosted regression eligibility

No provider call belongs to the network-zero result. A later live regression
requires a separately committed lock covering prompt, model, reasoning effort,
token ceiling, phase order, retries, artifact policy, and strict grading.

If a three-trial block is later used, report:

```text
run_status:
  COMPLETE     all declared provider attempts yielded valid artifacts
  DEGRADED     the lock explicitly permits partial runtime assessment
  INCOMPLETE   the semantic endpoint cannot be assessed as declared

regression_status:
  PASS          every completed declared strict pair passes and the block is complete
  FAIL          at least one assessable declared pair fails
  NOT_ASSESSED  provider/runtime incompleteness closes the semantic gate
```

The label `ALL_GREEN` requires a complete block and all declared strict pairs
passing. A first passing pair may be shown only under a predeclared selection
rule; it is not independent evidence after the known v0.5.2 defect.

## Claim boundary

The successful network-zero artifact establishes only that this deterministic
typed public program can:

- preserve and reproduce the known legacy lineage failure;
- distinguish direct from inherited active evidence;
- express a separately labeled two-edge repair; and
- close the contaminated engineering regression under local validation.

It does not establish semantic extraction, autonomous graph discovery,
hidden-state editing, backward propagation through GPT, control-map causality,
generated-output improvement, fresh generalization, or improved reasoning
quality.

The next milestone is v0.5.4, which compiles this accepted factorized program
into a temporal recurrence and tests exact backward credit under matched
actuator controls. See
[the v0.5.3-v0.5.5 roadmap](ROADMAP_V0_5_3_TO_V0_5_5.md).
