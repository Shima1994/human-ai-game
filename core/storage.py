import json
from datetime import datetime

import psycopg2
import streamlit as st

from core import db
from core.constants import (
    CODE_COMMIT,
    CONDITION_ASSIGNMENT_VERSION,
    DEFAULT_CONDITION,
    DEPLOYMENT_VERSION,
    EXPERIMENT_VERSION,
    GUESS_MODEL_NAME,
    HINT_MODEL_NAME,
    MODEL_IDENTIFIER,
    N_ROUNDS,
    REFLECTION_MODEL_NAME,
    SCHEMA_VERSION,
    VALID_CONDITIONS,
)
from core.game_logic import compute_score_change


# Field lists are the canonical schema: every key inside a row's JSONB `data`
# document. core/db.py's SCHEMA_SQL only declares the small set of real,
# indexed columns used for joins and filtering; these lists are what the
# thesis's data-collection description (System Description 3.5) refers to.
SESSIONS_LOG_FIELDS = [
    "participant_id",
    "nickname",
    "age_group",
    "gender",
    "english_proficiency",
    "ai_experience",
    "codenames_experience",
    "session_id",
    "condition",
    "starting_role",
    "start_time",
    "end_time",
    "completed",
    "consent_given",
    "total_rounds_planned",
    "total_rounds_completed",
    "total_turns_completed",
    "final_total_score",
    "user_agent",
    "device_type",
    "screen_size",
    "browser_language",
    "completion_code",
    "post_game_i_understood_ai_clues",
    "post_game_predict_ai_interpretation",
    "post_game_adapted_to_ai_behavior",
    "post_game_reflection_helped",
    "post_game_shared_understanding",
    "post_game_questionnaire_json",
    "ai_post_game_i_understood_human_clues",
    "ai_post_game_predict_human_interpretation",
    "ai_post_game_adapted_to_human_behavior",
    "ai_post_game_reflection_helped",
    "ai_post_game_shared_understanding",
    "ai_post_game_reasoning",
    "ai_post_game_questionnaire_json",
    "experiment_version",
    "schema_version",
    "code_commit",
    "deployment_version",
    "model_identifier",
    "condition_assignment_version",
    "last_activity_at",
    "last_completed_stage",
    "session_end_reason",
    "withdrawal_requested",
    "technical_termination",
]


ROUNDS_LOG_FIELDS = [
    "participant_id",
    "session_id",
    "condition",
    "round_number",
    "round_role",
    "clue_giver",
    "guesser",
    "board_template_type",
    "board_id",
    "all_board_words",
    "word_type_per_card",
    "target_words",
    "target_word_types",
    "neutral_words",
    "neutral_word_types",
    "bomb_words",
    "bomb_word_types",
    "remaining_targets_start",
    "remaining_targets_end",
    "number_of_turns",
    "round_score",
    "medal",
    "round_completed",
    "round_terminated_by_bomb",
    "bomb_selected",
    "selected_bomb_words",
    "round_start_time",
    "round_end_time",
    "round_duration_seconds",
    "round_end_reason",
    "ai_round_reflection",
    "human_round_feedback",
]


TURNS_LOG_FIELDS = [
    "participant_id",
    "session_id",
    "condition",
    "round_number",
    "turn_number",
    "action_type",
    "alignment_applicability",
    "completed_turn_number",
    "skip_number",
    "clue_giver",
    "guesser",
    "clue",
    "clue_number",
    "hint_explanation",
    "hint_attempts",
    "board_id",
    "outcome",
    "bomb_hit",
    "intended_cards",
    "intended_word_types",
    "expected_guess_cards",
    "expected_guess_word_types",
    "guess_rationale",
    "guess_rationale_word_count",
    "guessed_cards",
    "guess_order",
    "guess_order_json",
    "guessed_word_types",
    "correct_guesses",
    "correct_guess_word_types",
    "incorrect_guesses",
    "incorrect_guess_word_types",
    "missed_intended_targets",
    "extra_correct_guesses",
    "neutral_guesses",
    "neutral_guess_word_types",
    "bomb_guesses",
    "bomb_guess_word_types",
    "remaining_targets_before_turn",
    "remaining_targets_after_turn",
    "hint_time_sec",
    "guess_time_sec",
    "hit_rate",
    "target_yield",
    "jaccard_alignment",
    "alignment_status",
    "error_type",
    "turn_score_delta",
    "turn_start_time",
    "turn_end_time",
    "turn_duration_seconds",
    "partial_skip",
    "skip_interpreted_cards",
    "skip_interpreted_word_types",
    "skip_interpreted_count",
    "wrong_guess_replacements",
    "wrong_guess_replacement_word_types",
    "wrong_guess_replacement_count",
    "wrong_guess_replacement_actor",
    "wrong_guess_replacement_raw_response",
    "wrong_guess_replacement_response_time_sec",
    "wrong_guess_replacement_attempts",
    "completed_guesses",
    "skipped_guesses",
    "reflection_shown",
    "reflection_start_time",
    "reflection_end_time",
    "reflection_time_sec",
    "reflection_source",
    "ai_understanding_rating_before",
    "ai_understanding_rating_after",
    "human_understanding_rating_before",
    "human_understanding_rating",
    "human_relationship_type",
    "human_explanation_raw",
    "human_explanation_sanitized",
    "human_explanation_is_valid",
    "human_explanation_blocked_reason",
    "human_explanation_source",
    "human_explanation_collected_at",
    "ai_relationship_type",
    "ai_explanation_raw",
    "ai_explanation_sanitized",
    "ai_explanation_is_valid",
    "ai_explanation_blocked_reason",
    "ai_explanation",
    "repair_applied_to_next_prompt",
    "repair_context_used",
    "repair_required",
    "repair_source_turn",
    "repair_source_targets",
    "repair_chain_id",
    "repair_attempt_number",
    "repair_attempt",
    "repair_same_targets_retried",
    "repair_success",
    "timer_duration_seconds",
    "clue_timer_started_at",
    "human_decision_started_at",
    "human_decision_ended_at",
    "human_decision_time_sec",
    "human_timed_out",
    "timeout_timestamp",
    "timed_out",
    "timeout_repair_attempt",
    "timeout_selected_cards",
    "llm_model",
    "llm_temperature",
    "llm_prompt_version",
    "llm_system_prompt_version",
    "llm_response_raw",
    "llm_response_parsed",
    "llm_error",
    "llm_latency_seconds",
]


