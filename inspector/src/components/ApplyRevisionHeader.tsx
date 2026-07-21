import type { ApplyRevisionSnapshot } from "../applyRevisionTypes";
import { Icon } from "./Icon";

export function ApplyRevisionHeader({ snapshot }: { snapshot: ApplyRevisionSnapshot }) {
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
        <b className="ar-blue">{snapshot.after.answer}</b>
      </div>
      <div className="ar-recorded-mode">
        <Icon name="lock" size={16} />
        <span>RECORDED ACCEPTANCE · NO NEW MODEL CALL</span>
      </div>
    </header>
  );
}
