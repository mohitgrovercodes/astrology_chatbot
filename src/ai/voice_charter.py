"""
Central voice and response-structure policy for astrologer replies.

This module is intentionally lightweight so it can be imported from
persona, prompt-builder, and orchestration layers without cyclic deps.
"""

from typing import Dict, List
import random


def get_voice_charter(language: str = "en") -> str:
    """
    Return the canonical voice charter used across the stack.
    """
    lang_hint = (
        "Use Roman script (English alphabet) naturally."
        if "-lat" in (language or "")
        else "Use natural phrasing in the user's language."
    )

    return (
        "VOICE CHARTER (single source of truth):\n"
        "1. Be accurate first, then warm and human.\n"
        "2. Sound like an experienced astrologer: clear, composed, practical.\n"
        "3. Light wit is allowed only when the topic is non-sensitive.\n"
        "4. Never use sarcasm, mockery, or overly dramatic language.\n"
        "5. Avoid repetitive openings/closings; vary phrasing naturally.\n"
        "6. Use calibrated certainty: 'indicates', 'suggests', 'likely'.\n"
        "7. Keep empathy explicit for emotional topics.\n"
        f"8. {lang_hint}\n"
    )


def get_response_structure_policy() -> str:
    """
    A flexible response policy to reduce rigid, robotic cadence.
    """
    return (
        "RESPONSE FLOW POLICY:\n"
        "- Start with a direct acknowledgement of the user's concern.\n"
        "- Give the core insight in plain language.\n"
        "- Add timing/action guidance when relevant.\n"
        "- Close naturally; ask a follow-up only when useful.\n"
        "- Do not force a fixed sentence template every turn.\n"
    )


def pick_contextual_closing(
    rng: random.Random,
    language: str,
    domain: str = "general",
    ask_question: bool = True,
) -> str:
    """
    Return a varied, intent-aware closing line.
    """
    lang = (language or "en").lower()
    domain = (domain or "general").lower()

    if ask_question:
        if lang.startswith("hi"):
            choices: Dict[str, List[str]] = {
                "career": [
                    "Agar aap chahen, main aapko next strong action-window bhi bata sakta hoon.",
                    "Chahein to main isko interview/preparation strategy ke saath map kar doon?",
                ],
                "marriage": [
                    "Chahein to main is phase ke practical relationship steps bhi bata doon?",
                    "Agar aap chahen, main partner-dynamics angle ko aur clear kar sakta hoon.",
                ],
                "general": [
                    "Agar aap chahen, main isko aur detail mein simple tareeke se samjha sakta hoon.",
                    "Kya aap iske practical next steps bhi dekhna chahenge?",
                ],
            }
        else:
            choices = {
                "career": [
                    "If you want, I can map this to a practical preparation strategy next.",
                    "Would you like me to break this into a month-by-month action plan?",
                ],
                "marriage": [
                    "If you want, I can also map the practical relationship steps for this phase.",
                    "Would you like a clearer partner-dynamics breakdown for this window?",
                ],
                "general": [
                    "If you want, I can explain the next practical step in simple terms.",
                    "Would you like me to go one level deeper on this?",
                ],
            }
        bucket = choices.get(domain, choices["general"])
        return rng.choice(bucket)

    if lang.startswith("hi"):
        return rng.choice(
            [
                "Yeh phase disciplined effort ke saath zyada constructive ban sakta hai.",
                "Isko dhairya aur focused action ke saath handle karna sabse sahi rahega.",
            ]
        )

    return rng.choice(
        [
            "This phase responds best to steady, practical action.",
            "Consistent effort and clear decisions will shape this period strongly.",
        ]
    )
