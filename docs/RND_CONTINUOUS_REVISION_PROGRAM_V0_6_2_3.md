# EBRT Runtime Preview 2 — Continuous Revision Program

Status: **NETWORK-ZERO PRODUCT CONTRACT PASS; ONE HOSTED DELIVERY CANARY PASS; HOSTED UPTAKE, SEMANTIC QUALITY, AND EFFECT ATTRIBUTION NOT ASSESSED**

This note describes live protocol `v0.6.2.3`. Request, demo envelope, provider
contract, control, actuator, response, health, and error schemas move together,
so a v0.6.2.2 client fails before provider execution instead of consuming a
call and rejecting a newer response. The adapter's source v0.6.2.1 artifact
remains byte-pinned. Historical `ebrt.py`, the v0.6.2.1 artifact, and the
v0.6.2.2 report are not modified.

## One-horizon product path

```text
already-emitted public Before state
  -> typed late event
  -> candidate-graph incidence + typed-event public surrogate
  -> one torch.float64 backward()
  -> one projected continuous inspection-allocation update
  -> deterministic abstract inspection-budget compiler
  -> executable public revision state machine
  -> exactly one full-context hosted regeneration attempt
  -> public diff, lineage checks, and zero-call graph dependency probe
```

The controller allocates a unit public review budget over the eligible evidence
domain. For logits `u`, eligibility mask `M`, and fixed temperature `tau=1`:

```text
p(u) = masked_softmax(u / tau)
```

The public trajectory recurrence consumes those allocation fractions. Its
hand-built surrogate terminal-state loss plus a small allocation regularizer is
differentiated once at `u=0`; the resulting step is L2-bounded and accepted only
when the frozen surrogate objective decreases. Central finite differences,
simplex conservation, ineligible-zero allocation, objective descent, and the
gradient boundary are hard gates.

This is a real local optimization over the public surrogate. It is not a
gradient through GPT, and it does not imply that the hosted model uses the
allocation internally.

## Provider-visible continuous actuator

The optimized allocation is no longer reduced to a rank alone. The selected
reinspection rows retain their continuous shares and are deterministically
compiled into exactly 100 abstract public inspection units by a largest-
remainder allocator. The provider-visible plan carries:

```text
evidence ID
priority rank
controller allocation fraction
selected-plan inspection share
abstract inspection budget units
relative emphasis
review depth
```

These values are external review directives. They are not sampling
probabilities, attention weights, reasoning-token budgets, or provider usage
measurements. Raw evidence remains in its original chronological order and is
the only semantic authority.

## Executable public revision program

The compiled actuator is materialized before any provider attempt:

```text
LOAD_EVENT
  -> SUPPRESS*
  -> REINSPECT* with continuous allocation
  -> PRESERVE*
  -> PREPARE_FULL_CONTEXT_REGENERATION
```

The local executor validates every transition, emits an ordered execution
trace, and seals the exact provider operation against the source control map,
actuator, and prior public state. The engine separately validates the provider
receipt against the final payload fingerprint and reports that binding.
An invalid program fails before a provider call. The legacy reinspection,
suppression, and preservation ID lists remain exact derived summaries.

## Public block/restore dependency probe

After one candidate closure has been selected, a zero-provider-call probe masks
the correction evidence in that caller-supplied public graph, recomputes its
structural closure, removes the mask, and recomputes the baseline. A structural
`PASS` requires:

- every changed public fact was linked to the correction before blocking;
- that correction link is absent and the public lineage changes when blocked;
- the event invalidation transition no longer closes while blocked;
- stable-evidence binding remains present; and
- restoring the correction recreates the baseline closure byte-exactly.

This establishes only `PUBLIC_GRAPH_BLOCK_RESTORE` dependency on the selected
public graph. It does not show that a fact value or hosted output would change
under a provider counterfactual. The provider is not rerun.

## Status axes

The live response keeps the following separate:

```text
public_actuator_execution_status       PASS / FAIL
provider_delivery_status               PASS / FAIL
structural_dependency_status           PASS / FAIL
provider_uptake_status                 NOT_ASSESSED
counterfactual_output_effect_status    NOT_ASSESSED
semantic_correctness_status            NOT_ASSESSED
effect_attribution_status              NOT_ASSESSED
```

Therefore an operational `PASS` means the bounded public revision operation was
compiled, executed, delivered once, and structurally verified. It is not a
quality or causal-superiority result.

## Offline validation

```bash
python3 ebrt_live.py self-test
python3 ebrt_live.py apply-demo --provider scripted
```

The self-test denies network access and covers one backward call, finite-
difference agreement, objective descent, allocation simplex and budget bounds,
same-rank/different-magnitude provider-payload sensitivity, state-machine
execution, public block/restore locality, opaque candidate-ID map binding,
idempotency, one-attempt accounting, and the frozen v0.6.2.1 runtime hash.

The scripted path is plumbing only.

## One real-provider delivery canary

After every offline and Inspector gate passed, one explicit no-retry call was
made on 2026-07-21 JST using the known contaminated product fixture. GPT-5.6
accepted the new provider-input contract and returned a schema-valid result in
6.32 seconds. Accounting recorded exactly one logical/API call, 2,820 input
tokens, 150 output tokens, zero reported reasoning tokens, and 2,970 total
tokens. The public answer changed `POLISH -> PROVE`; actuator execution,
provider delivery, structural dependency, and overall operational acceptance
were `PASS`.

This canary is not a sealed benchmark artifact, matched contrast, or fresh
case. It confirms live contract compatibility only. `provider_uptake_status`,
semantic correctness, counterfactual output effect, and effect attribution all
remain `NOT_ASSESSED`.
