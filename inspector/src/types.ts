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

export type WorkbenchAccounting = {
  logical_calls: number;
  api_calls: number;
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  reasoning_tokens: number;
  total_tokens: number;
  cached_input_tokens?: number;
  cache_write_tokens?: number;
  exact_provider_tokens: boolean;
};

export type WorkbenchEvidence = {
  evidence_id: string;
  ordinal: number;
  phase: "initial" | "event" | string;
  text: string;
  invalidated_by_event: boolean;
};

export type WorkbenchInitial = {
  phase: "pre_event" | string;
  status: string;
  expected_answer: string;
  observed_answer: string;
  answer_exact: boolean;
  post_event_machine_success: null;
  public_card: PublicCard;
  public_cards: PublicCard[];
  accounting: WorkbenchAccounting;
};

export type WorkbenchLaneGrade = {
  machine_success: boolean;
  evidence_consistent: boolean;
  checks: Record<string, boolean>;
  citation_precision: number;
  citation_recall: number;
  missing_required_evidence_ids: string[];
  support_evidence_ids: string[];
  unexpected_support_evidence_ids: string[];
  stale_historical_cards: number;
};

export type WorkbenchPublicDiff = {
  answer_before: string;
  answer_after: string;
  answer_changed: boolean;
  support_before_ids: string[];
  support_after_ids: string[];
  support_added_ids: string[];
  support_dropped_ids: string[];
  invalidated_added_ids: string[];
  invalidated_dropped_ids: string[];
  decision_fact_changes: DecisionFactChange[];
  derived_from: string;
};

export type WorkbenchLane = {
  lane_id: "card_only_forward" | "selective_replay" | "full_restart" | string;
  label: string;
  source_plan_fingerprint: string;
  calls: number;
  regenerated_cards: number;
  replay_accounting: WorkbenchAccounting;
  public_cards: PublicCard[];
  final_card: PublicCard;
  grade: WorkbenchLaneGrade;
  public_output_diff: WorkbenchPublicDiff;
};

export type WorkbenchObserver = {
  source_id: string;
  relevant: boolean;
  public_summary: string;
  invalidated_evidence_ids: string[];
  topic?: string;
  confidence?: number;
  revision_cue?: number;
  provenance: {
    adapter_name: string;
    adapter_version: string;
    deterministic: boolean;
    model: string;
    provider: string;
    semantic_source: string;
  };
  receipt: {
    status: string;
    attempt_outcome: string;
    requested_model: string;
    returned_model: string;
    service_tier: string;
    retry_count: number;
    refusal_count: number;
    provider: string;
    usage: WorkbenchAccounting;
  };
  [key: string]: unknown;
};

export type WorkbenchEvent = {
  event_evidence_id: string;
  relevant: boolean;
  invalidated_evidence_ids: string[];
  public_summary: string;
  triggered: boolean;
  selected_anchor_evidence_id: string;
  [key: string]: unknown;
};

export type WorkbenchRevisionPlan = {
  pre_outcome: boolean;
  event_triggered: boolean;
  selected_anchor_evidence_id: string;
  selected_anchor_step: number;
  checkpoint_step: number;
  execution_replay_floor: number;
  selection_mode: string;
  invalidated_evidence_ids: string[];
  source_plan_fingerprint: string;
  trajectory_horizon_status: string;
  [key: string]: unknown;
};

export type ProviderPipelineStage = {
  stage_id: string;
  label: string;
  count: number;
  detail?: string;
  status?: string;
  status_code?: number;
};

export type ProviderFailureAtlas = {
  artifact: string;
  status: string;
  primary_execution_classification: string;
  pipeline: ProviderPipelineStage[];
  classified_failure: {
    phase: string;
    allowlisted_reason_code: string;
    phase_count: number;
    count: number;
    unclassified_count: number;
    [key: string]: unknown;
  };
  native_diagnostic_coverage: {
    v0_4_3_contract_smoke: { numerator: number; denominator: number; fraction: string };
    r01_frozen_native: { numerator: number; denominator: number; fraction: string };
    cross_block_effect_estimate: null;
    [key: string]: unknown;
  };
  gates: Record<string, boolean>;
  claim_boundary: string;
};

export type ApertureArmContext = {
  label?: string;
  machine_successes?: number;
  assessed_endpoints?: number;
  completed_endpoints?: number;
  fraction?: string;
  reasoning_tokens?: number;
  [key: string]: unknown;
};

export type WorkbenchSnapshot = {
  schema_version: string;
  status: string;
  generation: {
    builder_sha256: string;
    deterministic: boolean;
    network_calls: number;
    projection_lock_sha256: string;
    projection_mode: string;
    source_sha256: Record<string, string>;
    timestamp_recorded: boolean;
  };
  selection: {
    case_id: string;
    case_rule: string;
    trial_index: number;
    unique_match: boolean;
  };
  field_semantics: Record<string, string>;
  recorded_episode: {
    source: Record<string, unknown>;
    question: string;
    answer_choices: string[];
    decision_slots: DecisionSlot[];
    evidence: WorkbenchEvidence[];
    initial: WorkbenchInitial;
    observer: WorkbenchObserver;
    event: WorkbenchEvent;
    revision_plan: WorkbenchRevisionPlan;
    replay_lanes: WorkbenchLane[];
    public_output_comparison: {
      before: PublicCard;
      after: PublicCard;
      diff: WorkbenchPublicDiff;
      selected_recorded_lane: string;
      selection_rationale: string;
    };
    recorded_physical_experiment_accounting: WorkbenchAccounting;
    negative_lanes_retained: string[];
    projection_fingerprint: string;
  };
  aperture_context: {
    relationship_to_recorded_episode: string;
    v0_4_1: Record<string, unknown>;
    v0_4_2_unchanged_replication_r01: Record<string, unknown>;
    claim_boundary: string;
  };
  provider_failure_atlas: ProviderFailureAtlas;
  gates: Record<string, boolean>;
  claim_boundary: string[];
};
