import base64
import csv
import io
import json
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import streamlit as st

from core.constants import (
    DATA_FILE,
    EVENTS_DATA_FILE,
    GUESS_MODEL_NAME,
    HINT_MODEL_NAME,
    INTERACTION_DATA_FILE,
    N_ROUNDS,
    REFLECTION_MODEL_NAME,
    ROUNDS_DATA_FILE,
    SESSIONS_DATA_FILE,
    TURNS_DATA_FILE,
)
from core.game_logic import compute_score_change


ROUND_LOG_FIELDS = [
    "session_id",
    "timestamp_utc",
    "participant_id",
    "condition",
    "starting_role",
    "round",
    "round_number",
    "round_role",
    "role",
    "word_type",
    "board_template_type",
    "word_type_per_card",
    "board",
    "all_board_words",
    "targets",
    "target_words",
    "target_word_types",
    "bomb",
    "bomb_words",
    "bomb_word_types",
    "neutral_words",
    "neutral_word_types",
    "clues_used",
    "guesses",
    "guessed_word_types",
    "correct_guess_word_types",
    "incorrect_guess_word_types",
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
    "alignment_status",
    "error_type",
    "human_understanding_rating",
    "human_relationship_type",
    "human_explanation_raw",
    "human_explanation_is_valid",
    "human_explanation_blocked_reason",
    "ai_relationship_type",
    "ai_explanation_raw",
    "ai_explanation_sanitized",
    "ai_explanation_is_valid",
    "ai_explanation_blocked_reason",
    "ai_explanation",
    "reflection_source",
    "reflection_rating",
    "reflection_relationship_type",
    "reflection_explanation_raw",
    "reflection_explanation_is_valid",
    "reflection_blocked_reason",
]


INTERACTION_LOG_FIELDS = [
    "session_id",
    "timestamp_utc",
    "participant_id",
    "condition",
    "starting_role",
    "round",
    "round_number",
    "round_role",
    "role",
    "word_type",
    "board_template_type",
    "word_type_per_card",
    "target_word_types",
    "neutral_word_types",
    "bomb_word_types",
    "turn",
    "turn_number",
    "clue_giver",
    "guesser",
    "hint",
    "clue",
    "hint_number",
    "clue_number",
    "intended_targets",
    "intended_cards",
    "hint_explanation",
    "guesses",
    "guessed_cards",
    "guessed_word_types",
    "correct_guesses",
    "correct_guess_word_types",
    "incorrect_guesses",
    "incorrect_guess_word_types",
    "missed_intended_targets",
    "extra_correct_guesses",
    "neutral_guesses",
    "bomb_guess",
    "outcome",
    "alignment_status",
    "error_type",
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
    "human_understanding_rating",
    "human_relationship_type",
    "human_explanation_raw",
    "human_explanation_is_valid",
    "human_explanation_blocked_reason",
    "ai_relationship_type",
    "ai_explanation_raw",
    "ai_explanation_sanitized",
    "ai_explanation_is_valid",
    "ai_explanation_blocked_reason",
    "ai_explanation",
    "reflection_source",
    "reflection_rating",
    "reflection_relationship_type",
    "reflection_explanation_raw",
    "reflection_explanation_is_valid",
    "reflection_blocked_reason",
    "interaction_recorded_at",
]


SESSIONS_LOG_FIELDS = [
    "participant_id",
    "session_id",
    "condition",
    "starting_role",
    "start_time",
    "end_time",
    "completed",
    "consent_given",
    "total_rounds_planned",
    "total_rounds_completed",
    "total_turns_completed",
    "final_total_score",
    "user_agent",
    "device_type",
    "screen_size",
    "browser_language",
    "completion_code",
]


ROUNDS_LOG_FIELDS = [
    "participant_id",
    "session_id",
    "condition",
    "round_number",
    "round_role",
    "clue_giver",
    "guesser",
    "board_template_type",
    "all_board_words",
    "word_type_per_card",
    "target_words",
    "target_word_types",
    "neutral_words",
    "neutral_word_types",
    "bomb_words",
    "bomb_word_types",
    "remaining_targets_start",
    "remaining_targets_end",
    "number_of_turns",
    "round_score",
    "medal",
    "round_completed",
    "round_terminated_by_bomb",
    "bomb_selected",
    "selected_bomb_words",
    "round_start_time",
    "round_end_time",
    "round_duration_seconds",
]