EVENTS_LOG_FIELDS = [
    "participant_id",
    "session_id",
    "condition",
    "timestamp",
    "event_type",
    "round_number",
    "turn_number",
    "event_payload",
]


SESSION_STAGES = frozenset(
    {
        "consent",
        "game_guide",
        "participant_profile",
        "tutorial",
        "gameplay",
        "post_study_questionnaire",
        "debriefing",
        "completed",
    }
)
SESSION_END_REASONS = frozenset({"completed", "participant_withdrawal", "technical_termination"})
ACTION_TYPES = frozenset({"interaction", "full_skip", "partial_skip", "timeout"})
ALIGNMENT_APPLICABILITY_VALUES = frozenset(
    {
        "observed_completed_selection",
        "partial_selection",
        "interpreted_only_skip",
        "timeout_no_behavioral_selection",
        "not_applicable",
    }
)
ROUND_END_REASONS = frozenset(
    {"all_targets_found", "bomb", "completed_turn_limit"}
)


# The real (non-JSONB) columns declared in core/db.py's SCHEMA_SQL for each
# table, kept in one place so the flat analysis views below don't duplicate
# a JSONB copy of a column that already exists as a real column.
_SESSIONS_REAL_COLUMNS = ["participant_id", "session_id", "condition", "completed", "last_completed_stage"]
_ROUNDS_REAL_COLUMNS = ["session_id", "round_number", "condition"]
_TURNS_REAL_COLUMNS = [
    "session_id",
    "round_number",
    "turn_number",
    "condition",
    "action_type",
    "alignment_applicability",
]

_flat_views_ready = False


def ensure_flat_views():
    """Create/refresh turns_flat, rounds_flat, sessions_flat: one plain text
    column per field (no JSON to unpack), for direct use in R/pandas/SPSS/Excel.
    Safe to call repeatedly; only does real work once per process."""
    global _flat_views_ready
    if _flat_views_ready:
        return
    db.ensure_flat_views(
        [
            ("sessions_flat", "sessions", _SESSIONS_REAL_COLUMNS, SESSIONS_LOG_FIELDS),
            ("rounds_flat", "rounds", _ROUNDS_REAL_COLUMNS, ROUNDS_LOG_FIELDS),
            ("turns_flat", "turns", _TURNS_REAL_COLUMNS, TURNS_LOG_FIELDS),
        ]
    )
    _flat_views_ready = True


def _json(value):
    return json.dumps(value if value is not None else [], ensure_ascii=False)


def _json_obj(value):
    return json.dumps(value if value is not None else {}, ensure_ascii=False)


def _set_remote_saved():
    if st.session_state.get("remote_log_status") != "db_failed":
        st.session_state.remote_log_status = "db_saved"
        st.session_state.remote_log_error = ""


def _set_remote_failure(error):
    st.session_state.remote_log_status = "db_failed"
    existing = str(st.session_state.get("remote_log_error", "") or "")
    message = str(error)
    st.session_state.remote_log_error = (
        f"{existing}; {message}" if existing and message not in existing else existing or message
    )


