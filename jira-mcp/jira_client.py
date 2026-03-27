import requests
from requests import Response

from config import (
    JIRA_API_PATH,
    JIRA_BASE_URL,
    JIRA_PASSWORD,
    JIRA_TIMEOUT,
    JIRA_USERNAME,
)


class JiraClient:
    def __init__(self) -> None:
        self.base_api = f"{JIRA_BASE_URL}{JIRA_API_PATH}"
        self.session = requests.Session()
        self.session.auth = (JIRA_USERNAME, JIRA_PASSWORD)
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

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

    def search_issues(self, jql: str, max_results: int = 20) -> dict:
        response = self.session.get(
            f"{self.base_api}/search",
            params={
                "jql": jql,
                "maxResults": max_results,
                "fields": "summary,status,priority,project,components,assignee",
            },
            timeout=JIRA_TIMEOUT,
        )
        return self._handle_response(response)

    def get_issue(self, issue_key: str) -> dict:
        response = self.session.get(
            f"{self.base_api}/issue/{issue_key}",
            params={
                "fields": "summary,description,status,priority,project,components,assignee,comment"
            },
            timeout=JIRA_TIMEOUT,
        )
        return self._handle_response(response, f"Issue {issue_key} not found")

    def add_comment(self, issue_key: str, content: str) -> dict:
        response = self.session.post(
            f"{self.base_api}/issue/{issue_key}/comment",
            json={"body": content},
            timeout=JIRA_TIMEOUT,
        )
        return self._handle_response(response, f"Issue {issue_key} not found")

    def get_transitions(self, issue_key: str) -> dict:
        response = self.session.get(
            f"{self.base_api}/issue/{issue_key}/transitions",
            timeout=JIRA_TIMEOUT,
        )
        return self._handle_response(response, f"Issue {issue_key} not found")

    def transition_issue(self, issue_key: str, transition_id: str) -> dict:
        response = self.session.post(
            f"{self.base_api}/issue/{issue_key}/transitions",
            json={"transition": {"id": transition_id}},
            timeout=JIRA_TIMEOUT,
        )
        self._handle_response(response, f"Issue {issue_key} not found")
        return {"success": True}
