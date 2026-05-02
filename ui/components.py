from html import escape

import streamlit as st

from core.constants import (
    MAX_INTERACTIONS_PER_ROUND,
    N_ROUNDS,
    TARGET_COUNT,
)

MEDAL_LABELS = {
    "gold": "&#129351; Gold",
    "silver": "&#129352; Silver",
    "bronze": "&#129353; Bronze",
    "none": "None",
}

ROLE_CLASS = {
    "target": "word-target",
    "bomb": "word-bomb",
    "neutral": "word-neutral",
}

ROLE_MARK = {
    "target": "&#8226;",
    "bomb": "&#10005;",
    "neutral": "&#9670;",
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
                <div class="hero-badge">Medals</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_top_status():
    role_label = "Clue-giver" if st.session_state.role == "human_clue" else "Guesser"
    player_name = st.session_state.get("participant_id") or "-"
    found = len(st.session_state.get("found_targets", []))
    interactions = st.session_state.get("round_interactions", 0)
    medals = st.session_state.get("medal_counts", {})

    st.markdown(
        f"""
        <div class="top-status-shell">
            <div class="top-status">
                <div class="status-pill"><div class="status-label">Player</div><div class="status-value">{player_name}</div></div>
                <div class="status-pill"><div class="status-label">Round</div><div class="status-value">{st.session_state.round} / {N_ROUNDS}</div></div>
                <div class="status-pill medal-pill"><div class="status-label">Medals</div><div class="status-value medal-row"><span class="medal gold">&#129351; {medals.get("gold", 0)}</span><span class="medal silver">&#129352; {medals.get("silver", 0)}</span><span class="medal bronze">&#129353; {medals.get("bronze", 0)}</span></div></div>
                <div class="status-pill"><div class="status-label">Targets</div><div class="status-value">{found} / {TARGET_COUNT}</div></div>
                <div class="status-pill"><div class="status-label">Turns</div><div class="status-value">{interactions} / {MAX_INTERACTIONS_PER_ROUND}</div></div>
                <div class="status-pill"><div class="status-label">Role</div><div class="status-value">{role_label}</div></div>
                <div class="status-pill"><div class="status-label">Words</div><div class="status-value">{st.session_state.word_type.capitalize()}</div></div>
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


def _render_static_card(word, role, revealed, guessed=False):
    css_class = ROLE_CLASS.get(role, "word-neutral") if revealed else "word-hidden"
    if guessed and role == "target":
        css_class = "word-ai-found" if st.session_state.role == "human_clue" else "word-found"
    elif guessed and role == "neutral":
        css_class = "word-neutral-miss"
    selected_class = " word-selected" if guessed else ""
    mark = ""
    if revealed:
        mark = f"<div class='card-mark'>{ROLE_MARK.get(role, '')}</div>"

    st.markdown(
        f"<div class='word-card {css_class}{selected_class}'><div>{word}</div>{mark}</div>",
        unsafe_allow_html=True,
    )


def render_board(board, word_roles, guesses=None, reveal_all=False, clickable=False, max_clicks=0):
    guesses = guesses or []
    cols = st.columns(4)
    guess_set = set(guesses)
    clicked_word = None

    for index, word in enumerate(board):
        role = word_roles.get(word, "neutral")
        is_guessed = word in guess_set
        revealed = reveal_all or is_guessed or st.session_state.round_finished

        with cols[index % 4]:
            if clickable and not revealed:
                is_disabled = len(guesses) >= max_clicks or is_guessed
                if st.button(
                    word,
                    key=f"board_button_{st.session_state.round}_{word}",
                    use_container_width=True,
                    disabled=is_disabled,
                ):
                    clicked_word = word
            else:
                _render_static_card(word, role, revealed, guessed=is_guessed)

    return clicked_word


def render_board_legend():
    st.markdown(
        """
        <div class="legend">
            <div class="legend-pill legend-target">Green &#8226; target</div>
            <div class="legend-pill legend-gold">Gold &#8226; target found by AI</div>
            <div class="legend-pill legend-neutral">Gray &#9670; neutral</div>
            <div class="legend-pill legend-neutral-miss">Blue &#9670; wrong neutral</div>
            <div class="legend-pill legend-bomb">Red &#10005; bomb</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hint_panel(current_hint, hint_number, previous_hint=None):
    chips = [f"<div class='hint-chip'>{hint_number} guesses</div>"]
    if previous_hint:
        chips.append(f"<div class='hint-chip'>Previous: {previous_hint.upper()}</div>")
    chips_html = "".join(chips)
    chips_section = f"<div class=\"hint-chip-row\">{chips_html}</div>" if chips_html else ""

    st.markdown(
        f"""
        <div class="hint-card">
            <div class="hint-label">AI clue</div>
            <div class="hint-main">{current_hint.upper()}</div>
            {chips_section}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hint_target_selector(target_words, selected_targets, max_targets):
    selected_targets = selected_targets or []
    st.markdown(
        """
        <div class="panel-title section-gap">Select the target cards this clue is meant for</div>
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns(4)
    for index, word in enumerate(target_words):
        is_selected = word in selected_targets
        label = f"[x] {word}" if is_selected else word
        with cols[index % 4]:
            if st.button(
                label,
                key=f"hint_target_{st.session_state.round}_{st.session_state.round_interactions}_{word}",
                use_container_width=True,
                disabled=(not is_selected and len(selected_targets) >= max_targets),
            ):
                if is_selected:
                    st.session_state.hint_targets = [
                        item for item in selected_targets if item != word
                    ]
                else:
                    st.session_state.hint_targets = selected_targets + [word]
                st.rerun()


def render_interaction_history(history, show_ai_intended=False):
    if not history:
        st.markdown(
            """
            <div class="history-panel">
                <div class="panel-title">History</div>
                <div class="history-empty">No hints or guesses yet.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    rows = []
    for index, item in enumerate(history, start=1):
        guesses = escape(", ".join(item.get("guesses", [])) or "none")
        correct = escape(", ".join(item.get("correct_guesses", [])) or "none")
        intended = escape(", ".join(item.get("intended_targets", [])) or "none")
        hint = escape(item.get("hint", "").upper())
        if item.get("bomb_hit"):
            outcome = "Bomb"
        elif item.get("correct"):
            outcome = "Correct"
        else:
            outcome = "Wrong"
        intended_row = (
            f"<div><strong>AI intended:</strong> {intended}</div>"
            if show_ai_intended and item.get("clue_giver") == "ai"
            else ""
        )
        rows.append(
            "<div class='history-row'>"
            f"<div class='history-index'>{index}</div>"
            "<div>"
            f"<div><strong>Hint:</strong> {hint} <span class='history-number'>x{item.get('hint_number', '')}</span></div>"
            f"{intended_row}"
            f"<div><strong>Guesses:</strong> {guesses}</div>"
            f"<div><strong>Correct:</strong> {correct}</div>"
            "</div>"
            f"<div class='history-outcome'>{outcome}</div>"
            "</div>"
        )

    st.markdown(
        "<div class='history-panel'>"
        "<div class='panel-title'>History</div>"
        f"{''.join(rows)}"
        "</div>",
        unsafe_allow_html=True,
    )
