import hashlib
import random
from datetime import datetime, timezone

import streamlit as st

from core.constants import (
    BOARD_MATERIAL_VERSION,
    BOARD_SIZE,
    MAX_INTERACTIONS_PER_ROUND,
    MAX_SKIPS_PER_ROUND,
    MEDAL_POINTS,
    N_ROUNDS,
    CLUE_TIMER_SECONDS,
)
from core.words import ROUND_BOARDS


class BoardGenerationError(ValueError):
    pass


def start_participant_decision_timer(started_at=None, duration_seconds=None):
    """Start a deadline for a new human task; ordinary reruns never call this."""
    started_at = started_at or datetime.now(timezone.utc).isoformat()
    st.session_state.clue_timer_started_at = started_at
    st.session_state.clue_timer_duration_seconds = (
        duration_seconds if duration_seconds is not None else CLUE_TIMER_SECONDS
    )
    st.session_state.clue_timer_timeout_consumed = False
    return started_at


def clear_participant_decision_timer():
    st.session_state.clue_timer_started_at = ""
    st.session_state.clue_timer_duration_seconds = 0


def participant_decision_time_remaining(now=None):
    started_raw = st.session_state.get("clue_timer_started_at", "")
    if not started_raw:
        return None
    try:
        started = datetime.fromisoformat(started_raw)
    except (TypeError, ValueError):
        return 0.0
    now = now or datetime.now(timezone.utc)
    duration = st.session_state.get("clue_timer_duration_seconds") or CLUE_TIMER_SECONDS
    return max(0.0, float(duration) - (now - started).total_seconds())


def participant_decision_timer_expired(now=None):
    remaining = participant_decision_time_remaining(now)
    return remaining is not None and remaining <= 0


def get_word_type_for_round(round_number):
    return "mixed"


def get_role_for_round(round_number, starting_role=None):
    starting_role = starting_role or st.session_state.get("starting_role", "human_clue")
    if round_number % 2 == 1:
        return starting_role
    return "ai_clue" if starting_role == "human_clue" else "human_clue"


def _board_number_for_round(round_number):
    """Which entry in core.words.ROUND_BOARDS plays as this game round --
    shuffled once per session (see core.state._new_round_board_order) so
    the four boards appear in a random order instead of always B01..B04 in
    round 1..4. Falls back to a direct 1:1 mapping if the shuffled order is
    ever missing (e.g. an older session_state), rather than crashing."""
    order = st.session_state.get("round_board_order") or list(ROUND_BOARDS.keys())
    index = round_number - 1
    return order[index] if 0 <= index < len(order) else round_number


def get_board_template_id(round_number):
    # Each round plays one of the hand-curated, fixed boards (see
    # core.words.ROUND_BOARDS), assigned via the session's shuffled
    # round-to-board order rather than a fixed 1:1 mapping. This returns
    # that board's id (e.g. "B01"). Kept as its own function (rather than
    # inlining the lookup) since callers elsewhere treat "which board
    # layout is this round" as a single fact, independent of
    # get_role_for_round.
    board = ROUND_BOARDS.get(_board_number_for_round(round_number))
    if board is None:
        raise BoardGenerationError(f"No fixed board is defined for round {round_number}.")
    return board["id"]


def validate_word_bank_capacity(round_count=N_ROUNDS):
    missing_rounds = [
        round_number
        for round_number in range(1, round_count + 1)
        if round_number not in ROUND_BOARDS
    ]
    if missing_rounds:
        raise BoardGenerationError(
            "No fixed board is defined for round(s): "
            + ", ".join(str(r) for r in missing_rounds)
            + ". Add a board for every round in core/words.py before running the study."
        )
    for round_number in range(1, round_count + 1):
        board = ROUND_BOARDS[round_number]
        words = [word for role in ("target", "neutral", "bomb") for word, _ in board[role]]
        if len(words) != BOARD_SIZE:
            raise BoardGenerationError(
                f"Round {round_number}'s fixed board ({board['id']}) has {len(words)} "
                f"words, expected {BOARD_SIZE}."
            )
        if len(set(word.lower() for word in words)) != BOARD_SIZE:
            raise BoardGenerationError(
                f"Round {round_number}'s fixed board ({board['id']}) contains duplicate words."
            )


def build_board_instance_id(round_number, template_type, board_words, word_roles):
    board_signature = "|".join(
        f"{word}:{word_roles.get(word, '')}" for word in sorted(board_words)
    )
    digest = hashlib.sha1(board_signature.encode("utf-8")).hexdigest()[:10]
    return f"round-{round_number}-template-{template_type}-{digest}"


