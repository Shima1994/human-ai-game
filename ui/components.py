from html import escape
import math
import time

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

# The final, session-level medal (see get_final_medal) -- distinct from
# MEDAL_LABELS above, which labels the per-round efficiency medal.
FINAL_MEDAL_LABELS = {
    "gold": "&#129351; Gold",
    "silver": "&#129352; Silver",
    "bronze": "&#129353; Bronze",
    "none": "No medal",
}

ROLE_CLASS = {
    "target": "word-target",
    "bomb": "word-bomb",
    "neutral": "word-neutral",
}

ROLE_MARK = {
    # Non-color cue for each revealed role, so target/neutral/bomb don't
    # depend on hue alone (success-green and danger-red card backgrounds
    # have almost identical lightness, which erases the difference for
    # red-green color vision deficiency). Keyed by role rather than the
    # more granular css_class, so a wrong guess on a neutral card still
    # reads with the neutral glyph (not the bomb glyph) even though both
    # get the same red "miss" background.
    "target": "&#10003;",  # check mark
    "bomb": "&#10007;",  # cross mark
    "neutral": "&#9675;",  # open circle
}

RATING_OPTIONS = {
    1: "Very low",
    2: "Low",
    3: "Medium",
    4: "Good",
    5: "Strong",
}


def scroll_page_to_top(should_scroll):
    """Reset the parent Streamlit viewport after navigating to a new study view.

    Rendered on every rerun (the caller passes should_scroll rather than us
    only being called on transitions), so this component's own DOM node is
    never added on one rerun and removed on the next. Removing a component
    iframe -- even a zero-size one -- shifts the layout by its wrapper's
    spacing and was showing up as a one-time visible "jump" on the first
    widget interaction right after arriving at a new screen.
    """
    st_components.html(
        f"""
        <script>
          if ({str(bool(should_scroll)).lower()}) {{
            const resetScroll = () => {{
              const parentWindow = window.parent;
              const parentDocument = parentWindow.document;
              parentWindow.scrollTo({{ top: 0, left: 0, behavior: "instant" }});
              parentDocument.documentElement.scrollTop = 0;
              parentDocument.body.scrollTop = 0;
              const appViewport = parentDocument.querySelector(
                '[data-testid="stAppViewContainer"]'
              );
              if (appViewport) appViewport.scrollTo({{ top: 0, left: 0, behavior: "instant" }});
              const main = parentDocument.querySelector('[data-testid="stMain"]');
              if (main) main.scrollTo({{ top: 0, left: 0, behavior: "instant" }});
            }};
            requestAnimationFrame(() => requestAnimationFrame(resetScroll));
          }}
        </script>
        """,
        height=0,
        width=0,
    )


