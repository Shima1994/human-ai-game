import random
from datetime import datetime

import streamlit as st

from core.constants import (
    BOARD_SIZE,
    BOMB_COUNT,
    MAX_INTERACTIONS_PER_ROUND,
    MAX_SKIPS_PER_ROUND,
    MEDAL_POINTS,
    TARGET_COUNT,
)
from core.words import FIXED_ROUND_BOARDS


def get_word_type_for_round(round_number):
    return FIXED_ROUND_BOARDS[round_number]["word_type"]


def get_role_for_round(round_number):
    return "human_clue" if round_number % 2 else "ai_clue"


def sample_fixed_round_words(round_number):
    board_words = FIXED_ROUND_BOARDS[round_number]["words"].copy()
    if len(board_words) != BOARD_SIZE:
        raise ValueError(f"Round {round_number} must contain exactly {BOARD_SIZE} words.")
    if len(set(word.lower() for word in board_words)) != BOARD_SIZE:
        raise ValueError(f"Round {round_number} contains duplicate board words.")

    shuffled_roles = board_words[:]
    random.shuffle(shuffled_roles)
    targets = shuffled_roles[:TARGET_COUNT]
    bombs = shuffled_roles[TARGET_COUNT : TARGET_COUNT + BOMB_COUNT]
    neutrals = shuffled_roles[TARGET_COUNT + BOMB_COUNT:]

    word_roles = {word: "target" for word in targets}
    word_roles.update({word: "neutral" for word in neutrals})
    word_roles.update({word: "bomb" for word in bombs})

    random.shuffle(board_words)
    return board_words, targets, neutrals, bombs, word_roles


def setup_new_round():
    word_type = get_word_type_for_round(st.session_state.round)
    role = get_role_for_round(st.session_state.round)
    board, targets, neutrals, bombs, word_roles = sample_fixed_round_words(
        st.session_state.round
    )

    st.session_state.word_type = word_type
    st.session_state.role = role
    st.session_state.board = board
    st.session_state.target_words = targets
    st.session_state.bomb_words = bombs
    st.session_state.neutral_words = neutrals
    st.session_state.bomb_word = bombs[0] if bombs else None
    st.session_state.word_roles = word_roles
    st.session_state.guesses = []
    st.session_state.pending_guesses = []
    st.session_state.found_targets = []
    st.session_state.interaction_history = []
    st.session_state.round_interactions = 0
    st.session_state.round_skips = 0
    st.session_state.round_finished = False
    st.session_state.hint = ""
    st.session_state.hint_number = 1
    st.session_state.hint_targets = []
    st.session_state.hint_explanation = ""
    st.session_state.last_ai_guesses = []
    st.session_state.last_ai_hint = ""
    st.session_state.perception_rating = 3
    st.session_state.ai_understanding_rating_before = 3
    st.session_state.ai_understanding_rating_after = 3
    st.session_state.pending_ai_guess_review = None
    st.session_state.previous_hint = None
    st.session_state.start_time = datetime.utcnow()
    st.session_state.last_score_change = 0
    st.session_state.round_medal = "none"
    st.session_state.round_success = False
    st.session_state.round_bomb_hit = False
    st.session_state.ai_round_reflection = ""
    st.session_state.human_round_feedback = ""
    st.session_state.pending_hint_meta = None


def get_medal_for_round(interactions, success, bomb_hit):
    if bomb_hit or not success:
        return "none"
    if interactions <= 2:
        return "gold"
    if interactions == 3:
        return "silver"
    if interactions == 4:
        return "bronze"
    return "none"


def compute_score_change(guesses, target_words, bomb_words, interactions=None):
    if isinstance(bomb_words, str) or bomb_words is None:
        bomb_words = [bomb_words] if bomb_words else []
    bomb_hit = any(guess in bomb_words for guess in guesses)
    found_targets = {guess for guess in guesses if guess in target_words}
    success = len(found_targets) == len(target_words)
    if interactions is None:
        interactions = st.session_state.get("round_interactions", 0)
    medal = get_medal_for_round(interactions, success, bomb_hit)
    return MEDAL_POINTS[medal]


