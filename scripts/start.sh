#!/bin/sh
# Container entrypoint: migrate, optionally create the first admin, then serve.
set -e

python manage.py migrate --noinput

# One-time admin bootstrap: set DJANGO_SUPERUSER_USERNAME / _EMAIL / _PASSWORD in
# the host's environment. Does nothing (and never fails the boot) if it exists.
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    python manage.py createsuperuser --noinput 2>/dev/null || true
fi

exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-2}" \
    --timeout 120 \
    --access-logfile -
