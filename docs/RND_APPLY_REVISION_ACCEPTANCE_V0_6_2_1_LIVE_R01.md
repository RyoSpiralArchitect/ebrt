# EBRT v0.6.2.1 — Apply Revision Acceptance live r01

Status: **COMPLETE — PRODUCT ACCEPTANCE PASS; EFFECT ATTRIBUTION NOT ASSESSED**

This is the immutable result note for the first authorized
`Apply Revision -> Regenerate` product-acceptance run. It is one contaminated,
case-specific synthetic integration acceptance, not a fresh benchmark or a
matched causal comparison.

## Sealed execution

- Reviewed runtime PR: `#30`
- Authorized merge commit: `0dc6d738e5e8e870796c1ec9b0e2e442b2a88a7e`
- Annotated authorization tag:
  `v0.6.2.1-apply-revision-live-r01-authorized`
- Policy-lock fingerprint:
  `31b27497b6ff05369e9f33110f6faa1c3765a2e4caae710a2aa7d7661c4f111e`
- Provider attempts: exactly `2`, with no retry, resume, backfill, or third call
- Canonical artifact:
  `artifacts/apply_revision_acceptance_v0_6_2_1_live_r01/`
- Result fingerprint:
  `1ba3cfe9565124d92fa8db8222c4d44bc62a81e1da7c6fad07e24e9a8e7ad245`

The fresh execution worktree satisfied all live prerequisites before the first
attempt: clean `HEAD`, `origin/main`, and the annotated authorization tag all
resolved to the same commit; the policy lock was exact; the API key was
available; and both the output and inflight namespaces were absent.

## Product acceptance result

| Axis | Result |
| --- | --- |
| Run | `COMPLETE_EXACT_TWO_TERMINALS` |
| Mechanism | `PASS` |
| Before | `PASS_THEN_STALE` |
| After | `PASS_STRICT_POST_EVENT` |
| Public diff | `OBSERVED_EXPECTED_PUBLIC_DIFF` |
| Product acceptance | `PASS` |
| Effect attribution | `NOT_ASSESSED` |
| Terminal | `ACCEPT_APPLY_REVISION_PATH` |

The same actual Before bytes passed their original R1-R5 horizon and failed
when regraded under the R1-R6 post-event contract. No replacement Before was
fabricated for the stale test.

```text
Before answer     POLISH
Before closure    K_c9dc959be3

Late event        R6 supersedes R3

local backward()  1 call, float64
objective         0.8485741564 -> 0.6693646353
control L2        0.0965388843 <= 0.25

Apply Revision
  Reinspect       R6 -> R4 -> R2
  Suppress        R3
  Preserve        R5

After answer      PROVE
After closure     K_d59ad14817
```

The final public diff changed `final_priority` from `ADDITIONAL_UI_POLISH` to
`END_TO_END_PROOF` and `demo_centerpiece` from `POLISHED_SCREENS` to
`LIVE_REASONING_DIFF`. `THREE_MINUTE_NARRATED` remained unchanged. R4 and R6
entered active support, R3 left active support and was explicitly invalidated,
and every After fact-local lineage check passed.

The provider saw only the mechanically compiled public operation. It did not
receive an expected answer, accepted closure ID, required gold support set,
loss, gradient, grade, or semantic gold. The post-call gold file was parsed
only after two structurally valid terminals and from the exact byte buffer
whose `{path, bytes, sha256}` receipt matched the policy lock.

## Cost receipt

| Metric | Observed |
| --- | ---: |
| API calls | 2 |
| Input tokens | 3,274 |
| Output tokens | 338 |
| Reasoning tokens | 38 |
| Total tokens | 3,612 |
| Aggregate latency | 9,304.386 ms |

Provider reasoning tokens are usage accounting only. They are not reasoning
text and are not interpreted as a quality measure.

## Verification

The monolith revalidated the published bundle immediately after publication:

```bash
python3 ebrt.py validate
```

The result package preserves seven canonical files: `result.json`,
`calls.jsonl`, `attempt_journal.jsonl`, `provider_inputs.json`,
`apply_revision_trace.json`, `report.md`, and `manifest.json`. The portable
verification script added beside this note independently rechecks the frozen
bytes without importing the EBRT runtime or third-party packages.

```bash
python3 -I -S verify_apply_revision_acceptance_v0_6_2_1_live_r01.py \
  artifacts/apply_revision_acceptance_v0_6_2_1_live_r01
python3 -I -S verify_apply_revision_acceptance_v0_6_2_1_live_r01.py \
  --self-test artifacts/apply_revision_acceptance_v0_6_2_1_live_r01
```

The foreign-root validation returns `VALID`; the adversarial self-test passes
nine checks covering pristine reconstruction, coherent accounting, control,
journal, receipt and dynamic-payload tampering, duplicate/nonfinite JSON, and
extra-file rejection. Both paths make zero network calls.

## Claim boundary

This result establishes one executable, observable, and strictly verifiable
Apply Revision path. It does **not** establish that the control map caused the
changed answer. It does not support hidden-state editing, attention or KV-cache
control, gradient flow through GPT-5.6, causal superiority, quality
improvement, or general reasoning improvement.

The product story is therefore precise:

> EBRT computes backward credit over an external public reasoning trajectory,
> compiles a bounded revision operation, carries it through one full-context
> hosted regeneration, and verifies the resulting public output and lineage.

The Reasoning IDE is the operation panel and verifier for that engine. It is
not evidence that the engine's intervention was causally necessary.

Its committed public projection is independently deterministic and pinned to
the exact manifest, result, trace, and projection bytes. The browser verifies
the snapshot hash before rendering. `Replay recorded Apply Revision` performs
local playback only; it issues no provider request and cannot alter the sealed
result.
