import csv
from datetime import datetime

import streamlit as st

from core.constants import DATA_FILE
from core.game_logic import compute_score_change


def ensure_data_file():
    if not DATA_FILE.exists():
        with DATA_FILE.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
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
                    "guesses",
                    "correct",
                    "bomb_hit",
                    "score_change",
                    "response_time_sec",
                    "perception_rating",
                ]
            )


def log_round(participant_id):
    ensure_data_file()

    guesses = st.session_state.guesses
    correct = any(guess in st.session_state.target_words for guess in guesses)
    bomb_hit = any(guess == st.session_state.bomb_word for guess in guesses)
    score_change = compute_score_change(
        guesses,
        st.session_state.target_words,
        st.session_state.golden_target,
        st.session_state.bomb_word,
    )

    response_time = None
    if st.session_state.start_time is not None:
        response_time = (datetime.utcnow() - st.session_state.start_time).total_seconds()

    with DATA_FILE.open("a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                datetime.utcnow().isoformat(),
                participant_id,
                st.session_state.round,
                st.session_state.role,
                st.session_state.word_type,
                ";".join(st.session_state.board),
                ";".join(st.session_state.target_words),
                st.session_state.bomb_word,
                st.session_state.hint,
                st.session_state.hint_number,
                ";".join(guesses),
                int(correct),
                int(bomb_hit),
                score_change,
                response_time,
                st.session_state.perception_rating,
            ]
        )

    st.session_state.last_score_change = score_change
    st.session_state.score += score_change
