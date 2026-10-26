# Hard repair with a matched 180-second timeout

Status: **COLLECTED; MINIMAL OUTPUTS 2/6 VS 1/6, NO FEEDBACK ADVANTAGE**

The [60-second hard-case replication](RND_HARD_REPAIR_REPLICATION.md)
produced minimal outputs in 1/6 full-repair and 2/6 gradient-feedback trials.
All nine missing outputs were provider timeouts; all completed outputs were
optimal. This separate follow-up increases the configured request timeout
equally to obtain more mathematical outcomes. The earlier run remains closed.

## Fixed protocol

`ebrt_hard_timeout.py` reuses the unchanged hard-case invocation compiler,
record derivation, independent exact oracles, and assessments. Its plan records
the baseline plan fingerprint, all earlier source hashes, and its own source
hash. The only generation setting changed is `timeout_seconds`: 60 to 180,
for both solver and judge requests in both arms. Judge timeouts also change
because the existing runner shares a generation configuration across stages.
The transport setting is not a strict global wall-clock deadline.

Everything else remains fixed: model gpt-5.6-sol, low reasoning effort,
4096 output tokens per solver/judge request, identical prompts and gradients,
three selected 24/36/48-vertex problems, and exact minimum edits 12/18/21.
No witnesses or optima enter prompts. Judges assess feasibility in fresh
contexts without arm/trial/prior/gradient/oracle information; they use the
same backend, not an independent model. Exact minimality comes from the oracle.

Both arms run each problem twice. Trial 1 uses cases 24,36,48 and full repair
first; trial 2 reverses cases and arm order. Each pair's judges follow its two
solvers. This is six planned trials on three distinct problems per arm, not
six independent problems. Every planned trial stays in its denominator.

The block has at most 24 attempts (12 solver + 12 judge), with a total requested
output ceiling of 98304 tokens, not a consumption estimate. No retries, added
samples, case changes, prompt changes, or adaptive budget changes occur within
this block. A solver provider failure skips only its judge; completed malformed
or infeasible answers are still judged. Judge failures and disagreements are
retained. Model drift or pre-dispatch errors stop collection.

Primary endpoints remain completed, feasible, and exactly minimal outputs out
of six planned trials per arm. Report every case/trial pair, including failures,
and excess edits among feasible answers. Usage and latency are secondary;
unknown usage remains unknown. No superiority threshold or significance claim
is introduced after observing outcomes. Feedback supplies conflict localization
as well as public-state gradients, so differences cannot isolate a gradient
mechanism or establish model-native backpropagation.

Compare arms within this block. The earlier 60-second run provides context,
not a contemporaneous randomized timeout control: provider conditions and
sampling can change across blocks. Do not pool them as interchangeable trials
or attribute a cross-block change solely to timeout.

## Execution and verification

Private files outside the checkout refuse overwrite and use permissions 0600.
Freeze source and plan before any requests; do not rerun an existing plan after
interruptions without inspecting its saved report. Offline replay verifies raw
record consistency and exact grades, not provider authenticity.

```bash
python ebrt_hard_timeout.py plan --output /tmp/hard-timeout-plan.json
python ebrt_hard_timeout.py run --plan /tmp/hard-timeout-plan.json --output /tmp/hard-timeout-report.json
python ebrt_hard_timeout.py verify --plan /tmp/hard-timeout-plan.json --report /tmp/hard-timeout-report.json --output /tmp/hard-timeout-verification.json
```

Tests check byte-identical solver/judge invocations against the baseline,
actual SDK timeout and token limits for all 24 slots, preserved denominators,
no retries after timeouts, skipped judges, model drift, malformed outputs,
receipt/settings/grade tampering, truncated reports, and private output files.
All 234 network-zero tests passed before live collection, including six new
follow-up tests. The closed 60-second report replay also passed, and the new
plan's baseline fingerprint matches the original saved plan exactly.

## Executed results

Source `4517ee289c692c3198bfbed190cf96a7d1644c1b` and the plan were fixed
before requests. Collection and offline review completed on 2026-10-27
(Asia/Tokyo). All twelve solver requests were attempted once. Six returned
completed raw candidates and each received its planned judge. Six judges
were skipped for missing completed candidates: eighteen actual requests.

