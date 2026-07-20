# EBRT v0.6.3.1 live-r01 result

Status: **CONSUMED ONCE; COMPLETE; PROMOTE TO FRESH REPLICATION**

This note records the single authorized v0.6.3.1 hosted canary block. It does
not replace the frozen zero-call preflight or broaden the preregistered claim
boundary.

## Frozen execution identity

- authorization tag: `v0.6.3.1-live-r01-authorized`
- annotated tag object: `621d6ce5aca04629eefd1f0189635ee84b62e8da`
- peeled execution commit: `35b84895acb63298a8459dba1e9f3f2a47f4de0f`
- sealed order: `C -> X -> D -> Z`
- authorized and consumed calls: `4/4`
- attempt journal: four `START` rows and four terminal rows
- block status: `COMPLETE_EXACT_FOUR_TERMINALS`
- assessment status: `ASSESSED`
- result fingerprint: `131d64dfe74b99912d5e39b0fdd13d17c69eca0d1361b27a48e75887ec25b8e2`

The sole intentionally treatment-varying semantic field in the four provider
payloads was evidence order. The evidence chunks, candidate closure catalog,
instructions, schema, model settings, and budgets were frozen across arms.

## Observed public endpoints

| Position | Arm | Provider status | Selected closure | Public answer | Inspection adherence |
| ---: | --- | --- | --- | --- | --- |
| 1 | C | `COMPLETED` | `K_5c1377f2fc` | `VIOLET` | `true` |
| 2 | X | `COMPLETED` | `K_ba42ee466f` | `VIOLET` | `true` |
| 3 | D | `COMPLETED` | `K_ba42ee466f` | `VIOLET` | `true` |
| 4 | Z | `COMPLETED` | `K_f41cb3914f` | `VIOLET` | `true` |

The post-call classifier returned:

- positive channel: `CHANNEL_OPEN_DIRECTIONAL` because X selected the aligned
  closure while Z selected the mixed closure;
- gradient placement: `GRADIENT_PLACEMENT_DIRECTIONAL` because D selected the
  aligned closure while geometry-matched C selected the alternative closure;
- terminal decision: `PROMOTE_TO_FRESH_REPLICATION`;
- direct promotion to v0.6.4: `false`.

Semantic gold remained unavailable to provider execution and compilation. It
was loaded exactly once, only after all four arms had valid compiled terminal
records, to classify the completed block.

## Usage

| Metric | Observed |
| --- | ---: |
| API calls | 4 |
| Input tokens | 3,108 |
| Output tokens | 556 |
| Reasoning tokens | 194 |
| Total tokens | 3,664 |
| Aggregate provider latency | approximately 18.546 seconds |

## What this result does and does not say

This one block records a non-zero, directionally preregistered public endpoint
difference under the frozen position-only canary. It is enough to open a
separately sealed fresh replication.

It is not enough to attribute that difference causally to evidence order. The
arms ran once in the fixed serial order `C -> X -> D -> Z`, so treatment cannot
be separated from temporal or provider drift. There is one synthetic case and
one consumed block, with no population estimate. The result does not establish
answer-quality improvement, general reliability, hidden-state editing, a
gradient through GPT, or general reasoning improvement.

Accordingly, this result does not open UI work or v0.6.4. The next action is a
fresh, preregistered replication on a separately sealed case. Only a replicated
channel and directional D-versus-C placement effect can reopen the v0.6.4
scaffold-aperture decision.

## Artifacts

- [canonical live-r01 artifact](../artifacts/actuator_uptake_canary_v0_6_3_1_live_r01)
- [portable result verifier](../verify_actuator_uptake_canary_v0_6_3_1_live_r01.py)
- [frozen authorization protocol](RND_ACTUATOR_UPTAKE_CANARY_V0_6_3_1_LIVE_R01.md)
- [zero-call measurement-repair note](RND_ACTUATOR_UPTAKE_CANARY_V0_6_3_1.md)

The receipts and execution provenance remain operator-attested local records,
not provider-signed cryptographic proof. The authorization tag guards the exact
reviewed checkout but does not provide global exactly-once semantics across
clones.
