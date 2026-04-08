from __future__ import annotations

import base64
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
REPO_SKILL_DIR = ROOT / "claude-assets" / "skills" / "daily-workflow"
SKILL_NAME = "daily-workflow"

DEFAULT_API_PATH = "/rest/api/2"
DEFAULT_TIMEOUT = 20
DEFAULT_ISSUE_TYPE_ALIASES: dict[str, list[str]] = {
    "task": ["\u4efb\u52a1", "Task", "Story", "\u9700\u6c42"],
    "bug": ["\u7f3a\u9677", "Bug", "\u6545\u969c"],
}
TRANSITION_CHAINS: dict[str, list[str]] = {
    "\u4efb\u52a1": ["\u5f00\u653e", "\u5f00\u53d1\u4e2d", "\u63d0\u4ea4\u6d4b\u8bd5"],
    "\u7f3a\u9677": ["\u5f00\u653e", "\u5f00\u53d1\u4e2d", "\u5df2\u89e3\u51b3"],
}


def _expand_path(raw_path: str | Path) -> Path:
    return Path(raw_path).expanduser()


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    unique_paths: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        if path in seen:
            continue
        unique_paths.append(path)
        seen.add(path)
    return unique_paths


def get_skill_dir_candidates() -> list[Path]:
    candidates: list[Path] = []

    explicit_dir = os.environ.get("DAILY_WORKFLOW_SKILL_DIR", "").strip()
    if explicit_dir:
        candidates.append(_expand_path(explicit_dir))

    codex_home = os.environ.get("CODEX_HOME", "").strip()
    if codex_home:
        candidates.append(_expand_path(codex_home) / "skills" / SKILL_NAME)

    claude_home = os.environ.get("CLAUDE_HOME", "").strip()
    if claude_home:
        candidates.append(_expand_path(claude_home) / "skills" / SKILL_NAME)

    home = Path.home()
    candidates.append(home / ".codex" / "skills" / SKILL_NAME)
    candidates.append(home / ".claude" / "skills" / SKILL_NAME)
    return _dedupe_paths(candidates)


def resolve_skill_dir(skill_dir: Path | str | None = None) -> Path:
    if skill_dir is not None:
        return _expand_path(skill_dir)

    candidates = get_skill_dir_candidates()
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def resolve_jira_config_path(config_path: Path | str | None = None) -> Path:
    if config_path is not None:
        return _expand_path(config_path)
    return resolve_skill_dir() / "jira-config.json"


def resolve_mapping_path(mapping_path: Path | str | None = None) -> Path:
    if mapping_path is not None:
        return _expand_path(mapping_path)
    return resolve_skill_dir() / "svn-mapping.json"


def default_report_dir(skill_dir: Path | str | None = None) -> Path:
    return resolve_skill_dir(skill_dir) / "reports"


USER_SKILL_DIR = resolve_skill_dir()
JIRA_CONFIG_PATH = resolve_jira_config_path()
MAPPING_PATH = resolve_mapping_path()
DEFAULT_REPORT_DIR = default_report_dir()


