import unittest
from unittest.mock import patch

from scripts.check_secrets import main


class SecretHookTests(unittest.TestCase):
    def test_missing_scanner_blocks_commit(self):
        with (
            patch("scripts.check_secrets.shutil.which", return_value=None),
            patch("scripts.check_secrets.Path.is_file", return_value=False),
        ):
            self.assertEqual(main(), 1)

    def test_scanner_result_is_propagated_and_output_redacted(self):
        with (
            patch("scripts.check_secrets.shutil.which", return_value="gitleaks"),
            patch("scripts.check_secrets.subprocess.run") as run,
        ):
            for result in (0, 1, 2):
                run.return_value.returncode = result
                self.assertEqual(main(), result)
                self.assertIn("--redact", run.call_args.args[0])
                self.assertIn("--staged", run.call_args.args[0])
