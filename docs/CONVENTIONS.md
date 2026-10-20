# Shared Conventions (FOLDO-10)

Rules every FOLDO developer follows so data stays private, input is checked the
same way everywhere, and errors look the same on every page. The shared code
lives in `apps/core/` and `templates/partials/`; each rule below says which file
to use. Examples of every rule are in `apps/core/tests.py`.

## 1. Data ownership — nobody sees another user's data

Every view that shows, edits or deletes private data uses `OwnerRequiredMixin`
(`apps/core/mixins.py`), placed **left-most**:

```python
from apps.core.mixins import OwnerRequiredMixin

class EducationUpdateView(OwnerRequiredMixin, UpdateView):
    model = Education
    owner_field = "profile__user"
```

- Not signed in → redirected to the login page.
- Another user's row → **404**, not 403, so nobody can tell whether an id exists (prevents IDOR).
- The owner always comes from `request.user`. Never accept `user_id` or `profile_id` from a form or URL.

`owner_field` per table (from the ER diagram):

| Table | `owner_field` |
| --- | --- |
| `USER_SETTINGS`, `MAIN_PROFILES` | `"user"` (default) |
| `PROFILE_EDUCATIONS`, `PROFILE_EXPERIENCES`, `PROFILE_SKILLS`, `PROFILE_PROJECTS`, `PORTFOLIO_VERSIONS` | `"profile__user"` |
| `PROJECT_STORIES`, `PROJECT_EVIDENCE` | `"project__profile__user"` |
| `PORTFOLIO_SECTIONS`, `PORTFOLIO_CONTENT_SELECTIONS` | `"version__profile__user"` |
| `PORTFOLIO_TEMPLATES` | shared by everyone — do not use the mixin |

**`PORTFOLIO_CONTENT_SELECTIONS.content_id` has no foreign key.** The mixin only
checks who owns the selection row. Before saving a selection, also check that
the item behind `content_id` belongs to the same profile.

## 2. Validation — check input on the server, the same way everywhere

- Every user input goes through a Django `Form` / `ModelForm` (`forms.py`). Use
  `form.cleaned_data` only after `form.is_valid()`; never save `request.POST` directly.
- `ModelForm` lists its fields by name (`fields = [...]`). Never `"__all__"`, and
  never include `owner`, `user`, `profile` or `is_staff`.
- Every field that stores a link uses `safe_url_validator` (`apps/core/validators.py`):
  only `http` / `https`.
- Text fields use the shared maximum lengths:

| Constant | Characters | For |
| --- | --- | --- |
| `MAX_SHORT_NAME` | 100 | display name, skill name |
| `MAX_SHORT_TEXT` | 200 | project name, job title, institution |
| `MAX_URL` | 500 | any link |
| `MAX_LONG_TEXT` | 5000 | bio, description, project story |

- Database access goes through the Django ORM. No SQL built from strings.

## 3. Forms and error messages — the same look on every page

Add `BootstrapFormMixin` (`apps/core/forms.py`) left-most on every form, and
render it with the two shared partials:

```python
from apps.core.forms import BootstrapFormMixin

class AccountForm(BootstrapFormMixin, forms.ModelForm):
    ...
```

```django
<form method="post">
  {% csrf_token %}
  {% include "partials/form_errors.html" %}
  {% for field in form %}{% include "partials/form_field.html" %}{% endfor %}
  <button type="submit" class="btn btn-foldo">Save</button>
</form>
```

- `form_errors.html` — errors for the whole form, at the top
  (e.g. "username or password is incorrect").
- `form_field.html` — one field with its label, help text and error under it.
- Every `<form method="post">` has `{% csrf_token %}`. Never use `@csrf_exempt`.
- After a successful save: `messages.success(...)` then `redirect(...)`, so a page
  refresh never submits the form twice. Messages appear through `partials/messages.html`.

## 4. Error pages and empty lists

| Situation | What the user sees | How |
| --- | --- | --- |
| Not signed in | Login page, then back to where they were | `OwnerRequiredMixin` / `LoginRequiredMixin` |
| No permission | `templates/403.html` | `raise PermissionDenied` |
| Not found, or someone else's data | `templates/404.html` | ownership filter (section 1) |
| Unexpected error | `templates/500.html` | automatic when `DEBUG=False` |
| List with nothing in it | message + "Add" button | `partials/empty_state.html` |

```django
{% url "profiles:education_add" as add_url %}
{% for education in educations %}
  ...
{% empty %}
  {% include "partials/empty_state.html" with message="No education yet" action_url=add_url action_label="Add education" %}
{% endfor %}
```

## 5. Showing user text safely

Django escapes everything in `{{ }}` automatically. Keep it that way: never use
`|safe`, `mark_safe` or `{% autoescape off %}` on anything a user typed.
(`|safe` is allowed only on text written by developers, such as form help text.)

## 6. Tests — every new page proves it is private

FOLDO uses Django's test runner (`python manage.py test`). Every view with
private data gets these tests, copied from `OwnerRequiredMixinTests`:

1. The owner can open their own row → 200.
2. Another signed-in user opens the same row → **404**.
3. A visitor who is not signed in → redirected to login (302).

## 7. API

FOLDO renders HTML with Django templates; there is no JSON API in Sprint 1.
The only JSON endpoint is `/health/`, which must never expose settings,
secrets or environment variable names.