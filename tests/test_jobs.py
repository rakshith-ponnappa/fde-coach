import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fde_coach import jobs, store

TODAY = dt.date(2026, 11, 11)

CONFIG = {
    "search": {"regions": ["uae", "uk", "us"], "remote_ok": True, "remote_open_to": ["india", "apac", "anywhere"]},
    "regions": {
        "india": "india|hyderabad",
        "uae": "dubai|uae|united arab emirates",
        "uk": "london|united kingdom",
        "us": r"united states|\busa?\b|new york",
        "apac": r"\bapac\b",
        "anywhere": "anywhere|worldwide",
        "elsewhere": "canada|toronto",
    },
    "tiers": {
        "A": r"forward[- ]deploy",
        "B": r"applied ai|\bai engineer|solutions? architect",
        "C": r"platform engineer|\bsre\b",
        "exclude": r"\bintern\b|recruit",
    },
    "skill_keywords": {"Python": r"\bpython\b", "RAG": r"\brag\b", "Kubernetes": "kubernetes"},
    "linkedin": {
        "posted_within": "r86400",
        "queries": ['"forward deployed"'],
        "locations": [{"label": "Remote from India", "name": "India", "remote": True},
                      {"label": "UAE", "name": "United Arab Emirates"}],
    },
    "links": [{"label": "HN", "url": "https://news.ycombinator.com/submitted?id=whoishiring"}],
    "companies": [
        {"name": "Acme AI", "ats": "greenhouse", "slug": "acme"},
        {"name": "Bolt", "ats": "lever", "slug": "bolt"},
        {"name": "Cog", "ats": "ashby", "slug": "cog"},
        {"name": "Broken", "ats": "ashby", "slug": "broken"},
    ],
}

GREENHOUSE_LIST = {"jobs": [
    {"id": 1, "title": "Forward Deployed Engineer", "location": {"name": "London, United Kingdom"},
     "absolute_url": "https://example.com/gh/1", "first_published": "2026-11-01T10:00:00-04:00"},
    {"id": 2, "title": "Recruiter", "location": {"name": "London"}, "absolute_url": "https://example.com/gh/2"},
    {"id": 3, "title": "Platform Engineer", "location": {"name": "Toronto, Canada"},
     "absolute_url": "https://example.com/gh/3"},
]}
GREENHOUSE_DETAIL = {"content": "&lt;p&gt;Python &amp;amp; RAG.&lt;/p&gt;&lt;p&gt;We\u2019re unable to offer visa sponsorship.&lt;/p&gt;"}
LEVER_LIST = [
    {"id": "L1", "text": "AI Engineer", "hostedUrl": "https://example.com/lv/1",
     "categories": {"location": "Dubai", "allLocations": ["Dubai"]}, "country": "AE", "workplaceType": "onsite",
     "descriptionPlain": "Kubernetes and Python.", "lists": [{"text": "You have", "content": "<li>RAG</li>"}],
     "additionalPlain": "Relocation assistance available.", "createdAt": 1793000000000},
    {"id": "L2", "text": "Recruiter, Forward Deployed", "hostedUrl": "https://example.com/lv/2",
     "categories": {"location": "Dubai"}},
]
ASHBY_LIST = {"jobs": [
    {"id": "A1", "title": "Applied AI Engineer", "location": "Hyderabad", "isRemote": True,
     "jobUrl": "https://example.com/ab/1", "descriptionPlain": "We do sponsor visas! We can't sponsor every role.",
     "publishedAt": "2026-11-09T00:00:00Z"},
    {"id": "A2", "title": "Solutions Architect", "location": "Hyderabad", "isRemote": False,
     "jobUrl": "https://example.com/ab/2"},
    {"id": "A3", "title": "Forward Deployed Engineer", "location": "Toronto", "isRemote": True,
     "jobUrl": "https://example.com/ab/3", "isListed": False},
]}


