"""Find forward-deployed-style roles on public company job boards and track your applications.

Only official, public, no-login job-board APIs are used. Greenhouse, Lever and Ashby
publish them so companies can show their openings anywhere. LinkedIn, Naukri, Bayt
and similar sites are NOT scraped (their terms forbid it); for those the coach builds
search links that you open yourself (`fde jobs links`).
"""

import datetime as dt
import html
import json
import re
import sqlite3
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from .store import set_setting

USER_AGENT = "fde-coach/1.0 (personal job tracker)"
STATUSES = ["new", "shortlisted", "applied", "screening", "interviewing", "offer", "rejected", "withdrawn", "skipped"]
IN_PROGRESS = ["applied", "screening", "interviewing", "offer"]
CLOSED = ["rejected", "withdrawn", "skipped"]
TIER_ORDER = {"A": 0, "B": 1, "C": 2}

LIST_URLS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
    "lever": "https://api.lever.co/v0/postings/{slug}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{slug}",
}
GREENHOUSE_JOB_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{job_id}"

# Lever reports 2-letter country codes; spell out the ones the region filters look for.
COUNTRIES = {
    "IN": "India", "US": "United States", "GB": "United Kingdom", "AE": "United Arab Emirates",
    "SG": "Singapore", "IE": "Ireland", "NL": "Netherlands", "DE": "Germany", "FR": "France",
    "ES": "Spain", "PT": "Portugal", "SE": "Sweden", "DK": "Denmark", "FI": "Finland",
    "PL": "Poland", "IT": "Italy", "BE": "Belgium", "AT": "Austria", "CZ": "Czechia",
    "CH": "Switzerland", "SA": "Saudi Arabia", "QA": "Qatar", "CA": "Canada", "AU": "Australia",
    "JP": "Japan", "KR": "South Korea",
}


@dataclass
class Posting:
    """One job ad, normalised from any of the three job-board formats."""

    key: str
    company: str
    title: str
    location: str
    url: str
    remote: bool = False
    description: str = ""
    posted_on: str = ""
    tier: str = ""
    regions: list[str] = field(default_factory=list)


