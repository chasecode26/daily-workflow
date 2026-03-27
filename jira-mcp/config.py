import os


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


JIRA_BASE_URL = _require_env("JIRA_BASE_URL").rstrip("/")
JIRA_USERNAME = _require_env("JIRA_USERNAME")
JIRA_PASSWORD = _require_env("JIRA_PASSWORD")
JIRA_API_PATH = os.getenv("JIRA_API_PATH", "/rest/api/2")
JIRA_TIMEOUT = int(os.getenv("JIRA_TIMEOUT", "20"))
