from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path


EVENTS_FILENAME = "work-events.jsonl"


@dataclass(slots=True)
class WorkEvent:
    issue_key: str
    issue_type: str
    summary: str
    status: str
    project_key: str
    project_name: str
    committed_at: str
    workspace: str
    svn_command: str
    transitions: list[str]
    event_id: str = ""
    svn_revision: str = ""

    def to_dict(self) -> dict:
        return {
            "issueKey": self.issue_key,
            "issueType": self.issue_type,
            "summary": self.summary,
            "status": self.status,
            "projectKey": self.project_key,
            "projectName": self.project_name,
            "committedAt": self.committed_at,
            "workspace": self.workspace,
            "svnCommand": self.svn_command,
            "transitions": self.transitions,
            "eventId": self.event_id,
            "svnRevision": self.svn_revision,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorkEvent":
        return cls(
            issue_key=str(data.get("issueKey", "")).strip(),
            issue_type=str(data.get("issueType", "")).strip() or "Unknown",
            summary=str(data.get("summary", "")).strip(),
            status=str(data.get("status", "")).strip(),
            project_key=str(data.get("projectKey", "")).strip(),
            project_name=str(data.get("projectName", "")).strip(),
            committed_at=str(data.get("committedAt", "")).strip(),
            workspace=str(data.get("workspace", "")).strip(),
            svn_command=str(data.get("svnCommand", "")).strip(),
            transitions=[str(item).strip() for item in (data.get("transitions") or []) if str(item).strip()],
            event_id=str(data.get("eventId", "")).strip(),
            svn_revision=str(data.get("svnRevision", "")).strip(),
        )


def ensure_report_dir(report_dir: Path) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir


def append_event(report_dir: Path, event: WorkEvent) -> Path:
    report_dir = ensure_report_dir(report_dir)
    events_path = report_dir / EVENTS_FILENAME
    if event.event_id and events_path.exists():
        for raw_line in events_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                existing = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(existing.get("eventId", "")).strip() == event.event_id:
                return events_path
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
    return events_path


def load_events(report_dir: Path) -> list[WorkEvent]:
    events_path = report_dir / EVENTS_FILENAME
    if not events_path.exists():
        return []

    events: list[WorkEvent] = []
    for raw_line in events_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        events.append(WorkEvent.from_dict(json.loads(line)))
    return events


def _event_date(event: WorkEvent) -> date:
    return datetime.fromisoformat(event.committed_at).date()


def _event_project(event: WorkEvent) -> str:
    return event.project_name or event.project_key or "Unknown Project"


def _group_by_type(events: list[WorkEvent]) -> dict[str, list[WorkEvent]]:
    grouped: dict[str, list[WorkEvent]] = defaultdict(list)
    for event in events:
        grouped[event.issue_type or "Unknown"].append(event)
    return dict(sorted(grouped.items(), key=lambda item: item[0].lower()))


def _group_by_project(events: list[WorkEvent]) -> dict[str, list[WorkEvent]]:
    grouped: dict[str, list[WorkEvent]] = defaultdict(list)
    for event in events:
        grouped[_event_project(event)].append(event)
    return dict(sorted(grouped.items(), key=lambda item: item[0].lower()))


def _format_transition(event: WorkEvent) -> str:
    return " -> ".join(event.transitions) if event.transitions else "未流转"


def _classify_issue_category(issue_type: str) -> str:
    normalized = (issue_type or "").strip().lower()
    if normalized in {"bug", "缺陷", "故障"}:
        return "bug"
    if normalized in {"task", "story", "任务", "需求"}:
        return "task"
    return "other"


def _render_event_line(event: WorkEvent, include_date: bool) -> str:
    committed_at = datetime.fromisoformat(event.committed_at)
    when = committed_at.strftime("%Y-%m-%d %H:%M") if include_date else committed_at.strftime("%H:%M")
    workspace = event.workspace or "-"
    return (
        f"- `{event.issue_key}` {event.summary or '-'}"
        f" | 类型={event.issue_type or '-'}"
        f" | 状态={event.status or '-'}"
        f" | 流转={_format_transition(event)}"
        f" | 时间={when}"
        f" | 路径={workspace}"
    )


def _build_overview_lines(events: list[WorkEvent]) -> list[str]:
    if not events:
        return ["- 总计：0", "- 任务：0", "- 缺陷：0", "- 其他：0"]

    total = len(events)
    task_count = sum(1 for event in events if _classify_issue_category(event.issue_type) == "task")
    bug_count = sum(1 for event in events if _classify_issue_category(event.issue_type) == "bug")
    other_count = total - task_count - bug_count
    return [
        f"- 总计：{total}",
        f"- 任务：{task_count}",
        f"- 缺陷：{bug_count}",
        f"- 其他：{other_count}",
        f"- 项目数：{len(_group_by_project(events))}",
    ]


def build_daily_report(events: list[WorkEvent], target_day: str) -> str:
    day_events = [event for event in events if _event_date(event).isoformat() == target_day]
    lines = [f"# 日报 - {target_day}", ""]

    lines.append("## 今日概览")
    lines.extend(_build_overview_lines(day_events))
    lines.append("")

    lines.append("## 今日完成")
    if not day_events:
        lines.append("- 今日未记录已处理的 Jira 任务或缺陷。")
    else:
        for project_name, project_events in _group_by_project(day_events).items():
            lines.append(f"### {project_name}")
            for event in project_events:
                lines.append(_render_event_line(event, include_date=False))
            lines.append("")
        if lines[-1] == "":
            lines.pop()
    lines.append("")

    lines.append("## 备注")
    if not day_events:
        lines.append("- 无。")
    else:
        lines.append("- 本日报基于 SVN 成功提交后自动汇总。")
        lines.append("- 若需补录，可手动维护事件文件后重新生成。")
    return "\n".join(lines).rstrip() + "\n"


def build_weekly_report(events: list[WorkEvent], target_day: str) -> str:
    target_date = date.fromisoformat(target_day)
    week_start = target_date - timedelta(days=target_date.weekday())
    week_end = week_start + timedelta(days=4)
    weekly_events = [event for event in events if week_start <= _event_date(event) <= week_end]

    lines = [f"# 周报 - {week_start.isoformat()} 至 {week_end.isoformat()}", ""]

    lines.append("## 本周概览")
    lines.extend(_build_overview_lines(weekly_events))
    lines.append("")

    lines.append("## 本周完成事项")
    if not weekly_events:
        lines.append("- 本周未记录已处理的 Jira 任务或缺陷。")
    else:
        for project_name, project_events in _group_by_project(weekly_events).items():
            lines.append(f"### {project_name}")
            for event in project_events:
                lines.append(_render_event_line(event, include_date=True))
            lines.append("")
        if lines[-1] == "":
            lines.pop()
    lines.append("")

    lines.append("## 风险与阻塞")
    lines.append("- 自动汇总仅覆盖已成功 SVN 提交的事项；未提交内容不会进入周报。")
    lines.append("- 如需补充业务说明，可在生成后的 Markdown 中手动追加。")
    lines.append("")

    lines.append("## 下周建议")
    if not weekly_events:
        lines.append("- 无历史提交记录，可从 Jira 待办重新拉取。")
    else:
        lines.append("- 对已进入测试/已解决状态的事项，跟进测试反馈与回归结果。")
        lines.append("- 对本周高频项目，优先检查是否存在可复用修复模式或公共组件问题。")
    return "\n".join(lines).rstrip() + "\n"


def write_daily_report(report_dir: Path, target_day: str) -> Path:
    report_dir = ensure_report_dir(report_dir)
    output_path = report_dir / f"daily-{target_day}.md"
    output_path.write_text(build_daily_report(load_events(report_dir), target_day), encoding="utf-8")
    return output_path


def write_weekly_report(report_dir: Path, target_day: str) -> Path:
    report_dir = ensure_report_dir(report_dir)
    target_date = date.fromisoformat(target_day)
    week_start = target_date - timedelta(days=target_date.weekday())
    week_end = week_start + timedelta(days=4)
    output_path = report_dir / f"weekly-{week_start.isoformat()}-{week_end.isoformat()}.md"
    output_path.write_text(build_weekly_report(load_events(report_dir), target_day), encoding="utf-8")
    return output_path
