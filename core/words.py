# Each round's board is fixed in advance -- both the 16-word set and every
# word's target/neutral/bomb role are decided here, not drawn at random.
# Only the on-screen grid position is randomized at deal time (see
# sample_fixed_round_words in core/game_logic.py). One board per round,
# matched 1:1 by round number.
#
# Word type ("abstract"/"concrete") for a few words here (marked below)
# wasn't looked up against a concreteness-norms corpus the way most of this
# list was -- each board is specified to be exactly 8 abstract + 8 concrete
# words, so those few were inferred by whichever value makes that board's
# count come out to 8+8 (every other word's type was already fixed by the
# corpus lookup, leaving only one consistent answer). Confirm these read
# correctly: Antenna, Risk, Destiny, Lantern, Bottle. (Silence and Force
# were in this list too, but have since been swapped out for Boredom and
# Effort -- both unambiguously abstract, so neither needs the same
# confirmation.)
ROUND_BOARDS = {
    1: {
        "id": "B01",
        "name": "Communication, performance, and social commitment",
        "target": [
            ("Honesty", "abstract"),
            ("Promise", "abstract"),
            ("Mirror", "concrete"),
            ("Ring", "concrete"),
            ("Whistle", "concrete"),
        ],
        "neutral": [
            ("Boredom", "abstract"),
            ("Loyalty", "abstract"),
            ("Doubt", "abstract"),
            ("Idea", "abstract"),
            ("Mood", "abstract"),
            ("Chocolate", "concrete"),
            ("Chair", "concrete"),
            ("Stadium", "concrete"),
            ("Pen", "concrete"),
        ],
        "bomb": [
            ("Blame", "abstract"),
            ("Police", "concrete"),
        ],
    },
    2: {
        "id": "B02",
        "name": "Direction, movement, and decision-making",
        "target": [
            ("Purpose", "abstract"),
            ("Effort", "abstract"),
            ("Compass", "concrete"),
            ("Lever", "concrete"),
            ("Antenna", "concrete"),
        ],
        "neutral": [
            ("Risk", "abstract"),  # inferred, see module docstring
            ("Theory", "abstract"),
            ("Destiny", "abstract"),  # inferred, see module docstring
            ("Focus", "abstract"),
            ("Guilt", "abstract"),
            ("Car", "concrete"),
            ("Castle", "concrete"),
            ("Clock", "concrete"),
            ("Helmet", "concrete"),
        ],
        "bomb": [
            ("Freedom", "abstract"),
            ("Robot", "concrete"),
        ],
    },
    3: {
        "id": "B03",
        "name": "Emotion, nature, and animals",
        "target": [
            ("Kindness", "abstract"),
            ("Peace", "abstract"),
            ("Penguin", "concrete"),
            ("Honey", "concrete"),
            ("Spider", "concrete"),
        ],
        "neutral": [
            ("Pride", "abstract"),
            ("Anger", "abstract"),
            ("Belief", "abstract"),
            ("Secret", "abstract"),
            ("Shoe", "concrete"),
            ("Lantern", "concrete"),  # inferred, see module docstring
            ("Pumpkin", "concrete"),
            ("Lens", "concrete"),
            ("Luck", "abstract"),
        ],
        "bomb": [
            ("Resolution", "abstract"),
            ("Mouse", "concrete"),
        ],
    },
    4: {
        "id": "B04",
        "name": "Knowledge, private life, and everyday settings",
        "target": [
            ("Privacy", "abstract"),
            ("Memory", "abstract"),
            ("Hospital", "concrete"),
            ("Garden", "concrete"),
            ("Pillow", "concrete"),
        ],
        "neutral": [
            ("Justice", "abstract"),
            ("Courage", "abstract"),
            ("Value", "abstract"),
            ("Duty", "abstract"),
            ("Concept", "abstract"),
            ("Bridge", "concrete"),
            ("Bucket", "concrete"),
            ("Bottle", "concrete"),  # inferred, see module docstring
            ("Sofa", "concrete"),
        ],
        "bomb": [
            ("Method", "abstract"),
            ("Moon", "concrete"),
        ],
    },
}


def all_round_board_words():
    """Every word used anywhere in the 4 fixed round boards, lowercased --
    used to keep the tutorial's own small word set disjoint from the real
    experiment's words."""
    words = set()
    for board in ROUND_BOARDS.values():
        for role in ("target", "neutral", "bomb"):
            for word, _word_type in board[role]:
                words.add(word.lower())
    return words
