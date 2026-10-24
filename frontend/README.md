# Frontend FantaF1

Il frontend è server-rendered: template Django in `fantaApp/templates/fantaApp/` + asset in `fantaApp/static/fantaApp/`.
Questa cartella contiene la toolchain CSS (Tailwind v4, CLI standalone — niente Node/npm); questo README raccoglie
anche le convenzioni del frontend: [mappa del sito e URL](#mappa-del-sito-e-url),
[organizzazione delle view](#organizzazione-delle-view) e [glossario dei testi](#glossario-dei-testi).

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

## Mappa del sito e URL

FantaF1 è un sito di Formula 1 in cui il gioco è una delle sezioni. Nella colonna *Stato*: **c'è** = la pagina
esiste già (con #89 ha preso l'indirizzo in inglese), **nuova** = da fare nell'issue indicata, **futura** = più avanti.

| Sezione | Pagina | URL | Nome URL | Stato |
|---|---|---|---|---|
| Sito | Home: stagione F1, classifiche, news, banner del gioco | `/` | `home` | c'è |
| | Classifica piloti F1 | `/standings/drivers/` | `f1_drivers_standings` | c'è |
| | Classifica costruttori F1 | `/standings/constructors/` | `f1_constructors_standings` | futura (#104) |
| | News | `/news/`, `/news/<slug>/` | `news_list`, `news_detail` | futura (#111) |
| | Chi siamo, privacy, termini, supportaci | `/about/`, `/privacy/`, `/terms/`, `/support/` | `about`, `privacy`, `terms`, `support` | futura (#107–#110) |
| Il gioco | Presentazione del gioco | `/game/` | `game` | c'è, oggi su `/` (#90) |
| | Regolamento | `/game/rules/` | `game_rules` | c'è, oggi nella scheda Info (#81) |
| Accesso | Accedi, registrati, esci | `/auth/login/`, `/auth/register/`, `/auth/logout/` | `login`, `register`, `logout` | c'è |
| Account | Panoramica | `/account/` | `account` | c'è |
| | Dati personali | `/account/profile/` | `account_profile` | nuova (#97) |
| | Sicurezza (password) | `/account/security/` | `account_security` | nuova (#98) |
| | Dati e privacy | `/account/privacy/` | `account_privacy` | futura (#106) |
| I miei campionati | Campionati in corso | `/championships/` | `user_dashboard` | c'è |
| | Cerca un campionato | `/championships/search/` | `championship_search` | nuova (#72) |
| | Archivio | `/championships/archive/` | `championship_archive` | nuova (#100) |
| | Crea un campionato | `/championships/create/` | `create_championship` | c'è |
| | Iscriviti | `/championships/<id>/join/` | `join_championship` | c'è |
| | Invito (nascosto per ora) | `/championships/invite/`, `/championships/invite/<token>/` | `invite_redeem`, `invite_accept` | c'è |
| Campionato | Ingresso: le classifiche | `/championships/<id>/` | `championship_dashboard` | c'è, oggi apre «Prossimo weekend» (#113) |
| | Classifiche: lega, generale, qualifiche, sprint | `/championships/<id>/standings/league/`, `…/general/`, `…/qualifying/`, `…/sprint/` | `championship_league_standings`, `…_general_…`, `…_qualifying_…`, `…_sprint_…` | c'è |
| | Gioca: prossimo weekend | `/championships/<id>/play/` | `championship_next_weekend` | c'è, nome nuovo (#113) |
| | Gioca: le mie scelte | `/championships/<id>/my-choices/` | `championship_my_choices` | c'è |
| | Gioca: calendario | `/championships/<id>/calendar/` | `championship_calendar` | c'è |
| | Info | `/championships/<id>/info/` | `championship_info` | c'è |
| Weekend | Dettaglio del weekend | `/championships/<id>/weekends/<id>/` | `weekend_details` | c'è |
| | Scelte e risultati delle sessioni | `/championships/<id>/weekends/<id>/qualifying/…`, `…/race/…` | invariati | c'è |

Le schede del campionato sono in quest'ordine: **Classifiche · Gioca · Info** (#113).

Regole per gli URL:

- percorsi in inglese, minuscoli, parole separate da trattino, barra finale;
- il nome dell'URL (`name=`) non cambia quando cambia il percorso: template e test usano solo i nomi
  (`{% url %}`, `reverse()`);
- gli indirizzi vecchi che possono stare in segnalibri e chat (`/dashboard/account/`,
  `/dashboard/championships/<id>/`, `/campionati/invito/<token>/`) rimandano a quelli nuovi con un redirect
  permanente (`legacy_…` in `fantaApp/urls.py`);
- ogni pagina nuova va aggiunta allo smoke test (`PageSmokeTests` in `fantaApp/tests.py`), che altrimenti fallisce.

## Organizzazione delle view

Un modulo per pagina, raggruppati per sezione del sito. Gli helper usati da più pagine della stessa sezione stanno
in un `_shared.py`.

```
fantaApp/views/
  site/           home, classifiche F1, pagine informative
  game/           presentazione del gioco, regolamento
  auth.py         accesso e registrazione (c'è già)
  account/        panoramica, dati personali, sicurezza, privacy
  championships/  i miei campionati, ricerca, archivio, creazione, iscrizione e inviti
  championship/   sezioni del campionato (classifiche, gioca, info) + _shared.py
  weekend/        dettaglio, scelte e risultati del weekend + _shared.py
```

- `dashboard.py` e `weekend.py` si dividono in questi pacchetti con #54 e #55; le pagine nuove nascono già al loro
  posto.
- Moduli di qualche centinaio di righe al massimo; mai oltre 1000.
- JavaScript solo in `fantaApp/static/fantaApp/js/`, niente `<script>` dentro i template.

## Glossario dei testi

Le pagine sono in italiano; codice, URL e backend restano in inglese. Per ogni concetto si usa un solo termine.

| Concetto | Si scrive | Non si scrive | Note |
|---|---|---|---|
| Valuta del gioco | fantamilioni | crediti, credits | Deciso il 21/10/2026. Nel codice resta `credit` (`available_credit`). |
| Gara della domenica | Gran Premio; GP in forma breve | Grand Prix, gara | Deciso il 21/10/2026. Es. «GP d'Italia». |
| Qualifica del venerdì nei weekend sprint | Qualifiche Sprint | Sprint Qualifying, Sprint Shootout | Deciso il 21/10/2026. |
| Qualifica del sabato | Qualifiche | Qualifying | |
| Gara sprint | Sprint | Sprint Race | |
| Tipo di weekend | weekend sprint, weekend classico | Weekend Regular | |
| Griglia | griglia di partenza; «Griglia» nelle tabelle | Grid | |
| Posizione | posizione; «Pos.» nelle tabelle | | |
| Posizioni guadagnate o perse | «+/−» nelle tabelle, con ▲ ▼ | Delta | |
| Piloti scelti per una gara | scelta | pick | |
| Previsione sulle qualifiche | pronostico | | |
| Pilota preferito con sconto | pupillo | | |
| Gruppo di giocatori di un campionato | lega | | |
| Chi gestisce un campionato | manager | admin | «Admin» è solo il pannello di amministrazione del sito. |
| Gran Premio sopra i 43 punti, gara sotto i 5 | magata, sucata | | Gergo del gioco: resta. |

Regole di scrittura:

- si dà del tu al giocatore («Scegli i tuoi piloti»);
- nei testi dinamici singolare e plurale si scrivono per intero: `pluralize` aggiunge solo un suffisso e
  «legh» + «a» dà «legha»;
- date e orari in italiano e in ora italiana (#91).
