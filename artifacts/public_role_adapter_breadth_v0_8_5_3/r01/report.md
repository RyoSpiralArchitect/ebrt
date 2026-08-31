# EBRT v0.8.5.3 r01 — public-role adapter breadth

## Sealed execution

- Status: `COMPLETE_WITH_BOUNDED_ADAPTER_ADMISSION`
- Logical calls: `4`
- Automatic retries: `0`
- Models: `2` exact local snapshots
- Admitted regression models: `0`
- Policy-lock fingerprint:
  `1fb7f076a28ce30b86c30ab2e9caa8d257e52aba1acab6153710c1f379b87e07`
- Result file SHA-256:
  `74ae19dfcd294f15d49bb0af1133f70430a7803913f9a127b4f2691e68462b13`
- Run fingerprint:
  `0abe5048dcf81e7393bf417a831505d22b50822c97aa2a22c76dd3a888ba813d`
- Portable verification fingerprint:
  `a321a1ec67559bc787601f96ccd2fb693cd2ac7845da5951e39508911e9742a7`
- Post-run interpretation fingerprint:
  `ad088bc35f2a2227c0fb7fd5f9f6ea2bf98626854dffdda08d3945d5917ff624`

The lock was committed and pushed as `391e4e3` before the first model call.
The namespace was executed once and was not retried.

## Frozen surface

The only intended execution variable was the exact model snapshot pair.

- Complete prompt equality with v0.8.5.2: `9 / 9`
- Role-stripped prompt equality with v0.8.5: `9 / 9`
- Output contract, caller-supplied roles, controller, cases, schedule, sampling,
  and readiness gates: unchanged

## Readiness result

| Model | Format probe | Task probe | Public error | Cases |
| --- | --- | --- | --- | ---: |
| Llama 3.2 3B bf16 | FAIL | FAIL | `MLX_GENERATION_FAILED` | 0 |
| Gemma 2 2B 4-bit | FAIL | FAIL | `MLX_GENERATION_FAILED` | 0 |

Neither probe produced a public state or raw model text. The fail-closed gate
therefore stopped both snapshots after two calls each.

Consequently:

- direct/control cells: `0`
- final-output comparisons: `0`
- strict repairs or regressions: `0`
- algorithm-effect status: `NOT_ASSESSED_NO_ADMITTED_CELLS`

This is not a negative reasoning-quality result. Generation failed before a
typed public state existed.

## Post-run static adapter diagnosis

The sealed runtime required `prompt_rendering_mode=chat_template`. A local,
model-call-free inspection found no `chat_template` field in either locked
snapshot's `tokenizer_config.json`.

| Model | Tokenizer-config SHA-256 | Static status |
| --- | --- | --- |
| Llama 3.2 3B bf16 | `8004530facf809ac432114de2a4dcc65fcb632da5ec16d666091aeb6a2ee444a` | `CHAT_TEMPLATE_ABSENT_UNDER_LOCKED_CHAT_TEMPLATE_MODE` |
| Gemma 2 2B 4-bit | `fe5d3fb6a117764c66d7274b15df16660dcfe84795643fdbe512c502ab0cac9a` | `CHAT_TEMPLATE_ABSENT_UNDER_LOCKED_CHAT_TEMPLATE_MODE` |

This identifies a static adapter mismatch consistent with the observed public
errors. It does not prove that the absent configuration field was the sole
runtime cause: the public error code intentionally collapses the underlying
exception, so causal attribution remains `NOT_ASSESSED`.

## What this changes

Model breadth must not begin with inference. The model adapter needs a
zero-call rendering-capability preflight that checks whether the locked prompt
mode is supported before a model is admitted to any live call.

The next gate is therefore:

```text
snapshot identity
  -> tokenizer/rendering capability preflight
  -> literal format readiness
  -> task-channel readiness
  -> contaminated algorithm cells
```

For additional final-output examples, the next snapshots should be local
instruction-following candidates with an explicit chat template, or should be
placed under a separately locked plain-text adapter. Those are distinct
adapter protocols and must not be mixed into this frozen `r01`.

## Claim boundary

The model families and cases are previously exercised development material.
Public roles are caller-supplied scaffold metadata. No gradient crosses a model
adapter. No model capability, model ranking, final-output quality, causal
control, general reasoning improvement, or cross-model regularity claim is
admitted from this run.
