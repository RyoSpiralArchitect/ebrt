# Numeric revision diagnostic v0.8.5.5

One known case; component probes are assisted diagnostics, not additional repair successes.

Run: `COMPLETE_BOUNDED_DIAGNOSTIC`; calls: 8

## state_probes

### final_choice_order

```text
STATE_JSON={"answer":"45_CREDITS","decision_support_ids":["R2","R4"],"revision_event_id":"R6","preserved_constraint_ids":["R5"]}
```

Assessment: `{"execution_status":"COMPLETE","quality":{"diagnostics":{"extra_decision_support_ids":[],"extra_preserved_constraint_ids":[],"invalidated_evidence_ids_present":[],"missed_decision_support_ids":[],"missed_preserved_constraint_ids":[],"stable_value_preservation_status":"NOT_OBSERVABLE_IN_CURRENT_OUTPUT_SCHEMA","stale_answer_retained":true,"wrong_answer_value":true,"wrong_revision_event":false},"parse_error":null,"public_state":{"answer":"45_CREDITS","decision_support_ids":["R2","R4"],"fingerprint_sha256":"10c6022067b9f360f69d5ea9caf1389036eca895577070e3530d22417acd5987","preserved_constraint_ids":["R5"],"revision_event_id":"R6","schema_version":"ebrt-public-role-isolation-v0.8.5.2"},"strict_grade":{"checks":{"channels_pairwise_disjoint":true,"decision_support_exact":true,"expected_answer":false,"forbidden_evidence_absent":true,"preserved_constraints_exact":true,"revision_event_exact":true,"schema_parsed":true},"contract_fingerprint_sha256":"5215d0382411912ce658e73cdc2166c86b6e6939c5b76c98b39ae110e60084a8","expected":{"answer":"15_CREDITS","decision_support_ids":["R2","R4"],"preserved_constraint_ids":["R5"],"revision_event_id":"R6"},"fingerprint_sha256":"18e61f92355c1c5e2e7e7cbea0f0e935e8533b9a82043ee72c58cc372551d964","status":"FAIL"}},"raw_text":"STATE_JSON={\"answer\":\"45_CREDITS\",\"decision_support_ids\":[\"R2\",\"R4\"],\"revision_event_id\":\"R6\",\"preserved_constraint_ids\":[\"R5\"]}","secondary_edit_diagnostics":{"before_provenance":"CALLER_PRIOR_STATE_ROLE_PARTITION_NOT_A_NEW_MODEL_OUTPUT","counts":{"miss":1,"over_edit":0,"wrong_value":0},"errors":{"miss":["/answer"],"over_edit":[],"wrong_value":[]},"observed_edit_paths":["/decision_support_ids/R3","/decision_support_ids/R4"],"required_edit_paths":["/answer","/decision_support_ids/R3","/decision_support_ids/R4"],"status":"ASSESSED","strict_contract_remains_primary":true,"tracked_paths_complete":false,"untracked":["revision_event_id_before_unknown","stable_fact_values_not_emitted"]}}`

### final_explicit_operands

```text
STATE_JSON={"answer":"45_CREDITS","decision_support_ids":["R2","R4"],"revision_event_id":"R6","preserved_constraint_ids":["R5"]}
```

Assessment: `{"execution_status":"COMPLETE","quality":{"diagnostics":{"extra_decision_support_ids":[],"extra_preserved_constraint_ids":[],"invalidated_evidence_ids_present":[],"missed_decision_support_ids":[],"missed_preserved_constraint_ids":[],"stable_value_preservation_status":"NOT_OBSERVABLE_IN_CURRENT_OUTPUT_SCHEMA","stale_answer_retained":true,"wrong_answer_value":true,"wrong_revision_event":false},"parse_error":null,"public_state":{"answer":"45_CREDITS","decision_support_ids":["R2","R4"],"fingerprint_sha256":"10c6022067b9f360f69d5ea9caf1389036eca895577070e3530d22417acd5987","preserved_constraint_ids":["R5"],"revision_event_id":"R6","schema_version":"ebrt-public-role-isolation-v0.8.5.2"},"strict_grade":{"checks":{"channels_pairwise_disjoint":true,"decision_support_exact":true,"expected_answer":false,"forbidden_evidence_absent":true,"preserved_constraints_exact":true,"revision_event_exact":true,"schema_parsed":true},"contract_fingerprint_sha256":"5215d0382411912ce658e73cdc2166c86b6e6939c5b76c98b39ae110e60084a8","expected":{"answer":"15_CREDITS","decision_support_ids":["R2","R4"],"preserved_constraint_ids":["R5"],"revision_event_id":"R6"},"fingerprint_sha256":"18e61f92355c1c5e2e7e7cbea0f0e935e8533b9a82043ee72c58cc372551d964","status":"FAIL"}},"raw_text":"STATE_JSON={\"answer\":\"45_CREDITS\",\"decision_support_ids\":[\"R2\",\"R4\"],\"revision_event_id\":\"R6\",\"preserved_constraint_ids\":[\"R5\"]}","secondary_edit_diagnostics":{"before_provenance":"CALLER_PRIOR_STATE_ROLE_PARTITION_NOT_A_NEW_MODEL_OUTPUT","counts":{"miss":1,"over_edit":0,"wrong_value":0},"errors":{"miss":["/answer"],"over_edit":[],"wrong_value":[]},"observed_edit_paths":["/decision_support_ids/R3","/decision_support_ids/R4"],"required_edit_paths":["/answer","/decision_support_ids/R3","/decision_support_ids/R4"],"status":"ASSESSED","strict_contract_remains_primary":true,"tracked_paths_complete":false,"untracked":["revision_event_id_before_unknown","stable_fact_values_not_emitted"]}}`

