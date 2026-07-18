# EBRT v0.4.2 — diagnostic closure protocol

Status: `DEV_EXECUTED_INCOMPLETE`

Promotion eligible: `false`

Provider-facing protocol change from v0.4.1: `false`

## Purpose

v0.4.1 produced two completed OpenAI responses whose public cards were rejected
by the local validator before the staged arm could continue. The frozen artifact
records only `local_contract_error`, so it cannot identify the rejected rule.
It also treats every such arm as missing from the locked cause decision.

v0.4.2 closes that diagnostic gap without changing or reinterpreting v0.4.1.
The predecessor runner, lock, and artifact remain byte-identical. The prompts,
fixtures, gold, model, reasoning effort, budgets, Williams order, and four arms
are inherited from their pinned predecessor hashes.

## Predeclared endpoint policy

A local contract rejection after a completed provider call is now:

- terminal for that arm, with no retry or repair;
- backed by its counted, sanitized provider receipt;
- recorded only with an allowlisted non-sensitive reason code and sequence
  offset; and
- adjudicated as a strict failure of the primary endpoint.

The rejected card and raw exception message are not persisted. Remaining calls
in the rejected arm are not made, but the remaining preassigned arms continue.
Nominal and attempted calls are reported separately.

Provider-call exceptions, provider response-contract failures, request/receipt
fingerprint mismatches, internal invariant failures, and any unknown reason
code remain non-assessable. Any such failure keeps the full cause gate false.

This policy was prospective when frozen. It does not convert the frozen v0.4.1
bundle into a complete or decision-ready result. The fresh exact v0.4.2 block
described below remains independently non-decision-ready.

## Stable local reason-code surface

The lock contains the exact 13-code public-card enum. Codes identify only the
rejected model-output rule: answer choice, checkpoint, claim/topic bounds,
decision-slot schema, raw-copy bound, evidence availability, unseen or
invalidated active support, and invalidation permission. A request/receipt
fingerprint mismatch has a separate stable audit reason and is never counted as
a model-card strict failure.

Slot values, evidence values, rejected public cards, response bodies, headers,
and credentials are not added to the diagnostic surface.

## Direction-rule repair

The v0.4.1 implementation checked whether no-revision passed all cases before
checking whether no-revision-only stable cases existed. Under a hypothetical
10-versus-8 result, that could label a harmful fixed envelope as “not needed.”

v0.4.2 fixes the locked order:

1. mixed directional cases;
2. fixed-only contribution;
3. no-revision-only harm;
4. both arms saturated with no directional-only case; and
5. equal outcome below ceiling.

An offline test exercises the previously missing 10-versus-8 branch.

## Fixed execution sequence

Run the offline gate first:

```bash
python3 benchmark_aperture_controls_v0_4_2.py self-test
```

Then run the fixed prior-failure diagnostic smoke:

```bash
python3 benchmark_aperture_controls_v0_4_2.py live-contract-smoke \
  --output benchmark_results/v0_4_2_aperture_contract_live_smoke
```

This preset is fixed to `unit_reinterpretation` and
`invalidated_sensor_fallback`, one trial, and 28 nominal calls. It emits
`full_run_launch_ready=true` only when:

- exact two-case/one-trial coverage is present;
- every attempted receipt validates;
- every arm ends in either an accepted output or an allowlisted terminal local
  contract rejection backed by a completed exact-usage receipt; and
- no provider, internal, or other non-assessable failure occurs.

A terminal local rejection can therefore be a valid smoke outcome and still
permit the full run. Requiring all 28 nominal calls would erase the predeclared
terminal endpoint policy.

Only after that gate is true, launch the non-overridable full block:

```bash
python3 benchmark_aperture_controls_v0_4_2.py live-dev \
  --contract-smoke-manifest \
    benchmark_results/<passing-contract-smoke>/manifest.json \
  --output benchmark_results/v0_4_2_aperture_dev
```

`live-dev` always selects all ten locked cases and three trials. It exposes no
case or trial override and refuses to start without a passing same-source smoke
manifest. The manifest, its artifact hashes, executed case/trial pairs, receipt
accounting, and source graph are revalidated before any full-block API call.
`live-smoke` remains the fixed route/no-op canary, while `live-subset --case-id
...` is explicitly non-decision diagnostic work.

