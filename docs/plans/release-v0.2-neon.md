# Release Plan - v0.2.0 Docker + Render

## Scope
Deploy the app to Render using Docker, with release flow from develop to main.

## Non-goals
- No historical data migration from SQLite to PostgreSQL.
- No feature work outside release readiness.

## Confirmed Constraints
- Render is the hosting platform.
- Docker is the deployment artifact.
- SQLite stays local fallback only.
- Hosted runtime must use PostgreSQL via DATABASE_URL.
- Branch flow is feature/fix/chore to develop, then develop to main.
- Runtime note: keep current Django compatibility workaround active for Python 3.14 runtime.

## Release Steps
1. Create release prep branch from develop.
2. Finalize Docker and Render deploy checklist.
3. Verify required environment variables are defined in Render.
4. Run local checks and smoke run before PR.
5. Open PR to develop and complete review/checks.
6. Merge to develop.
7. Open release PR from develop to main.
8. After main merge, verify Render deployment health and tag v0.2.0.

## Required Environment Variables
- SECRET_KEY
- DEBUG
- ALLOWED_HOSTS
- DATABASE_URL
- RENDER_EXTERNAL_HOSTNAME
- WEB_CONCURRENCY

## Verification Checklist
- Docker image builds successfully.
- Container starts and serves the app.
- Database migrations run against hosted PostgreSQL.
- App login and admin pages load.
- Release branch and PR targets are correct.
- No secrets committed to repository.

## Rollback
- Roll back Render service to last stable deploy.
- Restore previous Render environment variables if needed.
- If code rollback is needed, use a revert or hotfix PR on main.