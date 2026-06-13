import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Meta } from "../types";

const FALLBACK_LANGUAGES = ["English", "Spanish", "French", "German", "Italian"];
const FALLBACK_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"];
const FALLBACK_DURATIONS = [5, 10, 20, 30];

export default function CreatePage() {
  const navigate = useNavigate();
  const [meta, setMeta] = useState<Meta | null>(null);

  const [nativeLanguage, setNativeLanguage] = useState("English");
  const [targetLanguage, setTargetLanguage] = useState("Spanish");
  const [cefrLevel, setCefrLevel] = useState("A2");
  const [durationMinutes, setDurationMinutes] = useState(10);
  const [tone, setTone] = useState("auto");
  const [topicCategory, setTopicCategory] = useState("");
  const [topicDescription, setTopicDescription] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.meta().then(setMeta).catch(() => setMeta(null));
  }, []);

  const languages = meta?.languages ?? FALLBACK_LANGUAGES;
  const levels = meta?.cefr_levels ?? FALLBACK_LEVELS;
  const durations = meta?.durations ?? FALLBACK_DURATIONS;
  const tones = meta?.tones ?? [
    { value: "auto", label: "Auto", description: "Match the tone to the topic." },
  ];
  const categories = meta?.topic_categories ?? [];
  const mockProviders = meta
    ? (["llm", "search", "tts"] as const).filter((k) => meta.providers[k] === "mock")
    : [];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!topicDescription.trim()) {
      setError("Please describe the topic you want a podcast about.");
      return;
    }
    if (nativeLanguage === targetLanguage) {
      setError("Native and target languages must be different.");
      return;
    }

    setSubmitting(true);
    try {
      const created = await api.create({
        native_language: nativeLanguage,
        target_language: targetLanguage,
        cefr_level: cefrLevel,
        topic_category: topicCategory || null,
        topic_description: topicDescription.trim(),
        duration_minutes: durationMinutes,
        tone,
      });
      navigate(`/podcasts/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  };

  return (
    <div className="page-narrow">
      <h1 className="page-title">Create a new podcast</h1>
      <p className="page-sub">
        Beshno researches your topic and builds a two-voice podcast calibrated to
        your level — the learner speaks the target language, the teacher explains
        in your native language.
      </p>

      {mockProviders.length > 0 && (
        <div className="alert alert-warn">
          ⚠️ Running in <strong>mock mode</strong> for: {mockProviders.join(", ")}.
          {meta?.providers.tts === "mock" && " Generated audio will be silent."}
          {meta?.providers.llm === "mock" && " Scripts will be placeholder text."}{" "}
          Set the API keys on the backend (and restart it) to enable real providers.
        </div>
      )}

      <form className="card form" onSubmit={handleSubmit}>
        <div className="field-row">
          <label className="field">
            <span className="field-label">I speak (native)</span>
            <select
              value={nativeLanguage}
              onChange={(e) => setNativeLanguage(e.target.value)}
            >
              {languages.map((l) => (
                <option key={l} value={l}>
                  {l}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span className="field-label">I'm learning (target)</span>
            <select
              value={targetLanguage}
              onChange={(e) => setTargetLanguage(e.target.value)}
            >
              {languages.map((l) => (
                <option key={l} value={l}>
                  {l}
                </option>
              ))}
            </select>
          </label>

          <label className="field field-narrow">
            <span className="field-label">My level</span>
            <select
              value={cefrLevel}
              onChange={(e) => setCefrLevel(e.target.value)}
            >
              {levels.map((lvl) => (
                <option key={lvl} value={lvl}>
                  {lvl}
                </option>
              ))}
            </select>
          </label>
        </div>

        <fieldset className="field duration-field">
          <span className="field-label">Episode length</span>
          <div className="duration-options" role="radiogroup" aria-label="Episode length">
            {durations.map((d) => (
              <button
                key={d}
                type="button"
                role="radio"
                aria-checked={durationMinutes === d}
                className={
                  "duration-option" +
                  (durationMinutes === d ? " duration-option-active" : "")
                }
                onClick={() => setDurationMinutes(d)}
              >
                {d} min
              </button>
            ))}
          </div>
        </fieldset>

        <label className="field">
          <span className="field-label">Tone</span>
          <select value={tone} onChange={(e) => setTone(e.target.value)}>
            {tones.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
          <span className="provider-hint">
            {tones.find((t) => t.value === tone)?.description}
          </span>
        </label>

        <label className="field">
          <span className="field-label">Topic category (optional)</span>
          <select
            value={topicCategory}
            onChange={(e) => setTopicCategory(e.target.value)}
          >
            <option value="">— None / custom —</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span className="field-label">What should the podcast be about?</span>
          <textarea
            rows={4}
            placeholder="e.g. How volcanoes form, the history of jazz, everyday small talk at a café…"
            value={topicDescription}
            onChange={(e) => setTopicDescription(e.target.value)}
          />
        </label>

        {error && <div className="alert alert-error">{error}</div>}

        <div className="form-actions">
          <button className="btn btn-primary" type="submit" disabled={submitting}>
            {submitting ? "Starting…" : "Generate podcast"}
          </button>
          {meta && (
            <span className="provider-hint">
              engine: {meta.providers.llm} · search: {meta.providers.search} ·
              voice: {meta.providers.tts}
            </span>
          )}
        </div>
      </form>
    </div>
  );
}
