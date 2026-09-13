"""Command-line interface for mistakebook.

Usage:
    mistakebook add --subject 数学 --question "..." --answer "..." [options]
    mistakebook due [--subject 数学] [--limit 20]
    mistakebook review <id> --result correct|partial|wrong [--notes "..."]
    mistakebook search [--query "..."] [--subject "..."] [--cause "..."]
    mistakebook show <id>
    mistakebook update <id> [fields]
    mistakebook archive <id> [--unarchive]
    mistakebook stats
    mistakebook export [--format csv|json] [--output path]

Database location: --db PATH, $MISTAKEBOOK_DB, or ~/.mistakebook/mistakebook.db
All commands accept --json for machine-readable output (agent-friendly).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .core import ERROR_CAUSES, Mistake, MistakeBook

DEFAULT_DB = Path.home() / ".mistakebook" / "mistakebook.db"
CSV_FIELDS = [
    "id", "subject", "question_text", "correct_answer", "student_answer",
    "analysis", "error_cause", "problem_type", "knowledge_points",
    "page_location", "source_image", "mastery", "stage", "next_review",
    "archived", "created_at", "updated_at",
]


def resolve_db(args) -> Path:
    if getattr(args, "db", None):
        return Path(args.db)
    env = os.environ.get("MISTAKEBOOK_DB")
    return Path(env) if env else DEFAULT_DB


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mistake):
        return mistake_to_dict(value)
    raise TypeError(f"not serializable: {type(value)}")


def _print_json(payload, *, file=None) -> None:
    print(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default),
        file=file or sys.stdout,
    )


def emit(args, payload) -> None:
    """Emit a successful payload in JSON or human-readable form."""
    if getattr(args, "json_out", False):
        _print_json(payload)
    else:
        args.human(payload)


def fail(args, code: str, message: str, **details) -> int:
    """Emit a stable machine-readable error when --json is active."""
    if getattr(args, "json_out", False):
        error = {"code": code, "message": message}
        error.update(details)
        _print_json({"error": error}, file=sys.stderr)
    else:
        print(f"❌ {message}", file=sys.stderr)
    return 1


def mistake_to_dict(m: Mistake) -> dict:
    d = asdict(m)
    d["next_review"] = m.next_review.isoformat() if m.next_review else None
    d["created_at"] = m.created_at.isoformat() if m.created_at else None
    d["updated_at"] = m.updated_at.isoformat() if m.updated_at else None
    return d


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("必须是正整数")
    return parsed


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("不能是负数")
    return parsed


# ------------------------------------------------------------- human printers
def human_mistake_brief(mistakes) -> None:
    if not mistakes:
        print("（没有匹配的错题）")
        return
    for m in mistakes:
        due = m.next_review.strftime("%Y-%m-%d") if m.next_review else "-"
        kps = "/".join(m.knowledge_points) if m.knowledge_points else "-"
        q = m.question_text.replace("\n", " ")
        if len(q) > 50:
            q = q[:50] + "…"
        print(f"[{m.id}] {m.subject} | 掌握度 {m.mastery}/5 | 复习日 {due}")
        print(f"    {q}")
        print(f"    知识点: {kps} | 错因: {m.error_cause or '-'}")


def human_mistake_detail(m: Mistake) -> None:
    if m is None:
        print("（找不到这条错题）")
        return
    print(f"#{m.id} [{m.subject}] {m.problem_type}")
    print(f"题干: {m.question_text}")
    print(f"你的作答: {m.student_answer or '（空）'}")
    print(f"正确答案: {m.correct_answer}")
    print(f"分析: {m.analysis or '（空）'}")
    print(f"错因: {m.error_cause or '-'} | 知识点: {', '.join(m.knowledge_points) or '-'}")
    print(f"掌握度: {m.mastery}/5 | 阶段: {m.stage} | "
          f"下次复习: {m.next_review.strftime('%Y-%m-%d') if m.next_review else '-'}")
    print(f"状态: {'已归档' if m.archived else '在册'}")


def human_stats(s: dict) -> None:
    print(f"在册错题: {s['total']}（已归档 {s['archived']}）")
    print(f"到期待复习: {s['due']}")
    print(f"累计复习次数: {s['total_reviews']}")
    if s["by_subject"]:
        print("按学科: " + ", ".join(f"{k} {v}" for k, v in s["by_subject"].items()))
    if s["by_error_cause"]:
        print("按错因: " + ", ".join(f"{k} {v}" for k, v in s["by_error_cause"].items()))
    if s["by_mastery"]:
        print("掌握度分布: " + ", ".join(
            f"{k}星×{v}" for k, v in sorted(s["by_mastery"].items())))
    if s["last_30d_reviews"]:
        print("近30天复习: " + ", ".join(
            f"{k}×{v}" for k, v in s["last_30d_reviews"].items()))


# ------------------------------------------------------------- subcommands
def cmd_add(args) -> int:
    kp = [k.strip() for k in (args.knowledge_points or "").split(",") if k.strip()]
    m = Mistake(
        subject=args.subject,
        question_text=args.question,
        correct_answer=args.answer,
        student_answer=args.student_answer or "",
        analysis=args.analysis or "",
        error_cause=args.cause or "",
        problem_type=args.problem_type or "",
        knowledge_points=kp,
        page_location=args.page or "",
        source_image=args.image or "",
    )
    with MistakeBook(resolve_db(args)) as book:
        mid = book.add(m)
        saved = book.get(mid)
    if args.json_out:
        _print_json({"id": mid, "mistake": mistake_to_dict(saved)})
    else:
        human_mistake_detail(saved)
        print(f"\n✅ 已录入 #{mid}，首次复习安排在明天。")
    return 0


def cmd_due(args) -> int:
    with MistakeBook(resolve_db(args)) as book:
        items = book.due(subject=args.subject, limit=args.limit)
        emit(args, [mistake_to_dict(m) for m in items] if args.json_out else items)
    return 0


def cmd_review(args) -> int:
    with MistakeBook(resolve_db(args)) as book:
        updated = book.review(
            args.id, result=args.result,
            notes=args.notes or "", duration_seconds=args.duration,
        )
    if updated is None:
        return fail(args, "not_found", f"找不到 #{args.id}", id=args.id)
    emit(args, mistake_to_dict(updated) if args.json_out else updated)
    return 0


def cmd_search(args) -> int:
    with MistakeBook(resolve_db(args)) as book:
        items = book.search(
            query=args.query, subject=args.subject,
            error_cause=args.cause, knowledge_point=args.knowledge_point,
            problem_type=args.problem_type,
            include_archived=args.all, limit=args.limit,
        )
        emit(args, [mistake_to_dict(m) for m in items] if args.json_out else items)
    return 0


def cmd_show(args) -> int:
    with MistakeBook(resolve_db(args)) as book:
        m = book.get(args.id)
        if m is None:
            return fail(args, "not_found", f"找不到 #{args.id}", id=args.id)
        reviews = book.reviews_for(args.id)
    if args.json_out:
        payload = mistake_to_dict(m)
        payload["reviews"] = reviews
        _print_json(payload)
    else:
        human_mistake_detail(m)
        if reviews:
            print(f"\n复习记录（{len(reviews)} 次）:")
            for r in reviews:
                print(f"  {r['reviewed_at'][:10]} {r['result']}"
                      f" → 阶段 {r['stage_after']}"
                      + (f" | {r['notes']}" if r["notes"] else ""))
    return 0


def cmd_archive(args) -> int:
    archived = not args.unarchive
    with MistakeBook(resolve_db(args)) as book:
        ok = book.archive(args.id, archived=archived)
        if not ok:
            return fail(args, "not_found", f"找不到 #{args.id}", id=args.id)
        updated = book.get(args.id)
    if args.json_out:
        _print_json({
            "id": args.id,
            "archived": archived,
            "mistake": mistake_to_dict(updated),
        })
    else:
        print(f"✅ #{args.id} {'已归档' if archived else '已恢复'}")
    return 0


def cmd_update(args) -> int:
    fields = {}
    for attr, key in [
        ("subject", "subject"), ("question", "question_text"),
        ("answer", "correct_answer"), ("student_answer", "student_answer"),
        ("analysis", "analysis"), ("cause", "error_cause"),
        ("problem_type", "problem_type"), ("page", "page_location"),
        ("image", "source_image"),
    ]:
        value = getattr(args, attr, None)
        if value is not None:
            fields[key] = value
    if args.knowledge_points is not None:
        fields["knowledge_points"] = [
            k.strip() for k in args.knowledge_points.split(",") if k.strip()]
    if not fields:
        return fail(args, "invalid_input", "没有要更新的字段")

    with MistakeBook(resolve_db(args)) as book:
        ok = book.update(args.id, **fields)
        if not ok:
            return fail(args, "not_found", f"找不到 #{args.id}", id=args.id)
        updated = book.get(args.id)
    if args.json_out:
        _print_json({
            "id": args.id,
            "updated": True,
            "mistake": mistake_to_dict(updated),
        })
    else:
        print(f"✅ #{args.id} 已更新")
    return 0


def cmd_stats(args) -> int:
    with MistakeBook(resolve_db(args)) as book:
        s = book.stats()
        emit(args, s)
    return 0


def _write_csv(rows: list[dict], fh) -> None:
    writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for row in rows:
        item = dict(row)
        item["knowledge_points"] = ";".join(item["knowledge_points"])
        writer.writerow({key: item.get(key) for key in CSV_FIELDS})


def cmd_export(args) -> int:
    out = Path(args.output) if args.output else None
    with MistakeBook(resolve_db(args)) as book:
        rows = [mistake_to_dict(m) for m in book.iter_all(include_archived=True)]

    if out:
        try:
            if args.format == "json":
                out.write_text(
                    json.dumps(rows, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            else:
                with out.open("w", newline="", encoding="utf-8-sig") as fh:
                    _write_csv(rows, fh)
        except OSError as exc:
            return fail(
                args,
                "export_failed",
                f"导出失败: {exc}",
                output=str(out),
            )

        if args.json_out:
            _print_json({
                "count": len(rows),
                "format": args.format,
                "output": str(out),
            })
        else:
            print(f"✅ 已导出 {len(rows)} 条到 {out}")
        return 0

    if args.json_out:
        _print_json({"count": len(rows), "format": args.format, "items": rows})
    elif args.format == "json":
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        _write_csv(rows, sys.stdout)
    return 0


# ------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mistakebook",
        description="间隔重复错题本（spaced-repetition mistake notebook）",
    )
    p.add_argument("--db", help="数据库路径（默认 ~/.mistakebook/mistakebook.db）")
    p.add_argument("--json", dest="json_out", action="store_true",
                   help="以 JSON 输出（适合 agent 调用）")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("add", help="录入一道错题")
    sp.add_argument("--subject", required=True, help="学科，如 数学")
    sp.add_argument("--question", required=True, help="完整题干")
    sp.add_argument("--answer", required=True, help="正确答案（含必要步骤）")
    sp.add_argument("--student-answer", help="学生作答")
    sp.add_argument("--analysis", help="错因分析与纠正方法")
    sp.add_argument("--cause", choices=ERROR_CAUSES, help="主错因")
    sp.add_argument("--problem-type", help="题型，如 计算题")
    sp.add_argument("--knowledge-points", help="知识点，逗号分隔，由宽到窄")
    sp.add_argument("--page", help="题号或页码位置")
    sp.add_argument("--image", help="原图路径")
    sp.set_defaults(func=cmd_add, human=human_mistake_detail)

    sp = sub.add_parser("due", help="列出到期待复习的错题")
    sp.add_argument("--subject")
    sp.add_argument("--limit", type=_positive_int, default=20)
    sp.set_defaults(func=cmd_due, human=human_mistake_brief)

    sp = sub.add_parser("review", help="记录一次复习结果")
    sp.add_argument("id", type=int)
    sp.add_argument("--result", required=True,
                    choices=["correct", "partial", "wrong"])
    sp.add_argument("--notes")
    sp.add_argument("--duration", type=_non_negative_int, help="用时（秒）")
    sp.set_defaults(func=cmd_review, human=human_mistake_detail)

    sp = sub.add_parser("search", help="检索错题")
    sp.add_argument("--query")
    sp.add_argument("--subject")
    sp.add_argument("--cause", choices=ERROR_CAUSES)
    sp.add_argument("--knowledge-point")
    sp.add_argument("--problem-type")
    sp.add_argument("--all", action="store_true", help="包含已归档")
    sp.add_argument("--limit", type=_positive_int, default=50)
    sp.set_defaults(func=cmd_search, human=human_mistake_brief)

    sp = sub.add_parser("show", help="查看一条错题详情和复习历史")
    sp.add_argument("id", type=int)
    sp.set_defaults(func=cmd_show)

    sp = sub.add_parser("update", help="修改一条错题")
    sp.add_argument("id", type=int)
    sp.add_argument("--subject")
    sp.add_argument("--question")
    sp.add_argument("--answer")
    sp.add_argument("--student-answer")
    sp.add_argument("--analysis")
    sp.add_argument("--cause", choices=ERROR_CAUSES)
    sp.add_argument("--problem-type")
    sp.add_argument("--knowledge-points")
    sp.add_argument("--page")
    sp.add_argument("--image")
    sp.set_defaults(func=cmd_update)

    sp = sub.add_parser("archive", help="归档（或恢复）一条错题")
    sp.add_argument("id", type=int)
    sp.add_argument("--unarchive", action="store_true")
    sp.set_defaults(func=cmd_archive)

    sp = sub.add_parser("stats", help="统计概览")
    sp.set_defaults(func=cmd_stats, human=human_stats)

    sp = sub.add_parser("export", help="导出全部错题")
    sp.add_argument("--format", choices=["csv", "json"], default="csv")
    sp.add_argument("--output", help="输出文件（默认打印到 stdout）")
    sp.set_defaults(func=cmd_export)

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
