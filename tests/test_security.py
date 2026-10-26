import subprocess
import unittest
from unittest.mock import patch

from scripts.check_private_files import main


class PrivateFilesTests(unittest.TestCase):
    def test_sensitive_paths_are_ignored_even_if_previously_tracked(self):
        paths = [
            ".env",
            ".env.local",
            "client_secret.json",
            "token_automation.json",
            "bot_newsan/newsan_auth_state.json",
            "bot_newsan/facturas_para_carga/test.pdf",
            "bot_newsan/salida_csv/test.csv",
            "bot_facturador/lista_fac_a.csv",
            "bot_revision_facturas/adjuntos/test.pdf",
            "env/pyvenv.cfg",
        ]
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "--stdin", "-z"],
            input="\0".join(paths) + "\0",
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(set(result.stdout.rstrip("\0").split("\0")), set(paths))

    def test_safe_examples_can_be_committed(self):
        result = subprocess.run(
            [
                "git",
                "check-ignore",
                "--no-index",
                ".env.example",
                "bot_facturador/lista_fac.example.csv",
            ],
            capture_output=True,
        )
        self.assertEqual(result.returncode, 1)

    def test_guard_rejects_forced_private_files_without_printing_contents(self):
        with patch("scripts.check_private_files.subprocess.run") as run:
            run.return_value.stdout = b".env\0token.json\0"
            self.assertEqual(main(), 1)
            run.return_value.stdout = b""
            self.assertEqual(main(), 0)
