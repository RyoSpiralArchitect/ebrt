import type { InspectorRun } from "../types";
import { Icon } from "./Icon";

type RunRailProps = {
  runs: InspectorRun[];
  selectedRunId: string;
  onSelect: (runId: string) => void;
};

export function RunRail({ runs, selectedRunId, onSelect }: RunRailProps) {
  return (
    <aside className="run-rail">
      <div className="rail-heading">
        <Icon name="runs" />
        <h2>Runs</h2>
      </div>
      <div className="run-list" role="listbox" aria-label="Recorded benchmark runs">
        {runs.map((run) => (
          <button
            type="button"
            role="option"
            aria-selected={run.run_id === selectedRunId}
            className={`run-row ${run.run_id === selectedRunId ? "selected" : ""}`}
            key={run.run_id}
            onClick={() => onSelect(run.run_id)}
          >
            <span>{run.case_id}</span>
            <small>Trial {run.trial_index} · {run.family}</small>
            {!run.complete ? <small className="run-status incomplete">INCOMPLETE · grade not assessed for at least one arm</small> : null}
          </button>
        ))}
      </div>
      <div className="rail-note">
        <span aria-hidden="true">i</span>
        <p>Public state only.<br />No chain-of-thought.</p>
      </div>
    </aside>
  );
}
