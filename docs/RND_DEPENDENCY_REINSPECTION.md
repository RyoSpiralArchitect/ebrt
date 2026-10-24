# Dependency-aware public reinspection

Status: **OFFLINE VERIFIED; READY FOR BOUNDED INTEGRATION**

Budgeted reinspection executes allocation units as provider output-token
ceilings, but its isolated requests cannot resolve dependencies across sources.
For example, a tariff-table reader cannot choose an applicable row when the
consignment's lookup key appears only in an account register. Credit order can
also place the table audit before the register audit.

This protocol accepts a caller-declared public dependency graph between
selected evidence sites. It executes those sites in a stable topological
order and supplies each audit with validated quotations from its direct
predecessors. The existing backward trajectory, selected sites, per-ID
allocation units, token limits, and final compiler remain unchanged.

## Runtime contract

Edges must connect distinct selected sites. Duplicate edges, unselected or
unknown sites, cycles, and malformed IDs fail before provider calls. Among
ready sites, original program rank determines order. No dependency extraction
or semantic validation of the caller's graph is claimed.

Each audit sees the question, its primary source, and the exact validated
parent quotations as escaped JSON data. It must still quote its own source.
The runtime binds the declared parent set, artifact fingerprints, actual
dynamic request, and generation configuration. A failed parent stops later
stages. There are at most three audits and one final generation, without
repair or retries.

Before final compilation, artifacts return to original program order. Thus
the dependency execution order and final evidence/program presentation order
are separate. Semantic gold and required quote spans are withheld from all
requests and request fingerprints.

A separate post-run contract measures inclusion of predeclared source spans.
An exact quotation can pass provenance while missing the required span. This
metric is literal declared-span containment, not a general judge of semantic
relevance, truth, or every acceptable paraphrase. Neither this grade nor the
answer grade changes the schedule or triggers another call.
The declared spans retain the consignment/account/key and key/fee associations
without requiring cosmetic sentence prefixes or trailing punctuation. They
are fixed before any provider output is observed.

## Engineered lookup case

The new consignment case requires a consignment-to-account-to-tariff-key join
from `R2`, then an exact key lookup in `R4`. The key does not appear in the
question or as a consignment identifier in the tariff table. `R2` contains 25
registration records and exceeds 1200 characters. `R4` contains 64 tariff rows,
also exceeds 1200 characters, and repeats every possible fee on many rows.
The target row cannot be selected merely by finding a unique fee.

`R6` authorizes replacement of the retired rule in `R3`. `R1` describes another
active consignment and is forbidden as support for the queried one. The answer
changes from `17_CREDITS` to `29_CREDITS`. Caller-supplied public geometry is
synthetic and is not a model-extracted dependency representation.

The graph is `R2 -> R4`. Original program order is `R6,R4,R2`, with audit token
ceilings `324,266,178`. Dependency order becomes `R6,R2,R4`, with the same
per-site ceilings. The three audit ceilings still sum to 768; final generation
is capped separately at 512.

## Fixed matched integration gate

One predeclared gate permits at most six provider attempts:

1. Run dependency-aware reinspection: shared `R6` and `R2` audits, contextual
   `R4`, then its final generation (at most four attempts).
2. Reuse the actual validated `R6`/`R2` artifacts. Audit `R4` in isolation with
   the same token cap, then generate one matched final answer (at most two
   further attempts).

The `R4` audit prompts have identical task/source/instruction text; only parent
JSON records differ. Final prompts keep full context, program, settings, and
artifact order fixed, replacing only the `R4` artifact. Shared audits are not
executed again or counted twice.

An execution failure in the contextual run stops the gate. A failed span or
answer grade after successful execution does not prevent the isolated arm.
Failure of the isolated audit stops its final generation. Unparsed final
pairs are not assessed as equal outputs. Every failed attempt remains in the
ledger and consumes its declared budget.

This is one engineered case with serial, nonrandomized calls and shared
artifacts. It establishes conditional dataflow and reports descriptive
extraction/final-output differences. It does not isolate a general causal
effect, gradient benefit, or population quality gain. Request ceilings are
not consumed compute, and signed controls retain their provenance-only role.

Source, graph, contracts, settings, and the six-attempt schedule are fixed
before the first request. Earlier evaluation blocks remain closed. Detailed
provider receipts stay outside the checkout in new mode-0600 files.

## Offline validation

All 158 network-zero tests passed, including 33 new runtime/canary tests.
Coverage includes dependency rejection and stable ordering, unchanged per-ID
caps, actual parent-quote routing, original-order final compilation, separate
provenance and required-span grades, Gold noninterference, six-attempt shared
prefix accounting, execution-only branch gating, unparsed comparisons, and
coherently resealed plan/report tampering.

Independent adversarial review found no required fixes. Additional fake-SDK
probes checked smaller site counts, optional contracts, pre-dispatch failures
after zero/four/five attempts, and isolated model mismatches at attempts five
and six. Earlier execution sources and recorded results remain unchanged.
