import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import setup_env


class SetupEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="afip setup ")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "requirements-lock.txt").write_text("example==1.0\n", encoding="utf-8")
        (self.root / ".env.example").write_text("AFIP_PASSWORD=\n", encoding="utf-8")
        self.environment = self.root / ".venv"
        self.python = self.environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

    def make_environment(self, _path=None):
        self.python.parent.mkdir(parents=True)
        self.python.touch()
        (self.environment / "pyvenv.cfg").write_text("version = 3.11.9\n", encoding="utf-8")

    def interpreter_result(self, version=(3, 11)):
        return subprocess.CompletedProcess(
            [], 0, stdout=json.dumps({"version": version, "prefix": str(self.environment)})
        )

    def test_creates_environment_and_uses_its_python_from_any_directory(self):
        with (
            patch.object(setup_env.sys, "version_info", (3, 11, 9)),
            patch.object(setup_env.venv, "EnvBuilder") as builder,
            patch.object(setup_env.subprocess, "run") as run,
        ):
            builder.return_value.create.side_effect = self.make_environment
            run.return_value = self.interpreter_result()
            self.assertEqual(setup_env.setup_environment(self.root), self.python)
            builder.return_value.create.assert_called_once_with(self.environment)
            commands = [call.args[0] for call in run.call_args_list]
            self.assertEqual(
                commands[1],
                [
                    str(self.python),
                    "-I",
                    "-m",
                    "pip",
                    "install",
                    "-r",
                    str(self.root / "requirements-lock.txt"),
                ],
            )
            self.assertEqual(commands[2][-2:], ["pip", "check"])
            self.assertEqual(commands[3][-3:], ["playwright", "install", "chromium"])
            self.assertTrue(all(call.kwargs["cwd"] == self.root for call in run.call_args_list))
        self.assertEqual(
            (self.root / ".env").read_bytes(), (self.root / ".env.example").read_bytes()
        )

    def test_existing_environment_and_env_are_preserved(self):
        self.make_environment()
        env_file = self.root / ".env"
        env_file.write_bytes(b"LOCAL_VALUE=keep-me\n")
        with (
            patch.object(setup_env.sys, "version_info", (3, 11, 9)),
            patch.object(setup_env.venv, "EnvBuilder") as builder,
            patch.object(setup_env.subprocess, "run", return_value=self.interpreter_result()),
        ):
            setup_env.setup_environment(self.root)
            builder.assert_not_called()
        self.assertEqual(env_file.read_bytes(), b"LOCAL_VALUE=keep-me\n")

    def test_wrong_python_does_not_create_or_install_anything(self):
        with (
            patch.object(setup_env.sys, "version_info", (3, 12, 0)),
            patch.object(setup_env.subprocess, "run") as run,
            self.assertRaisesRegex(RuntimeError, "Python 3.11"),
        ):
            setup_env.setup_environment(self.root)
        run.assert_not_called()
        self.assertFalse(self.environment.exists())

    def test_invalid_existing_directory_is_not_overwritten(self):
        self.environment.mkdir()
        marker = self.environment / "keep.txt"
        marker.write_text("keep", encoding="utf-8")
        with (
            patch.object(setup_env.sys, "version_info", (3, 11, 9)),
            self.assertRaisesRegex(RuntimeError, "no es un entorno"),
        ):
            setup_env.setup_environment(self.root)
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    def test_existing_environment_with_wrong_python_is_rejected(self):
        self.make_environment()
        with (
            patch.object(setup_env.sys, "version_info", (3, 11, 9)),
            patch.object(
                setup_env.subprocess, "run", return_value=self.interpreter_result((3, 12))
            ) as run,
            self.assertRaisesRegex(RuntimeError, "debe usar Python 3.11"),
        ):
            setup_env.setup_environment(self.root)
        self.assertEqual(run.call_count, 1)

    def test_install_failure_stops_before_browser_or_configuration(self):
        self.make_environment()
        failure = subprocess.CalledProcessError(1, ["pip", "install"])
        with (
            patch.object(setup_env.sys, "version_info", (3, 11, 9)),
            patch.object(
                setup_env.subprocess, "run", side_effect=[self.interpreter_result(), failure]
            ) as run,
            self.assertRaises(subprocess.CalledProcessError),
        ):
            setup_env.setup_environment(self.root)
        self.assertEqual(run.call_count, 2)
        self.assertFalse((self.root / ".env").exists())