def get_json(url: str, timeout: int = 30):
    """Download and decode a JSON document."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def html_to_text(raw: str) -> str:
    """Turn job-board HTML into readable plain text (Greenhouse escapes its HTML twice)."""
    text = html.unescape(html.unescape(raw or ""))
    text = re.sub(r"<\s*(br|/p|/li|/h\d|/div|/ul)\b[^>]*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t\r\f\v\xa0]+", " ", text)
    return re.sub(r"\s*\n\s*", "\n", text).strip()


def _clean(value) -> str:
    return " ".join(str(value or "").split())


def _join_places(places: list[str]) -> str:
    return "; ".join(dict.fromkeys(p.strip() for p in places if p and p.strip()))


def parse_greenhouse(company: str, slug: str, data: dict) -> list[Posting]:
    """Greenhouse: {"jobs": [{id, title, location: {name}, absolute_url, content?, ...}]}."""
    postings = []
    for job in data.get("jobs", []):
        location = (job.get("location") or {}).get("name") or ""
        postings.append(Posting(
            key=f"greenhouse:{slug}:{job['id']}",
            company=company,
            title=_clean(job.get("title")),
            location=location,
            url=job.get("absolute_url") or "",
            remote="remote" in location.lower(),
            description=html_to_text(job.get("content", "")),
            posted_on=(job.get("first_published") or job.get("updated_at") or "")[:10],
        ))
    return postings


def parse_lever(company: str, slug: str, data: list) -> list[Posting]:
    """Lever: [{id, text, hostedUrl, categories: {location, allLocations}, country, ...}]."""
    postings = []
    for job in data if isinstance(data, list) else []:
        categories = job.get("categories") or {}
        places = categories.get("allLocations") or [categories.get("location") or ""]
        country = COUNTRIES.get(job.get("country") or "", job.get("country") or "")
        location = _join_places([*places, country])
        extra = "\n".join(html_to_text(item.get("content", "")) for item in job.get("lists") or [])
        created = job.get("createdAt")
        postings.append(Posting(
            key=f"lever:{slug}:{job['id']}",
            company=company,
            title=_clean(job.get("text")),
            location=location,
            url=job.get("hostedUrl") or "",
            remote=job.get("workplaceType") == "remote" or "remote" in location.lower(),
            description="\n".join(t for t in [job.get("descriptionPlain"), extra, job.get("additionalPlain")] if t),
            posted_on=dt.datetime.fromtimestamp(created / 1000, dt.UTC).date().isoformat() if created else "",
        ))
    return postings


def parse_ashby(company: str, slug: str, data: dict) -> list[Posting]:
    """Ashby: {"jobs": [{id, title, location, secondaryLocations, isRemote, jobUrl, ...}]}."""
    postings = []
    for job in data.get("jobs", []):
        if job.get("isListed") is False:
            continue
        places = [job.get("location") or ""] + [s.get("location") or "" for s in job.get("secondaryLocations") or []]
        country = ((job.get("address") or {}).get("postalAddress") or {}).get("addressCountry") or ""
        location = _join_places([*places, country])
        postings.append(Posting(
            key=f"ashby:{slug}:{job['id']}",
            company=company,
            title=_clean(job.get("title")),
            location=location,
            url=job.get("jobUrl") or "",
            remote=bool(job.get("isRemote")) or job.get("workplaceType") == "Remote" or "remote" in location.lower(),
            description=job.get("descriptionPlain") or "",
            posted_on=(job.get("publishedAt") or "")[:10],
        ))
    return postings


PARSERS = {"greenhouse": parse_greenhouse, "lever": parse_lever, "ashby": parse_ashby}


def tier_of(title: str, tiers: dict) -> str | None:
    """'A' (forward deployed), 'B' (AI-adjacent), 'C' (platform stepping stone), or None."""
    if re.search(tiers["exclude"], title, re.I):
        return None
    for tier in ("A", "B", "C"):
        if re.search(tiers[tier], title, re.I):
            return tier
    return None


def regions_of(location: str, patterns: dict) -> list[str]:
    """Names of the regions in config.toml that a location string mentions."""
    return [name for name, pattern in patterns.items() if re.search(pattern, location, re.I)]


def location_ok(regions: list[str], remote: bool, search: dict) -> bool:
    """True for roles you could take: in one of your regions, or remote and open to you."""
    if set(regions) & set(search["regions"]):
        return True
    if remote and search.get("remote_ok", True):
        return not regions or bool(set(regions) & set(search.get("remote_open_to", [])))
    return False


def classify(posting: Posting, config: dict) -> bool:
    """Fill in tier and regions; return True when the posting passes your filters."""
    posting.tier = tier_of(posting.title, config["tiers"]) or ""
    # When the location names no place (e.g. just "Remote"), the title often does: "FDE - UAE", "FDE, Federal".
    posting.regions = regions_of(posting.location, config["regions"]) or regions_of(posting.title, config["regions"])
    return bool(posting.tier) and location_ok(posting.regions, posting.remote, config["search"])


# Sponsorship is judged sentence by sentence, so "We do sponsor visas! We can't sponsor every
# role." still reads as yes, while "we're unable to offer visa sponsorship" reads as no.
_SENTENCES = re.compile(r"(?<=[.!?])\s+|\n+")
_NO_SPONSOR = re.compile(
    r"\b(unable|not able|cannot|can ?not|can't|won't|will not|do not|don't|does not|doesn't"
    r"|are not|aren't|is not|isn't)\b[^.]{0,40}\bsponsor"
    r"|\bno (visa |immigration )?sponsorship\b"
    r"|\bsponsorship (is |will )?not\b"
    r"|\bwithout (the need for |requiring )?(visa |employer )?sponsorship\b"
    r"|\bmust be an? (u\.?s\.?|united states) citizen\b"
    r"|\b(u\.?s\.?|united states) citizenship (is )?required\b"
    r"|\b(security clearance|ts/sci)\b",
    re.I,
)
_YES_SPONSOR = re.compile(
    r"\bwe (do |can |will |are able to )?sponsor\b[^.]{0,20}\bvisas?\b"
    r"|\b(visa|immigration) sponsorship (is )?(available|offered|provided|supported)\b"
    r"|\b(offer|provide)s? (visa|immigration) sponsorship\b",
    re.I,
)
_RELOCATION = re.compile(r"\brelocation (support|assistance|package|bonus)\b|\bhelp (you )?relocate\b", re.I)


def sponsorship_of(text: str) -> str:
    """Visa sponsorship hint from a job description: 'yes', 'no', 'reloc' or '?' (not stated)."""
    text = (text or "").replace("\u2019", "'")
    text = re.sub(r"\bU\.S\.(A\.)?", "US", text, flags=re.I)  # so "U.S." doesn't end a sentence
    yes = no = False
    for sentence in _SENTENCES.split(text):
        if _NO_SPONSOR.search(sentence):
            no = True
        elif _YES_SPONSOR.search(sentence):
            yes = True
    if yes:
        return "yes"
    if no:
        return "no"
    return "reloc" if _RELOCATION.search(text) else "?"


def fetch_company(company: dict, config: dict, known: set[str]) -> list[Posting]:
    """Download one company's job board and return only the postings that match your filters."""
    ats, slug = company["ats"], company["slug"]
    data = get_json(LIST_URLS[ats].format(slug=slug))
    matches = [p for p in PARSERS[ats](company["name"], slug, data) if classify(p, config)]
    if ats == "greenhouse":
        # The Greenhouse list has no descriptions, so download them only for roles not stored yet.
        for posting in matches:
            if posting.key not in known:
                job_id = posting.key.rsplit(":", 1)[1]
                try:
                    detail = get_json(GREENHOUSE_JOB_URL.format(slug=slug, job_id=job_id))
                    posting.description = html_to_text(detail.get("content", ""))
                except (OSError, ValueError):
                    pass  # keep the role even when its description cannot be downloaded
    return matches


