# EBRT v0.6+ — Execution, Evaluation, and Orchestration Roadmap

Status: **v0.6.0 PREFLIGHT PASS; v0.6.1 FIVE-CALL BLOCK COMPLETE, GATE HELD; v0.6.2.1 APPLY-REVISION LIVE R01 PRODUCT ACCEPTANCE PASS, EFFECT NOT ASSESSED; v0.6.2.2 CURRENT TYPED INVALIDATION-REVISION MONOLITH, SEMANTIC QUALITY AND EFFECT NOT ASSESSED; v0.6.3 LIVE R01 EXECUTED ONCE, STOP_OUTPUT_CONTRACT; v0.6.3.1 LIVE R01 COMPLETE, PROMOTE TO FRESH REPLICATION; v0.6.3.2 LIVE R01 COMPLETE, D/C REPEATED, X/Z CEILING STOP; v0.6.4 BLOCKED; REASONING IDE CONVERGENCE IN PROGRESS**

The one allowed v0.6.1 block ran on 2026-07-20 in the preregistered order
`P -> A -> B -> D -> C`. All five calls completed and the committed artifact
validated, but the decision is `HOLD_V0_6_HOSTED_BUNDLE_GATE`: D passed the
strict hosted endpoint, while P failed its exact pre-event lineage contract and
the primary matched D-vs-C effect was `NULL`. The result is frozen rather than
repaired or rerun in this namespace.

This roadmap is derived only after the completed v0.5.3-v0.5.5 substrate
sequence:

```text
v0.5.3  dependency space       typed public lineage
v0.5.4  trajectory time        exact temporal credit
v0.5.5  trajectory multiplicity sealed lane composition
v0.6+   hosted execution       real outputs over the frozen substrate
```

The v0.5.5 decision is `PROMOTE_V0_6_LANE_COMPOSITION_GATE`. It proves that
one contaminated network-zero public bundle can be composed and audited. It
does not prove that its lanes are agents, that the merge improves an answer,
or that multiple models should be orchestrated.

## Origin anchor

EBRT's originating thesis remains:

> Treat reasoning as an editable trajectory rather than an irreversible token
> stream. When later evidence changes an earlier premise, send a bounded
> backward signal to the affected public trajectory before final generation.

Hosted models do not expose an editable differentiable hidden trajectory.
Therefore the reachable implementation remains layered:

```text
raw evidence history
  -> hosted semantic projection             non-differentiable
  -> typed public trajectory / lane bundle  sealed artifact boundary
  -> local differentiable control           real public backward pass
  -> allowlisted control projection          non-differentiable
  -> one full-context regeneration           hosted execution backend
  -> output and lineage grading              independent endpoint
```

No v0.6 result may be described as backpropagation through GPT. Full-context
regeneration is an execution backend, not EBRT's differentiable core.

## Evidence that constrains the next design

The next experiment must preserve all of these observed boundaries:

1. The v0.4.1 aperture result strongly favored cumulative raw context over a
   card-only staged restart on its contaminated DEV block. Every quality arm
   therefore receives the same full raw evidence history.
2. The v0.5.1 recovery block showed that a large local surrogate decrease can
   coexist with byte-identical hosted outputs. Surrogate success and generated
   output success remain separate fields and separate claims.
3. The v0.5.2 walkthrough produced a useful output change but failed one
   fact-local lineage contract. Answer correctness and lineage correctness
   remain separate endpoints.
4. v0.5.3 repaired a known representation defect under explicit contamination;
   it did not discover semantics from raw language.
5. v0.5.4 established exact time-local public credit on one supplied program;
   it did not establish hosted-model improvement.
6. v0.5.5 established deterministic lane composition and block credit; its
   lanes were schedule views of one public program, not independent agents.
7. v0.6.1 showed that a complete answer-adjacent public DAG can saturate the
   tested provider surface: B, D, and C returned byte-identical outputs.
8. v0.6.3-live-r01 stopped after one completed call because a freely emitted
   graph missed the exact-one-closure contract. It did not measure X/Z channel
   propagation or D/C placement and is not a null actuator result.

These findings make another network-zero mechanism extension lower priority
than a clean return to actual hosted output.

## Immediate critical path

The completed bridge path is v0.6.0 -> v0.6.1, with v0.6.2 preserving it as
a judge-readable product surface. The next algorithmic path is deliberately
separate:

```text
v0.6.3    preserve the consumed r01 output-contract stop
v0.6.3.1  repair the uptake measurement with one discrete public action
live-r01   execute exactly C -> X -> D -> Z under a separate merged lock/tag
           ↓ a favorable four-call canary opens only fresh replication
v0.6.3.2  test the same actuator on one new sealed case in mirrored blocks
           A: C -> Z -> D -> X; B: D -> X -> C -> Z
           ↓ D/C repeated, but required X/Z contrast hit ceiling; gate stopped
v0.6.4    remains future research; no current preflight or live path is opened
product   preserve immutable v0.6.2.1 acceptance; expose the promoted operation
lane      as the separate typed v0.6.2.2 live monolith
           ↓
v0.7    ask the first fresh matched quality question
```

Each step keeps a distinct acceptance decision so that provider completion,
channel adherence, downstream propagation, quality, and UI readiness cannot be
collapsed into one red or green badge. A non-null result is a promotion gate,
not an outcome to manufacture by weakening contracts or selecting a favorable
post-hoc diff.

