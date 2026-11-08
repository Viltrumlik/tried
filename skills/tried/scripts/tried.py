#!/usr/bin/env python3
"""tried - a log of what was already attempted, so nobody tries it twice.

You spend an hour finding out that an approach does not work. The session
ends. Tomorrow the agent tries the same thing again, because the reason it
failed lived only in a conversation that is gone.

`tried` keeps that reason in the repository, next to the code, where the
next session and the next person both find it.

    tried add "sqlite WAL for the queue" --failed --because "writers lock"
    tried check sqlite          # exit 3 if this ground was covered before
    tried list

State lives in .tried.jsonl at the repo root and is meant to be committed:
it is knowledge about the project, not a cache.

Zero dependencies. Python 3.9+. macOS, Linux and Windows.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid

VERSION = "0.1.0"
STORE = ".tried.jsonl"
EXIT_OK, EXIT_ERROR, EXIT_USAGE, EXIT_FOUND = 0, 1, 2, 3

OUTCOMES = ("failed", "worked", "partial")

# Bu so'zlar deyarli har bir yozuvda uchraydi, shuning uchun mos kelish
# uchun hisobga olinmaydi -- aks holda "the" bilan hamma narsa topiladi.
STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "when",
    "was", "were", "are", "but", "not", "you", "our", "its", "it's",
    "use", "used", "using", "try", "tried", "trying", "make", "made",
    "all", "any", "can", "did", "does", "has", "have", "how", "why",
}


class UsageError(Exception):
    pass


# ---------------------------------------------------------------- storage


def repo_root(start=None):
    """Repo ildizi, yoki git bo'lmasa joriy papka.

    Jurnal repoda yashashi kerak: u loyiha haqidagi bilim va u bilan birga
    ko'chib yurishi lozim.
    """
    start = os.path.abspath(start or os.getcwd())
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                             cwd=start, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, universal_newlines=True)
        if out.returncode == 0 and out.stdout.strip():
            return os.path.realpath(out.stdout.strip())
    except OSError:
        pass
    return start


def store_path(root=None):
    override = os.environ.get("TRIED_FILE")
    if override:
        return os.path.abspath(override)
    return os.path.join(repo_root(root), STORE)


def load(path=None):
    """Yozuvlarni o'qiydi. Buzuq qator butun jurnalni yo'q qilmaydi."""
    path = path or store_path()
    entries = []
    if not os.path.exists(path):
        return entries
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue  # qo'lda tahrirlangan bo'lishi mumkin; qolganini o'qiymiz
            if isinstance(entry, dict) and entry.get("what"):
                entries.append(entry)
    return entries


def append(entry, path=None):
    """Faylga qo'shadi. Qo'shish -- git uchun eng toza amal: ikki kishi bir
    vaqtda yozsa, to'qnashuv oxirgi qatorlarda bo'ladi va ikkalasi ham
    saqlanadi."""
    path = path or store_path()
    directory = os.path.dirname(path)
    if directory and not os.path.isdir(directory):
        os.makedirs(directory, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n")


def rewrite(entries, path=None):
    path = path or store_path()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


# ---------------------------------------------------------------- matching


def normalize(text):
    return re.sub(r"[^a-z0-9\s]+", " ", (text or "").casefold())


def words(text):
    """Mos kelishda hisobga olinadigan so'zlar."""
    return {w for w in normalize(text).split() if len(w) >= 3 and w not in STOPWORDS}


def haystack(entry):
    return " ".join(filter(None, [
        entry.get("what", ""), entry.get("because", ""),
        " ".join(entry.get("tags") or []),
    ]))


def relevance(query, entry):
    """0.0 dan 1.0 gacha. So'rovdagi so'zlarning nechtasi yozuvda uchraydi.

    Ataylab sodda va bashorat qilsa bo'ladigan: agent natijani tushunishi
    va unga ishonishi kerak, sehrli reyting emas.
    """
    q = words(query)
    if not q:
        return 0.0
    found = q & words(haystack(entry))
    return len(found) / float(len(q))


def newest_first(entries):
    """Eng yangisi birinchi.

    `at` soniyada saqlanadi, ya'ni bir soniyada qo'shilgan ikki yozuv teng
    chiqadi. Fayl faqat qo'shib boriladi, shuning uchun fayldagi o'rin
    vaqt tartibini aniq bildiradi -- teng holatni o'sha hal qiladi.
    """
    ordered = sorted(enumerate(entries),
                     key=lambda pair: (-pair[1].get("at", 0), -pair[0]))
    return [entry for _, entry in ordered]


def search(entries, query, threshold=0.5):
    scored = [(relevance(query, e), i, e) for i, e in enumerate(entries)]
    scored = [(s, i, e) for s, i, e in scored if s >= threshold]
    scored.sort(key=lambda t: (-t[0], -t[2].get("at", 0), -t[1]))
    return [(s, e) for s, _, e in scored]


# ---------------------------------------------------------------- display


def ago(seconds):
    seconds = max(0, int(seconds))
    for size, name in ((86400, "d"), (3600, "h"), (60, "m")):
        if seconds >= size:
            return "%d%s" % (seconds // size, name)
    return "%ds" % seconds


MARK = {"failed": "x", "worked": "v", "partial": "~"}


def describe(entry, now=None):
    now = time.time() if now is None else now
    line = "%s %s  %s" % (MARK.get(entry.get("outcome"), "?"),
                          entry.get("id", "")[:8], entry.get("what", ""))
    if entry.get("because"):
        line += "\n     because: %s" % entry["because"]
    meta = [ago(now - entry.get("at", now)) + " ago"]
    if entry.get("who"):
        meta.append(entry["who"])
    if entry.get("tags"):
        meta.append(" ".join("#" + t for t in entry["tags"]))
    return line + "\n     " + " · ".join(meta)


def emit_json(obj):
    print(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False))


