"""Command-line interface."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from . import __version__
from .config import CONFIG_FILENAME, DEFAULT_CONFIG, ConfigError, find_config
from .journal import JournalError, apply_plan, read_history, undo_last
from .planner import Plan, PlanError, build_plan


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tidydir",
        description="Sort a messy folder into tidy subfolders using simple rules.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    def add(name: str, help_: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help_, description=help_)
        p.add_argument(
            "directory", nargs="?", default=Path("."), type=Path,
            help="folder to work on (default: current folder)",
        )
        return p

    config_help = f"config file (default: DIRECTORY/{CONFIG_FILENAME}, else built-in rules)"

    p = add("init", f"write a starter {CONFIG_FILENAME} into the folder")
    p.add_argument("--force", action="store_true", help="overwrite an existing config")

    p = add("plan", "show what would move, without moving anything")
    p.add_argument("-c", "--config", type=Path, help=config_help)

    p = add("run", "move the files")
    p.add_argument("-c", "--config", type=Path, help=config_help)
    p.add_argument("-y", "--yes", action="store_true", help="don't ask for confirmation")

    add("undo", "move the files from the last run back")
    add("history", "list past runs that can be undone")
    return parser


def _show_plan(plan: Plan, root: Path) -> None:
    for move in plan.moves:
        print(f"  {move.source.name}  ->  {move.target.relative_to(root).as_posix()}   [{move.rule}]")
    for path, reason in plan.skipped:
        print(f"  {path.name}  (skipped: {reason})")


def _load_plan(args: argparse.Namespace) -> tuple[Path, Plan]:
    root = args.directory.resolve()
    return root, build_plan(root, find_config(root, args.config))


def _confirm(question: str) -> bool:
    try:
        answer = input(f"{question} [y/N] ")
    except EOFError:
        return False
    return answer.strip().lower() in ("y", "yes")


def _cmd_init(args: argparse.Namespace) -> int:
    target = args.directory / CONFIG_FILENAME
    if target.exists() and not args.force:
        print(f"{target} already exists (use --force to overwrite)", file=sys.stderr)
        return 1
    target.write_text(DEFAULT_CONFIG, encoding="utf-8")
    print(f"Wrote {target}. Edit the rules, then preview with: tidydir plan {args.directory}")
    return 0


def _cmd_plan(args: argparse.Namespace) -> int:
    root, plan = _load_plan(args)
    _show_plan(plan, root)
    if not plan.moves:
        print("Nothing to move.")
    else:
        print(f"\n{len(plan.moves)} file(s) would move. Nothing has been changed yet.")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    root, plan = _load_plan(args)
    _show_plan(plan, root)
    if not plan.moves:
        print("Nothing to move.")
        return 0
    if not args.yes and not _confirm(f"\nMove {len(plan.moves)} file(s)?"):
        print("Cancelled, nothing moved.")
        return 1
    record = apply_plan(root, plan.moves)
    print(f"Moved {len(record.moves)} file(s). Changed your mind? Run: tidydir undo")
    return 0


def _cmd_undo(args: argparse.Namespace) -> int:
    result = undo_last(args.directory)
    if result is None:
        print("Nothing to undo.")
        return 0
    print(f"Restored {len(result.restored)} file(s) from run {result.record.id}.")
    for target, reason in result.skipped:
        print(f"  skipped {target}: {reason}")
    return 1 if result.skipped else 0


def _cmd_history(args: argparse.Namespace) -> int:
    try:
        history = read_history(args.directory.resolve())
    except JournalError as exc:
        for record in reversed(exc.records):
            when = datetime.fromtimestamp(record.timestamp)
            print(f"{record.id}  {when:%Y-%m-%d %H:%M}  {len(record.moves)} file(s)")
        print(f"tidydir: {exc}", file=sys.stderr)
        return 1

    if not history:
        print("No runs recorded.")
        return 0
    for record in reversed(history):
        when = datetime.fromtimestamp(record.timestamp)
        print(f"{record.id}  {when:%Y-%m-%d %H:%M}  {len(record.moves)} file(s)")
    return 0


COMMANDS = {
    "init": _cmd_init,
    "plan": _cmd_plan,
    "run": _cmd_run,
    "undo": _cmd_undo,
    "history": _cmd_history,
}


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.directory.is_dir():
        print(f"tidydir: not a folder: {args.directory}", file=sys.stderr)
        return 2
    try:
        return COMMANDS[args.command](args)
    except (ConfigError, PlanError, JournalError, OSError) as exc:
        print(f"tidydir: {exc}", file=sys.stderr)
        return 1
