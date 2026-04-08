#!/usr/bin/env bash
# 一键安装：技能 + JIRA MCP 依赖 + 本地配置初始化/校验
# 用法: bash install.sh [--dry-run]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true && echo "[dry-run] 仅预览，不落盘"

run() {
  if [[ "$DRY_RUN" == true ]]; then
    echo "  [dry-run] $*"
  else
    "$@"
  fi
}

resolve_skills_destination() {
  if [[ -n "${DAILY_WORKFLOW_SKILLS_HOME:-}" ]]; then
    printf '%s\n' "$DAILY_WORKFLOW_SKILLS_HOME"
    return 0
  fi

  if [[ -n "${CODEX_HOME:-}" ]]; then
    printf '%s\n' "$CODEX_HOME/skills"
    return 0
  fi

  if [[ -d "$HOME/.codex/skills" ]]; then
    printf '%s\n' "$HOME/.codex/skills"
    return 0
  fi

  if [[ -d "$HOME/.claude/skills" ]]; then
    printf '%s\n' "$HOME/.claude/skills"
    return 0
  fi

  printf '%s\n' "$HOME/.codex/skills"
}

initialize_or_update_config() {
  local src="$1"
  local dst="$2"

  if [[ ! -f "$src" ]]; then
    echo "  [缺失示例] $src"
    return 1
  fi

  if [[ ! -f "$dst" ]]; then
    if [[ "$DRY_RUN" == true ]]; then
      echo "  [dry-run] cp \"$src\" \"$dst\""
    else
      cp "$src" "$dst"
      echo "  [已初始化] $dst"
    fi
    return 0
  fi

  if [[ "$DRY_RUN" == true ]]; then
    echo "  [dry-run] 配置已存在，将询问是否覆盖: $dst"
    return 1
  fi

  read -r -p "  [已存在] $dst，是否用示例覆盖？[y/N] " answer
  if [[ "$answer" =~ ^([yY]|yes|YES)$ ]]; then
    cp "$src" "$dst"
    echo "  [已覆盖] $dst"
    return 0
  fi

  echo "  [保留原配置] $dst"
  return 1
}

is_example_config() {
  local src="$1"
  local dst="$2"
  [[ -f "$src" && -f "$dst" ]] || return 1
  python -c "import json, pathlib, sys; src, dst = sys.argv[1:3]; print(json.loads(pathlib.Path(src).read_text(encoding='utf-8')) == json.loads(pathlib.Path(dst).read_text(encoding='utf-8')))" "$src" "$dst" | grep -qx "True"
}

config_needs_setup() {
  local jira_file="$1"
  local mapping_file="$2"
  python -c "import json, pathlib, sys
jira_path, mapping_path = sys.argv[1:3]
jira = json.loads(pathlib.Path(jira_path).read_text(encoding='utf-8'))
mapping = json.loads(pathlib.Path(mapping_path).read_text(encoding='utf-8'))
if jira.get('baseUrl') == 'https://jira.example.com' or jira.get('username') == 'your_username' or jira.get('password') == 'your_password':
    print('True')
    raise SystemExit(0)
for item in mapping.get('mappings') or []:
    comment = str(item.get('_comment', ''))
    project_name = str(item.get('projectName', ''))
    frontend = str(item.get('frontendPath', ''))
    backend = str(item.get('backendPath', ''))
    root = str(item.get('rootPath', ''))
    if '示例' in comment or project_name == '你的JIRA项目名' or 'your-project' in frontend or 'your-project' in backend or 'your-project' in root:
        print('True')
        raise SystemExit(0)
print('False')" "$jira_file" "$mapping_file" | grep -qx "True"
}

SKILLS_SRC="$SCRIPT_DIR/claude-assets/skills"
SKILLS_DST="$(resolve_skills_destination)"
REQ="$SCRIPT_DIR/jira-mcp/requirements.txt"
HOOK="$SCRIPT_DIR/claude-assets/hooks/svn_jira_transition_hook.py"
SKILL_SRC_DIR="$SCRIPT_DIR/claude-assets/skills/daily-workflow"
SKILL_TARGET_DIR="$SKILLS_DST/daily-workflow"
JIRA_EXAMPLE="$SKILL_SRC_DIR/jira-config.example.json"
JIRA_FILE="$SKILL_TARGET_DIR/jira-config.json"
MAPPING_EXAMPLE="$SKILL_SRC_DIR/svn-mapping.example.json"
MAPPING_FILE="$SKILL_TARGET_DIR/svn-mapping.json"
VALIDATOR="$SKILL_SRC_DIR/validate_daily_workflow_config.py"
CONFIG_CHANGED=false

