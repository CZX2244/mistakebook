"""SQLite storage layer for mistakebook.

Two tables:
- mistakes: one row per mistake (the problem, the correct answer, classification)
- reviews: one row per review event (immutable log)

All datetimes are stored as ISO-8601 UTC strings.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from . import scheduler

SCHEMA = """
CREATE TABLE IF NOT EXISTS mistakes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,
    question_text TEXT NOT NULL,
    correct_answer TEXT NOT NULL,
    student_answer TEXT NOT NULL DEFAULT '',
    analysis TEXT NOT NULL DEFAULT '',
    error_cause TEXT NOT NULL DEFAULT '',
    problem_type TEXT NOT NULL DEFAULT '',
    knowledge_points TEXT NOT NULL DEFAULT '[]',
    page_location TEXT NOT NULL DEFAULT '',
    source_image TEXT NOT NULL DEFAULT '',
    stage INTEGER NOT NULL DEFAULT 0,
    mastery INTEGER NOT NULL DEFAULT 0,
    next_review TEXT NOT NULL,
    archived INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mistake_id INTEGER NOT NULL REFERENCES mistakes(id) ON DELETE CASCADE,
    result TEXT NOT NULL,
    stage_after INTEGER NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    duration_seconds INTEGER,
    reviewed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mistakes_next_review ON mistakes(next_review);
