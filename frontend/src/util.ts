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

export function formatTokens(n?: number | null): string {
  return (n ?? 0).toLocaleString();
}

export function formatMillis(ms?: number | null): string {
  if (!ms || ms <= 0) return "—";
  if (ms < 1000) return `${ms} ms`;
  const totalSeconds = ms / 1000;
  if (totalSeconds < 60) return `${totalSeconds.toFixed(1)}s`;
  const m = Math.floor(totalSeconds / 60);
  const s = Math.round(totalSeconds % 60);
  return `${m}m ${s.toString().padStart(2, "0")}s`;
}

export function formatUsd(cost?: number | null): string {
  if (!cost || cost <= 0) return "$0.00";
  if (cost < 0.01) return "<$0.01";
  return `$${cost.toFixed(cost < 1 ? 3 : 2)}`;
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
