# FOLDO

**One Profile. Many Forms.**

FOLDO helps university students keep a single, reusable main profile and turn
it into multiple tailored portfolios — one for each job or internship they
apply to. Update the profile once, and every portfolio stays current.

> **Status: project foundation.** This repository currently contains a runnable
> Django 5.2 foundation (landing page, health check, navigation, an app-shell
> preview at `/onboarding/` and `/dashboard/`, and tests).
> The eight MVP features below are *not* implemented yet;
> they are developed one GitHub Issue at a time.

---

## Product goal

Let a student maintain **one** authoritative profile — personal details,
education, skills, projects and experience — and then create **many** portfolio
versions that each select the most relevant content and template for a specific
opportunity. FOLDO removes the copy-paste work of maintaining several CVs.

**Team:** five student developers (each contributes as a Developer), a Scrum
Master who rotates every Sprint, and the instructor as Product Owner.

| Issue    | Feature                                                   | Status |
| -------- | --------------------------------------------------------- | ------ |
| FOLDO-01 | Product scope, architecture and acceptance standards      | Done |
| FOLDO-02 | Authentication and first-time onboarding                  | Done |
| FOLDO-03 | Create and manage Main Profile                            | Done |
| FOLDO-04 | Education, skills, projects and experience                | Done |
| FOLDO-05 | Multiple portfolio versions                               | Done |
| FOLDO-06 | Select content per portfolio version                      | Done |
| FOLDO-07 | Templates and portfolio rendering                         | Done |
| FOLDO-08 | Preview (desktop / mobile)                                | Done |
| FOLDO-09 | Publish and unpublish                                     | In progress (republish snapshot pending) |
| FOLDO-10 | Persistence, validation, security and recovery states     | Done |
| FOLDO-11 | Export a portfolio version as PDF                         | Done |
| FOLDO-12 | Account settings                                          | Done |
| FOLDO-13 | Responsive UI and end-to-end release readiness            | In progress |
| FOLDO-14 | Portfolio DNA                                             | Done |
| FOLDO-15 | Project Story Builder                                     | Done |
| FOLDO-16 | Portfolio Quality Check                                   | Done |
| FOLDO-17 | Share Kit and QR code                                     | Done |

---

## Technology stack (course-required)

**Backend** — Python (OOP), Django 5.2 LTS, Django ORM, Django Forms/ModelForms,
Django authentication & permissions (when authentication is implemented).

**Database** — SQLite for local development; PostgreSQL for production. Django
ORM only, so the same code runs on both. Production credentials come from
environment variables.

**Frontend** — HTML5 (semantic), CSS3 with Flexbox & CSS Grid, **Bootstrap 5**,
JavaScript ES6+ for progressive enhancement, Django Templates for
server-rendered HTML. No React/Vue/Angular/Next.js/Tailwind.

**Version control** — Git, GitHub, GitHub Flow, feature branches, Pull Requests
with required review, protected `main`, GitHub Projects for the backlog.

**Services** — PostgreSQL (optional, via `DB_ENGINE`), Redis (optional cache,
via `REDIS_URL`).

---

## Repository structure

```text
.
├── config/                 # Django project package (settings, urls, wsgi/asgi)
├── apps/                   # one Django app per bounded context (modular monolith)
│   ├── accounts/           # CustomUser (AUTH_USER_MODEL) + future authentication
│   └── core/               # shared shell: landing page, health check, error pages
│       ├── models.py       #   data layer: tables and constraints only
│       ├── selectors.py    #   data access: pure read queries
│       ├── services.py     #   business logic: create/update/delete + transactions
│       ├── forms.py        #   validation: Forms / ModelForms
│       ├── views.py        #   presentation: skinny views
│       ├── urls.py         #   app URLconf with app_name namespace
│       ├── admin.py        #   admin registrations
│       ├── tests.py        #   the app's tests
│       └── templates/core/ # namespaced app templates
│   (profiles/, portfolios/ are created with FOLDO-02 and FOLDO-04)
├── templates/              # project-wide templates: base.html, partials/, 404/500
├── static/                 # source assets (css, js, images)
├── docs/                   # architecture, development, git, database, DoD
├── requirements.txt
├── manage.py
├── .env.example
└── .editorconfig
```

Why `config/` instead of `foldo/`? `config` is the conventional name for the
Django *project* package that holds settings and root URL configuration; the
apps under `apps/` hold the domain logic. This keeps the project package
and the business apps clearly separated.

---

## Prerequisites

- **Python 3.11+** (Django 5.2 requires 3.10 or newer). This project was set up
  and verified with **Python 3.11.16**.
- **pip** and the standard `venv` module.
- *(Optional)* **Git** and a GitHub account for collaboration.
- *(Optional, for PDF export)* the **Pango** system libraries used by WeasyPrint.
  Without them the whole site still runs; only "Export PDF" reports that it isn't
  available. Install: Ubuntu/Debian `sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0`,
  macOS `brew install pango`, Windows: see the
  [WeasyPrint installation guide](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation).

