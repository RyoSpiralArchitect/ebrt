# EBRT v0.5.2 — Hackathon Strategy Walkthrough

Status: **COMPLETE TWO-CALL BLOCK — STRICT NEAR-PASS PRESERVED**

Frozen endpoint: **`walkthrough_contract_passed=false`**

## Why this exists

The v0.5.1 quota-recovery block completed all four hosted calls, but its
saturated route-code case produced an exactly empty public-output diff.  That
null result is preserved.  v0.5.2 does not reinterpret or tune that block.  It
adds a separate, judge-readable English walkthrough that carries the mechanism
all the way to a final generated output.

The fixed question is:

> Which single final-build priority should Team Spiral choose to maximize its
> chance of winning? Follow the latest valid judging guidance. Answer POLISH or
> PROVE.

This is intentionally sharper than a free-form "tips to win a hackathon"
prompt.  It has one decision, two allowed answers, typed output slots, explicit
evidence lineage, and a checkable late correction.

## Frozen two-call story

| Position | Phase | Visible evidence | External control | Expected public endpoint |
| ---: | --- | --- | --- | --- |
| 1 | `before_event` | ordered R1–R5 exactly once | none | `POLISH` under the then-valid design-dominant brief |
| 2 | `controlled_after_event` | ordered R1–R6 exactly once | fixed v0.5.1 gradient temporal-control envelope | `PROVE` after R6 supersedes R3 |

R4 remains visible in the first horizon as counterevidence; it is not falsely
graded as support for `POLISH`.  R5 fixes the narrated three-minute video format
and must survive unchanged.  In the final horizon, R3 must be marked invalid,
not used as active support.

The provider sees neither the separate gold artifact nor downstream grades.
The local surrogate target is still an explicit oracle input; it is not learned
from provider output.

## Product checks

After both attempts have finished, the locked grader checks:

1. the Before card passes the R1–R5 contract;
2. that unchanged Before card fails the post-event contract and is therefore
   visibly stale;
3. the After card passes the R1–R6 contract;
4. the public answer changes from `POLISH` to `PROVE`;
5. R3 support is dropped and invalidated while R6 support is added;
6. the `THREE_MINUTE_NARRATED` fact is preserved;
7. local surrogate movement and actual generated-output movement remain
   separate fields.

## What this cannot establish

This is not an A/B estimate.  Evidence horizon, event visibility, revision
envelope, and run position change together.  A successful walkthrough shows a
sealed end-to-end product path for one synthetic English case.  It does not
show that the control map caused the change, that EBRT improves general
reasoning quality, or that the method is more efficient or production-ready.

The frozen v0.5.1 A/B/C/D canary remains the control-placement diagnostic.  Its
complete recovery result showed no output effect on its saturated DEV case.

## Commands

```bash
python3 demo_hackathon_strategy_walkthrough_v0_5_2.py self-test
python3 demo_hackathon_strategy_walkthrough_v0_5_2.py preflight
python3 demo_hackathon_strategy_walkthrough_v0_5_2.py live-demo \
  --output demo_results/hackathon_strategy_walkthrough_v0_5_2_live_r01
python3 demo_hackathon_strategy_walkthrough_v0_5_2.py validate \
  --artifact-dir demo_results/hackathon_strategy_walkthrough_v0_5_2_live_r01
```

The live command is fail-fast if the destination already exists.  It makes one
attempt per phase with SDK retries disabled, writes through a sibling staging
directory, validates the complete bundle, and then publishes it atomically.

## Live result

The preregistered block was run exactly once after commit `62cb3ed`, with the
fixed phase order and no retries.  Both hosted calls completed and the sealed
artifact validates.

| Observation | Before | Controlled after |
| --- | ---: | ---: |
| Answer | `POLISH` | `PROVE` |
| Phase strict pass | yes | no |
| API calls | 1 | 1 |
| Input tokens | 925 | 1,256 |
| Output tokens | 171 | 182 |
| Reasoning tokens | 0 | 0 |
| Latency | 4,091.33 ms | 3,538.94 ms |

The generated public diff has the intended product shape:

- answer: `POLISH → PROVE`;
- `final_priority`: `ADDITIONAL_UI_POLISH → END_TO_END_PROOF`;
- `demo_centerpiece`: `POLISHED_SCREENS → LIVE_REASONING_DIFF`;
- R3 active support was dropped and R3 was marked invalid;
- R4 and R6 entered active support;
- `THREE_MINUTE_NARRATED` remained unchanged;
- the Before card passed its own horizon and failed when regraded unchanged
  against the post-event contract.

The overall walkthrough contract is nevertheless `false`.  Exactly one strict
check failed: `required_facts_exact` on the controlled After card.  The model
cited R2+R6 on `final_priority` and R4+R6 on `demo_centerpiece`; the locked gold
required R2+R4+R6 on each individual fact.  The answer, aggregate required
evidence, forbidden-support exclusion, R3 invalidation, and stable fact all
passed.  This is a fact-level support-lineage mismatch: the answer and
invalidation checks passed, while the overall frozen revision contract failed.

The public diff is not a complete semantic-state comparison.  In particular,
claim, topic, stance, and confidence are not graded by this endpoint or shown
in the diff.  The observed After stance is `+1.0` while the frozen gold stance
is `-1.0`; no belief-polarity claim should be made from that ungraded field.

The local surrogate objective moved from `0.755433933319` to
`0.294771509854`.  Actual provider output did not participate in that
optimization, so this numeric movement and the observed output change remain
separate observations.

No rerun, gold relaxation, or post-hoc regrading was used.  The canonical
bundle is
`artifacts/demo_hackathon_strategy_walkthrough_v0_5_2_live_r01/`, with result
fingerprint
`2e641e0f11f17bb16cbe629048e9cc8cff49706147616d888487f38b243430d4`.
