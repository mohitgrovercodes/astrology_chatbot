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
                    "Ab agar aap chahein, to hum is phase ke career aur promotion ke yog bhi dekh sakte hain.",
                    "Chahein to agle step mein hum aapke kaam ke direction ya role change ke samay ko bhi explore kar sakte hain.",
                ],
                "marriage": [
                    "Agar aap chahein, to agle step mein hum shadi ke baad ke jeevan — jaise family, children ya career balance — ke yog bhi dekh sakte hain.",
                    "Chahein to ab hum aapke partner ke swabhav, family background ya married life ki quality par bhi nazar daal sakte hain.",
                ],
                "general": [
                    "Agar aap chahein, to hum iske saath-jude hue kisi aur vishay — jaise career, health ya family — ko bhi dekh sakte hain.",
                    "Kya aap ab kisi doosre pehlu (jaise paisa, career ya health) ke baare mein puchhna chahenge?",
                ],
            }
        else:
            choices = {
                "career": [
                    "If you’d like, we can next look at how this period affects your long-term career direction or promotions.",
                    "Would you like to explore how your skills and strengths align with future career opportunities?",
                ],
                "marriage": [
                    "If you’d like, we can next explore relationship dynamics, family life or children timing connected to this marriage window.",
                    "Would you like to look at how marriage might interact with your career or relocation plans?",
                ],
                "general": [
                    "If you’d like, we can now explore another connected area such as money, health or family.",
                    "Would you like to ask about a related topic next, like career, finances or health?",
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
