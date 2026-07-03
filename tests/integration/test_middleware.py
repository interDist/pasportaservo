import time
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.test import override_settings, tag
from django.urls import reverse
from django.utils import timezone

from django_webtest import WebTest
from faker import Faker
from postman.api import pm_write
from postman.models import Message

from core.models import Policy, UserBrowser

from ..factories import UserFactory

fake = Faker()


@tag('integration', 'middleware')
class MiddlewareTests(WebTest):
    def test_missing_usage_policies(self):
        Policy.objects.all().delete()
        with self.assertRaisesMessage(
                RuntimeError,
                "Service misconfigured: No user agreement was defined."
        ):
            self.app.get(reverse('account_settings'), user=UserFactory(profile=None))


@tag('integration', 'middleware')
class ConnectionInfoTests(WebTest):
    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory(profile=None)
        cls.general_url = reverse('about')

    def test_anonymous_user(self):
        self.app.get(self.general_url, user=AnonymousUser())
        self.assertNotIn('connection_id', self.app.session, msg=self.app.session.items())
        self.assertNotIn('connection_browser', self.app.session, msg=self.app.session.items())

    def test_missing_user_agent_info(self):
        self.app.get(self.general_url, user=self.user)
        self.assertNotIn('connection_id', self.app.session, msg=self.app.session.items())
        self.assertNotIn('connection_browser', self.app.session, msg=self.app.session.items())

    @patch('core.middleware.geocoder.ip')
    def test_connection_logged(self, mock_geoip):
        number_existing_conn_objects = UserBrowser.objects.count()
        mock_geoip.return_value.ok = mock_geoip.return_value.current_result.ok = True

        # Accessing the website from a browser (that sends a user agent string)
        # is expected to log a new connection.
        mock_geoip.return_value.state = None
        mock_geoip.return_value.country = 'AQ'
        self.app.get(
            self.general_url,
            user=self.user,
            headers={'User-Agent': 'Mozilla/5.0'})
        mock_geoip.assert_called_once()
        self.assertIn('connection_id', self.app.session, msg=self.app.session.items())
        user_conn_id = self.app.session['connection_id']
        self.assertIn('connection_browser', self.app.session, msg=self.app.session.items())
        self.assertEqual(self.app.session['connection_browser'], "Other")
        self.assertEqual(UserBrowser.objects.count(), number_existing_conn_objects + 1)

        self.app.reset()
        mock_geoip.reset_mock()

        # Accessing the website from the same browser and a different location
        # is expected to log a new connection.
        mock_geoip.return_value.state = None
        mock_geoip.return_value.country = 'GL'
        self.app.get(
            self.general_url,
            user=self.user,
            headers={'User-Agent': 'Mozilla/5.0'})
        mock_geoip.assert_called_once()
        self.assertIn('connection_id', self.app.session, msg=self.app.session.items())
        self.assertNotEqual(self.app.session['connection_id'], user_conn_id)
        self.assertIn('connection_browser', self.app.session, msg=self.app.session.items())
        self.assertEqual(self.app.session['connection_browser'], "Other")
        self.assertEqual(UserBrowser.objects.count(), number_existing_conn_objects + 2)

    @patch('core.middleware.geocoder.ip')
    def test_connection_not_logged(self, mock_geoip):
        mock_geoip.return_value.ok = mock_geoip.return_value.current_result.ok = True
        mock_geoip.return_value.state = 'Saskatchewan'
        mock_geoip.return_value.country = 'CA'
        self.app.get(
            self.general_url,
            user=self.user,
            headers={'User-Agent': 'Mozilla/5.0'})
        user_conn_id = self.app.session['connection_id']
        number_existing_conn_objects = UserBrowser.objects.count()

        self.app.reset()
        mock_geoip.reset_mock()

        # Accessing the website from the same browser and location is not expected
        # to log a new connection.
        self.app.get(
            self.general_url,
            user=self.user,
            headers={'User-Agent': 'Mozilla/5.0'})
        mock_geoip.assert_called_once()
        self.assertIn('connection_id', self.app.session, msg=self.app.session.items())
        self.assertEqual(self.app.session['connection_id'], user_conn_id)
        self.assertEqual(UserBrowser.objects.count(), number_existing_conn_objects)

        self.app.reset()
        mock_geoip.reset_mock()

        # Accessing the website from the same browser and an unknown location is
        # not expected to log a new connection.
        mock_geoip.return_value.current_result.ok = False
        self.app.get(
            self.general_url,
            user=self.user,
            headers={'User-Agent': 'Mozilla/5.0'})
        mock_geoip.assert_called_once()
        self.assertIn('connection_id', self.app.session, msg=self.app.session.items())
        self.assertEqual(self.app.session['connection_id'], user_conn_id)
        self.assertEqual(UserBrowser.objects.count(), number_existing_conn_objects)

    @patch('core.middleware.geocoder.ip')
    def test_connection_reuse(self, mock_geoip):
        mock_geoip.return_value.ok = mock_geoip.return_value.current_result.ok = False
        self.app.get(
            self.general_url,
            user=self.user,
            headers={'User-Agent': 'Mozilla/5.0'})
        user_conn_id = self.app.session['connection_id']
        number_existing_conn_objects = UserBrowser.objects.count()

        mock_geoip.reset_mock()
        time.sleep(0.250)

        # Accessing the website again in a short period of time through the
        # same session, even if the browser and/or the location differ, is
        # expected to reuse the existing connection.
        mock_geoip.return_value.ok = mock_geoip.return_value.current_result.ok = True
        mock_geoip.return_value.state = 'Nunavut'
        mock_geoip.return_value.country = 'CA'
        self.app.get(
            self.general_url,
            headers={'User-Agent': 'Mozilla/5.５'.encode('utf-8')})
        mock_geoip.assert_not_called()
        self.assertEqual(self.app.session['connection_id'], user_conn_id)
        self.assertEqual(UserBrowser.objects.count(), number_existing_conn_objects)

        mock_geoip.reset_mock()

        # Accessing the website again after more than 24 hours through the
        # same session is expected to log a new connection.
        session = self.app.session
        session['flag_connection_logged'] = timezone.now() - timezone.timedelta(hours=25)
        session.save()
        self.app.get(
            self.general_url,
            headers={'User-Agent': 'Mozilla/5.５'.encode('utf-8')})
        mock_geoip.assert_called_once()
        self.assertNotEqual(self.app.session['connection_id'], user_conn_id)
        self.assertEqual(UserBrowser.objects.count(), number_existing_conn_objects + 1)


