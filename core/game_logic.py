import hashlib
import random
from datetime import datetime

import streamlit as st

from core.constants import (
    BOARD_SIZE,
    BOMB_COUNT,
    MAX_INTERACTIONS_PER_ROUND,
    MAX_SKIPS_PER_ROUND,
    MEDAL_POINTS,
    N_ROUNDS,
    TARGET_COUNT,
)
from core.words import BOARD_TEMPLATES, WORD_BANKS


class BoardGenerationError(ValueError):
    pass


def get_word_type_for_round(round_number):
    return "mixed"


def get_role_for_round(round_number, starting_role=None):
    starting_role = starting_role or st.session_state.get("starting_role", "human_clue")
    if round_number % 2 == 1:
        return starting_role
    return "ai_clue" if starting_role == "human_clue" else "human_clue"


def get_board_template_type(round_number):
    return "A" if round_number % 2 == 1 else "B"


def _unique_words(words):
    seen = set()
    unique = []
    for word in words:
        key = word.strip().lower()
        if key not in seen:
            unique.append(word)
            seen.add(key)
    return unique


def required_word_counts(round_count=N_ROUNDS):
    counts = {"abstract": 0, "concrete": 0}
    for round_number in range(1, round_count + 1):
        template = BOARD_TEMPLATES[get_board_template_type(round_number)]
        for role_counts in template.values():
            counts["abstract"] += role_counts["abstract"]
            counts["concrete"] += role_counts["concrete"]
    return counts


def validate_word_bank_capacity(round_count=N_ROUNDS):
    required = required_word_counts(round_count)
    available = {
        "abstract": len(_unique_words(WORD_BANKS["abstract"])),
        "concrete": len(_unique_words(WORD_BANKS["concrete"])),
    }
    shortages = [
        f"{word_type}: need {required[word_type]}, found {available[word_type]}"
        for word_type in ("abstract", "concrete")
        if available[word_type] < required[word_type]
    ]
    if shortages:
        raise BoardGenerationError(
            "Not enough unique words to create 4 balanced rounds without repetition. "
            + "; ".join(shortages)
            + ". Add more unique words to the existing word lists before running the study."
        )


def _draw_words(pool, count, used_words):
    used_keys = {word.lower() for word in used_words}
    available = [word for word in _unique_words(pool) if word.lower() not in used_keys]
    if len(available) < count:
        raise BoardGenerationError(
            "Not enough unused unique words available for the mixed board. "
            "A word used in an earlier round cannot be reused in this session."
        )
    selected = random.sample(available, count)
    used_words.extend(selected)
    return selected


def _required_counts_for_template(template):
    return {
        "abstract": sum(role_counts["abstract"] for role_counts in template.values()),
        "concrete": sum(role_counts["concrete"] for role_counts in template.values()),
    }


def _validate_round_availability(template, used_by_type):
    required = _required_counts_for_template(template)
    shortages = []
    for word_type in ("abstract", "concrete"):
        used_keys = {word.lower() for word in used_by_type.get(word_type, [])}
        available_count = len(
            [
                word
                for word in _unique_words(WORD_BANKS[word_type])
                if word.lower() not in used_keys
            ]
        )
        if available_count < required[word_type]:
            shortages.append(
                f"{word_type}: need {required[word_type]} unused, found {available_count}"
            )
    if shortages:
        raise BoardGenerationError(
            "Not enough unused words remain to create this balanced round without repetition. "
            + "; ".join(shortages)
            + "."
        )


