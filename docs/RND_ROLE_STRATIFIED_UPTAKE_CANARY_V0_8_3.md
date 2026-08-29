# EBRT v0.8.3 Role-Stratified Provider-Uptake Canary

Status: **COMPLETE DEVELOPMENT CANARY; MIXED RESULT; NOT A BENCHMARK**

Canonical stdlib-tree-bound integrity artifact:
[`artifacts/role_stratified_uptake_v0_8_3/r12_stdlib_tree_bound/results.json`](../artifacts/role_stratified_uptake_v0_8_3/r12_stdlib_tree_bound/results.json)

Preserved r11 post-call integrity failure:
[`artifacts/role_stratified_uptake_v0_8_3/r11_stdlib_bound_attempt01/postcall_failure.json`](../artifacts/role_stratified_uptake_v0_8_3/r11_stdlib_bound_attempt01/postcall_failure.json)

Preserved r10 zero-call preflight failure:
[`artifacts/role_stratified_uptake_v0_8_3/r10_stdlib_bound_attempt01/preflight_failure.json`](../artifacts/role_stratified_uptake_v0_8_3/r10_stdlib_bound_attempt01/preflight_failure.json)

Preserved startup-isolated integrity artifact:
[`artifacts/role_stratified_uptake_v0_8_3/r09_startup_isolated/results.json`](../artifacts/role_stratified_uptake_v0_8_3/r09_startup_isolated/results.json)

Preserved verified-source integrity artifact:
[`artifacts/role_stratified_uptake_v0_8_3/r08_verified_source/results.json`](../artifacts/role_stratified_uptake_v0_8_3/r08_verified_source/results.json)

Preserved complete-integrity artifact:
[`artifacts/role_stratified_uptake_v0_8_3/r07_complete_integrity/results.json`](../artifacts/role_stratified_uptake_v0_8_3/r07_complete_integrity/results.json)

Preserved immutable-model/runtime-code integrity artifact:
[`artifacts/role_stratified_uptake_v0_8_3/r06_immutable_runtime_code/results.json`](../artifacts/role_stratified_uptake_v0_8_3/r06_immutable_runtime_code/results.json)

Preserved runtime-version-bound artifact:
[`artifacts/role_stratified_uptake_v0_8_3/r05_runtime_bound/results.json`](../artifacts/role_stratified_uptake_v0_8_3/r05_runtime_bound/results.json)

Preserved loader-bound integrity artifact:
[`artifacts/role_stratified_uptake_v0_8_3/r04_loader_bound/results.json`](../artifacts/role_stratified_uptake_v0_8_3/r04_loader_bound/results.json)

Preserved exact-snapshot-bound artifact:
[`artifacts/role_stratified_uptake_v0_8_3/r03_snapshot_bound/results.json`](../artifacts/role_stratified_uptake_v0_8_3/r03_snapshot_bound/results.json)

Preserved source-bound artifact:
[`artifacts/role_stratified_uptake_v0_8_3/r02_integrity/results.json`](../artifacts/role_stratified_uptake_v0_8_3/r02_integrity/results.json)

Preserved original artifact:
[`artifacts/role_stratified_uptake_v0_8_3/r01/results.json`](../artifacts/role_stratified_uptake_v0_8_3/r01/results.json)

Pre-call lock:
[`policy_lock_role_stratified_uptake_v0_8_3.json`](../policy_lock_role_stratified_uptake_v0_8_3.json)

Integrity-replication lock:
[`policy_lock_role_stratified_uptake_v0_8_3_1_r02.json`](../policy_lock_role_stratified_uptake_v0_8_3_1_r02.json)

Exact-snapshot lock:
[`policy_lock_role_stratified_uptake_v0_8_3_2_r03.json`](../policy_lock_role_stratified_uptake_v0_8_3_2_r03.json)

Loader-bound staging lock:
[`policy_lock_role_stratified_uptake_v0_8_3_3_r04.json`](../policy_lock_role_stratified_uptake_v0_8_3_3_r04.json)

Exact-runtime lock:
[`policy_lock_role_stratified_uptake_v0_8_3_4_r05.json`](../policy_lock_role_stratified_uptake_v0_8_3_4_r05.json)

Immutable-model/runtime-code lock:
[`policy_lock_role_stratified_uptake_v0_8_3_5_r06.json`](../policy_lock_role_stratified_uptake_v0_8_3_5_r06.json)

