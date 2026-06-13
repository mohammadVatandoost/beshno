"""Agent 5 — Exercise Generator.

Produces an interactive practice session for the finished podcast: exactly 5
exercises — 1 speaking prompt, 2 vocabulary-meaning questions (on difficult words
from the podcast), and 2 reading/listening multiple-choice questions.
"""

from __future__ import annotations

from ..content_models import (
    AdaptedContent,
    ExerciseSet,
    ReadingMCQExercise,
    SpeakingExercise,
    VocabExercise,
)
from ..enums import is_immersion_level
from .base import Agent

SYSTEM_PROMPT = """\
You are Agent 5, the Exercise Generator, in a language-learning podcast pipeline.
Create an interactive practice session based on the podcast content. Produce
EXACTLY:

- speaking: 1 open-ended prompt asking the learner to speak about the topic to
  practice fluency.
- vocabulary: EXACTLY 2 items, each testing the meaning of a DIFFICULT word or
  phrase that appeared in the podcast (target language). For each, give the
  `term` (in the target language), a `question` asking what it means, and the
  correct `answer` (the meaning) for grading.
- reading: EXACTLY 2 multiple-choice questions testing comprehension of the
  content. Each has a `question`, 3-4 `options`, and `correct_index` (0-based)
  pointing to the correct option. Exactly one option is correct; make the
  distractors plausible.

Language of the questions/prompts:
- Dual-language levels (A1/A2/B1): write prompts, questions and options in the
  learner's NATIVE language so the task is clear; keep vocabulary `term`s and any
  quoted target-language text in the TARGET language.
- Immersion levels (B2/C1/C2): write EVERYTHING in the TARGET language.

Base the questions only on the provided content; do not invent facts.
"""


class ExerciseGeneratorAgent(Agent):
    name = "exercise_generator"

    def run(
        self,
        *,
        topic: str,
        target_language: str,
        native_language: str,
        cefr_level: str,
        adapted: AdaptedContent,
    ) -> ExerciseSet:
        immersion = is_immersion_level(cefr_level)
        vocab = "\n".join(f"- {v.term}: {v.meaning}" for v in adapted.key_vocabulary)
        points = "\n".join(f"- {p}" for p in adapted.key_points)
        mode_line = (
            f"Mode: IMMERSION — write everything in {target_language}."
            if immersion
            else f"Mode: DUAL — write prompts/questions in {native_language}; "
            f"keep vocabulary terms in {target_language}."
        )
        user = (
            f"Topic: {topic}\n"
            f"Target (learning) language: {target_language}\n"
            f"Learner's native language: {native_language}\n"
            f"CEFR level: {cefr_level}\n"
            f"{mode_line}\n\n"
            f"Title: {adapted.title}\n\n"
            f"Content (in {target_language}):\n{adapted.adapted_text}\n\n"
            f"Key points:\n{points}\n\n"
            f"Difficult vocabulary:\n{vocab}\n\n"
            f"Create exactly 5 exercises (1 speaking, 2 vocabulary, 2 reading MCQ)."
        )

        mock = self._mock(adapted, target_language, native_language, immersion)

        return self.llm.structured(
            system=SYSTEM_PROMPT,
            user=user,
            schema=ExerciseSet,
            mock_example=mock,
            max_tokens=8000,
        )

    @staticmethod
    def _mock(
        adapted: AdaptedContent,
        target_language: str,
        native_language: str,
        immersion: bool,
    ) -> ExerciseSet:
        ask_lang = target_language if immersion else native_language

        # Vocabulary — from the difficult words, padded to 2.
        vocab_items = list(adapted.key_vocabulary)
        while len(vocab_items) < 2:
            from ..content_models import KeyVocab

            vocab_items.append(KeyVocab(term="overview", meaning="a short general description"))
        vocabulary = [
            VocabExercise(
                term=v.term,
                question=f"[in {ask_lang}] What does '{v.term}' mean?",
                answer=v.meaning,
            )
            for v in vocab_items[:2]
        ]

        # Reading MCQ — from key points, padded to 2.
        points = list(adapted.key_points) or [f"{adapted.title} is the topic."]
        while len(points) < 2:
            points.append("The content is suitable for learners.")
        reading = [
            ReadingMCQExercise(
                question=f"[in {ask_lang}] Which statement about the topic is correct?",
                options=[
                    points[i],
                    "None of the above.",
                    "The topic was not discussed.",
                ],
                correct_index=0,
            )
            for i in range(2)
        ]

        speaking = SpeakingExercise(
            prompt=(
                f"[in {ask_lang}] In a few sentences, say what you learned about "
                f"\"{adapted.title}\" and why it is interesting."
            )
        )

        return ExerciseSet(speaking=speaking, vocabulary=vocabulary, reading=reading)
