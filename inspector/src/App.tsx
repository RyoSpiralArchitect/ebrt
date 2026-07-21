import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { AcceptanceStrip } from "./components/AcceptanceStrip";
import { AfterVerificationPanel } from "./components/AfterVerificationPanel";
import { ApplyRevisionHeader } from "./components/ApplyRevisionHeader";
import { BeforeLateEventPanel } from "./components/BeforeLateEventPanel";
import { ProtocolEditor } from "./components/ProtocolEditor";
import { RevisionEnginePanel } from "./components/RevisionEnginePanel";
import type { LiveRevisionPhase } from "./components/RevisionEnginePanel";
import { loadApplyRevisionSnapshot } from "./applyRevisionSnapshot";
import type { ApplyRevisionSnapshot, ApplyRevisionView, LiveRequestBinding } from "./applyRevisionTypes";
import { applyLiveRevision, bindCallerRequest, loadLiveDemoRequest } from "./liveRevisionApi";
import {
  liveApplyRevisionView,
  liveRecordedReferenceView,
  recordedApplyRevisionView,
} from "./liveRevisionView";

type Stage = "before" | "engine" | "after";
type InspectorMode = "recorded" | "live";

const RECORDED_ONLY = import.meta.env.VITE_EBRT_RECORDED_ONLY === "true";

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
  const [recordedSnapshot, setRecordedSnapshot] = useState<ApplyRevisionSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<InspectorMode>("recorded");
  const [liveView, setLiveView] = useState<ApplyRevisionView | null>(null);
  const [livePhase, setLivePhase] = useState<LiveRevisionPhase>("idle");
  const [liveError, setLiveError] = useState<string | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editorValue, setEditorValue] = useState("");
  const [editorError, setEditorError] = useState<string | null>(null);
  const [editorLoading, setEditorLoading] = useState(false);
  const [activeStage, setActiveStage] = useState<Stage>("before");
  const [replayStep, setReplayStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const liveAbort = useRef<AbortController | null>(null);
  const liveInFlight = useRef(false);
  const liveSequence = useRef(0);

  useEffect(() => {
    loadApplyRevisionSnapshot().then(setRecordedSnapshot).catch((cause: unknown) => {
      setError(cause instanceof Error ? cause.message : "Recorded artifact projection failed to load");
    });
  }, []);

  useEffect(
    () => () => {
      liveSequence.current += 1;
      liveAbort.current?.abort();
    },
    [],
  );

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
    if (mode !== "recorded") return;
    setReplayStep(1);
    setActiveStage("engine");
    setPlaying(true);
  }

  function selectMode(nextMode: InspectorMode) {
    if (liveInFlight.current || (RECORDED_ONLY && nextMode === "live")) return;
    setMode(nextMode);
    setPlaying(false);
    setLiveError(null);
    if (nextMode === "recorded") {
      setReplayStep(0);
      setActiveStage("before");
    } else {
      setReplayStep(liveView ? 3 : 0);
      setActiveStage(liveView ? "after" : "engine");
    }
  }

  async function executeLiveRevision(
    loadBinding: (signal: AbortSignal) => Promise<LiveRequestBinding>,
    initialPhase: LiveRevisionPhase,
  ) {
    if (RECORDED_ONLY || mode !== "live" || liveInFlight.current) return;
    const controller = new AbortController();
    const sequence = ++liveSequence.current;
    liveAbort.current = controller;
    liveInFlight.current = true;
    setLiveView(null);
    setLiveError(null);
    setLivePhase(initialPhase);
    setReplayStep(1);
    setActiveStage("engine");

    try {
      const binding = await loadBinding(controller.signal);
      if (sequence !== liveSequence.current || controller.signal.aborted) return;
      setLivePhase("regenerating");
      setReplayStep(2);
      const response = await applyLiveRevision(binding, controller.signal);
      if (sequence !== liveSequence.current || controller.signal.aborted) return;
      setLiveView(liveApplyRevisionView(response));
      setLivePhase("complete");
      setReplayStep(3);
      setActiveStage("after");
    } catch (cause: unknown) {
      if (sequence !== liveSequence.current) return;
      if (controller.signal.aborted || (cause instanceof DOMException && cause.name === "AbortError")) {
        setLivePhase("aborted");
        setLiveError(null);
      } else {
        setLivePhase("error");
        setLiveError(cause instanceof Error ? cause.message : "Live Apply Revision failed");
      }
      setReplayStep(0);
      setActiveStage("engine");
    } finally {
      if (sequence === liveSequence.current) {
        liveInFlight.current = false;
        liveAbort.current = null;
      }
    }
  }

  async function applyLiveRevisionFromFreshTemplate() {
    await executeLiveRevision(loadLiveDemoRequest, "loading-template");
  }

  function openEditor() {
    if (RECORDED_ONLY || liveInFlight.current) return;
    setMode("live");
    setLiveError(null);
    setEditorError(null);
    setEditorOpen(true);
  }

  async function loadEditorSample() {
    if (editorLoading || liveInFlight.current) return;
    const controller = new AbortController();
    setEditorLoading(true);
    setEditorError(null);
    try {
      const envelope = await loadLiveDemoRequest(controller.signal);
      const request = structuredClone(envelope.request);
      request.request_id = `editor-${globalThis.crypto.randomUUID()}`;
      request.case_id = `${String(request.case_id)}-caller-sample`;
      setEditorValue(JSON.stringify(request, null, 2));
    } catch (cause: unknown) {
      setEditorError(cause instanceof Error ? cause.message : "Could not load the protocol sample");
    } finally {
      setEditorLoading(false);
    }
  }

  async function submitEditorRequest() {
    if (editorLoading || liveInFlight.current) return;
    setEditorError(null);
    let parsed: unknown;
    try {
      parsed = JSON.parse(editorValue);
    } catch {
      setEditorError("Request JSON is not valid JSON.");
      return;
    }
    try {
      const binding = await bindCallerRequest(parsed);
      setEditorOpen(false);
      await executeLiveRevision(async () => binding, "regenerating");
    } catch (cause: unknown) {
      setEditorError(cause instanceof Error ? cause.message : "Request could not be prepared");
    }
  }

  function abortLiveRevision() {
    liveAbort.current?.abort();
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

  if (!recordedSnapshot) {
    return <main className="ar-load-state">Loading sealed Apply Revision artifact…</main>;
  }

  const recordedView = recordedApplyRevisionView(recordedSnapshot);
  const snapshot = mode === "live" ? liveView ?? liveRecordedReferenceView(recordedSnapshot) : recordedView;
  const liveBusy = livePhase === "loading-template" || livePhase === "regenerating";

  return (
    <div className={`ar-shell replay-step-${replayStep}`}>
      <ApplyRevisionHeader
        busy={liveBusy || editorLoading}
        mode={mode}
        onModeChange={selectMode}
        onOpenEditor={openEditor}
        recordedOnly={RECORDED_ONLY}
        snapshot={snapshot}
      />
      <MobileStageNav active={activeStage} onSelect={setActiveStage} />

      <main className="ar-workspace">
        <BeforeLateEventPanel active={activeStage === "before"} snapshot={snapshot} />
        <RevisionEnginePanel
          active={activeStage === "engine"}
          liveError={liveError}
          livePhase={livePhase}
          mode={mode}
          onAbort={abortLiveRevision}
          onLiveApply={applyLiveRevisionFromFreshTemplate}
          onReplay={replayRecordedRevision}
          playing={playing}
          replayStep={replayStep}
          snapshot={snapshot}
        />
        <AfterVerificationPanel active={activeStage === "after"} replayStep={replayStep} snapshot={snapshot} />
      </main>

      <p className="ar-replay-announcer" aria-live="polite">
        {mode === "live"
          ? livePhase === "loading-template"
            ? "Loading a fresh server-owned Apply Revision request."
            : livePhase === "regenerating"
              ? "Live regeneration is in progress."
              : livePhase === "complete"
                ? "Live regeneration complete. Semantic correctness and effect attribution were not assessed."
                : livePhase === "aborted"
                  ? "Stopped waiting. The server run may still complete."
                  : livePhase === "error"
                    ? "Live Apply Revision failed. The recorded reference remains available."
                    : "Live mode is ready. No request is made until Apply is pressed."
          : replayStep === 0
            ? "Recorded Apply Revision is ready to replay."
            : replayStep === 1
              ? "Replaying the recorded local backward pass."
              : replayStep === 2
                ? "Replaying the recorded public actuator compilation."
                : "Recorded Apply Revision replay complete. No new model call was made."}
      </p>
      <AcceptanceStrip snapshot={snapshot} />
      <ProtocolEditor
        busy={liveBusy || editorLoading}
        error={editorError}
        onChange={(value) => {
          setEditorValue(value);
          setEditorError(null);
        }}
        onClose={() => {
          if (!liveBusy && !editorLoading) setEditorOpen(false);
        }}
        onLoadSample={loadEditorSample}
        onSubmit={submitEditorRequest}
        open={editorOpen}
        value={editorValue}
      />
    </div>
  );
}