def fake_get_json(url, timeout=30):
    if url.endswith("boards/acme/jobs/1"):
        return GREENHOUSE_DETAIL
    if url.endswith("boards/acme/jobs"):
        return GREENHOUSE_LIST
    if "postings/bolt" in url:
        return LEVER_LIST
    if url.endswith("job-board/cog"):
        return ASHBY_LIST
    raise OSError("HTTP Error 404: Not Found")


class JobsTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = store.connect(Path(self.tmp.name) / "test.db")

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def fetch(self, today=TODAY):
        with mock.patch.object(jobs, "get_json", side_effect=fake_get_json) as patched:
            result = jobs.fetch_all(self.conn, CONFIG, today, workers=2)
        return result, [call.args[0] for call in patched.call_args_list]


class ParsingTest(unittest.TestCase):
    def test_greenhouse(self):
        [first, *_] = jobs.parse_greenhouse("Acme AI", "acme", GREENHOUSE_LIST)
        self.assertEqual(first.key, "greenhouse:acme:1")
        self.assertEqual(first.location, "London, United Kingdom")
        self.assertEqual(first.posted_on, "2026-11-01")
        self.assertFalse(first.remote)

    def test_lever_spells_out_country_and_joins_lists(self):
        first = jobs.parse_lever("Bolt", "bolt", LEVER_LIST)[0]
        self.assertEqual(first.location, "Dubai; United Arab Emirates")
        self.assertIn("RAG", first.description)
        self.assertIn("Relocation", first.description)
        self.assertEqual(first.posted_on, "2026-10-26")
        self.assertEqual(jobs.parse_lever("Bolt", "bolt", {"error": "x"}), [])

    def test_ashby_skips_unlisted_jobs(self):
        postings = jobs.parse_ashby("Cog", "cog", ASHBY_LIST)
        self.assertEqual([p.key for p in postings], ["ashby:cog:A1", "ashby:cog:A2"])
        self.assertTrue(postings[0].remote)

    def test_html_to_text(self):
        self.assertEqual(jobs.html_to_text("&lt;p&gt;Hi &amp;amp; bye&lt;/p&gt;&lt;ul&gt;&lt;li&gt;x&lt;/li&gt;"),
                         "Hi & bye\nx")
        self.assertEqual(jobs.html_to_text(None), "")


