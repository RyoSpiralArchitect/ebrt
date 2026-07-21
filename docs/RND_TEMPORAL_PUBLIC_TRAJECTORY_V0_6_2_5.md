# EBRT Runtime Preview 4 — zero-control identity and diagnostic separation

Status: network-zero product-runtime successor to protocol `v0.6.2.4`.
Historical artifacts and `ebrt.py` remain unchanged.

## Why this successor exists

Preview 3 used `sigmoid(u_t)` as the proposal-admission gate. Therefore
`u_t = 0` admitted one half of every event-bearing proposal. Its so-called
neutral trajectory was not the unmodified forward trajectory. Preview 3 also
compared the accepted temporal placement with a reversed sham whose L2 norm
and value multiset matched, while its smoothness term still included forced
zeroes at ineligible sites. Finally, that local comparison was incorrectly
required to be favorable before the product could call the provider.

Preview 4 repairs those three boundaries without changing any sealed result.

## Zero-control identity

The frozen public recurrence first computes the same decayed state as before.
It now admits the typed public proposal through a bounded residual gate:

```text
decayed_t = F(state_(t-1))
state_t   = decayed_t + u_t * (proposal_t - decayed_t)
```

The accepted vector retains the global `L2 <= 0.25` projection. Consequently,
`u_t = 0` is exactly the unmodified forward recurrence and admits none of the
event proposal. This is tested independently from the older no-event identity
sentinel: a typed event may exist while zero control remains a proposal no-op.

## Matched temporal sham

Smoothness is now defined over adjacent eligible temporal-control sites:

```text
L_smooth = lambda * sum_j (u_(j+1) - u_j)^2
```

Ineligible evidence is outside the controller domain instead of being treated
as an intervening zero-valued control. Reversing accepted values over the
eligible sequence therefore preserves:

- the signed value multiset;
- L2 norm;
- control regularization;
- eligible-domain temporal smoothness.

The receipt seals those checks, the two local objectives, their margin, and a
`POSITIVE`, `NON_POSITIVE`, `UNAVAILABLE_DEGENERATE`, or `INVALID_GEOMETRY`
status. It makes zero provider calls.

## Product gate versus research diagnostic

Product execution still requires actual-Before binding, chronological forward
execution, exact zero-control identity, one finite backward pass, finite-
difference agreement, objective and path descent, bounded controls, exact
forward replay, stable-axis identity, deterministic compilation, provider
schema delivery, and public lineage integrity.

Whether exact placement beats the matched sham is not in either product check
set. The diagnostic is returned and independently rederived, but
`product_gate_participation` is always `false`. A `NON_POSITIVE` local contrast
therefore does not prevent a valid revision program from executing.

## Control responsibility

The provider-visible reinspection allocation is
`softmax(abs(u) / temperature)`. The backward pass therefore allocates where
and how much to reinspect. `SUPPRESS` and `PRESERVE` are allowlisted operations
compiled from the typed invalidation/stability event; their semantics are not
inferred from the sign of the gradient.

## Human-readable output surface

The Reasoning IDE now shows the concrete user prompt and a readable projection
of the bound structured Before fields and regenerated After fields. The
contaminated hackathon fixture asks:

```text
Which single final-build priority should Team Spiral choose to maximize its
chance of winning? Follow the latest valid judging guidance. Answer POLISH or
PROVE.
```

It renders the public decision change as:

```text
No revision applied: POLISH — Prioritize additional UI polish; center the demo on polished screens.
Apply Revision result: PROVE — Prioritize end-to-end proof; center the demo on a live reasoning diff.
```

This projection is deterministic UI copy over public fields, not a second model
call or hidden rationale.

## Network-zero evidence

`python3 ebrt_live.py self-test` covers the new identity, matched geometry,
diagnostic tamper detection, diagnostic/product separation, finite differences,
generic topology, idempotency, relay limits, HTTP boundaries, sealed-demo
operation, and exact preservation of the historical v0.6.2.1 artifact.

No new hosted comparison is claimed here. Semantic correctness, provider
uptake, counterfactual output effect, causal superiority, and general reasoning
improvement remain `NOT_ASSESSED`.
