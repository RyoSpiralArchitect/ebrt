import type { WorkbenchSnapshot } from "../types";
import { Icon } from "./Icon";

type HeaderProps = {
  snapshot: WorkbenchSnapshot;
};

function short(value: string, length = 10) {
  return value.length <= length ? value : `${value.slice(0, length)}…`;
}

export function Header({ snapshot }: HeaderProps) {
  const source = snapshot.recorded_episode.source;
  const runId = typeof source.run_id === "string" ? source.run_id : snapshot.selection.case_id;
  const model = snapshot.recorded_episode.observer.provenance?.model;

  return (
    <header className="rw-header">
      <div className="rw-brand">
        <strong>EBRT Reasoning Workbench</strong>
        <span>Read-only recorded artifact</span>
      </div>
      <div className="rw-header-meta" aria-label="Artifact metadata">
        <div className="rw-readonly">
          <Icon name="lock" size={15} />
          <span>Read-only</span>
        </div>
        <div>
          <span>Episode</span>
          <strong title={runId}>{short(runId, 18)}</strong>
        </div>
        <div>
          <span>Model</span>
          <strong>{typeof model === "string" ? model : "Recorded receipt"}</strong>
        </div>
        <div>
          <span>Projection</span>
          <strong title={snapshot.recorded_episode.projection_fingerprint}>
            {short(snapshot.recorded_episode.projection_fingerprint)}
          </strong>
        </div>
        <div>
          <span>Schema</span>
          <strong>{snapshot.schema_version.replace("ebrt-reasoning-workbench-", "")}</strong>
        </div>
      </div>
    </header>
  );
}