class ClassificationTest(unittest.TestCase):
    def test_tiers(self):
        tiers = CONFIG["tiers"]
        self.assertEqual(jobs.tier_of("Forward-Deployed Engineer", tiers), "A")
        self.assertEqual(jobs.tier_of("Senior Applied AI Engineer", tiers), "B")
        self.assertEqual(jobs.tier_of("Staff Platform Engineer", tiers), "C")
        self.assertIsNone(jobs.tier_of("Forward Deployed Recruiter", tiers))
        self.assertIsNone(jobs.tier_of("Accountant", tiers))

    def test_locations(self):
        search, patterns = CONFIG["search"], CONFIG["regions"]

        def ok(location, remote):
            return jobs.location_ok(jobs.regions_of(location, patterns), remote, search)

        self.assertTrue(ok("London, United Kingdom", False))
        self.assertTrue(ok("Remote - India", True))
        self.assertTrue(ok("Remote", True))
        self.assertTrue(ok("Remote - US", True))
        self.assertFalse(ok("Remote - Canada", True))
        self.assertFalse(ok("Hyderabad, India", False))
        self.assertFalse(ok("Toronto", False))
        self.assertFalse(jobs.location_ok([], True, {**search, "remote_ok": False}))

    def test_title_fills_in_a_missing_region(self):
        remote_uae = jobs.Posting(key="k1", company="X", title="Forward Deployed Engineer - UAE",
                                  location="Remote", url="https://example.com/1", remote=True)
        self.assertTrue(jobs.classify(remote_uae, CONFIG))
        self.assertEqual(remote_uae.regions, ["uae"])
        london = jobs.Posting(key="k2", company="X", title="Forward Deployed Engineer - US",
                              location="London, United Kingdom", url="https://example.com/2")
        self.assertTrue(jobs.classify(london, CONFIG))
        self.assertEqual(london.regions, ["uk"])  # the location wins when it names a place

    def test_sponsorship(self):
        cases = {
            "Please note: we're unable to offer visa sponsorship for these roles.": "no",
            "We do sponsor visas! However, we aren't able to successfully sponsor visas for every role.": "yes",
            "Visa sponsorship is available for this position.": "yes",
            "You must be a U.S. citizen. Great benefits.": "no",
            "Candidates must be authorized to work without the need for visa sponsorship.": "no",
            "Relocation assistance is offered.": "reloc",
            "A great team.": "?",
            "": "?",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(jobs.sponsorship_of(text), expected)


class FetchTest(JobsTestCase):
    def test_fetch_filters_saves_and_reports_errors(self):
        result, urls = self.fetch()
        self.assertEqual(result.boards, 4)
        self.assertEqual(result.matched, 3)
        self.assertEqual(sorted(p.key for p in result.new),
                         ["ashby:cog:A1", "greenhouse:acme:1", "lever:bolt:L1"])
        self.assertEqual([name for name, _ in result.errors], ["Broken"])
        self.assertIn("https://boards-api.greenhouse.io/v1/boards/acme/jobs/1", urls)

        rows = {r["key"]: r for r in self.conn.execute("SELECT * FROM jobs")}
        self.assertEqual(rows["greenhouse:acme:1"]["sponsorship"], "no")
        self.assertEqual(rows["lever:bolt:L1"]["sponsorship"], "reloc")
        self.assertEqual(rows["ashby:cog:A1"]["sponsorship"], "yes")
        self.assertEqual(rows["ashby:cog:A1"]["regions"], "remote,india")
        self.assertEqual(store.get_setting(self.conn, "last_fetch"), TODAY.isoformat())

    def test_second_fetch_finds_nothing_new_and_skips_known_descriptions(self):
        self.fetch()
        result, urls = self.fetch(TODAY + dt.timedelta(days=1))
        self.assertEqual(result.new, [])
        self.assertNotIn("https://boards-api.greenhouse.io/v1/boards/acme/jobs/1", urls)
        last_seen = self.conn.execute("SELECT DISTINCT last_seen FROM jobs").fetchall()
        self.assertEqual([r[0] for r in last_seen], ["2026-11-12"])

    def test_offline_run_does_not_count_as_todays_check(self):
        with mock.patch.object(jobs, "get_json", side_effect=OSError("offline")):
            result = jobs.fetch_all(self.conn, CONFIG, TODAY, workers=2)
        self.assertEqual(len(result.errors), 4)
        self.assertIsNone(store.get_setting(self.conn, "last_fetch"))

    def test_missing_greenhouse_description_is_retried_next_time(self):
        def no_detail(url, timeout=30):
            if url.endswith("/jobs/1"):
                raise OSError("HTTP Error 429: Too Many Requests")
            return fake_get_json(url)

        with mock.patch.object(jobs, "get_json", side_effect=no_detail):
            result = jobs.fetch_all(self.conn, CONFIG, TODAY, workers=1)
        self.assertEqual(result.matched, 3)
        row = self.conn.execute("SELECT description, sponsorship FROM jobs WHERE key = 'greenhouse:acme:1'").fetchone()
        self.assertEqual(tuple(row), ("", "?"))

        result, urls = self.fetch(TODAY + dt.timedelta(days=1))
        self.assertEqual(result.new, [])
        self.assertIn("https://boards-api.greenhouse.io/v1/boards/acme/jobs/1", urls)
        row = self.conn.execute("SELECT description, sponsorship FROM jobs WHERE key = 'greenhouse:acme:1'").fetchone()
        self.assertIn("RAG", row["description"])
        self.assertEqual(row["sponsorship"], "no")


class PipelineTest(JobsTestCase):
    def test_list_order_status_and_follow_ups(self):
        self.fetch()
        rows = jobs.list_jobs(self.conn, CONFIG, TODAY)
        # Tier A first; within tier B the remote-from-India role beats the Dubai one.
        self.assertEqual([r["key"] for r in rows], ["greenhouse:acme:1", "ashby:cog:A1", "lever:bolt:L1"])
        self.assertEqual(len(jobs.list_jobs(self.conn, CONFIG, TODAY, region="uae")), 1)
        self.assertEqual(len(jobs.list_jobs(self.conn, CONFIG, TODAY, tier="b")), 2)

        first = rows[0]["id"]
        jobs.set_status(self.conn, first, "applied", TODAY, "tailored CV")
        self.assertEqual(jobs.applications_between(self.conn, TODAY, TODAY), 1)
        self.assertEqual(jobs.pipeline_counts(self.conn)["applied"], 1)
        self.assertIn("tailored CV", jobs.get_job(self.conn, first)["notes"])
        self.assertEqual(jobs.follow_ups(self.conn, TODAY), [])
        self.assertEqual(len(jobs.follow_ups(self.conn, TODAY + dt.timedelta(days=7))), 1)

        # Applied roles stay visible after the ad disappears; skipped roles are hidden.
        later = TODAY + dt.timedelta(days=10)
        self.assertEqual([r["id"] for r in jobs.list_jobs(self.conn, CONFIG, later)], [first])
        jobs.set_status(self.conn, rows[1]["id"], "skipped", TODAY)
        self.assertNotIn(rows[1]["id"], [r["id"] for r in jobs.list_jobs(self.conn, CONFIG, TODAY)])
        self.assertEqual(len(jobs.list_jobs(self.conn, CONFIG, TODAY, show_all=True)), 3)
        self.assertEqual(len(jobs.list_jobs(self.conn, CONFIG, TODAY, status="skipped")), 1)

    def test_bad_status_and_unknown_job(self):
        with self.assertRaises(ValueError):
            jobs.set_status(self.conn, 1, "hired!", TODAY)
        with self.assertRaises(LookupError):
            jobs.set_status(self.conn, 99, "applied", TODAY)

    def test_add_manual(self):
        with self.assertRaises(ValueError):
            jobs.add_manual(self.conn, CONFIG, "Acme", "AI Engineer", "javascript:alert(1)", "", TODAY)
        job_id = jobs.add_manual(self.conn, CONFIG, "Acme", "Forward Deployed Engineer",
                                 "https://example.com/job", "Dubai", TODAY)
        row = jobs.get_job(self.conn, job_id)
        self.assertEqual((row["tier"], row["status"], row["regions"]), ("A", "shortlisted", "uae"))
        with self.assertRaises(ValueError):
            jobs.add_manual(self.conn, CONFIG, "Acme", "Forward Deployed Engineer",
                            "https://example.com/job", "Dubai", TODAY)
        other = jobs.add_manual(self.conn, CONFIG, "Beta", "Consultant", "https://example.com/2", "", TODAY)
        self.assertEqual(jobs.get_job(self.conn, other)["tier"], "?")

    def test_skill_demand(self):
        self.fetch()
        checked, demand = jobs.skill_demand(self.conn, CONFIG["skill_keywords"], TODAY)
        self.assertEqual(checked, 3)
        self.assertEqual(dict(demand), {"Python": 2, "RAG": 2, "Kubernetes": 1})


class LinksTest(unittest.TestCase):
    def test_linkedin_links_are_encoded(self):
        links = jobs.search_links(CONFIG)
        self.assertEqual(len(links), 3)
        label, url = links[0]
        self.assertIn("Remote from India", label)
        self.assertTrue(url.startswith("https://www.linkedin.com/jobs/search/?keywords=%22forward+deployed%22"))
        self.assertIn("f_WT=2", url)
        self.assertNotIn("f_WT", links[1][1])
        self.assertEqual(links[2][0], "HN")


if __name__ == "__main__":
    unittest.main()
