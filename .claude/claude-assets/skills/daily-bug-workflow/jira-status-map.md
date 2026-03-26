# JIRA Status Map

## Purpose

Document project-specific status transition rules used after successful SVN submission.

## Shared Rules

- Do not change JIRA before SVN submission succeeds
- Read current issue status and available transitions before each step
- Skip statuses already passed, but do not guess alternate status names
- If a required transition is unavailable, stop and report the failed step

## Standard Mapping

| Issue Type | Workflow Chain | Notes |
| --- | --- | --- |
| 任务 | 开放 -> 开发中 -> 提交测试 | If already at `开发中`, move directly to `提交测试` |
| 缺陷 | 开放 -> 开发中 -> 已解决 | If already at `开发中`, move directly to `已解决` |

## Runtime Rule

After successful SVN submission:
1. read current issue type and current status
2. confirm available transitions for the current status
3. execute the next required transition in the configured chain
4. re-read available transitions for the next step if another step is still required
5. stop immediately if any step is rejected or missing

## Failure Branches

- If issue type is not `任务` or `缺陷`, skip automatic transition and report it
- If current status is not in the configured chain, skip automatic transition and report it
- If the next required transition is unavailable, preserve the current status and report which step failed
- If JIRA API permission is denied or request fails, keep the issue unchanged and tell the user to handle it manually or retry later
