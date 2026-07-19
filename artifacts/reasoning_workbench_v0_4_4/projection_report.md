# EBRT v0.4.4 Reasoning Workbench projection

## Status

This is a deterministic, read-only projection of recorded public artifacts. It performs zero network calls and does not apply a live revision.

## Mechanically selected episode

- Rule: `episode_manifest.case_ids[0]`
- Case: `route_code_supersession`
- Trial: `0`
- Run: `openai_live_smoke:0:route_code_supersession`
- Source trace: `b8b7496fcc83d5726501f6dedbaa3472b5468594e9b0ed0a24e1dc2f43436841`
- Initial state: `pre_event / initial_answer_match` (not post-event PASS/FAIL)

## Recorded replay lanes

| Lane | Replay calls | Regenerated cards | Final answer | Machine grade |
| --- | ---: | ---: | --- | --- |
| `card_only_forward` | 1 | 1 | `AMBER` | FAIL |
| `selective_replay` | 4 | 4 | `AMBER` | FAIL |
| `full_restart` | 6 | 6 | `BLUE` | PASS |

All three lanes share the same recorded pre-outcome plan fingerprint: `56477ce3887021b2cd4f4bd7ad93843de1d594d003f20305eb17a86e79d929b1`.

The visible output diff is derived only from public Reasoning Cards. The retained negative lanes are part of the artifact, not hidden.

## Separate aperture context

- v0.4.1 status: `INCOMPLETE`; locked decision ready: `false`.
- v0.4.2 unchanged replication: `31` non-assessable endpoints; no locked aperture decision.

These are separate experiment blocks and are not the same causal episode.

## Provider Failure Atlas

| Boundary | Count |
| --- | ---: |
| Client attempts | 8 |
| HTTP observations | 8 |
| Structured parses | 0 |
| Accepted outputs | 0 |
| Assessed endpoints | 0 |

- HTTP status distribution derived from pinned receipts: `429:8`.
- v0.4.3 typed failure derived from the same receipts: `http_status/insufficient_quota` (8/8).
- Native diagnostic coverage: r01 `0/31` vs v0.4.3 `8/8`.
- Coverage authority: `v0.4.3_policy_exact_schedule_projection`.
- Coverage lineage: post-freeze derived correction, no live call; provider-observation artifact hashes unchanged.
- Cross-block effect estimate: `null`.
- v0.4.3 full block: not launched; reasoning comparison unavailable.

## Gates

- `live_execution_ready`: `false`
- `locked_reasoning_decision_ready`: `false`
- `promotion_eligible`: `false`
- `provider_diagnostic_integrity_ready`: `true`
- `projection_integrity_ready`: `true`
- `reasoning_improvement_claim_ready`: `false`
- `recorded_demo_ready`: `true`
- `recorded_episode_integrity_ready`: `true`

## Claim boundary

- This is a deterministic read-only projection of recorded public artifacts; it does not execute a model or apply a live revision.
- The selected v0.4 episode is a DEV smoke case and does not establish general reasoning improvement.
- Public Reasoning Cards, evidence, grades, and sanitized accounting are observable outputs, not private chain-of-thought or hidden model state.
- The v0.4.1 and v0.4.2 aperture blocks are context from separate experiments and are not the same causal episode as the recorded replay.
- The v0.4.3 Provider Failure Atlas measures diagnostic classification coverage, not reasoning quality or a cross-block causal effect.
- The authoritative v0.4.3 coverage fields are a post-freeze derived correction with no live call; the recorded provider-observation artifact hashes remain unchanged.
- No model weights, hidden states, or persisted provider response state are modified.

## Reproducibility

- Projection fingerprint: `6c5cf6d62546fd4c3a2029f63b6468e0ad21dc0868f09aa90d411cc46089ab6a`
- Projection lock: `e48eb520b15fd0c96a654721e76f08923439ed1e9f74b7cccb81372f81653385`
- Builder: `9d906c2f9e5cb1ace14ed12ab35dd4f1cc03c1e3f50a4a131c53fb7354bbcce6`
- Canonical and public snapshots are required to be byte-identical.
- Timestamps are intentionally absent.
