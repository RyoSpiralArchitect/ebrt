# EBRT v0.4.1 Aperture Controls

## Status

This note records a non-promotional, contaminated-DEV causal calibration. It
does not report a fresh holdout, general reasoning improvement, hidden-state
editing, or an unassisted plain-API baseline.

The experiment follows the v0.4 Direct-vs-Full result without modifying its
runner, lock, or committed artifact. Its narrow questions are:

1. Does the fixed revision envelope change one-shot output when raw evidence,
   prompt, schema, model, and nominal output ceiling are held fixed?
2. Does retaining the cumulative raw prefix change or recover staged output
   quality when the prompt, call geometry, public card, fixed envelope, and
   nominal output ceiling are held fixed?

## Locked four-arm block

| Arm | Calls per case | Raw aperture | Revision envelope |
| --- | ---: | --- | --- |
| `direct_raw_no_revision` | 1 | all ordered raw evidence | null |
| `direct_raw_fixed_revision_rerun` | 1 | all ordered raw evidence | fixed minimal envelope |
| `staged_card_only_rerun` | 6 | current raw chunk plus prior public card | fixed minimal envelope |
| `staged_cumulative_raw` | 6 | all raw chunks seen so far plus prior public card | fixed minimal envelope |

Each of the ten existing DEV cases has six evidence chunks and runs for three
trials. A four-by-four Williams schedule balances arm position and adjacency;
case order rotates by trial. The complete block therefore contains 30
case-trials and 420 API calls.

All arms use `gpt-5.6-sol`, low reasoning effort, strict structured output, no
SDK retry, no persisted response state, and a nominal 4,608-token output
ceiling per arm and case. That ceiling does **not** match input tokens, realized
output or reasoning tokens, calls, latency, price, or server compute.
Cumulative raw intentionally repeats prior input and should consume more input
tokens.

## Public-state and temporal boundary

The public card is a bounded semantic-state channel, not zero information.
`claim` is limited to 256 characters, `topic` to 64, and the two fields may
contain at most one full seen raw chunk. This audits gross raw copying but does
not eliminate a short quotation or semantic paraphrase.

The fixed envelope contains only the late evidence identifier, relevance flag,
revision cue, and invalidated evidence identifiers. It is a fixture annotation
used for post-event reconstruction. In the three envelope arms it is
deliberately available from the first rebuilt step; this experiment does not
measure online event discovery. The no-envelope arm never receives the fixture
annotation and uses it only after generation for no-retry local validation.

## Endpoint and decision rule

The primary unit is a case-level stable pass: at least two strict successes in
three trials. Strict success requires the exact answer and decision facts,
stable facts, required evidence, absence of forbidden active support, and the
expected invalidation marks.

The raw-aperture conclusion is decided from the staged pair only:

- **rescue candidate:** cumulative raw reaches all ten stable passes, improves
  on card-only, and has no card-only-only stable case;
- **partial rescue:** cumulative raw improves stable-pass count without full
  rescue;
- **mixed:** each staged arm has at least one exclusive stable case;
- **not sufficient:** cumulative raw does not improve the stable-pass count.

The revision-envelope conclusion is likewise based only on the one-shot pair.
No cause conclusion becomes decision-ready until exact 10-case × 3-trial
coverage, every arm output completes, and all stored live receipts validate.

## Locked result

The runner attempted all 30 scheduled case-trials. Twenty-eight four-arm runs
completed. Two `staged_card_only_rerun` arms stopped after their third provider
receipt with `local_contract_error`, so the bundle contains 414 of the nominal
420 calls and its manifest is `INCOMPLETE`. Every stored receipt validated, but
the predeclared cause decision is **not ready**.

| Metric | No-envelope Direct | Fixed-envelope Direct | Card-only staged | Cumulative-raw staged |
| --- | ---: | ---: | ---: | ---: |
| Completed outputs | 30/30 | 30/30 | 28/30 | 30/30 |
| Strict machine success | 29/30 | 30/30 | 2/28 completed | 30/30 |
| Answer exact | 30/30 | 30/30 | 11/28 completed | 30/30 |
| Descriptive stable-pass cases | 10/10 | 10/10 | 1/10 | 10/10 |
| API calls with validated receipts | 30 | 30 | 174 | 180 |
| Input tokens | 22,041 | 22,911 | 131,308 | 148,222 |
| Output tokens | 4,523 | 4,563 | 41,299 | 35,046 |
| Reasoning-token detail | 87 | 0 | 17,861 | 9,232 |

Among completed staged trial pairs there were 26 cumulative-only strict
successes and two both-pass successes, with no card-only-only success. The two
remaining staged pairs were incomplete. Cumulative raw also matched the fixed
Direct arm at 30/30 strict outputs and 10/10 descriptive stable-pass cases.

The one-shot pair completed every output. Fixed-envelope Direct had one
additional strict success, while both one-shot arms remained stable on all ten
cases. This saturated DEV suite does not establish a useful envelope effect.

### Incomplete-run atlas

Both incomplete outputs occurred only in `staged_card_only_rerun`:

| Case | Trial | Validated cards before stop | Provider receipts | Stored category |
| --- | ---: | ---: | ---: | --- |
| `unit_reinterpretation` | 0 | 2 | 3 | `local_contract_error` |
| `invalidated_sensor_fallback` | 1 | 2 | 3 | `local_contract_error` |

In each run the third Responses call itself completed and has exact sanitized
usage, but the returned card failed a local contract check before it could be
committed as a public call record. The remaining three staged calls were not
made. The allowlisted failure representation intentionally omits exception
messages and raw responses, so this artifact does **not** identify which local
sub-rule failed. A future runner should retain a stable, non-sensitive
validator reason code; this is now an instrumentation bottleneck rather than a
license to infer the rejected card.

### Post-run direction-rule audit

An independent post-run review found an unexercised branch defect in the
executed runner's revision-envelope direction helper. If no-envelope Direct
were stable on all ten cases while fixed-envelope Direct regressed on one or
more cases, the current ordering could label the envelope "not needed" before
reporting that no-envelope outperformed it. This attempt never reaches that
branch because its global decision gate is closed, and the observed stable
case result is 10/10 for both one-shot arms, so the stored outcome is not
changed.

The executed runner and lock remain byte-identical to the manifest. They must
not be reused for a decision-ready rerun. A successor version must require
one-shot parity at the ceiling for "not needed," emit a harmful/mixed direction
when appropriate, and add a self-test for the `no_revision=10, fixed<10` cell.

## Adjudication

The predeclared locked conclusion remains:

```text
decision_ready: false
revision_envelope: not_assessed_incomplete_or_subset_run
raw_aperture: not_assessed_incomplete_or_subset_run
selective_replay: paused_no_same_block_rank
```

The validated descriptive trend nevertheless nominates raw aperture very
strongly: cumulative raw preserved strict success in all 30 outputs, whereas
card-only staging passed 2 of 28 completed outputs and failed locally twice.
This is suitable for choosing the next control, not for claiming a completed
causal estimate.

## Interpretation boundary

The observed cumulative-raw recovery nominates raw aperture as a causal
bottleneck candidate under this exact staged protocol. It does not establish
general LLM reasoning improvement, nor show that a compact replacement memory
design is already sufficient. Because the locked block is incomplete, the
formal cause gate remains closed. Input volume, repeated-call prompt dynamics,
and per-call token allocation also remain part of the tested intervention.

Selective replay is not executed in this block and receives no same-block
rank. A fresh, harder suite is required before choosing or promoting a quality
scaffold.
