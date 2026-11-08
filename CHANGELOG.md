# Changelog

## 0.1.0 — 2026-11-08

First release.

- `tried` CLI: `add`, `check`, `list`, `show`, `rm`, all with `--json`.
- `tried check` exits `3` when an approach was attempted before, so agents and scripts can branch on it.
- Matching looks at the attempt, the reason and the tags; it reports the share of query words found, so the result is predictable rather than a hidden ranking.
- Entries are stored append-only in `.tried.jsonl` at the repo root, meant to be committed. A corrupt line never costs you the rest of the log.
- Ties on the same second are resolved by position in the file, which is chronological because the file is only ever appended to.
- Agent Skill (`SKILL.md`) and a Claude Code `SessionStart` hook that surfaces recent dead ends before work starts.
