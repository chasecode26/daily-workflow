import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
SKILL_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SKILL_DIR / "config.json"


def load_json(path: Path) -> tuple[dict | None, str | None]:
    if not path.exists():
        return None, f"missing file: {path}"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError as error:
        return None, f"invalid json: {path} :: {error}"


def resolve_from_root(raw_path: str) -> Path:
    return (ROOT / raw_path).resolve()


def normalize_path(raw_path: str) -> Path | None:
    value = (raw_path or "").strip()
    if not value:
        return None
    return Path(value)


def validate() -> list[str]:
    errors: list[str] = []

    config, error = load_json(CONFIG_PATH)
    if error:
        return [error]

    jira = config.get("jira") or {}
    projects = jira.get("projects") or []
    if not isinstance(projects, list) or not projects:
        errors.append("config.json: jira.projects must be a non-empty list")

    mapping_file = config.get("svnMappingFile")
    verification_file = config.get("verificationProfileFile")
    if not isinstance(mapping_file, str) or not mapping_file.strip():
        errors.append("config.json: svnMappingFile is required")
    if not isinstance(verification_file, str) or not verification_file.strip():
        errors.append("config.json: verificationProfileFile is required")
    if errors:
        return errors

    mapping_path = resolve_from_root(mapping_file)
    verification_path = resolve_from_root(verification_file)

    mappings_data, error = load_json(mapping_path)
    if error:
        errors.append(error)
        return errors

    verification_data, error = load_json(verification_path)
    if error:
        errors.append(error)
        return errors

    profiles = (verification_data.get("profiles") or {})
    if not isinstance(profiles, dict) or not profiles:
        errors.append("verification.json: profiles must be a non-empty object")
        return errors

    mappings = mappings_data.get("mappings") or []
    if not isinstance(mappings, list) or not mappings:
        errors.append("svn-mapping.json: mappings must be a non-empty list")
        return errors

    for index, mapping in enumerate(mappings, start=1):
        label = f"svn-mapping.json: mappings[{index}]"
        project_name = (mapping.get("projectName") or "").strip()
        profile_name = (mapping.get("verificationProfile") or "").strip()
        if not project_name:
            errors.append(f"{label}: projectName is required")
        if not profile_name:
            errors.append(f"{label}: verificationProfile is required")
        elif profile_name not in profiles:
            errors.append(f"{label}: verificationProfile '{profile_name}' not found in verification.json")

        root_path = normalize_path(mapping.get("rootPath", ""))
        frontend_path = normalize_path(mapping.get("frontendPath", ""))
        backend_path = normalize_path(mapping.get("backendPath", ""))

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
