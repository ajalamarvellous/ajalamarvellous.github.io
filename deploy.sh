#!/usr/bin/env bash
# Build the site and publish it.
#
# This repository is the source of truth. GitHub Actions builds it on every
# push to master and publishes the result to GitHub Pages, so deploying is
# just: build, check, commit, push.
#
#   ./deploy.sh              # build, check, commit and push the source
#   ./deploy.sh --dry-run    # show what would be committed, push nothing
#
# The old Jekyll site is preserved in git history, and at the tag
# `jekyll-backup` and the branch `backup/jekyll-site`.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRY_RUN=0

[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

echo "==> building"
python3 "$ROOT/build.py"

echo "==> checking links"
python3 "$ROOT/check.py"

cd "$ROOT"

git add -A
if git diff --cached --quiet; then
  echo "==> nothing to publish"
  exit 0
fi

if [ "$DRY_RUN" = "1" ]; then
  echo "==> would publish:"
  git diff --cached --stat
  exit 0
fi

git commit -m "Update site content"
echo "==> pushing"
git push origin master
echo "==> done — CI will build and publish to https://www.ajalamarvellous.com"
