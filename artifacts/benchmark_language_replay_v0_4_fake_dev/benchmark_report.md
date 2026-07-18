# EBRT v0.4 Language Replay Bridge — DEV report

Mode: `scripted_plumbing`  
Runs: `10`  
Observer route matches DEV gold: `10/10`

| Lane | Machine success | Cards regenerated | Branch API calls | Branch input tokens | Branch output tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| card_only_forward | 10/10 | 10 | 0 | n/a | n/a |
| full_restart | 10/10 | 60 | 0 | n/a | n/a |
| selective_replay | 10/10 | 37 | 0 | n/a | n/a |

Counterfactual totals charge the shared initial trace and the observer to every lane:

| Lane | Total API calls | Total input tokens | Total output tokens |
| --- | ---: | ---: | ---: |
| card_only_forward | 0 | n/a | n/a |
| full_restart | 0 | n/a | n/a |
| selective_replay | 0 | n/a | n/a |

Selective cards saved versus full restart: `23`.
Selective/full replay-card ratio: `0.6167`.

This is non-promotional DEV evidence. Scripted mode is plumbing-only; live-smoke mode is not a general LLM accuracy benchmark.
