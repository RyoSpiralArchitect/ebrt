# EBRT v0.5.1 Controlled Raw Restart — Canary

Status: **INCOMPLETE_CANARY**

Case: `route_code_supersession`
Mode: `openai_live_dev_canary`

| Arm | Status | Strict pass | Answer | API calls |
| --- | --- | ---: | --- | ---: |
| `raw_restart_zero_control` | failed | false | — | 1 |
| `raw_restart_textual_envelope` | failed | false | — | 1 |
| `raw_restart_matched_permutation` | failed | false | — | 1 |
| `controlled_raw_restart` | failed | false | — | 1 |

## Baseline to controlled public output diff

Unavailable because one or both public cards were rejected.

## Boundary

- This is one development-contaminated case and one unbalanced four-call block.
- Provider randomness and run position are not separated from arm behavior.
- The public temporal program and case binding are explicit oracle inputs.
- GPT, provider parsing, and final generation remain outside the gradient graph.
- A changed output or controlled-only pass is a canary observation, not an advantage estimate.
- Frozen predecessor imports may hash the gold file for source integrity, but semantic gold JSON is parsed and attached only after all four provider attempts.
