import uuid
from datetime import datetime

import streamlit as st

from core.constants import AI_REROLLS_PER_GAME, HUMAN_REROLLS_PER_GAME


def _new_session_id():
    return str(uuid.uuid4())


def init_session_state():
    defaults = {
        "session_id": _new_session_id(),
        "started": False,
        "participant_id": None,
        "round": 1,
        "score": 0,
        "board": None,
        "role": None,
        "word_type": None,
        "target_words": [],
        "bomb_word": None,
        "neutral_words": [],
        "word_roles": {},
        "hint": "",
        "hint_number": 1,
        "hint_targets": [],
        "hint_explanation": "",
        "used_hints": [],
        "guesses": [],
        "pending_guesses": [],
        "found_targets": [],
        "interaction_history": [],
        "ai_round_summaries": [],
        "round_interactions": 0,
        "round_skips": 0,
        "round_finished": False,
        "start_time": None,
        "perception_rating": 3,
        "ai_understanding_rating_before": 3,
        "ai_understanding_rating_after": 3,
        "pending_ai_guess_review": None,
        "previous_hint": None,
        "last_ai_guesses": [],
        "last_ai_hint": "",
        "ai_round_reflection": "",
        "human_round_feedback": "",
        "ai_rerolls": AI_REROLLS_PER_GAME,
        "human_rerolls": HUMAN_REROLLS_PER_GAME,
        "game_over": False,
        "last_score_change": 0,
        "round_medal": "none",
        "round_success": False,
        "round_bomb_hit": False,
        "medal_counts": {"gold": 0, "silver": 0, "bronze": 0, "none": 0},
        "remote_log_status": "",
        "remote_log_error": "",
        "pending_hint_meta": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_round_state():
    st.session_state.board = None
    st.session_state.role = None
    st.session_state.word_type = None
    st.session_state.target_words = []
    st.session_state.bomb_word = None
    st.session_state.neutral_words = []
    st.session_state.word_roles = {}
    st.session_state.hint = ""
    st.session_state.hint_number = 1
    st.session_state.hint_targets = []
    st.session_state.hint_explanation = ""
    st.session_state.guesses = []
    st.session_state.pending_guesses = []
    st.session_state.found_targets = []
    st.session_state.interaction_history = []
    st.session_state.round_interactions = 0
    st.session_state.round_skips = 0
    st.session_state.round_finished = False
    st.session_state.start_time = None
    st.session_state.perception_rating = 3
    st.session_state.ai_understanding_rating_before = 3
    st.session_state.ai_understanding_rating_after = 3
    st.session_state.pending_ai_guess_review = None
    st.session_state.previous_hint = None
    st.session_state.last_ai_guesses = []
    st.session_state.last_ai_hint = ""
    st.session_state.ai_round_reflection = ""
    st.session_state.human_round_feedback = ""
    st.session_state.last_score_change = 0
    st.session_state.round_medal = "none"
    st.session_state.round_success = False
    st.session_state.round_bomb_hit = False
    st.session_state.pending_hint_meta = None


def restart_game(keep_participant=False):
    participant_id = st.session_state.get("participant_id") if keep_participant else None
    for key in list(st.session_state.keys()):
        del st.session_state[key]

    init_session_state()
    st.session_state.session_id = _new_session_id()
    if participant_id:
        st.session_state.started = True
        st.session_state.participant_id = participant_id
    reset_round_state()
    st.session_state.round = 1
    st.session_state.score = 0
    st.session_state.ai_rerolls = AI_REROLLS_PER_GAME
    st.session_state.human_rerolls = HUMAN_REROLLS_PER_GAME
    st.session_state.game_over = False
    st.session_state.medal_counts = {"gold": 0, "silver": 0, "bronze": 0, "none": 0}
    st.session_state.used_hints = []
    st.session_state.ai_round_summaries = []
    st.session_state.remote_log_status = ""
    st.session_state.remote_log_error = ""
    st.session_state.start_time = datetime.utcnow()
