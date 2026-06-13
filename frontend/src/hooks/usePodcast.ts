import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { PodcastDetail } from "../types";
import { TERMINAL_STATUSES } from "../types";

// How often to re-check a podcast's status while it is still generating.
const POLL_INTERVAL_MS = 5000;

/**
 * Fetch a podcast and poll it every 5s until it reaches a terminal status
 * (ready / needs_review / failed), then stop.
 */
export function usePodcast(id: string | undefined) {
  const [data, setData] = useState<PodcastDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const tick = async () => {
      try {
        const detail = await api.get(id);
        if (!active) return;
        setData(detail);
        setError(null);
        setLoading(false);
        if (!TERMINAL_STATUSES.includes(detail.status)) {
          timer = setTimeout(tick, POLL_INTERVAL_MS);
        }
      } catch (e) {
        if (!active) return;
        setError(e instanceof Error ? e.message : String(e));
        setLoading(false);
      }
    };

    setLoading(true);
    tick();
    return () => {
      active = false;
      if (timer) clearTimeout(timer);
    };
  }, [id]);

  return { data, error, loading };
}
