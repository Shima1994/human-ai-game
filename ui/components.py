from html import escape
import math

import streamlit as st
import streamlit.components.v1 as st_components
from streamlit_autorefresh import st_autorefresh

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


def scroll_page_to_top():
    """Reset the parent Streamlit viewport after navigating to a new study view."""
    st_components.html(
        """
        <script>
          const resetScroll = () => {
            const parentWindow = window.parent;
            const parentDocument = parentWindow.document;
            parentWindow.scrollTo({ top: 0, left: 0, behavior: "instant" });
            parentDocument.documentElement.scrollTop = 0;
            parentDocument.body.scrollTop = 0;
            const appViewport = parentDocument.querySelector(
              '[data-testid="stAppViewContainer"]'
            );
            if (appViewport) appViewport.scrollTo({ top: 0, left: 0, behavior: "instant" });
            const main = parentDocument.querySelector('[data-testid="stMain"]');
            if (main) main.scrollTo({ top: 0, left: 0, behavior: "instant" });
          };
          requestAnimationFrame(() => requestAnimationFrame(resetScroll));
        </script>
        """,
        height=0,
        width=0,
    )


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
    is_clue_giver = st.session_state.role == "human_clue"
    role_label = "You're giving the clue" if is_clue_giver else "AI clues — you guess"
    role_variant = "human" if is_clue_giver else "ai"
    player_name = st.session_state.get("participant_id") or "-"
    initials = "".join(part[0] for part in str(player_name).replace("_", " ").split()[:2]).upper() or "P"
    found = len(st.session_state.get("found_targets", []))
    interactions = st.session_state.get("round_interactions", 0)
    skips = st.session_state.get("round_skips", 0)
    medals = st.session_state.get("medal_counts", {})

    def _bar(value, total):
        pct = 0 if not total else max(0, min(100, round(100 * value / total)))
        return pct

    st.markdown(
        f"""
        <div class="status-bar">
            <div class="status-id">
                <div class="status-avatar">{escape(initials)}</div>
                <div>
                    <div class="status-name">{escape(str(player_name))}</div>
                    <div class="status-round">Round {st.session_state.round} of {N_ROUNDS}</div>
                </div>
            </div>
            <div class="status-sep"></div>
            <div class="status-stats">
                <div class="stat-block">
                    <div class="stat-label">Targets found</div>
                    <div class="stat-value-row"><span class="big">{found}</span><span class="of">/ {TARGET_COUNT}</span></div>
                    <div class="mini-bar"><span style="width:{_bar(found, TARGET_COUNT)}%"></span></div>
                </div>
                <div class="stat-block">
                    <div class="stat-label">Turns used</div>
                    <div class="stat-value-row"><span class="big">{interactions}</span><span class="of">/ {MAX_INTERACTIONS_PER_ROUND}</span></div>
                    <div class="mini-bar"><span style="width:{_bar(interactions, MAX_INTERACTIONS_PER_ROUND)}%"></span></div>
                </div>
                <div class="stat-block">
                    <div class="stat-label">Skips left</div>
                    <div class="stat-value-row"><span class="big">{MAX_SKIPS_PER_ROUND - skips}</span><span class="of">/ {MAX_SKIPS_PER_ROUND}</span></div>
                    <div class="mini-bar warn"><span style="width:{_bar(MAX_SKIPS_PER_ROUND - skips, MAX_SKIPS_PER_ROUND)}%"></span></div>
                </div>
            </div>
            <div class="medal-cluster">
                <span class="medal-chip gold">&#129351; {medals.get("gold", 0)}</span>
                <span class="medal-chip silver">&#129352; {medals.get("silver", 0)}</span>
            </div>
            <span class="role-badge {role_variant}"><span class="role-dot"></span>{escape(role_label)}</span>
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
          const el = document.getElementById('clue-timer');
          const tick = () => {{
            remaining = Math.max(0, remaining - 1);
            const minutes = String(Math.floor(remaining / 60)).padStart(2, '0');
            const seconds = String(remaining % 60).padStart(2, '0');
            el.textContent = `${{minutes}}:${{seconds}}`;
            el.style.color = remaining <= 15 ? '#b42318' : 'inherit';
          }};
          if (remaining > 0) window.setInterval(tick, 1000);
        </script>
        """,
        height=42,
    )
    # Trigger a normal Streamlit rerun (preserves st.session_state) every few
    # seconds so the server-side timeout check in screens.py gets a chance to
    # fire once the deadline passes. A full browser reload was used here
    # previously, which wiped the participant's entire session on every
    # timeout instead of just consuming the current turn.
    if remaining > 0:
        st_autorefresh(interval=3000, key="clue_timer_autorefresh")


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


def render_board(
    board,
    word_roles,
    guesses=None,
    reveal_all=False,
    clickable=False,
    max_clicks=0,
    column_count=None,
    key_prefix="board_button",
):
    guesses = guesses or []
    column_count = column_count or (
        4 if len(board) == BOARD_SIZE else min(4, max(1, len(board)))
    )
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
                    key=f"{key_prefix}_{st.session_state.round}_{word}",
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


def render_rating_scale_endpoints():
    """Anchor labels under a RATING_OPTIONS radio (1-5). The radio itself only
    ever shows bare numbers, so without this the scale has no visible meaning."""
    st.markdown(
        f"""
        <div class="scale-endpoints">
            <span>{RATING_OPTIONS[1]}</span>
            <span>{RATING_OPTIONS[5]}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_board_lock_note(message):
    st.markdown(
        f"""
        <div class="board-lock-note">
            <span class="lock-icon">&#128274;</span>
            <span>{escape(message)}</span>
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


def render_hint_target_selector(
    target_words,
    selected_targets,
    max_targets,
    *,
    state_key="hint_targets",
    key_prefix="hint_target",
    column_count=None,
    disabled=False,
    selectable_words=None,
):
    selected_targets = selected_targets or []
    selectable_set = set(target_words if selectable_words is None else selectable_words)
    st.markdown(
        """
        <div class="panel-title section-gap">Select the target cards this clue is meant for</div>
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns(column_count or (5 if len(target_words) >= 5 else 4))
    for index, word in enumerate(target_words):
        is_selected = word in selected_targets
        label = f"[x] {word}" if is_selected else word
        with cols[index % len(cols)]:
            if st.button(
                label,
                key=(
                    f"{key_prefix}_{st.session_state.get('round', 0)}_"
                    f"{len(st.session_state.get('interaction_history', []))}_{word}"
                ),
                use_container_width=True,
                disabled=(
                    disabled
                    or word not in selectable_set
                    or (not is_selected and len(selected_targets) >= max_targets)
                ),
            ):
                if is_selected:
                    st.session_state[state_key] = [
                        item for item in selected_targets if item != word
                    ]
                else:
                    st.session_state[state_key] = selected_targets + [word]
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
