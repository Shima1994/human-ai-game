import streamlit as st

from core.constants import N_ROUNDS, TOTAL_HINT_CHANCES

ROLE_CLASS = {
    "gold_target": "word-gold",
    "target": "word-target",
    "bomb": "word-bomb",
    "neutral": "word-neutral",
}

ROLE_MARK = {
    "gold_target": "&#10022;",
    "target": "&#8226;",
    "bomb": "&#10005;",
    "neutral": "&#8226;",
}

RATING_OPTIONS = {
    1: "Very low",
    2: "Low",
    3: "Medium",
    4: "Good",
    5: "Strong",
}


def render_app_header():
    st.markdown(
        """
        <div class="hero">
            <div class="hero-title">Human-AI Cooperative Word Game</div>
            <p class="hero-subtitle">Give smart clues, connect as many safe target cards as you can, and avoid the bomb card.</p>
            <div class="hero-badge-row">
                <div class="hero-badge">8 rounds</div>
                <div class="hero-badge">Alternating roles</div>
                <div class="hero-badge">Shared score</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_top_status():
    role_label = "Clue-giver" if st.session_state.role == "human_clue" else "Guesser"
    total_rerolls_left = st.session_state.ai_rerolls + st.session_state.human_rerolls
    player_name = st.session_state.get("participant_id") or "-"

    st.markdown(
        f"""
        <div class="top-status-shell">
            <div class="top-status">
                <div class="status-pill"><div class="status-label">Player</div><div class="status-value">{player_name}</div></div>
                <div class="status-pill"><div class="status-label">Round</div><div class="status-value">{st.session_state.round} / {N_ROUNDS}</div></div>
                <div class="status-pill"><div class="status-label">Score</div><div class="status-value">{st.session_state.score}</div></div>
                <div class="status-pill"><div class="status-label">Role</div><div class="status-value">{role_label}</div></div>
                <div class="status-pill"><div class="status-label">Words</div><div class="status-value">{st.session_state.word_type.capitalize()}</div></div>
                <div class="status-pill"><div class="status-label">Hint chances</div><div class="status-value">{total_rerolls_left} / {TOTAL_HINT_CHANCES}</div></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_round_chip(text):
    st.markdown(
        f"<div class='round-chip'>{text}</div>",
        unsafe_allow_html=True,
    )


def _render_static_card(word, role, revealed):
    css_class = ROLE_CLASS.get(role, "word-neutral") if revealed else "word-hidden"
    mark = ""
    if revealed:
        mark = f"<div class='card-mark'>{ROLE_MARK.get(role, '')}</div>"

    st.markdown(
        f"<div class='word-card {css_class}'><div>{word}</div>{mark}</div>",
        unsafe_allow_html=True,
    )


def render_board(board, word_roles, guesses=None, reveal_all=False, clickable=False, max_clicks=0):
    guesses = guesses or []
    cols = st.columns(3)
    guess_set = set(guesses)
    clicked = False

    for index, word in enumerate(board):
        role = word_roles.get(word, "neutral")
        is_guessed = word in guess_set
        revealed = reveal_all or is_guessed or st.session_state.round_finished

        with cols[index % 3]:
            if clickable and not revealed:
                is_disabled = len(guesses) >= max_clicks or is_guessed
                if st.button(
                    word,
                    key=f"board_button_{st.session_state.round}_{word}",
                    use_container_width=True,
                    disabled=is_disabled,
                ):
                    st.session_state.guesses.append(word)
                    if role == "bomb" or len(st.session_state.guesses) >= max_clicks:
                        st.session_state.round_finished = True
                    clicked = True
            else:
                _render_static_card(word, role, revealed)

    return clicked


def render_board_legend():
    st.markdown(
        """
        <div class="legend">
            <div class="legend-pill legend-target">Green &#8226; +1</div>
            <div class="legend-pill legend-gold">Gold &#10022; +3</div>
            <div class="legend-pill legend-neutral">Gray &#8226; 0</div>
            <div class="legend-pill legend-bomb">Red &#10005; -1</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hint_panel(current_hint, hint_number, previous_hint=None):
    chips = [f"<div class='hint-chip'>{hint_number} words</div>"]
    if previous_hint:
        chips.append(f"<div class='hint-chip'>Previous: {previous_hint.upper()}</div>")
    chips_html = "".join(chips)

    st.markdown(
        f"""
        <div class="hint-card">
            <div class="hint-label">AI clue</div>
            <div class="hint-main">{current_hint.upper()}</div>
            <div class="hint-chip-row">{chips_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
