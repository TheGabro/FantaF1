# Chat Context Template

Copia/incolla questo blocco quando apri una nuova chat o cambi PC/agent.

## Contesto progetto
- Obiettivo corrente:
- Branch corrente:
- Base branch della PR:
- Milestone:
- Issue collegata:
- Ultimo step completato:
- Prossimo step:

## Vincoli
- Flusso PR: `feature/fix/chore -> develop`, release `develop -> main`
- Nessun segreto in repo (`.env` non tracciato)
- No migrazione dati SQLite (se non deciso diversamente)

## Verifiche da mantenere
- `python manage.py check`
- `python manage.py migrate`
- `python manage.py runserver`
