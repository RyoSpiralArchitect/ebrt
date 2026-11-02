# EBRT experiment atlas

These execution protocols and original findings are preserved from the former root README. Numbers are conditional on their recorded cases, models and budgets; a recorded structural PASS is not a model-quality claim. See the [project overview](../../README.md), [mechanism](../mechanism/README.md), and individual linked R&D notes.

The subsequent [v0.9.1 delayed-terminal-credit protocol](../RND_DELAYED_TERMINAL_CREDIT_V0_9_1.md)
has a [completed first hosted block](../RND_DELAYED_TERMINAL_CREDIT_V0_9_1_RUN.md):
all nine responses completed on `gpt-4.1-2025-04-14`, but direct, scrambled,
and adjoint each scored **0/3 exact answer, 1/3 exact support, and 0/3 strict**.
Offline verification and independent integer grading passed; no hosted
quality advantage was observed.

The maintainer then requested `gpt-5.6-sol`; its separately frozen
[r02 block](../RND_DELAYED_TERMINAL_CREDIT_V0_9_1_GPT56_RUN.md) completed nine calls
with **3/3 exact answer, support, and strict in every arm**, and byte-identical
outputs across arms within each case. This is an observed ceiling, again with
no placement advantage. R02 also changes the output ceiling from 384 to 4096;
the two blocks are preserved separately and do not isolate a model-only effect.

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

See the [v0.8.3 R&D note](../../docs/RND_ROLE_STRATIFIED_UPTAKE_CANARY_V0_8_3.md) and
the [framework-bound r13 artifact](../../artifacts/role_stratified_uptake_v0_8_3/r13_framework_bound/results.json).
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

See the [v0.8.4 R&D note](../../docs/RND_TYPED_REVISION_CHANNEL_V0_8_4.md) and the
[sealed report](../../artifacts/typed_revision_channel_v0_8_4/r01/report.md). The
[post-review interpretation receipt](../../artifacts/typed_revision_channel_v0_8_4/r01/post_review_interpretation.json)
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

See the [v0.8.5 R&D note](../../docs/RND_TYPED_PUBLIC_STATE_V0_8_5.md) and the
[sealed report](../../artifacts/typed_public_state_v0_8_5/r01/report.md).

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

See the [v0.8.5.1 R&D note](../../docs/RND_PUBLIC_ROLE_TRANSPORT_V0_8_5_1.md),
[sealed report](../../artifacts/public_role_transport_v0_8_5_1/r01/report.md), and
[post-run interpretation](../../artifacts/public_role_transport_v0_8_5_1/r01/post_run_interpretation.json).

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

See the [v0.8.5.2 R&D note](../../docs/RND_PUBLIC_ROLE_TRANSPORT_ISOLATION_V0_8_5_2.md),
[sealed report](../../artifacts/public_role_transport_isolation_v0_8_5_2/r01/report.md),
and [post-run interpretation](../../artifacts/public_role_transport_isolation_v0_8_5_2/r01/post_run_interpretation.json).

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

See the [v0.8.5.3 R&D note](../../docs/RND_PUBLIC_ROLE_ADAPTER_BREADTH_V0_8_5_3.md),
[sealed report](../../artifacts/public_role_adapter_breadth_v0_8_5_3/r01/report.md),
and [post-run interpretation](../../artifacts/public_role_adapter_breadth_v0_8_5_3/r01/post_run_interpretation.json).

### 11. Hosted-provider comparison

The standalone hosted runner connects the current core to the OpenAI Responses
API on Linux or macOS. Supply `OPENAI_API_KEY` through the environment, then run
from the repository root with the product dependencies installed:

```bash
python3 -m pip install -r requirements-product.txt
python3 ebrt_hosted.py --model gpt-5.6-sol \
  --output /tmp/ebrt-hosted-comparison.json
```

Choose a model available to your API account. The runner makes at most **two
generation attempts**: direct full context and EBRT credit-first, with identical
model settings and the same complete evidence. Each defaults to 1024 output
tokens, low reasoning effort, and a 60-second timeout. Retries are disabled;
failed attempts consume the two-call ceiling. Response storage for later API
retrieval is disabled (`store=False`), and incomplete, refused, empty, or
malformed outputs fail closed instead of being repaired or silently retried.

This is the existing known synthetic fixture, used as an integration check.
The report separates public surrogate execution, structural verification, and
post-run output grades. A passing result does not establish general reasoning
improvement or a causal benefit of the gradient.

The aggregate status and CLI exit code include **both** output grades. A
baseline output-contract failure remains `FAIL` even when hosted requests,
public mechanism checks, and the EBRT post-run contract pass. Inspect the
per-arm grades and `verification` fields to distinguish these outcomes.

