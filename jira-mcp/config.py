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
            f"未找到 JIRA 配置文件: {CONFIG_PATH}。"
            f"请先参考 {EXAMPLE_PATH.name} 创建 jira-config.json。"
        )

    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RuntimeError(f"JIRA 配置文件不是合法 JSON: {CONFIG_PATH} :: {error}") from error


def _require_string(config: dict, field_name: str) -> str:
    value = str(config.get(field_name, "")).strip()
    if not value:
        raise RuntimeError(f"jira-config.json 缺少必填字段: {field_name}")
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
        raise RuntimeError("jira-config.json 中 timeout 必须是正整数") from error
    if timeout <= 0:
        raise RuntimeError("jira-config.json 中 timeout 必须大于 0")
    return timeout


_CONFIG = _load_config()

JIRA_BASE_URL = _require_string(_CONFIG, "baseUrl").rstrip("/")
JIRA_USERNAME = _require_string(_CONFIG, "username")
JIRA_PASSWORD = _require_string(_CONFIG, "password")
JIRA_API_PATH = _normalize_api_path(_CONFIG.get("apiPath"))
JIRA_TIMEOUT = _parse_timeout(_CONFIG.get("timeout", 20))
