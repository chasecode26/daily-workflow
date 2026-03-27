import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO_SKILL_DIR = ROOT / "claude-assets" / "skills" / "daily-workflow"
USER_SKILL_DIR = Path.home() / ".claude" / "skills" / "daily-workflow"


def _resolve_example_path(filename: str) -> Path:
    user_path = USER_SKILL_DIR / filename
    if user_path.exists():
        return user_path
    return REPO_SKILL_DIR / filename


CONFIG_PATH = USER_SKILL_DIR / "jira-config.json"
EXAMPLE_PATH = _resolve_example_path("jira-config.example.json")


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise RuntimeError(
            f"JIRA config file was not found: {CONFIG_PATH}. "
            f"Create jira-config.json from {EXAMPLE_PATH.name} first."
        )

    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RuntimeError(f"JIRA config is not valid JSON: {CONFIG_PATH} :: {error}") from error


def _require_string(config: dict, field_name: str) -> str:
    value = str(config.get(field_name, "")).strip()
    if not value:
        raise RuntimeError(f"jira-config.json is missing required field: {field_name}")
    return value


def _normalize_api_path(value: object) -> str:
    api_path = str(value or "").strip()
    if not api_path:
        return "/rest/api/2"
    return api_path if api_path.startswith("/") else f"/{api_path}"


def _parse_timeout(value: object) -> int:
    try:
        timeout = int(value)
    except (TypeError, ValueError) as error:
        raise RuntimeError("jira-config.json field timeout must be a positive integer") from error
    if timeout <= 0:
        raise RuntimeError("jira-config.json field timeout must be greater than 0")
    return timeout


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

    aliases: dict[str, list[str]] = {
        "task": ["任务", "Task", "Story", "需求"],
        "bug": ["缺陷", "Bug", "故障"],
    }
    if isinstance(raw_value, dict):
        for key, default_values in aliases.items():
            configured = raw_value.get(key)
            if configured is None:
                continue
            if not isinstance(configured, list):
                raise RuntimeError(f"jira-config.json field issueTypeAliases.{key} must be an array")
            values = [str(item).strip() for item in configured if str(item).strip()]
            aliases[key] = values or default_values
    return aliases


def _parse_report_dir(config: dict) -> Path:
    raw_value = str(config.get("reportOutputDir", "")).strip()
    if not raw_value:
        return USER_SKILL_DIR / "reports"
    return Path(raw_value).expanduser()


_CONFIG = _load_config()

JIRA_BASE_URL = _require_string(_CONFIG, "baseUrl").rstrip("/")
JIRA_USERNAME = _require_string(_CONFIG, "username")
JIRA_PASSWORD = _require_string(_CONFIG, "password")
JIRA_API_PATH = _normalize_api_path(_CONFIG.get("apiPath"))
JIRA_TIMEOUT = _parse_timeout(_CONFIG.get("timeout", 20))
JIRA_PROJECTS = _parse_string_list(_CONFIG, "projects")
JIRA_ASSIGNEE = _require_string(_CONFIG, "assignee")
JIRA_WORKING_STATUSES = _parse_string_list(_CONFIG, "workingStatuses")
JIRA_ISSUE_TYPE_ALIASES = _parse_issue_type_aliases(_CONFIG)
REPORT_OUTPUT_DIR = _parse_report_dir(_CONFIG)
