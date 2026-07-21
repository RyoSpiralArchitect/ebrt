export type EvidenceRole =
  | "public_evidence"
  | "invalidated"
  | "stable_constraint"
  | "late_event";

export type EvidenceRecord = {
  evidence_id: string;
  text: string;
  role: EvidenceRole;
};

export type TargetValue = {
  slot: string;
  target_id: string;
  target_type: "fact" | "constraint";
  value: string;
};

export type CreditRow = {
  active_before: boolean;
  evidence_id: string;
  gradient: number;
  finite_difference_gradient: number;
  signed_public_credit?: number;
  reinspection_salience?: number;
  control_value?: number;
  eligible_for_reinspection?: boolean;
  baseline_allocation_fraction?: number;
  optimized_allocation_fraction?: number;
  allocation_delta?: number;
  surrogate_contribution_before?: number;
  surrogate_contribution_after?: number;
  source_effect: number;
};

export type InspectionPlanStep = {
  evidence_id: string;
  priority_rank: number;
  controller_allocation_fraction: number;
  inspection_share: number;
  allocation_delta: number;
  relative_emphasis: number;
  review_depth: "LIGHT" | "STANDARD" | "DEEP";
  inspection_budget_units: number;
};

export type RevisionProgramStep = {
  step_index: number;
  operation:
    | "LOAD_EVENT"
    | "SUPPRESS"
    | "REINSPECT"
    | "PRESERVE"
    | "PREPARE_FULL_CONTEXT_REGENERATION";
  evidence_id?: string;
  priority_rank?: number;
  controller_allocation_fraction?: number;
  inspection_share?: number;
  allocation_delta?: number;
  relative_emphasis?: number;
  review_depth?: "LIGHT" | "STANDARD" | "DEEP";
  inspection_budget_units?: number;
};

export type ActuatorExecutionTraceStep = {
  step_index: number;
  operation: RevisionProgramStep["operation"];
  state_before: string;
  state_after: string;
  evidence_id: string | null;
};

export type PublicDependencyAudit = {
  fingerprint_sha256: string;
  mode: "PUBLIC_GRAPH_BLOCK_RESTORE";
  scope: "SELECTED_CALLER_SUPPLIED_PUBLIC_GRAPH_ONLY";
  blocked_evidence_id: string;
  provider_calls: 0;
  hosted_output_regenerated: false;
  structural_dependency_status: "PASS" | "FAIL";
  hosted_causality_status: "NOT_ASSESSED";
  counterfactual_output_effect_status: "NOT_ASSESSED";
  baseline_closure_fingerprint_sha256: string;
  blocked_closure_fingerprint_sha256: string;
  unblocked_closure_fingerprint_sha256: string;
  changed_fact_targets: Array<{
    target_id: string;
    baseline_contains_correction: boolean;
    blocked_contains_correction: boolean;
    blocked_lineage_changed: boolean;
    blocked_lineage_evidence_ids: string[];
    unblocked_lineage_exact: boolean;
  }>;
  mask_trace: Array<{
    phase: "BLOCK" | "UNBLOCK_AND_RECOMPUTE";
    blocked_evidence_ids: string[];
    closure_fingerprint_sha256: string;
  }>;
  stable_target_ids: string[];
  checks: Record<string, boolean>;
};

export type VerificationRow = {
  label: string;
  detail: string;
  status: "PASS" | "FAIL";
};

