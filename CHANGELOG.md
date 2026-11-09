# Changelog

Tutte le modifiche rilevanti del progetto. Formato basato su [Keep a Changelog](https://keepachangelog.com/it/1.1.0/), versioni secondo [Semantic Versioning](https://semver.org/lang/it/).

## [Unreleased]

### Removed
- Dipendenza `fastf1`.

### Added
- Smoke test che apre ogni pagina del sito, da loggati e da anonimi; fallisce se si aggiunge una rotta senza coprirla.
- Pagina del gioco su `/game/`, aperta a tutti: chi ha già un account trova il link ai suoi campionati al posto delle schede di iscrizione e accesso. `/` la mostra ancora ai visitatori anonimi finché non arriva la home del sito.
- Classifica piloti F1 su `/standings/drivers/`, aperta a tutti: posizione, pilota, scuderia del weekend, vittorie e punti dopo l'ultimo round importato. Raggiungibile dalla home e dal footer.
- Home del sito su `/`, aperta a tutti: banner del gioco, prossimo Gran Premio con gli orari delle sessioni, programma della stagione (i weekend già corsi sono raccolti a parte), link alle classifiche F1 e spazio per le news. Chi ha fatto l'accesso non viene più rimandato ai suoi campionati.
- Area account su `/account/` (voce «Account» nel menu utente): panoramica con username, email, data di iscrizione e link ai propri campionati. Menu laterale su desktop, in alto su mobile.
- Account → Dati personali: si cambiano username, nome e cognome (facoltativi); i nomi giocatore già scelti nei campionati restano gli stessi. L'email si vede ma per ora non si cambia.
- Account → Sicurezza: cambio password con la password attuale, regole visibili e testi in italiano; dopo il cambio si resta collegati.
- Scheda Disiscrizione del campionato, per i giocatori che non sono manager: avvisa che si perdono scelte, risultati e fantamilioni e che non ci si potrà reiscrivere; si conferma con «Sei sicuro?» e scrivendo il nome del campionato, che il server ricontrolla. I manager non possono disiscriversi.
- Scheda Gestione del campionato, visibile solo ai manager: i giocatori iscritti divisi per lega. Un manager può nominare manager un altro giocatore del campionato o togliergli il ruolo, anche a sé stesso; il campionato resta sempre con almeno un manager. Tutti i manager hanno gli stessi poteri.

### Changed
- I miei campionati: un campionato in cui giochi e che gestisci compare una volta sola, con il badge Manager; «Campionati che gestisci» elenca quelli in cui non giochi, con il numero di leghe e di giocatori (prima compariva «1 legha»). La pagina fa lo stesso numero di query qualunque sia il numero di campionati.
- Aprendo un campionato chi gioca va su Gioca → Prossimo weekend, un manager che non gioca sulla scheda Gestione, gli altri sulla classifica generale. Le schede sono Gioca · Classifiche · Info · Gestione (solo per i manager); la scheda Classifiche apre la classifica della propria lega, o la generale per chi non gioca. «Prossimo weekend» è su `/championships/<id>/play/` e la scheda Gioca mostra quante scelte restano da fare nel prossimo weekend.
- Pagine del weekend (dettaglio, scelte e risultati): in cima un percorso cliccabile al posto del link indietro. Dal calendario è campionato › Calendario gare › weekend › sessione; da Prossimo weekend è campionato › Prossimo weekend › sessione, per tornare lì direttamente (anche dopo aver salvato o passando dalla pagina del weekend). Su mobile il percorso va a capo, senza scroll orizzontale.
- Risultati del Grand Prix e della Sprint con la griglia di partenza: durante la gara si vede la griglia con i propri piloti (e nel GP il pupillo); con i risultati la pagina ha due schede, «Ordine d'arrivo» e «Griglia di partenza», per controllare da quale griglia e a quali costi si è scelto.
- Scelta della Sprint con la stessa griglia di partenza del GP: per ogni pilota la scuderia e il solo costo; un clic su un altro pilota sostituisce la scelta. Il riepilogo ora sottrae lo sconto della Sprint Qualifying, come fa il calcolo vero (prima il «Costo totale» mostrava il prezzo pieno), e lo mostra su una riga.
- Scelta del GP con la griglia di partenza al posto della tabella: una casella per pilota nell'ordine della griglia ufficiale (due colonne sfalsate su desktop, una su mobile), con la card del pilota, i costi griglia e classifica e il totale in FM. La casella si sceglie con un clic e si toglie col secondo; il pilota scelto ha un bordo fisso (bianco nel tema scuro, quasi nero nel chiaro), con 2 piloti scelti le altre caselle si spengono e compare la stellina per indicare il pupillo. I piloti fuori budget sono spenti.
- Scelte della qualifica del sabato (weekend regular e sprint): dal via portano ai risultati della qualifica, senza più la pagina in sola lettura. Nei weekend sprint, accanto al titolo, il pulsante «Risultati Sprint», ombreggiato finché la Sprint non ha risultati.
- Scelte del GP e della Sprint: si aprono solo quando si può scegliere. Senza griglia rimandano alla pagina del weekend, dal via portano ai risultati della gara. Nel GP, accanto al titolo c'è il pulsante «Risultati qualifica», ombreggiato finché la classifica non è pubblicata. Nuovo stile unico per le azioni non ancora disponibili.
- Risultati della qualifica dei weekend sprint (quella a slot), sulla stessa pagina: i propri piloti per slot e i livelli Q1, Q2 e Top 3 con ✓ o ✗, a cascata, due volte: sulla classifica della qualifica (con i punti qualifica) e sulla griglia del GP (con lo sconto e il moltiplicatore sul GP).
- Risultati della qualifica del sabato (weekend regular), nuova pagina del campionato: classifica ufficiale con i tempi Q1, Q2 e Q3 e il proprio pronostico (posizione, punti qualifica e, con la griglia del GP, sconto o malus e moltiplicatore sul GP). Si apre dal via: «Qualifica in corso» per 2 ore, poi «Risultati non ancora pubblicati» finché la classifica non viene importata.
- Risultati del Grand Prix e della Sprint: la pagina si apre dal via della gara e mostra subito la propria scelta. Dice «Gara in corso» per 3 ore dal via nel GP e per 2 nella Sprint, poi «Risultati non ancora pubblicati» finché i risultati non vengono importati, poi la classifica come prima. Prima del via rimanda alla pagina del weekend.
- «Crea campionato» si apre in un pop-up sopra I miei campionati; se il form ha errori la pagina si ricarica col pop-up aperto. Senza JavaScript resta la pagina a parte. Con un nome già usato nell'anno compare un solo messaggio d'errore, in italiano (prima ne comparivano due).
- Testo più grande e una scala tipografica comune: testo normale a 16px, pulsanti, menu, schede e campi dei form a 16px, note e dati secondari a 14px; titoli di pagina, di card e di sezione con le stesse misure in tutto il sito. Su mobile le pagine Info e Calendario non scorrono più in orizzontale.
- Colore ed etichetta della scuderia di ogni pilota sono quelli del weekend (roster `WeekendParticipant`), non quelli di inizio stagione: chi cambia sedile a stagione in corso ha il colore giusto nelle pagine di scelta, nei risultati e in Le mie scelte. Il limite di scelte per scuderia della qualifica non cambia.
- Indirizzi delle pagine in inglese (`/championships/…`, `…/standings/…`, `…/weekends/…`, `/auth/register/`); i nomi delle URL non cambiano. I vecchi indirizzi della lista campionati, della pagina di un campionato e dei link d'invito rimandano ai nuovi.
- Header e footer uguali su tutto il sito. Nell'header solo il logo, che porta alla home, il tema e Accedi/Registrati oppure il menu utente (Account, I miei campionati, Esci), anche su mobile; Classifiche F1 e Il gioco sono nella home e nel footer. Menu accessibile da tastiera e screen reader (Escape chiude, `aria-expanded`), messaggi annunciati agli screen reader.
- Pagine di accesso e iscrizione rifatte: testi in italiano, regole della password visibili prima di inviare il form. Dopo l'iscrizione si entra subito e si va ai propri campionati (o all'invito da cui si arrivava), senza ripassare dal login.
- Risultati di qualifiche, sprint e gare presi da OpenF1 invece che da Jolpica (e da FastF1 per le qualifiche sprint). OpenF1 li pubblica circa 30 minuti dopo la fine della sessione; Jolpica resta per anagrafiche, calendario e classifica piloti. I piloti si riconoscono dal numero di gara. I non classificati vanno in fondo all'ordine di arrivo, come faceva Jolpica.
- `RaceResult.starting_grid` viene dalla griglia ufficiale già importata da `insert_starting_grid`.
- Airflow: l'attesa dei risultati scende da 36 a 6 ore.

