import type { PodcastScript } from "../types";

export default function ScriptView({ script }: { script: PodcastScript }) {
  // Guard against older podcasts saved before the two-phase format.
  const segments = script.segments ?? [];
  const fullText = segments.map((s) => s.target_text).join(" ");

  return (
    <div className="script">
      {script.intro && <p className="script-cue">{script.intro}</p>}

      <h3 className="subsection-title">Full reading · target language</h3>
      <div className="full-reading">{fullText}</div>

      {script.breakdown_intro && (
        <p className="script-cue">{script.breakdown_intro}</p>
      )}

      <h3 className="subsection-title">Section-by-section breakdown</h3>
      <div className="breakdown">
        {segments.map((seg, i) => {
          const runs = Array.isArray(seg.native_explanation)
            ? seg.native_explanation
            : [];
          return (
            <div key={i} className="segment">
              <p className="segment-target">{seg.target_text}</p>
              <p className="segment-native">
                💬{" "}
                {runs.map((run, j) => (
                  <span
                    key={j}
                    className={run.lang === "target" ? "run-target" : undefined}
                  >
                    {run.text}{" "}
                  </span>
                ))}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
