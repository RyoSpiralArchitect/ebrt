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
        {runs.map((run) => {
          const endpointsAssessed = run.primary_endpoint_assessed ?? run.complete;
          const outputsCompleted = run.all_outputs_completed ?? run.complete;
          return (
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
              {!endpointsAssessed ? (
                <small className="run-status incomplete">INCOMPLETE · at least one endpoint not assessed</small>
              ) : !outputsCompleted ? (
                <small className="run-status terminal">ASSESSED · at least one final output rejected</small>
              ) : null}
            </button>
          );
        })}
      </div>
      <div className="rail-note">
        <span aria-hidden="true">i</span>
        <p>Public state only.<br />No chain-of-thought.</p>
      </div>
    </aside>
  );
}