def _load_json(path: Path, label: str) -> dict:
    if not path.exists():
        raise RuntimeError(f"{label} was not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RuntimeError(f"{label} is not valid JSON: {path} :: {error}") from error


def _read_string(config: dict, field_name: str, *, required: bool = False, env_name: str | None = None) -> str:
    env_value = os.environ.get(env_name or "")
    if env_value is not None and env_value.strip():
        return env_value.strip()
    value = str(config.get(field_name, "")).strip()
    if required and not value:
        raise RuntimeError(f"jira-config.json is missing required field: {field_name}")
    return value


def _parse_timeout(value: object) -> int:
    try:
        timeout = int(value)
    except (TypeError, ValueError) as error:
        raise RuntimeError("jira-config.json field timeout must be a positive integer") from error
    if timeout <= 0:
        raise RuntimeError("jira-config.json field timeout must be greater than 0")
    return timeout


def _normalize_api_path(value: object) -> str:
    api_path = str(value or "").strip()
    if not api_path:
        return DEFAULT_API_PATH
    return api_path if api_path.startswith("/") else f"/{api_path}"


def _parse_string_list(config: dict, field_name: str) -> list[str]:
    raw_values = config.get(field_name) or []
    if not isinstance(raw_values, list):
        raise RuntimeError(f"jira-config.json field {field_name} must be an array")

    values = [str(item).strip() for item in raw_values if str(item).strip()]
    if not values:
        raise RuntimeError(f"jira-config.json field {field_name} must not be empty")
    return values


def _parse_issue_type_aliases(config: dict) -> dict[str, list[str]]:
    raw_value = config.get("issueTypeAliases") or {}
    if raw_value and not isinstance(raw_value, dict):
        raise RuntimeError("jira-config.json field issueTypeAliases must be an object")

    aliases = {key: list(values) for key, values in DEFAULT_ISSUE_TYPE_ALIASES.items()}
    if not isinstance(raw_value, dict):
        return aliases

    for key, default_values in DEFAULT_ISSUE_TYPE_ALIASES.items():
        configured = raw_value.get(key)
        if configured is None:
            continue
        if not isinstance(configured, list):
            raise RuntimeError(f"jira-config.json field issueTypeAliases.{key} must be an array")
        values = [str(item).strip() for item in configured if str(item).strip()]
        aliases[key] = values or list(default_values)
    return aliases


def _parse_report_dir(config: dict, *, skill_dir: Path | None = None) -> Path:
    raw_value = os.environ.get("DAILY_WORKFLOW_REPORT_DIR", "").strip() or str(config.get("reportOutputDir", "")).strip()
    if not raw_value:
        return default_report_dir(skill_dir)
    return Path(raw_value).expanduser()


def _normalize_issue(issue: dict) -> dict:
    fields = issue.get("fields") or issue
    project = fields.get("project") or {}
    return {
        "key": issue.get("key") or fields.get("key") or "",
        "summary": str(fields.get("summary") or "").strip(),
        "description": str(fields.get("description") or "").strip(),
        "projectKey": str(project.get("key") or fields.get("projectKey") or "").strip(),
        "projectName": str(project.get("name") or fields.get("projectName") or "").strip(),
        "issueType": str(((fields.get("issuetype") or {}).get("name")) or fields.get("issueType") or "").strip(),
        "status": str(((fields.get("status") or {}).get("name")) or fields.get("status") or "").strip(),
        "components": [
            str(item.get("name") or item).strip()
            for item in (fields.get("components") or [])
            if str(item.get("name") if isinstance(item, dict) else item).strip()
        ],
    }


def load_jira_runtime_config(config_path: Path | str | None = None) -> dict:
    resolved_config_path = resolve_jira_config_path(config_path)
    config = _load_json(resolved_config_path, "JIRA config file")

    base_url = _read_string(config, "baseUrl", required=True, env_name="JIRA_BASE_URL").rstrip("/")
    username = _read_string(config, "username", env_name="JIRA_USERNAME")
    password = _read_string(config, "password", env_name="JIRA_PASSWORD")
    token = _read_string(config, "token", env_name="JIRA_TOKEN")
    assignee = _read_string(config, "assignee", required=True, env_name="JIRA_ASSIGNEE")
    api_path = _normalize_api_path(os.environ.get("JIRA_API_PATH", "").strip() or config.get("apiPath"))
    timeout = _parse_timeout(os.environ.get("JIRA_TIMEOUT", "").strip() or config.get("timeout", DEFAULT_TIMEOUT))
    projects = _parse_string_list(config, "projects")
    working_statuses = _parse_string_list(config, "workingStatuses")
    issue_type_aliases = _parse_issue_type_aliases(config)
    report_output_dir = _parse_report_dir(config, skill_dir=resolved_config_path.parent)

    if not token and not (username and password):
        raise RuntimeError("jira-config.json must provide token, or username and password")

    return {
        "baseUrl": base_url,
        "username": username,
        "password": password,
        "token": token,
        "apiPath": api_path,
        "timeout": timeout,
        "projects": projects,
        "assignee": assignee,
        "workingStatuses": working_statuses,
        "issueTypeAliases": issue_type_aliases,
        "reportOutputDir": report_output_dir,
    }


def build_jira_auth_headers(config: dict) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    token = str(config.get("token") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
        return headers

    username = str(config.get("username") or "").strip()
    password = str(config.get("password") or "").strip()
    auth_token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    headers["Authorization"] = f"Basic {auth_token}"
    return headers


def load_mapping_config(mapping_path: Path | str | None = None) -> dict:
    data = _load_json(resolve_mapping_path(mapping_path), "SVN mapping file")
    mappings = data.get("mappings") or []
    if not isinstance(mappings, list):
        raise RuntimeError("svn-mapping.json field mappings must be an array")
    return data


def _normalize_candidate_paths(mapping: dict) -> dict[str, str]:
    return {
        "frontendPath": str(mapping.get("frontendPath") or "").strip(),
        "backendPath": str(mapping.get("backendPath") or "").strip(),
        "rootPath": str(mapping.get("rootPath") or "").strip(),
    }


def _normalize_verification(mapping: dict) -> dict:
    raw_value = mapping.get("verification") or {}
    if not isinstance(raw_value, dict):
        return {}

    commands = {
        "testCommand": str(raw_value.get("testCommand") or "").strip(),
        "buildCommand": str(raw_value.get("buildCommand") or "").strip(),
        "smokeCommand": str(raw_value.get("smokeCommand") or "").strip(),
    }
    default_cwd = str(raw_value.get("defaultCwd") or "").strip()
    shell = str(raw_value.get("shell") or "").strip() or "powershell"

    return {
        **commands,
        "defaultCwd": default_cwd,
        "shell": shell,
        "hasAutomation": any(commands.values()),
    }


def resolve_preferred_workspace(candidate: dict) -> dict[str, str]:
    for field_name in ("frontendPath", "backendPath", "rootPath"):
        value = str(candidate.get(field_name) or "").strip()
        if value:
            return {"key": field_name, "path": value}
    return {"key": "", "path": ""}


def build_verification_plan(candidate: dict) -> dict:
    verification = candidate.get("verification") or {}
    default_cwd = str(verification.get("defaultCwd") or "").strip()
    configured_workspace = str(candidate.get(default_cwd) or "").strip() if default_cwd else ""
    preferred_workspace = resolve_preferred_workspace(candidate)
    workspace_key = default_cwd if configured_workspace else preferred_workspace["key"]
    workspace_path = configured_workspace or preferred_workspace["path"]

    commands = [
        {"stage": "test", "command": str(verification.get("testCommand") or "").strip()},
        {"stage": "build", "command": str(verification.get("buildCommand") or "").strip()},
        {"stage": "smoke", "command": str(verification.get("smokeCommand") or "").strip()},
    ]
    configured_commands = [item for item in commands if item["command"]]

    return {
        "hasAutomation": bool(verification.get("hasAutomation")) and bool(workspace_path),
        "workspaceKey": workspace_key,
        "workspacePath": workspace_path,
        "shell": str(verification.get("shell") or "").strip() or "powershell",
        "commands": configured_commands,
        "defaultMode": "auto" if configured_commands else "",
    }


def resolve_workspace_from_issue(issue: dict, mapping_data: dict) -> dict:
    normalized_issue = _normalize_issue(issue)
    project_name = normalized_issue["projectName"]
    components = {value.casefold() for value in normalized_issue["components"]}
    search_text = " ".join(
        [
            normalized_issue["summary"],
            normalized_issue["description"],
            " ".join(normalized_issue["components"]),
        ]
    ).casefold()

    ranked_matches: list[dict] = []
    for index, mapping in enumerate(mapping_data.get("mappings") or []):
        if not isinstance(mapping, dict):
            continue

        mapping_project = str(mapping.get("projectName") or "").strip()
        mapping_component = str(mapping.get("componentName") or "").strip()
        keywords = [str(item).strip() for item in (mapping.get("keywords") or []) if str(item).strip()]

        reasons: list[str] = []
        rank = 99

        if mapping_project and mapping_project == project_name and mapping_component and mapping_component.casefold() in components:
            reasons = ["projectName", "componentName"]
            rank = 0
        elif mapping_project and mapping_project == project_name:
            reasons = ["projectName"]
            rank = 1
        elif mapping_component and mapping_component.casefold() in components:
            reasons = ["componentName"]
            rank = 2
        elif keywords and any(keyword.casefold() in search_text for keyword in keywords):
            reasons = ["keywords"]
            rank = 3

        if rank == 99:
            continue

        candidate = {
            "index": index,
            "rank": rank,
            "reasons": reasons,
            "projectName": mapping_project,
            "componentName": mapping_component,
            "keywords": keywords,
            "verification": _normalize_verification(mapping),
            **_normalize_candidate_paths(mapping),
        }
        candidate["verificationPlan"] = build_verification_plan(candidate)
        ranked_matches.append(candidate)

    ranked_matches.sort(key=lambda item: (item["rank"], item["index"]))
    top_rank = ranked_matches[0]["rank"] if ranked_matches else None
    best_matches = [item for item in ranked_matches if item["rank"] == top_rank]
    selected = best_matches[0] if len(best_matches) == 1 else None

    return {
        "issue": normalized_issue,
        "matches": best_matches,
        "selected": selected,
        "selectionRequired": len(best_matches) > 1,
        "matched": bool(best_matches),
    }


def build_transition_plan(issue_type: str, current_status: str, available_transition_names: list[str]) -> dict:
    normalized_type = str(issue_type or "").strip()
    normalized_status = str(current_status or "").strip()
    chain = TRANSITION_CHAINS.get(normalized_type)
    if not chain:
        return {
            "issueType": normalized_type or "Unknown",
            "currentStatus": normalized_status or "Unknown",
            "chain": [],
            "skipped": True,
            "reason": "unsupported_issue_type",
        }

    if normalized_status not in chain:
        return {
            "issueType": normalized_type,
            "currentStatus": normalized_status or "Unknown",
            "chain": list(chain),
            "skipped": True,
            "reason": "unsupported_current_status",
        }

    current_index = chain.index(normalized_status)
    remaining = chain[current_index + 1 :]
    next_target = remaining[0] if remaining else None
    available = {str(item).strip() for item in available_transition_names if str(item).strip()}

    return {
        "issueType": normalized_type,
        "currentStatus": normalized_status,
        "chain": list(chain),
        "remainingChain": remaining,
        "nextTarget": next_target,
        "readyNow": bool(next_target and next_target in available),
        "availableTransitions": sorted(available),
        "skipped": False,
        "reason": None,
    }
