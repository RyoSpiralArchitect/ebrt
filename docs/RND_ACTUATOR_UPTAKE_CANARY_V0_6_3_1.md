# EBRT v0.6.3.1 — Observable Actuator Uptake Canary

Status: **NETWORK-ZERO MEASUREMENT REPAIR; NO LIVE CALL AUTHORIZED**

## Why this namespace exists

The frozen v0.6.3-live-r01 namespace completed one provider call and then
stopped at the unchanged public graph compiler with
`EXACT_ONE_CLOSURE_FAILED`. Fifteen calls were not attempted, semantic gold was
not loaded, and neither X-versus-Z channel propagation nor D-versus-C placement
was assessed. That artifact remains immutable and must not be rerun, regraded,
or interpreted as a null actuator result.

v0.6.3.1 is a separately named, zero-call measurement repair. It does not
change the r01 evidence or loosen its exact-one-closure contract. Instead, it
removes two sources of premature termination from a future uptake canary:

1. the provider selects one known, opaque closure coordinate rather than
   freely generating a public dependency graph; and
2. a known stale, mixed, or incomplete closure is retained as a semantic
   endpoint rather than rejected as a structural output error.

The resulting question is intentionally smaller than the v0.6.3 quality
question:

> With every evidence chunk, candidate coordinate, instruction, schema, and
> budget fixed, does one position-only public perturbation change the hosted
> model's selected public closure, and does the block placement selected by one
> local backward pass differ directionally from a geometry-matched
> anti-placement?

This is an actuator-uptake calibration. It is not a reasoning-quality study.

## One-monolith surface

The measurement repair remains one readable network-zero monolith plus two
frozen inputs:

```text
actuator_uptake_canary_v0_6_3_1.py
fixtures/actuator_uptake_canary_v0_6_3_1.json
fixtures/actuator_uptake_canary_gold_v0_6_3_1.json
```

The monolith has no live command. It can derive one local float64 controller,
compile four blinded provider payloads, parse synthetic conformance outputs,
grade semantic endpoints, classify all closure-coordinate combinations, and
build or validate a canonical network-zero artifact. Provider calls authorized
and observed by this namespace are both zero.

Once the separately reviewed zero-call policy lock exists, reproduce the
preflight with:

```bash
python3 actuator_uptake_canary_v0_6_3_1.py self-test
python3 actuator_uptake_canary_v0_6_3_1.py build-artifact
python3 actuator_uptake_canary_v0_6_3_1.py validate-artifact
```

`emit-lock` is a construction command for the reviewed policy-lock file; it is
not live authorization. Any future provider execution requires a new runner,
a separate merged authorization lock, and an exact-commit authorization tag.

## Frozen case and public action

The fixture contains one previously unused synthetic case, seven immutable
evidence chunks, and four equal-cardinality candidate closures. Each candidate
label is an opaque, content-derived `K_...` identifier. The provider sees the
same candidate IDs, selected-evidence sets, candidate order, answer choices,
record-format choice, instructions, and typed response contract in every arm.

The primary public action is exactly:

```text
selected_closure_id
```

The provider also returns the current answer, stable record format, and exactly
three reviewed evidence IDs. Those fields remain public diagnostics, but the
inspection receipt is not the primary uptake endpoint. Free text and private
chain-of-thought are neither requested nor scored.

After parsing, the local harness deterministically expands the selected known
closure into a small public Evidence-to-Decision graph. The provider does not
write graph edges and cannot invent a fifth closure coordinate.

The separate provider-excluded gold assigns the four coordinates these roles:

```text
ALIGNED_EVENT_CONSISTENT
ALTERNATIVE_EVENT_CONSISTENT
STALE_INVALIDATED_SUPPORT
MIXED_INSUFFICIENT_SUPPORT
```

Both event-consistent coordinates are quality-valid. The aligned coordinate is
the preregistered construct target for X and D; it is not declared to be the
only semantically valid answer path. Gold and role labels are forbidden from
provider-payload construction. Network-zero conformance validates their
relation to the controller, while a future live executor must not load them
until all four attempts are terminal.

## The single actuator

The only provider-visible intervention is `evidence_permutation`. Every arm
contains the exact same immutable evidence-chunk byte multiset. After evidence
rows are normalized by ID, all provider payloads must be byte-identical. Only
sequence position may differ.

| Arm | Evidence order | Purpose |
| --- | --- | --- |
| Z | frozen neutral order | no-actuation positional reference |
| X | preregistered correction-first order | positive channel control |
| C | opposed path block before preferred path block | matched construct anti-placement |
| D | local-backward-preferred path block before opposed path block | tested EBRT placement |

D is compiled from one real local float64 backward pass through a frozen public
recurrent surrogate. Central finite differences audit the gradient. The
continuous displacement is converted deterministically into a discrete path-
block permutation before JSON construction; no float control is sent to the
provider.

C swaps the same two path blocks while keeping the late event, invalidated
evidence, and stable evidence at the same positions as D. Relative to Z, C and
D must match in Spearman footrule distance, Kendall distance, and fixed-point
count. D must have strictly greater frozen positional alignment under the local
displacement. This makes C a geometry-matched anti-placement, not a random
prompt.

