export type EvidenceRecord = {
  evidence_id: string;
  ordinal: number;
  kind: "initial" | "late" | string;
  text: string;
  listed_invalidated_by_envelope: boolean;
};

export type DecisionFact = {
  slot: string;
  value: string;
  evidence_ids: string[];
};

export type PublicCard = {
  checkpoint_id: string;
  claim: string;
  topic: string;
  stance: number;
  confidence: number;
  evidence_ids: string[];
  current_answer: string;
  revision_cue: number;
  decision_facts: DecisionFact[];
  invalidated_evidence_ids: string[];
};

export type Usage = {
  input_tokens?: number | null;
  output_tokens?: number | null;
  reasoning_tokens?: number | null;
  total_tokens?: number | null;
  cached_input_tokens?: number | null;
};

export type TimelineEntry = {
  sequence_offset: number;
  phase: string;
  current_evidence_id?: string | null;
  presented_raw_evidence_ids?: string[];
  presented_raw_evidence_ids_source?: "stored_call_record" | "derived_from_locked_arm_contract" | string;
  revision_envelope_delivered?: boolean;
  previous_public_card_delivered?: boolean;
  public_card: PublicCard;
  public_diff?: {
    answer_before?: string | null;
    answer_after?: string | null;
    support_added_ids?: string[];
    support_dropped_ids?: string[];
    invalidated_added_ids?: string[];
    invalidated_dropped_ids?: string[];
    decision_fact_changes?: Array<Record<string, unknown>>;
  };
  call?: {
    status?: string;
    attempt_outcome?: string;
    requested_model?: string | null;
    returned_model?: string | null;
    service_tier?: string | null;
    max_output_tokens?: number | null;
    latency_ms?: number | null;
    usage?: Usage;
  };
};

export type ArmOutcome = {
  available: boolean;
  machine_success: boolean | null;
  evidence_consistent: boolean | null;
  checks: Record<string, boolean> | null;
  support_evidence_ids: string[];
  missing_required_evidence_ids: string[];
  unexpected_support_evidence_ids: string[];
  citation_precision?: number | null;
  citation_recall?: number | null;
};

export type ArmCost = {
  logical_calls: number;
  api_calls: number;
  latency_ms: number;
  input_tokens?: number | null;
  output_tokens?: number | null;
  reasoning_tokens?: number | null;
  total_tokens?: number | null;
  cached_input_tokens?: number | null;
  exact_provider_tokens: boolean;
};

export type InspectorArm = {
  arm: string;
  status: string;
  configured_output_token_ceiling: number;
  expected_api_calls: number;
  timeline: TimelineEntry[];
  outcome: ArmOutcome;
  cost: ArmCost;
};

export type InspectorRun = {
  run_id: string;
  trial_index: number;
  run_position: number;
  case_id: string;
  family: string;
  arm_order: string[];
  complete: boolean;
  case: {
    question: string;
    answer_choices: string[];
    decision_slots: Array<Record<string, unknown>>;
    evidence: EvidenceRecord[];
    revision_envelope?: {
      late_evidence_id?: string;
      relevant?: boolean;
      revision_cue?: number;
      invalidated_evidence_ids?: string[];
    } | null;
  };
  arms: InspectorArm[];
};

export type ContrastDefinition = {
  contrast_id: string;
  label?: string;
  reference_arm: string;
  candidate_arm: string;
  public_question?: string;
  available?: boolean;
};

export type InspectorSnapshot = {
  schema_version: string;
  artifact: {
    source_schema_version: string;
    mode: string;
    status: string;
    promotion_eligible: boolean;
    execution_complete: boolean;
    case_count?: number;
    trials?: number;
    run_count?: number;
    arm_set?: string[];
    claim_boundary: string[];
    provider_provenance: Record<string, Record<string, unknown>>;
    artifact_id?: string;
    captured_at?: string | null;
  };
  field_semantics?: Record<string, string>;
  contrast_definitions: ContrastDefinition[];
  summary: {
    arms: unknown;
    stable_cases: unknown;
    cause_decision?: {
      status: string;
      decision_unit?: string;
      rule_version?: string;
      [key: string]: unknown;
    };
  };
  runs: InspectorRun[];
};
