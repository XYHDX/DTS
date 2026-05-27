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

# Conflict-resolution mode. Pick exactly one (or leave both empty).
#   PUSH_REBASE=1   → on a stale/non-fast-forward reject, fetch origin,
#                     rebase local main on top of origin/main, push again.
#                     Keeps the remote's history; safe for shared repos.
#   PUSH_FORCE=1    → overwrite the remote with the local history
#                     (still uses --force-with-lease, so it only succeeds
#                     when the remote hasn't moved since we last fetched).
#                     Loses commits on the remote that aren't local.
#                     Only safe for solo / throwaway-history repos.
: "${PUSH_REBASE:=}"
: "${PUSH_FORCE:=}"

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

  # First attempt — safe push (rejected if the remote has commits we
  # don't, which is what just happened the first time you ran this).
  banner "Pushing $label → main"
  if git push -u --force-with-lease origin main 2>&1; then
    ok "$label pushed"
    cd - >/dev/null
    return 0
  fi

  echo
  warn "$label push was rejected — the remote has commits the local doesn't."
  echo

  # Fetch and show the diff in both directions so the human can decide.
  git fetch origin --quiet || warn "could not fetch origin"
  echo -e "${BOLD}== LOCAL has but REMOTE doesn't (will be pushed):${RESET}"
  git log --oneline "origin/main..main" 2>/dev/null | sed 's/^/  /' || echo "  (none)"
  echo -e "${BOLD}== REMOTE has but LOCAL doesn't (could be lost on force-push):${RESET}"
  git log --oneline "main..origin/main" 2>/dev/null | sed 's/^/  /' || echo "  (none)"
  echo

  if [ -n "$PUSH_REBASE" ]; then
    banner "PUSH_REBASE=1 — rebasing local main onto origin/main"
    if git pull --rebase origin main; then
      ok "$label rebase OK — pushing again"
      git push -u origin main && { ok "$label pushed (post-rebase)"; cd - >/dev/null; return 0; }
      fail "push still failed after rebase — fix manually with: cd $repo && git status"
    else
      fail "rebase reported conflicts — fix manually with: cd $repo && git status"
    fi
  fi

  if [ -n "$PUSH_FORCE" ]; then
    banner "PUSH_FORCE=1 — overwriting remote with local history"
    # Fetch above already updated origin/main, so this lease will succeed.
    if git push -u --force-with-lease origin main; then
      ok "$label force-pushed (the remote commits listed above are now only in your reflog)"
      cd - >/dev/null
      return 0
    fi
    fail "force push failed — see error above"
  fi

  echo "Choose one:"
  echo "  • Keep the remote's commits and replay yours on top:"
  echo "      PUSH_REBASE=1 bash \"$0\""
  echo "  • Overwrite the remote with your local history (loses the commits above):"
  echo "      PUSH_FORCE=1 bash \"$0\""
  echo "  • Or do it manually:"
  echo "      cd $repo"
  echo "      git pull --rebase origin main  # then resolve conflicts"
  echo "      git push -u origin main"
  fail "push not completed for $label — pick a strategy and re-run"
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