## v0.6.0 — Provider-Safe Bundle Projection

### Question

Can the exact v0.5.5 sealed bundle be deterministically projected into a
provider-safe public revision program without changing its lane geometry,
receipts, bounds, or stop-gradient boundary?

### Minimum protocol

- use a new v0.6 namespace and keep the frozen v0.5.2 near-pass unchanged;
- pin the v0.5.5 source, manifest, shared ledger, three copied lane bytes,
  junction, lane controls, merge slack, and block-adjoint receipts;
- project only allowlisted public Evidence, Support, Fact, Constraint,
  invalidation, and bounded-control fields;
- give the provider the ordered cumulative R1-R6 raw history separately from
  the public revision program;
- blind treatment labels and make C/D payloads match in row set, value/sign
  multiset, sparsity, lane norm, merge norm, and schema; and
- freeze prompt, output schema, model snapshot, effort, ceiling, timeout,
  no-retry policy, and call order before the first provider response.

### Gates

- exact v0.5.5 source, lane, graph, control-map, and manifest rederivation;
- deterministic projection bytes across two builds under socket denial;
- same ordered raw R1-R6 bytes for every post-event arm;
- exact independent verification of the C/D matched geometry;
- no separately loaded grader/gold artifact, grade, arm label, or downstream
  result in provider input; B/C/D explicitly receive the contaminated,
  case-specific oracle lineage program whose answer-adjacent edges are part of
  the intervention rather than independently discovered support;
- output schema capable of Evidence -> Support -> Fact/Constraint lineage; and
- source, payload, namespace, and coherent re-sign tampering rejected before a
  live call is allowed.

Passing v0.6.0 establishes only a safe deterministic projection and launch
gate. It makes zero provider calls and establishes no generated-output effect.

## v0.6.1 — Controlled Full-Context Regeneration

### Question

Can the exact sealed v0.5.5 bundle be consumed by one GPT-5.6 full-context
regeneration, producing an actual revised answer with complete fact-level
lineage?

### Canary arms

Use the known R1-R6 hackathon-strategy case and label the entire block
contaminated. This is an engineering regression over a known defect, not fresh
reasoning evidence. All post-event arms receive byte-identical cumulative raw
evidence, the same output schema, one final provider call, and matched settings:

| Arm | Final-call intervention | Purpose |
| --- | --- | --- |
| P | R1-R5 pre-event reference | product Before; excluded from causal contrasts |
| A | no revision control | raw full-context restart |
| B | typed event/DAG envelope with zero controls | simple non-gradient control |
| C | norm-, sparsity-, sign-, lane-budget-, and merge-budget-matched sham placement | control-map geometry without EBRT placement |
| D | exact composed EBRT public control map | tested placement |

The hosted model is not differentiated. C and D differ only in allowlisted
public control placement; provider-visible treatment labels are blinded. Any
one attempt is allowed per arm, with no retry and a predeclared order. The
v0.5.5 lanes are already sealed inputs; this block does not relabel them as
independent executions or agents.

### Endpoints

Record these independently:

```text
run_status                 COMPLETE | DEGRADED | INCOMPLETE
answer_status              PASS | FAIL | NOT_ASSESSED
fact_local_lineage_status  PASS | FAIL | NOT_ASSESSED
invalidation_status        PASS | FAIL | NOT_ASSESSED
stable_fact_status         PASS | FAIL | NOT_ASSESSED
surrogate_status           PASS | FAIL
effect_status              POSITIVE | NULL | NEGATIVE | NOT_ASSESSED
```

The strict semantic endpoint requires P to pass its R1-R5 contract and remain
stale under R1-R6, plus D to change `POLISH -> PROVE`, remove and invalidate R3,
preserve R5 / `THREE_MINUTE_NARRATED`, and close exact direct/inherited/total
fact-local support. More generally it requires the exact decision, required fact-local
support, absence of active invalidated support, and preservation of unrelated
stable facts. Calls, input/output/reasoning tokens, latency, and provider errors
are receipts or budget constraints, not direct semantic-loss terms.

### Stop rule

Freeze every fixture, gold file, projection, and runtime field before the first
live response. A preflight failure makes zero calls. A provider failure freezes
the block `INCOMPLETE`; missing cells are not filled later. A D strict failure
is preserved and repaired only in a successor namespace. If D is identical to
A/B/C, record `NULL`; if it is worse, record `NEGATIVE`. Do not tune the known
case after observing the output. A null effect does not invalidate v0.5.5, and
a surrogate decrease does not rescue a failed final endpoint.

The first critical experiment is this contaminated five-call v0.6.1 block. It connects the completed
substrate to the missing product endpoint: a real regenerated answer. It also
directly tests the failure exposed by v0.5.1, where strong local movement had no
observable output effect.

Promotion means the bundle-to-output bridge and strict D path completed; it
does not require D to beat A/B/C. Arm differences remain separately labeled
observations. The exact promotion status is reserved as
`PROMOTE_V0_7_HOSTED_BUNDLE_GATE`.

### Locked v0.6.1 result

The policy lock fingerprint is
`51bd00343dafb4dd9bc0c42dc95c1df1b6f8b7132907e283d84a82b237801072`.
The validated result fingerprint is
`a814b54a23faef07e301aa676411789cfb62154c07e5ad373f779ed67621954b`.