def who():
    try:
        out = subprocess.run(["git", "config", "user.name"],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             universal_newlines=True)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()[:40]
    except OSError:
        pass
    return (os.environ.get("USER") or os.environ.get("USERNAME") or "")[:40]


# ---------------------------------------------------------------- commands


def cmd_add(args):
    what = " ".join(args.what).strip()
    if not what:
        raise UsageError("say what you tried")
    outcome = "failed"
    if args.worked:
        outcome = "worked"
    elif args.partial:
        outcome = "partial"
    entry = {
        "id": uuid.uuid4().hex[:8],
        "what": what[:300],
        "outcome": outcome,
        "because": (args.because or "").strip()[:500],
        "tags": sorted({t.strip().casefold()[:30] for t in (args.tag or []) if t.strip()}),
        "who": who(),
        "at": int(time.time()),
    }
    append(entry)
    if args.json:
        emit_json({"ok": True, "entry": entry})
    else:
        print("recorded: %s (%s)" % (entry["id"], outcome))
        if not entry["because"]:
            print("tip: add --because, or next time nobody will know why it failed")
    return EXIT_OK


def cmd_check(args):
    query = " ".join(args.query).strip()
    if not query:
        raise UsageError("check what?")
    hits = search(load(), query, args.threshold)
    if args.json:
        emit_json({"ok": True, "found": bool(hits), "query": query,
                   "matches": [dict(e, score=round(s, 2)) for s, e in hits]})
    elif hits:
        print("THIS WAS ALREADY TRIED:")
        for _, entry in hits[:5]:
            print("  " + describe(entry).replace("\n", "\n  "))
        print("Read the entry first. Pick a different approach, or say why this "
              "time is different.")
    else:
        print("clear: nothing on record for %s" % query)
    return EXIT_FOUND if hits else EXIT_OK


def cmd_list(args):
    entries = load()
    if args.failed:
        entries = [e for e in entries if e.get("outcome") == "failed"]
    elif args.worked:
        entries = [e for e in entries if e.get("outcome") == "worked"]
    entries = newest_first(entries)[:args.n]
    if args.json:
        emit_json({"ok": True, "entries": entries})
    elif not entries:
        print("the log is empty. Add the first entry with `tried add`.")
    else:
        for entry in entries:
            print(describe(entry))
            print()
    return EXIT_OK


def cmd_show(args):
    for entry in load():
        if entry.get("id", "").startswith(args.id):
            emit_json(entry) if args.json else print(describe(entry))
            return EXIT_OK
    raise UsageError("no such entry: %s" % args.id)


def cmd_rm(args):
    entries = load()
    keep = [e for e in entries if not e.get("id", "").startswith(args.id)]
    if len(keep) == len(entries):
        raise UsageError("bunday yozuv yo'q: %s" % args.id)
    rewrite(keep)
    if args.json:
        emit_json({"ok": True, "removed": len(entries) - len(keep)})
    else:
        print("removed: %s" % args.id)
    return EXIT_OK


# ---------------------------------------------------------------- cli


def build_parser():
    p = argparse.ArgumentParser(
        prog="tried",
        description="A log of approaches already attempted, so nobody tries them twice.")
    p.add_argument("--version", action="version", version="tried " + VERSION)
    sub = p.add_subparsers(dest="command")

    def add(name, help_text, func):
        sp = sub.add_parser(name, help=help_text, description=help_text)
        sp.add_argument("--json", action="store_true", help="machine-readable output")
        sp.set_defaults(func=func)
        return sp

    sp = add("add", "record an attempt", cmd_add)
    sp.add_argument("what", nargs="+", metavar="TEXT")
    sp.add_argument("--because", metavar="REASON", help="why it ended that way")
    sp.add_argument("--tag", action="append", metavar="TAG")
    g = sp.add_mutually_exclusive_group()
    g.add_argument("--failed", action="store_true", help="it did not work (default)")
    g.add_argument("--worked", action="store_true", help="it worked")
    g.add_argument("--partial", action="store_true", help="it partly worked")

    sp = add("check", "before you try: has this been tried already?", cmd_check)
    sp.add_argument("query", nargs="+", metavar="TEXT")
    sp.add_argument("--threshold", type=float, default=0.5,
                    help="match threshold, 0..1 (default 0.5)")

    sp = add("list", "recent entries", cmd_list)
    sp.add_argument("-n", type=int, default=10, help="how many (default 10)")
    g = sp.add_mutually_exclusive_group()
    g.add_argument("--failed", action="store_true")
    g.add_argument("--worked", action="store_true")

    sp = add("show", "one entry in full", cmd_show)
    sp.add_argument("id", metavar="ID")

    sp = add("rm", "remove a mistake", cmd_rm)
    sp.add_argument("id", metavar="ID")
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return EXIT_USAGE
    try:
        return args.func(args)
    except UsageError as e:
        if getattr(args, "json", False):
            emit_json({"ok": False, "error": str(e)})
        print("error: %s" % e, file=sys.stderr)
        return EXIT_USAGE
    except OSError as e:
        if getattr(args, "json", False):
            emit_json({"ok": False, "error": str(e)})
        print("error: %s" % e, file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
