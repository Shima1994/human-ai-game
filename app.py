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
        st.session_state.previous_hint = None

        # Global rerolls for the whole game (not per round)
        st.session_state.ai_rerolls = 2      # AI (as guesser) can ask for a new hint at most 2 times in the whole game
        st.session_state.human_rerolls = 2   # Human (as guesser) can ask AI for a new hint at most 2 times in the whole game

        # Pools stored in session_state to avoid repetition across rounds
        st.session_state.abstract_pools = {cat: words.copy() for cat, words in ABSTRACT_CATEGORIES.items()}
        st.session_state.concrete_pools = {cat: words.copy() for cat, words in CONCRETE_CATEGORIES.items()}

def get_word_type_for_round(r):
    return "abstract" if r in [1, 2, 5, 6] else "concrete"

def get_role_for_round(r):
    return "human_clue" if r % 2 == 1 else "ai_clue"

def sample_words_no_replacement(word_type):
    """
    Sample 3 words from each of the 3 categories (total 9),
    without replacement across rounds, using pools stored in session_state.
    """
    if word_type == "abstract":
        pools = st.session_state.abstract_pools
    else:
        pools = st.session_state.concrete_pools

    selected_words = []

    # pick 3 words from each category (total = 9)
    for category, words in pools.items():
        if len(words) < 3:
            raise ValueError(f"Not enough words left in category {category} for word_type={word_type}")

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

