# EBRT Model Adapter Protocol

Protocol: **v0.7.1**
Joint composition: **v0.8.0**

This document specifies the boundary between the differentiable EBRT core and
a generator. It is intentionally smaller than any provider SDK.

## Boundary

```text
StateAdapter output
  -> validate task-owned trajectory fields
  -> detach and clone into core-owned CPU float64 state
  -> EBRT backward credit
  -> bounded public control
  -> ActuatorProgram
       STOP GRADIENT
  -> ModelAdapter.generate(...)
  -> ModelResult
  -> structural verification
  -> optional post-run contract
```

The state-adapter boundary and model-adapter boundary are both stop-gradient
boundaries. The engine validates lane, adapter, axes, evidence, roles, event
index, target, decay, learning rate, control budget, tensor shape, dtype, and
device before optimization. It then detaches and clones all admitted tensors;
adapter-owned autograd history cannot receive gradients from the EBRT backward
pass. The model adapter never receives a tensor from the new core-owned graph.
The core never assumes that a model exposes hidden states, logits, attention,
KV cache, or private chain-of-thought.

The current protocol admits only detached CPU `torch.float64` public
trajectories. A model-native latent/device boundary is a research target and
requires a new protocol version with an explicit gradient policy.

The current actuator protocol is intentionally closed: after any
`ActuatorAdapter` returns, the engine recompiles the canonical public program
from the sealed backward receipt and requires exact equality. Alternate
actuator semantics require a new protocol version rather than silently changing
the operation behind a structural `PASS`. The core first takes a canonical deep
snapshot of its sealed receipt and gives the adapter only a separate clone;
single and joint compilation therefore cannot rewrite the receipt that is
validated or emitted.

An injected optimization core is also a checked boundary. Before actuation, the
engine retains an immutable admitted envelope and passes the core a separate
working clone. It then binds the sealed receipt to the admitted schema, lane,
state-adapter, axes, event index, budget, evidence rows, replayed trajectories,
losses, finite-difference diagnostics, the projected/backtracked update law,
and required checks. A core cannot mutate the validator's reference envelope,
and a resealed but inconsistent receipt cannot be promoted to engine `PASS`.

## Python contract

```python
class StateAdapter(Protocol):
    adapter_id: str

    def build(
        self,
        task: RevisionTask,
        *,
        lane_id: str,
    ) -> TrajectoryEnvelope: ...
```

The adapter may construct public trajectory values, but it may not redefine
task-owned optimization parameters. `event_index`, `target`, `decay`,
`control_budget`, and `learning_rate` must exactly match `RevisionTask`.
The admitted envelope also carries a canonical public state-adapter
configuration. The core receipt binds those exact typed transformation scales,
so two adapters with the same implementation ID but different trajectory
geometry cannot share an optimization identity.
Incoming tensors are copied and detached after conformance validation. The
admitted `control_basis` and its exactly matching `eligible_mask` remain the
authority for where the core can assign control; actuator compilation does not
silently restore eligibility from the pre-adapter task basis. The typed
correction is a required revision site in this protocol and must remain
eligible at admission; alternate correction semantics require a new version.

```python
class ModelAdapter(Protocol):
    descriptor: AdapterDescriptor

    def generate(
        self,
        task: RevisionTask,
        program: ActuatorProgram,
        *,
        prompt_policy: Literal["chronological", "credit_first"],
    ) -> ModelResult: ...
```

`AdapterDescriptor` declares:

| Field | Meaning |
| --- | --- |
| `adapter_id` | Unique implementation/configuration identity |
| `model_id` | Public model-and-weight identity for receipt grouping; cache-derived IDs include the snapshot revision |
| `interface_kind` | `deterministic_conformance`, `local_open_weight`, or `hosted_api` |
| `state_visibility` | `public_only` or an explicitly admitted `native_latent` surface |
| `differentiable_through_model` | Must be `false` for the current public/hosted protocol |
| `generation_config` | Canonically ordered public decoding settings |
| `generation_config_fingerprint_sha256` | Derived receipt identity for those settings |

`ModelResult` contains one allowed answer, zero or more known public support
IDs, raw public text, the descriptor, a request fingerprint, latency, and a
logical-call count. The runtime requires the exact public container and scalar
types: in particular, `logical_calls` is a non-boolean integer and latency is a
finite, non-boolean JSON number. Malformed adapter output fails structurally
without leaking a native type exception.

The reference MLX runtime derives `model_id` from a standard Hugging Face cache
snapshot as `repository@revision`. A model outside that layout must supply an
explicit revision-bearing identity; a filesystem path alone is not accepted as
weight identity because its contents can be replaced in place. Its descriptor
separately records and fingerprints `max_tokens`, seed, sampler temperature,
and chat-template generation mode, so two executions with the same weights and
adapter name but different decoding settings cannot share a configuration
receipt. An explicit identity cannot override a derivable cache identity; if
both are supplied, exact equality is required.

