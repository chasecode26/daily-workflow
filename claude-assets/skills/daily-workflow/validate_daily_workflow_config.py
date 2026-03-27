import json
from pathlib import Path
import sys


USER_SKILL_DIR = Path.home() / ".claude" / "skills" / "daily-workflow"
JIRA_CONFIG_PATH = USER_SKILL_DIR / "jira-config.json"
MAPPING_PATH = USER_SKILL_DIR / "svn-mapping.json"


def load_json(path: Path) -> tuple[dict | None, str | None]:
    if not path.exists():
        return None, f"Missing file: {path}"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError as error:
        return None, f"Invalid JSON: {path} :: {error}"


def normalize_path(raw_path: str) -> Path | None:
    value = (raw_path or "").strip()
    if not value:
        return None
    return Path(value).expanduser()


def validate_issue_type_aliases(jira_config: dict, errors: list[str]) -> None:
    aliases = jira_config.get("issueTypeAliases")
    if aliases is None:
        return
    if not isinstance(aliases, dict):
        errors.append("jira-config.json: issueTypeAliases must be an object")
        return

    for key in ("task", "bug"):
        values = aliases.get(key)
        if values is None:
            continue
        if not isinstance(values, list) or not [str(item).strip() for item in values if str(item).strip()]:
            errors.append(f"jira-config.json: issueTypeAliases.{key} must be a non-empty array")


def validate_report_dir(jira_config: dict, errors: list[str]) -> None:
    report_dir = jira_config.get("reportOutputDir")
    if report_dir is None:
        return
    value = str(report_dir).strip()
    if not value:
        errors.append("jira-config.json: reportOutputDir must not be empty when provided")


def validate() -> list[str]:
    errors: list[str] = []

    jira_config, error = load_json(JIRA_CONFIG_PATH)
    if error:
        return [error]

    for field_name in ("baseUrl", "username", "password", "assignee"):
        value = str(jira_config.get(field_name, "")).strip()
        if not value:
            errors.append(f"jira-config.json: {field_name} is required")

    for list_field in ("projects", "workingStatuses"):
        values = jira_config.get(list_field) or []
        if not isinstance(values, list) or not [str(item).strip() for item in values if str(item).strip()]:
            errors.append(f"jira-config.json: {list_field} must be a non-empty array")

    timeout = jira_config.get("timeout", 20)
    try:
        timeout_value = int(timeout)
    except (TypeError, ValueError):
        errors.append("jira-config.json: timeout must be a positive integer")
    else:
        if timeout_value <= 0:
            errors.append("jira-config.json: timeout must be greater than 0")

    api_path = str(jira_config.get("apiPath", "")).strip()
    if api_path and not api_path.startswith("/"):
        errors.append("jira-config.json: apiPath must start with /")

    validate_issue_type_aliases(jira_config, errors)
    validate_report_dir(jira_config, errors)

    mappings_data, error = load_json(MAPPING_PATH)
    if error:
        errors.append(error)
        return errors

    mappings = mappings_data.get("mappings") or []
    if not isinstance(mappings, list) or not mappings:
        errors.append("svn-mapping.json: mappings must be a non-empty array")
        return errors

    for index, mapping in enumerate(mappings, start=1):
        label = f"svn-mapping.json: mappings[{index}]"
        project_name = (mapping.get("projectName") or "").strip()
        if not project_name:
            errors.append(f"{label}: projectName is required")

        root_path = normalize_path(mapping.get("rootPath", ""))
        frontend_path = normalize_path(mapping.get("frontendPath", ""))
        backend_path = normalize_path(mapping.get("backendPath", ""))

        if not any((root_path, frontend_path, backend_path)):
            errors.append(f"{label}: rootPath, frontendPath, backendPath require at least one value")
        if root_path and not root_path.exists():
            errors.append(f"{label}: rootPath does not exist -> {root_path}")
        if frontend_path and not frontend_path.exists():
            errors.append(f"{label}: frontendPath does not exist -> {frontend_path}")
        if backend_path and not backend_path.exists():
            errors.append(f"{label}: backendPath does not exist -> {backend_path}")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("daily-workflow config validation failed:")
        for item in errors:
            print(f"- {item}")
        return 1

    print("daily-workflow config validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
