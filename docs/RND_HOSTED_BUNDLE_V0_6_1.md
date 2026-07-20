# EBRT v0.6.1 — Hosted Bundle Execution

Status: **FIVE-CALL BLOCK COMPLETE; ARTIFACT VALID; GATE HELD**

## Result in one sentence

The sealed v0.5.5 public substrate reached a real GPT-5.6 final output and D
passed the full strict contract, but the matched control-placement effect was
null and P failed its preregistered exact-lineage endpoint, so the overall gate
remains `HOLD_V0_6_HOSTED_BUNDLE_GATE`.

## Frozen protocol

The block used one known synthetic hackathon-strategy case. It is an
engineering regression over a contaminated case, not a fresh quality
benchmark.

- model: `gpt-5.6-sol`
- reasoning effort: `low`
- maximum output tokens: `4608`
- order: `P -> A -> B -> D -> C`
- attempts: one per arm, no retry
- raw horizon: R1-R5 for P; byte-identical R1-R6 for A/B/C/D
- gold: hashed before execution, semantically parsed only after all five
  attempts completed
- primary effect contrast: D versus norm-, sparsity-, sign-, lane-budget-,
  and merge-budget-matched C

The provider never received treatment labels, blinded IDs, a separately
loaded grader/gold artifact, a downstream grade, or a prior provider output.
B/C/D did receive the same contaminated, answer-adjacent oracle typed DAG.
Their public-control treatments differed while the raw evidence and DAG were
held fixed.

Policy lock:
`51bd00343dafb4dd9bc0c42dc95c1df1b6f8b7132907e283d84a82b237801072`

Validated result:
`a814b54a23faef07e301aa676411789cfb62154c07e5ad373f779ed67621954b`

## Endpoint results

| Arm | Intervention | Answer | Strict grade | Exact diagnostic |
| --- | --- | --- | --- | --- |
| P | R1-R5, no program | `POLISH` | FAIL | unexpected inherited R2 and total R2 on `demo_centerpiece` |
| A | R1-R6, no program | `PROVE` | FAIL | missing direct and total R4 on `final_priority` |
| B | typed DAG, zero controls | `PROVE` | PASS | all exact lineage and program-consistency checks pass |
| D | typed DAG, exact v0.5.5 placement | `PROVE` | PASS | all exact lineage and program-consistency checks pass |
| C | typed DAG, matched sham placement | `PROVE` | PASS | all exact lineage and program-consistency checks pass |

Independent decision endpoints:

```text
run                         COMPLETE
P pre-event                 FAIL
P stale regrade             FAIL
public surrogate            PASS
D strict hosted path        PASS
D vs C matched placement    NULL
overall decision            HOLD_V0_6_HOSTED_BUNDLE_GATE
```

All five provider calls completed and returned exact usage receipts:

```text
API calls             5
input tokens          36,722
output tokens          2,045
reasoning tokens         466
total tokens          38,767
aggregate latency     45,935.371 ms
```

The raw A arm used 1,796 total tokens. B used 11,447 and D/C each used
11,854, or roughly 6.4-6.6 times A, without a D-over-B/C output benefit. This
is a measured cost of the current verbose public-program projection, not a
matched-compute quality comparison.

## What the block established

### 1. The hosted bridge exists

D consumed the exact sealed public bundle, passed through the stop-gradient
provider projection and one full-context regeneration, returned `PROVE`,
invalidated R3, preserved R5 / `THREE_MINUTE_NARRATED`, and closed the exact
direct, inherited, and total fact-local support contract.

This establishes one real, auditable substrate-to-output execution path. It
does not establish that D caused a better answer.

### 2. Raw full-context regeneration nearly closed the semantic contract

A independently reached `PROVE`, invalidated R3, preserved R5, and correctly
constructed the `demo_centerpiece` lineage. It failed only because R4 was not
also attached directly to `final_priority`.

This is a lineage-factorization miss, not an answer-label failure.

### 3. The supplied typed DAG dominated the tested placement channel

B, D, and C emitted byte-identical public outputs with the same fingerprint:

`3b5e0946dae58f3931932942ec54023c36206d98557817dec2200542119914ab`

Zero control, exact gradient-derived placement, and matched sham placement
therefore had no observed output difference. The one positive strict contrast
is D versus raw A; D is null versus B and C.

