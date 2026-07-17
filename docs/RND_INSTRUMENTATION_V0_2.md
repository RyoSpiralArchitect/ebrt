# EBRT v0.2 counterfactual instrumentation

## Status

EBRT v0.2 adds an observational and counterfactual measurement layer on top of
the frozen v0.1 mechanism. It does not edit either `ebrt_monolith_v0_1.py` or
`benchmark_ebrt_v0_1.py`.

The positive purpose of this layer is algorithm discovery. It is intended to
show which event, route, control intervention, replay policy, and state-geometry
signals predict a revision that is useful, persistent, local, and compute
efficient. Claim discipline remains necessary, but it is not the endpoint of
the instrumentation.

## Research questions

The first v0.2 experiments ask four concrete questions.

1. Does the most semantically relevant earlier state also have the greatest
   target-aligned event-source projection sensitivity along the tested control
   direction?
2. When a local revision succeeds, how much of its effect survives to the
   event source and the terminal state?
3. Do trajectory geometry signals add predictive information beyond event
   score, control magnitude, replay distance, and sequence length?
4. Which candidate route maximizes useful target/source gain while minimizing
   unrelated-state leakage and replay cost?

These questions are designed to produce candidate router and revision-policy
changes. They are not merely explanations attached after an answer is emitted.

## Counterfactual mirror contract

v0.2 distinguishes two baselines that must not be conflated.

- **Global forward baseline:** the complete zero-revision trajectory from the
  start of the session. This is useful for a whole-run visualization.
- **Event-local mirror:** the trajectory that contains all previously accepted
  revisions but omits only the current revision delta. This is the comparison
  used to attribute a local effect to one revision event.

For event `k`, the local mirror and revised branch share observations, frozen
core, dtype, seed, prior committed controls, and every state before the earliest
replay step. The only treatment difference is the chosen control delta for
event `k`.

The global forward difference is not interpreted as the marginal effect of a
later event because it also contains every earlier accepted revision.

## Trace levels

The default trace is deliberately compact.

- **Session:** source/core hashes, configuration, adapter provenance, global
  baseline/final geometry, events, and a deterministic trace fingerprint.
- **Event:** semantic score decomposition, eligible anchors, selected route,
  event-local mirror, control update, energy change, replay span, and
  accept/rollback state.
- **Diagnostic probe:** optional centered finite differences for eligible
  candidates along one normalized topic-aligned control direction. Probe work
  is reported separately from execution work and cannot change the committed
  result.

Deep per-optimizer-step tensor capture is not enabled by default. It can grow as
`events × revision steps × replay length × latent dimension`, and collecting it
would distort timing and memory measurements.

## Geometry fields

For reasoning state `R_t`, v0.2 records:

```text
velocity[t]                = R_t - R_(t-1)
speed[t]                   = ||velocity[t]||
normalized_acceleration[t] = ||velocity[t] - velocity[t-1]||
                             / (||velocity[t]|| + epsilon)
turn_angle[t]              = acos(cosine(velocity[t-1], velocity[t]))
mirror_separation[t]       = ||R_t(revised) - R_t(mirror)||
```

Near-zero velocity makes an angle undefined; it is serialized as `null`, not
as zero. Geometry is computed for the full state and separately for the topic,
belief, and context blocks because the three blocks have different roles and
scales.

`normalized_acceleration` and `turn_angle` are exploratory state signals. v0.2
does not assume that high curvature is a belief transition, that low curvature
is better reasoning, or that either field measures answer quality.

## Revision-effect fields

The phrase “revision magnitude” is too ambiguous for diagnosis. The trace keeps
the following quantities separate:

- control delta norm at each selected target;
- local state separation at the target and event source;
- separation peak and area under the replay curve;
- source and terminal target-topic projection gain;
- propagation-survival ratio and decay distance;
- unrelated-topic or unrelated-state leakage;
- replay distance, replayed generator steps, and backward calls;
- energy drop, gradient norm, accepted checkpoint, and rollback-to-best state.

This separation is important because a large local edit can disappear during
replay, while a persistent difference can still be harmful leakage rather than
a useful correction.

## Semantic relevance versus source-projection leverage

The existing router combines topic similarity, contradiction, and recency into
an attention score. v0.2 records those components separately.

An optional diagnostic probe perturbs one normalized topic-aligned control
direction at each eligible earlier state. `control_leverage` is the centered
finite difference of the target-aligned belief projection at the event source.
It is not the gradient of revision energy, an all-direction controllability
measure, or terminal utility. It does not change the executed route.

