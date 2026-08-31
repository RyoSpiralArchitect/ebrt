# EBRT

**Backward Credit Assignment for Test-Time Revision**

EBRT is a model-interface-agnostic reasoning core. It turns a forward-only
reasoning episode into an explicit trajectory that can receive a late event,
assign bounded credit backward, compile a revision operation, and run the
affected computation forward again.

```text
forward trajectory
  -> late event
  -> backward credit assignment
  -> bounded intervention
  -> replay or regeneration
```

The current release has ten executable stages:

- **v0.7.1:** one trajectory, one real local backward pass, one compiled
  actuator, and one real open-weight regeneration;
- **v0.8.0:** one joint backward block over multiple public trajectories,
  lane-specific actuators, real local generations, and deterministic merge;
- **v0.8.1:** an optional, non-invasive state oscilloscope for faster local
  algorithm iteration;
- **v0.8.2:** a four-model local output-diff development corpus that separates
  algorithm-diagnostic cells from adapter/capability failures;
- **v0.8.3:** a fresh role-stratified uptake canary that separates deterministic
  compiler coverage from the local generator's observed support retention;
- **v0.8.4:** a sealed two-model, 2x2 typed-interface canary plus a post-review
  receipt that separates one full-factorial algorithm-diagnostic surface from
  one partial adapter/interface diagnostic.
- **v0.8.5:** a single typed public-state adapter and task-shaped readiness gate
  that stops both exact local snapshots before contaminated regression cells,
  preserving algorithm quality as `NOT_ASSESSED`.
- **v0.8.5.1:** a bounded public-role transport repair that carries the
  caller-supplied `Evidence.role` across the local model-adapter boundary while
  keeping the typed output state and controller fixed;
- **v0.8.5.2:** an exact role-field isolation that restores the v0.8.5 adapter
  label and requires nine complete prompt projections to match byte for byte;
- **v0.8.5.3:** a two-model adapter-breadth gate that fails closed before
  algorithm cells when the locked prompt-rendering mode is unsupported.

The generator is an adapter, not the definition of EBRT. The bundled reference
backend is a local MLX model. Hosted APIs and other local runtimes can meet the
same interface without entering the autograd graph.

## Start here

### 1. Network-zero mechanism check

Requires Python 3.11+ and PyTorch.

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
[`artifacts/model_interface_core_v0_7_1/local_mistral_e2e_r01.json`](artifacts/model_interface_core_v0_7_1/local_mistral_e2e_r01.json).

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

See the [R&D note](docs/RND_LOCAL_OUTPUT_DIFF_CORPUS_V0_8_2.md) and the
[generated report](artifacts/local_output_diff_corpus_v0_8_2/r01/report.md).

### 5. Role-stratified provider-uptake canary

The v0.8.3 auxiliary runner compares direct full context, the existing scalar
top-k actuator, and a role-stratified candidate on three fresh locked cases:

