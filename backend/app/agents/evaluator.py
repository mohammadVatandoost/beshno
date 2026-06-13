"""Agent 4 — Evaluator (quality gate).

Reviews the full script before audio generation across five dimensions:
CEFR compliance, language balance, pedagogical quality, factual/content
accuracy, and engagement/flow. Emits a pass/fail verdict, per-dimension scores,
and structured feedback that routes failures back to Agent 2 or Agent 3.
"""

from __future__ import annotations

from ..content_models import (
    AdaptedContent,
    EvaluationResult,
    EvaluationScores,
    PodcastScript,
)
from ..enums import is_immersion_level
from .base import Agent

# A script passes when no dimension is critically weak and the average is solid.
PASS_THRESHOLD_OVERALL = 3.8
PASS_THRESHOLD_PER_DIMENSION = 3.0

SYSTEM_PROMPT = """\
You are Agent 4, the Evaluator, a strict quality gate in a language-learning
podcast pipeline. The episode is dual-language and two-phase: the full text is
read in the target language, then revisited section by section with a
native-language breakdown after each chunk. Review the script BEFORE audio
generation and score it 0-5 on each dimension:

1. cefr_compliance — Do the target-language segments stay within the target
   CEFR level's vocabulary and grammar range (not too easy, not too hard)?
2. language_balance — Is the split between target-language content and
   native-language breakdowns appropriate and pedagogically useful (chunks short
   enough; explanations neither too sparse nor overwhelming)?
3. pedagogical_quality — Are the native-language breakdowns accurate, relevant
   and clearly tied to the chunk they explain (vocabulary, grammar, idioms)?
4. factual_accuracy — Do the segments faithfully reflect the adapted source
   content, with no hallucinated facts?
5. engagement_flow — Is the segmentation natural and well-paced, and does the
   concatenation of all segments read as one coherent text?

Then decide:
- passed = true only if the script is genuinely ready for audio.
- If not passed, set revision_target to "content_adapter" when the problem is in
  the underlying content (factual errors, wrong level of the source material) or
  "scriptwriter" when the problem is in the segmentation/breakdowns (balance,
  flow, explanations, CEFR drift, chunks too long or too short).
- Provide concrete, actionable feedback and a list of specific issues.
"""


class EvaluatorAgent(Agent):
    name = "evaluator"

    def run(
        self,
        *,
        script: PodcastScript,
        adapted: AdaptedContent,
        target_language: str,
        native_language: str,
        cefr_level: str,
    ) -> EvaluationResult:
        def render_explanation(runs) -> str:
            # Mark target-language runs with <...> so the evaluator can check that
            # foreign words are isolated for correct pronunciation.
            return " ".join(
                (f"<{r.text}>" if r.lang == "target" else r.text) for r in runs
            )

        rendered_segments = "\n\n".join(
            f"[{i}] TARGET: {seg.target_text}\n"
            f"    NATIVE: {render_explanation(seg.native_explanation)}"
            for i, seg in enumerate(script.segments)
        )
        immersion = is_immersion_level(cefr_level)
        rendered = (
            f"INTRO: {script.intro}\n"
            f"BREAKDOWN CUE: {script.breakdown_intro}\n\n"
            f"SEGMENTS (target chunk + breakdown):\n{rendered_segments}"
        )
        if immersion:
            mode_note = (
                "MODE: FULL IMMERSION (advanced level). The episode MUST be 100% in "
                "the target language — intro, cues and every breakdown included — "
                "with NO native language anywhere. For language_balance, heavily "
                "penalize ANY native-language usage; breakdowns should be deeper "
                "conceptual explanations in the target language."
            )
        else:
            mode_note = (
                "MODE: DUAL-LANGUAGE. Target-language content with native-language "
                "breakdowns after each chunk; target words quoted inside a breakdown "
                "are marked <like this>."
            )
        user = (
            f"Target (learning) language: {target_language}\n"
            f"Learner's native language: {native_language}\n"
            f"Target CEFR level: {cefr_level}\n"
            f"{mode_note}\n\n"
            f"Adapted source content (ground truth for factual accuracy):\n"
            f"{adapted.adapted_text}\n\n"
            f"Script to evaluate:\n{rendered}\n\n"
            f"Score every dimension and return your verdict."
        )

        mock = EvaluationResult(
            passed=True,
            scores=EvaluationScores(
                cefr_compliance=4.2,
                language_balance=4.0,
                pedagogical_quality=4.1,
                factual_accuracy=4.3,
                engagement_flow=4.0,
            ),
            overall_score=4.1,
            feedback="Script is well balanced and at the right level. Ready for audio.",
            revision_target=None,
            issues=[],
        )

        return self.llm.structured(
            system=SYSTEM_PROMPT,
            user=user,
            schema=EvaluationResult,
            mock_example=mock,
            max_tokens=12000,
        )

    @staticmethod
    def passes(result: EvaluationResult) -> bool:
        """Final gate: the agent's verdict AND the score thresholds must agree."""
        dims = result.scores
        per_dimension_ok = all(
            v >= PASS_THRESHOLD_PER_DIMENSION
            for v in (
                dims.cefr_compliance,
                dims.language_balance,
                dims.pedagogical_quality,
                dims.factual_accuracy,
                dims.engagement_flow,
            )
        )
        return (
            result.passed
            and per_dimension_ok
            and result.overall_score >= PASS_THRESHOLD_OVERALL
        )
