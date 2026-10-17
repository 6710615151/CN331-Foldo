# Git & GitHub Workflow

FOLDO follows **GitHub Flow**: a stable `main` branch that everyone protects,
short-lived feature branches, and Pull Requests with review. This document is the
agreed process for all five developers.

## Golden rules

1. **Never commit directly to `main`.**
2. **One branch = one Issue.** Keep branches small and short-lived.
3. **Every change reaches `main` through a reviewed Pull Request.**
4. **`main` must always be runnable** — tests and checks pass before merge.
5. Never force-push or rewrite history on shared branches.

## Branch naming

`<type>/FOLDO-<issue>-<short-description>`

Use the Conventional Commit *type* as the prefix:

| Type | Use for | Example |
| ---- | ------- | ------- |
| `feat` | a new feature | `feat/FOLDO-02-main-profile` |
| `fix` | a bug fix | `fix/FOLDO-02-profile-validation` |
| `test` | tests only | `test/FOLDO-02-profile-tests` |
| `docs` | documentation | `docs/update-development-guide` |
| `refactor` | internal cleanup | `refactor/FOLDO-03-skill-service` |
| `chore` | tooling/config | `chore/update-ci-python` |

Examples:

```text
feat/FOLDO-02-main-profile
feat/FOLDO-03-education-skills-projects
fix/FOLDO-02-profile-validation
test/FOLDO-02-profile-tests
docs/update-development-guide
```

## Conventional Commits

Format: `<type>(<scope>): <subject>` — imperative, lower-case, no trailing period.

```text
feat(core): initialize Django project
feat(core): create dashboard shell
test(core): add landing page tests
docs: add local development instructions
fix(profiles): validate required profile fields
refactor(portfolios): extract portfolio service
chore(deps): pin Django to 5.2 LTS
```

Scopes are the app names (`core`, `profiles`, `portfolios`) plus `docs`, `ci` or
`deps`. Keep the subject under ~72 characters; add detail in the body if needed.

## The daily loop

```bash
# 1. Update local main
git checkout main
git pull origin main

# 2. Create a feature branch
git checkout -b feat/FOLDO-02-main-profile

# 3. Work only on the assigned Issue
#    ... edit files, write tests ...

# 4. Run the relevant checks
python manage.py check
python manage.py test

# 5. Commit in small, logical steps
git add -A
git commit -m "feat(profiles): add main profile model"

# 6. Push the branch
git push -u origin feat/FOLDO-02-main-profile

# 7. Open a Pull Request into main (on GitHub), request a reviewer
```

Keep your branch current before requesting review:

```bash
git checkout main && git pull
git checkout feat/FOLDO-02-main-profile
git merge main          # resolve conflicts locally, then re-run tests
git push
```

## Pull Requests

Every PR must:

- Reference its Issue (e.g. `Closes #12`).
- Describe **what** changed, **why**, and **how it was tested**.
- Stay focused on one Issue (split unrelated work into another branch).
- Pass all required checks and have at least one approving review.

The PR template at `.github/pull_request_template.md` prompts for this
information automatically.

### Code review

Reviewers check that the change:

- Solves the Issue and respects the MVP scope.
- Keeps `main` runnable (tests pass; `check --deploy` clean for production code).
- Follows the conventions in `docs/DEVELOPMENT.md` and `.editorconfig`.
- Adds or updates tests and documentation where relevant.
- Introduces no secrets, and keeps `DEBUG=False` behaviour intact.

Review comments are addressed with new commits (never force-push while a review
is in progress). Re-request review after pushing fixes.

## Merging

- **Merge only after approval** and green checks.
- Prefer **Squash and merge** so each Issue becomes one readable commit on `main`.
- Delete the branch after merging.
- Pull `main` locally afterwards before starting the next Issue.

## Branch protection (maintainers, verify in GitHub)

These are configured in **GitHub → Settings → Branches → Branch protection
rules** for `main`. They are **not** set automatically — a maintainer must
confirm each one:

- [ ] Require a pull request before merging.
- [ ] Require at least **1 approval**.
- [ ] Dismiss stale approvals when new commits are pushed.
- [ ] Require review from Code Owners (if a `CODEOWNERS` file is added).
- [ ] Require status checks to pass (the CI workflow `Django CI`).
- [ ] Require branches to be up to date before merging.
- [ ] Require conversation resolution before merging.
- [ ] Do not allow bypassing the above settings.
- [ ] (Optional) Require linear history.

## GitHub Project / Backlog

- The **Product Owner (instructor)** owns priorities on the GitHub Project board.
- The **Scrum Master** (rotates each Sprint) maintains the board, runs
  ceremonies and tracks the Sprint Goal.
- Every Issue has: a clear description, acceptance criteria, a size estimate and
  a link to its Sprint.
- Move an Issue to *In Progress* when you start it and to *In Review* when the
  PR is open.
