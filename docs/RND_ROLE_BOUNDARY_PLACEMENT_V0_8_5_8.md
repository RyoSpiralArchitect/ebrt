# v0.8.5.8 — Role-boundary instruction placement

Status: **PREPARATION; THREE SEPARATE BACKEND PROFILES; NO RESULT CLAIM YET**

The [previous source-field ablation](RND_SOURCE_FIELD_ABLATION_V0_8_5_7.md)
changed a repeated support omission into repeated support/event overlap.
All four strict outputs failed. This successor tests one narrow interface
change before touching the backward controller or core monolith.

## One change, no new evidence

Both conditions retain the no-source numeric record compiled from the same
old actual calculation. The baseline is the exact previous no-source prompt.
The alternative moves these five existing consecutive lines from their early
position to immediately after `END_PUBLIC_CALCULATION_RECORD`:

```text
decision_support_ids must contain only evidence that directly determines answer.
revision_event_id must contain the late correction that authorizes revision.
preserved_constraint_ids must contain stable constraints that must remain unchanged but do not determine answer.
Keep the three evidence destinations pairwise disjoint.
Do not cite superseded evidence in any destination.
```

Nothing is duplicated, rewritten, or added. The line multiset, byte length,
raw evidence, numeric record, final question, choices, and output schema stay
fixed. No case-specific evidence IDs, correct answer, or gold support list is
added. The numeric product is not recalculated, and the source answer label
is not forwarded. The unchanged strict parser and grader remain primary.

The protocol is implemented in one auxiliary
[runner](../role_boundary_placement_v0_8_5_8.py). Old code, locks, and results
remain frozen. There is no core, UI, gradient, or default-compiler change.

## Per-backend sealed block

Each backend has the same six public input prompts:

1. Existing literal STATE_JSON format readiness.
2. Existing task-shaped strict readiness.
3. Early role instructions, pair 1.
4. Late role instructions, pair 1.
5. Late role instructions, pair 2.
6. Early role instructions, pair 2.

Failed readiness stops after two calls. A runtime error stops immediately
and is retained; no automatic retry, fallback model, or prompt repair is
permitted within the block. Every backend has its own execution claim.
Interruptions keep the claim and available journal. The maximum is six
generations per backend, eighteen across the three planned backends, with
four final-state quality cells per admitted backend. There is no new
calculation generation. These are contaminated, descriptive AB/BA repeats,
not independent fresh-case evaluation or proof of general causal benefit.

| Backend | Fixed generator | Execution policy |
| --- | --- | --- |
| Mac MLX | Mistral-7B-Instruct-v0.3 4-bit, snapshot `a4b8f870474b0eb527f466a03fbc187830d271f5` | seed 0, temperature 0, 96 output tokens, fresh KV per call |
| Furnace | Mistral-7B-Instruct-v0.3, snapshot `c170c708c41dac9275d15a8fff4eca08d52bab71` | managed TensorRT-LLM PyTorch backend, bf16, seed 0, temperature 0, 96 output tokens, KV block/partial reuse disabled |
| OpenAI API | `gpt-5.6-sol` | low reasoning effort, 2048 total output tokens, no prior response ID or tools, no schema-constrained decoding, no retries, store false |

These are different weights/quantization, tokenizers, execution environments,
and budgets. Evaluate early versus late **within each backend**. Do not pool
the cells into an algorithm score or rank backends as matched-compute models.
An API model name is not a locally verifiable weight hash. API generations
are not claimed deterministic or greedy.

## API budget and remote boundary

The API profile pre-counts the four unique inputs with the actual model and
reasoning setting; repeated prompts reuse their counts. These metadata/count
requests are separate from the six possible generation requests. The SDK has
zero retries and a 60-second timeout. Every dispatched call reserves its full
input count plus maximum output cost before generation, durably in the
journal; uncertain outcomes retain their reservation and stop the run.

The hard block ceiling is $0.40 at the checked rate card. Input is reserved at
$5/M, conservatively covering the $4/M rate and 1.25x cache-write multiplier;
output is reserved at $20/M. These rates were checked on 2026-10-20 against
the [official model page](https://developers.openai.com/api/docs/models/gpt-5.6-sol).
Accounting follows the no-retry/reservation principle in the
[official budget example](https://developers.openai.com/cookbook/articles/per_run_spending_controller_responses_api#check-the-budget-before-each-request).
This is a bounded experiment at a recorded rate card, not a billing invoice
or a perpetual price guarantee. Secrets are read from the environment and
never placed in the protocol, journal, profile, or repository.

Furnace follows its managed-runtime policy: `spiral-local-llm doctor`, no
environment repair or package mutation, no interference with other jobs,
and a separate checkout. Model weights are already cached; no model download
is planned. Its bf16 execution is not assumed equivalent to the Mac's 4-bit
MLX snapshot. TensorRT-LLM failure is retained as a backend-boundary result;
it does not authorize silently switching to another runtime.

## Lock and verification

The [protocol](../policy_lock_role_boundary_placement_v0_8_5_8.json) binds all
eleven source files, the predecessor records, exact six prompts, schedule,
post-call contract, and claim boundaries. Backend profiles separately bind
their input rendering/request bytes, runtime versions, model identity, local
file hashes where available, and output/cost settings. Sources, protocol and
profile must be committed and pushed before that backend's execution.

The 36-check synthetic self-test covers exact baseline-dispatch matching,
position-only transformation, role-overlap rejection, four-final denominators,
AB/BA normalization, forged grades, request binding, readiness stops,
durable dispatch, interruption retention, execution-identity reuse rejection,
API missing usage/incomplete responses/model mismatch/tier mismatch/excess
usage, and sanitized errors with no retry. It does not establish model
readiness. Mac tokenizer preflight yields 72/657 readiness tokens and 747
tokens for every early/late final prompt.

```sh
python3 role_boundary_placement_v0_8_5_8.py self-test
python3 role_boundary_placement_v0_8_5_8.py verify \
  artifacts/role_boundary_placement_v0_8_5_8/mlx_r01/results.json \
  --protocol policy_lock_role_boundary_placement_v0_8_5_8.json
```

The portable verifier checks recorded inputs, source binding, reservations,
readiness, strict grades, pair comparisons and the dispatch journal without
new generation. It does not authenticate execution or rerun tokenization.
No strict contract is relaxed to admit malformed outputs. Stable reference
membership is observable; stable fact values not emitted by the schema are
still unobservable.
