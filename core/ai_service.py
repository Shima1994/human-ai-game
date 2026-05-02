import random
import json
import re

import streamlit as st
from openai import OpenAI

from core.constants import MAX_HINT_NUMBER, MODEL_NAME

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

FALLBACK_HINTS = [
    "signal",
    "pattern",
    "linkage",
    "shared",
    "thread",
    "aspect",
    "angle",
    "bridge",
    "field",
    "motion",
    "shape",
    "anchor",
    "path",
    "zone",
    "core",
    "trace",
    "frame",
    "bond",
    "spark",
    "source",
    "guide",
    "match",
    "route",
    "sense",
    "theme",
    "point",
    "circle",
    "focus",
    "origin",
    "logic",
    "union",
    "vector",
]


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
        return "", fallback_n

    hint = hint.strip().lower()
    if not re.fullmatch(r"[a-z-]+", hint):
        hint = ""
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


def parse_hint_with_targets(raw_text, fallback_n, remaining_targets):
    cleaned = raw_text.strip()
    parts = [part.strip() for part in cleaned.split("|")]
    if len(parts) < 3:
        hint, hint_number = parse_hint(cleaned, fallback_n)
        return hint, hint_number, []

    hint, hint_number = parse_hint("|".join(parts[:2]), fallback_n)
    lookup = {word.lower(): word for word in remaining_targets}
    intended_targets = []
    seen = set()
    for raw_word in parts[2].split(","):
        word_key = raw_word.strip().lower()
        if word_key in lookup and word_key not in seen:
            intended_targets.append(lookup[word_key])
            seen.add(word_key)

    return hint, hint_number, intended_targets[:hint_number]


def remaining_target_count(target_words, history):
    found_targets = {
        guess
        for item in history
        for guess in item.get("correct_guesses", [])
    }
    return max(1, min(MAX_HINT_NUMBER, len(target_words) - len(found_targets)))


def format_interaction_history(history):
    if not history:
        return "No previous interactions in this round."

    lines = []
    for index, item in enumerate(history, start=1):
        guesses = ", ".join(item.get("guesses", [])) or "none"
        correct_guesses = ", ".join(item.get("correct_guesses", [])) or "none"
        if item.get("bomb_hit"):
            outcome = "bomb hit"
        elif item.get("correct"):
            outcome = "correct"
        else:
            outcome = "incorrect"
        lines.append(
            f"{index}. hint={item.get('hint', '')} | number={item.get('hint_number', '')} | "
            f"intended={', '.join(item.get('intended_targets', [])) or 'none'} | guesses={guesses} | "
            f"correct={correct_guesses} | outcome={outcome}"
        )
    return "\n".join(lines)


def format_round_memory(round_summaries):
    if not round_summaries:
        return "No previous round summaries yet."

    lines = []
    for summary in round_summaries:
        interactions = []
        for item in summary.get("interactions", []):
            interactions.append(
                {
                    "turn": item.get("turn"),
                    "clue_giver": item.get("clue_giver"),
                    "guesser": item.get("guesser"),
                    "hint": item.get("hint"),
                    "hint_number": item.get("hint_number"),
                    "intended_targets": item.get("intended_targets", []),
                    "guesses": item.get("guesses", []),
                    "correct_guesses": item.get("correct_guesses", []),
                    "neutral_guesses": item.get("neutral_guesses", []),
                    "bomb_guess": item.get("bomb_guess"),
                    "outcome": item.get("outcome"),
                }
            )
        lines.append(
            json.dumps(
                {
                    "round": summary.get("round"),
                    "role": summary.get("role"),
                    "word_type": summary.get("word_type"),
                    "medal": summary.get("medal"),
                    "success": summary.get("success"),
                    "bomb_hit": summary.get("bomb_hit"),
                    "turns": summary.get("turns"),
                    "targets": summary.get("targets", []),
                    "bomb": summary.get("bomb"),
                    "found_targets": summary.get("found_targets", []),
                    "interactions": interactions,
                },
                ensure_ascii=False,
            )
        )
    return "\n".join(lines)


def previous_hints(history):
    return [
        item.get("hint", "").strip().lower()
        for item in history
        if item.get("hint")
    ]


