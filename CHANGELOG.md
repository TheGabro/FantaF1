# Changelog

Tutte le modifiche rilevanti del progetto. Formato basato su [Keep a Changelog](https://keepachangelog.com/it/1.1.0/), versioni secondo [Semantic Versioning](https://semver.org/lang/it/).

## [Unreleased]

### Added
- Smoke test che apre ogni pagina del sito, da loggati e da anonimi; fallisce se si aggiunge una rotta senza coprirla.
- Pagina del gioco su `/game/`, aperta a tutti: chi ha già un account trova il link ai suoi campionati al posto delle schede di iscrizione e accesso. `/` la mostra ancora ai visitatori anonimi finché non arriva la home del sito.
- Classifica piloti F1 su `/standings/drivers/`, aperta a tutti: posizione, pilota, scuderia del weekend, vittorie e punti dopo l'ultimo round importato. Raggiungibile dalla home e dal footer.
- Home del sito su `/`, aperta a tutti: banner del gioco, prossimo Gran Premio con gli orari delle sessioni, programma della stagione (i weekend già corsi sono raccolti a parte), link alle classifiche F1 e spazio per le news. Chi ha fatto l'accesso non viene più rimandato ai suoi campionati.
- Area account su `/account/` (voce «Account» nel menu utente): panoramica con username, email, data di iscrizione e link ai propri campionati. Menu laterale su desktop, in alto su mobile.
- Account → Dati personali: si cambiano username, nome e cognome (facoltativi); i nomi giocatore già scelti nei campionati restano gli stessi. L'email si vede ma per ora non si cambia.
- Account → Sicurezza: cambio password con la password attuale, regole visibili e testi in italiano; dopo il cambio si resta collegati.

### Changed
- I miei campionati: un campionato in cui giochi e che gestisci compare una volta sola, con il badge Manager; «Campionati che gestisci» elenca quelli in cui non giochi, con il numero di leghe e di giocatori (prima compariva «1 legha»). La pagina fa lo stesso numero di query qualunque sia il numero di campionati.
- Aprendo un campionato si vedono le classifiche: la classifica della propria lega per chi gioca, la generale per gli altri, anche a stagione finita. Le schede sono Classifiche · Gioca · Info; «Prossimo weekend» è su `/championships/<id>/play/` e la scheda Gioca mostra quante scelte restano da fare nel prossimo weekend.
- Indirizzi delle pagine in inglese (`/championships/…`, `…/standings/…`, `…/weekends/…`, `/auth/register/`); i nomi delle URL non cambiano. I vecchi indirizzi della lista campionati, della pagina di un campionato e dei link d'invito rimandano ai nuovi.
- Header e footer uguali su tutto il sito. Nell'header solo il logo, che porta alla home, il tema e Accedi/Registrati oppure il menu utente (Account, I miei campionati, Esci), anche su mobile; Classifiche F1 e Il gioco sono nella home e nel footer. Menu accessibile da tastiera e screen reader (Escape chiude, `aria-expanded`), messaggi annunciati agli screen reader.
- Pagine di accesso e iscrizione rifatte: testi in italiano, regole della password visibili prima di inviare il form. Dopo l'iscrizione si entra subito e si va ai propri campionati (o all'invito da cui si arrivava), senza ripassare dal login.

### Fixed
- Iscrizione: le regole della password (lunghezza minima, password comuni, solo numeri, troppo simile ai dati dell'account) vengono applicate davvero; prima erano solo configurate.
- Accesso: un solo messaggio per utente inesistente e password errata, così la pagina non rivela quali account esistono.
- `insert_quali_result`: la qualifica sprint viene importata solo da FastF1, senza richiedere la qualifica regular su Jolpica; se i risultati sprint non sono ancora disponibili il comando restituisce il codice 3.
- `MAX_WAITING_ATTEMPTS` portato da 10 a 32.
- Airflow: i DAG `fantaf1_qualifying` e `fantaf1_race` girano tutti i giorni.
- Pagine dei risultati gara: chi non ha effettuato l'accesso viene mandato al login invece di ricevere un errore 500.
- Date, orari, conti alla rovescia ed errori dei form in italiano e in ora italiana su tutte le pagine (prima in inglese e in UTC).
- Build del CSS: Tailwind legge solo template e JS, quindi `main.css` è lo stesso da qualunque cartella si lanci la build (prima, dalla radice del repo, entravano classi inutili prese dai file Python e Markdown).

## [0.4.1] - 2026-10-12

### Added
- Comando per ricalcolare i costi delle scelte gara esistenti in base alla griglia di partenza.

### Changed
- Calcolo dei costi Sprint e Grand Prix aggiornato per applicare le soglie delle posizioni in griglia e dei passaggi Q1/Q2.
- Dashboard e informazioni del campionato chiariscono l'impatto della qualifica e della posizione in griglia.

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

[Unreleased]: https://github.com/TheGabro/FantaF1/compare/v0.4.1...develop
[0.4.1]: https://github.com/TheGabro/FantaF1/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/TheGabro/FantaF1/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/TheGabro/FantaF1/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/TheGabro/FantaF1/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/TheGabro/FantaF1/compare/v0.2...v0.2.1
[0.2]: https://github.com/TheGabro/FantaF1/compare/v0.1...v0.2
[0.1]: https://github.com/TheGabro/FantaF1/releases/tag/v0.1