@tag('integration', 'middleware')
class PostmanMiddlewareTests(WebTest):
    @classmethod
    def setUpTestData(cls):
        # Users without profiles
        cls.user_no_profile = UserFactory.create(profile=None)
        cls.staff_no_profile = UserFactory.create(is_staff=True, profile=None)
        cls.superuser_no_profile = UserFactory.create(is_superuser=True, profile=None)

        # Users with profiles
        cls.user_with_profile = UserFactory.create()
        cls.staff_with_profile = UserFactory.create(is_staff=True)

        # Another user to be the counterparty for messages
        cls.other_user = UserFactory.create()

        # Create a message for view/reply tests
        pm_write(cls.other_user, cls.user_no_profile, fake.sentence(), fake.paragraph())
        cls.msg = Message.objects.filter(recipient=cls.user_no_profile).first()

    def _test_blocked(self, url, user, method='get'):
        if method == 'get':
            response = self.app.get(url, user=user, status=403)
        else:
            response = self.app.post(url, user=user, status=403)

        self.assertTemplateUsed(response, 'registration/profile_create.html')
        return response

    def test_postman_urls_blocked_for_regular_user_no_profile(self):
        urls = [
            reverse('postman:inbox'),
            reverse('postman:sent'),
            reverse('postman:write'),
            reverse('postman:view', kwargs={'message_id': self.msg.pk}),
            reverse('postman:reply', kwargs={'message_id': self.msg.pk}),
        ]
        for url in urls:
            with self.subTest(url=url):
                self._test_blocked(url, self.user_no_profile)

    def test_postman_urls_blocked_for_staff_no_profile(self):
        # Staff is NOT superuser, so they should be blocked too if no profile
        url = reverse('postman:inbox')
        self._test_blocked(url, self.staff_no_profile)

    def test_postman_urls_allowed_for_superuser_no_profile(self):
        url = reverse('postman:inbox')
        self.app.get(url, user=self.superuser_no_profile, status=200)

    def test_postman_urls_allowed_for_users_with_profile(self):
        urls = [
            (reverse('postman:inbox'), self.user_with_profile),
            (reverse('postman:inbox'), self.staff_with_profile),
        ]
        for url, user in urls:
            with self.subTest(user=user):
                self.app.get(url, user=user, status=200)

    def test_postman_post_blocked(self):
        for url_name in ['postman:sent', 'postman:write']:
            url = reverse(url_name)
            with self.subTest(url=url):
                self._test_blocked(url, self.user_no_profile, method='post')

    def test_content_translation(self):
        url = reverse('postman:inbox')

        # English
        with override_settings(LANGUAGE_CODE='en'):
            res = self.app.get(url, user=self.user_no_profile, status=403)
            self.assertContains(
                res,
                "To be able to communicate with other members of the PS community, you need to create a profile."
            )
            self.assertContains(res, "Inbox")

        # Esperanto
        with override_settings(LANGUAGE_CODE='eo'):
            res = self.app.get(url, user=self.user_no_profile, status=403)
            # msgstr "Por havi la eblecon komuniki kun aliaj PS-anoj, vi devas krei kaj agordi vian profilon."
            self.assertContains(
                res,
                "Por havi la eblecon komuniki kun aliaj PS-anoj, vi devas krei kaj agordi vian profilon."
            )
            # msgid "Inbox" msgstr "Poŝtkesto"
            self.assertContains(res, "Poŝtkesto")
