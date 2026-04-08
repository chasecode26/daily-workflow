from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
JIRA_MCP_DIR = REPO_ROOT / "jira-mcp"
if str(JIRA_MCP_DIR) not in sys.path:
    sys.path.insert(0, str(JIRA_MCP_DIR))

from jira_client import JiraClient


class JiraClientTests(unittest.TestCase):
    def test_build_my_issues_jql_quotes_plain_assignee_values(self) -> None:
        client = JiraClient(
            {
                "baseUrl": "https://jira.example.com",
                "apiPath": "/rest/api/2",
                "timeout": 20,
                "projects": ["IMCP"],
                "assignee": "user@example.com",
                "workingStatuses": ["开发中"],
                "issueTypeAliases": {"task": ["任务"], "bug": ["缺陷"]},
                "username": "",
                "password": "",
                "token": "secret-token",
            }
        )

        jql = client.build_my_issues_jql()

        self.assertIn('assignee = "user@example.com"', jql)

    def test_build_my_issues_jql_keeps_function_assignee_unquoted(self) -> None:
        client = JiraClient(
            {
                "baseUrl": "https://jira.example.com",
                "apiPath": "/rest/api/2",
                "timeout": 20,
                "projects": ["IMCP"],
                "assignee": "currentUser()",
                "workingStatuses": ["开发中"],
                "issueTypeAliases": {"task": ["任务"], "bug": ["缺陷"]},
                "username": "",
                "password": "",
                "token": "secret-token",
            }
        )

        jql = client.build_my_issues_jql()

        self.assertIn("assignee = currentUser()", jql)


if __name__ == "__main__":
    unittest.main()
