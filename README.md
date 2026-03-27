# daily-workflow

项目级 Claude Code `daily-workflow` 配置仓库。

## 仓库目标

把 `daily-workflow` 相关的 Claude Code 配置集中管理，并与个人本地私有配置分离。

## 仓库结构

```text
.
├─ .claude/
│  ├─ settings.json          # hooks 入口 + MCP 启用
│  └─ settings.local.json    # 本地覆盖（不提交）
├─ .mcp.json                 # MCP 入口
├─ .gitignore
├─ install.sh                # 一键安装脚本
├─ install.ps1               # Windows / PowerShell 安装脚本
├─ jira-mcp/                 # JIRA MCP server
│  ├─ server.py
│  ├─ jira_client.py
│  ├─ config.py
│  └─ requirements.txt
└─ claude-assets/
   ├─ hooks/
   │  └─ svn_jira_transition_hook.py
   ├─ mcp/
   │  └─ mcp.template.json
   └─ skills/
      └─ daily-workflow/
         ├─ SKILL.md
         ├─ config.json                # 本地私有配置，不提交
         ├─ svn-mapping.json           # JIRA -> 本地 SVN 映射，不提交
         ├─ verification.json          # 验证命令配置，不提交
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
export JIRA_TIMEOUT=20

# 3. 填写本地配置
# claude-assets/skills/daily-workflow/config.json
# claude-assets/skills/daily-workflow/svn-mapping.json
# claude-assets/skills/daily-workflow/verification.json

# 4. 一键安装（安装技能 + MCP 依赖 + 检查环境 + 配置校验）
bash install.sh

# 5. 在 Claude Code 中打开此目录使用
```

Windows / PowerShell 可使用：

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

`install.sh` 与 `install.ps1` 都支持 dry-run 预览。

## 当前工作流

### daily-workflow

技能位置：`claude-assets/skills/daily-workflow/SKILL.md`

能力：
- 拉取我的 JIRA 列表，选择单个 issue
- 匹配本地 SVN 工作目录
- 先验证，再提交 SVN
- SVN 成功后自动推进 JIRA 状态

JIRA 状态流转规则（`jira-status-map.md`）：
- 任务：`开放 -> 开发中 -> 提交测试`
- 缺陷：`开放 -> 开发中 -> 已解决`

本地配置文件：
- `claude-assets/skills/daily-workflow/config.json`
  用来配置 JIRA 项目范围、assignee 默认值、以及另外两个本地配置文件入口。
- `claude-assets/skills/daily-workflow/svn-mapping.json`
  用来配置 JIRA 项目/组件/关键词 到本机 SVN 工作副本路径的映射。
- `claude-assets/skills/daily-workflow/verification.json`
  用来配置不同 `verificationProfile` 对应的测试、构建、smoke 命令。

模板文件：
- `config.example.json`
- `svn-mapping-template.json`
- `verification.template.json`
  仅作为结构参考；安装脚本会在本地配置缺失时自动初始化 `config.json`、`svn-mapping.json`、`verification.json`。

### SVN 后自动流转 hook

脚本：`claude-assets/hooks/svn_jira_transition_hook.py`
触发：`svn commit` / `svn ci` 成功后，从命令中提取 JIRA key，按预定义链路自动流转。
说明：当前 hook 命令已去掉 Unix shell 专用的重定向与 `|| true`，避免在 Windows / PowerShell 环境下行为不一致。

### JIRA MCP

`jira-mcp/server.py` 提供 `jira-local` MCP server，通过 `.mcp.json` 注册到 Claude Code。
依赖通过 `install.sh` 自动安装。
`.mcp.json` 与 `claude-assets/mcp/mcp.template.json` 均已透传 `JIRA_TIMEOUT`。

### 配置校验

校验脚本：`claude-assets/skills/daily-workflow/validate_daily_workflow_config.py`

用途：
- 检查 `config.json`、`svn-mapping.json`、`verification.json` 是否存在且为合法 JSON
- 检查 `svnMappingFile` / `verificationProfileFile` 引用是否存在
- 检查每条 mapping 的 `verificationProfile` 是否能在 `verification.json` 中找到
- 检查配置中的本地路径是否真实存在

手动运行：

```bash
python claude-assets/skills/daily-workflow/validate_daily_workflow_config.py
```

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
