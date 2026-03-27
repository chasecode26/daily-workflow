from __future__ import annotations

import base64
import json
from datetime import datetime
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "claude-assets" / "skills" / "daily-workflow"
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from work_summary import WorkEvent, append_event, write_daily_report, write_weekly_report


ISSUE_KEY_PATTERN = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")
SVN_COMMIT_PATTERN = re.compile(r"(^|[;&|][&|]?\s*|&&\s*)svn\s+(commit|ci)\b")
TRANSITION_CHAINS = {
    "任务": ["开放", "开发中", "提交测试"],
    "缺陷": ["开放", "开发中", "已解决"],
}
DEFAULT_TIMEOUT = 10
USER_SKILL_DIR = Path.home() / ".claude" / "skills" / "daily-workflow"
JIRA_CONFIG_PATH = USER_SKILL_DIR / "jira-config.json"
JIRA_CONFIG_EXAMPLE = SKILL_DIR / "jira-config.example.json"


def resolve_example_file(filename: str) -> Path:
    user_path = USER_SKILL_DIR / filename
    if user_path.exists():
        return user_path
    return SKILL_DIR / filename


def load_payload() -> dict:
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def get_command(payload: dict) -> str:
    tool_input = payload.get("tool_input") or {}
    command = tool_input.get("command")
    return command if isinstance(command, str) else ""


def get_cwd(payload: dict) -> str:
    tool_input = payload.get("tool_input") or {}
    cwd = tool_input.get("cwd") or tool_input.get("workdir") or payload.get("cwd")
    return cwd if isinstance(cwd, str) else ""


def should_handle(command: str) -> bool:
    return bool(SVN_COMMIT_PATTERN.search(command))


def extract_issue_keys(command: str) -> list[str]:
    seen: list[str] = []
    for key in ISSUE_KEY_PATTERN.findall(command):
        if key not in seen:
            seen.append(key)
    return seen


