# EBRT v0.4.2 diagnostic closure — DEV report

Mode: `openai_live_dev_aperture_controls_v0_4_2`  
Four-arm runs: `30`  
Primary-endpoint-assessed four-arm runs: `28/30`  
All-output-completed four-arm runs: `27/30`  
Locked decision ready: `false`  
Revision-envelope conclusion: `not_assessed_incomplete_or_subset_run`  
Raw-aperture conclusion: `not_assessed_incomplete_or_subset_run`  
Next scaffold step: `complete_exact_locked_same_block_run`  
Nominal / attempted API calls: `420` / `414`  
Full-run launch ready: `false`
Launch-gate smoke manifest: `72b7571be7eca10d2f4d89949dd791d9613c2e36f8bd2024188d10329188c3df`  
Launch-gate same-source revalidation: `true`

A completed provider response rejected by one allowlisted local public-card
rule is a terminal strict failure of the primary endpoint. It is not a
valid final card and is not missing data. Provider, SDK, or internal failures
remain non-assessable and keep the locked cause gate false.

| Arm | Strict success / assessed | Valid outputs | Terminal local rejection | Non-assessable | API calls |
| --- | ---: | ---: | ---: | ---: | ---: |
| direct_raw_no_revision | 29/30 | 30 | 0 | 0 | 30 |
| direct_raw_fixed_revision_rerun | 29/29 | 29 | 0 | 1 | 30 |
| staged_card_only_rerun | 2/29 | 28 | 1 | 1 | 174 |
| staged_cumulative_raw | 30/30 | 30 | 0 | 0 | 180 |

## Terminal local contract rejections

| Arm | Stable reason code | Count |
| --- | --- | ---: |
| staged_card_only_rerun | `invalidated_active_support` | 1 |

## Stable case outcomes

A stable pass means at least two strict successes in the locked three
trials. A terminal local contract rejection contributes one strict failure.
Smoke and subset runs cannot produce a locked cause decision.

| Case | No revision | Fixed revision | Card only | Cumulative raw | Envelope | Aperture |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| route_code_supersession | 3/3 | 3/3 | 0/3 | 3/3 | both | cumulative_raw_only |
| alias_rebind | 3/3 | 2/3 | 0/3 | 3/3 | not_assessed | not_assessed |
| unit_reinterpretation | 3/3 | 3/3 | 0/3 | 3/3 | both | cumulative_raw_only |
| timestamp_boundary | 3/3 | 3/3 | 0/3 | 3/3 | both | cumulative_raw_only |
| invalidated_sensor_fallback | 3/3 | 3/3 | 0/3 | 3/3 | both | cumulative_raw_only |
| dependency_root_correction | 3/3 | 3/3 | 0/3 | 3/3 | both | cumulative_raw_only |
| quantifier_erratum | 3/3 | 3/3 | 0/3 | 3/3 | both | cumulative_raw_only |
| source_revocation | 2/3 | 3/3 | 0/3 | 3/3 | both | cumulative_raw_only |
| relevant_nonflip | 3/3 | 3/3 | 0/3 | 3/3 | both | cumulative_raw_only |
| unrelated_noop | 3/3 | 3/3 | 2/3 | 3/3 | both | both |

## Claim boundary

This is a fresh run under a versioned local endpoint policy, not a
retrospective reclassification of v0.4.1. The prompts, fixtures, model,
arm order, and nominal budget remain inherited from the pinned v0.4.1
protocol. This contaminated DEV calibration is not a holdout, promotion
experiment, or proof of general reasoning improvement.