def clean_interaction_history(history):
    clean_items = []
    for index, item in enumerate(history, start=1):
        guesses = list(item.get("guesses", []))
        correct_guesses = list(item.get("correct_guesses", []))
        intended_targets = list(item.get("intended_targets", []))
        expected_guesses = list(item.get("expected_guesses", []))
        guess_order = list(
            item.get("guess_order")
            or [
                {"position": position, "word": guess}
                for position, guess in enumerate(guesses, start=1)
            ]
        )
        clean_items.append(
            {
                "turn": index,
                "completed_turn_number": item.get("completed_turn_number", index),
                "skip_number": item.get("skip_number", ""),
                "clue_giver": item.get("clue_giver", ""),
                "guesser": item.get("guesser", ""),
                "hint": item.get("hint", ""),
                "hint_number": int(item.get("hint_number", 0) or 0),
                "intended_targets": intended_targets,
                "expected_guesses": expected_guesses,
                "guess_rationale": item.get("guess_rationale", ""),
                "guess_rationale_word_count": item.get("guess_rationale_word_count", 0),
                "hint_explanation": item.get("hint_explanation", ""),
                "guesses": guesses,
                "guess_order": guess_order,
                "correct_guesses": correct_guesses,
                "incorrect_guesses": [
                    word for word in guesses if word not in correct_guesses
                ],
                "missed_intended_targets": [
                    word for word in intended_targets if word not in correct_guesses
                ],
                "extra_correct_guesses": [
                    word for word in correct_guesses if word not in intended_targets
                ],
                "neutral_guesses": list(item.get("neutral_guesses", [])),
                "bomb_guesses": list(item.get("bomb_guesses", [])),
                "bomb_guess": item.get("bomb_guess"),
                "outcome": item.get("outcome", "correct" if correct_guesses else "wrong"),
                "alignment_status": item.get("alignment_status", ""),
                "error_type": item.get("error_type", "none"),
                "skipped": bool(item.get("skipped", False)),
                "skipped_by": item.get("skipped_by", ""),
                "partial_skip": bool(item.get("partial_skip", False)),
                "skip_interpreted_cards": list(
                    item.get("skip_interpreted_cards", [])
                ),
                "repair_required": bool(item.get("repair_required", False)),
                "repair_source_turn": item.get("repair_source_turn", ""),
                "repair_source_targets": list(item.get("repair_source_targets", [])),
                "repair_chain_id": item.get("repair_chain_id", ""),
                "repair_attempt_number": item.get("repair_attempt_number", ""),
                "repair_attempt": bool(item.get("repair_attempt", False)),
                "repair_same_targets_retried": bool(item.get("repair_same_targets_retried", False)),
                "repair_success": bool(item.get("repair_success", False)),
                "timer_duration_seconds": item.get("timer_duration_seconds", ""),
                "clue_timer_started_at": item.get("clue_timer_started_at", ""),
                "human_decision_started_at": item.get("human_decision_started_at", ""),
                "human_decision_ended_at": item.get("human_decision_ended_at", ""),
                "human_decision_time_sec": item.get("human_decision_time_sec", ""),
                "human_timed_out": bool(item.get("human_timed_out", item.get("timed_out", False))),
                "timeout_timestamp": item.get("timeout_timestamp", ""),
                "timed_out": bool(item.get("timed_out", False)),
                "timeout_repair_attempt": bool(item.get("timeout_repair_attempt", False)),
                "timeout_selected_cards": list(item.get("timeout_selected_cards", [])),
                "wrong_guess_replacements": list(
                    item.get("wrong_guess_replacements", [])
                ),
                "wrong_guess_replacement_actor": item.get(
                    "wrong_guess_replacement_actor", ""
                ),
                "wrong_guess_replacement_raw_response": item.get(
                    "wrong_guess_replacement_raw_response", ""
                ),
                "wrong_guess_replacement_response_time_sec": item.get(
                    "wrong_guess_replacement_response_time_sec", ""
                ),
                "wrong_guess_replacement_attempts": item.get(
                    "wrong_guess_replacement_attempts", ""
                ),
                "completed_guesses": item.get("completed_guesses", len(guesses)),
                "skipped_guesses": item.get("skipped_guesses", 0),
                "bomb_hit": bool(item.get("bomb_hit", False)),
                "ai_understanding_rating_before": item.get("ai_understanding_rating_before"),
                "ai_understanding_rating_after": item.get("ai_understanding_rating_after"),
                "human_understanding_rating_before": item.get("human_understanding_rating_before"),
                "hint_raw_response": item.get("hint_raw_response", ""),
                "hint_response_time_sec": item.get("hint_response_time_sec"),
                "hint_attempts": item.get("hint_attempts"),
                "guess_raw_response": item.get("guess_raw_response", ""),
                "hint_time_sec": item.get("hint_time_sec"),
                "guess_time_sec": item.get("guess_time_sec"),
                "guess_response_time_sec": item.get("guess_response_time_sec"),
                "remaining_targets_before_turn": list(item.get("remaining_targets_before_turn", [])),
                "remaining_targets_after_turn": list(item.get("remaining_targets_after_turn", [])),
                "hit_rate": item.get("hit_rate", ""),
                "target_yield": item.get("target_yield", ""),
                "jaccard_alignment": item.get("jaccard_alignment", ""),
                "turn_score_delta": item.get("turn_score_delta", ""),
                "turn_start_time": item.get("turn_start_time", ""),
                "turn_end_time": item.get("turn_end_time", ""),
                "turn_duration_seconds": item.get("turn_duration_seconds", ""),
                "reflection_start_time": item.get("reflection_start_time", ""),
                "reflection_end_time": item.get("reflection_end_time", ""),
                "reflection_time_sec": item.get("reflection_time_sec", ""),
                "reflection_rating": item.get("reflection_rating", ""),
                "reflection_relationship_type": item.get("reflection_relationship_type", ""),
                "reflection_explanation_raw": item.get("reflection_explanation_raw", ""),
                "reflection_explanation_is_valid": item.get("reflection_explanation_is_valid", ""),
                "reflection_blocked_reason": item.get("reflection_blocked_reason", ""),
                "human_understanding_rating": item.get("human_understanding_rating", ""),
                "human_relationship_type": item.get("human_relationship_type", ""),
                "human_explanation_raw": item.get("human_explanation_raw", ""),
                "human_explanation_sanitized": item.get("human_explanation_sanitized", ""),
                "human_explanation_is_valid": item.get("human_explanation_is_valid", ""),
                "human_explanation_blocked_reason": item.get("human_explanation_blocked_reason", ""),
                "human_explanation_source": item.get("human_explanation_source", ""),
                "human_explanation_collected_at": item.get("human_explanation_collected_at", ""),
                "ai_relationship_type": item.get("ai_relationship_type", ""),
                "ai_explanation_raw": item.get("ai_explanation_raw", ""),
                "ai_explanation_sanitized": item.get("ai_explanation_sanitized", item.get("ai_explanation", "")),
                "ai_explanation_is_valid": item.get("ai_explanation_is_valid", ""),
                "ai_explanation_blocked_reason": item.get("ai_explanation_blocked_reason", ""),
                "ai_explanation": item.get("ai_explanation_sanitized", item.get("ai_explanation", "")),
                "reflection_source": item.get("reflection_source", ""),
                "recorded_at": item.get("recorded_at", ""),
            }
        )
    return clean_items


