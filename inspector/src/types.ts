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

export type DecisionSlot = {
  slot_id: string;
  description?: string;
  required?: boolean;
  allowed_values?: string[];
};

export type FactSnapshot = {
  value: string;
  evidence_ids: string[];
};

export type DecisionFactChange = {
  slot: string;
  before: FactSnapshot | null;
  after: FactSnapshot | null;
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
    answer_changed?: boolean;
    support_ids?: string[];
    support_added_ids?: string[];
    support_dropped_ids?: string[];
    invalidated_added_ids?: string[];
    invalidated_dropped_ids?: string[];
    decision_fact_changes?: DecisionFactChange[];
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
  primary_endpoint_assessed?: boolean;
  machine_success: boolean | null;
  evidence_consistent: boolean | null;
  final_checkpoint_id?: string | null;
  final_answer?: string | null;
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
  source_arm?: string;
  status: string;
  failure_category?: string | null;
  failure_reason_code?: string | null;
  failure_sequence_offset?: number | null;
  provider_failure_type?: string | null;
  terminal_outcome?: string;
  primary_endpoint_assessed?: boolean;
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
  primary_endpoint_assessed?: boolean;
  all_outputs_completed?: boolean;
  case: {
    question: string;
    answer_choices: string[];
    decision_slots: DecisionSlot[];
    evidence: EvidenceRecord[];
    revision_envelope?: {
      late_evidence_id?: string;
      relevant?: boolean;
      revision_cue?: number;
      invalidated_evidence_ids?: string[];
    } | null;
  };
  arms: InspectorArm[];
  contrasts?: RunContrast[];
};

export type ContrastDefinition = {
  contrast_id: string;
  label?: string;
  reference_arm: string;
  candidate_arm: string;
  public_question?: string;
  available?: boolean;
};

export type OutcomeRelation =
  | "both_pass"
  | "reference_only"
  | "candidate_only"
  | "neither_pass"
  | "incomplete";

export type CostComparisonValue = {
  reference: number | null;
  candidate: number | null;
  candidate_minus_reference: number | null;
  candidate_over_reference: number | null;
};

export type RunContrast = ContrastDefinition & {
  available: boolean;
  missing_arms?: string[];
  outcome_relation?: OutcomeRelation;
  primary_endpoints_assessed?: boolean;
  public_output_diff_available?: boolean;
  final_answer?: {
    reference: string | null;
    candidate: string | null;
    equal: boolean;
  };
  public_support_diff?: {
    reference_only_ids: string[];
    shared_ids: string[];
    candidate_only_ids: string[];
  };
  decision_fact_changes?: DecisionFactChange[];
  configured_output_token_ceiling_equal?: boolean;
  cost?: Partial<Record<
    | "api_calls"
    | "latency_ms"
    | "input_tokens"
    | "output_tokens"
    | "total_tokens"
    | "reasoning_tokens",
    CostComparisonValue
  >>;
};

export type InspectorViewMode = "overview" | "inspect";

export type InspectorSnapshot = {
  schema_version: string;
  artifact: {
    source_schema_version: string;
    mode: string;
    status: string;
    result_status?: string;
    promotion_eligible: boolean;
    execution_complete: boolean;
    all_outputs_completed?: boolean;
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
