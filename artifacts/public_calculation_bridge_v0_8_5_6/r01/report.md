# Public calculation bridge v0.8.5.6

One known case; shared model-emitted calculation; no gradient-utility or causal superiority claim.

Run: `COMPLETE_BOUNDED_BLOCK`; calls: 8
Readiness: `{"calc_format":true,"calc_task":true,"state_format":true,"state_task":true}`
Bridge admission: `PARSED_SOURCE_SEMANTICS_NOT_A_GATE`

## Actual outputs and cost

| Call | Execution | Input tokens | Output tokens | Finish |
| --- | --- | ---: | ---: | --- |
| state_format | COMPLETE | 72 | 46 | stop |
| state_task | COMPLETE | 657 | 52 | stop |
| calc_format | COMPLETE | 66 | 41 | stop |
| calc_task | COMPLETE | 592 | 41 | stop |
| calculation | COMPLETE | 592 | 43 | stop |
| raw_only | COMPLETE | 648 | 53 | stop |
| operands_only | COMPLETE | 752 | 50 | stop |
| product_bridge | COMPLETE | 757 | 50 | stop |

### state_format

```text
STATE_JSON={"answer":"READY","decision_support_ids":["R1"],"preserved_constraint_ids":["R3"],"revision_event_id":"R2"}
```

### state_task

```text
STATE_JSON={"answer":"GATE_BLUE","decision_support_ids":["R2","R4"],"revision_event_id":"R6","preserved_constraint_ids":["R5"]}
```

### calc_format

```text
CALC_JSON={"base_count":2,"multiplier":4,"product":8,"answer":"8_CREDITS","rule_evidence_id":"R4"}
```

### calc_task

```text
CALC_JSON={"base_count":2,"multiplier":4,"product":8,"answer":"8_CREDITS","rule_evidence_id":"R4"}
```

### calculation

```text
CALC_JSON={"base_count":5,"multiplier":3,"product":15,"answer":"15_CREDITS","rule_evidence_id":"R4"}
```

### raw_only

```text
STATE_JSON={"answer":"45_CREDITS","decision_support_ids":["R2","R4"],"revision_event_id":"R6","preserved_constraint_ids":["R5"]}
```

### operands_only

```text
STATE_JSON={"answer":"45_CREDITS","decision_support_ids":["R4"],"revision_event_id":"R6","preserved_constraint_ids":["R5"]}
```

Forwarded public record: `{"base_count":5,"multiplier":3,"rule_evidence_id":"R4"}`

### product_bridge

```text
STATE_JSON={"answer":"15_CREDITS","decision_support_ids":["R4"],"revision_event_id":"R6","preserved_constraint_ids":["R5"]}
```

Forwarded public record: `{"base_count":5,"multiplier":3,"product":15,"rule_evidence_id":"R4"}`

## Assessment