| Arm | Answer | Strict grade | Observation |
| --- | --- | --- | --- |
| P | `POLISH` | FAIL | correct answer, but R2 was unexpectedly inherited into `demo_centerpiece` |
| A | `PROVE` | FAIL | correct answer, invalidation, and stable fact; R4 was missing from `final_priority` |
| B | `PROVE` | PASS | the supplied typed DAG closed the exact lineage contract with zero controls |
| D | `PROVE` | PASS | exact v0.5.5 control placement closed the same strict contract |
| C | `PROVE` | PASS | matched sham placement produced the same public output as D |

B, D, and C produced byte-identical public outputs. Therefore the primary
matched comparison is `D_vs_C = NULL`; D is also null against B and positive
only against raw arm A at the strict endpoint. The block consumed exactly five
API calls and 38,767 provider tokens, including 466 reasoning tokens. These are
one contaminated, unbalanced, time-confounded observations, not a causal or
population estimate.

This result separates three facts that must not be collapsed:

1. the full sealed substrate-to-provider-to-output bridge exists and D can
   produce a strict passing final lineage;
2. supplying the case-specific typed DAG was sufficient for B, C, and D to
   converge to the same passing public program; and
3. signed-displacement placement had no observable output effect in this
   protocol, whose prompt already required exact DAG instantiation.

The last point nominates control-channel sensitivity, rather than another
same-case rerun, as the next algorithmic bottleneck. The detailed result and
nonclaims are recorded in
[RND_HOSTED_BUNDLE_V0_6_1.md](RND_HOSTED_BUNDLE_V0_6_1.md).

## v0.6.2 — Reasoning IDE Acceptance

v0.6.2 turns the sealed execution artifacts into a provisional developer
workflow. It does not freeze the final frontend design.

The primary view is:

```text
Evidence -> Revision Event -> Lane Credit -> Public Control -> Regeneration
    |                                                   |
    +---------------- Before / After Output Diff -------+
                                                        |
                                      Strict Lineage Diagnostic
```

The product acceptance set contains two immutable demonstrations:

1. **Clean path:** an independently sealed end-to-end artifact whose hosted
   answer and strict fact-local lineage both pass.
2. **Hidden-defect path:** the preserved v0.5.2-style case where the answer
   looks corrected but the Inspector exposes incomplete fact-local support.

The hero surface shows actual Before and After output, output diff, the public
control map, answer grade, lineage grade, calls, tokens, and latency. Surrogate
loss is visibly separate from actual-output status. Raw receipts, schema,
fingerprints, and claim boundaries remain available in an Inspect layer.

The three-minute story is:

```text
an answer becomes stale
  -> local autograd emits a bounded public-control receipt
  -> full-context regeneration produces a changed final output
     (v0.6.1 placement attribution remains NULL)
  -> the IDE verifies whether the new answer is actually supported
```

Demo readiness requires deterministic artifact playback, one real hosted
regeneration artifact, a visible final-output diff, strict diagnostic
separation, and an audited spoken claim ledger. It does not require a positive
general-accuracy claim.

### v0.6.2.1 — Apply Revision Acceptance

The promoted product path is now one single-lane monolith, `ebrt.py`:

```text
actual hosted Before
  -> factorized public state
  -> actual-Before-conditioned local backward()
  -> bounded public control map
  -> Reinspect / Suppress / Preserve actuator
  -> one dependent full-context regeneration
  -> strict output, lineage, invalidation, and stable-fact verification
```

This namespace asks for product integration acceptance, not another matched
effect experiment. It inherits the known contaminated R1-R6 walkthrough,
presents multiple opaque closure candidates without provider-visible gold,
and loads semantic gold only after two structurally valid terminals. The
dynamic Call-2 bytes are durably sealed only after the actual Call-1 output has
been normalized and used by the public surrogate.

The network-zero self-test requires an all-green scripted acceptance, exact
six-event journal, no-network execution, post-call gold barrier, dynamic
payload binding, artifact round-trip, and coherent tamper rejection. Live use
requires a separately merged policy lock and the exact annotated authorization
tag, then consumes at most two no-retry attempts in one namespace. Regardless
of the product endpoint, `effect_attribution_status` remains `NOT_ASSESSED`.

Live r01 has now consumed that authorization exactly once. Both provider calls
completed; the actual `POLISH` Before passed its own horizon and became stale
after R6; one local backward pass compiled `R6 -> R4 -> R2`, suppress R3, and
preserve R5; and the full-context After returned `PROVE` with strict answer,
invalidation, stable-fact, and fact-local lineage PASS. The terminal is
`ACCEPT_APPLY_REVISION_PATH`, while effect attribution remains deliberately
`NOT_ASSESSED`. The result is frozen under
`artifacts/apply_revision_acceptance_v0_6_2_1_live_r01/` and documented in
`RND_APPLY_REVISION_ACCEPTANCE_V0_6_2_1_LIVE_R01.md`.

### v0.6.2.2 — Typed Live Apply Revision Runtime

The current product runtime is the separate monolith `ebrt_live.py`. It leaves
root `ebrt.py`, the v0.6.2.1 policy surface, and the canonical acceptance
artifact immutable. Instead of rerunning the sealed two-call block, it accepts
one typed public invalidation-revision operation: full case and evidence, an
already emitted Before output with its selected closure graph, a typed late event, and at least
two structurally distinct After closure candidates.

