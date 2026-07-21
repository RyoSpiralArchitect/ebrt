# EBRT Runtime Preview 3 — Temporal Public Trajectory Control

Status: **NETWORK-ZERO OFFLINE CONTRACT PASS; HOSTED UPTAKE, SEMANTIC QUALITY, AND EFFECT ATTRIBUTION NOT ASSESSED**

This note describes the implementation in live protocol `v0.6.2.4`. It is a
product-runtime continuation of `v0.6.2.3`, not a reinterpretation of the
historical `ebrt.py` acceptance artifact or of the v0.5.4 research bundle.
Request, provider, compiled-output, trajectory, control, actuator, response,
health, and error schemas move together.

The change promotes the former scalar diagnostic trace into a chronological,
three-axis public revision trajectory. One local reverse-mode step assigns
credit to time-local public controls. The revised trajectory is then replayed
through the same declared recurrence before its control magnitudes are decoded
into the existing executable Apply Revision actuator.

## Implemented runtime path

```text
already-emitted public Before state
  -> typed late event and caller-supplied candidate graphs
  -> chronological neutral public trajectory
  -> trajectory-wide public surrogate loss
  -> exactly one torch.float64 backward()
  -> L2 projection and forward-only backtracking
  -> chronological revised-trajectory replay
  -> magnitude-to-inspection allocation decoder
  -> deterministic 100-unit public inspection plan
  -> executable Apply Revision state machine
  -> at most one full-context hosted regeneration attempt
  -> public output diff and structural verification
```

The gradient boundary ends at the bounded public controls. JSON projection,
provider parsing, hosted generation, output validation, and grading are not
differentiated.

## Public state and source basis

The axis order is fixed:

```text
event_consistent_support
invalidated_support_clearance
stable_support_retention
```

The initial vector is computed from the compiled public Before artifact:

```text
correction evidence present
fraction of typed-invalidated evidence already absent
fraction of typed-stable evidence still present
```

The first component initializes the trajectory's
`event_consistent_support` axis; it is not a learned embedding. All three
coordinates are public structural quantities.

The per-evidence effect basis is also public. Across every caller-supplied
candidate graph, direct target incidence contributes `2` and inherited target
incidence contributes `1`. Scores are normalized by the maximum observed
score. The explicit typed correction evidence receives a normalized effect of
`1.0`. Answer choices, target values, an accepted closure ID, graders, and
semantic-gold fields do not participate in this basis.

## Three-axis chronological recurrence

For evidence step `t`, let `s[t-1]` be the previous three-axis public state,
`u[t]` the scalar time-local control, `m[t]` its eligibility mask, and `e[t]`
the normalized public incidence effect. The implementation first applies:

```text
d[t, support]    = 0.82 * s[t-1, support]
d[t, clearance]  = 0.82 * s[t-1, clearance]
d[t, stable]     =        s[t-1, stable]
```

It then constructs a typed public proposal:

```text
eligible_effect = e[t] when m[t] else 0

p[t, support]
  = 1 - (1 - d[t, support]) * (1 - eligible_effect)

p[t, clearance]
  = 1 when t is the declared correction step
    d[t, clearance] otherwise

p[t, stable]
  = initial stable coordinate
```

The transition is the v0.5.4-style sigmoid interpolation, reduced to one
public scalar control per evidence time:

```text
alpha[t] = sigmoid(u[t] * m[t])
s[t]     = d[t] + alpha[t] * (p[t] - d[t])
```

Evidence is visited in the exact `all_raw_evidence` order, and the request
contract requires the typed correction to terminate the visible horizon. The
stable axis is an exact identity under both the neutral and revised runs.

The implementation also computes a graph-incidence-derived full-admission
support envelope. Starting at the initial support coordinate, it visits the
same evidence in the same chronology, applies the same `0.82` support decay,
and fully admits each eligible public incidence effect without the
control-dependent interpolation gate:

```text
reference_decay[t] = 0.82 * reference[t-1]

reference[t]
  = 1 - (1 - reference_decay[t]) * (1 - eligible_effect[t])
```

This is a public structural reference, not a semantic target or hidden-state
trace. Every neutral and revised trajectory point publishes its corresponding
`full_admission_support_reference` value.

This trajectory is a hand-built public revision surrogate. It is not a model
hidden state, an attention trace, or a transcript of private reasoning.

## Implemented trajectory-wide loss

The terminal target is derived only from the typed public revision contract:

