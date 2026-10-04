import os
import unittest
from unittest import mock

from core import prolific


class ProlificCompletionTests(unittest.TestCase):
    def test_complete_url_uses_prolific_redirect(self):
        self.assertEqual(
            prolific.prolific_complete_url("C1ABC23"),
            "https://app.prolific.com/submissions/complete?cc=C1ABC23",
        )

    def test_complete_url_is_blank_without_code(self):
        self.assertEqual(prolific.prolific_complete_url(""), "")

    def test_completion_code_read_from_environment(self):
        with mock.patch.dict(os.environ, {"PROLIFIC_COMPLETION_CODE": " C1ABC23 "}):
            self.assertEqual(prolific.prolific_completion_code(), "C1ABC23")


class ProlificUrlParamTests(unittest.TestCase):
    def _params(self, query):
        with mock.patch.object(prolific.st, "query_params", query):
            return prolific.prolific_params_from_url()

    def test_reads_all_three_ids(self):
        params = self._params(
            {"PROLIFIC_PID": "5f1a2b3c4d5e6f7a8b9c0d1e", "STUDY_ID": "abc123", "SESSION_ID": "xyz789"}
        )
        self.assertEqual(params["prolific_pid"], "5f1a2b3c4d5e6f7a8b9c0d1e")
        self.assertEqual(params["prolific_study_id"], "abc123")
        self.assertEqual(params["prolific_session_id"], "xyz789")

    def test_unsubstituted_placeholder_is_not_stored(self):
        params = self._params({"PROLIFIC_PID": "{{%PROLIFIC_PID%}}"})
        self.assertEqual(params["prolific_pid"], "")

    def test_missing_params_are_blank(self):
        self.assertEqual(
            self._params({}),
            {"prolific_pid": "", "prolific_study_id": "", "prolific_session_id": ""},
        )


class AttentionCheckTests(unittest.TestCase):
    def test_both_passed(self):
        self.assertEqual(prolific.attention_checks_failed("A few times a month", 2), 0)

    def test_both_failed(self):
        self.assertEqual(prolific.attention_checks_failed("Daily", 5), 2)

    def test_unanswered_check_is_not_a_failure(self):
        self.assertEqual(prolific.attention_checks_failed("Daily", ""), 1)
        self.assertEqual(prolific.attention_checks_failed("", None), 0)


if __name__ == "__main__":
    unittest.main()
