"""SessionStart hook tests, driven the way Claude Code drives it."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, os.pardir, "skills", "tried", "scripts")
TRIED = os.path.join(SCRIPTS, "tried.py")
HOOK = os.path.join(SCRIPTS, "tried_hook.py")


class HookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="tried-hook-"))
        self.store = os.path.join(self.tmp, ".tried.jsonl")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def env(self, extra=None):
        e = dict(os.environ)
        e["TRIED_FILE"] = self.store
        for key in ("TRIED_HOOK_DISABLE", "TRIED_HOOK_LIMIT"):
            e.pop(key, None)
        e.update(extra or {})
        return e

    def add(self, *args):
        subprocess.run([sys.executable, TRIED, "add", *args], cwd=self.tmp,
                       check=True, capture_output=True, env=self.env())

    def hook(self, payload=None, env=None, raw=None):
        return subprocess.run([sys.executable, HOOK], cwd=self.tmp,
                              input=json.dumps(payload) if raw is None else raw,
                              capture_output=True, text=True, env=self.env(env))

    def payload(self):
        return {"session_id": "abc123", "cwd": self.tmp,
                "hook_event_name": "SessionStart", "source": "startup"}

    def context(self, done):
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)["hookSpecificOutput"]["additionalContext"]

    # -- foydali bo'lganda gapiradi ---------------------------------------

    def test_recent_dead_ends_reach_the_session(self):
        self.add("sqlite WAL for the queue", "--because", "writers lock")
        text = self.context(self.hook(self.payload()))
        self.assertIn("sqlite WAL for the queue", text)
        self.assertIn("writers lock", text)
        self.assertIn("tried check", text)

    def test_the_output_names_the_right_hook_event(self):
        self.add("something")
        out = json.loads(self.hook(self.payload()).stdout)["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "SessionStart")

    def test_only_the_dead_ends_are_surfaced(self):
        self.add("redis streams", "--worked")
        self.add("sqlite WAL", "--failed")
        text = self.context(self.hook(self.payload()))
        self.assertIn("sqlite WAL", text)
        self.assertNotIn("redis streams", text)

    def test_the_number_shown_is_capped(self):
        for i in range(8):
            self.add("approach number %d" % i)
        text = self.context(self.hook(self.payload(), env={"TRIED_HOOK_LIMIT": "3"}))
        self.assertEqual(text.count("approach number"), 3)

    # -- aks holda jim turadi ---------------------------------------------

    def test_an_empty_log_says_nothing(self):
        done = self.hook(self.payload())
        self.assertEqual(done.returncode, 0)
        self.assertEqual(done.stdout.strip(), "")

    def test_a_broken_payload_says_nothing(self):
        for raw in ("not json", "", "[1,2,3]"):
            done = self.hook(None, raw=raw)
            self.assertEqual(done.returncode, 0)
            self.assertEqual(done.stdout.strip(), "")

    def test_it_can_be_switched_off(self):
        self.add("sqlite WAL")
        done = self.hook(self.payload(), env={"TRIED_HOOK_DISABLE": "1"})
        self.assertEqual(done.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
