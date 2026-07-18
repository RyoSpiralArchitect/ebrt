# EBRT v0.4: Language Replay Bridge

## Status

EBRT v0.4 is a **non-promotional DEV_DRAFT**. It is the first repository
version that executes a live GPT-5.6 public-state replay loop end to end. It
does not edit hidden states, request or store private chain-of-thought, or
establish a general LLM reasoning improvement.

> **Follow-up:** the proposed repeated 10-case calibration is now complete.
> One-shot fixed-envelope Direct passed 30/30 strict outputs while staged Full
> passed 4/30. This supersedes the “improve selective replay next” direction:
> repair or bypass public-card factorization first. See
> [`RND_DIRECT_FULL_CALIBRATION_V0_4.md`](RND_DIRECT_FULL_CALIBRATION_V0_4.md).

The v0.1-v0.3.1 mechanism, instrumentation, policies, locks, fixtures, and
artifacts remain unchanged. v0.4 is a separate language bridge layered on the
existing `SemanticAdapter` boundary.

## Executed bridge

The live path is:

```text
raw initial evidence
  -> public Reasoning Card after each chunk
  -> late evidence
  -> GPT-5.6 structured semantic observer over the terminal public card
  -> pre-outcome ReplayPlan
  -> public checkpoint selection
  -> suffix-only regeneration
  -> machine-graded final public card
```

The observer does **not** receive the raw initial-evidence texts or the full
card trace. Its aperture is the question, answer choices, terminal public card,
late evidence, and a roster of prior evidence IDs. Its free-form public summary
is persisted for audit only and is never passed to a card generator. The
generator receives only the previous public card, current evidence, and bounded
revision fields: the late evidence, relevance/revision cue, and explicitly
invalidated IDs. On the final late-evidence step, the raw late text appears only
as current evidence rather than being duplicated in revision context.

The observer and card generator both use `gpt-5.6-sol` through the Responses
API with strict structured outputs, `reasoning.effort=low`, SDK retries
disabled, `store=false`, no `previous_response_id`, and truncation disabled.
Every call is stateless except for the public card explicitly included in the
next request. Raw response objects and opaque reasoning items are not written
to artifacts.

## Public state contract

A card exposes only:

- checkpoint ID;
- claim and topic;
- bounded stance, confidence, and revision cue;
- one answer from the case's closed answer set;
- active evidence IDs and separately invalidated evidence IDs;
- fixed public decision slots with enumerated allowed values and citations.

The fixed slot/value surface was added during DEV after a first diagnostic
showed that free-form fact names could not be graded by exact string matching.
This is an external decision record, not a request for a hidden derivation.

Provider output fails closed on an unknown answer, unknown evidence ID,
unknown or duplicate decision slot, disallowed value, missing required slot,
or invalidation not named by the public revision context. Evidence IDs available
for active support come only from support actually retained in the previous
public card/facts, the current evidence, and public revision IDs. Merely having
appeared in an older prefix is not sufficient. Invalidated IDs can be marked
separately but cannot be used as active card or fact support.

This is a citation-level enforcement boundary. The schema cannot prove that
uncited prose or a value was not semantically influenced by invalidated text.

## Pre-outcome replay plan

The controller freezes the plan before any comparison lane executes. It can
read only:

- the shared initial public-card trace;
- the arrived late evidence;
- the GPT semantic observation;
- the locked event threshold.

The semantic observer inside that controller has the narrower terminal-card
aperture described above. Neither layer can read gold, a lane output, or a
grader result. The decision input and plan both receive SHA-256 fingerprints,
and every lane must carry the same plan fingerprint.

If the observer identifies an invalidated evidence ID, the controller selects
its earliest evidence step `j`:

```text
selected_anchor_step   = j
execution_replay_floor = j
checkpoint_step        = j - 1, or null when j = 0
```

If a relevant event has no safe anchor, v0.4 fails closed to a full restart.
If the late evidence is irrelevant, selective replay performs no backward
replay and processes only the late chunk. The trajectory-horizon candidate is
recorded as shadow data and never changes v0.4 execution.

## Matched lanes

All lanes share one physically executed initial trace and one semantic-observer
call. Post-event generation uses the same model, prompt, response schema,
reasoning effort, output cap, and evidence order. All three lanes consume the
same bounded observer-derived revision context. Only the public start
checkpoint and replay slice differ.

