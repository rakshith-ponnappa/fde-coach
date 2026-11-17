import datetime as dt
import re
import tempfile
import tomllib
import unittest
from pathlib import Path

from fde_coach import jobs, learning, store

ROOT = Path(__file__).resolve().parent.parent
START = dt.date(2026, 11, 11)

CURRICULUM = {
    "phases": [
        {"id": 1, "name": "Python", "weeks": "1-2"},
        {"id": 2, "name": "Production", "weeks": "3"},
    ],
    "weeks": [
        {"n": 1, "phase": 1, "title": "Basics"},
        {"n": 2, "phase": 1, "title": "Loops"},
        {"n": 3, "phase": 2, "title": "APIs"},
    ],
    "skills": [
        {"key": "python", "name": "Python", "baseline": 0, "target": 4},
        {"key": "cloud", "name": "Cloud", "baseline": 4, "target": 4},
    ],
}


class LearningTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = store.connect(Path(self.tmp.name) / "test.db")

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_begin_sets_start_and_seeds_baseline_once(self):
        self.assertIsNone(learning.start_date(self.conn))
        learning.begin(self.conn, CURRICULUM, START)
        learning.begin(self.conn, CURRICULUM, START + dt.timedelta(days=1))
        self.assertEqual(learning.start_date(self.conn), START + dt.timedelta(days=1))
        rows = self.conn.execute("SELECT skill, level FROM skill_ratings ORDER BY skill").fetchall()
        self.assertEqual([tuple(r) for r in rows], [("cloud", 4), ("python", 0)])

    def test_weeks_and_phases(self):
        self.assertEqual(learning.current_week(CURRICULUM, set())["n"], 1)
        learning.mark_week_done(self.conn, 1, START)
        learning.mark_week_done(self.conn, 2, START, "shipped CLI")
        done = learning.done_weeks(self.conn)
        week = learning.current_week(CURRICULUM, done)
        self.assertEqual((week["n"], learning.phase_for(CURRICULUM, week)["name"]), (3, "Production"))
        self.assertIsNone(learning.current_week(CURRICULUM, {1, 2, 3}))
        self.assertEqual(learning.find_week(CURRICULUM, 2)["title"], "Loops")
        with self.assertRaises(LookupError):
            learning.find_week(CURRICULUM, 99)

    def test_pace(self):
        self.assertEqual(learning.pace(set(), START, START + dt.timedelta(days=6)), 0)
        self.assertEqual(learning.pace(set(), START, START + dt.timedelta(days=10)), -1)
        self.assertEqual(learning.pace({1, 2}, START, START + dt.timedelta(days=10)), 1)
        self.assertEqual(learning.describe_pace(0), "on track")
        self.assertEqual(learning.describe_pace(-1), "1 week behind")
        self.assertEqual(learning.describe_pace(3), "3 weeks ahead")

    def test_calendar_and_plan_day(self):
        self.assertEqual(learning.plan_day(START, START), 1)
        self.assertEqual(learning.calendar_week_start(START, START + dt.timedelta(days=9)),
                         START + dt.timedelta(days=7))

    def test_log_hours_and_streak(self):
        for offset, hours in [(0, 4), (1, 3.5), (2, 4)]:
            learning.log_study(self.conn, START + dt.timedelta(days=offset), hours, "study", 1)
        last = START + dt.timedelta(days=2)
        self.assertEqual(learning.streak(self.conn, last), 3)
        self.assertEqual(learning.streak(self.conn, last + dt.timedelta(days=1)), 3)  # today not logged yet
        self.assertEqual(learning.streak(self.conn, last + dt.timedelta(days=2)), 0)
        self.assertEqual(learning.hours_between(self.conn, START, START + dt.timedelta(days=1)), 7.5)
        self.assertEqual(learning.total_hours(self.conn), 11.5)
        self.assertEqual(len(learning.recent_log(self.conn, START + dt.timedelta(days=1))), 2)
        for bad in (0, -1, 17):
            with self.assertRaises(ValueError):
                learning.log_study(self.conn, START, bad, "", 1)

    def test_skills(self):
        learning.begin(self.conn, CURRICULUM, START)
        learning.rate_skill(self.conn, CURRICULUM, "python", 2, START + dt.timedelta(days=30), "CS50P done")
        table = {s["key"]: s for s in learning.skill_table(self.conn, CURRICULUM)}
        self.assertEqual((table["python"]["first"], table["python"]["level"]), (0, 2))
        with self.assertRaises(ValueError):
            learning.rate_skill(self.conn, CURRICULUM, "cooking", 2, START)
        with self.assertRaises(ValueError):
            learning.rate_skill(self.conn, CURRICULUM, "python", 6, START)


