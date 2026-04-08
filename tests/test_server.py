from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
JIRA_MCP_DIR = REPO_ROOT / "jira-mcp"
if str(JIRA_MCP_DIR) not in sys.path:
    sys.path.insert(0, str(JIRA_MCP_DIR))

import server


class ServerTests(unittest.TestCase):
    def test_get_verification_plan_returns_selected_plan(self) -> None:
        result = {
            "issue": {"key": "IMCP-1"},
            "matched": True,
            "selectionRequired": False,
            "selected": {
                "frontendPath": "D:/svn/imcp/web",
                "verificationPlan": {
                    "hasAutomation": True,
                    "workspacePath": "D:/svn/imcp/web",
                    "commands": [{"stage": "test", "command": "npm test -- login"}],
                },
                "verification": {"testCommand": "npm test -- login"},
            },
            "matches": [],
        }

        with patch.object(server, "resolve_workspace_result", return_value=result):
            payload = server.get_verification_plan("IMCP-1")

        self.assertTrue(payload["verificationPlan"]["hasAutomation"])
        self.assertEqual(payload["verificationPlan"]["workspacePath"], "D:/svn/imcp/web")

    def test_run_verification_runs_selected_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = {
                "issue": {"key": "IMCP-1"},
                "matched": True,
                "selectionRequired": False,
                "selected": {
                    "frontendPath": tmp_dir,
                    "verificationPlan": {
                        "hasAutomation": True,
                        "workspacePath": tmp_dir,
                        "shell": "powershell",
                        "commands": [{"stage": "test", "command": "echo ok"}],
                    },
                    "verification": {"testCommand": "echo ok", "buildCommand": "", "smokeCommand": ""},
                },
                "matches": [],
            }

            with patch.object(server, "resolve_workspace_result", return_value=result):
                with patch.object(server, "run_selected_verification", return_value={"success": True, "skipped": False, "exitCode": 0, "message": "verification passed", "results": []}) as run_mock:
                    payload = server.run_verification("IMCP-1")

        self.assertTrue(payload["success"])
        run_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