export type ApplyRevisionSnapshot = {
  schema_version: string;
  mode: "RECORDED_ARTIFACT_PLAYBACK";
  case: {
    case_id: string;
    version: string;
    question: string;
    model: string;
  };
  source: {
    manifest_fingerprint_sha256: string;
    manifest_sha256: string;
    result_fingerprint_sha256: string;
    trace_fingerprint_sha256: string;
    artifact_sha256: Record<string, string>;
  };
  evidence: EvidenceRecord[];
  before: {
    horizon_evidence_ids: string[];
    answer: string;
    selected_closure_id: string;
    target_values: TargetValue[];
    active_support_evidence_ids: string[];
    provider_output_fingerprint_sha256: string;
    own_horizon_status: "PASS" | "FAIL";
    post_event_status: "PASS" | "FAIL";
    post_event_failed_axes: string[];
  };
  late_event: {
    evidence_id: string;
    event_id: string;
    text: string;
    invalidated_evidence_ids: string[];
    stable_evidence_ids: string[];
  };
  revision_engine: {
    actual_before_state: {
      fingerprint_sha256: string;
      source_selected_closure_id: string;
      initial_scalar: number;
      active_support_evidence_ids: string[];
    };
    surrogate: {
      objective_before: number;
      objective_after: number;
      terminal_target: number;
      dtype: string;
      backward_calls: number;
      maximum_finite_difference_error: number;
      inspection_temperature?: number;
      surrogate_terminal_state_before?: number;
      surrogate_terminal_state_after?: number;
    };
    public_control_map: {
      fingerprint_sha256: string;
      control_l2: number;
      max_control_l2: number;
      credit_rows: CreditRow[];
      allocation_domain_evidence_ids?: string[];
      checks: Record<string, boolean>;
    };
    compiled_actuator: {
      fingerprint_sha256: string;
      reinspect_evidence_ids: string[];
      reinspect_source?: string;
      suppress_evidence_ids: string[];
      suppress_source?: string;
      preserve_evidence_ids: string[];
      preserve_source?: string;
      correction_evidence_id: string;
      source_control_map_fingerprint_sha256?: string;
      inspection_plan?: {
        fingerprint_sha256: string;
        allocation_scope: "SELECTED_PUBLIC_REINSPECTION_STEPS";
        total_budget_units: number;
        budget_unit_semantics: "ABSTRACT_PUBLIC_REVIEW_ALLOCATION_NOT_PROVIDER_TOKENS";
        steps: InspectionPlanStep[];
      };
      program?: {
        fingerprint_sha256: string;
        state: "COMPILED";
        source_control_map_fingerprint_sha256: string;
        steps: RevisionProgramStep[];
      };
      checks?: Record<string, boolean>;
      gradient_stops_here: boolean;
    };
    actuator_execution?: {
      fingerprint_sha256: string;
      status: "COMPLETED";
      source_actuator_fingerprint_sha256: string;
      source_program_fingerprint_sha256: string;
      final_state: "READY_FOR_PROVIDER";
      trace: ActuatorExecutionTraceStep[];
      emitted_provider_operation_fingerprint_sha256: string;
      provider_payload_fingerprint_sha256: string;
      provider_payload_receipt_binding_status: "PASS";
      checks: Record<string, boolean>;
    };
    boundary: string;
  };
  after: {
    answer: string;
    selected_closure_id: string;
    target_values: TargetValue[];
    active_support_evidence_ids: string[];
    invalidated_evidence_ids: string[];
    invalidation_edges: Array<{
      source_evidence_id: string;
      target_evidence_id: string;
    }>;
    provider_output_fingerprint_sha256: string;
    strict_status: "PASS" | "FAIL";
    fact_local_lineage_status: "PASS" | "FAIL";
  };
  output_diff: {
    answer: { before: string; after: string };
    selected_closure_id: { before: string; after: string };
    support_added_evidence_ids: string[];
    support_dropped_evidence_ids: string[];
    stable_target_ids: string[];
    target_values: Array<{
      slot: string;
      target_id: string;
      before: string;
      after: string;
      changed: boolean;
    }>;
  };
  public_dependency_audit?: PublicDependencyAudit;
  verification: VerificationRow[];
  decision: {
    run_status: string;
    mechanism_status: "PASS" | "FAIL";
    before_status: string;
    after_status: string;
    diff_status: string;
    product_acceptance_status: "PASS" | "FAIL";
    effect_attribution_status: "NOT_ASSESSED";
    terminal_decision: string;
  };
  accounting: {
    api_calls: number;
    logical_calls: number;
    input_tokens: number;
    output_tokens: number;
    reasoning_tokens: number;
    total_tokens: number;
    latency_ms: number;
  };
  claim_boundary: string[];
};

export type AssessmentStatus = "PASS" | "FAIL" | "NOT_ASSESSED";

export type ProviderPublicOutput = {
  schema_version: string;
  checkpoint_id: string;
  current_answer: string;
  selected_closure_id: string;
  target_values: TargetValue[];
};

export type ApplyRevisionView = Omit<
  ApplyRevisionSnapshot,
  "mode" | "source" | "before" | "after" | "verification" | "decision"
