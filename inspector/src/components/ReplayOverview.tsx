import { useEffect, useMemo, useState } from "react";
import { armLabel } from "../armLabels";
import type {
  ContrastDefinition,
  CostComparisonValue,
  DecisionFactChange,
  InspectorArm,
  InspectorRun,
  PublicCard,
  RunContrast,
} from "../types";
import { Icon } from "./Icon";

type Props = {
  run: InspectorRun;
  contrast?: ContrastDefinition;
  arms: InspectorArm[];
};

type OutputCardProps = {
  arm?: InspectorArm;
  card?: PublicCard;
  roleLabel: string;
  muted?: boolean;
};

const COST_ROWS: Array<{
  key: keyof NonNullable<RunContrast["cost"]>;
  label: string;
  format?: "duration";
}> = [
  { key: "api_calls", label: "API calls" },
  { key: "latency_ms", label: "Recorded latency", format: "duration" },
  { key: "input_tokens", label: "Input tokens" },
  { key: "output_tokens", label: "Output tokens" },
  { key: "reasoning_tokens", label: "Reasoning-token detail" },
  { key: "total_tokens", label: "Total tokens" },
];

function formatNumber(value: number | null | undefined) {
  return value == null ? "—" : new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
}

function formatDuration(value: number | null | undefined) {
  return value == null ? "—" : `${(value / 1000).toFixed(2)}s`;
}

function formatDelta(value: number | null | undefined, duration = false) {
  if (value == null) return "—";
  const sign = value > 0 ? "+" : "";
  if (duration) return `${sign}${(value / 1000).toFixed(2)}s`;
  return `${sign}${new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value)}`;
}

function finalCard(arm?: InspectorArm) {
  if (!arm || arm.status !== "completed") return undefined;
  const card = arm.timeline.at(-1)?.public_card;
  if (!card) return undefined;
  if (arm.outcome.final_checkpoint_id && card.checkpoint_id !== arm.outcome.final_checkpoint_id) {
    return undefined;
  }
  return card;
}

function primaryEndpointAssessed(arm?: InspectorArm) {
  if (!arm) return false;
  return arm.outcome.primary_endpoint_assessed
    ?? arm.primary_endpoint_assessed
    ?? arm.outcome.available;
}

function relationClass(relation?: RunContrast["outcome_relation"]) {
  if (relation === "both_pass") return "pass";
  if (relation === "neither_pass") return "fail";
  if (relation === "reference_only" || relation === "candidate_only") return "relation-directional";
  return "not-assessed";
}

function IdList({ ids, empty = "None" }: { ids?: string[]; empty?: string }) {
  if (!ids?.length) return <span className="id-empty">{empty}</span>;
  return (
    <span className="id-list">
      {ids.map((id) => <code key={id}>{id}</code>)}
    </span>
  );
}

function OutputCard({ arm, card, roleLabel, muted = false }: OutputCardProps) {
  const endpointAssessed = primaryEndpointAssessed(arm);
  const passed = endpointAssessed && arm?.outcome.machine_success === true;
  const gradeLabel = endpointAssessed ? (passed ? "PASS" : "FAIL") : "NOT ASSESSED";
  const gradeClass = endpointAssessed ? (passed ? "pass" : "fail") : "not-assessed";
  const answer = card?.current_answer ?? "Unavailable";
  const failurePosition = arm?.failure_sequence_offset == null
    ? ""
    : ` at call ${arm.failure_sequence_offset + 1}`;
  const missingCardCopy = endpointAssessed
    ? `No final public card was accepted. Endpoint outcome: strict failure${arm?.failure_reason_code ? ` (${arm.failure_reason_code})` : ""}${failurePosition}.`
    : `No completed final Reasoning Card was recorded. Non-assessable failure${arm?.provider_failure_type ? `: ${arm.provider_failure_type}` : ""}${failurePosition}.`;

  return (
    <article className={`replay-output-card ${muted ? "muted" : ""}`}>
      <header>
        <div>
          <span className="replay-role">{roleLabel}</span>
          <h2>{arm ? armLabel(arm.arm) : "Recorded arm unavailable"}</h2>
        </div>
        <span className={`replay-grade ${gradeClass}`}>{gradeLabel}</span>
      </header>
      <div className="answer-block">
        <small>Final public answer</small>
        <strong>{answer}</strong>
      </div>
      <div className="claim-block">
        <small>Recorded GPT public claim</small>
        <p>{card?.claim ?? missingCardCopy}</p>
      </div>
      <div className="output-facts">
        <small>Final public decision facts</small>
        {card?.decision_facts.length ? (
          <dl>
            {card.decision_facts.map((fact) => (
              <div key={fact.slot}>
                <dt>{fact.slot}</dt>
                <dd>
                  <strong>{fact.value}</strong>
                  <IdList ids={fact.evidence_ids} empty="No declared evidence" />
                </dd>
              </div>
            ))}
          </dl>
        ) : <p className="empty-copy">Final decision facts unavailable.</p>}
      </div>
      <footer>
        <span>
          <small>Declared support</small>
          <IdList ids={arm?.outcome.support_evidence_ids} />
        </span>
        <span>
          <small>Marked invalidated</small>
          <IdList ids={card?.invalidated_evidence_ids} />
        </span>
      </footer>
    </article>
  );
}

