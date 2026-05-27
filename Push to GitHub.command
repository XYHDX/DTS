#!/usr/bin/env bash
# Push to GitHub.command
# ─────────────────────────────────────────────────────────────────────────
# Double-click on macOS (Finder launches this in Terminal.app),
# or from a Terminal:   bash "./Push to GitHub.command"
#
# What it does (v5.0 / Track A / Track C — 2026-05-27)
#   1. Sanity-checks git is installed.
#   2. Clears the stale sandbox lock-stubs in BOTH repos (the .gone-*
#      files and *.bak from sed -i.bak). No-op if there are none.
#   3. For each repo (source/ and the top-level meta repo):
#        a. Verifies/configures the `origin` remote.
#        b. Pushes `main` (force-with-lease when the remote already has
#           a head, so you don't blow away someone else's commits).
#   4. Configures the macOS keychain credential helper so the GitHub
#      Personal Access Token only needs to be entered once.
#
# What you need
#   - This script lives next to source/  (the actual code repo) and the
#     top-level project repo. Both already have v5.0 + Track A + Track C
#     committed on `main` — this only pushes them.
#   - A GitHub Personal Access Token with `repo` scope from
#       https://github.com/settings/tokens?type=beta
#     Paste it as the password the first time prompted; the keychain
#     helper remembers it for next time.
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; DIM='\033[2m'; RESET='\033[0m'; BOLD='\033[1m'
banner() { echo -e "${BLUE}${BOLD}❖ $*${RESET}"; }
ok()     { echo -e "${GREEN}✓${RESET} $*"; }
warn()   { echo -e "${YELLOW}!${RESET} $*"; }
fail()   { echo -e "${RED}✗${RESET} $*"; exit 1; }
dim()    { echo -e "${DIM}$*${RESET}"; }

# ── 0. Pre-flight ───────────────────────────────────────────────────────────
command -v git >/dev/null 2>&1 || fail "git not found. Install with: xcode-select --install"

# Defaults — override by exporting before running this script.
: "${SOURCE_REMOTE:=https://github.com/XYHDX/DTS.git}"
: "${META_REMOTE:=}"            # leave empty to skip the top-level push

banner "Damascus Transit — push v5.0 + Track A + Track C to GitHub"
dim    "  source remote : $SOURCE_REMOTE"
dim    "  meta remote   : ${META_REMOTE:-<skipped>}"

# macOS keychain helper (no-op if already enabled).
if [[ "$(uname -s)" == "Darwin" ]]; then
  git config --global credential.helper osxkeychain || true
fi

# ── 1. Cleanup stale sandbox lock-stubs ─────────────────────────────────────
banner "Cleaning sandbox lock-stubs"
cleanup_repo_locks() {
  local repo="$1"
  [ -d "$repo/.git" ] || return 0
  cd "$repo"
  rm -f .git/index.lock .git/HEAD.lock .git/packed-refs.lock \
        .git/index.lock.gone-* .git/index.lock.try-* .git/index.lock.refupd-* \
        .git/index.lock.tc-*   .git/index.lock.tc2-* \
        .git/HEAD.lock.gone-*  .git/HEAD.lock.tc-* .git/HEAD.lock.tc2-* \
        .git/packed-refs.lock.gone-* \
        .git/index.lock.todelete 2>/dev/null || true
  rm -f .git/refs/heads/_bootstrap.lock \
        .git/refs/heads/_bootstrap.lock.gone-* \
        .git/refs/heads/*.lock 2>/dev/null || true
  find . -name '*.bak' -type f -delete 2>/dev/null || true
  cd - >/dev/null
  ok "cleaned $repo"
}
cleanup_repo_locks "$HERE/source"
cleanup_repo_locks "$HERE"

# ── 2. Verify each repo's HEAD is on main + show what we'll push ────────────
report_repo() {
  local repo="$1" label="$2"
  cd "$repo"
  local branch sha
  branch="$(git branch --show-current 2>/dev/null || echo '?')"
  sha="$(git log --oneline -1 2>/dev/null || echo '<no commits>')"
  echo "  $label"
  echo "    branch : $branch"
  echo "    HEAD   : $sha"
  cd - >/dev/null
}
banner "Local state"
report_repo "$HERE/source" "source/"
[ -n "$META_REMOTE" ] && report_repo "$HERE" "top-level"

# ── 3. Push source/ ─────────────────────────────────────────────────────────
push_repo() {
  local repo="$1" want_remote="$2" label="$3"
  cd "$repo"

  # Ensure we're on main.
  local branch
  branch="$(git branch --show-current)"
  if [ "$branch" != "main" ]; then
    warn "$label is on '$branch', not 'main'. Switching."
    git checkout main || fail "couldn't switch $label to main"
  fi

  # Ensure origin points at the requested remote.
  if git remote get-url origin >/dev/null 2>&1; then
    local cur
    cur="$(git remote get-url origin)"
    if [ "$cur" != "$want_remote" ]; then
      warn "$label origin = $cur — rewriting to $want_remote"
      git remote set-url origin "$want_remote"
    fi
  else
    git remote add origin "$want_remote"
  fi
  ok "$label origin = $(git remote get-url origin)"

  # Push, force-with-lease for safety.
  banner "Pushing $label → main"
  if git push -u --force-with-lease origin main; then
    ok "$label pushed"
  else
    fail "push failed for $label — see error above"
  fi
  cd - >/dev/null
}
push_repo "$HERE/source" "$SOURCE_REMOTE" "source/"
[ -n "$META_REMOTE" ] && push_repo "$HERE" "$META_REMOTE" "top-level"

# ── 4. Done ─────────────────────────────────────────────────────────────────
echo
banner "Push complete"
echo "Next:"
echo "  • Vercel will auto-deploy if the repo is already connected."
echo "  • Hit ${BOLD}https://dts-brown.vercel.app/api/health${RESET} after the deploy —"
echo "    it should report \"version\":\"5.0.0\". If you still see 4.1.0,"
echo "    the deploy hasn't gone live yet."
echo "  • In Supabase SQL editor, run the four migrations in order:"
echo "      db/migrations/011_rotate_demo_credentials.sql"
echo "      db/migrations/012_geofence_capacity_and_links.sql"
echo "      db/migrations/013_trip_dispatch.sql"
echo "      db/migrations/014_headway_control.sql"
echo "  • New demo passwords (and the must_change_password flow) are in"
echo "    ${BOLD}DEMO_CREDENTIALS.md${RESET}."
