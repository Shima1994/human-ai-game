"""Step-by-step picture walkthrough shown at the top of the Game Guide.

The steps follow the order of a real game: a round starts, one turn as the
Clue-Giver, one turn as the Guesser, the end of a round, and the final medal.
Every picture is a small static copy of a real game screen built from the
game's own CSS classes, played out on two made-up example boards. None of the
example words is on a real board (tests/test_guide_walkthrough.py checks every
word a step shows), so the guide can't hint at any real target or bomb.
"""

from html import escape

import streamlit as st

from core.constants import (
    BOARD_SIZE,
    BOMB_COUNT,
    MAX_INTERACTIONS_PER_ROUND,
    MAX_SKIPS_PER_ROUND,
    N_ROUNDS,
    POINTS_EXACT_INTENDED_TARGET,
    POINTS_OTHER_TARGET,
    TARGET_COUNT,
)
from ui.components import (
    _guide_card,
    _guide_clue_panel,
    _stat_block,
    guide_history_figure,
    guide_scoring_figure,
    guide_status_bar_figure,
    guide_timers_figure,
    role_badge_html,
)

# Board seen as the Clue-Giver: the player gives "breakfast - 2" for Toast
# and Coffee, and expects the AI to take Plate instead of Coffee.
CLUE_GIVER_BOARD = (
    ("Violin", "target"), ("Pencil", "neutral"), ("Toast", "target"), ("Knife", "bomb"),
    ("Bicycle", "neutral"), ("Basket", "neutral"), ("Tent", "target"), ("Ladder", "neutral"),
    ("Coffee", "target"), ("Window", "neutral"), ("Fire", "bomb"), ("Feather", "neutral"),
    ("Plate", "neutral"), ("Snow", "target"), ("Carpet", "neutral"), ("Candle", "neutral"),
)
CLUE_GIVER_CLUE = ("breakfast", 2)
CLUE_GIVER_INTENDED = ("Toast", "Coffee")
CLUE_GIVER_PREDICTED = ("Toast", "Plate")
CLUE_GIVER_AI_PICKS = ("Toast", "Plate")
CLUE_GIVER_LINK = "Things people eat or drink in the morning"
CLUE_GIVER_BAD_LINK = "Toast and coffee"

# Board seen as the Guesser: the AI gives "ocean - 2" for Whale and Coral.
GUESSER_BOARD = (
    ("Tiger", "target"), ("Anchor", "neutral"), ("Desert", "target"), ("Cloud", "neutral"),
    ("Storm", "bomb"), ("Whale", "target"), ("Teapot", "neutral"), ("Map", "neutral"),
    ("Rocket", "neutral"), ("Piano", "target"), ("Coral", "target"), ("Sock", "neutral"),
    ("Bench", "neutral"), ("Volcano", "bomb"), ("Boat", "neutral"), ("Glove", "neutral"),
)
GUESSER_CLUE = ("ocean", 2)
GUESSER_INTENDED = ("Whale", "Coral")
GUESSER_PICKS = ("Whale", "Anchor")
GUESSER_RATIONALE = "Both are found in the sea."

# Streamlit draws the prediction drop-down's tags in the theme's primaryColor
# (.streamlit/config.toml); the picture copies that so it looks the same.
_MULTISELECT_TAG_COLOR = "#1d5ea8"


# --- Building blocks --------------------------------------------------------


def _board(cards, *, reveal=False, selected=(), found=(), missed=()):
    """A 4x4 example board. reveal=True shows every card's role (the
    clue-giver's view); otherwise only `found`/`missed` cards show a colour."""
    html = []
    for word, role in cards:
        ring = word in selected
        if word in found:
            html.append(_guide_card(word, role, css="word-found", selected=ring))
        elif word in missed:
            html.append(_guide_card(word, role, css="word-neutral-miss", selected=ring))
        elif reveal:
            html.append(_guide_card(word, role, selected=ring))
        else:
            html.append(_guide_card(word, "", css="word-hidden", selected=ring))
    return f'<div class="guide-board">{"".join(html)}</div>'


