#!/usr/bin/env python3
"""moo-export-data.py — generate halo data/swarm.json from live host state.

Live exporter (2026-08-23-live-exporter): five sources feed seven dashboard
sections — gh api (issues/PRs), openclaw.sqlite cron_jobs (read-only,
whitelisted projection), handoff-log tails (pipeline), session-file mtimes
(agents, metadata only) and the existing projects filesystem scan.

Failure honesty: each source is isolated behind run_source(); a failure
records source_errors[<section>] and keeps that section's last-good values
(the input file IS the cache), while every other section still refreshes.
Partial success exits 0; exit 1 is reserved for missing/unreadable input,
unwritable output, and guard violations.

Stdlib only by design (host has no pip). Never writes outside data/swarm.json
(atomic_write's transient sibling tmp file is consumed by os.replace and is
part of writing data/swarm.json itself).
"""
import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HALO_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = HALO_DIR / "data" / "swarm.json"

# ── CONFIG ────────────────────────────────────────────────────────────────
DEFAULT_OPENCLAW_DB = "/home/lex/.openclaw/state/openclaw.sqlite"
DEFAULT_AGENTS_DIR = "/home/lex/.openclaw/agents"
PROJECTS_DIR = Path("/home/lex/.openclaw/workspaces/_align-rail_/projects")
DEFAULT_REPO_DENYLIST = ".github"

ORG = "moo-swarm"
GH_TIMEOUT = 30
ISSUE_CAP = 50
PR_CAP = 50
STALE_MINUTES_DASH = 120  # dashboard-side staleness threshold (AC12)

AGENT_ALIASES = {
    "lex": "moo",
    "cmok": "cmok",
    "bagnik": "bagnik",
    "veles": "veles",
    "zlydni": "zlydni",
    "mokash": "mokash",
}

# Seed roster meta (emoji/role match the seed swarm.json); unmapped agent
# dirs get NEUTRAL_META (spec Q1 default: show all discovered, neutral meta).
AGENT_META = {
    "moo": {"emoji": "🐂", "role": "Orchestrator"},
    "veles": {"emoji": "🐍", "role": "Research"},
    "cmok": {"emoji": "🐉", "role": "Build"},
    "bagnik": {"emoji": "🚨", "role": "QA"},
    "zlydni": {"emoji": "🏦️", "role": "Commit"},
    "mokash": {"emoji": "🧶", "role": "Docs"},
}
NEUTRAL_META = {"emoji": "🤖", "role": "agent"}

# Static worker→role map for pipeline entries (D2). Workers seen in logs but
# absent here (coordinator, skills, …) produce no pipeline entry.
WORKER_ROLES = {
    "moo": "Route",
    "veles": "Research",
    "cmok": "Build",
    "bagnik": "QA",
    "mokash": "Docs",
    "zlydni": "Commit",
    "yaga": "Debug",
}

# Whitelist enforced as SELECT projection, not post-filter (DR-B): future
# schema drift cannot leak payload columns even if code changes elsewhere.
CRON_COLUMNS = (
    "name",
    "enabled",
    "schedule_kind",
    "schedule_expr",
    "schedule_tz",
    "every_ms",
    "next_run_at_ms",
    "last_run_at_ms",
    "last_run_status",
    "consecutive_errors",
)

# Guard lists (AC3/AC15). FORBIDDEN_SUBSTRINGS greps the whole serialized
# output; bare "description"/"last_error" are intentionally excluded there
# (legit seed fields carry them) — they are covered by the cron key-whitelist
# test instead. TOKEN_RE catches classic token shapes only, to keep the guard
# from false-positiving on public GitHub content (a firing guard blocks ALL
# publishing).
FORBIDDEN_SUBSTRINGS = (
    "payload",
    "delivery_to",
    "delivery_channel",
    "session_key",
    "job_json",
    "state_json",
    "telegram:",
)
TOKEN_RE = re.compile(
    r"\b(?:ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{16,}\b"
    r"|\bsk-[A-Za-z0-9]{20,}\b"
)


