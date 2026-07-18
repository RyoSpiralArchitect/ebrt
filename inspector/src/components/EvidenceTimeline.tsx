import type { EvidenceRecord, InspectorArm, TimelineEntry } from "../types";
import { armLabel } from "../armLabels";
import { Icon } from "./Icon";

export type RawApertureState = "available-in-call" | "not-in-raw-aperture" | "not-arrived" | "no-call-yet";
export type PublicSupportState = "in-declared-support" | "not-in-declared-support" | "marked-invalidated" | "no-card-yet";

export function entryAtEvidenceStep(
  arm: InspectorArm,
  evidence: EvidenceRecord[],
  stepIndex: number,
): TimelineEntry | undefined {
  const selectedId = evidence[stepIndex]?.evidence_id;
  if (!selectedId) return undefined;
  const exact = arm.timeline.find((entry) => entry.current_evidence_id === selectedId);
  if (exact) return exact;
  if (arm.timeline.length === 1 && arm.timeline[0].current_evidence_id == null) {
    return stepIndex === evidence.length - 1 ? arm.timeline[0] : undefined;
  }
  return undefined;
}

export function publicSupport(entry?: TimelineEntry) {
  if (!entry) return new Set<string>();
  const support = new Set(entry.public_card.evidence_ids ?? []);
  entry.public_card.decision_facts?.forEach((fact) =>
    fact.evidence_ids.forEach((evidenceId) => support.add(evidenceId)),
  );
  return support;
}

export function rawApertureState(
  evidence: EvidenceRecord,
  arm: InspectorArm,
  allEvidence: EvidenceRecord[],
  stepIndex: number,
): RawApertureState {
  const entry = entryAtEvidenceStep(arm, allEvidence, stepIndex);
  if (!entry) return "no-call-yet";
  if (evidence.ordinal > stepIndex + 1) return "not-arrived";
  return (entry.presented_raw_evidence_ids ?? []).includes(evidence.evidence_id)
    ? "available-in-call"
    : "not-in-raw-aperture";
}

export function publicSupportState(
  evidence: EvidenceRecord,
  arm: InspectorArm,
  allEvidence: EvidenceRecord[],
  stepIndex: number,
): PublicSupportState {
  const entry = entryAtEvidenceStep(arm, allEvidence, stepIndex);
  if (!entry) return "no-card-yet";
  if (entry.public_card.invalidated_evidence_ids.includes(evidence.evidence_id)) {
    return "marked-invalidated";
  }
  return publicSupport(entry).has(evidence.evidence_id)
    ? "in-declared-support"
    : "not-in-declared-support";
}

function StateGlyph({ raw, support }: { raw: RawApertureState; support: PublicSupportState }) {
  return (
    <span className="state-pair" aria-label={`Raw aperture: ${raw}; public card: ${support}`}>
      <i className={`raw-glyph ${raw}`} title={`Raw aperture: ${raw}`} />
      <span className={`state-glyph ${support}`} title={`Public card: ${support}`}>
        <Icon
          name={support === "in-declared-support" ? "check" : support === "no-card-yet" ? "minus" : "close"}
          size={15}
        />
      </span>
    </span>
  );
}

type TimelineProps = {
  evidence: EvidenceRecord[];
  arms: InspectorArm[];
  selectedArm: string;
  selectedStep: number;
  onSelectArm: (arm: string) => void;
  onSelectStep: (step: number) => void;
  revisionEnvelope?: {
    late_evidence_id?: string;
    relevant?: boolean;
  } | null;
};

export function EvidenceTimeline({
  evidence,
  arms,
  selectedArm,
  selectedStep,
  onSelectArm,
  onSelectStep,
  revisionEnvelope,
}: TimelineProps) {
  const lateEvidence = evidence.find((item) => item.kind === "late");
  const annotationLabel = lateEvidence
    ? `${revisionEnvelope?.relevant === false ? "Irrelevant fixture annotation" : "Fixed fixture annotation"} · ${lateEvidence.evidence_id}`
    : null;
  return (
    <section className="timeline-panel" aria-labelledby="timeline-title">
      <div className="section-title-row">
        <div>
          <h1 id="timeline-title">Evidence order / post-annotation replay step</h1>
          <p>Per-call raw aperture and emitted public-card support are shown separately.</p>
        </div>
        {annotationLabel ? <div className="revision-label">{annotationLabel}</div> : null}
      </div>
      <div className="evidence-head" style={{ "--evidence-count": evidence.length } as React.CSSProperties}>
        {evidence.map((item, index) => (
          <button
            type="button"
            key={item.evidence_id}
            className={`evidence-node ${item.kind === "late" ? "late" : ""} ${selectedStep === index ? "selected" : ""}`}
            onClick={() => onSelectStep(index)}
            title={item.text}
          >
            <strong>{item.evidence_id}</strong>
            <span>{item.kind === "late" ? "Late evidence" : `Evidence ${item.ordinal}`}</span>
          </button>
        ))}
      </div>
      <div className="arm-lanes">
        {arms.map((arm) => {
          const finalEntry = arm.status === "completed" ? arm.timeline.at(-1) : undefined;
          const selectedEntry = entryAtEvidenceStep(arm, evidence, selectedStep);
          const endpointAssessed = arm.outcome.primary_endpoint_assessed
            ?? arm.primary_endpoint_assessed
            ?? arm.outcome.available;
          const success = endpointAssessed && arm.outcome.machine_success === true;
          const envelopeDelivered = arm.timeline.some((entry) => entry.revision_envelope_delivered === true);
          return (
            <button
              type="button"
              className={`arm-lane ${selectedArm === arm.arm ? "selected" : ""}`}
              key={arm.arm}
              onClick={() => onSelectArm(arm.arm)}
            >
              <span className="arm-summary">
                <strong>{armLabel(arm.arm)}</strong>
                <small className={endpointAssessed ? (success ? "pass" : "fail") : "not-assessed"}>
                  Final endpoint: {endpointAssessed ? (success ? "PASS" : "FAIL") : "NOT ASSESSED"} · {arm.cost.api_calls} {arm.cost.api_calls === 1 ? "call" : "calls"}
                </small>
                <small>Envelope: {envelopeDelivered ? "delivered" : "null"}</small>
                <small>{selectedEntry ? `Emitted card: ${selectedEntry.public_card.checkpoint_id}` : "No emitted card at this step"}</small>
              </span>
              <span className="lane-states" style={{ "--evidence-count": evidence.length } as React.CSSProperties}>
                {evidence.map((item) => (
                  <StateGlyph
                    key={item.evidence_id}
                    raw={rawApertureState(item, arm, evidence, selectedStep)}
                    support={publicSupportState(item, arm, evidence, selectedStep)}
                  />
                ))}
              </span>
              <span className="lane-answer">
                <small>Final public answer</small>
                <strong>{finalEntry?.public_card.current_answer ?? "Unavailable"}</strong>
              </span>
            </button>
          );
        })}
      </div>
      <div className="timeline-footnote">
        <span>Selected evidence position: {evidence[selectedStep]?.evidence_id ?? "final"}</span>
        <span>These are post-event calibration calls, not an online detection trace.</span>
        <span>Declared support does not prove exclusive semantic influence.</span>
      </div>
    </section>
  );
}
