import random
from datetime import datetime

import streamlit as st


def get_word_type_for_round(round_number):
    return "abstract" if round_number in [1, 2, 5, 6] else "concrete"


def get_role_for_round(round_number):
    return "human_clue" if round_number % 2 == 1 else "ai_clue"


def sample_words_no_replacement(word_type):
    pools = (
        st.session_state.abstract_pools
        if word_type == "abstract"
        else st.session_state.concrete_pools
    )

    selected_words = []
    selected_pairs = []
    for category, words in pools.items():
        if len(words) < 3:
            raise ValueError(
                f"Not enough words left in category {category} for word_type={word_type}"
            )

        chosen = random.sample(words, 3)
        selected_words.extend(chosen)
        selected_pairs.extend((word, category) for word in chosen)
        for word in chosen:
            words.remove(word)

    targets, neutrals, bomb = _assign_balanced_roles(selected_pairs)
    golden_target = random.choice(targets)

    word_roles = {}
    for word in targets:
        word_roles[word] = "gold_target" if word == golden_target else "target"
    for word in neutrals:
        word_roles[word] = "neutral"
    word_roles[bomb] = "bomb"

    return selected_words, targets, neutrals, bomb, word_roles, golden_target


def _category_count(words_with_categories):
    counts = {}
    for _, category in words_with_categories:
        counts[category] = counts.get(category, 0) + 1
    return counts


def _is_balanced_group(words_with_categories, max_per_category):
    counts = _category_count(words_with_categories)
    return all(count <= max_per_category for count in counts.values())


def _assign_balanced_roles(selected_pairs):
    shuffled = selected_pairs[:]
    for _ in range(250):
        random.shuffle(shuffled)
        target_pairs = shuffled[:4]
        neutral_pairs = shuffled[4:8]
        bomb_pair = shuffled[8]

        if _is_balanced_group(target_pairs, 2) and _is_balanced_group(neutral_pairs, 2):
            targets = [word for word, _ in target_pairs]
            neutrals = [word for word, _ in neutral_pairs]
            bomb = bomb_pair[0]
            return targets, neutrals, bomb

    targets = [word for word, _ in shuffled[:4]]
    neutrals = [word for word, _ in shuffled[4:8]]
    bomb = shuffled[8][0]
    return targets, neutrals, bomb


def setup_new_round():
    word_type = get_word_type_for_round(st.session_state.round)
    role = get_role_for_round(st.session_state.round)
    board, targets, neutrals, bomb, word_roles, golden_target = sample_words_no_replacement(
        word_type
    )

    st.session_state.word_type = word_type
    st.session_state.role = role
    st.session_state.board = board
    st.session_state.target_words = targets
    st.session_state.neutral_words = neutrals
    st.session_state.bomb_word = bomb
    st.session_state.word_roles = word_roles
    st.session_state.golden_target = golden_target
    st.session_state.guesses = []
    st.session_state.round_finished = False
    st.session_state.hint = ""
    st.session_state.hint_number = 1
    st.session_state.perception_rating = 3
    st.session_state.previous_hint = None
    st.session_state.start_time = datetime.utcnow()
    st.session_state.last_score_change = 0


def compute_score_change(guesses, target_words, golden_target, bomb_word):
    if bomb_word in guesses:
        return -1

    score_change = 0
    for guess in guesses:
        if guess == golden_target:
            score_change += 3
        elif guess in target_words:
            score_change += 1
    return score_change


def finish_round():
    st.session_state.round_finished = True
    st.session_state.last_score_change = compute_score_change(
        st.session_state.guesses,
        st.session_state.target_words,
        st.session_state.golden_target,
        st.session_state.bomb_word,
    )