## Frozen execution record

The fixed contract smoke ran first and passed its launch gate:

- exact two-case x one-trial coverage;
- 2/2 four-arm runs reached accepted outputs;
- 28/28 nominal calls produced validated completed receipts;
- `status=COMPLETE_NON_DECISION_RUN`; and
- `full_run_launch_ready=true`.

The succeeding full block then executed the exact ten-case x three-trial
Williams schedule once, without resume, repair, or partial fill. It preserved
30/30 scheduled case-trials and 414 unique attempted-call receipts out of the
420-call nominal ceiling. Artifact hashes, all 16 pinned source hashes, the
fixture and gold hashes, and the launch-manifest hash validate.

The full manifest is intentionally `INCOMPLETE`:

- `alias_rebind`, trial 0, fixed-envelope Direct ended in one sanitized
  `APITimeoutError` after the 60-second client timeout;
- `alias_rebind`, trial 2, card-only staging ended at sequence offset 2 in a
  sanitized SDK `ValidationError` raised by the structured-output parse path;
  and
- `invalidated_sensor_fallback`, trial 2, card-only staging reached a completed
  exact-usage provider receipt and was then rejected locally with the new
  allowlisted reason `invalidated_active_support`.

The first two outcomes are non-assessable. The third is an assessed strict
failure under the predeclared terminal policy; its rejected card was not
persisted and its remaining three nominal calls were not made. Thus the block
contains 412 completed receipts, two non-assessable call receipts, one terminal
local contract rejection, 28/30 primary-endpoint-assessed four-arm runs, and
27/30 runs in which all four arms returned accepted outputs. No call was
retried.

| Metric | No-envelope Direct | Fixed Direct | Card-only staged | Cumulative raw |
| --- | ---: | ---: | ---: | ---: |
| Accepted outputs | 30/30 | 29/30 | 28/30 | 30/30 |
| Strict machine success | 29/30 | 29/30 | 2/30 | 30/30 |
| Exact final answer | 30/30 | 29/30 | 11/30 | 30/30 |
| Assessed stable-pass cases | 9/9 | 9/9 | 1/9 | 9/9 |
| Attempted API calls | 30 | 30 | 174 | 180 |
| Exact aggregate provider usage available | yes | no | no | yes |

Across the 28 assessed staged pairs, cumulative raw had 26 exclusive strict
successes and shared two successes with card-only; card-only had no exclusive
success. The remaining two pairs are incomplete, so the locked raw-aperture
cause conclusion stays `not_assessed_incomplete_or_subset_run`. The one-shot
revision-envelope comparison is likewise not decision-ready.

As a post-hoc descriptive check only, the 27 runs where all four outputs were
accepted give the staged arms the same 162-call realized geometry. Card-only
used 122,025 input, 39,020 output, and 17,326 reasoning tokens; cumulative raw
used 133,033 input, 31,620 output, and 8,341 reasoning tokens. That is +9.0%
input, -19.0% output, and -51.9% reasoning tokens for cumulative raw on this
accepted-output subset. Selection on completed outputs and the incomplete
whole block forbid promoting this to a causal or full-block efficiency claim.

This execution both validates and extends the diagnostic design. The new local
reason-code surface successfully converted one formerly opaque validator stop
into an assessed endpoint. It also exposed a separate blind spot: the current
provider wrapper cannot distinguish an SDK structured-output `ValidationError`
from a network transport exception once `responses.parse` raises before a
response object is returned. A successor may instrument that boundary, but it
must not relabel, fill, or rerun this frozen block.

Canonical evidence:

- `artifacts/benchmark_aperture_controls_v0_4_2_contract_smoke/`
- `artifacts/benchmark_aperture_controls_v0_4_2_dev/`

## Claim boundary

Decision readiness means the exact locked primary endpoints were assessable and
all attempted receipts validated. It does not mean every output was valid, all
420 nominal calls were attempted, or every arm passed. Terminal contract
rejections remain measured failures.

The suite is still contaminated DEV. This incomplete v0.4.2 block can describe
its assessed endpoints and nominate the same raw-aperture mechanism candidate.
It cannot formally rank the locked protocols at the preregistered case-level
endpoint, establish general reasoning improvement, isolate raw retention from
the other staged-interface differences, or establish holdout generalization.
