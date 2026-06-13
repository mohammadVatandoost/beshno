"""Agent 2 — Content Adapter.

Summarizes and rewrites the selected source material, strictly aligning
vocabulary, grammar and sentence complexity with the learner's CEFR level
(max ~5 pages of output).
"""

from __future__ import annotations

from ..content_models import AdaptedContent, KeyVocab
from .base import Agent

_CEFR_GUIDANCE = {
    "A1": "Use only the simplest, most frequent words and very short present-tense sentences.",
    "A2": "Use common everyday vocabulary and simple sentences; basic past/future is okay.",
    "B1": "Use clear, connected text on familiar topics; some subordinate clauses are fine.",
    "B2": "Use a broad vocabulary and complex sentences, but keep explanations clear.",
    "C1": "Use rich, idiomatic, well-structured language with nuance.",
    "C2": "Use sophisticated, precise, near-native language.",
}

SYSTEM_PROMPT = """\
You are Agent 2, the Content Adapter, in a language-learning podcast pipeline.

Rewrite and summarize the provided source material into a single coherent piece
written ENTIRELY in the target (learning) language, calibrated to the learner's
CEFR level. Requirements:

- Keep it factual and faithful to the sources. Do NOT invent facts.
- Strictly match the CEFR level for vocabulary, grammar and sentence length.
- Keep it focused and self-contained (roughly 3-5 short pages maximum).
- Produce: a short title, the adapted text, 3-6 key points, and a list of
  key vocabulary terms with concise explanations in the learner's NATIVE
  language.
- Avoid re-introducing vocabulary the learner already knows: do NOT choose,
  define, or build key vocabulary around any words listed under "ALREADY-TAUGHT
  WORDS". Pick fresh, level-appropriate words the learner has not seen yet.

If revision feedback is provided, address every point in it.
"""


class ContentAdapterAgent(Agent):
    name = "content_adapter"

    def run(
        self,
        *,
        topic: str,
        target_language: str,
        native_language: str,
        cefr_level: str,
        materials: str,
        feedback: str | None = None,
        owner: str = "default",
        learned_vocab_mcp=None,
    ) -> AdaptedContent:
        guidance = _CEFR_GUIDANCE.get(cefr_level, "")
        feedback_block = (
            f"\n\nREVISION FEEDBACK to address:\n{feedback}\n" if feedback else ""
        )
        # Query the learned-vocabulary MCP server to avoid repeating words.
        avoid = self.fetch_avoid_terms(learned_vocab_mcp, owner, target_language)
        avoid_block = (
            "\n\nALREADY-TAUGHT WORDS — the learner already knows these; do NOT "
            "reuse, define, or build key vocabulary around them, choose fresh words "
            "instead:\n" + ", ".join(avoid) + "\n"
            if avoid
            else ""
        )
        user = (
            f"Topic: {topic}\n"
            f"Target (learning) language: {target_language}\n"
            f"Learner's native language: {native_language}\n"
            f"CEFR level: {cefr_level} — {guidance}\n\n"
            f"Source material (from selected resources):\n{materials[:16000]}"
            f"{feedback_block}"
            f"{avoid_block}"
        )

        mock = AdaptedContent(
            title=f"{topic.strip().capitalize()} — a {cefr_level} introduction",
            adapted_text=(
                f"[Adapted into {target_language} at level {cefr_level}]\n\n"
                f"This short text explains {topic} in simple, clear language. "
                f"It introduces the main ideas, gives an everyday example, and "
                f"highlights why {topic} matters. The sentences are kept short and "
                f"the vocabulary is chosen to match a {cefr_level} learner."
            ),
            key_points=[
                f"What {topic} is, in simple terms.",
                f"A short, real-life example of {topic}.",
                f"Why {topic} is useful or interesting to know.",
            ],
            key_vocabulary=[
                KeyVocab(term="overview", meaning="a short general description"),
                KeyVocab(term="example", meaning="a thing that shows a general idea"),
                KeyVocab(term="everyday", meaning="happening as part of normal life"),
            ],
        )

        return self.llm.structured(
            system=SYSTEM_PROMPT,
            user=user,
            schema=AdaptedContent,
            mock_example=mock,
            max_tokens=32000,
        )
