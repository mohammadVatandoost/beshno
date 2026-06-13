"""Agent 6 — Exercise Grader.

Grades a learner's submitted answers in the voice of a supportive language
teacher: an overall score from 1 to 10, encouraging detailed feedback, and a
per-item verdict. Reading multiple-choice correctness is computed deterministically
by the caller and passed in; vocabulary and speaking are judged by the model.
"""

from __future__ import annotations

from ..content_models import (
    ExerciseGrade,
    ExerciseItemResult,
    ExerciseSet,
    ExerciseSubmission,
)
from .base import Agent

SYSTEM_PROMPT = """\
You are a supportive, encouraging language teacher grading a learner's answers to
a 5-part practice session (1 speaking, 2 vocabulary, 2 reading multiple-choice).

Return:
- score: an overall INTEGER from 1 to 10 reflecting accuracy and effort across all
  five exercises.
- feedback: a warm, constructive, detailed review in the voice of a supportive
  teacher — praise what they did well, gently correct mistakes, and give one
  concrete tip to improve.
- items: one entry per exercise, labelled "Speaking", "Vocabulary 1",
  "Vocabulary 2", "Reading 1", "Reading 2". Set `correct` true/false for
  vocabulary and reading items (null for speaking) and add a one-sentence note.

Grading guidance:
- Reading items: the correctness is provided — respect it.
- Vocabulary items: accept paraphrases and synonyms that capture the meaning;
  minor spelling slips are fine.
- Speaking: reward relevance to the topic, clarity and effort; be encouraging
  even for a short answer.
"""


class ExerciseGraderAgent(Agent):
    name = "exercise_grader"

    def run(
        self,
        *,
        exercise_set: ExerciseSet,
        submission: ExerciseSubmission,
        target_language: str,
        native_language: str,
        cefr_level: str,
        mcq_correct: list[bool],
    ) -> ExerciseGrade:
        sp_ans = submission.speaking_answer.strip() or "(no answer)"

        vocab_lines = []
        for i, v in enumerate(exercise_set.vocabulary):
            ans = (
                submission.vocabulary_answers[i]
                if i < len(submission.vocabulary_answers)
                else ""
            ).strip()
            vocab_lines.append(
                f"Vocabulary {i + 1}: term='{v.term}'\n"
                f"  correct meaning: {v.answer}\n"
                f"  learner answer: {ans or '(no answer)'}"
            )

        reading_lines = []
        for i, r in enumerate(exercise_set.reading):
            sel = (
                submission.reading_answers[i]
                if i < len(submission.reading_answers)
                else -1
            )
            sel_text = r.options[sel] if 0 <= sel < len(r.options) else "(no answer)"
            correct_text = (
                r.options[r.correct_index]
                if 0 <= r.correct_index < len(r.options)
                else ""
            )
            verdict = "CORRECT" if (i < len(mcq_correct) and mcq_correct[i]) else "INCORRECT"
            reading_lines.append(
                f"Reading {i + 1}: {r.question}\n"
                f"  learner chose: {sel_text}\n"
                f"  correct answer: {correct_text}  -> {verdict}"
            )

        user = (
            f"Target language: {target_language}\n"
            f"Native language: {native_language}\n"
            f"CEFR level: {cefr_level}\n\n"
            f"SPEAKING\n  prompt: {exercise_set.speaking.prompt}\n"
            f"  learner answer: {sp_ans}\n\n"
            + "\n\n".join(vocab_lines)
            + "\n\n"
            + "\n\n".join(reading_lines)
            + "\n\nGrade the session: overall score 1-10, teacher feedback, and "
            "a per-item result for all five exercises."
        )

        mock = self._mock(exercise_set, submission, mcq_correct)

        return self.llm.structured(
            system=SYSTEM_PROMPT,
            user=user,
            schema=ExerciseGrade,
            mock_example=mock,
            max_tokens=8000,
        )

    @staticmethod
    def _mock(
        exercise_set: ExerciseSet,
        submission: ExerciseSubmission,
        mcq_correct: list[bool],
    ) -> ExerciseGrade:
        items: list[ExerciseItemResult] = []

        spoke = bool(submission.speaking_answer.strip())
        items.append(
            ExerciseItemResult(
                label="Speaking",
                correct=None,
                feedback=(
                    "Nice effort speaking about the topic — keep going!"
                    if spoke
                    else "Try to say a few sentences next time."
                ),
            )
        )

        objective = 0
        for i, v in enumerate(exercise_set.vocabulary):
            ans = (
                submission.vocabulary_answers[i]
                if i < len(submission.vocabulary_answers)
                else ""
            ).strip().lower()
            ok = bool(ans) and (ans in v.answer.lower() or v.answer.lower() in ans)
            objective += 1 if ok else 0
            items.append(
                ExerciseItemResult(
                    label=f"Vocabulary {i + 1}",
                    correct=ok,
                    feedback=(
                        f"Correct — '{v.term}' means {v.answer}."
                        if ok
                        else f"Not quite — '{v.term}' means {v.answer}."
                    ),
                )
            )

        for i, r in enumerate(exercise_set.reading):
            ok = bool(i < len(mcq_correct) and mcq_correct[i])
            objective += 1 if ok else 0
            items.append(
                ExerciseItemResult(
                    label=f"Reading {i + 1}",
                    correct=ok,
                    feedback=(
                        "Correct!"
                        if ok
                        else f"The correct answer was: {r.options[r.correct_index]}."
                    ),
                )
            )

        score = max(1, min(10, objective * 2 + (1 if spoke else 0) + 1))
        feedback = (
            f"Good work! You got {objective} of 4 objective questions right. "
            "Review the new vocabulary, keep practising speaking, and you'll keep "
            "improving — well done for completing the session."
        )
        return ExerciseGrade(score=score, feedback=feedback, items=items)
