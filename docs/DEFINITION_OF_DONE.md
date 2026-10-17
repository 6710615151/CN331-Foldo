# Definition of Done

A checklist that every FOLDO Issue must satisfy before it can be considered
complete. It applies to all five developers and keeps quality consistent across
Sprints. If an item does not apply, say so explicitly in the Pull Request.

## 1. Scope & acceptance criteria

- [ ] All acceptance criteria written on the GitHub Issue are met.
- [ ] The work implements **only** the assigned Issue — unrelated changes were
      split into a separate branch/PR.
- [ ] No out-of-scope refactoring or "while I'm here" changes are bundled in.
- [ ] The MVP scope is respected (no features beyond the current Sprint Goal).

## 2. Correctness & code quality

- [ ] Code follows the project conventions in `docs/DEVELOPMENT.md`
      (4-space Python, 2-space HTML/CSS/JS, `.editorconfig` respected).
- [ ] Layers are respected: skinny views; reads in `selectors.py`; writes and
      transactions in `services.py`; validation in `forms.py`; schema only in
      `models.py`. No cross-app circular imports.
- [ ] Views are generic CBVs where possible; access mixins sit left-most
      (`LoginRequiredMixin, UpdateView`); class-level URLs use `reverse_lazy()`.
- [ ] Queries that follow relations use `select_related()` /
      `prefetch_related()`; concurrent writes use `@transaction.atomic` +
      `select_for_update()` (see "Coding rules per layer" in `docs/ARCHITECTURE.md`).
- [ ] Templates extend `base.html`, use semantic HTML and reversible
      `{% url %}` namespaces — no hardcoded paths.
- [ ] The UI is responsive (Bootstrap 5 grid/utilities) and keyboard-accessible,
      with visible focus and accessible labels.
- [ ] The page still works with JavaScript disabled (JS is progressive enhancement).

## 3. Testing

- [ ] New behaviour has automated tests in the app's `tests.py`.
- [ ] `python manage.py test` passes with no failures or errors.
- [ ] Edge cases and empty states are covered where relevant.
- [ ] No test was skipped, disabled or weakened to make the build pass.

## 4. Checks & validation

- [ ] `python manage.py check` reports no issues.
- [ ] `python manage.py makemigrations --check --dry-run` reports **no** missing
      migrations (models match committed migrations).
- [ ] `python manage.py check --deploy` is clean for production-affecting changes
      (the dev `SECRET_KEY` warning is expected locally).
- [ ] The development server starts and the new/changed routes respond correctly.

## 5. Database & migrations

- [ ] Any model change ships with a committed migration created by
      `makemigrations` (never hand-written before the model exists).
- [ ] Migrations are named/grouped coherently with the Issue and reviewed before
      committing.
- [ ] No placeholder models or unused tables were added.
- [ ] Schema changes are compatible with both SQLite (dev) and PostgreSQL (prod).

## 6. Security

- [ ] No secrets, credentials, tokens or `.env` values are committed.
- [ ] CSRF and security middleware remain enabled.
- [ ] User input is validated through Django Forms/ModelForms where applicable.
- [ ] Authentication/permission requirements (when in scope) are enforced
      server-side, not just hidden in the UI.
- [ ] Endpoints that return data expose nothing sensitive.

## 7. Documentation

- [ ] User-facing changes are reflected in `README.md` where relevant.
- [ ] Architectural decisions are recorded in `docs/ARCHITECTURE.md`.
- [ ] Setup/command changes are reflected in `docs/DEVELOPMENT.md`.
- [ ] Database changes are reflected in `docs/DATABASE.md`.

## 8. Version control & review

- [ ] Work was done on a correctly named branch (`feat/FOLDO-XX-...`).
- [ ] Commits use Conventional Commits and are small and logical.
- [ ] A Pull Request into `main` is open, referencing the Issue (`Closes #NN`).
- [ ] The PR template is completed (what, why, how tested).
- [ ] At least one other developer has reviewed and approved.
- [ ] All review comments are resolved and required checks (CI) are green.
- [ ] The branch is merged (Squash and merge) and deleted afterwards.

## 9. Definition of "done" for the Sprint

An Issue is done at the Increment level when:

- [ ] It is merged into `main`.
- [ ] `main` still runs (`python manage.py check` + full test suite pass).
- [ ] It is demonstrated to the Product Owner and accepted.
- [ ] The GitHub Project board item is moved to *Done*.
