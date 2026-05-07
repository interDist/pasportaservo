from unittest.mock import MagicMock, patch

from django.test import override_settings, tag
from django.urls import reverse

from django_webtest import WebTest

from links.utils import create_unique_url
from tests.assertions import AdditionalAsserts
from tests.factories import PlaceFactory


@tag('views', 'views-links')
class UniqueLinkViewTests(AdditionalAsserts, WebTest):
    @classmethod
    def setUpTestData(cls):
        cls.place = PlaceFactory()
        cls.owner = cls.place.owner
        cls.user = cls.owner.user

    def setUp(self):
        self.config_patcher = patch('core.models.SiteConfiguration.get_solo')
        self.mock_config = self.config_patcher.start()
        self.mock_config.return_value = MagicMock(
            salt='test-salt',
            token_max_age=3600
        )

    def tearDown(self):
        self.config_patcher.stop()

    def test_confirm_action(self):
        payload = {'action': 'confirm', 'place': self.place.pk}
        url, token = create_unique_url(payload)

        # English
        with override_settings(LANGUAGE_CODE='en'):
            response = self.app.get(url).follow()
            self.assertTemplateUsed(response, 'links/confirmed.html')
            self.assertIn("Data confirmed", response.pyquery("title").text())
            self.assertIn("Data confirmed", response.pyquery("h1").text())
            self.assertIn("You just confirmed that your profile and address are up-to-date. Thanks!",
                          response.pyquery("h3").text())

        # Esperanto
        with override_settings(LANGUAGE_CODE='eo'):
            response = self.app.get(url).follow()
            self.assertTemplateUsed(response, 'links/confirmed.html')
            self.assertIn("Informoj konfirmitaj", response.pyquery("title").text())
            self.assertIn("Informoj konfirmitaj", response.pyquery("h1").text())
            self.assertIn("Vi ĵus konfirmis ke viaj profilo kaj adreso estas aktualaj. Dankon!",
                          response.pyquery("h3").text())

    def test_already_confirmed_action(self):
        self.place.confirmed = True
        self.owner.confirmed = True
        self.place.save()
        self.owner.save()

        payload = {'action': 'confirm', 'place': self.place.pk}
        url, token = create_unique_url(payload)

        # English
        with override_settings(LANGUAGE_CODE='en'):
            response = self.app.get(url).follow()
            self.assertTemplateUsed(response, 'links/already_confirmed.html')
            self.assertIn("Already confirmed", response.pyquery("h1").text())
            self.assertIn("You already confirmed the accuracy of your profile and address. Thanks!",
                          response.pyquery("h3").text())

        # Esperanto
        with override_settings(LANGUAGE_CODE='eo'):
            response = self.app.get(url).follow()
            self.assertTemplateUsed(response, 'links/already_confirmed.html')
            self.assertIn("Informoj jam konfirmitaj", response.pyquery("h1").text())
            self.assertIn("Vi jam konfirmis la aktualecon de viaj profilo kaj adreso. Dankon!",
                          response.pyquery("h3").text())

    def test_update_action(self):
        payload = {'action': 'update', 'place': self.place.pk}
        url, token = create_unique_url(payload)

        response = self.app.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, self.owner.get_absolute_url())

        # Verify user is logged in
        response = response.follow()
        self.assertEqual(int(response.context['user'].id), self.user.id)

    @patch('links.views.URLSafeTimedSerializer.loads')
    def test_signature_expired(self, mock_loads):
        from itsdangerous import SignatureExpired
        mock_loads.side_effect = SignatureExpired("Signature expired")

        url = reverse('unique_link', kwargs={'token': 'some-token'})

        # English
        with override_settings(LANGUAGE_CODE='en'):
            response = self.app.get(url)
            self.assertTemplateUsed(response, 'links/signature_expired.html')
            self.assertIn("Invalid Link", response.pyquery(".hero-title").text())
            self.assertIn("Signature Expired", response.pyquery(".hero-subtitle").text())
            self.assertIn("The link is not valid anymore", response.pyquery(".hero-subtitle small").text())

        # Esperanto
        with override_settings(LANGUAGE_CODE='eo'):
            response = self.app.get(url)
            self.assertTemplateUsed(response, 'links/signature_expired.html')
            self.assertIn("Malbona ligilo", response.pyquery(".hero-title").text())
            self.assertIn("Tempostampo ne plu validas", response.pyquery(".hero-subtitle").text())
            # "The link is not valid anymore" is not translated in .po file, so it should stay in English or be empty
            # Looking at the .po file it was: msgstr ""
            self.assertIn("The link is not valid anymore", response.pyquery(".hero-subtitle small").text())

    @patch('links.views.URLSafeTimedSerializer.loads')
    def test_bad_time_signature(self, mock_loads):
        from itsdangerous import BadTimeSignature
        mock_loads.side_effect = BadTimeSignature("Bad time signature")

        url = reverse('unique_link', kwargs={'token': 'some-token'})

        # English
        with override_settings(LANGUAGE_CODE='en'):
            response = self.app.get(url)
            self.assertTemplateUsed(response, 'links/bad_time_signature.html')
            self.assertIn("Invalid Link", response.pyquery(".hero-title").text())
            self.assertIn("Bad Time Signature", response.pyquery(".hero-subtitle").text())
            self.assertIn("The link seems not valid", response.pyquery(".hero-subtitle").text())

        # Esperanto
        with override_settings(LANGUAGE_CODE='eo'):
            response = self.app.get(url)
            self.assertTemplateUsed(response, 'links/bad_time_signature.html')
            self.assertIn("Malbona ligilo", response.pyquery(".hero-title").text())
            self.assertIn("Malbona tempostampo", response.pyquery(".hero-subtitle").text())
            self.assertIn("La ligilo ne ŝajnas esti valida plu.", response.pyquery(".hero-subtitle").text())

    @patch('links.views.URLSafeTimedSerializer.loads')
    def test_bad_signature(self, mock_loads):
        from itsdangerous import BadSignature
        mock_loads.side_effect = BadSignature("Bad signature")

        url = reverse('unique_link', kwargs={'token': 'some-token'})

        # English
        with override_settings(LANGUAGE_CODE='en'):
            response = self.app.get(url)
            self.assertTemplateUsed(response, 'links/invalid_link.html')
            self.assertIn("Invalid Link", response.pyquery(".hero-title").text())
            self.assertIn("The link is not valid", response.pyquery(".hero-subtitle").text())

        # Esperanto
        with override_settings(LANGUAGE_CODE='eo'):
            response = self.app.get(url)
            self.assertTemplateUsed(response, 'links/invalid_link.html')
            self.assertIn("Malbona ligilo", response.pyquery(".hero-title").text())
            self.assertIn(
                "La ligilo havas malbonan formon aŭ malĝustan konfirmo-ĵetonon.",
                response.pyquery(".hero-subtitle").text()
            )

    def test_invalid_payload(self):
        payload = {'not-action': 'something'}
        url, token = create_unique_url(payload)

        response = self.app.get(url)
        self.assertTemplateUsed(response, 'links/invalid_link.html')
        self.assertIn("Invalid Link", response.pyquery(".hero-title").text())
