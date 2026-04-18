from html import escape

import streamlit as st

from core.ai_service import (
    ai_guess,
    generate_ai_hint,
    generate_ai_hint_reroll,
    validate_human_hint,
)
from core.constants import N_ROUNDS, TEAM_GOAL_SCORE
from core.game_logic import finish_round
from core.storage import log_round
from core.state import restart_game
from ui.components import (
    RATING_OPTIONS,
    render_board,
    render_board_legend,
    render_hint_panel,
    render_round_chip,
    render_top_status,
)


def screen_welcome():
    st.markdown(
        f"""
        <div class="welcome-grid">
            <div class="glass-card">
                <div class="panel-title">How to play</div>
                <h2 style="margin-top:0; margin-bottom:0.55rem;">Play this game with the AI as one team</h2>
                <p class="subtle-text">
                    You and the AI help each other find the correct word cards.
                    In each round, one of you gives a clue and the other one guesses.
                </p>
                <div class="feature-list">
                    <div class="feature-item feature-target"><strong>Find the green cards</strong>Each correct green card gives your team 1 point.</div>
                    <div class="feature-item feature-gold"><strong>Find the gold card</strong>The gold card is special and gives 3 points.</div>
                    <div class="feature-item feature-bomb"><strong>Do not touch red</strong>If anyone picks the red bomb card, the round ends and that round becomes -1 point.</div>
                    <div class="feature-item feature-neutral"><strong>Keep extra chances</strong>If you do not use all clue changes, you get bonus points later.</div>
                </div>
            </div>
            <div class="glass-card">
                <div class="panel-title">Simple steps</div>
                <h3 style="margin-top:0; margin-bottom:0.55rem;">What you do in the game</h3>
                <div class="choice-row">
                    <div class="choice-pill">{N_ROUNDS} rounds</div>
                    <div class="choice-pill">Take turns with the AI</div>
                    <div class="choice-pill">Some words are easy, some are tricky</div>
                    <div class="choice-pill">Goal: {TEAM_GOAL_SCORE} points</div>
                </div>
                <div class="mini-steps">
                    <div class="mini-step">1. Look at the words on the board.</div>
                    <div class="mini-step">2. The roles switch every round: sometimes you give the clue, sometimes the AI does.</div>
                    <div class="mini-step">3. Some rounds use abstract words and some use concrete words.</div>
                    <div class="mini-step">4. Try to make a clue that helps with more than one safe target card, not only the gold card.</div>
                    <div class="mini-step">5. Pick the words that best match the clue and help your team earn the most points.</div>
                    <div class="mini-step">6. Save the round and move to the next one.</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="center-actions">', unsafe_allow_html=True)
    if st.button("Start game", type="primary", use_container_width=True):
        st.session_state.started = True
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def screen_name():
    st.markdown(
        """
        <div class="glass-card compact-card">
            <div class="panel-title">Player</div>
            <h3 style="margin-top:0; margin-bottom:0.35rem;">Enter your name</h3>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="center-actions compact-field">', unsafe_allow_html=True)
    name = st.text_input("Your name", placeholder="Your name", label_visibility="collapsed")
    if st.button("Continue", type="primary", use_container_width=True):
        if not name.strip():
            st.error("Please enter your name.")
        else:
            st.session_state.participant_id = name.strip()
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def screen_human_clue():
    if st.session_state.round_finished:
        screen_round_summary()
        return

    render_top_status()
    render_round_chip("You are the clue-giver this round")

    with st.container(border=True):
        st.markdown('<div class="panel-title">Your secret board</div>', unsafe_allow_html=True)
        render_board(
            st.session_state.board,
            st.session_state.word_roles,
            reveal_all=True,
        )
        render_board_legend()

    st.markdown(
        """
        <div class="panel-title section-gap">Enter your clue for the AI guesser</div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        clue_col, count_col = st.columns([4.2, 1.25])
        with clue_col:
            hint = st.text_input(
                "Hint",
                value=st.session_state.hint,
                placeholder="One-word clue...",
                label_visibility="collapsed",
            )
        with count_col:
            hint_number = st.selectbox(
                "Words",
                options=[1, 2, 3, 4],
                index=max(0, st.session_state.hint_number - 1),
                label_visibility="collapsed",
                key=f"clue_count_{st.session_state.round}",
            )

    if st.button("Let AI guess", type="primary", use_container_width=True):
        is_valid, error_message = validate_human_hint(hint, st.session_state.board)
        if not is_valid:
            st.error(error_message)
        else:
            st.session_state.hint = hint.strip().lower()
            st.session_state.hint_number = int(hint_number)
            with st.spinner("AI is thinking..."):
                ai_guesses = ai_guess(
                    st.session_state.board,
                    st.session_state.hint,
                    st.session_state.hint_number,
                    st.session_state.ai_rerolls,
                )

            if ai_guesses == ["__REROLL_HINT__"]:
                if st.session_state.ai_rerolls > 0:
                    st.session_state.ai_rerolls -= 1
                    st.warning("The AI asked for another clue.")
                else:
                    st.warning("No AI rerolls remain. Please adjust the clue.")
            else:
                st.session_state.guesses = ai_guesses
                finish_round()
                st.rerun()


def screen_human_guesser():
    if st.session_state.round_finished:
        screen_round_summary()
        return

    render_top_status()
    render_round_chip("You are the guesser this round")

    board_col, side_col = st.columns([1.55, 0.95])

    with board_col:
        with st.container(border=True):
            st.markdown('<div class="panel-title">Board</div>', unsafe_allow_html=True)

            if not st.session_state.hint:
                render_board(
                    st.session_state.board,
                    st.session_state.word_roles,
                    guesses=st.session_state.guesses,
                    reveal_all=False,
                )
            else:
                clicked = render_board(
                    st.session_state.board,
                    st.session_state.word_roles,
                    guesses=st.session_state.guesses,
                    reveal_all=False,
                    clickable=True,
                    max_clicks=st.session_state.hint_number,
                )
                if clicked:
                    if st.session_state.round_finished:
                        finish_round()
                    st.rerun()

                if (
                    not st.session_state.round_finished
                    and len(st.session_state.guesses) >= st.session_state.hint_number
                ):
                    finish_round()
                    st.rerun()

    with side_col:
        if not st.session_state.hint:
            st.markdown(
                """
                <div class="glass-card compact-card">
                    <div class="panel-title">Clue</div>
                    <p class="subtle-text" style="margin:0;">Ask the AI for a clue when you are ready.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Ask AI for a clue", type="primary", use_container_width=True):
                with st.spinner("AI is generating a clue..."):
                    hint, hint_number = generate_ai_hint(
                        st.session_state.target_words,
                        st.session_state.bomb_word,
                        st.session_state.neutral_words,
                        st.session_state.word_type,
                        st.session_state.golden_target,
                    )
                st.session_state.hint = hint
                st.session_state.hint_number = hint_number
                st.rerun()
        else:
            render_hint_panel(
                st.session_state.hint,
                st.session_state.hint_number,
                st.session_state.previous_hint,
            )
            if st.session_state.human_rerolls > 0:
                if st.button(
                    f"Different clue ({st.session_state.human_rerolls} left)",
                    use_container_width=True,
                ):
                    st.session_state.human_rerolls -= 1
                    st.session_state.previous_hint = st.session_state.hint
                    with st.spinner("AI is generating a new clue..."):
                        hint, hint_number = generate_ai_hint_reroll(
                            st.session_state.target_words,
                            st.session_state.bomb_word,
                            st.session_state.neutral_words,
                            st.session_state.word_type,
                            st.session_state.golden_target,
                            st.session_state.previous_hint,
                        )
                    st.session_state.hint = hint
                    st.session_state.hint_number = hint_number
                    st.rerun()


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
        score_prefix = "+" if st.session_state.last_score_change > 0 else ""

        st.markdown(
            f"""
            <div class="summary-stat"><strong>Guesses:</strong> {escape(guesses_text)}</div>
            <div class="summary-stat"><strong>Golden card:</strong> {escape(st.session_state.golden_target)}</div>
            <div class="summary-stat"><strong>Round score:</strong> {score_prefix}{st.session_state.last_score_change}</div>
            """,
            unsafe_allow_html=True,
        )

    with action_col:
        st.markdown(
            """
            <div class="glass-card compact-card">
                <div class="panel-title">Quick rating</div>
                <p class="subtle-text" style="margin:0;">How well did the AI fit your thinking this round?</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        selected_label = st.radio(
            "Round rating",
            options=list(RATING_OPTIONS.keys()),
            index=max(0, st.session_state.perception_rating - 1),
            format_func=lambda option: f"{option}",
            horizontal=True,
            label_visibility="collapsed",
            key=f"rating_radio_{st.session_state.round}",
        )
        st.caption("1 low  2  3  4  5 strong")
        st.session_state.perception_rating = selected_label

        if st.button("Save round and continue", type="primary", use_container_width=True):
            log_round(st.session_state.participant_id)

            if st.session_state.round >= N_ROUNDS:
                bonus = st.session_state.ai_rerolls + st.session_state.human_rerolls
                st.session_state.score += bonus
                st.session_state.game_over = True
            else:
                st.session_state.round += 1
                st.session_state.board = None
                st.session_state.round_finished = False
                st.session_state.guesses = []
                st.session_state.hint = ""
                st.session_state.hint_number = 1
                st.session_state.previous_hint = None

            st.rerun()


def screen_game_over():
    bonus = st.session_state.ai_rerolls + st.session_state.human_rerolls
    base_score = st.session_state.score - bonus
    reached_goal = st.session_state.score >= TEAM_GOAL_SCORE
    player_name = st.session_state.get("participant_id") or "Player"
    title = "Goal reached" if reached_goal else "Run finished"
    subtitle = (
        f"{player_name}, you reached the target of {TEAM_GOAL_SCORE} points."
        if reached_goal
        else f"{player_name}, you finished below the target of {TEAM_GOAL_SCORE} points."
    )

    st.markdown(
        f"""
        <div class="glass-card game-over-card">
            <div class="panel-title">Final result</div>
            <h2 style="margin-top:0; margin-bottom:0.45rem;">{title}</h2>
            <p class="subtle-text" style="margin-bottom:0;">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("Base score", base_score)
    col2.metric("Hint bonus", f"+{bonus}")
    col3.metric("Final score", st.session_state.score)

    if reached_goal:
        st.success(f"Strong teamwork, {player_name}. The session ended above the target score.")
    else:
        st.info(f"The session ended below the target score, {player_name}, but the run has been saved correctly.")

    st.markdown('<div class="center-actions">', unsafe_allow_html=True)
    if st.button("Play again", use_container_width=True):
        restart_game(keep_participant=True)
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