TURNS_LOG_FIELDS = [
    "participant_id",
    "session_id",
    "condition",
    "round_number",
    "turn_number",
    "clue_giver",
    "guesser",
    "clue",
    "clue_number",
    "intended_cards",
    "intended_word_types",
    "guessed_cards",
    "guessed_word_types",
    "correct_guesses",
    "correct_guess_word_types",
    "incorrect_guesses",
    "incorrect_guess_word_types",
    "neutral_guesses",
    "neutral_guess_word_types",
    "bomb_guesses",
    "bomb_guess_word_types",
    "remaining_targets_before_turn",
    "remaining_targets_after_turn",
    "hit_rate",
    "target_yield",
    "jaccard_alignment",
    "alignment_status",
    "error_type",
    "turn_score_delta",
    "turn_start_time",
    "turn_end_time",
    "turn_duration_seconds",
    "reflection_shown",
    "reflection_source",
    "human_understanding_rating",
    "human_relationship_type",
    "human_explanation_raw",
    "human_explanation_sanitized",
    "human_explanation_is_valid",
    "human_explanation_blocked_reason",
    "ai_relationship_type",
    "ai_explanation_raw",
    "ai_explanation_sanitized",
    "ai_explanation_is_valid",
    "ai_explanation_blocked_reason",
    "ai_explanation",
    "repair_applied_to_next_prompt",
    "repair_context_used",
    "llm_model",
    "llm_temperature",
    "llm_prompt_version",
    "llm_system_prompt_version",
    "llm_response_raw",
    "llm_response_parsed",
    "llm_error",
    "llm_latency_seconds",
]


EVENTS_LOG_FIELDS = [
    "participant_id",
    "session_id",
    "condition",
    "timestamp",
    "event_type",
    "round_number",
    "turn_number",
    "event_payload",
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


def _ensure_csv_fields(data_file, expected_fields):
    data_file.parent.mkdir(parents=True, exist_ok=True)
    if not data_file.exists():
        with data_file.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(expected_fields)
        return

    try:
        with data_file.open("r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            existing_fields = reader.fieldnames or []
            if existing_fields == list(expected_fields):
                return
            rows = list(reader)
    except (FileNotFoundError, StopIteration):
        rows = []

    with data_file.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=expected_fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in expected_fields})


def ensure_data_file():
    data_file = get_data_file()
    _ensure_csv_fields(data_file, ROUND_LOG_FIELDS)
    return data_file


def get_interaction_data_file():
    return INTERACTION_DATA_FILE


def ensure_interaction_data_file():
    data_file = get_interaction_data_file()
    _ensure_csv_fields(data_file, INTERACTION_LOG_FIELDS)
    return data_file


def ensure_sessions_data_file():
    _ensure_csv_fields(SESSIONS_DATA_FILE, SESSIONS_LOG_FIELDS)
    return SESSIONS_DATA_FILE


def ensure_rounds_data_file():
    _ensure_csv_fields(ROUNDS_DATA_FILE, ROUNDS_LOG_FIELDS)
    return ROUNDS_DATA_FILE


def ensure_turns_data_file():
    _ensure_csv_fields(TURNS_DATA_FILE, TURNS_LOG_FIELDS)
    return TURNS_DATA_FILE


def ensure_events_data_file():
    _ensure_csv_fields(EVENTS_DATA_FILE, EVENTS_LOG_FIELDS)
    return EVENTS_DATA_FILE


def _json(value):
    return json.dumps(value if value is not None else [], ensure_ascii=False)


def _json_obj(value):
    return json.dumps(value if value is not None else {}, ensure_ascii=False)


def _append_dict_row(data_file, fields, row):
    missing = [field for field in fields if field not in row]
    if missing:
        raise ValueError(f"Missing required log fields for {data_file}: {missing}")
    with data_file.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writerow(row)


