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

VALID_CONDITIONS = frozenset({"baseline", "adaptive"})
DEFAULT_CONDITION = "adaptive"
DEBUG_MODE = False

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
AI_API_TIMEOUT_SECONDS = 20
MEDAL_POINTS = {
    "gold": 5,
    "silver": 4,
    "none": 0,
}
AI_REROLLS_PER_GAME = 2
HUMAN_REROLLS_PER_GAME = 2