def env_config() -> dict:
    """External paths via env with current defaults (AC18). Read once in main."""
    return {
        "db": Path(os.environ.get("HALO_OPENCLAW_DB", DEFAULT_OPENCLAW_DB)),
        "agents_dir": Path(os.environ.get("HALO_AGENTS_DIR", DEFAULT_AGENTS_DIR)),
        "projects_dir": Path(os.environ.get("HALO_PROJECTS_DIR", str(PROJECTS_DIR))),
        "denylist": tuple(
            s.strip()
            for s in os.environ.get("HALO_REPO_DENYLIST", DEFAULT_REPO_DENYLIST).split(",")
            if s.strip()
        ),
    }


# Module-level NOW_* kept for backward compat with anything importing them;
# main() computes its own run-local clock so repeated in-process runs are honest.
NOW = datetime.now(timezone.utc)
TODAY = NOW.strftime("%Y-%m-%d")
NOW_ISO = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_budget() -> dict:
    return {
        "tokens": 0,
        "cost": 0.0,
        "pricing_configured": False,
        "limit_tokens": 200000,
        "limit_cost": 0.60,
    }


def ms_to_iso(ms):
    """Epoch ms → ISO 8601 UTC Z string (AC2); None-safe."""
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


# ── GH LAYER ──────────────────────────────────────────────────────────────
def gh_api(path: str):
    """Single read-only gh api call → parsed JSON, or None on any failure."""
    try:
        result = subprocess.run(
            ["gh", "api", path],
            capture_output=True,
            text=True,
            timeout=GH_TIMEOUT,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def fetch_org_repos(denylist=DEFAULT_REPO_DENYLIST):
    """One paged org-repos call gives the scan list (AC1/D5).

    Raises when the listing fails so run_source records issues+prs errors
    together (failure class R).
    """
    payload = gh_api(f"orgs/{ORG}/repos?per_page=100")
    if not isinstance(payload, list):
        raise RuntimeError(f"gh api {ORG} repo listing failed")
    return [r["name"] for r in payload if isinstance(r, dict) and r.get("name") not in denylist]


def map_issue(repo: str, item: dict):
    """Pure issue mapper; excludes PR items (they carry a pull_request key)."""
    if not isinstance(item, dict) or item.get("pull_request") is not None:
        return None
    return {
        "project": repo,
        "number": item.get("number"),
        "title": item.get("title"),
        "labels": [lb.get("name") for lb in item.get("labels", []) if isinstance(lb, dict)],
        "created_at": item.get("created_at"),
        "url": item.get("html_url"),
    }


def map_pr(repo: str, item: dict):
    """Pure PR mapper; draft flag lives on the pulls endpoint."""
    if not isinstance(item, dict):
        return None
    author = item.get("user") or {}
    return {
        "project": repo,
        "number": item.get("number"),
        "title": item.get("title"),
        "author": author.get("login"),
        "status": "draft" if item.get("draft") else "open",
        "created_at": item.get("created_at"),
        "url": item.get("html_url"),
    }


def fetch_issues_and_prs(repos):
    """2N calls over the scanned repos → capped newest-first lists + counts.

    Any per-repo failure raises (class G): the section keeps last-good rather
    than publishing a partial fetch as fresh. Counts are pre-cap truth used by
    the projects source (AC6).
    """
    issues, prs, counts = [], [], {}
    for repo in repos:
        raw_issues = gh_api(f"repos/{ORG}/{repo}/issues?state=open&per_page=100")
        if raw_issues is None:
            raise RuntimeError(f"gh api open issues fetch failed for {repo}")
        open_issues = [
            mapped
            for item in raw_issues
            for mapped in (map_issue(repo, item),)
            if mapped is not None
        ]
        counts[repo] = len(open_issues)
        issues.extend(open_issues)

        raw_prs = gh_api(f"repos/{ORG}/{repo}/pulls?state=open&per_page=100")
        if raw_prs is None:
            raise RuntimeError(f"gh api open pulls fetch failed for {repo}")
        prs.extend(mapped for item in raw_prs if (mapped := map_pr(repo, item)))

    issues.sort(key=lambda i: i["created_at"] or "", reverse=True)
    prs.sort(key=lambda p: p["created_at"] or "", reverse=True)
    # Budget: 1 (org listing) + 2N calls/run; ≤ 40 ⇔ N ≤ 19 repos (AC19).
    return {"issues": issues[:ISSUE_CAP], "prs": prs[:PR_CAP], "counts": counts}


def fetch_issues(repo: str) -> int:
    """Legacy single-repo count helper. Superseded by fetch_issues_and_prs
    (kept so existing callers/tests keep working)."""
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/moo-swarm/{repo}", "--jq", ".open_issues_count"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip())
    except Exception:
        pass
    return 0


# ── CRON LAYER ────────────────────────────────────────────────────────────
def humanize_ms(ms) -> str:
    if ms is None:
        return "?"
    seconds = ms // 1000
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h"
    return f"{hours // 24}d"


def humanize_schedule(kind, expr, tz, every_ms) -> str:
    """schedule_expr (+tz) for cron-kind jobs, else every_ms rendered human."""
    if kind == "cron" and expr:
        return f"{expr} ({tz})" if tz else expr
    return f"every {humanize_ms(every_ms)}"


def extract_cron_jobs(db_path) -> list:
    """Read-only whitelisted cron export (AC2/D1).

    Opens the SQLite DB via mode=ro URI (writes blocked at engine level),
    selects ONLY CRON_COLUMNS as the projection, ORDER BY name. Missing or
    corrupt DB raises — run_source turns that into a cron_jobs error entry.
    """
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = con.execute(
            f"SELECT {','.join(CRON_COLUMNS)} FROM cron_jobs ORDER BY name"
        ).fetchall()
    finally:
        con.close()

    jobs = []
    for row in rows:
        job = dict(zip(CRON_COLUMNS, row))
        jobs.append(
            {
                "name": job["name"],
                "schedule_human": humanize_schedule(
                    job["schedule_kind"], job["schedule_expr"],
                    job["schedule_tz"], job["every_ms"],
                ),
                "schedule": (
                    job["schedule_expr"]
                    if job["schedule_kind"] == "cron" and job["schedule_expr"]
                    else job["every_ms"]
                ),
                "last_run": ms_to_iso(job["last_run_at_ms"]),
                "status": (
                    "disabled"
                    if not job["enabled"]
                    else ("ok" if job["last_run_status"] == "ok" else "fail")
                ),
                "next_run": ms_to_iso(job["next_run_at_ms"]),
                "consecutive_errors": job["consecutive_errors"] or 0,
            }
        )
    return jobs


# ── PIPELINE LAYER ────────────────────────────────────────────────────────
# Tolerant of both real kit forms:
#   ## HH:MM Worker → Coordinator [context] STATUS
#   ## HH:MM worker [context] progress
HEADER_RE = re.compile(
    r"^##\s+(?P<hhmm>\d{1,2}:\d{2})\s+(?P<worker>[A-Za-z][\w-]*)\s+"
    r"(?:.*?→\s*Coordinator\s+)?(?:\[(?P<context>[^\]]*)\]\s*)?(?P<tail>.*)$"
)


def parse_handoff_tail(path: Path):
    """Latest matching entry header line in a handoff log, or None.

    Malformed or unreadable logs are skipped without failing the run (class M).
    """
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    entry = None
    for line in lines:
        m = HEADER_RE.match(line.strip())
        if not m:
            continue
        tail = m.group("tail").strip()
        status_word = tail.strip("[]").split()[0] if tail else "progress"
        entry = {
            "hhmm": m.group("hhmm"),
            "worker": m.group("worker").lower(),
            "status_word": status_word.lower(),
        }
    return entry


def status_from_entry(status_word: str, age_days: int) -> str:
    """done/pass→pass, fail→fail, blocked→idle, recent progress→running;
    no activity in ≥30 d falls back to idle (AC4/D2)."""
    word = (status_word or "").lower()
    if age_days >= 30:
        return "idle"
    if word in ("done", "pass"):
        return "pass"
    if word == "fail":
        return "fail"
    if word == "blocked":
        return "idle"
    return "running"


def _feature_date(feature_dir: Path):
    parts = feature_dir.name.split("-")
    if len(parts) < 3:
        return None
    try:
        return datetime.strptime("-".join(parts[:3]), "%Y-%m-%d").date()
    except ValueError:
        return None


def extract_pipeline(projects_dir, now=None) -> list:
    """≤1 pipeline entry per known worker from handoff-log tails (AC4/D2)."""
    now = now or datetime.now(timezone.utc)
    latest = {}  # worker -> (entry_datetime, status_word)
    projects_path = Path(projects_dir)
    if not projects_path.is_dir():
        return []
    for proj_dir in sorted(projects_path.iterdir()):
        features = proj_dir / ".moo-swarm" / "features"
        if not proj_dir.is_dir() or not features.is_dir():
            continue
        for feature_dir in sorted(features.iterdir()):
            log_file = feature_dir / "handoff-log.md"
            if not log_file.is_file():
                continue
            feat_date = _feature_date(feature_dir)
            if feat_date is None:
                continue
            entry = parse_handoff_tail(log_file)
            if entry is None or entry["worker"] not in WORKER_ROLES:
                continue
            try:
                hh, mm = entry["hhmm"].split(":")
                stamp = datetime(
                    feat_date.year, feat_date.month, feat_date.day,
                    int(hh), int(mm), tzinfo=timezone.utc,
                )
            except ValueError:
                continue  # malformed HH:MM — skip silently (class M)
            if entry["worker"] not in latest or stamp > latest[entry["worker"]][0]:
                latest[entry["worker"]] = (stamp, entry["status_word"])

    entries = []
    for worker, role in WORKER_ROLES.items():
        if worker not in latest:
            continue
        stamp, status_word = latest[worker]
        age_days = (now - stamp).days
        meta = AGENT_META.get(worker, NEUTRAL_META)
        entries.append(
            {
                "agent": worker,
                "emoji": meta["emoji"],
                "role": role,
                "status": status_from_entry(status_word, age_days),
                "last_run": stamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        )
    return entries


# ── AGENTS LAYER ──────────────────────────────────────────────────────────
def status_from_age(minutes) -> str:
    """mtime-age only — no running/busy signal exists (D3 honest gap)."""
    if minutes is None:
        return "dormant"
    if minutes < 60:
        return "active"
    if minutes < 7 * 24 * 60:
        return "idle"
    return "dormant"


def extract_agents(agents_dir, now=None) -> list:
    """Per-agent metadata from session-file mtimes only (AC5/D3).

    Roster = discovered dirs ∪ AGENT_META knowledge; dirs without readable
    sessions are skipped silently. tokens_24h exports null (not derivable
    without parsing transcripts — honest gap).
    """
    now = now or datetime.now(timezone.utc)
    agents_path = Path(agents_dir)
    # Roster = discovered dirs ∪ seed knowledge (D3); unreadable session
    # trees are skipped silently rather than failing the run.
    discovered = {d.name for d in agents_path.iterdir() if d.is_dir()}
    names = sorted(discovered | set(AGENT_META))
    agents = []
    day_ago = now.timestamp() - 24 * 3600
    for name in names:
        sessions_dir = agents_path / name / "sessions"
        mtimes = []
        if sessions_dir.is_dir():
            try:
                mtimes = [
                    p.stat().st_mtime
                    for p in sessions_dir.iterdir()
                    if p.is_file()
                ]
            except OSError:
                mtimes = []
        meta = AGENT_META.get(name, NEUTRAL_META)
        last_active_iso = ms_to_iso(int(max(mtimes) * 1000)) if mtimes else None
        minutes = (now.timestamp() - max(mtimes)) / 60 if mtimes else None
        agents.append(
            {
                "name": name,
                "emoji": meta["emoji"],
                "role": meta["role"],
                "last_active": last_active_iso,
                "sessions_24h": sum(1 for m in mtimes if m > day_ago),
                "status": status_from_age(minutes),
                "tokens_24h": None,
                "budget_daily": _default_budget(),
            }
        )
    return agents


# ── SOURCE REGISTRY + ORCHESTRATION ───────────────────────────────────────
def sanitize_error(exc: Exception) -> str:
    """Make an exception message safe to publish (gate blocker 1).

    Applied AT CAPTURE inside run_source: whitespace collapsed, home prefix
    (/home/lex → ~) and remaining absolute-path runs redacted, truncated to
    ~200 chars.
    """
    msg = " ".join(str(exc).split())
    home = str(Path.home())
    if home and msg.startswith(home):
        msg = "~" + msg[len(home):]
    # absolute-path runs: /segment/segment… (≥2 segments), not right after ~
    msg = re.sub(r"(?<!~)(?<![\w])/([\w.\-]+(?:/[\w.\-]+)+)", "/…", msg)
    return msg[:200]


def _source_issues(data, cfg):
    repos = fetch_org_repos(cfg["denylist"])
    result = fetch_issues_and_prs(repos)
    cfg["issue_counts"] = result["counts"]
    cfg["pending_prs"] = result["prs"]
    return result["issues"]


def _source_prs(data, cfg):
    if "pending_prs" not in cfg:
        raise RuntimeError("prs unavailable: issues/prs fetch failed earlier this run")
    return cfg.pop("pending_prs")


def _source_projects(data, cfg):
    """Existing filesystem enrichment; open_issues from AC1 counts (AC6).

    Projects whose repo produced no count this run (fetch failed, or a
    local-only project) keep their previous value untouched.
    """
    counts = cfg.get("issue_counts", {})
    projects_path = Path(cfg["projects_dir"])
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for p in data.get("projects") or []:
        name = p.get("name")
        proj_path = projects_path / name if name else None

        specs = {"total": 0, "active": 0, "latest": None}
        if proj_path and proj_path.is_dir():
            specs = compute_specs(proj_path)
        p["specs"] = specs

        if specs["latest"]:
            p["last_updated"] = specs["latest"]
        else:
            p.setdefault("last_updated", today)

        if proj_path:
            p.setdefault("pipeline_owner_agent", infer_pipeline_owner(proj_path))

        budget = p.setdefault("budget_daily", {})
        budget.setdefault("tokens", 0)
        budget.setdefault("cost", 0.0)
        budget.setdefault("pricing_configured", False)
        budget.setdefault("limit_tokens", 200000)
        budget.setdefault("limit_cost", 0.60)

        if name in counts:
            p["open_issues"] = counts[name]
        else:
            p.setdefault("open_issues", 0)
    return data.get("projects") or []


def _source_pipeline(data, cfg):
    return extract_pipeline(cfg["projects_dir"])


def _source_cron(data, cfg):
    return extract_cron_jobs(cfg["db"])


def _source_agents(data, cfg):
    return extract_agents(cfg["agents_dir"])


# Ordered registry: issues+prs first because projects consumes their counts;
# fixed order keeps failure blast radius deterministic (§1.2 merge rule).
SOURCES = (
    ("issues", _source_issues),
    ("prs", _source_prs),
    ("projects", _source_projects),
    ("pipeline", _source_pipeline),
    ("cron_jobs", _source_cron),
    ("agents", _source_agents),
)


def run_source(key, fn, data, stamps, errors, now_iso, cfg) -> bool:
    """Fetch → stamp → error-catch isolation (AC10 structural shape).

    Success: replace section value + fresh stamp + clear any prior error.
    Failure: sanitized error into the map; section data AND its old stamp
    stay exactly as they were (last-good retained).
    """
    try:
        data[key] = fn(data, cfg)
    except Exception as exc:  # noqa: BLE001 — isolation IS the contract here
        errors[key] = {"error": sanitize_error(exc), "at": now_iso}
        return False
    stamps[key] = now_iso
    errors.pop(key, None)
    return True


def guard_output(serialized_text: str) -> None:
    """Defense-in-depth backstop (AC3/AC15, class V).

    With capture-time sanitization this should never fire; if it does, that
    is an exporter bug and refusing to publish remains correct (exit 1).
    """
    lowered = serialized_text.lower()
    for sub in FORBIDDEN_SUBSTRINGS:
        if sub in lowered:
            raise RuntimeError(f"guard violation: forbidden substring '{sub}' in output")
    if TOKEN_RE.search(serialized_text):
        raise RuntimeError("guard violation: token-like secret pattern in output")


def serialize_data(data) -> str:
    return json.dumps(data, indent=2) + "\n"


def atomic_write(path: Path, text: str) -> None:
    """Serialize-once → sibling tmp → os.replace (gate blocker 2).

    A torn write must never destroy the last-good cache (the input file IS
    the cache): either the old file survives intact or the new one appears
    atomically. The transient same-dir tmp is consumed by the replace and is
    part of writing path itself, not a second artifact (AC14 ruling).
    """
    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


# Legacy projects helpers (unchanged behaviour — AC6 keeps this logic).
def compute_specs(proj_path: Path) -> dict:
    moo = proj_path / ".moo-swarm"
    total, active = 0, 0
    latest_date = None
    for subdir, is_active in [("features", True), ("archive", False)]:
        d = moo / subdir
        if d.is_dir():
            for item in d.iterdir():
                if item.is_dir() and "-" in item.name:
                    total += 1
                    if is_active:
                        active += 1
                    parts = item.name.split("-", 3)
                    if len(parts) >= 3:
                        try:
                            feat_date = "-".join(parts[:3])
                            if latest_date is None or feat_date > latest_date:
                                latest_date = feat_date
                        except Exception:
                            pass
    return {"total": total, "active": active, "latest": latest_date}


def infer_pipeline_owner(proj_path: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(proj_path), "log", "--format=%ae", "-n", "30"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if out.returncode != 0:
            return None

        authors = [
            line.strip().split("@", 1)[0].strip().lower()
            for line in out.stdout.splitlines()
            if "@" in line
        ]
        if not authors:
            return None

        counts = {}
        for author in authors:
            counts[author] = counts.get(author, 0) + 1
        top = max(counts.items(), key=lambda pair: pair[1])[0]
        return AGENT_ALIASES.get(top)
    except Exception:
        return None


def main() -> None:
    if not DATA_FILE.exists():
        print(f"❌ {DATA_FILE} not found", file=sys.stderr)
        sys.exit(1)

    data = json.loads(DATA_FILE.read_text())

    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Last-good cache lives in the input file itself (DR-A): seed both maps
    # so a previously-failed section's old stamp persists truthfully until
    # its source next succeeds.
    stamps = data.setdefault("sections_updated_at", {})
    errors = data.setdefault("source_errors", {})

    cfg = env_config()
    failed = [key for key, fn in SOURCES if not run_source(key, fn, data, stamps, errors, now_iso, cfg)]

    # Back-compat migration for older exports (schema discipline, AC7):
    # every SCHEMA.required key present on every run, even when its source
    # failed on a fresh input file.
    data.setdefault("schema_version", "2.0")
    data.setdefault("budget_daily", {"window_days": 14, "generated_at": now_iso, "items": []})
    for key in ("projects", "pipeline", "issues", "prs", "cron_jobs", "agents"):
        data.setdefault(key, [])

    for agent in data["agents"]:
        if not isinstance(agent, dict):
            continue
        budget = agent.setdefault("budget_daily", {})
        budget.setdefault("tokens", 0)
        budget.setdefault("cost", 0.0)
        budget.setdefault("pricing_configured", False)
        budget.setdefault("limit_tokens", 200000)
        budget.setdefault("limit_cost", 0.60)

    # Global updated_at timestamps the FILE (always advances, even degraded).
    data["updated_at"] = now_iso
    meta = data.setdefault("meta", {})
    meta["version"] = "2.0"
    meta["generated_by"] = "moo-export-data.sh"
    meta["export_host"] = meta.get("export_host", "lex-agent-swarm")
    meta["runtime_version"] = meta.get("runtime_version", "24.18.0")

    try:
        payload = serialize_data(data)
        guard_output(payload)
        atomic_write(DATA_FILE, payload)
    except SystemExit:
        raise
    except Exception as exc:
        # Serialization/guard/write failures never touch the original file.
        print(f"❌ export aborted before write: {sanitize_error(exc)}", file=sys.stderr)
        sys.exit(1)

    if failed:
        print(f"⚠️ data/swarm.json written at {now_iso}; sources failed (kept last-good): {', '.join(failed)}")
    else:
        print(f"✅ data/swarm.json updated at {now_iso}")


if __name__ == "__main__":
    main()
