# EBRT v0.4.2 — diagnostic closure protocol

Status: `DEV_DRAFT`

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

This policy is prospective. It does not convert the frozen v0.4.1 bundle into a
complete or decision-ready result. A fresh exact v0.4.2 block is required.

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

No live API call was made while implementing this protocol.

## Claim boundary

Decision readiness means the exact locked primary endpoints were assessable and
all attempted receipts validated. It does not mean every output was valid, all
420 nominal calls were attempted, or every arm passed. Terminal contract
rejections remain measured failures.

The suite is still contaminated DEV. A v0.4.2 result can rank these locked
protocols on this suite, but cannot establish general reasoning improvement,
raw retention as the isolated mechanism, or holdout generalization.
