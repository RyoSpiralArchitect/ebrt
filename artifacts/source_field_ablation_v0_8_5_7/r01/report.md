# Source-field ablation v0.8.5.7

Recorded calculation replay on one known case; no fresh calculation or gradient-utility claim.

Run: `COMPLETE_SIX_CALL_BLOCK`; calls: 6; strict final: 0/4

| Call | Execution | Input tokens | Output tokens | Finish |
| --- | --- | ---: | ---: | --- |
| state_format | COMPLETE | 72 | 46 | stop |
| state_task | COMPLETE | 657 | 52 | stop |
| pair1_with_source | COMPLETE | 757 | 50 | stop |
| pair1_without_source | COMPLETE | 747 | 56 | stop |
| pair2_without_source | COMPLETE | 747 | 56 | stop |
| pair2_with_source | COMPLETE | 757 | 50 | stop |

## state_format

```text
STATE_JSON={"answer":"READY","decision_support_ids":["R1"],"preserved_constraint_ids":["R3"],"revision_event_id":"R2"}
```

## state_task

```text
STATE_JSON={"answer":"GATE_BLUE","decision_support_ids":["R2","R4"],"revision_event_id":"R6","preserved_constraint_ids":["R5"]}
```

## pair1_with_source

```text
STATE_JSON={"answer":"15_CREDITS","decision_support_ids":["R4"],"revision_event_id":"R6","preserved_constraint_ids":["R5"]}
```

## pair1_without_source

```text
STATE_JSON={"answer":"15_CREDITS","decision_support_ids":["R2","R4","R6"],"revision_event_id":"R6","preserved_constraint_ids":["R5"]}
```

## pair2_without_source

```text
STATE_JSON={"answer":"15_CREDITS","decision_support_ids":["R2","R4","R6"],"revision_event_id":"R6","preserved_constraint_ids":["R5"]}
```

## pair2_with_source

```text
STATE_JSON={"answer":"15_CREDITS","decision_support_ids":["R4"],"revision_event_id":"R6","preserved_constraint_ids":["R5"]}
```

## Assessment