| Case | Trial | Full repair | Gradient feedback | Exact minimum |
| --- | ---: | --- | --- | ---: |
| 24 vertices | 1 | Feasible, minimal: 12 edits | Feasible, minimal: 12 edits | 12 |
| 24 vertices | 2 | Feasible, minimal: 12 edits | Incomplete at 4096 tokens | 12 |
| 36 vertices | 1 | Incomplete at 4096 tokens | Infeasible: edge N01–N09 violated | 18 |
| 36 vertices | 2 | Incomplete at 4096 tokens | Incomplete at 4096 tokens | 18 |
| 48 vertices | 1 | Feasible: 25 edits (+4) | Incomplete at 4096 tokens | 21 |
| 48 vertices | 2 | Incomplete at 4096 tokens | Feasible: 28 edits (+7) | 21 |

| Condition | Planned / attempted | Completed | Feasible | Exactly minimal |
| --- | ---: | ---: | ---: | ---: |
| Full repair | 6 / 6 | 3 / 6 | 3 / 6 | 2 / 6 |
| Gradient feedback | 6 / 6 | 3 / 6 | 2 / 6 | 1 / 6 |

All six completed candidates passed native JSON format checks. The 36-vertex
feedback answer changed 17 vertices, but N01 and N09 were both BLUE on a
required edge. It is infeasible, not a better-than-optimal repair; excess edits
are undefined for it. Its judge returned FAIL and identified exactly that edge.
The other five candidates were feasible, and their judges returned PASS. All
six judges agreed with every mechanical criterion, including the failure.
Independent checks of the raw colors confirmed node coverage, palette, fixed
A, all edges, changed-vertex sets, and edit counts. The 48-vertex feasible
answers were nonminimal in both arms, on different trials; they are not a
same-trial pair of completed answers. Minimality remains an oracle result,
not a judge claim.

There were zero `HOSTED_PROVIDER_TIMEOUT` errors. Every missing solver answer
had `HOSTED_RESPONSE_INCOMPLETE`, exactly 4096 output tokens and 4096 reasoning
tokens, and no completed raw candidate. Thus these six attempts reached the
fixed output ceiling; they are not additional timeout observations or
mathematically graded wrong answers. All solver latencies were 54.17–78.16
seconds, below the configured 180-second timeout.

Provider usage was available for all eighteen attempts, including incomplete
responses. It was not imputed from requested limits:

| Requests | Input tokens | Output tokens | Reasoning tokens (within output) | Total tokens |
| --- | ---: | ---: | ---: | ---: |
| Full-repair solvers (6) | 6732 | 22908 | 22362 | 29640 |
| Feedback solvers (6) | 12946 | 23211 | 22605 | 36157 |
| Full-repair judges (3) | 3943 | 2569 | 1018 | 6512 |
| Feedback judges (3) | 4407 | 3116 | 1333 | 7523 |

Total recorded usage was 79832 tokens. Feedback supplied larger prompts and
did not save output tokens in this block. Judge workloads differ by candidate
and are reported separately; no monetary cost or general efficiency result is
inferred from these token counts.

Completion was equal at 3/6, while feasibility and minimality favored full
repair descriptively by one answer each. This does not establish superiority
of either approach on three selected problems with two repeated requests.
It does show that the present single feedback injection has not produced a
stable advantage here: constraint violations, nonminimal repairs, and output
budget exhaustion all remain. The earlier 60-second block is preserved as a
separate observation; its timeouts cannot be retrospectively relabeled as
token exhaustion, and the blocks are not pooled into a causal timeout estimate.

Collection is COMPLETE, execution is FAIL due to six incomplete responses,
and offline integrity is PASS for all eighteen attempts and all skipped slots.
No replacements, retries, or further budget changes followed within this block.

```text
plan:   c77ef52d53bc948b16ecd9ee71a7e1f98cca2701cae85a4d67d5d626d2f827b8
report: 1b0c064e1dd786cffce8debbcd643f35d71027935239195238304068e940eeac
verify: 05d67459547df7fd04ef032c65b68b5b1b2471939cdae787aa2f916bc370a1e2
```

The plan, raw report, and verification receipt remain in private 0600 files
outside the checkout. No earlier experiment source or closed report was edited.
