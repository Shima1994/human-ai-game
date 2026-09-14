import uuid
import random
from datetime import datetime, timezone

import streamlit as st

from core.constants import (
    AI_REROLLS_PER_GAME,
    DEFAULT_CONDITION,
    HUMAN_REROLLS_PER_GAME,
    VALID_CONDITIONS,
)


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


def _device_type_from_user_agent(user_agent):
    ua = (user_agent or "").lower()
    if not ua:
        return "unknown"
    if "ipad" in ua or "tablet" in ua or ("android" in ua and "mobile" not in ua):
        return "tablet"
    if "mobi" in ua or "iphone" in ua or "android" in ua:
        return "mobile"
    return "desktop"


def _client_context_defaults():
    """Request metadata read server-side via st.context (Streamlit 1.37+):
    the real User-Agent header and the browser's own navigator.language,
    with no custom JS component needed. st.context is unavailable in some
    embedding/test contexts, so every access is defensive.

    screen_size has no server-side source (it's client-only) and is left as
    "unknown" until a small bidirectional JS component captures it.
    """
    user_agent = ""
    browser_language = ""
    try:
        user_agent = str(st.context.headers.get("User-Agent", "") or "")
    except Exception:
        pass
    try:
        browser_language = str(st.context.locale or "")
    except Exception:
        pass
    return {
        "user_agent": user_agent or "unknown",
        "device_type": _device_type_from_user_agent(user_agent),
        "browser_language": browser_language or "unknown",
    }


def init_session_state():
    client_context = _client_context_defaults()
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
        "tutorial_completed": False,
        "tutorial_step": "introduction",
        "tutorial_practice_started_at": "",
        "tutorial_practice_result": "",
        "tutorial_comprehension_result": "",
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
        "session_start_time": datetime.now(timezone.utc).isoformat(),
        "session_end_time": "",
        "user_agent": client_context["user_agent"],
        "device_type": client_context["device_type"],
        "screen_size": "unknown",
        "browser_language": client_context["browser_language"],
        "last_activity_at": "",
        "last_completed_stage": "",
        "session_end_reason": "",
        "withdrawal_requested": False,
        "technical_termination": False,
        "session_log_initialized": False,
        "round_start_time": "",
        "logged_round_starts": [],
        "current_turn_start_time": "",
        "current_hint_start_time": "",
        "current_guess_start_time": "",
        "current_reflection_start_time": "",
        "clue_timer_started_at": "",
        "clue_timer_duration_seconds": 0,
        "clue_timer_timeout_consumed": False,
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
        "round_end_reason": "",
        "medal_counts": {"gold": 0, "silver": 0, "none": 0},
        "remote_log_status": "",
        "remote_log_error": "",
        "pending_hint_meta": None,
        "pending_reflection_turn": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


