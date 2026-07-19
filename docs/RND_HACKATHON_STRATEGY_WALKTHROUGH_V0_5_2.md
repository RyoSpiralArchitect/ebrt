# EBRT v0.5.2 — Hackathon Strategy Walkthrough

Status: **PREREGISTERED PRODUCT WALKTHROUGH — NO LIVE RESULT ATTACHED**

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

Not run at preregistration time.
