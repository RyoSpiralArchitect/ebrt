# EBRT v0.6.1 Hosted Bundle Execution

Decision: **HOLD_V0_6_HOSTED_BUNDLE_GATE**

## Independent endpoints

| Endpoint | Status |
| --- | --- |
| Run | COMPLETE |
| P pre-event | FAIL |
| P stale regrade | FAIL |
| Public surrogate | PASS |
| D strict hosted path | PASS |
| Observational effect | NULL |

## Calls

| Pos | Arm | Status | Answer | Strict grade | API calls | Tokens | Latency ms |
| ---: | --- | --- | --- | --- | ---: | ---: | ---: |
| 1 | P | COMPLETED | POLISH | FAIL | 1 | 1816 | 12685.216 |
| 2 | A | COMPLETED | PROVE | FAIL | 1 | 1796 | 8511.332 |
| 3 | B | COMPLETED | PROVE | PASS | 1 | 11447 | 8320.552 |
| 4 | D | COMPLETED | PROVE | PASS | 1 | 11854 | 7812.647 |
| 5 | C | COMPLETED | PROVE | PASS | 1 | 11854 | 8605.623 |

## Claim boundary

- This is one contaminated five-call engineering regression over a known synthetic walkthrough, not a fresh quality benchmark.
- P is a pre-event product reference and is excluded from A/B/C/D effect contrasts; the fixed execution order is unbalanced and time-confounded.
- A/B/C/D receive byte-identical ordered R1-R6 raw evidence; B/C/D receive the same contaminated typed public DAG and differ only in their frozen public-control treatment.
- C and D match in row set, value/sign multiset, sparsity, per-lane norm, merge norm, and schema; only signed-displacement placement differs.
- Signed public actuator displacement is not evidence truth, probability, required support, hidden-state editing, or a semantic boost/suppress claim.
- The public DAG and surrogate program are supplied case-specific oracle structure rather than autonomously discovered semantics.
- No separately loaded grader or gold artifact enters provider input; B/C/D do receive a contaminated answer-adjacent oracle lineage program.
- A local backward pass exists only in the public differentiable substrate; no gradient crosses GPT, JSON, provider parsing, or grading boundaries.
- Surrogate status, hosted output, strict lineage, effect label, calls, tokens, and latency are reported separately.
- Promotion requires a complete bridge plus the preregistered strict P and D paths; it does not require D to outperform A, B, or C.
- The frozen v0.5.2 near-pass remains byte-identical and false; this successor does not regrade, relax, or replace it.
- Sanitized receipts and local hashes establish internal consistency, not cryptographic provider attestation; an external manifest anchor is required to distinguish a coherent forgery.
