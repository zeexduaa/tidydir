"""Recording runs so they can be undone."""

from __future__ import annotations

import json
import shutil
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .planner import Move

JOURNAL_DIR = ".tidydir"
JOURNAL_FILE = "history.jsonl"


class JournalError(ValueError):
    """Raised when the undo journal is corrupt or unreadable."""

    def __init__(self, message: str, records: tuple[RunRecord, ...] = ()) -> None:
        super().__init__(message)
        self.records = records


@dataclass(frozen=True)
class RunRecord:
    id: str
    timestamp: float
    moves: tuple[tuple[str, str], ...]  # (source, target), POSIX paths relative to the root

    def to_json(self) -> str:
        return json.dumps(
            {"id": self.id, "timestamp": self.timestamp, "moves": [list(m) for m in self.moves]}
        )

    @classmethod
    def from_json(cls, line: str) -> RunRecord:
        data = json.loads(line)
        return cls(data["id"], data["timestamp"], tuple((s, t) for s, t in data["moves"]))


@dataclass
class UndoResult:
    record: RunRecord
    restored: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)


def journal_path(root: Path) -> Path:
    return Path(root) / JOURNAL_DIR / JOURNAL_FILE


def read_history(root: Path) -> list[RunRecord]:
    path = journal_path(root)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    records: list[RunRecord] = []
    for lineno, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            records.append(RunRecord.from_json(line))
        except (ValueError, KeyError, TypeError) as exc:
            raise JournalError(
                f"the undo journal is damaged at line {lineno}", records=tuple(records)
            ) from exc
    return records


def _write_history(root: Path, records: Iterable[RunRecord]) -> None:
    path = journal_path(root)
    path.parent.mkdir(exist_ok=True)
    path.write_text("".join(r.to_json() + "\n" for r in records), encoding="utf-8")


def _record_run(root: Path, moves: list[tuple[str, str]]) -> RunRecord:
    now = time.time()
    record = RunRecord(datetime.fromtimestamp(now).strftime("%Y%m%d-%H%M%S"), now, tuple(moves))
    path = journal_path(root)
    path.parent.mkdir(exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(record.to_json() + "\n")
    return record


def apply_plan(root: Path, moves: Iterable[Move]) -> RunRecord | None:
    """Move the files. Whatever was moved is recorded, even if a later move fails."""
    root = Path(root).resolve()
    done: list[tuple[str, str]] = []
    record = None
    try:
        for move in moves:
            if move.target.exists():
                raise FileExistsError(f"refusing to overwrite {move.target}")
            move.target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(move.source), str(move.target))
            done.append(
                (move.source.relative_to(root).as_posix(), move.target.relative_to(root).as_posix())
            )
    finally:
        if done:
            record = _record_run(root, done)
    return record


def undo_last(root: Path) -> UndoResult | None:
    """Move the files from the most recent run back. ``None`` if there is nothing to undo."""
    root = Path(root).resolve()
    history = read_history(root)
    if not history:
        return None
    result = UndoResult(history[-1])

    for source, target in reversed(result.record.moves):
        src, dst = root / source, root / target
        if not dst.exists():
            result.skipped.append((target, "no longer there"))
            continue
        if src.exists():
            result.skipped.append((target, f"{source} already exists"))
            continue
        src.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(dst), str(src))
        result.restored.append(source)
        _prune_empty_dirs(dst.parent, root)

    _write_history(root, history[:-1])
    return result


def _prune_empty_dirs(folder: Path, root: Path) -> None:
    while folder != root and root in folder.parents:
        try:
            folder.rmdir()
        except OSError:
            return
        folder = folder.parent
