from datetime import datetime

from core.constants import CLUE_TIMER_SECONDS
from core.validation import validate_guess_rationale


TUTORIAL_BOARD = ("Cat", "Dog", "Apple", "Table", "Train", "River")
TUTORIAL_TARGETS = frozenset({"Cat", "Dog"})
TUTORIAL_NEUTRALS = frozenset({"Apple", "Table", "Train"})
TUTORIAL_BOMB = "River"
TUTORIAL_CLUE = "Pet"
TUTORIAL_CLUE_NUMBER = 2
TUTORIAL_AI_EXPLANATION = "Both intended cards are common household companion animals."
TUTORIAL_WORD_ROLES = {
    "Cat": "target",
    "Dog": "target",
    "Apple": "neutral",
    "Table": "neutral",
    "Train": "neutral",
    "River": "bomb",
}

TUTORIAL_ROUND_2_BOARD = ("Cat", "Dog", "Apple", "Table", "Orange", "River")
TUTORIAL_ROUND_2_TARGETS = frozenset({"Apple", "Orange"})
TUTORIAL_ROUND_2_NEUTRALS = frozenset({"Cat", "Dog", "Table"})
TUTORIAL_ROUND_2_WORD_ROLES = {
    "Cat": "neutral",
    "Dog": "neutral",
    "Apple": "target",
    "Table": "neutral",
    "Orange": "target",
    "River": "bomb",
}


def tutorial_selection_is_correct(selected_cards):
    return set(selected_cards or []) == TUTORIAL_TARGETS


def tutorial_comprehension_is_correct(answer):
    return answer == TUTORIAL_CLUE_NUMBER


def tutorial_rationale_is_valid(text, min_words=3, max_words=30):
    return validate_guess_rationale(
        text,
        TUTORIAL_BOARD,
        min_words=min_words,
        max_words=max_words,
    )[0]


def tutorial_clue_is_valid(text):
    cleaned = str(text or "").strip()
    return bool(cleaned) and cleaned.isascii() and cleaned.isalpha()


def simulated_ai_guesses(clue_number):
    count = max(0, min(int(clue_number or 0), len(TUTORIAL_ROUND_2_TARGETS)))
    return [
        word
        for word in TUTORIAL_ROUND_2_BOARD
        if word in TUTORIAL_ROUND_2_TARGETS
    ][:count]


def tutorial_time_remaining(started_at, now=None):
    if not started_at:
        return float(CLUE_TIMER_SECONDS)
    try:
        started = datetime.fromisoformat(started_at)
    except (TypeError, ValueError):
        return 0.0
    now = now or datetime.utcnow()
    return max(0.0, float(CLUE_TIMER_SECONDS) - (now - started).total_seconds())