```text
[1.0, 1.0, initial_stable_coordinate]
```

The objective contains four published components:

```text
terminal
  = 0.5 * squared_distance(final_state, terminal_target)

path
  = mean squared distance between the preterminal trajectory support axis
    and the graph-incidence-derived full-admission support envelope

control
  = 0.01 * sum((u * eligibility)^2)

smoothness
  = 0.005 * sum(diff(u * eligibility)^2)

objective
  = terminal + 0.1 * path + control + smoothness
```

The path component excludes the declared correction terminal and is active in
the current offline cases: the neutral preterminal path loss must be positive,
and the revised preterminal path loss must be strictly smaller. The self-test
also reconstructs that mean squared error directly from the published points
and their reference values. This is enforced in the trajectory artifact as
`trajectory_path_loss_decreased`. Stable-state locality remains an exact
structural identity gate. No expected answer, accepted target value, or
semantic quality label is used as a target.

## One backward, projection, and replay

Controls begin at an exact zero vector. The neutral objective executes one
`loss.backward()` in `torch.float64`. The raw step is:

```text
raw_displacement = -0.05 * gradient
```

It is projected to a global `L2 <= 0.25` budget. The runtime then evaluates
the projected step and, if necessary, halves it for at most 12 backtracking
steps. Backtracking is forward-only; it does not add backward calls. A control
is accepted only when the frozen public objective strictly decreases.

Every time-site gradient is checked against a central finite difference with
epsilon `1e-6`; the maximum accepted error is `1e-8`. The accepted control is
replayed through the same recurrence, and the replayed objective, loss
components, terminal state, and every chronological trajectory point must be
exactly equal to the sealed revised trace.

Hard gates additionally require:

- non-zero temporal credit at a controllable pre-event step;
- non-zero credit at the correction site;
- positive neutral path loss and strictly lower revised path loss;
- exact stable-axis identity;
- a bounded non-neutral control;
- objective descent; and
- a gradient boundary before JSON and the provider.

## Matched temporal sham

The offline runtime constructs one matched sham by reversing the accepted
control values over eligible time sites. It preserves the exact multiset of
absolute eligible control values and the exact global L2 norm. The sham makes
zero provider calls.

The implemented hard gate requires:

```text
exact temporal placement objective + 1e-12
  < matched reversed-placement objective
```

This comparison is scoped only to the frozen public recurrence. It does not
establish provider uptake, hosted-output causality, semantic superiority, or
general reasoning improvement.

## No-event identity sentinel

The public live API still requires a typed event. Separately, a private
network-zero sentinel constructs an explicit no-event identity trajectory.
For that sentinel:

```text
neutral trace == revised trace
controls       == 0
gradients      == 0
backward calls == 0
provider calls == 0
```

The self-test patches the trajectory-loss function to raise if called, then
verifies that the sentinel never invokes it. No-event behavior is therefore an
exact identity path rather than a small learned or numerical update.

## Trajectory-to-actuator binding

The accepted control is decoded to public inspection allocation as:

```text
allocation = masked_softmax(abs(control) / 1.0)
```

The existing actuator compiler selects the declared number of highest-allocation
eligible evidence rows, renormalizes their shares, derives relative emphasis
and review depth, and reuses the deterministic largest-remainder allocator for
exactly 100 abstract public inspection units. These units are not provider
tokens, attention weights, or measured compute.

Typed invalidated evidence is compiled separately to `SUPPRESS`; typed stable
evidence is compiled separately to `PRESERVE`. Their semantic actions are not
inferred from gradient signs. The temporal control supplies the `REINSPECT`
placement and continuous magnitude.

The public trajectory fingerprint is copied into the inspection plan, public
revision program, compiled actuator, actuator execution, provider operation,
and provider-payload binding checks. Before compiling an actuator, the runtime
independently rederives the scientific receipt from the request and compiled
Before state. The validator:

1. recomputes the public Before vector, graph-incidence effects, eligibility,
   and correction index;
2. recomputes every central finite-difference derivative and checks the
   published gradients against it;
3. reconstructs `-0.05 * gradient`, the exact L2 projection, and the same
   deterministic forward-only backtracking search, then requires the published
   controls, unprojected norm, projection scale, and accepted backtrack index
   to match;
4. replays the neutral and revised trajectories and requires exact equality of
   objectives, loss components, terminal states, chronological points, and
   full-admission support references;
