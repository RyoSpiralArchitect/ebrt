# EBRT v0.4.2 — unchanged replication r01

Status before execution: **PREREGISTERED; NO LIVE CALL MADE**

This lane repeats the v0.4.2 contract smoke and, only if its fixed launch gate
passes, the exact ten-case three-trial DEV block. The v0.4.2 runner, its built-in
policy lock, prompts, fixtures, gold, model, budgets, order, validators, and
provider boundary remain byte-identical. The external meta-lock is
[`policy_lock_aperture_controls_v0_4_2_unchanged_replication_r01.json`](../policy_lock_aperture_controls_v0_4_2_unchanged_replication_r01.json).

This is not a confirmatory holdout. We have already seen the suite and the prior
v0.4.2 result. The primary endpoint is therefore operational diagnostic
closure, not whether the preferred arm wins:

1. `smoke_gate_failed_full_not_launched`
2. `full_executed_incomplete_non_assessable`
3. `full_executed_decision_ready`

Only the third state permits reporting the existing locked cause conclusion.
No result establishes generalization, a compression-only mechanism, or a
generic reasoning improvement.

## Git seal and unchanged-source gate

The preregistration commit must be pushed before the first live call. It must
descend from reviewed PR head `abb09bae4ca7aafe0a9ce6251e21bb0811b21474`
and final `main` commit `59f46a7d391fb698cd8edf59efdcbcff97be4fa5`
with tree `61264b1a1af5683d640c68cfeacb8546c4729f8e`.

Before execution:

- the worktree is clean;
- Python/OpenAI/Pydantic versions equal the meta-lock;
- the API key is present without being printed;
- the runner self-test passes;
- the runner's 16-file boot source snapshot equals the meta-lock exactly;
- both fixed working outputs and both canonical outputs do not exist;
- the policy file hash is recorded and remains unchanged through freeze.

Any failed gate ends r01 without a live call.

## One-shot execution

Run the fixed prior-failure smoke exactly once:

```bash
python3 benchmark_aperture_controls_v0_4_2.py \
  live-contract-smoke \
  --output benchmark_results/v0_4_2_unchanged_replication_r01_contract_smoke
```

The full launch gate requires all eight arm endpoints to be assessed as an
accepted output or allowlisted terminal local rejection, every attempted
receipt to validate, and zero provider/SDK/fingerprint/internal non-assessable
failures. A terminal local rejection may make attempted calls less than the
nominal 28 without invalidating the smoke.

Only when `full_run_launch_ready` is true, run exactly once:

```bash
python3 benchmark_aperture_controls_v0_4_2.py \
  live-dev \
  --contract-smoke-manifest \
    benchmark_results/v0_4_2_unchanged_replication_r01_contract_smoke/manifest.json \
  --output benchmark_results/v0_4_2_unchanged_replication_r01_dev
```

There is no retry, resume, repair, partial fill, replacement output, prior
receipt reuse, or `live-subset` substitute. Power loss, timeout, SDK failure,
or an adverse result is frozen as observed. Any future attempt requires a new
preregistered protocol identifier and does not fill r01.

## Predeclared comparison to the prior v0.4.2 block

The prior block recorded 28/30 assessed four-arm runs, 27/30 all-output-
completed runs, 414 attempted calls, two non-assessable failures, and one
terminal local rejection. Comparison is limited to those fields plus
predeclared per-arm accepted/strict-assessed counts, stable counts, the two
locked contrasts, cause-decision readiness/conclusion, and exact total token
accounting. No favorable post-hoc subset will be introduced.

## Executed record

Execution status: **FROZEN — FULL EXECUTED, INCOMPLETE/NON-ASSESSABLE**

The preregistration was committed and pushed before the first provider call:

```text
final main commit     59f46a7d391fb698cd8edf59efdcbcff97be4fa5
final main tree       61264b1a1af5683d640c68cfeacb8546c4729f8e
required ancestor     abb09bae4ca7aafe0a9ce6251e21bb0811b21474
prereg commit         02c53f72008fc476c066f7be4ef6935ca77f43b6
policy SHA-256        2fdecd663df2efd713a242268108e7f7ee131e074191c72bc650c5ab48886584
runtime               Python 3.13.13 / openai 2.45.0 / pydantic 2.12.5
source map            16/16 equal across policy, live manifests, and files
```

The policy file remained byte-identical. Both canonical bundles are
byte-identical copies of their one-shot working bundles, and all ten internal
artifact hashes verify.

### Contract smoke

```text
manifest SHA-256      fb623a28eb61d7c9dea971ff8018645890b141f79b048e38e109fb32765d15a5
status                 COMPLETE_NON_DECISION_RUN
runs / endpoints       2/2 / 8/8 accepted
nominal / attempted    28 / 28 calls
terminal rejections    0
non-assessable         0
receipt validation     true
full launch ready      true
```

Artifact SHA-256:

```text
results.json           763868acd12b7022f7f682fb0698b1ca1ae439b33a86864387810eb9f99311f7
traces.jsonl           3a68e848d7b56f74f8401a5665428b6a7f7a8c3debd745673c6d551b4c849787
calls.jsonl            86b194a4b9cf00206747ce940912d88c3477cc67759ea706b9747ea448266045
arm_rows.csv           be97060bdeca9a7e16ec937f15f31ebcffefa26121ad694afdf71cdcdb231b0a
benchmark_report.md    22da8f2727ab7fe7325c9e160db937fdd0d159a7f110e1ad34735ec9bd99023b
```

Both prior and r01 smoke blocks produced the same assessed outcomes: both
Direct arms and cumulative-raw passed 2/2, while card-only failed strictly on
2/2. The raw contrast was cumulative-only on both cases. Exact provider token
totals were 27,872 for the prior smoke and 27,675 for r01. This small stochastic
difference is descriptive only.

### Exact full block

```text
manifest SHA-256       dde2d872ead686fa5d4b8074536e0d44acc1678036937f834fbe6389a3971671
launch smoke SHA-256   fb623a28eb61d7c9dea971ff8018645890b141f79b048e38e109fb32765d15a5
status                  INCOMPLETE
exact coverage          10 cases x 3 trials / 30 scheduled runs
nominal / attempted     420 / 344 calls
accepted endpoints      87
terminal rejections     2, both invalidated_active_support
non-assessable          31
assessed four-arm runs  22/30
all-output-completed    20/30
receipt validation      true
locked decision ready   false
cause conclusion        not_assessed_incomplete_or_subset_run
```

Artifact SHA-256:

```text
results.json           a123bf3ff9fdf70a1cee6a7ea06508fa216dfb380efdf7e4e02c855d6ea3c4e7
traces.jsonl           c8e1656de8531aa53f3e6e801ace20276b66f66b16e360c08d5db3a89412951c
calls.jsonl            f9d3e750fc5db354e29db2742aa0eebe35898596440b2f24a995be964d9edbfb
arm_rows.csv           1408c5b24c62b635d4361978e6c9be1e6082f140630a6237514310927f39c69c
benchmark_report.md    eeb553867dd6a10ffcac916492f6c888cbb9df69b11d78209526586e738872c0
```

The two terminal local rejections occurred in card-only at
`timestamp_boundary` trial 0 and `dependency_root_correction` trial 1. Both
stopped after the third staged call, and both final provider receipts had exact
usage. They are assessed strict failures under the predeclared endpoint policy.

The first 313 receipts completed. Receipts 314 through 344 then formed a
contiguous 31-attempt failure tail. Every frozen row retains the v0.4.2
classification `provider_call_exception_unclassified`; receipt metadata records
`failure_type=RateLimitError`, `attempt=1`, and `retry_count=0`. The tail began
at the sixth/final cumulative-raw call for `invalidated_sensor_fallback` trial 2
and continued through the remaining two arms in that run and all four arms in
the last seven runs, with no successful recovery.

The artifact does not retain an HTTP status or provider error code. Therefore
it cannot distinguish ordinary rate limiting from quota exhaustion, and the
coarse `transport_error` receipt status is not evidence that no HTTP response
existed. These rows are not retrospectively relabeled.

### Predeclared prior comparison

| Endpoint | Prior v0.4.2 | r01 | Delta |
|---|---:|---:|---:|
| Assessed four-arm runs | 28/30 | 22/30 | -6 |
| All-output-completed runs | 27/30 | 20/30 | -7 |
| Attempted calls | 414 | 344 | -70 |
| Non-assessable endpoints | 2 | 31 | +29 |
| Terminal local rejections | 1 | 2 | +1 |

Per-arm accepted / assessed / strict-failure counts:

| Arm | Prior | r01 |
|---|---:|---:|
| Direct fixed revision | 29 / 29 / 0 | 22 / 22 / 0 |
| Direct no revision | 30 / 30 / 1 | 22 / 22 / 2 |
| Staged card-only | 28 / 29 / 27 | 21 / 23 / 22 |
| Staged cumulative-raw | 30 / 30 / 0 | 22 / 22 / 0 |

Stable-pass case counts fell from `9 / 9 / 1 / 9` to `2 / 2 / 0 / 2` in the
same arm order, but stable-assessed cases also fell from 9 to 2. This is missing
endpoint coverage, not evidence that model quality declined. Likewise, the
lower card-only strict-failure count has a smaller assessed denominator and is
not evidence of improvement.

Among trial-level assessed contrasts, prior to r01 changed from 27 to 20
both-pass and 1 to 2 fixed-only for revision, and from 26 to 21 cumulative-only
and 2 to 1 both-pass for raw aperture; incomplete contrasts rose from 2 to 8.
The direction remains descriptively compatible with the earlier block, but the
locked cause gate is closed. Exact full-block token comparison is unavailable
because both blocks contain provider calls without exact usage; no partial or
post-hoc favorable subset is reported.

### Frozen conclusion

The preregistered primary classification is:

```text
full_executed_incomplete_non_assessable
```

r01 passed its fresh smoke, but the full block was dominated late by a
contiguous provider-boundary failure tail and did not make the v0.4.2 mechanism
decision assessable. This supports the need for prospective provider-boundary
instrumentation in v0.4.3. It does not establish an algorithm performance gain
or loss, a compression-only mechanism, generalization, or an instrumentation
effect.