def _format_optional_float(value):
    if value is None or value == "":
        return ""
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return ""


def _types_for_words(words, word_type_per_card):
    missing = [word for word in words or [] if not word_type_per_card.get(word)]
    if missing:
        raise ValueError(
            "Cannot log word types because these words have no word_type: "
            + ", ".join(missing)
        )
    return [word_type_per_card[word] for word in words or []]


def _join_word_types(words, word_type_per_card):
    return ";".join(_types_for_words(words, word_type_per_card))


def _format_word_type_per_card(board, word_type_per_card):
    _types_for_words(board or [], word_type_per_card)
    return json.dumps(
        {word: word_type_per_card[word] for word in board or []},
        ensure_ascii=False,
    )


def _iso_now():
    return datetime.utcnow().isoformat()


def _session_row(completed=False):
    history = st.session_state.get("interaction_history", [])
    total_completed = len(st.session_state.get("ai_round_summaries", []))
    if st.session_state.get("round_finished"):
        total_completed = max(total_completed, int(st.session_state.get("round", 0) or 0))
    questionnaire = st.session_state.get("post_game_questionnaire", {}) or {}
    ai_questionnaire = st.session_state.get("ai_post_game_questionnaire", {}) or {}
    last_completed_stage = st.session_state.get("last_completed_stage", "")
    session_end_reason = st.session_state.get("session_end_reason", "")
    if last_completed_stage and last_completed_stage not in SESSION_STAGES:
        raise ValueError(f"Unknown completed session stage: {last_completed_stage}")
    if session_end_reason and session_end_reason not in SESSION_END_REASONS:
        raise ValueError(f"Unknown session end reason: {session_end_reason}")
    return {
        "participant_id": st.session_state.get("participant_id", ""),
        "nickname": st.session_state.get("nickname", st.session_state.get("participant_id", "")),
        "age_group": st.session_state.get("age_group", ""),
        "gender": st.session_state.get("gender", ""),
        "english_proficiency": st.session_state.get("english_proficiency", ""),
        "ai_experience": st.session_state.get("ai_experience", ""),
        "codenames_experience": st.session_state.get("codenames_experience", ""),
        "session_id": st.session_state.get("session_id", ""),
        "condition": st.session_state.get("condition", DEFAULT_CONDITION),
        "starting_role": st.session_state.get("starting_role", ""),
        "start_time": st.session_state.get("session_start_time", ""),
        "end_time": st.session_state.get("session_end_time", "") if completed else "",
        "completed": bool(completed),
        "consent_given": bool(st.session_state.get("consent_given", False)),
        "total_rounds_planned": N_ROUNDS,
        "total_rounds_completed": total_completed,
        "total_turns_completed": sum(
            int(summary.get("turns", 0) or 0)
            for summary in st.session_state.get("ai_round_summaries", [])
        )
        + (
            int(st.session_state.get("round_interactions", 0) or 0)
            if not st.session_state.get("round_finished")
            else 0
        ),
        "final_total_score": st.session_state.get("score", 0),
        "user_agent": st.session_state.get("user_agent", "unknown"),
        "device_type": st.session_state.get("device_type", "unknown"),
        "screen_size": st.session_state.get("screen_size", "unknown"),
        "browser_language": st.session_state.get("browser_language", "unknown"),
        "completion_code": st.session_state.get("completion_code", ""),
        "post_game_i_understood_ai_clues": questionnaire.get("i_understood_ai_clues", ""),
        "post_game_predict_ai_interpretation": questionnaire.get("predict_ai_interpretation", ""),
        "post_game_adapted_to_ai_behavior": questionnaire.get("adapted_to_ai_behavior", ""),
        "post_game_reflection_helped": questionnaire.get("reflection_helped", ""),
        "post_game_shared_understanding": questionnaire.get("shared_understanding", ""),
        "post_game_questionnaire_json": json.dumps(questionnaire, ensure_ascii=False),
        "ai_post_game_i_understood_human_clues": ai_questionnaire.get("i_understood_human_clues", ""),
        "ai_post_game_predict_human_interpretation": ai_questionnaire.get("predict_human_interpretation", ""),
        "ai_post_game_adapted_to_human_behavior": ai_questionnaire.get("adapted_to_human_behavior", ""),
        "ai_post_game_reflection_helped": ai_questionnaire.get("reflection_helped", ""),
        "ai_post_game_shared_understanding": ai_questionnaire.get("shared_understanding", ""),
        "ai_post_game_reasoning": ai_questionnaire.get("reasoning", ""),
        "ai_post_game_questionnaire_json": json.dumps(ai_questionnaire, ensure_ascii=False),
        "experiment_version": EXPERIMENT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "code_commit": CODE_COMMIT,
        "deployment_version": DEPLOYMENT_VERSION,
        "model_identifier": MODEL_IDENTIFIER,
        "condition_assignment_version": CONDITION_ASSIGNMENT_VERSION,
        "last_activity_at": st.session_state.get("last_activity_at", ""),
        "last_completed_stage": last_completed_stage,
        "session_end_reason": session_end_reason,
        "withdrawal_requested": bool(st.session_state.get("withdrawal_requested", False)),
        "technical_termination": bool(st.session_state.get("technical_termination", False)),
    }


