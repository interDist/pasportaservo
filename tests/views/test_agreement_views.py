from datetime import timedelta

from django.contrib.flatpages.models import FlatPage
from django.core.cache import cache
from django.test import override_settings, tag
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext as _

from factory import Faker

from core.models import Agreement, Policy
from hosting.models import Phone, Place

from ..factories import (
    AgreementFactory, PhoneFactory, PolicyFactory, UserFactory,
)
from .pages.agreement import AgreementPage, AgreementRejectPage
from .testcasebase import BasicViewTests


@tag('views', 'views-agreement')
class AgreementViewTests(BasicViewTests):
    view_page = AgreementPage

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.faker = Faker._get_faker()

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Create a user with a complex profile
        cls.complex_user = UserFactory.create(
            username='complex_user',
            profile__with_email=True,
            profile__places=2,
        )
        # Add phones manually
        PhoneFactory.create(profile=cls.complex_user.profile)
        PhoneFactory.create(profile=cls.complex_user.profile)

        # Create a FlatPage for terms-conditions
        cls.terms_content = (
            f"{cls.faker.sentence(nb_words=10)}\n\n"
            f"{cls.faker.sentence(nb_words=10)}"
        )
        fp, _ = FlatPage.objects.update_or_create(
            url='/terms-conditions/',
            defaults={
                'title': 'Terms and Conditions',
                'content': cls.terms_content,
            }
        )
        fp.sites.add(1)

    def test_agreement_view_get(self):
        # We use a specific user for these tests
        user = self.complex_user

        # Create policies
        Policy.objects.all().delete()
        PolicyFactory.create(
            version='v1',
            effective_date=timezone.now().date() - timedelta(days=10),
            requires_consent=True,
            content="<p>Policy V1 Content</p>"
        )
        policy2 = PolicyFactory.create(
            version='v2',
            effective_date=timezone.now().date() - timedelta(days=5),
            requires_consent=False,
            content="<p>Policy V2 Content</p>"
        )

        states = [
            {
                'name': 'consent_required',
                'setup': lambda: Agreement.objects.filter(user=user).delete(),
                'expected_alert': 'alert-warning',
                'expected_panel': 'panel-warning',
                'btn_text': _("I agree"),
                'expected_text': _("Dear member of the PS-community, your attention to the policy "
                                   "and conditions of use is required.")
            },
            {
                'name': 'consent_required_new_version',
                'setup': lambda: (
                    Agreement.objects.filter(user=user).delete(),
                    AgreementFactory.create(user=user, policy_version='v0')
                ),
                'expected_alert': 'alert-warning',
                'expected_panel': 'panel-warning',
                'btn_text': _("I agree"),
                'expected_text': _("Dear member of the PS-community, your attention is required. "
                                   "Since %(effective_date)s a new policy and conditions of use "
                                   "are in effect.") % {'effective_date': policy2.effective_date}
            },
            {
                'name': 'consent_obtained_old',
                'setup': lambda: (
                    Agreement.objects.filter(user=user).delete(),
                    AgreementFactory.create(user=user, policy_version='v1')
                ),
                'expected_alert': 'alert-success',
                'expected_panel': 'panel-default',
                'btn_text': _("I still agree"),
                'expected_text': _("You have already indicated your consent to be bound by the "
                                   "policy, published earlier. An updated text of that policy as "
                                   "of %(effective_date)s (below) includes some adjustments but "
                                   "does not introduce any changes in the substance.") % {
                                       'effective_date': policy2.effective_date}
            },
            {
                'name': 'consent_obtained_latest',
                'setup': lambda: (
                    Agreement.objects.filter(user=user).delete(),
                    AgreementFactory.create(user=user, policy_version='v2')
                ),
                'expected_alert': 'alert-success',
                'expected_panel': 'panel-default',
                'btn_text': _("I still agree"),
                'expected_text': _("You have already indicated your consent to be bound by the "
                                   "most up-to-date policy, which is in effect starting on "
                                   "%(effective_date)s.") % {
                                       'effective_date': policy2.effective_date}
            },
        ]

        for state in states:
            for lang in ['en', 'eo']:
                with (
                    override_settings(LANGUAGE_CODE=lang),
                    self.subTest(state=state['name'], lang=lang)
                ):
                    cache.clear()
                    state['setup']()
                    page = self.view_page.open(self, user=user)

                    self.assertIn(state['expected_alert'], page.get_top_notice_class())
                    self.assertIn(state['expected_panel'], page.get_terms_panel_class())
                    self.assertIn(state['expected_panel'], page.get_agreement_panel_class())

                    self.assertEqual(page.get_approve_button().text().strip(), state['btn_text'])
                    # We check for inclusion because there might be multiple spaces/newlines
                    self.assertIn(" ".join(state['expected_text'].split()),
                                  " ".join(page.get_top_notice().text().split()))

                    # Check terms
                    terms_items = page.get_terms_panel().find("li")
                    self.assertEqual(len(terms_items), 2)
                    # Check first terms item <b>
                    first_words = self.terms_content.split('\n\n')[0].split()[:4]
                    expected_b = " ".join(first_words)
                    self.assertEqual(terms_items.eq(0).find("b").text(), expected_b)

                    # Check policy content
                    self.assertIn("Policy V2 Content", page.get_agreement_panel().text())

    def test_agreement_view_no_terms(self):
        # Verify that when the FlatPage is missing, no terms panel is rendered.
        FlatPage.objects.filter(url='/terms-conditions/').delete()
        user = self.complex_user
        page = self.view_page.open(self, user=user)
        self.assertLength(page.get_terms_panel(), 0)

    def test_agreement_view_post_approve(self):
        user = self.complex_user

        # 1. Consent required state
        Policy.objects.all().delete()
        PolicyFactory.create(
            version='v3',
            effective_date=timezone.now().date() - timedelta(days=1),
            requires_consent=True
        )

        Agreement.objects.filter(user=user).delete()
        cache.clear()

        page = self.view_page.open(self, user=user)
        # Action 'approve'
        page.submit_action('approve')
        self.assertEqual(page.response.status_code, 302)
        self.assertEqual(page.response.location, '/')

        # Verify Agreement created
        self.assertTrue(Agreement.objects.filter(user=user, policy_version='v3').exists())

        # 2. Consent obtained state (I still agree)
        initial_agreement = Agreement.objects.get(user=user, policy_version='v3')
        initial_created = initial_agreement.created

        cache.clear()
        page = self.view_page.open(self, user=user)
        # Action 'approve'
        page.submit_action('approve')
        self.assertEqual(page.response.status_code, 302)

        # Verify NO new Agreement created and old one unchanged
        self.assertEqual(Agreement.objects.filter(user=user, policy_version='v3').count(), 1)
        self.assertEqual(Agreement.objects.get(user=user, policy_version='v3').created, initial_created)

    def test_agreement_view_post_approve_redirection(self):
        # Test 'next' parameter
        user = self.complex_user
        Policy.objects.all().delete()
        PolicyFactory.create(version='v4', effective_date=timezone.now().date() - timedelta(days=1))

        test_cases = [
            {'next': None, 'expected': '/'},
            {'next': '', 'expected': '/'},
            {'next': '/about/', 'expected': '/about/'},
            {'next': 'https://external.com', 'expected': '/'},
        ]

        for case in test_cases:
            with self.subTest(next=case['next']):
                Agreement.objects.filter(user=user).delete()
                cache.clear()
                page = self.view_page.open(self, user=user)
                page.submit_action('approve', next_url=case['next'])
                self.assertEqual(page.response.location, case['expected'])

    def test_agreement_view_post_reject(self):
        user = self.complex_user
        Policy.objects.all().delete()
        PolicyFactory.create(version='v5', effective_date=timezone.now().date() - timedelta(days=1))
        Agreement.objects.filter(user=user).delete()
        cache.clear()

        page = self.view_page.open(self, user=user)
        page.submit_action('reject')
        self.assertEqual(page.response.status_code, 302)
        self.assertEqual(page.response.location, str(reverse_lazy('agreement_reject')))
        self.assertEqual(self.app.session.get('agreement_rejected'), 'v5')

    def test_agreement_view_post_unknown(self):
        user = self.complex_user
        page = self.view_page.open(self, user=user)
        page.submit_action('unknown')
        self.assertEqual(page.response.status_code, 302)
        self.assertEqual(page.response.location, str(reverse_lazy('agreement')))


