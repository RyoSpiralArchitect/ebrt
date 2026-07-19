import type { PublicCard, WorkbenchLane } from "../types";
import type { WorkbenchStage } from "./ReasoningFlow";
import { Icon } from "./Icon";

type Props = {
  initialCard: PublicCard;
  lane?: WorkbenchLane;
  activeStage: WorkbenchStage;
};

function facts(card: PublicCard) {
  return new Map(card.decision_facts.map((fact) => [fact.slot, fact]));
}

function Ids({ values, empty = "none" }: { values: string[]; empty?: string }) {
  if (!values.length) return <span className="rw-empty">{empty}</span>;
  return <>{values.map((value) => <code key={value}>{value}</code>)}</>;
}

export function PublicOutputDiff({ initialCard, lane, activeStage }: Props) {
  const after = lane?.final_card ?? initialCard;
  const diff = lane?.public_output_diff;
  const beforeFacts = facts(initialCard);
  const afterFacts = facts(after);
  const slots = Array.from(new Set([...beforeFacts.keys(), ...afterFacts.keys()]));
  const answerChanged = initialCard.current_answer !== after.current_answer;

  return (
    <section className={`rw-stage rw-output-stage ${activeStage === "output" ? "mobile-active" : ""}`} data-stage="output">
      <header className="rw-stage-heading">
        <span>5</span>
        <div><h2>Final Output Diff</h2><p>Public state diff · git-style</p></div>
      </header>

      <div className="rw-answer-diff">
        <small>Selected recorded output</small>
        <div className={answerChanged ? "removed" : "unchanged"}>
          <span>{answerChanged ? "−" : "="}</span><code>answer = {initialCard.current_answer}</code>
        </div>
        {answerChanged ? (
          <div className="added"><span>+</span><code>answer = {after.current_answer}</code></div>
        ) : null}
      </div>

      <div className="rw-fact-diff">
        {slots.map((slot) => {
          const before = beforeFacts.get(slot);
          const next = afterFacts.get(slot);
          const changed = before?.value !== next?.value;
          return (
            <div className={changed ? "changed" : "stable"} key={slot}>
              <strong>@@ {slot}</strong>
              {changed ? <code className="removed">− {slot} = {before?.value ?? "UNSET"}</code> : null}
              <code className={changed ? "added" : "unchanged"}>
                {changed ? "+" : " "} {slot} = {next?.value ?? "UNSET"}
              </code>
            </div>
          );
        })}
      </div>

      <div className="rw-support-diff">
        <div><span>Support added</span><p><Ids values={diff?.support_added_ids ?? []} /></p></div>
        <div><span>Support dropped</span><p><Ids values={diff?.support_dropped_ids ?? []} /></p></div>
        <div><span>Invalidated</span><p><Ids values={diff?.invalidated_added_ids ?? []} /></p></div>
      </div>

      <div className="rw-output-outcome">
        <div>
          <span>Outcome</span>
          <strong className={!lane ? "pre-event" : lane.grade.machine_success ? "pass" : "fail"}>
            {!lane ? "PRE-EVENT" : lane.grade.machine_success ? "PASS" : "FAIL"}
          </strong>
        </div>
        <div>
          <span>Replay calls</span>
          <strong>{lane?.calls ?? 0}</strong>
        </div>
        <div>
          <span>Tokens</span>
          <strong>{lane ? new Intl.NumberFormat("en-US").format(lane.replay_accounting.total_tokens) : "—"}</strong>
        </div>
      </div>

      <p className="rw-public-only-note">
        <Icon name="lock" size={12} />
        Diff derived from emitted public Reasoning Cards only. No latent state or chain-of-thought.
      </p>
    </section>
  );
}