```bash
python3 role_stratified_uptake_canary_v0_8_3.py self-test

python3 role_stratified_uptake_canary_v0_8_3.py verify \
  artifacts/role_stratified_uptake_v0_8_3/r01/results.json \
  --lock policy_lock_role_stratified_uptake_v0_8_3.json

python3 role_stratified_uptake_integrity_v0_8_3_1.py \
  --base-lock policy_lock_role_stratified_uptake_v0_8_3.json \
  verify artifacts/role_stratified_uptake_v0_8_3/r02_integrity/results.json \
  --lock policy_lock_role_stratified_uptake_v0_8_3_1_r02.json

python3 role_stratified_uptake_integrity_v0_8_3_2.py \
  --base-lock policy_lock_role_stratified_uptake_v0_8_3.json \
  --prior-lock policy_lock_role_stratified_uptake_v0_8_3_1_r02.json \
  verify artifacts/role_stratified_uptake_v0_8_3/r03_snapshot_bound/results.json \
  --lock policy_lock_role_stratified_uptake_v0_8_3_2_r03.json

python3 role_stratified_uptake_integrity_v0_8_3_3.py \
  --base-lock policy_lock_role_stratified_uptake_v0_8_3.json \
  --source-lock policy_lock_role_stratified_uptake_v0_8_3_1_r02.json \
  --snapshot-lock policy_lock_role_stratified_uptake_v0_8_3_2_r03.json \
  verify artifacts/role_stratified_uptake_v0_8_3/r04_loader_bound/results.json \
  --lock policy_lock_role_stratified_uptake_v0_8_3_3_r04.json

python3 role_stratified_uptake_integrity_v0_8_3_4.py \
  --base-lock policy_lock_role_stratified_uptake_v0_8_3.json \
  --source-lock policy_lock_role_stratified_uptake_v0_8_3_1_r02.json \
  --snapshot-lock policy_lock_role_stratified_uptake_v0_8_3_2_r03.json \
  --loader-lock policy_lock_role_stratified_uptake_v0_8_3_3_r04.json \
  verify artifacts/role_stratified_uptake_v0_8_3/r05_runtime_bound/results.json \
  --lock policy_lock_role_stratified_uptake_v0_8_3_4_r05.json

python3 role_stratified_uptake_integrity_v0_8_3_5.py \
  --base-lock policy_lock_role_stratified_uptake_v0_8_3.json \
  --source-lock policy_lock_role_stratified_uptake_v0_8_3_1_r02.json \
  --snapshot-lock policy_lock_role_stratified_uptake_v0_8_3_2_r03.json \
  --loader-lock policy_lock_role_stratified_uptake_v0_8_3_3_r04.json \
  --runtime-lock policy_lock_role_stratified_uptake_v0_8_3_4_r05.json \
  verify artifacts/role_stratified_uptake_v0_8_3/r06_immutable_runtime_code/results.json \
  --lock policy_lock_role_stratified_uptake_v0_8_3_5_r06.json

python3 role_stratified_uptake_integrity_v0_8_3_6.py \
  --base-lock policy_lock_role_stratified_uptake_v0_8_3.json \
  --source-lock policy_lock_role_stratified_uptake_v0_8_3_1_r02.json \
  --snapshot-lock policy_lock_role_stratified_uptake_v0_8_3_2_r03.json \
  --loader-lock policy_lock_role_stratified_uptake_v0_8_3_3_r04.json \
  --runtime-lock policy_lock_role_stratified_uptake_v0_8_3_4_r05.json \
  --immutable-lock policy_lock_role_stratified_uptake_v0_8_3_5_r06.json \
  verify artifacts/role_stratified_uptake_v0_8_3/r07_complete_integrity/results.json \
  --lock policy_lock_role_stratified_uptake_v0_8_3_6_r07.json

python3 role_stratified_uptake_integrity_v0_8_3_7.py \
  --base-lock policy_lock_role_stratified_uptake_v0_8_3.json \
  --source-lock policy_lock_role_stratified_uptake_v0_8_3_1_r02.json \
  --snapshot-lock policy_lock_role_stratified_uptake_v0_8_3_2_r03.json \
  --loader-lock policy_lock_role_stratified_uptake_v0_8_3_3_r04.json \
  --runtime-lock policy_lock_role_stratified_uptake_v0_8_3_4_r05.json \
  --immutable-lock policy_lock_role_stratified_uptake_v0_8_3_5_r06.json \
  --complete-lock policy_lock_role_stratified_uptake_v0_8_3_6_r07.json \
  verify artifacts/role_stratified_uptake_v0_8_3/r08_verified_source/results.json \
  --lock policy_lock_role_stratified_uptake_v0_8_3_7_r08.json

python3 -E -S role_stratified_uptake_integrity_v0_8_3_8.py \
  --base-lock policy_lock_role_stratified_uptake_v0_8_3.json \
  --source-lock policy_lock_role_stratified_uptake_v0_8_3_1_r02.json \
  --snapshot-lock policy_lock_role_stratified_uptake_v0_8_3_2_r03.json \
  --loader-lock policy_lock_role_stratified_uptake_v0_8_3_3_r04.json \
  --runtime-lock policy_lock_role_stratified_uptake_v0_8_3_4_r05.json \
  --immutable-lock policy_lock_role_stratified_uptake_v0_8_3_5_r06.json \
  --complete-lock policy_lock_role_stratified_uptake_v0_8_3_6_r07.json \
  --verified-source-lock policy_lock_role_stratified_uptake_v0_8_3_7_r08.json \
  verify artifacts/role_stratified_uptake_v0_8_3/r09_startup_isolated/results.json \
  --lock policy_lock_role_stratified_uptake_v0_8_3_8_r09.json

python3 -E -S role_stratified_uptake_integrity_v0_8_3_12.py \
  --base-lock policy_lock_role_stratified_uptake_v0_8_3.json \
  --source-lock policy_lock_role_stratified_uptake_v0_8_3_1_r02.json \
  --snapshot-lock policy_lock_role_stratified_uptake_v0_8_3_2_r03.json \
  --loader-lock policy_lock_role_stratified_uptake_v0_8_3_3_r04.json \
  --runtime-lock policy_lock_role_stratified_uptake_v0_8_3_4_r05.json \
  --immutable-lock policy_lock_role_stratified_uptake_v0_8_3_5_r06.json \
  --complete-lock policy_lock_role_stratified_uptake_v0_8_3_6_r07.json \
  --verified-source-lock policy_lock_role_stratified_uptake_v0_8_3_7_r08.json \
  --startup-lock policy_lock_role_stratified_uptake_v0_8_3_8_r09.json \
  --stdlib-lock policy_lock_role_stratified_uptake_v0_8_3_9_r10.json \
  --imported-lock policy_lock_role_stratified_uptake_v0_8_3_10_r11.json \
  --tree-lock policy_lock_role_stratified_uptake_v0_8_3_11_r12.json \
  verify artifacts/role_stratified_uptake_v0_8_3/r13_framework_bound/results.json \
  --lock policy_lock_role_stratified_uptake_v0_8_3_12_r13.json
```

