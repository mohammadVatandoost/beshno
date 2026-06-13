import type {
  CreatePayload,
  Meta,
  PodcastDetail,
  PodcastStatus,
  PodcastSummary,
} from "../types";

const BASE = import.meta.env.VITE_API_BASE ?? "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!resp.ok) {
    let message = `Request failed (${resp.status})`;
    try {
      const body = await resp.json();
      if (body?.detail) message = String(body.detail);
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new Error(message);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export interface PodcastStatusOut {
  id: string;
  status: PodcastStatus;
  current_stage: string;
  revision_count: number;
  error_message?: string | null;
  stage_history: PodcastDetail["stage_history"];
  has_audio: boolean;
}

export const api = {
  meta: () => request<Meta>("/meta"),
  list: () => request<PodcastSummary[]>("/podcasts"),
  get: (id: string) => request<PodcastDetail>(`/podcasts/${id}`),
  status: (id: string) => request<PodcastStatusOut>(`/podcasts/${id}/status`),
  create: (payload: CreatePayload) =>
    request<PodcastDetail>("/podcasts", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  remove: (id: string) =>
    request<void>(`/podcasts/${id}`, { method: "DELETE" }),
  audioUrl: (id: string) => `${BASE}/podcasts/${id}/audio`,
};
