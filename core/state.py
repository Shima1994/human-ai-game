from datetime import datetime

import streamlit as st

from core.constants import AI_REROLLS_PER_GAME, HUMAN_REROLLS_PER_GAME
from core.words import ABSTRACT_CATEGORIES, CONCRETE_CATEGORIES


def _fresh_pools():
    return {
        "abstract_pools": {
            category: words.copy() for category, words in ABSTRACT_CATEGORIES.items()
        },
        "concrete_pools": {
            category: words.copy() for category, words in CONCRETE_CATEGORIES.items()
        },
    }


def init_session_state():
    defaults = {
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
        "guesses": [],
        "round_finished": False,
        "start_time": None,
        "perception_rating": 3,
        "golden_target": None,
        "previous_hint": None,
        "ai_rerolls": AI_REROLLS_PER_GAME,
        "human_rerolls": HUMAN_REROLLS_PER_GAME,
        "game_over": False,
        "last_score_change": 0,
    }
    defaults.update(_fresh_pools())

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
    st.session_state.guesses = []
    st.session_state.round_finished = False
    st.session_state.start_time = None
    st.session_state.perception_rating = 3
    st.session_state.golden_target = None
    st.session_state.previous_hint = None
    st.session_state.last_score_change = 0


def restart_game(keep_participant=False):
    participant_id = st.session_state.get("participant_id") if keep_participant else None
    for key in list(st.session_state.keys()):
        del st.session_state[key]

    init_session_state()
    if participant_id:
        st.session_state.started = True
        st.session_state.participant_id = participant_id
    reset_round_state()
    st.session_state.round = 1
    st.session_state.score = 0
    st.session_state.ai_rerolls = AI_REROLLS_PER_GAME
    st.session_state.human_rerolls = HUMAN_REROLLS_PER_GAME
    st.session_state.game_over = False
    st.session_state.start_time = datetime.utcnow()
