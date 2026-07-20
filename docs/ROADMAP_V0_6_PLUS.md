# EBRT v0.6+ — Execution, Evaluation, and Orchestration Roadmap

Status: **v0.6.0 PREFLIGHT PASS; v0.6.1 FIVE-CALL BLOCK COMPLETE, GATE HELD; v0.6.3 NETWORK-ZERO PREFLIGHT PASS, LIVE NOT AUTHORIZED**

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

These findings make another network-zero mechanism extension lower priority
than a clean return to actual hosted output.

## Immediate critical path

The completed bridge path is v0.6.0 -> v0.6.1, with v0.6.2 preserving it as
a judge-readable product surface. The next algorithmic path is deliberately
separate:

```text
v0.6.3  calibrate one explicit provider-visible actuator
v0.6.4  measure whether scaffold aperture suppresses that actuator
         ↓ only after a non-null, directionally attributable uptake result
converge the promoted runtime into one readable monolith
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

## v0.6.3 — Provider Actuator Calibration Canary

The monolithic network-zero implementation now records `PASS_NETWORK_ZERO`
with 20/20 hard gates and a canonical
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

## v0.6.4 — Scaffold Aperture

Proceed only if v0.6.3 establishes channel adherence, downstream propagation,
and a directionally attributable D-versus-C placement effect. Keep the
promoted actuator, projection, raw history, output contract, and budgets fixed,
then test the separate hypothesis that a complete answer-adjacent DAG saturates
the provider-visible control surface:

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

The research tree may remain modular and frozen for auditability, but the
promoted product path must converge before v0.7. Once v0.6.3 identifies a
non-null actuator and v0.6.4 selects its smallest sufficient scaffold, rewrite
that accepted path into one readable EBRT monolith containing:

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
runtime path during this convergence. A new abstraction is admitted only when
it replaces an older one in the promoted path. Historical modules and artifacts
remain immutable evidence rather than being rewritten to resemble the
monolith.

The rewrite is accepted only if network-zero differential fixtures show
byte-identical raw projection, local control map, actuator schedule, provider
payload, output schema, and strict grading trace between the promoted modular
path and the monolith. This equivalence gate prevents simplification from
silently creating a new, uncalibrated intervention.

## v0.7 — Fresh Matched Hosted Evaluation

v0.7 asks the first quality question only after the v0.6.3 uptake gate,
v0.6.4 aperture decision, and monolith convergence check:

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
| v0.6.3 | the hosted provider observably consumes one bounded public actuator and gradient placement differs directionally from its matched anti-placement construct control | that the changed output is better or that placement generalizes |
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
