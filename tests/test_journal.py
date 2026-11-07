from datetime import datetime

import pytest

from conftest import touch
from tidydir.journal import JournalError, apply_plan, read_history, undo_last
from tidydir.planner import build_plan


def test_run_and_undo_round_trip(tmp_path, config):
    touch(tmp_path / "a.jpg")
    touch(tmp_path / "b.pdf")
    record = apply_plan(tmp_path, build_plan(tmp_path, config).moves)

    assert (tmp_path / "Images" / "a.jpg").exists()
    assert not (tmp_path / "a.jpg").exists()
    assert read_history(tmp_path) == [record]

    result = undo_last(tmp_path)
    assert sorted(result.restored) == ["a.jpg", "b.pdf"]
    assert (tmp_path / "a.jpg").exists() and (tmp_path / "b.pdf").exists()
    assert not (tmp_path / "Images").exists()
    assert not (tmp_path / "Docs").exists()
    assert read_history(tmp_path) == []


def test_nothing_to_undo(tmp_path):
    assert undo_last(tmp_path) is None


def test_empty_plan_records_nothing(tmp_path):
    assert apply_plan(tmp_path, []) is None
    assert read_history(tmp_path) == []


def test_undo_skips_files_that_were_moved_away(tmp_path, config):
    touch(tmp_path / "a.jpg")
    apply_plan(tmp_path, build_plan(tmp_path, config).moves)
    (tmp_path / "Images" / "a.jpg").unlink()
    result = undo_last(tmp_path)
    assert result.restored == []
    assert result.skipped == [("Images/a.jpg", "no longer there")]


def test_undo_does_not_overwrite_a_new_file(tmp_path, config):
    touch(tmp_path / "a.jpg")
    apply_plan(tmp_path, build_plan(tmp_path, config).moves)
    touch(tmp_path / "a.jpg", b"new")
    result = undo_last(tmp_path)
    assert result.skipped == [("Images/a.jpg", "a.jpg already exists")]
    assert (tmp_path / "a.jpg").read_bytes() == b"new"


def test_undo_keeps_folders_that_still_have_files(tmp_path, config):
    touch(tmp_path / "a.jpg")
    apply_plan(tmp_path, build_plan(tmp_path, config).moves)
    touch(tmp_path / "Images" / "mine.png")
    undo_last(tmp_path)
    assert (tmp_path / "Images" / "mine.png").exists()


def test_partial_run_is_still_recorded(tmp_path, config):
    touch(tmp_path / "a.jpg")
    touch(tmp_path / "b.pdf", mtime=datetime(2023, 5, 1).timestamp())
    moves = build_plan(tmp_path, config).moves
    touch(tmp_path / "Docs" / "2023" / "b.pdf")  # appears after planning

    with pytest.raises(FileExistsError):
        apply_plan(tmp_path, moves)

    [record] = read_history(tmp_path)
    assert record.moves == (("a.jpg", "Images/a.jpg"),)


def test_undo_goes_newest_first(tmp_path, config):
    touch(tmp_path / "a.jpg")
    apply_plan(tmp_path, build_plan(tmp_path, config).moves)
    touch(tmp_path / "b.png")
    apply_plan(tmp_path, build_plan(tmp_path, config).moves)

    assert undo_last(tmp_path).restored == ["b.png"]
    assert (tmp_path / "Images" / "a.jpg").exists()
    assert len(read_history(tmp_path)) == 1





def test_damaged_journal_raises_journal_error(tmp_path):
    history_file = tmp_path / ".tidydir" / "history.jsonl"
    history_file.parent.mkdir()
    history_file.write_text(
        '{"id": "r1", "timestamp": 123.0, "moves": [["a.txt", "Text/a.txt"]]}\n{broken\n',
        encoding="utf-8",
    )
    with pytest.raises(JournalError, match="the undo journal is damaged at line 2") as exc_info:
        read_history(tmp_path)
    assert len(exc_info.value.records) == 1
    assert exc_info.value.records[0].id == "r1"
