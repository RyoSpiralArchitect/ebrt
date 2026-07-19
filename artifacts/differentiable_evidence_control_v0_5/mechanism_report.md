# EBRT v0.5.0 Differentiable Evidence Control — Mechanism Evidence

Status: `COMPLETE_MECHANISM_ONLY_NETWORK_ZERO`

This is a deterministic, network-zero mechanism bundle over two frozen
synthetic public semantic graphs. It contains no provider generation or
downstream reasoning-quality evaluation.

## Locked mechanism result

| Fixture | Event | Status | Backward calls | Objective before | Objective after |
| --- | ---: | --- | ---: | ---: | ---: |
| `route_code_supersession_public_graph_dev_v0_5` | yes | `ACCEPTED_LOCAL_CONTROL` | 120 | 1.610683159073 | 0.05931580595 |
| `route_code_no_event_public_graph_dev_v0_5` | no | `NO_EVENT_IDENTITY` | 0 | 0.0 | 0.0 |

The event fixture produced 2 boost, 1 suppress, and 4 preserve projections. The no-event fixture remained exact identity with zero backward calls.

## Numerical checks

The core self-test covered all five locked loss components plus the weighted total with central finite differences. Maximum absolute error: `2.4067525750126606e-10` (tolerance `2e-08`).

Control gates use `g=2*sigmoid(u)`, are projected in stable `ordinal,evidence_id` order, and cross a non-differentiable canonical JSON boundary after local optimization.
Adding 8 neutral, edge-less nodes changed every original gate by at most `2.220446049250313e-16` (tolerance `1e-14`).

## Lineage boundary

- v0.1: historical differentiable mechanism reference only; not an optimization input.
- v0.4.1: historical aperture observation reference only; not an optimization input.

Neither lineage file is loaded into the graph, loss, gradient, or control projection.

## Byte-reproduction runtime

Python `3.13.13`, PyTorch `2.11.0`, `Darwin 25.2.0 arm64`.

Byte identity is checked within this recorded runtime; no cross-runtime numerical identity is claimed.

## Claim boundary

- The controller uses real local autograd only inside a frozen one-hop public surrogate.
- The squared-L2-sum control penalty is invariant to eight disconnected neutral padding nodes within the locked 1e-14 tolerance on the built-in synthetic graph.
- The fixture graph topology, signed effects, event scope, invalidation, and replacement targets are synthetic oracle annotations, not learned semantics.
- No separately supplied downstream grader verdict, final-answer artifact, provider output, or final generation enters the controller.
- The v0.1 implementation and v0.4.1 manifest are lineage references only and are not empirical evidence for this mechanism result.
- Byte-identical artifact reproduction is evidenced only for the runtime recorded in the manifest, not across arbitrary Python, PyTorch, operating-system, or hardware versions.
- This lock does not support a hosted-model reasoning-improvement, causal, efficiency, or production-readiness claim.
