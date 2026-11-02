# v0.9.1 delayed terminal credit: requested GPT-5.6 block

Status: **R02 PLAN LOCKED; GENERATION NOT YET DISPATCHED**

The maintainer explicitly requested `gpt-5.6-sol` in response to the model
selection question after the [GPT-4.1 r01 block](RND_DELAYED_TERMINAL_CREDIT_V0_9_1_RUN.md)
had already completed. This is a separately authorized model-specific block
in [PR #58](https://github.com/RyoSpiralArchitect/ebrt/pull/58), using the unchanged
[PR #57 protocol implementation](RND_DELAYED_TERMINAL_CREDIT_V0_9_1.md).
R01's plan, receipts, results, and failures remain preserved. R02 is not a
retry of r01 or a replacement for its planned denominator.

## Configuration fixed before dispatch

- Date: 2026-11-03 (Asia/Tokyo).
- Model: **`gpt-5.6-sol`**, exact returned identity required.
- Output ceiling: **4096 tokens**, including any provider reasoning tokens.
- Timeout: **60 seconds**, unchanged in the runner; SDK retries **0**;
  `store=False`.
- The unchanged runner sends **no reasoning-effort parameter**. Provider
  defaults apply; do not describe this as the `low` effort used by some
  earlier hosted studies.
- The same three cases × direct / scrambled / adjoint: **nine maximum
  generation attempts**, original Latin-rotated serial order, one draw per cell.
- Stop after the first provider failure, incomplete response, or returned-model
  mismatch. No fallback, rescue calls, resumed block, or additional seeds.
- Python **3.12.14**, PyTorch **2.14.1+cpu**, OpenAI SDK **2.45.0**, httpx **0.28.1**.

The 4096-token ceiling is an existing plan-time option. It is fixed before
any GPT-5.6 task response to leave room for reasoning within the output budget;
it does not guarantee completion. Relative to r01, the model and output
ceiling both change. Therefore r01/r02 differences cannot isolate a model-only
effect. Within r02, all three arms share exactly the same settings.

The three cases were already exposed in r01. R02 is a descriptive reuse of
development fixtures, not held-out evidence. No fixture, instruction, weight,
prompt, schedule, output schema, or grading rule was tuned after those outputs.
The two sealed plans differ only in `model`, `max_output_tokens`, and their
resulting fingerprints. No new model-list or generation probe is needed;
the previous read-only model-list request included `gpt-5.6-sol`.

## Preflight and lock

The exact runner/test blobs and Python/package environment are the same as
the immediately preceding r01 preflight, which passed **16/16 network-zero
tests**, compilation, and the mechanism check. Those unit tests were not
rerun for this configuration-only block. R02 independently rechecked the
mechanism, plan validity, unchanged source, and exact plan-field delta before
dispatch. All passed without provider calls.

| Item | Fingerprint |
| --- | --- |
| Merged implementation commit | `cf3dc56f92c041f0eb7edc4f9bf31f1b1d87fe68` |
| Runner Git blob | `ef6cc96714fad80b6ebbd76f549b5a73c143ae6e` |
| Test-module Git blob | `43b244d0faf34c67d9beba0585922f9294d8db53` |
| Runner SHA-256 | `bb632431f10765b386c6ccbe0f6de8cee97c9e756e59a0d9effa29ae580e77b5` |
| R02 source-bound plan fingerprint | `4957298dbf61a71f09f929cc79d1773e04bd5734817d91ab7e30306250479e89` |
| Preserved r01 results file SHA-256 | `a21c44bf94e521df60362e15dffacd098cc20b090f22d6eacd4aed75e535fa28` |

R02 private artifacts use `/workspace/setup-logs/delayed-terminal-credit-*-r02.*`,
mode `0600`; r01 paths are not overwritten. Public notes will contain the
observed outcomes and fingerprints, without credentials or provider IDs.

## Interpretation fixed before dispatch

Each arm retains **three planned cases**. Report completed responses, schema
validity, exact answer, exact chronological support, and their strict
conjunction separately. Wrong completed outputs count as graded failures;
a provider stop leaves remaining outcomes unassessed. Do not reinterpret a
partial collection as a completed matched comparison.

Adjoint versus scrambled is the primary within-model placement contrast.
Direct remains contextual. A ceiling or null result must be retained as
observed. One draw per cell on three reused synthetic cases cannot establish
general quality superiority, model-internal gradients, or a unique advantage
over symbolic analysis. The previously exposed r01/r02 blocks are not pooled
into a single quality denominator.
