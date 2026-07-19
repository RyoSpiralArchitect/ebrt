import type { WorkbenchSnapshot } from "../types";
import { Icon } from "./Icon";

export function WorkbenchRail({ snapshot }: { snapshot: WorkbenchSnapshot }) {
  return (
    <aside className="rw-rail">
      <div className="rw-rail-title"><Icon name="runs" size={18} /><h2>Runs</h2></div>
      <div className="rw-rail-list">
        <button type="button" className="selected" aria-current="true">
          <strong>{snapshot.selection.case_id}</strong>
          <span>Trial {snapshot.selection.trial_index}</span>
          <small>Recorded episode · projected</small>
        </button>
      </div>
      <div className="rw-rail-context">
        <span>Context artifacts</span>
        <p>v0.4.1 aperture DEV</p>
        <p>v0.4.2 r01 replication</p>
        <p>v0.4.3 provider smoke</p>
      </div>
      <div className="rw-rail-note">
        <Icon name="lock" size={14} />
        <p>Immutable recorded projection.<br />No edits permitted.</p>
      </div>
    </aside>
  );
}
