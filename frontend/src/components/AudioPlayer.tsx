import { formatDuration } from "../util";

interface Props {
  src: string;
  title: string;
  durationSeconds?: number | null;
}

export default function AudioPlayer({ src, title, durationSeconds }: Props) {
  return (
    <div className="audio-player">
      <div className="audio-player-head">
        <div>
          <div className="audio-title">{title}</div>
          <div className="audio-sub">Duration {formatDuration(durationSeconds)}</div>
        </div>
        <a className="btn btn-ghost" href={src} download>
          Download
        </a>
      </div>
      {/* Native controls provide play / pause / seek. */}
      <audio controls preload="metadata" src={src} style={{ width: "100%" }}>
        Your browser does not support the audio element.
      </audio>
    </div>
  );
}
