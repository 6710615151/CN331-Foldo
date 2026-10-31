# API & Error Conventions

Agreed conventions for every response FOLDO returns — server-rendered HTML
pages and the small number of JSON endpoints (`/health/` today; any
AJAX-enhanced endpoint later). Written as the FOLDO-01 team agreement and kept
current as each Issue lands. If a new endpoint needs something not covered
here, add it to this document in the same Pull Request.

## 1. Transport

FOLDO is a server-rendered Django monolith (see `docs/ARCHITECTURE.md`). Most
routes return HTML; there is no general-purpose REST API. A route returns
JSON only when it exists for machine consumption (monitoring, future
progressive-enhancement calls from `static/js/`) — not as a default style.

## 2. HTTP status codes

| Code | Use for |
| ---- | ------- |
| 200  | Successful page render or successful JSON read. |
| 302  | Redirect after a successful form submission (`form_valid()`), or an unauthenticated user redirected to log in. |
| 400  | A malformed request the view cannot interpret (rare outside forms). |
| 401  | Reserved for JSON endpoints that require auth but received none (session auth uses 302 → login instead). |
| 403  | Authenticated, but not allowed to act on this object (`UserPassesTestMixin`, ownership checks). |
| 404  | Unknown route or an object that does not belong to the requesting user — **never** reveal that an object exists for someone else by returning 403 instead of 404. |
| 500  | Unhandled server error. Always rendered as the friendly `500.html` in production (`DEBUG=False`). |
| 503  | A dependency (database, cache) is unreachable — used by `/health/` only. |

## 3. JSON response shape

Every JSON endpoint returns one object, never a bare array, so new fields can
be added without breaking existing clients:

```json
{
  "status": "ok",
  "service": "foldo",
  "version": "0.1.0",
  "checks": { "database": true }
}
```

Rules:

- `status` is always present: `"ok"` or `"degraded"` / `"error"`.
- Keys are `snake_case` (matches Python/Django, not JavaScript convention).
- Timestamps, if ever added, are ISO-8601 UTC (`2026-01-01T00:00:00Z`).
- Never include secrets, environment variable names, stack traces, file
  paths or raw exception text — see `apps.core.selectors.DatabaseHealthCheck`
  for the pattern (swallow the exception, report a boolean).
- IDs exposed in a payload are the model's primary key (integer) unless an
  Issue specifically calls for an opaque/public identifier.

## 4. Form & validation errors (HTML)

Django Forms/ModelForms own all validation; views never duplicate it.

- Re-render the same template with the bound form so field errors show
  inline (`form.errors`), with `{{ field.errors }}` next to each input.
- Use the Django **messages** framework (`templates/partials/messages.html`)
  for one-off, page-level feedback (e.g. "Profile saved.") — not for
  per-field validation errors.
- Never leak which part of a credential pair was wrong (e.g. "that e-mail
  isn't registered") — use one generic message for login failures.
- A `clean_<field>()` / `clean()` method raises `forms.ValidationError` with a
  user-facing, translatable message; services never receive unvalidated
  input (see "Coding rules per layer" in `docs/ARCHITECTURE.md`).

## 5. Ownership & private data

- A view that serves one user's data filters by the requesting user first
  (`get_queryset()` scoped to `request.user`), then 404s on no match — it
  never fetches by ID alone and checks ownership afterwards.
- `LoginRequiredMixin` (and any ownership mixin) sits left-most in the base
  class list so it runs before the view logic.

## 6. Mock data (temporary, pre-Issue)

Some shell pages render against fixed mock data because the owning app
(`apps.profiles`, `apps.portfolios`) does not exist yet — for example
`apps.core.selectors.get_mock_dashboard_summary()`. Convention so it's easy
to find and remove:

- The function name is prefixed `get_mock_*` and its docstring starts with
  `MOCK:`.
- It lives in `selectors.py` (a read), never in `services.py` or a template
  tag, so it is replaced by swapping one function call in the view.
- The template or view referencing it links back to the Issue that will
  replace it (see `apps/core/views.py`).
- Mock data is never written to the database and never returned from a real
  JSON endpoint.

## 7. Scope note

This document covers the request/response surface only. Schema, model and
migration conventions live in `docs/DATABASE.md`; layer responsibilities
(where validation vs. business logic vs. data access live) live in
`docs/ARCHITECTURE.md`.