def generate_ai_hint(target_words, bomb_word, neutral_words, word_type, golden_target):
    system_prompt = (
        "You are the AI clue-giver in a Codenames-like cooperative word game. "
        "You play together with a human as a team. "
        "Your goal is to maximize the team's score by giving a single, smart clue. "
        "One of the target words is a GOLDEN TARGET worth 3 points. "
        "You must give ONE hint word and a number in the format HINT|N. "
        "STRICT RULES:\n"
        "1) You are NOT allowed to use any board word as a hint.\n"
        "2) You are NOT allowed to use any morphological variant, plural form, "
        "   conjugation, or derivation of any board word.\n"
        "   For example, if the board contains 'sad', you cannot use 'sadness', "
        "   'sadly', 'sadder', or anything sharing the same root.\n"
        "3) Your hint must relate to the target words and avoid the bomb word.\n"
        "4) Try to choose a clue that helps the human connect as many target words "
        "   as possible, especially the golden target, while avoiding the bomb.\n"
        "5) Do not explain your reasoning. Only output the hint and the number.\n"
    )

    user_prompt = (
        f"Target words: {', '.join(target_words)}\n"
        f"Golden target (worth 3 points): {golden_target}\n"
        f"Neutral words: {', '.join(neutral_words)}\n"
        f"Bomb word: {bomb_word}\n"
        f"Word type: {word_type}\n"
        "Return exactly one hint and one number in the format: HINT|N"
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

def generate_ai_hint_reroll(
    target_words, bomb_word, neutral_words, word_type, golden_target, previous_hint
):
    system_prompt = (
        "You are the AI clue-giver in a Codenames-like cooperative game. "
        "The human player has requested a NEW hint because the previous hint was too difficult. "
        "You MUST provide a completely different hint from the previous one.\n\n"
        "STRICT RULES:\n"
        "1) DO NOT repeat the previous hint.\n"
        "2) DO NOT use any board word or any morphological variant of a board word.\n"
        "3) DO NOT use any morphological variant of the previous hint.\n"
        "4) The new hint MUST be easier, clearer, and more helpful.\n"
        "5) Output format: HINT|N\n"
        "6) Do NOT explain your reasoning.\n"
    )

    user_prompt = (
        f"Previous hint: {previous_hint}\n"
        f"Target words: {', '.join(target_words)}\n"
        f"Golden target (worth 3 points): {golden_target}\n"
        f"Neutral words: {', '.join(neutral_words)}\n"
        f"Bomb word: {bomb_word}\n"
        f"Word type: {word_type}\n"
        "Provide a NEW hint that is different from the previous one.\n"
        "Return exactly one hint and one number in the format: HINT|N"
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

def ai_guess(board, hint, hint_number, remaining_rerolls):
    """
    AI is the guesser. It can either:
    - Output exactly 'REROLL_HINT' (uppercase) if the hint is too ambiguous AND remaining_rerolls > 0
    - Or output a comma-separated list of guesses from the board, e.g.: word1, word2, word3
    """
    system_prompt = (
        "You are the AI guesser in a Codenames-like cooperative word game. "
        "You and a human are playing together as a team. "
        "Your goal is to maximize the team's score by choosing the best possible guesses.\n\n"
        "There is a set of board words. Some of them are target words (including one GOLDEN TARGET worth 3 points), "
        "some are neutral, and one is a bomb word that ends the round with a penalty.\n\n"
        "You will receive:\n"
        "- The list of board words\n"
        "- A single hint word\n"
        "- A number N (how many guesses you are allowed to make)\n\n"
        "IMPORTANT RULES:\n"
        "1) You MUST choose ONLY from the given board words.\n"
        "2) You MUST output EXACTLY the number of words requested (N), unless you decide to request a new hint.\n"
        "3) The hint will NEVER be identical to any board word or any morphological variant of a board word.\n\n"
        "SPECIAL OPTION (REQUESTING A NEW HINT):\n"
        "If you think the hint is too ambiguous, unclear, or not helpful enough, and you still have at least one "
        "remaining chance to request a new hint, you may output EXACTLY the single token:\n"
        "REROLL_HINT\n"
        "This means: you are asking the human clue-giver to provide a different hint.\n\n"
        "If you choose to request a new hint, do NOT output any guesses. Only output 'REROLL_HINT'.\n"
        "Otherwise, output your guesses as a comma-separated list of board words, e.g.: word1, word2, word3\n"
        "Do not explain your reasoning."
    )

    user_prompt = (
        f"Board words: {', '.join(board)}\n"
        f"Hint: {hint}\n"
        f"Number of guesses (N): {hint_number}\n"
        f"Remaining chances to request a new hint: {remaining_rerolls}\n\n"
        "If the hint is too hard or ambiguous AND remaining chances > 0, you may output exactly:\n"
        "REROLL_HINT\n"
        "Otherwise, output exactly N guesses as a comma-separated list of board words.\n"
        "Examples of valid outputs:\n"
        "- love, fear, joy\n"
        "- house, school\n"
        "- REROLL_HINT\n"
        "Do not add any extra text."
    )

    raw = call_openai_chat(system_prompt, user_prompt).strip()

    # If the model explicitly requests a new hint
    if raw.upper() == "REROLL_HINT":
        return ["__REROLL_HINT__"]

    model_words = [g.strip() for g in raw.split(",") if g.strip()]
    valid = [w for w in model_words if w in board]

    if len(valid) < hint_number:
        remaining = [w for w in board if w not in valid]
        if remaining:
            needed = hint_number - len(valid)
            if needed > len(remaining):
                needed = len(remaining)
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

        <h4 style='margin-bottom:6px; color:#333;'>♻️ Extra hint chances</h4>
        <ul style='font-size:15px; color:#444; margin-top:0;'>
            <li>The human guesser can request a <b>new AI hint up to 2 times</b> in the whole game.</li>
            <li>The AI guesser can also request a <b>new human hint up to 2 times</b> in the whole game.</li>
            <li>Each unused hint chance becomes a <b>bonus point at the end of the game</b> (maximum +4).</li>
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
        st.session_state.previous_hint = None

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
            total_rerolls_left = st.session_state.ai_rerolls + st.session_state.human_rerolls
            st.markdown(f"**Unused hint chances (global):** {total_rerolls_left} / 4")

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
                        st.session_state.hint_number,
                        st.session_state.ai_rerolls
                    )

                    # Check if AI requested a new hint instead of guessing
                    if len(ai_guesses) == 1 and ai_guesses[0] == "__REROLL_HINT__":
                        if st.session_state.ai_rerolls > 0:
                            st.session_state.ai_rerolls -= 1
                            st.info(
                                "The AI found your hint too difficult and requested a new hint. "
                                "You can adjust your hint and click 'Let AI guess' again."
                            )
                        else:
                            st.warning(
                                "The AI tried to request a new hint, but there are no remaining AI rerolls. "
                                "Please keep your current hint or change it manually and try again."
                            )
                    else:
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

            # Human reroll button (global 2 chances in the whole game)
            if st.session_state.hint and st.session_state.human_rerolls > 0:
                if st.button(f"🔄 I need a different hint ({st.session_state.human_rerolls} left)"):
                    st.session_state.human_rerolls -= 1
                    st.session_state.previous_hint = st.session_state.hint

                    with st.spinner("AI is generating a new clue..."):
                        hint, num = generate_ai_hint_reroll(
                            st.session_state.target_words,
                            st.session_state.bomb_word,
                            st.session_state.neutral_words,
                            st.session_state.word_type,
                            st.session_state.golden_target,
                            st.session_state.previous_hint
                        )
                        st.session_state.hint = hint
                        st.session_state.hint_number = num
                        st.rerun()

            if st.session_state.hint:
                prev_hint_html = (
                    f"""
                    <div style="margin-bottom:6px;">
                        <span style="font-size:13px;font-weight:600;color:#6c757d;">Previous hint:</span><br>
                        <span style="font-size:16px;font-weight:700;color:#8a6d3b;">
                            {st.session_state.previous_hint.upper() if st.session_state.previous_hint else '—'}
                        </span>
                    </div>
                    """
                )

                st.markdown(
                    f"""
                    <div style="background-color:#fff3cd;border-left:4px solid #ffca2c;
                    padding:12px;border-radius:8px;margin:0 0 12px 0;
                    box-shadow:0 1px 3px rgba(0,0,0,0.1);">

                    <span style="font-size:18px;font-weight:800;color:#7a5a00;
                    display:block;margin-bottom:4px;">🔍 AI Hint</span>

                    {prev_hint_html}

                    <div style="margin-top:4px;">
                        <span style="font-size:14px;font-weight:600;color:#5c4400;">Current hint:</span><br>
                        <span style="font-size:22px;font-weight:900;color:#5c4400;
                        display:block;margin-bottom:4px;letter-spacing:0.5px;">
                            {st.session_state.hint.upper()}
                        </span>
                    </div>

                    <span style="font-size:15px;font-weight:700;color:#7a5a00;
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
                # BLURRED, LOCKED BOARD
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

            total_rerolls_left = st.session_state.ai_rerolls + st.session_state.human_rerolls

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
                        Score change (this round, without unused-hint bonus)
                    </div>
                    <div style="font-size:18px;font-weight:800;color:#0d47a1;">__SCORE__</div>
                </div>

                <div style="background-color:#f3f6ff;padding:8px;border-radius:6px;
                border:1px solid #d0d8ff;margin-bottom:8px;">
                    <div style="font-size:13px;font-weight:700;color:#1a237e;margin-bottom:2px;">
                        Unused hint chances (global)
                    </div>
                    <div style="font-size:13px;color:#1a237e;">
                        __REROLLS__ / 4 (bonus will be added at the end of the game)
                    </div>
                </div>
                """

                html = html.replace("__GUESSES__", ", ".join(st.session_state.guesses) if st.session_state.guesses else "No guesses")
                html = html.replace("__SCORE__", str(score_change))
                html = html.replace("__REROLLS__", str(total_rerolls_left))

                st.markdown(f"**Golden target:** ⭐ {st.session_state.golden_target}")
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
                    f"<b>{', '.join(st.session_state.guesses) if st.session_state.guesses else 'No guesses'}</b></div>",
                    unsafe_allow_html=True
                )

                html = """
                <div style="background-color:#eef3ff;padding:8px;border-radius:6px;
                border:1px solid #c7d4ff;margin-top:8px;">
                    <div style="font-size:13px;font-weight:700;color:#1a3e8a;margin-bottom:2px;">
                        Score change (this round, without unused-hint bonus)
                    </div>
                    <div style="font-size:18px;font-weight:800;color:#0d47a1;">__SCORE__</div>
                </div>

                <div style="background-color:#f3f6ff;padding:8px;border-radius:6px;
                border:1px solid #d0d8ff;margin-top:8px;">
                    <div style="font-size:13px;font-weight:700;color:#1a237e;margin-bottom:2px;">
                        Unused hint chances (global)
                    </div>
                    <div style="font-size:13px;color:#1a237e;">
                        __REROLLS__ / 4 (bonus will be added at the end of the game)
                    </div>
                </div>
                """

                html = html.replace("__SCORE__", str(score_change))
                html = html.replace("__REROLLS__", str(total_rerolls_left))

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
                # Log this round (without unused-hint bonus)
                log_round(st.session_state.participant_id)

                if st.session_state.round >= N_ROUNDS:
                    # End of the game: add bonus from unused hint chances
                    unused_rerolls = st.session_state.ai_rerolls + st.session_state.human_rerolls
                    st.session_state.score += unused_rerolls

                    st.success(
                        f"Game finished. Thank you for playing! "
                        f"You earned +{unused_rerolls} bonus point(s) from unused hint chances."
                    )

                    st.markdown(f"**Final team score (including bonus):** {st.session_state.score}")

                    if st.session_state.score >= 15:
                        st.success("🎉 Congratulations! You reached the team goal of 15 points or more!")
                    else:
                        st.info("You didn't reach 15 points this time. You can play again and try to beat the score!")

                else:
                    # Go to next round
                    st.session_state.round += 1
                    st.session_state.board = None
                    st.rerun()

# -----------------------------
# MAIN CALL
# -----------------------------
if __name__ == "__main__":
    main()
