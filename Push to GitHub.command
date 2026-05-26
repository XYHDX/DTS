#!/usr/bin/env bash
# Push to GitHub.command
# ─────────────────────────────────────────────────────────────────────────
# Double-click on macOS (Finder will launch this in Terminal.app).
# From a terminal:  bash "./Push to GitHub.command"
#
# What it does
#   1. Sanity-checks git is installed.
#   2. Restores the prepared git bundle into ./dts-push (idempotent — wipes
#      and recreates the directory on every run).
#   3. Re-points the remote to https://github.com/XYHDX/DTS.git
#   4. Pushes main, force-with-lease when a remote main already exists.
#   5. On macOS, configures the osxkeychain credential helper so you only
#      enter your GitHub Personal Access Token once.
#
# What you need
#   - The two files this script lives next to:
#        dts-repo.bundle           (the prepared repo, ~787 KB)
#        Push to GitHub.command    (this script)
#   - A GitHub Personal Access Token with `repo` scope from
#        https://github.com/settings/tokens?type=beta
#     Generate it ONCE; the keychain helper remembers it after the first push.
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

# Work from the directory this script lives in, no matter how it was invoked.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

# Pretty banner — terminal output only.
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
DIM='\033[2m'
RESET='\033[0m'
BOLD='\033[1m'

banner() { echo -e "${BLUE}${BOLD}❖ $*${RESET}"; }
ok()     { echo -e "${GREEN}✓ $*${RESET}"; }
warn()   { echo -e "${YELLOW}! $*${RESET}"; }
fail()   { echo -e "${RED}✗ $*${RESET}"; }

clear || true
echo ""
banner "DamascusTransit — push to https://github.com/XYHDX/DTS"
echo -e "${DIM}Working dir: ${HERE}${RESET}"
echo ""

# ─── 1. Prerequisites ──────────────────────────────────────────────────────
if ! command -v git >/dev/null 2>&1; then
  fail "git is not installed. Install Xcode Command-Line Tools first:"
  echo "    xcode-select --install"
  read -n 1 -s -r -p "Press any key to close…"; echo
  exit 2
fi
ok "git found ($(git --version | awk '{print $3}'))"

BUNDLE="$HERE/dts-repo.bundle"
if [[ ! -f "$BUNDLE" ]]; then
  fail "Bundle not found at: $BUNDLE"
  echo "    The script expects 'dts-repo.bundle' next to it."
  read -n 1 -s -r -p "Press any key to close…"; echo
  exit 3
fi
ok "Bundle present ($(du -h "$BUNDLE" | cut -f1))"

# ─── 2. macOS credential helper hint ───────────────────────────────────────
if [[ "$(uname -s)" == "Darwin" ]]; then
  if ! git config --global credential.helper | grep -q osxkeychain; then
    warn "git's macOS keychain helper isn't configured. Setting it now."
    git config --global credential.helper osxkeychain
    ok "git will remember your GitHub Personal Access Token after the first push."
  fi
fi

# ─── 3. Restore the bundle into a fresh ./dts-push ─────────────────────────
TARGET="$HERE/dts-push"
if [[ -d "$TARGET" ]]; then
  warn "Removing previous ./dts-push (idempotent re-run)."
  rm -rf "$TARGET"
fi

banner "Restoring the bundle…"
mkdir -p "$TARGET"
cd "$TARGET"

# The canonical restore: init on a throwaway branch so we can fetch into main
# without "Refusing to fetch into current branch", then check out main and
# delete the bootstrap branch. `git clone bundle` works in theory but leaves
# HEAD dangling when the bundle was produced from a freshly-init'd repo.
if ! git init -q -b _bootstrap; then
  fail "git init failed in $TARGET"
  read -n 1 -s -r -p "Press any key to close…"; echo
  exit 4
fi

if ! git fetch -q "$BUNDLE" main:main; then
  fail "Could not fetch main from the bundle. Is dts-repo.bundle complete?"
  read -n 1 -s -r -p "Press any key to close…"; echo
  exit 4
fi

if ! git checkout -q main; then
  fail "Could not check out main after fetch."
  read -n 1 -s -r -p "Press any key to close…"; echo
  exit 4
fi
git branch -D _bootstrap >/dev/null 2>&1 || true

# Wire the GitHub remote.
git remote remove origin >/dev/null 2>&1 || true
git remote add origin https://github.com/XYHDX/DTS.git

# Confirmation
HEAD_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
FILE_COUNT="$(git ls-files | wc -l | tr -d ' ')"
ok "Restored at ./dts-push  ·  branch=main  ·  HEAD=$HEAD_SHA  ·  $FILE_COUNT files"

