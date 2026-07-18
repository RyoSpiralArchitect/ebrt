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

This section is intentionally empty until r01 terminates. After execution it
will record, without changing the meta-lock:

- final main commit/tree, preregistration commit, and policy SHA-256;
- runtime versions and source-map equality;
- smoke/full manifest SHA-256 and internal artifact hash maps;
- nominal and attempted calls, assessed/accepted endpoints, terminal reason
  codes, non-assessable failures, coverage, and launch/decision gates;
- per-arm strict outcomes, stable counts, locked contrasts, and any permitted
  cause conclusion;
- byte-identical canonical freeze verification.

Execution status: **PENDING**