def log_session_state(completed=False, persist_remote=True):
    if completed and not st.session_state.get("session_end_time"):
        st.session_state.session_end_time = _iso_now()
    if completed:
        st.session_state.session_end_reason = "completed"
        st.session_state.last_completed_stage = "completed"
    row = _session_row(completed=completed)
    try:
        ensure_flat_views()
        db.upsert_row(
            "sessions",
            key_columns=["participant_id", "session_id"],
            extra_columns={
                "participant_id": row["participant_id"],
                "session_id": row["session_id"],
                "condition": row["condition"],
                "completed": row["completed"],
                "last_completed_stage": row["last_completed_stage"],
            },
            data=row,
        )
        _set_remote_saved()
    except (psycopg2.Error, RuntimeError) as error:
        _set_remote_failure(error)


def mark_session_progress(stage, completed=False):
    """Persist a successfully completed study stage at a meaningful boundary."""
    if stage not in SESSION_STAGES:
        raise ValueError(f"Unknown session stage: {stage}")
    timestamp = _iso_now()
    st.session_state.last_activity_at = timestamp
    st.session_state.last_completed_stage = stage
    log_session_state(completed=completed, persist_remote=True)


def log_event(event_type, payload=None, round_number=None, turn_number=None):
    row = {
        "participant_id": st.session_state.get("participant_id", ""),
        "session_id": st.session_state.get("session_id", ""),
        "condition": st.session_state.get("condition", DEFAULT_CONDITION),
        "timestamp": _iso_now(),
        "event_type": event_type,
        "round_number": str(
            round_number if round_number is not None else st.session_state.get("round", "")
        ),
        "turn_number": str(
            turn_number if turn_number is not None else st.session_state.get("round_interactions", "")
        ),
        "event_payload": payload or {},
    }
    try:
        db.insert_row(
            "events",
            columns=[
                "session_id",
                "participant_id",
                "condition",
                "round_number",
                "turn_number",
                "event_type",
                "event_payload",
            ],
            values=[
                row["session_id"],
                row["participant_id"],
                row["condition"],
                row["round_number"],
                row["turn_number"],
                row["event_type"],
                json.dumps(row["event_payload"], ensure_ascii=False),
            ],
        )
        _set_remote_saved()
    except (psycopg2.Error, RuntimeError) as error:
        _set_remote_failure(error)


def initialize_session_log(participant_id):
    if st.session_state.get("session_log_initialized"):
        return
    st.session_state.participant_id = participant_id
    st.session_state.nickname = st.session_state.get("nickname", participant_id) or participant_id
    st.session_state.consent_given = True
    st.session_state.last_activity_at = _iso_now()
    st.session_state.last_completed_stage = "participant_profile"
    # Allocate only when a participant is actually registered. Ordinary Streamlit
    # reruns therefore do not consume a slot in the alternating assignment. The
    # allocation itself is one atomic Postgres transaction (core/db.py
    # allocate_condition), so concurrent registrations cannot corrupt the
    # alternating adaptive/baseline balance the way a shared file or a
    # process-local lock could.
    st.session_state.condition = db.allocate_condition(VALID_CONDITIONS, DEFAULT_CONDITION)
    st.session_state.condition_assigned = True
    log_session_state(completed=False)
    log_event(
        "session_started",
        {
            "starting_role": st.session_state.get("starting_role", ""),
            "nickname": st.session_state.get("nickname", ""),
            "age_group": st.session_state.get("age_group", ""),
            "gender": st.session_state.get("gender", ""),
            "english_proficiency": st.session_state.get("english_proficiency", ""),
            "ai_experience": st.session_state.get("ai_experience", ""),
            "codenames_experience": st.session_state.get("codenames_experience", ""),
        },
        round_number="",
        turn_number="",
    )
    log_event("consent_given", {}, round_number="", turn_number="")
    log_event("instruction_viewed", {}, round_number="", turn_number="")
    st.session_state.session_log_initialized = True


def _role_pair(round_role):
    return (
        ("human", "ai") if round_role == "human_clue" else ("ai", "human")
    )


def _round_analysis_row(participant_id, timestamp, score_change):
    word_type_per_card = st.session_state.get("word_type_per_card", {})
    bomb_words = st.session_state.get("bomb_words") or [st.session_state.bomb_word]
    selected_bombs = [
        guess for guess in st.session_state.get("guesses", []) if guess in bomb_words
    ]
    clue_giver, guesser = _role_pair(st.session_state.get("role", ""))
    round_start = st.session_state.get("round_start_time") or st.session_state.get("start_time")
    if hasattr(round_start, "isoformat"):
        round_start = round_start.isoformat()
    round_end = timestamp
    duration = ""
    if round_start:
        try:
            duration = f"{(datetime.fromisoformat(round_end) - datetime.fromisoformat(round_start)).total_seconds():.3f}"
        except ValueError:
            duration = ""
    round_end_reason = st.session_state.get("round_end_reason", "")
    if round_end_reason and round_end_reason not in ROUND_END_REASONS:
        raise ValueError(f"Unknown round end reason: {round_end_reason}")
    if not st.session_state.get("round_finished"):
        round_end_reason = ""
    return {
        "participant_id": participant_id,
        "session_id": st.session_state.get("session_id", ""),
        "condition": st.session_state.get("condition", DEFAULT_CONDITION),
        "round_number": st.session_state.round,
        "round_role": st.session_state.role,
        "clue_giver": clue_giver,
        "guesser": guesser,
        "board_template_type": st.session_state.get("board_template_type", ""),
        "board_id": st.session_state.get("board_id", ""),
        "all_board_words": _json(st.session_state.board),
        "word_type_per_card": _format_word_type_per_card(st.session_state.board, word_type_per_card),
        "target_words": _json(st.session_state.target_words),
        "target_word_types": _json(_types_for_words(st.session_state.target_words, word_type_per_card)),
        "neutral_words": _json(st.session_state.neutral_words),
        "neutral_word_types": _json(_types_for_words(st.session_state.neutral_words, word_type_per_card)),
        "bomb_words": _json(bomb_words),
        "bomb_word_types": _json(_types_for_words(bomb_words, word_type_per_card)),
        "remaining_targets_start": _json(st.session_state.target_words),
        "remaining_targets_end": _json(
            [word for word in st.session_state.target_words if word not in st.session_state.found_targets]
        ),
        "number_of_turns": st.session_state.round_interactions,
        "round_score": score_change,
        "medal": st.session_state.round_medal,
        "round_completed": bool(st.session_state.round_finished),
        "round_terminated_by_bomb": bool(st.session_state.round_bomb_hit),
        "bomb_selected": bool(selected_bombs),
        "selected_bomb_words": _json(selected_bombs),
        "round_start_time": round_start or "",
        "round_end_time": round_end,
        "round_duration_seconds": duration,
        "round_end_reason": round_end_reason,
        "ai_round_reflection": st.session_state.get("ai_round_reflection", ""),
        "human_round_feedback": st.session_state.get("human_round_feedback", ""),
    }