def _upsert_dict_row(data_file, fields, row, key_fields):
    missing = [field for field in fields if field not in row]
    if missing:
        raise ValueError(f"Missing required log fields for {data_file}: {missing}")
    rows = []
    if data_file.exists():
        with data_file.open("r", newline="", encoding="utf-8") as file:
            rows = list(csv.DictReader(file))
    key = tuple(str(row.get(field, "")) for field in key_fields)
    replaced = False
    for index, existing in enumerate(rows):
        existing_key = tuple(str(existing.get(field, "")) for field in key_fields)
        if existing_key == key:
            rows[index] = {field: row.get(field, "") for field in fields}
            replaced = True
            break
    if not replaced:
        rows.append({field: row.get(field, "") for field in fields})
    with data_file.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _csv_line(values):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(values)
    return buffer.getvalue()


def _migrate_csv_content(content, expected_fields):
    reader = csv.DictReader(io.StringIO(content))
    existing_fields = reader.fieldnames or []
    if existing_fields == list(expected_fields):
        return content if content.endswith("\n") else f"{content}\n"

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=expected_fields, extrasaction="ignore")
    writer.writeheader()
    for row in reader:
        writer.writerow({field: row.get(field, "") for field in expected_fields})
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
        content = _migrate_csv_content(raw_content, header)
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
                "incorrect_guesses": [
                    word for word in guesses if word not in correct_guesses
                ],
                "missed_intended_targets": [
                    word for word in intended_targets if word not in correct_guesses
                ],
                "extra_correct_guesses": [
                    word for word in correct_guesses if word not in intended_targets
                ],
                "neutral_guesses": list(item.get("neutral_guesses", [])),
                "bomb_guesses": list(item.get("bomb_guesses", [])),
                "bomb_guess": item.get("bomb_guess"),
                "outcome": item.get("outcome", "correct" if correct_guesses else "wrong"),
                "alignment_status": item.get("alignment_status", ""),
                "error_type": item.get("error_type", "none"),
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
                "reflection_rating": item.get("reflection_rating", ""),
                "reflection_relationship_type": item.get("reflection_relationship_type", ""),
                "reflection_explanation_raw": item.get("reflection_explanation_raw", ""),
                "reflection_explanation_is_valid": item.get("reflection_explanation_is_valid", ""),
                "reflection_blocked_reason": item.get("reflection_blocked_reason", ""),
                "human_understanding_rating": item.get("human_understanding_rating", ""),
                "human_relationship_type": item.get("human_relationship_type", ""),
                "human_explanation_raw": item.get("human_explanation_raw", ""),
                "human_explanation_is_valid": item.get("human_explanation_is_valid", ""),
                "human_explanation_blocked_reason": item.get("human_explanation_blocked_reason", ""),
                "ai_relationship_type": item.get("ai_relationship_type", ""),
                "ai_explanation_raw": item.get("ai_explanation_raw", ""),
                "ai_explanation_sanitized": item.get("ai_explanation_sanitized", item.get("ai_explanation", "")),
                "ai_explanation_is_valid": item.get("ai_explanation_is_valid", ""),
                "ai_explanation_blocked_reason": item.get("ai_explanation_blocked_reason", ""),
                "ai_explanation": item.get("ai_explanation_sanitized", item.get("ai_explanation", "")),
                "reflection_source": item.get("reflection_source", ""),
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


def _types_for_words(words, word_type_per_card):
    missing = [word for word in words or [] if not word_type_per_card.get(word)]
    if missing:
        raise ValueError(
            "Cannot log word types because these words have no word_type: "
            + ", ".join(missing)
        )
    return [word_type_per_card[word] for word in words or []]


def _join_word_types(words, word_type_per_card):
    return ";".join(_types_for_words(words, word_type_per_card))


def _format_word_type_per_card(board, word_type_per_card):
    _types_for_words(board or [], word_type_per_card)
    return json.dumps(
        {word: word_type_per_card[word] for word in board or []},
        ensure_ascii=False,
    )


def _iso_now():
    return datetime.utcnow().isoformat()