def _build_word_type_map(board_words):
    abstract_lookup = {word.lower(): word for word in _unique_words(WORD_BANKS["abstract"])}
    concrete_lookup = {word.lower(): word for word in _unique_words(WORD_BANKS["concrete"])}
    word_types = {}
    missing = []
    duplicated_type = []

    for word in board_words:
        key = word.lower()
        in_abstract = key in abstract_lookup
        in_concrete = key in concrete_lookup
        if in_abstract and in_concrete:
            duplicated_type.append(word)
        elif in_abstract:
            word_types[word] = "abstract"
        elif in_concrete:
            word_types[word] = "concrete"
        else:
            missing.append(word)

    if missing or duplicated_type:
        details = []
        if missing:
            details.append(f"missing type for: {', '.join(missing)}")
        if duplicated_type:
            details.append(f"appears in both word lists: {', '.join(duplicated_type)}")
        raise BoardGenerationError(
            "Every board word must have exactly one word_type. " + "; ".join(details)
        )

    if len(word_types) != len(board_words):
        raise BoardGenerationError("word_type_per_card is incomplete for this board.")
    return word_types


def build_board_id(round_number, template_type, board_words, word_roles):
    board_signature = "|".join(
        f"{word}:{word_roles.get(word, '')}" for word in sorted(board_words)
    )
    digest = hashlib.sha1(board_signature.encode("utf-8")).hexdigest()[:10]
    return f"round-{round_number}-template-{template_type}-{digest}"


def _draw_role_words(template, role_name, used_words):
    abstract_words = _draw_words(
        WORD_BANKS["abstract"],
        template[role_name]["abstract"],
        used_words["abstract"],
    )
    concrete_words = _draw_words(
        WORD_BANKS["concrete"],
        template[role_name]["concrete"],
        used_words["concrete"],
    )
    return abstract_words + concrete_words


