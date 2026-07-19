# EBRT v0.5.0 Differentiable Evidence Control

## Status

v0.5.0 is a **mechanism-only** controller core over a synthetic, public,
typed semantic graph. It is intended to reconnect the differentiable mechanism
from early EBRT work with the full-context aperture direction without implying
that a hosted model exposes editable hidden state.

The graph topology, signed effects, affected claim, invalidation, and
replacement target are oracle-scripted public annotations. They are explicit
supervision, not autonomously discovered semantics. The downstream-leakage
audit described below prevents any separately supplied final-answer artifact,
provider output, or grader verdict from entering the controller boundary; it
does not turn this fixture into a learned adapter.

This milestone does not call a provider, regenerate a final answer, run a
canary, compare model outputs, or establish a reasoning improvement. The
internal lane identifier `controlled_raw_restart_once` is reserved for a later
integration milestone; it is not implemented or evaluated by v0.5.0.

## Execution and gradient boundaries

The intended end-to-end architecture is:

```text
raw public history
  -> semantic adapter
  -> frozen typed public dependency graph
       STOP-GRADIENT AT ADAPTER OUTPUT
  -> differentiable EBRT surrogate and bounded evidence gates
       backward() STOPS INSIDE THE LOCAL CONTROLLER
  -> deterministic public control-map projection
       NON-DIFFERENTIABLE JSON BOUNDARY
  -> controlled_raw_restart_once (reserved for later)
  -> hosted-model output (reserved for later)
```

Real autograd applies only to the local surrogate and its continuous gate
parameters. It does not differentiate through semantic extraction, JSON
serialization, a provider API, provider reasoning tokens, or the final natural
language generation. The later execution backend may consume the projected
control map, but it is not part of the gradient graph.

Accordingly, the precise claim is:

> EBRT optimizes bounded external evidence controls with local autograd over a
> frozen public semantic graph.

It is not accurate to say that EBRT differentiates through, fine-tunes, or
edits a hosted model.

## Public graph and intervention variable

Let each public dependency edge carry the fixture's signed effect
`a_ij`: positive for `supports` and negative for `contradicts`. Each evidence
node has one unconstrained parameter `u_i` and one bounded intervention gate:

\[
g_i = 2\sigma(u_i), \qquad 0 < g_i < 2.
\]

The neutral gate is `g_i = 1`. Roles are projections of this single degree of
freedom, not three independently optimized variables:

```text
g_i < 1 - delta       suppress
|g_i - 1| <= delta    preserve
g_i > 1 + delta       boost
```

For the minimal scalar surrogate, public claim activation is:

\[
q_j(g) = \tanh\!\left(\sum_i a_{ij} g_i\right),
\qquad q_j^0 = q_j(\mathbf 1).
\]

The dependency matrix is part of the frozen public artifact and is shared by
every future comparison arm. An affected claim receives gradient through its
incoming graph edges; an unrelated evidence node must not become an affected
node merely because its wording is similar.

## Exact loss roles

The local objective is:

\[
\mathcal L =
\lambda_{revision}\mathcal L_{revision}
+ \lambda_{support}\mathcal L_{support}
+ \lambda_{invalidation}\mathcal L_{invalidation}
+ \lambda_{drift}\mathcal L_{drift}
+ \lambda_{control}\mathcal L_{control}.
\]

Each term has one bounded role:

1. **Revision consistency**

   \[
   \mathcal L_{revision} =
   \frac{1}{|T|}\sum_{(j,t_j)\in T}(q_j(g)-t_j)^2.
   \]

   `T` is the public `revision_event.replacement_targets` set. This term sends
   terminal revision error backward through dependency edges into evidence
   gates.

2. **Active support preservation**

   \[
   \mathcal L_{support} =
   \frac{1}{|P|}\sum_{i\in P}\max(0,1-g_i)^2.
   \]

   `P` contains non-invalidated evidence with positive incoming effects to an
   affected claim. This term prevents the controller from solving a revision
   by indiscriminately deleting still-active public support.

3. **Invalidated evidence suppression**

   \[
   \mathcal L_{invalidation} =
   \frac{1}{|I|}\sum_{i\in I}g_i^2.
   \]

   `I` is the event's public `invalidated_evidence_ids` set. This term lowers
   the continuing contribution of explicitly revoked evidence.

4. **Unrelated-state drift**

   \[
   \mathcal L_{drift} =
   \frac{1}{|U|}\sum_{j\in U}(q_j(g)-q_j^0)^2.
   \]

   `U` is the set of claims whose `affected_by_event` value is false. It keeps
   stable and merely similar topics near their neutral pre-control state.

