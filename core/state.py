import uuid
import random
from datetime import datetime

import streamlit as st

from core.constants import AI_REROLLS_PER_GAME, HUMAN_REROLLS_PER_GAME

VALID_CONDITIONS = {"baseline", "adaptive"}
DEFAULT_CONDITION = "adaptive"


def _new_session_id():
    return str(uuid.uuid4())


def _condition_from_query_params():
    try:
        raw_value = st.query_params.get("condition", DEFAULT_CONDITION)
    except Exception:
        raw_value = DEFAULT_CONDITION
    if isinstance(raw_value, list):
        raw_value = raw_value[0] if raw_value else DEFAULT_CONDITION
    condition = str(raw_value or DEFAULT_CONDITION).strip().lower()
    return condition if condition in VALID_CONDITIONS else DEFAULT_CONDITION


def _new_starting_role():
    return random.choice(["human_clue", "ai_clue"])


def init_session_state():
    defaults = {
        "session_id": _new_session_id(),
        "condition": _condition_from_query_params(),
        "starting_role": _new_starting_role(),
        "started": False,
        "participant_id": None,
        "round": 1,
        "score": 0,
        "board": None,
        "role": None,
        "word_type": None,
        "board_template_type": "",
        "word_type_per_card": {},
        "used_board_words": [],
        "used_board_words_by_type": {"abstract": [], "concrete": []},
        "target_words": [],
        "bomb_words": [],
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
        "session_start_time": datetime.utcnow().isoformat(),
        "session_end_time": "",
        "session_log_initialized": False,
        "round_start_time": "",
        "logged_round_starts": [],
        "current_turn_start_time": "",
        "consent_given": False,
        "completion_code": "",
        "session_completed_logged": False,
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
        "pending_reflection_turn": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_round_state():
    st.session_state.board = None
    st.session_state.role = None
    st.session_state.word_type = None
    st.session_state.board_template_type = ""
    st.session_state.word_type_per_card = {}
    st.session_state.target_words = []
    st.session_state.bomb_words = []
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
    st.session_state.round_start_time = ""
    st.session_state.current_turn_start_time = ""
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
    st.session_state.pending_reflection_turn = None


def restart_game(keep_participant=False):
    participant_id = st.session_state.get("participant_id") if keep_participant else None
    condition = st.session_state.get("condition", DEFAULT_CONDITION)
    for key in list(st.session_state.keys()):
        del st.session_state[key]

    init_session_state()
    st.session_state.session_id = _new_session_id()
    st.session_state.condition = condition
    st.session_state.starting_role = _new_starting_role()
    st.session_state.session_start_time = datetime.utcnow().isoformat()
    st.session_state.session_end_time = ""
    st.session_state.session_log_initialized = False
    st.session_state.consent_given = False
    st.session_state.completion_code = ""
    st.session_state.session_completed_logged = False
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
    st.session_state.used_board_words = []
    st.session_state.used_board_words_by_type = {"abstract": [], "concrete": []}
    st.session_state.ai_round_summaries = []
    st.session_state.logged_round_starts = []
    st.session_state.remote_log_status = ""
    st.session_state.remote_log_error = ""
    st.session_state.start_time = datetime.utcnow()