Complete dependency/mount-binding lock:
[`policy_lock_role_stratified_uptake_v0_8_3_6_r07.json`](../policy_lock_role_stratified_uptake_v0_8_3_6_r07.json)

Verified-source execution lock:
[`policy_lock_role_stratified_uptake_v0_8_3_7_r08.json`](../policy_lock_role_stratified_uptake_v0_8_3_7_r08.json)

Startup-isolated execution lock:
[`policy_lock_role_stratified_uptake_v0_8_3_8_r09.json`](../policy_lock_role_stratified_uptake_v0_8_3_8_r09.json)

Imported-stdlib execution lock:
[`policy_lock_role_stratified_uptake_v0_8_3_9_r10.json`](../policy_lock_role_stratified_uptake_v0_8_3_9_r10.json)

Corrected imported-stdlib execution lock:
[`policy_lock_role_stratified_uptake_v0_8_3_10_r11.json`](../policy_lock_role_stratified_uptake_v0_8_3_10_r11.json)

Complete stdlib-code-tree execution lock:
[`policy_lock_role_stratified_uptake_v0_8_3_11_r12.json`](../policy_lock_role_stratified_uptake_v0_8_3_11_r12.json)

## Question

The v0.8.2 corpus exposed two different failures:

```text
backward credit
  -> scalar top-k compiler       # may drop a required public role
  -> model-visible request
  -> generated support lineage  # may omit a compiled obligation
```

This canary asks whether a minimal public-role coverage floor repairs the first
boundary, and whether that repair reaches the second boundary in one real local
generator.

It does not ask whether role-stratified EBRT is generally better. The arms have
different provider-visible requests, the public roles are caller-supplied, and
there are only three development cases over one model snapshot.

## Locked geometry

- Source main commit: `2961feb6aaa2222bb56a62cb04274587487f4a17`.
- Original lock commit before r01 calls: `8a04d04`.
- Strengthened lock commit before r02 calls: `c6e6ee7`.
- Exact snapshot-manifest lock commit before r03 calls: `34f7807`.
- Loader-bound staging lock commit before r04 calls: `9f2b754`.
- Exact-runtime lock commit before r05 calls: `9894121`.
- Immutable-model/runtime-code lock commit before r06 calls: `5ad3ee2`.
- Complete dependency/mount-binding lock commit before r07 calls: `9d2027c`.
- Verified-source execution lock commit before r08 calls: `15833fc`.
- Startup-isolated execution lock commit before r09 calls: `5a573d0`.
- Imported-stdlib lock commit before the zero-call r10 failure: `34c84ea`.
- Corrected imported-stdlib lock commit before the r11 calls: `0ef1062`.
- Complete stdlib-code-tree lock commit before r12 calls: `61e1895`.
- Model: `mlx-community/Mistral-7B-Instruct-v0.3-4bit@a4b8f...`.
- Three fresh synthetic late-event cases.
- Three arms and one generation per arm:
  - `direct_full_context`;
  - `ebrt_top_k`;
  - `ebrt_role_stratified`.
- Each arm occupies each serial position exactly once.
- `temperature=0`, `seed=0`, 48 generated-token ceiling.
- No automatic retry and no native-state capture.
- Semantic contracts remain post-call-only.

Codex review found two attribution gaps after r01: an arbitrary external model
directory could carry the explicit locked ID, and the pre-call lock hashed the
canary runner without hashing the imported core/corpus implementation. The r01
artifact remains immutable. r02 requires the exact content-address-verified
Hugging Face cache snapshot and binds SHA-256 hashes for the wrapper plus every
repository-local implementation file on the execution path.

r02 repeats already observed cases and therefore is not fresh replication
evidence. Its nine public outputs are byte-identical to r01 (`9/9`); it only
strengthens execution attribution.

A second review found that a cache directory could retain the expected path
and revision name while pointing at a different internally consistent blob
set. r03 therefore locks all seven expected snapshot-relative files by path,
byte size, and blob address. Git-blob SHA-1 and SHA-256 addresses are each
verified against file content immediately before and after the calls. r03 is
also a contaminated integrity repetition, not new evidence. All public outputs
remain byte-identical across r01/r02/r03 (`9/9`).

A third review identified a remaining time-of-check/time-of-use boundary:
the cache symlinks could in principle be changed while MLX loaded the model
and restored before the post-call manifest check. r04 therefore clones the
seven exact locked blobs into a private APFS copy-on-write tree, requires
regular files with source-distinct inodes, marks the tree read-only during
loading and generation, and passes only that isolated path to MLX. The staged
manifest is rehashed after all calls. r04 is again an integrity repetition
over known cases, not fresh evidence. All public outputs remain byte-identical
across r01/r02/r03/r04 (`9/9`).