def sample_fixed_round_words(round_number):
    validate_word_bank_capacity()
    board = ROUND_BOARDS[_board_number_for_round(round_number)]
    template_type = board["id"]

    targets = [word for word, _word_type in board["target"]]
    neutrals = [word for word, _word_type in board["neutral"]]
    bombs = [word for word, _word_type in board["bomb"]]
    board_words = targets + neutrals + bombs

    word_roles = {word: "target" for word in targets}
    word_roles.update({word: "neutral" for word in neutrals})
    word_roles.update({word: "bomb" for word in bombs})
    word_types = {
        word: word_type
        for role in ("target", "neutral", "bomb")
        for word, word_type in board[role]
    }

    # The word set and every word's role are fixed above -- only the
    # on-screen grid position is randomized, here.
    random.shuffle(board_words)
    return board_words, targets, neutrals, bombs, word_roles, word_types, template_type


def setup_new_round():
    word_type = get_word_type_for_round(st.session_state.round)
    board, targets, neutrals, bombs, word_roles, word_types, template_type = sample_fixed_round_words(
        st.session_state.round
    )

    st.session_state.word_type = word_type
    st.session_state.role = get_role_for_round(
        st.session_state.round,
        st.session_state.get("starting_role", "human_clue"),
    )
    st.session_state.board = board
    st.session_state.board_template_id = template_type
    st.session_state.board_material_version = BOARD_MATERIAL_VERSION
    st.session_state.board_instance_id = build_board_instance_id(
        st.session_state.round,
        template_type,
        board,
        word_roles,
    )
    st.session_state.target_words = targets
    st.session_state.bomb_words = bombs
    st.session_state.neutral_words = neutrals
    st.session_state.bomb_word = bombs[0] if bombs else None
    st.session_state.word_roles = word_roles
    st.session_state.word_type_per_card = word_types
    st.session_state.guesses = []
    st.session_state.pending_guesses = []
    st.session_state.current_guess_rationale = ""
    st.session_state.found_targets = []
    st.session_state.interaction_history = []
    st.session_state.round_interactions = 0
    st.session_state.round_skips = 0
    st.session_state.round_clue_giver_timeouts = 0
    st.session_state.final_guess_deadline_active = False
    st.session_state.round_finished = False
    st.session_state.hint = ""
    st.session_state.hint_number = 1
    st.session_state.hint_targets = []
    st.session_state.hint_expected_guesses = []
    st.session_state.hint_explanation = ""
    st.session_state.last_ai_guesses = []
    st.session_state.last_ai_hint = ""
    st.session_state.perception_rating = None
    st.session_state.human_expected_ai_understanding_rating = None
    st.session_state.pending_ai_guess_review = None
    st.session_state.previous_hint = None
    st.session_state.start_time = datetime.now(timezone.utc)
    st.session_state.round_start_time = st.session_state.start_time.isoformat()
    st.session_state.current_turn_start_time = ""
    st.session_state.current_hint_start_time = ""
    st.session_state.current_guess_start_time = ""
    st.session_state.current_reflection_start_time = ""
    clear_participant_decision_timer()
    st.session_state.last_score_change = 0
    st.session_state.round_medal = "none"
    st.session_state.round_success = False
    st.session_state.round_bomb_hit = False
    st.session_state.round_end_reason = ""
    st.session_state.ai_round_reflection = ""
    st.session_state.human_round_feedback = ""
    st.session_state.pending_hint_meta = None
    st.session_state.pending_reflection_turn = None


