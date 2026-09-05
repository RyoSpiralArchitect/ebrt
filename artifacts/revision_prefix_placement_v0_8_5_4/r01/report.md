# Revision-prefix placement canary v0.8.5.4

Known four-case engineering regression; one deterministic sample per arm. No gradient-only or generalization claim.

- Run: `COMPLETE_BOUNDED_CANARY`
- Logical calls: 14; cases per arm: 4
- Strict passes: `{'append': 2, 'baseline': 3, 'prepend': 0}`
- Append/prepend semantic differences: 1 / 3 parsed pairs
- Append/prepend answer differences: 0
- Stable evidence citation is observable; the value of a stable fact is not emitted by this schema.
- Token counts include terminal tokens; equal output ceilings do not establish equal actual compute.

## freight-lane-rule-revision

| Arm | Strict | Input tokens | Output tokens | Latency ms |
| --- | --- | ---: | ---: | ---: |
| append | PASS | 852 | 53 | 6775.8 |
| baseline | PASS | 671 | 53 | 6309.3 |
| prepend | FAIL | 852 | 56 | 6988.6 |

### append

```text
STATE_JSON={"answer":"LANE_SOUTH","decision_support_ids":["R2","R4"],"revision_event_id":"R6","preserved_constraint_ids":["R5"]}
```

Diagnostics: `{"extra_decision_support_ids":[],"extra_preserved_constraint_ids":[],"invalidated_evidence_ids_present":[],"missed_decision_support_ids":[],"missed_preserved_constraint_ids":[],"stable_value_preservation_status":"NOT_OBSERVABLE_IN_CURRENT_OUTPUT_SCHEMA","stale_answer_retained":false,"wrong_answer_value":false,"wrong_revision_event":false}`

### baseline

```text
STATE_JSON={"answer":"LANE_SOUTH","decision_support_ids":["R2","R4"],"revision_event_id":"R6","preserved_constraint_ids":["R5"]}
```

Diagnostics: `{"extra_decision_support_ids":[],"extra_preserved_constraint_ids":[],"invalidated_evidence_ids_present":[],"missed_decision_support_ids":[],"missed_preserved_constraint_ids":[],"stable_value_preservation_status":"NOT_OBSERVABLE_IN_CURRENT_OUTPUT_SCHEMA","stale_answer_retained":false,"wrong_answer_value":false,"wrong_revision_event":false}`

### prepend

```text
STATE_JSON={"answer":"LANE_SOUTH","decision_support_ids":["R2","R4","R6"],"revision_event_id":"R6","preserved_constraint_ids":["R5"]}
```

Diagnostics: `null`

Normalized comparisons:

- baseline → append: answers `['LANE_SOUTH', 'LANE_SOUTH']`; semantic change `False`; strict repair `False`; strict regression `False`
- baseline → prepend: answers `['LANE_SOUTH', None]`; semantic change `None`; strict repair `False`; strict regression `True`
- append → prepend: answers `['LANE_SOUTH', None]`; semantic change `None`; strict repair `False`; strict regression `True`

## credit-scale-rule-revision

| Arm | Strict | Input tokens | Output tokens | Latency ms |
| --- | --- | ---: | ---: | ---: |
| append | FAIL | 827 | 53 | 6633.9 |
| baseline | FAIL | 648 | 53 | 5603.6 |
| prepend | FAIL | 827 | 53 | 6576.3 |

### append

```text
STATE_JSON={"answer":"45_CREDITS","decision_support_ids":["R2","R4"],"revision_event_id":"R6","preserved_constraint_ids":["R5"]}
```

Diagnostics: `{"extra_decision_support_ids":[],"extra_preserved_constraint_ids":[],"invalidated_evidence_ids_present":[],"missed_decision_support_ids":[],"missed_preserved_constraint_ids":[],"stable_value_preservation_status":"NOT_OBSERVABLE_IN_CURRENT_OUTPUT_SCHEMA","stale_answer_retained":true,"wrong_answer_value":true,"wrong_revision_event":false}`

### baseline

```text
STATE_JSON={"answer":"45_CREDITS","decision_support_ids":["R2","R4"],"revision_event_id":"R6","preserved_constraint_ids":["R5"]}
```

Diagnostics: `{"extra_decision_support_ids":[],"extra_preserved_constraint_ids":[],"invalidated_evidence_ids_present":[],"missed_decision_support_ids":[],"missed_preserved_constraint_ids":[],"stable_value_preservation_status":"NOT_OBSERVABLE_IN_CURRENT_OUTPUT_SCHEMA","stale_answer_retained":true,"wrong_answer_value":true,"wrong_revision_event":false}`

### prepend

```text
STATE_JSON={"answer":"45_CREDITS","decision_support_ids":["R2","R4"],"revision_event_id":"R6","preserved_constraint_ids":["R5"]}
```

Diagnostics: `{"extra_decision_support_ids":[],"extra_preserved_constraint_ids":[],"invalidated_evidence_ids_present":[],"missed_decision_support_ids":[],"missed_preserved_constraint_ids":[],"stable_value_preservation_status":"NOT_OBSERVABLE_IN_CURRENT_OUTPUT_SCHEMA","stale_answer_retained":true,"wrong_answer_value":true,"wrong_revision_event":false}`

Normalized comparisons:

- baseline → append: answers `['45_CREDITS', '45_CREDITS']`; semantic change `False`; strict repair `False`; strict regression `False`
- baseline → prepend: answers `['45_CREDITS', '45_CREDITS']`; semantic change `False`; strict repair `False`; strict regression `False`
- append → prepend: answers `['45_CREDITS', '45_CREDITS']`; semantic change `False`; strict repair `False`; strict regression `False`

## archive-tier-policy-revision