def _session_row(completed=False):
    history = st.session_state.get("interaction_history", [])
    total_completed = len(st.session_state.get("ai_round_summaries", []))
    if st.session_state.get("round_finished"):
        total_completed = max(total_completed, int(st.session_state.get("round", 0) or 0))
    return {
        "participant_id": st.session_state.get("participant_id", ""),
        "session_id": st.session_state.get("session_id", ""),
        "condition": st.session_state.get("condition", "baseline"),
        "starting_role": st.session_state.get("starting_role", ""),
        "start_time": st.session_state.get("session_start_time", ""),
        "end_time": st.session_state.get("session_end_time", "") if completed else "",
        "completed": str(bool(completed)).lower(),
        "consent_given": str(bool(st.session_state.get("consent_given", False))).lower(),
        "total_rounds_planned": N_ROUNDS,
        "total_rounds_completed": total_completed,
        "total_turns_completed": sum(
            int(summary.get("turns", 0) or 0)
            for summary in st.session_state.get("ai_round_summaries", [])
        )
        + (len(history) if not st.session_state.get("round_finished") else 0),
        "final_total_score": st.session_state.get("score", 0),
        "user_agent": st.session_state.get("user_agent", "unknown"),
        "device_type": st.session_state.get("device_type", "unknown"),
        "screen_size": st.session_state.get("screen_size", "unknown"),
        "browser_language": st.session_state.get("browser_language", "unknown"),
        "completion_code": st.session_state.get("completion_code", ""),
    }


def log_session_state(completed=False):
    data_file = ensure_sessions_data_file()
    if completed and not st.session_state.get("session_end_time"):
        st.session_state.session_end_time = _iso_now()
    _upsert_dict_row(
        data_file,
        SESSIONS_LOG_FIELDS,
        _session_row(completed=completed),
        ["participant_id", "session_id"],
    )


def log_event(event_type, payload=None, round_number=None, turn_number=None):
    data_file = ensure_events_data_file()
    row = {
        "participant_id": st.session_state.get("participant_id", ""),
        "session_id": st.session_state.get("session_id", ""),
        "condition": st.session_state.get("condition", "baseline"),
        "timestamp": _iso_now(),
        "event_type": event_type,
        "round_number": round_number if round_number is not None else st.session_state.get("round", ""),
        "turn_number": turn_number if turn_number is not None else st.session_state.get("round_interactions", ""),
        "event_payload": _json_obj(payload or {}),
    }
    _append_dict_row(data_file, EVENTS_LOG_FIELDS, row)


def initialize_session_log(participant_id):
    if st.session_state.get("session_log_initialized"):
        return
    st.session_state.participant_id = participant_id
    st.session_state.consent_given = True
    log_session_state(completed=False)
    log_event("session_started", {"starting_role": st.session_state.get("starting_role", "")}, round_number="", turn_number="")
    log_event("consent_given", {}, round_number="", turn_number="")
    log_event("instruction_viewed", {}, round_number="", turn_number="")
    st.session_state.session_log_initialized = True


def _role_pair(round_role):
    return (
        ("human", "ai") if round_role == "human_clue" else ("ai", "human")
    )


