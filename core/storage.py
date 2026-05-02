import csv
import json
from datetime import datetime

import streamlit as st

from core.constants import DATA_FILE
from core.game_logic import compute_score_change

ROUND_LOG_FIELDS = [
    "timestamp",
    "participant_id",
    "round",
    "role",
    "word_type",
    "board",
    "targets",
    "bomb",
    "hint",
    "hint_number",
    "intended_targets",
    "guesses",
    "interaction_history",
    "turns",
    "targets_found",
    "correct",
    "bomb_hit",
    "medal",
    "score_change",
    "response_time_sec",
    "perception_rating",
]

INTERACTION_LOG_FIELDS = [
    "timestamp",
    "participant_id",
    "round",
    "role",
    "word_type",
    "turn",
    "clue_giver",
    "guesser",
    "hint",
    "hint_number",
    "intended_targets",
    "guesses",
    "correct_guesses",
    "missed_intended_targets",
    "extra_correct_guesses",
    "neutral_guesses",
    "bomb_guess",
    "outcome",
    "bomb_hit",
    "round_medal",
    "round_success",
    "perception_rating",
]


def get_data_file():
    if not DATA_FILE.exists():
        return DATA_FILE

    with DATA_FILE.open("r", newline="", encoding="utf-8") as file:
        reader = csv.reader(file)
        header = next(reader, [])

    if header == ROUND_LOG_FIELDS:
        return DATA_FILE

    multi_round_file = DATA_FILE.with_name("game_data_multi_round.csv")
    if multi_round_file.exists():
        with multi_round_file.open("r", newline="", encoding="utf-8") as file:
            reader = csv.reader(file)
            multi_round_header = next(reader, [])
        if multi_round_header == ROUND_LOG_FIELDS:
            return multi_round_file
        return DATA_FILE.with_name("game_data_multi_round_intended.csv")

    return multi_round_file


def ensure_data_file():
    data_file = get_data_file()
    if not data_file.exists():
        with data_file.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(ROUND_LOG_FIELDS)
    return data_file


def get_interaction_data_file():
    return DATA_FILE.with_name("game_interactions.csv")


def ensure_interaction_data_file():
    data_file = get_interaction_data_file()
    if not data_file.exists():
        with data_file.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(INTERACTION_LOG_FIELDS)
    return data_file


def clean_interaction_history(history):
    clean_items = []
    for index, item in enumerate(history, start=1):
        guesses = list(item.get("guesses", []))
        correct_guesses = list(item.get("correct_guesses", []))
        intended_targets = list(item.get("intended_targets", []))
        clean_items.append(
            {
                "turn": index,
                "clue_giver": item.get("clue_giver", ""),
                "guesser": item.get("guesser", ""),
                "hint": item.get("hint", ""),
                "hint_number": int(item.get("hint_number", 0) or 0),
                "intended_targets": intended_targets,
                "guesses": guesses,
                "correct_guesses": correct_guesses,
                "missed_intended_targets": [
                    word for word in intended_targets if word not in correct_guesses
                ],
                "extra_correct_guesses": [
                    word for word in correct_guesses if word not in intended_targets
                ],
                "neutral_guesses": list(item.get("neutral_guesses", [])),
                "bomb_guess": item.get("bomb_guess"),
                "outcome": item.get("outcome", "correct" if correct_guesses else "wrong"),
                "bomb_hit": bool(item.get("bomb_hit", False)),
            }
        )
    return clean_items


def log_round(participant_id):
    data_file = ensure_data_file()
    interaction_data_file = ensure_interaction_data_file()
    timestamp = datetime.utcnow().isoformat()

    guesses = st.session_state.guesses
    correct = any(guess in st.session_state.target_words for guess in guesses)
    bomb_hit = any(guess == st.session_state.bomb_word for guess in guesses)
    score_change = compute_score_change(
        guesses,
        st.session_state.target_words,
        st.session_state.bomb_word,
        st.session_state.round_interactions,
    )
    intended_targets = [
        item.get("intended_targets", [])
        for item in st.session_state.interaction_history
    ]
    clean_history = clean_interaction_history(st.session_state.interaction_history)

    response_time = None
    if st.session_state.start_time is not None:
        response_time = (datetime.utcnow() - st.session_state.start_time).total_seconds()

    with data_file.open("a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                timestamp,
                participant_id,
                st.session_state.round,
                st.session_state.role,
                st.session_state.word_type,
                ";".join(st.session_state.board),
                ";".join(st.session_state.target_words),
                st.session_state.bomb_word,
                st.session_state.hint,
                st.session_state.hint_number,
                json.dumps(intended_targets, ensure_ascii=False),
                ";".join(guesses),
                json.dumps(clean_history, ensure_ascii=False),
                st.session_state.round_interactions,
                len(st.session_state.found_targets),
                int(correct),
                int(bomb_hit),
                st.session_state.round_medal,
                score_change,
                response_time,
                st.session_state.perception_rating,
            ]
        )

    with interaction_data_file.open("a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        for item in clean_history:
            writer.writerow(
                [
                    timestamp,
                    participant_id,
                    st.session_state.round,
                    st.session_state.role,
                    st.session_state.word_type,
                    item["turn"],
                    item["clue_giver"],
                    item["guesser"],
                    item["hint"],
                    item["hint_number"],
                    ";".join(item["intended_targets"]),
                    ";".join(item["guesses"]),
                    ";".join(item["correct_guesses"]),
                    ";".join(item["missed_intended_targets"]),
                    ";".join(item["extra_correct_guesses"]),
                    ";".join(item["neutral_guesses"]),
                    item["bomb_guess"] or "",
                    item["outcome"],
                    int(item["bomb_hit"]),
                    st.session_state.round_medal,
                    int(st.session_state.round_success),
                    st.session_state.perception_rating,
                ]
            )

    st.session_state.last_score_change = score_change
    st.session_state.score += score_change