| Lane | Post-event action |
| --- | --- |
| `card_only_forward` | Continue once from the terminal public card with the late chunk |
| `full_restart` | Regenerate all initial chunks plus the late chunk from no checkpoint |
| `selective_replay` | Preserve the selected public prefix and regenerate its suffix plus the late chunk |

`card_only_forward` is intentionally named narrowly. It is not a claim about
all normal chat-model inference, which may resend a much richer conversation
history.

The bundle reports shared initial work, observer work, branch work,
counterfactual lane totals, and the physical cost of executing all lanes. Every
counterfactual total charges both the shared initial trace and the observer;
there is no selective-only observer surcharge. Logical cards, API calls,
provider input/output/reasoning tokens, cached tokens, and client-observed
latency remain separate. No price table is embedded.

## Independent machine grading

Input fixtures and gold are separate files. Live providers receive bounded,
gold-free public payloads only; in particular, the observer does not receive raw
initial-evidence text. Gold is loaded after execution and requires:

1. exact answer ID;
2. exact fixed slot/value facts;
3. exact stable facts;
4. minimal sufficient evidence IDs;
5. no retracted evidence in active support;
6. expected invalidated evidence marked separately.

Free-form prose and private reasoning are not graded. The local scripted
provider is explicitly gold-backed and exists only to test plumbing,
accounting, failure sentinels, and artifact determinism. Machine success grades
the final card; intermediate cards are schema/citation validated but are not
independently certified as semantically sufficient.

## DEV protocol revisions

Three earlier live diagnostics informed the final DEV contract and are
therefore contaminated development runs, not canonical evidence:

1. free-form decision facts made semantically equivalent cards fail string
   equality;
2. fixed slots worked, but the first gold revision required redundant procedure
   restatements in addition to a minimal sufficient evidence set;
3. a later diagnostic exposed three comparison leaks: the observer received raw
   initial evidence and could return an answer-bearing summary to every lane,
   old prefix IDs remained citable after their content disappeared from the
   public card, and observer cost was charged asymmetrically.

The reported canary was rerun only after closing those paths, adding direct
aperture regressions, symmetric accounting, strict per-receipt parity checks,
bootstrap/end source-hash checks, and incomplete failure bundles. This history
is why v0.4 cannot be treated as a holdout or promotion experiment even though
the boundary-fixed artifact is complete.

## Final two-case live canary

The boundary-fixed smoke used one answer-flip case and one
irrelevant-late-evidence control, one trial each. All 31 attempted API calls in
the physical experiment completed with requested and returned model
`gpt-5.6-sol`, service tier `default`, strict schemas, no SDK retry, and exact
provider usage. The successful bundle's source hashes match the source snapshot
taken before local bridge imports and rechecked before publication.

The GPT observer matched the DEV event/floor annotation on both cases.

| Lane | Machine success | Answer exact | Cards regenerated | Branch API calls | Input tokens | Output tokens | Reasoning tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Card-only forward | 1/2 | 1/2 | 2 | 2 | 1,580 | 431 | 136 |
| Full restart | 2/2 | 2/2 | 12 | 12 | 9,257 | 1,924 | 347 |
| Selective replay | 1/2 | 1/2 | 5 | 5 | 4,106 | 1,204 | 412 |

Selective replay regenerated 7 fewer cards than full restart. On branch-only
usage it consumed 5,151 fewer input tokens and 720 fewer output tokens, but 65
**more** reasoning tokens. These are exact measurements of this two-case run,
not a monotonic-compute, general cost, or speed claim.

Charging the common initial trace and observer to every lane yields the honest
counterfactual totals below. The selective/full token differences are unchanged
because the common work cancels; total calls do not.

| Lane | Counterfactual API calls | Input tokens | Output tokens | Reasoning tokens |
| --- | ---: | ---: | ---: | ---: |
| Card-only forward | 14 | 9,616 | 2,645 | 837 |
| Full restart | 24 | 17,293 | 4,138 | 1,048 |
| Selective replay | 17 | 12,142 | 3,418 | 1,113 |

The physical experiment—common work once plus all three branches—used 31 calls,
22,979 input tokens, 5,773 output tokens, and 1,596 reasoning-token detail.
Counterfactual lane totals must not be summed because doing so would triple-count
the shared initial trace and observer.

The quality guardrail did **not** pass: selective replay reproduced full
machine success on only 1/2 full-success cases.