def record_interaction(
    hint,
    hint_number,
    guesses,
    intended_targets=None,
    hint_explanation="",
    ai_understanding_rating_before=None,
    ai_understanding_rating_after=None,
    hint_raw_response="",
    hint_response_time_sec=None,
    hint_attempts=None,
    hint_used_fallback=False,
    guess_raw_response="",
    guess_response_time_sec=None,
):
    intended_targets = intended_targets or []
    normalized_hint = hint.strip().lower()
    correct_guesses = [guess for guess in guesses if guess in st.session_state.target_words]
    neutral_guesses = [guess for guess in guesses if guess in st.session_state.neutral_words]
    bomb_words = st.session_state.get("bomb_words") or [st.session_state.bomb_word]
    bomb_guesses = [guess for guess in guesses if guess in bomb_words]
    bomb_hit = bool(bomb_guesses)
    bomb_guess = ";".join(bomb_guesses) if bomb_guesses else None
    new_targets = [
        guess
        for guess in correct_guesses
        if guess not in st.session_state.found_targets
    ]
    clue_giver = "human" if st.session_state.role == "human_clue" else "ai"
    guesser = "ai" if st.session_state.role == "human_clue" else "human"
    if bomb_hit:
        outcome = "bomb"
    elif correct_guesses:
        outcome = "correct"
    else:
        outcome = "wrong"

    st.session_state.round_interactions += 1
    st.session_state.guesses.extend(
        guess for guess in guesses if guess not in st.session_state.guesses
    )
    st.session_state.found_targets.extend(new_targets)
    if normalized_hint and normalized_hint not in st.session_state.used_hints:
        st.session_state.used_hints.append(normalized_hint)
    st.session_state.interaction_history.append(
        {
            "turn": st.session_state.round_interactions,
            "clue_giver": clue_giver,
            "guesser": guesser,
            "hint": normalized_hint,
            "hint_number": hint_number,
            "intended_targets": intended_targets,
            "hint_explanation": hint_explanation,
            "guesses": guesses,
            "correct": bool(correct_guesses),
            "correct_guesses": correct_guesses,
            "neutral_guesses": neutral_guesses,
            "bomb_guesses": bomb_guesses,
            "bomb_guess": bomb_guess,
            "bomb_hit": bomb_hit,
            "outcome": outcome,
            "ai_understanding_rating_before": ai_understanding_rating_before,
            "ai_understanding_rating_after": ai_understanding_rating_after,
            "hint_raw_response": hint_raw_response,
            "hint_response_time_sec": hint_response_time_sec,
            "hint_attempts": hint_attempts,
            "hint_used_fallback": bool(hint_used_fallback),
            "guess_raw_response": guess_raw_response,
            "guess_response_time_sec": guess_response_time_sec,
            "recorded_at": datetime.utcnow().isoformat(),
        }
    )

    if (
        bomb_hit
        or len(st.session_state.found_targets) == len(st.session_state.target_words)
        or st.session_state.round_interactions >= MAX_INTERACTIONS_PER_ROUND
    ):
        finish_round()


def can_skip_current_clue():
    return (
        st.session_state.get("round_skips", 0) < MAX_SKIPS_PER_ROUND
        and st.session_state.get("round_interactions", 0) < MAX_INTERACTIONS_PER_ROUND - 1
    )


