# Frontend FantaF1

Il frontend è server-rendered: template Django in `fantaApp/templates/fantaApp/` + asset in `fantaApp/static/fantaApp/`.
Questa cartella contiene solo la toolchain CSS (Tailwind v4, CLI standalone — niente Node/npm).

## Build del CSS

Il sorgente è `input.css`, l'output compilato è `../fantaApp/static/fantaApp/css/main.css` (committato nel repo:
il sito funziona anche senza rifare la build).

Serve la CLI standalone in `bin/tailwindcss.exe` (non committata). Per scaricarla:

```powershell
Invoke-WebRequest -Uri "https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-windows-x64.exe" -OutFile "bin\tailwindcss.exe"
```

Build una tantum:

```powershell
.\build.ps1
```

Build continua durante lo sviluppo (ricompila a ogni modifica di template/CSS):

```powershell
.\build.ps1 -Watch
```

## Tema e design system

- Doppio tema chiaro/scuro pilotato da `data-theme` su `<html>` (toggle nella navbar, persistito in `localStorage`,
  default dalla preferenza di sistema).
- Token semantici (`--bg-surface`, `--text-ink`, `--accent`, ...) definiti in `input.css` e mappati su utility
  Tailwind (`bg-surface`, `text-ink`, `bg-accent`, ...).
- Colori scuderia: classi `team-<short_name slug>` (es. `team-fer`, `team-red`) che impostano la variabile `--team`,
  usata da `.team-bar` e `.team-chip`. Nei template: `team-{{ driver.team.short_name|slugify }}`.

## Server di sviluppo isolato

Per provare il sito senza toccare `db.sqlite3` reale, usare `dev_settings.py` (repo root), che lavora su una copia
del database in `frontend/dev_db.sqlite3` (creata al primo avvio, ignorata da git):

```powershell
..\.venv\Scripts\python.exe ..\manage.py runserver 8137 --settings=dev_settings
```
