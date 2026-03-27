# daily-workflow

`daily-workflow` 是给 Claude Code 用的日常缺陷处理配置，解决四件事：

- 从 JIRA 拉取当前待处理 issue
- 把 issue 映射到本机 SVN 工作副本
- 辅助完成代码修改与验证
- 在 `svn commit` 成功后自动推进 JIRA 状态

仓库只保存可共享的脚本和模板。账号、密码、机器路径统一放本地 JSON，不进 git。

## 目录

```text
.
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
      └─ validate_daily_workflow_config.py
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

安装脚本会：
- 安装 `jira-mcp` 依赖
- 把 skill 同步到 `~/.claude/skills/daily-workflow/`
- 在该目录生成本地配置文件
- 若本地配置已存在，会询问是否用示例覆盖
- 执行配置校验

## 本地配置

只需要填两个文件。

实际配置目录：

```text
~/.claude/skills/daily-workflow/
```

### `jira-config.json`

用途：
- 配置 JIRA 连接信息
- 配置 daily-workflow 默认查询条件
- 供 `jira-mcp` 和 `svn_jira_transition_hook.py` 共用

核心字段：

```json
{
  "baseUrl": "https://jira.example.com",
  "username": "your_username",
  "password": "your_password",
  "apiPath": "/rest/api/2",
  "timeout": 20,
  "projects": ["IMCP", "KINGE"],
  "assignee": "currentUser()",
  "workingStatuses": ["开放", "开发中"]
}
```

字段说明：
- `baseUrl`：JIRA 根地址
- `username` / `password`：登录凭据
- `apiPath`：通常保持 `/rest/api/2`
- `timeout`：接口超时秒数
- `projects`：默认拉取的项目 key
- `assignee`：默认责任人筛选
- `workingStatuses`：待办列表展示的状态

### `svn-mapping.json`

用途：
- 把 JIRA 项目、组件、关键词映射到本机 SVN 路径
- 让 daily-workflow 能直接找到应该进入的工作目录

推荐示例：

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
- `projectName` 尽量和 JIRA 项目名称保持一致
- `componentName` 留空表示整项目共用一条映射
- `keywords` 只在项目和组件不够区分时再加
- `frontendPath`、`backendPath`、`rootPath` 至少填一个真实存在的路径

## 工作流

`jira-mcp/server.py` 提供 `jira-local` MCP server。
它会直接读取 `jira-config.json`，不再依赖环境变量。

`daily-workflow` skill 会按下面顺序匹配：
1. `projectName`
2. `componentName`
3. `keywords`

匹配成功后，优先进入最合适的本地 SVN 工作目录再继续分析代码。

Hook 脚本：`claude-assets/hooks/svn_jira_transition_hook.py`
会在 `svn commit` / `svn ci` 成功后：
- 提取 JIRA key
- 读取 `jira-config.json`
- 查询当前状态
- 按预定义链路推进

默认状态链：
- 任务：`开放 -> 开发中 -> 提交测试`
- 缺陷：`开放 -> 开发中 -> 已解决`

## 校验与排错

手动校验命令：

```bash
python claude-assets/skills/daily-workflow/validate_daily_workflow_config.py
```

会检查：
- `jira-config.json` 是否存在且 JSON 合法
- JIRA 必填字段是否填写完整
- `svn-mapping.json` 是否存在且 JSON 合法
- 每条映射是否至少配置了一个路径
- 配置里的路径在本机上是否真实存在

常见失败原因：
- `baseUrl`、`username`、`password` 没填
- `projects` 或 `workingStatuses` 为空
- `svn-mapping.json` 里填的是示例路径，没有改成真实路径
- `apiPath` 没有以 `/` 开头

首次安装说明：
- 如果脚本刚生成或刚覆盖了示例配置，会直接跳过校验
- 如果检测到当前配置仍与示例完全一致，也会跳过校验
- 如果检测到明显的占位内容，也会跳过校验并提示先改配置
- 这时应先去 `~/.claude/skills/daily-workflow/` 修改两个 JSON
- 改完后再重新运行安装脚本，或单独运行校验命令

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
- 明文账号、密码、token
- 个人机器专用路径

## 一句话

先运行安装脚本，让它把配置生成到 `~/.claude/skills/daily-workflow/`，再修改 `jira-config.json` 和 `svn-mapping.json`，最后重新校验。
