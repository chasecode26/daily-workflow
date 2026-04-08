import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO_SKILL_DIR = ROOT / "claude-assets" / "skills" / "daily-workflow"
if str(REPO_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_SKILL_DIR))

from workflow_support import build_jira_auth_headers, load_jira_runtime_config


def get_runtime_config(config_path: Path | str | None = None) -> dict:
    return load_jira_runtime_config(config_path)


def get_request_headers(config: dict | None = None) -> dict[str, str]:
    runtime_config = config or get_runtime_config()
    return build_jira_auth_headers(runtime_config)