### Case-level result

`unrelated_noop` behaved as intended. The observer classified the late color
correction as irrelevant, selective replay performed no backward replay, and
all three lanes passed. Selective used one post-event card versus six for full
restart.

`route_code_supersession` exposed the central v0.4 interaction. The observer
correctly selected the card immediately before invalidated evidence `R3`.
Full restart reread raw route table `R2`, combined it with correction `R6`, and
passed with answer `BLUE`. The selected checkpoint retained only a bare `R2`
citation and `bay=UNKNOWN`, not the public fact `B2 -> BLUE`. Selective replay
therefore knew `current_code=B2` but kept `bay=UNKNOWN`, later dropped `R2`, and
ended at the stale answer `AMBER`; card-only continuation did the same. Both
retained the independent `cargo_seal=SEALED` fact and correctly kept invalidated
`R3` out of active support.

The observer route itself matched the annotation, but the invalidated-anchor
floor interacted with a public checkpoint that was not dependency-complete for
the corrected lookup.

## Algorithm finding

The boundary-fixed canary isolates a concrete hypothesis:
**invalidated-anchor routing is not sufficient without public-state
sufficiency**.

A compact card can preserve an answer or citation while discarding the actual
lookup edge, rule, fallback, or stable fact needed only after a future
correction. Within v0.4's bounded public aperture, replay cannot reconstruct raw
content that the checkpoint omitted. This is an algorithmic failure mode
revealed after closing the reporting and comparison leaks; two cases do not
establish that it is the only bottleneck.

At the time of this two-case canary, the v0.4.1 candidate was to remain
pre-outcome and test two controls:

1. a dependency-complete public state or evidence ledger that preserves
   machine-checkable edges such as `current_code -> route_table -> bay`, plus a
   pre-outcome sufficiency certificate over required public decision slots;
2. a fail-closed floor expansion rule that moves replay earlier until the
   public dependency set can be reconstructed from retained state and the raw
   replay slice.

The adaptive trajectory-horizon selector remained shadow-only pending
checkpoint sufficiency. At that time, the planned next experiment was the full
10-case DEV suite with repeated, rotated lane order after a repaired route-code
canary. Any later promotion suite still must use entirely fresh names, texts,
values, families, and gold.

That repeated 10-case experiment has since completed. Fixed-envelope Direct
passed 30/30 while staged Full passed 4/30, so replay-floor expansion is now
paused behind a no-revision-envelope one-shot control and a cumulative-raw
staging ablation. The current decision and evidence are in
[`RND_DIRECT_FULL_CALIBRATION_V0_4.md`](RND_DIRECT_FULL_CALIBRATION_V0_4.md).

## Claim ledger

Supported now:

- GPT-5.6 executed the public observer and card generator through the Responses
  API in a complete two-case DEV canary;
- the same pre-outcome plan was used by all three lanes;
- exact calls and provider token usage are recorded without serializing private
  reasoning items;
- selective replay processed seven fewer public cards and fewer input/output
  tokens than full restart in this canary, while using 65 more reasoning tokens;
- the irrelevant no-op passed in all lanes;
- the tested invalidated-anchor route exposed a concrete public-state
  sufficiency failure on the route-code case.

Not supported:

- selective replay is quality-equivalent or superior to full restart;
- EBRT improves general LLM reasoning accuracy;
- the GPT observer or checkpoint selector generalizes beyond two DEV cases;
- token savings generalize to other prompts, models, or workloads;
- fewer replay cards imply fewer reasoning tokens;
- a price, latency, or production reliability advantage;
- hidden-state editing, private chain-of-thought replay, or Transformer-internal
  intervention.

## Reproduce

Offline core and scripted plumbing:

```bash
python3 language_replay_bridge_v0_4.py
python3 openai_reasoning_provider_v0_4.py
python3 benchmark_language_replay_v0_4.py self-test
python3 benchmark_language_replay_v0_4.py fake-dev \
  --output benchmark_results/v0_4_fake_dev
```

Live smoke requires the separately declared live dependencies and an
`OPENAI_API_KEY` in the process environment:

```bash
python3 -m pip install -r requirements-live.txt
python3 benchmark_language_replay_v0_4.py live-smoke \
  --output benchmark_results/v0_4_live_smoke
```

Every output remains `DEV_DRAFT` and non-promotional.
