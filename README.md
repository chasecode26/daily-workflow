# daily-workflow

项目级 Claude Code 日常工作流配置仓库。

## 仓库目标

把日常工作里会复用的 Claude Code 配置集中管理，并与个人本地私有配置分离。

## 仓库结构

```text
.
├─ .claude/
│  ├─ settings.json          # hooks 入口 + MCP 启用
│  └─ settings.local.json    # 本地覆盖（不提交）
├─ .mcp.json                 # MCP 入口
├─ .gitignore
├─ install.sh                # 一键安装脚本
├─ jira-mcp/                 # JIRA MCP server
│  ├─ server.py
│  ├─ jira_client.py
│  ├─ config.py
│  └─ requirements.txt
└─ claude-assets/
   ├─ README.md
   ├─ hooks/
   │  └─ svn_jira_transition_hook.py
   ├─ mcp/
   │  └─ mcp.template.json
   └─ skills/
      └─ daily-bug-workflow/
         ├─ SKILL.md
         └─ jira-status-map.md
```

## 快速开始

```bash
# 1. 克隆仓库
git clone <repo-url> D:/git/daily-workflow
cd D:/git/daily-workflow

# 2. 配置环境变量（必填）
export JIRA_BASE_URL=https://jira.example.com
export JIRA_USERNAME=your_username
export JIRA_PASSWORD=your_password
# 可选
export JIRA_API_PATH=/rest/api/2

# 3. 一键安装（安装技能 + MCP 依赖 + 检查环境）
bash install.sh

# 4. 在 Claude Code 中打开此目录使用
```

`install.sh` 支持 `--dry-run` 参数预览操作。

## 当前工作流

### daily-bug-workflow

技能位置：`claude-assets/skills/daily-bug-workflow/SKILL.md`

能力：
- 拉取我的 JIRA 列表，选择单个任务/缺陷
- 匹配本地 SVN 工作目录
- 先验证，再提交 SVN
- SVN 成功后自动推进 JIRA 状态

JIRA 状态流转规则（`jira-status-map.md`）：
- 任务：`开放 -> 开发中 -> 提交测试`
- 缺陷：`开放 -> 开发中 -> 已解决`

### SVN 后自动流转 hook

脚本：`claude-assets/hooks/svn_jira_transition_hook.py`
触发：`svn commit` / `svn ci` 成功后，从命令中提取 JIRA key，按预定义链路自动流转。

### JIRA MCP

`jira-mcp/server.py` 提供 `jira-local` MCP server，通过 `.mcp.json` 注册到 Claude Code。
依赖通过 `install.sh` 自动安装。

## git 提交约定

适合提交：
- `.claude/settings.json`、`.mcp.json`、`.gitignore`
- `jira-mcp/**`、`claude-assets/**`、`install.sh`

不要提交：
- `.claude/settings.local.json`
- 明文账号、密码、token
- 个人机器专用路径

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `JIRA_BASE_URL` | 是 | JIRA 地址，如 `https://jira.example.com` |
| `JIRA_USERNAME` | 是 | 登录用户名 |
| `JIRA_PASSWORD` | 是 | 登录密码 |
| `JIRA_API_PATH` | 否 | 默认 `/rest/api/2` |
| `JIRA_TIMEOUT` | 否 | 默认 `20`（秒） |
