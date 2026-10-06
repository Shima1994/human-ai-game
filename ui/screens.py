from datetime import datetime, timezone
from html import escape
from pathlib import Path
import re

import streamlit as st

from core.ai_service import (
    AIClueGenerationError,
    ai_guess,
    generate_ai_post_game_reflection,
    generate_ai_round_reflection,
    generate_ai_hint,
    generate_ai_turn_explanation,
    generate_ai_wrong_guess_replacements,
    previous_hints,
    remaining_target_count,
    validate_human_hint_with_history,
)
from core.constants import (
    AI_API_TIMEOUT_SECONDS,
    CLUE_GIVER_FREE_TIMEOUTS_PER_ROUND,
    MAX_INTERACTIONS_PER_ROUND,
    MAX_POSSIBLE_SESSION_SCORE,
    MAX_SKIPS_PER_ROUND,
    N_ROUNDS,
    CLUE_TIMER_SECONDS,
    CLUE_GIVER_TIMER_SECONDS,
    GUESSER_TIMER_SECONDS,
    FINAL_GUESS_TIMER_SECONDS,
    DEFAULT_CONDITION,
)
from core.game_logic import (
    can_skip_current_clue,
    clear_participant_decision_timer,
    compute_round_score,
    get_final_medal,
    participant_decision_timer_expired,
    participant_decision_time_remaining,
    record_forced_timeout_loss,
    record_interaction,
    record_skip,
    record_timeout,
    start_participant_decision_timer,
    update_current_round_summary,
)
from core.storage import (
    initialize_session_log,
    log_event,
    log_round,
    mark_session_progress,
)
from core.tutorial import (
    TUTORIAL_BOARD,
    TUTORIAL_BOMB,
    TUTORIAL_CLUE,
    TUTORIAL_CLUE_NUMBER,
    TUTORIAL_AI_EXPLANATION,
    TUTORIAL_ROUND_2_BOARD,
    TUTORIAL_ROUND_2_TARGETS,
    TUTORIAL_ROUND_2_WORD_ROLES,
    TUTORIAL_TARGETS,
    TUTORIAL_WORD_ROLES,
    simulated_ai_guesses,
    tutorial_repair_clue,
    tutorial_time_remaining,
)
from core.prolific import (
    ATTENTION_CHECK_POST_GAME_ID,
    ATTENTION_CHECK_POST_GAME_QUESTION,
    ATTENTION_CHECK_PROFILE_OPTIONS,
    ATTENTION_CHECK_PROFILE_QUESTION,
    prolific_complete_url,
    prolific_completion_code,
)
from core.validation import validate_general_link, validate_guess_rationale
from ui.components import (
    FINAL_MEDAL_LABELS,
    GUIDE_SECTION_FIGURES,
    GUIDE_STEP_FIGURES,
    RATING_OPTIONS,
    render_board,
    render_board_legend,
    render_board_lock_note,
    render_clue_timer,
    render_hint_panel,
    render_hint_target_selector,
    render_interaction_history,
    render_overview_board_preview,
    render_rating_scale_endpoints,
    render_round_chip,
    render_top_status,
    render_tutorial_status,
    role_badge_html,
)
from ui.game_guide import (
    CLUE_GIVER_INTRO,
    CLUE_GIVER_OUTRO,
    CLUE_GIVER_STEPS,
    GUIDE_NO_AI_TOOLS,
    GUIDE_OVERVIEW,
    GUIDE_REMINDERS,
    GUIDE_ROLE,
    GUIDE_SECTIONS,
)
from ui.study_documents import (
    CONSENT_CHECKLIST_ITEMS,
    INFORMATION_SHEET_INTRODUCTION,
    INFORMATION_SHEET_SECTIONS,
    INFORMATION_SHEET_TITLE,
    render_debriefing_document,
)

POST_GAME_QUESTIONS = [
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
        "reflection_helped",
        "The reflection steps helped me recover from misunderstandings with the AI.",
    ),
    (
        "shared_understanding",
        "By the end of the game, I felt that the AI and I had developed a shared understanding.",
    ),
]

