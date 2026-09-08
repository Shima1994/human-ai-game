import base64
import csv
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from core import storage


class State(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


class DurablePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.original_st = storage.st
        self.state = State(
            participant_id="p1",
            session_id="s1",
            condition="adaptive",
            round=1,
            round_interactions=1,
            remote_log_status="",
            remote_log_error="",
        )
        storage.st = SimpleNamespace(session_state=self.state)
        self.config = {
            "token": "token",
            "repo": "owner/repo",
            "branch": "main",
            "round_path": "data/game_rounds.csv",
            "interaction_path": "data/game_interactions.csv",
            "sessions_path": "data/sessions.csv",
            "rounds_path": "data/rounds.csv",
            "turns_path": "data/turns.csv",
            "events_path": "data/events.csv",
        }

    def tearDown(self):
        storage.st = self.original_st

    @staticmethod
    def _values(fields, **overrides):
        row = {field: "" for field in fields}
        row.update(overrides)
        return [row[field] for field in fields]

    def test_all_round_exports_use_durable_paths_and_canonical_keys(self):
        wide_round = self._values(
            storage.ROUND_LOG_FIELDS, session_id="s1", round_number=1
        )
        wide_turn = self._values(
            storage.INTERACTION_LOG_FIELDS,
            session_id="s1",
            round_number=1,
            turn_number=1,
        )
        normalized_round = {
            field: "" for field in storage.ROUNDS_LOG_FIELDS
        }
        normalized_round.update(session_id="s1", round_number=1)
        normalized_turn = {field: "" for field in storage.TURNS_LOG_FIELDS}
        normalized_turn.update(session_id="s1", round_number=1, turn_number=1)

        calls = []

        def capture(path, header, rows, message, key_fields=None):
            calls.append((path, header, rows, key_fields))

        with patch.object(storage, "_github_storage_config", return_value=self.config), patch.object(
            storage, "_append_to_github_csv", side_effect=capture
        ):
            storage.append_remote_csv(
                wide_round, [wide_turn], normalized_round, [normalized_turn]
            )

        self.assertEqual(
            [call[0] for call in calls],
            [
                self.config["round_path"],
                self.config["interaction_path"],
                self.config["rounds_path"],
                self.config["turns_path"],
            ],
        )
        self.assertEqual(calls[0][3], ["session_id", "round_number"])
        self.assertEqual(
            calls[1][3], ["session_id", "round_number", "turn_number"]
        )
        self.assertEqual(calls[2][3], ["session_id", "round_number"])
        self.assertEqual(
            calls[3][3], ["session_id", "round_number", "turn_number"]
        )
        self.assertEqual(self.state.remote_log_status, "github_saved")

    def test_keyed_remote_writes_are_idempotent_but_distinct_events_survive(self):
        remote = {}
        sha_counter = [0]

        def request(url, token, method="GET", payload=None):
            path = url.split("/contents/", 1)[1].split("?", 1)[0]
            if method == "GET":
                if path not in remote:
                    raise HTTPError(url, 404, "missing", None, None)
                return {
                    "sha": remote[path][0],
                    "content": base64.b64encode(remote[path][1].encode()).decode(),
                }
            sha_counter[0] += 1
            remote[path] = (
                str(sha_counter[0]),
                base64.b64decode(payload["content"]).decode(),
            )
            return {}

        turn = self._values(
            storage.TURNS_LOG_FIELDS,
            session_id="s1",
            round_number=1,
            turn_number=1,
        )
        event_one = self._values(
            storage.EVENTS_LOG_FIELDS,
            session_id="s1",
            timestamp="2026-01-01T00:00:00.000001",
            event_type="submitted",
        )
        event_two = self._values(
            storage.EVENTS_LOG_FIELDS,
            session_id="s1",
            timestamp="2026-01-01T00:00:00.000002",
            event_type="submitted",
        )

        with patch.object(storage, "_github_storage_config", return_value=self.config), patch.object(
            storage, "_github_request", side_effect=request
        ):
            for _ in range(2):
                storage._append_to_github_csv(
                    self.config["turns_path"],
                    storage.TURNS_LOG_FIELDS,
                    [turn],
                    "turn",
                    key_fields=["session_id", "round_number", "turn_number"],
                )
            storage._append_to_github_csv(
                self.config["events_path"],
                storage.EVENTS_LOG_FIELDS,
                [event_one],
                "event",
                key_fields=storage.EVENTS_LOG_FIELDS,
            )
            storage._append_to_github_csv(
                self.config["events_path"],
                storage.EVENTS_LOG_FIELDS,
                [event_one, event_two],
                "events",
                key_fields=storage.EVENTS_LOG_FIELDS,
            )

        turn_rows = list(csv.DictReader(io.StringIO(remote["data/turns.csv"][1])))
        event_rows = list(csv.DictReader(io.StringIO(remote["data/events.csv"][1])))
        self.assertEqual(len(turn_rows), 1)
        self.assertEqual(len(event_rows), 2)
        self.assertNotEqual(event_rows[0]["timestamp"], event_rows[1]["timestamp"])

    def test_ambiguous_network_retry_does_not_duplicate_committed_row(self):
        remote = {}
        put_attempts = [0]

        def request(url, token, method="GET", payload=None):
            path = url.split("/contents/", 1)[1].split("?", 1)[0]
            if method == "GET":
                if path not in remote:
                    raise HTTPError(url, 404, "missing", None, None)
                return {
                    "sha": "committed",
                    "content": base64.b64encode(remote[path].encode()).decode(),
                }
            put_attempts[0] += 1
            remote[path] = base64.b64decode(payload["content"]).decode()
            if put_attempts[0] == 1:
                raise URLError("response lost after commit")
            return {}

        row = self._values(
            storage.ROUNDS_LOG_FIELDS, session_id="s1", round_number=1
        )
        with patch.object(storage, "_github_storage_config", return_value=self.config), patch.object(
            storage, "_github_request", side_effect=request
        ):
            storage._append_to_github_csv(
                self.config["rounds_path"],
                storage.ROUNDS_LOG_FIELDS,
                [row],
                "round",
                key_fields=["session_id", "round_number"],
            )

        rows = list(csv.DictReader(io.StringIO(remote["data/rounds.csv"])))
        self.assertEqual(len(rows), 1)
        self.assertEqual(put_attempts[0], 1)

    def test_event_is_local_before_remote_and_remote_failure_is_visible(self):
        with tempfile.TemporaryDirectory() as directory:
            event_file = Path(directory) / "events.csv"
            storage._ensure_csv_fields(event_file, storage.EVENTS_LOG_FIELDS)
            with patch.object(storage, "ensure_events_data_file", return_value=event_file), patch.object(
                storage, "_github_storage_config", return_value=self.config
            ), patch.object(
                storage, "_append_to_github_csv", side_effect=URLError("offline")
            ):
                storage.log_event("ai_api_failed", {"error": "network"}, 1, 1)

            with event_file.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["event_type"], "ai_api_failed")
            self.assertEqual(self.state.remote_log_status, "github_failed")
            self.assertIn("offline", self.state.remote_log_error)

    def test_normalized_round_and_turn_local_copies_are_still_written(self):
        with tempfile.TemporaryDirectory() as directory:
            rounds_file = Path(directory) / "rounds.csv"
            turns_file = Path(directory) / "turns.csv"
            storage._ensure_csv_fields(rounds_file, storage.ROUNDS_LOG_FIELDS)
            storage._ensure_csv_fields(turns_file, storage.TURNS_LOG_FIELDS)
            round_row = {field: "" for field in storage.ROUNDS_LOG_FIELDS}
            round_row.update(session_id="s1", round_number=1)
            turn_row = {field: "" for field in storage.TURNS_LOG_FIELDS}
            turn_row.update(session_id="s1", round_number=1, turn_number=1)
            with patch.object(
                storage, "ensure_rounds_data_file", return_value=rounds_file
            ), patch.object(
                storage, "ensure_turns_data_file", return_value=turns_file
            ), patch.object(
                storage, "_round_analysis_row", return_value=round_row
            ), patch.object(
                storage, "_turn_analysis_row", return_value=turn_row
            ):
                returned_round, returned_turns = storage.append_analysis_logs(
                    "p1", "2026-01-01T00:00:00", 1, [{}]
                )
            with rounds_file.open(newline="", encoding="utf-8") as handle:
                saved_rounds = list(csv.DictReader(handle))
            with turns_file.open(newline="", encoding="utf-8") as handle:
                saved_turns = list(csv.DictReader(handle))
            self.assertEqual(len(saved_rounds), 1)
            self.assertEqual(len(saved_turns), 1)
            self.assertEqual(returned_round, round_row)
            self.assertEqual(returned_turns, [turn_row])

    def test_local_event_failure_never_attempts_or_reports_remote_success(self):
        with patch.object(storage, "ensure_events_data_file", return_value=Path("unused")), patch.object(
            storage, "_append_dict_row", side_effect=OSError("disk full")
        ), patch.object(storage, "_append_to_github_csv") as remote_write:
            with self.assertRaises(OSError):
                storage.log_event("submitted")
        remote_write.assert_not_called()
        self.assertNotEqual(self.state.remote_log_status, "github_saved")

    def test_completed_session_snapshot_remains_durable_and_idempotent(self):
        session_row = {field: "" for field in storage.SESSIONS_LOG_FIELDS}
        session_row.update(session_id="s1", participant_id="p1", completed="true")
        calls = []
        with patch.object(storage, "_github_storage_config", return_value=self.config), patch.object(
            storage, "_session_row", return_value=session_row
        ), patch.object(
            storage,
            "_append_to_github_csv",
            side_effect=lambda *args, **kwargs: calls.append((args, kwargs)),
        ):
            storage._append_remote_session_snapshot(completed=True)
        self.assertEqual(calls[0][0][0], self.config["sessions_path"])
        self.assertEqual(calls[0][1]["key_fields"], storage.SESSIONS_LOG_FIELDS)

    def test_remote_round_failure_does_not_change_local_files_or_hide_error(self):
        with tempfile.TemporaryDirectory() as directory:
            local = Path(directory) / "rounds.csv"
            storage._ensure_csv_fields(local, storage.ROUNDS_LOG_FIELDS)
            local_row = {field: "" for field in storage.ROUNDS_LOG_FIELDS}
            local_row.update(session_id="s1", round_number=1)
            storage._append_dict_row(local, storage.ROUNDS_LOG_FIELDS, local_row)
            before = local.read_bytes()
            wide_round = self._values(
                storage.ROUND_LOG_FIELDS, session_id="s1", round_number=1
            )
            with patch.object(storage, "_github_storage_config", return_value=self.config), patch.object(
                storage, "_append_to_github_csv", side_effect=URLError("offline")
            ):
                storage.append_remote_csv(wide_round, [], local_row, [])
            self.assertEqual(local.read_bytes(), before)
            self.assertEqual(self.state.remote_log_status, "github_failed")


if __name__ == "__main__":
    unittest.main()