@dataclass
class FetchResult:
    """Summary of one run over every job board."""

    boards: int
    matched: int
    new: list[Posting]
    errors: list[tuple[str, str]]


def fetch_all(conn: sqlite3.Connection, config: dict, today: dt.date, workers: int = 12) -> FetchResult:
    """Check every company in config.toml, store matching roles and return what is new."""
    # Roles stored without a description (e.g. a download failed last time) get another try.
    known = {row["key"] for row in conn.execute("SELECT key FROM jobs WHERE description != ''")}

    def work(company: dict):
        try:
            return company["name"], fetch_company(company, config, known), ""
        except Exception as exc:  # one broken board must never stop the daily run
            return company["name"], [], f"{type(exc).__name__}: {exc}"

    matched, new, errors = 0, [], []
    # Boards respond slowly, so several are downloaded at once; database writes stay on this thread.
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for name, postings, error in pool.map(work, config["companies"]):
            if error:
                errors.append((name, error))
            for posting in postings:
                matched += 1
                if save_posting(conn, posting, today):
                    new.append(posting)
    conn.commit()
    if len(errors) < len(config["companies"]):  # an offline run should not count as today's check
        set_setting(conn, "last_fetch", today.isoformat())
    return FetchResult(len(config["companies"]), matched, new, errors)


def region_tags(posting: Posting) -> str:
    """Comma-separated region names, with 'remote' first for remote roles."""
    return ",".join((["remote"] if posting.remote else []) + posting.regions)


