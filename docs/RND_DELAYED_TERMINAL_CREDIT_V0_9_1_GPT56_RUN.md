# v0.9.1 delayed terminal credit: requested GPT-5.6 block

Status: **R02 CLOSED; 9/9 COMPLETED; ALL ARMS 3/3 ANSWER / SUPPORT / STRICT — OBSERVED CEILING**

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
mode `0600`; r01 paths are not overwritten. Public notes contain the
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

## Observed results

R02 ran on **2026-11-03, 01:07:42–01:09:13 JST**, from the pushed pre-dispatch
commit `c74c782d844f4bb040423a63e1a9ee0cf3c8eec7`. All nine scheduled responses
completed with the exact `gpt-5.6-sol` identity. There were **zero retries,
provider errors, incomplete responses, or rescue calls**. All nine private
response IDs were present and distinct.

| Arm | Planned | Completed | Schema valid | Exact answer | Exact support | Strict conjunction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Direct | 3 | 3 | 3 | 3 | 3 | 3 |
| Scrambled | 3 | 3 | 3 | 3 | 3 | 3 |
| Adjoint | 3 | 3 | 3 | 3 | 3 | 3 |

The three arms produced **byte-identical public output text within each
case**, not merely equal scores. All emitted the following correct values and
chronologically ordered support arrays:

| Case | Answer, every arm | Support IDs, every arm |
| --- | ---: | --- |
| shifted_readout | 5 | `E_B, E_C, E_T1, E_T2, E_EVENT` |
| merged_register | 14 | `E_A, E_B, E_C, E_T1, E_T2, E_EVENT` |
| cancelled_branch | 0 | `E_A, E_C, E_T1, E_T2, E_EVENT` |

Thus all conditions handled the two cancelled input dependencies correctly,
including direct with no supplied review weights. The collection status is
`COMPLETE_EXACT_NINE_TERMINALS`; offline verification returns
`DESCRIPTIVE_ONLY`. The quality scores above come from exact post-run grading,
not from those collection/verification labels.

## Verification and resource accounting

The original source-bound verifier passed with exit code **0**. The separate
integer audit reused the exact previously retained audit source (SHA-256
`43751e1f6229aa4dcc82fe570865967ae1820ad8659b0f930edeb481f19f685e`). It reconstructed
the matrices, inputs, and late event from the sealed public prompts, then
calculated answers and support through integer forward evaluation and basis
interventions. **All nine grades agreed** with the runner. Both checks were
offline and made no generation calls.

The runner and test-module blobs remain identical to PR #57. R01's private
result file also retains its pre-r02 SHA-256 above. R02 contributes nine fresh
generation attempts; PR #58 has **18 generation attempts in total** across
the two separate blocks, plus the one earlier model-list metadata request.

| Arm | Input tokens | Output tokens | Total tokens | Reasoning tokens (within output) |
| --- | ---: | ---: | ---: | ---: |
| Direct | 921 | 561 | 1,482 | 444 |
| Scrambled | 972 | 503 | 1,475 | 386 |
| Adjoint | 972 | 542 | 1,514 | 425 |
| Total | 2,865 | 1,606 | 4,471 | 1,255 |

All usage fields were available. Per-response output usage was **159–214
tokens**, including reasoning, below even r01's 384-token ceiling. This block
therefore does not show that raising the output ceiling was necessary; it also
does not test the counterfactual GPT-5.6 responses under a 384-token request.
The changed model and requested budget remain distinct protocol differences.

All artifacts remain in `/workspace/setup-logs/`, mode `0600`:

| Artifact | Filename | Sealed fingerprint |
| --- | --- | --- |
| Plan | `delayed-terminal-credit-plan-r02.json` | `4957298dbf61a71f09f929cc79d1773e04bd5734817d91ab7e30306250479e89` |
| Results | `delayed-terminal-credit-results-r02.json` | `04abc8693d3849d5c94edbeba8208a6aac8fec08406938ae5e3212a0696f3b47` |
| Verification | `delayed-terminal-credit-verification-r02.json` | `aef6a3b7850621df98338763e5d4c692c25f5ebf6da219fd26825982f03b6a67` |
| Independent audit | `delayed-terminal-credit-audit-r02.json` | `2eb9d95d3b4dc71515bb9107d2f83e3b2c5d2d5a35f7a8b8c64b72e3cb71f441` |

Execution timestamps/exit code are in `delayed-terminal-credit-execution-r02.json`;
CLI output is in `delayed-terminal-credit-run-r02.log`. The shared independent
audit source is `delayed-terminal-credit-audit-r01.py`. No private provider
receipts were committed. Fingerprints prove local consistency rather than
provider authenticity; their replay requires access to the retained artifacts.

```bash
.venv/bin/python delayed_terminal_credit_v0_9_1.py verify \
  --plan /workspace/setup-logs/delayed-terminal-credit-plan-r02.json \
  --report /workspace/setup-logs/delayed-terminal-credit-results-r02.json
```

## Interpretation and next decision

The requested model handles all three arithmetic/cancellation cases under
the frozen r02 settings. **No adjoint-placement quality advantage is observed**:
direct and scrambled already attain the same ceiling. This does not establish
that weights are inert in general, reveal private reasoning, or show a stable
effect across samples. These are three reused engineered cases with one draw
per cell, not nine independent benchmark problems.

R01's quality floor and r02's ceiling are both retained. Their difference is
descriptive under different model/budget settings, not a controlled estimate
of a model-only or gradient benefit. A useful next study would preregister
fresh, harder delayed-dependency cases on the requested model with fixed
within-model budgets and matched weight placement. No additional block or
case tuning was performed here.
