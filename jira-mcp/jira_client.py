import json
import re

import requests
from requests import Response

from config import get_request_headers, get_runtime_config


FUNCTION_CALL_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\(\)$")


class JiraClient:
    def __init__(self, config: dict | None = None) -> None:
        self.config = config or get_runtime_config()
        self.base_api = f"{self.config['baseUrl']}{self.config['apiPath']}"
        self.timeout = self.config["timeout"]
        self.projects = self.config["projects"]
        self.assignee = self.config["assignee"]
        self.issue_type_aliases = self.config["issueTypeAliases"]
        self.working_statuses = self.config["workingStatuses"]
        self.session = requests.Session()
        self.session.headers.update(get_request_headers(self.config))

    def _handle_response(self, response: Response, not_found_message: str | None = None) -> dict:
        if response.status_code == 401:
            raise RuntimeError("Jira authentication failed")
        if response.status_code == 404 and not_found_message:
            raise RuntimeError(not_found_message)
        if response.status_code >= 400:
            try:
                body = response.json()
            except Exception:
                body = response.text
            raise RuntimeError(f"Jira request failed: {response.status_code}, response={body}")

        if not response.content:
            return {}
        return response.json()

    def _build_issue_type_jql(self, issue_type: str) -> str:
        normalized = issue_type.strip().lower()
        if normalized in ("", "all"):
            return ""

        if normalized not in self.issue_type_aliases:
            supported = ", ".join(sorted(self.issue_type_aliases))
            raise RuntimeError(f"Unsupported issueType '{issue_type}'. Supported values: all, {supported}")

        values = ", ".join(f'"{item}"' for item in self.issue_type_aliases[normalized])
        return f"issuetype in ({values})"

    def _format_jql_value(self, value: str) -> str:
        normalized = str(value or "").strip()
        if FUNCTION_CALL_PATTERN.fullmatch(normalized):
            return normalized
        if normalized.startswith('"') and normalized.endswith('"'):
            return normalized
        return json.dumps(normalized, ensure_ascii=False)

    def build_my_issues_jql(self, issue_type: str = "all") -> str:
        project_clause = ", ".join(f'"{project}"' for project in self.projects)
        status_clause = ", ".join(f'"{status}"' for status in self.working_statuses)
        clauses = [
            f"assignee = {self._format_jql_value(self.assignee)}",
            f"project in ({project_clause})",
            f"status in ({status_clause})",
        ]

        issue_type_clause = self._build_issue_type_jql(issue_type)
        if issue_type_clause:
            clauses.append(issue_type_clause)

        return " AND ".join(clauses) + " ORDER BY updated DESC"

    def search_issues(self, jql: str, max_results: int = 20) -> dict:
        response = self.session.get(
            f"{self.base_api}/search",
            params={
                "jql": jql,
                "maxResults": max_results,
                "fields": "summary,status,priority,project,components,assignee,issuetype,updated",
            },
            timeout=self.timeout,
        )
        return self._handle_response(response)

    def search_my_issues(self, issue_type: str = "all", max_results: int = 20) -> dict:
        return self.search_issues(self.build_my_issues_jql(issue_type), max_results)

    def get_issue(self, issue_key: str) -> dict:
        response = self.session.get(
            f"{self.base_api}/issue/{issue_key}",
            params={
                "fields": "summary,description,status,priority,project,components,assignee,comment,issuetype"
            },
            timeout=self.timeout,
        )
        return self._handle_response(response, f"Issue {issue_key} not found")

    def add_comment(self, issue_key: str, content: str) -> dict:
        response = self.session.post(
            f"{self.base_api}/issue/{issue_key}/comment",
            json={"body": content},
            timeout=self.timeout,
        )
        return self._handle_response(response, f"Issue {issue_key} not found")

    def get_transitions(self, issue_key: str) -> dict:
        response = self.session.get(
            f"{self.base_api}/issue/{issue_key}/transitions",
            timeout=self.timeout,
        )
        return self._handle_response(response, f"Issue {issue_key} not found")

    def transition_issue(self, issue_key: str, transition_id: str) -> dict:
        response = self.session.post(
            f"{self.base_api}/issue/{issue_key}/transitions",
            json={"transition": {"id": transition_id}},
            timeout=self.timeout,
        )
        self._handle_response(response, f"Issue {issue_key} not found")
        return {"success": True}