def _figure(body, caption=""):
    caption_html = f"<figcaption>{escape(caption)}</figcaption>" if caption else ""
    return f'<figure class="guide-figure guide-walk-figure">{body}{caption_html}</figure>'


def _form_step(number, title):
    """A numbered heading as the clue-giver form shows it."""
    return (
        f'<div class="guide-walk-formstep"><span class="guide-walk-num">{number}</span>'
        f"{escape(title)}</div>"
    )


def _chips(words, on=()):
    chips = "".join(
        f'<span class="guide-walk-chip{" on" if word in on else ""}">'
        f'{"&#10003; " if word in on else ""}{escape(word)}</span>'
        for word in words
    )
    return f'<div class="guide-walk-chips">{chips}</div>'


def _multiselect(tags):
    tag_html = "".join(
        f'<span class="guide-walk-tag" style="background:{_MULTISELECT_TAG_COLOR}">'
        f'{escape(tag)}<span class="guide-walk-tag-x">&#215;</span></span>'
        for tag in tags
    )
    return (
        f'<div class="guide-walk-multiselect">{tag_html}'
        '<span class="guide-walk-caret">&#9662;</span></div>'
    )


def _input(text, extra_class=""):
    return f'<div class="guide-walk-input {extra_class}">{escape(text)}</div>'


def _rating(question, selected):
    pills = "".join(
        f'<span class="guide-walk-rate{" on" if value == selected else ""}">{value}</span>'
        for value in range(1, 6)
    )
    return (
        f'<div class="guide-walk-label">{escape(question)}</div>'
        f'<div class="guide-walk-rating">{pills}</div>'
        '<div class="guide-walk-ends"><span>Very low</span><span>Strong</span></div>'
    )


def _points(text):
    return f'<span class="medal-chip points guide-walk-points">{escape(text)}</span>'


def _row(*items):
    return f'<div class="guide-walk-row">{"".join(items)}</div>'


# --- Pictures ---------------------------------------------------------------


def fig_goal_board():
    return _figure(_board(CLUE_GIVER_BOARD, reveal=True), "A made-up example board.")


def fig_roles():
    items = "".join(
        f'<div class="guide-walk-role">{role_badge_html(role)}'
        f'<span class="guide-walk-role-text">{escape(text)}</span></div>'
        for role, text in (
            ("clue", "You give the clue, the AI guesses."),
            ("guess", "The AI gives the clue, you guess."),
        )
    )
    return _figure(f'<div class="guide-walk-roles">{items}</div>')


def fig_clue_board():
    return _figure(_board(CLUE_GIVER_BOARD, reveal=True), "Your board as the Clue-Giver.")


def fig_clue_step1():
    word, number = CLUE_GIVER_CLUE
    body = _form_step(1, "Enter your clue for the AI guesser") + _row(
        _input(word, "guide-walk-grow"), _input(f"{number} ▾", "guide-walk-select")
    )
    return _figure(body)


def fig_clue_step2():
    targets = [word for word, role in CLUE_GIVER_BOARD if role == "target"]
    body = _form_step(2, "Select the target cards this clue is meant for") + _chips(
        targets, on=CLUE_GIVER_INTENDED
    )
    return _figure(body, "Buttons: click a target card to mark it.")


def fig_clue_step3():
    body = _form_step(3, "Select the cards you think the AI will choose") + _multiselect(
        CLUE_GIVER_PREDICTED
    )
    return _figure(body, "Drop-down list: open it and pick any cards on the board.")


def fig_clue_step4():
    body = _form_step(4, "Before AI guesses") + _rating(
        "How well do you expect the AI understood your clue?", 4
    )
    return _figure(body)


def fig_clue_step5():
    body = (
        _form_step(5, "General link")
        + '<div class="guide-walk-label">General link (3–20 English words, no card names)</div>'
        + _input(CLUE_GIVER_LINK)
        + _row('<span class="guide-walk-button primary">Let AI Guess</span>')
    )
    return _figure(body)


