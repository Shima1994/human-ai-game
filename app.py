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
ABSTRACT_WORDS = [
    "freedom", "justice", "emotion", "love", "power", "trust", "fear", "hope",
    "honor", "belief", "memory", "dream", "logic", "reason", "faith", "desire",
    "value", "culture", "identity", "morality"
]

CONCRETE_WORDS = [
    "apple", "car", "table", "dog", "chair", "phone", "book", "house",
    "tree", "river", "mountain", "cup", "door", "window", "shoe", "bottle",
    "lamp", "pencil", "computer", "street"
]

DATA_FILE = "game_data.csv"
N_ROUNDS = 8

# -----------------------------
# UTILS
# -----------------------------
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

def get_word_type_for_round(r):
    return "abstract" if r in [1, 2, 5, 6] else "concrete"

def get_role_for_round(r):
    return "human_clue" if r % 2 == 1 else "ai_clue"

def sample_words(word_type):
    pool = ABSTRACT_WORDS if word_type == "abstract" else CONCRETE_WORDS
    targets = random.sample(pool, 4)
    remaining = [w for w in pool if w not in targets]
    neutrals = random.sample(remaining, 4)
    remaining2 = [w for w in remaining if w not in neutrals]
    if not remaining2:
        remaining2 = neutrals
    bomb = random.choice(remaining2)
    board = targets + neutrals + [bomb]
    random.shuffle(board)
    word_roles = {}
    for w in targets:
        word_roles[w] = "target"
    for w in neutrals:
        word_roles[w] = "neutral"
    word_roles[bomb] = "bomb"
    return board, targets, neutrals, bomb, word_roles

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
    score_change = -1 if bomb_hit else sum(1 for g in guesses if g in st.session_state.target_words)

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