5. **Control regularization**

   \[
   \mathcal L_{control} =
   \sum_i(g_i-1)^2 = \|g-\mathbf 1\|_2^2.
   \]

   This term prefers small interventions and makes control magnitude visible.
   It is a sum rather than a graph-size mean, so adding neutral disconnected
   nodes does not dilute regularization on existing controls.

Empty typed sets contribute an exact zero rather than a division error.
Provider calls, output tokens, reasoning tokens, latency, and server errors are
not semantic loss terms. A later runtime may report them as constraints or
post-run diagnostics, but v0.5.0 does not optimize them.

## Five v0.5.0 requirements

1. **Typed dependency graph.** Validate unique IDs, ordinals, references,
   relation vocabulary, effect sign, target bounds, event references, and the
   explicit affected/unaffected claim partition. Freeze the graph before
   optimization.

2. **Bounded differentiable controller.** Initialize neutral scalar gates,
   optimize only local gate parameters, retain the five separately reported
   loss terms, and never treat boost/suppress/preserve as independent latent
   controls.

3. **Mechanism checks.** Require finite-difference agreement for the analytic
   gradient, exact neutral behavior for a non-triggered event, revision-only
   terminal-credit locality on the locked topology and its severed-edge
   ablation, and gate-bound checks throughout optimization. This is not a
   generic total-objective locality guarantee for every valid graph.

4. **Deterministic control projection.** Project gates in stable
   `(ordinal, evidence_id)` order, use a fixed role threshold and numeric
   precision, record before/after objective components, and require byte-stable
   output across identical runs. The JSON projection is a non-differentiable
   public artifact.

5. **No downstream-grader/final-answer artifact leakage and frozen-source
   audit.** The controller may consume only the public graph, revision event,
   declared loss policy, and deterministic run configuration. No separately
   supplied evaluation label, final-answer artifact, provider output, or
   downstream verdict may enter graph construction, loss construction,
   initialization, stopping, or projection. The oracle replacement target and
   signed dependencies are declared controller inputs, not an independent
   quality grade. Adapter provenance is frozen by hashing the canonical JSON
   object made from `schema_version`, `graph_id`,
   `evidence_nodes`, `claim_nodes`, `dependency_edges`, and `revision_event`,
   with UTF-8, `ensure_ascii=False`, sorted keys, compact separators, and the
   runtime's standard JSON float representation. `provenance` and
   `claim_boundary` are excluded from that semantic-payload hash. A separate
   policy lock pins the full fixture bytes so provenance and boundary metadata
   cannot change under the same semantic hash.

These requirements define mechanism integrity, not empirical model quality.

## Frozen mechanism policy

[`policy_lock_differentiable_evidence_controller_v0_5.json`](../policy_lock_differentiable_evidence_controller_v0_5.json)
pins the controller, both fixtures, numeric policy, projection contract, and
zero-network artifact surface. The locked run uses float64, deterministic Adam
with no RNG, 120 revision steps at learning rate `0.08`, and these loss
weights:

```text
revision_consistency          4.00
support_preservation          1.00
invalidation_suppression      1.50
stable_claim_drift            2.00
control_l2                    0.05
```

Every optimizer step projects `g - 1` to an L2 radius of at most `1.25` and
clamps gates to `(1e-12, 2 - 1e-12)`. The lowest finite projected objective is
retained; it is accepted only if it improves the neutral objective by more
than `1e-12`, otherwise the public result rolls back to exact neutral gates.

The central finite-difference check uses epsilon `1e-6` and absolute tolerance
`2e-8` for each of the five unweighted terms and the weighted total. Public
roles use delta `0.05`; floats are rounded to 12 decimal places and controls
are ordered by `(ordinal, evidence_id)` before canonical UTF-8 serialization.
The padding audit adds eight neutral edge-less nodes and requires every original
gate to remain within `1e-14`; the observed maximum error is recorded in the
self-test artifact. This audit is distinct from the narrower terminal-credit
locality check.

The lock separately pins full fixture bytes and semantic payloads:

| Fixture | Full-file SHA-256 | Semantic-payload SHA-256 |
| --- | --- | --- |
| Triggered DEV | `6d9fa014e41185cd227c58833055f1382027199e3a6937812022b60c32eea0da` | `6c1b88ae49afb2102a7a98f3a17c1a0412ac627c43c9dbe1aad462231cc6b796` |
| No-event identity | `195b84b21bd0d620b8a2c0bc79dfb7ce16758734b4d4d1fe0f299487129ee497` | `cc757cda1c8403cbcd55ae2ca460e91a22d22b5031f4a246867b293dd6b868ad` |