def get_medal_for_round(interactions, success, bomb_hit):
    if bomb_hit or not success:
        return "none"
    if interactions <= 2:
        return "gold"
    if interactions == 3:
        return "silver"
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
    expected_guesses=None,
    guess_rationale="",
    hint_explanation="",
    human_expected_ai_understanding_rating=None,
    hint_raw_response="",
    hint_time_sec=None,
    hint_response_time_sec=None,
    hint_attempts=None,
    guess_raw_response="",
    guess_time_sec=None,
    guess_response_time_sec=None,
    partial_skip=False,
    skipped_by=None,
    skip_interpreted_cards=None,
    repair_context=None,
    clue_timer_started_at=None,
    timer_duration_seconds=None,
    human_explanation_raw="",
    human_explanation_is_valid=None,
    human_explanation_blocked_reason="",
    human_explanation_source="",
    human_explanation_collected_at="",
):
    intended_targets = intended_targets or []
    expected_guesses = expected_guesses or []
    skip_interpreted_cards = skip_interpreted_cards or []
    repair_context = repair_context or {}
    guess_rationale = (guess_rationale or "").strip()
    guess_order = [
        {"position": position, "word": guess}
        for position, guess in enumerate(guesses or [], start=1)
    ]
    turn_end = datetime.now(timezone.utc)
    turn_start_raw = st.session_state.get("current_turn_start_time") or turn_end.isoformat()
    try:
        turn_start = datetime.fromisoformat(turn_start_raw)
    except ValueError:
        turn_start = turn_end
    found_before = set(st.session_state.found_targets)
    remaining_before = [
        word for word in st.session_state.target_words if word not in found_before
    ]
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
    found_after = found_before.union(new_targets)
    remaining_after = [
        word for word in st.session_state.target_words if word not in found_after
    ]
    clue_giver = "human" if st.session_state.role == "human_clue" else "ai"
    guesser = "ai" if st.session_state.role == "human_clue" else "human"
    if bomb_hit:
        outcome = "bomb"
    elif partial_skip:
        outcome = "partial_skip"
    elif correct_guesses and neutral_guesses:
        # A turn with both a correct guess and a neutral (wrong) one used to
        # collapse into plain "correct" here (any correct guess at all was
        # enough) -- masking a real, analyzable distinction between a fully
        # clean turn and a partly-right one. ui.screens._guess_outcome_summary
        # already computes this exact split live for the "Partly right: ..."
        # message; this makes it a first-class STORED value instead of only
        # ever existing on screen. Independent of alignment_status (which
        # measures guessed-vs-INTENDED overlap, a communication question) --
        # this is the game-outcome axis (guessed-vs-actual board roles).
        outcome = "partial_correct"
    elif correct_guesses:
        outcome = "correct"
    else:
        outcome = "wrong"
    intended_set = set(intended_targets)
    guessed_set = set(guesses)
    if intended_set and guessed_set == intended_set:
        alignment_status = "perfect"
    elif intended_set.intersection(guessed_set):
        alignment_status = "partial"
    else:
        alignment_status = "misaligned"
    if bomb_guesses:
        error_type = "bomb"
    elif neutral_guesses:
        error_type = "neutral"
    else:
        error_type = "none"
    union_size = len(intended_set.union(guessed_set))
    jaccard_alignment = (
        len(intended_set.intersection(guessed_set)) / union_size if union_size else 0.0
    )
    hit_rate = len(correct_guesses) / len(guesses) if guesses else 0.0
    target_yield = len(new_targets)

    interaction_sequence = len(st.session_state.interaction_history) + 1
    st.session_state.round_interactions += 1
    if partial_skip:
        st.session_state.round_skips = st.session_state.get("round_skips", 0) + 1
    st.session_state.guesses.extend(
        guess for guess in guesses if guess not in st.session_state.guesses
    )
    st.session_state.found_targets.extend(new_targets)
    if normalized_hint and normalized_hint not in st.session_state.used_hints:
        st.session_state.used_hints.append(normalized_hint)
    st.session_state.interaction_history.append(
        {
            "turn": interaction_sequence,
            "completed_turn_number": st.session_state.round_interactions,
            "skip_number": st.session_state.get("round_skips", 0) if partial_skip else "",
            "clue_giver": clue_giver,
            "guesser": guesser,
            "hint": normalized_hint,
            "hint_number": hint_number,
            "intended_targets": intended_targets,
            "expected_guesses": expected_guesses,
            "guess_rationale": guess_rationale,
            "guess_rationale_word_count": len(guess_rationale.split()) if guess_rationale else 0,
            "hint_explanation": hint_explanation,
            "guesses": guesses,
            "guess_order": guess_order,
            "correct": bool(correct_guesses),
            "correct_guesses": correct_guesses,
            "neutral_guesses": neutral_guesses,
            "bomb_guesses": bomb_guesses,
            "bomb_guess": bomb_guess,
            "bomb_hit": bomb_hit,
            "outcome": outcome,
            "skipped": bool(partial_skip),
            "skipped_by": (skipped_by or guesser) if partial_skip else "",
            "partial_skip": bool(partial_skip),
            "skip_interpreted_cards": skip_interpreted_cards if partial_skip else [],
            "repair_required": bool(partial_skip and clue_giver == "ai" and skipped_by == "human"),
            "repair_source_turn": repair_context.get("skipped_turn", ""),
            "repair_source_targets": list(repair_context.get("unresolved_targets", [])),
            "repair_chain_id": repair_context.get("repair_chain_id", "") or (
                f"{st.session_state.get('session_id', '')}:r{st.session_state.get('round', '')}:"
                f"t{interaction_sequence}"
                if partial_skip and clue_giver == "ai" and skipped_by == "human"
                else ""
            ),
            "repair_attempt_number": repair_context.get("repair_attempt_number", ""),
            "repair_attempt": bool(repair_context),
            "repair_same_targets_retried": bool(
                repair_context and set(intended_targets) == set(repair_context.get("unresolved_targets", []))
            ),
            "repair_success": bool(
                repair_context and set(repair_context.get("unresolved_targets", [])).issubset(set(correct_guesses))
            ),
            "timer_duration_seconds": timer_duration_seconds if timer_duration_seconds is not None else st.session_state.get("clue_timer_duration_seconds", CLUE_TIMER_SECONDS),
            "clue_timer_started_at": clue_timer_started_at if clue_timer_started_at is not None else st.session_state.get("clue_timer_started_at", ""),
            "human_timed_out": False,
            "timeout_timestamp": "",
            "timed_out": False,
            "timeout_repair_attempt": False,
            "timeout_selected_cards": [],
            "wrong_guess_replacements": [],
            "wrong_guess_replacement_actor": "",
            "wrong_guess_replacement_raw_response": "",
            "wrong_guess_replacement_response_time_sec": "",
            "wrong_guess_replacement_attempts": "",
            "completed_guesses": len(guesses),
            "skipped_guesses": max(0, int(hint_number or 0) - len(guesses)) if partial_skip else 0,
            "alignment_status": alignment_status,
            "error_type": error_type,
            "human_expected_ai_understanding_rating": human_expected_ai_understanding_rating,
            "hint_raw_response": hint_raw_response,
            "hint_time_sec": hint_time_sec,
            "hint_response_time_sec": hint_response_time_sec,
            "hint_attempts": hint_attempts,
            "guess_raw_response": guess_raw_response,
            "guess_time_sec": guess_time_sec,
            "guess_response_time_sec": guess_response_time_sec,
            "remaining_targets_before_turn": remaining_before,
            "remaining_targets_after_turn": remaining_after,
            "hit_rate": hit_rate,
            "target_yield": target_yield,
            "jaccard_alignment": jaccard_alignment,
            "turn_score_delta": target_yield,
            "turn_start_time": turn_start.isoformat(),
            "turn_end_time": turn_end.isoformat(),
            "turn_duration_seconds": (turn_end - turn_start).total_seconds(),
            "reflection_start_time": "",
            "reflection_end_time": "",
            "reflection_time_sec": "",
            "recorded_at": turn_end.isoformat(),
            "reflection_rating": "",
            "reflection_relationship_type": "",
            "reflection_explanation_raw": human_explanation_raw,
            "reflection_explanation_is_valid": human_explanation_is_valid if human_explanation_is_valid is not None else "",
            "reflection_blocked_reason": "",
            "human_perceived_understanding_rating": "",
            "human_relationship_type": "",
            "human_explanation_raw": human_explanation_raw,
            "human_explanation_sanitized": human_explanation_raw if human_explanation_is_valid else "",
            "human_explanation_is_valid": human_explanation_is_valid if human_explanation_is_valid is not None else "",
            "human_explanation_blocked_reason": human_explanation_blocked_reason,
            "human_explanation_source": human_explanation_source,
            "human_explanation_collected_at": human_explanation_collected_at,
            "ai_relationship_type": "",
            "ai_explanation_raw": "",
            "ai_explanation_sanitized": "",
            "ai_explanation_is_valid": "",
            "ai_explanation_blocked_reason": "",
            "ai_explanation": "",
            "reflection_source": "",
        }
    )
    st.session_state.pending_reflection_turn = interaction_sequence

    if (
        bomb_hit
        or len(st.session_state.found_targets) == len(st.session_state.target_words)
        or st.session_state.round_interactions >= MAX_INTERACTIONS_PER_ROUND
    ):
        finish_round()


