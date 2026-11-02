# Getting started

The commands and details below are relocated from the former root README. See [the project overview](../../README.md) for the mechanism and claim boundary.

## Start here

### 1. Network-zero mechanism check

Requires Python 3.11+ and PyTorch.
The standard single-lane entry point is `ebrt_engine.RevisionEngine`; the
demo and hosted commands below select its coverage-first actuator by default.
`ebrt_core.py` retains the historical optimizer, reference engines, and CLI
for conformance and replay.

```bash
python3 -m pip install -r requirements-core.txt
python3 ebrt_core.py self-test
python3 ebrt_core.py capabilities
```

`self-test` performs no network call. It checks the single-trajectory and joint
contracts, real reverse-mode autodiff, finite differences, control budgets,
zero-control identity, deterministic merge, lane-order invariance, task-owned
trajectory binding, admitted-core receipt replay, nonzero model-visible credit,
immutable actuator inputs, exact post-run contract receipts, and both
state-adapter and model-adapter stop-gradient boundaries. It also checks that
the optional public oscilloscope runs strictly after optimization, leaves the
trajectory, actuator, and model output unchanged, and labels its reversed sham
geometry exactly.

#### One-command comparison demo

With the same core dependencies installed, run from the repository root:

```bash
python3 ebrt_demo.py
python3 ebrt_demo.py --json > /tmp/ebrt-demo.json
```

No API key or model download is needed. The demo shows the original `POLISH`
decision, the late `R6` correction, a real backward pass, per-evidence credit,
bounded controls, zero-control versus revised public trajectories, and the
compiled `REINSPECT / SUPPRESS / PRESERVE` program. The existing core and known
synthetic fixture are used unchanged. On the verified CPU run, the public
surrogate objective falls from `0.721232` to `0.080485`, within the `0.75` L2
control budget. Revised past steps are replays computed after the late event;
they do not overwrite the original history.

Both generation arms receive the complete evidence, including the correction.
The direct arm has no external revision program; the EBRT arm carries the
compiled program and credit-first ordering. **Both use the same fixed scripted
reply**, `ANSWER=PROVE` and `SUPPORT=R6,R4,R2`, independent of the prompt.
Output equality is expected: this is a wiring and mechanism demo, not evidence
of generator uptake, real-model quality improvement, or a gradient-specific
effect. The common output grade is separate from the core's post-run contract,
which also verifies compiled preservation requirements.

`--json` includes full prompts, trajectories, checks, and fingerprints, with
timings omitted for repeatable reports. Failures return a nonzero exit status.
Run the demo's regression tests with `python3 -m unittest -v test_ebrt_demo`.

### 2. Real local model

The reference adapter targets Apple silicon through MLX. Point
`EBRT_LOCAL_MODEL` at a complete local MLX snapshot:

```bash
python3 -m pip install -r requirements-local-mlx.txt
export EBRT_LOCAL_MODEL="$(hf download mlx-community/Mistral-7B-Instruct-v0.3-4bit)"

python3 ebrt_core.py local-e2e
python3 ebrt_core.py joint-local-e2e
```

If the Mistral snapshot is already in the standard Hugging Face cache, EBRT
discovers it automatically and the environment variable can be omitted.
Automatic discovery searches `HF_HUB_CACHE`, `HF_HOME`, `XDG_CACHE_HOME`, and
the default user cache in precedence order, then follows the repository's
`refs/main` revision. If that reference is absent while multiple complete
snapshots exist, EBRT rejects the ambiguous cache and requires
`EBRT_LOCAL_MODEL` or `--model` explicitly.
For an indexed snapshot, every shard named by every weight map must exist and
be non-empty before the snapshot is considered complete. Automatic discovery
also requires non-empty, parseable model/tokenizer configuration and a local
tokenizer asset before handing a snapshot to MLX.
Cache-derived model identities include the snapshot revision so different
weight snapshots cannot collapse into one receipt identity. An explicit
`--model-id` cannot relabel a cache-derived snapshot: when both are present,
they must match exactly.
Cache identity is derived only for an exact snapshot root beneath a configured
Hugging Face hub, with a 40-hex revision, complete loader material, and the
standard symlink-to-blob layout. Each linked blob is streamed and checked
recursively across nested repository directories against its SHA-256 or
Git-blob SHA-1 address before identity derivation. A directory that merely imitates
`models--.../snapshots/...` is treated as an ordinary local directory and must
supply `--model-id` explicitly.
The runtime exposes its bound model path as read-only and repeats cache identity
and blob verification immediately before lazy model loading, so construction
and generation cannot silently refer to different snapshots.
For a model stored outside that cache layout, pass a public receipt identity
explicitly with `--model-id provider/model@revision`. EBRT fails closed without
that revision-bearing identity rather than grouping replaceable weights by
their filesystem path. The MLX adapter also binds its seed, token ceiling,
sampler temperature, and chat-template mode into a separately fingerprinted
generation configuration in every model receipt.
Returned adapter descriptors are revalidated and compared to the pre-call
binding as canonical JSON bytes, so Python's `False == 0` or `True == 1`
coercions cannot preserve structural `PASS`.

