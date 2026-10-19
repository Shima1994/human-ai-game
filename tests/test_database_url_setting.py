"""DATABASE_URL can come from an environment variable (servers) or from
.streamlit/secrets.toml, like every other setting; the variable wins."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core import db


class DatabaseUrlSettingTests(unittest.TestCase):
    def test_environment_variable_wins(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://env"}), \
                patch.object(db, "st", SimpleNamespace(secrets={"DATABASE_URL": "postgresql://secrets"})):
            self.assertEqual(db._database_url(), "postgresql://env")

    def test_secrets_file_is_used_without_the_variable(self):
        env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
        with patch.dict(os.environ, env, clear=True), \
                patch.object(db, "st", SimpleNamespace(secrets={"DATABASE_URL": "postgresql://secrets"})):
            self.assertEqual(db._database_url(), "postgresql://secrets")


if __name__ == "__main__":
    unittest.main()