def can_skip_current_clue():
    return st.session_state.get("round_skips", 0) < MAX_SKIPS_PER_ROUND


def record_skip(
    hint,
    hint_number,
    intended_targets=None,
    expected_guesses=None,
    guess_rationale="",
    hint_explanation="",
    skipped_by=None,
    hint_raw_response="",
    hint_time_sec=None,
    hint_response_time_sec=None,
    hint_attempts=None,
    guess_raw_response="",
    guess_time_sec=None,
    guess_response_time_sec=None,
    skip_interpreted_cards=None,
    repair_context=None,
    timed_out=False,
    timeout_timestamp="",
    timeout_selected_cards=None,
    clue_timer_started_at=None,
    timer_duration_seconds=None,
    human_explanation_raw="",
    human_explanation_is_valid=None,
    human_explanation_blocked_reason="",
    human_explanation_source="",
    human_explanation_collected_at="",
    timeout_cost="skip",
):
    intended_targets = intended_targets or []
    expected_guesses = expected_guesses or []
    skip_interpreted_cards = skip_interpreted_cards or []
    repair_context = repair_context or {}
    timeout_selected_cards = timeout_selected_cards or []
    guess_rationale = (guess_rationale or "").strip()
    guess_order = []
    turn_end = datetime.now(timezone.utc)
    turn_start_raw = st.session_state.get("current_turn_start_time") or turn_end.isoformat()
    try:
        turn_start = datetime.fromisoformat(turn_start_raw)
    except ValueError:
        turn_start = turn_end
    normalized_hint = hint.strip().lower()
    clue_giver = "human" if st.session_state.role == "human_clue" else "ai"
    guesser = "ai" if st.session_state.role == "human_clue" else "human"
    skipped_by = skipped_by or guesser

    interaction_sequence = len(st.session_state.interaction_history) + 1
    # A timeout consumes a skip, the same as an explicit skip -- letting the
    # clock run out is not a free pass to reroll the clue. (Once skips are
    # exhausted, a further timeout is handled separately as a forced final
    # guess window; see record_forced_timeout_loss.) The clue-giver's own
    # timeout is the one exception: their first timeout each round costs
    # nothing at all (timeout_cost="none", see CLUE_GIVER_FREE_TIMEOUTS_PER_ROUND),
    # and from the second one onward it costs a completed interaction instead
    # of a skip (timeout_cost="interaction") -- see _consume_human_clue_timeout.
    if timeout_cost == "interaction":
        st.session_state.round_interactions = st.session_state.get("round_interactions", 0) + 1
    elif timeout_cost == "skip":
        st.session_state.round_skips = st.session_state.get("round_skips", 0) + 1
    if normalized_hint and normalized_hint not in st.session_state.used_hints:
        st.session_state.used_hints.append(normalized_hint)
    st.session_state.interaction_history.append(
        {
            "turn": interaction_sequence,
            "completed_turn_number": st.session_state.round_interactions,
            "skip_number": st.session_state.get("round_skips", 0),
            "clue_giver": clue_giver,
            "guesser": guesser,
            "hint": normalized_hint,
            "hint_number": hint_number,
            "intended_targets": intended_targets,
            "expected_guesses": expected_guesses,
            "guess_rationale": guess_rationale,
            "guess_rationale_word_count": len(guess_rationale.split()) if guess_rationale else 0,
            "hint_explanation": hint_explanation,
            "guesses": [],
            "guess_order": guess_order,
            "correct": False,
            "correct_guesses": [],
            "neutral_guesses": [],
            "bomb_guesses": [],
            "bomb_guess": None,
            "bomb_hit": False,
            "outcome": "timeout" if timed_out else "skip",
            "alignment_status": "",
            "error_type": "timeout" if timed_out else "none",
            "skipped": not timed_out,
            "skipped_by": "" if timed_out else skipped_by,
            "partial_skip": False,
            "skip_interpreted_cards": skip_interpreted_cards,
            "repair_required": bool(not timed_out and clue_giver == "ai" and skipped_by == "human"),
            "repair_source_turn": repair_context.get("skipped_turn", ""),
            "repair_source_targets": list(repair_context.get("unresolved_targets", [])),
            "repair_chain_id": repair_context.get("repair_chain_id", "") or (
                f"{st.session_state.get('session_id', '')}:r{st.session_state.get('round', '')}:"
                f"t{interaction_sequence}"
                if not timed_out and clue_giver == "ai" and skipped_by == "human"
                else ""
            ),
            "repair_attempt_number": repair_context.get("repair_attempt_number", ""),
            "repair_attempt": bool(repair_context),
            "repair_same_targets_retried": bool(
                repair_context and set(intended_targets) == set(repair_context.get("unresolved_targets", []))
            ),
            "repair_success": False,
            "timer_duration_seconds": timer_duration_seconds if timer_duration_seconds is not None else st.session_state.get("clue_timer_duration_seconds", CLUE_TIMER_SECONDS),
            "clue_timer_started_at": clue_timer_started_at if clue_timer_started_at is not None else st.session_state.get("clue_timer_started_at", ""),
            "human_timed_out": bool(timed_out),
            "timeout_timestamp": timeout_timestamp if timed_out else "",
            "timed_out": bool(timed_out),
            "timeout_repair_attempt": bool(timed_out and repair_context),
            "timeout_selected_cards": list(timeout_selected_cards) if timed_out else [],
            "wrong_guess_replacements": [],
            "wrong_guess_replacement_actor": "",
            "wrong_guess_replacement_raw_response": "",
            "wrong_guess_replacement_response_time_sec": "",
            "wrong_guess_replacement_attempts": "",
            "completed_guesses": 0,
            "skipped_guesses": int(hint_number or 0),
            "human_expected_ai_understanding_rating": None,
            "hint_raw_response": hint_raw_response,
            "hint_time_sec": hint_time_sec,
            "hint_response_time_sec": hint_response_time_sec,
            "hint_attempts": hint_attempts,
            "guess_raw_response": guess_raw_response,
            "guess_time_sec": guess_time_sec,
            "guess_response_time_sec": guess_response_time_sec,
            "remaining_targets_before_turn": [
                word
                for word in st.session_state.target_words
                if word not in st.session_state.found_targets
            ],
            "remaining_targets_after_turn": [
                word
                for word in st.session_state.target_words
                if word not in st.session_state.found_targets
            ],
            "hit_rate": 0.0,
            "target_yield": 0,
            "jaccard_alignment": 0.0,
            "turn_score_delta": 0,
            "turn_start_time": turn_start.isoformat(),
            "turn_end_time": turn_end.isoformat(),
            "turn_duration_seconds": (turn_end - turn_start).total_seconds(),
            "reflection_start_time": "",
            "reflection_end_time": "",
            "reflection_time_sec": "",
            "recorded_at": turn_end.isoformat(),
            "reflection_rating": "",
            "reflection_relationship_type": "",
            "reflection_explanation_raw": human_explanation_raw,
            "reflection_explanation_is_valid": human_explanation_is_valid if human_explanation_is_valid is not None else "",
            "reflection_blocked_reason": "",
            "human_perceived_understanding_rating": "",
            "human_relationship_type": "",
            "human_explanation_raw": human_explanation_raw,
            "human_explanation_sanitized": human_explanation_raw if human_explanation_is_valid else "",
            "human_explanation_is_valid": human_explanation_is_valid if human_explanation_is_valid is not None else "",
            "human_explanation_blocked_reason": human_explanation_blocked_reason,
            "human_explanation_source": human_explanation_source,
            "human_explanation_collected_at": human_explanation_collected_at,
            "ai_relationship_type": "",
            "ai_explanation_raw": "",
            "ai_explanation_sanitized": "",
            "ai_explanation_is_valid": "",
            "ai_explanation_blocked_reason": "",
            "ai_explanation": "",
            "reflection_source": "",
        }
    )
    st.session_state.pending_reflection_turn = None if timed_out else interaction_sequence

    if st.session_state.round_interactions >= MAX_INTERACTIONS_PER_ROUND:
        finish_round()