def _round_analysis_row(participant_id, timestamp, score_change):
    word_type_per_card = st.session_state.get("word_type_per_card", {})
    bomb_words = st.session_state.get("bomb_words") or [st.session_state.bomb_word]
    selected_bombs = [
        guess for guess in st.session_state.get("guesses", []) if guess in bomb_words
    ]
    clue_giver, guesser = _role_pair(st.session_state.get("role", ""))
    round_start = st.session_state.get("round_start_time") or st.session_state.get("start_time")
    if hasattr(round_start, "isoformat"):
        round_start = round_start.isoformat()
    round_end = timestamp
    duration = ""
    if round_start:
        try:
            duration = f"{(datetime.fromisoformat(round_end) - datetime.fromisoformat(round_start)).total_seconds():.3f}"
        except ValueError:
            duration = ""
    return {
        "participant_id": participant_id,
        "session_id": st.session_state.get("session_id", ""),
        "condition": st.session_state.get("condition", "baseline"),
        "round_number": st.session_state.round,
        "round_role": st.session_state.role,
        "clue_giver": clue_giver,
        "guesser": guesser,
        "board_template_type": st.session_state.get("board_template_type", ""),
        "all_board_words": _json(st.session_state.board),
        "word_type_per_card": _format_word_type_per_card(st.session_state.board, word_type_per_card),
        "target_words": _json(st.session_state.target_words),
        "target_word_types": _json(_types_for_words(st.session_state.target_words, word_type_per_card)),
        "neutral_words": _json(st.session_state.neutral_words),
        "neutral_word_types": _json(_types_for_words(st.session_state.neutral_words, word_type_per_card)),
        "bomb_words": _json(bomb_words),
        "bomb_word_types": _json(_types_for_words(bomb_words, word_type_per_card)),
        "remaining_targets_start": _json(st.session_state.target_words),
        "remaining_targets_end": _json(
            [word for word in st.session_state.target_words if word not in st.session_state.found_targets]
        ),
        "number_of_turns": st.session_state.round_interactions,
        "round_score": score_change,
        "medal": st.session_state.round_medal,
        "round_completed": str(bool(st.session_state.round_finished)).lower(),
        "round_terminated_by_bomb": str(bool(st.session_state.round_bomb_hit)).lower(),
        "bomb_selected": str(bool(selected_bombs)).lower(),
        "selected_bomb_words": _json(selected_bombs),
        "round_start_time": round_start or "",
        "round_end_time": round_end,
        "round_duration_seconds": duration,
    }


def _llm_fields_for_turn(item):
    clue_giver = item.get("clue_giver", "")
    if clue_giver == "ai":
        raw = item.get("hint_raw_response", "")
        latency = item.get("hint_response_time_sec")
        parsed = {
            "clue": item.get("hint", ""),
            "number": item.get("hint_number", ""),
            "targets": item.get("intended_targets", []),
        }
        model = HINT_MODEL_NAME
        temperature = "0.55"
        prompt_version = "hint_v1"
        system_version = "hint_system_v1"
    else:
        raw = item.get("guess_raw_response", "")
        latency = item.get("guess_response_time_sec")
        parsed = {"guesses": item.get("guesses", [])}
        model = GUESS_MODEL_NAME
        temperature = "0.2"
        prompt_version = "guess_v1"
        system_version = "guess_system_v1"
    error = raw if str(raw).startswith("<api_error:") else ""
    return {
        "llm_model": model,
        "llm_temperature": temperature,
        "llm_prompt_version": prompt_version,
        "llm_system_prompt_version": system_version,
        "llm_response_raw": raw,
        "llm_response_parsed": _json_obj(parsed),
        "llm_error": error,
        "llm_latency_seconds": _format_optional_float(latency),
    }


