"""Europe profile: per-location filtering, work-permission tags, separate config."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from job_scout import config as config_module
from job_scout.adapters import ashby
from job_scout.models import Board, Posting
from job_scout.permit import classify
from job_scout.poll import run
from job_scout.state import State

REPO = Path(__file__).parent.parent
N8N = Board("n8n", "ashby", "n8n")


def posting(location: str, extra: list[str] | None = None, title: str = "Solutions Engineer", description: str = "") -> Posting:
    return Posting("ashby:n8n", "n8n", "1", title, location, "https://x", extra_locations=extra or [], description=description)


class PermitTests(unittest.TestCase):
    def check(self, text: str, tag: str) -> None:
        self.assertEqual(classify(text).tag, tag, text)

    def test_blockers(self):
        self.check("Unfortunately we are unable to offer visa sponsorship for this role.", "permit_required")
        self.check("We do not sponsor work permits.", "permit_required")
        self.check("You must have the right to work in the UK.", "permit_required")
        self.check("Candidates must be eligible to work in Germany.", "permit_required")
        self.check("Visa sponsorship is not available.", "permit_required")

    def test_blocker_outranks_offer(self):
        self.check("We offer a relocation package. We cannot sponsor visas.", "permit_required")

    def test_conditional_from_real_posting(self):
        # Verbatim from every n8n posting on 2026-11-17.
        signal = classify("We can sponsor visas to Germany; for any other country, you need to have existing right to work.")
        self.assertEqual(signal.tag, "conditional")
        self.assertIn("sponsor visas to Germany", signal.evidence)

    def test_negated_offer_is_not_an_offer(self):
        self.check("We are unable to offer visa sponsorship. Must be eligible to work in the EU.", "permit_required")

    def test_residence(self):
        self.check("This is a remote role, but you must be based in the EU.", "residence_required")

    def test_offers(self):
        self.check("We offer visa sponsorship and relocation support to Amsterdam.", "sponsors")
        self.check("Relocation assistance to Berlin is available.", "sponsors")
        self.check("We hire as an independent contractor through Deel in most countries.", "remote_contract")
        self.check("Work from anywhere, we are fully distributed.", "remote_contract")
        self.check("We use an Employer of Record where we have no entity.", "remote_contract")

    def test_unstated_and_evidence(self):
        self.assertEqual(classify("Join our team in Prague.").tag, "unstated")
        signal = classify("Great team.\nWe offer visa sponsorship for this position. Apply now.")
        self.assertEqual(signal.evidence, "We offer visa sponsorship for this position")


class EuropeConfigTests(unittest.TestCase):
    def setUp(self):
        self.cfg = config_module.load(REPO / "config.europe.json")

    def test_loads_both_watchlists_and_tags(self):
        keys = {b.key for b in self.cfg.watchlist}
        self.assertIn("ashby:n8n", keys)
        self.assertIn("ashby:monday.com", keys)
        self.assertEqual(self.cfg.name, "europe")
        self.assertTrue(self.cfg.permit_tagging)
        self.assertEqual(self.cfg.permit_exclude, ["permit_required"])
        self.assertTrue(str(self.cfg.state_db).endswith("job-scout-europe.sqlite"))

    def test_israel_profile_is_unchanged(self):
        cfg = config_module.load(REPO / "config.json")
        self.assertEqual(cfg.name, "israel")
        self.assertFalse(cfg.permit_tagging)

    def test_location_judged_per_location(self):
        f = self.cfg.filters
        self.assertTrue(f.location_ok(posting("Remote - EMEA")))
        self.assertTrue(f.location_ok(posting("Prague, Czechia")))
        self.assertTrue(f.location_ok(posting("Remote - US", ["London, United Kingdom"])))
        self.assertFalse(f.location_ok(posting("Remote - US")))
        self.assertFalse(f.location_ok(posting("Tel Aviv, Israel")))
        self.assertFalse(f.location_ok(posting("Remote")))

    def test_duplicate_board_across_watchlists_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a.json", Path(tmp) / "b.json"
            entry = {"boards": [{"company": "X", "ats": "ashby", "slug": "x"}]}
            a.write_text(json.dumps(entry))
            b.write_text(json.dumps(entry))
            with self.assertRaises(config_module.ConfigError):
                config_module.load_watchlist([a, b])

    def test_unknown_permit_tag_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "watchlist.json").write_text(json.dumps({"boards": []}))
            (base / "c.json").write_text(json.dumps({"work_permit": {"tag": True, "exclude": ["needs_visa"]}}))
            with self.assertRaises(config_module.ConfigError):
                config_module.load(base / "c.json")


class EuropeRunTests(unittest.TestCase):
    JOBS = {
        "jobs": [
            {"id": "a", "title": "Solutions Engineer", "location": "Berlin", "isListed": True, "jobUrl": "https://a",
             "descriptionPlain": "We offer visa sponsorship and relocation support."},
            {"id": "b", "title": "Implementation Engineer", "location": "London", "isListed": True, "jobUrl": "https://b",
             "descriptionPlain": "You must have the right to work in the UK."},
            {"id": "c", "title": "AI Solutions Engineer", "location": "Remote - EMEA", "isListed": True, "jobUrl": "https://c",
             "descriptionPlain": "Join a distributed team."},
            {"id": "d", "title": "Solutions Engineer", "location": "New York", "isListed": True, "jobUrl": "https://d",
             "descriptionPlain": "We offer visa sponsorship."},
        ]
    }

    def test_tags_and_excludes(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = config_module.load(REPO / "config.europe.json", state_db=Path(tmp) / "s.sqlite")
            cfg.watchlist = [N8N]
            cfg.known_files = []
            state = State(cfg.state_db)
            try:
                report = run(cfg, state, lambda url: copy.deepcopy(self.JOBS), now="2026-11-17T06:00:00+00:00")
            finally:
                state.close()
        tags = {p["title"]: p["work_permit"]["tag"] for p in report.postings}
        self.assertEqual(tags, {"Solutions Engineer": "sponsors", "AI Solutions Engineer": "unstated"})
        self.assertEqual(report.counts["permit_excluded"], 1)
        self.assertEqual(report.counts["outside_location"], 1)
        self.assertEqual(report.profile, "europe")


if __name__ == "__main__":
    unittest.main()
