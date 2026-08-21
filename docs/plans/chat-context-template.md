# Chat Context Template

Use this template at the start of a new chat.

## Current Context
- Goal:
- Current branch:
- PR base branch:
- Milestone:
- Linked issue:
- Last completed step:
- Next step:

## Deployment Scope
- Platform: Render
- Artifact: Docker
- Release flow: develop to main
- Release tag target: main

## Required Constraints
- SQLite is local fallback only.
- Hosted runtime uses PostgreSQL via DATABASE_URL.
- No SQLite historical data migration unless explicitly approved.
- No secrets in repository.
- Keep Django Python 3.14 compatibility workaround active until framework upgrade.

## Environment Variables To Confirm
- SECRET_KEY
- DEBUG
- ALLOWED_HOSTS
- DATABASE_URL
- RENDER_EXTERNAL_HOSTNAME
- WEB_CONCURRENCY

## Quick Verification Commands
- python manage.py check
- python manage.py migrate
- python manage.py runserver

## Ready To Merge Checklist
- PR targets correct base branch.
- Docker and Render checks completed.
- Smoke checks passed for login and admin.
- Release notes updated for v0.2.0