def save_posting(conn: sqlite3.Connection, posting: Posting, today: dt.date) -> bool:
    """Insert a new posting or refresh one seen before. Returns True when it is new."""
    day = today.isoformat()
    # A description only fills a gap; SQLite evaluates both CASEs against the old (empty) value.
    updated = conn.execute(
        "UPDATE jobs SET last_seen = ?, title = ?, location = ?, regions = ?,"
        " sponsorship = CASE WHEN description = '' THEN ? ELSE sponsorship END,"
        " description = CASE WHEN description = '' THEN ? ELSE description END WHERE key = ?",
        (day, posting.title, posting.location, region_tags(posting),
         sponsorship_of(posting.description), posting.description, posting.key),
    )
    if updated.rowcount:
        return False
    conn.execute(
        "INSERT INTO jobs (key, company, title, location, url, tier, regions, sponsorship, description,"
        " posted_on, first_seen, last_seen) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (posting.key, posting.company, posting.title, posting.location, posting.url, posting.tier,
         region_tags(posting), sponsorship_of(posting.description), posting.description,
         posting.posted_on, day, day),
    )
    return True


def reach(row: sqlite3.Row, search: dict) -> int:
    """Sort rank by how reachable a role is: open remote first, then your regions in config order."""
    tags = [t for t in row["regions"].split(",") if t]
    named = [t for t in tags if t != "remote"]
    if "remote" in tags and (not named or set(named) & set(search.get("remote_open_to", []))):
        return 0
    order = search["regions"]
    return 1 + min((order.index(t) for t in named if t in order), default=len(order))


def list_jobs(conn: sqlite3.Connection, config: dict, today: dt.date, *, tier: str | None = None,
              status: str | None = None, region: str | None = None, show_all: bool = False,
              new_since: dt.date | None = None) -> list[sqlite3.Row]:
    """Stored jobs, best first: tier A before B before C, then the most reachable, then newest."""
    sql, params = "SELECT * FROM jobs WHERE 1 = 1", []
    if tier:
        sql += " AND tier = ?"
        params.append(tier.upper())
    if status:
        sql += " AND status = ?"
        params.append(status)
    elif not show_all:
        # Hide closed applications and ads that disappeared from their board (unless you applied).
        sql += f" AND status NOT IN ({','.join('?' * len(CLOSED))})"
        sql += f" AND (last_seen >= ? OR status IN ({','.join('?' * len(IN_PROGRESS))}))"
        params += [*CLOSED, (today - dt.timedelta(days=3)).isoformat(), *IN_PROGRESS]
    if new_since:
        sql += " AND first_seen >= ?"
        params.append(new_since.isoformat())
    rows = conn.execute(sql, params).fetchall()
    if region:
        rows = [r for r in rows if region in r["regions"].split(",")]
    return sorted(rows, key=lambda r: (TIER_ORDER.get(r["tier"], 3), reach(r, config["search"]),
                                       -dt.date.fromisoformat(r["first_seen"]).toordinal(), -r["id"]))


def get_job(conn: sqlite3.Connection, job_id: int) -> sqlite3.Row:
    """One stored job by its number (the # shown in lists)."""
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        raise LookupError(f"no job #{job_id} (see: fde jobs list)")
    return row


def set_status(conn: sqlite3.Connection, job_id: int, status: str, today: dt.date, note: str = "") -> None:
    """Move a job through your pipeline (new -> shortlisted -> applied -> ...); history is kept."""
    if status not in STATUSES:
        raise ValueError(f"status must be one of: {', '.join(STATUSES)}")
    get_job(conn, job_id)
    stamp = f"{today.isoformat()} {status}" + (f": {note}" if note else "")
    conn.execute(
        "UPDATE jobs SET status = ?, status_on = ?, notes = trim(notes || char(10) || ?) WHERE id = ?",
        (status, today.isoformat(), stamp, job_id),
    )
    conn.execute(
        "INSERT INTO job_events (job_id, status, on_day, note) VALUES (?, ?, ?, ?)",
        (job_id, status, today.isoformat(), note),
    )
    conn.commit()


