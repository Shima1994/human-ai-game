import base64
import csv
import io
import json
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import streamlit as st

from core.constants import DATA_FILE, INTERACTION_DATA_FILE
from core.game_logic import compute_score_change


ROUND_LOG_FIELDS = [
    "session_id",
    "timestamp_utc",
    "participant_id",
    "round",
    "role",
    "word_type",
    "board",
    "targets",
    "bomb",
    "neutral_words",
    "clues_used",
    "guesses",
    "turns",
    "skips",
    "targets_found",
    "any_target_correct",
    "all_targets_found",
    "bomb_hit",
    "medal",
    "score_change",
    "round_duration_sec",
    "perception_rating_end",
    "ai_round_reflection",
    "human_round_feedback",
]


INTERACTION_LOG_FIELDS = [
    "session_id",
    "timestamp_utc",
    "participant_id",
    "round",
    "role",
    "word_type",
    "turn",
    "clue_giver",
    "guesser",
    "hint",
    "hint_number",
    "intended_targets",
    "hint_explanation",
    "guesses",
    "correct_guesses",
    "missed_intended_targets",
    "extra_correct_guesses",
    "neutral_guesses",
    "bomb_guess",
    "outcome",
    "skipped",
    "skipped_by",
    "bomb_hit",
    "round_medal",
    "round_success",
    "ai_understanding_rating_before",
    "ai_understanding_rating_after",
    "hint_response_time_sec",
    "hint_attempts",
    "hint_used_fallback",
    "guess_response_time_sec",
    "hint_raw_response",
    "guess_raw_response",
    "interaction_recorded_at",
]


def get_data_file():
    return DATA_FILE


def _header_matches(data_file, expected_fields):
    try:
        with data_file.open("r", newline="", encoding="utf-8") as file:
            reader = csv.reader(file)
            existing = next(reader, [])
    except (FileNotFoundError, StopIteration):
        return False
    return list(existing) == list(expected_fields)


def ensure_data_file():
    data_file = get_data_file()
    data_file.parent.mkdir(parents=True, exist_ok=True)
    if not data_file.exists() or not _header_matches(data_file, ROUND_LOG_FIELDS):
        with data_file.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(ROUND_LOG_FIELDS)
    return data_file


def get_interaction_data_file():
    return INTERACTION_DATA_FILE


def ensure_interaction_data_file():
    data_file = get_interaction_data_file()
    data_file.parent.mkdir(parents=True, exist_ok=True)
    if not data_file.exists() or not _header_matches(data_file, INTERACTION_LOG_FIELDS):
        with data_file.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(INTERACTION_LOG_FIELDS)
    return data_file


def _csv_line(values):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(values)
    return buffer.getvalue()


def _secret_value(key, default=""):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


def _github_storage_config():
    token = _secret_value("GITHUB_TOKEN")
    repo = _secret_value("GITHUB_REPO")
    branch = _secret_value("GITHUB_BRANCH", "main")
    if not token or not repo:
        return None
    return {
        "token": token,
        "repo": repo,
        "branch": branch,
        "round_path": _secret_value(
            "GITHUB_ROUND_CSV_PATH",
            "data/game_rounds.csv",
        ),
        "interaction_path": _secret_value(
            "GITHUB_INTERACTION_CSV_PATH",
            "data/game_interactions.csv",
        ),
    }


