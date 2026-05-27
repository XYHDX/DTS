#!/usr/bin/env bash
# ============================================================
# CLEANUP_BRANCHES.command  —  remove obsolete branches from GitHub
# ============================================================
# After the v5.0 / Track A / Track C / Wave 6 work landed on `main`,
# the older wave / preview branches that were used during development
# are dead weight. This script lists them, asks for confirmation,
# then deletes them from origin AND your local clone.
#
# Run from Terminal:
#   bash ~/Documents/Claude/Projects/DamascusTransitSystem/CLEANUP_BRANCHES.command
# ============================================================

set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"/source 2>/dev/null || {
  echo "ERROR: run this from inside the DamascusTransitSystem project"
  exit 1
}

echo "❖ Fetching latest branch list from origin"
git fetch --prune origin

# Branches that are safe to delete. EDIT this list if you have any
# work-in-progress branches you want to keep — anything not listed
# below is left alone.
SAFE_TO_DELETE=(
  "_bootstrap"
  "preview"
  "wave2"
  "wave3"
  "wave3-plus"
  "wave-3"
  "feature/old"
)

echo
echo "Branches currently on origin:"
git branch -r 2>&1 | grep -v 'HEAD ->' | sed 's/^/  /'

echo
echo "Will attempt to delete:"
for b in "${SAFE_TO_DELETE[@]}"; do
  if git show-ref --quiet "refs/remotes/origin/$b"; then
    echo "  · $b"
  fi
done

echo
read -p "Proceed with deletion? [y/N] " yn
case "$yn" in
  y|Y|yes|YES) ;;
  *) echo "Aborted."; exit 0;;
esac

for b in "${SAFE_TO_DELETE[@]}"; do
  if git show-ref --quiet "refs/remotes/origin/$b"; then
    echo "  ✗ deleting origin/$b"
    git push origin --delete "$b" 2>&1 | sed 's/^/    /'
  fi
done

# Also drop any local references that point at the deleted branches.
git remote prune origin

echo
echo "Remaining branches on origin:"
git branch -r 2>&1 | grep -v 'HEAD ->' | sed 's/^/  /'

echo
echo "Done. main is now the canonical branch."
