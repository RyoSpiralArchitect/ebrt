# EBRT v0.6.3 — Provider Actuator Calibration Preregistration

Status: **PASS_NETWORK_ZERO; CANONICAL PREFLIGHT READY; NO LIVE CALL AUTHORIZED**

## Question and boundary

v0.6.3 asks whether one explicit `bounded_reinspection_schedule` reaches a
hosted provider and produces a directionally attributable change outside a
verbatim schedule receipt. It does not ask whether the changed answer is
better, whether the effect generalizes, or whether a gradient crosses the
provider boundary.

The D treatment is built from `q^D` and evaluated in the same `q^D` coordinate
system. This is an intentional construct-aligned calibration, not independent
validation or a quality claim.

## Implemented surface and canonical status

The current implementation is deliberately one monolith plus frozen inputs:

```text
actuator_calibration_v0_6_3.py
fixtures/actuator_calibration_v0_6_3.json
fixtures/actuator_calibration_gold_v0_6_3.json
policy_lock_actuator_calibration_v0_6_3.json
artifacts/actuator_calibration_v0_6_3_preflight/
```

Reproduce its network-zero checks and canonical artifact with:

```bash
python3 actuator_calibration_v0_6_3.py self-test
python3 actuator_calibration_v0_6_3.py build-artifact
```

The committed self-test status is `PASS_NETWORK_ZERO`: all 21 frozen hard
gates are true, all 16 future payloads are presealed, and network/provider call
counts are zero. The canonical manifest is
`READY_ZERO_CALL_PREFLIGHT_ONLY`. The CLI has no live command and the policy
lock authorizes zero provider calls.

## Frozen fixture contract

Use two previously unused synthetic calibration cases and two fixed trials.
For each case, freeze:

```text
P0 = K union A0
P1 = K union A1
A0 intersect A1 = empty
size(A0) = size(A1) >= 2
```

P0 and P1 are equally valid necessary-support closures for the same answer.
Common support `K`, invalidated evidence, and stable-only evidence are disjoint
from the alternative sets. A downstream closure is valid only when it equals
exactly P0 or P1. A union, partial path, or mixed path fails the contract.

Every arm receives every evidence ID exactly once, byte-identical ordered raw
evidence, the same neutral candidate scaffold, output schema, review budget,
model settings, and token ceiling. Schedule rows remain in canonical ID order;
only the allowlisted actuator fields change.

## Polarities and arms

Derive `q^D` from one named, deterministically rederived signed controller
displacement. Center it over `A0 union A1`, normalize it to L1 norm 1, and set
all common, invalidated, and stable-only entries to zero. Nonfinite values,
zero norm, or equal P0/P1 aggregate are preflight failures.

Derive `q^X` from the immediate predecessor branch head
`2b2e58710871767e1f522f75380a7ca3c1d8580e` plus the opaque case ID. That seed
predates this v0.6.3 implementation. The runtime rule does not read the answer
value, `q^D`, or a provider output, but it intentionally depends on the
preregistered path equivalence class. Because the cases and controller were
designed after the predecessor head, no broader study-design selection
independence is claimed. X is an engineered positive wiring instrument, not a
gold-free or quality arm. The frozen rule selects P0 in one case and P1 in the
other; this balance cannot be selected after observing a provider response.

| Arm | Frozen construction |
| --- | --- |
| Z | all priorities tied and `no_reordering=true` |
| C | fixed anti-placement derangement of D with the same rank/tier multiset, size, top-k, and budget |
| D | schedule compiled from descending `q^D` placement |
| X | schedule compiled from descending `q^X` placement |

C is a matched construct anti-control, not a generic random sham. It must have
no eligible fixed point, must differ from D after provider projection, and must
have strictly lower frozen input alignment under `q^D`.
All four projected payload hashes must be distinct where the actuator semantics
require a contrast; treatment names, gradient/anti-control labels, polarities, path
labels, grader fields, expected closures, and the expected answer value are
forbidden from provider input. The answer-choice vocabulary remains visible
because it is part of the typed response contract.

## Zero-call authorization gates

Every item must pass before network access:

- strict duplicate-key and nonfinite rejection plus exact source, fixture,
  schema, runtime, and instruction fingerprints;
- exactly two untouched cases with two equal-cardinality valid paths and the
  opposite-case X selection frozen;
- exact local backward/displacement rederivation, finite unit-L1 `q^D`, finite
  unit-L1 `q^X`, and a nonzero P0/P1 `q^D` margin;
