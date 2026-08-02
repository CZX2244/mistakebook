# mistakebook · 错题本

> 一个零依赖的间隔重复错题本——给学生用，也给 AI agent 用。

把做错的题记下来，按 **1 → 3 → 7 → 14 → 30 天**的节奏自动安排复习。
答对晋级，答错归零重来。SQLite 存储，纯标准库实现，一条命令就能跑。

**Features**

- 📝 **录入**：题干 / 正确答案 / 你的作答 / 错因分析 / 知识点标签
- 🔁 **间隔重复**：1/3/7/14/30 天五阶段，掌握度 0-5 自动追踪
- 🔍 **检索**：按学科、错因、知识点、关键词任意组合
- 📊 **统计**：按学科 / 错因 / 掌握度分布，一眼看清薄弱点
- 📤 **导出**：CSV / JSON，随时带走你的数据
- 🤖 **Agent 友好**：每个命令都有 `--json` 输出，零解析成本
- 🪶 **零依赖**：只用 Python 标准库，`pip install` 之后就能用

## 安装

```bash
pip install mistakebook
# 或者从源码
pip install git+https://github.com/CZX2244/mistakebook.git
```

要求 Python ≥ 3.9，无其他依赖。

## 快速开始

```bash
# 录入一道错题
mistakebook add --subject 数学 \
  --question "若a+b=5，ab=3，求a²+b²" \
  --answer "a²+b²=(a+b)²-2ab=25-6=19" \
  --student-answer "25" \
  --cause 概念不清 \
  --problem-type 计算题 \
  --knowledge-points "代数,完全平方公式" \
  --analysis "忘记减去2ab项"

# 今天该复习什么？
mistakebook due

# 复习完记录结果：correct / partial / wrong
mistakebook review 1 --result wrong --notes "又忘了-2ab"

# 检索
mistakebook search --subject 数学 --cause 概念不清
mistakebook search --query "浮力"

# 详情与复习历史
mistakebook show 1

# 统计
mistakebook stats

# 导出
mistakebook export --format csv --output mistakes.csv
mistakebook export --format json --output mistakes.json
```

## 复习算法

| 阶段 | 0 | 1 | 2 | 3 | 4 | 5 |
|------|---|---|---|---|---|---|
| 间隔 | 1 天 | 3 天 | 7 天 | 14 天 | 30 天 | 30 天循环 |

- `correct` → 晋级下一阶段
- `partial` → 停留当前阶段
- `wrong` → 回到第 0 阶段，明天重来

掌握度（0-5）与阶段一一对应。错因分类：`概念不清 / 方法选择 / 计算失误 / 审题失误 / 表达不规范 / 知识遗忘 / 其他`。

## 给 AI agent 用

所有命令支持 `--json`，输出完整结构化数据，天然适配 agent 工具调用：

```bash
mistakebook --json due
mistakebook --json add --subject 物理 --question "..." --answer "..."
```

仓库自带 `SKILL.md`——如果你的 agent 支持 skill 系统（如 Hermes Agent），
把这个文件放进 skills 目录，agent 就能自己学会管理你的错题本。

数据库默认存在 `~/.mistakebook/mistakebook.db`，可用 `--db` 或
环境变量 `MISTAKEBOOK_DB` 指定其他位置。

## 开发

```bash
git clone https://github.com/CZX2244/mistakebook.git
cd mistakebook
pip install -e ".[dev]"
pytest
```

## License

MIT