def record_forced_timeout_loss(hint, hint_number, intended_targets=None, expected_guesses=None):
    """Both skips are already used, and the one-last-chance final timer (see
    FINAL_GUESS_TIMER_SECONDS) has now also expired with no guess/clue
    submitted. End the round immediately as a loss rather than letting a
    stalling participant keep the round (and the clock) open indefinitely."""
    if st.session_state.get("clue_timer_timeout_consumed", False):
        return None
    st.session_state.clue_timer_timeout_consumed = True
    timeout_timestamp = datetime.now(timezone.utc).isoformat()
    intended_targets = intended_targets or []
    expected_guesses = expected_guesses or []
    interaction_sequence = len(st.session_state.interaction_history) + 1
    clue_giver = "human" if st.session_state.role == "human_clue" else "ai"
    guesser = "ai" if st.session_state.role == "human_clue" else "human"
    normalized_hint = (hint or "").strip().lower()
    st.session_state.interaction_history.append(
        {
            "turn": interaction_sequence,
            "completed_turn_number": st.session_state.round_interactions,
            "skip_number": st.session_state.get("round_skips", 0),
            "clue_giver": clue_giver,
            "guesser": guesser,
            "hint": normalized_hint,
            "hint_number": hint_number,
            "intended_targets": intended_targets,
            "expected_guesses": expected_guesses,
            "guesses": [],
            "correct": False,
            "correct_guesses": [],
            "neutral_guesses": [],
            "bomb_guesses": [],
            "bomb_hit": False,
            "outcome": "timeout_loss",
            "error_type": "timeout_loss",
            "skipped": False,
            "partial_skip": False,
            "timed_out": True,
            "human_timed_out": True,
            "timeout_timestamp": timeout_timestamp,
            "completed_guesses": 0,
            "skipped_guesses": int(hint_number or 0),
        }
    )
    st.session_state.pending_reflection_turn = None
    finish_round(forced_loss_reason="timeout_loss")
    return timeout_timestamp