def fig_link_examples():
    body = (
        '<div class="guide-walk-compare">'
        '<div class="guide-walk-ok"><span class="guide-walk-mark">&#10003;</span>'
        f"{escape(CLUE_GIVER_LINK)}<span class=\"guide-walk-note\">the meaning behind the clue</span></div>"
        '<div class="guide-walk-bad"><span class="guide-walk-mark">&#10007;</span>'
        f"{escape(CLUE_GIVER_BAD_LINK)}<span class=\"guide-walk-note\">names cards: not allowed</span></div>"
        "</div>"
    )
    return _figure(body)


def fig_clue_result():
    hit, miss = CLUE_GIVER_AI_PICKS
    body = _board(
        CLUE_GIVER_BOARD,
        reveal=True,
        found=(hit,),
        missed=(miss,),
        selected=CLUE_GIVER_AI_PICKS,
    ) + _row(_points(f"{hit}: +{POINTS_EXACT_INTENDED_TARGET}"), _points(f"{miss}: 0"))
    return _figure(body, "The outlined cards are the AI's guesses.")


def fig_guesser_clue():
    word, number = GUESSER_CLUE
    return _figure(
        _guide_clue_panel("AI clue", word, number, "guess") + _board(GUESSER_BOARD),
        "As the Guesser you see only the words.",
    )


def fig_guesser_why():
    body = (
        '<div class="guide-walk-panel"><div class="guess-rationale-head">'
        '<div class="panel-title">Why these cards?</div>'
        '<div class="guess-rationale-rule">3-30 English words · no card names · before selecting</div>'
        f"</div>{_input(GUESSER_RATIONALE)}</div>"
        + _board(GUESSER_BOARD, selected=GUESSER_PICKS)
    )
    return _figure(body, "The outlined cards are the ones clicked.")


def fig_guesser_result():
    hit, miss = GUESSER_PICKS
    body = (
        _board(GUESSER_BOARD, found=(hit,), missed=(miss,), selected=GUESSER_PICKS)
        + _row(_points(f"{hit}: +{POINTS_EXACT_INTENDED_TARGET}"), _points(f"{miss}: 0"))
        + _rating("After the guesses, how well do you think you understood the AI?", 3)
    )
    return _figure(body)


def fig_skip():
    body = _row(
        _stat_block("Skips left", MAX_SKIPS_PER_ROUND, MAX_SKIPS_PER_ROUND, "warn"),
        '<span class="guide-arrow" aria-hidden="true">&#8594;</span>',
        '<span class="guide-walk-button">Skip</span>',
        '<span class="guide-arrow" aria-hidden="true">&#8594;</span>',
        _stat_block("Skips left", MAX_SKIPS_PER_ROUND - 1, MAX_SKIPS_PER_ROUND, "warn"),
    )
    return _figure(body)


def fig_round_summary():
    body = (
        '<div class="summary-stat"><strong>Points this round:</strong> 6</div>'
        '<div class="summary-stat"><strong>&#11088; Star earned!</strong></div>'
    )
    return _figure(body, "The end of a round, when all targets were found without a bomb.")


def fig_round_end():
    """Round summary and a History card side by side, to keep this step as
    short as the others."""
    return f'<div class="guide-walk-split">{fig_round_summary()}{guide_history_figure()}</div>'


# --- Steps (in the order of a real game) --------------------------------------

NEUTRAL_COUNT = BOARD_SIZE - TARGET_COUNT - BOMB_COUNT

