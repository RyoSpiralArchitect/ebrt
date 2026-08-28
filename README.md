# EBRT

**Backward Credit Assignment for Test-Time Revision**

EBRT is a model-interface-agnostic reasoning core. It turns a forward-only
reasoning episode into an explicit trajectory that can receive a late event,
assign bounded credit backward, compile a revision operation, and run the
affected computation forward again.

```text
forward trajectory
  -> late event
  -> backward credit assignment
  -> bounded intervention
  -> replay or regeneration
```

The current release has two executable layers:

- **v0.7.1:** one trajectory, one real local backward pass, one compiled
  actuator, and one real open-weight regeneration;
- **v0.8.0:** one joint backward block over multiple public trajectories,
  lane-specific actuators, real local generations, and deterministic merge.

The generator is an adapter, not the definition of EBRT. The bundled reference
backend is a local MLX model. Hosted APIs and other local runtimes can meet the
same interface without entering the autograd graph.

## Start here

### 1. Network-zero mechanism check

Requires Python 3.11+ and PyTorch.

```bash
python3 -m pip install -r requirements-core.txt
python3 ebrt_core.py self-test
python3 ebrt_core.py capabilities
```

`self-test` performs no network call. It checks the single-trajectory and joint
contracts, real reverse-mode autodiff, finite differences, control budgets,
zero-control identity, deterministic merge, lane-order invariance, task-owned
trajectory binding, admitted-core receipt replay, nonzero model-visible credit,
immutable actuator inputs, exact post-run contract receipts, and both
state-adapter and model-adapter stop-gradient boundaries.

### 2. Real local model

The reference adapter targets Apple silicon through MLX. Point
`EBRT_LOCAL_MODEL` at a complete local MLX snapshot:

```bash
python3 -m pip install -r requirements-local-mlx.txt
export EBRT_LOCAL_MODEL="$(hf download mlx-community/Mistral-7B-Instruct-v0.3-4bit)"

python3 ebrt_core.py local-e2e
python3 ebrt_core.py joint-local-e2e
```

If the Mistral snapshot is already in the standard Hugging Face cache, EBRT
discovers it automatically and the environment variable can be omitted.
Automatic discovery follows the repository's `refs/main` revision. If that
reference is absent while multiple complete snapshots exist, EBRT rejects the
ambiguous cache and requires `EBRT_LOCAL_MODEL` or `--model` explicitly.
For an indexed snapshot, every shard named by every weight map must exist and
be non-empty before the snapshot is considered complete. Automatic discovery
also requires non-empty, parseable model/tokenizer configuration and a local
tokenizer asset before handing a snapshot to MLX.
Cache-derived model identities include the snapshot revision so different
weight snapshots cannot collapse into one receipt identity. An explicit
`--model-id` cannot relabel a cache-derived snapshot: when both are present,
they must match exactly.
Cache identity is derived only for an exact snapshot root beneath a configured
Hugging Face hub, with a 40-hex revision, complete loader material, and the
standard symlink-to-blob layout. Each linked blob is streamed and checked
against its SHA-256 or Git-blob SHA-1 address before identity derivation. A
directory that merely imitates
`models--.../snapshots/...` is treated as an ordinary local directory and must
supply `--model-id` explicitly.
For a model stored outside that cache layout, pass a public receipt identity
explicitly with `--model-id provider/model@revision`. EBRT fails closed without
that revision-bearing identity rather than grouping replaceable weights by
their filesystem path. The MLX adapter also binds its seed, token ceiling,
sampler temperature, and chat-template mode into a separately fingerprinted
generation configuration in every model receipt.

The committed interface was verified locally with
`mlx-community/Mistral-7B-Instruct-v0.3-4bit`. The v0.7.1 integration fixture
produced:

```text
ANSWER=PROVE
SUPPORT=R6,R4,R2
```

