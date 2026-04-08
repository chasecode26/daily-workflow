from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "claude-assets" / "skills" / "daily-workflow"
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

import validate_daily_workflow_config as validator


class ValidateDailyWorkflowConfigTests(unittest.TestCase):
    def test_validate_allows_token_only_auth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            jira_path = root / "jira-config.json"
            mapping_path = root / "svn-mapping.json"
            workspace = root / "workspace"
            workspace.mkdir()

            jira_path.write_text(
                json.dumps(
                    {
                        "baseUrl": "https://jira.example.com",
                        "token": "secret-token",
                        "assignee": "currentUser()",
                        "projects": ["IMCP"],
                        "workingStatuses": ["开发中"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            mapping_path.write_text(
                json.dumps(
                    {
                        "mappings": [
                            {
                                "projectName": "一体化平台",
                                "rootPath": str(workspace),
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            errors = validator.validate(jira_path, mapping_path)

        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