# Each step: (role badge: "clue", "guess" or "", title, parts). A part is
# either Markdown text or a function returning one picture.
GUIDE_WALKTHROUGH_SLIDES = (
    (
        "",
        "The goal",
        (
            f"You and the AI play as **one team** for {N_ROUNDS} rounds. "
            f"Each round has a board of {BOARD_SIZE} word cards:",
            fig_goal_board,
            f"**Green** = {TARGET_COUNT} target cards to find · **gray** = {NEUTRAL_COUNT} neutral cards · "
            f"**red** = {BOMB_COUNT} bombs to avoid. One of you gives a one-word clue, the other guesses.",
        ),
    ),
    (
        "",
        "A round begins",
        (
            "At the top of the screen, this bar shows how the round is going:",
            guide_status_bar_figure,
            f"**Targets found** · **Turns used** ({MAX_INTERACTIONS_PER_ROUND} per round) · "
            f"**Skips left** ({MAX_SKIPS_PER_ROUND} per round) · your **role** · your **points** and **stars**.",
            "Next to the board, a timer counts down each decision:",
            guide_timers_figure,
        ),
    ),
    (
        "",
        "Your role in this round",
        (
            "In each round you have one of two roles. The badge in the bar shows which:",
            fig_roles,
            "Roles can switch between rounds. The next steps show one turn in each role.",
        ),
    ),
    (
        "clue",
        "Your board",
        (
            "As the Clue-Giver you see the colour of every card. The AI sees only the words.",
            fig_clue_board,
            f"In this example the player wants the AI to find **{CLUE_GIVER_INTENDED[0]}** and "
            f"**{CLUE_GIVER_INTENDED[1]}**, and to keep away from the red cards **Knife** and **Fire**.",
        ),
    ),
    (
        "clue",
        "Step 1 · A clue and a number",
        (
            fig_clue_step1,
            "Type **one word** that links your cards (not a word that is on the board), "
            f"and choose **how many** cards it links: **{CLUE_GIVER_CLUE[0].upper()} - {CLUE_GIVER_CLUE[1]}**.",
            "Careful: a clue that also fits a red card is dangerous. If the AI picks a bomb, the round ends.",
        ),
    ),
    (
        "clue",
        "Step 2 · The cards you mean",
        (
            "Click the target cards your clue is meant for. They turn coloured:",
            fig_clue_step2,
            "These are **your** cards: what your clue is supposed to point to.",
        ),
    ),
    (
        "clue",
        "Step 3 · What you think the AI will choose",
        (
            "Now open the drop-down list and pick the cards you **expect the AI to choose**. "
            "This is not about your cards, but your guess about the AI:",
            fig_clue_step3,
            f"Here the player meant **{CLUE_GIVER_INTENDED[0]}** and **{CLUE_GIVER_INTENDED[1]}**, but expects "
            f"the AI to choose **{CLUE_GIVER_PREDICTED[0]}** and **{CLUE_GIVER_PREDICTED[1]}**, because "
            f"“{CLUE_GIVER_CLUE[0]}” might also make it think of a plate.",
            "If you are confident, pick the same cards as in step 2. "
            "If you think the AI will pick a wrong card, you can still change your clue.",
        ),
    ),
    (
        "clue",
        "Step 4 · Before AI guesses",
        (
            fig_clue_step4,
            "Rate how well you think the AI will understand your clue, **before** you see its guess. "
            "There are no right or wrong answers.",
        ),
    ),
    (
        "clue",
        "Step 5 · The general link",
        (
            "Write the **general link** behind your clue in 3–20 English words: "
            "the meaning that connects your cards.",
            fig_clue_step5,
            "Describe the meaning, **not the cards**, so card names are not allowed. "
            "You write it before the AI guesses, so it shows what you had in mind from the start, "
            "not what happened afterwards.",
            fig_link_examples,
            "Then press **Let AI Guess**.",
        ),
    ),
    (
        "clue",
        "The AI guesses",
        (
            fig_clue_result,
            f"The AI chose **{CLUE_GIVER_AI_PICKS[0]}** and **{CLUE_GIVER_AI_PICKS[1]}**, just as the "
            f"player predicted. {CLUE_GIVER_AI_PICKS[0]} was a card the player meant: "
            f"**+{POINTS_EXACT_INTENDED_TARGET} points**. {CLUE_GIVER_AI_PICKS[1]} was neutral: 0 points.",
            "A short window then asks how well you think you and the AI understood each other.",
        ),
    ),
    (
        "guess",
        "Your turn to guess",
        (
            "In another round the roles switch: the AI gives the clue and you guess. "
            "Now you **do not** see the colours.",
            fig_guesser_clue,
            f"**{GUESSER_CLUE[0].upper()} - {GUESSER_CLUE[1]}** means: {GUESSER_CLUE[1]} target cards "
            f"are linked to “{GUESSER_CLUE[0]}”. Sometimes you first press **Ask AI for a clue**.",
        ),
    ),
    (
        "guess",
        "Write why, then click the cards",
        (
            "Before clicking, write **why** you think the cards fit (3–30 English words, no card names):",
            fig_guesser_why,
            "Writing it first shows how you understood the clue before you see any colours. "
            "Then click the cards: each click is final, and the turn ends once you have clicked "
            "as many cards as the number.",
        ),
    ),
    (
        "guess",
        "See the result",
        (
            fig_guesser_result,
            f"**{GUESSER_PICKS[0]}** was a card the AI meant: **+{POINTS_EXACT_INTENDED_TARGET}**. "
            f"**{GUESSER_PICKS[1]}** was neutral: 0. Because {GUESSER_PICKS[1]} was not a target, you are "
            "also asked which card you would choose instead. Then you rate how well you understood each other.",
        ),
    ),
    (
        "guess",
        "Not sure? Skip",
        (
            "If the clue is unclear, press **Skip** (under the timer) instead of clicking:",
            fig_skip,
            f"You have {MAX_SKIPS_PER_ROUND} skips per round. Skipping **before** clicking any card does not "
            "use one of your turns. Skipping **after** clicking at least one card still counts as a turn. "
            "You are then asked which cards you think the clue was meant for.",
        ),
    ),
    (
        "",
        "The end of a round",
        (
            f"A round ends after {MAX_INTERACTIONS_PER_ROUND} turns, when all {TARGET_COUNT} targets are found, "
            "or as soon as a bomb is chosen. You then see all colours, your points, and whether you earned a star:",
            fig_round_end,
            "You also write a short reflection on the round. "
            "During the round, the History panel on the left keeps every turn.",
        ),
    ),
    (
        "",
        "Points, stars and medals",
        (
            f"**+{POINTS_EXACT_INTENDED_TARGET}** for the card the clue-giver had in mind, "
            f"**+{POINTS_OTHER_TARGET}** for another target, 0 for a neutral card. "
            f"Find all {TARGET_COUNT} targets without a bomb to earn a star.",
            guide_scoring_figure,
            f"Your points over all {N_ROUNDS} rounds decide your final medal. "
            "Before the real game, you will play two short practice rounds.",
        ),
    ),
)