For each new request identity the runtime validates those public structures,
runs one local float64 backward pass to rank reinspection salience, and combines
that ranking with typed-event `Suppress / Preserve` operations. Candidate IDs
are server-remapped to opaque graph hashes before exactly one After provider
attempt. The provider never receives gradient values, losses, salience values,
credentials, reserved gold fields, or caller candidate labels. SDK and
application retries remain disabled; request identity terminally binds both
successful and failed attempts rather than allowing a second provider call.

The live response keeps three axes distinct:

```text
mechanism     local backward, control-map, and actuator contract
output        actual typed Before, After, and public diff
verification  operational and lineage checks only
```

An operational `PASS` does not grade semantic answer quality and does not
attribute an output change to EBRT. Both `semantic_correctness_status` and
`effect_attribution_status` remain `NOT_ASSESSED`. The scripted provider is an
offline plumbing mode; the server-owned demo request adapts the contaminated
v0.6.2.1 case, is fingerprint-classified server-side, and is not a benchmark.
Reserved gold fields are rejected, but caller semantic content remains
unverified. The initial HTTP surface is loopback-only:
`GET /api/health`, `GET /api/capabilities`, `GET /api/demo-request`, and
`POST /api/apply-revision`. Provider credentials stay in the server environment.

This milestone closes the product-monolith convergence item. It does not open
v0.6.4, answer the fresh matched-quality question reserved for v0.7, or convert
the historical demo into independent evidence.

## v0.6.3 — Provider Actuator Calibration Canary

The monolithic network-zero implementation now records `PASS_NETWORK_ZERO`
with 21/21 hard gates and a canonical
`READY_ZERO_CALL_PREFLIGHT_ONLY` artifact. It seals 16 future payloads while
making zero network/provider calls; no hosted execution is authorized or
observed in this namespace.

v0.6.1 showed that the supplied typed DAG reached GPT but did not show that
continuous control placement did: B, D, and C were byte-identical, while their
total token cost was roughly 6.4-6.6 times raw A. That result cannot distinguish
an inert provider channel from a weak or misplaced gradient signal. Before a
quality study, run a fresh calibration asking only:

> With full raw context, a neutral candidate scaffold, schema, and budget held
> fixed, does one bounded public actuator produce a directionally attributable
> change in a hosted model's inspection plan and non-echo downstream state?

Use one operator only: a `bounded_reinspection_schedule`. Every arm contains
every evidence ID exactly once, the raw evidence remains in the same order, and
the operator changes only public priority tiers under one review budget.
Continuous displacement is compiled into that concrete operation before the
provider boundary; uninterpreted floats are not sent as if they were an
execution semantics. A zero treatment is encoded as tied priorities plus
`no_reordering=true`, not mislabeled canonical positional priority.

The minimum matched arms are:

| Arm | Placement | Purpose |
| --- | --- | --- |
| Z | all priorities tied; `no_reordering=true` | no-actuation reference in the same envelope |
| C | frozen anti-placement derangement matched to D in rank multiset, size, and budget | construct-aligned anti-control |
| D | gradient-derived schedule | tested EBRT placement |
| X | preregistered truth-neutral opposed schedule | positive channel control |

X is mandatory. If D and C match without X, an inert channel and a weak or
incorrect gradient placement remain observationally indistinguishable. Each
canary contains two preregistered, equally valid support paths. X promotes one
path using the immediate predecessor branch head plus an opaque case-ID rule.
The runtime rule does not read the answer value, the EBRT gradient, or provider
output, but the cases/controller were designed later, so broader study-design
selection independence is not claimed. The rule intentionally uses the private
equivalence class containing those two paths and must not be described as
gold-free. Both paths imply the same valid
answer, and neither path is privileged as more correct. The frozen case rule
selects opposite path members across the two cases. X validates channel wiring
only and is excluded from quality comparisons.

The provider-visible scaffold contains neutral node IDs/types, allowed relation
types, and a symmetric candidate-edge universe. It does not contain accepted
edges, expected closure, expected answers, answer-adjacent semantic role names,
or gold support sets. The deterministic local DAG remains the audit substrate,
but exact topology is diagnostic rather than the unique downstream truth.
Uptake grading uses necessary-support closure, invalidation absence, and stable
preservation fields that admit both preregistered valid support paths. Write the
paths as `P0 = K union A0` and `P1 = K union A1`, where `K` is common support and
the disjoint alternative sets `A0` and `A1` have equal cardinality. A scored
active closure must equal exactly P0 or P1; a union, partial path, or mixed path
is a contract failure rather than extra alignment credit. Closure is rederived
locally from the selected candidate-edge graph and is never accepted from an
output-declared closure field.

Record three endpoints separately:

```text
channel_adherence       did the public inspection plan consume the schedule?
downstream_propagation  did non-echo decision state move in its direction?
quality_status          did the answer/lineage improve? (secondary only)
```

Raw byte inequality and a verbatim schedule echo are not downstream uptake.
Before any call, freeze a signed controller polarity `q_i^D` and an independent
opaque-rule positive-control polarity `q_i^X` per evidence ID. Center each
polarity over the path-discriminating eligible IDs and normalize it to unit L1
norm; common, invalidated, and stable-only IDs receive zero score. A nonfinite or
zero-norm `q^D`, or tied P0/P1 aggregate under `q^D`, is a zero-call preflight
stop. Freeze the exact non-echo score

```text
alignment(output, q) = sum(q_i for i in active necessary-support closure)
delta_XZ = alignment(X, q^X) - alignment(Z, q^X)
delta_DC = alignment(D, q^D) - alignment(C, q^D)
```

