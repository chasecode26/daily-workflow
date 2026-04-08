import argparse
import json
import os
from pathlib import Path
import sys

from workflow_support import resolve_jira_config_path, resolve_mapping_path, resolve_skill_dir

USER_SKILL_DIR = resolve_skill_dir()
JIRA_CONFIG_PATH = resolve_jira_config_path()
MAPPING_PATH = resolve_mapping_path()


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


def validate_verification(label: str, mapping: dict, errors: list[str]) -> None:
    verification = mapping.get("verification")
    if verification is None:
        return
    if not isinstance(verification, dict):
        errors.append(f"{label}: verification must be an object")
        return

    for field_name in ("testCommand", "buildCommand", "smokeCommand", "defaultCwd", "shell"):
        value = verification.get(field_name)
        if value is None:
            continue
        if not isinstance(value, str):
            errors.append(f"{label}: verification.{field_name} must be a string")

    default_cwd = str(verification.get("defaultCwd", "")).strip()
    allowed_cwds = {"", "frontendPath", "backendPath", "rootPath"}
    if default_cwd and default_cwd not in allowed_cwds:
        errors.append(f"{label}: verification.defaultCwd must be one of frontendPath, backendPath, rootPath")


def read_string(jira_config: dict, field_name: str, env_name: str | None = None) -> str:
    env_value = os.environ.get(env_name or "")
    if env_value is not None and env_value.strip():
        return env_value.strip()
    return str(jira_config.get(field_name, "")).strip()


def validate(jira_config_path: Path | None = None, mapping_path: Path | None = None) -> list[str]:
    errors: list[str] = []
    resolved_jira_config_path = resolve_jira_config_path(jira_config_path)
    resolved_mapping_path = resolve_mapping_path(mapping_path)

    jira_config, error = load_json(resolved_jira_config_path)
    if error:
        return [error]

    for field_name, env_name in (("baseUrl", "JIRA_BASE_URL"), ("assignee", "JIRA_ASSIGNEE")):
        value = read_string(jira_config, field_name, env_name)
        if not value:
            errors.append(f"jira-config.json: {field_name} is required")

    username = read_string(jira_config, "username", "JIRA_USERNAME")
    password = read_string(jira_config, "password", "JIRA_PASSWORD")
    token = read_string(jira_config, "token", "JIRA_TOKEN")
    if not token and not (username and password):
        errors.append("jira-config.json: provide token, or username and password")

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

    mappings_data, error = load_json(resolved_mapping_path)
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
        validate_verification(label, mapping, errors)

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate daily-workflow runtime config.")
    parser.add_argument("--skill-dir", help="Optional skill directory containing jira-config.json and svn-mapping.json.")
    parser.add_argument("--jira-config", help="Optional explicit jira-config.json path.")
    parser.add_argument("--mapping", help="Optional explicit svn-mapping.json path.")
    args = parser.parse_args()

    skill_dir = Path(args.skill_dir).expanduser() if args.skill_dir else None
    jira_config_path = Path(args.jira_config).expanduser() if args.jira_config else None
    mapping_path = Path(args.mapping).expanduser() if args.mapping else None
    if skill_dir is not None:
        jira_config_path = jira_config_path or (skill_dir / "jira-config.json")
        mapping_path = mapping_path or (skill_dir / "svn-mapping.json")

    errors = validate(jira_config_path, mapping_path)
    if errors:
        print("daily-workflow config validation failed:")
        for item in errors:
            print(f"- {item}")
        return 1

    print("daily-workflow config validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
