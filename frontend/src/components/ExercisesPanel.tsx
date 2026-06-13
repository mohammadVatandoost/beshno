import { useState } from "react";
import { api } from "../api/client";
import type { ExerciseGrade, ExerciseSet } from "../types";

interface Props {
  podcastId: string;
  exercises: ExerciseSet;
}

export default function ExercisesPanel({ podcastId, exercises }: Props) {
  const [speaking, setSpeaking] = useState("");
  const [vocab, setVocab] = useState<string[]>(
    exercises.vocabulary.map(() => ""),
  );
  const [reading, setReading] = useState<(number | null)[]>(
    exercises.reading.map(() => null),
  );
  const [result, setResult] = useState<ExerciseGrade | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const setVocabAt = (i: number, v: string) =>
    setVocab((prev) => prev.map((x, j) => (j === i ? v : x)));
  const setReadingAt = (i: number, v: number) =>
    setReading((prev) => prev.map((x, j) => (j === i ? v : x)));

  const handleSubmit = async () => {
    setError(null);
    setSubmitting(true);
    try {
      const grade = await api.submitExercises(podcastId, {
        speaking_answer: speaking,
        vocabulary_answers: vocab,
        reading_answers: reading.map((r) => (r === null ? -1 : r)),
      });
      setResult(grade);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  // Optional speech-to-text for the speaking exercise (Chrome/Safari).
  const speechCtor =
    typeof window !== "undefined"
      ? // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
      : undefined;
  const recognize = () => {
    if (!speechCtor) return;
    const r = new speechCtor();
    r.continuous = false;
    r.interimResults = false;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    r.onresult = (ev: any) => {
      const text = ev?.results?.[0]?.[0]?.transcript ?? "";
      setSpeaking((prev) => (prev ? `${prev} ${text}` : text));
    };
    r.start();
  };

  const locked = result !== null;

  return (
    <div className="exercises">
      {/* Speaking */}
      <div className="exercise">
        <div className="exercise-tag">Speaking</div>
        <p className="exercise-q">{exercises.speaking.prompt}</p>
        <textarea
          rows={3}
          placeholder="Type — or dictate — your spoken answer…"
          value={speaking}
          onChange={(e) => setSpeaking(e.target.value)}
          disabled={locked}
        />
        {speechCtor && !locked && (
          <button type="button" className="btn btn-ghost" onClick={recognize}>
            🎤 Speak
          </button>
        )}
      </div>

      {/* Vocabulary */}
      {exercises.vocabulary.map((v, i) => (
        <div className="exercise" key={`v${i}`}>
          <div className="exercise-tag">Vocabulary {i + 1}</div>
          <p className="exercise-q">
            {v.question} <strong className="run-target">{v.term}</strong>
          </p>
          <input
            type="text"
            placeholder="Your answer…"
            value={vocab[i] ?? ""}
            onChange={(e) => setVocabAt(i, e.target.value)}
            disabled={locked}
          />
          {result && (
            <p className="exercise-reveal">Meaning: {result.vocabulary_reference[i]}</p>
          )}
        </div>
      ))}

      {/* Reading multiple-choice */}
      {exercises.reading.map((r, i) => (
        <div className="exercise" key={`r${i}`}>
          <div className="exercise-tag">Reading {i + 1}</div>
          <p className="exercise-q">{r.question}</p>
          <div className="options">
            {r.options.map((opt, oi) => {
              const isCorrect = result != null && result.reading_correct_index[i] === oi;
              const isChosen = reading[i] === oi;
              return (
                <label
                  key={oi}
                  className={
                    "option" +
                    (isCorrect ? " option-correct" : "") +
                    (result && isChosen && !isCorrect ? " option-wrong" : "")
                  }
                >
                  <input
                    type="radio"
                    name={`reading-${i}`}
                    checked={isChosen}
                    onChange={() => setReadingAt(i, oi)}
                    disabled={locked}
                  />
                  {opt}
                </label>
              );
            })}
          </div>
        </div>
      ))}

      {error && <div className="alert alert-error">{error}</div>}

      {!result ? (
        <button className="btn btn-primary" onClick={handleSubmit} disabled={submitting}>
          {submitting ? "Grading…" : "Submit answers"}
        </button>
      ) : (
        <div className="grade">
          <div className="grade-head">
            <div className="grade-score">
              {result.score}
              <span>/10</span>
            </div>
            <button
              className="btn btn-ghost"
              onClick={() => {
                setResult(null);
                setError(null);
              }}
            >
              Try again
            </button>
          </div>
          <p className="grade-feedback">{result.feedback}</p>
          <ul className="grade-items">
            {result.items.map((it, i) => (
              <li key={i} className="grade-item">
                <span
                  className={
                    "grade-mark " +
                    (it.correct === true
                      ? "ok"
                      : it.correct === false
                        ? "bad"
                        : "neutral")
                  }
                >
                  {it.correct === true ? "✓" : it.correct === false ? "✕" : "•"}
                </span>
                <span>
                  <strong>{it.label}:</strong> {it.feedback}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