def build_headers(username: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return {
        "Authorization": f"Basic {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def build_url(base_url: str, api_path: str, path: str) -> str:
    return f"{base_url.rstrip('/')}{api_path.rstrip('/')}{path}"


def request_json(method: str, url: str, headers: dict[str, str], timeout: int, body: dict | None = None) -> dict:
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url=url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content = response.read().decode("utf-8")
        return json.loads(content) if content else {}


def get_issue(headers: dict[str, str], base_url: str, api_path: str, timeout: int, issue_key: str) -> dict:
    query = urllib.parse.urlencode(
        {
            "fields": "summary,issuetype,status,project",
        }
    )
    url = build_url(base_url, api_path, f"/issue/{issue_key}?{query}")
    return request_json("GET", url, headers, timeout)


def get_transitions(headers: dict[str, str], base_url: str, api_path: str, timeout: int, issue_key: str) -> list[dict]:
    url = build_url(base_url, api_path, f"/issue/{issue_key}/transitions")
    return request_json("GET", url, headers, timeout).get("transitions") or []


def transition_issue(
    headers: dict[str, str], base_url: str, api_path: str, timeout: int, issue_key: str, transition_id: str
) -> None:
    url = build_url(base_url, api_path, f"/issue/{issue_key}/transitions")
    request_json("POST", url, headers, timeout, {"transition": {"id": transition_id}})


def find_transition_id(transitions: list[dict], target_name: str) -> str | None:
    for transition in transitions:
        if transition.get("name") == target_name:
            transition_id = transition.get("id")
            return str(transition_id) if transition_id is not None else None
    return None


def run_chain(headers: dict[str, str], jira_config: dict, issue_key: str) -> dict:
    issue = get_issue(headers, jira_config["baseUrl"], jira_config["apiPath"], jira_config["timeout"], issue_key)
    fields = issue.get("fields") or {}
    issue_type = ((fields.get("issuetype") or {}).get("name") or "").strip()
    current_status = ((fields.get("status") or {}).get("name") or "").strip()
    chain = TRANSITION_CHAINS.get(issue_type)
    result = {
        "issueKey": issue_key,
        "issueType": issue_type or "Unknown",
        "summary": str(fields.get("summary") or "").strip(),
        "projectKey": ((fields.get("project") or {}).get("key") or "").strip(),
        "projectName": ((fields.get("project") or {}).get("name") or "").strip(),
        "originalStatus": current_status or "Unknown",
    }

    if not chain:
        result.update({"skipped": True, "reason": "unsupported_issue_type"})
        return result
    if current_status not in chain:
        result.update({"skipped": True, "reason": "unsupported_current_status"})
        return result

    current_index = chain.index(current_status)
    if current_index == len(chain) - 1:
        result.update({"transitioned": [], "finalStatus": current_status})
        return result

    executed: list[str] = []
    status = current_status
    for target_status in chain[current_index + 1 :]:
        transitions = get_transitions(
            headers, jira_config["baseUrl"], jira_config["apiPath"], jira_config["timeout"], issue_key
        )
        transition_id = find_transition_id(transitions, target_status)
        if not transition_id:
            result.update(
                {
                    "transitioned": executed,
                    "failedTarget": target_status,
                    "finalStatus": status,
                    "error": f"missing_transition:{target_status}",
                }
            )
            return result
        transition_issue(
            headers,
            jira_config["baseUrl"],
            jira_config["apiPath"],
            jira_config["timeout"],
            issue_key,
            transition_id,
        )
        executed.append(target_status)
        status = target_status

    result.update({"transitioned": executed, "finalStatus": status})
    return result


def build_message(results: list[dict], report_messages: list[str]) -> list[str]:
    lines: list[str] = []
    for result in results:
        issue_key = result.get("issueKey", "UNKNOWN")
        issue_type = result.get("issueType", "Unknown")
        if result.get("error"):
            transitioned = " -> ".join(result.get("transitioned") or []) or "none"
            lines.append(
                f"{issue_key} | {issue_type} | transitioned={transitioned} | "
                f"failed={result.get('failedTarget')} | final={result.get('finalStatus')}"
            )
            continue
        if result.get("skipped"):
            reason = result.get("reason")
            if reason == "unsupported_issue_type":
                lines.append(f"{issue_key} | skipped | unsupported issue type: {issue_type}")
            elif reason == "unsupported_current_status":
                lines.append(
                    f"{issue_key} | skipped | current status is outside transition chain: "
                    f"{result.get('originalStatus')}"
                )
            continue
        transitioned = result.get("transitioned") or []
        if transitioned:
            lines.append(f"{issue_key} | {issue_type} | transitions={' -> '.join(transitioned)} | final={result.get('finalStatus')}")
        else:
            lines.append(f"{issue_key} | {issue_type} | no transition needed | final={result.get('finalStatus')}")

    lines.extend(report_messages)
    return lines


def normalize_api_path(api_path: object) -> str:
    value = str(api_path or "").strip()
    if not value:
        return "/rest/api/2"
    if value.startswith("/"):
        return value.rstrip("/")
    return "/" + value.rstrip("/")


def load_jira_config() -> dict:
    if not JIRA_CONFIG_PATH.exists():
        raise RuntimeError(
            f"JIRA config file was not found: {JIRA_CONFIG_PATH}. "
            f"Create jira-config.json from {resolve_example_file('jira-config.example.json').name} first."
        )

    try:
        config = json.loads(JIRA_CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RuntimeError(f"JIRA config is not valid JSON: {error}") from error

    base_url = str(config.get("baseUrl", "")).strip().rstrip("/")
    username = str(config.get("username", "")).strip()
    password = str(config.get("password", "")).strip()
    api_path = normalize_api_path(config.get("apiPath", "/rest/api/2"))
    report_output_dir = str(config.get("reportOutputDir", "")).strip()

    try:
        timeout = int(config.get("timeout", DEFAULT_TIMEOUT))
    except (TypeError, ValueError) as error:
        raise RuntimeError("jira-config.json field timeout must be a positive integer") from error

    if timeout <= 0:
        raise RuntimeError("jira-config.json field timeout must be greater than 0")
    if not base_url or not username or not password:
        raise RuntimeError("jira-config.json must include baseUrl, username, and password")

    return {
        "baseUrl": base_url,
        "username": username,
        "password": password,
        "apiPath": api_path,
        "timeout": timeout,
        "reportOutputDir": Path(report_output_dir).expanduser() if report_output_dir else USER_SKILL_DIR / "reports",
    }


def record_reports(results: list[dict], jira_config: dict, command: str, workspace: str) -> list[str]:
    report_dir = Path(jira_config["reportOutputDir"])
    recorded = 0
    report_messages: list[str] = []
    now = datetime.now().astimezone()
    today = now.date().isoformat()

    for result in results:
        if result.get("error") or result.get("skipped"):
            continue
        event = WorkEvent(
            issue_key=result.get("issueKey", ""),
            issue_type=result.get("issueType", "Unknown"),
            summary=result.get("summary", ""),
            status=result.get("finalStatus") or result.get("originalStatus") or "",
            project_key=result.get("projectKey", ""),
            project_name=result.get("projectName", ""),
            committed_at=now.isoformat(),
            workspace=workspace,
            svn_command=command,
            transitions=list(result.get("transitioned") or []),
        )
        append_event(report_dir, event)
        recorded += 1

    if not recorded:
        return report_messages

    daily_report = write_daily_report(report_dir, today)
    report_messages.append(f"daily-report | generated={daily_report}")
    if now.weekday() == 4:
        weekly_report = write_weekly_report(report_dir, today)
        report_messages.append(f"weekly-report | generated={weekly_report}")
    return report_messages


def main() -> None:
    payload = load_payload()
    command = get_command(payload).strip()
    if not command or not should_handle(command):
        return

    issue_keys = extract_issue_keys(command)
    if not issue_keys:
        return

    try:
        jira_config = load_jira_config()
    except Exception as error:
        print(json.dumps({"systemMessage": f"SVN committed, but JIRA auto-transition did not run: {error}"}, ensure_ascii=False))
        return

    headers = build_headers(jira_config["username"], jira_config["password"])
    results: list[dict] = []
    for issue_key in issue_keys:
        try:
            results.append(run_chain(headers, jira_config, issue_key))
        except urllib.error.HTTPError as error:
            results.append(
                {
                    "issueKey": issue_key,
                    "issueType": "Unknown",
                    "finalStatus": "Unknown",
                    "error": f"http_{error.code}",
                }
            )
        except Exception as error:
            results.append(
                {
                    "issueKey": issue_key,
                    "issueType": "Unknown",
                    "finalStatus": "Unknown",
                    "error": str(error),
                }
            )

    report_messages = record_reports(results, jira_config, command, get_cwd(payload))
    message_lines = build_message(results, report_messages)
    if message_lines:
        print(json.dumps({"systemMessage": "JIRA auto-transition result:\n" + "\n".join(message_lines)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
