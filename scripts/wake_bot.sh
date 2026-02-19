#!/bin/bash
# Wake bot via GitHub repository dispatch
# Requires: GitHub Personal Access Token with repo scope

GITHUB_TOKEN="${GITHUB_TOKEN:-}"
REPO="suraganovzh/coreelement-grants-hunter"

if [ -z "$GITHUB_TOKEN" ]; then
    echo "❌ Error: GITHUB_TOKEN not set"
    echo "Create token at: https://github.com/settings/tokens"
    echo "Required scope: repo"
    echo ""
    echo "Usage:"
    echo "  export GITHUB_TOKEN=your_token_here"
    echo "  ./scripts/wake_bot.sh"
    exit 1
fi

echo "🤖 Sending wake signal to bot..."

curl -s -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  "https://api.github.com/repos/${REPO}/dispatches" \
  -d '{"event_type":"wake_bot"}'

if [ $? -eq 0 ]; then
    echo "✅ Wake signal sent successfully"
    echo "Check Telegram for confirmation"
else
    echo "❌ Failed to send wake signal"
    exit 1
fi
