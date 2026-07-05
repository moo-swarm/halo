#!/usr/bin/env python3
"""moose-export-data.py — generate halo data/swarm.json from live host state"""
import json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

HALO_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = HALO_DIR / "data" / "swarm.json"
PROJECTS_DIR = Path("/home/lex/.openclaw/workspaces/_align-rail_/projects")

NOW = datetime.now(timezone.utc)
TODAY = NOW.strftime("%Y-%m-%d")
NOW_ISO = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")

def compute_specs(proj_path: Path) -> dict:
    moo = proj_path / ".moo-swarm"
    total, active = 0, 0
    for subdir, is_active in [("features", True), ("archive", False)]:
        d = moo / subdir
        if d.is_dir():
            for item in d.iterdir():
                if item.is_dir() and "-" in item.name:
                    total += 1
                    if is_active:
                        active += 1
    return {"total": total, "active": active}

def fetch_issues(repo: str) -> int:
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/moo-swarm/{repo}", "--jq", ".open_issues_count"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip())
    except Exception:
        pass
    return 0

def main():
    if not DATA_FILE.exists():
        print(f"❌ {DATA_FILE} not found", file=sys.stderr)
        sys.exit(1)

    data = json.loads(DATA_FILE.read_text())

    for p in data["projects"]:
        name = p["name"]
        proj_path = PROJECTS_DIR / name

        # Specs from filesystem
        if proj_path.is_dir():
            p["specs"] = compute_specs(proj_path)

        # Freshness: bump projects with active features to today
        moo = proj_path / ".moo-swarm"
        if moo.is_dir() and (moo / "features").is_dir():
            feat_dir = moo / "features"
            if any(d.startswith("20") for d in os.listdir(feat_dir)):
                p["last_updated"] = TODAY
        else:
            # keep existing date; if missing, set today
            p.setdefault("last_updated", TODAY)

        # GitHub issues
        p["open_issues"] = fetch_issues(name)

    # Top-level freshness
    data["updated_at"] = NOW_ISO

    DATA_FILE.write_text(json.dumps(data, indent=2) + "\n")
    print(f"✅ data/swarm.json updated at {NOW_ISO}")

if __name__ == "__main__":
    main()