This restricted signal can be compared with semantic relevance without
assuming that the two ranks coincide. An epsilon sweep, direct reroute
comparison, and nonlinearity test across control magnitudes are still required
before treating it as a runtime feature.

A future hybrid router is eligible for promotion only if a frozen-suite
benchmark shows improved useful gain or efficiency without a corresponding
increase in leakage. The instrumentation does not silently promote its own
diagnostic ranking into runtime policy.

## Observer-neutrality gate

Instrumentation is invalid if enabling it changes the mechanism it measures.
For matched runs, the observer-neutrality contract requires exact agreement on:

- detected and suppressed events;
- selected routes and attention weights;
- accepted checkpoints and control tensors;
- final states and decoded output;
- generator/backward/decode call counts;
- frozen-core hash and reproducibility fingerprint.

Diagnostic replays and gradient probes use separate cloned state and are
reported outside execution counters. Instrumented timing is never substituted
for the frozen v0.1 timing baseline.

The representative self-test exercises full output, route, control, counter,
and fingerprint equality on four selected fixtures. The 1,536-session full run
records run-wide frozen-core, generator-accounting, and finite-output checks;
it does not claim a second full-output equivalence pass for every session.

## Full v0.2 measurement run

The committed full run uses the unchanged v0.1 48-case suite, model seeds
`0..31`, 32 revision steps, CPU float32 execution, and a centered finite
difference leverage probe with epsilon `1e-3`.

- 1,536 instrumented sessions;
- 1,312 committed revision events;
- 512 events with more than one eligible anchor, representing 15 case clusters,
  16 case-source fixtures, and two case families;
- 1,984 candidate source-projection-leverage probes;
- 2,000 case-cluster bootstrap resamples;
- 100% frozen-core, generator-accounting, and finite-output pass rates.

The exact protocol, source hashes, environment, row counts, and artifact hashes
are in `artifacts/benchmark_instrumentation_v0_2/manifest.json`.

### Semantic relevance and source-projection leverage nominate separate roles

Single-candidate events make any route agreement automatic, so the informative
surface is the 512 multi-candidate rows. All listed alignment values were
invariant across the 32 seeds within each case-source fixture; the rows are not
512 independent routing situations. Case-cluster intervals retain every paired
seed and event within a resampled case.

| Measurement | Estimate | Case-cluster 95% CI |
| --- | ---: | ---: |
| Attention/source-projection-leverage Spearman correlation | 0.5000 | [0.0667, 0.8824] |
| Executed route selected maximum source-projection leverage | 75.00% | [53.33%, 93.75%] |
| Annotated semantic-gold anchor had maximum source-projection leverage | 12.50% | [0.00%, 33.33%] |
| Executed route selected semantic-gold anchor | 37.50% | [13.33%, 64.71%] |

This does not show that source-projection leverage should replace semantics.
The low semantic-gold/max-leverage overlap and broad cluster uncertainty make
direct replacement ineligible for promotion; they do not establish that such a
router is harmful.

The nominated algorithmic hypothesis is a separation of roles. A semantic
anchor should specify what evidence or belief is being revised. A candidate
control anchor or window would specify where a bounded intervention is
attempted. Whether it improves downstream survival must be tested
prospectively rather than read back from this diagnostic.

### Propagation is more informative than perturbation volume

The unnormalized full-trajectory separation AUC was negatively associated with
source projection gain (`rho=-0.7962`, case-cluster 95% CI
`[-0.8789, -0.6631]`). That quantity is strongly confounded by event position
and replay length. After normalization, AUC per step had a much weaker and
uncertain association (`rho=-0.2228`, `[-0.5353, 0.1575]`).

In contrast, mean post-source separation tracked source projection gain
strongly (`rho=0.8120`, `[0.6520, 0.8940]`). Terminal separation also tracked it
(`rho=0.7762`, `[0.6060, 0.8703]`). The benchmark's
`post_source_retention_ratio` by itself did not (`rho=-0.0590`,
`[-0.2231, 0.1544]`). It is the terminal/source separation ratio when source
separation exceeds the benchmark epsilon; it is distinct from the trace's
`propagation_survival_ratio` field.

The next replay policy should therefore not reward a large total disturbance or
survival ratio alone. It should measure whether target-aligned effect remains
at the source and terminal states while unrelated drift stays bounded.

