import sys
from pathlib import Path

from fastmcp import FastMCP

from config import REPO_SKILL_DIR
from jira_client import JiraClient

if str(REPO_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_SKILL_DIR))

from run_verification import run_selected_verification
from workflow_support import build_transition_plan, load_mapping_config, resolve_workspace_from_issue


mcp = FastMCP("jira-local")


def get_client() -> JiraClient:
    return JiraClient()


def resolve_workspace_result(issue_key: str) -> dict:
    client = get_client()
    issue = client.get_issue(issue_key)
    mapping_data = load_mapping_config()
    return resolve_workspace_from_issue(issue, mapping_data)


def select_match(result: dict, match_index: int = 0) -> dict | None:
    if not result.get("matched"):
        return None
    if result.get("selected") is not None:
        return result["selected"]
    matches = result.get("matches") or []
    if 0 <= match_index < len(matches):
        return matches[match_index]
    return None


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
    client = get_client()
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
    client = get_client()
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
    client = get_client()
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
    client = get_client()
    client.add_comment(issueKey, content)
    return {"success": True}


@mcp.tool
def get_transitions(issueKey: str) -> dict:
    """
    Get available transitions for a Jira issue.
    """
    client = get_client()
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
    client = get_client()
    return client.transition_issue(issueKey, transitionId)


@mcp.tool
def resolve_workspace(issueKey: str) -> dict:
    """
    Resolve local SVN workspace candidates for a Jira issue.
    """
    result = resolve_workspace_result(issueKey)
    return {
        "issue": result["issue"],
        "matched": result["matched"],
        "selectionRequired": result["selectionRequired"],
        "selected": result["selected"],
        "matches": result["matches"],
    }


@mcp.tool
def get_verification_plan(issueKey: str, matchIndex: int = 0) -> dict:
    """
    Resolve the automated verification plan for a Jira issue.
    """
    result = resolve_workspace_result(issueKey)
    selected = select_match(result, matchIndex)
    return {
        "issue": result["issue"],
        "matched": result["matched"],
        "selectionRequired": result["selectionRequired"],
        "matchIndexUsed": matchIndex,
        "selected": selected,
        "verificationPlan": (selected or {}).get("verificationPlan") or {},
        "matches": result["matches"],
    }


@mcp.tool
def run_verification(issueKey: str, matchIndex: int = 0, mode: str = "auto") -> dict:
    """
    Run configured automated verification for a Jira issue's resolved workspace.
    """
    result = resolve_workspace_result(issueKey)
    selected = select_match(result, matchIndex)
    if selected is None:
        return {
            "success": False,
            "skipped": True,
            "reason": "workspace_selection_required" if result.get("selectionRequired") else "workspace_not_matched",
            "issue": result["issue"],
            "matches": result["matches"],
        }

    verification_plan = selected.get("verificationPlan") or {}
    if not verification_plan.get("hasAutomation"):
        return {
            "success": False,
            "skipped": True,
            "reason": "verification_not_configured",
            "issue": result["issue"],
            "selected": selected,
            "verificationPlan": verification_plan,
        }

    verification_result = run_selected_verification(
        Path(verification_plan["workspacePath"]).expanduser(),
        test_command=str((selected.get("verification") or {}).get("testCommand") or ""),
        build_command=str((selected.get("verification") or {}).get("buildCommand") or ""),
        smoke_command=str((selected.get("verification") or {}).get("smokeCommand") or ""),
        shell=str(verification_plan.get("shell") or "powershell"),
        mode=mode,
    )
    return {
        "issue": result["issue"],
        "selected": selected,
        "verificationPlan": verification_plan,
        **verification_result,
    }


@mcp.tool
def plan_transition(issueKey: str) -> dict:
    """
    Read current Jira status and plan the next transition step without executing it.
    """
    client = get_client()
    issue = client.get_issue(issueKey)
    issue_type = (issue.get("issueType") or "").strip()
    status = (issue.get("status") or "").strip()
    transitions = get_transitions(issueKey).get("transitions", [])
    transition_names = [str(item.get("name") or "").strip() for item in transitions]
    plan = build_transition_plan(issue_type, status, transition_names)
    return {
        "issueKey": issueKey,
        **plan,
        "transitionOptions": transitions,
    }


if __name__ == "__main__":
    mcp.run()
