"""Prolific integration: URL parameters, completion codes, attention checks.

Prolific opens the study at the configured external URL with three query
parameters appended (set the study URL in Prolific to
``https://<app>/?PROLIFIC_PID={{%PROLIFIC_PID%}}&STUDY_ID={{%STUDY_ID%}}&SESSION_ID={{%SESSION_ID%}}``).
Finished participants are sent back to Prolific with the study's fixed
completion code, configured in Prolific and mirrored here as a secret.
"""

import os
import re
from urllib.parse import quote

import streamlit as st


PROLIFIC_COMPLETE_URL = "https://app.prolific.com/submissions/complete?cc={code}"

# Prolific IDs are short alphanumeric strings; anything else (a placeholder
# like "{{%PROLIFIC_PID%}}" that was never substituted, an injection attempt)
# is kept out of the database rather than stored as a real participant ID.
_PROLIFIC_ID_PATTERN = re.compile(r"^[A-Za-z0-9]{1,64}$")

# Instructional manipulation checks, worded per Prolific's attention-check
# policy: the instruction is inside the question itself, needs no memory of
# earlier pages, and has exactly one correct answer. The study is longer than
# five minutes, so a submission may only be rejected when BOTH are failed.
ATTENTION_CHECK_PROFILE_QUESTION = (
    "This question checks that you are reading carefully. Please select \"A few times a month\"."
)
ATTENTION_CHECK_PROFILE_OPTIONS = [
    "Never",
    "Less than once a month",
    "A few times a month",
    "A few times a week",
    "Daily",
]
ATTENTION_CHECK_PROFILE_ANSWER = "A few times a month"

ATTENTION_CHECK_POST_GAME_ID = "attention_check"
ATTENTION_CHECK_POST_GAME_QUESTION = (
    "This statement checks that you are reading carefully. Please select 2 for this statement."
)
ATTENTION_CHECK_POST_GAME_ANSWER = 2


def read_setting(name):
    value = os.getenv(name, "").strip()
    if value:
        return value
    try:
        return str(st.secrets.get(name, "") or "").strip()
    except Exception:
        return ""


def prolific_completion_code():
    """The study's 'completed' code from Prolific (blank when not configured)."""
    return read_setting("PROLIFIC_COMPLETION_CODE")


def prolific_complete_url(code):
    cleaned = str(code or "").strip()
    return PROLIFIC_COMPLETE_URL.format(code=quote(cleaned, safe="")) if cleaned else ""


def _query_param(name):
    try:
        value = st.query_params.get(name, "")
    except Exception:
        return ""
    if isinstance(value, list):
        value = value[0] if value else ""
    value = str(value or "").strip()
    return value if _PROLIFIC_ID_PATTERN.match(value) else ""


def prolific_params_from_url():
    return {
        "prolific_pid": _query_param("PROLIFIC_PID"),
        "prolific_study_id": _query_param("STUDY_ID"),
        "prolific_session_id": _query_param("SESSION_ID"),
    }


RUN_TYPES = ("participant", "pilot", "test")


def resolve_run_type(prolific_pid, debug_shortcut_used=False):
    """Which kind of session this is, so test and pilot data never mix with
    real participant data. Set RUN_TYPE ("pilot" or "test") as a secret or
    environment variable to label a whole deployment; otherwise a session
    is a participant session only when it arrived from Prolific with a PID.
    The debug shortcut always marks a session as a test."""
    if debug_shortcut_used:
        return "test"
    configured = read_setting("RUN_TYPE").lower()
    if configured in ("pilot", "test"):
        return configured
    return "participant" if prolific_pid else "test"


def provisional_analysis_eligible(run_type, completed, attention_failures):
    """A first, automatic eligibility flag. The final inclusion decision is
    made at analysis time (attention checks, exceptionally fast completion,
    technical problems), so analysis may override it."""
    return bool(run_type == "participant" and completed and attention_failures < 2)


def attention_checks_failed(profile_answer, post_game_answer):
    """Number of failed checks; an unanswered check counts as not yet taken."""
    failed = 0
    if profile_answer not in (None, "") and profile_answer != ATTENTION_CHECK_PROFILE_ANSWER:
        failed += 1
    if post_game_answer not in (None, "") and post_game_answer != ATTENTION_CHECK_POST_GAME_ANSWER:
        failed += 1
    return failed
