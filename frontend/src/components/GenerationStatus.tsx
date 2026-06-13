import type { PodcastStatus, StageEvent } from "../types";
import { PIPELINE_STAGES } from "../types";

type StageState = "done" | "active" | "failed" | "pending";

interface Props {
  status: PodcastStatus;
  currentStage: string;
  stageHistory: StageEvent[];
}

function buildState(
  stageKey: string,
  completed: Set<string>,
  failedStage: string | null,
  currentStage: string,
  status: PodcastStatus,
): StageState {
  if (completed.has(stageKey)) return "done";
  if (failedStage === stageKey) return "failed";
  const inFlight = status === "pending" || status === "in_progress";
  if (inFlight && currentStage === stageKey) return "active";
  return "pending";
}

function Icon({ state }: { state: StageState }) {
  if (state === "done") return <span className="stage-icon done">✓</span>;
  if (state === "failed") return <span className="stage-icon failed">✕</span>;
  if (state === "active") return <span className="stage-icon active spinner" />;
  return <span className="stage-icon pending" />;
}

export default function GenerationStatus({
  status,
  currentStage,
  stageHistory,
}: Props) {
  const completed = new Set(
    stageHistory.filter((e) => e.state === "completed").map((e) => e.stage),
  );
  const failedEvent = stageHistory.find((e) => e.state === "failed");
  const failedStage = failedEvent ? failedEvent.stage : null;

  // The most recent detail per stage, for the small subtitle line.
  const lastDetail = new Map<string, string>();
  for (const e of stageHistory) {
    if (e.detail) lastDetail.set(e.stage, e.detail);
  }

  return (
    <ol className="stage-list">
      {PIPELINE_STAGES.map((stage) => {
        const state = buildState(
          stage.key,
          completed,
          failedStage,
          currentStage,
          status,
        );
        const detail = lastDetail.get(stage.key);
        return (
          <li key={stage.key} className={`stage stage-${state}`}>
            <Icon state={state} />
            <div className="stage-text">
              <span className="stage-label">{stage.label}</span>
              {detail && <span className="stage-detail">{detail}</span>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
