"""Your learning plan: current week, study hours, streaks, pace and skill ratings."""

import datetime as dt
import sqlite3

from .store import get_setting, set_setting

LEVELS = ["none", "aware", "guided", "independent", "production", "expert"]
WEEKLY_TARGET_HOURS = 28  # 4 hours x 7 days


def start_date(conn: sqlite3.Connection) -> dt.date | None:
    """Day 1 of your plan, or None before the first run."""
    value = get_setting(conn, "start_date")
    return dt.date.fromisoformat(value) if value else None


def begin(conn: sqlite3.Connection, curriculum: dict, day: dt.date) -> None:
    """Set the plan start date; on the very first run also record baseline skill ratings."""
    set_setting(conn, "start_date", day.isoformat())
    if conn.execute("SELECT 1 FROM skill_ratings LIMIT 1").fetchone() is None:
        conn.executemany(
            "INSERT INTO skill_ratings (skill, level, rated_on, note) VALUES (?, ?, ?, 'baseline estimate')",
            [(s["key"], s["baseline"], day.isoformat()) for s in curriculum["skills"]],
        )
        conn.commit()


def done_weeks(conn: sqlite3.Connection) -> set[int]:
    """Week numbers you have marked as finished."""
    return {row["week"] for row in conn.execute("SELECT week FROM weeks_done")}


def current_week(curriculum: dict, done: set[int]) -> dict | None:
    """First plan week not yet marked done (None once the whole plan is finished)."""
    return next((w for w in curriculum["weeks"] if w["n"] not in done), None)


def find_week(curriculum: dict, number: int) -> dict:
    """Look up a plan week by its number."""
    for week in curriculum["weeks"]:
        if week["n"] == number:
            return week
    raise LookupError(f"there is no week {number} in the plan")


def phase_for(curriculum: dict, week: dict) -> dict:
    """The phase a week belongs to."""
    return next(p for p in curriculum["phases"] if p["id"] == week["phase"])


def mark_week_done(conn: sqlite3.Connection, number: int, day: dt.date, note: str = "") -> None:
    """Record that you finished a week (including its deliverable)."""
    conn.execute(
        "INSERT OR REPLACE INTO weeks_done (week, done_on, note) VALUES (?, ?, ?)",
        (number, day.isoformat(), note),
    )
    conn.commit()


def log_study(conn: sqlite3.Connection, day: dt.date, hours: float, note: str, week: int | None) -> None:
    """Add a study session to the log."""
    if not 0 < hours <= 16:
        raise ValueError("hours must be more than 0 and at most 16")
    conn.execute(
        "INSERT INTO study_log (day, hours, week, note) VALUES (?, ?, ?, ?)",
        (day.isoformat(), hours, week, note),
    )
    conn.commit()


def hours_between(conn: sqlite3.Connection, first: dt.date, last: dt.date) -> float:
    """Total hours logged from `first` to `last`, both days included."""
    row = conn.execute(
        "SELECT COALESCE(SUM(hours), 0) AS total FROM study_log WHERE day BETWEEN ? AND ?",
        (first.isoformat(), last.isoformat()),
    ).fetchone()
    return float(row["total"])


def total_hours(conn: sqlite3.Connection) -> float:
    """All hours ever logged."""
    return float(conn.execute("SELECT COALESCE(SUM(hours), 0) AS total FROM study_log").fetchone()["total"])


def recent_log(conn: sqlite3.Connection, since: dt.date) -> list[sqlite3.Row]:
    """Study sessions since a date, newest first."""
    return conn.execute(
        "SELECT day, hours, week, note FROM study_log WHERE day >= ? ORDER BY day DESC, id DESC",
        (since.isoformat(),),
    ).fetchall()


def streak(conn: sqlite3.Connection, today: dt.date) -> int:
    """Consecutive study days ending today (or yesterday, if today is not logged yet)."""
    days = {dt.date.fromisoformat(r["day"]) for r in conn.execute("SELECT DISTINCT day FROM study_log")}
    day = today if today in days else today - dt.timedelta(days=1)
    count = 0
    while day in days:
        count += 1
        day -= dt.timedelta(days=1)
    return count


def plan_day(start: dt.date, today: dt.date) -> int:
    """Day number in the plan, where the start date is day 1."""
    return (today - start).days + 1


def calendar_week_start(start: dt.date, today: dt.date) -> dt.date:
    """First day of the current 7-day plan week (plan weeks begin on your start weekday)."""
    return start + dt.timedelta(days=7 * ((today - start).days // 7))


def pace(done: set[int], start: dt.date, today: dt.date) -> int:
    """Weeks ahead (positive) or behind (negative) the calendar."""
    weeks_elapsed = (today - start).days // 7
    return len(done) - weeks_elapsed


def describe_pace(weeks: int) -> str:
    """Human wording for pace()."""
    if weeks == 0:
        return "on track"
    unit = "week" if abs(weeks) == 1 else "weeks"
    return f"{abs(weeks)} {unit} {'ahead' if weeks > 0 else 'behind'}"


def skill_table(conn: sqlite3.Connection, curriculum: dict) -> list[dict]:
    """Every tracked skill with its first rating, latest rating and target."""
    rows = []
    for skill in curriculum["skills"]:
        ratings = conn.execute(
            "SELECT level, rated_on FROM skill_ratings WHERE skill = ? ORDER BY rated_on, id",
            (skill["key"],),
        ).fetchall()
        rows.append({
            **skill,
            "first": ratings[0]["level"] if ratings else 0,
            "level": ratings[-1]["level"] if ratings else 0,
            "rated_on": ratings[-1]["rated_on"] if ratings else "",
        })
    return rows


def rate_skill(conn: sqlite3.Connection, curriculum: dict, key: str, level: int, day: dt.date, note: str = "") -> None:
    """Record a new self-rating (0-5) for a skill; old ratings are kept as history."""
    known = {s["key"] for s in curriculum["skills"]}
    if key not in known:
        raise ValueError(f"unknown skill '{key}'. Known skills: {', '.join(sorted(known))}")
    if level not in range(len(LEVELS)):
        raise ValueError("level must be a whole number from 0 to 5")
    conn.execute(
        "INSERT INTO skill_ratings (skill, level, rated_on, note) VALUES (?, ?, ?, ?)",
        (key, level, day.isoformat(), note),
    )
    conn.commit()