- exact Z/C/D/X row sets, one occurrence of every evidence ID, fixed protected
  IDs, equal budgets, and the locked C/D geometry and input-alignment margin;
- byte-identical ordered raw evidence, neutral scaffold, schema, and all
  non-actuator provider fields across arms;
- provider-payload denylist and structural scan proving that treatment keys,
  polarities, private paths, expected closure, grader, and expected answer
  value are absent;
- exact four-row Williams mapping; and
- deterministic reconstruction of the same 16 sealed payload hashes in two
  network-denied builds, plus fail-closed rejection of any extra, missing, or
  non-regular entry in the canonical artifact directory.

Failure of any item yields `ZERO_CALL_PREFLIGHT_STOP`; there is no partial live
authorization.

## Execution schedule

Generate and seal all 16 payloads before the first response. Use no stored
conversation, no previous response ID, no provider retry, no resume, and no
backfill.

```text
case_1 / trial_1: Z C X D
case_2 / trial_1: C D Z X
case_1 / trial_2: D X C Z
case_2 / trial_2: X Z D C
```

These four Williams rows balance arm position and first-order carryover over
the complete experiment. They do not establish within-case order balance or
independent random sampling.

## Endpoints and gates

Keep three endpoint families separate:

1. `channel_adherence`: the typed inspection-plan receipt follows the schedule;
2. `downstream_propagation`: typed decision state changes in the scheduled
   direction after excluding the receipt and free text; and
3. `quality_status`: answer and lineage quality, reported only as secondary
   diagnostics.

The provider returns selected candidate-edge IDs, not a trusted closure. The
local compiler validates an acyclic minimal selected graph, requires every
selected support edge to reach a primary or stable target, requires exactly the
frozen invalidation edge, and then rederives evidence reaching both targets.
The resulting evidence closure—not opaque support-node identity—must equal
exactly P0 or P1. Graph-isomorphic candidate paths are therefore accepted,
while unions, mixed evidence, redundant edges, and irrelevant edges fail. That
graph-derived closure is the only alignment input. The compiler never scores
the inspection plan, free-text rationale, or a model-written closure field.

```text
alignment(output, q) = sum(q_i for i in active necessary-support closure)
delta_XZ = alignment(X, q^X) - alignment(Z, q^X)
delta_DC = alignment(D, q^D) - alignment(C, q^D)
```

These deltas are definitions for a separately authorized future hosted block.
The current self-test compiles both exact conformance paths only to verify graph
closure, output round-trip, and alignment arithmetic. It does not emit a
synthetic Z/C/D/X arm-effect result, and no synthetic delta is a hard gate or
evidence of provider uptake.

Freeze the numeric tolerance before launch. X propagation passes only when the
sum of the four paired `delta_XZ` values is positive and at least three are
strictly positive. D attribution uses the same rule for `delta_DC`, with D and
C both adhering to their schedules in the same positive blocks. Any incomplete
block makes both effect gates `NOT_ASSESSED` rather than reducing the
denominator.

Exact-one closure, invalidated-support absence, and stable-fact preservation
are safety gates for all 16 outputs. Raw byte inequality and schedule echo are
never counted as downstream propagation.

## Stop statuses

```text
ZERO_CALL_PREFLIGHT_STOP
  A source, fixture, polarity, geometry, leakage, schedule, or payload seal gate failed.

INCOMPLETE_NOT_ASSESSED
  A provider call, receipt, parser, or four-arm block failed; execution stops with no retry.

STOP_OUTPUT_CONTRACT
  A completed output violated exact-one closure, invalidation, or stable preservation.

STOP_CHANNEL_ADHERENCE_NULL
  X did not consume the frozen schedule.

STOP_ACTUATOR_ECHO_ONLY
  X emitted the schedule receipt but did not pass non-echo X-versus-Z propagation.

STOP_GRADIENT_PLACEMENT_NULL
  X propagated, but D did not exceed matched C under the frozen q^D endpoint.

PROMOTE_V0_6_4_ACTUATOR_GATE
  Execution, safety, X adherence, X propagation, D/C adherence, and D/C propagation all passed.
```

No failed or null status may be rescued by editing the fixture, relaxing the
closure contract, changing thresholds, trying alternate prompt channels, or
rerunning this namespace.

The present namespace ends before those terminal live statuses are evaluated.
Its only published decision is `PASS_NETWORK_ZERO` /
`READY_ZERO_CALL_PREFLIGHT_ONLY`; hosted adherence, non-echo propagation, and
gradient-placement effect remain unobserved.
