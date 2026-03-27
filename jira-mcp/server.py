from fastmcp import FastMCP

from jira_client import JiraClient

mcp = FastMCP("jira-local")
client = JiraClient()


def _safe_name(user: dict | None) -> str | None:
    if not user:
        return None
    return user.get("name") or user.get("displayName") or user.get("emailAddress")


def _normalize_issue(issue: dict) -> dict:
    fields = issue.get("fields", {})
    return {
        "key": issue.get("key"),
        "summary": fields.get("summary"),
        "status": (fields.get("status") or {}).get("name"),
        "priority": (fields.get("priority") or {}).get("name"),
        "issueType": (fields.get("issuetype") or {}).get("name"),
        "updated": fields.get("updated"),
        "projectKey": (fields.get("project") or {}).get("key"),
        "projectName": (fields.get("project") or {}).get("name"),
        "components": [item.get("name") for item in (fields.get("components") or [])],
        "assignee": _safe_name(fields.get("assignee")),
    }


@mcp.tool
def get_my_issues(issueType: str = "all", maxResults: int = 20) -> dict:
    """
    Get my Jira issues using config defaults.
    issueType supports: all, task, bug.
    """
    data = client.search_my_issues(issueType, maxResults)
    issues = [_normalize_issue(item) for item in data.get("issues", [])]
    return {
        "issueType": issueType,
        "total": data.get("total", 0),
        "maxResults": data.get("maxResults", maxResults),
        "issues": issues,
    }


@mcp.tool
def search_issues(jql: str, maxResults: int = 20) -> dict:
    """
    Search Jira issues by JQL.
    """
    data = client.search_issues(jql, maxResults)
    issues = [_normalize_issue(item) for item in data.get("issues", [])]
    return {
        "total": data.get("total", 0),
        "maxResults": data.get("maxResults", maxResults),
        "issues": issues,
    }


@mcp.tool
def get_issue(issueKey: str) -> dict:
    """
    Get Jira issue details by issue key.
    """
    data = client.get_issue(issueKey)
    fields = data.get("fields", {})
    comments = ((fields.get("comment") or {}).get("comments") or [])

    return {
        "key": data.get("key"),
        "summary": fields.get("summary"),
        "description": fields.get("description"),
        "status": (fields.get("status") or {}).get("name"),
        "priority": (fields.get("priority") or {}).get("name"),
        "issueType": (fields.get("issuetype") or {}).get("name"),
        "projectKey": (fields.get("project") or {}).get("key"),
        "projectName": (fields.get("project") or {}).get("name"),
        "components": [item.get("name") for item in (fields.get("components") or [])],
        "assignee": _safe_name(fields.get("assignee")),
        "comments": [
            {
                "author": _safe_name(comment.get("author")),
                "body": comment.get("body"),
            }
            for comment in comments
        ],
    }


@mcp.tool
def add_comment(issueKey: str, content: str) -> dict:
    """
    Add a comment to a Jira issue.
    """
    client.add_comment(issueKey, content)
    return {"success": True}


@mcp.tool
def get_transitions(issueKey: str) -> dict:
    """
    Get available transitions for a Jira issue.
    """
    data = client.get_transitions(issueKey)
    return {
        "transitions": [
            {
                "id": item.get("id"),
                "name": item.get("name"),
            }
            for item in data.get("transitions", [])
        ]
    }


@mcp.tool
def transition_issue(issueKey: str, transitionId: str) -> dict:
    """
    Transition a Jira issue by transition id.
    """
    return client.transition_issue(issueKey, transitionId)


if __name__ == "__main__":
    mcp.run()
