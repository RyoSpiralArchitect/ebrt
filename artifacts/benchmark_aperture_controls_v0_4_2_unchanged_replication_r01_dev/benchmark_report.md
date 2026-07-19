# EBRT v0.4.2 diagnostic closure — DEV report

Mode: `openai_live_dev_aperture_controls_v0_4_2`  
Four-arm runs: `30`  
Primary-endpoint-assessed four-arm runs: `22/30`  
All-output-completed four-arm runs: `20/30`  
Locked decision ready: `false`  
Revision-envelope conclusion: `not_assessed_incomplete_or_subset_run`  
Raw-aperture conclusion: `not_assessed_incomplete_or_subset_run`  
Next scaffold step: `complete_exact_locked_same_block_run`  
Nominal / attempted API calls: `420` / `344`  
Full-run launch ready: `false`
Launch-gate smoke manifest: `fb623a28eb61d7c9dea971ff8018645890b141f79b048e38e109fb32765d15a5`  
Launch-gate same-source revalidation: `true`

A completed provider response rejected by one allowlisted local public-card
rule is a terminal strict failure of the primary endpoint. It is not a
valid final card and is not missing data. Provider, SDK, or internal failures
remain non-assessable and keep the locked cause gate false.

| Arm | Strict success / assessed | Valid outputs | Terminal local rejection | Non-assessable | API calls |
| --- | ---: | ---: | ---: | ---: | ---: |
| direct_raw_no_revision | 20/22 | 22 | 0 | 8 | 30 |
| direct_raw_fixed_revision_rerun | 22/22 | 22 | 0 | 8 | 30 |
| staged_card_only_rerun | 1/23 | 21 | 2 | 7 | 139 |
| staged_cumulative_raw | 22/22 | 22 | 0 | 8 | 145 |

## Terminal local contract rejections

| Arm | Stable reason code | Count |
| --- | --- | ---: |
| staged_card_only_rerun | `invalidated_active_support` | 2 |

## Stable case outcomes

A stable pass means at least two strict successes in the locked three
trials. A terminal local contract rejection contributes one strict failure.
Smoke and subset runs cannot produce a locked cause decision.

| Case | No revision | Fixed revision | Card only | Cumulative raw | Envelope | Aperture |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| route_code_supersession | 2/3 | 2/3 | 0/3 | 2/3 | not_assessed | not_assessed |
| alias_rebind | 2/3 | 2/3 | 0/3 | 2/3 | not_assessed | not_assessed |
| unit_reinterpretation | 3/3 | 3/3 | 0/3 | 3/3 | both | cumulative_raw_only |
| timestamp_boundary | 3/3 | 3/3 | 0/3 | 3/3 | both | cumulative_raw_only |
| invalidated_sensor_fallback | 2/3 | 2/3 | 0/3 | 2/3 | not_assessed | not_assessed |
| dependency_root_correction | 2/3 | 2/3 | 0/3 | 2/3 | not_assessed | not_assessed |
| quantifier_erratum | 2/3 | 2/3 | 0/3 | 2/3 | not_assessed | not_assessed |
| source_revocation | 0/3 | 2/3 | 0/3 | 2/3 | not_assessed | not_assessed |
| relevant_nonflip | 2/3 | 2/3 | 0/3 | 2/3 | not_assessed | not_assessed |
| unrelated_noop | 2/3 | 2/3 | 1/3 | 2/3 | not_assessed | not_assessed |

## Claim boundary

This is a fresh run under a versioned local endpoint policy, not a
retrospective reclassification of v0.4.1. The prompts, fixtures, model,
arm order, and nominal budget remain inherited from the pinned v0.4.1
protocol. This contaminated DEV calibration is not a holdout, promotion
experiment, or proof of general reasoning improvement.
