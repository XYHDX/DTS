# Contributing to DamascusTransit

> Updated 2026-05-24 to reflect the multi-codebase reality: Python backend + JS/HTML web + Dart/Flutter mobile + Capacitor wrapper. Pick the section that matches your change.

We genuinely want outside contributors. The roadmap is in [ROADMAP_100.md](ROADMAP_100.md) — pick an unticked step and reference its number in your PR title.

## First-time setup

```bash
git clone https://github.com/actuatorsos/SyrianTransitSystem.git
cd SyrianTransitSystem

# 1. Backend
cp .env.example .env       # fill in Supabase + JWT secrets (≥32 chars)
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pip install pre-commit
pre-commit install         # commit + commit-msg hooks
uvicorn api.index:app --reload --port 8000

# 2. Web (no build step needed)
# Files in public/ are served by Vercel directly. Edit and reload.

# 3. Flutter (only if you're touching flutter_app/)
cd flutter_app
flutter pub get
flutter run --dart-define=API_BASE=http://10.0.2.2:8000
```

## Branch + commit conventions

Branch names: `feat/short-name`, `fix/short-name`, `docs/short-name`, `refactor/short-name`, `security/short-name`.

Commit messages follow **Conventional Commits** — enforced by the `commit-msg` pre-commit hook:

```
feat(passenger): add ScheduleScreen with claude design
fix(auth): reject revoked JWTs after password change
docs(adr): record SSE-vs-WebSocket decision (#58)
deps(python): bump fastapi 0.115 → 0.136
```

Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`, `build`, `ci`, `revert`, `security`, `deps`.

## What you'll need to pass for merge

CI runs **eight** workflows. They all must be green:

| Workflow | Source | Catches |
|---|---|---|
| `ci.yml`               | lint + pytest + coverage | most regressions |
| `flutter.yml`          | `flutter analyze` + `flutter test` + debug APK | Dart bugs |
| `security-scan.yml`    | `pip-audit`, `npm audit`, gitleaks, `flutter pub outdated` | CVEs + leaked keys |
| `lighthouse.yml`       | Perf ≥85, a11y ≥90, best-practices ≥90 | UX regressions |
| `openapi-lint.yml`     | spectral against `openapi.json` | spec drift |
| `gtfs-validate.yml`    | GTFS feed sanity | bad transit data |
| `backup.yml`           | nightly Supabase backup + row-count diff | silent data loss |
| `release-please.yml`   | tag + changelog on `main` | release hygiene |

If a workflow fails for reasons unrelated to your change, post the link in the PR and a maintainer will retry it.

## Code style

### Python
- `ruff format`, `ruff check`, `bandit`. All run pre-commit and in CI.
- Async-first. Avoid `time.sleep`, prefer `asyncio.sleep`. Avoid sync IO in async endpoints.
- Type annotate every public function. Pydantic models for every request/response body.
- Tests in `tests/`, one module per router. Mark slow tests with `@pytest.mark.slow`.

### Dart / Flutter
- `dart format` + `flutter analyze --fatal-infos`. Lint config in `flutter_app/analysis_options.yaml`.
- Riverpod 2 for state. No `setState` in feature widgets except local UI gates.
- `const` constructors whenever possible.
- Strings to localise → add to both `lib/l10n/app_ar.arb` and `lib/l10n/app_en.arb`. RTL is the default.

### Web (HTML/CSS/JS)
- Use the design tokens in `public/lib/design-system.css`. Do not define new colours, radii, or spacing values in page CSS.
- Class naming follows the existing BEM-ish patterns (`.btn`, `.btn--gold`, `.stat`, `.stat__value`).
- Vanilla JS only. No framework. If a page becomes too complex, raise it in an issue first.

### SQL / migrations
- Migrations go in `db/migrations/NNN_short_name.sql` where `NNN` is the next free number.
- Wrap in `BEGIN; … COMMIT;`. Use `IF NOT EXISTS` everywhere idempotent.
- Document the column / table in a `COMMENT ON …` statement so it surfaces in the Supabase UI.

## Adding a feature — checklist

- [ ] Picked a step from `ROADMAP_100.md` (or opened an issue first if it isn't on the roadmap).
- [ ] Wrote / updated tests (`tests/`, `flutter_app/test/`, or `tests/test_*.spec.js`).
- [ ] Updated docs (`README.md`, the relevant `markdown-files/**/*.md`, or an ADR if it's a design decision).
- [ ] Ran `pre-commit run --all-files` locally and it passes.
- [ ] Opened a PR with a Conventional Commits title.
- [ ] Linked the roadmap step number in the PR body: `Closes ROADMAP-NN`.

## Reviewer expectations

Reviewers look for the following, in order:

1. **Does it work?** Run the change locally on a real device when it touches mobile. Run the relevant pytest module when it touches the backend.
2. **Does it preserve the contract?** API responses keep the same shape; SSE event payloads honour `markdown-files/technical/SSE_Contract.md`.
3. **Is the design language consistent?** Web uses tokens from `design-system.css`; Flutter uses `AppTheme` from `core/theme.dart`. New colours / fonts need an ADR.
4. **Is it safe?** No new secrets in code, no new HIGH bandit findings, no expansion of CORS or CSP without a comment explaining why.
5. **Is it understandable?** A new contributor reading just the PR diff and the linked docs should be able to follow what changed and why.

We aim to review every PR within **3 working days**. If yours has been quiet longer than that, ping `@maintainers` in the PR.

## Security disclosure

Security-relevant findings (HIGH / CRITICAL by the conventions in `markdown-files/technical/Security_Scan_*.md`) go to `security@damascustransit.sy` privately. Do **not** open a public issue.

We respond within 48 hours and aim to patch + release within seven days.

## Documentation footprint

If you write more than 50 lines of code, you probably owe at least 5 lines of documentation. Acceptable forms, ranked by preference:

1. **An ADR** in `markdown-files/adr/` when it's a design decision.
2. **An update to the README** when it changes how someone runs the project.
3. **A new file in `markdown-files/technical/`** when it's a process or contract.
4. **Inline `///` doc comments** (Dart) or `"""docstring"""` (Python) when it's a complex function.

Code without documentation is a tax on the next contributor.

## License

By contributing you agree your contribution is licensed under the project's MIT license.
