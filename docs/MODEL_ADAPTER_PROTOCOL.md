# EBRT Model Adapter Protocol

Protocol: **v0.7.1**
Joint composition: **v0.8.0**

This document specifies the boundary between the differentiable EBRT core and
a generator. It is intentionally smaller than any provider SDK.

## Boundary

```text
explicit trajectory
  -> EBRT backward credit
  -> bounded public control
  -> ActuatorProgram
       STOP GRADIENT
  -> ModelAdapter.generate(...)
  -> ModelResult
  -> structural verification
  -> optional post-run contract
```

The model adapter never receives a tensor from the autograd graph. The core
never assumes that a model exposes hidden states, logits, attention, KV cache,
or private chain-of-thought.

## Python contract

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
| `model_id` | Public model identity for receipt grouping |
| `interface_kind` | `deterministic_conformance`, `local_open_weight`, or `hosted_api` |
| `state_visibility` | `public_only` or an explicitly admitted `native_latent` surface |
| `differentiable_through_model` | Must be `false` for the current public/hosted protocol |

`ModelResult` contains one allowed answer, zero or more known public support
IDs, raw public text, the descriptor, a request fingerprint, latency, and a
logical-call count.

## Model-visible information

The invocation compiler may provide:

- the question and declared answer choices;
- complete public evidence;
- the compiled reinspection allocation;
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
`build_model_invocation`. The network-zero self-test checks this separation.

## Adapter obligations

A conforming adapter must:

1. preserve the supplied `ActuatorProgram` bytes semantically;
2. perform exactly one logical generation per invocation unless a separately
   declared protocol says otherwise;
3. return a declared answer choice;
4. return only known evidence IDs as active support;
5. exclude evidence compiled as invalidated support;
6. retain the correction as active support for this revision protocol;
7. report the public model and adapter identities; and
8. keep `differentiable_through_model=false` at a non-latent boundary.

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
- distinct IDs represented only by conformance doubles: `CONFORMANCE_ONLY`;
- distinct real local model IDs: `OBSERVED` protocol execution, still not a
  quality or causal-effect result;
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
