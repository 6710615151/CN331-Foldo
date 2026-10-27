# Architecture

This document explains how the FOLDO Django project is organised: the apps and
their responsibilities, URL routing, templates, static files, the current
(near-empty) model layer, and the intended data flow as MVP features land.

## High-level shape

FOLDO is a **server-rendered Django monolith**. Django renders HTML with the
template engine, Bootstrap 5 styles it, and a small amount of ES6 JavaScript
progressively enhances the page. There is no separate JavaScript application or
REST API in the foundation; those are not required by the course stack.

FOLDO is a **modular monolith** with a **4-tier layered architecture** inside
every app (presentation → validation → business logic → data access).

## C4 model

### Level 1 — System context

```text
   ┌──────────────┐                         ┌──────────────────────┐
   │   Student    │ builds one profile and  │  Instructor          │
   │   (Person)   │ many tailored portfolios│  (Product Owner)     │
   └──────┬───────┘                         └──────────┬───────────┘
          │ uses (browser, HTTPS)                      │ reviews data (Django admin)
          ▼                                            ▼
   ┌───────────────────────────────────────────────────────────────┐
   │                  FOLDO  (Software System)                     │
   │  Keep one main profile; create, preview and export tailored   │
   │  portfolio versions for each opportunity.                     │
   └───────────────────────────────────────────────────────────────┘
```

### Level 2 — Containers

```text
Browser ──HTTPS──▶ Nginx ──▶ Gunicorn ──▶ Django application ──▶ PostgreSQL
                (reverse     (WSGI app      (config + apps/)    (relational data)
                 proxy,       server)            │
                 static)                         └──────────────▶ Redis
                                                                  (cache, future queue)
```

| Container | Technology | Responsibility |
| --------- | ---------- | -------------- |
| Web server | Nginx | TLS termination, reverse proxy, serving `collectstatic` output. |
| Application server | Gunicorn | Runs Django through `config/wsgi.py`. |
| Web application | Django 5.2 | All business logic; server-rendered HTML (MVT). |
| Database | PostgreSQL (SQLite in local development) | Persistent data via the Django ORM. |
| Cache | Redis (in-process cache in local development) | Caching; future task queue. |

> Local development runs only the Django container (`runserver` + SQLite).
> Nginx and Gunicorn are the target production containers; their configuration
> is not kept in this repository.

### Level 3 — Components (inside the Django container)

```text
config (settings, root URLconf, wsgi/asgi)
   │
   ├── apps.accounts    CustomUser, authentication
   ├── apps.core        shared shell: landing page, health check, error pages
   ├── apps.profiles    (planned, FOLDO-02/03) the one main profile
   └── apps.portfolios  (planned, FOLDO-04..08) tailored portfolio versions
        dependencies: portfolios ──▶ profiles ──▶ accounts   (one way only)
```

## The `config/` package (Django project)

`config/` is the Django **project** package — configuration only, no business
logic.

| File | Responsibility |
| ---- | -------------- |
| `settings.py` | Single env-based settings module (see below). |
| `urls.py` | Root URLconf: mounts the admin and each app's URLs, defines error handlers. |
| `wsgi.py` | WSGI entry point (used by `runserver` and any WSGI server). |
| `asgi.py` | ASGI entry point (kept for future async support). |

### Why one settings module?

For a project of this size, separate `base/dev/prod` settings modules add import
complexity and a common source of bugs ("which settings am I running?"). Instead
`config/settings.py` reads environment variables through small `env_*` helpers:

- Unset variables fall back to **development-safe** defaults (SQLite, `DEBUG=True`).
- Setting `DJANGO_DEBUG=False` and the `DB_*` / `REDIS_URL` variables switches
  the *same* module into production behaviour, including HTTPS redirect, secure
  cookies, HSTS and trusted-proxy handling.

This keeps one obvious place to read configuration and avoids duplicating
settings across files.

## Apps and their responsibilities

FOLDO is a **modular monolith**: one Django project, one app per bounded
context. Apps live under the `apps/` package so the project package (`config/`)
and the domain apps are visually distinct. Each app is registered by its full
dotted path (e.g. `apps.core`) and has a single, clear responsibility.

Dependencies point one way — `portfolios → profiles → accounts`, with `core`
as the shared shell. Cross-app model references use string references
(`"profiles.Profile"`, `settings.AUTH_USER_MODEL`) and cross-app workflows live
in `services.py`, so there are no circular imports.

### Layers inside every app

