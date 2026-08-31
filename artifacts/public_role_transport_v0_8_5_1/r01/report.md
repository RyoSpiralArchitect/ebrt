# EBRT v0.8.5.1 r01 — Public Role Transport Result

## Execution

The pre-call lock was committed and pushed at `08f5a54` before either exact
local model snapshot received a call. The block completed 12 logical calls
with temperature `0`, seed `0`, a 96-token ceiling, and no retry.

| Model | `FORMAT_READY` | `TASK_CHANNEL_READY` | Regression cells |
| --- | ---: | ---: | ---: |
| Mistral 7B | PASS | PASS | 4 |
| Qwen 1.5B | PASS | FAIL | 0 |

The runner and portable verifier both passed. No native state was captured and
no gradient crossed either model adapter.

## Known-failure transition

Mistral changed from the v0.8.5 failed state:

```text
answer=GATE_RED
decision_support=R2,R4
revision_event=R6
preserved=R1,R5
```

to a strict v0.8.5.1 pass:

```text
answer=GATE_BLUE
decision_support=R2,R4
revision_event=R6
preserved=R5
```

Qwen emitted byte-identical task-shaped public state across the two versions:

```text
answer=GATE_BLUE
decision_support=R4
revision_event=R6
preserved=R5
```

It still omitted required identity evidence `R2`, so the gate stopped it before
every contaminated regression cell.

This is one contaminated `FAIL -> PASS` transition and one contaminated
`FAIL -> FAIL` transition. It is an adapter diagnostic, not cross-model
quality evidence.

## Admitted Mistral regression surface

Mistral produced strict passes in `3/4` cells for both arms. The remaining
`credit-scale-rule-revision` cell selected retired `45_CREDITS` rather than
current `15_CREDITS`; both arms nevertheless emitted exact decision support
`R2,R4`, revision event `R6`, and preserved constraint `R5`.

```text
direct_public_roles:       3/4 strict PASS
role_control_public_roles: 3/4 strict PASS
provider uptake:           4/4 PASS
strict repairs:            0
strict regressions:        0
```

The raw strings differed in `4/4` cells and parsed list order differed in
`3/4`. After sorting set-valued support and preservation channels, however,
the complete public state was identical in `4/4` cells and answers differed in
`0/4`. All observed direct/control differences were serialization or list-order
only. The admitted semantic control effect is therefore null on this surface.

## Post-run prompt audit

The intended change was the new evidence `role` field. Deterministic prompt
projection found one additional model-visible difference:

```diff
-You are a full-context generator behind the EBRT typed-state adapter.
+You are a full-context generator behind the EBRT public-role adapter.
```

Therefore v0.8.5.1 is labeled:

```text
BUNDLED_PUBLIC_ROLE_PLUS_ADAPTER_LABEL
role_only_effect_status = NOT_IDENTIFIED
```

This artifact is preserved and not rerun or relabeled as a role-only test. A
successor must restore the exact v0.8.5 adapter-label line, retain the role
field, freeze a new lock, and execute under a new namespace.

## Receipts

- Policy-lock fingerprint:
  `d97217a00106e23d46100e5fd9c9134cf6255652f71197e7ed6d259ac9fc573b`
- Results fingerprint:
  `ba33b30c9f1840381bf3bd5f9640fe6e9c31d81fb171697413ebc4e200149a1a`
- Results file SHA-256:
  `c8b9d970b431bf4c42df877c9752a0a0956b5a6fe9bc2a7183a495c557c2816c`
- Portable verification fingerprint:
  `8f6cb91191739926e015031ae2f3294f6f6a51a76d28089cdc7ded2fb30575c0`
- Post-run interpretation fingerprint:
  `ec5958b169f9d587b6c18d687ccca0e5105c0e606f20d392f3be9a604f3d162f`

## Claim boundary

- The readiness fixture and all regression cases are contaminated.
- Caller-supplied public roles are scaffold metadata, not autonomously
  discovered dependencies.
- The Mistral readiness repair cannot be attributed to the role field alone.
- The admitted direct/control semantic public-state difference was `0/4`.
- No causal superiority, general reasoning improvement, or cross-model
  regularity is claimed.
