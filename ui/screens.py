from html import escape

import streamlit as st

from core.ai_service import (
    ai_guess,
    generate_ai_hint,
    remaining_target_count,
    validate_human_hint_with_history,
)
from core.constants import MAX_TEAM_SCORE, N_ROUNDS, TEAM_GOAL_SCORE
from core.game_logic import record_interaction
from core.storage import log_round
from core.state import restart_game
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


def screen_welcome():
    st.markdown(
        f"""
        <div class="guide-shell">
            <div class="glass-card guide-intro">
                <div class="panel-title">Game Guide: Team Up with AI!</div>
                <p class="subtle-text">Welcome! In this game, you and the AI are on the same team. Your goal is to understand each other and find hidden target words together.</p>
            </div>
            <div class="guide-grid">
                <div class="guide-card guide-goal">
                    <h3>The Goal:</h3>
                    <p>There are 8 rounds in total. In each round, you will see 12 cards on the screen:</p>
                    <ul>
                        <li>4 Target Cards (The ones you need to find!)</li>
                        <li>1 Bomb Card (Avoid this at all costs!)</li>
                        <li>7 Neutral Cards (Wrong, but safe.)</li>
                    </ul>
                </div>
                <div class="guide-card">
                    <h3>How to Play:</h3>
                    <ol>
                        <li><strong>Take Turns:</strong> In one round, you give the hint and the AI guesses. In the next round, the AI gives the hint and you guess.</li>
                        <li><strong>Give a Clue:</strong> A clue is just one word and one number.</li>
                    </ol>
                    <p class="guide-example">Example: If the target words are "Apple" and "Banana," you could say: "Fruit, 2".</p>
                    <ol start="3">
                        <li><strong>Don't Hit the Bomb:</strong> If anyone picks the Red Bomb, the round ends immediately, and you lose all points for that round.</li>
                        <li><strong>4 Tries Only:</strong> You have a maximum of 4 turns per round to find all 4 targets.</li>
                    </ol>
                </div>
                <div class="guide-card guide-medals">
                    <h3>Win Medals & Points:</h3>
                    <p>The faster you find the 4 targets, the better your medal:</p>
                    <ul>
                        <li>&#129351; Gold (5 pts): Finish in 1 or 2 turns.</li>
                        <li>&#129352; Silver (4 pts): Finish in 3 turns.</li>
                        <li>&#129353; Bronze (3 pts): Finish in 4 turns.</li>
                    </ul>
                    <p>Pro Tip: Try to think like your AI partner! The better you "connect," the more points you'll earn.</p>
                </div>
                <div class="guide-card guide-research">
                    <h3>Important: Help Our Research! &#128300;</h3>
                    <p>Since this is a research project, please pay attention to these 3 extra steps. They help us understand how humans and AI connect:</p>
                    <ol>
                        <li><strong>Read the Round History:</strong><br>After each round, take a moment to read the summary. It helps you and the AI understand each other’s logic better for the next rounds.</li>
                        <li><strong>Mark Your Targets (Your Intent):</strong><br>When it's your turn to give a hint, we need to know what you’re thinking! After you give your clue and number, please select/mark the exact cards you expect the AI to pick. This shows us your "hidden plan."</li>
                        <li><strong>Rate Your Connection:</strong> Rate the Connection: After each round, rate our "Shared Understanding" from 1 to 5.</li>
                    </ol>
                    <p>(5 = We understood each other perfectly | 1 = We were totally lost).</p>
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
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def screen_human_clue():
    if st.session_state.round_finished:
        screen_round_summary()
        return

    render_top_status()
   

    with st.container(border=True):
        st.markdown('<div class="panel-title">Your secret board</div>', unsafe_allow_html=True)
        render_board(
            st.session_state.board,
            st.session_state.word_roles,
            guesses=st.session_state.guesses,
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
            intended_targets = st.session_state.hint_targets[:]
            with st.spinner("AI is thinking..."):
                ai_guesses = ai_guess(
                    st.session_state.board,
                    st.session_state.hint,
                    st.session_state.hint_number,
                    0,
                    st.session_state.interaction_history,
                    st.session_state.guesses,
                    st.session_state.ai_round_summaries,
                )

            if ai_guesses == ["__REROLL_HINT__"]:
                if st.session_state.ai_rerolls > 0:
                    st.session_state.ai_rerolls -= 1
                    st.warning("The AI asked for another clue.")
                else:
                    st.warning("No AI rerolls remain. Please adjust the clue.")
            else:
                st.session_state.last_ai_guesses = ai_guesses
                record_interaction(
                    st.session_state.hint,
                    st.session_state.hint_number,
                    ai_guesses,
                    intended_targets,
                )
                if not st.session_state.round_finished:
                    st.session_state.previous_hint = st.session_state.hint
                    st.session_state.hint = ""
                    st.session_state.hint_number = 1
                    st.session_state.hint_targets = []
                st.rerun()

    render_interaction_history(st.session_state.interaction_history)


def screen_human_guesser():
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
                    record_interaction(
                        st.session_state.hint,
                        st.session_state.hint_number,
                        st.session_state.pending_guesses,
                        st.session_state.hint_targets,
                    )
                    st.session_state.pending_guesses = []
                    if not st.session_state.round_finished:
                        st.session_state.previous_hint = st.session_state.hint
                        st.session_state.hint = ""
                        st.session_state.hint_number = 1
                        st.session_state.hint_targets = []
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
                hint, hint_number, intended_targets = generate_ai_hint(
                    st.session_state.target_words,
                    st.session_state.bomb_word,
                    st.session_state.neutral_words,
                    st.session_state.word_type,
                    st.session_state.interaction_history,
                    st.session_state.used_hints,
                    st.session_state.ai_round_summaries,
                )
            st.session_state.hint = hint
            st.session_state.hint_number = hint_number
            st.session_state.hint_targets = intended_targets
            st.rerun()
    else:
        render_hint_panel(
            st.session_state.hint,
            st.session_state.hint_number,
            st.session_state.previous_hint,
        )
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
        st.markdown(
            """
                <div class="glass-card compact-card">
                <div class="panel-title">Quick rating</div>
                <p class="subtle-text" style="margin:0;">Rate our Shared Understanding from 1 to 5.</p>
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

        st.session_state.perception_rating = selected_label

        if st.button("Save round and continue", type="primary", use_container_width=True):
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
                st.session_state.hint = ""
                st.session_state.hint_number = 1
                st.session_state.hint_targets = []
                st.session_state.previous_hint = None
                st.session_state.last_ai_guesses = []
                st.session_state.last_ai_hint = ""

            st.rerun()


def screen_game_over():
    player_name = st.session_state.get("participant_id") or "Player"
    total_score = st.session_state.get("score", 0)
    if total_score >= 35:
        title = "Elite team!"
        subtitle = f"Fantastic finish, {player_name}! Your team was sharp, fast, and beautifully in sync."
        tier = "Elite team"
    elif total_score >= 30:
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
            <div class="score-tiers">25+ Strong team &middot; 30+ Excellent team &middot; 35+ Elite team</div>
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
    st.info(f"The run has been saved correctly, {player_name}.")

    st.markdown('<div class="center-actions">', unsafe_allow_html=True)
    if st.button("Play again", type="primary", use_container_width=True):
        restart_game(keep_participant=True)
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