The deterministic compiler coverage floor repaired both intentionally exposed
top-k omissions: top-k covered all public required roles in `1/3` cases and the
candidate in `3/3`. That repair did not close the provider boundary. Both
controlled arms retained their compiled obligations in `2/3` outputs and both
passed the strict semantic contract in `2/3` cases. In the numeric-schema case,
the candidate changed the generated answer from `60_UNITS` to the expected
`6_UNITS`, but omitted correction provenance `R6`, so its strict contract still
failed. This is a useful mixed development result, not a superiority claim.

See the [v0.8.3 R&D note](docs/RND_ROLE_STRATIFIED_UPTAKE_CANARY_V0_8_3.md) and
the [framework-bound r13 artifact](artifacts/role_stratified_uptake_v0_8_3/r13_framework_bound/results.json).
The original r01 artifact is retained because review found that its pre-call
lock did not bind imported implementation files or reject arbitrary explicit
model identities. A second review found that r02 still did not bind the exact
expected blob set at the named cache revision. The r03 integrity replication
locks every snapshot-relative file, byte size, and content-addressed blob hash
before calls and checks the same manifest afterward. A third review found a
remaining cache-symlink TOCTOU window during model loading. r04 gives MLX only
a private APFS copy-on-write tree of the exact locked regular files, with
source-distinct inodes and pre/post content verification. All nine public
outputs are byte-identical across r01/r02/r03/r04. A fourth review found that
the open-ended `mlx-lm` requirement did not bind generation-runtime semantics.
r05 locks the exact Python/platform envelope and local-model distribution
versions before calls and checks them again afterward. Outputs remain
byte-identical across r01/r02/r03/r04/r05. A fifth review found that owner-mode
bits remained reversible and version metadata did not bind imported code. r06
loads from an unlinked read-only disk image and binds aggregate installed-file
content plus actual imported-module origins and hashes. Outputs remain
byte-identical across r01/r02/r03/r04/r05/r06. A sixth review found that r06
still omitted distributions reached indirectly during execution and did not
compare its portable mount receipt to the exact lock-derived model
fingerprints. r07 binds every imported file-backed non-standard-library module
to full owning-distribution content or repository source and verifies both the
staged-manifest and clone fingerprints. Outputs remain byte-identical across
r01-r07. A seventh review found that timestamp-valid generated bytecode could
still diverge from the locked source. r08 re-executes before repository or
site-package imports under a fresh empty `pycache_prefix` with bytecode writes
disabled, forcing Python modules through verified source while preserving
native-extension content receipts. Outputs remain byte-identical across
r01-r08. An eighth review found that the outer interpreter could still process
environment paths, `.pth`, `sitecustomize`, or `usercustomize` before the r08
bootstrap ran. r09 requires both outer and child interpreters to start with
`-E -S`, manually admits only the two locked site-package roots after startup,
and retains the empty-cache source policy. Its portable verifier passes 12/12
checks, and all r01-r09 public outputs remain byte-identical (`9/9`). None of
the integrity successors is fresh evidence. A ninth review found that r09 did
not bind the CPython executable or standard-library code. r10 added those
receipts but failed before provider calls because it re-entered r09's exact
module-set gate; r11 called the sealed base runner directly, completed nine
calls, then failed its own post-call gate when five legitimate stdlib modules
were lazily imported. Both failures are retained. r12 instead locks the entire
1,839-file stdlib Python/native code tree and checks imported-module coverage
against that fixed universe before and after generation. The imported set grew
from 392 to 397 modules, all covered; its portable verifier passes 16/16
checks. All complete r01-r09/r12 public outputs remain byte-identical (`9/9`).
An additional review found that the 119KB launcher was not the 13.55MB macOS
Python framework implementation. r13 adds that framework binary to the
pre/post lock; its portable verifier also passes 16/16 checks. All complete
r01-r09/r12/r13 public outputs remain byte-identical (`9/9`). None of these
integrity successors is fresh evidence.

The final review boundary is intentionally host-trusting. The r13 framework
receipt binds the configured on-disk framework file; it does not prove which
image dyld mapped, reject loader overrides, or attest other shared libraries.
Likewise, the source receipts bind cache-bypassed on-disk source before and
after the run, not the in-memory code objects against a concurrent same-user
file-swap attack. Interpret `cpython_framework_library_exact` and
`nonstdlib_source_execution_exact` as receipt-level checks inside a quiescent,
trusted local host. Loaded-image identity, hostile same-user TOCTOU, and full
host attestation are `NOT_ASSESSED`.

### 6. Typed revision-channel canary

v0.8.4 keeps the role-stratified controller fixed and crosses chronological
versus controlled context with flat versus typed output-interface packages.
Post-review audit found that the typed package also included typed-only
support-selection guidance for a scored stable-evidence criterion. The result
therefore does **not** identify field factorization alone.

```bash
python3 typed_revision_channel_canary_v0_8_4.py self-test

python3 typed_revision_channel_canary_v0_8_4.py verify \
  artifacts/typed_revision_channel_v0_8_4/r01/results.json \
  --lock policy_lock_typed_revision_channel_v0_8_4.json

python3 interpret_typed_revision_channel_v0_8_4.py verify \
  --source artifacts/typed_revision_channel_v0_8_4/r01/results.json \
  --lock policy_lock_typed_revision_channel_v0_8_4.json \
  --receipt artifacts/typed_revision_channel_v0_8_4/r01/post_review_interpretation.json
```

