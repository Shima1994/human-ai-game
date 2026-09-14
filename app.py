import streamlit as st

from core.game_logic import BoardGenerationError, setup_new_round
from core.state import init_session_state
from core.storage import log_event
from ui.components import render_app_header, scroll_page_to_top
from ui.screens import (
    screen_consent,
    screen_game_over,
    screen_human_clue,
    screen_human_guesser,
    screen_name,
    screen_tutorial,
    screen_welcome,
)
from ui.styles import inject_css


st.set_page_config(
    page_title="Human-AI Cooperative Word Game",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _current_view_key():
    """Identify real page transitions without treating widget reruns as navigation."""
    state = st.session_state
    if not state.consent_given:
        return "consent"
    if not state.started:
        return "game_guide"
    if not state.participant_id:
        return "participant_profile"
    if not state.tutorial_completed:
        return f"tutorial:{state.get('tutorial_step', 'introduction')}"
    if state.game_over:
        if not state.get("post_game_questionnaire_submitted"):
            return "post_study_questionnaire"
        if not state.get("debriefing_acknowledged"):
            return "debriefing"
        return "completion"
    round_number = state.get("round", 0)
    if state.get("round_finished"):
        return f"round:{round_number}:summary"
    return f"round:{round_number}:{state.get('role', '')}"


def _scroll_after_view_change():
    current_view = _current_view_key()
    previous_view = st.session_state.get("_rendered_view_key")
    should_scroll = previous_view is not None and previous_view != current_view
    st.session_state._rendered_view_key = current_view
    # Called every rerun (not just on a transition) so this component's DOM
    # node is never added/removed between reruns -- see scroll_page_to_top's
    # docstring for why that mattered.
    scroll_page_to_top(should_scroll)


def main():
    init_session_state()
    inject_css()
    _scroll_after_view_change()

    if not st.session_state.consent_given:
        screen_consent()
        return

    if not st.session_state.started:
        screen_welcome()
        return

    if not st.session_state.participant_id:
        screen_name()
        return

    if not st.session_state.tutorial_completed:
        screen_tutorial()
        return

    if st.session_state.game_over:
        screen_game_over()
        return

    if st.session_state.board is None:
        try:
            setup_new_round()
        except BoardGenerationError as error:
            render_app_header()
            st.error(str(error))
            return
        logged_rounds = st.session_state.setdefault("logged_round_starts", [])
        if st.session_state.round not in logged_rounds:
            log_event(
                "round_started",
                {
                    "round_role": st.session_state.role,
                    "board_template_type": st.session_state.get("board_template_type", ""),

                    "board_id": st.session_state.get("board_id", ""),

                },
                round_number=st.session_state.round,
                turn_number="",
            )
            logged_rounds.append(st.session_state.round)

    if st.session_state.role == "human_clue":
        screen_human_clue()
    else:
        screen_human_guesser()


if __name__ == "__main__":
    main()
