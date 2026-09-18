# Graph Report - FantaF1  (2026-09-17)

## Corpus Check
- 89 files · ~26,356 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 628 nodes · 1132 edges · 108 communities (28 shown, 80 thin omitted)
- Extraction: 79% EXTRACTED · 21% INFERRED · 0% AMBIGUOUS · INFERRED: 233 edges (avg confidence: 0.94)
- Token cost: 53,091 input · 0 output

## Community Hubs (Navigation)
- Season Import & Result Insert Commands
- Championship & Credit Costs
- League & Grand Prix Choice Tests
- Forms, Users & Hello DAG
- Qualifying Forms & Cost Rules
- Event Processing Commands & Service
- Home & Dashboard Templates
- Qualifying Bonus Logic
- Django Admin Config
- Score, Credit & Rollback Commands
- Player Results & Credit Consolidation
- Race Choice JS
- Deployment & Release Planning
- Airflow Compose Stack
- Player Choice Models
- Driver & Team Lookup
- Credit Consolidation Tests
- Django Compat Patch
- Import Drivers Command
- PostgreSQL Database Config
- Consolidate Credits Command
- Sync Weekend Participants
- Regular Qualifying Bonus Tests
- Template Dict Filters
- Custom User Manager
- Schedule Dedup Migration
- Dev vs Prod Settings
- Auth Templates
- manage.py Entrypoint (FantaF1)
- FantaF1 Project & FastF1
- manage.py Entrypoint
- SQLite Local Fallback
- Driver Number Migration
- Community 33
- Community 34
- Community 35
- Community 36
- Community 37
- Community 38
- Community 39
- Community 40
- Community 41
- Community 42
- Community 43
- Community 44
- Community 45
- Community 46
- Community 47
- Community 48
- Community 49
- Community 50
- Community 51
- Community 52
- Community 53
- Community 54
- Community 55
- Community 56
- Community 57
- Community 58
- Community 59
- Community 60
- Community 61
- Community 62
- Community 63
- Community 64
- Community 65
- Community 66
- Community 67
- Community 68
- Community 69
- Community 70
- Community 71
- Community 72
- Community 73
- Community 74
- Community 75
- Community 76
- Community 77
- Community 78
- Community 79
- Community 80
- Community 81
- Community 82
- Community 83
- Community 84
- Community 85
- Community 86
- Community 87
- Community 88
- Community 89
- Community 90
- Community 93
- Community 95
- Community 100
- Community 101
- Community 102
- Community 103
- Community 104
- Community 105
- Community 106
- Community 107

## God Nodes (most connected - your core abstractions)
1. `Weekend` - 37 edges
2. `Driver` - 35 edges
3. `PlayerScoringTests` - 28 edges
4. `Race` - 27 edges
5. `PlayerRaceChoice` - 26 edges
6. `Qualifying` - 24 edges
7. `QualifyingResult` - 22 edges
8. `Meta` - 20 edges
9. `GrandPrixChoiceTests` - 20 edges
10. `CreditConsolidationTests` - 20 edges

## Surprising Connections (you probably didn't know these)
- `Semantic Design Tokens` --shares_data_with--> `Base Template (fantaApp/base.html)`  [INFERRED]
  frontend/README.md → fantaApp/templates/fantaApp/base.html
- `fantaf1 Render Web Service` --conceptually_related_to--> `Render (Hosting Platform)`  [INFERRED]
  render.yaml → docs/plans/chat-context-template.md
- `Django (requirements)` --conceptually_related_to--> `fantaf1 Render Web Service`  [INFERRED]
  requirements.txt → render.yaml
- `dj-database-url (requirements-dev)` --conceptually_related_to--> `PostgreSQL via DATABASE_URL`  [INFERRED]
  requirements-dev.txt → docs/plans/release-v0.2-neon.md
- `dj-database-url (requirements)` --shares_data_with--> `dj-database-url (requirements-dev)`  [INFERRED]
  requirements.txt → requirements-dev.txt

## Import Cycles
- 3-file cycle: `fantaApp/services/__init__.py -> fantaApp/services/player_choices.py -> fantaApp/services/costs.py -> fantaApp/services/__init__.py`
- 3-file cycle: `fantaApp/services/__init__.py -> fantaApp/services/player_choices.py -> fantaApp/services/bonuses.py -> fantaApp/services/__init__.py`

