from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from work_summary import write_daily_report, write_weekly_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate daily-workflow markdown summaries.")
    parser.add_argument("--report-dir", required=True, help="Directory used to store summary files.")
    parser.add_argument(
        "--date",
        default=datetime.now().date().isoformat(),
        help="Target date in YYYY-MM-DD format. Defaults to today.",
    )
    parser.add_argument(
        "--mode",
        choices=("daily", "weekly", "both"),
        default="both",
        help="Which summaries to generate.",
    )
    args = parser.parse_args()

    report_dir = Path(args.report_dir).expanduser()
    outputs: list[Path] = []
    if args.mode in ("daily", "both"):
        outputs.append(write_daily_report(report_dir, args.date))
    if args.mode in ("weekly", "both"):
        outputs.append(write_weekly_report(report_dir, args.date))

    for output in outputs:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
