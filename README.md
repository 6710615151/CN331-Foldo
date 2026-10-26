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

| Issue   | Feature                                   | Status |
| ------- | ----------------------------------------- | ------ |
| FOLDO-01 | Define MVP Scope and Product Goal        | Backlog |
| FOLDO-02 | Create and Edit Main Profile             | Backlog |
| FOLDO-03 | Manage Education, Skills and Projects    | Backlog |
| FOLDO-04 | Create Multiple Portfolio Versions       | Backlog |
| FOLDO-05 | Select Content for Each Portfolio Version| Backlog |
| FOLDO-06 | Choose Portfolio Templates               | Backlog |
| FOLDO-07 | Preview Portfolio                        | Backlog |
| FOLDO-08 | Export Portfolio to PDF                  | Backlog |

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
| `/onboarding/` | First-time entry flow (mock steps; not gated behind login yet) |
| `/dashboard/` | Signed-in app shell (mock summary; not gated behind login yet) |
| `/health/` | JSON health check (200 ok / 503 degraded) |
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

## Current foundation scope

Implemented and verified:

- Django 5.2 project with env-based settings and secure production defaults.
- `accounts` app: `CustomUser` as `AUTH_USER_MODEL` from the first migration.
- `core` app: landing page, JSON health check, custom 404/500 pages, and an
  app-shell preview (`/onboarding/`, `/dashboard/`) rendered against mock data
  until `profiles`/`portfolios` exist.
- Responsive Bootstrap 5 UI with FOLDO design tokens and a small ES6 module.
- Automated tests in each app's `tests.py` (landing, health, user model, forms, 404).
- Optional PostgreSQL and Redis configuration through environment variables.
- Five documents under `docs/` plus GitHub templates and a CI workflow.

**Deliberately not implemented yet:** authentication, profile CRUD, portfolio
versioning, template selection, preview and PDF export. No placeholder database
models were created — planned models are documented in
`apps/*/models.py` and will arrive with their Issues.

---

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — apps, routing, templates, data flow
- [docs/API_CONVENTIONS.md](docs/API_CONVENTIONS.md) — HTTP status, JSON shape, form/error and mock-data conventions
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) — exact local setup commands
- [docs/GIT_WORKFLOW.md](docs/GIT_WORKFLOW.md) — branching, commits, reviews
- [docs/DATABASE.md](docs/DATABASE.md) — SQLite vs PostgreSQL, ORM, migrations
- [docs/DEFINITION_OF_DONE.md](docs/DEFINITION_OF_DONE.md) — acceptance criteria for Issues
