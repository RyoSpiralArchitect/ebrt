# EBRT v0.4.3 provider-boundary diagnostics — DEV report

Mode: `openai_live_provider_boundary_smoke_v0_4_3`  
Runs: `2`  
Diagnostic integrity ready: `true`  
Locked decision ready: `false`  
Full-run launch ready: `false`  
Provider-boundary failures: `8`  
Non-assessable endpoints: `8`

Provider/SDK failures are diagnostically classified but remain
non-assessable. Only inherited local public-card validator rejections
are assessed strict failures.

| Arm | Strict success / assessed | Accepted | Local rejection | Provider boundary | Non-assessable | API calls |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| direct_raw_no_revision | 0/0 | 0 | 0 | 2 | 2 | 2 |
| direct_raw_fixed_revision_rerun | 0/0 | 0 | 0 | 2 | 2 | 2 |
| staged_card_only_rerun | 0/0 | 0 | 0 | 2 | 2 | 2 |
| staged_cumulative_raw | 0/0 | 0 | 0 | 2 | 2 | 2 |

## Provider-boundary failures

- `authentication`: 0
- `bad_request`: 0
- `conflict`: 0
- `connection`: 0
- `http_other`: 0
- `insufficient_quota`: 8
- `missing_exact_usage`: 0
- `missing_structured_output`: 0
- `not_found`: 0
- `permission_denied`: 0
- `provider_error`: 0
- `provider_incomplete`: 0
- `provider_refusal`: 0
- `provider_status_non_completed`: 0
- `rate_limit`: 0
- `request_unclassified`: 0
- `sdk_http_envelope_validation`: 0
- `sdk_parse_unclassified`: 0
- `sdk_response_decode`: 0
- `sdk_structured_parse_validation`: 0
- `server_error`: 0
- `timeout`: 0
- `unknown429`: 0
- `unprocessable_entity`: 0
- `wrong_runtime`: 0

## Claim boundary

This is contaminated DEV instrumentation, not a holdout, promotion
result, general reasoning-improvement claim, or private-state read.
Diagnostic integrity does not make incomplete endpoints decision-ready.
