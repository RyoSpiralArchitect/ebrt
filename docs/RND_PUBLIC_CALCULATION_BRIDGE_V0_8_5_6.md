# v0.8.5.6 — Public calculation bridge

Status: **ZERO-CALL VALIDATED; LOCK AND PREFLIGHT READY; LIVE NOT RUN**

The preceding [numeric diagnosis](RND_NUMERIC_REVISION_DIAGNOSTIC_V0_8_5_5.md)
retains three identical, strictly failing `45_CREDITS` final outputs. Its
public calculation text contains 5, 3, and 15, but fails the required format
and names correction evidence R6 instead of factor-bearing R4. Those results
remain unchanged. They motivate a test, not a finding that the model reliably
calculates correctly and then loses the result.

This successor first admits the calculation interface independently. It then
asks whether forwarding an **actual model-emitted numeric record**, without
its answer label, changes final-state repair on the same known case.
Implementation stays in one auxiliary
[runner](../public_calculation_bridge_v0_8_5_6.py). The core, prior runners,
parsers, grading contracts, locks, and executed artifacts are unchanged.

## One small comparison, after independent admission

Same cached Mistral snapshot, seed 0, temperature 0, fresh per-call KV state,
96 output tokens per call, no retries, no download, and no hosted API calls.
All four readiness checks must pass before the target case is reached.

| Order | Call | Purpose | Rendered input tokens |
| ---: | --- | --- | ---: |
| 1 | `state_format` | Existing literal STATE_JSON format check | 72 |
| 2 | `state_task` | Existing task-shaped strict state check | 657 |
| 3 | `calc_format` | Literal CALC_JSON format check | 66 |
| 4 | `calc_task` | Distinct calibration: base 2, current factor 4, factor source R4 | 592 |
| 5 | `calculation` | Actual public numeric record from the full target context | 592 |
| 6 | `raw_only` | Exact historical full-context baseline prompt | 648 |
| 7 | `operands_only` | Full context plus emitted base, multiplier, and factor-source ID | Dynamic; preview 764 |
| 8 | `product_bridge` | Same as operands-only, adding only emitted `product` | Dynamic; preview 774 |

The new prompts explicitly show the five-field CALC_JSON shape, require its
prefix and single line, and distinguish factor-bearing evidence from the
event authorizing that factor. The parser is the **unchanged v0.8.5.5
parser**: no repair of missing prefixes, multiline objects, renamed keys,
unknown IDs, booleans, or extra fields. The literal check and task-shaped
calculation check are separate; success at copying JSON is not task readiness.

Readiness failure closes the block after four calls. A target calculation
that cannot be parsed leaves the new raw-only reference intact but skips
both bridges: six calls, with the failure retained. A parsed target record
feeds both bridges even when its numeric or provenance checks fail. Semantic
gold is **not** the bridge-admission gate. The maximum is eight calls, not an
invitation to rerun failed probes.

## The bridge is narrow and unverified

The target model emits:

```text
base_count, multiplier, product, answer, rule_evidence_id
```

The compiler drops `answer` and forwards only allowlisted fields. It never
recalculates `product`, substitutes 15, selects the correct answer, or
corrects a known-but-wrong evidence ID. For example, a parsed product of 45
with rule ID R6 remains exactly that in the product bridge. Each record is
explicitly labelled unverified supplementary data to check against the raw
evidence, not an authoritative instruction.

Both bridge calls retain identical complete chronological raw evidence,
final question, and legacy STATE_JSON contract. Between `operands_only` and
`product_bridge`, **the product field is the only prompt difference**.
Changing the source answer label alone cannot change either provider-visible
prompt; its source hash still changes for provenance. Compared with raw-only,
the common record and its checking instructions are an additional scaffold.

This is a shared public calculation followed by separate fresh generations,
not three matched-compute algorithm arms. The new calculator prompt may
itself change behavior; its fields do not disclose what happened privately
inside the raw-only call.

## Fixed transformation, then durable actual inputs

