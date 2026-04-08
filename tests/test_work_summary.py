from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "claude-assets" / "skills" / "daily-workflow"
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from work_summary import EVENTS_FILENAME, WorkEvent, append_event


class WorkSummaryTests(unittest.TestCase):
    def test_append_event_skips_duplicate_event_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            report_dir = Path(tmp_dir)
            event = WorkEvent(
                issue_key="IMCP-1",
                issue_type="任务",
                summary="Fix login bug",
                status="提交测试",
                project_key="IMCP",
                project_name="一体化平台",
                committed_at="2026-04-08T10:00:00+08:00",
                workspace="D:/svn/imcp/web",
                svn_command='svn commit -m "IMCP-1 fix login bug"',
                transitions=["提交测试"],
                event_id="revision-12345-IMCP-1",
            )

            append_event(report_dir, event)
            append_event(report_dir, event)

            lines = (report_dir / EVENTS_FILENAME).read_text(encoding="utf-8").splitlines()

        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])["eventId"], "revision-12345-IMCP-1")


if __name__ == "__main__":
    unittest.main()
