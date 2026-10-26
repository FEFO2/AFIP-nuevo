import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from afip_common import config


class ConfigTests(unittest.TestCase):
    def test_missing_and_blank_credentials_fail_without_values(self):
        for value in (None, "", "   "):
            with self.subTest(value=value), patch.dict(os.environ, {}, clear=True):
                if value is not None:
                    os.environ["AFIP_PASSWORD"] = value
                with self.assertRaisesRegex(ValueError, "AFIP_PASSWORD"):
                    config.get_required_env("AFIP_PASSWORD")

    def test_legacy_url_and_environment_priority(self):
        with patch.dict(os.environ, {"PAG_URL": "https://old.example"}, clear=True):
            self.assertEqual(config.get_required_env("PGA_URL", "PAG_URL"), "https://old.example")
            os.environ["PGA_URL"] = "https://new.example"
            self.assertEqual(config.get_required_env("PGA_URL", "PAG_URL"), "https://new.example")

    def test_env_comes_from_project_and_does_not_override_environment(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            root = Path(directory)
            (root / ".env").write_text("TEST_VALUE=file\nTEST_OTHER=local\n", encoding="utf-8")
            os.environ["TEST_VALUE"] = "process"
            with patch.object(config, "PROJECT_ROOT", root):
                config.load_environment()
            self.assertEqual(os.environ["TEST_VALUE"], "process")
            self.assertEqual(os.environ["TEST_OTHER"], "local")

    def test_credentials_are_not_in_settings_repr(self):
        settings = config.AranciaSettings("https://example.test", "test-user", "test-value")
        self.assertNotIn(settings.username, repr(settings))
        self.assertNotIn(settings.password, repr(settings))
