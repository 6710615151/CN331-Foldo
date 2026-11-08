# Release Checklist (FOLDO-13)

Run through this before tagging a release or deploying. Tick every box; anything
unticked is a release blocker unless the team agrees otherwise in the Sprint Review.

## 1. Code

- [ ] `main` CI is green (check, missing-migration check, tests on Python 3.11 and 3.12)
- [ ] `python manage.py test` passes locally, including `apps/core/test_e2e*.py` and `apps/core/test_regression.py`
- [ ] `python manage.py makemigrations --check --dry-run` → `No changes detected`
- [ ] No open PR marked as a release blocker

## 2. Production settings

Set these on the host (see `.env.example` for every variable):

- [ ] `DJANGO_DEBUG=False`
- [ ] `DJANGO_SECRET_KEY` = a new random value (never the development default)
- [ ] `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` = the real domain
- [ ] Database settings for PostgreSQL (`DB_ENGINE=postgresql` and the `DB_*` values)
- [ ] `DJANGO_LOG_LEVEL=INFO` (the `.env.example` default `DEBUG` logs hundreds of lines per PDF export)
- [ ] `DJANGO_DEBUG=False python manage.py check --deploy` shows no warnings that matter
- [ ] Static files are served with `DEBUG=False` (`collectstatic` has run and something serves `/static/`)
- [ ] Uploaded profile photos (`/media/`) are stored somewhere that survives a redeploy
- [ ] Pango is installed on the server, so PDF export works (see README → Prerequisites)

## 3. Smoke test on the deployed site

As a new user, in a private browser window:

- [ ] Register, then land on the dashboard
- [ ] Create a profile; add a skill and a project with a Project Story
- [ ] Create two portfolio versions with different templates; choose content for one
- [ ] Preview both, including Desktop / Mobile
- [ ] Publish one; open its public link logged out; the draft's link is a 404
- [ ] Share Kit: copy the link and scan the QR code with a phone
- [ ] Export a PDF of the draft; it downloads and the draft is still unpublished
- [ ] Portfolio DNA and Quality Check open without errors
- [ ] Unpublish; the public link is a 404 again
- [ ] On a phone: no page scrolls sideways

## 4. Sign-off

- [ ] Every Sprint exit criterion in the Sprint plan is met, or the gap is written down
- [ ] README and `docs/` describe the current setup
- [ ] Product Owner has seen the demo (Sprint Review)