"""Offline tests. Board responses come from tests/fixtures; nothing touches the network."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from job_scout import config as config_module
from job_scout.adapters import ashby, greenhouse, lever
from job_scout.config import Config
from job_scout.filters import Filters
from job_scout.models import Board
from job_scout.poll import run
from job_scout.state import State
from job_scout.text import html_to_text

FIXTURES = Path(__file__).parent / "fixtures"
REPO = Path(__file__).parent.parent

GUARDZ = Board("Guardz", "greenhouse", "guardz")
WALKME = Board("WalkMe", "lever", "walkme")
WONDERFUL = Board("Wonderful", "ashby", "wonderful")


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text())


class FakeFetcher:
    """Serves fixtures by URL; a test can edit or break a response between runs."""

    def __init__(self) -> None:
        self.responses = {
            greenhouse.url(GUARDZ): load_fixture("greenhouse.json"),
            lever.url(WALKME): load_fixture("lever.json"),
            ashby.url(WONDERFUL): load_fixture("ashby.json"),
        }
        self.broken: set[str] = set()

    def __call__(self, url: str):
        if url in self.broken:
            raise OSError("connection refused")
        return copy.deepcopy(self.responses[url])


def repo_filters() -> Filters:
    return Filters.from_config(json.loads((REPO / "config.json").read_text())["filters"])


class AdapterTests(unittest.TestCase):
    def test_greenhouse_parses_and_unescapes(self):
        postings = greenhouse.parse(GUARDZ, load_fixture("greenhouse.json"))
        first = postings[0]
        self.assertEqual(first.key, "greenhouse:guardz:4517973101")
        self.assertEqual(first.published_at, "2026-11-10T09:00:00-05:00")
        self.assertIn("Build & run AI automations.", first.description)
        self.assertNotIn("<", first.description)
        self.assertIn("Tel Aviv, Israel", first.extra_locations)

    def test_lever_parses_lists_and_eu_host(self):
        posting = lever.parse(WALKME, load_fixture("lever.json"))[0]
        self.assertEqual(posting.title, "Technical Solution Engineer")
        self.assertIn("Requirements", posting.description)
        self.assertIn("APIs", posting.description)
        self.assertTrue(posting.published_at.startswith("2025-11-03"))
        self.assertIn("api.eu.lever.co", lever.url(Board("Mobileye", "lever", "mobileye", region="eu")))

    def test_lever_unknown_slug_is_an_error(self):
        with self.assertRaises(ValueError):
            lever.parse(WALKME, {"ok": False, "error": "Document not found"})

    def test_ashby_skips_unlisted_and_keeps_secondary_country(self):
        postings = ashby.parse(WONDERFUL, load_fixture("ashby.json"))
        self.assertEqual([p.job_id for p in postings], ["bcca831c-e420-46bf-8533-1dc912025732", "c76a5995-13f5-4b3e-a794-520baef3210f"])
        self.assertIn("Israel", postings[1].extra_locations)

    def test_html_to_text_handles_double_escaping(self):
        self.assertEqual(html_to_text("&lt;p&gt;A &amp;amp; B&lt;/p&gt;"), "A & B")


class FilterTests(unittest.TestCase):
    def setUp(self):
        self.filters = repo_filters()
        self.postings = {p.title: p for p in greenhouse.parse(GUARDZ, load_fixture("greenhouse.json"))}

    def test_location(self):
        self.assertTrue(self.filters.location_ok(self.postings["AI Solutions Engineer"]))
        self.assertFalse(self.filters.location_ok(self.postings["Customer Success Manager"]))

    def test_titles(self):
        self.assertEqual(self.filters.title_reason(self.postings["Support Operations & AI Automation Engineer"]), "")
        self.assertIn("director", self.filters.title_reason(self.postings["Director of AI Solutions"]))
        self.assertEqual(self.filters.title_reason(self.postings["Engineering Manager"]), "title matches no included term")

    def test_word_boundaries(self):
        # "ai" must not match inside other words, and "IL" is not a location term (Illinois).
        posting = copy.copy(self.postings["Engineering Manager"])
        posting.title = "Retail Domain Specialist"
        self.assertEqual(self.filters.title_reason(posting), "title matches no included term")
        posting.location = "Chicago, IL"
        posting.extra_locations = []
        self.assertFalse(self.filters.location_ok(posting))


class RunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.notes = self.dir / "tracker.md"
        self.notes.write_text("| 117 | WalkMe — Technical Solution Engineer | Tel Aviv | rejected |\n")
        self.config = Config(
            watchlist=[GUARDZ, WALKME, WONDERFUL],
            filters=repo_filters(),
            state_db=self.dir / "state.sqlite",
            known_files=[self.notes],
        )
        self.fetcher = FakeFetcher()

    def tearDown(self):
        self.tmp.cleanup()

    def poll(self, **kwargs):
        state = State(self.config.state_db)
        try:
            return run(self.config, state, self.fetcher, now=kwargs.pop("now", "2026-11-17T06:00:00+00:00"), **kwargs)
        finally:
            state.close()

    def titles(self, report):
        return sorted(p["title"] for p in report.postings)

    def test_first_run_reports_matches_and_skips_known(self):
        report = self.poll()
        self.assertEqual(
            self.titles(report),
            ["AI Solutions Engineer", "Deployment Strategist", "Deployment Strategist, Israel", "Support Operations & AI Automation Engineer"],
        )
        self.assertEqual(report.counts["known_in_notes"], 1)
        self.assertEqual(report.known[0]["reason"], "company and title found on one line in notes")
        self.assertTrue(all(p["first_poll_of_board"] for p in report.postings))
        self.assertEqual(report.boards_ok, 3)

    def test_second_run_is_quiet(self):
        self.poll()
        report = self.poll(now="2026-11-18T06:00:00+00:00")
        self.assertEqual(report.postings, [])
        self.assertEqual(report.counts["already_reported"], 4)

    def test_new_updated_closed_reopened(self):
        self.poll()
        jobs = self.fetcher.responses[greenhouse.url(GUARDZ)]["jobs"]
        removed = jobs.pop(2)  # AI Solutions Engineer closes
        jobs[0]["content"] = "&lt;p&gt;Now also owns Intercom.&lt;/p&gt;"
        jobs.append(dict(removed, id=5200000002, title="Implementation Engineer"))
        report = self.poll(now="2026-11-18T06:00:00+00:00")
        changes = {p["title"]: p["change"] for p in report.postings}
        self.assertEqual(changes, {"Support Operations & AI Automation Engineer": "updated", "Implementation Engineer": "new"})
        self.assertFalse(any(p["first_poll_of_board"] for p in report.postings))
        self.assertEqual([c["title"] for c in report.closed], ["AI Solutions Engineer"])

        jobs.append(removed)
        report = self.poll(now="2026-11-19T06:00:00+00:00")
        self.assertEqual({p["title"]: p["change"] for p in report.postings}, {"AI Solutions Engineer": "reopened"})

    def test_failed_board_is_reported_and_closes_nothing(self):
        self.poll()
        self.fetcher.broken.add(greenhouse.url(GUARDZ))
        report = self.poll(now="2026-11-18T06:00:00+00:00")
        self.assertEqual(report.failed_boards[0]["board"], "greenhouse:guardz")
        self.assertEqual(report.counts["closed"], 0)
        report = self.poll(now="2026-11-19T06:00:00+00:00")
        self.assertEqual(report.failed_boards[0]["consecutive_failures"], 2)

    def test_baseline_reports_nothing_then_only_changes(self):
        self.assertEqual(self.poll(baseline=True).postings, [])
        jobs = self.fetcher.responses[greenhouse.url(GUARDZ)]["jobs"]
        jobs.append(dict(jobs[2], id=5300000003, title="Integration Engineer"))
        self.assertEqual(self.titles(self.poll(now="2026-11-18T06:00:00+00:00")), ["Integration Engineer"])

    def test_dry_run_writes_nothing(self):
        self.poll(dry_run=True)
        self.assertEqual(len(self.poll().postings), 4)

    def test_job_id_in_notes_counts_as_known(self):
        self.notes.write_text("Applied: https://job-boards.eu.greenhouse.io/guardz/jobs/4517973101\n")
        report = self.poll()
        self.assertNotIn("Support Operations & AI Automation Engineer", self.titles(report))
        self.assertIn({"company": "Guardz", "title": "Support Operations & AI Automation Engineer", "reason": "job id found in notes"}, report.known)


class ConfigTests(unittest.TestCase):
    def test_repo_config_and_watchlist_load(self):
        cfg = config_module.load(REPO / "config.json", use_local=False)
        self.assertGreater(len(cfg.watchlist), 30)
        self.assertEqual(len({b.key for b in cfg.watchlist}), len(cfg.watchlist))

    def test_local_override_and_missing_known_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "watchlist.json").write_text(json.dumps({"boards": [{"company": "X", "ats": "ashby", "slug": "x"}]}))
            (base / "config.json").write_text(json.dumps({"known_files": []}))
            (base / "config.local.json").write_text(json.dumps({"known_files": ["missing.md"]}))
            with self.assertRaises(config_module.ConfigError):
                config_module.load(base / "config.json")

    def test_unknown_ats_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "w.json"
            path.write_text(json.dumps({"boards": [{"company": "X", "ats": "comeet", "slug": "x"}]}))
            with self.assertRaises(config_module.ConfigError):
                config_module.load_watchlist(path)


if __name__ == "__main__":
    unittest.main()
