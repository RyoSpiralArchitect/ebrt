# EBRT

**Backward Credit Assignment for Test-Time Revision**

EBRT treats reasoning as a **revisable computation**, not merely an irreversible token prefix. When late evidence invalidates an earlier premise, EBRT assigns credit backward over an *explicit public trajectory*, compiles bounded controls, and re-executes the affected computation. The generator is an adapter, **not the definition** of the method.

```text
forward public trajectory
        ↓ late event
trajectory loss + backward credit
        ↓ bounded control
typed revision program
        ↓ replay / regeneration
revised public output + independent checks
```

## Mechanism in one view

For an adapter-supplied public trajectory, bounded controls (u_t) act on declared transitions:

$$
h_t = F_t(h_{t-1}, e_t, u_t), \qquad
u^{+} = \Pi_{\mathcal U}\!\left(u-\eta\nabla_u J(h_{1:T},u)\right).
$$

The core **replays** the public trajectory using the projected controls, then compiles the resulting credit into a public operation. It does not infer `SUPPRESS` or `PRESERVE` semantics from gradient signs.

| Boundary | Responsibility | Observable artifact |
| --- | --- | --- |
| **StateAdapter** | Admit a typed, detached public trajectory | Explicit states, event, control basis |
| **EBRT Core** | Forward recurrence, loss, one real backward pass, budgeted replay | Credit and trajectory receipt |
| **ActuatorAdapter** | Enforce required evidence coverage; compile the bounded intervention | `REINSPECT / SUPPRESS / PRESERVE` program |
| **ModelAdapter** | Run local open-weight or hosted generation beyond stop-gradient | Generated answer and declared supports |
| **Observer** | Separate mechanical, structural, and semantic contracts | Diff, integrity and result grades |

[Mechanism details and equations](docs/mechanism/README.md) · [Model adapter protocol](docs/MODEL_ADAPTER_PROTOCOL.md) · [Core thesis](docs/EBRT_CORE_THESIS.md)

## Run it

Network-zero core conformance (Python 3.11+, PyTorch):

```bash
python3 -m pip install -r requirements-core.txt
python3 ebrt_core.py self-test
python3 ebrt_demo.py
```

The one-command demo shows a real public `backward()`, bounded credit, revised trajectory, and compiled operation. **Its two generation arms use a fixed scripted reply**, so it does not demonstrate model uptake or output improvement.

For actual local generation, the reference adapter uses an exact MLX open-weight snapshot. The standard single-lane path is `ebrt_engine.RevisionEngine` with coverage-first compilation; other adapters implement the same interface. See [Quickstart](docs/quickstart/README.md) for installation, local E2E, optional hosted comparison, and runnable studies.

## What is demonstrated

**Mechanism:** v0.7.1 implements a literal zero-control identity, float64 backward and finite-difference checks, L2 projection, deterministic replay, and one local open-weight generation. v0.8.0 extends the public control block to multiple lanes with one joint backward pass; the verified local case uses **one shared Mistral model**, not independently demonstrated heterogeneous-model benefit. [Details](docs/mechanism/README.md)

**Generation and control:** multiple sealed local/hosted studies distinguish complete compiler coverage from provider uptake. A full program can be compiled and delivered while the generator ignores an obligation; in other cases, direct generation is already correct. [Study archive](docs/experiments/README.md)

**Revision and search:** a separate graph-coloring repair series tests actual gradient feedback and bounded repair trajectories. On three reused 24/36/48-vertex development cases at 2,048 state evaluations per run, multistart with the shared gradient-local-repair continuation found minimal repairs in **9/9** trials for each prior, versus **6/9** for each PUCT prior. This does *not* isolate a gradient benefit or establish general superiority. [Study](docs/RND_PUCT_MULTISTART_STUDY.md)

**Live product history:** the earlier Cloudflare/hosted Apply Revision demonstration is preserved as a historical product branch. Its acceptance artifacts do not redefine the model-agnostic core. [History](docs/repository/README.md) · [Build Week submission](SUBMISSION.md)

## What remains open

The central scientific question is **when nonlocal backward credit changes a decision that immediate local feedback cannot distinguish**. Current public-control experiments establish executable optimization and adapter boundaries, but do not establish general causal or reasoning-quality improvement.

The public trajectory is **not** a reconstruction of a model's private reasoning. EBRT does not backpropagate through a hosted model, JSON, token sampling, attention, or KV cache. Surrogate descent, actuator uptake, and answer quality are separate endpoints.

## Documentation

Start with the [documentation guide](docs/README.md), then [research roadmap](docs/ROADMAP_MODEL_INTERFACE_CORE.md), [repository map](docs/repository/README.md), or [experimental archive](docs/experiments/README.md). Closed v0.1–v0.6 studies, including null results and historical source locks, remain preserved.

Licensed under [Apache-2.0](LICENSE).
