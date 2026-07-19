import type {
  WorkbenchEvidence,
  WorkbenchInitial,
  WorkbenchLane,
  WorkbenchObserver,
  WorkbenchRevisionPlan,
} from "../types";
import { Icon } from "./Icon";

export type WorkbenchStage = "evidence" | "event" | "revision" | "replay" | "output";

type Props = {
  evidence: WorkbenchEvidence[];
  initial: WorkbenchInitial;
  observer: WorkbenchObserver;
  revisionPlan: WorkbenchRevisionPlan;
  lanes: WorkbenchLane[];
  selectedLaneId: string;
  onSelectLane: (laneId: string) => void;
  onPlay: () => void;
  playing: boolean;
  playbackStep: number;
  activeStage: WorkbenchStage;
};

const STAGES: Array<{ id: WorkbenchStage; number: number; title: string; subtitle: string }> = [
  { id: "evidence", number: 1, title: "Evidence", subtitle: "Recorded evidence chain" },
  { id: "event", number: 2, title: "Event", subtitle: "Revision trigger" },
  { id: "revision", number: 3, title: "Revision", subtitle: "Declared revision decision" },
  { id: "replay", number: 4, title: "Replay", subtitle: "Recorded replay lanes" },
  { id: "output", number: 5, title: "Output Diff", subtitle: "Public state diff" },
];

export function StageNav({
  activeStage,
  onSelect,
}: {
  activeStage: WorkbenchStage;
  onSelect: (stage: WorkbenchStage) => void;
}) {
  return (
    <nav className="rw-stage-nav" aria-label="Workbench stages">
      {STAGES.map((stage, index) => (
        <button
          type="button"
          key={stage.id}
          className={stage.id === activeStage ? "active" : ""}
          aria-current={stage.id === activeStage ? "step" : undefined}
          onClick={() => onSelect(stage.id)}
        >
          <span className="stage-number">{stage.number}</span>
          <span><strong>{stage.title}</strong><small>{stage.subtitle}</small></span>
          {index < STAGES.length - 1 ? <Icon name="chevron" size={14} /> : null}
        </button>
      ))}
    </nav>
  );
}

function evidenceLabel(evidence: WorkbenchEvidence) {
  if (evidence.phase === "event") return "Revision event";
  if (evidence.invalidated_by_event) return "Invalidated by event";
  return "Retained public evidence";
}

function StageHeading({ number, title, subtitle }: { number: number; title: string; subtitle: string }) {
  return (
    <header className="rw-stage-heading">
      <span>{number}</span>
      <div><h2>{title}</h2><p>{subtitle}</p></div>
    </header>
  );
}

function ReplayNodes({
  count,
  regenerated,
  invalidatedIndex,
  activeCount,
  mode = "replay",
}: {
  count: number;
  regenerated: number;
  invalidatedIndex: number;
  activeCount: number;
  mode?: "initial" | "replay";
}) {
  return (
    <div
      className="rw-replay-nodes"
      aria-label={mode === "initial" ? `${count} pre-event public cards` : `${regenerated} regenerated public cards`}
    >
      {Array.from({ length: count }, (_, index) => {
        const isInitial = mode === "initial";
        const isRegenerated = mode === "replay" && index >= count - regenerated;
        const isInvalidated = invalidatedIndex >= 0 && index === invalidatedIndex;
        const isActive = activeCount < 0 || index < activeCount;
        const classes = [
          "rw-replay-node",
          isInitial ? "initial" : isRegenerated ? "regenerated" : "retained",
          isInvalidated ? "invalidated" : "",
          isActive ? "active" : "pending",
        ].filter(Boolean).join(" ");
        return (
          <span className={classes} key={index} title={`R${index + 1}`}>
            <Icon name={isInvalidated ? "close" : "check"} size={11} />
          </span>
        );
      })}
    </div>
  );
}