def record_timeout(
    hint,
    hint_number,
    intended_targets=None,
    expected_guesses=None,
    guess_rationale="",
    hint_explanation="",
    timeout_selected_cards=None,
    skip_interpreted_cards=None,
    repair_context=None,
    hint_raw_response="",
    hint_time_sec=None,
    human_expected_ai_understanding_rating=None,
    human_explanation_raw="",
    human_explanation_is_valid=None,
    human_explanation_blocked_reason="",
    human_explanation_source="",
    human_explanation_collected_at="",
    timeout_cost="skip",
):
    if st.session_state.get("clue_timer_timeout_consumed", False):
        return None
    st.session_state.clue_timer_timeout_consumed = True
    timeout_timestamp = datetime.now(timezone.utc).isoformat()
    record_skip(
        hint,
        hint_number,
        intended_targets,
        expected_guesses,
        guess_rationale=guess_rationale,
        hint_explanation=hint_explanation,
        skipped_by="",
        hint_raw_response=hint_raw_response,
        hint_time_sec=hint_time_sec,
        skip_interpreted_cards=skip_interpreted_cards,
        repair_context=repair_context,
        timed_out=True,
        timeout_timestamp=timeout_timestamp,
        timeout_selected_cards=timeout_selected_cards,
        human_explanation_raw=human_explanation_raw,
        human_explanation_is_valid=human_explanation_is_valid,
        human_explanation_blocked_reason=human_explanation_blocked_reason,
        human_explanation_source=human_explanation_source,
        human_explanation_collected_at=human_explanation_collected_at,
        timeout_cost=timeout_cost,
    )
    if st.session_state.get("interaction_history"):
        st.session_state.interaction_history[-1]["human_expected_ai_understanding_rating"] = (
            human_expected_ai_understanding_rating
        )
    return timeout_timestamp