def sample_fixed_round_words(round_number):
    validate_word_bank_capacity()
    template_type = get_board_template_type(round_number)
    template = BOARD_TEMPLATES[template_type]
    used_by_type = st.session_state.setdefault(
        "used_board_words_by_type",
        {"abstract": [], "concrete": []},
    )
    used_by_type.setdefault("abstract", [])
    used_by_type.setdefault("concrete", [])
    _validate_round_availability(template, used_by_type)

    targets = _draw_role_words(template, "target", used_by_type)
    neutrals = _draw_role_words(template, "neutral", used_by_type)
    bombs = _draw_role_words(template, "bomb", used_by_type)
    board_words = targets + neutrals + bombs
    if len(board_words) != BOARD_SIZE:
        raise ValueError(f"Round {round_number} must contain exactly {BOARD_SIZE} words.")
    if len(set(word.lower() for word in board_words)) != BOARD_SIZE:
        raise ValueError(f"Round {round_number} contains duplicate board words.")

    word_roles = {word: "target" for word in targets}
    word_roles.update({word: "neutral" for word in neutrals})
    word_roles.update({word: "bomb" for word in bombs})
    word_types = _build_word_type_map(board_words)

    random.shuffle(board_words)
    used_board_words = st.session_state.setdefault("used_board_words", [])
    used_board_words.extend(board_words)
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
    st.session_state.board_template_type = template_type
    st.session_state.board_id = build_board_id(
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
    st.session_state.round_finished = False
    st.session_state.hint = ""
    st.session_state.hint_number = 1
    st.session_state.hint_targets = []
    st.session_state.hint_expected_guesses = []
    st.session_state.hint_explanation = ""
    st.session_state.last_ai_guesses = []
    st.session_state.last_ai_hint = ""
    st.session_state.perception_rating = None
    st.session_state.ai_understanding_rating_before = None
    st.session_state.ai_understanding_rating_after = None
    st.session_state.pending_ai_guess_review = None
    st.session_state.previous_hint = None
    st.session_state.start_time = datetime.utcnow()
    st.session_state.round_start_time = st.session_state.start_time.isoformat()
    st.session_state.current_turn_start_time = ""
    st.session_state.current_hint_start_time = ""
    st.session_state.current_guess_start_time = ""
    st.session_state.current_reflection_start_time = ""
    st.session_state.last_score_change = 0
    st.session_state.round_medal = "none"
    st.session_state.round_success = False
    st.session_state.round_bomb_hit = False
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
    expected_guesses=None,
    guess_rationale="",
    hint_explanation="",
    ai_understanding_rating_before=None,
    ai_understanding_rating_after=None,
    hint_raw_response="",
    hint_time_sec=None,
    hint_response_time_sec=None,
    hint_attempts=None,
    hint_used_fallback=False,
    guess_raw_response="",
    guess_time_sec=None,
    guess_response_time_sec=None,
):
    intended_targets = intended_targets or []
    expected_guesses = expected_guesses or []
    guess_rationale = (guess_rationale or "").strip()
    guess_order = [
        {"position": position, "word": guess}
        for position, guess in enumerate(guesses or [], start=1)
    ]
    turn_end = datetime.utcnow()
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
            "alignment_status": alignment_status,
            "error_type": error_type,
            "ai_understanding_rating_before": ai_understanding_rating_before,
            "ai_understanding_rating_after": ai_understanding_rating_after,
            "hint_raw_response": hint_raw_response,
            "hint_time_sec": hint_time_sec,
            "hint_response_time_sec": hint_response_time_sec,
            "hint_attempts": hint_attempts,
            "hint_used_fallback": bool(hint_used_fallback),
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
            "reflection_explanation_raw": "",
            "reflection_explanation_is_valid": "",
            "reflection_blocked_reason": "",
            "human_understanding_rating": "",
            "human_relationship_type": "",
            "human_explanation_raw": "",
            "human_explanation_sanitized": "",
            "human_explanation_is_valid": "",
            "human_explanation_blocked_reason": "",
            "ai_relationship_type": "",
            "ai_explanation_raw": "",
            "ai_explanation_sanitized": "",
            "ai_explanation_is_valid": "",
            "ai_explanation_blocked_reason": "",
            "ai_explanation": "",
            "reflection_source": "",
        }
    )
    st.session_state.pending_reflection_turn = st.session_state.round_interactions

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
    expected_guesses=None,
    guess_rationale="",
    hint_explanation="",
    skipped_by=None,
    hint_raw_response="",
    hint_time_sec=None,
    hint_response_time_sec=None,
    hint_attempts=None,
    hint_used_fallback=False,
    guess_raw_response="",
    guess_time_sec=None,
    guess_response_time_sec=None,
):
    intended_targets = intended_targets or []
    expected_guesses = expected_guesses or []
    guess_rationale = (guess_rationale or "").strip()
    guess_order = []
    turn_end = datetime.utcnow()
    turn_start_raw = st.session_state.get("current_turn_start_time") or turn_end.isoformat()
    try:
        turn_start = datetime.fromisoformat(turn_start_raw)
    except ValueError:
        turn_start = turn_end
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
            "outcome": "skip",
            "alignment_status": "",
            "error_type": "none",
            "skipped": True,
            "skipped_by": skipped_by,
            "ai_understanding_rating_before": None,
            "ai_understanding_rating_after": None,
            "hint_raw_response": hint_raw_response,
            "hint_time_sec": hint_time_sec,
            "hint_response_time_sec": hint_response_time_sec,
            "hint_attempts": hint_attempts,
            "hint_used_fallback": bool(hint_used_fallback),
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
            "reflection_explanation_raw": "",
            "reflection_explanation_is_valid": "",
            "reflection_blocked_reason": "",
            "human_understanding_rating": "",
            "human_relationship_type": "",
            "human_explanation_raw": "",
            "human_explanation_sanitized": "",
            "human_explanation_is_valid": "",
            "human_explanation_blocked_reason": "",
            "ai_relationship_type": "",
            "ai_explanation_raw": "",
            "ai_explanation_sanitized": "",
            "ai_explanation_is_valid": "",
            "ai_explanation_blocked_reason": "",
            "ai_explanation": "",
            "reflection_source": "",
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
            "board_template_type": st.session_state.get("board_template_type", ""),
            "board_id": st.session_state.get("board_id", ""),
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
                    "ai_understanding_rating_before": item.get("ai_understanding_rating_before"),
                    "ai_understanding_rating_after": item.get("ai_understanding_rating_after"),
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
