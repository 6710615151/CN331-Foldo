# Development Guide

Exact commands to get FOLDO running locally. Local development uses a Python
virtual environment and SQLite.

## 1. Prerequisites

- **Python 3.11+** (Django 5.2 requires 3.10+). Verified with **Python 3.11.16**.
- `venv` and `pip` (bundled with Python).
- Git.

Check your Python version — the system default on some machines is too old:

```bash
python3 --version
# If it is below 3.10, install a newer Python, e.g. on macOS:
#   brew install python@3.11
# then use `python3.11` instead of `python3` below.
```

## 2. Clone and create a virtual environment

```bash
git clone https://github.com/6710615151/CN331-Foldo.git
cd CN331-Foldo

python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
```

Your prompt should now start with `(.venv)`. Re-activate the environment in each
new terminal with `source .venv/bin/activate`.

## 3. Install dependencies

```bash
pip install --upgrade pip

# Production/runtime dependencies only:
pip install -r requirements.txt

# …or everything, including development tools (recommended for local work):
pip install -r requirements-dev.txt
```

`requirements.txt` holds what the app needs at runtime: Django 5.2, psycopg 3
(PostgreSQL driver), the redis client and python-dotenv. `requirements-dev.txt`
adds developer conveniences on top — currently **django-browser-reload** — and
is not needed to run the app.

## 4. Configure environment variables

Local development works with **zero configuration** thanks to development
defaults in `config/settings.py` (SQLite + `DEBUG=True`). To override anything:

```bash
cp .env.example .env
```

`.env` is git-ignored — never commit it. Only `.env.example` is tracked. Key
variables:

| Variable | Dev default | Purpose |
| -------- | ----------- | ------- |
| `DJANGO_SECRET_KEY` | dev-only key | Must be unique/random in production. |
| `DJANGO_DEBUG` | `True` | Set `False` in production. |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated hostnames. |
| `DB_ENGINE` | `sqlite` | Set `postgresql` for PostgreSQL. |
| `REDIS_URL` | *(empty)* | Set to use Redis for caching. |

Generate a strong key when you need one:

```bash
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

## 5. Create the database and run the server

```bash
python manage.py migrate
python manage.py runserver
```

Open <http://127.0.0.1:8000/>. Run on a different port with
`python manage.py runserver 8080`.

Optional admin access:

```bash
python manage.py createsuperuser
# then visit http://127.0.0.1:8000/admin/
```

## 6. Running tests and checks

```bash
python manage.py test                       # run all tests
python manage.py test apps.core             # a single app
python manage.py test -v 2                  # verbose
python manage.py check                      # framework checks
python manage.py check --deploy             # production security checks
```

`check --deploy` prints a warning if `SECRET_KEY` is the development default —
that is expected locally.

## 7. Database migration workflow

When you change a model:

```bash
python manage.py makemigrations <app_label>   # create the migration
python manage.py migrate                      # apply it
python manage.py makemigrations --check --dry-run   # CI-style check
```

Always commit the generated migration file alongside the model change.

## 8. Common tasks

```bash
python manage.py shell                # interactive Python shell with Django loaded
python manage.py showmigrations       # list migration status
python manage.py collectstatic        # gather static files into staticfiles/
```

Reset the local database (SQLite only — deletes all local data):

```bash
rm db.sqlite3 && python manage.py migrate
```

## 9. Project conventions

- **Formatting:** 4 spaces for Python, 2 for HTML/CSS/JS (see `.editorconfig`).
- **Templates:** extend `base.html`, use `{% url %}` namespaces, no hardcoded paths.
- **Models:** only add a model with the Issue that needs it; never add placeholders.
- **Layers (per app):** views stay skinny; reads go in `selectors.py`, writes
  (create/update/delete, `@transaction.atomic`) in `services.py`, validation in
  `forms.py`, and `models.py` holds only schema. See `docs/ARCHITECTURE.md`.
- **Tests:** each app keeps its tests in its own `tests.py`.
- **Security:** never disable CSRF or security middleware; never hardcode secrets.

## 10. Troubleshooting

| Symptom | Fix |
| ------- | --- |
| `Django requires Python 3.10+` | Use `python3.11` to create the venv. |
| `No module named django` | The venv is not activated — run `source .venv/bin/activate`. |
| Port already in use | `python manage.py runserver 8001`. |
| Static files 404 in dev | Ensure `django.contrib.staticfiles` is installed (it is) and `DEBUG=True`. |
| `.env` values ignored | `.env` must sit next to `manage.py`; restart the server after editing. |

## 11. Editing CSS, templates and static files (live reload)

Front-end assets are served **directly from source** during development, so you
rarely need to restart anything:

- **CSS / JS / templates** — edit `static/…` or `templates/…`, save, and the
  browser refreshes the change. No server restart.
- **Python (`.py`)** — `runserver`'s autoreloader restarts the server for you.

### Automatic browser refresh (already configured)

`django-browser-reload` is wired into `settings.py` and is active **only when
`DEBUG=True`** (it is never enabled in production). Install the dev requirements
once, then just run the server:

```bash
pip install -r requirements-dev.txt
python manage.py runserver
```

Now, saving a `.css`, `.js`, `.html` or `.py` file reloads the open page
automatically — no manual refresh.

- The reload script is injected automatically by the middleware; nothing to add
  to templates.
- It connects over `/__reload__/` (a DEBUG-only URL) and works with WSGI and ASGI.
- On Safari, use version 16+ (needs `SharedWorker`).
- File watching is handled by **`django-watchfiles`** (also DEBUG-only), which
  uses the OS instead of polling — much lower CPU with faster, batched reloads on
  macOS. `runserver` prints `Watching for file changes with WatchfilesReloader`
  to confirm it is active.

### If a change does not show up

1. **Hard refresh:** Cmd+Shift+R (macOS) / Ctrl+Shift+R (Windows/Linux).
2. **Disable cache while developing:** DevTools (F12) → Network → tick *Disable
   cache*.
3. Confirm you edited the source file (`static/css/styles.css`), not a collected
   copy under `staticfiles/` — that folder is generated by `collectstatic` and is
   only used in production.

### Quick theming

The FOLDO palette lives in one place — the `:root` block at the top of
`static/css/styles.css`:

```css
:root {
  --foldo-accent: #2b45e0;   /* primary brand colour */
  --foldo-canvas: #f6f7f9;   /* page background */
  --foldo-ink: #12141a;      /* text colour */
  --foldo-radius: 10px;      /* corner rounding */
}
```

Edit those variables to re-theme the whole site at once.
