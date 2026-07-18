# EBRT v0.3 dual-route prospective experiment

## Status

EBRT v0.3 is a preregistered **terminal protocol/invariant rejection**, not a
performance result.

The policy, runner, endpoint, margins, fixtures, runtime, and one-shot rule were
committed and pushed before the holdout was opened:

- protocol commit: `5b88faaeb8b357d527d00c0c1cf29ee70d52b422`;
- policy SHA-256: `5797e87727b17853088272a74a8affac4610a4bcc195664ed047642e5bd9763c`;
- runner SHA-256: `1341585bb7e5e2d8f26b294b4aac9d7c110736290e69ccd694101f8c012dd91a`;
- lock SHA-256: `26b1d7266c00babf583052b7fe592f9401a57a21362394631a8f84336c1953f4`;
- terminal ledger SHA-256:
  `9d8e8813f3529606166e5ccd73b3c95fb2448b1dce677043e1b2c6f0af6c36b5`.

Attempt 1 terminated on a predeclared structural assertion during the separate
native-cost frontier. The canonical ledger records
`failed_terminal_new_policy_version_required` and `rerun_permitted: false`.
No normal v0.3 result bundle was written, and the ledger contains no outcome
rows. There are therefore no reportable endpoint estimates, confidence
intervals, guardrail results, or policy-promotion decision.

## Why v0.3 existed

v0.2 found that semantic relevance and one narrow source-projection-leverage
measurement need not select the same prior state. That observation nominated a
two-role reasoning policy:

1. a semantic anchor defines what premise or belief is being revised;
2. a control anchor defines where a bounded intervention is applied.

v0.3 implemented that hypothesis prospectively. Its purpose was to learn
whether this separation produces a stronger reasoning algorithm, not merely to
make public claims easier to qualify.

## Frozen comparison

All primary arms used route width `K=2`, 32 Adam steps, learning rate `0.08`,
the same event and per-step control caps, and the same matched prefix-only
finite-difference probe and replay floor.

| Arm | Objective anchor | Two control sites | Role |
| --- | --- | --- | --- |
| S2 | semantic rank 1 | semantic top 2 | semantic control |
| L2 | leverage rank 1 | leverage top 2 | control-only diagnostic |
| D2 | semantic rank 1 | semantic rank 1 plus best distinct leverage site | dual-route candidate |
| SR2 | semantic rank 1 | semantic rank 1 plus deterministic random distinct site | sham booster control |
| G2 | annotated gold rank 1 | gold rank 1 plus best distinct leverage site | privileged diagnostic |

The primary population contained 48 single-event cases from 12 unseen
families. Twelve stable cases formed a separate no-event guardrail, and 16
two-event cases from four other families formed a separately gated sequential
stress test. The primary endpoint was terminal target-distance gain after one
to three post-event observations. Promotion required both D2-S2 and D2-SR2 to
clear a fixed `+0.02` margin as well as target, all-topic, leakage, compute,
stable-case, and structural guardrails.

The annotated target was visible to every deployable arm because it was the
structured runtime revision target. Only G2 received the privileged annotated
anchor location.

## Holdout controls

Before the one-shot run:

- the frozen v0.1/v0.2 source hashes and all v0.3 source and fixture hashes
  matched the lock;
- the exact Python, PyTorch, operating-system, machine, device, and dtype lock
  matched the runtime;
- policy and benchmark self-tests, Ruff, and bytecode compilation passed;
- a DEV-only epsilon audit retained the full and top-two leverage ranks for all
  24 decisions at `1e-4`, `1e-3`, and `1e-2`;
- two DEV-only quick runs produced byte-identical bundles with fingerprint
  `3c56e5ca1397aa4e3a77c5c90f3aca7c919a6f5d13f89b8cf32b75e9a4b67ed1`;
- the quick path executed zero holdout and zero sequential policy rows;
- adversarial checks rejected a missing locked source, runtime drift, alternate
  full policy/lock inputs, and fixture-override drift;
- the canonical ledger and full output directory did not yet exist.

One primary family that had been used for an operational smoke before locking,
and all earlier sequential smoke families, were removed and regenerated with
new identifiers, topics, text, and values before the final fixture hashes were
locked.

## Attempt 1 terminal result

