# EBRT v0.8.5.3 — public-role adapter breadth canary

Status: `COMPLETE_ADAPTER_DIAGNOSTIC; ALGORITHM_NOT_ASSESSED`.

## Question

Does the exact v0.8.5.2 public-role adapter surface pass the two-stage
readiness gate on two additional local model snapshots, and—only where it
does—does the existing public control program produce a normalized final-state
difference?

The model families and cases were exercised in prior development runs. This is
a contaminated adapter-breadth diagnostic, not a fresh benchmark or model
ranking.

## Only changed execution variable

The model-visible surface is frozen to v0.8.5.2. The new exact snapshots are:

- `mlx-community/Llama-3.2-3B-bf16@60a99aaf43164077157d64bf909b7b61143c6a6d`
- `mlx-community/gemma-2-2b-4bit@2da7060bea6e767e27d7a776f834071ba69bd3ba`

Before the policy lock can be emitted, the runner checks all nine prompts:

1. current v0.8.5.3 prompt bytes equal v0.8.5.2 exactly; and
2. deleting only `role` from each `EVIDENCE_JSON` reconstructs v0.8.5 exactly.

This covers one task-readiness prompt plus direct and role-controlled prompts
for all four cases.

## Readiness-first geometry

Each model receives exactly:

1. one literal `FORMAT_READY` call; and
2. one task-shaped `TASK_CHANNEL_READY` call.

Only a model passing both gates enters the four contaminated cases, with one
direct and one controlled call per case. Therefore the sealed run has:

- minimum logical calls: `4` when neither model is admitted;
- one-model admission: `12` calls; or
- maximum logical calls: `20` when both models are admitted.

Sampling remains temperature `0.0`, seed `0`, maximum `96` generated tokens,
chat-template rendering, and no automatic retry. Native-state capture is
disabled.

## Measurements

Primary adapter receipts:

- literal format readiness per model;
- task-channel readiness per model;
- exact reason-code checks for answer, support, revision, preservation,
  forbidden evidence, and channel disjointness.

Only for admitted models:

- strict direct and controlled grades;
- raw output difference;
- parsed sequence difference;
- normalized public-state and answer difference;
- strict repair or regression counts.

## Claim boundary

- Public roles are caller-supplied scaffold metadata, not autonomously
  discovered dependencies.
- Semantic gold remains post-call grading material and is absent from prompts.
- The direct/control arm still bundles evidence ordering and explicit public
  revision instructions.
- No gradient crosses a model adapter.
- One deterministic sample over known model families and contaminated cases
  cannot establish causal superiority, general reasoning improvement,
  model ranking, or cross-model regularity.
- A model stopped by readiness contributes no algorithm-quality denominator.

## Pre-call commands

```bash
python3 -m ruff check public_role_adapter_breadth_v0_8_5_3.py
python3 public_role_adapter_breadth_v0_8_5_3.py self-test
python3 public_role_adapter_breadth_v0_8_5_3.py lock-spec \
  --output policy_lock_public_role_adapter_breadth_v0_8_5_3.json
```

The runner and generated policy lock must be committed and pushed before the
first local model call. The `r01` result is preserved without retry whether it
passes, fails, or produces no admitted cells.

## r01 result

The lock was pushed in commit `391e4e3`. The no-retry run terminated after the
minimum four calls:

- Llama format/task: `FAIL / FAIL`, both `MLX_GENERATION_FAILED`;
- Gemma format/task: `FAIL / FAIL`, both `MLX_GENERATION_FAILED`;
- admitted models and regression cells: `0 / 0`;
- algorithm and final-output effect: `NOT_ASSESSED_NO_ADMITTED_CELLS`.

A post-run, model-call-free tokenizer-config inspection found that both
snapshots lack a chat template while the lock requires chat-template
rendering. This is a static adapter mismatch, not a model-reasoning result. The
public error code does not expose the underlying exception, so runtime-failure
causal attribution remains `NOT_ASSESSED`.

See the
[`r01` report](../artifacts/public_role_adapter_breadth_v0_8_5_3/r01/report.md)
and
[`post-run interpretation`](../artifacts/public_role_adapter_breadth_v0_8_5_3/r01/post_run_interpretation.json).
