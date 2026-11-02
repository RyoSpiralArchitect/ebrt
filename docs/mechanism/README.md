# Mechanism, mathematics, adapters, and boundaries

This technical specification is redistributed from the former root README. The EBRT core is model-interface-agnostic; its public trajectory is not private chain-of-thought. For the motivating derivation see [EBRT core thesis](../EBRT_CORE_THESIS.md).

## What the core owns

[`ebrt_engine.py`](../../ebrt_engine.py) owns the standard single-lane orchestration
and coverage-first actuator. [`ebrt_core.py`](../../ebrt_core.py) retains the verified
backward mechanism, adapter types, and historical reference engines.

```text
RevisionTask
  -> StateAdapter
       explicit differentiable trajectory
  -> EBRT Core
       objective + backward credit + bounded control + replay
  -> ActuatorAdapter
       public REINSPECT / SUPPRESS / PRESERVE program
       STOP GRADIENT
  -> ModelAdapter
       local open-weight model or hosted API
  -> Observer
       structural receipt + optional post-run contract
```

In compact notation, for generator interface `m`:

\[
\tau_m = S_m(x,e), \qquad
c_m = \operatorname{EBRT}(\tau_m,\mathcal L,B),
\]

\[
a_m = A_m(c_m), \qquad
y'_m = M_m(x,a_m).
\]

EBRT differentiates through a detached, core-owned copy of \(\tau_m\), not
through the state adapter that produced it or through \(M_m\). The current
public protocol validates the adapter output as CPU `torch.float64`, binds the
task-owned target, event index, decay, learning rate, and control budget, then
records the exact typed state-adapter scales in the core receipt and severs any
incoming autograd history before optimization. A future admitted latent
trajectory needs an explicit protocol version rather than silently crossing
this boundary.
All public numeric task and receipt fields are actual JSON numbers; strings and
booleans are rejected rather than coerced.

The engine attributes `real_backward_executed_once` only to the exact bundled
core implementation and its module-load original method, checked before and
after execution. The original callable is captured in the engine method closure
rather than retained in a writable module symbol. Its immutable code object is
captured separately and executed through a private function copy. The engine
rejects class replacement, instance-level method shadowing, function-code
mutation, and simultaneous rebinding of lookalike module symbols. An injected
core receipt is still structurally validated, but cannot promote a replay into
a claim about the current run. Independently, every engine call attaches a
run-local, forward-value-neutral autograd probe to the public target. Its
expected gradient is computed from the declared EBRT objective, and the actual
backward must fire it exactly once with that value. An unrelated traversal such
as `target.sum().backward()` therefore cannot validate a replayed receipt.
These are executable conformance checks, not a Python process sandbox; code
with arbitrary interpreter-memory mutation is outside the runtime trust model.

## v0.7.1 — single-trajectory revision

The bundled public trajectory has three explicit axes:

- `revision`: movement toward the event-consistent terminal state;
- `invalidation`: propagation of a typed correction;
- `stability`: information that must remain unchanged.

For bounded controls \(u_t\), the forward recurrence is intentionally small:

\[
h_t = \rho h_{t-1} + e_t + \tanh(u_t)b_t.
\]

Therefore \(u=0\) is a literal no-op over the declared forward trajectory. A
trajectory loss supplies terminal, path, smoothness, and control terms. EBRT
executes one `torch.float64` backward pass, verifies selected gradients against
central finite differences, projects the proposed control into an L2 budget,
and replays the trajectory.

The compiled actuator does not pretend that a gradient contains natural
language semantics. Responsibilities remain separate:

| Layer | Responsibility |
| --- | --- |
| Backward pass | assign where and how much to reinspect |
| Typed event compiler | provide allowlisted `SUPPRESS` and `PRESERVE` semantics |
| Model adapter | regenerate from complete public context and the full quantitative actuator |
| Observer | check public structure and, when supplied, a post-run contract |

Only non-correction rows with positive realized control can enter the
credit-first reinspection list. The typed correction remains mandatory; a
zero-credit padding row cannot change provider-visible evidence order.

The post-run contract never enters the model request. It is computed only after
generation, then its exact validated fields and fingerprint are sealed beside
the resulting grade so an archived semantic `PASS` remains independently
auditable.

## v0.8.0 — joint trajectories

v0.8 lifts the same mechanism into a block of namespaced lanes:

\[
\mathcal L_{joint}
= \sum_k w_k\mathcal L_k
+ \gamma\sum_{i<j}\|P h_i-P h_j\|^2.
\]

The implementation:

1. sorts and namespaces the lanes;
2. concatenates their admitted controls;
3. executes **one** backward pass over the joint block;
4. enforces per-lane and global control budgets;
5. compiles one actuator per lane;
6. invokes each declared model adapter; and
7. merges public answers deterministically.

The real local v0.8 check currently runs two different trajectory adapters and
prompt policies through one shared Mistral runtime. That establishes joint
multi-lane execution, not heterogeneous multi-model performance. Distinct
provider/model effects remain `NOT_ASSESSED` until two real model IDs run under
a locked comparison.

## Adapter contract

| Interface | Required edge | Current implementation |
| --- | --- | --- |
| `StateAdapter` | `build(task, lane_id) -> TrajectoryEnvelope` | `TypedPublicStateAdapter` |
| `ActuatorAdapter` | `compile(task, credit, lane_id) -> ActuatorProgram` | mainline `CoverageFirstActuator`; historical `PublicRevisionActuator` |
| `ModelAdapter` | `generate(task, program, prompt_policy) -> ModelResult` | `MLXLocalAdapter`, `CallableModelAdapter` |
| Observer | sealed mechanism, structural, and semantic receipts | mainline `ebrt_engine.RevisionEngine`; historical single/joint engines |

`CallableModelAdapter` is the provider-neutral binding edge for an SDK or
another local runtime. The original v0.7.1/v0.8.0 hosted shape is covered by
network-zero conformance. The separate v0.8.6 runner now exercises a real
hosted-provider boundary on the known synthetic fixture; its receipts and
per-arm grades describe that execution. Frozen core capability labels are
unchanged by this standalone integration.

Run `python3 ebrt_core.py capabilities` for the machine-readable boundary.

## Claim boundary

Implemented and verified:

- an explicit differentiable public trajectory;
- real local backward credit assignment and bounded control;
- a literal zero-control identity;
- deterministic compilation into a public revision actuator;
- one real local open-weight regeneration;
- one joint backward over multiple lanes and two real local generations;
- independent structural and post-run verification receipts.

Not established:

- access to, reconstruction of, or editing of private chain-of-thought;
- gradients through a language model, hosted API, JSON, or sampled text;
- equivalence between the public trajectory and model-native hidden states;
- causal superiority of EBRT over an uncontrolled or textual revision;
- general reasoning-quality improvement;
- heterogeneous multi-model benefit.

Surrogate descent, actuator uptake, generated-output quality, and causal effect
are separate measurements. A `PASS` in one category does not silently imply a
`PASS` in another.