The sealed block ran four fresh cases, two exact local instruction-model
snapshots, and 34 logical calls with no retry. Mistral produced one strict
flat-to-typed-package repair: the typed controlled arm restored required
decision evidence `R2` while moving correction provenance `R6` into its own
field. This is `1/4` within the sole full-factorial algorithm-diagnostic model.
The mechanically graded all-cell count is `1/8`, but that is not a cross-model
quality denominator.

The Qwen snapshot passed a literal readiness copy probe but produced no
parseable task-shaped typed output. It is therefore a partial adapter/interface
diagnostic and its typed failures are excluded from algorithm-quality counts.
Its flat outputs still showed a positive
answer flip in one case and a negative flip in another under the same control
bundle. The result therefore exposes two next bottlenecks: readiness must test
task-shaped channel composition, and a provider-visible actuator can be
non-neutral without controlling quality monotonically.

See the [v0.8.4 R&D note](docs/RND_TYPED_REVISION_CHANNEL_V0_8_4.md) and the
[sealed report](artifacts/typed_revision_channel_v0_8_4/r01/report.md). The
[post-review interpretation receipt](artifacts/typed_revision_channel_v0_8_4/r01/post_review_interpretation.json)
preserves the original result byte-for-byte while narrowing its denominators
and contrast claim.

### 7. Typed public-state adapter regression

v0.8.5 gives answer, decision support, revision provenance, and preserved
constraints distinct destinations in one strict `STATE_JSON` object. Before
any regression case, each model must pass both a literal format probe and a
held-out task-shaped channel-composition probe.

```bash
python3 typed_public_state_regression_v0_8_5.py self-test

python3 typed_public_state_regression_v0_8_5.py verify \
  artifacts/typed_public_state_v0_8_5/r01/results.json \
  --lock policy_lock_typed_public_state_v0_8_5.json
```

The v0.8.5 live namespace is frozen. Its lock retains the exact execution
runner hash; the current source adds a fail-closed portable-verifier check and
will not authorize another live run under that historical lock.

Both exact snapshots passed literal formatting and failed the task-shaped
gate. Mistral retained the retired answer despite correct decision evidence;
Qwen selected the corrected answer but omitted identity evidence from its
lineage. The fail-closed runner therefore made zero contaminated regression
calls. This is an adapter-readiness failure atlas and gate success, not a
direct/control or algorithm-quality result.

See the [v0.8.5 R&D note](docs/RND_TYPED_PUBLIC_STATE_V0_8_5.md) and the
[sealed report](artifacts/typed_public_state_v0_8_5/r01/report.md).

### 8. Public role transport repair

v0.8.5.1 changes one model-visible input field: every evidence record now
retains the caller-supplied public `Evidence.role` already present in
`RevisionTask`. Removing that field reconstructs the v0.8.5 text-only record
exactly. No expected answer or post-call semantic contract enters a prompt.

```bash
python3 public_role_transport_canary_v0_8_5_1.py self-test
python3 public_role_transport_canary_v0_8_5_1.py lock-spec
```

Mistral repaired the known readiness failure and passed `3/4` contaminated
cells in both arms. Qwen emitted the same incomplete support lineage and was
stopped before regression. Although raw strings changed in all four admitted
cells, normalized direct/control public states changed in none. A post-run
audit also found one adapter-label wording delta, so role-only effect is
`NOT_IDENTIFIED`; v0.8.5.1 is preserved as a bundled diagnostic.

See the [v0.8.5.1 R&D note](docs/RND_PUBLIC_ROLE_TRANSPORT_V0_8_5_1.md),
[sealed report](artifacts/public_role_transport_v0_8_5_1/r01/report.md), and
[post-run interpretation](artifacts/public_role_transport_v0_8_5_1/r01/post_run_interpretation.json).

### 9. Exact public-role isolation

v0.8.5.2 preserves v0.8.5.1 as a bundled diagnostic and restores the exact
v0.8.5 adapter-label line. Before locking, it removes only `role` from every
model-visible `EVIDENCE_JSON` record and requires the resulting complete prompt
to match v0.8.5 for readiness and both arms of all four cases: `9/9` exact.

```bash
python3 public_role_transport_isolation_v0_8_5_2.py self-test
python3 public_role_transport_isolation_v0_8_5_2.py verify \
  artifacts/public_role_transport_isolation_v0_8_5_2/r01/results.json \
  --lock policy_lock_public_role_transport_isolation_v0_8_5_2.json
```

Under the single pushed lock and one no-retry execution, Mistral again changed
from the known readiness `FAIL` to `PASS`; Qwen remained `FAIL` because `R2`
was absent. Mistral passed `3/4` contaminated cases in both arms. Three raw
direct/control differences reduced to list or JSON ordering: normalized public
state and answer differences were both `0/4`.

This isolates the exact model-visible field and records a one-model readiness
association, not causal attribution or a general quality result. The admitted
direct/control semantic effect remains `NULL_ON_ADMITTED_CELLS`.

