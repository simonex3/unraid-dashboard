#!/bin/bash
# publish.sh — Sanitizes index.html (removes real API key) and pushes to GitHub.
# Usage: bash publish.sh "your commit message"
#
# Workflow:
#   - index.html.local  = your working file WITH real API key (never committed)
#   - index.html        = sanitized version WITH placeholder (committed to git)

set -e

REAL_KEY="1976740970e7dcf51c8ff2863232bad9b52f732c8b730a9d0ab622e664a8c833"
PLACEHOLDER="YOUR_UNRAID_API_KEY"
MSG="${1:-Update dashboard}"

echo "→ Sanitizing index.html..."
sed "s/${REAL_KEY}/${PLACEHOLDER}/g" index.html.local > index.html

echo "→ Staging..."
git add index.html README.md docker-compose.yml .gitignore Dockerfile nginx.conf speedtest_server.py start.sh CONTEXT.md 2>/dev/null || true

if git diff --cached --quiet; then
  echo "  Nothing to commit."
else
  git commit -m "${MSG}

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
  echo "→ Pushing to GitHub..."
  git push origin master
  echo "✓ Done."
fi