echo ""
echo "=== 安装技能 ==="
if [[ ! -d "$SKILLS_SRC" ]]; then
  echo "跳过：技能目录不存在 ($SKILLS_SRC)"
else
  echo "  安装目标: $SKILLS_DST"
  run mkdir -p "$SKILLS_DST"
  count=0
  for skill_dir in "$SKILLS_SRC"/*/; do
    skill_name="$(basename "$skill_dir")"
    echo "  -> $skill_name"
    run mkdir -p "$SKILLS_DST/$skill_name"
    run cp -rf "$skill_dir". "$SKILLS_DST/$skill_name/"
    count=$((count + 1))
  done
  echo "  已安装 $count 个技能"
fi

echo ""
echo "=== 安装 JIRA MCP 依赖 ==="
if [[ ! -f "$REQ" ]]; then
  echo "跳过：未找到依赖文件 ($REQ)"
else
  echo "  pip install -r $REQ"
  run pip install -r "$REQ" -q
  echo "  依赖安装完成"
fi

echo ""
echo "=== 检查 Hook ==="
if [[ -f "$HOOK" ]]; then
  echo "  [已就绪] svn_jira_transition_hook.py"
  echo "           路径: $HOOK"
else
  echo "  [缺失] $HOOK"
fi

echo ""
echo "=== 初始化 daily-workflow 本地配置 ==="
run mkdir -p "$SKILL_TARGET_DIR"
if initialize_or_update_config "$JIRA_EXAMPLE" "$JIRA_FILE"; then
  CONFIG_CHANGED=true
fi
if initialize_or_update_config "$MAPPING_EXAMPLE" "$MAPPING_FILE"; then
  CONFIG_CHANGED=true
fi
echo "  配置目录: $SKILL_TARGET_DIR"

echo ""
echo "=== 校验 daily-workflow 本地配置 ==="
if [[ ! -f "$VALIDATOR" ]]; then
  echo "跳过：未找到校验脚本 ($VALIDATOR)"
elif [[ ! -f "$JIRA_FILE" || ! -f "$MAPPING_FILE" ]]; then
  echo "跳过：未找到本地配置"
  echo "      请先填写 jira-config.json 和 svn-mapping.json"
elif [[ "$CONFIG_CHANGED" == true ]]; then
  echo "跳过：本次刚生成或覆盖了示例配置"
  echo "      请先按实际环境修改 jira-config.json 和 svn-mapping.json"
  echo "      修改完成后重新运行安装脚本，或手动执行校验脚本"
elif is_example_config "$JIRA_EXAMPLE" "$JIRA_FILE" || is_example_config "$MAPPING_EXAMPLE" "$MAPPING_FILE"; then
  echo "跳过：检测到当前仍是示例配置"
  echo "      请先按实际环境修改 jira-config.json 和 svn-mapping.json"
  echo "      修改完成后重新运行安装脚本，或手动执行校验脚本"
elif config_needs_setup "$JIRA_FILE" "$MAPPING_FILE"; then
  echo "跳过：检测到配置里仍有占位示例内容"
  echo "      请先按实际环境修改 jira-config.json 和 svn-mapping.json"
  echo "      修改完成后重新运行安装脚本，或手动执行校验脚本"
elif [[ "$DRY_RUN" == true ]]; then
  echo "  [dry-run] python $VALIDATOR --skill-dir \"$SKILL_TARGET_DIR\""
else
  echo "  python $VALIDATOR --skill-dir \"$SKILL_TARGET_DIR\""
  if python "$VALIDATOR" --skill-dir "$SKILL_TARGET_DIR"; then
    echo "  配置校验通过"
  else
    echo "  警告：配置校验未通过，请按提示修正后再使用"
  fi
fi

echo ""
if [[ "$DRY_RUN" == true ]]; then
  echo "[dry-run] 预览完成，使用 bash install.sh 正式安装"
else
  echo "安装完成"
fi