CREATE INDEX IF NOT EXISTS idx_mistakes_subject ON mistakes(subject);
CREATE INDEX IF NOT EXISTS idx_reviews_mistake_id ON reviews(mistake_id);
"""

ERROR_CAUSES = (
    "概念不清", "方法选择", "计算失误", "审题失误", "表达不规范", "知识遗忘", "其他",
)


@dataclass
class Mistake:
    subject: str
    question_text: str
    correct_answer: str
    student_answer: str = ""
    analysis: str = ""
    error_cause: str = ""
    problem_type: str = ""
    knowledge_points: list[str] = field(default_factory=list)
    page_location: str = ""
    source_image: str = ""
    id: Optional[int] = None
    stage: int = 0
    mastery: int = 0
    next_review: Optional[datetime] = None
    archived: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MistakeBook:
    """The notebook itself. Open with ``MistakeBook(path)`` or as a context manager."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path).expanduser()
        if self.db_path.parent and str(self.db_path.parent) != ".":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    # ------------------------------------------------------------------ utils
    def __enter__(self) -> "MistakeBook":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _now_iso() -> str:
        return scheduler.utc_now().isoformat()

    @staticmethod
    def _parse_dt(value: str) -> datetime:
        return datetime.fromisoformat(value)

    def _row_to_mistake(self, row: sqlite3.Row) -> Mistake:
        return Mistake(
            id=row["id"],
            subject=row["subject"],
            question_text=row["question_text"],
            correct_answer=row["correct_answer"],
            student_answer=row["student_answer"],
            analysis=row["analysis"],
            error_cause=row["error_cause"],
            problem_type=row["problem_type"],
            knowledge_points=json.loads(row["knowledge_points"]),
            page_location=row["page_location"],
            source_image=row["source_image"],
            stage=row["stage"],
            mastery=row["mastery"],
            next_review=self._parse_dt(row["next_review"]),
            archived=bool(row["archived"]),
            created_at=self._parse_dt(row["created_at"]),
            updated_at=self._parse_dt(row["updated_at"]),
        )

    def get(self, mistake_id: int) -> Optional[Mistake]:
        row = self._conn.execute(
            "SELECT * FROM mistakes WHERE id = ?", (mistake_id,)
        ).fetchone()
        return self._row_to_mistake(row) if row else None

    # ------------------------------------------------------------------ CRUD
    def add(self, mistake: Mistake) -> int:
        """Insert a new mistake; returns its id. First review is due in 1 day."""
        now = self._now_iso()
        next_review = scheduler.next_review_at(stage=0).isoformat()
        cur = self._conn.execute(
            """INSERT INTO mistakes
               (subject, question_text, correct_answer, student_answer, analysis,
                error_cause, problem_type, knowledge_points, page_location,
                source_image, stage, mastery, next_review, archived,
                created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,0,0,?,0,?,?)""",
            (
                mistake.subject, mistake.question_text, mistake.correct_answer,
                mistake.student_answer, mistake.analysis, mistake.error_cause,
                mistake.problem_type, json.dumps(mistake.knowledge_points, ensure_ascii=False),
                mistake.page_location, mistake.source_image, next_review, now, now,
            ),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def update(self, mistake_id: int, **fields) -> bool:
        """Update editable fields of a mistake. Returns False if not found."""
        allowed = {
            "subject", "question_text", "correct_answer", "student_answer",
            "analysis", "error_cause", "problem_type", "page_location",
            "source_image",
        }
        sets, values = [], []
        for key, value in fields.items():
            if key == "knowledge_points":
                sets.append("knowledge_points = ?")
                values.append(json.dumps(value, ensure_ascii=False))
            elif key in allowed:
                sets.append(f"{key} = ?")
                values.append(value)
        if not sets:
            return False
        sets.append("updated_at = ?")
        values.append(self._now_iso())
        values.append(mistake_id)
        cur = self._conn.execute(
            f"UPDATE mistakes SET {', '.join(sets)} WHERE id = ?", values
        )
        self._conn.commit()
        return cur.rowcount > 0

    def archive(self, mistake_id: int, archived: bool = True) -> bool:
        cur = self._conn.execute(
            "UPDATE mistakes SET archived = ?, updated_at = ? WHERE id = ?",
            (1 if archived else 0, self._now_iso(), mistake_id),
        )
        self._conn.commit()
        return cur.rowcount > 0

    # ------------------------------------------------------------------ review
    def review(
        self,
        mistake_id: int,
        result: str,
        notes: str = "",
        duration_seconds: Optional[int] = None,
    ) -> Optional[Mistake]:
        """Record a review outcome; returns the updated mistake (None if missing)."""
        m = self.get(mistake_id)
        if m is None:
            return None
        new_stage = scheduler.next_stage(m.stage, result)
        next_review = scheduler.next_review_at(new_stage)
        now = self._now_iso()
        with self._conn:
            self._conn.execute(
                """INSERT INTO reviews
                   (mistake_id, result, stage_after, notes, duration_seconds, reviewed_at)
                   VALUES (?,?,?,?,?,?)""",
                (mistake_id, result, new_stage, notes, duration_seconds, now),
            )
            self._conn.execute(
                """UPDATE mistakes
                   SET stage = ?, mastery = ?, next_review = ?, updated_at = ?
                   WHERE id = ?""",
                (new_stage, scheduler.mastery_from_stage(new_stage),
                 next_review.isoformat(), now, mistake_id),
            )
        return self.get(mistake_id)

    def reviews_for(self, mistake_id: int) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM reviews WHERE mistake_id = ? ORDER BY reviewed_at",
            (mistake_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ query
    def due(self, subject: Optional[str] = None, limit: int = 20) -> list[Mistake]:
        """Mistakes whose next_review is now or in the past (and not archived)."""
        now = self._now_iso()
        sql = ("SELECT * FROM mistakes WHERE archived = 0 AND next_review <= ?")
        params: list = [now]
        if subject:
            sql += " AND subject = ?"
            params.append(subject)
        sql += " ORDER BY next_review LIMIT ?"
        params.append(limit)
        return [self._row_to_mistake(r) for r in self._conn.execute(sql, params)]

    def search(
        self,
        query: Optional[str] = None,
        subject: Optional[str] = None,
        error_cause: Optional[str] = None,
        knowledge_point: Optional[str] = None,
        problem_type: Optional[str] = None,
        include_archived: bool = False,
        limit: int = 50,
    ) -> list[Mistake]:
        sql = "SELECT * FROM mistakes WHERE 1=1"
        params: list = []
        if not include_archived:
            sql += " AND archived = 0"
        if subject:
            sql += " AND subject = ?"
            params.append(subject)
        if error_cause:
            sql += " AND error_cause = ?"
            params.append(error_cause)
        if problem_type:
            sql += " AND problem_type = ?"
            params.append(problem_type)
        if knowledge_point:
            sql += " AND knowledge_points LIKE ?"
            params.append(f"%{knowledge_point}%")
        if query:
            sql += " AND (question_text LIKE ? OR analysis LIKE ? OR correct_answer LIKE ?)"
            like = f"%{query}%"
            params += [like, like, like]
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        return [self._row_to_mistake(r) for r in self._conn.execute(sql, params)]

    # ------------------------------------------------------------------ stats
    def stats(self) -> dict:
        c = self._conn
        total = c.execute("SELECT COUNT(*) FROM mistakes WHERE archived = 0").fetchone()[0]
        archived = c.execute("SELECT COUNT(*) FROM mistakes WHERE archived = 1").fetchone()[0]
        due = c.execute(
            "SELECT COUNT(*) FROM mistakes WHERE archived = 0 AND next_review <= ?",
            (self._now_iso(),),
        ).fetchone()[0]
        by_subject = {
            r["subject"]: r["n"]
            for r in c.execute(
                "SELECT subject, COUNT(*) AS n FROM mistakes WHERE archived = 0 "
                "GROUP BY subject ORDER BY n DESC"
            )
        }
        by_cause = {
            r["error_cause"]: r["n"]
            for r in c.execute(
                "SELECT error_cause, COUNT(*) AS n FROM mistakes "
                "WHERE archived = 0 AND error_cause != '' GROUP BY error_cause"
            )
        }
        mastery = {
            str(r["mastery"]): r["n"]
            for r in c.execute(
                "SELECT mastery, COUNT(*) AS n FROM mistakes WHERE archived = 0 "
                "GROUP BY mastery"
            )
        }
        total_reviews = c.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
        recent = c.execute(
            "SELECT result, COUNT(*) AS n FROM reviews "
            "WHERE reviewed_at >= datetime('now', '-30 days') GROUP BY result"
        ).fetchall()
        return {
            "total": total,
            "archived": archived,
            "due": due,
            "total_reviews": total_reviews,
            "by_subject": by_subject,
            "by_error_cause": by_cause,
            "by_mastery": mastery,
            "last_30d_reviews": {r["result"]: r["n"] for r in recent},
        }

    # ------------------------------------------------------------------ export
    def iter_all(self, include_archived: bool = True) -> Iterator[Mistake]:
        sql = "SELECT * FROM mistakes"
        if not include_archived:
            sql += " WHERE archived = 0"
        for row in self._conn.execute(sql):
            yield self._row_to_mistake(row)
