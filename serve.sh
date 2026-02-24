#!/usr/bin/env bash
# Start a local development server for the Grant Hunter dashboard.
# Usage: ./serve.sh [port]
#
# Opens http://localhost:8000 (or custom port) in docs/ directory.

PORT="${1:-8000}"
DIR="$(cd "$(dirname "$0")/docs" && pwd)"

echo "Serving dashboard at http://localhost:${PORT}"
echo "Press Ctrl+C to stop."
python3 -m http.server "$PORT" --directory "$DIR"