AGE_GROUP_OPTIONS = ["18-24", "25-34", "35-44", "45-54", "55+", "Prefer not to say"]
GENDER_OPTIONS = [
    "Female",
    "Male",
    "Non-binary",
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
ENGLISH_ONLY_ERROR = "Please write your explanation in English only."
ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"


def _render_logo_row():
    """The university/COLAPS logo pair shown at the top of the consent,
    game guide, and participant profile pages."""
    university_col, colaps_col = st.columns(2, gap="large", vertical_alignment="center")
    with university_col:
        st.image(str(ASSETS_DIR / "university_duisburg_essen.png"), width=190)
    with colaps_col:
        st.image(str(ASSETS_DIR / "colaps.png"), width=180)


def screen_consent():
    with st.container(key="consent_document"):
        with st.container(key="consent_logos"):
            _render_logo_row()
        st.markdown(
            f"""
            <section class="information-hero">
                <div class="information-hero-copy">
                    <div class="information-eyebrow">RESEARCH STUDY</div>
                    <h1>Information Sheet for<br>Participation in Research</h1>
                    <p class="information-study-title">{INFORMATION_SHEET_TITLE}</p>
                    <div class="information-meta">
                        <div><span class="information-meta-label">Contact</span><strong>Shima Ghasempour</strong><br><a href="mailto:shima.ghasempoour-ardestani@stud.uni-due.de">shima.ghasempoour-ardestani@stud.uni-due.de</a></div>
                        <div><strong>Department of Human-centered Computing and Cognitive Science</strong></div>
                        <div><strong>October 2026</strong></div>
                    </div>
                </div>
                <div class="information-word-cards" aria-hidden="true">
                    <span>think</span><span>connect</span><span>play</span>
                </div>
            </section>
            <section class="information-intro">
                <div class="information-icon">i</div>
                <div><h2>Information for Participants</h2><p>{INFORMATION_SHEET_INTRODUCTION}</p></div>
            </section>
            """,
            unsafe_allow_html=True,
        )
        for section_number, (heading, content) in enumerate(
            INFORMATION_SHEET_SECTIONS, start=1
        ):
            heading_html = f"<h2>{heading}</h2>" if heading else ""
            st.markdown(
                f"""
                <section class="information-section">
                    <div class="information-number">{section_number}</div>
                    <div class="information-section-copy">{heading_html}{content}</div>
                </section>
                """,
                unsafe_allow_html=True,
            )
    with st.container(border=True, key="consent_action_panel"):
        st.markdown(
            "<h2>Consent Form</h2>"
            "<p class='information-consent-lead'>"
            "PARTICIPATION IN THIS RESEARCH STUDY IS VOLUNTARY</p>"
            "<ul class='information-consent-list'>"
            + "".join(f"<li>{escape(item)}</li>" for item in CONSENT_CHECKLIST_ITEMS)
            + "</ul>",
            unsafe_allow_html=True,
        )
        agreed = st.checkbox(
            "I consent voluntarily to participate in this study.",
            key="consent_confirmation",
        )
        st.caption(
            "Selecting I agree acts as your electronic confirmation. "
            "If you do not agree, close this browser window without continuing."
        )
        if st.button(
            "I agree",
            type="primary",
            use_container_width=True,
            disabled=not agreed,
        ):
            st.session_state.consent_given = True
            st.session_state.consent_timestamp = _now_iso()
            st.rerun()


def screen_welcome():
    with st.container(key="game_guide_document"):
        with st.container(key="game_guide_logos"):
            _render_logo_row()

        st.markdown(
            """
            <section class="game-guide-hero">
                <div class="game-guide-hero-copy">
                    <div class="information-eyebrow">RESEARCH STUDY</div>
                    <h1>Game Guide</h1>
                    <h2>Team Up with an AI</h2>
                    <p>How the game works, in one page.</p>
                    <p class="game-guide-inspiration">Similar to Codenames &mdash; if you've played it before, you'll get the hang of it right away!</p>
                </div>
                <div class="game-guide-word-cards" aria-hidden="true">
                    <span>think</span><span>connect</span><span>play</span>
                </div>
            </section>
            """,
            unsafe_allow_html=True,
        )

        # Placed above section 1 so that participants cannot miss it.
        no_ai_title, no_ai_content = GUIDE_NO_AI_TOOLS
        with st.container(key="guide_no_ai_notice"):
            st.markdown(f"#### :material/block: {no_ai_title}")
            st.markdown(no_ai_content)

        with st.expander(
            "**1**　Overview", expanded=True, icon=":material/groups:"
        ):
            overview_text_col, overview_preview_col = st.columns([4, 1])
            with overview_text_col:
                st.markdown(GUIDE_OVERVIEW)
            with overview_preview_col:
                render_overview_board_preview()
        with st.expander(
            "**2**　Your Role", expanded=True, icon=":material/switch_account:"
        ):
            st.markdown(_guide_role_with_badges(), unsafe_allow_html=True)

        def render_guide_section(section_number, title, content, icon, expanded=False):
            with st.expander(
                f"**{section_number}**　{title}",
                expanded=expanded,
                icon=icon,
            ):
                st.markdown(content)
                figure = GUIDE_SECTION_FIGURES.get(title)
                if figure:
                    st.markdown(figure(), unsafe_allow_html=True)

        section_icons = (
            ":material/target:",
            ":material/smart_toy:",
            ":material/style:",
            ":material/sync:",
            ":material/skip_next:",
            ":material/schedule:",
            ":material/rate_review:",
            ":material/emoji_events:",
        )
        # Targets, neutral cards and bombs come first (section 3): the
        # clue-giver section below already uses these terms.
        (cards_title, cards_content), *later_sections = GUIDE_SECTIONS
        render_guide_section(3, cards_title, cards_content, section_icons[0], expanded=True)

        with st.expander(
            "**4**　When You Are the Clue-Giver",
            expanded=True,
            icon=":material/lightbulb:",
        ):
            st.markdown(CLUE_GIVER_INTRO)
            for step_number, (step_heading, step_content) in enumerate(
                CLUE_GIVER_STEPS, start=1
            ):
                with st.container(key=f"guide_clue_step_{step_number}"):
                    number_col, content_col = st.columns([0.55, 9.45])
                    with number_col:
                        st.markdown(
                            f'<div class="guide-step-number">{step_number}</div>',
                            unsafe_allow_html=True,
                        )
                    with content_col:
                        st.markdown(f"#### {step_heading}")
                        st.markdown(step_content)
                        step_figure = GUIDE_STEP_FIGURES.get(step_heading)
                        if step_figure:
                            st.markdown(step_figure(), unsafe_allow_html=True)
            # Plain text, not st.success() -- the green "success" alert had
            # no actual success to report at this point (just reading the
            # guide), it was only ever borrowed for its visual weight.
            st.markdown(f"*{CLUE_GIVER_OUTRO}*")

        for section_number, ((title, content), icon) in enumerate(
            zip(later_sections, section_icons[1:]), start=5
        ):
            render_guide_section(section_number, title, content, icon)

        with st.container(key="guide_reminders"):
            st.markdown(
                '<div class="guide-reminder-title"><span>★</span>'
                "MOST IMPORTANT THINGS TO REMEMBER</div>",
                unsafe_allow_html=True,
            )
            st.markdown(GUIDE_REMINDERS)

        with st.container(key="game_guide_action"):
            if st.button(
                "Continue to Next Page",
                type="primary",
                use_container_width=True,
            ):
                st.session_state.started = True
                st.rerun()


def _guide_role_with_badges():
    """GUIDE_ROLE as written, with each role followed by the badge that marks
    it in the status bar during the game."""
    badged = {
        "- Clue-Giver": f"- Clue-Giver&nbsp;&nbsp;{role_badge_html('clue')}",
        "- Guesser": f"- Guesser&nbsp;&nbsp;{role_badge_html('guess')}",
    }
    return "\n".join(badged.get(line.strip(), line) for line in GUIDE_ROLE.splitlines())


def _reset_tutorial_practice():
    st.session_state.tutorial_practice_started_at = _now_iso()
    st.session_state.tutorial_practice_result = ""
    st.session_state.tutorial_step = "ai_clue_round"
    for key in list(st.session_state.keys()):
        if str(key).startswith("tutorial_") and key not in {
            "tutorial_completed",
            "tutorial_step",
            "tutorial_practice_started_at",
            "tutorial_practice_result",
        }:
            st.session_state.pop(key, None)


@st.dialog("Try each role once", width="large", dismissible=False)
def _tutorial_intro_dialog():
    st.markdown(
        """
        - **Round 1:** The AI gives a clue and you guess the cards.
        - **Round 2:** You give the clue and predict the AI's guesses.

        The practice board has six cards in a 3 × 2 layout. You will also try the same short
        ratings and explanations used in the real game.

        Nothing in this tutorial is scored or saved to the study data.
        """
    )
    if st.button("Start practice", type="primary", use_container_width=True):
        _reset_tutorial_practice()
        st.rerun()


@st.dialog("Before the AI can guess")
def _clue_form_errors_dialog(problems):
    for problem in problems:
        st.warning(problem)
    if st.button("Got it", type="primary", use_container_width=True):
        st.rerun()


@st.dialog("Before you continue")
def _round_summary_errors_dialog(problems):
    for problem in problems:
        st.warning(problem)
    if st.button("Got it", type="primary", use_container_width=True):
        st.rerun()


@st.dialog("Missing information")
def _profile_missing_fields_dialog(missing):
    st.warning("Please complete: " + ", ".join(missing) + ".")
    if st.button("Got it", type="primary", use_container_width=True):
        st.rerun()


@st.dialog("Which cards was this clue for?", dismissible=False)
def _skip_interpretation_dialog(remaining_guess_slots, options):
    st.caption(
        f"Select exactly {remaining_guess_slots} card(s) you think this clue was "
        "meant for, even if you are not confident. These are stored separately "
        "and do not count as guesses."
    )
    selected = st.multiselect(
        "Cards this clue was meant for",
        options=options,
        max_selections=remaining_guess_slots,
        placeholder=f"Select exactly {remaining_guess_slots} card(s)...",
        label_visibility="collapsed",
        key="guesser_skip_dialog_selection",
    )
    cancel_col, confirm_col = st.columns(2)
    with cancel_col:
        if st.button("Cancel", use_container_width=True):
            st.session_state.guesser_skip_dialog_open = False
            st.rerun()
    with confirm_col:
        if st.button("Confirm skip", type="primary", use_container_width=True):
            if len(selected) != remaining_guess_slots:
                st.error(f"Please select exactly {remaining_guess_slots} card(s).")
            else:
                st.session_state.guesser_skip_dialog_open = False
                st.session_state.guesser_skip_confirmed = True
                st.session_state.guesser_skip_selected_cards = selected
                st.rerun()


@st.dialog("Round 1 result", dismissible=False)
def _tutorial_round1_result_dialog(result):
    if result == "correct":
        st.success("Correct — the clue referred to both target cards.")
    elif result == "bomb":
        st.error("Bomb selected — just as in the real game, the round ends immediately.")
    elif result == "timeout":
        st.warning(
            "Time ran out before you guessed. The intended cards were Cat and Dog "
            "— the revealed colors show each card's role."
        )
    else:
        st.warning("The intended cards were Cat and Dog. The revealed colors show each card's role.")
    st.markdown(f"**AI's explanation:** {TUTORIAL_AI_EXPLANATION}")
    rating = st.radio(
        "After the guesses, how well do you think you and the AI understood each other?",
        options=RATING_OPTIONS,
        index=None,
        horizontal=True,
        key="tutorial_guesser_rating",
    )
    render_rating_scale_endpoints()
    if st.button(
        "Continue to round 2",
        type="primary",
        use_container_width=True,
        disabled=rating is None,
    ):
        st.session_state.tutorial_step = "human_clue_round"
        st.session_state.tutorial_practice_started_at = _now_iso()
        st.rerun()


@st.dialog("Simulated AI's decision", width="large", dismissible=False)
def _tutorial_round2_result_dialog(ai_guesses):
    st.markdown("**Simulated AI guesses:** " + ", ".join(ai_guesses))
    rating_after = st.radio(
        "After the guesses, how well do you think you and the AI understood each other?",
        options=RATING_OPTIONS,
        index=None,
        horizontal=True,
        key="tutorial_rating_after",
    )
    render_rating_scale_endpoints()
    st.divider()
    st.success("You tried both roles and all required inputs.")
    st.caption("Your practice answers are not scored and are not stored in the experimental datasets.")
    if st.button(
        "Begin the real game",
        type="primary",
        use_container_width=True,
        disabled=rating_after is None,
    ):
        st.session_state.tutorial_step = "complete"
        st.session_state.tutorial_completed = True
        mark_session_progress("tutorial")
        st.rerun()


def screen_tutorial():
    """Run two isolated deterministic practice rounds before the experiment."""
    step = st.session_state.get("tutorial_step", "introduction")
    # No hero/header card in the main column -- the real game's own screens
    # (screen_human_clue, screen_human_guesser) never have one above
    # render_top_status() either; an earlier decorative "TUTORIAL · PRACTICE
    # ROUND / Try the game first" hero card made the tutorial look like a
    # different, extra-padded screen instead of the same one the real game
    # uses. The label lives in the sidebar instead, above the History panel
    # added later in this same run (Streamlit appends sidebar content in
    # execution order, so declaring this first keeps it on top) -- that
    # leaves the main column starting directly at the actual round content,
    # instead of a standalone chip floating above a lot of empty space.
    with st.sidebar:
        with st.container(key="tutorial_sidebar_label"):
            render_round_chip("Practice round")

    if step == "introduction":
        _tutorial_intro_dialog()
        return

    if step == "ai_clue_round":
        # Same invisible role-accent marker the real guesser screen uses
        # (see app.css's role accent switch) -- without it, this round
        # silently fell back to the amber clue-giver tint even though the
        # participant is the guesser here (teal everywhere else).
        st.markdown('<div class="role-marker-guess"></div>', unsafe_allow_html=True)
        if not st.session_state.get("tutorial_practice_started_at"):
            st.session_state.tutorial_practice_started_at = _now_iso()
        remaining = tutorial_time_remaining(
            st.session_state.get("tutorial_practice_started_at", "")
        )
        if remaining <= 0 and not st.session_state.get("tutorial_practice_result"):
            st.session_state.tutorial_practice_result = "timeout"
        completed_interactions_preview = int(
            st.session_state.get("tutorial_completed_interactions", 0) or 0
        )
        skip_count_preview = int(st.session_state.get("tutorial_skip_count", 0) or 0)
        render_tutorial_status(
            "Round 1 of 2",
            "AI clues — you guess",
            "ai",
            [
                (
                    "Targets found",
                    len(st.session_state.get("tutorial_found_targets", [])),
                    len(TUTORIAL_TARGETS),
                ),
                (
                    "Turns used",
                    completed_interactions_preview,
                    MAX_INTERACTIONS_PER_ROUND,
                ),
                (
                    "Skips left",
                    MAX_SKIPS_PER_ROUND - skip_count_preview,
                    MAX_SKIPS_PER_ROUND,
                ),
            ],
        )
        st.caption("You are the Guesser. Interpret the clue, explain your reasoning, then guess or use a skip just as in the real game.")
        _render_live_history_sidebar(st.session_state.get("tutorial_history", []), True)
        with st.container(border=True, key="tutorial_ai_clue_panel"):
            repair_attempt = int(st.session_state.get("tutorial_repair_attempt", 0) or 0)
            found_targets = set(st.session_state.get("tutorial_found_targets", []))
            if repair_attempt:
                # Computed once per attempt and cached, not recomputed on
                # every rerun -- recomputing from found_targets meant a
                # single card click (e.g. 1 of the 2 this clue asked for)
                # immediately shrank the *displayed* clue number for the
                # very same still-in-progress attempt, which in turn shrank
                # max_clicks below and disabled every remaining card before
                # the participant could make their second, already-expected
                # click: a dead end with nothing left to press.
                clue_cache_key = f"tutorial_clue_for_attempt_{repair_attempt}"
                if clue_cache_key not in st.session_state:
                    unresolved_targets = TUTORIAL_TARGETS - found_targets
                    st.session_state[clue_cache_key] = tutorial_repair_clue(
                        unresolved_targets, repair_attempt
                    )
                current_clue, current_clue_number = st.session_state[clue_cache_key]
                st.caption(f"Repair attempt {repair_attempt} for the same unresolved target set.")
            else:
                current_clue, current_clue_number = TUTORIAL_CLUE, TUTORIAL_CLUE_NUMBER
            # Same clue-display component as the real game, so the practice
            # round looks exactly like what's coming next.
            render_hint_panel(current_clue, current_clue_number)

            # Now shown in the status bar above (Turns used / Skips left) --
            # these two still drive the actual gameplay logic below (skip
            # gating, completion checks), just no longer duplicated here as
            # their own captions.
            completed_interactions = completed_interactions_preview
            skip_count = skip_count_preview
            last_skip_kind = st.session_state.get("tutorial_last_skip_kind", "")
            if last_skip_kind:
                st.success(
                    f"{last_skip_kind} recorded: one skip was used. "
                    + (
                        "The completed guesses count as one interaction; the skip adds no extra interaction."
                        if last_skip_kind == "Partial skip"
                        else "No completed interaction was used."
                    )
                )

            rationale_key = f"tutorial_guess_rationale_{repair_attempt}"
            rationale = st.text_area(
                "Why do these cards fit the clue? (3–30 English words, no card names)",
                key=rationale_key,
                disabled=bool(st.session_state.get("tutorial_practice_result")),
                placeholder="Explain the general connection without naming any card.",
                height=90,
                max_chars=240,
            )
            rationale_words = len(str(rationale or "").strip().split())
            rationale_valid, rationale_reason = validate_guess_rationale(
                rationale, list(TUTORIAL_BOARD)
            )
            if not rationale.strip():
                st.caption("Write your reasoning first; then select cards directly from the board.")
            elif not rationale_valid:
                rationale_messages = {
                    "too_short": f"Your reasoning has {rationale_words} word(s). Write at least 3 words.",
                    "too_long": "Keep your reasoning to 30 words or 240 characters.",
                    "non_english": "Write your reasoning in English only.",
                    "board_word": "Do not use any board/card names. Explain only the general connection.",
                }
                st.warning(rationale_messages.get(rationale_reason, "Check your reasoning before selecting a card."))
            else:
                st.success("Reasoning complete — select two cards directly from the board.")

            selected = list(st.session_state.get("tutorial_guesser_cards", []))
            current_guesses = list(st.session_state.get("tutorial_current_guesses", []))
            # Board and timer sit side by side, same as the real guesser
            # screen's own board_col/board_timer_col split -- previously the
            # timer lived in its own row up next to the round heading, far
            # above the board it's actually timing, which read as two
            # unrelated pieces of UI instead of one screen.
            board_col, board_timer_col = st.columns([1.7, 1])
            with board_timer_col:
                with st.container(key="tutorial_timer_stack"):
                    render_clue_timer(remaining, pinned=False)
                    tutorial_skip_cluster_placeholder = st.empty()
            with board_col:
                with st.container(key="tutorial_board_wrap"):
                    clicked = render_board(
                        list(TUTORIAL_BOARD),
                        TUTORIAL_WORD_ROLES,
                        guesses=selected,
                        reveal_all=bool(st.session_state.get("tutorial_practice_result")),
                        clickable=not bool(st.session_state.get("tutorial_practice_result")),
                        max_clicks=(
                            len(selected) - len(current_guesses) + current_clue_number
                        ),
                        column_count=3,
                        key_prefix=f"tutorial_board_button_{repair_attempt}",
                    )
            result = st.session_state.get("tutorial_practice_result", "")
            if clicked and not result:
                if remaining <= 0:
                    st.session_state.tutorial_practice_result = "timeout"
                elif not rationale_valid:
                    st.error(_guess_rationale_error(rationale_reason))
                else:
                    selected.append(clicked)
                    current_guesses.append(clicked)
                    st.session_state.tutorial_guesser_cards = selected
                    st.session_state.tutorial_current_guesses = current_guesses
                    if clicked in TUTORIAL_TARGETS:
                        found_targets.add(clicked)
                        st.session_state.tutorial_found_targets = list(found_targets)
                    if clicked == TUTORIAL_BOMB:
                        st.session_state.tutorial_completed_interactions = completed_interactions + 1
                        st.session_state.tutorial_practice_result = "bomb"
                    elif len(current_guesses) >= current_clue_number:
                        completed_interactions += 1
                        st.session_state.tutorial_completed_interactions = completed_interactions
                        if found_targets == set(TUTORIAL_TARGETS):
                            st.session_state.tutorial_practice_result = "correct"
                        elif completed_interactions >= MAX_INTERACTIONS_PER_ROUND:
                            st.session_state.tutorial_practice_result = "incorrect"
                        else:
                            st.session_state.tutorial_practice_result = "incorrect"
                    turn_result = st.session_state.get("tutorial_practice_result", "")
                    if turn_result in {"bomb", "correct", "incorrect"}:
                        tutorial_history = list(st.session_state.get("tutorial_history", []))
                        tutorial_history.append(
                            {
                                "turn": len(tutorial_history) + 1,
                                "clue_giver": "ai",
                                "guesser": "human",
                                "hint": current_clue,
                                "hint_number": current_clue_number,
                                "guesses": list(current_guesses),
                                "correct_guesses": [
                                    word for word in current_guesses if word in TUTORIAL_TARGETS
                                ],
                                "neutral_guesses": [
                                    word
                                    for word in current_guesses
                                    if word not in TUTORIAL_TARGETS and word != TUTORIAL_BOMB
                                ],
                                "bomb_hit": turn_result == "bomb",
                                "correct": turn_result == "correct",
                                "outcome": "wrong" if turn_result == "incorrect" else turn_result,
                                "guess_rationale": rationale if rationale_valid else "",
                            }
                        )
                        st.session_state.tutorial_history = tutorial_history
                    st.rerun()

            result = st.session_state.get("tutorial_practice_result", "")
            if not result:
                remaining_guess_slots = current_clue_number - len(current_guesses)
                unavailable_cards = set(selected)
                skip_disabled = skip_count >= MAX_SKIPS_PER_ROUND
                # Rendered up next to the timer, same as the real game's skip
                # control -- only the button lives there; the interpretation
                # picker opens as a dialog once clicked (see
                # _skip_interpretation_dialog, shared with screen_human_guesser).
                # Once both skips are used there's nothing left to offer, so
                # the button disappears entirely instead of sitting there
                # disabled -- the caption below already explains why.
                if not skip_disabled:
                    with tutorial_skip_cluster_placeholder:
                        with st.container():
                            st.markdown("<div class='skip-button-marker'></div>", unsafe_allow_html=True)
                            if st.button(
                                "Skip",
                                use_container_width=True,
                                key=f"tutorial_skip_button_{repair_attempt}",
                            ):
                                st.session_state.guesser_skip_dialog_open = True
                                st.rerun()
                if st.session_state.get("guesser_skip_dialog_open") and not skip_disabled:
                    skip_options = [
                        word for word in TUTORIAL_BOARD if word not in unavailable_cards
                    ]
                    _skip_interpretation_dialog(remaining_guess_slots, skip_options)
                skip_confirmed = st.session_state.pop("guesser_skip_confirmed", False)
                skip_interpretation = (
                    st.session_state.pop("guesser_skip_selected_cards", [])
                    if skip_confirmed
                    else []
                )
                if skip_confirmed:
                    if len(skip_interpretation) != remaining_guess_slots:
                        st.error(
                            f"Please select exactly {remaining_guess_slots} card(s) before skipping."
                        )
                    elif current_guesses and not rationale_valid:
                        st.error(_guess_rationale_error(rationale_reason))
                    else:
                        # A partial skip preserves the already-completed guesses as one
                        # interaction. A full skip consumes no interaction.
                        if current_guesses:
                            completed_interactions += 1
                            st.session_state.tutorial_completed_interactions = completed_interactions
                            st.session_state.tutorial_last_skip_kind = "Partial skip"
                        else:
                            st.session_state.tutorial_last_skip_kind = "Full skip"
                        st.session_state.tutorial_skip_count = skip_count + 1
                        unresolved_targets = TUTORIAL_TARGETS - found_targets
                        if not unresolved_targets:
                            st.session_state.tutorial_practice_result = "correct"
                        elif completed_interactions >= MAX_INTERACTIONS_PER_ROUND:
                            st.session_state.tutorial_practice_result = "incorrect"
                        else:
                            st.session_state.tutorial_repair_attempt = repair_attempt + 1
                            st.session_state.tutorial_current_guesses = []
                            # A repair/new clue starts a fresh participant decision window.
                            st.session_state.tutorial_practice_started_at = _now_iso()
                        is_partial_skip = bool(current_guesses)
                        tutorial_history = list(st.session_state.get("tutorial_history", []))
                        tutorial_history.append(
                            {
                                "turn": len(tutorial_history) + 1,
                                "clue_giver": "ai",
                                "guesser": "human",
                                "hint": current_clue,
                                "hint_number": current_clue_number,
                                "guesses": list(current_guesses),
                                "correct_guesses": [
                                    word for word in current_guesses if word in TUTORIAL_TARGETS
                                ],
                                "neutral_guesses": [
                                    word
                                    for word in current_guesses
                                    if word not in TUTORIAL_TARGETS and word != TUTORIAL_BOMB
                                ],
                                "outcome": "partial_skip" if is_partial_skip else "skip",
                                "skipped": True,
                                "skipped_by": "human",
                                "partial_skip": is_partial_skip,
                                "skip_interpreted_cards": list(skip_interpretation),
                                "guess_rationale": rationale if rationale_valid else "",
                            }
                        )
                        st.session_state.tutorial_history = tutorial_history
                        new_result = st.session_state.get("tutorial_practice_result", "")
                        if new_result:
                            # Show the round-1 result dialog directly in this
                            # same rerun, right after the skip-interpretation
                            # dialog closed above -- a plain st.rerun() here
                            # left one rerun with no dialog open at all in
                            # between, which read as two separate popups
                            # flashing one after another (same fix as the
                            # real game's skip flow).
                            _tutorial_round1_result_dialog(new_result)
                        else:
                            st.rerun()
                if skip_disabled:
                    st.caption("Both practice skips have been used; continue by selecting cards.")

            if result in {"correct", "incorrect", "bomb", "timeout"}:
                _tutorial_round1_result_dialog(result)
        return

    if step == "human_clue_round":
        # Same invisible role-accent marker the real clue-giver screen uses
        # -- this round already happened to render amber by coincidence
        # (the app's default/fallback tint), but setting it explicitly keeps
        # that from being an accident that breaks the moment the fallback
        # ever changes.
        st.markdown('<div class="role-marker-clue"></div>', unsafe_allow_html=True)
        remaining = tutorial_time_remaining(
            st.session_state.get("tutorial_practice_started_at", "")
        )
        render_tutorial_status(
            "Round 2 of 2",
            "You're giving the clue",
            "human",
            [],
        )
        st.caption("The card roles are visible because you are the Clue-Giver. Complete every field before the simulated AI guesses.")
        # Its own history, not round 1's -- round 2 is a single clue
        # submission with no back-and-forth turns of its own, so this stays
        # empty ("0 past turns"), but it must be its own panel rather than
        # showing round 1's leftover tutorial_history.
        _render_live_history_sidebar(
            st.session_state.get("tutorial_history_round2", []), True
        )
        if remaining <= 0 and not st.session_state.get("tutorial_human_clue_submitted"):
            st.warning("Practice time expired. This does not affect your study participation or score.")
            if st.button("Retry with a fresh timer", key="tutorial_round2_retry"):
                st.session_state.tutorial_practice_started_at = _now_iso()
                st.rerun()
            return
        with st.container(border=True, key="tutorial_human_clue_panel"):
            # Board and timer side by side, same as the real clue-giver
            # screen's own board_col/board_timer_col split -- previously the
            # timer lived in its own row up next to the round heading, far
            # above the board it's actually timing.
            board_col, board_timer_col = st.columns([1.7, 1])
            with board_timer_col:
                with st.container(key="tutorial_timer_stack"):
                    render_clue_timer(remaining, pinned=False)
            with board_col:
                with st.container(key="tutorial_board_wrap"):
                    render_board(
                        list(TUTORIAL_ROUND_2_BOARD),
                        TUTORIAL_ROUND_2_WORD_ROLES,
                        guesses=st.session_state.get("tutorial_simulated_ai_guesses", []),
                        reveal_all=True,
                        column_count=3,
                    )
                    render_board_legend()
            form_locked = bool(st.session_state.get("tutorial_human_clue_submitted"))
            with st.container(key="clue_form_steps"):
                st.markdown(
                    """
                    <div class="panel-title section-gap">Enter your clue for the AI guesser</div>
                    """,
                    unsafe_allow_html=True,
                )
                tutorial_submit_attempted = bool(
                    st.session_state.get("tutorial_clue_submit_attempted")
                )
                with st.container(border=True, key="clue_hint_container"):
                    clue_col, number_col = st.columns([2, 1])
                    with clue_col:
                        clue = st.text_input(
                            "One-word clue",
                            key="tutorial_human_clue",
                            placeholder="Example: Fruit",
                            label_visibility="collapsed",
                            disabled=form_locked,
                        )
                    with number_col:
                        clue_number = st.selectbox(
                            "Clue number N",
                            options=[1, 2],
                            index=1,
                            key="tutorial_human_clue_number",
                            label_visibility="collapsed",
                            disabled=form_locked,
                        )
                tutorial_target_options = [
                    word
                    for word in TUTORIAL_ROUND_2_BOARD
                    if word in TUTORIAL_ROUND_2_TARGETS
                ]
                st.session_state.tutorial_intended_targets = [
                    word
                    for word in st.session_state.get("tutorial_intended_targets", [])
                    if word in tutorial_target_options
                ][:clue_number]
                # Only the real target words are offered here, exactly like the
                # real game -- listing all six board words (most disabled) made
                # this look like a second, confusing board.
                with st.container(key="clue_targets_container"):
                    render_hint_target_selector(
                        tutorial_target_options,
                        st.session_state.tutorial_intended_targets,
                        clue_number,
                        state_key="tutorial_intended_targets",
                        key_prefix="tutorial_hint_target",
                        column_count=3,
                        disabled=form_locked,
                    )
                intended = st.session_state.tutorial_intended_targets
                st.markdown(
                    """
                    <div class="panel-title section-gap">Select the cards you think the AI will choose</div>
                    """,
                    unsafe_allow_html=True,
                )
                with st.container(key="clue_expected_container"):
                    expected = st.multiselect(
                        f"Which cards do you expect the AI to guess? · select exactly {clue_number}",
                        options=list(TUTORIAL_ROUND_2_BOARD),
                        max_selections=clue_number,
                        placeholder=f"Choose {clue_number} card(s)...",
                        label_visibility="collapsed",
                        key="tutorial_expected_guesses",
                        disabled=form_locked,
                    )
                with st.container(border=True, key="before_ai_guess_panel"):
                    prompt_col, rating_col = st.columns([1.45, 1])
                    with prompt_col:
                        st.markdown(
                            """
                            <div class="panel-title section-gap">Before AI guesses</div>
                            <p class="subtle-text before-ai-question">How well do you expect the AI understood your clue?</p>
                            """,
                            unsafe_allow_html=True,
                        )
                    with rating_col:
                        with st.container(key="clue_rating_container"):
                            rating_before = st.radio(
                                "How well do you expect the AI to understand your clue?",
                                options=RATING_OPTIONS,
                                index=None,
                                format_func=lambda option: f"{option}",
                                horizontal=True,
                                label_visibility="collapsed",
                                key="tutorial_rating_before",
                                disabled=form_locked,
                            )
                            render_rating_scale_endpoints()
                st.markdown(
                    """
                    <div class="panel-title section-gap">General link</div>
                    """,
                    unsafe_allow_html=True,
                )
                with st.container(key="clue_general_link_container"):
                    general_link = st.text_area(
                        "General link (3–20 English words, no card names)",
                        key="tutorial_general_link",
                        placeholder="Describe the shared relationship without naming any card.",
                        disabled=form_locked,
                        max_chars=150,
                    )
                    if not form_locked:
                        st.caption("Press Ctrl+Enter or click outside this box to save it before continuing.")
            link_valid_live, _link_reason_live = validate_general_link(
                general_link, list(TUTORIAL_ROUND_2_BOARD)
            )
            clue_valid_live, _clue_error_live = validate_human_hint_with_history(
                clue, list(TUTORIAL_ROUND_2_BOARD), [], []
            )
            if tutorial_submit_attempted and not form_locked:
                tutorial_invalid_classes = " ".join(
                    css_class
                    for ready, css_class in [
                        (clue_valid_live, "invalid-hint"),
                        (len(intended) == clue_number, "invalid-targets"),
                        (len(expected) == clue_number, "invalid-expected"),
                        (rating_before is not None, "invalid-rating"),
                        (link_valid_live, "invalid-link"),
                    ]
                    if not ready
                )
                if tutorial_invalid_classes:
                    st.markdown(
                        f"<div class='turn-invalid-marker {tutorial_invalid_classes}'></div>",
                        unsafe_allow_html=True,
                    )
            if not form_locked:
                st.markdown("<div class='let-ai-guess-marker'></div>", unsafe_allow_html=True)
            if not form_locked and st.button(
                "Let the simulated AI guess", type="primary", use_container_width=True
            ):
                st.session_state.tutorial_clue_submit_attempted = True
                link_valid, link_reason = validate_general_link(
                    general_link, list(TUTORIAL_ROUND_2_BOARD)
                )
                clue_valid, clue_error = validate_human_hint_with_history(
                    clue,
                    list(TUTORIAL_ROUND_2_BOARD),
                    [],
                    [],
                )
                if not (
                    clue_valid
                    and len(intended) == clue_number
                    and len(expected) == clue_number
                    and rating_before is not None
                    and link_valid
                ):
                    problems = []
                    if not clue_valid:
                        problems.append(clue_error)
                    if len(intended) != clue_number:
                        problems.append(f"Select exactly {clue_number} intended target card(s).")
                    if len(expected) != clue_number:
                        problems.append(f"Select exactly {clue_number} expected AI guess(es).")
                    if rating_before is None:
                        problems.append("Choose your expected-understanding rating.")
                    if not link_valid:
                        link_messages = {
                            "too_short": "Write at least 3 English words.",
                            "too_long": "Keep the General Link to 20 words or fewer.",
                            "non_english": "Write the General Link in English only.",
                            "board_word": "Do not mention any board/card names in the General Link.",
                        }
                        problems.append(
                            link_messages.get(link_reason, "Check the General Link and try again.")
                        )
                    _clue_form_errors_dialog(problems)
                else:
                    st.session_state.tutorial_human_clue_submitted = True
                    st.session_state.tutorial_simulated_ai_guesses = simulated_ai_guesses(clue_number)
                    st.rerun()

            if form_locked:
                ai_guesses = st.session_state.get("tutorial_simulated_ai_guesses", [])
                _tutorial_round2_result_dialog(ai_guesses)
        return


def _anonymous_participant_id():
    session_id = str(st.session_state.get("session_id", "")).replace("-", "")
    suffix = session_id[-8:] if session_id else "unknown"
    return f"participant_{suffix}"


def _display_player_name():
    return st.session_state.get("nickname") or "Participant"


def _share_explanations():
    return st.session_state.get("condition", DEFAULT_CONDITION) == "adaptive"


def screen_name():
    with st.container(key="participant_profile_page"):
        with st.container(key="participant_profile_logos"):
            _render_logo_row()
        st.markdown(
            """
            <section class="participant-profile-hero">
                <div class="participant-profile-hero-copy">
                    <div class="information-eyebrow">PARTICIPANT PROFILE</div>
                    <h1>Participant Profile</h1>
                    <p>These answers help us analyze the game results.</p>
                </div>
                <div class="participant-profile-card-art" aria-hidden="true">
                    <div class="profile-avatar"></div>
                    <i></i><i></i><i></i>
                </div>
            </section>
            """,
            unsafe_allow_html=True,
        )
        with st.container(border=True, key="participant_profile_panel"):
            form_col, aside_col = st.columns([3.35, 1.15], gap="large")
            with form_col:
                with st.container(key="profile_nickname_group"):
                    nickname = st.text_input(
                        "Nickname or pseudonym (optional — do not enter your real name)",
                        value=st.session_state.get("nickname", ""),
                        placeholder="Optional nickname",
                    )
                with st.container(key="profile_age_group_group"):
                    # A radio group, not a dropdown: with only six options, showing
                    # them all at once is one click instead of two and lets a
                    # participant compare choices at a glance -- consistent with
                    # every other question on this page.
                    age_group = st.radio(
                        "What is your age group?",
                        AGE_GROUP_OPTIONS,
                        index=None,
                        horizontal=True,
                        key="profile_age_group",
                    )
                with st.container(key="profile_gender_group"):
                    gender_choice = st.radio(
                        "What is your gender?",
                        GENDER_OPTIONS,
                        index=None,
                        horizontal=True,
                        key="profile_gender",
                    )
                with st.container(key="profile_english_group"):
                    english_proficiency = st.radio(
                        "How would you describe your English proficiency?",
                        ENGLISH_PROFICIENCY_OPTIONS,
                        index=None,
                        horizontal=True,
                        key="profile_english_proficiency",
                    )
                with st.container(key="profile_ai_experience_group"):
                    ai_experience = st.radio(
                        "How often do you use AI tools such as ChatGPT, Gemini, or Claude?",
                        AI_EXPERIENCE_OPTIONS,
                        index=None,
                        horizontal=True,
                        key="profile_ai_experience",
                    )
                with st.container(key="profile_attention_check_group"):
                    attention_check_answer = st.radio(
                        ATTENTION_CHECK_PROFILE_QUESTION,
                        ATTENTION_CHECK_PROFILE_OPTIONS,
                        index=None,
                        horizontal=True,
                        key="profile_attention_check",
                    )
                with st.container(key="profile_codenames_group"):
                    codenames_experience = st.radio(
                        "Have you played Codenames before?",
                        CODENAMES_EXPERIENCE_OPTIONS,
                        index=None,
                        horizontal=True,
                        key="profile_codenames_experience",
                    )
            with aside_col:
                with st.container(key="profile_side_cards"):
                    st.markdown(
                        """
                        <aside class="profile-aside">
                            <section>
                                <div class="profile-aside-icon">i</div>
                                <h2>Why we ask this</h2>
                                <p>These answers help us analyze the game results.</p>
                            </section>
                            <section>
                                <div class="profile-aside-icon profile-shield">◇</div>
                                <h2>Your privacy</h2>
                                <p>Do not enter your real name.</p>
                            </section>
                            <div class="profile-aside-word-cards" aria-hidden="true">
                                <span>think</span><span>connect</span><span>play</span>
                            </div>
                        </aside>
                        """,
                        unsafe_allow_html=True,
                    )

            if st.button("Continue", type="primary", use_container_width=True):
                missing = []
                if not age_group:
                    missing.append("age group")
                if gender_choice is None:
                    missing.append("gender")
                if english_proficiency is None:
                    missing.append("English proficiency")
                if ai_experience is None:
                    missing.append("AI experience")
                if codenames_experience is None:
                    missing.append("Codenames experience")
                if attention_check_answer is None:
                    missing.append("the reading-check question")
                if missing:
                    _profile_missing_fields_dialog(missing)
                else:
                    clean_nickname = nickname.strip()
                    # participant_id is always the anonymous, session-derived
                    # ID -- never the free-text nickname. Two participants
                    # could otherwise pick the same nickname (colliding their
                    # data under one participant_id), or type something that
                    # de-anonymizes them despite the "do not enter your real
                    # name" hint. Nickname stays a separate, display-only field.
                    participant_id = _anonymous_participant_id()
                    gender = gender_choice
                    # participant_id itself is set inside initialize_session_log,
                    # only once registration actually succeeds -- app.py's
                    # routing treats a set participant_id as "registered", so
                    # it must never be committed ahead of a DB call that might
                    # still fail.
                    st.session_state.nickname = clean_nickname
                    st.session_state.age_group = age_group
                    st.session_state.gender = gender
                    st.session_state.english_proficiency = english_proficiency
                    st.session_state.ai_experience = ai_experience
                    st.session_state.codenames_experience = codenames_experience
                    # Recorded, never used to block: Prolific only allows a
                    # rejection after two failed checks, decided afterwards.
                    st.session_state.attention_check_profile_answer = attention_check_answer
                    if initialize_session_log(participant_id):
                        st.rerun()


def _current_action_index():
    return len(st.session_state.get("interaction_history", []))


def _next_action_number():
    return _current_action_index() + 1


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
    st.session_state.pending_hint_meta = None
    st.session_state.final_guess_deadline_active = False
    clear_participant_decision_timer()


def _log_timeout(timeout_timestamp, repair_context):
    if not timeout_timestamp:
        return
    log_event(
        "clue_timeout",
        {
            "timer_duration_seconds": st.session_state.get(
                "clue_timer_duration_seconds", CLUE_TIMER_SECONDS
            ),
            "clue_start_timestamp": st.session_state.get("clue_timer_started_at", ""),
            "human_timed_out": True,
            "timeout_timestamp": timeout_timestamp,
            "timed_out": True,
            "repair_attempt": bool(repair_context),
            "repair_source_turn": (repair_context or {}).get("skipped_turn", ""),
            "repair_chain_id": (repair_context or {}).get("repair_chain_id", ""),
            "repair_attempt_number": (repair_context or {}).get("repair_attempt_number", ""),
            "role": st.session_state.get("role", ""),
        },
        turn_number=(
            st.session_state.interaction_history[-1].get("turn", "")
            if st.session_state.get("interaction_history")
            else ""
        ),
    )



def _handle_skip_exhausted_timeout(hint, hint_number, intended_targets, expected_guesses):
    """The decision timer expired with no skips left to absorb it. The first
    time this happens, start one final short countdown instead of ending the
    turn -- if that also expires with nothing submitted, the round ends
    automatically as a loss (see FINAL_GUESS_TIMER_SECONDS)."""
    if not st.session_state.get("final_guess_deadline_active"):
        st.session_state.final_guess_deadline_active = True
        start_participant_decision_timer(_now_iso(), duration_seconds=FINAL_GUESS_TIMER_SECONDS)
        st.session_state.final_guess_warning_notice = True
        st.rerun()
    record_forced_timeout_loss(hint, hint_number, intended_targets, expected_guesses)
    _clear_current_clue()
    return True


def _consume_human_guess_timeout():
    """Consume an expired AI-clue turn once, preserving unsubmitted analysis input."""
    if not st.session_state.get("hint") or not participant_decision_timer_expired():
        return False
    if not can_skip_current_clue():
        return _handle_skip_exhausted_timeout(
            st.session_state.hint,
            st.session_state.hint_number,
            st.session_state.get("hint_targets", []),
            st.session_state.get("hint_expected_guesses", []),
        )
    pending_meta = st.session_state.get("pending_hint_meta") or {}
    repair_context = pending_meta.get("repair_context")
    interpretation_key = (
        f"skip_interpretation_{st.session_state.round}_"
        f"{_current_action_index()}"
    )
    timeout_timestamp = record_timeout(
        st.session_state.hint,
        st.session_state.hint_number,
        st.session_state.get("hint_targets", []),
        st.session_state.get("hint_expected_guesses", []),
        guess_rationale=st.session_state.get("current_guess_rationale", ""),
        hint_explanation=st.session_state.get("hint_explanation", ""),
        timeout_selected_cards=list(st.session_state.get("pending_guesses", [])),
        skip_interpreted_cards=list(st.session_state.get(interpretation_key, [])),
        repair_context=repair_context,
        hint_raw_response=pending_meta.get("raw_response", ""),
        hint_time_sec=pending_meta.get("hint_time_sec"),
    )
    _log_timeout(timeout_timestamp, repair_context)
    st.session_state.last_timeout_notice = True
    _clear_current_clue()
    return True


def _consume_human_clue_timeout():
    """Consume an expired human clue-form task without invoking the AI.

    Independent of the shared skip budget (see CLUE_GIVER_FREE_TIMEOUTS_PER_ROUND):
    the clue-giver's first timeout each round costs nothing at all -- a
    participant who doesn't yet know the timer exists shouldn't lose
    anything for it -- and every one after that costs a completed
    interaction from the round's MAX_INTERACTIONS_PER_ROUND budget instead
    of a skip. That budget already ends the round automatically once it's
    exhausted (see the tail of record_skip), so unlike the shared-skip path
    this doesn't need its own "stalled too long" forced-final-window escape
    hatch -- repeated clue-giver timeouts alone will end the round.
    """
    if not participant_decision_timer_expired():
        return False
    turn_index = _current_action_index()
    hint = st.session_state.get(
        f"human_hint_{st.session_state.round}_{turn_index}", ""
    )
    hint_number = int(
        st.session_state.get(
            f"clue_count_{st.session_state.round}_{turn_index}",
            st.session_state.get("hint_number", 1),
        )
        or 1
    )
    expected_guesses = list(
        st.session_state.get(
            f"expected_guesses_{st.session_state.round}_{turn_index}", []
        )
    )
    rating_before = st.session_state.get(
        f"before_ai_guess_rating_{st.session_state.round}_{turn_index}"
    )
    general_link = str(
        st.session_state.get(
            f"pre_ai_general_link_{st.session_state.round}_{turn_index}", ""
        )
        or ""
    ).strip()
    clue_giver_timeouts = st.session_state.get("round_clue_giver_timeouts", 0)
    is_free = clue_giver_timeouts < CLUE_GIVER_FREE_TIMEOUTS_PER_ROUND
    repair_context = _pending_human_clue_repair_context()
    timeout_timestamp = record_timeout(
        hint,
        hint_number,
        list(st.session_state.get("hint_targets", [])),
        expected_guesses,
        hint_time_sec=_seconds_between(
            st.session_state.get("current_hint_start_time", "")
        ),
        human_expected_ai_understanding_rating=rating_before,
        human_explanation_raw=general_link,
        human_explanation_is_valid=False if general_link else None,
        human_explanation_blocked_reason=(
            "timeout_unsubmitted" if general_link else ""
        ),
        human_explanation_source=(
            "pre_ai_human_clue_form_unsubmitted" if general_link else ""
        ),
        human_explanation_collected_at="",
        repair_context=repair_context,
        timeout_cost="none" if is_free else "interaction",
    )
    if timeout_timestamp is None:
        # record_timeout's own re-entrancy guard already fired (this
        # timeout was already consumed by an earlier call this render) --
        # don't double-count it against the free-timeout budget either.
        _clear_current_clue()
        return True
    st.session_state.round_clue_giver_timeouts = clue_giver_timeouts + 1
    _log_timeout(timeout_timestamp, repair_context)
    st.session_state.clue_giver_timeout_notice = "free" if is_free else "interaction"
    _clear_current_clue()
    return True


def _pending_ai_clue_repair_context():
    """Return the latest skipped AI-clue target set until a linked retry exists."""
    return _pending_repair_context("ai")


def _pending_human_clue_repair_context():
    """Same as _pending_ai_clue_repair_context, for a human clue the AI skipped."""
    return _pending_repair_context("human")


def _pending_repair_context(clue_giver):
    """The latest skipped clue by this clue-giver whose unresolved targets
    the next clue is invited (never required) to revisit -- offered once,
    until a turn linked to it as a repair attempt exists."""
    history = st.session_state.get("interaction_history", [])
    repaired_source_turns = {
        item.get("repair_source_turn")
        for item in history
        if item.get("repair_attempt")
    }
    for item in reversed(history):
        if item.get("clue_giver") != clue_giver:
            continue
        if not item.get("repair_required") or item.get("turn") in repaired_source_turns:
            continue
        unresolved = [
            word
            for word in item.get("intended_targets", [])
            if word not in item.get("correct_guesses", [])
            and word not in st.session_state.get("found_targets", [])
        ]
        if not unresolved:
            return None
        chain_id = item.get("repair_chain_id") or (
            f"{st.session_state.get('session_id', '')}:"
            f"r{st.session_state.round}:t{item.get('turn')}"
        )
        return {
            "skipped_turn": item.get("turn"),
            "skipped_hint": item.get("hint", ""),
            "unresolved_targets": unresolved,
            "participant_interpretation": list(item.get("skip_interpreted_cards", [])),
            "participant_reasoning": item.get("guess_rationale", ""),
            "participant_reflection": item.get("reflection_explanation_raw", ""),
            "repair_chain_id": chain_id,
            "repair_attempt_number": int(item.get("repair_attempt_number", 0) or 0) + 1,
        }
    return None


def _request_ai_hint(repair_context, extra_forbidden_hints=None):
    used_hints = list(st.session_state.used_hints) + list(extra_forbidden_hints or [])
    return generate_ai_hint(
        st.session_state.target_words,
        st.session_state.bomb_words,
        st.session_state.neutral_words,
        st.session_state.word_type,
        st.session_state.interaction_history,
        used_hints,
        st.session_state.ai_round_summaries,
        condition=st.session_state.get("condition", DEFAULT_CONDITION),
        repair_context=repair_context,
    )


def _generate_and_store_ai_hint():
    hint_start_time = _now_iso()
    repair_context = _pending_ai_clue_repair_context()
    try:
        with st.spinner("AI is generating a clue..."):
            hint_result = _request_ai_hint(repair_context)
            returned_hint = str(hint_result.get("hint", "")).strip().lower()
            if returned_hint in st.session_state.used_hints:
                # _generate_hint_with_forbidden already lists every used hint
                # as forbidden in the prompt and retries internally, but a
                # model can still ignore that instruction and hand back a
                # repeat anyway -- one more attempt with this exact word
                # blocked outright (not just one of many named in a prompt)
                # rather than letting a repeated clue reach the participant.
                hint_result = _request_ai_hint(repair_context, [returned_hint])
    except AIClueGenerationError as error:
        st.session_state.current_hint_start_time = ""
        log_event(
            "ai_clue_generation_failed",
            {
                "error": str(error),
                "technical_timeout_seconds": AI_API_TIMEOUT_SECONDS,
                "attempts": error.attempts,
                "last_raw_response": error.last_raw,
                "response_time_sec": error.response_time_sec,
            },
            turn_number=_next_action_number(),
        )
        st.error("Failed to generate a valid AI clue after 3 attempts. Please try again.")
        return False
    hint_end_time = _now_iso()
    hint_time_sec = _seconds_between(hint_start_time, hint_end_time)
    st.session_state.hint = hint_result.get("hint", "")
    st.session_state.hint_number = hint_result.get("hint_number", 1)
    st.session_state.hint_targets = hint_result.get("intended_targets", [])
    st.session_state.hint_expected_guesses = hint_result.get("expected_guesses", [])
    st.session_state.hint_explanation = hint_result.get("explanation", "")
    st.session_state.current_hint_start_time = hint_start_time
    st.session_state.current_turn_start_time = hint_end_time
    st.session_state.current_guess_start_time = hint_end_time
    start_participant_decision_timer(hint_end_time, duration_seconds=GUESSER_TIMER_SECONDS)
    st.session_state.pending_hint_meta = {
        "raw_response": hint_result.get("raw_response", ""),
        "hint_time_sec": hint_time_sec,
        "response_time_sec": hint_result.get("response_time_sec"),
        "attempts": hint_result.get("attempts"),
        "repair_context": repair_context,
    }
    return True


def _attach_ai_explanation(latest_item):
    ai_explanation = generate_ai_turn_explanation(
        latest_item.get("hint", ""),
        latest_item.get("hint_number", 1),
        latest_item.get("intended_targets", []),
        latest_item.get("guesses", []),
        st.session_state.get("board", []),
        latest_item.get("hint_explanation", ""),
    )
    for key in [
        "ai_relationship_type",
        "ai_explanation_raw",
        "ai_explanation_sanitized",
        "ai_explanation_is_valid",
        "ai_explanation_blocked_reason",
    ]:
        latest_item[key] = ai_explanation.get(key, "")
    latest_item["ai_explanation"] = ai_explanation.get(
        "ai_explanation_sanitized", ai_explanation.get("ai_explanation", "")
    )
    latest_item["reflection_source"] = "ai_clue_giver"


def _word_count(text):
    return len([word for word in text.split() if word.strip()])


def _is_english_text(text):
    text = str(text or "").strip()
    return bool(re.search(r"[A-Za-z]", text)) and text.isascii()


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _seconds_between(start_iso, end_iso=None):
    if not start_iso:
        return None
    try:
        start = datetime.fromisoformat(start_iso)
        end = datetime.fromisoformat(end_iso) if end_iso else datetime.now(timezone.utc)
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
    return f"guess_rationale_{st.session_state.round}_{_current_action_index()}"


def _render_guess_rationale_input():
    key = _guess_rationale_key()
    existing = st.session_state.get(key, st.session_state.get("current_guess_rationale", ""))
    st.session_state[key] = existing
    st.markdown(
        """
        <div class="guess-rationale-head">
            <div class="panel-title">Why these cards?</div>
            <div class="guess-rationale-rule">3-30 English words · no card names · before selecting</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    rationale = st.text_area(
        "Guess reasoning",
        max_chars=240,
        placeholder="Describe the general connection without naming any card on the board.",
        label_visibility="collapsed",
        key=key,
    )
    st.session_state.current_guess_rationale = rationale
    word_count = _word_count(rationale)
    is_valid, blocked_reason = validate_guess_rationale(
        rationale,
        st.session_state.get("board", []),
    )
    status_class = "ok" if is_valid else "pending"
    status_text = (
        f"{word_count} / 30 words"
        if word_count
        else "Write a short reason, then choose cards"
    )
    if word_count and not is_valid:
        status_text = {
            "too_short": "Use at least 3 words",
            "too_long": "Use at most 30 words / 240 characters",
            "non_english": "English only",
            "board_word": "Do not use board/card names",
        }.get(blocked_reason, "Check your explanation")
    st.markdown(
        f"<div class='guess-rationale-status {status_class}'>{escape(status_text)}</div>",
        unsafe_allow_html=True,
    )
    st.caption("Press Ctrl+Enter or click outside this box to save it before selecting cards.")
    return rationale.strip(), is_valid


def _general_link_error(reason):
    return {
        "too_short": "Please write at least 3 words for the General Link.",
        "too_long": "Please keep the General Link to 20 words or 150 characters.",
        "non_english": ENGLISH_ONLY_ERROR,
        "board_word": BOARD_WORD_ERROR,
    }.get(reason, "Please enter a valid General Link.")


def _guess_rationale_error(reason):
    return {
        "too_short": "Please write at least 3 words before selecting a card.",
        "too_long": "Please keep your explanation to 30 words or 240 characters.",
        "non_english": ENGLISH_ONLY_ERROR,
        "board_word": "Do not use any board/card names. Explain only the general connection.",
    }.get(reason, "Please enter a valid explanation before selecting a card.")


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
                    "human_perceived_understanding_rating",
                    "human_relationship_type",
                    "human_explanation_raw",
                    "human_explanation_is_valid",
                    "human_explanation_blocked_reason",
                    "human_explanation_source",
                    "human_explanation_collected_at",
                    "ai_relationship_type",
                    "ai_explanation_raw",
                    "ai_explanation_sanitized",
                    "ai_explanation_is_valid",
                    "ai_explanation_blocked_reason",
                    "ai_explanation",
                    "reflection_source",
                    "wrong_guess_replacements",
                    "wrong_guess_replacement_actor",
                    "wrong_guess_replacement_raw_response",
                    "wrong_guess_replacement_response_time_sec",
                    "wrong_guess_replacement_attempts",
                ]:
                    summary_item[key] = item.get(key, "")


def _save_turn_reflection(item, understood_ai_rating, relationship_type, explanation):
    explanation = (explanation or "").strip()
    understood_ai_rating = int(understood_ai_rating)
    item["reflection_rating"] = understood_ai_rating
    item["human_perceived_understanding_rating"] = understood_ai_rating
    st.session_state.perception_rating = understood_ai_rating
    if item.get("clue_giver") == "human":
        item["reflection_relationship_type"] = relationship_type or ""
        item["human_relationship_type"] = relationship_type or ""
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


def _attach_ai_wrong_guess_replacements(item):
    if (
        not item
        or item.get("bomb_hit")
        or item.get("guesser") != "ai"
        or not item.get("neutral_guesses")
    ):
        return
    result = generate_ai_wrong_guess_replacements(
        st.session_state.board,
        st.session_state.guesses,
        item.get("hint", ""),
        item.get("neutral_guesses", []),
    )
    item["wrong_guess_replacements"] = result.get("cards", [])
    item["wrong_guess_replacement_actor"] = "ai"
    item["wrong_guess_replacement_raw_response"] = result.get("raw_response", "")
    item["wrong_guess_replacement_response_time_sec"] = result.get(
        "response_time_sec", ""
    )
    item["wrong_guess_replacement_attempts"] = result.get("attempts", "")
    _sync_reflection_to_round_summary(item)
    log_event(
        "wrong_guess_replacements_recorded",
        {
            "actor": "ai",
            "wrong_guesses": item.get("neutral_guesses", []),
            "replacement_cards": item.get("wrong_guess_replacements", []),
            "required_count": len(item.get("neutral_guesses", [])),
        },
        turn_number=item.get("turn", ""),
    )


def _guess_outcome_summary(item):
    """Plain-language, condition-independent result of this turn's guesses.

    Whether a click hit a target/neutral/bomb is basic game feedback (a
    Codenames-style board always reveals a card's true color the instant
    it's picked) -- it must show regardless of _share_explanations(),
    which only gates the AI's *reasoning* text, not the factual outcome.
    Without this, a guesser whose condition doesn't share explanations saw
    nothing here confirming whether their guess was even right, and had to
    go check History afterward to find out.
    """
    outcome = item.get("outcome")
    guesses = item.get("guesses", [])
    correct = item.get("correct_guesses", [])
    neutral = item.get("neutral_guesses", [])
    bomb = item.get("bomb_guesses", [])
    if outcome == "bomb":
        return "error", f"Bomb hit: {', '.join(bomb)}. The round has ended."
    if outcome in ("skip", "partial_skip") or not guesses:
        return "info", "Skipped — no cards were guessed this turn."
    if outcome == "correct" and not neutral:
        was_were = "was" if len(correct) == 1 else "were"
        return "success", f"Correct: {', '.join(correct)} {was_were} the target."
    if correct and neutral:
        return "warning", (
            f"Partly right: {', '.join(correct)} correct, {', '.join(neutral)} neutral (not a target)."
        )
    # Red is kept for a bomb hit only; a wrong neutral guess costs nothing
    # beyond the turn, so it is shown as a warning.
    wrong = neutral or guesses
    if len(wrong) == 1:
        return "warning", f"Wrong: {wrong[0]} was a neutral card, not a target."
    return "warning", f"Wrong: {', '.join(wrong)} were neutral cards, not targets."


def _turn_points_message(item):
    """Player-facing points feedback for this turn: 2 points for a guess
    matching the clue-giver's own intended card, 1 for any other valid
    target, 0 otherwise -- worded without ever telling a guesser which
    specific card was intended (an exact match is only named as such after
    the fact, never predicted for them)."""
    turn_points = item.get("turn_points", 0)
    correct = item.get("correct_guesses", [])
    if item.get("outcome") == "bomb" or not correct:
        return ""
    intended = item.get("intended_targets", [])
    exact_only = len(correct) == 1 and correct[0] in intended
    other_only = len(correct) == 1 and correct[0] not in intended
    point_word = "point" if turn_points == 1 else "points"
    if exact_only:
        return f"Great match! +{turn_points} {point_word}"
    if other_only:
        return f"Valid target found! +{turn_points} {point_word}"
    return f"+{turn_points} {point_word} this turn"


def _render_live_history_sidebar(history, share_explanations, show_ai_intended=False):
    """Clue/guess history (with each turn's rationale/explanation already
    part of render_interaction_history's output) as Streamlit's native
    sidebar, so it's always reachable without scrolling the main column --
    persistent on desktop, tap-to-open on narrow screens, both handled by
    Streamlit itself. Every active-gameplay screen (clue-giving, guessing,
    the between-turns reflection step, the round summary) calls this with
    the same history so a participant never loses sight of what's happened
    so far, regardless of which role they're in or which screen they're on.

    Always visible, even before the first turn (showing "No hints or
    guesses yet."), so a participant sees it in the same place from the
    very start of a round instead of it appearing partway through."""
    with st.sidebar:
        st.markdown(
            f'<div class="panel-title section-gap">History · {len(history)} past turn(s)</div>',
            unsafe_allow_html=True,
        )
        render_interaction_history(
            history,
            show_ai_intended=show_ai_intended,
            share_explanations=share_explanations,
            show_title=False
        )


def _render_skip_interpretation_and_rationale(item):
    """The "Guesser thought" chips render_interaction_history shows in the
    History sidebar for a skip, repeated here inline in the "Turn result"
    popup itself -- so a participant doesn't have to glance away from the
    dialog to see the AI's interpretation of why the other side skipped.
    Gated identically (share_explanations, and skip_interpreted_cards only
    on an actual skip) so visibility stays symmetric between roles/
    conditions with the sidebar.

    Deliberately NOT repeating the "Why" row (the participant's own
    guess_rationale) here -- unlike "Guesser thought" (the AI's read on
    things), that text is always what THIS SAME participant just typed
    themselves moments earlier, so echoing it back in the very next popup
    is pure clutter, not new information. The History sidebar still shows
    it, for recalling past turns later."""
    if not _share_explanations():
        return
    is_skip = item.get("outcome") in ("skip", "partial_skip") or item.get("skipped")
    skip_interpreted_cards = item.get("skip_interpreted_cards", [])
    if not (is_skip and skip_interpreted_cards):
        return
    chips = "".join(
        f"<span class='history-chip'>{escape(word)}</span>"
        for word in skip_interpreted_cards
    )
    rows = [
        "<div class='history-detail'>"
        "<span class='history-detail-label'>Guesser thought</span>"
        f"<span class='history-chip-row'>{chips}</span>"
        "</div>"
    ]
    st.markdown(
        f"<div class='history-panel' style='margin-bottom:0.75rem;'>{''.join(rows)}</div>",
        unsafe_allow_html=True,
    )


# Not dismissible: Escape or the close button used to hide this mandatory
# step and leave a blank page with no way to continue the game.
@st.dialog("Turn result", dismissible=False)
def _turn_reflection_dialog(item, human_clue_giver, replacement_count):
    outcome_kind, outcome_message = _guess_outcome_summary(item)
    getattr(st, outcome_kind)(outcome_message)
    points_message = _turn_points_message(item)
    if points_message:
        st.caption(f"{points_message} · Round score so far: {compute_round_score()} pts")
    _render_skip_interpretation_and_rationale(item)
    ai_explanation = item.get("ai_explanation_sanitized") or item.get("ai_explanation", "")
    had_guesses = bool(item.get("guesses"))
    show_reflection_header = human_clue_giver or _share_explanations()
    if show_reflection_header:
        if not human_clue_giver and ai_explanation:
            header_body = escape(ai_explanation)
        elif had_guesses:
            # The radio question right below this card already asks the
            # specific thing ("After the guesses, how well do you think you
            # understood the AI?") -- a generic restatement here ("Rate the
            # shared understanding after the AI's guesses.") said the same
            # thing twice in a row with nothing new in between.
            header_body = ""
        elif human_clue_giver:
            header_body = "The AI didn't guess this turn — rate how well you think it understood your clue."
        else:
            header_body = "You didn't guess this turn — rate how well you understood the AI's clue."
        reflection_title = (
            "Shared-understanding rating"
            if human_clue_giver
            else "AI's clue explanation"
        )
        # The real AI-reasoning variant (adaptive condition, guesser role)
        # gets its own accent class -- it's the one message here actually
        # worth stopping to read, unlike the other branches' generic
        # self-rating prompt, so it shouldn't blend into the same neutral
        # card styling as everything else in this dialog.
        has_ai_explanation_class = (
            " has-ai-explanation" if not human_clue_giver and ai_explanation else ""
        )
        header_body_html = (
            f'<p class="subtle-text" style="margin:0;">{header_body}</p>' if header_body else ""
        )
        st.markdown(
            f'<div class="glass-card compact-card reflection-ai-explanation{has_ai_explanation_class} reflection-compact-head">'
            f'<div class="panel-title">{reflection_title}</div>'
            f"{header_body_html}"
            "</div>",
            unsafe_allow_html=True,
        )
    # A no-guess turn (full skip) has no completed exchange to judge *mutual*
    # understanding by -- asking "how well did you and the AI understand
    # EACH OTHER" here has no honest answer. Each role instead rates the one
    # thing it actually has a basis to judge: the clue-giver rates their own
    # guess at whether their clue landed (informed by the AI declining to
    # guess rather than guessing wrong); the guesser rates their own
    # comprehension of the clue they chose not to act on.
    # All three branches feed the SAME stored field
    # (human_perceived_understanding_rating) -- it is one column holding
    # answers to three different questions, disambiguated only by
    # reflection_source (human_clue_giver/ai_clue_giver) plus whether this
    # turn had any guesses at all. Analysis code must join on those two
    # fields to know which question a given value actually answers:
    #   had_guesses=True            -> perceived SHARED understanding after a
    #                                   completed exchange (either role)
    #   had_guesses=False, clue-giver -> did the AI understand MY clue
    #   had_guesses=False, guesser    -> did I understand the AI's clue
    if had_guesses:
        rating_question = "After the guesses, how well do you think you understood the AI?"
    elif human_clue_giver:
        rating_question = "How well do you think the AI understood your clue?"
    else:
        rating_question = "How well do you think you understood the AI's clue?"
    st.radio(
        rating_question,
        options=list(RATING_OPTIONS.keys()),
        index=None,
        format_func=lambda option: f"{option}",
        horizontal=True,
        key=f"reflection_rating_{st.session_state.round}_{item.get('turn')}",
    )
    render_rating_scale_endpoints()
    replacement_key = (
        f"wrong_guess_replacements_{st.session_state.round}_{item.get('turn')}"
    )
    replacement_cards = []
    if replacement_count:
        replacement_cards = st.multiselect(
            (
                f"If you could choose {replacement_count} other card"
                f"{'s' if replacement_count != 1 else ''}, which would you choose?"
            ),
            options=[
                word
                for word in st.session_state.board
                if word not in st.session_state.guesses
            ],
            max_selections=replacement_count,
            placeholder=f"Select exactly {replacement_count} replacement card(s)...",
            key=replacement_key,
            help=(
                "Choose the cards you would have selected instead of your "
                "wrong card(s)."
            ),
        )

    if st.button("Continue", type="primary", use_container_width=True):
        understood_ai_rating = st.session_state[
            f"reflection_rating_{st.session_state.round}_{item.get('turn')}"
        ]
        if understood_ai_rating is None:
            st.error("Please select a rating before continuing.")
            return
        if replacement_count and len(replacement_cards) != replacement_count:
            st.error(
                f"Please select exactly {replacement_count} replacement card(s)."
            )
            return
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

        if replacement_count:
            item["wrong_guess_replacements"] = list(replacement_cards)
            item["wrong_guess_replacement_actor"] = "human"
            item["wrong_guess_replacement_raw_response"] = ""
            item["wrong_guess_replacement_response_time_sec"] = ""
            item["wrong_guess_replacement_attempts"] = ""
            log_event(
                "wrong_guess_replacements_recorded",
                {
                    "actor": "human",
                    "wrong_guesses": item.get("neutral_guesses", []),
                    "replacement_cards": replacement_cards,
                    "required_count": replacement_count,
                },
                turn_number=item.get("turn", ""),
            )
        _save_turn_reflection(item, understood_ai_rating, relationship_type, explanation)
        log_event(
            "reflection_submitted",
            {"reflection_source": item.get("reflection_source", "")},
            turn_number=item.get("turn", ""),
        )
        st.rerun()


def _show_pending_turn_reflection_dialog(item):
    """The actual "Turn result" popup for a resolved turn -- factored out of
    render_turn_reflection() so a skip's own confirmation dialog (see the
    skip-processing blocks in screen_human_guesser/screen_tutorial) can show
    this SAME dialog immediately in the same rerun that recorded the skip,
    instead of closing its own dialog and waiting for the *next* rerun's
    top-of-function check to open a second, separate-looking popup right
    after it."""
    human_clue_giver = item.get("clue_giver") == "human"
    round_ended_by_bomb = bool(
        item.get("bomb_hit") or st.session_state.get("round_bomb_hit", False)
    )
    replacement_count = (
        len(item.get("neutral_guesses", []))
        if item.get("guesser") == "human" and not round_ended_by_bomb
        else 0
    )
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
    _turn_reflection_dialog(item, human_clue_giver, replacement_count)


def _finish_deferred_ai_work(item):
    """The AI calls that belong to an already-recorded turn: the AI clue-
    giver's explanation and the AI guesser's replacement cards. They run here,
    on the fresh page that follows the recording, instead of inside the run
    that recorded the turn -- a slow call there kept the old clue and timer on
    screen, and a rerun landing during it cut that run short. Each is
    attempted once per turn."""
    if item.get("clue_giver") == "ai" and not item.get("ai_explanation_attempted"):
        with st.spinner("AI is summarizing its clue..."):
            _attach_ai_explanation(item)
        item["ai_explanation_attempted"] = True
    if item.get("guesser") == "ai" and not item.get("wrong_guess_replacements_attempted"):
        if item.get("neutral_guesses") and not item.get("bomb_hit"):
            with st.spinner("AI is choosing the cards it would pick instead..."):
                _attach_ai_wrong_guess_replacements(item)
        item["wrong_guess_replacements_attempted"] = True


def _drop_stale_clue():
    """A clue that already appears in this round's History has been
    resolved: neither the AI nor the participant may reuse a clue within a
    round, so if one is still active it is left over from a run that was cut
    short before it could clear it. Clear it (and its timer) instead of
    letting it be guessed or timed out a second time."""
    if st.session_state.get("round_finished"):
        # The round's last clue is deliberately kept when the round ends,
        # and a finished round has no timer left to expire.
        return False
    hint = str(st.session_state.get("hint") or "").strip().lower()
    if hint and hint in previous_hints(st.session_state.get("interaction_history", [])):
        _clear_current_clue()
        log_event("stale_clue_cleared", {"clue": hint}, turn_number="")
        return True
    return False


def render_turn_reflection():
    item = _current_pending_reflection_item()
    if not item:
        return False
    _finish_deferred_ai_work(item)
    render_top_status()
    if item.get("clue_giver") == "human":
        # The clue-giver's board behind the "Turn result" dialog: only the
        # cards selected so far stay visible, the rest are blurred, so this
        # untimed step can't be used to plan the next clue.
        with st.container(border=True):
            st.markdown('<div class="panel-title">Your secret board</div>', unsafe_allow_html=True)
            render_board(
                st.session_state.board,
                st.session_state.word_roles,
                guesses=st.session_state.guesses,
                reveal_all=True,
                blur_unguessed=True,
            )
    _show_pending_turn_reflection_dialog(item)

    _render_live_history_sidebar(
        st.session_state.interaction_history,
        _share_explanations(),
    )
    return True


def _save_ai_guess_turn(review, repair_context):
    """Record the AI's guess on a human clue the moment it arrives, so the
    status bar updates at once and the "Turn result" dialog follows directly.
    (There used to be a separate, untimed "Save this turn" review step here,
    which left the status bar stale and gave the clue-giver unlimited time
    with the full board before the next clue's timer started.)"""
    st.session_state.last_ai_guesses = review.get("guesses", [])
    record_interaction(
        review.get("hint", ""),
        review.get("hint_number", 1),
        review.get("guesses", []),
        review.get("intended_targets", []),
        expected_guesses=review.get("expected_guesses", []),
        guess_rationale=review.get("guess_rationale", ""),
        hint_explanation=review.get("hint_explanation", ""),
        human_expected_ai_understanding_rating=review.get("rating_before"),
        hint_time_sec=review.get("hint_time_sec"),
        guess_raw_response=review.get("guess_raw_response", ""),
        guess_time_sec=review.get("guess_time_sec"),
        guess_response_time_sec=review.get("guess_response_time_sec"),
        partial_skip=review.get("partial_skip", False),
        skipped_by="ai" if review.get("partial_skip") else None,
        skip_interpreted_cards=review.get("skip_interpreted_cards", []),
        repair_context=repair_context,
        clue_timer_started_at=review.get("clue_timer_started_at"),
        timer_duration_seconds=review.get("timer_duration_seconds"),
        human_explanation_raw=review.get("human_explanation_raw", ""),
        human_explanation_is_valid=review.get("human_explanation_is_valid"),
        human_explanation_source=review.get("human_explanation_source", ""),
        human_explanation_collected_at=review.get("human_explanation_collected_at", ""),
    )
    recorded_item = st.session_state.interaction_history[-1]
    if review.get("partial_skip"):
        log_event(
            "partial_skip_used",
            {
                "skipped_by": "ai",
                "completed_turn_number": recorded_item.get("completed_turn_number", ""),
                "skip_number": recorded_item.get("skip_number", ""),
                "completed_guesses": len(review.get("guesses", [])),
                "skipped_guesses": max(
                    0, review.get("hint_number", 1) - len(review.get("guesses", []))
                ),
                "guessed_cards": review.get("guesses", []),
                "skip_interpreted_cards": review.get("skip_interpreted_cards", []),
            },
            turn_number=recorded_item.get("turn", ""),
        )
    # Clear the clue before the AI-replacements call below (a real API
    # request), so an interrupted rerun lands on a fresh clue form.
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


def screen_human_clue():
    # Invisible marker: tints --color-primary amber for this whole screen
    # (see app.css's role accent switch) -- purely cosmetic, no logic reads it.
    st.markdown('<div class="role-marker-clue"></div>', unsafe_allow_html=True)
    _drop_stale_clue()
    if st.session_state.get("pending_reflection_turn"):
        if render_turn_reflection():
            return

    if st.session_state.round_finished:
        screen_round_summary()
        return

    render_top_status()

    clue_giver_timeout_notice = st.session_state.pop("clue_giver_timeout_notice", "")
    if clue_giver_timeout_notice == "free":
        st.warning(
            "Time expired. This is a one-time grace period, so it didn't cost "
            "anything — please submit your clue before the timer runs out from now on."
        )
    elif clue_giver_timeout_notice == "interaction":
        st.warning(
            "Time expired. That used one of this round's 3 interactions."
        )
    if st.session_state.pop("final_guess_warning_notice", False):
        st.error(
            f"Both skips are used. You have {FINAL_GUESS_TIMER_SECONDS} seconds to submit "
            "your clue or the round ends automatically."
        )

    repair_context = _pending_human_clue_repair_context()
    if repair_context:
        # A nudge, never a rule: it names only the participant's own intended
        # cards (which they already know) and nothing about how the AI read
        # the skipped clue, so it can't give anything away.
        unresolved_cards = ", ".join(repair_context["unresolved_targets"])
        st.info(
            f"The AI skipped your last clue, so your intended card(s) {unresolved_cards} "
            "are still hidden. You may want to try a new clue for them, but you are free "
            "to choose any target cards."
        )
    with st.container(border=True):
        st.markdown('<div class="panel-title">Your secret board</div>', unsafe_allow_html=True)
        # Reserved here so the countdown ends up directly beside the board
        # instead of far below it, past the whole clue-composition form --
        # but actually filled much further down, only once the timer's own
        # state (start/consume-timeout) has run in its original place in
        # the function. st.empty() keeps the *visual* slot at this
        # position regardless of how much unrelated content renders in
        # between; see the fill site below for why that state logic
        # itself isn't moved up here too. A dedicated key (not the shared
        # timer_skip_stack used on the guesser/tutorial screens) since
        # this one sits in normal flow beside the narrower board rather
        # than fixed to the viewport.
        board_col, board_timer_col = st.columns([1.7, 1])
        with board_timer_col:
            with st.container(key="board_adjacent_timer"):
                board_timer_placeholder = st.empty()
        with board_col:
            with st.container(key="human_clue_board_wrap"):
                render_board(
                    st.session_state.board,
                    st.session_state.word_roles,
                    guesses=st.session_state.guesses,
                    reveal_all=True,
                )
                render_board_legend()

    with st.container(key="clue_form_steps"):
        st.markdown(
            """
            <div class="panel-title section-gap">Enter your clue for the AI guesser</div>
            """,
            unsafe_allow_html=True,
        )
        _ensure_timer("current_hint_start_time")
        if participant_decision_time_remaining() is None:
            start_participant_decision_timer(
                st.session_state.get("current_hint_start_time") or _now_iso(),
                duration_seconds=CLUE_GIVER_TIMER_SECONDS,
            )
            st.session_state.current_turn_start_time = st.session_state.get(
                "current_hint_start_time", ""
            )
        if _consume_human_clue_timeout():
            st.rerun()
        with board_timer_placeholder:
            # st.empty() can only hold ONE element -- render_clue_timer writes
            # more than one (the pill markdown, then the ticking component), so
            # without this inner container every write but the last silently
            # replaced the one before it and the pill never actually appeared.
            # Nesting a plain container gives the placeholder a single child
            # that can itself hold multiple elements.
            with st.container():
                render_clue_timer(participant_decision_time_remaining(), pinned=False)

        with st.container(border=True, key="clue_hint_container"):
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
                    key=f"human_hint_{st.session_state.round}_{_current_action_index()}",
                )
            with count_col:
                hint_number = st.selectbox(
                    "Count",
                    options=list(range(1, max_hint_count + 1)),
                    index=min(max(0, st.session_state.hint_number - 1), max_hint_count - 1),
                    label_visibility="collapsed",
                    key=f"clue_count_{st.session_state.round}_{_current_action_index()}",
                )

        found_targets = set(st.session_state.get("found_targets", []))
        remaining_targets = [
            word for word in st.session_state.target_words if word not in found_targets
        ]
        selected_count = int(hint_number)
        st.session_state.hint_targets = [
            word for word in st.session_state.get("hint_targets", []) if word in remaining_targets
        ][:selected_count]
        with st.container(key="clue_targets_container"):
            render_hint_target_selector(
                remaining_targets,
                st.session_state.hint_targets,
                selected_count,
            )
        expected_guess_key = f"expected_guesses_{st.session_state.round}_{_current_action_index()}"
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
        with st.container(key="clue_expected_container"):
            st.multiselect(
                "Expected AI guesses",
                options=available_guess_options,
                max_selections=selected_count,
                placeholder=f"Choose {selected_count} card(s)...",
                label_visibility="collapsed",
                key=expected_guess_key,
            )
        st.session_state.hint_expected_guesses = st.session_state.get(expected_guess_key, [])

        with st.container(border=True, key="before_ai_guess_panel"):
            prompt_col, rating_col = st.columns([1.45, 1])
            with prompt_col:
                st.markdown(
                    """
                    <div class="panel-title section-gap">Before AI guesses</div>
                    <p class="subtle-text before-ai-question">How well do you expect the AI understood your clue?</p>
                    """,
                    unsafe_allow_html=True,
                )
            with rating_col:
                with st.container(key="clue_rating_container"):
                    rating_before = st.radio(
                        "Before AI guess rating",
                        options=list(RATING_OPTIONS.keys()),
                        index=None,
                        format_func=lambda option: f"{option}",
                        horizontal=True,
                        label_visibility="collapsed",
                        key=f"before_ai_guess_rating_{st.session_state.round}_{_current_action_index()}",
                    )
                    render_rating_scale_endpoints()
        st.session_state.human_expected_ai_understanding_rating = rating_before

        general_link_key = (
            f"pre_ai_general_link_{st.session_state.round}_"
            f"{_current_action_index()}"
        )
        st.markdown(
            """
            <div class="panel-title section-gap">General link</div>
            """,
            unsafe_allow_html=True,
        )
        with st.container(key="clue_general_link_container"):
            general_link = st.text_area(
                "General link (3–20 English words, no card names)",
                max_chars=150,
                placeholder="Example: Both ideas connect through luck and success.",
                key=general_link_key,
            )
            st.caption("Press Ctrl+Enter or click outside this box to save it before continuing.")
    general_link_is_valid, general_link_blocked_reason = validate_general_link(
        general_link, st.session_state.get("board", [])
    )

    hint_is_valid, hint_error_message = validate_human_hint_with_history(
        hint,
        st.session_state.board,
        st.session_state.interaction_history,
        st.session_state.used_hints,
    )
    targets_ready = len(st.session_state.hint_targets) == selected_count
    predicted_ready = len(st.session_state.hint_expected_guesses) == selected_count
    rating_ready = rating_before is not None
    turn_ready = (
        hint_is_valid
        and targets_ready
        and predicted_ready
        and rating_ready
        and general_link_is_valid
    )

    clue_submit_attempted_key = (
        f"clue_form_submit_attempted_{st.session_state.round}_{_current_action_index()}"
    )
    if st.session_state.get(clue_submit_attempted_key):
        # A single marker, positioned wherever in the DOM, carrying one class
        # per currently-invalid field -- :has() reaches from it to each
        # field's own keyed container regardless of how deeply Streamlit
        # nests either one, so this doesn't depend on the two being adjacent
        # siblings (see the .let-ai-guess-marker fix earlier this session for
        # why a sibling-based version of this would silently match nothing).
        invalid_field_classes = " ".join(
            css_class
            for ready, css_class in [
                (hint_is_valid, "invalid-hint"),
                (targets_ready, "invalid-targets"),
                (predicted_ready, "invalid-expected"),
                (rating_ready, "invalid-rating"),
                (general_link_is_valid, "invalid-link"),
            ]
            if not ready
        )
        if invalid_field_classes:
            st.markdown(
                f"<div class='turn-invalid-marker {invalid_field_classes}'></div>",
                unsafe_allow_html=True,
            )

    st.markdown("<div class='let-ai-guess-marker'></div>", unsafe_allow_html=True)
    if st.button(
        "Let AI Guess",
        type="primary",
        use_container_width=True,
    ):
        st.session_state[clue_submit_attempted_key] = True
        if not turn_ready:
            problems = []
            if not hint_is_valid:
                problems.append(hint_error_message)
            if not targets_ready:
                problems.append(f"Please select exactly {selected_count} target card(s) for this clue.")
            if not predicted_ready:
                problems.append(f"Please select exactly {selected_count} card(s) you think the AI will choose.")
            if not rating_ready:
                problems.append("Please select how well you expect the AI understood your clue.")
            if not general_link_is_valid:
                problems.append(_general_link_error(general_link_blocked_reason))
            _clue_form_errors_dialog(problems)
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
            submitted_general_link = general_link.strip()
            clue_timer_started_at = st.session_state.get("clue_timer_started_at", "")
            timer_duration_seconds = st.session_state.get(
                "clue_timer_duration_seconds", CLUE_TIMER_SECONDS
            )
            log_event(
                "clue_submitted",
                {
                    "clue": st.session_state.hint,
                    "clue_number": st.session_state.hint_number,
                    "intended_cards": intended_targets,
                    "expected_guess_cards": expected_guess_cards,
                    "human_expected_ai_understanding_rating": rating_before,
                    "human_explanation_raw": submitted_general_link,
                    "human_explanation_is_valid": True,
                    "human_explanation_source": "pre_ai_human_clue_form",
                    "human_explanation_collected_at": hint_end_time,
                },
                turn_number=_next_action_number(),
            )
            board_timer_placeholder.empty()
            clear_participant_decision_timer()
            log_event("ai_guess_started", {"clue": st.session_state.hint}, turn_number=_next_action_number())
            guess_start_time = _now_iso()
            st.session_state.current_guess_start_time = guess_start_time
            # The button sits at the bottom of a long form, so a spinner shown
            # in place was often below the fold; this container is styled
            # (static/app.css) to show it in the middle of the screen instead.
            with st.container(key="ai_guess_thinking"), st.spinner("AI is thinking..."):
                guess_result = ai_guess(
                    st.session_state.board,
                    st.session_state.hint,
                    st.session_state.hint_number,
                    st.session_state.interaction_history,
                    st.session_state.guesses,
                    st.session_state.ai_round_summaries,
                    MAX_SKIPS_PER_ROUND - st.session_state.get("round_skips", 0),
                    can_skip_current_clue(),
                    condition=st.session_state.get("condition", DEFAULT_CONDITION),
                )
            guess_end_time = _now_iso()
            guess_time_sec = _seconds_between(guess_start_time, guess_end_time)

            action = guess_result.get("action", "guess")
            raw_ai_response = str(guess_result.get("raw_response", "") or "")
            if raw_ai_response.startswith("<api_error:"):
                log_event(
                    "ai_api_failed",
                    {
                        "error": raw_ai_response,
                        "technical_timeout_seconds": AI_API_TIMEOUT_SECONDS,
                        "human_timeout": False,
                    },
                    turn_number=_next_action_number(),
                )
            log_event(
                "ai_guess_completed",
                {
                    "action": action,
                    "guesses": guess_result.get("guesses", []),
                    "skip_interpreted_cards": guess_result.get(
                        "skip_interpreted_cards", []
                    ),
                    "guess_rationale": guess_result.get("guess_rationale", ""),
                    "raw_response": guess_result.get("raw_response", ""),
                },
                turn_number=_next_action_number(),
            )
            if action == "skip":
                record_skip(
                    st.session_state.hint,
                    st.session_state.hint_number,
                    intended_targets,
                    expected_guess_cards,
                    guess_rationale=guess_result.get("guess_rationale", ""),
                    hint_explanation=st.session_state.get("hint_explanation", ""),
                    hint_time_sec=hint_time_sec,
                    skipped_by="ai",
                    skip_interpreted_cards=guess_result.get(
                        "skip_interpreted_cards", []
                    ),
                    repair_context=repair_context,
                    guess_raw_response=guess_result.get("raw_response", ""),
                    guess_time_sec=guess_time_sec,
                    guess_response_time_sec=guess_result.get("response_time_sec"),
                    clue_timer_started_at=clue_timer_started_at,
                    timer_duration_seconds=timer_duration_seconds,
                    human_explanation_raw=submitted_general_link,
                    human_explanation_is_valid=True,
                    human_explanation_source="pre_ai_human_clue_form",
                    human_explanation_collected_at=hint_end_time,
                )
                recorded_item = st.session_state.interaction_history[-1]
                log_event(
                    "skip_used",
                    {
                        "skipped_by": "ai",
                        "completed_turn_number": recorded_item.get("completed_turn_number", ""),
                        "skip_number": recorded_item.get("skip_number", ""),
                        "skip_interpreted_cards": guess_result.get(
                            "skip_interpreted_cards", []
                        ),
                    },
                    turn_number=recorded_item.get("turn", ""),
                )
                _clear_current_clue()
                st.info("AI chose not to risk this clue. One skip was used; please give the next clue.")
                st.rerun()
            else:
                review = {
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
                    "partial_skip": action == "partial_skip",
                    "skip_interpreted_cards": guess_result.get(
                        "skip_interpreted_cards", []
                    ),
                    "clue_timer_started_at": clue_timer_started_at,
                    "timer_duration_seconds": timer_duration_seconds,
                    "human_explanation_raw": submitted_general_link,
                    "human_explanation_is_valid": True,
                    "human_explanation_source": "pre_ai_human_clue_form",
                    "human_explanation_collected_at": hint_end_time,
                }
                with st.spinner("Saving the AI's guess..."):
                    _save_ai_guess_turn(review, repair_context)
                st.rerun()

    _render_live_history_sidebar(
        st.session_state.interaction_history,
        _share_explanations(),
    )


def screen_human_guesser():
    # Invisible marker: tints --color-primary teal for this whole screen
    # (see app.css's role accent switch) -- purely cosmetic, no logic reads it.
    st.markdown('<div class="role-marker-guess"></div>', unsafe_allow_html=True)
    _drop_stale_clue()
    if st.session_state.get("pending_reflection_turn"):
        if render_turn_reflection():
            return

    if st.session_state.round_finished:
        screen_round_summary()
        return

    render_top_status()

    if st.session_state.pop("last_timeout_notice", False):
        st.warning("Time expired. That used one of your skips.")
    if st.session_state.pop("final_guess_warning_notice", False):
        st.error(
            f"Both skips are used. You have {FINAL_GUESS_TIMER_SECONDS} seconds to submit "
            "a guess or the round ends automatically."
        )

    if _consume_human_guess_timeout():
        st.rerun()

    remaining_time = None
    if not st.session_state.hint:
        # First turn of every AI-clue round (a new board): wait for the
        # participant to ask, so they can study the 16 new cards before the
        # guessing timer starts. Later turns of the round fetch the clue
        # straight after the previous turn's result. (Keyed on "no turn yet
        # this round" rather than "round 1": participants who start as
        # clue-giver meet their first AI clue in round 2 and must get the
        # same pause.)
        if not st.session_state.get("interaction_history"):
            st.markdown(
                """
                <div class="glass-card compact-card section-gap">
                    <div class="panel-title">Clue</div>
                    <p class="subtle-text" style="margin:0;"><strong>Please look at the cards on the board carefully before asking for a clue.</strong> Ask the AI for a clue when you are ready.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Ask AI for a clue", type="primary", use_container_width=True):
                if _generate_and_store_ai_hint():
                    st.rerun()
                return
        else:
            if _generate_and_store_ai_hint():
                st.rerun()
            if st.button("Try generating the AI clue again", use_container_width=True):
                st.rerun()
            # Keep the History panel on screen while the clue is retried.
            _render_live_history_sidebar(
                st.session_state.interaction_history,
                _share_explanations(),
            )
            return
    else:
        remaining_time = participant_decision_time_remaining()
        render_hint_panel(
            st.session_state.hint,
            st.session_state.hint_number,
            st.session_state.previous_hint,
        )
        with st.container(key="guesser_rationale_panel"):
            guess_rationale, rationale_is_valid = _render_guess_rationale_input()
        guess_gate_ready = rationale_is_valid

    with st.container(border=True):
        st.markdown('<div class="panel-title">Board</div>', unsafe_allow_html=True)
        # Before any clue exists yet, there is no timer (or skip button --
        # both need a hint first) to show -- giving the board the full width
        # instead of a second column avoids an empty card sitting next to it
        # with nothing inside.
        if not st.session_state.hint:
            board_col = st.container()
            skip_cluster_placeholder = None
        else:
            board_col, board_timer_col = st.columns([1.7, 1])
            # Timer and skip button stacked together, in normal flow beside the
            # (narrower) board rather than fixed to the viewport -- same
            # reasoning and pattern as screen_human_clue's
            # board_adjacent_timer. The skip placeholder is reserved here so
            # the button ends up right under the timer, but is filled later
            # once its own state (guess_gate_ready, remaining_guess_slots) is
            # known.
            with board_timer_col:
                with st.container(key="guesser_timer_skip_stack"):
                    if remaining_time is not None:
                        render_clue_timer(remaining_time, pinned=False)
                    skip_cluster_placeholder = st.empty()
        with board_col:
            with st.container(key="human_guesser_board_wrap"):
                if not st.session_state.hint:
                    render_board(
                        st.session_state.board,
                        st.session_state.word_roles,
                        guesses=st.session_state.guesses + st.session_state.pending_guesses,
                        reveal_all=False,
                    )
                else:
                    render_board_lock_note(
                        "Add your reasoning above to start guessing or skip.",
                        visible=not guess_gate_ready,
                    )
                    clicked = render_board(
                        st.session_state.board,
                        st.session_state.word_roles,
                        guesses=st.session_state.guesses + st.session_state.pending_guesses,
                        reveal_all=False,
                        # Always clickable; the rationale is checked on the
                        # click itself (just below). Locking the cards until
                        # the rationale was saved cost an extra click: the
                        # first click only saved the text (by leaving the box)
                        # and turned the cards into buttons, so it never
                        # selected the card.
                        clickable=True,
                        max_clicks=st.session_state.hint_number + len(st.session_state.guesses),
                    )
                    if clicked and not rationale_is_valid:
                        rationale_text = st.session_state.get("current_guess_rationale", "")
                        _, rationale_reason = validate_guess_rationale(
                            rationale_text,
                            st.session_state.get("board", []),
                        )
                        st.error(_guess_rationale_error(rationale_reason))
                    elif clicked:
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
                                guess_time_sec=guess_time_sec,
                                repair_context=pending_meta.get("repair_context"),
                            )
                            log_event(
                                "human_guess_submitted",
                                {
                                    "guessed_cards": submitted_guesses,
                                    "guess_rationale": guess_rationale,
                                },
                                turn_number=st.session_state.round_interactions,
                            )
                            # Clear the turn's state BEFORE the AI-explanation call
                            # below (a real, occasionally slow API request). The
                            # clue timer's autorefresh can interrupt an in-flight
                            # rerun -- and any code after the interruption point
                            # never runs -- so clearing state first means a
                            # collision here only costs this turn's AI explanation,
                            # not a screen stuck showing the old hint and
                            # already-submitted guesses, which looks exactly like
                            # "the AI repeated its previous clue and everything is
                            # locked."
                            st.session_state.pending_guesses = []
                            st.session_state.current_guess_rationale = ""
                            st.session_state.current_hint_start_time = ""
                            st.session_state.current_guess_start_time = ""
                            st.session_state.final_guess_deadline_active = False
                            if not st.session_state.round_finished:
                                st.session_state.previous_hint = st.session_state.hint
                                st.session_state.hint = ""
                                st.session_state.hint_number = 1
                                st.session_state.hint_targets = []
                                st.session_state.hint_expected_guesses = []
                                st.session_state.hint_explanation = ""
                            st.session_state.pending_hint_meta = None
                            clear_participant_decision_timer()
                            # Rerun straight away: the next run opens the
                            # "Turn result" dialog on a fresh page and only
                            # then fetches the AI's explanation (see
                            # _finish_deferred_ai_work), so the old clue,
                            # board and timer never linger on screen.
                            st.rerun()
                        else:
                            # More cards to pick: the board above was drawn
                            # before this click was handled, so rerun to show
                            # the card as selected right away. Without this
                            # it only appeared on the next click, which read
                            # as "it takes two or three clicks".
                            st.rerun()

    if st.session_state.hint:
        remaining_guess_slots = (
            int(st.session_state.hint_number)
            - len(st.session_state.pending_guesses)
        )
        # Rendered into the placeholder reserved next to the timer above --
        # only the button moves there; the click-handling logic below stays
        # in its original place and order (st.button()'s return value is
        # just a bool, so where it's checked doesn't matter). The card
        # -interpretation picker used to sit inline here too, but that made
        # this sticky cluster permanently tall -- it now opens as a dialog
        # only once the participant has actually chosen to skip.
        # Once both skips are used there's nothing left to offer, so the
        # button disappears entirely instead of sitting there disabled --
        # the "Skips used" stat in the status bar above already shows why.
        # The button stays enabled even before the rationale is saved, and
        # the rationale is checked on the click -- same reason as the board
        # cards: a disabled button needed one click to save the text and a
        # second to skip.
        if can_skip_current_clue():
            with skip_cluster_placeholder:
                with st.container():
                    if not guess_gate_ready:
                        st.caption("Add your reasoning above before you can skip too.")
                    st.markdown("<div class='skip-button-marker'></div>", unsafe_allow_html=True)
                    if st.button("Skip", use_container_width=True):
                        if guess_gate_ready:
                            st.session_state.guesser_skip_dialog_open = True
                            st.rerun()
                        _, rationale_reason = validate_guess_rationale(
                            st.session_state.get("current_guess_rationale", ""),
                            st.session_state.get("board", []),
                        )
                        st.error(_guess_rationale_error(rationale_reason))
        if st.session_state.get("guesser_skip_dialog_open") and can_skip_current_clue():
            unavailable_cards = set(st.session_state.guesses).union(
                st.session_state.pending_guesses
            )
            skip_options = [
                word for word in st.session_state.board if word not in unavailable_cards
            ]
            _skip_interpretation_dialog(remaining_guess_slots, skip_options)
        skip_button_clicked = st.session_state.pop("guesser_skip_confirmed", False)
        skip_interpretation = (
            st.session_state.pop("guesser_skip_selected_cards", [])
            if skip_button_clicked
            else []
        )
        if skip_button_clicked:
            pending_meta = st.session_state.get("pending_hint_meta") or {}
            if len(skip_interpretation) != remaining_guess_slots:
                st.error(
                    f"Please select exactly {remaining_guess_slots} card(s) before skipping."
                )
            elif st.session_state.pending_guesses and not rationale_is_valid:
                rationale_text = st.session_state.get("current_guess_rationale", "")
                _, rationale_reason = validate_guess_rationale(
                    rationale_text,
                    st.session_state.get("board", []),
                )
                st.error(_guess_rationale_error(rationale_reason))
            else:
                submitted_guesses = list(st.session_state.pending_guesses)
                common = {
                    "guess_rationale": guess_rationale if rationale_is_valid else "",
                    "hint_explanation": st.session_state.get("hint_explanation", ""),
                    "hint_raw_response": pending_meta.get("raw_response", ""),
                    "hint_time_sec": pending_meta.get("hint_time_sec"),
                    "hint_response_time_sec": pending_meta.get("response_time_sec"),
                    "hint_attempts": pending_meta.get("attempts"),
                    "guess_time_sec": _seconds_between(st.session_state.get("current_guess_start_time", "")),
                }
                if submitted_guesses:
                    record_interaction(
                        st.session_state.hint,
                        st.session_state.hint_number,
                        submitted_guesses,
                        st.session_state.hint_targets,
                        expected_guesses=st.session_state.get("hint_expected_guesses", []),
                        partial_skip=True,
                        skipped_by="human",
                        skip_interpreted_cards=skip_interpretation,
                        repair_context=pending_meta.get("repair_context"),
                        **common,
                    )
                    recorded_item = st.session_state.interaction_history[-1]
                    log_event(
                        "partial_skip_used",
                        {
                            "skipped_by": "human",
                            "completed_turn_number": recorded_item.get("completed_turn_number", ""),
                            "skip_number": recorded_item.get("skip_number", ""),
                            "completed_guesses": len(submitted_guesses),
                            "skipped_guesses": max(0, st.session_state.hint_number - len(submitted_guesses)),
                            "guessed_cards": submitted_guesses,
                            "skip_interpreted_cards": skip_interpretation,
                        },
                        turn_number=recorded_item.get("turn", ""),
                    )
                    _clear_current_clue()
                else:
                    record_skip(
                        st.session_state.hint,
                        st.session_state.hint_number,
                        st.session_state.hint_targets,
                        st.session_state.get("hint_expected_guesses", []),
                        skipped_by="human",
                        skip_interpreted_cards=skip_interpretation,
                        repair_context=pending_meta.get("repair_context"),
                        **common,
                    )
                    recorded_item = st.session_state.interaction_history[-1]
                    log_event(
                        "skip_used",
                        {
                            "skipped_by": "human",
                            "completed_turn_number": recorded_item.get("completed_turn_number", ""),
                            "skip_number": recorded_item.get("skip_number", ""),
                            "skip_interpreted_cards": skip_interpretation,
                        },
                        turn_number=recorded_item.get("turn", ""),
                    )
                    _clear_current_clue()
                # Rerun straight away (see the guess-completion branch): the
                # "Turn result" dialog and the AI's explanation follow on a
                # fresh page, so nothing from this clue stays on screen.
                st.rerun()
    _render_live_history_sidebar(
        st.session_state.interaction_history,
        _share_explanations(),
    )


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
        round_score = compute_round_score()
        round_star = bool(st.session_state.get("round_star", False))
        star_label = "&#11088; Star earned!" if round_star else "No star this round"
        timed_out_loss = st.session_state.get("round_end_reason") == "timeout_loss"
        outcome = "Bomb hit" if st.session_state.round_bomb_hit else (
            "Timed out" if timed_out_loss else (
                "All targets found" if st.session_state.round_success else "Max turns reached"
            )
        )

        if st.session_state.round_bomb_hit:
            st.error("Bomb hit. The round ended immediately — points already earned still count, but no star this round.")
        elif timed_out_loss:
            st.error(
                "Both skips were used and the final 30-second decision window ran out. "
                "The round ended automatically — no star this round."
            )

        st.markdown(
            f"""
            <div class="summary-stat"><strong>Guesses:</strong> {escape(guesses_text)}</div>
            <div class="summary-stat"><strong>Outcome:</strong> {escape(outcome)}</div>
            <div class="summary-stat"><strong>Points this round:</strong> {round_score}</div>
            <div class="summary-stat"><strong>{star_label}</strong></div>
            """,
            unsafe_allow_html=True,
        )
    _render_live_history_sidebar(
        st.session_state.interaction_history,
        _share_explanations(),
        show_ai_intended=True,
    )

    with action_col:
        if not st.session_state.get("ai_round_reflection"):
            def _generate_round_reflection():
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
                    condition=st.session_state.get("condition", DEFAULT_CONDITION),
                )
                update_current_round_summary()

            if _share_explanations():
                with st.spinner("AI is reflecting on this round..."):
                    _generate_round_reflection()
            else:
                # Baseline still collects the same AI reflection for analysis,
                # but must not reveal that process or its content to the user.
                _generate_round_reflection()

        if _share_explanations():
            # One paragraph per line: the reflection puts each clue, the
            # skip note and the suggestion on its own line.
            reflection_html = "".join(
                f'<p class="subtle-text" style="margin:0 0 0.45rem 0;">{escape(line)}</p>'
                for line in st.session_state.ai_round_reflection.splitlines()
                if line.strip()
            )
            st.markdown(
                f"""
                    <div class="glass-card compact-card">
                    <div class="panel-title">AI reflection</div>
                    {reflection_html}
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.session_state.human_round_feedback = st.text_area(
            "Your message to the AI for next rounds"
            if _share_explanations()
            else "Your end-of-round reflection",
            value=st.session_state.get("human_round_feedback", ""),
            placeholder=(
                "Tell the AI what you meant by your clue or how you interpreted its clue..."
                if _share_explanations()
                else "Describe what you meant by your clue or how you interpreted the AI clue..."
            ),
            key=f"human_round_feedback_{st.session_state.round}",
        )
        feedback_words = _word_count(st.session_state.human_round_feedback)
        st.caption(f"{feedback_words} / 200 words · English only")

        if st.button("Save round and continue", type="primary", use_container_width=True):
            problems = []
            if feedback_words < 3:
                problems.append("Please write at least 3 words in your end-of-round reflection.")
            if feedback_words > 200:
                problems.append("Please keep your message to 200 words or fewer.")
            if not _is_english_text(st.session_state.human_round_feedback):
                problems.append(ENGLISH_ONLY_ERROR)
            if problems:
                _round_summary_errors_dialog(problems)
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
                st.session_state.round_clue_giver_timeouts = 0
                st.session_state.final_guess_deadline_active = False
                st.session_state.hint = ""
                st.session_state.hint_number = 1
                st.session_state.hint_targets = []
                st.session_state.hint_explanation = ""
                st.session_state.previous_hint = None
                st.session_state.last_ai_guesses = []
                st.session_state.last_ai_hint = ""
                st.session_state.pending_hint_meta = None
                st.session_state.pending_reflection_turn = None
                st.session_state.ai_round_reflection = ""
                st.session_state.human_round_feedback = ""

            st.rerun()


def _study_completion_code():
    """Prolific's fixed study code when configured; otherwise (local runs,
    pilots outside Prolific) a per-session code derived from session_id."""
    return prolific_completion_code() or (
        str(st.session_state.get("session_id", "")).replace("-", "")[-8:].upper()
    )


def screen_game_over():
    player_name = _display_player_name()
    player_name_html = escape(player_name)
    total_score = st.session_state.get("score", 0)
    total_stars = st.session_state.get("total_stars_so_far", 0)
    final_medal = get_final_medal(total_score)
    if not st.session_state.get("session_completed_logged"):
        if not st.session_state.get("completion_code"):
            st.session_state.completion_code = _study_completion_code()
    if final_medal == "gold":
        title = "Gold team!"
        subtitle = f"Fantastic finish, {player_name_html}! Your team was sharp, fast, and beautifully in sync."
    elif final_medal == "silver":
        title = "Silver team!"
        subtitle = f"Great work, {player_name_html}! That was a confident run with strong clue-reading."
    elif final_medal == "bronze":
        title = "Bronze team!"
        subtitle = f"Nice work, {player_name_html}! You built a solid rhythm together."
    else:
        title = "Run finished"
        subtitle = f"{player_name_html}, you were close. A few more exact matches and this team can jump a medal."
    medal_label = FINAL_MEDAL_LABELS.get(final_medal, "No medal")

    st.markdown(
        f"""
        <div class="glass-card game-over-card celebration-card">
            <div class="celebration-medals">
                <span>{medal_label}</span>
            </div>
            <div class="panel-title">Final result</div>
            <h2 style="margin-top:0; margin-bottom:0.45rem;">{title}</h2>
            <p class="subtle-text" style="margin-bottom:0;">{subtitle}</p>
            <div class="final-score">Total score: {total_score} / {MAX_POSSIBLE_SESSION_SCORE}</div>
            <div class="score-tiers">10+ Bronze &middot; 20+ Silver &middot; 30+ Gold</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    col1.markdown(
        f"<div class='summary-stat'><strong>&#11088; Stars earned</strong><br>{total_stars} / {N_ROUNDS}</div>",
        unsafe_allow_html=True,
    )
    col2.markdown(
        f"<div class='summary-stat'><strong>Final medal</strong><br>{medal_label}</div>",
        unsafe_allow_html=True,
    )
    if not st.session_state.get("post_game_questionnaire_submitted"):
        with st.container(border=True, key="post_game_questionnaire_panel"):
            st.markdown(
                """
                <div class="panel-title">Final questions</div>
                <p class="subtle-text" style="margin-top:0;">Rate how much you agree with each statement: 1 = strongly disagree, 5 = strongly agree.</p>
                """,
                unsafe_allow_html=True,
            )
            answers = {}
            # The attention item sits mid-list so it reads like any other
            # statement; it is stored separately from the questionnaire.
            displayed_questions = (
                POST_GAME_QUESTIONS[:2]
                + [(ATTENTION_CHECK_POST_GAME_ID, ATTENTION_CHECK_POST_GAME_QUESTION)]
                + POST_GAME_QUESTIONS[2:]
            )
            for question_id, question_text in displayed_questions:
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
                    for question_id, question_text in displayed_questions
                    if answers.get(question_id) is None
                ]
                if missing:
                    _round_summary_errors_dialog(["Please answer all final questions before finishing."])
                    return
                st.session_state.post_game_questionnaire = {
                    question_id: int(answers[question_id])
                    for question_id, _ in POST_GAME_QUESTIONS
                }
                st.session_state.attention_check_post_game_answer = int(
                    answers[ATTENTION_CHECK_POST_GAME_ID]
                )
                st.session_state.post_game_questionnaire_submitted = True
                if not st.session_state.get("completion_code"):
                    st.session_state.completion_code = _study_completion_code()
                log_event(
                    "post_game_questionnaire_submitted",
                    st.session_state.post_game_questionnaire,
                    round_number="",
                    turn_number="",
                )
                # A private, structured self-report mirroring the human's
                # questionnaire, collected for research comparison only.
                # Never shown to the participant, regardless of condition.
                with st.spinner("Saving your answers..."):
                    st.session_state.ai_post_game_questionnaire = generate_ai_post_game_reflection(
                        st.session_state.get("ai_round_summaries", []),
                        condition=st.session_state.get("condition", DEFAULT_CONDITION),
                    )
                log_event(
                    "ai_post_game_questionnaire_generated",
                    st.session_state.ai_post_game_questionnaire,
                    round_number="",
                    turn_number="",
                )
                mark_session_progress("post_study_questionnaire")
                st.rerun()
        return

    if not st.session_state.get("debriefing_acknowledged"):
        with st.container(key="debriefing_document"):
            st.markdown(
                render_debriefing_document(
                    st.session_state.get("condition"),
                    st.session_state.get("completion_code"),
                ),
                unsafe_allow_html=True,
            )
        with st.container(border=True, key="debriefing_action_panel"):
            debriefing_read = st.checkbox(
                "I have read the debriefing information.",
                key="debriefing_read_confirmation",
            )
            if st.button(
                "Finish study",
                type="primary",
                use_container_width=True,
                disabled=not debriefing_read,
            ):
                st.session_state.debriefing_acknowledged = True
                st.session_state.debriefing_acknowledged_at = _now_iso()
                log_event(
                    "debriefing_acknowledged",
                    {},
                    round_number="",
                    turn_number="",
                )
                mark_session_progress("completed", completed=True)
                log_event(
                    "session_completed",
                    {
                        "final_total_score": total_score,
                        "final_star_count": total_stars,
                        "final_medal": final_medal,
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
    if remote_status == "db_failed":
        st.warning(
            f"Thank you, {player_name}. Your answers were recorded, but saving to the database failed: {remote_error}"
        )
    else:
        st.success(f"Thank you, {player_name}. Your answers and game data have been saved.")

    # The debriefing page (shown just before this one) is the only other
    # place the completion code appears -- a participant who clicks through
    # without copying it down there had no way to recover it once they
    # reached this final screen, which is the one they're actually looking
    # at when they go to paste the code into Prolific.
    st.markdown(
        f"""
        <div class="glass-card compact-card section-gap">
            <div class="panel-title">Your completion code</div>
            <p class="subtle-text" style="margin:0 0 0.4rem 0;">Enter this code on the platform where you found this study to confirm your participation:</p>
            <p style="font-size:1.4rem; font-weight:800; letter-spacing:0.08em; margin:0;">{escape(st.session_state.get("completion_code", ""))}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    complete_url = prolific_complete_url(st.session_state.get("completion_code", ""))
    if st.session_state.get("prolific_pid") and complete_url:
        st.link_button(
            "Return to Prolific to complete your submission",
            complete_url,
            type="primary",
            use_container_width=True,
        )
        st.caption("If the button does not work, copy the code above into Prolific.")
    else:
        st.caption("You may now close this browser tab.")
