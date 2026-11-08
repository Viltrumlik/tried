"""End-to-end tests: every test drives the real CLI against a real file."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, os.pardir, "skills", "tried", "scripts", "tried.py")

spec = importlib.util.spec_from_file_location("tried", SCRIPT)
tried = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tried)


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="tried-test-"))
        self.store = os.path.join(self.tmp, ".tried.jsonl")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_cli(self, *args, **kw):
        env = dict(os.environ)
        env["TRIED_FILE"] = kw.get("store", self.store)
        return subprocess.run([sys.executable, SCRIPT, *args], cwd=self.tmp,
                              capture_output=True, text=True, env=env)

    def entries(self):
        if not os.path.exists(self.store):
            return []
        with open(self.store, encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]

    # -- yozish ----------------------------------------------------------

    def test_add_records_a_failed_attempt_by_default(self):
        out = self.run_cli("add", "sqlite WAL for the queue",
                           "--because", "writers lock under load")
        self.assertEqual(out.returncode, 0, out.stderr)
        entry = self.entries()[0]
        self.assertEqual(entry["what"], "sqlite WAL for the queue")
        self.assertEqual(entry["outcome"], "failed")
        self.assertEqual(entry["because"], "writers lock under load")
        self.assertTrue(entry["id"] and entry["at"])

    def test_outcomes_can_be_stated(self):
        self.run_cli("add", "redis for the queue", "--worked")
        self.run_cli("add", "a thread pool", "--partial")
        self.assertEqual([e["outcome"] for e in self.entries()], ["worked", "partial"])

    def test_adding_nothing_is_a_usage_error(self):
        out = self.run_cli("add", "   ")
        self.assertEqual(out.returncode, 2)

    def test_a_missing_reason_is_nudged_but_allowed(self):
        out = self.run_cli("add", "some approach")
        self.assertEqual(out.returncode, 0)
        self.assertIn("--because", out.stdout)

    def test_tags_are_normalised_and_deduplicated(self):
        self.run_cli("add", "x", "--tag", "SQLite", "--tag", "sqlite", "--tag", " Queue ")
        self.assertEqual(self.entries()[0]["tags"], ["queue", "sqlite"])

    # -- tekshirish -------------------------------------------------------

    def test_check_finds_a_previous_attempt_and_exits_3(self):
        self.run_cli("add", "sqlite WAL for the queue", "--because", "writers lock")
        out = self.run_cli("check", "sqlite WAL")
        self.assertEqual(out.returncode, 3)
        self.assertIn("ALREADY TRIED", out.stdout)
        self.assertIn("writers lock", out.stdout)

    def test_check_on_clear_ground_exits_0(self):
        self.run_cli("add", "sqlite WAL for the queue")
        out = self.run_cli("check", "kubernetes ingress")
        self.assertEqual(out.returncode, 0)
        self.assertIn("clear", out.stdout)

    def test_check_matches_the_reason_too_not_only_the_title(self):
        self.run_cli("add", "the queue rewrite", "--because", "postgres advisory locks deadlock")
        self.assertEqual(self.run_cli("check", "advisory locks").returncode, 3)

    def test_check_matches_tags(self):
        self.run_cli("add", "some approach", "--tag", "websocket")
        self.assertEqual(self.run_cli("check", "websocket").returncode, 3)

    def test_an_empty_log_never_blocks(self):
        self.assertEqual(self.run_cli("check", "anything at all").returncode, 0)

    def test_the_threshold_can_be_loosened(self):
        self.run_cli("add", "sqlite WAL for the queue")
        strict = self.run_cli("check", "sqlite kubernetes helm istio")
        self.assertEqual(strict.returncode, 0)
        loose = self.run_cli("check", "sqlite kubernetes helm istio", "--threshold", "0.2")
        self.assertEqual(loose.returncode, 3)

    def test_check_without_words_is_a_usage_error(self):
        self.assertEqual(self.run_cli("check", "  ").returncode, 2)

    # -- o'qish -----------------------------------------------------------

    def test_list_is_newest_first_and_can_be_filtered(self):
        self.run_cli("add", "first thing", "--failed")
        self.run_cli("add", "second thing", "--worked")
        out = self.run_cli("list", "--json")
        got = json.loads(out.stdout)["entries"]
        self.assertEqual(got[0]["what"], "second thing")
        only = json.loads(self.run_cli("list", "--failed", "--json").stdout)["entries"]
        self.assertEqual([e["what"] for e in only], ["first thing"])

    def test_list_respects_n(self):
        for i in range(5):
            self.run_cli("add", "approach %d" % i)
        got = json.loads(self.run_cli("list", "-n", "2", "--json").stdout)["entries"]
        self.assertEqual(len(got), 2)

    def test_an_empty_log_says_so(self):
        self.assertIn("empty", self.run_cli("list").stdout)

    def test_show_and_rm_work_on_an_id_prefix(self):
        self.run_cli("add", "the one to remove")
        entry_id = self.entries()[0]["id"]
        self.assertIn("the one to remove", self.run_cli("show", entry_id[:4]).stdout)
        self.assertEqual(self.run_cli("rm", entry_id[:4]).returncode, 0)
        self.assertEqual(self.entries(), [])

    def test_show_and_rm_refuse_an_unknown_id(self):
        self.assertEqual(self.run_cli("show", "zzzzzzzz").returncode, 2)
        self.assertEqual(self.run_cli("rm", "zzzzzzzz").returncode, 2)

    # -- mustahkamlik ------------------------------------------------------

    def test_a_corrupt_line_does_not_lose_the_rest(self):
        self.run_cli("add", "good entry one")
        with open(self.store, "a", encoding="utf-8") as f:
            f.write("{ this is not json\n\n")
        self.run_cli("add", "good entry two")
        got = json.loads(self.run_cli("list", "--json").stdout)["entries"]
        self.assertEqual(len(got), 2)

    def test_json_errors_are_json(self):
        out = self.run_cli("show", "zzzzzzzz", "--json")
        self.assertFalse(json.loads(out.stdout)["ok"])

    def test_unicode_survives_the_round_trip(self):
        self.run_cli("add", "o'zbekcha yozuv", "--because", "sabab: ko'prik")
        self.assertIn("ko'prik", self.run_cli("list").stdout)


class StoreLocationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="tried-root-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_the_log_lands_at_the_repo_root_not_the_cwd(self):
        repo = os.path.join(self.tmp, "repo")
        deep = os.path.join(repo, "src", "pkg")
        os.makedirs(deep)
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True,
                       capture_output=True)
        env = dict(os.environ)
        env.pop("TRIED_FILE", None)
        subprocess.run([sys.executable, SCRIPT, "add", "from a subfolder"],
                       cwd=deep, check=True, capture_output=True, env=env)
        self.assertTrue(os.path.exists(os.path.join(repo, ".tried.jsonl")))
        self.assertFalse(os.path.exists(os.path.join(deep, ".tried.jsonl")))

    def test_outside_git_it_falls_back_to_the_current_folder(self):
        env = dict(os.environ)
        env.pop("TRIED_FILE", None)
        subprocess.run([sys.executable, SCRIPT, "add", "no git here"],
                       cwd=self.tmp, check=True, capture_output=True, env=env)
        self.assertTrue(os.path.exists(os.path.join(self.tmp, ".tried.jsonl")))


class UnitTest(unittest.TestCase):
    def test_relevance_is_the_share_of_query_words_found(self):
        entry = {"what": "sqlite WAL for the queue", "because": "writers lock"}
        self.assertEqual(tried.relevance("sqlite", entry), 1.0)
        self.assertEqual(tried.relevance("sqlite queue", entry), 1.0)
        self.assertEqual(tried.relevance("sqlite kubernetes", entry), 0.5)
        self.assertEqual(tried.relevance("kubernetes", entry), 0.0)

    def test_stopwords_alone_match_nothing(self):
        entry = {"what": "the thing with the stuff"}
        self.assertEqual(tried.relevance("the and for", entry), 0.0)

    def test_matching_ignores_case_and_punctuation(self):
        entry = {"what": "SQLite's WAL-mode"}
        self.assertEqual(tried.relevance("sqlite wal", entry), 1.0)

    def test_short_words_are_not_matched_on(self):
        self.assertEqual(tried.words("a an id of"), set())

    def test_ago_reads_naturally(self):
        self.assertEqual(tried.ago(45), "45s")
        self.assertEqual(tried.ago(120), "2m")
        self.assertEqual(tried.ago(7200), "2h")
        self.assertEqual(tried.ago(172800), "2d")


if __name__ == "__main__":
    unittest.main()


class OrderingTest(unittest.TestCase):
    """Bir soniyada qo'shilgan yozuvlar ham to'g'ri tartibda chiqishi kerak."""

    def test_entries_added_in_the_same_second_keep_their_order(self):
        same = 1762600000
        entries = [
            {"id": "a", "what": "first", "at": same},
            {"id": "b", "what": "second", "at": same},
            {"id": "c", "what": "third", "at": same},
        ]
        self.assertEqual([e["what"] for e in tried.newest_first(entries)],
                         ["third", "second", "first"])

    def test_a_newer_second_still_wins(self):
        entries = [
            {"id": "a", "what": "old", "at": 1762600000},
            {"id": "b", "what": "new", "at": 1762600100},
        ]
        self.assertEqual(tried.newest_first(entries)[0]["what"], "new")
