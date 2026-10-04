# Changelog

Tutte le modifiche rilevanti del progetto. Formato basato su [Keep a Changelog](https://keepachangelog.com/it/1.1.0/), versioni secondo [Semantic Versioning](https://semver.org/lang/it/).

## [Unreleased]

## [0.4.0] - 2026-10-04

### Added
- Modello `RaceStartingGrid`: griglia di partenza ufficiale di ogni gara (penalità incluse), modificabile dall'admin per correggere a mano le penalità tardive.
- Sorgente `openF1Source` e comando `insert_starting_grid` per importare la griglia da OpenF1 (`/v1/starting_grid`).
- Airflow: il DAG `fantaf1_qualifying` importa la griglia dopo i risultati di qualifica; l'evento passa a `processed` solo quando anche la griglia è disponibile.
- Comando interattivo `set_seat`: sposta un pilota in un altro team dal round indicato in poi, con l'eventuale pilota sostituito (`WeekendParticipant`).
- Airflow: secondo stack `dev` sulla stessa VM, configurabile da `.env` (`COMPOSE_PROJECT_NAME`, `AIRFLOW_PORT`, `IMAGE_TAG`).

### Changed
- Il costo dei piloti per Sprint e Grand Prix si calcola dalla griglia di partenza ufficiale invece che dalla posizione in qualifica.
- Airflow: rimossi i `container_name` fissi dal `docker-compose.yaml` per permettere più stack in parallelo.

### Fixed
- I piloti senza risultato in qualifica ma presenti in griglia ora sono selezionabili.
- Griglia OpenF1 non ancora pubblicata (404) o API bloccata durante una sessione live (401): l'evento resta in attesa e viene ritentato invece di andare in errore.

## [0.3.1] - 2026-09-23

### Added
- `WeekendParticipant`: roster dei piloti per ogni weekend, con sincronizzazione a inizio stagione (`sync_weekend_participants`).
- Limite di scelta per scuderia nella qualifica regular.
- Comando `import_drivers` per importare i piloti di una stagione.
- Airflow: DAG `fantaf1_qualifying` e `fantaf1_race` per elaborare automaticamente qualifiche e gare (risultati, consolidamento crediti, punteggi), con scheduling solo nei giorni di gara.
- Comandi `next_pending_event`, `mark_event`, `process_pending_events`, `rollback_event`.
- Deploy di Airflow sulla VM Oracle.
- Restyling completo del frontend (design system Tailwind, tema chiaro/scuro, pagine di scelta piloti e risultati).
- Campionati gestiti visibili nella dashboard utente.

### Changed
- Sorgenti dati (`jolpicaSource`, `fastf1Source`) spostate in `services/sources`; logica dei piloti spostata in `services/drivers.py`.

### Fixed
- Errore corretto quando i risultati di qualifica/gara non sono ancora disponibili.
- `qualifying_ready` restituisce true solo se la qualifica collegata è `PROCESSED`.
- Nome della variabile d'ambiente della secret key e configurazione di `airflow-init`.

### Removed
- Rimossi dal repository file generati: `db.sqlite3`, cache di graphify, `__pycache__`, `.DS_Store`.

## [0.3.0] - 2026-08-20

### Added
- Modello `EventProcessingStatus`, inizializzato da `import_start_season`.
- `point_modifier` su `PlayerRaceResult`, usato nel calcolo del punteggio (bonus sprint).

## [0.2.1] - 2026-08-13

### Added
- Bonus sulla scelta della sprint qualifying.

## [0.2] - 2026-07-31

### Changed
- Migrazione a PostgreSQL (Neon) e deploy su Render con Docker.

## [0.1] - 2026-07-30

### Added
- Prima versione funzionante con le funzionalità base.

[Unreleased]: https://github.com/TheGabro/FantaF1/compare/v0.4.0...develop
[0.4.0]: https://github.com/TheGabro/FantaF1/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/TheGabro/FantaF1/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/TheGabro/FantaF1/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/TheGabro/FantaF1/compare/v0.2...v0.2.1
[0.2]: https://github.com/TheGabro/FantaF1/compare/v0.1...v0.2
[0.1]: https://github.com/TheGabro/FantaF1/releases/tag/v0.1