5. reconstructs the reversed eligible-time matched sham and requires its
   objective, terminal state, norm, zero-call scope, and every trajectory hard
   gate to match; and
6. recomputes neutral and revised masked allocations and the complete ordered
   control-check receipt.

This validation occurs before the trajectory can be compiled into an
actuator. A self-consistent fingerprint reseal is therefore insufficient to
replace the scientific derivation.

A self-test mutates a revised stable coordinate, reseals the nested objects,
and confirms rejection before provider execution with
`PUBLIC_TRAJECTORY_FORWARD_REPLAY_MISMATCH`.

Two additional coherent-reseal attacks are checked. Changing the matched-sham
objective and resealing is rejected with
`PUBLIC_TRAJECTORY_RECEIPT_DERIVATION_INVALID`. Shifting both published
gradients and finite-difference values, updating the trajectory-point gradient
copies, and resealing every affected object is rejected with
`PUBLIC_TRAJECTORY_GRADIENT_RECEIPT_INVALID` because finite differences are
recomputed from the recurrence rather than trusted from the artifact.

## Current offline evidence

Run on the current working tree:

```bash
python3 ebrt_live.py self-test
```

The current implementation returns **41/41 checks PASS**. The exact current
receipt is:

```text
self-test schema       ebrt-live-self-test-v0.6.2.4
self-test fingerprint  98b1176f79660b01914de1ed7f8729f9d592e325bbb77c9064aecd60a70e82af
demo result fingerprint
                       bc3f740e9b4ecaa662c65078db6bbb482ec9fbdbbd76c21a2e5cb47df5c249e8
generic result fingerprint
                       d1fbdfe286436240de1ffc8196ac7bbdf3bec361679437a7cdbc664bb3608728
```

The trajectory-specific passing checks are:

```text
public_trajectory_forward_is_chronological_and_deterministic
late_event_assigns_nonzero_pre_event_temporal_credit
no_event_is_exact_identity_and_skips_backward
trajectory_adjoint_matches_central_finite_difference
trajectory_update_is_bounded_and_descends
trajectory_nonterminal_path_loss_is_active
matched_time_permutation_is_geometry_matched_and_worse
stable_axis_is_exactly_preserved
trajectory_patch_compiles_exactly_to_continuous_actuator
resealed_trajectory_tamper_rejected_before_provider
scientific_receipt_reseal_tamper_rejected_before_provider
```

A fresh local scripted invocation was also run:

```bash
python3 ebrt_live.py apply-demo --provider scripted
```

It completed with one logical/API provider attempt and operational `PASS`.
The request-scoped receipt for that invocation was:

```text
scripted response fingerprint
                       611321d0a52337d996855548be1ae712c06d7048938770343d1bd2d93dffaa93
public trajectory fingerprint
                       c1e6766cc16d276fb21c2a423e9946c63665c18497becbd9b97b5874e6d77f84
```

The scripted response fingerprint includes the fresh request identity and is
an execution receipt, not a pinned reproducibility claim or hosted-model run.

The same network-zero suite also retains protocol fail-closed behavior,
idempotency and single-attempt accounting, generic non-fixture topology,
100-unit actuator execution, candidate opacity, scoped block/restore audit,
semantic-gold-key rejection, and the byte-pinned historical v0.6.2.1 runtime.

This is offline mechanism and contract evidence. It is not a fresh hosted
benchmark, a replicated matched provider experiment, or evidence that the
hosted model consumed the temporal allocation.

## Claim boundary

The implemented result supports the following narrow statement:

> EBRT rolls a typed, three-axis public revision state forward over a visible
> evidence horizon, computes one bounded reverse-mode temporal control step,
> replays the revised public trajectory, and deterministically compiles its
> magnitude into an executable full-context revision request.

It does **not** establish any of the following:

- access to or editing of GPT hidden states, attention, KV cache, or private
  chain of thought;
- a gradient through JSON, GPT-5.6, provider parsing, generation, or grading;
- autonomous discovery or certification of semantic truth in caller-supplied
  graphs;
- provider uptake of the trajectory-derived allocation;
- semantic correctness, counterfactual hosted-output effect, causal
  superiority, or general reasoning improvement; or
- that `SUPPRESS` and `PRESERVE` were discovered from gradient signs.

Operational acceptance remains separate from
`provider_uptake_status`, `semantic_correctness_status`,
`counterfactual_output_effect_status`, and `effect_attribution_status`; those
axes remain `NOT_ASSESSED` unless a later sealed provider experiment measures
them.