See the [v0.8.5.2 R&D note](docs/RND_PUBLIC_ROLE_TRANSPORT_ISOLATION_V0_8_5_2.md),
[sealed report](artifacts/public_role_transport_isolation_v0_8_5_2/r01/report.md),
and [post-run interpretation](artifacts/public_role_transport_isolation_v0_8_5_2/r01/post_run_interpretation.json).

### 10. Public-role adapter breadth gate

v0.8.5.3 holds all nine v0.8.5.2 prompts byte-exact and substitutes two
previously exercised local snapshots: Llama 3.2 3B bf16 and Gemma 2 2B 4-bit.
Each model must pass literal and task-shaped readiness before any contaminated
regression call.

```bash
python3 public_role_adapter_breadth_v0_8_5_3.py self-test
python3 public_role_adapter_breadth_v0_8_5_3.py verify \
  artifacts/public_role_adapter_breadth_v0_8_5_3/r01/results.json \
  --lock policy_lock_public_role_adapter_breadth_v0_8_5_3.json
```

Both models returned `MLX_GENERATION_FAILED` at both probes, so the runner
stopped after four calls with zero algorithm cells. A no-call static diagnosis
then found that neither tokenizer configuration contains a chat template while
the lock requires chat-template rendering. This is an adapter mismatch and
failure-gate success—not evidence about model reasoning quality.

See the [v0.8.5.3 R&D note](docs/RND_PUBLIC_ROLE_ADAPTER_BREADTH_V0_8_5_3.md),
[sealed report](artifacts/public_role_adapter_breadth_v0_8_5_3/r01/report.md),
and [post-run interpretation](artifacts/public_role_adapter_breadth_v0_8_5_3/r01/post_run_interpretation.json).

## What the core owns

The central file is [`ebrt_core.py`](ebrt_core.py). It contains the complete
active prototype rather than scattering the reasoning mechanism across a
framework.

```text
RevisionTask
  -> StateAdapter
       explicit differentiable trajectory
  -> EBRT Core
       objective + backward credit + bounded control + replay
  -> ActuatorAdapter
       public REINSPECT / SUPPRESS / PRESERVE program
       STOP GRADIENT
  -> ModelAdapter
       local open-weight model or hosted API
  -> Observer
       structural receipt + optional post-run contract
```

In compact notation, for generator interface `m`:

\[
\tau_m = S_m(x,e), \qquad
c_m = \operatorname{EBRT}(\tau_m,\mathcal L,B),
\]

\[
a_m = A_m(c_m), \qquad
y'_m = M_m(x,a_m).
\]

EBRT differentiates through a detached, core-owned copy of \(\tau_m\), not
through the state adapter that produced it or through \(M_m\). The current
public protocol validates the adapter output as CPU `torch.float64`, binds the
task-owned target, event index, decay, learning rate, and control budget, then
records the exact typed state-adapter scales in the core receipt and severs any
incoming autograd history before optimization. A future admitted latent
trajectory needs an explicit protocol version rather than silently crossing
this boundary.
All public numeric task and receipt fields are actual JSON numbers; strings and
booleans are rejected rather than coerced.

The engine attributes `real_backward_executed_once` only to the exact bundled
core implementation and its module-load original method, checked before and
after execution. The original callable is captured in the engine method closure
rather than retained in a writable module symbol. Its immutable code object is
captured separately and executed through a private function copy. The engine
rejects class replacement, instance-level method shadowing, function-code
mutation, and simultaneous rebinding of lookalike module symbols. An injected
core receipt is still structurally validated, but cannot promote a replay into
a claim about the current run. Independently, every engine call attaches a
run-local, forward-value-neutral autograd probe to the public target. Its
expected gradient is computed from the declared EBRT objective, and the actual
backward must fire it exactly once with that value. An unrelated traversal such
as `target.sum().backward()` therefore cannot validate a replayed receipt.
These are executable conformance checks, not a Python process sandbox; code
with arbitrary interpreter-memory mutation is outside the runtime trust model.

## v0.7.1 — single-trajectory revision

The bundled public trajectory has three explicit axes:

- `revision`: movement toward the event-consistent terminal state;
- `invalidation`: propagation of a typed correction;
- `stability`: information that must remain unchanged.

For bounded controls \(u_t\), the forward recurrence is intentionally small:

\[
h_t = \rho h_{t-1} + e_t + \tanh(u_t)b_t.
\]

Therefore \(u=0\) is a literal no-op over the declared forward trajectory. A
trajectory loss supplies terminal, path, smoothness, and control terms. EBRT
executes one `torch.float64` backward pass, verifies selected gradients against
central finite differences, projects the proposed control into an L2 budget,
and replays the trajectory.

The compiled actuator does not pretend that a gradient contains natural
language semantics. Responsibilities remain separate:

| Layer | Responsibility |
| --- | --- |
| Backward pass | assign where and how much to reinspect |
| Typed event compiler | provide allowlisted `SUPPRESS` and `PRESERVE` semantics |
| Model adapter | regenerate from complete public context and the full quantitative actuator |
| Observer | check public structure and, when supplied, a post-run contract |

