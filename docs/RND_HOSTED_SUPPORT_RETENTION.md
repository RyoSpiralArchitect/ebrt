# Hosted support-retention diagnostic

Status: **EXECUTED; NO OBSERVED GENERATION BENEFIT FROM THE CANDIDATE**

One predeclared nine-call block used `gpt-5.6-sol` on 2026-10-22
(Asia/Tokyo). All three arms answered all three new synthetic cases correctly
and retained the complete required support. The public-role candidate repaired
compiler coverage from 1/3 to 3/3, but its generated outputs were byte-identical
to the current top-k outputs in every paired case. The coverage invariant is
now the default selection policy. This run does not establish a generation
quality improvement.

## Problem and cases

The previous known-fixture smoke omitted `R2` in direct generation. That
fixture's `R2` repeats general judging context. Here, the observation and current
rule are both needed to derive the answer, so required support is more than a
redundant citation checklist. This does not establish why the earlier omission
occurred; the new cases change several task details.

| Case | Required observation (`R2`) | Required rule (`R4`) | Correct answer | Intended compiler diagnostic |
| --- | --- | --- | --- | --- |
| Normalization | Raw reading 14 | Multiply by 2 | `28_UNITS` | Current top-k omits low-credit R2 |
| Parcel routing | Class N | Class M → HARBOR; class N → RIDGE | `RIDGE` | Current top-k omits low-credit R4 |
| Duration control | 8 hours | Allow at most 12 hours | `ALLOW` | Both compilers already cover all required support |

In every case `R6` retires the old rule in `R3`, and `R5` remains a stable
constraint. The duration case was already `ALLOW` under the retired policy;
correct revision does not always flip the answer. The cases and hand-built
public geometries deliberately expose compiler coverage conditions. They are
not a random sample or a general reasoning benchmark.

## Fixed comparison

- Direct full context, current EBRT top-k, and a public-role coverage candidate.
- Three selection slots, 100 allocation units, and the same verified optimized
  control vector and 0.75 L2 budget for the controlled arms. Each selected site
  retains its original signed control; selected subsets need not have equal
  norms.
- The candidate reuses the role-stratified compiler. It reserves correction
  and caller-declared required-support slots, then ranks by existing credit.
  It does not extract roles or receive the post-run contract.
- Both controlled arms receive the full evidence. For the already-covered
  duration case, their actual prompts must be byte-identical before execution.
- Cyclic arm order across the three cases, one call per cell, no retries, and
  a global limit of nine attempts. All requests used the same model, low
  reasoning effort, 1024 output-token ceiling, and 60-second timeout.
- Cases, contracts, programs, prompts, source hashes, settings, and schedule
  were saved before the first API call. Code was fixed at commit `517ad27`.

## Observed results

| Arm | Correct answer | Complete required support | Strict output contract | Compiler coverage | Compiled required-obligation uptake |
| --- | --- | --- | --- | --- | --- |
| Direct full context | 3/3 | 3/3 | 3/3 | N/A | N/A |
| Current EBRT top-k | 3/3 | 3/3 | 3/3 | 1/3 | 3/3 |
| Role coverage candidate | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |

All nine calls completed and parsed. Controlled outputs passed their structural
and post-run checks. Current top-k retained all required support even when its
compiled reinspection list omitted a required item: that evidence remained
available in the full context. Uptake of compiled obligations therefore must
not be mistaken for complete compiler coverage.

Top-k and candidate outputs were byte-identical in each case, including the
two cases where their programs differed. The result demonstrates the coverage
repair and a working evaluation path, without an observed generation benefit.

## Verification and local receipts

The plan fingerprint is:

```text
eeb51f0f5cad6325a93f0fe82a183a411f8bdb1922270dbe46f14d62213d03f7
```

The local report fingerprint is:

```text
e0ab2e5ef787ae46a8101be5eeb487aeb605a4f29b7b52c4ca38ca4650ac5c60
```

Offline verification reparsed all nine visible responses and recomputed grades,
coverage, uptake, structural checks, comparisons, and summaries. It passed.
The plan and full report remain outside the checkout with mode `0600`;
provider identifiers and detailed receipts are not included in this note.
Verification checks internal consistency, not provider authenticity or host
attestation.

Validation also passed 51 network-zero tests and the existing 90 core checks.
Tests cover gold-contract noninterference, the unchanged-answer control,
capacity and attempt limits, failure retention, output-path preflight, and
coherently resealed plan or grade tampering.

## Mainline admission

The diagnostic's original auxiliary labels describe the measured protocol.
`ebrt_engine.RevisionEngine` now admits a production `CoverageFirstActuator`
and is the default for `ebrt_demo.py` and `ebrt_hosted.py`. The production
compiler matches the measured candidate on all three cases. Promotion adopts
its complete-selection invariant as an engineering requirement; it does not
reinterpret the null generation result.

The historical optimizer, reference engines, source locks, and artifacts remain
unchanged. The new engine obtains the verified trajectory through an internal
compile-only run, then checks the exact coverage program and actual model
receipt. Missing capacity, unavailable mandatory control, unfillable slots,
or a positive control rounded to zero allocation stops before the actual
model call. Role quality remains caller-supplied.

Admission validation passed 75 offline tests and all 90 historical core
checks. A separate adversarial review found no required fixes after checking
optimizer replay, program and descriptor mutation, gold noninterference, and
provider-call accounting. A bounded three-call `gpt-5.6-sol` integration smoke
then ran the production engine once on each case: all three passed structural
and strict post-run checks. That smoke validates the new execution path and
does not add a comparative generation-quality result. Detailed provider
receipts remain local and are not committed.

Source-pinned reports are verified at their recorded revision. The original
nine-cell block was reverified successfully from a source snapshot at `517ad27`
after mainline admission, without modifying the plan, scores, or expected
checksums. From the repository root, with the retained local files:

```bash
set -o pipefail
replay_dir=$(mktemp -d /tmp/ebrt-replay.XXXXXX)
git archive 517ad27 | tar -x -C "$replay_dir"
.venv/bin/python "$replay_dir/ebrt_support_eval.py" verify \
  --plan /workspace/setup-logs/support-retention-plan-r01.json \
  --report /workspace/setup-logs/support-retention-results-r01.json
```

## Next target

Generation did not improve in this small block. Role extraction,
gradient-specific effects, and general quality remain unassessed.

The next useful gate is a separately predeclared set with competing evidence
chains and distractors, plus matched textual and placement controls. Keep the
support dependency contract explicit and inspect all arm failures, including
null outcomes, before changing the core optimizer or promoting an actuator.
