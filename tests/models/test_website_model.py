from django.test import TestCase, tag
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from hosting.models import Website
from ..factories import ProfileFactory, WebsiteFactory


@tag('models', 'website')
class WebsiteModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.profile = ProfileFactory()
        cls.website = WebsiteFactory(profile=cls.profile, url="https://example.com")

    def test_create_website(self):
        self.assertIsNotNone(self.website.pk)
        self.assertEqual(self.website.profile, self.profile)
        self.assertEqual(self.website.url, "https://example.com")

    def test_website_str(self):
        self.assertEqual(str(self.website), "https://example.com")

    def test_website_repr(self):
        expected_repr = f"<Website: https://example.com |p#{self.profile.pk}>"
        self.assertEqual(repr(self.website), expected_repr)

    def test_owner_property(self):
        self.assertEqual(self.website.owner, self.profile)

    def test_url_validation_invalid(self):
        # Model-level URLField validation is handled by Django during full_clean or save
        # This test checks if saving an invalid URL raises an error (usually ValidationError from full_clean)
        with self.assertRaises(ValidationError):
            Website(profile=self.profile, url="invalid-url").full_clean()

        # Some DBs might not raise error for invalid URL on save if full_clean isn't called
        # but Django's save() calls full_clean() by default if not disabled.
        # Depending on DB backend, an IntegrityError or other DB error might occur
        # if constraints are violated directly at DB level without full_clean.
        # For this test, we rely on full_clean.

    def test_url_validation_valid(self):
        try:
            Website(profile=self.profile, url="http://valid.co.uk/path?query=yes").full_clean()
            Website(profile=self.profile, url="https://another-example.com:8080").full_clean()
        except ValidationError:
            self.fail("ValidationError raised unexpectedly for a valid URL.")

    def test_profile_deletion_cascades(self):
        # Ensure that when a Profile is deleted, related Website instances are also deleted.
        profile_to_delete = ProfileFactory()
        WebsiteFactory(profile=profile_to_delete, url="https://site1.com")
        WebsiteFactory(profile=profile_to_delete, url="https://site2.com")

        website_count_before_delete = Website.objects.filter(profile=profile_to_delete).count()
        self.assertEqual(website_count_before_delete, 2)

        profile_to_delete.delete()

        website_count_after_delete = Website.objects.filter(profile=profile_to_delete).count()
        self.assertEqual(website_count_after_delete, 0)