## Hyperedges (group relationships)
- **Championship Event Flow Templates** — fantaapp_templates_fantaapp_championship_flow_base_template, fantaapp_templates_fantaapp_weekend_details_template, fantaapp_templates_fantaapp_race_results_template, fantaapp_templates_fantaapp_regular_race_choice_template, fantaapp_templates_fantaapp_regular_race_qualifying_choice_template, fantaapp_templates_fantaapp_regular_race_qualifying_multi_choice_template, fantaapp_templates_fantaapp_sprint_race_choice_template, fantaapp_templates_fantaapp_sprint_race_qualifying_choice_template [EXTRACTED 1.00]
- **Tailwind CSS Build and Theming Pipeline** — frontend_readme_tailwind_css_toolchain, frontend_readme_design_tokens, fantaapp_templates_fantaapp_base_static_main_css [INFERRED 0.80]
- **Deployment Environment Variables Alignment** — render_environment_variables, docs_plans_chat_context_template_required_environment_variables, docs_plans_release_v0_2_neon_required_environment_variables [INFERRED 0.90]
- **Grid-Based Driver Selection Pattern** — fantaapp_templates_fantaapp_regular_race_choice_template, fantaapp_templates_fantaapp_sprint_race_choice_template, fantaapp_static_fantaapp_js_race_choice [INFERRED 0.90]
- **Multi-Slot Qualifying Prediction Pattern** — fantaapp_templates_fantaapp_regular_race_qualifying_multi_choice_template, fantaapp_templates_fantaapp_sprint_race_qualifying_choice_template, fantaapp_static_fantaapp_js_select_dedupe, fantaapp_templatetags_dict_extras_module [INFERRED 0.90]
- **Airflow 3 task execution flow (scheduler -> Execution API on api-server, JWT-signed)** — airflow_docker_compose_airflow_scheduler, airflow_docker_compose_airflow_webserver, airflow_docker_compose_execution_api, airflow_docker_compose_jwt_secret, airflow_docker_compose_localexecutor [EXTRACTED 1.00]
- **Airflow FantaF1 compose stack (services sharing x-airflow-common)** — airflow_docker_compose_airflow_common, airflow_docker_compose_airflow_init, airflow_docker_compose_airflow_webserver, airflow_docker_compose_airflow_scheduler, airflow_docker_compose_airflow_dag_processor, airflow_docker_compose_postgres [EXTRACTED 1.00]

## Communities (108 total, 80 thin omitted)

### Community 0 - "Season Import & Result Insert Commands"
Cohesion: 0.07
Nodes (33): Command, atomic, BaseCommand, Management command: `python manage.py import_start_season [--season <year>]…, Command, get_best_lap(), atomic, BaseCommand (+25 more)

### Community 1 - "Championship & Credit Costs"
Cohesion: 0.10
Nodes (34): Championship, apply_race_credit_change(), Applica il credit_change ai costi dei piloti. - credit_change positivo = malus…, get_player_reserved_credit(), get_player_spendable_credit(), get_sprint_race_driver_options(), Restituisce le opzioni pilota per la gara sprint., Restituisce i crediti già prenotati dal player per gare non ancora concluse. (+26 more)

### Community 2 - "League & Grand Prix Choice Tests"
Cohesion: 0.09
Nodes (10): ChampionshipManager, League, GrandPrixChoiceTests, PlayerScoringTests, SprintRaceChoiceTests, championship_dashboard(), create_championship(), login_required (+2 more)

### Community 3 - "Forms, Users & Hello DAG"
Cohesion: 0.07
Nodes (15): AbstractUser, hello_f1(), dag, datetime, ChampionshipForm, ChampionshipPlayerForm, CustomUserRegistrationForm, LeagueForm (+7 more)

### Community 4 - "Qualifying Forms & Cost Rules"
Cohesion: 0.10
Nodes (24): RegularQualifyingForm, SprintQualifyingForm, Driver, get_cost_from_grid(), get_cost_from_standings_position(), get_race_driver_options(), get_regular_race_cost(), get_regular_race_cost_breakdown() (+16 more)

### Community 5 - "Event Processing Commands & Service"
Cohesion: 0.11
Nodes (15): Command, BaseCommand, Command, BaseCommand, Management command: `python manage.py process_pending_events` Elabora gli…, atomic, EventProcessingStatus, Status (+7 more)

### Community 6 - "Home & Dashboard Templates"
Cohesion: 0.09
Nodes (27): Base Template (fantaApp/base.html), URL Route: home, URL Route: login, URL Route: logout, URL Route: register, Static Asset: fantaApp/js/app.js, Static Asset: fantaApp/css/main.css, Theme Toggle (light/dark, localStorage) (+19 more)

### Community 7 - "Qualifying Bonus Logic"
Cohesion: 0.13
Nodes (24): QualifyingResult, get_qualifying_multichoice_bonus(), get_qualifying_multichoice_bonus_rule(), get_qualifying_sprint_bonus_rule(), get_race_bonus(), get_regular_qualifying_bonus(), get_regular_qualifying_bonus_rule(), get_regular_qualifying_choice_bonus() (+16 more)

### Community 8 - "Django Admin Config"
Cohesion: 0.13
Nodes (22): ChampionshipAdmin, ChampionshipManagerInline, ChampionshipPlayerAdmin, ChampionshipPlayerInline, CustomUserAdmin, DriverStandingAdmin, LeagueInline, PlayerQualifyingChoiceAdmin (+14 more)

### Community 9 - "Score, Credit & Rollback Commands"
Cohesion: 0.14
Nodes (12): Command, BaseCommand, Management command: `python manage.py compute_race_score --season <year>…, Management command: `python manage.py consolidate_player_credits --season…, Command, BaseCommand, Management command: `python manage.py rollback_event --season <year> --round…, Event (+4 more)

