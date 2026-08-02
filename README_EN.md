# mistakebook

> A zero-dependency, spaced-repetition mistake notebook — for students, and for AI agents.

Record the problems you got wrong, and let the notebook schedule reviews at
**1 → 3 → 7 → 14 → 30 day** intervals. Answer correctly to advance; answer wrong
and the mistake comes back tomorrow. SQLite-backed, stdlib-only, one command to run.

**Features**

- 📝 **Capture**: question / correct answer / your attempt / analysis / knowledge-point tags
- 🔁 **Spaced repetition**: 5 stages (1/3/7/14/30 days), mastery 0-5 tracked automatically
- 🔍 **Search**: by subject, error cause, knowledge point, keyword — in any combination
- 📊 **Stats**: distribution by subject / error cause / mastery
- 📤 **Export**: CSV / JSON — your data, anytime
- 🤖 **Agent-friendly**: every command supports `--json` output
- 🪶 **Zero dependencies**: Python standard library only

## Install

```bash
pip install mistakebook
# or from source
pip install git+https://github.com/CZX2244/mistakebook.git
```

Requires Python ≥ 3.9. Nothing else.

## Quick start

```bash
# Add a mistake
mistakebook add --subject math \
  --question "If a+b=5 and ab=3, find a²+b²" \
  --answer "a²+b²=(a+b)²-2ab=25-6=19" \
  --student-answer "25" \
  --analysis "Forgot the -2ab term"

# What's due today?
mistakebook due

# Record a review: correct / partial / wrong
mistakebook review 1 --result wrong --notes "missed -2ab again"

# Search / detail / stats / export
mistakebook search --query "buoyancy"
mistakebook show 1
mistakebook stats
mistakebook export --format csv --output mistakes.csv
```

## Review algorithm

| Stage | 0 | 1 | 2 | 3 | 4 | 5 |
|-------|---|---|---|---|---|---|
| Interval | 1d | 3d | 7d | 14d | 30d | 30d loop |

- `correct` → advance one stage
- `partial` → stay
- `wrong` → back to stage 0

## For AI agents

Every command accepts `--json` and returns fully structured output. The repo
ships a `SKILL.md` — drop it into the skills directory of a skill-capable agent
(e.g. Hermes Agent) and the agent learns to manage the notebook for you.

Database defaults to `~/.mistakebook/mistakebook.db`; override with `--db` or
the `MISTAKEBOOK_DB` environment variable.

## Development

```bash
git clone https://github.com/CZX2244/mistakebook.git
cd mistakebook
pip install -e ".[dev]"
pytest
```

## License

MIT