### Geometry currently looks like an effect signal, not a correctness signal

Excess turn angle and excess curvature were associated with continuous source
gain:

- turn angle: `rho=0.5215`, `[0.1371, 0.7303]`;
- curvature: `rho=0.4263`, `[0.1001, 0.6537]`.

They did not separate successful and unsuccessful final target-topic outcomes:

- successful-minus-unsuccessful turn angle: `-0.0090`,
  `[-0.0638, 0.0431]`;
- successful-minus-unsuccessful curvature: `-0.0538`,
  `[-0.1997, 0.0991]`.

For v0.2, geometry is a candidate signal for locating and sizing an
intervention, detecting propagation, or deciding when to inspect replay. Its
incremental predictive value has not yet been established. It is not promoted
to a correctness reward or a definition of better thinking.

### Efficiency and leakage form a promising objective pair

Source gain per unit control norm was negatively associated with unrelated-state
leakage (`rho=-0.7380`, `[-0.8615, -0.5444]`). This remains descriptive and is
partly case-family dependent, but it identifies a concrete next objective:
maximize target-aligned source/terminal gain per unit control and replay work,
subject to an explicit leakage penalty.

## Next algorithm hypothesis: dual-route EBRT

The first algorithm candidate produced by v0.2 is a two-role revision policy:

1. **Semantic route:** identify the invalidated premise and define the revision
   target from visible evidence.
2. **Control route:** choose one or more intervention points using features
   available at decision time, such as a validated predictor of the restricted
   source-projection leverage and explicit compute cost.
3. **Joint revision:** preserve an auditable semantic-anchor edit while allowing
   a bounded control booster at a different state when it improves downstream
   survival.

Propagation, terminal gain, and leakage are known only after candidate replay;
using them directly to route would be oracle leakage. Offline all-candidate
rollouts may define an oracle upper bound or training labels, but a deployable
policy must freeze a predictor that uses only decision-time features.

This candidate is not implemented or claimed as better in v0.2. Its next
experiment has two distinct levels:

1. **Decision-point shadow evaluation:** freeze the current D-arm prefix and
   event, then compare candidate actions without letting an earlier alternative
   rewrite the later candidate set. This estimates local choice quality.
2. **End-to-end policy evaluation:** rerun each policy from the start. For
   sequential events, recompute candidates and any leverage feature after every
   accepted revision; otherwise the mapping is stale.

The policy arms must include semantic-only, source-projection-leverage-only,
semantic plus leverage booster, and semantic plus sham/random booster. Total
top-k, control norm, optimizer budget, and replay work must be matched so that a
dual route does not win merely by receiving another control slot. Online probe
generator calls, replay, and wall time count toward the compute frontier.
Single-event cases are the primary clean test; sequential cases are a separate
recomputed-policy stress test.

Policy selection must use a new case-family holdout rather than the same 48
discovery cases. Primary endpoint, noninferiority margin for target-topic
success, leakage/compute guardrails, and multiple-comparison rule are fixed
before evaluation. Promotion requires improved source/terminal target gain or
compute efficiency without reducing target-topic success or increasing
unrelated drift.

## Promotion gates for algorithm changes

Instrumentation fields become router or revision-policy features only after
passing all relevant gates.

1. **Mathematical sanity:** geometry fixtures cover straight lines, turns,
   reversal, translation, orthogonal rotation, and zero-speed points.
2. **Counterfactual integrity:** pre-replay prefixes are identical and a later
   event-local mirror retains all earlier committed revisions.
3. **Negative controls:** stable, sham-zero-control, random-route, and
   gold-semantic-route cases remain distinguishable.
4. **Incremental value:** the candidate signal predicts held-out useful gain or
   leakage after conditioning on obvious cost and magnitude variables.
5. **Capacity-matched value:** semantic, control-only, dual-route, and
   sham/random-booster arms share control norm, optimizer, and replay budgets.
6. **Runtime value:** a frozen policy improves a predeclared outcome or compute
   frontier on a new case-family holdout; visualization alone is not a promotion
   result.

## Model boundary

The semantic adapter consumes visible text or structured observations and emits
versioned, attributable semantic fields. It is not an interface to private
chain-of-thought or hosted-model hidden states.

The first adapter remains the deterministic structured source used by v0.1. A
GPT-5.6 adapter can later replace that explicit semantic boundary while reusing
the same trace, controls, and mirror comparisons.
