"""Markdown progress report: study time, skills, job pipeline and what job ads are asking for."""

import datetime as dt
import sqlite3

from . import jobs, learning


def _cell(value) -> str:
    """Make a value safe for a Markdown table cell."""
    return " ".join(str(value).split()).replace("|", "/")


def _bar(level: int, target: int) -> str:
    return "#" * level + "." * max(target - level, 0)


def build(conn: sqlite3.Connection, curriculum: dict, config: dict, today: dt.date) -> str:
    """Build the full report as Markdown text."""
    start = learning.start_date(conn) or today
    done = learning.done_weeks(conn)
    week = learning.current_week(curriculum, done)
    phase = learning.phase_for(curriculum, week) if week else None
    week_start = learning.calendar_week_start(start, today)
    total_weeks = len(curriculum["weeks"])
    phase_text = f"{phase['id']}: {phase['name']}" if phase else "plan complete"
    week_text = f"{week['n']}: {week['title']}" if week else "-"

    out = [f"# FDE progress report - {today.isoformat()}", "", "## Snapshot", "", "| Item | Value |", "|---|---|"]
    out += [
        f"| Plan day | {learning.plan_day(start, today)} (started {start.isoformat()}) |",
        f"| Phase | {_cell(phase_text)} |",
        f"| Current week | {_cell(week_text)} |",
        f"| Weeks done | {len(done)}/{total_weeks} ({100 * len(done) // total_weeks}%) |",
        f"| Pace | {learning.describe_pace(learning.pace(done, start, today))} |",
        f"| Streak | {learning.streak(conn, today)} days |",
        f"| Hours this plan-week | {learning.hours_between(conn, week_start, today):.1f} / {learning.WEEKLY_TARGET_HOURS} |",
        f"| Hours last 30 days | {learning.hours_between(conn, today - dt.timedelta(days=29), today):.1f} |",
        f"| Total hours | {learning.total_hours(conn):.1f} |",
        "",
    ]

    out += ["## Study log (last 7 days)", ""]
    log = learning.recent_log(conn, today - dt.timedelta(days=6))
    if log:
        out += ["| Day | Hours | Week | Note |", "|---|---|---|---|"]
        out += [f"| {r['day']} | {r['hours']:.1f} | {r['week'] or '-'} | {_cell(r['note'])} |" for r in log]
    else:
        out.append("Nothing logged yet. After each session run: `fde log 4 \"what I did\"`")
    out.append("")

    out += ["## Skills (0 none, 1 aware, 2 guided, 3 independent, 4 production, 5 expert)", "",
            "| Skill | Start | Now | Target | Progress |", "|---|---|---|---|---|"]
    for s in learning.skill_table(conn, curriculum):
        out.append(f"| {_cell(s['name'])} | {s['first']} | {s['level']} | {s['target']} | `{_bar(s['level'], s['target'])}` |")
    out.append("")

    counts = jobs.pipeline_counts(conn)
    applied = jobs.applications_between(conn, week_start, today)
    out += ["## Job search", ""]
    if phase:
        out.append(f"Focus for this phase: {phase['job_focus']}  ")
        out.append(f"Applications this plan-week: **{applied} / {phase['apply_per_week']}**")
        out.append("")
    out.append("Pipeline: " + ", ".join(f"{status} {n}" for status, n in counts.items()))
    out.append("")
    fresh = jobs.list_jobs(conn, config, today, new_since=today - dt.timedelta(days=6))
    out += [f"New matching roles in the last 7 days: **{len(fresh)}** (top 10)", ""]
    if fresh:
        out += ["| # | Tier | Company | Role | Location | Visa |", "|---|---|---|---|---|---|"]
        out += [f"| {r['id']} | {r['tier']} | {_cell(r['company'])} | [{_cell(r['title'])}]({r['url']}) "
                f"| {_cell(r['location'])[:40]} | {r['sponsorship']} |" for r in fresh[:10]]
        out.append("")
    due = jobs.follow_ups(conn, today)
    if due:
        out += ["Follow-ups due (no update for 7+ days):", ""]
        out += [f"- #{r['id']} {_cell(r['company'])} - {_cell(r['title'])} ({r['status']} since {r['status_on']})" for r in due]
        out.append("")

    checked, demand = jobs.skill_demand(conn, config["skill_keywords"], today - dt.timedelta(days=29))
    out += ["## Market pulse (tier A/B ads seen in the last 30 days)", ""]
    if checked:
        out += [f"Out of {checked} job ads with descriptions:", "", "| Skill | Ads | Share |", "|---|---|---|"]
        out += [f"| {_cell(name)} | {n} | {100 * n // checked}% |" for name, n in demand[:15]]
    else:
        out.append("No job descriptions yet. Run `fde jobs fetch`.")
    out.append("")

    out += ["## Next up", ""]
    if week:
        out += [f"Week {week['n']}: **{week['title']}**", ""]
        out += [f"- {_cell(goal)}" for goal in week["goals"]]
        out += ["", f"Deliverable: {week['deliverable']}"]
    else:
        out.append("Every week of the plan is done.")
    return "\n".join(out) + "\n"
