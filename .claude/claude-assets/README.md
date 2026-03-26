# Claude Assets

## 目录目的

把项目级 Claude Code 配置实际内容集中放在这里，避免 hook、skill、MCP 模板散落在项目根目录。

## 必须保留在入口位置的文件

以下文件不能挪到本目录，否则 Claude Code 不会自动识别：

- `/.claude/settings.json`
- `/.mcp.json`

它们的职责：
- `/.claude/settings.json`：项目级 settings / hooks 入口
- `/.mcp.json`：项目级 MCP 入口

## 当前目录结构

```text
.claude/
  settings.json
  settings.local.json
  claude-assets/
    README.md
    hooks/
      svn_jira_transition_hook.py
    mcp/
      mcp.template.json
    skills/
      daily-bug-workflow/
        SKILL.md
        jira-status-map.md
```

## 子目录说明

### hooks/
放项目级 hook 的实际脚本。

当前文件：
- `hooks/svn_jira_transition_hook.py`

用途：
- 在 `svn commit` / `svn ci` 成功后，根据命令中的 JIRA key 自动推进 JIRA 状态

### mcp/
放 MCP 模板、说明文件或后续需要纳入版本管理的项目级 MCP 相关内容。

当前文件：
- `mcp/mcp.template.json`

说明：
- 真正生效的入口仍然是项目根目录的 `/.mcp.json`
- 这里保留模板，方便维护和复用

### skills/
放项目级技能内容。

当前文件：
- `skills/daily-bug-workflow/SKILL.md`
- `skills/daily-bug-workflow/jira-status-map.md`

## git 提交规则

适合提交：
- `/.claude/settings.json`
- `/.mcp.json`
- `/.claude/claude-assets/**`

不要提交：
- `/.claude/settings.local.json`
- 明文账号、密码、token
- 仅适用于个人机器的本地覆盖内容

## 环境变量规则

敏感配置不要写死在 git 文件里，统一走环境变量：

- `JIRA_BASE_URL`
- `JIRA_USERNAME`
- `JIRA_PASSWORD`
- `JIRA_API_PATH`

## 维护约定

1. 优先修改 `claude-assets` 下的实际内容
2. 入口文件只保留最小必要配置
3. 如果增加新的 hook / skill / MCP 模板，继续按当前目录分类放置
4. 如果某个 MCP 真正启用，需要同步检查 `/.mcp.json` 与 `/.claude/settings.json`