### Added
- Airflow: DAG `fantaf1_pair_events`, elabora una coppia qualifica + gara dello stesso tipo per run. Attende l'`eligible_after` di ogni evento con un sensore deferrable (`DateTimeSensorAsync`), poi controlla ogni 15 minuti, per al massimo 36 ore, se i risultati sono pubblicati. A fine coppia lancia da solo la run successiva; la prima va avviata a mano.
- Comando `next_pair_events`: restituisce la prima coppia qualifica + gara con eventi non ancora processati, errori compresi, anche se l'evento è nel futuro.
- Airflow: servizio `airflow-triggerer` nel `docker-compose.yaml`, necessario per i sensori deferrable.

### Changed
- `mark()` non trasforma più l'attesa in errore dopo un numero massimo di tentativi: il limite è il timeout del sensore e `attempts` è solo un contatore.
- `process_pending_events` spostato in `commands/manual/`: non è più eseguibile con `manage.py`.

### Removed
- DAG `fantaf1_qualifying` e `fantaf1_race` (polling ogni 15 minuti) e comando `next_pending_event`.
- Costante `MAX_WAITING_ATTEMPTS`.

### Fixed
- Iscrizione: le regole della password (lunghezza minima, password comuni, solo numeri, troppo simile ai dati dell'account) vengono applicate davvero; prima erano solo configurate.
- Accesso: un solo messaggio per utente inesistente e password errata, così la pagina non rivela quali account esistono.
- `insert_quali_result`: la qualifica sprint viene importata solo da FastF1, senza richiedere la qualifica regular su Jolpica; se i risultati sprint non sono ancora disponibili il comando restituisce il codice 3.
- `MAX_WAITING_ATTEMPTS` portato da 10 a 32.
- Pagine dei risultati gara: chi non ha effettuato l'accesso viene mandato al login invece di ricevere un errore 500.
- Pagine del weekend per chi non è iscritto al campionato (es. un manager che non gioca): le pagine di scelta rimandano al weekend con un messaggio invece di dare un errore 500, i risultati mostrano solo la classifica ufficiale e i pulsanti «Scegli» sono nascosti.
- Classifiche: sucate e magate contano anche il valore limite, come da regolamento (sucata 5 punti o meno, magata 43 punti o più). Prima una gara da 5 punti non era una sucata e una da 43 non era una magata.
- Date, orari, conti alla rovescia ed errori dei form in italiano e in ora italiana su tutte le pagine (prima in inglese e in UTC).
- Build del CSS: Tailwind legge solo template e JS, quindi `main.css` è lo stesso da qualunque cartella si lanci la build (prima, dalla radice del repo, entravano classi inutili prese dai file Python e Markdown).
- Una qualifica in errore non blocca più in silenzio le gare successive: la dipendenza qualifica → gara è un arco del DAG e un fallimento è visibile in Airflow.

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
