# EBRT documentation

The root [README](../README.md) is the short research-and-engineering entry point. Detailed material is organized by the question a developer is trying to answer:

| Read first | For |
| --- | --- |
| [Quickstart](quickstart/README.md) | Commands, local MLX setup, network-zero demos, and runnable canaries |
| [Mechanism](mechanism/README.md) | Equations, backward/control contracts, state/model/actuator adapters, and claim boundaries |
| [Runtime](runtime/README.md) | Coverage-first single-lane engine, budgeted and dependency-aware reinspection, non-unique solutions |
| [Experiments](experiments/README.md) | Versioned studies, controls, failures, sealed artifacts, and what each result does *not* establish |
| [Repository guide](repository/README.md) | Active paths, frozen v0.1–v0.6 history, roadmap, and origin |
| [Core thesis](EBRT_CORE_THESIS.md) | Latent north star and the formal adjoint/control formulation |
| [Adapter protocol](MODEL_ADAPTER_PROTOCOL.md) | Provider-neutral boundaries and conformance |
| [Roadmap](ROADMAP_MODEL_INTERFACE_CORE.md) | Current admitted capabilities and open research gates |

Each migrated chapter retains the underlying historical prose and links, rather than silently rewriting results. All public numeric comparisons are conditional on their recorded protocols.
