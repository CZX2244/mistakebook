"""Tests for the SQLite storage layer."""

from datetime import timedelta

import pytest

from mistakebook import scheduler
from mistakebook.core import Mistake, MistakeBook


@pytest.fixture
def book(tmp_path):
    with MistakeBook(tmp_path / "test.db") as b:
        yield b


def make_mistake(**overrides):
    base = dict(
        subject="数学",
        question_text="计算：(a+b)/(c+d)，a=1,b=2,c=3,d=4",
        correct_answer="3/7",
        student_answer="1/2",
        analysis="先算括号内再相除，不能拆开分别除",
        error_cause="概念不清",
        problem_type="计算题",
        knowledge_points=["有理数", "分数运算"],
        page_location="练习册 P23 第5题",
    )
    base.update(overrides)
    return Mistake(**base)


def test_add_and_get(book):
    mid = book.add(make_mistake())
    m = book.get(mid)
    assert m is not None
    assert m.id == mid
    assert m.subject == "数学"
    assert m.knowledge_points == ["有理数", "分数运算"]
    assert m.stage == 0 and m.mastery == 0
    assert not m.archived
    # 首次复习应在 ~1 天后
    assert m.next_review - scheduler.utc_now() < timedelta(days=1, minutes=1)


def test_update(book):
    mid = book.add(make_mistake())
    assert book.update(mid, analysis="改后的分析", knowledge_points=["代数"])
    m = book.get(mid)
    assert m.analysis == "改后的分析"
    assert m.knowledge_points == ["代数"]


def test_archive(book):
    mid = book.add(make_mistake())
    assert book.archive(mid)
    assert book.get(mid).archived
    # 归档后不出现在 due 里
    assert all(m.id != mid for m in book.due())
    assert book.archive(mid, archived=False)
    assert not book.get(mid).archived


def test_review_correct_advances_and_logs(book):
    mid = book.add(make_mistake())
    updated = book.review(mid, "correct", notes="这次对了")
    assert updated.stage == 1
    assert updated.mastery == 1
    reviews = book.reviews_for(mid)
    assert len(reviews) == 1
    assert reviews[0]["result"] == "correct"
    assert reviews[0]["stage_after"] == 1


def test_review_wrong_resets(book):
    mid = book.add(make_mistake())
    book.review(mid, "correct")
    book.review(mid, "correct")
    updated = book.review(mid, "wrong")
    assert updated.stage == 0
    assert updated.mastery == 0


def test_review_missing_returns_none(book):
    assert book.review(999, "correct") is None


def test_due_only_returns_overdue(book):
    mid = book.add(make_mistake())
    # 新录入的明天才到期
    assert all(m.id != mid for m in book.due())
    # 手动把 next_review 改成过去
    past = (scheduler.utc_now() - timedelta(days=1)).isoformat()
    book._conn.execute("UPDATE mistakes SET next_review = ? WHERE id = ?", (past, mid))
    book._conn.commit()
    assert any(m.id == mid for m in book.due())


def test_search(book):
    book.add(make_mistake())
    book.add(make_mistake(subject="物理", question_text="浮力公式是什么",
                          knowledge_points=["浮力", "压强"]))
    assert len(book.search(subject="数学")) == 1
    assert len(book.search(query="浮力")) == 1
    assert len(book.search(knowledge_point="分数")) == 1
    assert len(book.search(error_cause="概念不清")) == 2
    assert len(book.search()) == 2


def test_stats(book):
    book.add(make_mistake())
    mid = book.add(make_mistake(subject="物理"))
    book.review(mid, "correct")
    s = book.stats()
    assert s["total"] == 2
    assert s["total_reviews"] == 1
    assert s["by_subject"]["数学"] == 1
    assert s["by_subject"]["物理"] == 1
    assert s["by_error_cause"]["概念不清"] == 2