def _set_slide(index):
    st.session_state.guide_slide = index
    if index == len(GUIDE_WALKTHROUGH_SLIDES) - 1:
        st.session_state.guide_walkthrough_done = True


def render_guide_walkthrough():
    """Render the current step with Back/Next controls. Returns True once
    the participant has reached the last step at least once."""
    last = len(GUIDE_WALKTHROUGH_SLIDES) - 1
    index = min(max(int(st.session_state.get("guide_slide", 0)), 0), last)
    role, title, parts = GUIDE_WALKTHROUGH_SLIDES[index]

    with st.container(key="guide_walkthrough"):
        # Fixed-height body (see .st-key-guide_walk_body in app.css), so the
        # box and the Back/Next buttons don't move from one step to the next.
        with st.container(key="guide_walk_body"):
            badge = role_badge_html(role) if role else ""
            st.markdown(
                '<div class="guide-walk-head">'
                f'<span class="guide-walk-step">Step {index + 1} of {last + 1}</span>{badge}</div>'
                f'<div class="guide-walk-title">{escape(title)}</div>',
                unsafe_allow_html=True,
            )
            for part in parts:
                if callable(part):
                    st.markdown(part(), unsafe_allow_html=True)
                else:
                    st.markdown(part)

        back_col, dots_col, next_col = st.columns([1, 2, 1], vertical_alignment="center")
        with back_col:
            st.button(
                "Back",
                key="guide_walk_back",
                use_container_width=True,
                disabled=index == 0,
                on_click=_set_slide,
                args=(index - 1,),
            )
        with dots_col:
            dots = "".join(
                f'<span class="guide-walk-dot{" on" if i == index else ""}"></span>'
                for i in range(last + 1)
            )
            st.markdown(f'<div class="guide-walk-dots">{dots}</div>', unsafe_allow_html=True)
        with next_col:
            st.button(
                "Next",
                key="guide_walk_next",
                type="primary",
                use_container_width=True,
                disabled=index == last,
                on_click=_set_slide,
                args=(index + 1,),
            )
    return bool(st.session_state.get("guide_walkthrough_done"))
