import type { PodcastStatus } from "../types";
import { statusLabel } from "../util";

export default function StatusBadge({ status }: { status: PodcastStatus }) {
  return <span className={`badge badge-${status}`}>{statusLabel(status)}</span>;
}