# ─── 4. Identity hint ──────────────────────────────────────────────────────
if [[ -z "$(git config user.email)" ]]; then
  git config user.email "3dtitanssyria@gmail.com"
fi
if [[ -z "$(git config user.name)" ]]; then
  git config user.name  "3dtitans"
fi
echo -e "${DIM}Author: $(git config user.name) <$(git config user.email)>${RESET}"
echo ""

# ─── 5. Push ───────────────────────────────────────────────────────────────
banner "Pushing to main…"
echo -e "${DIM}If GitHub asks for credentials, paste a Personal Access Token"
echo -e "(not your password). Generate one at:"
echo -e "  https://github.com/settings/tokens?type=beta${RESET}"
echo ""

PUSH_OK=0

# Attempt 1: clean fast-forward push (works when remote is empty).
if git push -u origin main 2>&1 | tee /tmp/dts-push-output.log; then
  PUSH_OK=1
elif grep -qE "rejected|non-fast-forward|fetch first" /tmp/dts-push-output.log; then
  echo ""
  warn "The remote already has commits on main (probably from a 'Initialize with README' tick when the repo was created)."
  echo ""

  # Show what's actually on the remote so the user can decide informed.
  if git fetch origin main --quiet 2>/dev/null; then
    REMOTE_COUNT=$(git rev-list --count origin/main 2>/dev/null || echo "?")
    echo -e "${DIM}Remote main has $REMOTE_COUNT commit(s). The most recent are:${RESET}"
    git log --oneline -5 origin/main 2>/dev/null | sed 's/^/    /'
    echo ""
    REMOTE_FILES=$(git ls-tree -r --name-only origin/main 2>/dev/null | wc -l | tr -d ' ')
    echo -e "${DIM}…with $REMOTE_FILES file(s) on the remote.${RESET}"
  else
    echo -e "${DIM}(Couldn't fetch the remote for inspection.)${RESET}"
  fi
  echo ""

  echo "How would you like to proceed?"
  echo -e "  ${BOLD}o${RESET}) Overwrite remote main with this codebase (discards remote commits — usually what you want for a fresh project import)"
  echo -e "  ${BOLD}m${RESET}) Merge remote into local first, then push (keeps remote commits — pick this if there's something on the remote you care about)"
  echo -e "  ${BOLD}c${RESET}) Cancel"
  echo ""
  echo -ne "${BOLD}Choice [o/m/c]: ${RESET}"
  read -r CHOICE
  CHOICE=$(echo "$CHOICE" | tr '[:upper:]' '[:lower:]' | head -c 1)

  case "$CHOICE" in
    o)
      banner "Overwriting remote main…"
      if git push -u --force origin main; then
        PUSH_OK=1
      fi
      ;;
    m)
      banner "Merging remote into local, then pushing…"
      if git pull --allow-unrelated-histories --no-edit origin main && git push -u origin main; then
        PUSH_OK=1
      else
        fail "Merge had conflicts. Resolve them inside ./dts-push, commit, then run:"
        echo "    cd dts-push && git push -u origin main"
      fi
      ;;
    *)
      warn "Cancelled. Nothing was pushed."
      ;;
  esac
else
  # Some other failure — auth, network, etc.
  :
fi

echo ""
if [[ "${PUSH_OK:-0}" == "1" ]]; then
  echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
  ok "Push complete!"
  echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
  echo ""
  echo "Next steps:"
  echo "  1. Open https://github.com/XYHDX/DTS — confirm the commit is there."
  echo "  2. In Vercel, Import the XYHDX/DTS repository."
  echo "  3. Set the env vars listed in DEPLOY.md (SUPABASE_*, JWT_SECRET, ALLOWED_ORIGINS…)."
  echo "  4. After the first deploy, curl https://<your-url>/api/health/deep — expect 200."
  echo ""
else
  echo -e "${RED}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
  fail "Push failed."
  echo -e "${RED}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
  echo ""
  echo "Common causes:"
  echo "  • Authentication: you must use a Personal Access Token, not a password."
  echo "    Generate one at https://github.com/settings/tokens?type=beta"
  echo "    Required scope: 'repo' (or fine-grained 'Contents: read & write')."
  echo ""
  echo "  • The repo at github.com/XYHDX/DTS doesn't exist yet."
  echo "    Create it (empty) at https://github.com/new — owner XYHDX, name DTS."
  echo ""
  echo "  • Your account doesn't have push access to XYHDX/DTS."
  echo ""
  echo "Full output is at /tmp/dts-push-output.log"
fi

echo ""
read -n 1 -s -r -p "Press any key to close this window…"
echo