### final_reference

```text
STATE_JSON={"answer":"45_CREDITS","decision_support_ids":["R2","R4"],"revision_event_id":"R6","preserved_constraint_ids":["R5"]}
```

Assessment: `{"execution_status":"COMPLETE","quality":{"diagnostics":{"extra_decision_support_ids":[],"extra_preserved_constraint_ids":[],"invalidated_evidence_ids_present":[],"missed_decision_support_ids":[],"missed_preserved_constraint_ids":[],"stable_value_preservation_status":"NOT_OBSERVABLE_IN_CURRENT_OUTPUT_SCHEMA","stale_answer_retained":true,"wrong_answer_value":true,"wrong_revision_event":false},"parse_error":null,"public_state":{"answer":"45_CREDITS","decision_support_ids":["R2","R4"],"fingerprint_sha256":"10c6022067b9f360f69d5ea9caf1389036eca895577070e3530d22417acd5987","preserved_constraint_ids":["R5"],"revision_event_id":"R6","schema_version":"ebrt-public-role-isolation-v0.8.5.2"},"strict_grade":{"checks":{"channels_pairwise_disjoint":true,"decision_support_exact":true,"expected_answer":false,"forbidden_evidence_absent":true,"preserved_constraints_exact":true,"revision_event_exact":true,"schema_parsed":true},"contract_fingerprint_sha256":"5215d0382411912ce658e73cdc2166c86b6e6939c5b76c98b39ae110e60084a8","expected":{"answer":"15_CREDITS","decision_support_ids":["R2","R4"],"preserved_constraint_ids":["R5"],"revision_event_id":"R6"},"fingerprint_sha256":"18e61f92355c1c5e2e7e7cbea0f0e935e8533b9a82043ee72c58cc372551d964","status":"FAIL"}},"raw_text":"STATE_JSON={\"answer\":\"45_CREDITS\",\"decision_support_ids\":[\"R2\",\"R4\"],\"revision_event_id\":\"R6\",\"preserved_constraint_ids\":[\"R5\"]}","secondary_edit_diagnostics":{"before_provenance":"CALLER_PRIOR_STATE_ROLE_PARTITION_NOT_A_NEW_MODEL_OUTPUT","counts":{"miss":1,"over_edit":0,"wrong_value":0},"errors":{"miss":["/answer"],"over_edit":[],"wrong_value":[]},"observed_edit_paths":["/decision_support_ids/R3","/decision_support_ids/R4"],"required_edit_paths":["/answer","/decision_support_ids/R3","/decision_support_ids/R4"],"status":"ASSESSED","strict_contract_remains_primary":true,"tracked_paths_complete":false,"untracked":["revision_event_id_before_unknown","stable_fact_values_not_emitted"]}}`

## component_probes

### inspect_computation

```text
{
  "base_count": 5,
  "multiplier": 3,
  "product": 15,
  "answer": "15_CREDITS",
  "rule_evidence_id": "R6"
}
```

Assessment: `{"assistance":"EXPLICIT_PUBLIC_INTERMEDIATE_OUTPUT_SCHEMA","execution_status":"COMPLETE","quality":{"checks":null,"error_code":"V0855_COMPONENT_LINE_INVALID","public_values":null,"status":"FORMAT_ERROR"},"raw_text":"{\n  \"base_count\": 5,\n  \"multiplier\": 3,\n  \"product\": 15,\n  \"answer\": \"15_CREDITS\",\n  \"rule_evidence_id\": \"R6\"\n}"}`

### isolated_arithmetic

```text
{"result":15}
```

Assessment: `{"assistance":"PUBLIC_R2_R4_OPERANDS_GIVEN_NO_RULE_SELECTION_OR_LABEL","execution_status":"COMPLETE","quality":{"checks":null,"error_code":"V0855_COMPONENT_LINE_INVALID","public_values":null,"status":"FORMAT_ERROR"},"raw_text":"{\"result\":15}"}`

### isolated_label

```text
LABEL_JSON={"answer":"15_CREDITS"}
```

Assessment: `{"assistance":"CORRECT_NUMERIC_VALUE_GIVEN_FROM_PUBLIC_OPERANDS_NOT_A_REPAIR_SUCCESS","execution_status":"COMPLETE","quality":{"checks":{"given_numeric_value_label_correct":true},"component_pass":true,"error_code":null,"final_state_repair_assessed":false,"public_values":{"answer":"15_CREDITS"},"status":"PARSED"},"raw_text":"LABEL_JSON={\"answer\":\"15_CREDITS\"}"}`

## Boundary

```json
{
  "scope": "KNOWN_SINGLE_CASE_COMPONENT_DIAGNOSIS_NOT_QUALITY_BENCHMARK",
  "effect_attribution": "NOT_ASSESSED",
  "gradient_utility": "NOT_ASSESSED_NO_CONTROL_INTERVENTION",
  "internal_reasoning": "NOT_OBSERVED_PUBLIC_DIAGNOSTIC_OUTPUT_ONLY",
  "stable_fact_values": "NOT_OBSERVABLE_IN_LEGACY_STATE_SCHEMA",
  "component_assistance": "EXPLICIT_OPERANDS_AND_GIVEN_VALUE_ARE_DIAGNOSTIC_SCAFFOLDS",
  "repair_metric": "TRACKED_PUBLIC_PATH_ADAPTATION_NOT_REVPROPBENCH_REPLICATION",
  "optional_edits": "NONE",
  "automatic_output_repair": false,
  "gradient_through_model": false
}
```
