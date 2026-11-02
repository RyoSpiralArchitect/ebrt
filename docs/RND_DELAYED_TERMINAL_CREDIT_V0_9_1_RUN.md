# v0.9.1 hosted collection: delayed terminal credit

Status: **CLOSED; 9/9 RESPONSES COMPLETED; ALL ARMS 0/3 ANSWER / 1/3 SUPPORT / 0/3 STRICT**

This execution follows the merged [PR #57](https://github.com/RyoSpiralArchitect/ebrt/pull/57)
and its [fixed protocol](RND_DELAYED_TERMINAL_CREDIT_V0_9_1.md). The runner,
fixtures, prompts, grading, and nine-call schedule are unchanged. This note
records the first hosted block separately from implementation/preflight.

After this block closed, the maintainer's model-selection reply requested
`gpt-5.6-sol`. Its separately authorized [r02 collection](RND_DELAYED_TERMINAL_CREDIT_V0_9_1_GPT56_RUN.md)
uses the same fixtures and 4096 output tokens: all three arms scored 3/3 strict.
R01's outcomes below remain unchanged; the two blocks are not pooled or treated
as a model-only comparison.

## Configuration fixed before dispatch

- Date: 2026-11-03 (Asia/Tokyo).
- Merged implementation: `cf3dc56f92c041f0eb7edc4f9bf31f1b1d87fe68`.
- Model: `gpt-4.1-2025-04-14`, exact returned identity required.
- Output ceiling: **384 tokens**, the protocol default; timeout **60 seconds**.
- Three development cases × direct / scrambled / adjoint: **nine planned generation attempts**.
- Original Latin-rotated serial order, `store=False`, SDK retries **0**.
- Stop at the first provider failure, incomplete response, or model-identity drift.
  No replacement cases, rescue requests, or repeat collection under another path.
- Python **3.12.14**, PyTorch **2.14.1+cpu**, OpenAI SDK **2.45.0**, httpx **0.28.1**.

The model was selected before any task generation: the dated GPT-4.1 identity
supports this structured-output interface without allocating the small output
budget to reasoning tokens. This is a new model-specific descriptive block,
not a replication of earlier `gpt-5.6-sol` results. One read-only model-list
request confirmed availability; it is separate from generation attempts and
does not establish runtime compatibility or answer quality. No generation
probe was made.

The current environment passed **16/16 tests**, the mechanism self-test,
and Python compilation. Socket connection attempts were denied during the
test run; **0 connection attempts** were observed. Python/PyTorch versions
differ from PR #57's pre-merge environment and are recorded here explicitly.
The tested runner and test-module Git blobs match that merged preflight:

| Item | Fingerprint |
| --- | --- |
| Runner Git blob | `ef6cc96714fad80b6ebbd76f549b5a73c143ae6e` |
| Test-module Git blob | `43b244d0faf34c67d9beba0585922f9294d8db53` |
| Runner SHA-256 | `bb632431f10765b386c6ccbe0f6de8cee97c9e756e59a0d9effa29ae580e77b5` |
| Source-bound plan fingerprint | `80c4d54a260938b861f6fd726a9d90f22e2818d0f28bdea3fdb02ae3db9447bd` |

The sealed plan is stored outside the checkout at
`/workspace/setup-logs/delayed-terminal-credit-plan-r01.json`, mode `0600`.
Provider receipts and verification artifacts also remain private local
files; public documentation contains aggregate results and fingerprints,
not credentials or provider response identifiers.

## Interpretation fixed before collection

Report answer correctness, exact chronological support, and their strict
conjunction separately for each arm, with **three planned cases per arm**.
Completed wrong or malformed outputs remain failures in those denominators.
A provider stop leaves undispatched outcomes unassessed and cannot support a
completed matched comparison. Collection status and report integrity are
separate from answer quality.

Adjoint versus scrambled is the primary matched placement contrast; direct
is contextual. A ceiling or null contrast must be reported as observed. These
three engineered cases and one serial block cannot establish general model
quality, a gradient-specific advantage, or model-internal backpropagation.

## Observed results

The single block ran on **2026-11-03, 00:55:31–00:55:47 JST**, from the pushed
pre-dispatch commit `553bd6217ac49ac38e61e8552cfac898bc3faccb`. All nine calls
returned `completed` and the locked model identity. There were no retries,
incomplete responses, provider errors, or extra generation calls. Each of the
nine response IDs was present and distinct; those IDs remain private.

| Arm | Planned | Completed | Schema valid | Exact answer | Exact support | Strict conjunction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Direct | 3 | 3 | 3 | 0 | 1 | 0 |
| Scrambled | 3 | 3 | 3 | 0 | 1 | 0 |
| Adjoint | 3 | 3 | 3 | 0 | 1 | 0 |

All denominators include all three planned cases per arm. The completed
wrong outputs are output-quality failures; they are not transport failures.
The runner's collection status is `COMPLETE_EXACT_NINE_TERMINALS`, and its
offline verifier returns `DESCRIPTIVE_ONLY`. Neither status means that the
answers passed.

| Case | Correct answer | Direct answer | Scrambled answer | Adjoint answer | Exact support, every arm |
| --- | ---: | ---: | ---: | ---: | --- |
| shifted_readout | 5 | 11 | 8 | 6 | FAIL |
| merged_register | 14 | 8 | 8 | 10 | PASS |
| cancelled_branch | 0 | 12 | 12 | 12 | FAIL |

Every response supplied the same support array:
`[E_A, E_B, E_C, E_T1, E_T2, E_EVENT]`. For `shifted_readout`, `E_A` should
have been excluded after cancellation. For `cancelled_branch`, `E_B` should
have been excluded. Only `merged_register` requires all three input receipts.
Thus the observed support behavior did not follow the adjoint's zero-weight
input exclusions. Adjoint and scrambled produced different numeric answers
on two of the three cases, but their per-case answer/support/strict grades
were identical. This is a null contrast on the declared quality endpoints,
not byte-identical output or proof that weights can never affect generation.

## Verification and work accounting

The original offline verifier passed source/plan/report binding, prompt
schedule, model/status receipts, and grade replay. An additional offline audit
parsed the input receipts, matrices, and late selector directly from the sealed
public prompts. It used integer forward evaluation and basis interventions,
without calling the runner's `oracle`, `dynamics`, or `grade` for its independent
answers and supports. Its nine grades agreed with the saved report.

The independently reduced current-output expressions are:

- `shifted_readout`: `B - C + 2 = 5`.
- `merged_register`: `2*A + B + C - 3 = 14`.
- `cancelled_branch`: `2*A - 2*C + 4 = 0`.

These calculations also establish the two cancelled input dependencies. The
actual runner and test-module blobs remain byte-for-byte equal to PR #57.
Post-collection edits change documentation only. Verification and arithmetic
audit made **zero generation calls**; this block has **nine total generation
attempts**, plus the separate pre-dispatch model-list metadata request.

| Arm | Input tokens | Output tokens | Total tokens | Reasoning tokens |
| --- | ---: | ---: | ---: | ---: |
| Direct | 927 | 101 | 1,028 | 0 |
| Scrambled | 978 | 101 | 1,079 | 0 |
| Adjoint | 978 | 110 | 1,088 | 0 |
| Total | 2,883 | 312 | 3,195 | 0 |

All token-usage fields were available. Individual output usage was 30–50
tokens, below the 384-token ceiling; no provider truncation was recorded.
This does not diagnose why the arithmetic failed or demonstrate that another
model, output contract, or budget would succeed.

Private artifacts are in `/workspace/setup-logs/`, all mode `0600`:

| Artifact | Filename | Sealed fingerprint |
| --- | --- | --- |
| Plan | `delayed-terminal-credit-plan-r01.json` | `80c4d54a260938b861f6fd726a9d90f22e2818d0f28bdea3fdb02ae3db9447bd` |
| Results | `delayed-terminal-credit-results-r01.json` | `b22460e5835ea0efde30ecfd674dbb8777d1f81ce56cc586d8d5a6c78773f50a` |
| Verification | `delayed-terminal-credit-verification-r01.json` | `0379053c6db8caab7c31cb95911db32b67b54cb6a68f157e563e745c4182e85c` |
| Independent audit | `delayed-terminal-credit-audit-r01.json` | `4517ee56bbb9077f1cd9924726155394dfa8740191f362075e6cb41aa949e9ed` |

The execution timestamps/exit code are retained in
`delayed-terminal-credit-execution-r01.json`, and CLI output in
`delayed-terminal-credit-run-r01.log`. The independent audit source is retained
as `delayed-terminal-credit-audit-r01.py`, SHA-256
`43751e1f6229aa4dcc82fe570865967ae1820ad8659b0f930edeb481f19f685e`.
Fingerprints establish local consistency, not provider authenticity. Raw
provider receipts are not committed, so checking these private report seals
requires access to the retained local artifacts.

Offline replay, without another collection:

```bash
.venv/bin/python delayed_terminal_credit_v0_9_1.py verify \
  --plan /workspace/setup-logs/delayed-terminal-credit-plan-r01.json \
  --report /workspace/setup-logs/delayed-terminal-credit-results-r01.json
```

## Interpretation and next decision

The public-surrogate mechanism gate still passes. The hosted experiment
provides **no answer or support-quality advantage for adjoint placement** in
this fixed block. Since direct also answered every case incorrectly, this is
an observed quality floor, not the anticipated all-correct ceiling. A single
draw per case/arm cannot distinguish sampling variation from a repeatable
placement effect or explain the common arithmetic failures.

A useful next separately preregistered study would test task-shaped arithmetic
and cancellation readiness on fresh cases before a new matched placement
comparison. Model, budget, output contract, and admission rules would need to
be fixed before its own outputs are seen. No such follow-up was executed here;
the current cases, failures, and nine-call block remain closed.
