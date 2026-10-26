# Hard repair with a matched 180-second timeout

Status: **PROTOCOL FROZEN BEFORE REQUESTS; RESULTS PENDING**

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
