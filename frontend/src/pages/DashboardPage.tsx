import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import StatusBadge from "../components/StatusBadge";
import type { PodcastSummary } from "../types";
import { formatDate, formatDuration } from "../util";

export default function DashboardPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<PodcastSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    api
      .list()
      .then((list) => active && setItems(list))
      .catch((e) => active && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="page-title">Your podcasts</h1>
          <p className="page-sub">
            Every podcast you've generated, newest first.
          </p>
        </div>
        <Link to="/create" className="btn btn-primary">
          + New podcast
        </Link>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {!items && !error && <div className="muted">Loading…</div>}

      {items && items.length === 0 && (
        <div className="card empty-state">
          <div className="empty-emoji">🎧</div>
          <h2>No podcasts yet</h2>
          <p className="muted">
            Create your first personalised language-learning podcast.
          </p>
          <Link to="/create" className="btn btn-primary">
            Create a podcast
          </Link>
        </div>
      )}

      {items && items.length > 0 && (
        <div className="card table-card">
          <table className="table">
            <thead>
              <tr>
                <th>Topic</th>
                <th>Languages</th>
                <th>Level</th>
                <th>Created</th>
                <th>Length</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {items.map((p) => (
                <tr
                  key={p.id}
                  className="row-link"
                  onClick={() => navigate(`/podcasts/${p.id}`)}
                >
                  <td>
                    <div className="cell-title">{p.title || p.topic_description}</div>
                    {p.topic_category && (
                      <div className="cell-sub">{p.topic_category}</div>
                    )}
                  </td>
                  <td>
                    <span className="lang-pair">
                      {p.target_language}
                      <span className="arrow"> ← </span>
                      {p.native_language}
                    </span>
                  </td>
                  <td>
                    <span className="level-chip">{p.cefr_level}</span>
                  </td>
                  <td className="muted">{formatDate(p.created_at)}</td>
                  <td className="muted">
                    {formatDuration(p.audio_duration_seconds)}
                  </td>
                  <td>
                    <StatusBadge status={p.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
