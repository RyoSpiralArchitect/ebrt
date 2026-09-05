# v0.8.5.4 — Revision-prefix placement canary

Status: **ZERO-CALL VALIDATED; LOCAL LOCK/PREFLIGHT READY; NO LIVE RESULT**

## Question and implementation boundary

Does the **same existing EBRT public revision program** produce different
final public outputs when placed before, rather than after, the full raw
evidence? This is a small engineering canary inspired by
[Trace as State](https://arxiv.org/html/2609.02702v1), not a reproduction of its
model-generated reasoning-trace intervention or long-context experiments.

The existing `ebrt_core.py`, all historical runners, locks, and results stay
unchanged. One auxiliary file, `revision_prefix_placement_v0_8_5_4.py`, holds
the compiler comparison, local runner, repair-quality diagnostics, portable
verifier, report renderer, and zero-generation self-test. No UI or new model
backend is introduced.

## Exactly what changes

Let H be the common output-contract header, E the full chronological public
evidence block, P the public revision program, and Q the common final question.

| Arm | Input |
| --- | --- |
| baseline | H + E + Q |
| append | H + E + P + Q |
| prepend | H + P + E + Q |

All blocks are independently fingerprinted. E retains every raw record,
caller-supplied role, and original R1–R6 order. P is compiled once per case
through the existing local backward path and shared byte-for-byte by append
and prepend. The controller trajectory is retained separately from real model
outputs; the historical compilation helper's stub output and timing are not
model evidence and are excluded.

The previous role canary combined evidence reordering with an appended program.
Here evidence reordering is disabled in **all** arms. The baseline is generated
anew with the same H/E/Q; historical direct outputs are not substituted.

All four known cases have three mandatory reinspection targets (R6 correction,
R2 and R4 required support) and capacity three. Gradient-based **target
selection is therefore not identifiable**. This screen concerns placement of
the existing program, which also carries within-set ranking, allocation, and
signed controls. A future allocation test must remove all three gradient
channels from its fixed-control arm, not only equalize allocation units.

## Bounded execution

- Exact cached snapshot:
  `mlx-community/Mistral-7B-Instruct-v0.3-4bit@a4b8f870474b0eb527f466a03fbc187830d271f5`.
- Same four contaminated engineering cases from v0.8.4; no new quality suite.
- Two readiness calls: literal format, then task-shaped **new baseline**.
  Both must pass before any of the four cases is admitted.
- Three arms per admitted case, one deterministic generation each: at most
  **14 logical calls**, or two on a readiness stop. No automatic retry.
- Temperature 0, seed 0, 96 output tokens per call, chat-template rendering.
- Case call orders: B/A/P, A/P/B, P/B/A, P/A/B (B=baseline, A=append,
  P=prepend). This rotates order but is **not** a complete counterbalanced
  replication design; no causal or statistical superiority claim follows.
- No carried KV cache, native activation capture, speculative decoding,
  provider API, model download, or model-weight optimization.

The tokenizer-only preflight checks the exact local snapshot, chat-template
availability, full rendered prompts, token IDs/counts, snapshot file hashes,
and installed runtime versions before generation. It does not load model
weights. During execution the actual loaded tokenizer must reproduce those
receipts, and the recorded input token IDs are passed to MLX directly.

The MLX stream reports actual input/output counts and latency; terminal tokens
are included in the output count. Equal ceilings are **not equal actual
compute**. The baseline is shorter by construction, and tokenization may make
the two placement arms differ slightly in length. No synthetic padding hides
these differences. First-call model loading affects latency; this is not a
speed benchmark.

Commit and push the runner, policy lock, and preflight before execution. The
runner checks their exact bytes against the pushed branch commit. An exclusive
execution claim beside the policy lock prevents accidental reuse of the same
identity with another output directory. A flushed, hash-chained dispatch/
terminal journal preserves interruptions. Failure is retained, not rerun as r01.

## Repair quality, without changing the output contract

The existing strict v0.8.5.2 state parser and grader remain authoritative.
Post-call diagnostics distinguish:

- wrong answer value and a stale prior answer retained;
- missed or extra decision-support references;
- incorrect revision-event reference;
- missed or extra preserved-constraint references;
- invalidated evidence still present;
- parsing failure versus parsed semantic failure.

These are **public-field diagnostics**, not a general natural-language edit
distance or a full JSON Patch benchmark. The output schema emits stable
evidence IDs, not the values of stable facts. Consequently actual stable-value
preservation is explicitly `NOT_OBSERVABLE_IN_CURRENT_OUTPUT_SCHEMA`.

Set-valued support channels are normalized before comparing semantic outputs.
Raw generated text, normalized state, strict repairs/regressions, token counts,
and latency remain available side by side. A pair with an unparseable output
does not count as a semantic difference; it has a separate availability result.

The decomposition is motivated by
[RevPropBench](https://arxiv.org/html/2609.03254v1) and
[minimal-edit fidelity](https://arxiv.org/abs/2609.04061). Their published scores
are not imported or asserted for EBRT. No contract is relaxed to obtain a pass.

Gold is evaluated after output. Changing the expected-answer mapping while
holding the public task fixed must leave the compiled program and every prompt
unchanged. Answer choices themselves remain legitimate public task data.

## Commands

From the repository root, with the cached snapshot directory in
`EBRT_MISTRAL_PATH`:

```bash
python3 -m ruff check revision_prefix_placement_v0_8_5_4.py
python3 revision_prefix_placement_v0_8_5_4.py self-test
python3 revision_prefix_placement_v0_8_5_4.py lock-spec \
  --output policy_lock_revision_prefix_placement_v0_8_5_4.json
python3 revision_prefix_placement_v0_8_5_4.py preflight \
  --model "$EBRT_MISTRAL_PATH" \
  --lock policy_lock_revision_prefix_placement_v0_8_5_4.json \
  --output artifacts/revision_prefix_placement_v0_8_5_4/preflight.json
```

The two output paths are exclusive: the commands refuse to overwrite them.
Only after the frozen inputs are committed/pushed and execution is authorized:

```bash
python3 revision_prefix_placement_v0_8_5_4.py run \
  --execute-local-once \
  --model "$EBRT_MISTRAL_PATH" \
  --lock policy_lock_revision_prefix_placement_v0_8_5_4.json \
  --preflight artifacts/revision_prefix_placement_v0_8_5_4/preflight.json \
  --lock-commit FULL_PUSHED_COMMIT_SHA \
  --output artifacts/revision_prefix_placement_v0_8_5_4/r01
python3 revision_prefix_placement_v0_8_5_4.py verify \
  artifacts/revision_prefix_placement_v0_8_5_4/r01/results.json \
  --lock policy_lock_revision_prefix_placement_v0_8_5_4.json
```

Verification recomputes prompt plans, output parsing, strict grading, and
normalized differences. It does not rerun a model or assert that a hash alone
proves model execution. Tokenization is preserved as a recorded runtime receipt,
not independently rerun by the portable verifier.

## Next decision

First examine whether append/prepend differs on final answer or strict public
state, and whether either repairs or harms the contemporaneous baseline. If a
useful signal appears, test gradient versus genuinely non-gradient allocation
at the same position under a successor lock. If all semantic outputs remain
equal, retain the null and inspect the shared wrong-value case before expanding
architecture. Public effect attribution and gradient superiority remain
`NOT_ASSESSED` in this canary.

## Local validation — 2026-09-05

- New self-test: **42/42 PASS**, synthetic outputs only, zero model calls.
- Ruff lint/format and Python compilation: PASS.
- Historical v0.8.5.2 and v0.8.5.3 self-tests and r01 portable verifiers: PASS;
  no changes to their source, locks, or artifacts.
- Actual Mistral tokenizer-only preflight: PASS for all **14** planned prompts;
  seven snapshot files hashed, no weights loaded or generation requested.
- Append/prepend input-token counts match in every case:

| Case | Baseline | Append | Prepend |
| --- | ---: | ---: | ---: |
| freight-lane-rule-revision | 671 | 852 | 852 |
| credit-scale-rule-revision | 648 | 827 | 827 |
| archive-tier-policy-revision | 665 | 845 | 845 |
| permit-state-rule-revision | 642 | 822 | 822 |

Local artifacts:

- [Policy lock](../policy_lock_revision_prefix_placement_v0_8_5_4.json):
  `e38ef1dcdcbc5714f962360630e671f95646142fa0533a662e50e3f2498f584f`.
- [Tokenizer preflight](../artifacts/revision_prefix_placement_v0_8_5_4/preflight.json):
  `f1d85b33d95b6384e50b0015b349a624d180754172575a662ecd9493b9a9bfd9`.

The local generation count remains **0**. No `r01` result exists yet. Pushing
the sealed inputs and authorizing the bounded local run are the next gate;
offline validation is not an observed generator improvement.