The controller source SHA-256 is
`960dd29b90a319c032019ff0724d65134bf8f3baa294d9088823dce91cfe0e31`.
The v0.1 source and v0.4.1 manifest hashes are retained only as historical
lineage references; neither is an input to optimization.

The committed manifest records the exact Python, PyTorch, operating-system,
and machine runtime used to generate its floating-point bytes. Two-build byte
identity is a same-runtime result; cross-runtime numerical identity is not
claimed.

## Mechanism result

The built-in contract graph is numerically isomorphic to the locked triggered
fixture but has a distinct provenance payload. On that built-in graph:

- all five loss components and the weighted total matched central finite
  differences with maximum absolute error `2.4067525750126606e-10`, below the
  locked `2e-8` tolerance;
- revision-only terminal credit routed R2, R4, and R6 toward boost and R3 toward
  suppression, while R1, R5, and R7 had exact zero first gradient;
- severing the R4-to-bay edge made R4 terminal credit exactly zero;
- adding eight disconnected neutral nodes changed any original final gate by
  at most `2.220446049250313e-16`, below `1e-14`;
- two same-runtime runs emitted byte-identical canonical control maps.

The independently pinned triggered fixture then produced an accepted control:

| Evidence | Role | Gate |
| --- | --- | ---: |
| R1 | preserve | 1.000000000000 |
| R2 | boost | 1.087271107256 |
| R3 | suppress | 0.102212897239 |
| R4 | preserve | 1.020493960458 |
| R5 | preserve | 1.000000000000 |
| R6 | boost | 1.097417240667 |
| R7 | preserve | 1.000000000000 |

Its weighted surrogate objective fell from `1.610683159073` to
`0.059315805950` over 120 backward calls. The separately pinned no-event
fixture emitted exact neutral controls, unchanged public activations and
objective, and zero backward calls. The artifact builder denied socket creation
throughout materialization and reports `network_calls=0`.

These are mechanism checks, not model-output comparisons. In particular, the
finite-difference, terminal-credit, severed-edge, and padding tests belong to
the built-in graph; the external fixture separately validates the locked input,
accepted objective decrease, bounded public map, and deterministic artifact
pipeline.

## DEV fixture topology

`fixtures/differentiable_evidence_controller_v0_5_dev.json` deliberately
contains one small but nontrivial topology:

- R2 and R6 positively support the affected bay claim;
- invalidated R3 negatively affects that claim;
- R4 is weak positive context rather than a dominant answer carrier;
- R5 supports a stable cargo claim;
- R7 supports a semantically similar but unrelated shipment claim;
- R1 has no edge to the affected claim.

The event targets only the bay claim. This gives the controller a path for real
revision gradients while preserving stable and lexical-distractor checks. The
fixture contains public oracle supervision, but no separately supplied final
answer, provider output, or downstream evaluation outcome. Locality on this
fixture means
**disconnected-node locality on the frozen public graph**; it does not show that
the controller itself discovered R7 to be unrelated.

The graph is one hop: `evidence gate -> terminal claim`. v0.5.0 therefore
tests direct incoming-edge credit assignment, not multi-hop dependency
propagation, a recurrent reasoning trajectory, or backward replay.

## Historical boundary

The v0.1 mechanism optimizes vector controls inside a frozen toy recurrent
generator and replays a suffix. v0.5.0 instead optimizes scalar gates on a
static public graph; it is not an equivalent reimplementation of the v0.1
state transition.

The v0.4.1 `staged_cumulative_raw` arm retained a growing raw prefix across six
provider calls. The reserved `controlled_raw_restart_once` lane would perform
one stateless generation from all raw history. These geometries are different.
The v0.4.1 run was incomplete and its locked causal gate remained false;
retention, repeated-call dynamics, prompt commitment, and per-call allocation
were bundled in the observed intervention. v0.5.0 uses that result only to
nominate full-context regeneration as a future integration candidate.

## Claim boundary and deferred work

v0.5.0 can support claims about graph validation, local autograd, numerical
gradient agreement, bounded gates, locked-topology terminal-credit locality,
locked no-event identity, eight-node disconnected-padding invariance, and
deterministic projection when the corresponding checks pass.

It cannot support claims about:

- hosted-model reasoning improvement;
- correctness or usefulness of a regenerated answer;
- causal benefit over a textual envelope or matched random controls;
- provider efficiency, latency, or token use;
- private reasoning, hidden-state access, or editable provider internals;
- production readiness.

A future integration may implement `controlled_raw_restart_once`, freeze one
shared semantic artifact across matched arms, and only then define a canary.
That canary and any larger benchmark are explicitly outside v0.5.0.
