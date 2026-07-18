import type { EvidenceRecord, InspectorArm } from "../types";
import { armLabel } from "../armLabels";
import {
  entryAtEvidenceStep,
  publicSupportState,
  rawApertureState,
  type PublicSupportState,
  type RawApertureState,
} from "./EvidenceTimeline";
import { Icon } from "./Icon";

type Props = {
  evidence: EvidenceRecord[];
  arms: InspectorArm[];
  selectedStep: number;
};

const RAW_LABELS: Record<RawApertureState, string> = {
  "available-in-call": "Available in call",
  "not-in-raw-aperture": "Not in raw aperture",
  "not-arrived": "Not yet presented in replay",
  "no-call-yet": "No call yet",
};
const SUPPORT_LABELS: Record<PublicSupportState, string> = {
  "in-declared-support": "In declared support",
  "not-in-declared-support": "Not in declared support",
  "marked-invalidated": "Marked invalidated",
  "no-card-yet": "No emitted card",
};

function StateCell({ raw, support }: { raw: RawApertureState; support: PublicSupportState }) {
  return (
    <span className="lineage-state">
      <span className={`lineage-dimension raw ${raw}`}>
        <small>Raw</small>
        <strong>{RAW_LABELS[raw]}</strong>
      </span>
      <span className={`lineage-dimension support ${support}`}>
        <span className="lineage-icon">
        <Icon
          name={support === "in-declared-support" ? "check" : support === "no-card-yet" ? "minus" : "close"}
          size={14}
        />
        </span>
        <span><small>Card</small><strong>{SUPPORT_LABELS[support]}</strong></span>
      </span>
    </span>
  );
}

export function EvidenceLineage({ evidence, arms, selectedStep }: Props) {
  return (
    <aside className="lineage-panel" aria-labelledby="lineage-title">
      <div className="section-title-row compact">
        <div>
          <h2 id="lineage-title">Evidence lineage</h2>
          <p>Per-call raw scope and emitted public support</p>
        </div>
      </div>
      <div className="lineage-table-wrap">
        <table className="lineage-table">
          <thead>
            <tr>
              <th>Evidence</th>
              {arms.map((arm) => <th key={arm.arm}>{armLabel(arm.arm)}</th>)}
            </tr>
          </thead>
          <tbody>
            {evidence.map((item) => (
              <tr key={item.evidence_id}>
                <th>
                  <strong>{item.evidence_id}</strong>
                  <span>{item.kind === "late" ? "Late evidence" : item.text}</span>
                </th>
                {arms.map((arm) => (
                  <td key={arm.arm}>
                    <StateCell
                      raw={rawApertureState(item, arm, evidence, selectedStep)}
                      support={publicSupportState(item, arm, evidence, selectedStep)}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="lineage-legend" aria-label="Evidence-state legend">
        <span><i className="legend raw" /> Raw aperture</span>
        <span><i className="legend retained" /> In declared support</span>
        <span><i className="legend missing" /> Not in declared support</span>
        <span><i className="legend invalidated" /> Marked invalidated</span>
      </div>
      <div className="delivery-source">
        Input-scope provenance: {Array.from(new Set(arms.map((arm) => entryAtEvidenceStep(arm, evidence, selectedStep)?.presented_raw_evidence_ids_source).filter(Boolean))).join(" / ") || "no emitted call"}
      </div>
    </aside>
  );
}
