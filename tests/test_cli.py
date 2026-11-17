import contextlib
import datetime as dt
import io
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fde_coach import cli, jobs

ROOT = Path(__file__).resolve().parent.parent


class CliTest(unittest.TestCase):
    """Runs real commands against copies of the shipped config.example.toml and curriculum.toml."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        # No config.toml in the copy, so the CLI falls back to config.example.toml as on a fresh clone.
        for name in ("config.example.toml", "curriculum.toml"):
            shutil.copy(ROOT / name, Path(self.tmp.name) / name)
        self.env = mock.patch.dict(os.environ, {"FDE_HOME": self.tmp.name})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(list(argv))
        return code, out.getvalue() + err.getvalue()

    def test_first_day_flow(self):
        code, out = self.run_cli("today", "--offline")
        self.assertEqual(code, 0)
        self.assertIn("Welcome!", out)
        self.assertIn("WEEK 1:", out)
        self.assertIn("TODAY'S 4-HOUR SESSION", out)

        self.assertEqual(self.run_cli("log", "3.5", "CS50P lecture 0")[0], 0)
        code, out = self.run_cli("week", "done", "--note", "first program")
        self.assertEqual(code, 0)
        self.assertIn("Next: week 2", out)
        code, out = self.run_cli("today", "--offline")
        self.assertIn("WEEK 2:", out)
        self.assertIn("streak 1 days", out)
        self.assertIn("WEEK 7:", self.run_cli("week", "show", "7")[1])

        code, out = self.run_cli("plan")
        self.assertEqual(code, 0)
        self.assertIn("[x] W01", out)
        self.assertIn("[>] W02", out)

    def test_skills(self):
        self.assertEqual(self.run_cli("skills", "set", "python", "1", "--note", "week 1")[0], 0)
        code, out = self.run_cli("skills")
        self.assertIn("python", out)
        code, out = self.run_cli("skills", "set", "cooking", "3")
        self.assertEqual(code, 2)
        self.assertIn("unknown skill", out)
        self.assertEqual(self.run_cli("skills", "set", "python")[0], 2)

    def test_job_tracking_and_report(self):
        code, out = self.run_cli("jobs", "add", "Acme", "Forward Deployed Engineer",
                                 "https://example.com/jobs/1", "--location", "Dubai, UAE")
        self.assertEqual(code, 0)
        self.assertIn("#1", out)
        self.assertEqual(self.run_cli("jobs", "apply", "1", "--note", "referral")[0], 0)
        self.assertEqual(self.run_cli("jobs", "status", "1", "interviewing")[0], 0)
        code, out = self.run_cli("jobs", "show", "1")
        self.assertIn("status: interviewing", out)
        self.assertIn("referral", out)
        code, out = self.run_cli("jobs", "list", "--status", "interviewing")
        self.assertIn("Acme", out)
        self.assertEqual(self.run_cli("jobs", "show", "42")[0], 2)
        self.assertIn("linkedin.com/jobs/search", self.run_cli("jobs", "links")[1])
        self.assertIn("No job descriptions", self.run_cli("jobs", "skills")[1])

        code, out = self.run_cli("report", "--write")
        self.assertEqual(code, 0)
        written = Path(self.tmp.name) / "reports" / f"{dt.date.today().isoformat()}.md"
        self.assertTrue(written.exists())
        progress = (Path(self.tmp.name) / "PROGRESS.md").read_text()
        self.assertIn("## Job search", progress)
        self.assertIn("interviewing 1", progress)

    def test_fetch_and_today_use_job_boards(self):
        board = {"jobs": [{"id": "x1", "title": "Forward Deployed Engineer", "location": "Remote",
                           "isRemote": True, "jobUrl": "https://example.com/x1",
                           "descriptionPlain": "Python, RAG, agents and evals."}]}

        def fake(url, timeout=30):
            if url.endswith("job-board/openai"):
                return board
            return {"jobs": []} if "lever" not in url else []

        with mock.patch.object(jobs, "get_json", side_effect=fake):
            code, out = self.run_cli("jobs", "fetch")
            self.assertEqual(code, 0)
            self.assertIn("1 new", out)
            self.assertIn("OpenAI", out)
            # today does not fetch again on the same day, but shows the new role for this phase
            code, out = self.run_cli("today")
        self.assertNotIn("Checking job boards", out)
        self.assertIn("JOB SEARCH", out)
        code, out = self.run_cli("jobs", "skills")
        self.assertIn("Python", out)
        code, out = self.run_cli("init", "--start", "2026-11-01")
        self.assertIn("2026-11-01", out)


if __name__ == "__main__":
    unittest.main()