with a strict post-run contract `PASS`. This is an end-to-end mechanism check
over a known synthetic fixture, not a claim of general reasoning improvement.
The committed sanitized receipt is
[`artifacts/model_interface_core_v0_7_1/local_mistral_e2e_r01.json`](artifacts/model_interface_core_v0_7_1/local_mistral_e2e_r01.json).

## What the core owns

The central file is [`ebrt_core.py`](ebrt_core.py). It contains the complete
active prototype rather than scattering the reasoning mechanism across a
framework.

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
| `ActuatorAdapter` | `compile(task, credit, lane_id) -> ActuatorProgram` | `PublicRevisionActuator` |
| `ModelAdapter` | `generate(task, program, prompt_policy) -> ModelResult` | `MLXLocalAdapter`, `CallableModelAdapter` |
| Observer | sealed mechanism, structural, and semantic receipts | `RevisionEngine`, `JointRevisionEngine` |

`CallableModelAdapter` is the provider-neutral binding edge for an SDK or
another local runtime. Its hosted shape is covered by network-zero conformance;
no hosted-provider E2E is claimed in v0.7.1/v0.8.0 because no credential was
present for this development gate.

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

## Repository map

### Active path

| Path | Role |
| --- | --- |
| [`ebrt_core.py`](ebrt_core.py) | v0.7.1/v0.8 monolith and CLI |
| [`requirements-core.txt`](requirements-core.txt) | network-zero core dependency |
| [`requirements-local-mlx.txt`](requirements-local-mlx.txt) | Apple-silicon local backend |
| [`docs/EBRT_CORE_THESIS.md`](docs/EBRT_CORE_THESIS.md) | mathematical and conceptual anchor |
| [`docs/MODEL_ADAPTER_PROTOCOL.md`](docs/MODEL_ADAPTER_PROTOCOL.md) | provider-neutral binding contract |
| [`docs/ROADMAP_MODEL_INTERFACE_CORE.md`](docs/ROADMAP_MODEL_INTERFACE_CORE.md) | evidence-labelled path beyond v0.8 |
| [`artifacts/model_interface_core_v0_7_1/local_mistral_e2e_r01.json`](artifacts/model_interface_core_v0_7_1/local_mistral_e2e_r01.json) | sanitized real local E2E receipt |

### Frozen research history

Root-level v0.1-v0.6.3.2 modules, `policy_lock_*.json`, reports, and artifacts
are retained as immutable research history. They include negative results that
shaped the current abstraction: a mathematically valid control surface can be
ignored by a generator, public lineage is not the same as control uptake, and
integrity closure is not method superiority.

The most useful historical entrypoints are:

- [`ebrt_monolith_v0_1.py`](ebrt_monolith_v0_1.py): original differentiable toy
  mechanism;
- [`ebrt.py`](ebrt.py): sealed Apply Revision acceptance engine;
- [`ebrt_live.py`](ebrt_live.py): frozen v0.6 live runtime;
- [`docs/ROADMAP_V0_6_PLUS.md`](docs/ROADMAP_V0_6_PLUS.md): pre-core roadmap and
  decision record;
- [`SUBMISSION.md`](SUBMISSION.md): historical Build Week presentation, no
  longer the project definition.

## Roadmap

The active roadmap is
[`docs/ROADMAP_MODEL_INTERFACE_CORE.md`](docs/ROADMAP_MODEL_INTERFACE_CORE.md).
The next scientific gates are:

1. two distinct real local model IDs behind the same protocol;
2. a hosted adapter E2E when credentials and policy are available;
3. external public control versus an admitted model-native latent actuator;
4. fresh matched evaluation of actuator uptake and output quality.

## Origin

EBRT began as a sketch in which a latent reasoning trajectory receives a
trajectory-level loss and backward revision before decoding. The Build Week
deadline compressed that sketch into a hosted-model runtime, an Inspector, and
strict public artifacts. Those components remain valuable, but the current
definition is broader: **the missing primitive is backward revision at
inference time**, independent of any particular provider.

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