def _github_request(url, token, method="GET", payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _append_to_github_csv_once(path, header, rows, message):
    config = _github_storage_config()
    if not config:
        return

    token = config["token"]
    encoded_path = "/".join(part.replace(" ", "%20") for part in path.split("/"))
    url = (
        f"https://api.github.com/repos/{config['repo']}/contents/{encoded_path}"
        f"?ref={config['branch']}"
    )
    content = _csv_line(header)
    sha = None

    try:
        existing = _github_request(url, token)
        sha = existing.get("sha")
        raw_content = base64.b64decode(existing.get("content", "")).decode("utf-8")
        content = raw_content
        if not content.endswith("\n"):
            content += "\n"
    except HTTPError as error:
        if error.code != 404:
            raise

    for row in rows:
        content += _csv_line(row)

    payload = {
        "message": message,
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": config["branch"],
    }
    if sha:
        payload["sha"] = sha

    put_url = f"https://api.github.com/repos/{config['repo']}/contents/{encoded_path}"
    _github_request(put_url, token, method="PUT", payload=payload)


def _append_to_github_csv(path, header, rows, message):
    for attempt in range(3):
        try:
            _append_to_github_csv_once(path, header, rows, message)
            return
        except HTTPError as error:
            if error.code != 409 or attempt == 2:
                raise


def append_remote_csv(round_row, interaction_rows):
    try:
        config = _github_storage_config()
        if not config:
            st.session_state.remote_log_status = "local_only"
            st.session_state.remote_log_error = (
                "GitHub logging is not configured. Add GITHUB_TOKEN and GITHUB_REPO "
                "to Streamlit secrets to save public runs durably."
            )
            return
        _append_to_github_csv(
            config["round_path"],
            ROUND_LOG_FIELDS,
            [round_row],
            "Append word game round data",
        )
        if interaction_rows:
            _append_to_github_csv(
                config["interaction_path"],
                INTERACTION_LOG_FIELDS,
                interaction_rows,
                "Append word game interaction data",
            )
        st.session_state.remote_log_status = "github_saved"
        st.session_state.remote_log_error = ""
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        st.session_state.remote_log_status = "github_failed"
        st.session_state.remote_log_error = str(error)


def clean_interaction_history(history):
    clean_items = []
    for index, item in enumerate(history, start=1):
        guesses = list(item.get("guesses", []))
        correct_guesses = list(item.get("correct_guesses", []))
        intended_targets = list(item.get("intended_targets", []))
        clean_items.append(
            {
                "turn": index,
                "clue_giver": item.get("clue_giver", ""),
                "guesser": item.get("guesser", ""),
                "hint": item.get("hint", ""),
                "hint_number": int(item.get("hint_number", 0) or 0),
                "intended_targets": intended_targets,
                "hint_explanation": item.get("hint_explanation", ""),
                "guesses": guesses,
                "correct_guesses": correct_guesses,
                "missed_intended_targets": [
                    word for word in intended_targets if word not in correct_guesses
                ],
                "extra_correct_guesses": [
                    word for word in correct_guesses if word not in intended_targets
                ],
                "neutral_guesses": list(item.get("neutral_guesses", [])),
                "bomb_guess": item.get("bomb_guess"),
                "outcome": item.get("outcome", "correct" if correct_guesses else "wrong"),
                "skipped": bool(item.get("skipped", False)),
                "skipped_by": item.get("skipped_by", ""),
                "bomb_hit": bool(item.get("bomb_hit", False)),
                "ai_understanding_rating_before": item.get("ai_understanding_rating_before"),
                "ai_understanding_rating_after": item.get("ai_understanding_rating_after"),
                "hint_raw_response": item.get("hint_raw_response", ""),
                "hint_response_time_sec": item.get("hint_response_time_sec"),
                "hint_attempts": item.get("hint_attempts"),
                "hint_used_fallback": bool(item.get("hint_used_fallback", False)),
                "guess_raw_response": item.get("guess_raw_response", ""),
                "guess_response_time_sec": item.get("guess_response_time_sec"),
                "recorded_at": item.get("recorded_at", ""),
            }
        )
    return clean_items


def _format_optional_float(value):
    if value is None or value == "":
        return ""
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return ""


def log_round(participant_id):
    data_file = ensure_data_file()
    interaction_data_file = ensure_interaction_data_file()
    timestamp = datetime.utcnow().isoformat()

    guesses = st.session_state.guesses
    correct = any(guess in st.session_state.target_words for guess in guesses)
    bomb_hit = any(guess == st.session_state.bomb_word for guess in guesses)
    score_change = compute_score_change(
        guesses,
        st.session_state.target_words,
        st.session_state.bomb_word,
        st.session_state.round_interactions,
    )
    clean_history = clean_interaction_history(st.session_state.interaction_history)

    response_time = None
    if st.session_state.start_time is not None:
        response_time = (datetime.utcnow() - st.session_state.start_time).total_seconds()

    clues_used = ";".join(
        item.get("hint", "") for item in clean_history if item.get("hint")
    )

    session_id = st.session_state.get("session_id", "")

    round_row = [
        session_id,
        timestamp,
        participant_id,
        st.session_state.round,
        st.session_state.role,
        st.session_state.word_type,
        ";".join(st.session_state.board),
        ";".join(st.session_state.target_words),
        st.session_state.bomb_word,
        ";".join(st.session_state.neutral_words),
        clues_used,
        ";".join(guesses),
        st.session_state.round_interactions,
        st.session_state.get("round_skips", 0),
        len(st.session_state.found_targets),
        int(correct),
        int(st.session_state.round_success),
        int(bomb_hit),
        st.session_state.round_medal,
        score_change,
        _format_optional_float(response_time),
        st.session_state.perception_rating,
        st.session_state.get("ai_round_reflection", ""),
        st.session_state.get("human_round_feedback", ""),
    ]

    interaction_rows = []
    for item in clean_history:
        interaction_rows.append(
            [
                session_id,
                timestamp,
                participant_id,
                st.session_state.round,
                st.session_state.role,
                st.session_state.word_type,
                item["turn"],
                item["clue_giver"],
                item["guesser"],
                item["hint"],
                item["hint_number"],
                ";".join(item["intended_targets"]),
                item["hint_explanation"],
                ";".join(item["guesses"]),
                ";".join(item["correct_guesses"]),
                ";".join(item["missed_intended_targets"]),
                ";".join(item["extra_correct_guesses"]),
                ";".join(item["neutral_guesses"]),
                item["bomb_guess"] or "",
                item["outcome"],
                int(item["skipped"]),
                item["skipped_by"],
                int(item["bomb_hit"]),
                st.session_state.round_medal,
                int(st.session_state.round_success),
                item["ai_understanding_rating_before"] if item["ai_understanding_rating_before"] is not None else "",
                item["ai_understanding_rating_after"] if item["ai_understanding_rating_after"] is not None else "",
                _format_optional_float(item["hint_response_time_sec"]),
                item["hint_attempts"] if item["hint_attempts"] is not None else "",
                int(item["hint_used_fallback"]),
                _format_optional_float(item["guess_response_time_sec"]),
                item["hint_raw_response"] or "",
                item["guess_raw_response"] or "",
                item["recorded_at"],
            ]
        )

    with data_file.open("a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(round_row)

    with interaction_data_file.open("a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerows(interaction_rows)

    append_remote_csv(round_row, interaction_rows)

    st.session_state.last_score_change = score_change
    st.session_state.score += score_change
