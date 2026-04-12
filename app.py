import streamlit as st
import random
import csv
import os
from datetime import datetime
from openai import OpenAI

# -----------------------------
# STREAMLIT + OPENAI CONFIG
# -----------------------------
st.set_page_config(page_title="Human-AI Collaboration Study", layout="wide")

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
MODEL_NAME = "gpt-4o-mini"

# -----------------------------
# WORD POOLS 
# -----------------------------
ABSTRACT_CATEGORIES = {

    "emotion": [
        "love", "fear", "joy", "sadness", "anger", "hope", "happiness",
        "surprise", "weakness",
        "shame", "loneliness", "peace"
    ],

    "social": [
        "friend", "family", "team", "community", "leader",
        "respect", "cooperation", "freedom", 
        "support", "loyalty", "unity",  "kindness"
    ],

    "cognitive": [
        "thought", "learning", "understanding", "idea", 
        "reason", "focus", "imagination",
        "decision", "problem",  "knowledge", "memory", "awareness"
    ]

}



CONCRETE_CATEGORIES = {

    "objects": [
        "apple", "book", "chair", "table", "lamp",  "cup", 
        "shoe", "door",  "phone", "bag", "pen", "clock"
    ],

    "animals": [
        "dog", "cat",  "fish", "horse",  "elephant", "lion",
        "tiger", "monkey", "mouse", "rabbit", "sheep", "bear"
    ],

    "places": [
        "house", "school", "park", "river", "mountain", "street", "beach",
        "forest", "city", "market", "airport", "hospital"
    ]

}
DATA_FILE = "game_data.csv"
N_ROUNDS = 8

# -----------------------------
# UTILS
# -----------------------------

ABSTRACT_POOLS = {cat: words.copy() for cat, words in ABSTRACT_CATEGORIES.items()}
CONCRETE_POOLS = {cat: words.copy() for cat, words in CONCRETE_CATEGORIES.items()}

def init_session_state():
    if "round" not in st.session_state:
        st.session_state.round = 1
        st.session_state.score = 0
        st.session_state.board = None
        st.session_state.role = None
        st.session_state.word_type = None
        st.session_state.target_words = []
        st.session_state.bomb_word = None
        st.session_state.neutral_words = []
        st.session_state.word_roles = {}
        st.session_state.hint = ""
        st.session_state.hint_number = 0
        st.session_state.guesses = []
        st.session_state.round_finished = False
        st.session_state.start_time = None
        st.session_state.perception_rating = None
        st.session_state.golden_target = None


def get_word_type_for_round(r):
    return "abstract" if r in [1, 2, 5, 6] else "concrete"

def get_role_for_round(r):
    return "human_clue" if r % 2 == 1 else "ai_clue"

def sample_words_no_replacement(word_type):
    pools = ABSTRACT_POOLS if word_type == "abstract" else CONCRETE_POOLS

    selected_words = []

    # pick 3 words from each category (total = 9)
    for category, words in pools.items():
        if len(words) < 3:
            raise ValueError(f"Not enough words left in category {category}")

        chosen = random.sample(words, 3)
        selected_words.extend(chosen)

        # remove chosen words from pool
        for w in chosen:
            words.remove(w)

    # shuffle final board
    random.shuffle(selected_words)

    # assign roles: 4 targets, 4 neutrals, 1 bomb
    targets = selected_words[:4]
    neutrals = selected_words[4:8]
    bomb = selected_words[8]

    # pick one golden target
    golden_target = random.choice(targets)

    word_roles = {}
    for w in targets:
        if w == golden_target:
            word_roles[w] = "gold_target"   # ⭐ 3-point target
        else:
            word_roles[w] = "target"

    for w in neutrals:
        word_roles[w] = "neutral"

    word_roles[bomb] = "bomb"

    return selected_words, targets, neutrals, bomb, word_roles, golden_target




def ensure_data_file():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp", "participant_id", "round", "role", "word_type",
                "board", "targets", "bomb", "hint", "hint_number",
                "guesses", "correct", "bomb_hit", "score_change",
                "response_time_sec", "perception_rating"
            ])