### Community 10 - "Player Results & Credit Consolidation"
Cohesion: 0.16
Nodes (14): ChampionshipPlayer, PlayerRaceChoice, PlayerRaceResult, RaceResult, consolidate_race_credits_if_started(), Consolida (addebita definitivamente) i crediti prenotati per le scelte di UNA…, compute_player_score_per_race(), compute_race_points() (+6 more)

### Community 11 - "Race Choice JS"
Cohesion: 0.22
Nodes (17): isSelected(), pupilloId(), refresh(), refreshRows(), renderHiddenInputs(), renderPanel(), rowById(), selectedCardHtml() (+9 more)

### Community 12 - "Deployment & Release Planning"
Cohesion: 0.15
Nodes (14): Chat Context Template, Docker (Deployment Artifact), v0.2.0 Ready-to-Merge Checklist, Render (Hosting Platform), Required Environment Variables, Docker (Deployment Artifact), Release Plan v0.2.0 (Docker + Render), Render (Hosting Platform) (+6 more)

### Community 13 - "Airflow Compose Stack"
Cohesion: 0.30
Nodes (12): x-airflow-common (shared Airflow service template), airflow-dag-processor, airflow-init (db migrate + passwords.json bootstrap), airflow-scheduler, airflow-webserver (api-server, port 8080), Airflow 3 Execution API (task-to-server communication), FANTAF1_DATABASE_URL (bridge to FantaF1 Django DB), Shared JWT secret (AIRFLOW__API_AUTH__JWT_SECRET) (+4 more)

### Community 14 - "Player Choice Models"
Cohesion: 0.24
Nodes (9): AbstractPlayerChoice, DriverStanding, Meta, PlayerQualifyingChoice, PlayerQualifyingMultiChoice, PlayerSprintQualifyingChoice, Base comune: tiene traccia di chi sceglie cosa., WeekendParticipant (+1 more)

### Community 15 - "Driver & Team Lookup"
Cohesion: 0.36
Nodes (7): Team, find_driver(), Cerca un pilota nel DB, dalla chiave più forte alla più debole., save_driver(), save_drivers(), TeamNotFound, LookupError

### Community 17 - "Django Compat Patch"
Cohesion: 0.29
Nodes (4): AppConfig, FantaappConfig, apply_python314_django42_context_copy_patch(), Django 4.2 uses copy(super()) in BaseContext.__copy__. On Python 3.14 this can…

