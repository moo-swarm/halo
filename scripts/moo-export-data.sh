#!/usr/bin/env bash
# ============================================================
# moo-export-data.sh — Halo Dashboard Data Export
# ============================================================
# Generates data/swarm.json from live host state and pushes
# to github.com/moo-swarm/halo (main branch).
#
# Usage: cron (hourly), or manually: ./scripts/moo-export-data.sh
# ============================================================
set -euo pipefail

HALO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$HALO_DIR/scripts/moo-export-data.py"
DATA_FILE="$HALO_DIR/data/swarm.json"

# === Step 1: Generate data ===
cd "$HALO_DIR"
python3 "$SCRIPT"

# === Step 2: Commit & push if changed ===
cd "$HALO_DIR"

if ! git diff --quiet -- data/swarm.json; then
  git add data/swarm.json
  git commit -m "data: auto-export $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  git push origin main 2>&1
  echo "✅ Pushed to github.com/moo-swarm/halo"
else
  echo "ℹ️ No changes to commit"
fi