def log_round(participant_id):
    ensure_data_file()
    now = datetime.utcnow().isoformat()
    guesses = st.session_state.guesses
    correct = any(g in st.session_state.target_words for g in guesses)
    bomb_hit = any(g == st.session_state.bomb_word for g in guesses)
    score_change = 0

    for g in guesses:
        if g == st.session_state.bomb_word:
            score_change -= 1
        elif g == st.session_state.golden_target:
            score_change += 3
        elif g in st.session_state.target_words:
            score_change += 1

    response_time = None
    if st.session_state.start_time is not None:
        response_time = (datetime.utcnow() - st.session_state.start_time).total_seconds()

    with open(DATA_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            now,
            participant_id,
            st.session_state.round,
            st.session_state.role,
            st.session_state.word_type,
            ";".join(st.session_state.board),
            ";".join(st.session_state.target_words),
            st.session_state.bomb_word,
            st.session_state.hint,
            st.session_state.hint_number,
            ";".join(guesses),
            int(correct),
            int(bomb_hit),
            score_change,
            response_time,
            st.session_state.perception_rating
        ])

    st.session_state.score += score_change

# -----------------------------
# OPENAI HELPERS
# -----------------------------
def call_openai_chat(system_prompt, user_prompt):
    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
    )
    return resp.choices[0].message.content.strip()

def generate_ai_hint(target_words, bomb_word, neutral_words, word_type,golden_target):
    system_prompt = (
    "You are the AI clue-giver in a Codenames-like game. "
    "Your goal is to maximize the team's score. "
    "One of the target words is a GOLDEN TARGET worth 3 points. "
    "Give ONE hint word and a number in the format HINT|N. "
    "STRICT RULE: You are NOT allowed to use any board word as a hint, "
    "and you are NOT allowed to use any morphological variant, "
    "plural form, conjugation, or derivation of any board word. "
    "For example, if the board contains 'sad', you cannot use 'sadness', "
    "'sadly', 'sadder', or anything sharing the same root. "
    "Your hint must relate to the target words and avoid the bomb word."
    )

    user_prompt = (
         f"Target words: {', '.join(target_words)}\n"
         f"Golden target (worth 3 points): {golden_target}\n"
         f"Neutral words: {', '.join(neutral_words)}\n"
         f"Bomb word: {bomb_word}\n"
         f"Word type: {word_type}\n"
    )

    raw = call_openai_chat(system_prompt, user_prompt)

    if "|" in raw:
        hint, num = raw.split("|", 1)
        hint = hint.strip()
        try:
            n = int(num.strip())
        except:
            n = len(target_words)
    else:
        hint = raw.strip()
        n = len(target_words)

    return hint, n

def ai_guess(board, hint, hint_number):
    system_prompt = (
    "You are the AI guesser in a Codenames-like game. "
    "Your goal is to maximize the team's score. "
    "One of the target words is a GOLDEN TARGET worth 3 points. "
    "You MUST output EXACTLY the number of words requested. "
    "IMPORTANT RULE: The hint will NEVER be identical to any board word "
    "or any morphological variant of a board word. "
    "Choose ONLY from the board words I give you. "
    "Output format: word1, word2, word3"
    )

    user_prompt = (
        f"Board words: {', '.join(board)}\n"
        f"Hint: {hint}\n"
        f"Number: {hint_number}\n"
        "Choose ONLY from the board. No outside words."
    )

    raw = call_openai_chat(system_prompt, user_prompt)

    model_words = [g.strip() for g in raw.split(",")]
    valid = [w for w in model_words if w in board]

    if len(valid) < hint_number:
        remaining = [w for w in board if w not in valid]
        needed = hint_number - len(valid)
        valid += random.sample(remaining, needed)

    if len(valid) > hint_number:
        valid = valid[:hint_number]

    return valid

