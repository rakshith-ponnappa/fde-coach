"""Storage: one SQLite database plus two TOML files you can edit by hand.

Everything lives in the project folder (or in $FDE_HOME when that is set):
  config.toml      companies to watch, job title/location filters, search links
                   (create it with `cp config.example.toml config.toml`; until then
                   config.example.toml is read instead)
  curriculum.toml  the week-by-week learning plan and the skills you track
  data/fde.db      your study log, finished weeks, skill ratings and job pipeline
"""

import os
import sqlite3
import tomllib
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS study_log (
    id    INTEGER PRIMARY KEY,
    day   TEXT NOT NULL,             -- YYYY-MM-DD
    hours REAL NOT NULL,
    week  INTEGER,                   -- plan week you were working on
    note  TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS weeks_done (
    week    INTEGER PRIMARY KEY,
    done_on TEXT NOT NULL,
    note    TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS skill_ratings (
    id       INTEGER PRIMARY KEY,
    skill    TEXT NOT NULL,
    level    INTEGER NOT NULL CHECK (level BETWEEN 0 AND 5),
    rated_on TEXT NOT NULL,
    note     TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS jobs (
    id          INTEGER PRIMARY KEY,
    key         TEXT NOT NULL UNIQUE, -- ats:board:posting-id, or manual:url
    company     TEXT NOT NULL,
    title       TEXT NOT NULL,
    location    TEXT NOT NULL DEFAULT '',
    url         TEXT NOT NULL,
    tier        TEXT NOT NULL,        -- A = FDE, B = AI-adjacent, C = platform stepping stone
    regions     TEXT NOT NULL DEFAULT '',
    sponsorship TEXT NOT NULL DEFAULT '?',
    description TEXT NOT NULL DEFAULT '',
    posted_on   TEXT NOT NULL DEFAULT '',
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'new',
    status_on   TEXT NOT NULL DEFAULT '',
    notes       TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS job_events (
    id     INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    status TEXT NOT NULL,
    on_day TEXT NOT NULL,
    note   TEXT NOT NULL DEFAULT ''
);
"""


def home() -> Path:
    """Return the project folder that holds the TOML files, data/ and reports/."""
    return Path(os.environ.get("FDE_HOME") or Path(__file__).resolve().parent.parent)


def connect(path: Path | None = None) -> sqlite3.Connection:
    """Open the progress database, creating the file and tables on first use."""
    path = path or home() / "data" / "fde.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def load_toml(name: str) -> dict:
    """Read one of the editable TOML files from the project folder.

    When NAME.toml is missing but NAME.example.toml exists (e.g. a fresh clone without
    config.toml), the example file is read instead.
    """
    path = home() / name
    example = path.with_suffix(".example" + path.suffix)
    if not path.exists() and example.exists():
        path = example
    with open(path, "rb") as f:
        return tomllib.load(f)


def get_setting(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    """Read a single saved setting such as the plan start date."""
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    """Save (or overwrite) a single setting."""
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()
