import uuid
import random
from datetime import datetime

import streamlit as st

from core.constants import AI_REROLLS_PER_GAME, HUMAN_REROLLS_PER_GAME

VALID_CONDITIONS = {"baseline", "adaptive"}
DEFAULT_CONDITION = "baseline"


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
        "condition_assigned": False,
        "starting_role": _new_starting_role(),
        "started": False,
        "participant_id": None,
        "nickname": "",
        "age_group": "",
        "gender": "",
        "english_proficiency": "",
        "ai_experience": "",
        "codenames_experience": "",
        "round": 1,
        "score": 0,
        "board": None,
        "role": None,
        "word_type": None,
        "board_template_type": "",
        "board_id": "",
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
        "hint_expected_guesses": [],
        "hint_explanation": "",
        "used_hints": [],
        "guesses": [],
        "pending_guesses": [],
        "current_guess_rationale": "",
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
        "current_hint_start_time": "",
        "current_guess_start_time": "",
        "current_reflection_start_time": "",
        "consent_given": False,
        "consent_timestamp": "",
        "debriefing_acknowledged": False,
        "debriefing_acknowledged_at": "",
        "completion_code": "",
        "session_completed_logged": False,
        "ai_clue_intro_seen": False,
        "post_game_questionnaire_submitted": False,
        "post_game_questionnaire": {},
        "perception_rating": None,
        "ai_understanding_rating_before": None,
        "ai_understanding_rating_after": None,
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
    st.session_state.board_id = ""
    st.session_state.word_type_per_card = {}
    st.session_state.target_words = []
    st.session_state.bomb_words = []
    st.session_state.bomb_word = None
    st.session_state.neutral_words = []
    st.session_state.word_roles = {}
    st.session_state.hint = ""
    st.session_state.hint_number = 1
    st.session_state.hint_targets = []
    st.session_state.hint_expected_guesses = []
    st.session_state.hint_explanation = ""
    st.session_state.guesses = []
    st.session_state.pending_guesses = []
    st.session_state.current_guess_rationale = ""
    st.session_state.found_targets = []
    st.session_state.interaction_history = []
    st.session_state.round_interactions = 0
    st.session_state.round_skips = 0
    st.session_state.round_finished = False
    st.session_state.start_time = None
    st.session_state.round_start_time = ""
    st.session_state.current_turn_start_time = ""
    st.session_state.current_hint_start_time = ""
    st.session_state.current_guess_start_time = ""
    st.session_state.current_reflection_start_time = ""
    st.session_state.perception_rating = None
    st.session_state.ai_understanding_rating_before = None
    st.session_state.ai_understanding_rating_after = None
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
    nickname = st.session_state.get("nickname") if keep_participant else ""
    age_group = st.session_state.get("age_group") if keep_participant else ""
    gender = st.session_state.get("gender") if keep_participant else ""
    english_proficiency = st.session_state.get("english_proficiency") if keep_participant else ""
    ai_experience = st.session_state.get("ai_experience") if keep_participant else ""
    codenames_experience = st.session_state.get("codenames_experience") if keep_participant else ""
    condition = st.session_state.get("condition", DEFAULT_CONDITION)
    condition_assigned = st.session_state.get("condition_assigned", False)
    for key in list(st.session_state.keys()):
        del st.session_state[key]

    init_session_state()
    st.session_state.session_id = _new_session_id()
    st.session_state.condition = condition
    st.session_state.condition_assigned = condition_assigned if keep_participant else False
    st.session_state.starting_role = _new_starting_role()
    st.session_state.session_start_time = datetime.utcnow().isoformat()
    st.session_state.session_end_time = ""
    st.session_state.session_log_initialized = False
    st.session_state.consent_given = False
    st.session_state.consent_timestamp = ""
    st.session_state.debriefing_acknowledged = False
    st.session_state.debriefing_acknowledged_at = ""
    st.session_state.completion_code = ""
    st.session_state.session_completed_logged = False
    st.session_state.ai_clue_intro_seen = False
    st.session_state.post_game_questionnaire_submitted = False
    st.session_state.post_game_questionnaire = {}
    if participant_id:
        st.session_state.started = True
        st.session_state.participant_id = participant_id
        st.session_state.nickname = nickname or participant_id
        st.session_state.age_group = age_group or ""
        st.session_state.gender = gender or ""
        st.session_state.english_proficiency = english_proficiency or ""
        st.session_state.ai_experience = ai_experience or ""
        st.session_state.codenames_experience = codenames_experience or ""
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
