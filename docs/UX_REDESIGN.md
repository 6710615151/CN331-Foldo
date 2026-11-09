# UX redesign — audit and changes

Scope: usability, navigation and feedback across the signed-in app. The visual
identity (tokens, tones, components) is unchanged; new styles live in
`static/css/ux.css` and use only existing tokens. No models, migrations, URLs or
business rules changed. Tests: 417 existing + 27 new (`apps/core/test_ux.py`), all passing.

## Audit: problems found

| # | Area | Problem | Impact |
|---|------|---------|--------|
| 1 | Portfolio builder | Setup, content, preview, quality and share were five separate pages with no shared sense of order; back links all went to the list | Users didn't know what step they were on or what came next |
| 2 | Navigation | Sidebar Education / Skills / Projects always pointed at the *default* profile, even while viewing another one | Clicking the sidebar silently switched profiles |
| 3 | Navigation | No way to move between a profile's sections without going back to its overview | Extra clicks, lost context |
| 4 | Dashboard | "Next step" only knew 3 coarse milestones; said "ready to share" with no education/skills/projects | No guidance once the basics existed; empty sections hidden |
| 5 | Dashboard | "Create portfolio" CTA appeared 5 times; quick-action tiles were static | Noise instead of guidance |
| 6 | Forms | Failed validation showed a toast + red fields only; nothing linked to the fields | Hard to find errors on long forms, poor for keyboard/screen readers |
| 7 | Forms | Leaving a half-filled form lost the data silently | Accidental data loss |
| 8 | Data entry | Adding several skills/education rows meant list → add → save → list → add… | Repetitive clicks |
| 9 | Publishing | Publish is a switch inside the setup form; turning it off breaks shared links with no warning; "go publish" links landed at the top of the form | Accidental unpublish; publishing hard to find |
| 10 | Quality check | A clean report had no next action; severities weren't explained | Dead end at the moment the user is ready to share |
| 11 | Export | PDF download gave no feedback while generating | Repeat clicks |
| 12 | Templates | No way to see which templates are already used; theme picker linked only to the whole gallery | Weak comparison |
| 13 | Profile | Completion checklist items weren't links; profile form had no overview of what's required | Users hunted for the field |

## Changes

**Wayfinding**
- Builder stepper on every version page (`portfolios/_workflow.html`): 1 ตั้งค่าและดีไซน์ → 2 เลือกเนื้อหา → 3 ดูตัวอย่าง → 4 ตรวจคุณภาพ → 5 เผยแพร่และแชร์. Shows real state (content customised, published), never blocks a step; on the create page later steps are shown locked.
- "Next step" card at the end of each step (`portfolios/_workflow_next.html`). Quality check picks the next action from the report: fix first error → publish → open Share Kit.
- Sidebar follows the profile being viewed (`AppShell.nav_profile`), with a "which profile / switch" chip when the user has 2+ profiles.
- Profile sub-nav (`profiles/_section_nav.html`) on overview, education, skills & experience, projects, with counts and "ว่าง" (empty) markers.

**Guidance**
- One next-steps engine, `apps.core.selectors.get_next_steps`: required journey steps (bell + dashboard), then recommendations (education, skills, projects, Project Story, experience, photo). Each step deep-links to the exact field (e.g. `…/edit/#id_headline`, `#id_is_published`, `#sec-story`).
- Dashboard: "สิ่งที่ควรทำต่อ" card replaces static tiles (shortcuts kept as chips); empty section counts link to their add forms; each version shows one follow-up (share or check & publish); the 3-step banner shows only before the first version.
- Profile detail: checklist items link to their fields; "make this profile stronger" list.
- Profile form: side checklist of required/recommended fields that updates live.
- Project form: Project Story progress meter (x/5) and a worked example.
- Template gallery: "ใช้อยู่ใน N เวอร์ชัน" badges; theme picker links to each template rendered with the user's own profile.

**Feedback and safety**
- Error summary at the top of every form (`partials/form_errors.html`), linking to each invalid field; focus moves there after a failed submit.
- Unsaved-changes guard (`data-unsaved-guard`) on all edit forms: warns before leaving, and the sticky bar says "มีการเปลี่ยนแปลงที่ยังไม่บันทึก".
- Publish switch explains the consequence before saving (links stop working / page becomes public).
- PDF links show "กำลังสร้าง PDF…"; duplicate shows a loading state.
- Device preview labelled "โหมดดูตัวอย่าง · อ่านอย่างเดียว"; full-page preview toolbar now includes content selection and share.

**Fewer clicks**
- "บันทึกแล้วเพิ่มอีก" on create forms for education, skills, experience and projects (`apps.core.mixins.AddAnotherMixin`). It changes only where a *successful* save redirects.

## Deliberately not changed
- Redirect targets that tests lock in (e.g. portfolio save → full-page preview).
- Backend message text (some are English; tests assert them).
- No new endpoints (e.g. one-click publish), to avoid new business logic.

## Verified in a browser (Chromium, 1440px and 390px)
Error summary focus + data kept; summary links focus the field; deep links focus the field; unsaved guard fires on leave and not on save; no horizontal overflow at 390px; no console errors across 23 pages.