| Arm | Strict | Input tokens | Output tokens | Latency ms |
| --- | --- | ---: | ---: | ---: |
| append | PASS | 845 | 52 | 7309.6 |
| baseline | PASS | 665 | 52 | 5640.3 |
| prepend | FAIL | 845 | 49 | 6378.5 |

### append

```text
STATE_JSON={"answer":"COLD_TIER","decision_support_ids":["R2","R4"],"revision_event_id":"R6","preserved_constraint_ids":["R5"]}
```

Diagnostics: `{"extra_decision_support_ids":[],"extra_preserved_constraint_ids":[],"invalidated_evidence_ids_present":[],"missed_decision_support_ids":[],"missed_preserved_constraint_ids":[],"stable_value_preservation_status":"NOT_OBSERVABLE_IN_CURRENT_OUTPUT_SCHEMA","stale_answer_retained":false,"wrong_answer_value":false,"wrong_revision_event":false}`

### baseline

```text
STATE_JSON={"answer":"COLD_TIER","decision_support_ids":["R2","R4"],"revision_event_id":"R6","preserved_constraint_ids":["R5"]}
```

Diagnostics: `{"extra_decision_support_ids":[],"extra_preserved_constraint_ids":[],"invalidated_evidence_ids_present":[],"missed_decision_support_ids":[],"missed_preserved_constraint_ids":[],"stable_value_preservation_status":"NOT_OBSERVABLE_IN_CURRENT_OUTPUT_SCHEMA","stale_answer_retained":false,"wrong_answer_value":false,"wrong_revision_event":false}`

### prepend

```text
STATE_JSON={"answer":"COLD_TIER","decision_support_ids":["R4"],"revision_event_id":"R6","preserved_constraint_ids":["R5"]}
```

Diagnostics: `{"extra_decision_support_ids":[],"extra_preserved_constraint_ids":[],"invalidated_evidence_ids_present":[],"missed_decision_support_ids":["R2"],"missed_preserved_constraint_ids":[],"stable_value_preservation_status":"NOT_OBSERVABLE_IN_CURRENT_OUTPUT_SCHEMA","stale_answer_retained":false,"wrong_answer_value":false,"wrong_revision_event":false}`

Normalized comparisons:

- baseline → append: answers `['COLD_TIER', 'COLD_TIER']`; semantic change `False`; strict repair `False`; strict regression `False`
- baseline → prepend: answers `['COLD_TIER', 'COLD_TIER']`; semantic change `True`; strict repair `False`; strict regression `True`
- append → prepend: answers `['COLD_TIER', 'COLD_TIER']`; semantic change `True`; strict repair `False`; strict regression `True`

## permit-state-rule-revision

| Arm | Strict | Input tokens | Output tokens | Latency ms |
| --- | --- | ---: | ---: | ---: |
| append | FAIL | 822 | 47 | 7189.6 |
| baseline | PASS | 642 | 50 | 6552.0 |
| prepend | FAIL | 822 | 47 | 7301.0 |

### append

```text
STATE_JSON={"answer":"APPROVE","decision_support_ids":["R4"],"revision_event_id":"R6","preserved_constraint_ids":["R5"]}
```

Diagnostics: `{"extra_decision_support_ids":[],"extra_preserved_constraint_ids":[],"invalidated_evidence_ids_present":[],"missed_decision_support_ids":["R2"],"missed_preserved_constraint_ids":[],"stable_value_preservation_status":"NOT_OBSERVABLE_IN_CURRENT_OUTPUT_SCHEMA","stale_answer_retained":false,"wrong_answer_value":false,"wrong_revision_event":false}`

### baseline

```text
STATE_JSON={"answer":"APPROVE","decision_support_ids":["R2","R4"],"revision_event_id":"R6","preserved_constraint_ids":["R5"]}
```

Diagnostics: `{"extra_decision_support_ids":[],"extra_preserved_constraint_ids":[],"invalidated_evidence_ids_present":[],"missed_decision_support_ids":[],"missed_preserved_constraint_ids":[],"stable_value_preservation_status":"NOT_OBSERVABLE_IN_CURRENT_OUTPUT_SCHEMA","stale_answer_retained":false,"wrong_answer_value":false,"wrong_revision_event":false}`

### prepend

```text
STATE_JSON={"answer":"APPROVE","decision_support_ids":["R4"],"revision_event_id":"R6","preserved_constraint_ids":["R5"]}
```

Diagnostics: `{"extra_decision_support_ids":[],"extra_preserved_constraint_ids":[],"invalidated_evidence_ids_present":[],"missed_decision_support_ids":["R2"],"missed_preserved_constraint_ids":[],"stable_value_preservation_status":"NOT_OBSERVABLE_IN_CURRENT_OUTPUT_SCHEMA","stale_answer_retained":false,"wrong_answer_value":false,"wrong_revision_event":false}`

Normalized comparisons:

- baseline → append: answers `['APPROVE', 'APPROVE']`; semantic change `True`; strict repair `False`; strict regression `True`
- baseline → prepend: answers `['APPROVE', 'APPROVE']`; semantic change `True`; strict repair `False`; strict regression `True`
- append → prepend: answers `['APPROVE', 'APPROVE']`; semantic change `False`; strict repair `False`; strict regression `False`

## Boundary

```json
{
  "generalization": "CONTAMINATED_ENGINEERING_REGRESSION_ONLY",
  "effect_attribution": "NOT_ASSESSED",
  "gradient_allocation_superiority": "NOT_ASSESSED",
  "gradient_target_selection": "NOT_IDENTIFIABLE_WITH_MANDATORY_THREE_TARGETS",
  "stable_value_preservation": "NOT_OBSERVABLE_IN_CURRENT_OUTPUT_SCHEMA",
  "native_state_capture": "DISABLED",
  "gradient_through_model": false
}
```
