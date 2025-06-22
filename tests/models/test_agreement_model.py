import re

from django.db import IntegrityError
from django.test import override_settings, tag
from django.utils import timezone

from django_webtest import WebTest

from ..factories import AgreementFactory, UserFactory


@tag('models')
class AgreementModelTests(WebTest):
    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory(profile=None)

    def test_field_max_lengths(self):
        accord = AgreementFactory.build()
        self.assertEqual(accord._meta.get_field('policy_version').max_length, 50)

    def test_field_blanks(self):
        accord = AgreementFactory.build()
        self.assertTrue(accord._meta.get_field('withdrawn').blank)

    def test_field_defaults(self):
        accord = AgreementFactory.build()
        self.assertIs(accord._meta.get_field('withdrawn').default, None)

    def test_str(self):
        expected_strings = {
            'en': 'User .+ agreed to \'{}\' ',
            'eo': 'Uzanto .+ akceptis \'{}\' ',
        }

        accord = AgreementFactory()
        policy_version_string = re.escape(accord.policy_version)
        for lang in expected_strings:
            with override_settings(LANGUAGE_CODE=lang):
                self.assertRegex(str(accord), expected_strings[lang].format(policy_version_string))

    def test_prevent_duplicate_active_agreements(self):
        policy_v = "terms_v1.2"
        AgreementFactory(user=self.user, policy_version=policy_v, withdrawn=None)
        with self.assertRaises(IntegrityError):
            AgreementFactory(user=self.user, policy_version=policy_v, withdrawn=None)

    def test_allow_duplicate_if_one_withdrawn(self):
        policy_v = "terms_v1.3"
        AgreementFactory(user=self.user, policy_version=policy_v, withdrawn=timezone.now())
        # This should not raise an error
        try:
            AgreementFactory(user=self.user, policy_version=policy_v, withdrawn=None)
        except IntegrityError:
            self.fail("IntegrityError raised unexpectedly when creating a new active agreement after a withdrawn one.")

        accord = AgreementFactory(withdrawn=timezone.now())
        policy_version_string = re.escape(accord.policy_version)
        for lang in expected_strings:
            with override_settings(LANGUAGE_CODE=lang):
                self.assertRegex(str(accord), expected_strings[lang].format(policy_version_string))