def build_hint_system_prompt(history=None, used_hints=None):
    history = history or []
    used_hints = sorted(set(previous_hints(history) + (used_hints or [])))
    used_hints_clause = ""
    if used_hints:
        used_hints_clause = (
            f"8) Do not repeat any previous clue: {', '.join(used_hints)}.\n"
            "9) If a previous clue failed, avoid that association and choose a clearer one.\n"
        )

    return (
        "You are the AI clue-giver in a cooperative Codenames-like word game.\n"
        "You are trying to help your human teammate earn the best possible medal.\n"
        "There are four target words and one bomb word.\n"
        "Your job is to act like a thoughtful human teammate: give one natural clue word that "
        "points toward the largest safe cluster of remaining target words.\n\n"
        "Hard rules:\n"
        "1) Output exactly in the format HINT|N|target1,target2.\n"
        "2) HINT must be exactly one single English word.\n"
        "3) Never use any board word or any obvious morphological form of a board word.\n"
        "4) N must match the number of intended target words after the second pipe.\n"
        "5) The intended target words must be remaining target words only.\n"
        "6) Choose a clue that is helpful, human-like, and not too obscure.\n"
        "7) Use the interaction history. Avoid repeating failed associations and build on successful ones.\n"
        f"{used_hints_clause}"
        "Do not explain. Do not add extra text outside the required pipe-separated format."
    )


def build_hint_user_prompt(
    target_words,
    bomb_word,
    neutral_words,
    word_type,
    history,
    round_summaries=None,
):
    found_targets = {
        guess
        for item in history
        for guess in item.get("correct_guesses", [])
    }
    remaining_targets = [word for word in target_words if word not in found_targets]
    return (
        f"Word type: {word_type}\n"
        f"Remaining target words: {', '.join(remaining_targets)}\n"
        f"Already found targets: {', '.join(found_targets) or 'none'}\n"
        f"Neutral words: {', '.join(neutral_words)}\n"
        f"Bomb word: {bomb_word}\n\n"
        f"Previous round summaries for learning:\n{format_round_memory(round_summaries or [])}\n\n"
        f"Interaction history this round:\n{format_interaction_history(history)}\n\n"
        "Based on previous hints, guesses, successes, and failures, give a better clue for the "
        "remaining targets."
    )


def choose_fallback_hint(used_hints):
    used_hint_set = set(used_hints or [])
    for hint in FALLBACK_HINTS:
        if hint not in used_hint_set:
            return hint
    for hint in ["marker", "north", "south", "east", "west"]:
        if hint not in used_hint_set:
            return hint
    return "signal"


def generate_ai_hint(
    target_words,
    bomb_word,
    neutral_words,
    word_type,
    history=None,
    used_hints=None,
    round_summaries=None,
):
    history = history or []
    used_hints = used_hints or []
    used_hint_set = set(previous_hints(history) + used_hints)
    board_words = target_words + neutral_words + [bomb_word]
    fallback_number = remaining_target_count(target_words, history)
    found_targets = {
        guess
        for item in history
        for guess in item.get("correct_guesses", [])
    }
    remaining_targets = [word for word in target_words if word not in found_targets]

    for _ in range(3):
        raw = call_openai_chat(
            build_hint_system_prompt(history, used_hints),
            build_hint_user_prompt(
                target_words,
                bomb_word,
                neutral_words,
                word_type,
                history,
                round_summaries,
            ),
        )
        hint, hint_number, intended_targets = parse_hint_with_targets(
            raw, fallback_number, remaining_targets
        )
        if not intended_targets:
            intended_targets = remaining_targets[:hint_number]
        hint_number = min(hint_number, len(intended_targets), fallback_number)
        intended_targets = intended_targets[:hint_number]
        if (
            hint
            and hint not in used_hint_set
            and not is_hint_too_close_to_board(hint, board_words)
        ):
            return hint, hint_number, intended_targets

    fallback_targets = remaining_targets[: min(2, fallback_number)]
    return choose_fallback_hint(used_hint_set), len(fallback_targets), fallback_targets


