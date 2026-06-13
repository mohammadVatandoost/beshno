"""Tone Selector — resolves the narrator persona when the user picks "Auto".

Given the topic (and category/level), it chooses one concrete tone for the
episode. With a real LLM it reasons about the topic; the mock falls back to a
deterministic keyword heuristic so offline runs are predictable.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..enums import Tone
from .base import Agent

SYSTEM_PROMPT = """\
You choose the best narrator tone/persona for a language-learning podcast, based
on its topic. Pick EXACTLY ONE tone from this set (never "auto"):

- default: neutral, balanced, standard.
- professional: crisp, formal, polished (business/academic/workplace topics).
- friendly: warm and conversational (everyday life, travel, food, hobbies).
- candid: direct and no-nonsense.
- quirky: playful and humorous (light/comedic topics, games).
- efficient: ultra-concise.
- nerdy: analytical and deeply technical (cutting-edge tech, science, maths).
- cynical: dry, skeptical, bluntly realistic.

Match the tone to the topic — e.g. a frontier-tech topic suggests nerdy or
professional, a history topic suggests default, a comedy topic suggests quirky.
Give a one-sentence rationale.
"""


class ToneChoice(BaseModel):
    tone: Tone = Field(description="The chosen tone (must not be 'auto').")
    rationale: str = Field(description="One sentence explaining the choice.")


def heuristic_tone(topic: str, category: str | None) -> Tone:
    """Deterministic topic -> tone mapping used by the mock / as a fallback."""
    text = f"{category or ''} {topic or ''}".lower()

    def has(words: tuple[str, ...]) -> bool:
        return any(w in text for w in words)

    if has(
        (
            "tech", "ai", "software", "computer", "programming", "robot", "data",
            "crypto", "quantum", "physics", "chemistry", "biolog", "math",
            "engineer", "science", "algorithm",
        )
    ):
        return Tone.NERDY
    if has(
        (
            "business", "finance", "econom", "market", "management", "startup",
            "career", "workplace", "legal", "law", "invest", "corporate",
        )
    ):
        return Tone.PROFESSIONAL
    if has(("comedy", "funny", "humor", "humour", "meme", "game", "gaming", "party")):
        return Tone.QUIRKY
    if has(
        (
            "travel", "food", "cook", "recipe", "hobby", "music", "sport",
            "daily", "everyday", "family", "friend", "culture", "fashion",
        )
    ):
        return Tone.FRIENDLY
    return Tone.DEFAULT


class ToneSelectorAgent(Agent):
    name = "tone_selector"

    def run(
        self, *, topic: str, category: str | None = None, cefr_level: str = ""
    ) -> ToneChoice:
        user = (
            f"Topic: {topic}\n"
            f"Category: {category or '(none)'}\n"
            f"Learner CEFR level: {cefr_level}\n\n"
            f"Choose the best tone for this episode and explain briefly."
        )
        guess = heuristic_tone(topic, category)
        mock = ToneChoice(
            tone=guess, rationale=f"Heuristic match for the topic -> {guess.value}."
        )
        return self.llm.structured(
            system=SYSTEM_PROMPT,
            user=user,
            schema=ToneChoice,
            mock_example=mock,
            max_tokens=2000,
        )
