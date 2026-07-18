# EBRT v0.4.2 diagnostic closure — DEV report

Mode: `openai_live_contract_smoke`  
Four-arm runs: `2`  
Primary-endpoint-assessed four-arm runs: `2/2`  
All-output-completed four-arm runs: `2/2`  
Locked decision ready: `false`  
Revision-envelope conclusion: `not_assessed_incomplete_or_subset_run`  
Raw-aperture conclusion: `not_assessed_incomplete_or_subset_run`  
Next scaffold step: `complete_exact_locked_same_block_run`  
Nominal / attempted API calls: `28` / `28`  
Full-run launch ready: `true`

A completed provider response rejected by one allowlisted local public-card
rule is a terminal strict failure of the primary endpoint. It is not a
valid final card and is not missing data. Provider, SDK, or internal failures
remain non-assessable and keep the locked cause gate false.

| Arm | Strict success / assessed | Valid outputs | Terminal local rejection | Non-assessable | API calls |
| --- | ---: | ---: | ---: | ---: | ---: |
| direct_raw_no_revision | 2/2 | 2 | 0 | 0 | 2 |
| direct_raw_fixed_revision_rerun | 2/2 | 2 | 0 | 0 | 2 |
| staged_card_only_rerun | 0/2 | 2 | 0 | 0 | 12 |
| staged_cumulative_raw | 2/2 | 2 | 0 | 0 | 12 |

## Terminal local contract rejections

None.

## Stable case outcomes

A stable pass means at least two strict successes in the locked three
trials. A terminal local contract rejection contributes one strict failure.
Smoke and subset runs cannot produce a locked cause decision.

| Case | No revision | Fixed revision | Card only | Cumulative raw | Envelope | Aperture |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| unit_reinterpretation | 1/1 | 1/1 | 0/1 | 1/1 | not_assessed | not_assessed |
| invalidated_sensor_fallback | 1/1 | 1/1 | 0/1 | 1/1 | not_assessed | not_assessed |

## Claim boundary

This is a fresh run under a versioned local endpoint policy, not a
retrospective reclassification of v0.4.1. The prompts, fixtures, model,
arm order, and nominal budget remain inherited from the pinned v0.4.1
protocol. This contaminated DEV calibration is not a holdout, promotion
experiment, or proof of general reasoning improvement.