def record_skip(
    hint,
    hint_number,
    intended_targets=None,
    hint_explanation="",
    skipped_by=None,
    hint_raw_response="",
    hint_response_time_sec=None,
    hint_attempts=None,
    hint_used_fallback=False,
    guess_raw_response="",
    guess_response_time_sec=None,
):
    intended_targets = intended_targets or []
    normalized_hint = hint.strip().lower()
    clue_giver = "human" if st.session_state.role == "human_clue" else "ai"
    guesser = "ai" if st.session_state.role == "human_clue" else "human"
    skipped_by = skipped_by or guesser

    st.session_state.round_interactions += 1
    st.session_state.round_skips = st.session_state.get("round_skips", 0) + 1
    if normalized_hint and normalized_hint not in st.session_state.used_hints:
        st.session_state.used_hints.append(normalized_hint)
    st.session_state.interaction_history.append(
        {
            "turn": st.session_state.round_interactions,
            "clue_giver": clue_giver,
            "guesser": guesser,
            "hint": normalized_hint,
            "hint_number": hint_number,
            "intended_targets": intended_targets,
            "hint_explanation": hint_explanation,
            "guesses": [],
            "correct": False,
            "correct_guesses": [],
            "neutral_guesses": [],
            "bomb_guesses": [],
            "bomb_guess": None,
            "bomb_hit": False,
            "outcome": "skip",
            "skipped": True,
            "skipped_by": skipped_by,
            "ai_understanding_rating_before": None,
            "ai_understanding_rating_after": None,
            "hint_raw_response": hint_raw_response,
            "hint_response_time_sec": hint_response_time_sec,
            "hint_attempts": hint_attempts,
            "hint_used_fallback": bool(hint_used_fallback),
            "guess_raw_response": guess_raw_response,
            "guess_response_time_sec": guess_response_time_sec,
            "recorded_at": datetime.utcnow().isoformat(),
        }
    )

    if st.session_state.round_interactions >= MAX_INTERACTIONS_PER_ROUND:
        finish_round()


def finish_round():
    st.session_state.round_finished = True
    bomb_words = st.session_state.get("bomb_words") or [st.session_state.bomb_word]
    st.session_state.round_bomb_hit = any(
        guess in bomb_words for guess in st.session_state.guesses
    )
    st.session_state.round_success = (
        len(st.session_state.found_targets) == len(st.session_state.target_words)
    )
    st.session_state.round_medal = get_medal_for_round(
        st.session_state.round_interactions,
        st.session_state.round_success,
        st.session_state.round_bomb_hit,
    )
    st.session_state.last_score_change = MEDAL_POINTS[st.session_state.round_medal]
    append_ai_round_summary()


def append_ai_round_summary():
    if any(
        item.get("round") == st.session_state.round
        for item in st.session_state.ai_round_summaries
    ):
        return

    st.session_state.ai_round_summaries.append(
        {
            "round": st.session_state.round,
            "role": st.session_state.role,
            "word_type": st.session_state.word_type,
            "targets": list(st.session_state.target_words),
            "bomb": list(st.session_state.get("bomb_words", [])),
            "success": bool(st.session_state.round_success),
            "bomb_hit": bool(st.session_state.round_bomb_hit),
            "medal": st.session_state.round_medal,
            "turns": st.session_state.round_interactions,
            "found_targets": list(st.session_state.found_targets),
            "skips": st.session_state.get("round_skips", 0),
            "interactions": [
                {
                    "turn": item.get("turn"),
                    "clue_giver": item.get("clue_giver"),
                    "guesser": item.get("guesser"),
                    "hint": item.get("hint"),
                    "hint_number": item.get("hint_number"),
                    "intended_targets": list(item.get("intended_targets", [])),
                    "hint_explanation": item.get("hint_explanation", ""),
                    "guesses": list(item.get("guesses", [])),
                    "correct_guesses": list(item.get("correct_guesses", [])),
                    "neutral_guesses": list(item.get("neutral_guesses", [])),
                    "bomb_guesses": list(item.get("bomb_guesses", [])),
                    "bomb_guess": item.get("bomb_guess"),
                    "outcome": item.get("outcome"),
                    "skipped": bool(item.get("skipped", False)),
                    "skipped_by": item.get("skipped_by"),
                    "ai_understanding_rating_before": item.get("ai_understanding_rating_before"),
                    "ai_understanding_rating_after": item.get("ai_understanding_rating_after"),
                }
                for item in st.session_state.interaction_history
            ],
            "ai_reflection": st.session_state.get("ai_round_reflection", ""),
            "human_feedback": st.session_state.get("human_round_feedback", ""),
        }
    )


def update_current_round_summary():
    for summary in st.session_state.ai_round_summaries:
        if summary.get("round") == st.session_state.round:
            summary["ai_reflection"] = st.session_state.get("ai_round_reflection", "")
            summary["human_feedback"] = st.session_state.get("human_round_feedback", "")
            return
