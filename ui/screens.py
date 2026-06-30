from datetime import datetime
from html import escape

import streamlit as st

from core.ai_service import (
    ai_guess,
    generate_ai_round_reflection,
    generate_ai_hint,
    generate_ai_turn_explanation,
    remaining_target_count,
    validate_human_hint_with_history,
)
from core.constants import (
    BOARD_SIZE,
    BOMB_COUNT,
    MAX_SKIPS_PER_ROUND,
    MAX_TEAM_SCORE,
    N_ROUNDS,
    TARGET_COUNT,
    TEAM_GOAL_SCORE,
)
from core.game_logic import (
    can_skip_current_clue,
    record_interaction,
    record_skip,
    update_current_round_summary,
)
from core.storage import initialize_session_log, log_event, log_round, log_session_state
from core.state import restart_game
from core.validation import mentions_board_word
from ui.components import (
    MEDAL_LABELS,
    RATING_OPTIONS,
    render_board,
    render_board_legend,
    render_hint_panel,
    render_hint_target_selector,
    render_interaction_history,
    render_round_chip,
    render_top_status,
)

RELATIONSHIP_OPTIONS = [
    "Category / shared type",
    "Theme / shared situation",
    "Function / use or purpose",
    "Other",
]

POST_GAME_QUESTIONS = [
    (
        "ai_understood_my_clues",
        "I felt that the AI understood what I meant when I gave clues.",
    ),
    (
        "i_understood_ai_clues",
        "I felt that I understood what the AI meant when it gave clues.",
    ),
    (
        "predict_ai_interpretation",
        "By the end of the game, I could predict how the AI would interpret my clues.",
    ),
    (
        "adapted_to_ai_behavior",
        "I adapted my communication based on the AI's behaviour.",
    ),
    (
        "ai_adapted_to_me",
        "I felt that the AI adapted to my communication during the game.",
    ),
    (
        "reflection_helped",
        "The reflection steps helped improve the communication between me and the AI.",
    ),
    (
        "shared_strategy",
        "By the end of the game, I felt that the AI and I were working with a shared strategy.",
    ),
]

AGE_GROUP_OPTIONS = ["18-24", "25-34", "35-44", "45-54", "55+", "Prefer not to say"]
GENDER_OPTIONS = [
    "Female",
    "Male",
    "Non-binary",
    "Prefer to self-describe",
    "Prefer not to say",
]
ENGLISH_PROFICIENCY_OPTIONS = [
    "Beginner",
    "Intermediate",
    "Advanced",
    "Native / Near-native",
]
AI_EXPERIENCE_OPTIONS = [
    "Never",
    "Less than once a month",
    "A few times a month",
    "A few times a week",
    "Daily",
]
CODENAMES_EXPERIENCE_OPTIONS = [
    "Never",
    "Once or twice",
    "Occasionally",
    "Frequently",
]

BOARD_WORD_ERROR = (
    "Your explanation mentions a board word. Please describe the relationship without naming specific cards."
)