# ⭐ این تابع گم شده بود — اینجاست
def generate_ai_hint(target_words, bomb_word, neutral_words, word_type):
    system_prompt = (
        "You are the AI clue-giver in a Codenames-like game. "
        "Give ONE hint word and a number in the format HINT|N. "
        "The hint must relate to the target words and avoid the bomb word."
    )

    user_prompt = (
        f"Target words: {', '.join(target_words)}\n"
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

# ⭐ نسخهٔ جدید — AI دقیقاً همان تعداد را حدس می‌زند
def ai_guess(board, hint, hint_number):
    system_prompt = (
        "You are the AI guesser in a Codenames-like game. "
        "You MUST output EXACTLY the number of words requested. "
        "All guessed words MUST be chosen ONLY from the board words I give you. "
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
# UI HELPERS
# -----------------------------
def render_colored_board(board, word_roles, guesses=None, reveal_all=False, clickable=False, max_clicks=0):
    if guesses is None:
        guesses = []

    cols = st.columns(3)
    for i, w in enumerate(board):
        role = word_roles.get(w, "neutral")
        is_guessed = w in guesses

        if reveal_all or is_guessed:
            if role == "target":
                color = "#2e7d32"
            elif role == "bomb":
                color = "#c62828"
            else:
                color = "#616161"
            text_color = "white"
        else:
            color = "#1976d2"
            text_color = "white"

        button_label = w
        style = f"background-color:{color}; color:{text_color}; border-radius:8px; padding:12px; border:none;"

        with cols[i % 3]:
            if clickable and (not st.session_state.round_finished):
                disabled = (len(guesses) >= max_clicks) or is_guessed

                if st.button(button_label, key=f"btn_{w}", use_container_width=True, disabled=disabled):
                    role = word_roles[w]

                    if w not in st.session_state.guesses and len(st.session_state.guesses) < max_clicks:
                        st.session_state.guesses.append(w)

                        if role == "target":
                            st.success(f"Correct! '{w}' is a target word. (+1 point)")
                        elif role == "neutral":
                            st.info(f"'{w}' is a neutral word. (0 points)")
                        elif role == "bomb":
                            st.error(f"💣 Bomb! '{w}' ends the round. (-1 point)")
                            st.session_state.round_finished = True

                    if len(st.session_state.guesses) >= max_clicks and role != "bomb":
                        st.info("You have used all your guesses for this hint. Round ends.")
                        st.session_state.round_finished = True

                    st.rerun()
            else:
                st.markdown(
                    f"<div style='{style}; text-align:center; margin-bottom:8px;'>{button_label}</div>",
                    unsafe_allow_html=True
                )
# -----------------------------
# MAIN APP
# -----------------------------
def main():
    init_session_state()

    # --- Global CSS ---
    st.markdown("""
    <style>

    .summary-box {
        background-color: #f0f4ff;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #c7d4ff;
        box-shadow: 0 2px 6px rgba(0,0,0,0.1);
        margin-top: 20px;
        margin-bottom: 25px;
    }

    .summary-title {
        color: #1a3e8a;
        font-size: 20px;
        font-weight: 700;
        margin-bottom: 8px;
    }

    .summary-text {
        color: #333;
        font-size: 16px;
        margin-bottom: 12px;
    }

    .summary-score {
        color: #0d47a1;
        font-size: 22px;
        font-weight: 800;
    }

    </style>
    """, unsafe_allow_html=True)

    # --- Welcome Screen ---
    if "started" not in st.session_state:
        st.title("Human–AI Cooperative Word Association Game")

        st.markdown("""
### Welcome to the Human–AI Cooperative Word Association Game

In this game, you and an AI work together as a team. Each round, one of you gives a clue and the other guesses the target words.

Your goal is to guess as many correct words as possible and avoid mistakes.

---

### How scoring works:
- You get **+1 point** for each correct guess.  
- You get **–1 point** if you hit the **bomb word**.  
- The round ends when you guess the word.

---

### About the rounds:
- The game has **8 rounds**.  
- Rounds **1, 2, 5, 6** use **abstract words**.  
- Rounds **3, 4, 7, 8** use **concrete words**.  
- You and the AI take turns giving clues and guessing.

---

Click **Start Game** to begin.
""")

        if st.button("Start Game"):
            st.session_state.started = True
            st.rerun()

        st.stop()

    # --- Participant ID Screen ---
    if "participant_id" not in st.session_state:
        st.title("Participant Information")

        pid = st.text_input("Please enter your Participant ID:")

        if pid:
            st.session_state.participant_id = pid
            st.rerun()

        st.stop()

    # --- New Round ---
    if st.session_state.board is None:
        st.session_state.word_type = get_word_type_for_round(st.session_state.round)
        st.session_state.role = get_role_for_round(st.session_state.round)
        board, targets, neutrals, bomb, word_roles = sample_words(st.session_state.word_type)
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

    # --- Sidebar ---
    with st.sidebar:
        st.header("Game Info")
        st.markdown(f"**Participant:** {st.session_state.participant_id}")
        st.markdown(f"**Role:** {'Human clue-giver' if st.session_state.role=='human_clue' else 'Human guesser'}")
        st.markdown(f"**Word type:** {st.session_state.word_type.capitalize()}")
        st.markdown(f"**Score:** {st.session_state.score}")
        st.markdown(f"**Round:** {st.session_state.round} / {N_ROUNDS}")

    # --- Main Title ---
    st.title("Human–AI Cooperative Word Association Game")

    # -----------------------------
    # GAME LOGIC
    # -----------------------------
    if st.session_state.role == "human_clue":
        st.subheader("Your secret information")
        st.subheader("Board (with colors)")
        render_colored_board(
            st.session_state.board,
            st.session_state.word_roles,
            reveal_all=True,
            clickable=False
        )

        st.subheader("Your clue for the AI")
        st.session_state.hint = st.text_input("Hint word:", value=st.session_state.hint)
        st.session_state.hint_number = st.number_input(
            "Number of related words:",
            min_value=1, max_value=4,
            value=st.session_state.hint_number or 1
        )

        if not st.session_state.round_finished and st.button("Let AI guess"):
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
        st.subheader("Board")
        if st.session_state.hint == "":
            if st.button("Ask AI for a clue"):
                with st.spinner("AI is generating a clue..."):
                    hint, num = generate_ai_hint(
                        st.session_state.target_words,
                        st.session_state.bomb_word,
                        st.session_state.neutral_words,
                        st.session_state.word_type
                    )
                    st.session_state.hint = hint
                    st.session_state.hint_number = num

        if st.session_state.hint:
           st.markdown(f"""
<div style="background-color:#fff3cd;border-left:6px solid #ffca2c;padding:18px;border-radius:10px;margin:15px 0;box-shadow:0 2px 6px rgba(0,0,0,0.1);">
<span style="font-size:16px;font-weight:800;color:#7a5a00;display:block;margin-bottom:8px;">🔍 AI Hint</span>
<span style="font-size:20px;font-weight:900;color:#5c4400;display:block;margin-bottom:6px;">{st.session_state.hint.upper()}</span>
<span style="font-size:18px;font-weight:700;color:#7a5a00;display:block;">{st.session_state.hint_number} word(s)</span>
</div>
""", unsafe_allow_html=True)

           st.info("Click on the cards to make your guesses.")





        render_colored_board(
            st.session_state.board,
            st.session_state.word_roles,
            guesses=st.session_state.guesses,
            reveal_all=False,
            clickable=True,
            max_clicks=st.session_state.hint_number if st.session_state.hint_number > 0 else 1
        )

        if (not st.session_state.round_finished
            and st.session_state.hint
            and len(st.session_state.guesses) >= st.session_state.hint_number):
            st.info("You used all your guesses for this hint. Round ends.")
            st.session_state.round_finished = True
    # -----------------------------
    # ROUND SUMMARY
    # -----------------------------
    if st.session_state.round_finished:
        st.subheader("Round summary")

        guesses = st.session_state.guesses
        correct = any(g in st.session_state.target_words for g in guesses)
        bomb_hit = any(g == st.session_state.bomb_word for g in guesses)
        score_change = -1 if bomb_hit else sum(1 for g in guesses if g in st.session_state.target_words)

        if st.session_state.role == "human_clue":
            html = """
            <div class="summary-box">
                <div class="summary-title">AI guesses</div>
                <div class="summary-text">__GUESSES__</div>
            </div>

            <div class="summary-box">
                <div class="summary-title">Score change this round</div>
                <div class="summary-score">__SCORE__</div>
            </div>
            """

            html = html.replace("__GUESSES__", ", ".join(st.session_state.guesses))
            html = html.replace("__SCORE__", str(score_change))

            st.markdown(html, unsafe_allow_html=True)

        else:
            st.markdown("**Board with roles revealed:**")
            render_colored_board(
                st.session_state.board,
                st.session_state.word_roles,
                guesses=st.session_state.guesses,
                reveal_all=True,
                clickable=False
            )

            st.markdown(f"**Your guesses:** {', '.join(st.session_state.guesses)}")

            html = """
            <div class="summary-box">
                <div class="summary-title">Score change this round</div>
                <div class="summary-score">__SCORE__</div>
            </div>
            """

            html = html.replace("__SCORE__", str(score_change))
            st.markdown(html, unsafe_allow_html=True)

        st.subheader("Perception rating")
        st.session_state.perception_rating = st.slider(
            "How much did you feel understood by the AI this round?",
            1, 5, 3
        )

        if st.button("Save round and go to next"):
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
