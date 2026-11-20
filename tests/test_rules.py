"""Standing rules from the tracker: high-level Hebrew, blocked companies, one role per company."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from job_scout import hebrew
from job_scout.adapters import greenhouse
from job_scout.config import Config
from job_scout.known import KnownIndex
from job_scout.poll import run
from job_scout.state import State
from tests.test_job_scout import GUARDZ, WALKME, WONDERFUL, FakeFetcher, repo_filters


class HebrewTests(unittest.TestCase):
    def tag(self, text: str) -> str:
        return hebrew.classify(text).tag

    def test_high_level_is_required(self):
        for text in [
            "Native Hebrew and English.",
            "Excellent communication skills in Hebrew and English.",
            "Hebrew: native level",
            "Requirements:\nHigh-level Hebrew, written and spoken",
            "עברית ברמת שפת אם",
        ]:
            self.assertEqual(self.tag(text), hebrew.HIGH_REQUIRED, text)

    def test_soft_or_fluent_is_only_mentioned(self):
        for text in ["Fluent Hebrew and English", "Native Hebrew - an advantage", "English required; Hebrew is a plus"]:
            self.assertEqual(self.tag(text), hebrew.MENTIONED, text)

    def test_hebrew_language_posting_and_nothing(self):
        self.assertEqual(self.tag("דרושה מיישמת פתרונות בינה מלאכותית לחברה מובילה באזור המרכז, עבודה מול לקוחות"), hebrew.HEBREW_POSTING)
        self.assertEqual(self.tag("Strong English. Python."), hebrew.UNSTATED)

    def test_evidence_is_the_sentence(self):
        signal = hebrew.classify("You will build tools. Native Hebrew speaker. Python.")
        self.assertEqual(signal.evidence, "Native Hebrew speaker")


class EmployerTests(unittest.TestCase):
    def test_only_application_records_count(self):
        index = KnownIndex([
            "| 117 | WalkMe — Technical Solution Engineer | Tel Aviv | rejected |",
            "### 21. Unframe — Forward Deployed Engineer",
            "Seen via Gotfriends; Rise mentioned in passing.",
        ])
        self.assertIn("WalkMe", index.employer_line("WalkMe"))
        self.assertIn("Unframe", index.employer_line("Unframe"))
        self.assertEqual(index.employer_line("Via"), "")
        self.assertEqual(index.employer_line("Rise"), "")


class RuleRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        notes = self.dir / "tracker.md"
        notes.write_text("| 131 | Guardz — Customer Onboarding Lead | Tel Aviv | applied |\n")
        self.config = Config(
            watchlist=[GUARDZ, WALKME, WONDERFUL],
            filters=repo_filters(),
            state_db=self.dir / "state.sqlite",
            known_files=[notes],
            hebrew_tagging=True,
            hebrew_exclude=[hebrew.HIGH_REQUIRED],
            blocked_companies=["WalkMe"],
        )
        self.fetcher = FakeFetcher()

    def tearDown(self):
        self.tmp.cleanup()

    def poll(self, now="2026-11-20T04:00:00+00:00"):
        state = State(self.config.state_db)
        try:
            return run(self.config, state, self.fetcher, now=now)
        finally:
            state.close()

    def test_rules_apply_and_hebrew_drop_is_listed_once(self):
        jobs = self.fetcher.responses[greenhouse.url(GUARDZ)]["jobs"]
        target = next(j for j in jobs if j["title"] == "AI Solutions Engineer")
        target["content"] = "&lt;p&gt;Native Hebrew and English.&lt;/p&gt;"

        report = self.poll()
        titles = {p["title"] for p in report.postings}
        self.assertNotIn("AI Solutions Engineer", titles)
        self.assertEqual(report.counts["hebrew_excluded"], 1)
        self.assertEqual(report.excluded[0]["evidence"], "Native Hebrew and English")
        self.assertGreaterEqual(report.counts["blocked_company"], 1)
        self.assertFalse(any(p["company"] == "WalkMe" for p in report.postings))
        guardz = [p for p in report.postings if p["company"] == "Guardz"]
        self.assertTrue(guardz)
        self.assertTrue(all("| 131 | Guardz" in p["employer_in_tracker"] for p in guardz))
        self.assertTrue(all("hebrew" in p for p in report.postings))

        again = self.poll(now="2026-11-21T04:00:00+00:00")
        self.assertEqual(again.excluded, [])
        self.assertEqual(again.counts["hebrew_excluded"], 0)


if __name__ == "__main__":
    unittest.main()
