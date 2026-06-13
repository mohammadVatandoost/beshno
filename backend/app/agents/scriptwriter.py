"""Agent 3 — Scriptwriter.

Transforms the adapted summary into an engaging two-person podcast script:

- Learner speaker (the "girl"): speaks primarily in the TARGET language at the
  learner's CEFR level.
- Teacher speaker (the "boy"): speaks in the learner's NATIVE language, acting
  as a teacher who explains grammar points, difficult words, idioms and
  cultural context introduced by the learner's lines.
"""

from __future__ import annotations

from ..content_models import AdaptedContent, PodcastScript, ScriptTurn
from .base import Agent

LEARNER_NAME = "Mia"
TEACHER_NAME = "Leo"

SYSTEM_PROMPT = f"""\
You are Agent 3, the Scriptwriter, in a language-learning podcast pipeline.

Turn the adapted content into a natural, engaging two-person podcast dialogue.

Speakers:
- "{LEARNER_NAME}" (speaker = "learner", language = "target"): speaks in the
  TARGET language at the learner's CEFR level. She presents the content
  conversationally, sentence by sentence.
- "{TEACHER_NAME}" (speaker = "teacher", language = "native"): speaks in the
  learner's NATIVE language. After {LEARNER_NAME}'s lines, he acts as a teacher:
  explaining difficult words, grammar points, idioms and cultural context she
  just used, and occasionally asking her to continue.

Rules:
- Alternate naturally; the teacher should react to what the learner actually said.
- Keep the learner's language within the CEFR level.
- The teacher's explanations must be accurate and tied to the learner's lines.
- Aim for a balanced, pedagogically useful split (roughly half/half).
- Open with a short friendly intro and close with a brief wrap-up.
- Set language="target" for the learner's lines and language="native" for the
  teacher's lines. Put short teaching annotations in the optional "note" field.

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
            max_tokens=12000,
        )

    @staticmethod
    def _mock(
        adapted: AdaptedContent,
        target_language: str,
        native_language: str,
        cefr_level: str,
    ) -> PodcastScript:
        turns: list[ScriptTurn] = [
            ScriptTurn(
                speaker="teacher",
                speaker_name=TEACHER_NAME,
                language="native",
                text=(
                    f"[in {native_language}] Welcome! Today {LEARNER_NAME} will tell us "
                    f"about \"{adapted.title}\" in {target_language}. I'll jump in to "
                    f"explain the tricky parts."
                ),
            ),
            ScriptTurn(
                speaker="learner",
                speaker_name=LEARNER_NAME,
                language="target",
                text=f"[in {target_language}] {adapted.adapted_text.splitlines()[-1][:200]}",
            ),
        ]
        for point in adapted.key_points[:3]:
            turns.append(
                ScriptTurn(
                    speaker="learner",
                    speaker_name=LEARNER_NAME,
                    language="target",
                    text=f"[in {target_language}] {point}",
                )
            )
            turns.append(
                ScriptTurn(
                    speaker="teacher",
                    speaker_name=TEACHER_NAME,
                    language="native",
                    text=(
                        f"[in {native_language}] Nicely said. Notice the vocabulary she "
                        f"used there — let me explain what it means."
                    ),
                    note="Vocabulary explanation",
                )
            )
        if adapted.key_vocabulary:
            v = adapted.key_vocabulary[0]
            turns.append(
                ScriptTurn(
                    speaker="teacher",
                    speaker_name=TEACHER_NAME,
                    language="native",
                    text=f"[in {native_language}] For example, '{v.term}' means {v.meaning}.",
                    note=f"Key term: {v.term}",
                )
            )
        turns.append(
            ScriptTurn(
                speaker="teacher",
                speaker_name=TEACHER_NAME,
                language="native",
                text=f"[in {native_language}] Great work today. Keep practising your {target_language}!",
            )
        )
        return PodcastScript(title=adapted.title, turns=turns)