class ShippedFilesTest(unittest.TestCase):
    """The shipped curriculum.toml and config.example.toml must stay consistent as you edit them."""

    @classmethod
    def setUpClass(cls):
        with open(ROOT / "curriculum.toml", "rb") as f:
            cls.curriculum = tomllib.load(f)
        with open(ROOT / "config.example.toml", "rb") as f:
            cls.config = tomllib.load(f)

    def test_weeks_are_numbered_and_complete(self):
        weeks = self.curriculum["weeks"]
        self.assertEqual([w["n"] for w in weeks], list(range(1, len(weeks) + 1)))
        phase_ids = {p["id"] for p in self.curriculum["phases"]}
        for week in weeks:
            with self.subTest(week=week["n"]):
                self.assertIn(week["phase"], phase_ids)
                self.assertTrue(week["title"] and week["goals"] and week["deliverable"])
                self.assertTrue(week["resources"])
                for res in week["resources"]:
                    self.assertTrue(res["name"])
                    self.assertTrue(res["url"].startswith("https://"), res["url"])

    def test_phases_cover_their_weeks(self):
        for phase in self.curriculum["phases"]:
            with self.subTest(phase=phase["id"]):
                first, last = (int(x) for x in phase["weeks"].split("-"))
                numbers = [w["n"] for w in self.curriculum["weeks"] if w["phase"] == phase["id"]]
                self.assertEqual(numbers, list(range(first, last + 1)))
                self.assertTrue(set(phase["apply_tiers"]) <= {"A", "B", "C"})
                self.assertGreaterEqual(phase["apply_per_week"], 0)
                self.assertTrue(phase["goal"] and phase["practice"] and phase["job_focus"])

    def test_skills_and_daily_plan(self):
        keys = [s["key"] for s in self.curriculum["skills"]]
        self.assertEqual(len(keys), len(set(keys)))
        for skill in self.curriculum["skills"]:
            self.assertIn(skill["baseline"], range(6))
            self.assertIn(skill["target"], range(6))
        for name in ("default", "sunday"):
            for line in self.curriculum["daily"][name]:
                line.format(practice="x")  # raises if a placeholder is mistyped

    def test_region_patterns_on_real_location_strings(self):
        cases = {
            "Remote - California": ["us"],
            "Remote - Washington D.C.": ["us"],
            "Indianapolis, Indiana": ["us"],
            "Remote, AMER": ["us"],
            "Forward Deployed Engineer, Federal (Onsite - Lexington Park, MD)": ["us"],
            "Hyderabad, India": ["india"],
            "Remote - India": ["india"],
            "Dubai; United Arab Emirates": ["uae"],
            "Riyadh, Saudi Arabia": ["uae"],
            "London, United Kingdom": ["uk"],
            "Singapore": ["singapore"],
            "Remote, Global": ["anywhere"],
            "Toronto, Canada": ["elsewhere"],
        }
        for location, expected in cases.items():
            with self.subTest(location=location):
                self.assertEqual(jobs.regions_of(location, self.config["regions"]), expected)

    def test_config_is_valid(self):
        for section in ("regions", "tiers", "skill_keywords"):
            for name, pattern in self.config[section].items():
                with self.subTest(section=section, name=name):
                    re.compile(pattern)
        self.assertTrue(set(self.config["search"]["regions"]) <= set(self.config["regions"]))
        seen = set()
        for company in self.config["companies"]:
            self.assertIn(company["ats"], jobs.PARSERS)
            self.assertNotIn((company["ats"], company["slug"]), seen)
            seen.add((company["ats"], company["slug"]))
        for label, url in jobs.search_links(self.config):
            self.assertTrue(url.startswith("https://"), label)


if __name__ == "__main__":
    unittest.main()