The committed interface was verified locally with
`mlx-community/Mistral-7B-Instruct-v0.3-4bit`. The v0.7.1 integration fixture
produced:

```text
ANSWER=PROVE
SUPPORT=R6,R4,R2
```

with a strict post-run contract `PASS`. This is an end-to-end mechanism check
over a known synthetic fixture, not a claim of general reasoning improvement.
The committed sanitized receipt is
[`artifacts/model_interface_core_v0_7_1/local_mistral_e2e_r01.json`](../../artifacts/model_interface_core_v0_7_1/local_mistral_e2e_r01.json).

### 3. Selective State Oscilloscope

The oscilloscope is a development instrument, not a new reasoning claim. It
observes only selected windows and never feeds a measurement into the
controller:

```bash
python3 ebrt_core.py local-oscilloscope-e2e

# Optional selection for another compatible local architecture
python3 ebrt_core.py local-oscilloscope-e2e \
  --layers 0,15,31 \
  --event-window-radius 1 \
  --sampled-channels 16
```

One command performs the same deterministic local generation with the probe
OFF and ON. Acceptance requires exact equality of the raw natural-language
output, parsed answer, support IDs, request fingerprint, public trajectory,
and actuator. The observed run then retains only:

- the event-centered public trajectory window for neutral, exact, and an
  explicitly named L2/value-multiset-matched reversed temporal sham;
- scalar residual-stream summaries from the selected MLX layers at prefill,
  first decode, and last decode;
- evenly spaced channel samples and sampled-channel transition diagnostics.

Full native activations are not serialized or retained. The wrapper returns
the original layer output unchanged and restores the exact model-layer objects
after generation. The current reference check captures layers `0`, `15`, and
`31`; its probe-OFF and probe-ON outputs are both:

```text
ANSWER=PROVE
SUPPORT=R6,R4,R2
```

The command records the two serial wall times but marks instrumentation
overhead `NOT_ASSESSED_COLD_WARM_CONFOUNDED`: the first call includes cold model
loading and the second runs warm. A future overhead benchmark needs matched
warm-up and counterbalanced order.

Even sampled latent channels are derived model data. Native receipts are marked
`DERIVED_MODEL_DATA_REVIEW_BEFORE_EXPORT`; inspect them before publishing or
moving them outside the local development boundary.

This instrument exists to locate where an EBRT signal is lost or distorted
while improving the module. Its native-state measurements apply only to the
observed local run. They are not evidence about hosted-model internals,
cross-model regularities, semantic superiority, or general reasoning gains.

### 4. Local output-diff corpus

The auxiliary v0.8.2 runner stores the actual natural-language generations for
a matched direct full-context arm and an EBRT credit-first arm:

```bash
python3 local_output_diff_corpus_v0_8_2.py self-test

python3 local_output_diff_corpus_v0_8_2.py run \
  --model "$EBRT_LOCAL_MODEL" \
  --prompt-mode chat_template \
  --output /tmp/ebrt-local-output-run.json

python3 local_output_diff_corpus_v0_8_2.py verify \
  /tmp/ebrt-local-output-run.json

python3 local_output_diff_corpus_v0_8_2.py verify-aggregate \
  artifacts/local_output_diff_corpus_v0_8_2/r01/results.json
```

Verification reruns the deterministic public compilation from each fixed task,
rebuilds both model invocations, and requires their canonical fingerprints to
match the recorded request receipts. It then reparses raw output and recomputes
grades, diffs, categories, and aggregate summaries.

The committed corpus contains four cached model snapshots, four cases, and 32
terminal local calls. Raw output changed in all 16 paired cells, but only
Mistral satisfied the common output schema in both arms. Its final answer was
unchanged in all four cases while support lineage moved: one EBRT-only contract
pass, two direct-only passes, and one pass in both arms. The remaining 12 cells
are retained as adapter/capability failures rather than counted as EBRT quality
losses.

See the [R&D note](../../docs/RND_LOCAL_OUTPUT_DIFF_CORPUS_V0_8_2.md) and the
[generated report](../../artifacts/local_output_diff_corpus_v0_8_2/r01/report.md).
