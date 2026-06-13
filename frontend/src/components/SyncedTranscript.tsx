import { useEffect, useMemo, useRef, useState } from "react";
import type { TranscriptCue } from "../types";
import { formatDuration } from "../util";

interface Props {
  src: string;
  title: string;
  cues: TranscriptCue[];
  durationSeconds?: number | null;
}

/**
 * Karaoke-style transcript: highlights the cue at the audio cursor, auto-scrolls
 * it into view, and seeks playback when a cue is clicked.
 */
export default function SyncedTranscript({
  src,
  title,
  cues,
  durationSeconds,
}: Props) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const cueRefs = useRef<Record<number, HTMLElement | null>>({});
  const [activeIndex, setActiveIndex] = useState(-1);
  const [autoScroll, setAutoScroll] = useState(true);

  // Cues arrive in non-decreasing start order; binary-search the last cue whose
  // start is <= the cursor so the highlight persists through inter-cue gaps.
  const updateActive = (t: number) => {
    let lo = 0;
    let hi = cues.length - 1;
    let idx = -1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (cues[mid].start <= t + 1e-3) {
        idx = mid;
        lo = mid + 1;
      } else {
        hi = mid - 1;
      }
    }
    setActiveIndex((prev) => (prev === idx ? prev : idx));
  };

  // Center the active cue within the scroll container (not the whole page).
  useEffect(() => {
    if (!autoScroll || activeIndex < 0) return;
    const el = cueRefs.current[activeIndex];
    const container = scrollRef.current;
    if (!el || !container) return;
    const top = el.offsetTop - container.clientHeight / 2 + el.clientHeight / 2;
    container.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
  }, [activeIndex, autoScroll]);

  const seek = (cue: TranscriptCue) => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = cue.start + 0.001;
    setActiveIndex(cue.index);
    void audio.play().catch(() => {});
  };

  const groups = useMemo(() => {
    const intro = cues.filter((c) => c.phase === "intro");
    const playback = cues.filter((c) => c.phase === "playback");
    const breakdownIntro = cues.filter((c) => c.kind === "breakdown_intro");
    const byGroup = new Map<number, TranscriptCue[]>();
    for (const c of cues) {
      if (c.phase !== "breakdown" || c.kind === "breakdown_intro") continue;
      const g = c.group ?? -1;
      if (!byGroup.has(g)) byGroup.set(g, []);
      byGroup.get(g)!.push(c);
    }
    return { intro, playback, breakdownIntro, byGroup };
  }, [cues]);

  const renderCue = (c: TranscriptCue, trailingSpace = false) => (
    <span
      key={c.index}
      ref={(el) => {
        cueRefs.current[c.index] = el;
      }}
      className={
        "cue" +
        (c.lang === "target" ? " cue-target" : " cue-native") +
        (c.index === activeIndex ? " cue-active" : "")
      }
      onClick={() => seek(c)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          seek(c);
        }
      }}
      title="Jump to this point"
    >
      {c.text}
      {trailingSpace ? " " : ""}
    </span>
  );

  return (
    <div className="synced-transcript">
      <div className="audio-player-head">
        <div>
          <div className="audio-title">{title}</div>
          <div className="audio-sub">
            Duration {formatDuration(durationSeconds)} · tap any line to jump
          </div>
        </div>
        <div className="transcript-tools">
          <label className="autoscroll-toggle">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
            />
            Auto-scroll
          </label>
          <a className="btn btn-ghost" href={src} download>
            Download
          </a>
        </div>
      </div>

      <audio
        ref={audioRef}
        controls
        preload="metadata"
        src={src}
        style={{ width: "100%" }}
        onTimeUpdate={(e) => updateActive(e.currentTarget.currentTime)}
        onSeeked={(e) => updateActive(e.currentTarget.currentTime)}
      >
        Your browser does not support the audio element.
      </audio>

      <div className="transcript-scroll" ref={scrollRef}>
        {groups.intro.length > 0 && (
          <p className="transcript-line">
            {groups.intro.map((c) => renderCue(c))}
          </p>
        )}

        {groups.playback.length > 0 && (
          <>
            <h3 className="subsection-title">Full reading · target language</h3>
            <p className="transcript-line full-reading">
              {groups.playback.map((c) => renderCue(c, true))}
            </p>
          </>
        )}

        {groups.breakdownIntro.map((c) => (
          <p key={c.index} className="transcript-line transcript-cue-line">
            {renderCue(c)}
          </p>
        ))}

        {groups.byGroup.size > 0 && (
          <>
            <h3 className="subsection-title">Section-by-section breakdown</h3>
            {[...groups.byGroup.entries()].map(([g, items]) => {
              const target = items.filter((c) => c.kind === "segment");
              const explanation = items.filter((c) => c.kind === "explanation");
              return (
                <div key={g} className="transcript-segment">
                  <p className="transcript-line segment-target">
                    {target.map((c) => renderCue(c, true))}
                  </p>
                  {explanation.length > 0 && (
                    <p className="transcript-line segment-native">
                      💬 {explanation.map((c) => renderCue(c, true))}
                    </p>
                  )}
                </div>
              );
            })}
          </>
        )}
      </div>
    </div>
  );
}