### Community 18 - "Import Drivers Command"
Cohesion: 0.29
Nodes (4): Command, atomic, BaseCommand, Management command: `python manage.py import_drivers --season <year> [--dry-…

### Community 19 - "PostgreSQL Database Config"
Cohesion: 0.40
Nodes (6): PostgreSQL via DATABASE_URL, PostgreSQL via DATABASE_URL, dj-database-url (requirements-dev), psycopg2-binary (requirements-dev), dj-database-url (requirements), psycopg2-binary (requirements)

### Community 20 - "Consolidate Credits Command"
Cohesion: 0.33
Nodes (4): Command, BaseCommand, consolidate_race_credits(), atomic

### Community 21 - "Sync Weekend Participants"
Cohesion: 0.33
Nodes (3): Command, atomic, BaseCommand

### Community 23 - "Template Dict Filters"
Cohesion: 0.40
Nodes (5): get_item(), Serve a creare un range da 0 a value-1 nel template, utile per i loop. Se value…, Restituisce dictionary[key] nel template. Se la chiave non c’è, torna None., to_range(), filter

### Community 25 - "Schedule Dedup Migration"
Cohesion: 0.60
Nodes (4): deduplicate_schedule(), _merge_event_group(), Migration, _move_related()

### Community 27 - "Auth Templates"
Cohesion: 0.67
Nodes (4): Base Template, Login Template, Register Template, User Dashboard Template

### Community 28 - "manage.py Entrypoint (FantaF1)"
Cohesion: 0.50
Nodes (3): main(), Django's command-line utility for administrative tasks., Run administrative tasks.

### Community 29 - "FantaF1 Project & FastF1"
Cohesion: 0.50
Nodes (4): FantaF1 Frontend (Server-Rendered), FantaF1 Project, fastf1 (requirements-dev), fastf1 (requirements)

### Community 30 - "manage.py Entrypoint"
Cohesion: 0.50
Nodes (3): main(), Django's command-line utility for administrative tasks., Run administrative tasks.

### Community 31 - "SQLite Local Fallback"
Cohesion: 0.67
Nodes (3): SQLite Local Fallback Constraint, SQLite Local Fallback Constraint, dev_settings.py Isolated Dev Server

## Ambiguous Edges - Review These
- `postgres (Airflow metadata DB service)` → `FANTAF1_DATABASE_URL (bridge to FantaF1 Django DB)`  [AMBIGUOUS]
  airflow/docker-compose.yaml · relation: semantically_similar_to

## Knowledge Gaps
- **91 isolated node(s):** `dj-database-url (requirements)`, `User Dashboard Template`, `fastf1 (requirements)`, `FantaF1 Frontend (Server-Rendered)`, `dev_settings.py Isolated Dev Server` (+86 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 306 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **80 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `postgres (Airflow metadata DB service)` and `FANTAF1_DATABASE_URL (bridge to FantaF1 Django DB)`?**
  _Edge tagged AMBIGUOUS (relation: semantically_similar_to) - confidence is low._
- **Why does `Weekend` connect `Season Import & Result Insert Commands` to `Championship & Credit Costs`, `League & Grand Prix Choice Tests`, `Qualifying Forms & Cost Rules`, `Event Processing Commands & Service`, `Django Admin Config`, `Score, Credit & Rollback Commands`, `Player Results & Credit Consolidation`, `Player Choice Models`, `Credit Consolidation Tests`, `Consolidate Credits Command`, `Regular Qualifying Bonus Tests`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Why does `Driver` connect `Qualifying Forms & Cost Rules` to `Season Import & Result Insert Commands`, `Championship & Credit Costs`, `League & Grand Prix Choice Tests`, `Django Admin Config`, `Score, Credit & Rollback Commands`, `Player Results & Credit Consolidation`, `Player Choice Models`, `Driver & Team Lookup`, `Credit Consolidation Tests`, `Regular Qualifying Bonus Tests`?**
  _High betweenness centrality (0.040) - this node is a cross-community bridge._
- **Why does `QualifyingResult` connect `Qualifying Bonus Logic` to `Season Import & Result Insert Commands`, `League & Grand Prix Choice Tests`, `Qualifying Forms & Cost Rules`, `Django Admin Config`, `Score, Credit & Rollback Commands`, `Player Results & Credit Consolidation`, `Player Choice Models`, `Regular Qualifying Bonus Tests`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Are the 21 inferred relationships involving `Weekend` (e.g. with `Command` and `Command`) actually correct?**
  _`Weekend` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Are the 22 inferred relationships involving `Driver` (e.g. with `RegularQualifyingForm` and `SprintQualifyingForm`) actually correct?**
  _`Driver` has 22 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `PlayerScoringTests` (e.g. with `Championship` and `ChampionshipManager`) actually correct?**
  _`PlayerScoringTests` has 15 INFERRED edges - model-reasoned connections that need verification._