---
name: daily-workflow
description: Use for the daily-workflow JIRA -> local SVN flow, including issue selection, path mapping, verification, SVN submission, and JIRA status transitions.
---

# daily-workflow

## Overview

Standardize the `daily-workflow` flow for JIRA-driven work:
1. Pull **my** candidate issues by assignee and project
2. Let the user select one issue
3. Resolve local frontend/backend SVN paths from config
4. Open the matched workspace and begin code search/editing
5. Run the best available automated verification
6. Commit the code to SVN when the user asks
7. Transition JIRA in the correct order after SVN submission

**Core principle:** Default to the real daily-workflow sequence: pull my JIRA list, choose one issue, open the right local path, verify, submit SVN, then advance JIRA to the next required state.

## When to Use

Use when:
- The user wants to process daily issues from internal JIRA
- The issue must be located through project + component mapping
- The local code is managed in SVN
- The workflow should open the right frontend/backend directory automatically
- The workflow should verify first, then submit SVN, then advance JIRA status

Do not use when:
- The task does not start from JIRA
- The user already gave an exact local path and only wants a code edit
- The task is bulk triage across many issues

## Required Local Files

Read these files before starting:
- `jira-config.json` for the real JIRA connection info and default filters
- `svn-mapping.json` for the real JIRA to local SVN path mapping
- `jira-status-map.md` for allowed resolve transitions

Use `jira-config.example.json` and `svn-mapping.example.json` only as structure references when the real local files are missing.

## Workflow

### 1. Default to "my JIRA" list mode
Unless the user gives a specific JIRA key like `BUG-12345`, start by pulling **my current issue list** with assignee + project filters.

### 2. Pull and display issues
Use `jira-mcp` first. If needed, use browser fallback.
Default filters should prefer:
- assignee = `jira-config.json` 中的 `assignee`
- project in `jira-config.json` 中的 `projects`
- status in `jira-config.json` 中的 `workingStatuses`

Show only:
- JIRA key
- title
- project
- component
- status
- likely impact side: frontend / backend / fullstack

Keep the list compact so the user can choose quickly.

### 3. Confirm issue selection
In list mode, always stop and ask the user to choose exactly one issue.
Do not skip straight into path matching when more than one issue is present.

### 4. Direct issue mode
If the user gives a JIRA key like `BUG-12345`, skip the list and load that issue directly.

### 5. Resolve local paths
After one issue is selected, match with this order:
1. `projectName` exact match
2. `componentName` exact match
3. keyword match from title / description

If one mapping matches, continue.
If multiple mappings match, stop and ask the user to choose.
If no mapping matches, ask whether to save a new mapping before writing config.

### 6. Open work area
After mapping succeeds:
- surface `frontendPath` if present
- surface `backendPath` if present
- open or enter the matched path first
- then search code using issue title, component keywords, labels, or API clues

### 7. Modify and verify
Prefer in this order:
1. existing automated test command
2. build command
3. startup + smoke validation
4. browser login validation only when the project already has a stable local workflow

If verification cannot run, explain why and downgrade to manual verification pending.

### 8. SVN submission gate
If verification passes:
- ask whether to submit the code to SVN
- do not change JIRA before SVN submission finishes successfully

Never commit or push SVN automatically unless the user asked for it.

### 9. JIRA status transition after SVN submission
After SVN submission succeeds, transition JIRA immediately in workflow order.

For **任务**:
- if current status is `开放`, first change to `开发中`
- then change to `提交测试`
- target flow: `开放 -> 开发中 -> 提交测试`

For **缺陷**:
- if current status is `开放`, first change to `开发中`
- then change to `已解决`
- target flow: `开放 -> 开发中 -> 已解决`

Rules:
- Skip statuses already passed. Example: if a 任务 is already `开发中`, move it directly to `提交测试` after SVN submission.
- If the transition API rejects a step, stop there, report the failed step, and do not guess alternate statuses.
- Do not mark JIRA complete before SVN submission succeeds.
- Treat status names as exact business states: `开放`, `开发中`, `提交测试`, `已解决`.

## Quick Reference

| Issue type | After successful SVN submission |
|-----------|----------------------------------|
| 任务 | `开放 -> 开发中 -> 提交测试` |
| 缺陷 | `开放 -> 开发中 -> 已解决` |

## Failure Handling

- If JIRA fields are incomplete, switch to code-search-assisted mode
- If mapped paths do not exist, treat mapping as stale and ask for replacement
- If verification fails to start, keep the issue open and report the blocker
- If SVN submission fails, do not change JIRA status
- If a JIRA transition fails, preserve the current state and report which step failed

## Response Format

Keep responses short and structured.

### A. JIRA list mode
When showing candidate issues, prefer one compact line per issue:
- `KEY | 标题 | 项目 | 组件 | 状态 | frontend/backend/fullstack`

Then stop and ask the user to choose exactly one key.

### B. After one issue is selected
Return in this order:
- issue summary
- matched frontend/backend/workspace paths
- which path will be opened first
- verification plan
- current blocker or confirmation request

Example shape:
- `Issue: IMCP-1234 | 登录后菜单不显示 | 一体化平台 / 权限管理 | 处理中`
- `Paths: FE=D:/svn/... | BE=D:/svn/... | Root=D:/svn/...`
- `Next: enter FE path first and search login/menu related code`
- `Verify: existing test -> build -> smoke`
- `Need: confirm this issue selection`

### C. After successful SVN submission
Return in this order:
- SVN result
- JIRA issue type
- transition chain executed
- final JIRA status
- any failed transition step if applicable