X is an engineered correction-first positive control. Its job is to establish
whether this evidence-order channel can move the selected public closure on the
sealed case. It is not a quality arm and does not validate D by itself.

The gradient boundary is explicit:

```text
local recurrent public-state surrogate
  -> one float64 backward pass
  -> deterministic evidence permutation
  -> stop-gradient / JSON boundary
  -> future hosted full-context call
  -> selected public closure
```

The hosted model is not differentiated. This design makes no claim about its
hidden states, attention, KV cache, or private reasoning trajectory.

## Structural validity versus semantic endpoints

v0.6.3.1 does not relax semantic grading. It separates two jobs that r01
collapsed into one terminal compiler gate.

Structural failures make an arm invalid:

- provider transport failure or timeout in a future runner;
- malformed, duplicate-key, nonfinite, or schema-invalid JSON;
- checkpoint, answer vocabulary, record-format, or receipt-schema drift; or
- an unknown `selected_closure_id`.

Known semantic failures remain valid observations:

- stale invalidated support;
- mixed or insufficient support;
- missing late-event selection;
- retained invalidated evidence;
- divergence between answer validity and public-trace diagnostics; or
- failure to preserve the stable record-format evidence.

The local compiler expands these known coordinates without semantic rejection,
then the post-call grader reports answer, closure role, invalidation, stable
preservation, and answer-trace status separately. A future four-call runner
must continue after a known semantic failure. A provider, parse, schema, or
unknown-ID failure marks that arm structurally invalid, but the runner still
attempts the remaining presealed arms without retry or backfill and classifies
the complete block `INCOMPLETE_NOT_ASSESSED`. Only a pre-call fixture, source,
lock, payload, journal, or artifact-integrity failure stops the whole block
before the next call.

This distinction keeps the contract strict while ensuring that a failed public
reasoning state is measured rather than erased before the actuator contrast is
available.

## Four-call canary and decision grammar

A future live namespace, if separately authorized, contains one call for each
of Z, C, D, and X in the presealed blinded order. Retry, resume, backfill,
adaptive prompt edits, and alternate output paths remain forbidden.

The primary decision uses the selected closure coordinate, not raw output-byte
inequality. X-versus-Z tests whether the positive control reaches its aligned
target. D-versus-C is directional only when D selects that exact aligned target
and C does not. A frozen `1 / 0 / -1` construct-alignment score is retained as
a diagnostic, but a favorable numeric ordering between two off-target closures
cannot promote the canary. Aligned and alternative closures remain independently
quality-valid. The complete classifier is deterministic over all 4^4
closure-coordinate combinations.

Terminal decisions are:

```text
INCOMPLETE_NOT_ASSESSED
STOP_POSITIVE_CONTROL_CEILING_NOT_ASSESSED
STOP_CHANNEL_INERT
STOP_CHANNEL_AMBIGUOUS
STOP_CHANNEL_ADVERSE
STOP_PLACEMENT_CEILING_NOT_ASSESSED
STOP_PLACEMENT_NULL
STOP_PLACEMENT_AMBIGUOUS
STOP_PLACEMENT_ADVERSE
PROMOTE_TO_FRESH_REPLICATION
```

Promotion requires both:

1. Z does not select the aligned target while X does; and
2. D selects that exact aligned target while matched C does not.

If Z and X both select the target, the positive control is at ceiling and the
channel is not assessed. If C and D both select the target, placement is at
ceiling and is not assessed. Equality, an off-target change, or movement in the
opposite direction cannot be promoted as uptake.

## Promotion boundary

Even `PROMOTE_TO_FRESH_REPLICATION` is only a successful sensitivity canary.
It does not directly open v0.6.4. It opens one separately designed, fresh,
sealed replication with new evidence content and its own authorization
boundary. v0.6.4 remains blocked until that replication confirms a non-null,
directionally attributable actuator result under its preregistered rule.

A four-call result cannot establish:

- improved answer or lineage quality;
- a causal or population-level actuator effect;
- general sensitivity to evidence order;
- editing of hosted hidden state, attention, KV cache, or private reasoning;
- equivalence between a selected public closure and private reasoning; or
- provider, task, case-family, or prompt generalization.

If the positive control is inert, this evidence-order channel stops. If X
opens the channel but D does not exceed C, this local-backward-selected block
placement stops for the construct. Neither result may be rescued by modifying the completed
fixture, candidate catalog, target, order, prompt, score, or threshold.

## Relation to the convergent runtime

This measurement repair adds no ontology, agent framework, actuator plugin
system, or frontend runtime. Its candidate catalog is a finite calibration
instrument, not a required production representation. The central EBRT line
remains:

```text
late event
  -> typed public trajectory
  -> local temporal backward credit
  -> one deterministic public actuator
  -> full-context regeneration
  -> public answer and lineage audit
```

The deterministic DAG remains useful downstream for expansion, inspection,
and grading. It is not treated as the provider actuator itself. A promoted
path must ultimately collapse back into one readable runtime monolith, with
only minimal benchmark, verifier, and frontend-launch support around it.
