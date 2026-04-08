# daily-workflow

`daily-workflow` 用于把日常 Jira -> 本地 SVN -> 提交确认 -> Jira 流转 -> 日报周报 这条链路固化下来。

它解决的事情：

- 从 Jira 拉取当前待处理事项，支持只拉 `任务`、只拉 `缺陷`，或默认全拉
- 按项目/组件/关键词把 Jira 单据映射到本地 SVN 工作目录
- 在改代码前收集“修改目标”和“补充说明”
- 在用户确认提交前展示局部代码 diff，并解释改动内容
- `svn commit` 成功后自动推进 Jira 状态
- 自动生成当天日报，周五额外生成周报

仓库只保存可共享的脚本和模板。账号、密码、Token、本机路径等私有信息放在本地配置，不进 git。

## 目录

```text
.
├─ .codex/config.toml
├─ .claude/settings.json
├─ .mcp.json
├─ install.sh
├─ install.ps1
├─ jira-mcp/
│  ├─ server.py
│  ├─ jira_client.py
│  ├─ config.py
│  └─ requirements.txt
└─ claude-assets/
   ├─ hooks/svn_jira_transition_hook.py
   ├─ mcp/mcp.template.json
   └─ skills/daily-workflow/
      ├─ SKILL.md
      ├─ jira-config.example.json
      ├─ svn-mapping.example.json
      ├─ jira-status-map.md
      ├─ validate_daily_workflow_config.py
      ├─ work_summary.py
      └─ generate_work_summary.py
```

## 快速开始

```bash
git clone <repo-url> D:/git/daily-workflow
cd D:/git/daily-workflow
```

Linux / macOS:

```bash
bash install.sh
```

Windows / PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

仅预览，不落盘：

