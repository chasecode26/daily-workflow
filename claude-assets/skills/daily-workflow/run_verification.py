from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def resolve_shell_command(shell_name: str, command: str) -> list[str]:
    normalized = (shell_name or "").strip().lower() or "powershell"
    if normalized == "cmd":
        return ["cmd", "/d", "/c", command]
    return ["powershell", "-NoProfile", "-Command", command]


def select_commands(args: argparse.Namespace) -> list[tuple[str, str]]:
    ordered = [
        ("test", args.test_command),
        ("build", args.build_command),
        ("smoke", args.smoke_command),
    ]
    available = [(name, command.strip()) for name, command in ordered if str(command or "").strip()]
    if args.mode == "all":
        return available
    if args.mode == "auto":
        return available[:1]
    return [(name, command) for name, command in available if name == args.mode]


def run_selected_verification(
    workspace: Path,
    *,
    test_command: str = "",
    build_command: str = "",
    smoke_command: str = "",
    shell: str = "powershell",
    mode: str = "auto",
) -> dict:
    commands = select_commands(
        argparse.Namespace(
            test_command=test_command,
            build_command=build_command,
            smoke_command=smoke_command,
            mode=mode,
        )
    )
    if not commands:
        return {
            "success": False,
            "skipped": True,
            "exitCode": 2,
            "message": "verification skipped: no automated verification commands configured",
            "results": [],
        }

    if not workspace.exists():
        return {
            "success": False,
            "skipped": False,
            "exitCode": 1,
            "message": f"verification failed: workspace does not exist -> {workspace}",
            "results": [],
        }

    results: list[dict] = []
    for label, command in commands:
        result = subprocess.run(
            resolve_shell_command(shell, command),
            cwd=str(workspace),
            text=True,
            capture_output=True,
        )
        item = {
            "stage": label,
            "command": command,
            "exitCode": result.returncode,
            "stdout": result.stdout.rstrip(),
            "stderr": result.stderr.rstrip(),
        }
        results.append(item)
        if result.returncode != 0:
            return {
                "success": False,
                "skipped": False,
                "exitCode": result.returncode,
                "message": f"verification failed at {label}: exit={result.returncode}",
                "results": results,
            }

    return {
        "success": True,
        "skipped": False,
        "exitCode": 0,
        "message": "verification passed",
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run configured daily-workflow verification commands.")
    parser.add_argument("--workspace", required=True, help="Working directory used to run verification commands.")
    parser.add_argument("--test-command", default="", help="Automated test command.")
    parser.add_argument("--build-command", default="", help="Build command.")
    parser.add_argument("--smoke-command", default="", help="Smoke validation command.")
    parser.add_argument("--shell", choices=("powershell", "cmd"), default="powershell", help="Shell used to execute commands.")
    parser.add_argument(
        "--mode",
        choices=("auto", "test", "build", "smoke", "all"),
        default="auto",
        help="Which verification stage to run. auto picks the first configured command.",
    )
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser()
    result = run_selected_verification(
        workspace,
        test_command=args.test_command,
        build_command=args.build_command,
        smoke_command=args.smoke_command,
        shell=args.shell,
        mode=args.mode,
    )
    for item in result["results"]:
        print(f"[{item['stage']}] {item['command']}")
        if item["stdout"]:
            print(item["stdout"])
        if item["stderr"]:
            print(item["stderr"])
    print(result["message"])
    return int(result["exitCode"])


if __name__ == "__main__":
    raise SystemExit(main())
