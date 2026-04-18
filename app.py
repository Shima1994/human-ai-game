import streamlit as st

from core.game_logic import setup_new_round
from core.state import init_session_state
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
        setup_new_round()

    if st.session_state.role == "human_clue":
        screen_human_clue()
    else:
        screen_human_guesser()


if __name__ == "__main__":
    main()
