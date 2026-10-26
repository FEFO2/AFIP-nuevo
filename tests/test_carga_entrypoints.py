import subprocess
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class CargaEntrypointTests(unittest.TestCase):
    def test_current_and_archived_entrypoints_can_show_help_without_running_bots(self):
        commands = (
            (PROJECT_ROOT, ["bot_carga/main.py", "--help"]),
            (PROJECT_ROOT / "bot_carga", ["main.py", "--help"]),
            (PROJECT_ROOT, ["-m", "bot_carga", "--help"]),
            (PROJECT_ROOT, ["legacy/src/main.py", "--help"]),
            (PROJECT_ROOT / "legacy" / "src", ["main.py", "--help"]),
        )
        for directory, arguments in commands:
            with self.subTest(directory=directory, arguments=arguments):
                result = subprocess.run(
                    [sys.executable, *arguments],
                    cwd=directory,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("--mode", result.stdout)
                self.assertIn("--skip-downloads", result.stdout)
