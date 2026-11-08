"""FOLDO-13: end-to-end flow through the real pages, the way a user clicks through it.

Part 1 (this file): register -> Main Profile -> Project Story -> versions ->
content selection -> template -> preview -> publish link.
Part 2 (added when FOLDO-09 / FOLDO-17 / FOLDO-11 land): republish snapshot -> share/QR -> PDF export.

Every step goes through a URL with the Django test client (no direct model writes),
so a broken link between two features fails here even if each feature's own tests pass.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.portfolios.models import Portfolio
from apps.profiles.models import MainProfile, Project, Skill

User = get_user_model()

PASSWORD = "Str0ng-pass!23"


class EndToEndPart1Tests(TestCase):
    def post_ok(self, url, data):
        """POST a form and fail loudly (with the form errors) if it didn't redirect."""
        response = self.client.post(url, data)
        if response.status_code != 302:
            form = response.context.get("form") if response.context else None
            self.fail(f"POST {url} was not accepted: {getattr(form, 'errors', response.status_code)}")
        return response

    def test_full_flow_part1(self):
        # 1. Register: signed in straight away and sent to the dashboard.
        response = self.post_ok(reverse("accounts:register"), {
            "username": "jeff", "email": "jeff@example.com",
            "password1": PASSWORD, "password2": PASSWORD,
        })
        self.assertRedirects(response, reverse("core:dashboard"))
        user = User.objects.get(username="jeff")
        self.assertEqual(self.client.get(reverse("core:dashboard")).status_code, 200)

        # 2. Main Profile: the first profile becomes the default.
        self.post_ok(reverse("profiles:create"), {
            "label": "Main", "full_name": "Jeff Tester", "headline": "CS student",
            "contact_email": "jeff@example.com",
        })
        profile = MainProfile.objects.get(owner=user)
        self.assertTrue(profile.is_default)

        # 3. Profile sections: two skills, one project with a story, one without.
        self.post_ok(reverse("profiles:skill_add", args=[profile.pk]), {"name": "Python", "proficiency": "advanced"})
        self.post_ok(reverse("profiles:skill_add", args=[profile.pk]), {"name": "Figma", "proficiency": "beginner"})
        self.post_ok(reverse("profiles:project_add", args=[profile.pk]), {
            "project_name": "Resume Rocket", "description": "Portfolio builder",
            "problem": "Students retype the same profile for every application",
            "outcome": "One profile, many portfolios",
        })
        self.post_ok(reverse("profiles:project_add", args=[profile.pk]), {"project_name": "Side project"})
        python = Skill.objects.get(profile=profile, name="Python")
        story_project = Project.objects.get(profile=profile, project_name="Resume Rocket")
        self.assertTrue(story_project.has_story)
        self.assertFalse(Project.objects.get(profile=profile, project_name="Side project").has_story)

        # 4. Two portfolio versions with different templates, both private.
        self.post_ok(reverse("portfolios:create"), {
            "title": "Backend jobs", "profile": profile.pk, "template_key": "classic",
        })
        self.post_ok(reverse("portfolios:create"), {
            "title": "Design jobs", "profile": "", "template_key": "modern",
        })
        backend = Portfolio.objects.get(owner=user, title="Backend jobs")
        design = Portfolio.objects.get(owner=user, title="Design jobs")
        self.assertFalse(backend.is_published)

        # 5. Content selection on one version only.
        self.post_ok(reverse("portfolios:content", args=[backend.pk]), {
            "projects": [story_project.pk], "skills": [python.pk],
        })

        # 6. Preview shows the selection and the Project Story, in the version's own template.
        backend_page = self.client.get(reverse("portfolios:preview", args=[backend.pk])).content.decode()
        self.assertIn("pf--classic", backend_page)
        # Only the portfolio itself: the owner bar above it may show a pending "project added" message.
        backend_html = backend_page[backend_page.index('<main class="pf-page">'):]
        self.assertIn("Resume Rocket", backend_html)
        self.assertIn("Students retype the same profile", backend_html)
        self.assertIn("Python", backend_html)
        self.assertNotIn("Side project", backend_html)
        self.assertNotIn("Figma", backend_html)

        # The other version was never customised, so it shows everything (from the default profile).
        design_html = self.client.get(reverse("portfolios:preview", args=[design.pk])).content.decode()
        self.assertIn("pf--modern", design_html)
        for text in ("Resume Rocket", "Side project", "Python", "Figma"):
            self.assertIn(text, design_html)

        # 7. Device preview (FOLDO-08) shows the same version at phone width.
        self.assertEqual(self.client.get(reverse("portfolios:device_preview", args=[backend.pk]), {"mode": "mobile"}).status_code, 200)
        frame_html = self.client.get(reverse("portfolios:preview_frame", args=[backend.pk])).content.decode()
        self.assertIn("Resume Rocket", frame_html)
        self.assertNotIn("Side project", frame_html)

        # 8. Preview never publishes, and deselecting never deletes source data.
        backend.refresh_from_db()
        self.assertFalse(backend.is_published)
        self.assertEqual(Project.objects.filter(profile=profile).count(), 2)
        self.assertEqual(Skill.objects.filter(profile=profile).count(), 2)

        # 9. Before publishing, the public link is a 404, even for a stranger who guessed it.
        public_url = reverse("portfolios:public", args=[backend.slug])
        self.client.logout()
        self.assertEqual(self.client.get(public_url).status_code, 404)

        # 10. Publish, then the public link opens without logging in and keeps the selection.
        self.client.login(username="jeff", password=PASSWORD)
        self.post_ok(reverse("portfolios:update", args=[backend.pk]), {
            "title": "Backend jobs", "profile": profile.pk, "template_key": "classic", "is_published": "on",
        })
        self.client.logout()
        public = self.client.get(public_url)
        self.assertEqual(public.status_code, 200)
        public_html = public.content.decode()
        self.assertIn("Resume Rocket", public_html)
        self.assertNotIn("Side project", public_html)
        self.assertNotIn(reverse("portfolios:update", args=[backend.pk]), public_html)

        # 11. Unpublishing removes public access again.
        self.client.login(username="jeff", password=PASSWORD)
        self.post_ok(reverse("portfolios:update", args=[backend.pk]), {
            "title": "Backend jobs", "profile": profile.pk, "template_key": "classic",
        })
        self.client.logout()
        self.assertEqual(self.client.get(public_url).status_code, 404)

    def test_another_user_cannot_reach_any_step(self):
        """Every owner-only page in the flow is a 404 for a different signed-in user."""
        owner = User.objects.create_user("owner", password=PASSWORD)
        User.objects.create_user("stranger", password=PASSWORD)
        profile = MainProfile.objects.create(owner=owner, full_name="Owner", is_default=True)
        project = Project.objects.create(profile=profile, project_name="Secret")
        portfolio = Portfolio.objects.create(owner=owner, title="Private", profile=profile)

        self.client.login(username="stranger", password=PASSWORD)
        urls = [
            reverse("profiles:view", args=[profile.pk]),
            reverse("profiles:projects", args=[profile.pk]),
            reverse("profiles:project_detail", args=[project.pk]),
            reverse("portfolios:update", args=[portfolio.pk]),
            reverse("portfolios:content", args=[portfolio.pk]),
            reverse("portfolios:preview", args=[portfolio.pk]),
            reverse("portfolios:device_preview", args=[portfolio.pk]),
            reverse("portfolios:preview_frame", args=[portfolio.pk]),
            reverse("portfolios:public", args=[portfolio.slug]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
