# EBRT v0.5.1 Controlled Raw Restart — Canary

Status: **COMPLETE_CANARY**

Case: `route_code_supersession`
Mode: `openai_live_dev_canary`

| Arm | Status | Strict pass | Answer | API calls |
| --- | --- | ---: | --- | ---: |
| `raw_restart_zero_control` | completed | true | BLUE | 1 |
| `raw_restart_textual_envelope` | completed | true | BLUE | 1 |
| `raw_restart_matched_permutation` | completed | true | BLUE | 1 |
| `controlled_raw_restart` | completed | true | BLUE | 1 |

## Baseline to controlled public output diff

```json
{
  "answer_after": "BLUE",
  "answer_before": "BLUE",
  "answer_changed": false,
  "decision_fact_changes": [],
  "derived_from": "public_reasoning_cards_only",
  "invalidated_added_ids": [],
  "invalidated_dropped_ids": [],
  "support_added_ids": [],
  "support_after_ids": [
    "R1",
    "R2",
    "R4",
    "R5",
    "R6"
  ],
  "support_before_ids": [
    "R1",
    "R2",
    "R4",
    "R5",
    "R6"
  ],
  "support_dropped_ids": []
}
```

## Boundary

- This is one development-contaminated case and one unbalanced four-call block.
- Provider randomness and run position are not separated from arm behavior.
- The public temporal program and case binding are explicit oracle inputs.
- GPT, provider parsing, and final generation remain outside the gradient graph.
- A changed output or controlled-only pass is a canary observation, not an advantage estimate.
- Frozen predecessor imports may hash the gold file for source integrity, but semantic gold JSON is parsed and attached only after all four provider attempts.
