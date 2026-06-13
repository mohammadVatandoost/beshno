import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import AudioPlayer from "../components/AudioPlayer";
import ExercisesPanel from "../components/ExercisesPanel";
import GenerationStatus from "../components/GenerationStatus";
import ScriptView from "../components/ScriptView";
import SyncedTranscript from "../components/SyncedTranscript";
import StatusBadge from "../components/StatusBadge";
import { usePodcast } from "../hooks/usePodcast";
import type { Evaluation } from "../types";
import { formatDate } from "../util";

const SCORE_LABELS: Record<string, string> = {
  cefr_compliance: "CEFR fit",
  language_balance: "Language balance",
  pedagogical_quality: "Teaching quality",
  factual_accuracy: "Factual accuracy",
  engagement_flow: "Engagement & flow",
};

function ScoreBars({ evaluation }: { evaluation: Evaluation }) {
  const entries = Object.entries(evaluation.scores) as [string, number][];
  return (
    <div className="scores">
      {entries.map(([key, value]) => (
        <div className="score-row" key={key}>
          <span className="score-name">{SCORE_LABELS[key] ?? key}</span>
          <span className="score-bar">
            <span
              className="score-fill"
              style={{ width: `${(value / 5) * 100}%` }}
            />
          </span>
          <span className="score-value">{value.toFixed(1)}</span>
        </div>
      ))}
    </div>
  );
}