# -----------------------------
# UI HELPERS — ULTRA‑COMPACT BOARD
# -----------------------------
def render_colored_board(board, word_roles, guesses=None, reveal_all=False, clickable=False, max_clicks=0):
    if guesses is None:
        guesses = []

    cols = st.columns(3)
    for i, w in enumerate(board):
        role = word_roles.get(w, "neutral")
        is_guessed = w in guesses

        if reveal_all or is_guessed:
            if role == "gold_target":
                color = "#d4af37"   # طلایی
            elif role == "target":
                color = "#2e7d32"   # سبز
            elif role == "bomb":
                color = "#c62828"   # قرمز
            else:
                color = "#616161"   # خاکستری
            text_color = "white"

        else:
            color = "#1976d2"
            text_color = "white"

        style = f"""
        background-color:{color};
        color:{text_color};
        border-radius:6px;
        padding:6px 4px;
        font-size:14px;
        text-align:center;
        margin-bottom:6px;
        """

        with cols[i % 3]:
            if clickable and (not st.session_state.round_finished):
                disabled = (len(guesses) >= max_clicks) or is_guessed

                if st.button(w, key=f"btn_{w}", use_container_width=True, disabled=disabled):
                    role = word_roles[w]

                    if w not in st.session_state.guesses and len(st.session_state.guesses) < max_clicks:
                        st.session_state.guesses.append(w)

                        if role == "target":
                            st.success(f"Correct! '{w}' is a target word. (+1)")
                        elif role == "neutral":
                            st.info(f"'{w}' is neutral.")
                        elif role == "bomb":
                            st.error(f"💣 Bomb! '{w}' ends the round.")
                            st.session_state.round_finished = True

                    if len(st.session_state.guesses) >= max_clicks and role != "bomb":
                        st.info("All guesses used. Round ends.")
                        st.session_state.round_finished = True

                    st.rerun()
            else:
                st.markdown(f"<div style='{style}'>{w}</div>", unsafe_allow_html=True)

