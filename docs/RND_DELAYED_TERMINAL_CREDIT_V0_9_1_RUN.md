# v0.9.1 hosted collection: delayed terminal credit

Status: **PLAN LOCKED; GENERATION NOT YET DISPATCHED**

This execution follows the merged [PR #57](https://github.com/RyoSpiralArchitect/ebrt/pull/57)
and its [fixed protocol](RND_DELAYED_TERMINAL_CREDIT_V0_9_1.md). The runner,
fixtures, prompts, grading, and nine-call schedule are unchanged. This note
records the first hosted block separately from implementation/preflight.

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
Provider receipts and verification artifacts will also remain private local
files; public documentation will contain aggregate results and fingerprints,
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