def _action_classification(item):
    if item.get("timed_out") or item.get("outcome") == "timeout":
        return "timeout"
    if item.get("partial_skip") or item.get("outcome") == "partial_skip":
        return "partial_skip"
    if item.get("skipped") or item.get("outcome") == "skip":
        return "full_skip"
    return "interaction"


def _alignment_applicability(item, action_type=None):
    action_type = action_type or _action_classification(item)
    if action_type == "timeout":
        return "timeout_no_behavioral_selection"
    if action_type == "partial_skip":
        return "partial_selection"
    if action_type == "full_skip":
        return (
            "interpreted_only_skip"
            if item.get("skip_interpreted_cards")
            else "not_applicable"
        )
    if item.get("guesses"):
        return "observed_completed_selection"
    return "not_applicable"


def _llm_fields_for_turn(item):
    clue_giver = item.get("clue_giver", "")
    condition = st.session_state.get("condition", DEFAULT_CONDITION)
    if clue_giver == "ai":
        raw = item.get("hint_raw_response", "")
        latency = item.get("hint_response_time_sec")
        parsed = {
            "clue": item.get("hint", ""),
            "number": item.get("hint_number", ""),
            "targets": item.get("intended_targets", []),
            "expected_guesses": item.get("expected_guesses", []),
        }
        model = HINT_MODEL_NAME
        temperature = "0.55"
        prompt_version = "hint_v2_condition_memory"
        system_version = f"hint_system_v2_{condition}"
    else:
        raw = item.get("guess_raw_response", "")
        latency = item.get("guess_response_time_sec")
        parsed = {
            "action": item.get("outcome", "guess"),
            "guesses": item.get("guesses", []),
            "reasoning": item.get("guess_rationale", ""),
            "partial_skip": bool(item.get("partial_skip", False)),
        }
        model = GUESS_MODEL_NAME
        temperature = "0.2"
        prompt_version = "guess_v2_partial_skip"
        system_version = f"guess_system_v2_{condition}"
    error = raw if str(raw).startswith("<api_error:") else ""
    return {
        "llm_model": model,
        "llm_temperature": temperature,
        "llm_prompt_version": prompt_version,
        "llm_system_prompt_version": system_version,
        "llm_response_raw": raw,
        "llm_response_parsed": _json_obj(parsed),
        "llm_error": error,
        "llm_latency_seconds": _format_optional_float(latency),
    }


