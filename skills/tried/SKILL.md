---
name: tried
description: Use before starting a non-trivial approach, and whenever one fails. Keeps a log of what was already attempted in this repo and why it did not work, so a later session does not burn an hour rediscovering it.
---

# tried

An approach that failed is knowledge. It usually dies when the session ends,
and the next session repeats the work. `tried` keeps it in the repository.

The log lives in `.tried.jsonl` at the repo root and is committed.

## Before you start a non-trivial approach

```bash
tried check "sqlite WAL for the job queue"
```

- exit `0` — nothing on record, go ahead
- exit `3` — this ground was covered. **Read the entries before continuing.**

If it was tried and failed, do not repeat it silently. Either pick a
different approach, or say plainly why this time is different — a new
version, a changed constraint, a different part of the system.

Check once per approach, not once per file. A rewrite of the queue is one
check; the twelve files it touches are not twelve checks.

## When an approach fails

```bash
tried add "sqlite WAL for the job queue" --failed \
  --because "writers lock each other out above ~20 req/s" --tag queue
```

The `--because` is the whole point. "did not work" helps nobody; the reason
is what saves the next hour.

Record it when you abandon an approach, not when you finish the task. By
then the reason has already faded.

## When something works after several attempts

```bash
tried add "redis stream for the job queue" --worked --because "no writer contention"
```

Worth recording too: it tells the next session where the path out was.

## Reading the log

```bash
tried list            # the last 10, newest first
tried list --failed   # only the dead ends
tried show a1b2c3d4   # one entry in full
```

Every command takes `--json`.

## What not to record

- Ordinary bugs you fixed. This is for approaches considered and rejected.
- Anything secret. The file is committed and read by everyone.
- Your running commentary. One entry per real decision.