@tag('views', 'views-agreement')
class AgreementRejectViewTests(BasicViewTests):
    view_page = AgreementRejectPage

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Create a user with a complex profile
        cls.complex_user = UserFactory.create(
            username='reject_complex_user',
            profile__with_email=True,
            profile__places=2,
        )
        # Add phones manually
        PhoneFactory.create(profile=cls.complex_user.profile)
        PhoneFactory.create(profile=cls.complex_user.profile)

    def test_agreement_reject_view_get(self):
        user = self.complex_user

        # 1. No agreement in session -> should return empty response
        page = self.view_page.open(self, user=user)
        self.assertEqual(page.response.content, b"")

        # 2. Agreement in session
        expected_text = _("If you don't agree to our terms and conditions and to the usage "
                          "policies, you cannot continue to use Pasporta Servo. In this case,  "
                          "your account will be disabled and your information will not be "
                          "accessible to other users of Pasporta Servo anymore. If you change "
                          "your mind afterwise, you will need to contact us manually to "
                          "restore the access to your account.")

        for lang in ['en', 'eo']:
            with (
                override_settings(LANGUAGE_CODE=lang),
                self.subTest(lang=lang)
            ):
                session = self.app.session
                session['agreement_rejected'] = 'v5'
                session.save()

                page = self.view_page.open(self, user=user)
                self.assertEqual(self.app.session.get('agreement_rejected_final'), 'v5')
                self.assertIn(" ".join(expected_text.split()), " ".join(page.get_well().text().split()))
                self.assertLength(page.get_proceed_button(), 1)
                self.assertLength(page.get_back_link(), 1)

    def test_agreement_reject_view_post(self):
        # Create a complex user with pre-deleted objects
        user = UserFactory.create(username='reject_user', profile__places=2)
        profile = user.profile
        PhoneFactory.create(profile=profile)
        PhoneFactory.create(profile=profile)

        places = list(Place.all_objects.filter(owner=profile).order_by('pk'))
        phones = list(Phone.all_objects.filter(profile=profile).order_by('pk'))

        old_date = timezone.now() - timedelta(days=10)
        places[0].deleted_on = old_date
        places[0].save()
        phones[0].deleted_on = old_date
        phones[0].save()

        # Agreement to withdraw
        AgreementFactory.create(user=user, policy_version='v5')

        # Session setup
        session = self.app.session
        session['agreement_rejected_final'] = 'v5'
        session.save()

        # Ensure user is logged in for the TestApp
        self.app.get('/', user=user)

        response = self.app.post(str(self.view_page.url))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, '/')

        # Verify user deactivated
        user.refresh_from_db()
        self.assertFalse(user.is_active)

        # Verify Profile deleted
        profile.refresh_from_db()
        self.assertIsNotNone(profile.deleted_on)
        rejection_time = profile.deleted_on

        # Verify Places
        for i, place in enumerate(Place.all_objects.filter(owner=profile).order_by('pk')):
            if i == 0:
                self.assertEqual(place.deleted_on, old_date)
            else:
                self.assertEqual(place.deleted_on, rejection_time)

        # Verify Phones
        for i, phone in enumerate(Phone.all_objects.filter(profile=profile).order_by('pk')):
            if i == 0:
                self.assertEqual(phone.deleted_on, old_date)
            else:
                self.assertEqual(phone.deleted_on, rejection_time)

        # Verify Agreement withdrawn
        agreement = Agreement.objects.get(user=user, policy_version='v5')
        self.assertEqual(agreement.withdrawn, rejection_time)

        # Verify logout (check session - WebTest handles this)
        self.assertNotIn('_auth_user_id', self.app.session)

        # Verify "Farewell !" message
        expected_msg = _("Farewell !")
        for lang in ['en', 'eo']:
            with (
                override_settings(LANGUAGE_CODE=lang),
                self.subTest(lang=lang)
            ):
                if lang == 'en':  # Just check for one language to verify logic
                    page = self.view_page.wrap_response(self, response.follow())
                    messages = page.get_toplevel_messages()
                    self.assertIn(expected_msg, messages['content'])