```json
{
  "bridge_admission": "PARSED_SOURCE_SEMANTICS_NOT_A_GATE",
  "calculation_quality": {
    "checks": {
      "base_extraction_correct": true,
      "current_multiplier_selected": true,
      "current_rule_id_selected": true,
      "label_matches_current_rule": true,
      "label_matches_reported_product": true,
      "product_matches_current_rule": true,
      "product_matches_reported_operands": true
    },
    "component_pass": true,
    "error_code": null,
    "final_state_repair_assessed": false,
    "public_values": {
      "answer": "15_CREDITS",
      "base_count": 5,
      "multiplier": 3,
      "product": 15,
      "rule_evidence_id": "R4"
    },
    "status": "PARSED"
  },
  "comparisons": [
    {
      "answer_changed": false,
      "answer_transition": [
        "45_CREDITS",
        "45_CREDITS"
      ],
      "both_generations_complete": true,
      "both_parsed": true,
      "left_arm": "raw_only",
      "raw_text_changed": true,
      "right_arm": "operands_only",
      "semantic_state_changed": true,
      "strict_regression": false,
      "strict_repair": false,
      "unified_diff": [
        "--- raw_only",
        "+++ operands_only",
        "@@ -1 +1 @@",
        "-STATE_JSON={\"answer\":\"45_CREDITS\",\"decision_support_ids\":[\"R2\",\"R4\"],\"revision_event_id\":\"R6\",\"preserved_constraint_ids\":[\"R5\"]}",
        "+STATE_JSON={\"answer\":\"45_CREDITS\",\"decision_support_ids\":[\"R4\"],\"revision_event_id\":\"R6\",\"preserved_constraint_ids\":[\"R5\"]}"
      ]
    },
    {
      "answer_changed": true,
      "answer_transition": [
        "45_CREDITS",
        "15_CREDITS"
      ],
      "both_generations_complete": true,
      "both_parsed": true,
      "left_arm": "raw_only",
      "raw_text_changed": true,
      "right_arm": "product_bridge",
      "semantic_state_changed": true,
      "strict_regression": false,
      "strict_repair": false,
      "unified_diff": [
        "--- raw_only",
        "+++ product_bridge",
        "@@ -1 +1 @@",
        "-STATE_JSON={\"answer\":\"45_CREDITS\",\"decision_support_ids\":[\"R2\",\"R4\"],\"revision_event_id\":\"R6\",\"preserved_constraint_ids\":[\"R5\"]}",
        "+STATE_JSON={\"answer\":\"15_CREDITS\",\"decision_support_ids\":[\"R4\"],\"revision_event_id\":\"R6\",\"preserved_constraint_ids\":[\"R5\"]}"
      ]
    },
    {
      "answer_changed": true,
      "answer_transition": [
        "45_CREDITS",
        "15_CREDITS"
      ],
      "both_generations_complete": true,
      "both_parsed": true,
      "left_arm": "operands_only",
      "raw_text_changed": true,
      "right_arm": "product_bridge",
      "semantic_state_changed": true,
      "strict_regression": false,
      "strict_repair": false,
      "unified_diff": [
        "--- operands_only",
        "+++ product_bridge",
        "@@ -1 +1 @@",
        "-STATE_JSON={\"answer\":\"45_CREDITS\",\"decision_support_ids\":[\"R4\"],\"revision_event_id\":\"R6\",\"preserved_constraint_ids\":[\"R5\"]}",
        "+STATE_JSON={\"answer\":\"15_CREDITS\",\"decision_support_ids\":[\"R4\"],\"revision_event_id\":\"R6\",\"preserved_constraint_ids\":[\"R5\"]}"
      ]
    }
  ],
  "diagnostic_cause": "NOT_IDENTIFIED_SINGLE_SERIAL_BLOCK",
  "final_probe_denominator": 3,
  "finals": {
    "operands_only": {
      "edit_diagnostics": {
        "before_provenance": "CALLER_PRIOR_STATE_ROLE_PARTITION_NOT_A_NEW_MODEL_OUTPUT",
        "counts": {
          "miss": 1,
          "over_edit": 1,
          "wrong_value": 0
        },
        "errors": {
          "miss": [
            "/answer"
          ],
          "over_edit": [
            "/decision_support_ids/R2"
          ],
          "wrong_value": []
        },
        "observed_edit_paths": [
          "/decision_support_ids/R2",
          "/decision_support_ids/R3",
          "/decision_support_ids/R4"
        ],
        "required_edit_paths": [
          "/answer",
          "/decision_support_ids/R3",
          "/decision_support_ids/R4"
        ],
        "status": "ASSESSED",
        "strict_contract_remains_primary": true,
        "tracked_paths_complete": false,
        "untracked": [
          "revision_event_id_before_unknown",
          "stable_fact_values_not_emitted"
        ]
      },
      "execution_status": "COMPLETE",
      "quality": {
        "diagnostics": {
          "extra_decision_support_ids": [],
          "extra_preserved_constraint_ids": [],
          "invalidated_evidence_ids_present": [],
          "missed_decision_support_ids": [
            "R2"
          ],
          "missed_preserved_constraint_ids": [],
          "stable_value_preservation_status": "NOT_OBSERVABLE_IN_CURRENT_OUTPUT_SCHEMA",
          "stale_answer_retained": true,
          "wrong_answer_value": true,
          "wrong_revision_event": false
        },
        "parse_error": null,
        "public_state": {
          "answer": "45_CREDITS",
          "decision_support_ids": [
            "R4"
          ],
          "fingerprint_sha256": "3beb67079765379f4b662bb6d01b094569e86630c64524138a8e6b4060e8a991",
          "preserved_constraint_ids": [
            "R5"
          ],
          "revision_event_id": "R6",
          "schema_version": "ebrt-public-role-isolation-v0.8.5.2"
        },
        "strict_grade": {
          "checks": {
            "channels_pairwise_disjoint": true,
            "decision_support_exact": false,
            "expected_answer": false,
            "forbidden_evidence_absent": true,
            "preserved_constraints_exact": true,
            "revision_event_exact": true,
            "schema_parsed": true
          },
          "contract_fingerprint_sha256": "5215d0382411912ce658e73cdc2166c86b6e6939c5b76c98b39ae110e60084a8",
          "expected": {
            "answer": "15_CREDITS",
            "decision_support_ids": [
              "R2",
              "R4"
            ],
            "preserved_constraint_ids": [
              "R5"
            ],
            "revision_event_id": "R6"
          },
          "fingerprint_sha256": "eed3f4b2ed03bc68bf591b8ff1016b622ac1d20276ae504b814e8b92a956dc94",
          "status": "FAIL"
        }
      },
      "raw_text": "STATE_JSON={\"answer\":\"45_CREDITS\",\"decision_support_ids\":[\"R4\"],\"revision_event_id\":\"R6\",\"preserved_constraint_ids\":[\"R5\"]}"
    },
    "product_bridge": {
      "edit_diagnostics": {
        "before_provenance": "CALLER_PRIOR_STATE_ROLE_PARTITION_NOT_A_NEW_MODEL_OUTPUT",
        "counts": {
          "miss": 0,
          "over_edit": 1,
          "wrong_value": 0
        },
        "errors": {
          "miss": [],
          "over_edit": [
            "/decision_support_ids/R2"
          ],
          "wrong_value": []
        },
        "observed_edit_paths": [
          "/answer",
          "/decision_support_ids/R2",
          "/decision_support_ids/R3",
          "/decision_support_ids/R4"
        ],
        "required_edit_paths": [
          "/answer",
          "/decision_support_ids/R3",
          "/decision_support_ids/R4"
        ],
        "status": "ASSESSED",
        "strict_contract_remains_primary": true,
        "tracked_paths_complete": false,
        "untracked": [
          "revision_event_id_before_unknown",
          "stable_fact_values_not_emitted"
        ]
      },
      "execution_status": "COMPLETE",
      "quality": {
        "diagnostics": {
          "extra_decision_support_ids": [],
          "extra_preserved_constraint_ids": [],
          "invalidated_evidence_ids_present": [],
          "missed_decision_support_ids": [
            "R2"
          ],
          "missed_preserved_constraint_ids": [],
          "stable_value_preservation_status": "NOT_OBSERVABLE_IN_CURRENT_OUTPUT_SCHEMA",
          "stale_answer_retained": false,
          "wrong_answer_value": false,
          "wrong_revision_event": false
        },
        "parse_error": null,
        "public_state": {
          "answer": "15_CREDITS",
          "decision_support_ids": [
            "R4"
          ],
          "fingerprint_sha256": "a372e0961b95ce7a9356fa97701a56abbb5f0a4a11eb67bb2e1e3cb0c71f07f5",
          "preserved_constraint_ids": [
            "R5"
          ],
          "revision_event_id": "R6",
          "schema_version": "ebrt-public-role-isolation-v0.8.5.2"
        },
        "strict_grade": {
          "checks": {
            "channels_pairwise_disjoint": true,
            "decision_support_exact": false,
            "expected_answer": true,
            "forbidden_evidence_absent": true,
            "preserved_constraints_exact": true,
            "revision_event_exact": true,
            "schema_parsed": true
          },
          "contract_fingerprint_sha256": "5215d0382411912ce658e73cdc2166c86b6e6939c5b76c98b39ae110e60084a8",
          "expected": {
            "answer": "15_CREDITS",
            "decision_support_ids": [
              "R2",
              "R4"
            ],
            "preserved_constraint_ids": [
              "R5"
            ],
            "revision_event_id": "R6"
          },
          "fingerprint_sha256": "412adf0bfbdac461b09e4dd445e68d142a95faeef707bf6c2cae9a1751c6b490",
          "status": "FAIL"
        }
      },
      "raw_text": "STATE_JSON={\"answer\":\"15_CREDITS\",\"decision_support_ids\":[\"R4\"],\"revision_event_id\":\"R6\",\"preserved_constraint_ids\":[\"R5\"]}"
    },
    "raw_only": {
      "edit_diagnostics": {
        "before_provenance": "CALLER_PRIOR_STATE_ROLE_PARTITION_NOT_A_NEW_MODEL_OUTPUT",
        "counts": {
          "miss": 1,
          "over_edit": 0,
          "wrong_value": 0
        },
        "errors": {
          "miss": [
            "/answer"
          ],
          "over_edit": [],
          "wrong_value": []
        },
        "observed_edit_paths": [
          "/decision_support_ids/R3",
          "/decision_support_ids/R4"
        ],
        "required_edit_paths": [
          "/answer",
          "/decision_support_ids/R3",
          "/decision_support_ids/R4"
        ],
        "status": "ASSESSED",
        "strict_contract_remains_primary": true,
        "tracked_paths_complete": false,
        "untracked": [
          "revision_event_id_before_unknown",
          "stable_fact_values_not_emitted"
        ]
      },
      "execution_status": "COMPLETE",
      "quality": {
        "diagnostics": {
          "extra_decision_support_ids": [],
          "extra_preserved_constraint_ids": [],
          "invalidated_evidence_ids_present": [],
          "missed_decision_support_ids": [],
          "missed_preserved_constraint_ids": [],
          "stable_value_preservation_status": "NOT_OBSERVABLE_IN_CURRENT_OUTPUT_SCHEMA",
          "stale_answer_retained": true,
          "wrong_answer_value": true,
          "wrong_revision_event": false
        },
        "parse_error": null,
        "public_state": {
          "answer": "45_CREDITS",
          "decision_support_ids": [
            "R2",
            "R4"
          ],
          "fingerprint_sha256": "10c6022067b9f360f69d5ea9caf1389036eca895577070e3530d22417acd5987",
          "preserved_constraint_ids": [
            "R5"
          ],
          "revision_event_id": "R6",
          "schema_version": "ebrt-public-role-isolation-v0.8.5.2"
        },
        "strict_grade": {
          "checks": {
            "channels_pairwise_disjoint": true,
            "decision_support_exact": true,
            "expected_answer": false,
            "forbidden_evidence_absent": true,
            "preserved_constraints_exact": true,
            "revision_event_exact": true,
            "schema_parsed": true
          },
          "contract_fingerprint_sha256": "5215d0382411912ce658e73cdc2166c86b6e6939c5b76c98b39ae110e60084a8",
          "expected": {
            "answer": "15_CREDITS",
            "decision_support_ids": [
              "R2",
              "R4"
            ],
            "preserved_constraint_ids": [
              "R5"
            ],
            "revision_event_id": "R6"
          },
          "fingerprint_sha256": "18e61f92355c1c5e2e7e7cbea0f0e935e8533b9a82043ee72c58cc372551d964",
          "status": "FAIL"
        }
      },
      "raw_text": "STATE_JSON={\"answer\":\"45_CREDITS\",\"decision_support_ids\":[\"R2\",\"R4\"],\"revision_event_id\":\"R6\",\"preserved_constraint_ids\":[\"R5\"]}"
    }
  },
  "logical_calls": 8,
  "readiness": {
    "all_passed": true,
    "calc_task_quality": {
      "checks": {
        "base_extraction_correct": true,
        "current_multiplier_selected": true,
        "current_rule_id_selected": true,
        "label_matches_current_rule": true,
        "label_matches_reported_product": true,
        "product_matches_current_rule": true,
        "product_matches_reported_operands": true
      },
      "component_pass": true,
      "error_code": null,
      "final_state_repair_assessed": false,
      "public_values": {
        "answer": "8_CREDITS",
        "base_count": 2,
        "multiplier": 4,
        "product": 8,
        "rule_evidence_id": "R4"
      },
      "status": "PARSED"
    },
    "checks": {
      "calc_format": true,
      "calc_task": true,
      "state_format": true,
      "state_task": true
    },
    "state_task_quality": {
      "diagnostics": {
        "extra_decision_support_ids": [],
        "extra_preserved_constraint_ids": [],
        "invalidated_evidence_ids_present": [],
        "missed_decision_support_ids": [],
        "missed_preserved_constraint_ids": [],
        "stable_value_preservation_status": "NOT_OBSERVABLE_IN_CURRENT_OUTPUT_SCHEMA",
        "stale_answer_retained": false,
        "wrong_answer_value": false,
        "wrong_revision_event": false
      },
      "parse_error": null,
      "public_state": {
        "answer": "GATE_BLUE",
        "decision_support_ids": [
          "R2",
          "R4"
        ],
        "fingerprint_sha256": "d7b51aec41ed5dd8df370e273eac04999cec63187e45c21232a6574eaddd3e80",
        "preserved_constraint_ids": [
          "R5"
        ],
        "revision_event_id": "R6",
        "schema_version": "ebrt-public-role-isolation-v0.8.5.2"
      },
      "strict_grade": {
        "checks": {
          "channels_pairwise_disjoint": true,
          "decision_support_exact": true,
          "expected_answer": true,
          "forbidden_evidence_absent": true,
          "preserved_constraints_exact": true,
          "revision_event_exact": true,
          "schema_parsed": true
        },
        "contract_fingerprint_sha256": "fd1727218dcee14566bf489f7d61d9a2a2dcb7d4453f52e3a486ceec2b4ec5ce",
        "expected": {
          "answer": "GATE_BLUE",
          "decision_support_ids": [
            "R2",
            "R4"
          ],
          "preserved_constraint_ids": [
            "R5"
          ],
          "revision_event_id": "R6"
        },
        "fingerprint_sha256": "0d1932dfd5e0eea337dbc0f9f69518649a773edc48aae0550172b1e68c9bb91b",
        "status": "PASS"
      }
    }
  },
  "run_status": "COMPLETE_BOUNDED_BLOCK",
  "strict_final_passes": {
    "operands_only": false,
    "product_bridge": false,
    "raw_only": false
  },
  "total_input_tokens": 4136,
  "total_output_tokens_including_terminal": 376
}
```

## Boundary

```json
{
  "scope": "ONE_KNOWN_CASE_ENGINEERING_DIAGNOSTIC_NOT_BENCHMARK",
  "gradient_utility": "NOT_ASSESSED_NO_EBRT_GRADIENT_INTERVENTION",
  "effect_attribution": "NOT_ASSESSED_SINGLE_FIXED_SERIAL_BLOCK",
  "private_reasoning": "NOT_OBSERVED_PUBLIC_OUTPUT_ONLY",
  "bridge_source": "ACTUAL_MODEL_EMITTED_CALCULATION_NOT_GOLD",
  "bridge_gate": "STRUCTURAL_PARSING_ONLY_SEMANTIC_FAILURES_RETAINED",
  "bridge_trust": "UNVERIFIED_MAY_CONTAIN_WRONG_VALUES",
  "answer_label_forwarded": false,
  "product_recomputed_or_corrected": false,
  "parser_relaxed": false,
  "stable_values": "NOT_OBSERVABLE_IN_LEGACY_FINAL_STATE",
  "compute_matching": "NOT_CLAIMED_SHARED_CALCULATION_AND_DIFFERENT_PROMPTS"
}
```