> & {
  mode: "RECORDED_ARTIFACT_PLAYBACK" | "LIVE_RECORDED_REFERENCE" | "LIVE_AFTER_REGENERATION";
  source: {
    kind: "recorded" | "live";
    display_fingerprint_sha256: string;
    input_fingerprint_sha256?: string;
    input_provenance?: "CALLER_SUPPLIED_UNVERIFIED" | "CONTAMINATED_REGRESSION_FIXTURE";
    source_artifact_fingerprint_sha256?: string;
    transport_body_sha256?: string;
    server_response_fingerprint_sha256?: string;
    manifest_fingerprint_sha256?: string;
    manifest_sha256?: string;
    trace_fingerprint_sha256?: string;
    artifact_sha256?: Record<string, string>;
  };
  before: Omit<ApplyRevisionSnapshot["before"], "own_horizon_status" | "post_event_status"> & {
    own_horizon_status: AssessmentStatus;
    post_event_status: AssessmentStatus;
  };
  after: Omit<ApplyRevisionSnapshot["after"], "strict_status" | "fact_local_lineage_status"> & {
    strict_status: AssessmentStatus;
    fact_local_lineage_status: AssessmentStatus;
  };
  verification: Array<{
    label: string;
    detail: string;
    status: AssessmentStatus;
  }>;
  assessment: {
    run_label: string;
    run_status: string;
    mechanism_status: AssessmentStatus;
    acceptance_label: string;
    acceptance_status: AssessmentStatus;
    semantic_correctness_status: AssessmentStatus;
    effect_attribution_status: "NOT_ASSESSED";
    provider_attempts: number;
    terminal_label: string;
    cost_label: string;
  };
};

export type LiveDemoRequestEnvelope = {
  schema_version: "ebrt-live-demo-request-v0.6.2.3";
  provenance: "CONTAMINATED_REGRESSION_FIXTURE";
  source_artifact_fingerprint_sha256: string;
  request_fingerprint_sha256: string;
  fingerprint_sha256: string;
  request: Record<string, unknown> & {
    schema_version: "ebrt-live-apply-revision-request-v0.6.2.3";
    request_id: string;
  };
};

export type LiveApplyRevisionResponse = {
  schema_version: "ebrt-live-apply-revision-response-v0.6.2.3";
  transport_body_sha256: string;
  request_id: string;
  status: "COMPLETE";
  mode: "LIVE_AFTER_REGENERATION";
  case_id: string;
  input_fingerprint_sha256: string;
  context: {
    question: string;
    model: string;
    input_provenance: "CALLER_SUPPLIED_UNVERIFIED" | "CONTAMINATED_REGRESSION_FIXTURE";
    source_artifact_fingerprint_sha256: string | null;
    evidence: EvidenceRecord[];
    before_horizon_evidence_ids: string[];
    late_event: {
      evidence_id: string;
      event_id: string;
      text: string;
      invalidated_evidence_ids: string[];
      stable_evidence_ids: string[];
    };
  };
  mechanism: {
    status: "PASS" | "FAIL";
    actual_before_state: ApplyRevisionSnapshot["revision_engine"]["actual_before_state"];
    surrogate: ApplyRevisionSnapshot["revision_engine"]["surrogate"];
    public_control_map: ApplyRevisionSnapshot["revision_engine"]["public_control_map"];
    compiled_actuator: ApplyRevisionSnapshot["revision_engine"]["compiled_actuator"] & {
      source_control_map_fingerprint_sha256: string;
      inspection_plan: NonNullable<
        ApplyRevisionSnapshot["revision_engine"]["compiled_actuator"]["inspection_plan"]
      >;
      program: NonNullable<
        ApplyRevisionSnapshot["revision_engine"]["compiled_actuator"]["program"]
      >;
      checks: Record<string, boolean>;
    };
    actuator_execution: NonNullable<
      ApplyRevisionSnapshot["revision_engine"]["actuator_execution"]
    >;
    boundary: string;
  };
  output: {
    before: {
      public_output: ProviderPublicOutput;
      compiled_output_fingerprint_sha256: string;
      active_support_evidence_ids: string[];
      invalidated_evidence_ids: string[];
      invalidation_edges: ApplyRevisionSnapshot["after"]["invalidation_edges"];
    };
    after: {
      public_output: ProviderPublicOutput;
      compiled_output_fingerprint_sha256: string;
      active_support_evidence_ids: string[];
      invalidated_evidence_ids: string[];
      invalidation_edges: ApplyRevisionSnapshot["after"]["invalidation_edges"];
    };
    diff: ApplyRevisionSnapshot["output_diff"];
  };
  verification: {
    rows: ApplyRevisionView["verification"];
    operational_acceptance_status: "PASS" | "FAIL";
    provider_output_schema_status: "PASS" | "FAIL";
    lineage_binding_status: "PASS" | "FAIL";
    public_actuator_execution_status: "PASS" | "FAIL";
    provider_delivery_status: "PASS" | "FAIL";
    provider_uptake_status: "NOT_ASSESSED";
    structural_dependency_status: "PASS" | "FAIL";
    counterfactual_output_effect_status: "NOT_ASSESSED";
    semantic_correctness_status: "NOT_ASSESSED";
    effect_attribution_status: "NOT_ASSESSED";
    provider_attempts: 1;
  };
  public_dependency_audit: PublicDependencyAudit;
  accounting: ApplyRevisionSnapshot["accounting"];
  claim_boundary: string[];
  fingerprint_sha256: string;
};
