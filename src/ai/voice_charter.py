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
        "2. Start with one brief emotional mirror of the user's intent before analysis.\n"
        "3. Sound like an experienced astrologer: clear, composed, practical.\n"
        "4. Light wit is allowed only when the topic is non-sensitive.\n"
        "5. Never use sarcasm, mockery, or overly dramatic language.\n"
        "6. Avoid repetitive openings/closings; vary phrasing naturally across turns.\n"
        "7. Do not copy fixed templates verbatim; keep a live conversational rhythm.\n"
        "8. Use calibrated certainty: 'indicates', 'suggests', 'likely'.\n"
        "9. Keep empathy explicit for emotional topics.\n"
        f"10. {lang_hint}\n"
    )


def get_response_structure_policy() -> str:
    """
    A flexible response policy to reduce rigid, robotic cadence.
    """
    return (
        "RESPONSE FLOW POLICY:\n"
        "- Start with a one-line emotional acknowledgement of the user's concern.\n"
        "- Give the core insight in plain language.\n"
        "- Add timing/action guidance when relevant.\n"
        "- Close naturally; ask a follow-up only when useful.\n"
        "- Do not force a fixed sentence template every turn.\n"
        "- Avoid repeating the same opener or closer used in the last few replies.\n"
    )


def pick_initial_closing(
    rng: random.Random,
    language: str,
    domain: str = "general",
) -> str:
    """
    Return a varied closing line for the INITIAL (short) response.
    ONLY offers deeper astrological detail on the CURRENT topic.
    Never suggests other topics like career/health/family — those belong in the detailed follow-up.
    """
    lang = (language or "en").lower()
    domain = (domain or "general").lower()

    if lang.startswith("hi"):
        choices: Dict[str, List[str]] = {
            "marriage": [
                "Kya aap is shadi ke yog ke peeche ki vistarit jyotishiya wajah jaanna chahenge?",
                "Agar aap chahein, to hum is vishay mein aur gehri jyotishiya jaankaari de sakte hain.",
                "Kya aap iske baare mein aur detail mein samajhna chahenge?",
            ],
            "career": [
                "Kya aap is career phase ke peeche ke jyotishiya kaaran aur gehri jaankaari chahenge?",
                "Agar aap chahein, to hum is vishay mein aur vistar se baat kar sakte hain.",
                "Kya aap iske baare mein aur detail mein jaanna chahenge?",
            ],
            "foreign": [
                "Kya aap is videsh yatra ke yog ki vistarit jyotishiya wajah jaanna chahenge?",
                "Agar aap chahein, to hum is pehlu mein aur gehri jaankaari de sakte hain.",
                "Kya aap iske baare mein aur gehri jyotishiya samajh chahte hain?",
            ],
            "health": [
                "Kya aap is swasthya sambandhi yog ki vistarit jyotishiya wajah jaanna chahenge?",
                "Agar aap chahein, to hum is vishay mein aur detail mein baat kar sakte hain.",
            ],
            "finance": [
                "Kya aap is arthik phase ke peeche ki vistarit jyotishiya wajah jaanna chahenge?",
                "Agar aap chahein, to hum is vishay mein aur gehri jaankaari de sakte hain.",
            ],
            "children": [
                "Kya aap is santaan sambandhi yog ki vistarit jyotishiya wajah jaanna chahenge?",
                "Agar aap chahein, to hum is pehlu mein aur detail mein baat kar sakte hain.",
            ],
            "general": [
                "Kya aap iske peeche ki vistarit jyotishiya wajah jaanna chahenge?",
                "Agar aap chahein, to hum is vishay mein aur gehri jaankaari de sakte hain.",
                "Kya aap iske baare mein aur detail mein samajhna chahenge?",
            ],
        }
    else:
        choices = {
            "marriage": [
                "Would you like a deeper astrological breakdown of what's shaping this marriage timing?",
                "If you'd like, I can go deeper into the planetary factors driving this period.",
                "Would you like to explore the astrological reasons behind this in more detail?",
            ],
            "career": [
                "Would you like a deeper look at the astrological factors shaping this career period?",
                "If you'd like, I can explain the planetary influences in more detail.",
                "Want me to go deeper into what's driving this in your chart?",
            ],
            "foreign": [
                "Would you like a deeper astrological breakdown of what's shaping this foreign travel period?",
                "If you'd like, I can explain the planetary factors in more detail.",
                "Want me to go deeper into the astrological picture behind this?",
            ],
            "health": [
                "Would you like a deeper astrological look at the factors behind this health tendency?",
                "If you'd like, I can go deeper into what's driving this in your chart.",
            ],
            "finance": [
                "Would you like a deeper astrological breakdown of the factors shaping this financial period?",
                "If you'd like, I can explain the planetary influences in more detail.",
            ],
            "children": [
                "Would you like a deeper look at the astrological factors shaping this children-related period?",
                "If you'd like, I can go deeper into what's driving this in your chart.",
            ],
            "general": [
                "Would you like a deeper astrological breakdown of what's shaping this?",
                "If you'd like, I can go deeper into the planetary factors behind this.",
                "Want me to explain the astrological picture in more detail?",
            ],
        }

    bucket = choices.get(domain, choices["general"])
    return rng.choice(bucket)


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
