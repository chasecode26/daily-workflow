from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK_DIR = REPO_ROOT / "claude-assets" / "hooks"
if str(HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(HOOK_DIR))

import svn_jira_transition_hook as hook


class SvnJiraTransitionHookTests(unittest.TestCase):
    def test_process_command_ignores_non_svn_commands(self) -> None:
        self.assertEqual(hook.process_command("git commit -m test"), [])

    def test_process_command_runs_manual_mode_for_svn_commit(self) -> None:
        jira_config = {
            "baseUrl": "https://jira.example.com",
            "apiPath": "/rest/api/2",
            "timeout": 20,
            "reportOutputDir": Path("reports"),
        }

        with patch.object(hook, "load_jira_config", return_value=jira_config):
            with patch.object(hook, "build_jira_auth_headers", return_value={"Authorization": "Bearer token"}):
                with patch.object(
                    hook,
                    "run_chain",
                    return_value={"issueKey": "IMCP-1", "issueType": "任务", "finalStatus": "提交测试", "transitioned": ["提交测试"]},
                ) as run_chain:
                    with patch.object(hook, "record_reports", return_value=["daily-report | generated=reports/daily-2026-04-08.md"]):
                        lines = hook.process_command('svn commit -m "IMCP-1 fix login bug"', "D:/svn/imcp/web")

        run_chain.assert_called_once()
        self.assertIn("IMCP-1 | 任务 | transitions=提交测试 | final=提交测试", lines)
        self.assertIn("daily-report | generated=reports/daily-2026-04-08.md", lines)

    def test_process_command_reads_issue_key_from_commit_file(self) -> None:
        jira_config = {
            "baseUrl": "https://jira.example.com",
            "apiPath": "/rest/api/2",
            "timeout": 20,
            "reportOutputDir": Path("reports"),
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            message_file = Path(tmp_dir) / "commit-message.txt"
            message_file.write_text("IMCP-2 fix login menu", encoding="utf-8")

            with patch.object(hook, "load_jira_config", return_value=jira_config):
                with patch.object(hook, "build_jira_auth_headers", return_value={"Authorization": "Bearer token"}):
                    with patch.object(
                        hook,
                        "run_chain",
                        return_value={"issueKey": "IMCP-2", "issueType": "任务", "finalStatus": "提交测试", "transitioned": ["提交测试"]},
                    ) as run_chain:
                        with patch.object(hook, "record_reports", return_value=[]):
                            lines = hook.process_command(f'svn commit -F "{message_file.name}"', tmp_dir)

        run_chain.assert_called_once()
        self.assertIn("IMCP-2 | 任务 | transitions=提交测试 | final=提交测试", lines)


if __name__ == "__main__":
    unittest.main()
