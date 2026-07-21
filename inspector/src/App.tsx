import { useEffect, useState, type KeyboardEvent } from "react";
import { AcceptanceStrip } from "./components/AcceptanceStrip";
import { AfterVerificationPanel } from "./components/AfterVerificationPanel";
import { ApplyRevisionHeader } from "./components/ApplyRevisionHeader";
import { BeforeLateEventPanel } from "./components/BeforeLateEventPanel";
import { RevisionEnginePanel } from "./components/RevisionEnginePanel";
import { loadApplyRevisionSnapshot } from "./applyRevisionSnapshot";
import type { ApplyRevisionSnapshot } from "./applyRevisionTypes";

type Stage = "before" | "engine" | "after";

const STAGES: Array<{ id: Stage; label: string }> = [
  { id: "before", label: "Before + Event" },
  { id: "engine", label: "Revision Engine" },
  { id: "after", label: "After + Verify" },
];

function MobileStageNav({ active, onSelect }: { active: Stage; onSelect: (stage: Stage) => void }) {
  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    event.preventDefault();
    const offset = event.key === "ArrowRight" ? 1 : -1;
    const nextIndex = (index + offset + STAGES.length) % STAGES.length;
    onSelect(STAGES[nextIndex].id);
    window.requestAnimationFrame(() => {
      document.getElementById(`stage-tab-${STAGES[nextIndex].id}`)?.focus({ preventScroll: true });
    });
  }

  return (
    <nav className="ar-stage-nav" aria-label="Apply Revision stages" role="tablist">
      {STAGES.map((stage, index) => (
        <button
          aria-controls={`stage-panel-${stage.id}`}
          aria-selected={active === stage.id}
          id={`stage-tab-${stage.id}`}
          key={stage.id}
          onClick={() => onSelect(stage.id)}
          onKeyDown={(event) => handleKeyDown(event, index)}
          role="tab"
          tabIndex={active === stage.id ? 0 : -1}
          type="button"
        >
          <span>0{index + 1}</span>
          {stage.label}
        </button>
      ))}
    </nav>
  );
}

export default function App() {
  const [snapshot, setSnapshot] = useState<ApplyRevisionSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeStage, setActiveStage] = useState<Stage>("before");
  const [replayStep, setReplayStep] = useState(0);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    loadApplyRevisionSnapshot().then(setSnapshot).catch((cause: unknown) => {
      setError(cause instanceof Error ? cause.message : "Recorded artifact projection failed to load");
    });
  }, []);

  useEffect(() => {
    if (!playing) return undefined;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reducedMotion) {
      setReplayStep(3);
      setActiveStage("after");
      setPlaying(false);
      return undefined;
    }
    const timers = [
      window.setTimeout(() => {
        setReplayStep(2);
        setActiveStage("engine");
      }, 420),
      window.setTimeout(() => {
        setReplayStep(3);
        setActiveStage("after");
        setPlaying(false);
      }, 940),
    ];
    return () => timers.forEach(window.clearTimeout);
  }, [playing]);

  function replayRecordedRevision() {
    setReplayStep(1);
    setActiveStage("engine");
    setPlaying(true);
  }

  if (error) {
    return (
      <main className="ar-load-state ar-load-error">
        <strong>EBRT Apply Revision</strong>
        <p>{error}</p>
        <code>/data/ebrt-apply-revision-acceptance-v0.6.2.1.json</code>
      </main>
    );
  }

  if (!snapshot) {
    return <main className="ar-load-state">Loading sealed Apply Revision artifact…</main>;
  }

  return (
    <div className={`ar-shell replay-step-${replayStep}`}>
      <ApplyRevisionHeader snapshot={snapshot} />
      <MobileStageNav active={activeStage} onSelect={setActiveStage} />

      <main className="ar-workspace">
        <BeforeLateEventPanel active={activeStage === "before"} snapshot={snapshot} />
        <RevisionEnginePanel
          active={activeStage === "engine"}
          onReplay={replayRecordedRevision}
          playing={playing}
          replayStep={replayStep}
          snapshot={snapshot}
        />
        <AfterVerificationPanel active={activeStage === "after"} replayStep={replayStep} snapshot={snapshot} />
      </main>

      <p className="ar-replay-announcer" aria-live="polite">
        {replayStep === 0
          ? "Recorded Apply Revision is ready to replay."
          : replayStep === 1
            ? "Replaying the recorded local backward pass."
            : replayStep === 2
              ? "Replaying the recorded public actuator compilation."
              : "Recorded Apply Revision replay complete. No new model call was made."}
      </p>
      <AcceptanceStrip snapshot={snapshot} />
    </div>
  );
}
