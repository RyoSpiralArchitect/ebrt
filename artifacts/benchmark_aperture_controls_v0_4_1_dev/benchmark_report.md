# EBRT v0.4.1 aperture controls — DEV report

Mode: `openai_live_dev_aperture_controls`  
Four-arm runs: `30`  
Complete four-arm runs: `28/30`  
Locked decision ready: `false`  
Revision-envelope conclusion: `not_assessed_incomplete_or_subset_run`  
Raw-aperture conclusion: `not_assessed_incomplete_or_subset_run`  
Next scaffold step: `complete_exact_locked_same_block_run`

The one-shot pair shares one prompt; only revision_context differs. The
staged pair shares one prompt; retained raw prefix and its corresponding
allowed evidence aperture differ. Only nominal cumulative max_output_tokens
ceilings are matched. Actual calls, input/output/reasoning tokens, latency,
price, and server compute are measured rather than matched.

| Arm | Strict success | Completed | API calls | Input tokens | Output tokens | Reasoning tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| direct_raw_no_revision | 29/30 | 30/30 | 30 | 22041 | 4523 | 87 |
| direct_raw_fixed_revision_rerun | 30/30 | 30/30 | 30 | 22911 | 4563 | 0 |
| staged_card_only_rerun | 2/30 | 28/30 | 174 | 131308 | 41299 | 17861 |
| staged_cumulative_raw | 30/30 | 30/30 | 180 | 148222 | 35046 | 9232 |

## Stable case outcomes

A stable pass means at least two successes in the locked three trials.
Smoke and subset runs cannot produce a locked cause decision.

| Case | No revision | Fixed revision | Card only | Cumulative raw | Envelope | Aperture |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| route_code_supersession | 3/3 | 3/3 | 0/3 | 3/3 | both | cumulative_raw_only |
| alias_rebind | 3/3 | 3/3 | 0/3 | 3/3 | both | cumulative_raw_only |
| unit_reinterpretation | 3/3 | 3/3 | 0/3 | 3/3 | both | cumulative_raw_only |
| timestamp_boundary | 3/3 | 3/3 | 0/3 | 3/3 | both | cumulative_raw_only |
| invalidated_sensor_fallback | 3/3 | 3/3 | 0/3 | 3/3 | both | cumulative_raw_only |
| dependency_root_correction | 3/3 | 3/3 | 0/3 | 3/3 | both | cumulative_raw_only |
| quantifier_erratum | 3/3 | 3/3 | 0/3 | 3/3 | both | cumulative_raw_only |
| source_revocation | 2/3 | 3/3 | 0/3 | 3/3 | both | cumulative_raw_only |
| relevant_nonflip | 3/3 | 3/3 | 0/3 | 3/3 | both | cumulative_raw_only |
| unrelated_noop | 3/3 | 3/3 | 2/3 | 3/3 | both | both |

## Claim boundary

This contaminated DEV calibration is a mechanism diagnostic, not a
holdout, promotion experiment, or proof of general reasoning improvement.
The no-revision arm remains a strict-schema scaffold. Cumulative raw
repeats prior raw input across calls. A failure therefore cannot isolate
retention from sequential commitment, prompt dynamics, or per-call cap
allocation. Selective replay remains paused and unranked.
