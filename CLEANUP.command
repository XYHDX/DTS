#!/usr/bin/env bash
# ============================================================
# CLEANUP.command — remove stub lock files left by the sandbox
# ============================================================
# The sandbox merge worked by renaming .git/index.lock and friends to
# .git/index.lock.gone-N (because rm/unlink wasn't permitted on the
# mount). Git treats some of those names as broken refs and warns on
# every command. This script removes them from your Terminal where
# regular FS permissions apply.
#
# Run once:
#   bash ~/Documents/Claude/Projects/DamascusTransitSystem/CLEANUP.command
# ============================================================
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

cleanup() {
  local repo="$1"
  echo "── cleaning $repo"
  cd "$repo"
  # Stub lock-ish files left at the .git root
  rm -f .git/index.lock.try-* .git/index.lock.gone-* .git/index.lock.refupd-* \
        .git/index.lock.todelete .git/HEAD.lock .git/HEAD.lock.gone-* \
        .git/packed-refs.lock .git/packed-refs.lock.gone-* 2>/dev/null || true
  # Broken refs Git complains about
  rm -f .git/refs/heads/_bootstrap.lock         \
        .git/refs/heads/_bootstrap.lock.gone-*  \
        .git/refs/heads/*.lock                  2>/dev/null || true
  # Old .bak from sed -i.bak
  find . -name '*.bak' -type f -delete 2>/dev/null || true
  # If _bootstrap branch is still around in the top-level repo, drop it.
  if git show-ref --quiet refs/heads/_bootstrap && [ "$(git branch --show-current)" != "_bootstrap" ]; then
    git branch -D _bootstrap || true
  fi
  echo "  done. branches:"
  git branch -a 2>&1 | sed 's/^/    /'
  echo "  HEAD: $(git symbolic-ref HEAD)"
  echo "  log:  $(git log --oneline -1)"
}

cleanup "$ROOT"
cleanup "$ROOT/source"

echo
echo "─────────────────────────────────────────────────────────────"
echo "All set. Push when ready:"
echo "  cd $ROOT/source && git push -u origin main"
echo "  cd $ROOT        && git push -u origin main"
echo "─────────────────────────────────────────────────────────────"