```bash
bash install.sh --dry-run
```

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -DryRun
```

安装脚本会做这些事：

- 安装 `jira-mcp` 依赖
- 把 skill 同步到 `~/.codex/skills/daily-workflow/` 或 `~/.claude/skills/daily-workflow/`
- 初始化本地 `jira-config.json` 和 `svn-mapping.json`
- 校验配置合法性

安装脚本会优先使用 `CODEX_HOME/skills` 或 `~/.codex/skills`，否则回退到 `~/.claude/skills`。也可以通过 `DAILY_WORKFLOW_SKILLS_HOME` 指定安装根目录。

## Codex 接入

项目内已提供 [`.codex/config.toml`](.codex/config.toml)，用于在 Codex 中自动注册 `jira-local` MCP。

Codex 目前没有与 Claude Code `PostToolUse` 等价的自动 hook，所以 `svn commit` 之后如果你想继续自动推进 Jira 并生成日报/周报，需要手动执行：

```bash
python claude-assets/hooks/svn_jira_transition_hook.py --plain --cwd "<your-workspace>" --command 'svn commit -m "IMCP-123 fix xxx"'
```

如果你已经在 Claude Code 中使用本仓库，原有 [`.claude/settings.json`](.claude/settings.json) 里的 hook 仍然可用。

## 本地配置

实际配置目录：

```text
~/.codex/skills/daily-workflow/
# or
~/.claude/skills/daily-workflow/
```

### `jira-config.json`

用途：

- 配置 Jira 连接信息
- 配置“我的待办”默认筛选条件
- 配置 Jira 单据类型别名
- 配置日报/周报输出目录

示例：

```json
{
  "baseUrl": "https://jira.example.com",
  "username": "your_username",
  "password": "your_password",
  "token": "",
  "apiPath": "/rest/api/2",
  "timeout": 20,
  "projects": ["IMCP", "KINGE"],
  "assignee": "currentUser()",
  "workingStatuses": ["开放", "开发中"],
  "issueTypeAliases": {
    "task": ["任务", "Task", "Story", "需求"],
    "bug": ["缺陷", "Bug", "故障"]
  }
}
```

字段说明：

- `baseUrl`: Jira 根地址
- `username` / `password`: Basic Auth 登录凭据
- `token`: 可选。若提供 `token`，或环境变量里存在 `JIRA_TOKEN`，则优先使用 Bearer Token 认证
- `apiPath`: 通常保持 `/rest/api/2`
- `timeout`: Jira 接口超时时间，单位秒
- `projects`: 默认拉取的项目 key 列表
- `assignee`: 默认负责人，通常是 `currentUser()`
- `workingStatuses`: 待办列表展示的状态集合
- `issueTypeAliases`: `task` / `bug` 映射到你们 Jira 实际单据类型名
- `reportOutputDir`: 自动生成日报周报的目录；不填写时默认落到当前技能目录下的 `reports/`

认证优先级：

- `JIRA_TOKEN` env > `jira-config.json.token`
- 若没有 token，则回退到 `username` / `password`

可选环境变量覆盖：

- `JIRA_BASE_URL`
- `JIRA_USERNAME`
- `JIRA_PASSWORD`
- `JIRA_TOKEN`
- `JIRA_ASSIGNEE`
- `JIRA_API_PATH`
- `JIRA_TIMEOUT`
- `DAILY_WORKFLOW_REPORT_DIR`

### `svn-mapping.json`

用途：

- 把 Jira 项目、组件、关键词映射到本地 SVN 路径
- 让 workflow 自动定位到正确工作目录

示例：

```json
{
  "mappings": [
    {
      "projectName": "一体化平台",
      "componentName": "权限管理",
      "keywords": ["登录", "菜单", "权限"],
      "frontendPath": "D:/svn/imcp/web",
      "backendPath": "D:/svn/imcp/service",
      "rootPath": "D:/svn/imcp"
    },
    {
      "projectName": "金格协同",
      "componentName": "",
      "keywords": ["流程", "表单"],
      "frontendPath": "",
      "backendPath": "",
      "rootPath": "D:/svn/kinge"
    }
  ]
}
```

填写建议：

- `projectName` 尽量与 Jira 项目名保持一致
- `componentName` 留空表示整个项目共用该映射
- `keywords` 只在项目与组件不足以区分时再补
- `frontendPath` / `backendPath` / `rootPath` 至少填写一个真实存在的路径

## 工作流说明

### 1. 拉取 Jira

优先使用 `jira-local.get_my_issues`，支持：

- `all`: 默认，任务和缺陷都拉
- `task`: 只拉任务
- `bug`: 只拉缺陷

默认筛选来自 `jira-config.json`：

- `assignee`
- `projects`
- `workingStatuses`

补充 MCP tool：

- `jira-local.resolve_workspace(issueKey)`: 根据 `svn-mapping.json` 返回命中的 frontend/backend/rootPath 候选
- `jira-local.plan_transition(issueKey)`: 在真正流转前，预览当前状态剩余链路与下一跳是否可执行

### 2. 选择事项并补充说明

用户选中一个 Jira 后，workflow 需要继续收集：

- 具体要改什么
- 是否有补充说明，需要带入最终变更解释

### 3. 映射本地工作目录

按下面顺序匹配：

1. `projectName`
2. `componentName`
3. `keywords`

推荐先调用 `jira-local.resolve_workspace(issueKey)`，再根据返回结果决定进入哪个目录。

匹配成功后优先进入最可能的前端或后端目录，再开始搜代码。

### 4. 修改并校验

推荐校验顺序：

1. 现有 automated test
2. build
3. 启动后 smoke 验证
4. 浏览器验证

### 5. 用户确认前的展示规则

在请求用户确认代码前，必须展示：

- 改了什么
- 为什么这么改
- 用户补充说明
- 仅展示变更片段

展示规则：

- 修改文件：展示 compact diff，只放调整的 hunk
- 新增代码：只展示新增部分，不展示整文件
- 不要展示未改动的大段上下文

### 6. SVN 提交与 Jira 流转

`svn commit` 成功后，Hook 会自动：

- 提取提交命令里的 Jira key
- 查询当前单据状态
- 按类型推进 Jira 流转

若要在提交前预判状态链，可先调用 `jira-local.plan_transition(issueKey)`。

默认流转链：

- 任务：`开放 -> 开发中 -> 提交测试`
- 缺陷：`开放 -> 开发中 -> 已解决`

### 7. 日报与周报

SVN 提交成功后会记录事件，并生成：

- `daily-YYYY-MM-DD.md`
- 若当天是周五，再生成 `weekly-周一-周五.md`

日报格式：

- 今日概览
- 今日完成
- 备注

周报格式：

- 本周概览
- 本周完成事项
- 风险与阻塞
- 下周建议

如需手动重建汇总：

```bash
python claude-assets/skills/daily-workflow/generate_work_summary.py --report-dir "<skill-home>/reports" --date 2026-03-27 --mode both
```

## 校验

手动校验命令：

```bash
python claude-assets/skills/daily-workflow/validate_daily_workflow_config.py
```

会检查：

- `jira-config.json` 是否存在且为合法 JSON
- Jira 必填字段是否完整
- `issueTypeAliases` 与 `reportOutputDir` 是否合法
- `svn-mapping.json` 是否存在且为合法 JSON
- 每条映射是否至少配置了一个真实路径

## 提交约定

可以提交：

- `.claude/settings.json`
- `.mcp.json`
- `jira-mcp/**`
- `claude-assets/**`
- `install.sh`
- `install.ps1`

不要提交：

- `.claude/settings.local.json`
- 明文账号、密码、Token
- 个人机器专用路径

## 一句话

先运行安装脚本，把配置落到 `~/.codex/skills/daily-workflow/` 或 `~/.claude/skills/daily-workflow/`，再补好 Jira 与 SVN 映射；之后就可以按“拉 Jira -> 改代码 -> 局部 diff 确认 -> SVN -> Jira -> 日报/周报”的顺序走完整条链。 

## Automated Verification

The workflow now supports config-driven automated verification commands inside `svn-mapping.json`.

Example:

```json
{
  "projectName": "一体化平台",
  "frontendPath": "D:/svn/imcp/web",
  "verification": {
    "testCommand": "npm test -- login",
    "buildCommand": "npm run build",
    "smokeCommand": "",
    "defaultCwd": "frontendPath",
    "shell": "powershell"
  }
}
```

If you are driving the flow through MCP, prefer:

- `jira-local.get_verification_plan(issueKey, matchIndex=0)`
- `jira-local.run_verification(issueKey, matchIndex=0, mode="auto")`

After the workspace is resolved, use either the configured commands directly or run:

```bash
python claude-assets/skills/daily-workflow/run_verification.py --workspace "D:/svn/imcp/web" --test-command "npm test -- login" --build-command "npm run build" --mode all
```

`--mode auto` runs the first configured command, usually the automated test command.
