import streamlit as st

from core.game_logic import BoardGenerationError, setup_new_round
from core.state import init_session_state
from core.storage import log_event
from ui.components import render_app_header
from ui.screens import (
    screen_game_over,
    screen_human_clue,
    screen_human_guesser,
    screen_name,
    screen_welcome,
)
from ui.styles import inject_css


st.set_page_config(
    page_title="Human-AI Cooperative Word Game",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main():
    inject_css()
    init_session_state()

    if not st.session_state.started:
        render_app_header()
        screen_welcome()
        return

    if not st.session_state.participant_id:
        render_app_header()
        screen_name()
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
