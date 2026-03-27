#!/usr/bin/env bash
# 一键安装：技能 + MCP 依赖 + 环境变量检查 + 本地配置初始化/校验
# 用法: bash install.sh [--dry-run]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true && echo "[dry-run] 仅预览"

run() {
  if [[ "$DRY_RUN" == true ]]; then
    echo "  [dry-run] $*"
  else
    "$@"
  fi
}

copy_if_missing() {
  local src="$1"
  local dst="$2"
  if [[ -f "$dst" ]]; then
    echo "  [已存在] $dst"
  elif [[ ! -f "$src" ]]; then
    echo "  [缺失模板] $src"
  elif [[ "$DRY_RUN" == true ]]; then
    echo "  [dry-run] cp \"$src\" \"$dst\""
  else
    cp "$src" "$dst"
    echo "  [已初始化] $dst"
  fi
}

# ── 1. 技能安装 ────────────────────────────────────────────
SKILLS_SRC="$SCRIPT_DIR/claude-assets/skills"
SKILLS_DST="$HOME/.claude/skills"

echo ""
echo "=== 安装技能 ==="
if [[ ! -d "$SKILLS_SRC" ]]; then
  echo "跳过：技能目录不存在 ($SKILLS_SRC)"
else
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

# ── 2. MCP Python 依赖 ─────────────────────────────────────
MCP_DIR="$SCRIPT_DIR/jira-mcp"
REQ="$MCP_DIR/requirements.txt"

echo ""
echo "=== 安装 MCP 依赖 ==="
if [[ ! -f "$REQ" ]]; then
  echo "跳过：未找到 $REQ"
else
  echo "  pip install -r $REQ"
  run pip install -r "$REQ" -q
  echo "  依赖安装完成"
fi

# ── 3. 环境变量检查 ────────────────────────────────────────
echo ""
echo "=== 检查 JIRA 环境变量 ==="
REQUIRED_VARS=(JIRA_BASE_URL JIRA_USERNAME JIRA_PASSWORD)
OPTIONAL_VARS=(JIRA_API_PATH JIRA_TIMEOUT)
missing=0

for var in "${REQUIRED_VARS[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    echo "  [缺失] $var  <-- 必填"
    missing=$((missing + 1))
  else
    echo "  [OK]   $var"
  fi
done

for var in "${OPTIONAL_VARS[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    echo "  [默认] $var（未设置，将使用代码默认值）"
  else
    echo "  [OK]   $var"
  fi
done

if [[ $missing -gt 0 ]]; then
  echo ""
  echo "警告: $missing 个必填环境变量未设置，MCP 启动时会报错"
  echo "请在系统环境变量或 .env 中配置后重新运行"
fi

# ── 4. hooks 检查 ──────────────────────────────────────────
HOOK="$SCRIPT_DIR/claude-assets/hooks/svn_jira_transition_hook.py"

echo ""
echo "=== 检查 Hooks ==="
if [[ -f "$HOOK" ]]; then
  echo "  [OK] svn_jira_transition_hook.py 存在"
  echo "       路径: $HOOK"
  echo "       已通过 .claude/settings.json 引用，无需额外安装"
else
  echo "  [缺失] $HOOK"
fi

# ── 5. 初始化本地 daily-workflow 配置 ─────────────────────
SKILL_DIR="$SCRIPT_DIR/claude-assets/skills/daily-workflow"
CONFIG_TEMPLATE="$SKILL_DIR/config.example.json"
MAPPING_TEMPLATE="$SKILL_DIR/svn-mapping-template.json"
VERIFY_TEMPLATE="$SKILL_DIR/verification.template.json"
CONFIG_FILE="$SKILL_DIR/config.json"
MAPPING_FILE="$SKILL_DIR/svn-mapping.json"
VERIFY_FILE="$SKILL_DIR/verification.json"

echo ""
echo "=== 初始化 daily-workflow 配置 ==="
copy_if_missing "$CONFIG_TEMPLATE" "$CONFIG_FILE"
copy_if_missing "$MAPPING_TEMPLATE" "$MAPPING_FILE"
copy_if_missing "$VERIFY_TEMPLATE" "$VERIFY_FILE"

# ── 6. 本地 daily-workflow 配置校验 ───────────────────────
VALIDATOR="$SCRIPT_DIR/claude-assets/skills/daily-workflow/validate_daily_workflow_config.py"

echo ""
echo "=== 检查 daily-workflow 配置 ==="
if [[ ! -f "$VALIDATOR" ]]; then
  echo "跳过：未找到校验脚本 ($VALIDATOR)"
elif [[ ! -f "$CONFIG_FILE" ]]; then
  echo "跳过：未找到本地配置 ($CONFIG_FILE)"
  echo "      首次使用时请先填写 config.json / svn-mapping.json / verification.json"
else
  echo "  python $VALIDATOR"
  if [[ "$DRY_RUN" == true ]]; then
    echo "  [dry-run] python $VALIDATOR"
  elif python "$VALIDATOR"; then
    echo "  配置校验通过"
  else
    echo "  警告: daily-workflow 配置校验未通过，请按提示修正后再使用"
  fi
fi

# ── 完成 ───────────────────────────────────────────────────
echo ""
if [[ "$DRY_RUN" == true ]]; then
  echo "[dry-run] 预览完成，使用 bash install.sh 正式安装"
else
  echo "安装完成"
fi