def _turn_analysis_row(participant_id, item, word_type_per_card):
    guessed = item.get("guesses", [])
    correct = item.get("correct_guesses", [])
    incorrect = item.get("incorrect_guesses", [])
    neutral = item.get("neutral_guesses", [])
    bombs = item.get("bomb_guesses", [])
    human_raw = item.get("human_explanation_raw", "")
    human_sanitized = item.get("human_explanation_sanitized", human_raw)
    human_valid = bool(item.get("human_explanation_is_valid", False))
    ai_sanitized = item.get("ai_explanation_sanitized", item.get("ai_explanation", ""))
    ai_valid = bool(item.get("ai_explanation_is_valid", False))
    llm_fields = _llm_fields_for_turn(item)
    return {
        "participant_id": participant_id,
        "session_id": st.session_state.get("session_id", ""),
        "condition": st.session_state.get("condition", "baseline"),
        "round_number": st.session_state.round,
        "turn_number": item.get("turn", ""),
        "clue_giver": item.get("clue_giver", ""),
        "guesser": item.get("guesser", ""),
        "clue": item.get("hint", ""),
        "clue_number": item.get("hint_number", ""),
        "intended_cards": _json(item.get("intended_targets", [])),
        "intended_word_types": _json(_types_for_words(item.get("intended_targets", []), word_type_per_card)),
        "guessed_cards": _json(guessed),
        "guessed_word_types": _json(_types_for_words(guessed, word_type_per_card)),
        "correct_guesses": _json(correct),
        "correct_guess_word_types": _json(_types_for_words(correct, word_type_per_card)),
        "incorrect_guesses": _json(incorrect),
        "incorrect_guess_word_types": _json(_types_for_words(incorrect, word_type_per_card)),
        "neutral_guesses": _json(neutral),
        "neutral_guess_word_types": _json(_types_for_words(neutral, word_type_per_card)),
        "bomb_guesses": _json(bombs),
        "bomb_guess_word_types": _json(_types_for_words(bombs, word_type_per_card)),
        "remaining_targets_before_turn": _json(item.get("remaining_targets_before_turn", [])),
        "remaining_targets_after_turn": _json(item.get("remaining_targets_after_turn", [])),
        "hit_rate": f"{float(item.get('hit_rate', 0) or 0):.3f}",
        "target_yield": item.get("target_yield", 0),
        "jaccard_alignment": f"{float(item.get('jaccard_alignment', 0) or 0):.3f}",
        "alignment_status": item.get("alignment_status", ""),
        "error_type": item.get("error_type", "none"),
        "turn_score_delta": item.get("turn_score_delta", 0),
        "turn_start_time": item.get("turn_start_time", ""),
        "turn_end_time": item.get("turn_end_time", ""),
        "turn_duration_seconds": _format_optional_float(item.get("turn_duration_seconds", "")),
        "reflection_shown": str(bool(item.get("reflection_source"))).lower(),
        "reflection_source": item.get("reflection_source", ""),
        "human_understanding_rating": item.get("human_understanding_rating", ""),
        "human_relationship_type": item.get("human_relationship_type", ""),
        "human_explanation_raw": human_raw,
        "human_explanation_sanitized": human_sanitized if human_valid else "",
        "human_explanation_is_valid": str(human_valid).lower(),
        "human_explanation_blocked_reason": item.get("human_explanation_blocked_reason", ""),
        "ai_relationship_type": item.get("ai_relationship_type", ""),
        "ai_explanation_raw": item.get("ai_explanation_raw", ""),
        "ai_explanation_sanitized": ai_sanitized,
        "ai_explanation_is_valid": str(ai_valid).lower(),
        "ai_explanation_blocked_reason": item.get("ai_explanation_blocked_reason", ""),
        "ai_explanation": ai_sanitized,
        "repair_applied_to_next_prompt": str(
            st.session_state.get("condition") == "adaptive" and bool(item.get("reflection_source"))
        ).lower(),
        "repair_context_used": _json_obj(
            {
                "source": item.get("reflection_source", ""),
                "rating": item.get("human_understanding_rating", ""),
                "relationship_type": item.get("human_relationship_type", "") or item.get("ai_relationship_type", ""),
                "explanation": human_sanitized if human_valid else "",
                "ai_explanation": ai_sanitized if ai_valid else "",
            }
            if st.session_state.get("condition") == "adaptive"
            else {}
        ),
        **llm_fields,
    }


def append_analysis_logs(participant_id, timestamp, score_change, clean_history):
    rounds_file = ensure_rounds_data_file()
    turns_file = ensure_turns_data_file()
    round_row = _round_analysis_row(participant_id, timestamp, score_change)
    _append_dict_row(rounds_file, ROUNDS_LOG_FIELDS, round_row)

    word_type_per_card = st.session_state.get("word_type_per_card", {})
    for item in clean_history:
        _append_dict_row(
            turns_file,
            TURNS_LOG_FIELDS,
            _turn_analysis_row(participant_id, item, word_type_per_card),
        )