def finish_round(forced_loss_reason=None):
    st.session_state.round_finished = True
    bomb_words = st.session_state.get("bomb_words") or [st.session_state.bomb_word]
    st.session_state.round_bomb_hit = any(
        guess in bomb_words for guess in st.session_state.guesses
    )
    st.session_state.round_success = (
        len(st.session_state.found_targets) == len(st.session_state.target_words)
    )
    if forced_loss_reason:
        st.session_state.round_end_reason = forced_loss_reason
    elif st.session_state.round_bomb_hit:
        st.session_state.round_end_reason = "bomb"
    elif st.session_state.round_success:
        st.session_state.round_end_reason = "all_targets_found"
    elif st.session_state.round_interactions >= MAX_INTERACTIONS_PER_ROUND:
        st.session_state.round_end_reason = "completed_turn_limit"
    else:
        st.session_state.round_end_reason = ""
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
    word_type_per_card = st.session_state.get("word_type_per_card", {})

    def word_types_for(words):
        missing = [word for word in words if not word_type_per_card.get(word)]
        if missing:
            raise BoardGenerationError(
                "Cannot summarize round because these words have no word_type: "
                + ", ".join(missing)
            )
        return [word_type_per_card[word] for word in words]

    st.session_state.ai_round_summaries.append(
        {
            "round": st.session_state.round,
            "role": st.session_state.role,
            "word_type": st.session_state.word_type,
            "board_template_id": st.session_state.get("board_template_id", ""),
            "board_material_version": st.session_state.get("board_material_version", ""),
            "board_instance_id": st.session_state.get("board_instance_id", ""),
            "word_type_per_card": dict(word_type_per_card),
            "targets": list(st.session_state.target_words),
            "target_word_types": word_types_for(st.session_state.target_words),
            "neutral_word_types": word_types_for(st.session_state.neutral_words),
            "bomb": list(st.session_state.get("bomb_words", [])),
            "bomb_word_types": word_types_for(st.session_state.get("bomb_words", [])),
            "success": bool(st.session_state.round_success),
            "bomb_hit": bool(st.session_state.round_bomb_hit),
            "medal": st.session_state.round_medal,
            "turns": st.session_state.round_interactions,
            "found_targets": list(st.session_state.found_targets),
            "skips": st.session_state.get("round_skips", 0),
            "interactions": [
                {
                    "turn": item.get("turn"),
                    "completed_turn_number": item.get("completed_turn_number", ""),
                    "skip_number": item.get("skip_number", ""),
                    "clue_giver": item.get("clue_giver"),
                    "guesser": item.get("guesser"),
                    "hint": item.get("hint"),
                    "hint_number": item.get("hint_number"),
                    "intended_targets": list(item.get("intended_targets", [])),
                    "expected_guesses": list(item.get("expected_guesses", [])),
                    "guess_rationale": item.get("guess_rationale", ""),
                    "guess_rationale_word_count": item.get("guess_rationale_word_count", 0),
                    "hint_explanation": item.get("hint_explanation", ""),
                    "hint_time_sec": item.get("hint_time_sec"),
                    "guesses": list(item.get("guesses", [])),
                    "guess_order": list(item.get("guess_order", [])),
                    "guess_time_sec": item.get("guess_time_sec"),
                    "correct_guesses": list(item.get("correct_guesses", [])),
                    "neutral_guesses": list(item.get("neutral_guesses", [])),
                    "bomb_guesses": list(item.get("bomb_guesses", [])),
                    "bomb_guess": item.get("bomb_guess"),
                    "outcome": item.get("outcome"),
                    "alignment_status": item.get("alignment_status", ""),
                    "error_type": item.get("error_type", ""),
                    "skipped": bool(item.get("skipped", False)),
                    "skipped_by": item.get("skipped_by"),
                    "partial_skip": bool(item.get("partial_skip", False)),
                    "skip_interpreted_cards": list(item.get("skip_interpreted_cards", [])),
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
                    "completed_guesses": item.get("completed_guesses", len(item.get("guesses", []))),
                    "skipped_guesses": item.get("skipped_guesses", 0),
                    "human_expected_ai_understanding_rating": item.get("human_expected_ai_understanding_rating"),
                    "reflection_rating": item.get("reflection_rating", ""),
                    "reflection_relationship_type": item.get("reflection_relationship_type", ""),
                    "reflection_explanation_raw": item.get("reflection_explanation_raw", ""),
                    "reflection_explanation_is_valid": item.get("reflection_explanation_is_valid", ""),
                    "reflection_blocked_reason": item.get("reflection_blocked_reason", ""),
                    "human_perceived_understanding_rating": item.get("human_perceived_understanding_rating", ""),
                    "human_relationship_type": item.get("human_relationship_type", ""),
                    "human_explanation_raw": item.get("human_explanation_raw", ""),
                    "human_explanation_sanitized": item.get("human_explanation_sanitized", ""),
                    "human_explanation_is_valid": item.get("human_explanation_is_valid", ""),
                    "human_explanation_blocked_reason": item.get("human_explanation_blocked_reason", ""),
                    "human_explanation_source": item.get("human_explanation_source", ""),
                    "human_explanation_collected_at": item.get("human_explanation_collected_at", ""),
                    "ai_relationship_type": item.get("ai_relationship_type", ""),
                    "ai_explanation_raw": item.get("ai_explanation_raw", ""),
                    "ai_explanation_sanitized": item.get("ai_explanation_sanitized", ""),
                    "ai_explanation_is_valid": item.get("ai_explanation_is_valid", ""),
                    "ai_explanation_blocked_reason": item.get("ai_explanation_blocked_reason", ""),
                    "ai_explanation": item.get("ai_explanation", ""),
                    "reflection_source": item.get("reflection_source", ""),
                    "reflection_start_time": item.get("reflection_start_time", ""),
                    "reflection_end_time": item.get("reflection_end_time", ""),
                    "reflection_time_sec": item.get("reflection_time_sec", ""),
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
