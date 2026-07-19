# EBRT v0.5.2 — Hackathon Strategy Walkthrough

Call block: **COMPLETE_CALL_BLOCK**
Walkthrough contract: **FALSE**

> Which single final-build priority should Team Spiral choose to maximize its chance of winning? Follow the latest valid judging guidance. Answer POLISH or PROVE.

| Phase | Visible evidence | Status | Phase pass | Answer | API calls |
| --- | --- | --- | ---: | --- | ---: |
| `before_event` | R1-R5 | completed | true | POLISH | 1 |
| `controlled_after_event` | R1-R6 | completed | false | PROVE | 1 |

## Public output diff

```json
{
  "answer_after": "PROVE",
  "answer_before": "POLISH",
  "answer_changed": true,
  "decision_fact_changes": [
    {
      "after": {
        "evidence_ids": [
          "R2",
          "R6"
        ],
        "value": "END_TO_END_PROOF"
      },
      "before": {
        "evidence_ids": [
          "R2",
          "R3"
        ],
        "value": "ADDITIONAL_UI_POLISH"
      },
      "slot": "final_priority"
    },
    {
      "after": {
        "evidence_ids": [
          "R4",
          "R6"
        ],
        "value": "LIVE_REASONING_DIFF"
      },
      "before": {
        "evidence_ids": [
          "R3"
        ],
        "value": "POLISHED_SCREENS"
      },
      "slot": "demo_centerpiece"
    }
  ],
  "derived_from": "public_reasoning_cards_only",
  "invalidated_added_ids": [
    "R3"
  ],
  "invalidated_dropped_ids": [],
  "support_added_ids": [
    "R4",
    "R6"
  ],
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
    "R3",
    "R5"
  ],
  "support_dropped_ids": [
    "R3"
  ]
}
```

## Surrogate / actual separation

- Local surrogate objective: `0.755433933319` → `0.294771509854`
- Before under its own horizon: `True`
- Same Before card under post-event grading: `False`
- Controlled after-event output: `False`
- Actual provider output did not participate in local autograd.

## Boundary

- This is one synthetic English product walkthrough, not a matched causal benchmark or fresh quality evaluation.
- The before and after calls have different visible evidence horizons; the after call also has a revision envelope and later run position.
- The public temporal program, semantic roles, evidence values, event scope, operator order, and terminal surrogate target are explicit oracle inputs.
- The provider receives a stop-gradient JSON projection; GPT, provider parsing, and final generation remain outside the gradient graph.
- Surrogate objective movement and actual public-output movement are reported separately; neither implies the other.
- A POLISH to PROVE change demonstrates this sealed walkthrough contract only, not a general reasoning, quality, efficiency, or causal advantage.
