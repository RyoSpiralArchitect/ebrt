import type { ContrastDefinition, InspectorSnapshot, InspectorViewMode } from "../types";
import { Icon } from "./Icon";

type HeaderProps = {
  snapshot: InspectorSnapshot;
  contrasts: ContrastDefinition[];
  selectedContrastId: string;
  onContrastChange: (id: string) => void;
  viewMode: InspectorViewMode;
  onViewModeChange: (mode: InspectorViewMode) => void;
};

const CONTRAST_LABELS: Record<string, string> = {
  direct_full_recorded_calibration: "Direct / Full recorded calibration",
  revision_envelope_ablation: "Fixed envelope / No envelope",
  raw_aperture_ablation: "Card-only / Retained evidence",
  staged_residual: "Fixed Direct / Cumulative staged",
};

export function Header({
  snapshot,
  contrasts,
  selectedContrastId,
  onContrastChange,
  viewMode,
  onViewModeChange,
}: HeaderProps) {
  const models = Array.from(new Set(
    Object.values(snapshot.artifact.provider_provenance)
      .map((item) => item.model)
      .filter((item): item is string => typeof item === "string"),
  ));
  const model = models.length === 1 ? models[0] : "See per-arm receipts";
  const causeStatus = snapshot.summary.cause_decision?.status ?? "not available";
  const decisionReady = causeStatus === "classified_locked_controls";
  const datasetLabel = snapshot.artifact.mode
    .replace(/^openai_live_dev_/, "")
    .replaceAll("_", " ");
  const schemaLabel = snapshot.schema_version.replace("ebrt-public-inspector-", "");
  const endpointsAssessed = snapshot.artifact.execution_complete;
  const outputsCompleted = snapshot.artifact.all_outputs_completed ?? endpointsAssessed;
  return (
    <header className="topbar">
      <div className="brand-block">
        <div className="brand-name">EBRT Inspector</div>
        <div className="brand-subtitle">Read-only artifact view</div>
      </div>
      <div className="artifact-control">
        <div className="view-switch" role="group" aria-label="Inspector view">
          <button
            type="button"
            aria-pressed={viewMode === "overview"}
            className={viewMode === "overview" ? "selected" : ""}
            onClick={() => onViewModeChange("overview")}
          >
            Overview
          </button>
          <button
            type="button"
            aria-pressed={viewMode === "inspect"}
            className={viewMode === "inspect" ? "selected" : ""}
            onClick={() => onViewModeChange("inspect")}
          >
            Inspect
          </button>
        </div>
        <label htmlFor="contrast-select">Execution protocol contrast</label>
        <select
          id="contrast-select"
          value={selectedContrastId}
          onChange={(event) => onContrastChange(event.target.value)}
        >
          {contrasts.map((contrast) => (
            <option key={contrast.contrast_id} value={contrast.contrast_id}>
              {contrast.label ?? CONTRAST_LABELS[contrast.contrast_id] ?? contrast.contrast_id}
            </option>
          ))}
        </select>
      </div>
      <div className="header-meta" aria-label="Artifact metadata">
        <div className="readonly-mark">
          <Icon name="lock" size={16} />
          <span>Read-only</span>
        </div>
        <div className="meta-item">
          <span>Dataset</span>
          <strong title={snapshot.artifact.mode}>{datasetLabel}</strong>
        </div>
        <div className="meta-item">
          <span>Model</span>
          <strong>{model}</strong>
        </div>
        <div className="meta-item">
          <span>Schema</span>
          <strong title={snapshot.schema_version}>{schemaLabel}</strong>
        </div>
      </div>
      <div className="boundary-strip" aria-label="Interpretation boundary">
        <strong>{snapshot.artifact.status} · {snapshot.artifact.promotion_eligible ? "promotion eligible" : "non-promotional"}</strong>
        <strong className={decisionReady ? "pass" : "not-assessed"}>Cause decision: {decisionReady ? "READY" : "NOT READY"}</strong>
        <span>Endpoints: {endpointsAssessed ? "assessed" : "incomplete"}</span>
        <span>Outputs: {outputsCompleted ? "complete" : "incomplete"}</span>
        <span>Recorded contaminated DEV</span>
        <span>Public state only</span>
        <span>Observer not evaluated</span>
        <span>Selective not executed</span>
        <span>Nominal output ceiling only</span>
      </div>
    </header>
  );
}
