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


def screen_name():
    st.markdown('<div class="center-actions compact-field">', unsafe_allow_html=True)
    name = st.text_input("Your name", placeholder="Your name", label_visibility="collapsed")
    if st.button("Continue", type="primary", use_container_width=True):
        if not name.strip():
            st.error("Please enter your name.")
        else:
            st.session_state.participant_id = name.strip()
            initialize_session_log(name.strip())
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


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
    st.session_state.hint_explanation = ""
    st.session_state.pending_guesses = []
    st.session_state.pending_ai_guess_review = None
    st.session_state.pending_hint_meta = None


def _word_count(text):
    return len([word for word in text.split() if word.strip()])


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
        log_event(
            "reflection_shown",
            {"reflection_source": "human_clue_giver" if human_clue_giver else "ai_clue_giver"},
            turn_number=item.get("turn", ""),
        )
        item["reflection_shown_logged"] = True

    render_top_status()
    with st.container(border=True, key="reflection_panel"):
        st.markdown(
            """
            <div class="reflection-header">
                <div class="reflection-title">Turn Reflection</div>
                <div class="reflection-subtitle">Help us understand how the clue was interpreted.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        ai_explanation = item.get("ai_explanation_sanitized") or item.get("ai_explanation", "")
        if not human_clue_giver and ai_explanation:
            st.markdown(
                f"""
                <div class="glass-card compact-card reflection-ai-explanation">
                    <div class="panel-title">AI clue explanation</div>
                    <p class="subtle-text" style="margin:0;">{escape(ai_explanation)}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.radio(
            "How well was your intended meaning understood?"
            if human_clue_giver
            else "How well did you understand the AI's intended meaning?",
            options=list(RATING_OPTIONS.keys()),
            index=2,
            format_func=lambda option: f"{option}",
            horizontal=True,
            key=f"reflection_rating_{st.session_state.round}_{item.get('turn')}",
        )
        explanation_key = f"reflection_explanation_{st.session_state.round}_{item.get('turn')}"
        relationship_key = f"reflection_relationship_{st.session_state.round}_{item.get('turn')}"
        if show_full_form:
            st.selectbox(
                "What type of relationship did your clue mainly express?",
                options=RELATIONSHIP_OPTIONS,
                key=relationship_key,
            )
            st.text_area(
                "Briefly describe the general relationship behind your clue.",
                value=st.session_state.get(explanation_key, ""),
                max_chars=150,
                key=explanation_key,
            )
            st.caption("Do not mention any card names or target words.")

        if st.button("Continue", type="primary", use_container_width=True):
            rating = st.session_state[f"reflection_rating_{st.session_state.round}_{item.get('turn')}"]
            relationship_type = ""
            explanation = ""
            if show_full_form:
                relationship_type = st.session_state[relationship_key]
                explanation = st.session_state.get(explanation_key, "")
                if _word_count(explanation) > 20 or len(explanation) > 150:
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
        st.markdown(
            """
            <div class="glass-card compact-card section-gap">
                <div class="panel-title">After AI guessed</div>
                <p class="subtle-text" style="margin:0;">Save this turn to reflect on how your clue was understood.</p>
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
                hint_explanation=pending_review.get("hint_explanation", ""),
                ai_understanding_rating_before=pending_review.get("rating_before"),
                guess_raw_response=pending_review.get("guess_raw_response", ""),
                guess_response_time_sec=pending_review.get("guess_response_time_sec"),
            )
            st.session_state.pending_ai_guess_review = None
            if not st.session_state.round_finished:
                st.session_state.previous_hint = st.session_state.hint
                st.session_state.hint = ""
                st.session_state.hint_number = 1
                st.session_state.hint_targets = []
                st.session_state.hint_explanation = ""
            st.rerun()
        render_interaction_history(st.session_state.interaction_history)
        return

    st.markdown(
        """
        <div class="panel-title section-gap">Enter your clue for the AI guesser</div>
        """,
        unsafe_allow_html=True,
    )

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

    st.markdown("<div class='let-ai-guess-marker'></div>", unsafe_allow_html=True)
    st.caption(
        "The AI can also ask for the next clue if this clue looks too risky. "
        + _skip_help_text()
    )
    st.markdown(
        """
        <div class="glass-card compact-card section-gap">
            <div class="panel-title">Before AI guesses</div>
            <p class="subtle-text" style="margin:0;">How well do you expect the AI understood your clue?</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    rating_before = st.radio(
        "Before AI guess rating",
        options=list(RATING_OPTIONS.keys()),
        index=max(0, st.session_state.ai_understanding_rating_before - 1),
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
        else:
            st.session_state.hint = hint.strip().lower()
            st.session_state.hint_number = int(hint_number)
            st.session_state.current_turn_start_time = datetime.utcnow().isoformat()
            intended_targets = st.session_state.hint_targets[:]
            log_event(
                "clue_submitted",
                {
                    "clue": st.session_state.hint,
                    "clue_number": st.session_state.hint_number,
                    "intended_cards": intended_targets,
                },
                turn_number=st.session_state.round_interactions + 1,
            )
            log_event("ai_guess_started", {"clue": st.session_state.hint}, turn_number=st.session_state.round_interactions + 1)
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

            action = guess_result.get("action", "guess")
            log_event(
                "ai_guess_completed",
                {"action": action, "guesses": guess_result.get("guesses", [])},
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
                    st.session_state.get("hint_explanation", ""),
                    skipped_by="ai",
                    guess_raw_response=guess_result.get("raw_response", ""),
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
                    "hint_explanation": "",
                    "rating_before": rating_before,
                    "guess_raw_response": guess_result.get("raw_response", ""),
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
                clickable=True,
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
                    record_interaction(
                        st.session_state.hint,
                        st.session_state.hint_number,
                        submitted_guesses,
                        st.session_state.hint_targets,
                        hint_explanation=st.session_state.get("hint_explanation", ""),
                        hint_raw_response=pending_meta.get("raw_response", ""),
                        hint_response_time_sec=pending_meta.get("response_time_sec"),
                        hint_attempts=pending_meta.get("attempts"),
                        hint_used_fallback=pending_meta.get("used_fallback", False),
                    )
                    log_event(
                        "human_guess_submitted",
                        {"guessed_cards": submitted_guesses},
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
                    if not st.session_state.round_finished:
                        st.session_state.previous_hint = st.session_state.hint
                        st.session_state.hint = ""
                        st.session_state.hint_number = 1
                        st.session_state.hint_targets = []
                        st.session_state.hint_explanation = ""
                    st.session_state.pending_hint_meta = None
                st.rerun()

    if not st.session_state.hint:
        st.markdown(
            """
            <div class="glass-card compact-card section-gap">
                <div class="panel-title">Clue</div>
                <p class="subtle-text" style="margin:0;">Ask the AI for a clue when you are ready.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Ask AI for a clue", type="primary", use_container_width=True):
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
            st.session_state.hint = hint_result.get("hint", "")
            st.session_state.hint_number = hint_result.get("hint_number", 1)
            st.session_state.hint_targets = hint_result.get("intended_targets", [])
            st.session_state.hint_explanation = hint_result.get("explanation", "")
            st.session_state.current_turn_start_time = datetime.utcnow().isoformat()
            st.session_state.pending_hint_meta = {
                "raw_response": hint_result.get("raw_response", ""),
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
        st.caption(_skip_help_text())
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
                st.session_state.get("hint_explanation", ""),
                skipped_by="human",
                hint_raw_response=pending_meta.get("raw_response", ""),
                hint_response_time_sec=pending_meta.get("response_time_sec"),
                hint_attempts=pending_meta.get("attempts"),
                hint_used_fallback=pending_meta.get("used_fallback", False),
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
    player_name = st.session_state.get("participant_id") or "Player"
    total_score = st.session_state.get("score", 0)
    if not st.session_state.get("session_completed_logged"):
        if not st.session_state.get("completion_code"):
            st.session_state.completion_code = (
                str(st.session_state.get("session_id", "")).replace("-", "")[-8:].upper()
            )
        log_session_state(completed=True)
        log_event(
            "session_completed",
            {
                "final_total_score": total_score,
                "completion_code": st.session_state.completion_code,
            },
            round_number="",
            turn_number="",
        )
        st.session_state.session_completed_logged = True
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
    remote_status = st.session_state.get("remote_log_status")
    remote_error = st.session_state.get("remote_log_error", "")
    if remote_status == "github_saved":
        st.info(f"The run has been saved to GitHub, {player_name}.")
    elif remote_status == "github_failed":
        st.warning(f"The run was saved locally, but GitHub logging failed: {remote_error}")
    elif remote_status == "local_only":
        st.info(f"The run has been saved locally, {player_name}.")
    else:
        st.info(f"The run has been saved locally, {player_name}.")

    st.markdown('<div class="center-actions">', unsafe_allow_html=True)
    if st.button("Play again", type="primary", use_container_width=True):
        restart_game(keep_participant=True)
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
