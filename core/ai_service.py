import random
import re

import streamlit as st
from openai import OpenAI

from core.constants import MAX_HINT_NUMBER, MODEL_NAME

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])


def call_openai_chat(system_prompt, user_prompt, temperature=0.4):
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
    )
    return response.choices[0].message.content.strip()


def normalize_token(value):
    return re.sub(r"[^a-z]", "", value.lower())


def simple_stem(word):
    base = normalize_token(word)
    suffixes = ["ation", "ment", "ness", "ingly", "ing", "ed", "ly", "es", "s", "er"]
    for suffix in suffixes:
        if base.endswith(suffix) and len(base) - len(suffix) >= 3:
            return base[: -len(suffix)]
    return base


def is_hint_too_close_to_board(hint, board_words):
    normalized_hint = normalize_token(hint)
    stemmed_hint = simple_stem(hint)
    for word in board_words:
        normalized_word = normalize_token(word)
        stemmed_word = simple_stem(word)
        if normalized_hint == normalized_word:
            return True
        if stemmed_hint and stemmed_word and stemmed_hint == stemmed_word:
            return True
        if len(normalized_hint) >= 4 and len(normalized_word) >= 4:
            if normalized_hint.startswith(normalized_word) or normalized_word.startswith(
                normalized_hint
            ):
                return True
    return False


def parse_hint(raw_text, fallback_n):
    cleaned = raw_text.strip()
    if "|" in cleaned:
        hint, raw_number = cleaned.split("|", 1)
    else:
        parts = cleaned.split()
        hint = parts[0] if parts else "bridge"
        raw_number = str(fallback_n)

    hint = re.sub(r"[^A-Za-z-]", "", hint).lower()
    if not hint:
        hint = "bridge"

    try:
        hint_number = int(re.findall(r"\d+", raw_number)[0])
    except IndexError:
        hint_number = fallback_n
    except ValueError:
        hint_number = fallback_n

    hint_number = max(1, min(MAX_HINT_NUMBER, hint_number))
    return hint, hint_number


def build_hint_system_prompt(previous_hint=None):
    previous_hint_clause = ""
    if previous_hint:
        previous_hint_clause = (
            f"6) The new clue must be clearly different from '{previous_hint}'.\n"
            "7) Prefer a simpler, more everyday association than before.\n"
        )

    return (
        "You are the AI clue-giver in a cooperative Codenames-like word game.\n"
        "You are trying to help your human teammate score as many points as possible.\n"
        "There are four target words, one of which is a GOLDEN TARGET worth 3 points.\n"
        "Your job is to act like a thoughtful human teammate: give one natural clue word that "
        "points toward the largest safe cluster of target words.\n\n"
        "Hard rules:\n"
        "1) Output exactly in the format HINT|N.\n"
        "2) HINT must be exactly one single English word.\n"
        "3) Never use any board word or any obvious morphological form of a board word.\n"
        "4) Choose a clue that is helpful, human-like, and not too obscure.\n"
        "5) Favor clues that safely connect multiple target words. Prioritize the golden target "
        "only if it does not make the clue risky.\n"
        f"{previous_hint_clause}"
        "Do not explain. Do not add punctuation or extra text."
    )


def build_hint_user_prompt(target_words, bomb_word, neutral_words, word_type, golden_target):
    return (
        f"Word type: {word_type}\n"
        f"Target words: {', '.join(target_words)}\n"
        f"Golden target: {golden_target}\n"
        f"Neutral words: {', '.join(neutral_words)}\n"
        f"Bomb word: {bomb_word}\n\n"
        "Choose the clue that a smart human teammate would most likely give to help the guesser "
        "find the highest number of safe targets."
    )


def generate_ai_hint(target_words, bomb_word, neutral_words, word_type, golden_target):
    board_words = target_words + neutral_words + [bomb_word]
    fallback_number = len(target_words)

    for _ in range(3):
        raw = call_openai_chat(
            build_hint_system_prompt(),
            build_hint_user_prompt(
                target_words, bomb_word, neutral_words, word_type, golden_target
            ),
        )
        hint, hint_number = parse_hint(raw, fallback_number)
        if not is_hint_too_close_to_board(hint, board_words):
            return hint, hint_number

    return "cluster", min(2, fallback_number)


def generate_ai_hint_reroll(
    target_words,
    bomb_word,
    neutral_words,
    word_type,
    golden_target,
    previous_hint,
):
    board_words = target_words + neutral_words + [bomb_word]
    fallback_number = len(target_words)

    for _ in range(3):
        raw = call_openai_chat(
            build_hint_system_prompt(previous_hint=previous_hint),
            build_hint_user_prompt(
                target_words, bomb_word, neutral_words, word_type, golden_target
            ),
        )
        hint, hint_number = parse_hint(raw, fallback_number)
        if hint != previous_hint and not is_hint_too_close_to_board(hint, board_words):
            return hint, hint_number

    return "simple", 1


def ai_guess(board, hint, hint_number, remaining_rerolls):
    system_prompt = (
        "You are the AI guesser in a cooperative Codenames-like word game.\n"
        "Your job is to help the team score points by making the best possible guesses from the board.\n\n"
        "Decision policy:\n"
        "1) Default behavior is to guess. Do not ask for a new clue just because a clue is imperfect.\n"
        "2) Only output REROLL_HINT if the clue is genuinely unusable: for example meaningless, unrelated to every board word, "
        "or so ambiguous that any guess would be close to random.\n"
        "3) If the clue plausibly points to one or more board words, you must guess.\n"
        "4) Output exactly either REROLL_HINT or exactly N comma-separated board words.\n"
        "5) Never explain your reasoning."
    )

    user_prompt = (
        f"Board words: {', '.join(board)}\n"
        f"Hint: {hint}\n"
        f"Number of guesses (N): {hint_number}\n"
        f"Remaining clue rerolls: {remaining_rerolls}\n\n"
        "Remember: reroll is a last resort. If there is any plausible interpretation, guess."
    )

    raw = call_openai_chat(system_prompt, user_prompt, temperature=0.2).strip()
    if raw.upper() == "REROLL_HINT" and remaining_rerolls > 0:
        return ["__REROLL_HINT__"]

    model_words = [part.strip().lower() for part in raw.split(",") if part.strip()]
    valid_words = []
    seen = set()
    board_lookup = {word.lower(): word for word in board}

    for word in model_words:
        if word in board_lookup and word not in seen:
            valid_words.append(board_lookup[word])
            seen.add(word)

    if len(valid_words) < hint_number:
        remaining_choices = [word for word in board if word not in valid_words]
        needed = min(hint_number - len(valid_words), len(remaining_choices))
        if needed > 0:
            valid_words.extend(random.sample(remaining_choices, needed))

    return valid_words[:hint_number]


def validate_human_hint(hint, board_words):
    cleaned = hint.strip().lower()
    if not cleaned:
        return False, "Please enter a clue word."
    if " " in cleaned:
        return False, "The clue must be exactly one word."
    if is_hint_too_close_to_board(cleaned, board_words):
        return False, "This clue is too close to a board word. Please choose a different word."
    return True, ""
