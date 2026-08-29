# EBRT v0.8.2 Local Output-Diff Development Corpus

Status: **COMPLETE DEVELOPMENT CORPUS; NOT A BENCHMARK**

Artifact:
[`artifacts/local_output_diff_corpus_v0_8_2/r01/results.json`](../artifacts/local_output_diff_corpus_v0_8_2/r01/results.json)

Human-readable report:
[`artifacts/local_output_diff_corpus_v0_8_2/r01/report.md`](../artifacts/local_output_diff_corpus_v0_8_2/r01/report.md)

## Question

For several already-cached local models, what changes in the actual generated
text when the same synthetic late-event task is sent through either:

1. `direct_full_context`: chronological raw evidence with no external revision
   program; or
2. `ebrt_credit_first`: one real local backward pass, a bounded public
   actuator, and credit-first full-context regeneration?

This run records generated text, parsing, support lineage, and the public EBRT
trajectory. It is intended to produce concrete debugging examples for the next
algorithm iteration. It does not estimate a causal effect.

## Locked execution geometry

- Four synthetic revision cases.
- Two arms per case and one local generation per arm.
- Same model snapshot within each pair.
- `temperature=0`, `seed=0`, and a 48-token ceiling.
- Arm order counterbalanced by case index.
- No automatic retry.
- Semantic contracts fixed with the cases and evaluated only after generation.
- Native-state capture disabled for this breadth pass.
- Portable verification reruns deterministic compilation from each fixed task,
  reconstructs both arm invocations, and binds both request fingerprints before
  replaying parsing, grading, and aggregation.

The arm bundle differs in evidence order and explicit revision instructions.
Consequently, even a generated-output difference cannot be attributed to the
gradient placement alone.

## Models

| Model snapshot | Prompt mode | Parsed outputs | Admitted diagnostic scope |
| --- | --- | ---: | --- |
| `Mistral-7B-Instruct-v0.3-4bit@a4b8f...` | chat template | 8/8 | algorithm and output-lineage diagnosis |
| `Llama-3.2-3B-bf16@60a99...` | plain text | 0/8 | adapter/capability diagnosis only |
| `gemma-2-2b-4bit@2da706...` | plain text | 0/8 | adapter/capability diagnosis only |
| `SmolLM2-135M-Instruct@12fd2...` | chat template | 0/8 | adapter/capability diagnosis only |

The cached Llama and Gemma snapshots are base-model snapshots without a
tokenizer chat template. Plain-text rendering lets them execute, but it does
not turn them into instruction-following models. SmolLM executes its chat
template but copies schema placeholders or instructions instead of satisfying
the two-line contract. These 12 paired format failures are not counted as 12
EBRT reasoning losses.

## Aggregate result

| Measurement | Result |
| --- | ---: |
| Model snapshots | 4 |
| Paired cells | 16 |
| Local generation calls | 32 |
| Raw natural-language output changed | 16/16 |
| Parsed answer changed | 0/16 |
| Parsed support set changed | 4/16 |
| Both arms parsed | 4/16 |
| Any format failure | 12/16 |
| Any generation error | 0/16 |

Across all cells the direct arm passed 3 output contracts and the EBRT arm
passed 2. That aggregate is not a model-quality comparison because only the
four Mistral cells reached the common parsed-output surface.

## Mistral failure atlas

All eight Mistral outputs parsed, and both arms produced the same final answer
in every case. The differences were entirely in public support lineage.

| Case | Direct support | EBRT support | Contract category | Diagnostic |
| --- | --- | --- | --- | --- |
| release priority | `R1,R2,R5,R6` | `R6,R4,R2` | EBRT only passes | EBRT restores the missing required `R4` support. |
| registry route | `R2,R4,R6` | `R6,R4` | direct only passes | The actuator selected `R1` instead of required-support `R2`; top-k credit lost dependency coverage. |
| sensor fallback | `R1,R2,R4,R6` | `R6,R4` | direct only passes | The actuator selected `R2`, but the generator still omitted it; selection did not guarantee uptake. |
| unit reinterpretation | `R1,R2,R4,R6` | `R6,R4,R2,R1,R5` | both pass | The answer and required support pass, but preserve-only `R5` leaks into active support. The locked contract does not reject this extra citation. |