The public protocol commit was pushed first. The exact one-shot command was:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 benchmark_dual_route_v0_3.py full --no-progress
```

The run exited with code `1` at the separate native-cost phase:

```text
AssertionError: native selected-min replay changed matched outcome:
('holdout_dual_repeated_stream_00', 0, 'S2')
```

The assertion compared a fingerprint over committed events, control tensors,
final states, and decoded output. It establishes that at least one exact policy
outcome field changed. It does not establish whether task quality improved or
degraded, and it does not identify which field first diverged.

The matched arm matrix had executed in process, but the runner writes its
deterministic bundle only after the native frontier and all validations finish.
No matched rows were persisted. Post-treatment recovery or selective reporting
would violate the frozen one-shot rule, so v0.3 is not rerun and no partial
quality statistic is reconstructed.

## What the failure discovered

The rejected invariant treated the native replay start as though it changed
only cost, while the implementation reused that same value for a second role.

Matched mode replays from the minimum eligible candidate. Native mode replays
from the minimum selected control site. In v0.3, `replay_floor` enters two
different parts of the implementation:

1. it sets the physical point where recurrent recomputation begins; and
2. it also sets the support of the `trajectory_anchor` loss term, which averages
   state deviation over `states[replay_floor:]`.

For the failing S2 case, static route evaluation gives five candidates at
steps `(0, 2, 4, 6, 8)` and semantic controls `(2, 4)`. Matched mode therefore
averages the anchor loss over 11 states from step 0, while native mode averages
the same suffix drift over nine states from step 2. The native regularizer is
`11/9` as strong. Equal semantic objectives and selected control sites thus
produce different gradients, Adam checkpoints, controls, states, or decoded
outputs.

Physical suffix replay can still be a cost-only optimization if it reuses the
same exact incoming state and leaves the mathematical objective unchanged. The
v0.3 failure shows that **execution replay start and trajectory-anchor loss
horizon had been conflated**. Under that coupling, the loss horizon changed
with a cost setting and thereby changed the reasoning policy.

The stronger factorization suggested by this failure is:

```text
semantic objective x control sites x trajectory-anchor loss horizon
```

This is useful algorithm discovery. A future EBRT router should decide not only
what belief is invalidated and where to intervene, but also over which states a
trajectory-deviation penalty should constrain the revision. Physical execution
replay start remains a separate optimization variable that is cost-only only
when exact outcome equality holds under a fixed mathematical objective.

## What remains supported

The following narrow statements remain supported:

- the five frozen v0.3 policies execute and close their deterministic generator
  and backward accounting on DEV fixtures and self-tests;
- matched arms have equal configured route capacity, probe, replay, optimizer,
  and norm budgets;
- the protocol was frozen and publicly timestamped before attempt 1;
- attempt 1 falsified the universal matched/native exact-outcome invariant for
  at least one holdout case;
- the one-shot guard failed closed and preserved a terminal audit ledger.

The following statements are **not** supported:

- D2 is better than, worse than, or equivalent to S2 or SR2;
- either co-primary contrast or any guardrail passed or failed;
- selected-min replay reduces compute without changing quality;
- the sequential dual-route policy is supported;
- this structured mechanism improves an LLM or natural-language reasoning.

## Clean v0.3.1 experiment

Any correction requires a new policy version, a new ledger, and entirely fresh
holdout families, identifiers, topics, text, and values. The consumed v0.3
holdout cannot be reused for promotion.

The smallest clean next design has two explicitly separated lanes:

1. keep the capacity-matched D2-S2-SR2 quality comparison on a common replay
   floor;
2. for a pure cost lane, split `execution_replay_floor` from
   `trajectory_anchor_floor`, keep the latter fixed at the matched minimum
   candidate, and retain exact outcome equality as a fail-closed invariant;
3. add a DEV regression case where the semantic top two omit the oldest
   candidate, proving route equality, exact outcome equality, and reduced
   replay work under the separated implementation;
4. separately run a DEV-only causal factorial that varies
   `trajectory_anchor_floor` while semantic objective, control sites, and
   `execution_replay_floor` stay fixed, allowing outcomes to differ and
   measuring terminal gain, propagation, leakage, and control behavior;
5. if a trajectory-anchor horizon policy enters a new holdout, name it as a
   distinct end-to-end policy; keep any execution-floor cost optimization in
   the exact-equality lane rather than coupling the two factors again;
6. retain sequential evaluation as a separate gate after a single-event result.

This design keeps v0.3 immutable while turning its stopping condition into a
new causal experiment about trajectory-loss support.

## Reproducibility and artifact boundary

- `policy_lock_v0_3.json` is the frozen protocol.
- `artifacts/.dual_route_v0_3_holdout_ledger.json` is the canonical terminal
  attempt record.
- `dual_route_policy_v0_3.py` and `benchmark_dual_route_v0_3.py` remain exactly
  the files hashed by the lock.
- There is intentionally no `artifacts/benchmark_dual_route_v0_3/` result
  bundle. Its absence is evidence that the runner stopped before validated
  bundle publication, not an omitted successful result.

The self-tests and DEV-only quick path remain inspectable, but `full` must not
be rerun for v0.3. A new full experiment belongs to v0.3.1 with new preregistered
inputs.
