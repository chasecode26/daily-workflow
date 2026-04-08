from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "claude-assets" / "skills" / "daily-workflow"
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

import run_verification


class RunVerificationTests(unittest.TestCase):
    def test_select_commands_auto_prefers_test(self) -> None:
        class Args:
            test_command = "pytest"
            build_command = "npm run build"
            smoke_command = ""
            mode = "auto"

        self.assertEqual(run_verification.select_commands(Args()), [("test", "pytest")])

    def test_main_runs_all_configured_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            completed = subprocess.CompletedProcess(args=["powershell"], returncode=0, stdout="ok\n", stderr="")

            with patch.object(run_verification.subprocess, "run", return_value=completed) as run_mock:
                with patch.object(
                    sys,
                    "argv",
                    [
                        "run_verification.py",
                        "--workspace",
                        str(workspace),
                        "--test-command",
                        "pytest",
                        "--build-command",
                        "npm run build",
                        "--mode",
                        "all",
                    ],
                ):
                    exit_code = run_verification.main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(run_mock.call_count, 2)


if __name__ == "__main__":
    unittest.main()
