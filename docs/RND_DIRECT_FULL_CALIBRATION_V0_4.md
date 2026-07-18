# EBRT v0.4: Direct vs Full Calibration

## Status and decision

This is a complete, non-promotional `DEV_DRAFT` calibration over the existing
10-case v0.4 development suite. It is deliberately contaminated by prior
development and is not a holdout.

The result rejects the current six-step public-card Full Restart as EBRT's
default quality scaffold on these cases:

- `direct_raw_fixed_revision`: 30/30 strict successes and 10/10 stable cases;
- `full_restart`: 4/30 strict successes and 1/10 stable cases;
- paired outcomes: 26 Direct-only, 0 Full-only, 4 both;
- the only stable Full success was the irrelevant-late-evidence control.

The next phase therefore does **not** optimize selective replay. Selective
replay remains an unranked diagnostic or future efficiency ablation until the
public-state representation can preserve Direct-level quality. The immediate
research target is to isolate whether the failure comes from lossy card
compression or from repeated sequential commitments.

This does not show that external reasoning scaffolds generally fail. The Direct
arm itself receives a fixed revision envelope and a strict public output schema.
It shows that this particular staged public-card execution underperformed
fixed-envelope Direct in answer and audit-record quality on this DEV suite.

## Why this calibration was inserted

The prior two-case v0.4 canary established a live observer/card bridge and found
that Full Restart passed both cases while selective replay passed only one. That
was enough to expose a checkpoint-sufficiency failure, but it did not answer a
more basic question:

> Does the external staged scaffold improve final output quality over one
> stateless call that can read the same raw evidence at once?

If Full had won, it would have been reasonable to treat Full as the primary
quality mechanism and selective replay as an optional cost optimization. The
calibration instead found the opposite. That changes the algorithmic priority:
representation sufficiency now comes before replay-floor optimization.

## Locked comparison

Both arms begin after the same fixed, summary-free revision annotation. The
annotation is read from the input fixture, not the gold file, and exposes only:

```text
late_evidence_id
relevant
revision_cue
invalidated_evidence_ids
```

It excludes topic, stance, confidence, public summary, answer, required facts,
required evidence, replay floor, grader output, and all gold fields. This holds
observer performance out of scope and focuses the contrast on the
generation/execution layer; staging, instructions, and aperture still differ.

| Arm | Execution |
| --- | --- |
| `direct_raw_fixed_revision` | One stateless Responses call sees the question, choices, fixed slots, all six raw evidence chunks in order, and the fixed revision envelope. |
| `full_restart` | Six stateless Responses calls start from an empty card. Each sees the previous public card, one new raw chunk, the fixed slots, and the same envelope. Raw content omitted from a public card is unavailable to later calls. |

Late raw text appears exactly once in each arm. The Full implementation prevents
the late evidence ID from becoming active support before that raw chunk is
presented. Invalidated IDs may be marked but may never be active support.

The interfaces necessarily use different fixed instructions. Direct receives
the revision envelope once; Full receives the same metadata in every staged
call. These differences are part of the tested protocol and prevent a claim
that public-card structure alone caused the result.

### Provider and state lock

Both arms use:

- `gpt-5.6-sol`;
- Responses structured output parsed into the same `ReasoningCard` schema;
- `reasoning.effort=low`;
- service tier `default`;
- `store=false` and no `previous_response_id`;
- SDK retry count zero and one counted attempt per logical call;
- truncation disabled;
- the same independent final-card grader.

No private chain-of-thought, opaque reasoning item, raw response object, API
key, or Authorization header is written to the bundle.

### Budget contract

The only matched budget is the nominal cumulative output-token ceiling:

```text
Direct: 1 call  x 4608 max_output_tokens = 4608
Full:   6 calls x  768 max_output_tokens = 4608
```

There is no padding. Input tokens, realized output tokens, reasoning-token
detail, calls, latency, price, and server compute are measured rather than
forced equal. “Completion-ceiling matched” must not be shortened to
“compute-matched” or “token-matched.”