def close_maxed_multiselects():
    """Every st.multiselect with max_selections in this app should close its
    dropdown the instant a click brings it up to that cap, instead of
    sitting open showing BaseWeb's own "You can only select up to N
    option(s). Remove an option first." hint. Streamlit has no built-in way
    to do this, so this reaches into the parent document (same cross-frame
    technique as scroll_page_to_top) and blurs the focused input right after
    an option click that leaves that hint showing -- closing it, since
    BaseWeb's popover closes on blur.

    Deliberately keyed off the option *click*, not just "is the hint
    currently visible": a popover reopened by clicking the multiselect box
    itself (e.g. to remove a chip) shows the exact same hint while still at
    the cap, and must NOT be immediately closed again -- only a click that
    just added the capping option should trigger this. Mounted once,
    app-wide, from app.py's main() rather than once per multiselect, since
    it isn't tied to any one widget."""
    st_components.html(
        """
        <script>
          (function () {
            const doc = window.parent.document;
            if (doc.__closeMaxedMultiselectsInstalled) return;
            doc.__closeMaxedMultiselectsInstalled = true;
            doc.addEventListener(
              "click",
              (event) => {
                doc.body.setAttribute("data-debug-option-click-seen", "yes");
                if (!event.target.closest('[role="option"]')) return;
                doc.body.setAttribute("data-debug-option-click-matched", "yes");
                // The selection has to round-trip to the Streamlit server and
                // back (a script rerun) before the "you can only select up
                // to N" hint actually renders -- that can easily take longer
                // than a single short delay, so poll for a couple of seconds
                // instead of checking once.
                let attempts = 0;
                const poll = setInterval(() => {
                  attempts += 1;
                  const popovers = doc.querySelectorAll('[data-baseweb="popover"]');
                  doc.body.setAttribute("data-debug-popover-count", String(popovers.length));
                  doc.body.setAttribute(
                    "data-debug-popover-texts",
                    Array.from(popovers).map((p) => p.textContent.slice(0, 40)).join(" || ")
                  );
                  for (const popover of popovers) {
                    if (
                      popover.getClientRects().length > 0 &&
                      popover.textContent.includes("You can only select up to")
                    ) {
                      doc.body.setAttribute("data-debug-close-attempted", "yes");
                      clearInterval(poll);
                      // Neither .blur() nor an Escape keydown closes a BaseWeb
                      // Select popover -- it tracks its own open/closed React
                      // state via a document-level "click outside" listener,
                      // not native focus or key handling. Simulating that
                      // click (on <body>, away from the popover/input) is
                      // what its own close logic actually listens for.
                      const away = doc.body;
                      const opts = { bubbles: true, cancelable: true, view: doc.defaultView };
                      away.dispatchEvent(new MouseEvent("mousedown", opts));
                      away.dispatchEvent(new MouseEvent("mouseup", opts));
                      away.dispatchEvent(new MouseEvent("click", opts));
                      return;
                    }
                  }
                  if (attempts >= 20) clearInterval(poll);
                }, 100);
              },
              true
            );
          })();
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
    player_name = (
        st.session_state.get("nickname")
        or st.session_state.get("participant_id")
        or "-"
    )
    initials = "".join(part[0] for part in str(player_name).replace("_", " ").split()[:2]).upper() or "P"
    found = len(st.session_state.get("found_targets", []))
    interactions = st.session_state.get("round_interactions", 0)
    skips = st.session_state.get("round_skips", 0)
    stars = st.session_state.get("total_stars_so_far", 0)
    total_score = st.session_state.get("score", 0)

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
                <span class="medal-chip points">{total_score} pts</span>
                <span class="medal-chip star">&#11088; {stars} / {N_ROUNDS}</span>
            </div>
            <span class="role-badge {role_variant}"><span class="role-dot"></span>{escape(role_label)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_tutorial_status(round_label, role_label, role_variant, stats):
    """Same visual status bar as render_top_status, for the two practice
    rounds -- which never call that function since it reads real-game
    session-state fields (st.session_state.round, .found_targets,
    .round_interactions, .medal_counts, ...) the tutorial doesn't populate.
    Left without this, the tutorial's own header was a bare heading with no
    equivalent of the name/progress/role info the real screens always show,
    which read as a different, less-finished-looking screen entirely.

    stats is a list of up to three (label, value, total) tuples rendered as
    the same stat-block/mini-bar pattern; medals are omitted entirely since
    practice rounds never award any."""
    def _bar(value, total):
        pct = 0 if not total else max(0, min(100, round(100 * value / total)))
        return pct

    # Each block built as one continuous string, not a multi-line template --
    # embedding a multi-line, indented template's actual *content* (not just
    # the Python source) into the outer markdown call leaves the same
    # blank-but-indented lines Markdown misreads as an indented code block
    # (see the comment on the outer call below).
    stat_blocks = "".join(
        f'<div class="stat-block">'
        f'<div class="stat-label">{escape(label)}</div>'
        f'<div class="stat-value-row"><span class="big">{value}</span><span class="of">/ {total}</span></div>'
        f'<div class="mini-bar"><span style="width:{_bar(value, total)}%"></span></div>'
        f"</div>"
        for label, value, total in stats
    )
    # Round 2 has no per-turn stats to show (a single clue submission, not a
    # back-and-forth round) -- omit the separator and stats block entirely
    # rather than leave a divider with nothing after it.
    sep_and_stats = (
        f'<div class="status-sep"></div><div class="status-stats">{stat_blocks}</div>'
        if stats
        else ""
    )
    # Single-line, no blank/whitespace-only rows -- when sep_and_stats is ""
    # (round 2, no stats), a multi-line template with it on its own indented
    # line leaves a blank-but-indented row, which Markdown reads as starting
    # an indented code block: the rest of the HTML then renders as literal
    # text instead of being parsed (same trap noted elsewhere in this file).
    st.markdown(
        '<div class="status-bar">'
        '<div class="status-id"><div class="status-avatar">P</div><div>'
        '<div class="status-name">Practice</div>'
        f'<div class="status-round">{escape(round_label)}</div>'
        "</div></div>"
        f"{sep_and_stats}"
        f'<span class="role-badge {role_variant}"><span class="role-dot"></span>{escape(role_label)}</span>'
        "</div>",
        unsafe_allow_html=True,
    )


def render_round_chip(text):
    st.markdown(
        f"<div class='round-chip'>{escape(text)}</div>",
        unsafe_allow_html=True,
    )


def render_clue_timer(remaining_seconds, pinned=True):
    """A ring countdown (conic-gradient arc around a hollow clock face),
    sticky to the top of the viewport instead of scrolling away with the
    page -- so it stays visible during every timed decision, not just while
    the participant happens to be scrolled to the top.

    pinned=False renders the identical ring in normal document flow next
    to wherever it's called from (no position:fixed) instead -- used to
    sit the timer directly beside the board heading rather than floating
    far above it. Callers that use this must accept the tradeoff that the
    timer can then scroll out of view on a long form below the board;
    pinned=True (the default, used by the tutorial and any other caller)
    keeps the original always-on-screen behavior unchanged.

    The ring itself (arc angle, color, border) is a plain st.markdown element,
    not a custom HTML/JS component -- those render inside a sandboxed iframe
    document and so could never pick up the app's own fonts/colors, which is
    why an earlier iframe-based version of this always looked like plain
    unstyled browser text. Only the countdown digits are ticked by a tiny,
    invisible (height=0) iframe that reaches into the *parent* document once
    a second and rewrites the .timer-clock span's text -- the same
    cross-frame-write technique scroll_page_to_top() already uses elsewhere
    in this file. That component decides nothing; it is purely cosmetic. The
    real timeout/skip/loss logic still only runs from the server-side check
    on the autorefresh below (every few seconds), same as before, so a
    participant's clock being off can't desync the actual game state.

    The phase label (giving a clue vs. guessing) and the forced-final-guess
    state are both read from st.session_state rather than taken as
    parameters, so every call site automatically stays in sync with no
    signature to keep updated -- this is the one timer implementation used
    everywhere a participant has a timed decision to make.
    """
    remaining = max(0, int(math.ceil(remaining_seconds or 0)))
    is_final_guess = bool(st.session_state.get("final_guess_deadline_active"))
    clock = f"{remaining // 60:02d}:{remaining % 60:02d}"
    # Absolute deadline (ms since epoch, matches JS Date.now()) so the tiny
    # ticking script below can compute "seconds left" independently on every
    # tick rather than needing a fresh value from the server each time.
    deadline_ms = int((time.time() + max(0.0, remaining_seconds or 0)) * 1000)
    # The clue-giver/guesser role label used to prefix every state ("Guessing
    # -- 01:13 left"), but the role is already obvious from the screen the
    # participant is on, so it just made the pill wider without adding
    # information -- dropped everywhere except the urgency states below,
    # each a real state change worth calling out (and, for "warn", not
    # something the color/pulse change alone should have to carry).
    if is_final_guess:
        state_class = " final"
        caption = "Final chance"
    elif remaining <= 0:
        state_class = " expired"
        caption = "Time&rsquo;s up"
    elif remaining <= 15:
        state_class = " warn"
        caption = "Hurry"
    else:
        state_class = ""
        caption = ""
    clock_html = (
        "&ndash;&ndash;:&ndash;&ndash;"
        if remaining <= 0
        else f'<span class="timer-clock" data-deadline-ms="{deadline_ms}">{clock}</span>'
    )
    # The ring's filled arc, computed server-side from remaining/total so it
    # already shows the right angle on first paint -- it only advances again
    # on the next autorefresh (same cadence the pill's color states always
    # updated at), not smoothly every second like the clock digits (those
    # still tick client-side every second via the cross-frame script below).
    total = st.session_state.get("clue_timer_duration_seconds") or remaining or 1
    # The filled arc represents time REMAINING (starts as a full circle,
    # empties out as the deadline approaches) -- the more familiar
    # countdown-ring convention, not "elapsed so far."
    progress_deg = max(0, min(360, round(360 * (remaining / total))))
    caption_html = (
        f'<div class="timer-caption">{caption}</div>' if caption else ""
    )
    row_class = "timer-row" if pinned else "timer-row-inline"
    # Single-line, no blank/whitespace-only rows -- when caption_html is ""
    # (the common case), a multi-line template with it on its own indented
    # line leaves a blank-but-indented row, which Markdown reads as starting
    # an indented code block: the rest of the HTML then renders as literal
    # text instead of being parsed (same trap noted elsewhere in this file).
    st.markdown(
        f'<div class="{row_class}">{caption_html}'
        f'<span class="timer-pill{state_class}" style="--ring-progress: {progress_deg}deg;" aria-live="polite">'
        f'<span class="timer-ring-label">{clock_html}</span></span></div>',
        unsafe_allow_html=True,
    )
    # The pill's text is otherwise only as fresh as the last rerun (every
    # few seconds, see the autorefresh below) -- which read as choppy
    # ("every 5-6 seconds" per feedback) rather than an actually running
    # clock. This tiny invisible iframe does nothing but tick the .timer-clock
    # text in the *parent* document once a second between reruns, the same
    # cross-frame-write technique scroll_page_to_top() already uses elsewhere
    # in this file. It never decides anything -- the real timeout/skip/loss
    # logic still only runs from the server-side check on the autorefresh
    # below, unchanged, so this can't desync the actual game state even if
    # the participant's clock is off.
    st_components.html(
        """
        <script>
          function tickClueTimer() {
            const parentDoc = window.parent.document;
            parentDoc.querySelectorAll(".timer-clock").forEach((el) => {
              const deadline = parseInt(el.dataset.deadlineMs, 10);
              if (!deadline) return;
              const remaining = Math.max(0, Math.round((deadline - Date.now()) / 1000));
              const mm = String(Math.floor(remaining / 60)).padStart(2, "0");
              const ss = String(remaining % 60).padStart(2, "0");
              el.textContent = mm + ":" + ss;
            });
          }
          tickClueTimer();
          setInterval(tickClueTimer, 1000);
        </script>
        """,
        height=0,
        width=0,
    )
    # Trigger a normal Streamlit rerun (preserves st.session_state) every few
    # seconds so the server-side timeout check in screens.py gets a chance to
    # fire once the deadline passes. A full browser reload was used here
    # previously, which wiped the participant's entire session on every
    # timeout instead of just consuming the current turn.
    #
    # This must keep firing even once remaining hits 0 (previously gated on
    # remaining > 0): the *next* rerun is what actually calls
    # _consume_human_clue_timeout()/_consume_human_guess_timeout() and clears
    # the expired turn. Stopping autorefresh exactly at 0 meant the app never
    # rendered again on its own once time ran out -- the participant's next
    # click was the one that silently triggered the timeout instead of
    # submitting what they clicked, which looked exactly like "the button
    # doesn't work." Once the timeout is actually consumed, the screen moves
    # on to a fresh timer (or away from this one), so this keeps working
    # correctly rather than looping.
    #
    # Interval is a tradeoff: Streamlit aborts an in-flight script run (and
    # discards that run's not-yet-applied widget state) whenever a new rerun
    # is triggered before it finishes, including one from this autorefresh --
    # so a shorter interval means more chances for a real click's rerun to
    # get interrupted and silently dropped, which is exactly what showed up
    # as "the board card I clicked didn't register" and "the screen randomly
    # refreshes itself," and (further downstream) the AI-guess response
    # itself getting silently discarded if a real OpenAI call -- often
    # 3-10+ seconds -- is still in flight when a tick lands. 10s keeps
    # timeout detection close enough (a 90-120s decision timer noticing a
    # few seconds late is harmless) while meaningfully cutting how often
    # this collides with either a participant click or a slow AI response.
    st_autorefresh(interval=10000, key="clue_timer_autorefresh")


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
    guess_set = set(guesses)
    clicked_word = None

    # Keyed so app.css can style these buttons like the static .word-card
    # cards (light background, dark text) instead of the app's default
    # solid-blue CTA button -- without this, the instant the board becomes
    # clickable (e.g. once the guess-reasoning field turns valid), every
    # still-hidden card flips all at once from the calm .word-hidden
    # palette to a wall of vivid blue buttons, which reads as a jarring,
    # unexplained color change rather than "these are now clickable."
    with st.container(key="board_card_grid"):
        cols = st.columns(column_count)
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


def render_board_lock_note(message, visible=True):
    """Always render this note (rather than only when locked) and hide it
    with CSS when not needed, so its DOM node is never added/removed across
    reruns -- removing it (e.g. the instant reasoning becomes valid) shifted
    the board and everything below it up by the note's height, which showed
    up as a one-time visible "jump" right when the lock note should have
    just quietly gone away. Same fix pattern as scroll_page_to_top."""
    hidden_class = "" if visible else " board-lock-note-hidden"
    st.markdown(
        f"""
        <div class="board-lock-note{hidden_class}">
            <span class="lock-icon">&#128274;</span>
            <span>{escape(message)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hint_panel(current_hint, hint_number, previous_hint=None):
    st.markdown(
        f"""
        <div class="hint-card">
            <div class="hint-copy">
                <div class="hint-label">AI clue</div>
                <div class="hint-main">
                    <span class="hint-word">{escape(current_hint.upper())}</span>
                    <span class="hint-chip">{hint_number} guesses</span>
                </div>
            </div>
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
    # Wrapped in a keyed container so these render as small pill chips
    # (styled below via the "..._chips" class) instead of inheriting the
    # board's full-size hidden-card button style, which made this look like
    # a confusing second board.
    with st.container(key=f"{key_prefix}_chips"):
        cols = st.columns(column_count or (5 if len(target_words) >= 5 else 4))
        for index, word in enumerate(target_words):
            is_selected = word in selected_targets
            label = f"✓ {word}" if is_selected else word
            with cols[index % len(cols)]:
                if st.button(
                    label,
                    key=(
                        f"{key_prefix}_{st.session_state.get('round', 0)}_"
                        f"{len(st.session_state.get('interaction_history', []))}_{word}"
                    ),
                    use_container_width=True,
                    type="primary" if is_selected else "secondary",
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


def render_interaction_history(
    history, show_ai_intended=False, share_explanations=True, show_title=True
):
    title_html = '<div class="panel-title">History</div>' if show_title else ""
    if not history:
        # A blank (whitespace-only) line inside this block -- e.g. from an
        # empty title_html landing on its own line -- gets read as a
        # markdown indented code block, so the HTML after it renders as
        # literal text instead of a page element. Keep every line non-empty.
        st.markdown(
            "<div class='history-panel'>"
            f"{title_html}"
            "<div class='history-empty'>No hints or guesses yet.</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    rows = []
    # Most recent turn first -- keep each item's original position as its
    # number so turn numbering stays stable while newest reads on top.
    for index, item in reversed(list(enumerate(history, start=1))):
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
            f"<div class='history-row {outcome_class}'>"
            "<div class='history-row-head'>"
            f"<span class='history-index'>Turn {index}</span>"
            f"<span class='history-outcome-badge {outcome_class}'>{outcome}</span>"
            "</div>"
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
        )

    st.markdown(
        "<div class='history-panel'>"
        f"{title_html}"
        f"{''.join(rows)}"
        "</div>",
        unsafe_allow_html=True,
    )
