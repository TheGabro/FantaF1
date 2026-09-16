# Graph Report - FantaF1  (2026-09-16)

## Corpus Check
- Corpus is ~23,725 words - fits in a single context window. You may not need a graph.

## Summary
- 560 nodes · 987 edges · 96 communities (18 shown, 78 thin omitted)
- Extraction: 79% EXTRACTED · 21% INFERRED · 0% AMBIGUOUS · INFERRED: 203 edges (avg confidence: 0.94)
- Token cost: 220,580 input · 0 output

## Community Hubs (Navigation)
- Django Forms & Validation
- Management Commands
- Race & Qualifying Bonus Logic
- Player Choice & Credit Logic
- Prediction Forms & Import Commands
- Django Admin Config
- Home & Dashboard Templates
- Race Choice JS & Templates
- Deployment & Release Planning
- Player Scoring Tests
- Django Compat Patch
- PostgreSQL Database Config
- Template Dict Filters
- Custom User Manager
- Schedule Dedup Migration
- Dev vs Prod Settings
- Auth Templates (Base/Login/Register)
- manage.py Entrypoint
- FantaF1 Project & FastF1
- manage.py Entrypoint (App)
- SQLite Local Fallback
- Migration: Alter Driver Number Nullable
- Django Python 3.14 Compatibility Workaro
- Migration: Initial
- Migration: Alter Customuser Managers
- Migration: Remove Customuser Type Customuser Role
- Migration: Team Alter Customuser Email Driver
- Migration: Circuit Race Raceentry Qualifingentry
- Migration: Championship League Playerentry
- Migration: Rename Role Customuser Type
- Migration: Rename Type Customuser User Type
- Migration: Championship Active Championship Is Priv
- Migration: Alter Playerentry League
- Migration: Rename Playerentry Championshipplayer
- Migration: Championshipplayer Available Credit
- Migration: Raceresult Remove Circuit Continent Circ
- Migration: Rename State Circuit Country
- Migration: Rename Spinr Qualifing Start Race Sprint
- Migration: Remove Circuit Active
- Migration: Race Event Name
- Migration: Alter Race Round Number Alter Race Week
- Migration: Alter Race Options Alter Race Unique Tog
- Migration: Alter Driver Options Rename Name Driver
- Migration: Circuit Api Id
- Migration: Alter Circuit Api Id Alter Driver Api Id
- Migration: Driver Season
- Migration: Alter Race Modified At
- Migration: Alter Race Options Rename Year Race Seas
- Migration: Alter Qualifingentry Q1 Position
- Migration: Rename Qualifingentry Qualifyingentry
- Migration: Remove Raceentry Time
- Migration: Qualifyingentry Position
- Migration: Qualifying Alter Qualifyingentry Options
- Migration: Alter Weekend Weekend Type
- Migration: Alter Driver Unique Together
- Migration: Playerqualifyingchoice Playerracechoice
- Migration: Rename Qualifyingentry Qualifyingresult
- Migration: Rename Raceentry Raceresult
- Migration: Alter Race Options
- Migration: Alter Qualifying Options
- Migration: Alter Playerqualifyingmultichoice Select
- Migration: Alter Qualifying Weekend Alter Race Week
- Migration: Alter Qualifying Weekend Alter Race Week
- Migration: Refactor Choice Spent Amount
- Migration: Alter Playerqualifyingmultichoice Slot A
- Migration: Playerracechoice Credit Applied
- Migration: Driverstanding
- Migration: Playerraceresult
- Migration: Playerraceresult Point Modifier
- Migration: Eventprocessingstatus
- ASGI Config
- URL Configuration
- WSGI Config
- Gunicorn Dependency
- python-dotenv Dependency
- Requests Dependency
- Whitenoise Dependency
- Git Branch Flow
- Render Rollback Plan
- F1 Favicon Icon
- Empty Logout Template
- Matplotlib Dependency
- NumPy Dependency
- Pandas Dependency
- Pydantic Dependency
- RapidFuzz Dependency
- Requests-Cache Dependency
- SciPy Dependency
- SignalRCore Dependency

## God Nodes (most connected - your core abstractions)
1. `Driver` - 33 edges
2. `Weekend` - 32 edges
3. `PlayerScoringTests` - 28 edges
4. `PlayerRaceChoice` - 26 edges
5. `Race` - 24 edges
6. `Qualifying` - 20 edges
7. `QualifyingResult` - 20 edges
8. `GrandPrixChoiceTests` - 20 edges
9. `CreditConsolidationTests` - 20 edges
10. `Meta` - 19 edges

## Surprising Connections (you probably didn't know these)
- `fantaf1 Render Web Service` --conceptually_related_to--> `Render (Hosting Platform)`  [INFERRED]
  render.yaml → docs/plans/chat-context-template.md
