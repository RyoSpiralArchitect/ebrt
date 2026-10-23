# Budgeted public reinspection

Status: **OFFLINE VERIFIED; READY FOR BOUNDED INTEGRATION**

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
