from __future__ import annotations

import argparse
import hashlib
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
from workflow_support import build_jira_auth_headers, build_transition_plan, load_jira_runtime_config, resolve_jira_config_path


ISSUE_KEY_PATTERN = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")
SVN_COMMIT_PATTERN = re.compile(r"(^|[;&|][&|]?\s*|&&\s*)svn\s+(commit|ci)\b")
SVN_COMMIT_FILE_PATTERN = re.compile(r'(?:^|\s)(?:-F|--file)\s+(?:"([^"]+)"|\'([^\']+)\'|([^\s]+))')
SVN_REVISION_PATTERN = re.compile(r"Committed revision\s+(\d+)", re.IGNORECASE)
JIRA_CONFIG_PATH = resolve_jira_config_path()


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


def get_tool_output(payload: dict) -> str:
    value = payload.get("tool_output") or payload.get("toolOutput") or ""
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return json.dumps(value, ensure_ascii=False)


def should_handle(command: str) -> bool:
    return bool(SVN_COMMIT_PATTERN.search(command))


def extract_issue_keys(command: str) -> list[str]:
    seen: list[str] = []
    for key in ISSUE_KEY_PATTERN.findall(command):
        if key not in seen:
            seen.append(key)
    return seen


def extract_commit_file_path(command: str, workspace: str = "") -> Path | None:
    match = SVN_COMMIT_FILE_PATTERN.search(command)
    if not match:
        return None

    raw_path = next((item for item in match.groups() if item), "")
    if not raw_path:
        return None

    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        return candidate

    base_dir = Path(workspace).expanduser() if workspace else Path.cwd()
    return base_dir / candidate


def extract_issue_keys_from_commit_file(command: str, workspace: str = "") -> list[str]:
    commit_file = extract_commit_file_path(command, workspace)
    if commit_file is None or not commit_file.exists():
        return []
    try:
        return extract_issue_keys(commit_file.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        return extract_issue_keys(commit_file.read_text(encoding="utf-8-sig"))


def extract_svn_revision(svn_output: str) -> str:
    match = SVN_REVISION_PATTERN.search(svn_output or "")
    return match.group(1) if match else ""


def build_event_id(issue_key: str, command: str, workspace: str, status: str, transitions: list[str], svn_output: str) -> str:
    revision = extract_svn_revision(svn_output)
    if revision:
        return f"svn-revision:{revision}:{issue_key}"

    digest = hashlib.sha1(
        "||".join(
            [
                issue_key.strip(),
                command.strip(),
                workspace.strip(),
                status.strip(),
                "->".join(item.strip() for item in transitions if item.strip()),
            ]
        ).encode("utf-8")
    ).hexdigest()
    return f"svn-fallback:{digest}"


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
    query = urllib.parse.urlencode({"fields": "summary,issuetype,status,project"})
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
    initial_transitions = get_transitions(headers, jira_config["baseUrl"], jira_config["apiPath"], jira_config["timeout"], issue_key)
    initial_plan = build_transition_plan(
        issue_type,
        current_status,
        [str(item.get("name") or "").strip() for item in initial_transitions],
    )

    result = {
        "issueKey": issue_key,
        "issueType": issue_type or "Unknown",
        "summary": str(fields.get("summary") or "").strip(),
        "projectKey": ((fields.get("project") or {}).get("key") or "").strip(),
        "projectName": ((fields.get("project") or {}).get("name") or "").strip(),
        "originalStatus": current_status or "Unknown",
    }

    if initial_plan["skipped"]:
        result.update({"skipped": True, "reason": initial_plan["reason"]})
        return result

    remaining = initial_plan["remainingChain"]
    if not remaining:
        result.update({"transitioned": [], "finalStatus": current_status})
        return result

    executed: list[str] = []
    status = current_status
    for target_status in remaining:
        transitions = get_transitions(
            headers,
            jira_config["baseUrl"],
            jira_config["apiPath"],
            jira_config["timeout"],
            issue_key,
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


def load_jira_config() -> dict:
    return load_jira_runtime_config(JIRA_CONFIG_PATH)


def record_reports(results: list[dict], jira_config: dict, command: str, workspace: str, svn_output: str = "") -> list[str]:
    report_dir = Path(jira_config["reportOutputDir"])
    recorded = 0
    report_messages: list[str] = []
    now = datetime.now().astimezone()
    today = now.date().isoformat()
    revision = extract_svn_revision(svn_output)

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
            event_id=build_event_id(
                result.get("issueKey", ""),
                command,
                workspace,
                result.get("finalStatus") or result.get("originalStatus") or "",
                list(result.get("transitioned") or []),
                svn_output,
            ),
            svn_revision=revision,
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


def process_command(command: str, workspace: str = "", svn_output: str = "") -> list[str]:
    if not command or not should_handle(command):
        return []

    issue_keys = extract_issue_keys(command)
    for issue_key in extract_issue_keys_from_commit_file(command, workspace):
        if issue_key not in issue_keys:
            issue_keys.append(issue_key)
    if not issue_keys:
        return []

    try:
        jira_config = load_jira_config()
    except Exception as error:
        return [f"SVN committed, but JIRA auto-transition did not run: {error}"]

    headers = build_jira_auth_headers(jira_config)
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

    report_messages = record_reports(results, jira_config, command, workspace, svn_output)
    message_lines = build_message(results, report_messages)
    return message_lines


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Handle post-SVN JIRA transition and report generation.")
    parser.add_argument("--command", help="Run in manual mode with the original svn command line.")
    parser.add_argument("--cwd", default="", help="Optional workspace path for manual mode.")
    parser.add_argument("--svn-output", default="", help="Optional SVN command output used to extract committed revision.")
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Print plain text instead of Claude hook JSON output in manual mode.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command:
        message_lines = process_command(args.command.strip(), args.cwd.strip(), args.svn_output)
        if not message_lines:
            return
        message = "JIRA auto-transition result:\n" + "\n".join(message_lines)
        if args.plain:
            print(message)
        else:
            print(json.dumps({"systemMessage": message}, ensure_ascii=False))
        return

    payload = load_payload()
    command = get_command(payload).strip()
    message_lines = process_command(command, get_cwd(payload), get_tool_output(payload))
    if message_lines:
        print(json.dumps({"systemMessage": "JIRA auto-transition result:\n" + "\n".join(message_lines)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