export default function DetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data, error, loading } = usePodcast(id);

  if (loading && !data) {
    return <div className="page muted">Loading…</div>;
  }
  if (error && !data) {
    return (
      <div className="page">
        <div className="alert alert-error">{error}</div>
        <Link to="/" className="btn btn-ghost">
          ← Back to dashboard
        </Link>
      </div>
    );
  }
  if (!data) return null;

  const p = data;
  const generating = p.status === "pending" || p.status === "in_progress";
  const finished = p.status === "ready" || p.status === "needs_review";
  const latestEval =
    p.evaluations.length > 0 ? p.evaluations[p.evaluations.length - 1] : null;

  const handleDelete = async () => {
    if (!id) return;
    if (!window.confirm("Delete this podcast? This cannot be undone.")) return;
    try {
      await api.remove(id);
      navigate("/");
    } catch (e) {
      window.alert(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="page">
      <Link to="/" className="back-link">
        ← Dashboard
      </Link>

      <div className="detail-head">
        <div>
          <h1 className="page-title">{p.title || p.topic_description}</h1>
          <div className="chips">
            <span className="chip chip-strong">
              {p.target_language} <span className="arrow">←</span>{" "}
              {p.native_language}
            </span>
            <span className="chip">Level {p.cefr_level}</span>
            {["B2", "C1", "C2"].includes(p.cefr_level) && (
              <span className="chip">🎯 Immersion · target language only</span>
            )}
            {p.topic_category && <span className="chip">{p.topic_category}</span>}
            <StatusBadge status={p.status} />
            <span className="chip-muted">Created {formatDate(p.created_at)}</span>
          </div>
        </div>
        <button className="btn btn-ghost danger" onClick={handleDelete}>
          Delete
        </button>
      </div>

      {p.topic_description && p.title && (
        <p className="topic-line">Topic: {p.topic_description}</p>
      )}

      {/* Progress / failure */}
      {(generating || p.status === "failed") && (
        <section className="card">
          <h2 className="section-title">
            {generating ? "Generating your podcast…" : "Generation failed"}
          </h2>
          {generating && (
            <p className="muted">
              This usually takes a minute or two. The page updates automatically.
            </p>
          )}
          {p.status === "failed" && p.error_message && (
            <div className="alert alert-error">{p.error_message}</div>
          )}
          <GenerationStatus
            status={p.status}
            currentStage={p.current_stage}
            stageHistory={p.stage_history}
          />
        </section>
      )}

      {p.status === "needs_review" && (
        <div className="alert alert-warn">
          This podcast passed generation but the evaluator flagged it for review
          after {p.revision_count} revision
          {p.revision_count === 1 ? "" : "s"}. Listen and check the quality notes
          below.
        </div>
      )}

      {/* Audio + synced transcript (karaoke). Falls back to a plain player and
          static transcript for podcasts generated before timed cues existed. */}
      {finished && p.has_audio && id && p.transcript && p.transcript.length > 0 ? (
        <section className="card">
          <h2 className="section-title">Listen & follow along</h2>
          <SyncedTranscript
            src={api.audioUrl(id)}
            title={p.title || p.topic_description}
            cues={p.transcript}
            durationSeconds={p.audio_duration_seconds}
          />
        </section>
      ) : (
        <>
          {finished && p.has_audio && id && (
            <section className="card">
              <AudioPlayer
                src={api.audioUrl(id)}
                title={p.title || p.topic_description}
                durationSeconds={p.audio_duration_seconds}
              />
            </section>
          )}
          {finished && p.script && (
            <section className="card">
              <h2 className="section-title">Transcript</h2>
              <ScriptView script={p.script} />
            </section>
          )}
        </>
      )}

      {/* Interactive exercises */}
      {finished && p.exercises && id && (
        <section className="card">
          <h2 className="section-title">Practice exercises</h2>
          <p className="muted small">
            Answer all five, then submit for a score out of 10 and teacher feedback.
          </p>
          <ExercisesPanel podcastId={id} exercises={p.exercises} />
        </section>
      )}

      {/* Adapted content */}
      {finished && p.adapted_content && (
        <section className="card">
          <h2 className="section-title">Adapted summary</h2>
          <p className="adapted-text">{p.adapted_content.adapted_text}</p>

          {p.adapted_content.key_points.length > 0 && (
            <>
              <h3 className="subsection-title">Key points</h3>
              <ul className="bullet-list">
                {p.adapted_content.key_points.map((pt, i) => (
                  <li key={i}>{pt}</li>
                ))}
              </ul>
            </>
          )}

          {p.adapted_content.key_vocabulary.length > 0 && (
            <>
              <h3 className="subsection-title">Key vocabulary</h3>
              <dl className="vocab-list">
                {p.adapted_content.key_vocabulary.map((v, i) => (
                  <div className="vocab-item" key={i}>
                    <dt>{v.term}</dt>
                    <dd>{v.meaning}</dd>
                  </div>
                ))}
              </dl>
            </>
          )}
        </section>
      )}

      {/* Sources */}
      {finished && p.selected_sources && p.selected_sources.length > 0 && (
        <section className="card">
          <h2 className="section-title">Sources</h2>
          <ul className="source-list">
            {p.selected_sources.map((s, i) => (
              <li key={i}>
                <a href={s.url} target="_blank" rel="noreferrer">
                  {s.title}
                </a>
                <span className="source-score">
                  {(s.relevance_score * 100).toFixed(0)}% relevant
                </span>
                <div className="source-reason">{s.reason}</div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Quality review */}
      {finished && latestEval && (
        <section className="card">
          <h2 className="section-title">
            Quality review
            <span
              className={`eval-verdict ${latestEval.passed ? "pass" : "fail"}`}
            >
              {latestEval.passed ? "Passed" : "Flagged"} ·{" "}
              {latestEval.overall_score.toFixed(1)}/5
            </span>
          </h2>
          <ScoreBars evaluation={latestEval} />
          {latestEval.feedback && (
            <p className="eval-feedback">{latestEval.feedback}</p>
          )}
          {latestEval.issues.length > 0 && (
            <ul className="bullet-list">
              {latestEval.issues.map((iss, i) => (
                <li key={i}>{iss}</li>
              ))}
            </ul>
          )}
          {p.evaluations.length > 1 && (
            <p className="muted small">
              {p.evaluations.length} evaluation rounds were run.
            </p>
          )}
        </section>
      )}
    </div>
  );
}
