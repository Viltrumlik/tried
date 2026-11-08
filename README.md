<h1 align="center">tried</h1>

<p align="center">
  <b>A log of what was already attempted in this repo, and why it didn't work.</b>
</p>

<p align="center">
  <a href="https://github.com/Viltrumlik/tried/actions/workflows/ci.yml"><img src="https://github.com/Viltrumlik/tried/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/tried/"><img src="https://img.shields.io/pypi/v/tried?color=3775a9&label=pypi" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/dependencies-0-brightgreen" alt="Zero dependencies">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT"></a>
</p>

You spend an hour discovering that an approach doesn't work. The session ends. Tomorrow the agent reaches for the same approach, because the reason it failed lived in a conversation that no longer exists.

**tried** keeps that reason in the repository, next to the code, where the next session and the next person both find it.

```bash
tried add "sqlite WAL for the job queue" --failed \
  --because "writers lock each other out above ~20 req/s" --tag queue

tried check "sqlite WAL"
# THIS WAS ALREADY TRIED: ...  → exit 3
```

`tried check` exits `3` when the ground was covered before, so an agent can branch on it and go a different way instead of repeating the work.

## Install

```bash
pipx install tried
```

As an [Agent Skill](https://agentskills.io), so agents use it on their own:

```bash
npx skills add Viltrumlik/tried
```

As a Claude Code plugin — this also installs a `SessionStart` hook that puts the recent dead ends in front of the agent before it starts:

```
/plugin marketplace add Viltrumlik/tried
/plugin install tried@tried
```

## Commands

| Command | What it does |
|---|---|
| `tried add TEXT --because WHY [--failed\|--worked\|--partial] [--tag T]` | Record an attempt |
| `tried check TEXT` | Exit `3` if this was tried before, `0` if clear |
| `tried list [-n 10] [--failed\|--worked]` | Recent entries, newest first |
| `tried show ID` | One entry in full |
| `tried rm ID` | Remove a mistake |

Every command takes `--json`.

Exit codes: `0` ok · `1` error · `2` usage error · `3` prior attempts found.

## Where it lives

`.tried.jsonl` at the repo root, and **it is meant to be committed**. This is knowledge about the project, not a cache — it should travel with the code and show up in review.

The file is append-only, which keeps git diffs clean: two people writing at once conflict only on the last lines, and the fix is to keep both.

Outside a git repo it falls back to the current folder. `TRIED_FILE` overrides the path.

## Why `--because` matters

"didn't work" helps nobody. The reason is the whole value:

```
x 4f2a1c8b  sqlite WAL for the job queue
     because: writers lock each other out above ~20 req/s
     3d ago · Alisher · #queue
```

A year later, that line is the difference between an hour lost and a minute saved.

## What not to record

- Ordinary bugs you fixed — this is for approaches considered and rejected
- Anything secret: the file is committed and everyone reads it
- Running commentary — one entry per real decision

## Development

```bash
python3 -m unittest discover -s tests -v
```

CI runs on Ubuntu, macOS and Windows with Python 3.9 through 3.13.

```
skills/tried/
├── SKILL.md              # what agents read
└── scripts/
    ├── tried.py          # the CLI: one file, zero dependencies
    └── tried_hook.py     # SessionStart hook
hooks/hooks.json          # registers the hook for the plugin
pyproject.toml            # the PyPI package
tests/                    # end-to-end tests against real files
```

## License

[MIT](LICENSE) © Alisher Muhammadaliyev ([@Viltrumlik](https://github.com/Viltrumlik))