### Trials and grading

The run used all 10 existing DEV cases and three trials per case. Case order was
rotated by trial, and arm order was balanced 15 Direct-first / 15 Full-first.
There is no model seed claim. Gold was attached only after all provider calls
finished.

The primary run-level endpoint is strict `machine_success`, requiring all six:

1. exact answer;
2. exact required decision facts;
3. exact stable facts;
4. required evidence present;
5. invalidated evidence absent from active support;
6. expected invalidated evidence marked separately.

The primary decision unit is a case-level stable pass: at least two successes
in the three locked trials. Intermediate Full cards are diagnostic only because
Direct has no matched intermediate output.

## Execution integrity

All 210 calls completed:

- 30 Direct receipts and 180 Full receipts;
- requested and returned model `gpt-5.6-sol` on every call;
- returned service tier `default` on every call;
- no retry, refusal, incomplete response, schema failure, or local citation
  boundary failure;
- exact provider usage on every receipt;
- provider audit order exactly equal to stored trace order;
- 10 source/fixture/policy hashes and five generated-artifact hashes verified
  against the manifest.

The inherited v0.4 client classifies all SDK call exceptions under one broad
receipt label. No such failure occurred here. The protocol does not claim exact
failed-call usage or true transport classification for a future failed run.

## Result

### Output quality

| Metric | Direct | Full |
| --- | ---: | ---: |
| Strict machine success | 30/30 | 4/30 |
| Answer exact | 30/30 | 15/30 |
| Evidence consistent | 30/30 | 4/30 |
| Required facts exact | 30/30 | 13/30 |
| Stable facts exact | 30/30 | 30/30 |
| Required evidence present | 30/30 | 4/30 |
| Forbidden invalidated support absent | 30/30 | 30/30 |
| Expected invalidation marked | 30/30 | 30/30 |
| Mean citation precision | 0.740 | 0.854 |
| Mean citation recall | 1.000 | 0.652 |

Full's higher citation precision is not a quality win. It mostly reflects a
smaller support set while required evidence is missing. Direct cited extra
evidence in 27/30 runs, so its 30/30 result is evidence-complete rather than
minimal-provenance evidence.

Eleven Full outputs had the correct answer but failed the public fact/evidence
contract. The other 15 Full failures also had the wrong answer. The distinction
matters: Full underperformed Direct in both answer quality and audit-record
quality.

### Paired and case-stable outcomes

| Outcome | Runs |
| --- | ---: |
| Direct only | 26 |
| Full only | 0 |
| Both pass | 4 |
| Neither pass | 0 |
| Incomplete | 0 |

| Case family | Direct strict | Full strict | Full answer exact | Stable outcome |
| --- | ---: | ---: | ---: | --- |
| Lookup-key revision | 3/3 | 0/3 | 2/3 | Direct only |
| Entity-alias revision | 3/3 | 0/3 | 0/3 | Direct only |
| Unit revision | 3/3 | 0/3 | 1/3 | Direct only |
| Timestamp revision | 3/3 | 0/3 | 0/3 | Direct only |
| Source-fallback revision | 3/3 | 1/3 | 3/3 | Direct only |
| Dependency-chain revision | 3/3 | 0/3 | 0/3 | Direct only |
| Rule revision | 3/3 | 0/3 | 3/3 | Direct only |
| Source-precedence revision | 3/3 | 0/3 | 3/3 | Direct only |
| Relevant same-answer revision | 3/3 | 0/3 | 0/3 | Direct only |
| Irrelevant late control | 3/3 | 3/3 | 3/3 | Both |

The repeated trials do not create 30 independent task families. They measure
stochastic stability for 10 already-known DEV cases. No population-level or
holdout inference is made.

### Measured usage

