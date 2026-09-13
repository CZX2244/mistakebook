"""CLI contract tests, especially for agent-facing JSON output."""

import csv
import json

from mistakebook.cli import main


def run_json(capsys, db, *command):
    rc = main(["--db", str(db), "--json", *command])
    captured = capsys.readouterr()
    stream = captured.out if captured.out else captured.err
    return rc, json.loads(stream), captured


def test_json_add_update_archive_lifecycle(tmp_path, capsys):
    db = tmp_path / "book.db"
    rc, added, _ = run_json(
        capsys, db,
        "add", "--subject", "数学", "--question", "1+1", "--answer", "2",
        "--image", "scan.png",
    )
    assert rc == 0
    mid = added["id"]
    assert added["mistake"]["source_image"] == "scan.png"

    rc, updated, _ = run_json(capsys, db, "update", str(mid), "--analysis", "会了")
    assert rc == 0
    assert updated["updated"] is True
    assert updated["mistake"]["analysis"] == "会了"

    rc, archived, _ = run_json(capsys, db, "archive", str(mid))
    assert rc == 0
    assert archived["archived"] is True

    rc, restored, _ = run_json(capsys, db, "archive", str(mid), "--unarchive")
    assert rc == 0
    assert restored["archived"] is False


def test_json_errors_are_machine_readable(tmp_path, capsys):
    db = tmp_path / "book.db"
    rc, payload, captured = run_json(capsys, db, "show", "999")
    assert rc == 1
    assert captured.out == ""
    assert payload["error"]["code"] == "not_found"
    assert payload["error"]["id"] == 999


def test_json_update_without_fields_is_machine_readable(tmp_path, capsys):
    db = tmp_path / "book.db"
    rc, payload, _ = run_json(capsys, db, "update", "1")
    assert rc == 1
    assert payload["error"]["code"] == "invalid_input"


def test_csv_export_keeps_source_image(tmp_path, capsys):
    db = tmp_path / "book.db"
    out = tmp_path / "mistakes.csv"
    run_json(
        capsys, db,
        "add", "--subject", "物理", "--question", "Q", "--answer", "A",
        "--image", "photo.jpg",
    )
    rc = main(["--db", str(db), "export", "--format", "csv", "--output", str(out)])
    assert rc == 0
    capsys.readouterr()
    with out.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["source_image"] == "photo.jpg"


def test_json_export_with_output_returns_status(tmp_path, capsys):
    db = tmp_path / "book.db"
    out = tmp_path / "mistakes.json"
    run_json(capsys, db, "add", "--subject", "数学", "--question", "Q", "--answer", "A")
    rc, payload, _ = run_json(
        capsys, db, "export", "--format", "json", "--output", str(out)
    )
    assert rc == 0
    assert payload == {"count": 1, "format": "json", "output": str(out)}
    exported = json.loads(out.read_text(encoding="utf-8"))
    assert exported[0]["subject"] == "数学"


def test_json_export_without_output_is_structured(tmp_path, capsys):
    db = tmp_path / "book.db"
    run_json(capsys, db, "add", "--subject", "英语", "--question", "Q", "--answer", "A")
    rc, payload, _ = run_json(capsys, db, "export", "--format", "csv")
    assert rc == 0
    assert payload["count"] == 1
    assert payload["format"] == "csv"
    assert payload["items"][0]["subject"] == "英语"