The most direct interpretation is that the typed DAG was sufficient to close
the public output contract, while the current signed-displacement projection
was observationally silent. Because the prompt required exact DAG
instantiation and required target values to come only from raw evidence, this
block did not provide a sensitive output channel through which placement could
express itself.

### 4. Exact lineage is stricter than answer correctness

P returned the preregistered `POLISH` answer and preserved the video
constraint. It additionally declared that `demo_centerpiece` depends on
`final_priority`, causing R2 to be inherited into the demo fact. The gold
expected no such inheritance, so P failed.

The artifact proves an exact contract mismatch. It does not prove that this
alternative public factorization is logically or semantically unreasonable.
This is a representation-identifiability boundary that the Inspector should
show explicitly rather than collapse into a generic red answer badge.

## Decision and next bottleneck

The run is not rerun, the P gold is not relaxed, and the null D-versus-C result
is not tuned away. v0.6.1 remains the canonical five-call artifact.

The next algorithmic question is not another same-case coefficient search. It
is whether EBRT can expose a bounded, allowlisted actuator whose placement can
change a provider-visible decision without pre-specifying the entire accepted
lineage graph. A successor should therefore separate:

1. a partial structural scaffold that does not already determine the endpoint;
2. a typed control channel with a declared provider-visible action;
3. a matched sham that preserves information and geometry; and
4. a fresh paired suite whose strict endpoint remains locally compiled.

Before that fresh quality question, v0.6.2 can productize this artifact as a
Reasoning IDE view with independent badges for answer, invalidation, stable
fact, exact lineage, program consistency, and matched effect. The useful story
is not one green score: it is that P and A look correct at answer level while
the debugger exposes two different dependency defects, and that D's apparent
success is not credited to placement when B and C match it exactly.

A small v0.6.3 provider-actuator uptake canary should then precede the proposed
100-call v0.7 quality suite. It should hold raw context and an admissible
partial topology fixed, compile displacement into an explicit truth-neutral
operation such as bounded evidence-reinspection order or budget, and require
an observable D-versus-C difference in a preregistered public field before
quality evaluation is allowed. If zero, sham, and exact placement remain
identical, freeze this hosted actuator projection as inert rather than scaling
it up.

## Claim boundary

- This is one contaminated, unbalanced, time-confounded block.
- The public DAG is case-specific oracle structure, not autonomously
  discovered semantics.
- Gradients exist only inside the local public differentiable substrate; none
  crosses GPT, JSON, provider parsing, or grading.
- D strict PASS establishes a working path, not causal superiority.
- B/D/C identity is a null observation for this protocol, not a theorem that
  external differentiable control can never affect generation.
- P/A exact-lineage failures are frozen contract mismatches, not proof that
  their natural-language answers are wrong.
- Sanitized receipts and local hashes provide internally reconstructable
  evidence, not cryptographic provider attestation.

## Artifact

The canonical directory is
`artifacts/hosted_bundle_execution_v0_6_live_r01/`.

It contains the frozen provider inputs, five sanitized call receipts, durable
attempt journal, projection bundle, local grades and output diff, report, and a
manifest binding every artifact byte. The live runner independently rebuilt
the projection, closure, grades, report, journal, and manifest before returning
success.

Portable canonical-snapshot verification is available with only the Python
standard library:

```bash
python3 -I -S verify_hosted_bundle_v0_6_1_portable.py verify
python3 -I -S verify_hosted_bundle_v0_6_1_portable.py self-test
```

The portable verifier is intentionally post-run and non-generative. It pins
the policy, manifest, result, and every artifact byte; checks their recorded
source, runtime, projection, provider-input, attempt, receipt, usage, grade,
and outcome bindings; and does not import project/provider packages, read the
current v0.5.5 source tree, call a network, or gate on the verification host.
It validates the historical v0.5.5 receipts recorded in the frozen projection
bundle rather than pretending to rederive that predecessor from later fixed
bytes. This establishes canonical snapshot consistency, not current-tree
mechanism reproducibility, provider authentication, or a fresh semantic
regrade.

`run_hosted_bundle_v0_6.py validate` remains the exact historical
producer-tree/runtime rederivation path. Use it only from the frozen producer
source graph and recorded runtime; failure on a later v0.5.5 tree is expected
and must not be repaired by changing the v0.6.1 lock or live artifact.

The live command is historical evidence, not an instruction to rerun the
one-shot block.
