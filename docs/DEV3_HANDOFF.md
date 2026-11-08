# Dev 3 handoff — Sprint 1–5, stopped mid-Sprint-4/5 rework

Written by Claude (saifadecha07's assistant) because the session ran out of
budget. Picks up for whoever continues (Gemini or a human). Read this whole
file before touching `apps/insights/`.

## TL;DR

- Sprint 1–3 Dev 3 work is **merged into `main` and done**.
- Sprint 4 (FOLDO-14, Portfolio DNA) and Sprint 5 (FOLDO-16, Quality Check)
  are **written, tested, pushed, PRs open — but built against the wrong
  contract**. They will not give correct results against the real app once
  merged. **Do not merge #41 / #42 as-is.** See "What's actually broken" below.

## Branch / PR chain (stacked, in merge order)

| PR | Branch | Status | Contains |
| --- | --- | --- | --- |
| #24 | `feat/FOLDO-02-app-shell-onboarding` | **merged** | Sprint 1: nav, onboarding, dashboard shell |
| #27 | `fix/FOLDO-02-shell-auth-integration` | **merged** | Sprint 1: login-gate the shell |
| #28 | `#3FOLDOMain-Profile-full-stack` (HomemadeSalads) | **merged** | FOLDO-03 Main Profile (their work) |
| #29 | `feat/FOLDO-03-profile-integration` | **merged into #28** | My Sprint 2 tests + dashboard wiring |
| #30 | `feat/FOLDO-03-finish` | **merged into #28** | Fixed #28's bugs (broken password reset, unsafe migration, open redirect), shared conventions, theme |
| #31 | `feat/FOLDO-07-templates-rendering` | **merged into main** | `apps.rendering`: 3 templates + `build_portfolio_content`/`render_portfolio_html`. **This part is fine and is what the team built on.** |
| #41 | `feat/FOLDO-14-portfolio-dna` | **open, do not merge yet** | Portfolio DNA — wrong contract, see below |
| #42 | `feat/FOLDO-16-quality-check` | **open, do not merge yet** | Quality Check — depends on #41, same problem |

All of #24/#27/#28/#29/#30/#31 are safely in `main`. Nothing there needs
redoing.

## What's actually broken in #41 / #42

While I was writing `apps/insights` (Sprint 4/5), the rest of the team merged
**PR #32 "Feat/foldo 5,6,7,8,9,14 fullsprint3 and portfolio"** into `main`,
which built the *real* FOLDO-04/05/06/07/08/09/15 apps. I designed
`apps/insights/sources.py` against an assumed contract (profile owns
everything directly: `profile.skills`, `profile.educations`,
`profile.portfolio_versions`, a `PortfolioContentSelection` with
`content_type`/`content_id`). **That assumed contract does not match what's
actually on `main` now.**

### The real contract on `main` today

- **`apps.portfolios`** (not a relation on `MainProfile`): `Portfolio` model
  — `owner` FK (user, not profile!), `profile` FK (nullable — "follow my
  default profile" when empty), `template_key`, `is_published`, `slug`.
  - `apps/portfolios/services.py` is the entry point:
    `get_portfolios(user)`, `get_portfolio(user, pk)`,
    `resolve_profile(portfolio)` (chosen profile, else the owner's default),
    `theme_for(portfolio)`, `selected_ids(portfolio)` (returns a
    `{section: {ids}}` dict **or `None`** — currently **always `None`**
    because FOLDO-06's `content_selection` submodule isn't merged yet, so
    every portfolio shows everything), `build_version_content(portfolio)`,
    `render_version_html(portfolio, ...)`.
  - URL name for a version's page: `portfolios:preview` (one `pk` arg).
- **`apps.education`** is its **own app**, not part of `apps.profiles`.
  `EducationEntry.owner` is a **direct FK to the user**, not to
  `MainProfile`. One row per `Level` choice (phd/graduate/undergraduate/
  high_school), `is_blank` property. Read via
  `apps.education.services.get_entries(user)` /
  `get_education_display(user)`. **This means education is shared across
  every one of a user's profiles/portfolios — it is not per-profile.**
  URL name: `education:settings` (no pk — it's one page per user).
- **`apps.profiles.skills_experience`**: `Skill`/`Experience`, FK
  `profile`, read via `selectors.get_skills(profile)` /
  `get_experiences(profile)`. URL names: `profiles:skill_edit`,
  `profiles:experience_edit` (what I assumed — this part is fine).
- **`apps.profiles.projects`**: exists with its own
  `selectors.py`/`services.py`/`urls.py` — **not inspected yet**, read it
  before relying on it. URL names look like `profiles:project_edit` /
  `profiles:project_detail` (confirm in `apps/profiles/projects/urls.py`).
- **`apps.rendering`** (mine, #31, since extended by the team): section keys
  are still `"skills"`, `"experience"`, `"education"`, `"projects"` via
  `SECTION_SPECS` in `apps/rendering/selectors.py` — **that part still
  matches**. `render_portfolio_html` gained a `noindex: bool` kwarg I don't
  pass (harmless default, but check).

### What this means for `apps/insights/sources.py`

Needs a rewrite of `portfolio_versions()` and the skills/experience/
education/projects lookups:

```python
# WRONG (what's there now):
manager = getattr(profile, "portfolio_versions", None)   # no such relation
...
items = providers.get(key, ...)(profile)                  # assumes profile.skills etc.

# RIGHT (sketch):
from apps.portfolios.services import get_portfolios, resolve_profile, selected_ids
from apps.education.services import get_entries as get_education_entries
from apps.profiles.skills_experience.selectors import get_skills, get_experiences
from apps.profiles.projects.selectors import ...  # read this file first

def portfolio_versions_for_profile(profile):
    versions = []
    for portfolio in get_portfolios(profile.owner):
        resolved = resolve_profile(portfolio)
        if resolved is None or resolved.pk != profile.pk:
            continue
        versions.append(VersionRef(
            id=portfolio.pk,
            name=portfolio.title,
            url=reverse("portfolios:preview", args=[portfolio.pk]),
            selected=selected_ids(portfolio),   # dict OR None — see below
            template=portfolio.template_key,
        ))
    return versions
```

**`VersionRef.selected` needs a 3rd state.** Right now `DnaRow`/`uses()`
treats "not in the dict" as unused. But `selected_ids(portfolio)` returning
`None` means "FOLDO-06 hasn't landed, so this portfolio shows **everything**
from its profile" — that is NOT the same as "uses nothing". Fix `uses()`:

```python
def uses(self, section, item_id):
    if self.selected is None:
        return True   # no selection system yet => portfolio shows everything
    return item_id in self.selected.get(section, frozenset())
```

And `compute_dna`'s "missing" check (stale selection pointing at a deleted
item) only makes sense when `selected` is an actual dict — skip it when
`None`.

**Education is cross-profile.** Because `EducationEntry.owner` is the user,
not the profile, every portfolio of that user "uses" the same education rows
regardless of which `MainProfile` it's attached to. Simplest fix: in
`source_sections()`, pull education via `get_education_entries(profile.owner)`
(not scoped to profile) and accept that its "used in" list is really "used in
any of this user's portfolios", which is fine since DNA is scoped to one
profile's page anyway — just document the caveat in the template/docstring.

**`apps/insights/quality.py`** has the same disease wherever it calls
`default_providers()` / assumes `profile.<section>` — same fix pattern
applies (use the real selectors above). The severity rules themselves
(missing fields, bad links, empty sections, render failure, crash-isolation)
are not the problem, only the data-source wiring.

### Tests to fix after rewiring

`apps/insights/tests.py` and `apps/insights/test_quality.py` currently use
fake `providers()` dicts and `SimpleNamespace` rows (that part is fine and
can stay — the unit tests for `compute_dna`/`run_quality_check` logic don't
need real models). What needs new tests: an integration test creating a real
`apps.portfolios.Portfolio`, a real `apps.education.EducationEntry`, and
asserting `portfolio_versions_for_profile()` / `source_sections()` return the
right things against actual `main` models. **These don't exist yet** —
that's the main gap, not the pure-logic tests.

## Recommended next steps, in order

1. `git fetch && git log --oneline -30 origin/main` — see if the team merged
   even more since this was written (check for a `content_selection`
   submodule landing — if it has, `selected_ids()` will start returning real
   dicts and the "always None" assumption above goes stale).
2. Read `apps/profiles/projects/selectors.py`, `services.py`, `urls.py` in
   full (not done in this session) — needed for the projects section of
   `source_sections()`.
3. Rebase `feat/FOLDO-14-portfolio-dna` onto current `origin/main` (not onto
   my stale `feat/FOLDO-07-templates-rendering` chain — that's now
   redundant since #31 is already in `main`). Simplest: new branch from
   `origin/main`, cherry-pick/rewrite `apps/insights/` onto it.
4. Rewrite `sources.py` per the sketch above; rerun
   `python manage.py test apps.insights`.
5. Rewrite/extend `quality.py`'s data wiring the same way.
6. Add the real-model integration tests described above.
7. Close #41 and #42 (or force-push the rebased branches over them — ask the
   human first, these are shared branches) and open fresh PRs against
   current `main`.
8. **`docs/CONVENTIONS.md` §8/§9 in this repo still describe my original
   (wrong) `profile.portfolio_versions` / `PortfolioContentSelection
   .content_type/content_id` contract.** Fix or remove those sections once
   the real contract is confirmed, so the next person doesn't make the same
   mistake I did.

## Things that are solid and don't need rework

- Everything in `main` up through PR #31 (Sprint 1–3: app shell, Main
  Profile, 3 portfolio templates + `build_portfolio_content`/
  `render_portfolio_html`).
- The **logic** in `apps/insights/dna.py` (`compute_dna`) and
  `apps/insights/quality.py` (the `Finding`/severity/check-isolation
  machinery) — only the functions that fetch data need rewiring, not the
  analysis itself.
- `.env.example` / `EMAIL_BACKEND` fix (console backend locally, SMTP from
  env) — merged via #30, unrelated to this problem.

## Credentials / commit note

Commits in this session were made without a `Co-Authored-By` trailer per the
repo owner's standing preference (see this session's memory file
`feedback_commit_attribution.md` if you have access to it) — keep doing that
unless told otherwise.