`--output` exclusively creates a local JSON report outside the checkout with
mode `0600`; existing paths are rejected before any generation call. The report
contains provider request identifiers and usage in a separate local receipt
section. Review before export and keep it outside committed public artifacts.
The CLI prints a short comparison without credentials or raw SDK error bodies.

Run its network-zero tests with:

```bash
python3 -m unittest -v test_ebrt_hosted
```

### 12. Fresh required-support diagnostics

The support-retention runner tests a low-credit observation, a low-credit rule,
and an already-covered case whose correct answer stays unchanged. These are
three deliberately engineered synthetic diagnostics, not a random benchmark.
The observation and rule are both needed to derive each answer.

```bash
python3 ebrt_support_eval.py plan --model gpt-5.6-sol \
  --output /tmp/ebrt-support-plan.json
python3 ebrt_support_eval.py run --plan /tmp/ebrt-support-plan.json \
  --output /tmp/ebrt-support-results.json
python3 ebrt_support_eval.py verify --plan /tmp/ebrt-support-plan.json \
  --report /tmp/ebrt-support-results.json
```

`plan` and `verify` require no API calls. The plan fixes the cases, post-run
contracts, programs, actual prompts, generation settings, execution source
hashes, and cyclic arm order before generation. `run` checks that plan again
and permits at most nine generation attempts: three cases times three arms,
with no retries. Failed attempts consume the same budget. Output files stay
outside the checkout, are created exclusively, and use mode `0600`.

The candidate reserves slots for caller-declared required support, then ranks
within those constraints by the existing credit. It reuses the experimental
role-stratified compiler with the same three slots, 100 allocation units, and
original optimized control vector and L2 budget. Selected sites keep their
original signed control values. The already-covered case requires byte-equal
top-k and candidate prompts before any API call.

This diagnostic preserves the original legacy top-k and auxiliary-candidate
arms for comparison. The normal demo and hosted paths now use the admitted
coverage-first engine described below. Caller-supplied role quality and role
extraction are not evaluated. The report separates compiler coverage, retention of
compiled obligations, required-support retention, answer correctness, and
strict output grades. A completed run can contain failing output grades;
execution and offline integrity verification have separate statuses.
Execution `PASS` means all nine responses completed, parsed, and used matched
settings and model identity. Structural and output-contract grades remain
separate; execution success does not mean the core accepted every output.
Verification reparses visible outputs and recomputes grades and summaries;
it is not a provider signature or host attestation.

In the first predeclared nine-call block, all arms passed all three strict
output contracts. Candidate compiler coverage rose from 1/3 to 3/3; current
top-k and candidate generated byte-identical outputs in all three cases. The
coverage invariant is now the default selection policy; no generation-quality
gain is claimed. See the [R&D note](../../docs/RND_HOSTED_SUPPORT_RETENTION.md)
for the fixed protocol, results, and limits.

```bash
python3 -m unittest -v test_ebrt_support_eval
```

### 13. Numeric control alignment and evidence placement

The next diagnostic holds required-support coverage and revision instructions
fixed. Two fresh tasks contain a relevant entity join and an active competing
chain. Each compares the original numeric control mapping with a fixed
permutation of the same allocation/control tuples, crossed with chronological
and credit-first evidence ordering.

```bash
python3 ebrt_alignment_eval.py plan --model gpt-5.6-sol \
  --output /tmp/ebrt-alignment-plan.json
python3 ebrt_alignment_eval.py run --plan /tmp/ebrt-alignment-plan.json \
  --output /tmp/ebrt-alignment-results.json
python3 ebrt_alignment_eval.py verify --plan /tmp/ebrt-alignment-plan.json \
  --report /tmp/ebrt-alignment-results.json
```

`plan` and `verify` are offline. `run` spends at most eight attempts with no
retries. The plan fixes actual prompts, sources, contracts, settings, and
schedule, and checks that numeric-mapping pairs differ only in numeric
assignments while placement pairs differ only in evidence-record order.
Selected IDs and their program order, three slots, 100 allocation units, and
the numeric tuple multiset stay fixed. The standard engine does not admit the
permuted programs; they are auxiliary experimental conditions.

"Aligned" means the original core mapping, without assuming it is semantically
optimal. This small diagnostic examines sensitivity under a shared textual
program and gradient-derived ranking; it does not establish gradient
superiority or general reasoning improvement. See the
[protocol note](../../docs/RND_CONTROL_ALIGNMENT.md) for its scope and results.
In the first fixed eight-call block, all four conditions passed both strict
contracts. Every paired answer and support set matched; visible differences
only changed support-ID order. No numeric-control quality benefit was observed.