The important negative result is not merely `2 < 3`. It is that one controller
failure occurs before provider invocation and another occurs after it:

```text
public backward credit
  -> top-k actuator              # registry coverage loss
  -> model-visible instructions
  -> generated support lineage   # sensor uptake loss
```

The two boundaries need different repairs.

## Representative generated-output diffs

The full raw text and unified diff for every pair are stored in the aggregate
artifact. Representative excerpts make the observed boundaries concrete.

Mistral, release priority:

```diff
 ANSWER=PROVE
-SUPPORT=R1, R2, R5, R6
+SUPPORT=R6,R4,R2
```

Mistral, registry route:

```diff
 ANSWER=BLUE
-SUPPORT=R2, R4, R6
+SUPPORT=R6,R4
```

The plain-text Llama base snapshot produced free-form prose in the direct arm
and immediate empty output in the EBRT arm. In one registry case its direct
prose began with `The answer is BLUE`, but it never satisfied the locked
two-line schema. The Gemma base snapshot repeated task delimiters in the direct
arm and revision instructions in the EBRT arm. SmolLM repeated schema
placeholders in both arms. These are retained as generated-output examples,
but no semantic comparison is admitted for them.

## Bounded improvement hypotheses

### H1 — Role-stratified allocation before larger top-k

The current actuator ranks scalar evidence credit and takes a fixed top-k. In
the registry case, a context node displaced a required-support node. The next
compiler should reserve a minimal allocation slot for distinct public evidence
roles before filling the remaining budget by credit magnitude.

This uses caller-supplied public roles, not post-call semantic gold. It must be
described as structured public control, not autonomous discovery of the true
dependency graph.

### H2 — An explicit uptake receipt, not more prompt emphasis

In the sensor case, `R2` was already present in the actuator yet disappeared
from the output. Increasing its scalar weight would not identify the broken
boundary. A minimal next step is to compile a small fact-local reinspection
plan into the same one-call request and require the output to bind each active
decision fact to the evidence it actually retained.

Surrogate selection and provider uptake must remain separate receipt fields.

### H3 — Keep `PRESERVE` outside active support

The unit case cites stable-format evidence `R5` as decision support. The public
program should expose preserved constraints in a separate field rather than
placing them near active support instructions. This is a schema/channel repair,
not evidence that a stronger gradient is needed.

### H4 — Add an adapter-readiness gate

Before any model contributes to algorithm statistics, run a network-local
capability canary for prompt rendering and the two-line output contract. A
base-model or schema-compliance failure should stop at
`ADAPTER_OR_CAPABILITY_DIAGNOSTIC`; it must not update EBRT controller
parameters.

### H5 — The current answer surface is saturated

The capable model produced the correct final choice in both arms for all four
development cases. The current cases can diagnose lineage but cannot reveal an
answer-level control effect. New answer-ambiguous cases must be frozen before
execution rather than tuned on this contaminated corpus.

## Next minimal experiment

`v0.8.3` should be a small provider-uptake canary, not a new architecture:

1. Freeze this `r01` artifact unchanged.
2. Add a role-stratified coverage floor to the existing actuator compiler.
3. Keep surrogate credit, compiled selection, provider output, and post-call
   grade as four separate artifacts.
4. Compare current top-k and role-stratified compilation first on fresh cases
   with one instruction-capable local model.
5. Include at least one case where answer choice, not only support lineage, is
   genuinely ambiguous before the late event is applied.
6. Expand to a second instruction-capable model only after its adapter-readiness
   canary passes.

This preserves the central line: one monolithic reasoning core, a small corpus
runner, and instrumentation that exists to improve the module rather than to
manufacture a cross-model claim.

## Claim boundary

- The public trajectory is an inspectable surrogate, not private model
  reasoning.
- No gradient crosses the model adapter or sampled text.
- Raw output changes do not identify which bundled intervention caused them.
- Format failures do not measure EBRT reasoning quality.
- The corpus is synthetic, small, and development-contaminated.
- No general reasoning improvement, causal superiority, or cross-model
  regularity is claimed.
