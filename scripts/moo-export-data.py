#!/usr/bin/env python3
"""moo-export-data.py — generate halo data/swarm.json from live host state"""
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

HALO_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = HALO_DIR / "data" / "swarm.json"
PROJECTS_DIR = Path("/home/lex/.openclaw/workspaces/_align-rail_/projects")

NOW = datetime.now(timezone.utc)
TODAY = NOW.strftime("%Y-%m-%d")
NOW_ISO = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")

AGENT_ALIASES = {
    "lex": "moo",
    "cmok": "cmok",
    "bagnik": "bagnik",
    "veles": "veles",
    "zlydni": "zlydni",
    "mokash": "mokash",
}


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
            [
                "git",
                "-C",
                str(proj_path),
                "log",
                "--format=%ae",
                "-n",
                "30",
            ],
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


def fetch_issues(repo: str) -> int:
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


def main() -> None:
    if not DATA_FILE.exists():
        print(f"❌ {DATA_FILE} not found", file=sys.stderr)
        sys.exit(1)

    data = json.loads(DATA_FILE.read_text())

    for p in data["projects"]:
        name = p["name"]
        proj_path = PROJECTS_DIR / name

        specs = {"total": 0, "active": 0, "latest": None}
        if proj_path.is_dir():
            specs = compute_specs(proj_path)

        p["specs"] = specs

        if specs["latest"]:
            p["last_updated"] = specs["latest"]
        else:
            p.setdefault("last_updated", TODAY)

        p.setdefault("pipeline_owner_agent", infer_pipeline_owner(proj_path))

        budget = p.setdefault("budget_daily", {})
        budget.setdefault("tokens", 0)
        budget.setdefault("cost", 0.0)
        budget.setdefault("pricing_configured", False)
        budget.setdefault("limit_tokens", 200000)
        budget.setdefault("limit_cost", 0.60)

        if "open_issues" not in p:
            p["open_issues"] = fetch_issues(name)

    # Back-compat migration for older exports
    data.setdefault("schema_version", "2.0")
    data.setdefault("budget_daily", {"window_days": 14, "generated_at": NOW_ISO, "items": []})

    for agent in data.setdefault("agents", []):
        budget = agent.setdefault("budget_daily", {})
        budget.setdefault("tokens", 0)
        budget.setdefault("cost", 0.0)
        budget.setdefault("pricing_configured", False)
        budget.setdefault("limit_tokens", 200000)
        budget.setdefault("limit_cost", 0.60)

    data["updated_at"] = NOW_ISO
    meta = data.setdefault("meta", {})
    meta["version"] = "2.0"
    meta["generated_by"] = "moo-export-data.sh"
    meta["export_host"] = meta.get("export_host", "lex-agent-swarm")
    meta["runtime_version"] = meta.get("runtime_version", "24.18.0")

    DATA_FILE.write_text(json.dumps(data, indent=2) + "\n")
    print(f"✅ data/swarm.json updated at {NOW_ISO}")


if __name__ == "__main__":
    main()