- `Semantic Design Tokens` --shares_data_with--> `Base Template (fantaApp/base.html)`  [INFERRED]
  frontend/README.md → fantaApp/templates/fantaApp/base.html
- `Django (requirements)` --conceptually_related_to--> `fantaf1 Render Web Service`  [INFERRED]
  requirements.txt → render.yaml
- `LeagueInline` --uses--> `League`  [INFERRED]
  fantaApp/admin.py → fantaApp/models.py
- `ChampionshipManagerInline` --uses--> `ChampionshipManager`  [INFERRED]
  fantaApp/admin.py → fantaApp/models.py

## Import Cycles
- 3-file cycle: `fantaApp/services/__init__.py -> fantaApp/services/player_choices.py -> fantaApp/services/bonuses.py -> fantaApp/services/__init__.py`
- 3-file cycle: `fantaApp/services/__init__.py -> fantaApp/services/player_choices.py -> fantaApp/services/costs.py -> fantaApp/services/__init__.py`

## Hyperedges (group relationships)
- **Deployment Environment Variables Alignment** — render_environment_variables, docs_plans_chat_context_template_required_environment_variables, docs_plans_release_v0_2_neon_required_environment_variables [INFERRED 0.90]
- **Tailwind CSS Build and Theming Pipeline** — frontend_readme_tailwind_css_toolchain, frontend_readme_design_tokens, fantaapp_templates_fantaapp_base_static_main_css [INFERRED 0.80]
- **Grid-Based Driver Selection Pattern** — fantaapp_templates_fantaapp_regular_race_choice_template, fantaapp_templates_fantaapp_sprint_race_choice_template, fantaapp_static_fantaapp_js_race_choice [INFERRED 0.90]
- **Multi-Slot Qualifying Prediction Pattern** — fantaapp_templates_fantaapp_regular_race_qualifying_multi_choice_template, fantaapp_templates_fantaapp_sprint_race_qualifying_choice_template, fantaapp_static_fantaapp_js_select_dedupe, fantaapp_templatetags_dict_extras_module [INFERRED 0.90]
- **Championship Event Flow Templates** — fantaapp_templates_fantaapp_championship_flow_base_template, fantaapp_templates_fantaapp_weekend_details_template, fantaapp_templates_fantaapp_race_results_template, fantaapp_templates_fantaapp_regular_race_choice_template, fantaapp_templates_fantaapp_regular_race_qualifying_choice_template, fantaapp_templates_fantaapp_regular_race_qualifying_multi_choice_template, fantaapp_templates_fantaapp_sprint_race_choice_template, fantaapp_templates_fantaapp_sprint_race_qualifying_choice_template [EXTRACTED 1.00]

## Communities (96 total, 78 thin omitted)

### Community 0 - "Django Forms & Validation"
Cohesion: 0.05
Nodes (22): ChampionshipForm, ChampionshipPlayerForm, CustomUserRegistrationForm, LeagueForm, Meta, UsernameOrEmailAuthenticationForm, Championship, ChampionshipManager (+14 more)

### Community 1 - "Management Commands"
Cohesion: 0.06
Nodes (40): Command, BaseCommand, Management command: `python manage.py compute_race_score --season <year>…, Command, BaseCommand, Management command: `python manage.py consolidate_player_credits --season…, Command, atomic (+32 more)

### Community 2 - "Race & Qualifying Bonus Logic"
Cohesion: 0.06
Nodes (54): PlayerRaceChoice, PlayerRaceResult, QualifyingResult, RaceResult, apply_race_credit_change(), get_qualifying_multichoice_bonus(), get_qualifying_multichoice_bonus_rule(), get_race_bonus() (+46 more)

### Community 3 - "Player Choice & Credit Logic"
Cohesion: 0.10
Nodes (41): AbstractPlayerChoice, PlayerQualifyingChoice, PlayerQualifyingMultiChoice, PlayerSprintQualifyingChoice, Base comune: tiene traccia di chi sceglie cosa., get_qualifying_sprint_bonus_rule(), get_sprint_qualifying_bonus(), Restituisce i valori bonus per un livello multichoice. (+33 more)

