# Push to https://github.com/XYHDX/DTS

> The sandbox where the code was prepared is firewalled from github.com (proxy returns HTTP 403 on CONNECT). So **you push from your own machine**. The repo is already initialised, committed, and bundled — just run two commands.

## Option A — Restore the git bundle (recommended, ~30 seconds)

Open a terminal on your Mac and paste:

```bash
cd ~/Documents/Claude/Projects/DamascusTransitSystem

# 1. Materialise the prepared repo from the bundle file
git clone dts-repo.bundle dts-push
cd dts-push

# 2. Re-point the remote and push
git remote remove origin
git remote add origin https://github.com/XYHDX/DTS.git
git branch -M main
git push -u origin main
```

That's it. Vercel auto-deploys on the first push if you've already connected the repo there.

If GitHub asks for credentials, use a **Personal Access Token** (not your password) — generate one at <https://github.com/settings/tokens?type=beta> with **Contents: read & write** scope, and paste it when prompted.

## Option B — From the files-only tarball

If you'd rather start a fresh git history:

```bash
cd ~/Documents/Claude/Projects/DamascusTransitSystem

mkdir dts-push && tar -xzf dts-repo-files.tar.gz -C dts-push
cd dts-push

git init -b main
git add -A
git commit -m "feat: post-revival v1.0 — Claude design + Flutter + 100k-scale foundation"
git remote add origin https://github.com/XYHDX/DTS.git
git push -u origin main
```

## Option C — If the repo already has history at XYHDX/DTS

Force-pushing would wipe your existing commits. If you want to merge instead:

```bash
git clone https://github.com/XYHDX/DTS.git dts-existing
cd dts-existing
# Then copy the changed files in by hand or with rsync from dts-push/
rsync -a --exclude='.git' ../dts-push/ ./
git add -A
git commit -m "feat: revival 2026-05-24"
git push
```

## What's inside

- `dts-repo.bundle` (787 KB) — full git history with one commit, ready to clone.
- `dts-repo-files.tar.gz` (1.1 MB) — same content as plain files, no git history.

Both contain:

- Backend (`api/`), database migrations (`db/`), web apps (`public/`), Capacitor wrapper (`mobile/`), Flutter app (`flutter_app/`).
- All eight CI workflows (`.github/workflows/`).
- All documentation (`markdown-files/`, runbooks, ADRs, `ROADMAP_100.md`, `Scale_100k_Roadmap.md`).
- `vercel.json` — Vercel will detect it on first deploy.

## After the push: Vercel deploy

In the Vercel dashboard:

1. **Import Project** → pick the XYHDX/DTS repository.
2. **Framework Preset:** "Other" (Vercel will detect `vercel.json`).
3. **Environment variables** (at minimum):
   - `SUPABASE_URL`
   - `SUPABASE_KEY` (anon)
   - `SUPABASE_SERVICE_KEY`
   - `JWT_SECRET` (≥32 chars — generate with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`)
   - `ALLOWED_ORIGINS` (your production hostname)
   - `TRUSTED_PROXY_IPS` (Vercel edge — leave blank initially; the limiter falls back to TCP source IP).

Full env-var table is in `DEPLOY.md` inside the repo.

After the first deploy, hit `https://<your-project>.vercel.app/api/health/deep` — you should see `{"status":"healthy"}`.
