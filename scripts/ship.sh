#!/usr/bin/env bash
# ship.sh — one-command commit + push for this repo.
#
# Pairs with .github/workflows/auto-pr.yml, which auto-opens the pull request
# once the branch is pushed. So your whole flow per change becomes one line:
#
#     scripts/ship.sh -m "fix(scope): short conventional summary"
#
# It clears any stale .git/index.lock, creates/switches to a branch, stages your
# changes, commits, and pushes with upstream tracking. The PR then opens itself.
#
# Usage:
#   scripts/ship.sh -m "<commit message>" [-b <branch>] [<path> ...]
#
#   -m   commit message (REQUIRED; use Conventional Commits — CI lints it)
#   -b   branch name (optional; default derived from the message + a timestamp)
#   -h   show this help
#   trailing paths: stage only these files (default: stage everything, git add -A)
#
# Examples:
#   scripts/ship.sh -m "fix(auth): reject expired tokens"
#   scripts/ship.sh -m "docs: refresh readme" -b docs/readme README.md
set -euo pipefail

msg=""; branch=""
while getopts ":m:b:h" opt; do
  case "$opt" in
    m) msg="$OPTARG" ;;
    b) branch="$OPTARG" ;;
    h) grep '^#' "$0" | grep -v '^#!' | sed 's/^# \{0,1\}//'; exit 0 ;;
    \?) echo "Unknown option -$OPTARG (use -h for help)" >&2; exit 2 ;;
    :) echo "Option -$OPTARG requires a value" >&2; exit 2 ;;
  esac
done
shift $((OPTIND - 1))

[ -n "$msg" ] || { echo "ERROR: -m \"<commit message>\" is required (use -h for help)." >&2; exit 2; }

cd "$(git rev-parse --show-toplevel)"

# Derive a branch name from the commit message when one isn't supplied.
if [ -z "$branch" ]; then
  slug=$(printf '%s' "$msg" | tr '[:upper:]' '[:lower:]' \
        | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//' | cut -c1-40)
  branch="claude/${slug:-change}-$(date -u +%Y%m%d-%H%M%S)"
fi

# Never commit straight to the default branch.
default_branch=$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null \
                 | sed 's@^origin/@@' || true)
default_branch="${default_branch:-main}"
case "$branch" in
  main|master|"$default_branch")
    echo "ERROR: refusing to commit directly to '$branch'." >&2; exit 2 ;;
esac

# Clear a stale index lock (safe when no other git process is running).
[ -f .git/index.lock ] && rm -f .git/index.lock || true

# Create or switch to the branch (from the current HEAD).
git switch -c "$branch" 2>/dev/null || git switch "$branch"

# Stage explicit paths if given, otherwise everything.
if [ "$#" -gt 0 ]; then
  git add -- "$@"
else
  git add -A
fi

if git diff --cached --quiet; then
  echo "Nothing staged to commit — aborting." >&2
  exit 1
fi

git commit -m "$msg"
git push -u origin "$branch"

echo
echo "✅ Pushed '$branch'. The auto-PR workflow will open the pull request."
repo_path=$(git remote get-url origin 2>/dev/null \
            | sed -E 's#(git@[^:]+:|https?://[^/]+/)##; s#\.git$##' || true)
[ -n "$repo_path" ] && echo "   If it doesn't appear: https://github.com/$repo_path/pull/new/$branch"