A fourth review identified that `mlx-lm>=0.31.2` still admitted changed loader,
chat-template, sampling, or generation semantics under the same execution lock.
r05 therefore binds CPython, macOS, architecture, and the exact installed
versions of MLX, `mlx-lm`, Torch, Transformers, tokenizers, safetensors,
Hugging Face Hub, and NumPy. The same runtime receipt is checked before and
after all calls. This is a version-identity receipt, not signed binary or
hardware attestation, and r05 remains a contaminated integrity repetition.
All public outputs remain byte-identical across r01/r02/r03/r04/r05 (`9/9`).

A fifth review noted that owner-reversible mode bits did not make the r04
staging tree immutable to another process under the same account. It also
noted that r05 distribution version strings did not exclude shadowed or
locally modified module code. r06 therefore loads the exact model from an APFS
read-only disk image, unlinks the backing image pathname before model load,
and verifies the mounted seven-file manifest before and after calls. It also
binds aggregate content hashes for 16,031 files across the eight recorded
distributions plus the origins and hashes of 1,314 actually imported modules.
The claim stops short of hardware, kernel, code-signing, or malicious-root
attestation. r06 is still a contaminated integrity repetition, and all public
outputs remain byte-identical across r01/r02/r03/r04/r05/r06 (`9/9`).

A sixth review found two narrower receipt gaps. First, r06 bound eight selected
distributions but not every distribution that owned imported non-standard-
library code; for example, chat-template execution imported Jinja2. Second,
its portable verifier checked only that the mount receipt remained unchanged,
not that it equaled the exact staged-manifest and clone fingerprints derived
from the locked snapshot. r07 closes both gaps: it binds 3,039 imported
file-backed non-standard-library modules to 42 owning distributions and 10
repository modules to repository-relative source receipts, commits the full
content of 34,910 distribution files, and compares the embedded mount receipt
with both exact locked fingerprints. The portable verifier passes all eight
checks. r07 is still a contaminated integrity repetition over known cases, not
fresh scientific evidence, and all nine public outputs remain byte-identical
across r01/r02/r03/r04/r05/r06/r07.

A seventh review identified a CPython-specific execution gap: a
timestamp-valid generated `.pyc` can contain bytecode that differs from its
corresponding locked `.py`, while `module.__file__` still points at that source
and package manifests omit the generated cache. r08 starts a child interpreter
before importing repository or site-package modules, assigns it a fresh empty
`pycache_prefix`, and disables bytecode writes. This makes CPython ignore
adjacent caches and compile 2,861 Python modules from the content-bound source;
189 native-extension modules remain content-bound by the r07 receipt. A local
self-test demonstrates both sides with a deliberately divergent,
timestamp-valid cache: the ordinary interpreter returns the cached value while
the r08 policy returns the source value. Portable verification passes all nine
checks. r08 remains a contaminated integrity repetition, not fresh scientific
evidence, and all nine public outputs remain byte-identical across r01-r08.

An eighth review identified an earlier startup boundary: the outer r08 Python
process could still import environment-provided paths or automatically process
`.pth`, `sitecustomize`, and `usercustomize` before its source-only child was
launched. r09 requires `python3 -E -S` at the outer CLI and repeats those flags
for the child, failing closed otherwise. It adds only the two explicit,
pre-call-locked site-package roots after startup without running `site.main()`
or customization hooks, while retaining `-B` and the fresh empty
`pycache_prefix`. A local self-test shows an actual `sitecustomize` fixture
running under ordinary Python but not under the admitted path. Portable
verification passes all 12 checks. r09 is a contaminated integrity repetition
over the known r01-r08 cases, not fresh scientific evidence; all nine public
outputs remain byte-identical across r01-r09 (`9/9`).

A ninth review observed that r09 still trusted the CPython executable and
standard-library implementation behind its version string. r10 sealed the two
interpreter paths plus 392 imported file-backed stdlib modules. Its first run
failed before provider calls because the wrapper re-entered r09's historical
exact-module gate with a new `__main__` module; that zero-call failure is
retained. r11 corrected the plumbing and completed all nine calls, then failed
before artifact write because its exact imported-stdlib set grew from 392 to
397 through legitimate lazy imports. That post-call failure is also retained
and contributes no result rows.