| Measurement | Direct | Full | Full / Direct |
| --- | ---: | ---: | ---: |
| API calls | 30 | 180 | 6.00x |
| Input tokens | 22,041 | 132,097 | 5.99x |
| Output tokens | 4,442 | 41,864 | 9.42x |
| Total tokens | 26,483 | 173,961 | 6.57x |
| Reasoning-token detail | 0 | 17,502 | not meaningful as a ratio |
| Median arm latency | 3.390 s | 34.259 s | 10.11x |
| Sum of recorded call latency | 118.8 s | 1,042.5 s | 8.78x |

The recorded Direct reasoning-token detail of zero must not be interpreted as
zero server reasoning or zero compute. It is only the provider's returned usage
field for these calls.

Neither nominal cap bound: the largest Direct output was 170 tokens against a
4,608 cap, and the largest Full card was 541 against 768. Across all runs,
Direct used 3.21% and Full used 30.28% of their equal aggregate ceilings.
Matching a ceiling therefore did not equalize realized generation.

## Bottleneck diagnosis

The failure pattern is structured:

- stable independent facts were exact in 30/30 Full outputs;
- invalidation marking and stale-support exclusion were correct in 30/30;
- required evidence survived in only 4/30;
- every one of the nine actual revision families failed the stable strict gate;
- the irrelevant no-op was the only stable Full pass.

The leading inference is **lossy public-state factorization**. This is strongly
supported diagnostically but not yet causally isolated.

In the current Full protocol, public support citations—the union of card-level
`evidence_ids` and fact-level evidence citations—do two incompatible jobs:

1. they are an auditable citation set for the current decision;
2. they control which prior evidence can remain available to the next call.

A mapping, threshold, conversion factor, precedence rule, or dependency edge may
not determine a decision slot when first seen. The card therefore writes
`UNKNOWN` and may retain only an ID—or drop the evidence entirely. Later, a
correction supplies the missing key, but the raw semantics needed to recompute
the dependent value no longer exist in the aperture.

Examples:

- route code: the route table arrived before the corrected code; Full later knew
  `B2` but could not reliably reconstruct `B2 -> BLUE`;
- alias: the score table disappeared before `Luma -> BX7`, leaving score
  `UNKNOWN`;
- timestamp and dependency chain: the boundary or mode-to-valve mapping vanished
  before the corrected root value arrived;
- source fallback and rule/source-precedence cases often kept the right answer
  but omitted the threshold, return rule, or precedence evidence needed for an
  auditable final record.

This also explains why a bare evidence ID is insufficient. A citation is not a
lossless semantic memory.

The trace exposes a strong recency signature. At the second card, Full retained
the first card's active support in only 7/30 runs. By the final card, raw
position 1 survived in 1/30 outputs, position 2 in 15/30, position 4 in 14/30,
position 5 in 30/30, and the late position 6 in 27/30. Restricting the count to
gold-required evidence, position 1 survived in 1/24 opportunities, position 2
in 14/24, position 4 in 0/3, and late evidence in 27/27. Because the next
aperture is built from surviving support plus the new chunk, a dropped raw fact
cannot re-enter later.

The mandatory prefix `current_answer` is another candidate failure amplifier.
For the relevant-nonflip family, Full ended with the correct revised
`reading=84` fact but kept the earlier `CONTINUE` answer in all three trials.
Future state should permit `UNRESOLVED` before the dependency closure is
sufficient rather than forcing an early closed-set commitment.

Stable-fact success also needs a position caveat: the stable distractor/fact is
the fifth chunk in every current case, immediately before the late event. Its
30/30 preservation does not establish long-horizon memory.

## Research decision

The current result supports the following repository-level decision:

1. keep one-shot Direct as the quality reference on the current suite;
2. freeze the negative Full result rather than tuning it after seeing outcomes;
3. pause selective replay and replay-floor optimization;
4. repair or bypass the public-state bottleneck first;
5. move to fresh harder DEV tasks because current Direct is saturated at 30/30.