function FactDiff({ changes }: { changes?: DecisionFactChange[] }) {
  if (!changes?.length) return <p className="empty-copy">No public decision-fact changes.</p>;
  return (
    <div className="fact-diff-list">
      {changes.map((change) => (
        <div className="fact-diff-row" key={change.slot}>
          <strong>{change.slot}</strong>
          <span>
            <b>{change.before?.value ?? "Unavailable"}</b>
            <IdList ids={change.before?.evidence_ids} empty="No declared evidence" />
          </span>
          <Icon name="chevron" size={17} />
          <span className="candidate-value">
            <b>{change.after?.value ?? "Unavailable"}</b>
            <IdList ids={change.after?.evidence_ids} empty="No declared evidence" />
          </span>
        </div>
      ))}
    </div>
  );
}

function CostCell({ value, duration }: { value?: CostComparisonValue; duration?: boolean }) {
  const format = duration ? formatDuration : formatNumber;
  return (
    <>
      <td>{format(value?.reference)}</td>
      <td>{format(value?.candidate)}</td>
      <td>{formatDelta(value?.candidate_minus_reference, duration)}</td>
    </>
  );
}

function CostDiff({ contrast }: { contrast?: RunContrast }) {
  return (
    <div className="replay-cost-wrap">
      <table className="replay-cost-table">
        <thead>
          <tr>
            <th>Recorded usage</th>
            <th>Reference</th>
            <th>Candidate</th>
            <th>Candidate − reference</th>
          </tr>
        </thead>
        <tbody>
          {COST_ROWS.map((row) => (
            <tr key={row.key}>
              <th>{row.label}</th>
              <CostCell value={contrast?.cost?.[row.key]} duration={row.format === "duration"} />
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ReplayOverview({ run, contrast, arms }: Props) {
  const [revealed, setRevealed] = useState(false);
  const recordedContrast = run.contrasts?.find(
    (item) => item.contrast_id === contrast?.contrast_id,
  );
  const armMap = useMemo(() => new Map(arms.map((arm) => [arm.arm, arm])), [arms]);
  const referenceArm = contrast ? armMap.get(contrast.reference_arm) : arms[0];
  const candidateArm = contrast ? armMap.get(contrast.candidate_arm) : arms[1];
  const referenceCard = finalCard(referenceArm);
  const candidateCard = finalCard(candidateArm);
  const endpointComparisonAssessed = Boolean(
    recordedContrast?.primary_endpoints_assessed
      ?? (primaryEndpointAssessed(referenceArm) && primaryEndpointAssessed(candidateArm)),
  );
  const publicDiffAvailable = Boolean(
    referenceCard
      && candidateCard
      && recordedContrast?.available
      && (recordedContrast.public_output_diff_available ?? true)
      && recordedContrast.outcome_relation !== "incomplete",
  );
  const lateEvidence = run.case.evidence.find(
    (item) => item.evidence_id === run.case.revision_envelope?.late_evidence_id,
  ) ?? run.case.evidence.find((item) => item.kind === "late");
  const invalidated = run.case.revision_envelope?.invalidated_evidence_ids ?? [];
  const eventRelevant = run.case.revision_envelope?.relevant;
  const candidateEndpointAssessed = primaryEndpointAssessed(candidateArm);
  const candidateReadyLabel = candidateCard
    ? "Recorded candidate output ready"
    : candidateEndpointAssessed
      ? "Recorded terminal failure ready"
      : "Recorded candidate outcome incomplete";
  const candidateReadyCopy = candidateCard
    ? "Playback reveals an existing public Reasoning Card."
    : candidateEndpointAssessed
      ? "No final public card was accepted. Playback exposes the recorded endpoint failure."
      : "No final public card or assessed endpoint was recorded for this arm.";

  useEffect(() => setRevealed(false), [run.run_id, contrast?.contrast_id]);

  return (
    <main className="replay-overview" aria-labelledby="replay-title">
      <header className="replay-heading">
        <div>
          <h1 id="replay-title">Recorded replay / final output</h1>
          <p>{run.case.question}</p>
        </div>
        <div className="replay-readonly-note">
          <Icon name="lock" size={15} />
          <span>Recorded artifact playback · no new model call</span>
        </div>
      </header>

      <section className="replay-event" aria-label="Recorded late-evidence event">
        <div className="event-id">{lateEvidence?.evidence_id ?? "Late evidence"}</div>
        <div>
          <small>
            Recorded late evidence
            {eventRelevant === false ? " · no-op fixture" : eventRelevant === true ? " · revision relevant" : ""}
          </small>
          <p>{lateEvidence?.text ?? "Late-evidence text unavailable."}</p>
        </div>
        <div className="event-invalidates">
          <small>Fixture-listed invalidation</small>
          <IdList ids={invalidated} />
        </div>
      </section>

      <section className="replay-question" aria-label="Selected recorded contrast">
        <span>{contrast?.public_question ?? "Recorded execution-protocol comparison"}</span>
        <strong>{referenceArm ? armLabel(referenceArm.arm) : "Reference unavailable"}</strong>
        <Icon name="chevron" size={16} />
        <strong>{candidateArm ? armLabel(candidateArm.arm) : "Candidate unavailable"}</strong>
      </section>

      <section className="replay-stage" aria-label="Recorded final-output comparison">
        <OutputCard arm={referenceArm} card={referenceCard} roleLabel="Reference recorded output" />
        <div className="replay-bridge">
          <span>Recorded candidate playback</span>
          <Icon name="chevron" size={20} />
        </div>
        {revealed ? (
          <div className="replay-revealed" id="recorded-candidate-output" aria-live="polite">
            <OutputCard arm={candidateArm} card={candidateCard} roleLabel="Candidate recorded output" />
          </div>
        ) : (
          <div className="replay-awaiting" id="recorded-candidate-output">
            <Icon name="lock" size={18} />
            <strong>{candidateReadyLabel}</strong>
            <span>{candidateReadyCopy}</span>
          </div>
        )}
      </section>

      <div className="replay-controls">
        <button
          type="button"
          className="replay-button"
          aria-controls="recorded-candidate-output replay-diff"
          aria-expanded={revealed}
          onClick={() => setRevealed((value) => !value)}
        >
          {revealed
            ? "Reset recorded playback"
            : candidateCard
              ? "Play recorded output"
              : candidateEndpointAssessed
                ? "Show recorded endpoint outcome"
                : "Show recorded incomplete state"}
          <Icon name="chevron" size={16} />
        </button>
        <span>Read-only control. Source evidence, cards, grades, and receipts are unchanged.</span>
      </div>

      {revealed ? (
        <section className="replay-diff" id="replay-diff" aria-labelledby="diff-title">
          <div className="diff-heading">
            <div>
              <h2 id="diff-title">Public output diff</h2>
              <p>Cross-arm final-card comparison, not an edit of model state.</p>
            </div>
            <strong className={relationClass(endpointComparisonAssessed ? recordedContrast?.outcome_relation : "incomplete")}>
              {endpointComparisonAssessed
                ? recordedContrast?.outcome_relation?.replaceAll("_", " ")
                : "COMPARISON INCOMPLETE"}
            </strong>
          </div>
          {publicDiffAvailable ? (
            <>
              <div className="diff-grid">
                <div className="diff-panel">
                  <h3>Decision facts</h3>
                  <FactDiff changes={recordedContrast?.decision_fact_changes} />
                </div>
                <div className="diff-panel support-diff">
                  <h3>Declared public support</h3>
                  <dl>
                    <div><dt>Reference only</dt><dd><IdList ids={recordedContrast?.public_support_diff?.reference_only_ids} /></dd></div>
                    <div><dt>Shared</dt><dd><IdList ids={recordedContrast?.public_support_diff?.shared_ids} /></dd></div>
                    <div><dt>Candidate only</dt><dd><IdList ids={recordedContrast?.public_support_diff?.candidate_only_ids} /></dd></div>
                  </dl>
                  <p>Declared support does not prove exclusive semantic influence.</p>
                </div>
              </div>
            </>
          ) : (
            <div className="incomplete-comparison">
              <strong>Final-card diff is not available.</strong>
              <p>
                {endpointComparisonAssessed
                  ? "The endpoint comparison is assessed, but at least one arm has no accepted final public card."
                  : "At least one arm has neither an accepted final public card nor an assessed endpoint."}
              </p>
            </div>
          )}
          {recordedContrast?.available ? <CostDiff contrast={recordedContrast} /> : null}
          <p className="usage-boundary">Reasoning-token detail is provider usage metadata, not chain-of-thought, reasoning quality, or total compute.</p>
        </section>
      ) : null}

      <footer className="replay-boundary">
        <span>Recorded contaminated DEV</span>
        <span>Post-event protocol comparison</span>
        <span>No online detection claim</span>
        <span>Causal interpretation follows the locked artifact gate above</span>
      </footer>
    </main>
  );
}
