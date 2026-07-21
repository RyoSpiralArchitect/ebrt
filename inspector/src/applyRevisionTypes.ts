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
  signed_public_credit: number;
  source_effect: number;
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
    };
    public_control_map: {
      fingerprint_sha256: string;
      control_l2: number;
      max_control_l2: number;
      credit_rows: CreditRow[];
      checks: Record<string, boolean>;
    };
    compiled_actuator: {
      fingerprint_sha256: string;
      reinspect_evidence_ids: string[];
      suppress_evidence_ids: string[];
      preserve_evidence_ids: string[];
      correction_evidence_id: string;
      gradient_stops_here: boolean;
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