```json
{
  "diagnostic_cause": "NOT_IDENTIFIED_ONE_KNOWN_CASE_DESCRIPTIVE_REPEATS",
  "final_probe_denominator": 4,
  "finals": {
    "pair1_with_source": {
      "arm": "with_source",
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
      "r2_present": false,
      "raw_text": "STATE_JSON={\"answer\":\"15_CREDITS\",\"decision_support_ids\":[\"R4\"],\"revision_event_id\":\"R6\",\"preserved_constraint_ids\":[\"R5\"]}"
    },
    "pair1_without_source": {
      "arm": "without_source",
      "edit_diagnostics": {
        "counts": null,
        "status": "NOT_ASSESSED_INVALID_PUBLIC_STATE"
      },
      "execution_status": "COMPLETE",
      "quality": {
        "diagnostics": null,
        "parse_error": "V0852_STATE_CHANNELS_OVERLAP",
        "public_state": null,
        "strict_grade": {
          "checks": {
            "channels_pairwise_disjoint": false,
            "decision_support_exact": false,
            "expected_answer": false,
            "forbidden_evidence_absent": false,
            "preserved_constraints_exact": false,
            "revision_event_exact": false,
            "schema_parsed": false
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
          "fingerprint_sha256": "4c3a9ab1969c7e8f6a239b254d591418a6f9e88754bdb27d27568ce97108e6e4",
          "status": "FAIL"
        }
      },
      "r2_present": null,
      "raw_text": "STATE_JSON={\"answer\":\"15_CREDITS\",\"decision_support_ids\":[\"R2\",\"R4\",\"R6\"],\"revision_event_id\":\"R6\",\"preserved_constraint_ids\":[\"R5\"]}"
    },
    "pair2_with_source": {
      "arm": "with_source",
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
      "r2_present": false,
      "raw_text": "STATE_JSON={\"answer\":\"15_CREDITS\",\"decision_support_ids\":[\"R4\"],\"revision_event_id\":\"R6\",\"preserved_constraint_ids\":[\"R5\"]}"
    },
    "pair2_without_source": {
      "arm": "without_source",
      "edit_diagnostics": {
        "counts": null,
        "status": "NOT_ASSESSED_INVALID_PUBLIC_STATE"
      },
      "execution_status": "COMPLETE",
      "quality": {
        "diagnostics": null,
        "parse_error": "V0852_STATE_CHANNELS_OVERLAP",
        "public_state": null,
        "strict_grade": {
          "checks": {
            "channels_pairwise_disjoint": false,
            "decision_support_exact": false,
            "expected_answer": false,
            "forbidden_evidence_absent": false,
            "preserved_constraints_exact": false,
            "revision_event_exact": false,
            "schema_parsed": false
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
          "fingerprint_sha256": "4c3a9ab1969c7e8f6a239b254d591418a6f9e88754bdb27d27568ce97108e6e4",
          "status": "FAIL"
        }
      },
      "r2_present": null,
      "raw_text": "STATE_JSON={\"answer\":\"15_CREDITS\",\"decision_support_ids\":[\"R2\",\"R4\",\"R6\"],\"revision_event_id\":\"R6\",\"preserved_constraint_ids\":[\"R5\"]}"
    }
  },
  "logical_calls": 6,
  "new_calculation_calls": 0,
  "pairs_with_to_without_source": [
    {
      "answer_changed": null,
      "answer_transition": [
        "15_CREDITS",
        null
      ],
      "both_generations_complete": true,
      "both_parsed": false,
      "execution_order": [
        "pair1_with_source",
        "pair1_without_source"
      ],
      "left_arm": "pair1_with_source",
      "r2_presence_transition": [
        false,
        null
      ],
      "raw_text_changed": true,
      "right_arm": "pair1_without_source",
      "semantic_state_changed": null,
      "strict_regression": false,
      "strict_repair": false,
      "unified_diff": [
        "--- pair1_with_source",
        "+++ pair1_without_source",
        "@@ -1 +1 @@",
        "-STATE_JSON={\"answer\":\"15_CREDITS\",\"decision_support_ids\":[\"R4\"],\"revision_event_id\":\"R6\",\"preserved_constraint_ids\":[\"R5\"]}",
        "+STATE_JSON={\"answer\":\"15_CREDITS\",\"decision_support_ids\":[\"R2\",\"R4\",\"R6\"],\"revision_event_id\":\"R6\",\"preserved_constraint_ids\":[\"R5\"]}"
      ]
    },
    {
      "answer_changed": null,
      "answer_transition": [
        "15_CREDITS",
        null
      ],
      "both_generations_complete": true,
      "both_parsed": false,
      "execution_order": [
        "pair2_without_source",
        "pair2_with_source"
      ],
      "left_arm": "pair2_with_source",
      "r2_presence_transition": [
        false,
        null
      ],
      "raw_text_changed": true,
      "right_arm": "pair2_without_source",
      "semantic_state_changed": null,
      "strict_regression": false,
      "strict_repair": false,
      "unified_diff": [
        "--- pair2_with_source",
        "+++ pair2_without_source",
        "@@ -1 +1 @@",
        "-STATE_JSON={\"answer\":\"15_CREDITS\",\"decision_support_ids\":[\"R4\"],\"revision_event_id\":\"R6\",\"preserved_constraint_ids\":[\"R5\"]}",
        "+STATE_JSON={\"answer\":\"15_CREDITS\",\"decision_support_ids\":[\"R2\",\"R4\",\"R6\"],\"revision_event_id\":\"R6\",\"preserved_constraint_ids\":[\"R5\"]}"
      ]
    }
  ],
  "readiness": {
    "all_passed": true,
    "checks": {
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
  "recorded_source_fingerprint_sha256": "0a2ac505635f230184a0d22e430a540e47a34c7867d19416d9ec833d7ee9da25",
  "run_status": "COMPLETE_SIX_CALL_BLOCK",
  "strict_final_passes": 0,
  "total_input_tokens": 3737,
  "total_output_tokens_including_terminal": 310,
  "within_arm_repeats": {
    "with_source": {
      "generated": 2,
      "normalized_states_identical": true,
      "parsed": 2,
      "planned": 2,
      "raw_outputs_identical": true,
      "strict_passes": 0
    },
    "without_source": {
      "generated": 2,
      "normalized_states_identical": null,
      "parsed": 0,
      "planned": 2,
      "raw_outputs_identical": true,
      "strict_passes": 0
    }
  }
}
```

## Boundary

```json
{
  "scope": "ONE_KNOWN_CASE_CONTAMINATED_RECORDED_CALCULATION_REPLAY",
  "calculation": "PREVIOUS_ACTUAL_TERMINAL_NOT_REGENERATED",
  "changed_surface": "ONLY_SUPPLEMENTARY_RULE_EVIDENCE_ID_PRESENCE",
  "raw_evidence": "COMPLETE_CHRONOLOGICAL_BYTES_UNCHANGED",
  "answer_label_forwarded": false,
  "product_recomputed_or_corrected": false,
  "gold_support_inserted": false,
  "parser_or_grader_relaxed": false,
  "gradient_utility": "NOT_ASSESSED_NO_GRADIENT_INTERVENTION",
  "causal_superiority": "NOT_ESTABLISHED_ONE_CASE_AB_BA_DESCRIPTIVE_REPEATS",
  "private_reasoning": "NOT_OBSERVED_PUBLIC_OUTPUT_ONLY",
  "stable_values": "NOT_OBSERVABLE_IN_LEGACY_FINAL_STATE",
  "compute_matching": "SHARED_CEILING_NOT_EQUAL_INPUT_TOKENS_OR_TOTAL_COMPUTE"
}
```
