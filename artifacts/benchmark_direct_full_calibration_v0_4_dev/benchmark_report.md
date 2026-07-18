# EBRT v0.4 Direct vs Full calibration — DEV report

Mode: `openai_live_dev_calibration`  
Paired runs: `30`  
Complete paired runs: `30/30`  
Locked decision ready: `true`  
Direction: `repair_public_card_factorization_before_selective`

Both arms received the same fixed, summary-free revision envelope. The
comparison matches only the nominal cumulative `max_output_tokens` ceiling;
realized tokens, calls, latency, price, and server compute were not matched.
The interfaces require arm-specific instructions. Direct receives the envelope
once, while Full receives the same metadata on each staged call; late raw text
still appears exactly once per arm and is not citable early in Full.

| Arm | Strict success | Completed | API calls | Input tokens | Output tokens | Reasoning tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| direct_raw_fixed_revision | 30/30 | 30/30 | 30 | 22041 | 4442 | 0 |
| full_restart | 4/30 | 30/30 | 180 | 132097 | 41864 | 17502 |

## Paired outcomes

- Full only: `0`
- Direct only: `26`
- Both pass: `4`
- Neither passes: `0`
- Incomplete: `0`

## Stable case outcomes

A stable pass means at least two successes in the locked three trials.
Smoke runs cannot produce a locked direction.

| Case | Family | Direct | Full | Outcome |
| --- | --- | ---: | ---: | --- |
| route_code_supersession | lookup_key_revision | 3/3 | 0/3 | direct_only |
| alias_rebind | entity_alias_revision | 3/3 | 0/3 | direct_only |
| unit_reinterpretation | unit_revision | 3/3 | 0/3 | direct_only |
| timestamp_boundary | timestamp_revision | 3/3 | 0/3 | direct_only |
| invalidated_sensor_fallback | source_fallback_revision | 3/3 | 1/3 | direct_only |
| dependency_root_correction | dependency_chain_revision | 3/3 | 0/3 | direct_only |
| quantifier_erratum | rule_revision | 3/3 | 0/3 | direct_only |
| source_revocation | source_precedence_revision | 3/3 | 0/3 | direct_only |
| relevant_nonflip | state_revision_same_answer | 3/3 | 0/3 | direct_only |
| unrelated_noop | irrelevant_late_control | 3/3 | 3/3 | both |

## Claim boundary

This contaminated DEV calibration does not evaluate the observer, does not
match actual compute, and cannot establish general reasoning improvement.
A Full advantage would support this staged protocol on these cases; it would
not isolate public-card structure from the effect of repeated API calls.
Selective replay was not executed and receives no formal same-block rank.