def add_manual(conn: sqlite3.Connection, config: dict, company: str, title: str, url: str,
               location: str, today: dt.date) -> int:
    """Track a role you found yourself (LinkedIn, a referral, ...). It starts as 'shortlisted'."""
    if urllib.parse.urlparse(url).scheme not in ("http", "https"):
        raise ValueError("url must start with http:// or https://")
    posting = Posting(key=f"manual:{url}", company=_clean(company), title=_clean(title),
                      location=location, url=url, remote="remote" in location.lower())
    posting.tier = tier_of(posting.title, config["tiers"]) or "?"
    posting.regions = regions_of(location, config["regions"]) or regions_of(posting.title, config["regions"])
    if not save_posting(conn, posting, today):
        raise ValueError("that job is already in your list")
    job_id = conn.execute("SELECT id FROM jobs WHERE key = ?", (posting.key,)).fetchone()["id"]
    set_status(conn, job_id, "shortlisted", today, "added by hand")
    return job_id


def follow_ups(conn: sqlite3.Connection, today: dt.date, after_days: int = 7) -> list[sqlite3.Row]:
    """Applications with no update for `after_days` days: time for a polite follow-up."""
    cutoff = (today - dt.timedelta(days=after_days)).isoformat()
    return conn.execute(
        "SELECT * FROM jobs WHERE status IN ('applied', 'screening', 'interviewing') AND status_on <= ?"
        " ORDER BY status_on",
        (cutoff,),
    ).fetchall()


def pipeline_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """How many stored jobs are in each status."""
    counts = dict.fromkeys(STATUSES, 0)
    for row in conn.execute("SELECT status, COUNT(*) AS n FROM jobs GROUP BY status"):
        counts[row["status"]] = row["n"]
    return counts


def applications_between(conn: sqlite3.Connection, first: dt.date, last: dt.date) -> int:
    """Number of jobs you marked 'applied' between two days (inclusive)."""
    return conn.execute(
        "SELECT COUNT(DISTINCT job_id) AS n FROM job_events WHERE status = 'applied' AND on_day BETWEEN ? AND ?",
        (first.isoformat(), last.isoformat()),
    ).fetchone()["n"]


def skill_demand(conn: sqlite3.Connection, keywords: dict, since: dt.date,
                 tiers: tuple[str, ...] = ("A", "B")) -> tuple[int, list[tuple[str, int]]]:
    """How many recent matching job ads mention each skill. Returns (ads_checked, [(skill, count)])."""
    rows = conn.execute(
        f"SELECT title, description FROM jobs WHERE tier IN ({','.join('?' * len(tiers))})"
        " AND last_seen >= ? AND description != ''",
        (*tiers, since.isoformat()),
    ).fetchall()
    texts = [f"{r['title']}\n{r['description']}" for r in rows]
    counts = [(name, sum(1 for t in texts if re.search(pattern, t, re.I))) for name, pattern in keywords.items()]
    return len(texts), sorted(counts, key=lambda kv: kv[1], reverse=True)


def search_links(config: dict) -> list[tuple[str, str]]:
    """Ready-made searches for sites you browse yourself (LinkedIn and other job boards)."""
    linkedin = config["linkedin"]
    links = []
    for place in linkedin["locations"]:
        for query in linkedin["queries"]:
            params = {"keywords": query, "location": place["name"], "f_TPR": linkedin["posted_within"]}
            if place.get("remote"):
                params["f_WT"] = "2"
            links.append((f"LinkedIn | {place['label']} | {query}",
                          "https://www.linkedin.com/jobs/search/?" + urllib.parse.urlencode(params)))
    links += [(link["label"], link["url"]) for link in config.get("links", [])]
    return links
