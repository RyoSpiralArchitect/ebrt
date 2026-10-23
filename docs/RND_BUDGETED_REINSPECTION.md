# Budgeted public reinspection

Status: **EXECUTED; REQUEST-BUDGET AND SOURCE-PROVENANCE INTEGRATION PASS**

The hosted numeric-alignment diagnostic in PR #50 found no answer or
support-set benefit from changing the numeric mapping in a shared textual
program. Its eight-call block is closed. This next implementation connects
the existing allocation units to actual request token ceilings and executes
a public reinspection phase before final generation.

## Executed operations

The planner obtains the verified backward trajectory and the standard
coverage-first program. It accepts at most three selected evidence sites.
Each site's allocation determines the `max_output_tokens` setting of a
separate extraction request. The default audit budget is 768 output tokens
across all sites, with a minimum of 128 per site. The remaining budget is
distributed by exact integer largest remainders over the program's allocation
units. Selected-row order breaks ties deterministically.

For example, allocations of 51/36/13 with three sites yield request ceilings
of 324/266/178 tokens. Those ceilings sum to 768. They constrain requested
output budgets, rather than measuring consumed compute or forcing the model
to use all available tokens. Signed controls remain provenance; this protocol
does not assign new executable semantics to their sign.

Each extraction request receives the question and one selected evidence
record. It must return one JSON object containing exactly `evidence_id` and
`quote`, without explanations. The host checks the selected ID and a bounded,
nonempty, verbatim source quotation. Invalid JSON, duplicate or extra fields,
unknown or wrong-site IDs, and invented quotations stop the run. Source
provenance does not establish semantic relevance or completeness.

After all extractions pass, the runtime supplies the complete original
evidence and validated quotations as escaped, quoted data to one final
generation. Its actual prompt and request fingerprint bind the extraction
artifacts. The default final request has a separate 512-token ceiling.
Semantic gold is used only for optional post-run grading.

## Call accounting and failure handling

This is a separate opt-in orchestration protocol. The standard single-lane
engine retains its original behavior and admission rules. A three-site run
contains three extraction attempts and one final generation attempt, for a
maximum of four provider attempts. A final-stage `ModelResult` describes only
that final request; it is not the call count of the complete run.

All stages share an explicit outer ledger and SDK client. Each stage permits
one attempt with no retries. The plan fixes its request configuration and
token cap. A provider or extraction failure remains recorded and stops before
any later stage. There is no repair request or fallback final generation.

The local report retains stage invocations, per-stage generation settings,
provider receipts, visible responses, validated excerpts, and separate
execution, structural, and semantic grades. The offline verifier rebuilds the
plan and dynamic final invocation from those responses and checks the
termination boundary and complete accounting. This verifies internal receipt
consistency, not provider authenticity.

## Scope of evidence

The completion target is executed allocation scheduling and source-bound
dataflow into final generation. It is not a new reasoning-quality benchmark.
The generator remains outside autograd. Public roles and geometry remain
caller supplied, and the new runtime does not extract a differentiable model
trajectory or backpropagate through a hosted provider.

The smallest live integration check is one known synthetic case with at most
four attempts, after fixing the source and saving an offline plan. A failure
is retained without retrying that block. Provider identifiers and detailed
receipts stay in new local files outside the checkout with mode `0600`.

## Offline validation

All 102 network-zero tests passed across the existing demo, hosted runtime,
support diagnostic, standard engine, and new reinspection runtime. The 27 new
tests cover actual SDK token settings, exact aggregate budgets, real backward
execution, gold noninterference, quotation provenance and escaping, the
separate final request, early stops, model mismatch, semantic failures,
coherently resealed report changes, and private output preflight.

An independent adversarial review found no required changes. It also checked
one- and two-site call accounting, optional semantic contracts, and rejection
of a success ledger truncated before its next planned stage. Historical core,
standard-engine, hosted-runtime, and diagnostic execution sources are unchanged.

## First fixed integration block

One known synthetic normalization case ran with `gpt-5.6-sol` on 2026-10-23
(Asia/Tokyo). Source was fixed at
`36cc517d26290f483f8c33b0decee4cd8343b84e`, and the plan was saved before any
of its provider calls. Requests used low reasoning effort and a 60-second
per-attempt timeout, with retries disabled.

| Stage | Allocation units | Requested output-token ceiling | Result |
| --- | --- | --- | --- |
| Reinspect correction `R6` | 52 | 328 | Exact source quotation validated |
| Reinspect current rule `R4` | 35 | 262 | Exact source quotation validated |
| Reinspect observation `R2` | 13 | 178 | Exact source quotation validated |
| Final generation | N/A | 512 | Structural and post-run checks passed |

All four attempts completed using the same returned model identity. Audit
ceilings summed to 768, and the complete run reserved 1280 output tokens.
These are request ceilings, not reported token consumption. All three source
quotations reached the final full-context invocation, whose new fingerprint
bound their artifacts. The final answer was `28_UNITS`, with support
`R6,R4,R2`. Execution, source-provenance, structural, and semantic checks passed.

A separate offline process rebuilt the report and passed all four stages.
Independent review also checked the raw quotations, final request, call ledger,
token limits, and answer/support grades. No detailed provider receipts were
exported. The plan, report, and verification receipt remain outside the
checkout with mode `0600`.

This establishes that requested allocation scheduling and validated excerpt
dataflow execute end to end. The known case was already solved by earlier
single-call conditions; this run does not establish that the excerpts, extra
calls, or allocation mapping improve quality. The four-attempt integration
block is complete, and PR #50's earlier comparison was not rerun.

Plan fingerprint:

```text
87dfc2a70217716719746faca5fbb470133ad67e3a688bbfcd36e65afd1d55db
```

Local report fingerprint:

```text
01a47753277af8722428fb7f43c5237beb3aada02464a84816c5222c8e7a75d4
```

With the retained local files, offline verification is:

```bash
python3 ebrt_reinspection_hosted.py verify \
  --plan /workspace/setup-logs/budgeted-reinspection-plan-r01.json \
  --report /workspace/setup-logs/budgeted-reinspection-results-r01.json
```

Future execution-source changes require replay against the recorded source
revision. Existing hashes and scores must not be rewritten to fit newer code.
