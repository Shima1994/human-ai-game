import json
import os

HINT_MODEL_NAME = "gpt-4o"
GUESS_MODEL_NAME = "gpt-4o"
REFLECTION_MODEL_NAME = "gpt-4o"

# Canonical build metadata. Deployments should set the environment-backed
# values to their platform's exact identifiers; blank means unavailable and is
# preferable to fabricated provenance.
EXPERIMENT_VERSION = os.getenv("EXPERIMENT_VERSION", "pilot-v1")
SCHEMA_VERSION = "2.0.0"
CODE_COMMIT = next(
    (
        os.getenv(name, "").strip()
        for name in ("CODE_COMMIT", "GITHUB_SHA", "STREAMLIT_GIT_COMMIT", "RENDER_GIT_COMMIT")
        if os.getenv(name, "").strip()
    ),
    "",
)
DEPLOYMENT_VERSION = os.getenv("DEPLOYMENT_VERSION", "").strip()
MODEL_IDENTIFIER = json.dumps(
    {
        "hint": HINT_MODEL_NAME,
        "guess": GUESS_MODEL_NAME,
        "reflection": REFLECTION_MODEL_NAME,
    },
    sort_keys=True,
)
CONDITION_ASSIGNMENT_VERSION = "alternating-registered-sessions-v1"

# Bump this by hand whenever core/words.py's ROUND_BOARDS word content
# changes (a swapped word, an abstract/concrete correction, a typo fix,
# etc.). A board's template id (e.g. "B01") stays the same across such an
# edit, so without this a session played before a correction and one played
# after are otherwise indistinguishable in the logged data.
BOARD_MATERIAL_VERSION = "v2026-09-26"

VALID_CONDITIONS = frozenset({"baseline", "adaptive"})
DEFAULT_CONDITION = "adaptive"
DEBUG_MODE = True

N_ROUNDS = 4
MAX_TEAM_SCORE = 20
TEAM_GOAL_SCORE = 12
MAX_HINT_NUMBER = 5
BOARD_SIZE = 16
TARGET_COUNT = 5
BOMB_COUNT = 2
MAX_INTERACTIONS_PER_ROUND = 3
MAX_SKIPS_PER_ROUND = 2
CLUE_TIMER_SECONDS = 90
# Giving a clue is harder than guessing one, so it gets more time.
CLUE_GIVER_TIMER_SECONDS = 120
GUESSER_TIMER_SECONDS = CLUE_TIMER_SECONDS
# Once both round skips are used up, a further timeout no longer has a skip
# to consume -- the participant instead gets one last short window to submit
# a guess/clue before the round ends automatically as a loss. This bounds
# how long an indefinitely-stalling participant can be paid for.
FINAL_GUESS_TIMER_SECONDS = 30
AI_API_TIMEOUT_SECONDS = 20
# The clue-giver's own decision timer (unlike the guesser's) doesn't touch
# the shared skip budget at all for their first timeout each round -- they
# may not yet know the timer exists. From the second clue-giver timeout in
# the same round onward, it costs a completed interaction instead (the
# round's 3-interaction budget, same as a real guess would).
CLUE_GIVER_FREE_TIMEOUTS_PER_ROUND = 1
MEDAL_POINTS = {
    "gold": 5,
    "silver": 4,
    "none": 0,
}
