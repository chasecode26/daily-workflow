import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

ISSUE_KEY_PATTERN = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")
SVN_COMMIT_PATTERN = re.compile(r"(^|[;&|][&|]?\s*|&&\s*)svn\s+(commit|ci)\b")
TRANSITION_CHAINS = {
  "任务": ["开放", "开发中", "提交测试"],
  "缺陷": ["开放", "开发中", "已解决"]
}
TIMEOUT = 10


def load_payload():
  try:
    return json.load(sys.stdin)
  except Exception:
    return {}


def get_command(payload):
  tool_input = payload.get("tool_input") or {}
  command = tool_input.get("command")
  return command if isinstance(command, str) else ""


def should_handle(command):
  return bool(SVN_COMMIT_PATTERN.search(command))


def extract_issue_keys(command):
  seen = []
  for key in ISSUE_KEY_PATTERN.findall(command):
    if key not in seen:
      seen.append(key)
  return seen


def build_headers(username, password):
  token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
  return {
    "Authorization": f"Basic {token}",
    "Accept": "application/json",
    "Content-Type": "application/json"
  }


def build_url(base_url, api_path, path):
  return f"{base_url.rstrip('/')}" + f"{api_path.rstrip('/')}" + path


def request_json(method, url, headers, body=None):
  data = None
  if body is not None:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
  request = urllib.request.Request(url=url, data=data, headers=headers, method=method)
  with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
    content = response.read().decode("utf-8")
    return json.loads(content) if content else {}


def get_issue(headers, base_url, api_path, issue_key):
  query = urllib.parse.urlencode({"fields": "issuetype,status"})
  url = build_url(base_url, api_path, f"/issue/{issue_key}?{query}")
  return request_json("GET", url, headers)


def get_transitions(headers, base_url, api_path, issue_key):
  url = build_url(base_url, api_path, f"/issue/{issue_key}/transitions")
  return request_json("GET", url, headers).get("transitions") or []


def transition_issue(headers, base_url, api_path, issue_key, transition_id):
  url = build_url(base_url, api_path, f"/issue/{issue_key}/transitions")
  request_json("POST", url, headers, {"transition": {"id": transition_id}})


def find_transition_id(transitions, target_name):
  for transition in transitions:
    if transition.get("name") == target_name:
      transition_id = transition.get("id")
      return str(transition_id) if transition_id is not None else None
  return None


def run_chain(headers, base_url, api_path, issue_key):
  issue = get_issue(headers, base_url, api_path, issue_key)
  fields = issue.get("fields") or {}
  issue_type = ((fields.get("issuetype") or {}).get("name") or "").strip()
  current_status = ((fields.get("status") or {}).get("name") or "").strip()
  chain = TRANSITION_CHAINS.get(issue_type)
  if not chain:
    return {"issueKey": issue_key, "issueType": issue_type or "未知", "skipped": True, "reason": "unsupported_issue_type"}
  if current_status not in chain:
    return {
      "issueKey": issue_key,
      "issueType": issue_type,
      "skipped": True,
      "reason": "unsupported_current_status",
      "currentStatus": current_status or "未知"
    }

  current_index = chain.index(current_status)
  if current_index == len(chain) - 1:
    return {
      "issueKey": issue_key,
      "issueType": issue_type,
      "transitioned": [],
      "finalStatus": current_status
    }

  executed = []
  status = current_status
  for target_status in chain[current_index + 1:]:
    transitions = get_transitions(headers, base_url, api_path, issue_key)
    transition_id = find_transition_id(transitions, target_status)
    if not transition_id:
      return {
        "issueKey": issue_key,
        "issueType": issue_type,
        "transitioned": executed,
        "failedTarget": target_status,
        "finalStatus": status,
        "error": f"missing_transition:{target_status}"
      }
    transition_issue(headers, base_url, api_path, issue_key, transition_id)
    executed.append(target_status)
    status = target_status

  return {
    "issueKey": issue_key,
    "issueType": issue_type,
    "transitioned": executed,
    "finalStatus": status
  }


def build_message(results):
  lines = []
  for result in results:
    issue_key = result.get("issueKey", "UNKNOWN")
    issue_type = result.get("issueType", "未知")
    if result.get("error"):
      transitioned = " -> ".join(result.get("transitioned") or []) or "无"
      lines.append(f"{issue_key} | {issue_type} | 已执行: {transitioned} | 失败步骤: {result.get('failedTarget')} | 当前状态: {result.get('finalStatus')}")
      continue
    if result.get("skipped"):
      reason = result.get("reason")
      if reason == "unsupported_issue_type":
        lines.append(f"{issue_key} | 跳过 | 不支持的单据类型: {issue_type}")
      elif reason == "unsupported_current_status":
        lines.append(f"{issue_key} | 跳过 | 当前状态不在自动流转链: {result.get('currentStatus')}")
      continue
    transitioned = result.get("transitioned") or []
    if transitioned:
      lines.append(f"{issue_key} | {issue_type} | 执行流转: {' -> '.join(transitioned)} | 最终状态: {result.get('finalStatus')}")
    else:
      lines.append(f"{issue_key} | {issue_type} | 无需流转 | 当前已是: {result.get('finalStatus')}")
  return lines


def normalize_api_path(api_path):
  value = (api_path or "").strip()
  if not value:
    return "/rest/api/2"
  match = re.search(r"(/rest/api/\d+)$", value)
  if match:
    return match.group(1)
  if value.startswith("/"):
    return value.rstrip("/")
  return "/rest/api/2"


def main():
  payload = load_payload()
  command = get_command(payload).strip()
  if not command or not should_handle(command):
    return

  issue_keys = extract_issue_keys(command)
  if not issue_keys:
    return

  base_url = os.environ.get("JIRA_BASE_URL", "").strip()
  username = os.environ.get("JIRA_USERNAME", "").strip()
  password = os.environ.get("JIRA_PASSWORD", "").strip()
  api_path = normalize_api_path(os.environ.get("JIRA_API_PATH", "/rest/api/2"))
  if not base_url or not username or not password:
    print(json.dumps({"systemMessage": "SVN 已提交，但未执行 JIRA 自动流转：JIRA 环境变量未配置完整。"}, ensure_ascii=False))
    return

  headers = build_headers(username, password)
  results = []
  for issue_key in issue_keys:
    try:
      results.append(run_chain(headers, base_url, api_path, issue_key))
    except urllib.error.HTTPError as error:
      results.append({
        "issueKey": issue_key,
        "issueType": "未知",
        "finalStatus": "未知",
        "error": f"http_{error.code}"
      })
    except Exception as error:
      results.append({
        "issueKey": issue_key,
        "issueType": "未知",
        "finalStatus": "未知",
        "error": str(error)
      })

  message_lines = build_message(results)
  if message_lines:
    print(json.dumps({"systemMessage": "JIRA 自动流转结果：\n" + "\n".join(message_lines)}, ensure_ascii=False))


if __name__ == "__main__":
  main()
