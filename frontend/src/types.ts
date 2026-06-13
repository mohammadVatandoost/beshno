// Mirrors the backend Pydantic schemas.

export type PodcastStatus =
  | "pending"
  | "in_progress"
  | "ready"
  | "needs_review"
  | "failed";

export interface StageEvent {
  stage: string;
  label: string;
  state: "started" | "completed" | "failed";
  at: string;
  detail?: string | null;
}

export interface Source {
  title: string;
  url: string;
  relevance_score: number;
  reason: string;
}

export interface KeyVocab {
  term: string;
  meaning: string;
}

export interface AdaptedContent {
  title: string;
  adapted_text: string;
  key_points: string[];
  key_vocabulary: KeyVocab[];
}

export interface ExplanationRun {
  lang: "native" | "target";
  text: string;
}

export interface ContentSegment {
  target_text: string;
  native_explanation: ExplanationRun[];
}

export interface PodcastScript {
  title: string;
  intro: string;
  breakdown_intro: string;
  segments: ContentSegment[];
}

export type CueKind =
  | "intro"
  | "full"
  | "breakdown_intro"
  | "segment"
  | "explanation";

export type CuePhase = "intro" | "playback" | "breakdown";

export interface TranscriptCue {
  index: number;
  kind: CueKind;
  phase: CuePhase;
  group?: number | null;
  lang: "target" | "native";
  text: string;
  start: number;
  end: number;
}

export interface EvaluationScores {
  cefr_compliance: number;
  language_balance: number;
  pedagogical_quality: number;
  factual_accuracy: number;
  engagement_flow: number;
}

export interface Evaluation {
  iteration: number;
  passed: boolean;
  scores: EvaluationScores;
  overall_score: number;
  feedback: string;
  revision_target?: string | null;
  issues: string[];
  created_at: string;
}

export interface ExerciseSet {
  speaking: { prompt: string };
  vocabulary: { term: string; question: string }[];
  reading: { question: string; options: string[] }[];
}

export interface ExerciseSubmission {
  speaking_answer: string;
  vocabulary_answers: string[];
  reading_answers: number[];
}

export interface ExerciseItemResult {
  label: string;
  correct?: boolean | null;
  feedback: string;
}

export interface ExerciseGrade {
  score: number;
  feedback: string;
  items: ExerciseItemResult[];
  reading_correct_index: number[];
  vocabulary_reference: string[];
}

export interface PodcastSummary {
  id: string;
  created_at: string;
  updated_at: string;
  native_language: string;
  target_language: string;
  cefr_level: string;
  topic_category?: string | null;
  topic_description: string;
  duration_minutes: number;
  title?: string | null;
  status: PodcastStatus;
  current_stage: string;
  audio_duration_seconds?: number | null;
}

export interface PodcastDetail extends PodcastSummary {
  error_message?: string | null;
  revision_count: number;
  stage_history: StageEvent[];
  selected_sources?: Source[] | null;
  adapted_content?: AdaptedContent | null;
  script?: PodcastScript | null;
  transcript?: TranscriptCue[] | null;
  evaluations: Evaluation[];
  exercises?: ExerciseSet | null;
  audio_format: string;
  has_audio: boolean;
  has_exercises: boolean;
}

export interface Providers {
  llm: string;
  search: string;
  tts: string;
}

export interface Meta {
  topic_categories: string[];
  languages: string[];
  cefr_levels: string[];
  durations: number[];
  providers: Providers;
  max_revisions: number;
}

export interface CreatePayload {
  native_language: string;
  target_language: string;
  cefr_level: string;
  topic_category?: string | null;
  topic_description: string;
  duration_minutes: number;
}

export const TERMINAL_STATUSES: PodcastStatus[] = [
  "ready",
  "needs_review",
  "failed",
];

// Ordered pipeline stages surfaced in the progress tracker.
export const PIPELINE_STAGES: { key: string; label: string }[] = [
  { key: "researching", label: "Researching topic" },
  { key: "filtering", label: "Selecting sources" },
  { key: "adapting", label: "Adapting content" },
  { key: "scripting", label: "Writing script" },
  { key: "evaluating", label: "Reviewing quality" },
  { key: "generating_audio", label: "Generating audio" },
  { key: "exercises", label: "Creating exercises" },
];
