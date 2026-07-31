# Release Plan - v0.2.0 Neon Migration

## Scopo
Portare l'app da SQLite a PostgreSQL su Neon con flusso Git ordinato e rilascio controllato.

## Non obiettivi
- Migrazione dei dati storici da SQLite

## Stato attuale
- Configurazione env già introdotta (SECRET_KEY, DEBUG, ALLOWED_HOSTS)
- `.env` escluso dal versionamento
- `.env.example` presente
- Milestone Neon creata su GitHub

## Strategia branch
- Lavoro ordinario: `feature/*`, `fix/*`, `chore/*` -> `develop`
- Rilascio: `develop` -> `main`

## Piano operativo
1. Allineare branch locali `main` e `develop`.
2. Creare branch `chore/postgres-neon` da `develop`.
3. Aggiungere dipendenze in `requirements.txt`:
   - `dj-database-url`
   - `psycopg2-binary`
4. Aggiornare `FantaF1/settings.py`:
   - usare `DATABASE_URL` se presente
   - fallback a SQLite se assente
5. Aggiornare `.env.example` con placeholder `DATABASE_URL`.
6. Verifica locale:
   - `python manage.py check`
   - `python manage.py migrate`
   - `python manage.py runserver`
   - test con e senza `DATABASE_URL`
7. Push branch e PR verso `develop` con `Closes #<issue-neon>`.
8. Dopo merge su `develop`, PR `develop -> main`.
9. Tag/release `v0.2.0` dopo verifica finale su `main`.

## Checklist pre-merge
- Nessun segreto nel repository
- Base branch della PR corretta (`develop`)
- Test minimi passati

## Note
Questa cartella e' documentazione di progetto e non fa parte del codice eseguito da Django.