r12 fixes the representation rather than weakening the gate. It locks the
complete standard-library code universe: 1,761 Python source files and 78
native extensions, plus the resolved CPython executable. Pre- and post-call
coverage receipts may contain different imported-module sets, but every member
must resolve into the same locked tree with exact size and SHA-256. The observed
392-to-397 expansion passes that contract; the tree itself is unchanged, the
portable verifier passes all 16 checks, and all complete r01-r09/r12 public
outputs are byte-identical (`9/9`). r12 remains a contaminated integrity
repetition, not fresh evidence. Its boundary excludes non-code stdlib data,
dyld/shared system libraries, kernel, hardware, code signing, and malicious
root behavior.

The candidate reserves capacity for the correction plus every public evidence
node whose caller-supplied role is `required_support`, then fills remaining
capacity by absolute backward-credit magnitude. The total allocation remains
100 units and uses the same signed controls, suppression, preservation, and one
full-context regeneration boundary as scalar top-k.

## Result

| Measurement | Scalar top-k | Role-stratified |
| :--- | ---: | ---: |
| Compiler coverage | 1/3 | 3/3 |
| Provider uptake | 2/3 | 2/3 |
| Strict semantic pass | 2/3 | 2/3 |

The direct arm also passed `2/3` strict semantic contracts.

Across top-k versus role-stratified outputs:

- raw output changed in `2/3` cases;
- support lineage changed in `2/3` cases; and
- the final answer changed in `1/3` cases.

The deterministic compiler repair succeeded exactly where intended. It did not
produce an aggregate provider-uptake or strict-semantic gain.

## Case atlas

### Parcel dock policy

The scalar compiler selected `R6,R4,R1`, dropping required identity evidence
`R2`. The role compiler selected `R6,R4,R2`.

```diff
 ANSWER=DOCK_A
-SUPPORT=R6,R4,R1,R2,R5
+SUPPORT=R6,R4,R2
```

Both controlled outputs passed. Even though scalar top-k did not compile `R2`,
the generator recovered it from full raw context. The role candidate removed
the irrelevant context citation and preserve-only leakage in this one case.

### Scaled reading schema

The scalar compiler selected `R6,R1,R2`, dropping required rule evidence `R4`.
The role compiler selected `R6,R2,R4`.

```diff
-ANSWER=60_UNITS
-SUPPORT=R1,R2,R4,R5
+ANSWER=6_UNITS
+SUPPORT=R2,R4,R5
```

This is the only answer-level difference. Direct and scalar top-k emitted the
old value `60_UNITS`; the candidate emitted the expected `6_UNITS`. However,
both controlled outputs omitted compiled correction evidence `R6`. The
candidate therefore failed provider uptake and the strict semantic contract.
This is an observed fresh-case difference, not evidence that role placement
caused the improvement.

### Grant eligibility policy

Both compilers selected `R6,R4,R2`. Their provider-visible prompts were
byte-identical and Mistral emitted the same output in both serial positions:

```text
ANSWER=ELIGIBLE
SUPPORT=R6,R4,R2
```

This is the canary's no-op/invariance control.

## Interpretation

The result localizes the remaining bottleneck.

1. **Coverage loss is repaired at compile time.** The role floor prevents a
   high-credit context node from displacing a required public role.
2. **Full raw context can compensate for compiler omissions.** In the parcel
   case, top-k omitted `R2` but the generator cited it anyway.
3. **Complete compilation does not guarantee uptake.** In the numeric case,
   both controlled arms omitted `R6` despite explicit compilation and prompt
   language requiring the late correction.
4. **Answer and lineage remain different axes.** The role candidate produced
   the expected numeric answer while still failing correction provenance.

The next bounded iteration should not increase gradient magnitude. It should
test a smaller typed output channel that separates decision support from
revision provenance, for example:

```text
ANSWER=6_UNITS
SUPPORT=R2,R4
REVISION_EVENT=R6
```

That would test whether the provider can retain compiled obligations when the
schema gives correction provenance its own slot. It remains a provider-channel
experiment, not a hidden-state or general reasoning claim.

## Claim boundary

- Public `required_support` roles are supplied by the synthetic task author.
- The local backward pass is real, but the generator lies beyond a
  stop-gradient boundary.
- Arms differ in evidence order, actuator payload, and prompt text.
- One fresh answer difference does not establish a causal effect.
- `PASS` for compiler coverage, provider uptake, or semantic correctness does
  not imply either of the other two.
- No cross-model conclusion is admitted.