The [lock](../policy_lock_public_calculation_bridge_v0_8_5_6.json) binds all
source dependencies, six actual fixed prompts, the compiler, parser, bounds,
schedule, model identity, and post-call contract. The
[preflight](../artifacts/public_calculation_bridge_v0_8_5_6/preflight.json)
records real cached-tokenizer rendering for those six prompts and two
**synthetic bridge previews**. Their bounded numeric values exercise the
compiler and tokenizer; they are neither actual model outputs nor the actual
future bridge payloads. Preview token counts are not live cost measurements
or a formal worst-case token bound.

During an authorized run, each actual bridge is deterministically compiled
from the recorded target calculation terminal. Its source hash, complete
prompt, rendered bytes, and token IDs are flushed and fsynced in the dispatch
journal **before** generation. A 4096-token input ceiling applies to the
actual rendering. Synthetic previews cannot replace an absent source.

The runtime rechecks the published source/lock/preflight commit, snapshot
files, environment identity, and tokenizer rendering. An exclusive execution
claim prevents another run under the same lock even with a different output
directory. Interruptions retain that claim and the available journal; they
do not authorize an automatic retry.

## Readouts and limits

- Readiness, generation completion, calculation parsing, calculation semantic
  checks, and final-state strict grades have separate fields and denominators.
- The unchanged strict final grader remains primary. Miss / over-edit /
  wrong-value diagnostics compare the registered public paths secondarily;
  an unchanged 45 remains a missed revision, not a successful calculation.
- All three final outputs, exact projected records, per-call tokens, latency,
  and finish reasons are retained. A generation error is not a strict repair
  or regression comparison.
- A parsed correct calculation with an incorrect final output localizes an
  observable interface gap. It does not identify hidden reasoning or a
  unique failure mechanism.
- If product-bridge passes while operands-only fails, retain the difference
  as a candidate for a replicated compiler intervention. If both pass, the
  product may be unnecessary for that observation. If neither passes, retain
  the null. No outcome automatically changes a compiler default.

One known contaminated case, one sample per prompt, and a fixed serial order
cannot establish causal superiority or general reasoning improvement. This
block contains **no EBRT gradient intervention**. It diagnoses a candidate
generation interface before adding controller machinery. Stable-reference
membership remains observable; stable fact values absent from the legacy
schema do not become measurable here.

## Preparation and operation

- [57 synthetic checks](../artifacts/public_calculation_bridge_v0_8_5_6/self_test.json): PASS.
  These include real orchestration with a mocked backend, durable dispatch
  before invocation, source-bound dynamic prompts, unchanged semantic errors,
  four- and six-call stops, generation errors, exact journal replay, and
  rejection of a second execution claim. They are not real model calls.
- Six fixed prompts and two synthetic previews rendered with the real cached
  tokenizer. New model generations: **0**.
- Self-test fingerprint:
  `84d62010bc9794a278cb0abebc7bdbc7f5f1e1a81b1370b9eb196dbf9c7bc25c`.
- Lock fingerprint:
  `6abc909dd9d2842308bbff1321f5125fb316c32231ed29989cd7a33d7bd7ce0b`.
- Preflight fingerprint:
  `3a67200f501e311b34e51919333d0998de3cbb63978caf4dedcfbb57d25394b5`.

```sh
python3 public_calculation_bridge_v0_8_5_6.py self-test
```

After authorization, publish the preparation commit on its non-main branch,
then invoke `run` with the cached snapshot, lock, preflight, exact commit,
fresh output directory, and `--execute-local-once`. No real `r01` result or
new execution claim exists at preparation. Do not substitute mock test
outputs for the live block.

After that separately authorized run:

```sh
python3 public_calculation_bridge_v0_8_5_6.py verify \
  artifacts/public_calculation_bridge_v0_8_5_6/r01/results.json \
  --lock policy_lock_public_calculation_bridge_v0_8_5_6.json
```

The portable verifier recomputes admission, actual-source projection, prompts,
grades, and journal correspondence without a model call. Recorded tokenizer
bytes are checked for internal consistency but not retokenized by that
verifier. Hashes are integrity checks, not signatures or proof of execution.
