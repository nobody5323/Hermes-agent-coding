"""Command-line entrypoint for the local AI Coding MVP."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .workflow import run_minimum_bugfix_loop


def _read_patch(path: str | None) -> str | None:
    if not path:
        return None
    return Path(path).read_text(encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m extensions.ai_coding.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the minimum AI Coding bug-fix loop")
    run_parser.add_argument("--repo", required=True, help="Target repository path")
    run_parser.add_argument("--task", required=True, help="User coding task")
    run_parser.add_argument("--patch", help="Unified diff patch file to preview and verify")
    run_parser.add_argument("--project-id", default="demo", help="Project id for stable chunk ids")
    run_parser.add_argument(
        "--sandbox",
        choices=["local", "docker"],
        default="local",
        help="Verification backend; docker requires Docker daemon",
    )
    run_parser.add_argument("--json", action="store_true", help="Print full JSON result")
    return parser


def run_command(args: argparse.Namespace) -> int:
    patch_text = _read_patch(args.patch)
    result = run_minimum_bugfix_loop(
        args.repo,
        args.task,
        patch_text=patch_text,
        project_id=args.project_id,
        sandbox_backend=args.sandbox,
    )

    if args.json:
        print(result.model_dump_json(indent=2))
    else:
        print(result.final_summary)
        if result.patch_preview and result.patch_preview.errors:
            print("\nPatch errors:")
            for error in result.patch_preview.errors:
                print(f"- {error}")

    if result.patch_preview and not result.patch_preview.valid:
        return 2
    if result.sandbox_result:
        return result.sandbox_result.exit_code
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return run_command(args)
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