export function ReasoningFlow({
  evidence,
  initial,
  observer,
  revisionPlan,
  lanes,
  selectedLaneId,
  onSelectLane,
  onPlay,
  playing,
  playbackStep,
  activeStage,
}: Props) {
  const invalidatedIndex = evidence.findIndex((item) => item.invalidated_by_event);
  const selectedLane = lanes.find((lane) => lane.lane_id === selectedLaneId);
  const playbackTotal = selectedLane?.public_cards.length ?? initial.public_cards.length;

  return (
    <>
      <section className={`rw-stage rw-evidence-stage ${activeStage === "evidence" ? "mobile-active" : ""}`} data-stage="evidence">
        <StageHeading number={1} title="Evidence" subtitle="Recorded evidence chain" />
        <ol className="rw-evidence-list">
          {evidence.map((item) => (
            <li
              key={item.evidence_id}
              className={`${item.invalidated_by_event ? "invalidated" : ""} ${item.phase === "event" ? "event" : ""}`}
            >
              <span className="rw-evidence-id">{item.evidence_id}</span>
              <div>
                <strong>{item.text}</strong>
                <small>{evidenceLabel(item)}</small>
              </div>
              <span className="rw-evidence-state">
                <Icon name={item.invalidated_by_event ? "close" : "check"} size={13} />
              </span>
            </li>
          ))}
        </ol>
      </section>

      <section className={`rw-stage rw-event-stage ${activeStage === "event" ? "mobile-active" : ""}`} data-stage="event">
        <StageHeading number={2} title="Event" subtitle="Revision trigger" />
        <div className="rw-event-card">
          <span className="rw-event-id">{observer.source_id}</span>
          <small>GPT public structured observer</small>
          <p>{observer.public_summary}</p>
          <dl>
            <div><dt>Relevant</dt><dd>{String(observer.relevant)}</dd></div>
            <div><dt>Invalidates</dt><dd>{observer.invalidated_evidence_ids.join(", ")}</dd></div>
            <div><dt>Revision cue</dt><dd>{observer.revision_cue?.toFixed(2) ?? "—"}</dd></div>
            <div><dt>Observer calls</dt><dd>{observer.receipt.usage.api_calls}</dd></div>
          </dl>
        </div>
      </section>

      <section className={`rw-stage rw-revision-stage ${activeStage === "revision" ? "mobile-active" : ""}`} data-stage="revision">
        <StageHeading number={3} title="Revision" subtitle="Declared revision decision" />
        <div className="rw-plan-card">
          <div className="rw-plan-lead">
            <span>Pre-outcome</span>
            <strong>{String(revisionPlan.pre_outcome)}</strong>
          </div>
          <dl>
            <div><dt>Anchor</dt><dd>{revisionPlan.selected_anchor_evidence_id}</dd></div>
            <div><dt>Replay floor</dt><dd>R{revisionPlan.execution_replay_floor + 1}</dd></div>
            <div><dt>Event</dt><dd>{observer.source_id}</dd></div>
            <div><dt>Selection</dt><dd>{revisionPlan.selection_mode.replaceAll("_", " ")}</dd></div>
            <div><dt>Plan seal</dt><dd title={revisionPlan.source_plan_fingerprint}>{revisionPlan.source_plan_fingerprint.slice(0, 10)}…</dd></div>
          </dl>
        </div>
        <p className="rw-stage-note">The horizon is recorded as {revisionPlan.trajectory_horizon_status.replaceAll("_", " ")}.</p>
      </section>

      <section className={`rw-stage rw-replay-stage ${activeStage === "replay" ? "mobile-active" : ""}`} data-stage="replay">
        <div className="rw-replay-title-row">
          <StageHeading number={4} title="Replay" subtitle="Recorded replay lanes · all attempts" />
          <button type="button" className="rw-play-button" onClick={onPlay} aria-pressed={playing}>
            <Icon name="play" size={15} />
            {playing ? "Playing record" : "Play recorded revision"}
          </button>
        </div>
        <div className="rw-lanes" role="group" aria-label="Recorded replay lanes">
          <button
            type="button"
            aria-pressed={selectedLaneId === "initial"}
            className={`rw-lane ${selectedLaneId === "initial" ? "selected" : ""}`}
            onClick={() => onSelectLane("initial")}
          >
            <div className="rw-lane-name"><strong>Initial</strong><span>{initial.observed_answer}</span></div>
            <ReplayNodes
              count={initial.public_cards.length}
              regenerated={0}
              invalidatedIndex={-1}
              activeCount={-1}
              mode="initial"
            />
            <div className="rw-lane-grade pre-event"><strong>PRE-EVENT</strong><span>answer match</span></div>
          </button>
          {lanes.map((lane) => {
            const selected = lane.lane_id === selectedLaneId;
            const activeCount = selected && playing ? playbackStep : -1;
            return (
              <button
                type="button"
                aria-pressed={selected}
                className={`rw-lane ${selected ? "selected" : ""}`}
                key={lane.lane_id}
                onClick={() => onSelectLane(lane.lane_id)}
              >
                <div className="rw-lane-name">
                  <strong>{lane.label}</strong>
                  <span>{lane.final_card.current_answer}</span>
                </div>
                <ReplayNodes
                  count={lane.public_cards.length}
                  regenerated={lane.regenerated_cards}
                  invalidatedIndex={invalidatedIndex}
                  activeCount={activeCount}
                />
                <div className={`rw-lane-grade ${lane.grade.machine_success ? "pass" : "fail"}`}>
                  <strong>{lane.grade.machine_success ? "PASS" : "FAIL"}</strong>
                  <span>{lane.regenerated_cards} regenerated</span>
                </div>
                <Icon name="chevron" size={16} />
              </button>
            );
          })}
        </div>
        <div className="rw-playback" aria-live="polite">
          <Icon name="play" size={14} />
          <span className="rw-playback-track"><i style={{ width: `${Math.min(100, (playbackStep / Math.max(playbackTotal, 1)) * 100)}%` }} /></span>
          <code>{Math.min(playbackStep, playbackTotal)} / {playbackTotal} public cards</code>
        </div>
      </section>
    </>
  );
}
