from html import escape
import math

import streamlit as st
import streamlit.components.v1 as st_components

from core.constants import (
    BOARD_SIZE,
    BOMB_COUNT,
    MAX_INTERACTIONS_PER_ROUND,
    MAX_SKIPS_PER_ROUND,
    N_ROUNDS,
    TARGET_COUNT,
)

MEDAL_LABELS = {
    "gold": "&#129351; Gold",
    "silver": "&#129352; Silver",
    "none": "None",
}

ROLE_CLASS = {
    "target": "word-target",
    "bomb": "word-bomb",
    "neutral": "word-neutral",
}

ROLE_MARK = {
    "target": "",
    "bomb": "",
    "neutral": "",
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
            <p class="hero-subtitle">Give smart clues, connect as many safe target cards as you can, and avoid the bomb cards.</p>
            <div class="hero-badge-row">
                <div class="hero-badge">4 rounds</div>
                <div class="hero-badge">Alternating turns</div>
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
    skips = st.session_state.get("round_skips", 0)
    medals = st.session_state.get("medal_counts", {})

    st.markdown(
        f"""
        <div class="top-status-shell">
            <div class="top-status">
                <div class="status-pill"><div class="status-label">Player</div><div class="status-value">{escape(str(player_name))}</div></div>
                <div class="status-pill"><div class="status-label">Round</div><div class="status-value">{st.session_state.round} / {N_ROUNDS}</div></div>
                <div class="status-pill medal-pill"><div class="status-label">Medals</div><div class="status-value medal-row"><span class="medal gold">&#129351; {medals.get("gold", 0)}</span><span class="medal silver">&#129352; {medals.get("silver", 0)}</span></div></div>
                <div class="status-pill"><div class="status-label">Target words</div><div class="status-value">{found} / {TARGET_COUNT}</div></div>
                <div class="status-pill"><div class="status-label">Turns</div><div class="status-value">{interactions} / {MAX_INTERACTIONS_PER_ROUND}</div></div>
                <div class="status-pill"><div class="status-label">Next clue</div><div class="status-value">{skips} / {MAX_SKIPS_PER_ROUND}</div></div>
                <div class="status-pill"><div class="status-label">Human role</div><div class="status-value">{role_label}</div></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_round_chip(text):
    st.markdown(
        f"<div class='round-chip'>{escape(text)}</div>",
        unsafe_allow_html=True,
    )


def render_clue_timer(remaining_seconds):
    remaining = max(0, int(math.ceil(remaining_seconds or 0)))
    st_components.html(
        f"""
        <div style="font-family:system-ui;text-align:center;font-weight:700;font-size:1.05rem;"
             aria-live="polite">
          Decision time remaining: <span id="clue-timer">{remaining // 60:02d}:{remaining % 60:02d}</span>
        </div>
        <script>
          let remaining = {remaining};
          let reloaded = false;
          const el = document.getElementById('clue-timer');
          const tick = () => {{
            remaining = Math.max(0, remaining - 1);
            const minutes = String(Math.floor(remaining / 60)).padStart(2, '0');
            const seconds = String(remaining % 60).padStart(2, '0');
            el.textContent = `${{minutes}}:${{seconds}}`;
            el.style.color = remaining <= 15 ? '#b42318' : 'inherit';
            if (remaining === 0 && !reloaded) {{
              reloaded = true;
              window.parent.location.reload();
            }}
          }};
          if (remaining > 0) window.setInterval(tick, 1000);
        </script>
        """,
        height=42,
    )


def _render_static_card(word, role, revealed, guessed=False):
    css_class = ROLE_CLASS.get(role, "word-neutral") if revealed else "word-hidden"
    if guessed and role == "target":
        css_class = "word-found"
    elif guessed and role == "neutral":
        css_class = "word-neutral-miss"
    selected_class = " word-selected" if guessed else ""
    mark = ""
    if revealed and ROLE_MARK.get(role):
        mark = f"<div class='card-mark'>{ROLE_MARK.get(role, '')}</div>"

    st.markdown(
        f"<div class='word-card {css_class}{selected_class}'><div>{escape(str(word))}</div>{mark}</div>",
        unsafe_allow_html=True,
    )


def render_board(board, word_roles, guesses=None, reveal_all=False, clickable=False, max_clicks=0):
    guesses = guesses or []
    column_count = 4 if len(board) == BOARD_SIZE else min(4, max(1, len(board)))
    cols = st.columns(column_count)
    guess_set = set(guesses)
    clicked_word = None

    for index, word in enumerate(board):
        role = word_roles.get(word, "neutral")
        is_guessed = word in guess_set
        revealed = reveal_all or is_guessed or st.session_state.round_finished

        with cols[index % column_count]:
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
        f"""
        <div class="legend">
            <div class="legend-pill legend-target">Green target</div>
            <div class="legend-pill legend-neutral">Gray neutral</div>
            <div class="legend-pill legend-neutral-miss">Blue wrong neutral</div>
            <div class="legend-pill legend-bomb">Red bombs ({BOMB_COUNT})</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hint_panel(current_hint, hint_number, previous_hint=None):
    chips_html = f"<div class='hint-chip'>{hint_number} guesses</div>"
    chips_section = f"<div class=\"hint-chip-row\">{chips_html}</div>"

    st.markdown(
        f"""
        <div class="hint-card">
            <div class="hint-copy">
                <div class="hint-label">AI clue</div>
                <div class="hint-main">{escape(current_hint.upper())}</div>
            </div>
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
    cols = st.columns(5 if len(target_words) >= 5 else 4)
    for index, word in enumerate(target_words):
        is_selected = word in selected_targets
        label = f"[x] {word}" if is_selected else word
        with cols[index % len(cols)]:
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


def render_interaction_history(history, show_ai_intended=False, share_explanations=True):
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
        guesses = item.get("guesses", [])
        skip_interpreted_cards = item.get("skip_interpreted_cards", [])
        wrong_guess_replacements = item.get("wrong_guess_replacements", [])
        correct_guesses = item.get("correct_guesses", [])
        intended_targets = item.get("intended_targets", [])
        expected_guesses = item.get("expected_guesses", [])
        guess_rationale = item.get("guess_rationale", "")
        hint = escape(item.get("hint", "").upper())
        clue_giver = escape((item.get("clue_giver") or "-").title())
        guesser = escape((item.get("guesser") or "-").title())
        is_skip = item.get("outcome") == "skip" or item.get("skipped")
        is_partial_skip = bool(
            item.get("partial_skip") or item.get("outcome") == "partial_skip"
        )
        is_full_skip = bool(is_skip and not is_partial_skip)
        if item.get("bomb_hit"):
            outcome = "Bomb"
            outcome_class = "history-outcome-bomb"
        elif item.get("timed_out") or item.get("outcome") == "timeout":
            outcome = "Timed out"
            outcome_class = "history-outcome-wrong"
        elif is_skip:
            outcome = "Skipped"
            outcome_class = "history-outcome-skip"
        elif item.get("correct"):
            outcome = "Correct"
            outcome_class = "history-outcome-correct"
        else:
            outcome = "Wrong"
            outcome_class = "history-outcome-wrong"

        def chip_row(label, values, empty="none", class_for_value=None):
            chip_items = []
            for value in values:
                css_class = "history-chip"
                if class_for_value:
                    css_class = f"{css_class} {class_for_value(value)}".strip()
                chip_items.append(f"<span class='{css_class}'>{escape(value)}</span>")
            chips = "".join(chip_items)
            if not chips:
                chips = f"<span class='history-chip muted'>{empty}</span>"
            return (
                "<div class='history-detail'>"
                f"<span class='history-detail-label'>{label}</span>"
                f"<span class='history-chip-row'>{chips}</span>"
                "</div>"
            )

        intended_label = "AI intended" if item.get("clue_giver") == "ai" else "Human intended"
        intended_row = chip_row(intended_label, intended_targets)
        expected_label = (
            "AI expected human" if item.get("clue_giver") == "ai" else "Human expected AI"
        )
        expected_row = chip_row(expected_label, expected_guesses)
        correct_set = set(correct_guesses)
        neutral_set = set(item.get("neutral_guesses", []))
        bomb_guesses = set(item.get("bomb_guesses", []))
        if not bomb_guesses and item.get("bomb_guess"):
            bomb_guesses = set(str(item.get("bomb_guess")).split(";"))

        def guess_class(value):
            if value in bomb_guesses:
                return "bomb"
            if value in correct_set:
                return "correct"
            if value in neutral_set:
                return "neutral"
            return ""

        guesses_row = (
            ""
            if is_full_skip
            else chip_row("Guesses", guesses, class_for_value=guess_class)
        )
        skip_interpretation_row = (
            chip_row("Guesser thought", skip_interpreted_cards)
            if share_explanations and is_skip and skip_interpreted_cards
            else ""
        )
        replacement_row = (
            chip_row("Would choose instead", wrong_guess_replacements)
            if share_explanations
            and not item.get("bomb_hit")
            and wrong_guess_replacements
            else ""
        )
        rationale_row = ""
        if share_explanations and guess_rationale:
            rationale_row = (
                "<div class='history-detail'>"
                "<span class='history-detail-label'>Why</span>"
                f"<span class='history-chip-row'><span class='history-chip muted'>{escape(guess_rationale)}</span></span>"
                "</div>"
            )
        skip_note = ""
        if is_skip:
            skipped_by = escape((item.get("skipped_by") or guesser).title())
            if is_partial_skip:
                remaining = item.get("skipped_guesses", max(0, int(item.get("hint_number", 0) or 0) - len(guesses)))
                skip_note = (
                    f"<div class='history-skip-note'>{skipped_by} kept the completed guesses and skipped "
                    f"{remaining} remaining guess(es). One full skip was used.</div>"
                )
            else:
                skip_note = (
                    f"<div class='history-skip-note'>{skipped_by} selected no cards, "
                    "asked for the next clue, and used one full skip.</div>"
                )

        rows.append(
            "<div class='history-row'>"
            f"<div class='history-index'>{index}</div>"
            "<div class='history-body'>"
            "<div class='history-meta'>"
            f"<span>{clue_giver} clue</span>"
            f"<span>{guesser} guesser</span>"
            "</div>"
            "<div class='history-hint-line'>"
            f"<span class='history-hint'>{hint}</span>"
            f"<span class='history-number'>x{item.get('hint_number', '')}</span>"
            "</div>"
            f"{intended_row if share_explanations and (show_ai_intended or item.get('clue_giver') == 'human') else ''}"
            f"{expected_row if share_explanations and expected_guesses and (show_ai_intended or item.get('clue_giver') == 'human') else ''}"
            f"{guesses_row}"
            f"{skip_interpretation_row}"
            f"{replacement_row}"
            f"{rationale_row}"
            f"{skip_note}"
            "</div>"
            f"<div class='history-outcome {outcome_class}'>{outcome}</div>"
            "</div>"
        )

    st.markdown(
        "<div class='history-panel'>"
        "<div class='panel-title'>History</div>"
        f"{''.join(rows)}"
        "</div>",
        unsafe_allow_html=True,
    )