def screen_welcome():
    st.markdown(
        f"""
        <div class="guide-shell">
            <div class="glass-card guide-intro">
                <div class="panel-title">Game Guide: Team Up with AI</div>
                <p class="subtle-text">This is a cooperative word association game. You and the AI are on the same team, trying to find hidden target cards while avoiding bomb cards.</p>
            </div>
            <div class="guide-grid">
                <div class="guide-card guide-goal">
                    <h3>The Goal</h3>
                    <p>There are 4 rounds in total. Each round has a 4 by 4 board with a mix of abstract and concrete words. Hidden behind the cards are:</p>
                    <ul>
                        <li>{TARGET_COUNT} target cards to find</li>
                        <li>{BOMB_COUNT} bomb cards to avoid</li>
                        <li>{BOARD_SIZE - TARGET_COUNT - BOMB_COUNT} neutral cards that are wrong but safe</li>
                    </ul>
                </div>
                <div class="guide-card">
                    <h3>How to Play</h3>
                    <ol>
                        <li><strong>Roles:</strong> Across rounds, you may alternate between clue-giver and guesser.</li>
                        <li><strong>Give a clue:</strong> The clue-giver gives one word and one number.</li>
                        <li><strong>Guess cards:</strong> The guesser chooses the cards that seem connected to the clue.</li>
                    </ol>
                    <p class="guide-example">Example: If two target cards are linked by food, the clue could be "meal, 2".</p>
                    <ol start="4">
                        <li><strong>Avoid bombs:</strong> If anyone picks a bomb, the round ends immediately.</li>
                        <li><strong>4 turns only:</strong> You have a maximum of 4 turns per round to find all {TARGET_COUNT} targets.</li>
                        <li><strong>Next clue:</strong> If a clue feels too risky, the guesser can skip it and ask for the next clue. This uses one turn.</li>
                    </ol>
                </div>
                <div class="guide-card guide-medals">
                    <h3>Win Medals &amp; Points</h3>
                    <p>The faster you find the {TARGET_COUNT} targets, the better your medal:</p>
                    <ul>
                        <li>&#129351; Gold (5 pts): Finish in 1 or 2 turns.</li>
                        <li>&#129352; Silver (4 pts): Finish in 3 turns.</li>
                        <li>&#129353; Bronze (3 pts): Finish in 4 turns.</li>
                    </ul>
                    <p>Pro Tip: Try to think like your AI partner! The better you "connect," the more points you'll earn.</p>
                </div>
                <div class="guide-card guide-research">
                    <h3>After Each Turn</h3>
                    <p>After each hint and guess, you will answer a short reflection question.</p>
                    <ol>
                        <li><strong>Rate understanding:</strong> Tell us how well your intended meaning was understood.</li>
                        <li><strong>Describe the relationship:</strong> Briefly describe the general relationship behind the clue.</li>
                        <li><strong>Keep it general:</strong> Do not mention card names or target words in your reflection.</li>
                    </ol>
                    <p>The game interface is the same for all participants.</p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="center-actions">', unsafe_allow_html=True)
    if st.button("Start the game", type="primary", use_container_width=True):
        st.session_state.started = True
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def _anonymous_participant_id():
    session_id = str(st.session_state.get("session_id", "")).replace("-", "")
    suffix = session_id[-8:] if session_id else "unknown"
    return f"participant_{suffix}"


def _display_player_name():
    return st.session_state.get("nickname") or "Participant"


def screen_name():
    with st.container(border=True, key="participant_profile_panel"):
        st.markdown(
            """
            <div class="panel-title">Participant profile</div>
            <p class="subtle-text" style="margin-top:0;">These answers help us analyze the game results.</p>
            """,
            unsafe_allow_html=True,
        )
        nickname = st.text_input(
            "Nickname (optional)",
            value=st.session_state.get("nickname", ""),
            placeholder="Optional nickname",
        )
        age_group = st.selectbox(
            "What is your age group?",
            [""] + AGE_GROUP_OPTIONS,
            index=0,
            format_func=lambda option: "Select age group" if option == "" else option,
            key="profile_age_group",
        )
        gender_choice = st.radio(
            "What is your gender? Optional",
            GENDER_OPTIONS,
            index=None,
            horizontal=True,
            key="profile_gender",
        )
        gender_self_describe = ""
        if gender_choice == "Prefer to self-describe":
            gender_self_describe = st.text_input(
                "Self-describe",
                placeholder="Write your gender",
                key="profile_gender_self_describe",
            )
        english_proficiency = st.radio(
            "How would you describe your English proficiency?",
            ENGLISH_PROFICIENCY_OPTIONS,
            index=None,
            horizontal=True,
            key="profile_english_proficiency",
        )
        ai_experience = st.radio(
            "How often do you use AI tools such as ChatGPT, Gemini, or Claude?",
            AI_EXPERIENCE_OPTIONS,
            index=None,
            horizontal=True,
            key="profile_ai_experience",
        )
        codenames_experience = st.radio(
            "Have you played Codenames before?",
            CODENAMES_EXPERIENCE_OPTIONS,
            index=None,
            horizontal=True,
            key="profile_codenames_experience",
        )

        if st.button("Continue", type="primary", use_container_width=True):
            missing = []
            if not age_group:
                missing.append("age group")
            if gender_choice is None:
                missing.append("gender")
            if gender_choice == "Prefer to self-describe" and not gender_self_describe.strip():
                missing.append("self-described gender")
            if english_proficiency is None:
                missing.append("English proficiency")
            if ai_experience is None:
                missing.append("AI experience")
            if codenames_experience is None:
                missing.append("Codenames experience")
            if missing:
                st.error("Please complete: " + ", ".join(missing) + ".")
            else:
                clean_nickname = nickname.strip()
                participant_id = clean_nickname or _anonymous_participant_id()
                gender = (
                    f"Self-describe: {gender_self_describe.strip()}"
                    if gender_choice == "Prefer to self-describe"
                    else gender_choice
                )
                st.session_state.nickname = clean_nickname
                st.session_state.participant_id = participant_id
                st.session_state.age_group = age_group
                st.session_state.gender = gender
                st.session_state.english_proficiency = english_proficiency
                st.session_state.ai_experience = ai_experience
                st.session_state.codenames_experience = codenames_experience
                initialize_session_log(participant_id)
                st.rerun()


def _skip_help_text():
    used = st.session_state.get("round_skips", 0)
    remaining = max(0, MAX_SKIPS_PER_ROUND - used)
    if not can_skip_current_clue():
        return "Next clue is not available now: you either used both skips or this is the final turn."
    return (
        f"Use only when the clue feels too risky. It burns one of the 4 turns in this round. "
        f"Remaining skips this round: {remaining}."
    )


def _clear_current_clue():
    st.session_state.previous_hint = st.session_state.hint
    st.session_state.hint = ""
    st.session_state.hint_number = 1
    st.session_state.hint_targets = []
    st.session_state.hint_expected_guesses = []
    st.session_state.hint_explanation = ""
    st.session_state.pending_guesses = []
    st.session_state.current_guess_rationale = ""
    st.session_state.current_hint_start_time = ""
    st.session_state.current_guess_start_time = ""
    st.session_state.current_reflection_start_time = ""
    st.session_state.pending_ai_guess_review = None
    st.session_state.pending_hint_meta = None


def _word_count(text):
    return len([word for word in text.split() if word.strip()])


def _now_iso():
    return datetime.utcnow().isoformat()


def _seconds_between(start_iso, end_iso=None):
    if not start_iso:
        return None
    try:
        start = datetime.fromisoformat(start_iso)
        end = datetime.fromisoformat(end_iso) if end_iso else datetime.utcnow()
        return round((end - start).total_seconds(), 3)
    except (TypeError, ValueError):
        return None


def _ensure_timer(key):
    if not st.session_state.get(key):
        st.session_state[key] = _now_iso()


def _available_guess_options():
    guessed = set(st.session_state.get("guesses", []))
    return [word for word in st.session_state.get("board", []) if word not in guessed]


def _guess_rationale_key():
    return f"guess_rationale_{st.session_state.round}_{st.session_state.round_interactions}"


def _render_guess_rationale_input():
    key = _guess_rationale_key()
    existing = st.session_state.get(key, st.session_state.get("current_guess_rationale", ""))
    st.session_state[key] = existing
    st.markdown(
        """
        <div class="guess-rationale-head">
            <div class="panel-title">Why these cards?</div>
            <div class="guess-rationale-rule">3-30 words, before selecting cards</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    rationale = st.text_area(
        "Guess reasoning",
        max_chars=240,
        placeholder="Write 3-30 words. Example: Fortune points to luck, so I prefer Wealth over Crown...",
        label_visibility="collapsed",
        key=key,
    )
    st.session_state.current_guess_rationale = rationale
    word_count = _word_count(rationale)
    is_valid = 3 <= word_count <= 30
    status_class = "ok" if is_valid else "pending"
    status_text = (
        f"{word_count} / 30 words"
        if word_count
        else "Write a short reason, then choose cards"
    )
    if word_count and not is_valid:
        status_text = "Use 3 to 30 words"
    st.markdown(
        f"<div class='guess-rationale-status {status_class}'>{escape(status_text)}</div>",
        unsafe_allow_html=True,
    )
    return rationale.strip(), is_valid


def _mentions_board_word(text, board_words):
    return mentions_board_word(text, board_words)


def _current_pending_reflection_item():
    pending_turn = st.session_state.get("pending_reflection_turn")
    if not pending_turn:
        return None
    for item in st.session_state.get("interaction_history", []):
        if item.get("turn") == pending_turn:
            return item
    st.session_state.pending_reflection_turn = None
    return None


def _sync_reflection_to_round_summary(item):
    for summary in st.session_state.get("ai_round_summaries", []):
        if summary.get("round") != st.session_state.round:
            continue
        for summary_item in summary.get("interactions", []):
            if summary_item.get("turn") == item.get("turn"):
                for key in [
                    "reflection_rating",
                    "reflection_relationship_type",
                    "reflection_explanation_raw",
                    "reflection_explanation_is_valid",
                    "reflection_blocked_reason",
                    "reflection_start_time",
                    "reflection_end_time",
                    "reflection_time_sec",
                    "human_understanding_rating",
                    "human_relationship_type",
                    "human_explanation_raw",
                    "human_explanation_is_valid",
                    "human_explanation_blocked_reason",
                    "ai_relationship_type",
                    "ai_explanation_raw",
                    "ai_explanation_sanitized",
                    "ai_explanation_is_valid",
                    "ai_explanation_blocked_reason",
                    "ai_explanation",
                    "reflection_source",
                ]:
                    summary_item[key] = item.get(key, "")


def _save_turn_reflection(item, rating, relationship_type, explanation):
    explanation = (explanation or "").strip()
    rating = int(rating)
    item["reflection_rating"] = rating
    item["human_understanding_rating"] = rating
    st.session_state.perception_rating = rating
    if item.get("clue_giver") == "human":
        item["reflection_relationship_type"] = relationship_type or ""
        item["reflection_explanation_raw"] = explanation
        item["human_explanation_sanitized"] = explanation
        item["reflection_explanation_is_valid"] = True
        item["reflection_blocked_reason"] = ""
        item["human_relationship_type"] = relationship_type or ""
        item["human_explanation_raw"] = explanation
        item["human_explanation_sanitized"] = explanation
        item["human_explanation_is_valid"] = True
        item["human_explanation_blocked_reason"] = ""
        item["reflection_source"] = "human_clue_giver"
    else:
        item["reflection_relationship_type"] = ""
        item["reflection_explanation_raw"] = ""
        item["human_explanation_sanitized"] = ""
        item["reflection_explanation_is_valid"] = True
        item["reflection_blocked_reason"] = ""
        item["human_relationship_type"] = ""
        item["human_explanation_raw"] = ""
        item["human_explanation_sanitized"] = ""
        item["human_explanation_is_valid"] = True
        item["human_explanation_blocked_reason"] = ""
        item["reflection_source"] = "ai_clue_giver"
    _sync_reflection_to_round_summary(item)
    st.session_state.pending_reflection_turn = None


def render_turn_reflection():
    item = _current_pending_reflection_item()
    if not item:
        return False
    human_clue_giver = item.get("clue_giver") == "human"
    show_full_form = human_clue_giver and item.get("alignment_status") != "perfect"
    if not item.get("reflection_shown_logged"):
        reflection_start = _now_iso()
        st.session_state.current_reflection_start_time = reflection_start
        item["reflection_start_time"] = reflection_start
        log_event(
            "reflection_shown",
            {"reflection_source": "human_clue_giver" if human_clue_giver else "ai_clue_giver"},
            turn_number=item.get("turn", ""),
        )
        item["reflection_shown_logged"] = True

    render_top_status()
    with st.container(border=True, key="reflection_panel"):
        ai_explanation = item.get("ai_explanation_sanitized") or item.get("ai_explanation", "")
        header_body = (
            escape(ai_explanation)
            if not human_clue_giver and ai_explanation
            else "Rate the clue understanding and add the general link."
        )
        st.markdown(
            f"""
            <div class="glass-card compact-card reflection-ai-explanation reflection-compact-head">
                <div class="panel-title">Turn reflection</div>
                <p class="subtle-text" style="margin:0;">{header_body}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        explanation_key = f"reflection_explanation_{st.session_state.round}_{item.get('turn')}"
        relationship_key = f"reflection_relationship_{st.session_state.round}_{item.get('turn')}"
        if show_full_form:
            rating_col, relationship_col = st.columns([1, 1.35])
        else:
            rating_col = st.container()
            relationship_col = None

        with rating_col:
            st.radio(
                "Understood?",
                options=list(RATING_OPTIONS.keys()),
                index=None,
                format_func=lambda option: f"{option}",
                horizontal=True,
                key=f"reflection_rating_{st.session_state.round}_{item.get('turn')}",
            )
        if show_full_form:
            with relationship_col:
                st.selectbox(
                    "Relationship",
                    options=RELATIONSHIP_OPTIONS,
                    key=relationship_key,
                )
            st.text_area(
                "General link (3-20 words, no card names)",
                value=st.session_state.get(explanation_key, ""),
                max_chars=150,
                placeholder="Example: Both ideas connect through luck and success.",
                key=explanation_key,
            )

        if st.button("Continue", type="primary", use_container_width=True):
            rating = st.session_state[f"reflection_rating_{st.session_state.round}_{item.get('turn')}"]
            if rating is None:
                st.error("Please select a rating before continuing.")
                return True
            reflection_end_time = _now_iso()
            reflection_start_time = item.get("reflection_start_time") or st.session_state.get(
                "current_reflection_start_time", ""
            )
            item["reflection_start_time"] = reflection_start_time
            item["reflection_end_time"] = reflection_end_time
            item["reflection_time_sec"] = _seconds_between(
                reflection_start_time,
                reflection_end_time,
            )
            relationship_type = ""
            explanation = ""
            if show_full_form:
                relationship_type = st.session_state[relationship_key]
                explanation = st.session_state.get(explanation_key, "")
                explanation_word_count = _word_count(explanation)
                if explanation_word_count < 3:
                    item["reflection_explanation_raw"] = explanation.strip()
                    item["human_explanation_sanitized"] = ""
                    item["reflection_explanation_is_valid"] = False
                    item["reflection_blocked_reason"] = "too_short"
                    item["human_explanation_raw"] = explanation.strip()
                    item["human_explanation_sanitized"] = ""
                    item["human_explanation_is_valid"] = False
                    item["human_explanation_blocked_reason"] = "too_short"
                    log_event(
                        "reflection_blocked",
                        {"reason": "too_short"},
                        turn_number=item.get("turn", ""),
                    )
                    st.error("Please write at least 3 words about the general relationship behind your clue.")
                    return True
                if explanation_word_count > 20 or len(explanation) > 150:
                    item["reflection_explanation_raw"] = explanation.strip()
                    item["human_explanation_sanitized"] = ""
                    item["reflection_explanation_is_valid"] = False
                    item["reflection_blocked_reason"] = "too_long"
                    item["human_explanation_raw"] = explanation.strip()
                    item["human_explanation_sanitized"] = ""
                    item["human_explanation_is_valid"] = False
                    item["human_explanation_blocked_reason"] = "too_long"
                    log_event(
                        "reflection_blocked",
                        {"reason": "too_long"},
                        turn_number=item.get("turn", ""),
                    )
                    st.error("Please keep your explanation to 20 words or 150 characters.")
                    return True
                if _mentions_board_word(explanation, st.session_state.get("board", [])):
                    item["reflection_explanation_raw"] = explanation.strip()
                    item["human_explanation_sanitized"] = ""
                    item["reflection_explanation_is_valid"] = False
                    item["reflection_blocked_reason"] = "board_word"
                    item["human_explanation_raw"] = explanation.strip()
                    item["human_explanation_sanitized"] = ""
                    item["human_explanation_is_valid"] = False
                    item["human_explanation_blocked_reason"] = "board_word"
                    log_event(
                        "reflection_blocked",
                        {"reason": "board_word"},
                        turn_number=item.get("turn", ""),
                    )
                    st.error(BOARD_WORD_ERROR)
                    return True

            _save_turn_reflection(item, rating, relationship_type, explanation)
            log_event(
                "reflection_submitted",
                {"reflection_source": item.get("reflection_source", "")},
                turn_number=item.get("turn", ""),
            )
            st.rerun()

    render_interaction_history(st.session_state.interaction_history)
    return True


def screen_human_clue():
    if st.session_state.get("pending_reflection_turn"):
        if render_turn_reflection():
            return

    if st.session_state.round_finished:
        screen_round_summary()
        return

    render_top_status()

    with st.container(border=True):
        st.markdown('<div class="panel-title">Your secret board</div>', unsafe_allow_html=True)
        pending_review = st.session_state.get("pending_ai_guess_review")
        review_guesses = pending_review.get("guesses", []) if pending_review else []
        render_board(
            st.session_state.board,
            st.session_state.word_roles,
            guesses=st.session_state.guesses + review_guesses,
            reveal_all=True,
        )
        render_board_legend()

    if st.session_state.get("pending_ai_guess_review"):
        pending_review = st.session_state.pending_ai_guess_review
        guesses_text = ", ".join(pending_review.get("guesses", []))
        st.info(f"AI selected: {guesses_text}")
        guess_rationale = pending_review.get("guess_rationale", "")
        if guess_rationale:
            st.markdown(
                f"""
                <div class="glass-card compact-card section-gap">
                    <div class="panel-title">AI guess reasoning</div>
                    <p class="subtle-text" style="margin:0;">{escape(guess_rationale)}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        if st.button("Save this turn", type="primary", use_container_width=True):
            st.session_state.last_ai_guesses = pending_review.get("guesses", [])
            record_interaction(
                pending_review.get("hint", ""),
                pending_review.get("hint_number", 1),
                pending_review.get("guesses", []),
                pending_review.get("intended_targets", []),
                expected_guesses=pending_review.get("expected_guesses", []),
                guess_rationale=pending_review.get("guess_rationale", ""),
                hint_explanation=pending_review.get("hint_explanation", ""),
                ai_understanding_rating_before=pending_review.get("rating_before"),
                hint_time_sec=pending_review.get("hint_time_sec"),
                guess_raw_response=pending_review.get("guess_raw_response", ""),
                guess_time_sec=pending_review.get("guess_time_sec"),
                guess_response_time_sec=pending_review.get("guess_response_time_sec"),
            )
            st.session_state.pending_ai_guess_review = None
            if not st.session_state.round_finished:
                st.session_state.previous_hint = st.session_state.hint
                st.session_state.hint = ""
                st.session_state.hint_number = 1
                st.session_state.hint_targets = []
                st.session_state.hint_expected_guesses = []
                st.session_state.hint_explanation = ""
                st.session_state.current_hint_start_time = ""
                st.session_state.current_guess_start_time = ""
                st.session_state.current_reflection_start_time = ""
            st.rerun()
        render_interaction_history(st.session_state.interaction_history)
        return

    st.markdown(
        """
        <div class="panel-title section-gap">Enter your clue for the AI guesser</div>
        """,
        unsafe_allow_html=True,
    )
    _ensure_timer("current_hint_start_time")

    with st.container(border=True):
        clue_col, count_col = st.columns([4.2, 1.2])
        max_hint_count = remaining_target_count(
            st.session_state.target_words,
            st.session_state.interaction_history,
        )
        with clue_col:
            hint = st.text_input(
                "Hint",
                placeholder="One-word clue...",
                label_visibility="collapsed",
                key=f"human_hint_{st.session_state.round}_{st.session_state.round_interactions}",
            )
        with count_col:
            hint_number = st.selectbox(
                "Count",
                options=list(range(1, max_hint_count + 1)),
                index=min(max(0, st.session_state.hint_number - 1), max_hint_count - 1),
                label_visibility="collapsed",
                key=f"clue_count_{st.session_state.round}_{st.session_state.round_interactions}",
            )

    if st.session_state.last_ai_guesses:
        guesses_text = ", ".join(st.session_state.last_ai_guesses)
        st.info(f"AI selected: {guesses_text}")

    found_targets = set(st.session_state.get("found_targets", []))
    remaining_targets = [
        word for word in st.session_state.target_words if word not in found_targets
    ]
    selected_count = int(hint_number)
    st.session_state.hint_targets = [
        word for word in st.session_state.get("hint_targets", []) if word in remaining_targets
    ][:selected_count]
    render_hint_target_selector(
        remaining_targets,
        st.session_state.hint_targets,
        selected_count,
    )
    expected_guess_key = f"expected_guesses_{st.session_state.round}_{st.session_state.round_interactions}"
    available_guess_options = _available_guess_options()
    existing_expected_guesses = st.session_state.get(
        expected_guess_key,
        st.session_state.get("hint_expected_guesses", []),
    )
    current_expected_guesses = [
        word
        for word in existing_expected_guesses
        if word in available_guess_options
    ][:selected_count]
    st.session_state.hint_expected_guesses = current_expected_guesses
    st.session_state[expected_guess_key] = current_expected_guesses
    st.markdown(
        """
        <div class="panel-title section-gap">Select the cards you think the AI will choose</div>
        """,
        unsafe_allow_html=True,
    )
    st.multiselect(
        "Expected AI guesses",
        options=available_guess_options,
        max_selections=selected_count,
        placeholder=f"Choose {selected_count} card(s)...",
        label_visibility="collapsed",
        key=expected_guess_key,
    )
    st.session_state.hint_expected_guesses = st.session_state.get(expected_guess_key, [])

    st.markdown("<div class='let-ai-guess-marker'></div>", unsafe_allow_html=True)
    with st.container(border=True, key="before_ai_guess_panel"):
        prompt_col, rating_col = st.columns([1.45, 1])
        with prompt_col:
            st.markdown(
                """
                <div class="panel-title">Before AI guesses</div>
                <p class="subtle-text before-ai-question">How well do you expect the AI understood your clue?</p>
                """,
                unsafe_allow_html=True,
            )
        with rating_col:
            rating_before = st.radio(
                "Before AI guess rating",
                options=list(RATING_OPTIONS.keys()),
                index=None,
                format_func=lambda option: f"{option}",
                horizontal=True,
                label_visibility="collapsed",
                key=f"before_ai_guess_rating_{st.session_state.round}_{st.session_state.round_interactions}",
            )
    st.session_state.ai_understanding_rating_before = rating_before

    if st.button("Let AI Guess", type="primary", use_container_width=True):
        is_valid, error_message = validate_human_hint_with_history(
            hint,
            st.session_state.board,
            st.session_state.interaction_history,
            st.session_state.used_hints,
        )
        if not is_valid:
            st.error(error_message)
        elif len(st.session_state.hint_targets) != selected_count:
            st.error(f"Please select exactly {selected_count} target card(s) for this clue.")
        elif len(st.session_state.hint_expected_guesses) != selected_count:
            st.error(f"Please select exactly {selected_count} card(s) you think the AI will choose.")
        elif rating_before is None:
            st.error("Please select how well you expect the AI understood your clue.")
        else:
            hint_end_time = _now_iso()
            hint_time_sec = _seconds_between(
                st.session_state.get("current_hint_start_time", ""),
                hint_end_time,
            )
            st.session_state.hint = hint.strip().lower()
            st.session_state.hint_number = int(hint_number)
            st.session_state.current_turn_start_time = st.session_state.get(
                "current_hint_start_time", hint_end_time
            )
            intended_targets = st.session_state.hint_targets[:]
            expected_guess_cards = st.session_state.hint_expected_guesses[:]
            log_event(
                "clue_submitted",
                {
                    "clue": st.session_state.hint,
                    "clue_number": st.session_state.hint_number,
                    "intended_cards": intended_targets,
                    "expected_guess_cards": expected_guess_cards,
                },
                turn_number=st.session_state.round_interactions + 1,
            )
            log_event("ai_guess_started", {"clue": st.session_state.hint}, turn_number=st.session_state.round_interactions + 1)
            guess_start_time = _now_iso()
            st.session_state.current_guess_start_time = guess_start_time
            with st.spinner("AI is thinking..."):
                guess_result = ai_guess(
                    st.session_state.board,
                    st.session_state.hint,
                    st.session_state.hint_number,
                    0,
                    st.session_state.interaction_history,
                    st.session_state.guesses,
                    st.session_state.ai_round_summaries,
                    MAX_SKIPS_PER_ROUND - st.session_state.get("round_skips", 0),
                    can_skip_current_clue(),
                    condition=st.session_state.get("condition", "adaptive"),
                )
            guess_end_time = _now_iso()
            guess_time_sec = _seconds_between(guess_start_time, guess_end_time)

            action = guess_result.get("action", "guess")
            log_event(
                "ai_guess_completed",
                {
                    "action": action,
                    "guesses": guess_result.get("guesses", []),
                    "guess_rationale": guess_result.get("guess_rationale", ""),
                    "raw_response": guess_result.get("raw_response", ""),
                },
                turn_number=st.session_state.round_interactions + 1,
            )
            if action == "reroll":
                if st.session_state.ai_rerolls > 0:
                    st.session_state.ai_rerolls -= 1
                    st.warning("The AI asked for another clue.")
                else:
                    st.warning("No AI rerolls remain. Please adjust the clue.")
            elif action == "skip":
                record_skip(
                    st.session_state.hint,
                    st.session_state.hint_number,
                    intended_targets,
                    expected_guess_cards,
                    guess_rationale=guess_result.get("guess_rationale", ""),
                    hint_explanation=st.session_state.get("hint_explanation", ""),
                    hint_time_sec=hint_time_sec,
                    skipped_by="ai",
                    guess_raw_response=guess_result.get("raw_response", ""),
                    guess_time_sec=guess_time_sec,
                    guess_response_time_sec=guess_result.get("response_time_sec"),
                )
                _clear_current_clue()
                st.info("AI chose not to risk this clue. One turn was used; please give the next clue.")
                st.rerun()
            else:
                st.session_state.pending_ai_guess_review = {
                    "hint": st.session_state.hint,
                    "hint_number": st.session_state.hint_number,
                    "guesses": guess_result.get("guesses", []),
                    "intended_targets": intended_targets,
                    "expected_guesses": expected_guess_cards,
                    "guess_rationale": guess_result.get("guess_rationale", ""),
                    "hint_explanation": "",
                    "rating_before": rating_before,
                    "hint_time_sec": hint_time_sec,
                    "guess_raw_response": guess_result.get("raw_response", ""),
                    "guess_time_sec": guess_time_sec,
                    "guess_response_time_sec": guess_result.get("response_time_sec"),
                }
                st.rerun()

    render_interaction_history(st.session_state.interaction_history)


def screen_human_guesser():
    if st.session_state.get("pending_reflection_turn"):
        if render_turn_reflection():
            return

    if st.session_state.round_finished:
        screen_round_summary()
        return

    render_top_status()

    if not st.session_state.hint:
        if not st.session_state.get("ai_clue_intro_seen", False):
            st.markdown(
                """
                <div class="glass-card compact-card section-gap">
                    <div class="panel-title">Clue</div>
                    <p class="subtle-text" style="margin:0;">Ask the AI for a clue when you are ready.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.session_state.ai_clue_intro_seen = True
        if st.button("Ask AI for a clue", type="primary", use_container_width=True):
            hint_start_time = _now_iso()
            st.session_state.current_hint_start_time = hint_start_time
            with st.spinner("AI is generating a clue..."):
                hint_result = generate_ai_hint(
                    st.session_state.target_words,
                    st.session_state.bomb_words,
                    st.session_state.neutral_words,
                    st.session_state.word_type,
                    st.session_state.interaction_history,
                    st.session_state.used_hints,
                    st.session_state.ai_round_summaries,
                    condition=st.session_state.get("condition", "adaptive"),
                )
            hint_end_time = _now_iso()
            hint_time_sec = _seconds_between(hint_start_time, hint_end_time)
            st.session_state.hint = hint_result.get("hint", "")
            st.session_state.hint_number = hint_result.get("hint_number", 1)
            st.session_state.hint_targets = hint_result.get("intended_targets", [])
            st.session_state.hint_expected_guesses = hint_result.get("expected_guesses", [])
            st.session_state.hint_explanation = hint_result.get("explanation", "")
            st.session_state.current_turn_start_time = hint_start_time
            st.session_state.current_guess_start_time = hint_end_time
            st.session_state.pending_hint_meta = {
                "raw_response": hint_result.get("raw_response", ""),
                "hint_time_sec": hint_time_sec,
                "response_time_sec": hint_result.get("response_time_sec"),
                "attempts": hint_result.get("attempts"),
                "used_fallback": hint_result.get("used_fallback", False),
            }
            st.rerun()
    else:
        render_hint_panel(
            st.session_state.hint,
            st.session_state.hint_number,
            st.session_state.previous_hint,
        )
        guess_rationale, rationale_is_valid = _render_guess_rationale_input()

    with st.container(border=True):
        st.markdown('<div class="panel-title">Board</div>', unsafe_allow_html=True)

        if not st.session_state.hint:
            render_board(
                st.session_state.board,
                st.session_state.word_roles,
                guesses=st.session_state.guesses + st.session_state.pending_guesses,
                reveal_all=False,
            )
        else:
            clicked = render_board(
                st.session_state.board,
                st.session_state.word_roles,
                guesses=st.session_state.guesses + st.session_state.pending_guesses,
                reveal_all=False,
                clickable=rationale_is_valid,
                max_clicks=st.session_state.hint_number + len(st.session_state.guesses),
            )
            if clicked:
                st.session_state.pending_guesses.append(clicked)
                role = st.session_state.word_roles.get(clicked)
                if (
                    role == "bomb"
                    or len(st.session_state.pending_guesses) >= st.session_state.hint_number
                ):
                    pending_meta = st.session_state.get("pending_hint_meta") or {}
                    submitted_guesses = list(st.session_state.pending_guesses)
                    guess_time_sec = _seconds_between(
                        st.session_state.get("current_guess_start_time", "")
                    )
                    record_interaction(
                        st.session_state.hint,
                        st.session_state.hint_number,
                        submitted_guesses,
                        st.session_state.hint_targets,
                        expected_guesses=st.session_state.get("hint_expected_guesses", []),
                        guess_rationale=guess_rationale,
                        hint_explanation=st.session_state.get("hint_explanation", ""),
                        hint_raw_response=pending_meta.get("raw_response", ""),
                        hint_time_sec=pending_meta.get("hint_time_sec"),
                        hint_response_time_sec=pending_meta.get("response_time_sec"),
                        hint_attempts=pending_meta.get("attempts"),
                        hint_used_fallback=pending_meta.get("used_fallback", False),
                        guess_time_sec=guess_time_sec,
                    )
                    log_event(
                        "human_guess_submitted",
                        {
                            "guessed_cards": submitted_guesses,
                            "guess_rationale": guess_rationale,
                        },
                        turn_number=st.session_state.round_interactions,
                    )
                    if st.session_state.interaction_history:
                        latest_item = st.session_state.interaction_history[-1]
                        with st.spinner("AI is summarizing its clue..."):
                            ai_explanation = generate_ai_turn_explanation(
                                latest_item.get("hint", ""),
                                latest_item.get("hint_number", 1),
                                latest_item.get("intended_targets", []),
                                latest_item.get("guesses", []),
                                st.session_state.get("board", []),
                                latest_item.get("hint_explanation", ""),
                            )
                        latest_item["ai_relationship_type"] = ai_explanation.get(
                            "ai_relationship_type", ""
                        )
                        latest_item["ai_explanation_raw"] = ai_explanation.get(
                            "ai_explanation_raw", ""
                        )
                        latest_item["ai_explanation_sanitized"] = ai_explanation.get(
                            "ai_explanation_sanitized", ""
                        )
                        latest_item["ai_explanation_is_valid"] = ai_explanation.get(
                            "ai_explanation_is_valid", False
                        )
                        latest_item["ai_explanation_blocked_reason"] = ai_explanation.get(
                            "ai_explanation_blocked_reason", ""
                        )
                        latest_item["ai_explanation"] = ai_explanation.get(
                            "ai_explanation_sanitized", ai_explanation.get("ai_explanation", "")
                        )
                        latest_item["reflection_source"] = "ai_clue_giver"
                    st.session_state.pending_guesses = []
                    st.session_state.current_guess_rationale = ""
                    st.session_state.current_hint_start_time = ""
                    st.session_state.current_guess_start_time = ""
                    if not st.session_state.round_finished:
                        st.session_state.previous_hint = st.session_state.hint
                        st.session_state.hint = ""
                        st.session_state.hint_number = 1
                        st.session_state.hint_targets = []
                        st.session_state.hint_expected_guesses = []
                        st.session_state.hint_explanation = ""
                    st.session_state.pending_hint_meta = None
                st.rerun()

    if st.session_state.hint:
        if st.button(
            "Skip this clue and ask for the next one",
            use_container_width=True,
            disabled=not can_skip_current_clue() or bool(st.session_state.pending_guesses),
        ):
            pending_meta = st.session_state.get("pending_hint_meta") or {}
            record_skip(
                st.session_state.hint,
                st.session_state.hint_number,
                st.session_state.hint_targets,
                st.session_state.get("hint_expected_guesses", []),
                guess_rationale=guess_rationale if rationale_is_valid else "",
                hint_explanation=st.session_state.get("hint_explanation", ""),
                skipped_by="human",
                hint_raw_response=pending_meta.get("raw_response", ""),
                hint_time_sec=pending_meta.get("hint_time_sec"),
                hint_response_time_sec=pending_meta.get("response_time_sec"),
                hint_attempts=pending_meta.get("attempts"),
                hint_used_fallback=pending_meta.get("used_fallback", False),
                guess_time_sec=_seconds_between(st.session_state.get("current_guess_start_time", "")),
            )
            _clear_current_clue()
            st.rerun()
    render_interaction_history(st.session_state.interaction_history)


def screen_round_summary():
    render_top_status()
    render_round_chip("Round complete")

    summary_col, action_col = st.columns([1.45, 1])

    with summary_col:
        with st.container(border=True):
            st.markdown('<div class="panel-title">Board reveal</div>', unsafe_allow_html=True)
            render_board(
                st.session_state.board,
                st.session_state.word_roles,
                guesses=st.session_state.guesses,
                reveal_all=True,
            )

        guesses_text = ", ".join(st.session_state.guesses) if st.session_state.guesses else "No guesses"
        medal_label = MEDAL_LABELS.get(st.session_state.round_medal, "None")
        outcome = "Bomb hit" if st.session_state.round_bomb_hit else (
            "All targets found" if st.session_state.round_success else "Max turns reached"
        )

        if st.session_state.round_bomb_hit:
            st.error("Bomb hit. The round ended immediately and no medal was awarded.")

        st.markdown(
            f"""
            <div class="summary-stat"><strong>Guesses:</strong> {escape(guesses_text)}</div>
            <div class="summary-stat"><strong>Outcome:</strong> {escape(outcome)}</div>
            <div class="summary-stat"><strong>Medal:</strong> {medal_label}</div>
            """,
            unsafe_allow_html=True,
        )
        render_interaction_history(
            st.session_state.interaction_history,
            show_ai_intended=True,
        )

    with action_col:
        if not st.session_state.get("ai_round_reflection"):
            with st.spinner("AI is reflecting on this round..."):
                st.session_state.ai_round_reflection = generate_ai_round_reflection(
                    st.session_state.target_words,
                    st.session_state.bomb_words,
                    st.session_state.neutral_words,
                    st.session_state.word_type,
                    st.session_state.role,
                    st.session_state.interaction_history,
                    st.session_state.round_success,
                    st.session_state.round_bomb_hit,
                    st.session_state.round_medal,
                )
                update_current_round_summary()

        st.markdown(
            f"""
                <div class="glass-card compact-card">
                <div class="panel-title">AI reflection</div>
                <p class="subtle-text" style="margin:0;">{escape(st.session_state.ai_round_reflection)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.session_state.human_round_feedback = st.text_area(
            "Your message to the AI for next rounds",
            value=st.session_state.get("human_round_feedback", ""),
            placeholder="Tell the AI what you meant by your clue or how you interpreted its clue...",
            key=f"human_round_feedback_{st.session_state.round}",
        )
        feedback_words = _word_count(st.session_state.human_round_feedback)
        st.caption(f"{feedback_words} / 200 words")

        if st.button("Save round and continue", type="primary", use_container_width=True):
            if feedback_words > 200:
                st.error("Please keep your message to 200 words or fewer.")
                return
            update_current_round_summary()
            log_round(st.session_state.participant_id)
            medal = st.session_state.round_medal
            st.session_state.medal_counts[medal] = st.session_state.medal_counts.get(medal, 0) + 1

            if st.session_state.round >= N_ROUNDS:
                st.session_state.game_over = True
            else:
                st.session_state.round += 1
                st.session_state.board = None
                st.session_state.round_finished = False
                st.session_state.guesses = []
                st.session_state.pending_guesses = []
                st.session_state.round_skips = 0
                st.session_state.hint = ""
                st.session_state.hint_number = 1
                st.session_state.hint_targets = []
                st.session_state.hint_explanation = ""
                st.session_state.previous_hint = None
                st.session_state.last_ai_guesses = []
                st.session_state.last_ai_hint = ""
                st.session_state.pending_ai_guess_review = None
                st.session_state.pending_hint_meta = None
                st.session_state.pending_reflection_turn = None
                st.session_state.ai_round_reflection = ""
                st.session_state.human_round_feedback = ""

            st.rerun()


def screen_game_over():
    player_name = _display_player_name()
    total_score = st.session_state.get("score", 0)
    if total_score >= 16:
        title = "Elite team!"
        subtitle = f"Fantastic finish, {player_name}! Your team was sharp, fast, and beautifully in sync."
        tier = "Elite team"
    elif total_score >= 14:
        title = "Excellent team!"
        subtitle = f"Great work, {player_name}! That was a confident run with strong clue-reading."
        tier = "Excellent team"
    elif total_score >= TEAM_GOAL_SCORE:
        title = "Strong team!"
        subtitle = f"Nice work, {player_name}! You cleared the target score and built a solid rhythm."
        tier = "Strong team"
    else:
        title = "Run finished"
        subtitle = f"{player_name}, you were close. A few cleaner clue connections and this team can jump a tier."
        tier = "Building team"

    st.markdown(
        f"""
        <div class="glass-card game-over-card celebration-card">
            <div class="celebration-medals">
                <span>&#129351;</span><span>&#129352;</span><span>&#129353;</span>
            </div>
            <div class="panel-title">Final result</div>
            <h2 style="margin-top:0; margin-bottom:0.45rem;">{title}</h2>
            <p class="subtle-text" style="margin-bottom:0;">{subtitle}</p>
            <div class="final-score">Total score: {total_score} / {MAX_TEAM_SCORE} &middot; {tier}</div>
            <div class="score-tiers">12+ Strong team &middot; 14+ Excellent team &middot; 16+ Elite team</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)
    medal_counts = st.session_state.medal_counts
    col1.markdown(
        f"<div class='summary-stat'><strong>&#129351; Gold</strong><br>{medal_counts.get('gold', 0)}</div>",
        unsafe_allow_html=True,
    )
    col2.markdown(
        f"<div class='summary-stat'><strong>&#129352; Silver</strong><br>{medal_counts.get('silver', 0)}</div>",
        unsafe_allow_html=True,
    )
    col3.markdown(
        f"<div class='summary-stat'><strong>&#129353; Bronze</strong><br>{medal_counts.get('bronze', 0)}</div>",
        unsafe_allow_html=True,
    )

    if not st.session_state.get("post_game_questionnaire_submitted"):
        with st.container(border=True, key="post_game_questionnaire_panel"):
            st.markdown(
                """
                <div class="panel-title">Final questions</div>
                <p class="subtle-text" style="margin-top:0;">Rate each statement from 1 to 5. 5 = very good.</p>
                """,
                unsafe_allow_html=True,
            )
            answers = {}
            for question_id, question_text in POST_GAME_QUESTIONS:
                answers[question_id] = st.radio(
                    question_text,
                    options=[1, 2, 3, 4, 5],
                    index=None,
                    horizontal=True,
                    key=f"post_game_{question_id}",
                )
            if st.button("Submit final answers", type="primary", use_container_width=True):
                missing = [
                    question_text
                    for question_id, question_text in POST_GAME_QUESTIONS
                    if answers.get(question_id) is None
                ]
                if missing:
                    st.error("Please answer all final questions before finishing.")
                    return
                st.session_state.post_game_questionnaire = {
                    question_id: int(answers[question_id])
                    for question_id, _ in POST_GAME_QUESTIONS
                }
                st.session_state.post_game_questionnaire_submitted = True
                if not st.session_state.get("completion_code"):
                    st.session_state.completion_code = (
                        str(st.session_state.get("session_id", "")).replace("-", "")[-8:].upper()
                    )
                log_session_state(completed=True)
                log_event(
                    "post_game_questionnaire_submitted",
                    st.session_state.post_game_questionnaire,
                    round_number="",
                    turn_number="",
                )
                log_event(
                    "session_completed",
                    {
                        "final_total_score": total_score,
                        "completion_code": st.session_state.completion_code,
                        "post_game_questionnaire": st.session_state.post_game_questionnaire,
                    },
                    round_number="",
                    turn_number="",
                )
                st.session_state.session_completed_logged = True
                st.rerun()
        return

    remote_status = st.session_state.get("remote_log_status")
    remote_error = st.session_state.get("remote_log_error", "")
    if remote_status == "github_saved":
        st.success(f"Thank you, {player_name}. Your answers and game data have been saved.")
    elif remote_status == "github_failed":
        st.warning(
            f"Thank you, {player_name}. Your answers were saved locally, but GitHub logging failed: {remote_error}"
        )
    elif remote_status == "local_only":
        st.success(f"Thank you, {player_name}. Your answers and game data have been saved locally.")
    else:
        st.success(f"Thank you, {player_name}. Your answers and game data have been saved locally.")

    st.markdown('<div class="center-actions">', unsafe_allow_html=True)
    if st.button("Play again", type="primary", use_container_width=True):
        restart_game(keep_participant=True)
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