### Community 4 - "Prediction Forms & Import Commands"
Cohesion: 0.09
Nodes (21): RegularQualifyingForm, SprintQualifyingForm, Command, atomic, BaseCommand, Management command: `python manage.py import_drivers --season <year> [--dry-…, Command, get_best_lap() (+13 more)

### Community 5 - "Django Admin Config"
Cohesion: 0.10
Nodes (25): AbstractUser, ChampionshipAdmin, ChampionshipManagerInline, ChampionshipPlayerAdmin, ChampionshipPlayerInline, CustomUserAdmin, DriverStandingAdmin, LeagueInline (+17 more)

### Community 6 - "Home & Dashboard Templates"
Cohesion: 0.09
Nodes (27): Base Template (fantaApp/base.html), URL Route: home, URL Route: login, URL Route: logout, URL Route: register, Static Asset: fantaApp/js/app.js, Static Asset: fantaApp/css/main.css, Theme Toggle (light/dark, localStorage) (+19 more)

### Community 7 - "Race Choice JS & Templates"
Cohesion: 0.22
Nodes (17): isSelected(), pupilloId(), refresh(), refreshRows(), renderHiddenInputs(), renderPanel(), rowById(), selectedCardHtml() (+9 more)

### Community 8 - "Deployment & Release Planning"
Cohesion: 0.15
Nodes (14): Chat Context Template, Docker (Deployment Artifact), v0.2.0 Ready-to-Merge Checklist, Render (Hosting Platform), Required Environment Variables, Docker (Deployment Artifact), Release Plan v0.2.0 (Docker + Render), Render (Hosting Platform) (+6 more)

### Community 10 - "Django Compat Patch"
Cohesion: 0.29
Nodes (4): AppConfig, FantaappConfig, apply_python314_django42_context_copy_patch(), Django 4.2 uses copy(super()) in BaseContext.__copy__. On Python 3.14 this can…

### Community 11 - "PostgreSQL Database Config"
Cohesion: 0.40
Nodes (6): PostgreSQL via DATABASE_URL, PostgreSQL via DATABASE_URL, dj-database-url (requirements-dev), psycopg2-binary (requirements-dev), dj-database-url (requirements), psycopg2-binary (requirements)

### Community 12 - "Template Dict Filters"
Cohesion: 0.40
Nodes (5): get_item(), Serve a creare un range da 0 a value-1 nel template, utile per i loop. Se value…, Restituisce dictionary[key] nel template. Se la chiave non c’è, torna None., to_range(), filter

### Community 14 - "Schedule Dedup Migration"
Cohesion: 0.60
Nodes (4): deduplicate_schedule(), _merge_event_group(), Migration, _move_related()

### Community 16 - "Auth Templates (Base/Login/Register)"
Cohesion: 0.67
Nodes (4): Base Template, Login Template, Register Template, User Dashboard Template

### Community 17 - "manage.py Entrypoint"
Cohesion: 0.50
Nodes (3): main(), Django's command-line utility for administrative tasks., Run administrative tasks.

### Community 18 - "FantaF1 Project & FastF1"
Cohesion: 0.50
Nodes (4): FantaF1 Frontend (Server-Rendered), FantaF1 Project, fastf1 (requirements-dev), fastf1 (requirements)

### Community 19 - "manage.py Entrypoint (App)"
Cohesion: 0.50
Nodes (3): main(), Django's command-line utility for administrative tasks., Run administrative tasks.

### Community 20 - "SQLite Local Fallback"
Cohesion: 0.67
Nodes (3): SQLite Local Fallback Constraint, SQLite Local Fallback Constraint, dev_settings.py Isolated Dev Server

## Knowledge Gaps
- **90 isolated node(s):** `Migration`, `Migration`, `Migration`, `Migration`, `Migration` (+85 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 282 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **78 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Driver` connect `Prediction Forms & Import Commands` to `Django Forms & Validation`, `Management Commands`, `Race & Qualifying Bonus Logic`, `Player Choice & Credit Logic`, `Django Admin Config`, `Player Scoring Tests`?**
  _High betweenness centrality (0.040) - this node is a cross-community bridge._
- **Why does `Weekend` connect `Management Commands` to `Django Forms & Validation`, `Race & Qualifying Bonus Logic`, `Player Choice & Credit Logic`, `Prediction Forms & Import Commands`, `Django Admin Config`, `Player Scoring Tests`?**
  _High betweenness centrality (0.036) - this node is a cross-community bridge._
- **Why does `PlayerScoringTests` connect `Player Scoring Tests` to `Django Forms & Validation`, `Management Commands`, `Race & Qualifying Bonus Logic`, `Player Choice & Credit Logic`, `Prediction Forms & Import Commands`?**
  _High betweenness centrality (0.025) - this node is a cross-community bridge._
- **Are the 21 inferred relationships involving `Driver` (e.g. with `RegularQualifyingForm` and `SprintQualifyingForm`) actually correct?**
  _`Driver` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `Weekend` (e.g. with `Command` and `Command`) actually correct?**
  _`Weekend` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `PlayerScoringTests` (e.g. with `Championship` and `ChampionshipManager`) actually correct?**
  _`PlayerScoringTests` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 16 inferred relationships involving `PlayerRaceChoice` (e.g. with `PlayerRaceChoiceInline` and `get_player_reserved_credit()`) actually correct?**
  _`PlayerRaceChoice` has 16 INFERRED edges - model-reasoned connections that need verification._