Only non-correction rows with positive realized control can enter the
credit-first reinspection list. The typed correction remains mandatory; a
zero-credit padding row cannot change provider-visible evidence order.

The post-run contract never enters the model request. It is computed only after
generation, then its exact validated fields and fingerprint are sealed beside
the resulting grade so an archived semantic `PASS` remains independently
auditable.

## v0.8.0 — joint trajectories

v0.8 lifts the same mechanism into a block of namespaced lanes:

\[
\mathcal L_{joint}
= \sum_k w_k\mathcal L_k
+ \gamma\sum_{i<j}\|P h_i-P h_j\|^2.
\]

The implementation:

1. sorts and namespaces the lanes;
2. concatenates their admitted controls;
3. executes **one** backward pass over the joint block;
4. enforces per-lane and global control budgets;
5. compiles one actuator per lane;
6. invokes each declared model adapter; and
7. merges public answers deterministically.

The real local v0.8 check currently runs two different trajectory adapters and
prompt policies through one shared Mistral runtime. That establishes joint
multi-lane execution, not heterogeneous multi-model performance. Distinct
provider/model effects remain `NOT_ASSESSED` until two real model IDs run under
a locked comparison.

## Adapter contract

| Interface | Required edge | Current implementation |
| --- | --- | --- |
| `StateAdapter` | `build(task, lane_id) -> TrajectoryEnvelope` | `TypedPublicStateAdapter` |
| `ActuatorAdapter` | `compile(task, credit, lane_id) -> ActuatorProgram` | `PublicRevisionActuator` |
| `ModelAdapter` | `generate(task, program, prompt_policy) -> ModelResult` | `MLXLocalAdapter`, `CallableModelAdapter` |
| Observer | sealed mechanism, structural, and semantic receipts | `RevisionEngine`, `JointRevisionEngine` |

`CallableModelAdapter` is the provider-neutral binding edge for an SDK or
another local runtime. Its hosted shape is covered by network-zero conformance;
no hosted-provider E2E is claimed in v0.7.1/v0.8.0 because no credential was
present for this development gate.

Run `python3 ebrt_core.py capabilities` for the machine-readable boundary.

## Claim boundary

Implemented and verified:

- an explicit differentiable public trajectory;
- real local backward credit assignment and bounded control;
- a literal zero-control identity;
- deterministic compilation into a public revision actuator;
- one real local open-weight regeneration;
- one joint backward over multiple lanes and two real local generations;
- independent structural and post-run verification receipts.

Not established:

- access to, reconstruction of, or editing of private chain-of-thought;
- gradients through a language model, hosted API, JSON, or sampled text;
- equivalence between the public trajectory and model-native hidden states;
- causal superiority of EBRT over an uncontrolled or textual revision;
- general reasoning-quality improvement;
- heterogeneous multi-model benefit.

Surrogate descent, actuator uptake, generated-output quality, and causal effect
are separate measurements. A `PASS` in one category does not silently imply a
`PASS` in another.

## Repository map

### Active path

