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

The only application model is **`accounts.CustomUser`** (subclass of
`AbstractUser`, no extra fields yet), set as `AUTH_USER_MODEL` from the very
first migration so fields can be added later without a user-model swap. Always
refer to it via `settings.AUTH_USER_MODEL` / `get_user_model()`, never
`auth.User`. Besides it, only Django's built-in tables exist (`auth` groups and
permissions, `admin`, `contenttypes`, `sessions`). No placeholder tables were
created — an unused model plus migration is noise and confuses the team.

Planned models are documented in the source and arrive with their Issues:

| App | Model | Issue | Purpose |
| --- | ----- | ----- | ------- |
| `profiles` | `Profile` | FOLDO-02 | One-to-one with `AUTH_USER_MODEL`; personal details. |
| `profiles` | `Education` | FOLDO-03 | Institution, degree, field, dates. |
| `profiles` | `Skill` | FOLDO-03 | Name, category, proficiency. |
| `profiles` | `Project` | FOLDO-03 | Title, description, link, dates. |
| `profiles` | `Experience` | FOLDO-03 | Organisation, role, description, dates. |
| `portfolios` | `PortfolioVersion` | FOLDO-04 | Title, target role/company, template. |
| `portfolios` | `PortfolioSectionItem` | FOLDO-05 | Ordered references to profile content. |
| `portfolios` | `TemplateChoice` | FOLDO-06 | Template key → renderer. |

Relationships (planned): `User 1─1 Profile 1─* {Education, Skill, Project,
Experience}`, and `Profile 1─* PortfolioVersion 1─* PortfolioSectionItem`.

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
