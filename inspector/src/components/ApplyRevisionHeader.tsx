import type { ApplyRevisionView } from "../applyRevisionTypes";
import { Icon } from "./Icon";

type InspectorMode = "recorded" | "live";

export function ApplyRevisionHeader({
  busy,
  mode,
  onModeChange,
  onOpenEditor,
  recordedOnly,
  snapshot,
}: {
  busy: boolean;
  mode: InspectorMode;
  onModeChange: (mode: InspectorMode) => void;
  onOpenEditor: () => void;
  recordedOnly: boolean;
  snapshot: ApplyRevisionView;
}) {
  const liveResult = snapshot.mode === "LIVE_AFTER_REGENERATION";
  const livePending = snapshot.mode === "LIVE_RECORDED_REFERENCE";
  return (
    <header className="ar-header">
      <div className="ar-brand">
        <strong>EBRT</strong>
        <span>Apply Revision</span>
      </div>
      <div className="ar-case-line">
        <span>CASE</span>
        <strong>{snapshot.case.case_id}</strong>
        <i aria-hidden="true">·</i>
        <b>{snapshot.before.answer}</b>
        <Icon name="arrow" size={18} />
        <b className={livePending ? "ar-pending" : "ar-blue"}>{snapshot.after.answer}</b>
      </div>
      <div className="ar-mode-area">
        {!recordedOnly ? <div aria-label="Inspector mode" className="ar-mode-switch" role="group">
          <button
            aria-pressed={mode === "recorded"}
            disabled={busy}
            onClick={() => onModeChange("recorded")}
            type="button"
          >
            Recorded
          </button>
          <button
            aria-pressed={mode === "live"}
            disabled={busy}
            onClick={() => onModeChange("live")}
            type="button"
          >
            Live
          </button>
          <button aria-pressed="false" disabled={busy} onClick={onOpenEditor} type="button">
            Editor
          </button>
        </div> : null}
        <div className={`ar-mode-status ${mode === "live" ? "live" : "recorded"}`}>
          <Icon name={mode === "live" ? "runs" : "lock"} size={16} />
          <span>
            {mode === "recorded"
              ? recordedOnly
                ? "PUBLIC RECORDED DEMO · NO API OR MODEL CALL"
                : "RECORDED ACCEPTANCE · NO NEW MODEL CALL"
              : liveResult
                ? "LIVE AFTER REGENERATION · 1 PROVIDER ATTEMPT"
                : "LIVE READY · APPLY TO REGENERATE"}
          </span>
        </div>
      </div>
    </header>
  );
}