def _turn_analysis_row(participant_id, item, word_type_per_card):
    guessed = item.get("guesses", [])
    correct = item.get("correct_guesses", [])
    incorrect = item.get("incorrect_guesses", [])
    neutral = item.get("neutral_guesses", [])
    bombs = item.get("bomb_guesses", [])
    human_raw = item.get("human_explanation_raw", "")
    human_sanitized = item.get("human_explanation_sanitized", human_raw)
    human_valid = bool(item.get("human_explanation_is_valid", False))
    ai_sanitized = item.get("ai_explanation_sanitized", item.get("ai_explanation", ""))
    ai_valid = bool(item.get("ai_explanation_is_valid", False))
    llm_fields = _llm_fields_for_turn(item)
    action_type = _action_classification(item)
    alignment_applicability = _alignment_applicability(item, action_type)
    if action_type not in ACTION_TYPES:
        raise ValueError(f"Unknown action type: {action_type}")
    if alignment_applicability not in ALIGNMENT_APPLICABILITY_VALUES:
        raise ValueError(f"Unknown alignment applicability: {alignment_applicability}")
    return {
        "participant_id": participant_id,
        "session_id": st.session_state.get("session_id", ""),
        "condition": st.session_state.get("condition", DEFAULT_CONDITION),
        "round_number": st.session_state.round,
        "turn_number": item.get("turn", ""),
        "action_type": action_type,
        "alignment_applicability": alignment_applicability,
        "completed_turn_number": item.get("completed_turn_number", ""),
        "skip_number": item.get("skip_number", ""),
        "clue_giver": item.get("clue_giver", ""),
        "guesser": item.get("guesser", ""),
        "clue": item.get("hint", ""),
        "clue_number": item.get("hint_number", ""),
        "hint_explanation": item.get("hint_explanation", ""),
        "hint_attempts": item.get("hint_attempts"),
        "board_id": st.session_state.get("board_id", ""),
        "outcome": item.get("outcome", "correct" if correct else "wrong"),
        "bomb_hit": bool(item.get("bomb_hit", False)),
        "intended_cards": _json(item.get("intended_targets", [])),
        "intended_word_types": _json(_types_for_words(item.get("intended_targets", []), word_type_per_card)),
        "expected_guess_cards": _json(item.get("expected_guesses", [])),
        "expected_guess_word_types": _json(_types_for_words(item.get("expected_guesses", []), word_type_per_card)),
        "guess_rationale": item.get("guess_rationale", ""),
        "guess_rationale_word_count": item.get("guess_rationale_word_count", 0),
        "guessed_cards": _json(guessed),
        "guess_order": ";".join(
            f"{entry.get('position')}:{entry.get('word')}"
            for entry in item.get("guess_order", [])
        ),
        "guess_order_json": _json(item.get("guess_order", [])),
        "guessed_word_types": _json(_types_for_words(guessed, word_type_per_card)),
        "correct_guesses": _json(correct),
        "correct_guess_word_types": _json(_types_for_words(correct, word_type_per_card)),
        "incorrect_guesses": _json(incorrect),
        "incorrect_guess_word_types": _json(_types_for_words(incorrect, word_type_per_card)),
        "missed_intended_targets": _json(
            [word for word in item.get("intended_targets", []) if word not in correct]
        ),
        "extra_correct_guesses": _json(
            [word for word in correct if word not in item.get("intended_targets", [])]
        ),
        "neutral_guesses": _json(neutral),
        "neutral_guess_word_types": _json(_types_for_words(neutral, word_type_per_card)),
        "bomb_guesses": _json(bombs),
        "bomb_guess_word_types": _json(_types_for_words(bombs, word_type_per_card)),
        "remaining_targets_before_turn": _json(item.get("remaining_targets_before_turn", [])),
        "remaining_targets_after_turn": _json(item.get("remaining_targets_after_turn", [])),
        "hint_time_sec": _format_optional_float(item.get("hint_time_sec")),
        "guess_time_sec": _format_optional_float(item.get("guess_time_sec")),
        "hit_rate": _format_optional_float(item.get("hit_rate")),
        "target_yield": item.get("target_yield", ""),
        "jaccard_alignment": _format_optional_float(item.get("jaccard_alignment")),
        "alignment_status": item.get("alignment_status", ""),
        "error_type": item.get("error_type", "none"),
        "turn_score_delta": item.get("turn_score_delta", ""),
        "turn_start_time": item.get("turn_start_time", ""),
        "turn_end_time": item.get("turn_end_time", ""),
        "turn_duration_seconds": _format_optional_float(item.get("turn_duration_seconds", "")),
        "partial_skip": bool(item.get("partial_skip", False)),
        "skip_interpreted_cards": _json(item.get("skip_interpreted_cards", [])),
        "skip_interpreted_word_types": _json(
            _types_for_words(item.get("skip_interpreted_cards", []), word_type_per_card)
        ),
        "skip_interpreted_count": len(item.get("skip_interpreted_cards", [])),
        "wrong_guess_replacements": _json(
            item.get("wrong_guess_replacements", [])
        ),
        "wrong_guess_replacement_word_types": _json(
            _types_for_words(
                item.get("wrong_guess_replacements", []), word_type_per_card
            )
        ),
        "wrong_guess_replacement_count": len(
            item.get("wrong_guess_replacements", [])
        ),
        "wrong_guess_replacement_actor": item.get(
            "wrong_guess_replacement_actor", ""
        ),
        "wrong_guess_replacement_raw_response": item.get(
            "wrong_guess_replacement_raw_response", ""
        ),
        "wrong_guess_replacement_response_time_sec": _format_optional_float(
            item.get("wrong_guess_replacement_response_time_sec", "")
        ),
        "wrong_guess_replacement_attempts": item.get(
            "wrong_guess_replacement_attempts", ""
        ),
        "completed_guesses": item.get("completed_guesses", len(guessed)),
        "skipped_guesses": item.get("skipped_guesses", 0),
        "reflection_shown": bool(item.get("reflection_source")),
        "reflection_start_time": item.get("reflection_start_time", ""),
        "reflection_end_time": item.get("reflection_end_time", ""),
        "reflection_time_sec": _format_optional_float(item.get("reflection_time_sec")),
        "reflection_source": item.get("reflection_source", ""),
        "ai_understanding_rating_before": item.get("ai_understanding_rating_before"),
        "ai_understanding_rating_after": item.get("ai_understanding_rating_after"),
        "human_understanding_rating_before": item.get("human_understanding_rating_before"),
        "human_understanding_rating": item.get("human_understanding_rating", ""),
        "human_relationship_type": item.get("human_relationship_type", ""),
        "human_explanation_raw": human_raw,
        "human_explanation_sanitized": human_sanitized if human_valid else "",
        "human_explanation_is_valid": bool(human_valid),
        "human_explanation_blocked_reason": item.get("human_explanation_blocked_reason", ""),
        "human_explanation_source": item.get("human_explanation_source", ""),
        "human_explanation_collected_at": item.get("human_explanation_collected_at", ""),
        "ai_relationship_type": item.get("ai_relationship_type", ""),
        "ai_explanation_raw": item.get("ai_explanation_raw", ""),
        "ai_explanation_sanitized": ai_sanitized,
        "ai_explanation_is_valid": bool(ai_valid),
        "ai_explanation_blocked_reason": item.get("ai_explanation_blocked_reason", ""),
        "ai_explanation": ai_sanitized,
        "repair_applied_to_next_prompt": bool(item.get("repair_attempt")),
        "repair_context_used": _json_obj(
            {
                "source_turn": item.get("repair_source_turn", ""),
                "source_targets": item.get("repair_source_targets", []),
                "adaptive_reflection_available": bool(
                    st.session_state.get("condition") == "adaptive" and item.get("repair_attempt")
                ),
            }
            if item.get("repair_attempt")
            else {}
        ),
        "repair_required": bool(item.get("repair_required", False)),
        "repair_source_turn": item.get("repair_source_turn", ""),
        "repair_source_targets": _json(item.get("repair_source_targets", [])),
        "repair_chain_id": item.get("repair_chain_id", ""),
        "repair_attempt_number": item.get("repair_attempt_number", ""),
        "repair_attempt": bool(item.get("repair_attempt", False)),
        "repair_same_targets_retried": bool(item.get("repair_same_targets_retried", False)),
        "repair_success": bool(item.get("repair_success", False)),
        "timer_duration_seconds": item.get("timer_duration_seconds", ""),
        "clue_timer_started_at": item.get("clue_timer_started_at", ""),
        "human_decision_started_at": item.get("human_decision_started_at", ""),
        "human_decision_ended_at": item.get("human_decision_ended_at", ""),
        "human_decision_time_sec": _format_optional_float(item.get("human_decision_time_sec")),
        "human_timed_out": bool(item.get("human_timed_out", False)),
        "timeout_timestamp": item.get("timeout_timestamp", ""),
        "timed_out": bool(item.get("timed_out", False)),
        "timeout_repair_attempt": bool(item.get("timeout_repair_attempt", False)),
        "timeout_selected_cards": _json(item.get("timeout_selected_cards", [])),
        **llm_fields,
    }


