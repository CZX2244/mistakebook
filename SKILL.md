---
name: mistakebook
description: Manage the user's mistake notebook (错题本) — record wrong problems, schedule spaced-repetition reviews, search and analyze weaknesses. Use when the user shares a wrong homework/exam question, asks what to review today, or wants study stats.
---

# mistakebook · 错题本管理

通过 `mistakebook` CLI 管理用户的错题本（间隔重复，1/3/7/14/30 天）。

## 触发条件

- 用户发来做错的题目（作业、试卷照片或文字）
- 用户问"今天该复习什么"
- 用户想要学习统计 / 薄弱点分析
- 用户说"记一下这道错题"

## 数据库位置

默认 `~/.mistakebook/mistakebook.db`。可用 `--db PATH` 或 `$MISTAKEBOOK_DB` 覆盖。
不确定时先运行 `mistakebook stats` 确认数据库可访问。

## 核心命令

```bash
# 录入错题（--cause 只能是：概念不清/方法选择/计算失误/审题失误/表达不规范/知识遗忘/其他）
mistakebook --json add --subject 数学 --question "完整题干" \
  --answer "正确答案与步骤" --student-answer "学生的作答" \
  --cause 计算失误 --problem-type 计算题 \
  --knowledge-points "代数,完全平方公式" --analysis "错因分析与纠正方法"

# 到期待复习
mistakebook --json due [--subject 数学] [--limit 20]

# 记录复习结果（correct 晋级 / partial 停留 / wrong 归零）
mistakebook --json review <id> --result correct [--notes "..."] [--duration 秒]

# 检索
mistakebook --json search [--query 关键词] [--subject 学科] \
  [--cause 错因] [--knowledge-point 知识点] [--all]

# 详情（含全部复习历史）
mistakebook --json show <id>

# 统计
mistakebook --json stats

# 导出
mistakebook export --format json --output mistakes.json
```

所有命令带 `--json` 时输出结构化 JSON，直接解析，不要正则抓人类可读输出。

## 工作流

### 录入一道新错题

1. 从用户提供的题目中提取：学科、完整题干、正确答案（自己验算一遍！）、学生作答、错因、题型、知识点（1-5 个，由宽到窄）。
2. 正确答案**必须独立验算**后再录入，不要直接抄用户给的。
3. 录完把 `--json` 返回的 id 告诉用户，并说明首次复习在明天。

### 复习会话

1. `mistakebook --json due` 拿到到期列表。
2. 逐条提问：只展示题干，让用户作答，**不要先给答案**。
3. 对照 `correct_answer` 判断，调用 `review` 记录结果：
   - 完全答对 → `correct`
   - 思路对但有瑕疵/需要提示 → `partial`
   - 答错或不会 → `wrong`，讲清楚错在哪
4. 复习完用 `stats` 给个简短总结。

## 注意

- 录入前先 `search --query` 查重；同一道题再次做错时，用 `review <id> --result wrong` 追加记录，不要新建条目。
- 归档用 `archive <id>`（可 `--unarchive` 恢复），数据不会真正删除。
- 不要编造题干或答案。用户没给全就问。