Invalidated and stable-only IDs are excluded from this score and remain separate
strict endpoints. Score parsed typed fields only, never free-text rationale or
the `inspection_plan` receipt. C must preserve D's rank/tier multiset, size, and
budget while having no eligible fixed point, different provider bytes after
projection, and strictly lower frozen input alignment under `q^D`.

Use two fresh cases x two fixed trials x four arms (16 calls), no retry, and the
following complete Williams mapping:

```text
case_1 / trial_1: Z C X D
case_2 / trial_1: C D Z X
case_1 / trial_2: D X C Z
case_2 / trial_2: X Z D C
```

This balances position and first-order carryover over the whole block, not
within either case. Evaluate X-versus-Z under `q^X` and D-versus-C under `q^D`.
Each gate requires positive aggregate paired alignment and the expected sign in
at least three of four complete blocks. Any incomplete block makes the effect
gates `NOT_ASSESSED`. Freeze both polarities, rank distance, derangement,
parser, numeric tolerance, and all 16 provider payloads before launch.

The network-zero conformance outputs exercise both exact path coordinates and
alignment arithmetic only. They do not instantiate hosted Z/C/D/X effects, and
no synthetic X-versus-Z or D-versus-C delta is a hard gate.

The D schedule and the D endpoint deliberately share `q^D`; this is a
construct-aligned actuator calibration against a matched anti-placement
control, not independent validation or evidence
of reasoning quality. The terminal statuses are exact:

```text
ZERO_CALL_PREFLIGHT_STOP          a network-zero hard gate failed
INCOMPLETE_NOT_ASSESSED           a call, receipt, parser, or block failed
STOP_OUTPUT_CONTRACT              exact-one closure, invalidation, or stable preservation failed
STOP_CHANNEL_ADHERENCE_NULL       X did not consume its schedule
STOP_ACTUATOR_ECHO_ONLY           X echoed the schedule without non-echo propagation
STOP_GRADIENT_PLACEMENT_NULL      X propagated but D did not exceed C directionally
PROMOTE_V0_6_4_ACTUATOR_GATE      every frozen gate passed
```

This is a feasibility canary, not a population estimate or quality win. Do not
tune or rerun the completed v0.6.1 case, relax lineage contracts, or search many
unreported prompt channels to rescue a null result.

The live r01 runner and its separate 16-call authorization lock now freeze the
existing Williams order, exact payload hashes, one-shot provider boundary,
durable pre-call journal, `epsilon=1e-12`, all-four X adherence, all-eight D/C
adherence, endpoint thresholds, and terminal decisions. The live revision also
requires all-four Z baseline adherence, an annotated execution-commit tag, and
a locked-code semantic-gold loader guard through complete public compilation.
The zero-call monolith, policy, and canonical preflight artifact remain
unchanged.

The r01 namespace executed once after the authorization tag was published. Its
first provider call completed, but the unchanged local compiler rejected the
public graph with `EXACT_ONE_CLOSURE_FAILED`. The frozen terminal state is
`STOP_OUTPUT_CONTRACT`: 15 calls were not attempted, gold and secondary quality
remained unloaded/not assessed, and neither X/Z propagation nor D/C placement
was evaluated. Do not rerun or reinterpret this as a null actuator effect. See
the frozen
[`preregistration`](RND_ACTUATOR_CALIBRATION_V0_6_3_LIVE_R01.md) and
[`terminal result`](RND_ACTUATOR_CALIBRATION_V0_6_3_LIVE_R01_RESULT.md).
The receipts are operator-attested rather than provider-signed or
cryptographically authenticated; the tag neither authenticates operator
identity nor guarantees cross-clone exactly-once execution.

## v0.6.3.1 — Observable Actuator Uptake Canary

v0.6.3.1 is a new zero-call measurement-repair namespace, not a repair or
rerun of the frozen r01 artifact. It narrows the provider-visible intervention
to one `evidence_permutation` and the primary public action to one known opaque
`selected_closure_id`. The deterministic DAG remains downstream as an
expansion and audit substrate; the provider no longer freely generates the
edge set used to decide whether uptake was observed.

Freeze one new synthetic case and four payloads:

| Arm | Frozen order | Purpose |
| --- | --- | --- |
| Z | neutral | positional reference |
| X | correction first | positive channel control |
| C | opposed path block first | geometry-matched anti-placement |
| D | local-backward-preferred path block first | tested EBRT placement |

Every arm contains the same immutable evidence-chunk byte multiset, candidate
catalog and order, instructions, schema, model settings, and budgets. After
normalizing evidence rows by ID, the payloads must be byte-identical. D is
compiled from one real local float64 backward pass; C matches D in Spearman
footrule distance, Kendall distance, fixed points, and protected anchor
positions while having lower frozen positional alignment. The gradient stops
before JSON and the hosted model is not differentiated.

Known stale, mixed, or incomplete closure IDs are valid semantic observations.
They are deterministically expanded and graded after parsing rather than
causing an output-contract stop. Malformed JSON, schema drift, an unknown
closure ID, or a provider/receipt failure remains structural and makes the
four-call block `INCOMPLETE_NOT_ASSESSED`. Thus the measurement boundary is
repaired without relaxing answer, invalidation, stable-fact, or lineage
diagnostics.

The primary canary gate is directionally preregistered:

