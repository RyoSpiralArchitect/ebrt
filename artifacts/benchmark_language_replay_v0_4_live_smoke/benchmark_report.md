# EBRT v0.4 Language Replay Bridge — DEV report

Mode: `openai_live_smoke`  
Runs: `2`  
Observer route matches DEV gold: `2/2`

| Lane | Machine success | Cards regenerated | Branch API calls | Branch input tokens | Branch output tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| card_only_forward | 1/2 | 2 | 2 | 1580 | 431 |
| full_restart | 2/2 | 12 | 12 | 9257 | 1924 |
| selective_replay | 1/2 | 5 | 5 | 4106 | 1204 |

Counterfactual totals charge the shared initial trace and the observer to every lane:

| Lane | Total API calls | Total input tokens | Total output tokens |
| --- | ---: | ---: | ---: |
| card_only_forward | 14 | 9616 | 2645 |
| full_restart | 24 | 17293 | 4138 |
| selective_replay | 17 | 12142 | 3418 |

Selective cards saved versus full restart: `7`.
Selective/full replay-card ratio: `0.4167`.

This is non-promotional DEV evidence. Scripted mode is plumbing-only; live-smoke mode is not a general LLM accuracy benchmark.