| Path | Role |
| --- | --- |
| [`ebrt_core.py`](ebrt_core.py) | v0.7.1/v0.8 monolith and CLI |
| [`local_output_diff_corpus_v0_8_2.py`](local_output_diff_corpus_v0_8_2.py) | matched local-model output corpus runner |
| [`role_stratified_uptake_canary_v0_8_3.py`](role_stratified_uptake_canary_v0_8_3.py) | fresh three-arm compiler-coverage/provider-uptake canary |
| [`policy_lock_role_stratified_uptake_v0_8_3.json`](policy_lock_role_stratified_uptake_v0_8_3.json) | pre-call v0.8.3 case, schedule, model, and source lock |
| [`typed_revision_channel_canary_v0_8_4.py`](typed_revision_channel_canary_v0_8_4.py) | sealed two-model, four-arm typed revision-channel canary |
| [`policy_lock_typed_revision_channel_v0_8_4.json`](policy_lock_typed_revision_channel_v0_8_4.json) | pre-call v0.8.4 cases, models, schedule, source, and invocation lock |
| [`interpret_typed_revision_channel_v0_8_4.py`](interpret_typed_revision_channel_v0_8_4.py) | deterministic post-review contrast and denominator interpreter |
| [`typed_public_state_regression_v0_8_5.py`](typed_public_state_regression_v0_8_5.py) | frozen typed-state runner and fail-closed portable verifier for the two-stage readiness artifact |
| [`policy_lock_typed_public_state_v0_8_5.json`](policy_lock_typed_public_state_v0_8_5.json) | pre-call v0.8.5 sources, exact models, readiness, cases, and invocation lock |
| [`public_role_transport_canary_v0_8_5_1.py`](public_role_transport_canary_v0_8_5_1.py) | caller-supplied public-role transport repair over the v0.8.5 task-shaped gate |
| [`policy_lock_public_role_transport_v0_8_5_1.json`](policy_lock_public_role_transport_v0_8_5_1.json) | pre-call v0.8.5.1 runner, role-record schema, exact models, readiness, cases, and invocations |
| [`interpret_public_role_transport_v0_8_5_1.py`](interpret_public_role_transport_v0_8_5_1.py) | deterministic prompt-delta and normalized public-state interpreter for sealed v0.8.5.1 |
| [`public_role_transport_isolation_v0_8_5_2.py`](public_role_transport_isolation_v0_8_5_2.py) | exact role-only prompt isolation and two-stage local adapter canary |
| [`policy_lock_public_role_transport_isolation_v0_8_5_2.json`](policy_lock_public_role_transport_isolation_v0_8_5_2.json) | pre-call runner, dependencies, nine prompt projections, exact models, schedule, and invocation lock |
| [`interpret_public_role_transport_isolation_v0_8_5_2.py`](interpret_public_role_transport_isolation_v0_8_5_2.py) | deterministic v0.8.5-to-v0.8.5.2 readiness, prompt, and normalized output interpreter |
| [`public_role_adapter_breadth_v0_8_5_3.py`](public_role_adapter_breadth_v0_8_5_3.py) | readiness-first Llama/Gemma adapter-breadth canary on the byte-exact v0.8.5.2 surface |
| [`policy_lock_public_role_adapter_breadth_v0_8_5_3.json`](policy_lock_public_role_adapter_breadth_v0_8_5_3.json) | pre-call source, prompt-surface, exact model, schedule, and no-retry lock |
| [`interpret_public_role_adapter_breadth_v0_8_5_3.py`](interpret_public_role_adapter_breadth_v0_8_5_3.py) | no-call static rendering-capability and sealed readiness interpreter |
| [`role_stratified_uptake_integrity_v0_8_3_1.py`](role_stratified_uptake_integrity_v0_8_3_1.py) | source- and model-bound integrity replication wrapper |
| [`policy_lock_role_stratified_uptake_v0_8_3_1_r02.json`](policy_lock_role_stratified_uptake_v0_8_3_1_r02.json) | pre-call hashes for the wrapper and every imported local execution file |
| [`role_stratified_uptake_integrity_v0_8_3_2.py`](role_stratified_uptake_integrity_v0_8_3_2.py) | exact expected model-snapshot manifest wrapper |
| [`policy_lock_role_stratified_uptake_v0_8_3_2_r03.json`](policy_lock_role_stratified_uptake_v0_8_3_2_r03.json) | pre-call relative path, byte-size, and blob-hash manifest |
| [`role_stratified_uptake_integrity_v0_8_3_3.py`](role_stratified_uptake_integrity_v0_8_3_3.py) | loader-bound private APFS staging wrapper |
| [`policy_lock_role_stratified_uptake_v0_8_3_3_r04.json`](policy_lock_role_stratified_uptake_v0_8_3_3_r04.json) | pre-call loader-path and staged-byte policy lock |
| [`role_stratified_uptake_integrity_v0_8_3_4.py`](role_stratified_uptake_integrity_v0_8_3_4.py) | exact Python/platform/distribution runtime wrapper |
| [`policy_lock_role_stratified_uptake_v0_8_3_4_r05.json`](policy_lock_role_stratified_uptake_v0_8_3_4_r05.json) | pre-call exact local runtime-version lock |
| [`role_stratified_uptake_integrity_v0_8_3_5.py`](role_stratified_uptake_integrity_v0_8_3_5.py) | unlinked read-only model image and imported-code wrapper |
| [`policy_lock_role_stratified_uptake_v0_8_3_5_r06.json`](policy_lock_role_stratified_uptake_v0_8_3_5_r06.json) | pre-call immutable-model/runtime-code lock |
| [`role_stratified_uptake_integrity_v0_8_3_6.py`](role_stratified_uptake_integrity_v0_8_3_6.py) | complete imported-dependency and exact locked-mount verifier |
| [`policy_lock_role_stratified_uptake_v0_8_3_6_r07.json`](policy_lock_role_stratified_uptake_v0_8_3_6_r07.json) | pre-call complete runtime-code and lock-derived mount receipt |
| [`role_stratified_uptake_integrity_v0_8_3_7.py`](role_stratified_uptake_integrity_v0_8_3_7.py) | verified-source child bootstrap and bytecode-cache divergence guard |
| [`policy_lock_role_stratified_uptake_v0_8_3_7_r08.json`](policy_lock_role_stratified_uptake_v0_8_3_7_r08.json) | pre-call source-execution policy and module receipt |
| [`requirements-core.txt`](requirements-core.txt) | network-zero core dependency |
| [`requirements-local-mlx.txt`](requirements-local-mlx.txt) | Apple-silicon local backend |
| [`docs/EBRT_CORE_THESIS.md`](docs/EBRT_CORE_THESIS.md) | mathematical and conceptual anchor |
| [`docs/MODEL_ADAPTER_PROTOCOL.md`](docs/MODEL_ADAPTER_PROTOCOL.md) | provider-neutral binding contract |
| [`docs/ROADMAP_MODEL_INTERFACE_CORE.md`](docs/ROADMAP_MODEL_INTERFACE_CORE.md) | evidence-labelled path beyond v0.8 |
| [`docs/RND_LOCAL_OUTPUT_DIFF_CORPUS_V0_8_2.md`](docs/RND_LOCAL_OUTPUT_DIFF_CORPUS_V0_8_2.md) | generated-output failure atlas and bounded next hypotheses |
| [`docs/RND_ROLE_STRATIFIED_UPTAKE_CANARY_V0_8_3.md`](docs/RND_ROLE_STRATIFIED_UPTAKE_CANARY_V0_8_3.md) | role-coverage repair result and remaining provider-uptake boundary |
| [`docs/RND_TYPED_REVISION_CHANNEL_V0_8_4.md`](docs/RND_TYPED_REVISION_CHANNEL_V0_8_4.md) | typed-channel result, readiness-gate defect, and next bounded adapter repair |
| [`artifacts/model_interface_core_v0_7_1/local_mistral_e2e_r01.json`](artifacts/model_interface_core_v0_7_1/local_mistral_e2e_r01.json) | sanitized real local E2E receipt |
| [`artifacts/local_output_diff_corpus_v0_8_2/r01/results.json`](artifacts/local_output_diff_corpus_v0_8_2/r01/results.json) | sealed four-model, 32-call development corpus |
| [`artifacts/role_stratified_uptake_v0_8_3/r01/results.json`](artifacts/role_stratified_uptake_v0_8_3/r01/results.json) | sealed one-model, nine-call uptake canary |
| [`artifacts/typed_revision_channel_v0_8_4/r01/results.json`](artifacts/typed_revision_channel_v0_8_4/r01/results.json) | sealed two-model, 34-call typed-channel canary |
| [`artifacts/role_stratified_uptake_v0_8_3/r02_integrity/results.json`](artifacts/role_stratified_uptake_v0_8_3/r02_integrity/results.json) | preserved source-bound repetition; not fresh evidence |
| [`artifacts/role_stratified_uptake_v0_8_3/r03_snapshot_bound/results.json`](artifacts/role_stratified_uptake_v0_8_3/r03_snapshot_bound/results.json) | preserved exact-snapshot-bound repetition; not fresh evidence |
| [`artifacts/role_stratified_uptake_v0_8_3/r04_loader_bound/results.json`](artifacts/role_stratified_uptake_v0_8_3/r04_loader_bound/results.json) | preserved loader-bound repetition; not fresh evidence |
| [`artifacts/role_stratified_uptake_v0_8_3/r05_runtime_bound/results.json`](artifacts/role_stratified_uptake_v0_8_3/r05_runtime_bound/results.json) | preserved runtime-version-bound repetition; not fresh evidence |
| [`artifacts/role_stratified_uptake_v0_8_3/r06_immutable_runtime_code/results.json`](artifacts/role_stratified_uptake_v0_8_3/r06_immutable_runtime_code/results.json) | preserved immutable-model/runtime-code repetition; not fresh evidence |
| [`artifacts/role_stratified_uptake_v0_8_3/r07_complete_integrity/results.json`](artifacts/role_stratified_uptake_v0_8_3/r07_complete_integrity/results.json) | preserved complete-integrity repetition; not fresh evidence |
| [`artifacts/role_stratified_uptake_v0_8_3/r08_verified_source/results.json`](artifacts/role_stratified_uptake_v0_8_3/r08_verified_source/results.json) | canonical verified-source repetition; not fresh evidence |