# -----------------------------
# MAIN APP
# -----------------------------
def main():
    init_session_state()

    # --- GLOBAL ULTRA‑COMPACT CSS ---
    st.markdown("""
    <style>
    .block-container { padding-top: 0.8rem; padding-bottom: 0.2rem; }
    h2, h3, h4 { margin-top: 0.2rem; margin-bottom: 0.4rem; }
    </style>
    """, unsafe_allow_html=True)

    # --- TITLE (ALWAYS VISIBLE) ---
    st.markdown("<h2 style='margin: 6px 0 10px 0; text-align:center;'>  Human–AI Cooperative Word Association Game</h2>", unsafe_allow_html=True)

    # --- Welcome Screen ---
    if "started" not in st.session_state:

        st.markdown("""
        <div style='
            background-color:#f8f9fa;
            padding:18px 22px;
            border-radius:10px;
            border:1px solid #e0e0e0;
            margin-bottom:18px;
        '>

        <p style='font-size:16px; color:#444; margin-top:10px;'>
            Welcome to the Human–AI Cooperative Word Association Game!  
            In this short experiment, <b>you and an AI work together as a team</b>.  
            Each round, one of you gives a clue and the other tries to guess the target words.
        </p>

        <h4 style='margin-bottom:6px; color:#333;'>🎯 Your goal</h4>
        <p style='font-size:15px; color:#444; margin-top:0;'>
         Try to reach a total of <b>15 points</b> together with the AI by the end of all 8 rounds.
         </p>

        <h4 style='margin-bottom:6px; color:#333;'>📊 Scoring</h4>
        <ul style='font-size:15px; color:#444; margin-top:0;'>
            <li><b>+1 point</b> for each correct guess</li>
            <li><b style="color:#d4af37;">+3 points</b> for the Golden Target</li>
            <li><b>–1 point</b> if you hit the bomb word</li>
            <li>The round ends immediately if the bomb is selected</li>
        </ul>

        <h4 style='margin-bottom:6px; color:#333;'>🌀 About the rounds</h4>
        <ul style='font-size:15px; color:#444; margin-top:0;'>
            <li>The game has <b>8 rounds</b></li>
            <li>Rounds <b>1, 2, 5, 6</b> use <b>abstract words</b></li>
            <li>Rounds <b>3, 4, 7, 8</b> use <b>concrete words</b></li>
            <li>You and the AI <b>alternate roles</b> between clue-giver and guesser</li>
        </ul>

        <p style='font-size:15px; color:#444; margin-top:10px;'>
            When you're ready, click the button below to begin.
        </p>

        </div>
        """, unsafe_allow_html=True)

        # --- Stylish Start Button ---
        st.markdown("""
        <style>
        .start-btn {
            background-color:#ff4b4b;
            color:white;
            padding:10px 26px;
            font-size:17px;
            border:none;
            border-radius:8px;
            cursor:pointer;
            font-weight:600;
            box-shadow:0 2px 4px rgba(0,0,0,0.15);
        }
        .start-btn:hover {
            background-color:#e04343;
        }
        </style>
        """, unsafe_allow_html=True)

        col = st.columns([1,1,1])
        with col[1]:
            if st.button("Start Game", key="real_start_button"):
                st.session_state.started = True
                st.rerun()

        st.stop()

    # --- Participant ID Screen ---
    # --- Participant ID Screen ---
    if "participant_id" not in st.session_state:
        st.markdown("<h3>Who’s playing?</h3>", unsafe_allow_html=True)

        pid = st.text_input(
        "Type your name to begin:",
        placeholder="Enter your name..."
    )

        if st.button("🚀 Lets Go"):
            if pid.strip() == "":
               st.error("Please enter your name.")
            else:
               st.session_state.participant_id = pid.strip()
               st.rerun()

        st.stop()

       


    # --- New Round Setup ---
    if st.session_state.board is None:
        st.session_state.word_type = get_word_type_for_round(st.session_state.round)
        st.session_state.role = get_role_for_round(st.session_state.round)
        board, targets, neutrals, bomb, word_roles, golden_target = sample_words_no_replacement(st.session_state.word_type)

        st.session_state.board = board
        st.session_state.target_words = targets
        st.session_state.neutral_words = neutrals
        st.session_state.bomb_word = bomb
        st.session_state.word_roles = word_roles
        st.session_state.guesses = []
        st.session_state.round_finished = False
        st.session_state.hint = ""
        st.session_state.hint_number = 0
        st.session_state.perception_rating = None
        st.session_state.start_time = datetime.utcnow()
        st.session_state.golden_target = golden_target


    # --- Sidebar (ONLY AFTER GAME STARTS) ---
    if (
        "started" in st.session_state 
        and "participant_id" in st.session_state 
        and st.session_state.board is not None
    ):
        with st.sidebar:
            st.markdown("<h3>Game Info</h3>", unsafe_allow_html=True)
            st.markdown(f"**Participant:** {st.session_state.participant_id}")
            st.markdown(f"**Role:** {'Human clue-giver' if st.session_state.role=='human_clue' else 'Human guesser'}")
            st.markdown(f"**Word type:** {st.session_state.word_type.capitalize()}")
            st.markdown(f"**Score:** {st.session_state.score}")
            st.markdown(f"**Round:** {st.session_state.round} / {N_ROUNDS}")

    # -----------------------------
    # GAME LOGIC
    # -----------------------------
    if st.session_state.role == "human_clue":

        st.markdown("<h4>Your secret board</h4>", unsafe_allow_html=True)
        render_colored_board(
            st.session_state.board,
            st.session_state.word_roles,
            reveal_all=True,
            clickable=False
        )

        st.markdown("<h4>Your clue</h4>", unsafe_allow_html=True)

        col1, col2 = st.columns([0.7, 0.3])
        with col1:
            st.session_state.hint = st.text_input(
                "Hint:",
                value=st.session_state.hint,
                label_visibility="collapsed",
                placeholder="Enter hint..."
            )
        with col2:
            st.session_state.hint_number = st.number_input(
                "N:",
                min_value=1,
                max_value=4,
                value=st.session_state.hint_number or 1,
                label_visibility="collapsed"
            )

        if not st.session_state.round_finished and st.button("Let AI guess", use_container_width=True):
            if not st.session_state.hint:
                st.error("Please enter a hint word.")
            else:
                with st.spinner("AI is guessing..."):
                    ai_guesses = ai_guess(
                        st.session_state.board,
                        st.session_state.hint,
                        st.session_state.hint_number
                    )
                    st.session_state.guesses = ai_guesses
                    st.session_state.round_finished = True

    else:
        # -----------------------------
        # HUMAN GUESSER — BLUR OVERLAY BEFORE HINT
        # -----------------------------
        col_board, col_side = st.columns([0.62, 0.38])

        # --- RIGHT SIDE: AI HINT + BUTTON ---
        with col_side:

            if st.session_state.hint == "":
                st.markdown("<h4>Get a clue</h4>", unsafe_allow_html=True)
                st.markdown(
                    "<p style='font-size:14px;color:#555;'>First, take a moment to look at the words on the board. "
                    "When you're ready, ask the AI for a clue.</p>",
                    unsafe_allow_html=True
                )
                if st.button("Ask AI for a clue", use_container_width=True):
                    with st.spinner("AI is generating a clue..."):
                        hint, num = generate_ai_hint(
                            st.session_state.target_words,
                            st.session_state.bomb_word,
                            st.session_state.neutral_words,
                            st.session_state.word_type,
                            st.session_state.golden_target
                        )
                        st.session_state.hint = hint
                        st.session_state.hint_number = num
                        st.rerun()

            if st.session_state.hint:
                st.markdown(
                    f"""
                    <div style="background-color:#fff3cd;border-left:4px solid #ffca2c;
                    padding:12px;border-radius:8px;margin:0 0 12px 0;
                    box-shadow:0 1px 3px rgba(0,0,0,0.1);">

                    <span style="font-size:18px;font-weight:800;color:#7a5a00;
                    display:block;margin-bottom:4px;">🔍 AI Hint</span>

                    <span style="font-size:22px;font-weight:900;color:#5c4400;
                    display:block;margin-bottom:4px;">{st.session_state.hint.upper()}</span>

                    <span style="font-size:16px;font-weight:700;color:#7a5a00;
                    display:block;">{st.session_state.hint_number} word(s)</span>

                    </div>
                    """,
                    unsafe_allow_html=True
                )

                st.info("Click on the cards to make your guesses.")

        # --- LEFT SIDE: BOARD ---
        with col_board:
            st.markdown("<h4>Board</h4>", unsafe_allow_html=True)

            if st.session_state.hint == "":
                # BLURRED, LOCKED BOARD (OPTION C)
                st.markdown(
                    """
                    <div style="position:relative;">
                        <div style="filter: blur(2px); opacity:0.7;">
                    """,
                    unsafe_allow_html=True
                )

                render_colored_board(
                    st.session_state.board,
                    st.session_state.word_roles,
                    guesses=st.session_state.guesses,
                    reveal_all=False,
                    clickable=False,
                    max_clicks=0
                )

                st.markdown(
                    """
                        </div>
                        <div style="
                            position:absolute;
                            top:50%;
                            left:50%;
                            transform:translate(-50%, -50%);
                            background:rgba(255,255,255,0.8);
                            padding:8px 14px;
                            border-radius:10px;
                            box-shadow:0 1px 3px rgba(0,0,0,0.2);
                            font-size:13px;
                            color:#333;
                            text-align:center;
                        ">
                         
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            else:
                # ACTIVE BOARD AFTER HINT
                render_colored_board(
                    st.session_state.board,
                    st.session_state.word_roles,
                    guesses=st.session_state.guesses,
                    reveal_all=False,
                    clickable=True,
                    max_clicks=st.session_state.hint_number if st.session_state.hint_number > 0 else 1
                )

                if (
                    not st.session_state.round_finished
                    and st.session_state.hint
                    and len(st.session_state.guesses) >= st.session_state.hint_number
                ):
                    st.info("All guesses used. Round ends.")
                    st.session_state.round_finished = True

    # -----------------------------
    # ROUND SUMMARY (ULTRA‑COMPACT + SIDE-BY-SIDE)
    # -----------------------------
    if st.session_state.round_finished:

        col_sum, col_rate = st.columns([0.55, 0.45])

        # -----------------------------
        # LEFT — SUMMARY
        # -----------------------------
        with col_sum:
            st.markdown("<h4 style='margin:4px 0;'>Round summary</h4>", unsafe_allow_html=True)

            guesses = st.session_state.guesses
            correct = any(g in st.session_state.target_words for g in guesses)
            bomb_hit = any(g == st.session_state.bomb_word for g in guesses)
            score_change = 0

            if bomb_hit:
                score_change = -1
            else:
                for g in guesses:
                    if g == st.session_state.golden_target:
                        score_change += 3
                    elif g in st.session_state.target_words:
                        score_change += 1
            

            if st.session_state.role == "human_clue":
                html = """
                <div style="background-color:#eef3ff;padding:8px;border-radius:6px;
                border:1px solid #c7d4ff;margin-bottom:8px;">
                    <div style="font-size:13px;font-weight:700;color:#1a3e8a;margin-bottom:2px;">
                        AI guesses
                    </div>
                    <div style="font-size:12px;color:#333;">__GUESSES__</div>
                </div>

                <div style="background-color:#eef3ff;padding:8px;border-radius:6px;
                border:1px solid #c7d4ff;margin-bottom:8px;">
                    <div style="font-size:13px;font-weight:700;color:#1a3e8a;margin-bottom:2px;">
                        Score change
                    </div>
                    <div style="font-size:18px;font-weight:800;color:#0d47a1;">__SCORE__</div>
                </div>
                """

                html = html.replace("__GUESSES__", ", ".join(st.session_state.guesses))

                st.markdown(f"**Golden target:** ⭐ {st.session_state.golden_target}")
                html = html.replace("__SCORE__", str(score_change))

                st.markdown(html, unsafe_allow_html=True)

            else:
                st.markdown("<h5 style='margin:4px 0;'>Board revealed</h5>", unsafe_allow_html=True)

                render_colored_board(
                    st.session_state.board,
                    st.session_state.word_roles,
                    guesses=st.session_state.guesses,
                    reveal_all=True,
                    clickable=False
                )

                st.markdown(
                    f"<div style='font-size:12px;margin-top:4px;'>Your guesses: "
                    f"<b>{', '.join(st.session_state.guesses)}</b></div>",
                    unsafe_allow_html=True
                )

                html = """
                <div style="background-color:#eef3ff;padding:8px;border-radius:6px;
                border:1px solid #c7d4ff;margin-top:8px;">
                    <div style="font-size:13px;font-weight:700;color:#1a3e8a;margin-bottom:2px;">
                        Score change
                    </div>
                    <div style="font-size:18px;font-weight:800;color:#0d47a1;">__SCORE__</div>
                </div>
                """

                html = html.replace("__SCORE__", str(score_change))
                st.markdown(f"**Golden target:** ⭐ {st.session_state.golden_target}")
                st.markdown(html, unsafe_allow_html=True)

        # -----------------------------
        # RIGHT — PERCEPTION RATING
        # -----------------------------
        with col_rate:
            st.markdown("<h4 style='margin:4px 0;'>Perception rating</h4>", unsafe_allow_html=True)

            st.session_state.perception_rating = st.slider(
                "How much did you feel understood by the AI?",
                1, 5, 3,
                label_visibility="collapsed"
            )

            if st.button("Save round and continue", use_container_width=True):
                log_round(st.session_state.participant_id)

                if st.session_state.round >= N_ROUNDS:
                    st.success("Game finished. Thank you!")
                else:
                    st.session_state.round += 1
                    st.session_state.board = None
                    st.rerun()

# -----------------------------
# MAIN CALL
# -----------------------------
if __name__ == "__main__":
    main()