```text
X moves from non-target Z to the aligned closure
and
D selects the aligned closure while matched C does not
  -> PROMOTE_TO_FRESH_REPLICATION
```

Ceilings, equality, off-target movement, and adverse movement have separate
non-promotional terminal statuses. Raw byte inequality, reviewed-evidence
echo, local surrogate decrease, and a quality-valid answer are not substitutes
for the selected-closure contrast.

The preflight monolith authorizes zero provider calls and publishes no hosted
result. Its separately reviewed live-r01 successor froze exactly one call per
arm in `C -> X -> D -> Z` order, with no retry, reorder, resume, or backfill.
It was anchored to annotated tag `v0.6.3.1-preflight`, peeled to commit
`c5e1244055e5d7f83493698119549c49df718ed7`. Live execution was forbidden until
the authorization pull request merged and annotated tag
`v0.6.3.1-live-r01-authorized` pointed exactly at that merge commit.

Known stale or mixed closures remain valid semantic endpoints. A structurally
invalid arm is recorded and the remaining presealed arms continue, but the
block ends `INCOMPLETE_NOT_ASSESSED` without loading gold. A source, lock,
payload, journal, receipt, filesystem, or process-integrity failure instead
stops the sequence and burns the attempt. Gold may load only after all four
arms have valid compiled terminals. The protocol required the hosted result and
its independent verifier to enter through a later result pull request, never
the authorization commit.

That authorization tag was created at object
`621d6ce5aca04629eefd1f0189635ee84b62e8da`, peeled to commit
`35b84895acb63298a8459dba1e9f3f2a47f4de0f`, and the exact block was consumed
once. All four calls completed and produced eight durable attempt-journal rows.
C selected the alternative closure, X and D selected the aligned closure, and Z
selected the mixed closure. The locked classifier returned
`CHANNEL_OPEN_DIRECTIONAL`, `GRADIENT_PLACEMENT_DIRECTIONAL`, and terminal
`PROMOTE_TO_FRESH_REPLICATION`. Semantic gold loaded exactly once after the
complete valid block. The result fingerprint is
`131d64dfe74b99912d5e39b0fdd13d17c69eca0d1361b27a48e75887ec25b8e2`.

This is a one-case, one-block directional observation. Although evidence order
was the sole intentionally treatment-varying semantic payload field, fixed
serial order cannot separate treatment from temporal or provider drift. The
result establishes neither quality improvement nor causal, population,
hidden-state, or general reasoning claims.

This favorable four-call result opens only a separately sealed fresh
replication. It does not directly promote v0.6.4 or establish quality,
causality, population reliability, hidden-state editing, or general reasoning
improvement. See the
[`v0.6.3.1 measurement-repair note`](RND_ACTUATOR_UPTAKE_CANARY_V0_6_3_1.md).
The live authorization boundary is detailed in
[`v0.6.3.1-live-r01 protocol`](RND_ACTUATOR_UPTAKE_CANARY_V0_6_3_1_LIVE_R01.md).
The consumed block is documented in the
[`v0.6.3.1-live-r01 result`](RND_ACTUATOR_UPTAKE_CANARY_V0_6_3_1_LIVE_R01_RESULT.md),
with its
[`canonical artifact`](../artifacts/actuator_uptake_canary_v0_6_3_1_live_r01)
and
[`portable verifier`](../verify_actuator_uptake_canary_v0_6_3_1_live_r01.py).

## v0.6.3.2 — Mirrored Fresh Actuator Replication

The network-zero preflight now freezes one synthetic case that is fresh
relative to the frozen v0.6.3.1 predecessor, not an independently sampled
population case, and exactly four provider payload byte strings. Those same
bytes are referenced in two pairwise serial-position-counterbalanced blocks:

```text
Block A: C -> Z -> D -> X
Block B: D -> X -> C -> Z
```

C and D each occupy positions `{1, 3}` with reversed order; Z and X each
occupy `{2, 4}` with reversed order. Block, attempt, arm, gradient, gold, and
expected-result metadata remain outside the provider payload. The only primary
public action is the opaque `selected_closure_id`. The mandated first-three
`reviewed_evidence_ids` echo is secondary and excluded from endpoint grading
and every promotion decision.

Each block must independently satisfy both frozen directional contrasts:

```text
X = aligned and Z != aligned
D = aligned and C != aligned
```

Only two directional blocks yield
`REPLICATION_DIRECTIONAL_COUNTERBALANCED`. One directional block yields
`STOP_REPLICATION_MIXED`; any structural-invalid attempt yields
`INCOMPLETE_NOT_ASSESSED`. There is no pooling, retry, backfill, tie-break,
third block, alternate case, or ninth call.

The producer and a pure-stdlib verifier freeze 26 hard gates, all 256 per-block
closure combinations, all 65,536 two-block closure combinations, the exact
four-payload/eight-attempt reuse geometry, the predecessor promotion receipt,
and zero provider/network calls. A separate reviewed live runner and exact
authorization tag are still required.

Even a positive live result would support only that one public evidence-order
contrast repeated on one fresh sealed case under pairwise serial-position
counterbalancing. It would not establish evidence-order causality, quality
improvement, population reliability, hidden-state/attention/KV editing, or a
v0.6.4 live launch. This is the final actuator-replication block before the
project returns to the Reasoning IDE and submission surface.

