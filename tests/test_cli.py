from conftest import touch
from tidydir.cli import main


def test_init_writes_config_once(tmp_path, capsys):
    assert main(["init", str(tmp_path)]) == 0
    assert "[[rule]]" in (tmp_path / "tidydir.toml").read_text(encoding="utf-8")
    assert main(["init", str(tmp_path)]) == 1
    assert "already exists" in capsys.readouterr().err
    assert main(["init", str(tmp_path), "--force"]) == 0


def test_plan_run_history_undo(tmp_path, capsys):
    touch(tmp_path / "photo.jpg")
    touch(tmp_path / "report.pdf")

    assert main(["plan", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "photo.jpg  ->  Images/" in out
    assert "report.pdf  ->  Documents/pdf/report.pdf" in out
    assert (tmp_path / "photo.jpg").exists()

    assert main(["run", str(tmp_path), "--yes"]) == 0
    assert not (tmp_path / "photo.jpg").exists()
    assert (tmp_path / "Documents" / "pdf" / "report.pdf").exists()

    assert main(["history", str(tmp_path)]) == 0
    assert "2 file(s)" in capsys.readouterr().out

    assert main(["undo", str(tmp_path)]) == 0
    assert (tmp_path / "photo.jpg").exists()
    assert not (tmp_path / "Documents").exists()


def test_run_asks_before_moving(tmp_path, monkeypatch):
    touch(tmp_path / "photo.jpg")
    monkeypatch.setattr("builtins.input", lambda _: "n")
    assert main(["run", str(tmp_path)]) == 1
    assert (tmp_path / "photo.jpg").exists()


def test_custom_config_flag(tmp_path, capsys):
    config = tmp_path / "rules.toml"
    config.write_text("[[rule]]\nextensions = ['txt']\ndestination = 'Text'\n", encoding="utf-8")
    work = tmp_path / "work"
    touch(work / "a.txt")
    assert main(["plan", str(work), "--config", str(config)]) == 0
    assert "a.txt  ->  Text/a.txt" in capsys.readouterr().out


def test_bad_config_is_reported(tmp_path, capsys):
    (tmp_path / "tidydir.toml").write_text("[[rule]]\nname = 'x'\n", encoding="utf-8")
    assert main(["plan", str(tmp_path)]) == 1
    assert "destination" in capsys.readouterr().err


def test_missing_folder(tmp_path, capsys):
    assert main(["plan", str(tmp_path / "nope")]) == 2
    assert "not a folder" in capsys.readouterr().err


def test_empty_folder(tmp_path, capsys):
    assert main(["run", str(tmp_path), "--yes"]) == 0
    assert "Nothing to move." in capsys.readouterr().out





def test_history_and_undo_on_damaged_journal(tmp_path, capsys):
    history_file = tmp_path / ".tidydir" / "history.jsonl"
    history_file.parent.mkdir()
    history_file.write_text('{broken\n', encoding="utf-8")

    assert main(["history", str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert "the undo journal is damaged at line 1" in err

    assert main(["undo", str(tmp_path)]) == 1
    err2 = capsys.readouterr().err
    assert "the undo journal is damaged at line 1" in err2


def test_history_shows_readable_runs_before_damaged_line(tmp_path, capsys):
    history_file = tmp_path / ".tidydir" / "history.jsonl"
    history_file.parent.mkdir()
    history_file.write_text(
        '{"id": "20261107-120000", "timestamp": 1700000000.0, "moves": [["x.jpg", "Images/x.jpg"]]}\n{corrupt\n',
        encoding="utf-8",
    )

    assert main(["history", str(tmp_path)]) == 1
    captured = capsys.readouterr()
    assert "20261107-120000" in captured.out
    assert "1 file(s)" in captured.out
    assert "the undo journal is damaged at line 2" in captured.err
