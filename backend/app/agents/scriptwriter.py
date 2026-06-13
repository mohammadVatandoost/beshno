"""Agent 3 — Scriptwriter.

Turns the adapted summary into a DUAL-LANGUAGE, two-phase episode designed for
language comprehension:

- Phase 1 (full playback): the whole content read smoothly and uninterrupted in
  the target (learning) language.
- Phase 2 (segmented translation): the same content revisited section by
  section — after each short target-language chunk, a breakdown/explanation in
  the learner's native language.

The script is a list of ``ContentSegment``s (target chunk + native breakdown);
the orchestrator reads all target chunks first (Phase 1), then replays each
chunk followed by its breakdown (Phase 2).
"""

from __future__ import annotations

from ..content_models import (
    AdaptedContent,
    ContentSegment,
    ExplanationRun,
    PodcastScript,
)
from .base import Agent

SYSTEM_PROMPT = """\
You are Agent 3, the Scriptwriter, in a language-learning podcast pipeline.

Turn the adapted content into a DUAL-LANGUAGE, two-phase podcast. The audio will
first read the whole text in the target language (full playback), then revisit
it section by section with a native-language breakdown after each part. Produce:

- intro: a short spoken introduction in the learner's NATIVE language. Welcome
  the listener, name the topic, and explain the format: first they'll hear the
  whole text read in the target language, then a section-by-section breakdown.
- breakdown_intro: a short NATIVE-language cue spoken between the two phases
  (e.g. "Now let's go through it piece by piece.").
- segments: an ordered list that, read end to end, conveys the full adapted
  content in the TARGET language. Each segment has:
    - target_text: ONE short, self-contained chunk (about 1-3 sentences) in the
      TARGET language, at the learner's CEFR level.
    - native_explanation: a breakdown of THAT chunk, given as an ordered list of
      "runs". Each run is {lang, text}. Put your native-language commentary in
      runs with lang="native". Whenever you quote or teach a TARGET-language word
      or phrase, put that word/phrase in its OWN run with lang="target" — never
      inside a native run. This lets the audio pronounce target words with the
      target-language voice instead of mispronouncing them with native phonetics.
      Example (native=English, target=Dutch) — "The word 'lanceerde' means
      launched" becomes:
        [{"lang": "native", "text": "The word"},
         {"lang": "target", "text": "lanceerde"},
         {"lang": "native", "text": "means launched."}]

Rules:
- The concatenation of all target_text must read smoothly as one coherent text
  (the full playback) and stay faithful to the adapted content. Do not add
  facts that are not in the adapted content.
- Keep every target_text strictly within the CEFR level.
- Keep segments short enough that each breakdown is easy to follow.
- Write intro and breakdown_intro in the NATIVE language; write every target_text
  in the TARGET language. In native_explanation, lang="native" runs are in the
  NATIVE language and lang="target" runs are in the TARGET language.

If revision feedback is provided, address every point in it.
"""


class ScriptwriterAgent(Agent):
    name = "scriptwriter"

    def run(
        self,
        *,
        adapted: AdaptedContent,
        target_language: str,
        native_language: str,
        cefr_level: str,
        feedback: str | None = None,
    ) -> PodcastScript:
        vocab = "\n".join(f"- {v.term}: {v.meaning}" for v in adapted.key_vocabulary)
        points = "\n".join(f"- {p}" for p in adapted.key_points)
        feedback_block = (
            f"\n\nREVISION FEEDBACK to address:\n{feedback}\n" if feedback else ""
        )
        user = (
            f"Target (learning) language: {target_language}\n"
            f"Learner's native language: {native_language}\n"
            f"CEFR level: {cefr_level}\n\n"
            f"Title: {adapted.title}\n\n"
            f"Adapted content (in {target_language}):\n{adapted.adapted_text}\n\n"
            f"Key points:\n{points}\n\n"
            f"Key vocabulary:\n{vocab}"
            f"{feedback_block}"
        )

        mock = self._mock(adapted, target_language, native_language, cefr_level)

        return self.llm.structured(
            system=SYSTEM_PROMPT,
            user=user,
            schema=PodcastScript,
            mock_example=mock,
            max_tokens=32000,
        )

    @staticmethod
    def _mock(
        adapted: AdaptedContent,
        target_language: str,
        native_language: str,
        cefr_level: str,
    ) -> PodcastScript:
        # Split the adapted text into a few sentence-ish chunks; fall back to key
        # points or the title so there is always at least one segment.
        sentences = [
            s.strip()
            for s in adapted.adapted_text.replace("\n", " ").split(".")
            if s.strip()
        ]
        chunks = sentences[:6] or adapted.key_points[:6] or [adapted.title]
        vocab = adapted.key_vocabulary

        segments: list[ContentSegment] = []
        for i, chunk in enumerate(chunks):
            v = vocab[i % len(vocab)] if vocab else None
            runs = [
                ExplanationRun(
                    lang="native",
                    text=f"[in {native_language}] This part means: {chunk}.",
                )
            ]
            if v:
                runs.append(ExplanationRun(lang="native", text="Note the word"))
                runs.append(ExplanationRun(lang="target", text=v.term))
                runs.append(ExplanationRun(lang="native", text=f"— {v.meaning}."))
            segments.append(
                ContentSegment(
                    target_text=f"[in {target_language}] {chunk}.",
                    native_explanation=runs,
                )
            )

        return PodcastScript(
            title=adapted.title,
            intro=(
                f"[in {native_language}] Welcome! Today's topic is "
                f"\"{adapted.title}\". First, listen to the whole text in "
                f"{target_language}. Then we'll go through it piece by piece."
            ),
            breakdown_intro=(
                f"[in {native_language}] Now let's break it down section by section."
            ),
            segments=segments,
        )