Automatic Hugging Face cache discovery follows the repository's `refs/main`
revision. When that reference is absent, exactly one complete snapshot is
required; multiple complete snapshots are rejected as ambiguous rather than
selecting one by directory-name order. An explicit `EBRT_LOCAL_MODEL` or
`--model` remains available when the caller intends a different snapshot. A
sharded snapshot is complete only when its index is valid and every referenced
`.safetensors` shard exists and is non-empty. Automatic discovery additionally
requires parseable `config.json` and `tokenizer_config.json`, a declared model
type, and at least one non-empty local tokenizer asset.

The engine recomputes the expected invocation before generation and requires
the returned request fingerprint and adapter descriptor to match that binding.
An adapter cannot substitute another request or model identity while retaining
structural `PASS`. Descriptor values are runtime-validated, and the current
protocol rejects any descriptor that claims a gradient crosses generation.

Core receipt replay validation is not an execution attestation by itself. The
current engine reports a backward execution only when the exact bundled single
or joint core and its module-load original method remain identical before and
after that call. The pinned original lives in the engine method closure rather
than a writable module-level reference. The closure separately retains its
immutable code object and invokes a private function copy. Instance-level
shadowing, function-code mutation, or simultaneous class/module-symbol
replacement is rejected alongside injected cores. Such cores can be validated
for conformance but cannot yield engine `PASS` from a previously captured
receipt.

## Model-visible information

The invocation compiler may provide:

- the question and declared answer choices;
- complete public evidence;
- the complete sealed actuator program, including reinspection allocation and
  signed control values;
- typed invalidated evidence to suppress;
- typed stable evidence to preserve; and
- an output schema.

It must not provide:

- the post-run expected answer;
- required or forbidden gold support sets;
- a grader verdict;
- a hidden correct closure ID;
- a gradient tensor; or
- credentials and private provider metadata.

The known fixture's `PostRunContract` is validated locally and withheld from
`build_model_invocation`. After generation, the exact contract is sealed into
the grade receipt; two passing grades under different contracts therefore have
different fingerprints. The network-zero self-test checks both separation and
receipt binding. The separately sealed task fingerprint includes the
controller's terminal target and every other task-owned trajectory parameter.

## Adapter obligations

A conforming adapter must:

1. preserve the supplied `ActuatorProgram` bytes semantically;
2. perform exactly one logical generation per invocation unless a separately
   declared protocol says otherwise;
3. preserve the native completion text and require exactly the declared
   two-line schema, with no surrounding prose or normalization that hides it;
4. return a declared answer choice, including a declared multi-word choice;
5. return only known evidence IDs as active support;
6. exclude evidence compiled as invalidated support;
7. retain the correction as active support for this revision protocol;
8. report the public model and adapter identities;
9. return the exact request fingerprint compiled by the engine; and
10. keep `differentiable_through_model=false` at a non-latent boundary.

Transport retry policy, provider receipts, cost, and rate limiting belong to a
concrete adapter and must remain distinguishable from EBRT mechanism status.

## Binding another runtime

`CallableModelAdapter` is the smallest conformance edge:

```python
adapter = CallableModelAdapter(
    descriptor=AdapterDescriptor(
        adapter_id="provider-config-v1",
        model_id="provider/model-name",
        interface_kind="hosted_api",
        state_visibility="public_only",
        differentiable_through_model=False,
    ),
    callback=lambda invocation: provider_generate(invocation["prompt"]),
)
```

The callback must return the public two-line response currently parsed by the
reference monolith:

```text
ANSWER=<declared choice>
SUPPORT=<comma-separated public evidence IDs>
```

A production adapter may replace that parser with a stricter structured-output
boundary while returning the same `ModelResult` semantics.

## v0.8 joint execution

Each `JointLaneSpec` binds one state adapter, one model adapter, one prompt
policy, and one positive lane weight. v0.8 executes one backward pass over the
joint trajectory block, compiles an actuator for each lane, calls each model
adapter, and merges only public results.

Receipt interpretation is strict:

- multiple lanes around one model ID: joint multi-lane execution;
- distinct model IDs under the current adapter-declared interface:
  `CONFORMANCE_ONLY`, even when adapters self-declare `local_open_weight`;
- `OBSERVED` heterogeneous execution requires a separately verifiable backend
  execution receipt and is not emitted by this protocol;
- any generator effect: `NOT_ASSESSED` until a locked matched evaluation.

## Current coverage

| Boundary | Status |
| --- | --- |
| Deterministic local/provider-shaped doubles | Network-zero conformance `PASS` |
| Apple-silicon MLX open-weight adapter | Real E2E `PASS` |
| Two lanes, one shared local Mistral model | Real E2E `PASS` |
| Two distinct real model IDs | Deferred |
| Hosted SDK with live credential | Deferred |
| Model-native latent actuator | Research target |