def log_round(participant_id):
    data_file = ensure_data_file()
    interaction_data_file = ensure_interaction_data_file()
    timestamp = datetime.utcnow().isoformat()

    guesses = st.session_state.guesses
    correct = any(guess in st.session_state.target_words for guess in guesses)
    bomb_words = st.session_state.get("bomb_words") or [st.session_state.bomb_word]
    bomb_hit = any(guess in bomb_words for guess in guesses)
    score_change = compute_score_change(
        guesses,
        st.session_state.target_words,
        bomb_words,
        st.session_state.round_interactions,
    )
    clean_history = clean_interaction_history(st.session_state.interaction_history)

    response_time = None
    if st.session_state.start_time is not None:
        response_time = (datetime.utcnow() - st.session_state.start_time).total_seconds()

    clues_used = ";".join(
        item.get("hint", "") for item in clean_history if item.get("hint")
    )
    reflection_ratings = ";".join(
        str(item.get("reflection_rating", "")) for item in clean_history
    )
    alignment_statuses = ";".join(
        item.get("alignment_status", "") for item in clean_history
    )
    error_types = ";".join(
        item.get("error_type", "") for item in clean_history
    )
    human_understanding_ratings = ";".join(
        str(item.get("human_understanding_rating", "")) for item in clean_history
    )
    human_relationship_types = ";".join(
        item.get("human_relationship_type", "") for item in clean_history
    )
    human_explanations = ";".join(
        item.get("human_explanation_raw", "") for item in clean_history
    )
    human_explanation_valid_flags = ";".join(
        str(item.get("human_explanation_is_valid", "")) for item in clean_history
    )
    human_explanation_blocked_reasons = ";".join(
        item.get("human_explanation_blocked_reason", "") for item in clean_history
    )
    ai_relationship_types = ";".join(
        item.get("ai_relationship_type", "") for item in clean_history
    )
    ai_explanations_raw = ";".join(
        item.get("ai_explanation_raw", "") for item in clean_history
    )
    ai_explanations_sanitized = ";".join(
        item.get("ai_explanation_sanitized", item.get("ai_explanation", "")) for item in clean_history
    )
    ai_explanation_valid_flags = ";".join(
        str(item.get("ai_explanation_is_valid", "")) for item in clean_history
    )
    ai_explanation_blocked_reasons = ";".join(
        item.get("ai_explanation_blocked_reason", "") for item in clean_history
    )
    ai_explanations = ";".join(
        item.get("ai_explanation_sanitized", item.get("ai_explanation", "")) for item in clean_history
    )
    reflection_sources = ";".join(
        item.get("reflection_source", "") for item in clean_history
    )
    reflection_relationship_types = ";".join(
        item.get("reflection_relationship_type", "") for item in clean_history
    )
    reflection_explanations = ";".join(
        item.get("reflection_explanation_raw", "") for item in clean_history
    )
    reflection_valid_flags = ";".join(
        str(item.get("reflection_explanation_is_valid", "")) for item in clean_history
    )
    reflection_blocked_reasons = ";".join(
        item.get("reflection_blocked_reason", "") for item in clean_history
    )

    session_id = st.session_state.get("session_id", "")
    condition = st.session_state.get("condition", "baseline")
    starting_role = st.session_state.get("starting_role", "")
    round_role = st.session_state.get("role", "")
    word_type_per_card = st.session_state.get("word_type_per_card", {})
    correct_guesses_all = [
        guess for guess in guesses if guess in st.session_state.target_words
    ]
    incorrect_guesses_all = [
        guess for guess in guesses if guess not in correct_guesses_all
    ]
    word_type_per_card_json = _format_word_type_per_card(
        st.session_state.board,
        word_type_per_card,
    )

    round_row = [
        session_id,
        timestamp,
        participant_id,
        condition,
        starting_role,
        st.session_state.round,
        st.session_state.round,
        round_role,
        st.session_state.role,
        st.session_state.word_type,
        st.session_state.get("board_template_type", ""),
        word_type_per_card_json,
        ";".join(st.session_state.board),
        ";".join(st.session_state.board),
        ";".join(st.session_state.target_words),
        ";".join(st.session_state.target_words),
        _join_word_types(st.session_state.target_words, word_type_per_card),
        ";".join(bomb_words),
        ";".join(bomb_words),
        _join_word_types(bomb_words, word_type_per_card),
        ";".join(st.session_state.neutral_words),
        _join_word_types(st.session_state.neutral_words, word_type_per_card),
        clues_used,
        ";".join(guesses),
        _join_word_types(guesses, word_type_per_card),
        _join_word_types(correct_guesses_all, word_type_per_card),
        _join_word_types(incorrect_guesses_all, word_type_per_card),
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
        alignment_statuses,
        error_types,
        human_understanding_ratings,
        human_relationship_types,
        human_explanations,
        human_explanation_valid_flags,
        human_explanation_blocked_reasons,
        ai_relationship_types,
        ai_explanations_raw,
        ai_explanations_sanitized,
        ai_explanation_valid_flags,
        ai_explanation_blocked_reasons,
        ai_explanations,
        reflection_sources,
        reflection_ratings,
        reflection_relationship_types,
        reflection_explanations,
        reflection_valid_flags,
        reflection_blocked_reasons,
    ]

    interaction_rows = []
    for item in clean_history:
        interaction_rows.append(
            [
                session_id,
                timestamp,
                participant_id,
                condition,
                starting_role,
                st.session_state.round,
                st.session_state.round,
                round_role,
                st.session_state.role,
                st.session_state.word_type,
                st.session_state.get("board_template_type", ""),
                word_type_per_card_json,
                _join_word_types(st.session_state.target_words, word_type_per_card),
                _join_word_types(st.session_state.neutral_words, word_type_per_card),
                _join_word_types(bomb_words, word_type_per_card),
                item["turn"],
                item["turn"],
                item["clue_giver"],
                item["guesser"],
                item["hint"],
                item["hint"],
                item["hint_number"],
                item["hint_number"],
                ";".join(item["intended_targets"]),
                ";".join(item["intended_targets"]),
                item["hint_explanation"],
                ";".join(item["guesses"]),
                ";".join(item["guesses"]),
                _join_word_types(item["guesses"], word_type_per_card),
                ";".join(item["correct_guesses"]),
                _join_word_types(item["correct_guesses"], word_type_per_card),
                ";".join(item["incorrect_guesses"]),
                _join_word_types(item["incorrect_guesses"], word_type_per_card),
                ";".join(item["missed_intended_targets"]),
                ";".join(item["extra_correct_guesses"]),
                ";".join(item["neutral_guesses"]),
                item["bomb_guess"] or "",
                item["outcome"],
                item["alignment_status"],
                item["error_type"],
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
                item["human_understanding_rating"],
                item["human_relationship_type"],
                item["human_explanation_raw"],
                item["human_explanation_is_valid"],
                item["human_explanation_blocked_reason"],
                item["ai_relationship_type"],
                item["ai_explanation_raw"],
                item["ai_explanation_sanitized"],
                item["ai_explanation_is_valid"],
                item["ai_explanation_blocked_reason"],
                item["ai_explanation"],
                item["reflection_source"],
                item["reflection_rating"],
                item["reflection_relationship_type"],
                item["reflection_explanation_raw"],
                item["reflection_explanation_is_valid"],
                item["reflection_blocked_reason"],
                item["recorded_at"],
            ]
        )

    with data_file.open("a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(round_row)

    with interaction_data_file.open("a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerows(interaction_rows)

    st.session_state.last_score_change = score_change
    st.session_state.score += score_change

    append_analysis_logs(participant_id, timestamp, score_change, clean_history)
    log_event(
        "round_completed",
        {
            "round_score": score_change,
            "medal": st.session_state.round_medal,
            "turns": st.session_state.round_interactions,
        },
        round_number=st.session_state.round,
        turn_number=st.session_state.round_interactions,
    )
    if st.session_state.round_bomb_hit:
        log_event(
            "bomb_selected",
            {
                "bomb_words": [
                    guess
                    for guess in st.session_state.guesses
                    if guess in (st.session_state.get("bomb_words") or [])
                ]
            },
            round_number=st.session_state.round,
            turn_number=st.session_state.round_interactions,
        )
    log_event("export_completed", {"files": ["rounds.csv", "turns.csv"]})
    log_session_state(completed=False)

    append_remote_csv(round_row, interaction_rows)