def generate_ai_hint_reroll(
    target_words,
    bomb_word,
    neutral_words,
    word_type,
    previous_hint,
    history=None,
    used_hints=None,
    round_summaries=None,
):
    history = history or []
    used_hints = used_hints or []
    used_hint_set = set(previous_hints(history) + used_hints + [previous_hint])
    board_words = target_words + neutral_words + [bomb_word]
    fallback_number = remaining_target_count(target_words, history)
    found_targets = {
        guess
        for item in history
        for guess in item.get("correct_guesses", [])
    }
    remaining_targets = [word for word in target_words if word not in found_targets]

    for _ in range(3):
        raw = call_openai_chat(
            build_hint_system_prompt(history + [{"hint": previous_hint}], used_hints),
            build_hint_user_prompt(
                target_words,
                bomb_word,
                neutral_words,
                word_type,
                history,
                round_summaries,
            ),
        )
        hint, hint_number, intended_targets = parse_hint_with_targets(
            raw, fallback_number, remaining_targets
        )
        if not intended_targets:
            intended_targets = remaining_targets[:hint_number]
        hint_number = min(hint_number, len(intended_targets), fallback_number)
        intended_targets = intended_targets[:hint_number]
        if (
            hint
            and hint not in used_hint_set
            and not is_hint_too_close_to_board(hint, board_words)
        ):
            return hint, hint_number, intended_targets

    fallback_targets = remaining_targets[: min(1, fallback_number)]
    return choose_fallback_hint(used_hint_set), len(fallback_targets), fallback_targets


def ai_guess(
    board,
    hint,
    max_guesses,
    remaining_rerolls,
    history=None,
    previous_guesses=None,
    round_summaries=None,
):
    history = history or []
    previous_guesses = previous_guesses or []
    available_board = [word for word in board if word not in previous_guesses]
    system_prompt = (
        "You are the AI guesser in a cooperative Codenames-like word game.\n"
        "Your job is to help the team find all four targets while avoiding the bomb.\n\n"
        "Decision policy:\n"
        "1) Default behavior is to guess. Do not ask for a new clue just because a clue is imperfect.\n"
        "2) Only output REROLL_HINT if the clue is genuinely unusable: for example meaningless, unrelated to every board word, "
        "or so ambiguous that any guess would be close to random.\n"
        "3) If the clue plausibly points to one or more board words, you must guess.\n"
        "4) Output exactly either REROLL_HINT or exactly N comma-separated board words.\n"
        "5) Use the interaction history to avoid repeating previous guesses.\n"
        "6) Never explain your reasoning."
    )

    user_prompt = (
        f"Available board words: {', '.join(available_board)}\n"
        f"Previous guesses: {', '.join(previous_guesses) or 'none'}\n"
        f"Hint: {hint}\n"
        f"Maximum guesses (N): {max_guesses}\n"
        f"Remaining clue rerolls: {remaining_rerolls}\n\n"
        f"Previous round summaries for learning:\n{format_round_memory(round_summaries or [])}\n\n"
        f"Interaction history this round:\n{format_interaction_history(history)}\n\n"
        "Remember: reroll is a last resort. If there is any plausible interpretation, guess."
    )

    raw = call_openai_chat(system_prompt, user_prompt, temperature=0.2).strip()
    if raw.upper() == "REROLL_HINT" and remaining_rerolls > 0:
        return ["__REROLL_HINT__"]

    model_words = [part.strip().lower() for part in raw.split(",") if part.strip()]
    valid_words = []
    seen = set()
    board_lookup = {word.lower(): word for word in available_board}

    for word in model_words:
        if word in board_lookup and word not in seen:
            valid_words.append(board_lookup[word])
            seen.add(word)

    if len(valid_words) < max_guesses:
        remaining_choices = [word for word in available_board if word not in valid_words]
        needed = min(max_guesses - len(valid_words), len(remaining_choices))
        if needed > 0:
            valid_words.extend(random.sample(remaining_choices, needed))

    return valid_words[:max_guesses]


def validate_human_hint(hint, board_words):
    cleaned = hint.strip().lower()
    if not cleaned:
        return False, "Please enter a clue word."
    if not re.fullmatch(r"[a-z-]+", cleaned):
        return False, "The clue must be exactly one word."
    if is_hint_too_close_to_board(cleaned, board_words):
        return False, "This clue is too close to a board word. Please choose a different word."
    return True, ""


def validate_human_hint_with_history(hint, board_words, history, used_hints=None):
    is_valid, message = validate_human_hint(hint, board_words)
    if not is_valid:
        return is_valid, message

    cleaned = hint.strip().lower()
    if cleaned in set(previous_hints(history) + (used_hints or [])):
        return False, "You already used this clue. Please choose a new one-word clue."
    return True, ""