| File | Layer | Holds |
| ---- | ----- | ----- |
| `views.py` + `urls.py` | Presentation | Skinny views: take the request, call a selector/service, return a response or redirect. `urls.py` sets `app_name`. |
| `forms.py` | Validation | `Form` / `ModelForm` type checks, validation and cleaning before data enters the system. |
| `services.py` | Business logic | Create / update / delete, `@transaction.atomic`, `select_for_update()`, external integrations (e-mail, PDF). |
| `selectors.py` | Data access | Pure read queries, optimised with `select_related` / `prefetch_related`. |
| `models.py` | Data | Tables, field types, relationships and constraints only. |
| `admin.py`, `tests.py`, `templates/<app>/` | — | Admin registrations, the app's tests, namespaced templates. |

Files for layers an app does not need yet contain only a docstring describing
what will go there.

### Coding rules per layer

**Models (`models.py`)** — schema only: fields, relationships (1:1, 1:N, M:N),
`Meta.constraints`. No business logic, no calls to other systems. Foreign keys
to another app use a string reference (`"profiles.Profile"`,
`settings.AUTH_USER_MODEL`) so modules never import each other in a circle.

**Selectors (`selectors.py`)** — pure reads, no side effects.

- `select_related()` for single-object relations (FK / 1:1) — one SQL JOIN.
- `prefetch_related()` for multi-object relations (M:N / reverse FK).
- `Q` objects for complex conditions (OR / NOT).
- `only()` / `defer()` / `values()` when only some fields are needed.

**Services (`services.py`)** — every create / update / delete, plus calls to
external systems (e-mail, PDF export).

- Wrap multi-step writes in `@transaction.atomic` so any error rolls back.
- Lock rows with `select_for_update()` (inside the transaction) wherever
  concurrent requests could race.
- Use `F()` expressions for updates computed in the database (e.g. counters).

**Forms (`forms.py`)** — never trust user input. Validate with `Form` /
`ModelForm` and `clean_<field>()` / `clean()`; services receive only
`cleaned_data`. Example: `accounts.forms` normalises the e-mail and rejects a
duplicate via `accounts.selectors.email_is_taken()`.

**Views (`views.py`)** — skinny (about 15–20 lines): take input → call a
selector / service → return a response.

- Prefer generic class-based views (`ListView`, `DetailView`, `CreateView`,
  `UpdateView`, `DeleteView`, `TemplateView`).
- Override `get_queryset()` to filter, `get_context_data()` to add context and
  `form_valid()` to hand cleaned data to a service.
- Access-control mixins (`LoginRequiredMixin`, `UserPassesTestMixin`) go
  **left-most** in the base list, so Python's MRO (C3 linearisation) runs them
  first: `class EditView(LoginRequiredMixin, UpdateView)`.
- Use `reverse_lazy()` for class-level URLs (`success_url`) to avoid
  `NoReverseMatch` at import time.

**Templates** — `{% csrf_token %}` in every POST form; rely on Django's
auto-escaping (never `|safe` on user input); `{% url %}` namespaces instead of
hardcoded paths; app templates namespaced as `templates/<app>/…`.

### `apps.accounts` — users and authentication

Owns `CustomUser` (`AbstractUser` subclass), configured as
`AUTH_USER_MODEL = "accounts.CustomUser"` before the first migration, plus its
admin and admin forms. Log in / sign-up views arrive with the authentication
Issue; `urls.py` is mounted at `accounts/` with no routes yet.

### `apps.core` — the shared shell

Owns everything that is *not* tied to a specific domain:

- `views.LandingView` — the public landing page: a single hero screen with one
  "Get Started" call to action, layered over a designer graphic slot.
- `views.OnboardingView` — first-time entry flow: a three-step walkthrough
  (`/onboarding/`). Not gated behind login yet — real authentication lands
  with the rest of FOLDO-02.
- `views.DashboardView` — the signed-in app shell (`/dashboard/`): navigation
  plus an empty-state summary. Same auth caveat as `OnboardingView`.
- `views.HealthCheckView` — JSON health endpoint for monitoring.
- `views.page_not_found` / `views.server_error` — custom error handlers.
- `selectors.py` — health check (`get_health_report()`, `DatabaseHealthCheck`,
  `HealthReport`): a pure read with no side effects. Also holds the shell's
  mock data (`get_mock_onboarding_steps()`, `get_mock_dashboard_summary()`)
  until `apps.profiles`/`apps.portfolios` exist — see
  `docs/API_CONVENTIONS.md` for the mock-data convention.
- `services.py` — empty: the shell performs no mutations.
- `urls.py` — `""` (landing), `"health/"`, `"onboarding/"`, `"dashboard/"`.
- `templates/core/landing.html`, `onboarding.html`, `dashboard.html`.

`core` intentionally has **no models**. Navigation, base template, skip link,
footer and shared CSS/JS are also part of the core shell.

### Planned apps (not created yet)

The current scope is **FOLDO-01** (MVP scope and product goal), so only the
foundation exists. The domain apps are created together with the Issue that
first needs them — never as empty placeholders:

| App | Created with | Will own |
| --- | ------------ | -------- |
| `apps.profiles` | FOLDO-02 | The one main profile: personal details, education, skills, projects, experience (FOLDO-02/03). |
| `apps.portfolios` | FOLDO-04 | Portfolio versions, content selection, templates, preview, PDF export (FOLDO-04..08). |

Each new app follows the same layered layout (`models`, `selectors`,
`services`, `forms`, `views`, `urls`, `admin`, `tests.py`,
`templates/<app>/`). The planned models are listed in `docs/DATABASE.md`.

### Why these apps?

They map to the natural seams of the product: accounts (who you are), a shared
shell, the *one* profile, and the *many* portfolios. This lets several
developers work on different Issues without colliding in the same files. Fewer
apps would create a single crowded module; more apps would be premature
abstraction.

## URL routing

Routing is decentralised — the root URLconf mounts each app, and each app owns
its own paths:

```text
config/urls.py
├── admin/        → django.contrib.admin
├── ""            → apps.core.urls        → ""              (landing,    name="core:landing")
│                                            "health/"       (health,     name="core:health")
│                                            "onboarding/"   (onboarding, name="core:onboarding")
│                                            "dashboard/"    (dashboard,  name="core:dashboard")
└── "accounts/"   → apps.accounts.urls    → (auth routes arrive with the authentication Issue)
```

All app URLconfs use `app_name` namespaces, so templates reverse URLs safely
with `{% url 'core:landing' %}`. Reverse lookups are used everywhere instead of
hardcoded paths, so moving a route never breaks a template.

`config/urls.py` also declares `handler404` and `handler500`, which render the
project's `404.html` and `500.html` when `DEBUG=False`.

## Templates

Shared templates live project-wide in `templates/` (`TEMPLATES["DIRS"]`); each
app's own pages live inside the app, namespaced twice
(`apps/<app>/templates/<app>/…`, found via `APP_DIRS`) so names like
`index.html` never collide between apps.

```text
apps/core/templates/core/
├── landing.html               # landing page (no shared navbar/footer)
├── onboarding.html            # first-time entry flow (mock steps)
└── dashboard.html             # signed-in app shell (mock summary)

templates/
├── base.html                 # <head>, skip link, navbar, main, footer, scripts
├── 404.html  500.html        # error pages
├── partials/
│   ├── navbar.html           # accessible responsive navigation (brand + Dashboard link)
│   ├── footer.html
│   ├── messages.html         # Django messages
│   ├── logo_mark.html        # logo slot (designer asset)
│   └── asset_slot.html       # generic graphic slot (designer asset)
```

`base.html` exposes blocks (`html_lang`, `title`, `meta_description`, `header`,
`content`, `footer`, `extra_css`, `extra_js`) so child templates only override
what they need.

## Static files

- **Source** lives in `static/` (`css/styles.css`, `js/main.js`, `images/`).
- `STATICFILES_DIRS` points at it for development and for `collectstatic`.
- `collectstatic` gathers everything into `STATIC_ROOT` (`staticfiles/`), which
  is git-ignored.

`static/css/styles.css` is organised as tokens → base → components →
responsive and defines FOLDO's design system through CSS custom properties
(navy, electric blue, lime and orange). `static/js/main.js` is a small ES6
module that adds a navbar shadow on scroll; **the site works fully with
JavaScript disabled**.

## Models and data flow

**Today the only model is `accounts.CustomUser`.** No placeholder tables were
created, because an unused model and its migration add noise and confuse the
team. The planned models are listed in `docs/DATABASE.md`, and each will be
added together with the Issue that needs it.

The intended data flow once features exist:

```text
User ──edits──▶ Profile (+ Education / Skill / Project / Experience)   [profiles]
                     │  referenced by (not copied into)
                     ▼
User ──creates──▶ PortfolioVersion ──selects──▶ PortfolioSectionItem   [portfolios]
                     │
                     ├── render with a chosen template ──▶ Preview
                     └── render ──▶ PDF export
```

The key design decision: portfolio versions store **references** to profile
content rather than copies, so editing the main profile keeps every portfolio in
sync — the behaviour the product tagline promises.

## Cross-cutting concerns

| Concern | Where | Notes |
| ------- | ----- | ----- |
| Security | `config/settings.py` | Security + CSRF middleware never disabled; HTTPS/HSTS/secure cookies auto-enabled when `DEBUG=False`. |
| Logging | `config/settings.py` | Console logging (stdout) at an env-configurable level. |
| Health | `apps.core.selectors` | OOP `HealthReport` + `DatabaseHealthCheck`; payload exposes no secrets. |
| Errors | `config/urls.py` + `apps.core.views` | Friendly 404/500 pages in production. |
