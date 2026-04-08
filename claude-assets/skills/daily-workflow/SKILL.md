---
name: daily-workflow
description: Use for the daily-workflow JIRA -> local SVN flow, including issue selection, path mapping, change preview, verification, SVN submission, and JIRA status transitions.
---

# daily-workflow

## Overview

Standardize the `daily-workflow` flow for JIRA-driven work:
1. Pull candidate issues from JIRA
2. Let the user choose one issue
3. Ask what should be changed and capture any supplemental explanation
4. Resolve local frontend/backend SVN paths from config
5. Edit only after reading the relevant code
6. Verify the change
7. Before user confirmation, show a compact code preview and explain the change
8. Submit to SVN only after user approval
9. Transition JIRA after SVN succeeds
10. Auto-generate daily markdown, and weekly markdown every Friday

## Required Local Files

Read these files before starting:
- `jira-config.json` for JIRA connection info, default filters, issue-type aliases, and report output path
- `svn-mapping.json` for JIRA to local SVN path mapping
- `jira-status-map.md` for allowed resolve transitions

Use `jira-config.example.json` and `svn-mapping.example.json` only as structure references when the real local files are missing.

## Workflow

### 1. Default to "my JIRA" list mode
Unless the user gives a specific JIRA key like `BUG-12345`, start by pulling **my current issue list**.

The pull step must support:
- `all` (default)
- `task`
- `bug`

Prefer the `jira-local.get_my_issues` MCP tool first.

Available MCP helpers for this workflow:
- `jira-local.resolve_workspace(issueKey)` to resolve frontend/backend/root SVN candidates from `svn-mapping.json`
- `jira-local.plan_transition(issueKey)` to preview the next JIRA status step before any transition is executed
- `jira-local.get_verification_plan(issueKey, matchIndex=0)` to resolve the automated verification workspace and commands
- `jira-local.run_verification(issueKey, matchIndex=0, mode="auto")` to execute the configured automated verification

### 2. Pull and display issues
Use the configured defaults:
- assignee = `jira-config.json.assignee`
- projects = `jira-config.json.projects`
- statuses = `jira-config.json.workingStatuses`

Display only:
- JIRA key
- title
- issue type
- project
- component
- status
- likely impact side: frontend / backend / fullstack

Keep the list compact so the user can choose quickly.

### 3. Confirm issue selection and change scope
After the user selects one issue, ask for:
- the exact modification target
- any supplemental explanation the user wants added to the change description

Treat that supplemental explanation as part of the final verification and confirmation summary.

### 4. Direct issue mode
If the user gives a JIRA key like `BUG-12345`, skip the list and load that issue directly.

### 5. Resolve local paths
After one issue is selected, match in this order:
1. `projectName` exact match
2. `componentName` exact match
3. keyword match from title / description

Prefer `jira-local.resolve_workspace(issueKey)` first when the local mapping file is present.

If one mapping matches, continue.
If multiple mappings match, stop and ask the user to choose.
If no mapping matches, ask whether to save a new mapping before writing config.

### 6. Open work area
After mapping succeeds:
- surface `frontendPath` if present
- surface `backendPath` if present
- surface `rootPath` if present
- open or enter the most likely path first
- then search code using issue title, component keywords, labels, API clues, and the user-provided modification target

### 7. Modify and verify
Prefer verification in this order:
1. existing automated test command
2. build command
3. startup + smoke validation
4. browser validation only if the project already has a stable local workflow

If the resolved workspace includes `verification.testCommand`, `verification.buildCommand`, or `verification.smokeCommand`, prefer those configured commands first.

You may execute them through:
- direct shell execution in the selected workspace, or
- `python claude-assets/skills/daily-workflow/run_verification.py --workspace "<path>" --test-command "<cmd>" --build-command "<cmd>" --smoke-command "<cmd>" --mode auto|all`

If verification cannot run, explain why and downgrade to manual verification pending.

### 8. User confirmation gate
Before asking the user to confirm code submission, always show:
- a short explanation of what changed
- a short explanation of why it changed
- the user-provided supplemental explanation, if any
- only the adjusted code sections

Preview rules:
- Show only changed hunks, never the full file.
- For modified files, present a compact diff.
- For newly added code, show only the added code content.
- Do not show untouched lines unless they are needed for minimal context.
- Keep the preview focused on the exact adjustment area.

### 9. SVN submission gate
If verification passes:
- ask whether to submit the code to SVN
- do not change JIRA before SVN submission finishes successfully

Never commit or push SVN automatically unless the user asked for it.

### 10. JIRA status transition after SVN submission
After SVN submission succeeds, transition JIRA immediately in workflow order.

Before executing any transition, prefer `jira-local.plan_transition(issueKey)` to preview the remaining chain and confirm the next target is actually available in the current workflow state.

For `任务`:
- `开放 -> 开发中 -> 提交测试`

For `缺陷`:
- `开放 -> 开发中 -> 已解决`

Rules:
- Skip statuses already passed.
- If the transition API rejects a step, stop there and report the failed step.
- Do not mark JIRA complete before SVN submission succeeds.

### 11. Auto summary output
After a successful SVN submission:
- append the processed issue to the local event log
- generate `daily-YYYY-MM-DD.md`
- if the current day is Friday, also generate `weekly-YYYY-MM-DD-YYYY-MM-DD.md`

Report output directory defaults to `jira-config.json.reportOutputDir`, otherwise `<active-skill-home>/reports` under either `.codex` or `.claude`.

In Codex environments without automatic post-tool hooks, run `python claude-assets/hooks/svn_jira_transition_hook.py --plain --cwd "<workspace>" --command 'svn commit -m "KEY-123 message"'` after a successful SVN commit to execute the same transition/report flow manually.

## Response Format

Keep responses short and structured.

### A. JIRA list mode
Use one compact line per issue:
- `KEY | title | type | project | component | status | frontend/backend/fullstack`

Then stop and ask the user to choose exactly one key.

### B. After one issue is selected
Return in this order:
- issue summary
- user change target
- supplemental explanation
- matched frontend/backend/workspace paths
- resolved automated verification commands, if any
- which path will be opened first
- verification plan
- current blocker or confirmation request

### C. Before user confirmation
Return in this order:
- change summary
- why the change solves the issue
- supplemental explanation
- compact code preview with changed hunks only
- verification commands that were actually run
- verification result
- whether to submit to SVN

### D. After successful SVN submission
Return in this order:
- SVN result
- JIRA issue type
- transition plan preview, if it was checked before execution
- transition chain executed
- final JIRA status
- generated daily report path
- generated weekly report path when the day is Friday
