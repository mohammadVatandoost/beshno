import type { PodcastStatus } from "./types";

export function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function formatDuration(seconds?: number | null): string {
  if (!seconds || seconds <= 0) return "—";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

const STATUS_LABELS: Record<PodcastStatus, string> = {
  pending: "Queued",
  in_progress: "In progress",
  ready: "Ready",
  needs_review: "Needs review",
  failed: "Failed",
};

export function statusLabel(status: PodcastStatus): string {
  return STATUS_LABELS[status] ?? status;
}
