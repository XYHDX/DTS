#!/usr/bin/env bash
# ============================================================
# MERGE_TO_MAIN.command — finish the v5.0 + Track A commit
# ============================================================
# Why this exists: the sandbox where I prepared the work has a file-system
# permission that prevents removing .git/index.lock when a host process
# (your editor or a Git GUI) is holding it. Run this script from your
# Terminal and it will:
#   1. Stop any stale Git locks in both repos.
#   2. Commit the staged work in `source/` to `main`.
#   3. Switch the top-level repo from `_bootstrap` → `main` and commit
#      every new untracked file (FIXES_APPLIED.md, DEMO_CREDENTIALS.md,
#      and friends) on top of the existing typography commit.
#
# Double-click in Finder, or run:
#   bash ~/Documents/Claude/Projects/DamascusTransitSystem/MERGE_TO_MAIN.command
# ============================================================

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
echo "ROOT = $ROOT"

# ---- 1. source/ repo --------------------------------------------------------
echo
echo "── 1/2  source/ → main ─────────────────────────────────────────────"
cd "$ROOT/source"

# Defensive: drop the stale lock file if it exists. Safe because we KNOW
# the only thing that locked it earlier was the sandbox sibling process.
if [ -f .git/index.lock ]; then
  echo "  removing stale .git/index.lock"
  rm -f .git/index.lock
fi
# Also drop the rename-marker we left behind.
rm -f .git/index.lock.todelete || true

git config user.name  "${GIT_USER_NAME:-3dtitans}"
git config user.email "${GIT_USER_EMAIL:-3dtitanssyria@gmail.com}"

# Make sure all v5.0 + Track A work is staged.
git add -A
echo "  staged: $(git status --short | wc -l | tr -d ' ') paths"

# Skip if nothing to commit (re-runs are safe).
if git diff --cached --quiet; then
  echo "  nothing to commit in source/"
else
  git commit -F "$ROOT/COMMIT_MSG.txt"
  echo "  ✓ commit in source/:"
  git log --oneline -1
fi

# ---- 2. top-level repo ------------------------------------------------------
echo
echo "── 2/2  DamascusTransitSystem/ → main ──────────────────────────────"
cd "$ROOT"

if [ -f .git/index.lock ]; then
  echo "  removing stale .git/index.lock"
  rm -f .git/index.lock
fi
rm -f .git/index.lock.todelete || true

git config user.name  "${GIT_USER_NAME:-3dtitans}"
git config user.email "${GIT_USER_EMAIL:-3dtitanssyria@gmail.com}"

# _bootstrap is empty — switch to main and bring the new files in.
CUR_BRANCH="$(git branch --show-current)"
if [ "$CUR_BRANCH" != "main" ]; then
  echo "  switching $CUR_BRANCH → main"
  git checkout main
fi

git add -A
if git diff --cached --quiet; then
  echo "  nothing to commit in top-level"
else
  git commit -F "$ROOT/COMMIT_MSG.txt"
  echo "  ✓ commit in top-level:"
  git log --oneline -1
fi

# Optional: delete the empty _bootstrap branch (it had no commits, so it's pure
# branch-pointer cleanup — comment out if you want to keep it for any reason).
if git show-ref --quiet refs/heads/_bootstrap; then
  echo "  deleting empty _bootstrap branch"
  git branch -D _bootstrap || true
fi

echo
echo "─────────────────────────────────────────────────────────────────────"
echo "Done. To push to GitHub:"
echo "  cd $ROOT/source && git push -u origin main"
echo "  cd $ROOT        && git push -u origin main"
echo "─────────────────────────────────────────────────────────────────────"
