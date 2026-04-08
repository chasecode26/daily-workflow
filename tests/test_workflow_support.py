from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "claude-assets" / "skills" / "daily-workflow"
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

import workflow_support
from workflow_support import build_transition_plan, load_jira_runtime_config, resolve_skill_dir, resolve_workspace_from_issue


class WorkflowSupportTests(unittest.TestCase):
    def test_resolve_skill_dir_prefers_existing_codex_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            home = Path(tmp_dir)
            codex_skill_dir = home / ".codex" / "skills" / "daily-workflow"
            claude_skill_dir = home / ".claude" / "skills" / "daily-workflow"
            codex_skill_dir.mkdir(parents=True)
            claude_skill_dir.mkdir(parents=True)

            with patch.object(workflow_support.Path, "home", return_value=home):
                with patch.dict("os.environ", {}, clear=False):
                    resolved = resolve_skill_dir()

        self.assertEqual(resolved, codex_skill_dir)

    def test_load_jira_runtime_config_defaults_report_dir_to_selected_skill_root(self) -> None:
        raw_config = {
            "baseUrl": "https://jira.example.com",
            "username": "user",
            "password": "password",
            "assignee": "currentUser()",
            "projects": ["IMCP"],
            "workingStatuses": ["开发中"],
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            home = Path(tmp_dir)
            claude_skill_dir = home / ".claude" / "skills" / "daily-workflow"
            claude_skill_dir.mkdir(parents=True)
            config_path = claude_skill_dir / "jira-config.json"

            with patch.object(workflow_support.Path, "home", return_value=home):
                with patch.object(workflow_support, "_load_json", return_value=raw_config):
                    with patch.dict("os.environ", {}, clear=False):
                        config = load_jira_runtime_config(config_path)

        self.assertEqual(config["reportOutputDir"], claude_skill_dir / "reports")

    def test_load_jira_runtime_config_supports_token_override(self) -> None:
        raw_config = {
            "baseUrl": "https://jira.example.com",
            "username": "user",
            "password": "password",
            "assignee": "currentUser()",
            "projects": ["IMCP"],
            "workingStatuses": ["\u5f00\u53d1\u4e2d"],
        }

        with patch.object(workflow_support, "_load_json", return_value=raw_config):
            with patch.dict("os.environ", {"JIRA_TOKEN": "token-value"}, clear=False):
                config = load_jira_runtime_config(Path("ignored.json"))

        self.assertEqual(config["token"], "token-value")
        self.assertEqual(config["username"], "user")
        self.assertEqual(config["password"], "password")

    def test_resolve_workspace_prefers_project_and_component_match(self) -> None:
        issue = {
            "key": "IMCP-1",
            "fields": {
                "summary": "fix login menu issue",
                "description": "permission menu cannot load",
                "project": {"name": "\u4e00\u4f53\u5316\u5e73\u53f0", "key": "IMCP"},
                "components": [{"name": "\u6743\u9650\u7ba1\u7406"}],
            },
        }
        mappings = {
            "mappings": [
                {
                    "projectName": "\u4e00\u4f53\u5316\u5e73\u53f0",
                    "componentName": "",
                    "keywords": ["login"],
                    "rootPath": "D:/svn/imcp",
                },
                {
                    "projectName": "\u4e00\u4f53\u5316\u5e73\u53f0",
                    "componentName": "\u6743\u9650\u7ba1\u7406",
                    "keywords": ["menu"],
                    "frontendPath": "D:/svn/imcp/web",
                    "backendPath": "D:/svn/imcp/service",
                    "verification": {
                        "testCommand": "npm test -- login",
                        "buildCommand": "npm run build",
                        "defaultCwd": "frontendPath",
                    },
                },
            ]
        }

        result = resolve_workspace_from_issue(issue, mappings)

        self.assertTrue(result["matched"])
        self.assertFalse(result["selectionRequired"])
        self.assertEqual(result["selected"]["frontendPath"], "D:/svn/imcp/web")
        self.assertEqual(result["selected"]["reasons"], ["projectName", "componentName"])
        self.assertTrue(result["selected"]["verification"]["hasAutomation"])
        self.assertEqual(result["selected"]["verification"]["testCommand"], "npm test -- login")
        self.assertEqual(result["selected"]["verification"]["defaultCwd"], "frontendPath")

    def test_build_transition_plan_reports_next_step(self) -> None:
        plan = build_transition_plan(
            "\u4efb\u52a1",
            "\u5f00\u53d1\u4e2d",
            ["\u63d0\u4ea4\u6d4b\u8bd5", "\u5173\u95ed"],
        )

        self.assertFalse(plan["skipped"])
        self.assertEqual(plan["nextTarget"], "\u63d0\u4ea4\u6d4b\u8bd5")
        self.assertTrue(plan["readyNow"])


if __name__ == "__main__":
    unittest.main()
