#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

COVERAGE_DIR=".coverage_history"
COVERAGE_PREV="$COVERAGE_DIR/coverage-prev.json"

# Create virtual environment if it doesn't exist
if [ ! -d .venv ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies (including pytest + coverage)
pip install -r requirements.txt --quiet
pip install pytest pytest-mock pytest-cov httpx --quiet

# Save previous coverage if it exists
mkdir -p "$COVERAGE_DIR"
if [ -f "$COVERAGE_DIR/coverage-current.json" ]; then
    cp "$COVERAGE_DIR/coverage-current.json" "$COVERAGE_PREV"
fi

# Run all unit tests with coverage
echo "========================================="
echo "  Running backend tests with coverage"
echo "========================================="
python -m pytest --cov --cov-report=term-missing --cov-report=json:"$COVERAGE_DIR/coverage-current.json" "$@"

# Show coverage delta if previous run exists
if [ -f "$COVERAGE_PREV" ]; then
    echo ""
    echo "========================================="
    echo "  Coverage changes since last run"
    echo "========================================="
    python3 -c "
import json, sys

with open('$COVERAGE_PREV') as f:
    prev = json.load(f)
with open('$COVERAGE_DIR/coverage-current.json') as f:
    curr = json.load(f)

prev_total = prev.get('totals', {}).get('percent_covered', 0)
curr_total = curr.get('totals', {}).get('percent_covered', 0)
delta = curr_total - prev_total

arrow = '↑' if delta > 0 else ('↓' if delta < 0 else '→')
color = '\033[32m' if delta > 0 else ('\033[31m' if delta < 0 else '\033[33m')
reset = '\033[0m'

print(f'  Overall: {prev_total:.1f}% → {curr_total:.1f}%  {color}{arrow} {delta:+.1f}%{reset}')
print()

# Per-file deltas
prev_files = prev.get('files', {})
curr_files = curr.get('files', {})
all_files = sorted(set(list(prev_files.keys()) + list(curr_files.keys())))

changes = []
for f in all_files:
    p = prev_files.get(f, {}).get('summary', {}).get('percent_covered', 0)
    c = curr_files.get(f, {}).get('summary', {}).get('percent_covered', 0)
    d = c - p
    if abs(d) > 0.01 or f not in prev_files:
        changes.append((f, p, c, d))

if changes:
    for f, p, c, d in changes:
        arrow = '↑' if d > 0 else ('↓' if d < 0 else 'NEW')
        color = '\033[32m' if d > 0 else ('\033[31m' if d < 0 else '\033[36m')
        if f not in prev_files:
            print(f'  {color}NEW{reset}  {c:5.1f}%  {f}')
        else:
            print(f'  {color}{d:+5.1f}%{reset}  {p:.1f}% → {c:.1f}%  {f}')
else:
    print('  No per-file changes.')
print()
"
else
    echo ""
    echo "(First run — no previous coverage to compare against)"
    echo "(Run tests again to see coverage delta)"
fi
