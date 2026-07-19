# EBRT v0.4.2 r01 vs v0.4.3 provider-boundary diagnostic

Status: `COMPLETE_DIAGNOSTIC_NON_CAUSAL`
Scope: offline, deterministic, diagnostic-only artifact comparison.
Promotion eligible: `false`

## Primary metric

`classified_nonassessable_endpoints/all_nonassessable_endpoints`

| Frozen block | Native classified | Ratio |
| --- | ---: | ---: |
| v0.4.2 r01 full | 0/31 | 0.0 |
| v0.4.3 contract smoke | 8/8 | 1.0 |

The r01 numerator remains zero because its frozen rows do not contain
the prospective v0.4.3 phase/reason fields. They were not relabeled.

## v0.4.3 observed boundary

- `http_status/insufficient_quota`: 8

- Diagnostic integrity ready: `true`
- Full launch ready: `false`
- Full block executed: `false`

## Decision

The v0.4.3 boundary classified all eight non-assessable smoke endpoints with diagnostic integrity, but the failed smoke launch gate closed the full block and every reasoning conclusion.

- Primary execution classification: `smoke_gate_failed_full_not_launched`
- Locked reasoning ready: `false`
- Cross-block diagnostic effect estimate: `null`
- Cross-block reasoning effect estimate: `null`
- Raw-aperture conclusion: `not_assessed_incomplete_or_subset_run`
- Revision-envelope conclusion: `not_assessed_incomplete_or_subset_run`

## Verification

- `artifact_hash_maps_valid`: `true`
- `canonical_bundles_required`: `true`
- `deterministic_schedule_valid`: `true`
- `full_v0_4_3_block_absent`: `true`
- `pinned_hashes_valid`: `true`
- `post_freeze_runner_verified_from_preregistration_blob`: `true`
- `privacy_audit_valid`: `true`
- `r01_native_rows_not_reclassified`: `true`
- `receipt_cardinality_valid`: `true`
- `v0_4_3_phase_reason_allowlist_valid`: `true`
- `v0_4_3_post_freeze_coverage_lineage_valid`: `true`
- `v0_4_3_provider_receipts_unchanged_by_coverage_correction`: `true`
- `working_bundles_optional_for_clean_checkout`: `true`
- `working_canonical_byte_identity_valid_when_available`: `true`
- `zero_retry_valid`: `true`

## Interpretation

- The frozen r01 block natively classified 0 of 31 non-assessable endpoints at the prospective phase/reason boundary.
- The v0.4.3 smoke natively classified 8 of 8 non-assessable endpoints and retained diagnostic integrity.
- The v0.4.3 smoke failed its full-launch gate, so no v0.4.3 full block exists and no reasoning endpoint comparison is available.

## Claim boundary

- The r01 rows remain frozen and are not retrospectively relabeled.
- r01 and v0.4.3 are independent stochastic blocks; the two proportions are descriptive and are not a causal instrumentation effect.
- The blocks have different declared populations: r01 is a 10-case by 3-trial full block, while v0.4.3 is a 2-case by 1-trial contract smoke.
- No quality, token, latency, failure-rate, or reasoning conclusion is assessed by this diagnostic comparison.
- This does not establish general reasoning improvement, provider-side root cause beyond typed observations, private chain-of-thought access, hidden-state editing, or model-weight change.
