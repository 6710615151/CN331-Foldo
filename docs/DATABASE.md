# Database

FOLDO uses the **Django ORM** exclusively, so the same application code runs on
**SQLite** (local development) and **PostgreSQL** (production/cloud). No raw SQL
and no database-specific queries are used.

## Local development — SQLite

- Configured by default when `DB_ENGINE` is unset or `sqlite`.
- The file is `db.sqlite3` in the project root and is **git-ignored**.
- No server to install or start: `python manage.py migrate` is enough.

```bash
python manage.py migrate          # create/update db.sqlite3
rm db.sqlite3 && python manage.py migrate   # reset local data
```

## Production — PostgreSQL

Set these environment variables (see `.env.example`). Never hardcode them.

| Variable | Example | Notes |
| -------- | ------- | ----- |
| `DB_ENGINE` | `postgresql` | Switches settings to PostgreSQL. |
| `DB_NAME` | `foldo` | Database name. |
| `DB_USER` | `foldo` | Database user. |
| `DB_PASSWORD` | *(secret)* | Injected via environment/secret manager. |
| `DB_HOST` | `localhost` | Database server host. |
| `DB_PORT` | `5432` | PostgreSQL port. |
| `DB_CONN_MAX_AGE` | `60` | Seconds to reuse a connection. |

`config/settings.py` selects the backend like this:

```python
DB_ENGINE = env_str("DB_ENGINE", "sqlite").lower()
if DB_ENGINE in {"postgres", "postgresql"}:
    DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql", ...}}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", ...}}
```

The driver is **psycopg 3** (`psycopg[binary]`), installed from
`requirements.txt`. Django connects through it automatically.

### Keeping both databases compatible

- Use ORM queries and `F()`/`Q()` expressions, not raw SQL.
- Avoid backend-specific field types unless there is no alternative.
- Avoid case-sensitivity assumptions: SQLite is case-insensitive for `LIKE`
  while PostgreSQL is not — use `__iexact` / `Lower()` deliberately.
- Do not rely on SQLite's dynamic typing; declare proper field types.

## Migrations

Migrations are the single source of truth for the schema and are committed to
Git.

```bash
python manage.py makemigrations <app_label>          # after changing models
python manage.py migrate                             # apply
python manage.py makemigrations --check --dry-run    # CI: model/migration drift
python manage.py showmigrations                      # status
```

Rules:

- **One Issue, one coherent migration.** Add a model with the Issue that needs it.
- **Commit migrations with the code they belong to.**
- Review the generated migration before committing — Django sometimes asks for a
  default for a new non-nullable field.
- Never edit an already-applied migration on a shared branch; add a new one.

## Current schema

**`accounts.CustomUser`** (subclass of `AbstractUser`, no extra fields yet) is
`AUTH_USER_MODEL` from the very first migration, so fields can be added later
without a user-model swap. Always refer to it via `settings.AUTH_USER_MODEL` /
`get_user_model()`, never `auth.User`.

**`profiles.MainProfile`** (FOLDO-03) — the ER diagram's `MAIN_PROFILES`:

| Field | Notes |
| ----- | ----- |
| `owner` | FK → `AUTH_USER_MODEL`, `on_delete=CASCADE` |
| `label`, `is_default` | Name the owner sees; one default per owner (partial unique constraint) |
| `full_name` | Required |
| `headline`, `bio`, `location` | Optional |
| `photo` | Optional `ImageField` (jpg/png/webp/gif, ≤ 5 MB) stored under `MEDIA_ROOT/profile_photos/user_<id>/` with a random name |
| `contact_email`, `phone` | Optional contact details |
| `website`, `linkedin_url`, `github_url` | Optional links (http/https) |
| `created_at`, `updated_at` | Timestamps |

**`profiles.Education`** (FOLDO-04) — the ER diagram's `PROFILE_EDUCATIONS`:

| Field | Notes |
| ----- | ----- |
| `profile` | FK → `MainProfile` (`related_name="educations"`), `on_delete=CASCADE`. Owner path: `profile__owner` |
| `institution` | Required, ≤ `MAX_SHORT_TEXT` (200) |
| `degree`, `field_of_study` | Optional, ≤ 200 |
| `start_date` | Required; 1900-01-01 … today (form) |
| `end_date` | Optional; empty = still studying ("Present"); may be up to 10 years ahead (expected graduation). DB check constraint `education_end_not_before_start` |
| `grade` | Optional, ≤ 50 (e.g. GPA) |
| `description` | Optional, ≤ `MAX_LONG_TEXT` (5000) |
| `created_at`, `updated_at` | Timestamps |

Ordered current studies first, then by most recent end/start date.

"Complete" means `full_name`, `headline` and `contact_email` are filled in
(`MainProfile.REQUIRED_FOR_PORTFOLIO`). Saving an incomplete profile is
allowed and shows a warning.

> **Decision (Sprint 2):** a user may keep up to 10 Main Profiles, exactly one
> of them the **default** (used by the dashboard and as the starting point for
> new portfolio versions). The original ER diagram had `MAIN_PROFILES.user_id`
> UNIQUE (one profile); it was relaxed because FOLDO-03 and FOLDO-04 were
> built on the many-profile model. Child tables reach the user through
> `profile__owner` (see `docs/CONVENTIONS.md` §1). Tailoring for a specific
> job is still the job of portfolio versions (FOLDO-05).

Besides these, only Django's built-in tables exist (`auth` groups and
permissions, `admin`, `contenttypes`, `sessions`). No placeholder tables were
created — an unused model plus migration is noise and confuses the team.

Planned models arrive with their Issues:

| App | Model (ER table) | Issue | Purpose |
| --- | ---------------- | ----- | ------- |
| `profiles` | `Education` (`PROFILE_EDUCATIONS`) | FOLDO-04 | Implemented. Institution, degree, field of study, dates, grade (see above). |
| `profiles` | `Skill` (`PROFILE_SKILLS`) | FOLDO-04 | Implemented. Name (unique per profile, ignoring case), proficiency. |
| `profiles` | `Experience` (`PROFILE_EXPERIENCES`) | FOLDO-04 | Implemented. Company, job title, description, start date, optional end date (empty = present). |
| `profiles` | `Project` (`PROFILE_PROJECTS`) | FOLDO-04 | Project name, description, URL, dates. |
| `profiles` | `ProjectStory` (`PROJECT_STORIES`) | FOLDO-15 | Optional problem / role / process / solution / outcome (0..1 per project). |
| `profiles` | `ProjectEvidence` (`PROJECT_EVIDENCE`) | FOLDO-15 | Evidence links and images per project. |
| `portfolios` | `PortfolioVersion` | FOLDO-05 | Version name, status, template. |
| `portfolios` | `PortfolioContentSelection` | FOLDO-06 | References to profile content per version. |
| `portfolios` | `PortfolioTemplate` | FOLDO-07 | Template key → renderer. |


Relationships (planned): `User 1─* MainProfile 1─* {Education, Skill, Project,
Experience}` (or `1─1` if the open decision above goes that way),
`Project 1─0..1 ProjectStory`, and `MainProfile 1─* PortfolioVersion`.

Design principle: portfolio versions **reference** profile content rather than
copying it, so editing the main profile updates every portfolio.

## Django admin

The admin is enabled for staff/instructor use. Create a user with:

```bash
python manage.py createsuperuser
```

Instructor (Product Owner) can inspect student data; students use the FOLDO UI.
Models are registered in each app's `admin.py` as they are implemented.

## Backups and safety (production)

- Back up PostgreSQL with `pg_dump` and restore with `psql`.
- Never commit a database dump or `.env` to Git.