Selective replay has no reliable way to recover a dependency absent from both
its checkpoint and raw replay slice. It may return later as an efficiency
mechanism only after the representation and floor policy guarantee availability
and pass the Direct non-degradation gate.

## Next causal experiments

### 1. No-revision-envelope one-shot raw control

The current Direct arm receives the fixed revision envelope. Add
`direct_raw_no_revision`: one stateless call over the same ordered raw evidence,
answer choices, slots, schema, model, and cap, but without relevance, revision
cue, or invalidated-ID metadata. It remains a structured-output control with
arm-specific instructions, not a literally unassisted API request.

Run this primarily on fresh harder DEV cases. The existing suite is saturated,
so another 30/30 would verify robustness but could not demonstrate a quality
gain.

### 2. Compression ablation

Add `staged_cumulative_raw`: the same six calls, evidence order, envelope,
output schema, and arm-order rotation as Full, but every call can read all raw
evidence seen so far.

- If cumulative raw recovers Direct, the card-only aperture/information loss is
  a causal contributor and becomes the leading bottleneck under matched staging.
- If it still fails, repeated sequential commitments or arm-specific prompt
  dynamics become the leading explanation.

### 3. Sufficiency-first public state

Only after the compression control, test a new representation with:

- an immutable evidence ledger separate from the compact decision card;
- typed dependency edges for mappings, thresholds, unit transforms, fallbacks,
  source precedence, and rule composition;
- a public sufficiency certificate for each required decision slot;
- fail-closed raw-evidence retention when a future dependency is unresolved;
- the Reasoning Card as a view over the ledger, not the ledger itself.

Concretely, separate `support_pool` (lossless available memory) from
`answer_support` (minimal final provenance). Expanding case-specific slots until
all current fixtures pass would overfit the suite; a generic public fact and
dependency ledger is the stronger algorithmic test.

The first gate is non-degradation: stable success on all 10 current cases with
no Direct-only case. A later quality claim requires fresh harder tasks on which
the no-revision-envelope one-shot raw control is not already at ceiling.

## Claim ledger

Supported now:

- all 210 locked calls completed with exact sanitized usage;
- one-shot fixed-envelope Direct passed all 30 runs;
- current staged Full passed 4/30 and had no Full-only paired success;
- Direct was stable on all 10 cases while Full was stable only on the no-op;
- Full preserved stable facts and invalidation hygiene but frequently lost
  required dependency evidence;
- the current public-card Full protocol is not a viable primary quality scaffold
  on this DEV suite.

Not supported:

- plain API inference generally beats external reasoning scaffolds;
- the revision envelope is unnecessary;
- public-card compression alone caused the failure;
- actual compute, cost, or reasoning work was matched;
- Direct generalizes beyond these contaminated DEV cases;
- selective replay is formally ranked by this two-arm experiment;
- EBRT improves or edits private chain-of-thought or model hidden state.

## Reproduce and inspect

Offline contract checks:

```bash
python3 benchmark_direct_full_calibration_v0_4.py self-test
```

Two-case API plumbing smoke:

```bash
python3 benchmark_direct_full_calibration_v0_4.py live-smoke \
  --output benchmark_results/v0_4_direct_full_live_smoke
```

Locked 10-case, three-trial DEV calibration:

```bash
python3 benchmark_direct_full_calibration_v0_4.py live-dev \
  --output benchmark_results/v0_4_direct_full_dev
```

The committed evidence is under
`artifacts/benchmark_direct_full_calibration_v0_4_dev/`. Start with
`manifest.json`, `benchmark_report.md`, and `arm_rows.csv`; use `results.json`,
`traces.jsonl`, and `calls.jsonl` for full audit.

The live integration follows OpenAI's official guidance for
[Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
and the locked GPT-5.6 Sol model configuration described in the
[model guidance](https://developers.openai.com/api/docs/guides/model-guidance?model=gpt-5.6-sol).