The separate
[`v0.6.3.2-live-r01 authorization protocol`](RND_ACTUATOR_UPTAKE_REPLICATION_V0_6_3_2_LIVE_R01.md)
freezes the exact eight-call runner, delayed-gold barrier, unique attempt-key
contract, and annotated-tag gate. The tag was published and the exact block was
consumed once. Both blocks selected the aligned closure for D and the
alternative event-consistent closure for C, producing
`REPLICATED_DIRECTIONAL`. Both also selected aligned for X and Z, producing
`REPLICATED_CEILING`; the locked terminal is
`STOP_REPLICATION_CEILING_NOT_ASSESSED`, and v0.6.4 was not opened.

The result is not a null D-versus-C observation, but the strict aggregate gate
cannot discard its required positive contrast after seeing a favorable
placement contrast. The complete geometry was `D = Z = X`, with only C on the
alternative closure, so D was not shown to move beyond neutral and C
anti-placement sensitivity remains an equally compatible account. Both
closures are independently quality-valid and all arms returned `JADE`, so the
result establishes no quality advantage. The frozen
stop rule forbids a third block, alternate seed, replacement case, relaxed
gold, rescue call, or ninth call. The current submission therefore closes this
research branch and returns to Reasoning IDE product convergence. See the
[`live-r01 result`](RND_ACTUATOR_UPTAKE_REPLICATION_V0_6_3_2_LIVE_R01_RESULT.md),
its
[`canonical artifact`](../artifacts/actuator_uptake_replication_v0_6_3_2_live_r01),
and the
[`portable verifier`](../verify_actuator_uptake_replication_v0_6_3_2_live_r01.py).

## v0.6.4 — Scaffold Aperture

Proceed only in a future research cycle with a newly preregistered basis for
both a positive channel contrast and a directionally attributable D-versus-C
placement effect. The sealed v0.6.3.2 result repeated D versus C but hit an X/Z
ceiling, so the strict gate did not open v0.6.4. Do not rescue it with another
block or revised gold in the consumed namespace. If this future lane is ever
reopened, keep the
replicated actuator, projection, raw history, output contract, and budgets
fixed, then test the separate hypothesis that a complete answer-adjacent DAG
saturates the provider-visible control surface:

```text
scaffold:  none | partial | full
placement: anti-control | gradient
```

The primary endpoint is the interaction, not a best-arm score: is the
directional D-minus-C downstream effect smaller under the full scaffold and
larger under the partial scaffold? Keep a fixed-size envelope across aperture
conditions by retaining the same candidate rows and changing only their state
(`UNAVAILABLE`, `CANDIDATE`, or `FIXED`). Report actual token differences.

Freeze two new cases x three trials x six arms (36 calls), one complete
six-sequence Williams block, before launch. Any missing arm makes aperture
selection `NOT_ASSESSED`. Select the smallest scaffold only if it preserves
schema validity and auditable necessary-support/invalidation/stable fields in
all six blocks, retains positive aggregate D-versus-C alignment with the
expected sign in at least four of six blocks, and satisfies the preregistered
interaction threshold against `full`. These are sufficiency conditions, not a
quality-improvement claim.

This stage may support the narrow statement that scaffold density moderates a
specific public actuator. It cannot show that partial DAGs are generally
better, that the provider's hidden trajectory was edited, or that the effect
improves reasoning quality.

## Runtime convergence target

The research tree remains modular and frozen for auditability, while
v0.6.2.1 now supplies the first converged product-acceptance path in one
readable EBRT monolith, `ebrt.py`, containing:

```text
raw semantic projection
  -> typed public state
  -> local autograd controller
  -> one bounded actuator compiler
  -> full-context regeneration
  -> trace and strict-grade export
```

Keep only minimal surrounding scripts for matched benchmarking, portable
artifact verification, and launching the frontend. The polished Reasoning IDE
consumes the same stable trace contract but remains a separate frontend. Do not
grow a general ontology, agent framework, control-plugin system, or second
product runtime path. A new abstraction is admitted only when it replaces an
older one in the product path. Historical modules and artifacts remain
immutable evidence rather than being rewritten to resemble the monolith.

This convergence is product acceptance, not promotion of a causally validated
quality actuator. Any future research actuator brought into `ebrt.py` must
first pass network-zero differential fixtures covering raw projection, local
control, actuator schedule, provider payload, output schema, and strict grading
trace. That gate prevents later simplification from silently creating a new,
uncalibrated intervention.

## v0.7 — Fresh Matched Hosted Evaluation

v0.7 asks the first quality question only after the v0.6.3.1 uptake canary,
its separately sealed fresh replication, the v0.6.4 aperture decision, and the
monolith convergence check:

> On a fresh frozen suite where control placement can matter, does the promoted
> EBRT actuator outperform its matched anti-placement construct control,
> zero-control, and text-only baselines under equal full-context generation
> budgets?

The suite must combine required evidence, later-invalidated evidence, a
semantically plausible distractor, and an unrelated stable fact. A strict pass
requires exact decision, required support presence, invalidated support absence,
and stable-fact preservation.

After a two-case contract smoke excluded from analysis, use 10 fresh cases x 2
trials x 5 post-event arms (100 analyzed calls) with the frozen ten-sequence
Williams order. Pre-event references may be added for UI diffs but are excluded
from the primary comparison. The arms are raw restart, matched textual revision
envelope, the explicit actuator with identity placement, the explicit actuator
with the frozen matched anti-placement, and the same actuator with
gradient-derived placement. The primary comparison is gradient placement versus
the anti-placement construct control. This evaluation exercises only the
converged monolith path;
lane multiplicity remains a later research question rather than entering the
product runtime without evidence. Report paired differences and McNemar
intervals only when the block is complete.

