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
    remaining_target_count,
    validate_human_hint_with_history,
)
from core.constants import (
    AI_API_TIMEOUT_SECONDS,
    MAX_INTERACTIONS_PER_ROUND,
    MAX_SKIPS_PER_ROUND,
    MAX_TEAM_SCORE,
    N_ROUNDS,
    TEAM_GOAL_SCORE,
    CLUE_TIMER_SECONDS,
    DEFAULT_CONDITION,
)
from core.game_logic import (
    can_skip_current_clue,
    clear_participant_decision_timer,
    participant_decision_timer_expired,
    participant_decision_time_remaining,
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
from core.validation import validate_general_link, validate_guess_rationale
from ui.components import (
    MEDAL_LABELS,
    RATING_OPTIONS,
    render_board,
    render_board_legend,
    render_board_lock_note,
    render_clue_timer,
    render_hint_panel,
    render_hint_target_selector,
    render_interaction_history,
    render_rating_scale_endpoints,
    render_round_chip,
    render_top_status,
)
from ui.game_guide import (
    CLUE_GIVER_INTRO,
    CLUE_GIVER_OUTRO,
    CLUE_GIVER_STEPS,
    GUIDE_OVERVIEW,
    GUIDE_REMINDERS,
    GUIDE_ROLE,
    GUIDE_SECTIONS,
)
from ui.study_documents import (
    CONSENT_CHECKLIST_ITEMS,
    INFORMATION_SHEET_CONTACT,
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


def screen_consent():
    with st.container(key="consent_document"):
        with st.container(key="consent_logos"):
            university_col, colaps_col = st.columns(2, gap="large", vertical_alignment="center")
            with university_col:
                st.image(str(ASSETS_DIR / "university_duisburg_essen.png"), width=190)
            with colaps_col:
                st.image(str(ASSETS_DIR / "colaps.png"), width=180)
        st.markdown(
            f"""
            <section class="information-hero">
                <div class="information-hero-copy">
                    <div class="information-eyebrow">RESEARCH STUDY</div>
                    <h1>Information Sheet for<br>Participation in Research</h1>
                    <p class="information-study-title">{INFORMATION_SHEET_TITLE}</p>
                    <div class="information-meta">
                        <div><strong>Shima Ghasempour</strong><br><a href="mailto:shima.ghasempoour-ardestani@stud.uni-due.de">shima.ghasempoour-ardestani@stud.uni-due.de</a></div>
                        <div><strong>Department of Human-centered Computing and Cognitive Science</strong></div>
                        <div><strong>September 2026</strong></div>
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
        st.markdown(
            f"""
            <section class="information-contact">
                <h2>Contact information</h2>
                <p>{INFORMATION_SHEET_CONTACT}</p>
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
            university_col, colaps_col = st.columns(
                2, gap="large", vertical_alignment="center"
            )
            with university_col:
                st.image(
                    str(ASSETS_DIR / "university_duisburg_essen.png"), width=190
                )
            with colaps_col:
                st.image(str(ASSETS_DIR / "colaps.png"), width=180)

        st.markdown(
            """
            <section class="game-guide-hero">
                <div class="game-guide-hero-copy">
                    <div class="information-eyebrow">RESEARCH STUDY</div>
                    <h1>Game Guide</h1>
                    <h2>Team Up with an AI</h2>
                    <p>This page explains how the game works and what you need to do.<br>Please read the instructions carefully before starting.</p>
                </div>
                <div class="game-guide-word-cards" aria-hidden="true">
                    <span>think</span><span>connect</span><span>play</span>
                </div>
            </section>
            """,
            unsafe_allow_html=True,
        )

        with st.expander(
            "**1**　Overview", expanded=True, icon=":material/groups:"
        ):
            st.markdown(GUIDE_OVERVIEW)
        with st.expander(
            "**2**　Your Role", expanded=True, icon=":material/switch_account:"
        ):
            st.markdown(GUIDE_ROLE)
        with st.expander(
            "**3**　When You Are the Clue-Giver",
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
            st.success(CLUE_GIVER_OUTRO)

        section_icons = (
            ":material/smart_toy:",
            ":material/target:",
            ":material/style:",
            ":material/sync:",
            ":material/skip_next:",
            ":material/forum:",
            ":material/schedule:",
            ":material/rate_review:",
            ":material/emoji_events:",
        )
        for section_number, ((title, content), icon) in enumerate(
            zip(GUIDE_SECTIONS, section_icons), start=4
        ):
            with st.expander(
                f"**{section_number}**　{title}",
                expanded=False,
                icon=icon,
            ):
                st.markdown(content)

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


def screen_tutorial():
    """Run two isolated deterministic practice rounds before the experiment."""
    step = st.session_state.get("tutorial_step", "introduction")
    st.markdown(
        """
        <div class="glass-card compact-card tutorial-hero">
            <div class="panel-title">Practice · Learn both roles</div>
            <p class="subtle-text" style="margin:0;">Two short practice rounds. No score and no experimental data.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if step == "introduction":
        with st.container(border=True):
            st.markdown(
                """
                ### Try each role once

                - **Round 1:** The AI gives a clue and you guess the cards.
                - **Round 2:** You give the clue and predict the AI's guesses.

                The practice board has six cards in a 3 × 2 layout. You will also try the same short
                ratings and explanations used in the real game.
                """
            )
        if st.button("Start practice", type="primary", use_container_width=True):
            _reset_tutorial_practice()
            st.rerun()
        return

    if step == "ai_clue_round":
        if not st.session_state.get("tutorial_practice_started_at"):
            st.session_state.tutorial_practice_started_at = _now_iso()
        remaining = tutorial_time_remaining(
            st.session_state.get("tutorial_practice_started_at", "")
        )
        if remaining <= 0 and not st.session_state.get("tutorial_practice_result"):
            st.session_state.tutorial_practice_result = "timeout"
        render_clue_timer(remaining)
        st.markdown("### Round 1 of 2 · AI Clue-Giver")
        st.caption("You are the Guesser. Interpret the clue, explain your reasoning, then guess or use a skip just as in the real game.")
        with st.container(border=True, key="tutorial_ai_clue_panel"):
            repair_attempt = int(st.session_state.get("tutorial_repair_attempt", 0) or 0)
            found_targets = set(st.session_state.get("tutorial_found_targets", []))
            if repair_attempt:
                unresolved_targets = TUTORIAL_TARGETS - found_targets
                current_clue, current_clue_number = tutorial_repair_clue(
                    unresolved_targets, repair_attempt
                )
                st.info(
                    f"AI repair clue: **{current_clue} — {current_clue_number}**  "
                    f"\nRepair attempt {repair_attempt} for the same unresolved target set."
                )
            else:
                current_clue, current_clue_number = TUTORIAL_CLUE, TUTORIAL_CLUE_NUMBER
                st.info(f"AI clue: **{current_clue} — {current_clue_number}**")

            completed_interactions = int(
                st.session_state.get("tutorial_completed_interactions", 0) or 0
            )
            skip_count = int(st.session_state.get("tutorial_skip_count", 0) or 0)
            status_col_1, status_col_2 = st.columns(2)
            status_col_1.caption(
                f"Completed interactions: {completed_interactions} / {MAX_INTERACTIONS_PER_ROUND}"
            )
            status_col_2.caption(f"Skips used: {skip_count} / {MAX_SKIPS_PER_ROUND}")
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
                    st.rerun()

            result = st.session_state.get("tutorial_practice_result", "")
            if not result:
                remaining_guess_slots = current_clue_number - len(current_guesses)
                unavailable_cards = set(selected)
                skip_interpretation = st.multiselect(
                    (
                        f"Before skipping, select exactly {remaining_guess_slots} card(s) "
                        "you think this clue was meant for."
                    ),
                    options=[word for word in TUTORIAL_BOARD if word not in unavailable_cards],
                    max_selections=remaining_guess_slots,
                    key=f"tutorial_skip_interpretation_{repair_attempt}",
                    help=(
                        "These cards are stored separately as your interpretation and do not "
                        "count as guesses."
                    ),
                )
                skip_disabled = skip_count >= MAX_SKIPS_PER_ROUND
                if st.button(
                    "Stop guessing and use 1 skip",
                    use_container_width=True,
                    disabled=skip_disabled,
                    key=f"tutorial_skip_button_{repair_attempt}",
                ):
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
                        st.rerun()
                if skip_disabled:
                    st.caption("Both practice skips have been used; continue by selecting cards.")

            if result == "timeout":
                st.warning("Practice time expired. This does not affect your study participation or score.")
                if st.button("Retry with a fresh timer", use_container_width=True):
                    _reset_tutorial_practice()
                    st.rerun()
            elif result in {"correct", "incorrect", "bomb"}:
                if result == "correct":
                    st.success("Correct — the clue referred to both target cards.")
                elif result == "bomb":
                    st.error("Bomb selected — just as in the real game, the round ends immediately.")
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
                if st.button(
                    "Continue to round 2",
                    type="primary",
                    use_container_width=True,
                    disabled=rating is None,
                ):
                    st.session_state.tutorial_step = "human_clue_round"
                    st.session_state.tutorial_practice_started_at = _now_iso()
                    st.rerun()
        return

    if step == "human_clue_round":
        remaining = tutorial_time_remaining(
            st.session_state.get("tutorial_practice_started_at", "")
        )
        render_clue_timer(remaining)
        st.markdown("### Round 2 of 2 · Human Clue-Giver")
        st.caption("The card roles are visible because you are the Clue-Giver. Complete every field before the simulated AI guesses.")
        with st.container(border=True, key="tutorial_human_clue_panel"):
            render_board(
                list(TUTORIAL_ROUND_2_BOARD),
                TUTORIAL_ROUND_2_WORD_ROLES,
                guesses=st.session_state.get("tutorial_simulated_ai_guesses", []),
                reveal_all=True,
                column_count=3,
            )
            render_board_legend()
            form_locked = bool(st.session_state.get("tutorial_human_clue_submitted"))
            clue_col, number_col = st.columns([2, 1])
            with clue_col:
                clue = st.text_input(
                    "One-word clue",
                    key="tutorial_human_clue",
                    placeholder="Example: Fruit",
                    disabled=form_locked,
                )
            with number_col:
                clue_number = st.selectbox(
                    "Clue number N",
                    options=[1, 2],
                    index=1,
                    key="tutorial_human_clue_number",
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
            st.caption(
                "All six board cards are shown here. As the Clue-Giver, you can select only "
                "green target cards; neutral cards and the bomb are unavailable."
            )
            render_hint_target_selector(
                list(TUTORIAL_ROUND_2_BOARD),
                st.session_state.tutorial_intended_targets,
                clue_number,
                state_key="tutorial_intended_targets",
                key_prefix="tutorial_hint_target",
                column_count=3,
                disabled=form_locked,
                selectable_words=tutorial_target_options,
            )
            intended = st.session_state.tutorial_intended_targets
            expected = st.multiselect(
                f"Which cards do you expect the AI to guess? · select exactly {clue_number}",
                options=list(TUTORIAL_ROUND_2_BOARD),
                max_selections=clue_number,
                key="tutorial_expected_guesses",
                disabled=form_locked,
            )
            rating_before = st.radio(
                "How well do you expect the AI to understand your clue?",
                options=RATING_OPTIONS,
                index=None,
                horizontal=True,
                key="tutorial_rating_before",
                disabled=form_locked,
            )
            general_link = st.text_area(
                "General link (3–20 English words, no card names)",
                key="tutorial_general_link",
                placeholder="Describe the shared relationship without naming any card.",
                disabled=form_locked,
                max_chars=150,
            )
            if not form_locked and st.button(
                "Let the simulated AI guess", type="primary", use_container_width=True
            ):
                link_valid, link_reason = validate_general_link(
                    general_link, list(TUTORIAL_ROUND_2_BOARD)
                )
                if remaining <= 0:
                    st.warning("Practice time expired. Restart this practice round to try again.")
                else:
                    clue_valid, clue_error = validate_human_hint_with_history(
                        clue,
                        list(TUTORIAL_ROUND_2_BOARD),
                        [],
                        [],
                    )
                    if not clue_valid:
                        st.warning(clue_error)
                    elif len(intended) != clue_number:
                        st.warning(f"Select exactly {clue_number} intended target card(s).")
                    elif len(expected) != clue_number:
                        st.warning(f"Select exactly {clue_number} expected AI guess(es).")
                    elif rating_before is None:
                        st.warning("Choose your expected-understanding rating.")
                    elif not link_valid:
                        messages = {
                            "too_short": "Write at least 3 English words.",
                            "too_long": "Keep the General Link to 20 words or fewer.",
                            "non_english": "Write the General Link in English only.",
                            "board_word": "Do not mention any board/card names in the General Link.",
                        }
                        st.warning(messages.get(link_reason, "Check the General Link and try again."))
                    else:
                        st.session_state.tutorial_human_clue_submitted = True
                        st.session_state.tutorial_simulated_ai_guesses = simulated_ai_guesses(clue_number)
                        st.rerun()

            if form_locked:
                ai_guesses = st.session_state.get("tutorial_simulated_ai_guesses", [])
                st.success("The simulated AI has made its decision. Your submitted General Link is now locked.")
                st.markdown("**Simulated AI guesses:** " + ", ".join(ai_guesses))
                rating_after = st.radio(
                    "After the guesses, how well do you think you and the AI understood each other?",
                    options=RATING_OPTIONS,
                    index=None,
                    horizontal=True,
                    key="tutorial_rating_after",
                )
                if st.button(
                    "Complete practice",
                    type="primary",
                    use_container_width=True,
                    disabled=rating_after is None,
                ):
                    st.session_state.tutorial_step = "complete"
                    st.rerun()
        return

    st.success("Practice complete — you tried both roles and all required inputs.")
    st.caption("Your practice answers are not scored and are not stored in the experimental datasets.")
    if st.button("Begin the real game", type="primary", use_container_width=True):
        st.session_state.tutorial_completed = True
        mark_session_progress("tutorial")
        st.rerun()


def _anonymous_participant_id():
    session_id = str(st.session_state.get("session_id", "")).replace("-", "")
    suffix = session_id[-8:] if session_id else "unknown"
    return f"participant_{suffix}"


def _display_player_name():
    return st.session_state.get("nickname") or "Participant"


def _share_explanations():
    return st.session_state.get("condition", DEFAULT_CONDITION) == "adaptive"


def _history_with_pending_ai_guess(pending_review):
    """Add an unsaved AI result to History so it is not shown in a duplicate banner."""
    history = list(st.session_state.get("interaction_history", []))
    if not pending_review:
        return history
    guesses = list(pending_review.get("guesses", []))
    targets = set(st.session_state.get("target_words", []))
    neutrals = set(st.session_state.get("neutral_words", []))
    bombs = set(st.session_state.get("bomb_words", []))
    correct_guesses = [word for word in guesses if word in targets]
    neutral_guesses = [word for word in guesses if word in neutrals]
    bomb_guesses = [word for word in guesses if word in bombs]
    history.append(
        {
            "turn": len(history) + 1,
            "clue_giver": "human",
            "guesser": "ai",
            "hint": pending_review.get("hint", ""),
            "hint_number": pending_review.get("hint_number", 1),
            "intended_targets": pending_review.get("intended_targets", []),
            "expected_guesses": pending_review.get("expected_guesses", []),
            "guess_rationale": pending_review.get("guess_rationale", ""),
            "guesses": guesses,
            "correct": bool(correct_guesses),
            "correct_guesses": correct_guesses,
            "neutral_guesses": neutral_guesses,
            "bomb_guesses": bomb_guesses,
            "bomb_hit": bool(bomb_guesses),
            "outcome": (
                "bomb"
                if bomb_guesses
                else (
                    "partial_skip"
                    if pending_review.get("partial_skip")
                    else ("correct" if correct_guesses else "wrong")
                )
            ),
            "skipped": bool(pending_review.get("partial_skip")),
            "skipped_by": "ai" if pending_review.get("partial_skip") else "",
            "partial_skip": bool(pending_review.get("partial_skip")),
            "skip_interpreted_cards": list(
                pending_review.get("skip_interpreted_cards", [])
            ),
        }
    )
    return history


def screen_name():
    with st.container(key="participant_profile_page"):
        with st.container(key="participant_profile_logos"):
            university_col, colaps_col = st.columns(
                2, gap="large", vertical_alignment="center"
            )
            with university_col:
                st.image(
                    str(ASSETS_DIR / "university_duisburg_essen.png"), width=190
                )
            with colaps_col:
                st.image(str(ASSETS_DIR / "colaps.png"), width=180)
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
                    age_group = st.selectbox(
                        "What is your age group?",
                        [""] + AGE_GROUP_OPTIONS,
                        index=0,
                        format_func=lambda option: (
                            "Select age group" if option == "" else option
                        ),
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
                if missing:
                    st.error("Please complete: " + ", ".join(missing) + ".")
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
    st.session_state.pending_ai_guess_review = None
    st.session_state.pending_hint_meta = None
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
            "human_decision_started_at": st.session_state.get("clue_timer_started_at", ""),
            "human_decision_ended_at": timeout_timestamp,
            "human_decision_time_sec": _seconds_between(
                st.session_state.get("clue_timer_started_at", ""), timeout_timestamp
            ),
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


def _consume_human_guess_timeout():
    """Consume an expired AI-clue turn once, preserving unsubmitted analysis input."""
    if not st.session_state.get("hint") or not participant_decision_timer_expired():
        return False
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
    """Consume an expired human clue-form task without invoking the AI."""
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
    timeout_timestamp = record_timeout(
        hint,
        hint_number,
        list(st.session_state.get("hint_targets", [])),
        expected_guesses,
        hint_time_sec=_seconds_between(
            st.session_state.get("current_hint_start_time", "")
        ),
        ai_understanding_rating_before=rating_before,
        human_explanation_raw=general_link,
        human_explanation_is_valid=False if general_link else None,
        human_explanation_blocked_reason=(
            "timeout_unsubmitted" if general_link else ""
        ),
        human_explanation_source=(
            "pre_ai_human_clue_form_unsubmitted" if general_link else ""
        ),
        human_explanation_collected_at="",
    )
    _log_timeout(timeout_timestamp, None)
    st.session_state.last_timeout_notice = True
    _clear_current_clue()
    return True


def _pending_ai_clue_repair_context():
    """Return the latest skipped AI-clue target set until a linked retry exists."""
    history = st.session_state.get("interaction_history", [])
    repaired_source_turns = {
        item.get("repair_source_turn")
        for item in history
        if item.get("repair_attempt")
    }
    for item in reversed(history):
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


def _generate_and_store_ai_hint():
    hint_start_time = _now_iso()
    repair_context = _pending_ai_clue_repair_context()
    try:
        with st.spinner("AI is generating a clue..."):
            hint_result = generate_ai_hint(
                st.session_state.target_words,
                st.session_state.bomb_words,
                st.session_state.neutral_words,
                st.session_state.word_type,
                st.session_state.interaction_history,
                st.session_state.used_hints,
                st.session_state.ai_round_summaries,
                condition=st.session_state.get("condition", DEFAULT_CONDITION),
                repair_context=repair_context,
            )
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
    start_participant_decision_timer(hint_end_time)
    st.session_state.pending_hint_meta = {
        "raw_response": hint_result.get("raw_response", ""),
        "hint_time_sec": hint_time_sec,
        "response_time_sec": hint_result.get("response_time_sec"),
        "attempts": hint_result.get("attempts"),
        "repair_context": repair_context,
    }
    return True


def _attach_ai_explanation_to_latest_turn():
    if not st.session_state.get("interaction_history"):
        return
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
                    "human_understanding_rating",
                    "ai_understanding_rating_after",
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


def _save_turn_reflection(item, understood_ai_rating, ai_understood_me_rating, relationship_type, explanation):
    explanation = (explanation or "").strip()
    understood_ai_rating = int(understood_ai_rating)
    ai_understood_me_rating = int(ai_understood_me_rating)
    # human_understanding_rating: how well the human thinks THEY understood
    # the AI this turn. ai_understanding_rating_after: how well the human
    # thinks the AI understood THEM. These are two directions of the same
    # question, not one mutual score.
    item["reflection_rating"] = understood_ai_rating
    item["human_understanding_rating"] = understood_ai_rating
    item["ai_understanding_rating_after"] = ai_understood_me_rating
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


def render_turn_reflection():
    item = _current_pending_reflection_item()
    if not item:
        return False
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

    render_top_status()
    with st.container(border=True, key="reflection_panel"):
        ai_explanation = item.get("ai_explanation_sanitized") or item.get("ai_explanation", "")
        show_reflection_header = human_clue_giver or _share_explanations()
        if show_reflection_header:
            header_body = (
                escape(ai_explanation)
                if not human_clue_giver and ai_explanation
                else "Rate the shared understanding after the AI's guesses."
            )
            reflection_title = (
                "Shared-understanding rating"
                if human_clue_giver
                else "AI's clue explanation"
            )
            st.markdown(
                f"""
                <div class="glass-card compact-card reflection-ai-explanation reflection-compact-head">
                    <div class="panel-title">{reflection_title}</div>
                    <p class="subtle-text" style="margin:0;">{header_body}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        rating_col = st.container()

        with rating_col:
            st.radio(
                "After the guesses, how well do you think you understood the AI?",
                options=list(RATING_OPTIONS.keys()),
                index=None,
                format_func=lambda option: f"{option}",
                horizontal=True,
                key=f"reflection_rating_{st.session_state.round}_{item.get('turn')}",
            )
            render_rating_scale_endpoints()
            st.radio(
                "How well do you think the AI understood you?",
                options=list(RATING_OPTIONS.keys()),
                index=None,
                format_func=lambda option: f"{option}",
                horizontal=True,
                key=f"reflection_rating_ai_understood_me_{st.session_state.round}_{item.get('turn')}",
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
            ai_understood_me_rating = st.session_state[
                f"reflection_rating_ai_understood_me_{st.session_state.round}_{item.get('turn')}"
            ]
            if understood_ai_rating is None or ai_understood_me_rating is None:
                st.error("Please select both ratings before continuing.")
                return True
            if replacement_count and len(replacement_cards) != replacement_count:
                st.error(
                    f"Please select exactly {replacement_count} replacement card(s)."
                )
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
            _save_turn_reflection(item, understood_ai_rating, ai_understood_me_rating, relationship_type, explanation)
            log_event(
                "reflection_submitted",
                {"reflection_source": item.get("reflection_source", "")},
                turn_number=item.get("turn", ""),
            )
            st.rerun()

    with st.expander(
        f"History · {len(st.session_state.interaction_history)} past turn(s)",
        expanded=False,
    ):
        render_interaction_history(
            st.session_state.interaction_history,
            share_explanations=_share_explanations(),
        )
    return True


def screen_human_clue():
    if st.session_state.get("pending_reflection_turn"):
        if render_turn_reflection():
            return

    if st.session_state.round_finished:
        screen_round_summary()
        return

    render_top_status()

    if st.session_state.pop("last_timeout_notice", False):
        st.warning("Time expired. The clue used one turn and no guesses were submitted.")
    if st.session_state.pop("ai_reroll_notice", False):
        st.warning("The AI asked for another clue.")

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
                partial_skip=pending_review.get("partial_skip", False),
                skipped_by="ai" if pending_review.get("partial_skip") else None,
                skip_interpreted_cards=pending_review.get(
                    "skip_interpreted_cards", []
                ),
                clue_timer_started_at=pending_review.get("clue_timer_started_at"),
                timer_duration_seconds=pending_review.get("timer_duration_seconds"),
                human_decision_ended_at=pending_review.get("human_decision_ended_at"),
                human_decision_time_sec=pending_review.get("human_decision_time_sec"),
                human_explanation_raw=pending_review.get("human_explanation_raw", ""),
                human_explanation_is_valid=pending_review.get("human_explanation_is_valid"),
                human_explanation_source=pending_review.get("human_explanation_source", ""),
                human_explanation_collected_at=pending_review.get("human_explanation_collected_at", ""),
            )
            _attach_ai_wrong_guess_replacements(
                st.session_state.interaction_history[-1]
                if st.session_state.interaction_history
                else None
            )
            if pending_review.get("partial_skip"):
                recorded_item = st.session_state.interaction_history[-1]
                log_event(
                    "partial_skip_used",
                    {
                        "skipped_by": "ai",
                        "completed_turn_number": recorded_item.get("completed_turn_number", ""),
                        "skip_number": recorded_item.get("skip_number", ""),
                        "completed_guesses": len(pending_review.get("guesses", [])),
                        "skipped_guesses": max(
                            0,
                            pending_review.get("hint_number", 1)
                            - len(pending_review.get("guesses", [])),
                        ),
                        "guessed_cards": pending_review.get("guesses", []),
                        "skip_interpreted_cards": pending_review.get(
                            "skip_interpreted_cards", []
                        ),
                    },
                    turn_number=recorded_item.get("turn", ""),
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
        history_for_review = _history_with_pending_ai_guess(pending_review)
        with st.expander(f"History · {len(history_for_review)} past turn(s)", expanded=False):
            render_interaction_history(
                history_for_review,
                share_explanations=_share_explanations(),
            )
        return

    st.markdown(
        """
        <div class="panel-title section-gap">Enter your clue for the AI guesser</div>
        """,
        unsafe_allow_html=True,
    )
    _ensure_timer("current_hint_start_time")
    if participant_decision_time_remaining() is None:
        start_participant_decision_timer(
            st.session_state.get("current_hint_start_time") or _now_iso()
        )
        st.session_state.current_turn_start_time = st.session_state.get(
            "current_hint_start_time", ""
        )
    if _consume_human_clue_timeout():
        st.rerun()
    participant_timer_placeholder = st.empty()
    with participant_timer_placeholder:
        render_clue_timer(participant_decision_time_remaining())

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
                key=f"before_ai_guess_rating_{st.session_state.round}_{_current_action_index()}",
            )
            render_rating_scale_endpoints()
    st.session_state.ai_understanding_rating_before = rating_before

    general_link_key = (
        f"pre_ai_general_link_{st.session_state.round}_"
        f"{_current_action_index()}"
    )
    general_link = st.text_area(
        "General link (3–20 English words, no card names)",
        max_chars=150,
        placeholder="Example: Both ideas connect through luck and success.",
        key=general_link_key,
    )
    general_link_is_valid, general_link_blocked_reason = validate_general_link(
        general_link, st.session_state.get("board", [])
    )

    hint_is_valid, _hint_error_preview = validate_human_hint_with_history(
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

    def _checklist_item(done, label):
        mark = "&#10003;" if done else "&#9675;"
        state = "ok" if done else ""
        return f"<li class='{state}'><span class='mark'>{mark}</span> {escape(label)}</li>"

    st.markdown(
        "<ul class='turn-checklist'>"
        + _checklist_item(hint_is_valid, "Clue and count set")
        + _checklist_item(targets_ready, "Cards you mean selected")
        + _checklist_item(predicted_ready, "Predicted AI guesses selected")
        + _checklist_item(rating_ready, "Confidence rated")
        + _checklist_item(general_link_is_valid, "Connection explained")
        + "</ul>",
        unsafe_allow_html=True,
    )

    if st.button(
        "Let AI Guess",
        type="primary",
        use_container_width=True,
        disabled=not turn_ready,
    ):
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
        elif not general_link_is_valid:
            st.error(_general_link_error(general_link_blocked_reason))
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
                    "ai_understanding_rating_before": rating_before,
                    "human_explanation_raw": submitted_general_link,
                    "human_explanation_is_valid": True,
                    "human_explanation_source": "pre_ai_human_clue_form",
                    "human_explanation_collected_at": hint_end_time,
                    "human_decision_started_at": clue_timer_started_at,
                    "human_decision_ended_at": hint_end_time,
                    "human_decision_time_sec": hint_time_sec,
                },
                turn_number=_next_action_number(),
            )
            participant_timer_placeholder.empty()
            clear_participant_decision_timer()
            log_event("ai_guess_started", {"clue": st.session_state.hint}, turn_number=_next_action_number())
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
            if action == "reroll":
                if st.session_state.ai_rerolls > 0:
                    st.session_state.ai_rerolls -= 1
                    st.session_state.ai_reroll_notice = True
                    st.session_state.current_hint_start_time = ""
                else:
                    st.warning("No AI rerolls remain. Please adjust the clue.")
                st.rerun()
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
                    skip_interpreted_cards=guess_result.get(
                        "skip_interpreted_cards", []
                    ),
                    guess_raw_response=guess_result.get("raw_response", ""),
                    guess_time_sec=guess_time_sec,
                    guess_response_time_sec=guess_result.get("response_time_sec"),
                    clue_timer_started_at=clue_timer_started_at,
                    timer_duration_seconds=timer_duration_seconds,
                    human_decision_ended_at=hint_end_time,
                    human_decision_time_sec=hint_time_sec,
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
                    "partial_skip": action == "partial_skip",
                    "skip_interpreted_cards": guess_result.get(
                        "skip_interpreted_cards", []
                    ),
                    "clue_timer_started_at": clue_timer_started_at,
                    "timer_duration_seconds": timer_duration_seconds,
                    "human_decision_ended_at": hint_end_time,
                    "human_decision_time_sec": hint_time_sec,
                    "human_explanation_raw": submitted_general_link,
                    "human_explanation_is_valid": True,
                    "human_explanation_source": "pre_ai_human_clue_form",
                    "human_explanation_collected_at": hint_end_time,
                }
                st.rerun()

    with st.expander(
        f"History · {len(st.session_state.interaction_history)} past turn(s)",
        expanded=False,
    ):
        render_interaction_history(
            st.session_state.interaction_history,
            share_explanations=_share_explanations(),
        )


def screen_human_guesser():
    if st.session_state.get("pending_reflection_turn"):
        if render_turn_reflection():
            return

    if st.session_state.round_finished:
        screen_round_summary()
        return

    render_top_status()

    if st.session_state.pop("last_timeout_notice", False):
        st.warning("Time expired. The clue used one turn and no guesses were submitted.")

    if _consume_human_guess_timeout():
        st.rerun()

    if not st.session_state.hint:
        if st.session_state.round == 1:
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
                if _generate_and_store_ai_hint():
                    st.rerun()
                return
        else:
            if _generate_and_store_ai_hint():
                st.rerun()
            if st.button("Try generating the AI clue again", use_container_width=True):
                st.rerun()
            return
    else:
        remaining_time = participant_decision_time_remaining()
        if remaining_time is not None:
            render_clue_timer(remaining_time)
        render_hint_panel(
            st.session_state.hint,
            st.session_state.hint_number,
            st.session_state.previous_hint,
        )
        with st.container(border=True, key="before_human_guess_panel"):
            prompt_col, rating_col = st.columns([1.45, 1])
            with prompt_col:
                st.markdown(
                    """
                    <div class="panel-title">Before you guess</div>
                    <p class="subtle-text before-ai-question">How well do you think you understand the AI's clue?</p>
                    """,
                    unsafe_allow_html=True,
                )
            with rating_col:
                human_pre_guess_rating = st.radio(
                    "Before guessing rating",
                    options=list(RATING_OPTIONS.keys()),
                    index=None,
                    format_func=lambda option: f"{option}",
                    horizontal=True,
                    label_visibility="collapsed",
                    key=f"human_pre_guess_rating_{st.session_state.round}_{_current_action_index()}",
                )
                render_rating_scale_endpoints()
        guess_rationale, rationale_is_valid = _render_guess_rationale_input()
        guess_gate_ready = human_pre_guess_rating is not None and rationale_is_valid

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
            if not guess_gate_ready:
                render_board_lock_note(
                    "Rate the clue and add your reasoning above to start guessing."
                )
            clicked = render_board(
                st.session_state.board,
                st.session_state.word_roles,
                guesses=st.session_state.guesses + st.session_state.pending_guesses,
                reveal_all=False,
                clickable=guess_gate_ready,
                max_clicks=st.session_state.hint_number + len(st.session_state.guesses),
            )
            if clicked and human_pre_guess_rating is None:
                st.error("Please rate how well you understand the AI's clue before guessing.")
            elif clicked and not rationale_is_valid:
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
                        human_understanding_rating_before=human_pre_guess_rating,
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
                    clear_participant_decision_timer()
                st.rerun()

    if st.session_state.hint:
        skip_interpretation = []
        remaining_guess_slots = (
            int(st.session_state.hint_number)
            - len(st.session_state.pending_guesses)
        )
        if can_skip_current_clue():
            unavailable_cards = set(st.session_state.guesses).union(
                st.session_state.pending_guesses
            )
            skip_interpretation = st.multiselect(
                (
                    f"Before skipping, select exactly {remaining_guess_slots} card(s) "
                    "you think this clue was meant for."
                ),
                options=[
                    word
                    for word in st.session_state.board
                    if word not in unavailable_cards
                ],
                max_selections=remaining_guess_slots,
                placeholder=(
                    f"Select exactly {remaining_guess_slots} remaining card(s)..."
                ),
                key=(
                    f"skip_interpretation_{st.session_state.round}_"
        f"{_current_action_index()}"
                ),
                help=(
                    f"Select exactly {remaining_guess_slots} card(s), even if you are "
                    "not confident. These are stored separately and do not count as guesses."
                ),
            )
        if st.button(
            "Stop guessing and use 1 skip",
            use_container_width=True,
            disabled=not can_skip_current_clue() or not guess_gate_ready,
        ):
            pending_meta = st.session_state.get("pending_hint_meta") or {}
            if human_pre_guess_rating is None:
                st.error("Please rate how well you understand the AI's clue before skipping.")
            elif len(skip_interpretation) != remaining_guess_slots:
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
                    "human_understanding_rating_before": human_pre_guess_rating,
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
                    _attach_ai_explanation_to_latest_turn()
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
                    _attach_ai_explanation_to_latest_turn()
                _clear_current_clue()
                st.rerun()
    with st.expander(
        f"History · {len(st.session_state.interaction_history)} past turn(s)",
        expanded=False,
    ):
        render_interaction_history(
            st.session_state.interaction_history,
            share_explanations=_share_explanations(),
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
        with st.expander(
            f"History · {len(st.session_state.interaction_history)} past turn(s)",
            expanded=False,
        ):
            render_interaction_history(
                st.session_state.interaction_history,
                show_ai_intended=True,
                share_explanations=_share_explanations(),
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
            if feedback_words < 3:
                st.error("Please write at least 3 words in your end-of-round reflection.")
                return
            if feedback_words > 200:
                st.error("Please keep your message to 200 words or fewer.")
                return
            if not _is_english_text(st.session_state.human_round_feedback):
                st.error(ENGLISH_ONLY_ERROR)
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
    player_name_html = escape(player_name)
    total_score = st.session_state.get("score", 0)
    if not st.session_state.get("session_completed_logged"):
        if not st.session_state.get("completion_code"):
            st.session_state.completion_code = (
                str(st.session_state.get("session_id", "")).replace("-", "")[-8:].upper()
            )
    if total_score >= 16:
        title = "Elite team!"
        subtitle = f"Fantastic finish, {player_name_html}! Your team was sharp, fast, and beautifully in sync."
        tier = "Elite team"
    elif total_score >= 14:
        title = "Excellent team!"
        subtitle = f"Great work, {player_name_html}! That was a confident run with strong clue-reading."
        tier = "Excellent team"
    elif total_score >= TEAM_GOAL_SCORE:
        title = "Strong team!"
        subtitle = f"Nice work, {player_name_html}! You cleared the target score and built a solid rhythm."
        tier = "Strong team"
    else:
        title = "Run finished"
        subtitle = f"{player_name_html}, you were close. A few cleaner clue connections and this team can jump a tier."
        tier = "Building team"

    st.markdown(
        f"""
        <div class="glass-card game-over-card celebration-card">
            <div class="celebration-medals">
                <span>&#129351;</span><span>&#129352;</span>
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

    col1, col2 = st.columns(2)
    medal_counts = st.session_state.medal_counts
    col1.markdown(
        f"<div class='summary-stat'><strong>&#129351; Gold</strong><br>{medal_counts.get('gold', 0)}</div>",
        unsafe_allow_html=True,
    )
    col2.markdown(
        f"<div class='summary-stat'><strong>&#129352; Silver</strong><br>{medal_counts.get('silver', 0)}</div>",
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

    st.caption("You may now close this browser tab.")
