#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# ScrapeGoat — single-machine startup script
# Usage: bash start.sh
# ──────────────────────────────────────────────────────────────────────────────

set -e

PYTHON=${PYTHON:-python3}
PORT=7331

echo ""
echo "  🐐  ScrapeGoat v2.1 — startup"
echo "  ─────────────────────────────"

# 1. Check Python
if ! command -v $PYTHON &> /dev/null; then
    echo "  ✗  Python 3 not found. Install from https://python.org"
    exit 1
fi
echo "  ✓  Python: $($PYTHON --version)"

# 2. Install Python deps
echo "  →  Installing Python dependencies..."
$PYTHON -m pip install -r requirements.txt --quiet --break-system-packages 2>/dev/null || \
$PYTHON -m pip install -r requirements.txt --quiet

# 3. Install Playwright Chromium (skip if already installed)
echo "  →  Checking Playwright Chromium..."
$PYTHON -m playwright install chromium --quiet 2>/dev/null || true

# 4. Check port availability
if lsof -Pi :$PORT -sTCP:LISTEN -t &>/dev/null 2>&1; then
    echo "  ⚠   Port $PORT already in use. Kill existing process or change PORT in server.py"
    exit 1
fi

# 5. Launch
echo "  ✓  All checks passed"
echo ""
echo "  ➜  Starting backend on http://localhost:$PORT"
echo "  ➜  Open http://localhost:$PORT in your browser"
echo ""
$PYTHON server.py
