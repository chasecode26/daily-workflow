import json
from pathlib import Path
import sys


USER_SKILL_DIR = Path.home() / ".claude" / "skills" / "daily-workflow"
JIRA_CONFIG_PATH = USER_SKILL_DIR / "jira-config.json"
MAPPING_PATH = USER_SKILL_DIR / "svn-mapping.json"


def load_json(path: Path) -> tuple[dict | None, str | None]:
    if not path.exists():
        return None, f"缺少文件: {path}"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError as error:
        return None, f"JSON 非法: {path} :: {error}"


def normalize_path(raw_path: str) -> Path | None:
    value = (raw_path or "").strip()
    if not value:
        return None
    return Path(value)


def validate() -> list[str]:
    errors: list[str] = []

    jira_config, error = load_json(JIRA_CONFIG_PATH)
    if error:
        return [error]

    for field_name in ("baseUrl", "username", "password"):
        value = str(jira_config.get(field_name, "")).strip()
        if not value:
            errors.append(f"jira-config.json: {field_name} 为必填项")

    projects = jira_config.get("projects") or []
    if not isinstance(projects, list) or not projects:
        errors.append("jira-config.json: projects 必须是非空数组")

    assignee = str(jira_config.get("assignee", "")).strip()
    if not assignee:
        errors.append("jira-config.json: assignee 为必填项")

    working_statuses = jira_config.get("workingStatuses") or []
    if not isinstance(working_statuses, list) or not working_statuses:
        errors.append("jira-config.json: workingStatuses 必须是非空数组")

    timeout = jira_config.get("timeout", 20)
    try:
        timeout_value = int(timeout)
    except (TypeError, ValueError):
        errors.append("jira-config.json: timeout 必须是正整数")
    else:
        if timeout_value <= 0:
            errors.append("jira-config.json: timeout 必须大于 0")

    api_path = str(jira_config.get("apiPath", "")).strip()
    if api_path and not api_path.startswith("/"):
        errors.append("jira-config.json: apiPath 必须以 / 开头")

    mappings_data, error = load_json(MAPPING_PATH)
    if error:
        errors.append(error)
        return errors

    if errors:
        return errors

    mappings = mappings_data.get("mappings") or []
    if not isinstance(mappings, list) or not mappings:
        errors.append("svn-mapping.json: mappings 必须是非空数组")
        return errors

    for index, mapping in enumerate(mappings, start=1):
        label = f"svn-mapping.json: mappings[{index}]"
        project_name = (mapping.get("projectName") or "").strip()
        if not project_name:
            errors.append(f"{label}: projectName 为必填项")

        root_path = normalize_path(mapping.get("rootPath", ""))
        frontend_path = normalize_path(mapping.get("frontendPath", ""))
        backend_path = normalize_path(mapping.get("backendPath", ""))

        if not any((root_path, frontend_path, backend_path)):
            errors.append(f"{label}: rootPath、frontendPath、backendPath 至少要填写一个")
        if root_path and not root_path.exists():
            errors.append(f"{label}: rootPath 不存在 -> {root_path}")
        if frontend_path and not frontend_path.exists():
            errors.append(f"{label}: frontendPath 不存在 -> {frontend_path}")
        if backend_path and not backend_path.exists():
            errors.append(f"{label}: backendPath 不存在 -> {backend_path}")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("daily-workflow 配置校验失败：")
        for item in errors:
            print(f"- {item}")
        return 1

    print("daily-workflow 配置校验通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