> ⚠️ The default `python3` on older macOS installs can be 3.9, which Django 5.x
> does **not** support. Check with `python3 --version` and install a newer Python
> (e.g. `brew install python@3.11`) if needed.

---

## Installation and setup (local development)

```bash
# 1. Clone
git clone https://github.com/6710615151/CN331-Foldo.git
cd CN331-Foldo

# 2. Create and activate a virtual environment
python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements-dev.txt   # includes requirements.txt + dev tools
# (runtime only: pip install -r requirements.txt)

# 4. Configure environment (optional for local — sensible dev defaults exist)
cp .env.example .env               # then edit if you wish

# 5. Create the local SQLite database
python manage.py migrate

# 6. Run the development server
python manage.py runserver
```

Open <http://127.0.0.1:8000/>. Other useful routes:

| URL | Purpose |
| --- | --- |
| `/` | FOLDO landing page |
| `/onboarding/` | First-time entry flow (mock steps; login required) |
| `/dashboard/` | Signed-in app shell: Main Profile status (login required) |
| `/profiles/` | Main Profile: create, view, edit, delete (login required) |
| `/templates/` | Portfolio templates gallery and preview with your profile (login required) |
| `/health/` | JSON health check (200 ok / 503 degraded) |
| `/profiles/<id>/education/` | Education of one of your profiles: add, edit, delete (login required; owner only, others get 404) |
| `/accounts/settings/` | Account settings (login required; edits the signed-in user only) |
| `/profiles/<id>/skills-experience/` | Skills and experience of one of your profiles (login required; owner only, others get 404) |
| `/admin/` | Django admin (create a superuser to use it) |

Create an admin user:

```bash
python manage.py createsuperuser
```

---

## Running tests

```bash
python manage.py test              # all tests
python manage.py test apps.core        # one app
python manage.py check             # framework checks
python manage.py check --deploy    # production security checks
```

---

## Database migration commands

```bash
python manage.py makemigrations    # create migrations after changing models
python manage.py migrate           # apply migrations
python manage.py makemigrations --check --dry-run   # CI: fail if models lack migrations
```

Local development uses SQLite (`db.sqlite3`, git-ignored). See
[docs/DATABASE.md](docs/DATABASE.md) for PostgreSQL configuration.

---

## GitHub collaboration workflow (summary)

1. Update local `main`: `git checkout main && git pull`
2. Create a branch from `main`, e.g. `feat/FOLDO-02-main-profile`
3. Work **only** on the assigned Issue.
4. Run the relevant tests.
5. Commit using [Conventional Commits](https://www.conventionalcommits.org/),
   e.g. `feat(profiles): add main profile model`.
6. Push the branch and open a Pull Request into `main`.
7. Request review from another developer.
8. Resolve comments; pass required checks.
9. Merge only after approval.

**Never commit directly to `main`.** Full details, branch naming and the branch
protection checklist are in [docs/GIT_WORKFLOW.md](docs/GIT_WORKFLOW.md).

---

## Current scope

Implemented and verified (see the table above for what is still in progress):

- `accounts`: register, log in/out, password reset, account settings (`CustomUser`).
- `core`: landing page, JSON health check, custom 403/404/500 pages, onboarding and dashboard.
- `profiles`: up to 10 Main Profiles per user (one default) with photo, contact details and a
  completeness indicator; education, skills, experience and projects with an optional
  Project Story (problem, role, process, solution, outcome).
- `portfolios`: portfolio versions, per-version content selection, template choice,
  preview (incl. desktop / mobile), publish / unpublish with a public link, Share Kit with
  QR code, PDF export and Quality Check.
- `rendering`: three portfolio templates shared by preview, public page and PDF.
- `insights`: Portfolio DNA (which versions reuse each profile item).
- Tests in every app, plus end-to-end and regression tests in `apps/core/test_e2e*.py`
  and `apps/core/test_regression.py`. CI runs `check`, missing-migration check and tests.
---

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — apps, routing, templates, data flow
- [docs/API_CONVENTIONS.md](docs/API_CONVENTIONS.md) — HTTP status, JSON shape, form/error and mock-data conventions
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) — exact local setup commands
- [docs/GIT_WORKFLOW.md](docs/GIT_WORKFLOW.md) — branching, commits, reviews
- [docs/DATABASE.md](docs/DATABASE.md) — SQLite vs PostgreSQL, ORM, migrations
- [docs/DEFINITION_OF_DONE.md](docs/DEFINITION_OF_DONE.md) — acceptance criteria for Issues

- [docs/CONVENTIONS.md](docs/CONVENTIONS.md) — shared rules for data ownership, validation, errors and tests (FOLDO-10)

- [docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md) — what to check before a release or deploy (FOLDO-13)