def _board_card_rows():
    """One row per board card for this round, for direct SQL/pandas access
    to abstract/concrete composition (RQ3) without unpacking JSON per row."""
    word_roles = st.session_state.get("word_roles", {})
    word_type_per_card = st.session_state.get("word_type_per_card", {})
    session_id = st.session_state.get("session_id", "")
    round_number = st.session_state.round
    board_id = st.session_state.get("board_id", "")
    rows = []
    for word in st.session_state.get("board", []) or []:
        rows.append(
            (
                session_id,
                round_number,
                board_id,
                word,
                word_roles.get(word, ""),
                word_type_per_card.get(word, ""),
            )
        )
    return rows


def append_analysis_logs(participant_id, timestamp, score_change, clean_history):
    round_row = _round_analysis_row(participant_id, timestamp, score_change)
    db.upsert_row(
        "rounds",
        key_columns=["session_id", "round_number"],
        extra_columns={
            "session_id": round_row["session_id"],
            "round_number": round_row["round_number"],
            "condition": round_row["condition"],
        },
        data=round_row,
    )

    word_type_per_card = st.session_state.get("word_type_per_card", {})
    turn_rows = []
    for item in clean_history:
        turn_row = _turn_analysis_row(participant_id, item, word_type_per_card)
        db.upsert_row(
            "turns",
            key_columns=["session_id", "round_number", "turn_number"],
            extra_columns={
                "session_id": turn_row["session_id"],
                "round_number": turn_row["round_number"],
                "turn_number": turn_row["turn_number"],
                "condition": turn_row["condition"],
                "action_type": turn_row["action_type"],
                "alignment_applicability": turn_row["alignment_applicability"],
            },
            data=turn_row,
        )
        turn_rows.append(turn_row)

    board_card_rows = _board_card_rows()
    if board_card_rows:
        db.insert_rows(
            "board_cards",
            columns=["session_id", "round_number", "board_id", "card_word", "card_role", "word_type"],
            rows=board_card_rows,
        )
        # Re-running the same round (e.g. after a Streamlit rerun before the
        # round advances) would otherwise violate the primary key; the ON
        # CONFLICT clause below makes repeated calls idempotent.

    return round_row, turn_rows


def log_round(participant_id):
    timestamp = datetime.utcnow().isoformat()

    guesses = st.session_state.guesses
    bomb_words = st.session_state.get("bomb_words") or [st.session_state.bomb_word]
    score_change = compute_score_change(
        guesses,
        st.session_state.target_words,
        bomb_words,
        st.session_state.round_interactions,
    )
    clean_history = clean_interaction_history(st.session_state.interaction_history)

    st.session_state.last_score_change = score_change
    st.session_state.score += score_change

    try:
        normalized_round_row, normalized_turn_rows = append_analysis_logs(
            participant_id,
            timestamp,
            score_change,
            clean_history,
        )
        _set_remote_saved()
    except (psycopg2.Error, RuntimeError) as error:
        _set_remote_failure(error)
        normalized_round_row, normalized_turn_rows = None, None

    log_event(
        "round_completed",
        {
            "round_score": score_change,
            "medal": st.session_state.round_medal,
            "turns": st.session_state.round_interactions,
        },
        round_number=st.session_state.round,
        turn_number=st.session_state.round_interactions,
    )
    if st.session_state.round_bomb_hit:
        log_event(
            "bomb_selected",
            {
                "bomb_words": [
                    guess
                    for guess in st.session_state.guesses
                    if guess in (st.session_state.get("bomb_words") or [])
                ]
            },
            round_number=st.session_state.round,
            turn_number=st.session_state.round_interactions,
        )
    log_event("export_completed", {"tables": ["rounds", "turns"]})
    st.session_state.last_activity_at = timestamp
    st.session_state.last_completed_stage = "gameplay"
    log_session_state(completed=False, persist_remote=True)

    return normalized_round_row, normalized_turn_rows
