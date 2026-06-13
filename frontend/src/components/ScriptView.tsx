import type { PodcastScript } from "../types";

export default function ScriptView({ script }: { script: PodcastScript }) {
  return (
    <div className="script">
      {script.turns.map((turn, i) => (
        <div key={i} className={`turn turn-${turn.speaker}`}>
          <div className="turn-meta">
            <span className="turn-name">{turn.speaker_name}</span>
            <span className={`lang-tag lang-${turn.language}`}>
              {turn.language === "target" ? "target language" : "native language"}
            </span>
            <span className="turn-role">
              {turn.speaker === "learner" ? "learner" : "teacher"}
            </span>
          </div>
          <p className="turn-text">{turn.text}</p>
          {turn.note && <p className="turn-note">💡 {turn.note}</p>}
        </div>
      ))}
    </div>
  );
}