### Frozen research history

Root-level v0.1-v0.6.3.2 modules, `policy_lock_*.json`, reports, and artifacts
are retained as immutable research history. They include negative results that
shaped the current abstraction: a mathematically valid control surface can be
ignored by a generator, public lineage is not the same as control uptake, and
integrity closure is not method superiority.

The most useful historical entrypoints are:

- [`ebrt_monolith_v0_1.py`](ebrt_monolith_v0_1.py): original differentiable toy
  mechanism;
- [`ebrt.py`](ebrt.py): sealed Apply Revision acceptance engine;
- [`ebrt_live.py`](ebrt_live.py): frozen v0.6 live runtime;
- [`docs/ROADMAP_V0_6_PLUS.md`](docs/ROADMAP_V0_6_PLUS.md): pre-core roadmap and
  decision record;
- [`SUBMISSION.md`](SUBMISSION.md): historical Build Week presentation, no
  longer the project definition.

## Roadmap

The active roadmap is
[`docs/ROADMAP_MODEL_INTERFACE_CORE.md`](docs/ROADMAP_MODEL_INTERFACE_CORE.md).
The next scientific gates are:

1. two distinct real local model IDs behind the same protocol;
2. a hosted adapter E2E when credentials and policy are available;
3. external public control versus an admitted model-native latent actuator;
4. fresh matched evaluation of actuator uptake and output quality.

## Origin

EBRT began as a sketch in which a latent reasoning trajectory receives a
trajectory-level loss and backward revision before decoding. The Build Week
deadline compressed that sketch into a hosted-model runtime, an Inspector, and
strict public artifacts. Those components remain valuable, but the current
definition is broader: **the missing primitive is backward revision at
inference time**, independent of any particular provider.

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
