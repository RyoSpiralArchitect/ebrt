# EBRT v0.6.3.2 live-r01 result

Status: **CONSUMED ONCE; COMPLETE; STOP ON POSITIVE-CONTROL CEILING**

This note records the one authorized v0.6.3.2 hosted replication block. It
does not replace the frozen network-zero preflight, relax its strict-AND gate,
or reopen this namespace for another call.

## Frozen execution identity

- authorization tag: `v0.6.3.2-live-r01-authorized`
- annotated tag object: `e7f4ca03ed04010cf2e399865950973fd066ca41`
- peeled execution commit: `dc8b344bb7ff05a7d9d0a8e967f1e0c1efc5bf8c`
- sealed order: `C -> Z -> D -> X / D -> X -> C -> Z`
- authorized and consumed calls: `8/8`
- attempt journal: eight `ATTEMPT_STARTED` rows and eight matching terminal rows
- attempt block: `COMPLETE_EXACT_EIGHT_TERMINALS`
- assessment: `ASSESSED`
- policy-lock fingerprint: `7cf24f5f9a57c3c8bf9d9b56d3dd2ae3cc7bafdbf7355bd0aec4d6a57d44af17`
- result fingerprint: `97634c76bfaf2b027368379d8ee7a5520a866c1a999e8686741577febaff7c52`

Exactly four blinded request payloads were reused across eight unique attempt
identities. The sole intentionally treatment-varying semantic payload field
was evidence order. Evidence rows, candidate closures, instructions, schema,
model settings, and budgets remained frozen.

## Observed public endpoints

| Position | Block | Arm | Selected closure | Frozen role |
| ---: | --- | --- | --- | --- |
| 1 | A | C | `K_8027291974` | alternative event-consistent |
| 2 | A | Z | `K_265e97f857` | aligned event-consistent |
| 3 | A | D | `K_265e97f857` | aligned event-consistent |
| 4 | A | X | `K_265e97f857` | aligned event-consistent |
| 5 | B | D | `K_265e97f857` | aligned event-consistent |
| 6 | B | X | `K_265e97f857` | aligned event-consistent |
| 7 | B | C | `K_8027291974` | alternative event-consistent |
| 8 | B | Z | `K_265e97f857` | aligned event-consistent |

Both blocks therefore produced the same preregistered classification:

- gradient placement: `GRADIENT_PLACEMENT_DIRECTIONAL`, because D selected
  aligned while geometry-matched C selected the alternative closure;
- positive control: `POSITIVE_CONTROL_CEILING`, because X and Z both selected
  aligned; and
- block terminal: `STOP_POSITIVE_CONTROL_CEILING_NOT_ASSESSED`.

The aggregate classifier independently returned:

- gradient placement: `REPLICATED_DIRECTIONAL`;
- positive control: `REPLICATED_CEILING`;
- terminal decision: `STOP_REPLICATION_CEILING_NOT_ASSESSED`; and
- v0.6.4 network-zero preflight opened: `false`.

`ASSESSED` means the complete eight-terminal block was structurally eligible
and classified. The `NOT_ASSESSED` suffix means the actuator-promotion claim
cannot be evaluated under the preregistered positive-control ceiling; it does
not mean that calls or endpoints are missing.

The delayed semantic gold was unavailable during all provider calls and public
compilation. It loaded exactly once only after eight structurally valid
terminals existed.

## What the ceiling means

The D-versus-C public closure difference repeated after the two arms exchanged
serial positions. This narrows the fixed-position explanation attached to the
v0.6.3.1 observation. It is still one serial execution on one synthetic case
and does not eliminate provider or temporal drift.

The full observed geometry is `D = Z = X`, with only C selecting the
alternative closure. It therefore does not show that D improved over the
neutral Z arm. The same observation is compatible with sensitivity to the C
anti-placement rather than positive uptake of the D placement.

The frozen promotion contract also required X to select aligned while Z did
not. Here both selected aligned in both blocks. The positive contrast therefore
had no remaining headroom, so the strict conjunction was not assessed as a
replicated actuator gate. The directional D-versus-C observation cannot
override that preregistered ceiling.

Both observed closures are independently quality-valid and every arm returned
the same public answer, `JADE`. This result is about public closure selection,
not answer-quality improvement. It does not establish an attention effect,
hidden-state or KV-cache editing, a gradient through GPT, population
reliability, or general reasoning improvement.

The result is neither a null D-versus-C observation nor a promotion. The exact
safe summary is:

> A D-versus-C public evidence-order contrast repeated across two mirrored
> blocks on one fresh sealed synthetic case, while the required X-versus-Z
> positive contrast saturated at the aligned closure; the preregistered gate
> stopped without opening v0.6.4.

Per the frozen stop rule, there is no third block, alternate seed, replacement
case, relaxed gold, rescue call, or ninth call. This closes the actuator-
replication branch for the current submission and returns the project to the
Reasoning IDE and product-convergence path.

## Usage

| Metric | Observed |
| --- | ---: |
| API calls | 8 |
| Input tokens | 6,160 |
| Output tokens | 1,690 |
| Reasoning tokens | 964 |
| Total tokens | 7,850 |
| Aggregate provider latency | approximately 45.211 seconds |

## Artifacts

- [canonical live-r01 artifact](../artifacts/actuator_uptake_replication_v0_6_3_2_live_r01)
- [portable result verifier](../verify_actuator_uptake_replication_v0_6_3_2_live_r01.py)
- [frozen authorization protocol](RND_ACTUATOR_UPTAKE_REPLICATION_V0_6_3_2_LIVE_R01.md)
- [network-zero replication protocol](RND_ACTUATOR_UPTAKE_REPLICATION_V0_6_3_2.md)

Provider receipts and execution provenance remain operator-attested local
records, not provider-signed cryptographic proof. The authorization tag guards
the reviewed checkout but does not guarantee global exactly-once execution
across clones.
