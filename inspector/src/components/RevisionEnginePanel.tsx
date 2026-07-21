import type { ApplyRevisionSnapshot } from "../applyRevisionTypes";
import { Icon } from "./Icon";

function formatObjective(value: number) {
  return value.toFixed(4);
}

export function RevisionEnginePanel({
  active,
  onReplay,
  playing,
  replayStep,
  snapshot,
}: {
  active: boolean;
  onReplay: () => void;
  playing: boolean;
  replayStep: number;
  snapshot: ApplyRevisionSnapshot;
}) {
  const { compiled_actuator: actuator, public_control_map: control, surrogate } = snapshot.revision_engine;
  const visibleCredits = control.credit_rows.filter((row) => ["R2", "R3", "R4", "R5", "R6"].includes(row.evidence_id));
  const maxCredit = Math.max(...visibleCredits.map((row) => Math.abs(row.signed_public_credit)));

  return (
    <section
      aria-labelledby="engine-title"
      className={`ar-panel ar-engine-panel ${active ? "mobile-active" : ""}`}
      id="stage-panel-engine"
      role="tabpanel"
    >
      <header className="ar-panel-title">
        <span>02</span>
        <h1 id="engine-title">EBRT Revision Engine</h1>
      </header>

      <div className={`ar-engine-step ar-surrogate-block ${replayStep >= 1 ? "is-replaying" : ""}`}>
        <span className="ar-block-label">Local surrogate</span>
        <div className="ar-event-node">Late evidence R6</div>
        <Icon name="arrow" size={18} />
        <div className="ar-objective-row">
          <span>Revision objective</span>
          <strong>{formatObjective(surrogate.objective_before)}</strong>
          <Icon name="arrow" size={16} />
          <strong>{formatObjective(surrogate.objective_after)}</strong>
        </div>
        <div className="ar-backward-row">
          <span>backward()</span>
          <strong>EXECUTED LOCALLY · {surrogate.dtype}</strong>
        </div>
      </div>

      <div className={`ar-engine-step ar-control-block ${replayStep >= 1 ? "is-replaying" : ""}`}>
        <div className="ar-block-heading">
          <span className="ar-block-label">Public control map</span>
          <code>L2 {control.control_l2.toFixed(4)} / {control.max_control_l2.toFixed(2)}</code>
        </div>
        <div className="ar-credit-map" aria-label="Signed public credit by evidence">
          {visibleCredits.map((row) => (
            <div className={row.evidence_id === "R3" ? "suppressed" : ""} key={row.evidence_id}>
              <strong>{row.evidence_id}</strong>
              <span><i style={{ width: `${Math.max(2, Math.abs(row.signed_public_credit) / maxCredit * 100)}%` }} /></span>
              <code>{row.signed_public_credit.toFixed(4)}</code>
            </div>
          ))}
        </div>
      </div>

      <div className={`ar-engine-step ar-actuator-block ${replayStep >= 2 ? "is-replaying" : ""}`}>
        <span className="ar-block-label">Compiled actuator · provider-visible</span>
        <dl>
          <div><dt>Reinspect</dt><dd className="ar-blue">{actuator.reinspect_evidence_ids.join(" → ")}</dd></div>
          <div><dt>Suppress</dt><dd className="ar-red">{actuator.suppress_evidence_ids.join(", ")}</dd></div>
          <div><dt>Preserve</dt><dd>{actuator.preserve_evidence_ids.join(", ")}</dd></div>
        </dl>
      </div>

      <div className="ar-boundary">
        <span>GRADIENT STOPS HERE</span>
        <p>{snapshot.revision_engine.boundary}</p>
      </div>

      <div className="ar-regeneration-node">{snapshot.case.model} · full-context regeneration</div>
      <button
        aria-describedby="replay-status"
        aria-pressed={replayStep === 3}
        className="ar-replay-button"
        disabled={playing}
        onClick={onReplay}
        type="button"
      >
        <Icon name="play" size={18} />
        Replay recorded Apply Revision
      </button>
      <span className="ar-replay-status" id="replay-status">
        {playing ? "Replaying sealed public states…" : replayStep === 3 ? "Replay complete · no model call" : "Local playback · no model call"}
      </span>
    </section>
  );
}
