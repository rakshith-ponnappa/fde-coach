"""Command line for the coach. Start with:  python3 -m fde_coach today"""

import argparse
import datetime as dt
import sqlite3
import sys
import textwrap
from dataclasses import dataclass

from . import jobs, learning, report, store


@dataclass
class Ctx:
    """Things every command needs."""

    conn: sqlite3.Connection
    curriculum: dict
    config: dict
    today: dt.date


def _short(text, width: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= width else text[: width - 1] + "…"


def _wrap(text: str, first: str, rest: str = "    ") -> str:
    return textwrap.fill(" ".join(text.split()), width=100, initial_indent=first, subsequent_indent=rest)


def print_jobs(rows) -> None:
    """One line per job: number, tier, company, title, location, visa hint, status."""
    if not rows:
        print("  (none)")
    for r in rows:
        print(f"  #{r['id']:<5} {r['tier']}  {_short(r['company'], 15):15}  {_short(r['title'], 50):50}  "
              f"{_short(r['location'], 26):26}  visa:{r['sponsorship']:<5}  {r['status']}")


def print_week(week: dict, phase: dict) -> None:
    """Goals, resources and deliverable for one plan week."""
    print(f"WEEK {week['n']}: {week['title']}   (phase {phase['id']}: {phase['name']})")
    print("Goals:")
    for goal in week["goals"]:
        print(_wrap(goal, "  - "))
    print("Resources:")
    for res in week["resources"]:
        print(f"  - {res['name']}\n      {res['url']}")
    print(_wrap(week["deliverable"], "Deliverable (when finished run `fde week done`): ", "  "))


def print_fetch(result: jobs.FetchResult) -> None:
    """Summary line for a job-board check, plus any boards that failed."""
    ok = result.boards - len(result.errors)
    print(f"Checked {ok}/{result.boards} job boards: {result.matched} roles match your filters, {len(result.new)} new.")
    for name, error in result.errors[:5]:
        print(f"  ! {name}: {_short(error, 90)}")
    if len(result.errors) > 5:
        print(f"  ! ...and {len(result.errors) - 5} more boards failed (offline?)")


def ensure_started(ctx: Ctx) -> dt.date:
    """Return the plan start date, starting the plan today on the very first run."""
    start = learning.start_date(ctx.conn)
    if start is None:
        learning.begin(ctx.conn, ctx.curriculum, ctx.today)
        print(f"Welcome! Your plan starts today ({ctx.today}). To change it: fde init --start YYYY-MM-DD\n")
        start = ctx.today
    return start


def cmd_today(args, ctx: Ctx) -> int:
    start = ensure_started(ctx)
    if not args.offline and store.get_setting(ctx.conn, "last_fetch") != ctx.today.isoformat():
        print("Checking job boards (once a day, takes about a minute)...")
        print_fetch(jobs.fetch_all(ctx.conn, ctx.config, ctx.today))
        print()

    done = learning.done_weeks(ctx.conn)
    week = learning.current_week(ctx.curriculum, done)
    week_start = learning.calendar_week_start(start, ctx.today)
    print(f"FDE COACH | {ctx.today:%a %d %b %Y} | day {learning.plan_day(start, ctx.today)} of your plan")
    if week is None:
        print("Every week of the plan is done. Keep logging and review your progress with: fde report")
        return 0
    phase = learning.phase_for(ctx.curriculum, week)
    print(f"Pace: {learning.describe_pace(learning.pace(done, start, ctx.today))} | "
          f"streak {learning.streak(ctx.conn, ctx.today)} days | "
          f"this plan-week {learning.hours_between(ctx.conn, week_start, ctx.today):.1f}/{learning.WEEKLY_TARGET_HOURS} h | "
          f"total {learning.total_hours(ctx.conn):.0f} h | weeks done {len(done)}/{len(ctx.curriculum['weeks'])}")
    print()
    print_week(week, phase)
    print()
    print("TODAY'S 4-HOUR SESSION")
    session = ctx.curriculum["daily"]["sunday" if ctx.today.weekday() == 6 else "default"]
    for line in session:
        print("  " + line.format(practice=phase["practice"]))
    print()

    applied = jobs.applications_between(ctx.conn, week_start, ctx.today)
    print(_wrap(phase["job_focus"], "JOB SEARCH: ", "  "))
    print(f"  Applications this plan-week: {applied}/{phase['apply_per_week']}")
    fresh = [r for r in jobs.list_jobs(ctx.conn, ctx.config, ctx.today, new_since=ctx.today - dt.timedelta(days=1))
             if r["tier"] in phase["apply_tiers"]]
    print(f"  New since yesterday in tiers {'/'.join(phase['apply_tiers'])}: {len(fresh)}")
    print_jobs(fresh[:8])
    due = jobs.follow_ups(ctx.conn, ctx.today)
    if due:
        print("  Follow-ups due (no update for 7+ days):")
        print_jobs(due[:5])
    print("  More: fde jobs list | fde jobs show ID | fde jobs apply ID | fde jobs links")
    return 0


def cmd_init(args, ctx: Ctx) -> int:
    day = args.start or ctx.today
    learning.begin(ctx.conn, ctx.curriculum, day)
    print(f"Plan start date set to {day}. Run: fde today")
    return 0


def cmd_log(args, ctx: Ctx) -> int:
    day = args.date or ctx.today
    week = learning.current_week(ctx.curriculum, learning.done_weeks(ctx.conn))
    learning.log_study(ctx.conn, day, args.hours, args.note, week["n"] if week else None)
    start = learning.start_date(ctx.conn) or day
    week_hours = learning.hours_between(ctx.conn, learning.calendar_week_start(start, ctx.today), ctx.today)
    print(f"Logged {args.hours:g} h on {day}. This plan-week: {week_hours:.1f}/{learning.WEEKLY_TARGET_HOURS} h. "
          f"Streak: {learning.streak(ctx.conn, ctx.today)} days.")
    return 0


def cmd_week(args, ctx: Ctx) -> int:
    done = learning.done_weeks(ctx.conn)
    if args.number is not None:
        week = learning.find_week(ctx.curriculum, args.number)
    else:
        week = learning.current_week(ctx.curriculum, done)
        if week is None:
            print("Every week is already done.")
            return 0
    if args.action == "show":
        print_week(week, learning.phase_for(ctx.curriculum, week))
        return 0
    learning.mark_week_done(ctx.conn, week["n"], ctx.today, args.note)
    print(f"Week {week['n']} done: {week['title']}. Nice work.")
    upcoming = learning.current_week(ctx.curriculum, learning.done_weeks(ctx.conn))
    if upcoming:
        print(f"Next: week {upcoming['n']} - {upcoming['title']}  (details: fde week show)")
    print("Also update your skill ratings if they changed: fde skills set SKILL LEVEL")
    return 0


def cmd_plan(args, ctx: Ctx) -> int:
    done = learning.done_weeks(ctx.conn)
    current = learning.current_week(ctx.curriculum, done)
    for phase in ctx.curriculum["phases"]:
        print(f"\nPHASE {phase['id']}: {phase['name']} (weeks {phase['weeks']})")
        print(_wrap(phase["goal"], "  Goal: ", "        "))
        for week in (w for w in ctx.curriculum["weeks"] if w["phase"] == phase["id"]):
            mark = "x" if week["n"] in done else (">" if current and week["n"] == current["n"] else " ")
            print(f"  [{mark}] W{week['n']:02d} {week['title']}")
    print("\n[x] done  [>] current week. Details for any week: fde week show N")
    return 0


def cmd_skills(args, ctx: Ctx) -> int:
    if args.action == "set":
        if args.skill is None or args.level is None:
            raise ValueError("usage: fde skills set SKILL LEVEL   e.g. fde skills set python 2")
        learning.rate_skill(ctx.conn, ctx.curriculum, args.skill, args.level, ctx.today, args.note)
        print(f"{args.skill} is now {args.level}/5 ({learning.LEVELS[args.level]}).")
        return 0
    print("Levels: " + ", ".join(f"{i} {name}" for i, name in enumerate(learning.LEVELS)))
    for s in learning.skill_table(ctx.conn, ctx.curriculum):
        bar = "#" * s["level"] + "." * max(s["target"] - s["level"], 0)
        change = s["level"] - s["first"]
        print(f"  {s['key']:18} {bar:6} {s['level']}/5  target {s['target']}  "
              f"{f'(+{change} since start)' if change > 0 else '':16} {s['name']}")
    print("Update after each week: fde skills set KEY LEVEL --note \"why\"")
    return 0


def cmd_jobs_fetch(args, ctx: Ctx) -> int:
    print("Checking job boards...")
    result = jobs.fetch_all(ctx.conn, ctx.config, ctx.today)
    print_fetch(result)
    if result.new:
        print("New roles:")
        new_keys = {p.key for p in result.new}
        print_jobs([r for r in jobs.list_jobs(ctx.conn, ctx.config, ctx.today, new_since=ctx.today)
                    if r["key"] in new_keys][:25])
    return 0


def cmd_jobs_list(args, ctx: Ctx) -> int:
    new_since = ctx.today - dt.timedelta(days=args.new - 1) if args.new else None
    rows = jobs.list_jobs(ctx.conn, ctx.config, ctx.today, tier=args.tier, status=args.status,
                          region=args.region, show_all=args.all, new_since=new_since)
    print(f"{len(rows)} jobs" + (f", showing the first {args.limit}" if len(rows) > args.limit else ""))
    print_jobs(rows[: args.limit])
    print("Tier A = forward deployed, B = AI-adjacent, C = platform stepping stone. Details: fde jobs show ID")
    return 0


def cmd_jobs_show(args, ctx: Ctx) -> int:
    r = jobs.get_job(ctx.conn, args.id)
    print(f"#{r['id']} [{r['tier']}] {r['company']} - {r['title']}")
    print(f"Location: {r['location'] or '-'}  |  regions: {r['regions'] or '-'}  |  visa sponsorship: {r['sponsorship']}")
    print(f"Posted: {r['posted_on'] or '?'}  |  first seen: {r['first_seen']}  |  status: {r['status']}")
    print(f"Link: {r['url']}")
    if r["notes"]:
        print("History:\n" + textwrap.indent(r["notes"], "  "))
    if r["description"]:
        text = r["description"] if args.full else r["description"][:2500]
        print("\n" + text + ("\n... (see the full ad with --full)" if len(r["description"]) > len(text) else ""))
    return 0


def cmd_jobs_add(args, ctx: Ctx) -> int:
    job_id = jobs.add_manual(ctx.conn, ctx.config, args.company, args.title, args.url, args.location, ctx.today)
    print(f"Added as #{job_id} (shortlisted). When you apply: fde jobs apply {job_id}")
    return 0


def cmd_jobs_status(args, ctx: Ctx) -> int:
    status = "applied" if args.jobs_command == "apply" else args.status
    jobs.set_status(ctx.conn, args.id, status, ctx.today, args.note)
    print(f"#{args.id} is now '{status}'.")
    return 0


def cmd_jobs_skills(args, ctx: Ctx) -> int:
    since = ctx.today - dt.timedelta(days=args.days - 1)
    checked, demand = jobs.skill_demand(ctx.conn, ctx.config["skill_keywords"], since)
    if not checked:
        print("No job descriptions stored yet. Run: fde jobs fetch")
        return 0
    print(f"What {checked} tier A/B job ads seen in the last {args.days} days ask for:")
    for name, n in demand:
        pct = 100 * n // checked
        print(f"  {name:28} {'#' * (pct // 4):25} {pct:3}%  ({n})")
    return 0


def cmd_jobs_links(args, ctx: Ctx) -> int:
    print("Open these yourself (sites like LinkedIn forbid automated scraping):")
    for label, url in jobs.search_links(ctx.config):
        print(f"\n  {label}\n  {url}")
    return 0


def cmd_report(args, ctx: Ctx) -> int:
    text = report.build(ctx.conn, ctx.curriculum, ctx.config, ctx.today)
    if not args.write:
        print(text)
        return 0
    folder = store.home() / "reports"
    folder.mkdir(exist_ok=True)
    path = folder / f"{ctx.today.isoformat()}.md"
    path.write_text(text, encoding="utf-8")
    (store.home() / "PROGRESS.md").write_text(text, encoding="utf-8")
    print(f"Saved {path} and PROGRESS.md")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """All commands and their options."""
    parser = argparse.ArgumentParser(prog="fde", description="Your daily Forward Deployed Engineer coach.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("today", help="what to do today (also checks job boards once a day)")
    p.add_argument("--offline", action="store_true", help="skip the daily job-board check")
    p.set_defaults(func=cmd_today)

    p = sub.add_parser("init", help="set or change the day your plan started")
    p.add_argument("--start", type=dt.date.fromisoformat, help="YYYY-MM-DD (default: today)")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("log", help='log study time, e.g. fde log 4 "CS50P lecture 1"')
    p.add_argument("hours", type=float)
    p.add_argument("note", nargs="?", default="")
    p.add_argument("--date", type=dt.date.fromisoformat, help="log for another day (YYYY-MM-DD)")
    p.set_defaults(func=cmd_log)

    p = sub.add_parser("week", help="show a week, or mark the current week done")
    p.add_argument("action", choices=["show", "done"])
    p.add_argument("number", nargs="?", type=int, help="week number (default: your current week)")
    p.add_argument("--note", default="", help="what you shipped (saved with the week)")
    p.set_defaults(func=cmd_week)

    sub.add_parser("plan", help="the whole week-by-week plan with your progress").set_defaults(func=cmd_plan)

    p = sub.add_parser("skills", help="show skill ratings, or rate one: fde skills set python 2")
    p.add_argument("action", nargs="?", choices=["show", "set"], default="show")
    p.add_argument("skill", nargs="?")
    p.add_argument("level", nargs="?", type=int)
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_skills)

    p = sub.add_parser("jobs", help="find and track jobs")
    jsub = p.add_subparsers(dest="jobs_command", required=True)
    jsub.add_parser("fetch", help="check all company job boards now").set_defaults(func=cmd_jobs_fetch)

    q = jsub.add_parser("list", help="stored jobs, best matches first")
    q.add_argument("--tier", choices=["A", "B", "C", "a", "b", "c"])
    q.add_argument("--status", choices=jobs.STATUSES)
    q.add_argument("--region", help="e.g. remote, uae, singapore, uk, eu, us")
    q.add_argument("--new", type=int, metavar="DAYS", help="only roles first seen in the last DAYS days")
    q.add_argument("--all", action="store_true", help="include closed and skipped jobs")
    q.add_argument("--limit", type=int, default=40)
    q.set_defaults(func=cmd_jobs_list)

    q = jsub.add_parser("show", help="details and link for one job")
    q.add_argument("id", type=int)
    q.add_argument("--full", action="store_true", help="print the whole job description")
    q.set_defaults(func=cmd_jobs_show)

    q = jsub.add_parser("add", help="track a job you found yourself (LinkedIn, referral, ...)")
    q.add_argument("company")
    q.add_argument("title")
    q.add_argument("url")
    q.add_argument("--location", default="")
    q.set_defaults(func=cmd_jobs_add)

    q = jsub.add_parser("apply", help="mark a job as applied")
    q.add_argument("id", type=int)
    q.add_argument("--note", default="", help="e.g. 'referral from a friend', 'tailored CV v3'")
    q.set_defaults(func=cmd_jobs_status)

    q = jsub.add_parser("status", help="move a job through your pipeline")
    q.add_argument("id", type=int)
    q.add_argument("status", choices=jobs.STATUSES)
    q.add_argument("--note", default="")
    q.set_defaults(func=cmd_jobs_status)

    q = jsub.add_parser("skills", help="which skills recent FDE-style job ads ask for")
    q.add_argument("--days", type=int, default=30)
    q.set_defaults(func=cmd_jobs_skills)

    jsub.add_parser("links", help="LinkedIn and job-site searches to open yourself").set_defaults(func=cmd_jobs_links)

    p = sub.add_parser("report", help="progress report (add --write to save reports/DATE.md + PROGRESS.md)")
    p.add_argument("--write", action="store_true")
    p.set_defaults(func=cmd_report)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for `python3 -m fde_coach` and the ./fde script."""
    args = build_parser().parse_args(argv)
    ctx = Ctx(store.connect(), store.load_toml("curriculum.toml"), store.load_toml("config.toml"), dt.date.today())
    try:
        if args.command != "init":
            ensure_started(ctx)
        return args.func(args, ctx)
    except (ValueError, LookupError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    finally:
        ctx.conn.close()
