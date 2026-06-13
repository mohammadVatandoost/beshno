"""Agent 3 — Scriptwriter.

Turns the adapted summary into a two-phase episode whose language strategy
adapts to the learner's CEFR level:

- A1 / A2 / B1 — DUAL-LANGUAGE. Phase 1 reads the whole content in the target
  language; Phase 2 revisits it chunk by chunk, each followed by a breakdown in
  the learner's NATIVE language.
- B2 / C1 / C2 — FULL IMMERSION. Everything (intro, cues, content and the
  deeper explanations) is 100% in the TARGET language; the native language is
  omitted entirely.

The script is a list of ``ContentSegment``s (target chunk + a breakdown made of
language-tagged ``ExplanationRun``s). In immersion mode every run is
``lang="target"``.
"""

from __future__ import annotations

from ..content_models import (
    AdaptedContent,
    ContentSegment,
    ExplanationRun,
    PodcastScript,
)
from ..enums import (
    DEFAULT_DURATION_MINUTES,
    duration_plan,
    is_immersion_level,
    tone_directive,
)
from .base import Agent

SYSTEM_PROMPT_DUAL = """\
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

SYSTEM_PROMPT_IMMERSION = """\
You are Agent 3, the Scriptwriter, in a language-learning podcast pipeline.

The learner is ADVANCED, so this episode is FULL IMMERSION: write and present
EVERYTHING 100% in the TARGET (learning) language. Do NOT use the learner's
native language anywhere. The audio first reads the whole text, then revisits it
section by section with a deeper explanation after each part — all in the target
language. Produce:

- intro: a short spoken introduction IN THE TARGET LANGUAGE. Welcome the
  listener, name the topic, and explain the format.
- breakdown_intro: a short TARGET-LANGUAGE cue spoken between the two phases.
- segments: an ordered list that, read end to end, conveys the full adapted
  content in the TARGET language. Each segment has:
    - target_text: ONE short, self-contained chunk (about 1-3 sentences) in the
      TARGET language, at the learner's CEFR level.
    - native_explanation: a DEEPER explanation of THAT chunk, written ENTIRELY in
      the TARGET language — rephrase it more simply, expand on nuance, define
      difficult words using easier target-language words, add relevant context.
      Give it as a list of runs; EVERY run MUST have lang="target". Never use the
      native language.

Rules:
- Everything — intro, breakdown_intro, target_text and every explanation run — is
  in the TARGET language. Do not use the native language at all.
- Every native_explanation run MUST be lang="target".
- Keep target_text within the CEFR level; explanations may use richer language
  appropriate for an advanced learner, but stay in the target language.
- The concatenation of all target_text must read smoothly and stay faithful to
  the adapted content.

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
        owner: str = "default",
        learned_vocab_mcp=None,
        duration_minutes: int = DEFAULT_DURATION_MINUTES,
        tone: str = "default",
    ) -> PodcastScript:
        immersion = is_immersion_level(cefr_level)
        plan = duration_plan(duration_minutes)
        vocab = "\n".join(f"- {v.term}: {v.meaning}" for v in adapted.key_vocabulary)
        points = "\n".join(f"- {p}" for p in adapted.key_points)
        feedback_block = (
            f"\n\nREVISION FEEDBACK to address:\n{feedback}\n" if feedback else ""
        )
        # Query the learned-vocabulary MCP server to avoid re-teaching words.
        avoid = self.fetch_avoid_terms(learned_vocab_mcp, owner, target_language)
        avoid_block = (
            "\n\nALREADY-TAUGHT WORDS — the learner already knows these; do NOT "
            "focus the breakdowns/explanations on them or re-teach them, prefer "
            "introducing fresh vocabulary:\n" + ", ".join(avoid) + "\n"
            if avoid
            else ""
        )
        mode_line = (
            f"Mode: FULL IMMERSION (level {cefr_level} is advanced) — everything "
            f"must be in {target_language}; do not use {native_language} at all."
            if immersion
            else f"Mode: DUAL-LANGUAGE (level {cefr_level}) — target content with "
            f"{native_language} breakdowns."
        )
        length_line = (
            f"Target runtime: ~{duration_minutes} minutes — produce about "
            f"{plan['segments']} segments covering the full adapted content. Do not "
            f"pad or invent material to fill time, and do not drop content to save "
            f"time; chunk the adapted text into roughly that many segments."
        )
        tone_line = (
            f"Tone — narrate in this style: {tone_directive(tone)} Apply the tone to "
            f"style only; keep within the CEFR level and the required format."
        )
        user = (
            f"Target (learning) language: {target_language}\n"
            f"Learner's native language: {native_language}\n"
            f"CEFR level: {cefr_level}\n"
            f"{mode_line}\n"
            f"{length_line}\n"
            f"{tone_line}\n\n"
            f"Title: {adapted.title}\n\n"
            f"Adapted content (in {target_language}):\n{adapted.adapted_text}\n\n"
            f"Key points:\n{points}\n\n"
            f"Key vocabulary:\n{vocab}"
            f"{feedback_block}"
            f"{avoid_block}"
        )

        system = SYSTEM_PROMPT_IMMERSION if immersion else SYSTEM_PROMPT_DUAL
        mock = self._mock(adapted, target_language, native_language, cefr_level, immersion)

        return self.llm.structured(
            system=system,
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
        immersion: bool,
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
            if immersion:
                # Everything in the target language; the explanation is a deeper
                # target-language paraphrase.
                runs = [
                    ExplanationRun(
                        lang="target",
                        text=f"[in {target_language}] In other words: {chunk}.",
                    )
                ]
                if v:
                    runs.append(
                        ExplanationRun(
                            lang="target",
                            text=f"[in {target_language}] '{v.term}' means {v.meaning}.",
                        )
                    )
            else:
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

        if immersion:
            intro = (
                f"[in {target_language}] Welcome! Today's topic is "
                f"\"{adapted.title}\". First the whole text, then a closer look."
            )
            breakdown_intro = f"[in {target_language}] Now, section by section."
        else:
            intro = (
                f"[in {native_language}] Welcome! Today's topic is "
                f"\"{adapted.title}\". First, listen to the whole text in "
                f"{target_language}. Then we'll go through it piece by piece."
            )
            breakdown_intro = (
                f"[in {native_language}] Now let's break it down section by section."
            )

        return PodcastScript(
            title=adapted.title,
            intro=intro,
            breakdown_intro=breakdown_intro,
            segments=segments,
        )