Decision readiness requires at least 18/20 complete five-arm blocks and no
differential arm attrition. Otherwise semantic status is `NOT_ASSESSED`.

If the quality gate fails, freeze the negative result and retain EBRT as an
instrumentation/debugging substrate. Do not coefficient-sweep the held-out
suite. A separately named successor may be designed from a new DEV partition.

## v0.8 — Outcome-Blind Runtime Lane Population

v0.8 asks the first genuine multiplicity-execution question: can three
independent GPT-5.6 calls populate typed public lanes before any outcome is
observed, after which the unchanged v0.5.5 substrate composes them into one
final regeneration? Start with one model so provider heterogeneity is not
confounded with composition.

Every lane is sealed and identity-blinded before merge or grading. Invalid
lanes make the block incomplete; there is no silent deletion, outcome-based
retry, or post-hoc repair. Reuse those exact lane bytes across downstream arms:

- one predeclared sealed lane;
- all lanes under a uniform non-adjoint merge;
- all lanes under a geometry-matched sham merge; and
- all lanes under the exact block-adjoint merge.

Evidence horizon and final-call budget remain matched. Lane-generation cost is
shared across downstream arms and reported separately. Identical lanes are
recorded as multiplicity collapse, not diversity. Disagreement, slack, and
residual remain independently visible.

Heterogeneous provider adapters become v0.8.1 only after same-model runtime
geometry is valid. GPT, Claude, Gemini, or a local model may then populate the
same public contract with provider identity hidden until grading. A positive
result would be local evidence for a fixed heterogeneous public-trajectory
substrate, not proof that SOL selects the best model. Tool-using autonomous SOL
agents and learned arbitration remain v0.9+ work.

## v0.9 — Return Toward the Latent Thesis

The original hidden-trajectory sketch can be tested only with an open-weight
model whose intermediate states and gradients are legitimately accessible.
v0.9 may compare:

- the current external public surrogate;
- an activation-level bounded latent intervention with frozen weights; and
- full restart without intervention.

The experiment must specify the exact state tensor, intervention site, decoder,
loss, norm budget, and matched compute. It must not transfer a public-surrogate
result into a claim about latent faithfulness.

The deferred novelty objective belongs after factuality and task-validity
guardrails are fixed. It requires a frozen reference distribution, semantic
distance metric, reward-hacking probes, and a matched rare-word/random-drift
control. Novelty is not allowed to rescue a failed v0.6-v0.8 endpoint.

## Promotion ledger

| Version | A passing result would establish | It would still not establish |
| --- | --- | --- |
| v0.6.0 | the exact sealed bundle has a deterministic provider-safe projection | any hosted execution or answer improvement |
| v0.6.1 | a real full-context bundle-to-output path and separately graded answer/lineage effect | controlled superiority, general quality, or gradients through the hosted model |
| v0.6.2 | a judge-readable, reproducible Reasoning IDE workflow | a final frontend or a population-level algorithm claim |
| v0.6.2.1 | one exact `Apply Revision -> Regenerate` product path is executable, observable, independently verifiable, and replayable in the IDE | causal necessity of the control, quality improvement, hidden-state editing, or general reasoning improvement |
| v0.6.3 | the hosted provider observably consumes one bounded public actuator and gradient placement differs directionally from its matched anti-placement construct control | that the changed output is better or that placement generalizes |
| v0.6.3.1 | in a separately authorized four-call canary, public selected-closure endpoints differ across the position-only payloads and gradient placement differs directionally from matched anti-placement | quality improvement, causality, population reliability, or direct promotion to v0.6.4; success opens only fresh replication |
| v0.6.3.2 | on one synthetic case fresh relative to the frozen v0.6.3.1 predecessor, the preregistered X/Z and D/C closure pattern repeats in both pairwise serial-position-counterbalanced blocks | causality, quality improvement, population reliability, an independently sampled case, or permission for v0.6.4 live execution |
| v0.6.4 | scaffold density moderates that fixed actuator under a matched aperture experiment | that partial scaffolds or the actuator generalize |
| v0.7 | a paired effect on one fresh frozen hosted suite | provider- or task-general superiority |
| v0.8 | independently executed same-model public lanes can be sealed before outcome and composed into one regeneration | autonomous agents, heterogeneous superiority, or optimal routing |
| v0.9 | a bounded open-model latent intervention result | equivalence between latent and public semantic trajectories |

## Standing stop conditions

- Never rewrite a completed predecessor artifact or relax its gold.
- Never infer semantic success from provider completion or surrogate decrease.
- Never infer causal superiority from an unmatched Before/After walkthrough.
- Never call deterministic schedule views independent agents.
- Never let downstream gold, grader output, or final answers enter an upstream
  lane or control map.
- Never use usage tokens as a monotonic proxy for reasoning quality.
- Never expand to learned routing while the fixed matched control is open.

The winning product story is intentionally narrower than the long-term thesis:
EBRT makes a late revision visible, carries it through a real full-context
regeneration, and then tests whether the corrected-looking answer has valid
fact-level support. The research program remains larger, but the demo must end
at an actual output and an auditable verdict.
